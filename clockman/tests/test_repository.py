"""
Tests for database repository (clockman.db.repository).

This module tests the data access layer including CRUD operations,
queries, and database interactions.
"""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from clockman.db.models import DailyStats, ProjectStats, TimeSession
from clockman.db.repository import SessionRepository


class TestSessionRepository:
    """Test cases for SessionRepository class."""

    def test_create_session(self, session_repository: SessionRepository) -> None:
        """Test creating a new session."""
        # Arrange
        session = TimeSession(
            task_name="Test Task",
            description="Test description",
            tags=["test", "development"],
            start_time=datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            is_active=True,
            metadata={"test": True},
        )

        # Act
        created_session = session_repository.create_session(session)

        # Assert
        assert created_session == session

        # Verify it was stored in database
        retrieved = session_repository.get_session_by_id(session.id)
        assert retrieved is not None
        assert retrieved.task_name == "Test Task"
        assert retrieved.description == "Test description"
        assert set(retrieved.tags) == {"test", "development"}
        assert retrieved.is_active is True
        assert retrieved.metadata == {"test": True}

    def test_create_session_with_completed_session(
        self, session_repository: SessionRepository
    ) -> None:
        """Test creating a completed session."""
        # Arrange
        start_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc)

        session = TimeSession(
            task_name="Completed Task",
            description="Completed session",
            start_time=start_time,
            end_time=end_time,
            is_active=False,
        )

        # Act
        created_session = session_repository.create_session(session)

        # Assert
        assert created_session.is_active is False
        assert created_session.end_time == end_time

    def test_get_session_by_id_exists(
        self, session_repository: SessionRepository
    ) -> None:
        """Test getting session by ID when it exists."""
        # Arrange
        session = TimeSession(
            task_name="Test Task", description="Test description", end_time=None
        )
        session_repository.create_session(session)

        # Act
        retrieved = session_repository.get_session_by_id(session.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == session.id
        assert retrieved.task_name == "Test Task"

    def test_get_session_by_id_not_exists(
        self, session_repository: SessionRepository
    ) -> None:
        """Test getting session by ID when it doesn't exist."""
        # Arrange
        non_existent_id = uuid4()

        # Act
        retrieved = session_repository.get_session_by_id(non_existent_id)

        # Assert
        assert retrieved is None

    def test_get_active_session_with_active(
        self, session_repository: SessionRepository
    ) -> None:
        """Test getting active session when one exists."""
        # Arrange
        active_session = TimeSession(
            task_name="Active Task",
            description="Active session",
            is_active=True,
            end_time=None,
        )
        session_repository.create_session(active_session)

        # Create inactive session too
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(minutes=30)
        inactive_session = TimeSession(
            task_name="Inactive Task",
            description="Inactive session",
            start_time=start_time,
            end_time=end_time,
            is_active=False,
        )
        session_repository.create_session(inactive_session)

        # Act
        retrieved = session_repository.get_active_session()

        # Assert
        assert retrieved is not None
        assert retrieved.id == active_session.id
        assert retrieved.is_active is True

    def test_get_active_session_with_none_active(
        self, session_repository: SessionRepository
    ) -> None:
        """Test getting active session when none exists."""
        # Arrange - create only inactive sessions
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(minutes=30)
        inactive_session = TimeSession(
            task_name="Inactive Task",
            description="Inactive session",
            start_time=start_time,
            end_time=end_time,
            is_active=False,
        )
        session_repository.create_session(inactive_session)

        # Act
        retrieved = session_repository.get_active_session()

        # Assert
        assert retrieved is None

    def test_get_active_session_returns_most_recent(
        self, session_repository: SessionRepository
    ) -> None:
        """Test that get_active_session returns most recent when multiple active."""
        # Arrange - create multiple active sessions (shouldn't happen in practice)
        earlier_session = TimeSession(
            task_name="Earlier Active",
            description="Earlier active session",
            start_time=datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
            is_active=True,
            end_time=None,
        )
        session_repository.create_session(earlier_session)

        later_session = TimeSession(
            task_name="Later Active",
            description="Later active session",
            start_time=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            is_active=True,
            end_time=None,
        )
        session_repository.create_session(later_session)

        # Act
        retrieved = session_repository.get_active_session()

        # Assert
        assert retrieved is not None
        assert retrieved.id == later_session.id
        assert retrieved.task_name == "Later Active"

    def test_update_session(self, session_repository: SessionRepository) -> None:
        """Test updating an existing session."""
        # Arrange
        session = TimeSession(
            task_name="Original Task",
            description="Original description",
            tags=["original"],
            is_active=True,
            end_time=None,
        )
        session_repository.create_session(session)

        # Modify session
        session.task_name = "Updated Task"
        session.description = "Updated description"
        session.tags = ["updated", "test"]
        session.end_time = datetime.now(timezone.utc)
        session.is_active = False
        session.metadata = {"updated": True}

        # Act
        updated_session = session_repository.update_session(session)

        # Assert
        assert updated_session == session

        # Verify changes were persisted
        retrieved = session_repository.get_session_by_id(session.id)
        assert retrieved is not None
        assert retrieved.task_name == "Updated Task"
        assert retrieved.description == "Updated description"
        assert set(retrieved.tags) == {"updated", "test"}
        assert retrieved.is_active is False
        assert retrieved.end_time is not None
        assert retrieved.metadata == {"updated": True}

    def test_delete_session_exists(self, session_repository: SessionRepository) -> None:
        """Test deleting a session that exists."""
        # Arrange
        session = TimeSession(
            task_name="To Delete", description="Session to delete", end_time=None
        )
        session_repository.create_session(session)

        # Verify it exists
        assert session_repository.get_session_by_id(session.id) is not None

        # Act
        result = session_repository.delete_session(session.id)

        # Assert
        assert result is True
        assert session_repository.get_session_by_id(session.id) is None

    def test_delete_session_not_exists(
        self, session_repository: SessionRepository
    ) -> None:
        """Test deleting a session that doesn't exist."""
        # Arrange
        non_existent_id = uuid4()

        # Act
        result = session_repository.delete_session(non_existent_id)

        # Assert
        assert result is False

    def test_get_sessions_for_date(self, session_repository: SessionRepository) -> None:
        """Test getting sessions for a specific date."""
        # Arrange
        target_date = date(2024, 1, 1)

        # Sessions on target date
        session1 = TimeSession(
            task_name="Task 1",
            description="Session on target date",
            start_time=datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
            end_time=None,
        )
        session2 = TimeSession(
            task_name="Task 2",
            description="Session on target date",
            start_time=datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
            end_time=None,
        )

        # Session on different date
        session3 = TimeSession(
            task_name="Task 3",
            description="Session on different date",
            start_time=datetime(2024, 1, 2, 9, 0, 0, tzinfo=timezone.utc),
            end_time=None,
        )

        for session in [session1, session2, session3]:
            session_repository.create_session(session)

        # Act
        sessions = session_repository.get_sessions_for_date(target_date)

        # Assert
        assert len(sessions) == 2
        task_names = [s.task_name for s in sessions]
        assert "Task 1" in task_names
        assert "Task 2" in task_names
        assert "Task 3" not in task_names

        # Should be ordered by start time
        assert sessions[0].start_time <= sessions[1].start_time

    def test_get_sessions_for_date_empty(
        self, session_repository: SessionRepository
    ) -> None:
        """Test getting sessions for date with no sessions."""
        # Arrange
        target_date = date(2024, 1, 1)

        # Act
        sessions = session_repository.get_sessions_for_date(target_date)

        # Assert
        assert sessions == []

    def test_get_sessions_in_range(self, session_repository: SessionRepository) -> None:
        """Test getting sessions within a date range."""
        # Arrange
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 3)

        sessions_data = [
            ("Task 1", datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)),
            ("Task 2", datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)),
            ("Task 3", datetime(2024, 1, 3, 11, 0, 0, tzinfo=timezone.utc)),
            (
                "Task 4",
                datetime(2024, 1, 4, 12, 0, 0, tzinfo=timezone.utc),
            ),  # Outside range
        ]

        for task_name, start_time in sessions_data:
            session = TimeSession(
                task_name=task_name,
                start_time=start_time,
                description="Session in range",
                end_time=None,
            )
            session_repository.create_session(session)

        # Act
        sessions = session_repository.get_sessions_in_range(start_date, end_date)

        # Assert
        assert len(sessions) == 3
        task_names = [s.task_name for s in sessions]
        assert "Task 1" in task_names
        assert "Task 2" in task_names
        assert "Task 3" in task_names
        assert "Task 4" not in task_names

    def test_get_recent_sessions(self, session_repository: SessionRepository) -> None:
        """Test getting recent sessions with limit."""
        # Arrange
        sessions_data = []
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        for i in range(5):
            start_time = base_time + timedelta(hours=i)
            session = TimeSession(
                task_name=f"Task {i + 1}",
                start_time=start_time,
                description="Session in range",
                end_time=None,
            )
            session_repository.create_session(session)
            sessions_data.append(session)

        # Act
        recent_sessions = session_repository.get_recent_sessions(limit=3)

        # Assert
        assert len(recent_sessions) == 3

        # Should be in descending order by start time (most recent first)
        assert recent_sessions[0].task_name == "Task 5"
        assert recent_sessions[1].task_name == "Task 4"
        assert recent_sessions[2].task_name == "Task 3"

    def test_get_recent_sessions_no_limit(
        self, session_repository: SessionRepository
    ) -> None:
        """Test getting recent sessions with default limit."""
        # Arrange
        for i in range(15):  # More than default limit
            session = TimeSession(
                task_name=f"Task {i + 1}",
                start_time=datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
                + timedelta(hours=i),
                description="Session in range",
                end_time=None,
            )
            session_repository.create_session(session)

        # Act
        recent_sessions = session_repository.get_recent_sessions()

        # Assert
        assert len(recent_sessions) == 10  # Default limit

    def test_get_sessions_by_task(self, session_repository: SessionRepository) -> None:
        """Test getting sessions by task name."""
        # Arrange
        task_name = "Project Alpha"

        # Create sessions with same task name
        session1 = TimeSession(
            task_name=task_name,
            start_time=datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
            description="Session for Project Alpha",
            end_time=None,
        )
        session2 = TimeSession(
            task_name=task_name,
            start_time=datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            description="Session for Project Alpha",
            end_time=None,
        )

        # Create session with different task name
        session3 = TimeSession(
            task_name="Different Task",
            start_time=datetime(2024, 1, 3, 11, 0, 0, tzinfo=timezone.utc),
            description="Session for Different Task",
            end_time=None,
        )

        for session in [session1, session2, session3]:
            session_repository.create_session(session)

        # Act
        sessions = session_repository.get_sessions_by_task(task_name)

        # Assert
        assert len(sessions) == 2
        assert all(s.task_name == task_name for s in sessions)

        # Should be ordered by start time descending
        assert sessions[0].start_time > sessions[1].start_time

    def test_get_sessions_by_task_case_sensitive(
        self, session_repository: SessionRepository
    ) -> None:
        """Test that task name search is case sensitive."""
        # Arrange
        session1 = TimeSession(
            task_name="Task", description="Session for Task", end_time=None
        )
        session2 = TimeSession(
            task_name="task", description="Session for task", end_time=None
        )  # Different case

        session_repository.create_session(session1)
        session_repository.create_session(session2)

        # Act
        sessions = session_repository.get_sessions_by_task("Task")

        # Assert
        assert len(sessions) == 1
        assert sessions[0].task_name == "Task"

    def test_get_sessions_by_tag(self, session_repository: SessionRepository) -> None:
        """Test getting sessions by tag."""
        # Arrange
        sessions_data = [
            ("Task 1", ["development", "urgent"]),
            ("Task 2", ["testing", "development"]),
            ("Task 3", ["design"]),
            ("Task 4", ["development", "review"]),
        ]

        for task_name, tags in sessions_data:
            session = TimeSession(
                task_name=task_name,
                tags=tags,
                description="Session for " + task_name,
                end_time=None,
            )
            session_repository.create_session(session)

        # Act
        sessions = session_repository.get_sessions_by_tag("development")

        # Assert
        assert len(sessions) == 3
        task_names = [s.task_name for s in sessions]
        assert "Task 1" in task_names
        assert "Task 2" in task_names
        assert "Task 4" in task_names
        assert "Task 3" not in task_names

    def test_get_sessions_by_tag_case_insensitive(
        self, session_repository: SessionRepository
    ) -> None:
        """Test that tag search is case insensitive."""
        # Arrange
        session = TimeSession(
            task_name="Task",
            tags=["Development", "TESTING"],  # Mixed case
            description="Session for Task",
            end_time=None,
        )
        session_repository.create_session(session)

        # Act
        sessions_dev = session_repository.get_sessions_by_tag("development")
        sessions_test = session_repository.get_sessions_by_tag("testing")

        # Assert
        assert len(sessions_dev) == 1
        assert len(sessions_test) == 1
        assert sessions_dev[0].task_name == "Task"
        assert sessions_test[0].task_name == "Task"

    def test_get_sessions_by_tag_partial_match_prevention(
        self, session_repository: SessionRepository
    ) -> None:
        """Test that tag search doesn't match partial tags."""
        # Arrange
        session = TimeSession(
            task_name="Task",
            tags=["development"],
            description="Session for Task",
            end_time=None,
        )
        session_repository.create_session(session)

        # Act - search for partial tag
        sessions = session_repository.get_sessions_by_tag("dev")

        # Assert
        assert len(sessions) == 0  # Should not match partial

    def test_get_daily_stats(self, session_repository: SessionRepository) -> None:
        """Test getting daily statistics."""
        # Arrange
        target_date = date(2024, 1, 1)

        # Create completed sessions
        sessions_data = [
            ("Task 1", ["dev", "urgent"], timedelta(hours=1)),
            ("Task 2", ["test", "dev"], timedelta(hours=2)),
            ("Task 1", ["dev"], timedelta(minutes=30)),  # Same task name
        ]

        for i, (task_name, tags, duration) in enumerate(sessions_data):
            start_time = datetime(2024, 1, 1, 9 + i, 0, 0, tzinfo=timezone.utc)
            end_time = start_time + duration

            session = TimeSession(
                task_name=task_name,
                description=f"Session for {task_name}",
                tags=tags,
                start_time=start_time,
                end_time=end_time,
                is_active=False,
            )
            session_repository.create_session(session)

        # Create active session (should not be included in stats)
        active_session = TimeSession(
            task_name="Active Task",
            description="Session for Active Task",
            start_time=datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc),
            is_active=True,
            end_time=None,
        )
        session_repository.create_session(active_session)

        # Act
        stats = session_repository.get_daily_stats(target_date)

        # Assert
        assert isinstance(stats, DailyStats)
        assert stats.date == "2024-01-01"
        assert stats.session_count == 3  # Only completed sessions
        assert stats.unique_tasks == 2  # "Task 1" and "Task 2"
        assert stats.total_duration == 3.5 * 3600  # 3.5 hours in seconds
        assert stats.longest_session == 2 * 3600  # 2 hours in seconds

        # Check most used tags
        assert "dev" in stats.most_used_tags
        assert len(stats.most_used_tags) <= 5

    def test_get_daily_stats_no_sessions(
        self, session_repository: SessionRepository
    ) -> None:
        """Test getting daily stats for date with no sessions."""
        # Arrange
        target_date = date(2024, 1, 1)

        # Act
        stats = session_repository.get_daily_stats(target_date)

        # Assert
        assert stats.date == "2024-01-01"
        assert stats.total_duration == 0.0
        assert stats.session_count == 0
        assert stats.unique_tasks == 0
        assert stats.most_used_tags == []
        assert stats.longest_session is None

    def test_get_project_stats(self, session_repository: SessionRepository) -> None:
        """Test getting project statistics."""
        # Arrange
        task_name = "Project Alpha"

        # Create completed sessions for the project
        sessions_data = [
            (timedelta(hours=2), ["backend", "api"]),
            (timedelta(hours=1, minutes=30), ["frontend", "ui"]),
            (timedelta(minutes=45), ["testing", "backend"]),
        ]

        for i, (duration, tags) in enumerate(sessions_data):
            start_time = datetime(2024, 1, 1 + i, 9, 0, 0, tzinfo=timezone.utc)
            end_time = start_time + duration

            session = TimeSession(
                task_name=task_name,
                description=f"Session {i + 1} for {task_name}",
                tags=tags,
                start_time=start_time,
                end_time=end_time,
                is_active=False,
            )
            session_repository.create_session(session)

        # Act
        stats = session_repository.get_project_stats(task_name)

        # Assert
        assert isinstance(stats, ProjectStats)
        assert stats.task_name == task_name
        assert stats.session_count == 3

        expected_total = (2 * 3600) + (1.5 * 3600) + (0.75 * 3600)  # Total seconds
        assert stats.total_duration == expected_total
        assert stats.average_session == expected_total / 3

        # Check tags (should be unique)
        expected_tags = {"backend", "api", "frontend", "ui", "testing"}
        assert set(stats.tags) == expected_tags

        # Check session dates
        assert stats.first_session is not None
        assert stats.last_session is not None
        assert stats.first_session <= stats.last_session

    def test_get_project_stats_no_completed_sessions(
        self, session_repository: SessionRepository
    ) -> None:
        """Test getting project stats with no completed sessions."""
        # Arrange
        task_name = "Empty Project"

        # Create only active session (not completed)
        active_session = TimeSession(
            task_name=task_name,
            is_active=True,
            description="Active session for Empty Project",
            end_time=None,
        )
        session_repository.create_session(active_session)

        # Act
        stats = session_repository.get_project_stats(task_name)

        # Assert
        assert stats.task_name == task_name
        assert stats.total_duration == 0.0
        assert stats.session_count == 0
        assert stats.average_session == 0.0
        assert stats.tags == []
        assert stats.first_session is None
        assert stats.last_session is None

    def test_get_project_stats_nonexistent_task(
        self, session_repository: SessionRepository
    ) -> None:
        """Test getting project stats for non-existent task."""
        # Act
        stats = session_repository.get_project_stats("Nonexistent Task")

        # Assert
        assert stats.task_name == "Nonexistent Task"
        assert stats.total_duration == 0.0
        assert stats.session_count == 0
        assert stats.average_session == 0.0
        assert stats.tags == []
        assert stats.first_session is None
        assert stats.last_session is None

    def test_row_to_session_conversion(
        self, session_repository: SessionRepository
    ) -> None:
        """Test internal _row_to_session method functionality."""
        # Arrange
        session_id = uuid4()
        start_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        original_session = TimeSession(
            id=session_id,
            task_name="Test Task",
            description="Test description",
            tags=["test", "development"],
            start_time=start_time,
            end_time=end_time,
            is_active=False,
            metadata={"test_key": "test_value"},
        )

        # Act - create and retrieve session
        session_repository.create_session(original_session)
        retrieved_session = session_repository.get_session_by_id(session_id)

        # Assert - verify all fields are correctly converted
        assert retrieved_session is not None
        assert retrieved_session.id == session_id
        assert retrieved_session.task_name == "Test Task"
        assert retrieved_session.description == "Test description"
        assert set(retrieved_session.tags) == {"test", "development"}
        assert retrieved_session.start_time == start_time
        assert retrieved_session.end_time == end_time
        assert retrieved_session.is_active is False
        assert retrieved_session.metadata == {"test_key": "test_value"}


