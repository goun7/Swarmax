"""Lossless PNG encoder for the console's chart canvases (§5 monitor UX).

Console charts are drawn into raw RGBA pixel canvases (uint8, row-major,
4 bytes/pixel).  This module turns such a canvas into a standards-compliant
PNG: signature, IHDR (truecolour+alpha, 8-bit), one IDAT with per-row filter
type 0 (None — the canvases are small, compression still removes redundancy),
IEND.  CRC-32 per chunk per ISO/IEC 15948 / RFC 2083.

Deliberately stdlib-only (project invariant §7 F0): zlib for compression,
binascii.crc32 for integrity.  No vector rasterization here — callers that
have SVG simply pass their canvas; the encoder never sees markup.
"""
from __future__ import annotations

import binascii
import struct
import zlib

_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", binascii.crc32(tag + payload) & 0xFFFFFFFF))


def encode_png(rgba: bytes, width: int, height: int, *, level: int = 9) -> bytes:
    """Encode an RGBA8 canvas as PNG bytes.

    ``rgba`` must be exactly ``width * height * 4`` bytes.  Alpha is
    preserved (callers composite onto their own background when they want
    opaque output — the console paints an opaque canvas already).
    """
    if width <= 0 or height <= 0:
        raise ValueError("empty canvas")
    expected = width * height * 4
    if len(rgba) != expected:
        raise ValueError(f"canvas size mismatch: {len(rgba)} != {expected}")

    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)                      # filter type 0 (None) per scanline
        raw += rgba[y * stride:(y + 1) * stride]

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8bit RGBA
    idat = zlib.compress(bytes(raw), level)
    return (_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat)
            + _chunk(b"IEND", b""))


def decode_png(png: bytes) -> tuple[bytes, int, int]:
    """Decode the exact subset of PNG this module produces (round-trip +
    external-tool verification support).  Raises ValueError on anything
    else — no silent best-effort parsing."""
    if not png.startswith(_SIGNATURE):
        raise ValueError("not a PNG")
    pos, out, meta = 8, bytearray(), {}
    while pos < len(png):
        (length,), tag = struct.unpack(">I", png[pos:pos + 4]), png[pos + 4:pos + 8]
        payload, crc = png[pos + 8:pos + 8 + length], png[pos + 8 + length:pos + 12 + length]
        if binascii.crc32(tag + payload) & 0xFFFFFFFF != struct.unpack(">I", crc)[0]:
            raise ValueError(f"CRC mismatch in {tag!r}")
        if tag == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", payload[:10])
            if depth != 8 or ctype != 6:
                raise ValueError("only 8-bit RGBA supported")
            meta = {"w": w, "h": h}
        elif tag == b"IDAT":
            out += payload
        elif tag == b"IEND":
            break
        pos += 12 + length
    if "w" not in meta:
        raise ValueError("missing IHDR")
    w, h = meta["w"], meta["h"]
    data = zlib.decompress(bytes(out))
    stride = w * 4
    pixels = bytearray(w * h * 4)
    for y in range(h):
        row = data[y * (stride + 1) + 1:(y + 1) * (stride + 1)]
        if data[y * (stride + 1)] != 0:
            raise ValueError("unexpected filter type")
        pixels[y * stride:(y + 1) * stride] = row
    return bytes(pixels), w, h
