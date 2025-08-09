"""
Advanced plugin examples for Clockman.

This module demonstrates sophisticated plugin implementations using
the enhanced integration system with hooks, dependencies, and advanced
event handling capabilities.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3

from ..events.events import ClockmanEvent, EventType
from ..plugins.base import BasePlugin, PluginInfo
from ..plugins.dependencies import DependencySpec, DependencyType


class ProductivityAnalyzerPlugin(BasePlugin):
    """
    Advanced plugin that analyzes productivity patterns and generates insights.
    
    This plugin demonstrates:
    - Complex event processing
    - Data persistence
    - Statistical analysis
    - Configurable behavior
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the productivity analyzer plugin."""
        super().__init__(config)
        self.db_path: Optional[Path] = None
        self.db_connection: Optional[sqlite3.Connection] = None
        self.session_buffer: List[Dict[str, Any]] = []
        self.analysis_threshold = self.get_config_value("analysis_threshold", 10)
        self.min_session_duration = self.get_config_value("min_session_duration", 300)  # 5 minutes
    
    @property
    def info(self) -> PluginInfo:
        """Get plugin information."""
        return PluginInfo(
            name="Productivity Analyzer",
            version="2.0.0",
            description="Analyzes work patterns and generates productivity insights",
            author="Clockman Advanced Team",
            website="https://github.com/theany-org/clockman-plugins",
            supported_events=[
                EventType.SESSION_STARTED,
                EventType.SESSION_STOPPED,
                EventType.SESSION_UPDATED,
            ],
            dependencies=[
                DependencySpec(
                    name="database_manager",
                    type=DependencyType.OPTIONAL,
                    description="Enhanced database operations"
                )
            ],
            provides=["productivity_insights", "session_analysis"],
            categories=["analytics", "productivity", "insights"],
            config_schema={
                "type": "object",
                "properties": {
                    "analysis_threshold": {
                        "type": "integer",
                        "default": 10,
                        "description": "Number of sessions before triggering analysis"
                    },
                    "min_session_duration": {
                        "type": "integer", 
                        "default": 300,
                        "description": "Minimum session duration in seconds to include in analysis"
                    },
                    "database_path": {
                        "type": "string",
                        "description": "Custom path for analytics database"
                    },
                    "generate_daily_reports": {
                        "type": "boolean",
                        "default": True,
                        "description": "Generate daily productivity reports"
                    },
                    "track_focus_patterns": {
                        "type": "boolean",
                        "default": True,
                        "description": "Analyze focus and distraction patterns"
                    }
                }
            }
        )
    
    def initialize(self) -> None:
        """Initialize the plugin."""
        # Set up database
        db_path = self.get_config_value("database_path")
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path.cwd() / "data" / "productivity_analysis.db"
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_connection = sqlite3.connect(str(self.db_path))
        self._create_tables()
        
        # Register hooks for additional functionality
        from ..hooks import get_hook_manager
        hook_manager = get_hook_manager()
        
        # Register daily report hook
        if self.get_config_value("generate_daily_reports", True):
            hook_manager.register_hook(
                callback=self._generate_daily_report,
                name="productivity_daily_report",
                event_types=[EventType.SYSTEM_STARTED],  # Trigger on system start
                owner=self.info.name
            )
        
        self.logger.info("Productivity Analyzer plugin initialized")
    
    def shutdown(self) -> None:
        """Shutdown the plugin."""
        if self.session_buffer:
            self._process_session_buffer()
        
        if self.db_connection:
            self.db_connection.close()
        
        # Unregister hooks
        from ..hooks import get_hook_manager
        hook_manager = get_hook_manager()
        hook_manager.unregister_hooks_by_owner(self.info.name)
        
        self.logger.info("Productivity Analyzer plugin shutdown")
    
    def handle_event(self, event: ClockmanEvent) -> None:
        """Handle time tracking events."""
        if event.event_type == EventType.SESSION_STOPPED:
            self._process_session_stopped(event)
        elif event.event_type == EventType.SESSION_STARTED:
            self._process_session_started(event)
    
    def _create_tables(self) -> None:
        """Create database tables for analytics."""
        cursor = self.db_connection.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                task_name TEXT,
                start_time DATETIME,
                end_time DATETIME,
                duration_seconds INTEGER,
                tags TEXT,  -- JSON array
                project_id TEXT,
                productivity_score REAL,
                focus_rating INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_summaries (
                date DATE PRIMARY KEY,
                total_sessions INTEGER,
                total_duration INTEGER,
                average_session_length REAL,
                productivity_score REAL,
                top_tags TEXT,  -- JSON array
                insights TEXT,   -- JSON object
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT,  -- 'focus', 'productivity', 'schedule'
                pattern_data TEXT,   -- JSON object
                confidence REAL,
                discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.db_connection.commit()
    
    def _process_session_stopped(self, event: ClockmanEvent) -> None:
        """Process a completed session."""
        session_data = event.data
        duration = session_data.get("duration_seconds", 0)
        
        # Only process sessions longer than minimum duration
        if duration < self.min_session_duration:
            return
        
        # Calculate productivity score
        productivity_score = self._calculate_productivity_score(session_data)
        
        # Add to session buffer
        enhanced_session = {
            **session_data,
            "productivity_score": productivity_score,
            "processed_at": datetime.utcnow().isoformat()
        }
        
        self.session_buffer.append(enhanced_session)
        
        # Store in database
        self._store_session(enhanced_session)
        
        # Check if we should trigger analysis
        if len(self.session_buffer) >= self.analysis_threshold:
            self._process_session_buffer()
    
    def _process_session_started(self, event: ClockmanEvent) -> None:
        """Process a session start for context tracking."""
        # Could be used for tracking context switches, interruptions, etc.
        pass
    
    def _calculate_productivity_score(self, session_data: Dict[str, Any]) -> float:
        """
        Calculate a productivity score for a session.
        
        This is a simplified scoring algorithm that considers:
        - Session length
        - Task type (based on tags)
        - Time of day
        - Description quality
        """
        score = 0.5  # Base score
        
        duration = session_data.get("duration_seconds", 0)
        tags = session_data.get("tags", [])
        task_name = session_data.get("task_name", "")
        description = session_data.get("description", "")
        
        # Duration scoring (optimal range: 25-90 minutes)
        if 1500 <= duration <= 5400:  # 25-90 minutes
            score += 0.3
        elif duration > 5400:  # Over 90 minutes
            score += 0.1  # Might indicate lack of breaks
        
        # Tag-based scoring
        productive_tags = ["work", "development", "coding", "writing", "analysis", "design"]
        less_productive_tags = ["meeting", "email", "admin"]
        unproductive_tags = ["break", "social", "distraction"]
        
        for tag in tags:
            if tag.lower() in productive_tags:
                score += 0.2
            elif tag.lower() in less_productive_tags:
                score += 0.05
            elif tag.lower() in unproductive_tags:
                score -= 0.1
        
        # Task name quality
        if task_name and len(task_name) > 5:
            score += 0.1
        
        # Description quality
        if description and len(description) > 10:
            score += 0.1
        
        # Clamp to 0-1 range
        return max(0.0, min(1.0, score))
    
    def _store_session(self, session_data: Dict[str, Any]) -> None:
        """Store session data in the database."""
        cursor = self.db_connection.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO sessions (
                id, task_name, start_time, end_time, duration_seconds,
                tags, project_id, productivity_score, focus_rating
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_data.get("session_id", ""),
            session_data.get("task_name", ""),
            session_data.get("start_time", ""),
            session_data.get("end_time", ""),
            session_data.get("duration_seconds", 0),
            json.dumps(session_data.get("tags", [])),
            session_data.get("project_id", ""),
            session_data.get("productivity_score", 0.0),
            session_data.get("focus_rating", 3)  # Default neutral focus
        ))
        
        self.db_connection.commit()
    
    def _process_session_buffer(self) -> None:
        """Process accumulated sessions and generate insights."""
        if not self.session_buffer:
            return
        
        self.logger.info(f"Processing {len(self.session_buffer)} sessions for analysis")
        
        # Analyze patterns
        insights = self._analyze_patterns(self.session_buffer)
        
        # Generate report
        report = self._generate_productivity_report(insights)
        
        # Save insights
        self._store_insights(insights)
        
        # Log report
        self.logger.info(f"Productivity analysis complete: {report}")
        
        # Clear buffer
        self.session_buffer.clear()
    
    def _analyze_patterns(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze productivity patterns in session data."""
        total_sessions = len(sessions)
        total_duration = sum(s.get("duration_seconds", 0) for s in sessions)
        average_duration = total_duration / total_sessions if total_sessions > 0 else 0
        
        # Tag frequency analysis
        all_tags = []
        for session in sessions:
            all_tags.extend(session.get("tags", []))
        
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Productivity score analysis
        productivity_scores = [s.get("productivity_score", 0.5) for s in sessions]
        average_productivity = sum(productivity_scores) / len(productivity_scores)
        
        return {
            "analysis_period": {
                "start": min(s.get("start_time", "") for s in sessions),
                "end": max(s.get("end_time", "") for s in sessions),
            },
            "session_stats": {
                "total_sessions": total_sessions,
                "total_duration": total_duration,
                "average_duration": average_duration,
                "average_productivity": average_productivity,
            },
            "top_tags": top_tags,
            "patterns": {
                "most_productive_tag": top_tags[0][0] if top_tags else None,
                "productivity_trend": self._calculate_trend(productivity_scores),
                "session_length_trend": self._calculate_trend([s.get("duration_seconds", 0) for s in sessions]),
            }
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate if a series of values is trending up, down, or stable."""
        if len(values) < 3:
            return "insufficient_data"
        
        # Simple linear trend calculation
        n = len(values)
        x_values = list(range(n))
        
        # Calculate slope using least squares
        x_mean = sum(x_values) / n
        y_mean = sum(values) / n
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        if slope > 0.01:
            return "increasing"
        elif slope < -0.01:
            return "decreasing"
        else:
            return "stable"
    
    def _generate_productivity_report(self, insights: Dict[str, Any]) -> str:
        """Generate a human-readable productivity report."""
        stats = insights["session_stats"]
        patterns = insights["patterns"]
        
        report_lines = [
            f"Productivity Analysis Report",
            f"Sessions: {stats['total_sessions']}",
            f"Total Time: {stats['total_duration'] // 3600}h {(stats['total_duration'] % 3600) // 60}m",
            f"Average Session: {stats['average_duration'] // 60}m",
            f"Productivity Score: {stats['average_productivity']:.2f}/1.0",
        ]
        
        if patterns["most_productive_tag"]:
            report_lines.append(f"Most Used Tag: {patterns['most_productive_tag']}")
        
        report_lines.append(f"Productivity Trend: {patterns['productivity_trend']}")
        
        return " | ".join(report_lines)
    
    def _store_insights(self, insights: Dict[str, Any]) -> None:
        """Store analysis insights in the database."""
        cursor = self.db_connection.cursor()
        
        cursor.execute("""
            INSERT INTO patterns (pattern_type, pattern_data, confidence)
            VALUES (?, ?, ?)
        """, (
            "productivity_analysis",
            json.dumps(insights),
            0.8  # Confidence score
        ))
        
        self.db_connection.commit()
    
    def _generate_daily_report(self, event: ClockmanEvent) -> None:
        """Hook callback to generate daily productivity reports."""
        self.logger.info("Generating daily productivity report")
        
        # Query yesterday's sessions
        cursor = self.db_connection.cursor()
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT * FROM sessions 
            WHERE DATE(start_time) = ?
        """, (yesterday,))
        
        sessions = cursor.fetchall()
        
        if sessions:
            self.logger.info(f"Generated daily report for {yesterday}: {len(sessions)} sessions")
        else:
            self.logger.info(f"No sessions found for {yesterday}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get plugin status with analytics information."""
        status = super().get_status()
        
        if self.db_connection:
            cursor = self.db_connection.cursor()
            
            # Get session count
            cursor.execute("SELECT COUNT(*) FROM sessions")
            session_count = cursor.fetchone()[0]
            
            # Get latest analysis
            cursor.execute("""
                SELECT pattern_data FROM patterns 
                WHERE pattern_type = 'productivity_analysis'
                ORDER BY discovered_at DESC LIMIT 1
            """)
            latest_analysis = cursor.fetchone()
            
            status.update({
                "database_path": str(self.db_path),
                "total_sessions_analyzed": session_count,
                "sessions_in_buffer": len(self.session_buffer),
                "has_recent_analysis": latest_analysis is not None,
            })
        
        return status


class AutoBackupPlugin(BasePlugin):
    """
    Plugin that automatically creates backups of time tracking data.
    
    Demonstrates:
    - File system operations
    - Scheduled operations
    - Error handling and recovery
    - Configuration management
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the auto backup plugin."""
        super().__init__(config)
        self.backup_dir: Optional[Path] = None
        self.last_backup: Optional[datetime] = None
        self.backup_count = 0
    
    @property
    def info(self) -> PluginInfo:
        """Get plugin information."""
        return PluginInfo(
            name="Auto Backup Manager",
            version="1.2.0",
            description="Automatically creates backups of time tracking data",
            author="Clockman Team",
            supported_events=[
                EventType.SESSION_STOPPED,
                EventType.PROJECT_CREATED,
                EventType.SYSTEM_SHUTDOWN,
            ],
            config_schema={
                "type": "object",
                "properties": {
                    "backup_directory": {
                        "type": "string",
                        "description": "Directory to store backups"
                    },
                    "backup_frequency": {
                        "type": "integer",
                        "default": 24,
                        "description": "Hours between automatic backups"
                    },
                    "max_backups": {
                        "type": "integer",
                        "default": 30,
                        "description": "Maximum number of backups to keep"
                    },
                    "compress_backups": {
                        "type": "boolean",
                        "default": True,
                        "description": "Compress backup files"
                    }
                }
            }
        )
    
    def initialize(self) -> None:
        """Initialize the plugin."""
        backup_dir = self.get_config_value("backup_directory")
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            self.backup_dir = Path.cwd() / "backups"
        
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Auto Backup plugin initialized - backup dir: {self.backup_dir}")
    
    def handle_event(self, event: ClockmanEvent) -> None:
        """Handle events for backup triggers."""
        frequency_hours = self.get_config_value("backup_frequency", 24)
        
        should_backup = False
        
        if event.event_type == EventType.SYSTEM_SHUTDOWN:
            # Always backup on shutdown
            should_backup = True
        elif self.last_backup is None:
            # First backup
            should_backup = True
        elif datetime.utcnow() - self.last_backup > timedelta(hours=frequency_hours):
            # Time-based backup
            should_backup = True
        
        if should_backup:
            self._create_backup()
    
    def _create_backup(self) -> None:
        """Create a backup of the time tracking data."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = f"clockman_backup_{timestamp}"
            
            if self.get_config_value("compress_backups", True):
                backup_file = self.backup_dir / f"{backup_name}.tar.gz"
                # In a real implementation, create compressed backup
                backup_file.touch()  # Placeholder
            else:
                backup_file = self.backup_dir / f"{backup_name}.json"
                # In a real implementation, create JSON backup
                backup_file.write_text('{"backup": "placeholder"}')
            
            self.backup_count += 1
            self.last_backup = datetime.utcnow()
            
            self.logger.info(f"Created backup: {backup_file}")
            
            # Clean up old backups
            self._cleanup_old_backups()
            
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
    
    def _cleanup_old_backups(self) -> None:
        """Remove old backup files."""
        max_backups = self.get_config_value("max_backups", 30)
        
        try:
            backup_files = list(self.backup_dir.glob("clockman_backup_*"))
            backup_files.sort(key=lambda f: f.stat().st_mtime)
            
            while len(backup_files) > max_backups:
                old_backup = backup_files.pop(0)
                old_backup.unlink()
                self.logger.info(f"Removed old backup: {old_backup}")
                
        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get backup plugin status."""
        status = super().get_status()
        
        backup_files = list(self.backup_dir.glob("clockman_backup_*")) if self.backup_dir else []
        
        status.update({
            "backup_directory": str(self.backup_dir) if self.backup_dir else None,
            "total_backups": len(backup_files),
            "last_backup": self.last_backup.isoformat() if self.last_backup else None,
            "next_backup_due": self._calculate_next_backup_time(),
        })
        
        return status
    
    def _calculate_next_backup_time(self) -> Optional[str]:
        """Calculate when the next backup is due."""
        if not self.last_backup:
            return "now"
        
        frequency_hours = self.get_config_value("backup_frequency", 24)
        next_backup = self.last_backup + timedelta(hours=frequency_hours)
        
        if next_backup <= datetime.utcnow():
            return "now"
        
        return next_backup.isoformat()


# Plugin configuration examples
PLUGIN_CONFIGS = {
    "productivity_analyzer": {
        "analysis_threshold": 5,
        "min_session_duration": 300,
        "generate_daily_reports": True,
        "track_focus_patterns": True,
    },
    "auto_backup": {
        "backup_frequency": 12,  # Every 12 hours
        "max_backups": 50,
        "compress_backups": True,
    }
}


def create_plugin_config(plugin_name: str, **overrides) -> Dict[str, Any]:
    """
    Create a plugin configuration with optional overrides.
    
    Args:
        plugin_name: Name of the plugin
        **overrides: Configuration overrides
        
    Returns:
        Plugin configuration dictionary
    """
    base_config = PLUGIN_CONFIGS.get(plugin_name, {})
    base_config.update(overrides)
    return base_config


if __name__ == "__main__":
    # Test plugin creation
    print("Testing advanced plugin examples...")
    
    # Test ProductivityAnalyzerPlugin
    try:
        config = create_plugin_config("productivity_analyzer")
        plugin = ProductivityAnalyzerPlugin(config)
        print(f"✓ ProductivityAnalyzerPlugin: {plugin.info.name} v{plugin.info.version}")
    except Exception as e:
        print(f"✗ ProductivityAnalyzerPlugin: {e}")
    
    # Test AutoBackupPlugin
    try:
        config = create_plugin_config("auto_backup")
        plugin = AutoBackupPlugin(config)
        print(f"✓ AutoBackupPlugin: {plugin.info.name} v{plugin.info.version}")
    except Exception as e:
        print(f"✗ AutoBackupPlugin: {e}")
    
    print("Advanced plugin examples tested successfully!")