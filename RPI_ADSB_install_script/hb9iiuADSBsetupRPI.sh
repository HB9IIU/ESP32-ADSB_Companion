#!/bin/bash
set -euo pipefail

# 🛰️ ADS-B Receiver Setup Script (Raspberry Pi OS Lite / Debian)
# Author: Daniel S. (HB9IIU)
# Created: 2026-02-07
#
# What this script does:
#   1) ✅ Updates the OS and installs base tools
#   2) ✅ Installs RTL-SDR tools and blacklists the DVB kernel driver
#   3) ✅ Installs readsb (wiedehopf build with RTL-SDR support)
#   4) ✅ Optionally enables Bias-T (active antenna power) [default: YES]
#   5) ✅ Sets gain mode: auto / low / high [default: auto]
#   6) ✅ Sets receiver location (lat/lon) for range rings [defaults provided]
#   7) ✅ Installs tar1090 web UI
#   8) ✅ Prints the URLs you need (tar1090 + aircraft.json for ESP32)
#
# Run:
#   chmod +x setup-adsb.sh
#   ./setup-adsb.sh

log()  { echo -e "\n🟦 $*\n"; }
ok()   { echo -e "✅ $*"; }
warn() { echo -e "⚠️  $*"; }

# ---------- Defaults (press ENTER to accept) ----------
DEFAULT_LAT="46.4670012"
DEFAULT_LON="6.8613704"
DEFAULT_BIAS="yes"     # yes/no
DEFAULT_GAIN="auto"    # auto/low/high

# ---------- Intro / plan ----------
log "ADS-B setup will now configure this Raspberry Pi as a receiver with a web map (tar1090)."
echo "🔧 Steps:"
echo "  • System update + base packages"
echo "  • RTL-SDR tools + blacklist DVB driver"
echo "  • Install readsb (RTL-capable build)"
echo "  • Bias-T prompt (default: ${DEFAULT_BIAS})"
echo "  • Gain prompt  (default: ${DEFAULT_GAIN})"
echo "  • Location prompt (default: lat=${DEFAULT_LAT}, lon=${DEFAULT_LON})"
echo "  • Install tar1090 web UI"
echo

# ---------- Collect user inputs (interactive only) ----------
BIAS_ENABLE="$DEFAULT_BIAS"
GAIN_MODE="$DEFAULT_GAIN"
LAT="$DEFAULT_LAT"
LON="$DEFAULT_LON"

if [ -t 0 ]; then
  # Bias-T
  log "Bias-T (active antenna power)"
  read -r -p "Enable Bias-T? [${DEFAULT_BIAS}]: " BIAS_IN || true
  BIAS_IN="${BIAS_IN,,}"
  if [ -n "${BIAS_IN}" ]; then BIAS_ENABLE="$BIAS_IN"; fi

  # Gain
  log "Gain setting"
  echo "Gain options:"
  echo "  auto  = tuner AGC (recommended default)"
  echo "  low   = fixed ~28 dB (urban / strong signals)"
  echo "  high  = fixed ~49 dB (rural / weak signals)"
  read -r -p "Select gain [${DEFAULT_GAIN}]: " GAIN_IN || true
  GAIN_IN="${GAIN_IN,,}"
  if [ -n "${GAIN_IN}" ]; then GAIN_MODE="$GAIN_IN"; fi

  # Location
  log "Receiver location (range rings / display)"
  read -r -p "Latitude  [${DEFAULT_LAT}]: " LAT_IN || true
  read -r -p "Longitude [${DEFAULT_LON}]: " LON_IN || true
  if [ -n "${LAT_IN}" ]; then LAT="$LAT_IN"; fi
  if [ -n "${LON_IN}" ]; then LON="$LON_IN"; fi
else
  warn "No interactive console detected; using defaults:"
  echo "   Bias-T: ${BIAS_ENABLE}"
  echo "   Gain:   ${GAIN_MODE}"
  echo "   Lat/Lon:${LAT}, ${LON}"
