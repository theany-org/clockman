"""
Cross-platform notification utilities for TrackIt.

This module provides desktop notifications for time tracking events.
"""

import logging
from typing import Optional

try:
    from plyer import notification

    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages desktop notifications for TrackIt."""

    def __init__(self, app_name: str = "TrackIt"):
        """
        Initialize notification manager.

        Args:
            app_name: Name of the application for notifications
        """
        self.app_name = app_name
        self.enabled = NOTIFICATIONS_AVAILABLE

        if not self.enabled:
            logger.warning("Notifications are not available on this system")

    def show_notification(
        self,
        title: str,
        message: str,
        timeout: int = 5,
        app_icon: Optional[str] = None,
    ) -> None:
        """
        Show a desktop notification.

        Args:
            title: Notification title
            message: Notification message
            timeout: Notification display timeout in seconds
            app_icon: Path to app icon (optional)
        """
        if not self.enabled:
            logger.debug(f"Notification would show: {title} - {message}")
            return

        try:
            notification.notify(
                title=title,
                message=message,
                app_name=self.app_name,
                timeout=timeout,
                app_icon=app_icon,
            )
        except Exception as e:
            logger.error(f"Failed to show notification: {e}")

    def notify_session_started(
        self, task_name: str, tags: Optional[list] = None
    ) -> None:
        """
        Show notification for session start.

        Args:
            task_name: Name of the started task
            tags: Optional list of tags
        """
        title = "Time Tracking Started"
        message = f"Now tracking: {task_name}"

        if tags:
            message += f"\nTags: {', '.join(tags)}"

        self.show_notification(title, message)

    def notify_session_stopped(self, task_name: str, duration: str) -> None:
        """
        Show notification for session stop.

        Args:
            task_name: Name of the stopped task
            duration: Duration of the session as formatted string
        """
        title = "Time Tracking Stopped"
        message = f"Stopped: {task_name}\nDuration: {duration}"

        self.show_notification(title, message)

    def notify_error(self, error_message: str) -> None:
        """
        Show error notification.

        Args:
            error_message: Error message to display
        """
        title = "TrackIt Error"
        self.show_notification(title, error_message, timeout=8)
