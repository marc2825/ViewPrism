"""Minimal OpenEXR scanline encoder/decoder (stdlib zlib + NumPy, no bpy).

Writes single-part scanline files with FLOAT / UINT channels and NONE, ZIPS or ZIP
compression (the lossless codecs every OpenEXR reader supports). The decoder exists
for round-trip verification and also reads HALF channels. Arrays are top-left row
order, which matches EXR's INCREASING_Y line order with y = row.
"""
import struct
import zlib

import numpy as np

MAGIC = 20000630
NO_COMPRESSION, ZIPS_COMPRESSION, ZIP_COMPRESSION = 0, 2, 3
_LINES_PER_BLOCK = {NO_COMPRESSION: 1, ZIPS_COMPRESSION: 1, ZIP_COMPRESSION: 16}
_COMPRESSION_NAMES = {'NONE': NO_COMPRESSION, 'ZIPS': ZIPS_COMPRESSION, 'ZIP': ZIP_COMPRESSION}
UINT, HALF, FLOAT = 0, 1, 2
_NP = {UINT: np.dtype('<u4'), HALF: np.dtype('<f2'), FLOAT: np.dtype('<f4')}


class ExrError(ValueError):
    pass


def _attr(name, kind, value):
    return name.encode() + b'\0' + kind.encode() + b'\0' + struct.pack('<i', len(value)) + value


def _zip_pack(raw):
    t = np.frombuffer(raw, dtype=np.uint8)
    n = t.size
    half = (n + 1) // 2
    tmp = np.empty(n, dtype=np.uint8)
    tmp[:half] = t[0::2]
    tmp[half:] = t[1::2]
    d = tmp.astype(np.int16)
    d[1:] = (tmp[1:].astype(np.int16) - tmp[:-1].astype(np.int16) + 128 + 256) & 255
    return zlib.compress(d.astype(np.uint8).tobytes(), 6)


def _zip_unpack(data, expected):
    d = np.frombuffer(zlib.decompress(data), dtype=np.uint8)
    if d.size != expected:
        raise ExrError('ZIP block has unexpected size')
    acc = np.cumsum(np.concatenate([d[:1].astype(np.int64), d[1:].astype(np.int64) - 128]))
    t = (acc & 255).astype(np.uint8)
    half = (expected + 1) // 2
    out = np.empty(expected, dtype=np.uint8)
    out[0::2] = t[:half]
    out[1::2] = t[half:]
    return out.tobytes()


def encode(channels, compression='ZIP'):
    """channels: dict name -> (H,W) array; float arrays are stored as FLOAT, unsigned
    integer arrays as UINT. Returns EXR file bytes."""
    if compression not in _COMPRESSION_NAMES:
        raise ExrError(f'unsupported compression {compression!r}')
    comp = _COMPRESSION_NAMES[compression]
    if not channels:
        raise ExrError('no channels')
    names = sorted(channels, key=lambda s: s.encode())   # EXR stores channels sorted by name
    arrays, types = [], []
    shape = None
    for nm in names:
        if not nm or '\0' in nm or len(nm.encode()) > 255:
            raise ExrError(f'invalid channel name {nm!r}')
        a = np.asarray(channels[nm])
        if a.ndim != 2:
            raise ExrError(f'channel {nm!r} must be 2-D')
        shape = shape or a.shape
        if a.shape != shape:
            raise ExrError('all channels must have the same shape')
        if a.dtype.kind == 'f':
            types.append(FLOAT)
            arrays.append(np.ascontiguousarray(a, dtype='<f4'))
        elif a.dtype.kind in 'ub':
            if a.dtype.kind == 'u' and a.dtype.itemsize > 4:
                raise ExrError('UINT channels are limited to 32 bits')
            types.append(UINT)
            arrays.append(np.ascontiguousarray(a, dtype='<u4'))
        else:
            raise ExrError(f'channel {nm!r}: unsupported dtype {a.dtype}')
    h, w = shape
    if h < 1 or w < 1:
        raise ExrError('empty image')
    chlist = b''.join(nm.encode() + b'\0' + struct.pack('<iB3xii', t, 0, 1, 1)
                      for nm, t in zip(names, types)) + b'\0'
    box = struct.pack('<iiii', 0, 0, w - 1, h - 1)
    header = (struct.pack('<ii', MAGIC, 2)
              + _attr('channels', 'chlist', chlist)
              + _attr('compression', 'compression', struct.pack('<B', comp))
              + _attr('dataWindow', 'box2i', box)
              + _attr('displayWindow', 'box2i', box)
              + _attr('lineOrder', 'lineOrder', struct.pack('<B', 0))
              + _attr('pixelAspectRatio', 'float', struct.pack('<f', 1.0))
              + _attr('screenWindowCenter', 'v2f', struct.pack('<ff', 0.0, 0.0))
              + _attr('screenWindowWidth', 'float', struct.pack('<f', 1.0))
              + b'\0')
    lpb = _LINES_PER_BLOCK[comp]
    nblocks = (h + lpb - 1) // lpb
    # Interleave per scanline: [ch0 row][ch1 row]...
    rows = np.concatenate([a.view(np.uint8).reshape(h, w * 4) for a in arrays], axis=1)
    blocks = []
    for b in range(nblocks):
        y0 = b * lpb
        raw = rows[y0:y0 + lpb].tobytes()
        if comp == NO_COMPRESSION:
            payload = raw
        else:
            packed = _zip_pack(raw)
            payload = packed if len(packed) < len(raw) else raw
        blocks.append(struct.pack('<ii', y0, len(payload)) + payload)
    offsets = []
    pos = len(header) + 8 * nblocks
    for blk in blocks:
        offsets.append(pos)
        pos += len(blk)
    return header + struct.pack(f'<{nblocks}Q', *offsets) + b''.join(blocks)


