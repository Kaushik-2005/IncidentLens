import os
from pathlib import Path

import pytest

from incidentlens.baseline import run_baseline
from incidentlens.config import Settings
from incidentlens.contracts import IncidentInput
from incidentlens.model_adapter import GeminiLangChainModelClient
from incidentlens.tools import build_fixture_registry

FIXTURE_PATH = Path("fixtures/incidents/payment_latency.json")


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_GEMINI") != "1",
    reason="set RUN_LIVE_GEMINI=1 to call the external Gemini API",
)
def test_live_gemini_baseline() -> None:
    """Exercise the configured Gemini adapter against synthetic telemetry."""
    settings = Settings()
    if not settings.google_api_key:
        pytest.skip("INCIDENTLENS_GOOGLE_API_KEY is not configured")

    incident = IncidentInput(
        incident_id="payment-latency-001",
        title="Checkout latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency and timeout errors increased.",
    )
    tools = build_fixture_registry(FIXTURE_PATH)
    model = GeminiLangChainModelClient.from_settings(settings=settings, tools=tools)

    artifact, artifact_path = run_baseline(
        incident=incident,
        model=model,
        tools=tools,
        max_steps=settings.max_agent_steps,
        max_model_retries=settings.max_model_retries,
        retry_backoff_base_ms=settings.retry_backoff_base_ms,
        max_retry_delay_ms=settings.max_retry_delay_ms,
        output_dir=Path("artifacts"),
    )

    assert artifact.report.incident_id == incident.incident_id
    assert artifact.metadata.model_calls <= settings.max_agent_steps
    assert artifact_path.exists()
