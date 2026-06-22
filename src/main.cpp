

/*******************************************************
*                                                     *
*   ⚠️  WORK IN PROGRESS! ⚠️                          *
*                                                     *
*   This file is a wild experiment zone.               *
*   Please be patient, tolerant, and bring snacks.     *
*   It's just a hobby project, not a NASA launch!      *
*                                                     *
*   If you find bugs, they're probably features.       *
*   If you find features, they're probably accidental. *
*                                                     *
*   Enjoy, and don't take it too seriously!            *
*                                                     *
*******************************************************/

#include <config.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>
#include <TJpg_Decoder.h>
#include <SPI.h>
#include <pgmspace.h>
#include <math.h>
#include "background565.h"
#include <HB9IIU_BacklightControl.h>
#include <HB9IIUportalBasic.h>
#include "HB9IIU_RobustTimeAquisition.h"
#include "splash565.h"
#include <Preferences.h>
#include <time.h>

#include "A032_360.h"
#include "A132_360.h"
#include "A232_360.h"
#include "A332_360.h"
#include "A432_360.h"
#include "A532_360.h"
#include "A632_360.h"
#include "A732_360.h"
#include "B032_360.h"
#include "B132_360.h"
#include "B232_360.h"
#include "NA32_360.h"

#include "JetBrainsMono_Medium15pt7b.h"
#include "JetBrainsMono_Medium22pt7b.h"
#include "JetBrainsMono_SemiBold18pt7b.h"
#include "SFMonoSemibold124px7b.h"



// Track storage limit
static const int MAX_TRACKS = 200;

// How many planes to actually DRAW each refresh (performance knob)
static const int MAX_DRAW = 99;

// ===================== Stats TFT JSON =====================
struct StatsTft
{
  int aircraft_in_view = 0;
  float closest_record_km = 0;
  float farthest_km = 0;
  float farthest_record_km = 0;
  int fastest_kmh = 0;
  int fastest_record_kmh = 0;
  int highest_alt_m = 0;
  int highest_record_m = 0;
  float nearest_km = 0;
  int peak_record = 0;
  int peak_today = 0;
  int unique_ever = 0;
  int unique_today = 0;
  unsigned long uptime = 0;
  char uptime_str[32] = {0};
};
static StatsTft gStatsTft;

static bool fetchStatsTft()
{
  String url = String(ADSB_JSON_STREAM_URL);
  int schemeIdx = url.indexOf("://");
  int hostStart = (schemeIdx >= 0) ? schemeIdx + 3 : 0;
  int slashIdx = url.indexOf('/', hostStart);
  if (slashIdx >= 0)
  {
    url = url.substring(0, slashIdx);
  }
  url += "/stats_tft.json";

  HTTPClient http;
  http.setTimeout(4000);
  http.setReuse(false);
  http.begin(url);
  int code = http.GET();
  if (code != 200)
  {
    Serial.printf("STATS_TFT http=%d url=%s\n", code, url.c_str());
    http.end();
    return false;
  }
  WiFiClient *stream = http.getStreamPtr();
  JsonDocument doc;
  JsonDocument filter;
  filter["aircraft_in_view"] = true;
  filter["closest_record_km"] = true;
  filter["farthest_km"] = true;
  filter["farthest_record_km"] = true;
  filter["fastest_kmh"] = true;
  filter["fastest_record_kmh"] = true;
  filter["highest_alt_m"] = true;
  filter["highest_record_m"] = true;
  filter["nearest_km"] = true;
  filter["peak_record"] = true;
  filter["peak_today"] = true;
  filter["unique_ever"] = true;
  filter["unique_today"] = true;
  filter["uptime"] = true;
  filter["uptime_str"] = true;
  DeserializationError err = deserializeJson(doc, *stream, DeserializationOption::Filter(filter));
  http.end();
  if (err)
  {
    Serial.printf("STATS_TFT JSON error: %s\n", err.c_str());
    return false;
  }
  gStatsTft.aircraft_in_view = doc["aircraft_in_view"] | 0;
  gStatsTft.closest_record_km = doc["closest_record_km"] | 0.0f;
  gStatsTft.farthest_km = doc["farthest_km"] | 0.0f;
  gStatsTft.farthest_record_km = doc["farthest_record_km"] | 0.0f;
  gStatsTft.fastest_kmh = doc["fastest_kmh"] | 0;
  gStatsTft.fastest_record_kmh = doc["fastest_record_kmh"] | 0;
  gStatsTft.highest_alt_m = doc["highest_alt_m"] | 0;
  gStatsTft.highest_record_m = doc["highest_record_m"] | 0;
  gStatsTft.nearest_km = doc["nearest_km"] | 0.0f;
  gStatsTft.peak_record = doc["peak_record"] | 0;
  gStatsTft.peak_today = doc["peak_today"] | 0;
  gStatsTft.unique_ever = doc["unique_ever"] | 0;
  gStatsTft.unique_today = doc["unique_today"] | 0;
  gStatsTft.uptime = doc["uptime"] | 0UL;
  const char *us = doc["uptime_str"] | "";
  strncpy(gStatsTft.uptime_str, us, sizeof(gStatsTft.uptime_str) - 1);
  gStatsTft.uptime_str[sizeof(gStatsTft.uptime_str) - 1] = 0;

  // Print all fields for debug
  Serial.printf("STATS_TFT: in_view=%d closest=%.1f farthest=%.1f farthest_record=%.1f fastest=%d fastest_record=%d highest=%d highest_record=%d nearest=%.1f peak_record=%d peak_today=%d unique_ever=%d unique_today=%d uptime=%lu uptime_str=%s\n",
                gStatsTft.aircraft_in_view, gStatsTft.closest_record_km, gStatsTft.farthest_km, gStatsTft.farthest_record_km,
                gStatsTft.fastest_kmh, gStatsTft.fastest_record_kmh, gStatsTft.highest_alt_m, gStatsTft.highest_record_m,
                gStatsTft.nearest_km, gStatsTft.peak_record, gStatsTft.peak_today, gStatsTft.unique_ever, gStatsTft.unique_today,
                gStatsTft.uptime, gStatsTft.uptime_str);
  return true;
}

// Ignore stale positions older than this (seconds, from JSON seen_pos)
static const double MAX_SEEN_POS_S = 30.0;
// "Total aircraft" count uses JSON field "seen" (can be older than position)
static const double MAX_SEEN_S = 60.0;

// Remove/erase planes if not updated for this long (ms)
static const uint32_t TRACK_TTL_MS = 15000;

// Refresh interval (ms)
static const uint32_t FETCH_PERIOD_MS = 2000;

// Outdoor temperature refresh interval (15 min)
static const uint32_t METEO_REFRESH_MS = 15UL * 60UL * 1000UL;

// Range filter (km) just to reject far aircraft early (optional)
static const double RANGE_KM = 500.0;

// Debug prints
static const bool DEBUG_FETCH = false;
static const bool DEBUG_TRACKS = false;
static const bool DEBUG_HEADING_MAP = false; // prints heading mapping
static const bool DEBUG_META = false;
static const bool DEBUG_HEAP = false;
static const uint32_t HEAP_LOG_INTERVAL_MS = 5000;
static const bool DEBUG_TOUCH = false;
static const bool DEBUG_TRACKS_DUMP = false;
static const bool DEBUG_DRAWLIST = false;

// ===================== Stats for bottom bar =====================
// Total aircraft entries in JSON, how many have position, how many are drawn
static volatile int gTotalRaw = 0;
static volatile int gWithPos = 0;
static volatile int gSeen = 0;
static char gCategory[4] = "NA";
static int gDrawIdxCache[MAX_DRAW];
static int gDrawCount = 0;
static char gInfoText[96] = {0};
static bool gInfoActive = false;
static uint32_t gInfoUntilMs = 0;
static const uint32_t INFO_HOLD_MS = 4000;

static void drawBottomBarTextDiff(const char *text);

// Forward declaration for stats page drawing
static void drawStatsPage();

// ===================== TFT / Sprites =====================
TFT_eSPI tft = TFT_eSPI();

static const int SW = 480;
static const int SH = 320;

static const int PW = A032_w;
static const int PH = A032_h;

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

