"""Display-only preview overlay in the 3D viewport the capture came from.

The preview is drawn by a POST_PIXEL handler from a GPU texture owned by this module;
no image datablocks are created. Raw preview arrays are never used for export: exports
always capture again at export resolution.
"""
import time

import bpy
import numpy as np

from . import encode, viewport

DEBOUNCE = 0.2          # seconds of stillness before an auto refresh
TICK = 0.1
SLOW_CAPTURE = 0.25     # back off when a preview capture is slower than this


class _State:
    def __init__(self):
        self.reset()

    def reset(self):
        self.pointers = None       # (window, area, region) pointers of the source view
        self.raw = None            # last preview capture result
        self.texture = None
        self.size = (0, 0)
        self.signature = None
        self.capture_modes = None  # (normal_mode, id_mode) used for raw
        self.dirty = False
        self.change_time = None
        self.busy = False
        self.error = ''
        self.message = ''
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
    global _shader, _batch
    if _shader is None:
        import gpu
        from gpu_extras.batch import batch_for_shader
        iface = gpu.types.GPUStageInterfaceInfo('viewprism_preview_iface')
        iface.smooth('VEC2', 'v_uv')
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant('FLOAT', 'opacity')
        info.sampler(0, 'FLOAT_2D', 'image')
        info.vertex_in(0, 'VEC2', 'pos')
        info.vertex_in(1, 'VEC2', 'uv')
        info.vertex_out(iface)
        info.fragment_out(0, 'VEC4', 'color')
        info.vertex_source('void main() { v_uv = uv; gl_Position = vec4(pos, 0.0, 1.0); }')
        info.fragment_source('void main() { color = vec4(texture(image, v_uv).rgb, opacity); }')
        _shader = gpu.shader.create_from_info(info)
        _batch = batch_for_shader(_shader, 'TRI_FAN', {
            'pos': ((-1, -1), (1, -1), (1, 1), (-1, 1)), 'uv': ((0, 0), (1, 0), (1, 1), (0, 1))})
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


def _upload(rgb):
    import gpu
    h, w = rgb.shape[:2]
    rgba = np.ascontiguousarray(encode.to_rgba(rgb)[::-1], dtype=np.float32)   # GPU rows start at bottom
    buf = gpu.types.Buffer('FLOAT', h * w * 4, rgba.ravel())
    return gpu.types.GPUTexture((w, h), format='RGBA8', data=buf)


def _rebuild_texture(settings):
    if state.raw is None:
        state.texture = None
        return
    try:
        rgb = display_image(state.raw, settings.preview_pass, settings)
        state.error = ''
    except encode.EncodeError as exc:
        state.error = str(exc)
        rgb = np.zeros(state.raw['mask'].shape + (3,), np.float32)
    state.texture = _upload(rgb)
    if hasattr(state.texture, 'filter_mode'):      # Blender 5.x; cosmetic only
        state.texture.filter_mode(settings.preview_pass in ('depth', 'normal'))


def _tag_redraw():
    if not state.active:
        return
    try:
        viewport.find(state.pointers).area.tag_redraw()
    except viewport.ViewError:
        pass


def refresh(context, view):
    """Capture at preview resolution for `view` and show it."""
    from . import capture as cap
    from . import props
    settings = props.settings(context)
    state.busy = True
    try:
        request, _src = viewport.build_request(view, context.scene, context.evaluated_depsgraph_get(),
                                               settings, ('depth', 'normal', 'object_id', 'mask'), preview=True)
        with context.temp_override(**view.override()):
            result = cap.capture(bpy.context, request)
    finally:
        state.busy = False
    state.pointers = view.pointers()
    state.raw = result
    state.size = (request['width'], request['height'])
    state.signature = viewport.view_signature(view)
    state.capture_modes = (settings.normal_mode, settings.id_mode)
    state.dirty = False
    state.change_time = None
    state.stale = False
    state.last_seconds = result['stats']['seconds']['total']
    n_warn = len(result['warnings'])
    state.message = (f"Preview {request['width']}x{request['height']}, {state.last_seconds * 1000:.0f} ms"
                     + (f", {n_warn} warning(s)" if n_warn else ''))
    _rebuild_texture(settings)
    _ensure_draw_handler()
    _ensure_timer()
    view.area.tag_redraw()
    return result


