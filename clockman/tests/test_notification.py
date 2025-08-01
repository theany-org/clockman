import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clockman.utils import notifier


@pytest.mark.asyncio
async def test_notify_sends_notification() -> None:
    """Test that notifier.notify() calls the DesktopNotifier.send method."""
    with (
        patch("clockman.utils.notifier._get_notifier") as mock_get_notifier,
        patch("clockman.utils.notifier.get_config_manager") as mock_config,
        patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True),
    ):
        # Setup mocks
        mock_notifier_instance = MagicMock()
        mock_notifier_instance.send = AsyncMock()
        mock_get_notifier.return_value = mock_notifier_instance

        mock_config_instance = MagicMock()
        mock_config_instance.are_notifications_enabled.return_value = True
        mock_config_instance.get_notification_timeout.return_value = 5000
        mock_config.return_value = mock_config_instance

        # Test the function
        result = await notifier.notify("Test Title", "Test Message")

        # Assertions
        assert result is None
        mock_notifier_instance.send.assert_awaited_once_with(
            title="Test Title", message="Test Message", timeout=5000
        )


@pytest.mark.asyncio
async def test_notify_disabled_in_config() -> None:
    """Test that notify respects configuration when notifications are disabled."""
    with patch("clockman.utils.notifier.get_config_manager") as mock_config:
        mock_config_instance = MagicMock()
        mock_config_instance.are_notifications_enabled.return_value = False
        mock_config_instance.should_fallback_to_log.return_value = True
        mock_config.return_value = mock_config_instance

        with patch("clockman.utils.notifier.logger") as mock_logger:
            result = await notifier.notify("Test Title", "Test Message")

            assert result is None
            mock_logger.info.assert_called_once_with(
                "[NOTIFICATION] Test Title: Test Message"
            )


@pytest.mark.asyncio
async def test_notify_headless_environment() -> None:
    """Test notify behavior in headless environment (no DISPLAY)."""
    with (
        patch("clockman.utils.notifier.get_config_manager") as mock_config,
        patch.dict(os.environ, {}, clear=True),  # Clear DISPLAY and WAYLAND_DISPLAY
    ):
        mock_config_instance = MagicMock()
        mock_config_instance.are_notifications_enabled.return_value = True
        mock_config_instance.should_fallback_to_log.return_value = True
        mock_config.return_value = mock_config_instance

        with patch("clockman.utils.notifier.logger") as mock_logger:
            result = await notifier.notify("Test Title", "Test Message")

            assert result == "Headless or CI environment"
            mock_logger.info.assert_called_once_with(
                "[NOTIFICATION] Test Title: Test Message (headless/CI environment)"
            )


@pytest.mark.asyncio
async def test_notify_handles_exception() -> None:
    """Test that notify handles exceptions gracefully."""
    with (
        patch("clockman.utils.notifier._get_notifier") as mock_get_notifier,
        patch("clockman.utils.notifier.get_config_manager") as mock_config,
        patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True),
    ):
        # Setup mocks
        mock_notifier_instance = MagicMock()
        mock_notifier_instance.send = AsyncMock(side_effect=Exception("Test error"))
        mock_get_notifier.return_value = mock_notifier_instance

        mock_config_instance = MagicMock()
        mock_config_instance.are_notifications_enabled.return_value = True
        mock_config_instance.get_notification_timeout.return_value = 5000
        mock_config_instance.should_fallback_to_log.return_value = True
        mock_config.return_value = mock_config_instance

        with patch("clockman.utils.notifier.logger") as mock_logger:
            result = await notifier.notify("Test Title", "Test Message")

            assert result == "Failed to send notification: Test error"
            mock_logger.error.assert_called_once_with(
                "Failed to send notification: Test error"
            )
            mock_logger.info.assert_called_once_with(
                "[NOTIFICATION] Test Title: Test Message (fallback)"
            )


