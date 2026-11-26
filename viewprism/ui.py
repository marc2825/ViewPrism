# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""3D View sidebar (N panel) UI.

Layout (top to bottom): Passes (one row per pass: export checkbox, file summary, preview eye, settings
popover), Size, Output (folder, name, numbering and the list of files Export will write), the Export
buttons and the result of the last export. Rarely changed options live in two closed sub-panels.
Every setting of a pass is reached from its own row (one place per pass).
"""
import os
import unicodedata

import bpy

from . import operators, preview, props, viewport
from .i18n import iface
from .i18n_data import CONTEXT

DOCS_URL = 'https://github.com/marc2825/ViewPrism#readme'
DOCS_URL_JA = 'https://github.com/marc2825/ViewPrism/blob/main/README.ja.md'
PASS_ROWS = (('depth', 'use_depth', 'VIEWPRISM_PT_depth'), ('normal', 'use_normal', 'VIEWPRISM_PT_normal'),
             ('object_id', 'use_object_id', 'VIEWPRISM_PT_object_id'), ('mask', 'use_mask', None))
FILE_NOTES = {'depth:PNG8': '8-bit', 'depth:PNG16': '16-bit', 'depth:EXR': 'float',
              'normal:PNG8': '8-bit', 'normal:PNG16': '16-bit', 'normal:EXR': 'float',
              'object_id:PNG16': '16-bit', 'object_id:EXR': '32-bit', 'mask:PNG8': '8-bit',
              'meta': 'metadata'}
WRAP = 33          # characters per line in a default-width sidebar (CJK characters count twice)


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


def pass_summary(s, p):
    """Short list of the files a pass writes, e.g. 'PNG 8 + EXR' ('' if none)."""
    if p == 'depth':
        parts = ([f'PNG {s.depth_png[3:]}'] if s.depth_png != 'NONE' else []) + (['EXR'] if s.depth_exr else [])
    elif p == 'normal':
        parts = ([f'PNG {s.normal_png[3:]}'] if s.normal_png != 'NONE' else []) + (['EXR'] if s.normal_exr else [])
    elif p == 'object_id':
        parts = (['PNG 16'] if s.id_png else []) + (['EXR'] if s.id_exr else [])
    else:
        parts = ['PNG 8']
    return ' + '.join(parts)


def text_width(text):
    """Display width in Latin-character units (CJK and other wide characters count twice)."""
    return sum(2 if unicodedata.east_asian_width(ch) in 'WF' else 1 for ch in text)


def wrap(text, width=WRAP):
    """Greedy word wrap by display width; text without spaces (Japanese) is cut where it overflows."""
    lines, cur = [], ''
    for word in text.split(' '):
        while text_width(word) > width:
            if cur:
                lines.append(cur)
                cur = ''
            n, used = 0, 0
            while n < len(word) and used + text_width(word[n]) <= width:
                used += text_width(word[n])
                n += 1
            lines.append(word[:max(1, n)])
            word = word[max(1, n):]
        if cur and text_width(cur) + 1 + text_width(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f'{cur} {word}'.strip()
    if cur:
        lines.append(cur)
    return lines or ['']


def wrap_width(context):
    """Characters that fit next to an icon in the current sidebar width."""
    region = getattr(context, 'region', None)
    ui = context.preferences.system.ui_scale
    if region is None or region.width < 50:
        return WRAP
    return max(16, int((region.width / ui - 56) / 6.8))


def short_folder(path):
    """The last two folders of a path ('…/demo/viewprism/'), which fit in the sidebar."""
    parts = [p for p in os.path.normpath(path).split(os.sep) if p]
    keep = 2 if text_width(os.sep.join(parts[-2:])) <= 22 else 1
    tail = os.sep.join(parts[-keep:])
    return ('…' + os.sep if len(parts) > keep else '') + tail + os.sep


def _labels(col, text, icon='NONE', width=WRAP):
    for i, line in enumerate(wrap(text, width)):
        col.label(text=line, icon=icon if i == 0 else 'BLANK1', translate=False)


class VIEWPRISM_MT_panel_menu(bpy.types.Menu):
    bl_label = 'ViewPrism'
    bl_idname = 'VIEWPRISM_MT_panel_menu'
    bl_translation_context = CONTEXT

    def draw(self, context):
        layout = self.layout
        ja = bpy.app.translations.locale.startswith('ja')
        op = layout.operator('wm.url_open', text=iface('Documentation'), icon='HELP', translate=False)
        op.url = DOCS_URL_JA if ja else DOCS_URL
        layout.separator()
        layout.operator('viewprism.settings_save_defaults', icon='FILE_TICK')
        layout.operator('viewprism.settings_load_defaults', icon='LOOP_BACK')


class VIEWPRISM_PT_main(bpy.types.Panel):
    bl_label = 'ViewPrism'
    bl_idname = 'VIEWPRISM_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ViewPrism'
    bl_translation_context = CONTEXT

    def draw_header_preset(self, context):
        self.layout.menu('VIEWPRISM_MT_panel_menu', text='', icon='DOWNARROW_HLT')

    def draw(self, context):
        props.init_session_settings(context)
        s = props.settings(context)
        layout = self.layout
        self.draw_passes(context, layout, s)
        layout.separator(factor=0.6)
        self.draw_size(context, layout, s)
        layout.separator(factor=0.6)
        self.draw_output(context, layout, s)
        self.draw_export(context, layout, s)

    # -- Passes ------------------------------------------------------------------------------------
    @staticmethod
    def draw_passes(context, layout, s):
        head = layout.row(align=True)
        head.label(text=iface('Passes'), translate=False)
        if preview.is_showing(context.area):
            sub = head.row(align=True)
            sub.alignment = 'RIGHT'
            sub.operator('viewprism.preview', text='', icon='FILE_REFRESH')
            sub.operator('viewprism.preview_hide', text='', icon='PANEL_CLOSE')
        shown = preview.overlay_pass(context.area)
        col = layout.column(align=True)
        for p, flag, popover in PASS_ROWS:
            on = getattr(s, flag)
            row = col.row(align=True)
            split = row.split(factor=0.47, align=True)
            split.prop(s, flag)
            right = split.row(align=True)
            summary = pass_summary(s, p)
            info = right.row(align=True)
            info.alignment = 'RIGHT'
            info.active = on
            info.alert = on and not summary
            info.label(text=summary or iface('no file type'), translate=False)
            eye = right.row(align=True)
            eye.alignment = 'RIGHT'
            op = eye.operator('viewprism.preview_show', text='', icon='HIDE_OFF', depress=shown == p)
            op.pass_name = p
            if popover:
                eye.popover(popover, text='', icon='PREFERENCES')
            else:
                eye.label(text='', icon='BLANK1')

    # -- Size ----------------------------------------------------------------------------------------
    @staticmethod
    def draw_size(context, layout, s):
        layout.label(text=iface('Size'), translate=False)
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(s, 'resolution_mode', expand=True)
        row.prop(s, 'camera_frame', text='', icon='OUTLINER_OB_CAMERA')
        row = col.row(align=True)
        if s.resolution_mode == 'VIEW':
            row.prop(s, 'scale')
        else:
            row.prop(s, 'width')
            if not s.lock_aspect:           # locked: the height follows the view (shown in the line below)
                row.prop(s, 'height')
            row.prop(s, 'lock_aspect', text='', icon='LOCKED' if s.lock_aspect else 'UNLOCKED')
        size, camera = _view_size_hint(context, s)
        if size:
            text = iface('{} × {} px').format(*size)
            if camera:
                text += '  ' + iface('(camera frame)')
            col.label(text=text, icon='OUTLINER_OB_CAMERA' if camera else 'IMAGE_DATA', translate=False)

    # -- Output --------------------------------------------------------------------------------------
    @staticmethod
    def draw_output(context, layout, s):
        layout.label(text=iface('Output'), translate=False)
        col = layout.column(align=True)
        col.prop(s, 'output_dir', text='')
        row = col.row(align=True)
        row.prop(s, 'base_name', text='')
        row.prop(s, 'numbering', text='')
        row = layout.row()
        row.active = s.numbering == 'NONE'
        row.prop(s, 'overwrite')
        plan = operators.planned_files(s)
        width = wrap_width(context)
        box = layout.box()
        bcol = box.column(align=True)
        if plan['error']:
            row = bcol.row()
            row.alert = True
            _labels(row.column(align=True), plan['error'], 'ERROR', width)
            return
        n = len(plan['files'])
        if plan['unsaved']:
            head = iface('{} files; Export will ask for a folder').format(n)
            _labels(bcol, head, 'FILEBROWSER', width)
        else:
            folder = short_folder(plan['directory'])
            bcol.label(text=iface('{} files to {}').format(n, folder), icon='FILE_FOLDER', translate=False)
        clashes = 0
        for key, name, exists in plan['files']:
            row = bcol.row(align=True)
            split = row.split(factor=0.68, align=True)
            if exists and not s.overwrite:
                clashes += 1
                split.alert = True
            split.label(text=name, translate=False)
            note = (iface('replaces') if s.overwrite else iface('exists')) if exists else iface(FILE_NOTES.get(key, ''))
            right = split.row()
            right.alignment = 'RIGHT'
            right.active = exists
            right.label(text=note, translate=False)
        if clashes:
            row = bcol.row()
            row.alert = True
            _labels(row.column(align=True), iface('{} files already exist. Choose "Add Number", turn on Overwrite '
                                                  'or change the name.').format(clashes), 'ERROR', width)

    # -- Export + result -----------------------------------------------------------------------------
    @staticmethod
    def draw_export(context, layout, s):
        n = len(operators.selected_passes(s))
        label = iface('Export 1 Pass') if n == 1 else iface('Export {} Passes').format(n) if n else iface('Export')
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator('viewprism.export', text=label, icon='EXPORT', translate=False)
        row = layout.row(align=True)
        row.operator('viewprism.export_as', icon='FILEBROWSER')
        row.operator('viewprism.open_folder', text='', icon='FOLDER_REDIRECT')
        st = operators.status
        if not st['text']:
            return
        current = st['signature'] is None or st['signature'] == props.signature(s)
        if st['level'] == 'ERROR' and not current:
            return                              # the settings changed: the error may no longer apply
        width = wrap_width(context)
        box = layout.box()
        col = box.column(align=True)
        col.active = current
        icon = {'ERROR': 'CANCEL', 'WARNING': 'ERROR'}.get(st['level'], 'CHECKMARK')
        _labels(col, st['text'] if current else iface('Last export: {}').format(st['text']), icon, width)
        for w in st['warnings'][:4]:
            _labels(col, w, 'DOT', width)
        if len(st['warnings']) > 4:
            col.label(text=iface('{} more in the Info editor').format(len(st['warnings']) - 4), icon='BLANK1',
                      translate=False)


class VIEWPRISM_PT_preview(bpy.types.Panel):
    bl_label = 'Preview'
    bl_idname = 'VIEWPRISM_PT_preview'
    bl_parent_id = 'VIEWPRISM_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ViewPrism'
    bl_options = {'DEFAULT_CLOSED'}
    bl_translation_context = CONTEXT

    def draw(self, context):
        s = props.settings(context)
        layout = self.layout
        showing = preview.is_showing(context.area)
        row = layout.row(align=True)
        row.operator('viewprism.preview', text=iface('Refresh') if showing else iface('Start Preview'),
                     icon='FILE_REFRESH', translate=False)
        sub = row.row(align=True)
        sub.enabled = showing
        sub.operator('viewprism.preview_hide', text=iface('Close'), icon='PANEL_CLOSE', translate=False)
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(s, 'preview_auto')
        col.prop(s, 'preview_thumbnails')
        col.prop(s, 'preview_opacity', slider=True)
        col.prop(s, 'preview_scale')
        info = layout.column(align=True)
        if showing and preview.state.message:
            info.label(text=preview.state.message, icon='INFO', translate=False)
            for w in preview.state.warnings[:3]:
                _labels(info, w, 'DOT', wrap_width(context))
        if preview.state.error:
            row = info.row()
            row.alert = True
            _labels(row.column(align=True), preview.state.error, 'ERROR', wrap_width(context))


class VIEWPRISM_PT_output_details(bpy.types.Panel):
    bl_label = 'Output Details'
    bl_idname = 'VIEWPRISM_PT_output_details'
    bl_parent_id = 'VIEWPRISM_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ViewPrism'
    bl_options = {'DEFAULT_CLOSED'}
    bl_translation_context = CONTEXT

    def draw(self, context):
        s = props.settings(context)
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(s, 'exr_compression')
        col = layout.column(heading=iface('Metadata'), translate=False)
        col.prop(s, 'write_meta', text=iface('Write JSON'), translate=False)
        sub = col.column()
        sub.active = s.write_meta
        sub.prop(s, 'metadata_privacy')


class _PassSettings:
    """Popover with every setting of one pass (opened from the pass row)."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 13
    bl_translation_context = CONTEXT

    def draw(self, context):
        s = props.settings(context)
        layout = self.layout
        layout.label(text=iface(self.title), translate=False)
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        self.draw_settings(col, s)


