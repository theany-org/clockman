"""
Advanced webhook configuration examples for Clockman.

This module demonstrates the enhanced webhook filtering and configuration
capabilities of the upgraded Clockman integration system.
"""

import json
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from ..events.events import EventType
from ..webhooks.models import WebhookConfig, RetryPolicy


def create_filtered_slack_webhook() -> WebhookConfig:
    """
    Create a Slack webhook with advanced filtering.
    
    This webhook only triggers for work-related sessions longer than 5 minutes
    from specific projects.
    """
    return WebhookConfig(
        id=uuid4(),
        name="Filtered Slack Notifications",
        url="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
        description="Sends notifications only for significant work sessions",
        event_types=[EventType.SESSION_STOPPED],
        event_filter={
            "$and": [
                # Only sessions longer than 5 minutes
                {"duration_seconds": {"min": 300}},
                # Only work-related tags
                {"$or": [
                    {"tags": ["work", "development", "coding", "meeting"]},
                    {"task_name": {"pattern": ".*(work|dev|code|meeting).*", "ignore_case": True}}
                ]},
                # Exclude break sessions
                {"$not": {"tags": ["break", "lunch", "personal"]}}
            ]
        },
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


def create_project_milestone_webhook() -> WebhookConfig:
    """
    Create a webhook that triggers on project milestones.
    
    This webhook sends notifications when certain project activities occur,
    like creation, updates, or when daily time thresholds are met.
    """
    return WebhookConfig(
        id=uuid4(),
        name="Project Milestone Tracker",
        url="https://api.projectmanager.com/webhooks/clockman",
        description="Tracks project milestones and significant activities",
        event_types=[
            EventType.PROJECT_CREATED,
            EventType.PROJECT_UPDATED,
            EventType.SESSION_STOPPED,
        ],
        event_filter={
            "$or": [
                # All project events
                {"event_type": "project_created"},
                {"event_type": "project_updated"},
                # Sessions that represent significant daily progress (>2 hours)
                {
                    "$and": [
                        {"event_type": "session_stopped"},
                        {"duration_seconds": {"min": 7200}},  # 2+ hours
                        {"project_id": {"pattern": ".*"}}  # Has project association
                    ]
                }
            ]
        },
        headers={
            "Content-Type": "application/json",
            "X-API-Key": "your-project-manager-api-key",
            "X-Source": "clockman-integration",
        },
        timeout=30.0,
        retry_policy=RetryPolicy(
            max_attempts=5,
            base_delay=3.0,
            max_delay=300.0,
            exponential_backoff=True,
        ),
    )


def create_time_tracking_analytics_webhook() -> WebhookConfig:
    """
    Create a webhook for comprehensive time tracking analytics.
    
    This webhook sends all session data to an analytics platform
    for detailed reporting and insights.
    """
    return WebhookConfig(
        id=uuid4(),
        name="Analytics Data Pipeline",
        url="https://analytics.company.com/api/v1/timetracking/events",
        description="Sends comprehensive time tracking data for analytics",
        event_types=[
            EventType.SESSION_STARTED,
            EventType.SESSION_STOPPED,
            EventType.SESSION_UPDATED,
        ],
        # No additional filtering - send all session events
        event_filter=None,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer your-analytics-api-token",
            "X-Analytics-Dataset": "timetracking",
            "X-Analytics-Version": "v2",
        },
        timeout=45.0,
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay=5.0,
            max_delay=600.0,
            exponential_backoff=True,
        ),
    )


