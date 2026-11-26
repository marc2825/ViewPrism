# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import struct
import sys
import tracemalloc
import unittest
import zlib

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from viewprism import exr, png  # noqa: E402

rng = np.random.default_rng(1234)


class Png(unittest.TestCase):
    def test_roundtrip_all_layouts(self):
        for dtype in (np.uint8, np.uint16):
            hi = np.iinfo(dtype).max
            for c in (1, 2, 3, 4):
                for shape in ((1, 1), (7, 5), (33, 64)):
                    a = rng.integers(0, hi + 1, size=(*shape, c), dtype=np.int64).astype(dtype)
                    a[0, 0] = 0
                    a[-1, -1] = hi
                    data = png.encode(a)
                    b, info = png.decode(data)
                    self.assertEqual(info['bit_depth'], 8 if dtype == np.uint8 else 16)
                    self.assertEqual(info['channels'], c)
                    np.testing.assert_array_equal(b, a)

    def test_smooth_gradient_compresses(self):
        g = np.tile(np.arange(256, dtype=np.uint16) * 200, (64, 1))
        data = png.encode(g)
        self.assertLess(len(data), g.nbytes / 4)
        np.testing.assert_array_equal(png.decode(data)[0][..., 0], g)

    def test_gray_2d_and_errors(self):
        a = np.array([[0, 255], [128, 7]], np.uint8)
        b, info = png.decode(png.encode(a))
        self.assertEqual(b.shape, (2, 2, 1))
        np.testing.assert_array_equal(b[..., 0], a)
        with self.assertRaises(png.PngError):
            png.encode(np.zeros((2, 2), np.float32))
        with self.assertRaises(png.PngError):
            png.encode(np.zeros((2, 2, 5), np.uint8))
        with self.assertRaises(png.PngError):
            png.decode(b'nope')
        bad = bytearray(png.encode(a))
        bad[-20] ^= 0xFF  # corrupt IDAT -> CRC mismatch
        with self.assertRaises(png.PngError):
            png.decode(bytes(bad))

    def test_header_layout_matches_spec(self):
        # Independent check of the IHDR bytes against the PNG specification.
        data = png.encode(np.zeros((3, 5), np.uint16))
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        length, kind = struct.unpack('>I4s', data[8:16])
        self.assertEqual((length, kind), (13, b'IHDR'))
        w, h, bits, ctype, comp, filt, inter = struct.unpack('>IIBBBBB', data[16:29])
        self.assertEqual((w, h, bits, ctype, comp, filt, inter), (5, 3, 16, 0, 0, 0, 0))

    def test_decode_reference_filters(self):
        # Hand-built PNG using Average (3) and Paeth (4) filters (not produced by the encoder).
        raw = np.array([[10, 20, 30], [40, 50, 60], [5, 5, 200]], np.uint8)
        rows = [bytes([0]) + raw[0].tobytes()]
        prev = raw[0].astype(int)
        line = []
        for x in range(3):                                       # Average filter row 1
            a = raw[1, x - 1] if x else 0
            line.append((int(raw[1, x]) - ((int(a) + int(prev[x])) >> 1)) & 255)
        rows.append(bytes([3] + line))
        prev2 = raw[1].astype(int)
        line = []
        for x in range(3):                                       # Paeth filter row 2
            a = int(raw[2, x - 1]) if x else 0
            b = int(prev2[x])
            c = int(prev2[x - 1]) if x else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            line.append((int(raw[2, x]) - pred) & 255)
        rows.append(bytes([4] + line))
        body = struct.pack('>IIBBBBB', 3, 3, 8, 0, 0, 0, 0)

        def chunk(k, d):
            return struct.pack('>I', len(d)) + k + d + struct.pack('>I', zlib.crc32(k + d) & 0xFFFFFFFF)
        data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', body) + chunk(b'IDAT', zlib.compress(b''.join(rows))) + chunk(b'IEND', b'')
        np.testing.assert_array_equal(png.decode(data)[0][..., 0], raw)


