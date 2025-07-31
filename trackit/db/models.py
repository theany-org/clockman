"""
Database models for TrackIt.

This module defines the Pydantic models for time tracking sessions and related data.
"""

from datetime import datetime, timezone
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
        """Validate that end_time is after start_time."""
        if v is not None and info.data.get("start_time"):
            if v <= info.data["start_time"]:
                raise ValueError("End time must be after start time")
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


class ProjectStats(BaseModel):
    """Model for project-based statistics."""

    task_name: str = Field(..., description="Task/project name")
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
