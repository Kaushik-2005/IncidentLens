import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from incidentlens.agent_loop import (
    ModelProviderError,
    ProviderFailureKind,
    run_agent_loop,
)
from incidentlens.contracts import IncidentInput, ToolCall, ToolObservation
from incidentlens.model_adapter import (
    GeminiLangChainModelClient,
    _provider_error_to_incident_error,
)
from incidentlens.tools import build_fixture_registry

FIXTURE_PATH = "fixtures/incidents/payment_latency.json"


class FakeChatModel:
    def __init__(self, response: AIMessage) -> None:
        self.response = response
        self.messages: list[BaseMessage] | None = None

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        self.messages = messages
        return self.response


class FakeBindableChatModel(FakeChatModel):
    def __init__(self, response: AIMessage) -> None:
        super().__init__(response)
        self.bound_tools: list[dict[str, Any]] | None = None

    def bind_tools(self, tools: list[dict[str, Any]]) -> "FakeBindableChatModel":
        self.bound_tools = tools
        return self


def incident() -> IncidentInput:
    return IncidentInput(
        incident_id="payment-latency-001",
        title="Checkout latency spike",
        affected_service="checkout-api",
        start_time="2026-09-10T10:05:00Z",
        summary="Checkout latency and timeout errors increased.",
    )


def test_adapter_parses_langchain_tool_call() -> None:
    fake_model = FakeChatModel(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "lookup_incident_fixture",
                    "args": {"incident_id": "payment-latency-001"},
                    "id": "call-1",
                }
            ],
        )
    )
    adapter = GeminiLangChainModelClient(chat_model=fake_model)

    response = adapter.invoke(incident(), [])

    assert response == {
        "kind": "tool_request",
        "tool_call": {
            "name": "lookup_incident_fixture",
            "arguments": {"incident_id": "payment-latency-001"},
            "call_id": "call-1",
        },
    }
    assert fake_model.messages is not None
    assert "payment-latency-001" in str(fake_model.messages[-1].content)


def test_adapter_parses_json_final_report_content() -> None:
    report_payload = {
        "kind": "final_report",
        "report": {
            "incident_id": "payment-latency-001",
            "summary": "Checkout latency is consistent with payment-service timeouts.",
            "evidence": [{"evidence_id": "E1", "source": "metric", "summary": "Latency rose."}],
            "hypotheses": [
                {
                    "statement": "payment-service latency contributed to checkout latency.",
                    "confidence": "medium",
                    "supporting_evidence_ids": ["E1"],
                    "contradicting_evidence_ids": [],
                }
            ],
            "status": "completed",
        },
    }
    fake_model = FakeChatModel(AIMessage(content=json.dumps(report_payload)))
    adapter = GeminiLangChainModelClient(chat_model=fake_model)

    response = adapter.invoke(incident(), [])

    assert response == report_payload


def test_adapter_can_drive_agent_loop_with_fake_chat_model() -> None:
    tools = build_fixture_registry(FIXTURE_PATH)
    report_payload = {
        "kind": "final_report",
        "report": {
            "incident_id": "payment-latency-001",
            "summary": "Checkout latency is consistent with payment-service timeouts.",
            "evidence": [{"evidence_id": "E1", "source": "metric", "summary": "Latency rose."}],
            "hypotheses": [
                {
                    "statement": "payment-service latency contributed to checkout latency.",
                    "confidence": "medium",
                    "supporting_evidence_ids": ["E1"],
                    "contradicting_evidence_ids": [],
                }
            ],
            "status": "completed",
        },
    }
    adapter = GeminiLangChainModelClient(
        chat_model=FakeChatModel(AIMessage(content=json.dumps(report_payload)))
    )

    report = run_agent_loop(incident=incident(), model=adapter, tools=tools, max_steps=1)

    assert report.status == "completed"


def test_bindable_chat_model_records_tool_schemas() -> None:
    tools = build_fixture_registry(FIXTURE_PATH)
    fake_model = FakeBindableChatModel(AIMessage(content="{}"))

    bound_model = fake_model.bind_tools(tools.model_tool_schemas())

    assert bound_model.bound_tools is not None
    assert bound_model.bound_tools[0]["name"] == "lookup_incident_fixture"


