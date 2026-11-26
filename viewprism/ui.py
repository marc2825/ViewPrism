"""3D View sidebar (N-panel) UI: passes, size, depth range, preview, output, export."""
import bpy

from . import operators, preview, props, viewport


def _view_size_hint(context, settings):
    try:
        view = viewport.resolve(context)
    except viewport.ViewError:
        return None, False
    if viewport.uses_camera_frame(view, settings):
        r = context.scene.render
        w = round(r.resolution_x * r.resolution_percentage / 100)
        h = round(r.resolution_y * r.resolution_percentage / 100)
        camera = True
    else:
        w, h = view.region.width, view.region.height
        camera = False
    if settings.resolution_mode == 'CUSTOM':
        from .projection import locked_height
        ow = settings.width
        oh = locked_height(ow, w, h) if settings.lock_aspect else settings.height
    else:
        ow, oh = max(1, round(w * settings.scale / 100)), max(1, round(h * settings.scale / 100))
    return (ow, oh), camera


class VIEWPRISM_PT_main(bpy.types.Panel):
    bl_label = 'ViewPrism'
    bl_idname = 'VIEWPRISM_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ViewPrism'

    def draw(self, context):
        props.init_session_settings(context)
        s = props.settings(context)
        layout = self.layout

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(s, 'use_depth', toggle=True)
        row.prop(s, 'use_normal', toggle=True)
        row = col.row(align=True)
        row.prop(s, 'use_object_id', toggle=True)
        row.prop(s, 'use_mask', toggle=True)

        box = layout.column()
        box.use_property_split = True
        box.use_property_decorate = False
        box.prop(s, 'resolution_mode')
        if s.resolution_mode == 'VIEW':
            box.prop(s, 'scale')
        else:
            sub = box.column(align=True)
            sub.prop(s, 'width')
            if not s.lock_aspect:
                sub.prop(s, 'height')
            box.prop(s, 'lock_aspect')
        size, camera = _view_size_hint(context, s)
        if size:
            box.label(text=f"Output {size[0]} x {size[1]} px" + ("  (camera frame)" if camera else ''),
                      icon='OUTLINER_OB_CAMERA' if camera else 'RESTRICT_VIEW_OFF')

        if s.use_depth or s.preview_pass == 'depth':
            dcol = layout.column()
            dcol.use_property_split = True
            dcol.use_property_decorate = False
            dcol.prop(s, 'depth_range')
            if s.depth_range == 'FIXED':
                sub = dcol.column(align=True)
                sub.prop(s, 'depth_near')
                sub.prop(s, 'depth_far')
            dcol.prop(s, 'depth_near_white')

        layout.separator()
        pcol = layout.column(align=True)
        row = pcol.row(align=True)
        row.prop(s, 'preview_pass', text='')
        row.operator('viewprism.preview', text='', icon='FILE_REFRESH')
        if preview.is_showing(context.area):
            row.operator('viewprism.preview_hide', text='', icon='HIDE_ON')
            row = pcol.row(align=True)
            row.prop(s, 'preview_auto', toggle=True, icon='TIME')
            row.prop(s, 'preview_opacity', slider=True)
            if preview.state.message:
                pcol.label(text=preview.state.message, icon='INFO')
        if preview.state.error:
            pcol.label(text=preview.state.error, icon='ERROR')

        layout.separator()
        ocol = layout.column()
        ocol.use_property_split = True
        ocol.use_property_decorate = False
        ocol.prop(s, 'output_dir')
        ocol.prop(s, 'base_name')
        ocol.prop(s, 'numbering')
        if s.numbering == 'NONE':
            ocol.prop(s, 'overwrite')

        row = layout.row(align=True)
        row.scale_y = 1.4
        row.operator('viewprism.export', icon='EXPORT')
        row = layout.row(align=True)
        row.operator('viewprism.export_as', text='Export As...', icon='FILEBROWSER')
        row.operator('viewprism.open_folder', text='', icon='FILE_FOLDER')

        st = operators.status
        if st['text']:
            icon = {'ERROR': 'ERROR', 'WARNING': 'ERROR'}.get(st['level'], 'CHECKMARK')
            box = layout.box()
            col = box.column(align=True)
            for i, line in enumerate(_wrap(st['text'], 42)):
                col.label(text=line, icon=icon if i == 0 else 'BLANK1')
            for w in st['warnings'][:4]:
                for i, line in enumerate(_wrap(w, 42)):
                    col.label(text=line, icon='DOT' if i == 0 else 'BLANK1')


def _wrap(text, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f'{cur} {w}'.strip()
    if cur:
        lines.append(cur)
    return lines or ['']


class VIEWPRISM_PT_formats(bpy.types.Panel):
    bl_label = 'Formats'
    bl_parent_id = 'VIEWPRISM_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ViewPrism'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        s = props.settings(context)
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        for flag, rows in (('use_depth', ('depth_png', 'depth_exr')), ('use_normal', ('normal_png', 'normal_exr')),
                           ('use_object_id', ('id_png', 'id_exr'))):
            col = layout.column(align=True)
            col.active = getattr(s, flag)
            for r in rows:
                col.prop(s, r)
        layout.prop(s, 'exr_compression')
        layout.prop(s, 'write_meta')


class VIEWPRISM_PT_advanced(bpy.types.Panel):
    bl_label = 'Advanced'
    bl_parent_id = 'VIEWPRISM_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ViewPrism'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        s = props.settings(context)
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(s, 'camera_frame')
        layout.prop(s, 'normal_mode')
        layout.prop(s, 'normal_background')
        col = layout.column(heading='Normal PNG', align=True)
        col.prop(s, 'normal_flip_x')
        col.prop(s, 'normal_flip_y')
        layout.prop(s, 'id_mode')
        layout.prop(s, 'depth_background')
        if s.depth_background == 'VALUE':
            layout.prop(s, 'depth_background_value')
        layout.prop(s, 'preview_scale')
        row = layout.row(align=True)
        row.operator('viewprism.settings_save_defaults', text='Save as Defaults', icon='FILE_TICK')
        row.operator('viewprism.settings_load_defaults', text='Load Defaults', icon='LOOP_BACK')


def menu_func(self, context):
    self.layout.separator()
    self.layout.operator('viewprism.export', icon='EXPORT')


classes = (VIEWPRISM_PT_main, VIEWPRISM_PT_formats, VIEWPRISM_PT_advanced)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.VIEW3D_MT_view.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_view.remove(menu_func)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
