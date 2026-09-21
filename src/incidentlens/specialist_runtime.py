import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC
from typing import Protocol

from incidentlens.agent_loop import ModelCallBudget, ModelClient, run_agent_loop_with_metadata
from incidentlens.contracts import IncidentInput
from incidentlens.coordination import InvestigationTask, SpecialistFindingMessage
from incidentlens.parallel_investigation import SpecialistWorkerResult
from incidentlens.specialists import FindingKind, SpecialistRole
from incidentlens.tools import ToolRegistry


class SpecialistModelFactory(Protocol):
    def __call__(self, role: SpecialistRole) -> ModelClient:
        """Return the provider adapter assigned to one specialist role."""


def build_model_backed_worker(
    models: Mapping[SpecialistRole, ModelClient],
    registries: Mapping[SpecialistRole, ToolRegistry],
    *,
    model_budgets: Mapping[SpecialistRole, ModelCallBudget] | None = None,
    tool_budgets: Mapping[SpecialistRole, ModelCallBudget] | None = None,
) -> Callable[[InvestigationTask], Awaitable[SpecialistWorkerResult]]:
    """Build the bounded worker used by ``CoordinatorRuntime``.

    The worker translates a task envelope into the provider-neutral IncidentInput,
    runs the existing bounded loop with the role-specific registry, and converts
    only evidence-linked hypotheses into coordinator findings.
    """

    async def worker(task: InvestigationTask) -> SpecialistWorkerResult:
        model = models[task.specialist_role]
        registry = registries[task.specialist_role]
        incident = IncidentInput(
            incident_id=task.incident_id,
            title=f"{task.specialist_role.value} investigation",
            affected_service=task.affected_services[0],
            start_time=task.time_window.start.isoformat(),
            end_time=task.time_window.end.astimezone(UTC).isoformat(),
            summary=task.objective,
        )
        result = await asyncio.to_thread(
            run_agent_loop_with_metadata,
            incident=incident,
            model=model,
            tools=registry,
            max_steps=task.max_model_calls,
            model_budget=(model_budgets or {}).get(task.specialist_role),
            tool_budget=(tool_budgets or {}).get(task.specialist_role),
        )
        findings: list[SpecialistFindingMessage] = []
        for index, hypothesis in enumerate(result.report.hypotheses):
            evidence_ids = list(
                dict.fromkeys(
                    hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids
                )
            )
            if not evidence_ids:
                continue
            claim_kind = (
                FindingKind.OBSERVATION
                if not hypothesis.supporting_evidence_ids
                else FindingKind.INFERENCE
            )
            findings.append(
                SpecialistFindingMessage(
                    task_id=task.task_id,
                    finding_id=f"{task.task_id}-finding-{index + 1}",
                    incident_id=task.incident_id,
                    agent_id=task.specialist_role.value,
                    specialist_role=task.specialist_role,
                    claim_kind=claim_kind,
                    claim=hypothesis.statement,
                    evidence_ids=evidence_ids,
                    confidence=hypothesis.confidence,
                    open_questions=list(hypothesis.missing_evidence),
                    limitations=(
                        ["specialist report was inconclusive"]
                        if result.report.status != "completed"
                        else []
                    ),
                )
            )
        return SpecialistWorkerResult(
            findings=findings,
            model_calls=result.metadata.model_calls,
            tool_calls=result.metadata.tool_calls,
            latency_ms=result.metadata.elapsed_ms,
            requested_tools=result.metadata.requested_tools,
            input_tokens=result.metadata.input_tokens,
            output_tokens=result.metadata.output_tokens,
            total_tokens=result.metadata.total_tokens,
        )

    return worker
