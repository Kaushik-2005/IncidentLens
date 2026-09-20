import json
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from incidentlens.agent_loop import ModelProviderError, ProviderFailureKind
from incidentlens.config import Settings
from incidentlens.contracts import IncidentInput, ToolObservation
from incidentlens.errors import IncidentError
from incidentlens.tools import ToolRegistry


class ChatModel(Protocol):
    def invoke(self, messages: list[BaseMessage]) -> Any:
        """Invoke a chat model with LangChain messages."""


@runtime_checkable
class BindableChatModel(ChatModel, Protocol):
    def bind_tools(
        self,
        tools: list[dict[str, Any]],
    ) -> ChatModel:
        """Return a chat model configured with tool schemas."""


class GeminiLangChainModelClient:
    """Gemini-backed ModelClient adapter using LangChain at the integration edge."""

    def __init__(
        self,
        *,
        chat_model: ChatModel,
        system_instruction: str | None = None,
    ) -> None:
        self._chat_model = chat_model
        self._system_instruction = system_instruction or DEFAULT_SYSTEM_INSTRUCTION
        self._assistant_messages: list[AIMessage] = []
        self.last_usage: dict[str, int] | None = None

    @classmethod
    def from_settings(
        cls, *, settings: Settings, tools: ToolRegistry
    ) -> "GeminiLangChainModelClient":
        chat_model: ChatModel = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            api_key=settings.google_api_key,
            temperature=0,
            max_retries=0,
        )
        if isinstance(chat_model, BindableChatModel):
            chat_model = chat_model.bind_tools(tools.model_tool_schemas())
        return cls(chat_model=chat_model)

    def invoke(self, incident: IncidentInput, observations: list[Any]) -> dict[str, Any]:
        if not observations:
            self._assistant_messages = []
        try:
            response = self._chat_model.invoke(
                _build_messages(
                    incident,
                    observations,
                    self._system_instruction,
                    self._assistant_messages,
                )
            )
        except Exception as exc:  # noqa: BLE001 - provider SDK exception types vary
            failure_kind = _classify_provider_error(exc)
            incident_error = _provider_error_to_incident_error(
                failure_kind=failure_kind,
                attempt_count=1,
            )
            raise ModelProviderError(
                "Model provider invocation failed",
                retryable=(failure_kind is not None),
                failure_kind=failure_kind,
                incident_error=incident_error,
            ) from None
        self.last_usage = _extract_usage(response)
        if isinstance(response, AIMessage) and response.tool_calls:
            self._assistant_messages.append(response)
        return _parse_langchain_response(response)


DEFAULT_SYSTEM_INSTRUCTION = """You are the IncidentLens single-agent baseline.
Request at most one declared tool at a time, or return a final report.
For a final report, return ONLY this JSON object with no Markdown fences or extra fields:
{
    "kind": "final_report",
    "report": {
    "incident_id": "...",
    "summary": "...",
    "evidence": [{"evidence_id": "E1", "source": "metric", "summary": "..."}],
    "hypotheses": [{
        "statement": "...",
        "confidence": "low|medium|high",
        "supporting_evidence_ids": ["E1"],
        "contradicting_evidence_ids": [],
        "missing_evidence": []
    }],
    "status": "completed|inconclusive|failed"
    }
}
Every final claim must cite evidence IDs from the tool observations. Do not invent evidence IDs.
If a hypothesis requires evidence that was unavailable, list that requirement in the
`missing_evidence` field and mark the report `inconclusive`; never treat missing evidence as evidence of absence.
"""


