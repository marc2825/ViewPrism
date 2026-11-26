# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings. Session settings live on the WindowManager (runtime only: never saved into
the user's .blend). Add-on preferences hold persistent defaults copied in at startup.

UI names use the add-on's own translation context (i18n_data.CONTEXT), so the Japanese
translation never changes Blender's own labels that happen to use the same English word."""
import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)

from .i18n_data import CONTEXT

T = dict(translation_context=CONTEXT)


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


PASS_ITEMS = [('depth', 'Depth', 'Distance from the camera plane'),
              ('normal', 'Normal', 'Surface direction as seen from the camera'),
              ('object_id', 'Object ID', 'One integer per object'),
              ('mask', 'Mask', 'Foreground (white) and background (black)')]
PNG_BITS = [('NONE', 'Off', 'No PNG file for this pass'),
            ('PNG8', '8-bit', '256 levels; small files, enough for most image tools'),
            ('PNG16', '16-bit', '65,536 levels; smoother gradients, larger files')]


def _redraw(_self, context):
    """Display setting: re-encode the cached preview (no new capture)."""
    from . import preview
    preview.settings_changed(context, 'display')


def _repaint(_self, context):
    """Only drawing changes (opacity, exported passes, Auto Refresh)."""
    from . import preview
    preview.settings_changed(context, 'repaint')


def _recapture(_self, context):
    """Preview resolution: needs a new capture."""
    from . import preview
    preview.settings_changed(context, 'capture')