static const bool ENABLE_BOTTOM_BAR = true;

// ===================== Metadata =====================
static bool fetchMetaForSelected();
static const uint32_t META_FETCH_MIN_MS = 30000;

enum PageId
{
  PAGE_MAIN = 0,
  PAGE_2,
  PAGE_3,
  PAGE_4,
  PAGE_CLOCK
};

static PageId gPage = PAGE_MAIN;
static uint32_t gLastPageTouchMs = 0;
static const uint32_t PAGE_TOUCH_DEBOUNCE_MS = 50;

// ===================== Screensaver =====================
static const uint32_t SCREENSAVER_TIMEOUT_MS = 60000; // 30 s of no touch
static uint32_t gLastActivityMs  = 0;
static bool     gClockFullRedraw = true; // set true whenever we enter PAGE_CLOCK
static const int BRIGHT_BOX      = 40;  // px: corner tap zone for brightness control

static const int      CLK_COLON_NUDGE   = -12; // px: left-shift ':' glyph to visually center it between H2 and M1
static const int      CLK_COLON_SHRINK  =  20; // px: total reduction of ':' slot (10 each side)

// Clock colour palette — cycled by top-centre tap (colour-wheel order, maximally distinct)
static const uint16_t CLK_PALETTE[] = {
  0xFFFF,  // White       — RGB(255,255,255)
  0xFFE0,  // Yellow      — RGB(255,255,  0)
  0x87E0,  // Lime        — RGB(132,255,  0)
  0x07E0,  // Green       — RGB(  0,255,  0)
  0x07FF,  // Cyan        — RGB(  0,255,255)
  0x5D1F,  // Blue        — RGB( 88,160,248)
  0x901A,  // Purple      — RGB(144,  0,208)
  0xF81F,  // Magenta     — RGB(255,  0,255)
  0xF800,  // Red         — RGB(255,  0,  0)
  0xFD20,  // Orange      — RGB(255,165,  0)
};
static const int CLK_PALETTE_SIZE = (int)(sizeof(CLK_PALETTE) / sizeof(CLK_PALETTE[0]));
static int       gClockColorIdx   = 0;
  
// ===================== Helpers =====================
static inline double deg2rad(double d) { return d * (PI / 180.0); }
static inline double rad2deg(double r) { return r * (180.0 / PI); }

static void logHeapTag(const char *tag)
{
  if (!DEBUG_HEAP)
    return;
  Serial.printf("HEAP %s free=%u min=%u maxAlloc=%u\n",
                tag,
                ESP.getFreeHeap(),
                ESP.getMinFreeHeap(),
                ESP.getMaxAllocHeap());
}

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
struct PlaneSet
{
  const uint8_t *masks;
  const uint16_t *offset;
  int w;
  int h;
  int stride;
};

#define PLANESET16(prefix) {prefix##_masks, prefix##_offset, prefix##_w, prefix##_h, prefix##_stride}

static const PlaneSet PLANE_A0 = PLANESET16(A032);
static const PlaneSet PLANE_A1 = PLANESET16(A132);
static const PlaneSet PLANE_A2 = PLANESET16(A232);
static const PlaneSet PLANE_A3 = PLANESET16(A332);
static const PlaneSet PLANE_A4 = PLANESET16(A432);
static const PlaneSet PLANE_A5 = PLANESET16(A532);
static const PlaneSet PLANE_A6 = PLANESET16(A632);
static const PlaneSet PLANE_A7 = PLANESET16(A732);
static const PlaneSet PLANE_B0 = PLANESET16(B032);
static const PlaneSet PLANE_B1 = PLANESET16(B132);
static const PlaneSet PLANE_B2 = PLANESET16(B232);
static const PlaneSet PLANE_NA = PLANESET16(NA32);

static inline const PlaneSet &planeForCategory(const char *category)
{
  if (!category || category[0] == '\0')
    return PLANE_NA;

  if (category[0] == 'A')
  {
    switch (category[1])
    {
    case '0':
      return PLANE_A0;
    case '1':
      return PLANE_A1;
    case '2':
      return PLANE_A2;
    case '3':
      return PLANE_A3;
    case '4':
      return PLANE_A4;
    case '5':
      return PLANE_A5;
    case '6':
      return PLANE_A6;
    case '7':
      return PLANE_A7;
    default:
      return PLANE_NA;
    }
  }

  if (category[0] == 'B')
  {
    switch (category[1])
    {
    case '0':
      return PLANE_B0;
    case '1':
      return PLANE_B1;
    case '2':
      return PLANE_B2;
    default:
      return PLANE_NA;
    }
  }

  return PLANE_NA;
}

static inline const uint8_t *planeMaskForHeading(const PlaneSet &p, int headingDeg)
{
  headingDeg %= 360;
  if (headingDeg < 0)
    headingDeg += 360;

  uint16_t off = 0;
  memcpy_P(&off, &p.offset[headingDeg], sizeof(p.offset[headingDeg]));
  return p.masks + off;
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

void drawPlaneAtTopLeft(int x0, int y0, const PlaneSet &plane, int spriteHeadingDeg, uint16_t color)
{
  const uint8_t *maskPtr = planeMaskForHeading(plane, spriteHeadingDeg);
  drawMask1bit_PROGMEM(x0, y0, maskPtr, plane.w, plane.h, plane.stride, color);
}

// ===================== Track table =====================
struct Track
{
  bool used = false;

  char hex[7] = {0};    // 6 hex chars + null
  char flight[9] = {0}; // up to 8 + null
  char category[4] = "NA";

  double lat = 0;
  double lon = 0;

  int cx = 0, cy = 0; // center screen position
  int oldDrawX = 0, oldDrawY = 0;

  int headingDeg = 0; // 0..359 from ADS-B track

  int altitude_m = -1; // barometric altitude (meters), -1 = unknown

  double gs_kts = -1.0; // ground speed in knots, -1 = unknown

  uint16_t color = TFT_WHITE;

  uint32_t lastUpdateMs = 0; // millis() when updated
  bool drawn = false;
};

struct SelectedPlane
{
  bool valid = false;
  char hex[7] = {0};
  char flight[9] = {0};
  char category[4] = "NA";
  double lat = 0;
  double lon = 0;
  int headingDeg = 0;
  int altitude_m = -1;
  double gs_kts = -1.0;
};

struct MetaInfo
{
  bool valid = false;
  char icaoType[8] = {0};
  char country[32] = {0};
  char manufacturer[32] = {0};
  char modeS[8] = {0};
  char operatorFlag[8] = {0};
  char owner[48] = {0};
  char registration[16] = {0};
  char type[32] = {0};
  char flag_rgb565[24] = {0};
  uint32_t first_seen = 0;
  uint32_t last_seen = 0;
};

static SelectedPlane gSelected;
static MetaInfo gMeta;
static uint32_t gMetaFetchMs = 0;

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
      if (gSelected.valid && strncmp(tracks[i].hex, gSelected.hex, 6) == 0)
        gSelected.valid = false;
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

  if (DEBUG_DRAWLIST)
  {
    Serial.printf("DRAWLIST count=%d\n", count);
    for (int i = 0; i < count; i++)
    {
      const Track &t = tracks[outIdx[i]];
      Serial.printf("  dl %s %s cx=%d cy=%d alt=%d hdg=%d\n",
                    t.hex,
                    t.flight,
                    t.cx,
                    t.cy,
                    t.altitude_m,
                    t.headingDeg);
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
    const PlaneSet &plane = planeForCategory(t.category);
    drawPlaneAtTopLeft(x0, y0, plane, spriteHeading, t.color);

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
          "T%02d %s %-8s cat=%-2s alt=%6dm  d=%.1fkm brg=%.0f  lat=%.5f lon=%.5f  xy=(%d,%d) trk=%d age=%.1fs\n",
          k, t.hex, t.flight, t.category,
          t.altitude_m,
          dkm, brg,
          t.lat, t.lon,
          t.cx, t.cy,
          t.headingDeg, ageS);
    }
  }
}

