"""
Pytest configuration and fixtures for Clockman tests.

This module provides shared fixtures and configuration for all test modules.
"""

import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from clockman.core.time_tracker import TimeTracker
from clockman.db.models import TimeSession
from clockman.db.repository import SessionRepository
from clockman.db.schema import DatabaseManager
from clockman.utils.config import ConfigManager


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def test_db_path(temp_dir: Path) -> Path:
    """Provide a test database path."""
    return temp_dir / "test_clockman.db"


@pytest.fixture
def db_manager(test_db_path: Path) -> DatabaseManager:
    """Provide a test database manager."""
    manager = DatabaseManager(test_db_path)
    manager.initialize_database()
    return manager


@pytest.fixture
def session_repository(db_manager: DatabaseManager) -> SessionRepository:
    """Provide a test session repository."""
    return SessionRepository(db_manager)


@pytest.fixture
def time_tracker(temp_dir: Path) -> TimeTracker:
    """Provide a test time clockman instance."""
    return TimeTracker(temp_dir)


@pytest.fixture
def mock_config_manager() -> Mock:
    """Provide a mocked configuration manager."""
    mock_config = Mock(spec=ConfigManager)
    mock_config.get_data_dir.return_value = Path("/tmp/test_clockman")
    mock_config.get_date_format.return_value = "%Y-%m-%d"
    mock_config.get_time_format.return_value = "%H:%M:%S"
    mock_config.show_seconds.return_value = True
    mock_config.is_compact_mode.return_value = False
    mock_config.get_max_task_name_length.return_value = 50
    mock_config.get_color.return_value = "white"
    mock_config.get_default_tags.return_value = []
    mock_config.is_auto_stop_enabled.return_value = False
    mock_config.get_inactive_timeout.return_value = 30
    return mock_config


@pytest.fixture
def sample_time_session() -> TimeSession:
    """Provide a sample time session for testing."""
    return TimeSession(
        id=uuid4(),
        task_name="Test Task",
        description="A test task for unit testing",
        tags=["test", "development"],
        start_time=datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc),
        is_active=False,
        metadata={"test": True},
    )


@pytest.fixture
def active_time_session() -> TimeSession:
    """Provide an active time session for testing."""
    return TimeSession(
        id=uuid4(),
        task_name="Active Task",
        description="An active task for testing",
        tags=["active", "current"],
        start_time=datetime.now(timezone.utc),
        end_time=None,
        is_active=True,
    )


@pytest.fixture
def sample_sessions_list() -> list[TimeSession]:
    """Provide a list of sample sessions for testing."""
    sessions = []
    base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

    for i in range(5):
        start_time = base_time.replace(hour=9 + i * 2)
        end_time = start_time.replace(hour=start_time.hour + 1, minute=30)

        session = TimeSession(
            id=uuid4(),
            task_name=f"Task {i + 1}",
            description=f"Description for task {i + 1}",
            tags=[f"tag{i}", "common"],
            start_time=start_time,
            end_time=end_time,
            is_active=False,
        )
        sessions.append(session)

    return sessions


@pytest.fixture
def today() -> date:
    """Provide today's date for testing."""
    return date(2024, 1, 1)


@pytest.fixture
def mock_datetime() -> type:
    """Mock datetime.now to return a fixed datetime."""
    fixed_datetime = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    class MockDateTime:
        @classmethod
        def now(cls, tz: Optional[Any] = None) -> datetime:
            if tz:
                return fixed_datetime.astimezone(tz)
            return fixed_datetime.replace(tzinfo=None)

    return MockDateTime


# Mark tests that require database access
pytest_mark_db = pytest.mark.integration

# Mark slow tests
pytest_mark_slow = pytest.mark.slow

# Mark unit tests
pytest_mark_unit = pytest.mark.unit
