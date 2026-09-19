import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ActionType = Literal["rollback", "traffic_shift", "feature_flag"]
ApprovalStatus = Literal["approved", "rejected", "expired", "consumed"]
AuditEventType = Literal["proposed", "approved", "rejected", "expired", "executed"]


class ActionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    action_type: ActionType
    target: str = Field(min_length=1)
    arguments: dict[str, Any]
    evidence_refs: list[str] = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    fingerprint: str = Field(min_length=64, max_length=64)


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    action_fingerprint: str = Field(min_length=64, max_length=64)
    approver_id: str = Field(min_length=1)
    expires_at: datetime
    status: ApprovalStatus

    @model_validator(mode="after")
    def expires_at_is_aware(self) -> "Approval":
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")
        return self


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    event_type: AuditEventType
    actor_id: str = Field(min_length=1)
    action_fingerprint: str = Field(min_length=64, max_length=64)
    occurred_at: datetime


class ApprovalValidationError(ValueError):
    def __init__(self, classification: str, message: str) -> None:
        self.classification = classification
        super().__init__(message)


def build_action_plan(
    *,
    action_id: str,
    incident_id: str,
    action_type: ActionType,
    target: str,
    arguments: dict[str, Any],
    evidence_refs: list[str],
    policy_version: str,
) -> ActionPlan:
    fingerprint_payload = {
        "action_type": action_type,
        "arguments": arguments,
        "evidence_refs": sorted(set(evidence_refs)),
        "incident_id": incident_id,
        "policy_version": policy_version,
        "target": target,
    }
    canonical = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ActionPlan(
        action_id=action_id,
        incident_id=incident_id,
        action_type=action_type,
        target=target,
        arguments=arguments,
        evidence_refs=evidence_refs,
        policy_version=policy_version,
        fingerprint=fingerprint,
    )


def validate_approval(
    plan: ActionPlan,
    approval: Approval,
    *,
    authorized_approver_ids: set[str],
    now: datetime,
    consumed_action_ids: set[str] | None = None,
    rejected_fingerprints: set[str] | None = None,
) -> None:
    if approval.status == "rejected" or approval.action_fingerprint in (
        rejected_fingerprints or set()
    ):
        raise ApprovalValidationError("APPROVAL_REJECTED", "This action fingerprint was rejected.")
    if approval.status != "approved":
        raise ApprovalValidationError("APPROVAL_NOT_APPROVED", "Approval is not executable.")
    if approval.action_id != plan.action_id:
        raise ApprovalValidationError("ACTION_ID_MISMATCH", "Approval does not match the action.")
    if approval.action_fingerprint != plan.fingerprint:
        raise ApprovalValidationError(
            "ACTION_FINGERPRINT_MISMATCH", "Approval does not match the action."
        )
    if approval.approver_id not in authorized_approver_ids:
        raise ApprovalValidationError("APPROVER_NOT_AUTHORIZED", "Approver is not authorized.")
    if approval.expires_at.astimezone(UTC) <= now.astimezone(UTC):
        raise ApprovalValidationError("APPROVAL_EXPIRED", "Approval has expired.")
    if plan.action_id in (consumed_action_ids or set()):
        raise ApprovalValidationError(
            "ACTION_ALREADY_CONSUMED", "Action has already been executed."
        )


def consume_approval(
    plan: ActionPlan,
    approval: Approval,
    *,
    authorized_approver_ids: set[str],
    now: datetime,
    consumed_action_ids: set[str] | None = None,
    rejected_fingerprints: set[str] | None = None,
) -> Approval:
    validate_approval(
        plan,
        approval,
        authorized_approver_ids=authorized_approver_ids,
        now=now,
        consumed_action_ids=consumed_action_ids,
        rejected_fingerprints=rejected_fingerprints,
    )
    return approval.model_copy(update={"status": "consumed"})


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: ActionPlan
    approval: Approval | None = None
    audit_events: list[AuditEvent] = Field(default_factory=list)
    execution_status: Literal["awaiting_approval", "executing", "executed", "failed"] = (
        "awaiting_approval"
    )
    execution_error: str | None = None


