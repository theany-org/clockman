"""
Central integration manager for Clockman.

This module provides a unified interface for managing all integration
functionality including events, webhooks, and plugins.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from .config import IntegrationConfigManager
from .events.event_manager import EventManager
from .events.events import ClockmanEvent, EventType
from .plugins.manager import PluginManager
from .webhooks.models import WebhookConfig
from .webhooks.webhook_manager import WebhookManager
from .hooks import HookManager, get_hook_manager

logger = logging.getLogger(__name__)


class IntegrationManager:
    """
    Central manager for all Clockman integrations.
    
    This class coordinates between the event system, webhook manager,
    and plugin manager to provide a unified integration experience.
    """
    
    def __init__(self, data_dir: Path):
        """
        Initialize the integration manager.
        
        Args:
            data_dir: Directory for storing integration data and configuration
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize configuration
        config_file = self.data_dir / "integrations.json"
        self.config_manager = IntegrationConfigManager(config_file)
        
        # Load configuration
        try:
            self.config = self.config_manager.load_config()
        except Exception as e:
            logger.error(f"Failed to load integration configuration: {e}")
            self.config = self.config_manager.get_config()
        
        # Initialize managers
        self.event_manager = EventManager(max_workers=self.config.max_plugin_workers)
        self.webhook_manager = WebhookManager(max_concurrent_deliveries=self.config.max_concurrent_webhooks)
        self.plugin_manager = PluginManager()
        self.hook_manager = get_hook_manager()
        
        # Set up plugin directories
        for directory_str in self.config.plugin_directories:
            self.plugin_manager.add_plugin_directory(Path(directory_str))
        
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize all integration components."""
        if self._initialized:
            logger.warning("Integration manager already initialized")
            return
        
        try:
            logger.info("Initializing integration manager...")
            
            # Load webhooks
            for webhook_config in self.config.webhooks:
                self.webhook_manager.add_webhook(webhook_config)
            
            # Register webhook handler with event manager
            self.event_manager.register_global_hook(
                callback=self._handle_event_for_webhooks,
                name="webhook_handler",
                priority=10,  # High priority for webhooks
            )
            
            # Register plugin handler with event manager
            self.event_manager.register_global_hook(
                callback=self._handle_event_for_plugins,
                name="plugin_handler",
                priority=20,  # Lower priority than webhooks
            )
            
            # Register hook manager handler with event manager
            self.event_manager.register_global_hook(
                callback=self._handle_event_for_hooks,
                name="hook_handler",
                priority=5,  # High priority for hooks
            )
            
            # Load plugins
            enabled_plugins = self.config_manager.get_enabled_plugins()
            for plugin_config in enabled_plugins:
                try:
                    if plugin_config.module:
                        success = self.plugin_manager.load_plugin_from_module(
                            plugin_config.module,
                            plugin_config.name,
                            plugin_config.config,
                        )
                    elif plugin_config.file_path:
                        success = self.plugin_manager.load_plugin(
                            plugin_config.name,
                            Path(plugin_config.file_path),
                            plugin_config.config,
                        )
                    else:
                        # Try to load from discovered plugins
                        success = self.plugin_manager.load_plugin(
                            plugin_config.name,
                            config=plugin_config.config,
                        )
                    
                    if not success:
                        logger.warning(f"Failed to load plugin: {plugin_config.name}")
                    
                except Exception as e:
                    logger.error(f"Error loading plugin {plugin_config.name}: {e}", exc_info=True)
            
            self._initialized = True
            logger.info("Integration manager initialization complete")
            
            # Emit system started event
            if self.config.enabled:
                self.emit_event(EventType.SYSTEM_STARTED, {
                    "source": "integration_manager",
                    "plugins_loaded": len(self.plugin_manager.list_plugins()),
                    "webhooks_configured": len(self.webhook_manager.list_webhooks()),
                })
            
        except Exception as e:
            logger.error(f"Failed to initialize integration manager: {e}", exc_info=True)
            raise
    
    def shutdown(self) -> None:
        """Shutdown all integration components."""
        if not self._initialized:
            return
        
        logger.info("Shutting down integration manager...")
        
        try:
            # Emit system shutdown event
            if self.config.enabled:
                self.emit_event(EventType.SYSTEM_SHUTDOWN, {
                    "source": "integration_manager",
                })
            
            # Shutdown components
            self.plugin_manager.shutdown()
            self.webhook_manager.shutdown()
            self.event_manager.shutdown()
            
            self._initialized = False
            logger.info("Integration manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during integration manager shutdown: {e}", exc_info=True)
    
    def is_enabled(self) -> bool:
        """Check if integrations are enabled."""
        return self.config.enabled
    
    def enable(self) -> None:
        """Enable integrations."""
        self.config_manager.update_config(enabled=True)
        self.config = self.config_manager.get_config()
        self.event_manager.enable()
        logger.info("Integrations enabled")
    
    def disable(self) -> None:
        """Disable integrations."""
        self.config_manager.update_config(enabled=False)
        self.config = self.config_manager.get_config()
        self.event_manager.disable()
        logger.info("Integrations disabled")
    
    def emit_event(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ClockmanEvent]:
        """
        Emit an event to all registered handlers.
        
        Args:
            event_type: The type of event to emit
            data: Event-specific data
            metadata: Additional metadata
            
        Returns:
            The created event, or None if integrations are disabled
        """
        if not self.config.enabled:
            return None
        
        event = self.event_manager.emit_event(
            event_type=event_type,
            data=data,
            metadata=metadata,
            async_execution=self.config.async_event_execution,
        )
        
        return event
    
    def _handle_event_for_webhooks(self, event: ClockmanEvent) -> None:
        """Handle events for webhook delivery."""
        try:
            self.webhook_manager.handle_event(event)
        except Exception as e:
            logger.error(f"Error handling event for webhooks: {e}", exc_info=True)
    
    def _handle_event_for_plugins(self, event: ClockmanEvent) -> None:
        """Handle events for plugin distribution."""
        try:
            self.plugin_manager.handle_event(event)
        except Exception as e:
            logger.error(f"Error handling event for plugins: {e}", exc_info=True)
    
    def _handle_event_for_hooks(self, event: ClockmanEvent) -> None:
        """Handle events for hook execution."""
        try:
            self.hook_manager.execute_hooks(event)
        except Exception as e:
            logger.error(f"Error handling event for hooks: {e}", exc_info=True)
    
    # Webhook management methods
    
    def add_webhook(self, webhook_config: WebhookConfig) -> UUID:
        """Add a webhook configuration."""
        webhook_id = self.webhook_manager.add_webhook(webhook_config)
        self.config_manager.add_webhook_config(webhook_config)
        return webhook_id
    
    def remove_webhook(self, webhook_id: UUID) -> bool:
        """Remove a webhook configuration."""
        success = self.webhook_manager.remove_webhook(webhook_id)
        if success:
            self.config_manager.remove_webhook_config(webhook_id)
        return success
    
    def get_webhook(self, webhook_id: UUID) -> Optional[WebhookConfig]:
        """Get a webhook configuration."""
        return self.webhook_manager.get_webhook(webhook_id)
    
    def get_webhook_by_name(self, name: str) -> Optional[WebhookConfig]:
        """Get a webhook configuration by name."""
        return self.webhook_manager.get_webhook_by_name(name)
    
    def list_webhooks(self) -> List[WebhookConfig]:
        """List all webhook configurations."""
        return self.webhook_manager.list_webhooks()
    
    def enable_webhook(self, webhook_id: UUID) -> bool:
        """Enable a webhook."""
        success = self.webhook_manager.enable_webhook(webhook_id)
        if success:
            self.config_manager.update_webhook_config(webhook_id, status="active")
        return success
    
    def disable_webhook(self, webhook_id: UUID) -> bool:
        """Disable a webhook."""
        success = self.webhook_manager.disable_webhook(webhook_id)
        if success:
            self.config_manager.update_webhook_config(webhook_id, status="disabled")
        return success
    
    def test_webhook(self, webhook_id: UUID):
        """Send a test event to a webhook."""
        return self.webhook_manager.test_webhook(webhook_id)
    
    # Plugin management methods
    
    def add_plugin_directory(self, directory: Path) -> None:
        """Add a plugin directory."""
        self.plugin_manager.add_plugin_directory(directory)
        self.config_manager.add_plugin_directory(directory)
    
    def load_plugin(
        self,
        plugin_name: str,
        plugin_file: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Load a plugin."""
        success = self.plugin_manager.load_plugin(plugin_name, plugin_file, config)
        if success:
            # Update configuration
            from .config import PluginConfigEntry
            plugin_config = PluginConfigEntry(
                name=plugin_name,
                enabled=True,
                file_path=str(plugin_file) if plugin_file else None,
                config=config or {},
            )
            self.config_manager.add_plugin_config(plugin_config)
        return success
    
    def load_plugin_from_module(
        self,
        module_name: str,
        plugin_name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Load a plugin from a module."""
        success = self.plugin_manager.load_plugin_from_module(module_name, plugin_name, config)
        if success:
            # Update configuration
            from .config import PluginConfigEntry
            plugin_config = PluginConfigEntry(
                name=plugin_name or module_name,
                enabled=True,
                module=module_name,
                config=config or {},
            )
            self.config_manager.add_plugin_config(plugin_config)
        return success
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin."""
        success = self.plugin_manager.unload_plugin(plugin_name)
        if success:
            self.config_manager.remove_plugin_config(plugin_name)
        return success
    
    def list_plugins(self):
        """List all loaded plugins."""
        return self.plugin_manager.list_plugins()
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin."""
        success = self.plugin_manager.enable_plugin(plugin_name)
        if success:
            self.config_manager.update_plugin_config(plugin_name, enabled=True)
        return success
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin."""
        success = self.plugin_manager.disable_plugin(plugin_name)
        if success:
            self.config_manager.update_plugin_config(plugin_name, enabled=False)
        return success
    
    def get_plugin_status(self, plugin_name: str):
        """Get the status of a plugin."""
        return self.plugin_manager.get_plugin_status(plugin_name)
    
    def discover_plugins(self):
        """Discover available plugins."""
        return self.plugin_manager.discover_plugins()
    
    # Statistics and monitoring
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive integration statistics."""
        return {
            "enabled": self.config.enabled,
            "initialized": self._initialized,
            "event_manager": self.event_manager.get_statistics(),
            "webhook_manager": self.webhook_manager.get_statistics(),
            "plugin_manager": self.plugin_manager.get_statistics(),
            "hook_manager": self.hook_manager.get_statistics(),
        }
    
    def process_webhook_retries(self):
        """Process pending webhook retries."""
        return self.webhook_manager.process_retries()
    
    def get_webhook_delivery_history(self, webhook_id: Optional[UUID] = None, limit: int = 100):
        """Get webhook delivery history."""
        return self.webhook_manager.get_delivery_history(webhook_id, limit)
    
    def clear_webhook_history(self) -> int:
        """Clear webhook delivery history."""
        return self.webhook_manager.clear_delivery_history()
    
    # Hook management methods
    
    def register_hook(self, callback, name: str, **kwargs) -> UUID:
        """Register a new integration hook."""
        return self.hook_manager.register_hook(callback, name, **kwargs)
    
    def unregister_hook(self, hook_id: UUID) -> bool:
        """Unregister an integration hook."""
        return self.hook_manager.unregister_hook(hook_id)
    
    def list_hooks(self, owner: Optional[str] = None):
        """List registered hooks."""
        return self.hook_manager.list_hooks(owner)
    
    def enable_hook(self, hook_id: UUID) -> bool:
        """Enable a hook."""
        return self.hook_manager.enable_hook(hook_id)
    
    def disable_hook(self, hook_id: UUID) -> bool:
        """Disable a hook."""
        return self.hook_manager.disable_hook(hook_id)