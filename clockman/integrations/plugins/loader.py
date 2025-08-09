"""
Plugin loading and discovery system for Clockman.

This module handles the discovery, loading, and validation of plugins.
"""

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base import BasePlugin

logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """Raised when a plugin fails to load."""
    pass


class PluginLoader:
    """
    Handles discovery and loading of Clockman plugins.
    
    This class provides functionality to:
    - Discover plugins in specified directories
    - Load plugins from Python modules
    - Validate plugin classes
    - Handle loading errors gracefully
    """
    
    def __init__(self, plugin_directories: Optional[List[Path]] = None):
        """
        Initialize the plugin loader.
        
        Args:
            plugin_directories: List of directories to search for plugins
        """
        self.plugin_directories = plugin_directories or []
        self._discovered_plugins: Dict[str, Path] = {}
        self._loaded_plugin_classes: Dict[str, Type[BasePlugin]] = {}
    
    def add_plugin_directory(self, directory: Path) -> None:
        """
        Add a directory to search for plugins.
        
        Args:
            directory: Path to the plugin directory
        """
        if directory not in self.plugin_directories:
            self.plugin_directories.append(directory)
            logger.info(f"Added plugin directory: {directory}")
    
    def discover_plugins(self) -> Dict[str, Path]:
        """
        Discover plugins in all configured directories.
        
        This method searches for Python files that contain plugin classes
        and builds a mapping of plugin names to file paths.
        
        Returns:
            Dictionary mapping plugin names to their file paths
        """
        self._discovered_plugins.clear()
        
        for directory in self.plugin_directories:
            if not directory.exists():
                logger.warning(f"Plugin directory does not exist: {directory}")
                continue
            
            if not directory.is_dir():
                logger.warning(f"Plugin path is not a directory: {directory}")
                continue
            
            logger.info(f"Discovering plugins in: {directory}")
            
            # Look for Python files
            for plugin_file in directory.glob("*.py"):
                if plugin_file.name.startswith("__"):
                    continue  # Skip __init__.py, __pycache__, etc.
                
                plugin_name = plugin_file.stem
                self._discovered_plugins[plugin_name] = plugin_file
                logger.debug(f"Discovered plugin file: {plugin_name} -> {plugin_file}")
        
        logger.info(f"Discovered {len(self._discovered_plugins)} potential plugins")
        return self._discovered_plugins.copy()
    
    def load_plugin_from_file(self, plugin_file: Path, plugin_name: Optional[str] = None) -> Optional[Type[BasePlugin]]:
        """
        Load a plugin class from a Python file.
        
        Args:
            plugin_file: Path to the plugin Python file
            plugin_name: Optional name for the plugin (defaults to filename stem)
            
        Returns:
            The loaded plugin class, or None if loading failed
            
        Raises:
            PluginLoadError: If the plugin cannot be loaded
        """
        if plugin_name is None:
            plugin_name = plugin_file.stem
        
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Could not create module spec for {plugin_file}")
            
            module = importlib.util.module_from_spec(spec)
            
            # Add to sys.modules before executing
            sys.modules[plugin_name] = module
            
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                # Remove from sys.modules on failure
                if plugin_name in sys.modules:
                    del sys.modules[plugin_name]
                raise PluginLoadError(f"Failed to execute module {plugin_file}: {e}") from e
            
            # Find plugin classes in the module
            plugin_classes = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type) and
                    issubclass(attr, BasePlugin) and
                    attr != BasePlugin
                ):
                    plugin_classes.append(attr)
            
            if not plugin_classes:
                raise PluginLoadError(f"No plugin classes found in {plugin_file}")
            
            if len(plugin_classes) > 1:
                logger.warning(f"Multiple plugin classes found in {plugin_file}, using the first one")
            
            plugin_class = plugin_classes[0]
            self._loaded_plugin_classes[plugin_name] = plugin_class
            
            logger.info(f"Successfully loaded plugin class: {plugin_class.__name__} from {plugin_file}")
            return plugin_class
            
        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_file}: {e}", exc_info=True)
            raise PluginLoadError(f"Failed to load plugin from {plugin_file}: {e}") from e
    
    def load_plugin_from_module(self, module_name: str) -> Optional[Type[BasePlugin]]:
        """
        Load a plugin class from an installed Python module.
        
        Args:
            module_name: Name of the module to import
            
        Returns:
            The loaded plugin class, or None if loading failed
            
        Raises:
            PluginLoadError: If the plugin cannot be loaded
        """
        try:
            module = importlib.import_module(module_name)
            
            # Find plugin classes in the module
            plugin_classes = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type) and
                    issubclass(attr, BasePlugin) and
                    attr != BasePlugin
                ):
                    plugin_classes.append(attr)
            
            if not plugin_classes:
                raise PluginLoadError(f"No plugin classes found in module {module_name}")
            
            if len(plugin_classes) > 1:
                logger.warning(f"Multiple plugin classes found in {module_name}, using the first one")
            
            plugin_class = plugin_classes[0]
            self._loaded_plugin_classes[module_name] = plugin_class
            
            logger.info(f"Successfully loaded plugin class: {plugin_class.__name__} from module {module_name}")
            return plugin_class
            
        except ImportError as e:
            logger.error(f"Failed to import module {module_name}: {e}")
            raise PluginLoadError(f"Failed to import module {module_name}: {e}") from e
        except Exception as e:
            logger.error(f"Failed to load plugin from module {module_name}: {e}", exc_info=True)
            raise PluginLoadError(f"Failed to load plugin from module {module_name}: {e}") from e
    
    def instantiate_plugin(
        self,
        plugin_class: Type[BasePlugin],
        config: Optional[Dict[str, Any]] = None
    ) -> BasePlugin:
        """
        Create an instance of a plugin class.
        
        Args:
            plugin_class: The plugin class to instantiate
            config: Optional configuration for the plugin
            
        Returns:
            An instance of the plugin
            
        Raises:
            PluginLoadError: If the plugin cannot be instantiated
        """
        try:
            plugin_instance = plugin_class(config)
            
            # Validate the plugin
            if not isinstance(plugin_instance, BasePlugin):
                raise PluginLoadError(f"Plugin class {plugin_class.__name__} does not inherit from BasePlugin")
            
            # Validate configuration if provided
            if config:
                plugin_instance.validate_config()
            
            logger.info(f"Successfully instantiated plugin: {plugin_instance}")
            return plugin_instance
            
        except Exception as e:
            logger.error(f"Failed to instantiate plugin {plugin_class.__name__}: {e}", exc_info=True)
            raise PluginLoadError(f"Failed to instantiate plugin {plugin_class.__name__}: {e}") from e
    
    def load_all_discovered_plugins(self) -> Dict[str, BasePlugin]:
        """
        Load all discovered plugins and return instances.
        
        Returns:
            Dictionary mapping plugin names to plugin instances
        """
        if not self._discovered_plugins:
            self.discover_plugins()
        
        loaded_plugins = {}
        
        for plugin_name, plugin_file in self._discovered_plugins.items():
            try:
                plugin_class = self.load_plugin_from_file(plugin_file, plugin_name)
                if plugin_class:
                    plugin_instance = self.instantiate_plugin(plugin_class)
                    loaded_plugins[plugin_name] = plugin_instance
            except PluginLoadError as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error loading plugin {plugin_name}: {e}", exc_info=True)
                continue
        
        logger.info(f"Successfully loaded {len(loaded_plugins)} out of {len(self._discovered_plugins)} discovered plugins")
        return loaded_plugins
    
    def get_discovered_plugins(self) -> Dict[str, Path]:
        """
        Get the list of discovered plugins.
        
        Returns:
            Dictionary mapping plugin names to their file paths
        """
        return self._discovered_plugins.copy()
    
    def get_loaded_plugin_classes(self) -> Dict[str, Type[BasePlugin]]:
        """
        Get the list of loaded plugin classes.
        
        Returns:
            Dictionary mapping plugin names to their classes
        """
        return self._loaded_plugin_classes.copy()
    
    def validate_plugin_class(self, plugin_class: Type[BasePlugin]) -> bool:
        """
        Validate that a plugin class is properly implemented.
        
        Args:
            plugin_class: The plugin class to validate
            
        Returns:
            True if the plugin class is valid
            
        Raises:
            PluginLoadError: If the plugin class is invalid
        """
        if not issubclass(plugin_class, BasePlugin):
            raise PluginLoadError(f"Plugin class {plugin_class.__name__} does not inherit from BasePlugin")
        
        # Check that required abstract methods are implemented
        required_methods = ["info", "initialize", "shutdown", "handle_event"]
        
        for method_name in required_methods:
            if not hasattr(plugin_class, method_name):
                raise PluginLoadError(f"Plugin class {plugin_class.__name__} is missing required method: {method_name}")
            
            method = getattr(plugin_class, method_name)
            if not callable(method):
                raise PluginLoadError(f"Plugin class {plugin_class.__name__} method {method_name} is not callable")
        
        # Try to create a temporary instance to validate the info property
        try:
            temp_instance = plugin_class()
            plugin_info = temp_instance.info
            
            # Validate plugin info
            if not plugin_info.name:
                raise PluginLoadError(f"Plugin class {plugin_class.__name__} has empty name")
            
            if not plugin_info.version:
                raise PluginLoadError(f"Plugin class {plugin_class.__name__} has empty version")
                
        except Exception as e:
            raise PluginLoadError(f"Failed to validate plugin class {plugin_class.__name__}: {e}") from e
        
        return True