#!/bin/bash
clear
cat << "EOF"
                                       |
                                       |
                                       |
                                     .-'-.
                                    ' ___ '
                          ---------'  .-.  '---------
          _________________________'  '-'  '_________________________
           ''''''-|---|--/    \==][^',_m_,'^][==/    \--|---|-''''''
                         \    /  ||/   H   \||  \    /
                          '--'   OO   O|O   OO   '--'

                          ADS-B Receiver Setup Script
                             By HB9IIU (Daniel S.)
EOF


set -euo pipefail
if [ "$EUID" -ne 0 ]; then
  echo "❌ This script must be run as root (with sudo)." >&2
  echo "   sudo $0" >&2
  exit 1
fi

# ==========================================================
# ── Target user detection ──────────────────────────────────
# ==========================================================
TARGET_USER="${SUDO_USER:-}"
if [ -z "$TARGET_USER" ]; then
  read -r -t 30 -p "Username for Python apps [pi]: " TARGET_USER || true
  TARGET_USER="${TARGET_USER:-pi}"
fi
if ! id "$TARGET_USER" >/dev/null 2>&1; then
  echo "❌ User '$TARGET_USER' does not exist on this system. Create it first." >&2
  exit 1
fi
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
echo "👤 Target user: $TARGET_USER (home: $TARGET_HOME)"

SCRIPT_START_TS=$(date +%s)

# ==========================================================
# ── Receiver defaults (press ENTER to accept) ─────────────
# ==========================================================
DEFAULT_LAT="46.4670012"
DEFAULT_LON="6.8613704"
DEFAULT_BIAS="yes"     # yes/no
DEFAULT_GAIN="auto"    # auto/low/high

# ==========================================================
# ── Paths ──────────────────────────────────────────────────
# ==========================================================
BASE_DIR="${TARGET_HOME}/pythonApps"
VENV_DIR="$BASE_DIR/venv"

WEB_HEX_DIR="/var/www/html/hex"
WEB_JPG_DIR="/var/www/html/jpg"
WEB_JPG_LARGE_DIR="/var/www/html/jpglarge"
WEB_FLAGS_DIR="/var/www/html/flags"
WEB_INDEX="/var/www/html/index.html"

# ==========================================================
# ── Remote URLs ────────────────────────────────────────────
# ==========================================================
REPO_URL="https://github.com/HB9IIU/ESP32-ADSB_Companion.git"
FLAGS_PATH="RPI_ADSB_install_script/SupportingFiles/flags"

RAW_IMAGE_BUILDER="https://raw.githubusercontent.com/HB9IIU/ESP32-ADSB_Companion/main/RPI_ADSB_install_script/SupportingFiles/apps/imageBuilder.py"
RAW_ADSB_STATS="https://raw.githubusercontent.com/HB9IIU/ESP32-ADSB_Companion/main/RPI_ADSB_install_script/SupportingFiles/apps/adsb-stats.py"
RAW_PHOTO_GALLERY="https://raw.githubusercontent.com/HB9IIU/ESP32-ADSB_Companion/main/RPI_ADSB_install_script/SupportingFiles/apps/photoGallery.py"
RAW_WEB_STATUS="https://raw.githubusercontent.com/HB9IIU/ESP32-ADSB_Companion/main/RPI_ADSB_install_script/SupportingFiles/apps/status_web.py"
RAW_ROUTE_FINDER="https://raw.githubusercontent.com/HB9IIU/ESP32-ADSB_Companion/main/RPI_ADSB_install_script/SupportingFiles/apps/routeFinder.py"
RAW_DASHBOARD="https://raw.githubusercontent.com/HB9IIU/ESP32-ADSB_Companion/main/RPI_ADSB_install_script/SupportingFiles/web/index.html"

# ==========================================================
# ── Helper functions ───────────────────────────────────────
# ==========================================================
log()  { echo -e "\n🟦 $*\n"; }
ok()   { echo -e "✅ $*"; }
warn() { echo -e "⚠️  $*"; }

need_cmd() {
  local c="$1"
  if ! command -v "$c" >/dev/null 2>&1; then
    echo "❌ Missing required command: $c"
    echo "👉 Install it with:"
    echo "   sudo apt-get update && sudo apt-get install -y $c"
    exit 1
  fi
}

DOWNLOADER=""
if command -v curl >/dev/null 2>&1; then
  DOWNLOADER="curl"
elif command -v wget >/dev/null 2>&1; then
  DOWNLOADER="wget"
else
  echo "❌ ERROR: Need curl or wget."
  echo "👉 Install one of them:"
  echo "   sudo apt-get update && sudo apt-get install -y curl"
  exit 1
fi

download() {
  local url="$1"
  local dest_file="$2"
  local dest_dir
  dest_dir="$(dirname "$dest_file")"
  echo "📁 Ensuring folder: $dest_dir"
  mkdir -p "$dest_dir"
  echo "⬇️  Downloading: $url"
  echo "➡️  To: $dest_file"
  if [[ "$DOWNLOADER" == "curl" ]]; then
    curl -fsSL -o "$dest_file" "$url"
  else
    wget -qO "$dest_file" "$url"
  fi
  echo "✅ Saved: $(ls -lah "$dest_file")"
}

# ==========================================================
# ── Interactive prompts ────────────────────────────────────
# ==========================================================
log "ADS-B setup will now configure this Raspberry Pi as a receiver with a web map (tar1090)."
echo "🔧 Steps:"
echo "  • System update + base packages"
echo "  • RTL-SDR tools + blacklist DVB driver"
echo "  • Install readsb (RTL-capable build)"
echo "  • Bias-T prompt (default: ${DEFAULT_BIAS})"
echo "  • Gain prompt  (default: ${DEFAULT_GAIN})"
echo "  • Location prompt (default: lat=${DEFAULT_LAT}, lon=${DEFAULT_LON})"
echo "  • Install tar1090 web UI"
echo "  • Python apps + systemd services"
echo "  • Samba shares"
echo

BIAS_ENABLE="$DEFAULT_BIAS"
GAIN_MODE="$DEFAULT_GAIN"
LAT="$DEFAULT_LAT"
LON="$DEFAULT_LON"

if [ -t 0 ]; then
  log "Bias-T (active antenna power)"
  read -r -t 30 -p "Enable Bias-T? [${DEFAULT_BIAS}]: " BIAS_IN || true
  BIAS_IN="${BIAS_IN,,}"
  if [ -n "${BIAS_IN}" ]; then BIAS_ENABLE="$BIAS_IN"; fi

  log "Gain setting"
  echo "Gain options:"
  echo "  auto  = tuner AGC (recommended default)"
  echo "  low   = fixed ~28 dB (urban / strong signals)"
  echo "  high  = fixed ~49 dB (rural / weak signals)"
  read -r -t 30 -p "Select gain [${DEFAULT_GAIN}]: " GAIN_IN || true
  GAIN_IN="${GAIN_IN,,}"
  if [ -n "${GAIN_IN}" ]; then GAIN_MODE="$GAIN_IN"; fi

  log "Receiver location (range rings / display)"
  read -r -t 30 -p "Latitude  [${DEFAULT_LAT}]: " LAT_IN || true
  read -r -t 30 -p "Longitude [${DEFAULT_LON}]: " LON_IN || true
  if [ -n "${LAT_IN}" ]; then LAT="$LAT_IN"; fi
  if [ -n "${LON_IN}" ]; then LON="$LON_IN"; fi
else
  warn "No interactive console detected; using defaults:"
  echo "   Bias-T: ${BIAS_ENABLE}"
  echo "   Gain:   ${GAIN_MODE}"
  echo "   Lat/Lon:${LAT}, ${LON}"
fi

ENABLE_BIASTEE=0
if [ "$BIAS_ENABLE" = "yes" ] || [ "$BIAS_ENABLE" = "y" ]; then
  ENABLE_BIASTEE=1
fi

# ==========================================================
# ── 1) Base OS packages ────────────────────────────────────
# ==========================================================
log "System update + base tools"
apt-get update
apt-get full-upgrade -y
apt-get install -y \
  curl wget ca-certificates gnupg lsb-release \
  usbutils procps python3 git
ok "Base system ready"

# ==========================================================
# ── 2) RTL-SDR + blacklist DVB driver ─────────────────────
# ==========================================================
log "Installing RTL-SDR tools"
apt-get install -y rtl-sdr
ok "rtl-sdr installed"

log "Blacklisting DVB driver (dvb_usb_rtl28xxu)"
BLACKLIST_FILE="/etc/modprobe.d/rtl-sdr-blacklist.conf"
if ! test -f "$BLACKLIST_FILE"; then
  echo 'blacklist dvb_usb_rtl28xxu' | tee "$BLACKLIST_FILE" >/dev/null
  ok "Blacklist written: $BLACKLIST_FILE"
else
  if ! grep -q '^blacklist dvb_usb_rtl28xxu$' "$BLACKLIST_FILE"; then
    echo 'blacklist dvb_usb_rtl28xxu' | tee -a "$BLACKLIST_FILE" >/dev/null
    ok "Blacklist appended: $BLACKLIST_FILE"
  else
    ok "Blacklist already present"
  fi
fi

if lsmod | grep -q '^dvb_usb_rtl28xxu'; then
  warn "DVB driver currently loaded; attempting to unload (no reboot)"
  modprobe -r dvb_usb_rtl28xxu rtl2832 rtl2830 2>/dev/null || true
fi

log "Quick RTL device check (non-fatal)"
if command -v rtl_test >/dev/null 2>&1; then
  rtl_test -t 2>/dev/null | head -n 12 || true
fi

# ==========================================================
# ── 3) readsb (wiedehopf build) ───────────────────────────
# ==========================================================
log "Installing readsb (RTL-SDR capable) via wiedehopf"
systemctl stop readsb 2>/dev/null || true

if dpkg -l | awk '{print $2}' | grep -qx 'readsb'; then
  warn "Removing distro readsb package (may lack RTL-SDR support)"
  apt-get remove -y readsb || true
fi

if command -v readsb >/dev/null 2>&1; then
  ok "readsb already installed; skipping installer"
else
  warn "Installing readsb now..."
  warn "You may see a line like: 'old priority 0, new priority 10' — that's normal (service renice)."
  bash -c "$(wget -q -O - https://raw.githubusercontent.com/wiedehopf/adsb-scripts/master/readsb-install.sh)"
  ok "readsb installed"
fi

echo
echo "⚠️  NOTICE:"
echo "   Ignore the 'set your location' message above."
echo "   Location will be configured correctly by this installer."
echo

log "Configuring readsb (Gain + Location)"
READSB_DEFAULTS="/etc/default/readsb"
touch "$READSB_DEFAULTS"

if ! grep -q '^RECEIVER_OPTIONS=' "$READSB_DEFAULTS"; then
  echo 'RECEIVER_OPTIONS=""' | tee -a "$READSB_DEFAULTS" >/dev/null
fi
if ! grep -q '^DECODER_OPTIONS=' "$READSB_DEFAULTS"; then
  echo 'DECODER_OPTIONS=""' | tee -a "$READSB_DEFAULTS" >/dev/null
fi

# Remove old gain/lat/lon/biastee options (idempotent re-runs)
sed -i 's/--gain[[:space:]]\+[-0-9.]\+//g' "$READSB_DEFAULTS"
sed -i 's/--lat[[:space:]]\+[-0-9.]\+//g' "$READSB_DEFAULTS"
sed -i 's/--lon[[:space:]]\+[-0-9.]\+//g' "$READSB_DEFAULTS"
sed -i 's/--enable-biastee//g' "$READSB_DEFAULTS"

case "$GAIN_MODE" in
  auto)
    ok "Gain: auto (tuner AGC)"
    ;;
  low)
    sed -i 's/^RECEIVER_OPTIONS="\([^"]*\)"/RECEIVER_OPTIONS="\1 --gain 28"/' "$READSB_DEFAULTS"
    ok "Gain: low (~28 dB)"
    ;;
  high)
    sed -i 's/^RECEIVER_OPTIONS="\([^"]*\)"/RECEIVER_OPTIONS="\1 --gain 49"/' "$READSB_DEFAULTS"
    ok "Gain: high (~49 dB)"
    ;;
  *)
    warn "Unknown gain option '$GAIN_MODE' → using auto"
    ;;
