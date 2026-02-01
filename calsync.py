#!/usr/bin/env python3
"""Calendar synchronization tool for Google Calendar."""

import argparse
import os
from socket import gaierror
import sys

from prettytable import PrettyTable
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from urllib3.exceptions import NameResolutionError, NewConnectionError
import yaml

from calendar_api import CalendarAPI
from state_db import StateDB
from sync_engine import SyncEngine


def _log_retry_attempt(retry_state):
    """Log retry attempts for network failures."""
    print(
        f"Network error occurred (attempt {retry_state.attempt_number}/5): "
        f"{retry_state.outcome.exception()}"
    )
    print(f"Retrying in {retry_state.next_action.sleep} seconds...")


@retry(
    retry=retry_if_exception_type((gaierror, NameResolutionError, NewConnectionError, OSError)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    before_sleep=_log_retry_attempt,
)
def initialize_calendar_api(credentials_file: str) -> CalendarAPI:
    """Initialize CalendarAPI with retry logic for network failures.

    Args:
        credentials_file: Path to credentials file

    Returns:
        Initialized CalendarAPI instance

    Raises:
        Exception: If initialization fails after all retry attempts
    """
    return CalendarAPI(credentials_file)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        print("Please copy config.yaml.example to config.yaml and customize it.")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync events from read-only Google calendars to your personal calendar"
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be synced without making changes"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="Reconcile mode: detect and record existing events in target calendar that match source events",
    )
    parser.add_argument(
        "--list-calendars",
        action="store_true",
        help="List all available calendars with their IDs and exit",
    )

    args = parser.parse_args()

    # Handle --list-calendars mode (doesn't require config file)
    if args.list_calendars:
        # Try to load config to get credentials file path, but don't require it
        try:
            if os.path.exists(args.config):
                config = load_config(args.config)
                credentials_file = config.get("credentials_file", "credentials.json")
            else:
                credentials_file = "credentials.json"
        except Exception:
            credentials_file = "credentials.json"
        if not os.path.exists(credentials_file):
            print(f"Error: Credentials file not found: {credentials_file}")
            print("\nTo set up Google Calendar API credentials:")
            print("1. Go to https://console.cloud.google.com/")
            print("2. Create a new project or select existing one")
            print("3. Enable the Google Calendar API")
            print("4. Create OAuth 2.0 credentials (Desktop app)")
            print("5. Download the credentials JSON file")
            print(f"6. Save it as '{credentials_file}' in this directory")
            sys.exit(1)

        try:
            api = initialize_calendar_api(credentials_file)
            calendars = api.list_calendars()

            if not calendars:
                print("No calendars found.")
                sys.exit(0)

            print("\nAvailable Calendars:")
            tbl = PrettyTable(("name", "ID", "access"))
            tbl.align = "l"
            for cal in calendars:
                cal_id = cal.get("id", "N/A")
                summary = cal.get("summary", "N/A")
                access_role = cal.get("accessRole", "N/A")
                primary = " (Primary)" if cal.get("primary", False) else ""

                tbl.add_row((f"{summary}{primary}", str(cal_id), str(access_role)))

            print(tbl)
            print(f"Total: {len(calendars)} calendar(s)")
            print("\nUse these IDs in your config.yaml file.")

        except Exception as e:
            print(f"Error listing calendars: {e}")
            sys.exit(1)

        sys.exit(0)

    # Load configuration
    config = load_config(args.config)

    # Check if credentials file exists
    credentials_file = config.get("credentials_file", "credentials.json")
    if not os.path.exists(credentials_file):
        print(f"\nError: Credentials file not found: {credentials_file}")
        print("\nTo set up Google Calendar API credentials:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing one")
        print("3. Enable the Google Calendar API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print("5. Download the credentials JSON file")
        print(f"6. Save it as '{credentials_file}' in this directory")
        sys.exit(1)

    try:
        api = initialize_calendar_api(credentials_file)
        state_db = StateDB(config.get("state_db", "~/.local/share/calsync/sync_state.db"))
        sync_engine = SyncEngine(api, state_db, config, dry_run=args.dry_run)

        if args.dry_run:
            print("\n*** DRY RUN MODE - No changes will be made ***\n")

        if args.reconcile:
            print("\n*** RECONCILE MODE - Detecting existing events ***\n")

        # Sync each source calendar
        source_calendars = config.get("source_calendars", [])

        if not source_calendars:
            print("\nWarning: No source calendars configured.")
            print("Please add source calendars to your config.yaml file.")
            sys.exit(0)

        for source_cal in source_calendars:
            name = source_cal["name"]
            calendar_id = source_cal["calendar_id"]
            if args.reconcile:
                sync_engine.reconcile_calendar(name, calendar_id)
            else:
                sync_engine.sync_calendar(name, calendar_id)

        # Clean up
        state_db.close()

    except KeyboardInterrupt:
        print("\n\nSync interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during sync: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
