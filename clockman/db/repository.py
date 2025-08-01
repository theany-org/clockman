"""
Database repository for Clockman sessions.

This module provides the data access layer for time tracking sessions.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from .models import DailyStats, ProjectStats, TimeSession
from .schema import DatabaseManager


class SessionRepository:
    """Repository for managing time tracking sessions in the database."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize repository with database manager."""
        self.db_manager = db_manager

    def create_session(self, session: TimeSession) -> TimeSession:
        """Create a new time tracking session."""
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, task_name, description, tags, start_time, 
                                    end_time, is_active, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(session.id),
                    session.task_name,
                    session.description,
                    json.dumps(session.tags),
                    session.start_time.isoformat(),
                    session.end_time.isoformat() if session.end_time else None,
                    session.is_active,
                    json.dumps(session.metadata),
                ),
            )
            conn.commit()

        return session

    def get_session_by_id(self, session_id: UUID) -> Optional[TimeSession]:
        """Get a session by its ID."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (str(session_id),)
            )
            row = cursor.fetchone()

        return self._row_to_session(row) if row else None

    def get_active_session(self) -> Optional[TimeSession]:
        """Get the currently active session (there should be at most one)."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE is_active = 1 ORDER BY start_time DESC LIMIT 1"
            )
            row = cursor.fetchone()

        return self._row_to_session(row) if row else None

    def update_session(self, session: TimeSession) -> TimeSession:
        """Update an existing session."""
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                UPDATE sessions 
                SET task_name = ?, description = ?, tags = ?, start_time = ?,
                    end_time = ?, is_active = ?, metadata = ?
                WHERE id = ?
            """,
                (
                    session.task_name,
                    session.description,
                    json.dumps(session.tags),
                    session.start_time.isoformat(),
                    session.end_time.isoformat() if session.end_time else None,
                    session.is_active,
                    json.dumps(session.metadata),
                    str(session.id),
                ),
            )
            conn.commit()

        return session

    def delete_session(self, session_id: UUID) -> bool:
        """Delete a session by ID. Returns True if deleted, False if not found."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE id = ?", (str(session_id),)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_sessions_for_date(self, target_date: date) -> List[TimeSession]:
        """Get all sessions for a specific date."""
        start_datetime = datetime.combine(target_date, datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        end_datetime = start_datetime + timedelta(days=1)

        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM sessions 
                WHERE start_time >= ? AND start_time < ?
                ORDER BY start_time ASC
            """,
                (start_datetime.isoformat(), end_datetime.isoformat()),
            )
            rows = cursor.fetchall()

        return [self._row_to_session(row) for row in rows]

    def get_sessions_in_range(
        self, start_date: date, end_date: date
    ) -> List[TimeSession]:
        """Get all sessions within a date range (inclusive)."""
        start_datetime = datetime.combine(start_date, datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        end_datetime = datetime.combine(end_date, datetime.max.time()).replace(
            tzinfo=timezone.utc
        )

        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM sessions 
                WHERE start_time >= ? AND start_time <= ?
                ORDER BY start_time ASC
            """,
                (start_datetime.isoformat(), end_datetime.isoformat()),
            )
            rows = cursor.fetchall()

        return [self._row_to_session(row) for row in rows]

    def get_recent_sessions(self, limit: int = 10) -> List[TimeSession]:
        """Get the most recent sessions."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM sessions 
                ORDER BY start_time DESC 
                LIMIT ?
            """,
                (limit,),
            )
            rows = cursor.fetchall()

        return [self._row_to_session(row) for row in rows]

    def get_sessions_by_task(self, task_name: str) -> List[TimeSession]:
        """Get all sessions for a specific task."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM sessions 
                WHERE task_name = ?
                ORDER BY start_time DESC
            """,
                (task_name,),
            )
            rows = cursor.fetchall()

        return [self._row_to_session(row) for row in rows]

    def get_sessions_by_tag(self, tag: str) -> List[TimeSession]:
        """Get all sessions containing a specific tag."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM sessions 
                WHERE tags LIKE ?
                ORDER BY start_time DESC
            """,
                (f'%"{tag.lower()}"%',),
            )
            rows = cursor.fetchall()

        return [
            self._row_to_session(row)
            for row in rows
            if tag.lower() in json.loads(row["tags"])
        ]

    def get_daily_stats(self, target_date: date) -> DailyStats:
        """Get statistics for a specific date."""
        sessions = self.get_sessions_for_date(target_date)

        total_duration = 0.0
        all_tags = []
        session_durations = []
        unique_tasks = set()

        for session in sessions:
            if session.end_time:  # Only count completed sessions
                duration = session.duration or 0
                total_duration += duration
                session_durations.append(duration)
                all_tags.extend(session.tags)
                unique_tasks.add(session.task_name)

        # Count tag frequency
        tag_counts: Dict[str, int] = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Sort tags by frequency
        most_used_tags = sorted(
            tag_counts.keys(), key=lambda x: tag_counts[x], reverse=True
        )[:5]

        return DailyStats(
            date=target_date.isoformat(),
            total_duration=total_duration,
            session_count=len(
                [s for s in sessions if s.end_time]
            ),  # Only completed sessions
            unique_tasks=len(unique_tasks),
            most_used_tags=most_used_tags,
            longest_session=max(session_durations) if session_durations else None,
        )

    def get_project_stats(self, task_name: str) -> ProjectStats:
        """Get statistics for a specific project/task."""
        sessions = self.get_sessions_by_task(task_name)
        completed_sessions = [s for s in sessions if s.end_time]

        if not completed_sessions:
            return ProjectStats(
                task_name=task_name,
                total_duration=0.0,
                session_count=0,
                average_session=0.0,
                tags=[],
                first_session=None,
                last_session=None,
            )

        total_duration = sum(s.duration or 0 for s in completed_sessions)
        all_tags = []
        for session in completed_sessions:
            all_tags.extend(session.tags)

        # Get unique tags
        unique_tags = list(set(all_tags))

        return ProjectStats(
            task_name=task_name,
            total_duration=total_duration,
            session_count=len(completed_sessions),
            average_session=total_duration / len(completed_sessions),
            tags=unique_tags,
            first_session=min(s.start_time for s in completed_sessions),
            last_session=max(s.start_time for s in completed_sessions),
        )

    def _row_to_session(self, row: sqlite3.Row) -> TimeSession:
        """Convert a database row to a TimeSession model."""
        return TimeSession(
            id=UUID(row["id"]),
            task_name=row["task_name"],
            description=row["description"],
            tags=json.loads(row["tags"]),
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=(
                datetime.fromisoformat(row["end_time"]) if row["end_time"] else None
            ),
            is_active=bool(row["is_active"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
