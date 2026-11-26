# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal lossless PNG encoder/decoder (stdlib zlib + NumPy, no bpy).

Writing PNG bytes directly keeps exports free of Blender colour management and
avoids creating image datablocks. Supports 8/16-bit gray, gray+alpha, RGB, RGBA,
non-interlaced. Arrays are top-left row order.
"""
import struct
import zlib

import numpy as np

_SIG = b'\x89PNG\r\n\x1a\n'
_COLOR_TYPES = {1: 0, 2: 4, 3: 2, 4: 6}          # channels -> PNG colour type
_CHANNELS = {v: k for k, v in _COLOR_TYPES.items()}


class PngError(ValueError):
    pass


def _chunk(kind, data):
    return (struct.pack('>I', len(data)) + kind + data
            + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF))


def _as_image(arr):
    a = np.asarray(arr)
    if a.dtype not in (np.uint8, np.uint16):
        raise PngError(f'PNG data must be uint8 or uint16, got {a.dtype}')
    if a.ndim == 2:
        a = a[..., None]
    if a.ndim != 3 or a.shape[2] not in _COLOR_TYPES:
        raise PngError(f'PNG data must be (H,W) or (H,W,C) with C in 1..4, got {a.shape}')
    h, w, _c = a.shape
    if h < 1 or w < 1 or h > 0x7FFFFFFF or w > 0x7FFFFFFF:
        raise PngError('invalid PNG dimensions')
    return a


CHUNK_BYTES = 1 << 22          # ~4 MB of raw scanlines per step keeps encoder memory bounded


def encode(arr, compress_level=5):
    """Encode an image array to PNG bytes. Per-row filter chosen among None/Sub/Up.

    Rows are filtered and compressed in chunks (streaming zlib), so the temporary memory does not
    grow with the image size beyond a few MB plus the compressed output.
    """
    a = _as_image(arr)
    h, w, c = a.shape
    bits = 8 if a.dtype == np.uint8 else 16
    bpp = c * bits // 8
    rowbytes = w * bpp
    rows_per = max(1, CHUNK_BYTES // max(1, rowbytes))
    step = 4 if rowbytes >= 64 else 1
    comp = zlib.compressobj(compress_level)
    parts = []
    prev = None                              # last raw row of the previous chunk (for the Up filter)
    for y0 in range(0, h, rows_per):
        block = a[y0:y0 + rows_per]
        raw = np.ascontiguousarray(block.astype('>u2') if bits == 16 else block).view(np.uint8).reshape(len(block), -1)
        sub = raw.copy()
        sub[:, bpp:] -= raw[:, :-bpp]          # uint8 arithmetic wraps mod 256 as PNG requires
        up = raw.copy()
        up[1:] -= raw[:-1]
        if prev is not None:
            up[0] -= prev
        # libpng heuristic (minimum sum of absolute signed residuals), estimated on a column
        # subsample for speed. Only the filter choice is approximate; the output is lossless.
        cost = np.stack([np.abs(c_[:, ::step].view(np.int8).astype(np.int16)).sum(axis=1, dtype=np.int64)
                         for c_ in (raw, sub, up)])                           # (3, rows)
        choice = cost.argmin(axis=0)                                           # 0 none, 1 sub, 2 up
        rows = np.where((choice == 0)[:, None], raw, np.where((choice == 1)[:, None], sub, up))
        filtered = np.concatenate([choice.astype(np.uint8)[:, None], rows], axis=1)
        parts.append(comp.compress(filtered.tobytes()))
        prev = raw[-1].copy()
    parts.append(comp.flush())
    ihdr = struct.pack('>IIBBBBB', w, h, bits, _COLOR_TYPES[c], 0, 0, 0)
    return (_SIG + _chunk(b'IHDR', ihdr) + _chunk(b'IDAT', b''.join(parts)) + _chunk(b'IEND', b''))


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode(data):
    """Decode PNG bytes -> (array (H,W,C) uint8/uint16, info dict). For verification."""
    if not data.startswith(_SIG):
        raise PngError('not a PNG file')
    pos = len(_SIG)
    idat = []
    ihdr = None
    chunks = []
    while pos < len(data):
        if pos + 8 > len(data):
            raise PngError('truncated chunk header')
        (length,) = struct.unpack('>I', data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack('>I', data[pos + 8 + length:pos + 12 + length])
        if zlib.crc32(kind + body) & 0xFFFFFFFF != crc:
            raise PngError(f'CRC mismatch in {kind!r}')
        chunks.append(kind.decode('latin-1'))
        if kind == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', body)
        elif kind == b'IDAT':
            idat.append(body)
        elif kind == b'IEND':
            break
        pos += 12 + length
    if ihdr is None:
        raise PngError('missing IHDR')
    w, h, bits, ctype, _comp, _filt, interlace = ihdr
    if interlace or bits not in (8, 16) or ctype not in _CHANNELS:
        raise PngError(f'unsupported PNG (bits={bits}, colour type={ctype}, interlace={interlace})')
    c = _CHANNELS[ctype]
    bpp = c * bits // 8
    stride = w * bpp
    buf = np.frombuffer(zlib.decompress(b''.join(idat)), dtype=np.uint8)
    if buf.size != h * (stride + 1):
        raise PngError('unexpected decompressed size')
    buf = buf.reshape(h, stride + 1)
    out = np.zeros((h, stride), dtype=np.uint8)
    prev = np.zeros(stride, dtype=np.int64)
    for y in range(h):
        f = int(buf[y, 0])
        line = buf[y, 1:].astype(np.int64)
        if f == 0:
            rec = line
        elif f == 1:
            rec = np.empty_like(line)
            for k in range(bpp):
                rec[k::bpp] = np.cumsum(line[k::bpp]) & 255
        elif f == 2:
            rec = (line + prev) & 255
        elif f in (3, 4):
            rec = np.zeros_like(line)
            ln, pv = line.tolist(), prev.tolist()
            rl = [0] * stride
            for x in range(stride):
                a = rl[x - bpp] if x >= bpp else 0
                b = pv[x]
                if f == 3:
                    rl[x] = (ln[x] + ((a + b) >> 1)) & 255
                else:
                    cc = pv[x - bpp] if x >= bpp else 0
                    rl[x] = (ln[x] + _paeth(a, b, cc)) & 255
            rec = np.array(rl, dtype=np.int64)
        else:
            raise PngError(f'bad filter type {f}')
        out[y] = rec
        prev = rec
    if bits == 16:
        arr = out.reshape(h, w * c * 2).view('>u2').astype(np.uint16).reshape(h, w, c)
    else:
        arr = out.reshape(h, w, c)
    return arr, dict(width=w, height=h, bit_depth=bits, channels=c, chunks=chunks)
