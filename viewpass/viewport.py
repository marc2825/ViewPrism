"""Derive a capture request from the 3D viewport the user is working in (read-only)."""
import bpy
import numpy as np

from . import projection as proj

PREVIEW_MAX_PIXELS = 2_000_000


class ViewError(RuntimeError):
    pass


class ViewRef:
    """Identifies one window/area/region so it can be found again (e.g. after a file browser)."""
    __slots__ = ('window', 'area', 'region', 'space', 'rv3d', 'quad')

    def __init__(self, window, area, region, space, rv3d, quad=False):
        self.window, self.area, self.region, self.space, self.rv3d, self.quad = window, area, region, space, rv3d, quad

    def pointers(self):
        return (self.window.as_pointer(), self.area.as_pointer(), self.region.as_pointer())

    def override(self):
        return dict(window=self.window, area=self.area, region=self.region, space_data=self.space,
                    screen=self.window.screen)


def _window_regions(area):
    return [r for r in area.regions if r.type == 'WINDOW' and r.width > 0 and r.height > 0]


def resolve(context):
    """The view the operator was invoked from (N-panel button, menu or hotkey over the view)."""
    area = context.area
    if area is None or area.type != 'VIEW_3D':
        raise ViewError('Run ViewPass from a 3D Viewport')
    space = area.spaces.active
    regions = _window_regions(area)
    if not regions:
        raise ViewError('The 3D Viewport has no visible drawing region')
    quad = bool(len(space.region_quadviews))
    region = context.region if (context.region is not None and context.region.type == 'WINDOW') else None
    if region is None:
        # From the sidebar: the main region (in Quad View the unlocked user view).
        region = next((r for r in regions if r.data == space.region_3d), regions[-1])
    if region.data is None:
        raise ViewError('The 3D Viewport region has no view data')
    return ViewRef(context.window, area, region, space, region.data, quad)


def find(pointers):
    """Find a ViewRef again by pointers, or raise ViewError if it no longer exists."""
    win_p, area_p, region_p = pointers
    for window in bpy.context.window_manager.windows:
        if window.as_pointer() != win_p:
            continue
        for area in window.screen.areas:
            if area.as_pointer() != area_p or area.type != 'VIEW_3D':
                continue
            for region in area.regions:
                if region.as_pointer() == region_p and region.type == 'WINDOW' and region.data is not None:
                    space = area.spaces.active
                    return ViewRef(window, area, region, space, region.data, bool(len(space.region_quadviews)))
    raise ViewError('The 3D Viewport used for this export was closed or changed; run the export again')


def _np(m):
    return np.array([list(r) for r in m], dtype=np.float64)


def active_camera(space, scene):
    cam = space.camera if getattr(space, 'use_local_camera', False) else scene.camera
    return cam if cam is not None else space.camera


def uses_camera_frame(view, settings):
    return view.rv3d.view_perspective == 'CAMERA' and settings.camera_frame


def _size(base_w, base_h, settings, preview):
    if preview:
        s = settings.preview_scale / 100.0
        w, h = max(1, round(base_w * s)), max(1, round(base_h * s))
        if w * h > PREVIEW_MAX_PIXELS:
            f = (PREVIEW_MAX_PIXELS / float(w * h)) ** 0.5
            w, h = max(1, int(w * f)), max(1, int(h * f))
        return w, h
    if settings.resolution_mode == 'CUSTOM':
        w = settings.width
        h = proj.locked_height(w, base_w, base_h) if settings.lock_aspect else settings.height
        return w, h
    s = settings.scale / 100.0
    return max(1, round(base_w * s)), max(1, round(base_h * s))


def build_request(view, scene, depsgraph, settings, passes, *, preview=False):
    """Return (request, source_info). The request satisfies the capture contract."""
    region, rv3d, space = view.region, view.rv3d, view.space
    rw, rh = region.width, region.height
    if rw < 1 or rh < 1:
        raise ViewError('The 3D Viewport is too small')
    if not preview and uses_camera_frame(view, settings):
        cam = active_camera(space, scene)
        if cam is None or cam.type != 'CAMERA':
            raise ViewError('Camera view without an active camera')
        r = scene.render
        base_w = max(1, round(r.resolution_x * r.resolution_percentage / 100.0))
        base_h = max(1, round(r.resolution_y * r.resolution_percentage / 100.0))
        pa_x, pa_y = r.pixel_aspect_x, r.pixel_aspect_y
        w, h = _size(base_w, base_h, settings, False)
        cam_eval = cam.evaluated_get(depsgraph)
        if settings.resolution_mode == 'CUSTOM' and not settings.lock_aspect:
            # centred crop of the render frame to the requested pixel aspect
            p_full = _np(cam_eval.calc_matrix_camera(depsgraph, x=base_w, y=base_h, scale_x=pa_x, scale_y=pa_y))
            p = proj.crop_to_aspect(p_full, base_w / base_h, w / h)
        else:
            # identical framing to a render of w x h (including pixel aspect)
            p = _np(cam_eval.calc_matrix_camera(depsgraph, x=w, y=h, scale_x=pa_x, scale_y=pa_y))
        v = _np(cam_eval.matrix_world.normalized().inverted())
        source = dict(kind='camera', camera=cam.name, camera_type=cam.data.type, render_size=[base_w, base_h])
        shift = 0.0
    else:
        w, h = _size(rw, rh, settings, preview)
        p = proj.crop_to_aspect(_np(rv3d.window_matrix), rw / rh, w / h)
        v = _np(rv3d.view_matrix)
        source = dict(kind='viewport', view_perspective=rv3d.view_perspective, region_size=[rw, rh],
                      quad_view=view.quad)
        v, p, shift = proj.shift_ortho_origin_to_near(v, p)
    source['ortho_depth_origin_shift'] = shift
    if shift:
        source['ortho_depth_origin'] = ('view origin moved back onto the near clipping plane '
                                        f'({shift:g} units) so that all depths are positive')
    request = dict(width=int(w), height=int(h), view_matrix=v.tolist(), projection_matrix=p.tolist(),
                   passes=list(passes), normal_mode=settings.normal_mode, id_mode=settings.id_mode)
    return request, source


def view_signature(view):
    """Cheap fingerprint of everything that changes the projected image (for auto preview)."""
    rv3d, region = view.rv3d, view.region
    return (tuple(round(x, 7) for row in rv3d.view_matrix for x in row),
            tuple(round(x, 7) for row in rv3d.window_matrix for x in row),
            region.width, region.height, rv3d.view_perspective)