def create_client_billing_webhook() -> WebhookConfig:
    """
    Create a webhook for client billing integration.
    
    This webhook filters for billable time and sends data to
    a billing system for invoice generation.
    """
    return WebhookConfig(
        id=uuid4(),
        name="Client Billing Integration",
        url="https://billing.yourcompany.com/api/webhooks/timetracking",
        description="Processes billable time for client invoicing",
        event_types=[EventType.SESSION_STOPPED],
        event_filter={
            "$and": [
                # Only billable sessions
                {"tags": ["billable", "client"]},
                # Minimum 15 minutes for billing
                {"duration_seconds": {"min": 900}},
                # Must have client or project association
                {"$or": [
                    {"project_id": {"pattern": ".*"}},
                    {"task_name": {"pattern": ".*client.*", "ignore_case": True}}
                ]},
                # Exclude internal work
                {"$not": {"tags": ["internal", "admin", "training"]}}
            ]
        },
        headers={
            "Content-Type": "application/json",
            "X-Billing-Source": "clockman",
            "X-Currency": "USD",
        },
        timeout=20.0,
        retry_policy=RetryPolicy(
            max_attempts=4,
            base_delay=2.0,
            max_delay=180.0,
            exponential_backoff=True,
        ),
    )


def create_team_collaboration_webhook() -> WebhookConfig:
    """
    Create a webhook for team collaboration tools.
    
    This webhook integrates with team chat or project management tools
    to share work status and progress updates.
    """
    return WebhookConfig(
        id=uuid4(),
        name="Team Collaboration Updates",
        url="https://api.slack.com/hooks/team-workspace",
        description="Shares work status with team collaboration tools",
        event_types=[
            EventType.SESSION_STARTED,
            EventType.SESSION_STOPPED,
        ],
        event_filter={
            "$and": [
                # Only team/shared work
                {"$or": [
                    {"tags": ["team", "shared", "collaboration", "meeting"]},
                    {"task_name": {"contains": "team"}},
                    {"task_name": {"contains": "meeting"}},
                ]},
                # Sessions longer than 10 minutes
                {"$or": [
                    {"event_type": "session_started"},  # Always announce starts
                    {
                        "$and": [
                            {"event_type": "session_stopped"},
                            {"duration_seconds": {"min": 600}}  # 10+ minutes
                        ]
                    }
                ]}
            ]
        },
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


def create_productivity_insights_webhook() -> WebhookConfig:
    """
    Create a webhook for productivity analysis.
    
    This webhook sends data to productivity analysis tools
    to help understand work patterns and efficiency.
    """
    return WebhookConfig(
        id=uuid4(),
        name="Productivity Insights",
        url="https://productivity.insights.com/api/data/ingest",
        description="Analyzes work patterns for productivity insights",
        event_types=[
            EventType.SESSION_STARTED,
            EventType.SESSION_STOPPED,
            EventType.SESSION_UPDATED,
        ],
        event_filter={
            # Include all work sessions, exclude personal time
            "$not": {"tags": ["personal", "break", "lunch", "entertainment"]}
        },
        headers={
            "Content-Type": "application/json",
            "X-API-Key": "your-productivity-api-key",
            "X-User-ID": "your-user-id",
        },
        timeout=25.0,
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay=2.0,
            max_delay=120.0,
            exponential_backoff=True,
        ),
    )


def create_compliance_audit_webhook() -> WebhookConfig:
    """
    Create a webhook for compliance and audit tracking.
    
    This webhook sends all time tracking data to compliance systems
    for regulatory reporting and audit trails.
    """
    return WebhookConfig(
        id=uuid4(),
        name="Compliance Audit Trail",
        url="https://compliance.yourcompany.com/api/audit/timetracking",
        description="Maintains audit trail for compliance reporting",
        event_types=list(EventType),  # All events for complete audit trail
        # No filtering - compliance needs everything
        event_filter=None,
        headers={
            "Content-Type": "application/json",
            "X-Compliance-Source": "clockman-timetracking",
            "X-Audit-Category": "employee-time",
            "Authorization": "Bearer your-compliance-api-token",
        },
        timeout=60.0,  # Longer timeout for compliance systems
        retry_policy=RetryPolicy(
            max_attempts=5,  # Critical for compliance
            base_delay=5.0,
            max_delay=900.0,  # 15 minutes max delay
            exponential_backoff=True,
        ),
    )


