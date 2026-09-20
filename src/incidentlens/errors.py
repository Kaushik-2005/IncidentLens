import re
from collections.abc import Mapping
from traceback import format_exception
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_SENSITIVE_PATTERNS = (
    (
        re.compile(r"(?i)(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s]+"),
        "[REDACTED_CONNECTION_STRING]",
    ),
    (
        re.compile(
            r"(?i)\b(?:password|passwd|secret|token|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+"
        ),
        "[REDACTED_SECRET]",
    ),
    (
        re.compile(r"(?i)\bcustomer(?:_id)?\s*[=:]\s*[A-Za-z0-9._-]+"),
        "customer_id=[REDACTED]",
    ),
)
_SENSITIVE_KEYS = re.compile(
    r"(?i)(?:password|passwd|secret|token|api[_-]?key|authorization|connection[_-]?string|customer[_-]?id)"
)


def sanitize_text(value: str, *, max_length: int = 500) -> str:
    """Redact common secrets/identifiers and bound text before it crosses a boundary."""
    sanitized = value
    for pattern, replacement in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    if len(sanitized) > max_length:
        return sanitized[: max_length - 3] + "..."
    return sanitized


def sanitize_exception(exc: BaseException, *, max_length: int = 500) -> str:
    """Sanitize an exception and its chained causes before diagnostic use."""
    return sanitize_text("".join(format_exception(exc)), max_length=max_length)


def sanitize_structured(value: Any) -> Any:
    """Recursively sanitize diagnostic mappings and sequences without changing inputs."""
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]"
            if _SENSITIVE_KEYS.search(str(key))
            else sanitize_structured(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_structured(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_structured(item) for item in value)
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, BaseException):
        return sanitize_exception(value)
    return value


ErrorClassification = Literal[
    "service_unavailable",
    "dependency_timeout",
    "dependency_circuit_open",
    "model_budget_exhausted",
    "tool_budget_exhausted",
    "invalid_request",
    "incident_scope_violation",
    "tool_not_authorized",
    "approval_invalid",
    "model_contract_violation",
    "unsupported_checkpoint_version",
]

ErrorComponent = Literal[
    "model_provider",
    "metrics_backend",
    "logs_backend",
    "traces_backend",
    "tool_authorization",
    "coordinator",
    "model_adapter",
    "checkpoint_recovery",
    "approval_boundary",
]


class IncidentError(BaseModel):
    """Sanitized, provider-neutral error shared across IncidentLens layers."""

    model_config = ConfigDict(extra="forbid")

    classification: ErrorClassification
    retryable: bool
    component: ErrorComponent
    correlation_id: str = Field(min_length=1)
    attempt_count: int = Field(default=0, ge=0)
    user_message: str = Field(min_length=1, max_length=500)
    debug_ref: str | None = Field(default=None, min_length=1)

    @classmethod
    def from_message(
        cls,
        *,
        classification: ErrorClassification,
        retryable: bool,
        component: ErrorComponent,
        correlation_id: str,
        user_message: str,
        attempt_count: int = 0,
        debug_ref: str | None = None,
    ) -> "IncidentError":
        return cls(
            classification=classification,
            retryable=retryable,
            component=component,
            correlation_id=correlation_id,
            attempt_count=attempt_count,
            user_message=sanitize_text(user_message),
            debug_ref=debug_ref,
        )
