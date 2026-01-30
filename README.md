# CalSync - Google Calendar Synchronization Tool

A Python tool to synchronize events from read-only (imported) Google calendars to your personal calendar, making them visible to people you share your calendar with.

## Features

- ✅ Sync events from multiple source calendars to your personal calendar
- ✅ Tracks sync state to avoid duplicates
- ✅ Detects and updates changed events
- ✅ Configurable sync window (days ahead/back)
- ✅ Optionally delete synced events when source is deleted
- ✅ Add custom prefix to synced events (e.g., "[Synced] ")
- ✅ Designed to run as a cron job for automatic synchronization

## Setup

### 1. Install Dependencies

```bash
# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
# venv\Scripts\activate  # On Windows

# Install required packages
pip install -r requirements.txt
```

### 2. Set Up Google Calendar API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Calendar API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as the application type
   - Download the credentials JSON file
5. Save the downloaded file as `credentials.json` in this directory

### 3. Configure CalSync

```bash
# Copy the example config
cp config.yaml.example config.yaml

# Edit config.yaml with your settings
nano config.yaml  # or use your preferred editor
```

Important configuration items:

- **target_calendar_id**: Usually `"primary"` for your main calendar, or your email address
- **source_calendars**: List your read-only calendars with their IDs
- **event_prefix**: Prefix added to synced events (e.g., `"[Synced] "`)
- **days_ahead/days_back**: How far to sync into future/past

#### Finding Calendar IDs

To find a calendar ID:
1. Open Google Calendar in a web browser
2. Click the three dots next to the calendar name
3. Select "Settings and sharing"
4. Scroll down to "Integrate calendar"
5. Copy the "Calendar ID" (looks like `xyz123@group.calendar.google.com`)

### 4. First Run

```bash
# Make the script executable
chmod +x calsync.py

# Run the first sync
./calsync.py
```

On first run, you'll be prompted to authorize the application in your browser. This creates a `token.pickle` file for subsequent runs.

## Usage

### Manual Sync

```bash
# Basic sync
./calsync.py

# Use a different config file
./calsync.py --config my-config.yaml

# Dry run (see what would be synced without making changes)
./calsync.py --dry-run

# Verbose output
./calsync.py --verbose
```

### Systemd Timer Setup

For a more robust solution using systemd, see SYSTEMD_SETUP.md.

## How It Works

1. **Authentication**: Uses OAuth 2.0 to access your Google Calendar
2. **State Tracking**: Maintains a SQLite database of synced events
3. **Event Fetching**: Retrieves events from source calendars within configured time window
4. **Sync Logic**:
   - Creates new events that don't exist in target calendar
   - Updates existing events if source has changed
   - Optionally deletes events when source is deleted
5. **Duplicate Prevention**: Uses event IDs to track what's been synced

## Configuration Options

See `config.yaml.example` for all available options with detailed comments.

Key settings:
- `days_ahead`: How many days into the future to sync (default: 90)
- `days_back`: How many days into the past to check for updates (default: 7)
- `event_prefix`: Text prepended to synced event titles
- `sync_description`: Whether to copy event descriptions
- `delete_on_source_delete`: Whether to delete synced events when source is deleted

## Troubleshooting

### "Credentials file not found"
- Make sure you've downloaded `credentials.json` from Google Cloud Console
- Place it in the same directory as `calsync.py`

### "Config file not found"
- Copy `config.yaml.example` to `config.yaml`
- Customize with your calendar IDs

### Events not syncing
- Check that calendar IDs are correct in config
- Verify you have read access to source calendars
- Try running with `--verbose` flag for more details

### Permission errors
- Ensure you granted calendar access during first authorization
- Delete `token.pickle` and re-run to re-authorize

## Security Notes

- `credentials.json`: Contains your OAuth client ID/secret (keep private)
- `token.pickle`: Contains your access tokens (keep private, already in .gitignore)
- `sync_state.db`: Only contains event IDs and timestamps (low sensitivity)

## License

This project is provided as-is for personal use.
