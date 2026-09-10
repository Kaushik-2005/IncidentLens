import json
from pathlib import Path

from pydantic import BaseModel

from incidentlens.agent_loop import (
    AgentRunMetadata,
    ModelClient,
    run_agent_loop_with_metadata,
)
from incidentlens.contracts import IncidentInput, InvestigationReport
from incidentlens.tools import ToolRegistry


class BaselineArtifact(BaseModel):
    """Durable, provider-neutral output from one baseline investigation run."""

    incident: IncidentInput
    report: InvestigationReport
    metadata: AgentRunMetadata


def run_baseline(
    *,
    incident: IncidentInput,
    model: ModelClient,
    tools: ToolRegistry,
    max_steps: int,
    max_model_retries: int = 0,
    retry_backoff_base_ms: int = 0,
    max_retry_delay_ms: int = 2000,
    output_dir: str | Path,
) -> tuple[BaselineArtifact, Path]:
    """Run the baseline and save its validated report and measurements as JSON."""
    result = run_agent_loop_with_metadata(
        incident=incident,
        model=model,
        tools=tools,
        max_steps=max_steps,
        max_model_retries=max_model_retries,
        retry_backoff_base_ms=retry_backoff_base_ms,
        max_retry_delay_ms=max_retry_delay_ms,
    )
    artifact = BaselineArtifact(
        incident=incident,
        report=result.report,
        metadata=result.metadata,
    )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    artifact_path = destination / f"baseline-{incident.incident_id}.json"
    artifact_path.write_text(
        json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact, artifact_path


def require_api_key(api_key: str | None) -> str:
    """Return a configured API key or fail before constructing a live client."""
    if not api_key:
        raise RuntimeError("live Gemini execution requires a configured API key")
    return api_key
