"""
Webhook models and data structures for Clockman integrations.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, validator

from ..events.events import EventType


class WebhookStatus(str, Enum):
    """Status of a webhook configuration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISABLED = "disabled"


class DeliveryStatus(str, Enum):
    """Status of a webhook delivery attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    TIMEOUT = "timeout"
    DISABLED = "disabled"


class RetryPolicy(BaseModel):
    """Configuration for webhook retry behavior."""
    
    max_attempts: int = Field(default=3, ge=1, le=10, description="Maximum number of retry attempts")
    base_delay: float = Field(default=1.0, ge=0.1, description="Base delay in seconds between retries")
    max_delay: float = Field(default=300.0, ge=1.0, description="Maximum delay in seconds")
    exponential_backoff: bool = Field(default=True, description="Use exponential backoff")
    
    @validator("max_delay")
    def max_delay_must_be_greater_than_base(cls, v, values):
        if "base_delay" in values and v <= values["base_delay"]:
            raise ValueError("max_delay must be greater than base_delay")
        return v


class WebhookConfig(BaseModel):
    """Configuration for a webhook integration."""
    
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the webhook")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name for the webhook")
    url: HttpUrl = Field(..., description="The URL to POST webhook data to")
    description: Optional[str] = Field(None, max_length=500, description="Optional description of the webhook")
    
    # Event filtering
    event_types: List[EventType] = Field(default_factory=list, description="Event types to trigger this webhook")
    event_filter: Optional[Dict[str, Any]] = Field(None, description="Additional filters for events")
    
    # HTTP configuration
    headers: Dict[str, str] = Field(default_factory=dict, description="Custom HTTP headers to include")
    timeout: float = Field(default=30.0, ge=1.0, le=300.0, description="Request timeout in seconds")
    verify_ssl: bool = Field(default=True, description="Whether to verify SSL certificates")
    
    # Retry configuration
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy, description="Retry policy for failed deliveries")
    
    # Status and metadata
    status: WebhookStatus = Field(default=WebhookStatus.ACTIVE, description="Current status of the webhook")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When the webhook was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When the webhook was last updated")
    last_delivery_at: Optional[datetime] = Field(None, description="When the last delivery attempt was made")
    
    # Statistics
    total_deliveries: int = Field(default=0, ge=0, description="Total number of delivery attempts")
    successful_deliveries: int = Field(default=0, ge=0, description="Number of successful deliveries")
    failed_deliveries: int = Field(default=0, ge=0, description="Number of failed deliveries")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: str,
        }
    
    def is_active(self) -> bool:
        """Check if the webhook is active and can receive events."""
        return self.status == WebhookStatus.ACTIVE
    
    def matches_event(self, event_type: EventType, event_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if this webhook should be triggered for the given event.
        
        Args:
            event_type: The type of event
            event_data: Optional event data for filtering
            
        Returns:
            True if the webhook should be triggered
        """
        if not self.is_active():
            return False
        
        # Check event type filter
        if self.event_types and event_type not in self.event_types:
            return False
        
        # Check additional event filters if provided
        if self.event_filter and event_data:
            return self._evaluate_filter(self.event_filter, event_data)
        
        return True
    
    def _evaluate_filter(self, filter_config: Dict[str, Any], event_data: Dict[str, Any]) -> bool:
        """
        Evaluate a filter configuration against event data.
        
        Supports:
        - Simple equality: {"task_name": "example"}
        - Lists (any match): {"tags": ["work", "urgent"]}  
        - Ranges: {"duration_seconds": {"min": 60, "max": 3600}}
        - Patterns: {"task_name": {"pattern": ".*test.*"}}
        - Logical operators: {"$and": [...], "$or": [...], "$not": {...}}
        
        Args:
            filter_config: The filter configuration
            event_data: The event data to filter against
            
        Returns:
            True if the filter matches
        """
        import re
        
        for key, expected_value in filter_config.items():
            # Handle logical operators
            if key == "$and":
                if not isinstance(expected_value, list):
                    return False
                return all(self._evaluate_filter(condition, event_data) for condition in expected_value)
            
            elif key == "$or":
                if not isinstance(expected_value, list):
                    return False
                return any(self._evaluate_filter(condition, event_data) for condition in expected_value)
            
            elif key == "$not":
                if not isinstance(expected_value, dict):
                    return False
                return not self._evaluate_filter(expected_value, event_data)
            
            # Regular field checks
            elif key not in event_data:
                return False
            
            actual_value = event_data[key]
            
            # Handle different filter types
            if isinstance(expected_value, dict):
                # Range filter
                if "min" in expected_value or "max" in expected_value:
                    try:
                        actual_num = float(actual_value)
                        if "min" in expected_value and actual_num < expected_value["min"]:
                            return False
                        if "max" in expected_value and actual_num > expected_value["max"]:
                            return False
                    except (ValueError, TypeError):
                        return False
                
                # Pattern filter
                elif "pattern" in expected_value:
                    try:
                        pattern = expected_value["pattern"]
                        flags = re.IGNORECASE if expected_value.get("ignore_case", True) else 0
                        if not re.search(pattern, str(actual_value), flags):
                            return False
                    except re.error:
                        return False
                
                # Contains filter
                elif "contains" in expected_value:
                    if expected_value["contains"] not in str(actual_value):
                        return False
                
                else:
                    # Nested object filter - not implemented for now
                    return False
            
            elif isinstance(expected_value, list):
                # List filter - check if actual value is in the list
                if actual_value not in expected_value:
                    return False
            
            else:
                # Simple equality
                if actual_value != expected_value:
                    return False
        
        return True
    
    def update_stats(self, success: bool) -> None:
        """Update delivery statistics."""
        self.total_deliveries += 1
        self.last_delivery_at = datetime.utcnow()
        
        if success:
            self.successful_deliveries += 1
        else:
            self.failed_deliveries += 1
        
        self.updated_at = datetime.utcnow()
    
    def get_success_rate(self) -> float:
        """Calculate the success rate of webhook deliveries."""
        if self.total_deliveries == 0:
            return 0.0
        return self.successful_deliveries / self.total_deliveries


