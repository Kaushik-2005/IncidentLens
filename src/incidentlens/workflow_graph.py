from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from incidentlens.contracts import InvestigationReport, validate_report_acceptance
from incidentlens.errors import IncidentError
from incidentlens.parallel_investigation import (
    CoordinatorRuntime,
    SpecialistBranchResult,
    apply_coverage_to_report,
)
from incidentlens.persistence import ArtifactStore, StoredArtifact
from incidentlens.workflow_state import (
    IncidentGraphState,
    InvalidTransitionError,
    LifecycleStatus,
    transition,
)

ReportFactory = Callable[[IncidentGraphState], InvestigationReport]
InvestigationRunner = Callable[[IncidentGraphState], list[SpecialistBranchResult]]


def build_incident_graph(
    report_factory: ReportFactory,
    *,
    checkpointer: Any | None = None,
    interrupt_before: list[str] | None = None,
    artifact_store: ArtifactStore | None = None,
    investigation_runner: InvestigationRunner | None = None,
    coordinator_runtime: CoordinatorRuntime | None = None,
) -> Any:
    """Build a deterministic lifecycle graph with an injected report producer."""
    graph = StateGraph(IncidentGraphState)
    graph.add_node("validate", _node_to(LifecycleStatus.TRIAGING))
    graph.add_node("triage", _node_to(LifecycleStatus.INVESTIGATING))
    runner = investigation_runner or coordinator_runtime
    graph.add_node("investigate", lambda state: _investigate(state, runner))
    graph.add_node("synthesize", lambda state: _synthesize(state, report_factory, artifact_store))

    graph.add_edge(START, "validate")
    graph.add_conditional_edges("validate", _route, {"triage": "triage", "end": END})
    graph.add_conditional_edges("triage", _route, {"investigate": "investigate", "end": END})
    graph.add_conditional_edges("investigate", _route, {"synthesize": "synthesize", "end": END})
    graph.add_conditional_edges("synthesize", _route, {"end": END})
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
    )


def _node_to(target: LifecycleStatus) -> Callable[[Any], dict[str, Any]]:
    def node(raw_state: Any) -> dict[str, Any]:
        state = IncidentGraphState.model_validate(raw_state)
        if state.cancel_requested:
            return transition(state, LifecycleStatus.CANCELLED).model_dump()
        try:
            return transition(state, target).model_dump()
        except InvalidTransitionError:
            failed = state.model_copy(update={"error": "invalid lifecycle transition"})
            return transition(failed, LifecycleStatus.FAILED).model_dump()

    return node


def _synthesize(
    raw_state: Any,
    report_factory: ReportFactory,
    artifact_store: ArtifactStore | None,
) -> dict[str, Any]:
    state = IncidentGraphState.model_validate(raw_state)
    if state.cancel_requested:
        return transition(state, LifecycleStatus.CANCELLED).model_dump()
    try:
        report = InvestigationReport.model_validate(report_factory(state))
        report = validate_report_acceptance(report)
        if state.specialist_results:
            report = apply_coverage_to_report(report, state.specialist_results)
        if report.incident_id != state.incident_id:
            raise ValueError("report incident does not match active incident")
        with_report = state.model_copy(update={"report": report})
        if artifact_store is not None:
            evidence_artifact_ids = []
            for evidence in report.evidence:
                evidence_id = f"evidence-{state.incident_id}-{evidence.evidence_id}-v1"
                artifact_store.put(
                    StoredArtifact(
                        artifact_id=evidence_id,
                        incident_id=state.incident_id,
                        artifact_type="evidence",
                        schema_version=1,
                        content=evidence.model_dump(mode="json"),
                    )
                )
                evidence_artifact_ids.append(evidence_id)
            with_report = with_report.model_copy(
                update={"artifact_references": evidence_artifact_ids}
            )
        if artifact_store is not None:
            artifact_id = f"report-{state.incident_id}-v1"
            artifact_store.put(
                StoredArtifact(
                    artifact_id=artifact_id,
                    incident_id=state.incident_id,
                    artifact_type="report",
                    schema_version=1,
                    content=report.model_dump(mode="json"),
                )
            )
            with_report = with_report.model_copy(
                update={
                    "artifact_references": [
                        *with_report.artifact_references,
                        artifact_id,
                    ]
                }
            )
        if report.status == "failed":
            failed = with_report.model_copy(update={"error": report.summary})
            return transition(failed, LifecycleStatus.FAILED).model_dump()
        return transition(with_report, LifecycleStatus.COMPLETED).model_dump()
    except (RuntimeError, TypeError, ValueError) as exc:
        failed = _failed_state(state, "report synthesis failed", exc)
        return transition(failed, LifecycleStatus.FAILED).model_dump()


def _investigate(
    raw_state: Any,
    investigation_runner: InvestigationRunner | None,
) -> dict[str, Any]:
    state = IncidentGraphState.model_validate(raw_state)
    if state.cancel_requested:
        return transition(state, LifecycleStatus.CANCELLED).model_dump()
    try:
        next_state = transition(state, LifecycleStatus.SYNTHESIZING)
        if investigation_runner is not None:
            next_state = next_state.model_copy(
                update={"specialist_results": investigation_runner(next_state)}
            )
        return next_state.model_dump()
    except (RuntimeError, TypeError, ValueError) as exc:
        failed = _failed_state(state, "investigation failed", exc)
        return transition(failed, LifecycleStatus.FAILED).model_dump()


def _failed_state(
    state: IncidentGraphState,
    fallback_message: str,
    error: Exception,
) -> IncidentGraphState:
    detail = getattr(error, "incident_error", None)
    if not isinstance(detail, IncidentError):
        detail = IncidentError.from_message(
            classification="model_contract_violation",
            retryable=False,
            component="coordinator",
            correlation_id=f"workflow-{state.incident_id}",
            user_message=fallback_message,
        )
    return state.model_copy(
        update={
            "error": detail.user_message,
            "error_detail": detail,
        }
    )


def _route(raw_state: Any) -> str:
    state = IncidentGraphState.model_validate(raw_state)
    routes = {
        LifecycleStatus.TRIAGING: "triage",
        LifecycleStatus.INVESTIGATING: "investigate",
        LifecycleStatus.SYNTHESIZING: "synthesize",
    }
    return routes.get(state.status, "end")
