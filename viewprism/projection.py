"""Pure projection math (NumPy only, no bpy) shared by the capture core and the UI.

Conventions
-----------
* Matrices are 4x4, row-major, column-vector convention (``clip = P @ V @ p``),
  OpenGL style: the camera looks down -Z in view space and NDC z is in [-1, 1].
* Image rows are top-left first. Pixel ``(row, col)`` covers NDC
  ``x in [2*col/W - 1, 2*(col+1)/W - 1]`` and ``y in [1 - 2*(row+1)/H, 1 - 2*row/H]``;
  samples are taken at pixel centres (+0.5).
"""
import math

import numpy as np

PERSPECTIVE = 'PERSPECTIVE'
ORTHOGRAPHIC = 'ORTHOGRAPHIC'
GENERIC = 'GENERIC'

# Depth-buffer mapping modes used by the GPU pass (see docs/decisions/0001-renderer.md).
DEPTH_LINEAR = 0       # gl_FragDepth = (d - near) / (far - near)        (orthographic)
DEPTH_LOG = 1          # gl_FragDepth = log(d / near) / log(far / near)  (perspective)
DEPTH_HARDWARE = 2     # gl_FragDepth = gl_FragCoord.z                   (anything else)

_EPS = 1e-12


class ProjectionError(ValueError):
    pass


