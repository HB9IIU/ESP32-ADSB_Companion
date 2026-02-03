#!/usr/bin/env python3
"""
ESP32-friendly static map generator (480x320 default):
- Fetches XYZ (Web Mercator) tiles from multiple providers
- Stitches + crops to exact output size
- Saves each provider output to: <OUT_DIR>/<provider_id>/map.png
- Immediately converts map.png to: <OUT_DIR>/<provider_id>/background565.h
- Deletes provider subfolder first if it already exists and has content
- Uses TEMP tile cache by default (auto erased)
- Verbose progress output
- OPTIONAL: draw test markers (Bern/Geneva) to validate positioning

Dependencies:
  pip install requests pillow
"""

import math
import os
import time
import tempfile
import shutil
from io import BytesIO
from datetime import datetime

import requests
from PIL import Image, ImageDraw

# =============================================================================
# =============================== USER SETTINGS ===============================
# --- Map center & size ---
CENTER_LAT = 46.4717185
CENTER_LON = 6.4767709
RANGE_KM   = 80
# =============================================================================

R = 6378137.0
TILE = 256
USER_AGENT = "ESP32-ADSB-Map-Generator/1.4 (personal use)"

# Cache behavior:
#   "temp"   -> cache exists only during runtime (auto-erased after run)  ✅ recommended
#   "keep"   -> keep a persistent cache on disk
#   "delete" -> use persistent cache during run, then delete it afterwards
CACHE_MODE = "temp"
PERSISTENT_CACHE_ROOT = "tile_cache"

# Verbosity
VERBOSE = True
PROGRESS_EVERY_TILES = 8
SHOW_EACH_FAILED_TILE = True

# Output behavior
DELETE_PROVIDER_DIR_IF_NOT_EMPTY = True   # delete <OUT_DIR>/<provider_id>/ if it already has files

# Convert to RGB565 header after rendering
CONVERT_TO_RGB565_HEADER = True

# If True, only providers with nolabels=True are used
ONLY_NO_LABELS = False

# --- Test marker overlay (to validate geometry) ------------------------------
DRAW_TEST_MARKERS = False  # set False once you're done checking

# Bern and Geneva coordinates:
# Bern:   46.94809, 7.44744  :contentReference[oaicite:2]{index=2}
# Geneva: 46.204391, 6.143158 :contentReference[oaicite:3]{index=3}
TEST_MARKERS = [
    ("Bern",   46.94809,  7.44744),
    ("Geneva", 46.204391, 6.143158),
]
TEST_MARKER_COLOR = (255, 0, 0, 220)   # red
TEST_MARKER_RADIUS = 4
TEST_MARKER_LABELS = True


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str) -> None:
    if VERBOSE:
        print(f"[{ts()}] {msg}")


# -----------------------------------------------------------------------------
# Web Mercator / XYZ math
# -----------------------------------------------------------------------------

def latlon_to_global_pixels(lat_deg: float, lon_deg: float, zoom: int) -> tuple[float, float]:
    lat_deg = max(min(lat_deg, 85.05112878), -85.05112878)
    lat = math.radians(lat_deg)
    n = 2 ** zoom
    x = (lon_deg + 180.0) / 360.0 * (TILE * n)
    y = (1.0 - math.log(math.tan(lat) + (1.0 / math.cos(lat))) / math.pi) / 2.0 * (TILE * n)
    return x, y


def global_pixels_to_latlon(x: float, y: float, zoom: int) -> tuple[float, float]:
    n = 2 ** zoom
    lon = x / (TILE * n) * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / (TILE * n))))
    lat = math.degrees(lat_rad)
    return lat, lon


def meters_per_pixel(lat_deg: float, zoom: int) -> float:
    lat = math.radians(lat_deg)
    return math.cos(lat) * 2.0 * math.pi * R / (TILE * (2 ** zoom))


def choose_zoom_for_width(lat_deg: float, width_px: int, width_m: float) -> int:
    mpp_target = width_m / width_px
    val = math.cos(math.radians(lat_deg)) * 2.0 * math.pi * R / (TILE * mpp_target)
    z = math.log(val, 2)
    return int(round(z))


# -----------------------------------------------------------------------------
# Output folder utilities
# -----------------------------------------------------------------------------

