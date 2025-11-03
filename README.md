# Wedding Bot

A Python-based bot for managing wedding communications over the Meshtastic network. This bot runs on a Raspberry Pi and provides various commands for wedding guests and organizers.

## Features

- Real-time messaging over Meshtastic
- Command-based interactions
- Multi-language support (German/English)
- Systemd service for automatic startup

## Installation

1. Clone this repository to your Raspberry Pi
2. Install dependencies:
   ```bash
   pip install meshtastic
   ```

## Usage

### Service Management

```bash
# Start service
sudo systemctl start wedding-bot

# Stop service
sudo systemctl stop wedding-bot

# Restart service
sudo systemctl restart wedding-bot

# Enable auto-start on boot
sudo systemctl enable --now wedding-bot

# Disable auto-start
sudo systemctl disable --now wedding-bot
```

### Viewing Logs

```bash
# Live logs
journalctl -u wedding-bot -f

# Last 10 minutes
journalctl -u wedding-bot --since "10 min ago"
```

### Maintenance

```bash
# Stop service
sudo systemctl stop wedding-bot

# Clear Python cache
find /home/pi -name "*.pyc" -delete
find /home/pi -name "__pycache__" -type d -exec rm -r {} + 2>/dev/null || true

# Restart service
sudo systemctl start wedding-bot
```

## Available Commands

- `help` - Show available commands
- `time` - Show current time
- `btc` - Show Bitcoin price
- `uptime` - Show system uptime