"""
Time validation utilities for accurate time tracking.

This module provides utilities for validating and improving time tracking accuracy.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from ..db.models import TimeSession


class TimeValidationError(Exception):
    """Exception raised for time validation errors."""
    pass


class TimeAccuracyValidator:
    """Validator for ensuring time tracking accuracy."""

    def __init__(self):
        """Initialize the validator with default settings."""
        self.max_session_duration = timedelta(hours=24)
        self.min_session_duration = timedelta(seconds=1)
        self.future_time_threshold = timedelta(minutes=5)  # Allow 5 minutes in future for clock drift

    def validate_session_duration(
        self, 
        start_time: datetime, 
        end_time: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """
        Validate session duration.

        Args:
            start_time: Session start time
            end_time: Session end time (None for active sessions)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if end_time is None:
            # For active sessions, validate against current time
            end_time = datetime.now(timezone.utc)

        duration = end_time - start_time

        # Check minimum duration
        if duration < self.min_session_duration:
            return False, f"Session duration is too short: {duration.total_seconds():.1f} seconds"

        # Check maximum duration
        if duration > self.max_session_duration:
            hours = duration.total_seconds() / 3600
            return False, f"Session duration is too long: {hours:.1f} hours"

        return True, ""

    def validate_session_times(
        self, 
        start_time: datetime, 
        end_time: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """
        Validate session start and end times.

        Args:
            start_time: Session start time
            end_time: Session end time (None for active sessions)

        Returns:
            Tuple of (is_valid, error_message)
        """
        now = datetime.now(timezone.utc)

        # Validate start time
        if start_time > now + self.future_time_threshold:
            return False, "Start time cannot be in the future"

        # Check if start time is too far in the past (1 year limit)
        if start_time < now - timedelta(days=365):
            return False, "Start time cannot be more than 1 year in the past"

        # Validate end time if provided
        if end_time is not None:
            if end_time > now + self.future_time_threshold:
                return False, "End time cannot be in the future"

            if end_time <= start_time:
                return False, "End time must be after start time"

        return True, ""

    def detect_potential_idle_time(
        self, 
        session: TimeSession, 
        threshold_hours: float = 4.0
    ) -> Tuple[bool, str]:
        """
        Detect if a session might contain significant idle time.

        Args:
            session: Time session to analyze
            threshold_hours: Threshold in hours for flagging potential idle time

        Returns:
            Tuple of (has_potential_idle, warning_message)
        """
        if session.end_time is None:
            # Check active session duration
            duration = datetime.now(timezone.utc) - session.start_time
        else:
            duration = session.end_time - session.start_time

        threshold = timedelta(hours=threshold_hours)

        if duration > threshold:
            hours = duration.total_seconds() / 3600
            return True, f"Session is {hours:.1f} hours long - may contain idle time"

        return False, ""

    def find_overlapping_sessions(self, sessions: List[TimeSession]) -> List[Tuple[TimeSession, TimeSession]]:
        """
        Find overlapping sessions that might indicate data integrity issues.

        Args:
            sessions: List of sessions to check

        Returns:
            List of tuples containing overlapping session pairs
        """
        overlaps = []
        completed_sessions = [s for s in sessions if s.end_time is not None]
        completed_sessions.sort(key=lambda s: s.start_time)

        for i, session1 in enumerate(completed_sessions):
            for session2 in completed_sessions[i + 1:]:
                # Check if session1 overlaps with session2
                if (session1.start_time <= session2.start_time < session1.end_time) or \
                   (session2.start_time <= session1.start_time < session2.end_time):
                    overlaps.append((session1, session2))

        return overlaps

    def suggest_time_corrections(
        self, 
        session: TimeSession
    ) -> List[str]:
        """
        Suggest potential corrections for time tracking issues.

        Args:
            session: Session to analyze

        Returns:
            List of suggestion strings
        """
        suggestions = []

        # Check for very long sessions
        is_idle, idle_msg = self.detect_potential_idle_time(session)
        if is_idle:
            suggestions.append(f"Consider splitting long session: {idle_msg}")

        # Check for very short sessions
        if session.end_time:
            duration = session.end_time - session.start_time
            if duration < timedelta(minutes=1):
                suggestions.append("Very short session - consider if this was intentional")

        # Check for sessions starting at unusual times
        hour = session.start_time.hour
        if hour < 5 or hour > 23:
            suggestions.append(f"Session started at {hour:02d}:XX - verify this is correct")

        return suggestions

    def calculate_accuracy_score(
        self, 
        sessions: List[TimeSession]
    ) -> Tuple[float, dict]:
        """
        Calculate a time tracking accuracy score based on various factors.

        Args:
            sessions: List of sessions to analyze

        Returns:
            Tuple of (score_0_to_100, detailed_metrics)
        """
        if not sessions:
            return 100.0, {"message": "No sessions to analyze"}

        score = 100.0
        metrics = {
            "total_sessions": len(sessions),
            "completed_sessions": 0,
            "potential_idle_sessions": 0,
            "overlapping_sessions": 0,
            "unusual_time_sessions": 0,
            "very_short_sessions": 0,
            "very_long_sessions": 0,
        }

        completed_sessions = [s for s in sessions if s.end_time is not None]
        metrics["completed_sessions"] = len(completed_sessions)

        # Analyze each session
        for session in completed_sessions:
            # Check for potential idle time
            is_idle, _ = self.detect_potential_idle_time(session, threshold_hours=6.0)
            if is_idle:
                metrics["potential_idle_sessions"] += 1
                score -= 5

            # Check for very short sessions (less than 1 minute)
            duration = session.end_time - session.start_time
            if duration < timedelta(minutes=1):
                metrics["very_short_sessions"] += 1
                score -= 2

            # Check for very long sessions (more than 12 hours)
            if duration > timedelta(hours=12):
                metrics["very_long_sessions"] += 1
                score -= 10

            # Check for unusual start times
            hour = session.start_time.hour
            if hour < 5 or hour > 23:
                metrics["unusual_time_sessions"] += 1
                score -= 1

        # Check for overlapping sessions
        overlaps = self.find_overlapping_sessions(completed_sessions)
        metrics["overlapping_sessions"] = len(overlaps)
        score -= len(overlaps) * 15  # Overlaps are serious issues

        # Ensure score doesn't go below 0
        score = max(0.0, score)

        return score, metrics