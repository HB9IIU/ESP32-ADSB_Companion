#include <Config.h>
#include <HB9IIU_RobustWIfiConnection.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>
#include <SPI.h>
#include <pgmspace.h>
#include <math.h>
#include "background565.h"
#include "plane32_360.h"
#include <HB9IIU_BacklightControl.h>
#include "splash565.h"
#include <Preferences.h>

// Track storage limit
static const int MAX_TRACKS = 200;

// How many planes to actually DRAW each refresh (performance knob)
static const int MAX_DRAW = 99;

// Ignore stale positions older than this (seconds, from JSON seen_pos)
static const double MAX_SEEN_POS_S = 30.0;
// "Total aircraft" count uses JSON field "seen" (can be older than position)
static const double MAX_SEEN_S = 60.0;

// Remove/erase planes if not updated for this long (ms)
static const uint32_t TRACK_TTL_MS = 15000;

// Refresh interval (ms)
static const uint32_t FETCH_PERIOD_MS = 1000;

// Range filter (km) just to reject far aircraft early (optional)
static const double RANGE_KM = 500.0;

// Debug prints
static const bool DEBUG_FETCH = true;
static const bool DEBUG_TRACKS = true;
static const bool DEBUG_HEADING_MAP = false; // prints heading mapping

// ===================== Stats for bottom bar =====================
// Total aircraft entries in JSON, how many have position, how many are drawn
static volatile int gTotalRaw = 0;
static volatile int gWithPos = 0;
static volatile int gSeen = 0;

// ===================== TFT / Sprites =====================
TFT_eSPI tft = TFT_eSPI();

static const int SW = 480;
static const int SH = 320;

static const int PW = plane32_w;
static const int PH = plane32_h;
static const int STRIDE = plane32_stride;

// line buffers for background restore
static uint16_t lineBuf32[PW];   // 32
static uint16_t lineBufWide[SW]; // up to 480 (for dirty regions)

// sprite mapping (your working fix)
static const bool SPRITE_CCW = true;
static const int SPRITE_OFFSET_DEG = 0;
static const bool SPRITE_FLIP_180 = false;

// ===================== Altitude color layers (meters) =====================
// altitude_m == -1 means "unknown"
static const int ALT_L1_M = 1000; // < 1 km
static const int ALT_L2_M = 5000; // 1..5 km
static const int ALT_L3_M = 9000; // 5..9 km
// >= 9 km is the highest band

// Colors per band (TFT_eSPI built-ins)
static const uint16_t ALT_COLOR_UNKNOWN = TFT_DARKGREY;
static const uint16_t ALT_COLOR_L1 = TFT_RED;    // low
static const uint16_t ALT_COLOR_L2 = TFT_GREEN;  // medium-low
static const uint16_t ALT_COLOR_L3 = TFT_YELLOW; // medium-high
static const uint16_t ALT_COLOR_L4 = TFT_CYAN;   // high

// ===================== Legend bar tuning =====================
static const int LEGEND_H = 18;               // bar height
static const int LEGEND_LEFT_MARGIN = 50;     // shift legend row left/right
static const int LEGEND_TEXT_Y_OFFSET = 0;    // text vertical tweak
static const int LEGEND_SWATCH_Y_OFFSET = -1; // swatch vertical tweak

// ===================== Bottom status bar =====================
static const int BOTTOM_H = 18;            // pixels reserved at bottom
static const int BOTTOM_LEFT_MARGIN = 25;  // horizontal offset
static const int BOTTOM_TEXT_Y_OFFSET = 2; // vertical tweak for text

// ===================== Helpers =====================
static inline double deg2rad(double d) { return d * (PI / 180.0); }
static inline double rad2deg(double r) { return r * (180.0 / PI); }

static uint16_t colorFromAltitudeM(int alt_m)
{
  if (alt_m < 0)
    return ALT_COLOR_UNKNOWN;
  if (alt_m < ALT_L1_M)
    return ALT_COLOR_L1;
  if (alt_m < ALT_L2_M)
    return ALT_COLOR_L2;
  if (alt_m < ALT_L3_M)
    return ALT_COLOR_L3;
  return ALT_COLOR_L4;
}

static double haversine_km(double lat1, double lon1, double lat2, double lon2)
{
  const double R = 6371.0;
  const double dLat = deg2rad(lat2 - lat1);
  const double dLon = deg2rad(lon2 - lon1);
  const double a = sin(dLat / 2) * sin(dLat / 2) +
                   cos(deg2rad(lat1)) * cos(deg2rad(lat2)) *
                       sin(dLon / 2) * sin(dLon / 2);
  const double c = 2.0 * atan2(sqrt(a), sqrt(1 - a));
  return R * c;
}

