#!/usr/bin/env python3
"""
ADS-B Receiver Stats (readsb aircraft.json snapshot -> state + HTML)

What this script does (high level)
----------------------------------
- Each run reads ONE snapshot file: /run/readsb/aircraft.json
- Updates counters in a state JSON
- Writes a simple HTML page (auto-refresh in the browser)

What this script aims for
-------------------------
- Keep SD writes low (state in /run, HTML throttled, periodic disk backup)
- Show a small set of *interesting facts* that are easy to understand

Definitions
-----------
- Unique aircraft: unique ICAO hex strings ("hex")
- Flights/callsigns: "flight" field (trimmed); often missing
- Visit: counts the same aircraft again if it disappears for >= PASS_GAP_SECONDS

2) SD-card friendly:
   - Live state is stored in /run (tmpfs/RAM): frequent writes do NOT hit the SD card.
   - HTML is written to /var/www/html (on disk), but THROTTLED to once every 15s.

3) History survives reboot:
   - Every BACKUP_INTERVAL_SECONDS (10 minutes) we write a backup to:
       /var/lib/adsb-stats/state-backup.json
   - On boot (when /run state is gone), we restore from that backup.

How to run it
-------------
- Best: systemd timer every 5 seconds (you already have this).
- Script is designed to run fast and exit (no "while true" inside).

Resetting history
-----------------
- To wipe all captured history (today + all-time), run:
    adsb-stats.py --reset
- Or manually delete:
    /run/adsb-stats/* and /var/lib/adsb-stats/state-backup.json

"""

import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------
# INPUTS (read-only sources)
# --------------------------------------------------------------------
AIRCRAFT_JSON = Path("/run/readsb/aircraft.json")     # readsb snapshot (usually tmpfs)
READSB_DEFAULTS = Path("/etc/default/readsb")         # for --lat / --lon extraction

# --------------------------------------------------------------------
# OUTPUTS (state + html)
# --------------------------------------------------------------------
# Live state in RAM (tmpfs): safe to write often
STATE_DIR  = Path("/run/adsb-stats")
STATE_FILE = STATE_DIR / "state.json"

# Small meta file also in RAM (for HTML throttling)
HTML_META_FILE = STATE_DIR / "html_meta.json"

# HTML output: typical web root (disk) - we throttle writes to reduce SD wear
OUT_HTML = Path("/var/www/html/stats.html")

# Backup state on disk (survives reboot)
BACKUP_DIR  = Path("/var/lib/adsb-stats")
BACKUP_FILE = BACKUP_DIR / "state-backup.json"

# --------------------------------------------------------------------
# TUNABLES
# --------------------------------------------------------------------
# Browser refresh interval (HTML <meta refresh>)
HTML_META_REFRESH_SECONDS = 15

# How often we actually rewrite stats.html on disk
HTML_WRITE_INTERVAL = 15

# "Pass" definition: same aircraft counts again if not seen for this long
PASS_GAP_SECONDS = 30 * 60   # 30 minutes

# Backup interval (your choice): 10 minutes
BACKUP_INTERVAL_SECONDS = 10 * 60

# Optional pruning for last_seen_ts (prevents unbounded growth if you run for months)
# Keep last_seen entries from the last 14 days; older ones are removed.
PRUNE_LAST_SEEN_OLDER_THAN_SECONDS = 14 * 86400

# --------------------------------------------------------------------
# MATH / PARSING UTILITIES
# --------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two points (km)."""
    R = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = math.sin(dlat/2)**2 + math.cos(lat1*p)*math.cos(lat2*p)*math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def read_receiver_latlon() -> Tuple[Optional[float], Optional[float]]:
    """
    Extract --lat and --lon from /etc/default/readsb (DECODER_OPTIONS).
    Returns (None, None) if not found.
    """
    try:
        txt = READSB_DEFAULTS.read_text(errors="ignore")
    except Exception:
        return None, None

    mlat = re.search(r"--lat\s+([-0-9.]+)", txt)
    mlon = re.search(r"--lon\s+([-0-9.]+)", txt)
    if not (mlat and mlon):
        return None, None

    try:
        return float(mlat.group(1)), float(mlon.group(1))
    except Exception:
        return None, None

