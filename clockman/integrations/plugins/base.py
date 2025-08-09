"""
Base plugin class for Clockman integrations.

This module provides the abstract base class that all Clockman plugins must inherit from.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from ..events.events import ClockmanEvent, EventType


class PluginInfo(BaseModel):
    """Information about a plugin."""
    
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the plugin")
    name: str = Field(..., description="Human-readable name of the plugin")
    version: str = Field(..., description="Version of the plugin")
    description: str = Field(..., description="Description of what the plugin does")
    author: str = Field(..., description="Author of the plugin")
    website: Optional[str] = Field(None, description="Plugin website or repository URL")
    
    # Event handling capabilities
    supported_events: List[EventType] = Field(default_factory=list, description="Event types this plugin can handle")
    
    # Configuration schema
    config_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for plugin configuration")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {UUID: str}


class BasePlugin(ABC):
    """
    Abstract base class for all Clockman plugins.
    
    Plugins provide a way to extend Clockman's functionality by responding to events
    and performing custom actions. All plugins must inherit from this class and
    implement the required methods.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the plugin.
        
        Args:
            config: Optional configuration dictionary for the plugin
        """
        self._config = config or {}
        self._enabled = True
        self._initialized = False
    
    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """
        Get information about this plugin.
        
        Returns:
            PluginInfo object with metadata about the plugin
        """
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the plugin.
        
        This method is called once when the plugin is loaded. Use it to set up
        any resources, connections, or configuration that the plugin needs.
        
        Raises:
            Exception: If initialization fails
        """
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """
        Shutdown the plugin and cleanup resources.
        
        This method is called when the plugin is being unloaded or when
        Clockman is shutting down. Use it to cleanup any resources,
        close connections, etc.
        """
        pass
    
    @abstractmethod
    def handle_event(self, event: ClockmanEvent) -> None:
        """
        Handle a Clockman event.
        
        This method is called whenever an event occurs that this plugin
        has registered to receive. The plugin should process the event
        and perform any necessary actions.
        
        Args:
            event: The event to handle
        """
        pass
    
    def can_handle_event(self, event_type: EventType) -> bool:
        """
        Check if this plugin can handle a specific event type.
        
        Args:
            event_type: The event type to check
            
        Returns:
            True if the plugin can handle this event type
        """
        return event_type in self.info.supported_events
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: The configuration key
            default: Default value if key is not found
            
        Returns:
            The configuration value
        """
        return self._config.get(key, default)
    
    def set_config_value(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: The configuration key
            value: The value to set
        """
        self._config[key] = value
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the complete configuration dictionary.
        
        Returns:
            The plugin's configuration
        """
        return self._config.copy()
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update the plugin's configuration.
        
        Args:
            config: New configuration values to merge
        """
        self._config.update(config)
    
    def is_enabled(self) -> bool:
        """
        Check if the plugin is enabled.
        
        Returns:
            True if the plugin is enabled
        """
        return self._enabled
    
    def enable(self) -> None:
        """Enable the plugin."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable the plugin."""
        self._enabled = False
    
    def is_initialized(self) -> bool:
        """
        Check if the plugin has been initialized.
        
        Returns:
            True if the plugin has been initialized
        """
        return self._initialized
    
    def _set_initialized(self, initialized: bool = True) -> None:
        """
        Set the initialization status.
        
        This is called internally by the plugin manager.
        
        Args:
            initialized: Whether the plugin is initialized
        """
        self._initialized = initialized
    
    def validate_config(self) -> bool:
        """
        Validate the plugin's configuration.
        
        This method can be overridden by plugins to perform custom
        configuration validation.
        
        Returns:
            True if the configuration is valid
            
        Raises:
            ValueError: If the configuration is invalid
        """
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the plugin.
        
        This method can be overridden by plugins to provide custom
        status information.
        
        Returns:
            Dictionary with status information
        """
        return {
            "enabled": self._enabled,
            "initialized": self._initialized,
            "config_keys": list(self._config.keys()),
        }
    
    def __str__(self) -> str:
        """String representation of the plugin."""
        return f"{self.info.name} v{self.info.version}"
    
    def __repr__(self) -> str:
        """Detailed string representation of the plugin."""
        return f"<{self.__class__.__name__}: {self.info.name} v{self.info.version}>"