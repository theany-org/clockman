"""
Tests for configuration management (trackit.utils.config).

This module tests configuration loading, validation, and management functionality.
"""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from trackit.utils.config import ConfigManager, get_config_manager


class TestConfigManager:
    """Test cases for ConfigManager class."""

    def test_init_creates_directories(self) -> None:
        """Test that ConfigManager creates config and data directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("trackit.utils.config.user_config_dir") as mock_config_dir,
                patch("trackit.utils.config.user_data_dir") as mock_data_dir,
            ):

                mock_config_dir.return_value = str(Path(temp_dir) / "config")
                mock_data_dir.return_value = str(Path(temp_dir) / "data")

                # Act
                config_manager = ConfigManager()

                # Assert
                assert config_manager.config_dir.exists()
                assert config_manager.data_dir.exists()
                assert (
                    config_manager.config_file
                    == config_manager.config_dir / "config.json"
                )

    def test_init_loads_default_config_on_fresh_install(self) -> None:
        """Test default configuration is created on fresh install."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("trackit.utils.config.user_config_dir") as mock_config_dir,
                patch("trackit.utils.config.user_data_dir") as mock_data_dir,
            ):

                mock_config_dir.return_value = str(Path(temp_dir) / "config")
                mock_data_dir.return_value = str(Path(temp_dir) / "data")

                # Act
                config_manager = ConfigManager()

                # Assert
                assert config_manager.config_file.exists()
                assert config_manager.get("date_format") == "%Y-%m-%d"
                assert config_manager.get("time_format") == "%H:%M:%S"
                assert config_manager.get("timezone") == "local"

    def test_init_loads_existing_config(self) -> None:
        """Test loading existing configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            data_dir = Path(temp_dir) / "data"
            config_dir.mkdir(parents=True)
            data_dir.mkdir(parents=True)

            # Create existing config file
            config_file = config_dir / "config.json"
            existing_config = {
                "date_format": "%d/%m/%Y",
                "time_format": "%I:%M %p",
                "custom_setting": "custom_value",
            }
            with open(config_file, "w") as f:
                json.dump(existing_config, f)

            with (
                patch("trackit.utils.config.user_config_dir") as mock_config_dir,
                patch("trackit.utils.config.user_data_dir") as mock_data_dir,
            ):

                mock_config_dir.return_value = str(config_dir)
                mock_data_dir.return_value = str(data_dir)

                # Act
                config_manager = ConfigManager()

                # Assert
                assert config_manager.get("date_format") == "%d/%m/%Y"
                assert config_manager.get("time_format") == "%I:%M %p"
                assert config_manager.get("custom_setting") == "custom_value"
                # Should still have defaults for missing keys
                assert config_manager.get("timezone") == "local"

    def test_init_handles_corrupt_config_file(self) -> None:
        """Test handling of corrupt configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            data_dir = Path(temp_dir) / "data"
            config_dir.mkdir(parents=True)
            data_dir.mkdir(parents=True)

            # Create corrupt config file
            config_file = config_dir / "config.json"
            with open(config_file, "w") as f:
                f.write("invalid json content {")

            with (
                patch("trackit.utils.config.user_config_dir") as mock_config_dir,
                patch("trackit.utils.config.user_data_dir") as mock_data_dir,
            ):

                mock_config_dir.return_value = str(config_dir)
                mock_data_dir.return_value = str(data_dir)

                # Act
                config_manager = ConfigManager()

                # Assert - should fall back to defaults
                assert config_manager.get("date_format") == "%Y-%m-%d"
                assert config_manager.get("time_format") == "%H:%M:%S"

    def test_get_simple_key(self) -> None:
        """Test getting simple configuration value."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.get("date_format") == "%Y-%m-%d"
        assert config_manager.get("timezone") == "local"

    def test_get_nested_key(self) -> None:
        """Test getting nested configuration value."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.get("colors.active") == "green"
        assert config_manager.get("display.show_seconds") is True
        assert config_manager.get("display.compact_mode") is False

    def test_get_with_default(self) -> None:
        """Test getting value with default fallback."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.get("nonexistent_key", "default_value") == "default_value"
        assert config_manager.get("colors.nonexistent", "blue") == "blue"

    def test_get_nonexistent_key_no_default(self) -> None:
        """Test getting non-existent key without default."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.get("nonexistent_key") is None
        assert config_manager.get("colors.nonexistent") is None

    def test_set_simple_key(self) -> None:
        """Test setting simple configuration value."""
        config_manager = ConfigManager()

        # Act
        config_manager.set("date_format", "%d-%m-%Y")

        # Assert
        assert config_manager.get("date_format") == "%d-%m-%Y"

    def test_set_nested_key(self) -> None:
        """Test setting nested configuration value."""
        config_manager = ConfigManager()

        # Act
        config_manager.set("colors.active", "blue")
        config_manager.set("display.max_lines", 25)

        # Assert
        assert config_manager.get("colors.active") == "blue"
        assert config_manager.get("display.max_lines") == 25

    def test_set_creates_nested_structure(self) -> None:
        """Test setting value creates nested structure if needed."""
        config_manager = ConfigManager()

        # Act
        config_manager.set("new_section.new_key", "new_value")

        # Assert
        assert config_manager.get("new_section.new_key") == "new_value"

    @patch("trackit.utils.config.ConfigManager._save_config")
    def test_set_saves_config(self, mock_save) -> None:
        """Test that set method saves configuration."""
        config_manager = ConfigManager()

        # Act
        config_manager.set("test_key", "test_value")

        # Assert
        mock_save.assert_called_once()

    def test_get_data_dir(self) -> None:
        """Test getting data directory."""
        config_manager = ConfigManager()

        # Act
        data_dir = config_manager.get_data_dir()

        # Assert
        assert isinstance(data_dir, Path)
        assert data_dir.exists()

    def test_get_data_dir_custom_path(self) -> None:
        """Test getting custom data directory from config."""
        config_manager = ConfigManager()
        custom_path = "/tmp/custom_trackit_data"

        # Act
        config_manager.set("data_directory", custom_path)
        data_dir = config_manager.get_data_dir()

        # Assert
        assert data_dir == Path(custom_path)

    def test_get_config_dir(self) -> None:
        """Test getting configuration directory."""
        config_manager = ConfigManager()

        # Act
        config_dir = config_manager.get_config_dir()

        # Assert
        assert isinstance(config_dir, Path)
        assert config_dir.exists()
        assert config_dir == config_manager.config_dir

    def test_get_date_format(self) -> None:
        """Test getting date format."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.get_date_format() == "%Y-%m-%d"

        # Test custom format
        config_manager.set("date_format", "%d/%m/%Y")
        assert config_manager.get_date_format() == "%d/%m/%Y"

    def test_get_time_format(self) -> None:
        """Test getting time format."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.get_time_format() == "%H:%M:%S"

        # Test custom format
        config_manager.set("time_format", "%I:%M %p")
        assert config_manager.get_time_format() == "%I:%M %p"

    def test_get_color(self) -> None:
        """Test getting UI element colors."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.get_color("active") == "green"
        assert config_manager.get_color("inactive") == "dim"
        assert config_manager.get_color("nonexistent") == "white"  # Default

    def test_is_compact_mode(self) -> None:
        """Test checking compact mode setting."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.is_compact_mode() is False

        # Test setting compact mode
        config_manager.set("display.compact_mode", True)
        assert config_manager.is_compact_mode() is True

    def test_show_seconds(self) -> None:
        """Test checking show seconds setting."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.show_seconds() is True

        # Test disabling seconds
        config_manager.set("display.show_seconds", False)
        assert config_manager.show_seconds() is False

    def test_get_max_task_name_length(self) -> None:
        """Test getting maximum task name length."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.get_max_task_name_length() == 50

        # Test custom length
        config_manager.set("display.max_task_name_length", 100)
        assert config_manager.get_max_task_name_length() == 100

    def test_get_default_tags(self):
        """Test getting default tags."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.get_default_tags() == []

        # Test custom tags
        config_manager.set("default_tags", ["work", "project"])
        assert config_manager.get_default_tags() == ["work", "project"]

    def test_is_auto_stop_enabled(self) -> None:
        """Test checking auto-stop setting."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.is_auto_stop_enabled() is False

        # Test enabling auto-stop
        config_manager.set("auto_stop_inactive", True)
        assert config_manager.is_auto_stop_enabled() is True

    def test_get_inactive_timeout(self) -> None:
        """Test getting inactive timeout."""
        config_manager = ConfigManager()

        # Act & Assert
        assert config_manager.get_inactive_timeout() == 30

        # Test custom timeout
        config_manager.set("inactive_timeout_minutes", 60)
        assert config_manager.get_inactive_timeout() == 60

    def test_reset_to_defaults(self) -> None:
        """Test resetting configuration to defaults."""
        config_manager = ConfigManager()

        # Modify some settings
        config_manager.set("date_format", "%d/%m/%Y")
        config_manager.set("colors.active", "blue")
        config_manager.set("custom_setting", "custom_value")

        # Verify changes
        assert config_manager.get("date_format") == "%d/%m/%Y"
        assert config_manager.get("colors.active") == "blue"
        assert config_manager.get("custom_setting") == "custom_value"

        # Act
        config_manager.reset_to_defaults()

        # Assert
        assert config_manager.get("date_format") == "%Y-%m-%d"
        assert config_manager.get("colors.active") == "green"
        assert config_manager.get("custom_setting") is None

    def test_export_config(self) -> None:
        """Test exporting configuration to file."""
        config_manager = ConfigManager()

        # Modify some settings
        config_manager.set("date_format", "%d/%m/%Y")
        config_manager.set("custom_setting", "exported_value")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            export_path = Path(f.name)

        try:
            # Act
            config_manager.export_config(export_path)

            # Assert
            assert export_path.exists()
            with open(export_path, "r") as f:
                exported_config = json.load(f)

            assert exported_config["date_format"] == "%d/%m/%Y"
            assert exported_config["custom_setting"] == "exported_value"

        finally:
            export_path.unlink()

    def test_import_config(self) -> None:
        """Test importing configuration from file."""
        config_manager = ConfigManager()

        # Create import file
        import_config: dict[str, Any] = {
            "date_format": "%m/%d/%Y",
            "time_format": "%I:%M %p",
            "colors": {"active": "purple"},
            "imported_setting": "imported_value",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(import_config, f)
            import_path = Path(f.name)

        try:
            # Act
            config_manager.import_config(import_path)

            # Assert
            assert config_manager.get("date_format") == "%m/%d/%Y"
            assert config_manager.get("time_format") == "%I:%M %p"
            assert config_manager.get("colors.active") == "purple"
            assert config_manager.get("imported_setting") == "imported_value"
            # Should retain other defaults
            assert config_manager.get("timezone") == "local"

        finally:
            import_path.unlink()

    def test_save_config_io_error_handling(self) -> None:
        """Test handling IO errors when saving config."""
        config_manager = ConfigManager()

        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with patch("builtins.print") as mock_print:
                # Act - should not raise exception
                config_manager.set("test_key", "test_value")

                # Assert - should print warning
                mock_print.assert_called()
                args = mock_print.call_args[0]
                assert "Could not save config file" in args[0]

    def test_load_config_io_error_handling(self) -> None:
        """Test handling IO errors when loading config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            data_dir = Path(temp_dir) / "data"
            config_dir.mkdir(parents=True)
            data_dir.mkdir(parents=True)

            # Create config file with restrictive permissions
            config_file = config_dir / "config.json"
            with open(config_file, "w") as f:
                json.dump({"test": "value"}, f)

            with (
                patch("trackit.utils.config.user_config_dir") as mock_config_dir,
                patch("trackit.utils.config.user_data_dir") as mock_data_dir,
                patch("builtins.open", side_effect=IOError("Permission denied")),
                patch("builtins.print") as mock_print,
            ):

                mock_config_dir.return_value = str(config_dir)
                mock_data_dir.return_value = str(data_dir)

                # Act
                config_manager = ConfigManager()

                # Assert - should fall back to defaults and print warning
                mock_print.assert_called()
                assert config_manager.get("date_format") == "%Y-%m-%d"

    def test_default_config_structure(self) -> None:
        """Test default configuration has expected structure."""
        config_manager = ConfigManager()

        # Act & Assert - check all expected keys exist
        assert config_manager.get("data_directory") is not None
        assert config_manager.get("date_format") == "%Y-%m-%d"
        assert config_manager.get("time_format") == "%H:%M:%S"
        assert config_manager.get("timezone") == "local"
        assert config_manager.get("default_tags") == []
        assert config_manager.get("auto_stop_inactive") is False
        assert config_manager.get("inactive_timeout_minutes") == 30

        # Check colors section
        assert config_manager.get("colors.active") == "green"
        assert config_manager.get("colors.inactive") == "dim"
        assert config_manager.get("colors.duration") == "cyan"
        assert config_manager.get("colors.task_name") == "bold"
        assert config_manager.get("colors.tags") == "yellow"

        # Check display section
        assert config_manager.get("display.show_seconds") is True
        assert config_manager.get("display.compact_mode") is False
        assert config_manager.get("display.max_task_name_length") == 50


class TestGlobalConfigManager:
    """Test cases for global configuration manager."""

    def test_get_config_manager_singleton(self) -> None:
        """Test that get_config_manager returns singleton instance."""
        # Reset global instance
        import trackit.utils.config

        trackit.utils.config._config_manager = None

        # Act
        config1 = get_config_manager()
        config2 = get_config_manager()

        # Assert
        assert config1 is config2
        assert isinstance(config1, ConfigManager)

    def test_get_config_manager_initializes_once(self) -> None:
        """Test that get_config_manager initializes only once."""
        # Reset global instance
        import trackit.utils.config

        trackit.utils.config._config_manager = None

        with patch("trackit.utils.config.ConfigManager") as mock_config_class:
            mock_instance = Mock()
            mock_config_class.return_value = mock_instance

            # Act
            config1 = get_config_manager()
            config2 = get_config_manager()

            # Assert
            assert config1 is mock_instance
            assert config2 is mock_instance
            mock_config_class.assert_called_once()


@pytest.mark.integration
class TestConfigManagerIntegration:
    """Integration tests for ConfigManager."""

    def test_full_config_workflow(self) -> None:
        """Test complete configuration workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("trackit.utils.config.user_config_dir") as mock_config_dir,
                patch("trackit.utils.config.user_data_dir") as mock_data_dir,
            ):

                mock_config_dir.return_value = str(Path(temp_dir) / "config")
                mock_data_dir.return_value = str(Path(temp_dir) / "data")

                # Initialize
                config_manager = ConfigManager()

                # Verify defaults
                assert config_manager.get("date_format") == "%Y-%m-%d"
                assert config_manager.get("colors.active") == "green"

                # Modify settings
                config_manager.set("date_format", "%d/%m/%Y")
                config_manager.set("colors.active", "blue")
                config_manager.set("display.max_task_name_length", 75)

                # Verify changes
                assert config_manager.get("date_format") == "%d/%m/%Y"
                assert config_manager.get("colors.active") == "blue"
                assert config_manager.get("display.max_task_name_length") == 75

                # Create new instance (should load from file)
                config_manager2 = ConfigManager()

                # Verify persistence
                assert config_manager2.get("date_format") == "%d/%m/%Y"
                assert config_manager2.get("colors.active") == "blue"
                assert config_manager2.get("display.max_task_name_length") == 75

    def test_config_persistence_across_instances(self) -> None:
        """Test configuration persists across different instances."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            data_dir = Path(temp_dir) / "data"

            with (
                patch("trackit.utils.config.user_config_dir") as mock_config_dir,
                patch("trackit.utils.config.user_data_dir") as mock_data_dir,
            ):

                mock_config_dir.return_value = str(config_dir)
                mock_data_dir.return_value = str(data_dir)

                # First instance
                config1 = ConfigManager()
                config1.set("test_setting", "test_value")
                config1.set("colors.custom", "purple")
                del config1  # Ensure instance is cleaned up

                # Second instance
                config2 = ConfigManager()

                # Assert settings persisted
                assert config2.get("test_setting") == "test_value"
                assert config2.get("colors.custom") == "purple"

    def test_config_file_format_and_structure(self) -> None:
        """Test that config file has correct format and structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            data_dir = Path(temp_dir) / "data"

            with (
                patch("trackit.utils.config.user_config_dir") as mock_config_dir,
                patch("trackit.utils.config.user_data_dir") as mock_data_dir,
            ):

                mock_config_dir.return_value = str(config_dir)
                mock_data_dir.return_value = str(data_dir)

                # Create config manager
                config_manager = ConfigManager()
                config_file = config_manager.config_file

                # Verify file exists and is valid JSON
                assert config_file.exists()
                with open(config_file, "r") as f:
                    config_data = json.load(f)

                # Verify structure
                assert isinstance(config_data, dict)
                assert "colors" in config_data
                assert "display" in config_data
                assert isinstance(config_data["colors"], dict)
                assert isinstance(config_data["display"], dict)

                # Verify JSON is formatted (indented)
                with open(config_file, "r") as f:
                    content = f.read()
                assert "\n" in content  # Should be pretty-printed
                assert "  " in content  # Should have indentation


