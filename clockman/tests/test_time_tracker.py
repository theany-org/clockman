"""
Tests for time_tracker core module (clockman.core.time_tracker).

This module tests the core time tracking functionality including session management,
error handling, and business logic.
"""

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from clockman.core.time_tracker import (
    ActiveSessionError,
    SessionNotFoundError,
    TimeTracker,
    TimeTrackingError,
)
from clockman.db.models import DailyStats, ProjectStats
from clockman.db.repository import SessionRepository
from clockman.db.schema import DatabaseManager


class TestTimeTracker:
    """Test cases for TimeTracker class."""

    def test_init_creates_data_directory(self, temp_dir: Path) -> None:
        """Test that TimeTracker creates data directory on initialization."""
        # Arrange
        data_dir = temp_dir / "test_data"
        assert not data_dir.exists()

        # Act
        clockman = TimeTracker(data_dir)

        # Assert
        assert data_dir.exists()
        assert clockman.data_dir == data_dir
        assert isinstance(clockman.db_manager, DatabaseManager)
        assert isinstance(clockman.session_repo, SessionRepository)

    def test_init_with_existing_directory(self, temp_dir: Path) -> None:
        """Test TimeTracker initialization with existing directory."""
        # Arrange
        data_dir = temp_dir / "existing"
        data_dir.mkdir()

        # Act
        clockman = TimeTracker(data_dir)

        # Assert
        assert clockman.data_dir == data_dir

    def test_start_session_success(self, time_tracker: TimeTracker) -> None:
        """Test successful session start."""
        # Act
        session_id = time_tracker.start_session(
            task_name="Test Task",
            tags=["test", "development"],
            description="A test task",
        )

        # Assert
        assert isinstance(session_id, UUID)

        # Verify session was created
        session = time_tracker.get_session_by_id(session_id)
        assert session is not None
        assert session.task_name == "Test Task"
        assert session.description == "A test task"
        assert set(session.tags) == {"test", "development"}
        assert session.is_active is True
        assert session.end_time is None

    def test_start_session_with_minimal_params(self, time_tracker: TimeTracker) -> None:
        """Test starting session with minimal parameters."""
        # Act
        session_id = time_tracker.start_session("Simple Task")

        # Assert
        session = time_tracker.get_session_by_id(session_id)
        assert session is not None
        assert session.task_name == "Simple Task"
        assert session.description is None
        assert session.tags == []

    def test_start_session_trims_whitespace(self, time_tracker: TimeTracker) -> None:
        """Test that task name and description are trimmed."""
        # Act
        session_id = time_tracker.start_session(
            task_name="  Test Task  ",
            description="  Test description  ",
        )

        # Assert
        session = time_tracker.get_session_by_id(session_id)
        assert session is not None
        assert session.task_name == "Test Task"
        assert session.description == "Test description"

    def test_start_session_with_active_session_raises_error(
        self, time_tracker: TimeTracker
    ) -> None:
        """Test that starting session with active session raises error."""
        # Arrange
        time_tracker.start_session("First Task")

        # Act & Assert
        with pytest.raises(ActiveSessionError) as exc_info:
            time_tracker.start_session("Second Task")

        assert "already active" in str(exc_info.value)
        assert "First Task" in str(exc_info.value)

    def test_stop_session_success(self, time_tracker: TimeTracker) -> None:
        """Test successful session stop."""
        # Arrange
        session_id = time_tracker.start_session("Test Task")
        original_session = time_tracker.get_session_by_id(session_id)
        assert original_session is not None
        assert original_session.is_active

        # Act
        stopped_session = time_tracker.stop_session()

        # Assert
        assert stopped_session is not None
        assert stopped_session.id == session_id
        assert stopped_session.is_active is False
        assert stopped_session.end_time is not None
        assert stopped_session.end_time > stopped_session.start_time

    def test_stop_session_by_id(self, time_tracker: TimeTracker) -> None:
        """Test stopping session by specific ID."""
        # Arrange
        session_id = time_tracker.start_session("Test Task")

        # Act
        stopped_session = time_tracker.stop_session(session_id)

        # Assert
        assert stopped_session is not None
        assert stopped_session.id == session_id
        assert stopped_session.is_active is False

    def test_stop_session_with_no_active_session_raises_error(
        self, time_tracker: TimeTracker
    ) -> None:
        """Test stopping session when none is active raises error."""
        # Act & Assert
        with pytest.raises(ActiveSessionError) as exc_info:
            time_tracker.stop_session()

        assert "No active session to stop" in str(exc_info.value)

    def test_stop_session_with_invalid_id_raises_error(
        self, time_tracker: TimeTracker
    ) -> None:
        """Test stopping session with invalid ID raises error."""
        # Arrange
        invalid_id = uuid4()

        # Act & Assert
        with pytest.raises(SessionNotFoundError) as exc_info:
            time_tracker.stop_session(invalid_id)

        assert str(invalid_id) in str(exc_info.value)

    def test_get_active_session_with_active(self, time_tracker: TimeTracker) -> None:
        """Test getting active session when one exists."""
        # Arrange
        session_id = time_tracker.start_session("Active Task")

        # Act
        active_session = time_tracker.get_active_session()

        # Assert
        assert active_session is not None
        assert active_session.id == session_id
        assert active_session.is_active

    def test_get_active_session_with_none_active(
        self, time_tracker: TimeTracker
    ) -> None:
        """Test getting active session when none exists."""
        # Act
        active_session = time_tracker.get_active_session()

        # Assert
        assert active_session is None

    def test_get_session_by_id_exists(self, time_tracker: TimeTracker) -> None:
        """Test getting session by ID when it exists."""
        # Arrange
        session_id = time_tracker.start_session("Test Task")

        # Act
        session = time_tracker.get_session_by_id(session_id)

        # Assert
        assert session is not None
        assert session.id == session_id

    def test_get_session_by_id_not_exists(self, time_tracker: TimeTracker) -> None:
        """Test getting session by ID when it doesn't exist."""
        # Arrange
        invalid_id = uuid4()

        # Act
        session = time_tracker.get_session_by_id(invalid_id)

        # Assert
        assert session is None

    def test_get_entries_for_date(self, time_tracker: TimeTracker) -> None:
        """Test getting entries for a specific date."""
        # Arrange
        target_date = date(2024, 1, 1)

        # Create sessions on target date
        with patch("clockman.core.time_tracker.datetime") as mock_datetime:
            # Create a time sequence for start/stop operations
            time_sequence = [
                datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),  # start task 1
                datetime(2024, 1, 1, 10, 1, 0, tzinfo=timezone.utc),  # stop task 1
                datetime(2024, 1, 1, 10, 2, 0, tzinfo=timezone.utc),  # start task 2
                datetime(2024, 1, 1, 10, 3, 0, tzinfo=timezone.utc),  # stop task 2
            ]
            mock_datetime.now.side_effect = time_sequence
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            session_id1 = time_tracker.start_session("Task 1")
            time_tracker.stop_session(session_id1)

            session_id2 = time_tracker.start_session("Task 2")
            time_tracker.stop_session(session_id2)

        # Act
        entries = time_tracker.get_entries_for_date(target_date)

        # Assert
        assert len(entries) == 2
        task_names = [entry.task_name for entry in entries]
        assert "Task 1" in task_names
        assert "Task 2" in task_names

    def test_get_entries_in_range(self, time_tracker: TimeTracker) -> None:
        """Test getting entries within a date range."""
        # Arrange
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 3)

        # Create sessions across different dates
        with patch("clockman.core.time_tracker.datetime") as mock_datetime:
            # Create a time sequence for start/stop operations across multiple dates
            time_sequence = [
                # Session 1 on 2024-01-01
                datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),  # start task 1
                datetime(2024, 1, 1, 10, 1, 0, tzinfo=timezone.utc),  # stop task 1
                # Session 2 on 2024-01-02
                datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc),  # start task 2
                datetime(2024, 1, 2, 10, 1, 0, tzinfo=timezone.utc),  # stop task 2
                # Session 3 on 2024-01-05 (outside range)
                datetime(2024, 1, 5, 10, 0, 0, tzinfo=timezone.utc),  # start task 3
                datetime(2024, 1, 5, 10, 1, 0, tzinfo=timezone.utc),  # stop task 3
            ]
            mock_datetime.now.side_effect = time_sequence
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            session_id1 = time_tracker.start_session("Task 1")
            time_tracker.stop_session(session_id1)

            session_id2 = time_tracker.start_session("Task 2")
            time_tracker.stop_session(session_id2)

            session_id3 = time_tracker.start_session("Task 3")
            time_tracker.stop_session(session_id3)

        # Act
        entries = time_tracker.get_entries_in_range(start_date, end_date)

        # Assert
        assert len(entries) == 2
        task_names = [entry.task_name for entry in entries]
        assert "Task 1" in task_names
        assert "Task 2" in task_names
        assert "Task 3" not in task_names

    def test_get_recent_entries(self, time_tracker: TimeTracker) -> None:
        """Test getting recent entries with limit."""
        # Arrange
        # Create multiple sessions
        session_ids = []
        for i in range(5):
            session_id = time_tracker.start_session(f"Task {i + 1}")
            time_tracker.stop_session(session_id)
            session_ids.append(session_id)

        # Act
        entries = time_tracker.get_recent_entries(limit=3)

        # Assert
        assert len(entries) == 3
        # Should be most recent first
        assert entries[0].task_name == "Task 5"
        assert entries[1].task_name == "Task 4"
        assert entries[2].task_name == "Task 3"

    def test_get_entries_by_task(self, time_tracker: TimeTracker) -> None:
        """Test getting entries by task name."""
        # Arrange
        session_id1 = time_tracker.start_session("Task A")
        time_tracker.stop_session(session_id1)

        session_id2 = time_tracker.start_session("Task B")
        time_tracker.stop_session(session_id2)

        session_id3 = time_tracker.start_session("Task A")  # Same task name
        time_tracker.stop_session(session_id3)

        # Act
        entries = time_tracker.get_entries_by_task("Task A")

        # Assert
        assert len(entries) == 2
        assert all(entry.task_name == "Task A" for entry in entries)

    def test_get_entries_by_tag(self, time_tracker: TimeTracker) -> None:
        """Test getting entries by tag."""
        # Arrange
        session_id1 = time_tracker.start_session(
            "Task 1", tags=["development", "urgent"]
        )
        time_tracker.stop_session(session_id1)

        session_id2 = time_tracker.start_session("Task 2", tags=["testing"])
        time_tracker.stop_session(session_id2)

        session_id3 = time_tracker.start_session(
            "Task 3", tags=["development", "review"]
        )
        time_tracker.stop_session(session_id3)

        # Act
        entries = time_tracker.get_entries_by_tag("development")

        # Assert
        assert len(entries) == 2
        assert all("development" in entry.tags for entry in entries)

    def test_get_daily_stats(self, time_tracker: TimeTracker) -> None:
        """Test getting daily statistics."""
        # Arrange
        target_date = date(2024, 1, 1)

        with patch("clockman.core.time_tracker.datetime") as mock_datetime:
            # Create a time sequence for start/stop operations
            time_sequence = [
                datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),  # start task 1
                datetime(2024, 1, 1, 10, 1, 0, tzinfo=timezone.utc),  # stop task 1
                datetime(2024, 1, 1, 10, 2, 0, tzinfo=timezone.utc),  # start task 2
                datetime(2024, 1, 1, 10, 3, 0, tzinfo=timezone.utc),  # stop task 2
            ]
            mock_datetime.now.side_effect = time_sequence
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # Create and complete sessions
            session_id1 = time_tracker.start_session("Task 1", tags=["dev"])
            time_tracker.stop_session(session_id1)

            session_id2 = time_tracker.start_session("Task 2", tags=["test"])
            time_tracker.stop_session(session_id2)

        # Act
        stats = time_tracker.get_daily_stats(target_date)

        # Assert
        assert isinstance(stats, DailyStats)
        assert stats.date == target_date.isoformat()
        assert stats.session_count == 2
        assert stats.unique_tasks == 2
        assert stats.total_duration > 0

    def test_get_project_stats(self, time_tracker: TimeTracker) -> None:
        """Test getting project statistics."""
        # Arrange
        task_name = "Project Alpha"

        # Create multiple sessions for the same task
        session_id1 = time_tracker.start_session(task_name, tags=["backend"])
        time_tracker.stop_session(session_id1)

        session_id2 = time_tracker.start_session(task_name, tags=["frontend"])
        time_tracker.stop_session(session_id2)

        # Act
        stats = time_tracker.get_project_stats(task_name)

        # Assert
        assert isinstance(stats, ProjectStats)
        assert stats.task_name == task_name
        assert stats.session_count == 2
        assert stats.total_duration > 0
        assert stats.average_session > 0
        assert set(stats.tags) == {"backend", "frontend"}

    def test_delete_session(self, time_tracker: TimeTracker) -> None:
        """Test deleting a session."""
        # Arrange
        session_id = time_tracker.start_session("Test Task")
        time_tracker.stop_session(session_id)

        # Verify session exists
        assert time_tracker.get_session_by_id(session_id) is not None

        # Act
        result = time_tracker.delete_session(session_id)

        # Assert
        assert result is True
        assert time_tracker.get_session_by_id(session_id) is None

    def test_delete_nonexistent_session(self, time_tracker: TimeTracker) -> None:
        """Test deleting a non-existent session."""
        # Arrange
        invalid_id = uuid4()

        # Act
        result = time_tracker.delete_session(invalid_id)

        # Assert
        assert result is False

    def test_update_session_success(self, time_tracker: TimeTracker) -> None:
        """Test successful session update."""
        # Arrange
        session_id = time_tracker.start_session("Original Task", description="Original")
        time_tracker.stop_session(session_id)

        # Act
        updated_session = time_tracker.update_session(
            session_id,
            task_name="Updated Task",
            description="Updated description",
            tags=["updated", "test"],
        )

        # Assert
        assert updated_session is not None
        assert updated_session.task_name == "Updated Task"
        assert updated_session.description == "Updated description"
        assert set(updated_session.tags) == {"updated", "test"}

    def test_update_session_partial(self, time_tracker: TimeTracker) -> None:
        """Test partial session update."""
        # Arrange
        session_id = time_tracker.start_session(
            "Task", description="Description", tags=["tag1"]
        )
        time_tracker.stop_session(session_id)

        # Act - only update task name
        updated_session = time_tracker.update_session(session_id, task_name="New Task")

        # Assert
        assert updated_session is not None
        assert updated_session.task_name == "New Task"
        assert updated_session.description == "Description"  # Unchanged
        assert updated_session.tags == ["tag1"]  # Unchanged

    def test_update_session_trims_whitespace(self, time_tracker: TimeTracker) -> None:
        """Test that update trims whitespace."""
        # Arrange
        session_id = time_tracker.start_session("Task")
        time_tracker.stop_session(session_id)

        # Act
        updated_session = time_tracker.update_session(
            session_id,
            task_name="  Updated Task  ",
            description="  Updated description  ",
        )

        # Assert
        assert updated_session is not None
        assert updated_session.task_name == "Updated Task"
        assert updated_session.description == "Updated description"

    def test_update_session_clear_description(self, time_tracker: TimeTracker) -> None:
        """Test clearing description with empty string."""
        # Arrange
        session_id = time_tracker.start_session("Task", description="Original")
        time_tracker.stop_session(session_id)

        # Act
        updated_session = time_tracker.update_session(session_id, description="")

        # Assert
        assert updated_session is not None
        assert updated_session.description is None

    def test_update_session_nonexistent_raises_error(
        self, time_tracker: TimeTracker
    ) -> None:
        """Test updating non-existent session raises error."""
        # Arrange
        invalid_id = uuid4()

        # Act & Assert
        with pytest.raises(SessionNotFoundError) as exc_info:
            time_tracker.update_session(invalid_id, task_name="New Task")

        assert str(invalid_id) in str(exc_info.value)

    def test_get_database_stats(self, time_tracker: TimeTracker) -> None:
        """Test getting database statistics."""
        # Arrange
        session_id = time_tracker.start_session("Test Task")

        # Act
        stats = time_tracker.get_database_stats()

        # Assert
        assert isinstance(stats, dict)
        assert "total_sessions" in stats
        assert "active_sessions" in stats
        assert stats["total_sessions"] >= 1
        assert stats["active_sessions"] == 1


