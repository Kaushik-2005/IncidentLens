import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from incidentlens.telemetry import (
    AgentIncidentFixture,
    EvaluatorIncidentFixture,
    TelemetryQueryError,
    TelemetryRecord,
    build_incident_error,
    load_agent_fixture,
    load_evaluator_fixture,
    project_agent_fixture,
    records_for_trace,
    records_in_window,
)


def test_telemetry_timeout_maps_to_shared_dependency_error() -> None:
    error = TelemetryQueryError(
        classification="timeout",
        message="Metric evidence could not be retrieved within the allowed time.",
        retryable=True,
    )

    shared = build_incident_error(
        error,
        component="metrics_backend",
        correlation_id="telemetry-timeout-1",
        attempt_count=2,
    )

    assert shared.classification == "dependency_timeout"
    assert shared.retryable is True
    assert shared.component == "metrics_backend"
    assert shared.attempt_count == 2


def test_telemetry_unknown_dependency_error_is_sanitized_and_terminal() -> None:
    error = TelemetryQueryError(
        classification="unknown_dependency_error",
        message="The telemetry backend encountered an internal error.",
        retryable=False,
    )

    shared = build_incident_error(
        error,
        component="metrics_backend",
        correlation_id="telemetry-error-1",
    )

    assert shared.classification == "service_unavailable"
    assert shared.retryable is False
    assert "connection" not in shared.model_dump_json().lower()


def fixture_payload() -> dict:
    return {
        "manifest": {
            "schema_version": "1.0",
            "incident_id": "incident-001",
            "title": "Checkout latency",
            "time_window": {
                "start": "2026-09-10T10:00:00Z",
                "end": "2026-09-10T10:15:00Z",
            },
            "affected_services": ["checkout-api"],
            "telemetry_record_ids": ["record-1"],
        },
        "telemetry": [
            {
                "schema_version": "1.0",
                "record_id": "record-1",
                "signal_type": "metric",
                "service_name": "checkout-api",
                "timestamp": "2026-09-10T10:05:00+05:30",
                "normalized_timestamp": "2026-09-10T04:35:00Z",
                "attributes": {},
                "payload": {"name": "latency", "value": 2100, "unit": "ms"},
                "provenance": {"source_type": "fixture", "source_name": "test"},
            }
        ],
        "hidden_ground_truth": {
            "root_cause": "SECRET_GROUND_TRUTH_SENTINEL",
        },
    }


def test_agent_loader_excludes_ground_truth(tmp_path: Path) -> None:
    path = tmp_path / "incident.json"
    path.write_text(json.dumps(fixture_payload()), encoding="utf-8")

    agent_fixture = load_agent_fixture(path)

    assert isinstance(agent_fixture, AgentIncidentFixture)
    serialized = json.dumps(agent_fixture.model_dump(mode="json"))
    assert "hidden_ground_truth" not in serialized
    assert "SECRET_GROUND_TRUTH_SENTINEL" not in serialized


def test_evaluator_loader_retains_ground_truth_for_grading(tmp_path: Path) -> None:
    path = tmp_path / "incident.json"
    path.write_text(json.dumps(fixture_payload()), encoding="utf-8")

    fixture = load_evaluator_fixture(path)

    assert isinstance(fixture, EvaluatorIncidentFixture)
    assert fixture.hidden_ground_truth.root_cause == "SECRET_GROUND_TRUTH_SENTINEL"


def test_naive_timestamp_is_rejected() -> None:
    payload = fixture_payload()["telemetry"][0]
    payload["timestamp"] = "2026-09-10T10:05:00"

    with pytest.raises(ValidationError, match="timezone-aware"):
        from incidentlens.telemetry import TelemetryRecord

        TelemetryRecord.model_validate(payload)


def test_mismatched_normalized_timestamp_is_rejected() -> None:
    payload = fixture_payload()["telemetry"][0]
    payload["normalized_timestamp"] = "2026-09-10T10:05:00Z"

    with pytest.raises(ValidationError, match="must equal"):
        from incidentlens.telemetry import TelemetryRecord

        TelemetryRecord.model_validate(payload)


def test_invalid_time_window_is_rejected() -> None:
    payload = fixture_payload()
    payload["manifest"]["time_window"]["end"] = "2026-09-10T09:59:00Z"

    with pytest.raises(ValidationError, match="before"):
        EvaluatorIncidentFixture.model_validate(payload)


def test_timezone_conversion_is_expected() -> None:
    original = datetime.fromisoformat("2026-09-10T10:05:00+05:30")
    assert original.astimezone(UTC).isoformat() == "2026-09-10T04:35:00+00:00"


@pytest.mark.parametrize(
    "fixture_path",
    [
        Path("fixtures/incidents/payment_failure.json"),
        Path("fixtures/incidents/resource_exhaustion.json"),
        Path("fixtures/incidents/service_latency.json"),
    ],
)
def test_recorded_fixtures_validate(fixture_path: Path) -> None:
    fixture = load_evaluator_fixture(fixture_path)

    assert fixture.manifest.incident_id
    assert fixture.telemetry
    assert fixture.hidden_ground_truth.root_cause


def test_missing_signal_is_allowed_when_manifest_is_explicit() -> None:
    fixture = project_agent_fixture(EvaluatorIncidentFixture.model_validate(fixture_payload()))

    assert {record.signal_type for record in fixture.telemetry} == {"metric"}
    assert len(fixture.telemetry) == 1


def test_partial_record_preserves_warning() -> None:
    fixture = load_agent_fixture(Path("fixtures/incidents/resource_exhaustion.json"))
    partial = next(record for record in fixture.telemetry if record.is_partial)

    assert partial.validation_warnings == ["host field was absent"]


def test_records_for_trace_sorts_out_of_order_input() -> None:
    fixture = load_agent_fixture(Path("fixtures/incidents/payment_failure.json"))
    trace_records = [record for record in fixture.telemetry if record.trace_id == "pf-trace-a"]

    ordered = records_for_trace(list(reversed(trace_records)), "pf-trace-a")

    assert [record.record_id for record in ordered] == ["pf-trace-1", "pf-log-1"]


def test_manifest_missing_record_is_rejected() -> None:
    payload = fixture_payload()
    payload["manifest"]["telemetry_record_ids"] = ["missing-record"]

    with pytest.raises(ValidationError, match="missing telemetry IDs"):
        EvaluatorIncidentFixture.model_validate(payload)


def test_empty_window_returns_no_records() -> None:
    fixture = load_agent_fixture(Path("fixtures/incidents/service_latency.json"))

    records = records_in_window(
        fixture.telemetry,
        datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
        datetime(2026, 9, 12, 12, 5, tzinfo=UTC),
    )

    assert records == []


def test_trace_and_log_correlation_preserves_shared_trace_id() -> None:
    fixture = load_agent_fixture(Path("fixtures/incidents/service_latency.json"))

    correlated = records_for_trace(fixture.telemetry, "sl-trace-a")

    assert {record.signal_type for record in correlated} == {"log", "trace"}
    assert all(record.trace_id == "sl-trace-a" for record in correlated)


def test_extra_telemetry_fields_are_rejected() -> None:
    payload = fixture_payload()["telemetry"][0]
    payload["unexpected"] = "not allowed"

    with pytest.raises(ValidationError, match="extra"):
        TelemetryRecord.model_validate(payload)
