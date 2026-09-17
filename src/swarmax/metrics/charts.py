"""RGBA pixel canvas for console charts (§5 monitor UX).

The console draws every chart twice from the *same* geometry: once as an
accessible SVG (WCAG 1.1.1 tooltips + data-table alternative) and once as a
PNG download/email attachment.  This module is the shared drawing surface
for the PNG twin — pure stdlib, no imaging dependency (§7 F0).

Pixels are RGBA8, row-major, 4 bytes/pixel; alpha stays 255 (the canvas is
pre-composited onto the console's dark background by the caller).
"""
from __future__ import annotations


class Canvas:
    """Tiny software rasterizer: horizontal/vertical lines, segments,
    rectangles, filled discs and polyline paths."""

    __slots__ = ("w", "h", "buf")

    def __init__(self, w: int, h: int, bg: tuple[int, int, int] = (0, 0, 0)) -> None:
        if w <= 0 or h <= 0:
            raise ValueError("empty canvas")
        self.w, self.h = w, h
        r, g, b = bg
        self.buf = bytearray(bytes((r, g, b, 255)) * (w * h))

    def start(self) -> bytearray:
        """Direct pixel access for special drawing; returns the buffer."""
        return self.buf

    def _px(self, x: int, y: int, r: int, g: int, b: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 4
            self.buf[i:i + 3] = bytes((r, g, b))

    def hline(self, x0: int, x1: int, y: int, color: tuple[int, int, int]) -> None:
        for x in range(min(x0, x1), max(x0, x1) + 1):
            self._px(x, y, *color)

    def vline(self, x: int, y0: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(min(y0, y1), max(y0, y1) + 1):
            self._px(x, y, *color)

    def line(self, x0: int, y0: int, x1: int, y1: int,
             color: tuple[int, int, int]) -> None:
        """Bresenham segment."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self._px(x0, y0, *color)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def line_pts(self, pts: list[tuple[int, int]],
                 color: tuple[int, int, int]) -> None:
        """Polyline through integer points (sparkline path)."""
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            self.line(xa, ya, xb, yb, color)

    def rect(self, x: int, y: int, w: int, h: int,
             color: tuple[int, int, int]) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self._px(xx, yy, *color)

    def disc(self, cx: int, cy: int, radius: int,
             color: tuple[int, int, int]) -> None:
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    self._px(cx + dx, cy + dy, *color)

    def bytes(self) -> bytes:
        """Raw RGBA bytes, ready for raster.encode_png."""
        return bytes(self.buf)
