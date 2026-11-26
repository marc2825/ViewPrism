"""Invoked only in a fresh Blender process by run.py."""
import argparse
import importlib
import json
from pathlib import Path
import sys
import time
import traceback

import bpy

p = argparse.ArgumentParser()
p.add_argument('--repo', required=True)
p.add_argument('--result', required=True, type=Path)
p.add_argument('--mode', required=True, choices=['background', 'gpu'])
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
sys.path.insert(0, a.repo)
sys.path.insert(0, str(Path(__file__).resolve().parent))


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def write(status, **extra):
    info = {'status': status, 'mode': a.mode, 'blender': bpy.app.version_string, **extra}
    a.result.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding='utf-8')
    print('VIEWPASS_RESULT', info, flush=True)


def registration():
    mod = importlib.import_module('viewpass')
    for _ in range(2):
        mod.register()
        mod.unregister()
    return mod


if a.mode == 'background':
    try:
        check(bpy.app.background, 'expected background mode')
        registration()
        write('pass', checks=['register/unregister twice'])
    except Exception:
        write('fail', traceback=traceback.format_exc())
        raise
else:
    start = time.monotonic()

    def gpu_task():
        # Wait for a real GUI window / 3D region; never use background GPU as a substitute.
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                region = next((r for r in area.regions if r.type == 'WINDOW' and r.width > 0 and r.height > 0), None)
                if region is not None:
                    try:
                        import gpu
                        from gpu_cases import run_cases
                        with bpy.context.temp_override(window=window, area=area, region=region):
                            mod = registration()
                            mod.register()
                            try:
                                capture = importlib.import_module('viewpass.capture').capture
                                checks = run_cases(bpy.context, capture)
                            finally:
                                mod.unregister()
                        platform = {k: getattr(gpu.platform, k)() for k in
                                    ('backend_type_get', 'device_type_get', 'vendor_get', 'renderer_get', 'version_get')
                                    if hasattr(gpu.platform, k)}
                        write('pass', checks=checks, gpu=platform)
                    except Exception:
                        write('fail', traceback=traceback.format_exc())
                    bpy.ops.wm.quit_blender()
                    return None
        if time.monotonic() - start > 30:
            write('fail', reason='No usable VIEW_3D region after 30 seconds')
            bpy.ops.wm.quit_blender()
            return None
        return 0.5

    check(not bpy.app.background, 'GPU tests require GUI')
    bpy.app.timers.register(gpu_task, first_interval=1.0)
