from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from incidentlens.specialists import FindingKind, SpecialistRole, role_contracts
from incidentlens.telemetry import IncidentTimeWindow


class InvestigationTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_type: Literal["investigation_task"] = "investigation_task"
    schema_version: Literal["1.0"] = "1.0"

    task_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    tenant_id: str = Field(default="default-tenant", min_length=1)
    specialist_role: SpecialistRole

    objective: str = Field(min_length=1)
    time_window: IncidentTimeWindow
    affected_services: list[str] = Field(min_length=1)
    environment: str = Field(default="production", min_length=1)

    allowed_tools: frozenset[str] = Field(min_length=1)
    allowed_signal_types: frozenset[Literal["log", "metric", "trace"]] = Field(min_length=1)

    evidence_refs: list[str] = Field(default_factory=list)

    max_model_calls: int = Field(ge=1)
    max_tool_calls: int = Field(ge=1)

    output_contract: Literal["SpecialistFinding"] = "SpecialistFinding"


class FollowUpProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str = Field(min_length=1)
    specialist_role: SpecialistRole
    evidence_gap: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class FollowUpContext(BaseModel):
    known_evidence_ids: frozenset[str] = Field(default_factory=frozenset)
    allowed_roles: frozenset[SpecialistRole] = Field(default_factory=frozenset)
    existing_task_keys: frozenset[str] = Field(default_factory=frozenset)
    follow_up_round: int = Field(ge=0)
    max_follow_up_rounds: int = Field(ge=0)
    remaining_tool_calls: int = Field(ge=0)
    remaining_model_calls: int = Field(ge=0)
    global_deadline_reached: bool = False


class FollowUpValidationResult(BaseModel):
    accepted: bool
    reason: str | None = None


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

    def register_task(self, task: InvestigationTask) -> None:
        if task.task_id in self._tasks:
            raise ValueError(f"duplicate task_id: {task.task_id}")
        self._tasks[task.task_id] = task

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
        self.follow_up_round = 0
        self.scheduled_task_keys: set[str] = set()

    def accept_finding(self, finding: SpecialistFindingMessage) -> bool:
        return self.inbox.add(finding)

    def schedule_follow_up(
        self,
        proposal: FollowUpProposal,
        context: FollowUpContext,
        *,
        incident_id: str,
        time_window: IncidentTimeWindow,
        affected_services: list[str],
    ) -> InvestigationTask:
        if self.tasks and incident_id != self.tasks[0].incident_id:
            raise ValueError("INCIDENT_SCOPE_MISMATCH")

        validation_context = context.model_copy(
            update={
                "existing_task_keys": context.existing_task_keys
                | frozenset(self.scheduled_task_keys),
            }
        )
        validation = validate_follow_up(proposal, validation_context)
        if not validation.accepted:
            raise ValueError(validation.reason or "FOLLOW_UP_REJECTED")

        contract = role_contracts()[proposal.specialist_role]
        round_number = context.follow_up_round + 1
        task = InvestigationTask(
            task_id=f"followup-{proposal.specialist_role.value}-{incident_id}-{round_number}",
            incident_id=incident_id,
            specialist_role=proposal.specialist_role,
            objective=proposal.objective,
            time_window=time_window,
            affected_services=affected_services,
            allowed_tools=contract.allowed_tools,
            allowed_signal_types=contract.allowed_signal_types,
            evidence_refs=proposal.supporting_evidence_ids,
            max_model_calls=min(contract.max_model_calls, context.remaining_model_calls),
            max_tool_calls=min(contract.max_tool_calls, context.remaining_tool_calls),
        )
        self.inbox.register_task(task)
        self.tasks = (*self.tasks, task)
        self.follow_up_round = round_number
        self.scheduled_task_keys.add(canonical_task_key(proposal))
        return task


def router_pattern(tasks: list[InvestigationTask], role: SpecialistRole) -> list[InvestigationTask]:
    """Pattern lab: route to one specialist."""
    return [task for task in tasks if task.specialist_role == role]


def handoff_pattern(tasks: list[InvestigationTask]) -> list[str]:
    """Pattern lab: pass control through specialists in deterministic order."""
    return [task.task_id for task in tasks]


def supervisor_workers_pattern(tasks: list[InvestigationTask]) -> list[InvestigationTask]:
    """Pattern lab: dispatch all independent tasks to a centralized supervisor."""
    return list(tasks)


def canonical_task_key(proposal: FollowUpProposal) -> str:
    return "|".join(
        [
            proposal.specialist_role.value,
            proposal.objective.strip().lower(),
            proposal.evidence_gap.strip().lower(),
            ",".join(sorted(proposal.supporting_evidence_ids)),
        ]
    )