@pytest.mark.unit
class TestConfigManagerEdgeCases:
    """Test edge cases and error conditions."""

    def test_get_with_deep_nesting(self) -> None:
        """Test getting values with deep nesting."""
        config_manager = ConfigManager()
        config_manager.set("level1.level2.level3.level4", "deep_value")

        # Act & Assert
        assert config_manager.get("level1.level2.level3.level4") == "deep_value"
        assert config_manager.get("level1.level2.level3") == {"level4": "deep_value"}

    def test_set_with_none_value(self) -> None:
        """Test setting None value."""
        config_manager = ConfigManager()

        # Act
        config_manager.set("null_value", None)

        # Assert
        assert config_manager.get("null_value") is None

    def test_set_with_empty_key(self) -> None:
        """Test setting value with empty key."""
        config_manager = ConfigManager()

        # Act - should handle gracefully
        config_manager.set("", "empty_key_value")

        # Assert
        assert config_manager.get("") == "empty_key_value"

    def test_get_with_non_dict_intermediate_value(self) -> None:
        """Test getting nested value when intermediate is not dict."""
        config_manager = ConfigManager()
        config_manager.set("string_value", "not_a_dict")

        # Act & Assert
        assert config_manager.get("string_value.nested", "default") == "default"

    def test_large_configuration_handling(self) -> None:
        """Test handling large configuration."""
        config_manager = ConfigManager()

        # Create large config structure
        for i in range(100):
            config_manager.set(f"section_{i}.key_{i}", f"value_{i}")

        # Verify all values are accessible
        for i in range(100):
            assert config_manager.get(f"section_{i}.key_{i}") == f"value_{i}"
