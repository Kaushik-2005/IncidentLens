import asyncio
from datetime import UTC, datetime

import pytest

from incidentlens.contracts import Hypothesis, InvestigationReport
from incidentlens.coordination import InvestigationTask
from incidentlens.parallel_investigation import (
    CoordinatorRuntime,
    SpecialistBranchResult,
    apply_coverage_to_report,
    run_branch,
    run_parallel,
    summarize_coverage,
)
from incidentlens.reliability import CircuitBreaker, CircuitBreakerRegistry
from incidentlens.specialists import SpecialistRole
from incidentlens.telemetry import IncidentTimeWindow


def make_task_for_role(role: SpecialistRole) -> InvestigationTask:
    signal = {
        SpecialistRole.LOGS: "log",
        SpecialistRole.METRICS: "metric",
        SpecialistRole.TRACES: "trace",
    }[role]
    tool = {
        SpecialistRole.LOGS: "search_logs",
        SpecialistRole.METRICS: "query_metrics",
        SpecialistRole.TRACES: "search_traces",
    }[role]
    return InvestigationTask(
        task_id=f"task-{role.value}",
        incident_id="incident-001",
        specialist_role=role,
        objective="Inspect assigned evidence.",
        time_window=IncidentTimeWindow(
            start=datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
            end=datetime(2026, 9, 15, 10, 20, tzinfo=UTC),
        ),
        affected_services=["checkout-api"],
        allowed_tools={tool},
        allowed_signal_types={signal},
        evidence_refs=[f"{signal}-1"],
        max_model_calls=3,
        max_tool_calls=5,
    )


def test_branch_result_preserves_success() -> None:
    result = SpecialistBranchResult(role=SpecialistRole.METRICS, status="success")

    assert result.role == SpecialistRole.METRICS
    assert result.status == "success"
    assert result.findings == []


def test_run_branch_converts_timeout_to_structured_result() -> None:
    async def run() -> SpecialistBranchResult:
        async def slow_worker(_task):
            await asyncio.Event().wait()
            return []

        return await run_branch(
            make_task_for_role(SpecialistRole.METRICS),
            slow_worker,
            asyncio.Semaphore(1),
            timeout_seconds=0.01,
        )

    result = asyncio.run(run())

    assert result.role == SpecialistRole.METRICS
    assert result.status == "timeout"
    assert result.findings == []


def test_run_parallel_returns_stable_role_order() -> None:
    async def worker(task):
        await asyncio.sleep(
            {SpecialistRole.LOGS: 0.03, SpecialistRole.METRICS: 0.02, SpecialistRole.TRACES: 0}[
                task.specialist_role
            ]
        )
        return []

    tasks = [make_task_for_role(role) for role in reversed(list(SpecialistRole))]
    results = asyncio.run(run_parallel(tasks, worker, max_concurrency=3, branch_timeout_seconds=1))

    assert [result.role for result in results] == list(SpecialistRole)


def test_coordinator_runtime_composes_parallel_results_for_graph_boundary() -> None:
    async def worker(_task):
        return []

    runtime = CoordinatorRuntime(
        [make_task_for_role(SpecialistRole.METRICS)],
        worker,
        max_concurrency=1,
        branch_timeout_seconds=1,
    )

    results = runtime(type("State", (), {"incident_id": "incident-001"})())

    assert len(results) == 1
    assert results[0].role == SpecialistRole.METRICS


def test_run_parallel_preserves_sibling_success_when_one_fails() -> None:
    async def worker(task):
        if task.specialist_role == SpecialistRole.METRICS:
            raise RuntimeError("provider detail")
        return []

    results = asyncio.run(
        run_parallel(
            [make_task_for_role(role) for role in SpecialistRole],
            worker,
            max_concurrency=3,
            branch_timeout_seconds=1,
        )
    )

    statuses = {result.role: result.status for result in results}
    assert statuses[SpecialistRole.LOGS] == "success"
    assert statuses[SpecialistRole.METRICS] == "failed"
    assert statuses[SpecialistRole.TRACES] == "success"


def test_run_parallel_fails_open_branch_but_keeps_healthy_siblings() -> None:
    metrics_breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=10)
    metrics_breaker.record_failure()

    async def worker(_task):
        return []

    results = asyncio.run(
        run_parallel(
            [make_task_for_role(role) for role in SpecialistRole],
            worker,
            max_concurrency=3,
            branch_timeout_seconds=1,
            circuit_breakers={SpecialistRole.METRICS: metrics_breaker},
        )
    )

    statuses = {result.role: result for result in results}
    assert statuses[SpecialistRole.METRICS].status == "dependency_error"
    assert statuses[SpecialistRole.METRICS].error == "dependency circuit open"
    assert statuses[SpecialistRole.METRICS].incident_error is not None
    assert (
        statuses[SpecialistRole.METRICS].incident_error.classification
        == "dependency_circuit_open"
    )
    assert statuses[SpecialistRole.LOGS].status == "success"
    assert statuses[SpecialistRole.TRACES].status == "success"


