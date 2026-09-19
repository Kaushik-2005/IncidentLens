import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from incidentlens.contracts import InvestigationReport
from incidentlens.coordination import (
    FindingInbox,
    InvestigationTask,
    SpecialistFindingMessage,
)
from incidentlens.reliability import CircuitBreaker, CircuitBreakerRegistry
from incidentlens.specialists import SpecialistRole

BranchStatus = Literal[
    "success",
    "timeout",
    "failed",
    "cancelled",
]
ReportStatus = Literal["completed", "inconclusive", "failed"]

Worker = Callable[
    [InvestigationTask],
    Awaitable[list[SpecialistFindingMessage]],
]

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
            if circuit_breaker is not None and not circuit_breaker.allow_request():
                return SpecialistBranchResult(
                    role=task.specialist_role,
                    status="failed",
                    error="dependency circuit open",
                )
            try:
                raw_findings = await asyncio.wait_for(
                    worker(task),
                    timeout=timeout_seconds,
                )
                findings = [SpecialistFindingMessage.model_validate(item) for item in raw_findings]
                if circuit_breaker is not None:
                    circuit_breaker.record_success()
            except TimeoutError:
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                return SpecialistBranchResult(
                    role=task.specialist_role,
                    status="timeout",
                    error="specialist deadline exceeded",
                )
            except (RuntimeError, TypeError, ValueError, ValidationError):
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                return SpecialistBranchResult(
                    role=task.specialist_role,
                    status="failed",
                    error="specialist execution failed",
                )
            except Exception:  # noqa: BLE001 - isolate unexpected worker failures
                if circuit_breaker is not None:
                    circuit_breaker.record_failure()
                return SpecialistBranchResult(
                    role=task.specialist_role,
                    status="failed",
                    error="specialist execution failed",
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
