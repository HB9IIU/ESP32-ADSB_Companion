# ICAO24 country mapping (full, embedded)
ICAO24_COUNTRIES = [
    (0x004000, 0x0047FF, "Zimbabwe"),
    (0x006000, 0x006FFF, "Mozambique"),
    (0x008000, 0x00FFFF, "South Africa"),
    (0x010000, 0x017FFF, "Egypt"),
    (0x018000, 0x01FFFF, "Libya"),
    (0x020000, 0x027FFF, "Morocco"),
    (0x028000, 0x02FFFF, "Tunisia"),
    (0x030000, 0x0307FF, "Botswana"),
    (0x032000, 0x032FFF, "Burundi"),
    (0x034000, 0x034FFF, "Cameroon"),
    (0x035000, 0x0357FF, "Comoros"),
    (0x036000, 0x036FFF, "Republic of the Congo"),
    (0x038000, 0x038FFF, "Côte d’Ivoire"),
    (0x03E000, 0x03EFFF, "Gabon"),
    (0x040000, 0x040FFF, "Ethiopia"),
    (0x042000, 0x042FFF, "Equatorial Guinea"),
    (0x044000, 0x044FFF, "Ghana"),
    (0x046000, 0x046FFF, "Guinea"),
    (0x048000, 0x0487FF, "Guinea-Bissau"),
    (0x04A000, 0x04A7FF, "Lesotho"),
    (0x04C000, 0x04CFFF, "Kenya"),
    (0x050000, 0x050FFF, "Liberia"),
    (0x054000, 0x054FFF, "Madagascar"),
    (0x058000, 0x058FFF, "Malawi"),
    (0x05A000, 0x05A7FF, "Maldives"),
    (0x05C000, 0x05CFFF, "Mali"),
    (0x05E000, 0x05E7FF, "Mauritania"),
    (0x060000, 0x0607FF, "Mauritius"),
    (0x062000, 0x062FFF, "Niger"),
    (0x064000, 0x064FFF, "Nigeria"),
    (0x068000, 0x068FFF, "Uganda"),
    (0x06A000, 0x06AFFF, "Qatar"),
    (0x06C000, 0x06CFFF, "Central African Republic"),
    (0x06E000, 0x06EFFF, "Rwanda"),
    (0x070000, 0x070FFF, "Senegal"),
    (0x074000, 0x0747FF, "Seychelles"),
    (0x076000, 0x0767FF, "Sierra Leone"),
    (0x078000, 0x078FFF, "Somalia"),
    (0x07A000, 0x07A7FF, "Eswatini"),
    (0x07C000, 0x07CFFF, "Sudan"),
    (0x080000, 0x080FFF, "Tanzania"),
    (0x084000, 0x084FFF, "Chad"),
    (0x088000, 0x088FFF, "Togo"),
    (0x08A000, 0x08AFFF, "Zambia"),
    (0x08C000, 0x08CFFF, "DR Congo"),
    (0x090000, 0x090FFF, "Angola"),
    (0x094000, 0x0947FF, "Benin"),
    (0x096000, 0x0967FF, "Cabo Verde"),
    (0x098000, 0x0987FF, "Djibouti"),
    (0x09A000, 0x09AFFF, "Gambia"),
    (0x09C000, 0x09CFFF, "Burkina Faso"),
    (0x09E000, 0x09E7FF, "São Tomé and Príncipe"),
    (0x0A0000, 0x0A7FFF, "Algeria"),
    (0x0A8000, 0x0A8FFF, "Bahamas"),
    (0x0AA000, 0x0AA7FF, "Barbados"),
    (0x0AB000, 0x0AB7FF, "Belize"),
    (0x0AC000, 0x0ADFFF, "Colombia"),
    (0x0AE000, 0x0AEFFF, "Costa Rica"),
    (0x0B0000, 0x0B0FFF, "Cuba"),
    (0x0B2000, 0x0B2FFF, "El Salvador"),
    (0x0B4000, 0x0B4FFF, "Guatemala"),
    (0x0B6000, 0x0B6FFF, "Guyana"),
    (0x0B8000, 0x0B8FFF, "Haiti"),
    (0x0BA000, 0x0BAFFF, "Honduras"),
    (0x0BC000, 0x0BC7FF, "Saint Vincent and the Grenadines"),
    (0x0BE000, 0x0BEFFF, "Jamaica"),
    (0x0C0000, 0x0C0FFF, "Nicaragua"),
    (0x0C2000, 0x0C2FFF, "Panama"),
    (0x0C4000, 0x0C4FFF, "Dominican Republic"),
    (0x0C6000, 0x0C6FFF, "Trinidad and Tobago"),
    (0x0C8000, 0x0C8FFF, "Suriname"),
    (0x0CA000, 0x0CA7FF, "Antigua and Barbuda"),
    (0x0CC000, 0x0CC7FF, "Grenada"),
    (0x0D0000, 0x0D7FFF, "Mexico"),
    (0x0D8000, 0x0DFFFF, "Venezuela"),
    (0x100000, 0x1FFFFF, "Russia"),
    (0x201000, 0x2017FF, "Namibia"),
    (0x202000, 0x2027FF, "Eritrea"),
    (0x300000, 0x33FFFF, "Italy"),
    (0x340000, 0x37FFFF, "Spain"),
    (0x380000, 0x3BFFFF, "France"),
    (0x3C0000, 0x3FFFFF, "Germany"),
    (0x400000, 0x43FFFF, "United Kingdom"),
    (0x440000, 0x447FFF, "Austria"),
    (0x448000, 0x44FFFF, "Belgium"),
    (0x450000, 0x457FFF, "Bulgaria"),
    (0x458000, 0x45FFFF, "Denmark"),
    (0x460000, 0x467FFF, "Finland"),
    (0x468000, 0x46FFFF, "Greece"),
    (0x470000, 0x477FFF, "Hungary"),
    (0x478000, 0x47FFFF, "Norway"),
    (0x480000, 0x487FFF, "Netherlands"),
    (0x488000, 0x48FFFF, "Poland"),
    (0x490000, 0x497FFF, "Portugal"),
    (0x498000, 0x49FFFF, "Czechia"),
    (0x4A0000, 0x4A7FFF, "Romania"),
    (0x4A8000, 0x4AFFFF, "Sweden"),
    (0x4B0000, 0x4B7FFF, "Switzerland"),
    (0x4B8000, 0x4BFFFF, "Turkey"),
    (0x4C0000, 0x4C7FFF, "Serbia"),
    (0x4C8000, 0x4C87FF, "Cyprus"),
    (0x4CA000, 0x4CAFFF, "Ireland"),
    (0x4CC000, 0x4CCFFF, "Iceland"),
    (0x4D0000, 0x4D07FF, "Luxembourg"),
    (0x4D2000, 0x4D27FF, "Malta"),
    (0x4D4000, 0x4D47FF, "Monaco"),
    (0x500000, 0x5007FF, "San Marino"),
    (0x501000, 0x5017FF, "Albania"),
    (0x501800, 0x501FFF, "Croatia"),
    (0x502800, 0x502FFF, "Latvia"),
    (0x503800, 0x503FFF, "Lithuania"),
    (0x504800, 0x504FFF, "Moldova"),
    (0x505800, 0x505FFF, "Slovakia"),
    (0x506800, 0x506FFF, "Slovenia"),
    (0x507800, 0x507FFF, "Uzbekistan"),
    (0x508000, 0x50FFFF, "Ukraine"),
    (0x510000, 0x5107FF, "Belarus"),
    (0x511000, 0x5117FF, "Estonia"),
    (0x512000, 0x5127FF, "North Macedonia"),
    (0x513000, 0x5137FF, "Bosnia and Herzegovina"),
    (0x514000, 0x5147FF, "Georgia"),
    (0x515000, 0x5157FF, "Tajikistan"),
    (0x516000, 0x5167FF, "Montenegro"),
    (0x600000, 0x6007FF, "Armenia"),
    (0x600800, 0x600FFF, "Azerbaijan"),
    (0x601000, 0x6017FF, "Kyrgyzstan"),
    (0x601800, 0x601FFF, "Turkmenistan"),
    (0x680000, 0x6807FF, "Bhutan"),
    (0x681000, 0x6817FF, "Micronesia, Federated States of"),
    (0x682000, 0x6827FF, "Mongolia"),
    (0x683000, 0x6837FF, "Kazakhstan"),
    (0x684000, 0x6847FF, "Palau"),
    (0x700000, 0x700FFF, "Afghanistan"),
    (0x702000, 0x702FFF, "Bangladesh"),
    (0x704000, 0x704FFF, "Myanmar"),
    (0x706000, 0x706FFF, "Kuwait"),
    (0x708000, 0x708FFF, "Laos"),
    (0x70A000, 0x70AFFF, "Nepal"),
    (0x70C000, 0x70C7FF, "Oman"),
    (0x70E000, 0x70EFFF, "Cambodia"),
    (0x710000, 0x717FFF, "Saudi Arabia"),
    (0x718000, 0x71FFFF, "South Korea"),
    (0x720000, 0x727FFF, "North Korea"),
    (0x728000, 0x72FFFF, "Iraq"),
    (0x730000, 0x737FFF, "Iran"),
    (0x738000, 0x73FFFF, "Israel"),
    (0x740000, 0x747FFF, "Jordan"),
    (0x748000, 0x74FFFF, "Lebanon"),
    (0x750000, 0x757FFF, "Malaysia"),
    (0x758000, 0x75FFFF, "Philippines"),
    (0x760000, 0x767FFF, "Pakistan"),
    (0x768000, 0x76FFFF, "Singapore"),
    (0x770000, 0x777FFF, "Sri Lanka"),
    (0x778000, 0x77FFFF, "Syria"),
    (0x789000, 0x789FFF, "Hong Kong"),
    (0x780000, 0x7BFFFF, "China"),
    (0x7C0000, 0x7FFFFF, "Australia"),
    (0x800000, 0x83FFFF, "India"),
    (0x840000, 0x87FFFF, "Japan"),
    (0x880000, 0x887FFF, "Thailand"),
    (0x888000, 0x88FFFF, "Viet Nam"),
    (0x890000, 0x890FFF, "Yemen"),
    (0x894000, 0x894FFF, "Bahrain"),
    (0x895000, 0x8957FF, "Brunei"),
    (0x896000, 0x896FFF, "United Arab Emirates"),
    (0x897000, 0x8977FF, "Solomon Islands"),
    (0x898000, 0x898FFF, "Papua New Guinea"),
    (0x899000, 0x8997FF, "Taiwan"),
    (0x8A0000, 0x8A7FFF, "Indonesia"),
    (0x900000, 0x9007FF, "Marshall Islands"),
    (0x901000, 0x9017FF, "Cook Islands"),
    (0x902000, 0x9027FF, "Samoa"),
    (0xA00000, 0xAFFFFF, "United States"),
    (0xC00000, 0xC3FFFF, "Canada"),
    (0xC80000, 0xC87FFF, "New Zealand"),
    (0xC88000, 0xC88FFF, "Fiji"),
    (0xC8A000, 0xC8A7FF, "Nauru"),
    (0xC8C000, 0xC8C7FF, "Saint Lucia"),
    (0xC8D000, 0xC8D7FF, "Tonga"),
    (0xC8E000, 0xC8E7FF, "Kiribati"),
    (0xC90000, 0xC907FF, "Vanuatu"),
    (0xC91000, 0xC917FF, "Andorra"),
    (0xC92000, 0xC927FF, "Dominica"),
    (0xC93000, 0xC937FF, "Saint Kitts and Nevis"),
    (0xC94000, 0xC947FF, "South Sudan"),
    (0xC95000, 0xC957FF, "Timor-Leste"),
    (0xC97000, 0xC977FF, "Tuvalu"),
    (0xE00000, 0xE3FFFF, "Argentina"),
    (0xE40000, 0xE7FFFF, "Brazil"),
    (0xE80000, 0xE80FFF, "Chile"),
    (0xE84000, 0xE84FFF, "Ecuador"),
    (0xE88000, 0xE88FFF, "Paraguay"),
    (0xE8C000, 0xE8CFFF, "Peru"),
    (0xE90000, 0xE90FFF, "Uruguay"),
    (0xE94000, 0xE94FFF, "Bolivia"),
    (0xF00000, 0xF07FFF, "ICAO (temporary)"),
    (0xF09000, 0xF097FF, "ICAO (special use)"),
    (0xFFFFFF, 0xFFFFFF, "Unknown"),
]