// ===================== Outdoor temperature refresh ===============
static void fetchMeteoTemp()
{
  if (WiFi.status() != WL_CONNECTED) return;
  char url[256];
  snprintf(url, sizeof(url),
    "https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f&current=temperature_2m&timezone=auto",
    (float)HOME_LAT, (float)HOME_LON);
  HTTPClient http;
  http.begin(url);
  if (http.GET() == 200) {
    JsonDocument doc;
    if (!deserializeJson(doc, http.getStream())) {
      if (!doc["current"]["temperature_2m"].isNull()) {
        gMeteoTempC     = doc["current"]["temperature_2m"].as<float>();
        gMeteoTempValid = true;
        Serial.printf("🌡 Meteo refresh: %.1f °C\n", gMeteoTempC);
      }
    }
  }
  http.end();
}

// ===================== Network fetch + parse =====================
static bool fetchAndUpdateTracks()
{
  logHeapTag("fetch.begin");
  if (WiFi.status() != WL_CONNECTED)
    return false;

  const uint32_t t0 = millis();

  HTTPClient http;
  http.setTimeout(3500);
  http.setReuse(false);
  http.begin(ADSB_JSON_STREAM_URL);

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
  a0["category"] = true;
  a0["gs"] = true;

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

    const char *category = a["category"] | "";
    if (category[0])
    {
      strncpy(gCategory, category, sizeof(gCategory) - 1);
      gCategory[sizeof(gCategory) - 1] = 0;
    }
    else
    {
      strncpy(gCategory, "NA", sizeof(gCategory) - 1);
      gCategory[sizeof(gCategory) - 1] = 0;
    }

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

    strncpy(t.category, gCategory, sizeof(t.category) - 1);
    t.category[sizeof(t.category) - 1] = 0;

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

    if (a["gs"].is<double>())
    {
      t.gs_kts = a["gs"].as<double>();
    }
    else if (a["gs"].is<int>())
    {
      t.gs_kts = (double)a["gs"].as<int>();
    }
    else
    {
      t.gs_kts = -1.0;
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
  logHeapTag("fetch.end");
  return true;
}

static const char *trackLabel(const Track &t)
{
  // Prefer callsign, else fall back to hex
  return (t.flight[0] != 0) ? t.flight : t.hex;
}

static char bottomPrev[96] = {0}; // previous rendered string
static bool bottomHasPrev = false;

static void showSelectionBanner(const Track &t)
{
  double dkm = haversine_km(HOME_LAT, HOME_LON, t.lat, t.lon);
  double brg = bearing_deg(HOME_LAT, HOME_LON, t.lat, t.lon);

  if (t.altitude_m >= 0)
  {
    snprintf(gInfoText, sizeof(gInfoText),
             "SEL %s %s alt=%dm d=%.1fkm brg=%.0f",
             trackLabel(t), t.category, t.altitude_m, dkm, brg);
  }
  else
  {
    snprintf(gInfoText, sizeof(gInfoText),
             "SEL %s %s alt=--- d=%.1fkm brg=%.0f",
             trackLabel(t), t.category, dkm, brg);
  }

  gInfoActive = true;
  gInfoUntilMs = millis() + INFO_HOLD_MS;
  tft.startWrite();
  drawBottomBarTextDiff(gInfoText);
  tft.endWrite();
}

static void copySelectedFromTrack(const Track &t)
{
  gSelected.valid = true;
  strncpy(gSelected.hex, t.hex, sizeof(gSelected.hex) - 1);
  gSelected.hex[sizeof(gSelected.hex) - 1] = 0;
  strncpy(gSelected.flight, t.flight, sizeof(gSelected.flight) - 1);
  gSelected.flight[sizeof(gSelected.flight) - 1] = 0;
  strncpy(gSelected.category, t.category, sizeof(gSelected.category) - 1);
  gSelected.category[sizeof(gSelected.category) - 1] = 0;
  gSelected.lat = t.lat;
  gSelected.lon = t.lon;
  gSelected.headingDeg = t.headingDeg;
  gSelected.altitude_m = t.altitude_m;
  gSelected.gs_kts = t.gs_kts;

  fetchMetaForSelected();

  if (DEBUG_META)
  {
    Serial.printf("SELECT plane: hex=%s flight=%s cat=%s alt=%d gs=%.0f\n",
                  gSelected.hex, gSelected.flight, gSelected.category,
                  gSelected.altitude_m, gSelected.gs_kts);
  }
}

static bool handlePlaneTouch(int touchX, int touchY)
{
  if (gDrawCount <= 0)
    return false;

  if (DEBUG_TOUCH)
  {
    Serial.printf("TOUCH pick: x=%d y=%d drawCount=%d\n", touchX, touchY, gDrawCount);
  }

  if (DEBUG_TRACKS_DUMP)
  {
    int usedCount = 0;
    for (int i = 0; i < MAX_TRACKS; i++)
      if (tracks[i].used)
        usedCount++;

    Serial.printf("DUMP touch x=%d y=%d used=%d drawn=%d\n", touchX, touchY, usedCount, gDrawCount);
    for (int i = 0; i < MAX_TRACKS; i++)
    {
      if (!tracks[i].used)
        continue;
      Serial.printf("  trk %s %s cx=%d cy=%d lat=%.5f lon=%.5f hdg=%d\n",
                    tracks[i].hex,
                    tracks[i].flight,
                    tracks[i].cx,
                    tracks[i].cy,
                    tracks[i].lat,
                    tracks[i].lon,
                    tracks[i].headingDeg);
    }
  }

  int bestIdx = -1;
  int bestD2 = 0x7fffffff;

  for (int i = 0; i < gDrawCount; i++)
  {
    Track &t = tracks[gDrawIdxCache[i]];
    if (!t.used)
      continue;

    int x0 = t.cx - PW / 2;
    int y0 = t.cy - PH / 2;

    if (touchX < x0 || touchX >= (x0 + PW))
      continue;
    if (touchY < y0 || touchY >= (y0 + PH))
      continue;

    int dx = touchX - t.cx;
    int dy = touchY - t.cy;
    int d2 = dx * dx + dy * dy;

    if (d2 < bestD2)
    {
      bestD2 = d2;
      bestIdx = gDrawIdxCache[i];
    }

    if (DEBUG_TOUCH)
    {
      Serial.printf("  hit %s %s cx=%d cy=%d d2=%d\n",
                    t.hex, t.flight, t.cx, t.cy, d2);
    }
  }

  if (bestIdx >= 0)
  {
    if (DEBUG_TOUCH)
    {
      Track &bt = tracks[bestIdx];
      Serial.printf("  select %s %s cx=%d cy=%d\n",
                    bt.hex, bt.flight, bt.cx, bt.cy);
    }
    if (DEBUG_TRACKS_DUMP)
    {
      Track &bt = tracks[bestIdx];
      Serial.printf("DUMP decision: select hex=%s flight=%s cx=%d cy=%d\n",
                    bt.hex, bt.flight, bt.cx, bt.cy);
    }
    copySelectedFromTrack(tracks[bestIdx]);
    return true;
  }

  if (DEBUG_TOUCH)
  {
    Serial.println("  no hit");
  }

  if (DEBUG_TRACKS_DUMP)
  {
    Serial.println("DUMP decision: select none");
  }

  return false;
}

static void formatEpoch(uint32_t epoch, char *out, size_t outLen)
{
  if (!out || outLen == 0)
    return;
  if (epoch == 0)
  {
    strncpy(out, "---", outLen - 1);
    out[outLen - 1] = 0;
    return;
  }

  time_t t = (time_t)epoch;
  struct tm tmv;
  if (!gmtime_r(&t, &tmv))
  {
    strncpy(out, "---", outLen - 1);
    out[outLen - 1] = 0;
    return;
  }

  snprintf(out, outLen, "%02d.%02d.%02d %02d:%02d",
           tmv.tm_mday, tmv.tm_mon + 1, (tmv.tm_year + 1900) % 100,
           tmv.tm_hour, tmv.tm_min);
}

static String buildMetaUrl(const char *hex)
{
  String url(ADSB_JSON_STREAM_URL);
  int schemeIdx = url.indexOf("://");
  int hostStart = (schemeIdx >= 0) ? schemeIdx + 3 : 0;
  int slashIdx = url.indexOf('/', hostStart);
  if (slashIdx >= 0)
  {
    url = url.substring(0, slashIdx);
  }
  url += "/hex/";
  url += hex;
  url += ".json";
  return url;
}

static String buildMetaImageUrl(const char *hex)
{
  String url(ADSB_JSON_STREAM_URL);
  int schemeIdx = url.indexOf("://");
  int hostStart = (schemeIdx >= 0) ? schemeIdx + 3 : 0;
  int slashIdx = url.indexOf('/', hostStart);
  if (slashIdx >= 0)
  {
    url = url.substring(0, slashIdx);
  }
  url += "/jpg/";
  url += hex;
  url += ".jpg";
  return url;
}

static bool fetchMetaForSelected()
{
  logHeapTag("meta.begin");
  if (!gSelected.valid || !gSelected.hex[0])
    return false;

  const uint32_t now = millis();
  if (gMeta.valid && strncmp(gMeta.modeS, gSelected.hex, 6) == 0)
  {
    if ((now - gMetaFetchMs) < META_FETCH_MIN_MS)
      return true;
  }
  else
  {
    memset(&gMeta, 0, sizeof(gMeta));
    gMeta.valid = false;
  }

  String url = buildMetaUrl(gSelected.hex);

  if (DEBUG_META)
  {
    Serial.printf("META fetch: hex=%s url=%s\n", gSelected.hex, url.c_str());
  }

  HTTPClient http;
  http.setTimeout(3500);
  http.setReuse(false);
  http.begin(url);

  int code = http.GET();
  if (code != 200)
  {
    if (DEBUG_META)
      Serial.printf("META http=%d\n", code);
    http.end();
    memset(&gMeta, 0, sizeof(gMeta));
    gMeta.valid = false;
    return false;
  }

  JsonDocument filter;
  filter["first_seen"] = true;
  filter["last_seen"] = true;
  filter["hex"] = true;
  filter["country"] = true;
  filter["flag_rgb565"] = true;
  JsonObject h = filter["hexdb"].to<JsonObject>();
  h["ICAOTypeCode"] = true;
  h["Manufacturer"] = true;
  h["ModeS"] = true;
  h["OperatorFlagCode"] = true;
  h["RegisteredOwners"] = true;
  h["Registration"] = true;
  h["Type"] = true;
  h["Country"] = true;

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, *http.getStreamPtr(),
                                             DeserializationOption::Filter(filter));
  http.end();

  if (err)
  {
    if (DEBUG_META)
      Serial.printf("META json error: %s\n", err.c_str());
    memset(&gMeta, 0, sizeof(gMeta));
    gMeta.valid = false;
    return false;
  }

  // Print the full parsed JSON for debugging
  if (DEBUG_META)
  {
    Serial.println("META full JSON:");
    serializeJsonPretty(doc, Serial);
    Serial.println();
  }

  memset(&gMeta, 0, sizeof(gMeta));
  gMeta.valid = true;
  gMeta.first_seen = doc["first_seen"] | 0;
  gMeta.last_seen = doc["last_seen"] | 0;

  JsonObject hexdb = doc["hexdb"].as<JsonObject>();
  const char *s = nullptr;

  s = doc["hex"] | "";
  strncpy(gMeta.modeS, s, sizeof(gMeta.modeS) - 1);

  s = hexdb["ICAOTypeCode"] | "";
  strncpy(gMeta.icaoType, s, sizeof(gMeta.icaoType) - 1);
  s = hexdb["Manufacturer"] | "";
  strncpy(gMeta.manufacturer, s, sizeof(gMeta.manufacturer) - 1);
  s = hexdb["ModeS"] | "";
  if (s && s[0])
    strncpy(gMeta.modeS, s, sizeof(gMeta.modeS) - 1);
  s = hexdb["OperatorFlagCode"] | "";
  strncpy(gMeta.operatorFlag, s, sizeof(gMeta.operatorFlag) - 1);
  s = hexdb["RegisteredOwners"] | "";
  strncpy(gMeta.owner, s, sizeof(gMeta.owner) - 1);
  s = hexdb["Registration"] | "";
  strncpy(gMeta.registration, s, sizeof(gMeta.registration) - 1);
  s = hexdb["Type"] | "";
  strncpy(gMeta.type, s, sizeof(gMeta.type) - 1);
  s = doc["country"] | "";
  strncpy(gMeta.country, s, sizeof(gMeta.country) - 1);

  s = doc["flag_rgb565"] | "";
  strncpy(gMeta.flag_rgb565, s, sizeof(gMeta.flag_rgb565) - 1);

  gMetaFetchMs = now;

  if (DEBUG_META)
  {
    Serial.printf("META ok: hex=%s reg=%s type=%s mfg=%s owner=%s country=%s first=%lu last=%lu\n",
                  gMeta.modeS, gMeta.registration, gMeta.type,
                  gMeta.manufacturer, gMeta.owner, gMeta.country,
                  (unsigned long)gMeta.first_seen,
                  (unsigned long)gMeta.last_seen);
  }
  logHeapTag("meta.end");
  return true;
}

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
  if (gInfoActive)
  {
    if ((int32_t)(millis() - gInfoUntilMs) < 0)
    {
      drawBottomBarTextDiff(gInfoText);
      return;
    }
    gInfoActive = false;
  }

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

  gDrawCount = nDraw;
  for (int i = 0; i < nDraw; i++)
  {
    gDrawIdxCache[i] = drawIdx[i];
    
  }

  // Build dirty rectangles:
  // - for each plane we will draw: its old rect (if previously drawn) and its new rect
  // - for planes that were drawn but are no longer in draw list: their old rect
  static Rect dirty[2 * MAX_DRAW + MAX_DRAW]; // enough for old+new + removed
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
  if (ENABLE_BOTTOM_BAR)
  {
    updateBottomBar(drawIdx, nDraw);
  }
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

