#pragma once
#include <Arduino.h>
#include <WiFi.h>

// =========================
// Tunable behavior knobs
// =========================
static const uint32_t WIFI_CONNECT_TIMEOUT_MS   = 6000;  // per-attempt connect timeout
static const uint8_t  WIFI_CYCLES               = 3;      // full cycles across candidates
static const uint16_t WIFI_RETRY_PAUSE_MS       = 700;    // pause between attempts
static const int      WIFI_MIN_RSSI_TO_TRY_DBM  = -95;    // only used if scanFirst=true

static String g_connectedSSID = "";

// ---------------- Helpers ----------------
static void wifiPrintStatusLine()
{
  wl_status_t s = WiFi.status();
  Serial.print("📶 Status: ");
  switch (s)
  {
    case WL_CONNECTED:       Serial.println("✅ CONNECTED"); break;
    case WL_NO_SSID_AVAIL:   Serial.println("🫥 NO_SSID_AVAIL"); break;
    case WL_CONNECT_FAILED:  Serial.println("❌ CONNECT_FAILED"); break;
    case WL_CONNECTION_LOST: Serial.println("📉 CONNECTION_LOST"); break;
    case WL_DISCONNECTED:    Serial.println("🔌 DISCONNECTED"); break;
    default:                 Serial.printf("❓ %d\n", (int)s); break;
  }
}

static void wifiPrintIpInfo()
{
  Serial.print("🌐 IP: ");   Serial.println(WiFi.localIP());
  Serial.print("🧭 GW: ");   Serial.println(WiFi.gatewayIP());
  Serial.print("🧱 Mask: "); Serial.println(WiFi.subnetMask());
  Serial.print("📡 RSSI: "); Serial.print(WiFi.RSSI()); Serial.println(" dBm");
}

static bool wifiIsEnabledSSID(const char* ssid)
{
  return (ssid != nullptr) && (ssid[0] != '\0');
}

struct WifiCandidate
{
  const char* ssid;
  const char* pass;
  int rssi;          // from scan, or -999 if unknown
  bool present;      // seen in scan
};

static bool wifiCandidateEnabled(const WifiCandidate& c)
{
  return wifiIsEnabledSSID(c.ssid);
}

static bool wifiTryConnectOne(const WifiCandidate& c, uint32_t timeoutMs)
{
  if (!wifiCandidateEnabled(c)) return false;

  Serial.printf("➡️ Trying: \"%s\"", c.ssid);
  if (c.rssi != -999) Serial.printf(" (RSSI=%d dBm)", c.rssi);
  Serial.println();

  // Hard reset connection state
  WiFi.disconnect(true, true);
  delay(50);

  WiFi.begin(c.ssid, c.pass);

  uint32_t t0 = millis();
  while (millis() - t0 < timeoutMs)
  {
    if (WiFi.status() == WL_CONNECTED)
    {
      g_connectedSSID = String(c.ssid);
      Serial.println("🎉 Connected!");
      wifiPrintIpInfo();
      return true;
    }

    Serial.print("⏳");
    delay(300);
  }

  Serial.println();
  Serial.println("⛔ Timeout — not connected.");
  wifiPrintStatusLine();
  return false;
}