static double bearing_deg(double lat1, double lon1, double lat2, double lon2)
{
  const double phi1 = deg2rad(lat1);
  const double phi2 = deg2rad(lat2);
  const double dLon = deg2rad(lon2 - lon1);

  const double y = sin(dLon) * cos(phi2);
  const double x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dLon);
  double brng = rad2deg(atan2(y, x));
  if (brng < 0)
    brng += 360.0;
  return brng;
}

static String trimFlight(const char *flight)
{
  if (!flight)
    return "";
  String s(flight);
  s.trim();
  return s;
}

// Slippy-map global pixels (same math as your Python)
static void latlon_to_global_pixels(double lat_deg, double lon_deg, int zoom, double &x, double &y)
{
  if (lat_deg > 85.05112878)
    lat_deg = 85.05112878;
  if (lat_deg < -85.05112878)
    lat_deg = -85.05112878;

  const double lat = deg2rad(lat_deg);
  const double n = (double)(1UL << zoom); // 2^zoom
  x = (lon_deg + 180.0) / 360.0 * (256.0 * n);
  y = (1.0 - log(tan(lat) + (1.0 / cos(lat))) / PI) / 2.0 * (256.0 * n);
}

static bool latlon_to_screen_xy(double lat, double lon, int &sx, int &sy)
{
  double gx, gy;
  latlon_to_global_pixels(lat, lon, MAP_ZOOM, gx, gy);
  const double fx = gx - MAP_PX0;
  const double fy = gy - MAP_PY0;

  sx = (int)lround(fx);
  sy = (int)lround(fy);

  if (sx < -PW || sx > SW + PW)
    return false;
  if (sy < -PH || sy > SH + PH)
    return false;
  return true;
}

// ===================== Background =====================
void drawFullBackground()
{
  static uint16_t row[SW];
  for (int y = 0; y < SH; y++)
  {
    const uint16_t *src = bg565 + (y * SW);
    memcpy_P(row, src, SW * sizeof(uint16_t));
    tft.pushImage(0, y, SW, 1, row);
    yield();
  }
}

// Fast restore for 32-wide rectangles (kept for compatibility/use)
void restoreBgRect32(int x, int y, int w, int h)
{
  if (x < 0)
  {
    w += x;
    x = 0;
  }
  if (y < 0)
  {
    h += y;
    y = 0;
  }
  if (x + w > SW)
    w = SW - x;
  if (y + h > SH)
    h = SH - y;
  if (w <= 0 || h <= 0)
    return;

  for (int row = 0; row < h; row++)
  {
    const uint16_t *src = bg565 + ((y + row) * SW + x);
    memcpy_P(lineBuf32, src, w * sizeof(uint16_t));
    tft.pushImage(x, y + row, w, 1, lineBuf32);
  }
}

// General restore for any width up to SW (used for dirty regions)
void restoreBgRectWide(int x, int y, int w, int h)
{
  if (x < 0)
  {
    w += x;
    x = 0;
  }
  if (y < 0)
  {
    h += y;
    y = 0;
  }
  if (x + w > SW)
    w = SW - x;
  if (y + h > SH)
    h = SH - y;
  if (w <= 0 || h <= 0)
    return;

  for (int row = 0; row < h; row++)
  {
    const uint16_t *src = bg565 + ((y + row) * SW + x);
    memcpy_P(lineBufWide, src, w * sizeof(uint16_t));
    tft.pushImage(x, y + row, w, 1, lineBufWide);
  }
}

// ===================== Plane draw =====================
static inline const uint8_t *planeMaskForHeading(int headingDeg)
{
  headingDeg %= 360;
  if (headingDeg < 0)
    headingDeg += 360;

  uint32_t off = 0;
  memcpy_P(&off, &plane32_offset[headingDeg], sizeof(plane32_offset[headingDeg]));
  return plane32_masks + off;
}

void drawMask1bit_PROGMEM(int x0, int y0,
                          const uint8_t *maskProgmem,
                          int w, int h, int stride,
                          uint16_t color)
{
  for (int y = 0; y < h; y++)
  {
    int x = 0;
    while (x < w)
    {
      while (x < w)
      {
        int byteIndex = y * stride + (x >> 3);
        uint8_t b = pgm_read_byte(maskProgmem + byteIndex);
        int bit = 7 - (x & 7);
        bool on = (b & (1 << bit)) != 0;
        if (on)
          break;
        x++;
      }
      if (x >= w)
        break;

      int xStart = x;

      while (x < w)
      {
        int byteIndex = y * stride + (x >> 3);
        uint8_t b = pgm_read_byte(maskProgmem + byteIndex);
        int bit = 7 - (x & 7);
        bool on = (b & (1 << bit)) != 0;
        if (!on)
          break;
        x++;
      }

      tft.drawFastHLine(x0 + xStart, y0 + y, x - xStart, color);
    }
  }
}

static inline int mapHeadingToSprite(int headingDeg)
{
  int h = headingDeg % 360;
  if (h < 0)
    h += 360;

  if (SPRITE_CCW)
    h = (360 - h) % 360;
  h = (h + SPRITE_OFFSET_DEG) % 360;
  if (SPRITE_FLIP_180)
    h = (h + 180) % 360;
  return h;
}