static void drawPageLabel(const char *label)
{
  tft.fillScreen(TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString(label, SW / 2, SH / 2);
}

static const char *bearingToDir8(double deg)
{
  // Normalize into [0,360)
  while (deg < 0)
    deg += 360.0;
  while (deg >= 360.0)
    deg -= 360.0;

  // 8-wind compass, 45° sectors centered on N/NE/E/...
  static const char *kDir8[] = {
      "north",
      "north-east",
      "east",
      "south-east",
      "south",
      "south-west",
      "west",
      "north-west",
  };

  const int idx = (int)((deg + 22.5) / 45.0) & 7;
  return kDir8[idx];
}

static void drawPlaneInfoPage()
{

  tft.fillScreen(TFT_BLACK);

  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);

  // PAGE_2 layout controls
  const int leftMargin = 12; // adjust this to shift both columns left/right
  const int rightMargin = 12;
  const int colGap = 18;
  const int bottomMargin = 12;

// Top banner
// Use a bigger FreeFont for the banner title.
#ifdef LOAD_GFXFF
  tft.setFreeFont(&JetBrainsMono_Medium22pt7b);
#endif

  int bannerH = 24;
#ifdef LOAD_GFXFF
  bannerH = tft.fontHeight() + 10;
#endif
  tft.fillRect(0, 0, SW, bannerH, TFT_DARKGREY);
  tft.setTextColor(TFT_WHITE, TFT_DARKGREY);
  {
    const char *bannerTitle = "AIRCRAFT INFO";
    tft.setTextDatum(MC_DATUM);
    tft.drawString(bannerTitle, SW / 2, bannerH / 2);
    tft.setTextDatum(TL_DATUM);
  }
  tft.setTextColor(TFT_WHITE, TFT_BLACK);

  const int topMargin = bannerH + 28; // YYYYYY

// Use a smaller FreeFont for the PAGE_2 body text.
#ifdef LOAD_GFXFF
  tft.setFreeFont(&JetBrainsMono_Medium15pt7b);
#endif

  int dy = 16;
  int startY = topMargin;
#ifdef LOAD_GFXFF
  // Note: with FreeFonts, y is treated as a baseline in TFT_eSPI.
  dy = tft.fontHeight() + 4;
  startY = topMargin + tft.fontHeight();
#endif

  const int colW = (SW - leftMargin - rightMargin - colGap) / 2;
  const int colX0 = leftMargin;
  const int colX1 = leftMargin + colW + colGap - 20;
  const int yMax = SH - bottomMargin;

  int col = 0;
  int x = colX0;
  int y = startY;

  auto newColumnIfNeeded = [&]()
  {
    if (y + dy <= yMax)
      return;
    if (col == 0)
    {
      col = 1;
      x = colX1;
      y = startY;
    }
  };

  auto put = [&](const char *s)
  {
    newColumnIfNeeded();
    tft.drawString(s, x, y);
    y += dy;
  };

  auto gap = [&](int extra)
  {
    y += extra;
  };

  char line[96];

  snprintf(line, sizeof(line), "ICAO: %s", gSelected.hex[0] ? gSelected.hex : "---");
  put(line);

  snprintf(line, sizeof(line), "CALL: %s", gSelected.flight[0] ? gSelected.flight : "---");
  put(line);

  snprintf(line, sizeof(line), "REG: %s", gMeta.registration[0] ? gMeta.registration : "---");
  put(line);

  snprintf(line, sizeof(line), "COUNTRY: %s", gMeta.country[0] ? gMeta.country : "---");
  put(line);

  if (gSelected.altitude_m >= 0)
    snprintf(line, sizeof(line), "ALT: %d m", gSelected.altitude_m);
  else
    snprintf(line, sizeof(line), "ALT: ---");
  put(line);

  if (gSelected.gs_kts >= 0.0)
    snprintf(line, sizeof(line), "SPD: %.0f km/h", gSelected.gs_kts * 1.852);
  else
    snprintf(line, sizeof(line), "SPD: ---");
  put(line);

  double dkm = haversine_km(HOME_LAT, HOME_LON, gSelected.lat, gSelected.lon);
  double brg = bearing_deg(HOME_LAT, HOME_LON, gSelected.lat, gSelected.lon);
  snprintf(line, sizeof(line), "DST: %.1f km", dkm);
  put(line);
  snprintf(line, sizeof(line), "BRG: %.0f deg (%s)", brg, bearingToDir8(brg));
  put(line);
  gap(4);

  snprintf(line, sizeof(line), "TYPE: %s", gMeta.type[0] ? gMeta.type : "---");
  put(line);

  snprintf(line, sizeof(line), "MFG: %s", gMeta.manufacturer[0] ? gMeta.manufacturer : "---");
  put(line);

  snprintf(line, sizeof(line), "OP: %s", gMeta.operatorFlag[0] ? gMeta.operatorFlag : "---");
  put(line);

  snprintf(line, sizeof(line), "OWNER: %s", gMeta.owner[0] ? gMeta.owner : "---");
  put(line);

  char tsFirst[24];
  char tsLast[24];
  formatEpoch(gMeta.first_seen, tsFirst, sizeof(tsFirst));
  formatEpoch(gMeta.last_seen, tsLast, sizeof(tsLast));
  snprintf(line, sizeof(line), "FIRST: %s", tsFirst);
  put(line);

  snprintf(line, sizeof(line), "LAST:  %s", tsLast);
  put(line);

// Restore default built-in font for other pages
#ifdef LOAD_GFXFF
  tft.setFreeFont(NULL);
#endif

  // Show "Searching..." before flag + route fetches
  {
    const char *searching = "Searching Route Detail...";
    tft.setFreeFont(&JetBrainsMono_Medium15pt7b);
    tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
    tft.drawString(searching, (SW - tft.textWidth(searching)) / 2, 45);
    tft.setFreeFont(NULL);
  }

  // --- FLAG IMAGE RENDERING (JPEG) ---
  // flag_rgb565 holds ISO2 code like "ch.rgb565" or "ch"
  // We fetch /flags/<iso2>.jpg and decode with TJpgDec
  if (gMeta.flag_rgb565[0])
  {
    // Strip extension to get bare ISO2 code
    String isoCode(gMeta.flag_rgb565);
    int dotIdx = isoCode.indexOf('.');
    if (dotIdx > 0) isoCode = isoCode.substring(0, dotIdx);

    // Build URL: http://<host>/flags/<iso2>.jpg
    String url(ADSB_JSON_STREAM_URL);
    int schemeIdx = url.indexOf("://");
    int hostStart = (schemeIdx >= 0) ? schemeIdx + 3 : 0;
    int slashIdx = url.indexOf('/', hostStart);
    if (slashIdx >= 0) url = url.substring(0, slashIdx);
    url += "/flags/" + isoCode + ".jpg";

    Serial.printf("[FLAG] Fetching %s\n", url.c_str());

    HTTPClient http;
    http.setTimeout(4000);
    http.setReuse(false);
    http.begin(url);
    int code = http.GET();
    if (code == 200)
    {
      int jpgLen = http.getSize();
      if (jpgLen > 0 && jpgLen < 60000)
      {
        uint8_t *jpgBuf = (uint8_t *)malloc(jpgLen);
        if (jpgBuf)
        {
          WiFiClient *stream = http.getStreamPtr();
          int got = stream->readBytes(jpgBuf, jpgLen);
          if (got == jpgLen)
          {
            int x0 = 240 + 130 / 2, y0 = 210;
            TJpgDec.drawJpg(x0, y0, jpgBuf, jpgLen);
            Serial.printf("[FLAG] OK (%d bytes)\n", jpgLen);
          }
          else
          {
            Serial.printf("[FLAG] Read short: got %d of %d\n", got, jpgLen);
          }
          free(jpgBuf);
        }
        else
        {
          Serial.printf("[FLAG] malloc failed for %d bytes\n", jpgLen);
        }
      }
      else
      {
        Serial.printf("[FLAG] Bad size: %d\n", jpgLen);
      }
    }
    else
    {
      Serial.printf("[FLAG] HTTP %d for %s\n", code, url.c_str());
    }
    http.end();
  }

  // Fetch route from routeFinder.py Flask app (port 6969)
  {
    String baseUrl = String(ADSB_JSON_STREAM_URL);
    int schemeIdx = baseUrl.indexOf("://");
    int hostStart = (schemeIdx >= 0) ? schemeIdx + 3 : 0;
    int slashIdx = baseUrl.indexOf('/', hostStart);
    String hostOnly = (slashIdx >= 0) ? baseUrl.substring(hostStart, slashIdx) : baseUrl.substring(hostStart);
    // strip any existing port from hostOnly
    int colonIdx = hostOnly.indexOf(':');
    if (colonIdx >= 0) hostOnly = hostOnly.substring(0, colonIdx);
    String icao = gSelected.hex;
    String url = "http://" + hostOnly + ":6969/api/flight/" + icao;
    Serial.print("Fetching: ");
    Serial.println(url);

    HTTPClient http;
    http.setTimeout(5000);
    http.setReuse(false);
    http.begin(url);
    unsigned long routeT0 = millis();
    int code = http.GET();
    Serial.printf("[ROUTE] fetch time: %lu ms\n", millis() - routeT0);
    bool routeDisplayed = false;
    if (code == 200)
    {
      String payload = http.getString();
      Serial.println("/api/<icao> JSON:");
      Serial.println(payload);
      JsonDocument doc;
      DeserializationError err = deserializeJson(doc, payload);
      if (!err)
      {
        const char *line1 = doc["line1"] | "";
        const char *line2 = doc["line2"] | "";
        // Erase "Searching..." by redrawing it in black
        tft.setFreeFont(&JetBrainsMono_Medium15pt7b);
        tft.setTextColor(TFT_BLACK, TFT_BLACK);
        { const char *s = "Searching Route Detail...";
          tft.drawString(s, (SW - tft.textWidth(s)) / 2, 45); }
        tft.setFreeFont(NULL);
        if (line1 && line1[0])
        {
          tft.setFreeFont(&JetBrainsMono_SemiBold18pt7b);
          int16_t x1 = (SW - tft.textWidth(line1)) / 2;
          tft.setTextColor(TFT_WHITE, TFT_BLACK);
          tft.drawString(line1, x1, 45);
          tft.setFreeFont(NULL);
          routeDisplayed = true;
        }
        if (line2 && line2[0])
        {
          tft.setFreeFont(&JetBrainsMono_Medium15pt7b);
          int16_t x2 = (SW - tft.textWidth(line2)) / 2;
          tft.setTextColor(TFT_WHITE, TFT_BLACK);
          tft.drawString(line2, x2, 65);
          tft.setFreeFont(NULL);
        }
      }
      else
      {
        Serial.print("JSON parse error: ");
        Serial.println(err.c_str());
      }
    }
    else
    {
      Serial.printf("/api/<icao> fetch failed: %d\n", code);
    }
    http.end();

    if (!routeDisplayed)
    {
      const char *msg = "No Route Information Available";
      tft.setFreeFont(&JetBrainsMono_Medium15pt7b);
      int16_t xMsg = (SW - tft.textWidth(msg)) / 2;
      tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
      tft.drawString(msg, xMsg, 55);
      tft.setFreeFont(NULL);
    }
  }
}

