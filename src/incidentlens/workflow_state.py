from enum import StrEnum

from pydantic import BaseModel, Field

from incidentlens.contracts import InvestigationReport


class LifecycleStatus(StrEnum):
    CREATED = "created"
    TRIAGING = "triaging"
    INVESTIGATING = "investigating"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IncidentGraphState(BaseModel):
    incident_id: str = Field(min_length=1)
    status: LifecycleStatus = LifecycleStatus.CREATED
    current_node: str | None = None
    cancel_requested: bool = False

    evidence_references: list[str] = Field(default_factory=list)
    report: InvestigationReport | None = None

    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)

    error: str | None = None


class InvalidTransitionError(ValueError):
    """Raised when a lifecycle transition is not permitted."""


NORMAL_TRANSITIONS: dict[LifecycleStatus, LifecycleStatus] = {
    LifecycleStatus.CREATED: LifecycleStatus.TRIAGING,
    LifecycleStatus.TRIAGING: LifecycleStatus.INVESTIGATING,
    LifecycleStatus.INVESTIGATING: LifecycleStatus.SYNTHESIZING,
    LifecycleStatus.SYNTHESIZING: LifecycleStatus.COMPLETED,
}

ACTIVE_STATES = {
    LifecycleStatus.CREATED,
    LifecycleStatus.TRIAGING,
    LifecycleStatus.INVESTIGATING,
    LifecycleStatus.SYNTHESIZING,
}

TERMINAL_STATES = {
    LifecycleStatus.COMPLETED,
    LifecycleStatus.FAILED,
    LifecycleStatus.CANCELLED,
}


def transition(
    state: IncidentGraphState,
    target: LifecycleStatus,
) -> IncidentGraphState:
    current = state.status

    if current in TERMINAL_STATES:
        raise InvalidTransitionError(f"TERMINAL_STATE_TRANSITION: {current} cannot transition")

    if target == LifecycleStatus.FAILED:
        if not state.error:
            raise InvalidTransitionError("FAILED requires sanitized error information")
        return state.model_copy(
            update={
                "status": LifecycleStatus.FAILED,
                "current_node": None,
            }
        )

    if target == LifecycleStatus.CANCELLED:
        return state.model_copy(
            update={
                "status": LifecycleStatus.CANCELLED,
                "current_node": None,
            }
        )

    if target == LifecycleStatus.COMPLETED and state.report is None:
        raise InvalidTransitionError(
            "COMPLETED requires a validated report",
        )

    if NORMAL_TRANSITIONS.get(current) != target:
        raise InvalidTransitionError(f"INVALID_TRANSITION: {current} -> {target}")

    return state.model_copy(
        update={
            "status": target,
            "current_node": None if target in TERMINAL_STATES else target.value,
        }
    )


def record_usage(
    state: IncidentGraphState,
    *,
    model_calls: int = 0,
    tool_calls: int = 0,
) -> IncidentGraphState:
    """Record additional application-measured usage without reducing counters."""
    if model_calls < 0:
        raise ValueError("model_calls increment cannot be negative")
    if tool_calls < 0:
        raise ValueError("tool_calls increment cannot be negative")

    return state.model_copy(
        update={
            "model_calls": state.model_calls + model_calls,
            "tool_calls": state.tool_calls + tool_calls,
        }
    )
