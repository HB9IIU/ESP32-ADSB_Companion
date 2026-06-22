SVG → Rotating Plane Icon Pipeline

This script converts a set of SVG aircraft category icons into rotating bitmap
representations and compact embedded headers.

It is intended to be read by humans months later, not machines or GitHub.
https://adsb-radar.com/help/icons.html
----------------------------------------------------------------

WHAT THIS SCRIPT DOES

For each SVG file in tar1090_category_icons/:

1) Renders the SVG to a 320x320 PNG with a forced black silhouette
2) Crops the PNG tightly to the visible alpha content
3) Measures the maximum bounding box over all 360 rotations
4) Scales the icon so it fits safely at ANY heading (no clipping)
5) Applies an optional per-category shrink margin
6) Renders 360 PNG frames (000.png … 359.png)
   - or 360 identical frames if rotation is disabled
7) Downscales to 32x32 and packs the alpha into a 1-bit mask
8) Writes a PROGMEM-friendly .h file

----------------------------------------------------------------

FOLDER STRUCTURE

tar1090_category_icons/
    Input SVG icons (A1.svg, A2.svg, B1.svg, etc.)

png320x320/
    SVG rendered to 320x320 PNG (forced black)

cropped/
    Tightly cropped square master icons

360_zoomed/<CAT>/
    Final 320x320 PNG frames for each heading

gifs_zoomed/
    Optional animated previews (usually disabled)

h32/
    Generated 32x32 1-bit mask headers

----------------------------------------------------------------

IMPORTANT CONCEPTS

WORST-CASE ROTATION SCALING
The icon is scaled based on the LARGEST bounding box observed over all 360
rotations. This guarantees:
- No clipping at any angle
- Stable size during rotation
- No popping or resizing artifacts

SHRINK_MARGIN
Different silhouettes look bigger or smaller even if they share the same
bounding box.

SHRINK_MARGIN allows you to visually normalize categories by adding extra
transparent margin (in pixels) during scaling.

Bigger margin → smaller icon

ROTATE_ENABLED
Some categories should not rotate.

If rotation is disabled:
- All 360 PNGs are rendered at 0 degrees
- The filenames still exist (000–359)
- The header still contains 360 entries
This keeps the embedded API simple and uniform.

----------------------------------------------------------------

OUTPUT HEADERS

Each category generates:

h32/<CAT>32_360.h

Contents:
- 32x32 pixels
- 1-bit alpha mask
- 360 headings
- Offset table + packed mask data
- Suitable for PROGMEM / embedded use

----------------------------------------------------------------

WHEN THINGS LOOK WRONG

Icon looks too big or too small:
- Adjust SHRINK_MARGIN for that category

Icon should not rotate:
- Set ROTATE_ENABLED[cat] = False

Embedded output looks wrong:
- Inspect 360_zoomed/<cat>/000.png first

----------------------------------------------------------------

MENTAL MODEL

Scale once so the worst rotation fits,
optionally shrink,
rotate into 360 frames,
then crush it down into a tiny embedded-friendly mask.
