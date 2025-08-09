"""
Configuration management for Clockman integrations.

This module provides configuration loading, saving, and management
for webhooks and plugins.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from .webhooks.models import WebhookConfig

logger = logging.getLogger(__name__)


class PluginConfigEntry(BaseModel):
    """Configuration entry for a plugin."""
    
    name: str = Field(..., description="Plugin name")
    enabled: bool = Field(default=True, description="Whether the plugin is enabled")
    module: Optional[str] = Field(None, description="Python module name (if loading from installed module)")
    file_path: Optional[str] = Field(None, description="Path to plugin file (if loading from file)")
    config: Dict[str, Any] = Field(default_factory=dict, description="Plugin-specific configuration")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {Path: str}


class IntegrationConfig(BaseModel):
    """Complete integration configuration for Clockman."""
    
    # Global settings
    enabled: bool = Field(default=True, description="Whether integrations are enabled globally")
    max_concurrent_webhooks: int = Field(default=10, description="Maximum concurrent webhook deliveries")
    max_plugin_workers: int = Field(default=4, description="Maximum worker threads for plugin execution")
    
    # Plugin settings
    plugin_directories: List[str] = Field(default_factory=list, description="Directories to search for plugins")
    plugins: List[PluginConfigEntry] = Field(default_factory=list, description="Plugin configurations")
    
    # Webhook settings
    webhooks: List[WebhookConfig] = Field(default_factory=list, description="Webhook configurations")
    webhook_history_limit: int = Field(default=1000, description="Maximum webhook delivery history entries")
    
    # Event settings
    event_history_limit: int = Field(default=500, description="Maximum event history entries")
    async_event_execution: bool = Field(default=True, description="Execute event handlers asynchronously")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            UUID: str,
            Path: str,
        }


class IntegrationConfigManager:
    """
    Manages loading, saving, and validation of integration configurations.
    
    This class provides a centralized way to manage all integration-related
    configuration, including plugins and webhooks.
    """
    
    def __init__(self, config_file: Path):
        """
        Initialize the configuration manager.
        
        Args:
            config_file: Path to the configuration file
        """
        self.config_file = Path(config_file)
        self._config: Optional[IntegrationConfig] = None
    
    def load_config(self) -> IntegrationConfig:
        """
        Load configuration from file.
        
        Returns:
            The loaded configuration
            
        Raises:
            FileNotFoundError: If the config file doesn't exist
            ValidationError: If the configuration is invalid
        """
        if not self.config_file.exists():
            logger.info(f"Configuration file {self.config_file} does not exist, creating default config")
            self._config = IntegrationConfig()
            self.save_config()
            return self._config
        
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            self._config = IntegrationConfig(**config_data)
            logger.info(f"Loaded integration configuration from {self.config_file}")
            return self._config
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file {self.config_file}: {e}")
            raise
        except ValidationError as e:
            logger.error(f"Invalid configuration in {self.config_file}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration from {self.config_file}: {e}")
            raise
    
    def save_config(self) -> None:
        """
        Save the current configuration to file.
        
        Raises:
            RuntimeError: If no configuration is loaded
        """
        if self._config is None:
            raise RuntimeError("No configuration loaded to save")
        
        try:
            # Ensure parent directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write configuration
            with open(self.config_file, 'w') as f:
                json.dump(
                    self._config.model_dump(),
                    f,
                    indent=2,
                    default=str,  # Handle UUID and other types
                )
            
            logger.info(f"Saved integration configuration to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error saving configuration to {self.config_file}: {e}")
            raise
    
    def get_config(self) -> IntegrationConfig:
        """
        Get the current configuration.
        
        Returns:
            The current configuration
            
        Raises:
            RuntimeError: If no configuration is loaded
        """
        if self._config is None:
            self._config = self.load_config()
        
        return self._config
    
    def update_config(self, **updates: Any) -> None:
        """
        Update configuration values.
        
        Args:
            **updates: Configuration values to update
        """
        config = self.get_config()
        
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                logger.warning(f"Unknown configuration key: {key}")
        
        self.save_config()
        logger.info("Updated integration configuration")
    
    def add_plugin_directory(self, directory: Path) -> None:
        """
        Add a plugin directory to the configuration.
        
        Args:
            directory: Path to the plugin directory
        """
        config = self.get_config()
        directory_str = str(directory)
        
        if directory_str not in config.plugin_directories:
            config.plugin_directories.append(directory_str)
            self.save_config()
            logger.info(f"Added plugin directory: {directory}")
    
    def remove_plugin_directory(self, directory: Path) -> bool:
        """
        Remove a plugin directory from the configuration.
        
        Args:
            directory: Path to the plugin directory
            
        Returns:
            True if the directory was removed
        """
        config = self.get_config()
        directory_str = str(directory)
        
        if directory_str in config.plugin_directories:
            config.plugin_directories.remove(directory_str)
            self.save_config()
            logger.info(f"Removed plugin directory: {directory}")
            return True
        
        return False
    
    def add_plugin_config(self, plugin_config: PluginConfigEntry) -> None:
        """
        Add a plugin configuration.
        
        Args:
            plugin_config: The plugin configuration to add
        """
        config = self.get_config()
        
        # Remove existing config with same name
        config.plugins = [p for p in config.plugins if p.name != plugin_config.name]
        
        # Add new config
        config.plugins.append(plugin_config)
        self.save_config()
        logger.info(f"Added plugin configuration: {plugin_config.name}")
    
    def remove_plugin_config(self, plugin_name: str) -> bool:
        """
        Remove a plugin configuration.
        
        Args:
            plugin_name: Name of the plugin to remove
            
        Returns:
            True if the plugin configuration was removed
        """
        config = self.get_config()
        original_count = len(config.plugins)
        
        config.plugins = [p for p in config.plugins if p.name != plugin_name]
        
        if len(config.plugins) < original_count:
            self.save_config()
            logger.info(f"Removed plugin configuration: {plugin_name}")
            return True
        
        return False
    
    def get_plugin_config(self, plugin_name: str) -> Optional[PluginConfigEntry]:
        """
        Get configuration for a specific plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            The plugin configuration, or None if not found
        """
        config = self.get_config()
        
        for plugin_config in config.plugins:
            if plugin_config.name == plugin_name:
                return plugin_config
        
        return None
    
    def update_plugin_config(
        self,
        plugin_name: str,
        **updates: Any
    ) -> bool:
        """
        Update configuration for a specific plugin.
        
        Args:
            plugin_name: Name of the plugin
            **updates: Configuration values to update
            
        Returns:
            True if the plugin configuration was updated
        """
        config = self.get_config()
        
        for plugin_config in config.plugins:
            if plugin_config.name == plugin_name:
                for key, value in updates.items():
                    if hasattr(plugin_config, key):
                        setattr(plugin_config, key, value)
                    elif key in plugin_config.config:
                        plugin_config.config[key] = value
                    else:
                        logger.warning(f"Unknown plugin config key: {key}")
                
                self.save_config()
                logger.info(f"Updated plugin configuration: {plugin_name}")
                return True
        
        return False
    
    def add_webhook_config(self, webhook_config: WebhookConfig) -> None:
        """
        Add a webhook configuration.
        
        Args:
            webhook_config: The webhook configuration to add
        """
        config = self.get_config()
        
        # Remove existing config with same ID or name
        config.webhooks = [
            w for w in config.webhooks 
            if w.id != webhook_config.id and w.name != webhook_config.name
        ]
        
        # Add new config
        config.webhooks.append(webhook_config)
        self.save_config()
        logger.info(f"Added webhook configuration: {webhook_config.name}")
    
    def remove_webhook_config(self, webhook_id: UUID) -> bool:
        """
        Remove a webhook configuration.
        
        Args:
            webhook_id: UUID of the webhook to remove
            
        Returns:
            True if the webhook configuration was removed
        """
        config = self.get_config()
        original_count = len(config.webhooks)
        
        config.webhooks = [w for w in config.webhooks if w.id != webhook_id]
        
        if len(config.webhooks) < original_count:
            self.save_config()
            logger.info(f"Removed webhook configuration: {webhook_id}")
            return True
        
        return False
    
    def get_webhook_config(self, webhook_id: UUID) -> Optional[WebhookConfig]:
        """
        Get configuration for a specific webhook.
        
        Args:
            webhook_id: UUID of the webhook
            
        Returns:
            The webhook configuration, or None if not found
        """
        config = self.get_config()
        
        for webhook_config in config.webhooks:
            if webhook_config.id == webhook_id:
                return webhook_config
        
        return None
    
    def get_webhook_config_by_name(self, webhook_name: str) -> Optional[WebhookConfig]:
        """
        Get configuration for a specific webhook by name.
        
        Args:
            webhook_name: Name of the webhook
            
        Returns:
            The webhook configuration, or None if not found
        """
        config = self.get_config()
        
        for webhook_config in config.webhooks:
            if webhook_config.name == webhook_name:
                return webhook_config
        
        return None
    
    def update_webhook_config(
        self,
        webhook_id: UUID,
        **updates: Any
    ) -> bool:
        """
        Update configuration for a specific webhook.
        
        Args:
            webhook_id: UUID of the webhook
            **updates: Configuration values to update
            
        Returns:
            True if the webhook configuration was updated
        """
        config = self.get_config()
        
        for webhook_config in config.webhooks:
            if webhook_config.id == webhook_id:
                for key, value in updates.items():
                    if hasattr(webhook_config, key):
                        setattr(webhook_config, key, value)
                    else:
                        logger.warning(f"Unknown webhook config key: {key}")
                
                self.save_config()
                logger.info(f"Updated webhook configuration: {webhook_id}")
                return True
        
        return False
    
    def get_enabled_plugins(self) -> List[PluginConfigEntry]:
        """
        Get all enabled plugin configurations.
        
        Returns:
            List of enabled plugin configurations
        """
        config = self.get_config()
        return [p for p in config.plugins if p.enabled]
    
    def get_active_webhooks(self) -> List[WebhookConfig]:
        """
        Get all active webhook configurations.
        
        Returns:
            List of active webhook configurations
        """
        config = self.get_config()
        return [w for w in config.webhooks if w.is_active()]
    
    def validate_config(self) -> bool:
        """
        Validate the current configuration.
        
        Returns:
            True if the configuration is valid
            
        Raises:
            ValidationError: If the configuration is invalid
        """
        try:
            config = self.get_config()
            
            # Validate plugin directories exist
            for directory_str in config.plugin_directories:
                directory = Path(directory_str)
                if not directory.exists():
                    logger.warning(f"Plugin directory does not exist: {directory}")
            
            # Validate plugin configurations
            for plugin_config in config.plugins:
                if plugin_config.module and plugin_config.file_path:
                    logger.warning(f"Plugin {plugin_config.name} has both module and file_path specified")
                
                if plugin_config.file_path:
                    file_path = Path(plugin_config.file_path)
                    if not file_path.exists():
                        logger.warning(f"Plugin file does not exist: {file_path}")
            
            # Validate webhook configurations
            webhook_names = set()
            for webhook_config in config.webhooks:
                if webhook_config.name in webhook_names:
                    logger.warning(f"Duplicate webhook name: {webhook_config.name}")
                webhook_names.add(webhook_config.name)
            
            logger.info("Configuration validation completed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
    
    def reset_config(self) -> None:
        """Reset configuration to defaults."""
        self._config = IntegrationConfig()
        self.save_config()
        logger.info("Reset integration configuration to defaults")
    
    def export_config(self, export_file: Path) -> None:
        """
        Export configuration to a file.
        
        Args:
            export_file: Path to export the configuration to
        """
        config = self.get_config()
        
        try:
            export_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_file, 'w') as f:
                json.dump(
                    config.model_dump(),
                    f,
                    indent=2,
                    default=str,
                )
            
            logger.info(f"Exported configuration to {export_file}")
            
        except Exception as e:
            logger.error(f"Error exporting configuration to {export_file}: {e}")
            raise
    
    def import_config(self, import_file: Path) -> None:
        """
        Import configuration from a file.
        
        Args:
            import_file: Path to import the configuration from
            
        Raises:
            FileNotFoundError: If the import file doesn't exist
            ValidationError: If the imported configuration is invalid
        """
        if not import_file.exists():
            raise FileNotFoundError(f"Import file does not exist: {import_file}")
        
        try:
            with open(import_file, 'r') as f:
                config_data = json.load(f)
            
            imported_config = IntegrationConfig(**config_data)
            self._config = imported_config
            self.save_config()
            
            logger.info(f"Imported configuration from {import_file}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in import file {import_file}: {e}")
            raise
        except ValidationError as e:
            logger.error(f"Invalid configuration in import file {import_file}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error importing configuration from {import_file}: {e}")
            raise