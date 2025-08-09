"""
Webhook management system for Clockman integrations.

This module provides HTTP-based webhook functionality for external system integration.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..events.events import ClockmanEvent, EventType
from .models import (
    DeliveryStatus,
    WebhookConfig,
    WebhookDelivery,
    WebhookDeliveryResult,
    WebhookStatus,
)

logger = logging.getLogger(__name__)


class WebhookManager:
    """
    Manages webhook configurations and handles delivery of events to external endpoints.
    
    This class provides comprehensive webhook functionality including:
    - Configuration management
    - Event delivery with retry logic
    - Delivery tracking and statistics
    - Error handling and status management
    """
    
    def __init__(self, max_concurrent_deliveries: int = 10):
        """
        Initialize the webhook manager.
        
        Args:
            max_concurrent_deliveries: Maximum number of concurrent webhook deliveries
        """
        self._webhooks: Dict[UUID, WebhookConfig] = {}
        self._pending_deliveries: List[WebhookDelivery] = []
        self._delivery_history: List[WebhookDelivery] = []
        self._max_concurrent_deliveries = max_concurrent_deliveries
        
        # HTTP client configuration
        self._http_client = httpx.Client(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=max_concurrent_deliveries),
        )
        
        # Statistics
        self._total_webhooks_created = 0
        self._total_deliveries_attempted = 0
        self._total_deliveries_successful = 0
        self._total_deliveries_failed = 0
    
    def add_webhook(self, webhook_config: WebhookConfig) -> UUID:
        """
        Add a new webhook configuration.
        
        Args:
            webhook_config: The webhook configuration to add
            
        Returns:
            The UUID of the added webhook
            
        Raises:
            ValueError: If a webhook with the same name already exists
        """
        # Check for duplicate names
        for existing_webhook in self._webhooks.values():
            if existing_webhook.name == webhook_config.name:
                raise ValueError(f"Webhook with name '{webhook_config.name}' already exists")
        
        self._webhooks[webhook_config.id] = webhook_config
        self._total_webhooks_created += 1
        
        logger.info(f"Added webhook '{webhook_config.name}' (ID: {webhook_config.id})")
        return webhook_config.id
    
    def remove_webhook(self, webhook_id: UUID) -> bool:
        """
        Remove a webhook configuration.
        
        Args:
            webhook_id: The UUID of the webhook to remove
            
        Returns:
            True if the webhook was removed, False if it didn't exist
        """
        if webhook_id in self._webhooks:
            webhook = self._webhooks.pop(webhook_id)
            logger.info(f"Removed webhook '{webhook.name}' (ID: {webhook_id})")
            return True
        
        logger.warning(f"Attempted to remove non-existent webhook: {webhook_id}")
        return False
    
    def get_webhook(self, webhook_id: UUID) -> Optional[WebhookConfig]:
        """
        Get a webhook configuration by ID.
        
        Args:
            webhook_id: The UUID of the webhook
            
        Returns:
            The webhook configuration, or None if not found
        """
        return self._webhooks.get(webhook_id)
    
    def get_webhook_by_name(self, name: str) -> Optional[WebhookConfig]:
        """
        Get a webhook configuration by name.
        
        Args:
            name: The name of the webhook
            
        Returns:
            The webhook configuration, or None if not found
        """
        for webhook in self._webhooks.values():
            if webhook.name == name:
                return webhook
        return None
    
    def list_webhooks(self) -> List[WebhookConfig]:
        """
        Get all webhook configurations.
        
        Returns:
            List of all webhook configurations
        """
        return list(self._webhooks.values())
    
    def update_webhook(self, webhook_id: UUID, **updates: Any) -> Optional[WebhookConfig]:
        """
        Update a webhook configuration.
        
        Args:
            webhook_id: The UUID of the webhook to update
            **updates: Fields to update
            
        Returns:
            The updated webhook configuration, or None if not found
        """
        if webhook_id not in self._webhooks:
            return None
        
        webhook = self._webhooks[webhook_id]
        
        # Update fields
        for field, value in updates.items():
            if hasattr(webhook, field):
                setattr(webhook, field, value)
        
        webhook.updated_at = datetime.utcnow()
        logger.info(f"Updated webhook '{webhook.name}' (ID: {webhook_id})")
        
        return webhook
    
    def enable_webhook(self, webhook_id: UUID) -> bool:
        """
        Enable a webhook.
        
        Args:
            webhook_id: The UUID of the webhook to enable
            
        Returns:
            True if the webhook was enabled, False if it didn't exist
        """
        if webhook_id in self._webhooks:
            self._webhooks[webhook_id].status = WebhookStatus.ACTIVE
            logger.info(f"Enabled webhook: {webhook_id}")
            return True
        return False
    
    def disable_webhook(self, webhook_id: UUID) -> bool:
        """
        Disable a webhook.
        
        Args:
            webhook_id: The UUID of the webhook to disable
            
        Returns:
            True if the webhook was disabled, False if it didn't exist
        """
        if webhook_id in self._webhooks:
            self._webhooks[webhook_id].status = WebhookStatus.DISABLED
            logger.info(f"Disabled webhook: {webhook_id}")
            return True
        return False
    
    def handle_event(self, event: ClockmanEvent) -> List[WebhookDeliveryResult]:
        """
        Handle an incoming event by delivering it to matching webhooks.
        
        Args:
            event: The event to handle
            
        Returns:
            List of delivery results
        """
        results = []
        
        # Find matching webhooks
        matching_webhooks = []
        for webhook in self._webhooks.values():
            if webhook.matches_event(event.event_type, event.data):
                matching_webhooks.append(webhook)
        
        if not matching_webhooks:
            logger.debug(f"No webhooks match event: {event.event_type.value}")
            return results
        
        logger.info(f"Delivering event {event.event_type.value} to {len(matching_webhooks)} webhooks")
        
        # Deliver to each matching webhook
        for webhook in matching_webhooks:
            try:
                result = self._deliver_webhook(webhook, event)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to deliver webhook '{webhook.name}': {e}", exc_info=True)
                # Create a failed delivery result
                delivery = WebhookDelivery(
                    webhook_id=webhook.id,
                    event_id=event.event_id,
                    event_type=event.event_type,
                    status=DeliveryStatus.FAILED,
                    url=str(webhook.url),
                    request_body=json.dumps(event.to_dict()),
                    error_message=str(e),
                    completed_at=datetime.utcnow(),
                )
                results.append(WebhookDeliveryResult(
                    delivery=delivery,
                    success=False,
                    will_retry=False,
                ))
        
        return results
    
    def _deliver_webhook(self, webhook: WebhookConfig, event: ClockmanEvent) -> WebhookDeliveryResult:
        """
        Deliver an event to a specific webhook.
        
        Args:
            webhook: The webhook configuration
            event: The event to deliver
            
        Returns:
            The delivery result
        """
        # Create delivery record
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_id=event.event_id,
            event_type=event.event_type,
            url=str(webhook.url),
            request_body=json.dumps(event.to_dict(), indent=2),
        )
        
        # Prepare request
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Clockman-Webhook/1.0",
            "X-Clockman-Event": event.event_type.value,
            "X-Clockman-Event-ID": event.event_id,
            **webhook.headers,
        }
        delivery.request_headers = headers
        
        try:
            # Make HTTP request
            start_time = datetime.utcnow()
            
            response = self._http_client.post(
                str(webhook.url),
                json=event.to_dict(),
                headers=headers,
                timeout=webhook.timeout,
            )
            
            end_time = datetime.utcnow()
            delivery.duration_ms = (end_time - start_time).total_seconds() * 1000
            delivery.completed_at = end_time
            
            # Record response details
            delivery.response_status = response.status_code
            delivery.response_headers = dict(response.headers)
            
            try:
                delivery.response_body = response.text
            except Exception:
                delivery.response_body = "<Unable to decode response body>"
            
            # Check if successful
            if 200 <= response.status_code < 300:
                delivery.status = DeliveryStatus.SUCCESS
                webhook.update_stats(success=True)
                self._total_deliveries_successful += 1
                
                logger.info(f"Successfully delivered webhook to {webhook.name}")
                
                return WebhookDeliveryResult(
                    delivery=delivery,
                    success=True,
                    will_retry=False,
                )
            else:
                delivery.status = DeliveryStatus.FAILED
                delivery.error_message = f"HTTP {response.status_code}: {response.reason_phrase}"
                
                webhook.update_stats(success=False)
                self._total_deliveries_failed += 1
                
                logger.warning(f"Webhook delivery failed for {webhook.name}: HTTP {response.status_code}")
                
                # Check if we should retry
                will_retry = delivery.attempt_number < webhook.retry_policy.max_attempts
                next_retry_at = None
                
                if will_retry:
                    next_retry_at = delivery.calculate_next_retry(webhook.retry_policy)
                    delivery.next_retry_at = next_retry_at
                    delivery.status = DeliveryStatus.RETRYING
                    self._pending_deliveries.append(delivery)
                
                return WebhookDeliveryResult(
                    delivery=delivery,
                    success=False,
                    will_retry=will_retry,
                    next_retry_at=next_retry_at,
                )
        
        except httpx.TimeoutException:
            delivery.status = DeliveryStatus.TIMEOUT
            delivery.error_message = f"Request timeout after {webhook.timeout}s"
            delivery.completed_at = datetime.utcnow()
            
            webhook.update_stats(success=False)
            self._total_deliveries_failed += 1
            
            logger.warning(f"Webhook delivery timeout for {webhook.name}")
            
            # Check if we should retry
            will_retry = delivery.attempt_number < webhook.retry_policy.max_attempts
            next_retry_at = None
            
            if will_retry:
                next_retry_at = delivery.calculate_next_retry(webhook.retry_policy)
                delivery.next_retry_at = next_retry_at
                delivery.status = DeliveryStatus.RETRYING
                self._pending_deliveries.append(delivery)
            
            return WebhookDeliveryResult(
                delivery=delivery,
                success=False,
                will_retry=will_retry,
                next_retry_at=next_retry_at,
            )
        
        except Exception as e:
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(e)
            delivery.completed_at = datetime.utcnow()
            
            webhook.update_stats(success=False)
            self._total_deliveries_failed += 1
            
            logger.error(f"Webhook delivery error for {webhook.name}: {e}", exc_info=True)
            
            # Check if we should retry
            will_retry = delivery.attempt_number < webhook.retry_policy.max_attempts
            next_retry_at = None
            
            if will_retry:
                next_retry_at = delivery.calculate_next_retry(webhook.retry_policy)
                delivery.next_retry_at = next_retry_at
                delivery.status = DeliveryStatus.RETRYING
                self._pending_deliveries.append(delivery)
            
            return WebhookDeliveryResult(
                delivery=delivery,
                success=False,
                will_retry=will_retry,
                next_retry_at=next_retry_at,
            )
        
        finally:
            self._total_deliveries_attempted += 1
            self._delivery_history.append(delivery)
            
            # Keep delivery history manageable
            if len(self._delivery_history) > 1000:
                self._delivery_history = self._delivery_history[-500:]
    
    def process_retries(self) -> List[WebhookDeliveryResult]:
        """
        Process pending webhook delivery retries.
        
        Returns:
            List of retry results
        """
        results = []
        now = datetime.utcnow()
        
        # Find deliveries ready for retry
        ready_for_retry = []
        still_pending = []
        
        for delivery in self._pending_deliveries:
            if delivery.next_retry_at and delivery.next_retry_at <= now:
                ready_for_retry.append(delivery)
            else:
                still_pending.append(delivery)
        
        self._pending_deliveries = still_pending
        
        if not ready_for_retry:
            return results
        
        logger.info(f"Processing {len(ready_for_retry)} webhook delivery retries")
        
        # Process retries
        for delivery in ready_for_retry:
            webhook = self._webhooks.get(delivery.webhook_id)
            if not webhook:
                logger.warning(f"Webhook {delivery.webhook_id} not found for retry")
                continue
            
            if not webhook.is_active():
                logger.info(f"Skipping retry for inactive webhook: {webhook.name}")
                continue
            
            try:
                # Create event from delivery data
                event_data = json.loads(delivery.request_body)
                event = ClockmanEvent.from_dict(event_data)
                
                # Update delivery for retry
                delivery.attempt_number += 1
                delivery.created_at = datetime.utcnow()
                
                # Attempt delivery
                result = self._deliver_webhook(webhook, event)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Failed to retry webhook delivery: {e}", exc_info=True)
        
        return results
    
    def get_delivery_history(self, webhook_id: Optional[UUID] = None, limit: int = 100) -> List[WebhookDelivery]:
        """
        Get delivery history.
        
        Args:
            webhook_id: Optional webhook ID to filter by
            limit: Maximum number of deliveries to return
            
        Returns:
            List of delivery records
        """
        deliveries = self._delivery_history
        
        if webhook_id:
            deliveries = [d for d in deliveries if d.webhook_id == webhook_id]
        
        # Sort by creation time (newest first) and limit
        deliveries = sorted(deliveries, key=lambda d: d.created_at, reverse=True)
        return deliveries[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get webhook manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        active_webhooks = sum(1 for w in self._webhooks.values() if w.is_active())
        
        return {
            "total_webhooks": len(self._webhooks),
            "active_webhooks": active_webhooks,
            "total_webhooks_created": self._total_webhooks_created,
            "total_deliveries_attempted": self._total_deliveries_attempted,
            "total_deliveries_successful": self._total_deliveries_successful,
            "total_deliveries_failed": self._total_deliveries_failed,
            "pending_retries": len(self._pending_deliveries),
            "delivery_history_size": len(self._delivery_history),
            "success_rate": (
                self._total_deliveries_successful / self._total_deliveries_attempted
                if self._total_deliveries_attempted > 0 else 0.0
            ),
        }
    
    def clear_delivery_history(self) -> int:
        """
        Clear the delivery history.
        
        Returns:
            Number of delivery records cleared
        """
        count = len(self._delivery_history)
        self._delivery_history.clear()
        logger.info(f"Cleared {count} delivery history records")
        return count
    
    def test_webhook(self, webhook_id: UUID) -> WebhookDeliveryResult:
        """
        Send a test event to a webhook.
        
        Args:
            webhook_id: The UUID of the webhook to test
            
        Returns:
            The delivery result
            
        Raises:
            ValueError: If the webhook doesn't exist
        """
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            raise ValueError(f"Webhook with ID {webhook_id} not found")
        
        # Create a test event
        from ..events.event_manager import EventManager
        event_manager = EventManager()
        
        test_event = event_manager.create_event(
            event_type=EventType.SYSTEM_STARTED,
            data={
                "test": True,
                "message": f"Test webhook delivery for '{webhook.name}'",
            },
            metadata={
                "source": "webhook_test",
            },
        )
        
        logger.info(f"Sending test event to webhook '{webhook.name}'")
        return self._deliver_webhook(webhook, test_event)
    
    def shutdown(self) -> None:
        """Shutdown the webhook manager and cleanup resources."""
        logger.info("Shutting down webhook manager...")
        self._http_client.close()
        self._pending_deliveries.clear()
        logger.info("Webhook manager shutdown complete")