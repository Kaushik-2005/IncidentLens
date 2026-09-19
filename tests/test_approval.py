from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from incidentlens.approval import (
    Approval,
    ApprovalValidationError,
    build_action_plan,
    consume_approval,
    validate_approval,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def make_plan(**overrides):
    values = {
        "action_id": "action-1",
        "incident_id": "incident-001",
        "action_type": "rollback",
        "target": "checkout-api",
        "arguments": {"version": "v2.4"},
        "evidence_refs": ["E1", "E3"],
        "policy_version": "1.0",
    }
    values.update(overrides)
    return build_action_plan(**values)


def make_approval(plan, **overrides):
    values = {
        "approval_id": "approval-1",
        "action_id": plan.action_id,
        "action_fingerprint": plan.fingerprint,
        "approver_id": "sre-1",
        "expires_at": NOW + timedelta(minutes=10),
        "status": "approved",
    }
    values.update(overrides)
    return Approval(**values)


def test_fingerprint_changes_when_action_or_evidence_changes() -> None:
    plan = make_plan()
    assert make_plan(arguments={"version": "v2.5"}).fingerprint != plan.fingerprint
    assert make_plan(evidence_refs=["E1", "E2"]).fingerprint != plan.fingerprint


def test_evidence_order_does_not_change_fingerprint() -> None:
    assert make_plan(evidence_refs=["E3", "E1"]).fingerprint == make_plan().fingerprint


def test_valid_approval_can_be_consumed_once() -> None:
    plan = make_plan()
    approval = make_approval(plan)

    consumed = consume_approval(
        plan,
        approval,
        authorized_approver_ids={"sre-1"},
        now=NOW,
    )

    assert consumed.status == "consumed"


def test_rejected_fingerprint_cannot_be_reused() -> None:
    plan = make_plan()
    approval = make_approval(plan, status="rejected")

    with pytest.raises(ApprovalValidationError, match="rejected") as error:
        validate_approval(
            plan,
            approval,
            authorized_approver_ids={"sre-1"},
            now=NOW,
        )

    assert error.value.classification == "APPROVAL_REJECTED"


def test_changed_evidence_requires_new_approval() -> None:
    original = make_plan()
    changed = make_plan(evidence_refs=["E1", "E2"])
    approval = make_approval(original)

    with pytest.raises(ApprovalValidationError) as error:
        validate_approval(
            changed,
            approval,
            authorized_approver_ids={"sre-1"},
            now=NOW,
        )

    assert error.value.classification == "ACTION_FINGERPRINT_MISMATCH"


def test_expired_approval_is_rejected() -> None:
    plan = make_plan()
    approval = make_approval(plan, expires_at=NOW)

    with pytest.raises(ApprovalValidationError) as error:
        validate_approval(
            plan,
            approval,
            authorized_approver_ids={"sre-1"},
            now=NOW,
        )

    assert error.value.classification == "APPROVAL_EXPIRED"


def test_unauthorized_approver_is_rejected() -> None:
    plan = make_plan()
    approval = make_approval(plan, approver_id="viewer-1")

    with pytest.raises(ApprovalValidationError) as error:
        validate_approval(
            plan,
            approval,
            authorized_approver_ids={"sre-1"},
            now=NOW,
        )

    assert error.value.classification == "APPROVER_NOT_AUTHORIZED"


def test_duplicate_execution_is_rejected() -> None:
    plan = make_plan()
    approval = make_approval(plan)

    with pytest.raises(ApprovalValidationError) as error:
        validate_approval(
            plan,
            approval,
            authorized_approver_ids={"sre-1"},
            now=NOW,
            consumed_action_ids={plan.action_id},
        )

    assert error.value.classification == "ACTION_ALREADY_CONSUMED"


def test_approval_expiry_must_be_timezone_aware() -> None:
    plan = make_plan()
    with pytest.raises(ValidationError, match="timezone-aware"):
        make_approval(plan, expires_at=datetime(2026, 9, 19, 12, 0))  # noqa: DTZ001
