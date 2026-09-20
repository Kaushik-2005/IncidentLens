from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, model_validator


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IncidentInput(BaseModel):
    incident_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    affected_service: str = Field(min_length=1)
    start_time: str = Field(min_length=1)
    end_time: str | None = None
    summary: str = Field(min_length=1)


class Evidence(BaseModel):
    evidence_id: str = Field(min_length=1)
    source: Literal["log", "metric", "trace", "change", "runbook", "fixture"]
    summary: str = Field(min_length=1)


class Hypothesis(BaseModel):
    statement: str = Field(min_length=1)
    confidence: Confidence
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class InvestigationReport(BaseModel):
    incident_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(min_length=1)
    status: Literal["completed", "inconclusive", "failed"]

    @model_validator(mode="after")
    def evidence_ids_must_be_known(self) -> "InvestigationReport":
        known_ids = {item.evidence_id for item in self.evidence}
        for hypothesis in self.hypotheses:
            cited_ids = set(
                hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids
            )
            unknown_ids = cited_ids - known_ids
            if unknown_ids:
                raise ValueError(f"hypothesis cites unknown evidence IDs: {sorted(unknown_ids)}")
        return self


def validate_report_acceptance(report: InvestigationReport) -> InvestigationReport:
    """Downgrade a report that explicitly admits an unresolved evidence obligation."""
    if report.status != "completed":
        return report
    missing = [
        hypothesis.statement
        for hypothesis in report.hypotheses
        if hypothesis.missing_evidence or not hypothesis.supporting_evidence_ids
    ]
    if not missing:
        return report
    return report.model_copy(
        update={
            "status": "inconclusive",
            "summary": (
                "The report contains unresolved evidence requirements and hypotheses without "
                "sufficient supporting evidence; "
                "causal conclusions were not promoted. "
                f"{report.summary}"
            ),
        }
    )


class ToolCall(BaseModel):
    name: str = Field(min_length=1)
    arguments: dict[str, Any]
    call_id: str | None = Field(default=None, min_length=1)


class ToolObservation(BaseModel):
    tool_call: ToolCall
    result: dict[str, Any]


class ModelToolRequest(BaseModel):
    kind: Literal["tool_request"] = "tool_request"
    tool_call: ToolCall


class ModelFinalReport(BaseModel):
    kind: Literal["final_report"] = "final_report"
    report: InvestigationReport


ModelResponse = ModelToolRequest | ModelFinalReport
ModelResponseAdapter = TypeAdapter(ModelResponse)