static bool fetchPlaneImageToTft(const char *hex)
{
  logHeapTag("image.begin");
  if (!hex || !hex[0])
    return false;

  String url = buildMetaImageUrl(hex);
  Serial.printf("[IMG] Fetching %s\n", url.c_str());

  HTTPClient http;
  http.setTimeout(6000);
  http.setReuse(false);
  http.begin(url);

  int code = http.GET();
  if (code != 200)
  {
    Serial.printf("[IMG] HTTP %d\n", code);
    http.end();
    return false;
  }

  int jpgLen = http.getSize();
  if (jpgLen <= 0 || jpgLen > 200000)
  {
    Serial.printf("[IMG] Bad size: %d\n", jpgLen);
    http.end();
    return false;
  }

  uint8_t *jpgBuf = (uint8_t *)malloc(jpgLen);
  if (!jpgBuf)
  {
    Serial.printf("[IMG] malloc failed for %d bytes\n", jpgLen);
    http.end();
    return false;
  }

  unsigned long tStart = millis();
  WiFiClient *stream = http.getStreamPtr();
  int got = stream->readBytes(jpgBuf, jpgLen);
  http.end();

  if (got != jpgLen)
  {
    Serial.printf("[IMG] Read short: got %d of %d\n", got, jpgLen);
    free(jpgBuf);
    return false;
  }

  TJpgDec.drawJpg(0, 0, jpgBuf, jpgLen);
  free(jpgBuf);

  unsigned long tEnd = millis();
  Serial.printf("[IMG] Download+decode: %lu ms  RSSI: %d dBm  size: %d bytes\n",
                tEnd - tStart, WiFi.RSSI(), jpgLen);
  logHeapTag("image.end");
  return true;
}

