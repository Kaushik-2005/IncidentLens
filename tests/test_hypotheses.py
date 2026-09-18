from typing import Any

import pytest
from pydantic import ValidationError

from incidentlens.contracts import Evidence, IncidentInput
from incidentlens.hypotheses import (
    EvidenceTable,
    HypothesisCandidate,
    VerifierAgent,
    build_verifier_context,
    validate_hypothesis_evidence,
    verify_hypothesis,
)


def test_supporting_and_contradicting_evidence_must_be_disjoint() -> None:
    with pytest.raises(ValidationError, match="both support"):
        HypothesisCandidate(
            hypothesis_id="H1",
            statement="Payment service degraded.",
            evidence=EvidenceTable(
                supporting_evidence_ids=["E1"],
                contradicting_evidence_ids=["E1"],
            ),
            confidence="low",
            status="candidate",
        )


def test_unknown_hypothesis_evidence_is_rejected() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="Payment service degraded.",
        evidence=EvidenceTable(supporting_evidence_ids=["E99"]),
        confidence="low",
        status="candidate",
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        validate_hypothesis_evidence(hypothesis, {"E1", "E2"})


def test_insufficient_evidence_is_explicit() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="A deployment caused the latency increase.",
        evidence=EvidenceTable(
            supporting_evidence_ids=["E1"],
            missing_evidence=["deployment event and rollback correlation"],
        ),
        confidence="low",
        status="insufficient_evidence",
    )

    assert hypothesis.status == "insufficient_evidence"
    assert hypothesis.evidence.missing_evidence


def test_insufficient_evidence_requires_missing_evidence() -> None:
    with pytest.raises(ValidationError, match="missing evidence"):
        HypothesisCandidate(
            hypothesis_id="H1",
            statement="Payment service degraded.",
            evidence=EvidenceTable(),
            confidence="low",
            status="insufficient_evidence",
        )


def test_verifier_rejects_unknown_evidence_before_classifying() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="Payment service degraded.",
        evidence=EvidenceTable(supporting_evidence_ids=["E99"]),
        confidence="high",
        status="candidate",
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        verify_hypothesis(hypothesis, {"E1"})


def test_verifier_downgrades_conflicting_evidence() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="Payment service degraded.",
        evidence=EvidenceTable(
            supporting_evidence_ids=["E1"],
            contradicting_evidence_ids=["E2"],
        ),
        confidence="high",
        status="candidate",
    )

    result = verify_hypothesis(hypothesis, {"E1", "E2"})

    assert result.status == "low_confidence"
    assert result.confidence == "low"


def test_verifier_returns_insufficient_evidence_for_missing_signal() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="A deployment caused the latency increase.",
        evidence=EvidenceTable(
            supporting_evidence_ids=["E1"],
            missing_evidence=["deployment timing and rollback result"],
        ),
        confidence="medium",
        status="insufficient_evidence",
    )

    result = verify_hypothesis(hypothesis, {"E1"})

    assert result.status == "insufficient_evidence"
    assert result.confidence == "low"


def test_verifier_context_excludes_unexpected_peer_or_ground_truth_fields() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="Payment service degraded.",
        evidence=EvidenceTable(supporting_evidence_ids=["E1"]),
        confidence="medium",
        status="candidate",
    )
    incident = IncidentInput(
        incident_id="incident-001",
        title="Latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency increased.",
    )
    evidence = [Evidence(evidence_id="E1", source="trace", summary="Payment span slow.")]

    context = build_verifier_context(incident, [hypothesis], evidence)
    serialized = context.model_dump_json()

    assert "peer_conclusion" not in serialized
    assert "hidden_ground_truth" not in serialized
    assert context.available_evidence_ids == {"E1"}

    with pytest.raises(ValidationError):
        VerifierAgent().build_context(incident, [hypothesis], evidence).model_validate(
            {**context.model_dump(), "expected_root_cause": "database"}
        )