def safe_callsign(a: Dict[str, Any]) -> Optional[str]:
    """
    readsb often uses key "flight" for callsign and pads with spaces.
    We strip and return None if empty.
    """
    cs = a.get("flight") or a.get("call") or ""
    cs = cs.strip()
    return cs if cs else None

def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def _to_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(float(x))
    except Exception:
        return None

def alt_ft(a: Dict[str, Any]) -> Optional[int]:
    """Best-effort altitude in feet from readsb fields."""
    # readsb commonly provides alt_baro (ft) and sometimes alt_geom.
    for key in ("alt_baro", "alt_geom", "altitude"):
        v = a.get(key)
        if isinstance(v, str):
            # E.g. "ground" or "".
            continue
        i = _to_int(v)
        if i is not None:
            return i
    return None

def gs_kt(a: Dict[str, Any]) -> Optional[float]:
    """Best-effort ground speed in knots from readsb fields."""
    for key in ("gs", "speed", "tas"):
        v = _to_float(a.get(key))
        if v is not None:
            return v
    return None

def fmt_age(seconds: int) -> str:
    """Format seconds as '1d 02h 03m 04s', '17m 24s', etc."""
    if seconds < 0:
        seconds = 0
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    mins = seconds // 60
    secs = seconds % 60
    if days > 0:
        return f"{days}d {hours:02d}h {mins:02d}m {secs:02d}s"
    if hours > 0:
        return f"{hours}h {mins:02d}m {secs:02d}s"
    if mins > 0:
        return f"{mins}m {secs:02d}s"
    return f"{secs}s"

def today_key_local(now_ts: int) -> str:
    """Local date key used for 'today' reset logic."""
    return time.strftime("%Y-%m-%d", time.localtime(now_ts))

# --------------------------------------------------------------------
# ATOMIC JSON WRITE HELPER
# --------------------------------------------------------------------