static void drawPlaneImagePage()
{
  tft.fillScreen(TFT_BLACK);
  if (!gSelected.valid)
  {
    drawPageLabel("NO PLANE");
    return;
  }

  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.drawString("Downloading image...", SW / 2, SH / 2);

  if (DEBUG_META)
  {
    Serial.printf("PAGE3 image for hex=%s flight=%s\n", gSelected.hex, gSelected.flight);
  }

  if (!fetchPlaneImageToTft(gSelected.hex))
  {
    drawPageLabel("NO IMAGE");
  }
}

static void drawClockPage()
{
  time_t now;
  time(&now);
  struct tm tm_info;
  localtime_r(&now, &tm_info);

  // HH:MM
  char timeBuf[6];
  snprintf(timeBuf, sizeof(timeBuf), "%02d:%02d", tm_info.tm_hour, tm_info.tm_min);

  // Ordinal suffix: 1st, 2nd, 3rd, 22nd ...
  int day = tm_info.tm_mday;
  const char *suffix;
  if (day >= 11 && day <= 13)      suffix = "th";
  else switch (day % 10) {
    case 1:  suffix = "st"; break;
    case 2:  suffix = "nd"; break;
    case 3:  suffix = "rd"; break;
    default: suffix = "th"; break;
  }

  // "Sunday 22nd February 2026"
  char dayName[12], monthName[12], dateBuf[48];
  strftime(dayName,   sizeof(dayName),   "%A", &tm_info);
  strftime(monthName, sizeof(monthName), "%B", &tm_info);
  snprintf(dateBuf, sizeof(dateBuf), "%s %d%s %s %d",
           dayName, day, suffix, monthName, tm_info.tm_year + 1900);

  // Persistent state — track what's currently on screen to skip unchanged draws
  static char  prevTimeBuf[6]  = "";
  static char  prevDateBuf[48] = "";
  static float prevTempC       = -999.0f;

  if (gClockFullRedraw) {
    tft.fillScreen(TFT_BLACK);
    memset(prevTimeBuf, 0, sizeof(prevTimeBuf)); // force all digits + colon to be redrawn
    memset(prevDateBuf, 0, sizeof(prevDateBuf));
    prevTempC      = -999.0f;
    gClockFullRedraw = false;
  }

  // ── Time digits ──────────────────────────────────────────────────────────
  uint16_t clr = CLK_PALETTE[gClockColorIdx];
  uint16_t digitColors[5] = { clr, clr, clr, clr, clr };
  tft.setFreeFont(&SFMonoSemibold124px7b);
  int slotW   = tft.textWidth("0");
  int totalW  = 5 * slotW - CLK_COLON_SHRINK;
  int startX  = (SW - totalW) / 2;
  int centerY = SH / 2 - 25;
  int fh      = tft.fontHeight();
  tft.setTextDatum(MC_DATUM);

  // Colon: drawn once on full redraw — it never changes
  if (prevTimeBuf[0] == '\0') {
    int colonX = startX + 2 * slotW + (slotW - CLK_COLON_SHRINK) / 2 + CLK_COLON_NUDGE;
    tft.setTextColor(clr, TFT_BLACK);
    tft.drawString(":", colonX, centerY);
  }

  // Digits: only redraw positions that changed
  int leftX = startX;
  for (int i = 0; timeBuf[i]; i++) {
    int thisSlot = (i == 2) ? (slotW - CLK_COLON_SHRINK) : slotW;
    if (i != 2 && timeBuf[i] != prevTimeBuf[i]) {
      tft.fillRect(leftX, centerY - fh / 2 - 2, thisSlot, fh + 4, TFT_BLACK);
      char ch[2] = { timeBuf[i], '\0' };
      tft.setTextColor(digitColors[i], TFT_BLACK);
      tft.drawString(ch, leftX + thisSlot / 2, centerY);
    }
    leftX += thisSlot;
  }
  tft.setFreeFont(NULL);
  memcpy(prevTimeBuf, timeBuf, sizeof(timeBuf));

  // ── Outdoor temperature ───────────────────────────────────────────────────
  if (gMeteoTempValid && gMeteoTempC != prevTempC) {
    tft.setFreeFont(&JetBrainsMono_SemiBold18pt7b);
    int tempFh = tft.fontHeight();
    tft.fillRect(0, SH - 46 - tempFh - 2, SW, tempFh + 4, TFT_BLACK);
    char tempBuf[16];
    snprintf(tempBuf, sizeof(tempBuf), "Temp. %.1f deg. C", gMeteoTempC);
    tft.setTextColor(TFT_CYAN, TFT_BLACK);
    tft.setTextDatum(BC_DATUM);
    tft.drawString(tempBuf, SW / 2, SH - 46);
    tft.setFreeFont(NULL);
    prevTempC = gMeteoTempC;
  }

  // ── Date ─────────────────────────────────────────────────────────────────
  if (strcmp(dateBuf, prevDateBuf) != 0) {
    tft.setFreeFont(&JetBrainsMono_SemiBold18pt7b);
    int dateFh = tft.fontHeight();
    tft.fillRect(0, SH - 12 - dateFh - 2, SW, dateFh + 4, TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setTextDatum(BC_DATUM);
    tft.drawString(dateBuf, SW / 2, SH - 12);
    tft.setFreeFont(NULL);
    memcpy(prevDateBuf, dateBuf, sizeof(dateBuf));
  }
}

// ===================== Brightness / Prefs globals =====================
Preferences prefs;
static uint8_t        gBl            = HB9_BL_DEFAULT_PERCENT; // current brightness
static uint8_t        gBlSaved       = 255;                     // last saved value (init invalid)
static uint8_t        gBlMain        = HB9_BL_DEFAULT_PERCENT;  // main brightness saved when entering clock page
static bool           gBlDirty       = false;
static uint32_t       gLastTouchMs   = 0;
static const uint32_t BL_SAVE_IDLE_MS  = 5000;
static const char    *PREF_NS          = "ui";
static const char    *PREF_KEY_BL        = "bl";
static const char    *PREF_KEY_BL_CLOCK  = "bl_clk";
static const char    *PREF_KEY_CLR_CLOCK = "cl_clk";

static void setPage(PageId page)
{
  bottomHasPrev = false;
  gPage = page;
  tft.startWrite();
  if (gPage == PAGE_MAIN)
  {
    drawFullBackground();
    drawLegendBar();
  }
  else if (gPage == PAGE_2)
  {
    drawPlaneInfoPage();
  }
  else if (gPage == PAGE_3)
  {
    drawPlaneImagePage();
  }
  else if (gPage == PAGE_4)
  {
    fetchStatsTft();
    drawStatsPage();
  }
  else if (gPage == PAGE_CLOCK)
  {
    gBlMain = gBl;  // remember main brightness
    gBl     = prefs.getUChar(PREF_KEY_BL_CLOCK, 30);
    gBlSaved = gBl;
    backlightSetPercent(gBl);
    gClockColorIdx = (int)prefs.getUChar(PREF_KEY_CLR_CLOCK, 0);
    Serial.printf("[BL] clock page: brightness -> %u%%  (main saved: %u%%)\n", gBl, gBlMain);
    gClockFullRedraw = true;
    drawClockPage();
  }
  else
  {
    drawPageLabel("PAGE ?");
  }
  tft.endWrite();
}

static void handleTouchPageSwitch()
{
  uint16_t touchX, touchY;

  tft.endWrite();
  if (!tft.getTouch(&touchX, &touchY))
    return;

  gLastActivityMs = millis(); // any touch resets the screensaver timer

  uint32_t now = millis();
  if (now - gLastPageTouchMs < PAGE_TOUCH_DEBOUNCE_MS)
    return;

  gLastPageTouchMs = now;

  if (gPage == PAGE_CLOCK)
  {
    // Top-edge invisible buttons — raw Y=0 is physical top
    bool inTopEdge = (touchY < BRIGHT_BOX);
    bool inCorner  = inTopEdge && ((touchX < BRIGHT_BOX) || (touchX >= (uint16_t)(SW - BRIGHT_BOX)));
    bool inCenter  = inTopEdge && (touchX >= (uint16_t)(SW / 2 - BRIGHT_BOX))
                               && (touchX <  (uint16_t)(SW / 2 + BRIGHT_BOX));

    if (inCorner) {
      // handled by handleTouchBrightnessAndSave()
    } else if (inCenter) {
      // Cycle digit colour
      gClockColorIdx = (gClockColorIdx + 1) % CLK_PALETTE_SIZE;
      prefs.putUChar(PREF_KEY_CLR_CLOCK, (uint8_t)gClockColorIdx);
      Serial.printf("[CLR] clock colour -> idx=%d  0x%04X\n", gClockColorIdx, CLK_PALETTE[gClockColorIdx]);
      gClockFullRedraw = true;
      tft.startWrite();
      drawClockPage();
      tft.endWrite();
    } else {
      // Centre of screen — go back to main
      prefs.putUChar(PREF_KEY_BL_CLOCK, gBl);
      gBl = gBlMain;
      gBlSaved = gBl;
      gBlDirty = false;
      backlightSetPercent(gBl);
      setPage(PAGE_MAIN);
    }
    return;
  }

  if (gPage == PAGE_MAIN)
  {
    if (handlePlaneTouch((int)touchX, (int)touchY))
      setPage(PAGE_2);
    return;
  }

  PageId next = PAGE_MAIN;
  if (gPage == PAGE_2)
    next = PAGE_3;
  else if (gPage == PAGE_3)
    next = PAGE_4;

  setPage(next);
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
    delay(25);
  }

  // Hold
  delay(holdMs);

  // Fade out
  for (int p = HB9_BL_DEFAULT_PERCENT; p >= 0; p -= 2)
  {
    backlightSetPercent(p);
    delay(25);
  }
}

