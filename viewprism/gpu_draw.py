# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Single geometry pass on the GPU (Blender ``gpu`` module only; no bgl, no raw OpenGL).

One draw of every item into two RGBA32F colour targets plus a DEPTH_COMPONENT32F
depth target (multiple render targets). Because depth, normal, ID and coverage are
written by the same fragment, the passes are pixel-aligned by construction.

* target 0: (nx, ny, nz, -z_view)       camera-space unit normal and planar depth
* target 1: (object_id, coverage, 0, 0)  id as float (exact up to 2**24)

Visibility uses a remapped depth (log for perspective, linear for orthographic) written
to gl_FragDepth; see projection.depth_mapping. All push constants fit in 128 bytes.
"""
import numpy as np

_shader = None
_shader_error = None
_targets = None             # reused render targets: (size, fb, tex_geom, tex_id, tex_depth, last_use)
KEEP_MAX_PIXELS = 2_100_000 # keep targets up to ~1080p between captures (avoids GPU allocation churn)
IDLE_RELEASE = 30.0         # seconds without a capture before kept targets are freed

_VERT = """
void main()
{
  vec4 p = vec4(pos, 1.0);
  vec3 vpos = vec3(dot(MVRow0, p), dot(MVRow1, p), dot(MVRow2, p));
  v_view = vpos;
  /* Normal matrix = inverse-transpose of the linear part, via the cofactor matrix.
   * Multiplying by sign(det) keeps outward normals outward for mirrored objects. */
  vec3 c0 = vec3(MVRow0.x, MVRow1.x, MVRow2.x);
  vec3 c1 = vec3(MVRow0.y, MVRow1.y, MVRow2.y);
  vec3 c2 = vec3(MVRow0.z, MVRow1.z, MVRow2.z);
  vec3 x01 = cross(c0, c1);
  vec3 x12 = cross(c1, c2);
  vec3 x20 = cross(c2, c0);
  float det = dot(c0, x12);
  float s = (det < 0.0) ? -1.0 : 1.0;
  v_nor = s * (x12 * nor.x + x20 * nor.y + x01 * nor.z);
  gl_Position = ProjectionMatrix * vec4(vpos, 1.0);
}
"""

_FRAG = """
void main()
{
  float d = -v_view.z;
  vec3 n = v_nor;
  float len2 = dot(n, n);
  n = (len2 > 1e-30) ? n * inversesqrt(len2) : vec3(0.0, 0.0, 1.0);
  float fd;
  if (Params.z < 0.5) {
    fd = (d - Params.x) * Params.y;
  }
  else if (Params.z < 1.5) {
    fd = log(max(d, 1e-37) / Params.x) * Params.y;
  }
  else {
    fd = gl_FragCoord.z;
  }
  gl_FragDepth = clamp(fd, 0.0, 1.0);
  out_geom = vec4(n, d);
  out_id = vec4(Params.w, 1.0, 0.0, 0.0);
}
"""


class GPUCaptureError(RuntimeError):
    pass


def shader():
    """Compile once per session (requires an active GPU context)."""
    global _shader, _shader_error
    if _shader is not None:
        return _shader
    import gpu
    iface = gpu.types.GPUStageInterfaceInfo('viewprism_iface')
    iface.smooth('VEC3', 'v_view')
    iface.smooth('VEC3', 'v_nor')
    info = gpu.types.GPUShaderCreateInfo()
    info.push_constant('VEC4', 'MVRow0')
    info.push_constant('VEC4', 'MVRow1')
    info.push_constant('VEC4', 'MVRow2')
    info.push_constant('MAT4', 'ProjectionMatrix')
    info.push_constant('VEC4', 'Params')        # (depth_near, depth_scale, depth_mode, object_id)
    info.vertex_in(0, 'VEC3', 'pos')
    info.vertex_in(1, 'VEC3', 'nor')
    info.vertex_out(iface)
    info.fragment_out(0, 'VEC4', 'out_geom')
    info.fragment_out(1, 'VEC4', 'out_id')
    info.depth_write('ANY')
    info.vertex_source(_VERT)
    info.fragment_source(_FRAG)
    try:
        _shader = gpu.shader.create_from_info(info)
    except Exception as exc:
        _shader_error = str(exc)
        raise GPUCaptureError(f'shader compilation failed: {exc}') from exc
    return _shader


def release_targets():
    global _targets
    _targets = None
    try:
        import bpy
        while bpy.app.timers.is_registered(_idle_release):
            bpy.app.timers.unregister(_idle_release)
    except ImportError:
        pass


def _idle_release():
    import time
    if _targets is None:
        return None
    left = IDLE_RELEASE - (time.monotonic() - _targets[5])
    if left > 0:
        return left
    release_targets()
    return None


def _get_targets(width, height):
    """Textures are reused between same-size captures; the framebuffer is not.

    OpenGL framebuffer objects belong to the GL context they were created in (one per window), so a
    cached framebuffer must never outlive or cross contexts (Blender 4.5 crashed after the window
    that created it was closed). Textures are shared between contexts, so only they are cached and a
    small framebuffer is created and freed within each capture.
    """
    import time
    import gpu
    global _targets
    if _targets is not None and _targets[0] == (width, height):
        _targets = _targets[:5] + (time.monotonic(),)
        tex_geom, tex_id, tex_depth = _targets[2:5]
    else:
        _targets = None
        tex_geom = gpu.types.GPUTexture((width, height), format='RGBA32F')
        tex_id = gpu.types.GPUTexture((width, height), format='RGBA32F')
        tex_depth = gpu.types.GPUTexture((width, height), format='DEPTH_COMPONENT32F')
        if width * height <= KEEP_MAX_PIXELS:
            import bpy
            _targets = ((width, height), None, tex_geom, tex_id, tex_depth, time.monotonic())
            if not bpy.app.timers.is_registered(_idle_release):
                bpy.app.timers.register(_idle_release, first_interval=IDLE_RELEASE, persistent=True)
    fb = gpu.types.GPUFrameBuffer(depth_slot=tex_depth, color_slots=(tex_geom, tex_id))
    return fb, tex_geom, tex_id, tex_depth


def free_resources():
    global _shader, _shader_error
    release_targets()
    _shader = None
    _shader_error = None


def _as_array(buf):
    """gpu.types.Buffer -> flat float32 array (zero-copy when the buffer is contiguous)."""
    try:
        return np.frombuffer(buf, dtype=np.float32)
    except (BufferError, ValueError, TypeError):
        return np.frombuffer(memoryview(buf).tobytes(), dtype=np.float32)


def make_batches(meshes, sh):
    from gpu_extras.batch import batch_for_shader
    return {k: batch_for_shader(sh, 'TRIS', {'pos': m.pos, 'nor': m.nor}, indices=m.tris)
            for k, m in meshes.items()}


def render(width, height, view, projection, items, batches, depth_params, *, _after_draw=None):
    """Draw and read back. Returns (geom (H,W,4) float32, ident (H,W,4) float32), top-left rows.

    GPU state (depth test/mask, blend, viewport, framebuffer) is restored on success and
    on failure. ``_after_draw`` is a test seam (fault injection) called after drawing.
    """
    import gpu
    from mathutils import Matrix, Vector

    sh = shader()
    mode, dnear, dscale = depth_params
    fb, tex_geom, tex_id, tex_depth = _get_targets(width, height)
    prev_depth_test = gpu.state.depth_test_get()
    prev_depth_mask = gpu.state.depth_mask_get()
    prev_blend = gpu.state.blend_get()
    prev_viewport = gpu.state.viewport_get()
    proj = Matrix(projection.tolist())
    try:
        with fb.bind():
            try:
                fb.clear(color=(0.0, 0.0, 0.0, 0.0), depth=1.0)
                gpu.state.viewport_set(0, 0, width, height)
                gpu.state.depth_test_set('LESS')
                gpu.state.depth_mask_set(True)
                gpu.state.blend_set('NONE')
                gpu.state.face_culling_set('NONE')
                sh.bind()
                sh.uniform_float('ProjectionMatrix', proj)
                for it in items:
                    mv = view @ it.matrix
                    sh.uniform_float('MVRow0', Vector(mv[0].tolist()))
                    sh.uniform_float('MVRow1', Vector(mv[1].tolist()))
                    sh.uniform_float('MVRow2', Vector(mv[2].tolist()))
                    sh.uniform_float('Params', Vector((dnear, dscale, float(mode), float(it.id))))
                    batches[it.mesh_key].draw(sh)
                if _after_draw is not None:
                    _after_draw()
                # Read into flat 1-D buffers: Blender 4.5 exports the default (h, w, 4) Buffer
                # through a non-contiguous buffer protocol, which NumPy cannot view.
                buf_geom = gpu.types.Buffer('FLOAT', width * height * 4)
                buf_id = gpu.types.Buffer('FLOAT', width * height * 4)
                fb.read_color(0, 0, width, height, 4, 0, 'FLOAT', data=buf_geom)
                fb.read_color(0, 0, width, height, 4, 1, 'FLOAT', data=buf_id)
            finally:
                gpu.state.depth_test_set(prev_depth_test)
                gpu.state.depth_mask_set(prev_depth_mask)
                gpu.state.blend_set(prev_blend)
                gpu.state.face_culling_set('NONE')
        # Views (no copy) flipped to top-left row order; the caller builds new output arrays.
        geom = _as_array(buf_geom).reshape(height, width, 4)[::-1]
        ident = _as_array(buf_id).reshape(height, width, 4)[::-1]
        return geom, ident
    except BaseException:
        release_targets()      # never reuse targets after a failure
        raise
    finally:
        gpu.state.viewport_set(*prev_viewport)
        del fb, tex_geom, tex_id, tex_depth
