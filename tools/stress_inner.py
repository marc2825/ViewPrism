# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resource stress run inside a sandboxed GUI Blender (started by tools/stress.py).

Measures capture/export time and process peak memory at 1080p / 4K / 8K, repeated large captures
with and without redraws, a high-instance scene, preview responsiveness and recovery after an
injected GPU failure. Procedural scenes only; nothing is saved.
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

ap = argparse.ArgumentParser()
ap.add_argument('--repo', required=True)
ap.add_argument('--result', required=True, type=Path)
ap.add_argument('--sizes', default='1920x1080,3840x2160,7680x4320')
ap.add_argument('--instances', type=int, default=40000)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
sys.path.insert(0, a.repo)


def memory():
    """(current, peak) process memory in bytes: Windows private bytes, Linux RSS / max RSS."""
    if os.name == 'nt':
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
        k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.PagefileUsage, pmc.PeakPagefileUsage
    import resource
    cur = 0
    with open('/proc/self/status') as fh:
        for line in fh:
            if line.startswith('VmRSS:'):
                cur = int(line.split()[1]) * 1024
    return cur, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def view3d():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                return dict(window=window, screen=window.screen, area=area, region=region,
                            space_data=area.spaces.active)


def scatter(name, src, grid, size):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=grid, y_subdivisions=grid, size=size, location=(0, 0, 0.3))
    host = bpy.context.active_object
    host.name = name
    ng = bpy.data.node_groups.new(name + '_gn', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
    m2p = ng.nodes.new('GeometryNodeMeshToPoints')
    oi = ng.nodes.new('GeometryNodeObjectInfo')
    oi.inputs['Object'].default_value = src
    oi.inputs['As Instance'].default_value = True
    iop = ng.nodes.new('GeometryNodeInstanceOnPoints')
    ng.links.new(gi.outputs[0], m2p.inputs['Mesh'])
    ng.links.new(m2p.outputs[0], iop.inputs['Points'])
    ng.links.new(oi.outputs['Geometry'], iop.inputs['Instance'])
    ng.links.new(iop.outputs[0], go.inputs[0])
    host.modifiers.new('scatter', 'NODES').node_group = ng
    return host


def build(ov, instances):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    with bpy.context.temp_override(**ov):
        bpy.ops.mesh.primitive_plane_add(size=60)
        for i in range(20):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=0.9,
                                                 location=((i % 5) * 2.4 - 5, (i // 5) * 2.4 - 4, 0.9))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.08, location=(0, 0, -50))
        pebble = bpy.context.active_object
        pebble.hide_set(True)
        grid = max(2, int(math.sqrt(instances)))
        scatter('Scatter', pebble, grid, 40)
    rv3d = ov['region'].data
    rv3d.view_perspective = 'PERSP'
    rv3d.view_distance = 30
    rv3d.view_rotation = (0.82, 0.42, 0.18, 0.35)
    rv3d.update()
    bpy.context.view_layer.update()
    return grid * grid


def run():
    import viewprism
    from viewprism import capture as cap, gpu_draw, writer, viewport, preview
    viewprism.register()
    ov = view3d()
    info = dict(blender=bpy.app.version_string)
    import gpu
    info['gpu'] = {k: getattr(gpu.platform, k)() for k in ('backend_type_get', 'renderer_get', 'version_get')}
    n_inst = build(ov, a.instances)
    info['instances'] = n_inst
    s = bpy.context.window_manager.viewprism
    s.use_depth = s.use_normal = s.use_object_id = s.use_mask = True

    def capture_at(w, h):
        with bpy.context.temp_override(**ov):
            view = viewport.resolve(bpy.context)
            s.resolution_mode, s.width, s.height, s.lock_aspect = 'CUSTOM', w, h, False
            req, src = viewport.build_request(view, bpy.context.scene, bpy.context.evaluated_depsgraph_get(), s,
                                              ['depth', 'normal', 'object_id', 'mask'])
            t0 = time.perf_counter()
            res = cap.capture(bpy.context, req)
            return res, src, time.perf_counter() - t0

    out_dir = tempfile.mkdtemp(prefix='viewprism-stress-')
    rows = []
    for size in a.sizes.split(','):
        w, h = (int(v) for v in size.split('x'))
        base_cur, _ = memory()
        res, src, t_cap = capture_at(w, h)
        cur_after_cap, peak_cap = memory()
        opts = writer.default_options()
        opts['outputs'] = {'depth': ['PNG16', 'EXR'], 'normal': ['PNG8'], 'object_id': ['PNG16'], 'mask': ['PNG8']}
        opts['base_name'] = f'stress_{w}x{h}'
        t0 = time.perf_counter()
        wres = writer.export_capture(res, opts, out_dir)
        t_exp = time.perf_counter() - t0
        cur_after_exp, peak_exp = memory()
        rows.append(dict(size=[w, h], megapixels=round(w * h / 1e6, 2), capture_s=round(t_cap, 3),
                         export_s=round(t_exp, 3), stages_s=res['stats']['seconds'], triangles=res['stats']['triangles'],
                         failed=[f.code for f in wres['failed']],
                         process_mb=dict(before=round(base_cur / 1e6), after_capture=round(cur_after_cap / 1e6),
                                         peak_after_capture=round(peak_cap / 1e6), after_export=round(cur_after_exp / 1e6),
                                         peak_after_export=round(peak_exp / 1e6))))
        print('STRESS', rows[-1], flush=True)
        del res
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    info['sizes'] = rows
    # repeated large captures (4K) without and with redraws
    rep = {}
    for mode in ('no_redraw', 'redraw'):
        mem0 = memory()[0]
        mems, times = [], []
        for i in range(8):
            res, _src, t = capture_at(3840, 2160)
            del res
            times.append(t)
            if mode == 'redraw':
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            mems.append(memory()[0])
        rep[mode] = dict(capture_s_median=round(float(np.median(times)), 3),
                         private_mb=[round((m - mem0) / 1e6) for m in mems])
        print('STRESS repeat', mode, rep[mode], flush=True)
    info['repeat_4k'] = rep
    # preview responsiveness at the default preview scale (50 % of the region), without and with the
    # four-pass thumbnails, plus the re-encode cost of a display-setting change
    s.preview_scale = 50
    info['preview'] = dict(region=[ov['region'].width, ov['region'].height])
    for thumbs in (False, True):
        s.preview_thumbnails = thumbs
        pt, rt = [], []
        for i in range(7):
            with bpy.context.temp_override(**ov):
                view = viewport.resolve(bpy.context)
                t0 = time.perf_counter()
                preview.refresh(bpy.context, view)
                pt.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            preview._rebuild_texture(s)
            rt.append(time.perf_counter() - t0)
        key = 'thumbnails_on' if thumbs else 'thumbnails_off'
        info['preview'][key] = dict(size=list(preview.state.size),
                                    refresh_s_median=round(float(np.median(pt)), 3),
                                    refresh_s_max=round(max(pt), 3),
                                    reencode_ms_median=round(float(np.median(rt)) * 1000, 1))
        preview.clear()
    print('STRESS preview', info['preview'], flush=True)
    # recovery after an injected GPU allocation failure at 4K
    real = gpu_draw._get_targets

    def boom(w, h):
        raise RuntimeError('injected GPU allocation failure')
    gpu_draw._get_targets = boom
    try:
        capture_at(3840, 2160)
        info['recovery'] = 'failure was not raised'
    except Exception as exc:
        info['recovery_error'] = f'{type(exc).__name__}: {exc}'
    finally:
        gpu_draw._get_targets = real
    res, _src, t = capture_at(3840, 2160)
    info['recovery'] = dict(capture_after_failure_s=round(t, 3), foreground=int(res['mask'].sum()) > 0)
    viewprism.unregister()
    return info


def main():
    try:
        info = run()
        info['status'] = 'pass'
    except Exception:
        info = dict(status='fail', traceback=traceback.format_exc())
    a.result.write_text(json.dumps(info, indent=2), encoding='utf-8')
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(main, first_interval=1.0)
