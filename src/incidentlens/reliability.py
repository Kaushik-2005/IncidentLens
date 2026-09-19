from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class DependencyKey:
    backend: str
    tenant_id: str
    environment: str


class CircuitBreaker:
    """Small deterministic circuit breaker with injectable time for tests."""

    def __init__(
        self,
        *,
        failure_threshold: int,
        recovery_timeout_seconds: float,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least one")
        if recovery_timeout_seconds <= 0:
            raise ValueError("recovery_timeout_seconds must be greater than zero")
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._probe_in_flight = False

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def allow_request(self) -> bool:
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.HALF_OPEN:
            if self._probe_in_flight:
                return False
            self._probe_in_flight = True
            return True
        if (
            self._opened_at is None
            or self._clock() - self._opened_at < self.recovery_timeout_seconds
        ):
            return False
        self._state = CircuitState.HALF_OPEN
        self._probe_in_flight = True
        return True

    def record_success(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = None
        self._probe_in_flight = False

    def record_failure(self) -> None:
        self._probe_in_flight = False
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = self._clock()
            return
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = self._clock()


class CircuitBreakerRegistry:
    """Coordinator-owned breaker registry isolated by backend and scope."""

    def __init__(
        self,
        *,
        failure_threshold: int,
        recovery_timeout_seconds: float,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout_seconds = recovery_timeout_seconds
        self._clock = clock
        self._breakers: dict[DependencyKey, CircuitBreaker] = {}

    def get(self, *, backend: str, tenant_id: str, environment: str) -> CircuitBreaker:
        key = DependencyKey(backend, tenant_id, environment)
        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker(
                failure_threshold=self._failure_threshold,
                recovery_timeout_seconds=self._recovery_timeout_seconds,
                clock=self._clock,
            )
        return self._breakers[key]
