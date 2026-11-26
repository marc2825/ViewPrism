# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate README images from real ViewPrism output in a sandboxed GUI Blender.

    set BLENDER_USER_RESOURCES=<empty temp dir>   (no recent-files list -> no private names)
    blender --factory-startup --enable-event-simulate --python tools/make_screenshots.py -- --repo . --out docs/images

Use tools/screenshots.py, which sets this up.

Builds a procedural scene (Blender primitives only, no third-party assets), exports the
passes with the ViewPrism operator and takes screenshots of the 3D viewport with the
sidebar, the preview overlay and the thumbnails (English, plus one in Japanese). The scene is saved only
to a temporary folder, so that '//' resolves.
"""
import argparse
import math
import os
import sys
import tempfile
import traceback

import bpy

ap = argparse.ArgumentParser()
ap.add_argument('--repo', required=True)
ap.add_argument('--out', required=True)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
sys.path.insert(0, os.path.abspath(a.repo))
OUT = os.path.abspath(a.out)


def view3d():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                return dict(window=window, screen=window.screen, area=area, region=region,
                            space_data=area.spaces.active)


def scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    ov = view3d()
    with bpy.context.temp_override(**ov):
        bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, 0))
        bpy.ops.mesh.primitive_torus_add(location=(-1.6, 0.4, 0.55), major_radius=0.9, minor_radius=0.32,
                                         rotation=(math.radians(70), 0, math.radians(20)))
        bpy.ops.object.shade_smooth()
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.8, location=(0.9, 0.9, 0.8), segments=64, ring_count=32)
        bpy.ops.object.shade_smooth()
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.9, -1.0, 0.5), rotation=(0, 0, math.radians(30)))
        bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=1.6, location=(-0.2, -1.4, 0.8))
        bpy.ops.mesh.primitive_cone_add(radius1=0.5, depth=1.2, location=(-2.6, -1.6, 0.6))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.12, location=(0, 0, -20))
        pebble = bpy.context.active_object
        pebble.name = 'Pebble'
        pebble.hide_set(True)
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=12, y_subdivisions=6, size=1, location=(0.2, 2.6, 0.12))
        host = bpy.context.active_object
        host.name = 'PebbleScatter'
        host.scale = (6, 2, 1)
        ng = bpy.data.node_groups.new('shot_scatter', 'GeometryNodeTree')
        ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
        m2p = ng.nodes.new('GeometryNodeMeshToPoints')
        oi = ng.nodes.new('GeometryNodeObjectInfo')
        oi.inputs['Object'].default_value = pebble
        oi.inputs['As Instance'].default_value = True
        iop = ng.nodes.new('GeometryNodeInstanceOnPoints')
        ng.links.new(gi.outputs[0], m2p.inputs['Mesh'])
        ng.links.new(m2p.outputs[0], iop.inputs['Points'])
        ng.links.new(oi.outputs['Geometry'], iop.inputs['Instance'])
        ng.links.new(iop.outputs[0], go.inputs[0])
        host.modifiers.new('scatter', 'NODES').node_group = ng
    from mathutils import Euler
    rv3d = ov['region'].data
    rv3d.view_perspective = 'PERSP'
    rv3d.view_location = (0, 0.3, 0.6)
    rv3d.view_rotation = Euler((math.radians(62), 0, math.radians(28))).to_quaternion()
    rv3d.view_distance = 9.5
    rv3d.update()
    space = ov['space_data']
    space.overlay.show_floor = False
    space.overlay.show_axis_x = space.overlay.show_axis_y = False
    space.show_region_ui = True
    space.show_region_toolbar = False
    return ov


def grid_image(stem_dir, stem):
    import numpy as np
    from viewprism import encode, png
    rd = lambda n: png.decode(open(os.path.join(stem_dir, f'{stem}_{n}'), 'rb').read())[0]
    depth = rd('depth.png')[..., 0]
    normal = rd('normal.png')
    ids = rd('id.png')[..., 0]
    mask = rd('mask.png')[..., 0]
    tiles = [np.repeat(depth[..., None], 3, -1), normal,
             (encode.id_colors(ids) * 255).astype(np.uint8),            # display colours for the README
             np.repeat(mask[..., None], 3, -1)]
    h, w = depth.shape
    gap = 6
    out = np.full((2 * h + gap, 2 * w + gap, 3), 255, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, 2)
        out[r * (h + gap):r * (h + gap) + h, c * (w + gap):c * (w + gap) + w] = t
    with open(os.path.join(OUT, 'passes_grid.png'), 'wb') as fh:
        fh.write(png.encode(out))


def ui_region(area):
    return next(r for r in area.regions if r.type == 'UI')


def steps():
    """Generator driven by a timer so simulated events get processed between steps."""
    assert os.environ.get('BLENDER_USER_RESOURCES'), 'run with an isolated BLENDER_USER_RESOURCES'
    os.makedirs(OUT, exist_ok=True)
    import viewprism
    viewprism.register()
    ov = scene()
    win = ov['window']
    win.event_simulate(type='ESC', value='PRESS')          # dismiss the splash screen
    win.event_simulate(type='ESC', value='RELEASE')
    yield 0.5
    s = bpy.context.window_manager.viewprism
    tmp = tempfile.mkdtemp(prefix='viewprism-shots-')
    # Save the throwaway scene in a temp folder so the default '//viewprism/' folder resolves.
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, 'demo.blend'), check_existing=False)
    yield 0.3
    s.output_dir, s.base_name, s.numbering = '//viewprism/', 'shot', 'AUTO'
    s.use_depth = s.use_normal = s.use_object_id = s.use_mask = True
    s.resolution_mode, s.width, s.lock_aspect = 'CUSTOM', 640, True
    s.id_mode = 'INSTANCER'
    with bpy.context.temp_override(**ov):
        assert bpy.ops.viewprism.export() == {'FINISHED'}
    grid_image(os.path.join(tmp, 'viewprism'), 'shot_0001')
    for ob in bpy.context.scene.objects:
        ob.select_set(False)
    # Click the ViewPrism sidebar tab (tab position is found by scanning the tab strip).
    ui = ui_region(ov['area'])
    x = ui.x + ui.width - 9
    for y in range(ui.y + ui.height - 20, ui.y + ui.height - 400, -12):
        win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x, y=y)
        win.event_simulate(type='LEFTMOUSE', value='PRESS', x=x, y=y)
        win.event_simulate(type='LEFTMOUSE', value='RELEASE', x=x, y=y)
        yield 0.15
        if ui.active_panel_category == 'ViewPrism':
            break
    assert ui.active_panel_category == 'ViewPrism', f'tab not activated: {ui.active_panel_category}'
    cx, cy = ov['region'].x + 300, ov['region'].y + 300       # park the mouse in the viewport
    win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=cx, y=cy)
    yield 0.3
    s.preview_scale = 100

    def shoot(fname):
        ui.tag_redraw()
        ov['area'].tag_redraw()
        yield 0.5
        with bpy.context.temp_override(**ov):
            bpy.ops.screen.screenshot_area(filepath=os.path.join(OUT, fname))
    # Large overlay of one pass + the four thumbnails (the eye button of that pass).
    for pass_name, fname in (('depth', 'ui_preview_depth.png'), ('normal', 'ui_preview_normal.png')):
        with bpy.context.temp_override(**ov):
            bpy.ops.viewprism.preview_show(pass_name=pass_name)
        yield from shoot(fname)
    # Same eye again: overlay off, thumbnails stay -> the panel with the file list and the result.
    with bpy.context.temp_override(**ov):
        bpy.ops.viewprism.preview_show(pass_name='normal')
    yield from shoot('ui_panel.png')
    # Japanese interface (README.ja).
    view = bpy.context.preferences.view
    view.language, view.use_translate_interface = 'ja_JP', True
    with bpy.context.temp_override(**ov):
        bpy.ops.viewprism.preview_show(pass_name='normal')
    yield from shoot('ui_preview_normal_ja.png')
    view.language = 'en_US'
    with bpy.context.temp_override(**ov):
        bpy.ops.viewprism.preview_hide()
    viewprism.unregister()
    print('SHOTS OK', OUT)


_gen = None


def run():
    global _gen
    try:
        if _gen is None:
            _gen = steps()
        return next(_gen)
    except StopIteration:
        pass
    except Exception:
        traceback.print_exc()
        print('SHOTS FAIL')
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(run, first_interval=1.5)
