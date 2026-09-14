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
    records_for_trace,
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


class LogsQueryArgs(BaseModel):
    incident_id: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=200)
    start_time: datetime
    end_time: datetime
    limit: int = Field(ge=1, le=MAX_RESULT_LIMIT)

    @model_validator(mode="after")
    def validate_window(self) -> "LogsQueryArgs":
        _validate_window(self.start_time, self.end_time)
        return self


class TracesQueryArgs(BaseModel):
    incident_id: str = Field(min_length=1)
    trace_id: str | None = Field(default=None, min_length=1)
    service_name: str | None = Field(default=None, min_length=1)
    start_time: datetime
    end_time: datetime
    limit: int = Field(ge=1, le=MAX_RESULT_LIMIT)

    @model_validator(mode="after")
    def validate_window(self) -> "TracesQueryArgs":
        _validate_window(self.start_time, self.end_time)
        if self.trace_id is None and self.service_name is None:
            raise ValueError("trace_id or service_name is required")
        return self


class TraceLookupArgs(BaseModel):
    incident_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)


class TelemetryFixtureStore:
    def __init__(self, fixture: AgentIncidentFixture) -> None:
        self._fixture = fixture

    def search_logs(self, args: LogsQueryArgs) -> TelemetryQueryResult:
        query_id = _query_id_for("search_logs", args)
        if not self._in_scope(args.incident_id):
            return _invalid_result(
                query_id, "search_logs", args, "incident is outside active scope"
            )
        needle = args.query.casefold()
        records = [
            record
            for record in records_in_window(self._fixture.telemetry, args.start_time, args.end_time)
            if record.signal_type == "log"
            and needle in json.dumps(record.payload, sort_keys=True).casefold()
        ]
        return _telemetry_result(query_id, "search_logs", args, records)

    def search_traces(self, args: TracesQueryArgs) -> TelemetryQueryResult:
        query_id = _query_id_for("search_traces", args)
        if not self._in_scope(args.incident_id):
            return _invalid_result(
                query_id, "search_traces", args, "incident is outside active scope"
            )
        records = [
            record
            for record in records_in_window(self._fixture.telemetry, args.start_time, args.end_time)
            if record.signal_type == "trace"
            and (args.trace_id is None or record.trace_id == args.trace_id)
            and (args.service_name is None or record.service_name == args.service_name)
        ]
        return _telemetry_result(query_id, "search_traces", args, records)

    def get_trace(self, args: TraceLookupArgs) -> TelemetryQueryResult:
        query_id = _query_id_for("get_trace", args)
        window = self._fixture.manifest.time_window
        if not self._in_scope(args.incident_id):
            return _invalid_result(
                query_id, "get_trace", args, "incident is outside active scope", window
            )
        records = [
            record
            for record in records_for_trace(self._fixture.telemetry, args.trace_id)
            if record.signal_type == "trace"
        ]
        return TelemetryQueryResult(
            schema_version="1.0",
            query_id=query_id,
            source_name="incident_fixture",
            tool_name="get_trace",
            time_window=window,
            status="success",
            records=records,
            returned_count=len(records),
        )

    def _in_scope(self, incident_id: str) -> bool:
        return incident_id == self._fixture.manifest.incident_id


def build_logs_registry(fixture_path: Path) -> ToolRegistry:
    store = TelemetryFixtureStore(load_agent_fixture(fixture_path))
    return ToolRegistry(
        [
            ToolSpec(
                name="search_logs",
                description="Search bounded log records for the active synthetic incident.",
                args_schema=LogsQueryArgs,
                result_schema=TelemetryQueryResult,
                handler=store.search_logs,
            )
        ]
    )


def build_traces_registry(fixture_path: Path) -> ToolRegistry:
    store = TelemetryFixtureStore(load_agent_fixture(fixture_path))
    return ToolRegistry(
        [
            ToolSpec(
                name="search_traces",
                description="Search bounded trace records by trace or service for the active incident.",
                args_schema=TracesQueryArgs,
                result_schema=TelemetryQueryResult,
                handler=store.search_traces,
            ),
            ToolSpec(
                name="get_trace",
                description="Retrieve trace spans by trace ID within the active incident.",
                args_schema=TraceLookupArgs,
                result_schema=TelemetryQueryResult,
                handler=store.get_trace,
            ),
        ]
    )


def _validate_window(start_time: datetime, end_time: datetime) -> None:
    for name, value in (("start_time", start_time), ("end_time", end_time)):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")
        if value.tzinfo != UTC:
            raise ValueError(f"{name} must use UTC")
    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")
    if end_time - start_time > MAX_QUERY_WINDOW:
        raise ValueError("query window exceeds maximum duration")


def _query_id_for(tool_name: str, args: BaseModel) -> str:
    serialized = json.dumps(
        {"tool": tool_name, "args": args.model_dump(mode="json")}, sort_keys=True
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _telemetry_result(
    query_id: str, tool_name: str, args: BaseModel, records: list
) -> TelemetryQueryResult:
    limit = args.limit
    truncated = len(records) > limit
    bounded_records = records[:limit]
    return TelemetryQueryResult(
        schema_version="1.0",
        query_id=query_id,
        source_name="incident_fixture",
        tool_name=tool_name,
        time_window={"start": args.start_time, "end": args.end_time},
        status="partial" if truncated else "success",
        records=bounded_records,
        truncated=truncated,
        returned_count=len(bounded_records),
    )


def _invalid_result(
    query_id: str,
    tool_name: str,
    args: BaseModel,
    message: str,
    window=None,
) -> TelemetryQueryResult:
    if window is None:
        window = {"start": args.start_time, "end": args.end_time}
    return TelemetryQueryResult(
        schema_version="1.0",
        query_id=query_id,
        source_name="incident_fixture",
        tool_name=tool_name,
        time_window=window,
        status="invalid_query",
        error=TelemetryQueryError(classification="bad_request", message=message, retryable=False),
    )
