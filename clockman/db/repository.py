"""
Database repository for Clockman sessions.

This module provides the data access layer for time tracking sessions.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from uuid import UUID

from .models import DailyStats, Project, ProjectStats, TimeSession
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
                INSERT INTO sessions (id, task_name, description, project_id, tags, start_time, 
                                    end_time, is_active, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(session.id),
                    session.task_name,
                    session.description,
                    str(session.project_id) if session.project_id else None,
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
                SET task_name = ?, description = ?, project_id = ?, tags = ?, start_time = ?,
                    end_time = ?, is_active = ?, metadata = ?
                WHERE id = ?
            """,
                (
                    session.task_name,
                    session.description,
                    str(session.project_id) if session.project_id else None,
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

    def get_all_sessions(self) -> List[TimeSession]:
        """Get all sessions in the database."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM sessions 
                ORDER BY start_time DESC
            """
            )
            rows = cursor.fetchall()

        return [self._row_to_session(row) for row in rows]

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
        session = TimeSession(
            id=UUID(row["id"]),
            task_name=row["task_name"],
            description=row["description"],
            project_id=UUID(row["project_id"]) if row["project_id"] else None,
            tags=json.loads(row["tags"]),
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=(
                datetime.fromisoformat(row["end_time"]) if row["end_time"] else None
            ),
            is_active=bool(row["is_active"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

        # Add database-specific fields as metadata for CSV export
        session.metadata["created_at"] = (
            row["created_at"] if "created_at" in row.keys() else None
        )
        session.metadata["updated_at"] = (
            row["updated_at"] if "updated_at" in row.keys() else None
        )

        return session


class ProjectRepository:
    """Repository for managing projects in the database."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize repository with database manager."""
        self.db_manager = db_manager

    def create_project(self, project: Project) -> Project:
        """Create a new project."""
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, description, parent_id, is_active, 
                                    default_tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(project.id),
                    project.name,
                    project.description,
                    str(project.parent_id) if project.parent_id else None,
                    project.is_active,
                    json.dumps(project.default_tags),
                    json.dumps(project.metadata),
                ),
            )
            conn.commit()

        return project

    def get_project_by_id(self, project_id: UUID) -> Optional[Project]:
        """Get a project by its ID."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (str(project_id),)
            )
            row = cursor.fetchone()

        return self._row_to_project(row) if row else None

    def get_project_by_name(self, name: str) -> Optional[Project]:
        """Get a project by its name."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM projects WHERE name = ?", (name,))
            row = cursor.fetchone()

        return self._row_to_project(row) if row else None

    def get_all_projects(self) -> List[Project]:
        """Get all projects."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM projects ORDER BY name ASC")
            rows = cursor.fetchall()

        return [self._row_to_project(row) for row in rows]

    def get_active_projects(self) -> List[Project]:
        """Get all active projects."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM projects WHERE is_active = 1 ORDER BY name ASC"
            )
            rows = cursor.fetchall()

        return [self._row_to_project(row) for row in rows]

    def get_projects_by_parent(self, parent_id: Optional[UUID]) -> List[Project]:
        """Get projects by parent ID (None for root projects)."""
        with self.db_manager.get_connection() as conn:
            if parent_id is None:
                cursor = conn.execute(
                    "SELECT * FROM projects WHERE parent_id IS NULL ORDER BY name ASC"
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM projects WHERE parent_id = ? ORDER BY name ASC",
                    (str(parent_id),),
                )
            rows = cursor.fetchall()

        return [self._row_to_project(row) for row in rows]

    def update_project(self, project: Project) -> Project:
        """Update an existing project."""
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                UPDATE projects 
                SET name = ?, description = ?, parent_id = ?, is_active = ?,
                    default_tags = ?, metadata = ?
                WHERE id = ?
            """,
                (
                    project.name,
                    project.description,
                    str(project.parent_id) if project.parent_id else None,
                    project.is_active,
                    json.dumps(project.default_tags),
                    json.dumps(project.metadata),
                    str(project.id),
                ),
            )
            conn.commit()

        return project

    def delete_project(self, project_id: UUID) -> bool:
        """Delete a project by ID. Returns True if deleted, False if not found."""
        with self.db_manager.get_connection() as conn:
            # First, unlink any sessions from this project
            conn.execute(
                "UPDATE sessions SET project_id = NULL WHERE project_id = ?",
                (str(project_id),),
            )

            # Delete the project
            cursor = conn.execute(
                "DELETE FROM projects WHERE id = ?", (str(project_id),)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_project_hierarchy(self) -> Dict[str, Any]:
        """Get the complete project hierarchy as a nested structure."""
        projects = self.get_all_projects()
        project_map = {str(p.id): p for p in projects}

        def build_tree(parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
            children = []
            for project in projects:
                if (parent_id is None and project.parent_id is None) or (
                    parent_id is not None
                    and project.parent_id
                    and str(project.parent_id) == parent_id
                ):
                    children.append(
                        {"project": project, "children": build_tree(str(project.id))}
                    )
            return children

        return {"hierarchy": build_tree()}

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        """Convert a database row to a Project model."""
        return Project(
            id=UUID(row["id"]),
            name=row["name"],
            description=row["description"],
            parent_id=UUID(row["parent_id"]) if row["parent_id"] else None,
            is_active=bool(row["is_active"]),
            default_tags=json.loads(row["default_tags"]) if row["default_tags"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
