#pragma once
#include <Arduino.h>
#include <time.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// Outdoor temperature fetched from open-meteo (set once at boot, refreshed periodically)
static float gMeteoTempC     = 0.0f;
static bool  gMeteoTempValid = false;

void HB9IIUWifiGetTime()
{

    const char* ntp1 = "pool.ntp.org";
    const char* ntp2 = "time.nist.gov";
    const char* ntp3 = "europe.pool.ntp.org";

    Serial.println();
    Serial.println("══════════════════════════════════════════════");
    Serial.println("  Time acquisition (NTP + Geo Timezone)");
    Serial.println("══════════════════════════════════════════════");

    // 1. Get lat/lon from config.h
    float lat = HOME_LAT;
    float lon = HOME_LON;
    char url[256];
    snprintf(url, sizeof(url), "https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f&current=temperature_2m&timezone=auto", lat, lon);
    //Serial.printf("ℹ️  Fetching timezone from: %s\n", url);
    Serial.printf("ℹ️  Fetching timezone fromhttps://api.open-meteo.com");


    HTTPClient http;
    http.begin(url);
    int httpCode = http.GET();
    String payload;
    String timezone = "Europe/Zurich"; // fallback
    int utc_offset_seconds = 3600;
    String tz_abbr = "GMT+1";
    float elevation = 0.0;
    float temperature = 0.0;
    String current_time = "";
    if (httpCode == 200) {
        payload = http.getString();
        JsonDocument doc;
        DeserializationError err = deserializeJson(doc, payload);
        if (!err) {
            timezone = doc["timezone"] | timezone;
            utc_offset_seconds = doc["utc_offset_seconds"] | utc_offset_seconds;
            tz_abbr = doc["timezone_abbreviation"] | tz_abbr;
            elevation = doc["elevation"] | 0.0;
            if (doc["current"]) {
                temperature = doc["current"]["temperature_2m"] | 0.0;
                current_time = doc["current"]["time"] | "";
            }
            gMeteoTempC     = temperature;
            gMeteoTempValid = true;
            Serial.printf("✅ Timezone: %s, Offset: %d, Abbr: %s\n", timezone.c_str(), utc_offset_seconds, tz_abbr.c_str());
            Serial.printf("   Elevation: %.1f m, Current temp: %.1f °C, Current time: %s\n", elevation, temperature, current_time.c_str());
        } else {
            Serial.println("❌ Failed to parse timezone JSON, using fallback.");
        }
    } else {
        Serial.printf("❌ HTTP error: %d, using fallback timezone\n", httpCode);
    }
    http.end();

    // 2. Use utc_offset_seconds for configTime, do not set TZ
    configTime(utc_offset_seconds, 0, ntp1, ntp2, ntp3);
    Serial.printf("ℹ️  NTP servers: %s, %s, %s\n", ntp1, ntp2, ntp3);
    Serial.printf("ℹ️  Timezone: %s (%s), Offset: %d\n", timezone.c_str(), tz_abbr.c_str(), utc_offset_seconds);

    uint32_t t0 = millis();
    time_t now = 0;
    int tries = 0;
    while (tries < 20) {
        time(&now);
        if (now > 1600000000) break; // valid time
        Serial.println("⏳ waiting for NTP sync...");
        delay(500);
        tries++;
    }
    float elapsedSec = (millis() - t0) / 1000.0f;

    if (now > 1600000000) {
        struct tm local_tm, utc_tm;
        char buf[64];
        // Local time
        localtime_r(&now, &local_tm);
        Serial.println("      ──────────────────────────────────────");
        // Format: HH:MM:SS dd.mm.yyyy (MonthName, Weekday)
        strftime(buf, sizeof(buf), "%H:%M:%S %d.%m.%Y (%b, %A)", &local_tm);
        Serial.printf("✅ Local time: %s\n", buf);
        // UTC time
        gmtime_r(&now, &utc_tm);
        strftime(buf, sizeof(buf), "%H:%M:%S %d.%m.%Y (UTC, %b, %A)", &utc_tm);
        Serial.printf("🌍 UTC time: %s\n", buf);
        // Raw epoch
        Serial.printf("🕓 Epoch: %ld\n", (long)now);
        Serial.printf("⏱️  Time acquisition took %.2f seconds\n", elapsedSec);
        Serial.printf("🕒 UTC Offset (seconds): %d\n", utc_offset_seconds);
        Serial.println("      ──────────────────────────────────────");
    } else {
        Serial.println("❌ Failed to acquire time from NTP.");
    }
}
