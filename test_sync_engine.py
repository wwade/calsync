"""Tests for calendar synchronization behavior."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from sync_engine import SyncEngine


def _engine() -> SyncEngine:
    return SyncEngine(
        Mock(),
        Mock(),
        {"target_calendar_id": "target", "sync": {}},
    )


def test_timed_event_that_has_ended_is_past():
    event = {"end": {"dateTime": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}}

    assert _engine()._event_is_past(event)


def test_ongoing_event_is_not_past():
    event = {"end": {"dateTime": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()}}

    assert not _engine()._event_is_past(event)


def test_all_day_event_uses_exclusive_end_date():
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()

    assert _engine()._event_is_past({"end": {"date": yesterday}})


def test_event_without_end_is_not_assumed_past():
    assert not _engine()._event_is_past({})


def test_sync_preserves_missing_past_event():
    api = Mock()
    api.get_events.return_value = []
    api.get_event.return_value = {
        "summary": "Appointment",
        "start": {"dateTime": "2026-08-19T10:00:00Z"},
        "end": {"dateTime": "2026-08-19T11:00:00Z"},
    }
    state_db = Mock()
    state_db.get_all_synced_events.return_value = [("source-event", "target-event")]
    state_db.get_synced_event.return_value = (
        "target",
        "target-event",
        datetime.now(timezone.utc),
    )
    engine = SyncEngine(
        api,
        state_db,
        {"target_calendar_id": "target", "sync": {"delete_on_source_delete": True}},
    )

    engine.sync_calendar("Appointments", "source")

    state_db.delete_sync_record.assert_not_called()
    api.delete_event.assert_not_called()


def test_sync_still_deletes_missing_future_event():
    api = Mock()
    api.get_events.return_value = []
    api.get_event.return_value = {
        "summary": "Appointment",
        "start": {"dateTime": "2099-08-20T10:00:00Z"},
        "end": {"dateTime": "2099-08-20T11:00:00Z"},
    }
    api.delete_event.return_value = True
    state_db = Mock()
    state_db.get_all_synced_events.return_value = [("source-event", "target-event")]
    state_db.get_synced_event.return_value = (
        "target",
        "target-event",
        datetime.now(timezone.utc),
    )
    state_db.delete_sync_record.return_value = "target-event"
    engine = SyncEngine(
        api,
        state_db,
        {"target_calendar_id": "target", "sync": {"delete_on_source_delete": True}},
    )

    engine.sync_calendar("Appointments", "source")

    state_db.delete_sync_record.assert_called_once_with("source", "source-event")
    api.delete_event.assert_called_once_with("target", "target-event")
