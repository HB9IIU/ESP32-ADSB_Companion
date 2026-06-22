
// ------------------ Prototypes (explicit, for VS Code / PlatformIO) ------------------
static void HB9IIU_legend_drawMask1bit_PROGMEM(int x0, int y0,
                                               const uint8_t *maskProgmem,
                                               int mw, int mh, int mstride,
                                               uint16_t color);
static void HB9IIU_legend_drawPlaneInCell(int i, int headingDeg);
static void HB9IIU_legend_drawLegendPage(void);
// -------------------------------------------------------------------------------------

static const int HB9IIU_legend_SW = 480;
static const int HB9IIU_legend_SH = 320;

#ifndef HB9_TFT_INVERT
#define HB9_TFT_INVERT 0
#endif

// ----- Layout (reserved bottom margin) -----
static const int HB9IIU_legend_MARGIN_BOTTOM = 18; // reserved space at bottom
static const int HB9IIU_legend_GRID_H = HB9IIU_legend_SH - HB9IIU_legend_MARGIN_BOTTOM;

static const int HB9IIU_legend_COLS = 4;
static const int HB9IIU_legend_ROWS = 3;

static const int HB9IIU_legend_cellW = HB9IIU_legend_SW / HB9IIU_legend_COLS;
static const int HB9IIU_legend_cellH = HB9IIU_legend_GRID_H / HB9IIU_legend_ROWS;

// ---- Data tables (parallel arrays) ----
// Assumption: all *_offset tables are uint16_t offsets.
static const uint8_t *const HB9IIU_legend_masks[] PROGMEM = {
    A032_masks, A132_masks, A232_masks, A332_masks, A432_masks, A532_masks, A632_masks, A732_masks,
    B032_masks, B132_masks, B232_masks, NA32_masks};

static const uint16_t *const HB9IIU_legend_offsets[] PROGMEM = {
    A032_offset, A132_offset, A232_offset, A332_offset, A432_offset, A532_offset, A632_offset, A732_offset,
    B032_offset, B132_offset, B232_offset, NA32_offset};

static const uint16_t HB9IIU_legend_w[] PROGMEM = {
    A032_w, A132_w, A232_w, A332_w, A432_w, A532_w, A632_w, A732_w,
    B032_w, B132_w, B232_w, NA32_w};

static const uint16_t HB9IIU_legend_h[] PROGMEM = {
    A032_h, A132_h, A232_h, A332_h, A432_h, A532_h, A632_h, A732_h,
    B032_h, B132_h, B232_h, NA32_h};

static const uint16_t HB9IIU_legend_stride[] PROGMEM = {
    A032_stride, A132_stride, A232_stride, A332_stride, A432_stride, A532_stride, A632_stride, A732_stride,
    B032_stride, B132_stride, B232_stride, NA32_stride};

static const int HB9IIU_legend_N_PLANES = 12;

static const char *HB9IIU_legend_planeNames[HB9IIU_legend_N_PLANES] = {
    "Jet/Airliner",
    "Light Aircraft",
    "Twin Engine",
    "High Perf. Jet",
    "Regional Jet",
    "Heavy Aircraft",
    "Military Jet",
    "Helicopter",
    "Drone/UAV",
    "Glider/Sailplane",
    "Balloon",
    "Unknown Type"};

static const uint16_t HB9IIU_legend_planeColors[HB9IIU_legend_N_PLANES] = {
    TFT_RED, TFT_GREEN, TFT_BLUE, TFT_YELLOW,
    TFT_CYAN, TFT_MAGENTA, TFT_ORANGE, TFT_WHITE,
    TFT_DARKGREY, TFT_LIGHTGREY, TFT_BROWN, TFT_PINK};

// ------------------ Implementations ------------------

static void HB9IIU_legend_drawMask1bit_PROGMEM(int x0, int y0,
                                               const uint8_t *maskProgmem,
                                               int mw, int mh, int mstride,
                                               uint16_t color)
{
    for (int y = 0; y < mh; y++)
    {
        int x = 0;
        while (x < mw)
        {
            while (x < mw)
            {
                int byteIndex = y * mstride + (x >> 3);
                uint8_t b = pgm_read_byte(maskProgmem + byteIndex);
                int bit = 7 - (x & 7);
                if (b & (1 << bit))
                    break;
                x++;
            }
            if (x >= mw)
                break;

            int xStart = x;

            while (x < mw)
            {
                int byteIndex = y * mstride + (x >> 3);
                uint8_t b = pgm_read_byte(maskProgmem + byteIndex);
                int bit = 7 - (x & 7);
                if (!(b & (1 << bit)))
                    break;
                x++;
            }
            tft.drawFastHLine(x0 + xStart, y0 + y, x - xStart, color);
        }
    }
}

static void HB9IIU_legend_drawPlaneInCell(int i, int headingDeg)
{
    // headingDeg is assumed 0..359 (we call random(0,360))
    tft.setTextFont(1);
    const int spriteHeading = headingDeg;

    const int r = i / HB9IIU_legend_COLS;
    const int c = i % HB9IIU_legend_COLS;

    const int cellX = c * HB9IIU_legend_cellW;
    const int cellY = r * HB9IIU_legend_cellH;

    const int cx = cellX + HB9IIU_legend_cellW / 2;
    const int cy = cellY + HB9IIU_legend_cellH / 2;

    // Clear only within the grid area (bottom margin stays untouched)
    tft.fillRect(cellX, cellY, HB9IIU_legend_cellW, HB9IIU_legend_cellH, TFT_BLACK);
    tft.drawRect(cellX, cellY, HB9IIU_legend_cellW, HB9IIU_legend_cellH, TFT_WHITE);

    const int pw = (int)pgm_read_word(&HB9IIU_legend_w[i]);
    const int ph = (int)pgm_read_word(&HB9IIU_legend_h[i]);
    const int ps = (int)pgm_read_word(&HB9IIU_legend_stride[i]);

    const uint8_t *m = (const uint8_t *)pgm_read_ptr(&HB9IIU_legend_masks[i]);
    const uint16_t *offTbl = (const uint16_t *)pgm_read_ptr(&HB9IIU_legend_offsets[i]);

    uint16_t off16 = 0;
    memcpy_P(&off16, &offTbl[spriteHeading], 2);
    const uint8_t *mask = m + off16;

    const int x0 = cx - pw / 2;
    const int y0 = cy - ph / 2;

    HB9IIU_legend_drawMask1bit_PROGMEM(x0, y0, mask, pw, ph, ps, HB9IIU_legend_planeColors[i]);

    // Label below icon, constrained to the grid (doesn't go into bottom margin)
    tft.setTextDatum(TC_DATUM);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);

    int labelY = cy + ph / 2 + 10;
    int maxLabelY = cellY + HB9IIU_legend_cellH - 2; // keep inside cell
    if (labelY > maxLabelY)
        labelY = maxLabelY;

    tft.drawString(HB9IIU_legend_planeNames[i], cx, labelY);
}

static void HB9IIU_legend_drawLegendPage(void)
{

    // Draw only inside grid area (keep bottom margin available)
    tft.fillRect(0, 0, HB9IIU_legend_SW, HB9IIU_legend_GRID_H, TFT_BLACK);

    for (int i = 0; i < HB9IIU_legend_N_PLANES; i++)
        HB9IIU_legend_drawPlaneInCell(i, random(0, 360));

    // Fade in
    for (int p = 0; p <= HB9_BL_DEFAULT_PERCENT; p += 2)
    {
        backlightSetPercent(p);
        delay(50);
    }
}
