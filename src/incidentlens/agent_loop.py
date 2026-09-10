from enum import StrEnum
from time import perf_counter, sleep
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from incidentlens.contracts import (
    IncidentInput,
    InvestigationReport,
    ModelFinalReport,
    ModelResponse,
    ModelResponseAdapter,
    ToolCall,
    ToolObservation,
)
from incidentlens.tools import ToolRegistry


class AgentLoopError(RuntimeError):
    """Base class for deterministic agent-loop failures."""


class InvalidModelResponseError(AgentLoopError):
    """Raised when a model response does not match the expected contract."""


class ProviderFailureKind(StrEnum):
    RATE_LIMITED = "rate_limited"
    SERVICE_UNAVAILABLE = "service_unavailable"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"


class ProviderRetryMetadata(BaseModel):
    attempts: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    retryable_failures: list[ProviderFailureKind] = Field(default_factory=list)
    retry_delays_ms: list[int] = Field(default_factory=list, min_length=0)


class ModelProviderError(AgentLoopError):
    """Raised when the model provider fails before returning a response."""

    def __init__(
        self, message: str, *, retryable: bool, failure_kind: ProviderFailureKind | None = None
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.failure_kind = failure_kind


class MaxStepsExceededError(AgentLoopError):
    """Raised when the model never reaches a final report within the step budget."""


class ModelClient(Protocol):
    def invoke(self, incident: IncidentInput, observations: list[BaseModel]) -> Any:
        """Return the model's next raw tool request or final report."""


class AgentRunMetadata(BaseModel):
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    elapsed_ms: float = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    model_retries: int = Field(default=0, ge=0)
    provider_retry: ProviderRetryMetadata = Field(default_factory=ProviderRetryMetadata)


class AgentRunResult(BaseModel):
    report: InvestigationReport
    metadata: AgentRunMetadata


def validate_model_response(raw_response: Any) -> ModelResponse:
    try:
        return ModelResponseAdapter.validate_python(raw_response)
    except ValidationError as exc:
        raise InvalidModelResponseError("model response did not match expected schema") from exc


def run_agent_loop(
    *,
    incident: IncidentInput,
    model: ModelClient,
    tools: ToolRegistry,
    max_steps: int,
) -> InvestigationReport:
    return run_agent_loop_with_metadata(
        incident=incident,
        model=model,
        tools=tools,
        max_steps=max_steps,
    ).report


def run_agent_loop_with_metadata(
    *,
    incident: IncidentInput,
    model: ModelClient,
    tools: ToolRegistry,
    max_steps: int,
    max_model_retries: int = 0,
    retry_backoff_base_ms: int = 0,
    max_retry_delay_ms: int = 2000,
) -> AgentRunResult:
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")
    if max_model_retries < 0:
        raise ValueError("max_model_retries cannot be negative")
    if retry_backoff_base_ms < 0 or max_retry_delay_ms < 0:
        raise ValueError("retry delay settings cannot be negative")
    if retry_backoff_base_ms > max_retry_delay_ms:
        raise ValueError("retry_backoff_base_ms cannot exceed max_retry_delay_ms")

    observations: list[BaseModel] = []
    started_at = perf_counter()
    model_calls = 0
    model_retries = 0
    provider_retry = ProviderRetryMetadata()
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    usage_seen: set[str] = set()

    while model_calls < max_steps:
        model_calls += 1
        try:
            raw_response = model.invoke(incident, observations)
            provider_retry.attempts = model_calls
        except ModelProviderError as exc:
            provider_retry.attempts = model_calls
            if exc.retryable and model_retries < max_model_retries:
                delay_ms = min(retry_backoff_base_ms * (2**model_retries), max_retry_delay_ms)
                provider_retry.retries += 1
                if exc.failure_kind is not None:
                    provider_retry.retryable_failures.append(exc.failure_kind)
                provider_retry.retry_delays_ms.append(delay_ms)
                model_retries += 1
                if delay_ms:
                    sleep(delay_ms / 1000)
                continue
            raise

        _merge_usage(
            totals=usage_totals,
            seen=usage_seen,
            usage=getattr(model, "last_usage", None),
        )
        response = validate_model_response(raw_response)
        if isinstance(response, ModelFinalReport):
            return AgentRunResult(
                report=response.report,
                metadata=AgentRunMetadata(
                    model_calls=model_calls,
                    tool_calls=len(observations),
                    elapsed_ms=(perf_counter() - started_at) * 1000,
                    input_tokens=(
                        usage_totals["input_tokens"] if "input_tokens" in usage_seen else None
                    ),
                    output_tokens=(
                        usage_totals["output_tokens"] if "output_tokens" in usage_seen else None
                    ),
                    total_tokens=(
                        usage_totals["total_tokens"] if "total_tokens" in usage_seen else None
                    ),
                    model_retries=model_retries,
                    provider_retry=provider_retry,
                ),
            )

        result = tools.execute(response.tool_call.name, response.tool_call.arguments)
        observations.append(
            ToolObservation(
                tool_call=ToolCall(
                    name=response.tool_call.name,
                    arguments=response.tool_call.arguments,
                    call_id=response.tool_call.call_id or f"tool-call-{model_calls}",
                ),
                result=result.model_dump(),
            )
        )

    raise MaxStepsExceededError(f"agent did not produce a final report within {max_steps} steps")


def _merge_usage(
    *,
    totals: dict[str, int],
    seen: set[str],
    usage: Any,
) -> None:
    if not isinstance(usage, dict):
        return
    for field in totals:
        value = usage.get(field)
        if isinstance(value, int) and value >= 0:
            totals[field] += value
            seen.add(field)
