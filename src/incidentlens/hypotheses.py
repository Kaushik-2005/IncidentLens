from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from incidentlens.contracts import Confidence, Evidence, IncidentInput

HypothesisStatus = Literal[
    "candidate",
    "supported",
    "contradicted",
    "insufficient_evidence",
]


class EvidenceTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_ids_are_disjoint(self) -> "EvidenceTable":
        supporting = set(self.supporting_evidence_ids)
        contradicting = set(self.contradicting_evidence_ids)
        overlap = supporting & contradicting
        if overlap:
            raise ValueError(f"evidence cannot both support and contradict: {sorted(overlap)}")
        return self


class HypothesisCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    causal_mechanism: str | None = None
    evidence: EvidenceTable
    confidence: Confidence
    status: HypothesisStatus
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status_evidence(self) -> "HypothesisCandidate":
        if self.status == "insufficient_evidence" and not self.evidence.missing_evidence:
            raise ValueError("insufficient_evidence requires at least one missing evidence item")
        if self.status == "supported" and not self.evidence.supporting_evidence_ids:
            raise ValueError("supported hypotheses require supporting evidence")
        if self.status == "contradicted" and not self.evidence.contradicting_evidence_ids:
            raise ValueError("contradicted hypotheses require contradicting evidence")
        return self


