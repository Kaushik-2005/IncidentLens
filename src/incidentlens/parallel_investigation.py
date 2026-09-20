import asyncio
from collections.abc import Awaitable, Callable, Mapping
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from incidentlens.agent_loop import (
    InvalidModelResponseError,
    MaxStepsExceededError,
    ModelBudgetExhaustedError,
    ModelProviderError,
    ToolBudgetExhaustedError,
)
from incidentlens.contracts import InvestigationReport
from incidentlens.coordination import (
    FindingInbox,
    InvestigationTask,
    SpecialistFindingMessage,
)
from incidentlens.errors import ErrorComponent, IncidentError
from incidentlens.reliability import CircuitBreaker, CircuitBreakerRegistry
from incidentlens.specialists import SpecialistRole

BranchStatus = Literal[
    "success",
    "timeout",
    "dependency_error",
    "failed",
    "cancelled",
]
ReportStatus = Literal["completed", "inconclusive", "failed"]

class SpecialistWorkerResult(BaseModel):
    """Findings plus sanitized execution measurements from one specialist worker."""

    findings: list[SpecialistFindingMessage] = Field(default_factory=list)
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0, ge=0)
    requested_tools: list[str] = Field(default_factory=list)


Worker = Callable[
    [InvestigationTask],
    Awaitable[list[SpecialistFindingMessage] | SpecialistWorkerResult],
]


class CoordinatorRuntime:
    """Synchronous graph-facing composition of task creation results and parallel fan-in."""

    def __init__(
        self,
        tasks: list[InvestigationTask],
        worker: Worker,
        *,
        max_concurrency: int,
        branch_timeout_seconds: float,
        global_timeout_seconds: float | None = None,
        circuit_breaker_registry: CircuitBreakerRegistry | None = None,
    ) -> None:
        self.tasks = list(tasks)
        self.worker = worker
        self.max_concurrency = max_concurrency
        self.branch_timeout_seconds = branch_timeout_seconds
        self.global_timeout_seconds = global_timeout_seconds
        self.circuit_breaker_registry = circuit_breaker_registry

    def __call__(self, state: object) -> list["SpecialistBranchResult"]:
        incident_id = getattr(state, "incident_id", None)
        if incident_id is not None and any(
            task.incident_id != incident_id for task in self.tasks
        ):
            raise ValueError("INVESTIGATION_SCOPE_MISMATCH")
        return asyncio.run(
            run_parallel(
                self.tasks,
                self.worker,
                max_concurrency=self.max_concurrency,
                branch_timeout_seconds=self.branch_timeout_seconds,
                global_timeout_seconds=self.global_timeout_seconds,
                circuit_breaker_registry=self.circuit_breaker_registry,
            )
        )

SPECIALIST_ORDER = {
    SpecialistRole.LOGS: 0,
    SpecialistRole.METRICS: 1,
    SpecialistRole.TRACES: 2,
}

SPECIALIST_BACKENDS = {
    SpecialistRole.LOGS: "logs_backend",
    SpecialistRole.METRICS: "metrics_backend",
    SpecialistRole.TRACES: "traces_backend",
}


class SpecialistBranchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: SpecialistRole
    status: BranchStatus
    findings: list[SpecialistFindingMessage] = Field(default_factory=list)
    error: str | None = None
    incident_error: IncidentError | None = None
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0, ge=0)
    requested_tools: list[str] = Field(default_factory=list)


class InvestigationCoverage(BaseModel):
    status: ReportStatus
    message: str
    unavailable_roles: tuple[SpecialistRole, ...] = ()


def summarize_coverage(results: list[SpecialistBranchResult]) -> InvestigationCoverage:
    unavailable = tuple(result.role for result in results if result.status != "success")
    if not unavailable:
        return InvestigationCoverage(
            status="completed", message="All specialist evidence was available."
        )
    if not any(result.status == "success" for result in results):
        return InvestigationCoverage(
            status="failed",
            message="No specialist evidence was available; the investigation could not produce a grounded report.",
            unavailable_roles=unavailable,
        )
    roles = ", ".join(role.value for role in unavailable)
    return InvestigationCoverage(
        status="inconclusive",
        message=f"Evidence coverage was incomplete because these specialists were unavailable: {roles}.",
        unavailable_roles=unavailable,
    )