#ifndef HB9_TFT_INVERT
#define HB9_TFT_INVERT 0
#endif

void handleTouchBrightnessAndSave()
{

  // Ensure any pending TFT write transaction is not holding the SPI bus
  tft.endWrite();

  // 1) Handle touch -> change brightness
  uint16_t touchX, touchY;

  if (tft.getTouch(&touchX, &touchY))
  {

    // TEMP DEBUG:
    Serial.printf("TOUCH raw x=%u y=%u\n", touchX, touchY);

    // Y invert
    touchY = SH - touchY;

    static uint32_t lastSelectMs = 0;
    uint32_t now = millis();
    if (now - lastSelectMs >= 200)
    {
      handlePlaneTouch((int)touchX, (int)touchY);
      lastSelectMs = now;
    }

    static uint32_t lastStepMs = 0;
    now = millis();

    // After Y-inversion, top of screen = touchY > SH - BRIGHT_BOX
    bool inDimBox    = (touchX < BRIGHT_BOX) && (touchY > (SH - BRIGHT_BOX));
    bool inBrightBox = (touchX >= (SW - BRIGHT_BOX)) && (touchY > (SH - BRIGHT_BOX));

    if (inDimBox || inBrightBox)
      Serial.printf("[BL] corner touch x=%u y=%u  %s  current=%d%%\n",
                    touchX, touchY, inBrightBox ? "BRIGHT" : "DIM", gBl);

    // limit repeat rate while finger is down
    if ((inDimBox || inBrightBox) && (now - lastStepMs >= 180))
    {
      lastStepMs = now;

      const uint8_t step = 5;
      uint8_t old = gBl;

      if (inBrightBox)
        gBl = (gBl + step > 100) ? 100 : (gBl + step);
      else
        gBl = (gBl < step + 3) ? 3 : (gBl - step);

      if (gBl != old)
      {
        backlightSetPercent(gBl);
        gBlDirty = true;
        gLastTouchMs = millis();
        Serial.printf("[BL] brightness changed %d%% -> %d%%\n", old, gBl);
      }
    }
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
        const char *key = (gPage == PAGE_CLOCK) ? PREF_KEY_BL_CLOCK : PREF_KEY_BL;
        prefs.putUChar(key, gBl);
        gBlSaved = gBl;
        Serial.printf("Saved brightness (%s): %u%%\n", key, gBl);
      }
      gBlDirty = false;
    }
  }
}

// ===================== Stats Page (PAGE_4) =====================
static void drawStatsPage()
{
  tft.fillScreen(TFT_BLACK);
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);

  // Layout controls (similar to PAGE_2)
  const int leftMargin = 12;
  const int rightMargin = 12;
  const int colGap = 18;
  const int bottomMargin = 12;

// Top banner
#ifdef LOAD_GFXFF
  tft.setFreeFont(&JetBrainsMono_Medium22pt7b);
#endif
  int bannerH = 24;
#ifdef LOAD_GFXFF
  bannerH = tft.fontHeight() + 10;
#endif
  tft.fillRect(0, 0, SW, bannerH, TFT_DARKGREY);
  tft.setTextColor(TFT_WHITE, TFT_DARKGREY);
  {
    const char *bannerTitle = "STATISTICS";
    tft.setTextDatum(MC_DATUM);
    tft.drawString(bannerTitle, SW / 2, bannerH / 2);
    tft.setTextDatum(TL_DATUM);
  }
  tft.setTextColor(TFT_WHITE, TFT_BLACK);

  const int topMargin = bannerH + 8;

#ifdef LOAD_GFXFF
  tft.setFreeFont(&JetBrainsMono_Medium15pt7b);
#endif
  int dy = 16;
  int startY = topMargin;
#ifdef LOAD_GFXFF
  dy = tft.fontHeight() + 4;
  startY = topMargin + tft.fontHeight();
