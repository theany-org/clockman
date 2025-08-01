"""
Main CLI entry point for Clockman.

This module provides the primary command-line interface using typer.
"""

from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from ..core.time_tracker import TimeTracker
from ..utils.config import get_config_manager
from ..utils.formatting import format_datetime, format_duration
from ..utils.notifier import notify_sync

# Create the main typer app
app = typer.Typer(
    name="clockman",
    help="Clockman: Terminal-based time tracking for developers",
    add_completion=False,
)

# Initialize console for rich output
console = Console()

# Global tracker instance
tracker: Optional[TimeTracker] = None


def get_tracker() -> TimeTracker:
    """Get or initialize the global time tracker instance."""
    global tracker
    if tracker is None:
        config = get_config_manager()
        tracker = TimeTracker(config.get_data_dir())
    return tracker


@app.command()
def start(
    task_name: str = typer.Argument(..., help="Name of the task to track"),
    tag: Optional[List[str]] = typer.Option(
        None, "--tag", "-t", help="Add tags to the task"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Task description"
    ),
) -> None:
    """Start tracking time for a task."""
    try:
        time_tracker = get_tracker()

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

        # Start new session
        session_id = time_tracker.start_session(
            task_name=task_name, tags=tag or [], description=description
        )

        console.print(f"[green]✓[/green] Started tracking: [bold]{task_name}[/bold]")
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
        time_tracker = get_tracker()
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
        time_tracker = get_tracker()
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
        time_tracker = get_tracker()

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

            table.add_row(
                entry.task_name,
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
def version() -> None:
    """Show Clockman version information."""
    from .. import __version__

    console.print(f"Clockman version {__version__}")


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