void drawPlaneAtTopLeft(int x0, int y0, int spriteHeadingDeg, uint16_t color)
{
  const uint8_t *maskPtr = planeMaskForHeading(spriteHeadingDeg);
  drawMask1bit_PROGMEM(x0, y0, maskPtr, PW, PH, STRIDE, color);
}

// ===================== Track table =====================
struct Track
{
  bool used = false;

  char hex[7] = {0};    // 6 hex chars + null
  char flight[9] = {0}; // up to 8 + null

  double lat = 0;
  double lon = 0;

  int cx = 0, cy = 0; // center screen position
  int oldDrawX = 0, oldDrawY = 0;

  int headingDeg = 0; // 0..359 from ADS-B track

  int altitude_m = -1; // barometric altitude (meters), -1 = unknown

  uint16_t color = TFT_WHITE;

  uint32_t lastUpdateMs = 0; // millis() when updated
  bool drawn = false;
};

static Track tracks[MAX_TRACKS];

static int findTrackByHex(const char *hex)
{
  for (int i = 0; i < MAX_TRACKS; i++)
  {
    if (tracks[i].used && strncmp(tracks[i].hex, hex, 6) == 0)
      return i;
  }
  return -1;
}

static int allocTrackSlot()
{
  for (int i = 0; i < MAX_TRACKS; i++)
  {
    if (!tracks[i].used)
      return i;
  }
  uint32_t oldest = 0xFFFFFFFF;
  int idx = 0;
  for (int i = 0; i < MAX_TRACKS; i++)
  {
    if (tracks[i].lastUpdateMs < oldest)
    {
      oldest = tracks[i].lastUpdateMs;
      idx = i;
    }
  }
  return idx;
}

static void eraseTrackIfDrawn(Track &t)
{
  if (!t.drawn)
    return;
  restoreBgRect32(t.oldDrawX, t.oldDrawY, PW, PH);
  t.drawn = false;
}

static void expireOldTracks()
{
  const uint32_t now = millis();
  tft.startWrite();
  for (int i = 0; i < MAX_TRACKS; i++)
  {
    if (!tracks[i].used)
      continue;
    if ((now - tracks[i].lastUpdateMs) > TRACK_TTL_MS)
    {
      eraseTrackIfDrawn(tracks[i]);
      tracks[i].used = false;
    }
  }
  tft.endWrite();
}

// pick up to MAX_DRAW nearest (by distance to HOME) among fresh tracks
static int buildDrawList(int outIdx[], int maxOut)
{
  int count = 0;

  // Step 1: collect all drawable tracks
  for (int i = 0; i < MAX_TRACKS && count < maxOut; i++)
  {
    if (!tracks[i].used)
      continue;

    // must be fresh enough
    if ((millis() - tracks[i].lastUpdateMs) >
        (uint32_t)(MAX_SEEN_POS_S * 1000.0))
      continue;

    // must be on screen (using sprite top-left)
    int x0 = tracks[i].cx - PW / 2;
    int y0 = tracks[i].cy - PH / 2;

    // skip anything that would enter the legend bar
    if (y0 < LEGEND_H)
      continue;
    // skip anything that would enter the bottom bar
    if (y0 + PH > (SH - BOTTOM_H))
      continue;

    if (x0 < -PW || x0 > SW)
      continue;
    if (y0 < -PH || y0 > SH)
      continue;

    outIdx[count++] = i;
  }

  // Step 2: sort by altitude (ascending → highest drawn last)
  for (int i = 0; i < count - 1; i++)
  {
    for (int j = i + 1; j < count; j++)
    {
      int ai = tracks[outIdx[i]].altitude_m;
      int aj = tracks[outIdx[j]].altitude_m;

      // unknown altitude goes first
      if (ai < 0)
        ai = -1000000;
      if (aj < 0)
        aj = -1000000;

      if (ai > aj)
      {
        int tmp = outIdx[i];
        outIdx[i] = outIdx[j];
        outIdx[j] = tmp;
      }
    }
  }

  return count;
}

static bool isInDrawList(int idx, const int list[], int n)
{
  for (int i = 0; i < n; i++)
    if (list[i] == idx)
      return true;
  return false;
}

// ===================== Dirty-rect renderer (handles overlaps) =====================
struct Rect
{
  int x, y, w, h;
};

static inline Rect rectClampToScreen(Rect r)
{
  if (r.x < 0)
  {
    r.w += r.x;
    r.x = 0;
  }
  if (r.y < 0)
  {
    r.h += r.y;
    r.y = 0;
  }
  if (r.x + r.w > SW)
    r.w = SW - r.x;
  if (r.y + r.h > SH)
    r.h = SH - r.y;
  if (r.w < 0)
    r.w = 0;
  if (r.h < 0)
    r.h = 0;
  return r;
}

