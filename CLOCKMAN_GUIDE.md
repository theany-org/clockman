# Clockman - Complete User Guide

Clockman is a powerful terminal-based time tracking application with advanced integration capabilities.

## Basic Time Tracking

### Starting a Session
```bash
# Start tracking a task
clockman start "Working on project"

# Start with tags
clockman start "Meeting with client" --tags work,meeting

# Start with project
clockman start "Bug fixes" --project myapp
```

### Managing Sessions
```bash
# Stop current session
clockman stop

# Pause current session
clockman pause

# Resume paused session
clockman resume

# Check current status
clockman status
```

### Viewing Time Data
```bash
# View today's summary
clockman summary

# View weekly summary
clockman summary --week

# View monthly summary
clockman summary --month

# View specific date range
clockman summary --from 2024-01-01 --to 2024-01-31
```

## Project Management

```bash
# List all projects
clockman projects

# Create new project
clockman project create "My New Project"

# Set active project
clockman project set "My New Project"

# View project statistics
clockman project stats "My New Project"
```

## Tag Management

```bash
# List all tags
clockman tags

# Add tags to current session
clockman tag add work,urgent

# Remove tags from current session
clockman tag remove urgent

# View sessions by tag
clockman filter --tags work
```

## Data Export

```bash
# Export to CSV
clockman export --format csv --output timesheet.csv

# Export to JSON
clockman export --format json --output data.json

# Export specific date range
clockman export --from 2024-01-01 --to 2024-01-31 --format csv
```

## Webhook Integration

### Managing Webhooks
```bash
# List all webhooks
clockman webhook list

# Add webhook from template
clockman webhook add --name "Slack Notifications" \
  --url "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  --template slack

# Add custom webhook
clockman webhook add --name "Time Tracker" \
  --url "https://api.example.com/webhook" \
  --events "session_started,session_stopped" \
  --description "Custom time tracking webhook"

# Test webhook
clockman webhook test --name "Slack Notifications"

# View webhook delivery history
clockman webhook history --name "Slack Notifications"

# Enable/disable webhook
clockman webhook enable --name "Slack Notifications"
clockman webhook disable --name "Slack Notifications"

# Remove webhook
clockman webhook remove --name "Slack Notifications"
```

### Webhook Templates
```bash
# View available templates
clockman webhook templates

# Available templates:
# - slack: Slack channel notifications
# - discord: Discord channel integration  
# - teams: Microsoft Teams notifications
# - generic: Basic webhook template
# - analytics: Data analytics integration
# - billing: Client billing system
```

### Advanced Webhook Filtering
Webhooks support sophisticated filtering:

```json
{
  "task_name": "Meeting",
  "duration_seconds": {"min": 300},
  "tags": ["work", "client"],
  "project": {"pattern": ".*client.*"}
}
```

## Plugin System

### Managing Plugins
```bash
# Discover available plugins
clockman plugin discover

# Load a plugin
clockman plugin load --name "productivity_analyzer"

# Load plugin with configuration
clockman plugin load --name "auto_backup" --config backup_config.json

# List loaded plugins
clockman plugin list

# View plugin details
clockman plugin status --name "productivity_analyzer"

# Enable/disable plugin
clockman plugin enable --name "productivity_analyzer"
clockman plugin disable --name "productivity_analyzer"

# Unload plugin
clockman plugin unload --name "productivity_analyzer"

# Reload plugin (useful during development)
clockman plugin reload --name "productivity_analyzer"
```

### Available Plugin Types
- **Productivity Analyzer**: Advanced analytics and insights
- **Auto Backup**: Automatic data backup management
- **Notification System**: Custom notification handlers
- **Data Processors**: Custom data processing and transformation
- **Integration Helpers**: Third-party service integrations

## Integration System

### System Management
```bash
# Check integration system status
clockman integration status

# View detailed statistics
clockman integration stats

# Enable/disable entire integration system
clockman integration enable
clockman integration disable

# Process pending webhook retries
clockman integration retry

# Clear delivery history
clockman integration clear-history
```

### Integration Hooks
The hook system allows custom callbacks on events:

