from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from incidentlens.contracts import Evidence, IncidentInput


class SpecialistRole(StrEnum):
    LOGS = "logs_agent"
    METRICS = "metrics_agent"
    TRACES = "traces_agent"


class FindingKind(StrEnum):
    OBSERVATION = "observation"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"


class SpecialistRoleContract(BaseModel):
    role: SpecialistRole
    contract_version: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    allowed_tools: frozenset[str] = Field(min_length=1)
    allowed_signal_types: frozenset[Literal["log", "metric", "trace"]] = Field(min_length=1)
    output_schema: str = "SpecialistFinding"
    max_model_calls: int = Field(ge=1)
    max_tool_calls: int = Field(ge=1)
    stopping_rule: str = Field(min_length=1)


class SpecialistContext(BaseModel):
    """The isolated input contract for one specialist investigation."""

    incident_id: str = Field(min_length=1)
    affected_services: list[str] = Field(min_length=1)
    start_time: str = Field(min_length=1)
    end_time: str | None = None
    neutral_summary: str = Field(min_length=1)
    task: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)
    allowed_tools: frozenset[str] = Field(min_length=1)

    model_config = {"extra": "forbid"}


class SpecialistFinding(BaseModel):
    role: SpecialistRole
    claim_kind: FindingKind
    claim: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]
    open_questions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_ids_are_unique(self) -> "SpecialistFinding":
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence_ids must be unique")
        return self


def role_contracts() -> dict[SpecialistRole, SpecialistRoleContract]:
    return {
        SpecialistRole.LOGS: SpecialistRoleContract(
            role=SpecialistRole.LOGS,
            contract_version="1.0",
            objective="Identify log-recorded errors, timeouts, and changes in log patterns.",
            allowed_tools=frozenset({"search_logs"}),
            allowed_signal_types=frozenset({"log"}),
            max_model_calls=3,
            max_tool_calls=5,
            stopping_rule="Stop after relevant log patterns are covered or the tool budget is exhausted.",
        ),
        SpecialistRole.METRICS: SpecialistRoleContract(
            role=SpecialistRole.METRICS,
            contract_version="1.0",
            objective="Identify metric anomalies, trends, saturation, and missing metric coverage.",
            allowed_tools=frozenset({"query_metrics"}),
            allowed_signal_types=frozenset({"metric"}),
            max_model_calls=3,
            max_tool_calls=5,
            stopping_rule="Stop after the bounded incident window is covered or the tool budget is exhausted.",
        ),
        SpecialistRole.TRACES: SpecialistRoleContract(
            role=SpecialistRole.TRACES,
            contract_version="1.0",
            objective="Localize latency and errors across trace and span relationships.",
            allowed_tools=frozenset({"search_traces", "get_trace"}),
            allowed_signal_types=frozenset({"trace"}),
            max_model_calls=3,
            max_tool_calls=5,
            stopping_rule="Stop after affected request paths are localized or the tool budget is exhausted.",
        ),
    }


def build_specialist_context(
    incident: IncidentInput,
    role: SpecialistRole,
    evidence: list[Evidence],
) -> SpecialistContext:
    contract = role_contracts()[role]
    visible_evidence = [item for item in evidence if item.source in contract.allowed_signal_types]
    return SpecialistContext(
        incident_id=incident.incident_id,
        affected_services=[incident.affected_service],
        start_time=incident.start_time,
        end_time=incident.end_time,
        neutral_summary=incident.summary,
        task=contract.objective,
        evidence=visible_evidence,
        allowed_tools=contract.allowed_tools,
    )


def validate_finding_evidence(
    finding: SpecialistFinding,
    available_evidence_ids: set[str],
) -> SpecialistFinding:
    unknown_ids = set(finding.evidence_ids) - available_evidence_ids
    if unknown_ids:
        raise ValueError(f"finding cites unknown evidence IDs: {sorted(unknown_ids)}")
    return finding
