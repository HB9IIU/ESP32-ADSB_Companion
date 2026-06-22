#!/usr/bin/env python3
from pathlib import Path
from PIL import Image
import cairosvg
# https://adsb-radar.com/help/icons.html
# ---------------- CONFIG ----------------
SRC_SVG_DIR = Path("tar1090_category_icons")

PNG_DIR     = Path("png320x320")
CROPPED_DIR = Path("cropped")
OUT_360     = Path("360_zoomed")
OUT_GIF     = Path("gifs_zoomed")
#OUT_H32     = Path("h32")
OUT_H32 = Path(__file__).resolve().parents[3] / "include"

CANVAS = 320
PADDING = 2
ALPHA_THRESHOLD_VISIBLE = 1

MAKE_GIFS = False
GIF_STEP_DEG = 10
GIF_FRAME_MS = 60

FINAL_SIZE = 32
ALPHA_THRESHOLD_MASK = 128

STYLE = "<style>*{fill:#000 !important; stroke:#000 !important;}</style>"

# --- per-category extra margin (shrinks icon) --------------------------------
# Meaning: extra transparent margin (in pixels) you want around the silhouette,
# on TOP of the base PADDING, in the 320x320 canvas.
SHRINK_MARGIN: dict[str, int] = {
    "A0": 0,
    "A1": 60,
    "A2": 40,
    "A3": 25,
    "A4": 15,
    "A5": 0,
    "A6": 0,
    "A7": 0,
    "B0": 0,
    "B1": 0,
    "B2": 0,
    "NA": 50,
}

# --- per-category rotation enable --------------------------------------------
# If False: all 360 frames are rendered at 0° (no rotation animation).
ROTATE_ENABLED: dict[str, bool] = {
    "A0": True,
    "A1": True,
    "A2": True,
    "A3": True,
    "A4": True,
    "A5": True,
    "A6": True,
    "A7": True,
    "B0": True,
    "B1": True,
    "B2": False,
    "NA": False,
}
# ----------------------------------------------------------------------------


def get_shrink_margin(cat: str) -> int:
    """Return per-category shrink margin in pixels (>=0)."""
    m = SHRINK_MARGIN.get(cat, 0)
    try:
        m = int(m)
    except Exception:
        m = 0
    return max(0, m)


def get_rotate_enabled(cat: str) -> bool:
    """Return True if category should render rotated frames, else all frames at 0°."""
    return bool(ROTATE_ENABLED.get(cat, True))


def inject_style(svg_text: str) -> str:
    if "<svg" in svg_text:
        i = svg_text.find(">", svg_text.find("<svg"))
        if i != -1:
            return svg_text[:i+1] + STYLE + svg_text[i+1:]
    return STYLE + svg_text


def svg_to_png320(svg_path: Path, out_png: Path) -> None:
    svg_text = svg_path.read_text(encoding="utf-8", errors="ignore")
    svg_black = inject_style(svg_text)
    cairosvg.svg2png(
        bytestring=svg_black.encode("utf-8"),
        write_to=str(out_png),
        output_width=CANVAS,
        output_height=CANVAS,
    )


