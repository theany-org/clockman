"""
System tray manager for TrackIt.

This module provides the main system tray interface that allows users to interact
with the time tracking application from the system tray.
"""

import logging
import threading
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import pystray as _pystray

import pystray
from pystray import MenuItem, Menu

from ..core.time_tracker import TimeTracker, ActiveSessionError, TimeTrackingError
from ..utils.config import get_config_manager
from ..utils.formatting import format_duration
from .icons import create_tray_icon
from .notifications import NotificationManager

logger = logging.getLogger(__name__)


class TrayManager:
    """Manages the system tray interface for TrackIt."""

    def __init__(self):
        """Initialize the tray manager."""
        self.config = get_config_manager()
        self.tracker = TimeTracker(self.config.get_data_dir())
        self.notifications = NotificationManager()

        # Create tray icons
        self.icon_inactive = create_tray_icon(is_active=False)
        self.icon_active = create_tray_icon(is_active=True)

        # Initialize tray icon
        self.tray_icon: Optional[pystray.Icon] = pystray.Icon(
            "trackit",
            self.icon_inactive,
            "TrackIt - Time Tracker",
            menu=self._create_menu(),
        )

        # Track state
        self._is_running = False
        self._update_thread: Optional[threading.Thread] = None

    def _create_menu(self) -> Menu:
        """Create the system tray context menu."""
        return Menu(
            MenuItem("Start Tracking", self._show_start_menu),
            MenuItem(
                "Stop Tracking", self._stop_tracking, enabled=self._is_tracking_active()
            ),
            Menu.SEPARATOR,
            MenuItem("Current Status", self._show_status),
            MenuItem("Recent Tasks", self._show_recent_tasks),
            Menu.SEPARATOR,
            MenuItem("Open Terminal", self._open_terminal),
            Menu.SEPARATOR,
            MenuItem("Exit", self._quit_application),
        )

    def _is_tracking_active(self, item: Optional[MenuItem] = None) -> bool:
        """Check if time tracking is currently active."""
        try:
            active_session = self.tracker.get_active_session()
            return active_session is not None
        except Exception:
            return False

    def _show_start_menu(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Show the start tracking submenu."""
        # Create a simple task input dialog using the notification system
        # In a full implementation, you might want to use tkinter or another GUI toolkit

        # For now, we'll provide some common task options
        recent_tasks = self._get_recent_task_names()

        # Create submenu with recent tasks and "Other" option
        submenu_items = []

        for task in recent_tasks[:5]:  # Show last 5 recent tasks
            submenu_items.append(
                MenuItem(
                    f"📋 {task}",
                    lambda icon, item, task_name=task: self._start_tracking(task_name),
                )
            )

        if recent_tasks:
            submenu_items.append(Menu.SEPARATOR)

        submenu_items.append(MenuItem("➕ New Task...", self._start_new_task))

        # Update the menu with submenu
        start_menu = Menu(*submenu_items)
        self.tray_icon.menu = Menu(
            MenuItem("Start Tracking", start_menu),
            MenuItem(
                "Stop Tracking", self._stop_tracking, enabled=self._is_tracking_active()
            ),
            Menu.SEPARATOR,
            MenuItem("Current Status", self._show_status),
            MenuItem("Recent Tasks", self._show_recent_tasks),
            Menu.SEPARATOR,
            MenuItem("Open Terminal", self._open_terminal),
            Menu.SEPARATOR,
            MenuItem("Exit", self._quit_application),
        )

    def _get_recent_task_names(self) -> List[str]:
        """Get list of recent task names."""
        try:
            recent_entries = self.tracker.get_recent_entries(limit=10)
            # Get unique task names while preserving order
            seen = set()
            unique_tasks = []
            for entry in recent_entries:
                if entry.task_name not in seen:
                    unique_tasks.append(entry.task_name)
                    seen.add(entry.task_name)
            return unique_tasks
        except Exception as e:
            logger.error(f"Error getting recent tasks: {e}")
            return []

    def _start_new_task(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Start tracking a new task."""
        # This is a simplified implementation
        # In a production app, you'd want a proper input dialog
        self.notifications.show_notification(
            "Start New Task",
            "Use 'tracker start <task_name>' in terminal to start a custom task",
            timeout=8,
        )

    def _start_tracking(self, task_name: str) -> None:
        """Start tracking the specified task."""
        try:
            # Stop any active session first
            active_session = self.tracker.get_active_session()
            if active_session:
                self.tracker.stop_session()
                duration = datetime.now(timezone.utc) - active_session.start_time
                self.notifications.notify_session_stopped(
                    active_session.task_name, format_duration(duration)
                )

            # Start new session
            session_id = self.tracker.start_session(task_name=task_name)
            self.notifications.notify_session_started(task_name)

            # Update tray icon to active state
            self.tray_icon.icon = self.icon_active
            self.tray_icon.title = f"TrackIt - Tracking: {task_name}"

            logger.info(f"Started tracking task: {task_name} (ID: {session_id})")

        except Exception as e:
            error_msg = f"Failed to start tracking: {str(e)}"
            logger.error(error_msg)
            self.notifications.notify_error(error_msg)

    def _stop_tracking(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Stop the currently active tracking session."""
        try:
            active_session = self.tracker.get_active_session()
            if not active_session:
                self.notifications.show_notification(
                    "No Active Session", "No time tracking session is currently active"
                )
                return

            stopped_session = self.tracker.stop_session()

            if stopped_session and stopped_session.end_time:
                duration = stopped_session.end_time - stopped_session.start_time
                self.notifications.notify_session_stopped(
                    stopped_session.task_name, format_duration(duration)
                )

                # Update tray icon to inactive state
                self.tray_icon.icon = self.icon_inactive
                self.tray_icon.title = "TrackIt - Time Tracker"

                logger.info(f"Stopped tracking task: {stopped_session.task_name}")

        except Exception as e:
            error_msg = f"Failed to stop tracking: {str(e)}"
            logger.error(error_msg)
            self.notifications.notify_error(error_msg)

    def _show_status(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Show current tracking status."""
        try:
            active_session = self.tracker.get_active_session()

            if not active_session:
                self.notifications.show_notification(
                    "TrackIt Status", "No active session"
                )
                return

            # Calculate current duration
            current_time = datetime.now(timezone.utc)
            duration = current_time - active_session.start_time

            message = f"Task: {active_session.task_name}\nDuration: {format_duration(duration)}"

            if active_session.tags:
                message += f"\nTags: {', '.join(active_session.tags)}"

            self.notifications.show_notification("Current Session", message, timeout=8)

        except Exception as e:
            error_msg = f"Failed to get status: {str(e)}"
            logger.error(error_msg)
            self.notifications.notify_error(error_msg)

    def _show_recent_tasks(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Show recent tasks."""
        try:
            recent_tasks = self._get_recent_task_names()

            if not recent_tasks:
                self.notifications.show_notification(
                    "Recent Tasks", "No recent tasks found"
                )
                return

            # Show up to 5 recent tasks
            tasks_text = "\n".join(f"• {task}" for task in recent_tasks[:5])

            if len(recent_tasks) > 5:
                tasks_text += f"\n... and {len(recent_tasks) - 5} more"

            self.notifications.show_notification("Recent Tasks", tasks_text, timeout=10)

        except Exception as e:
            error_msg = f"Failed to get recent tasks: {str(e)}"
            logger.error(error_msg)
            self.notifications.notify_error(error_msg)

    def _open_terminal(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Open terminal with TrackIt CLI."""
        import subprocess
        import os

        try:
            # Try to open terminal with the tracker command ready
            if os.name == "posix":  # Linux/macOS
                # Try various terminal emulators
                terminals = [
                    "gnome-terminal",
                    "konsole",
                    "xterm",
                    "x-terminal-emulator",
                ]
                for terminal in terminals:
                    try:
                        subprocess.Popen(
                            [terminal, "--", "bash", "-c", "tracker --help; exec bash"]
                        )
                        return
                    except FileNotFoundError:
                        continue

                # Fallback: just show help in notification
                self.notifications.show_notification(
                    "TrackIt CLI",
                    "Run 'tracker --help' in your terminal to see available commands",
                    timeout=10,
                )
            else:
                # Windows
                subprocess.Popen(["cmd", "/k", "tracker --help"])

        except Exception as e:
            logger.error(f"Failed to open terminal: {e}")
            self.notifications.show_notification(
                "TrackIt CLI",
                "Run 'tracker --help' in your terminal to see available commands",
                timeout=10,
            )

    def _quit_application(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Quit the tray application."""
        logger.info("Quitting TrackIt tray application")
        self._is_running = False
        icon.stop()

    def _update_tray_state(self) -> None:
        """Update tray icon state based on current tracking status."""
        while self._is_running:
            try:
                active_session = self.tracker.get_active_session()

                if active_session:
                    # Update to active state
                    if self.tray_icon.icon != self.icon_active:
                        self.tray_icon.icon = self.icon_active

                    # Update title with current task and duration
                    current_time = datetime.now(timezone.utc)
                    duration = current_time - active_session.start_time
                    self.tray_icon.title = f"TrackIt - {active_session.task_name} ({format_duration(duration)})"
                else:
                    # Update to inactive state
                    if self.tray_icon.icon != self.icon_inactive:
                        self.tray_icon.icon = self.icon_inactive
                        self.tray_icon.title = "TrackIt - Time Tracker"

                # Update every 30 seconds
                threading.Event().wait(30)

            except Exception as e:
                logger.error(f"Error updating tray state: {e}")
                threading.Event().wait(30)

    def run(self) -> None:
        """Run the system tray application."""
        logger.info("Starting TrackIt system tray")
        self._is_running = True

        # Start background thread to update tray state
        self._update_thread = threading.Thread(
            target=self._update_tray_state, daemon=True
        )
        self._update_thread.start()

        # Run the tray icon (this blocks until quit)
        self.tray_icon.run()

        logger.info("TrackIt system tray stopped")