class VIEWPRISM_PT_depth(_PassSettings, bpy.types.Panel):
    bl_label = 'Depth Settings'
    bl_idname = 'VIEWPRISM_PT_depth'
    title = 'Depth Settings'

    @staticmethod
    def draw_settings(col, s):
        col.prop(s, 'depth_png')
        col.prop(s, 'depth_exr')
        col.separator()
        col.row().prop(s, 'depth_range', expand=True)
        if s.depth_range == 'FIXED':
            sub = col.column(align=True)
            sub.prop(s, 'depth_near')
            sub.prop(s, 'depth_far')
        col.prop(s, 'depth_near_white')
        col.prop(s, 'depth_background')
        if s.depth_background == 'VALUE':
            col.prop(s, 'depth_background_value')


class VIEWPRISM_PT_normal(_PassSettings, bpy.types.Panel):
    bl_label = 'Normal Settings'
    bl_idname = 'VIEWPRISM_PT_normal'
    title = 'Normal Settings'

    @staticmethod
    def draw_settings(col, s):
        col.prop(s, 'normal_png')
        col.prop(s, 'normal_exr')
        col.separator()
        col.prop(s, 'normal_mode')
        col.prop(s, 'normal_background')
        sub = col.column(heading=iface('PNG Axes'), align=True, translate=False)
        sub.prop(s, 'normal_flip_x')
        sub.prop(s, 'normal_flip_y')


class VIEWPRISM_PT_object_id(_PassSettings, bpy.types.Panel):
    bl_label = 'Object ID Settings'
    bl_idname = 'VIEWPRISM_PT_object_id'
    title = 'Object ID Settings'

    @staticmethod
    def draw_settings(col, s):
        col.prop(s, 'id_png')
        col.prop(s, 'id_exr')
        col.separator()
        col.prop(s, 'id_mode')


def menu_func(self, context):
    self.layout.separator()
    self.layout.operator('viewprism.export', icon='EXPORT')


classes = (VIEWPRISM_MT_panel_menu, VIEWPRISM_PT_main, VIEWPRISM_PT_preview, VIEWPRISM_PT_output_details,
           VIEWPRISM_PT_depth, VIEWPRISM_PT_normal, VIEWPRISM_PT_object_id)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.VIEW3D_MT_view.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_view.remove(menu_func)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