ALIASES = {
    "DR Congo": "Congo, The Democratic Republic of the",
    "Republic of the Congo": "Congo",
    "Côte d’Ivoire": "Cote d'Ivoire",
    "Cabo Verde": "Cabo Verde",  # pycountry supports; keep
    "Viet Nam": "Viet Nam",
    "Eswatini": "Eswatini",
    "United Kingdom": "United Kingdom",
    "Russia": "Russian Federation",
    "South Korea": "Korea, Republic of",
    "North Korea": "Korea, Democratic People's Republic of",
    "Syria": "Syrian Arab Republic",
    "Laos": "Lao People's Democratic Republic",
    "Taiwan": "Taiwan, Province of China",
    "Tanzania": "Tanzania, United Republic of",
    "Iran": "Iran, Islamic Republic of",
    "Moldova": "Moldova, Republic of",
    "Bolivia": "Bolivia, Plurinational State of",
    "Venezuela": "Venezuela, Bolivarian Republic of",
    "Palestine": "Palestine, State of",
    "Hong Kong": "Hong Kong",
    "Micronesia, Federated States of": "Micronesia, Federated States of",
    "São Tomé and Príncipe": "Sao Tome and Principe",
    "Turkey": "Türkiye",
    "Brunei": "Brunei Darussalam",
}