def apply_coverage_to_report(
    report: InvestigationReport,
    results: list[SpecialistBranchResult],
) -> InvestigationReport:
    coverage = summarize_coverage(results)
    if coverage.status == "completed":
        return report
    return report.model_copy(
        update={
            "status": coverage.status,
            "summary": f"{coverage.message} {report.summary}",
        }
    )


async def run_branch(
    task: InvestigationTask,
    worker: Worker,
    semaphore: asyncio.Semaphore,
    timeout_seconds: float,
    circuit_breaker: CircuitBreaker | None = None,
) -> SpecialistBranchResult:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    try:
        async with semaphore:
            started_at = perf_counter()
            if circuit_breaker is not None and not circuit_breaker.allow_request():
                return SpecialistBranchResult(
                    role=task.specialist_role,
                    status="dependency_error",
                    error="dependency circuit open",
                    incident_error=IncidentError.from_message(
                        classification="dependency_circuit_open",
                        retryable=False,
                        component=_backend_component(task.specialist_role),
                        correlation_id=f"circuit-{task.task_id}",
                        user_message=(
                            "Telemetry evidence was unavailable because the dependency "
                            "circuit is open."
                        ),
                    ),
                )
            try:
                raw_result = await asyncio.wait_for(
                    worker(task),
                    timeout=timeout_seconds,
                )
                if isinstance(raw_result, SpecialistWorkerResult):
                    worker_result = raw_result
                else:
                    worker_result = SpecialistWorkerResult(findings=raw_result)
                findings = [
                    SpecialistFindingMessage.model_validate(item)
                    for item in worker_result.findings
                ]
                if circuit_breaker is not None:
                    circuit_breaker.record_success()
            except TimeoutError:
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                return SpecialistBranchResult(
                    role=task.specialist_role,
                    status="timeout",
                    error="specialist deadline exceeded",
                    incident_error=IncidentError.from_message(
                        classification="dependency_timeout",
                        retryable=True,
                        component=_backend_component(task.specialist_role),
                        correlation_id=f"timeout-{task.task_id}",
                        user_message="Telemetry evidence could not be retrieved within the allowed time.",
                    ),
                )
            except ModelProviderError as exc:
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                incident_error = exc.incident_error or IncidentError.from_message(
                    classification="service_unavailable",
                    retryable=exc.retryable,
                    component=_backend_component(task.specialist_role),
                    correlation_id=f"branch-{task.task_id}",
                    user_message="The specialist model service failed during investigation.",
                )
                return _failed_branch(
                    task,
                    incident_error,
                    latency_ms=(perf_counter() - started_at) * 1000,
                )
            except ModelBudgetExhaustedError as exc:
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                return _failed_branch(
                    task,
                    exc.incident_error,
                    latency_ms=(perf_counter() - started_at) * 1000,
                )
            except ToolBudgetExhaustedError as exc:
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                return _failed_branch(
                    task,
                    exc.incident_error,
                    latency_ms=(perf_counter() - started_at) * 1000,
                )
            except InvalidModelResponseError:
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                return _failed_branch(
                    task,
                    IncidentError.from_message(
                        classification="model_contract_violation",
                        retryable=True,
                        component="model_adapter",
                        correlation_id=f"branch-{task.task_id}",
                        user_message="The specialist model returned an invalid response.",
                    ),
                    latency_ms=(perf_counter() - started_at) * 1000,
                )
            except MaxStepsExceededError:
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                return _failed_branch(
                    task,
                    IncidentError.from_message(
                        classification="model_step_limit_exhausted",
                        retryable=False,
                        component="coordinator",
                        correlation_id=f"branch-{task.task_id}",
                        user_message="The specialist did not produce a valid report within its step limit.",
                    ),
                    latency_ms=(perf_counter() - started_at) * 1000,
                )
            except (RuntimeError, TypeError, ValueError, ValidationError):
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                return _failed_branch(
                    task,
                    IncidentError.from_message(
                        classification="service_unavailable",
                        retryable=False,
                        component=_backend_component(task.specialist_role),
                        correlation_id=f"branch-{task.task_id}",
                        user_message="The specialist failed during investigation.",
                    ),
                    latency_ms=(perf_counter() - started_at) * 1000,
                )
            except Exception:  # noqa: BLE001 - isolate unexpected worker failures
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                return _failed_branch(
                    task,
                    IncidentError.from_message(
                        classification="service_unavailable",
                        retryable=False,
                        component=_backend_component(task.specialist_role),
                        correlation_id=f"branch-{task.task_id}",
                        user_message="The specialist failed during investigation.",
                    ),
                    latency_ms=(perf_counter() - started_at) * 1000,
                )
    except asyncio.CancelledError:
        return SpecialistBranchResult(
            role=task.specialist_role,
            status="cancelled",
            error="specialist execution cancelled",
        )

    return SpecialistBranchResult(
        role=task.specialist_role,
        status="success",
        findings=findings,
        model_calls=worker_result.model_calls,
        tool_calls=worker_result.tool_calls,
        latency_ms=worker_result.latency_ms,
        requested_tools=worker_result.requested_tools,
    )


