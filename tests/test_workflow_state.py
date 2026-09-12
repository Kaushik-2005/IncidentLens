import pytest

from incidentlens.workflow_state import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    IncidentGraphState,
    InvalidTransitionError,
    LifecycleStatus,
    record_usage,
    transition,
)


def test_states_created() -> None:
    state = IncidentGraphState(incident_id="incident-001")

    assert state.status == LifecycleStatus.CREATED
    assert state.model_calls == 0
    assert state.tool_calls == 0
    assert state.report is None


def test_all_normal_transitions_are_allowed() -> None:
    state = IncidentGraphState(incident_id="incident-001")

    state = transition(state, LifecycleStatus.TRIAGING)
    state = transition(state, LifecycleStatus.INVESTIGATING)
    state = transition(state, LifecycleStatus.SYNTHESIZING)

    assert state.status == LifecycleStatus.SYNTHESIZING


def test_triage_cannot_be_skipped() -> None:
    state = IncidentGraphState(incident_id="incident-001")

    with pytest.raises(InvalidTransitionError, match="INVALID_TRANSITION"):
        transition(state, LifecycleStatus.INVESTIGATING)


def test_terminal_state_cannot_transition() -> None:
    state = IncidentGraphState(
        incident_id="incident-001",
        status=LifecycleStatus.CANCELLED,
    )

    with pytest.raises(
        InvalidTransitionError,
        match="TERMINAL_STATE_TRANSITION",
    ):
        transition(state, LifecycleStatus.TRIAGING)


def test_failed_requires_error() -> None:
    state = IncidentGraphState(incident_id="incident-001")

    with pytest.raises(InvalidTransitionError, match="error"):
        transition(state, LifecycleStatus.FAILED)


from incidentlens.contracts import Evidence, Hypothesis, InvestigationReport


def valid_report() -> InvestigationReport:
    return InvestigationReport(
        incident_id="incident-001",
        summary="Latency increased.",
        evidence=[Evidence(evidence_id="E1", source="metric", summary="Latency rose.")],
        hypotheses=[
            Hypothesis(
                statement="A dependency became slow.",
                confidence="medium",
                supporting_evidence_ids=["E1"],
            )
        ],
        status="completed",
    )


def test_completed_requires_a_validated_report() -> None:
    state = IncidentGraphState(
        incident_id="incident-001",
        status=LifecycleStatus.SYNTHESIZING,
    )

    with pytest.raises(InvalidTransitionError, match="validated report"):
        transition(state, LifecycleStatus.COMPLETED)


def test_valid_report_allows_completion() -> None:
    state = IncidentGraphState(
        incident_id="incident-001",
        status=LifecycleStatus.SYNTHESIZING,
        report=valid_report(),
    )

    completed = transition(state, LifecycleStatus.COMPLETED)

    assert completed.status == LifecycleStatus.COMPLETED
    assert completed.current_node is None
    assert completed.report is not None


def test_record_usage_increases_counters_and_preserves_identity() -> None:
    state = IncidentGraphState(
        incident_id="incident-001",
        model_calls=1,
        tool_calls=2,
    )

    updated = record_usage(state, model_calls=3, tool_calls=4)

    assert updated.incident_id == "incident-001"
    assert updated.model_calls == 4
    assert updated.tool_calls == 6


def test_record_usage_rejects_negative_increments() -> None:
    state = IncidentGraphState(incident_id="incident-001")

    with pytest.raises(ValueError, match="model_calls"):
        record_usage(state, model_calls=-1)

    with pytest.raises(ValueError, match="tool_calls"):
        record_usage(state, tool_calls=-1)


@pytest.mark.parametrize("active_status", sorted(ACTIVE_STATES, key=lambda item: item.value))
def test_any_active_state_can_be_cancelled(active_status) -> None:
    state = IncidentGraphState(incident_id="incident-001", status=active_status)

    cancelled = transition(state, LifecycleStatus.CANCELLED)

    assert cancelled.status == LifecycleStatus.CANCELLED
    assert cancelled.current_node is None


@pytest.mark.parametrize("terminal_status", sorted(TERMINAL_STATES, key=lambda item: item.value))
def test_every_terminal_state_rejects_transition(terminal_status) -> None:
    state = IncidentGraphState(incident_id="incident-001", status=terminal_status)

    with pytest.raises(InvalidTransitionError, match="TERMINAL_STATE_TRANSITION"):
        transition(state, LifecycleStatus.TRIAGING)