class WebhookDelivery(BaseModel):
    """Record of a webhook delivery attempt."""
    
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the delivery")
    webhook_id: UUID = Field(..., description="ID of the webhook configuration")
    event_id: str = Field(..., description="ID of the event that triggered this delivery")
    event_type: EventType = Field(..., description="Type of the event")
    
    # Delivery details
    status: DeliveryStatus = Field(..., description="Status of the delivery")
    attempt_number: int = Field(default=1, ge=1, description="Which attempt this is (1-based)")
    url: str = Field(..., description="The URL the webhook was delivered to")
    
    # Request/response details
    request_headers: Dict[str, str] = Field(default_factory=dict, description="Headers sent with the request")
    request_body: str = Field(..., description="Body of the request")
    response_status: Optional[int] = Field(None, description="HTTP response status code")
    response_headers: Optional[Dict[str, str]] = Field(None, description="Response headers received")
    response_body: Optional[str] = Field(None, description="Response body received")
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When the delivery was initiated")
    completed_at: Optional[datetime] = Field(None, description="When the delivery completed")
    duration_ms: Optional[float] = Field(None, description="Duration of the request in milliseconds")
    
    # Error information
    error_message: Optional[str] = Field(None, description="Error message if delivery failed")
    next_retry_at: Optional[datetime] = Field(None, description="When the next retry will be attempted")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: str,
        }
    
    def is_successful(self) -> bool:
        """Check if the delivery was successful."""
        return self.status == DeliveryStatus.SUCCESS
    
    def calculate_next_retry(self, retry_policy: RetryPolicy) -> Optional[datetime]:
        """
        Calculate when the next retry should be attempted.
        
        Args:
            retry_policy: The retry policy to use
            
        Returns:
            Datetime for next retry, or None if no more retries
        """
        if self.attempt_number >= retry_policy.max_attempts:
            return None
        
        if retry_policy.exponential_backoff:
            delay = min(
                retry_policy.base_delay * (2 ** (self.attempt_number - 1)),
                retry_policy.max_delay
            )
        else:
            delay = retry_policy.base_delay
        
        return datetime.utcnow() + timedelta(seconds=delay)


class WebhookDeliveryResult(BaseModel):
    """Result of a webhook delivery operation."""
    
    delivery: WebhookDelivery = Field(..., description="The delivery record")
    success: bool = Field(..., description="Whether the delivery was successful")
    will_retry: bool = Field(default=False, description="Whether a retry will be attempted")
    next_retry_at: Optional[datetime] = Field(None, description="When the next retry will occur")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: str,
        }