def ensure_safe_path(path: str) -> None:
    norm = os.path.normpath(path).replace("\\", "/")
    if norm in (".", "", "/", ".."):
        raise ValueError(f"Refusing to use unsafe path: '{path}'")


def ensure_empty_dir(dir_path: str) -> None:
    ensure_safe_path(dir_path)

    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        return

    has_content = any(os.scandir(dir_path))
    if has_content and DELETE_PROVIDER_DIR_IF_NOT_EMPTY:
        log(f"Folder not empty -> deleting: {dir_path}")
        shutil.rmtree(dir_path, ignore_errors=True)
        os.makedirs(dir_path, exist_ok=True)
        log(f"Folder recreated: {dir_path}")
    else:
        os.makedirs(dir_path, exist_ok=True)


# -----------------------------------------------------------------------------
# RGB565 header conversion (your logic)
# -----------------------------------------------------------------------------

def rgb565(r: int, g: int, b: int) -> int:
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def write_background565_h(input_png: str, output_h: str, w: int, h: int) -> None:
    img = Image.open(input_png).convert("RGB")
    if img.size != (w, h):
        raise SystemExit(f"ERROR: image must be {w}x{h}, got {img.size}")

    pixels = list(img.get_flattened_data())

    with open(output_h, "w", encoding="utf-8") as f:
        f.write("#pragma once\n")
        f.write("#include <stdint.h>\n")
        f.write("#include <pgmspace.h>\n\n")
        f.write(f"static const uint16_t bg_w = {w};\n")
        f.write(f"static const uint16_t bg_h = {h};\n\n")
        f.write(f"static const uint16_t bg565[{w*h}] PROGMEM = {{\n")

        for i in range(0, len(pixels), 12):
            chunk = pixels[i:i+12]
            vals = [f"0x{rgb565(r,g,b):04X}" for (r, g, b) in chunk]
            f.write("  " + ", ".join(vals) + ",\n")

        f.write("};\n")


# -----------------------------------------------------------------------------
# Tile fetching / caching
# -----------------------------------------------------------------------------

def format_tile_url(template: str, z: int, x: int, y: int, subdomains=None, counter: int = 0) -> str:
    s = ""
    if "{s}" in template:
        if subdomains:
            s = subdomains[counter % len(subdomains)]
        else:
            s = "a"
    return template.format(z=z, x=x, y=y, s=s)


def fetch_tile(provider: dict,
               z: int, x: int, y: int,
               session: requests.Session,
               cache_root: str,
               stats: dict,
               counter: int = 0) -> Image.Image:
    n = 2 ** z
    x_wrapped = x % n

    if y < 0 or y >= n:
        stats["blank_tiles"] += 1
        return Image.new("RGB", (TILE, TILE), (240, 240, 240))

    prov_cache = os.path.join(cache_root, provider["id"])
    os.makedirs(prov_cache, exist_ok=True)

    ext = provider.get("ext", "png").lower()
    if ext == "jpg":
        ext = "jpeg"

    path = os.path.join(prov_cache, f"{z}_{x_wrapped}_{y}.{ext}")

    if os.path.exists(path):
        stats["cache_hits"] += 1
        with Image.open(path) as im:
            return im.convert("RGB")

    url = format_tile_url(
        provider["url"], z, x_wrapped, y,
        subdomains=provider.get("subdomains"),
        counter=counter
    )

    headers = {"User-Agent": USER_AGENT}
    retries = int(provider.get("retries", 2))
    last_exc = None

    for attempt in range(retries + 1):
        try:
            r = session.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGB")
            img.save(path)
            stats["downloaded"] += 1
            time.sleep(float(provider.get("sleep", 0.2)))
            return img
        except Exception as e:
            last_exc = e
            time.sleep(0.5 + 0.5 * attempt)

    stats["failed"] += 1
    if SHOW_EACH_FAILED_TILE:
        print(f"[WARN] tile fetch failed: {provider['id']} z{z} x{x_wrapped} y{y} -> {last_exc}")
    return Image.new("RGB", (TILE, TILE), (230, 230, 230))


# -----------------------------------------------------------------------------
# Overlays
# -----------------------------------------------------------------------------

