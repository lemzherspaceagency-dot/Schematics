#!/usr/bin/env python3
"""Generate installer/antinode.ico (and a PNG preview).

The icon is the game's own premise: two wave sources whose crests cross into
a standing pattern, drawn with the same maths the Vault uses.
"""
import math, os, struct, sys, zlib

SIZES = [16, 24, 32, 48, 64, 128, 256]

BG     = (10, 8, 6)
CREAM  = (236, 225, 205)
ROSE   = (207, 143, 124)
CYAN   = (95, 201, 194)


def shade(size, x, y):
    u = (x + 0.5) / size * 2.0 - 1.0
    v = 1.0 - (y + 0.5) / size * 2.0
    r = math.hypot(u, v)
    if r > 0.97:
        return None
    edge = max(0.0, min(1.0, (0.97 - r) / 0.10))

    # Aurora's own visual language: a cream head, a rose collar ring, and a
    # cold cyan scan arc sweeping past it -- the warm face and the machine
    # underneath, in one small mark.
    head_d = math.hypot(u, v + 0.18)
    head = max(0.0, 1.0 - head_d / 0.34)

    collar_d = abs(math.hypot(u, v + 0.02) - 0.30)
    collar = max(0.0, 1.0 - collar_d / 0.05)

    scan_d = abs(r - 0.74)
    ang = math.atan2(v, u)
    scan_gate = max(0.0, math.sin(ang * 0.5 + 0.6))
    scan = max(0.0, 1.0 - scan_d / 0.05) * scan_gate

    col = [BG[0], BG[1], BG[2]]
    if scan > 0.0:
        for i in range(3):
            col[i] = col[i] + (CYAN[i] - col[i]) * scan
    if collar > 0.0:
        for i in range(3):
            col[i] = col[i] + (ROSE[i] - col[i]) * collar
    if head > 0.0:
        for i in range(3):
            col[i] = col[i] + (CREAM[i] - col[i]) * head

    for i in range(3):
        col[i] *= 0.30 + 0.70 * edge
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
    out_ico = sys.argv[1] if len(sys.argv) > 1 else 'installer/aurora.ico'
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
