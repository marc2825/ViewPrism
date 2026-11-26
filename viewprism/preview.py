# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Display-only preview in the 3D viewport the capture came from.

One preview capture holds all four passes. They are shown as
* a strip of small thumbnails in the lower left corner (all passes side by side), and
* optionally one pass large over the whole viewport (the "eye" button of that pass).
Both are drawn by a POST_PIXEL handler from GPU textures owned by this module; no image
datablocks are created. Raw preview arrays are never used for export: exports always capture
again at export resolution.
"""
import time

import bpy
import numpy as np

from . import encode, viewport
from .i18n import iface

DEBOUNCE = 0.2          # seconds of stillness (no view change, no depsgraph update) before an auto refresh
TICK = 0.1
SLOW_CAPTURE = 0.25     # back off when a preview capture is slower than this
MAX_SETTLE = 1.0        # upper bound of the stillness wait for slow scenes
PASSES = ('depth', 'normal', 'object_id', 'mask')
LABELS = {'depth': 'Depth', 'normal': 'Normal', 'object_id': 'Object ID', 'mask': 'Mask'}
THUMB_TEXTURE_HEIGHT = 128   # thumbnails are sampled down to about this many rows before encoding
THUMB_HEIGHT = 56            # drawn height in UI units (scaled by the UI scale)
STALE_DIM = 0.35             # opacity factor of an outdated preview


class _State:
    def __init__(self):
        self.reset()

    def reset(self):
        self.pointers = None       # (window, area, region) pointers of the source view
        self.raw = None            # last preview capture result
        self.small = None          # the same passes sampled down for the thumbnails
        self.texture = None        # large overlay of settings.preview_pass (only while overlay is on)
        self.thumbs = {}           # pass -> thumbnail texture
        self.overlay = False       # large overlay shown
        self.size = (0, 0)
        self.signature = None
        self.capture_modes = None  # (normal_mode, id_mode) used for raw
        self.dirty = False
        self.change_time = None    # last time the view or the scene was seen changing
        self.pending_signature = None
        self.busy = False
        self.error = ''
        self.message = ''
        self.warnings = []
        self.last_seconds = 0.0
        self.stale = False
        self.windows = frozenset()

    @property
    def active(self):
        return self.pointers is not None


state = _State()
_draw_handle = None
_shader = None
_batch = None


def _image_shader():
    """Draws a texture into a rectangle given in normalized device coordinates (push constant)."""
    global _shader, _batch
    if _shader is None:
        import gpu
        from gpu_extras.batch import batch_for_shader
        iface_ = gpu.types.GPUStageInterfaceInfo('viewprism_preview_iface')
        iface_.smooth('VEC2', 'v_uv')
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant('VEC4', 'rect')
        info.push_constant('FLOAT', 'opacity')
        info.push_constant('FLOAT', 'gain')
        info.sampler(0, 'FLOAT_2D', 'image')
        info.vertex_in(0, 'VEC2', 'uv')
        info.vertex_out(iface_)
        info.fragment_out(0, 'VEC4', 'color')
        info.vertex_source('void main() { v_uv = uv; gl_Position = vec4(mix(rect.xy, rect.zw, uv), 0.0, 1.0); }')
        info.fragment_source('void main() { color = vec4(texture(image, v_uv).rgb * gain, opacity); }')
        _shader = gpu.shader.create_from_info(info)
        _batch = batch_for_shader(_shader, 'TRI_FAN', {'uv': ((0, 0), (1, 0), (1, 1), (0, 1))})
    return _shader, _batch


def display_image(result, pass_name, settings):
    """RGB float32 (H,W,3), top-left rows, for display only."""
    mask = result['mask']
    if pass_name == 'depth':
        bg = settings.depth_background
        bg = settings.depth_background_value if bg == 'VALUE' else bg
        img, _info = encode.normalize_depth(result['depth'], mask, settings.depth_range, settings.depth_near,
                                            settings.depth_far, settings.depth_near_white, bg)
        return np.repeat(img[..., None], 3, axis=-1)
    if pass_name == 'normal':
        bg = (0.5, 0.5, 1.0) if settings.normal_background == 'FLAT' else (0.0, 0.0, 0.0)
        sign = np.array([-1 if settings.normal_flip_x else 1, -1 if settings.normal_flip_y else 1, 1], np.float32)
        return encode.normal_to_rgb(result['normal'] * sign, mask, bg)
    if pass_name == 'object_id':
        return encode.id_colors(result['object_id'], mask).astype(np.float32)
    return np.repeat(mask.astype(np.float32)[..., None], 3, axis=-1)


def downsample(result, rows=THUMB_TEXTURE_HEIGHT):
    """Every n-th pixel of each pass (nearest neighbour keeps IDs and masks exact)."""
    h = result['mask'].shape[0]
    step = max(1, h // rows)
    return {p: result[p][::step, ::step] for p in PASSES}


def _upload(rgb):
    import gpu
    h, w = rgb.shape[:2]
    rgba = np.ascontiguousarray(encode.to_rgba(rgb)[::-1], dtype=np.float32)   # GPU rows start at bottom
    buf = gpu.types.Buffer('FLOAT', h * w * 4, rgba.ravel())
    return gpu.types.GPUTexture((w, h), format='RGBA8', data=buf)


def _encoded(result, pass_name, settings):
    try:
        return display_image(result, pass_name, settings)
    except encode.EncodeError as exc:
        state.error = str(exc)
        return np.zeros(result['mask'].shape + (3,), np.float32)


def _rebuild_texture(settings, overlay=True, thumbnails=True):
    """Re-encode the cached capture for the current display settings (no new capture). Only the
    parts asked for are rebuilt (the eye button changes the overlay, not the thumbnails)."""
    if state.raw is None:
        state.texture, state.thumbs = None, {}
        return
    state.error = ''
    if overlay:
        if state.overlay:
            state.texture = _upload(_encoded(state.raw, settings.preview_pass, settings))
            if hasattr(state.texture, 'filter_mode'):      # Blender 5.x; cosmetic only
                state.texture.filter_mode(settings.preview_pass in ('depth', 'normal'))
        else:
            state.texture = None
    if thumbnails:
        if settings.preview_thumbnails and state.small is not None:
            state.thumbs = {p: _upload(_encoded(state.small, p, settings)) for p in PASSES}
        else:
            state.thumbs = {}


def modes_differ(settings):
    """The capture was made with other normal/ID modes: its data no longer matches the settings."""
    return state.capture_modes is not None and state.capture_modes != (settings.normal_mode, settings.id_mode)


def _tag_redraw():
    if not state.active:
        return
    try:
        viewport.find(state.pointers).area.tag_redraw()
    except viewport.ViewError:
        pass


def refresh(context, view):
    """Capture at preview resolution for `view` and show it. A new preview starts with the large
    overlay of settings.preview_pass; an existing one keeps its overlay state."""
    from . import capture as cap
    from . import props
    settings = props.settings(context)
    starting = not is_showing(view.area)
    state.busy = True
    try:
        request, _src = viewport.build_request(view, context.scene, context.evaluated_depsgraph_get(),
                                               settings, PASSES, preview=True)
        with context.temp_override(**view.override()):
            result = cap.capture(bpy.context, request)
    finally:
        state.busy = False
    if starting:
        state.overlay = True
    state.pointers = view.pointers()
    state.raw = result
    state.small = downsample(result)
    state.size = (request['width'], request['height'])
    state.signature = viewport.view_signature(view)
    state.capture_modes = (settings.normal_mode, settings.id_mode)
    state.dirty = False
    state.change_time = None
    state.pending_signature = None
    state.stale = False
    state.last_seconds = result['stats']['seconds']['total']
    state.warnings = list(result['warnings'])
    state.message = iface('{} × {} px, {:.0f} ms').format(request['width'], request['height'],
                                                         state.last_seconds * 1000)
    _rebuild_texture(settings)
    _ensure_draw_handler()
    _ensure_timer()
    view.area.tag_redraw()
    return result


def show_pass(context, view, pass_name):
    """The eye button of a pass: show it large; the same button again hides the large overlay
    (the thumbnails stay). Starts a preview first if this view has none."""
    from . import props
    settings = props.settings(context)
    if not is_showing(view.area):
        settings.preview_pass = pass_name
        refresh(context, view)
        return
    if state.overlay and settings.preview_pass == pass_name:
        state.overlay = False
        if not settings.preview_thumbnails:
            clear()                         # nothing left to show: stop the preview entirely
            return
        _rebuild_texture(settings, thumbnails=False)
    elif settings.preview_pass != pass_name:
        state.overlay = True
        settings.preview_pass = pass_name   # its update re-encodes the overlay
    else:
        state.overlay = True
        _rebuild_texture(settings, thumbnails=False)
    _tag_redraw()


def overlay_pass(area):
    """The pass shown large in `area`, or None."""
    from . import props
    if not (is_showing(area) and state.overlay):
        return None
    return props.settings(bpy.context).preview_pass


def clear():
    was = state.active
    ptrs = state.pointers
    state.reset()
    if was:
        try:
            viewport.find(ptrs).area.tag_redraw()
        except Exception:
            pass


def settings_changed(context, which='display'):
    """Called by property updates.

    which='display': display settings changed (pass shown, depth range, colours, thumbnails): re-encode
    the cached capture; no new capture. A preview with neither overlay nor thumbnails stops.
    which='repaint': only drawing changes (opacity, which passes are exported, Auto Refresh).
    which='capture': the preview resolution changed: capture again (at once with Auto Refresh,
    otherwise on the next Refresh).
    """
    if not state.active:
        return
    from . import props
    settings = props.settings(context)
    if which == 'display':
        if not state.overlay and not settings.preview_thumbnails:
            clear()
            return
        _rebuild_texture(settings)
    elif which == 'capture':
        state.dirty = True
    if settings.preview_auto:
        _ensure_timer()
    _tag_redraw()


def is_showing(area):
    return state.active and area is not None and state.pointers[1] == area.as_pointer()


# ----------------------------------------------------------------------------- drawing

def _ndc(x, y, w, h, rw, rh):
    return (2 * x / rw - 1, 2 * y / rh - 1, 2 * (x + w) / rw - 1, 2 * (y + h) / rh - 1)


def _draw_image(texture, rect_ndc, opacity, gain=1.0):
    shader, batch = _image_shader()
    shader.bind()
    shader.uniform_float('rect', rect_ndc)
    shader.uniform_float('opacity', opacity)
    shader.uniform_float('gain', gain)
    shader.uniform_sampler('image', texture)
    batch.draw(shader)


def _top_inset(ctx):
    """Height of header regions that float over the top of the viewport (transparent headers)."""
    region = ctx.region
    top = region.y + region.height
    inset = 0
    for r in ctx.area.regions:          # header and tool header, stacked at the top edge
        if r.type in {'HEADER', 'TOOL_HEADER'} and r.height > 1 and region.y < r.y < top and top - r.y < 200:
            inset = max(inset, top - r.y)
    return inset


def _rect(x, y, w, h, rw, rh, color):
    """Filled rectangle in region pixels (converted to NDC; no gpu.matrix state is assumed)."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    from mathutils import Matrix
    x0, y0, x1, y1 = _ndc(x, y, w, h, rw, rh)
    sh = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(sh, 'TRI_FAN', {'pos': ((x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0))})
    with gpu.matrix.push_pop():
        gpu.matrix.load_identity()
        with gpu.matrix.push_pop_projection():
            gpu.matrix.load_projection_matrix(Matrix.Identity(4))
            sh.uniform_float('color', color)
            batch.draw(sh)