class Exr(unittest.TestCase):
    def test_roundtrip(self):
        for comp in ('NONE', 'ZIPS', 'ZIP'):
            for h, w in ((1, 1), (17, 9), (40, 33)):
                z = rng.normal(size=(h, w)).astype(np.float32) * 100
                z[0, 0] = np.nan
                z[-1, -1] = np.inf
                ids = rng.integers(0, 2**32, size=(h, w), dtype=np.uint64).astype(np.uint32)
                data = exr.encode({'Z': z, 'A': (z > 0).astype(np.float32), 'id': ids}, comp)
                out, info = exr.decode(data)
                self.assertEqual(info['channels'], ['A', 'Z', 'id'])     # sorted by name
                self.assertEqual(info['types'], {'A': exr.FLOAT, 'Z': exr.FLOAT, 'id': exr.UINT})
                np.testing.assert_array_equal(out['Z'], z)              # bit-exact incl. NaN/inf
                np.testing.assert_array_equal(out['id'], ids)
                self.assertEqual(out['Z'].dtype, np.float32)

    def test_zip_actually_compresses_smooth_data(self):
        z = np.tile(np.linspace(1, 2, 256, dtype=np.float32), (64, 1))
        self.assertLess(len(exr.encode({'Z': z}, 'ZIP')), len(exr.encode({'Z': z}, 'NONE')) / 2)

    def test_uncompressed_layout_matches_spec(self):
        # Independent byte layout check for a 2x1 FLOAT 'Z' image, NO_COMPRESSION.
        z = np.array([[1.5, -2.0]], np.float32)
        data = exr.encode({'Z': z}, 'NONE')
        self.assertEqual(struct.unpack('<ii', data[:8]), (20000630, 2))
        # Last 8 bytes: two little-endian floats; before that: y=0 and size=8
        self.assertEqual(data[-16:-8], struct.pack('<ii', 0, 8))
        self.assertEqual(data[-8:], struct.pack('<ff', 1.5, -2.0))
        # offset table points at the chunk
        (off,) = struct.unpack('<Q', data[-24:-16])
        self.assertEqual(off, len(data) - 16)
        for attr in (b'channels\0chlist\0', b'compression\0compression\0', b'dataWindow\0box2i\0',
                     b'displayWindow\0box2i\0', b'lineOrder\0lineOrder\0', b'pixelAspectRatio\0float\0',
                     b'screenWindowCenter\0v2f\0', b'screenWindowWidth\0float\0'):
            self.assertIn(attr, data)

    def test_decode_hand_built_multipart(self):
        # Two-part scanline file built from the OpenEXR spec (not by the product encoder).
        def attr(n, k, v):
            return n.encode() + b'\0' + k.encode() + b'\0' + struct.pack('<i', len(v)) + v

        def header(part, chname):
            ch = chname.encode() + b'\0' + struct.pack('<iB3xii', 2, 0, 1, 1) + b'\0'
            box = struct.pack('<iiii', 0, 0, 1, 0)                       # 2 x 1 pixels
            return (attr('channels', 'chlist', ch) + attr('compression', 'compression', b'\0')
                    + attr('dataWindow', 'box2i', box) + attr('displayWindow', 'box2i', box)
                    + attr('lineOrder', 'lineOrder', b'\0') + attr('pixelAspectRatio', 'float', struct.pack('<f', 1))
                    + attr('screenWindowCenter', 'v2f', struct.pack('<ff', 0, 0))
                    + attr('screenWindowWidth', 'float', struct.pack('<f', 1))
                    + attr('name', 'string', part.encode()) + attr('type', 'string', b'scanlineimage')
                    + attr('chunkCount', 'int', struct.pack('<i', 1)) + b'\0')
        heads = struct.pack('<ii', 20000630, 2 | 0x1000) + header('L.Depth', 'Z') + header('L.Normal', 'X') + b'\0'
        chunk0 = struct.pack('<iii', 0, 0, 8) + struct.pack('<ff', 3.5, 7.0)
        chunk1 = struct.pack('<iii', 1, 0, 8) + struct.pack('<ff', -1.0, 0.25)
        base = len(heads) + 16
        data = heads + struct.pack('<QQ', base, base + len(chunk0)) + chunk0 + chunk1
        out, info = exr.decode(data)
        self.assertTrue(info['multipart'])
        self.assertEqual(info['parts'], 2)
        np.testing.assert_array_equal(out['L.Depth.Z'], [[3.5, 7.0]])
        np.testing.assert_array_equal(out['L.Normal.X'], [[-1.0, 0.25]])

    def test_errors(self):
        with self.assertRaises(exr.ExrError):
            exr.encode({}, 'ZIP')
        with self.assertRaises(exr.ExrError):
            exr.encode({'Z': np.zeros((2, 2), np.float32), 'A': np.zeros((3, 2), np.float32)})
        with self.assertRaises(exr.ExrError):
            exr.encode({'Z': np.zeros((2, 2), np.float32)}, 'PIZ')
        with self.assertRaises(exr.ExrError):
            exr.decode(b'\0' * 16)


