"""Generate the app icon set for frontend/icons from a single master drawing.

One-off design tool, not part of the running app.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "icons"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BG_TOP = (28, 26, 20)      # #1c1a14
BG_BOTTOM = (20, 18, 12)   # #14120c
GOLD = (201, 162, 63)      # #c9a23f
GOLD_LIGHT = (227, 200, 120)  # #e3c878
PARCHMENT = (244, 236, 216)   # #f4ecd8

SIZE = 1024


def make_master():
    img = Image.new("RGB", (SIZE, SIZE))
    px = img.load()
    for y in range(SIZE):
        t = y / (SIZE - 1)
        r = round(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = round(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = round(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        for x in range(SIZE):
            px[x, y] = (r, g, b)

    draw = ImageDraw.Draw(img, "RGBA")
    cx = cy = SIZE / 2

    # Outer gold ring (kept inside the safe zone for maskable icons)
    ring_r = SIZE * 0.40
    draw.ellipse(
        [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
        outline=GOLD, width=int(SIZE * 0.018),
    )

    # Twelve short tick marks around the ring, evoking a scroll/sun motif
    tick_r_out = ring_r + SIZE * 0.035
    tick_r_in = ring_r + SIZE * 0.01
    for i in range(12):
        a = math.radians(i * 30)
        x1, y1 = cx + tick_r_in * math.cos(a), cy + tick_r_in * math.sin(a)
        x2, y2 = cx + tick_r_out * math.cos(a), cy + tick_r_out * math.sin(a)
        draw.line([x1, y1, x2, y2], fill=GOLD, width=int(SIZE * 0.012))

    # Hebrew letter Bet (ב, first letter of "בלעם") centered in the ring
    font_path = "C:/Windows/Fonts/davidbd.ttf"
    font = ImageFont.truetype(font_path, int(SIZE * 0.46))
    letter = "ב"  # ב
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = cx - tw / 2 - bbox[0]
    ty = cy - th / 2 - bbox[1] - SIZE * 0.01
    draw.text((tx, ty), letter, font=font, fill=GOLD_LIGHT)

    return img


def export(master: Image.Image):
    targets = {
        "icon-512.png": 512,
        "icon-192.png": 192,
        "icon-180.png": 180,  # apple-touch-icon
        "icon-32.png": 32,
        "icon-16.png": 16,
    }
    pngs = {}
    for name, size in targets.items():
        resized = master.resize((size, size), Image.LANCZOS)
        resized.save(OUT_DIR / name)
        pngs[size] = resized

    # favicon.ico bundles the small sizes together
    pngs[32].save(
        OUT_DIR / "favicon.ico",
        sizes=[(16, 16), (32, 32)],
    )


if __name__ == "__main__":
    master = make_master()
    master.save(OUT_DIR / "icon-master.png")
    export(master)
    print(f"Icons written to {OUT_DIR}")
