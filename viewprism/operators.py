# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operators. Every capture goes through capture.capture() - the same entry point as tests."""
import os
import sys
import time

import bpy
from bpy.props import EnumProperty, StringProperty

from . import capture as cap
from . import export, preview, props, resources, viewport, writer
from .encode import EncodeError
from .i18n import iface, rpt
from .i18n_data import CONTEXT
from .projection import ProjectionError

VERSION = '0.3.0'
_ERRORS = (viewport.ViewError, cap.CaptureError, export.ExportError, EncodeError, ProjectionError, OSError)
PASS_LABELS = {'depth': 'Depth', 'normal': 'Normal', 'object_id': 'Object ID', 'mask': 'Mask'}

# Last export, shown in the panel (session only). `signature` = the settings it was made with, so the
# panel can tell when the shown result no longer matches the current settings.
status = {'text': '', 'level': 'INFO', 'warnings': [], 'time': 0.0, 'signature': None}


def _set_status(text, level='INFO', warnings=(), settings=None):
    status.update(text=text, level=level, warnings=list(warnings), time=time.time(),
                  signature=props.signature(settings) if settings is not None else None)


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
        names = ', '.join(iface(PASS_LABELS[p]) for p in empty)
        raise export.ExportError(iface('No file type is selected for {}. Choose PNG or EXR in the settings of '
                                       'that pass.').format(names))
    if not out:
        raise export.ExportError(iface('Select at least one pass to export.'))
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


class UnsavedBlendError(export.ExportError):
    pass


def output_directory(path):
    path = (path or '').strip()
    if not path:
        raise export.ExportError(iface('Choose an output folder.'))
    if path.startswith('//') and not bpy.data.filepath:
        raise UnsavedBlendError(iface('The .blend file is not saved, so "//" has no location. Save the file or '
                                      'choose a folder with Export As.'))
    return os.path.normpath(bpy.path.abspath(path))


# ----------------------------------------------------------------------------- what Export will write

_plan_cache = {'key': None, 'time': 0.0, 'value': None}
_PLAN_TTL = 1.0         # seconds; the panel redraws often, the folder is listed at most once per second
_CASE_INSENSITIVE = os.name == 'nt' or sys.platform == 'darwin'


def invalidate_plan():
    _plan_cache.update(key=None, value=None)


def planned_files(settings):
    """Predict what Export would write now, without writing or reserving anything.

    Returns dict(files=[(key, name, exists)], directory, stem, error, unsaved). `exists` marks a file
    that is already in the folder (only possible with Name Only). The folder is listed once and the
    result cached briefly, so the panel stays fast on slow or network drives.
    """
    out = dict(files=[], directory=None, stem=None, error=None, unsaved=False)
    try:
        items = export.output_items(output_formats(settings))
        base = export.sanitize_stem(settings.base_name)
    except export.ExportError as exc:
        out['error'] = str(exc)
        return out
    numbering, meta = settings.numbering, settings.write_meta
    try:
        directory = output_directory(settings.output_dir)
    except UnsavedBlendError:
        stem = f'{base}_0001' if numbering == 'AUTO' else base
        out.update(unsaved=True, stem=stem, files=[(k, n, False) for k, n in export.file_names(stem, items, meta)])
        return out
    except export.ExportError as exc:
        out['error'] = str(exc)
        return out
    key = (directory, base, numbering, meta, tuple(items))
    now = time.monotonic()
    if _plan_cache['key'] == key and now - _plan_cache['time'] < _PLAN_TTL:
        return _plan_cache['value']
    try:
        present = set(os.listdir(directory)) if os.path.isdir(directory) else set()
    except OSError:
        present = set()
    if _CASE_INSENSITIVE:
        present = {n.casefold() for n in present}

    def exists(path):
        name = os.path.basename(path)
        return (name.casefold() if _CASE_INSENSITIVE else name) in present
    try:
        plan = export.plan(directory, base, items, numbering=numbering, overwrite=True, meta=meta,
                           exists=exists, reserve=False)
        out.update(directory=directory, stem=plan['stem'],
                   files=[(k, n, exists(p)) for k, n, p in plan['files']])
    except export.ExportError as exc:
        out.update(directory=directory, error=str(exc))
    _plan_cache.update(key=key, time=now, value=out)
    return out


# ----------------------------------------------------------------------------- capture + export

def capture_view(context, view, settings, request=None, source=None):
    passes = selected_passes(settings)
    if not passes:
        raise export.ExportError(iface('Select at least one pass to export.'))
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