esac

sed -i "s/^DECODER_OPTIONS=\"\\([^\"]*\\)\"/DECODER_OPTIONS=\"\\1 --lat ${LAT} --lon ${LON}\"/" "$READSB_DEFAULTS"
ok "Location set: lat=${LAT}, lon=${LON}"

# Clean up extra whitespace
sed -i 's/  */ /g' "$READSB_DEFAULTS"
sed -i 's/RECEIVER_OPTIONS=" /RECEIVER_OPTIONS="/' "$READSB_DEFAULTS"
sed -i 's/DECODER_OPTIONS=" /DECODER_OPTIONS="/' "$READSB_DEFAULTS"

# ==========================================================
# ── 4) Bias-T persistence (systemd oneshot before readsb) ─
# ==========================================================
log "Installing Bias-T boot persistence (systemd) using rtl_biast"

BIAS_SCRIPT="/usr/local/sbin/rtl-biast-apply.sh"
tee "$BIAS_SCRIPT" >/dev/null <<'SH'
#!/bin/bash
set -euo pipefail

MODE="${1:-enable}"

if ! command -v rtl_biast >/dev/null 2>&1; then
  echo "rtl_biast not found; nothing to do."
  exit 0
fi

if [ "$MODE" = "disable" ]; then
  for i in {1..10}; do
    rtl_biast -b 0 && exit 0
    sleep 1
  done
  exit 0
