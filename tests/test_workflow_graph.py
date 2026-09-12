from incidentlens.contracts import Evidence, Hypothesis, InvestigationReport
from incidentlens.workflow_graph import build_incident_graph
from incidentlens.workflow_state import LifecycleStatus


def report_factory(state):
    return InvestigationReport(
        incident_id=state.incident_id,
        summary="Investigation completed.",
        evidence=[Evidence(evidence_id="E1", source="metric", summary="Latency rose.")],
        hypotheses=[
            Hypothesis(
                statement="A dependency became slow.",
                confidence="medium",
                supporting_evidence_ids=["E1"],
            )
        ],
        status="completed",
    )


def test_graph_runs_normal_lifecycle() -> None:
    result = build_incident_graph(report_factory).invoke({"incident_id": "incident-001"})

    assert result["status"] == LifecycleStatus.COMPLETED
    assert result["report"]["incident_id"] == "incident-001"
    assert result["current_node"] is None


def test_graph_cancels_before_work() -> None:
    result = build_incident_graph(report_factory).invoke(
        {"incident_id": "incident-001", "cancel_requested": True}
    )

    assert result["status"] == LifecycleStatus.CANCELLED
    assert result["report"] is None


def test_graph_fails_when_report_factory_errors() -> None:
    def broken_factory(_state):
        raise RuntimeError("provider details must not enter state")

    result = build_incident_graph(broken_factory).invoke({"incident_id": "incident-001"})

    assert result["status"] == LifecycleStatus.FAILED
    assert result["error"] == "report synthesis failed"


def test_graph_rejects_invalid_initial_transition() -> None:
    result = build_incident_graph(report_factory).invoke(
        {"incident_id": "incident-001", "status": LifecycleStatus.INVESTIGATING}
    )

    assert result["status"] == LifecycleStatus.FAILED
    assert result["error"] == "invalid lifecycle transition"


def test_graph_execution_exposes_expected_node_sequence() -> None:
    updates = list(
        build_incident_graph(report_factory).stream(
            {"incident_id": "incident-001"},
            stream_mode="updates",
        )
    )

    assert [next(iter(update)) for update in updates] == [
        "validate",
        "triage",
        "investigate",
        "synthesize",
    ]
