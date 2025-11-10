"""Tests for the deployment infrastructure."""

import time
from unittest.mock import Mock, MagicMock

import pytest

from src.orchestration.deployment import (
    AgentDeployment,
    CircuitBreaker,
    CircuitBreakerState,
    MissionPriority,
    QueuedMission,
)
from src.orchestration.missions import Mission
from src.orchestration.types import (
    MissionOutcome,
    MissionStatus,
    ExecutionContext,
)


def test_circuit_breaker_initial_state():
    """Test circuit breaker starts in CLOSED state."""
    breaker = CircuitBreaker()
    assert breaker.state == CircuitBreakerState.CLOSED
    assert breaker.can_execute() is True


def test_circuit_breaker_opens_after_failures():
    """Test circuit breaker opens after threshold failures."""
    breaker = CircuitBreaker(failure_threshold=3)
    
    # Record failures
    breaker.record_failure()
    assert breaker.state == CircuitBreakerState.CLOSED
    assert breaker.can_execute() is True
    
    breaker.record_failure()
    assert breaker.state == CircuitBreakerState.CLOSED
    
    breaker.record_failure()
    assert breaker.state == CircuitBreakerState.OPEN
    assert breaker.can_execute() is False


def test_circuit_breaker_resets_on_success():
    """Test circuit breaker resets on successful execution."""
    breaker = CircuitBreaker(failure_threshold=3)
    
    breaker.record_failure()
    breaker.record_failure()
    assert breaker._failure_count == 2
    
    breaker.record_success()
    assert breaker._failure_count == 0
    assert breaker.state == CircuitBreakerState.CLOSED


def test_circuit_breaker_recovery():
    """Test circuit breaker transitions to HALF_OPEN after timeout."""
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    
    # Trigger OPEN state
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitBreakerState.OPEN
    assert breaker.can_execute() is False
    
    # Wait for recovery
    time.sleep(1.1)
    assert breaker.can_execute() is True
    assert breaker.state == CircuitBreakerState.HALF_OPEN


def test_circuit_breaker_manual_reset():
    """Test manual circuit breaker reset."""
    breaker = CircuitBreaker(failure_threshold=2)
    
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitBreakerState.OPEN
    
    breaker.reset()
    assert breaker.state == CircuitBreakerState.CLOSED
    assert breaker._failure_count == 0
    assert breaker.can_execute() is True


def test_queued_mission_priority_ordering():
    """Test that missions are ordered by priority."""
    mission = Mission(
        id="test",
        goal="Test goal",
        constraints=[],
        success_criteria=[],
        max_steps=5,
        allowed_tools=None,
        requires_approval=False
    )
    
    high_priority = QueuedMission(
        priority=MissionPriority.HIGH.value,
        timestamp=time.time(),
        mission=mission,
        context=ExecutionContext(),
        mission_id="high"
    )
    
    low_priority = QueuedMission(
        priority=MissionPriority.LOW.value,
        timestamp=time.time(),
        mission=mission,
        context=ExecutionContext(),
        mission_id="low"
    )
    
    # Higher priority (lower number) should come first
    assert high_priority < low_priority


def test_deployment_enqueue_mission():
    """Test enqueueing missions."""
    runtime = Mock()
    monitor = Mock()
    
    deployment = AgentDeployment(
        runtime=runtime,
        monitor=monitor,
        max_queue_size=10
    )
    
    mission = Mission(
        id="test",
        goal="Test goal",
        constraints=[],
        success_criteria=[],
        max_steps=5,
        allowed_tools=None,
        requires_approval=False
    )
    
    success = deployment.enqueue_mission(
        mission=mission,
        context=ExecutionContext(),
        priority=MissionPriority.NORMAL
    )
    
    assert success is True
    assert deployment._queue.qsize() == 1


def test_deployment_queue_full_rejection():
    """Test that missions are rejected when queue is full."""
    runtime = Mock()
    monitor = Mock()
    
    deployment = AgentDeployment(
        runtime=runtime,
        monitor=monitor,
        max_queue_size=2
    )
    
    mission = Mission(
        id="test",
        goal="Test goal",
        constraints=[],
        success_criteria=[],
        max_steps=5,
        allowed_tools=None,
        requires_approval=False
    )
    
    # Fill queue
    assert deployment.enqueue_mission(mission, ExecutionContext()) is True
    assert deployment.enqueue_mission(mission, ExecutionContext()) is True
    
    # Third should be rejected
    assert deployment.enqueue_mission(mission, ExecutionContext()) is False


