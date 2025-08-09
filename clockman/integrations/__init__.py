"""
Clockman integrations package.

This package provides webhook and plugin integration capabilities for Clockman.
"""

from .events.event_manager import EventManager
from .events.events import ClockmanEvent, EventType
from .plugins.base import BasePlugin
from .webhooks.webhook_manager import WebhookManager

__all__ = ["EventManager", "ClockmanEvent", "EventType", "BasePlugin", "WebhookManager"]