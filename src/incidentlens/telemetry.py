import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SignalType = Literal["log", "metric", "trace"]


class TelemetryProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    fixture_id: str | None = None
    original_record_id: str | None = None


class TelemetryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    signal_type: SignalType
    service_name: str | None = None
    timestamp: datetime
    normalized_timestamp: datetime
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any]
    provenance: TelemetryProvenance
    is_partial: bool = False
    validation_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def timestamps_are_normalized(self) -> "TelemetryRecord":
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if (
            self.normalized_timestamp.tzinfo is None
            or self.normalized_timestamp.utcoffset() is None
        ):
            raise ValueError("normalized_timestamp must be timezone-aware")
        if self.normalized_timestamp.tzinfo != UTC:
            raise ValueError("normalized_timestamp must use UTC")
        if self.normalized_timestamp != self.timestamp.astimezone(UTC):
            raise ValueError("normalized_timestamp must equal timestamp converted to UTC")
        return self


class IncidentTimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def is_valid_utc_window(self) -> "IncidentTimeWindow":
        for field_name in ("start", "end"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
            if value.tzinfo != UTC:
                raise ValueError(f"{field_name} must use UTC")
        if self.start >= self.end:
            raise ValueError("time window start must be before end")
        return self


class IncidentTimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    description: str = Field(min_length=1)
    affected_services: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def timestamp_is_utc(self) -> "IncidentTimelineEvent":
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timeline timestamp must be timezone-aware")
        if self.timestamp.tzinfo != UTC:
            raise ValueError("timeline timestamp must use UTC")
        return self


class IncidentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    load_profile: dict[str, Any] = Field(default_factory=dict)
    fault_injection: str | None = None
    timeline: list[IncidentTimelineEvent] = Field(default_factory=list)
    expected_evidence_ids: list[str] = Field(default_factory=list)
    time_window: IncidentTimeWindow
    affected_services: list[str] = Field(min_length=1)
    telemetry_record_ids: list[str] = Field(min_length=1)
    distractors: list[str] = Field(default_factory=list)


class HiddenGroundTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_cause: str = Field(min_length=1)
    contributing_factors: list[str] = Field(default_factory=list)
    expected_evidence_ids: list[str] = Field(default_factory=list)


class EvaluatorIncidentFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: IncidentManifest
    telemetry: list[TelemetryRecord]
    hidden_ground_truth: HiddenGroundTruth

    @model_validator(mode="after")
    def manifest_records_exist(self) -> "EvaluatorIncidentFixture":
        record_ids = [record.record_id for record in self.telemetry]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("telemetry record IDs must be unique")
        missing = set(self.manifest.telemetry_record_ids) - set(record_ids)
        if missing:
            raise ValueError(f"manifest references missing telemetry IDs: {sorted(missing)}")
        return self


class AgentIncidentFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: IncidentManifest
    telemetry: list[TelemetryRecord]

    @model_validator(mode="after")
    def manifest_records_exist(self) -> "AgentIncidentFixture":
        record_ids = [record.record_id for record in self.telemetry]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("telemetry record IDs must be unique")
        missing = set(self.manifest.telemetry_record_ids) - set(record_ids)
        if missing:
            raise ValueError(f"manifest references missing telemetry IDs: {sorted(missing)}")
        return self


def load_evaluator_fixture(path: str | Path) -> EvaluatorIncidentFixture:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return EvaluatorIncidentFixture.model_validate(data)


def project_agent_fixture(fixture: EvaluatorIncidentFixture) -> AgentIncidentFixture:
    return AgentIncidentFixture(manifest=fixture.manifest, telemetry=fixture.telemetry)


def load_agent_fixture(path: str | Path) -> AgentIncidentFixture:
    return project_agent_fixture(load_evaluator_fixture(path))


def records_in_window(
    records: list[TelemetryRecord], start: datetime, end: datetime
) -> list[TelemetryRecord]:
    """Return records in a bounded UTC window, or an empty list when none match."""
    window = IncidentTimeWindow(start=start, end=end)
    return sorted(
        (record for record in records if window.start <= record.normalized_timestamp < window.end),
        key=lambda record: (record.normalized_timestamp, record.record_id),
    )


def records_for_trace(records: list[TelemetryRecord], trace_id: str) -> list[TelemetryRecord]:
    """Return records for one trace in deterministic normalized-time order."""
    return sorted(
        (record for record in records if record.trace_id == trace_id),
        key=lambda record: (record.normalized_timestamp, record.record_id),
    )


QueryStatus = Literal["success", "partial", "dependency_error", "invalid_query"]


class TelemetryQueryError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: Literal[
        "timeout",
        "rate_limited",
        "service_unavailable",
        "authorization_failed",
        "bad_request",
        "unknown_dependency_error",
    ]
    message: str = Field(min_length=1)
    retryable: bool


class TelemetryQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    query_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    time_window: IncidentTimeWindow
    status: QueryStatus
    records: list[TelemetryRecord] = Field(default_factory=list)
    truncated: bool = False
    returned_count: int = Field(default=0, ge=0)
    error: TelemetryQueryError | None = None

    @model_validator(mode="after")
    def result_invariants(self) -> "TelemetryQueryResult":
        if self.returned_count != len(self.records):
            raise ValueError("returned_count must equal the number of records")
        if self.status == "success" and self.error is not None:
            raise ValueError("successful results cannot contain an error")
        if self.status == "partial" and not self.truncated:
            raise ValueError("partial results must be marked truncated")
        if self.status in {"dependency_error", "invalid_query"} and self.error is None:
            raise ValueError("failed results require a sanitized error")
        if self.status == "invalid_query" and self.error is not None and self.error.retryable:
            raise ValueError("invalid queries cannot be retryable")
        return self
