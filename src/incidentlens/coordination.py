from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from incidentlens.specialists import SpecialistRole, role_contracts
from incidentlens.telemetry import IncidentTimeWindow


class InvestigationTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_type: Literal["investigation_task"] = "investigation_task"
    schema_version: Literal["1.0"] = "1.0"

    task_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    specialist_role: SpecialistRole

    objective: str = Field(min_length=1)
    time_window: IncidentTimeWindow
    affected_services: list[str] = Field(min_length=1)

    allowed_tools: frozenset[str] = Field(min_length=1)
    allowed_signal_types: frozenset[Literal["log", "metric", "trace"]] = Field(min_length=1)

    evidence_refs: list[str] = Field(default_factory=list)

    max_model_calls: int = Field(ge=1)
    max_tool_calls: int = Field(ge=1)

    output_contract: Literal["SpecialistFinding"] = "SpecialistFinding"


from incidentlens.specialists import FindingKind


class SpecialistFindingMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_type: Literal["specialist_finding"] = "specialist_finding"
    schema_version: Literal["1.0"] = "1.0"

    task_id: str = Field(min_length=1)
    finding_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    specialist_role: SpecialistRole

    claim_kind: FindingKind
    claim: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]
    open_questions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def validate_finding_for_task(
    task: InvestigationTask,
    finding: SpecialistFindingMessage,
) -> SpecialistFindingMessage:
    """Validate semantic ownership and evidence scope at the coordinator boundary."""
    if finding.task_id != task.task_id:
        raise ValueError("finding task_id does not match task")
    if finding.incident_id != task.incident_id:
        raise ValueError("finding incident_id does not match task")
    if finding.specialist_role != task.specialist_role:
        raise ValueError("finding specialist_role does not match task")

    unknown_evidence = set(finding.evidence_ids) - set(task.evidence_refs)
    if unknown_evidence:
        raise ValueError(f"finding cites evidence outside task scope: {sorted(unknown_evidence)}")
    return finding


class FindingInbox:
    """Store validated findings with idempotent exact-duplicate handling."""

    def __init__(self, tasks: list[InvestigationTask]) -> None:
        self._tasks: dict[str, InvestigationTask] = {}
        for task in tasks:
            if task.task_id in self._tasks:
                raise ValueError(f"duplicate task_id: {task.task_id}")
            self._tasks[task.task_id] = task
        self._findings: dict[str, SpecialistFindingMessage] = {}

    @property
    def findings(self) -> tuple[SpecialistFindingMessage, ...]:
        return tuple(self._findings.values())

    def add(self, finding: SpecialistFindingMessage) -> bool:
        task = self._tasks.get(finding.task_id)
        if task is None:
            raise ValueError(f"finding references unknown task_id: {finding.task_id}")
        validate_finding_for_task(task, finding)

        existing = self._findings.get(finding.finding_id)
        if existing is not None:
            if existing != finding:
                raise ValueError(f"conflicting duplicate finding_id: {finding.finding_id}")
            return False

        self._findings[finding.finding_id] = finding
        return True


class CoordinationPattern(StrEnum):
    ROUTER = "router"
    HANDOFF = "handoff"
    SUPERVISOR_WORKERS = "supervisor_workers"


class PatternAssessment(BaseModel):
    pattern: CoordinationPattern
    execution_shape: str = Field(min_length=1)
    strengths: list[str] = Field(min_length=1)
    risks: list[str] = Field(min_length=1)
    selected_for_incidentlens: bool = False


def pattern_matrix() -> tuple[PatternAssessment, ...]:
    return (
        PatternAssessment(
            pattern=CoordinationPattern.ROUTER,
            execution_shape="coordinator -> one selected specialist",
            strengths=["low latency", "low cost"],
            risks=["can miss cross-domain evidence"],
        ),
        PatternAssessment(
            pattern=CoordinationPattern.HANDOFF,
            execution_shape="agent -> next agent",
            strengths=["flexible sequencing"],
            risks=["harder routing audit", "circular handoffs"],
        ),
        PatternAssessment(
            pattern=CoordinationPattern.SUPERVISOR_WORKERS,
            execution_shape="coordinator -> independent specialists -> coordinator",
            strengths=["centralized control", "parallel-ready", "clear audit trail"],
            risks=["coordination overhead", "aggregation required"],
            selected_for_incidentlens=True,
        ),
    )


def build_investigation_tasks(
    *,
    incident_id: str,
    time_window: IncidentTimeWindow,
    affected_services: list[str],
    evidence_by_signal: Mapping[str, list[str]],
) -> list[InvestigationTask]:
    """Create deterministic specialist tasks from role contracts."""
    tasks: list[InvestigationTask] = []
    for role, contract in role_contracts().items():
        signal_type = next(iter(contract.allowed_signal_types))
        tasks.append(
            InvestigationTask(
                task_id=f"task-{role.value}-{incident_id}",
                incident_id=incident_id,
                specialist_role=role,
                objective=contract.objective,
                time_window=time_window,
                affected_services=affected_services,
                allowed_tools=contract.allowed_tools,
                allowed_signal_types=contract.allowed_signal_types,
                evidence_refs=evidence_by_signal.get(signal_type, []),
                max_model_calls=contract.max_model_calls,
                max_tool_calls=contract.max_tool_calls,
            )
        )
    return tasks


class InvestigationCoordinator:
    """Central coordinator boundary for task creation and finding intake."""

    def __init__(self, tasks: list[InvestigationTask]) -> None:
        self.tasks = tuple(tasks)
        self.inbox = FindingInbox(tasks)

    def accept_finding(self, finding: SpecialistFindingMessage) -> bool:
        return self.inbox.add(finding)


def router_pattern(tasks: list[InvestigationTask], role: SpecialistRole) -> list[InvestigationTask]:
    """Pattern lab: route to one specialist."""
    return [task for task in tasks if task.specialist_role == role]


def handoff_pattern(tasks: list[InvestigationTask]) -> list[str]:
    """Pattern lab: pass control through specialists in deterministic order."""
    return [task.task_id for task in tasks]


def supervisor_workers_pattern(tasks: list[InvestigationTask]) -> list[InvestigationTask]:
    """Pattern lab: dispatch all independent tasks to a centralized supervisor."""
    return list(tasks)
