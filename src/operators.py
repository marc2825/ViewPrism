import bpy
import gpu
import numpy as np
from . import utils


class RENDER_OT_depth_image(bpy.types.Operator):
    bl_idname = "render.depth_image"
    bl_label = "Render Depth Image"
    bl_description = "Save a depth image from the current 3D view"
    bl_options = { 'REGISTER', 'UNDO' }

    filepath: bpy.props.StringProperty(name="File Path", subtype="FILE_PATH")

    def execute(self, context):
        for area in context.window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if region:
                    width, height = region.width, region.height
                    break
        else:
            self.report({'ERROR'}, "Cannot find VIEW_3D")
            return {'CANCELLED'}

        depth_array = utils.render_depth(context, width, height)
        if depth_array is None:
            self.report({'ERROR'}, "深度画像のレンダリングに失敗しました")
            return {'CANCELLED'}

        # 新規Imageを作成し、深度情報（グレースケール）をRGBAとしてセット
        image = bpy.data.images.new("DepthImage", width=width, height=height, alpha=False)
        pixels = []
        # ※ Blenderのimage.pixelsは下から上にピクセルを並べるので注意
        for y in range(height):
            for x in range(width):
                val = depth_array[y, x]
                # 値は[0,1]であることを想定。必要に応じて正規化してください。
                pixels.extend([val, val, val, 1.0])
        image.pixels = pixels
        image.filepath_raw = self.filepath
        image.file_format = 'PNG'
        image.save()

        self.report({'INFO'}, f"深度画像を {self.filepath} に保存しました")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    


classes = [RENDER_OT_depth_image]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)