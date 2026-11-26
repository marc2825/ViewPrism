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


def encode(arr, compress_level=6):
    """Encode an image array to PNG bytes. Per-row filter chosen among None/Sub/Up."""
    a = _as_image(arr)
    h, w, c = a.shape
    bits = 8 if a.dtype == np.uint8 else 16
    raw = np.ascontiguousarray(a.astype('>u2') if bits == 16 else a).view(np.uint8).reshape(h, -1)
    bpp = c * bits // 8
    sub = raw.copy()
    sub[:, bpp:] -= raw[:, :-bpp]          # uint8 arithmetic wraps mod 256 as PNG requires
    up = raw.copy()
    up[1:] -= raw[:-1]
    cands = (raw, sub, up)
    # libpng heuristic: minimise the sum of absolute values of the signed residuals.
    cost = np.stack([np.abs(c_.view(np.int8).astype(np.int16)).sum(axis=1, dtype=np.int64)
                     for c_ in cands])                                    # (3, H)
    choice = cost.argmin(axis=0)                                           # 0 none, 1 sub, 2 up
    rows = np.where((choice == 0)[:, None], raw, np.where((choice == 1)[:, None], sub, up))
    filtered = np.concatenate([choice.astype(np.uint8)[:, None], rows], axis=1)
    ihdr = struct.pack('>IIBBBBB', w, h, bits, _COLOR_TYPES[c], 0, 0, 0)
    return (_SIG + _chunk(b'IHDR', ihdr)
            + _chunk(b'IDAT', zlib.compress(filtered.tobytes(), compress_level))
            + _chunk(b'IEND', b''))


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