class ApprovalStore:
    """Durable approval interrupt and at-most-once simulated execution store."""

    def __init__(self, root: str) -> None:
        from pathlib import Path

        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, action_id: str):
        from pathlib import Path

        if not action_id or Path(action_id).name != action_id:
            raise ValueError("action ID must be a single path-safe name")
        return self.root / f"{action_id}.json"

    def request(self, plan: ActionPlan, *, actor_id: str, event_id: str) -> ApprovalRecord:
        path = self._path(plan.action_id)
        if path.exists():
            record = self.load(plan.action_id)
            if record.plan.fingerprint != plan.fingerprint:
                raise ApprovalValidationError(
                    "ACTION_ID_CONFLICT", "Action ID already refers to a different plan."
                )
            return record
        record = ApprovalRecord(
            plan=plan,
            audit_events=[
                AuditEvent(
                    event_id=event_id,
                    incident_id=plan.incident_id,
                    action_id=plan.action_id,
                    event_type="proposed",
                    actor_id=actor_id,
                    action_fingerprint=plan.fingerprint,
                    occurred_at=datetime.now(UTC),
                )
            ],
        )
        self._save(record)
        return record

    def approve(self, action_id: str, approval: Approval, *, event_id: str) -> ApprovalRecord:
        record = self.load(action_id)
        if record.approval is not None and record.approval.status == "rejected":
            raise ApprovalValidationError(
                "APPROVAL_REJECTED", "This action fingerprint was rejected."
            )
        if approval.action_id != record.plan.action_id:
            raise ApprovalValidationError(
                "ACTION_ID_MISMATCH", "Approval does not match the action."
            )
        if approval.action_fingerprint != record.plan.fingerprint:
            raise ApprovalValidationError(
                "ACTION_FINGERPRINT_MISMATCH", "Approval does not match the action."
            )
        record.approval = approval
        record.execution_status = "awaiting_approval"
        record.audit_events.append(
            AuditEvent(
                event_id=event_id,
                incident_id=record.plan.incident_id,
                action_id=record.plan.action_id,
                event_type="approved",
                actor_id=approval.approver_id,
                action_fingerprint=record.plan.fingerprint,
                occurred_at=datetime.now(UTC),
            )
        )
        self._save(record)
        return record

    def reject(
        self, action_id: str, *, approver_id: str, approval_id: str, event_id: str
    ) -> ApprovalRecord:
        record = self.load(action_id)
        record.approval = Approval(
            approval_id=approval_id,
            action_id=record.plan.action_id,
            action_fingerprint=record.plan.fingerprint,
            approver_id=approver_id,
            expires_at=datetime.now(UTC),
            status="rejected",
        )
        record.audit_events.append(
            AuditEvent(
                event_id=event_id,
                incident_id=record.plan.incident_id,
                action_id=record.plan.action_id,
                event_type="rejected",
                actor_id=approver_id,
                action_fingerprint=record.plan.fingerprint,
                occurred_at=datetime.now(UTC),
            )
        )
        self._save(record)
        return record

    def resume(
        self,
        action_id: str,
        *,
        authorized_approver_ids: set[str],
        now: datetime,
        execute: Callable[[ActionPlan], Any],
        event_id: str,
    ) -> str:
        record = self.load(action_id)
        if record.execution_status == "executed":
            return "already_executed"
        if record.execution_status in {"executing", "failed"}:
            return "indeterminate"
        if record.approval is None:
            return "awaiting_approval"
        validate_approval(
            record.plan,
            record.approval,
            authorized_approver_ids=authorized_approver_ids,
            now=now,
        )
        record.execution_status = "executing"
        self._save(record)
        try:
            execute(record.plan)
        except Exception as exc:
            record.execution_status = "failed"
            record.execution_error = "simulated action execution failed"
            self._save(record)
            raise ApprovalValidationError(
                "ACTION_EXECUTION_FAILED", record.execution_error
            ) from exc
        record.execution_status = "executed"
        record.audit_events.append(
            AuditEvent(
                event_id=event_id,
                incident_id=record.plan.incident_id,
                action_id=record.plan.action_id,
                event_type="executed",
                actor_id=record.approval.approver_id,
                action_fingerprint=record.plan.fingerprint,
                occurred_at=datetime.now(UTC),
            )
        )
        self._save(record)
        return "executed"

    def load(self, action_id: str) -> ApprovalRecord:
        import json

        path = self._path(action_id)
        try:
            return ApprovalRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ApprovalValidationError(
                "APPROVAL_RECORD_UNAVAILABLE", "Approval record is unavailable."
            ) from exc

    def _save(self, record: ApprovalRecord) -> None:
        import json

        path = self._path(record.plan.action_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