def test_notify_sync_success() -> None:
    """Test that notify_sync works correctly in normal conditions."""
    with patch("clockman.utils.notifier.asyncio.run") as mock_run:
        mock_run.return_value = None

        result = notifier.notify_sync("Sync Title", "Sync Message")

        assert result is None
        mock_run.assert_called_once()


def test_notify_sync_handles_runtime_error() -> None:
    """Test notify_sync fallback when RuntimeError occurs (nested event loop)."""
    with (
        patch(
            "clockman.utils.notifier.asyncio.get_running_loop",
            side_effect=RuntimeError("No running loop"),
        ),
        patch("clockman.utils.notifier.asyncio.run") as mock_run,
    ):
        mock_run.return_value = None

        result = notifier.notify_sync("Fallback Title", "Fallback Message")

        assert result is None
        mock_run.assert_called_once()


def test_notify_sync_in_async_context() -> None:
    """Test notify_sync when called from async context (uses thread executor)."""
    with (
        patch("clockman.utils.notifier.asyncio.get_running_loop") as mock_get_loop,
        patch("concurrent.futures.ThreadPoolExecutor") as mock_executor,
        patch("clockman.utils.notifier.notify") as mock_notify,
    ):
        # Mock running loop exists
        mock_get_loop.return_value = MagicMock()

        # Mock thread executor
        mock_executor_instance = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = None
        mock_executor_instance.submit.return_value = mock_future
        mock_executor.return_value.__enter__.return_value = mock_executor_instance

        # Mock the async notify function to avoid coroutine warnings
        mock_notify.return_value = None

        result = notifier.notify_sync("Async Context", "Message")

        assert result is None
        mock_executor_instance.submit.assert_called_once()


def test_notify_task_start() -> None:
    """Test task start notification helper."""
    with (
        patch("clockman.utils.notifier.get_config_manager") as mock_config,
        patch("clockman.utils.notifier.notify_sync") as mock_notify_sync,
    ):
        mock_config_instance = MagicMock()
        mock_config_instance.should_notify_task_start.return_value = True
        mock_config.return_value = mock_config_instance
        mock_notify_sync.return_value = None

        result = notifier.notify_task_start("Test Task", ["tag1", "tag2"])

        assert result is None
        mock_notify_sync.assert_called_once_with(
            "Clockman - Task Started", "Started working on: Test Task [tag1, tag2]"
        )


def test_notify_task_start_disabled() -> None:
    """Test task start notification when disabled in config."""
    with patch("clockman.utils.notifier.get_config_manager") as mock_config:
        mock_config_instance = MagicMock()
        mock_config_instance.should_notify_task_start.return_value = False
        mock_config.return_value = mock_config_instance

        result = notifier.notify_task_start("Test Task")

        assert result is None


def test_notify_task_stop() -> None:
    """Test task stop notification helper."""
    with (
        patch("clockman.utils.notifier.get_config_manager") as mock_config,
        patch("clockman.utils.notifier.notify_sync") as mock_notify_sync,
    ):
        mock_config_instance = MagicMock()
        mock_config_instance.should_notify_task_stop.return_value = True
        mock_config.return_value = mock_config_instance
        mock_notify_sync.return_value = None

        result = notifier.notify_task_stop("Test Task", "2h 30m", ["tag1"])

        assert result is None
        mock_notify_sync.assert_called_once_with(
            "Clockman - Task Completed", "Completed: Test Task [tag1]\nDuration: 2h 30m"
        )


def test_notify_error() -> None:
    """Test error notification helper."""
    with (
        patch("clockman.utils.notifier.get_config_manager") as mock_config,
        patch("clockman.utils.notifier.notify_sync") as mock_notify_sync,
    ):
        mock_config_instance = MagicMock()
        mock_config_instance.should_notify_errors.return_value = True
        mock_config.return_value = mock_config_instance
        mock_notify_sync.return_value = None

        result = notifier.notify_error("Something went wrong")

        assert result is None
        mock_notify_sync.assert_called_once_with(
            "Clockman - Error", "Something went wrong"
        )
