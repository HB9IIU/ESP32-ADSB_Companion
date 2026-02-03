import math
import os
import shutil
import time
from io import BytesIO
from datetime import datetime

import requests
from PIL import Image, ImageDraw



# ============================ USER SETTINGS =================================
# --- Google Static Maps API key ---
# Get a valid key here:
# https://console.cloud.google.com/apis/credentials
# (Enable "Static Maps API" for your project, then create an API key)
GOOGLE_MAPS_KEY = "69AIzaSyAWpgxpxah1JAuXXbHNQRUXDLUI93Mr5wM"  # this is a fake key

# --- Map center & size ---
CENTER_LAT = 46.4717185
CENTER_LON = 6.4767709
RANGE_KM   = 80
# ============================================================================



OUT_W = 480
OUT_H = 320

# --- Output ---
OUT_DIR = "google_maps"
DELETE_STYLE_DIR_IF_NOT_EMPTY = True
CONVERT_TO_RGB565_HEADER = True

# --- Map styles to fetch ---
GOOGLE_MAPTYPES = ["roadmap", "terrain", "hybrid", "satellite"]

# --- Range rings overlay ---
DRAW_RINGS   = False
RING_STEP_KM = 10
RING_MAX_KM  = 200
RING_COLOR   = (0, 255, 0, 140)   # RGBA

# --- Optional test markers ---
DRAW_TEST_MARKERS = False
TEST_MARKERS = [
    ("Bern",   46.94809,  7.44744),
    ("Geneva", 46.204391, 6.143158),
]
TEST_MARKER_COLOR  = (255, 0, 0, 220)
TEST_MARKER_RADIUS = 4
TEST_MARKER_LABELS = True

# --- Logging / HTTP ---
VERBOSE = True
HTTP_RETRIES = 2
HTTP_BACKOFF_S = 0.6

# ============================================================================
# ======================= INTERNAL CONSTANTS (DO NOT TOUCH) ==================
# ============================================================================

R_EARTH_M = 6378137.0
TILE_PX  = 256


# ============================================================================
# Logging helpers
# ============================================================================
def ts():
    return datetime.now().strftime("%H:%M:%S")


def log(msg):
    if VERBOSE:
        print(f"[{ts()}] {msg}")


# ============================================================================
# Web Mercator helpers
# ============================================================================
def latlon_to_global_pixels(lat_deg, lon_deg, zoom):
    lat_deg = max(min(lat_deg, 85.05112878), -85.05112878)
    lat = math.radians(lat_deg)
    n = 2 ** zoom
    x = (lon_deg + 180.0) / 360.0 * (TILE_PX * n)
    y = (1.0 - math.log(math.tan(lat) + 1.0 / math.cos(lat)) / math.pi) / 2.0 * (TILE_PX * n)
    return x, y


def global_pixels_to_latlon(x, y, zoom):
    n = 2 ** zoom
    lon = x / (TILE_PX * n) * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / (TILE_PX * n)))))
    return lat, lon


def meters_per_pixel(lat_deg, zoom):
    return (
        math.cos(math.radians(lat_deg))
        * 2.0 * math.pi * R_EARTH_M
        / (TILE_PX * (2 ** zoom))
    )


def choose_zoom_for_width(lat_deg, width_px, width_m):
    mpp_target = width_m / width_px
    val = (
        math.cos(math.radians(lat_deg))
        * 2.0 * math.pi * R_EARTH_M
        / (TILE_PX * mpp_target)
    )
    return int(round(math.log(val, 2)))


def compute_geometry(center_lat, center_lon, range_km, out_w, out_h):
    width_m = 2 * range_km * 1000.0
    zoom = choose_zoom_for_width(center_lat, out_w, width_m)

    cx, cy = latlon_to_global_pixels(center_lat, center_lon, zoom)

    px0 = cx - out_w / 2
    py0 = cy - out_h / 2
    px1 = px0 + out_w
    py1 = py0 + out_h

    return {
        "zoom": zoom,
        "px0": px0,
        "py0": py0,
        "top_left_latlon": global_pixels_to_latlon(px0, py0, zoom),
        "bottom_right_latlon": global_pixels_to_latlon(px1, py1, zoom),
    }