# Configuration templates for easy setup
WEBHOOK_TEMPLATES = {
    "filtered_slack": create_filtered_slack_webhook,
    "project_milestones": create_project_milestone_webhook,
    "analytics": create_time_tracking_analytics_webhook,
    "billing": create_client_billing_webhook,
    "team_collaboration": create_team_collaboration_webhook,
    "productivity": create_productivity_insights_webhook,
    "compliance": create_compliance_audit_webhook,
}


def create_webhook_from_template(template_name: str, **kwargs) -> WebhookConfig:
    """
    Create a webhook from a predefined template.
    
    Args:
        template_name: Name of the template to use
        **kwargs: Template-specific parameters
        
    Returns:
        Configured webhook
        
    Raises:
        ValueError: If template name is unknown
    """
    if template_name not in WEBHOOK_TEMPLATES:
        available = ", ".join(WEBHOOK_TEMPLATES.keys())
        raise ValueError(f"Unknown template '{template_name}'. Available: {available}")
    
    webhook = WEBHOOK_TEMPLATES[template_name]()
    
    # Apply any overrides from kwargs
    for key, value in kwargs.items():
        if hasattr(webhook, key):
            setattr(webhook, key, value)
    
    return webhook


def save_webhook_config_examples(output_dir: Path) -> None:
    """
    Save all webhook configuration examples to JSON files.
    
    Args:
        output_dir: Directory to save configuration files
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for template_name, template_func in WEBHOOK_TEMPLATES.items():
        webhook_config = template_func()
        
        config_file = output_dir / f"{template_name}_webhook.json"
        
        with open(config_file, 'w') as f:
            json.dump(
                webhook_config.model_dump(),
                f,
                indent=2,
                default=str,
            )
        
        print(f"Saved {template_name} webhook configuration: {config_file}")
    
    # Create a README file with usage instructions
    readme_content = """# Clockman Webhook Configuration Examples

This directory contains example webhook configurations demonstrating
the advanced filtering and integration capabilities of Clockman.

## Available Templates

"""
    
    for template_name, template_func in WEBHOOK_TEMPLATES.items():
        webhook = template_func()
        readme_content += f"### {template_name}\n"
        readme_content += f"- **File**: `{template_name}_webhook.json`\n"
        readme_content += f"- **Description**: {webhook.description}\n"
        readme_content += f"- **Event Types**: {', '.join(e.value for e in webhook.event_types)}\n"
        readme_content += "\n"
    
    readme_content += """
## Usage

To use these configurations:

1. Copy the desired JSON file to your Clockman configuration directory
2. Update the URL and any authentication headers
3. Load the webhook using the CLI:

```bash
clockman webhook add --name "My Webhook" --config path/to/webhook.json
```

Or customize and create via template:

```bash
clockman webhook add --name "My Slack Integration" \\
    --url "https://hooks.slack.com/your/webhook/url" \\
    --template filtered_slack
```

## Filter Examples

The webhook configurations demonstrate various filtering patterns:

- **Duration filters**: Only sessions longer/shorter than specified time
- **Tag filters**: Include/exclude based on session tags
- **Pattern matching**: Use regex patterns for task names
- **Logical operators**: Combine filters with AND, OR, NOT
- **Event type filtering**: Trigger on specific event types only

## Testing

Test your webhook configuration:

```bash
clockman webhook test --name "Your Webhook Name"
```

View delivery history:

```bash
clockman webhook history --name "Your Webhook Name"
```
"""
    
    readme_file = output_dir / "README.md"
    readme_file.write_text(readme_content)
    print(f"Created documentation: {readme_file}")


if __name__ == "__main__":
    # Create example configurations
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        save_webhook_config_examples(Path(temp_dir))
        print(f"Example configurations created in: {temp_dir}")
        
        # Test template creation
        for template_name in WEBHOOK_TEMPLATES:
            try:
                webhook = create_webhook_from_template(template_name)
                print(f"✓ {template_name}: {webhook.name}")
            except Exception as e:
                print(f"✗ {template_name}: {e}")