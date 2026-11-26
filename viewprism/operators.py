# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operators. Every capture goes through capture.capture() - the same entry point as tests."""
import os
import time

import bpy
from bpy.props import StringProperty

from . import capture as cap
from . import export, preview, props, resources, viewport, writer
from .encode import EncodeError
from .projection import ProjectionError

VERSION = '0.2.0'
_ERRORS = (viewport.ViewError, cap.CaptureError, export.ExportError, EncodeError, ProjectionError, OSError)

# Last action, shown in the panel (session only).
status = {'text': '', 'level': 'INFO', 'warnings': [], 'time': 0.0}


def _set_status(text, level='INFO', warnings=()):
    status.update(text=text, level=level, warnings=list(warnings), time=time.time())


def selected_passes(settings):
    return [p for p, on in (('depth', settings.use_depth), ('normal', settings.use_normal),
                            ('object_id', settings.use_object_id), ('mask', settings.use_mask)) if on]


def output_formats(settings):
    out = {}
    if settings.use_depth:
        out['depth'] = ([settings.depth_png] if settings.depth_png != 'NONE' else []) + (['EXR'] if settings.depth_exr else [])
    if settings.use_normal:
        out['normal'] = ([settings.normal_png] if settings.normal_png != 'NONE' else []) + (['EXR'] if settings.normal_exr else [])
    if settings.use_object_id:
        out['object_id'] = (['PNG16'] if settings.id_png else []) + (['EXR'] if settings.id_exr else [])
    if settings.use_mask:
        out['mask'] = ['PNG8']
    empty = [p for p, f in out.items() if not f]
    if empty:
        raise export.ExportError(f'no file format enabled for: {", ".join(empty)} (see Formats)')
    if not out:
        raise export.ExportError('select at least one pass')
    return out


def writer_options(settings, source, *, base_name=None, numbering=None):
    bg = settings.depth_background
    return {
        'outputs': output_formats(settings),
        'depth': {'range': settings.depth_range, 'near': settings.depth_near, 'far': settings.depth_far,
                  'near_white': settings.depth_near_white,
                  'background': settings.depth_background_value if bg == 'VALUE' else bg},
        'normal': {'background': (0.5, 0.5, 1.0) if settings.normal_background == 'FLAT' else (0.0, 0.0, 0.0),
                   'flip_x': settings.normal_flip_x, 'flip_y': settings.normal_flip_y},
        'exr': {'compression': settings.exr_compression},
        'base_name': settings.base_name if base_name is None else base_name,
        'numbering': settings.numbering if numbering is None else numbering,
        'overwrite': settings.overwrite, 'meta': settings.write_meta,
        'privacy': settings.metadata_privacy.lower(),
        'source': source, 'version': VERSION,
    }


def output_directory(path):
    path = (path or '').strip()
    if not path:
        raise export.ExportError('choose an output folder')
    if path.startswith('//') and not bpy.data.filepath:
        raise export.ExportError('the .blend file is not saved, so "//" has no location: '
                                 'save the file or choose an absolute folder (Export As...)')
    return os.path.normpath(bpy.path.abspath(path))


def capture_view(context, view, settings, request=None, source=None):
    passes = selected_passes(settings)
    if not passes:
        raise export.ExportError('select at least one pass')
    if request is None:
        request, source = viewport.build_request(view, context.scene, context.evaluated_depsgraph_get(),
                                                 settings, sorted(set(passes) | {'mask'}, key=cap.PASSES.index))
    cap.validate_request(request)          # size limits first, so their message wins over the memory one
    try:                                   # capture + export peak, checked before any GPU work
        mem = resources.check(request['width'], request['height'], export=True)
    except resources.ResourceError as exc:
        raise cap.ResourceLimitError(str(exc)) from exc
    with context.temp_override(**view.override()):
        result = cap.capture(bpy.context, request, memory_checked=True)
    if mem['warning']:
        result['warnings'].append(mem['warning'])
        result.setdefault('warnings_anonymous', []).append(mem['warning'])
    if getattr(view.rv3d, 'use_clip_planes', False):
        msg = 'the viewport clipping region (Alt+B) is not applied to the export'
        result['warnings'].append(msg)
        result.setdefault('warnings_anonymous', []).append(msg)
    return result, request, source


def _finish(op, result, res, request):
    n_ok, failed = len(res['written']), res['failed']
    ms = result['stats']['seconds']['total'] * 1000
    size = f"{request['width']}x{request['height']}"
    for w in result['warnings']:
        op.report({'WARNING'}, f'ViewPrism: {w}')
    if failed:
        for name, err in failed:
            op.report({'ERROR'}, f'ViewPrism: could not write {name}: {err}')
        _set_status(f"{len(failed)} of {n_ok + len(failed)} files failed ({res['stem']})", 'ERROR',
                    result['warnings'] + [f'{n}: {e}' for n, e in failed])
        return {'CANCELLED'}
    text = f"Saved {n_ok} files as {res['stem']}_*  ({size}, capture {ms:.0f} ms)"
    op.report({'INFO'}, f'ViewPrism: {text}')
    _set_status(text, 'WARNING' if result['warnings'] else 'INFO', result['warnings'])
    return {'FINISHED'}


def _fail(op, exc):
    msg = str(exc) or type(exc).__name__
    op.report({'ERROR'}, f'ViewPrism: {msg}')
    _set_status(msg, 'ERROR')
    return {'CANCELLED'}