fi

# Normalize Bias input
ENABLE_BIASTEE=0
if [ "$BIAS_ENABLE" = "yes" ] || [ "$BIAS_ENABLE" = "y" ]; then
  ENABLE_BIASTEE=1
fi

# ---------- 1) Base OS packages ----------
log "System update + base tools"
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y \
  curl wget ca-certificates gnupg lsb-release \
  usbutils procps
ok "Base system ready"

# ---------- 2) RTL-SDR + blacklist DVB driver ----------
log "Installing RTL-SDR tools"
sudo apt install -y rtl-sdr
ok "rtl-sdr installed"

log "Blacklisting DVB driver (dvb_usb_rtl28xxu)"
BLACKLIST_FILE="/etc/modprobe.d/rtl-sdr-blacklist.conf"
if ! sudo test -f "$BLACKLIST_FILE"; then
  echo 'blacklist dvb_usb_rtl28xxu' | sudo tee "$BLACKLIST_FILE" >/dev/null
  ok "Blacklist written: $BLACKLIST_FILE"
else
  if ! sudo grep -q '^blacklist dvb_usb_rtl28xxu$' "$BLACKLIST_FILE"; then
    echo 'blacklist dvb_usb_rtl28xxu' | sudo tee -a "$BLACKLIST_FILE" >/dev/null
    ok "Blacklist appended: $BLACKLIST_FILE"
  else
    ok "Blacklist already present"
  fi
fi

# Try to unload without forcing reboot
if lsmod | grep -q '^dvb_usb_rtl28xxu'; then
  warn "DVB driver currently loaded; attempting to unload (no reboot)"
  sudo modprobe -r dvb_usb_rtl28xxu rtl2832 rtl2830 2>/dev/null || true
fi

log "Quick RTL device check (non-fatal)"
if command -v rtl_test >/dev/null 2>&1; then
  rtl_test -t 2>/dev/null | head -n 12 || true
fi

# ---------- 3) readsb (wiedehopf build with RTL-SDR support) ----------
log "Installing readsb (RTL-SDR capable) via wiedehopf"
sudo systemctl stop readsb 2>/dev/null || true

# Remove distro readsb if present (often the wrong build)
if dpkg -l | awk '{print $2}' | grep -qx 'readsb'; then
  warn "Removing distro readsb package (may lack RTL-SDR support)"
  sudo apt remove -y readsb || true
fi

if systemctl list-unit-files | grep -q '^readsb\.service'; then
  ok "readsb already installed; skipping installer"
else
  sudo bash -c "$(wget -q -O - https://raw.githubusercontent.com/wiedehopf/adsb-scripts/master/readsb-install.sh)"
  ok "readsb installed"
fi

# ---------- Configure readsb options: Bias-T + Gain + Location ----------
log "Configuring readsb (Bias-T + Gain + Location)"
READSB_DEFAULTS="/etc/default/readsb"
sudo touch "$READSB_DEFAULTS"

# Ensure options variables exist
if ! sudo grep -q '^RECEIVER_OPTIONS=' "$READSB_DEFAULTS"; then
  echo 'RECEIVER_OPTIONS=""' | sudo tee -a "$READSB_DEFAULTS" >/dev/null
fi
if ! sudo grep -q '^DECODER_OPTIONS=' "$READSB_DEFAULTS"; then
  echo 'DECODER_OPTIONS=""' | sudo tee -a "$READSB_DEFAULTS" >/dev/null
fi

# Remove old bias/gain/lat/lon options to keep it clean + re-runnable
sudo sed -i 's/--enable-biastee//g' "$READSB_DEFAULTS"
sudo sed -i 's/--gain[[:space:]]\+[-0-9.]\+//g' "$READSB_DEFAULTS"
sudo sed -i 's/--lat[[:space:]]\+[-0-9.]\+//g' "$READSB_DEFAULTS"
sudo sed -i 's/--lon[[:space:]]\+[-0-9.]\+//g' "$READSB_DEFAULTS"