def _provider_error_to_incident_error(
    *,
    failure_kind: ProviderFailureKind | None,
    attempt_count: int,
) -> IncidentError:
    correlation_id = f"model-{uuid4().hex}"

    if failure_kind == ProviderFailureKind.TIMEOUT:
        return IncidentError(
            classification="dependency_timeout",
            retryable=True,
            component="model_provider",
            correlation_id=correlation_id,
            attempt_count=attempt_count,
            user_message="The model service timed out.",
        )

    if failure_kind == ProviderFailureKind.INVALID_REQUEST:
        return IncidentError(
            classification="invalid_request",
            retryable=False,
            component="model_provider",
            correlation_id=correlation_id,
            attempt_count=attempt_count,
            user_message="The model provider rejected the request format.",
        )

    if failure_kind in {
        ProviderFailureKind.SERVICE_UNAVAILABLE,
        ProviderFailureKind.RATE_LIMITED,
        ProviderFailureKind.CONNECTION_ERROR,
    }:
        return IncidentError(
            classification="service_unavailable",
            retryable=True,
            component="model_provider",
            correlation_id=correlation_id,
            attempt_count=attempt_count,
            user_message="The model service is temporarily unavailable.",
        )

    return IncidentError(
        classification="service_unavailable",
        retryable=False,
        component="model_provider",
        correlation_id=correlation_id,
        attempt_count=attempt_count,
        user_message="The model service failed to process the request.",
    )


def _build_messages(
    incident: IncidentInput,
    observations: list[Any],
    system_instruction: str,
    assistant_messages: list[AIMessage] | None = None,
) -> list[BaseMessage]:
    user_payload = {
        "incident": incident.model_dump(),
        "expected_response": "Return a tool request or final report matching the IncidentLens schema.",
    }
    messages: list[BaseMessage] = [
        SystemMessage(content=system_instruction),
        HumanMessage(content=json.dumps(user_payload, sort_keys=True)),
    ]
    assistant_messages = assistant_messages or []
    for index, observation in enumerate(observations):
        if not isinstance(observation, ToolObservation):
            continue
        call_id = observation.tool_call.call_id
        if call_id is None:
            continue
        assistant_message = (
            assistant_messages[index]
            if index < len(assistant_messages)
            else AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": observation.tool_call.name,
                        "args": observation.tool_call.arguments,
                        "id": call_id,
                    }
                ],
            )
        )
        messages.extend(
            [
                assistant_message,
                ToolMessage(
                    content=json.dumps(observation.result, sort_keys=True),
                    tool_call_id=call_id,
                ),
            ]
        )
    return messages


def _parse_langchain_response(response: Any) -> dict[str, Any]:
    tool_calls = getattr(response, "tool_calls", None) or []
    if tool_calls:
        first_call = tool_calls[0]
        return {
            "kind": "tool_request",
            "tool_call": {
                "name": first_call["name"],
                "arguments": first_call.get("args", {}),
                "call_id": first_call.get("id"),
            },
        }

    content = getattr(response, "content", response)
    if isinstance(content, dict):
        return content
    if isinstance(content, list):
        text_blocks = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        content = "".join(text_blocks).strip()
    if isinstance(content, str):
        content = _strip_json_fence(content)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {"kind": "invalid_model_response", "content": content}
        if isinstance(parsed, dict):
            if "kind" not in parsed and {"incident_id", "summary", "hypotheses", "status"}.issubset(
                parsed
            ):
                return {"kind": "final_report", "report": parsed}
            return parsed
        return {"kind": "invalid_model_response", "content": parsed}

    return {"kind": "invalid_model_response", "content": repr(content)}


def _strip_json_fence(content: str) -> str:
    """Remove an optional Markdown JSON fence without changing the payload."""
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _classify_provider_error(exc: Exception) -> ProviderFailureKind | None:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status == 429 or "429" in str(exc):
        return ProviderFailureKind.RATE_LIMITED
    if status in {500, 502, 503, 504}:
        return ProviderFailureKind.SERVICE_UNAVAILABLE
    if status == 408 or "TIMEOUT" in str(exc).upper():
        return ProviderFailureKind.TIMEOUT
    if status == 400:
        return ProviderFailureKind.INVALID_REQUEST
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return ProviderFailureKind.CONNECTION_ERROR
    return None


def _extract_usage(response: Any) -> dict[str, int] | None:
    candidates = [
        getattr(response, "usage_metadata", None),
        getattr(response, "response_metadata", None),
    ]
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        normalized: dict[str, int] = {}
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            value = candidate.get(field)
            if isinstance(value, int) and value >= 0:
                normalized[field] = value
        if normalized:
            return normalized
    return None
