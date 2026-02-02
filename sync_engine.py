"""Core sync engine for calendar synchronization."""

from datetime import datetime, timedelta, timezone
from typing import Any

from calendar_api import CalendarAPI
from state_db import StateDB


class SyncEngine:
    """Handles synchronization logic between source and target calendars."""

    def __init__(
        self, api: CalendarAPI, state_db: StateDB, config: dict[str, Any], dry_run: bool = False
    ):
        """Initialize the sync engine.

        Args:
            api: CalendarAPI instance
            state_db: StateDB instance
            config: Configuration dictionary
            dry_run: If True, only simulate changes without making them
        """
        self.api = api
        self.state_db = state_db
        self.config = config
        self.target_calendar_id = config["target_calendar_id"]
        self.event_prefix = config["sync"].get("event_prefix", "")
        self.sync_description = config["sync"].get("sync_description", True)
        self.delete_on_source_delete = config["sync"].get("delete_on_source_delete", False)
        self.dry_run = dry_run

    def sync_calendar(self, source_name: str, source_calendar_id: str):
        """Sync events from a source calendar to target calendar.

        Args:
            source_name: Human-readable name of source calendar
            source_calendar_id: Source calendar ID
        """
        # Calculate time range
        days_back = self.config["sync"].get("days_back", 7)
        days_ahead = self.config["sync"].get("days_ahead", 90)
        time_min = datetime.now(timezone.utc) - timedelta(days=days_back)
        time_max = datetime.now(timezone.utc) + timedelta(days=days_ahead)

        # Get events from source calendar
        source_events = self.api.get_events(source_calendar_id, time_min, time_max)

        # Track statistics
        stats = {"created": 0, "updated": 0, "skipped": 0, "deleted": 0}

        # Get all currently synced events for this calendar
        synced_events = {
            event_id for event_id, _ in self.state_db.get_all_synced_events(source_calendar_id)
        }
        current_source_event_ids = set()

        # Process each source event
        for source_event in source_events:
            source_event_id = source_event["id"]
            current_source_event_ids.add(source_event_id)

            # Check if event is already synced
            sync_record = self.state_db.get_synced_event(source_calendar_id, source_event_id)

            if sync_record:
                # Event already synced, check if update needed
                _, target_event_id, last_synced = sync_record

                # Get source event updated time
                source_updated = self._get_updated_time(source_event)

                if source_updated and source_updated > last_synced:
                    # Event has been updated, sync the changes
                    if self.dry_run:
                        stats["updated"] += 1
                        date_str = self._format_event_datetime(source_event)
                        title = self._get_event_title(source_event)
                        print(f'  [DRY RUN] Would update event Date={date_str} "{title}"')
                    elif self._update_synced_event(source_event, target_event_id):
                        self.state_db.record_sync(
                            source_calendar_id,
                            source_event_id,
                            self.target_calendar_id,
                            target_event_id,
                            source_updated,
                        )
                        stats["updated"] += 1
                        date_str = self._format_event_datetime(source_event)
                        title = self._get_event_title(source_event)
                        print(f'Updated event Date={date_str} "{title}"')
                    else:
                        stats["skipped"] += 1
                else:
                    stats["skipped"] += 1
            else:
                # New event, create it
                if self.dry_run:
                    stats["created"] += 1
                    date_str = self._format_event_datetime(source_event)
                    title = self._get_event_title(source_event)
                    print(f'  [DRY RUN] Would create event Date={date_str} "{title}"')
                else:
                    target_event = self._create_synced_event(source_event)
                    if target_event:
                        target_event_id = target_event["id"]
                        source_updated = self._get_updated_time(source_event)

                        self.state_db.record_sync(
                            source_calendar_id,
                            source_event_id,
                            self.target_calendar_id,
                            target_event_id,
                            source_updated,
                        )
                        stats["created"] += 1
                        date_str = self._format_event_datetime(source_event)
                        title = self._get_event_title(source_event)
                        print(f'Added event Date={date_str} "{title}"')
                    else:
                        stats["skipped"] += 1

        # Handle deleted events
        if self.delete_on_source_delete:
            deleted_events = synced_events - current_source_event_ids
            for deleted_event_id in deleted_events:
                if self.dry_run:
                    # In dry-run mode, just peek at what would be deleted
                    sync_record = self.state_db.get_synced_event(
                        source_calendar_id, deleted_event_id
                    )
                    if sync_record:
                        stats["deleted"] += 1
                        # Try to get event details for display
                        _, target_event_id, _ = sync_record
                        target_event = self.api.get_event(self.target_calendar_id, target_event_id)
                        if target_event:
                            date_str = self._format_event_datetime(target_event)
                            title = self._get_event_title(target_event)
                            print(f'  [DRY RUN] Would delete event Date={date_str} "{title}"')
                        else:
                            print(f"  [DRY RUN] Would delete event ID={deleted_event_id}")
                else:
                    # Get event details before deleting
                    sync_record = self.state_db.get_synced_event(
                        source_calendar_id, deleted_event_id
                    )
                    event_info = None
                    if sync_record:
                        _, target_event_id, _ = sync_record
                        target_event = self.api.get_event(self.target_calendar_id, target_event_id)
                        if target_event:
                            date_str = self._format_event_datetime(target_event)
                            title = self._get_event_title(target_event)
                            event_info = f'Date={date_str} "{title}"'
                        else:
                            event_info = f"ID={deleted_event_id}"

                    target_event_id = self.state_db.delete_sync_record(
                        source_calendar_id, deleted_event_id
                    )
                    if target_event_id and self.api.delete_event(
                        self.target_calendar_id, target_event_id
                    ):
                        stats["deleted"] += 1
                        if event_info:
                            print(f"Deleted event {event_info}")
                        else:
                            print(f"Deleted event ID={deleted_event_id}")

        # Print summary
        self._print_stats_summary(stats, source_name, source_calendar_id)

    def reconcile_calendar(self, source_name: str, source_calendar_id: str):
        """Reconcile existing events in target calendar with source events.

        This is useful when the database is not initialized but events already exist
        in the target calendar. It will detect matching events and record them in
        the database to avoid creating duplicates.

        Args:
            source_name: Human-readable name of source calendar
            source_calendar_id: Source calendar ID
        """
        # Calculate time range
        days_back = self.config["sync"].get("days_back", 7)
        days_ahead = self.config["sync"].get("days_ahead", 90)
        time_min = datetime.now(timezone.utc) - timedelta(days=days_back)
        time_max = datetime.now(timezone.utc) + timedelta(days=days_ahead)

        # Get events from source calendar
        source_events = self.api.get_events(source_calendar_id, time_min, time_max)

        # Get events from target calendar
        target_events = self.api.get_events(self.target_calendar_id, time_min, time_max)

        # Build lookup table for target events
        # Key: (summary, start, end) -> event
        target_lookup = {}
        for target_event in target_events:
            key = self._build_event_key(target_event)
            if key:
                target_lookup[key] = target_event

        # Track statistics
        stats = {"reconciled": 0, "already_tracked": 0, "not_found": 0, "target_already_mapped": 0}

        # Try to match each source event with target events
        for source_event in source_events:
            source_event_id = source_event["id"]

            # Check if already tracked in database
            sync_record = self.state_db.get_synced_event(source_calendar_id, source_event_id)
            if sync_record:
                stats["already_tracked"] += 1
                continue

            # Build expected event data and key
            expected_event_data = self._build_event_data(source_event)
            expected_key = self._build_event_key_from_data(expected_event_data)

            if expected_key and expected_key in target_lookup:
                target_event = target_lookup[expected_key]
                target_event_id = target_event["id"]

                # Check if this target event is already mapped to another source event
                existing_mapping = self.state_db.get_by_target_event(target_event_id)
                if existing_mapping:
                    stats["target_already_mapped"] += 1
                    continue

                # Record the mapping
                source_updated = self._get_updated_time(source_event)
                if self.dry_run:
                    stats["reconciled"] += 1
                    date_str = self._format_event_datetime(source_event)
                    title = self._get_event_title(source_event)
                    print(f'  [DRY RUN] Would reconcile event Date={date_str} "{title}"')
                else:
                    self.state_db.record_sync(
                        source_calendar_id,
                        source_event_id,
                        self.target_calendar_id,
                        target_event_id,
                        source_updated,
                    )
                    stats["reconciled"] += 1
                    date_str = self._format_event_datetime(source_event)
                    title = self._get_event_title(source_event)
                    print(f'Reconciled event Date={date_str} "{title}"')
            else:
                stats["not_found"] += 1

        # Print summary
        self._print_stats_summary(stats, source_name, source_calendar_id)

    def _create_synced_event(self, source_event: dict[str, Any]) -> dict[str, Any] | None:
        """Create a new event in target calendar from source event.

        Args:
            source_event: Source event dictionary

        Returns:
            Created event dictionary or None on failure
        """
        event_data = self._build_event_data(source_event)
        return self.api.create_event(self.target_calendar_id, event_data)

    def _update_synced_event(self, source_event: dict[str, Any], target_event_id: str) -> bool:
        """Update an existing synced event.

        Args:
            source_event: Source event dictionary
            target_event_id: Target event ID to update

        Returns:
            True on success, False on failure
        """
        event_data = self._build_event_data(source_event)
        result = self.api.update_event(self.target_calendar_id, target_event_id, event_data)
        return result is not None

    def _build_event_data(self, source_event: dict[str, Any]) -> dict[str, Any]:
        """Build event data for creating/updating in target calendar.

        Args:
            source_event: Source event dictionary

        Returns:
            Event data dictionary
        """
        # Start with basic structure
        event_data = {
            "summary": self.event_prefix + source_event.get("summary", "Untitled Event"),
            "start": source_event["start"],
            "end": source_event["end"],
        }

        # Add description if enabled
        if self.sync_description and "description" in source_event:
            event_data["description"] = source_event["description"]

        # Add location if present
        if "location" in source_event:
            event_data["location"] = source_event["location"]

        # Copy other relevant fields
        if "visibility" in source_event:
            event_data["visibility"] = source_event["visibility"]

        return event_data

    def _get_event_title(self, event: dict[str, Any]) -> str:
        """Get event title for display.

        Args:
            event: Event dictionary

        Returns:
            Event title
        """
        return event.get("summary", "Untitled Event")

    def _format_event_datetime(self, event: dict[str, Any]) -> str:
        """Format event datetime for display.

        Args:
            event: Event dictionary

        Returns:
            Formatted datetime string like "2026-01-30 13:30 (-08:00)"
        """
        start = event.get("start", {})
        start_str = start.get("dateTime") or start.get("date")

        if not start_str:
            return "Unknown date"

        # Parse the datetime
        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))

        # Format the output
        if start.get("dateTime"):
            # Has time component - show date, time, and timezone offset
            tz_offset = dt.strftime("%z")
            # Format offset as (-HH:MM)
            tz_formatted = f"({tz_offset[:3]}:{tz_offset[3:]})" if tz_offset else "(+00:00)"
            return dt.strftime(f"%Y-%m-%d %H:%M {tz_formatted}")
        else:
            # All-day event - just show date
            return dt.strftime("%Y-%m-%d")

    def _get_updated_time(self, event: dict[str, Any]) -> datetime | None:
        """Get the last updated time of an event.

        Args:
            event: Event dictionary

        Returns:
            Updated datetime or None
        """
        updated_str = event.get("updated")
        if updated_str:
            # Parse ISO format datetime
            # Google returns format like '2024-01-29T10:30:00.000Z'
            return datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
        return None

    def _print_stats_summary(
        self, stats: dict[str, int], source_name: str, source_calendar_id: str
    ):
        """Print formatted stats summary, skipping zero values.

        Args:
            stats: Statistics dictionary
            source_name: Human-readable name of source calendar
            source_calendar_id: Source calendar ID
        """
        # Map stat keys to display names
        stat_display_names = {
            "created": "Created",
            "updated": "Updated",
            "skipped": "Skipped",
            "deleted": "Deleted",
            "reconciled": "Reconciled",
            "already_tracked": "AlreadyTracked",
            "not_found": "NotFoundInTarget",
            "target_already_mapped": "TargetAlreadyMapped",
        }

        # Build list of non-zero stats
        non_zero_stats = []
        for key, value in stats.items():
            if value > 0 and key in stat_display_names:
                display_name = stat_display_names[key]
                non_zero_stats.append(f"{display_name}={value}")

        # Format prefix: either non-zero stats or "<No entries>"
        stats_str = " ".join(non_zero_stats) if non_zero_stats else "<No entries>"

        # Print with calendar info
        print(f'{stats_str} Calendar="{source_name}" ID={source_calendar_id}')

    def _build_event_key(self, event: dict[str, Any]) -> tuple | None:
        """Build a key for matching events.

        Args:
            event: Event dictionary

        Returns:
            Tuple of (summary, start_datetime, end_datetime) or None if key cannot be built
        """
        summary = event.get("summary")
        start = event.get("start")
        end = event.get("end")

        if not summary or not start or not end:
            return None

        # Parse datetime strings into timezone-aware datetime objects normalized to UTC
        start_str = start.get("dateTime") or start.get("date")
        end_str = end.get("dateTime") or end.get("date")

        # Parse and normalize to UTC for consistent comparison
        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).astimezone(timezone.utc)

        return (summary, start_dt, end_dt)

    def _build_event_key_from_data(self, event_data: dict[str, Any]) -> tuple | None:
        """Build a key from event data (as created by _build_event_data).

        Args:
            event_data: Event data dictionary

        Returns:
            Tuple of (summary, start_datetime, end_datetime) or None if key cannot be built
        """
        summary = event_data.get("summary")
        start = event_data.get("start")
        end = event_data.get("end")

        if not summary or not start or not end:
            return None

        # Parse datetime strings into timezone-aware datetime objects normalized to UTC
        start_str = start.get("dateTime") or start.get("date")
        end_str = end.get("dateTime") or end.get("date")

        # Parse and normalize to UTC for consistent comparison
        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).astimezone(timezone.utc)

        return (summary, start_dt, end_dt)
