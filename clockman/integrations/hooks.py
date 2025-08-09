"""
Integration hooks system for Clockman.

This module provides a flexible hook system that allows plugins and external
systems to register callbacks for various integration events.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Union
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum

from .events.events import ClockmanEvent, EventType

logger = logging.getLogger(__name__)


class HookPriority(int, Enum):
    """Priority levels for hook execution."""
    CRITICAL = 1
    HIGH = 10
    NORMAL = 50
    LOW = 100


class HookExecutionMode(str, Enum):
    """Execution modes for hooks."""
    SYNC = "sync"           # Execute synchronously
    ASYNC = "async"         # Execute asynchronously
    FIRE_AND_FORGET = "fire_and_forget"  # Execute asynchronously without waiting


@dataclass
class HookResult:
    """Result of a hook execution."""
    success: bool
    duration_ms: float
    error_message: Optional[str] = None
    return_value: Any = None


@dataclass
class Hook:
    """A registered hook callback."""
    id: UUID = field(default_factory=uuid4)
    name: str = field()
    callback: Callable = field()
    priority: int = field(default=HookPriority.NORMAL)
    execution_mode: HookExecutionMode = field(default=HookExecutionMode.SYNC)
    event_types: Optional[List[EventType]] = field(default=None)
    conditions: Optional[Dict[str, Any]] = field(default=None)
    enabled: bool = field(default=True)
    created_at: datetime = field(default_factory=datetime.utcnow)
    owner: Optional[str] = field(default=None)  # Plugin or system that registered the hook


class HookManager:
    """
    Manages registration and execution of integration hooks.
    
    The hook system allows plugins and external systems to register
    callbacks that are executed when certain events occur.
    """
    
    def __init__(self):
        """Initialize the hook manager."""
        self._hooks: Dict[UUID, Hook] = {}
        self._event_hooks: Dict[EventType, List[UUID]] = {}
        self._global_hooks: List[UUID] = []
        
        # Statistics
        self._hooks_executed = 0
        self._hook_errors = 0
        self._total_execution_time = 0.0
    
    def register_hook(
        self,
        callback: Callable,
        name: str,
        priority: int = HookPriority.NORMAL,
        execution_mode: HookExecutionMode = HookExecutionMode.SYNC,
        event_types: Optional[List[EventType]] = None,
        conditions: Optional[Dict[str, Any]] = None,
        owner: Optional[str] = None,
    ) -> UUID:
        """
        Register a new hook.
        
        Args:
            callback: The function to call when the hook is triggered
            name: Human-readable name for the hook
            priority: Execution priority (lower numbers execute first)
            execution_mode: How to execute the hook (sync/async/fire_and_forget)
            event_types: List of event types to trigger on (None = all events)
            conditions: Additional conditions for hook execution
            owner: Plugin or system that owns this hook
            
        Returns:
            UUID of the registered hook
        """
        hook = Hook(
            name=name,
            callback=callback,
            priority=priority,
            execution_mode=execution_mode,
            event_types=event_types,
            conditions=conditions,
            owner=owner,
        )
        
        self._hooks[hook.id] = hook
        
        if event_types:
            # Register for specific events
            for event_type in event_types:
                if event_type not in self._event_hooks:
                    self._event_hooks[event_type] = []
                self._event_hooks[event_type].append(hook.id)
                # Sort by priority
                self._event_hooks[event_type].sort(key=lambda h_id: self._hooks[h_id].priority)
        else:
            # Global hook - applies to all events
            self._global_hooks.append(hook.id)
            self._global_hooks.sort(key=lambda h_id: self._hooks[h_id].priority)
        
        logger.info(f"Registered hook '{name}' (ID: {hook.id}) for owner '{owner}'")
        return hook.id
    
    def unregister_hook(self, hook_id: UUID) -> bool:
        """
        Unregister a hook.
        
        Args:
            hook_id: ID of the hook to unregister
            
        Returns:
            True if the hook was unregistered
        """
        if hook_id not in self._hooks:
            return False
        
        hook = self._hooks.pop(hook_id)
        
        # Remove from event hooks
        for event_type_hooks in self._event_hooks.values():
            if hook_id in event_type_hooks:
                event_type_hooks.remove(hook_id)
        
        # Remove from global hooks
        if hook_id in self._global_hooks:
            self._global_hooks.remove(hook_id)
        
        logger.info(f"Unregistered hook '{hook.name}' (ID: {hook_id})")
        return True
    
    def unregister_hooks_by_owner(self, owner: str) -> int:
        """
        Unregister all hooks owned by a specific owner.
        
        Args:
            owner: The owner identifier
            
        Returns:
            Number of hooks unregistered
        """
        hooks_to_remove = [
            hook_id for hook_id, hook in self._hooks.items()
            if hook.owner == owner
        ]
        
        count = 0
        for hook_id in hooks_to_remove:
            if self.unregister_hook(hook_id):
                count += 1
        
        logger.info(f"Unregistered {count} hooks for owner '{owner}'")
        return count
    
    def enable_hook(self, hook_id: UUID) -> bool:
        """Enable a hook."""
        if hook_id in self._hooks:
            self._hooks[hook_id].enabled = True
            return True
        return False
    
    def disable_hook(self, hook_id: UUID) -> bool:
        """Disable a hook."""
        if hook_id in self._hooks:
            self._hooks[hook_id].enabled = False
            return True
        return False
    
    def execute_hooks(self, event: ClockmanEvent) -> Dict[UUID, HookResult]:
        """
        Execute all applicable hooks for an event.
        
        Args:
            event: The event that triggered the hooks
            
        Returns:
            Dictionary mapping hook IDs to their execution results
        """
        start_time = datetime.utcnow()
        results = {}
        
        # Collect applicable hooks
        applicable_hooks = []
        
        # Add global hooks
        applicable_hooks.extend(self._global_hooks)
        
        # Add event-specific hooks
        if event.event_type in self._event_hooks:
            applicable_hooks.extend(self._event_hooks[event.event_type])
        
        # Remove duplicates and sort by priority
        unique_hooks = list(dict.fromkeys(applicable_hooks))  # Preserves order
        hooks_to_execute = [
            self._hooks[hook_id] for hook_id in unique_hooks 
            if hook_id in self._hooks and self._hooks[hook_id].enabled
        ]
        
        # Filter by conditions
        filtered_hooks = []
        for hook in hooks_to_execute:
            if self._matches_conditions(hook, event):
                filtered_hooks.append(hook)
        
        if not filtered_hooks:
            return results
        
        logger.debug(f"Executing {len(filtered_hooks)} hooks for event {event.event_type.value}")
        
        # Execute hooks
        for hook in filtered_hooks:
            result = self._execute_hook(hook, event)
            results[hook.id] = result
            
            if result.success:
                logger.debug(f"Hook '{hook.name}' executed successfully in {result.duration_ms:.1f}ms")
            else:
                logger.error(f"Hook '{hook.name}' failed: {result.error_message}")
                self._hook_errors += 1
        
        total_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        self._total_execution_time += total_time
        
        return results
    
    def _matches_conditions(self, hook: Hook, event: ClockmanEvent) -> bool:
        """
        Check if a hook's conditions match the event.
        
        Args:
            hook: The hook to check
            event: The event to match against
            
        Returns:
            True if conditions match or no conditions are specified
        """
        if not hook.conditions:
            return True
        
        # Use the same filtering logic as webhooks
        try:
            from .webhooks.models import WebhookConfig
            # Create a temporary webhook config to use its filtering logic
            temp_webhook = WebhookConfig(
                name="temp",
                url="http://example.com",
                event_filter=hook.conditions
            )
            return temp_webhook._evaluate_filter(hook.conditions, event.data or {})
        except Exception as e:
            logger.warning(f"Error evaluating hook conditions for '{hook.name}': {e}")
            return False
    
    def _execute_hook(self, hook: Hook, event: ClockmanEvent) -> HookResult:
        """
        Execute a single hook.
        
        Args:
            hook: The hook to execute
            event: The event that triggered the hook
            
        Returns:
            Result of the hook execution
        """
        start_time = datetime.utcnow()
        
        try:
            self._hooks_executed += 1
            
            if hook.execution_mode == HookExecutionMode.SYNC:
                # Execute synchronously
                return_value = hook.callback(event)
                
            elif hook.execution_mode == HookExecutionMode.ASYNC:
                # Execute asynchronously (simplified - in production use proper async/await)
                import threading
                
                def async_wrapper():
                    try:
                        hook.callback(event)
                    except Exception as e:
                        logger.error(f"Async hook '{hook.name}' failed: {e}")
                
                thread = threading.Thread(target=async_wrapper)
                thread.daemon = True
                thread.start()
                return_value = None
                
            elif hook.execution_mode == HookExecutionMode.FIRE_AND_FORGET:
                # Fire and forget
                import threading
                
                def fire_and_forget_wrapper():
                    try:
                        hook.callback(event)
                    except Exception:
                        pass  # Ignore errors in fire-and-forget mode
                
                thread = threading.Thread(target=fire_and_forget_wrapper)
                thread.daemon = True
                thread.start()
                return_value = None
            
            else:
                raise ValueError(f"Unknown execution mode: {hook.execution_mode}")
            
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            return HookResult(
                success=True,
                duration_ms=duration_ms,
                return_value=return_value
            )
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            return HookResult(
                success=False,
                duration_ms=duration_ms,
                error_message=str(e)
            )
    
    def get_hook(self, hook_id: UUID) -> Optional[Hook]:
        """Get a hook by ID."""
        return self._hooks.get(hook_id)
    
    def list_hooks(self, owner: Optional[str] = None) -> List[Hook]:
        """
        List registered hooks.
        
        Args:
            owner: Optional owner filter
            
        Returns:
            List of hooks
        """
        hooks = list(self._hooks.values())
        
        if owner:
            hooks = [hook for hook in hooks if hook.owner == owner]
        
        return sorted(hooks, key=lambda h: (h.priority, h.name))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get hook execution statistics."""
        return {
            "total_hooks": len(self._hooks),
            "enabled_hooks": sum(1 for h in self._hooks.values() if h.enabled),
            "hooks_executed": self._hooks_executed,
            "hook_errors": self._hook_errors,
            "total_execution_time_ms": self._total_execution_time,
            "average_execution_time_ms": (
                self._total_execution_time / self._hooks_executed 
                if self._hooks_executed > 0 else 0.0
            ),
            "event_subscriptions": {
                event_type.value: len(hook_ids) 
                for event_type, hook_ids in self._event_hooks.items()
            },
            "global_hooks": len(self._global_hooks),
        }
    
    def clear_statistics(self):
        """Clear execution statistics."""
        self._hooks_executed = 0
        self._hook_errors = 0
        self._total_execution_time = 0.0


