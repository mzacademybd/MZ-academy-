#!/bin/bash
# Make the Telegram bot start automatically on your Mac — after restarts, logins
# and crashes. Run once from this folder:   ./install_mac_service.sh
# Remove later with:                          ./install_mac_service.sh --remove
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
LABEL="com.mzacademy.assistant-bot"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" = "--remove" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Removed. The bot will no longer start automatically."
  exit 0
fi

PY="$(command -v python3)"
[ -n "$PY" ] || { echo "python3 not found. Install Python first (README step 1)."; exit 1; }
[ -f .env ] || { echo "Missing .env file. Copy .env.example to .env and fill it in."; exit 1; }
"$PY" -c "import anthropic, requests" || { echo "Run: $PY -m pip install -r requirements.txt"; exit 1; }
[ -f assistant_ids.json ] || { echo "Run setup first: $PY setup_assistant.py"; exit 1; }

mkdir -p "$HOME/Library/LaunchAgents" logs
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/caffeinate</string><string>-is</string>
    <string>$PY</string><string>$DIR/telegram_bot.py</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>15</integer>
  <key>StandardOutPath</key><string>$DIR/logs/bot.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/bot.log</string>
</dict>
</plist>
PLISTEOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "✅ Bot installed and running. It restarts by itself after crashes and Mac restarts."
echo "   Log:  $DIR/logs/bot.log"
