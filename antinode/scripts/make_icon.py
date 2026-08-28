#!/usr/bin/env python3
"""Generate installer/antinode.ico (and a PNG preview).

The icon is the game's own premise: two wave sources whose crests cross into
a standing pattern, drawn with the same maths the Vault uses.
"""
import math, os, struct, sys, zlib

SIZES = [16, 24, 32, 48, 64, 128, 256]

BG      = (7, 12, 20)
CRYSTAL = (150, 232, 255)
DEEP    = (24, 60, 84)


def shade(size, x, y):
    # normalised device coords, y up
    u = (x + 0.5) / size * 2.0 - 1.0
    v = 1.0 - (y + 0.5) / size * 2.0

    d1 = math.hypot(u + 0.42, v + 0.10)
    d2 = math.hypot(u - 0.42, v + 0.10)
    k = 13.5
    f = (math.sin(d1 * k) + math.sin(d2 * k)) * 0.5      # -1 .. 1

    # Round mask so the icon reads at 16px.
    r = math.hypot(u, v)
    if r > 0.97:
        return None
    edge = max(0.0, min(1.0, (0.97 - r) / 0.10))

    t = max(0.0, min(1.0, (f - 0.10) / 0.55))
    glow = max(0.0, min(1.0, (f + 0.35) / 1.2)) * 0.5

    col = [0.0, 0.0, 0.0]
    for i in range(3):
        base = BG[i] + (DEEP[i] - BG[i]) * glow
        col[i] = base + (CRYSTAL[i] - base) * t
        col[i] *= 0.35 + 0.65 * edge
    a = int(255 * min(1.0, edge * 1.4))
    return (int(col[0]), int(col[1]), int(col[2]), a)


def png_bytes(size):
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            px = shade(size, x, y)
            if px is None:
                row += bytes((0, 0, 0, 0))
            else:
                row += bytes(max(0, min(255, c)) for c in px)
        rows.append(bytes(row))
    raw = b''.join(rows)

    def chunk(tag, payload):
        return (struct.pack('>I', len(payload)) + tag + payload +
                struct.pack('>I', zlib.crc32(tag + payload) & 0xffffffff))

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))


def main():
    out_ico = sys.argv[1] if len(sys.argv) > 1 else 'installer/antinode.ico'
    images = [(s, png_bytes(s)) for s in SIZES]

    header = struct.pack('<HHH', 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b'', b''
    for size, data in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack('<BBBBHHII', dim, dim, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)

    os.makedirs(os.path.dirname(out_ico) or '.', exist_ok=True)
    open(out_ico, 'wb').write(header + entries + blobs)
    preview = os.path.splitext(out_ico)[0] + '-preview.png'
    open(preview, 'wb').write(dict(images)[256])
    print("wrote %s (%d sizes) and %s" % (out_ico, len(images), preview))


if __name__ == '__main__':
    main()
