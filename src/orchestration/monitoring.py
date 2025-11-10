"""Monitoring and observability for the Copilot agent runtime."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from .types import MissionOutcome, MissionStatus


class HealthStatus(Enum):
    """Overall health assessment for the agent."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class MissionMetrics:
    """Performance metrics for a single mission execution."""

    mission_id: str
    mission_type: str
    status: MissionStatus
    duration_seconds: float
    step_count: int
    tool_call_count: int
    timestamp: datetime
    error_message: str | None = None
    token_usage: int | None = None
    cost_estimate: float | None = None


@dataclass(frozen=True)
class HealthReport:
    """Agent health assessment report."""

    status: HealthStatus
    total_missions: int
    success_count: int
    failure_count: int
    blocked_count: int
    avg_duration: float
    recent_errors: Sequence[str]
    recommendations: Sequence[str]


@dataclass
class AgentMonitor:
    """Tracks agent performance and health metrics."""

    db_path: Path = field(default_factory=lambda: Path("agent_metrics.db"))
    _connection: sqlite3.Connection | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize database connection and schema."""
        self._connection = sqlite3.connect(str(self.db_path))
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create metrics tables if they don't exist."""
        cursor = self._connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS mission_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                mission_type TEXT NOT NULL,
                status TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                step_count INTEGER NOT NULL,
                tool_call_count INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                error_message TEXT,
                token_usage INTEGER,
                cost_estimate REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_mission_timestamp 
            ON mission_metrics(timestamp DESC)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_mission_status 
            ON mission_metrics(status)
            """
        )
        self._connection.commit()

    def record_mission(self, outcome: MissionOutcome, mission_id: str, mission_type: str, 
                      duration: float, token_usage: int | None = None,
                      cost_estimate: float | None = None) -> None:
        """Log mission execution metrics.
        
        Args:
            outcome: Mission execution outcome
            mission_id: Unique identifier for this mission execution
            mission_type: Type/category of mission
            duration: Execution time in seconds
            token_usage: Optional LLM token count
            cost_estimate: Optional cost in USD
        """
        # Count tool calls
        tool_call_count = sum(
            1 for step in outcome.steps 
            if step.thought.tool_call is not None
        )

        metrics = MissionMetrics(
            mission_id=mission_id,
            mission_type=mission_type,
            status=outcome.status,
            duration_seconds=duration,
            step_count=len(outcome.steps),
            tool_call_count=tool_call_count,
            timestamp=datetime.utcnow(),
            error_message=outcome.summary if outcome.status == MissionStatus.FAILED else None,
            token_usage=token_usage,
            cost_estimate=cost_estimate,
        )

        cursor = self._connection.cursor()
        cursor.execute(
            """
            INSERT INTO mission_metrics 
            (mission_id, mission_type, status, duration_seconds, step_count, 
             tool_call_count, timestamp, error_message, token_usage, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metrics.mission_id,
                metrics.mission_type,
                metrics.status.value,
                metrics.duration_seconds,
                metrics.step_count,
                metrics.tool_call_count,
                metrics.timestamp.isoformat(),
                metrics.error_message,
                metrics.token_usage,
                metrics.cost_estimate,
            ),
        )
        self._connection.commit()

    def check_health(self, lookback_hours: int = 24) -> HealthReport:
        """Assess agent health based on recent performance.
        
        Args:
            lookback_hours: How many hours of history to analyze
            
        Returns:
            Health assessment report
        """
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        
        cursor = self._connection.cursor()
        cursor.execute(
            """
            SELECT status, duration_seconds, error_message
            FROM mission_metrics
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            """,
            (cutoff.isoformat(),),
        )
        
        rows = cursor.fetchall()
        
        if not rows:
            return HealthReport(
                status=HealthStatus.HEALTHY,
                total_missions=0,
                success_count=0,
                failure_count=0,
                blocked_count=0,
                avg_duration=0.0,
                recent_errors=[],
                recommendations=["No recent mission executions"],
            )
        
        success_count = sum(1 for row in rows if row["status"] == MissionStatus.SUCCEEDED.value)
        failure_count = sum(1 for row in rows if row["status"] == MissionStatus.FAILED.value)
        blocked_count = sum(1 for row in rows if row["status"] == MissionStatus.BLOCKED.value)
        
        avg_duration = sum(row["duration_seconds"] for row in rows) / len(rows)
        
        # Collect recent errors
        recent_errors = [
            row["error_message"]
            for row in rows[:5]  # Last 5 missions
            if row["error_message"] is not None
        ]
        
        # Calculate health status
        total = len(rows)
        success_rate = success_count / total if total > 0 else 0.0
        
        if success_rate >= 0.9 and failure_count < 3:
            health_status = HealthStatus.HEALTHY
        elif success_rate >= 0.7 or failure_count < 5:
            health_status = HealthStatus.DEGRADED
        else:
            health_status = HealthStatus.UNHEALTHY
        
        # Generate recommendations
        recommendations = []
        if failure_count >= 5:
            recommendations.append(f"High failure rate: {failure_count}/{total} missions failed")
        if blocked_count >= 3:
            recommendations.append(f"Multiple blocked missions: {blocked_count} requiring approval")
        if avg_duration > 60:
            recommendations.append(f"Slow execution: avg {avg_duration:.1f}s per mission")
        if not recommendations:
            recommendations.append("Agent operating normally")
        
        return HealthReport(
            status=health_status,
            total_missions=total,
            success_count=success_count,
            failure_count=failure_count,
            blocked_count=blocked_count,
            avg_duration=avg_duration,
            recent_errors=recent_errors,
            recommendations=recommendations,
        )

    def generate_report(self, period: timedelta = timedelta(days=7)) -> dict[str, Any]:
        """Generate comprehensive performance report.
        
        Args:
            period: Time period to analyze
            
        Returns:
            Report data as dictionary
        """
        cutoff = datetime.utcnow() - period
        
        cursor = self._connection.cursor()
        cursor.execute(
            """
            SELECT 
                COUNT(*) as total,
                AVG(duration_seconds) as avg_duration,
                SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as successes,
                SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as failures,
                SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as blocked,
                SUM(tool_call_count) as total_tool_calls,
                SUM(token_usage) as total_tokens,
                SUM(cost_estimate) as total_cost
            FROM mission_metrics
            WHERE timestamp > ?
            """,
            (
                MissionStatus.SUCCEEDED.value,
                MissionStatus.FAILED.value,
                MissionStatus.BLOCKED.value,
                cutoff.isoformat(),
            ),
        )
        
        row = cursor.fetchone()
        
        # Get mission type breakdown
        cursor.execute(
            """
            SELECT mission_type, COUNT(*) as count
            FROM mission_metrics
            WHERE timestamp > ?
            GROUP BY mission_type
            ORDER BY count DESC
            """,
            (cutoff.isoformat(),),
        )
        
        mission_breakdown = {row["mission_type"]: row["count"] for row in cursor.fetchall()}
        
        total = row["total"] or 0
        
        return {
            "period": {
                "start": cutoff.isoformat(),
                "end": datetime.utcnow().isoformat(),
                "days": period.days,
            },
            "summary": {
                "total_missions": total,
                "success_rate": (row["successes"] / total * 100) if total > 0 else 0.0,
                "failure_rate": (row["failures"] / total * 100) if total > 0 else 0.0,
                "blocked_rate": (row["blocked"] / total * 100) if total > 0 else 0.0,
            },
            "performance": {
                "avg_duration_seconds": row["avg_duration"] or 0.0,
                "total_tool_calls": row["total_tool_calls"] or 0,
                "avg_tool_calls_per_mission": (row["total_tool_calls"] / total) if total > 0 else 0.0,
            },
            "costs": {
                "total_tokens": row["total_tokens"] or 0,
                "total_cost_usd": row["total_cost"] or 0.0,
                "avg_cost_per_mission": (row["total_cost"] / total) if total > 0 and row["total_cost"] else 0.0,
            },
            "mission_types": mission_breakdown,
        }

    def get_recent_missions(self, limit: int = 10) -> Sequence[dict[str, Any]]:
        """Retrieve recent mission executions.
        
        Args:
            limit: Maximum number of missions to return
            
        Returns:
            List of mission records
        """
        cursor = self._connection.cursor()
        cursor.execute(
            """
            SELECT mission_id, mission_type, status, duration_seconds, 
                   step_count, tool_call_count, timestamp, error_message
            FROM mission_metrics
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> AgentMonitor:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
