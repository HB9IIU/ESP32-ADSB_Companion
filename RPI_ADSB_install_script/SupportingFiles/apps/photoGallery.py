#!/usr/bin/env python3
"""
HB9IIU ADS-B Photo Gallery generator (Bootstrap)

Reads per-aircraft assets produced by imageBuilder:
  /var/www/html/hex/<HEX>.png
  /var/www/html/hex/<HEX>.json

Generates:
  /var/www/html/gallery.html

Change:
- Cards show ONLY a minimal "Info" table:
  country, selected hexdb fields, first_seen/last_seen formatted DD.MM.YY
- Label cleanup:
  OperatorFlagCode -> Operator ICAO
  RegisteredOwners -> Owner
  etc.
- first_seen/last_seen labels:
  First Seen / Last Seen
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =========================
# CONFIG (NO CLI ARGS)
# =========================

ASSET_DIR = Path("/var/www/html/hex")        # JSON files live here
JPG_DIR   = Path("/var/www/html/jpglarge")   # 800x480 gallery photos
OUT_HTML  = Path("/var/www/html/gallery.html")

TITLE = "HB9IIU ADS-B Photo Gallery"

JPG_URL_PREFIX = "/jpglarge/"
DISK_PATH_FOR_USAGE = Path("/")

INCLUDE_PLACEHOLDERS = True
INCLUDE_ERRORS       = True

CARD_IMG_HEIGHT_PX = 190
MAX_ITEMS: Optional[int] = None


# =========================
# DATA MODEL
# =========================
@dataclass
class AircraftItem:
    hex_id: str
    png_name: Optional[str]
    json_name: str
    country: str
    image_status: str
    image_source: str
    first_seen: Optional[int]
    last_seen: Optional[int]
    raw: Dict[str, Any]

    # for filtering/search
    search_country: str
    search_reg: str
    search_type: str
    search_owner: str
    search_mfr: str


# =========================
# HELPERS
# =========================
def _safe_int(v) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if x < 1024.0 or u == units[-1]:
            return f"{int(x)} {u}" if u == "B" else f"{x:.1f} {u}"
        x /= 1024.0
    return f"{n} B"


def fmt_ddmmyy(ts: Optional[int]) -> str:
    """Format unix seconds as DD.MM.YY (UTC)."""
    if ts is None:
        return "—"
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return dt.strftime("%d.%m.%y")
    except Exception:
        return "—"


def folder_size_bytes(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except Exception:
                pass
    return total


def disk_usage_summary(path: Path):
    du = shutil.disk_usage(str(path))
    return {
        "total": du.total,
        "used": du.used,
        "free": du.free,
        "used_pct": (du.used / du.total * 100.0) if du.total else 0.0,
    }


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(errors="ignore"))
    except Exception:
        return None


def escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )


def badge_class_for_status(status: str) -> str:
    status = (status or "").upper()
    if status == "OK":
        return "text-bg-success"
    if status == "NO_IMAGE":
        return "text-bg-secondary"
    if status == "ERROR":
        return "text-bg-danger"
    return "text-bg-warning"


def badge_class_for_source(source: str) -> str:
    s = (source or "").lower()
    if s == "hexdb":
        return "text-bg-primary"
    if s == "planespotters":
        return "text-bg-info"
    if s == "placeholder":
        return "text-bg-secondary"
    if s == "error":
        return "text-bg-danger"
    return "text-bg-dark"


def _join_url(prefix: str, name: str) -> str:
    if not prefix:
        return name
    if not prefix.endswith("/"):
        prefix = prefix + "/"
    return prefix + name.lstrip("/")


def _first_str(d: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


# =========================
# MINIMAL "INFO" TABLE
# =========================
INFO_HEXDB_KEYS = [
    "ICAOTypeCode",
    "Manufacturer",
    "ModeS",
    "OperatorFlagCode",
    "RegisteredOwners",
    "Registration",
    "Type",
]

INFO_LABELS = {
    "country": "Country",
    "ICAOTypeCode": "ICAO Type",
    "Manufacturer": "Manufacturer",
    "ModeS": "Mode-S",
    "OperatorFlagCode": "Operator ICAO",
    "RegisteredOwners": "Owner",
    "Registration": "Registration",
    "Type": "Type",
}


def build_info_table_minimal(raw: Dict[str, Any]) -> str:
    """
    Card shows ONLY:
      - country (top-level)
      - selected hexdb fields (with nicer labels)
      - First Seen / Last Seen as DD.MM.YY (UTC)
    Table title: "Info"
    """
    country = str(raw.get("country") or "—")

    hexdb = raw.get("hexdb") if isinstance(raw.get("hexdb"), dict) else {}
    assert isinstance(hexdb, dict)

    first_seen = fmt_ddmmyy(_safe_int(raw.get("first_seen")))
    last_seen  = fmt_ddmmyy(_safe_int(raw.get("last_seen")))

    rows: List[Tuple[str, str]] = []
    rows.append((INFO_LABELS.get("country", "country"), country))

    for k in INFO_HEXDB_KEYS:
        v = hexdb.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            val = "—"
        else:
            val = str(v).strip() if isinstance(v, str) else str(v)

        label = INFO_LABELS.get(k, k)
        rows.append((label, val))

    rows.append(("First Seen", first_seen))
    rows.append(("Last Seen", last_seen))

    parts: List[str] = []
    parts.append('<div class="table-responsive">')
    parts.append('<table class="table table-sm table-striped align-middle mb-0">')
    parts.append('<tbody>')
    parts.append('<tr class="table-light"><th colspan="2" class="small text-uppercase">Info</th></tr>')

    for k, v in rows:
        parts.append(
            f"<tr><td class=\"text-muted\" style=\"width:38%\">{escape_html(k)}</td>"
            f"<td style=\"width:62%\">{escape_html(v)}</td></tr>"
        )

    parts.append("</tbody></table></div>")
    return "\n".join(parts)


# =========================
# LOAD ITEMS
# =========================
def load_items(asset_dir: Path) -> List[AircraftItem]:
    items: List[AircraftItem] = []

    for json_path in sorted(asset_dir.glob("*.json")):
        data = read_json(json_path)
        if not isinstance(data, dict):
            continue

        hex_id = str(data.get("hex") or json_path.stem).lower()

        country = str(data.get("country") or "Unknown")
        image_status = str(data.get("image_status") or "UNKNOWN")
        image_source = str(data.get("image_source") or "unknown")

        png_name = data.get("image_jpg_large") or data.get("image_jpg")
        if not isinstance(png_name, str) or not png_name.strip():
            png_name = f"{hex_id}.jpg"

        png_path = JPG_DIR / png_name
        if not png_path.exists():
            png_name = None

        first_seen = _safe_int(data.get("first_seen"))
        last_seen = _safe_int(data.get("last_seen"))

        if image_status == "NO_IMAGE" and not INCLUDE_PLACEHOLDERS:
            continue
        if image_status == "ERROR" and not INCLUDE_ERRORS:
            continue

        hexdb = data.get("hexdb") if isinstance(data.get("hexdb"), dict) else {}
        assert isinstance(hexdb, dict)

        search_reg = _first_str(hexdb, "Registration", "registration", "Reg", "reg")
        search_type = _first_str(hexdb, "ICAOTypeCode", "ICAOType", "Type", "type")
        search_owner = _first_str(hexdb, "RegisteredOwners", "Operator", "operator")
        search_mfr = _first_str(hexdb, "Manufacturer", "manufacturer")

        items.append(
            AircraftItem(
                hex_id=hex_id,
                png_name=png_name,
                json_name=json_path.name,
                country=country,
                image_status=image_status,
                image_source=image_source,
                first_seen=first_seen,
                last_seen=last_seen,
                raw=data,
                search_country=country,
                search_reg=search_reg,
                search_type=search_type,
                search_owner=search_owner,
                search_mfr=search_mfr,
            )
        )

    items.sort(key=lambda x: (x.last_seen or 0), reverse=True)

    if MAX_ITEMS is not None:
        items = items[: MAX_ITEMS]

    return items


# =========================
# RENDER HTML
# =========================
def render_html(items: List[AircraftItem], stats: Dict[str, Any]) -> str:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    cards_html = []
    for it in items:
        hex_upper = it.hex_id.upper()
        country = escape_html(it.country or "Unknown")

        status_badge = f'<span class="badge {badge_class_for_status(it.image_status)} me-2">{escape_html(it.image_status)}</span>'
        source_badge = f'<span class="badge {badge_class_for_source(it.image_source)} me-2">{escape_html(it.image_source)}</span>'
        country_badge = f'<span class="badge text-bg-light border text-dark">{country}</span>'

        # Image + modal
        if it.png_name:
            img_url = _join_url(JPG_URL_PREFIX, it.png_name)
            img_src = escape_html(img_url)
            modal_id = f"m_{it.hex_id}"
            img_tag = f"""
              <a href="#" data-bs-toggle="modal" data-bs-target="#{modal_id}">
                <img src="{img_src}" class="card-img-top object-fit-cover" alt="{hex_upper}" loading="lazy"
                     style="height:{CARD_IMG_HEIGHT_PX}px;">
              </a>
            """
            modal = f"""
            <div class="modal fade" id="{modal_id}" tabindex="-1" aria-hidden="true">
              <div class="modal-dialog modal-dialog-centered modal-xl">
                <div class="modal-content bg-dark">
                  <div class="modal-header border-0">
                    <h5 class="modal-title text-white">{hex_upper}</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                  </div>
                  <div class="modal-body text-center">
                    <img src="{img_src}" class="img-fluid rounded" alt="{hex_upper}">
                    <div class="mt-3 text-white-50 small">Click outside or press ESC to close</div>
                  </div>
                </div>
              </div>
            </div>
            """
        else:
            img_tag = f"""
              <div class="d-flex align-items-center justify-content-center bg-secondary-subtle"
                   style="height:{CARD_IMG_HEIGHT_PX}px;">
                <div class="text-muted">No PNG file</div>
              </div>
            """
            modal = ""

        json_url = _join_url("/hex/", it.json_name)

        # Minimal info table (title = "Info")
        info_table = build_info_table_minimal(it.raw)

        card = f"""
        <div class="col">
          <div class="card h-100 shadow-sm gallery-card"
               data-hex="{escape_html(hex_upper)}"
               data-country="{escape_html((it.search_country or '').lower())}"
               data-reg="{escape_html((it.search_reg or '').lower())}"
               data-type="{escape_html((it.search_type or '').lower())}"
               data-owner="{escape_html((it.search_owner or '').lower())}"
               data-mfr="{escape_html((it.search_mfr or '').lower())}">
            {img_tag}
            <div class="card-body">
              <div class="d-flex align-items-start justify-content-between gap-2">
                <div>
                  <div class="h5 mb-1">Info</div>
                  <div class="small text-muted">{escape_html(hex_upper)}</div>
                </div>
                <div class="text-end">
                  {status_badge}
                  {source_badge}
                </div>
              </div>

              <div class="mt-2">
                {country_badge}
                <a class="ms-2 small link-secondary" href="{escape_html(json_url)}" target="_blank" rel="noopener">open JSON</a>
              </div>

              <hr class="my-3">

              {info_table}
            </div>
          </div>
        </div>
        {modal}
        """
        cards_html.append(card)

    cards_joined = "\n".join(cards_html)

    total_png = stats["total_png"]
    total_json = stats["total_json"]
    folder_size = stats["folder_size"]
    disk_total = stats["disk_total"]
    disk_used = stats["disk_used"]
    disk_free = stats["disk_free"]
    disk_used_pct = stats["disk_used_pct"]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_html(TITLE)}</title>

  <!-- Bootstrap 5 (CDN) -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"
        integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">

  <style>
    body {{
      background: radial-gradient(1200px 600px at 10% 0%, rgba(13,110,253,.12), transparent 60%),
                  radial-gradient(1200px 600px at 90% 0%, rgba(32,201,151,.10), transparent 60%),
                  #0b1220;
      color: #e9eef7;
    }}
    .navbar {{
      background: rgba(10, 18, 32, 0.85) !important;
      backdrop-filter: blur(8px);
    }}
    .hero {{
      padding: 2.2rem 0 1.2rem 0;
    }}
    .stat-card {{
      background: rgba(255,255,255,.06);
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 16px;
    }}
    .card {{
      background: rgba(255,255,255,.92);
      border: 0;
      border-radius: 16px;
      overflow: hidden;
    }}
    .card-body {{
      color: #0b1220;
    }}
    .object-fit-cover {{
      object-fit: cover;
    }}
    .search-wrap {{
      background: rgba(255,255,255,.06);
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 14px;
      padding: .75rem;
    }}
    .muted-top {{
      color: rgba(233,238,247,.75);
    }}
    .footer {{
      color: rgba(233,238,247,.65);
      padding: 2rem 0 3rem;
    }}
    table.table td, table.table th {{
      vertical-align: middle;
    }}
  </style>
</head>

<body>
<nav class="navbar navbar-expand-lg navbar-dark sticky-top">
  <div class="container">
    <a class="navbar-brand fw-semibold" href="#">
      ✈️ {escape_html(TITLE)}
    </a>
    <span class="navbar-text small muted-top">
      Updated: {escape_html(now_utc)}
    </span>
  </div>
</nav>

<div class="container hero">
  <div class="row align-items-end g-3">
    <div class="col-lg-7">
      <h1 class="display-6 mb-1">{escape_html(TITLE)}</h1>
      <div class="muted-top">
        Auto-generated from your readsb receiver assets in <code>{escape_html(str(ASSET_DIR))}</code>.
      </div>
    </div>

    <div class="col-lg-5">
      <div class="search-wrap">
        <label class="form-label small muted-top mb-2">Search (HEX / country / reg / type / owner / manufacturer)</label>
        <input id="searchBox" type="search" class="form-control form-control-lg"
               placeholder="e.g. 46B822, Greece, SX-, A21N, Aegean..." autocomplete="off">
        <div class="d-flex justify-content-between mt-2 small muted-top">
          <div><span id="matchCount">0</span> matches</div>
          <div><button class="btn btn-sm btn-outline-light" id="clearBtn" type="button">Clear</button></div>
        </div>
      </div>
    </div>
  </div>

  <div class="row g-3 mt-2">
    <div class="col-md-3">
      <div class="stat-card p-3 h-100">
        <div class="small muted-top">Pictures (JPEG)</div>
        <div class="h3 mb-0">{total_png}</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="stat-card p-3 h-100">
        <div class="small muted-top">Records (JSON)</div>
        <div class="h3 mb-0">{total_json}</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="stat-card p-3 h-100">
        <div class="small muted-top">Gallery folder size</div>
        <div class="h3 mb-0">{escape_html(human_bytes(folder_size))}</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="stat-card p-3 h-100">
        <div class="small muted-top">Disk used</div>
        <div class="h3 mb-0">{disk_used_pct:.1f}%</div>
        <div class="small muted-top">{escape_html(human_bytes(disk_used))} / {escape_html(human_bytes(disk_total))} used • {escape_html(human_bytes(disk_free))} free</div>
      </div>
    </div>
  </div>
</div>

<div class="container pb-4">
  <div class="d-flex align-items-center justify-content-between mb-3">
    <div class="muted-top small">
      Tip: click any picture to view it larger.
    </div>
    <div class="muted-top small">
      Showing newest first (by <code>last_seen</code>).
    </div>
  </div>

  <div id="grid" class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 row-cols-xxl-4 g-3">
    {cards_joined}
  </div>
</div>

<div class="container footer">
  <div class="small">
    Generated by HB9IIU <code>galleryMaker.py</code> • {escape_html(now_utc)}
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz"
        crossorigin="anonymous"></script>

<script>
(function() {{
  const box = document.getElementById('searchBox');
  const clearBtn = document.getElementById('clearBtn');
  const cards = Array.from(document.querySelectorAll('.gallery-card'));
  const matchCount = document.getElementById('matchCount');

  function norm(s) {{
    return (s || '').toString().toLowerCase().trim();
  }}

  function applyFilter() {{
    const q = norm(box.value);
    let shown = 0;
    for (const c of cards) {{
      const hay = [
        c.getAttribute('data-hex'),
        c.getAttribute('data-country'),
        c.getAttribute('data-reg'),
        c.getAttribute('data-type'),
        c.getAttribute('data-owner'),
        c.getAttribute('data-mfr'),
        c.textContent
      ].map(norm).join(' ');
      const ok = !q || hay.includes(q);
      c.closest('.col').style.display = ok ? '' : 'none';
      if (ok) shown++;
    }}
    matchCount.textContent = shown.toString();
  }}

  clearBtn.addEventListener('click', () => {{
    box.value = '';
    applyFilter();
    box.focus();
  }});

  box.addEventListener('input', applyFilter);

  matchCount.textContent = cards.length.toString();
}})();
</script>

</body>
</html>
"""


def main():
    print("HB9IIU ADS-B gallery generator")
    print(f"Assets : {ASSET_DIR}")
    print(f"Output : {OUT_HTML}")
    print(f"URL prefix for assets: {JPG_URL_PREFIX}")

    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    items = load_items(ASSET_DIR)

    total_png = sum(1 for p in JPG_DIR.glob("*.jpg") if p.is_file())
    total_json = sum(1 for p in ASSET_DIR.glob("*.json") if p.is_file())
    folder_size = folder_size_bytes(JPG_DIR) + folder_size_bytes(ASSET_DIR)

    du = disk_usage_summary(DISK_PATH_FOR_USAGE)

    stats = {
        "total_png": total_png,
        "total_json": total_json,
        "folder_size": folder_size,
        "disk_total": du["total"],
        "disk_used": du["used"],
        "disk_free": du["free"],
        "disk_used_pct": du["used_pct"],
    }

    html = render_html(items, stats)
    OUT_HTML.write_text(html, encoding="utf-8")

    print(f"Done. Wrote {OUT_HTML} ({len(html)} chars)")
    print("Open:")
    print("  http://<pi-ip>/gallery.html")


if __name__ == "__main__":
    main()
