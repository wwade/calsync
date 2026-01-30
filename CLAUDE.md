# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CalSync is a Python tool that synchronizes events from read-only (imported) Google calendars to a personal calendar. It's designed to run as a cron job or systemd timer for automatic synchronization.

## Architecture

The codebase follows a clean separation of concerns with three core modules:

1. **calendar_api.py**: Google Calendar API wrapper
   - Handles OAuth2 authentication (stores tokens in `token.pickle`)
   - Provides methods for CRUD operations on calendar events
   - Uses `credentials.json` for OAuth client configuration

2. **state_db.py**: SQLite-based state tracking
   - Maintains sync state in `~/.local/share/calsync/sync_state.db` (configurable)
   - Tracks: source_event_id → target_event_id mappings
   - Stores last_synced timestamps to detect updates
   - Uses indexes for efficient lookups on both source and target events

3. **sync_engine.py**: Core synchronization logic
   - Compares source calendar events with sync state
   - Creates new events with configurable prefix (e.g., "[Synced] ")
   - Updates events when source changes (compares timestamps)
   - Optionally deletes target events when source is deleted
   - Operates within configurable time windows (days_ahead/days_back)

4. **calsync.py**: CLI entry point
   - Loads YAML configuration from `config.yaml`
   - Orchestrates the sync process for multiple source calendars
   - Supports --dry-run and --verbose flags

## Development Commands

### Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running
```bash
# Basic sync
./calsync.py

# Dry run (see what would happen)
./calsync.py --dry-run

# Verbose output
./calsync.py --verbose

# Custom config file
./calsync.py --config my-config.yaml
```

### Configuration
Copy `config.yaml.example` to `config.yaml` and customize:
- `target_calendar_id`: Usually "primary" or your email address
- `source_calendars`: List of read-only calendars to sync from
- `sync.days_ahead/days_back`: Time window for syncing
- `sync.event_prefix`: Prefix added to synced events
- `sync.delete_on_source_delete`: Whether to clean up deleted events

## Key Behaviors

- **Duplicate Prevention**: Uses source event IDs to track what's been synced; won't create duplicates
- **Update Detection**: Compares event `updated` timestamp with `last_synced` to detect changes
- **State Tracking**: SQLite database maintains mapping between source and target events
- **Time Windows**: Only syncs events within configured days_ahead/days_back range
- **Dry Run**: Use `--dry-run` to preview changes without modifying calendars

## Authentication Flow

1. First run requires `credentials.json` (OAuth client from Google Cloud Console)
2. Opens browser for user authorization
3. Stores refresh token in `token.pickle` for subsequent runs
4. Automatically refreshes expired tokens

## Important Notes

- All datetime operations use timezone-aware UTC timestamps
- The tool is idempotent: safe to run multiple times
- State database grows over time; no cleanup mechanism currently implemented
- Event updates are detected by comparing timestamps, not content