@pytest.mark.integration
class TestSessionRepositoryIntegration:
    """Integration tests for SessionRepository with database."""

    def test_complete_crud_workflow(
        self, session_repository: SessionRepository
    ) -> None:
        """Test complete CRUD workflow."""
        # Create
        session = TimeSession(
            task_name="CRUD Test",
            description="Testing CRUD operations",
            tags=["test", "crud"],
            end_time=None,
        )
        created = session_repository.create_session(session)
        assert created == session

        # Read
        retrieved = session_repository.get_session_by_id(session.id)
        assert retrieved is not None
        assert retrieved.task_name == "CRUD Test"

        # Update
        retrieved.task_name = "Updated CRUD Test"
        retrieved.description = "Updated description"
        retrieved.end_time = datetime.now(timezone.utc)
        retrieved.is_active = False

        updated = session_repository.update_session(retrieved)
        assert updated.task_name == "Updated CRUD Test"
        assert updated.is_active is False

        # Verify update persisted
        re_retrieved = session_repository.get_session_by_id(session.id)
        assert re_retrieved is not None
        assert re_retrieved.task_name == "Updated CRUD Test"
        assert re_retrieved.is_active is False

        # Delete
        deleted = session_repository.delete_session(session.id)
        assert deleted is True

        # Verify deletion
        final_check = session_repository.get_session_by_id(session.id)
        assert final_check is None

    def test_concurrent_session_handling(
        self, session_repository: SessionRepository
    ) -> None:
        """Test handling multiple sessions concurrently."""
        sessions = []

        # Create multiple sessions
        for i in range(10):
            session = TimeSession(
                task_name=f"Concurrent Task {i}",
                tags=[f"tag{i}", "concurrent"],
                description=f"Session for Concurrent Task {i}",
                end_time=None,
            )
            session_repository.create_session(session)
            sessions.append(session)

        # Verify all were created
        for session in sessions:
            retrieved = session_repository.get_session_by_id(session.id)
            assert retrieved is not None
            assert retrieved.task_name == session.task_name

        # Get sessions by tag
        concurrent_sessions = session_repository.get_sessions_by_tag("concurrent")
        assert len(concurrent_sessions) == 10

        # Clean up
        for session in sessions:
            session_repository.delete_session(session.id)

        # Verify cleanup
        remaining_sessions = session_repository.get_sessions_by_tag("concurrent")
        assert len(remaining_sessions) == 0

    def test_database_consistency_after_operations(
        self, session_repository: SessionRepository
    ) -> None:
        """Test database consistency after various operations."""
        # Create several sessions with overlapping data
        sessions_data = [
            ("Project A", ["backend", "api"], True),
            ("Project A", ["frontend", "ui"], False),
            ("Project B", ["backend", "database"], False),
            ("Project C", ["testing", "qa"], True),
        ]

        created_sessions = []
        base_time = datetime.now(timezone.utc)
        for i, (task_name, tags, is_active) in enumerate(sessions_data):
            start_time = base_time + timedelta(minutes=i * 60)  # Stagger start times
            end_time = None if is_active else start_time + timedelta(minutes=30)
            session = TimeSession(
                task_name=task_name,
                tags=tags,
                start_time=start_time,
                end_time=end_time,
                is_active=is_active,
                description=f"Session for {task_name}",
            )
            session_repository.create_session(session)
            created_sessions.append(session)

        # Test various queries return consistent results
        all_project_a = session_repository.get_sessions_by_task("Project A")
        assert len(all_project_a) == 2

        backend_sessions = session_repository.get_sessions_by_tag("backend")
        assert len(backend_sessions) == 2

        active_session = session_repository.get_active_session()
        assert active_session is not None
        assert active_session.task_name in ["Project A", "Project C"]

        recent_sessions = session_repository.get_recent_sessions(limit=5)
        assert len(recent_sessions) == 4

        # Verify stats calculation consistency
        today = date.today()
        daily_stats = session_repository.get_daily_stats(today)
        assert daily_stats.session_count >= 0  # Depends on whether sessions are today

        project_a_stats = session_repository.get_project_stats("Project A")
        assert project_a_stats.task_name == "Project A"
