"""
Tests for formatting utilities (trackit.utils.formatting).

This module tests time formatting, display utilities, and other formatting functions.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from trackit.utils.formatting import (
    format_bytes,
    format_date,
    format_datetime,
    format_duration,
    format_percentage,
    format_relative_time,
    format_time,
    pluralize,
    truncate_text,
)


class TestFormatDuration:
    """Test cases for format_duration function."""

    def test_format_duration_hours_minutes_seconds(self) -> None:
        """Test formatting duration with hours, minutes, and seconds."""
        # Arrange
        duration = timedelta(hours=2, minutes=30, seconds=45)

        # Act
        result = format_duration(duration, show_seconds=True)

        # Assert
        assert result == "2h 30m 45s"

    def test_format_duration_hours_minutes_no_seconds(self) -> None:
        """Test formatting duration without seconds."""
        # Arrange
        duration = timedelta(hours=1, minutes=45, seconds=30)

        # Act
        result = format_duration(duration, show_seconds=False)

        # Assert
        assert result == "1h 45m"

    def test_format_duration_minutes_seconds(self) -> None:
        """Test formatting duration with minutes and seconds only."""
        # Arrange
        duration = timedelta(minutes=25, seconds=15)

        # Act
        result = format_duration(duration, show_seconds=True)

        # Assert
        assert result == "25m 15s"

    def test_format_duration_seconds_only(self) -> None:
        """Test formatting duration with seconds only."""
        # Arrange
        duration = timedelta(seconds=42)

        # Act
        result = format_duration(duration, show_seconds=True)

        # Assert
        assert result == "42s"

    def test_format_duration_zero_duration(self) -> None:
        """Test formatting zero duration."""
        # Arrange
        duration = timedelta(0)

        # Act
        result = format_duration(duration, show_seconds=True)

        # Assert
        assert result == "0s"

    def test_format_duration_zero_no_seconds(self) -> None:
        """Test formatting zero duration without seconds."""
        # Arrange
        duration = timedelta(0)

        # Act
        result = format_duration(duration, show_seconds=False)

        # Assert
        assert result == "0s"  # Should still show something

    def test_format_duration_negative_duration(self) -> None:
        """Test formatting negative duration."""
        # Arrange
        duration = timedelta(seconds=-30)

        # Act
        result = format_duration(duration)

        # Assert
        assert result == "0s"  # Should handle negative as zero

    def test_format_duration_exact_hours(self) -> None:
        """Test formatting exact hours."""
        # Arrange
        duration = timedelta(hours=3)

        # Act
        result = format_duration(duration, show_seconds=True)

        # Assert
        assert result == "3h"

    def test_format_duration_exact_minutes(self) -> None:
        """Test formatting exact minutes."""
        # Arrange
        duration = timedelta(minutes=30)

        # Act
        result = format_duration(duration, show_seconds=True)

        # Assert
        assert result == "30m"

    def test_format_duration_hours_seconds_no_minutes(self) -> None:
        """Test formatting duration with hours and seconds but no minutes."""
        # Arrange
        duration = timedelta(hours=1, seconds=30)

        # Act
        result = format_duration(duration, show_seconds=True)

        # Assert
        assert result == "1h 0m 30s"  # Should include minutes for clarity

    @patch("trackit.utils.formatting.get_config_manager")
    def test_format_duration_uses_config_default(self, mock_get_config: Mock) -> None:
        """Test that format_duration uses config default for show_seconds."""
        # Arrange
        mock_config = Mock()
        mock_config.show_seconds.return_value = False
        mock_get_config.return_value = mock_config

        duration = timedelta(hours=1, minutes=30, seconds=45)

        # Act
        result = format_duration(duration)  # No show_seconds parameter

        # Assert
        assert result == "1h 30m"
        mock_config.show_seconds.assert_called_once()

    def test_format_duration_large_values(self) -> None:
        """Test formatting very large durations."""
        # Arrange
        duration = timedelta(hours=25, minutes=70, seconds=120)  # 26h 12m

        # Act
        result = format_duration(duration, show_seconds=True)

        # Assert
        assert result == "26h 12m"  # Should normalize minutes and seconds


class TestFormatDatetime:
    """Test cases for format_datetime function."""

    def test_format_datetime_with_date_and_time(self) -> None:
        """Test formatting datetime with both date and time."""
        # Arrange
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        with patch("trackit.utils.formatting.get_config_manager") as mock_get_config:
            mock_config = Mock()
            mock_config.get_date_format.return_value = "%Y-%m-%d"
            mock_config.get_time_format.return_value = "%H:%M:%S"
            mock_config.show_seconds.return_value = True
            mock_get_config.return_value = mock_config

            # Act
            result = format_datetime(dt, include_date=True, include_time=True)

            # Assert
            # Result will be in local time, so we check the general format
            assert (
                "2024-01-15" in result or "2024-01-14" in result
            )  # Depending on timezone
            assert ":" in result  # Should contain time

    def test_format_datetime_date_only(self) -> None:
        """Test formatting datetime with date only."""
        # Arrange
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        with patch("trackit.utils.formatting.get_config_manager") as mock_get_config:
            mock_config = Mock()
            mock_config.get_date_format.return_value = "%Y-%m-%d"
            mock_get_config.return_value = mock_config

            # Act
            result = format_datetime(dt, include_date=True, include_time=False)

            # Assert
            assert (
                "2024-01-15" in result or "2024-01-14" in result
            )  # Depending on timezone
            assert ":" not in result  # Should not contain time

    def test_format_datetime_time_only(self) -> None:
        """Test formatting datetime with time only."""
        # Arrange
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        with patch("trackit.utils.formatting.get_config_manager") as mock_get_config:
            mock_config = Mock()
            mock_config.get_time_format.return_value = "%H:%M:%S"
            mock_config.show_seconds.return_value = True
            mock_get_config.return_value = mock_config

            # Act
            result = format_datetime(dt, include_date=False, include_time=True)

            # Assert
            assert ":" in result  # Should contain time
            assert "2024" not in result  # Should not contain date

    def test_format_datetime_without_seconds(self) -> None:
        """Test formatting datetime without seconds."""
        # Arrange
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        with patch("trackit.utils.formatting.get_config_manager") as mock_get_config:
            mock_config = Mock()
            mock_config.get_time_format.return_value = "%H:%M:%S"
            mock_config.show_seconds.return_value = False
            mock_get_config.return_value = mock_config

            # Act
            result = format_datetime(dt, include_date=False, include_time=True)

            # Assert
            assert ":" in result
            assert result.count(":") == 1  # Only hours:minutes, no seconds

    def test_format_datetime_naive_datetime(self) -> None:
        """Test formatting naive datetime (assumes UTC)."""
        # Arrange
        dt = datetime(2024, 1, 15, 14, 30, 45)  # No timezone

        with patch("trackit.utils.formatting.get_config_manager") as mock_get_config:
            mock_config = Mock()
            mock_config.get_date_format.return_value = "%Y-%m-%d"
            mock_config.get_time_format.return_value = "%H:%M:%S"
            mock_config.show_seconds.return_value = True
            mock_get_config.return_value = mock_config

            # Act
            result = format_datetime(dt)

            # Assert - should not raise exception
            assert isinstance(result, str)
            assert len(result) > 0

    def test_format_datetime_custom_formats(self) -> None:
        """Test formatting with custom date and time formats."""
        # Arrange
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        with patch("trackit.utils.formatting.get_config_manager") as mock_get_config:
            mock_config = Mock()
            mock_config.get_date_format.return_value = "%d/%m/%Y"
            mock_config.get_time_format.return_value = "%I:%M %p"
            mock_config.show_seconds.return_value = True
            mock_get_config.return_value = mock_config

            # Act
            result = format_datetime(dt, include_date=True, include_time=True)

            # Assert
            # Should use custom formats (converted to local time)
            assert "/" in result  # Custom date format
            # Time format will depend on local timezone


class TestFormatDateAndTime:
    """Test cases for format_date and format_time functions."""

    def test_format_date(self) -> None:
        """Test format_date function."""
        # Arrange
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        with patch("trackit.utils.formatting.get_config_manager") as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.get_date_format.return_value = "%Y-%m-%d"
            mock_config_instance.get_time_format.return_value = "%H:%M:%S"
            mock_config.return_value = mock_config_instance

            # Act
            result = format_date(dt)

            # Assert - should only contain date
            assert "2024" in result
            assert ":" not in result

    def test_format_time(self) -> None:
        """Test format_time function."""
        # Arrange
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        with patch("trackit.utils.formatting.get_config_manager") as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.get_date_format.return_value = "%Y-%m-%d"
            mock_config_instance.get_time_format.return_value = "%H:%M:%S"
            mock_config.return_value = mock_config_instance

            # Act
            result = format_time(dt)

            # Assert - should only contain time
            assert ":" in result
            assert "2024" not in result


class TestTruncateText:
    """Test cases for truncate_text function."""

    def test_truncate_text_within_limit(self) -> None:
        """Test truncating text within the limit."""
        # Arrange
        text = "Short text"

        # Act
        result = truncate_text(text, max_length=20)

        # Assert
        assert result == "Short text"

    def test_truncate_text_exceeds_limit(self) -> None:
        """Test truncating text that exceeds the limit."""
        # Arrange
        text = "This is a very long text that exceeds the maximum length"

        # Act
        result = truncate_text(text, max_length=20)

        # Assert
        assert len(result) == 20
        assert result.endswith("...")
        assert result == "This is a very lo..."

    def test_truncate_text_exact_limit(self) -> None:
        """Test truncating text that is exactly at the limit."""
        # Arrange
        text = "Exactly twenty chars"  # 20 characters

        # Act
        result = truncate_text(text, max_length=20)

        # Assert
        assert result == "Exactly twenty chars"

    def test_truncate_text_very_short_limit(self) -> None:
        """Test truncating with very short limit."""
        # Arrange
        text = "Long text"

        # Act
        result = truncate_text(text, max_length=5)

        # Assert
        assert len(result) == 5
        assert result == "Lo..."

    def test_truncate_text_limit_less_than_ellipsis(self) -> None:
        """Test truncating with limit less than ellipsis length."""
        # Arrange
        text = "Text"

        # Act
        result = truncate_text(text, max_length=2)

        # Assert
        assert len(result) == 2
        assert result == "..."[:2]

    @patch("trackit.utils.formatting.get_config_manager")
    def test_truncate_text_uses_config_default(self, mock_get_config: Mock) -> None:
        """Test that truncate_text uses config default for max_length."""
        # Arrange
        mock_config = Mock()
        mock_config.get_max_task_name_length.return_value = 15
        mock_get_config.return_value = mock_config

        text = "This is a long text that should be truncated"

        # Act
        result = truncate_text(text)  # No max_length parameter

        # Assert
        assert len(result) == 15
        assert result.endswith("...")
        mock_config.get_max_task_name_length.assert_called_once()


class TestFormatBytes:
    """Test cases for format_bytes function."""

    def test_format_bytes_bytes(self) -> None:
        """Test formatting bytes."""
        # Act & Assert
        assert format_bytes(0) == "0 B"
        assert format_bytes(1) == "1 B"
        assert format_bytes(512) == "512 B"
        assert format_bytes(1023) == "1023 B"

    def test_format_bytes_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        # Act & Assert
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(2048) == "2.0 KB"

    def test_format_bytes_megabytes(self) -> None:
        """Test formatting megabytes."""
        # Act & Assert
        assert format_bytes(1024 * 1024) == "1.0 MB"
        assert format_bytes(1024 * 1024 * 1) == "1.0 MB"
        assert format_bytes(1024 * 1024 * 10) == "10.0 MB"

    def test_format_bytes_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        # Act & Assert
        assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"
        assert format_bytes(1024 * 1024 * 1024 * 2) == "2.0 GB"

    def test_format_bytes_terabytes(self) -> None:
        """Test formatting terabytes."""
        # Act & Assert
        assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.0 TB"
        assert format_bytes(1024 * 1024 * 1024 * 1024 * 5) == "5.0 TB"

    def test_format_bytes_large_values(self) -> None:
        """Test formatting very large byte values."""
        # Arrange
        very_large = 1024**4 * 1000  # 1000 TB

        # Act
        result = format_bytes(very_large)

        # Assert
        assert "TB" in result
        assert result == "1000.0 TB"


class TestFormatPercentage:
    """Test cases for format_percentage function."""

    def test_format_percentage_normal_values(self) -> None:
        """Test formatting normal percentage values."""
        # Act & Assert
        assert format_percentage(25, 100) == "25.0%"
        assert format_percentage(50, 100) == "50.0%"
        assert format_percentage(75, 100) == "75.0%"
        assert format_percentage(100, 100) == "100.0%"

    def test_format_percentage_zero_value(self) -> None:
        """Test formatting zero percentage."""
        # Act & Assert
        assert format_percentage(0, 100) == "0.0%"

    def test_format_percentage_zero_total(self) -> None:
        """Test formatting percentage with zero total."""
        # Act & Assert
        assert format_percentage(50, 0) == "0.0%"

    def test_format_percentage_decimal_values(self) -> None:
        """Test formatting decimal percentage values."""
        # Act & Assert
        assert format_percentage(33.333, 100) == "33.3%"
        assert format_percentage(66.666, 100) == "66.7%"

    def test_format_percentage_greater_than_total(self) -> None:
        """Test formatting percentage greater than 100%."""
        # Act & Assert
        assert format_percentage(150, 100) == "150.0%"

    def test_format_percentage_fractional_total(self) -> None:
        """Test formatting percentage with fractional total."""
        # Act & Assert
        assert format_percentage(1, 3) == "33.3%"
        assert format_percentage(2, 3) == "66.7%"


class TestPluralize:
    """Test cases for pluralize function."""

    def test_pluralize_singular(self) -> None:
        """Test pluralization with singular count."""
        # Act & Assert
        assert pluralize(1, "item") == "item"
        assert pluralize(1, "task") == "task"
        assert pluralize(1, "entry") == "entry"

    def test_pluralize_plural(self) -> None:
        """Test pluralization with plural count."""
        # Act & Assert
        assert pluralize(0, "item") == "items"
        assert pluralize(2, "task") == "tasks"
        assert pluralize(10, "entry", "entries") == "entries"

    def test_pluralize_custom_plural(self) -> None:
        """Test pluralization with custom plural form."""
        # Act & Assert
        assert pluralize(1, "child", "children") == "child"
        assert pluralize(2, "child", "children") == "children"
        assert pluralize(0, "person", "people") == "people"
        assert pluralize(1, "person", "people") == "person"

    def test_pluralize_irregular_words(self) -> None:
        """Test pluralization with irregular words."""
        # Act & Assert
        assert pluralize(1, "mouse", "mice") == "mouse"
        assert pluralize(3, "mouse", "mice") == "mice"
        assert pluralize(1, "foot", "feet") == "foot"
        assert pluralize(2, "foot", "feet") == "feet"

    def test_pluralize_negative_count(self) -> None:
        """Test pluralization with negative count."""
        # Act & Assert
        assert pluralize(-1, "item") == "item"  # Singular for -1
        assert pluralize(-2, "item") == "items"  # Plural for other negative


class TestFormatRelativeTime:
    """Test cases for format_relative_time function."""

    def test_format_relative_time_just_now(self) -> None:
        """Test formatting time that's very recent."""
        # Arrange
        now = datetime.now(timezone.utc)
        recent = now - timedelta(seconds=30)

        # Act
        result = format_relative_time(recent)

        # Assert
        assert result == "just now"

    def test_format_relative_time_minutes_ago(self) -> None:
        """Test formatting time in minutes ago."""
        # Arrange
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=5)

        # Act
        result = format_relative_time(past)

        # Assert
        assert result == "5 minutes ago"

    def test_format_relative_time_one_minute_ago(self) -> None:
        """Test formatting one minute ago (singular)."""
        # Arrange
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=1)

        # Act
        result = format_relative_time(past)

        # Assert
        assert result == "1 minute ago"

    def test_format_relative_time_hours_ago(self) -> None:
        """Test formatting time in hours ago."""
        # Arrange
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=3)

        # Act
        result = format_relative_time(past)

        # Assert
        assert result == "3 hours ago"

    def test_format_relative_time_one_hour_ago(self) -> None:
        """Test formatting one hour ago (singular)."""
        # Arrange
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)

        # Act
        result = format_relative_time(past)

        # Assert
        assert result == "1 hour ago"

    def test_format_relative_time_days_ago(self) -> None:
        """Test formatting time in days ago."""
        # Arrange
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=2)

        # Act
        result = format_relative_time(past)

        # Assert
        assert result == "2 days ago"

    def test_format_relative_time_one_day_ago(self) -> None:
        """Test formatting one day ago (singular)."""
        # Arrange
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=1)

        # Act
        result = format_relative_time(past)

        # Assert
        assert result == "1 day ago"

    @patch("trackit.utils.formatting.datetime")
    def test_format_relative_time_future_minutes(self, mock_datetime: Mock) -> None:
        """Test formatting future time in minutes."""
        # Arrange
        fixed_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_now
        future = fixed_now + timedelta(minutes=10)

        # Act
        result = format_relative_time(future)

        # Assert
        assert result == "in 10 minutes"

    @patch("trackit.utils.formatting.datetime")
    def test_format_relative_time_future_hours(self, mock_datetime: Mock) -> None:
        """Test formatting future time in hours."""
        # Arrange
        fixed_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_now
        future = fixed_now + timedelta(hours=2)

        # Act
        result = format_relative_time(future)

        # Assert
        assert result == "in 2 hours"

    @patch("trackit.utils.formatting.datetime")
    def test_format_relative_time_future_days(self, mock_datetime: Mock) -> None:
        """Test formatting future time in days."""
        # Arrange
        fixed_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_now
        future = fixed_now + timedelta(days=5)

        # Act
        result = format_relative_time(future)

        # Assert
        assert result == "in 5 days"

    def test_format_relative_time_naive_datetime(self) -> None:
        """Test formatting relative time with naive datetime."""
        # Arrange
        now = datetime.now()  # Naive datetime
        past = now - timedelta(minutes=15)

        # Act
        result = format_relative_time(past)

        # Assert - should not raise exception
        assert isinstance(result, str)
        assert "ago" in result or "in" in result or "just now" == result