def draw_range_rings(img_rgb: Image.Image,
                     center_lat: float, center_lon: float,
                     zoom: int, px0: float, py0: float,
                     step_km: int = 10, max_km: int = 200,
                     ring_color=(0, 255, 0, 140), ring_width: int = 1,
                     draw_center_dot: bool = True) -> Image.Image:
    w, h = img_rgb.size

    cxg, cyg = latlon_to_global_pixels(center_lat, center_lon, zoom)
    cx = cxg - px0
    cy = cyg - py0

    mpp = meters_per_pixel(center_lat, zoom)

    base = img_rgb.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    for km in range(step_km, max_km + 1, step_km):
        r_px = (km * 1000.0) / mpp
        bbox = (cx - r_px, cy - r_px, cx + r_px, cy + r_px)
        d.ellipse(bbox, outline=ring_color, width=ring_width)

    if draw_center_dot:
        r = 2
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ring_color)

    return Image.alpha_composite(base, overlay).convert("RGB")


def draw_markers(img_rgb: Image.Image,
                 zoom: int, px0: float, py0: float,
                 markers: list[tuple[str, float, float]],
                 color=(255, 0, 0, 220),
                 radius: int = 4,
                 draw_labels: bool = True) -> Image.Image:
    """
    Draws dots (and optional text labels) on the already-cropped image.
    Uses the same global-pixel mapping as aircraft plotting.
    """
    w, h = img_rgb.size
    base = img_rgb.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    for name, lat, lon in markers:
        gx, gy = latlon_to_global_pixels(lat, lon, zoom)
        x = gx - px0
        y = gy - py0

        # Draw even if slightly off-screen? Here: only if within reasonable bounds.
        if -20 <= x <= w + 20 and -20 <= y <= h + 20:
            d.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)

            # small crosshair for clarity
            d.line((x - radius - 3, y, x + radius + 3, y), fill=color, width=1)
            d.line((x, y - radius - 3, x, y + radius + 3), fill=color, width=1)

            if draw_labels:
                # label a bit offset so it doesn't cover the dot
                d.text((x + radius + 4, y - radius - 2), name, fill=color)

    return Image.alpha_composite(base, overlay).convert("RGB")


# -----------------------------------------------------------------------------
# Geometry / stitching
# -----------------------------------------------------------------------------

def compute_geometry(center_lat: float, center_lon: float, range_km: float, out_w: int, out_h: int) -> dict:
    width_m = 2 * range_km * 1000.0
    zoom = choose_zoom_for_width(center_lat, out_w, width_m)

    cx, cy = latlon_to_global_pixels(center_lat, center_lon, zoom)

    px0 = cx - out_w / 2.0
    py0 = cy - out_h / 2.0
    px1 = px0 + out_w
    py1 = py0 + out_h

    top_left = global_pixels_to_latlon(px0, py0, zoom)
    bottom_right = global_pixels_to_latlon(px1, py1, zoom)

    tx0 = int(math.floor(px0 / TILE))
    ty0 = int(math.floor(py0 / TILE))
    tx1 = int(math.floor((px1 - 1) / TILE))
    ty1 = int(math.floor((py1 - 1) / TILE))

    crop_left = int(round(px0 - tx0 * TILE))
    crop_top = int(round(py0 - ty0 * TILE))

    return {
        "zoom": zoom,
        "px0": px0, "py0": py0,
        "top_left_latlon": top_left,
        "bottom_right_latlon": bottom_right,
        "tx0": tx0, "ty0": ty0,
        "tx1": tx1, "ty1": ty1,
        "crop_left": crop_left,
        "crop_top": crop_top
    }