def crop_to_square(img: Image.Image, alpha_threshold: int = 1, padding: int = 0) -> Image.Image:
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    mask = alpha.point(lambda a: 255 if a >= alpha_threshold else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return img

    cropped = img.crop(bbox)
    w, h = cropped.size
    side = max(w, h) + 2 * padding

    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(cropped, ((side - w) // 2, (side - h) // 2), cropped)
    return square


def alpha_bbox(img_rgba: Image.Image):
    alpha = img_rgba.getchannel("A")
    mask = alpha.point(lambda a: 255 if a >= ALPHA_THRESHOLD_VISIBLE else 0)
    return mask.getbbox()


def measure_worst_case(base_rgba: Image.Image) -> tuple[int, int]:
    max_w = 0
    max_h = 0
    for heading in range(360):
        # rotate +heading to match plane32 convention
        rot = base_rgba.rotate(+heading, resample=Image.Resampling.BICUBIC, expand=True)
        bbox = alpha_bbox(rot)
        if bbox is None:
            continue
        l, u, r, b = bbox
        max_w = max(max_w, r - l)
        max_h = max(max_h, b - u)
    return max_w, max_h


def render_frame(base_scaled: Image.Image, heading: int) -> Image.Image:
    # rotate +heading to match plane32 convention
    rot = base_scaled.rotate(+heading, resample=Image.Resampling.BICUBIC, expand=True)
    frame = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    x = (CANVAS - rot.width) // 2
    y = (CANVAS - rot.height) // 2
    frame.paste(rot, (x, y), rot)
    return frame


def make_gif(icon_name: str):
    icon_dir = OUT_360 / icon_name
    OUT_GIF.mkdir(parents=True, exist_ok=True)
    frames = []
    for heading in range(0, 360, GIF_STEP_DEG):
        png = Image.open(icon_dir / f"{heading:03d}.png").convert("RGBA")
        flat = Image.new("RGB", png.size, (255, 255, 255))
        flat.paste(png, (0, 0), png)
        frames.append(flat)

    out_path = OUT_GIF / f"{icon_name}.gif"
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=GIF_FRAME_MS,
        loop=0,
        optimize=False,
    )
    print(f"GIF: {icon_name} -> {out_path}")


def pack_1bit_mask(img_rgba_32: Image.Image, alpha_threshold: int) -> bytes:
    img = img_rgba_32.convert("RGBA")
    w, h = img.size
    if (w, h) != (FINAL_SIZE, FINAL_SIZE):
        raise ValueError(f"Expected {FINAL_SIZE}x{FINAL_SIZE}, got {w}x{h}")

    stride = (w + 7) // 8
    alpha = img.getchannel("A")

    out = bytearray(h * stride)
    for y in range(h):
        for x in range(w):
            a = alpha.getpixel((x, y))
            if a >= alpha_threshold:
                idx = y * stride + (x // 8)
                bit = 7 - (x % 8)  # MSB-first
                out[idx] |= (1 << bit)
    return bytes(out)


def format_u16_array(name: str, values: list[int], per_line: int = 12) -> str:
    lines = [f"static const uint16_t {name}[{len(values)}] PROGMEM = {{"]
    for i in range(0, len(values), per_line):
        chunk = values[i:i+per_line]
        lines.append("  " + ", ".join(str(v) for v in chunk) + ",")
    lines.append("};\n")
    return "\n".join(lines)


def format_u8_array(name: str, data: bytes, per_line: int = 16) -> str:
    lines = [f"static const uint8_t {name}[{len(data)}] PROGMEM = {{"]
    for i in range(0, len(data), per_line):
        chunk = data[i:i+per_line]
        lines.append("  " + ", ".join(f"0x{b:02X}" for b in chunk) + ",")
    lines.append("};\n")
    return "\n".join(lines)


def write_header_for_category(cat: str, cat_dir_360: Path, out_h: Path, rotate_ok: bool):
    w = FINAL_SIZE
    h = FINAL_SIZE
    stride = (w + 7) // 8
    bytes_per_mask = h * stride

    offsets = [i * bytes_per_mask for i in range(360)]
    blob = bytearray()

    for heading in range(360):
        src_heading = heading if rotate_ok else 0
        p = cat_dir_360 / f"{src_heading:03d}.png"
        img = Image.open(p).convert("RGBA")

        # 32x32 reduction FIRST
        img32 = img.resize((FINAL_SIZE, FINAL_SIZE), resample=Image.Resampling.LANCZOS)

        blob += pack_1bit_mask(img32, alpha_threshold=ALPHA_THRESHOLD_MASK)

    prefix = f"{cat}32"

    out = []
    out.append("#pragma once")
    out.append("#include <stdint.h>")
    out.append("#include <pgmspace.h>\n")
    out.append("// Generated by: wip4.py (rotation direction fixed, per-category shrink + rotation control)")
    out.append(f"// Source category: {cat}")
    out.append(f"// Format: {w}x{h} 1-bit masks, 360 headings\n")
    out.append(f"static const uint16_t {prefix}_w = {w};")
    out.append(f"static const uint16_t {prefix}_h = {h};")
    out.append(f"static const uint16_t {prefix}_stride = {stride};")
    out.append(f"static const uint16_t {prefix}_bytes_per_mask = {bytes_per_mask};\n")
    out.append(format_u16_array(f"{prefix}_offset", offsets))
    out.append(format_u8_array(f"{prefix}_masks", bytes(blob)))

    out_h.parent.mkdir(parents=True, exist_ok=True)
    out_h.write_text("\n".join(out), encoding="utf-8")

    print(f"H: {cat} -> {out_h}  ({len(blob)} bytes masks)")


def main():
    if not SRC_SVG_DIR.exists():
        print(f"SVG folder not found: {SRC_SVG_DIR.resolve()}")
        return

    PNG_DIR.mkdir(parents=True, exist_ok=True)
    CROPPED_DIR.mkdir(parents=True, exist_ok=True)
    OUT_360.mkdir(parents=True, exist_ok=True)
    OUT_H32.mkdir(parents=True, exist_ok=True)

    svgs = sorted(SRC_SVG_DIR.glob("*.svg"))
    if not svgs:
        print(f"No SVG files found in: {SRC_SVG_DIR.resolve()}")
        return

    for svg_path in svgs:
        cat = svg_path.stem
        shrink = get_shrink_margin(cat)
        rotate_ok = get_rotate_enabled(cat)

        # 1) SVG -> forced-black 320x320 PNG
        png_path = PNG_DIR / f"{cat}.png"
        svg_to_png320(svg_path, png_path)

        # 2) Crop to tight square master
        img = Image.open(png_path).convert("RGBA")
        master = crop_to_square(img, alpha_threshold=ALPHA_THRESHOLD_VISIBLE, padding=0)
        master_path = CROPPED_DIR / f"{cat}.png"
        master.save(master_path)

        # 3) Fixed zoom per icon (no clipping over 360°),
        #    with per-category shrink margin applied as extra padding.
        base = Image.open(master_path).convert("RGBA")
        worst_w, worst_h = measure_worst_case(base)
        if worst_w == 0 or worst_h == 0:
            print(f"SKIP (empty?): {svg_path.name}")
            continue

        eff_pad = PADDING + shrink
        usable = CANVAS - 2 * eff_pad
        if usable <= 0:
            print(f"SKIP (usable<=0): {cat}  (PADDING={PADDING}, shrink={shrink})")
            continue

        scale = usable / max(worst_w, worst_h)

        new_w = max(1, int(round(base.width * scale)))
        new_h = max(1, int(round(base.height * scale)))
        base_scaled = base.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)

        # 4) Render 360 frames into /360_zoomed/<cat>/
        out_dir = OUT_360 / cat
        out_dir.mkdir(parents=True, exist_ok=True)

        for heading in range(360):
            angle = heading if rotate_ok else 0
            frame = render_frame(base_scaled, angle)
            frame.save(out_dir / f"{heading:03d}.png")

        print(
            f"OK: {svg_path.name} -> {png_path.name} -> cropped/{cat}.png -> 360_zoomed/{cat}/ "
            f"(scale={scale:.4f}, shrink={shrink}, eff_pad={eff_pad}, rotate={rotate_ok})"
        )

        if MAKE_GIFS:
            make_gif(cat)

        # 5) FINAL: generate the header from the 360 frames
        out_h = OUT_H32 / f"{cat}32_360.h"
        write_header_for_category(cat, out_dir, out_h, rotate_ok)

    print("Take now all files inside h32 and copy to ESP32 include file")


if __name__ == "__main__":
    main()