fi

for i in {1..10}; do
  rtl_biast -b 1 && exit 0
  sleep 1
done
exit 0
SH
chmod +x "$BIAS_SCRIPT"

BIAS_UNIT="/etc/systemd/system/rtl-biast.service"
tee "$BIAS_UNIT" >/dev/null <<UNIT
[Unit]
Description=Enable RTL-SDR Bias-T using rtl_biast (before readsb)
Before=readsb.service
After=network.target
Wants=network.target

[Service]
Type=oneshot
ExecStart=${BIAS_SCRIPT} enable
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload

if [ "$ENABLE_BIASTEE" -eq 1 ]; then
  ok "Bias-T requested: installing + enabling rtl-biast.service"
  systemctl enable rtl-biast.service
  systemctl stop readsb 2>/dev/null || true
  systemctl stop tar1090 2>/dev/null || true
  if command -v rtl_biast >/dev/null 2>&1; then
    systemctl start rtl-biast.service || true
    ok "Bias-T applied now + will persist after reboot (rtl-biast.service)"
  else
    warn "rtl_biast not found: service installed, but cannot enable Bias-T until rtl_biast exists."
    warn "Verify with: which rtl_biast"
  fi
else
  warn "Bias-T not requested: disabling rtl-biast.service (if present)"
  systemctl disable rtl-biast.service 2>/dev/null || true
  systemctl stop rtl-biast.service 2>/dev/null || true
  if command -v rtl_biast >/dev/null 2>&1; then
    rtl_biast -b 0 || true
  fi
  ok "Bias-T disabled"