def _png_chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xFFFFFFFF)


def _png(w, h, idat):
    return (b'\x89PNG\r\n\x1a\n' + _png_chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
            + _png_chunk(b'IDAT', idat) + _png_chunk(b'IEND', b''))


def _peak_bytes(fn):
    tracemalloc.start()
    try:
        fn()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def _exr_single_block(data):
    """(offset-table position, chunk offset) of a single-block EXR (the table entry points just past itself)."""
    for p in range(8, len(data) - 8):
        if struct.unpack('<Q', data[p:p + 8])[0] == p + 8:
            return p, p + 8
    raise AssertionError('offset table not found')


class DecoderLimits(unittest.TestCase):
    """Issue #15: the verification decoders must not allocate or inflate without bounds."""

    def test_png_oversized_header_is_refused_before_allocating(self):
        with self.assertRaises(png.PngError):
            png.decode(_png(100000, 100000, zlib.compress(b'\0' * 64)))
        with self.assertRaises(png.PngError):
            png.decode(_png(0, 5, zlib.compress(b'')))

    def test_png_decompression_bomb_is_not_inflated(self):
        bomb = zlib.compress(b'\0' * 50_000_000, 9)                 # ~50 KB that would inflate to 50 MB
        peak = _peak_bytes(lambda: self.assertRaises(png.PngError, png.decode, _png(8, 8, bomb)))
        self.assertLess(peak, 5_000_000, 'the decoder inflated the whole stream')
        with self.assertRaises(png.PngError):
            png.decode(_png(8, 8, b'not zlib data'))

    def test_exr_oversized_data_window(self):
        data = exr.encode({'Z': np.zeros((2, 2), np.float32)}, 'NONE')
        key = b'dataWindow\0box2i\0' + struct.pack('<i', 16)
        i = data.index(key) + len(key)
        bad = data[:i] + struct.pack('<iiii', 0, 0, 99999, 99999) + data[i + 16:]
        with self.assertRaises(exr.ExrError):
            exr.decode(bad)

    def test_exr_zip_bomb_and_bad_offsets(self):
        data = exr.encode({'Z': np.ones((4, 16), np.float32)}, 'ZIP')
        table, chunk = _exr_single_block(data)
        bomb = zlib.compress(b'\0' * 50_000_000, 9)
        bombed = data[:chunk] + struct.pack('<ii', 0, len(bomb)) + bomb
        peak = _peak_bytes(lambda: self.assertRaises(exr.ExrError, exr.decode, bombed))
        self.assertLess(peak, 5_000_000, 'the decoder inflated the whole block')
        outside = data[:table] + struct.pack('<Q', len(data) + 1000) + data[table + 8:]
        with self.assertRaises(exr.ExrError):
            exr.decode(outside)
        with self.assertRaises(exr.ExrError):
            exr.decode(data[:table + 4])                                 # truncated offset table


if __name__ == '__main__':
    unittest.main()
