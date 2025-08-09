"""
Core time tracking functionality for Clockman.

This module contains the main TimeTracker class that orchestrates session management.
"""

from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from ..db.models import DailyStats, Project, ProjectStats, TimeSession
from ..db.repository import ProjectRepository, SessionRepository
from ..db.schema import DatabaseManager
from ..integrations.events.events import EventType
from ..integrations.manager import IntegrationManager


class TimeTrackingError(Exception):
    """Base exception for time tracking operations."""

    pass


class ActiveSessionError(TimeTrackingError):
    """Raised when there's an issue with active session management."""

    pass


class SessionNotFoundError(TimeTrackingError):
    """Raised when a requested session cannot be found."""

    pass


class TimeTracker:
    """Main time tracking service that coordinates session management."""

    def __init__(self, data_dir: Path):
        """
        Initialize TimeTracker with the given data directory.

        Args:
            data_dir: Directory where the database and other data files are stored
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        db_path = self.data_dir / "clockman.db"
        self.db_manager = DatabaseManager(db_path)
        self.db_manager.initialize_database()

        # Initialize repositories
        self.session_repo = SessionRepository(self.db_manager)
        self.project_repo = ProjectRepository(self.db_manager)
        
        # Initialize integrations
        try:
            self.integration_manager = IntegrationManager(self.data_dir)
            self.integration_manager.initialize()
        except Exception as e:
            # Log error but don't fail initialization if integrations fail
            import logging
            logging.getLogger(__name__).error(f"Failed to initialize integrations: {e}")
            self.integration_manager = None

    def start_session(
        self,
        task_name: str,
        tags: Optional[List[str]] = None,
        description: Optional[str] = None,
        project_id: Optional[UUID] = None,
    ) -> UUID:
        """
        Start a new time tracking session.

        Args:
            task_name: Name of the task to track
            tags: Optional list of tags to associate with the task
            description: Optional description of the task
            project_id: Optional project ID to associate with the task

        Returns:
            UUID of the created session

        Raises:
            ActiveSessionError: If there's already an active session
        """
        # Check for existing active session
        active_session = self.session_repo.get_active_session()
        if active_session:
            raise ActiveSessionError(
                f"Session '{active_session.task_name}' is already active. "
                "Stop it before starting a new one."
            )

        # Create new session
        session = TimeSession(
            task_name=task_name.strip(),
            description=description.strip() if description else None,
            project_id=project_id,
            tags=tags or [],
            start_time=datetime.now(timezone.utc),
            end_time=None,
            is_active=True,
        )

        created_session = self.session_repo.create_session(session)
        
        # Emit session started event
        if self.integration_manager:
            try:
                self.integration_manager.emit_event(
                    EventType.SESSION_STARTED,
                    data={
                        "session_id": str(created_session.id),
                        "task_name": created_session.task_name,
                        "description": created_session.description,
                        "project_id": str(created_session.project_id) if created_session.project_id else None,
                        "tags": created_session.tags,
                        "start_time": created_session.start_time.isoformat(),
                    }
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to emit session started event: {e}")
        
        return created_session.id

    def stop_session(self, session_id: Optional[UUID] = None) -> Optional[TimeSession]:
        """
        Stop a time tracking session.

        Args:
            session_id: Optional specific session ID to stop. If None, stops the active session.

        Returns:
            The stopped session, or None if no session was active

        Raises:
            SessionNotFoundError: If the specified session ID doesn't exist
            ActiveSessionError: If no active session exists when session_id is None
        """
        if session_id:
            session = self.session_repo.get_session_by_id(session_id)
            if not session:
                raise SessionNotFoundError(f"Session with ID {session_id} not found")
        else:
            session = self.session_repo.get_active_session()
            if not session:
                raise ActiveSessionError("No active session to stop")

        # Stop the session
        session.stop(datetime.now(timezone.utc))
        stopped_session = self.session_repo.update_session(session)
        
        # Emit session stopped event
        if self.integration_manager and stopped_session:
            try:
                self.integration_manager.emit_event(
                    EventType.SESSION_STOPPED,
                    data={
                        "session_id": str(stopped_session.id),
                        "task_name": stopped_session.task_name,
                        "description": stopped_session.description,
                        "project_id": str(stopped_session.project_id) if stopped_session.project_id else None,
                        "tags": stopped_session.tags,
                        "start_time": stopped_session.start_time.isoformat(),
                        "end_time": stopped_session.end_time.isoformat() if stopped_session.end_time else None,
                        "duration_seconds": stopped_session.duration.total_seconds() if stopped_session.duration else None,
                    }
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to emit session stopped event: {e}")
        
        return stopped_session

    def get_active_session(self) -> Optional[TimeSession]:
        """
        Get the currently active session.

        Returns:
            The active session, or None if no session is active
        """
        return self.session_repo.get_active_session()

    def get_session_by_id(self, session_id: UUID) -> Optional[TimeSession]:
        """
        Get a session by its ID.

        Args:
            session_id: UUID of the session

        Returns:
            The session, or None if not found
        """
        return self.session_repo.get_session_by_id(session_id)

    def get_entries_for_date(self, target_date: date) -> List[TimeSession]:
        """
        Get all time entries for a specific date.

        Args:
            target_date: The date to get entries for

        Returns:
            List of time sessions for the date, ordered by start time
        """
        return self.session_repo.get_sessions_for_date(target_date)

    def get_entries_in_range(
        self, start_date: date, end_date: date
    ) -> List[TimeSession]:
        """
        Get all time entries within a date range.

        Args:
            start_date: Start of the date range (inclusive)
            end_date: End of the date range (inclusive)

        Returns:
            List of time sessions in the range, ordered by start time
        """
        return self.session_repo.get_sessions_in_range(start_date, end_date)

    def get_recent_entries(self, limit: int = 10) -> List[TimeSession]:
        """
        Get the most recent time entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent time sessions, ordered by start time (newest first)
        """
        return self.session_repo.get_recent_sessions(limit)

    def get_entries_by_task(self, task_name: str) -> List[TimeSession]:
        """
        Get all entries for a specific task.

        Args:
            task_name: Name of the task

        Returns:
            List of sessions for the task, ordered by start time (newest first)
        """
        return self.session_repo.get_sessions_by_task(task_name)

    def get_entries_by_tag(self, tag: str) -> List[TimeSession]:
        """
        Get all entries containing a specific tag.

        Args:
            tag: Tag to search for

        Returns:
            List of sessions with the tag, ordered by start time (newest first)
        """
        return self.session_repo.get_sessions_by_tag(tag)

    def get_daily_stats(self, target_date: date) -> DailyStats:
        """
        Get daily statistics for a specific date.

        Args:
            target_date: Date to get statistics for

        Returns:
            Daily statistics including total time, session count, etc.
        """
        return self.session_repo.get_daily_stats(target_date)

    def get_project_stats(self, task_name: str) -> ProjectStats:
        """
        Get statistics for a specific project/task.

        Args:
            task_name: Name of the task/project

        Returns:
            Project statistics including total time, session count, etc.
        """
        return self.session_repo.get_project_stats(task_name)

    def delete_session(self, session_id: UUID) -> bool:
        """
        Delete a session by ID.

        Args:
            session_id: UUID of the session to delete

        Returns:
            True if the session was deleted, False if it didn't exist
        """
        # Get session info before deletion for event
        session = self.session_repo.get_session_by_id(session_id)
        
        success = self.session_repo.delete_session(session_id)
        
        # Emit session deleted event if deletion was successful
        if success and session and self.integration_manager:
            try:
                self.integration_manager.emit_event(
                    EventType.SESSION_DELETED,
                    data={
                        "session_id": str(session.id),
                        "task_name": session.task_name,
                        "description": session.description,
                        "project_id": str(session.project_id) if session.project_id else None,
                        "tags": session.tags,
                    }
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to emit session deleted event: {e}")
        
        return success

    def update_session(
        self,
        session_id: UUID,
        task_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[TimeSession]:
        """
        Update a session's metadata.

        Args:
            session_id: UUID of the session to update
            task_name: New task name (optional)
            description: New description (optional)
            tags: New tags list (optional)

        Returns:
            Updated session, or None if session not found

        Raises:
            SessionNotFoundError: If the session doesn't exist
        """
        session = self.session_repo.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session with ID {session_id} not found")

        # Update fields if provided
        if task_name is not None:
            session.task_name = task_name.strip()
        if description is not None:
            session.description = description.strip() if description else None
        if tags is not None:
            session.tags = tags

        updated_session = self.session_repo.update_session(session)
        
        # Emit session updated event
        if self.integration_manager and updated_session:
            try:
                self.integration_manager.emit_event(
                    EventType.SESSION_UPDATED,
                    data={
                        "session_id": str(updated_session.id),
                        "task_name": updated_session.task_name,
                        "description": updated_session.description,
                        "project_id": str(updated_session.project_id) if updated_session.project_id else None,
                        "tags": updated_session.tags,
                    }
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to emit session updated event: {e}")
        
        return updated_session

    def get_database_stats(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dictionary with database statistics
        """
        return self.db_manager.get_database_stats()

    # Project management methods

    def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        parent_id: Optional[UUID] = None,
        default_tags: Optional[List[str]] = None,
    ) -> UUID:
        """
        Create a new project.

        Args:
            name: Project name
            description: Optional project description
            parent_id: Optional parent project ID for hierarchy
            default_tags: Optional default tags for tasks in this project

        Returns:
            UUID of the created project

        Raises:
            TimeTrackingError: If a project with the same name already exists
        """
        # Check for existing project with same name
        existing_project = self.project_repo.get_project_by_name(name.strip())
        if existing_project:
            raise TimeTrackingError(f"Project '{name}' already exists")

        # Create new project
        project = Project(
            name=name.strip(),
            description=description.strip() if description else None,
            parent_id=parent_id,
            default_tags=default_tags or [],
            is_active=True,
        )

        created_project = self.project_repo.create_project(project)
        
        # Emit project created event
        if self.integration_manager:
            try:
                self.integration_manager.emit_event(
                    EventType.PROJECT_CREATED,
                    data={
                        "project_id": str(created_project.id),
                        "project_name": created_project.name,
                        "description": created_project.description,
                        "parent_id": str(created_project.parent_id) if created_project.parent_id else None,
                        "default_tags": created_project.default_tags,
                    }
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to emit project created event: {e}")
        
        return created_project.id

    def get_project_by_id(self, project_id: UUID) -> Optional[Project]:
        """Get a project by its ID."""
        return self.project_repo.get_project_by_id(project_id)

    def get_project_by_name(self, name: str) -> Optional[Project]:
        """Get a project by its name."""
        return self.project_repo.get_project_by_name(name)

    def get_all_projects(self) -> List[Project]:
        """Get all projects."""
        return self.project_repo.get_all_projects()

    def get_active_projects(self) -> List[Project]:
        """Get all active projects."""
        return self.project_repo.get_active_projects()

    def get_project_hierarchy(self) -> dict:
        """Get the complete project hierarchy."""
        return self.project_repo.get_project_hierarchy()

    def update_project(
        self,
        project_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parent_id: Optional[UUID] = None,
        default_tags: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Project]:
        """
        Update a project.

        Args:
            project_id: UUID of the project to update
            name: New project name (optional)
            description: New description (optional)
            parent_id: New parent project ID (optional)
            default_tags: New default tags (optional)
            is_active: New active status (optional)

        Returns:
            Updated project, or None if project not found

        Raises:
            SessionNotFoundError: If the project doesn't exist
        """
        project = self.project_repo.get_project_by_id(project_id)
        if not project:
            raise SessionNotFoundError(f"Project with ID {project_id} not found")

        # Update fields if provided
        if name is not None:
            # Check for name conflicts
            existing = self.project_repo.get_project_by_name(name.strip())
            if existing and existing.id != project_id:
                raise TimeTrackingError(f"Project '{name}' already exists")
            project.name = name.strip()
        if description is not None:
            project.description = description.strip() if description else None
        if parent_id is not None:
            project.parent_id = parent_id
        if default_tags is not None:
            project.default_tags = default_tags
        if is_active is not None:
            project.is_active = is_active

        return self.project_repo.update_project(project)

    def delete_project(self, project_id: UUID) -> bool:
        """
        Delete a project by ID.

        Args:
            project_id: UUID of the project to delete

        Returns:
            True if the project was deleted, False if it didn't exist
        """
        # Get project info before deletion for event
        project = self.project_repo.get_project_by_id(project_id)
        
        success = self.project_repo.delete_project(project_id)
        
        # Emit project deleted event if deletion was successful
        if success and project and self.integration_manager:
            try:
                self.integration_manager.emit_event(
                    EventType.PROJECT_DELETED,
                    data={
                        "project_id": str(project.id),
                        "project_name": project.name,
                        "description": project.description,
                        "parent_id": str(project.parent_id) if project.parent_id else None,
                        "default_tags": project.default_tags,
                    }
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to emit project deleted event: {e}")
        
        return success

    def get_sessions_by_project(self, project_id: UUID) -> List[TimeSession]:
        """Get all sessions for a specific project."""
        with self.session_repo.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM sessions 
                WHERE project_id = ?
                ORDER BY start_time DESC
            """,
                (str(project_id),),
            )
            rows = cursor.fetchall()

        return [self.session_repo._row_to_session(row) for row in rows]
    
    def shutdown(self) -> None:
        """
        Shutdown the time tracker and clean up resources.
        
        This should be called when the application is closing to ensure
        proper cleanup of integration resources.
        """
        if self.integration_manager:
            try:
                self.integration_manager.shutdown()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error shutting down integration manager: {e}")
        
        # Close database connection if needed
        if hasattr(self.db_manager, 'close'):
            try:
                self.db_manager.close()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error closing database: {e}")
