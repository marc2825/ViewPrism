"""ViewPass - export pixel-aligned Depth / Normal / Object ID / Mask from the current 3D viewport.

Pure modules (projection, encode, png, exr, export, writer) do not import bpy, so they can be
unit-tested outside Blender. Blender-facing modules are imported lazily in register().
"""

_modules = []


def _load():
    from . import props, operators, preview, ui
    return [props, operators, preview, ui]


def register():
    global _modules
    mods = _load()
    done = []
    try:
        for m in mods:
            m.register()
            done.append(m)
    except Exception:
        for m in reversed(done):
            m.unregister()
        raise
    _modules = mods
    import bpy
    from . import capture
    capture.remember_windows(bpy.context)


def unregister():
    global _modules
    for m in reversed(_modules):
        m.unregister()
    _modules = []
    try:
        from . import gpu_draw
        gpu_draw.free_resources()
    except ImportError:
        pass
