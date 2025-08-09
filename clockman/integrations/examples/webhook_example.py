"""
Example webhook integration for Clockman.

This module demonstrates how to configure and use webhooks to integrate
Clockman with external services like Slack, Discord, or custom HTTP endpoints.
"""

import json
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from ..events.events import EventType
from ..webhooks.models import WebhookConfig, RetryPolicy


def create_slack_webhook(webhook_url: str, channel: str = "#general") -> WebhookConfig:
    """
    Create a webhook configuration for Slack integration.
    
    Args:
        webhook_url: The Slack webhook URL
        channel: The Slack channel to post to
        
    Returns:
        Configured webhook for Slack
    """
    return WebhookConfig(
        id=uuid4(),
        name="Slack Integration",
        url=webhook_url,
        description=f"Posts time tracking events to Slack channel {channel}",
        event_types=[
            EventType.SESSION_STARTED,
            EventType.SESSION_STOPPED,
            EventType.PROJECT_CREATED,
        ],
        headers={
            "Content-Type": "application/json",
        },
        timeout=15.0,
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay=2.0,
            max_delay=60.0,
            exponential_backoff=True,
        ),
    )


def create_discord_webhook(webhook_url: str) -> WebhookConfig:
    """
    Create a webhook configuration for Discord integration.
    
    Args:
        webhook_url: The Discord webhook URL
        
    Returns:
        Configured webhook for Discord
    """
    return WebhookConfig(
        id=uuid4(),
        name="Discord Integration",
        url=webhook_url,
        description="Posts time tracking events to Discord channel",
        event_types=[
            EventType.SESSION_STARTED,
            EventType.SESSION_STOPPED,
        ],
        headers={
            "Content-Type": "application/json",
        },
        timeout=10.0,
        retry_policy=RetryPolicy(
            max_attempts=2,
            base_delay=1.0,
            max_delay=30.0,
            exponential_backoff=True,
        ),
    )


def create_generic_webhook(
    name: str,
    url: str,
    description: str = "",
    event_types: List[EventType] = None,
    headers: Dict[str, str] = None,
) -> WebhookConfig:
    """
    Create a generic webhook configuration.
    
    Args:
        name: Name for the webhook
        url: The webhook URL
        description: Description of the webhook
        event_types: List of event types to subscribe to
        headers: Custom HTTP headers
        
    Returns:
        Configured webhook
    """
    if event_types is None:
        event_types = [
            EventType.SESSION_STARTED,
            EventType.SESSION_STOPPED,
            EventType.PROJECT_CREATED,
            EventType.PROJECT_UPDATED,
            EventType.PROJECT_DELETED,
        ]
    
    if headers is None:
        headers = {"Content-Type": "application/json"}
    
    return WebhookConfig(
        id=uuid4(),
        name=name,
        url=url,
        description=description,
        event_types=event_types,
        headers=headers,
        timeout=30.0,
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay=1.0,
            max_delay=120.0,
            exponential_backoff=True,
        ),
    )


def create_task_tracker_webhook(webhook_url: str) -> WebhookConfig:
    """
    Create a webhook configuration for external task tracking systems.
    
    This webhook focuses on session events and provides detailed timing information
    suitable for integration with project management tools.
    
    Args:
        webhook_url: The webhook URL for the task tracker
        
    Returns:
        Configured webhook for task tracking
    """
    return WebhookConfig(
        id=uuid4(),
        name="Task Tracker Integration",
        url=webhook_url,
        description="Integrates with external task tracking and project management systems",
        event_types=[
            EventType.SESSION_STARTED,
            EventType.SESSION_STOPPED,
            EventType.SESSION_UPDATED,
            EventType.SESSION_DELETED,
        ],
        event_filter={
            # Only send events for sessions longer than 1 minute
            # Note: This filtering would need to be implemented in the webhook manager
        },
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Clockman-TaskTracker/1.0",
        },
        timeout=20.0,
        retry_policy=RetryPolicy(
            max_attempts=5,
            base_delay=2.0,
            max_delay=300.0,
            exponential_backoff=True,
        ),
    )


