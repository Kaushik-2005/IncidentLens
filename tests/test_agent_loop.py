from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from incidentlens.agent_loop import (
    InvalidModelResponseError,
    MaxStepsExceededError,
    ModelBudgetExhaustedError,
    ModelProviderError,
    ProviderFailureKind,
    run_agent_loop,
    run_agent_loop_with_metadata,
)
from incidentlens.contracts import (
    Confidence,
    Evidence,
    Hypothesis,
    IncidentInput,
    InvestigationReport,
    ModelFinalReport,
    ModelResponse,
    ModelToolRequest,
    ToolCall,
)
from incidentlens.coordination import BudgetLedger
from incidentlens.errors import IncidentError
from incidentlens.tools import ToolExecutionError, UnknownToolError, build_fixture_registry

FIXTURE_PATH = Path("fixtures/incidents/payment_latency.json")


class ScriptedModel:
    def __init__(self, responses: Iterable[ModelResponse | dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def invoke(self, incident: IncidentInput, observations: list[BaseModel]) -> Any:
        self.calls += 1
        return self._responses.pop(0)


def incident() -> IncidentInput:
    return IncidentInput(
        incident_id="payment-latency-001",
        title="Checkout latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency and timeout errors increased.",
    )


def test_shared_model_budget_blocks_invocation_before_retry_or_provider_call() -> None:
    model = ScriptedModel([])
    budget = BudgetLedger(max_model_calls=0, max_tool_calls=5)

    with pytest.raises(ModelBudgetExhaustedError) as exc_info:
        run_agent_loop_with_metadata(
            incident=incident(),
            model=model,
            tools=build_fixture_registry(FIXTURE_PATH),
            max_steps=3,
            max_model_retries=2,
            model_budget=budget,
        )

    assert model.calls == 0
    assert budget.model_calls == 0
    assert exc_info.value.incident_error.classification == "model_budget_exhausted"


def final_report(evidence: list[Evidence]) -> ModelFinalReport:
    return ModelFinalReport(
        report=InvestigationReport(
            incident_id="payment-latency-001",
            summary="Checkout latency is most consistent with payment-service timeouts.",
            evidence=evidence,
            hypotheses=[
                Hypothesis(
                    statement="payment-service dependency latency caused checkout-api latency.",
                    confidence=Confidence.HIGH,
                    supporting_evidence_ids=["E1", "E2", "E3"],
                )
            ],
            status="completed",
        )
    )


def test_agent_loop_executes_tool_then_returns_final_report() -> None:
    tools = build_fixture_registry(FIXTURE_PATH)
    model = ScriptedModel(
        [
            ModelToolRequest(
                tool_call=ToolCall(
                    name="lookup_incident_fixture",
                    arguments={"incident_id": "payment-latency-001"},
                )
            ),
            final_report(
                [
                    Evidence(
                        evidence_id="E1",
                        source="metric",
                        summary="checkout-api latency rose sharply.",
                    ),
                    Evidence(
                        evidence_id="E2",
                        source="log",
                        summary="checkout-api emitted payment timeout errors.",
                    ),
                    Evidence(
                        evidence_id="E3",
                        source="trace",
                        summary="traces show latency in payment-service calls.",
                    ),
                ]
            ),
        ]
    )

    report = run_agent_loop(incident=incident(), model=model, tools=tools, max_steps=3)

    assert report.status == "completed"
    assert report.hypotheses[0].supporting_evidence_ids == ["E1", "E2", "E3"]
    assert model.calls == 2


def test_agent_loop_result_includes_application_measured_metadata() -> None:
    tools = build_fixture_registry(FIXTURE_PATH)
    model = ScriptedModel(
        [
            ModelToolRequest(
                tool_call=ToolCall(
                    name="lookup_incident_fixture",
                    arguments={"incident_id": "payment-latency-001"},
                )
            ),
            final_report(
                [
                    Evidence(
                        evidence_id="E1",
                        source="metric",
                        summary="checkout-api latency rose sharply.",
                    ),
                    Evidence(
                        evidence_id="E2",
                        source="log",
                        summary="checkout-api emitted payment timeout errors.",
                    ),
                    Evidence(
                        evidence_id="E3",
                        source="trace",
                        summary="traces show latency in payment-service calls.",
                    ),
                ]
            ),
        ]
    )

    result = run_agent_loop_with_metadata(
        incident=incident(), model=model, tools=tools, max_steps=3
    )

    assert result.report.status == "completed"
    assert result.metadata.model_calls == 2
    assert result.metadata.tool_calls == 1
    assert result.metadata.elapsed_ms >= 0
    assert result.metadata.total_tokens is None


def test_unknown_tool_request_fails_before_execution() -> None:
    tools = build_fixture_registry(FIXTURE_PATH)
    model = ScriptedModel(
        [ModelToolRequest(tool_call=ToolCall(name="delete_database", arguments={"confirm": True}))]
    )

    with pytest.raises(UnknownToolError):
        run_agent_loop(incident=incident(), model=model, tools=tools, max_steps=1)


def test_malformed_tool_arguments_fail_validation() -> None:
    tools = build_fixture_registry(FIXTURE_PATH)
    model = ScriptedModel(
        [
            ModelToolRequest(
                tool_call=ToolCall(name="lookup_incident_fixture", arguments={"incident_id": ""})
            )
        ]
    )

    with pytest.raises(ValidationError):
        run_agent_loop(incident=incident(), model=model, tools=tools, max_steps=1)


def test_malformed_model_response_fails_before_tool_execution() -> None:
    tools = build_fixture_registry(FIXTURE_PATH)
    model = ScriptedModel(
        [{"kind": "tool_request", "tool_call": {"name": "lookup_incident_fixture"}}]
    )

    with pytest.raises(InvalidModelResponseError):
        run_agent_loop(incident=incident(), model=model, tools=tools, max_steps=1)


def test_tool_execution_error_propagates_from_permitted_tool() -> None:
    tools = build_fixture_registry(FIXTURE_PATH)
    model = ScriptedModel(
        [
            ModelToolRequest(
                tool_call=ToolCall(
                    name="lookup_incident_fixture",
                    arguments={"incident_id": "missing-incident"},
                )
            )
        ]
    )

    with pytest.raises(ToolExecutionError):
        run_agent_loop(incident=incident(), model=model, tools=tools, max_steps=1)


def test_max_steps_terminates_loop() -> None:
    tools = build_fixture_registry(FIXTURE_PATH)
    model = ScriptedModel(
        [
            ModelToolRequest(
                tool_call=ToolCall(
                    name="lookup_incident_fixture",
                    arguments={"incident_id": "payment-latency-001"},
                )
            ),
            ModelToolRequest(
                tool_call=ToolCall(
                    name="lookup_incident_fixture",
                    arguments={"incident_id": "payment-latency-001"},
                )
            ),
        ]
    )

    with pytest.raises(MaxStepsExceededError):
        run_agent_loop(incident=incident(), model=model, tools=tools, max_steps=2)


def test_structured_report_rejects_unknown_evidence_id() -> None:
    with pytest.raises(ValidationError):
        InvestigationReport(
            incident_id="payment-latency-001",
            summary="Unsupported report.",
            evidence=[
                Evidence(evidence_id="E1", source="metric", summary="Latency rose."),
            ],
            hypotheses=[
                Hypothesis(
                    statement="A cause with an invalid citation.",
                    confidence=Confidence.MEDIUM,
                    supporting_evidence_ids=["E999"],
                )
            ],
            status="completed",
        )


class RetryThenReportModel:
    def __init__(self) -> None:
        self.calls = 0
        self.last_usage: dict[str, int] | None = None

    def invoke(self, incident: IncidentInput, observations: list[BaseModel]) -> Any:
        self.calls += 1
        if self.calls == 1:
            raise ModelProviderError(
                "temporary provider outage",
                retryable=True,
                failure_kind=ProviderFailureKind.SERVICE_UNAVAILABLE,
            )
        self.last_usage = {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        }
        return final_report(
            [
                Evidence(evidence_id="E1", source="metric", summary="Latency rose."),
                Evidence(evidence_id="E2", source="log", summary="Timeouts occurred."),
                Evidence(evidence_id="E3", source="trace", summary="Dependency was slow."),
            ]
        )


def test_retryable_provider_failure_is_capped_and_counted() -> None:
    model = RetryThenReportModel()
    result = run_agent_loop_with_metadata(
        incident=incident(),
        model=model,
        tools=build_fixture_registry(FIXTURE_PATH),
        max_steps=2,
        max_model_retries=1,
        retry_backoff_base_ms=100,
        max_retry_delay_ms=150,
    )

    assert result.report.status == "completed"
    assert result.metadata.model_calls == 2
    assert result.metadata.model_retries == 1
    assert result.metadata.input_tokens == 10
    assert result.metadata.output_tokens == 5
    assert result.metadata.total_tokens == 15
    assert result.metadata.provider_retry.attempts == 2
    assert result.metadata.provider_retry.retries == 1
    assert result.metadata.provider_retry.retryable_failures == [
        ProviderFailureKind.SERVICE_UNAVAILABLE
    ]
    assert result.metadata.provider_retry.retry_delays_ms == [100]


def test_retryable_provider_failure_without_budget_propagates() -> None:
    model = RetryThenReportModel()

    with pytest.raises(ModelProviderError):
        run_agent_loop_with_metadata(
            incident=incident(),
            model=model,
            tools=build_fixture_registry(FIXTURE_PATH),
            max_steps=1,
            max_model_retries=0,
        )


class AlwaysFailingModel:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, incident: IncidentInput, observations: list[BaseModel]) -> Any:
        self.calls += 1
        raise ModelProviderError(
            "temporary provider outage",
            retryable=True,
            failure_kind=ProviderFailureKind.SERVICE_UNAVAILABLE,
            incident_error=IncidentError(
                classification="service_unavailable",
                retryable=True,
                component="model_provider",
                correlation_id="err-exhausted-1",
                user_message="The model service is temporarily unavailable.",
            ),
        )


def test_exhausted_provider_failure_preserves_cumulative_incident_error() -> None:
    model = AlwaysFailingModel()

    with pytest.raises(ModelProviderError) as raised:
        run_agent_loop_with_metadata(
            incident=incident(),
            model=model,
            tools=build_fixture_registry(FIXTURE_PATH),
            max_steps=2,
            max_model_retries=1,
        )

    assert model.calls == 2
    assert raised.value.incident_error is not None
    assert raised.value.incident_error.attempt_count == 2
    assert raised.value.incident_error.classification == "service_unavailable"


def test_many_investigations_cannot_create_unbounded_retry_storm() -> None:
    models = [AlwaysFailingModel() for _ in range(20)]

    for model in models:
        with pytest.raises(ModelProviderError):
            run_agent_loop_with_metadata(
                incident=incident(),
                model=model,
                tools=build_fixture_registry(FIXTURE_PATH),
                max_steps=2,
                max_model_retries=1,
            )

    assert sum(model.calls for model in models) == 40
    assert all(model.calls <= 2 for model in models)