def _finish(op, result, res, request, settings):
    invalidate_plan()
    n_ok, failed = len(res['written']), res['failed']
    ms = result['stats']['seconds']['total'] * 1000
    size = f"{request['width']} × {request['height']}"
    for w in result['warnings']:
        op.report({'WARNING'}, f'ViewPrism: {w}')
    if failed:
        for name, err in failed:
            op.report({'ERROR'}, rpt('ViewPrism: could not write {}: {}').format(name, err))
        _set_status(iface('{} of {} files could not be written ({}).').format(len(failed), n_ok + len(failed),
                                                                            res['stem']), 'ERROR',
                    result['warnings'] + [f'{n}: {e}' for n, e in failed], settings)
        return {'CANCELLED'}
    text = iface('Saved {} files as {}_* ({} px, {:.0f} ms).').format(n_ok, res['stem'], size, ms)
    op.report({'INFO'}, f'ViewPrism: {text}')
    _set_status(text, 'WARNING' if result['warnings'] else 'INFO', result['warnings'], settings)
    return {'FINISHED'}


def _message(exc):
    if isinstance(exc, export.CollisionError):
        names = exc.names
        shown = ', '.join(names[:2]) + (', …' if len(names) > 2 else '')
        return iface('{} files with these names already exist ({}). Choose "Add Number", turn on Overwrite or '
                     'change the name.').format(len(names), shown)
    return str(exc) or type(exc).__name__


def _fail(op, exc, settings=None):
    """Report an error. With settings (export operators) it also becomes the panel's status line."""
    msg = _message(exc)
    op.report({'ERROR'}, f'ViewPrism: {msg}')
    if settings is not None:
        _set_status(msg, 'ERROR', (), settings)
    return {'CANCELLED'}


def _fail_preview(op, exc):
    msg = _message(exc)
    op.report({'ERROR'}, f'ViewPrism: {msg}')
    preview.state.error = msg
    return {'CANCELLED'}


class _WaitCursor:
    def __init__(self, context):
        self.window = getattr(context, 'window', None)

    def __enter__(self):
        if self.window is not None:
            self.window.cursor_modal_set('WAIT')

    def __exit__(self, *exc):
        if self.window is not None:
            self.window.cursor_modal_restore()


def _export_poll(cls, context):
    if context.area is None or context.area.type != 'VIEW_3D':
        return False
    try:
        output_formats(props.settings(context))
    except export.ExportError as exc:
        cls.poll_message_set(str(exc))
        return False
    return True


class VIEWPRISM_OT_export(bpy.types.Operator):
    bl_idname = 'viewprism.export'
    bl_label = 'Export Passes'
    bl_description = ('Capture the selected passes from this 3D viewport and save them to the output folder. '
                      'Nothing in the scene is changed')
    bl_translation_context = CONTEXT
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        if not _export_poll(cls, context):
            return False
        settings = props.settings(context)
        if settings.numbering == 'NONE' and not settings.overwrite:
            clash = [n for _k, n, exists in planned_files(settings)['files'] if exists]
            if clash:                       # shown in the file list; prevent the error instead of reporting it
                cls.poll_message_set(_message(export.CollisionError(clash)))
                return False
        return True

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
            with _WaitCursor(context):
                view = viewport.resolve(context)
                directory = output_directory(settings.output_dir)
                result, request, source = capture_view(context, view, settings)
                options = writer_options(settings, source)
                res = writer.export_capture(result, options, directory)
        except _ERRORS as exc:
            return _fail(self, exc, settings)
        res['seconds'] = time.perf_counter() - t0
        return _finish(self, result, res, request, settings)