fi

# ==========================================================
# ── 5) Start readsb ───────────────────────────────────────
# ==========================================================
log "Starting readsb"
systemctl enable --now readsb
systemctl restart readsb

log "readsb status (tail)"
systemctl --no-pager --full status readsb | tail -n 25

log "Waiting for /run/readsb/aircraft.json (max 60s)"
FOUND_JSON=0
for i in $(seq 1 60); do
  if [ -s /run/readsb/aircraft.json ]; then
    FOUND_JSON=1
    break
  fi
  sleep 1
done
if [ "$FOUND_JSON" -eq 1 ]; then
  ok "Found /run/readsb/aircraft.json"
else
  warn "Still no aircraft.json after 60s (may be low traffic, antenna, power, or gain/location issues)"
fi

# ==========================================================
# ── 6) tar1090 web UI ─────────────────────────────────────
# ==========================================================
log "Installing tar1090 (web interface) via wiedehopf"
systemctl stop tar1090 2>/dev/null || true

if [ -f /usr/local/share/tar1090/tar1090.sh ]; then
  ok "tar1090 already installed; skipping installer"
else
  bash -c "$(wget -q -O - https://raw.githubusercontent.com/wiedehopf/adsb-scripts/master/tar1090-install.sh)"
  ok "tar1090 installed"
fi

log "Starting tar1090"
systemctl enable --now tar1090
systemctl restart tar1090