#endif

  const int colW = (SW - leftMargin - rightMargin - colGap) / 2;
  const int colX0 = leftMargin;
  const int colX1 = leftMargin + colW + colGap - 20;
  const int yMax = SH - bottomMargin;

  int col = 0;
  int x = colX0;
  int y = startY;

  auto newColumnIfNeeded = [&]()
  {
    if (y + dy <= yMax)
      return;
    if (col == 0)
    {
      col = 1;
      x = colX1;
      y = startY;
    }
  };

  auto put = [&](const char *s)
  {
    newColumnIfNeeded();
    tft.drawString(s, x, y);
    y += dy;
  };

  auto gap = [&](int extra)
  {
    y += extra;
  };

  char line[96];

  snprintf(line, sizeof(line), "Uptime: %s", gStatsTft.uptime_str[0] ? gStatsTft.uptime_str : "---");
  put(line);
  snprintf(line, sizeof(line), "Aircraft in view: %d", gStatsTft.aircraft_in_view);
  put(line);
  snprintf(line, sizeof(line), "Unique today: %d", gStatsTft.unique_today);
  put(line);
  snprintf(line, sizeof(line), "Unique ever: %d", gStatsTft.unique_ever);
  put(line);
  snprintf(line, sizeof(line), "Peak today: %d", gStatsTft.peak_today);
  put(line);
  snprintf(line, sizeof(line), "Peak record: %d", gStatsTft.peak_record);
  put(line);
  snprintf(line, sizeof(line), "Nearest: %.1f km", gStatsTft.nearest_km);
  put(line);
  snprintf(line, sizeof(line), "Nearest record: %.1f km", gStatsTft.closest_record_km);
  put(line);
  snprintf(line, sizeof(line), "Farthest: %.1f km", gStatsTft.farthest_km);
  put(line);
  snprintf(line, sizeof(line), "Farthest record: %.1f km", gStatsTft.farthest_record_km);
  put(line);
  snprintf(line, sizeof(line), "Highest alt: %d m", gStatsTft.highest_alt_m);
  put(line);
  snprintf(line, sizeof(line), "Highest record: %d m", gStatsTft.highest_record_m);
  put(line);
  snprintf(line, sizeof(line), "Fastest: %d km/h", gStatsTft.fastest_kmh);
  put(line);
  snprintf(line, sizeof(line), "Fastest record: %d km/h", gStatsTft.fastest_record_kmh);
  put(line);

// Restore default built-in font for other pages
#ifdef LOAD_GFXFF
  tft.setFreeFont(NULL);
#endif
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
    http.begin(ADSB_JSON_STREAM_URL);

    Serial.println(String("🌐 HTTP GET → ") + ADSB_JSON_STREAM_URL);

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

static void setGamma_ILI9488()
{
  tft.startWrite();

  // P-Gamma (0xE0)
  tft.writecommand(0xE0);
  tft.writedata(0x00);
  tft.writedata(0x08);
  tft.writedata(0x0C);
  tft.writedata(0x02);
  tft.writedata(0x0E);
  tft.writedata(0x04);
  tft.writedata(0x30);
  tft.writedata(0x45);
  tft.writedata(0x47);
  tft.writedata(0x04);
  tft.writedata(0x0C);
  tft.writedata(0x0A);
  tft.writedata(0x2E);
  tft.writedata(0x34);
  tft.writedata(0x0F);

  // N-Gamma (0xE1)
  tft.writecommand(0xE1);
  tft.writedata(0x00);
  tft.writedata(0x11);
  tft.writedata(0x0D);
  tft.writedata(0x01);
  tft.writedata(0x0F);
  tft.writedata(0x05);
  tft.writedata(0x39);
  tft.writedata(0x36);
  tft.writedata(0x51);
  tft.writedata(0x06);
  tft.writedata(0x0F);
  tft.writedata(0x0D);
  tft.writedata(0x33);
  tft.writedata(0x37);
  tft.writedata(0x0F);

  tft.endWrite();
}
#include "HB9IIU_LegendPage.h"
#include "HB9IIU_CalibrateTFTdisplay.h"
bool lastConnected = false;

// TJpgDec callback — pushes each decoded block directly to the TFT
bool tft_output(int16_t x, int16_t y, uint16_t w, uint16_t h, uint16_t *bitmap)
{
  tft.pushImage(x, y, w, h, bitmap);
  return true;
}

// ===================== Setup / Loop =====================
void setup()
{
  Serial.begin(115200);
  tft.init();
  tft.setRotation(TFT_ROTATION);
  tft.invertDisplay(HB9_TFT_INVERT);
  tft.fillScreen(TFT_BLACK);
  tft.setSwapBytes(true);

  TJpgDec.setJpgScale(1);
  TJpgDec.setSwapBytes(false);  // tft.setSwapBytes(true) handles the swap in pushImage
  TJpgDec.setCallback(tft_output);
  backlightInit();
    // Check for factory reset (hold touch/button at boot to erase all settings)
    HB9IIUPortal::checkFactoryReset();


  // Draw a white rectangle at the display extremities for 3D print window check
  tft.drawRect(0, 0, tft.width(), tft.height(), TFT_WHITE);
  //delay(2000000);
  checkAndApplyTFTCalibrationData(false);

  prefs.begin(PREF_NS, false);
  gBl = prefs.getUChar(PREF_KEY_BL, HB9_BL_DEFAULT_PERCENT);
  gBlSaved = gBl;
  backlightSetPercent(gBl);
  setGamma_ILI9488();
  displaySplashScreen(2500);
  tft.fillScreen(TFT_BLACK);

 
 HB9IIU_legend_drawLegendPage();
    // --- Start Wi-Fi / Portal handling ---
    // Attempts to connect to saved Wi-Fi; launches AP/captive portal if needed
    HB9IIUPortal::begin("cyd-demo");

    // Block here until Wi-Fi is connected
    // If in AP mode, process captive portal events (web server, DNS, etc.)
    while (!HB9IIUPortal::isConnected()) {
        if (HB9IIUPortal::isInAPMode()) {
            HB9IIUPortal::loop();
        }
        delay(10); // avoid busy loop
    }

    lastConnected = true;


HB9IIUWifiGetTime();


  // Fade out
  for (int p = HB9_BL_DEFAULT_PERCENT; p >= 0; p -= 2)
  {
    backlightSetPercent(p);
    delay(25);
  }

  setPage(PAGE_MAIN);

  // Fade in
  for (int p = 0; p <= HB9_BL_DEFAULT_PERCENT; p += 2)
  {
    backlightSetPercent(p);
    delay(50);
  }
  // Block here until we see a valid JSON stream (or timeout)
  waitForValidAircraftStream(10000, 800); // 20s max, retry every 0.8s

  gLastActivityMs = millis(); // start screensaver timer from now
}

void loop()
{
  handleTouchPageSwitch();
  handleTouchBrightnessAndSave();

  static uint32_t lastFetch = 0;
  static uint32_t lastHeapMs = 0;
  const uint32_t now = millis();

  if (DEBUG_HEAP && (now - lastHeapMs) >= HEAP_LOG_INTERVAL_MS)
  {
    lastHeapMs = now;
    Serial.printf("HEAP free=%u min=%u maxAlloc=%u\n",
                  ESP.getFreeHeap(),
                  ESP.getMinFreeHeap(),
                  ESP.getMaxAllocHeap());
  }


  // Screensaver: switch to clock after inactivity
  if (gPage != PAGE_CLOCK && (now - gLastActivityMs) >= SCREENSAVER_TIMEOUT_MS)
  {
    setPage(PAGE_CLOCK);
  }

  // Clock page: periodic temperature refresh (every 15 min)
  if (gPage == PAGE_CLOCK)
  {
    static uint32_t lastMeteoMs = 0;
    if ((now - lastMeteoMs) >= METEO_REFRESH_MS)
    {
      lastMeteoMs = now;
      fetchMeteoTemp();
    }
  }

  // Clock page: redraw when the minute changes
  if (gPage == PAGE_CLOCK)
  {
    static uint8_t lastClockMin = 255;
    time_t t;
    time(&t);
    struct tm tm_info;
    localtime_r(&t, &tm_info);
    if ((uint8_t)tm_info.tm_min != lastClockMin)
    {
      lastClockMin = (uint8_t)tm_info.tm_min;
      tft.startWrite();
      drawClockPage();
      tft.endWrite();
    }
  }

  if (gPage == PAGE_MAIN && (now - lastFetch) >= FETCH_PERIOD_MS)
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
