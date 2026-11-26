"""ViewPass GUI/GPU test suite. Runs only in a fresh GUI Blender started by tests/run_blender_tests.py.

Expected values come from analytic geometry or from Blender's own functions
(RegionView3D.perspective_matrix, bpy_extras.object_utils.world_to_camera_view,
bpy.data.images.load), never from ViewPass output.
"""
import argparse
import ctypes
import json
import math
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

p = argparse.ArgumentParser()
p.add_argument('--repo', required=True)
p.add_argument('--result', required=True, type=Path)
p.add_argument('--only', default='')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
sys.path.insert(0, a.repo)

W, H = 200, 150


# ----------------------------------------------------------------------------- helpers

def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)
    for ng in list(bpy.data.node_groups):
        bpy.data.node_groups.remove(ng)
    bpy.context.view_layer.update()


def plane(name, center, half, coll=None, scale=(1, 1, 1), rot=(0, 0, 0)):
    hx, hy = half
    me = bpy.data.meshes.new(name + '_mesh')
    me.from_pydata([(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0)], [], [(0, 1, 2, 3)])
    me.update()
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    ob.location, ob.scale, ob.rotation_euler = center, scale, rot
    return ob


def cube(name, center, size, scale=(1, 1, 1)):
    s = size / 2
    v = [(-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s), (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]  # outward
    me = bpy.data.meshes.new(name + '_mesh')
    me.from_pydata(v, [], f)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location, ob.scale = center, scale
    return ob


def persp(fov_y, aspect, n, f):
    t = 1 / math.tan(fov_y / 2)
    return np.array([[t / aspect, 0, 0, 0], [0, t, 0, 0], [0, 0, -(f + n) / (f - n), -2 * f * n / (f - n)],
                     [0, 0, -1, 0]])


def ortho(half_h, aspect, n, f):
    return np.array([[1 / (half_h * aspect), 0, 0, 0], [0, 1 / half_h, 0, 0],
                     [0, 0, -2 / (f - n), -(f + n) / (f - n)], [0, 0, 0, 1]])


def pix(clip_m, point, w, h):
    c = clip_m @ np.array([*point, 1.0])
    x, y = c[0] / c[3], c[1] / c[3]
    return int((1 - y) * h / 2), int((x + 1) * w / 2)


def req(view, projm, w=W, h=H, passes=('depth', 'normal', 'object_id', 'mask'), **kw):
    return dict(width=w, height=h, view_matrix=np.asarray(view).tolist(),
                projection_matrix=np.asarray(projm).tolist(), passes=list(passes), **kw)


def name_at(res, r, c):
    i = int(res['object_id'][r, c])
    return res['id_map'].get(i) if i else None


def private_bytes():
    """Process memory for leak trends: Windows private bytes, Linux RSS; None if unavailable."""
    if sys.platform.startswith('linux'):
        try:
            with open('/proc/self/status', encoding='ascii') as fh:
                for line in fh:
                    if line.startswith('VmRSS:'):
                        return int(line.split()[1]) * 1024
        except OSError:
            return None
        return None
    if os.name != 'nt':
        return None
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + \
                   [(n, ctypes.c_size_t) for n in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                                                   'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                                                   'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    check(k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb), 'GetProcessMemoryInfo')
    return pmc.PagefileUsage


def snapshot():
    s = bpy.context.scene
    vl = bpy.context.view_layer
    ids = {}
    for coll_name in ('objects', 'meshes', 'materials', 'images', 'cameras', 'node_groups', 'collections',
                      'textures', 'worlds', 'lights', 'scenes', 'texts', 'actions'):
        ids[coll_name] = tuple(sorted(x.name for x in getattr(bpy.data, coll_name)))
    obs = tuple(sorted((o.name, tuple(v for row in o.matrix_world for v in row), o.hide_get(), o.select_get(),
                        o.hide_viewport, o.display_type, len(o.modifiers), tuple(o.keys()))
                       for o in s.objects))
    r = s.render
    render = (r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.film_transparent,
              r.use_compositing, r.filepath, s.display_settings.display_device, s.view_settings.view_transform)
    passes = tuple(getattr(vl, n) for n in ('use_pass_z', 'use_pass_normal', 'use_pass_mist',
                                            'use_pass_object_index') if hasattr(vl, n))
    comp = getattr(s, 'compositing_node_group', None)
    comp = (comp.name, len(comp.nodes)) if comp is not None else None
    return dict(ids=ids, obs=obs, render=render, passes=passes, comp=comp, frame=s.frame_current,
                camera=s.camera.name if s.camera else None, mode=bpy.context.mode,
                active=vl.objects.active.name if vl.objects.active else None, scene_props=tuple(s.keys()))


def find_view3d():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                return window, area, region
    raise AssertionError('no 3D view')


def override(window, area, region):
    return dict(window=window, screen=window.screen, area=area, region=region, space_data=area.spaces.active)


def set_view(area, region, *, location=(0, 0, 0), rotation=(1, 0, 0, 0), distance=5.0, perspective='PERSP'):
    rv3d = region.data
    rv3d.view_perspective = perspective
    rv3d.view_location = location
    rv3d.view_rotation = Quaternion(rotation)
    rv3d.view_distance = distance
    rv3d.update()
    return rv3d


def settings_for_test(s, outdir):
    s.use_depth = s.use_normal = s.use_object_id = s.use_mask = True
    s.depth_png, s.depth_exr = 'PNG16', True
    s.normal_png, s.normal_exr = 'PNG8', True
    s.id_png, s.id_exr = True, True
    s.output_dir = outdir + os.sep
    s.base_name = 'gui'
    s.numbering = 'AUTO'
    s.resolution_mode = 'CUSTOM'
    s.width, s.lock_aspect = 240, True


# ----------------------------------------------------------------------------- tests

def t_registration(ctx, vp):
    for op in ('export', 'export_as', 'preview', 'preview_hide', 'open_folder'):
        check(hasattr(bpy.ops.viewpass, op), f'operator {op} missing')
    check(hasattr(bpy.types, 'VIEWPASS_PT_main'), 'panel missing')
    check(hasattr(bpy.context.window_manager, 'viewpass'), 'settings missing')
    return 'operators, panel, settings registered'


def t_empty_scene(ctx, vp):
    clear_scene()
    res = vp.capture.capture(ctx, req(np.eye(4), persp(math.radians(60), W / H, .1, 100)))
    check(not res['mask'].any() and np.isnan(res['depth']).all() and (res['object_id'] == 0).all()
          and (res['normal'] == 0).all() and res['id_map'] == {}, 'empty scene must be all background')
    check(any('nothing visible' in w for w in res['warnings']), 'empty capture should warn')
    return 'all background, warning present'


def t_visibility(ctx, vp):
    clear_scene()
    plane('Visible', (-1, 0, -5), (.5, .5))
    hid = plane('HiddenEye', (1, 0, -5), (.5, .5))
    hid.hide_set(True)
    ex = bpy.data.collections.new('Excluded')
    ctx.scene.collection.children.link(ex)
    plane('InExcluded', (0, 1.2, -5), (.5, .3), coll=ex)
    ctx.view_layer.layer_collection.children['Excluded'].exclude = True
    hc = bpy.data.collections.new('HiddenColl')
    ctx.scene.collection.children.link(hc)
    plane('InHiddenColl', (0, -1.2, -5), (.5, .3), coll=hc)
    ctx.view_layer.layer_collection.children['HiddenColl'].hide_viewport = True
    dv = plane('DisabledVP', (2.5, 0, -5), (.4, .4))
    dv.hide_viewport = True
    wire = plane('WireDisplay', (-2.5, 0, -5), (.4, .4))
    wire.display_type = 'WIRE'
    ctx.view_layer.update()
    projm = persp(math.radians(70), W / H, .1, 100)
    res = vp.capture.capture(ctx, req(np.eye(4), projm))
    names = set(res['id_map'].values())
    check(names == {'Visible'}, f'only Visible expected, got {names}')
    for pt in [(1, 0, -5), (0, 1.2, -5), (0, -1.2, -5), (2.5, 0, -5), (-2.5, 0, -5)]:
        r, c = pix(projm, pt, W, H)
        check(not res['mask'][r, c], f'hidden geometry leaked at {pt}')
    r, c = pix(projm, (-1, 0, -5), W, H)
    check(name_at(res, r, c) == 'Visible' and abs(res['depth'][r, c] - 5) < 1e-4, 'visible plane wrong')
    check(any('Wire' in w for w in res['warnings']), 'wire display skip should be reported')
    return 'hide, exclude, hidden collection, disabled, wire display'


def t_local_view(ctx, vp):
    clear_scene()
    a_ = plane('LocalA', (-1, 0, -5), (.5, .5))
    plane('LocalB', (1, 0, -5), (.5, .5))
    window, area, region = find_view3d()
    for o in ctx.scene.objects:
        o.select_set(o is a_)
    ctx.view_layer.objects.active = a_
    with ctx.temp_override(**override(window, area, region)):
        bpy.ops.view3d.localview(frame_selected=False)
    try:
        check(area.spaces.active.local_view is not None, 'local view not entered')
        with ctx.temp_override(**override(window, area, region)):
            res = vp.capture.capture(bpy.context, req(np.eye(4), persp(math.radians(70), W / H, .1, 100)))
        check(set(res['id_map'].values()) == {'LocalA'}, f'local view not respected: {res["id_map"]}')
    finally:
        with ctx.temp_override(**override(window, area, region)):
            bpy.ops.view3d.localview(frame_selected=False)
    return 'only local-view objects captured'


def t_modifier_and_scale(ctx, vp):
    clear_scene()
    ob = plane('Arrayed', (-1, 0, -6), (.4, .4))
    m = ob.modifiers.new('arr', 'ARRAY')
    m.count, m.use_relative_offset, m.relative_offset_displace = 2, True, (2.5, 0, 0)   # copy at x + 2.0
    cube('Mirrored', (0, -1.6, -6), 1.0, scale=(-1.5, 1, 1))
    plane('Tilted', (0, 1.6, -6), (.5, .3), scale=(2, 1, .5), rot=(0, math.radians(30), 0))
    ctx.view_layer.update()
    projm = persp(math.radians(70), W / H, .1, 100)
    res = vp.capture.capture(ctx, req(np.eye(4), projm))
    r, c = pix(projm, (-1 + 2.0, 0, -6), W, H)
    check(name_at(res, r, c) == 'Arrayed' and abs(res['depth'][r, c] - 6) < 1e-4, 'array copy missing/wrong')
    # mirrored closed cube: front face (z = -6 + .5) normal must face the viewer (+Z)
    r, c = pix(projm, (0, -1.6, -5.5), W, H)
    check(name_at(res, r, c) == 'Mirrored', 'mirrored cube not visible')
    check(abs(res['depth'][r, c] - 5.5) < 1e-4, f"mirrored depth {res['depth'][r, c]}")
    check(np.allclose(res['normal'][r, c], (0, 0, 1), atol=1e-4), f"negative scale normal {res['normal'][r, c]}")
    # tilted + non-uniform scale: analytic inverse-transpose normal
    M = Matrix.LocRotScale(None, Euler((0, math.radians(30), 0)), Vector((2, 1, .5))).to_3x3()
    n = (M.inverted().transposed() @ Vector((0, 0, 1))).normalized()
    r, c = pix(projm, (0, 1.6, -6), W, H)
    check(np.allclose(res['normal'][r, c], tuple(n), atol=2e-3), f"tilted normal {res['normal'][r, c]} vs {tuple(n)}")
    return 'array modifier evaluated, mirrored outward normals, inverse-transpose normals'


def _gn_scatter(host, src):
    ng = bpy.data.node_groups.new('VP_scatter', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    n = ng.nodes
    gi, go = n.new('NodeGroupInput'), n.new('NodeGroupOutput')
    oi = n.new('GeometryNodeObjectInfo')
    oi.inputs['Object'].default_value = src
    oi.inputs['As Instance'].default_value = True
    iop = n.new('GeometryNodeInstanceOnPoints')
    ng.links.new(gi.outputs[0], iop.inputs['Points'])
    ng.links.new(oi.outputs['Geometry'], iop.inputs['Instance'])
    ng.links.new(iop.outputs[0], go.inputs[0])
    host.modifiers.new('scatter', 'NODES').node_group = ng


def t_instances(ctx, vp):
    clear_scene()
    src_coll = bpy.data.collections.new('Src')
    ctx.scene.collection.children.link(src_coll)
    src = plane('SrcPlane', (0, 0, 0), (.3, .3), coll=src_coll)
    ctx.view_layer.layer_collection.children['Src'].hide_viewport = True   # hidden source, instances visible
    for i, x in enumerate((-1.5, 0.0)):
        e = bpy.data.objects.new(f'CI_{i}', None)
        e.instance_type, e.instance_collection = 'COLLECTION', src_coll
        e.location = (x, 1.0, -6)
        ctx.scene.collection.objects.link(e)
    me = bpy.data.meshes.new('pts')
    me.from_pydata([(1.5, -1.0, -6), (0.0, -1.0, -6)], [], [])
    host = bpy.data.objects.new('Scatter', me)
    ctx.scene.collection.objects.link(host)
    _gn_scatter(host, src)
    ctx.view_layer.update()
    projm = persp(math.radians(70), W / H, .1, 100)
    pts = [(-1.5, 1, -6), (0, 1, -6), (1.5, -1, -6), (0, -1, -6)]
    out = {}
    for mode in ('OBJECT', 'INSTANCER', 'INSTANCE'):
        res = vp.capture.capture(ctx, req(np.eye(4), projm, id_mode=mode))
        got = []
        for pt in pts:
            r, c = pix(projm, pt, W, H)
            check(res['mask'][r, c] and abs(res['depth'][r, c] - 6) < 1e-4, f'{mode}: instance missing at {pt}')
            got.append(name_at(res, r, c))
        out[mode] = got
    check(set(out['OBJECT']) == {'SrcPlane'}, f"OBJECT ids {out['OBJECT']}")
    check(out['INSTANCER'] == ['CI_0', 'CI_1', 'Scatter', 'Scatter'], f"INSTANCER ids {out['INSTANCER']}")
    check(len(set(out['INSTANCE'])) == 4, f"INSTANCE ids not unique {out['INSTANCE']}")
    return f"collection + GN instances; ids {out}"


def t_viewport_matrices(ctx, vp):
    clear_scene()
    plane('Target', (0.7, -0.4, 0.0), (.6, .4))
    plane('Back', (0, 0, -3.0), (6, 6))
    ctx.view_layer.update()
    window, area, region = find_view3d()
    space = area.spaces.active
    settings = vp.props.settings(ctx)
    settings.resolution_mode, settings.scale = 'VIEW', 50
    results = {}
    for mode in ('PERSP', 'ORTHO'):
        q = Euler((math.radians(25), 0, math.radians(15))).to_quaternion()
        rv3d = set_view(area, region, location=(0.2, -0.1, -0.5), rotation=q, distance=7.0, perspective=mode)
        with ctx.temp_override(**override(window, area, region)):
            view = vp.viewport.resolve(bpy.context)
            request, source = vp.viewport.build_request(view, ctx.scene, bpy.context.evaluated_depsgraph_get(),
                                                        settings, ['depth', 'normal', 'object_id', 'mask'])
            res = vp.capture.capture(bpy.context, request)
        w, h = request['width'], request['height']
        check((w, h) == (round(region.width * .5), round(region.height * .5)), 'scale not applied')
        pm = np.array([list(r) for r in rv3d.perspective_matrix])        # Blender's own view-projection
        vm = np.array([list(r) for r in rv3d.view_matrix])
        shift = space.clip_end / 2 if mode == 'ORTHO' else 0.0             # Blender ortho near = -clip_end/2
        pt = np.array([0.7, -0.4, 0.0])
        c = pm @ np.array([*pt, 1])
        nx, ny = c[0] / c[3], c[1] / c[3]
        # pixel of a point measured with the region's aspect (output is a scaled region)
        r_, c_ = int((1 - ny) * h / 2), int((nx + 1) * w / 2)
        check(name_at(res, r_, c_) == 'Target', f'{mode}: target not at Blender-projected pixel')
        exp_depth = -(vm @ np.array([*pt, 1]))[2] + shift
        check(abs(res['depth'][r_, c_] - exp_depth) < 2e-3 * max(1, exp_depth), f"{mode}: depth {res['depth'][r_, c_]} vs {exp_depth}")
        n_view = vm[:3, :3] @ np.array([0, 0, 1.0])
        check(np.allclose(res['normal'][r_, c_], n_view, atol=2e-3), f"{mode}: view normal {res['normal'][r_, c_]} vs {n_view}")
        check((res['depth'][res['mask']] > 0).all(), f'{mode}: non-positive depth in UI capture')
        results[mode] = dict(size=[w, h], depth=float(res['depth'][r_, c_]), shift=source['ortho_depth_origin_shift'])
    return results


def t_camera_view(ctx, vp):
    from bpy_extras.object_utils import world_to_camera_view
    clear_scene()
    plane('CamTarget', (0.5, 0.3, 0.0), (.4, .3))
    plane('CamBack', (0, 0, -2.0), (8, 8))
    cam_data = bpy.data.cameras.new('TestCam')
    cam_data.lens, cam_data.shift_x = 40, 0.1
    cam = bpy.data.objects.new('TestCam', cam_data)
    ctx.scene.collection.objects.link(cam)
    cam.location = (1.0, -6.0, 3.0)
    cam.rotation_euler = (math.radians(65), 0, math.radians(10))
    ctx.scene.camera = cam
    ctx.scene.render.resolution_x, ctx.scene.render.resolution_y, ctx.scene.render.resolution_percentage = 320, 180, 100
    ctx.view_layer.update()
    window, area, region = find_view3d()
    region.data.view_perspective = 'CAMERA'
    region.data.update()
    settings = vp.props.settings(ctx)
    settings.resolution_mode, settings.scale, settings.camera_frame = 'VIEW', 100, True
    before = snapshot()
    with ctx.temp_override(**override(window, area, region)):
        view = vp.viewport.resolve(bpy.context)
        request, source = vp.viewport.build_request(view, ctx.scene, bpy.context.evaluated_depsgraph_get(),
                                                    settings, ['depth', 'normal', 'object_id', 'mask'])
        res = vp.capture.capture(bpy.context, request)
    check(snapshot() == before, 'camera capture changed the scene')
    check((request['width'], request['height']) == (320, 180) and source['kind'] == 'camera', 'camera framing')
    dg = ctx.evaluated_depsgraph_get()
    # Blender's camera frame corners in camera space (lens, sensor fit and shift included)
    frame = [Vector(v) for v in cam.data.view_frame(scene=ctx.scene)]   # tr, br, bl, tl
    tr, br, bl, tl = frame
    mw = cam.matrix_world.normalized()
    for pt, plane_z, name in [((0.5, 0.3, 0.0), 0.0, 'CamTarget'), ((0.8, 0.5, 0.0), 0.0, 'CamTarget'),
                              ((-2.0, 1.0, -2.0), -2.0, 'CamBack')]:
        co = world_to_camera_view(ctx.scene, cam.evaluated_get(dg), Vector(pt))   # Blender: (x, y in 0..1, depth)
        r_, c_ = int((1 - co.y) * 180), int(co.x * 320)
        check(0 <= r_ < 180 and 0 <= c_ < 320, 'sample outside frame')
        check(res['mask'][r_, c_] and name_at(res, r_, c_) == name, f'{name} not at Blender-projected pixel')
        u, v = (c_ + 0.5) / 320, 1 - (r_ + 0.5) / 180                     # pixel centre, v up
        top = tl.lerp(tr, u)
        bottom = bl.lerp(br, u)
        d_cam = bottom.lerp(top, v)                                       # ray direction in camera space
        origin = mw.translation
        d_world = (mw.to_3x3() @ d_cam)
        t = (plane_z - origin.z) / d_world.z
        hit_cam = mw.inverted() @ (origin + d_world * t)
        exp = -hit_cam.z
        check(abs(res['depth'][r_, c_] - exp) < 1e-4 * exp, f"camera depth {res['depth'][r_, c_]} vs ray {exp}")
    region.data.view_perspective = 'PERSP'
    region.data.update()
    return 'camera frame matches world_to_camera_view (with lens shift)'


def t_repeat_and_leak(ctx, vp):
    clear_scene()
    for i in range(6):
        cube(f'C{i}', ((i % 3) - 1, (i // 3) - .5, -6 - i * .3), .8)
    ctx.view_layer.update()
    r = req(np.eye(4), persp(math.radians(60), 4 / 3, .1, 100), 640, 480)
    base = vp.capture.capture(ctx, r)
    mem, mem_noredraw, times = [], [], []
    for i in range(20):                         # back-to-back (no redraw between captures)
        res = vp.capture.capture(ctx, r)
        mem_noredraw.append(private_bytes())
        del res
    ov = override(*find_view3d())
    for i in range(40):                         # like interactive use: the UI redraws between captures
        t0 = time.perf_counter()
        with bpy.context.temp_override(**ov):
            res = vp.capture.capture(bpy.context, r)
        times.append(time.perf_counter() - t0)
        for k in ('depth', 'normal', 'object_id', 'mask'):
            check(np.array_equal(res[k], base[k], equal_nan=True), f'repeat {i}: {k} differs')
        del res
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        mem.append(private_bytes())
    # Leak criterion: no growth trend in steady state. A per-capture leak (even 1 MB) grows on
    # nearly every capture; allocator chunks show up as rare single steps. So: <= 3 growth steps
    # > 1 MB and < 32 MB in total over the last 20 captures. (The 640x480 targets alone are 11 MB.)
    # large captures are not kept: allocation per capture, released afterwards
    big = req(np.eye(4), persp(math.radians(60), 16 / 9, .1, 100), 2560, 1440)
    with bpy.context.temp_override(**ov):
        vp.capture.capture(bpy.context, big)
    from viewpass import gpu_draw
    check(gpu_draw._targets is None, 'large render targets must not be kept')
    detail = dict(median_ms=round(1000 * float(np.median(times)), 2),
                  p95_ms=round(1000 * float(np.percentile(times, 95)), 2))
    if any(m is None for m in mem + mem_noredraw):
        detail['memory'] = 'NOT MEASURED on this OS (no process memory API); determinism checked only'
        return detail
    tail = np.array(mem[-21:], dtype=np.float64) / 1e6
    steps = int((np.diff(tail) > 1.0).sum())
    growth = float(tail[-1] - tail[0])
    burst = (mem_noredraw[-1] - mem_noredraw[0]) / 1e6
    print('MEM noredraw MB', [round(m / 1e6) for m in mem_noredraw])
    print('MEM redraw MB', [round(m / 1e6) for m in mem])
    check(steps <= 3 and growth < 32, f'memory trend: {steps} growth steps, {growth:.1f} MB over the last 20 captures')
    check(burst < 64, f'back-to-back captures grew {burst:.1f} MB (render targets should be reused)')
    detail.update(memory_source='VmRSS' if sys.platform.startswith('linux') else 'private bytes',
                  mem_steady_growth_mb_last20=round(growth, 2), growth_steps_last20=steps,
                  mem_ramp_mb=round((max(mem) - mem[0]) / 1e6, 2), mem_growth_mb_20_back_to_back=round(burst, 2))
    return detail


def t_fault_injection(ctx, vp):
    import gpu
    clear_scene()
    plane('F', (0, 0, -4), (1, 1))
    ctx.view_layer.update()
    r = req(np.eye(4), persp(math.radians(60), W / H, .1, 100))
    good = vp.capture.capture(ctx, r)
    before = (gpu.state.depth_test_get(), gpu.state.depth_mask_get(), gpu.state.blend_get(), gpu.state.viewport_get())
    snap = snapshot()

    def boom():
        raise RuntimeError('injected GPU failure')
    try:
        vp.capture.capture(ctx, r, _after_draw=boom)
        raise AssertionError('fault was not raised')
    except RuntimeError as exc:
        check('injected' in str(exc), 'unexpected error')
    after = (gpu.state.depth_test_get(), gpu.state.depth_mask_get(), gpu.state.blend_get(), gpu.state.viewport_get())
    check(before == after, f'GPU state not restored: {before} -> {after}')
    check(snapshot() == snap, 'scene changed after failure')
    from viewpass import gpu_draw
    check(gpu_draw._targets is None, 'targets kept after a failure')
    again = vp.capture.capture(ctx, r)
    for k in ('depth', 'normal', 'object_id', 'mask'):
        check(np.array_equal(again[k], good[k], equal_nan=True), f'retry differs: {k}')
    return 'state restored, retry identical'


def t_sizes(ctx, vp):
    clear_scene()
    plane('S', (0.25, 0.25, -4), (.5, .5))
    ctx.view_layer.update()
    for w, h in ((1, 1), (3, 7), (640, 160), (160, 640), (1920, 1080)):
        projm = persp(math.radians(60), w / h, .1, 100)
        res = vp.capture.capture(ctx, req(np.eye(4), projm, w, h))
        check(res['depth'].shape == (h, w), f'{w}x{h} shape')
        if w >= 3:
            r_, c_ = pix(projm, (0.25, 0.25, -4), w, h)
            check(res['mask'][r_, c_] and abs(res['depth'][r_, c_] - 4) < 1e-4, f'{w}x{h} sample')
    for bad in (dict(width=0, height=10), dict(width=20000, height=10), dict(width=8000, height=8000)):
        try:
            vp.capture.capture(ctx, req(np.eye(4), persp(1, 1, .1, 10), **{}) | bad)
            raise AssertionError(f'size {bad} accepted')
        except vp.capture.RequestError:
            pass
    try:
        vp.capture.capture(ctx, req(np.eye(4), np.zeros((4, 4))))
        raise AssertionError('singular projection accepted')
    except vp.capture.RequestError:
        pass
    return '1x1, 3x7, wide, tall, 1080p; oversize and singular rejected'


def t_multi_area(ctx, vp):
    clear_scene()
    plane('Left', (-1.5, 0, 0), (.5, .5))
    ctx.view_layer.update()
    window, area, region = find_view3d()
    with ctx.temp_override(**override(window, area, region)):
        bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
    areas = [a_ for a_ in window.screen.areas if a_.type == 'VIEW_3D']
    check(len(areas) >= 2, 'split failed')
    a1, a2 = areas[0], areas[1]
    r1 = next(r for r in a1.regions if r.type == 'WINDOW')
    r2 = next(r for r in a2.regions if r.type == 'WINDOW')
    set_view(a1, r1, rotation=(1, 0, 0, 0), distance=8)                              # looking down -Z
    set_view(a2, r2, rotation=tuple(Euler((0, 0, math.pi)).to_quaternion()), distance=8)   # rotated 180 deg
    settings = vp.props.settings(ctx)
    settings.resolution_mode, settings.scale = 'VIEW', 50
    cols = []
    for ar, rg in ((a1, r1), (a2, r2)):
        with ctx.temp_override(**override(window, ar, rg)):
            view = vp.viewport.resolve(bpy.context)
            check(view.area == ar, 'resolve picked the wrong area')
            request, _ = vp.viewport.build_request(view, ctx.scene, bpy.context.evaluated_depsgraph_get(),
                                                   settings, ['depth', 'mask', 'object_id'])
            vmat = np.array(request['view_matrix'])
            check(np.allclose(vmat, np.array([list(r) for r in rg.data.view_matrix])), 'matrices from wrong view')
            res = vp.capture.capture(bpy.context, request)
        ys, xs = np.nonzero(res['mask'])
        check(xs.size > 0, 'object not visible')
        cols.append(xs.mean() / request['width'])
    check(cols[0] < 0.5 < cols[1], f'object should be left in view 1 and right in view 2: {cols}')
    with ctx.temp_override(**override(window, a2, r2)):
        bpy.ops.screen.area_close()
    return f'each view captured from its own matrices (centroid x {cols[0]:.2f} / {cols[1]:.2f})'


def t_precision(ctx, vp):
    clear_scene()
    plane('Far', (0, 0, -100.0), (300, 300))
    plane('Near5mm', (0, 0, -99.995), (300, 300))
    ctx.view_layer.update()
    res = vp.capture.capture(ctx, req(np.eye(4), persp(math.radians(60), W / H, .01, 1000)))
    names = {res['id_map'][int(i)] for i in np.unique(res['object_id'][res['mask']])}
    check(names == {'Near5mm'}, f'z-fighting: {names}')
    check(np.allclose(res['depth'][res['mask']], 99.995, atol=1e-3), 'depth value')
    return 'surfaces 5 mm apart at 100 m ordered correctly (clip 0.01..1000)'


def t_edit_mode(ctx, vp):
    clear_scene()
    ob = plane('Editing', (0, 0, -5), (.5, .5))
    ctx.view_layer.objects.active = ob
    ob.select_set(True)
    window, area, region = find_view3d()
    with ctx.temp_override(**override(window, area, region)):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.transform.translate(value=(0, 0, 1.0))      # edit-mode move: plane now at z = -4
    try:
        with ctx.temp_override(**override(window, area, region)):
            mode_before = bpy.context.mode
            res = vp.capture.capture(bpy.context, req(np.eye(4), persp(math.radians(60), W / H, .1, 100)))
            check(bpy.context.mode == mode_before == 'EDIT_MESH', 'mode changed')
        r_, c_ = pix(persp(math.radians(60), W / H, .1, 100), (0, 0, -4), W, H)
        check(abs(res['depth'][r_, c_] - 4.0) < 1e-4, f"edit-mode geometry not used: {res['depth'][r_, c_]}")
    finally:
        with ctx.temp_override(**override(window, area, region)):
            bpy.ops.object.mode_set(mode='OBJECT')
    return 'edit-mode edits captured, mode untouched'


def t_operator_export(ctx, vp):
    from viewpass import exr, png
    clear_scene()
    plane('OpNear', (-0.4, 0.2, -0.5), (.5, .4))
    plane('OpFar', (0.3, -0.2, -2.5), (1.2, .9))
    ctx.view_layer.update()
    window, area, region = find_view3d()
    set_view(area, region, rotation=(1, 0, 0, 0), distance=6)
    out = tempfile.mkdtemp(prefix='viewpass-gui-')
    s = vp.props.settings(ctx)
    settings_for_test(s, out)
    before = snapshot()
    n_images = len(bpy.data.images)
    with ctx.temp_override(**override(window, area, region)):
        r1 = bpy.ops.viewpass.export()
        r2 = bpy.ops.viewpass.export()
    check(r1 == {'FINISHED'} and r2 == {'FINISHED'}, f'operator failed: {vp.operators.status}')
    check(snapshot() == before and len(bpy.data.images) == n_images, 'export changed scene/datablocks')
    files = sorted(os.listdir(out))
    check(sum(f.startswith('gui_0001_') for f in files) == 8 and sum(f.startswith('gui_0002_') for f in files) == 8,
          f'unexpected files {files}')
    # Reference arrays through the same UI path (request from the same view)
    with ctx.temp_override(**override(window, area, region)):
        view = vp.viewport.resolve(bpy.context)
        request, _ = vp.viewport.build_request(view, ctx.scene, bpy.context.evaluated_depsgraph_get(), s,
                                               ['depth', 'normal', 'object_id', 'mask'])
        ref = vp.capture.capture(bpy.context, request)
    rd = lambda n: open(os.path.join(out, 'gui_0001_' + n), 'rb').read()
    z = exr.decode(rd('depth.exr'))[0]['Z']
    check(np.array_equal(z, ref['depth'], equal_nan=True), 'EXR depth != capture')
    ids = png.decode(rd('id.png'))[0][..., 0]
    check(np.array_equal(ids, ref['object_id']), 'ID PNG != capture')
    meta = json.loads(rd('meta.json'))
    check(meta['resolution'] == [request['width'], request['height']], 'meta resolution')
    check(set(meta['id_map'].values()) == {'OpNear', 'OpFar'}, 'meta id_map')
    # Independent decoder: Blender's image loader (temporary datablocks, removed afterwards)
    loaded = {}
    for name in ('mask.png', 'depth.png', 'normal.exr'):
        img = bpy.data.images.load(os.path.join(out, 'gui_0001_' + name), check_existing=False)
        try:
            img.colorspace_settings.is_data = True
            px = np.empty(img.size[0] * img.size[1] * img.channels, np.float32)
            img.pixels.foreach_get(px)
            loaded[name] = (px.reshape(img.size[1], img.size[0], img.channels)[::-1], img.depth, img.is_float)
        finally:
            bpy.data.images.remove(img)
    mpx = loaded['mask.png'][0][..., 0] > 0.5
    check(np.array_equal(mpx, ref['mask']), 'Blender-read mask differs (orientation?)')
    dpx, ddepth, dfloat = loaded['depth.png']
    check(dfloat, f'16-bit PNG should load into a float buffer (depth={ddepth})')
    ours = png.decode(rd('depth.png'))[0][..., 0].astype(np.float64) / 65535
    check(np.allclose(dpx[..., 0], ours, atol=1 / 65535 + 1e-6), 'Blender-read 16-bit depth differs')
    npx, _, isf = loaded['normal.exr']
    check(isf and np.allclose(npx[..., :3][ref['mask']], ref['normal'][ref['mask']], atol=1e-6),
          'Blender-read normal EXR differs')
    # collision handling: exact name exists -> error, nothing overwritten
    s.numbering, s.base_name, s.overwrite = 'NONE', 'gui_0001', False
    stamp = os.path.getmtime(os.path.join(out, 'gui_0001_depth.exr'))
    def refused(fn, needle):
        # bpy.ops raises RuntimeError when an operator reports an ERROR and cancels
        try:
            ret = fn()
        except RuntimeError as exc:
            check(needle in str(exc), f'unexpected error text: {exc}')
            return True
        return ret == {'CANCELLED'}
    with ctx.temp_override(**override(window, area, region)):
        check(refused(lambda: bpy.ops.viewpass.export(), 'already exist'), 'collision not refused')
    check(os.path.getmtime(os.path.join(out, 'gui_0001_depth.exr')) == stamp, 'existing file was touched')
    # export_as without invoke must refuse (view must be frozen before the browser)
    with ctx.temp_override(**override(window, area, region)):
        check(refused(lambda: bpy.ops.viewpass.export_as('EXEC_DEFAULT', filepath=os.path.join(out, 'x')),
                      '3D Viewport'), 'export_as without invoke should fail explicitly')
    check(not any(f.startswith('x_') for f in os.listdir(out)), 'export_as wrote files')
    check(snapshot() == before and len(bpy.data.images) == n_images, 'scene changed')
    return f'16 files, EXR/PNG equal capture, Blender loader agrees, collision refused ({out})'


def t_view_lost(ctx, vp):
    window, area, region = find_view3d()
    with ctx.temp_override(**override(window, area, region)):
        bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.5)
    areas = [a_ for a_ in window.screen.areas if a_.type == 'VIEW_3D']
    a2 = areas[-1]
    r2 = next(r for r in a2.regions if r.type == 'WINDOW')
    ptrs = (window.as_pointer(), a2.as_pointer(), r2.as_pointer())
    check(vp.viewport.find(ptrs).area == a2, 'find failed for live view')
    with ctx.temp_override(**override(window, a2, r2)):
        bpy.ops.screen.area_close()
    try:
        vp.viewport.find(ptrs)
        raise AssertionError('closed view still found')
    except vp.viewport.ViewError as exc:
        check('closed' in str(exc), 'error message should say the view was closed')
    return 'closed view -> explicit ViewError'


def t_preview_lifecycle(ctx, vp):
    clear_scene()
    plane('Prev', (0, 0, 0), (1, 1))
    ctx.view_layer.update()
    window, area, region = find_view3d()
    set_view(area, region, distance=6)
    pv = vp.preview
    before = snapshot()
    with ctx.temp_override(**override(window, area, region)):
        check(bpy.ops.viewpass.preview() == {'FINISHED'}, 'preview failed')
    check(pv.state.active and pv.state.texture is not None, 'preview texture missing')
    check(pv._draw_handle is not None and bpy.app.timers.is_registered(pv._tick), 'handler/timer missing')
    for name in ('depth', 'normal', 'object_id', 'mask'):
        vp.props.settings(ctx).preview_pass = name        # re-encode without capture
        check(pv.state.texture is not None, f'texture for {name}')
    check(snapshot() == before and not any('viewpass' in i.name.lower() for i in bpy.data.images), 'preview created data')
    with ctx.temp_override(**override(window, area, region)):
        bpy.ops.viewpass.preview_hide()
    check(not pv.state.active and pv.state.texture is None and pv.state.raw is None, 'hide did not free')
    # closing the source view releases the preview via the timer
    with ctx.temp_override(**override(window, area, region)):
        bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
    a2 = [a_ for a_ in window.screen.areas if a_.type == 'VIEW_3D'][-1]
    r2 = next(r for r in a2.regions if r.type == 'WINDOW')
    with ctx.temp_override(**override(window, a2, r2)):
        bpy.ops.viewpass.preview()
    check(pv.state.active, 'preview on second view')
    with ctx.temp_override(**override(window, a2, r2)):
        bpy.ops.screen.area_close()
    pv._tick()
    check(not pv.state.active and pv.state.texture is None, 'closed view did not release preview')
    # load_pre releases as well
    with ctx.temp_override(**override(window, area, region)):
        bpy.ops.viewpass.preview()
    pv._on_load_pre()
    check(not pv.state.active, 'load_pre did not clear')
    return 'refresh, re-encode, hide, closed view and file load release resources'


def t_multi_window(ctx, vp):
    clear_scene()
    plane('MW', (0, 0, 0), (1, 1))
    ctx.view_layer.update()
    before = {w.as_pointer() for w in bpy.context.window_manager.windows}
    window, area, region = find_view3d()
    with ctx.temp_override(**override(window, area, region)):
        bpy.ops.wm.window_new()
    new = [w for w in bpy.context.window_manager.windows if w.as_pointer() not in before]
    check(len(new) == 1, 'second window not created')
    win2 = new[0]
    a2 = next((x for x in win2.screen.areas if x.type == 'VIEW_3D'), None)
    check(a2 is not None, 'second window has no 3D view')
    r2 = next(r for r in a2.regions if r.type == 'WINDOW')
    set_view(a2, r2, rotation=tuple(Euler((math.radians(30), 0, 0)).to_quaternion()), distance=7)
    s = vp.props.settings(ctx)
    s.resolution_mode, s.scale = 'VIEW', 50
    try:
        with ctx.temp_override(**override(win2, a2, r2)):
            view = vp.viewport.resolve(bpy.context)
            check(view.window == win2 and view.area == a2, 'resolved the wrong window')
            request, _ = vp.viewport.build_request(view, ctx.scene, bpy.context.evaluated_depsgraph_get(), s,
                                                   ['depth', 'mask'])
            check(np.allclose(np.array(request['view_matrix']), np.array([list(r) for r in r2.data.view_matrix])),
                  'matrices not from the second window')
            res = vp.capture.capture(bpy.context, request)
        check(res['mask'].any(), 'nothing captured in the second window')
    finally:
        with ctx.temp_override(window=win2, screen=win2.screen):
            bpy.ops.wm.window_close()
    # Right after closing a window Blender may have no active GPU context until the next redraw:
    # the capture must fail explicitly (not crash), and work again after a redraw.
    window, area, region = find_view3d()
    r = req(np.eye(4), persp(math.radians(60), W / H, .1, 100))
    note = 'context still active after close'
    try:
        with ctx.temp_override(**override(window, area, region)):
            vp.capture.capture(bpy.context, r)
    except vp.capture.GPUContextError as exc:
        note = f'explicit error after close: {exc}'
    with ctx.temp_override(**override(window, area, region)):
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    with ctx.temp_override(**override(window, area, region)):     # redraw_timer drops the override
        res = vp.capture.capture(bpy.context, r)
    check(res['depth'].shape == (H, W), 'capture after redraw failed')
    return f"second main window uses its own view; {note}; recovered after redraw"


def t_reregister_clean(ctx, vp):
    import viewpass
    n_dg = len(bpy.app.handlers.depsgraph_update_post)
    n_lp = len(bpy.app.handlers.load_pre)
    # disable while a preview (auto refresh on) is showing
    clear_scene()
    plane('RR', (0, 0, 0), (1, 1))
    window, area, region = find_view3d()
    vp.props.settings(ctx).preview_auto = True
    with ctx.temp_override(**override(window, area, region)):
        check(bpy.ops.viewpass.preview() == {'FINISHED'}, 'preview before unregister')
    check(vp.preview.state.active and vp.preview._draw_handle is not None, 'preview not active')
    viewpass.unregister()
    check(not hasattr(bpy.ops.viewpass, 'export') or not hasattr(bpy.types, 'VIEWPASS_PT_main'), 'still registered')
    check(len(bpy.app.handlers.depsgraph_update_post) == n_dg - 1 and len(bpy.app.handlers.load_pre) == n_lp - 1,
          'handlers not removed')
    check(vp.preview._draw_handle is None, f'draw handle left: {vp.preview._draw_handle}')
    check(not bpy.app.timers.is_registered(vp.preview._tick), 'timer left')
    check(vp.preview._tick() is None, 'tick must stop when inactive')
    from viewpass import gpu_draw
    check(gpu_draw._targets is None and gpu_draw._shader is None, 'GPU resources kept after unregister')
    check(not bpy.app.timers.is_registered(gpu_draw._idle_release), 'idle-release timer left')
    viewpass.register()
    check(hasattr(bpy.types, 'VIEWPASS_PT_main'), 're-register failed')
    return 'unregister removes handlers, draw callbacks, timers; re-register works'


def t_deviation_warnings(ctx, vp):
    clear_scene()
    a_ = plane('SubdivDiff', (-1, 0, -5), (.4, .4))
    m = a_.modifiers.new('sub', 'SUBSURF')
    m.levels, m.render_levels = 1, 3
    b = plane('AlphaMat', (0, 0, -5), (.4, .4))
    mat = bpy.data.materials.new('VP_alpha')
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0.5
    b.data.materials.append(mat)
    c = plane('Displaced', (1, 0, -5), (.4, .4))
    dmat = bpy.data.materials.new('VP_disp')
    dmat.use_nodes = True
    dmat.displacement_method = 'DISPLACEMENT'
    nt = dmat.node_tree
    disp = nt.nodes.new('ShaderNodeDisplacement')
    nt.links.new(disp.outputs[0], nt.nodes['Material Output'].inputs['Displacement'])
    c.data.materials.append(dmat)
    plain = plane('Plain', (0, 1, -5), (.3, .3))
    pmat = bpy.data.materials.new('VP_default')          # a default material must not be flagged
    pmat.use_nodes = True
    plain.data.materials.append(pmat)
    ctx.view_layer.update()
    res = vp.capture.capture(ctx, req(np.eye(4), persp(math.radians(70), W / H, .1, 100)))
    text = ' | '.join(res['warnings'])
    check('SubdivDiff' in text and 'viewport/render' in text, f'render-diff warning missing: {text}')
    check('1 object(s) may use transparency' in text and 'AlphaMat' in text,
          f'transparency warning missing or with false positives: {text}')
    check('Displaced' in text and 'displacement' in text, f'displacement warning missing: {text}')
    check('Plain' not in text, f'false positive: {text}')
    for mname in ('VP_alpha', 'VP_disp', 'VP_default'):
        bpy.data.materials.remove(bpy.data.materials[mname])
    return text


TESTS = [t_registration, t_empty_scene, t_deviation_warnings, t_visibility, t_local_view, t_modifier_and_scale, t_instances,
         t_viewport_matrices, t_camera_view, t_repeat_and_leak, t_fault_injection, t_sizes, t_multi_area,
         t_precision, t_edit_mode, t_operator_export, t_view_lost, t_preview_lifecycle, t_multi_window,
         t_reregister_clean]


def write(status, **extra):
    import gpu
    info = dict(status=status, blender=bpy.app.version_string,
                gpu={k: getattr(gpu.platform, k)() for k in ('backend_type_get', 'vendor_get', 'renderer_get',
                                                            'version_get') if hasattr(gpu.platform, k)}, **extra)
    a.result.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding='utf-8')
    print('VIEWPASS_SUITE', status, flush=True)


start = time.monotonic()


def run():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW' and r.width > 0), None)
                if region is None:
                    continue
                results = []
                try:
                    import importlib
                    import viewpass
                    viewpass.register()
                    vp = argparse.Namespace(**{m: importlib.import_module(f'viewpass.{m}') for m in
                                               ('capture', 'viewport', 'props', 'preview', 'operators')})
                    only = set(filter(None, a.only.split(',')))
                    for t in TESTS:
                        if only and t.__name__ not in only:
                            continue
                        w0, ar0, rg0 = find_view3d()
                        t0 = time.perf_counter()
                        try:
                            with bpy.context.temp_override(**override(w0, ar0, rg0)):
                                detail = t(bpy.context, vp)
                            results.append(dict(test=t.__name__, status='pass', detail=detail,
                                                seconds=round(time.perf_counter() - t0, 3)))
                        except Exception:
                            results.append(dict(test=t.__name__, status='fail', traceback=traceback.format_exc()))
                        print('TEST', results[-1]['test'], results[-1]['status'], flush=True)
                    viewpass.unregister()
                    ok = results and all(r['status'] == 'pass' for r in results)
                    write('pass' if ok else 'fail', results=results)
                except Exception:
                    write('fail', results=results, traceback=traceback.format_exc())
                bpy.ops.wm.quit_blender()
                return None
    if time.monotonic() - start > 30:
        write('fail', reason='no 3D view')
        bpy.ops.wm.quit_blender()
        return None
    return 0.5


check(not bpy.app.background, 'GUI required')
bpy.app.timers.register(run, first_interval=1.0)
