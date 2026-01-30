"""Google Calendar API wrapper."""

import os
import pickle
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Scopes required for reading and writing calendar events
SCOPES = ['https://www.googleapis.com/auth/calendar']


class CalendarAPI:
    """Wrapper for Google Calendar API operations."""

    def __init__(self, credentials_file: str):
        """Initialize the Calendar API client.

        Args:
            credentials_file: Path to credentials.json file
        """
        self.credentials_file = credentials_file
        self.token_file = 'token.pickle'
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Calendar API."""
        creds = None

        # Load token from file if it exists
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

        # If no valid credentials, let user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_file}\n"
                        "Please download it from Google Cloud Console."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)

        self.service = build('calendar', 'v3', credentials=creds)

    def get_events(self, calendar_id: str, time_min: datetime, time_max: datetime) -> List[Dict[str, Any]]:
        """Get events from a calendar within a time range.

        Args:
            calendar_id: Calendar ID
            time_min: Start of time range
            time_max: End of time range

        Returns:
            List of event dictionaries
        """
        try:
            # Format datetime as RFC3339 with 'Z' suffix
            # Replace '+00:00' with 'Z' for proper UTC format
            time_min_str = time_min.isoformat().replace('+00:00', 'Z')
            time_max_str = time_max.isoformat().replace('+00:00', 'Z')

            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min_str,
                timeMax=time_max_str,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            return events_result.get('items', [])

        except HttpError as error:
            print(f"Error fetching events from {calendar_id}: {error}")
            return []

    def create_event(self, calendar_id: str, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new event in a calendar.

        Args:
            calendar_id: Target calendar ID
            event_data: Event data dictionary

        Returns:
            Created event dictionary or None on failure
        """
        try:
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_data
            ).execute()

            return event

        except HttpError as error:
            print(f"Error creating event: {error}")
            return None

    def update_event(self, calendar_id: str, event_id: str, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing event.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID to update
            event_data: Updated event data

        Returns:
            Updated event dictionary or None on failure
        """
        try:
            event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_data
            ).execute()

            return event

        except HttpError as error:
            print(f"Error updating event {event_id}: {error}")
            return None

    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete an event from a calendar.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID to delete

        Returns:
            True on success, False on failure
        """
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()

            return True

        except HttpError as error:
            print(f"Error deleting event {event_id}: {error}")
            return False

    def get_event(self, calendar_id: str, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event by ID.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID

        Returns:
            Event dictionary or None if not found
        """
        try:
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()

            return event

        except HttpError as error:
            if error.resp.status == 404:
                return None
            print(f"Error fetching event {event_id}: {error}")
            return None

    def list_calendars(self) -> List[Dict[str, Any]]:
        """List all calendars accessible to the authenticated user.

        Returns:
            List of calendar dictionaries with id, summary, and access role
        """
        try:
            calendar_list = self.service.calendarList().list().execute()
            return calendar_list.get('items', [])

        except HttpError as error:
            print(f"Error listing calendars: {error}")
            return []
