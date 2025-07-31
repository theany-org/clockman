"""
Configuration management for TrackIt.

This module handles user configuration, data directories, and settings.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from platformdirs import user_data_dir, user_config_dir


class ConfigManager:
    """Manages TrackIt configuration and data directories."""

    def __init__(self):
        """Initialize configuration manager."""
        self.app_name = "trackit"
        self.config_dir = Path(user_config_dir(self.app_name))
        self.data_dir = Path(user_data_dir(self.app_name))
        self.config_file = self.config_dir / "config.json"

        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Default configuration
        self.default_config = {
            "data_directory": str(self.data_dir),
            "date_format": "%Y-%m-%d",
            "time_format": "%H:%M:%S",
            "timezone": "local",
            "default_tags": [],
            "auto_stop_inactive": False,
            "inactive_timeout_minutes": 30,
            "colors": {
                "active": "green",
                "inactive": "dim",
                "duration": "cyan",
                "task_name": "bold",
                "tags": "yellow",
            },
            "display": {
                "show_seconds": True,
                "compact_mode": False,
                "max_task_name_length": 50,
            },
        }

        # Load existing configuration
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file, creating default if it doesn't exist."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    loaded_config = json.load(f)

                # Merge with defaults to ensure all keys exist
                config = self.default_config.copy()
                config.update(loaded_config)
                return config

            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config file: {e}")
                print("Using default configuration")

        # Create default config file
        self._save_config(self.default_config)
        return self.default_config.copy()

    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2, sort_keys=True)
        except IOError as e:
            print(f"Warning: Could not save config file: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key, with optional default."""
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by key."""
        keys = key.split(".")
        config = self._config

        # Navigate to the parent dictionary
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set the value
        config[keys[-1]] = value

        # Save configuration
        self._save_config(self._config)

    def get_data_dir(self) -> Path:
        """Get the data directory path."""
        data_dir_str = self.get("data_directory", str(self.data_dir))
        return Path(data_dir_str)

    def get_config_dir(self) -> Path:
        """Get the configuration directory path."""
        return self.config_dir

    def get_date_format(self) -> str:
        """Get the date format string."""
        return self.get("date_format", "%Y-%m-%d")

    def get_time_format(self) -> str:
        """Get the time format string."""
        return self.get("time_format", "%H:%M:%S")

    def get_color(self, element: str) -> str:
        """Get color for a UI element."""
        return self.get(f"colors.{element}", "white")

    def is_compact_mode(self) -> bool:
        """Check if compact display mode is enabled."""
        return self.get("display.compact_mode", False)

    def show_seconds(self) -> bool:
        """Check if seconds should be shown in time displays."""
        return self.get("display.show_seconds", True)

    def get_max_task_name_length(self) -> int:
        """Get maximum task name length for display."""
        return self.get("display.max_task_name_length", 50)

    def get_default_tags(self) -> list:
        """Get default tags to suggest."""
        return self.get("default_tags", [])

    def is_auto_stop_enabled(self) -> bool:
        """Check if auto-stop on inactivity is enabled."""
        return self.get("auto_stop_inactive", False)

    def get_inactive_timeout(self) -> int:
        """Get inactivity timeout in minutes."""
        return self.get("inactive_timeout_minutes", 30)

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self._config = self.default_config.copy()
        self._save_config(self._config)

    def export_config(self, file_path: Path) -> None:
        """Export current configuration to a file."""
        with open(file_path, "w") as f:
            json.dump(self._config, f, indent=2, sort_keys=True)

    def import_config(self, file_path: Path) -> None:
        """Import configuration from a file."""
        with open(file_path, "r") as f:
            imported_config = json.load(f)

        # Merge with current config
        self._config.update(imported_config)
        self._save_config(self._config)


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
