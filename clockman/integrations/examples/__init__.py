"""Example integrations for Clockman."""

from .webhook_example import (
    create_slack_webhook,
    create_discord_webhook,
    create_generic_webhook,
    create_task_tracker_webhook,
    create_analytics_webhook,
    create_webhook_from_template,
    load_webhook_config_from_file,
    save_webhook_config_examples,
)

from .logging_plugin import (
    LoggingPlugin,
    SessionSummaryPlugin,
    create_logging_plugin_config,
    create_session_summary_config,
)

__all__ = [
    "create_slack_webhook",
    "create_discord_webhook", 
    "create_generic_webhook",
    "create_task_tracker_webhook",
    "create_analytics_webhook",
    "create_webhook_from_template",
    "load_webhook_config_from_file",
    "save_webhook_config_examples",
    "LoggingPlugin",
    "SessionSummaryPlugin", 
    "create_logging_plugin_config",
    "create_session_summary_config",
]