def _failed_branch(
    task: InvestigationTask,
    error: IncidentError,
    *,
    latency_ms: float = 0,
) -> SpecialistBranchResult:
    """Return a branch failure without allowing raw exception text to cross the boundary."""
    return SpecialistBranchResult(
        role=task.specialist_role,
        status="failed",
        error=error.classification,
        incident_error=error,
        model_calls=max(1, error.attempt_count),
        latency_ms=latency_ms,
    )


async def run_parallel(
    tasks: list[InvestigationTask],
    worker: Worker,
    *,
    max_concurrency: int,
    branch_timeout_seconds: float,
    global_timeout_seconds: float | None = None,
    circuit_breakers: Mapping[SpecialistRole, CircuitBreaker] | None = None,
    circuit_breaker_registry: CircuitBreakerRegistry | None = None,
) -> list[SpecialistBranchResult]:
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least one")
    if branch_timeout_seconds <= 0:
        raise ValueError("branch_timeout_seconds must be greater than zero")
    if global_timeout_seconds is not None and global_timeout_seconds <= 0:
        raise ValueError("global_timeout_seconds must be greater than zero")
    if len({task.specialist_role for task in tasks}) != len(tasks):
        raise ValueError("tasks must contain at most one task per specialist role")

    semaphore = asyncio.Semaphore(max_concurrency)
    branch_tasks = [
        asyncio.create_task(
            run_branch(
                task,
                worker,
                semaphore,
                branch_timeout_seconds,
                (
                    None
                    if circuit_breakers is None and circuit_breaker_registry is None
                    else (
                        circuit_breakers.get(task.specialist_role)
                        if circuit_breakers is not None
                        else circuit_breaker_registry.get(
                            backend=SPECIALIST_BACKENDS[task.specialist_role],
                            tenant_id=task.tenant_id,
                            environment=task.environment,
                        )
                    )
                ),
            )
        )
        for task in tasks
    ]
    if global_timeout_seconds is None:
        results = await asyncio.gather(*branch_tasks)
    else:
        done, pending = await asyncio.wait(branch_tasks, timeout=global_timeout_seconds)
        for pending_task in pending:
            pending_task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        results = [
            task.result()
            if task in done
            else SpecialistBranchResult(
                role=tasks[index].specialist_role,
                status="cancelled",
                error="global investigation deadline exceeded",
            )
            for index, task in enumerate(branch_tasks)
        ]

    return sorted(results, key=lambda result: SPECIALIST_ORDER[result.role])


def aggregate_findings(
    tasks: list[InvestigationTask],
    results: list[SpecialistBranchResult],
) -> tuple[SpecialistFindingMessage, ...]:
    """Validate and deduplicate successful findings in deterministic task order."""
    inbox = FindingInbox(tasks)
    for result in results:
        if result.status != "success":
            continue
        for finding in result.findings:
            try:
                inbox.add(finding)
            except ValueError:
                continue
    return inbox.findings


def _backend_component(role: SpecialistRole) -> ErrorComponent:
    return {
        SpecialistRole.LOGS: "logs_backend",
        SpecialistRole.METRICS: "metrics_backend",
        SpecialistRole.TRACES: "traces_backend",
    }[role]