static inline bool rectIntersects(const Rect &a, const Rect &b)
{
  return !(a.x + a.w <= b.x || b.x + b.w <= a.x ||
           a.y + a.h <= b.y || b.y + b.h <= a.y);
}

static inline Rect rectUnion(const Rect &a, const Rect &b)
{
  int x1 = min(a.x, b.x);
  int y1 = min(a.y, b.y);
  int x2 = max(a.x + a.w, b.x + b.w);
  int y2 = max(a.y + a.h, b.y + b.h);
  return {x1, y1, x2 - x1, y2 - y1};
}

static inline Rect trackRectCurrent(const Track &t)
{
  return {t.cx - PW / 2, t.cy - PH / 2, PW, PH};
}

static inline Rect trackRectOld(const Track &t)
{
  return {t.oldDrawX, t.oldDrawY, PW, PH};
}

static void redrawPlanesIntersecting(const Rect &r, const int drawIdx[], int nDraw)
{
  for (int k = 0; k < nDraw; k++)
  {
    Track &t = tracks[drawIdx[k]];
    Rect cr = trackRectCurrent(t);
    if (!rectIntersects(r, cr))
      continue;

    int x0 = cr.x;
    int y0 = cr.y;

    int spriteHeading = mapHeadingToSprite(t.headingDeg);
    drawPlaneAtTopLeft(x0, y0, spriteHeading, t.color);

    if (DEBUG_HEADING_MAP)
    {
      Serial.printf("MAP heading: adsb=%3d -> sprite=%3d  (CCW=%d off=%d flip180=%d)\n",
                    t.headingDeg, spriteHeading,
                    (int)SPRITE_CCW, SPRITE_OFFSET_DEG, (int)SPRITE_FLIP_180);
    }

    t.oldDrawX = x0;
    t.oldDrawY = y0;
    t.drawn = true;

    if (DEBUG_TRACKS)
    {
      const double dkm = haversine_km(HOME_LAT, HOME_LON, t.lat, t.lon);
      const double brg = bearing_deg(HOME_LAT, HOME_LON, t.lat, t.lon);
      const double ageS = (double)(millis() - t.lastUpdateMs) / 1000.0;

      Serial.printf(
          "T%02d %s %-8s alt=%6dm  d=%.1fkm brg=%.0f  lat=%.5f lon=%.5f  xy=(%d,%d) trk=%d age=%.1fs\n",
          k, t.hex, t.flight,
          t.altitude_m,
          dkm, brg,
          t.lat, t.lon,
          t.cx, t.cy,
          t.headingDeg, ageS);
    }
  }
}