class TestTimeTrackingExceptions:
    """Test custom exceptions."""

    def test_time_tracking_error_inheritance(self) -> None:
        """Test TimeTrackingError is base exception."""
        # Act & Assert
        assert issubclass(ActiveSessionError, TimeTrackingError)
        assert issubclass(SessionNotFoundError, TimeTrackingError)
        assert issubclass(TimeTrackingError, Exception)

    def test_active_session_error_message(self) -> None:
        """Test ActiveSessionError message."""
        # Act
        error = ActiveSessionError("Test message")

        # Assert
        assert str(error) == "Test message"

    def test_session_not_found_error_message(self) -> None:
        """Test SessionNotFoundError message."""
        # Act
        error = SessionNotFoundError("Session not found")

        # Assert
        assert str(error) == "Session not found"


@pytest.mark.integration
class TestTimeTrackerIntegration:
    """Integration tests for TimeTracker with real database."""

    def test_complete_workflow(self, time_tracker: TimeTracker) -> None:
        """Test complete time tracking workflow."""
        # Start session
        session_id = time_tracker.start_session(
            "Integration Test",
            tags=["integration", "test"],
            description="Full workflow test",
        )

        # Verify active session
        active = time_tracker.get_active_session()
        assert active is not None
        assert active.id == session_id

        # Stop session
        stopped = time_tracker.stop_session()
        assert stopped is not None
        assert not stopped.is_active

        # Verify no active session
        assert time_tracker.get_active_session() is None

        # Get by ID
        retrieved = time_tracker.get_session_by_id(session_id)
        assert retrieved is not None
        assert retrieved.task_name == "Integration Test"

        # Update session
        updated = time_tracker.update_session(
            session_id, task_name="Updated Integration Test"
        )
        assert updated is not None
        assert updated.task_name == "Updated Integration Test"

        # Get stats
        stats = time_tracker.get_database_stats()
        assert stats["total_sessions"] >= 1
        assert stats["active_sessions"] == 0

        # Delete session
        deleted = time_tracker.delete_session(session_id)
        assert deleted is True
        assert time_tracker.get_session_by_id(session_id) is None

    def test_multiple_sessions_same_task(self, time_tracker: TimeTracker) -> None:
        """Test multiple sessions for the same task."""
        # Create multiple sessions for same task
        task_name = "Recurring Task"
        session_ids = []

        for i in range(3):
            session_id = time_tracker.start_session(f"{task_name} {i+1}")
            time_tracker.stop_session(session_id)
            session_ids.append(session_id)

        # Get recent entries
        recent = time_tracker.get_recent_entries(limit=5)
        assert len(recent) == 3

        # Verify ordering (most recent first)
        assert recent[0].task_name == f"{task_name} 3"
        assert recent[1].task_name == f"{task_name} 2"
        assert recent[2].task_name == f"{task_name} 1"
