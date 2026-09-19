from incidentlens.reliability import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitState,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


def test_circuit_opens_after_threshold_and_fails_fast() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=10, clock=clock)

    assert breaker.allow_request() is True
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED
    breaker.record_failure()

    assert breaker.state == CircuitState.OPEN
    assert breaker.allow_request() is False


def test_circuit_half_open_probe_recovers() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=10, clock=clock)
    breaker.record_failure()

    clock.value = 10
    assert breaker.allow_request() is True
    assert breaker.state == CircuitState.HALF_OPEN
    breaker.record_success()

    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_circuit_half_open_failure_reopens() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=10, clock=clock)
    breaker.record_failure()

    clock.value = 10
    assert breaker.allow_request() is True
    breaker.record_failure()

    assert breaker.state == CircuitState.OPEN


def test_registry_shares_same_scope_and_isolates_tenants_and_environments() -> None:
    registry = CircuitBreakerRegistry(failure_threshold=1, recovery_timeout_seconds=10)

    first = registry.get(backend="metrics_backend", tenant_id="tenant-a", environment="prod")
    same_scope = registry.get(backend="metrics_backend", tenant_id="tenant-a", environment="prod")
    other_tenant = registry.get(backend="metrics_backend", tenant_id="tenant-b", environment="prod")
    other_environment = registry.get(
        backend="metrics_backend", tenant_id="tenant-a", environment="staging"
    )

    first.record_failure()

    assert same_scope is first
    assert first.state == CircuitState.OPEN
    assert other_tenant.state == CircuitState.CLOSED
    assert other_environment.state == CircuitState.CLOSED
