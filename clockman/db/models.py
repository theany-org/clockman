"""
Database models for Clockman.

This module defines the Pydantic models for time tracking sessions and related data.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimeSession(BaseModel):
    """Model for a time tracking session."""

    id: UUID = Field(default_factory=uuid4, description="Unique session identifier")
    task_name: str = Field(
        ..., min_length=1, max_length=255, description="Name of the task"
    )
    description: Optional[str] = Field(
        None, max_length=1000, description="Optional task description"
    )
    project_id: Optional[UUID] = Field(
        None, description="Associated project ID"
    )
    tags: List[str] = Field(
        default_factory=list, description="Tags associated with the task"
    )
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Session start time",
    )
    end_time: Optional[datetime] = Field(
        None, description="Session end time (None for active sessions)"
    )
    is_active: bool = Field(
        default=True, description="Whether the session is currently active"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
    )

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: Optional[datetime], info: Any) -> Optional[datetime]:
        """Validate that end_time is after start_time and not in the future."""
        if v is not None:
            # Check that end time is not in the future
            now = datetime.now(timezone.utc)
            if v > now:
                raise ValueError("End time cannot be in the future")
            
            # Check that end time is after start time
            if info.data.get("start_time"):
                if v <= info.data["start_time"]:
                    raise ValueError("End time must be after start time")
                
                # Check for reasonable duration (not more than 24 hours)
                duration = v - info.data["start_time"]
                if duration.total_seconds() > 86400:  # 24 hours
                    raise ValueError("Session duration cannot exceed 24 hours")
        return v

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, v: datetime) -> datetime:
        """Validate start_time."""
        # Check that start time is not more than 7 days in the future
        now = datetime.now(timezone.utc)
        if v > now + timedelta(days=7):
            raise ValueError("Start time cannot be more than 7 days in the future")
        
        # Check that start time is not more than 1 year in the past (reasonable limit)
        if v < now - timedelta(days=365):
            raise ValueError("Start time cannot be more than 1 year in the past")
        
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalize tags."""
        # Remove duplicates and empty strings, normalize case
        return list(set(tag.lower().strip() for tag in v if tag.strip()))

    @property
    def duration(self) -> Optional[float]:
        """Get session duration in seconds. Returns None for active sessions."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()

    def stop(self, end_time: Optional[datetime] = None) -> None:
        """Stop the session with the given end time."""
        if end_time is None:
            end_time = datetime.now(timezone.utc)

        self.end_time = end_time
        self.is_active = False


class DailyStats(BaseModel):
    """Model for daily time tracking statistics."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    total_duration: float = Field(0.0, description="Total tracked time in seconds")
    session_count: int = Field(0, description="Number of sessions")
    unique_tasks: int = Field(0, description="Number of unique tasks")
    most_used_tags: List[str] = Field(
        default_factory=list, description="Most frequently used tags"
    )
    longest_session: Optional[float] = Field(
        None, description="Longest session duration in seconds"
    )


class Project(BaseModel):
    """Model for project organization."""

    id: UUID = Field(default_factory=uuid4, description="Unique project identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Project description"
    )
    parent_id: Optional[UUID] = Field(
        None, description="Parent project ID for hierarchy"
    )
    is_active: bool = Field(default=True, description="Whether project is active")
    default_tags: List[str] = Field(
        default_factory=list, description="Default tags for tasks in this project"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Project creation time",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional project metadata"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and normalize project name."""
        return v.strip()


class ProjectStats(BaseModel):
    """Model for project-based statistics."""

    task_name: str = Field(..., description="Task/project name")
    project_name: Optional[str] = Field(None, description="Associated project name")
    total_duration: float = Field(0.0, description="Total time spent in seconds")
    session_count: int = Field(0, description="Number of sessions")
    average_session: float = Field(
        0.0, description="Average session duration in seconds"
    )
    tags: List[str] = Field(default_factory=list, description="Associated tags")
    first_session: Optional[datetime] = Field(
        None, description="First session start time"
    )
    last_session: Optional[datetime] = Field(
        None, description="Last session start time"
    )