def atomic_write_json(path: Path, obj: Dict[str, Any]) -> None:
    """
    Write JSON atomically: write to temp then rename.
    This avoids partially-written files if power is lost mid-write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True))
    tmp.replace(path)

# --------------------------------------------------------------------
# STATE DEFAULT / LOAD / SAVE
# --------------------------------------------------------------------

def default_state(now_ts: int) -> Dict[str, Any]:
    """State structure with all counters initialized."""
    tk = today_key_local(now_ts)
    return {
        # History start time (for "Age" on HTML)
        "created_ts": now_ts,

        # Optional metric: how many aircraft entries we processed across runs (not unique)
        "total_seen_updates": 0,

        # Unique since history start
        "seen_hex": {},          # hex -> first_seen_ts
        "seen_calls": {},        # callsign -> first_seen_ts

        # Daily reset fields
        "today_key": tk,
        "today_seen_hex": {},    # hex -> first_seen_ts_today
        "today_seen_calls": {},  # callsign -> first_seen_ts_today

        # Pass logic
        "last_seen_ts": {},      # hex -> last_seen_ts
        "passes_total": 0,       # passes since created_ts
        "passes_today": 0,       # passes since local midnight

        # Peak traffic (simple but fun)
        "peak_aircraft_in_view": 0,        # maximum aircraft_total in any snapshot
        "today_peak_aircraft_in_view": 0,  # same, reset daily

        # Distance stats (since history start)
        "max_distance_km": None,
        "max_distance_info": None,
        "min_distance_km": None,
        "min_distance_info": None,

        # Altitude stats
        "max_alt_ft": None,
        "max_alt_info": None,
        "today_max_alt_ft": None,
        "today_max_alt_info": None,

        # Speed stats
        "max_gs_kt": None,
        "max_gs_info": None,
        "today_max_gs_kt": None,
        "today_max_gs_info": None,

        # Backup bookkeeping
        # This helps us decide when to write BACKUP_FILE next.
        "last_backup_ts": 0,
    }

def load_backup_state(now_ts: int) -> Optional[Dict[str, Any]]:
    """
    Load backup from disk if available.
    Returns dict if OK, else None.
    """
    if not BACKUP_FILE.exists():
        return None
    try:
        st = json.loads(BACKUP_FILE.read_text(errors="ignore"))
        if isinstance(st, dict):
            return st
    except Exception:
        pass
    return None

def load_state(now_ts: int) -> Dict[str, Any]:
    """
    Load state using this priority:
      1) Live state in /run (if present)
      2) Backup state on disk (if present)
      3) Fresh default
    """
    # 1) Live /run state (preferred while system is running)
    if STATE_FILE.exists():
        try:
            st = json.loads(STATE_FILE.read_text(errors="ignore"))
            if isinstance(st, dict):
                return st
        except Exception:
            # If /run state is corrupted, fall back to backup
            pass

    # 2) Backup state (survives reboot)
    b = load_backup_state(now_ts)
    if b is not None:
        # If backup is old and it's now a new day, we will reset "today" below anyway.
        return b

    # 3) Fresh start
    return default_state(now_ts)

def save_live_state(state: Dict[str, Any]) -> None:
    """Save live state to /run (RAM)."""
    atomic_write_json(STATE_FILE, state)

# --------------------------------------------------------------------
# "TODAY" ROLLOVER
# --------------------------------------------------------------------

def roll_daily_if_needed(state: Dict[str, Any], now_ts: int) -> None:
    """
    If local date changed since last run, reset daily fields.
    This handles midnight rollover and also handles clock corrections.
    """
    tk = today_key_local(now_ts)
    if state.get("today_key") != tk:
        state["today_key"] = tk
        state["today_seen_hex"] = {}
        state["today_seen_calls"] = {}
        state["passes_today"] = 0

        state["today_peak_aircraft_in_view"] = 0

        # Reset daily records
        state["today_max_alt_ft"] = None
        state["today_max_alt_info"] = None
        state["today_max_gs_kt"] = None
        state["today_max_gs_info"] = None

# --------------------------------------------------------------------
# HTML THROTTLING (reduce SD writes)
# --------------------------------------------------------------------

def load_html_meta() -> Dict[str, Any]:
    """Meta data used only for throttling HTML writes."""
    if not HTML_META_FILE.exists():
        return {"last_html_write_ts": 0}
    try:
        meta = json.loads(HTML_META_FILE.read_text(errors="ignore"))
        return meta if isinstance(meta, dict) else {"last_html_write_ts": 0}
    except Exception:
        return {"last_html_write_ts": 0}

def save_html_meta(meta: Dict[str, Any]) -> None:
    """Save meta to /run (RAM)."""
    atomic_write_json(HTML_META_FILE, meta)

def should_write_html(now_ts: int) -> bool:
    """
    Decide whether to rewrite /var/www/html/stats.html on this run.
    This is the SD-card wear reduction measure for the HTML output.
    """
    meta = load_html_meta()
    last = int(meta.get("last_html_write_ts", 0))
    if (now_ts - last) >= HTML_WRITE_INTERVAL:
        meta["last_html_write_ts"] = now_ts
        save_html_meta(meta)
        return True
    return False

# --------------------------------------------------------------------
# BACKUP LOGIC (survive reboot with low SD churn)
# --------------------------------------------------------------------

def maybe_backup_to_disk(state: Dict[str, Any], now_ts: int) -> None:
    """
    Periodically write a backup to /var/lib/adsb-stats/state-backup.json
    at BACKUP_INTERVAL_SECONDS (10 minutes).
    """
    last_b = int(state.get("last_backup_ts", 0))
    if last_b == 0:
        # First opportunity: do not necessarily back up immediately.
        # We can choose to back up right away, but it's fine to wait until interval.
        # If you prefer immediate backup on first run, set last_backup_ts to (now_ts - BACKUP_INTERVAL_SECONDS).
        pass

    if (now_ts - last_b) >= BACKUP_INTERVAL_SECONDS:
        # Important: backup should not include the HTML meta file (it is separate anyway).
        # We DO include last_backup_ts in backup, so the schedule continues across reboot.
        state["last_backup_ts"] = now_ts
        atomic_write_json(BACKUP_FILE, state)

# --------------------------------------------------------------------
# HTML RENDERING
# --------------------------------------------------------------------

def render_html(state: Dict[str, Any],
                rx_lat: Optional[float],
                rx_lon: Optional[float],
                now_ts: int,
                live: Optional[Dict[str, Any]] = None) -> str:
    """Render the stats page as a full HTML string."""

    live = live or {}

    def fmt_km(x: Optional[float]) -> str:
        return "-" if x is None else f"{x:.1f} km"


    def fmt_kt(x: Optional[float]) -> str:
        if x is None:
            return "-"
        kmh = x * 1.852
        return f"{x:.0f} kt ({kmh:.0f} km/h)"


    def fmt_ft(x: Optional[int]) -> str:
        if x is None:
            return "-"
        m = x * 0.3048
        return f"{x:,} ft ({m:.0f} m)"

    def fmt_info(info: Optional[Dict[str, Any]]) -> str:
        if not info:
            return "-"
        parts = []
        if info.get("hex"):
            parts.append(f"HEX: {info['hex']}")
        if info.get("callsign"):
            parts.append(f"Call: {info['callsign']}")
        if info.get("distance_km") is not None:
            parts.append(f"Dist: {info['distance_km']:.1f} km")
        if info.get("alt_ft") is not None:
            try:
                alt_ft = int(info['alt_ft'])
                alt_m = alt_ft * 0.3048
                parts.append(f"Alt: {alt_ft:,} ft ({alt_m:.0f} m)")
            except Exception:
                pass
        if info.get("gs_kt") is not None:
            try:
                gs_kt = float(info['gs_kt'])
                gs_kmh = gs_kt * 1.852
                parts.append(f"GS: {gs_kt:.0f} kt ({gs_kmh:.0f} km/h)")
            except Exception:
                pass
        if info.get("lat") is not None and info.get("lon") is not None:
            parts.append(f"Pos: {info['lat']:.4f}, {info['lon']:.4f}")
        if info.get("seen_ts"):
            parts.append(time.strftime("Seen: %Y-%m-%d %H:%M:%S", time.localtime(info["seen_ts"])))
        return " | ".join(parts)

    def fmt_live_entry(info: Optional[Dict[str, Any]]) -> str:
        if not info:
            return "-"
        parts = []
        if info.get("hex"):
            parts.append(str(info["hex"]))
        if info.get("callsign"):
            parts.append(str(info["callsign"]))
        if info.get("distance_km") is not None:
            parts.append(f"{float(info['distance_km']):.1f} km")
        return " • ".join(parts)

    created_ts = int(state.get("created_ts", now_ts))
    created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created_ts))
    updated = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now_ts))
    age_str = fmt_age(now_ts - created_ts)

    rx_lat_s = f"{rx_lat:.5f}" if rx_lat is not None else "?"
    rx_lon_s = f"{rx_lon:.5f}" if rx_lon is not None else "?"

    visits_gap_min = PASS_GAP_SECONDS // 60
    aircraft_total = int(live.get("aircraft_total", 0))
    aircraft_fresh_pos = int(live.get("aircraft_fresh_pos", 0))
    nearest_now = live.get("nearest_now")
    farthest_now = live.get("farthest_now")
    highest_alt_now_ft = live.get("highest_alt_now_ft")
    fastest_gs_now_kt = live.get("fastest_gs_now_kt")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="refresh" content="{HTML_META_REFRESH_SECONDS}">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ADS-B Stats</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Arial, sans-serif; margin: 24px; }}
    h1 {{ margin: 0 0 12px 0; }}
    .meta {{ color: #555; margin-bottom: 18px; line-height: 1.5; }}
        .card {{ border: 1px solid #ddd; border-radius: 10px; padding: 16px; max-width: 980px; }}
        h2 {{ margin: 0 0 10px 0; font-size: 18px; }}
        .section {{ margin-bottom: 16px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px 18px; }}
    .k {{ color: #555; }}
    .v {{ font-weight: 600; }}
    code {{ background: #f6f6f6; padding: 2px 6px; border-radius: 6px; }}
    .wide {{ grid-column: 1 / -1; }}
        .note {{ color: #666; font-size: 13px; margin-top: 8px; }}
  </style>
</head>
<body>
    <h1>HB9IIU ADS-B Receiver Stats</h1>

  <div class="meta">
    Created: <code>{created}</code> • Updated: <code>{updated}</code><br>
    History age: <code>{age_str}</code> • Today: <code>{state.get("today_key","?")}</code><br>
    Receiver: <code>{rx_lat_s}</code>, <code>{rx_lon_s}</code> • Auto refresh: {HTML_META_REFRESH_SECONDS}s
  </div>

  <div class="card">
        <div class="section">
            <h2>Now</h2>
            <div class="grid">
                <div class="k">Aircraft currently in view</div>
                <div class="v">{aircraft_total}</div>

                <div class="k">With fresh position (≤ 60s)</div>
                <div class="v">{aircraft_fresh_pos}</div>

                <div class="k">Nearest right now</div>
                <div class="v">{fmt_live_entry(nearest_now)}</div>

                <div class="k">Farthest right now</div>
                <div class="v">{fmt_live_entry(farthest_now)}</div>

                <div class="k">Highest altitude right now</div>
                <div class="v">{fmt_ft(highest_alt_now_ft)}</div>

                <div class="k">Fastest ground speed right now</div>
                <div class="v">{fmt_kt(fastest_gs_now_kt)}</div>
            </div>
        </div>

        <div class="section">
            <h2>Today</h2>
            <div class="grid">
                <div class="k">New aircraft (unique HEX)</div>
                <div class="v">{len(state.get("today_seen_hex", {}))}</div>

                <div class="k">New flights (callsigns)</div>
                <div class="v">{len(state.get("today_seen_calls", {}))}</div>

                <div class="k">Visits (gap ≥ {visits_gap_min} min)</div>
                <div class="v">{int(state.get("passes_today", 0))}</div>

                <div class="k">Peak aircraft in view</div>
                <div class="v">{int(state.get("today_peak_aircraft_in_view", 0))}</div>

                <div class="k">Highest altitude</div>
                <div class="v">{fmt_ft(state.get("today_max_alt_ft"))}</div>

                <div class="k">Fastest ground speed</div>
                <div class="v">{fmt_kt(state.get("today_max_gs_kt"))}</div>
            </div>
            <div class="note">
                A new “visit” starts when an aircraft hasn’t been seen for at least {visits_gap_min} minutes.
            </div>
        </div>

        <div class="section" style="margin-bottom:0;">
            <h2>Records (since history started)</h2>
            <div class="grid">

                <div class="k">Total aircraft seen since begin (unique HEX)</div>
                <div class="v">{len(state.get("seen_hex", {}))}</div>

                <div class="k">Farthest range</div>
                <div class="v">{fmt_km(state.get("max_distance_km"))}</div>

                <div class="k">Closest range</div>
                <div class="v">{fmt_km(state.get("min_distance_km"))}</div>

                <div class="k">Highest altitude</div>
                <div class="v">{fmt_ft(state.get("max_alt_ft"))}</div>

                <div class="k">Fastest ground speed</div>
                <div class="v">{fmt_kt(state.get("max_gs_kt"))}</div>

                <div class="k">Peak aircraft in view</div>
                <div class="v">{int(state.get("peak_aircraft_in_view", 0))}</div>

                <div class="k wide">Farthest details</div>
                <div class="v wide">{fmt_info(state.get("max_distance_info"))}</div>

                <div class="k wide">Closest details</div>
                <div class="v wide">{fmt_info(state.get("min_distance_info"))}</div>

                <div class="k wide">Highest altitude details</div>
                <div class="v wide">{fmt_info(state.get("max_alt_info"))}</div>

                <div class="k wide">Fastest speed details</div>
                <div class="v wide">{fmt_info(state.get("max_gs_info"))}</div>
            </div>
        </div>
  </div>

  <p style="margin-top:14px;">
    Tip: Open tar1090 at <a href="/tar1090/">/tar1090/</a>
  </p>
</body>
</html>
"""

