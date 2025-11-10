"""Deployment infrastructure for continuous agent operation."""

from __future__ import annotations

import json
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from queue import PriorityQueue, Empty
from threading import Event, Lock
from typing import Any, Callable, Sequence

from .agent import AgentRuntime, MissionEvaluator
from .missions import Mission
from .monitoring import AgentMonitor, HealthStatus
from .types import ExecutionContext, MissionOutcome, MissionStatus


class MissionPriority(Enum):
    """Priority levels for mission execution."""

    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


@dataclass(frozen=True, order=True)
class QueuedMission:
    """Mission in the execution queue."""

    priority: int  # Lower is higher priority
    timestamp: float  # For FIFO within same priority
    mission: Mission = field(compare=False)
    context: ExecutionContext = field(compare=False)
    mission_id: str = field(compare=False)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures detected, operations blocked
    HALF_OPEN = "half_open"  # Testing if system recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker to prevent cascading failures."""

    failure_threshold: int = 3
    recovery_timeout: int = 300  # seconds
    _state: CircuitBreakerState = field(default=CircuitBreakerState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float | None = field(default=None, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        with self._lock:
            return self._state

    def record_success(self) -> None:
        """Record successful execution."""
        with self._lock:
            self._failure_count = 0
            self._state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        """Record failed execution."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                print(
                    f"Circuit breaker OPEN after {self._failure_count} consecutive failures",
                    file=sys.stderr,
                )

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        with self._lock:
            if self._state == CircuitBreakerState.CLOSED:
                return True

            if self._state == CircuitBreakerState.OPEN:
                # Check if recovery timeout has elapsed
                if self._last_failure_time is None:
                    return False

                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitBreakerState.HALF_OPEN
                    print("Circuit breaker HALF_OPEN - testing recovery", file=sys.stderr)
                    return True
                return False

            # HALF_OPEN state allows one test execution
            return True

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._failure_count = 0
            self._state = CircuitBreakerState.CLOSED
            self._last_failure_time = None


@dataclass
class AgentDeployment:
    """Manages continuous agent operation with queue and health checks."""

    runtime: AgentRuntime
    monitor: AgentMonitor
    max_queue_size: int = 100
    health_check_interval: int = 60  # seconds
    _queue: PriorityQueue = field(default_factory=PriorityQueue, init=False)
    _circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker, init=False)
    _shutdown_event: Event = field(default_factory=Event, init=False)
    _running: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Initialize shutdown signal handlers."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle graceful shutdown signals."""
        print(f"\nReceived signal {signum}, initiating graceful shutdown...")
        self._shutdown_event.set()

    def enqueue_mission(
        self,
        mission: Mission,
        context: ExecutionContext,
        priority: MissionPriority = MissionPriority.NORMAL,
        mission_id: str | None = None,
    ) -> bool:
        """Add a mission to the execution queue.

        Args:
            mission: Mission to execute
            context: Execution context
            priority: Mission priority level
            mission_id: Optional mission ID (generated if not provided)

        Returns:
            True if enqueued, False if queue is full
        """
        if self._queue.qsize() >= self.max_queue_size:
            print(
                f"warning: Queue full ({self.max_queue_size}), mission rejected",
                file=sys.stderr,
            )
            return False

        if mission_id is None:
            mission_id = f"{mission.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        queued = QueuedMission(
            priority=priority.value,
            timestamp=time.time(),
            mission=mission,
            context=context,
            mission_id=mission_id,
        )

        self._queue.put(queued)
        return True

    def run_continuously(self) -> None:
        """Execute missions from the queue continuously until shutdown."""
        self._running = True
        print("Agent deployment started - processing missions continuously")
        print(f"Queue size limit: {self.max_queue_size}")
        print(f"Health check interval: {self.health_check_interval}s")
        print("Press Ctrl+C to initiate graceful shutdown\n")

        last_health_check = time.time()

        while not self._shutdown_event.is_set():
            # Periodic health check
            if time.time() - last_health_check >= self.health_check_interval:
                self._perform_health_check()
                last_health_check = time.time()

            # Try to get a mission from queue
            try:
                queued = self._queue.get(timeout=1.0)
            except Empty:
                continue

            # Check circuit breaker
            if not self._circuit_breaker.can_execute():
                print(
                    f"Circuit breaker {self._circuit_breaker.state.value} - "
                    f"requeueing mission {queued.mission_id}",
                    file=sys.stderr,
                )
                # Requeue with delay
                time.sleep(5)
                self._queue.put(queued)
                continue

            # Execute mission
            self._execute_queued_mission(queued)

        print("\nGraceful shutdown initiated - waiting for current mission to complete")
        self._running = False
        print("Agent deployment stopped cleanly")

    def _execute_queued_mission(self, queued: QueuedMission) -> None:
        """Execute a queued mission and handle the outcome."""
        print(f"[{datetime.utcnow().isoformat()}] Executing: {queued.mission_id}")
        print(f"  Priority: {MissionPriority(queued.priority).name}")
        print(f"  Goal: {queued.mission.goal[:80]}...")

        start_time = time.time()

        try:
            outcome = self.runtime.execute_mission(queued.mission, queued.context)
            duration = time.time() - start_time

            # Record metrics
            self.monitor.record_mission(
                outcome=outcome,
                mission_id=queued.mission_id,
                mission_type=queued.mission.id,
                duration=duration,
            )

            # Update circuit breaker
            if outcome.status == MissionStatus.SUCCEEDED:
                self._circuit_breaker.record_success()
                print(f"  ✓ Completed successfully in {duration:.2f}s")
            else:
                self._circuit_breaker.record_failure()
                print(
                    f"  ✗ Failed with status {outcome.status.value} in {duration:.2f}s",
                    file=sys.stderr,
                )
                if outcome.summary:
                    print(f"    Reason: {outcome.summary}", file=sys.stderr)

        except Exception as exc:
            duration = time.time() - start_time
            self._circuit_breaker.record_failure()

            print(
                f"  ✗ Exception during execution: {exc}",
                file=sys.stderr,
            )

            # Record failure
            from .types import MissionOutcome

            failed_outcome = MissionOutcome(
                status=MissionStatus.FAILED,
                steps=[],
                summary=f"Exception: {exc}",
            )
            self.monitor.record_mission(
                outcome=failed_outcome,
                mission_id=queued.mission_id,
                mission_type=queued.mission.id,
                duration=duration,
            )

        print()  # Blank line between missions

    def _perform_health_check(self) -> None:
        """Perform periodic health assessment."""
        health = self.monitor.check_health(lookback_hours=24)

        print(f"[Health Check] Status: {health.status.value.upper()}")
        print(f"  Total missions (24h): {health.total_missions}")
        print(f"  Success rate: {health.success_count}/{health.total_missions}")
        print(f"  Circuit breaker: {self._circuit_breaker.state.value}")
        print(f"  Queue size: {self._queue.qsize()}/{self.max_queue_size}")

        if health.status == HealthStatus.UNHEALTHY:
            print(f"  WARNING: Agent health is {health.status.value}", file=sys.stderr)
            for rec in health.recommendations:
                print(f"    - {rec}", file=sys.stderr)

        print()

    def get_status(self) -> dict[str, Any]:
        """Get current deployment status.

        Returns:
            Status information dictionary
        """
        health = self.monitor.check_health()

        return {
            "running": self._running,
            "circuit_breaker": self._circuit_breaker.state.value,
            "queue_size": self._queue.qsize(),
            "queue_capacity": self.max_queue_size,
            "health": {
                "status": health.status.value,
                "total_missions": health.total_missions,
                "success_count": health.success_count,
                "failure_count": health.failure_count,
            },
        }

    def shutdown(self) -> None:
        """Initiate graceful shutdown."""
        self._shutdown_event.set()

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker."""
        self._circuit_breaker.reset()
        print("Circuit breaker manually reset to CLOSED state")
