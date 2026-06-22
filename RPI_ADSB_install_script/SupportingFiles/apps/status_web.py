#!/home/pi/pythonApps/venv/bin/python3
"""
pi-status-web  –  HB9IIU ADS-B station system dashboard.
Served on port 8080 by pi-status-web.service.
"""
import os
import re
import time
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# ── Config ──────────────────────────────────────────────────────
BACKUP_FILE = Path("/var/lib/adsb-stats/state-backup.json")
VENV_PYTHON = Path(os.environ.get("VENV_DIR", "/home/pi/pythonApps/venv")) / "bin" / "python3"
APPS_DIR    = Path(os.environ.get("APPS_DIR",  "/home/pi/pythonApps"))

SERVICES = [
    "readsb.service",
    "tar1090.service",
    "rtl-biast.service",
    "image-builder.service",
    "pi-status-web.service",
    "route-finder.service",
    "smbd.service",
    "nmbd.service",
]

TIMERS = [
    "adsb-stats.timer",
    "photo-gallery.timer",
]

REFRESH_MS = 5000

# ── System helpers ───────────────────────────────────────────────

def get_uptime() -> str:
    try:
        secs = float(Path("/proc/uptime").read_text().split()[0])
        d = int(secs // 86400)
        h = int((secs % 86400) // 3600)
        m = int((secs % 3600) // 60)
        if d:   return f"{d}d {h}h {m}m"
        if h:   return f"{h}h {m}m"
        return  f"{m}m"
    except Exception:
        return "?"

def get_load() -> dict:
    try:
        l1, l5, l15 = os.getloadavg()
        return {"load1": f"{l1:.2f}", "load5": f"{l5:.2f}", "load15": f"{l15:.2f}"}
    except Exception:
        return {"load1": "?", "load5": "?", "load15": "?"}

def get_disk() -> dict:
    try:
        u = shutil.disk_usage("/")
        gb = 1024 ** 3
        pct = round(u.used / u.total * 100)
        return {
            "total": f"{u.total / gb:.1f} GB",
            "used":  f"{u.used  / gb:.1f} GB",
            "free":  f"{u.free  / gb:.1f} GB",
            "pct":   pct,
        }
    except Exception:
        return {"total": "?", "used": "?", "free": "?", "pct": 0}

def get_mem() -> dict:
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            info[k.strip()] = int(v.strip().split()[0])   # kB
        total = info["MemTotal"]
        avail = info["MemAvailable"]
        used  = total - avail
        pct   = round(used / total * 100)
        def mb(kb): return f"{kb // 1024} MB"
        return {"total": mb(total), "used": mb(used), "free": mb(avail), "pct": pct}
    except Exception:
        return {"total": "?", "used": "?", "free": "?", "pct": 0}

def get_cpu_temp() -> str:
    try:
        raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()
        return f"{int(raw) / 1000:.1f}"   # °C as string, no unit (added in JS)
    except Exception:
        return "?"

# ── Systemd helpers ─────────────────────────────────────────────

def systemctl_show(unit: str, props: list) -> dict:
    try:
        out = subprocess.check_output(
            ["systemctl", "show"] + sum([["-p", p] for p in props], []) + [unit],
            text=True, stderr=subprocess.DEVNULL,
        )
    except Exception:
        return {}
    d = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k] = v
    return d

def unit_info(unit: str) -> dict:
    d = systemctl_show(unit, ["ActiveState", "UnitFileState", "ActiveEnterTimestamp"])
    active  = d.get("ActiveState",         "unknown")
    enabled = d.get("UnitFileState",       "unknown")
    since   = d.get("ActiveEnterTimestamp", "") or ""
    # strip the long timestamp to HH:MM:SS
    if since:
        m = re.search(r'\d{2}:\d{2}:\d{2}', since)
        since = m.group(0) if m else since[-8:]
    return {"name": unit, "active": active, "enabled": enabled, "since": since}

def _usec_to_relative(usec_str: str) -> str:
    """Convert NextElapseUSecRealtime (µs epoch) to a human relative string."""
    try:
        usec = int(usec_str)
        if usec == 0:
            return "-"
        delta = (usec / 1_000_000) - time.time()
        if delta <= 0:
            return "now"
        if delta < 60:
            return f"{int(delta)}s"
        if delta < 3600:
            return f"{int(delta // 60)}m {int(delta % 60)}s"
        return f"{int(delta // 3600)}h {int((delta % 3600) // 60)}m"
    except Exception:
        return "-"

def timer_info(timer: str) -> dict:
    props = ["ActiveState", "UnitFileState", "NextElapseUSecRealtime", "Triggers"]
    d = systemctl_show(timer, props)
    target = (d.get("Triggers", "") or "").strip()
    next_t  = _usec_to_relative(d.get("NextElapseUSecRealtime", "0"))
    # last result comes from the triggered service
    last_result = ""
    if target:
        sd = systemctl_show(target, ["Result"])
        last_result = sd.get("Result", "") or ""
    return {
        "name":        timer,
        "active":      d.get("ActiveState",   "unknown"),
        "enabled":     d.get("UnitFileState", "unknown"),
        "next":        next_t,
        "target":      target,
        "last_result": last_result,
    }

# ── HTML ────────────────────────────────────────────────────────

HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HB9IIU · System Status</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" />
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet" />
  <style>
    :root {
      --green:  #00ff88;
      --amber:  #ffa040;
      --red:    #ff4455;
      --card-bg:#0d1117;
      --border: #1e3a2e;
      --muted:  #8b949e;
      --dim:    #30363d;
    }
    body {
      background: #060a06;
      color: #c9d1d9;
      font-family: system-ui, 'Segoe UI', sans-serif;
      min-height: 100vh;
    }
    /* Header */
    .site-header { background:#080d08; border-bottom:1px solid var(--border); }
    .callsign {
      font-family:'Courier New',monospace;
      color:var(--green); font-size:1.25rem;
      font-weight:700; letter-spacing:3px;
    }
    .clock {
      font-family:'Courier New',monospace;
      color:var(--amber); font-size:.95rem;
    }
    .radar-dot {
      width:9px; height:9px; border-radius:50%;
      background:var(--green); display:inline-block;
      animation:rpulse 2s ease-in-out infinite;
    }
    @keyframes rpulse {
      0%,100%{ box-shadow:0 0 0 0   rgba(0,255,136,.5); }
      50%    { box-shadow:0 0 0 8px rgba(0,255,136,0);  }
    }
    /* Back link */
    .back-link { color:var(--muted); font-size:.82rem; text-decoration:none; }
    .back-link:hover { color:var(--green); }
    /* Cards */
    .scard {
      background:var(--card-bg);
      border:1px solid var(--border);
      border-radius:12px; padding:1.2rem;
    }
    .scard-title {
      color:#e6edf3; font-weight:600;
      font-size:.8rem; text-transform:uppercase;
      letter-spacing:1.5px; margin-bottom:.9rem;
    }
    /* Metric row */
    .metric-label { color:var(--muted); font-size:.78rem; }
    .metric-value {
      font-family:'Courier New',monospace;
      color:#e6edf3; font-size:.95rem; font-weight:600;
    }
    .metric-value.green { color:var(--green); }
    .metric-value.amber { color:var(--amber); }
    .metric-value.red   { color:var(--red);   }
    /* Progress bar */
    .pbar-wrap {
      height:6px; border-radius:3px;
      background:#1a2a1a; margin-top:4px;
    }
    .pbar {
      height:6px; border-radius:3px;
      background:var(--green);
      transition: width .6s ease;
    }
    .pbar.warn  { background:var(--amber); }
    .pbar.crit  { background:var(--red);   }
    /* Status dot */
    .sdot {
      width:9px; height:9px; border-radius:50%;
      display:inline-block; flex-shrink:0;
      background:#333; margin-right:6px;
    }
    .sdot.ok  { background:var(--green); box-shadow:0 0 5px rgba(0,255,136,.5); }
    .sdot.err { background:var(--red);   box-shadow:0 0 5px rgba(255,68,85,.4); }
    .sdot.dim { background:#555; }
    /* Tables */
    .status-table { width:100%; border-collapse:collapse; font-size:.83rem; }
    .status-table th {
      color:var(--dim); font-size:.72rem;
      text-transform:uppercase; letter-spacing:1px;
      padding:4px 8px; border-bottom:1px solid var(--border);
      font-weight:500;
    }
    .status-table td {
      padding:7px 8px; border-bottom:1px solid #111a11;
      vertical-align:middle;
    }
    .status-table tr:last-child td { border-bottom:none; }
    .mono { font-family:'Courier New',monospace; }
    .unit-name { color:#c9d1d9; }
    .t-muted { color:var(--muted); }
    .t-green { color:var(--green); font-weight:600; }
    .t-amber { color:var(--amber); }
    .t-red   { color:var(--red);  font-weight:600; }
    /* Pill */
    .pill {
      display:inline-block; padding:1px 8px;
      border-radius:999px; font-size:.72rem;
      border:1px solid var(--dim); color:var(--muted);
    }
    .pill.ok  { border-color:var(--green); color:var(--green); }
    .pill.bad { border-color:var(--red);   color:var(--red);   }
    /* Delete button */
    .del-btn {
      background:#1a0a0a; border:1px solid #3a1e1e;
      color:var(--red); border-radius:8px;
      padding:6px 14px; font-size:.8rem; cursor:pointer;
      transition:background .15s;
    }
    .del-btn:hover { background:#2a1010; }
    /* Section label */
    .section-label {
      color:var(--muted); font-size:.75rem;
      text-transform:uppercase; letter-spacing:1.5px;
    }
    footer { color:var(--dim); font-size:.75rem; border-top:1px solid #0d1117; }
  </style>
</head>
<body>

<!-- Header -->
<header class="site-header py-3 px-3 px-md-4 mb-4">
  <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
    <div class="d-flex align-items-center gap-3">
      <span class="radar-dot"></span>
      <span class="callsign">HB9IIU</span>
      <span class="text-secondary d-none d-sm-inline" style="font-size:.82rem;">System Status</span>
    </div>
    <div class="d-flex align-items-center gap-3">
      <a href="/" class="back-link"><i class="bi bi-arrow-left me-1"></i>Dashboard</a>
      <span class="clock" id="clock">--:--:-- UTC</span>
    </div>
  </div>
</header>

<main class="container-fluid px-3 px-md-4 pb-5" style="max-width:1100px;">

  <!-- ── Row 1: system metrics ── -->
  <div class="row g-3 mb-3">

    <!-- Time & Uptime -->
    <div class="col-12 col-sm-6 col-lg-3">
      <div class="scard h-100">
        <div class="scard-title"><i class="bi bi-clock me-1"></i>System Time</div>
        <div class="metric-label">Local time</div>
        <div class="metric-value green mono" id="s-time">—</div>
        <div class="metric-label mt-2">Uptime</div>
        <div class="metric-value" id="s-uptime">—</div>
      </div>
    </div>

    <!-- CPU Load -->
    <div class="col-12 col-sm-6 col-lg-3">
      <div class="scard h-100">
        <div class="scard-title"><i class="bi bi-cpu me-1"></i>CPU Load</div>
        <div class="d-flex justify-content-between align-items-baseline">
          <div>
            <div class="metric-label">1 min</div>
            <div class="metric-value" id="s-load1">—</div>
          </div>
          <div>
            <div class="metric-label">5 min</div>
            <div class="metric-value" id="s-load5">—</div>
          </div>
          <div>
            <div class="metric-label">15 min</div>
            <div class="metric-value" id="s-load15">—</div>
          </div>
          <div>
            <div class="metric-label">Temp</div>
            <div class="metric-value" id="s-temp">—</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Memory -->
    <div class="col-12 col-sm-6 col-lg-3">
      <div class="scard h-100">
        <div class="scard-title"><i class="bi bi-memory me-1"></i>Memory</div>
        <div class="d-flex justify-content-between">
          <div>
            <div class="metric-label">Used</div>
            <div class="metric-value" id="s-mem-used">—</div>
          </div>
          <div>
            <div class="metric-label">Free</div>
            <div class="metric-value t-muted" id="s-mem-free">—</div>
          </div>
          <div>
            <div class="metric-label">Total</div>
            <div class="metric-value t-muted" id="s-mem-total">—</div>
          </div>
        </div>
        <div class="pbar-wrap mt-2">
          <div class="pbar" id="pbar-mem" style="width:0%"></div>
        </div>
        <div class="t-muted mt-1" style="font-size:.72rem;" id="s-mem-pct">—</div>
      </div>
    </div>

    <!-- Disk -->
    <div class="col-12 col-sm-6 col-lg-3">
      <div class="scard h-100">
        <div class="scard-title"><i class="bi bi-device-ssd me-1"></i>Disk  /</div>
        <div class="d-flex justify-content-between">
          <div>
            <div class="metric-label">Used</div>
            <div class="metric-value" id="s-disk-used">—</div>
          </div>
          <div>
            <div class="metric-label">Free</div>
            <div class="metric-value t-muted" id="s-disk-free">—</div>
          </div>
          <div>
            <div class="metric-label">Total</div>
            <div class="metric-value t-muted" id="s-disk-total">—</div>
          </div>
        </div>
        <div class="pbar-wrap mt-2">
          <div class="pbar" id="pbar-disk" style="width:0%"></div>
        </div>
        <div class="t-muted mt-1" style="font-size:.72rem;" id="s-disk-pct">—</div>
      </div>
    </div>

  </div><!-- /row 1 -->

  <!-- ── Row 2: services + timers ── -->
  <div class="row g-3 mb-3">

    <!-- Services -->
    <div class="col-12 col-lg-7">
      <div class="scard">
        <div class="scard-title"><i class="bi bi-gear me-1"></i>Services</div>
        <table class="status-table">
          <thead>
            <tr>
              <th>Unit</th>
              <th>State</th>
              <th>Enabled</th>
              <th>Since</th>
            </tr>
          </thead>
          <tbody id="tbl-services">
            <tr><td colspan="4" class="t-muted">Loading…</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Timers -->
    <div class="col-12 col-lg-5">
      <div class="scard">
        <div class="scard-title"><i class="bi bi-stopwatch me-1"></i>Timers</div>
        <table class="status-table">
          <thead>
            <tr>
              <th>Timer</th>
              <th>Next run</th>
              <th>Last result</th>
            </tr>
          </thead>
          <tbody id="tbl-timers">
            <tr><td colspan="3" class="t-muted">Loading…</td></tr>
          </tbody>
        </table>
      </div>
    </div>

  </div><!-- /row 2 -->

  <!-- ── History delete ── -->
  <div class="scard d-flex align-items-center gap-3 flex-wrap">
    <i class="bi bi-trash" style="color:var(--red); font-size:1.2rem;"></i>
    <div>
      <div style="color:#e6edf3; font-size:.88rem; font-weight:600;">ADS-B History</div>
      <div class="t-muted" style="font-size:.78rem;">Wipes the adsb-stats state backup file and resets long-term counters.</div>
    </div>
    <button class="del-btn ms-auto" onclick="deleteHistory()">Delete History</button>
    <span id="del-result" style="font-size:.78rem; display:none;"></span>
  </div>

</main>

<footer class="text-center py-3">
  73 de HB9IIU &nbsp;·&nbsp; ADS-B Station
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
(function () {
  'use strict';

  // ── UTC clock ──────────────────────────────────────────────
  function tickClock() {
    const n = new Date();
    const p = v => String(v).padStart(2,'0');
    document.getElementById('clock').textContent =
      `${p(n.getUTCHours())}:${p(n.getUTCMinutes())}:${p(n.getUTCSeconds())} UTC`;
  }
  setInterval(tickClock, 1000);
  tickClock();

  // ── Progress bar helper ────────────────────────────────────
  function setPbar(id, pct) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.width = pct + '%';
    el.classList.remove('warn','crit');
    if (pct >= 90) el.classList.add('crit');
    else if (pct >= 70) el.classList.add('warn');
  }

  // ── Temperature colour ─────────────────────────────────────
  function tempClass(v) {
    const t = parseFloat(v);
    if (isNaN(t)) return '';
    if (t >= 70)  return 'red';
    if (t >= 55)  return 'amber';
    return 'green';
  }

  // ── Load colour ────────────────────────────────────────────
  function loadClass(v) {
    const f = parseFloat(v);
    if (isNaN(f)) return '';
    if (f >= 1.5) return 'red';
    if (f >= 0.8) return 'amber';
    return '';
  }

  // ── Render services ────────────────────────────────────────
  function renderServices(rows) {
    const tbody = document.getElementById('tbl-services');
    tbody.innerHTML = '';
    for (const u of rows) {
      const ok = u.active === 'active';
      const dotCls = ok ? 'ok' : (u.active === 'inactive' ? 'dim' : 'err');
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="mono unit-name">
          <span class="sdot ${dotCls}"></span>${u.name}
        </td>
        <td class="${ok ? 't-green' : 't-red'}">${u.active}</td>
        <td class="${u.enabled === 'enabled' ? 't-green' : 't-muted'}">${u.enabled}</td>
        <td class="mono t-muted">${u.since || '—'}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  // ── Render timers ──────────────────────────────────────────
  function renderTimers(rows) {
    const tbody = document.getElementById('tbl-timers');
    tbody.innerHTML = '';
    for (const t of rows) {
      const ok = t.last_result === 'success' || t.last_result === '';
      const resultHtml = t.last_result
        ? `<span class="pill ${t.last_result === 'success' ? 'ok' : 'bad'}">${t.last_result}</span>`
        : `<span class="t-muted">—</span>`;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="mono unit-name">${t.name}</td>
        <td class="mono ${t.next === '-' ? 't-muted' : 't-green'}">${t.next || '—'}</td>
        <td>${resultHtml}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  // ── Main refresh ───────────────────────────────────────────
  async function refresh() {
    try {
      const r = await fetch('/api/status', { cache: 'no-store' });
      if (!r.ok) return;
      const d = await r.json();
      const s = d.system;

      // Time & uptime
      document.getElementById('s-time').textContent   = s.time_local;
      document.getElementById('s-uptime').textContent = s.uptime;

      // Load
      ['load1','load5','load15'].forEach(k => {
        const el = document.getElementById('s-' + k);
        el.textContent = s[k];
        el.className = 'metric-value ' + loadClass(s[k]);
      });

      // Temperature
      const tempEl = document.getElementById('s-temp');
      tempEl.textContent = s.cpu_temp !== '?' ? s.cpu_temp + ' °C' : '?';
      tempEl.className = 'metric-value ' + tempClass(s.cpu_temp);

      // Memory
      document.getElementById('s-mem-used').textContent  = s.mem.used;
      document.getElementById('s-mem-free').textContent  = s.mem.free;
      document.getElementById('s-mem-total').textContent = s.mem.total;
      document.getElementById('s-mem-pct').textContent   = s.mem.pct + '% used';
      setPbar('pbar-mem', s.mem.pct);

      // Disk
      document.getElementById('s-disk-used').textContent  = s.disk.used;
      document.getElementById('s-disk-free').textContent  = s.disk.free;
      document.getElementById('s-disk-total').textContent = s.disk.total;
      document.getElementById('s-disk-pct').textContent   = s.disk.pct + '% used';
      setPbar('pbar-disk', s.disk.pct);

      renderServices(d.services);
      renderTimers(d.timers);

    } catch (e) {
      console.warn('refresh error', e);
    }
  }

  refresh();
  setInterval(refresh, """ + str(REFRESH_MS) + r""");

  // ── Delete history ─────────────────────────────────────────
  window.deleteHistory = async function () {
    if (!confirm('Delete ADS-B history backup file and reset long-term counters?')) return;
    const el = document.getElementById('del-result');
    try {
      const r = await fetch('/api/delete-history', { method: 'POST' });
      const data = await r.json();
      el.textContent = data.ok ? '✓ History deleted.' : '✗ ' + (data.error || 'Error');
      el.style.color = data.ok ? 'var(--green)' : 'var(--red)';
    } catch {
      el.textContent = '✗ Request failed';
      el.style.color = 'var(--red)';
    }
    el.style.display = 'inline';
    setTimeout(() => { el.style.display = 'none'; }, 4000);
  };
})();
</script>
</body>
</html>
"""

# ── Routes ──────────────────────────────────────────────────────

@app.get("/")
def index():
    return render_template_string(HTML)

@app.get("/api/status")
def api_status():
    now = datetime.now().astimezone()
    load = get_load()
    return {
        "system": {
            "time_local": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "uptime":     get_uptime(),
            "load1":      load["load1"],
            "load5":      load["load5"],
            "load15":     load["load15"],
            "cpu_temp":   get_cpu_temp(),
            "mem":        get_mem(),
            "disk":       get_disk(),
        },
        "services": [unit_info(u)  for u in SERVICES],
        "timers":   [timer_info(t) for t in TIMERS],
    }

@app.post("/api/delete-history")
def delete_history():
    try:
        subprocess.run(
            [str(VENV_PYTHON), str(APPS_DIR / "adsb-stats.py"), "--reset"],
            check=True,
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    host = os.environ.get("STATUS_HOST", "0.0.0.0")
    port = int(os.environ.get("STATUS_PORT", "8080"))
    app.run(host=host, port=port)
