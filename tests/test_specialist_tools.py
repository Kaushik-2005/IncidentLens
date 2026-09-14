from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from incidentlens.telemetry import TelemetryQueryResult
from incidentlens.telemetry_tools import (
    LogsQueryArgs,
    TraceLookupArgs,
    TracesQueryArgs,
    build_logs_registry,
    build_traces_registry,
)
from incidentlens.tools import UnknownToolError

FIXTURE = Path("fixtures/incidents/service_latency.json")
START = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
END = datetime(2026, 9, 12, 10, 20, tzinfo=UTC)


def test_logs_registry_returns_only_matching_logs() -> None:
    registry = build_logs_registry(FIXTURE)

    result = registry.execute(
        "search_logs",
        LogsQueryArgs(
            incident_id="service-latency-001",
            query="timed out",
            start_time=START,
            end_time=END,
            limit=10,
        ).model_dump(),
    )

    assert isinstance(result, TelemetryQueryResult)
    assert [record.record_id for record in result.records] == ["sl-log-1"]
    assert all(record.signal_type == "log" for record in result.records)


def test_traces_registry_searches_and_retrieves_by_trace_id() -> None:
    registry = build_traces_registry(FIXTURE)
    search_args = TracesQueryArgs(
        incident_id="service-latency-001",
        trace_id="sl-trace-a",
        start_time=START,
        end_time=END,
        limit=10,
    )

    search_result = registry.execute("search_traces", search_args.model_dump())
    trace_result = registry.execute(
        "get_trace",
        TraceLookupArgs(
            incident_id="service-latency-001",
            trace_id="sl-trace-a",
        ).model_dump(),
    )

    assert [record.record_id for record in search_result.records] == ["sl-trace-1"]
    assert [record.record_id for record in trace_result.records] == ["sl-trace-1"]


def test_specialist_tools_reject_cross_incident_requests() -> None:
    registry = build_logs_registry(FIXTURE)
    result = registry.execute(
        "search_logs",
        LogsQueryArgs(
            incident_id="other-incident",
            query="timeout",
            start_time=START,
            end_time=END,
            limit=10,
        ).model_dump(),
    )

    assert result.status == "invalid_query"
    assert result.error is not None
    assert result.error.retryable is False


def test_trace_search_requires_a_narrow_filter() -> None:
    with pytest.raises(ValidationError, match="trace_id or service_name"):
        TracesQueryArgs(
            incident_id="service-latency-001",
            start_time=START,
            end_time=END,
            limit=10,
        )


def test_trace_registry_has_no_log_capability() -> None:
    registry = build_traces_registry(FIXTURE)

    with pytest.raises(UnknownToolError):
        registry.execute("search_logs", {})


def test_each_runtime_registry_exposes_only_its_domain_tools() -> None:
    logs = build_logs_registry(FIXTURE)
    traces = build_traces_registry(FIXTURE)

    assert logs.tool_names == {"search_logs"}
    assert traces.tool_names == {"search_traces", "get_trace"}

    with pytest.raises(UnknownToolError):
        logs.execute("query_metrics", {})
    with pytest.raises(UnknownToolError):
        traces.execute("search_logs", {})
