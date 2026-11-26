# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
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
ZLIB_LEVEL = 4      # speed/size balance for float data (lossless at any level)


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
    d = np.empty_like(tmp)
    d[0] = tmp[0]
    np.subtract(tmp[1:], tmp[:-1], out=d[1:])     # uint8 arithmetic wraps mod 256
    d[1:] += 128
    return zlib.compress(d.tobytes(), ZLIB_LEVEL)


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
    # Interleave per scanline ([ch0 row][ch1 row]...), one block at a time (bounded memory).
    blocks = []
    for b in range(nblocks):
        y0 = b * lpb
        raw = np.concatenate([a[y0:y0 + lpb].view(np.uint8).reshape(-1, w * 4) for a in arrays], axis=1).tobytes()
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


def _read_header(data, pos):
    header = {}
    while True:
        name, pos = _read_str(data, pos)
        if not name:
            return header, pos
        kind, pos = _read_str(data, pos)
        (size,) = struct.unpack('<i', data[pos:pos + 4])
        pos += 4
        header[name] = (kind, data[pos:pos + size])
        pos += size


def _part_layout(header):
    chans = []
    raw = header['channels'][1]
    p = 0
    while raw[p:p + 1] != b'\0':
        nm, p = _read_str(raw, p)
        t, _lin, xs, ys = struct.unpack('<iB3xii', raw[p:p + 16])
        p += 16
        if xs != 1 or ys != 1:
            raise ExrError('subsampled channels not supported')
        if t not in _NP:
            raise ExrError(f'unknown pixel type {t}')
        chans.append((nm, t))
    comp = header['compression'][1][0]
    if comp not in _LINES_PER_BLOCK:
        raise ExrError(f'unsupported compression id {comp} (only NONE, ZIPS, ZIP)')
    if 'type' in header and header['type'][1].rstrip(b'\0') != b'scanlineimage':
        raise ExrError(f"unsupported part type {header['type'][1]!r}")
    x0, y0, x1, y1 = struct.unpack('<iiii', header['dataWindow'][1])
    w, h = x1 - x0 + 1, y1 - y0 + 1
    lpb = _LINES_PER_BLOCK[comp]
    return dict(chans=chans, comp=comp, x0=x0, y0=y0, x1=x1, y1=y1, w=w, h=h, lpb=lpb,
                nblocks=(h + lpb - 1) // lpb, line_bytes=sum(w * _NP[t].itemsize for _nm, t in chans))


def _read_chunk(data, off, lay, out, multipart):
    if multipart:
        off += 4                          # part number
    y, size = struct.unpack('<ii', data[off:off + 8])
    payload = data[off + 8:off + 8 + size]
    nlines = min(lay['lpb'], lay['y1'] - y + 1)
    expected = nlines * lay['line_bytes']
    block = payload if (lay['comp'] == NO_COMPRESSION or size == expected) else _zip_unpack(payload, expected)
    buf = np.frombuffer(block, dtype=np.uint8).reshape(nlines, lay['line_bytes'])
    col = 0
    w = lay['w']
    for nm, t in lay['chans']:
        nb = w * _NP[t].itemsize
        out[nm][y - lay['y0']:y - lay['y0'] + nlines] = buf[:, col:col + nb].copy().view(_NP[t]).reshape(nlines, w)
        col += nb


def decode(data):
    """Decode EXR bytes -> (dict name -> (H,W) array, info dict). For verification.

    Supports single-part and multi-part scanline files (NONE/ZIPS/ZIP). In multi-part files
    channel names are returned as '<part name>.<channel>'.
    """
    if len(data) < 8:
        raise ExrError('truncated file')
    magic, version = struct.unpack('<ii', data[:8])
    if magic != MAGIC:
        raise ExrError('not an OpenEXR file')
    if version & 0xFF != 2 or version & 0x0A00:   # tiled 0x200, deep 0x800
        raise ExrError(f'unsupported EXR version/flags 0x{version:x} (tiled or deep)')
    multipart = bool(version & 0x1000)
    pos = 8
    headers = []
    while True:
        header, pos = _read_header(data, pos)
        if not header:
            break
        headers.append(header)
        if not multipart:
            break
    if not headers:
        raise ExrError('no header')
    layouts = [_part_layout(hd) for hd in headers]
    out, types, attrs = {}, {}, set()
    for hd, lay in zip(headers, layouts):
        attrs.update(hd)
        offsets = struct.unpack(f"<{lay['nblocks']}Q", data[pos:pos + 8 * lay['nblocks']])
        pos += 8 * lay['nblocks']
        part = {nm: np.empty((lay['h'], lay['w']), dtype=_NP[t].newbyteorder('=')) for nm, t in lay['chans']}
        for off in offsets:
            _read_chunk(data, off, lay, part, multipart)
        prefix = hd['name'][1].rstrip(b'\0').decode('utf-8', 'replace') + '.' if (multipart and 'name' in hd) else ''
        for nm, t in lay['chans']:
            key = nm if (not prefix or nm.startswith(prefix)) else prefix + nm
            out[key] = part[nm]
            types[key] = t
    lay0 = layouts[0]
    info = dict(width=lay0['w'], height=lay0['h'], compression=lay0['comp'], channels=list(out),
                types=types, attributes=sorted(attrs), parts=len(headers), multipart=multipart)
    return out, info
