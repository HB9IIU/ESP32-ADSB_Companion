# ESP32 ADS-B Companion (4" TFT Plane Radar)

This project runs on an ESP32 with a 480x320 TFT and shows nearby aircraft on a static map background.  
It fetches live ADS-B JSON data over Wi-Fi (e.g. from a local ADS-B receiver / tar1090 / dump1090 JSON endpoint), tracks aircraft, and renders plane icons oriented by heading. Plane color is based on altitude bands. A bottom bar shows summary stats and nearest aircraft.

## Video

[![ESP32 ADS-B Companion Demo](https://img.youtube.com/vi/luJIPpM341g/hqdefault.jpg)](https://youtu.be/luJIPpM341g)

---

## Features

- 480x320 map background (stored as `background565.h` in PROGMEM)
- Fetch aircraft JSON every `FETCH_PERIOD_MS` (default 1000 ms)
- Track up to `MAX_TRACKS` aircrafts 
- Draw up to `MAX_DRAW` aircraft per refresh (performance knob)
- Altitude color bands + legend bar at the top
- Bottom status bar with differential text update (reduced flicker)
- Splash screen with fade in/out + backlight control
- Four PlatformIO build targets:
  - CYD 4" integrated board (ST7796)
  - External 4" TFT (ILI9488) + standard ESP32 DevKit (DC=GPIO5)
  - External 4" TFT (ILI9488) + ESP32U antenna variant (DC=GPIO0)
  - External 4" TFT (ILI9488) IPS type + standard ESP32 DevKit (DC=GPIO5)
---

## Hardware

### Supported displays / targets

1. **CYD 4" integrated board (ST7796)**  
   PlatformIO env: `cyd4_st7796`

2. **External 4" TFT (ILI9488) + standard ESP32 DevKit** (TFT_DC = GPIO5)  
   PlatformIO env: `ext_ili9488_dc5`

3. **External 4" TFT (ILI9488) + ESP32U / antenna variant** (TFT_DC = GPIO0)  
   PlatformIO env: `ext_ili9488_dc0_antenna`

4. **External 4" TFT (ILI9488) IPS type + standard ESP32 DevKit** (TFT_DC = GPIO5)  
   PlatformIO env: `ext_ili9488_dc5_IPS`

---

## Configuration

All user-specific settings are located in **`Config.h`**.  
You **must** update this file before compiling.

---

# Map Background Generator (RGB565)

## IMPORTANT: Generate your own map background (background565.h)

This project **does not** auto-create the map background.  
You must generate `background565.h` for **your own location** using the included Python tools.

---

## Where the Python tools are

In the repository:

- `pythonTools/GoogleMaps.py`
- `pythonTools/OpenStreetMaps.py`

---

## Choose ONE map source

Use **one or the other**:

- **GoogleMaps.py** — Google tiles (requires Google Static Maps API key)
- **OpenStreetMaps.py** — OpenStreetMap tiles (no API key required)

Both scripts generate the same output:

- `src/background565.h`  
- Resolution: **480 × 320**
- Format: **RGB565**

---

## How to use

Open the script you want to use (`GoogleMaps.py` or `OpenStreetMaps.py`) and follow the instructions **inside the code**.

Inside the script you will configure values such as:

- `CENTER_LAT`
- `CENTER_LON`
- `RANGE_KM`

Example:

```python
CENTER_LAT = 46.4717185
CENTER_LON = 6.4767709
RANGE_KM   = 80
```

Change these values to match your location and desired map coverage.

---

## Google Maps vs OpenStreetMap configuration

The required configuration depends on which script you use.

---

### If you use GoogleMaps.py (Google Static Maps)

**Google Static Maps requires an API key.**

Create a key here:  
https://console.cloud.google.com/apis/credentials

You must:
1. Create a Google Cloud project
2. Enable **Static Maps API**
3. Create an API key

Then edit `GoogleMaps.py`:

```python
# ============================ USER SETTINGS =================================
# --- Google Static Maps API key ---
# Get a valid key here:
# https://console.cloud.google.com/apis/credentials
# (Enable "Static Maps API" for your project, then create an API key)
GOOGLE_MAPS_KEY = "YOUR_GOOGLE_STATIC_MAPS_API_KEY_HERE"

# --- Map center & size ---
CENTER_LAT = 46.4717185
CENTER_LON = 6.4767709
RANGE_KM   = 80
# ============================================================================
```

> **Note:** Google may require billing to be enabled (even if you stay within the free tier).

---

### If you use OpenStreetMaps.py

**OpenStreetMap does not require an API key.**

Edit `OpenStreetMaps.py` and set only the map parameters:

```python
# =============================== USER SETTINGS ===============================
# --- Map center & size ---
CENTER_LAT = 46.4717185
CENTER_LON = 6.4767709
RANGE_KM   = 80
# =============================================================================
```

---

## Output

The script will generate an RGB565 background image and save it as:

```
src/background565.h
```

This file is used directly by the ESP32 firmware.






### After generating the background

Make sure your `Config.h` values match the background you generated:

- `MAP_ZOOM`
- `MAP_PX0`
- `MAP_PY0`

If these do not match your generated map, aircraft icons will not line up with the map correctly.

---

## Build & Upload (PlatformIO)

In `platformio.ini` choose a build target:

```ini

[platformio]
; Pick the default build target here:
;default_envs = cyd4_st7796
;default_envs = ext_ili9488_dc5
default_envs = ext_ili9488_dc0_antenna
;default_envs = ext_ili9488_dc5_IPS

```

# Raspberry Pi ADS-B Receiver Setup
(readsb + tar1090)

This ESP32 ADS-B Companion requires a local ADS-B receiver on your network
that provides live aircraft data in JSON format.

This document describes how to install and configure an ADS-B receiver
on a Raspberry Pi using an RTL-SDR dongle, readsb, and tar1090.

---

## Hardware Requirements

- Raspberry Pi (Pi 3 / Pi 4 / Pi 5 recommended)
- MicroSD card
- RTL-SDR dongle (RTL-SDR Blog V4 recommended)
- ADS-B antenna (active antenna optional)
- Ethernet or Wi-Fi network

---

## Operating System

Use the following operating system:

- Raspberry Pi OS Lite (64-bit)
- Debian release: Trixie

Desktop versions are not recommended.

---

## Step 1 — Flash Raspberry Pi OS

1. Install Raspberry Pi Imager
2. Select:
   - Raspberry Pi OS Lite (64-bit)
   - Debian Trixie
3. Optional (recommended):
   - Enable SSH
   - Configure Wi-Fi
   - Set username and password
4. Flash the SD card and boot the Raspberry Pi

After first boot, update the system:

sudo apt update  
sudo apt full-upgrade -y  
sudo reboot  

---

## Step 2 — Install ADS-B Receiver Software

Download and run the HB9IIU setup script:

```bash
wget -O hb9iiuADSBsetupRPI.sh \
   https://raw.githubusercontent.com/HB9IIU/ESP32-ADSB_Companion/main/RPI_ADSB_install_script/hb9iiuADSBsetupRPI.sh
chmod +x hb9iiuADSBsetupRPI.sh
./hb9iiuADSBsetupRPI.sh
```

The script performs the following tasks:

- Installs RTL-SDR drivers
- Blacklists the DVB kernel driver
- Installs readsb (ADS-B decoder)
- Installs tar1090 web interface
- Optionally enables Bias-T power for active antennas
- Configures receiver gain (auto / low / high)
- Configures receiver latitude and longitude for correct range rings

Press ENTER to accept default values.

---

## Step 3 — Verify tar1090 Web Interface

Open a web browser and navigate to:

```
http://<PI-IP>/tar1090/
```

A live aircraft map should be visible.

---

## Step 4 — JSON Endpoint for ESP32

The ESP32 firmware fetches aircraft data from the following endpoint:

```
http://<PI-IP>/tar1090/data/aircraft.json
```

Example:

```
http://192.168.0.15/tar1090/data/aircraft.json
```

Use this URL in the ESP32 configuration file.

---

## Notes

- An active ADS-B antenna is recommended for best reception
- Bias-T must be enabled only when using an active antenna
- The Raspberry Pi and ESP32 must be on the same network
- Aircraft may take several minutes to appear after startup

---

73 de HB9IIU
