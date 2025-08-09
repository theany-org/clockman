"""
Main CLI entry point for Clockman.

This module provides the primary command-line interface using typer.
"""

import csv
import gzip
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, TaskID
from rich.text import Text

from ..core.time_tracker import TimeTracker
from ..utils.config import get_config_manager
from ..utils.formatting import format_datetime, format_duration, format_date
from ..utils.notifier import notify_sync

# Create the main typer app
app = typer.Typer(
    name="clockman",
    help="Clockman: Terminal-based time tracking for developers",
    add_completion=False,
)

# Initialize console for rich output
console = Console()

# Global clockman instance
clockman: Optional[TimeTracker] = None


def get_clockman() -> TimeTracker:
    """Get or initialize the global time clockman instance."""
    global clockman
    if clockman is None:
        config = get_config_manager()
        clockman = TimeTracker(config.get_data_dir())
    return clockman


@app.command()
def start(
    task_name: str = typer.Argument(..., help="Name of the task to track"),
    tag: Optional[List[str]] = typer.Option(
        None, "--tag", "-t", help="Add tags to the task"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Task description"
    ),
    project: Optional[str] = typer.Option(
        None, "--project", "-p", help="Project name or ID to associate with the task"
    ),
) -> None:
    """Start tracking time for a task."""
    try:
        time_tracker = get_clockman()

        # Stop any active session first
        active_session = time_tracker.get_active_session()
        if active_session:
            time_tracker.stop_session()
            console.print(
                f"[yellow]Stopped previous task: {active_session.task_name}[/yellow]"
            )
            notify_sync(
                title="Clockman Notification",
                message=f"Stopped previous task: {active_session.task_name}",
            )

        # Handle project parameter
        project_id = None
        if project:
            # Try to find project by name first, then by ID
            project_obj = time_tracker.get_project_by_name(project)
            if not project_obj:
                try:
                    from uuid import UUID
                    project_obj = time_tracker.get_project_by_id(UUID(project))
                except ValueError:
                    console.print(f"[red]Project '{project}' not found[/red]")
                    raise typer.Exit(1)
            if project_obj:
                project_id = project_obj.id

        # Start new session
        session_id = time_tracker.start_session(
            task_name=task_name, 
            tags=tag or [], 
            description=description,
            project_id=project_id
        )

        console.print(f"[green]✓[/green] Started tracking: [bold]{task_name}[/bold]")
        if project_obj:
            console.print(f"[dim]Project: {project_obj.name}[/dim]")
        if tag:
            console.print(f"[dim]Tags: {', '.join(tag)}[/dim]")
        if description:
            console.print(f"[dim]Description: {description}[/dim]")
        console.print(f"[dim]Session ID: {session_id}[/dim]")
        notify_sync(
            title="Clockman Notification",
            message=f"Started tracking: {task_name}",
        )

    except Exception as e:
        console.print(f"[red]Error starting task: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def stop() -> None:
    """Stop the currently active time tracking session."""
    try:
        time_tracker = get_clockman()
        active_session = time_tracker.get_active_session()

        if not active_session:
            console.print("[yellow]No active session to stop[/yellow]")
            notify_sync(
                title="Clockman Notification",
                message="No active session to stop",
            )
            return

        stopped_session = time_tracker.stop_session()

        if stopped_session and stopped_session.end_time:
            duration = stopped_session.end_time - stopped_session.start_time
            console.print(
                f"[green]✓[/green] Stopped: [bold]{stopped_session.task_name}[/bold]"
            )
            console.print(f"[dim]Duration: {format_duration(duration)}[/dim]")
            notify_sync(
                title="Clockman Notification",
                message=f"Stopped: {stopped_session.task_name} (Duration: {format_duration(duration)})",
            )
    except Exception as e:
        console.print(f"[red]Error stopping session: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show the current active session status."""
    try:
        time_tracker = get_clockman()
        active_session = time_tracker.get_active_session()

        if not active_session:
            console.print("[dim]No active session[/dim]")
            return

        # Calculate current duration
        from datetime import datetime, timezone

        current_time = datetime.now(timezone.utc)
        duration = current_time - active_session.start_time

        # Create status table
        table = Table(show_header=False, show_edge=False, pad_edge=False)
        table.add_column("Key", style="dim")
        table.add_column("Value")

        table.add_row("Task", f"[bold]{active_session.task_name}[/bold]")
        table.add_row("Started", format_datetime(active_session.start_time))
        table.add_row("Duration", format_duration(duration))

        if active_session.project_id:
            project = time_tracker.get_project_by_id(active_session.project_id)
            table.add_row("Project", project.name if project else "Unknown")

        if active_session.tags:
            table.add_row("Tags", ", ".join(active_session.tags))

        if active_session.description:
            table.add_row("Description", active_session.description)

        console.print("[green]● Active Session[/green]")
        console.print(table)

    except Exception as e:
        console.print(f"[red]Error getting status: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def log(
    today: bool = typer.Option(True, "--today", help="Show today's entries"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of entries to show"),
) -> None:
    """Show recent time tracking entries."""
    try:
        time_tracker = get_clockman()

        if today:
            from datetime import date

            entries = time_tracker.get_entries_for_date(date.today())
            console.print(f"[bold]Today's Time Entries ({date.today()})[/bold]")
        else:
            entries = time_tracker.get_recent_entries(limit=limit)
            console.print(f"[bold]Recent Time Entries (last {limit})[/bold]")

        if not entries:
            console.print("[dim]No entries found[/dim]")
            return

        # Create entries table
        table = Table()
        table.add_column("Task", style="bold")
        table.add_column("Project", style="magenta")
        table.add_column("Start", style="dim")
        table.add_column("End", style="dim")
        table.add_column("Duration", justify="right")
        table.add_column("Tags", style="cyan")

        total_duration = 0.0
        for entry in entries:
            if entry.end_time:
                duration = entry.end_time - entry.start_time
                total_duration += duration.total_seconds()
                end_str = format_datetime(entry.end_time)
                duration_str = format_duration(duration)
            else:
                end_str = "[yellow]Active[/yellow]"
                duration_str = "[yellow]Running[/yellow]"

            tags_str = ", ".join(entry.tags) if entry.tags else ""
            
            # Get project name
            project_name = ""
            if entry.project_id:
                project = time_tracker.get_project_by_id(entry.project_id)
                project_name = project.name if project else "Unknown"

            table.add_row(
                entry.task_name,
                project_name,
                format_datetime(entry.start_time),
                end_str,
                duration_str,
                tags_str,
            )

        console.print(table)

        if total_duration > 0:
            from datetime import timedelta

            total = timedelta(seconds=total_duration)
            console.print(f"\n[bold]Total: {format_duration(total)}[/bold]")

    except Exception as e:
        console.print(f"[red]Error showing log: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def summary(
    start_date: Optional[str] = typer.Option(
        None, "--start", "-s", help="Start date (YYYY-MM-DD) or 'today', 'week', 'month'"
    ),
    end_date: Optional[str] = typer.Option(
        None, "--end", "-e", help="End date (YYYY-MM-DD)"
    ),
    group_by: str = typer.Option(
        "date", "--group-by", "-g", help="Group by: date, task, tag, week, month, raw"
    ),
    export_csv: Optional[str] = typer.Option(
        None, "--csv", help="Export to CSV file"
    ),
    show_details: bool = typer.Option(
        False, "--details", "-d", help="Show detailed breakdown"
    ),
) -> None:
    """Show time tracking summary with date ranges and grouping options."""
    try:
        time_tracker = get_clockman()
        
        # Parse date range
        start_dt, end_dt = _parse_date_range(start_date, end_date)
        
        console.print(f"[bold]Time Summary: {format_date(start_dt)} to {format_date(end_dt)}[/bold]")
        
        # Get entries in range
        entries = time_tracker.get_entries_in_range(start_dt.date(), end_dt.date())
        completed_entries = [e for e in entries if e.end_time]
        
        if not completed_entries:
            console.print("[dim]No completed entries found in the specified range[/dim]")
            return
        
        # Group and display data
        if group_by == "date":
            _display_date_summary(completed_entries, show_details)
        elif group_by == "task":
            _display_task_summary(completed_entries, show_details)
        elif group_by == "tag":
            _display_tag_summary(completed_entries, show_details)
        elif group_by == "week":
            _display_week_summary(completed_entries, show_details)
        elif group_by == "month":
            _display_month_summary(completed_entries, show_details)
        elif group_by == "raw":
            _display_raw_summary(completed_entries, show_details)
        else:
            console.print(f"[red]Invalid group-by option: {group_by}[/red]")
            return
        
        # Export to CSV if requested
        if export_csv:
            _export_to_csv(completed_entries, Path(export_csv), group_by)
            console.print(f"[green]Data exported to {export_csv}[/green]")
            console.print("[dim]Note: Use --group-by=raw for complete database export with all fields[/dim]")
            
    except Exception as e:
        console.print(f"[red]Error generating summary: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def export(
    output_file: str = typer.Argument(..., help="Output file path for export"),
    format_type: str = typer.Option(
        "json", "--format", "-f", help="Export format: json, ical, sql"
    ),
    start_date: Optional[str] = typer.Option(
        None, "--start", "-s", help="Start date (YYYY-MM-DD) or 'today', 'week', 'month'"
    ),
    end_date: Optional[str] = typer.Option(
        None, "--end", "-e", help="End date (YYYY-MM-DD)"
    ),
    include_active: bool = typer.Option(
        True, "--include-active", help="Include active sessions in export"
    ),
    pretty: bool = typer.Option(
        True, "--pretty", help="Pretty-print JSON output (JSON format only)"
    ),
    compress: bool = typer.Option(
        False, "--compress", "-z", help="Compress the output file"
    ),
) -> None:
    """Export time tracking data in various formats."""
    try:
        time_tracker = get_clockman()
        output_path = Path(output_file)
        
        # Parse date range if provided
        if start_date or end_date:
            start_dt, end_dt = _parse_date_range(start_date, end_date)
            entries = time_tracker.get_entries_in_range(start_dt.date(), end_dt.date())
            date_range_str = f" from {format_date(start_dt)} to {format_date(end_dt)}"
        else:
            # Export all entries
            entries = time_tracker.session_repo.get_all_sessions()
            date_range_str = " (all data)"
        
        # Filter out active sessions if not requested
        if not include_active:
            entries = [e for e in entries if not e.is_active]
        
        console.print(f"[bold]Exporting {len(entries)} sessions{date_range_str}[/bold]")
        
        if format_type.lower() == "json":
            _export_json(entries, output_path, pretty, compress)
        elif format_type.lower() == "ical":
            _export_ical(entries, output_path, compress)
        elif format_type.lower() == "sql":
            _export_sql(entries, output_path, compress)
        else:
            console.print(f"[red]Unsupported format: {format_type}[/red]")
            console.print("Supported formats: json, ical, sql")
            raise typer.Exit(1)
        
        file_size = output_path.stat().st_size
        size_str = f"{file_size:,} bytes" if file_size < 1024 else f"{file_size / 1024:.1f} KB"
        
        console.print(f"[green]✓[/green] Export completed: {output_file}")
        console.print(f"[dim]File size: {size_str}[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error exporting data: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query (task name, description, or tag)"),
    field: str = typer.Option(
        "all", "--field", "-f", help="Search field: all, task, description, tag"
    ),
    case_sensitive: bool = typer.Option(
        False, "--case-sensitive", "-c", help="Case-sensitive search"
    ),
    regex: bool = typer.Option(
        False, "--regex", "-r", help="Use regular expression matching"
    ),
    start_date: Optional[str] = typer.Option(
        None, "--start", "-s", help="Start date (YYYY-MM-DD) for date range filter"
    ),
    end_date: Optional[str] = typer.Option(
        None, "--end", "-e", help="End date (YYYY-MM-DD) for date range filter"
    ),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results"),
) -> None:
    """Advanced search through time tracking entries."""
    try:
        time_tracker = get_clockman()
        
        # Get entries within date range if specified
        if start_date or end_date:
            start_dt, end_dt = _parse_date_range(start_date, end_date)
            entries = time_tracker.get_entries_in_range(start_dt.date(), end_dt.date())
            date_filter_str = f" (filtered: {format_date(start_dt)} to {format_date(end_dt)})"
        else:
            entries = time_tracker.session_repo.get_all_sessions()
            date_filter_str = ""
        
        # Perform search
        search_results = _perform_search(entries, query, field, case_sensitive, regex)
        
        # Apply limit
        if len(search_results) > limit:
            search_results = search_results[:limit]
            limited_str = f" (showing first {limit})"
        else:
            limited_str = ""
        
        console.print(f"[bold]Search Results: {len(search_results)} matches{date_filter_str}{limited_str}[/bold]")
        console.print(f"[dim]Query: \"{query}\" in {field} field(s)[/dim]")
        
        if not search_results:
            console.print("[dim]No matches found[/dim]")
            return
        
        # Display results table
        table = Table(show_header=True, header_style="bold")
        table.add_column("ID", style="dim", width=8)
        table.add_column("Task", style="bold")
        table.add_column("Start", style="dim")
        table.add_column("Duration", justify="right", style="green")
        table.add_column("Tags", style="cyan")
        table.add_column("Description", style="dim")
        
        for entry in search_results:
            # Highlight search matches in results
            task_display = _highlight_match(entry.task_name, query, case_sensitive)
            desc_display = _highlight_match(entry.description or "", query, case_sensitive)
            
            if entry.end_time:
                duration = entry.end_time - entry.start_time
                duration_str = format_duration(duration)
            else:
                duration_str = "[yellow]Active[/yellow]"
            
            tags_str = ", ".join(entry.tags) if entry.tags else ""
            
            table.add_row(
                str(entry.id)[:8],
                task_display,
                format_datetime(entry.start_time),
                duration_str,
                tags_str,
                desc_display[:50] + "..." if len(desc_display) > 50 else desc_display,
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error searching entries: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def resume() -> None:
    """Resume a previous task interactively."""
    try:
        time_tracker = get_clockman()
        
        # Stop any active session first
        active_session = time_tracker.get_active_session()
        if active_session:
            console.print(f"[yellow]Stopping current task: {active_session.task_name}[/yellow]")
            time_tracker.stop_session()
        
        # Get recent unique tasks
        recent_entries = time_tracker.get_recent_entries(limit=50)
        unique_tasks = []
        task_details = {}
        
        for entry in recent_entries:
            if entry.task_name not in task_details:
                unique_tasks.append(entry.task_name)
                task_details[entry.task_name] = {
                    'description': entry.description,
                    'tags': entry.tags,
                    'last_used': entry.start_time
                }
        
        if not unique_tasks:
            console.print("[dim]No previous tasks found[/dim]")
            return
        
        # Display task options
        console.print("[bold]Recent Tasks:[/bold]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=3)
        table.add_column("Task", style="bold")
        table.add_column("Tags", style="cyan")
        table.add_column("Last Used", style="dim")
        
        for i, task_name in enumerate(unique_tasks[:10], 1):
            details = task_details[task_name]
            tags_str = ", ".join(details['tags']) if details['tags'] else ""
            last_used_str = format_datetime(details['last_used'])
            table.add_row(str(i), task_name, tags_str, last_used_str)
        
        console.print(table)
        
        # Get user selection
        try:
            choice = Prompt.ask("Select task number (or 'n' for new task)", default="n")
            if choice.lower() == 'n':
                new_task = Prompt.ask("Enter new task name")
                if new_task.strip():
                    session_id = time_tracker.start_session(task_name=new_task.strip())
                    console.print(f"[green]✓[/green] Started tracking: [bold]{new_task}[/bold]")
                    console.print(f"[dim]Session ID: {session_id}[/dim]")
                return
                
            choice_num = int(choice)
            if 1 <= choice_num <= min(10, len(unique_tasks)):
                selected_task = unique_tasks[choice_num - 1]
                details = task_details[selected_task]
                
                session_id = time_tracker.start_session(
                    task_name=selected_task,
                    description=details['description'],
                    tags=details['tags']
                )
                
                console.print(f"[green]✓[/green] Resumed tracking: [bold]{selected_task}[/bold]")
                if details['tags']:
                    console.print(f"[dim]Tags: {', '.join(details['tags'])}[/dim]")
                if details['description']:
                    console.print(f"[dim]Description: {details['description']}[/dim]")
                console.print(f"[dim]Session ID: {session_id}[/dim]")
                
                notify_sync(
                    title="Clockman Notification",
                    message=f"Resumed tracking: {selected_task}",
                )
            else:
                console.print("[red]Invalid selection[/red]")
                
        except ValueError:
            console.print("[red]Invalid input[/red]")
            
    except Exception as e:
        console.print(f"[red]Error resuming task: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def delete() -> None:
    """Delete time entries interactively."""
    try:
        time_tracker = get_clockman()
        
        # Get recent entries
        recent_entries = time_tracker.get_recent_entries(limit=20)
        if not recent_entries:
            console.print("[dim]No entries found[/dim]")
            return
        
        # Display entries
        console.print("[bold]Recent Entries:[/bold]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=3)
        table.add_column("Task", style="bold")
        table.add_column("Start", style="dim")
        table.add_column("Duration", justify="right")
        table.add_column("Tags", style="cyan")
        
        for i, entry in enumerate(recent_entries, 1):
            if entry.end_time:
                duration = entry.end_time - entry.start_time
                duration_str = format_duration(duration)
            else:
                duration_str = "[yellow]Active[/yellow]"
            
            tags_str = ", ".join(entry.tags) if entry.tags else ""
            
            table.add_row(
                str(i),
                entry.task_name,
                format_datetime(entry.start_time),
                duration_str,
                tags_str
            )
        
        console.print(table)
        
        # Get selection
        selection = Prompt.ask("Enter entry numbers to delete (comma-separated) or 'cancel'", default="cancel")
        
        if selection.lower() == 'cancel':
            console.print("[dim]Cancelled[/dim]")
            return
        
        try:
            # Parse selections
            selected_indices = [int(x.strip()) for x in selection.split(",")]
            selected_entries = []
            
            for idx in selected_indices:
                if 1 <= idx <= len(recent_entries):
                    selected_entries.append(recent_entries[idx - 1])
                else:
                    console.print(f"[yellow]Warning: Invalid entry number {idx}[/yellow]")
            
            if not selected_entries:
                console.print("[red]No valid entries selected[/red]")
                return
            
            # Confirm deletion
            entry_names = [f"'{e.task_name}'" for e in selected_entries]
            if len(entry_names) > 3:
                entry_list = ", ".join(entry_names[:3]) + f", and {len(entry_names)-3} more"
            else:
                entry_list = ", ".join(entry_names)
            
            if Confirm.ask(f"Delete {len(selected_entries)} entries: {entry_list}?"):
                deleted_count = 0
                for entry in selected_entries:
                    if time_tracker.delete_session(entry.id):
                        deleted_count += 1
                
                console.print(f"[green]✓[/green] Deleted {deleted_count} entries")
            else:
                console.print("[dim]Cancelled[/dim]")
            
        except ValueError:
            console.print("[red]Invalid input format[/red]")
            
    except Exception as e:
        console.print(f"[red]Error deleting entries: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def config(
    key: Optional[str] = typer.Argument(None, help="Configuration key to get/set"),
    value: Optional[str] = typer.Argument(None, help="Value to set (omit to get current value)"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List all configuration"),
    reset: bool = typer.Option(False, "--reset", help="Reset to default configuration"),
    export_file: Optional[str] = typer.Option(None, "--export", help="Export config to file"),
    import_file: Optional[str] = typer.Option(None, "--import", help="Import config from file"),
) -> None:
    """Manage Clockman configuration."""
    try:
        config_manager = get_config_manager()
        
        if reset:
            if Confirm.ask("Reset all configuration to defaults?"):
                config_manager.reset_to_defaults()
                console.print("[green]✓[/green] Configuration reset to defaults")
            return
        
        if export_file:
            config_manager.export_config(Path(export_file))
            console.print(f"[green]✓[/green] Configuration exported to {export_file}")
            return
        
        if import_file:
            if Path(import_file).exists():
                config_manager.import_config(Path(import_file))
                console.print(f"[green]✓[/green] Configuration imported from {import_file}")
            else:
                console.print(f"[red]File not found: {import_file}[/red]")
            return
        
        if list_all:
            # Display current configuration
            console.print("[bold]Current Configuration:[/bold]")
            
            table = Table(show_header=True, header_style="bold")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="white")
            
            # Key settings to display
            settings = [
                ("data_directory", config_manager.get_data_dir()),
                ("date_format", config_manager.get_date_format()),
                ("time_format", config_manager.get_time_format()),
                ("show_seconds", config_manager.show_seconds()),
                ("compact_mode", config_manager.is_compact_mode()),
                ("max_task_name_length", config_manager.get_max_task_name_length()),
                ("notifications_enabled", config_manager.are_notifications_enabled()),
                ("notification_timeout_ms", config_manager.get_notification_timeout()),
                ("auto_stop_inactive", config_manager.is_auto_stop_enabled()),
                ("inactive_timeout_minutes", config_manager.get_inactive_timeout()),
            ]
            
            for setting, val in settings:
                table.add_row(setting, str(val))
            
            console.print(table)
            return
        
        if key is None:
            console.print("Use --list to see all configuration or provide a key to get/set")
            return
        
        if value is None:
            # Get value
            current_value = config_manager.get(key)
            if current_value is not None:
                console.print(f"[cyan]{key}[/cyan] = [white]{current_value}[/white]")
            else:
                console.print(f"[red]Configuration key '{key}' not found[/red]")
        else:
            # Set value (try to parse as JSON first, then as string)
            try:
                import json
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value
            
            config_manager.set(key, parsed_value)
            console.print(f"[green]✓[/green] Set [cyan]{key}[/cyan] = [white]{parsed_value}[/white]")
        
    except Exception as e:
        console.print(f"[red]Error managing configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def project(
    action: str = typer.Argument(..., help="Action: create, list, show, update, delete, hierarchy"),
    name: Optional[str] = typer.Argument(None, help="Project name or ID for show/update/delete actions"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Project description"),
    parent: Optional[str] = typer.Option(None, "--parent", "-p", help="Parent project name or ID"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", "-t", help="Default tags for the project"),
    active: Optional[bool] = typer.Option(None, "--active", help="Project active status"),
    show_inactive: bool = typer.Option(False, "--show-inactive", help="Show inactive projects in list"),
) -> None:
    """Manage projects for organizing time tracking sessions."""
    try:
        time_tracker = get_clockman()
        
        if action == "create":
            if not name:
                console.print("[red]Project name is required for create action[/red]")
                raise typer.Exit(1)
            
            # Handle parent project
            parent_id = None
            parent_obj = None
            if parent:
                parent_obj = time_tracker.get_project_by_name(parent)
                if not parent_obj:
                    try:
                        from uuid import UUID
                        parent_obj = time_tracker.get_project_by_id(UUID(parent))
                    except ValueError:
                        console.print(f"[red]Parent project '{parent}' not found[/red]")
                        raise typer.Exit(1)
                
                if not parent_obj:
                    console.print(f"[red]Parent project '{parent}' not found[/red]")
                    raise typer.Exit(1)
                    
                parent_id = parent_obj.id
            
            project_id = time_tracker.create_project(
                name=name,
                description=description,
                parent_id=parent_id,
                default_tags=tags or []
            )
            
            console.print(f"[green]✓[/green] Created project: [bold]{name}[/bold]")
            if parent_obj:
                console.print(f"[dim]Parent: {parent_obj.name}[/dim]")
            if description:
                console.print(f"[dim]Description: {description}[/dim]")
            if tags:
                console.print(f"[dim]Default tags: {', '.join(tags)}[/dim]")
            console.print(f"[dim]Project ID: {project_id}[/dim]")
        
        elif action == "list":
            projects = time_tracker.get_active_projects() if not show_inactive else time_tracker.get_all_projects()
            
            if not projects:
                console.print("[dim]No projects found[/dim]")
                return
            
            console.print(f"[bold]Projects ({len(projects)} total)[/bold]")
            
            table = Table(show_header=True, header_style="bold")
            table.add_column("Name", style="bold")
            table.add_column("Description", style="dim")
            table.add_column("Parent", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Default Tags", style="yellow")
            table.add_column("ID", style="dim", width=8)
            
            for project in projects:
                parent_name = ""
                if project.parent_id:
                    parent_obj = time_tracker.get_project_by_id(project.parent_id)
                    parent_name = parent_obj.name if parent_obj else "Unknown"
                
                status = "[green]Active[/green]" if project.is_active else "[red]Inactive[/red]"
                tags_str = ", ".join(project.default_tags) if project.default_tags else ""
                desc = project.description[:50] + "..." if project.description and len(project.description) > 50 else (project.description or "")
                
                table.add_row(
                    project.name,
                    desc,
                    parent_name,
                    status,
                    tags_str,
                    str(project.id)[:8]
                )
            
            console.print(table)
        
        elif action == "hierarchy":
            hierarchy = time_tracker.get_project_hierarchy()
            
            def display_tree(nodes, indent=0):
                for node in nodes:
                    project = node["project"]
                    prefix = "  " * indent + ("├── " if indent > 0 else "")
                    status = "[green]●[/green]" if project.is_active else "[red]○[/red]"
                    console.print(f"{prefix}{status} [bold]{project.name}[/bold]")
                    if project.description:
                        console.print(f"{'  ' * (indent + 1)}[dim]{project.description}[/dim]")
                    if node["children"]:
                        display_tree(node["children"], indent + 1)
            
            console.print("[bold]Project Hierarchy[/bold]")
            if hierarchy["hierarchy"]:
                display_tree(hierarchy["hierarchy"])
            else:
                console.print("[dim]No projects found[/dim]")
        
        elif action == "show":
            if not name:
                console.print("[red]Project name or ID is required for show action[/red]")
                raise typer.Exit(1)
            
            project = time_tracker.get_project_by_name(name)
            if not project:
                try:
                    from uuid import UUID
                    project = time_tracker.get_project_by_id(UUID(name))
                except ValueError:
                    pass
            
            if not project:
                console.print(f"[red]Project '{name}' not found[/red]")
                raise typer.Exit(1)
            
            # Display project details
            table = Table(show_header=False, show_edge=False, pad_edge=False)
            table.add_column("Key", style="dim")
            table.add_column("Value")
            
            table.add_row("Name", f"[bold]{project.name}[/bold]")
            table.add_row("ID", str(project.id))
            table.add_row("Status", "[green]Active[/green]" if project.is_active else "[red]Inactive[/red]")
            
            if project.description:
                table.add_row("Description", project.description)
            
            if project.parent_id:
                parent_obj = time_tracker.get_project_by_id(project.parent_id)
                table.add_row("Parent", parent_obj.name if parent_obj else "Unknown")
            
            if project.default_tags:
                table.add_row("Default Tags", ", ".join(project.default_tags))
            
            table.add_row("Created", format_datetime(project.created_at))
            
            console.print(table)
            
            # Show sessions for this project
            sessions = time_tracker.get_sessions_by_project(project.id)
            if sessions:
                console.print(f"\n[bold]Recent Sessions ({len(sessions)} total)[/bold]")
                session_table = Table()
                session_table.add_column("Task", style="bold")
                session_table.add_column("Start", style="dim")
                session_table.add_column("Duration", justify="right")
                
                for session in sessions[:5]:  # Show only first 5
                    if session.end_time:
                        duration = session.end_time - session.start_time
                        duration_str = format_duration(duration)
                    else:
                        duration_str = "[yellow]Active[/yellow]"
                    
                    session_table.add_row(
                        session.task_name,
                        format_datetime(session.start_time),
                        duration_str
                    )
                
                console.print(session_table)
                if len(sessions) > 5:
                    console.print(f"[dim]... and {len(sessions) - 5} more sessions[/dim]")
        
        elif action == "update":
            if not name:
                console.print("[red]Project name or ID is required for update action[/red]")
                raise typer.Exit(1)
            
            project = time_tracker.get_project_by_name(name)
            project_id = None
            if not project:
                try:
                    from uuid import UUID
                    project_id = UUID(name)
                    project = time_tracker.get_project_by_id(project_id)
                except ValueError:
                    pass
            else:
                project_id = project.id
            
            if not project:
                console.print(f"[red]Project '{name}' not found[/red]")
                raise typer.Exit(1)
            
            # Handle parent project
            parent_id = None
            parent_obj = None
            if parent:
                parent_obj = time_tracker.get_project_by_name(parent)
                if not parent_obj:
                    try:
                        from uuid import UUID
                        parent_obj = time_tracker.get_project_by_id(UUID(parent))
                    except ValueError:
                        console.print(f"[red]Parent project '{parent}' not found[/red]")
                        raise typer.Exit(1)
                
                if not parent_obj:
                    console.print(f"[red]Parent project '{parent}' not found[/red]")
                    raise typer.Exit(1)
                    
                parent_id = parent_obj.id
            
            updated_project = time_tracker.update_project(
                project_id=project_id,
                description=description,
                parent_id=parent_id,
                default_tags=tags,
                is_active=active
            )
            
            console.print(f"[green]✓[/green] Updated project: [bold]{updated_project.name}[/bold]")
        
        elif action == "delete":
            if not name:
                console.print("[red]Project name or ID is required for delete action[/red]")
                raise typer.Exit(1)
            
            project = time_tracker.get_project_by_name(name)
            project_id = None
            if not project:
                try:
                    from uuid import UUID
                    project_id = UUID(name)
                    project = time_tracker.get_project_by_id(project_id)
                except ValueError:
                    pass
            else:
                project_id = project.id
            
            if not project:
                console.print(f"[red]Project '{name}' not found[/red]")
                raise typer.Exit(1)
            
            # Check for child projects
            children = time_tracker.project_repo.get_projects_by_parent(project_id)
            if children:
                console.print(f"[red]Cannot delete project '{project.name}' because it has {len(children)} child projects[/red]")
                console.print("Child projects:")
                for child in children:
                    console.print(f"  - {child.name}")
                raise typer.Exit(1)
            
            if Confirm.ask(f"Delete project '{project.name}' and unlink all associated sessions?"):
                if time_tracker.delete_project(project_id):
                    console.print(f"[green]✓[/green] Deleted project: {project.name}")
                else:
                    console.print(f"[red]Failed to delete project: {project.name}[/red]")
            else:
                console.print("[dim]Cancelled[/dim]")
        
        else:
            console.print(f"[red]Unknown action: {action}[/red]")
            console.print("Available actions: create, list, show, update, delete, hierarchy")
            raise typer.Exit(1)
    
    except Exception as e:
        console.print(f"[red]Error managing projects: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def analyze(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to analyze"),
    fix_issues: bool = typer.Option(False, "--fix", help="Attempt to fix detected issues"),
    detailed: bool = typer.Option(False, "--detailed", help="Show detailed analysis"),
) -> None:
    """Analyze time tracking accuracy and detect potential issues."""
    try:
        from ..utils.time_validation import TimeAccuracyValidator
        
        time_tracker = get_clockman()
        validator = TimeAccuracyValidator()
        
        # Get recent sessions
        if days > 0:
            from datetime import date, timedelta
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            sessions = time_tracker.get_entries_in_range(start_date, end_date)
        else:
            sessions = time_tracker.session_repo.get_all_sessions()
        
        if not sessions:
            console.print("[dim]No sessions found to analyze[/dim]")
            return
        
        console.print(f"[bold]Time Tracking Analysis[/bold] ({len(sessions)} sessions)")
        console.print(f"[dim]Analyzing last {days} days[/dim]" if days > 0 else "[dim]Analyzing all sessions[/dim]")
        
        # Calculate accuracy score
        score, metrics = validator.calculate_accuracy_score(sessions)
        
        # Display score with color coding
        if score >= 90:
            score_color = "green"
        elif score >= 70:
            score_color = "yellow"
        else:
            score_color = "red"
        
        console.print(f"[bold]Accuracy Score: [{score_color}]{score:.1f}/100[/{score_color}][/bold]")
        
        # Show metrics summary
        console.print("\n[bold]Summary:[/bold]")
        summary_table = Table(show_header=False, show_edge=False, pad_edge=False)
        summary_table.add_column("Metric", style="dim")
        summary_table.add_column("Count", justify="right")
        
        summary_table.add_row("Total Sessions", str(metrics["total_sessions"]))
        summary_table.add_row("Completed Sessions", str(metrics["completed_sessions"]))
        
        if metrics["potential_idle_sessions"] > 0:
            summary_table.add_row("⚠️ Potential Idle Sessions", f"[yellow]{metrics['potential_idle_sessions']}[/yellow]")
        
        if metrics["overlapping_sessions"] > 0:
            summary_table.add_row("🔴 Overlapping Sessions", f"[red]{metrics['overlapping_sessions']}[/red]")
        
        if metrics["very_short_sessions"] > 0:
            summary_table.add_row("⚡ Very Short Sessions", f"[yellow]{metrics['very_short_sessions']}[/yellow]")
        
        if metrics["very_long_sessions"] > 0:
            summary_table.add_row("⏰ Very Long Sessions", f"[yellow]{metrics['very_long_sessions']}[/yellow]")
        
        if metrics["unusual_time_sessions"] > 0:
            summary_table.add_row("🌙 Unusual Time Sessions", f"[cyan]{metrics['unusual_time_sessions']}[/cyan]")
        
        console.print(summary_table)
        
        # Show detailed analysis if requested
        if detailed or metrics["overlapping_sessions"] > 0 or metrics["potential_idle_sessions"] > 5:
            console.print("\n[bold]Detailed Issues:[/bold]")
            
            # Find and display overlapping sessions
            overlaps = validator.find_overlapping_sessions(sessions)
            if overlaps:
                console.print(f"\n[red]❌ Overlapping Sessions ({len(overlaps)} pairs):[/red]")
                for session1, session2 in overlaps[:5]:  # Show first 5
                    console.print(f"  • {session1.task_name} ({format_datetime(session1.start_time)})")
                    console.print(f"    overlaps with {session2.task_name} ({format_datetime(session2.start_time)})")
                
                if len(overlaps) > 5:
                    console.print(f"  ... and {len(overlaps) - 5} more")
            
            # Show sessions with potential idle time
            idle_sessions = []
            for session in sessions:
                if session.end_time:
                    has_idle, msg = validator.detect_potential_idle_time(session)
                    if has_idle:
                        idle_sessions.append((session, msg))
            
            if idle_sessions:
                console.print(f"\n[yellow]⚠️ Sessions with Potential Idle Time ({len(idle_sessions)}):[/yellow]")
                for session, msg in idle_sessions[:5]:  # Show first 5
                    console.print(f"  • {session.task_name}: {msg}")
                
                if len(idle_sessions) > 5:
                    console.print(f"  ... and {len(idle_sessions) - 5} more")
        
        # Provide recommendations
        console.print("\n[bold]Recommendations:[/bold]")
        recommendations = []
        
        if metrics["overlapping_sessions"] > 0:
            recommendations.append("🔴 Fix overlapping sessions - these indicate data integrity issues")
        
        if metrics["potential_idle_sessions"] > 5:
            recommendations.append("⚠️ Review long sessions for potential idle time")
        
        if metrics["very_short_sessions"] > 10:
            recommendations.append("⚡ Consider consolidating very short sessions")
        
        if score < 70:
            recommendations.append("📊 Consider using more consistent time tracking habits")
        
        if not recommendations:
            recommendations.append("✅ Your time tracking looks accurate! Keep up the good work.")
        
        for rec in recommendations:
            console.print(f"  {rec}")
        
        # Auto-fix option
        if fix_issues and (metrics["overlapping_sessions"] > 0 or metrics["very_short_sessions"] > 0):
            console.print("\n[bold]Auto-Fix Results:[/bold]")
            console.print("[dim]Auto-fix functionality would be implemented here[/dim]")
            console.print("[dim]This could include merging very short consecutive sessions[/dim]")
            console.print("[dim]or flagging overlapping sessions for manual review[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error analyzing time tracking: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def backup(
    output_file: Optional[str] = typer.Argument(None, help="Backup file path (default: clockman_backup_YYYYMMDD.json.gz)"),
    compress: bool = typer.Option(True, "--compress/--no-compress", help="Compress backup file"),
    include_config: bool = typer.Option(True, "--include-config", help="Include configuration in backup"),
) -> None:
    """Create a complete backup of all time tracking data."""
    try:
        time_tracker = get_clockman()
        config_manager = get_config_manager()
        
        # Generate default filename if not provided
        if not output_file:
            from datetime import date
            date_str = date.today().strftime("%Y%m%d")
            extension = ".json.gz" if compress else ".json"
            output_file = f"clockman_backup_{date_str}{extension}"
        
        output_path = Path(output_file)
        
        # Get all data
        sessions = time_tracker.session_repo.get_all_sessions()
        projects = time_tracker.get_all_projects()
        db_stats = time_tracker.get_database_stats()
        
        # Create backup data structure
        backup_data = {
            "backup_info": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "clockman_version": "2.0.0",
                "backup_format_version": "1.0",
                "total_sessions": len(sessions),
                "total_projects": len(projects),
                "database_stats": db_stats
            },
            "sessions": [],
            "projects": []
        }
        
        # Include configuration if requested
        if include_config:
            backup_data["configuration"] = {
                "config_file": str(config_manager.config_file),
                "settings": config_manager._config
            }
        
        # Serialize sessions
        for session in sessions:
            session_data = {
                "id": str(session.id),
                "task_name": session.task_name,
                "description": session.description,
                "project_id": str(session.project_id) if session.project_id else None,
                "tags": session.tags,
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "is_active": session.is_active,
                "metadata": session.metadata
            }
            backup_data["sessions"].append(session_data)
        
        # Serialize projects
        for project in projects:
            project_data = {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "parent_id": str(project.parent_id) if project.parent_id else None,
                "is_active": project.is_active,
                "default_tags": project.default_tags,
                "created_at": project.created_at.isoformat(),
                "metadata": project.metadata
            }
            backup_data["projects"].append(project_data)
        
        # Write backup file
        json_content = json.dumps(backup_data, indent=2, ensure_ascii=False)
        
        if compress:
            with gzip.open(output_path, "wt", encoding="utf-8") as f:
                f.write(json_content)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_content)
        
        # Show results
        file_size = output_path.stat().st_size
        size_str = f"{file_size:,} bytes" if file_size < 1024 else f"{file_size / 1024:.1f} KB"
        
        console.print(f"[green]✓[/green] Backup created: {output_file}")
        console.print(f"[dim]File size: {size_str}[/dim]")
        console.print(f"[dim]Sessions: {len(sessions)}, Projects: {len(projects)}[/dim]")
        console.print(f"[dim]Configuration included: {'Yes' if include_config else 'No'}[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error creating backup: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def restore(
    backup_file: str = typer.Argument(..., help="Backup file path to restore from"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview restore without making changes"),
    merge: bool = typer.Option(False, "--merge", help="Merge with existing data (default: replace)"),
    restore_config: bool = typer.Option(False, "--restore-config", help="Restore configuration settings"),
) -> None:
    """Restore time tracking data from a backup file."""
    try:
        backup_path = Path(backup_file)
        if not backup_path.exists():
            console.print(f"[red]Backup file not found: {backup_file}[/red]")
            raise typer.Exit(1)
        
        # Load backup data
        if backup_path.suffix == '.gz':
            with gzip.open(backup_path, "rt", encoding="utf-8") as f:
                backup_data = json.load(f)
        else:
            with open(backup_path, "r", encoding="utf-8") as f:
                backup_data = json.load(f)
        
        # Validate backup format
        if "backup_info" not in backup_data:
            console.print("[red]Invalid backup file format[/red]")
            raise typer.Exit(1)
        
        backup_info = backup_data["backup_info"]
        console.print(f"[bold]Backup Information:[/bold]")
        console.print(f"[dim]Created: {backup_info.get('created_at', 'Unknown')}[/dim]")
        console.print(f"[dim]Clockman version: {backup_info.get('clockman_version', 'Unknown')}[/dim]")
        console.print(f"[dim]Sessions: {backup_info.get('total_sessions', 0)}[/dim]")
        console.print(f"[dim]Projects: {backup_info.get('total_projects', 0)}[/dim]")
        
        if dry_run:
            console.print("\n[bold]Dry Run - Preview Only:[/bold]")
            console.print(f"Would restore {len(backup_data.get('sessions', []))} sessions")
            console.print(f"Would restore {len(backup_data.get('projects', []))} projects")
            if restore_config and "configuration" in backup_data:
                console.print("Would restore configuration settings")
            return
        
        # Confirm restoration
        if not merge:
            if not Confirm.ask("This will replace all existing data. Continue?"):
                console.print("[dim]Cancelled[/dim]")
                return
        else:
            if not Confirm.ask("This will merge backup data with existing data. Continue?"):
                console.print("[dim]Cancelled[/dim]")
                return
        
        time_tracker = get_clockman()
        config_manager = get_config_manager()
        
        # Clear existing data if not merging
        if not merge:
            console.print("[yellow]Clearing existing data...[/yellow]")
            # This would require implementing clear methods in repositories
            console.print("[dim]Full replacement not yet implemented - using merge mode[/dim]")
        
        # Restore projects first (for foreign key relationships)
        projects_restored = 0
        if "projects" in backup_data:
            console.print(f"[cyan]Restoring {len(backup_data['projects'])} projects...[/cyan]")
            
            for project_data in backup_data["projects"]:
                try:
                    from uuid import UUID
                    project = Project(
                        id=UUID(project_data["id"]),
                        name=project_data["name"],
                        description=project_data.get("description"),
                        parent_id=UUID(project_data["parent_id"]) if project_data.get("parent_id") else None,
                        is_active=project_data.get("is_active", True),
                        default_tags=project_data.get("default_tags", []),
                        created_at=datetime.fromisoformat(project_data["created_at"]),
                        metadata=project_data.get("metadata", {})
                    )
                    
                    # Check if project exists (for merge mode)
                    existing = time_tracker.get_project_by_id(project.id)
                    if not existing:
                        time_tracker.project_repo.create_project(project)
                        projects_restored += 1
                    elif merge:
                        console.print(f"[dim]Skipping existing project: {project.name}[/dim]")
                
                except Exception as e:
                    console.print(f"[yellow]Failed to restore project {project_data.get('name', 'Unknown')}: {e}[/yellow]")
        
        # Restore sessions
        sessions_restored = 0
        if "sessions" in backup_data:
            console.print(f"[cyan]Restoring {len(backup_data['sessions'])} sessions...[/cyan]")
            
            for session_data in backup_data["sessions"]:
                try:
                    from uuid import UUID
                    session = TimeSession(
                        id=UUID(session_data["id"]),
                        task_name=session_data["task_name"],
                        description=session_data.get("description"),
                        project_id=UUID(session_data["project_id"]) if session_data.get("project_id") else None,
                        tags=session_data.get("tags", []),
                        start_time=datetime.fromisoformat(session_data["start_time"]),
                        end_time=datetime.fromisoformat(session_data["end_time"]) if session_data.get("end_time") else None,
                        is_active=session_data.get("is_active", False),
                        metadata=session_data.get("metadata", {})
                    )
                    
                    # Check if session exists (for merge mode)
                    existing = time_tracker.get_session_by_id(session.id)
                    if not existing:
                        time_tracker.session_repo.create_session(session)
                        sessions_restored += 1
                    elif merge:
                        console.print(f"[dim]Skipping existing session: {session.task_name}[/dim]")
                
                except Exception as e:
                    console.print(f"[yellow]Failed to restore session: {e}[/yellow]")
        
        # Restore configuration
        if restore_config and "configuration" in backup_data:
            console.print("[cyan]Restoring configuration...[/cyan]")
            config_data = backup_data["configuration"]["settings"]
            for key, value in config_data.items():
                try:
                    config_manager.set(key, value)
                except Exception as e:
                    console.print(f"[yellow]Failed to restore config {key}: {e}[/yellow]")
        
        # Show results
        console.print(f"\n[green]✓[/green] Restore completed!")
        console.print(f"[dim]Projects restored: {projects_restored}[/dim]")
        console.print(f"[dim]Sessions restored: {sessions_restored}[/dim]")
        
        if restore_config and "configuration" in backup_data:
            console.print(f"[dim]Configuration restored: Yes[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error restoring backup: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show Clockman version information."""
    from .. import __version__

    console.print(f"Clockman version {__version__}")


def _parse_date_range(start_date: Optional[str], end_date: Optional[str]) -> tuple[datetime, datetime]:
    """Parse start and end date strings into datetime objects."""
    today = date.today()
    
    # Parse start date
    if start_date is None or start_date == "today":
        start_dt = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    elif start_date == "week":
        # Start of current week (Monday)
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    elif start_date == "month":
        # Start of current month
        month_start = today.replace(day=1)
        start_dt = datetime.combine(month_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    else:
        try:
            start_date_parsed = datetime.strptime(start_date, "%Y-%m-%d").date()
            start_dt = datetime.combine(start_date_parsed, datetime.min.time()).replace(tzinfo=timezone.utc)
        except ValueError:
            raise typer.BadParameter(f"Invalid start date format: {start_date}. Use YYYY-MM-DD, 'today', 'week', or 'month'")
    
    # Parse end date
    if end_date is None:
        if start_date in ["week", None]:
            # Default to end of today
            end_dt = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
        elif start_date == "month":
            # End of current month
            if today.month == 12:
                next_month = today.replace(year=today.year + 1, month=1, day=1)
            else:
                next_month = today.replace(month=today.month + 1, day=1)
            end_dt = datetime.combine(next_month - timedelta(days=1), datetime.max.time()).replace(tzinfo=timezone.utc)
        else:
            # Same day as start
            end_dt = datetime.combine(start_dt.date(), datetime.max.time()).replace(tzinfo=timezone.utc)
    else:
        try:
            end_date_parsed = datetime.strptime(end_date, "%Y-%m-%d").date()
            end_dt = datetime.combine(end_date_parsed, datetime.max.time()).replace(tzinfo=timezone.utc)
        except ValueError:
            raise typer.BadParameter(f"Invalid end date format: {end_date}. Use YYYY-MM-DD")
    
    if start_dt > end_dt:
        raise typer.BadParameter("Start date must be before or equal to end date")
    
    return start_dt, end_dt


def _display_date_summary(entries, show_details: bool) -> None:
    """Display summary grouped by date."""
    from collections import defaultdict
    
    date_data = defaultdict(lambda: {"duration": 0.0, "entries": []})
    
    for entry in entries:
        entry_date = entry.start_time.date()
        duration = (entry.end_time - entry.start_time).total_seconds()
        date_data[entry_date]["duration"] += duration
        date_data[entry_date]["entries"].append(entry)
    
    # Create summary table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Date", style="cyan")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Sessions", justify="center")
    if show_details:
        table.add_column("Tasks", style="dim")
    
    total_duration = 0.0
    for entry_date in sorted(date_data.keys()):
        data = date_data[entry_date]
        duration_str = format_duration(timedelta(seconds=data["duration"]))
        session_count = len(data["entries"])
        total_duration += data["duration"]
        
        row = [entry_date.strftime("%Y-%m-%d"), duration_str, str(session_count)]
        
        if show_details:
            task_names = list(set(e.task_name for e in data["entries"]))
            tasks_str = ", ".join(task_names[:3])
            if len(task_names) > 3:
                tasks_str += f" (+{len(task_names)-3} more)"
            row.append(tasks_str)
        
        table.add_row(*row)
    
    console.print(table)
    console.print(f"\n[bold]Total: {format_duration(timedelta(seconds=total_duration))}[/bold]")


def _display_task_summary(entries, show_details: bool) -> None:
    """Display summary grouped by task."""
    from collections import defaultdict
    
    task_data = defaultdict(lambda: {"duration": 0.0, "sessions": 0, "tags": set(), "dates": set()})
    
    for entry in entries:
        duration = (entry.end_time - entry.start_time).total_seconds()
        task_data[entry.task_name]["duration"] += duration
        task_data[entry.task_name]["sessions"] += 1
        task_data[entry.task_name]["tags"].update(entry.tags)
        task_data[entry.task_name]["dates"].add(entry.start_time.date())
    
    # Create summary table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Task", style="bold")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Sessions", justify="center")
    table.add_column("Avg/Session", justify="right", style="cyan")
    if show_details:
        table.add_column("Tags", style="yellow")
        table.add_column("Days", justify="center", style="dim")
    
    # Sort by duration (descending)
    sorted_tasks = sorted(task_data.items(), key=lambda x: x[1]["duration"], reverse=True)
    
    total_duration = 0.0
    for task_name, data in sorted_tasks:
        duration_str = format_duration(timedelta(seconds=data["duration"]))
        avg_duration = data["duration"] / data["sessions"]
        avg_str = format_duration(timedelta(seconds=avg_duration))
        total_duration += data["duration"]
        
        row = [task_name, duration_str, str(data["sessions"]), avg_str]
        
        if show_details:
            tags_str = ", ".join(sorted(data["tags"])) if data["tags"] else ""
            days_count = len(data["dates"])
            row.extend([tags_str, str(days_count)])
        
        table.add_row(*row)
    
    console.print(table)
    console.print(f"\n[bold]Total: {format_duration(timedelta(seconds=total_duration))}[/bold]")


def _display_tag_summary(entries, show_details: bool) -> None:
    """Display summary grouped by tag."""
    from collections import defaultdict
    
    tag_data = defaultdict(lambda: {"duration": 0.0, "sessions": 0, "tasks": set()})
    
    # Handle entries without tags
    no_tag_duration = 0.0
    no_tag_sessions = 0
    
    for entry in entries:
        duration = (entry.end_time - entry.start_time).total_seconds()
        
        if not entry.tags:
            no_tag_duration += duration
            no_tag_sessions += 1
        else:
            for tag in entry.tags:
                tag_data[tag]["duration"] += duration
                tag_data[tag]["sessions"] += 1
                tag_data[tag]["tasks"].add(entry.task_name)
    
    # Create summary table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Tag", style="yellow")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Sessions", justify="center")
    if show_details:
        table.add_column("Tasks", justify="center", style="dim")
        table.add_column("Task Names", style="dim")
    
    # Sort by duration (descending)
    sorted_tags = sorted(tag_data.items(), key=lambda x: x[1]["duration"], reverse=True)
    
    total_duration = 0.0
    for tag, data in sorted_tags:
        duration_str = format_duration(timedelta(seconds=data["duration"]))
        total_duration += data["duration"]
        
        row = [tag, duration_str, str(data["sessions"])]
        
        if show_details:
            task_count = len(data["tasks"])
            task_list = ", ".join(list(data["tasks"])[:3])
            if task_count > 3:
                task_list += f" (+{task_count-3} more)"
            row.extend([str(task_count), task_list])
        
        table.add_row(*row)
    
    # Add untagged entries if any
    if no_tag_sessions > 0:
        duration_str = format_duration(timedelta(seconds=no_tag_duration))
        total_duration += no_tag_duration
        row = ["[no tags]", duration_str, str(no_tag_sessions)]
        if show_details:
            row.extend(["", ""])
        table.add_row(*row)
    
    console.print(table)
    console.print(f"\n[bold]Total: {format_duration(timedelta(seconds=total_duration))}[/bold]")


def _display_week_summary(entries, show_details: bool) -> None:
    """Display summary grouped by week."""
    from collections import defaultdict
    
    def get_week_start(dt):
        """Get the Monday of the week containing the given date."""
        days_since_monday = dt.weekday()
        return dt - timedelta(days=days_since_monday)
    
    week_data = defaultdict(lambda: {"duration": 0.0, "entries": []})
    
    for entry in entries:
        week_start = get_week_start(entry.start_time.date())
        duration = (entry.end_time - entry.start_time).total_seconds()
        week_data[week_start]["duration"] += duration
        week_data[week_start]["entries"].append(entry)
    
    # Create summary table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Week Starting", style="cyan")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Sessions", justify="center")
    table.add_column("Days Active", justify="center", style="dim")
    if show_details:
        table.add_column("Top Tasks", style="dim")
    
    total_duration = 0.0
    for week_start in sorted(week_data.keys()):
        data = week_data[week_start]
        duration_str = format_duration(timedelta(seconds=data["duration"]))
        session_count = len(data["entries"])
        total_duration += data["duration"]
        
        # Calculate days active
        active_days = len(set(e.start_time.date() for e in data["entries"]))
        
        week_end = week_start + timedelta(days=6)
        week_range = f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
        
        row = [week_range, duration_str, str(session_count), str(active_days)]
        
        if show_details:
            task_counts = defaultdict(float)
            for entry in data["entries"]:
                task_counts[entry.task_name] += (entry.end_time - entry.start_time).total_seconds()
            
            top_tasks = sorted(task_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            tasks_str = ", ".join(f"{task}" for task, _ in top_tasks)
            row.append(tasks_str)
        
        table.add_row(*row)
    
    console.print(table)
    console.print(f"\n[bold]Total: {format_duration(timedelta(seconds=total_duration))}[/bold]")


def _display_month_summary(entries, show_details: bool) -> None:
    """Display summary grouped by month."""
    from collections import defaultdict
    
    month_data = defaultdict(lambda: {"duration": 0.0, "entries": []})
    
    for entry in entries:
        month_start = entry.start_time.date().replace(day=1)
        duration = (entry.end_time - entry.start_time).total_seconds()
        month_data[month_start]["duration"] += duration
        month_data[month_start]["entries"].append(entry)
    
    # Create summary table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Month", style="cyan")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Sessions", justify="center")
    table.add_column("Days Active", justify="center", style="dim")
    if show_details:
        table.add_column("Top Tasks", style="dim")
    
    total_duration = 0.0
    for month_start in sorted(month_data.keys()):
        data = month_data[month_start]
        duration_str = format_duration(timedelta(seconds=data["duration"]))
        session_count = len(data["entries"])
        total_duration += data["duration"]
        
        # Calculate days active
        active_days = len(set(e.start_time.date() for e in data["entries"]))
        
        month_name = month_start.strftime('%Y-%m (%B)')
        
        row = [month_name, duration_str, str(session_count), str(active_days)]
        
        if show_details:
            task_counts = defaultdict(float)
            for entry in data["entries"]:
                task_counts[entry.task_name] += (entry.end_time - entry.start_time).total_seconds()
            
            top_tasks = sorted(task_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            tasks_str = ", ".join(f"{task}" for task, _ in top_tasks)
            row.append(tasks_str)
        
        table.add_row(*row)
    
    console.print(table)
    console.print(f"\n[bold]Total: {format_duration(timedelta(seconds=total_duration))}[/bold]")


def _display_raw_summary(entries, show_details: bool) -> None:
    """Display raw entries summary with all session information."""
    # Create detailed table for raw data
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Task", style="bold")
    table.add_column("Start", style="dim")
    table.add_column("End", style="dim") 
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Tags", style="cyan")
    if show_details:
        table.add_column("Description", style="dim")
        table.add_column("Active", style="yellow")
        table.add_column("Metadata", style="dim")
    
    total_duration = 0.0
    for entry in entries:
        if entry.end_time:
            duration = (entry.end_time - entry.start_time).total_seconds()
            total_duration += duration
            duration_str = format_duration(timedelta(seconds=duration))
            end_str = format_datetime(entry.end_time)
        else:
            duration_str = "[yellow]Active[/yellow]"
            end_str = "[yellow]Running[/yellow]"
        
        tags_str = ", ".join(entry.tags) if entry.tags else ""
        
        row = [
            str(entry.id)[:8],  # Show first 8 chars of UUID
            entry.task_name,
            format_datetime(entry.start_time),
            end_str,
            duration_str,
            tags_str
        ]
        
        if show_details:
            description = entry.description[:50] + "..." if entry.description and len(entry.description) > 50 else (entry.description or "")
            
            # Show clean metadata (excluding our internal timestamps)
            clean_metadata = {k: v for k, v in entry.metadata.items() 
                             if k not in ["created_at", "updated_at"]}
            metadata_str = json.dumps(clean_metadata) if clean_metadata else ""
            if len(metadata_str) > 30:
                metadata_str = metadata_str[:27] + "..."
            
            row.extend([
                description,
                "Yes" if entry.is_active else "No", 
                metadata_str
            ])
        
        table.add_row(*row)
    
    console.print(table)
    console.print(f"\n[bold]Total Sessions: {len(entries)}[/bold]")
    if total_duration > 0:
        console.print(f"[bold]Total Duration: {format_duration(timedelta(seconds=total_duration))}[/bold]")


def _export_to_csv(entries, file_path: Path, group_by: str) -> None:
    """Export entries to CSV file with comprehensive data."""
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        if group_by == "raw":
            # Export complete raw entries with ALL database fields
            fieldnames = [
                'id',
                'task_name',
                'description',
                'tags',
                'start_time',
                'end_time',
                'duration_seconds',
                'duration_formatted',
                'is_active',
                'metadata',
                'created_at',
                'updated_at'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for entry in entries:
                duration = (entry.end_time - entry.start_time).total_seconds() if entry.end_time else 0
                
                # Get the database timestamps from metadata
                created_at = entry.metadata.get("created_at", "")
                updated_at = entry.metadata.get("updated_at", "")
                
                # Remove database timestamps from metadata for clean export
                export_metadata = {k: v for k, v in entry.metadata.items() 
                                 if k not in ["created_at", "updated_at"]}
                
                writer.writerow({
                    'id': str(entry.id),
                    'task_name': entry.task_name,
                    'description': entry.description or '',
                    'tags': ','.join(entry.tags),
                    'start_time': entry.start_time.isoformat(),
                    'end_time': entry.end_time.isoformat() if entry.end_time else '',
                    'duration_seconds': duration,
                    'duration_formatted': format_duration(timedelta(seconds=duration)) if duration > 0 else '',
                    'is_active': entry.is_active,
                    'metadata': json.dumps(export_metadata) if export_metadata else '',
                    'created_at': created_at,
                    'updated_at': updated_at
                })
        else:
            # Export aggregated data based on group_by
            if group_by == "task":
                _export_task_csv(entries, csvfile)
            elif group_by == "date":
                _export_date_csv(entries, csvfile)
            elif group_by == "tag":
                _export_tag_csv(entries, csvfile)
            elif group_by == "week":
                _export_week_csv(entries, csvfile)
            elif group_by == "month":
                _export_month_csv(entries, csvfile)


def _export_task_csv(entries, csvfile) -> None:
    """Export task-grouped data to CSV with enhanced information."""
    from collections import defaultdict
    
    task_data = defaultdict(lambda: {
        "duration": 0.0, 
        "sessions": 0, 
        "tags": set(),
        "first_session": None,
        "last_session": None,
        "descriptions": set(),
        "session_ids": []
    })
    
    for entry in entries:
        duration = (entry.end_time - entry.start_time).total_seconds()
        task_name = entry.task_name
        task_data[task_name]["duration"] += duration
        task_data[task_name]["sessions"] += 1
        task_data[task_name]["tags"].update(entry.tags)
        task_data[task_name]["session_ids"].append(str(entry.id))
        
        if entry.description:
            task_data[task_name]["descriptions"].add(entry.description)
        
        # Track first and last session times
        if not task_data[task_name]["first_session"] or entry.start_time < task_data[task_name]["first_session"]:
            task_data[task_name]["first_session"] = entry.start_time
        if not task_data[task_name]["last_session"] or entry.start_time > task_data[task_name]["last_session"]:
            task_data[task_name]["last_session"] = entry.start_time
    
    fieldnames = [
        'task_name', 
        'duration_seconds', 
        'duration_formatted', 
        'session_count', 
        'average_session_seconds',
        'average_session_formatted',
        'tags', 
        'descriptions',
        'first_session',
        'last_session',
        'session_ids'
    ]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    
    for task_name, data in sorted(task_data.items(), key=lambda x: x[1]["duration"], reverse=True):
        avg_duration = data["duration"] / data["sessions"]
        writer.writerow({
            'task_name': task_name,
            'duration_seconds': data["duration"],
            'duration_formatted': format_duration(timedelta(seconds=data["duration"])),
            'session_count': data["sessions"],
            'average_session_seconds': avg_duration,
            'average_session_formatted': format_duration(timedelta(seconds=avg_duration)),
            'tags': ','.join(sorted(data["tags"])),
            'descriptions': ' | '.join(sorted(data["descriptions"])),
            'first_session': data["first_session"].isoformat() if data["first_session"] else '',
            'last_session': data["last_session"].isoformat() if data["last_session"] else '',
            'session_ids': ','.join(data["session_ids"])
        })


def _export_date_csv(entries, csvfile) -> None:
    """Export date-grouped data to CSV with enhanced information."""
    from collections import defaultdict
    
    date_data = defaultdict(lambda: {
        "duration": 0.0, 
        "sessions": 0,
        "tasks": set(),
        "tags": set(),
        "session_ids": [],
        "first_session": None,
        "last_session": None
    })
    
    for entry in entries:
        entry_date = entry.start_time.date()
        duration = (entry.end_time - entry.start_time).total_seconds()
        date_data[entry_date]["duration"] += duration
        date_data[entry_date]["sessions"] += 1
        date_data[entry_date]["tasks"].add(entry.task_name)
        date_data[entry_date]["tags"].update(entry.tags)
        date_data[entry_date]["session_ids"].append(str(entry.id))
        
        # Track first and last session times of the day
        if not date_data[entry_date]["first_session"] or entry.start_time < date_data[entry_date]["first_session"]:
            date_data[entry_date]["first_session"] = entry.start_time
        if not date_data[entry_date]["last_session"] or entry.start_time > date_data[entry_date]["last_session"]:
            date_data[entry_date]["last_session"] = entry.start_time
    
    fieldnames = [
        'date', 
        'weekday',
        'duration_seconds', 
        'duration_formatted', 
        'session_count',
        'unique_tasks',
        'task_names',
        'unique_tags',
        'tag_names',
        'first_session_time',
        'last_session_time',
        'session_ids'
    ]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    
    for entry_date in sorted(date_data.keys()):
        data = date_data[entry_date]
        writer.writerow({
            'date': entry_date.strftime('%Y-%m-%d'),
            'weekday': entry_date.strftime('%A'),
            'duration_seconds': data["duration"],
            'duration_formatted': format_duration(timedelta(seconds=data["duration"])),
            'session_count': data["sessions"],
            'unique_tasks': len(data["tasks"]),
            'task_names': ', '.join(sorted(data["tasks"])),
            'unique_tags': len(data["tags"]),
            'tag_names': ', '.join(sorted(data["tags"])),
            'first_session_time': data["first_session"].isoformat() if data["first_session"] else '',
            'last_session_time': data["last_session"].isoformat() if data["last_session"] else '',
            'session_ids': ','.join(data["session_ids"])
        })


def _export_tag_csv(entries, csvfile) -> None:
    """Export tag-grouped data to CSV with enhanced information."""
    from collections import defaultdict
    
    tag_data = defaultdict(lambda: {
        "duration": 0.0, 
        "sessions": 0, 
        "tasks": set(),
        "session_ids": [],
        "first_session": None,
        "last_session": None,
        "dates": set()
    })
    
    for entry in entries:
        duration = (entry.end_time - entry.start_time).total_seconds()
        entry_date = entry.start_time.date()
        
        if not entry.tags:
            tag_key = "[no_tags]"
            tag_data[tag_key]["duration"] += duration
            tag_data[tag_key]["sessions"] += 1
            tag_data[tag_key]["tasks"].add(entry.task_name)
            tag_data[tag_key]["session_ids"].append(str(entry.id))
            tag_data[tag_key]["dates"].add(entry_date)
            
            # Track first and last session times
            if not tag_data[tag_key]["first_session"] or entry.start_time < tag_data[tag_key]["first_session"]:
                tag_data[tag_key]["first_session"] = entry.start_time
            if not tag_data[tag_key]["last_session"] or entry.start_time > tag_data[tag_key]["last_session"]:
                tag_data[tag_key]["last_session"] = entry.start_time
        else:
            for tag in entry.tags:
                tag_data[tag]["duration"] += duration
                tag_data[tag]["sessions"] += 1
                tag_data[tag]["tasks"].add(entry.task_name)
                tag_data[tag]["session_ids"].append(str(entry.id))
                tag_data[tag]["dates"].add(entry_date)
                
                # Track first and last session times
                if not tag_data[tag]["first_session"] or entry.start_time < tag_data[tag]["first_session"]:
                    tag_data[tag]["first_session"] = entry.start_time
                if not tag_data[tag]["last_session"] or entry.start_time > tag_data[tag]["last_session"]:
                    tag_data[tag]["last_session"] = entry.start_time
    
    fieldnames = [
        'tag', 
        'duration_seconds', 
        'duration_formatted', 
        'session_count', 
        'unique_tasks',
        'task_names',
        'unique_dates',
        'average_session_seconds',
        'average_session_formatted',
        'first_session',
        'last_session',
        'session_ids'
    ]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    
    for tag in sorted(tag_data.keys(), key=lambda x: tag_data[x]["duration"], reverse=True):
        data = tag_data[tag]
        avg_duration = data["duration"] / data["sessions"] if data["sessions"] > 0 else 0
        writer.writerow({
            'tag': tag,
            'duration_seconds': data["duration"],
            'duration_formatted': format_duration(timedelta(seconds=data["duration"])),
            'session_count': data["sessions"],
            'unique_tasks': len(data["tasks"]),
            'task_names': ', '.join(sorted(data["tasks"])),
            'unique_dates': len(data["dates"]),
            'average_session_seconds': avg_duration,
            'average_session_formatted': format_duration(timedelta(seconds=avg_duration)),
            'first_session': data["first_session"].isoformat() if data["first_session"] else '',
            'last_session': data["last_session"].isoformat() if data["last_session"] else '',
            'session_ids': ','.join(data["session_ids"])
        })


def _export_week_csv(entries, csvfile) -> None:
    """Export week-grouped data to CSV with enhanced information."""
    from collections import defaultdict
    
    def get_week_start(dt):
        days_since_monday = dt.weekday()
        return dt - timedelta(days=days_since_monday)
    
    week_data = defaultdict(lambda: {
        "duration": 0.0, 
        "sessions": 0,
        "tasks": set(),
        "tags": set(),
        "session_ids": [],
        "dates": set(),
        "first_session": None,
        "last_session": None
    })
    
    for entry in entries:
        week_start = get_week_start(entry.start_time.date())
        duration = (entry.end_time - entry.start_time).total_seconds()
        week_data[week_start]["duration"] += duration
        week_data[week_start]["sessions"] += 1
        week_data[week_start]["tasks"].add(entry.task_name)
        week_data[week_start]["tags"].update(entry.tags)
        week_data[week_start]["session_ids"].append(str(entry.id))
        week_data[week_start]["dates"].add(entry.start_time.date())
        
        # Track first and last session times
        if not week_data[week_start]["first_session"] or entry.start_time < week_data[week_start]["first_session"]:
            week_data[week_start]["first_session"] = entry.start_time
        if not week_data[week_start]["last_session"] or entry.start_time > week_data[week_start]["last_session"]:
            week_data[week_start]["last_session"] = entry.start_time
    
    fieldnames = [
        'week_start', 
        'week_end', 
        'week_number',
        'year',
        'duration_seconds', 
        'duration_formatted', 
        'session_count',
        'unique_tasks',
        'task_names',
        'unique_tags', 
        'tag_names',
        'active_days',
        'first_session',
        'last_session',
        'session_ids'
    ]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    
    for week_start in sorted(week_data.keys()):
        data = week_data[week_start]
        week_end = week_start + timedelta(days=6)
        year, week_num, _ = week_start.isocalendar()
        
        writer.writerow({
            'week_start': week_start.strftime('%Y-%m-%d'),
            'week_end': week_end.strftime('%Y-%m-%d'),
            'week_number': week_num,
            'year': year,
            'duration_seconds': data["duration"],
            'duration_formatted': format_duration(timedelta(seconds=data["duration"])),
            'session_count': data["sessions"],
            'unique_tasks': len(data["tasks"]),
            'task_names': ', '.join(sorted(data["tasks"])),
            'unique_tags': len(data["tags"]),
            'tag_names': ', '.join(sorted(data["tags"])),
            'active_days': len(data["dates"]),
            'first_session': data["first_session"].isoformat() if data["first_session"] else '',
            'last_session': data["last_session"].isoformat() if data["last_session"] else '',
            'session_ids': ','.join(data["session_ids"])
        })


def _export_month_csv(entries, csvfile) -> None:
    """Export month-grouped data to CSV with enhanced information."""
    from collections import defaultdict
    import calendar
    
    month_data = defaultdict(lambda: {
        "duration": 0.0, 
        "sessions": 0,
        "tasks": set(),
        "tags": set(),
        "session_ids": [],
        "dates": set(),
        "first_session": None,
        "last_session": None
    })
    
    for entry in entries:
        month_start = entry.start_time.date().replace(day=1)
        duration = (entry.end_time - entry.start_time).total_seconds()
        month_data[month_start]["duration"] += duration
        month_data[month_start]["sessions"] += 1
        month_data[month_start]["tasks"].add(entry.task_name)
        month_data[month_start]["tags"].update(entry.tags)
        month_data[month_start]["session_ids"].append(str(entry.id))
        month_data[month_start]["dates"].add(entry.start_time.date())
        
        # Track first and last session times
        if not month_data[month_start]["first_session"] or entry.start_time < month_data[month_start]["first_session"]:
            month_data[month_start]["first_session"] = entry.start_time
        if not month_data[month_start]["last_session"] or entry.start_time > month_data[month_start]["last_session"]:
            month_data[month_start]["last_session"] = entry.start_time
    
    fieldnames = [
        'month', 
        'month_name',
        'year',
        'duration_seconds', 
        'duration_formatted', 
        'session_count',
        'unique_tasks',
        'task_names',
        'unique_tags',
        'tag_names',
        'active_days',
        'first_session',
        'last_session',
        'session_ids'
    ]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    
    for month_start in sorted(month_data.keys()):
        data = month_data[month_start]
        month_name = calendar.month_name[month_start.month]
        
        writer.writerow({
            'month': month_start.strftime('%Y-%m'),
            'month_name': f"{month_name} {month_start.year}",
            'year': month_start.year,
            'duration_seconds': data["duration"],
            'duration_formatted': format_duration(timedelta(seconds=data["duration"])),
            'session_count': data["sessions"],
            'unique_tasks': len(data["tasks"]),
            'task_names': ', '.join(sorted(data["tasks"])),
            'unique_tags': len(data["tags"]),
            'tag_names': ', '.join(sorted(data["tags"])),
            'active_days': len(data["dates"]),
            'first_session': data["first_session"].isoformat() if data["first_session"] else '',
            'last_session': data["last_session"].isoformat() if data["last_session"] else '',
            'session_ids': ','.join(data["session_ids"])
        })


def _export_json(entries: List, output_path: Path, pretty: bool, compress: bool) -> None:
    """Export entries to JSON format with comprehensive data structure."""
    # Create export metadata
    export_data = {
        "export_info": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "clockman_version": "2.0.0",  # Phase 3 version
            "total_sessions": len(entries),
            "format_version": "1.0"
        },
        "sessions": [],
        "statistics": {}
    }
    
    # Convert sessions to export format
    for entry in entries:
        session_data = {
            "id": str(entry.id),
            "task_name": entry.task_name,
            "description": entry.description,
            "tags": entry.tags,
            "start_time": entry.start_time.isoformat(),
            "end_time": entry.end_time.isoformat() if entry.end_time else None,
            "duration_seconds": (entry.end_time - entry.start_time).total_seconds() if entry.end_time else None,
            "is_active": entry.is_active,
            "metadata": entry.metadata
        }
        export_data["sessions"].append(session_data)
    
    # Calculate statistics
    completed_sessions = [s for s in entries if s.end_time]
    if completed_sessions:
        total_duration = sum((s.end_time - s.start_time).total_seconds() for s in completed_sessions)
        export_data["statistics"] = {
            "total_sessions": len(entries),
            "completed_sessions": len(completed_sessions),
            "active_sessions": len([s for s in entries if s.is_active]),
            "total_duration_seconds": total_duration,
            "total_duration_formatted": format_duration(timedelta(seconds=total_duration)),
            "unique_tasks": len(set(s.task_name for s in completed_sessions)),
            "unique_tags": len(set(tag for s in completed_sessions for tag in s.tags)),
            "date_range": {
                "first_session": min(s.start_time for s in completed_sessions).isoformat(),
                "last_session": max(s.start_time for s in completed_sessions).isoformat()
            }
        }
    
    # Write to file
    json_content = json.dumps(export_data, indent=2 if pretty else None, ensure_ascii=False)
    
    if compress:
        with gzip.open(f"{output_path}.gz", "wt", encoding="utf-8") as f:
            f.write(json_content)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_content)


def _export_ical(entries: List, output_path: Path, compress: bool) -> None:
    """Export entries to iCal format for calendar integration."""
    # iCal header
    ical_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Clockman//Time Tracking//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Clockman Time Tracking",
        f"X-WR-CALDESC:Time tracking sessions exported from Clockman",
    ]
    
    # Add events for completed sessions
    for entry in entries:
        if entry.end_time:  # Only export completed sessions
            # Generate unique event ID
            event_id = f"{entry.id}@clockman"
            
            # Format dates for iCal (UTC format)
            start_utc = entry.start_time.strftime("%Y%m%dT%H%M%SZ")
            end_utc = entry.end_time.strftime("%Y%m%dT%H%M%SZ")
            created_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            
            # Build event
            ical_lines.extend([
                "BEGIN:VEVENT",
                f"UID:{event_id}",
                f"DTSTART:{start_utc}",
                f"DTEND:{end_utc}",
                f"DTSTAMP:{created_utc}",
                f"SUMMARY:{_escape_ical_text(entry.task_name)}",
                f"DESCRIPTION:{_escape_ical_text(_build_ical_description(entry))}",
                f"CATEGORIES:{','.join(_escape_ical_text(tag) for tag in entry.tags)}",
                "TRANSP:OPAQUE",
                "STATUS:CONFIRMED",
                "END:VEVENT"
            ])
    
    ical_lines.append("END:VCALENDAR")
    ical_content = "\n".join(ical_lines)
    
    # Write to file
    if compress:
        with gzip.open(f"{output_path}.gz", "wt", encoding="utf-8") as f:
            f.write(ical_content)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ical_content)


def _export_sql(entries: List, output_path: Path, compress: bool) -> None:
    """Export entries as SQL INSERT statements."""
    sql_lines = [
        "-- Clockman Time Tracking Data Export",
        f"-- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"-- Total sessions: {len(entries)}",
        "",
        "-- Table schema",
        "CREATE TABLE IF NOT EXISTS sessions (",
        "    id TEXT PRIMARY KEY,",
        "    task_name TEXT NOT NULL,",
        "    description TEXT,",
        "    tags TEXT,",
        "    start_time TEXT NOT NULL,",
        "    end_time TEXT,",
        "    is_active BOOLEAN NOT NULL DEFAULT 1,",
        "    metadata TEXT,",
        "    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,",
        "    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
        ");",
        "",
        "-- Data",
        "BEGIN TRANSACTION;",
    ]
    
    # Add INSERT statements
    for entry in entries:
        values = (
            str(entry.id),
            entry.task_name,
            entry.description or "",
            json.dumps(entry.tags),
            entry.start_time.isoformat(),
            entry.end_time.isoformat() if entry.end_time else "",
            entry.is_active,
            json.dumps(entry.metadata),
            entry.metadata.get("created_at", datetime.now(timezone.utc).isoformat()),
            entry.metadata.get("updated_at", datetime.now(timezone.utc).isoformat())
        )
        
        # Escape single quotes in values
        escaped_values = [str(v).replace("'", "''") if v is not None else "NULL" for v in values]
        sql_lines.append(
            f"INSERT INTO sessions (id, task_name, description, tags, start_time, end_time, is_active, metadata, created_at, updated_at) "
            f"VALUES ('{escaped_values[0]}', '{escaped_values[1]}', '{escaped_values[2]}', '{escaped_values[3]}', "
            f"'{escaped_values[4]}', '{escaped_values[5]}', {escaped_values[6]}, '{escaped_values[7]}', "
            f"'{escaped_values[8]}', '{escaped_values[9]}');"
        )
    
    sql_lines.extend(["", "COMMIT;"])
    sql_content = "\n".join(sql_lines)
    
    # Write to file
    if compress:
        with gzip.open(f"{output_path}.gz", "wt", encoding="utf-8") as f:
            f.write(sql_content)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(sql_content)


def _escape_ical_text(text: str) -> str:
    """Escape text for iCal format."""
    if not text:
        return ""
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _build_ical_description(entry) -> str:
    """Build iCal event description from session data."""
    desc_parts = []
    
    if entry.description:
        desc_parts.append(f"Description: {entry.description}")
    
    if entry.tags:
        desc_parts.append(f"Tags: {', '.join(entry.tags)}")
    
    if entry.end_time:
        duration = entry.end_time - entry.start_time
        desc_parts.append(f"Duration: {format_duration(duration)}")
    
    desc_parts.append(f"Session ID: {entry.id}")
    
    return "\\n".join(desc_parts)


def _perform_search(entries: List, query: str, field: str, case_sensitive: bool, regex: bool) -> List:
    """Perform advanced search on entries."""
    results = []
    
    # Prepare query for matching
    if regex:
        try:
            pattern = re.compile(query, 0 if case_sensitive else re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        match_func = pattern.search
    else:
        if not case_sensitive:
            query = query.lower()
        match_func = lambda text: query in (text if case_sensitive else text.lower())
    
    for entry in entries:
        matched = False
        
        if field == "all" or field == "task":
            if match_func(entry.task_name):
                matched = True
        
        if (field == "all" or field == "description") and entry.description:
            if match_func(entry.description):
                matched = True
        
        if field == "all" or field == "tag":
            for tag in entry.tags:
                if match_func(tag):
                    matched = True
                    break
        
        if matched:
            results.append(entry)
    
    return results


def _highlight_match(text: str, query: str, case_sensitive: bool) -> str:
    """Highlight search matches in text for display."""
    if not text or not query:
        return text
    
    # Simple highlighting for non-regex searches
    if not case_sensitive:
        query_lower = query.lower()
        text_lower = text.lower()
        start = text_lower.find(query_lower)
    else:
        start = text.find(query)
    
    if start == -1:
        return text
    
    # Highlight the match
    end = start + len(query)
    highlighted = f"{text[:start]}[bold yellow]{text[start:end]}[/bold yellow]{text[end:]}"
    return highlighted


# ===== INTEGRATION COMMANDS =====

@app.command()
def webhook(
    action: str = typer.Argument(
        ..., 
        help="Action to perform: list, add, remove, enable, disable, test, config, history, templates"
    ),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Webhook name"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Webhook URL"),
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Webhook template (slack, discord, generic, task_tracker, analytics)"),
    events: Optional[str] = typer.Option(None, "--events", "-e", help="Comma-separated list of event types to subscribe to"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Webhook description"),
    timeout: Optional[float] = typer.Option(None, "--timeout", help="Request timeout in seconds"),
    retries: Optional[int] = typer.Option(None, "--retries", help="Maximum retry attempts"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Load webhook configuration from JSON file"),
    webhook_id: Optional[str] = typer.Option(None, "--id", help="Webhook ID (for remove, enable, disable, test actions)"),
) -> None:
    """Manage webhooks for external system integration."""
    try:
        from ..integrations.manager import IntegrationManager
        from ..integrations.config import IntegrationConfigManager
        from ..integrations.examples.webhook_example import create_webhook_from_template, load_webhook_config_from_file
        from ..integrations.webhooks.models import WebhookConfig, RetryPolicy
        from ..integrations.events.events import EventType
        from ..utils.config import get_config_manager
        from uuid import UUID, uuid4
        from pathlib import Path
        import json
        
        # Initialize integration manager
        config_mgr = get_config_manager()
        data_dir = config_mgr.get_data_dir()
        integration_mgr = IntegrationManager(data_dir)
        
        if not integration_mgr._initialized:
            integration_mgr.initialize()
        
        if action == "list":
            webhooks = integration_mgr.list_webhooks()
            
            if not webhooks:
                console.print("[dim]No webhooks configured[/dim]")
                return
            
            table = Table(show_header=True, header_style="bold")
            table.add_column("Name", style="bold")
            table.add_column("URL", style="cyan", max_width=50)
            table.add_column("Status", justify="center")
            table.add_column("Events", style="yellow")
            table.add_column("ID", style="dim", width=8)
            
            for webhook in webhooks:
                status = "[green]Active[/green]" if webhook.is_active() else "[red]Disabled[/red]"
                events_str = ", ".join(event.value for event in webhook.event_types)
                if len(events_str) > 30:
                    events_str = events_str[:27] + "..."
                
                table.add_row(
                    webhook.name,
                    str(webhook.url),
                    status,
                    events_str,
                    str(webhook.id)[:8]
                )
            
            console.print(f"[bold]Webhooks ({len(webhooks)} total)[/bold]")
            console.print(table)
        
        elif action == "add":
            if not name:
                console.print("[red]Webhook name is required[/red]")
                raise typer.Exit(1)
            
            if config_file:
                # Load from configuration file
                config_path = Path(config_file)
                try:
                    webhook_config = load_webhook_config_from_file(config_path)
                    webhook_config.name = name  # Override name
                except Exception as e:
                    console.print(f"[red]Failed to load webhook config from {config_file}: {e}[/red]")
                    raise typer.Exit(1)
            elif template and url:
                # Create from template
                try:
                    webhook_config = create_webhook_from_template(template, url)
                    webhook_config.name = name  # Override name
                    if description:
                        webhook_config.description = description
                except ValueError as e:
                    console.print(f"[red]{e}[/red]")
                    raise typer.Exit(1)
            elif url:
                # Create generic webhook
                event_types = []
                if events:
                    event_names = [e.strip() for e in events.split(",")]
                    for event_name in event_names:
                        try:
                            event_types.append(EventType(event_name))
                        except ValueError:
                            console.print(f"[yellow]Warning: Unknown event type '{event_name}'[/yellow]")
                
                if not event_types:
                    # Default to common events
                    event_types = [EventType.SESSION_STARTED, EventType.SESSION_STOPPED]
                
                retry_policy = RetryPolicy()
                if retries is not None:
                    retry_policy.max_attempts = retries
                
                webhook_config = WebhookConfig(
                    id=uuid4(),
                    name=name,
                    url=url,
                    description=description or f"Webhook for {name}",
                    event_types=event_types,
                    timeout=timeout or 30.0,
                    retry_policy=retry_policy,
                )
            else:
                console.print("[red]Either --url or --config is required[/red]")
                raise typer.Exit(1)
            
            try:
                webhook_id = integration_mgr.add_webhook(webhook_config)
                console.print(f"[green]Added webhook '{name}' (ID: {webhook_id})[/green]")
            except Exception as e:
                console.print(f"[red]Failed to add webhook: {e}[/red]")
                raise typer.Exit(1)
        
        elif action == "remove":
            if not webhook_id and not name:
                console.print("[red]Either --id or --name is required[/red]")
                raise typer.Exit(1)
            
            webhook = None
            if webhook_id:
                try:
                    webhook = integration_mgr.get_webhook(UUID(webhook_id))
                except ValueError:
                    console.print("[red]Invalid webhook ID format[/red]")
                    raise typer.Exit(1)
            else:
                webhook = integration_mgr.get_webhook_by_name(name)
            
            if not webhook:
                console.print("[red]Webhook not found[/red]")
                raise typer.Exit(1)
            
            if integration_mgr.remove_webhook(webhook.id):
                console.print(f"[green]Removed webhook '{webhook.name}'[/green]")
            else:
                console.print("[red]Failed to remove webhook[/red]")
                raise typer.Exit(1)
        
        elif action == "enable" or action == "disable":
            if not webhook_id and not name:
                console.print("[red]Either --id or --name is required[/red]")
                raise typer.Exit(1)
            
            webhook = None
            if webhook_id:
                try:
                    webhook = integration_mgr.get_webhook(UUID(webhook_id))
                except ValueError:
                    console.print("[red]Invalid webhook ID format[/red]")
                    raise typer.Exit(1)
            else:
                webhook = integration_mgr.get_webhook_by_name(name)
            
            if not webhook:
                console.print("[red]Webhook not found[/red]")
                raise typer.Exit(1)
            
            if action == "enable":
                if integration_mgr.enable_webhook(webhook.id):
                    console.print(f"[green]Enabled webhook '{webhook.name}'[/green]")
                else:
                    console.print("[red]Failed to enable webhook[/red]")
            else:
                if integration_mgr.disable_webhook(webhook.id):
                    console.print(f"[green]Disabled webhook '{webhook.name}'[/green]")
                else:
                    console.print("[red]Failed to disable webhook[/red]")
        
        elif action == "test":
            if not webhook_id and not name:
                console.print("[red]Either --id or --name is required[/red]")
                raise typer.Exit(1)
            
            webhook = None
            if webhook_id:
                try:
                    webhook = integration_mgr.get_webhook(UUID(webhook_id))
                except ValueError:
                    console.print("[red]Invalid webhook ID format[/red]")
                    raise typer.Exit(1)
            else:
                webhook = integration_mgr.get_webhook_by_name(name)
            
            if not webhook:
                console.print("[red]Webhook not found[/red]")
                raise typer.Exit(1)
            
            console.print(f"[blue]Testing webhook '{webhook.name}'...[/blue]")
            try:
                result = integration_mgr.test_webhook(webhook.id)
                if result.success:
                    console.print(f"[green]Test successful! Response: {result.delivery.response_status}[/green]")
                    if result.delivery.response_body:
                        console.print(f"[dim]Response body: {result.delivery.response_body[:200]}[/dim]")
                else:
                    console.print(f"[red]Test failed: {result.delivery.error_message}[/red]")
                    if result.will_retry:
                        console.print(f"[yellow]Will retry at: {result.next_retry_at}[/yellow]")
            except Exception as e:
                console.print(f"[red]Test failed: {e}[/red]")
        
        elif action == "history":
            limit = 50
            webhook_uuid = None
            
            if webhook_id:
                try:
                    webhook_uuid = UUID(webhook_id)
                except ValueError:
                    console.print("[red]Invalid webhook ID format[/red]")
                    raise typer.Exit(1)
            elif name:
                webhook = integration_mgr.get_webhook_by_name(name)
                if webhook:
                    webhook_uuid = webhook.id
                else:
                    console.print("[red]Webhook not found[/red]")
                    raise typer.Exit(1)
            
            history = integration_mgr.get_webhook_delivery_history(webhook_uuid, limit)
            
            if not history:
                console.print("[dim]No delivery history found[/dim]")
                return
            
            table = Table(show_header=True, header_style="bold")
            table.add_column("Time", style="dim")
            table.add_column("Webhook", style="bold")
            table.add_column("Event", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Duration", style="yellow")
            table.add_column("Response", style="green")
            
            for delivery in history:
                webhook = integration_mgr.get_webhook(delivery.webhook_id)
                webhook_name = webhook.name if webhook else "Unknown"
                
                status_color = "green" if delivery.status.value == "success" else "red"
                status_text = f"[{status_color}]{delivery.status.value.title()}[/{status_color}]"
                
                duration = f"{delivery.duration_ms:.0f}ms" if delivery.duration_ms else "N/A"
                response = str(delivery.response_status) if delivery.response_status else "N/A"
                
                table.add_row(
                    format_datetime(delivery.created_at),
                    webhook_name,
                    delivery.event_type.value,
                    status_text,
                    duration,
                    response
                )
            
            console.print(f"[bold]Webhook Delivery History ({len(history)} entries)[/bold]")
            console.print(table)
        
        elif action == "templates":
            console.print("[bold]Available Webhook Templates[/bold]")
            
            templates_info = [
                ("slack", "Slack integration webhook", "Posts to Slack channels"),
                ("discord", "Discord integration webhook", "Posts to Discord channels"),
                ("generic", "Generic HTTP webhook", "Basic webhook for custom endpoints"),
                ("task_tracker", "Task tracking integration", "Integrates with project management tools"),
                ("analytics", "Analytics integration", "Sends data to analytics platforms"),
            ]
            
            table = Table(show_header=True, header_style="bold")
            table.add_column("Template", style="bold")
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="dim")
            
            for template, name, desc in templates_info:
                table.add_row(template, name, desc)
            
            console.print(table)
            console.print("\n[dim]Usage: clockman webhook add --name 'My Webhook' --url https://example.com/webhook --template slack[/dim]")
        
        elif action == "config":
            # Show integration configuration
            stats = integration_mgr.get_statistics()
            
            table = Table(show_header=False, show_edge=False)
            table.add_column("Setting", style="dim")
            table.add_column("Value")
            
            table.add_row("Integration Status", "[green]Enabled[/green]" if stats["enabled"] else "[red]Disabled[/red]")
            table.add_row("Total Webhooks", str(stats["webhook_manager"]["total_webhooks"]))
            table.add_row("Active Webhooks", str(stats["webhook_manager"]["active_webhooks"]))
            table.add_row("Success Rate", f"{stats['webhook_manager']['success_rate']:.1%}")
            table.add_row("Pending Retries", str(stats["webhook_manager"]["pending_retries"]))
            
            console.print("[bold]Integration Configuration[/bold]")
            console.print(table)
        
        else:
            console.print(f"[red]Unknown action: {action}[/red]")
            console.print("Available actions: list, add, remove, enable, disable, test, history, templates, config")
            raise typer.Exit(1)
    
    except ImportError as e:
        console.print("[red]Integration features not available. Please check your installation.[/red]")
        console.print(f"[dim]Error: {e}[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Webhook command failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def plugin(
    action: str = typer.Argument(
        ..., 
        help="Action to perform: list, load, unload, enable, disable, discover, status, config, reload"
    ),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Plugin name"),
    file_path: Optional[str] = typer.Option(None, "--file", "-f", help="Plugin file path"),
    module: Optional[str] = typer.Option(None, "--module", "-m", help="Python module name"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Plugin configuration JSON file"),
    directory: Optional[str] = typer.Option(None, "--directory", "-d", help="Plugin directory to add/remove"),
) -> None:
    """Manage plugins for extending Clockman functionality."""
    try:
        from ..integrations.manager import IntegrationManager
        from ..integrations.config import PluginConfigEntry
        from ..utils.config import get_config_manager
        from pathlib import Path
        import json
        
        # Initialize integration manager
        config_mgr = get_config_manager()
        data_dir = config_mgr.get_data_dir()
        integration_mgr = IntegrationManager(data_dir)
        
        if not integration_mgr._initialized:
            integration_mgr.initialize()
        
        if action == "list":
            plugins = integration_mgr.list_plugins()
            
            if not plugins:
                console.print("[dim]No plugins loaded[/dim]")
                return
            
            table = Table(show_header=True, header_style="bold")
            table.add_column("Name", style="bold")
            table.add_column("Version", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Events", style="yellow")
            table.add_column("Description", style="dim", max_width=40)
            
            for plugin_name, plugin_instance in plugins.items():
                status_info = integration_mgr.get_plugin_status(plugin_name)
                
                enabled = status_info.get("enabled", False)
                initialized = status_info.get("initialized", False)
                
                if enabled and initialized:
                    status = "[green]Active[/green]"
                elif enabled:
                    status = "[yellow]Loading[/yellow]"
                else:
                    status = "[red]Disabled[/red]"
                
                events_count = len(plugin_instance.info.supported_events)
                events_str = f"{events_count} events"
                
                desc = plugin_instance.info.description
                if len(desc) > 40:
                    desc = desc[:37] + "..."
                
                table.add_row(
                    plugin_instance.info.name,
                    plugin_instance.info.version,
                    status,
                    events_str,
                    desc
                )
            
            console.print(f"[bold]Loaded Plugins ({len(plugins)} total)[/bold]")
            console.print(table)
        
        elif action == "discover":
            discovered = integration_mgr.discover_plugins()
            
            if not discovered:
                console.print("[dim]No plugins found in configured directories[/dim]")
                return
            
            table = Table(show_header=True, header_style="bold")
            table.add_column("Name", style="bold")
            table.add_column("File Path", style="cyan")
            table.add_column("Loaded", justify="center")
            
            loaded_plugins = set(integration_mgr.list_plugins().keys())
            
            for plugin_name, plugin_path in discovered.items():
                is_loaded = "[green]Yes[/green]" if plugin_name in loaded_plugins else "[dim]No[/dim]"
                
                table.add_row(
                    plugin_name,
                    str(plugin_path),
                    is_loaded
                )
            
            console.print(f"[bold]Discovered Plugins ({len(discovered)} total)[/bold]")
            console.print(table)
        
        elif action == "load":
            if not name:
                console.print("[red]Plugin name is required[/red]")
                raise typer.Exit(1)
            
            plugin_config = {}
            if config_file:
                try:
                    with open(config_file, 'r') as f:
                        plugin_config = json.load(f)
                except Exception as e:
                    console.print(f"[red]Failed to load plugin config: {e}[/red]")
                    raise typer.Exit(1)
            
            if module:
                # Load from Python module
                success = integration_mgr.load_plugin_from_module(module, name, plugin_config)
            elif file_path:
                # Load from file
                success = integration_mgr.load_plugin(name, Path(file_path), plugin_config)
            else:
                # Load from discovered plugins
                success = integration_mgr.load_plugin(name, config=plugin_config)
            
            if success:
                console.print(f"[green]Successfully loaded plugin '{name}'[/green]")
            else:
                console.print(f"[red]Failed to load plugin '{name}'[/red]")
                raise typer.Exit(1)
        
        elif action == "unload":
            if not name:
                console.print("[red]Plugin name is required[/red]")
                raise typer.Exit(1)
            
            if integration_mgr.unload_plugin(name):
                console.print(f"[green]Successfully unloaded plugin '{name}'[/green]")
            else:
                console.print(f"[red]Failed to unload plugin '{name}' (not loaded?)[/red]")
                raise typer.Exit(1)
        
        elif action == "reload":
            if not name:
                console.print("[red]Plugin name is required[/red]")
                raise typer.Exit(1)
            
            # Get current config before unloading
            current_config = integration_mgr.get_plugin_config(name)
            
            # Unload and reload
            if integration_mgr.unload_plugin(name):
                if integration_mgr.load_plugin(name, config=current_config):
                    console.print(f"[green]Successfully reloaded plugin '{name}'[/green]")
                else:
                    console.print(f"[red]Failed to reload plugin '{name}'[/red]")
                    raise typer.Exit(1)
            else:
                console.print(f"[red]Plugin '{name}' was not loaded[/red]")
                raise typer.Exit(1)
        
        elif action == "enable" or action == "disable":
            if not name:
                console.print("[red]Plugin name is required[/red]")
                raise typer.Exit(1)
            
            if action == "enable":
                if integration_mgr.enable_plugin(name):
                    console.print(f"[green]Enabled plugin '{name}'[/green]")
                else:
                    console.print(f"[red]Failed to enable plugin '{name}' (not loaded?)[/red]")
            else:
                if integration_mgr.disable_plugin(name):
                    console.print(f"[green]Disabled plugin '{name}'[/green]")
                else:
                    console.print(f"[red]Failed to disable plugin '{name}' (not loaded?)[/red]")
        
        elif action == "status":
            if name:
                # Show status for specific plugin
                status = integration_mgr.get_plugin_status(name)
                if not status:
                    console.print(f"[red]Plugin '{name}' not found[/red]")
                    raise typer.Exit(1)
                
                table = Table(show_header=False, show_edge=False)
                table.add_column("Property", style="dim")
                table.add_column("Value")
                
                plugin_info = status.get("plugin_info", {})
                
                table.add_row("Name", plugin_info.get("name", "Unknown"))
                table.add_row("Version", plugin_info.get("version", "Unknown"))
                table.add_row("Author", plugin_info.get("author", "Unknown"))
                table.add_row("Description", plugin_info.get("description", ""))
                table.add_row("Enabled", "[green]Yes[/green]" if status.get("enabled") else "[red]No[/red]")
                table.add_row("Initialized", "[green]Yes[/green]" if status.get("initialized") else "[red]No[/red]")
                
                if plugin_info.get("website"):
                    table.add_row("Website", plugin_info["website"])
                
                supported_events = plugin_info.get("supported_events", [])
                if supported_events:
                    events_str = ", ".join(event for event in supported_events)
                    table.add_row("Supported Events", events_str)
                
                console.print(f"[bold]Plugin Status: {name}[/bold]")
                console.print(table)
            else:
                # Show overall plugin system status
                stats = integration_mgr.get_statistics()
                
                table = Table(show_header=False, show_edge=False)
                table.add_column("Metric", style="dim")
                table.add_column("Value")
                
                plugin_stats = stats["plugin_manager"]
                
                table.add_row("Total Plugins", str(plugin_stats["total_plugins"]))
                table.add_row("Enabled Plugins", str(plugin_stats["enabled_plugins"]))
                table.add_row("Initialized Plugins", str(plugin_stats["initialized_plugins"]))
                table.add_row("Events Handled", str(plugin_stats["events_handled"]))
                table.add_row("Plugin Errors", str(plugin_stats["plugin_errors"]))
                
                console.print("[bold]Plugin System Status[/bold]")
                console.print(table)
        
        elif action == "config":
            # Show plugin configuration
            config = integration_mgr.config
            
            table = Table(show_header=False, show_edge=False)
            table.add_column("Setting", style="dim")
            table.add_column("Value")
            
            table.add_row("Plugin Directories", str(len(config.plugin_directories)))
            table.add_row("Max Plugin Workers", str(config.max_plugin_workers))
            table.add_row("Async Event Execution", "[green]Yes[/green]" if config.async_event_execution else "[red]No[/red]")
            
            console.print("[bold]Plugin Configuration[/bold]")
            console.print(table)
            
            if config.plugin_directories:
                console.print("\n[bold]Plugin Directories:[/bold]")
                for i, directory in enumerate(config.plugin_directories, 1):
                    console.print(f"  {i}. {directory}")
        
        else:
            console.print(f"[red]Unknown action: {action}[/red]")
            console.print("Available actions: list, load, unload, enable, disable, discover, status, config, reload")
            raise typer.Exit(1)
    
    except ImportError as e:
        console.print("[red]Integration features not available. Please check your installation.[/red]")
        console.print(f"[dim]Error: {e}[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Plugin command failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def integration(
    action: str = typer.Argument(
        ..., 
        help="Action to perform: status, enable, disable, stats, retry, clear-history"
    ),
) -> None:
    """Manage the integration system (webhooks and plugins)."""
    try:
        from ..integrations.manager import IntegrationManager
        from ..utils.config import get_config_manager
        
        # Initialize integration manager
        config_mgr = get_config_manager()
        data_dir = config_mgr.get_data_dir()
        integration_mgr = IntegrationManager(data_dir)
        
        if not integration_mgr._initialized:
            integration_mgr.initialize()
        
        if action == "status":
            stats = integration_mgr.get_statistics()
            
            # Overall status
            table = Table(show_header=False, show_edge=False)
            table.add_column("Component", style="bold")
            table.add_column("Status", justify="center")
            table.add_column("Details", style="dim")
            
            enabled = "[green]Enabled[/green]" if stats["enabled"] else "[red]Disabled[/red]"
            initialized = "[green]Initialized[/green]" if stats["initialized"] else "[red]Not Initialized[/red]"
            
            table.add_row("Integration System", enabled, initialized)
            
            # Webhook status
            webhook_stats = stats["webhook_manager"]
            webhook_details = f"{webhook_stats['active_webhooks']}/{webhook_stats['total_webhooks']} active"
            table.add_row("Webhooks", "[green]Active[/green]" if webhook_stats['active_webhooks'] > 0 else "[dim]None[/dim]", webhook_details)
            
            # Plugin status  
            plugin_stats = stats["plugin_manager"]
            plugin_details = f"{plugin_stats['enabled_plugins']}/{plugin_stats['total_plugins']} enabled"
            table.add_row("Plugins", "[green]Active[/green]" if plugin_stats['enabled_plugins'] > 0 else "[dim]None[/dim]", plugin_details)
            
            console.print("[bold]Integration System Status[/bold]")
            console.print(table)
            
            # Event statistics
            if plugin_stats.get("event_subscriptions"):
                console.print("\n[bold]Event Subscriptions:[/bold]")
                for event_type, count in plugin_stats["event_subscriptions"].items():
                    console.print(f"  {event_type}: {count} plugins")
        
        elif action == "enable":
            integration_mgr.enable()
            console.print("[green]Integration system enabled[/green]")
        
        elif action == "disable":
            integration_mgr.disable()
            console.print("[yellow]Integration system disabled[/yellow]")
        
        elif action == "stats":
            stats = integration_mgr.get_statistics()
            
            # Detailed statistics table
            table = Table(show_header=True, header_style="bold")
            table.add_column("Category", style="bold")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")
            
            # Integration stats
            table.add_row("System", "Enabled", str(stats["enabled"]))
            table.add_row("System", "Initialized", str(stats["initialized"]))
            
            # Webhook stats
            webhook_stats = stats["webhook_manager"]
            table.add_row("Webhooks", "Total", str(webhook_stats["total_webhooks"]))
            table.add_row("Webhooks", "Active", str(webhook_stats["active_webhooks"]))
            table.add_row("Webhooks", "Deliveries Attempted", str(webhook_stats["total_deliveries_attempted"]))
            table.add_row("Webhooks", "Deliveries Successful", str(webhook_stats["total_deliveries_successful"]))
            table.add_row("Webhooks", "Deliveries Failed", str(webhook_stats["total_deliveries_failed"]))
            table.add_row("Webhooks", "Success Rate", f"{webhook_stats['success_rate']:.1%}")
            table.add_row("Webhooks", "Pending Retries", str(webhook_stats["pending_retries"]))
            
            # Plugin stats
            plugin_stats = stats["plugin_manager"]
            table.add_row("Plugins", "Total", str(plugin_stats["total_plugins"]))
            table.add_row("Plugins", "Enabled", str(plugin_stats["enabled_plugins"]))
            table.add_row("Plugins", "Initialized", str(plugin_stats["initialized_plugins"]))
            table.add_row("Plugins", "Events Handled", str(plugin_stats["events_handled"]))
            table.add_row("Plugins", "Plugin Errors", str(plugin_stats["plugin_errors"]))
            
            console.print("[bold]Integration System Statistics[/bold]")
            console.print(table)
        
        elif action == "retry":
            console.print("[blue]Processing webhook retries...[/blue]")
            results = integration_mgr.process_webhook_retries()
            
            if not results:
                console.print("[dim]No retries processed[/dim]")
                return
            
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            
            console.print(f"[green]Processed {len(results)} retries: {successful} successful, {failed} failed[/green]")
        
        elif action == "clear-history":
            count = integration_mgr.clear_webhook_history()
            console.print(f"[green]Cleared {count} webhook delivery history entries[/green]")
        
        else:
            console.print(f"[red]Unknown action: {action}[/red]")
            console.print("Available actions: status, enable, disable, stats, retry, clear-history")
            raise typer.Exit(1)
    
    except ImportError as e:
        console.print("[red]Integration features not available. Please check your installation.[/red]")
        console.print(f"[dim]Error: {e}[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Integration command failed: {e}[/red]")
        raise typer.Exit(1)


def version_callback(value: bool) -> None:
    """Version callback that prints version and exits."""
    if value:
        version()
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """
    Clockman: Terminal-based time tracking for developers.

    A privacy-focused, offline-first time tracking CLI application.
    """
    pass


if __name__ == "__main__":
    app()