@pytest.mark.unit
class TestFormattingEdgeCases:
    """Test edge cases and error conditions for formatting functions."""

    def test_format_duration_microseconds(self) -> None:
        """Test formatting duration with microseconds."""
        # Arrange
        duration = timedelta(microseconds=500000)  # 0.5 seconds

        # Act
        result = format_duration(duration, show_seconds=True)

        # Assert
        assert result == "0s"  # Should round down

    def test_format_datetime_empty_string_formats(self) -> None:
        """Test datetime formatting with empty format strings."""
        # Arrange
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        with patch("trackit.utils.formatting.get_config_manager") as mock_get_config:
            mock_config = Mock()
            mock_config.get_date_format.return_value = ""
            mock_config.get_time_format.return_value = ""
            mock_config.show_seconds.return_value = True
            mock_get_config.return_value = mock_config

            # Act
            result = format_datetime(dt)

            # Assert - should handle gracefully
            assert isinstance(result, str)

    def test_truncate_text_empty_string(self) -> None:
        """Test truncating empty string."""
        # Act & Assert
        assert truncate_text("", max_length=10) == ""
        assert truncate_text("", max_length=0) == ""

    def test_format_bytes_negative_values(self) -> None:
        """Test formatting negative byte values."""
        # Act - should handle gracefully (though not typical use case)
        result = format_bytes(-1024)

        # Assert
        assert isinstance(result, str)
        # Implementation may vary for negative values

    def test_format_percentage_negative_values(self) -> None:
        """Test formatting negative percentage values."""
        # Act & Assert
        assert format_percentage(-25, 100) == "-25.0%"
        assert format_percentage(25, -100) == "-25.0%"

    def test_pluralize_float_count(self) -> None:
        """Test pluralization with float count."""
        # Act & Assert
        assert pluralize(1.0, "item") == "item"
        assert pluralize(1.5, "item") == "items"  # Non-integer is plural
        assert pluralize(0.0, "item") == "items"