log "Removing lighttpd root alias (tar1090 steals / otherwise)"
OTHERPORT_CONF="/etc/lighttpd/conf-available/95-tar1090-otherport.conf"
if [ -f "$OTHERPORT_CONF" ]; then
  sed -i '/"\/\" => "\/usr\/local\/share\/tar1090\/html\//d' "$OTHERPORT_CONF"
  ok "Root alias removed from $OTHERPORT_CONF"
else
  ok "95-tar1090-otherport.conf not present; nothing to patch"
fi
systemctl reload lighttpd

log "Installing station dashboard: / -> index.html"
mkdir -p /var/www/html
download "$RAW_DASHBOARD" "$WEB_INDEX"
ok "Dashboard installed: http://$(hostname -I | awk '{print $1}')/"

log "tar1090 status (tail)"
systemctl --no-pager --full status tar1090 | tail -n 20

# ==========================================================
# ── 7) Python environment ─────────────────────────────────
# ==========================================================
log "Setting up Python virtual environment"

echo "🔎 Checking required commands..."
need_cmd python3
need_cmd git
need_cmd systemctl
need_cmd sed
need_cmd df
ok "Requirements OK"

if [[ -d "$BASE_DIR" ]]; then
  echo "🧹 Removing existing directory: $BASE_DIR"
  rm -rf "$BASE_DIR"
fi
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "$BASE_DIR"

echo "🐍 Creating virtual environment (as user ${TARGET_USER})..."
sudo -u "${TARGET_USER}" -H python3 -m venv "$VENV_DIR"

echo "⬆️  Upgrading pip (as user ${TARGET_USER})..."
sudo -u "${TARGET_USER}" -H "$VENV_DIR/bin/python3" -m pip install --upgrade pip

echo "📦 Installing pinned Python packages (as user ${TARGET_USER})..."
sudo -u "${TARGET_USER}" -H "$VENV_DIR/bin/python3" -m pip install \
  airportsdata==20260208 \
  blinker==1.9.0 \
  cairocffi==1.7.1 \
  CairoSVG==2.8.2 \
  certifi==2026.1.4 \
  cffi==2.0.0 \
  charset-normalizer==3.4.4 \
  click==8.3.1 \
  cssselect2==0.8.0 \
  defusedxml==0.7.1 \
  Flask==3.1.2 \
  flask-cors==6.0.2 \
  freetype-py==2.5.1 \
  idna==3.11 \
  itsdangerous==2.2.0 \
  Jinja2==3.1.6 \
  MarkupSafe==3.0.3 \
  packaging==26.0 \
  pillow==12.1.0 \
  pycountry==24.6.1 \
  pycparser==3.0 \
  requests==2.32.5 \
  setuptools==82.0.0 \
  tinycss2==1.5.1 \
  urllib3==2.6.3 \
  webencodings==0.5.1 \
  Werkzeug==3.1.5 \
  wheel==0.46.3
ok "Python environment ready: $VENV_DIR"

# ==========================================================
# ── 8) Download Python apps ───────────────────────────────
# ==========================================================
log "Downloading app files"
download "$RAW_IMAGE_BUILDER"  "$BASE_DIR/imageBuilder.py"
download "$RAW_ADSB_STATS"    "$BASE_DIR/adsb-stats.py"
download "$RAW_PHOTO_GALLERY" "$BASE_DIR/photoGallery.py"
download "$RAW_WEB_STATUS"    "$BASE_DIR/status_web.py"
download "$RAW_ROUTE_FINDER"  "$BASE_DIR/routeFinder.py"

# ==========================================================
# ── 9) Flags (sparse-checkout) ────────────────────────────
# ==========================================================
log "Installing flags into: $WEB_FLAGS_DIR"
TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$WEB_HEX_DIR" "$WEB_JPG_DIR" "$WEB_JPG_LARGE_DIR" "$WEB_FLAGS_DIR"

echo "🔽 Cloning repo (sparse-checkout, flags only)..."
git clone --filter=blob:none --no-checkout "$REPO_URL" "$TMP/repo" >/dev/null
cd "$TMP/repo"
git sparse-checkout init --no-cone >/dev/null
git sparse-checkout set "$FLAGS_PATH" >/dev/null
git checkout main >/dev/null

