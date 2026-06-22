#!/usr/bin/env python3
import json
import time
import re
import math
import requests
import airportsdata
from pathlib import Path
from datetime import datetime

# ================= CONFIG =================
AIRCRAFT_JSON = Path("/run/readsb/aircraft.json")
POLL_SECONDS = 1
LOST_TIMEOUT = 30
MIN_QUERY_INTERVAL = 4
HTTP_TIMEOUT = 20
CRUISE_SPEED_KMH = 840
# ==========================================

airports = airportsdata.load()
iata_index = {v["iata"]: v for v in airports.values() if v.get("iata")}

tracked = {}
route_cache = {}
last_query_time = 0


# ================= UTILS =================
def now_str():
    return datetime.now().strftime("%H:%M:%S")


def format_duration(seconds):
    seconds = int(seconds)
    m = seconds // 60
    s = seconds % 60
    if m > 0:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def format_eta(minutes):
    h = minutes // 60
    m = minutes % 60
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) *
         math.sin(dlon / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_airport(code):
    if not code:
        return None
    code = code.upper()
    return airports.get(code) or iata_index.get(code)


# ================= FlightAware =================
def flightaware_dep_arr(ident: str, timeout: int = 20):
    url = f"https://www.flightaware.com/live/flight/{ident}"
    r = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )

    if r.status_code != 200:
        return None

    html = r.text

    def grab(key: str):
        m = re.search(
            r"setTargeting\(\s*'%s'\s*,\s*'([^']*)'\s*\)" % re.escape(key),
            html,
        )
        return m.group(1) if m else None

    origin_iata = grab("origin_IATA")
    origin_icao = grab("origin")
    dest_iata = grab("destination_IATA")
    dest_icao = grab("destination")

    if not origin_icao or not dest_icao:
        return None

    o = origin_iata or origin_icao
    d = dest_iata or dest_icao

    if o and d:
        return o, d

    return None


def get_route(callsign: str):
    global last_query_time

    callsign = callsign.strip().upper()
    if not callsign:
        return None

    if callsign in route_cache:
        return route_cache[callsign]

    now = time.time()
    wait = MIN_QUERY_INTERVAL - (now - last_query_time)
    if wait > 0:
        time.sleep(wait)

    try:
        result = flightaware_dep_arr(callsign, timeout=HTTP_TIMEOUT)
    except Exception:
        result = None

    last_query_time = time.time()

    if not result:
        route_cache[callsign] = None
        return None

    origin_code, dest_code = result
    airport1 = get_airport(origin_code)
    airport2 = get_airport(dest_code)

    if not airport1 or not airport2:
        route_cache[callsign] = None
        return None

    total_km = int(haversine_km(
        airport1["lat"], airport1["lon"],
        airport2["lat"], airport2["lon"]
    ))

    route_cache[callsign] = {
        "origin": origin_code,
        "dest": dest_code,
        "origin_name": airport1.get("city") or airport1.get("name"),
        "dest_name": airport2.get("city") or airport2.get("name"),
        "dest_lat": airport2["lat"],
        "dest_lon": airport2["lon"],
        "total_km": total_km
    }

    return route_cache[callsign]


# ================= MAIN =================
def main():
    global tracked

    while True:
        try:
            data = json.loads(AIRCRAFT_JSON.read_text(errors="ignore"))
        except Exception:
            time.sleep(POLL_SECONDS)
            continue

        current_hex = set()
        now = time.time()

        for a in data.get("aircraft", []):
            hx = a.get("hex")
            if not hx:
                continue

            hx = hx.lower()
            current_hex.add(hx)

            callsign = (a.get("flight") or "").strip()
            lat = a.get("lat")
            lon = a.get("lon")
            gs_knots = a.get("gs")

            if hx not in tracked:
                tracked[hx] = {
                    "enter": now,
                    "last": now,
                    "callsign": callsign,
                    "route": None,
                }
                print(f"🟢 {now_str()}  ENTER  {hx}  {callsign}", flush=True)
            else:
                tracked[hx]["last"] = now

            if callsign:
                if not tracked[hx]["callsign"]:
                    tracked[hx]["callsign"] = callsign
                    print(f"🔵 {now_str()}  CALL   {hx}  {callsign}", flush=True)

                if not tracked[hx]["route"]:
                    route = get_route(callsign)
                    if route:
                        tracked[hx]["route"] = route

                        print(
                            f"🟣 {now_str()}  ROUTE  {hx}  "
                            f"{route['origin']}-{route['dest']}  "
                            f"({route['origin_name']} → {route['dest_name']})  "
                            f"{route['total_km']} km",
                            flush=True
                        )

                # ===== LIVE ETA =====
                route = tracked[hx]["route"]
                if route and lat and lon and gs_knots:
                    speed_kmh = float(gs_knots) * 1.852
                    remaining_km = haversine_km(
                        float(lat), float(lon),
                        route["dest_lat"], route["dest_lon"]
                    )

                    if speed_kmh > 100:
                        eta_minutes = int((remaining_km / speed_kmh) * 60)

                        print(
                            f"✈️  {now_str()}  ETA    {hx}  "
                            f"{int(remaining_km)} km remaining  "
                            f"~{format_eta(eta_minutes)}",
                            flush=True
                        )

        # LOST
        to_remove = []
        for hx, info in tracked.items():
            if hx not in current_hex:
                if now - info["last"] > LOST_TIMEOUT:
                    duration = format_duration(info["last"] - info["enter"])
                    print(f"🔴 {now_str()}  LOST   {hx}  ({duration})", flush=True)
                    to_remove.append(hx)

        for hx in to_remove:
            del tracked[hx]

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
