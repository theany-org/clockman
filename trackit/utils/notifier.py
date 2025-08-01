"""
Desktop notification service for TrackIt.

This module provides desktop notification functionality with proper error handling,
logging integration, and configuration support.
"""

import asyncio
import logging
import os
from typing import Optional

from desktop_notifier import DesktopNotifier

from .config import get_config_manager

logger = logging.getLogger(__name__)

# Global notifier instance
_notifier: Optional[DesktopNotifier] = None


def _get_notifier() -> DesktopNotifier:
    """Get or create the global DesktopNotifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = DesktopNotifier(app_name="TrackIt")
    return _notifier


async def notify(title: str, message: str) -> Optional[str]:
    """
    Send a desktop notification asynchronously.

    Args:
        title: The notification title
        message: The notification message

    Returns:
        None if successful, error message string if failed

    Example:
        >>> error = await notify("Task Started", "Working on project")
        >>> if error:
        ...     logger.warning(f"Notification failed: {error}")
    """
    config = get_config_manager()

    # Check if notifications are disabled
    if not config.are_notifications_enabled():
        if config.should_fallback_to_log():
            logger.info(f"[NOTIFICATION] {title}: {message}")
        return None

    # Check for headless environment or CI
    is_headless = (
        (not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"))
        or os.environ.get("CI") == "true"
        or os.environ.get("TRACKIT_HEADLESS") == "true"
    )

    if is_headless:
        if config.should_fallback_to_log():
            logger.info(f"[NOTIFICATION] {title}: {message} (headless/CI environment)")
        return "Headless or CI environment"

    try:
        notifier = _get_notifier()
        timeout_ms = config.get_notification_timeout()
        await notifier.send(title=title, message=message, timeout=timeout_ms)
        logger.debug(f"Notification sent: {title}")
        return None

    except ImportError as e:
        error_msg = f"Desktop notifications not available: {e}"
        logger.warning(error_msg)
        if config.should_fallback_to_log():
            logger.info(f"[NOTIFICATION] {title}: {message} (fallback)")
        return error_msg

    except Exception as e:
        error_msg = f"Failed to send notification: {e}"
        logger.error(error_msg)
        if config.should_fallback_to_log():
            logger.info(f"[NOTIFICATION] {title}: {message} (fallback)")
        return error_msg


def notify_sync(title: str, message: str) -> Optional[str]:
    """
    Send a desktop notification synchronously.

    This function handles event loop issues gracefully and provides
    proper error handling for synchronous contexts.

    Args:
        title: The notification title
        message: The notification message

    Returns:
        None if successful, error message string if failed

    Example:
        >>> error = notify_sync("Task Completed", "Project finished")
        >>> if error:
        ...     print(f"Could not send notification: {error}")
    """
    try:
        # Try to use existing event loop
        asyncio.get_running_loop()
        # If we're in an async context, we need to use a thread
        import concurrent.futures

        def run_in_thread() -> Optional[str]:
            # Create new event loop in thread
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(notify(title, message))
            finally:
                new_loop.close()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            result = future.result(timeout=10)  # 10 second timeout
            return result

    except RuntimeError:
        # No running event loop, we can use asyncio.run
        try:
            return asyncio.run(notify(title, message))
        except Exception as e:
            logger.error(f"Failed to run notification: {e}")
            config = get_config_manager()
            if config.should_fallback_to_log():
                logger.info(f"[NOTIFICATION] {title}: {message} (fallback)")
            return str(e)
    except Exception as e:
        logger.error(f"Unexpected error in notify_sync: {e}")
        config = get_config_manager()
        if config.should_fallback_to_log():
            logger.info(f"[NOTIFICATION] {title}: {message} (fallback)")
        return str(e)


def notify_task_start(task_name: str, tags: Optional[list] = None) -> Optional[str]:
    """
    Send a task start notification if enabled in configuration.

    Args:
        task_name: Name of the task being started
        tags: Optional list of task tags

    Returns:
        None if successful, error message string if failed
    """
    config = get_config_manager()
    if not config.should_notify_task_start():
        return None

    tag_str = f" [{', '.join(tags)}]" if tags else ""
    message = f"Started working on: {task_name}{tag_str}"
    return notify_sync("TrackIt - Task Started", message)


def notify_task_stop(
    task_name: str, duration: str, tags: Optional[list] = None
) -> Optional[str]:
    """
    Send a task stop notification if enabled in configuration.

    Args:
        task_name: Name of the task being stopped
        duration: Duration the task was active
        tags: Optional list of task tags

    Returns:
        None if successful, error message string if failed
    """
    config = get_config_manager()
    if not config.should_notify_task_stop():
        return None

    tag_str = f" [{', '.join(tags)}]" if tags else ""
    message = f"Completed: {task_name}{tag_str}\nDuration: {duration}"
    return notify_sync("TrackIt - Task Completed", message)


def notify_error(error_message: str) -> Optional[str]:
    """
    Send an error notification if enabled in configuration.

    Args:
        error_message: The error message to display

    Returns:
        None if successful, error message string if failed
    """
    config = get_config_manager()
    if not config.should_notify_errors():
        return None

    return notify_sync("TrackIt - Error", error_message)