VerificationStatus = Literal[
    "supported",
    "low_confidence",
    "contradicted",
    "insufficient_evidence",
]


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str = Field(min_length=1)
    status: VerificationStatus
    confidence: Confidence
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ModelCritiqueProposal(BaseModel):
    """Untrusted model output; it is not accepted as a final verification result."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str = Field(min_length=1)
    evidence: EvidenceTable
    rationale: str = Field(min_length=1)


class VerifierContext(BaseModel):
    """Isolated context available to the verifier, separate from specialist chats."""

    model_config = ConfigDict(extra="forbid")

    incident_id: str = Field(min_length=1)
    neutral_summary: str = Field(min_length=1)
    hypotheses: list[HypothesisCandidate] = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)

    @property
    def available_evidence_ids(self) -> set[str]:
        return {item.evidence_id for item in self.evidence}


class VerifierRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "critique_limit_exceeded"]
    critique_rounds_used: int = Field(ge=0)
    results: list[VerificationResult] = Field(default_factory=list)


class VerifierAgent:
    """Bounded verifier boundary; provider-specific model APIs stay outside it."""

    def __init__(self, max_critique_rounds: int = 2) -> None:
        if max_critique_rounds < 1:
            raise ValueError("max_critique_rounds must be at least 1")
        self.max_critique_rounds = max_critique_rounds

    def build_context(
        self,
        incident: IncidentInput,
        hypotheses: list[HypothesisCandidate],
        evidence: list[Evidence],
    ) -> VerifierContext:
        if not hypotheses:
            raise ValueError("verifier requires at least one hypothesis")
        context = VerifierContext(
            incident_id=incident.incident_id,
            neutral_summary=incident.summary,
            hypotheses=hypotheses,
            evidence=evidence,
        )
        for hypothesis in context.hypotheses:
            validate_hypothesis_evidence(hypothesis, context.available_evidence_ids)
        return context

    def review(
        self,
        context: VerifierContext,
        hypothesis_id: str,
        critique_round: int = 1,
        review_fn: Callable[[HypothesisCandidate, set[str]], VerificationResult] | None = None,
    ) -> VerificationResult:
        self._validate_round(critique_round)
        hypothesis = self._find_hypothesis(context, hypothesis_id)
        reviewer = review_fn or verify_hypothesis
        return reviewer(hypothesis, context.available_evidence_ids)

    def review_with_model(
        self,
        context: VerifierContext,
        hypothesis_id: str,
        model: Callable[[dict[str, Any]], Any],
        critique_round: int = 1,
    ) -> VerificationResult:
        """Ask a model for a critique proposal, then deterministically verify it."""
        self._validate_round(critique_round)
        hypothesis = self._find_hypothesis(context, hypothesis_id)
        request = {
            "incident_id": context.incident_id,
            "neutral_summary": context.neutral_summary,
            "hypothesis": hypothesis.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in context.evidence],
            "critique_round": critique_round,
        }
        try:
            proposal = ModelCritiqueProposal.model_validate(model(request))
        except Exception as exc:
            raise ValueError("INVALID_CRITIQUE_PROPOSAL") from exc
        if proposal.hypothesis_id != hypothesis_id:
            raise ValueError("HYPOTHESIS_SCOPE_MISMATCH")
        validate_evidence_table(proposal.evidence, context.available_evidence_ids)
        result = classify_evidence(
            hypothesis_id=hypothesis_id,
            evidence=proposal.evidence,
            confidence=hypothesis.confidence,
            reasons=[proposal.rationale],
        )
        return result

    def run(self, context: VerifierContext) -> VerifierRunResult:
        results = [
            self.review(context, hypothesis.hypothesis_id) for hypothesis in context.hypotheses
        ]
        return VerifierRunResult(
            status="completed",
            critique_rounds_used=1,
            results=results,
        )

    def _validate_round(self, critique_round: int) -> None:
        if critique_round < 1 or critique_round > self.max_critique_rounds:
            raise ValueError("CRITIQUE_ROUND_LIMIT_EXCEEDED")

    @staticmethod
    def _find_hypothesis(context: VerifierContext, hypothesis_id: str) -> HypothesisCandidate:
        hypothesis = next(
            (item for item in context.hypotheses if item.hypothesis_id == hypothesis_id),
            None,
        )
        if hypothesis is None:
            raise ValueError("UNKNOWN_HYPOTHESIS_ID")
        return hypothesis


def build_verifier_context(
    incident: IncidentInput,
    hypotheses: list[HypothesisCandidate],
    evidence: list[Evidence],
) -> VerifierContext:
    return VerifierAgent().build_context(incident, hypotheses, evidence)


def validate_evidence_table(evidence: EvidenceTable, available_evidence_ids: set[str]) -> None:
    cited_ids = set(evidence.supporting_evidence_ids) | set(evidence.contradicting_evidence_ids)
    unknown_ids = cited_ids - available_evidence_ids
    if unknown_ids:
        raise ValueError(f"hypothesis cites unknown evidence IDs: {sorted(unknown_ids)}")


def validate_hypothesis_evidence(
    hypothesis: HypothesisCandidate,
    available_evidence_ids: set[str],
) -> HypothesisCandidate:
    validate_evidence_table(hypothesis.evidence, available_evidence_ids)
    return hypothesis


def classify_evidence(
    *,
    hypothesis_id: str,
    evidence: EvidenceTable,
    confidence: Confidence,
    reasons: list[str],
) -> VerificationResult:
    if evidence.missing_evidence:
        status: VerificationStatus = "insufficient_evidence"
        result_confidence: Confidence = Confidence.LOW
        reasons = [*reasons, "required evidence is unavailable"]
    elif evidence.contradicting_evidence_ids and not evidence.supporting_evidence_ids:
        status = "contradicted"
        result_confidence = Confidence.LOW
        reasons = [*reasons, "available evidence contradicts the hypothesis"]
    elif evidence.contradicting_evidence_ids:
        status = "low_confidence"
        result_confidence = Confidence.LOW
        reasons = [*reasons, "supporting and contradicting evidence are both present"]
    elif evidence.supporting_evidence_ids:
        status = "supported"
        result_confidence = confidence
    else:
        status = "insufficient_evidence"
        result_confidence = Confidence.LOW
        reasons = [*reasons, "no supporting or contradicting evidence was provided"]

    return VerificationResult(
        hypothesis_id=hypothesis_id,
        status=status,
        confidence=result_confidence,
        supporting_evidence_ids=list(evidence.supporting_evidence_ids),
        contradicting_evidence_ids=list(evidence.contradicting_evidence_ids),
        missing_evidence=list(evidence.missing_evidence),
        reasons=reasons,
    )


def verify_hypothesis(
    hypothesis: HypothesisCandidate,
    available_evidence_ids: set[str],
) -> VerificationResult:
    """Apply deterministic grounding checks to one candidate hypothesis."""
    validate_hypothesis_evidence(hypothesis, available_evidence_ids)
    return classify_evidence(
        hypothesis_id=hypothesis.hypothesis_id,
        evidence=hypothesis.evidence,
        confidence=hypothesis.confidence,
        reasons=[],
    )