def test_adapter_builds_tool_result_message_with_call_id() -> None:
    fake_model = FakeChatModel(AIMessage(content="{}"))
    adapter = GeminiLangChainModelClient(chat_model=fake_model)

    adapter.invoke(
        incident(),
        [
            ToolObservation(
                tool_call=ToolCall(
                    name="lookup_incident_fixture",
                    arguments={"incident_id": "payment-latency-001"},
                    call_id="call-1",
                ),
                result={
                    "incident_id": "payment-latency-001",
                    "evidence": [],
                    "truncated": False,
                },
            )
        ],
    )

    assert fake_model.messages is not None
    assert isinstance(fake_model.messages[-1], ToolMessage)
    assert fake_model.messages[-1].tool_call_id == "call-1"


def test_adapter_parses_structured_text_content() -> None:
    payload = {
        "kind": "final_report",
        "report": {
            "incident_id": "payment-latency-001",
            "summary": "Structured content report.",
            "evidence": [{"evidence_id": "E1", "source": "metric", "summary": "Latency rose."}],
            "hypotheses": [
                {
                    "statement": "Latency increased.",
                    "confidence": "medium",
                    "supporting_evidence_ids": ["E1"],
                    "contradicting_evidence_ids": [],
                }
            ],
            "status": "completed",
        },
    }
    adapter = GeminiLangChainModelClient(
        chat_model=FakeChatModel(AIMessage(content=[{"type": "text", "text": json.dumps(payload)}]))
    )

    assert adapter.invoke(incident(), []) == payload


def test_adapter_extracts_langchain_usage_metadata() -> None:
    payload = {
        "kind": "final_report",
        "report": {
            "incident_id": "payment-latency-001",
            "summary": "Usage metadata report.",
            "evidence": [{"evidence_id": "E1", "source": "metric", "summary": "Latency rose."}],
            "hypotheses": [
                {
                    "statement": "Latency increased.",
                    "confidence": "medium",
                    "supporting_evidence_ids": ["E1"],
                    "contradicting_evidence_ids": [],
                }
            ],
            "status": "completed",
        },
    }
    adapter = GeminiLangChainModelClient(
        chat_model=FakeChatModel(
            AIMessage(
                content=json.dumps(payload),
                usage_metadata={
                    "input_tokens": 12,
                    "output_tokens": 8,
                    "total_tokens": 20,
                },
            )
        )
    )

    adapter.invoke(incident(), [])

    assert adapter.last_usage == {
        "input_tokens": 12,
        "output_tokens": 8,
        "total_tokens": 20,
    }


class TemporaryProviderFailure(Exception):
    status_code = 503


class FailingChatModel:
    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        raise TemporaryProviderFailure()


def test_adapter_normalizes_retryable_provider_failure() -> None:
    adapter = GeminiLangChainModelClient(chat_model=FailingChatModel())

    try:
        adapter.invoke(incident(), [])
    except ModelProviderError as exc:
        assert exc.retryable is True
    else:
        raise AssertionError("provider failure should be normalized")


def test_adapter_parses_fenced_bare_report() -> None:
    report = {
        "incident_id": "payment-latency-001",
        "summary": "Checkout latency increased.",
        "evidence": [{"evidence_id": "E1", "source": "metric", "summary": "Latency rose."}],
        "hypotheses": [
            {
                "statement": "Latency increased during the incident window.",
                "confidence": "medium",
                "supporting_evidence_ids": ["E1"],
                "contradicting_evidence_ids": [],
            }
        ],
        "status": "completed",
    }
    fenced = "```json\n" + json.dumps(report) + "\n```"
    adapter = GeminiLangChainModelClient(chat_model=FakeChatModel(AIMessage(content=fenced)))

    response = adapter.invoke(incident(), [])

    assert response == {"kind": "final_report", "report": report}


def test_provider_503_maps_to_sanitized_incident_error() -> None:
    error = _provider_error_to_incident_error(
        failure_kind=ProviderFailureKind.SERVICE_UNAVAILABLE,
        attempt_count=1,
    )

    assert error.classification == "service_unavailable"
    assert error.retryable is True
    assert error.component == "model_provider"
    assert error.attempt_count == 1
    assert "temporarily unavailable" in error.user_message


def test_provider_timeout_maps_to_dependency_timeout() -> None:
    error = _provider_error_to_incident_error(
        failure_kind=ProviderFailureKind.TIMEOUT,
        attempt_count=2,
    )

    assert error.classification == "dependency_timeout"
    assert error.retryable is True
    assert error.attempt_count == 2
    assert error.user_message == "The model service timed out."


def test_unknown_provider_failure_is_terminal_and_sanitized() -> None:
    error = _provider_error_to_incident_error(
        failure_kind=None,
        attempt_count=1,
    )

    assert error.retryable is False
    assert error.component == "model_provider"
    assert "provider" not in error.user_message.lower()