// ===================== Network fetch + parse =====================
static bool fetchAndUpdateTracks()
{
  if (WiFi.status() != WL_CONNECTED)
    return false;

  const uint32_t t0 = millis();

  HTTPClient http;
  http.setTimeout(3500);
  http.setReuse(false);
  http.begin(AIRCRAFT_URL);

  int code = http.GET();
  uint32_t t1 = millis();

  if (code != 200)
  {
    if (DEBUG_FETCH)
    {
      Serial.printf("--- FETCH --- heap=%u rssi=%d dBm\n", ESP.getFreeHeap(), WiFi.RSSI());
      Serial.printf("HTTP GET failed: %d  (dt=%ums)\n\n", code, (unsigned)(t1 - t0));
    }
    http.end();
    return false;
  }

  JsonDocument filter;
  filter["now"] = true;
  JsonArray fa = filter["aircraft"].to<JsonArray>();
  JsonObject a0 = fa.add<JsonObject>();
  a0["hex"] = true;
  a0["flight"] = true;
  a0["lat"] = true;
  a0["lon"] = true;
  a0["track"] = true;
  a0["seen_pos"] = true;
  a0["seen"] = true;
  a0["alt_baro"] = true;

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, *http.getStreamPtr(),
                                             DeserializationOption::Filter(filter));
  http.end();

  const uint32_t t2 = millis();

  if (err)
  {
    if (DEBUG_FETCH)
    {
      Serial.printf("--- FETCH --- heap=%u rssi=%d dBm\n", ESP.getFreeHeap(), WiFi.RSSI());
      Serial.printf("HTTP 200  (dt=%ums)\n", (unsigned)(t1 - t0));
      Serial.printf("JSON parse error: %s  (parse dt=%ums)\n\n", err.c_str(), (unsigned)(t2 - t1));
    }
    return false;
  }

  const double now = doc["now"] | 0.0;
  JsonArray aircraft = doc["aircraft"].as<JsonArray>();

  int totalRaw = (int)aircraft.size();
  int totalShown = 0; // PiAware/PlaneFinder-like
  int withPos = 0;
  int fresh = 0;
  int within = 0;
  int updated = 0;
  gTotalRaw = totalRaw;
  for (JsonObject a : aircraft)
  {
    const char *hex = a["hex"] | "";
    if (!hex[0])
      continue;

    const double seen = a["seen"] | 9999.0;
    if (seen <= MAX_SEEN_S)
      totalShown++;

    if (!a["lat"].is<double>() || !a["lon"].is<double>())
      continue;
    withPos++;

    const double seen_pos = a["seen_pos"] | 9999.0;
    if (seen_pos > MAX_SEEN_POS_S)
      continue;

    fresh++;

    const double lat = a["lat"].as<double>();
    const double lon = a["lon"].as<double>();

    const double dkm = haversine_km(HOME_LAT, HOME_LON, lat, lon);
    if (dkm > RANGE_KM)
      continue;
    within++;

    int sx, sy;
    if (!latlon_to_screen_xy(lat, lon, sx, sy))
      continue;

    int idx = findTrackByHex(hex);
    if (idx < 0)
      idx = allocTrackSlot();

    Track &t = tracks[idx];

    if (t.used && strncmp(t.hex, hex, 6) != 0)
    {
      tft.startWrite();
      eraseTrackIfDrawn(t);
      tft.endWrite();
    }

    t.used = true;
    strncpy(t.hex, hex, 6);
    t.hex[6] = 0;

    String flightS = trimFlight(a["flight"] | "");
    strncpy(t.flight, flightS.c_str(), 8);
    t.flight[8] = 0;

    t.lat = lat;
    t.lon = lon;

    t.cx = sx;
    t.cy = sy;

    // track heading (degrees)
    double trk = a["track"] | 0.0;
    int hdg = (int)lround(trk);
    hdg %= 360;
    if (hdg < 0)
      hdg += 360;
    t.headingDeg = hdg;

    // --- barometric altitude (feet) ---
    if (a["alt_baro"].is<int>())
    {
      int alt_ft = a["alt_baro"].as<int>();
      t.altitude_m = (int)lround(alt_ft * 0.3048);
    }
    else
    {
      t.altitude_m = -1;
    }

    t.color = colorFromAltitudeM(t.altitude_m);

    t.lastUpdateMs = millis();

    updated++;
  }
  gWithPos = withPos;

  if (DEBUG_FETCH)
  {
    Serial.printf("--- FETCH --- heap=%u rssi=%d dBm\n", ESP.getFreeHeap(), WiFi.RSSI());
    Serial.printf("HTTP 200  (dt=%ums)\n", (unsigned)(t1 - t0));
    Serial.printf("now=%.1f aircraft=%d\n", now, totalRaw);
    Serial.printf("stats: seen<=%.0fs=%d (raw=%d) withPos=%d posFresh<=%.0fs=%d within%.0fkm=%d updated=%d\n",
                  MAX_SEEN_S, totalShown, totalRaw, withPos, MAX_SEEN_POS_S, fresh, RANGE_KM, within, updated);
  }
  gSeen = totalShown;
  gWithPos = withPos;
  return true;
}

static const char *trackLabel(const Track &t)
{
  // Prefer callsign, else fall back to hex
  return (t.flight[0] != 0) ? t.flight : t.hex;
}

static char bottomPrev[96] = {0}; // previous rendered string
static bool bottomHasPrev = false;