def render_one_provider(provider: dict, geom: dict,
                        out_w: int, out_h: int,
                        provider_dir: str,
                        center_lat: float, center_lon: float,
                        cache_root: str,
                        draw_rings: bool = True,
                        ring_step_km: int = 10, ring_max_km: int = 200,
                        ring_color=(0, 255, 0, 140)) -> tuple[str, str]:
    ensure_empty_dir(provider_dir)

    out_png = os.path.join(provider_dir, "map.png")
    out_hfile = os.path.join(provider_dir, "background565.h")

    tx0, ty0, tx1, ty1 = geom["tx0"], geom["ty0"], geom["tx1"], geom["ty1"]
    tiles_x = (tx1 - tx0 + 1)
    tiles_y = (ty1 - ty0 + 1)
    total_tiles = tiles_x * tiles_y

    log(f"--- Provider '{provider['id']}' ---")
    log(f"Output folder: {provider_dir}")
    log(f"Zoom z={geom['zoom']}  tiles: {tiles_x} x {tiles_y} = {total_tiles}")

    stitched = Image.new("RGB", (tiles_x * TILE, tiles_y * TILE))
    stats = {"cache_hits": 0, "downloaded": 0, "failed": 0, "blank_tiles": 0}

    with requests.Session() as session:
        counter = 0
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                tile = fetch_tile(
                    provider,
                    geom["zoom"], tx, ty,
                    session=session,
                    cache_root=cache_root,
                    stats=stats,
                    counter=counter
                )
                ox = (tx - tx0) * TILE
                oy = (ty - ty0) * TILE
                stitched.paste(tile, (ox, oy))

                counter += 1
                if (counter % PROGRESS_EVERY_TILES == 0) or (counter == total_tiles):
                    pct = 100.0 * counter / total_tiles
                    log(f"{provider['id']}: {counter}/{total_tiles} tiles ({pct:5.1f}%)  "
                        f"dl={stats['downloaded']} cache={stats['cache_hits']} fail={stats['failed']}")

    cropped = stitched.crop((
        geom["crop_left"],
        geom["crop_top"],
        geom["crop_left"] + out_w,
        geom["crop_top"] + out_h
    ))

    if draw_rings:
        cropped = draw_range_rings(
            cropped,
            center_lat, center_lon,
            geom["zoom"], geom["px0"], geom["py0"],
            step_km=ring_step_km,
            max_km=ring_max_km,
            ring_color=ring_color,
            ring_width=1,
            draw_center_dot=True
        )

    if DRAW_TEST_MARKERS:
        cropped = draw_markers(
            cropped,
            zoom=geom["zoom"], px0=geom["px0"], py0=geom["py0"],
            markers=TEST_MARKERS,
            color=TEST_MARKER_COLOR,
            radius=TEST_MARKER_RADIUS,
            draw_labels=TEST_MARKER_LABELS
        )

    cropped.save(out_png, "PNG")
    log(f"Saved PNG: {out_png}")
    log(f"Summary '{provider['id']}': downloaded={stats['downloaded']} cache_hits={stats['cache_hits']} "
        f"failed={stats['failed']} blank={stats['blank_tiles']}")

    if CONVERT_TO_RGB565_HEADER:
        write_background565_h(out_png, out_hfile, out_w, out_h)
        log(f"OK: wrote {out_hfile}")

    return out_png, out_hfile


