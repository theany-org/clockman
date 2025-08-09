"""
Event definitions for Clockman integrations.

This module defines the core event types and data structures used throughout
the integration system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events that can be triggered in Clockman."""
    
    # Session events
    SESSION_STARTED = "session_started"
    SESSION_STOPPED = "session_stopped"
    SESSION_PAUSED = "session_paused"
    SESSION_RESUMED = "session_resumed"
    SESSION_UPDATED = "session_updated"
    SESSION_DELETED = "session_deleted"
    
    # Project events
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_DELETED = "project_deleted"
    
    # Export events
    EXPORT_COMPLETED = "export_completed"
    EXPORT_FAILED = "export_failed"
    
    # System events
    SYSTEM_STARTED = "system_started"
    SYSTEM_SHUTDOWN = "system_shutdown"


class ClockmanEvent(BaseModel):
    """
    Base event class for all Clockman events.
    
    This class provides the structure for all events that can be triggered
    within the Clockman application.
    """
    
    event_type: EventType = Field(..., description="Type of the event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the event occurred")
    event_id: str = Field(..., description="Unique identifier for this event")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data payload")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: str,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the event to a dictionary for serialization."""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClockmanEvent":
        """Create an event from a dictionary."""
        return cls(**data)


class SessionEvent(ClockmanEvent):
    """Event specifically for session-related actions."""
    
    @property
    def session_id(self) -> Optional[UUID]:
        """Get the session ID from the event data."""
        session_id_str = self.data.get("session_id")
        if session_id_str:
            try:
                return UUID(session_id_str)
            except (ValueError, TypeError):
                pass
        return None
    
    @property
    def task_name(self) -> Optional[str]:
        """Get the task name from the event data."""
        return self.data.get("task_name")
    
    @property
    def project_id(self) -> Optional[UUID]:
        """Get the project ID from the event data."""
        project_id_str = self.data.get("project_id")
        if project_id_str:
            try:
                return UUID(project_id_str)
            except (ValueError, TypeError):
                pass
        return None


class ProjectEvent(ClockmanEvent):
    """Event specifically for project-related actions."""
    
    @property
    def project_id(self) -> Optional[UUID]:
        """Get the project ID from the event data."""
        project_id_str = self.data.get("project_id")
        if project_id_str:
            try:
                return UUID(project_id_str)
            except (ValueError, TypeError):
                pass
        return None
    
    @property
    def project_name(self) -> Optional[str]:
        """Get the project name from the event data."""
        return self.data.get("project_name")


class ExportEvent(ClockmanEvent):
    """Event specifically for export-related actions."""
    
    @property
    def export_type(self) -> Optional[str]:
        """Get the export type from the event data."""
        return self.data.get("export_type")
    
    @property
    def file_path(self) -> Optional[str]:
        """Get the exported file path from the event data."""
        return self.data.get("file_path")
    
    @property
    def record_count(self) -> Optional[int]:
        """Get the number of records exported."""
        return self.data.get("record_count")