static void drawBottomBarTextDiff(const char *text)
{
  const int y0 = SH - BOTTOM_H;

  // Bar background (draw once per frame is fine; but we avoid full clears for flicker)
  // We'll keep the bar background stable by only changing characters.

  tft.setTextDatum(TL_DATUM);

  // Positioning
  const int yText = y0 + (BOTTOM_H - 8) / 2 + BOTTOM_TEXT_Y_OFFSET;
  const int xText = BOTTOM_LEFT_MARGIN;

  // Copy current text to a fixed buffer (protect against long strings)
  char cur[96];
  strncpy(cur, text, sizeof(cur) - 1);
  cur[sizeof(cur) - 1] = 0;

  // First time: draw full bar background + full text
  if (!bottomHasPrev)
  {
    tft.fillRect(0, y0, SW, BOTTOM_H, TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.drawString(cur, xText, yText);

    strncpy(bottomPrev, cur, sizeof(bottomPrev));
    bottomPrev[sizeof(bottomPrev) - 1] = 0;
    bottomHasPrev = true;
    return;
  }

  // Redraw only changed characters (old in black, new in white)
  // Default font approx 6px per char; we'll treat it as fixed-width for this bar.
  const int charW = 6;

  size_t maxLen = max(strlen(bottomPrev), strlen(cur));

  for (size_t i = 0; i < maxLen; i++)
  {
    char oldc = (i < strlen(bottomPrev)) ? bottomPrev[i] : '\0';
    char newc = (i < strlen(cur)) ? cur[i] : '\0';

    if (oldc == newc)
      continue;

    int x = xText + (int)i * charW;

    // erase old char by drawing it in black on black
    if (oldc != '\0')
    {
      tft.setTextColor(TFT_BLACK, TFT_BLACK);
      char s[2] = {oldc, 0};
      tft.drawString(s, x, yText);
    }

    // draw new char in white
    if (newc != '\0')
    {
      tft.setTextColor(TFT_WHITE, TFT_BLACK);
      char s[2] = {newc, 0};
      tft.drawString(s, x, yText);
    }
  }

  // Save as previous
  strncpy(bottomPrev, cur, sizeof(bottomPrev));
  bottomPrev[sizeof(bottomPrev) - 1] = 0;
}
static void updateBottomBar(const int drawIdx[], int nDraw)
{
  // Compute NEAR / FAR over the planes we are actually drawing
  double nearKm = 1e9;
  double farKm = 0.0;
  int nearSlot = -1;

  int maxAltM = -1; // <<< ADDED

  for (int k = 0; k < nDraw; k++)
  {
    Track &t = tracks[drawIdx[k]];
    double dkm = haversine_km(HOME_LAT, HOME_LON, t.lat, t.lon);

    if (dkm < nearKm)
    {
      nearKm = dkm;
      nearSlot = drawIdx[k];
    }
    if (dkm > farKm)
      farKm = dkm;

    // <<< ADDED: max altitude among drawn planes
    if (t.altitude_m >= 0 && t.altitude_m > maxAltM)
      maxAltM = t.altitude_m;
  }

  char line[96];

  if (nDraw <= 0)
  {
    snprintf(line, sizeof(line),
             "Tot %d  Pos %d  Drw 0 | NEAR --- --.-km | FAR --.-km | MAX ALT ---",
             gTotalRaw, gWithPos);
  }
  else
  {
    const Track &tn = tracks[nearSlot];
    const char *nearName = trackLabel(tn);

    if (maxAltM >= 0)
    {
      snprintf(line, sizeof(line),
               "Tot %d  Pos %d  Drw %d | NEAR %s %.1fkm | FAR %.1fkm | MAX ALT %dm",
               gSeen, gWithPos, nDraw,
               nearName, nearKm, farKm, maxAltM);
    }
    else
    {
      snprintf(line, sizeof(line),
               "Tot %d  Pos %d  Drw %d | NEAR %s %.1fkm | FAR %.1fkm | MAX ALT ---",
               gSeen, gWithPos, nDraw,
               nearName, nearKm, farKm);
    }
  }

  drawBottomBarTextDiff(line);
}

// ===================== Render =====================
static void renderTracks()
{
  // expire old ones (still uses 32x32 erase; OK because expiry removes the whole sprite area)
  expireOldTracks();

  int drawIdx[MAX_DRAW];
  int nDraw = buildDrawList(drawIdx, MAX_DRAW);

  // Build dirty rectangles:
  // - for each plane we will draw: its old rect (if previously drawn) and its new rect
  // - for planes that were drawn but are no longer in draw list: their old rect
  Rect dirty[2 * MAX_DRAW + MAX_DRAW]; // enough for old+new + removed
  int nDirty = 0;

  // removed-from-draw-list: mark their old rect dirty so they get erased
  for (int i = 0; i < MAX_TRACKS; i++)
  {
    if (!tracks[i].used)
      continue;
    if (tracks[i].drawn && !isInDrawList(i, drawIdx, nDraw))
    {
      dirty[nDirty++] = trackRectOld(tracks[i]);
      tracks[i].drawn = false; // will be gone after redraw pass
    }
  }

  // old + new rects for the ones we will draw
  for (int k = 0; k < nDraw; k++)
  {
    Track &t = tracks[drawIdx[k]];
    if (t.drawn)
    {
      dirty[nDirty++] = trackRectOld(t);
    }
    dirty[nDirty++] = trackRectCurrent(t);
  }

  // clamp dirty rects to screen and drop empties
  int wptr = 0;
  for (int i = 0; i < nDirty; i++)
  {
    Rect r = rectClampToScreen(dirty[i]);
    if (r.w > 0 && r.h > 0)
      dirty[wptr++] = r;
  }
  nDirty = wptr;

  // Merge overlapping dirty rects (simple O(n^2); n is small)
  for (int i = 0; i < nDirty; i++)
  {
    for (int j = i + 1; j < nDirty;)
    {
      if (rectIntersects(dirty[i], dirty[j]))
      {
        dirty[i] = rectClampToScreen(rectUnion(dirty[i], dirty[j]));
        dirty[j] = dirty[nDirty - 1];
        nDirty--;
      }
      else
      {
        j++;
      }
    }
  }

  tft.startWrite();

  // For each dirty region: restore background and redraw any planes that intersect it
  for (int i = 0; i < nDirty; i++)
  {
    restoreBgRectWide(dirty[i].x, dirty[i].y, dirty[i].w, dirty[i].h);
    redrawPlanesIntersecting(dirty[i], drawIdx, nDraw);
  }
  updateBottomBar(drawIdx, nDraw);
  tft.endWrite();

  if (DEBUG_TRACKS)
    Serial.println();
}

static void drawLegendBar()
{
  // Background strip
  tft.fillRect(0, 0, SW, LEGEND_H, TFT_BLACK);

  // Swatch size
  const int sw = 10;
  const int sh = 10;

  // Compute "centered" Y positions with optional offsets
  const int yText = (LEGEND_H - 8) / 2 + LEGEND_TEXT_Y_OFFSET; // ~8px font height
  const int ySwatch = (LEGEND_H - sh) / 2 + LEGEND_SWATCH_Y_OFFSET;

  // Text setup
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);

  int x = LEGEND_LEFT_MARGIN;

  tft.drawString("ALT m:", x, yText);
  x += 46; // spacing after "ALT m:"

  // Draw one legend item: swatch + label
  auto item = [&](uint16_t col, const char *label)
  {
    tft.fillRect(x, ySwatch, sw, sh, col);
    tft.drawRect(x, ySwatch, sw, sh, TFT_WHITE);
    x += sw + 3;

    tft.drawString(label, x, yText);

    // crude width estimate for default font: ~6 px per char
    x += (int)strlen(label) * 6 + 10;
  };

  item(ALT_COLOR_L1, "0-1000");
  item(ALT_COLOR_L2, "1000-5000");
  item(ALT_COLOR_L3, "5000-9000");
  item(ALT_COLOR_L4, "9000+");
  item(ALT_COLOR_UNKNOWN, "UNKNOWN");
}