def clear():
    was = state.active
    ptrs = state.pointers
    state.reset()
    if was:
        try:
            viewport.find(ptrs).area.tag_redraw()
        except Exception:
            pass


def settings_changed(context):
    """Called by property updates: re-encode the cached preview (no capture) or mark dirty."""
    if not state.active:
        return
    from . import props
    settings = props.settings(context)
    if state.capture_modes != (settings.normal_mode, settings.id_mode):
        state.dirty = True
        state.stale = True
    else:
        _rebuild_texture(settings)
    if settings.preview_auto:
        _ensure_timer()
    _tag_redraw()


def is_showing(area):
    return state.active and area is not None and state.pointers[1] == area.as_pointer()


# ----------------------------------------------------------------------------- drawing

def _draw():
    if not state.active or state.texture is None:
        return
    ctx = bpy.context
    if ctx.area is None or ctx.region is None:
        return
    if ctx.area.as_pointer() != state.pointers[1] or ctx.region.as_pointer() != state.pointers[2]:
        return
    import gpu
    from . import props
    settings = props.settings(ctx)
    shader, batch = _image_shader()
    prev_blend = gpu.state.blend_get()
    try:
        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float('opacity', settings.preview_opacity)
        shader.uniform_sampler('image', state.texture)
        batch.draw(shader)
    finally:
        gpu.state.blend_set(prev_blend)
    sig_now = (tuple(round(x, 7) for row in ctx.region_data.view_matrix for x in row),
               tuple(round(x, 7) for row in ctx.region_data.window_matrix for x in row),
               ctx.region.width, ctx.region.height, ctx.region_data.view_perspective)
    stale = state.stale or sig_now != state.signature
    import blf
    font = 0
    blf.size(font, 12 * ctx.preferences.system.ui_scale)
    label = f'ViewPrism preview ({settings.preview_pass}) - display only'
    if stale:
        label += ' - OUTDATED, press Refresh' if not settings.preview_auto else ' - updating...'
    ui = ctx.preferences.system.ui_scale
    tw, th = blf.dimensions(font, label)
    _backdrop(8 * ui, 8 * ui, tw + 8 * ui, th + 8 * ui, ctx.region.width, ctx.region.height)
    blf.color(font, 1.0, 0.85 if stale else 1.0, 0.2 if stale else 1.0, 1.0)
    blf.position(font, 12 * ui, 12 * ui, 0)
    blf.draw(font, label)


def _backdrop(x, y, w, h, rw, rh):
    """Dark translucent box behind the overlay label (pixel coords -> NDC, no gpu.matrix use)."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    from mathutils import Matrix
    x0, y0 = 2 * x / rw - 1, 2 * y / rh - 1
    x1, y1 = 2 * (x + w) / rw - 1, 2 * (y + h) / rh - 1
    sh = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(sh, 'TRI_FAN', {'pos': ((x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0))})
    prev = gpu.state.blend_get()
    gpu.state.blend_set('ALPHA')
    with gpu.matrix.push_pop():
        gpu.matrix.load_identity()
        with gpu.matrix.push_pop_projection():
            gpu.matrix.load_projection_matrix(Matrix.Identity(4))
            sh.uniform_float('color', (0.0, 0.0, 0.0, 0.6))
            batch.draw(sh)
    gpu.state.blend_set(prev)


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
    changed = state.dirty or viewport.view_signature(view) != state.signature
    if not changed:
        state.change_time = None
        return TICK
    if state.change_time is None:
        state.change_time = now
        return TICK
    if now - state.change_time < DEBOUNCE:
        return TICK
    from .capture import GPUContextError
    try:
        with ctx.temp_override(**view.override()):
            refresh(bpy.context, view)
    except GPUContextError:
        return 0.5                  # transient (e.g. a window was just closed): retry later
    except Exception as exc:  # never leave a broken timer running
        settings.preview_auto = False
        state.error = f'Auto refresh stopped: {exc}'
        _tag_redraw()
        return 0.5
    return max(TICK, min(1.0, state.last_seconds * 4)) if state.last_seconds > SLOW_CAPTURE else TICK


@bpy.app.handlers.persistent
def _on_depsgraph_update(_scene, _depsgraph):
    if state.active and not state.busy:
        state.dirty = True
        state.stale = True


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
