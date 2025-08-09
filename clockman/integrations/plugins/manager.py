"""
Plugin management system for Clockman.

This module provides centralized management of loaded plugins, including
lifecycle management, event handling, and status monitoring.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from ..events.events import ClockmanEvent, EventType
from .base import BasePlugin
from .loader import PluginLoader, PluginLoadError

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Manages the lifecycle and execution of Clockman plugins.
    
    This class provides centralized management for all loaded plugins,
    including initialization, event distribution, and cleanup.
    """
    
    def __init__(self, plugin_directories: Optional[List[Path]] = None):
        """
        Initialize the plugin manager.
        
        Args:
            plugin_directories: List of directories to search for plugins
        """
        self.loader = PluginLoader(plugin_directories)
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
        self._event_subscriptions: Dict[EventType, List[str]] = {}
        
        # Statistics
        self._events_handled = 0
        self._plugin_errors = 0
    
    def add_plugin_directory(self, directory: Path) -> None:
        """
        Add a directory to search for plugins.
        
        Args:
            directory: Path to the plugin directory
        """
        self.loader.add_plugin_directory(directory)
    
    def discover_plugins(self) -> Dict[str, Path]:
        """
        Discover available plugins.
        
        Returns:
            Dictionary mapping plugin names to their file paths
        """
        return self.loader.discover_plugins()
    
    def load_plugin(
        self,
        plugin_name: str,
        plugin_file: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Load a specific plugin.
        
        Args:
            plugin_name: Name of the plugin to load
            plugin_file: Optional path to the plugin file (if not discovered)
            config: Optional configuration for the plugin
            
        Returns:
            True if the plugin was loaded successfully
        """
        try:
            # If plugin is already loaded, unload it first
            if plugin_name in self._plugins:
                logger.info(f"Plugin {plugin_name} already loaded, reloading...")
                self.unload_plugin(plugin_name)
            
            # Load plugin class
            if plugin_file:
                plugin_class = self.loader.load_plugin_from_file(plugin_file, plugin_name)
            else:
                # Try to find in discovered plugins
                discovered = self.loader.get_discovered_plugins()
                if plugin_name not in discovered:
                    # Try to discover plugins if we haven't yet
                    self.discover_plugins()
                    discovered = self.loader.get_discovered_plugins()
                
                if plugin_name not in discovered:
                    logger.error(f"Plugin {plugin_name} not found in discovered plugins")
                    return False
                
                plugin_class = self.loader.load_plugin_from_file(
                    discovered[plugin_name], plugin_name
                )
            
            if not plugin_class:
                logger.error(f"Failed to load plugin class for {plugin_name}")
                return False
            
            # Instantiate plugin
            plugin_instance = self.loader.instantiate_plugin(plugin_class, config)
            
            # Initialize plugin
            plugin_instance.initialize()
            plugin_instance._set_initialized(True)
            
            # Store plugin and configuration
            self._plugins[plugin_name] = plugin_instance
            if config:
                self._plugin_configs[plugin_name] = config
            
            # Update event subscriptions
            self._update_event_subscriptions()
            
            logger.info(f"Successfully loaded and initialized plugin: {plugin_name}")
            return True
            
        except PluginLoadError as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error loading plugin {plugin_name}: {e}", exc_info=True)
            return False
    
    def load_plugin_from_module(
        self,
        module_name: str,
        plugin_name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Load a plugin from an installed Python module.
        
        Args:
            module_name: Name of the module to import
            plugin_name: Optional name for the plugin (defaults to module name)
            config: Optional configuration for the plugin
            
        Returns:
            True if the plugin was loaded successfully
        """
        if plugin_name is None:
            plugin_name = module_name
        
        try:
            # If plugin is already loaded, unload it first
            if plugin_name in self._plugins:
                logger.info(f"Plugin {plugin_name} already loaded, reloading...")
                self.unload_plugin(plugin_name)
            
            # Load plugin class from module
            plugin_class = self.loader.load_plugin_from_module(module_name)
            
            if not plugin_class:
                logger.error(f"Failed to load plugin class from module {module_name}")
                return False
            
            # Instantiate plugin
            plugin_instance = self.loader.instantiate_plugin(plugin_class, config)
            
            # Initialize plugin
            plugin_instance.initialize()
            plugin_instance._set_initialized(True)
            
            # Store plugin and configuration
            self._plugins[plugin_name] = plugin_instance
            if config:
                self._plugin_configs[plugin_name] = config
            
            # Update event subscriptions
            self._update_event_subscriptions()
            
            logger.info(f"Successfully loaded and initialized plugin: {plugin_name} from module {module_name}")
            return True
            
        except PluginLoadError as e:
            logger.error(f"Failed to load plugin from module {module_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error loading plugin from module {module_name}: {e}", exc_info=True)
            return False
    
    def load_all_plugins(self, configs: Optional[Dict[str, Dict[str, Any]]] = None) -> int:
        """
        Load all discovered plugins.
        
        Args:
            configs: Optional dictionary of plugin configurations
            
        Returns:
            Number of plugins successfully loaded
        """
        configs = configs or {}
        discovered = self.discover_plugins()
        
        loaded_count = 0
        for plugin_name in discovered:
            plugin_config = configs.get(plugin_name)
            if self.load_plugin(plugin_name, config=plugin_config):
                loaded_count += 1
        
        logger.info(f"Loaded {loaded_count} out of {len(discovered)} discovered plugins")
        return loaded_count
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a specific plugin.
        
        Args:
            plugin_name: Name of the plugin to unload
            
        Returns:
            True if the plugin was unloaded successfully
        """
        if plugin_name not in self._plugins:
            logger.warning(f"Plugin {plugin_name} is not loaded")
            return False
        
        try:
            plugin = self._plugins[plugin_name]
            
            # Shutdown the plugin
            plugin.shutdown()
            plugin._set_initialized(False)
            
            # Remove from tracking
            del self._plugins[plugin_name]
            if plugin_name in self._plugin_configs:
                del self._plugin_configs[plugin_name]
            
            # Update event subscriptions
            self._update_event_subscriptions()
            
            logger.info(f"Successfully unloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {e}", exc_info=True)
            # Still remove the plugin from tracking even if shutdown failed
            if plugin_name in self._plugins:
                del self._plugins[plugin_name]
            if plugin_name in self._plugin_configs:
                del self._plugin_configs[plugin_name]
            self._update_event_subscriptions()
            return False
    
    def unload_all_plugins(self) -> int:
        """
        Unload all loaded plugins.
        
        Returns:
            Number of plugins successfully unloaded
        """
        plugin_names = list(self._plugins.keys())
        unloaded_count = 0
        
        for plugin_name in plugin_names:
            if self.unload_plugin(plugin_name):
                unloaded_count += 1
        
        logger.info(f"Unloaded {unloaded_count} plugins")
        return unloaded_count
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """
        Get a loaded plugin by name.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            The plugin instance, or None if not found
        """
        return self._plugins.get(plugin_name)
    
    def list_plugins(self) -> Dict[str, BasePlugin]:
        """
        Get all loaded plugins.
        
        Returns:
            Dictionary mapping plugin names to plugin instances
        """
        return self._plugins.copy()
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """
        Enable a plugin.
        
        Args:
            plugin_name: Name of the plugin to enable
            
        Returns:
            True if the plugin was enabled
        """
        plugin = self._plugins.get(plugin_name)
        if plugin:
            plugin.enable()
            logger.info(f"Enabled plugin: {plugin_name}")
            return True
        
        logger.warning(f"Plugin {plugin_name} not found")
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """
        Disable a plugin.
        
        Args:
            plugin_name: Name of the plugin to disable
            
        Returns:
            True if the plugin was disabled
        """
        plugin = self._plugins.get(plugin_name)
        if plugin:
            plugin.disable()
            logger.info(f"Disabled plugin: {plugin_name}")
            return True
        
        logger.warning(f"Plugin {plugin_name} not found")
        return False
    
    def handle_event(self, event: ClockmanEvent) -> None:
        """
        Handle an event by distributing it to interested plugins.
        
        Args:
            event: The event to handle
        """
        if event.event_type not in self._event_subscriptions:
            return
        
        interested_plugins = self._event_subscriptions[event.event_type]
        if not interested_plugins:
            return
        
        logger.debug(f"Distributing event {event.event_type.value} to {len(interested_plugins)} plugins")
        
        for plugin_name in interested_plugins:
            plugin = self._plugins.get(plugin_name)
            if not plugin or not plugin.is_enabled() or not plugin.is_initialized():
                continue
            
            try:
                self._events_handled += 1
                plugin.handle_event(event)
                logger.debug(f"Plugin {plugin_name} handled event {event.event_type.value}")
            except Exception as e:
                self._plugin_errors += 1
                logger.error(f"Error in plugin {plugin_name} handling event {event.event_type.value}: {e}", exc_info=True)
    
    def get_plugin_config(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the configuration for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            The plugin's configuration, or None if not found
        """
        return self._plugin_configs.get(plugin_name)
    
    def update_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """
        Update the configuration for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            config: New configuration values
            
        Returns:
            True if the configuration was updated
        """
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            logger.warning(f"Plugin {plugin_name} not found")
            return False
        
        try:
            plugin.update_config(config)
            self._plugin_configs[plugin_name] = plugin.get_config()
            logger.info(f"Updated configuration for plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to update config for plugin {plugin_name}: {e}", exc_info=True)
            return False
    
    def get_plugin_status(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin status information, or None if not found
        """
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            return None
        
        try:
            status = plugin.get_status()
            status.update({
                "plugin_name": plugin_name,
                "plugin_info": plugin.info.model_dump(),
            })
            return status
        except Exception as e:
            logger.error(f"Error getting status for plugin {plugin_name}: {e}", exc_info=True)
            return {
                "plugin_name": plugin_name,
                "error": str(e),
                "enabled": False,
                "initialized": False,
            }
    
    def get_all_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the status of all plugins.
        
        Returns:
            Dictionary mapping plugin names to status information
        """
        status = {}
        for plugin_name in self._plugins:
            status[plugin_name] = self.get_plugin_status(plugin_name)
        return status
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get plugin manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        total_plugins = len(self._plugins)
        enabled_plugins = sum(1 for p in self._plugins.values() if p.is_enabled())
        initialized_plugins = sum(1 for p in self._plugins.values() if p.is_initialized())
        
        return {
            "total_plugins": total_plugins,
            "enabled_plugins": enabled_plugins,
            "initialized_plugins": initialized_plugins,
            "events_handled": self._events_handled,
            "plugin_errors": self._plugin_errors,
            "event_subscriptions": {
                event_type.value: len(plugins) 
                for event_type, plugins in self._event_subscriptions.items()
            },
        }
    
    def _update_event_subscriptions(self) -> None:
        """Update the event subscription mapping based on loaded plugins."""
        self._event_subscriptions.clear()
        
        for plugin_name, plugin in self._plugins.items():
            if not plugin.is_enabled():
                continue
            
            for event_type in plugin.info.supported_events:
                if event_type not in self._event_subscriptions:
                    self._event_subscriptions[event_type] = []
                
                if plugin_name not in self._event_subscriptions[event_type]:
                    self._event_subscriptions[event_type].append(plugin_name)
        
        logger.debug(f"Updated event subscriptions: {len(self._event_subscriptions)} event types")
    
    def shutdown(self) -> None:
        """Shutdown the plugin manager and all loaded plugins."""
        logger.info("Shutting down plugin manager...")
        self.unload_all_plugins()
        self._event_subscriptions.clear()
        logger.info("Plugin manager shutdown complete")