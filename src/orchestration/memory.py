"""Mission memory and learning system for the agent runtime."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .types import AgentStep, MissionOutcome, MissionStatus


@dataclass(frozen=True)
class SuccessPattern:
    """Identified pattern in successful mission executions."""

    tool_sequence: tuple[str, ...]
    mission_type: str
    occurrence_count: int
    success_rate: float
    average_steps: float


class MissionMemory:
    """Stores and retrieves mission execution history for learning."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize mission memory with a database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses in-memory database.
        """
        self._db_path = db_path or ":memory:"
        self._conn = sqlite3.connect(str(self._db_path))
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create database tables for storing mission history."""
        cursor = self._conn.cursor()

        # Main mission executions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mission_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                mission_goal TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT,
                step_count INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                execution_data TEXT NOT NULL
            )
        """)

        # Individual steps table for pattern analysis
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER NOT NULL,
                step_number INTEGER NOT NULL,
                thought_content TEXT NOT NULL,
                thought_type TEXT NOT NULL,
                tool_name TEXT,
                tool_arguments TEXT,
                result_success INTEGER,
                result_output TEXT,
                result_error TEXT,
                FOREIGN KEY (execution_id) REFERENCES mission_executions(id)
            )
        """)

        # Create indexes for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mission_id 
            ON mission_executions(mission_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status 
            ON mission_executions(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON mission_executions(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_name 
            ON execution_steps(tool_name)
        """)

        self._conn.commit()

    def record_execution(self, mission_id: str, mission_goal: str, outcome: MissionOutcome) -> int:
        """Save mission execution details.

        Args:
            mission_id: Identifier for the mission type
            mission_goal: Natural language goal description
            outcome: Mission execution outcome with steps

        Returns:
            Database ID of the stored execution
        """
        cursor = self._conn.cursor()

        # Serialize full outcome for complete record
        execution_data = json.dumps({
            "status": outcome.status.value,
            "summary": outcome.summary,
            "steps": [
                {
                    "thought": {
                        "content": step.thought.content,
                        "type": step.thought.type.value,
                        "tool_call": (
                            {
                                "name": step.thought.tool_call.name,
                                "arguments": dict(step.thought.tool_call.arguments),
                            }
                            if step.thought.tool_call
                            else None
                        ),
                    },
                    "result": (
                        {
                            "success": step.result.success,
                            "output": step.result.output,
                            "error": step.result.error,
                        }
                        if step.result
                        else None
                    ),
                }
                for step in outcome.steps
            ],
        })

        # Store main execution record
        timestamp = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO mission_executions 
            (mission_id, mission_goal, status, summary, step_count, timestamp, execution_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mission_id,
                mission_goal,
                outcome.status.value,
                outcome.summary,
                len(outcome.steps),
                timestamp,
                execution_data,
            ),
        )

        execution_id = cursor.lastrowid

        # Store individual steps for pattern analysis
        for step_number, step in enumerate(outcome.steps, start=1):
            tool_name = step.thought.tool_call.name if step.thought.tool_call else None
            tool_arguments = (
                json.dumps(dict(step.thought.tool_call.arguments))
                if step.thought.tool_call
                else None
            )

            result_success = step.result.success if step.result else None
            result_output = json.dumps(step.result.output) if step.result and step.result.output else None
            result_error = step.result.error if step.result else None

            cursor.execute(
                """
                INSERT INTO execution_steps
                (execution_id, step_number, thought_content, thought_type, tool_name, 
                 tool_arguments, result_success, result_output, result_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    step_number,
                    step.thought.content,
                    step.thought.type.value,
                    tool_name,
                    tool_arguments,
                    result_success,
                    result_output,
                    result_error,
                ),
            )

        self._conn.commit()
        
        if execution_id is None:
            raise RuntimeError("Failed to insert mission execution record")
        
        return execution_id

    def find_similar(
        self, mission_id: str, *, limit: int = 10, status_filter: MissionStatus | None = None
    ) -> list[MissionOutcome]:
        """Retrieve similar past mission executions.

        Args:
            mission_id: Identifier of the mission type to match
            limit: Maximum number of results to return
            status_filter: If provided, only return missions with this status

        Returns:
            List of mission outcomes ordered by recency
        """
        cursor = self._conn.cursor()

        query = """
            SELECT execution_data
            FROM mission_executions
            WHERE mission_id = ?
        """
        params: list[Any] = [mission_id]

        if status_filter:
            query += " AND status = ?"
            params.append(status_filter.value)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        outcomes: list[MissionOutcome] = []
        for (execution_data,) in rows:
            data = json.loads(execution_data)
            outcome = self._deserialize_outcome(data)
            outcomes.append(outcome)

        return outcomes

    def extract_patterns(self, *, min_occurrences: int = 3) -> list[SuccessPattern]:
        """Identify successful tool sequences across mission executions.

        Args:
            min_occurrences: Minimum number of times a pattern must occur to be reported

        Returns:
            List of identified success patterns
        """
        cursor = self._conn.cursor()

        # Get all successful executions grouped by mission type
        cursor.execute("""
            SELECT 
                me.mission_id,
                me.id,
                GROUP_CONCAT(es.tool_name, '->') as tool_sequence,
                COUNT(es.id) as step_count
            FROM mission_executions me
            JOIN execution_steps es ON me.id = es.execution_id
            WHERE me.status = 'succeeded' AND es.tool_name IS NOT NULL
            GROUP BY me.mission_id, me.id
            ORDER BY me.mission_id, me.timestamp
        """)

        # Aggregate patterns by mission type and tool sequence
        pattern_stats: dict[tuple[str, str], dict[str, Any]] = {}

        for mission_id, execution_id, tool_sequence, step_count in cursor.fetchall():
            if not tool_sequence:
                continue

            key = (mission_id, tool_sequence)
            if key not in pattern_stats:
                pattern_stats[key] = {
                    "occurrences": 0,
                    "total_steps": 0,
                    "executions": [],
                }

            pattern_stats[key]["occurrences"] += 1
            pattern_stats[key]["total_steps"] += step_count
            pattern_stats[key]["executions"].append(execution_id)

        # Calculate success patterns
        patterns: list[SuccessPattern] = []

        for (mission_id, tool_sequence), stats in pattern_stats.items():
            if stats["occurrences"] < min_occurrences:
                continue

            # Calculate success rate for this pattern
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM mission_executions
                WHERE mission_id = ?
                """,
                (mission_id,),
            )
            total_attempts = cursor.fetchone()[0]

            success_rate = stats["occurrences"] / total_attempts if total_attempts > 0 else 0.0
            average_steps = stats["total_steps"] / stats["occurrences"]

            pattern = SuccessPattern(
                tool_sequence=tuple(tool_sequence.split("->")),
                mission_type=mission_id,
                occurrence_count=stats["occurrences"],
                success_rate=success_rate,
                average_steps=average_steps,
            )
            patterns.append(pattern)

        # Sort by success rate and occurrence count
        patterns.sort(key=lambda p: (p.success_rate, p.occurrence_count), reverse=True)

        return patterns

    def get_statistics(self) -> dict[str, Any]:
        """Get overall statistics about stored mission history.

        Returns:
            Dictionary with execution counts, success rates, etc.
        """
        cursor = self._conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM mission_executions")
        total_executions = cursor.fetchone()[0]

        cursor.execute("""
            SELECT status, COUNT(*) 
            FROM mission_executions 
            GROUP BY status
        """)
        status_counts = dict(cursor.fetchall())

        cursor.execute("""
            SELECT AVG(step_count) 
            FROM mission_executions 
            WHERE status = 'succeeded'
        """)
        avg_steps_success = cursor.fetchone()[0] or 0.0

        cursor.execute("""
            SELECT mission_id, COUNT(*) as count
            FROM mission_executions
            GROUP BY mission_id
            ORDER BY count DESC
            LIMIT 10
        """)
        top_missions = dict(cursor.fetchall())

        return {
            "total_executions": total_executions,
            "status_counts": status_counts,
            "success_rate": (
                status_counts.get("succeeded", 0) / total_executions if total_executions > 0 else 0.0
            ),
            "average_steps_on_success": avg_steps_success,
            "top_mission_types": top_missions,
        }

    def _deserialize_outcome(self, data: dict[str, Any]) -> MissionOutcome:
        """Reconstruct MissionOutcome from stored JSON data."""
        from .types import Thought, ThoughtType, ToolCall, ToolResult

        steps: list[AgentStep] = []
        for step_data in data.get("steps", []):
            thought_data = step_data["thought"]
            tool_call = None
            if thought_data.get("tool_call"):
                tc = thought_data["tool_call"]
                tool_call = ToolCall(name=tc["name"], arguments=tc["arguments"])

            thought = Thought(
                content=thought_data["content"],
                type=ThoughtType(thought_data["type"]),
                tool_call=tool_call,
            )

            result = None
            if step_data.get("result"):
                res = step_data["result"]
                result = ToolResult(
                    success=res["success"], output=res.get("output"), error=res.get("error")
                )

            steps.append(AgentStep(thought=thought, result=result))

        return MissionOutcome(
            status=MissionStatus(data["status"]),
            steps=tuple(steps),
            summary=data.get("summary"),
        )

    def clear_all(self) -> None:
        """Delete all stored mission history. Use with caution!"""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM execution_steps")
        cursor.execute("DELETE FROM mission_executions")
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> "MissionMemory":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit - closes connection."""
        self.close()