// ------------------------------------------------------------
// Robust connector with optional scan
// - scanFirst = true  -> scan, rank known SSIDs by RSSI, try strongest first
// - scanFirst = false -> no scan; try in fixed order: default then alt
// - Empty SSIDs ("") are treated as DISABLED and skipped.
// ------------------------------------------------------------
bool connectWiFiRobust(bool scanFirst)
{
  g_connectedSSID = "";
  WiFi.mode(WIFI_STA);

  Serial.println("\n==============================");
  Serial.println("📡 Wi-Fi Robust Connect (2 SSIDs)");
  Serial.println("==============================");
  Serial.printf("⚙️ Scan first: %s\n", scanFirst ? "YES" : "NO");

  WifiCandidate cand[2] = {
    { SSIDdefault, PASSdefault, -999, false },
    { SSIDalt,     PASSalt,     -999, false }
  };

  // Quick sanity: at least one SSID enabled
  if (!wifiCandidateEnabled(cand[0]) && !wifiCandidateEnabled(cand[1]))
  {
    Serial.println("🛑 No SSIDs configured (both are empty).");
    return false;
  }

  // ---------- Optional scan ----------
  if (scanFirst)
  {
    Serial.println("🔍 Scanning for known SSIDs...");
    WiFi.disconnect(true, true);
    delay(50);

    int n = WiFi.scanNetworks(false, true);
    if (n <= 0)
    {
      Serial.println("😕 Scan found nothing (or failed). Will still try configured SSIDs.");
    }
    else
    {
      Serial.printf("📋 Found %d networks.\n", n);

      for (int i = 0; i < n; i++)
      {
        String s = WiFi.SSID(i);
        int rssi = WiFi.RSSI(i);

        for (int k = 0; k < 2; k++)
        {
          if (!wifiCandidateEnabled(cand[k])) continue;

          if (s == cand[k].ssid)
          {
            cand[k].present = true;
            cand[k].rssi = rssi;
          }
        }
      }

      for (int k = 0; k < 2; k++)
      {
        if (!wifiCandidateEnabled(cand[k]))
        {
          Serial.printf("🚫 Disabled: \"%s\"\n", (cand[k].ssid ? cand[k].ssid : "(null)"));
          continue;
        }

        if (cand[k].present)
          Serial.printf("✅ Seen: \"%s\"  RSSI=%d dBm\n", cand[k].ssid, cand[k].rssi);
        else
          Serial.printf("🚫 Not seen: \"%s\"\n", cand[k].ssid);
      }
    }

    WiFi.scanDelete();

    // Sort strongest present first (only meaningful if scanFirst)
    auto score = [](const WifiCandidate& c) -> int {
      if (!wifiCandidateEnabled(c)) return -2000; // disabled goes last always
      if (!c.present) return -1000;               // not seen goes after seen
      return c.rssi;                              // higher is better
    };

    if (score(cand[1]) > score(cand[0]))
    {
      WifiCandidate tmp = cand[0];
      cand[0] = cand[1];
      cand[1] = tmp;
    }
  }

  // ---------- Print attempt order ----------
  Serial.println("🧠 Attempt order:");
  int orderIndex = 1;
  for (int k = 0; k < 2; k++)
  {
    if (!wifiCandidateEnabled(cand[k])) continue;
    Serial.printf("  %d) \"%s\"\n", orderIndex++, cand[k].ssid);
  }

  // ---------- Connect cycles ----------
  for (uint8_t cycle = 1; cycle <= WIFI_CYCLES; cycle++)
  {
    Serial.printf("\n🔁 Cycle %u/%u\n", cycle, WIFI_CYCLES);

    for (int k = 0; k < 2; k++)
    {
      if (!wifiCandidateEnabled(cand[k])) continue;

      // Only apply RSSI skip if scanFirst is on and we actually saw it
      if (scanFirst && cand[k].present && cand[k].rssi < WIFI_MIN_RSSI_TO_TRY_DBM)
      {
        Serial.printf("🪫 Skipping \"%s\" (RSSI=%d too weak)\n", cand[k].ssid, cand[k].rssi);
        continue;
      }

      if (wifiTryConnectOne(cand[k], WIFI_CONNECT_TIMEOUT_MS))
      {
        Serial.printf("🏁 Connected to \"%s\"\n", g_connectedSSID.c_str());
        return true;
      }

      delay(WIFI_RETRY_PAUSE_MS);
    }
  }

  Serial.println("\n🧯 All attempts failed.");
  return false;
}

String getConnectedSSID()
{
  return g_connectedSSID;
}
void HB9IIUWifiConnection(){
  // 1) Fast attempt (no scan)
  bool ok = connectWiFiRobust(false);

  // 2) If fast attempt fails, do a smarter attempt (scan + strongest-first)
  if (!ok)
  {
    Serial.println("🧠 Fast connect failed — trying scan-based connect...");
    ok = connectWiFiRobust(true);
  }

  if (!ok)
  {
    Serial.println("😵 Wi-Fi not available — continuing offline mode.");
    // Optional: you could start AP mode / captive portal here later.
  }
  else
  {
    Serial.print("🔗 Using SSID: ");
    Serial.println(getConnectedSSID());
  }
}