def test_run_parallel_uses_coordinator_registry_scope() -> None:
    registry = CircuitBreakerRegistry(failure_threshold=1, recovery_timeout_seconds=10)
    registry.get(
        backend="metrics_backend", tenant_id="default-tenant", environment="production"
    ).record_failure()

    async def worker(_task):
        return []

    results = asyncio.run(
        run_parallel(
            [make_task_for_role(role) for role in SpecialistRole],
            worker,
            max_concurrency=3,
            branch_timeout_seconds=1,
            circuit_breaker_registry=registry,
        )
    )

    statuses = {result.role: result.status for result in results}
    assert statuses[SpecialistRole.METRICS] == "dependency_error"
    assert statuses[SpecialistRole.LOGS] == "success"
    assert statuses[SpecialistRole.TRACES] == "success"


def test_partial_coverage_downgrades_report_to_inconclusive() -> None:
    report = InvestigationReport(
        incident_id="incident-001",
        summary="The dependency appears to be the likely cause.",
        evidence=[],
        hypotheses=[
            Hypothesis(
                statement="The dependency caused the failure.",
                confidence="medium",
            )
        ],
        status="completed",
    )
    results = [
        SpecialistBranchResult(role=SpecialistRole.LOGS, status="success"),
        SpecialistBranchResult(
            role=SpecialistRole.METRICS,
            status="failed",
            error="dependency circuit open",
        ),
    ]

    coverage = summarize_coverage(results)
    downgraded = apply_coverage_to_report(report, results)

    assert coverage.status == "inconclusive"
    assert downgraded.status == "inconclusive"
    assert "metrics_agent" in downgraded.summary


def test_no_successful_branches_produce_failed_coverage() -> None:
    results = [
        SpecialistBranchResult(role=SpecialistRole.LOGS, status="failed"),
        SpecialistBranchResult(role=SpecialistRole.METRICS, status="timeout"),
    ]

    coverage = summarize_coverage(results)

    assert coverage.status == "failed"


def test_run_parallel_rejects_invalid_concurrency() -> None:
    with pytest.raises(ValueError, match="max_concurrency"):
        asyncio.run(
            run_parallel(
                [],
                lambda _task: asyncio.sleep(0, result=[]),
                max_concurrency=0,
                branch_timeout_seconds=1,
            )
        )


from time import perf_counter

from incidentlens.coordination import SpecialistFindingMessage
from incidentlens.parallel_investigation import aggregate_findings
from incidentlens.specialists import FindingKind


def make_finding(
    task: InvestigationTask, finding_id: str = "finding-001"
) -> SpecialistFindingMessage:
    evidence_id = next(iter(task.evidence_refs))
    return SpecialistFindingMessage(
        task_id=task.task_id,
        finding_id=finding_id,
        incident_id=task.incident_id,
        agent_id=task.specialist_role.value,
        specialist_role=task.specialist_role,
        claim_kind=FindingKind.OBSERVATION,
        claim="Assigned evidence was observed.",
        evidence_ids=[evidence_id],
        confidence="medium",
    )


def test_global_deadline_preserves_completed_and_cancels_pending_branches() -> None:
    async def worker(task):
        if task.specialist_role == SpecialistRole.METRICS:
            await asyncio.Event().wait()
        return []

    results = asyncio.run(
        run_parallel(
            [make_task_for_role(role) for role in SpecialistRole],
            worker,
            max_concurrency=3,
            branch_timeout_seconds=1,
            global_timeout_seconds=0.01,
        )
    )

    statuses = {result.role: result.status for result in results}
    assert statuses[SpecialistRole.LOGS] == "success"
    assert statuses[SpecialistRole.METRICS] == "cancelled"
    assert statuses[SpecialistRole.TRACES] == "success"


def test_aggregate_findings_deduplicates_exact_worker_results() -> None:
    task = make_task_for_role(SpecialistRole.METRICS)
    finding = make_finding(task)
    results = [
        SpecialistBranchResult(
            role=SpecialistRole.METRICS,
            status="success",
            findings=[finding, finding],
        )
    ]

    assert aggregate_findings([task], results) == (finding,)


def test_concurrent_execution_is_faster_than_sequential_execution() -> None:
    async def worker(_task):
        await asyncio.sleep(0.03)
        return []

    tasks = [make_task_for_role(role) for role in SpecialistRole]

    async def sequential() -> None:
        for task in tasks:
            await worker(task)

    sequential_start = perf_counter()
    asyncio.run(sequential())
    sequential_elapsed = perf_counter() - sequential_start

    parallel_start = perf_counter()
    asyncio.run(
        run_parallel(
            tasks,
            worker,
            max_concurrency=3,
            branch_timeout_seconds=1,
        )
    )
    parallel_elapsed = perf_counter() - parallel_start

    assert parallel_elapsed < sequential_elapsed