static void displaySplashScreen(uint32_t holdMs)
{
  // Start dark
  backlightSetPercent(0);

  // Draw splash while dark
  tft.startWrite();
  tft.pushImage(0, 0, 480, 320, splash565);
  tft.endWrite();

  // Fade in
  for (int p = 0; p <= HB9_BL_DEFAULT_PERCENT; p += 2)
  {
    backlightSetPercent(p);
    delay(15);
  }

  // Hold
  delay(holdMs);

  // Fade out
  for (int p = HB9_BL_DEFAULT_PERCENT; p >= 0; p -= 2)
  {
    backlightSetPercent(p);
    delay(12);
  }

  // Switch to main UI while dark
  tft.startWrite();
  drawFullBackground();
  drawLegendBar();
  tft.endWrite();

  // Fade in again
  for (int p = 0; p <= HB9_BL_DEFAULT_PERCENT; p += 2)
  {
    backlightSetPercent(p);
    delay(12);
  }
}

#ifndef HB9_TFT_INVERT
#define HB9_TFT_INVERT 0
#endif

// BRIGTHNESS HANDLING
Preferences prefs;

static uint8_t gBl = HB9_BL_DEFAULT_PERCENT; // current brightness
static uint8_t gBlSaved = 255;               // last saved value (init invalid)
static bool gBlDirty = false;
static uint32_t gLastTouchMs = 0;

static const uint32_t BL_SAVE_IDLE_MS = 5000; // save after 5s no touch
static const char *PREF_NS = "ui";
static const char *PREF_KEY_BL = "bl";

void handleTouchBrightnessAndSave()
{
  
  // Ensure any pending TFT write transaction is not holding the SPI bus
tft.endWrite();
  
  // 1) Handle touch -> change brightness
  uint16_t touchX, touchY;
  if (tft.getTouch(&touchX, &touchY))
  {
    // Y invert
    touchY = SH - touchY;

    static uint32_t lastStepMs = 0;
    uint32_t now = millis();

    // limit repeat rate while finger is down
    if (now - lastStepMs >= 180)
    {
      lastStepMs = now;

      const uint8_t step = 2;
      uint8_t old = gBl;

      if (touchY < (SH / 2)) // upper half => brighter
        gBl = (gBl + step > 100) ? 100 : (gBl + step);
      else // lower half => dimmer
        gBl = (gBl < step) ? 0 : (gBl - step);

      if (gBl != old)
      {
        backlightSetPercent(gBl);
        gBlDirty = true;
      }
    }

    gLastTouchMs = millis(); // update "activity"
  }

  // 2) Save only after inactivity window
  if (gBlDirty)
  {
    uint32_t now = millis();
    if ((now - gLastTouchMs) >= BL_SAVE_IDLE_MS)
    {
      // only write if different from last saved value
      if (gBl != gBlSaved)
      {
        prefs.putUChar(PREF_KEY_BL, gBl);
        gBlSaved = gBl;
        Serial.printf("Saved brightness: %u%%\n", gBl);
      }
      gBlDirty = false;
    }
  }
}