def as_matrix(value, name='matrix'):
    """Convert a nested sequence / array / mathutils.Matrix to a finite float64 4x4 array."""
    try:
        if hasattr(value, 'col') and hasattr(value, 'row'):  # mathutils.Matrix
            value = [list(r) for r in value]
        m = np.array(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ProjectionError(f'{name} must be a 4x4 numeric matrix') from exc
    if m.shape != (4, 4):
        raise ProjectionError(f'{name} must be 4x4, got shape {m.shape}')
    if not np.isfinite(m).all():
        raise ProjectionError(f'{name} contains non-finite values')
    return m


def is_affine(m, tol=1e-9):
    return np.allclose(m[3], (0.0, 0.0, 0.0, 1.0), atol=tol, rtol=0.0)


def classify(p, tol=1e-9):
    """Return PERSPECTIVE, ORTHOGRAPHIC or GENERIC for an OpenGL-style projection matrix."""
    row = p[3]
    scale = max(1.0, float(np.abs(p).max()))
    t = tol * scale
    if abs(row[0]) < t and abs(row[1]) < t and abs(row[2] + 1.0) < t and abs(row[3]) < t:
        return PERSPECTIVE
    if abs(row[0]) < t and abs(row[1]) < t and abs(row[2]) < t and abs(row[3] - 1.0) < t:
        return ORTHOGRAPHIC
    return GENERIC


def clip_range(p):
    """Return (kind, near, far) as positive-forward distances along -Z in view space.

    For GENERIC matrices near/far are None. ``far`` may be ``inf`` for an
    infinite perspective projection.
    """
    kind = classify(p)
    a, b = float(p[2, 2]), float(p[2, 3])
    if kind == PERSPECTIVE:
        if abs(a - 1.0) < _EPS:
            raise ProjectionError('degenerate perspective projection (near undefined)')
        near = b / (a - 1.0)
        far = math.inf if abs(a + 1.0) < _EPS else b / (a + 1.0)
        if not (near > 0.0) or not (far > near):
            raise ProjectionError(f'invalid perspective clip range near={near} far={far}')
        return kind, near, far
    if kind == ORTHOGRAPHIC:
        if abs(a) < _EPS:
            raise ProjectionError('degenerate orthographic projection (zero depth scale)')
        near = (b + 1.0) / a
        far = (b - 1.0) / a
        if not (far > near):
            raise ProjectionError(f'invalid orthographic clip range near={near} far={far}')
        return kind, near, far
    return kind, None, None


def depth_mapping(p):
    """Parameters for the GPU visibility depth: (mode, near, scale).

    Visibility uses a remapped depth buffer instead of the hyperbolic hardware depth
    so that surfaces millimetres apart stay ordered at the default viewport clip
    range (0.01 .. 1000). The *output* depth value is always the exact
    interpolated -Z, independent of this mapping.
    """
    kind, near, far = clip_range(p)
    if kind == PERSPECTIVE:
        if not math.isfinite(far):
            far = near * 1e12
        return DEPTH_LOG, near, 1.0 / math.log(far / near)
    if kind == ORTHOGRAPHIC:
        return DEPTH_LINEAR, near, 1.0 / (far - near)
    return DEPTH_HARDWARE, 0.0, 1.0


def validate_projection(p):
    if abs(np.linalg.det(p)) < 1e-300 or not np.isfinite(np.linalg.cond(p)):
        raise ProjectionError('projection matrix is singular')
    clip_range(p)  # raises for invalid persp/ortho ranges


def crop_to_aspect(p, src_aspect, dst_aspect):
    """Centred crop of the image described by ``p`` (aspect W/H ``src_aspect``) to ``dst_aspect``.

    Cropping a centred sub-rectangle of the screen is a pure scale of NDC x or y,
    so this works for perspective, orthographic and shifted projections alike and
    never shows anything outside the source view.
    """
    if not (src_aspect > 0 and dst_aspect > 0):
        raise ProjectionError('aspect ratios must be positive')
    s = np.eye(4)
    if dst_aspect < src_aspect:
        s[0, 0] = src_aspect / dst_aspect
    else:
        s[1, 1] = dst_aspect / src_aspect
    return s @ p


def shift_ortho_origin_to_near(view, p):
    """For orthographic views whose near plane lies behind the eye (Blender's viewport
    uses near = -clip_end/2), move the view origin onto the near plane so that every
    visible depth is positive. Returns (view', p', shift) with shift = distance moved
    (0 when no change is needed). Geometry and pixels are unchanged; only the depth
    origin moves (recorded in metadata).
    """
    kind, near, _far = clip_range(p)
    if kind != ORTHOGRAPHIC or near >= 0.0:
        return view, p, 0.0
    # View-space z' = z + near  (near < 0): the near plane z = -near maps to z' = 0.
    t = np.eye(4)
    t[2, 3] = near
    t_inv = np.eye(4)
    t_inv[2, 3] = -near
    return t @ view, p @ t_inv, -near


def project(p, view, points, width, height):
    """Project world points (N,3) -> (col_float, row_float, view_depth, ndc_z).

    Column/row are continuous pixel coordinates (pixel centres at +0.5),
    top-left origin. Used by tests and overlays; the GPU does its own projection.
    """
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    hom = np.concatenate([pts, np.ones((len(pts), 1))], axis=1)
    vpos = hom @ view.T
    clip = vpos @ p.T
    ndc = clip[:, :3] / clip[:, 3:4]
    col = (ndc[:, 0] + 1.0) * 0.5 * width
    row = (1.0 - ndc[:, 1]) * 0.5 * height
    return col, row, -vpos[:, 2], ndc[:, 2]


def perspective(fov_y, aspect, near, far):
    """Symmetric OpenGL perspective matrix (helper for tests/tools)."""
    f = 1.0 / math.tan(fov_y / 2.0)
    return np.array([[f / aspect, 0, 0, 0], [0, f, 0, 0],
                     [0, 0, -(far + near) / (far - near), -2 * far * near / (far - near)],
                     [0, 0, -1, 0]], dtype=np.float64)


def orthographic(half_height, aspect, near, far):
    """Symmetric OpenGL orthographic matrix (helper for tests/tools)."""
    hw = half_height * aspect
    return np.array([[1 / hw, 0, 0, 0], [0, 1 / half_height, 0, 0],
                     [0, 0, -2 / (far - near), -(far + near) / (far - near)],
                     [0, 0, 0, 1]], dtype=np.float64)


def locked_height(width, src_width, src_height):
    """Height that keeps the source aspect for a given width (at least 1)."""
    return max(1, int(round(width * src_height / float(src_width))))