# ============================================================================
# Overlays
# ============================================================================
def draw_range_rings(img, center_lat, center_lon, zoom, px0, py0):
    w, h = img.size
    cxg, cyg = latlon_to_global_pixels(center_lat, center_lon, zoom)
    cx = cxg - px0
    cy = cyg - py0

    mpp = meters_per_pixel(center_lat, zoom)

    base = img.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    for km in range(RING_STEP_KM, RING_MAX_KM + 1, RING_STEP_KM):
        r_px = (km * 1000.0) / mpp
        d.ellipse(
            (cx - r_px, cy - r_px, cx + r_px, cy + r_px),
            outline=RING_COLOR,
            width=1,
        )

    d.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=RING_COLOR)
    return Image.alpha_composite(base, overlay).convert("RGB")


def draw_markers(img, zoom, px0, py0):
    w, h = img.size
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    for name, lat, lon in TEST_MARKERS:
        gx, gy = latlon_to_global_pixels(lat, lon, zoom)
        x = gx - px0
        y = gy - py0

        if -20 <= x <= w + 20 and -20 <= y <= h + 20:
            r = TEST_MARKER_RADIUS
            d.ellipse((x - r, y - r, x + r, y + r), fill=TEST_MARKER_COLOR)
            if TEST_MARKER_LABELS:
                d.text((x + r + 4, y - r), name, fill=TEST_MARKER_COLOR)

    return Image.alpha_composite(base, overlay).convert("RGB")


# ============================================================================
# Folder helpers
# ============================================================================
def ensure_empty_dir(path):
    if os.path.exists(path) and any(os.scandir(path)) and DELETE_STYLE_DIR_IF_NOT_EMPTY:
        shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)


# ============================================================================
# RGB565 export
# ============================================================================
def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def write_background565_h(png_path, h_path, w, h):
    img = Image.open(png_path).convert("RGB")
    if img.size != (w, h):
        raise RuntimeError("Image size mismatch")

    with open(h_path, "w") as f:
        f.write("#pragma once\n#include <stdint.h>\n#include <pgmspace.h>\n\n")
        f.write(f"static const uint16_t bg565[{w*h}] PROGMEM = {{\n")

        for r, g, b in img.get_flattened_data():
            f.write(f"0x{rgb565(r, g, b):04X},")

        f.write("\n};\n")

# ============================================================================
# Google Static Maps
# ============================================================================
def fetch_google_static(session, lat, lon, zoom, w, h, maptype):
    url = (
        "https://maps.googleapis.com/maps/api/staticmap"
        f"?center={lat},{lon}"
        f"&zoom={zoom}"
        f"&size={w}x{h}"
        f"&maptype={maptype}"
        f"&key={GOOGLE_MAPS_KEY}"
    )

    for i in range(HTTP_RETRIES + 1):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return Image.open(BytesIO(r.content)).convert("RGB")
        except Exception:
            time.sleep(HTTP_BACKOFF_S * (i + 1))
    raise RuntimeError("HTTP fetch failed")


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":

    geom = compute_geometry(CENTER_LAT, CENTER_LON, RANGE_KM, OUT_W, OUT_H)
    zoom = geom["zoom"]

    log(f"Zoom={zoom}")
    log(f"Top-left={geom['top_left_latlon']}")
    log(f"Bottom-right={geom['bottom_right_latlon']}")

    os.makedirs(OUT_DIR, exist_ok=True)

    with requests.Session() as session:
        for mt in GOOGLE_MAPTYPES:
            style_dir = os.path.join(OUT_DIR, f"google_{mt}")
            ensure_empty_dir(style_dir)

            png_path = os.path.join(style_dir, "map.png")
            h_path   = os.path.join(style_dir, "background565.h")

            img = fetch_google_static(
                session, CENTER_LAT, CENTER_LON, zoom, OUT_W, OUT_H, mt
            )

            if DRAW_RINGS:
                img = draw_range_rings(img, CENTER_LAT, CENTER_LON, zoom, geom["px0"], geom["py0"])

            if DRAW_TEST_MARKERS:
                img = draw_markers(img, zoom, geom["px0"], geom["py0"])

            img.save(png_path)
            log(f"Saved {png_path}")

            if CONVERT_TO_RGB565_HEADER:
                write_background565_h(png_path, h_path, OUT_W, OUT_H)
                log(f"Saved {h_path}")

    print("\nPaste into ESP32 Config.h:")
    print(f"static const int    MAP_ZOOM = {zoom};")
    print(f"static const double MAP_PX0  = {geom['px0']};")
    print(f"static const double MAP_PY0  = {geom['py0']};")