```python
# Example hook registration
from clockman.integrations.hooks import register_hook

@register_hook('session_started', priority=10)
def my_session_handler(event_data):
    print(f"Session started: {event_data['task_name']}")
```

## Configuration

### Global Settings
Configuration is stored in `~/.clockman/config.json`:

```json
{
  "default_project": "work",
  "auto_save_interval": 60,
  "notification_enabled": true,
  "webhook_retry_attempts": 3,
  "plugin_directory": "~/.clockman/plugins"
}
```

### Environment Variables
```bash
export CLOCKMAN_CONFIG_DIR=~/.clockman
export CLOCKMAN_DATA_DIR=~/.clockman/data
export CLOCKMAN_PLUGIN_DIR=~/.clockman/plugins
```

## Advanced Features

### Custom Reporting
```bash
# Generate detailed reports
clockman report --type productivity --period month

# Custom date ranges
clockman report --from 2024-01-01 --to 2024-01-31 --group-by project

# Export reports
clockman report --format pdf --output monthly_report.pdf
```

### Automation
```bash
# Set up automatic session tracking
clockman auto-track --enable

# Configure idle detection
clockman idle-detection --timeout 300 --action pause

# Schedule automatic reports
clockman schedule-report --frequency weekly --email user@example.com
```

### Data Filtering
```bash
# Filter by project
clockman filter --project "client work"

# Filter by tags
clockman filter --tags work,urgent

# Filter by duration
clockman filter --min-duration 30m --max-duration 4h

# Complex filtering
clockman filter --project "client*" --tags work --after 2024-01-01
```

## Integration Examples

### Slack Integration
```bash
# Set up Slack notifications
clockman webhook add --name "Slack Team" \
  --url "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK" \
  --template slack \
  --events "session_started,session_stopped"
```

### Analytics Pipeline
```bash
# Set up analytics webhook
clockman webhook add --name "Analytics" \
  --url "https://analytics.example.com/webhook" \
  --events "session_stopped" \
  --filter '{"duration_seconds": {"min": 300}}'
```

### Backup System
```bash
# Load auto-backup plugin
clockman plugin load --name "auto_backup" \
  --config '{"interval": 3600, "destination": "/backup/clockman"}'
```

## Testing and Debugging

### Webhook Testing
```bash
# Test specific webhook
clockman webhook test --name "Slack Notifications" --event session_started

# Test all webhooks
clockman webhook test --all

# View webhook logs
clockman webhook history --name "Slack Notifications" --verbose
```

### Plugin Testing
```bash
# Test plugin functionality
clockman plugin test --name "productivity_analyzer"

# Debug plugin issues
clockman plugin status --name "productivity_analyzer" --debug
```

### System Diagnostics
```bash
# System health check
clockman integration status --verbose

# View detailed logs
clockman logs --level debug --component webhooks

# Performance statistics
clockman integration stats --detailed
```

## Troubleshooting

### Common Issues

**Webhook delivery failures:**
```bash
# Check webhook status
clockman webhook list
# View delivery history
clockman webhook history --name "webhook_name"
# Test webhook manually
clockman webhook test --name "webhook_name"
```

**Plugin loading issues:**
```bash
# Check plugin dependencies
clockman plugin status --name "plugin_name" --debug
# Reload plugin
clockman plugin reload --name "plugin_name"
```

**Integration system problems:**
```bash
# Check system status
clockman integration status
# View error logs
clockman logs --level error
# Restart integration system
clockman integration disable && clockman integration enable
```

## Tips and Best Practices

1. **Use descriptive task names** for better reporting
2. **Tag consistently** for easy filtering and analysis
3. **Set up project hierarchies** for complex work structures
4. **Configure webhooks gradually** - start simple, add complexity
5. **Test plugins in development** before production use
6. **Monitor webhook delivery** regularly
7. **Back up your data** using the auto-backup plugin
8. **Use filtering** to focus on relevant time entries
9. **Set up automation** for repetitive tasks
10. **Regular maintenance** - clean up old data and unused integrations

## Getting Help

```bash
# View command help
clockman --help
clockman command --help

# Check system version
clockman version

# View configuration
clockman config show
```

For more advanced usage and development information, see the plugin development documentation and webhook API reference.