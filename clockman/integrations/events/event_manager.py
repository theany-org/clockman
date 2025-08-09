"""
Event management system for Clockman integrations.

This module provides the core event dispatching and hook management functionality
for the integration system.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

from .events import ClockmanEvent, EventType

logger = logging.getLogger(__name__)


class EventHook:
    """
    Represents a single event hook with metadata.
    """
    
    def __init__(
        self,
        callback: Callable[[ClockmanEvent], Any],
        name: Optional[str] = None,
        priority: int = 100,
        async_callback: bool = False,
    ):
        """
        Initialize an event hook.
        
        Args:
            callback: The function to call when the event occurs
            name: Optional name for the hook (for identification)
            priority: Priority for execution order (lower numbers execute first)
            async_callback: Whether the callback is an async function
        """
        self.callback = callback
        self.name = name or f"hook_{uuid4().hex[:8]}"
        self.priority = priority
        self.async_callback = async_callback
        self.id = uuid4().hex
    
    def __call__(self, event: ClockmanEvent) -> Any:
        """Execute the hook."""
        return self.callback(event)
    
    def __repr__(self) -> str:
        return f"EventHook(name='{self.name}', priority={self.priority})"


class EventManager:
    """
    Manages event hooks and dispatches events to registered handlers.
    
    This class provides the core event system for Clockman integrations,
    allowing plugins and webhooks to register for and receive notifications
    about various system events.
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize the event manager.
        
        Args:
            max_workers: Maximum number of worker threads for async execution
        """
        self._hooks: Dict[EventType, List[EventHook]] = {}
        self._global_hooks: List[EventHook] = []
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._enabled = True
        
        # Statistics
        self._events_dispatched = 0
        self._hook_executions = 0
        self._failed_executions = 0
    
    def register_hook(
        self,
        event_type: EventType,
        callback: Callable[[ClockmanEvent], Any],
        name: Optional[str] = None,
        priority: int = 100,
        async_callback: bool = False,
    ) -> str:
        """
        Register a hook for a specific event type.
        
        Args:
            event_type: The type of event to listen for
            callback: The function to call when the event occurs
            name: Optional name for the hook
            priority: Priority for execution order (lower numbers execute first)
            async_callback: Whether the callback is an async function
            
        Returns:
            Hook ID for later removal
        """
        hook = EventHook(callback, name, priority, async_callback)
        
        if event_type not in self._hooks:
            self._hooks[event_type] = []
        
        self._hooks[event_type].append(hook)
        # Keep hooks sorted by priority
        self._hooks[event_type].sort(key=lambda h: h.priority)
        
        logger.debug(f"Registered hook '{hook.name}' for event '{event_type.value}'")
        return hook.id
    
    def register_global_hook(
        self,
        callback: Callable[[ClockmanEvent], Any],
        name: Optional[str] = None,
        priority: int = 100,
        async_callback: bool = False,
    ) -> str:
        """
        Register a hook that receives all events.
        
        Args:
            callback: The function to call for any event
            name: Optional name for the hook
            priority: Priority for execution order (lower numbers execute first)
            async_callback: Whether the callback is an async function
            
        Returns:
            Hook ID for later removal
        """
        hook = EventHook(callback, name, priority, async_callback)
        self._global_hooks.append(hook)
        # Keep hooks sorted by priority
        self._global_hooks.sort(key=lambda h: h.priority)
        
        logger.debug(f"Registered global hook '{hook.name}'")
        return hook.id
    
    def unregister_hook(self, hook_id: str) -> bool:
        """
        Remove a hook by its ID.
        
        Args:
            hook_id: The ID of the hook to remove
            
        Returns:
            True if the hook was found and removed, False otherwise
        """
        # Check specific event hooks
        for event_type, hooks in self._hooks.items():
            for i, hook in enumerate(hooks):
                if hook.id == hook_id:
                    removed_hook = hooks.pop(i)
                    logger.debug(f"Unregistered hook '{removed_hook.name}' for event '{event_type.value}'")
                    return True
        
        # Check global hooks
        for i, hook in enumerate(self._global_hooks):
            if hook.id == hook_id:
                removed_hook = self._global_hooks.pop(i)
                logger.debug(f"Unregistered global hook '{removed_hook.name}'")
                return True
        
        logger.warning(f"Hook with ID '{hook_id}' not found")
        return False
    
    def unregister_hooks_by_name(self, name: str) -> int:
        """
        Remove all hooks with a specific name.
        
        Args:
            name: The name of the hooks to remove
            
        Returns:
            Number of hooks removed
        """
        removed_count = 0
        
        # Remove from specific event hooks
        for event_type, hooks in self._hooks.items():
            original_length = len(hooks)
            self._hooks[event_type] = [h for h in hooks if h.name != name]
            removed_count += original_length - len(self._hooks[event_type])
        
        # Remove from global hooks
        original_length = len(self._global_hooks)
        self._global_hooks = [h for h in self._global_hooks if h.name != name]
        removed_count += original_length - len(self._global_hooks)
        
        if removed_count > 0:
            logger.debug(f"Removed {removed_count} hooks with name '{name}'")
        
        return removed_count
    
    def dispatch_event(self, event: ClockmanEvent, async_execution: bool = True) -> None:
        """
        Dispatch an event to all registered hooks.
        
        Args:
            event: The event to dispatch
            async_execution: Whether to execute hooks asynchronously
        """
        if not self._enabled:
            logger.debug(f"Event manager disabled, skipping event: {event.event_type.value}")
            return
        
        self._events_dispatched += 1
        logger.debug(f"Dispatching event: {event.event_type.value} (ID: {event.event_id})")
        
        # Get all hooks that should receive this event
        hooks_to_execute = []
        
        # Add specific event hooks
        if event.event_type in self._hooks:
            hooks_to_execute.extend(self._hooks[event.event_type])
        
        # Add global hooks
        hooks_to_execute.extend(self._global_hooks)
        
        # Sort all hooks by priority
        hooks_to_execute.sort(key=lambda h: h.priority)
        
        if not hooks_to_execute:
            logger.debug(f"No hooks registered for event: {event.event_type.value}")
            return
        
        logger.debug(f"Executing {len(hooks_to_execute)} hooks for event: {event.event_type.value}")
        
        # Execute hooks
        if async_execution:
            self._execute_hooks_async(hooks_to_execute, event)
        else:
            self._execute_hooks_sync(hooks_to_execute, event)
    
    def _execute_hooks_sync(self, hooks: List[EventHook], event: ClockmanEvent) -> None:
        """Execute hooks synchronously."""
        for hook in hooks:
            try:
                self._hook_executions += 1
                if hook.async_callback:
                    # Run async callback in thread pool
                    future = self._executor.submit(
                        lambda: asyncio.run(hook.callback(event))
                    )
                    future.result(timeout=30)  # 30 second timeout
                else:
                    hook.callback(event)
                logger.debug(f"Successfully executed hook: {hook.name}")
            except Exception as e:
                self._failed_executions += 1
                logger.error(f"Error executing hook '{hook.name}': {e}", exc_info=True)
    
    def _execute_hooks_async(self, hooks: List[EventHook], event: ClockmanEvent) -> None:
        """Execute hooks asynchronously."""
        for hook in hooks:
            try:
                self._hook_executions += 1
                if hook.async_callback:
                    # Submit async callback to thread pool
                    self._executor.submit(
                        lambda h=hook, e=event: asyncio.run(h.callback(e))
                    )
                else:
                    # Submit sync callback to thread pool
                    self._executor.submit(hook.callback, event)
                logger.debug(f"Submitted hook for async execution: {hook.name}")
            except Exception as e:
                self._failed_executions += 1
                logger.error(f"Error submitting hook '{hook.name}' for execution: {e}", exc_info=True)
    
    def create_event(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClockmanEvent:
        """
        Create a new event with the given type and data.
        
        Args:
            event_type: The type of event to create
            data: Event-specific data payload
            metadata: Additional metadata
            
        Returns:
            The created event
        """
        return ClockmanEvent(
            event_type=event_type,
            event_id=uuid4().hex,
            data=data or {},
            metadata=metadata or {},
        )
    
    def emit_event(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        async_execution: bool = True,
    ) -> ClockmanEvent:
        """
        Create and dispatch an event in one call.
        
        Args:
            event_type: The type of event to emit
            data: Event-specific data payload
            metadata: Additional metadata
            async_execution: Whether to execute hooks asynchronously
            
        Returns:
            The created and dispatched event
        """
        event = self.create_event(event_type, data, metadata)
        self.dispatch_event(event, async_execution)
        return event
    
    def get_registered_hooks(self) -> Dict[str, List[str]]:
        """
        Get information about all registered hooks.
        
        Returns:
            Dictionary mapping event types to lists of hook names
        """
        result = {}
        
        # Add specific event hooks
        for event_type, hooks in self._hooks.items():
            result[event_type.value] = [hook.name for hook in hooks]
        
        # Add global hooks
        if self._global_hooks:
            result["*"] = [hook.name for hook in self._global_hooks]
        
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get event manager statistics.
        
        Returns:
            Dictionary with statistics about event dispatching
        """
        return {
            "events_dispatched": self._events_dispatched,
            "hook_executions": self._hook_executions,
            "failed_executions": self._failed_executions,
            "registered_event_types": len(self._hooks),
            "total_hooks": sum(len(hooks) for hooks in self._hooks.values()) + len(self._global_hooks),
            "global_hooks": len(self._global_hooks),
            "enabled": self._enabled,
        }
    
    def enable(self) -> None:
        """Enable event dispatching."""
        self._enabled = True
        logger.info("Event manager enabled")
    
    def disable(self) -> None:
        """Disable event dispatching."""
        self._enabled = False
        logger.info("Event manager disabled")
    
    def is_enabled(self) -> bool:
        """Check if event dispatching is enabled."""
        return self._enabled
    
    def clear_hooks(self) -> None:
        """Remove all registered hooks."""
        total_hooks = sum(len(hooks) for hooks in self._hooks.values()) + len(self._global_hooks)
        self._hooks.clear()
        self._global_hooks.clear()
        logger.info(f"Cleared {total_hooks} hooks from event manager")
    
    def shutdown(self) -> None:
        """Shutdown the event manager and cleanup resources."""
        logger.info("Shutting down event manager...")
        self.disable()
        self._executor.shutdown(wait=True)
        self.clear_hooks()
        logger.info("Event manager shutdown complete")