static bool waitForValidAircraftStream(uint32_t maxWaitMs, uint32_t retryDelayMs)
{
  const uint32_t tStart = millis();
  uint32_t attempts = 0;
  Serial.println("");
  Serial.println("🛰️  Stream check: waiting for valid aircraft JSON…");

  while ((millis() - tStart) < maxWaitMs)
  {
    attempts++;

    const uint32_t elapsed = millis() - tStart;
    Serial.printf("🔎 Try #%lu | ⏱️ %lums / %lums | 📶 WiFi=%s\n",
                  (unsigned long)attempts,
                  (unsigned long)elapsed,
                  (unsigned long)maxWaitMs,
                  (WiFi.status() == WL_CONNECTED) ? "OK ✅" : "DOWN ❌");

    // Bottom bar progress
    {

      const uint32_t elapsedS = (millis() - tStart) / 1000;
      const uint32_t totalS = maxWaitMs / 1000;
      char msg[80];
      snprintf(msg, sizeof(msg),
               "                 JSON Stream check... #%lu  %lus / %lus",
               (unsigned long)attempts,
               (unsigned long)elapsedS,
               (unsigned long)totalS);

      tft.startWrite();
      drawBottomBarTextDiff(msg);
      tft.endWrite();
    }

    if (WiFi.status() != WL_CONNECTED)
    {
      Serial.println("⚠️  WiFi not connected yet… waiting…");
      delay(retryDelayMs);
      continue;
    }

    HTTPClient http;
    http.setTimeout(3500);
    http.setReuse(false);
    http.begin(AIRCRAFT_URL);

    Serial.println(String("🌐 HTTP GET → ") + AIRCRAFT_URL);

    const uint32_t t0 = millis();
    int code = http.GET();
    const uint32_t t1 = millis();

    if (code != 200)
    {
      Serial.printf("❌ HTTP failed: %d | ⏱️%lums\n", code, (unsigned long)(t1 - t0));
      http.end();
      delay(retryDelayMs);
      continue;
    }

    Serial.printf("✅ HTTP 200 OK | ⏱️%lums | parsing JSON…\n", (unsigned long)(t1 - t0));

    JsonDocument doc;

    DeserializationError err = deserializeJson(doc, *http.getStreamPtr());
    http.end();

    if (err)
    {
      Serial.printf("💥 JSON parse error: %s\n", err.c_str());
      delay(retryDelayMs);
      continue;
    }

    // require "now" and "aircraft" array
const bool hasNow = !doc["now"].isNull();
const bool hasAircraftArray = doc["aircraft"].is<JsonArray>();

    if (!hasNow || !hasAircraftArray)
    {
      Serial.printf("⚠️  JSON structure not ready: now=%s aircraft[]=%s\n",
                    hasNow ? "YES ✅" : "NO ❌",
                    hasAircraftArray ? "YES ✅" : "NO ❌");
      delay(retryDelayMs);
      continue;
    }

    // Optional: count aircraft entries (may be 0 and still valid)
    int n = doc["aircraft"].as<JsonArray>().size();
    double nowVal = doc["now"] | 0.0;

    Serial.printf("🎯 Stream OK ✅ | now=%.1f | ✈️ aircraft=%d\n", nowVal, n);

    tft.startWrite();
    drawBottomBarTextDiff("                      Data stream OK.......");
    tft.endWrite();
    Serial.println("");
    return true;
  }

  Serial.println("⏳❌ Stream check TIMEOUT: no valid aircraft JSON received.");

  tft.startWrite();
  drawBottomBarTextDiff("                  Stream timeout (no valid JSON stream)");
  tft.endWrite();
  delay(2000);
  tft.startWrite();
  drawBottomBarTextDiff("                         Rebooting.......");
  tft.endWrite();
  delay(2000);
  ESP.restart();
  return false;
}
static void wifiBannerToTFT(const char *msg)
{
  tft.startWrite();
  drawBottomBarTextDiff(msg);
  tft.endWrite();
}
// ===================== Setup / Loop =====================
void setup()
{
  Serial.begin(115200);
  tft.init();
  tft.setRotation(1);
  tft.invertDisplay(HB9_TFT_INVERT);
  tft.fillScreen(TFT_BLACK);
  tft.setSwapBytes(true);
  backlightInit();

  prefs.begin(PREF_NS, false);
  gBl = prefs.getUChar(PREF_KEY_BL, HB9_BL_DEFAULT_PERCENT);
  gBlSaved = gBl;
  backlightSetPercent(gBl);

  displaySplashScreen(2000);
  setWifiStatusBannerCallback(wifiBannerToTFT);

  HB9IIUWifiConnection();

  // Block here until we see a valid JSON stream (or timeout)
  waitForValidAircraftStream(10000, 800); // 20s max, retry every 0.8s

  delay(4000);
}

void loop()
{

  handleTouchBrightnessAndSave();

  static uint32_t lastFetch = 0;
  const uint32_t now = millis();

  if (WiFi.status() != WL_CONNECTED)
  {
    delay(250);
    return;
  }

  if ((now - lastFetch) >= FETCH_PERIOD_MS)
  {
    lastFetch = now;

    bool ok = fetchAndUpdateTracks();
    if (ok)
    {
      renderTracks();
    }
  }

  delay(5);
}
