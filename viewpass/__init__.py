"""ViewPass - export pixel-aligned Depth / Normal / Object ID / Mask from the current 3D viewport."""

_modules = ()


def register():
    for m in _modules:
        m.register()


def unregister():
    for m in reversed(_modules):
        m.unregister()
