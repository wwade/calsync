"""State database management for tracking synced events."""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class StateDB:
    """Manages SQLite database for tracking event sync state."""

    def __init__(self, db_path: str):
        """Initialize the state database.

        Args:
            db_path: Path to SQLite database file
        """
        # Expand user home directory
        self.db_path = os.path.expanduser(db_path)

        # Create parent directories if needed
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self._init_schema()

    def _init_schema(self):
        """Create database schema if it doesn't exist."""
        cursor = self.conn.cursor()

        # Table for tracking synced events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS synced_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_calendar_id TEXT NOT NULL,
                source_event_id TEXT NOT NULL,
                target_calendar_id TEXT NOT NULL,
                target_event_id TEXT NOT NULL,
                source_updated TIMESTAMP,
                last_synced TIMESTAMP NOT NULL,
                UNIQUE(source_calendar_id, source_event_id)
            )
        """)

        # Index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_event
            ON synced_events(source_calendar_id, source_event_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_target_event
            ON synced_events(target_event_id)
        """)

        self.conn.commit()

    def get_synced_event(
        self, source_calendar_id: str, source_event_id: str
    ) -> tuple[str, str, datetime] | None:
        """Get target event info for a synced event.

        Args:
            source_calendar_id: Source calendar ID
            source_event_id: Source event ID

        Returns:
            Tuple of (target_calendar_id, target_event_id, last_synced) or None
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT target_calendar_id, target_event_id, last_synced
            FROM synced_events
            WHERE source_calendar_id = ? AND source_event_id = ?
        """,
            (source_calendar_id, source_event_id),
        )

        result = cursor.fetchone()
        if result:
            # Parse as timezone-aware datetime in UTC
            last_synced = datetime.fromisoformat(result[2])
            if last_synced.tzinfo is None:
                # If stored as naive, assume it's UTC
                last_synced = last_synced.replace(tzinfo=timezone.utc)
            return result[0], result[1], last_synced
        return None

    def record_sync(
        self,
        source_calendar_id: str,
        source_event_id: str,
        target_calendar_id: str,
        target_event_id: str,
        source_updated: datetime | None = None,
    ):
        """Record a synced event.

        Args:
            source_calendar_id: Source calendar ID
            source_event_id: Source event ID
            target_calendar_id: Target calendar ID
            target_event_id: Target event ID
            source_updated: When the source event was last updated
        """
        cursor = self.conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        source_updated_str = source_updated.isoformat() if source_updated else None

        cursor.execute(
            """
            INSERT OR REPLACE INTO synced_events
            (source_calendar_id, source_event_id, target_calendar_id, target_event_id,
             source_updated, last_synced)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                source_calendar_id,
                source_event_id,
                target_calendar_id,
                target_event_id,
                source_updated_str,
                now,
            ),
        )

        self.conn.commit()

    def delete_sync_record(self, source_calendar_id: str, source_event_id: str) -> str | None:
        """Delete a sync record and return the target event ID.

        Args:
            source_calendar_id: Source calendar ID
            source_event_id: Source event ID

        Returns:
            Target event ID if found, None otherwise
        """
        # First get the target event ID
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT target_event_id FROM synced_events
            WHERE source_calendar_id = ? AND source_event_id = ?
        """,
            (source_calendar_id, source_event_id),
        )

        result = cursor.fetchone()
        if result:
            target_event_id = result[0]

            # Delete the record
            cursor.execute(
                """
                DELETE FROM synced_events
                WHERE source_calendar_id = ? AND source_event_id = ?
            """,
                (source_calendar_id, source_event_id),
            )

            self.conn.commit()
            return target_event_id

        return None

    def get_all_synced_events(self, source_calendar_id: str) -> list[tuple[str, str]]:
        """Get all synced events for a source calendar.

        Args:
            source_calendar_id: Source calendar ID

        Returns:
            List of (source_event_id, target_event_id) tuples
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT source_event_id, target_event_id
            FROM synced_events
            WHERE source_calendar_id = ?
        """,
            (source_calendar_id,),
        )

        return cursor.fetchall()

    def get_by_target_event(self, target_event_id: str) -> tuple[str, str] | None:
        """Check if a target event is already tracked.

        Args:
            target_event_id: Target event ID

        Returns:
            Tuple of (source_calendar_id, source_event_id) or None
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT source_calendar_id, source_event_id
            FROM synced_events
            WHERE target_event_id = ?
        """,
            (target_event_id,),
        )

        result = cursor.fetchone()
        return result if result else None

    def close(self):
        """Close the database connection."""
        self.conn.close()
