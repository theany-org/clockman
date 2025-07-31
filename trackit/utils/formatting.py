"""
Utility functions for formatting time and display elements.

This module provides consistent formatting for durations, dates, and other display elements.
"""

from datetime import datetime, timedelta
from typing import Optional

from .config import get_config_manager


def format_duration(duration: timedelta, show_seconds: Optional[bool] = None) -> str:
    """
    Format a timedelta as a human-readable duration string.
    
    Args:
        duration: The timedelta to format
        show_seconds: Whether to show seconds (uses config default if None)
        
    Returns:
        Formatted duration string (e.g., "2h 30m 15s", "1h 45m")
    """
    if show_seconds is None:
        config = get_config_manager()
        show_seconds = config.show_seconds()
    
    total_seconds = int(duration.total_seconds())
    
    if total_seconds < 0:
        return "0s"
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    parts = []
    
    if hours > 0:
        parts.append(f"{hours}h")
    
    if minutes > 0 or (hours > 0 and seconds > 0):
        parts.append(f"{minutes}m")
    
    if show_seconds and (seconds > 0 or not parts):
        parts.append(f"{seconds}s")
    
    return " ".join(parts) if parts else "0s"


def format_datetime(dt: datetime, include_date: bool = True, include_time: bool = True) -> str:
    """
    Format a datetime for display.
    
    Args:
        dt: The datetime to format
        include_date: Whether to include the date
        include_time: Whether to include the time
        
    Returns:
        Formatted datetime string
    """
    config = get_config_manager()
    
    if dt.tzinfo is None:
        # Assume UTC if no timezone
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Convert to local time for display
    local_dt = dt.astimezone()
    
    parts = []
    
    if include_date:
        date_format = config.get_date_format()
        parts.append(local_dt.strftime(date_format))
    
    if include_time:
        time_format = config.get_time_format()
        if not config.show_seconds():
            # Remove seconds from format if not showing them
            time_format = time_format.replace(':%S', '')
        parts.append(local_dt.strftime(time_format))
    
    return " ".join(parts)


def format_date(dt: datetime) -> str:
    """Format just the date portion of a datetime."""
    return format_datetime(dt, include_date=True, include_time=False)


def format_time(dt: datetime) -> str:
    """Format just the time portion of a datetime."""
    return format_datetime(dt, include_date=False, include_time=True)


def truncate_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Truncate text to a maximum length with ellipsis.
    
    Args:
        text: Text to potentially truncate
        max_length: Maximum length (uses config default if None)
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if max_length is None:
        config = get_config_manager()
        max_length = config.get_max_task_name_length()
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


def format_bytes(size: int) -> str:
    """
    Format a byte size as a human-readable string.
    
    Args:
        size: Size in bytes
        
    Returns:
        Formatted size string (e.g., "1.2 KB", "3.4 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            if unit == 'B':
                return f"{size} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_percentage(value: float, total: float) -> str:
    """
    Format a percentage value.
    
    Args:
        value: The value
        total: The total to calculate percentage against
        
    Returns:
        Formatted percentage string (e.g., "75.0%")
    """
    if total == 0:
        return "0.0%"
    
    percentage = (value / total) * 100
    return f"{percentage:.1f}%"


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    """
    Return singular or plural form based on count.
    
    Args:
        count: The count
        singular: Singular form
        plural: Plural form (defaults to singular + 's')
        
    Returns:
        Properly pluralized string
    """
    if plural is None:
        plural = singular + 's'
    
    return singular if count == 1 else plural


def format_relative_time(dt: datetime) -> str:
    """
    Format a datetime as relative time (e.g., "2 hours ago", "in 30 minutes").
    
    Args:
        dt: The datetime to format
        
    Returns:
        Relative time string
    """
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    
    now = datetime.now(dt.tzinfo)
    diff = dt - now
    abs_diff = abs(diff.total_seconds())
    
    if abs_diff < 60:
        return "just now"
    elif abs_diff < 3600:
        minutes = int(abs_diff // 60)
        unit = pluralize(minutes, "minute")
        if diff.total_seconds() > 0:
            return f"in {minutes} {unit}"
        else:
            return f"{minutes} {unit} ago"
    elif abs_diff < 86400:
        hours = int(abs_diff // 3600)
        unit = pluralize(hours, "hour")
        if diff.total_seconds() > 0:
            return f"in {hours} {unit}"
        else:
            return f"{hours} {unit} ago"
    else:
        days = int(abs_diff // 86400)
        unit = pluralize(days, "day")
        if diff.total_seconds() > 0:
            return f"in {days} {unit}"
        else:
            return f"{days} {unit} ago"