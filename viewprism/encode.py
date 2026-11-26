# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure conversions from raw pass arrays to display/encoded arrays (NumPy only, no bpy).

Raw arrays (the capture result) are never modified; every function returns new arrays.
"""
import math

import numpy as np

ID_PNG_MAX = 65535            # 16-bit grayscale PNG, value == object id, 0 == background
ID_GPU_MAX = (1 << 24) - 1    # ids travel through a float32 render target (exact up to 2**24)
CHUNK_PIXELS = 1 << 20        # pixels per chunk in chunked encoders (bounded temporaries)


class EncodeError(ValueError):
    pass


class IdOverflowError(EncodeError):
    pass


# --------------------------------------------------------------------------- depth

def depth_range(depth, mask, mode='AUTO', near=None, far=None):
    """Resolve the display range.

    Returns dict(lo, hi, flat, empty, mode). AUTO uses the finite foreground min/max.
    FIXED uses (near, far) as given; near > far is allowed (linear mapping still
    defined, which flips the ramp) but near == far or non-finite values are errors.
    """
    mask = np.asarray(mask, dtype=bool)
    fg = np.asarray(depth)[mask]
    fg = fg[np.isfinite(fg)]
    empty = fg.size == 0
    if mode == 'AUTO':
        if empty:
            return dict(mode=mode, lo=None, hi=None, flat=False, empty=True)
        lo, hi = float(fg.min()), float(fg.max())
        return dict(mode=mode, lo=lo, hi=hi, flat=(hi - lo) <= 0.0, empty=False)
    if mode == 'FIXED':
        if near is None or far is None or not (math.isfinite(near) and math.isfinite(far)):
            raise EncodeError('fixed depth range needs finite Near and Far values')
        if near == far:
            raise EncodeError('fixed depth range: Near and Far must differ')
        return dict(mode=mode, lo=float(near), hi=float(far), flat=False, empty=empty)
    raise EncodeError(f'unknown depth range mode {mode!r}')


def background_value(background, near_white):
    """Resolve the depth display background ('FAR', 'NEAR' or a value in [0, 1])."""
    near_value, far_value = (1.0, 0.0) if near_white else (0.0, 1.0)
    if background == 'FAR':
        return far_value
    if background == 'NEAR':
        return near_value
    bg = float(background)
    if not (0.0 <= bg <= 1.0):
        raise EncodeError('background value must be within [0, 1]')
    return bg


def normalize_depth(depth, mask, mode='AUTO', near=None, far=None, near_white=True, background='FAR',
                    dtype=np.float32, _range=None):
    """Map raw depth to a [0, 1] display image (float32 by default; float64 for file encoding).

    * Linear in depth between the resolved range; values outside a FIXED range clamp.
    * ``near_white``: nearest = 1.0 (white) and farthest = 0.0; otherwise reversed.
    * ``background``: 'FAR' (the far colour, i.e. as if infinitely far), 'NEAR', or a
      float in [0, 1].
    * A constant-depth foreground (AUTO range with min == max) is drawn with the near
      colour so it always contrasts with the default background.
    * Foreground pixels with non-finite depth are treated as background and counted.
    Returns (image, info) where info records the range actually used.
    """
    depth = np.asarray(depth, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    if depth.shape != mask.shape:
        raise EncodeError('depth/mask shape mismatch')
    info = dict(_range) if _range is not None else depth_range(depth, mask, mode, near, far)
    near_value, far_value = (1.0, 0.0) if near_white else (0.0, 1.0)
    bg = background_value(background, near_white)
    valid = mask & np.isfinite(depth)
    info['invalid_foreground'] = int((mask & ~np.isfinite(depth)).sum())
    if info['empty']:
        out = np.full(depth.shape, bg, dtype=dtype)
    elif info['flat']:
        out = np.where(valid, near_value, bg).astype(dtype)
    else:
        with np.errstate(invalid='ignore'):
            t = (depth - info['lo']) * (1.0 / (info['hi'] - info['lo']))   # 0 at lo (near), 1 at hi (far)
        np.clip(t, 0.0, 1.0, out=t)
        if near_white:
            np.subtract(1.0, t, out=t)
        out = np.where(valid, t, bg).astype(dtype)
    info.update(near_white=bool(near_white), background=float(bg))
    return out, info


# --------------------------------------------------------------------------- normal / mask / id

def normal_to_rgb(normal, mask, background=(0.0, 0.0, 0.0), dtype=np.float32):
    """Signed camera-space normals -> RGB in [0, 1] using n * 0.5 + 0.5 (no colour management)."""
    normal = np.asarray(normal, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    out = np.empty(normal.shape, dtype=np.float64)
    out[...] = np.asarray(background, dtype=np.float64)
    out[mask] = np.clip(normal[mask] * 0.5 + 0.5, 0.0, 1.0)
    return out.astype(dtype)


def quantize(img01, bits):
    """[0, 1] float -> uint8/uint16 with round-to-nearest (0 and 1 map exactly)."""
    if bits not in (8, 16):
        raise EncodeError('bit depth must be 8 or 16')
    maxv = (1 << bits) - 1
    a = np.asarray(img01, dtype=np.float64)
    if not np.isfinite(a).all():
        raise EncodeError('cannot quantize non-finite values')
    q = np.floor(np.clip(a, 0.0, 1.0) * maxv + 0.5)
    return q.astype(np.uint8 if bits == 8 else np.uint16)


def quantize_normal(normal, mask, bits, background=(0.0, 0.0, 0.0)):
    """Exact, fast equivalent of quantize(normal_to_rgb(...), bits).

    round((n * 0.5 + 0.5) * M) == floor(n * M/2 + (M + 1)/2) and, for float32 n, the product
    and sum are exact in float64, so ties round exactly as in the reference formula.
    """
    if bits not in (8, 16):
        raise EncodeError('bit depth must be 8 or 16')
    maxv = (1 << bits) - 1
    normal = np.asarray(normal, dtype=np.float32)
    mask = np.asarray(mask, dtype=bool)
    dt = np.uint8 if bits == 8 else np.uint16
    out = np.empty(normal.shape, dtype=dt)
    bg = quantize(np.asarray(background, dtype=np.float64), bits)
    rows = max(1, CHUNK_PIXELS // max(1, normal.shape[1]))      # bounded float64 temporaries
    for y0 in range(0, normal.shape[0], rows):
        q = normal[y0:y0 + rows].astype(np.float64)
        q *= maxv / 2.0
        q += (maxv + 1) / 2.0
        np.floor(q, out=q)
        np.clip(q, 0, maxv, out=q)
        chunk = q.astype(dt)
        chunk[~mask[y0:y0 + rows]] = bg
        out[y0:y0 + rows] = chunk
    return out


def quantize_depth(depth, mask, bits, mode='AUTO', near=None, far=None, near_white=True, background='FAR'):
    """Chunked, bit-identical equivalent of quantize(normalize_depth(..., dtype=float64), bits).

    The display range is resolved once for the whole image; each chunk then uses exactly the same
    formula. Returns (uint array, info). Only a few MB of float64 temporaries are alive at a time.
    """
    if bits not in (8, 16):
        raise EncodeError('bit depth must be 8 or 16')
    depth = np.asarray(depth)
    mask = np.asarray(mask, dtype=bool)
    if depth.shape != mask.shape or depth.ndim != 2:
        raise EncodeError('depth/mask must be 2-D arrays of the same shape')
    full = depth_range(depth, mask, mode, near, far)
    out = np.empty(depth.shape, dtype=np.uint8 if bits == 8 else np.uint16)
    rows = max(1, CHUNK_PIXELS // max(1, depth.shape[1]))
    info = None
    for y0 in range(0, depth.shape[0], rows):
        img, part = normalize_depth(depth[y0:y0 + rows], mask[y0:y0 + rows], mode, near, far, near_white,
                                    background, dtype=np.float64, _range=full)
        out[y0:y0 + rows] = quantize(img, bits)
        info = info or part
    if info is None:                                   # zero-height image
        _img, info = normalize_depth(depth, mask, mode, near, far, near_white, background, _range=full)
    info['invalid_foreground'] = int((mask & ~np.isfinite(depth)).sum())
    return out, info


def mask_to_u8(mask):
    return np.where(np.asarray(mask, dtype=bool), 255, 0).astype(np.uint8)


def encode_id_u16(ids):
    """Lossless 16-bit encoding: pixel value == object id, 0 == background."""
    ids = np.asarray(ids)
    if ids.size and int(ids.max()) > ID_PNG_MAX:
        raise IdOverflowError(f'object id {int(ids.max())} exceeds the 16-bit PNG limit '
                              f'{ID_PNG_MAX}; export the ID pass as EXR instead')
    if ids.size and int(ids.min()) < 0:
        raise IdOverflowError('negative object id')
    return ids.astype(np.uint16)


def decode_id_u16(values):
    return np.asarray(values).astype(np.uint32)


def id_colors(ids, mask=None):
    """Deterministic pseudo-colours for *display only* (never written as ID data)."""
    ids = np.asarray(ids, dtype=np.uint64)
    h = (ids * np.uint64(2654435761)) & np.uint64(0xFFFFFFFF)
    r = ((h >> np.uint64(0)) & np.uint64(255)).astype(np.float32)
    g = ((h >> np.uint64(8)) & np.uint64(255)).astype(np.float32)
    b = ((h >> np.uint64(16)) & np.uint64(255)).astype(np.float32)
    rgb = np.stack([r, g, b], axis=-1) / 255.0 * 0.75 + 0.25
    bg = (ids == 0) if mask is None else ~np.asarray(mask, dtype=bool)
    rgb[bg] = 0.0
    return rgb


def to_rgba(img, alpha=None):
    """Gray (H,W) or RGB (H,W,3) float -> RGBA float32 (for previews)."""
    img = np.asarray(img, dtype=np.float32)
    if img.ndim == 2:
        img = np.repeat(img[..., None], 3, axis=-1)
    a = np.ones(img.shape[:2], np.float32) if alpha is None else np.asarray(alpha, np.float32)
    return np.concatenate([img, a[..., None]], axis=-1)
