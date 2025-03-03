import bpy

class VIEW3D_PT_depth_panel(bpy.types.Panel):
    bl_label = "Depth Renderer"
    bl_idname = "VIEW3D_PT_depth_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Depth'

    def draw(self, context):
        layout = self.layout
        layout.operator("render.depth_image", text="深度画像を保存")

classes = [VIEW3D_PT_depth_panel]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