def _read_str(data, pos):
    end = data.index(b'\0', pos)
    return data[pos:end].decode('latin-1'), end + 1


def decode(data):
    """Decode EXR bytes -> (dict name -> (H,W) array, header dict). For verification."""
    if len(data) < 8:
        raise ExrError('truncated file')
    magic, version = struct.unpack('<ii', data[:8])
    if magic != MAGIC:
        raise ExrError('not an OpenEXR file')
    if version & 0xFF != 2 or version & 0x1A00:   # tiled 0x200, deep 0x800, multi-part 0x1000
        raise ExrError(f'unsupported EXR version/flags 0x{version:x} (tiled, deep, multi-part not supported)')
    pos = 8
    header = {}
    while True:
        name, pos = _read_str(data, pos)
        if not name:
            break
        kind, pos = _read_str(data, pos)
        (size,) = struct.unpack('<i', data[pos:pos + 4])
        pos += 4
        header[name] = (kind, data[pos:pos + size])
        pos += size
    chans = []
    raw = header['channels'][1]
    p = 0
    while raw[p:p + 1] != b'\0':
        nm, p = _read_str(raw, p)
        t, _lin, xs, ys = struct.unpack('<iB3xii', raw[p:p + 16])
        p += 16
        if xs != 1 or ys != 1:
            raise ExrError('subsampled channels not supported')
        chans.append((nm, t))
    comp = header['compression'][1][0]
    if comp not in _LINES_PER_BLOCK:
        raise ExrError(f'unsupported compression id {comp}')
    x0, y0, x1, y1 = struct.unpack('<iiii', header['dataWindow'][1])
    w, h = x1 - x0 + 1, y1 - y0 + 1
    lpb = _LINES_PER_BLOCK[comp]
    nblocks = (h + lpb - 1) // lpb
    offsets = struct.unpack(f'<{nblocks}Q', data[pos:pos + 8 * nblocks])
    line_bytes = sum(w * _NP[t].itemsize for _nm, t in chans)
    out = {nm: np.empty((h, w), dtype=_NP[t].newbyteorder('=')) for nm, t in chans}
    for off in offsets:
        y, size = struct.unpack('<ii', data[off:off + 8])
        payload = data[off + 8:off + 8 + size]
        nlines = min(lpb, y1 - y + 1)
        expected = nlines * line_bytes
        block = payload if (comp == NO_COMPRESSION or size == expected) else _zip_unpack(payload, expected)
        buf = np.frombuffer(block, dtype=np.uint8).reshape(nlines, line_bytes)
        col = 0
        for nm, t in chans:
            nb = w * _NP[t].itemsize
            out[nm][y - y0:y - y0 + nlines] = buf[:, col:col + nb].copy().view(_NP[t]).reshape(nlines, w)
            col += nb
    info = dict(width=w, height=h, compression=comp, channels=[c for c, _t in chans],
                types={c: t for c, t in chans}, attributes=sorted(header))
    return out, info
