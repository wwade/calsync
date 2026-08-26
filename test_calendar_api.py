# Copyright (c) 2026 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
"""Tests for Google Calendar API operations."""

from unittest.mock import Mock

from calendar_api import CalendarAPI


def test_get_events_fetches_all_pages():
    api = object.__new__(CalendarAPI)
    request = Mock()
    request.execute.side_effect = [
        {"items": [{"id": "first"}], "nextPageToken": "next-page"},
        {"items": [{"id": "second"}]},
    ]
    api.service = Mock()
    api.service.events.return_value.list.return_value = request

    events = api.get_events("calendar", Mock(), Mock())

    assert events == [{"id": "first"}, {"id": "second"}]
    assert api.service.events.return_value.list.call_count == 2
