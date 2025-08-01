"""
Tests for database models (clockman.db.models).

This module tests the Pydantic models including validation, serialization,
and business logic methods.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from clockman.db.models import DailyStats, ProjectStats, TimeSession


class TestTimeSession:
    """Test cases for TimeSession model."""

    def test_time_session_creation_with_defaults(self) -> None:
        """Test creating TimeSession with minimal required fields."""
        # Act
        session = TimeSession(
            task_name="Test Task", description="Test Description", end_time=None
        )

        # Assert
        assert session.task_name == "Test Task"
        assert session.description == "Test Description"
        assert session.tags == []
        assert session.is_active is True
        assert session.end_time is None
        assert isinstance(session.id, UUID)
        assert isinstance(session.start_time, datetime)
        assert session.start_time.tzinfo is not None  # Should have timezone
        assert session.metadata == {}

    def test_time_session_creation_with_all_fields(self) -> None:
        """Test creating TimeSession with all fields specified."""
        # Arrange
        session_id = uuid4()
        start_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc)
        metadata = {"project": "alpha", "priority": "high"}

        # Act
        session = TimeSession(
            id=session_id,
            task_name="Complete Task",
            description="A comprehensive test task",
            tags=["development", "testing"],
            start_time=start_time,
            end_time=end_time,
            is_active=False,
            metadata=metadata,
        )

        # Assert
        assert session.id == session_id
        assert session.task_name == "Complete Task"
        assert session.description == "A comprehensive test task"
        assert set(session.tags) == {"development", "testing"}
        assert session.start_time == start_time
        assert session.end_time == end_time
        assert session.is_active is False
        assert session.metadata == metadata

    def test_time_session_task_name_validation(self) -> None:
        """Test task name validation rules."""
        # Test empty task name
        with pytest.raises(ValidationError) as exc_info:
            TimeSession(task_name="", description="", end_time=None)
        assert "at least 1 character" in str(exc_info.value)

        # Test task name too long
        long_name = "x" * 256
        with pytest.raises(ValidationError) as exc_info:
            TimeSession(task_name=long_name, description="", end_time=None)
        assert "at most 255 characters" in str(exc_info.value)

        # Test valid task name
        session = TimeSession(
            task_name="Valid Task", description="Valid Task", end_time=None
        )
        assert session.task_name == "Valid Task"

    def test_time_session_description_validation(self) -> None:
        """Test description validation rules."""
        # Test description too long
        long_description = "x" * 1001
        with pytest.raises(ValidationError) as exc_info:
            TimeSession(task_name="Task", description=long_description, end_time=None)
        assert "at most 1000 characters" in str(exc_info.value)

        # Test valid description
        valid_description = "x" * 1000
        session = TimeSession(
            task_name="Task", description=valid_description, end_time=None
        )
        assert session.description == valid_description

        # Test None description
        session = TimeSession(task_name="Task", description=None, end_time=None)
        assert session.description is None

    def test_time_session_tags_validation_and_normalization(self) -> None:
        """Test tags validation and normalization."""
        # Test duplicate removal and normalization
        session = TimeSession(
            task_name="Task",
            tags=["Development", "TESTING", "development", "  testing  ", ""],
            description="Task with tags",
            end_time=None,
        )

        # Should remove duplicates, normalize case, and remove empty strings
        expected_tags = {"development", "testing"}
        assert set(session.tags) == expected_tags

    def test_time_session_end_time_validation(self) -> None:
        """Test end_time validation against start_time."""
        start_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Test valid end_time (after start_time)
        valid_end_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        session = TimeSession(
            task_name="Task",
            start_time=start_time,
            end_time=valid_end_time,
            description="Valid session",
        )
        assert session.end_time == valid_end_time

        # Test invalid end_time (before start_time)
        invalid_end_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            TimeSession(
                task_name="Task",
                start_time=start_time,
                end_time=invalid_end_time,
                description="Invalid session",
            )
        assert "End time must be after start time" in str(exc_info.value)

        # Test end_time equal to start_time (should fail)
        with pytest.raises(ValidationError) as exc_info:
            TimeSession(
                task_name="Task",
                description="Invalid session",
                start_time=start_time,
                end_time=start_time,
            )
        assert "End time must be after start time" in str(exc_info.value)

    def test_time_session_duration_property(self) -> None:
        """Test duration property calculation."""
        start_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc)  # 1.5 hours

        # Test completed session duration
        session = TimeSession(
            description="Completed session",
            task_name="Task",
            start_time=start_time,
            end_time=end_time,
            is_active=False,
        )
        expected_duration = 1.5 * 3600  # 1.5 hours in seconds
        assert session.duration == expected_duration

        # Test active session duration (should be None)
        active_session = TimeSession(
            description="Active session",
            task_name="Active Task",
            start_time=start_time,
            end_time=None,
            is_active=True,
        )
        assert active_session.duration is None

    def test_time_session_stop_method(self) -> None:
        """Test the stop method."""
        # Test stopping with specific end time
        session = TimeSession(
            task_name="Task",
            is_active=True,
            end_time=None,
            description="Stopping session",
        )
        end_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        session.stop(end_time)

        assert session.end_time == end_time
        assert session.is_active is False

        # Test stopping with current time (default)
        active_session = TimeSession(
            task_name="Another Task",
            is_active=True,
            description="Active session",
            end_time=None,
        )
        before_stop = datetime.now(timezone.utc)

        active_session.stop()

        assert active_session.is_active is False
        assert active_session.end_time is not None
        assert active_session.end_time >= before_stop

    def test_time_session_json_serialization(self) -> None:
        """Test JSON serialization of TimeSession."""
        session_id = uuid4()
        start_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        session = TimeSession(
            id=session_id,
            task_name="Serialization Test",
            description="Testing JSON serialization",
            tags=["test", "json"],
            start_time=start_time,
            end_time=end_time,
            is_active=False,
            metadata={"test": True},
        )

        # Test model dump
        data = session.model_dump()

        assert isinstance(data, dict)
        assert data["id"] == session_id
        assert data["task_name"] == "Serialization Test"
        assert data["start_time"] == start_time
        assert data["end_time"] == end_time

        # Test JSON string
        json_str = session.model_dump_json()
        assert isinstance(json_str, str)
        assert str(session_id) in json_str
        assert "Serialization Test" in json_str

    def test_time_session_from_dict(self) -> None:
        """Test creating TimeSession from dictionary."""
        session_id = uuid4()
        data = {
            "id": str(session_id),
            "task_name": "From Dict",
            "description": "Created from dictionary",
            "tags": ["dict", "test"],
            "start_time": "2024-01-01T09:00:00+00:00",
            "end_time": "2024-01-01T10:00:00+00:00",
            "is_active": False,
            "metadata": {"source": "dict"},
        }

        session = TimeSession.model_validate(data)

        assert session.id == session_id
        assert session.task_name == "From Dict"
        assert session.description == "Created from dictionary"
        assert set(session.tags) == {
            "dict",
            "test",
        }  # Order not guaranteed due to normalization
        assert session.is_active is False
        assert session.metadata == {"source": "dict"}


class TestDailyStats:
    """Test cases for DailyStats model."""

    def test_daily_stats_creation_with_defaults(self) -> None:
        """Test creating DailyStats with minimal fields."""
        stats = DailyStats(
            date="2024-01-01",
            total_duration=0.0,
            session_count=0,
            unique_tasks=0,
            longest_session=None,
        )

        assert stats.date == "2024-01-01"
        assert stats.total_duration == 0.0
        assert stats.session_count == 0
        assert stats.unique_tasks == 0
        assert stats.most_used_tags == []
        assert stats.longest_session is None

    def test_daily_stats_creation_with_all_fields(self) -> None:
        """Test creating DailyStats with all fields."""
        stats = DailyStats(
            date="2024-01-01",
            total_duration=7200.0,  # 2 hours
            session_count=3,
            unique_tasks=2,
            most_used_tags=["development", "testing"],
            longest_session=3600.0,  # 1 hour
        )

        assert stats.date == "2024-01-01"
        assert stats.total_duration == 7200.0
        assert stats.session_count == 3
        assert stats.unique_tasks == 2
        assert stats.most_used_tags == ["development", "testing"]
        assert stats.longest_session == 3600.0

    def test_daily_stats_validation(self) -> None:
        """Test DailyStats field validation."""
        # Test valid stats
        stats = DailyStats(
            date="2024-01-01",
            total_duration=1800.0,
            session_count=1,
            unique_tasks=1,
            longest_session=None,
        )
        assert stats.date == "2024-01-01"

        # All fields should accept valid values
        assert stats.total_duration >= 0
        assert stats.session_count >= 0
        assert stats.unique_tasks >= 0

    def test_daily_stats_serialization(self) -> None:
        """Test DailyStats serialization."""
        stats = DailyStats(
            date="2024-01-01",
            total_duration=3600.0,
            session_count=2,
            unique_tasks=2,
            most_used_tags=["work", "project"],
            longest_session=1800.0,
        )

        # Test dictionary conversion
        data = stats.model_dump()
        assert isinstance(data, dict)
        assert data["date"] == "2024-01-01"
        assert data["total_duration"] == 3600.0

        # Test JSON serialization
        json_str = stats.model_dump_json()
        assert "2024-01-01" in json_str
        assert "3600.0" in json_str


class TestProjectStats:
    """Test cases for ProjectStats model."""

    def test_project_stats_creation_with_defaults(self) -> None:
        """Test creating ProjectStats with minimal fields."""
        stats = ProjectStats(
            task_name="Test Project",
            total_duration=0.0,
            session_count=0,
            average_session=0.0,
            tags=[],
            first_session=None,
            last_session=None,
        )

        assert stats.task_name == "Test Project"
        assert stats.total_duration == 0.0
        assert stats.session_count == 0
        assert stats.average_session == 0.0
        assert stats.tags == []
        assert stats.first_session is None
        assert stats.last_session is None

    def test_project_stats_creation_with_all_fields(self) -> None:
        """Test creating ProjectStats with all fields."""
        first_session = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        last_session = datetime(2024, 1, 5, 15, 0, 0, tzinfo=timezone.utc)

        stats = ProjectStats(
            task_name="Complete Project",
            total_duration=14400.0,  # 4 hours
            session_count=4,
            average_session=3600.0,  # 1 hour
            tags=["backend", "api", "database"],
            first_session=first_session,
            last_session=last_session,
        )

        assert stats.task_name == "Complete Project"
        assert stats.total_duration == 14400.0
        assert stats.session_count == 4
        assert stats.average_session == 3600.0
        assert stats.tags == ["backend", "api", "database"]
        assert stats.first_session == first_session
        assert stats.last_session == last_session

    def test_project_stats_validation(self) -> None:
        """Test ProjectStats field validation."""
        # Test valid stats
        stats = ProjectStats(
            task_name="Valid Project",
            total_duration=1800.0,
            session_count=2,
            average_session=900.0,
            tags=["development", "testing"],
            first_session=datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
            last_session=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        )

        assert stats.task_name == "Valid Project"
        assert stats.total_duration == 1800.0
        assert stats.session_count == 2
        assert stats.average_session == 900.0

    def test_project_stats_serialization(self) -> None:
        """Test ProjectStats serialization."""
        first_session = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        last_session = datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)

        stats = ProjectStats(
            task_name="Serialization Project",
            total_duration=7200.0,
            session_count=3,
            average_session=2400.0,
            tags=["test", "serialization"],
            first_session=first_session,
            last_session=last_session,
        )

        # Test dictionary conversion
        data = stats.model_dump()
        assert isinstance(data, dict)
        assert data["task_name"] == "Serialization Project"
        assert data["total_duration"] == 7200.0
        assert data["tags"] == ["test", "serialization"]

        # Test JSON serialization
        json_str = stats.model_dump_json()
        assert "Serialization Project" in json_str
        assert "7200.0" in json_str

    def test_project_stats_from_dict(self) -> None:
        """Test creating ProjectStats from dictionary."""
        data = {
            "task_name": "Dict Project",
            "total_duration": 5400.0,
            "session_count": 2,
            "average_session": 2700.0,
            "tags": ["dictionary", "validation"],
            "first_session": "2024-01-01T09:00:00Z",
            "last_session": "2024-01-02T14:30:00Z",
        }

        stats = ProjectStats.model_validate(data)

        assert stats.task_name == "Dict Project"
        assert stats.total_duration == 5400.0
        assert stats.session_count == 2
        assert stats.average_session == 2700.0
        assert stats.tags == ["dictionary", "validation"]
        assert isinstance(stats.first_session, datetime)
        assert isinstance(stats.last_session, datetime)


@pytest.mark.unit
class TestModelInteractions:
    """Test interactions between different models."""

    def test_time_session_to_daily_stats_data(self) -> None:
        """Test that TimeSession data can be used for DailyStats."""
        # Create multiple sessions
        sessions = []
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        for i in range(3):
            start_time = base_time.replace(hour=9 + i * 2)
            end_time = start_time + timedelta(hours=1)

            session = TimeSession(
                task_name=f"Task {i + 1}",
                tags=["work", f"task{i}"],
                start_time=start_time,
                end_time=end_time,
                is_active=False,
                description=f"Session for task {i + 1}",
            )
            sessions.append(session)

        # Calculate stats from sessions
        total_duration = sum(s.duration or 0 for s in sessions)
        session_count = len(sessions)
        unique_tasks = len(set(s.task_name for s in sessions))
        all_tags = []
        for s in sessions:
            all_tags.extend(s.tags)

        # Create DailyStats
        stats = DailyStats(
            date="2024-01-01",
            total_duration=total_duration,
            session_count=session_count,
            unique_tasks=unique_tasks,
            most_used_tags=list(set(all_tags)),
            longest_session=max(
                (s.duration for s in sessions if s.duration), default=None
            ),
        )

        assert stats.total_duration == 3 * 3600.0  # 3 hours
        assert stats.session_count == 3
        assert stats.unique_tasks == 3
        assert "work" in stats.most_used_tags

    def test_time_session_to_project_stats_data(self) -> None:
        """Test that TimeSession data can be used for ProjectStats."""
        task_name = "Project Alpha"
        sessions = []

        # Create sessions for the same project
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        for i in range(2):
            start_time = base_time + timedelta(days=i)
            end_time = start_time + timedelta(hours=2)

            session = TimeSession(
                task_name=task_name,
                tags=["project", f"phase{i+1}"],
                start_time=start_time,
                end_time=end_time,
                is_active=False,
                description=f"Session for {task_name} phase {i + 1}",
            )
            sessions.append(session)

        # Calculate project stats
        total_duration = sum(s.duration or 0 for s in sessions)
        session_count = len(sessions)
        average_session = total_duration / session_count
        all_tags = []
        for s in sessions:
            all_tags.extend(s.tags)
        unique_tags = list(set(all_tags))

        first_session = min(s.start_time for s in sessions)
        last_session = max(s.start_time for s in sessions)

        # Create ProjectStats
        stats = ProjectStats(
            task_name=task_name,
            total_duration=total_duration,
            session_count=session_count,
            average_session=average_session,
            tags=unique_tags,
            first_session=first_session,
            last_session=last_session,
        )

        assert stats.task_name == task_name
        assert stats.total_duration == 2 * 2 * 3600.0  # 2 sessions * 2 hours each
        assert stats.session_count == 2
        assert stats.average_session == 2 * 3600.0  # 2 hours
        assert "project" in stats.tags
        assert "phase1" in stats.tags
        assert "phase2" in stats.tags


@pytest.mark.unit
class TestModelEdgeCases:
    """Test edge cases and error conditions for models."""

    def test_time_session_with_extreme_values(self) -> None:
        """Test TimeSession with boundary values."""
        # Test minimum valid task name
        session = TimeSession(task_name="a", description="Minimal task", end_time=None)
        assert session.task_name == "a"

        # Test maximum valid task name
        max_name = "x" * 255
        session = TimeSession(
            task_name=max_name, description="Max task name", end_time=None
        )
        assert session.task_name == max_name

        # Test maximum valid description
        max_description = "x" * 1000
        session = TimeSession(
            task_name="Task", description=max_description, end_time=None
        )
        assert session.description == max_description

    def test_daily_stats_with_zero_values(self) -> None:
        """Test DailyStats with zero/empty values."""
        stats = DailyStats(
            date="2024-01-01",
            total_duration=0.0,
            session_count=0,
            unique_tasks=0,
            most_used_tags=[],
            longest_session=None,
        )

        assert stats.total_duration == 0.0
        assert stats.session_count == 0
        assert stats.unique_tasks == 0
        assert stats.most_used_tags == []
        assert stats.longest_session is None

    def test_project_stats_with_zero_values(self) -> None:
        """Test ProjectStats with zero/empty values."""
        stats = ProjectStats(
            task_name="Empty Project",
            total_duration=0.0,
            session_count=0,
            average_session=0.0,
            tags=[],
            first_session=None,
            last_session=None,
        )

        assert stats.task_name == "Empty Project"
        assert stats.total_duration == 0.0
        assert stats.session_count == 0
        assert stats.average_session == 0.0
        assert stats.tags == []
        assert stats.first_session is None
        assert stats.last_session is None
