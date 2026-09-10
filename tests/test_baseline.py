import json
from pathlib import Path
from typing import Any

from incidentlens.baseline import require_api_key, run_baseline
from incidentlens.contracts import (
    Confidence,
    Evidence,
    Hypothesis,
    IncidentInput,
    InvestigationReport,
    ModelFinalReport,
    ModelToolRequest,
    ToolCall,
)
from incidentlens.tools import build_fixture_registry

FIXTURE_PATH = Path("fixtures/incidents/payment_latency.json")


class ScriptedModel:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses

    def invoke(self, incident: IncidentInput, observations: list[Any]) -> Any:
        return self.responses.pop(0)


def test_run_baseline_saves_report_and_metadata(tmp_path: Path) -> None:
    incident = IncidentInput(
        incident_id="payment-latency-001",
        title="Checkout latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency and timeout errors increased.",
    )
    evidence = [
        Evidence(evidence_id="E1", source="metric", summary="Latency rose."),
    ]
    model = ScriptedModel(
        [
            ModelToolRequest(
                tool_call=ToolCall(
                    name="lookup_incident_fixture",
                    arguments={"incident_id": incident.incident_id},
                )
            ),
            ModelFinalReport(
                report=InvestigationReport(
                    incident_id=incident.incident_id,
                    summary="The fixture confirms the latency symptom.",
                    evidence=evidence,
                    hypotheses=[
                        Hypothesis(
                            statement="Latency increased during the incident window.",
                            confidence=Confidence.MEDIUM,
                            supporting_evidence_ids=["E1"],
                        )
                    ],
                    status="completed",
                )
            ),
        ]
    )

    artifact, artifact_path = run_baseline(
        incident=incident,
        model=model,
        tools=build_fixture_registry(FIXTURE_PATH),
        max_steps=3,
        output_dir=tmp_path / "artifacts",
    )

    saved = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact.report.summary == saved["report"]["summary"]
    assert saved["metadata"]["model_calls"] == 2
    assert saved["metadata"]["tool_calls"] == 1
    assert saved["metadata"]["total_tokens"] is None


def test_live_baseline_requires_api_key() -> None:
    try:
        require_api_key(None)
    except RuntimeError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("missing API key should prevent live execution")
