#!/usr/bin/env python
"""Generate the Swarmax brand set from ONE geometry definition.

Outputs (assets/):
  logo.svg        primary icon (vector, gradient)
  logo-mono.svg   monochrome icon, currentColor, transparent (docs/dark-light)
  banner.svg      1500x500 GitHub social/README banner with wordmark
  logo-1024.png   raster master (project's own rasterizer: swarmax.raster)
  logo-512.png    box-downsampled (anti-aliased)
  logo-256.png    README/PyPI embed size
  logo-64.png     favicon-scale

Geometry: seven-point protractor star (one point up = the sealed evidence
chain) over a seven-arc stroboscope ring (the fleet, seen per turn).
Single source of truth -> SVG and PNG are coordinate-identical by construction.

  python scripts/gen_brand.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swarmax.metrics.charts import Canvas  # noqa: E402
from swarmax.raster import decode_png, encode_png  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "assets"

CX = CY = 512.0
OUTER_R, INNER_R = 336.0, 143.0
N = 7
ARC_R0, ARC_STEP = 296.0, 12.0
INK_A, INK_B = (99, 245, 221), (43, 179, 163)     # #63F5DD -> #2BB3A3
BG_IN, BG_OUT = (18, 42, 92), (8, 20, 48)          # #122A5C -> #081430
BG_CENTER = (CX, 430.0)


def _pt(angle_deg: float, radius: float) -> tuple[float, float]:
    a = math.radians(angle_deg)
    return (CX + radius * math.cos(a), CY + radius * math.sin(a))


def star_vertices() -> list[tuple[float, float]]:
    """Compass-star silhouette: outer/inner alternating, one point straight up."""
    step = 360.0 / N
    pts: list[tuple[float, float]] = []
    for i in range(N):
        pts.append(_pt(-90 + i * step, OUTER_R))
        pts.append(_pt(-90 + (i + 0.5) * step, INNER_R))
    return pts


def arc_paths() -> list[tuple[float, float, float]]:
    """(start_angle, sweep, radius) for the seven stroboscope arcs."""
    step = 360.0 / N
    return [(-90 + i * step, 118.0, ARC_R0 - i * ARC_STEP) for i in range(N)]


def _fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def svg_paths() -> str:
    star = "M " + " L ".join(f"{_fmt(x)} {_fmt(y)}" for x, y in star_vertices()) + " Z"
    arcs = []
    for start, sweep, r in arc_paths():
        x0, y0 = _pt(start, r)
        x1, y1 = _pt(start + sweep, r)
        large = 1 if sweep > 180 else 0
        arcs.append(
            f'<path d="M {_fmt(x0)} {_fmt(y0)} A {r} {r} 0 {large} 1 '
            f'{_fmt(x1)} {_fmt(y1)}"/>'
        )
    return star, "\n      ".join(arcs)


def logo_svg(mono: bool) -> str:
    star, arcs = svg_paths()
    if mono:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" '
            'role="img" aria-labelledby="t d">\n'
            '<title id="t">Swarmax</title>'
            '<desc id="d">Seven-pointed protractor star over a seven-arc ring.</desc>\n'
            f'  <path fill="currentColor" d="{star}"/>\n'
            f'  <g fill="none" stroke="currentColor" stroke-width="15" opacity="0.55">\n      {arcs}\n  </g>\n'
            "</svg>\n"
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" role="img" aria-labelledby="t d">\n'
        '  <title id="t">Swarmax</title>\n'
        '  <desc id="d">Seven-pointed protractor star (the sealed evidence chain) over a seven-arc stroboscope ring (the fleet).</desc>\n'
        "  <defs>\n"
        '    <radialGradient id="bg" cx="50%" cy="42%" r="75%">\n'
        f'      <stop offset="0%" stop-color="#122A5C"/><stop offset="100%" stop-color="#081430"/>\n'
        "    </radialGradient>\n"
        '    <linearGradient id="ink" x1="0" y1="0" x2="1" y2="1">\n'
        f'      <stop offset="0%" stop-color="#63F5DD"/><stop offset="100%" stop-color="#2BB3A3"/>\n'
        "    </linearGradient>\n"
        "  </defs>\n"
        '  <rect width="1024" height="1024" rx="228" fill="url(#bg)"/>\n'
        '  <g fill="none" stroke="url(#ink)" stroke-linecap="round">\n'
        '    <g stroke-width="9" opacity="0.20">\n'
        '      <circle cx="512" cy="512" r="390"/><circle cx="512" cy="512" r="340"/>\n'
        "    </g>\n"
        f'    <g stroke-width="15" opacity="0.82">\n      {arcs}\n    </g>\n'
        f'    <path fill="url(#ink)" stroke="none" d="{star}"/>\n'
        '    <circle cx="512" cy="512" r="34" fill="#081430" stroke="url(#ink)" stroke-width="14"/>\n'
        "  </g>\n"
        "</svg>\n"
    )


def banner_svg() -> str:
    star, arcs = svg_paths()
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="500" viewBox="0 0 1500 500" role="img" aria-labelledby="t d">\n'
        '  <title id="t">Swarmax — evidence-based operations for AI agent fleets</title>\n'
        '  <desc id="d">Swarmax banner: protractor-star mark and wordmark on deep navy.</desc>\n'
        "  <defs>\n"
        '    <linearGradient id="bgb" x1="0" y1="0" x2="1" y2="1">\n'
        '      <stop offset="0%" stop-color="#0D2148"/><stop offset="100%" stop-color="#081430"/>\n'
        "    </linearGradient>\n"
        '    <linearGradient id="inkb" x1="0" y1="0" x2="1" y2="1">\n'
        '      <stop offset="0%" stop-color="#63F5DD"/><stop offset="100%" stop-color="#2BB3A3"/>\n'
        "    </linearGradient>\n"
        "  </defs>\n"
        '  <rect width="1500" height="500" fill="url(#bgb)"/>\n'
        '  <g transform="translate(114,-51) scale(0.365)">\n'
        f'    <path fill="url(#inkb)" d="{star}"/>\n'
        f'    <g fill="none" stroke="url(#inkb)" stroke-width="15" opacity="0.82" stroke-linecap="round">\n      {arcs}\n    </g>\n'
        '    <circle cx="512" cy="512" r="34" fill="#081430" stroke="url(#inkb)" stroke-width="14"/>\n'
        "  </g>\n"
        '  <text x="440" y="268" font-family="\'Segoe UI\',\'Helvetica Neue\',Arial,sans-serif" '
        'font-size="128" font-weight="650" fill="#E8F1FF" letter-spacing="2">Swarmax</text>\n'
        '  <text x="446" y="340" font-family="\'Segoe UI\',\'Helvetica Neue\',Arial,sans-serif" '
        'font-size="38" fill="#8FA3C8">Evidence-based operations for AI agent fleets</text>\n'
        '  <g fill="#2BB3A3">\n'
        + "".join(
            f'    <circle cx="{446 + i * 26}" cy="386" r="5"/>\n' for i in range(N)
        )
        + "  </g>\n"
        "</svg>\n"
    )


# ---- PNG rendering (same geometry, project's own rasterizer) ---------------

def _lerp(c0, c1, t):
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c0, c1))


def render_master(size: int = 1024) -> bytes:
    s = float(size)
    k = size / 1024.0
    cv = Canvas(size, size, bg=BG_OUT)

    # radial background (separable: dx depends on x only, dy on y only)
    dx2 = [(x - BG_CENTER[0] * k) ** 2 for x in range(size)]
    start = cv.start()
    row_bg = []
    for y in range(size):
        dy2 = (y - BG_CENTER[1] * k) ** 2
        row = bytearray(size * 3)
        for x in range(size):
            t = min(1.0, math.sqrt(dx2[x] + dy2) / (620 * k))
            r, g, b = _lerp(BG_IN, BG_OUT, t)
            i = x * 3
            row[i:i + 3] = bytes((r, g, b))
        row_bg.append(row)
    for y in range(size):
        base = y * size * 4
        for x in range(size):
            i = x * 3
            j = base + x * 4
            start[j:j + 3] = row_bg[y][i:i + 3]

    ink_at = lambda x, y: _lerp(INK_A, INK_B, min(1.0, (x + y) / (2 * size)))  # noqa: E731

    def disc(x0, y0, rad, color_fn):
        r2 = rad * rad
        for yy in range(max(0, int(y0 - rad)), min(size, int(y0 + rad) + 1)):
            span = r2 - (yy - y0) ** 2
            if span <= 0:
                continue
            half = math.sqrt(span)
            for xx in range(max(0, int(x0 - half)), min(size, int(x0 + half) + 1)):
                cv._px(xx, yy, *color_fn(xx, yy))

    def ring(x0, y0, rad, width, color_fn, a0=None, a1=None):
        for yy in range(max(0, int(y0 - rad - width)), min(size, int(y0 + rad + width) + 1)):
            for xx in range(max(0, int(x0 - rad - width)), min(size, int(x0 + rad + width) + 1)):
                d = math.hypot(xx - x0, yy - y0)
                if abs(d - rad) > width / 2:
                    continue
                if a0 is not None:
                    ang = math.degrees(math.atan2(yy - y0, xx - x0)) % 360
                    rel = (ang - a0) % 360
                    if rel > (a1 - a0) % 360:
                        continue
                cv._px(xx, yy, *color_fn(xx, yy))

    # faint outer rings
    ring(CX * k, CY * k, 390 * k, 9 * k, lambda x, y: tuple(int(c * 0.20 + b * 0.80) for c, b in zip(ink_at(x, y), BG_OUT)))
    ring(CX * k, CY * k, 340 * k, 9 * k, lambda x, y: tuple(int(c * 0.20 + b * 0.80) for c, b in zip(ink_at(x, y), BG_OUT)))
    # seven stroboscope arcs
    for a0, sweep, r in arc_paths():
        ring(CX * k, CY * k, r * k, 15 * k, ink_at, a0=a0, a1=a0 + sweep)
    # star (nonzero fill == simple polygon here: scanline winding)
    verts = [(x * k, y * k) for x, y in star_vertices()]
    ys = [p[1] for p in verts]
    for y in range(max(0, int(min(ys))), min(size, int(max(ys)) + 1)):
        cross: list[tuple[float, int]] = []
        n = len(verts)
        for i in range(n):
            (x1, y1), (x2, y2) = verts[i], verts[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                cross.append((x, 1 if y2 > y1 else -1))
        cross.sort()
        w = 0
        for idx, (x, d) in enumerate(cross):
            w += d
            if w != 0 and idx + 1 < len(cross):
                x_end = int(cross[idx + 1][0])
                for xx in range(max(0, int(x)), min(size, x_end + 1)):
                    cv._px(xx, y, *ink_at(xx, y))
    # center hub
    disc(CX * k, CY * k, 41 * k, lambda x, y: BG_OUT)
    ring(CX * k, CY * k, 34 * k, 14 * k, ink_at)
    disc(CX * k, CY * k, 27 * k, lambda x, y: BG_OUT)

    return encode_png(bytes(cv.buf), size, size)


def downsample(png: bytes, factor: int) -> bytes:
    rgba, w, h = decode_png(png)
    assert w % factor == 0 and h % factor == 0
    small_w = w // factor
    out = bytearray(small_w * small_w * 4)
    f2 = factor * factor
    for sy in range(small_w):
        for sx in range(small_w):
            rs = gs = bs = 0
            for dy in range(factor):
                base = ((sy * factor + dy) * w + sx * factor) * 4
                for dx in range(factor):
                    i = base + dx * 4
                    rs += rgba[i]
                    gs += rgba[i + 1]
                    bs += rgba[i + 2]
            o = (sy * small_w + sx) * 4
            out[o:o + 4] = bytes((rs // f2, gs // f2, bs // f2, 255))
    return encode_png(bytes(out), small_w, small_w)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / "logo.svg").write_text(logo_svg(mono=False), encoding="utf-8")
    (OUT / "logo-mono.svg").write_text(logo_svg(mono=True), encoding="utf-8")
    (OUT / "banner.svg").write_text(banner_svg(), encoding="utf-8")
    master = render_master(1024)
    (OUT / "logo-1024.png").write_bytes(master)
    for factor, name in ((2, "logo-512.png"), (4, "logo-256.png"), (16, "logo-64.png")):
        (OUT / name).write_bytes(downsample(master, factor))
    for f in sorted(OUT.iterdir()):
        print(f"{f.name:16s} {f.stat().st_size:>8,d} bytes")


if __name__ == "__main__":
    main()