echo "📤 Copying flags..."
cp "$TMP/repo/$FLAGS_PATH"/*.jpg "$WEB_FLAGS_DIR"/
ok "Flags installed: $(ls "$WEB_FLAGS_DIR" | wc -l) files"

# ==========================================================
# ── 10) Ownership / permissions ───────────────────────────
# ==========================================================
log "Fixing ownership and permissions"
chown -R "${TARGET_USER}:${TARGET_USER}" "$BASE_DIR"

chown "${TARGET_USER}:www-data" "$WEB_INDEX"
chmod 0644 "$WEB_INDEX"

for web_asset_dir in "$WEB_HEX_DIR" "$WEB_JPG_DIR" "$WEB_JPG_LARGE_DIR"; do
  chown -R "${TARGET_USER}:www-data" "$web_asset_dir"
  find "$web_asset_dir" -type d -exec chmod 0755 {} \;
  find "$web_asset_dir" -type f -exec chmod 0644 {} \;
done
ok "Ownership set (user: ${TARGET_USER})"

# ==========================================================
# ── 11) systemd units ─────────────────────────────────────
# ==========================================================
log "Installing systemd units"

cat > /etc/systemd/system/adsb-stats.service << EOF
[Unit]
Description=ADS-B Stats HTML generator
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${BASE_DIR}
RuntimeDirectory=adsb-stats
RuntimeDirectoryMode=0755
ExecStart=${VENV_DIR}/bin/python3 ${BASE_DIR}/adsb-stats.py
EOF

cat > /etc/systemd/system/adsb-stats.timer << 'EOF'
[Unit]
Description=Run ADS-B stats every 5 seconds

[Timer]
OnBootSec=20
OnUnitActiveSec=5
AccuracySec=1s

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/image-builder.service << EOF
[Unit]
Description=Aircraft Image Builder
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${BASE_DIR}
ExecStart=${VENV_DIR}/bin/python3 ${BASE_DIR}/imageBuilder.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/pi-status-web.service << EOF
[Unit]
Description=Pi Status Web (Flask)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${BASE_DIR}
ExecStart=${VENV_DIR}/bin/python3 ${BASE_DIR}/status_web.py
Restart=always
RestartSec=3
Environment=STATUS_HOST=0.0.0.0
Environment=STATUS_PORT=8080

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/route-finder.service << EOF
[Unit]
Description=Route Finder Flask server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${BASE_DIR}
ExecStart=${VENV_DIR}/bin/python3 ${BASE_DIR}/routeFinder.py
Restart=always
RestartSec=3
Environment=HOST=0.0.0.0
Environment=PORT=6969

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/photo-gallery.service << EOF
[Unit]
Description=ADS-B Photo Gallery generator
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${BASE_DIR}
ExecStart=${VENV_DIR}/bin/python3 ${BASE_DIR}/photoGallery.py
EOF

cat > /etc/systemd/system/photo-gallery.timer << 'EOF'
[Unit]
Description=Run Photo Gallery generator every 5 minutes

[Timer]
OnBootSec=30
OnUnitActiveSec=5min
AccuracySec=1s

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload

_start_unit() {
  local unit="$1"
  systemctl enable "$unit" && systemctl restart "$unit"
  local state
  state="$(systemctl is-active "$unit" 2>/dev/null || true)"
  if [ "$state" = "active" ] || [ "$state" = "activating" ]; then
    ok "$unit → $state"
  else
    warn "$unit → $state"
    systemctl --no-pager status "$unit" 2>/dev/null | tail -5 || true
  fi
}

_start_unit adsb-stats.timer
_start_unit image-builder.service
_start_unit pi-status-web.service
_start_unit route-finder.service
systemctl enable --now photo-gallery.timer && systemctl restart photo-gallery.timer
_start_unit photo-gallery.timer

# ==========================================================
# ── 12) Samba (guest RW, no password) ─────────────────────
# ==========================================================
log "Installing Samba (guest RW, no password)"
apt-get update
apt-get install -y samba samba-common-bin

if [[ ! -f /etc/samba/smb.conf.bak ]]; then
  cp /etc/samba/smb.conf /etc/samba/smb.conf.bak
fi

if ! grep -q "^ *map to guest *= *Bad User" /etc/samba/smb.conf; then
  sed -i '0,/^\[global\]/{s/^\[global\]/[global]\n   map to guest = Bad User/}' /etc/samba/smb.conf
fi

add_share_if_missing() {
  local name="$1"
  local block="$2"
  if ! grep -q "^\[$name\]" /etc/samba/smb.conf; then
    echo "➕ Adding share: [$name]"
    printf "\n%s\n" "$block" >> /etc/samba/smb.conf
  else
    echo "ℹ️  Share [$name] already exists (skipping)."
  fi
}

add_share_if_missing "pi-home" "[pi-home]
  comment = ${TARGET_HOME} (GUEST RW)
  path = ${TARGET_HOME}
  browseable = yes
  read only = no
  guest ok = yes
  force user = ${TARGET_USER}
  force group = ${TARGET_USER}
  create mask = 0644
  directory mask = 0755
"

add_share_if_missing "www-html" "[www-html]
  comment = /var/www/html (GUEST RW)
  path = /var/www/html
  browseable = yes
  read only = no
  guest ok = yes
  force user = ${TARGET_USER}
  force group = www-data
  create mask = 0644
  directory mask = 0755
"

chown -R "${TARGET_USER}:www-data" /var/www/html
find /var/www/html -type d -exec chmod 0755 {} \;
find /var/www/html -type f -exec chmod 0644 {} \;

echo "🧪 Validating Samba config..."
testparm -s >/dev/null

systemctl enable smbd nmbd
systemctl restart smbd nmbd
ok "Samba ready"

# ==========================================================
# ── DONE ──────────────────────────────────────────────────
# ==========================================================
IP="$(hostname -I | awk '{print $1}')"
DASH_URL="http://${IP}/"
TAR_URL="http://${IP}/tar1090/"
AIRCRAFT_URL="http://${IP}/tar1090/data/aircraft.json"
STATUS_URL="http://${IP}:8080/"

log "ALL DONE"
echo "🏠  Dashboard:       ${DASH_URL}"
echo "🗺️  Live Map:        ${TAR_URL}"
echo "📡  aircraft.json:   ${AIRCRAFT_URL}"
echo "📊  ADS-B Stats:     http://${IP}/stats.html"
echo "🖼️  Photo Gallery:   http://${IP}/gallery.html"
echo "🌐  Status page:     ${STATUS_URL}"
echo "✈️   Route Finder:    http://${IP}:6969/"
echo
echo "➡️  Use: ${AIRCRAFT_URL} in the config file for your ESP32 TFT monitor"
echo
echo "📁 SMB shares:"
echo "   Windows:  \\\\${IP}\\pi-home   and   \\\\${IP}\\www-html"
echo "   macOS:    smb://${IP}/pi-home  and  smb://${IP}/www-html"
echo
if [ "$ENABLE_BIASTEE" -eq 1 ]; then
  echo "🔌 Bias-T: ENABLED (rtl-biast.service runs before readsb on every boot)"
  echo "   Check with: systemctl status rtl-biast.service"
else
  echo "🔌 Bias-T: DISABLED"
fi
echo
echo "🔎 Service checks:"
echo "   systemctl status image-builder.service --no-pager"
echo "   systemctl status adsb-stats.timer --no-pager"
echo "   systemctl status pi-status-web.service --no-pager"
echo "   systemctl status route-finder.service --no-pager"
echo "   systemctl status photo-gallery.timer --no-pager"
echo
echo "🪵 Logs:"
echo "   journalctl -u image-builder.service -f"
echo "   journalctl -u pi-status-web.service -f"
echo "   journalctl -u route-finder.service -f"
echo

SCRIPT_END_TS=$(date +%s)
SCRIPT_ELAPSED=$((SCRIPT_END_TS - SCRIPT_START_TS))
SCRIPT_MM=$((SCRIPT_ELAPSED / 60))
SCRIPT_SS=$((SCRIPT_ELAPSED % 60))
printf "⏱️  Total time: %02d:%02d\n" "$SCRIPT_MM" "$SCRIPT_SS"
echo "73 de HB9IIU"
echo

warn "Rebooting in 5 seconds..."
sleep 5
reboot
