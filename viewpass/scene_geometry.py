"""Collect drawable, visible geometry from the evaluated depsgraph (read-only).

Visibility follows what the given 3D viewport shows (see docs/decisions/0001-renderer.md):

* only depsgraph instances with ``show_self``;
* the object in the view layer (the instancer for instances) must pass
  ``Object.visible_get(view_layer, viewport)`` - this covers hide (eye), collection
  exclusion / hiding, local view and per-viewport local collections;
* the viewport's object-type visibility filter is respected;
* objects displayed as Wire / Bounds are not solid in the viewport and are skipped;
* surface types are converted with the evaluated ``to_mesh()`` (modifiers, geometry
  nodes, shape keys, edit-mode edits). Curves (hair), point clouds, volumes and grease
  pencil are reported as unsupported.

Nothing in the scene is modified: ``to_mesh()`` results are owned by the evaluated
object and released immediately with ``to_mesh_clear()``.
"""
from collections import Counter

import numpy as np

SURFACE_TYPES = {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}
UNSUPPORTED_VISIBLE = {'CURVES', 'POINTCLOUD', 'VOLUME', 'GREASEPENCIL', 'GPENCIL'}
_TYPE_FILTER = {
    'MESH': 'show_object_viewport_mesh', 'CURVE': 'show_object_viewport_curve',
    'SURFACE': 'show_object_viewport_surf', 'FONT': 'show_object_viewport_font',
    'META': 'show_object_viewport_meta',
}
ID_MODES = ('OBJECT', 'INSTANCER', 'INSTANCE')
NORMAL_MODES = ('SHADED', 'FLAT')


class MeshData:
    __slots__ = ('pos', 'nor', 'tris', 'name')

    def __init__(self, pos, nor, tris, name):
        self.pos, self.nor, self.tris, self.name = pos, nor, tris, name

    @property
    def ntris(self):
        return len(self.tris)


class DrawItem:
    __slots__ = ('key', 'mesh_key', 'matrix', 'sort_key', 'id')

    def __init__(self, key, mesh_key, matrix, sort_key):
        self.key, self.mesh_key, self.matrix, self.sort_key = key, mesh_key, matrix, sort_key
        self.id = 0


def extract_mesh(ob_eval, normal_mode='SHADED'):
    """Evaluated object -> MeshData with per-corner positions/normals and triangle corner
    indices (all float32/int32 NumPy). Returns None when there are no triangles."""
    me = ob_eval.to_mesh()
    try:
        if me is None:
            return None
        ntri = len(me.loop_triangles)
        if ntri == 0:
            return None
        nv, nl = len(me.vertices), len(me.loops)
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get('co', co)
        corner_vert = np.empty(nl, np.int32)
        me.loops.foreach_get('vertex_index', corner_vert)
        tris = np.empty(ntri * 3, np.int32)
        me.loop_triangles.foreach_get('loops', tris)
        if normal_mode == 'FLAT':
            npoly = len(me.polygons)
            pn = np.empty(npoly * 3, np.float32)
            me.polygon_normals.foreach_get('vector', pn)
            totals = np.empty(npoly, np.int32)
            me.polygons.foreach_get('loop_total', totals)
            starts = np.empty(npoly, np.int32)
            me.polygons.foreach_get('loop_start', starts)
            corner_poly = np.empty(nl, np.int64)
            order = np.argsort(starts, kind='stable')
            corner_poly[:] = np.repeat(order, totals[order])
            nor = pn.reshape(-1, 3)[corner_poly]
        else:
            nor = np.empty(nl * 3, np.float32)
            me.corner_normals.foreach_get('vector', nor)
            nor = nor.reshape(-1, 3)
        pos = co.reshape(-1, 3)[corner_vert]
        return MeshData(np.ascontiguousarray(pos, np.float32), np.ascontiguousarray(nor, np.float32),
                        tris.reshape(-1, 3), ob_eval.name)
    finally:
        ob_eval.to_mesh_clear()


def _type_visible(space, ob_type):
    attr = _TYPE_FILTER.get(ob_type)
    return True if (space is None or attr is None) else bool(getattr(space, attr, True))


def _id_key(inst, ob, mode):
    if mode == 'INSTANCER':
        owner = inst.parent if inst.is_instance and inst.parent is not None else ob
        return owner.original.name_full
    if mode == 'INSTANCE' and inst.is_instance:
        owner = inst.parent.original.name_full if inst.parent is not None else '?'
        pid = '.'.join(str(v) for v in inst.persistent_id if v != 0x7FFFFFFF)
        return f'{owner}|{ob.original.name_full}|{pid}'
    return ob.original.name_full


def collect(depsgraph, view_layer, space, *, normal_mode='SHADED', id_mode='OBJECT'):
    """Returns (items, meshes, warnings, stats).

    items: list[DrawItem] sorted deterministically; meshes: mesh_key -> MeshData.
    """
    if normal_mode not in NORMAL_MODES:
        raise ValueError(f'normal_mode must be one of {NORMAL_MODES}')
    if id_mode not in ID_MODES:
        raise ValueError(f'id_mode must be one of {ID_MODES}')
    items, meshes = [], {}
    skipped = Counter()
    failed = []
    vis_cache = {}
    n_inst = 0
    for inst in depsgraph.object_instances:
        if not inst.show_self:
            continue
        ob = inst.object
        owner = inst.parent if (inst.is_instance and inst.parent is not None) else ob
        owner_orig = owner.original
        okey = owner_orig.as_pointer()
        visible = vis_cache.get(okey)
        if visible is None:
            visible = bool(owner_orig.visible_get(view_layer=view_layer, viewport=space))
            vis_cache[okey] = visible
        if not visible:
            continue
        ob_type = ob.type
        if ob_type not in SURFACE_TYPES:
            if ob_type in UNSUPPORTED_VISIBLE:
                skipped[f'unsupported type {ob_type}'] += 1
            continue
        if not _type_visible(space, ob_type):
            continue
        if ob.display_type in {'WIRE', 'BOUNDS'}:
            skipped[f'display as {ob.display_type.title()}'] += 1
            continue
        data = ob.data
        mesh_key = (ob.as_pointer(), data.as_pointer() if data is not None else 0, ob_type)
        if mesh_key not in meshes:
            try:
                meshes[mesh_key] = extract_mesh(ob, normal_mode)
            except RuntimeError as exc:  # e.g. objects that cannot be converted
                meshes[mesh_key] = None
                failed.append(f'{ob.name}: {exc}')
        if meshes[mesh_key] is None:
            continue
        n_inst += inst.is_instance
        key = _id_key(inst, ob, id_mode)
        pid = tuple(inst.persistent_id)
        items.append(DrawItem(key, mesh_key, np.array(inst.matrix_world, dtype=np.float64),
                              (key, inst.is_instance, pid, owner_orig.name_full)))
    items.sort(key=lambda it: it.sort_key)
    warnings = [f'{n} object(s) skipped: {why}' for why, n in sorted(skipped.items())]
    warnings += [f'could not convert {msg}' for msg in failed]
    used = {it.mesh_key for it in items}
    stats = dict(draw_items=len(items), instances=n_inst,
                 unique_meshes=len(used),
                 triangles=int(sum(meshes[it.mesh_key].ntris for it in items)))
    return items, {k: v for k, v in meshes.items() if k in used}, warnings, stats
