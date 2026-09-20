from datetime import UTC, datetime
from pathlib import Path

import pytest

from incidentlens.change_tools import ChangeQueryArgs, build_changes_registry

FIXTURE = Path("fixtures/changes/payment_latency.json")


def query_args(**updates):
    values = {
        "incident_id": "payment-latency-001",
        "service_name": "checkout-api",
        "environment": "production",
        "start_time": datetime(2026, 9, 10, 10, 0, tzinfo=UTC),
        "end_time": datetime(2026, 9, 10, 10, 20, tzinfo=UTC),
        "limit": 20,
    }
    values.update(updates)
    return ChangeQueryArgs(**values)


def test_list_changes_is_bounded_and_scoped() -> None:
    registry = build_changes_registry(FIXTURE, incident_id="payment-latency-001")

    result = registry.execute("list_changes", query_args().model_dump())

    assert result.records[0].change_id == "C1"
    assert result.truncated is False


def test_list_changes_rejects_cross_incident_request() -> None:
    registry = build_changes_registry(FIXTURE, incident_id="payment-latency-001")

    result = registry.execute(
        "list_changes",
        query_args(incident_id="other-incident").model_dump(),
    )

    assert result.status == "invalid_query"
    assert result.records == []
    assert result.error["classification"] == "incident_scope_violation"


def test_change_window_is_bounded() -> None:
    with pytest.raises(ValueError, match="maximum duration"):
        query_args(end_time=datetime(2026, 9, 18, 10, 0, tzinfo=UTC))
