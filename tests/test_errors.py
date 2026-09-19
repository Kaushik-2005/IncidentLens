import pytest
from pydantic import ValidationError

from incidentlens.errors import (
    IncidentError,
    sanitize_exception,
    sanitize_structured,
    sanitize_text,
)


def make_error(**overrides):
    values = {
        "classification": "service_unavailable",
        "retryable": True,
        "component": "model_provider",
        "correlation_id": "err-7421",
        "attempt_count": 2,
        "user_message": "The model service is temporarily unavailable.",
        "debug_ref": "diag-7421",
    }
    values.update(overrides)
    return IncidentError(**values)


def test_error_contract_accepts_sanitized_failure() -> None:
    error = make_error()

    assert error.classification == "service_unavailable"
    assert error.attempt_count == 2
    assert error.model_dump()["debug_ref"] == "diag-7421"


def test_error_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        make_error(raw_exception="secret connection string")


def test_error_contract_rejects_negative_attempt_count() -> None:
    with pytest.raises(ValidationError):
        make_error(attempt_count=-1)


def test_error_contract_does_not_store_raw_exception_text() -> None:
    error = make_error(
        user_message="The telemetry backend encountered an internal error.",
        debug_ref="diag-1001",
    )

    serialized = error.model_dump_json()

    assert "postgres://admin:secret@db.internal" not in serialized
    assert "customer=C12345" not in serialized


def test_sanitize_text_redacts_secrets_connections_and_customer_ids() -> None:
    sanitized = sanitize_text(
        "postgres://admin:secret@db.internal/app api_key=abc123 customer_id=C12345"
    )

    assert "postgres://" not in sanitized
    assert "secret" not in sanitized
    assert "abc123" not in sanitized
    assert "C12345" not in sanitized


def test_incident_error_from_message_sanitizes_and_bounds_text() -> None:
    error = IncidentError.from_message(
        classification="service_unavailable",
        retryable=False,
        component="model_provider",
        correlation_id="err-1",
        user_message="token=secret-value " + "x" * 600,
    )

    assert "secret-value" not in error.user_message
    assert len(error.user_message) == 500


def test_sanitize_structured_redacts_nested_payloads_and_headers() -> None:
    payload = {
        "request": {
            "headers": {
                "Authorization": "Bearer super-secret",
                "x-api-key": "abc123",
            },
            "customer": {"customer_id": "C12345", "region": "IN"},
        },
        "message": "postgres://admin:secret@db.internal/app",
    }

    sanitized = sanitize_structured(payload)

    assert sanitized["request"]["headers"]["Authorization"] == "[REDACTED]"
    assert sanitized["request"]["headers"]["x-api-key"] == "[REDACTED]"
    assert sanitized["request"]["customer"]["customer_id"] == "[REDACTED]"
    assert "postgres://" not in sanitized["message"]


def test_sanitize_exception_includes_chained_causes_without_secrets() -> None:
    try:
        try:
            raise RuntimeError("password=inner-secret")
        except RuntimeError as cause:
            raise ValueError("postgres://admin:outer-secret@db.internal/app") from cause
    except ValueError as exc:
        sanitized = sanitize_exception(exc)

    assert "inner-secret" not in sanitized
    assert "outer-secret" not in sanitized
    assert "postgres://" not in sanitized


def test_sanitize_structured_audit_payload_contains_no_sensitive_values() -> None:
    audit_payload = {
        "event_type": "execution_failed",
        "action_id": "action-1",
        "arguments": {"version": "v2.4", "api_key": "secret-value"},
        "debug": {"customer_id": "C12345", "error": "token=abc"},
    }

    sanitized = sanitize_structured(audit_payload)

    serialized = str(sanitized)
    assert "secret-value" not in serialized
    assert "C12345" not in serialized
    assert "token=abc" not in serialized
    assert sanitized["event_type"] == "execution_failed"


def test_error_contract_requires_non_empty_safe_fields() -> None:
    with pytest.raises(ValidationError):
        make_error(correlation_id="")

    with pytest.raises(ValidationError):
        make_error(user_message="")
