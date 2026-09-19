from datetime import UTC, datetime, timedelta

import pytest

from incidentlens.approval import (
    Approval,
    ApprovalStore,
    ApprovalValidationError,
    build_action_plan,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def plan():
    return build_action_plan(
        action_id="action-1",
        incident_id="incident-001",
        action_type="rollback",
        target="checkout-api",
        arguments={"version": "v2.4"},
        evidence_refs=["E1", "E3"],
        policy_version="1.0",
    )


def approval(action):
    return Approval(
        approval_id="approval-1",
        action_id=action.action_id,
        action_fingerprint=action.fingerprint,
        approver_id="sre-1",
        expires_at=NOW + timedelta(minutes=10),
        status="approved",
    )


def test_request_persists_awaiting_approval_and_audit(tmp_path):
    store = ApprovalStore(str(tmp_path))
    record = store.request(plan(), actor_id="agent-1", event_id="audit-1")

    restored = store.load("action-1")
    assert record.execution_status == "awaiting_approval"
    assert restored.audit_events[0].event_type == "proposed"


def test_resume_without_approval_pauses(tmp_path):
    store = ApprovalStore(str(tmp_path))
    store.request(plan(), actor_id="agent-1", event_id="audit-1")
    calls = []

    result = store.resume(
        "action-1",
        authorized_approver_ids={"sre-1"},
        now=NOW,
        execute=lambda action: calls.append(action.action_id),
        event_id="audit-2",
    )

    assert result == "awaiting_approval"
    assert calls == []


def test_resume_executes_once_and_duplicate_resume_does_not_call_again(tmp_path):
    store = ApprovalStore(str(tmp_path))
    action = plan()
    store.request(action, actor_id="agent-1", event_id="audit-1")
    store.approve(action.action_id, approval(action), event_id="audit-2")
    calls = []

    execute = lambda value: calls.append(value.action_id)
    assert (
        store.resume(
            "action-1",
            authorized_approver_ids={"sre-1"},
            now=NOW,
            execute=execute,
            event_id="audit-3",
        )
        == "executed"
    )
    assert (
        store.resume(
            "action-1",
            authorized_approver_ids={"sre-1"},
            now=NOW,
            execute=execute,
            event_id="audit-4",
        )
        == "already_executed"
    )
    assert calls == ["action-1"]
    assert store.load("action-1").audit_events[-1].event_type == "executed"


def test_resume_after_crash_marker_is_indeterminate_and_does_not_repeat(tmp_path):
    store = ApprovalStore(str(tmp_path))
    action = plan()
    store.request(action, actor_id="agent-1", event_id="audit-1")
    store.approve(action.action_id, approval(action), event_id="audit-2")
    record = store.load("action-1")
    record.execution_status = "executing"
    store._save(record)
    calls = []

    result = store.resume(
        "action-1",
        authorized_approver_ids={"sre-1"},
        now=NOW,
        execute=lambda value: calls.append(value.action_id),
        event_id="audit-3",
    )

    assert result == "indeterminate"
    assert calls == []


def test_rejection_cannot_be_resumed(tmp_path):
    store = ApprovalStore(str(tmp_path))
    action = plan()
    store.request(action, actor_id="agent-1", event_id="audit-1")
    store.reject(
        action.action_id, approver_id="sre-1", approval_id="approval-1", event_id="audit-2"
    )

    with pytest.raises(ApprovalValidationError, match="rejected"):
        store.resume(
            "action-1",
            authorized_approver_ids={"sre-1"},
            now=NOW,
            execute=lambda _: None,
            event_id="audit-3",
        )


def test_audit_event_does_not_store_raw_execution_exception(tmp_path):
    store = ApprovalStore(str(tmp_path))
    action = plan()
    store.request(action, actor_id="agent-1", event_id="audit-1")
    store.approve(action.action_id, approval(action), event_id="audit-2")

    with pytest.raises(ApprovalValidationError, match="execution failed"):
        store.resume(
            "action-1",
            authorized_approver_ids={"sre-1"},
            now=NOW,
            execute=lambda _: (_ for _ in ()).throw(RuntimeError("secret provider detail")),
            event_id="audit-3",
        )

    assert "secret provider detail" not in store.load("action-1").model_dump_json()


def test_rejected_action_cannot_be_approved_later(tmp_path):
    store = ApprovalStore(str(tmp_path))
    action = plan()
    store.request(action, actor_id="agent-1", event_id="audit-1")
    store.reject(
        action.action_id, approver_id="sre-1", approval_id="approval-1", event_id="audit-2"
    )

    with pytest.raises(ApprovalValidationError, match="rejected"):
        store.approve(action.action_id, approval(action), event_id="audit-3")


def test_failed_execution_is_not_retried_on_resume(tmp_path):
    store = ApprovalStore(str(tmp_path))
    action = plan()
    store.request(action, actor_id="agent-1", event_id="audit-1")
    store.approve(action.action_id, approval(action), event_id="audit-2")
    calls = []

    with pytest.raises(ApprovalValidationError, match="execution failed"):
        store.resume(
            action.action_id,
            authorized_approver_ids={"sre-1"},
            now=NOW,
            execute=lambda value: (
                calls.append(value.action_id),
                (_ for _ in ()).throw(RuntimeError("failure")),
            )[1],
            event_id="audit-3",
        )

    assert (
        store.resume(
            action.action_id,
            authorized_approver_ids={"sre-1"},
            now=NOW,
            execute=lambda value: calls.append(value.action_id),
            event_id="audit-4",
        )
        == "indeterminate"
    )
    assert calls == ["action-1"]
