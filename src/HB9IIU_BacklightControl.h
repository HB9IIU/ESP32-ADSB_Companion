#pragma once
#include <Arduino.h>

// Backlight pin & polarity are selected per PlatformIO environment via build_flags:
//   -D HB9_BL_PIN=27            (CYD 4")
//   -D HB9_BL_PIN=4             (external ILI9488)
// Optional (only if needed):
//   -D HB9_BL_ACTIVE_HIGH=1     (default)
//   -D HB9_BL_ACTIVE_HIGH=0     (inverted)

#ifndef HB9_BL_PIN
  #define HB9_BL_PIN 27
#endif

#ifndef HB9_BL_ACTIVE_HIGH
  #define HB9_BL_ACTIVE_HIGH 1
#endif

static const int  BL_PIN = HB9_BL_PIN;
static const bool BL_ACTIVE_HIGH = (HB9_BL_ACTIVE_HIGH != 0);

static const int BL_CH   = 0;          // pick a simple channel
static const int BL_FREQ = 500;        // LOW freq so you can *see* dimming easily
static const int BL_RES  = 10;         // 0..1023

static bool bl_inited = false;

static inline uint32_t blMaxDuty() { return (1u << BL_RES) - 1u; }

static inline uint32_t blPolarity(uint32_t duty) {
  if (duty > blMaxDuty()) duty = blMaxDuty();
  return BL_ACTIVE_HIGH ? duty : (blMaxDuty() - duty);
}

void backlightInit()
{
  ledcSetup(BL_CH, BL_FREQ, BL_RES);
  ledcAttachPin(BL_PIN, BL_CH);
  ledcWrite(BL_CH, blPolarity(blMaxDuty())); // start full ON
  bl_inited = true;
}

void backlightSetPercent(uint8_t percent)
{
  if (!bl_inited) backlightInit();
  if (percent > 100) percent = 100;
  uint32_t duty = (uint32_t)percent * blMaxDuty() / 100u;
  ledcWrite(BL_CH, blPolarity(duty));
}