def validate_follow_up(
    proposal: FollowUpProposal,
    context: FollowUpContext,
) -> FollowUpValidationResult:
    unknown_ids = set(proposal.supporting_evidence_ids) - set(context.known_evidence_ids)
    if unknown_ids:
        return FollowUpValidationResult(accepted=False, reason="UNKNOWN_EVIDENCE_ID")
    if proposal.specialist_role not in context.allowed_roles:
        return FollowUpValidationResult(accepted=False, reason="ROLE_NOT_ALLOWED")
    if canonical_task_key(proposal) in context.existing_task_keys:
        return FollowUpValidationResult(accepted=False, reason="DUPLICATE_FOLLOW_UP")
    if context.follow_up_round >= context.max_follow_up_rounds:
        return FollowUpValidationResult(accepted=False, reason="FOLLOW_UP_LIMIT_EXCEEDED")
    if context.remaining_tool_calls <= 0:
        return FollowUpValidationResult(accepted=False, reason="TOOL_BUDGET_EXHAUSTED")
    if context.remaining_model_calls <= 0:
        return FollowUpValidationResult(accepted=False, reason="MODEL_BUDGET_EXHAUSTED")
    if context.global_deadline_reached:
        return FollowUpValidationResult(accepted=False, reason="GLOBAL_DEADLINE_EXCEEDED")
    return FollowUpValidationResult(accepted=True)


class IncidentComplexity(StrEnum):
    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"


class ComplexityPolicy(BaseModel):
    complexity: IncidentComplexity
    baseline_roles: frozenset[SpecialistRole] = Field(min_length=1)
    max_follow_up_rounds: int = Field(ge=0)


def classify_incident(
    *,
    affected_services: list[str],
    evidence_by_signal: Mapping[str, list[str]],
) -> IncidentComplexity:
    service_count = len(set(affected_services))
    signal_count = sum(bool(records) for records in evidence_by_signal.values())
    if service_count <= 1 and signal_count <= 1:
        return IncidentComplexity.SIMPLE
    if service_count <= 2 and signal_count <= 2:
        return IncidentComplexity.STANDARD
    return IncidentComplexity.COMPLEX


def complexity_policy(complexity: IncidentComplexity) -> ComplexityPolicy:
    if complexity == IncidentComplexity.SIMPLE:
        return ComplexityPolicy(
            complexity=complexity,
            baseline_roles=frozenset({SpecialistRole.METRICS}),
            max_follow_up_rounds=1,
        )
    return ComplexityPolicy(
        complexity=complexity,
        baseline_roles=frozenset(SpecialistRole),
        max_follow_up_rounds=1,
    )


class BudgetLedger(BaseModel):
    max_model_calls: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)

    @property
    def remaining_model_calls(self) -> int:
        return self.max_model_calls - self.model_calls

    @property
    def remaining_tool_calls(self) -> int:
        return self.max_tool_calls - self.tool_calls

    def consume(self, *, model_calls: int = 0, tool_calls: int = 0) -> None:
        if model_calls < 0 or tool_calls < 0:
            raise ValueError("budget increments cannot be negative")
        if model_calls > self.remaining_model_calls:
            raise ValueError("MODEL_BUDGET_EXHAUSTED")
        if tool_calls > self.remaining_tool_calls:
            raise ValueError("TOOL_BUDGET_EXHAUSTED")
        self.model_calls += model_calls
        self.tool_calls += tool_calls


class TerminationDecision(BaseModel):
    terminate: bool
    reason: Literal[
        "report_ready",
        "budget_exhausted",
        "deadline_exceeded",
        "follow_up_limit",
        "no_new_work",
        "continue_investigation",
    ]


def evaluate_termination(
    *,
    valid_report_possible: bool,
    pending_tasks: bool,
    follow_up_round: int,
    max_follow_up_rounds: int,
    budget: BudgetLedger,
    deadline_reached: bool,
) -> TerminationDecision:
    if valid_report_possible and not pending_tasks:
        return TerminationDecision(terminate=True, reason="report_ready")
    if deadline_reached:
        return TerminationDecision(terminate=True, reason="deadline_exceeded")
    if budget.remaining_model_calls == 0 or budget.remaining_tool_calls == 0:
        return TerminationDecision(terminate=True, reason="budget_exhausted")
    if follow_up_round >= max_follow_up_rounds:
        return TerminationDecision(terminate=True, reason="follow_up_limit")
    if not pending_tasks:
        return TerminationDecision(terminate=True, reason="no_new_work")
    return TerminationDecision(terminate=False, reason="continue_investigation")
