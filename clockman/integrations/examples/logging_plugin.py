"""
Example logging plugin for Clockman.

This plugin demonstrates how to create a plugin that logs time tracking events
to files, console, or external logging systems.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..events.events import ClockmanEvent, EventType
from ..plugins.base import BasePlugin, PluginInfo


class LoggingPlugin(BasePlugin):
    """
    A plugin that logs Clockman events to various destinations.
    
    This plugin supports:
    - File logging (JSON, text)
    - Console logging
    - Structured logging with different formats
    - Event filtering and formatting
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the logging plugin."""
        super().__init__(config)
        self.logger: Optional[logging.Logger] = None
        self.log_file_path: Optional[Path] = None
        self.json_log_file_path: Optional[Path] = None
        self.event_count = 0
    
    @property
    def info(self) -> PluginInfo:
        """Get information about this plugin."""
        return PluginInfo(
            name="Event Logger",
            version="1.0.0",
            description="Logs time tracking events to files and console",
            author="Clockman Team",
            website="https://github.com/theany-org/clockman",
            supported_events=list(EventType),  # Support all event types
            config_schema={
                "type": "object",
                "properties": {
                    "log_level": {
                        "type": "string",
                        "enum": ["DEBUG", "INFO", "WARNING", "ERROR"],
                        "default": "INFO",
                        "description": "Logging level for events"
                    },
                    "log_to_file": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to log events to a file"
                    },
                    "log_to_console": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to log events to console"
                    },
                    "log_file_path": {
                        "type": "string",
                        "description": "Path to the log file (optional)"
                    },
                    "json_format": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to use JSON format for logging"
                    },
                    "include_event_data": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to include event data in logs"
                    },
                    "event_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of event types to log (empty = all)"
                    },
                    "max_log_size": {
                        "type": "integer",
                        "default": 10485760,
                        "description": "Maximum log file size in bytes (10MB default)"
                    },
                    "backup_count": {
                        "type": "integer",
                        "default": 5,
                        "description": "Number of backup log files to keep"
                    }
                }
            }
        )
    
    def initialize(self) -> None:
        """Initialize the logging plugin."""
        # Set up logging configuration
        log_level = getattr(logging, self.get_config_value("log_level", "INFO"))
        
        # Create logger
        self.logger = logging.getLogger(f"clockman.plugin.{self.info.name}")
        self.logger.setLevel(log_level)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Set up file logging
        if self.get_config_value("log_to_file", True):
            self._setup_file_logging()
        
        # Set up console logging
        if self.get_config_value("log_to_console", False):
            self._setup_console_logging()
        
        # Set up JSON logging if enabled
        if self.get_config_value("json_format", False):
            self._setup_json_logging()
        
        self.logger.info(f"Initialized {self.info.name} plugin")
    
    def shutdown(self) -> None:
        """Shutdown the logging plugin."""
        if self.logger:
            self.logger.info(f"Shutting down {self.info.name} plugin (logged {self.event_count} events)")
            
            # Close all handlers
            for handler in self.logger.handlers:
                handler.close()
            
            self.logger.handlers.clear()
    
    def handle_event(self, event: ClockmanEvent) -> None:
        """Handle a Clockman event by logging it."""
        if not self.logger:
            return
        
        # Apply event filtering
        event_filter = self.get_config_value("event_filter", [])
        if event_filter and event.event_type.value not in event_filter:
            return
        
        self.event_count += 1
        
        # Create log message
        if self.get_config_value("json_format", False):
            self._log_event_json(event)
        else:
            self._log_event_text(event)
    
    def _setup_file_logging(self) -> None:
        """Set up file logging handler."""
        log_file_path = self.get_config_value("log_file_path")
        if not log_file_path:
            # Use default path in plugin config directory
            log_file_path = Path.cwd() / "logs" / "clockman_events.log"
        else:
            log_file_path = Path(log_file_path)
        
        # Create log directory
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Set up rotating file handler
        from logging.handlers import RotatingFileHandler
        
        max_size = self.get_config_value("max_log_size", 10485760)  # 10MB
        backup_count = self.get_config_value("backup_count", 5)
        
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_size,
            backupCount=backup_count
        )
        
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        
        self.logger.addHandler(file_handler)
        self.log_file_path = log_file_path
    
    def _setup_console_logging(self) -> None:
        """Set up console logging handler."""
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        
        self.logger.addHandler(console_handler)
    
    def _setup_json_logging(self) -> None:
        """Set up JSON file logging handler."""
        json_log_path = self.get_config_value("json_log_file_path")
        if not json_log_path:
            json_log_path = Path.cwd() / "logs" / "clockman_events.jsonl"
        else:
            json_log_path = Path(json_log_path)
        
        # Create log directory
        json_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Set up rotating file handler for JSON logs
        from logging.handlers import RotatingFileHandler
        
        max_size = self.get_config_value("max_log_size", 10485760)  # 10MB
        backup_count = self.get_config_value("backup_count", 5)
        
        json_handler = RotatingFileHandler(
            json_log_path,
            maxBytes=max_size,
            backupCount=backup_count
        )
        
        # Custom formatter for JSON logging
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                # The record.msg should contain the JSON data
                if isinstance(record.msg, dict):
                    return json.dumps(record.msg, default=str)
                return str(record.msg)
        
        json_handler.setFormatter(JsonFormatter())
        self.logger.addHandler(json_handler)
        self.json_log_file_path = json_log_path
    
    def _log_event_text(self, event: ClockmanEvent) -> None:
        """Log event in text format."""
        message_parts = [
            f"Event: {event.event_type.value}",
            f"ID: {event.event_id}",
            f"Time: {event.timestamp.isoformat()}",
        ]
        
        if self.get_config_value("include_event_data", True) and event.data:
            # Format event data nicely
            data_str = ", ".join(f"{k}={v}" for k, v in event.data.items())
            message_parts.append(f"Data: {data_str}")
        
        if event.metadata:
            metadata_str = ", ".join(f"{k}={v}" for k, v in event.metadata.items())
            message_parts.append(f"Metadata: {metadata_str}")
        
        message = " | ".join(message_parts)
        self.logger.info(message)
    
    def _log_event_json(self, event: ClockmanEvent) -> None:
        """Log event in JSON format."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "plugin": self.info.name,
            "event": event.to_dict()
        }
        
        if not self.get_config_value("include_event_data", True):
            # Remove event data if not wanted
            if "data" in log_data["event"]:
                del log_data["event"]["data"]
        
        self.logger.info(log_data)
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the plugin."""
        status = super().get_status()
        status.update({
            "events_logged": self.event_count,
            "log_file_path": str(self.log_file_path) if self.log_file_path else None,
            "json_log_file_path": str(self.json_log_file_path) if self.json_log_file_path else None,
            "log_level": self.get_config_value("log_level", "INFO"),
            "log_to_file": self.get_config_value("log_to_file", True),
            "log_to_console": self.get_config_value("log_to_console", False),
            "json_format": self.get_config_value("json_format", False),
        })
        return status


class SessionSummaryPlugin(BasePlugin):
    """
    A plugin that creates session summaries and daily reports.
    
    This plugin demonstrates more complex event handling by tracking
    session state and generating summaries.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the session summary plugin."""
        super().__init__(config)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.daily_stats: Dict[str, Dict[str, Any]] = {}
        self.logger: Optional[logging.Logger] = None
    
    @property
    def info(self) -> PluginInfo:
        """Get information about this plugin."""
        return PluginInfo(
            name="Session Summary",
            version="1.0.0",
            description="Creates session summaries and daily reports",
            author="Clockman Team",
            website="https://github.com/theany-org/clockman",
            supported_events=[
                EventType.SESSION_STARTED,
                EventType.SESSION_STOPPED,
                EventType.SESSION_UPDATED,
            ],
            config_schema={
                "type": "object",
                "properties": {
                    "summary_file_path": {
                        "type": "string",
                        "description": "Path to save session summaries"
                    },
                    "daily_report": {
                        "type": "boolean",
                        "default": True,
                        "description": "Generate daily reports"
                    },
                    "include_short_sessions": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include sessions shorter than 1 minute"
                    }
                }
            }
        )
    
    def initialize(self) -> None:
        """Initialize the session summary plugin."""
        self.logger = logging.getLogger(f"clockman.plugin.{self.info.name}")
        self.logger.setLevel(logging.INFO)
        
        # Set up file handler for summaries
        summary_path = self.get_config_value("summary_file_path")
        if not summary_path:
            summary_path = Path.cwd() / "logs" / "session_summaries.log"
        else:
            summary_path = Path(summary_path)
        
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        
        handler = logging.FileHandler(summary_path)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        self.logger.addHandler(handler)
        
        self.logger.info(f"Initialized {self.info.name} plugin")
    
    def shutdown(self) -> None:
        """Shutdown the session summary plugin."""
        if self.logger:
            # Generate final summary
            if self.active_sessions:
                self.logger.warning(f"Shutting down with {len(self.active_sessions)} active sessions")
            
            self.logger.info(f"Shutting down {self.info.name} plugin")
            
            for handler in self.logger.handlers:
                handler.close()
            self.logger.handlers.clear()
    
    def handle_event(self, event: ClockmanEvent) -> None:
        """Handle session events."""
        if event.event_type == EventType.SESSION_STARTED:
            self._handle_session_started(event)
        elif event.event_type == EventType.SESSION_STOPPED:
            self._handle_session_stopped(event)
        elif event.event_type == EventType.SESSION_UPDATED:
            self._handle_session_updated(event)
    
    def _handle_session_started(self, event: ClockmanEvent) -> None:
        """Handle session started event."""
        session_id = event.data.get("session_id")
        if not session_id:
            return
        
        self.active_sessions[session_id] = {
            "task_name": event.data.get("task_name"),
            "start_time": event.data.get("start_time"),
            "project_id": event.data.get("project_id"),
            "tags": event.data.get("tags", []),
            "description": event.data.get("description"),
        }
        
        if self.logger:
            self.logger.info(f"Started session: {event.data.get('task_name')} (ID: {session_id})")
    
    def _handle_session_stopped(self, event: ClockmanEvent) -> None:
        """Handle session stopped event."""
        session_id = event.data.get("session_id")
        if not session_id or session_id not in self.active_sessions:
            return
        
        session_info = self.active_sessions.pop(session_id)
        duration_seconds = event.data.get("duration_seconds", 0)
        
        # Skip very short sessions if configured
        if not self.get_config_value("include_short_sessions", False):
            if duration_seconds < 60:  # Less than 1 minute
                return
        
        # Create session summary
        summary = {
            "session_id": session_id,
            "task_name": session_info["task_name"],
            "description": session_info.get("description"),
            "project_id": session_info.get("project_id"),
            "tags": session_info.get("tags", []),
            "start_time": session_info["start_time"],
            "end_time": event.data.get("end_time"),
            "duration_seconds": duration_seconds,
            "duration_formatted": self._format_duration(duration_seconds),
        }
        
        if self.logger:
            duration_str = self._format_duration(duration_seconds)
            self.logger.info(f"Completed session: {session_info['task_name']} - Duration: {duration_str}")
            
            # Log detailed summary
            if summary.get("description"):
                self.logger.info(f"  Description: {summary['description']}")
            if summary.get("tags"):
                self.logger.info(f"  Tags: {', '.join(summary['tags'])}")
        
        # Update daily stats if enabled
        if self.get_config_value("daily_report", True):
            self._update_daily_stats(summary)
    
    def _handle_session_updated(self, event: ClockmanEvent) -> None:
        """Handle session updated event."""
        session_id = event.data.get("session_id")
        if session_id in self.active_sessions:
            # Update active session info
            session_info = self.active_sessions[session_id]
            session_info.update({
                "task_name": event.data.get("task_name", session_info["task_name"]),
                "description": event.data.get("description", session_info.get("description")),
                "tags": event.data.get("tags", session_info.get("tags", [])),
            })
    
    def _update_daily_stats(self, session_summary: Dict[str, Any]) -> None:
        """Update daily statistics."""
        # Extract date from start time
        start_time = session_summary.get("start_time", "")
        try:
            date_str = start_time.split("T")[0]  # Get date part of ISO timestamp
        except (AttributeError, IndexError):
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        if date_str not in self.daily_stats:
            self.daily_stats[date_str] = {
                "total_sessions": 0,
                "total_duration": 0,
                "tasks": set(),
                "projects": set(),
            }
        
        stats = self.daily_stats[date_str]
        stats["total_sessions"] += 1
        stats["total_duration"] += session_summary.get("duration_seconds", 0)
        stats["tasks"].add(session_summary.get("task_name", ""))
        
        if session_summary.get("project_id"):
            stats["projects"].add(session_summary.get("project_id"))
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the plugin."""
        status = super().get_status()
        status.update({
            "active_sessions": len(self.active_sessions),
            "tracked_days": len(self.daily_stats),
            "daily_report_enabled": self.get_config_value("daily_report", True),
        })
        return status


