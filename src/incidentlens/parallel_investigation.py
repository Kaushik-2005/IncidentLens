import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from incidentlens.coordination import (
    FindingInbox,
    InvestigationTask,
    SpecialistFindingMessage,
)
from incidentlens.specialists import SpecialistRole

BranchStatus = Literal[
    "success",
    "timeout",
    "failed",
    "cancelled",
]

Worker = Callable[
    [InvestigationTask],
    Awaitable[list[SpecialistFindingMessage]],
]

SPECIALIST_ORDER = {
    SpecialistRole.LOGS: 0,
    SpecialistRole.METRICS: 1,
    SpecialistRole.TRACES: 2,
}


class SpecialistBranchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: SpecialistRole
    status: BranchStatus
    findings: list[SpecialistFindingMessage] = Field(default_factory=list)
    error: str | None = None


async def run_branch(
    task: InvestigationTask,
    worker: Worker,
    semaphore: asyncio.Semaphore,
    timeout_seconds: float,
) -> SpecialistBranchResult:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    try:
        async with semaphore:
            try:
                raw_findings = await asyncio.wait_for(
                    worker(task),
                    timeout=timeout_seconds,
                )
                findings = [SpecialistFindingMessage.model_validate(item) for item in raw_findings]
            except TimeoutError:
                return SpecialistBranchResult(
                    role=task.specialist_role,
                    status="timeout",
                    error="specialist deadline exceeded",
                )
            except (RuntimeError, TypeError, ValueError, ValidationError):
                return SpecialistBranchResult(
                    role=task.specialist_role,
                    status="failed",
                    error="specialist execution failed",
                )
            except Exception:  # noqa: BLE001 - isolate unexpected worker failures
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
        asyncio.create_task(run_branch(task, worker, semaphore, branch_timeout_seconds))
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