def _side_insets(ctx):
    """(left, right) widths of the toolbar and the sidebar when they float over the viewport."""
    if not ctx.preferences.system.use_region_overlap:
        return 0, 0
    space = ctx.area.spaces.active

    def width(kind, shown):
        r = next((r for r in ctx.area.regions if r.type == kind), None)
        return r.width if shown and r is not None and r.width > 1 else 0
    return (width('TOOLS', getattr(space, 'show_region_toolbar', False)),
            width('UI', getattr(space, 'show_region_ui', False)))


def thumbnail_layout(region_w, region_h, image_w, image_h, ui, left=0, right=0):
    """Pixel rectangles (x, y, w, h) of the four thumbnail images, lower left, between the toolbar
    (left) and the sidebar (ight), keeping the image aspect; [] if they do not fit."""
    margin, gap, label_h = 10 * ui, 6 * ui, 18 * ui
    aspect = image_w / max(1, image_h)
    th = THUMB_HEIGHT * ui
    tw = th * aspect
    if tw > 2.2 * th:                               # very wide views: limit the width, keep the aspect
        tw = 2.2 * th
        th = tw / aspect
    room = region_w - left - right - 2 * margin
    if 4 * tw + 3 * gap > room:                     # shrink to the available width
        tw = max(0.0, (room - 3 * gap) / 4)
        th = tw / aspect
    if tw < 12 * ui or th < 12 * ui or th + label_h + 2 * margin > region_h:
        return []
    return [(left + margin + i * (tw + gap), margin + label_h, tw, th) for i in range(4)]