@pytest.mark.integration
class TestFormattingIntegration:
    """Integration tests for formatting functions."""

    def test_duration_and_relative_time_consistency(self) -> None:
        """Test consistency between duration and relative time formatting."""
        # Arrange
        base_time = datetime.now(timezone.utc)
        past_time = base_time - timedelta(hours=2, minutes=30)
        duration = base_time - past_time

        # Act
        duration_str = format_duration(duration)
        relative_str = format_relative_time(past_time)

        # Assert - both should indicate roughly 2.5 hours
        assert "2h" in duration_str
        assert "30m" in duration_str
        assert "hours" in relative_str or "hour" in relative_str

    def test_datetime_formatting_with_config_integration(self) -> None:
        """Test datetime formatting integrates properly with config."""
        # Arrange
        dt = datetime(2024, 6, 15, 14, 30, 45, tzinfo=timezone.utc)

        # Test with different config settings
        with patch("trackit.utils.formatting.get_config_manager") as mock_get_config:
            mock_config = Mock()
            mock_config.get_date_format.return_value = "%d/%m/%Y"
            mock_config.get_time_format.return_value = "%I:%M %p"
            mock_config.show_seconds.return_value = False
            mock_get_config.return_value = mock_config

            # Act
            date_result = format_date(dt)
            time_result = format_time(dt)
            datetime_result = format_datetime(dt)

            # Assert
            assert "/" in date_result  # Uses custom date format
            # Time format depends on local timezone conversion
            assert isinstance(time_result, str)
            assert isinstance(datetime_result, str)

    def test_text_truncation_with_config_integration(self) -> None:
        """Test text truncation integrates with config settings."""
        # Arrange
        long_text = "This is a very long task name that exceeds normal limits"

        with patch("trackit.utils.formatting.get_config_manager") as mock_get_config:
            mock_config = Mock()
            mock_config.get_max_task_name_length.return_value = 25
            mock_get_config.return_value = mock_config

            # Act
            result = truncate_text(long_text)

            # Assert
            assert len(result) == 25
            assert result.endswith("...")
            mock_config.get_max_task_name_length.assert_called_once()

    def test_comprehensive_formatting_workflow(self) -> None:
        """Test a comprehensive formatting workflow."""
        # Arrange
        start_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 11, 30, 45, tzinfo=timezone.utc)
        duration = end_time - start_time
        task_name = "Very Long Task Name That Should Be Truncated For Display"
        file_size = 1024 * 1024 * 2.0  # 2.0 MB

        with patch("trackit.utils.formatting.get_config_manager") as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.get_date_format.return_value = "%Y-%m-%d"
            mock_config_instance.get_time_format.return_value = "%H:%M:%S"
            mock_config.return_value = mock_config_instance

            with patch("trackit.utils.formatting.datetime") as mock_datetime:
                mock_datetime.now.return_value = datetime(
                    2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc
                )
                mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

                # Act
                formatted_start = format_datetime(start_time)
                formatted_end = format_datetime(end_time)
                formatted_duration = format_duration(duration)
                formatted_task = truncate_text(task_name, max_length=30)
                formatted_size = format_bytes(int(file_size))
                formatted_relative = format_relative_time(start_time)

                # Assert - all should return properly formatted strings
                assert isinstance(formatted_start, str)
                assert isinstance(formatted_end, str)
                assert "2h" in formatted_duration and "30m" in formatted_duration
                assert formatted_task.endswith("...")
                assert len(formatted_task) == 30
                assert "2.0 MB" == formatted_size
                assert isinstance(formatted_relative, str)