def test_verifier_rejects_out_of_scope_hypothesis_evidence_before_run() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="Payment service degraded.",
        evidence=EvidenceTable(supporting_evidence_ids=["E99"]),
        confidence="medium",
        status="candidate",
    )
    incident = IncidentInput(
        incident_id="incident-001",
        title="Latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency increased.",
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        build_verifier_context(incident, [hypothesis], [])


def test_verifier_enforces_critique_round_limit() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="Payment service degraded.",
        evidence=EvidenceTable(supporting_evidence_ids=["E1"]),
        confidence="medium",
        status="candidate",
    )
    incident = IncidentInput(
        incident_id="incident-001",
        title="Latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency increased.",
    )
    evidence = [Evidence(evidence_id="E1", source="trace", summary="Payment span slow.")]
    verifier = VerifierAgent(max_critique_rounds=2)
    context = verifier.build_context(incident, [hypothesis], evidence)

    verifier.review(context, "H1", critique_round=2)
    with pytest.raises(ValueError, match="CRITIQUE_ROUND_LIMIT_EXCEEDED"):
        verifier.review(context, "H1", critique_round=3)


def test_verifier_run_returns_one_result_per_candidate() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="Payment service degraded.",
        evidence=EvidenceTable(supporting_evidence_ids=["E1"]),
        confidence="medium",
        status="candidate",
    )
    incident = IncidentInput(
        incident_id="incident-001",
        title="Latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency increased.",
    )
    evidence = [Evidence(evidence_id="E1", source="trace", summary="Payment span slow.")]
    verifier = VerifierAgent(max_critique_rounds=2)
    context = verifier.build_context(incident, [hypothesis], evidence)

    result = verifier.run(context)

    assert result.status == "completed"
    assert result.critique_rounds_used == 1
    assert [item.hypothesis_id for item in result.results] == ["H1"]


def test_model_critique_is_grounded_by_deterministic_boundary() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="Payment service degraded.",
        evidence=EvidenceTable(supporting_evidence_ids=["E1"]),
        confidence="high",
        status="candidate",
    )
    incident = IncidentInput(
        incident_id="incident-001",
        title="Latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency increased.",
    )
    evidence = [
        Evidence(evidence_id="E1", source="trace", summary="Payment span slow."),
        Evidence(evidence_id="E2", source="metric", summary="Payment latency normal."),
    ]
    verifier = VerifierAgent(max_critique_rounds=2)
    context = verifier.build_context(incident, [hypothesis], evidence)

    result = verifier.review_with_model(
        context,
        "H1",
        lambda request: {
            "hypothesis_id": request["hypothesis"]["hypothesis_id"],
            "evidence": {
                "supporting_evidence_ids": ["E1"],
                "contradicting_evidence_ids": ["E2"],
                "missing_evidence": [],
            },
            "rationale": "The metric evidence conflicts with the trace evidence.",
        },
    )

    assert result.status == "low_confidence"
    assert result.confidence == "low"


def test_model_critique_cannot_cite_unknown_evidence() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="Payment service degraded.",
        evidence=EvidenceTable(supporting_evidence_ids=["E1"]),
        confidence="medium",
        status="candidate",
    )
    incident = IncidentInput(
        incident_id="incident-001",
        title="Latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency increased.",
    )
    evidence = [Evidence(evidence_id="E1", source="trace", summary="Payment span slow.")]
    context = VerifierAgent().build_context(incident, [hypothesis], evidence)

    with pytest.raises(ValueError, match="unknown evidence"):
        VerifierAgent().review_with_model(
            context,
            "H1",
            lambda _: {
                "hypothesis_id": "H1",
                "evidence": {
                    "supporting_evidence_ids": ["E99"],
                    "contradicting_evidence_ids": [],
                    "missing_evidence": [],
                },
                "rationale": "Unsupported claim.",
            },
        )


def test_model_critique_round_limit_is_checked_before_model_call() -> None:
    hypothesis = HypothesisCandidate(
        hypothesis_id="H1",
        statement="Payment service degraded.",
        evidence=EvidenceTable(supporting_evidence_ids=["E1"]),
        confidence="medium",
        status="candidate",
    )
    incident = IncidentInput(
        incident_id="incident-001",
        title="Latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency increased.",
    )
    evidence = [Evidence(evidence_id="E1", source="trace", summary="Payment span slow.")]
    context = VerifierAgent(max_critique_rounds=1).build_context(incident, [hypothesis], evidence)
    calls = 0

    def model(_: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise AssertionError("model must not be called")

    with pytest.raises(ValueError, match="CRITIQUE_ROUND_LIMIT_EXCEEDED"):
        VerifierAgent(max_critique_rounds=1).review_with_model(
            context, "H1", model, critique_round=2
        )
    assert calls == 0