def test_deployment_execute_successful_mission():
    """Test executing a successful mission updates circuit breaker."""
    runtime = Mock()
    monitor = Mock()
    
    # Mock successful execution
    runtime.execute_mission.return_value = MissionOutcome(
        status=MissionStatus.SUCCEEDED,
        steps=[],
        summary="Success"
    )
    
    deployment = AgentDeployment(runtime=runtime, monitor=monitor)
    
    mission = Mission(
        id="test",
        goal="Test goal",
        constraints=[],
        success_criteria=[],
        max_steps=5,
        allowed_tools=None,
        requires_approval=False
    )
    
    queued = QueuedMission(
        priority=MissionPriority.NORMAL.value,
        timestamp=time.time(),
        mission=mission,
        context=ExecutionContext(),
        mission_id="test_001"
    )
    
    deployment._execute_queued_mission(queued)
    
    # Check mission was executed
    runtime.execute_mission.assert_called_once()
    
    # Check monitoring was recorded
    monitor.record_mission.assert_called_once()
    
    # Check circuit breaker is still closed
    assert deployment._circuit_breaker.state == CircuitBreakerState.CLOSED


def test_deployment_execute_failed_mission():
    """Test executing a failed mission triggers circuit breaker."""
    runtime = Mock()
    monitor = Mock()
    
    # Mock failed execution
    runtime.execute_mission.return_value = MissionOutcome(
        status=MissionStatus.FAILED,
        steps=[],
        summary="Failure"
    )
    
    deployment = AgentDeployment(runtime=runtime, monitor=monitor)
    deployment._circuit_breaker = CircuitBreaker(failure_threshold=2)
    
    mission = Mission(
        id="test",
        goal="Test goal",
        constraints=[],
        success_criteria=[],
        max_steps=5,
        allowed_tools=None,
        requires_approval=False
    )
    
    queued = QueuedMission(
        priority=MissionPriority.NORMAL.value,
        timestamp=time.time(),
        mission=mission,
        context=ExecutionContext(),
        mission_id="test_001"
    )
    
    # Execute twice to trigger circuit breaker
    deployment._execute_queued_mission(queued)
    deployment._execute_queued_mission(queued)
    
    # Circuit breaker should be open
    assert deployment._circuit_breaker.state == CircuitBreakerState.OPEN


def test_deployment_get_status():
    """Test getting deployment status."""
    runtime = Mock()
    monitor = Mock()
    
    # Mock health check
    from src.orchestration.monitoring import HealthReport, HealthStatus
    monitor.check_health.return_value = HealthReport(
        status=HealthStatus.HEALTHY,
        total_missions=10,
        success_count=9,
        failure_count=1,
        blocked_count=0,
        avg_duration=2.5,
        recent_errors=[],
        recommendations=[]
    )
    
    deployment = AgentDeployment(runtime=runtime, monitor=monitor)
    deployment._running = True
    
    status = deployment.get_status()
    
    assert status["running"] is True
    assert status["circuit_breaker"] == CircuitBreakerState.CLOSED.value
    assert status["queue_size"] == 0
    assert status["health"]["status"] == HealthStatus.HEALTHY.value
    assert status["health"]["total_missions"] == 10


def test_deployment_reset_circuit_breaker():
    """Test manual circuit breaker reset on deployment."""
    runtime = Mock()
    monitor = Mock()
    
    deployment = AgentDeployment(runtime=runtime, monitor=monitor)
    
    # Trigger circuit breaker
    deployment._circuit_breaker.record_failure()
    deployment._circuit_breaker.record_failure()
    deployment._circuit_breaker.record_failure()
    assert deployment._circuit_breaker.state == CircuitBreakerState.OPEN
    
    # Reset
    deployment.reset_circuit_breaker()
    assert deployment._circuit_breaker.state == CircuitBreakerState.CLOSED