def _draw():
    if not state.active:
        return
    ctx = bpy.context
    if ctx.area is None or ctx.region is None:
        return
    if ctx.area.as_pointer() != state.pointers[1] or ctx.region.as_pointer() != state.pointers[2]:
        return
    import blf
    import gpu
    from . import props
    settings = props.settings(ctx)
    rw, rh = ctx.region.width, ctx.region.height
    ui = ctx.preferences.system.ui_scale
    sig_now = viewport.signature_of(ctx.region_data, ctx.region, ctx.space_data)
    stale = state.stale or sig_now != state.signature or modes_differ(settings)
    left, right = _side_insets(ctx)
    gain = STALE_DIM if stale else 1.0                  # an outdated preview is drawn darker
    prev_blend = gpu.state.blend_get()
    try:
        gpu.state.blend_set('ALPHA')
        if state.overlay and state.texture is not None:
            _draw_image(state.texture, (-1.0, -1.0, 1.0, 1.0), settings.preview_opacity, gain)
        if state.thumbs:
            _draw_thumbnails(ctx, settings, rw, rh, ui, gain, left, right)
        if stale:
            text = iface('Preview updating…') if settings.preview_auto else \
                iface('Preview outdated: click Refresh or turn on Auto Refresh')
        elif state.overlay:
            text = iface('Preview: {} (display only)').format(iface(LABELS[settings.preview_pass]))
        else:
            text = ''
        if text:
            font = 0
            blf.size(font, 13 * ui)
            tw, th = blf.dimensions(font, text)
            x, y = left + (rw - left - right - tw) / 2, rh - _top_inset(ctx) - th - 14 * ui
            _rect(x - 8 * ui, y - 6 * ui, tw + 16 * ui, th + 12 * ui, rw, rh, (0.0, 0.0, 0.0, 0.65))
            blf.color(font, 1.0, 0.82 if stale else 1.0, 0.25 if stale else 1.0, 1.0)
            blf.position(font, x, y, 0)
            blf.draw(font, text)
    finally:
        gpu.state.blend_set(prev_blend)


