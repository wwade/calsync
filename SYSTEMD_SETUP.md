# Systemd Timer Setup for CalSync

This guide explains how to set up calsync to run automatically once per day using systemd.

## Features

- **Daily execution**: Runs once per day at 9 AM
- **Catch-up on missed runs**: If your computer was off/asleep, it runs immediately on boot
- **Error notifications**: Desktop notifications appear only when sync fails
- **Logging**: All output goes to systemd journal

## Installation

### 1. Install the systemd units

```bash
# Copy the unit files to your user systemd directory
mkdir -p ~/.config/systemd/user/
cp calsync.service ~/.config/systemd/user/
cp calsync.timer ~/.config/systemd/user/
cp calsync-failure@.service ~/.config/systemd/user/

# Reload systemd to recognize the new units
systemctl --user daemon-reload
```

### 2. Enable and start the timer

```bash
# Enable the timer to start on boot
systemctl --user enable calsync.timer

# Start the timer now
systemctl --user start calsync.timer

# Enable lingering so the timer runs even when you're not logged in
sudo loginctl enable-linger $USER
```

## Customization

### Change the schedule

Edit `~/.config/systemd/user/calsync.timer` and modify the `OnCalendar` line:

```ini
# Run at 6 PM daily
OnCalendar=18:00

# Run every 12 hours
OnCalendar=00/12:00:00

# Run on weekdays at 8 AM
OnCalendar=Mon-Fri 08:00
```

After changes, reload systemd:
```bash
systemctl --user daemon-reload
systemctl --user restart calsync.timer
```

### Change notification method

Edit `~/.config/systemd/user/calsync-failure@.service`:

**For email notifications:**
```ini
ExecStart=/usr/bin/mail -s "Calendar Sync Failed" you@example.com
```

**For Slack/Discord webhook:**
```ini
ExecStart=/usr/bin/curl -X POST -H 'Content-type: application/json' --data '{"text":"CalSync failed!"}' YOUR_WEBHOOK_URL
```

### Use different config file

Edit `~/.config/systemd/user/calsync.service` and modify the `ExecStart` line:
```ini
ExecStart=VENV-DIR/bin/python3 calsync.py --config /path/to/custom-config.yaml
```

## Management Commands

```bash
# Check timer status
systemctl --user status calsync.timer

# Check service status
systemctl --user status calsync.service

# See when the timer will run next
systemctl --user list-timers calsync.timer

# View logs
journalctl --user -u calsync.service

# View recent logs
journalctl --user -u calsync.service -n 50

# Follow logs in real-time
journalctl --user -u calsync.service -f

# Manually trigger a sync (useful for testing)
systemctl --user start calsync.service

# Stop the timer
systemctl --user stop calsync.timer

# Disable the timer (prevents auto-start on boot)
systemctl --user disable calsync.timer
```

## Troubleshooting

### Timer not running when computer wakes up

Ensure lingering is enabled:
```bash
sudo loginctl enable-linger $USER
loginctl show-user $USER | grep Linger
```

Should show: `Linger=yes`

### Notification not appearing

Test the notification manually:
```bash
systemctl --user start calsync-failure@calsync.service
```

Check if notify-send works:
```bash
notify-send "Test" "This is a test notification"
```

If notifications don't work, you may need to set the `DISPLAY` and `DBUS_SESSION_BUS_ADDRESS` environment variables in the failure service.

### Check if timer is active

```bash
systemctl --user list-timers --all
```

Look for `calsync.timer` in the list. It should show the next activation time.

### Permission issues

Make sure the service has access to your Google credentials:
```bash
ls -la token.pickle
ls -la credentials.json
```

## Uninstallation

```bash
# Stop and disable the timer
systemctl --user stop calsync.timer
systemctl --user disable calsync.timer

# Remove the unit files
rm ~/.config/systemd/user/calsync.service
rm ~/.config/systemd/user/calsync.timer
rm ~/.config/systemd/user/calsync-failure@.service

# Reload systemd
systemctl --user daemon-reload
```