# Restore correct ICAO24 hex_id to country mapping
def icao24_to_country(hex_id: str) -> str | None:
    try:
        n = int(hex_id, 16)
    except Exception:
        return None
    for start, end, country in ICAO24_COUNTRIES:
        if start <= n <= end:
            return country
    return None



#!/usr/bin/env python3
import json
import math
import time
from pathlib import Path
from io import BytesIO
import pycountry
import requests
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# CONFIGURATION
# ============================================================

AIRCRAFT_JSON = Path("/run/readsb/aircraft.json")
RECEIVER_JSON = Path("/run/readsb/receiver.json")

OUT_DIR = Path("/var/www/html/hex")
JPG_OUT_DIR = Path("/var/www/html/jpg")
JPG_LARGE_OUT_DIR = Path("/var/www/html/jpglarge")

POLL_SECONDS = 5
MAX_DISTANCE_KM = 1000.0
LAST_SEEN_WRITE_SEC = 60

TARGET_SIZE = (480, 320)
LARGE_TARGET_SIZE = (800, 480)
BANNER_SCAN_WIDTH = 20
BANNER_CROP_MIN_HEIGHT = 6

HEXDB_INFO_URL = "https://hexdb.io/api/v1/aircraft/{hex}"
HEXDB_IMAGE_URL = "https://hexdb.io/hex-image?hex={hex}"

