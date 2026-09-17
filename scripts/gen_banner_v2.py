#!/usr/bin/env python
"""Rebuild the Swarmax banner around the CANONICAL mark (assets/logo-mark.png).

The original banner (banner.png) was built for the logo1 composition; this
generator keeps its navy background and typography roles but recomposes with
the transparent one-tone mark:  mark | wordmark+tagline, left-aligned row.

  python scripts/gen_banner_v2.py        # writes assets/banner-v2.png (2172x724)

Pillow is a build-time tool only — the product stays zero-dependency.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

W, H = 2172, 724
NAVY_L, NAVY_R = (10, 24, 56), (4, 20, 48)
INK = (232, 241, 255)        # wordmark off-white (#E8F1FF)
MUTED = (143, 163, 200)      # tagline blue-grey (#8FA3C8)
FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def main() -> None:
    # 1) diagonal navy gradient background (matches original palette)
    bg = Image.new("RGB", (W, H))
    px = bg.load()
    for y in range(H):
        for x in range(W):
            t = (x / W * 0.6 + y / H * 0.4)
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(NAVY_L, NAVY_R))

    # 2) canonical transparent mark, dominant-height
    mark = Image.open("assets/logo-mark.png").convert("RGBA")
    side = 470                                   # ~65% of banner height
    mark = mark.resize((side, side), Image.LANCZOS)
    mx, my = 150, (H - side) // 2
    bg.paste(mark, (mx, my), mark)

    # 3) wordmark + tagline column
    d = ImageDraw.Draw(bg)
    tx = mx + side + 110
    f_word = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 150)
    f_tag = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 47)
    d.text((tx, H // 2 - 132), "Swarmax", font=f_word, fill=INK)
    d.text((tx + 6, H // 2 + 62),
           "Evidence-based operations for AI agent fleets",
           font=f_tag, fill=MUTED)

    # 4) seven-dot rhythm under the tagline
    for i in range(7):
        x = tx + 8 + i * 34
        d.ellipse((x, H // 2 + 152, x + 10, H // 2 + 162), fill=(43, 179, 163))

    bg.save("assets/banner-v2.png", optimize=True)
    print("assets/banner-v2.png", bg.size)


if __name__ == "__main__":
    main()
