#!/usr/bin/env bash
set -euo pipefail

# --- must run as root ---
if [ "$EUID" -ne 0 ]; then
  echo "❌ This script must be run as root (use sudo)." >&2
  echo "   sudo $0" >&2
  exit 1
fi

###############################################################################
# HB9IIU routeFinder installer + systemd service creator + PHP proxy setup
#
# What this script does:
#   1) Creates /home/pi/pythonApps if missing
#   2) Downloads routeFinder.py from your GitHub repo (RAW URL, not the "blob" page)
#   3) Sets ownership to pi:pi and makes the script executable
#   4) Creates a systemd service (route-finder.service) that runs the app using:
#        /home/pi/pythonApps/venv/bin/python3
#      and restarts automatically if it crashes
#   5) Enables and starts the service
#   6) Installs lighttpd and PHP, enables FastCGI modules, restarts lighttpd
#   7) Creates /var/www/html/route.php (PHP proxy for Flask API)
#      with correct permissions and ownership
#
# Run with:
#   sudo ./activateRouteFinder.sh
###############################################################################

# ---------------- CONFIG ----------------
TARGET_DIR="/home/pi/pythonApps"
TARGET_FILE="routeFinder.py"
RAW_URL="https://raw.githubusercontent.com/HB9IIU/ESP32-ADSB_Companion/main/pythonTools/ForDevelopmentOnly/extra/routeFinder.py"
VENV_PY="/home/pi/pythonApps/venv/bin/python3"
SERVICE_NAME="route-finder"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
# ----------------------------------------

echo "📁 Ensuring target directory exists: $TARGET_DIR"
mkdir -p "$TARGET_DIR"

echo "⬇️  Downloading $TARGET_FILE..."
wget -O "$TARGET_DIR/$TARGET_FILE" "$RAW_URL"

echo "👤 Setting ownership to pi:pi..."
chown pi:pi "$TARGET_DIR/$TARGET_FILE"

echo "🔧 Making file executable..."
chmod +x "$TARGET_DIR/$TARGET_FILE"

echo "🧩 Creating systemd service: ${SERVICE_NAME}.service"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=HB9IIU Route Finder (Python app)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=${TARGET_DIR}
ExecStart=${VENV_PY} ${TARGET_DIR}/${TARGET_FILE}
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "🔄 Reloading systemd..."
systemctl daemon-reload

echo "✅ Enabling + starting service..."
systemctl enable --now "${SERVICE_NAME}.service"

echo "📋 Service status:"
systemctl --no-pager -l status "${SERVICE_NAME}.service"

echo


# --- Create /var/www/html/route.php ---
echo "🧩 Creating /var/www/html/route.php (PHP proxy for Flask API)..."
tee /var/www/html/route.php > /dev/null <<'EOF'
<?php
$icao = $_GET['icao'];
$url = "http://localhost:6969/api/flight/" . urlencode($icao);
$response = file_get_contents($url);
header('Content-Type: application/json');
echo $response;
?>
EOF
chown www-data:www-data /var/www/html/route.php
chmod 644 /var/www/html/route.php

echo
# --- Install lighttpd and PHP, enable modules, restart server ---
echo "🧩 Installing lighttpd and PHP..."
apt-get update
apt-get install -y php-cgi lighttpd

lighty-enable-mod fastcgi
lighty-enable-mod fastcgi-php
systemctl restart lighttpd
echo
# --- Final output ---
echo "Done."
echo "Useful commands:"
echo "  sudo systemctl restart ${SERVICE_NAME}.service"
echo "  sudo journalctl -u ${SERVICE_NAME}.service -n 100 --no-pager"
echo "  sudo systemctl stop ${SERVICE_NAME}.service"
