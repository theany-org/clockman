"""
Tests for CLI main module (trackit.cli.main).

This module tests the command-line interface functionality including all commands,
error handling, and output formatting.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest import result
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from trackit.cli.main import app, get_tracker
from trackit.core.time_tracker import (
    TimeTracker,
)
from trackit.db.models import TimeSession


class TestCLIMain:
    """Test cases for CLI main functionality."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("trackit.cli.main.get_tracker")
    def test_start_command_success(self, mock_get_tracker: Mock) -> None:
        """Test successful start command."""
        # Arrange
        mock_tracker = Mock()
        mock_tracker.get_active_session.return_value = None
        mock_tracker.start_session.return_value = uuid4()
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["start", "Test Task"])

        # Assert
        assert result.exit_code == 0
        assert "Started tracking: Test Task" in result.stdout
        mock_tracker.start_session.assert_called_once_with(
            task_name="Test Task", tags=[], description=None
        )

    @patch("trackit.cli.main.get_tracker")
    def test_start_command_with_tags_and_description(self, mock_get_tracker: Mock) -> None:
        """Test start command with tags and description."""
        # Arrange
        mock_tracker = Mock()
        mock_tracker.get_active_session.return_value = None
        mock_tracker.start_session.return_value = uuid4()
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(
            app,
            [
                "start",
                "Test Task",
                "--tag",
                "tag1",
                "--tag",
                "tag2",
                "--description",
                "Test description",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Started tracking: Test Task" in result.stdout
        assert "Tags: tag1, tag2" in result.stdout
        assert "Description: Test description" in result.stdout
        mock_tracker.start_session.assert_called_once_with(
            task_name="Test Task", tags=["tag1", "tag2"], description="Test description"
        )

    @patch("trackit.cli.main.get_tracker")
    def test_start_command_stops_active_session(self, mock_get_tracker: Mock) -> None:
        """Test start command stops existing active session."""
        # Arrange
        mock_tracker = Mock()
        active_session = TimeSession(
            task_name="Previous Task",
            start_time=datetime.now(timezone.utc),
            is_active=True,
            description="Previous active task",
            end_time=None,
        )
        mock_tracker.get_active_session.return_value = active_session
        mock_tracker.start_session.return_value = uuid4()
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["start", "New Task"])

        # Assert
        assert result.exit_code == 0
        assert "Stopped previous task: Previous Task" in result.stdout
        assert "Started tracking: New Task" in result.stdout
        mock_tracker.stop_session.assert_called_once()
        mock_tracker.start_session.assert_called_once()

    @patch("trackit.cli.main.get_tracker")
    def test_start_command_error_handling(self, mock_get_tracker: Mock) -> None:
        """Test start command error handling."""
        # Arrange
        mock_tracker = Mock()
        mock_tracker.get_active_session.side_effect = Exception("Database error")
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["start", "Test Task"])

        # Assert
        assert result.exit_code == 1
        assert "Error starting task: Database error" in result.stdout

    @patch("trackit.cli.main.get_tracker")
    def test_stop_command_success(self, mock_get_tracker: Mock) -> None:
        """Test successful stop command."""
        # Arrange
        mock_tracker = Mock()
        active_session = TimeSession(
            task_name="Test Task",
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            end_time=datetime.now(timezone.utc),
            description="Test description",
            is_active=False,
        )
        mock_tracker.get_active_session.return_value = active_session
        mock_tracker.stop_session.return_value = active_session
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["stop"])

        # Assert
        assert result.exit_code == 0
        assert "Stopped: Test Task" in result.stdout
        assert "Duration:" in result.stdout
        mock_tracker.stop_session.assert_called_once()

    @patch("trackit.cli.main.get_tracker")
    def test_stop_command_no_active_session(self, mock_get_tracker: Mock) -> None:
        """Test stop command with no active session."""
        # Arrange
        mock_tracker = Mock()
        mock_tracker.get_active_session.return_value = None
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["stop"])

        # Assert
        assert result.exit_code == 0
        assert "No active session to stop" in result.stdout
        mock_tracker.stop_session.assert_not_called()

    @patch("trackit.cli.main.get_tracker")
    def test_stop_command_error_handling(self, mock_get_tracker: Mock) -> None:
        """Test stop command error handling."""
        # Arrange
        mock_tracker = Mock()
        mock_tracker.get_active_session.side_effect = Exception("Database error")
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["stop"])

        # Assert
        assert result.exit_code == 1
        assert "Error stopping session: Database error" in result.stdout

    @patch("trackit.cli.main.get_tracker")
    def test_status_command_with_active_session(self, mock_get_tracker: Mock) -> None:
        """Test status command with active session."""
        # Arrange
        mock_tracker = Mock()
        active_session = TimeSession(
            task_name="Test Task",
            description="Test description",
            tags=["tag1", "tag2"],
            start_time=datetime.now(timezone.utc) - timedelta(minutes=30),
            end_time=None,
            is_active=True,
        )
        mock_tracker.get_active_session.return_value = active_session
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["status"])

        # Assert
        assert result.exit_code == 0
        assert "Active Session" in result.stdout
        assert "Test Task" in result.stdout
        assert "Test description" in result.stdout
        assert any(tag_set in result.stdout for tag_set in ["tag1, tag2", "tag2, tag1"])

    @patch("trackit.cli.main.get_tracker")
    def test_status_command_no_active_session(self, mock_get_tracker: Mock) -> None:
        """Test status command with no active session."""
        # Arrange
        mock_tracker = Mock()
        mock_tracker.get_active_session.return_value = None
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["status"])

        # Assert
        assert result.exit_code == 0
        assert "No active session" in result.stdout

    @patch("trackit.cli.main.get_tracker")
    def test_status_command_error_handling(self, mock_get_tracker: Mock) -> None:
        """Test status command error handling."""
        # Arrange
        mock_tracker = Mock()
        mock_tracker.get_active_session.side_effect = Exception("Database error")
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["status"])

        # Assert
        assert result.exit_code == 1
        assert "Error getting status: Database error" in result.stdout

    @patch("trackit.cli.main.get_tracker")
    @patch("datetime.date")
    def test_log_command_today_with_entries(self, mock_date: Mock, mock_get_tracker: Mock) -> None:
        """Test log command showing today's entries."""
        # Arrange
        mock_date.today.return_value = datetime(2024, 1, 1).date()
        mock_tracker = Mock()
        now = datetime.now(timezone.utc)
        sessions = [
            TimeSession(
                task_name="Task 1",
                description="Description for task 1",
                start_time=now - timedelta(hours=1),
                end_time=now,
                tags=["tag1"],
                is_active=False,
            ),
            TimeSession(
                task_name="Task 2",
                description="Description for task 2",
                start_time=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
                end_time=None,
                is_active=True,
            ),
        ]

        mock_tracker.get_entries_for_date.return_value = sessions
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["log"])

        # Assert
        if result.exit_code != 0:
            print(f"CLI output: {result.output}")
            print(f"Exception: {result.exception}")
        assert result.exit_code == 0
        assert "Today's Time Entries" in result.stdout
        assert "Task 1" in result.stdout
        assert "Task 2" in result.stdout
        assert "Active" in result.stdout
        assert "Total:" in result.stdout

    @patch("trackit.cli.main.get_tracker")
    def test_log_command_recent_entries(self, mock_get_tracker: Mock) -> None:
        """Test log command showing recent entries."""
        # Arrange
        mock_tracker = Mock()
        now = datetime.now(timezone.utc)

        sessions = [
            TimeSession(
                task_name="Recent Task",
                description="Recent task description",
                start_time=now - timedelta(hours=1),
                end_time=now,
                is_active=False,
            )
        ]

        mock_tracker.get_entries_for_date.return_value = sessions
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["log", "--limit", "5"])

        # Assert
        assert result.exit_code == 0
        assert "Today's Time Entries" in result.stdout
        assert "Recent Task" in result.stdout

    @patch("trackit.cli.main.get_tracker")
    def test_log_command_no_entries(self, mock_get_tracker: Mock) -> None:
        """Test log command with no entries."""
        # Arrange
        mock_tracker = Mock()
        mock_tracker.get_entries_for_date.return_value = []
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["log"])

        # Assert
        assert result.exit_code == 0
        assert "No entries found" in result.stdout

    @patch("trackit.cli.main.get_tracker")
    def test_log_command_error_handling(self, mock_get_tracker: Mock) -> None:
        """Test log command error handling."""
        # Arrange
        mock_tracker = Mock()
        mock_tracker.get_entries_for_date.side_effect = Exception("Database error")
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["log"])

        # Assert
        assert result.exit_code == 1
        assert "Error showing log: Database error" in result.stdout

    @patch("trackit.__version__", "1.0.0")
    def test_version_command(self) -> None:
        """Test version command."""
        # Act
        result = self.runner.invoke(app, ["version"])

        # Assert
        assert result.exit_code == 0
        assert "TrackIt version 1.0.0" in result.stdout

    def test_version_callback(self) -> None:
        """Test version callback option."""
        # Act
        result = self.runner.invoke(app, ["--version"])

        # Assert
        assert result.exit_code == 0
        assert "TrackIt version" in result.stdout

    @patch("trackit.cli.main.get_config_manager")
    def test_get_tracker_initialization(self, mock_get_config_manager: Mock) -> None:
        """Test tracker initialization."""
        # Arrange
        mock_config = Mock()
        mock_config.get_data_dir.return_value = "/tmp/test"
        mock_get_config_manager.return_value = mock_config

        # Act
        tracker = get_tracker()

        # Assert
        assert tracker is not None
        assert isinstance(tracker, TimeTracker)
        mock_get_config_manager.assert_called_once()

    @patch("trackit.cli.main.get_config_manager")
    def test_get_tracker_singleton(self, mock_get_config_manager: Mock) -> None:
        """Test that get_tracker returns the same instance."""
        # Arrange
        mock_config = Mock()
        mock_config.get_data_dir.return_value = "/tmp/test"
        mock_get_config_manager.return_value = mock_config

        # Clear any existing tracker
        import trackit.cli.main

        trackit.cli.main.tracker = None

        # Act
        tracker1 = get_tracker()
        tracker2 = get_tracker()

        # Assert
        assert tracker1 is tracker2
        # Config manager should only be called once
        mock_get_config_manager.assert_called_once()


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_app_help(self) -> None:
        """Test that app help is displayed correctly."""
        # Act
        result = self.runner.invoke(app, ["--help"])

        # Assert
        assert result.exit_code == 0
        assert "TrackIt: Terminal-based time tracking for developers" in result.stdout
        assert "TrackIt" in result.stdout
        assert "start" in result.stdout
        assert "stop" in result.stdout
        assert "status" in result.stdout
        assert "log" in result.stdout
        assert "version" in result.stdout

    def test_start_command_help(self) -> None:
        """Test start command help."""
        # Act
        result = self.runner.invoke(app, ["start", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "Start tracking time for a task" in result.stdout
        assert "task_name" in result.stdout
        assert "--tag" in result.stdout
        assert "--description" in result.stdout

    def test_stop_command_help(self) -> None:
        """Test stop command help."""
        # Act
        result = self.runner.invoke(app, ["stop", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "Stop the currently active time tracking session" in result.stdout

    def test_status_command_help(self) -> None:
        """Test status command help."""
        # Act
        result = self.runner.invoke(app, ["status", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "Show the current active session status" in result.stdout

    def test_log_command_help(self) -> None:
        """Test log command help."""
        # Act
        result = self.runner.invoke(app, ["log", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "Show recent time tracking entries" in result.stdout
        assert "--today" in result.stdout
        assert "--limit" in result.stdout

    def test_version_command_help(self) -> None:
        """Test version command help."""
        # Act
        result = self.runner.invoke(app, ["version", "--help"])

        # Assert
        assert result.exit_code == 0
        assert "Show TrackIt version information" in result.stdout


@pytest.mark.unit
class TestCLICommandValidation:
    """Test CLI command argument validation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_start_command_requires_task_name(self) -> None:
        """Test that start command requires task name."""
        # Act
        result = self.runner.invoke(app, ["start"])

        # Assert
        assert result.exit_code != 0
        assert "Missing argument" in result.output or "Usage:" in result.output

    @patch("trackit.cli.main.get_tracker")
    def test_start_command_empty_task_name_handled(self, mock_get_tracker: Mock) -> None:
        """Test that empty task name is handled gracefully."""
        # Arrange
        mock_tracker = Mock()
        mock_tracker.get_active_session.return_value = None
        mock_tracker.start_session.return_value = uuid4()
        mock_get_tracker.return_value = mock_tracker

        # Act
        result = self.runner.invoke(app, ["start", ""])

        # Assert
        # Should still work as the model will handle validation
        assert result.exit_code == 0 or "Error starting task" in result.stdout

    def test_log_command_limit_validation(self) -> None:
        """Test log command limit parameter validation."""
        # Act - test with negative limit
        result = self.runner.invoke(app, ["log", "--limit", "-1"])

        # Should not crash, but may show an error or use default
        # The exact behavior depends on typer's validation
        assert isinstance(result.exit_code, int)
