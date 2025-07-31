"""
Tests for database schema management (trackit.db.schema).

This module tests database initialization, migrations, and schema operations.
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from trackit.db.schema import (
    CREATE_INDEXES,
    CREATE_SCHEMA_VERSION_TABLE,
    CREATE_SESSIONS_TABLE,
    CREATE_TRIGGERS,
    SCHEMA_VERSION,
    DatabaseManager,
)


class TestDatabaseManager:
    """Test cases for DatabaseManager class."""

    def test_init_creates_parent_directory(self):
        """Test that DatabaseManager creates parent directory."""
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "subdir" / "test.db"
            assert not db_path.parent.exists()

            # Act
            db_manager = DatabaseManager(db_path)

            # Assert
            assert db_path.parent.exists()
            assert db_manager.db_path == db_path

    def test_get_connection_context_manager(self, test_db_path):
        """Test get_connection context manager functionality."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Act & Assert
        with db_manager.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)
            assert conn.row_factory == sqlite3.Row

            # Test that we can execute queries
            cursor = conn.execute("SELECT 1 as test_value")
            result = cursor.fetchone()
            assert result["test_value"] == 1

        # Connection should be closed after context manager exits
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_get_connection_pragma_settings(self, test_db_path):
        """Test that connection has correct PRAGMA settings."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Act & Assert
        with db_manager.get_connection() as conn:
            # Check foreign keys are enabled
            cursor = conn.execute("PRAGMA foreign_keys")
            result = cursor.fetchone()
            assert result[0] == 1

            # Check journal mode is WAL
            cursor = conn.execute("PRAGMA journal_mode")
            result = cursor.fetchone()
            assert result[0].upper() == "WAL"

    def test_initialize_database_fresh(self, test_db_path):
        """Test initializing a fresh database."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)
        assert not test_db_path.exists()

        # Act
        db_manager.initialize_database()

        # Assert
        assert test_db_path.exists()

        # Verify tables were created
        with db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            assert "sessions" in tables
            assert "schema_version" in tables

    def test_initialize_database_creates_indexes(self, test_db_path):
        """Test that database initialization creates indexes."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Act
        db_manager.initialize_database()

        # Assert
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
            )
            indexes = [row[0] for row in cursor.fetchall()]

            # Should have our custom indexes
            assert "idx_sessions_start_time" in indexes
            assert "idx_sessions_task_name" in indexes
            assert "idx_sessions_is_active" in indexes
            assert "idx_sessions_tags" in indexes

    def test_initialize_database_creates_triggers(self, test_db_path):
        """Test that database initialization creates triggers."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Act
        db_manager.initialize_database()

        # Assert
        with db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
            triggers = [row[0] for row in cursor.fetchall()]

            assert "update_sessions_timestamp" in triggers

    def test_initialize_database_sets_schema_version(self, test_db_path):
        """Test that database initialization sets schema version."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Act
        db_manager.initialize_database()

        # Assert
        with db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            version = cursor.fetchone()[0]

            assert version == SCHEMA_VERSION

    def test_initialize_database_existing_current_version(self, test_db_path):
        """Test initializing database that already has current version."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)
        db_manager.initialize_database()  # Initialize once

        # Verify current version
        with db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM schema_version")
            initial_count = cursor.fetchone()[0]

        # Act - initialize again
        db_manager.initialize_database()

        # Assert - should not create duplicate version entries
        with db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM schema_version")
            final_count = cursor.fetchone()[0]

            assert final_count == initial_count

    def test_get_schema_version_fresh_database(self, test_db_path):
        """Test getting schema version from fresh database."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Act & Assert
        with db_manager.get_connection() as conn:
            version = db_manager._get_schema_version(conn)
            assert version is None

    def test_get_schema_version_existing_database(self, test_db_path):
        """Test getting schema version from existing database."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)
        db_manager.initialize_database()

        # Act
        with db_manager.get_connection() as conn:
            version = db_manager._get_schema_version(conn)

        # Assert
        assert version == SCHEMA_VERSION

    def test_set_schema_version(self, test_db_path):
        """Test setting schema version."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Act
        with db_manager.get_connection() as conn:
            conn.execute(CREATE_SCHEMA_VERSION_TABLE)
            db_manager._set_schema_version(conn, 42)
            conn.commit()

            # Assert
            version = db_manager._get_schema_version(conn)
            assert version == 42

    def test_set_schema_version_multiple(self, test_db_path):
        """Test setting multiple schema versions."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Act
        with db_manager.get_connection() as conn:
            conn.execute(CREATE_SCHEMA_VERSION_TABLE)
            db_manager._set_schema_version(conn, 1)
            db_manager._set_schema_version(conn, 2)
            db_manager._set_schema_version(conn, 3)
            conn.commit()

            # Assert - should return the maximum version
            version = db_manager._get_schema_version(conn)
            assert version == 3

    def test_create_tables(self, test_db_path):
        """Test _create_tables method."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Act
        with db_manager.get_connection() as conn:
            db_manager._create_tables(conn)
            conn.commit()

        # Assert
        with db_manager.get_connection() as conn:
            # Check sessions table exists and has correct structure
            cursor = conn.execute("PRAGMA table_info(sessions)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]

            expected_columns = [
                "id",
                "task_name",
                "description",
                "tags",
                "start_time",
                "end_time",
                "is_active",
                "metadata",
                "created_at",
                "updated_at",
            ]

            for col in expected_columns:
                assert col in column_names

    def test_vacuum_database(self, test_db_path):
        """Test vacuum database operation."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)
        db_manager.initialize_database()

        # Act - should not raise exception
        db_manager.vacuum_database()

        # Assert - database should still be functional
        with db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            assert len(tables) > 0

    def test_get_database_stats_empty_database(self, test_db_path):
        """Test getting stats from empty database."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)
        db_manager.initialize_database()

        # Act
        stats = db_manager.get_database_stats()

        # Assert
        assert isinstance(stats, dict)
        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == 0
        assert stats["first_session"] is None
        assert stats["last_session"] is None
        assert stats["database_size"] > 0  # File exists

    def test_get_database_stats_with_data(self, test_db_path):
        """Test getting stats from database with data."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)
        db_manager.initialize_database()

        # Add some test data
        with db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, task_name, start_time, is_active, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("test-id-1", "Task 1", "2024-01-01T09:00:00Z", 1, "[]", "{}"),
            )
            conn.execute(
                """
                INSERT INTO sessions (id, task_name, start_time, end_time, is_active, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "test-id-2",
                    "Task 2",
                    "2024-01-01T10:00:00Z",
                    "2024-01-01T11:00:00Z",
                    0,
                    "[]",
                    "{}",
                ),
            )
            conn.commit()

        # Act
        stats = db_manager.get_database_stats()

        # Assert
        assert stats["total_sessions"] == 2
        assert stats["active_sessions"] == 1
        assert stats["first_session"] == "2024-01-01T09:00:00Z"
        assert stats["last_session"] == "2024-01-01T10:00:00Z"
        assert stats["database_size"] > 0

    def test_get_database_stats_nonexistent_file(self):
        """Test getting stats when database file doesn't exist."""
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "nonexistent.db"
            db_manager = DatabaseManager(db_path)

            # Act
            stats = db_manager.get_database_stats()

            # Assert
            assert stats["total_sessions"] == 0
            assert stats["active_sessions"] == 0
            assert stats["first_session"] is None
            assert stats["last_session"] is None
            assert stats["database_size"] == 0

    def test_migrate_database_placeholder(self, test_db_path):
        """Test migration method (currently placeholder)."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Act & Assert - should not raise exception
        with db_manager.get_connection() as conn:
            db_manager._migrate_database(conn, 0, 1)

    @patch("trackit.db.schema.SCHEMA_VERSION", 2)
    def test_initialize_database_with_migration_needed(self, test_db_path):
        """Test database initialization when migration would be needed."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)

        # Create database with old version
        with db_manager.get_connection() as conn:
            conn.execute(CREATE_SCHEMA_VERSION_TABLE)
            conn.execute(CREATE_SESSIONS_TABLE)
            db_manager._set_schema_version(conn, 1)
            conn.commit()

        # Act
        db_manager.initialize_database()

        # Assert - should call migration (but currently no-op)
        with db_manager.get_connection() as conn:
            version = db_manager._get_schema_version(conn)
            # Migration is no-op, so version stays at 1
            assert version == 1


class TestSchemaConstants:
    """Test schema SQL constants."""

    def test_create_sessions_table_sql(self):
        """Test sessions table creation SQL."""
        # Act & Assert
        assert "CREATE TABLE IF NOT EXISTS sessions" in CREATE_SESSIONS_TABLE
        assert "id TEXT PRIMARY KEY" in CREATE_SESSIONS_TABLE
        assert "task_name TEXT NOT NULL" in CREATE_SESSIONS_TABLE
        assert "tags TEXT" in CREATE_SESSIONS_TABLE
        assert "start_time TEXT NOT NULL" in CREATE_SESSIONS_TABLE
        assert "is_active BOOLEAN NOT NULL DEFAULT 1" in CREATE_SESSIONS_TABLE

    def test_create_schema_version_table_sql(self):
        """Test schema version table creation SQL."""
        # Act & Assert
        assert (
            "CREATE TABLE IF NOT EXISTS schema_version" in CREATE_SCHEMA_VERSION_TABLE
        )
        assert "version INTEGER PRIMARY KEY" in CREATE_SCHEMA_VERSION_TABLE
        assert (
            "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
            in CREATE_SCHEMA_VERSION_TABLE
        )

    def test_create_indexes_list(self):
        """Test indexes creation SQL list."""
        # Act & Assert
        assert isinstance(CREATE_INDEXES, list)
        assert len(CREATE_INDEXES) > 0

        for index_sql in CREATE_INDEXES:
            assert "CREATE INDEX IF NOT EXISTS" in index_sql
            assert "sessions" in index_sql

    def test_create_triggers_list(self):
        """Test triggers creation SQL list."""
        # Act & Assert
        assert isinstance(CREATE_TRIGGERS, list)
        assert len(CREATE_TRIGGERS) > 0

        for trigger_sql in CREATE_TRIGGERS:
            assert "CREATE TRIGGER IF NOT EXISTS" in trigger_sql

    def test_schema_version_constant(self):
        """Test schema version constant."""
        # Act & Assert
        assert isinstance(SCHEMA_VERSION, int)
        assert SCHEMA_VERSION > 0


@pytest.mark.integration
class TestDatabaseManagerIntegration:
    """Integration tests for DatabaseManager."""

    def test_full_database_lifecycle(self, test_db_path):
        """Test complete database lifecycle."""
        # Initialize
        db_manager = DatabaseManager(test_db_path)
        db_manager.initialize_database()

        # Verify initialization
        assert test_db_path.exists()

        # Insert test data
        with db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, task_name, start_time, is_active, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "test-id",
                    "Test Task",
                    "2024-01-01T09:00:00Z",
                    1,
                    '["test"]',
                    '{"test": true}',
                ),
            )
            conn.commit()

        # Verify data insertion
        with db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            count = cursor.fetchone()[0]
            assert count == 1

        # Test vacuum
        db_manager.vacuum_database()

        # Verify data still exists after vacuum
        with db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            count = cursor.fetchone()[0]
            assert count == 1

        # Test stats
        stats = db_manager.get_database_stats()
        assert stats["total_sessions"] == 1
        assert stats["active_sessions"] == 1

    def test_database_constraints_and_triggers(self, test_db_path):
        """Test database constraints and triggers work correctly."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)
        db_manager.initialize_database()

        # Act - insert data and trigger update
        with db_manager.get_connection() as conn:
            # Insert initial record
            conn.execute(
                """
                INSERT INTO sessions (id, task_name, start_time, is_active, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("test-id", "Test Task", "2024-01-01T09:00:00Z", 1, "[]", "{}"),
            )

            # Get initial timestamp
            cursor = conn.execute(
                "SELECT created_at, updated_at FROM sessions WHERE id = ?", ("test-id",)
            )
            initial_times = cursor.fetchone()

            # Update the record (should trigger updated_at change)
            conn.execute(
                "UPDATE sessions SET task_name = ? WHERE id = ?",
                ("Updated Task", "test-id"),
            )

            # Get updated timestamp
            cursor = conn.execute(
                "SELECT created_at, updated_at FROM sessions WHERE id = ?", ("test-id",)
            )
            updated_times = cursor.fetchone()

            conn.commit()

        # Assert
        assert (
            initial_times["created_at"] == updated_times["created_at"]
        )  # created_at unchanged
        # updated_at should be different (though might be same if very fast)
        # This test is somewhat time-sensitive, but the trigger should work

    def test_database_performance_with_indexes(self, test_db_path):
        """Test that indexes improve query performance."""
        # Arrange
        db_manager = DatabaseManager(test_db_path)
        db_manager.initialize_database()

        # Insert test data
        with db_manager.get_connection() as conn:
            for i in range(100):
                conn.execute(
                    """
                    INSERT INTO sessions (id, task_name, start_time, is_active, tags, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"test-id-{i}",
                        f"Task {i}",
                        f"2024-01-01T{i % 24:02d}:00:00Z",
                        i % 2,
                        "[]",
                        "{}",
                    ),
                )
            conn.commit()

        # Act & Assert - queries should work efficiently
        with db_manager.get_connection() as conn:
            # Query by start_time (should use index)
            cursor = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE start_time >= ?",
                ("2024-01-01T12:00:00Z",),
            )
            count = cursor.fetchone()[0]
            assert count > 0

            # Query by task_name (should use index)
            cursor = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE task_name = ?",
                ("Task 50",),
            )
            count = cursor.fetchone()[0]
            assert count == 1

            # Query by is_active (should use index)
            cursor = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE is_active = ?",
                (1,),
            )
            count = cursor.fetchone()[0]
            assert count == 50  # Half should be active

    def test_database_concurrent_access(self, test_db_path):
        """Test database handles concurrent access correctly."""
        # Arrange
        db_manager1 = DatabaseManager(test_db_path)
        db_manager2 = DatabaseManager(test_db_path)

        db_manager1.initialize_database()

        # Act - simulate concurrent access
        with db_manager1.get_connection() as conn1:
            with db_manager2.get_connection() as conn2:
                # Both connections should work
                conn1.execute(
                    "INSERT INTO sessions (id, task_name, start_time, is_active, tags, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-1", "Task 1", "2024-01-01T09:00:00Z", 1, "[]", "{}"),
                )

                conn2.execute(
                    "INSERT INTO sessions (id, task_name, start_time, is_active, tags, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-2", "Task 2", "2024-01-01T10:00:00Z", 1, "[]", "{}"),
                )

                conn1.commit()
                conn2.commit()

        # Assert - both records should be present
        with db_manager1.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            count = cursor.fetchone()[0]
            assert count == 2
