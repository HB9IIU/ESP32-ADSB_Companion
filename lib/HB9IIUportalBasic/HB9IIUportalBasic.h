#pragma once
#include <Arduino.h>

namespace HB9IIUPortal
{
    // Call once in setup()
    // Optional hostname: if not null/empty, used for WiFi hostname + mDNS (hostname.local)
    void begin(const char *hostname = nullptr); // tries to connect to saved WiFi, else starts captive portal

    // Call every loop()
    void loop();                  // handles WebServer + DNS when in AP mode

    // Factory reset: erase ALL NVS (wifi/config/iPhonetime/etc.) and restart
    void eraseAllPreferencesAndRestart();

    // Check factory-reset at boot using an already-configured button + LED
    // - buttonPin: INPUT_PULLUP, active LOW
    // - ledPin   : OUTPUT
    // If button is held LOW at boot for ~1s, NVS is erased and ESP restarts.
    bool checkFactoryReset();

    // State helpers
    bool isInAPMode();            // true when captive portal is running
    bool isConnected();           // true when WiFi.status() == WL_CONNECTED
}
