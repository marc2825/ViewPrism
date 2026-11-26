"""Benchmark + render-pass comparison, run inside a sandboxed GUI Blender by tools/benchmark.py.

Builds procedural scenes (no third-party assets), times ViewPrism captures, renders the standard
Z / Normal / Object Index passes with EEVEE and Cycles from the same camera and compares values.
The scene changes made here (camera, passes, pass_index) exist only in this factory-startup
process and are never saved.
"""
import argparse
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

ap = argparse.ArgumentParser()
ap.add_argument('--repo', required=True)
ap.add_argument('--result', required=True, type=Path)
ap.add_argument('--scene', choices=['simple', 'complex'], default='simple')
ap.add_argument('--warm', type=int, default=7)
ap.add_argument('--renders', type=int, default=2)
ap.add_argument('--compare', action='store_true')
ap.add_argument('--width', type=int, default=1920)
ap.add_argument('--height', type=int, default=1080)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
sys.path.insert(0, a.repo)


def view3d():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                return dict(window=window, screen=window.screen, area=area, region=region,
                            space_data=area.spaces.active)


def build(kind):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    ov = view3d()
    with bpy.context.temp_override(**ov):
        bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
        if kind == 'simple':
            for i in range(12):
                bpy.ops.mesh.primitive_cube_add(size=1.2, location=((i % 4) * 2.2 - 3.3, (i // 4) * 2.2 - 2.2, 0.6))
        else:
            for i in range(30):
                bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=0.9,
                                                     location=((i % 6) * 2.4 - 6, (i // 6) * 2.4 - 4.8, 0.9))
                bpy.ops.object.shade_smooth()
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=0.25, location=(0, 0, -50))
            ico = bpy.context.active_object
            ico.name = 'ScatterSource'
            bpy.ops.mesh.primitive_grid_add(x_subdivisions=50, y_subdivisions=50, size=30, location=(0, 0, 0.25))
            grid = bpy.context.active_object
            grid.name = 'ScatterHost'
            ng = bpy.data.node_groups.new('bench_scatter', 'GeometryNodeTree')
            ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
            ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
            gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
            m2p = ng.nodes.new('GeometryNodeMeshToPoints')
            oi = ng.nodes.new('GeometryNodeObjectInfo')
            oi.inputs['Object'].default_value = ico
            oi.inputs['As Instance'].default_value = True
            iop = ng.nodes.new('GeometryNodeInstanceOnPoints')
            ng.links.new(gi.outputs[0], m2p.inputs['Mesh'])
            ng.links.new(m2p.outputs[0], iop.inputs['Points'])
            ng.links.new(oi.outputs['Geometry'], iop.inputs['Instance'])
            ng.links.new(iop.outputs[0], go.inputs[0])
            grid.modifiers.new('scatter', 'NODES').node_group = ng
            ico.hide_set(True)
    cam_data = bpy.data.cameras.new('BenchCam')
    cam_data.lens = 35
    cam_data.clip_start, cam_data.clip_end = 0.1, 200
    cam = bpy.data.objects.new('BenchCam', cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (0, -16, 9)
    cam.rotation_euler = (math.radians(62), 0, 0)
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = a.width, a.height, 100
    bpy.context.view_layer.update()
    ov['region'].data.view_perspective = 'CAMERA'
    ov['region'].data.update()
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    n_inst = 0
    for inst in dg.object_instances:
        if inst.object.type == 'MESH':
            n_inst += 1
            tris += len(inst.object.data.loop_triangles) if inst.is_instance else len(inst.object.evaluated_get(dg).data.loop_triangles)
    return ov, dict(objects=len(sc.objects), mesh_instances=n_inst, triangles=tris)


def viewprism_capture(vp, ov):
    s = bpy.context.window_manager.viewprism
    s.resolution_mode, s.scale, s.camera_frame = 'VIEW', 100, True
    with bpy.context.temp_override(**ov):
        view = vp['viewport'].resolve(bpy.context)
        request, source = vp['viewport'].build_request(view, bpy.context.scene, bpy.context.evaluated_depsgraph_get(),
                                                       s, ['depth', 'normal', 'object_id', 'mask'])
        t0 = time.perf_counter()
        res = vp['capture'].capture(bpy.context, request)
        total = time.perf_counter() - t0
    return res, request, source, total


def render_passes(engine, out_dir, tag):
    sc = bpy.context.scene
    vl = bpy.context.view_layer
    sc.render.engine = engine
    vl.use_pass_z = True
    vl.use_pass_normal = True
    if engine == 'CYCLES':
        vl.use_pass_object_index = True
        sc.cycles.samples = 1
        sc.cycles.use_denoising = False
        sc.cycles.use_adaptive_sampling = False
        sc.cycles.pixel_filter_type = 'BOX'
        sc.cycles.filter_width = 0.01
        sc.cycles.max_bounces = 0
    elif engine == 'BLENDER_EEVEE' or engine.startswith('BLENDER_EEVEE'):
        sc.eevee.taa_render_samples = 1
    fmt = sc.render.image_settings
    if 'media_type' in fmt.bl_rna.properties:          # Blender 5.x
        fmt.media_type = 'MULTI_LAYER_IMAGE'
        fmt.file_format = 'OPEN_EXR_MULTILAYER'
    else:                                              # Blender 4.x
        fmt.file_format = 'OPEN_EXR_MULTILAYER'
    sc.render.image_settings.color_depth = '32'
    sc.render.image_settings.exr_codec = 'ZIP'
    sc.render.filepath = os.path.join(out_dir, f'{tag}_')
    t0 = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    dt = time.perf_counter() - t0
    import glob
    found = sorted(glob.glob(os.path.join(out_dir, f'{tag}_*')), key=os.path.getmtime)
    if not found:
        raise RuntimeError(f'render output for {tag} not found in {out_dir}')
    return dt, found[-1]


def eroded(mask, n=2):
    m = mask.copy()
    for _ in range(n):
        m[1:] &= mask[:-1]; m[:-1] &= mask[1:]; m[:, 1:] &= mask[:, :-1]; m[:, :-1] &= mask[:, 1:]
        mask = m.copy()
    return m


def main():
    import importlib
    import viewprism
    viewprism.register()
    vp = {m: importlib.import_module(f'viewprism.{m}') for m in ('capture', 'viewport', 'writer', 'exr')}
    import gpu
    info = dict(blender=bpy.app.version_string, scene=a.scene,
                gpu={k: getattr(gpu.platform, k)() for k in ('backend_type_get', 'renderer_get', 'version_get')})
    ov, stats = build(a.scene)
    info['scene_stats'] = stats
    # cold = first capture in this process (shader compile, target allocation)
    res, request, source, cold = viewprism_capture(vp, ov)
    info['viewprism_cold_s'] = cold
    info['viewprism_cold_stages'] = res['stats']['seconds']
    warm, stages = [], []
    for _ in range(a.warm):
        res, request, source, t = viewprism_capture(vp, ov)
        warm.append(t)
        stages.append(res['stats']['seconds'])
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    info['viewprism_warm_s'] = warm
    info['viewprism_warm_median_s'] = float(np.median(warm))
    info['viewprism_warm_p95_s'] = float(np.percentile(warm, 95))
    info['viewprism_stage_median_s'] = {k: float(np.median([s[k] for s in stages])) for k in stages[0]}
    info['capture_stats'] = {k: v for k, v in res['stats'].items() if k != 'seconds'}
    out = tempfile.mkdtemp(prefix='viewprism-bench-')
    opts = vp['writer'].default_options()
    opts['outputs'] = {'depth': ['PNG8', 'EXR'], 'normal': ['PNG8'], 'object_id': ['PNG16'], 'mask': ['PNG8']}
    t0 = time.perf_counter()
    wres = vp['writer'].export_capture(res, opts, out)
    info['encode_write_s'] = time.perf_counter() - t0
    info['files_bytes'] = {n: os.path.getsize(os.path.join(out, n)) for n in wres['written']}
    if a.compare:
        for oid, name in res['id_map'].items():      # sandbox only: lets Cycles' IndexOB match our ids
            bpy.data.objects[name].pass_index = oid
        engines = {}
        for engine in ('BLENDER_EEVEE', 'CYCLES'):
            try:
                bpy.context.scene.render.engine = engine     # add-on engines are not in the static enum
            except TypeError:
                continue
            times = []
            path = None
            for i in range(a.renders):
                t, path = render_passes(engine, out, f'{engine.lower()}_{i}')
                times.append(t)
            engines[engine] = dict(render_s=times, file=path)
        info['render_engines'] = {k: dict(render_s=v['render_s']) for k, v in engines.items()}
        info['cycles_device'] = bpy.context.scene.cycles.device if 'CYCLES' in engines else None
        if 'CYCLES' in engines:
            raw = open(engines['CYCLES']['file'], 'rb').read()
            ch, hdr = vp['exr'].decode(raw)
            names = hdr['channels']
            info['cycles_channels'] = names
            zkey = next(n for n in names if n.endswith('Depth.Z'))
            z = ch[zkey]
            nk = [next(n for n in names if n.endswith(f'Normal.{c}')) for c in 'XYZ']
            nworld = np.stack([ch[k] for k in nk], -1)
            idk = next((n for n in names if n.endswith('IndexOB.X') or n.endswith('Object Index.X')), None)
            ours = res
            fg_c = z < 1e9
            both = eroded(fg_c & ours['mask'], 2)
            dz = np.abs(ours['depth'][both] - z[both])
            rel = dz / z[both]
            view = np.array(request['view_matrix'])
            ncam = nworld @ view[:3, :3].T
            ln = np.linalg.norm(ncam, axis=-1)
            ok_n = both & (ln > 0.5)
            ang = np.degrees(np.arccos(np.clip(np.sum((ncam[ok_n] / ln[ok_n, None]) * ours['normal'][ok_n], -1), -1, 1)))
            cmp = dict(foreground_pixels_ours=int(ours['mask'].sum()), foreground_pixels_cycles=int(fg_c.sum()),
                       mask_disagreement_fraction=float((fg_c != ours['mask']).mean()),
                       interior_pixels=int(both.sum()),
                       depth_abs_err_median=float(np.median(dz)), depth_abs_err_p99=float(np.percentile(dz, 99)),
                       depth_rel_err_max=float(rel.max()), depth_rel_err_p99=float(np.percentile(rel, 99)),
                       normal_angle_deg_median=float(np.median(ang)), normal_angle_deg_p99=float(np.percentile(ang, 99)))
            if idk:
                # Cycles object index was set to (our id) for every object in this sandbox
                cid = np.rint(ch[idk]).astype(np.int64)
                cmp['id_agreement_interior'] = float((cid[both] == ours['object_id'][both]).mean())
            info['cycles_comparison'] = cmp
    info['output_dir'] = out
    viewprism.unregister()
    return info


def run():
    try:
        info = main()
        info['status'] = 'pass'
    except Exception:
        info = dict(status='fail', traceback=traceback.format_exc())
    a.result.write_text(json.dumps(info, indent=2), encoding='utf-8')
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(run, first_interval=1.0)