class VIEWPRISM_OT_export_as(bpy.types.Operator):
    bl_idname = 'viewprism.export_as'
    bl_label = 'Export As…'
    bl_description = 'Choose a folder and base name, then export the selected passes from this viewport'
    bl_translation_context = CONTEXT
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    filter_glob: StringProperty(default='*.png;*.exr;*.json', options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return _export_poll(cls, context)

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
            return _fail(self, exc, settings)
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
            return _fail(self, viewport.ViewError(iface('Export As must be started from a 3D Viewport.')), settings)
        directory, name = os.path.split(bpy.path.abspath(self.filepath))
        stem = name
        for ext in ('.png', '.exr', '.json'):
            if stem.lower().endswith(ext):
                stem = stem[:-len(ext)]
        for suffix in ('_depth', '_normal', '_id', '_mask', '_meta'):
            if stem.endswith(suffix):
                stem = stem[:-len(suffix)]
        try:
            with _WaitCursor(context):
                view = viewport.find(self._pointers)
                result, request, source = capture_view(context, view, settings, self._request, self._source)
                res = writer.export_capture(result, writer_options(settings, source, base_name=stem,
                                                                   numbering='NONE'), directory)
        except _ERRORS as exc:
            return _fail(self, exc, settings)
        settings.output_dir = directory + os.sep
        settings.base_name = stem
        return _finish(self, result, res, request, settings)


class VIEWPRISM_OT_preview(bpy.types.Operator):
    bl_idname = 'viewprism.preview'
    bl_label = 'Refresh Preview'
    bl_description = 'Capture the preview again from this viewport (display only, nothing is saved)'
    bl_translation_context = CONTEXT
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        try:
            view = viewport.resolve(context)
            result = preview.refresh(context, view)
        except _ERRORS as exc:
            return _fail_preview(self, exc)
        for w in result['warnings']:
            self.report({'WARNING'}, f'ViewPrism: {w}')
        return {'FINISHED'}


class VIEWPRISM_OT_preview_show(bpy.types.Operator):
    bl_idname = 'viewprism.preview_show'
    bl_label = 'Show Pass'
    bl_description = ('Show this pass over the viewport (display only). Click again to hide it; '
                      'the thumbnails stay')
    bl_translation_context = CONTEXT
    bl_options = {'REGISTER', 'INTERNAL'}

    pass_name: EnumProperty(items=props.PASS_ITEMS, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        try:
            view = viewport.resolve(context)
            preview.show_pass(context, view, self.pass_name)
        except _ERRORS as exc:
            return _fail_preview(self, exc)
        return {'FINISHED'}


class VIEWPRISM_OT_preview_hide(bpy.types.Operator):
    bl_idname = 'viewprism.preview_hide'
    bl_label = 'Close Preview'
    bl_description = 'Remove the preview and the thumbnails from the viewport and free their memory'
    bl_translation_context = CONTEXT
    bl_options = {'REGISTER'}

    def execute(self, context):
        props.settings(context).preview_auto = False
        preview.clear()
        return {'FINISHED'}


class VIEWPRISM_OT_open_folder(bpy.types.Operator):
    bl_idname = 'viewprism.open_folder'
    bl_label = 'Open Output Folder'
    bl_description = 'Open the output folder in the file manager'
    bl_translation_context = CONTEXT
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            directory = output_directory(props.settings(context).output_dir)
        except export.ExportError as exc:
            return _fail(self, exc)
        if not os.path.isdir(directory):
            return _fail(self, export.ExportError(iface('The output folder does not exist yet. It is created by '
                                                        'the first export.')))
        bpy.ops.wm.path_open(filepath=directory)
        return {'FINISHED'}


class VIEWPRISM_OT_settings_save_defaults(bpy.types.Operator):
    bl_idname = 'viewprism.settings_save_defaults'
    bl_label = 'Save Current Settings as Defaults'
    bl_description = 'Store the current settings in the add-on preferences; new sessions start from them'
    bl_translation_context = CONTEXT
    bl_options = {'REGISTER'}

    def execute(self, context):
        prefs = props.preferences(context)
        if prefs is None:
            return _fail(self, export.ExportError(iface('The add-on preferences are not available.')))
        props.copy_settings(props.settings(context), prefs.defaults)
        context.preferences.is_dirty = True
        self.report({'INFO'}, rpt('ViewPrism: defaults saved to the preferences'))
        return {'FINISHED'}


class VIEWPRISM_OT_settings_load_defaults(bpy.types.Operator):
    bl_idname = 'viewprism.settings_load_defaults'
    bl_label = 'Load Defaults'
    bl_description = 'Reset the current settings to the saved defaults'
    bl_translation_context = CONTEXT
    bl_options = {'REGISTER'}

    def execute(self, context):
        prefs = props.preferences(context)
        if prefs is None:
            return _fail(self, export.ExportError(iface('The add-on preferences are not available.')))
        props.copy_settings(prefs.defaults, props.settings(context))
        return {'FINISHED'}


classes = (VIEWPRISM_OT_export, VIEWPRISM_OT_export_as, VIEWPRISM_OT_preview, VIEWPRISM_OT_preview_show,
           VIEWPRISM_OT_preview_hide, VIEWPRISM_OT_open_folder, VIEWPRISM_OT_settings_save_defaults,
           VIEWPRISM_OT_settings_load_defaults)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