# Optional fallback (no CLI flags, no retry logic)
PLANESPOTTERS_FALLBACK_ENABLED = True
PLANESPOTTERS_API_URL = "https://api.planespotters.net/pub/photos"
PLANESPOTTERS_USER_AGENT = (
    "adsb-image-builder/1.0 "
    "(+https://github.com/HB9IIU/ESP32-ADSB_Companion)"
)

# Set your receiver coordinates here (recommended).
# If left as None, the script will try to read them from receiver.json.
RX_LAT = None
RX_LON = None

# ============================================================
# UTILS
# ============================================================
def sanitize_name(s: str) -> str:
    return s.strip().replace("’", "'")


def country_to_iso2(name: str) -> str | None:
    name = sanitize_name(name)
    lookup = ALIASES.get(name, name)
    try:
        c = pycountry.countries.lookup(lookup)
        return c.alpha_2.lower()
    except LookupError:
        return None





def load_receiver_latlon():
    if not RECEIVER_JSON.exists():
        print(f"RX: {RECEIVER_JSON} not found")
        return None, None

    try:
        data = json.loads(RECEIVER_JSON.read_text(errors="ignore"))
    except Exception as e:
        print(f"RX: failed to read/parse {RECEIVER_JSON}: {e}")
        return None, None

    lat = data.get("lat")
    lon = data.get("lon")

    if lat is None or lon is None:
        print(f"RX: lat/lon missing in {RECEIVER_JSON}")
        return None, None

    try:
        lat = float(lat)
        lon = float(lon)
    except Exception:
        print(f"RX: lat/lon not numeric in {RECEIVER_JSON}: lat={lat!r} lon={lon!r}")
        return None, None

    return lat, lon


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) *
         math.sin(dlon / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))




