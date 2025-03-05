import bpy
from . import operators, panel, utils


bl_info = {
    "name": "Depth Renderer",
    "author": "marc",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Depth Renderer",
    "description": "Renders a depth image from the current 3D view",
    "warning": "",
    "support": "TESTING",
    "wiki_url": "https://github.com/marc2825/Blender_Depth_Renderer",
    "tracker_url": "https://github.com/marc2825/Blender_Depth_Renderer/issues",
    "category": "Render"
}


def register():
    operators.register()
    panel.register()

    print("Depth Renderer Enabled!")


def unregister():
    panel.unregister()
    operators.unregister()

    print("Depth Renderer Disabled!")



if __name__ == "__main__":
    register()