class ViewPrismSettings(bpy.types.PropertyGroup):
    use_depth: BoolProperty(name='Depth', default=True, update=_repaint, **T,
                            description='Export the depth pass (distance from the camera plane)')
    use_normal: BoolProperty(name='Normal', default=True, update=_repaint, **T,
                             description='Export the normal pass (surface direction as seen from the camera)')
    use_object_id: BoolProperty(name='Object ID', default=False, update=_repaint, **T,
                                description='Export the object ID pass (one integer per object)')
    use_mask: BoolProperty(name='Mask', default=False, update=_repaint, **T,
                           description='Export the foreground mask (white = something, black = nothing)')

    resolution_mode: EnumProperty(
        name='Size', default='VIEW', **T,
        items=[('VIEW', 'View', 'The size of this viewport (or the render resolution in camera view), scaled'),
               ('CUSTOM', 'Custom', 'An exact size in pixels; a different aspect ratio crops the view (centred)')])
    scale: IntProperty(name='Scale', default=100, min=1, max=800, soft_max=400, subtype='PERCENTAGE', **T,
                       description='Scale applied to the view size')
    width: IntProperty(name='Width', default=1920, min=1, max=16384, **T, description='Output width in pixels')
    height: IntProperty(name='Height', default=1080, min=1, max=16384, **T, description='Output height in pixels')
    lock_aspect: BoolProperty(name='Keep View Aspect', default=True, **T,
                              description='Derive the height from the view aspect ratio')
    camera_frame: BoolProperty(name='Camera Frame', default=True, **T,
                               description='In camera view, export exactly the camera frame (camera projection, '
                                           'render aspect) instead of the whole viewport')

    depth_range: EnumProperty(name='Range', default='AUTO', update=_redraw, **T,
                              items=[('AUTO', 'Auto', 'From the nearest to the farthest visible surface'),
                                     ('FIXED', 'Fixed', 'Between two distances you enter')])
    depth_near: FloatProperty(name='Near', default=0.0, unit='LENGTH', update=_redraw, **T,
                              description='Distance shown with the near colour')
    depth_far: FloatProperty(name='Far', default=10.0, unit='LENGTH', update=_redraw, **T,
                             description='Distance shown with the far colour')
    depth_near_white: BoolProperty(name='Near is White', default=True, update=_redraw, **T,
                                   description='Near surfaces are white (common for depth ControlNets); '
                                               'off: near is black. Applies to the PNG only')
    depth_background: EnumProperty(name='Background', default='FAR', update=_redraw, **T,
                                   items=[('FAR', 'Far Colour', 'Empty areas get the far colour'),
                                          ('NEAR', 'Near Colour', 'Empty areas get the near colour'),
                                          ('VALUE', 'Grey Value', 'Empty areas get a grey value you choose')])
    depth_background_value: FloatProperty(name='Grey Value', default=0.0, min=0.0, max=1.0, subtype='FACTOR',
                                          update=_redraw, **T, description='Grey value of empty areas in the PNG')

    normal_mode: EnumProperty(name='Shading', default='SHADED', update=_redraw, **T,
                              items=[('SHADED', 'As Shaded', 'Normals as displayed: smooth/flat shading, '
                                                             'auto smooth and custom normals'),
                                     ('FLAT', 'Flat', 'One normal per face')])
    normal_background: EnumProperty(name='Background', default='BLACK', update=_redraw, **T,
                                    items=[('BLACK', 'Black', 'RGB (0, 0, 0)'),
                                           ('FLAT', 'Facing Viewer', 'RGB (0.5, 0.5, 1.0): the colour of a normal '
                                                                     'pointing at the viewer')])
    normal_flip_x: BoolProperty(name='Flip X', default=False, update=_redraw, **T,
                                description='Store -X in the normal PNG (some tools expect a mirrored X axis). '
                                            'EXR stays canonical')
    normal_flip_y: BoolProperty(name='Flip Y', default=False, update=_redraw, **T,
                                description='Store -Y in the normal PNG (DirectX-style green channel). '
                                            'EXR stays canonical')
    id_mode: EnumProperty(name='One ID per', default='OBJECT', update=_redraw, **T,
                          items=[('OBJECT', 'Object', 'One ID per source object (instances share it)'),
                                 ('INSTANCER', 'Instancer', 'One ID per object in the view layer '
                                                            '(a collection instance is one ID)'),
                                 ('INSTANCE', 'Instance', 'One ID per individual instance')])

    depth_png: EnumProperty(name='PNG', default='PNG8', items=PNG_BITS, **T,
                            description='Normalized depth image for image tools')
    depth_exr: BoolProperty(name='EXR (exact values)', default=True, **T,
                            description='Depth in scene units as 32-bit float (OpenEXR)')
    normal_png: EnumProperty(name='PNG', default='PNG8', items=PNG_BITS, **T,
                             description='Normal map image for image tools')
    normal_exr: BoolProperty(name='EXR (exact values)', default=False, **T,
                             description='Signed normals as 32-bit float (OpenEXR)')
    id_png: BoolProperty(name='PNG (16-bit)', default=True, **T,
                         description='16-bit PNG, pixel value = ID (IDs up to 65,535)')
    id_exr: BoolProperty(name='EXR (32-bit integer)', default=False, **T,
                         description='32-bit unsigned integer EXR channel (any number of IDs)')
    exr_compression: EnumProperty(name='EXR Compression', default='ZIP', **T,
                                  items=[('ZIP', 'ZIP', 'Lossless, smaller files'),
                                         ('NONE', 'None', 'Uncompressed, faster to write')])
    metadata_privacy: EnumProperty(
        name='Names', default='FULL', **T,
        items=[('FULL', 'Object Names', 'Object and camera names in the ID map and warnings'),
               ('ANONYMIZED', 'Anonymized', 'Neutral labels (object_1, ...) instead of object and camera names; '
                                            'IDs, images and camera matrices are unchanged')])
    write_meta: BoolProperty(name='Metadata', default=True, **T,
                             description='Write <name>_meta.json (matrices, depth range, ID map, warnings)')

    output_dir: StringProperty(name='Folder', default='//viewprism/', subtype='DIR_PATH', **T,
                               options=_path_options(),
                               description='Output folder ("//" means: next to the saved .blend file)')
    base_name: StringProperty(name='Name', default='viewprism', **T, description='Start of every file name')
    numbering: EnumProperty(name='Numbering', default='AUTO', **T,
                            items=[('AUTO', 'Add Number', 'Add the next free number (never overwrites)'),
                                   ('NONE', 'Name Only', 'Use the name as is')])
    overwrite: BoolProperty(name='Overwrite', default=False, **T,
                            description='With "Name Only": replace existing files of the same name')

    preview_pass: EnumProperty(name='Preview', items=PASS_ITEMS, default='depth', update=_redraw, **T)
    preview_opacity: FloatProperty(name='Opacity', default=1.0, min=0.0, max=1.0, subtype='FACTOR',
                                   update=_repaint, **T, description='Opacity of the large preview')
    preview_scale: IntProperty(name='Resolution', default=50, min=10, max=100, subtype='PERCENTAGE', **T,
                               update=_recapture,
                               description='Preview resolution relative to the viewport')
    preview_auto: BoolProperty(name='Auto Refresh', default=False, update=_repaint, **T,
                               description='Capture the preview again once the view and the scene stop changing')
    preview_thumbnails: BoolProperty(name='Thumbnails', default=True, update=_redraw, **T,
                                     description='Show small images of all four passes in the corner of the viewport')


class ViewPrismPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    defaults: PointerProperty(type=ViewPrismSettings)

    def draw(self, context):
        from .i18n import iface
        layout = self.layout
        col = layout.column(align=True)
        col.label(text=iface('New sessions start from saved defaults. Settings are never stored in .blend files.'),
                  translate=False)
        col.label(text=iface('Defaults include every panel setting.'), translate=False)
        row = layout.row()
        row.operator('viewprism.settings_save_defaults', icon='FILE_TICK')
        row.operator('viewprism.settings_load_defaults', icon='LOOP_BACK')


def preferences(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon is not None else None


def _setting_names(s):
    return [p.identifier for p in s.bl_rna.properties if p.identifier not in {'rna_type', 'name'} and not p.is_readonly]


def copy_settings(src, dst):
    for name in _setting_names(src):
        setattr(dst, name, getattr(src, name))


def signature(s):
    """Everything that changes what an export writes (not preview display options)."""
    return tuple(getattr(s, n) for n in _setting_names(s) if not n.startswith('preview_'))


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