def detect_bottom_banner_height_from_img(img):
    """
    Detect a uniform-colour watermark/banner at the bottom of an image.

    Scans a centered horizontal strip (BANNER_SCAN_WIDTH pixels wide) from
    the bottom row upward. Counts consecutive rows where every pixel in the
    strip shares the same colour — that run is the estimated banner height.

    Works directly on an already-open PIL Image (no disk I/O needed).
    Returns (width, height, banner_height).
    """
    img = img.convert("RGB")
    width, height = img.size
    if width <= 0 or height <= 0:
        return width, height, 0
    scan_width = min(BANNER_SCAN_WIDTH, width)
    x_start = max(0, (width - scan_width) // 2)
    x_end = x_start + scan_width
    pixels = img.load()
    banner_height = 0
    for y in range(height - 1, -1, -1):
        first_pixel = pixels[x_start, y]
        if all(pixels[x, y] == first_pixel for x in range(x_start, x_end)):
            banner_height += 1
        else:
            break
    return width, height, banner_height


def build_letterboxed_image(img, target_size):
    """
    Fit the image inside target_size without cropping, then centre it on a
    black canvas (letterbox / pillarbox).  Returns:
        (canvas_img, fitted_width, fitted_height, offset_x, offset_y)
    """
    from PIL import Image, ImageOps
    fitted = ImageOps.contain(img, target_size, method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", target_size, (0, 0, 0))
    offset_x = max(0, (target_size[0] - fitted.width) // 2)
    offset_y = max(0, (target_size[1] - fitted.height) // 2)
    canvas.paste(fitted, (offset_x, offset_y))
    return canvas, fitted.width, fitted.height, offset_x, offset_y



def make_no_pic_image(hex_id, registration):
    img = Image.new("RGB", TARGET_SIZE, (30, 30, 30))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    lines = [
        "NO PICTURE AVAILABLE",
        f"HEX: {hex_id.upper()}",
    ]
    if registration:
        lines.append(f"REG: {registration}")

    y = TARGET_SIZE[1] // 2 - len(lines) * 10
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text(((TARGET_SIZE[0] - w) // 2, y),
                  line, fill=(220, 220, 220), font=font)
        y += 20

    return img


def fetch_hexdb_info(hex_id):
    url = HEXDB_INFO_URL.format(hex=hex_id)
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        raise RuntimeError("hexdb info status " + str(r.status_code))
    return r.json()


def fetch_hexdb_image_url(hex_id):
    url = HEXDB_IMAGE_URL.format(hex=hex_id)
    r = requests.get(url, timeout=10)
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise RuntimeError("hexdb imageurl status " + str(r.status_code))
    image_url = r.text.strip()
    if not image_url.startswith("http"):
        raise RuntimeError("hexdb imageurl returned non-url")
    return image_url


def fetch_jpeg(image_url):
    r = requests.get(image_url, timeout=20)
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError("jpeg download failed")
    return r.content


def _first_str(d, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def fetch_planespotters_image_url(hex_id, registration=None, icao_type=None):
    """Best-effort PlaneSpotters thumbnail URL lookup.

    Returns a URL string or None.
    """
    url = f"{PLANESPOTTERS_API_URL}/hex/{hex_id.upper()}"
    params = {}
    if registration:
        params["reg"] = registration
    if icao_type:
        params["icaoType"] = icao_type

    r = requests.get(
        url,
        params=params,
        timeout=15,
        headers={
            "User-Agent": PLANESPOTTERS_USER_AGENT,
            "Accept": "application/json",
        },
    )
    if r.status_code != 200:
        detail = r.text.strip().replace("\n", " ")[:300]
        raise RuntimeError(
            f"planespotters api status {r.status_code}"
            + (f": {detail}" if detail else "")
        )

    data = r.json()
    photos = data.get("photos")
    if not isinstance(photos, list):
        return None

    for p in photos:
        if not isinstance(p, dict):
            continue

        image_url = None

        # 1) Prefer the largest thumbnail PlaneSpotters provides
        tlarge = p.get("thumbnail_large")
        if isinstance(tlarge, dict):
            image_url = _first_str(tlarge, ("src", "url"))

        # 2) Fallback to the small thumbnail
        if not image_url:
            tsmall = p.get("thumbnail")
            if isinstance(tsmall, dict):
                image_url = _first_str(tsmall, ("src", "url"))

        # 3) Last-resort fallbacks (varies by API / older formats)
        if not image_url:
            image_url = _first_str(p, ("src", "url", "thumbnail_url", "thumbnailSrc"))

        if image_url and image_url.startswith("http"):
            return image_url


    return None


def read_json(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)


def write_bytes(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def render_and_write_jpeg(img, target_size, output_path, quality=85):
    """Letterbox an image to an exact size and write it atomically as JPEG."""
    rendered, fitted_w, fitted_h, off_x, off_y = build_letterboxed_image(
        img, target_size
    )
    buf = BytesIO()
    rendered.save(buf, format="JPEG", quality=quality, optimize=True)
    jpg_bytes = buf.getvalue()
    write_bytes(output_path, jpg_bytes)
    return fitted_w, fitted_h, off_x, off_y, len(jpg_bytes)


def load_last_seen_cache():
    cache = {}
    for json_file in OUT_DIR.glob("*.json"):
        try:
            data = json.loads(json_file.read_text())
        except Exception:
            continue
        hex_id = data.get("hex", json_file.stem)
        last_seen = data.get("last_seen")
        first_seen = data.get("first_seen")
        cache[hex_id] = {
            "last_seen": last_seen,
            "first_seen": first_seen,
        }
    return cache


# ============================================================
# MAIN LOOP
# ============================================================

def main():
    print("ADS-B hex asset builder")
    print(f"Watching: {AIRCRAFT_JSON}")
    print(f"Output  : {OUT_DIR}")
    print(f"Max dist: {MAX_DISTANCE_KM} km")
    print(f"Poll    : {POLL_SECONDS}s")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    last_seen_cache = load_last_seen_cache()

    while True:
        if not AIRCRAFT_JSON.exists():
            print("aircraft.json not found yet, waiting...")
            time.sleep(POLL_SECONDS)
            continue

        try:
            data = json.loads(AIRCRAFT_JSON.read_text())
        except Exception as e:
            print(f"Failed to parse aircraft.json: {e}")
            time.sleep(POLL_SECONDS)
            continue

        aircraft = data.get("aircraft", [])
        print(f"Loaded {len(aircraft)} aircraft")

        rx_lat, rx_lon = (RX_LAT, RX_LON)
        if rx_lat is None or rx_lon is None:
            rx_lat, rx_lon = load_receiver_latlon()

        for a in aircraft:
            hex_id = a.get("hex")
            if not hex_id:
                continue

            print(f"HEX {hex_id} seen")

            a_lat = a.get("lat")
            a_lon = a.get("lon")

            dist = None
            if rx_lat is not None and rx_lon is not None and a_lat is not None and a_lon is not None:
                try:
                    dist = haversine_km(rx_lat, rx_lon, float(a_lat), float(a_lon))
                except Exception:
                    dist = None

            if dist is not None and dist > MAX_DISTANCE_KM:
                print(f"  skip: dist={dist:.1f}km > {MAX_DISTANCE_KM}km")
                continue

            now = int(time.time())

            json_path = OUT_DIR / f"{hex_id}.json"
            jpg_path = JPG_OUT_DIR / f"{hex_id}.jpg"
            jpg_large_path = JPG_LARGE_OUT_DIR / f"{hex_id}.jpg"

            record = read_json(json_path) or {}
            cache_entry = last_seen_cache.get(hex_id, {})
            first_seen = cache_entry.get("first_seen") or record.get("first_seen") or now
            prev_last_seen = cache_entry.get("last_seen") or record.get("last_seen")

            # Always initialize image_source so cached entries don't crash.
            image_source = record.get("image_source") or "unknown"

            hexdb = record.get("hexdb")
            if not isinstance(hexdb, dict):
                try:
                    hexdb = fetch_hexdb_info(hex_id)
                    print(f"  hexdb info OK for {hex_id}")
                except Exception as e:
                    print(f"hexdb info failed for {hex_id}: {e}")
                    hexdb = record.get("hexdb") or {}

            image_status = record.get("image_status") or "UNKNOWN"
            files_ready = jpg_path.exists() and jpg_large_path.exists()
            if files_ready and image_status in ("OK", "NO_IMAGE"):
                pass
            else:
                try:
                    image_url = None
                    image_source = None

                    # 1) Prefer HexDB because it usually provides larger images.
                    try:
                        image_url = fetch_hexdb_image_url(hex_id)
                        if image_url:
                            image_source = "hexdb"
                            print("  image source: hexdb")
                    except Exception as e:
                        print(f"  hexdb image lookup failed for {hex_id}: {e}")

                    # 2) Fallback to Planespotters for wider coverage.
                    if not image_url and PLANESPOTTERS_FALLBACK_ENABLED:
                        reg = a.get("r") or a.get("reg") or hexdb.get("Registration")
                        icao_type = a.get("t") or a.get("type") or a.get("icaoType")
                        try:
                            ps_url = fetch_planespotters_image_url(hex_id, reg, icao_type)
                            if (not ps_url) and (reg or icao_type):
                                # Some filters can eliminate otherwise valid photos; retry bare
                                ps_url = fetch_planespotters_image_url(hex_id, None, None)
                            if ps_url:
                                image_url = ps_url
                                image_source = "planespotters"
                                print("  image source: planespotters (fallback)")
                        except Exception as e:
                            print(f"  planespotters lookup failed for {hex_id}: {e}")

                    if image_url is None:
                        print(f"  no image for {hex_id}, creating placeholder")
                        img = make_no_pic_image(hex_id, hexdb.get("Registration"))
                        image_status = "NO_IMAGE"
                        image_source = "placeholder"
                    else:
                        print(f"  image url: {image_url}")
                        print(f"  image source: {image_source}")
                        jpeg = fetch_jpeg(image_url)
                        img = Image.open(BytesIO(jpeg)).convert("RGB")
                        image_status = "OK"

                    orig_w, orig_h = img.size

                    # Banner detection on the current image (not a previously saved file)
                    img_width, img_height, banner_height = detect_bottom_banner_height_from_img(img)
                    print(f"  [BANNER] {img_width}x{img_height} banner height {banner_height}")
                    crop_bottom = 0
                    if BANNER_CROP_MIN_HEIGHT <= banner_height < img_height:
                        crop_bottom = banner_height
                        img = img.crop((0, 0, img_width, img_height - crop_bottom))
                        print(f"  [CROP] cropping bottom {crop_bottom}px -> {img_width}x{img_height - crop_bottom}")
                    else:
                        print(f"  [CROP] skipped (threshold={BANNER_CROP_MIN_HEIGHT})")

                    JPG_OUT_DIR.mkdir(parents=True, exist_ok=True)
                    JPG_LARGE_OUT_DIR.mkdir(parents=True, exist_ok=True)

                    fitted_w, fitted_h, off_x, off_y, byte_count = (
                        render_and_write_jpeg(img, TARGET_SIZE, jpg_path)
                    )
                    print(
                        f"  letterbox small: {orig_w}x{orig_h} -> "
                        f"fitted={fitted_w}x{fitted_h} offsets={off_x},{off_y}"
                    )
                    print(
                        f"  wrote: {jpg_path} "
                        f"({TARGET_SIZE[0]}x{TARGET_SIZE[1]}, {byte_count} bytes)"
                    )

                    fitted_w, fitted_h, off_x, off_y, byte_count = (
                        render_and_write_jpeg(
                            img, LARGE_TARGET_SIZE, jpg_large_path
                        )
                    )
                    print(
                        f"  letterbox large: {orig_w}x{orig_h} -> "
                        f"fitted={fitted_w}x{fitted_h} offsets={off_x},{off_y}"
                    )
                    print(
                        f"  wrote: {jpg_large_path} "
                        f"({LARGE_TARGET_SIZE[0]}x{LARGE_TARGET_SIZE[1]}, "
                        f"{byte_count} bytes)"
                    )
                except Exception as e:
                    print(f"image build failed for {hex_id}: {e}")
                    image_status = "ERROR"
                    image_source = "error"



            country = icao24_to_country(hex_id)
            print(f"  debug: extracted country for {hex_id} is {country!r}")
            if not country:
                country = "Unknown"
            if country != "Unknown":
                iso2 = country_to_iso2(country)
            else:
                iso2 = None

            record = {
                "hex": hex_id,
                "country": country,
                "first_seen": first_seen,
                "last_seen": now,
                "hexdb": hexdb,
                "image_status": image_status,
                "image_source": image_source,
                "image_jpg": jpg_path.name,
                "image_jpg_large": jpg_large_path.name,
                "flag_rgb565": (iso2 + ".rgb565") if iso2 else None
            }

            if (not json_path.exists()) or (prev_last_seen is None) or ((now - prev_last_seen) >= LAST_SEEN_WRITE_SEC):
                write_json(json_path, record)
                last_seen_cache[hex_id] = {"last_seen": now, "first_seen": first_seen}
            else:
                print(f"  skip json write: last_seen {now - prev_last_seen}s ago")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