def make_multiple_maps(center_lat: float, center_lon: float, providers: list[dict],
                       range_km: float = 80, out_w: int = 480, out_h: int = 320,
                       out_dir: str = "out_maps",
                       draw_rings: bool = True, ring_step_km: int = 10, ring_max_km: int = 200,
                       ring_color=(0, 255, 0, 140)) -> tuple[dict, list[tuple[str, str, str]]]:
    ensure_safe_path(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    geom = compute_geometry(center_lat, center_lon, range_km, out_w, out_h)

    log("============================================================")
    log(f"Target center: lat={center_lat:.6f}, lon={center_lon:.6f}")
    log(f"Output: {out_w}x{out_h}  range_km={range_km}  => zoom z={geom['zoom']}")
    log(f"Top-left:     {geom['top_left_latlon']}")
    log(f"Bottom-right: {geom['bottom_right_latlon']}")
    log("============================================================")

    if ONLY_NO_LABELS:
        providers = [p for p in providers if p.get("nolabels", False)]
        log(f"ONLY_NO_LABELS=True -> providers used: {len(providers)}")

    outputs: list[tuple[str, str, str]] = []

    if CACHE_MODE == "temp":
        log("Tile cache: TEMP (auto-erased after run)")
        with tempfile.TemporaryDirectory(prefix="tile_cache_") as tmp_cache:
            for p in providers:
                provider_dir = os.path.join(out_dir, p["id"])
                map_png, header = render_one_provider(
                    p, geom,
                    out_w, out_h,
                    provider_dir,
                    center_lat, center_lon,
                    cache_root=tmp_cache,
                    draw_rings=draw_rings,
                    ring_step_km=ring_step_km,
                    ring_max_km=ring_max_km,
                    ring_color=ring_color
                )
                outputs.append((p["id"], map_png, header if CONVERT_TO_RGB565_HEADER else ""))
    else:
        cache_root = PERSISTENT_CACHE_ROOT
        os.makedirs(cache_root, exist_ok=True)
        log(f"Tile cache: {CACHE_MODE.upper()}  root='{cache_root}'")

        for p in providers:
            provider_dir = os.path.join(out_dir, p["id"])
            map_png, header = render_one_provider(
                p, geom,
                out_w, out_h,
                provider_dir,
                center_lat, center_lon,
                cache_root=cache_root,
                draw_rings=draw_rings,
                ring_step_km=ring_step_km,
                ring_max_km=ring_max_km,
                ring_color=ring_color
            )
            outputs.append((p["id"], map_png, header if CONVERT_TO_RGB565_HEADER else ""))

        if CACHE_MODE == "delete":
            log(f"Deleting cache folder: {cache_root}")
            shutil.rmtree(cache_root, ignore_errors=True)

    return geom, outputs


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

if __name__ == "__main__":

    OUT_DIR = "openstreet_maps"

    PROVIDERS = [
        # NO-LABELS (good for overlays)
        {
            "id": "carto_light_nolabels",
            "url": "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png",
            "subdomains": ["a", "b", "c", "d"],
            "ext": "png",
            "sleep": 0.2,
            "retries": 2,
            "nolabels": True
        },
        {
            "id": "carto_dark_nolabels",
            "url": "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png",
            "subdomains": ["a", "b", "c", "d"],
            "ext": "png",
            "sleep": 0.2,
            "retries": 2,
            "nolabels": True
        },
        {
            "id": "carto_voyager_nolabels",
            "url": "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}.png",
            "subdomains": ["a", "b", "c", "d"],
            "ext": "png",
            "sleep": 0.2,
            "retries": 2,
            "nolabels": True
        },
        {
            "id": "swisstopo_swissimage",
            "url": "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/3857/{z}/{x}/{y}.jpeg",
            "ext": "jpeg",
            "sleep": 0.2,
            "retries": 2,
            "nolabels": True
        },

        # Labeled
        {
            "id": "osm_standard",
            "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "ext": "png",
            "sleep": 0.2,
            "retries": 2
        },
        {
            "id": "opentopo",
            "url": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
            "subdomains": ["a", "b", "c"],
            "ext": "png",
            "sleep": 0.25,
            "retries": 2
        },
        {
            "id": "cyc_osm",
            "url": "https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png",
            "subdomains": ["a", "b", "c"],
            "ext": "png",
            "sleep": 0.25,
            "retries": 2
        },
        {
            "id": "swisstopo_pixelkarte_farbe",
            "url": "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-farbe/default/current/3857/{z}/{x}/{y}.jpeg",
            "ext": "jpeg",
            "sleep": 0.2,
            "retries": 2
        },
    ]

    geom, outputs = make_multiple_maps(
        CENTER_LAT, CENTER_LON,
        PROVIDERS,
        RANGE_KM,
        out_w=480, out_h=320,
        out_dir=OUT_DIR,
        draw_rings=False,
        ring_step_km=10,
        ring_max_km=200,
        ring_color=(0, 255, 0, 140)
    )

    print("\nGenerated outputs:")
    for pid, png_path, h_path in outputs:
        print(f" - {pid}")
        print(f"    PNG : {png_path}")
        if CONVERT_TO_RGB565_HEADER:
            print(f"    HDR : {h_path}")

    print('\n"Paste this into your ESP app Config.h file"\n')

    print("// ===================== Map geometry (MUST match your Python map) =====================")
    print(f"static const int    MAP_ZOOM = {geom['zoom']};")
    print(f"static const double MAP_PX0  = {geom['px0']};")
    print(f"static const double MAP_PY0  = {geom['py0']};")

    home_px, home_py = latlon_to_global_pixels(CENTER_LAT, CENTER_LON, geom["zoom"])
    sx = home_px - geom["px0"]
    sy = home_py - geom["py0"]
    print("\nSANITY CHECK")
    print("Home global px,py:", (home_px, home_py))
    print("Home screen x,y:", (sx, sy), "  (expected ~", (480 / 2, 320 / 2), ")")