def create_analytics_webhook(webhook_url: str) -> WebhookConfig:
    """
    Create a webhook configuration for analytics and reporting systems.
    
    This webhook sends all events and is suitable for comprehensive
    data analysis and reporting.
    
    Args:
        webhook_url: The webhook URL for the analytics system
        
    Returns:
        Configured webhook for analytics
    """
    return WebhookConfig(
        id=uuid4(),
        name="Analytics Integration",
        url=webhook_url,
        description="Sends comprehensive time tracking data to analytics systems",
        event_types=list(EventType),  # All event types
        headers={
            "Content-Type": "application/json",
            "X-Analytics-Source": "clockman",
        },
        timeout=45.0,
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay=5.0,
            max_delay=600.0,
            exponential_backoff=True,
        ),
    )


def save_webhook_config_examples(config_dir: Path) -> None:
    """
    Save example webhook configurations to JSON files.
    
    This function creates example configuration files that users can
    modify and use as templates for their own integrations.
    
    Args:
        config_dir: Directory to save the example configurations
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Create example configurations
    examples = {
        "slack_example.json": create_slack_webhook(
            "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
        ),
        "discord_example.json": create_discord_webhook(
            "https://discord.com/api/webhooks/YOUR/DISCORD/WEBHOOK"
        ),
        "generic_example.json": create_generic_webhook(
            name="Custom Integration",
            url="https://api.example.com/clockman/webhook",
            description="Example custom webhook integration"
        ),
        "task_tracker_example.json": create_task_tracker_webhook(
            "https://api.tasktracker.com/webhooks/clockman"
        ),
        "analytics_example.json": create_analytics_webhook(
            "https://analytics.company.com/api/webhooks/timetracking"
        ),
    }
    
    # Save each example to a file
    for filename, webhook_config in examples.items():
        config_file = config_dir / filename
        
        with open(config_file, 'w') as f:
            json.dump(
                webhook_config.model_dump(),
                f,
                indent=2,
                default=str,  # Handle UUID and other types
            )
        
        print(f"Saved example webhook configuration: {config_file}")


def load_webhook_config_from_file(config_file: Path) -> WebhookConfig:
    """
    Load a webhook configuration from a JSON file.
    
    Args:
        config_file: Path to the configuration file
        
    Returns:
        Loaded webhook configuration
        
    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        ValueError: If the configuration is invalid
    """
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        return WebhookConfig(**config_data)
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}")
    except Exception as e:
        raise ValueError(f"Invalid webhook configuration: {e}")


def create_webhook_from_template(
    template: str,
    url: str,
    **kwargs
) -> WebhookConfig:
    """
    Create a webhook from a predefined template.
    
    Args:
        template: Template name (slack, discord, generic, task_tracker, analytics)
        url: The webhook URL
        **kwargs: Additional parameters for the template
        
    Returns:
        Configured webhook based on the template
        
    Raises:
        ValueError: If the template is unknown
    """
    templates = {
        "slack": lambda url, **kw: create_slack_webhook(url, kw.get("channel", "#general")),
        "discord": create_discord_webhook,
        "generic": lambda url, **kw: create_generic_webhook(
            kw.get("name", "Generic Webhook"),
            url,
            kw.get("description", ""),
            kw.get("event_types"),
            kw.get("headers"),
        ),
        "task_tracker": create_task_tracker_webhook,
        "analytics": create_analytics_webhook,
    }
    
    if template not in templates:
        available = ", ".join(templates.keys())
        raise ValueError(f"Unknown template '{template}'. Available templates: {available}")
    
    return templates[template](url, **kwargs)


# Example usage and testing functions

def test_webhook_configuration() -> None:
    """Test webhook configuration creation and serialization."""
    print("Testing webhook configurations...")
    
    # Test each template
    templates = [
        ("slack", "https://hooks.slack.com/test"),
        ("discord", "https://discord.com/test"),
        ("generic", "https://api.example.com/webhook"),
        ("task_tracker", "https://tasktracker.com/webhook"),
        ("analytics", "https://analytics.com/webhook"),
    ]
    
    for template, url in templates:
        try:
            webhook = create_webhook_from_template(template, url)
            print(f"✓ {template}: {webhook.name}")
            
            # Test serialization
            json_data = webhook.model_dump()
            restored = WebhookConfig(**json_data)
            assert restored.name == webhook.name
            
        except Exception as e:
            print(f"✗ {template}: {e}")
    
    print("Webhook configuration tests completed.")


if __name__ == "__main__":
    # Run tests when executed directly
    test_webhook_configuration()
    
    # Create example configurations
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        save_webhook_config_examples(Path(temp_dir))
        print(f"Example configurations saved to: {temp_dir}")