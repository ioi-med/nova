#!/usr/bin/env python3
"""Génère assets/nova.ico (icône de l'application Nova).

Dessin vectoriel « à la main » (champs de distance signés + anticrénelage),
puis encodage PNG (zlib) et empaquetage dans un fichier .ico multi-tailles.
Aucune dépendance externe : ni PIL, ni ImageMagick.
"""

import math
import pathlib
import struct
import zlib

SIZES = [256, 128, 64, 48, 32, 24, 16]

# Aplat de l'interface (assagi en 1.3) : plus de dégradé, un seul accent.
ACCENT = (107, 117, 232)
GLYPH = (255, 255, 255)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def rounded_rect_sdf(px, py, cx, cy, half_w, half_h, radius):
    qx = abs(px - cx) - (half_w - radius)
    qy = abs(py - cy) - (half_h - radius)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    inside = min(max(qx, qy), 0.0)
    return outside + inside - radius


def segment_sdf(px, py, ax, ay, bx, by, thickness):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx * vx + vy * vy
    t = 0.0 if denom == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    dx, dy = wx - t * vx, wy - t * vy
    return math.hypot(dx, dy) - thickness


def render(size):
    """Retourne une liste de pixels RGBA (size x size) pour l'icône."""
    s = float(size)
    cx = cy = s / 2.0
    margin = s * 0.055
    radius = s * 0.235
    half = s / 2.0 - margin

    # Lettre « N » : deux montants et une diagonale, aux extrémités arrondies.
    stroke = s * 0.088
    top = s * 0.315
    bottom = s * 0.685
    left = s * 0.335
    right = s * 0.665
    bars = [
        (left, top, left, bottom),
        (right, top, right, bottom),
        (left, top, right, bottom),
    ]

    pixels = bytearray()
    for y in range(size):
        for x in range(size):
            px, py = x + 0.5, y + 0.5

            d_bg = rounded_rect_sdf(px, py, cx, cy, half, half, radius)
            alpha_bg = 1.0 - smoothstep(-1.0, 1.0, d_bg)

            base = ACCENT

            d_glyph = min(segment_sdf(px, py, *b, stroke / 2.0) for b in bars)
            glyph_cov = 1.0 - smoothstep(-1.0, 1.0, d_glyph)

            rgb = tuple(
                base[i] * (1.0 - glyph_cov) + GLYPH[i] * glyph_cov for i in range(3)
            )
            a = int(round(alpha_bg * 255))
            pixels += bytes(
                (
                    int(round(rgb[0])),
                    int(round(rgb[1])),
                    int(round(rgb[2])),
                    a,
                )
            )
    return bytes(pixels)


def png_encode(size, rgba):
    raw = bytearray()
    stride = size * 4
    for y in range(size):
        raw.append(0)  # filtre « None »
        raw += rgba[y * stride : (y + 1) * stride]

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def build_ico(path, images):
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = bytearray()
    payload = bytearray()
    offset = 6 + 16 * len(images)
    for size, data in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack(
            "<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset
        )
        payload += data
        offset += len(data)
    path.write_bytes(header + bytes(entries) + bytes(payload))


def main():
    assets = pathlib.Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    images = []
    for size in SIZES:
        images.append((size, png_encode(size, render(size))))
    ico = assets / "nova.ico"
    build_ico(ico, images)
    print(f"{ico} écrit ({ico.stat().st_size} octets, tailles : {SIZES})")

    logo = assets / "nova-logo.png"
    logo.write_bytes(png_encode(256, render(256)))
    print(f"{logo} écrit ({logo.stat().st_size} octets)")

    # Icône de la fenêtre (barre de titre et barre des tâches) : tao attend des
    # pixels RGBA bruts, que l'on livre à côté du binaire.
    brut = assets / "nova-64.rgba"
    brut.write_bytes(render(64))
    print(f"{brut} écrit ({brut.stat().st_size} octets, 64x64 RGBA)")


if __name__ == "__main__":
    main()