# Global hook manager instance
_hook_manager: Optional[HookManager] = None


def get_hook_manager() -> HookManager:
    """Get the global hook manager instance."""
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = HookManager()
    return _hook_manager


# Convenience functions for common hook patterns

def on_session_start(callback: Callable[[ClockmanEvent], Any], name: str, owner: str = "user") -> UUID:
    """Register a hook for session start events."""
    return get_hook_manager().register_hook(
        callback=callback,
        name=name,
        event_types=[EventType.SESSION_STARTED],
        owner=owner
    )


def on_session_stop(callback: Callable[[ClockmanEvent], Any], name: str, owner: str = "user") -> UUID:
    """Register a hook for session stop events."""
    return get_hook_manager().register_hook(
        callback=callback,
        name=name,
        event_types=[EventType.SESSION_STOPPED],
        owner=owner
    )


def on_project_created(callback: Callable[[ClockmanEvent], Any], name: str, owner: str = "user") -> UUID:
    """Register a hook for project creation events."""
    return get_hook_manager().register_hook(
        callback=callback,
        name=name,
        event_types=[EventType.PROJECT_CREATED],
        owner=owner
    )


def on_all_events(
    callback: Callable[[ClockmanEvent], Any], 
    name: str, 
    priority: int = HookPriority.NORMAL,
    owner: str = "user"
) -> UUID:
    """Register a hook for all events."""
    return get_hook_manager().register_hook(
        callback=callback,
        name=name,
        priority=priority,
        owner=owner
    )