# Bias-T
if [ "$ENABLE_BIASTEE" -eq 1 ]; then
  sudo sed -i 's/^RECEIVER_OPTIONS="\([^"]*\)"/RECEIVER_OPTIONS="\1 --enable-biastee"/' "$READSB_DEFAULTS"
  ok "Bias-T ENABLED"
else
  warn "Bias-T DISABLED"
fi

# Gain
case "$GAIN_MODE" in
  auto)
    ok "Gain: auto (tuner AGC)"
    ;;
  low)
    sudo sed -i 's/^RECEIVER_OPTIONS="\([^"]*\)"/RECEIVER_OPTIONS="\1 --gain 28"/' "$READSB_DEFAULTS"
    ok "Gain: low (~28 dB)"
    ;;
  high)
    sudo sed -i 's/^RECEIVER_OPTIONS="\([^"]*\)"/RECEIVER_OPTIONS="\1 --gain 49"/' "$READSB_DEFAULTS"
    ok "Gain: high (~49 dB)"
    ;;
  *)
    warn "Unknown gain option '$GAIN_MODE' → using auto"
    ;;
esac

# Location
sudo sed -i "s/^DECODER_OPTIONS=\"\\([^\"]*\\)\"/DECODER_OPTIONS=\"\\1 --lat ${LAT} --lon ${LON}\"/" "$READSB_DEFAULTS"
ok "Location set: lat=${LAT}, lon=${LON}"

# Clean up spacing
sudo sed -i 's/  */ /g' "$READSB_DEFAULTS"
sudo sed -i 's/RECEIVER_OPTIONS=" /RECEIVER_OPTIONS="/' "$READSB_DEFAULTS"
sudo sed -i 's/DECODER_OPTIONS=" /DECODER_OPTIONS="/' "$READSB_DEFAULTS"

# Start/enable readsb
log "Starting readsb"
sudo systemctl enable --now readsb
sudo systemctl restart readsb

log "readsb status (tail)"
sudo systemctl --no-pager --full status readsb | tail -n 25

# Wait for JSON output
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
  warn "Still no aircraft.json after 60s (may be low traffic, antenna, or gain/location issues)"
fi

# ---------- 4) tar1090 web UI ----------
log "Installing tar1090 (web interface) via wiedehopf"
sudo systemctl stop tar1090 2>/dev/null || true

if systemctl list-unit-files | grep -q '^tar1090\.service'; then
  ok "tar1090 already installed; skipping installer"
else
  sudo bash -c "$(wget -q -O - https://raw.githubusercontent.com/wiedehopf/adsb-scripts/master/tar1090-install.sh)"
  ok "tar1090 installed"
fi

log "Starting tar1090"
sudo systemctl enable --now tar1090

log "tar1090 status (tail)"
sudo systemctl --no-pager --full status tar1090 | tail -n 20

# ---------- Final output ----------
IP="$(hostname -I | awk '{print $1}')"
TAR_URL="http://${IP}/tar1090/"
AIRCRAFT_URL="http://${IP}/tar1090/data/aircraft.json"

log "DONE 🎉"
echo "🗺️  Web UI: ${TAR_URL}"
echo "📡  aircraft.json: ${AIRCRAFT_URL}"
echo
echo "➡️  Use: ${AIRCRAFT_URL} in the config file for your ESP32 TFT monitor"
echo
echo "73 de HB9IIU"

# Suggest reboot only if DVB module is still loaded
if lsmod | grep -q '^dvb_usb_rtl28xxu'; then
  echo
  warn "dvb_usb_rtl28xxu is still loaded. Reboot recommended to fully unload it:"
  echo "   sudo reboot"
fi

# Optional: show readsb invocation line for verification
echo
log "readsb invocation (verification)"
sudo journalctl -u readsb -n 120 --no-pager 2>/dev/null | grep -E 'invoked by:' || true
