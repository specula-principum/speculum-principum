"""Tests for the monitoring module."""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.orchestration.monitoring import AgentMonitor, HealthStatus, MissionMetrics
from src.orchestration.types import MissionOutcome, MissionStatus, AgentStep, Thought, ThoughtType


def test_monitor_initialization():
    """Test that monitor initializes database correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metrics.db"
        monitor = AgentMonitor(db_path=db_path)
        
        assert db_path.exists()
        
        # Check schema
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "mission_metrics" in tables
        conn.close()
        
        monitor.close()


def test_record_mission():
    """Test recording a mission execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metrics.db"
        monitor = AgentMonitor(db_path=db_path)
        
        # Create a simple successful outcome
        outcome = MissionOutcome(
            status=MissionStatus.SUCCEEDED,
            steps=[
                AgentStep(
                    thought=Thought(content="Test thought", type=ThoughtType.FINISH),
                    result=None
                )
            ],
            summary="Test mission completed"
        )
        
        monitor.record_mission(
            outcome=outcome,
            mission_id="test_001",
            mission_type="test_mission",
            duration=1.5,
            token_usage=100,
            cost_estimate=0.01
        )
        
        # Verify record was created
        recent = monitor.get_recent_missions(limit=1)
        assert len(recent) == 1
        assert recent[0]["mission_id"] == "test_001"
        assert recent[0]["status"] == MissionStatus.SUCCEEDED.value
        assert recent[0]["duration_seconds"] == 1.5
        
        monitor.close()


def test_health_check_healthy():
    """Test health check with all successful missions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metrics.db"
        monitor = AgentMonitor(db_path=db_path)
        
        # Record 10 successful missions
        for i in range(10):
            outcome = MissionOutcome(
                status=MissionStatus.SUCCEEDED,
                steps=[],
                summary="Success"
            )
            monitor.record_mission(
                outcome=outcome,
                mission_id=f"test_{i:03d}",
                mission_type="test_mission",
                duration=1.0
            )
        
        health = monitor.check_health()
        assert health.status == HealthStatus.HEALTHY
        assert health.total_missions == 10
        assert health.success_count == 10
        assert health.failure_count == 0
        
        monitor.close()


def test_health_check_degraded():
    """Test health check with some failures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metrics.db"
        monitor = AgentMonitor(db_path=db_path)
        
        # Record 7 successes and 3 failures (70% success rate)
        for i in range(7):
            outcome = MissionOutcome(status=MissionStatus.SUCCEEDED, steps=[], summary="Success")
            monitor.record_mission(
                outcome=outcome,
                mission_id=f"test_success_{i}",
                mission_type="test_mission",
                duration=1.0
            )
        
        for i in range(3):
            outcome = MissionOutcome(
                status=MissionStatus.FAILED,
                steps=[],
                summary="Test failure"
            )
            monitor.record_mission(
                outcome=outcome,
                mission_id=f"test_failure_{i}",
                mission_type="test_mission",
                duration=1.0
            )
        
        health = monitor.check_health()
        assert health.status == HealthStatus.DEGRADED
        assert health.total_missions == 10
        assert health.success_count == 7
        assert health.failure_count == 3
        
        monitor.close()


def test_health_check_unhealthy():
    """Test health check with many failures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metrics.db"
        monitor = AgentMonitor(db_path=db_path)
        
        # Record 3 successes and 7 failures (30% success rate)
        for i in range(3):
            outcome = MissionOutcome(status=MissionStatus.SUCCEEDED, steps=[], summary="Success")
            monitor.record_mission(
                outcome=outcome,
                mission_id=f"test_success_{i}",
                mission_type="test_mission",
                duration=1.0
            )
        
        for i in range(7):
            outcome = MissionOutcome(
                status=MissionStatus.FAILED,
                steps=[],
                summary="Test failure"
            )
            monitor.record_mission(
                outcome=outcome,
                mission_id=f"test_failure_{i}",
                mission_type="test_mission",
                duration=1.0
            )
        
        health = monitor.check_health()
        assert health.status == HealthStatus.UNHEALTHY
        assert health.total_missions == 10
        assert health.success_count == 3
        assert health.failure_count == 7
        
        monitor.close()


def test_generate_report():
    """Test generating performance report."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metrics.db"
        monitor = AgentMonitor(db_path=db_path)
        
        # Record some missions
        for i in range(5):
            outcome = MissionOutcome(status=MissionStatus.SUCCEEDED, steps=[], summary="Success")
            monitor.record_mission(
                outcome=outcome,
                mission_id=f"test_{i}",
                mission_type="test_mission",
                duration=2.0,
                token_usage=100,
                cost_estimate=0.01
            )
        
        report = monitor.generate_report(period=timedelta(days=7))
        
        assert report["summary"]["total_missions"] == 5
        assert report["summary"]["success_rate"] == 100.0
        assert report["performance"]["avg_duration_seconds"] == 2.0
        assert report["costs"]["total_tokens"] == 500
        assert report["costs"]["total_cost_usd"] == 0.05
        assert "test_mission" in report["mission_types"]
        
        monitor.close()


def test_context_manager():
    """Test using monitor as context manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metrics.db"
        
        with AgentMonitor(db_path=db_path) as monitor:
            outcome = MissionOutcome(status=MissionStatus.SUCCEEDED, steps=[], summary="Success")
            monitor.record_mission(
                outcome=outcome,
                mission_id="test_001",
                mission_type="test_mission",
                duration=1.0
            )
            recent = monitor.get_recent_missions(limit=1)
            assert len(recent) == 1
        
        # Connection should be closed after context exit
        assert monitor._connection is None
