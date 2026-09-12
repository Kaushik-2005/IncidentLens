import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from incidentlens.telemetry import (
    AgentIncidentFixture,
    TelemetryQueryError,
    TelemetryQueryResult,
    load_agent_fixture,
    records_in_window,
)
from incidentlens.tools import ToolRegistry, ToolSpec

MAX_RESULT_LIMIT = 500
MAX_QUERY_WINDOW = timedelta(hours=1)


class MetricsQueryArgs(BaseModel):
    incident_id: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    start_time: datetime
    end_time: datetime
    limit: int = Field(ge=1, le=MAX_RESULT_LIMIT)

    @model_validator(mode="after")
    def validate_window(self) -> "MetricsQueryArgs":
        for field_name in ("start_time", "end_time"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
            if value.tzinfo != UTC:
                raise ValueError(f"{field_name} must use UTC")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.end_time - self.start_time > MAX_QUERY_WINDOW:
            raise ValueError("query window exceeds maximum duration")
        return self


class MetricsFixtureStore:
    def __init__(self, fixture: AgentIncidentFixture) -> None:
        self._fixture = fixture

    def query_metrics(self, args: MetricsQueryArgs) -> TelemetryQueryResult:
        query_id = _query_id(args)
        if args.incident_id != self._fixture.manifest.incident_id:
            return _invalid_query(query_id, args, "incident is outside the active fixture scope")

        records = [
            record
            for record in records_in_window(self._fixture.telemetry, args.start_time, args.end_time)
            if record.signal_type == "metric"
            and record.attributes.get("metric_name") == args.metric_name
        ]
        truncated = len(records) > args.limit
        records = records[: args.limit]
        return TelemetryQueryResult(
            schema_version="1.0",
            query_id=query_id,
            source_name="incident_fixture",
            tool_name="query_metrics",
            time_window={"start": args.start_time, "end": args.end_time},
            status="partial" if truncated else "success",
            records=records,
            truncated=truncated,
            returned_count=len(records),
        )


def build_metrics_registry(fixture_path: Path) -> ToolRegistry:
    fixture = load_agent_fixture(fixture_path)
    store = MetricsFixtureStore(fixture)
    return ToolRegistry(
        [
            ToolSpec(
                name="query_metrics",
                description="Query bounded metric records for the active synthetic incident.",
                args_schema=MetricsQueryArgs,
                result_schema=TelemetryQueryResult,
                handler=store.query_metrics,
            )
        ]
    )


def _query_id(args: MetricsQueryArgs) -> str:
    serialized = json.dumps(args.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _invalid_query(query_id: str, args: MetricsQueryArgs, message: str) -> TelemetryQueryResult:
    return TelemetryQueryResult(
        schema_version="1.0",
        query_id=query_id,
        source_name="incident_fixture",
        tool_name="query_metrics",
        time_window={"start": args.start_time, "end": args.end_time},
        status="invalid_query",
        error=TelemetryQueryError(classification="bad_request", message=message, retryable=False),
    )
