import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from incidentlens.telemetry import TelemetryQueryResult
from incidentlens.telemetry_tools import (
    MAX_QUERY_WINDOW,
    MetricsQueryArgs,
    build_metrics_registry,
)
from incidentlens.tools import UnknownToolError

FIXTURE = Path("fixtures/incidents/service_latency.json")


def query_args(**overrides: object) -> MetricsQueryArgs:
    values: dict[str, object] = {
        "incident_id": "service-latency-001",
        "metric_name": "http.server.duration.p95",
        "start_time": datetime(2026, 9, 12, 10, 0, tzinfo=UTC),
        "end_time": datetime(2026, 9, 12, 10, 20, tzinfo=UTC),
        "limit": 10,
    }
    values.update(overrides)
    return MetricsQueryArgs.model_validate(values)


def test_metrics_tool_returns_bounded_metric_records() -> None:
    registry = build_metrics_registry(FIXTURE)

    result = registry.execute("query_metrics", query_args().model_dump())

    assert isinstance(result, TelemetryQueryResult)
    assert result.status == "success"
    assert result.returned_count == 1
    assert result.records[0].record_id == "sl-metric-1"


def test_metrics_tool_returns_successful_empty_result() -> None:
    registry = build_metrics_registry(FIXTURE)

    result = registry.execute(
        "query_metrics",
        query_args(metric_name="does.not.exist").model_dump(),
    )

    assert result.status == "success"
    assert result.records == []
    assert result.error is None


def test_metrics_tool_rejects_other_incident_scope() -> None:
    registry = build_metrics_registry(FIXTURE)

    result = registry.execute(
        "query_metrics",
        query_args(incident_id="other-incident").model_dump(),
    )

    assert result.status == "invalid_query"
    assert result.error is not None
    assert result.error.retryable is False


def test_query_args_rejects_unbounded_limit_and_window() -> None:
    with pytest.raises(ValidationError):
        query_args(limit=MAX_QUERY_WINDOW.seconds)
    with pytest.raises(ValidationError, match="maximum duration"):
        query_args(end_time=datetime(2026, 9, 12, 11, 30, tzinfo=UTC))


def test_query_args_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        query_args(start_time=datetime(2026, 9, 12, 10, 0))  # noqa: DTZ001


def test_metrics_tool_marks_truncated_results(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    duplicate = payload["telemetry"][0].copy()
    duplicate["record_id"] = "sl-metric-2"
    payload["telemetry"].append(duplicate)
    fixture_path = tmp_path / "service_latency.json"
    fixture_path.write_text(json.dumps(payload), encoding="utf-8")
    registry = build_metrics_registry(fixture_path)

    result = registry.execute("query_metrics", query_args(limit=1).model_dump())

    assert result.status == "partial"
    assert result.truncated is True
    assert result.returned_count == 1


def test_query_result_invariants_reject_mismatched_count() -> None:
    with pytest.raises(ValidationError, match="returned_count"):
        TelemetryQueryResult(
            schema_version="1.0",
            query_id="q-1",
            source_name="fixture",
            tool_name="query_metrics",
            time_window={
                "start": "2026-09-12T10:00:00Z",
                "end": "2026-09-12T10:05:00Z",
            },
            status="success",
            returned_count=1,
        )


def test_metrics_registry_is_explicitly_least_privilege() -> None:
    registry = build_metrics_registry(FIXTURE)

    metrics_agent_tools = registry.restrict_to({"query_metrics"})

    assert metrics_agent_tools.tool_names == {"query_metrics"}
    with pytest.raises(UnknownToolError):
        metrics_agent_tools.execute("query_logs", {})