# --------------------------------------------------------------------
# MAIN LOOP (single run)
# --------------------------------------------------------------------

def main() -> None:
    now_ts = int(time.time())

    if "--reset" in sys.argv:
        # Wipe both RAM state and disk backup.
        for p in (STATE_FILE, HTML_META_FILE, BACKUP_FILE, OUT_HTML):
            try:
                p.unlink(missing_ok=True)  # py3.8+: ok on modern distros
            except TypeError:
                # older python compatibility
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
            except Exception:
                pass
        return

    # Load state (prefers /run; falls back to disk backup after reboot)
    state = load_state(now_ts)

    # If we restored from disk backup, /run directory may not exist yet
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Make sure daily counters are correct for "today"
    roll_daily_if_needed(state, now_ts)

    # Receiver lat/lon (optional: used only for distance stats)
    rx_lat, rx_lon = read_receiver_latlon()
    can_distance = (rx_lat is not None and rx_lon is not None)

    # If snapshot is missing/empty, we still:
    # - backup periodically
    # - update HTML occasionally (throttled)
    if (not AIRCRAFT_JSON.exists()) or (AIRCRAFT_JSON.stat().st_size == 0):
        # HTML: write only if interval elapsed
        if should_write_html(now_ts):
            OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
            OUT_HTML.write_text(render_html(state, rx_lat, rx_lon, now_ts, live={
                "aircraft_total": 0,
                "aircraft_fresh_pos": 0,
                "nearest_now": None,
                "farthest_now": None,
            }))

        # Live state save (RAM)
        save_live_state(state)

        # Disk backup occasionally
        maybe_backup_to_disk(state, now_ts)
        return

    # Read one snapshot per run
    try:
        data = json.loads(AIRCRAFT_JSON.read_text(errors="ignore"))
    except Exception:
        # Snapshot could be mid-write; just keep state and try next run.
        if should_write_html(now_ts):
            OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
            OUT_HTML.write_text(render_html(state, rx_lat, rx_lon, now_ts, live={
                "aircraft_total": 0,
                "aircraft_fresh_pos": 0,
                "nearest_now": None,
                "farthest_now": None,
            }))
        save_live_state(state)
        maybe_backup_to_disk(state, now_ts)
        return

    aircraft = data.get("aircraft", [])
    if not isinstance(aircraft, list):
        aircraft = []

    # Ensure dictionaries exist (useful if state came from older version)
    seen_hex = state.setdefault("seen_hex", {})
    seen_calls = state.setdefault("seen_calls", {})
    today_hex = state.setdefault("today_seen_hex", {})
    today_calls = state.setdefault("today_seen_calls", {})
    last_seen = state.setdefault("last_seen_ts", {})

    # Ensure record keys exist for older backups
    state.setdefault("max_alt_ft", None)
    state.setdefault("max_alt_info", None)
    state.setdefault("today_max_alt_ft", None)
    state.setdefault("today_max_alt_info", None)
    state.setdefault("max_gs_kt", None)
    state.setdefault("max_gs_info", None)
    state.setdefault("today_max_gs_kt", None)
    state.setdefault("today_max_gs_info", None)

    state.setdefault("peak_aircraft_in_view", 0)
    state.setdefault("today_peak_aircraft_in_view", 0)

    passes_total = int(state.get("passes_total", 0))
    passes_today = int(state.get("passes_today", 0))

    # Optional pruning: drop aircraft we haven't seen for a long time from last_seen_ts
    if PRUNE_LAST_SEEN_OLDER_THAN_SECONDS > 0 and isinstance(last_seen, dict):
        prune_before = now_ts - PRUNE_LAST_SEEN_OLDER_THAN_SECONDS
        old_keys = [
            hx for hx, ts in last_seen.items()
            if isinstance(ts, (int, float)) and ts < prune_before
        ]
        for hx in old_keys:
            last_seen.pop(hx, None)

    # Live snapshot facts (computed per-run)
    aircraft_total = 0
    aircraft_fresh_pos = 0
    nearest_now: Optional[Dict[str, Any]] = None
    farthest_now: Optional[Dict[str, Any]] = None
    highest_alt_now_ft: Optional[int] = None
    fastest_gs_now_kt: Optional[float] = None

    # Process each aircraft entry in this snapshot
    for a in aircraft:
        if not isinstance(a, dict):
            continue

        hx = a.get("hex")
        if not hx:
            continue

        aircraft_total += 1

        # Fresh position: readsb provides seen_pos as seconds since last position update.
        sp = _to_float(a.get("seen_pos"))
        if sp is not None and sp <= 60.0:
            aircraft_fresh_pos += 1

        # Optional metric: count processed entries (NOT unique)
        state["total_seen_updates"] = int(state.get("total_seen_updates", 0)) + 1

        # Unique aircraft since history start
        if hx not in seen_hex:
            seen_hex[hx] = now_ts

        # Unique aircraft today
        if hx not in today_hex:
            today_hex[hx] = now_ts

        # Callsign uniqueness (since history start + today)
        cs = safe_callsign(a)
        if cs:
            if cs not in seen_calls:
                seen_calls[cs] = now_ts
            if cs not in today_calls:
                today_calls[cs] = now_ts

        # PASS counting logic:
        # - A "pass" is counted if:
        #   * first time ever seeing this hex, OR
        #   * last_seen_ts is >= PASS_GAP_SECONDS ago
        last = last_seen.get(hx)
        is_new_pass = False

        if last is None:
            is_new_pass = True
        else:
            try:
                if (now_ts - int(last)) >= PASS_GAP_SECONDS:
                    is_new_pass = True
            except Exception:
                # Corrupted last value -> treat as new pass
                is_new_pass = True

        if is_new_pass:
            passes_total += 1
            passes_today += 1

        # Always update last_seen_ts
        last_seen[hx] = now_ts

        # Distance stats: only if we have receiver lat/lon AND aircraft lat/lon
        if can_distance and ("lat" in a) and ("lon" in a):
            try:
                dist_km = haversine_km(float(rx_lat), float(rx_lon), float(a["lat"]), float(a["lon"]))
            except Exception:
                continue

            info = {
                "hex": hx,
                "callsign": cs,
                "distance_km": dist_km,
                "lat": float(a["lat"]),
                "lon": float(a["lon"]),
                "seen_ts": now_ts,
            }

            # Max distance record
            if state.get("max_distance_km") is None or dist_km > float(state["max_distance_km"]):
                state["max_distance_km"] = dist_km
                state["max_distance_info"] = info

            # Min distance record
            if state.get("min_distance_km") is None or dist_km < float(state["min_distance_km"]):
                state["min_distance_km"] = dist_km
                state["min_distance_info"] = info

            # Live nearest/farthest (this snapshot only)
            if nearest_now is None or dist_km < float(nearest_now.get("distance_km", 1e12)):
                nearest_now = info
            if farthest_now is None or dist_km > float(farthest_now.get("distance_km", -1.0)):
                farthest_now = info

        # Altitude records
        a_alt = alt_ft(a)
        if a_alt is not None:
            if highest_alt_now_ft is None or a_alt > highest_alt_now_ft:
                highest_alt_now_ft = a_alt

            cur_max_alt = state.get("max_alt_ft")
            if cur_max_alt is None or a_alt > int(cur_max_alt):
                state["max_alt_ft"] = a_alt
                state["max_alt_info"] = {
                    "hex": hx,
                    "callsign": cs,
                    "distance_km": None,
                    "lat": _to_float(a.get("lat")),
                    "lon": _to_float(a.get("lon")),
                    "seen_ts": now_ts,
                    "alt_ft": a_alt,
                }

            cur_today_max_alt = state.get("today_max_alt_ft")
            if cur_today_max_alt is None or a_alt > int(cur_today_max_alt):
                state["today_max_alt_ft"] = a_alt
                state["today_max_alt_info"] = {
                    "hex": hx,
                    "callsign": cs,
                    "distance_km": None,
                    "lat": _to_float(a.get("lat")),
                    "lon": _to_float(a.get("lon")),
                    "seen_ts": now_ts,
                    "alt_ft": a_alt,
                }

        # Speed records
        a_gs = gs_kt(a)
        if a_gs is not None:
            if fastest_gs_now_kt is None or a_gs > fastest_gs_now_kt:
                fastest_gs_now_kt = a_gs

            cur_max_gs = state.get("max_gs_kt")
            if cur_max_gs is None or a_gs > float(cur_max_gs):
                state["max_gs_kt"] = a_gs
                state["max_gs_info"] = {
                    "hex": hx,
                    "callsign": cs,
                    "distance_km": None,
                    "lat": _to_float(a.get("lat")),
                    "lon": _to_float(a.get("lon")),
                    "seen_ts": now_ts,
                    "gs_kt": a_gs,
                }

            cur_today_max_gs = state.get("today_max_gs_kt")
            if cur_today_max_gs is None or a_gs > float(cur_today_max_gs):
                state["today_max_gs_kt"] = a_gs
                state["today_max_gs_info"] = {
                    "hex": hx,
                    "callsign": cs,
                    "distance_km": None,
                    "lat": _to_float(a.get("lat")),
                    "lon": _to_float(a.get("lon")),
                    "seen_ts": now_ts,
                    "gs_kt": a_gs,
                }

    # Store pass counters back into state
    state["passes_total"] = passes_total
    state["passes_today"] = passes_today

    # Peak traffic
    try:
        state["peak_aircraft_in_view"] = max(int(state.get("peak_aircraft_in_view", 0)), int(aircraft_total))
        state["today_peak_aircraft_in_view"] = max(int(state.get("today_peak_aircraft_in_view", 0)), int(aircraft_total))
    except Exception:
        pass


    # Write HTML and TFT JSON (throttled)
    if should_write_html(now_ts):
        OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
        OUT_HTML.write_text(render_html(state, rx_lat, rx_lon, now_ts, live={
            "aircraft_total": aircraft_total,
            "aircraft_fresh_pos": aircraft_fresh_pos,
            "nearest_now": nearest_now,
            "farthest_now": farthest_now,
            "highest_alt_now_ft": highest_alt_now_ft,
            "fastest_gs_now_kt": fastest_gs_now_kt,
        }))

        # --- TFT JSON export ---
        tft_json = {
            # Now/Today
            "aircraft_in_view": aircraft_total,
            "nearest_km": round(float(nearest_now["distance_km"]), 1) if nearest_now and "distance_km" in nearest_now else None,
            "farthest_km": round(float(farthest_now["distance_km"]), 1) if farthest_now and "distance_km" in farthest_now else None,
            "highest_alt_m": round(highest_alt_now_ft * 0.3048) if highest_alt_now_ft is not None else None,
            "fastest_kmh": round(fastest_gs_now_kt * 1.852) if fastest_gs_now_kt is not None else None,
            "unique_today": len(state.get("today_seen_hex", {})),
            "peak_today": int(state.get("today_peak_aircraft_in_view", 0)),
            "uptime": int(time.time()) - int(state.get("created_ts", int(time.time()))),
            "uptime_str": fmt_age(int(time.time()) - int(state.get("created_ts", int(time.time())))),
            # Records
            "unique_ever": len(state.get("seen_hex", {})),
            "farthest_record_km": round(float(state["max_distance_km"]), 1) if state.get("max_distance_km") is not None else None,
            "closest_record_km": round(float(state["min_distance_km"]), 1) if state.get("min_distance_km") is not None else None,
            "highest_record_m": round(state["max_alt_ft"] * 0.3048) if state.get("max_alt_ft") is not None else None,
            "fastest_record_kmh": round(state["max_gs_kt"] * 1.852) if state.get("max_gs_kt") is not None else None,
            "peak_record": int(state.get("peak_aircraft_in_view", 0)),
        }
        # Write JSON file
        TFT_JSON_PATH = Path("/var/www/html/stats_tft.json")
        TFT_JSON_PATH.write_text(json.dumps(tft_json, indent=2, sort_keys=True))

    # Save live state to /run (RAM)
    save_live_state(state)

    # Periodic backup to disk (every 10 minutes)
    maybe_backup_to_disk(state, now_ts)

if __name__ == "__main__":
    main()