def _draw_thumbnails(ctx, settings, rw, rh, ui, gain, left, right):
    import blf
    w, h = state.size
    rects = thumbnail_layout(rw, rh, w, h, ui, left, right)
    shown = settings.preview_pass if state.overlay else None
    exported = {'depth': settings.use_depth, 'normal': settings.use_normal,
                'object_id': settings.use_object_id, 'mask': settings.use_mask}
    font = 0
    blf.size(font, 11 * ui)
    for p, (x, y, tw, th) in zip(PASSES, rects):
        pad = 2 * ui
        frame = (0.96, 0.76, 0.31, 0.95) if p == shown else (0.0, 0.0, 0.0, 0.6)
        _rect(x - pad, y - 18 * ui, tw + 2 * pad, th + 18 * ui + pad, rw, rh, frame)
        tex = state.thumbs.get(p)
        if tex is not None:
            _draw_image(tex, _ndc(x, y, tw, th, rw, rh), 1.0, gain)
        label = iface(LABELS[p])
        lw, _lh = blf.dimensions(font, label)
        if lw > tw - 6 * ui:                        # very narrow thumbnails: shorten the label
            label = label[:max(1, int(len(label) * (tw - 6 * ui) / lw))]
        on = exported[p]
        if p == shown:
            blf.color(font, 0.1, 0.1, 0.1, 1.0)
        else:
            blf.color(font, 1.0, 1.0, 1.0, 1.0 if on else 0.55)
        blf.position(font, x + 4 * ui, y - 13 * ui, 0)
        blf.draw(font, label)


