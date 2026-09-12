from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from incidentlens.contracts import InvestigationReport
from incidentlens.workflow_state import (
    IncidentGraphState,
    InvalidTransitionError,
    LifecycleStatus,
    transition,
)

ReportFactory = Callable[[IncidentGraphState], InvestigationReport]


def build_incident_graph(report_factory: ReportFactory) -> Any:
    """Build a deterministic lifecycle graph with an injected report producer."""
    graph = StateGraph(IncidentGraphState)
    graph.add_node("validate", _node_to(LifecycleStatus.TRIAGING))
    graph.add_node("triage", _node_to(LifecycleStatus.INVESTIGATING))
    graph.add_node("investigate", _node_to(LifecycleStatus.SYNTHESIZING))
    graph.add_node("synthesize", lambda state: _synthesize(state, report_factory))

    graph.add_edge(START, "validate")
    graph.add_conditional_edges("validate", _route, {"triage": "triage", "end": END})
    graph.add_conditional_edges("triage", _route, {"investigate": "investigate", "end": END})
    graph.add_conditional_edges("investigate", _route, {"synthesize": "synthesize", "end": END})
    graph.add_conditional_edges("synthesize", _route, {"end": END})
    return graph.compile()


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


def _synthesize(raw_state: Any, report_factory: ReportFactory) -> dict[str, Any]:
    state = IncidentGraphState.model_validate(raw_state)
    if state.cancel_requested:
        return transition(state, LifecycleStatus.CANCELLED).model_dump()
    try:
        report = InvestigationReport.model_validate(report_factory(state))
        if report.incident_id != state.incident_id:
            raise ValueError("report incident does not match active incident")
        with_report = state.model_copy(update={"report": report})
        return transition(with_report, LifecycleStatus.COMPLETED).model_dump()
    except (RuntimeError, TypeError, ValueError):
        failed = state.model_copy(update={"error": "report synthesis failed"})
        return transition(failed, LifecycleStatus.FAILED).model_dump()


def _route(raw_state: Any) -> str:
    state = IncidentGraphState.model_validate(raw_state)
    routes = {
        LifecycleStatus.TRIAGING: "triage",
        LifecycleStatus.INVESTIGATING: "investigate",
        LifecycleStatus.SYNTHESIZING: "synthesize",
    }
    return routes.get(state.status, "end")
