import pytest
from pydantic import ValidationError

from incidentlens.contracts import Evidence, IncidentInput
from incidentlens.specialists import (
    FindingKind,
    SpecialistFinding,
    SpecialistRole,
    build_role_tool_registry,
    build_specialist_context,
    role_contracts,
    validate_finding_evidence,
)

FIXTURE_PATH = "fixtures/incidents/payment_latency.json"

INCIDENT = IncidentInput(
    incident_id="incident-001",
    title="Latency spike",
    affected_service="checkout-api",
    start_time="2026-09-10T10:05:00Z",
    summary="Checkout latency increased.",
)


def test_role_contracts_have_distinct_domains_and_tools() -> None:
    contracts = role_contracts()

    assert contracts[SpecialistRole.LOGS].allowed_tools == {"search_logs"}
    assert contracts[SpecialistRole.METRICS].allowed_tools == {"query_metrics"}
    assert contracts[SpecialistRole.TRACES].allowed_tools == {"search_traces", "get_trace"}
    assert (
        contracts[SpecialistRole.LOGS].allowed_signal_types
        != contracts[SpecialistRole.METRICS].allowed_signal_types
    )


@pytest.mark.parametrize("role", list(SpecialistRole))
def test_role_registry_contains_only_role_capabilities(role) -> None:
    registry = build_role_tool_registry(role, FIXTURE_PATH)

    assert registry.tool_names == role_contracts()[role].allowed_tools


def test_context_contains_only_role_domain_evidence() -> None:
    evidence = [
        Evidence(evidence_id="L1", source="log", summary="Timeout logged."),
        Evidence(evidence_id="M1", source="metric", summary="Latency rose."),
        Evidence(evidence_id="T1", source="trace", summary="Payment span was slow."),
    ]

    context = build_specialist_context(INCIDENT, SpecialistRole.METRICS, evidence)

    assert [item.evidence_id for item in context.evidence] == ["M1"]
    assert context.allowed_tools == {"query_metrics"}
    assert "hypothesis" not in context.model_dump()


def test_context_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        build_specialist_context(INCIDENT, SpecialistRole.METRICS, []).model_validate(
            {"incident_id": "incident-001", "peer_conclusion": "database"}
        )


def test_finding_requires_unique_known_evidence_ids() -> None:
    finding = SpecialistFinding(
        role=SpecialistRole.METRICS,
        claim_kind=FindingKind.OBSERVATION,
        claim="Latency increased.",
        evidence_ids=["M1"],
        confidence="medium",
    )

    assert validate_finding_evidence(finding, {"M1"}) == finding

    with pytest.raises(ValueError, match="unknown evidence"):
        validate_finding_evidence(finding, {"L1"})


def test_finding_rejects_duplicate_evidence_ids() -> None:
    with pytest.raises(ValidationError, match="unique"):
        SpecialistFinding(
            role=SpecialistRole.TRACES,
            claim_kind=FindingKind.INFERENCE,
            claim="Latency is localized.",
            evidence_ids=["T1", "T1"],
            confidence="low",
        )


@pytest.mark.parametrize(
    ("role", "expected_source"),
    [
        (SpecialistRole.LOGS, "log"),
        (SpecialistRole.METRICS, "metric"),
        (SpecialistRole.TRACES, "trace"),
    ],
)
def test_each_specialist_excludes_other_signal_domains(role, expected_source) -> None:
    evidence = [
        Evidence(evidence_id="L1", source="log", summary="Timeout logged."),
        Evidence(evidence_id="M1", source="metric", summary="Latency rose."),
        Evidence(evidence_id="T1", source="trace", summary="Payment span was slow."),
    ]

    context = build_specialist_context(INCIDENT, role, evidence)

    assert {item.source for item in context.evidence} == {expected_source}
    assert context.allowed_tools == role_contracts()[role].allowed_tools


def test_specialist_context_does_not_carry_peer_findings() -> None:
    context = build_specialist_context(INCIDENT, SpecialistRole.TRACES, [])

    serialized = context.model_dump_json()

    assert "hypothesis" not in serialized
    assert "peer" not in serialized
    assert "ground_truth" not in serialized


@pytest.mark.parametrize("role", list(SpecialistRole))
def test_missing_domain_evidence_is_explicitly_empty(role) -> None:
    context = build_specialist_context(INCIDENT, role, [])

    assert context.evidence == []
    assert context.task
    assert context.allowed_tools == role_contracts()[role].allowed_tools


def test_missing_evidence_cannot_be_replaced_with_invented_id() -> None:
    finding = SpecialistFinding(
        role=SpecialistRole.METRICS,
        claim_kind=FindingKind.HYPOTHESIS,
        claim="The metric source may be unavailable.",
        evidence_ids=["INVENTED"],
        confidence="low",
        open_questions=["Was metric collection available during the incident window?"],
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        validate_finding_evidence(finding, set())


def test_finding_without_evidence_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 1 item"):
        SpecialistFinding(
            role=SpecialistRole.LOGS,
            claim_kind=FindingKind.OBSERVATION,
            claim="No log evidence was retrieved.",
            evidence_ids=[],
            confidence="low",
        )
