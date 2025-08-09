"""
Database schema definition for Clockman.

This module contains the SQL schema and migration logic for the SQLite database.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional

# Database schema version
SCHEMA_VERSION = 2

# SQL for creating tables
CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    description TEXT,
    project_id TEXT,  -- References projects.id
    tags TEXT,  -- JSON array of tags
    start_time TEXT NOT NULL,  -- ISO format datetime
    end_time TEXT,  -- ISO format datetime, NULL for active sessions
    is_active BOOLEAN NOT NULL DEFAULT 1,
    metadata TEXT,  -- JSON object for additional data
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    parent_id TEXT,  -- Self-referencing for hierarchy
    is_active BOOLEAN NOT NULL DEFAULT 1,
    default_tags TEXT,  -- JSON array of default tags
    metadata TEXT,  -- JSON object for additional data
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES projects(id) ON DELETE SET NULL
);
"""

CREATE_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# Indexes for better query performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_task_name ON sessions(task_name);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_is_active ON sessions(is_active);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_tags ON sessions(tags);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);",
    "CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);",
    "CREATE INDEX IF NOT EXISTS idx_projects_parent_id ON projects(parent_id);",
    "CREATE INDEX IF NOT EXISTS idx_projects_is_active ON projects(is_active);",
]

# Triggers for updating timestamps
CREATE_TRIGGERS = [
    """
    CREATE TRIGGER IF NOT EXISTS update_sessions_timestamp 
    AFTER UPDATE ON sessions
    BEGIN
        UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS update_projects_timestamp 
    AFTER UPDATE ON projects
    BEGIN
        UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
    """
]


class DatabaseManager:
    """Manages database connections and schema operations."""

    def __init__(self, db_path: Path):
        """Initialize database manager with the given database path."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            conn.close()

    def initialize_database(self) -> None:
        """Initialize the database with the current schema."""
        with self.get_connection() as conn:
            # Create schema version table first
            conn.execute(CREATE_SCHEMA_VERSION_TABLE)

            # Check current schema version
            current_version = self._get_schema_version(conn)

            if current_version is None:
                # Fresh database, create all tables
                self._create_tables(conn)
                self._set_schema_version(conn, SCHEMA_VERSION)
            elif current_version < SCHEMA_VERSION:
                # Migrate to newer version
                self._migrate_database(conn, current_version, SCHEMA_VERSION)

            conn.commit()

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """Create all database tables."""
        # Create main tables
        conn.execute(CREATE_SESSIONS_TABLE)
        conn.execute(CREATE_PROJECTS_TABLE)

        # Create indexes
        for index_sql in CREATE_INDEXES:
            conn.execute(index_sql)

        # Create triggers
        for trigger_sql in CREATE_TRIGGERS:
            conn.execute(trigger_sql)

    def _get_schema_version(self, conn: sqlite3.Connection) -> Optional[int]:
        """Get the current schema version."""
        try:
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else None
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return None

    def _set_schema_version(self, conn: sqlite3.Connection, version: int) -> None:
        """Set the schema version."""
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))

    def _migrate_database(
        self, conn: sqlite3.Connection, from_version: int, to_version: int
    ) -> None:
        """Migrate database from one version to another."""
        if from_version == 1 and to_version >= 2:
            # Migration from v1 to v2: Add project support
            conn.execute("ALTER TABLE sessions ADD COLUMN project_id TEXT;")
            conn.execute(CREATE_PROJECTS_TABLE)
            
            # Add new indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_parent_id ON projects(parent_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_is_active ON projects(is_active);")
            
            # Add new trigger
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS update_projects_timestamp 
                AFTER UPDATE ON projects
                BEGIN
                    UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END;
            """)
            
            self._set_schema_version(conn, 2)

    def vacuum_database(self) -> None:
        """Optimize the database by running VACUUM."""
        with self.get_connection() as conn:
            conn.execute("VACUUM")

    def get_database_stats(self) -> Dict[str, Any]:
        """Get basic database statistics."""
        # If database file doesn't exist, return zeros
        if not self.db_path.exists():
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "first_session": None,
                "last_session": None,
                "database_size": 0,
            }

        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT 
                        COUNT(*) as total_sessions,
                        COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_sessions,
                        MIN(start_time) as first_session,
                        MAX(start_time) as last_session
                    FROM sessions
                """
                )
                result = cursor.fetchone()

                if result:
                    return {
                        "total_sessions": result["total_sessions"],
                        "active_sessions": result["active_sessions"],
                        "first_session": result["first_session"],
                        "last_session": result["last_session"],
                        "database_size": self.db_path.stat().st_size,
                    }
                else:
                    return {
                        "total_sessions": 0,
                        "active_sessions": 0,
                        "first_session": None,
                        "last_session": None,
                        "database_size": self.db_path.stat().st_size,
                    }
        except sqlite3.OperationalError:
            # Table doesn't exist, return basic stats
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "first_session": None,
                "last_session": None,
                "database_size": self.db_path.stat().st_size,
            }
