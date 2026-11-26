# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Public capture entry point - the same function serves the UI and the test harness.

    capture(context, request) -> dict

request keys
    width, height        int, output size in pixels
    view_matrix          4x4 row-major world -> view (affine)
    projection_matrix    4x4 row-major OpenGL-style projection (NDC z in [-1, 1])
    passes               subset of ('depth', 'normal', 'object_id', 'mask')
    normal_mode          optional 'SHADED' (default: corner normals as displayed) | 'FLAT'
    id_mode              optional 'OBJECT' (default) | 'INSTANCER' | 'INSTANCE'

context must provide a VIEW_3D space (visibility follows that viewport: local view,
hidden objects, excluded collections, object-type filters).

Result (arrays are new, top-left row order, owned by the caller)
    depth      float32 (H,W)   planar view depth -Z_view in scene units, NaN background
    normal     float32 (H,W,3) camera-space unit normal (+X right, +Y up, +Z to viewer), 0 bg
    object_id  uint32 (H,W)    0 background, 1..N objects
    mask       bool (H,W)      foreground == finite depth == object_id > 0
    id_map     dict[int, str]  id -> object name (name_full)
    info, warnings, stats
"""
import time

import numpy as np

from . import projection as proj
from . import encode
from . import resources

PASSES = ('depth', 'normal', 'object_id', 'mask')
MAX_SIDE = 16384
MAX_PIXELS = 1 << 25          # 33.5 MP (e.g. 8K UHD). ~1.2 GB of GPU targets.


class CaptureError(RuntimeError):
    pass


class RequestError(CaptureError, ValueError):
    pass


class GPUCaptureError(CaptureError):
    """The GPU could not allocate or draw (for example out of GPU memory)."""


class ResourceLimitError(RequestError):
    """Not enough free memory for the requested size (see resources.check)."""


class GPUContextError(CaptureError):
    """Transient: Blender has no active GPU context (retry after the next redraw)."""


def _int(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise RequestError(f'{name} must be an integer')
    return int(value)


def validate_request(request, max_side=MAX_SIDE):
    if not isinstance(request, dict):
        raise RequestError('request must be a dict')
    w = _int(request.get('width'), 'width')
    h = _int(request.get('height'), 'height')
    if w < 1 or h < 1:
        raise RequestError('width and height must be positive')
    if w > max_side or h > max_side:
        raise RequestError(f'resolution {w}x{h} exceeds the maximum side of {max_side} px')
    if w * h > MAX_PIXELS:
        raise RequestError(f'resolution {w}x{h} exceeds the limit of {MAX_PIXELS:,} pixels')
    try:
        view = proj.as_matrix(request.get('view_matrix'), 'view_matrix')
        p = proj.as_matrix(request.get('projection_matrix'), 'projection_matrix')
    except proj.ProjectionError as exc:
        raise RequestError(str(exc)) from exc
    if not proj.is_affine(view):
        raise RequestError('view_matrix must be affine (last row 0 0 0 1)')
    if abs(np.linalg.det(view[:3, :3])) < 1e-300:
        raise RequestError('view_matrix is singular')
    try:
        proj.validate_projection(p)
    except proj.ProjectionError as exc:
        raise RequestError(str(exc)) from exc
    passes = request.get('passes')
    if not isinstance(passes, (list, tuple)) or not passes:
        raise RequestError('passes must be a non-empty list')
    unknown = [x for x in passes if x not in PASSES]
    if unknown:
        raise RequestError(f'unknown passes: {unknown}')
    normal_mode = request.get('normal_mode', 'SHADED')
    id_mode = request.get('id_mode', 'OBJECT')
    return dict(width=w, height=h, view=view, projection=p, passes=tuple(dict.fromkeys(passes)),
                normal_mode=normal_mode, id_mode=id_mode)


def _view3d_space(context):
    space = getattr(context, 'space_data', None)
    if space is None or getattr(space, 'type', None) != 'VIEW_3D':
        area = getattr(context, 'area', None)
        if area is not None and area.type == 'VIEW_3D':
            space = area.spaces.active
        else:
            raise CaptureError('a 3D Viewport context is required')
    return space


_known_windows = None


def remember_windows(context):
    """Record the current set of windows (called at registration and after each capture)."""
    global _known_windows
    wm = getattr(context, 'window_manager', None)
    if wm is not None:
        _known_windows = frozenset(w.as_pointer() for w in wm.windows)


def _ensure_gpu_context(context):
    """After a window was opened or closed Blender may have no current GPU context until it
    redraws. On Blender 4.5 GPU calls in that state crash (5.x raises an error), so draw the
    windows once first. This only happens when the set of windows changed since the last capture."""
    import bpy
    wm = context.window_manager
    current = frozenset(w.as_pointer() for w in wm.windows)
    if _known_windows is not None and current != _known_windows and len(wm.windows):
        from . import gpu_draw
        gpu_draw.release_targets()          # never carry GPU objects across a window change
        win = context.window if context.window is not None else wm.windows[0]
        with context.temp_override(window=win, screen=win.screen):
            bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1)
    remember_windows(context)


def capture(context, request, *, _after_draw=None):
    import bpy
    from . import gpu_draw, scene_geometry

    if bpy.app.background:
        raise CaptureError('GPU capture needs Blender with a user interface (not --background)')
    t0 = time.perf_counter()
    req = validate_request(request)
    space = _view3d_space(context)
    try:
        mem = resources.check(req['width'], req['height'], export=False)
    except resources.ResourceError as exc:
        raise ResourceLimitError(str(exc)) from exc
    _ensure_gpu_context(context)
    view_layer = context.view_layer
    depsgraph = context.evaluated_depsgraph_get()
    w, h = req['width'], req['height']
    kind, near, far = proj.clip_range(req['projection'])
    depth_params = proj.depth_mapping(req['projection'])

    items, meshes, warnings, stats = scene_geometry.collect(
        depsgraph, view_layer, space, normal_mode=req['normal_mode'], id_mode=req['id_mode'])
    keys = sorted({it.key for it in items})
    if len(keys) > encode.ID_GPU_MAX:
        raise CaptureError(f'{len(keys)} ids exceed the supported maximum of {encode.ID_GPU_MAX}')
    ids = {k: i + 1 for i, k in enumerate(keys)}
    for it in items:
        it.id = ids[it.key]
    t_collect = time.perf_counter()

    try:
        sh = gpu_draw.shader()
        batches = gpu_draw.make_batches(meshes, sh)
        meshes = None
        t_upload = time.perf_counter()
        geom, ident = gpu_draw.render(w, h, req['view'], req['projection'], items, batches,
                                      depth_params, _after_draw=_after_draw)
    except RuntimeError as exc:
        if 'GPU context' in str(exc):
            # e.g. directly after a window was closed, before Blender redraws another window
            raise GPUContextError('no active GPU context right now (for example just after closing a '
                                  'window); try again') from exc
        raise GPUCaptureError(f'GPU error ({exc}); try a lower resolution') from exc
    batches = None
    t_gpu = time.perf_counter()

    mask = ident[..., 1] > 0.5                       # coverage: the single foreground test
    out = {}
    if 'depth' in req['passes']:
        out['depth'] = np.where(mask, geom[..., 3], np.float32(np.nan))
    if 'normal' in req['passes']:
        # normalised per fragment in the shader; background forced to exactly 0
        out['normal'] = np.where(mask[..., None], geom[..., :3], np.float32(0.0))
    if 'object_id' in req['passes']:
        out['object_id'] = np.where(mask, ident[..., 0], np.float32(0.0)).astype(np.uint32)
    if 'mask' in req['passes']:
        out['mask'] = mask
    geom = ident = None
    if not mask.any():
        warnings.append(('nothing visible: the capture is empty',) * 2)
    if mem['warning']:
        warnings.append((mem['warning'],) * 2)
    t_post = time.perf_counter()

    out['id_map'] = {i: k for k, i in ids.items()}
    out['warnings'] = [w[0] for w in warnings]               # for the UI (may name objects)
    out['warnings_anonymous'] = [w[1] for w in warnings]     # same warnings without object names
    stats.update(width=w, height=h, foreground_pixels=int(mask.sum()),
                 seconds=dict(collect=t_collect - t0, upload=t_upload - t_collect,
                              gpu_draw_readback=t_gpu - t_upload, post=t_post - t_gpu,
                              total=t_post - t0))
    out['stats'] = stats
    out['info'] = dict(width=w, height=h, projection=kind, near=near, far=far,
                       view_matrix=req['view'].tolist(), projection_matrix=req['projection'].tolist(),
                       normal_mode=req['normal_mode'], id_mode=req['id_mode'],
                       frame=context.scene.frame_current, frame_float=float(getattr(context.scene, 'frame_float', context.scene.frame_current)),
                       blender=bpy.app.version_string, passes=list(req['passes']))
    return out
