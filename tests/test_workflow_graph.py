from langgraph.checkpoint.memory import InMemorySaver

from incidentlens.contracts import Evidence, Hypothesis, InvestigationReport
from incidentlens.parallel_investigation import SpecialistBranchResult
from incidentlens.persistence import ArtifactStore
from incidentlens.specialists import SpecialistRole
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


def test_graph_resumes_from_checkpoint_without_restarting_completed_nodes(
    tmp_path,
) -> None:
    checkpointer = InMemorySaver()
    artifact_store = ArtifactStore(tmp_path / "artifacts")
    graph = build_incident_graph(
        report_factory,
        checkpointer=checkpointer,
        interrupt_before=["investigate"],
        artifact_store=artifact_store,
    )
    config = {
        "configurable": {
            "thread_id": "incident-001",
        }
    }

    paused = graph.invoke(
        {"incident_id": "incident-001"},
        config=config,
    )

    assert paused["status"] == LifecycleStatus.INVESTIGATING
    assert paused["current_node"] == "investigating"
    assert paused["report"] is None

    resumed = graph.invoke(None, config=config)

    assert resumed["status"] == LifecycleStatus.COMPLETED
    assert resumed["artifact_references"] == [
        "evidence-incident-001-E1-v1",
        "report-incident-001-v1",
    ]

    saved_report = artifact_store.load(
        "report-incident-001-v1",
        "incident-001",
    )

    assert saved_report.content["incident_id"] == "incident-001"

    resumed_again = graph.invoke(None, config=config)

    assert resumed_again["status"] == LifecycleStatus.COMPLETED
    assert resumed_again["artifact_references"] == [
        "evidence-incident-001-E1-v1",
        "report-incident-001-v1",
    ]
    assert len(list((tmp_path / "artifacts").glob("*.json"))) == 2


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


def test_graph_downgrades_report_when_specialist_coverage_is_partial() -> None:
    def partial_runner(_state):
        return [
            SpecialistBranchResult(role=SpecialistRole.LOGS, status="success"),
            SpecialistBranchResult(
                role=SpecialistRole.METRICS,
                status="failed",
                error="dependency circuit open",
            ),
        ]

    result = build_incident_graph(
        report_factory,
        investigation_runner=partial_runner,
    ).invoke({"incident_id": "incident-001"})

    assert result["status"] == LifecycleStatus.COMPLETED
    assert result["report"]["status"] == "inconclusive"
    assert "metrics_agent" in result["report"]["summary"]


def test_graph_fails_when_no_specialist_coverage_exists() -> None:
    def failed_runner(_state):
        return [
            SpecialistBranchResult(role=SpecialistRole.LOGS, status="failed"),
            SpecialistBranchResult(role=SpecialistRole.METRICS, status="timeout"),
        ]

    result = build_incident_graph(
        report_factory,
        investigation_runner=failed_runner,
    ).invoke({"incident_id": "incident-001"})

    assert result["status"] == LifecycleStatus.FAILED
    assert "No specialist evidence was available" in result["error"]


def test_graph_downgrades_report_with_unresolved_evidence_requirement() -> None:
    def unsupported_factory(_state):
        report = report_factory(_state)
        hypothesis = report.hypotheses[0].model_copy(
            update={"missing_evidence": ["metric saturation evidence"]}
        )
        return report.model_copy(update={"hypotheses": [hypothesis]})

    result = build_incident_graph(unsupported_factory).invoke({"incident_id": "incident-001"})

    assert result["status"] == LifecycleStatus.COMPLETED
    assert result["report"]["status"] == "inconclusive"
    assert "unresolved evidence" in result["report"]["summary"]


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
