#!/usr/bin/env python3
"""Convert the uncompressed 24-bit TGA screenshots the game writes into PNG.

Pure stdlib, so verification needs no image libraries installed.
"""
import struct, sys, zlib


def convert(src, dst):
    data = open(src, 'rb').read()
    idlen, cmap, imgtype = data[0], data[1], data[2]
    if imgtype != 2 or cmap != 0:
        raise SystemExit("%s: expected an uncompressed truecolour TGA" % src)
    w, h, depth, desc = struct.unpack_from('<HHBB', data, 12)
    if depth != 24:
        raise SystemExit("%s: expected 24 bits per pixel" % src)
    off = 18 + idlen
    stride = w * 3
    rows = []
    for y in range(h):
        row = data[off + y * stride: off + (y + 1) * stride]
        # TGA stores BGR; PNG wants RGB.
        rows.append(bytes(row[i + 2 - (i % 3) * 2] if False else 0 for i in range(0)) or
                    b''.join(row[x * 3:x * 3 + 3][::-1] for x in range(w)))
    # Bit 5 of the descriptor set means the first row is the top one.
    if not (desc & 0x20):
        rows.reverse()
    raw = b''.join(b'\x00' + r for r in rows)

    def chunk(tag, payload):
        c = struct.pack('>I', len(payload)) + tag + payload
        return c + struct.pack('>I', zlib.crc32(tag + payload) & 0xffffffff)

    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw, 9))
           + chunk(b'IEND', b''))
    open(dst, 'wb').write(png)
    print("%s -> %s (%dx%d)" % (src, dst, w, h))


if __name__ == '__main__':
    for path in sys.argv[1:]:
        convert(path, path.rsplit('.', 1)[0] + '.png')
