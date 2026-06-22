#pragma once
#include <Arduino.h>

static unsigned long lastUserInteractionMs = 0;

void calibrateTFTscreen()
{
    uint16_t calibrationData[5];

    // Display recalibration message
    tft.fillScreen(TFT_BLACK);             // Clear screen
    tft.setTextColor(TFT_BLACK, TFT_GOLD); // Set text color (black on gold)
    tft.setFreeFont(&FreeSansBold12pt7b);  // Use custom free font
    tft.setCursor(10, 22);
    tft.fillRect(0, 0, 480, 30, TFT_GOLD);
    tft.print("   TFT TOUCHSCREEN CALIBRATION");
    tft.setTextColor(TFT_WHITE, TFT_BLACK);

    tft.setFreeFont(&FreeSans12pt7b);

    String instructions[] = {
        "Welcome to the initial touchscreen calibration.",
        "This procedure will only be required once.",
        "On the next screen you will see arrows",
        "appearing one after the other at each corner.",
        "Just tap them until completion.",
        "",
        "Tap anywhere on the screen to begin"};

    int16_t yPos = 100;

    for (String line : instructions)
    {
        int16_t xPos = (tft.width() - tft.textWidth(line)) / 2;
        tft.setCursor(xPos, yPos);
        tft.print(line);
        yPos += tft.fontHeight();
    }

    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.setCursor((tft.width() - tft.textWidth(instructions[6])) / 2, yPos - tft.fontHeight());
    tft.print(instructions[6]);

    while (true)
    {
        uint16_t x, y;
        if (tft.getTouch(&x, &y))
        {
            break;
        }
    }

    tft.fillScreen(TFT_BLACK);

    tft.calibrateTouch(calibrationData, TFT_GREEN, TFT_BLACK, 12);

    prefs.begin("TFT", false);
    for (int i = 0; i < 5; i++)
    {
        prefs.putUInt(("calib" + String(i)).c_str(), calibrationData[i]);
    }
    prefs.end();

    // Test calibration with dynamic feedback
    tft.fillScreen(TFT_BLACK);
    uint16_t x, y;
    int16_t lastX = -1, lastY = -1;
    String lastResult = "";

    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setTextFont(4);
    String text = "Tap anywhere to test";
    tft.setCursor((tft.width() - tft.textWidth(text)) / 2, 8);
    tft.print(text);

    text = "Click Here to Exit";
    int16_t btn_w = tft.textWidth(text) + 20;
    int16_t btn_h = tft.fontHeight() + 12;
    int16_t btn_x = (tft.width() - btn_w) / 2;
    int16_t btn_y = 280;
    int16_t btn_r = 10;

    tft.fillRoundRect(btn_x, btn_y, btn_w, btn_h, btn_r, TFT_BLUE);
    tft.drawRoundRect(btn_x, btn_y, btn_w, btn_h, btn_r, TFT_WHITE);
    tft.setTextColor(TFT_WHITE, TFT_BLUE);
    tft.setCursor((tft.width() - tft.textWidth(text)) / 2, btn_y + 10);
    tft.print(text);

    while (true)
    {
        if (tft.getTouch(&x, &y))
        {
            String result = "x=" + String(x) + "  y=" + String(y) + "  p=" + String(tft.getTouchRawZ());
            lastUserInteractionMs = millis();
            tft.setTextColor(TFT_BLACK, TFT_BLACK);
            tft.setCursor(lastX, lastY);
            tft.print(lastResult);

            int16_t textWidth = tft.textWidth(result);
            int16_t xPos = (tft.width() - textWidth) / 2;
            int16_t yPos = (tft.height() - tft.fontHeight()) / 2;

            tft.setTextColor(TFT_GREEN, TFT_BLACK);
            tft.setCursor(xPos, yPos);
            tft.print(result);

            lastX = xPos;
            lastY = yPos;
            lastResult = result;

            tft.fillCircle(x, y, 2, TFT_RED);

            if (x > btn_x && x < btn_x + btn_w && y > btn_y && y < btn_y + btn_h)
            {
                Serial.println("Exit Touched");
                break;
            }
        }
    }
    tft.setTextSize(2);
    tft.fillScreen(TFT_BLACK);
}


void checkAndApplyTFTCalibrationData(bool recalibrate)
{
    Serial.println(F("───────────────────────────────────────────────────────────────────────────────"));
    Serial.println(F("[INIT] 🖥️  TFT Touch Calibration Check"));
    Serial.println(F("───────────────────────────────────────────────────────────────────────────────"));

    if (recalibrate)
    {
        Serial.println(F("↪ Forced recalibration requested — launching calibration wizard..."));
        calibrateTFTscreen();
        return;
    }

    uint16_t calibrationData[5];
    bool dataValid = true;

    Serial.println(F("Reading stored calibration data from NVS namespace: 'TFT'"));
    prefs.begin("TFT", true); // read-only mode

    for (int i = 0; i < 5; i++)
    {
        calibrationData[i] = prefs.getUInt(("calib" + String(i)).c_str(), 0xFFFF);
        if (calibrationData[i] == 0xFFFF)
        {
            dataValid = false;
            Serial.printf("   ⚠️  calib%d = 0xFFFF → missing or invalid\n", i);
        }
        else
        {
            Serial.printf("   ✓ calib%d = %u\n", i, calibrationData[i]);
        }
    }
    prefs.end();

    if (dataValid)
    {
        tft.setTouch(calibrationData);
        Serial.println();
        Serial.println(F("✅ TFT touch calibration successfully retrieved and applied."));
        Serial.println(F("───────────────────────────────────────────────────────────────────────────────"));
    }
    else
    {
        Serial.println();
        Serial.println(F("❌ Calibration data invalid or incomplete."));
        Serial.println(F("↪ Starting full recalibration procedure..."));
        Serial.println(F("───────────────────────────────────────────────────────────────────────────────"));
        //digitalWrite(TFT_BLP, HIGH);  XXXX
        calibrateTFTscreen();
    }

    Serial.println();
}
