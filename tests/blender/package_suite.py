# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the built extension ZIP into an isolated user directory and exercise it in a GUI session.

Started by tests/run_blender_tests.py with BLENDER_USER_RESOURCES pointing at a fresh temporary
directory, so the real user configuration is never touched.
"""
import argparse
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

import bpy

p = argparse.ArgumentParser()
p.add_argument('--repo', required=True)
p.add_argument('--result', required=True, type=Path)
p.add_argument('--zip', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
MODULE = 'bl_ext.user_default.viewprism'


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def enabled():
    import addon_utils
    return addon_utils.check(MODULE)[1]


def view3d():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                return dict(window=window, screen=window.screen, area=area, region=region,
                            space_data=area.spaces.active)
    raise AssertionError('no 3D view')


def export_once(out):
    s = bpy.context.window_manager.viewprism
    s.output_dir, s.base_name = out + os.sep, 'pkg'
    s.use_depth = s.use_normal = s.use_object_id = s.use_mask = True
    with bpy.context.temp_override(**view3d()):
        ret = bpy.ops.viewprism.export()
    check(ret == {'FINISHED'}, f'export returned {ret}')
    return sorted(os.listdir(out))


def steps():
    log = []
    user = bpy.utils.resource_path('USER')
    check(os.environ.get('BLENDER_USER_RESOURCES') and Path(user).resolve() == Path(os.environ['BLENDER_USER_RESOURCES']).resolve(),
          f'user resources not isolated: {user}')
    log.append(f'isolated user dir {user}')
    check(not sys.modules.get('viewprism'), 'repo copy must not be importable/used here')
    ret = bpy.ops.extensions.package_install_files(filepath=a.zip, repo='user_default', enable_on_install=True)
    check(ret == {'FINISHED'}, f'install returned {ret}')
    check(enabled(), 'not enabled after install')
    mod = sys.modules[MODULE]
    check(str(Path(mod.__file__).resolve()).startswith(str(Path(user).resolve())), f'loaded from {mod.__file__}')
    log.append(f'installed + enabled from {Path(mod.__file__).parent.name}')
    bpy.ops.mesh.primitive_monkey_add(location=(0, 0, 0))
    out = tempfile.mkdtemp(prefix='viewprism-pkg-')
    files = export_once(out)
    check(len(files) >= 5 and any(f.endswith('_depth.exr') for f in files), f'files {files}')
    log.append(f'export ok: {len(files)} files')
    prefs = bpy.context.preferences.addons[MODULE].preferences
    check(prefs.defaults.base_name == 'viewprism', 'preferences not available')
    bpy.ops.preferences.addon_disable(module=MODULE)
    check(not enabled() and not hasattr(bpy.types, 'VIEWPRISM_PT_main'), 'disable failed')
    check(not hasattr(bpy.context.window_manager, 'viewprism'), 'settings left after disable')
    log.append('disabled cleanly')
    bpy.ops.preferences.addon_enable(module=MODULE)
    check(enabled() and hasattr(bpy.types, 'VIEWPRISM_PT_main'), 're-enable failed')
    out2 = tempfile.mkdtemp(prefix='viewprism-pkg-')
    export_once(out2)
    log.append('re-enabled and exported again')
    repo_index = next(i for i, r in enumerate(bpy.context.preferences.extensions.repos) if r.module == 'user_default')
    ret = bpy.ops.extensions.package_uninstall(repo_index=repo_index, pkg_id='viewprism')
    check(ret == {'FINISHED'}, f'uninstall returned {ret}')
    check(not enabled() and not hasattr(bpy.types, 'VIEWPRISM_PT_main'), 'still registered after uninstall')
    pkg_dir = Path(user) / 'extensions' / 'user_default' / 'viewprism'
    check(not pkg_dir.exists(), f'package directory left: {pkg_dir}')
    log.append('uninstalled, directory removed')
    return log


def run():
    try:
        detail = steps()
        a.result.write_text(json.dumps(dict(status='pass', blender=bpy.app.version_string,
                                             results=[dict(test='package_lifecycle', status='pass',
                                                           detail='; '.join(detail))]), indent=2), encoding='utf-8')
    except Exception:
        a.result.write_text(json.dumps(dict(status='fail', blender=bpy.app.version_string,
                                             results=[dict(test='package_lifecycle', status='fail',
                                                           traceback=traceback.format_exc())]), indent=2),
                            encoding='utf-8')
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(run, first_interval=1.0)
