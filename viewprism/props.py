# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings. Session settings live on the WindowManager (runtime only: never saved into
the user's .blend). Add-on preferences hold persistent defaults copied in at startup."""
import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)

def _path_options():
    """'//' is resolved with bpy.path.abspath, so declare blend-relative support where the
    option exists (Blender 5.x marks undeclared relative paths as invalid)."""
    class _Probe(bpy.types.PropertyGroup):
        pass
    _Probe.__annotations__ = {'p': StringProperty(subtype='DIR_PATH', options={'PATH_SUPPORTS_BLEND_RELATIVE'})}
    try:
        bpy.utils.register_class(_Probe)
    except (TypeError, ValueError, RuntimeError):
        return set()
    bpy.utils.unregister_class(_Probe)
    return {'PATH_SUPPORTS_BLEND_RELATIVE'}


PASS_ITEMS = [('depth', 'Depth', 'Planar camera-space depth'),
              ('normal', 'Normal', 'Camera-space normals'),
              ('object_id', 'Object ID', 'Integer object index'),
              ('mask', 'Mask', 'Foreground mask')]


def _redraw(_self, context):
    from . import preview
    preview.settings_changed(context)


class ViewPrismSettings(bpy.types.PropertyGroup):
    use_depth: BoolProperty(name='Depth', default=True, description='Export the depth pass', update=_redraw)
    use_normal: BoolProperty(name='Normal', default=True, description='Export the normal pass', update=_redraw)
    use_object_id: BoolProperty(name='Object ID', default=False, description='Export the object ID pass', update=_redraw)
    use_mask: BoolProperty(name='Mask', default=False, description='Export the foreground mask', update=_redraw)

    resolution_mode: EnumProperty(
        name='Resolution', default='VIEW',
        items=[('VIEW', 'View', 'Viewport size (or the render resolution when exporting the camera frame), scaled'),
               ('CUSTOM', 'Custom', 'Explicit size; a different aspect ratio crops the view (centred)')])
    scale: IntProperty(name='Scale', default=100, min=1, max=800, soft_max=400, subtype='PERCENTAGE',
                       description='Scale applied to the view size')
    width: IntProperty(name='Width', default=1920, min=1, max=16384, description='Output width in pixels')
    height: IntProperty(name='Height', default=1080, min=1, max=16384, description='Output height in pixels')
    lock_aspect: BoolProperty(name='Lock Aspect', default=True,
                              description='Derive the height from the view aspect ratio')
    camera_frame: BoolProperty(name='Camera Frame in Camera View', default=True,
                               description='When looking through a camera, export exactly the camera frame '
                                           '(camera projection, render aspect) instead of the whole viewport')

    depth_range: EnumProperty(name='Depth Range', default='AUTO', update=_redraw,
                              items=[('AUTO', 'Auto', 'Nearest to farthest visible surface'),
                                     ('FIXED', 'Fixed', 'Explicit near/far distances')])
    depth_near: FloatProperty(name='Near', default=0.0, unit='LENGTH', update=_redraw,
                              description='Distance mapped to the near colour')
    depth_far: FloatProperty(name='Far', default=10.0, unit='LENGTH', update=_redraw,
                             description='Distance mapped to the far colour')
    depth_near_white: BoolProperty(name='Near is White', default=True, update=_redraw,
                                   description='Near surfaces are white (common for depth ControlNets); '
                                               'off: near is black')
    depth_background: EnumProperty(name='Background', default='FAR', update=_redraw,
                                   items=[('FAR', 'Far Colour', 'Background uses the far colour'),
                                          ('NEAR', 'Near Colour', 'Background uses the near colour'),
                                          ('VALUE', 'Value', 'Explicit gray value')])
    depth_background_value: FloatProperty(name='Value', default=0.0, min=0.0, max=1.0, subtype='FACTOR',
                                          update=_redraw)

    normal_mode: EnumProperty(name='Normals', default='SHADED', update=_redraw,
                              items=[('SHADED', 'As Shaded', 'Corner normals as displayed: smooth/flat shading, '
                                                             'auto smooth and custom normals'),
                                     ('FLAT', 'Flat', 'Polygon (face) normals')])
    normal_background: EnumProperty(name='Background', default='BLACK', update=_redraw,
                                    items=[('BLACK', 'Black', 'RGB (0, 0, 0)'),
                                           ('FLAT', 'Facing Viewer', 'RGB (0.5, 0.5, 1.0): the colour of a normal '
                                                                     'pointing at the viewer')])
    normal_flip_x: BoolProperty(name='Flip X (PNG)', default=False, update=_redraw,
                                description='Store -X in the normal PNG (some tools expect a mirrored X axis). '
                                            'EXR stays canonical')
    normal_flip_y: BoolProperty(name='Flip Y (PNG)', default=False, update=_redraw,
                                description='Store -Y in the normal PNG (DirectX-style green channel). '
                                            'EXR stays canonical')
    id_mode: EnumProperty(name='ID Per', default='OBJECT', update=_redraw,
                          items=[('OBJECT', 'Object', 'One ID per source object (instances share it)'),
                                 ('INSTANCER', 'Instancer', 'One ID per object in the view layer '
                                                            '(a collection instance is one ID)'),
                                 ('INSTANCE', 'Instance', 'One ID per individual instance')])

    depth_png: EnumProperty(name='Depth PNG', default='PNG8',
                            items=[('NONE', 'Off', ''), ('PNG8', '8-bit', ''), ('PNG16', '16-bit', '')])
    depth_exr: BoolProperty(name='Depth EXR', default=True, description='Raw float32 depth (EXR)')
    normal_png: EnumProperty(name='Normal PNG', default='PNG8',
                             items=[('NONE', 'Off', ''), ('PNG8', '8-bit', ''), ('PNG16', '16-bit', '')])
    normal_exr: BoolProperty(name='Normal EXR', default=False, description='Raw signed float32 normals (EXR)')
    id_png: BoolProperty(name='ID PNG', default=True, description='16-bit PNG, pixel value = ID (max 65535)')
    id_exr: BoolProperty(name='ID EXR', default=False, description='32-bit unsigned integer EXR channel')
    exr_compression: EnumProperty(name='EXR Codec', default='ZIP',
                                  items=[('ZIP', 'ZIP', 'Lossless, 16 scanlines per block'),
                                         ('NONE', 'None', 'Uncompressed')])
    metadata_privacy: EnumProperty(
        name='Metadata Names', default='FULL',
        items=[('FULL', 'Full', 'Object and camera names in the ID map and warnings'),
               ('ANONYMIZED', 'Anonymized', 'Neutral labels (object_1, ...) instead of object and camera names; '
                                            'ids, images and camera matrices are unchanged')])
    write_meta: BoolProperty(name='Metadata', default=True,
                             description='Write <name>_meta.json (matrices, ranges, ID map, warnings)')

    output_dir: StringProperty(name='Folder', default='//viewprism/', subtype='DIR_PATH',
                               options=_path_options(),
                               description='Output folder ("//" is relative to the saved .blend file)')
    base_name: StringProperty(name='Name', default='viewprism', description='Base file name')
    numbering: EnumProperty(name='Numbering', default='AUTO',
                            items=[('AUTO', 'Auto Number', 'Append the next free number (never overwrites)'),
                                   ('NONE', 'Exact Name', 'Use the name as is')])
    overwrite: BoolProperty(name='Overwrite', default=False,
                            description='With Exact Name: replace existing files')

    preview_pass: EnumProperty(name='Preview', items=PASS_ITEMS, default='depth', update=_redraw)
    preview_opacity: FloatProperty(name='Opacity', default=1.0, min=0.0, max=1.0, subtype='FACTOR',
                                   update=_redraw)
    preview_scale: IntProperty(name='Preview Scale', default=50, min=10, max=100, subtype='PERCENTAGE',
                               description='Preview resolution relative to the viewport')
    preview_auto: BoolProperty(name='Auto Refresh', default=False, update=_redraw,
                               description='Re-capture the preview shortly after the view or scene changes')


class ViewPrismPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    defaults: PointerProperty(type=ViewPrismSettings)

    def draw(self, context):
        layout = self.layout
        layout.label(text='Session settings start from these defaults. Settings are never stored in .blend files.')
        row = layout.row()
        row.operator('viewprism.settings_save_defaults', icon='FILE_TICK')
        row.operator('viewprism.settings_load_defaults', icon='LOOP_BACK')
        col = layout.column()
        col.use_property_split = True
        d = self.defaults
        for name in ('output_dir', 'base_name', 'numbering', 'resolution_mode', 'scale', 'depth_png',
                     'depth_exr', 'normal_png', 'normal_exr', 'id_png', 'id_exr', 'depth_near_white'):
            col.prop(d, name)


def preferences(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon is not None else None


def copy_settings(src, dst):
    for prop in src.bl_rna.properties:
        if prop.identifier in {'rna_type', 'name'} or prop.is_readonly:
            continue
        setattr(dst, prop.identifier, getattr(src, prop.identifier))


def settings(context=None):
    context = context or bpy.context
    return context.window_manager.viewprism


_initialized_wm = set()


def init_session_settings(context=None):
    """Copy persistent defaults into the session settings once per window manager."""
    context = context or bpy.context
    wm = context.window_manager
    if wm is None:
        return
    key = wm.as_pointer()
    if key in _initialized_wm:
        return
    prefs = preferences(context)
    if prefs is not None:
        copy_settings(prefs.defaults, wm.viewprism)
    _initialized_wm.add(key)


classes = (ViewPrismSettings, ViewPrismPreferences)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.viewprism = PointerProperty(type=ViewPrismSettings)


def unregister():
    del bpy.types.WindowManager.viewprism
    _initialized_wm.clear()
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