# Example configuration functions

def create_logging_plugin_config(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = False,
    json_format: bool = False,
    log_file_path: Optional[str] = None,
    event_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Create a configuration for the logging plugin.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
        json_format: Whether to use JSON format
        log_file_path: Custom log file path
        event_filter: List of event types to log
        
    Returns:
        Plugin configuration dictionary
    """
    config = {
        "log_level": log_level,
        "log_to_file": log_to_file,
        "log_to_console": log_to_console,
        "json_format": json_format,
        "include_event_data": True,
        "max_log_size": 10485760,  # 10MB
        "backup_count": 5,
    }
    
    if log_file_path:
        config["log_file_path"] = log_file_path
    
    if event_filter:
        config["event_filter"] = event_filter
    
    return config


def create_session_summary_config(
    summary_file_path: Optional[str] = None,
    daily_report: bool = True,
    include_short_sessions: bool = False,
) -> Dict[str, Any]:
    """
    Create a configuration for the session summary plugin.
    
    Args:
        summary_file_path: Custom summary file path
        daily_report: Whether to generate daily reports
        include_short_sessions: Whether to include sessions < 1 minute
        
    Returns:
        Plugin configuration dictionary
    """
    config = {
        "daily_report": daily_report,
        "include_short_sessions": include_short_sessions,
    }
    
    if summary_file_path:
        config["summary_file_path"] = summary_file_path
    
    return config


if __name__ == "__main__":
    # Example usage
    print("Testing logging plugin...")
    
    # Create and test logging plugin
    logging_config = create_logging_plugin_config(
        log_level="DEBUG",
        log_to_console=True,
        json_format=False,
    )
    
    plugin = LoggingPlugin(logging_config)
    print(f"Plugin info: {plugin.info.name} v{plugin.info.version}")
    print(f"Supported events: {len(plugin.info.supported_events)}")
    
    # Test plugin initialization
    try:
        plugin.initialize()
        print("Plugin initialized successfully")
        plugin.shutdown()
        print("Plugin shutdown successfully")
    except Exception as e:
        print(f"Plugin test failed: {e}")