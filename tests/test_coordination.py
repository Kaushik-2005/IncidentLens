from datetime import UTC, datetime

from incidentlens.coordination import InvestigationTask
from incidentlens.specialists import SpecialistRole


def test_task_envelope_is_typed_and_scoped() -> None:
    task = InvestigationTask(
        task_id="task-metrics-001",
        incident_id="incident-001",
        specialist_role=SpecialistRole.METRICS,
        objective="Indentify metric anomalies.",
        time_window={
            "start": datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
            "end": datetime(2026, 9, 15, 10, 20, tzinfo=UTC),
        },
        affected_services=["checkout-api"],
        allowed_tools=frozenset({"query_metrics"}),
        allowed_signal_types=frozenset({"metric"}),
        evidence_refs=["M1", "M2"],
        max_model_calls=3,
        max_tool_calls=5,
    )

    assert task.message_type == "investigation_task"
    assert task.specialist_role == SpecialistRole.METRICS
    assert task.allowed_tools == {"query_metrics"}


from incidentlens.coordination import SpecialistFindingMessage
from incidentlens.specialists import FindingKind


def test_finding_message_is_typed_and_traceable() -> None:
    finding = SpecialistFindingMessage(
        task_id="task-metrics-001",
        finding_id="finding-metrics-001",
        incident_id="incident-001",
        agent_id="metrics-agent-1",
        specialist_role=SpecialistRole.METRICS,
        claim_kind=FindingKind.OBSERVATION,
        claim="Latency increased.",
        evidence_ids=["M1"],
        confidence="medium",
    )

    assert finding.message_type == "specialist_finding"
    assert finding.task_id == "task-metrics-001"
    assert finding.agent_id == "metrics-agent-1"


import pytest
from pydantic import ValidationError

from incidentlens.coordination import (
    FindingInbox,
    validate_finding_for_task,
)


def make_task() -> InvestigationTask:
    return InvestigationTask(
        task_id="task-metrics-001",
        incident_id="incident-001",
        specialist_role=SpecialistRole.METRICS,
        objective="Identify metric anomalies.",
        time_window={
            "start": datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
            "end": datetime(2026, 9, 15, 10, 20, tzinfo=UTC),
        },
        affected_services=["checkout-api"],
        allowed_tools={"query_metrics"},
        allowed_signal_types={"metric"},
        evidence_refs=["M1"],
        max_model_calls=3,
        max_tool_calls=5,
    )


def make_finding() -> SpecialistFindingMessage:
    return SpecialistFindingMessage(
        task_id="task-metrics-001",
        finding_id="finding-metrics-001",
        incident_id="incident-001",
        agent_id="metrics-agent-1",
        specialist_role=SpecialistRole.METRICS,
        claim_kind=FindingKind.OBSERVATION,
        claim="Latency increased.",
        evidence_ids=["M1"],
        confidence="medium",
    )


def test_finding_must_match_task_scope() -> None:
    task = make_task()
    finding = make_finding()

    assert validate_finding_for_task(task, finding) == finding


def test_finding_with_wrong_role_is_rejected() -> None:
    finding = make_finding().model_copy(update={"specialist_role": SpecialistRole.LOGS})

    with pytest.raises(ValueError, match="specialist_role"):
        validate_finding_for_task(make_task(), finding)


def test_finding_outside_evidence_scope_is_rejected() -> None:
    finding = make_finding().model_copy(update={"evidence_ids": ["M2"]})

    with pytest.raises(ValueError, match="outside task scope"):
        validate_finding_for_task(make_task(), finding)


def test_inbox_accepts_exact_retry_only_once() -> None:
    inbox = FindingInbox([make_task()])
    finding = make_finding()

    assert inbox.add(finding) is True
    assert inbox.add(finding) is False
    assert inbox.findings == (finding,)


def test_inbox_rejects_conflicting_duplicate_and_unknown_task() -> None:
    inbox = FindingInbox([make_task()])
    finding = make_finding()
    conflicting = finding.model_copy(update={"claim": "Latency was normal."})
    unknown_task = finding.model_copy(update={"task_id": "stale-task"})

    with pytest.raises(ValueError, match="conflicting duplicate"):
        inbox.add(finding)
        inbox.add(conflicting)
    with pytest.raises(ValueError, match="unknown task_id"):
        inbox.add(unknown_task)


def test_task_contract_rejects_unsupported_version_and_extra_fields() -> None:
    task = make_task()

    with pytest.raises(ValidationError):
        InvestigationTask.model_validate(task.model_dump() | {"schema_version": "2.0"})
    with pytest.raises(ValidationError):
        InvestigationTask.model_validate(task.model_dump() | {"peer_conclusion": "database"})


from incidentlens.coordination import (
    CoordinationPattern,
    InvestigationCoordinator,
    build_investigation_tasks,
    handoff_pattern,
    pattern_matrix,
    router_pattern,
    supervisor_workers_pattern,
)
from incidentlens.telemetry import IncidentTimeWindow


def test_coordinator_builds_one_scoped_task_per_specialist() -> None:
    tasks = build_investigation_tasks(
        incident_id="incident-001",
        time_window=IncidentTimeWindow(
            start=datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
            end=datetime(2026, 9, 15, 10, 20, tzinfo=UTC),
        ),
        affected_services=["checkout-api"],
        evidence_by_signal={"log": ["L1"], "metric": ["M1"], "trace": ["T1"]},
    )

    assert {task.specialist_role for task in tasks} == set(SpecialistRole)
    assert {task.task_id for task in tasks} == {
        "task-logs_agent-incident-001",
        "task-metrics_agent-incident-001",
        "task-traces_agent-incident-001",
    }
    assert next(
        task for task in tasks if task.specialist_role == SpecialistRole.METRICS
    ).evidence_refs == ["M1"]


def test_coordinator_accepts_only_validated_findings() -> None:
    coordinator = InvestigationCoordinator([make_task()])

    assert coordinator.accept_finding(make_finding()) is True
    assert coordinator.accept_finding(make_finding()) is False
    assert len(coordinator.inbox.findings) == 1


def test_pattern_labs_have_distinct_execution_shapes() -> None:
    tasks = [
        make_task(),
        make_task().model_copy(
            update={"task_id": "task-logs-001", "specialist_role": SpecialistRole.LOGS}
        ),
    ]

    assert router_pattern(tasks, SpecialistRole.METRICS) == [tasks[0]]
    assert handoff_pattern(tasks) == [task.task_id for task in tasks]
    assert supervisor_workers_pattern(tasks) == tasks

    assessments = pattern_matrix()
    selected = [item.pattern for item in assessments if item.selected_for_incidentlens]
    assert selected == [CoordinationPattern.SUPERVISOR_WORKERS]
