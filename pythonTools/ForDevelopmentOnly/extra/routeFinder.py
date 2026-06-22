#!/usr/bin/env python3
import json
import time
import re
import math
import threading
from pathlib import Path
from datetime import datetime, timezone

import requests
import airportsdata
from flask import Flask, jsonify

HEXDB_ROUTE_URL = "https://hexdb.io/api/v1/route/icao/{callsign}"

# ================= CONFIG =================
AIRCRAFT_JSON = Path("/run/readsb/aircraft.json")

HTTP_TIMEOUT = 10
POLL_RETRY_SECONDS = 1

HOST = "0.0.0.0"
PORT = 6969
# ==========================================

app = Flask(__name__)

airports = airportsdata.load()
iata_index = {v["iata"]: v for v in airports.values() if v.get("iata")}

# Caches / state
route_cache: dict[str, dict | None] = {}

# Lock (Flask can run threaded)
route_lock = threading.Lock()


# ================= UTILS =================
def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def format_eta(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) *
         math.sin(dlon / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_airport(code: str | None):
    if not code:
        return None
    code = code.upper()
    return airports.get(code) or iata_index.get(code)


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def clean_hex_icao24(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^0-9a-f]", "", s)
    return s


# ================= readsb lookup =================
def read_aircraft_json():
    for _ in range(3):
        try:
            return json.loads(AIRCRAFT_JSON.read_text(errors="ignore"))
        except Exception:
            time.sleep(POLL_RETRY_SECONDS)
    return None


def find_aircraft_by_hex(hex_icao24: str):
    data = read_aircraft_json()
    if not data:
        return None

    target = hex_icao24.lower().strip()
    for a in data.get("aircraft", []):
        hx = (a.get("hex") or "").lower().strip()
        if hx == target:
            return a
    return None


# ================= hexdb.io route lookup =================
def hexdb_dep_arr(callsign: str):
    url = HEXDB_ROUTE_URL.format(callsign=callsign)
    r = requests.get(url, timeout=HTTP_TIMEOUT)
    if r.status_code != 200:
        return None
    data = r.json()
    route_str = data.get("route", "")
    parts = route_str.split("-")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


def get_route(callsign: str):
    """
    Returns cached route dict or None.
    Caches both success and failure per callsign.
    Thread-safe for Flask threaded server.
    """
    callsign = callsign.strip().upper()
    if not callsign:
        return None

    # Cache check
    with route_lock:
        if callsign in route_cache:
            return route_cache[callsign]

    try:
        result = hexdb_dep_arr(callsign)
    except Exception:
        result = None

    if not result:
        with route_lock:
            route_cache[callsign] = None
        return None

    origin_code, dest_code = result
    airport1 = get_airport(origin_code)
    airport2 = get_airport(dest_code)

    if not airport1 or not airport2:
        with route_lock:
            route_cache[callsign] = None
        return None

    total_km = int(haversine_km(
        airport1["lat"], airport1["lon"],
        airport2["lat"], airport2["lon"]
    ))

    route = {
        "origin": origin_code,
        "dest": dest_code,
        "origin_name": airport1.get("city") or airport1.get("name"),
        "dest_name": airport2.get("city") or airport2.get("name"),
        "dest_lat": airport2["lat"],
        "dest_lon": airport2["lon"],
        "total_km": total_km,
    }

    with route_lock:
        route_cache[callsign] = route

    return route


# ================= “business logic” =================
def build_summary_for_hex(hx: str) -> dict:
    """
    Builds the JSON payload for a given ICAO24 hex.
    Raises ValueError with a message on user-facing errors.
    """
    hx = clean_hex_icao24(hx)
    if len(hx) != 6:
        raise ValueError("invalid hex (expected 6 hex chars)")

    a = find_aircraft_by_hex(hx)
    if not a:
        raise ValueError("aircraft not currently visible")

    callsign = (a.get("flight") or "").strip().upper()
    lat = safe_float(a.get("lat"))
    lon = safe_float(a.get("lon"))
    gs_knots = safe_float(a.get("gs"))

    payload = {
        "ts": iso_utc_now(),
        "hex": hx,
        "callsign": callsign or None,
        "lat": lat,
        "lon": lon,
        "gs_knots": gs_knots,
        "gs_kmh": (gs_knots * 1.852) if gs_knots is not None else None,
        "alt_baro": a.get("alt_baro"),
        "squawk": a.get("squawk"),
    }

    if not callsign:
        payload["route"] = None
        payload["line"] = None
        payload["line1"] = None
        payload["line2"] = None
        payload["error_detail"] = "no callsign in readsb for this aircraft"
        return payload

    route = get_route(callsign)
    if not route:
        payload["route"] = None
        payload["line"] = None
        payload["line1"] = None
        payload["line2"] = None
        payload["error_detail"] = "route not found (FlightAware scrape failed or unknown airports)"
        return payload

    payload["route"] = {
        "origin": route["origin"],
        "dest": route["dest"],
        "origin_name": route["origin_name"],
        "dest_name": route["dest_name"],
        "total_km": route["total_km"],
    }

    # Live remaining / ETA (optional)
    rem_km = None
    eta_min = None
    eta_str = "n/a"

    if lat is not None and lon is not None and gs_knots is not None:
        speed_kmh = gs_knots * 1.852
        rem_km = int(haversine_km(lat, lon, route["dest_lat"], route["dest_lon"]))

        if speed_kmh > 100:
            eta_min = int((rem_km / speed_kmh) * 60)
            eta_str = format_eta(eta_min)

    payload["remaining_km"] = rem_km
    payload["eta_min"] = eta_min

    payload["line1"] = (
        f"{route['origin']}-{route['dest']} "
        f"({route['origin_name']} - {route['dest_name']})"
    )
    payload["line2"] = (
        f"tot: {route['total_km']} km, "
        f"rem: {rem_km if rem_km is not None else 'n/a'} km, "
        f"ETA {eta_str}"
    )
    payload["line"] = f"{payload['line1']}, {payload['line2']}"

    return payload


# ================= Flask endpoints =================
@app.get("/api/health")
def api_health():
    return jsonify({"ok": True, "ts": iso_utc_now()})


@app.get("/api/flight/<hex_icao24>")
def api_flight(hex_icao24: str):
    try:
        payload = build_summary_for_hex(hex_icao24)
        # If we got a payload but route/line1/line2 missing, still return 200 with detail
        return jsonify(payload)
    except ValueError as e:
        return jsonify({"error": str(e), "ts": iso_utc_now(), "hex": clean_hex_icao24(hex_icao24)}), 404
    except Exception:
        import traceback; traceback.print_exc()
        return jsonify({"error": "internal error", "ts": iso_utc_now()}), 500


@app.get("/")
def root():
    return jsonify({
        "service": "adsb-flight-summary",
        "endpoints": ["/api/health", "/api/flight/<icao24hex>"],
        "ts": iso_utc_now(),
    })


def main():
    # Threaded is fine because we locked caches + rate limiting.
    app.run(host=HOST, port=PORT, threaded=True)


if __name__ == "__main__":
    main()
