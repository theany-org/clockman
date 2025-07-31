"""
Core time tracking functionality for TrackIt.

This module contains the main TimeTracker class that orchestrates session management.
"""

from datetime import datetime, timezone, date
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from ..db.models import TimeSession, DailyStats, ProjectStats
from ..db.schema import DatabaseManager
from ..db.repository import SessionRepository


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
        db_path = self.data_dir / "trackit.db"
        self.db_manager = DatabaseManager(db_path)
        self.db_manager.initialize_database()
        
        # Initialize repository
        self.session_repo = SessionRepository(self.db_manager)
    
    def start_session(
        self, 
        task_name: str, 
        tags: Optional[List[str]] = None, 
        description: Optional[str] = None
    ) -> UUID:
        """
        Start a new time tracking session.
        
        Args:
            task_name: Name of the task to track
            tags: Optional list of tags to associate with the task
            description: Optional description of the task
            
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
            tags=tags or [],
            start_time=datetime.now(timezone.utc),
            is_active=True
        )
        
        created_session = self.session_repo.create_session(session)
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
        return self.session_repo.update_session(session)
    
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
    
    def get_entries_in_range(self, start_date: date, end_date: date) -> List[TimeSession]:
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
        return self.session_repo.delete_session(session_id)
    
    def update_session(
        self,
        session_id: UUID,
        task_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
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
        
        return self.session_repo.update_session(session)
    
    def get_database_stats(self) -> dict:
        """
        Get database statistics.
        
        Returns:
            Dictionary with database statistics
        """
        return self.db_manager.get_database_stats()