class VIEWPRISM_OT_export(bpy.types.Operator):
    bl_idname = 'viewprism.export'
    bl_label = 'Export Passes'
    bl_description = ('Capture the selected passes from this 3D viewport and save them to the output folder. '
                      'Nothing in the scene is changed')
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        settings = props.settings(context)
        if settings.output_dir.strip().startswith('//') and not bpy.data.filepath:
            # Unsaved file + relative folder: ask for a folder instead of failing.
            return bpy.ops.viewprism.export_as('INVOKE_DEFAULT')
        return self.execute(context)

    def execute(self, context):
        settings = props.settings(context)
        t0 = time.perf_counter()
        try:
            view = viewport.resolve(context)
            directory = output_directory(settings.output_dir)
            result, request, source = capture_view(context, view, settings)
            options = writer_options(settings, source)
            res = writer.export_capture(result, options, directory)
        except _ERRORS as exc:
            return _fail(self, exc)
        res['seconds'] = time.perf_counter() - t0
        return _finish(self, result, res, request)


class VIEWPRISM_OT_export_as(bpy.types.Operator):
    bl_idname = 'viewprism.export_as'
    bl_label = 'Export Passes As...'
    bl_description = 'Choose a folder and base name, then export the selected passes from this viewport'
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    filter_glob: StringProperty(default='*.png;*.exr;*.json', options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        settings = props.settings(context)
        try:
            view = viewport.resolve(context)
            output_formats(settings)
            # Freeze the view *before* the file browser takes over the context.
            passes = sorted(set(selected_passes(settings)) | {'mask'}, key=cap.PASSES.index)
            self._request, self._source = viewport.build_request(
                view, context.scene, context.evaluated_depsgraph_get(), settings, passes)
            self._pointers = view.pointers()
        except _ERRORS as exc:
            return _fail(self, exc)
        try:
            start = output_directory(settings.output_dir)
        except export.ExportError:
            start = os.path.expanduser('~')
        self.filepath = os.path.join(start, settings.base_name)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = props.settings(context)
        if not getattr(self, '_pointers', None):
            return _fail(self, viewport.ViewError('Export As must be started from a 3D Viewport'))
        directory, name = os.path.split(bpy.path.abspath(self.filepath))
        stem = name
        for ext in ('.png', '.exr', '.json'):
            if stem.lower().endswith(ext):
                stem = stem[:-len(ext)]
        for suffix in ('_depth', '_normal', '_id', '_mask', '_meta'):
            if stem.endswith(suffix):
                stem = stem[:-len(suffix)]
        try:
            view = viewport.find(self._pointers)
            result, request, source = capture_view(context, view, settings, self._request, self._source)
            res = writer.export_capture(result, writer_options(settings, source, base_name=stem,
                                                               numbering='NONE'), directory)
        except _ERRORS as exc:
            return _fail(self, exc)
        settings.output_dir = directory + os.sep
        settings.base_name = stem
        return _finish(self, result, res, request)


class VIEWPRISM_OT_preview(bpy.types.Operator):
    bl_idname = 'viewprism.preview'
    bl_label = 'Refresh Preview'
    bl_description = 'Capture a display-only preview of the chosen pass over this viewport'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        try:
            view = viewport.resolve(context)
            result = preview.refresh(context, view)
        except _ERRORS as exc:
            return _fail(self, exc)
        for w in result['warnings']:
            self.report({'WARNING'}, f'ViewPrism: {w}')
        return {'FINISHED'}


class VIEWPRISM_OT_preview_hide(bpy.types.Operator):
    bl_idname = 'viewprism.preview_hide'
    bl_label = 'Hide Preview'
    bl_description = 'Remove the preview overlay and free its memory'
    bl_options = {'REGISTER'}

    def execute(self, context):
        props.settings(context).preview_auto = False
        preview.clear()
        return {'FINISHED'}


class VIEWPRISM_OT_open_folder(bpy.types.Operator):
    bl_idname = 'viewprism.open_folder'
    bl_label = 'Open Output Folder'
    bl_description = 'Open the output folder in the file manager'
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            directory = output_directory(props.settings(context).output_dir)
        except export.ExportError as exc:
            return _fail(self, exc)
        if not os.path.isdir(directory):
            return _fail(self, export.ExportError('the output folder does not exist yet'))
        bpy.ops.wm.path_open(filepath=directory)
        return {'FINISHED'}


class VIEWPRISM_OT_settings_save_defaults(bpy.types.Operator):
    bl_idname = 'viewprism.settings_save_defaults'
    bl_label = 'Save Current as Defaults'
    bl_description = 'Store the current session settings in the add-on preferences'
    bl_options = {'REGISTER'}

    def execute(self, context):
        prefs = props.preferences(context)
        if prefs is None:
            return _fail(self, export.ExportError('add-on preferences are not available'))
        props.copy_settings(props.settings(context), prefs.defaults)
        context.preferences.is_dirty = True
        self.report({'INFO'}, 'ViewPrism: defaults saved to preferences')
        return {'FINISHED'}


class VIEWPRISM_OT_settings_load_defaults(bpy.types.Operator):
    bl_idname = 'viewprism.settings_load_defaults'
    bl_label = 'Load Defaults'
    bl_description = 'Reset the session settings to the stored defaults'
    bl_options = {'REGISTER'}

    def execute(self, context):
        prefs = props.preferences(context)
        if prefs is None:
            return _fail(self, export.ExportError('add-on preferences are not available'))
        props.copy_settings(prefs.defaults, props.settings(context))
        return {'FINISHED'}


classes = (VIEWPRISM_OT_export, VIEWPRISM_OT_export_as, VIEWPRISM_OT_preview, VIEWPRISM_OT_preview_hide,
           VIEWPRISM_OT_open_folder, VIEWPRISM_OT_settings_save_defaults, VIEWPRISM_OT_settings_load_defaults)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