def _ensure_draw_handler():
    global _draw_handle
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')


# ----------------------------------------------------------------------------- auto refresh

def _ensure_timer():
    # Blender allows registering the same function twice (two timers), so ask Blender.
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=TICK)


def _tick():
    if not state.active:
        return None
    try:
        view = viewport.find(state.pointers)
    except viewport.ViewError:
        clear()                     # the source view was closed: release everything
        return None
    from . import props
    ctx = bpy.context
    settings = props.settings(ctx)
    if not settings.preview_auto:
        return 0.5                  # keep watching for a closed view so resources are released
    # A window was opened/closed since the last tick: Blender may have no current GPU context
    # until it redraws (on 4.5 GPU calls without a context can crash), so wait one tick.
    windows = frozenset(w.as_pointer() for w in ctx.window_manager.windows)
    if windows != state.windows:
        state.windows = windows
        return TICK
    now = time.monotonic()
    signature = viewport.view_signature(view)
    if not (state.dirty or signature != state.signature or modes_differ(settings)):
        state.change_time = state.pending_signature = None
        return TICK
    # Refresh only once the view has been still for DEBOUNCE seconds (longer for slow scenes), so
    # navigating or dragging never triggers blocking captures. Depsgraph updates move change_time too.
    if signature != state.pending_signature or state.change_time is None:
        state.pending_signature = signature
        state.change_time = now
        return TICK
    if now - state.change_time < min(MAX_SETTLE, max(DEBOUNCE, state.last_seconds)):
        return TICK
    from .capture import GPUContextError
    try:
        with ctx.temp_override(**view.override()):
            refresh(bpy.context, view)
    except GPUContextError:
        return 0.5                  # transient (e.g. a window was just closed): retry later
    except Exception as exc:  # never leave a broken timer running
        settings.preview_auto = False
        state.error = iface('Auto Refresh stopped: {}').format(exc)
        _tag_redraw()
        return 0.5
    return max(TICK, min(1.0, state.last_seconds * 4)) if state.last_seconds > SLOW_CAPTURE else TICK


@bpy.app.handlers.persistent
def _on_depsgraph_update(_scene, depsgraph):
    # Changing an add-on setting (a WindowManager property) also fires this handler, with no updated
    # datablocks: that does not change the scene, so the preview stays current.
    updates = getattr(depsgraph, 'updates', None)
    if updates is not None and len(updates) == 0:
        return
    if state.active and not state.busy:
        state.dirty = True
        state.stale = True
        state.change_time = time.monotonic()      # still editing: restart the stillness wait


@bpy.app.handlers.persistent
def _on_load_pre(*_args):
    clear()


def register():
    bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)
    bpy.app.handlers.load_pre.append(_on_load_pre)


def unregister():
    global _draw_handle, _shader, _batch
    for lst, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph_update),
                    (bpy.app.handlers.load_pre, _on_load_pre)):
        while fn in lst:
            lst.remove(fn)
    while bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        _draw_handle = None
    state.reset()
    _shader = None
    _batch = None
