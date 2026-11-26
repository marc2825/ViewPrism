"""Capture result -> files on disk (pure: NumPy + stdlib; no bpy).

Separates numeric arrays (the capture) from file encoding, so the same code path is
unit-tested with synthetic arrays and used by the Blender operators.
"""
import datetime

import numpy as np

from . import encode, export, exr, png

FORMAT_VERSION = 1


def default_options():
    return {
        'outputs': {'depth': ['PNG8', 'EXR'], 'normal': ['PNG8']},
        'depth': {'range': 'AUTO', 'near': None, 'far': None, 'near_white': True, 'background': 'FAR'},
        'normal': {'background': (0.0, 0.0, 0.0), 'flip_x': False, 'flip_y': False},
        'exr': {'compression': 'ZIP'},
        'base_name': 'viewpass', 'numbering': 'AUTO', 'overwrite': False, 'meta': True,
        'source': {}, 'version': '0.0.0',
    }


def _required(result, name):
    if name not in result:
        raise export.ExportError(f'the capture has no {name} pass')
    return np.asarray(result[name])


def _mask(result):
    if 'mask' in result:
        return np.asarray(result['mask'], dtype=bool)
    if 'object_id' in result:
        return np.asarray(result['object_id']) > 0
    if 'depth' in result:
        return np.isfinite(np.asarray(result['depth']))
    raise export.ExportError('cannot determine foreground mask')


def producers(result, options):
    """Return (dict key -> callable bytes, dict pass -> encoding description)."""
    depth_opt = options['depth']
    exr_comp = options['exr']['compression']
    prods, enc = {}, {}
    outputs = options['outputs']

    if outputs.get('depth'):
        depth = _required(result, 'depth')
        mask = _mask(result)
        enc['depth'] = {'raw': 'planar view depth (-Z in view space), scene units, float32',
                        'background_raw': 'NaN'}
        for fmt in outputs['depth']:
            if fmt.startswith('PNG'):
                bits = 16 if fmt == 'PNG16' else 8
                img, info = encode.normalize_depth(depth, mask, depth_opt['range'], depth_opt.get('near'),
                                                   depth_opt.get('far'), depth_opt['near_white'],
                                                   depth_opt['background'], dtype=np.float64)
                enc['depth']['png'] = dict(bit_depth=bits, mapping='linear', range_mode=info['mode'],
                                           range=[info['lo'], info['hi']], flat=info['flat'],
                                           empty=info['empty'], near_white=info['near_white'],
                                           background_value=info['background'],
                                           note='display encoding; use the EXR for measurements')
                prods[f'depth:{fmt}'] = (lambda img=img, bits=bits: png.encode(encode.quantize(img, bits)))
            else:
                enc['depth']['exr'] = dict(channels={'Z': 'depth (NaN = background)', 'A': 'mask 0/1'},
                                           type='FLOAT', compression=exr_comp)
                prods['depth:EXR'] = (lambda: exr.encode({'Z': depth.astype(np.float32),
                                                          'A': mask.astype(np.float32)}, exr_comp))

    if outputs.get('normal'):
        normal = _required(result, 'normal')
        mask = _mask(result)
        enc['normal'] = {'raw': 'camera-space unit normal: +X right, +Y up, +Z towards the viewer'}
        for fmt in outputs['normal']:
            if fmt.startswith('PNG'):
                bits = 16 if fmt == 'PNG16' else 8
                bg = tuple(float(v) for v in options['normal']['background'])
                fx = bool(options['normal'].get('flip_x', False))
                fy = bool(options['normal'].get('flip_y', False))
                sx, sy = ('-' if fx else '', '-' if fy else '')
                enc['normal']['png'] = dict(bit_depth=bits, mapping=f'rgb = ({sx}n.x, {sy}n.y, n.z) * 0.5 + 0.5',
                                            flip_x=fx, flip_y=fy, background_rgb=list(bg), colour_management='none')
                shown = normal if not (fx or fy) else normal * np.array([-1 if fx else 1, -1 if fy else 1, 1], np.float32)
                prods[f'normal:{fmt}'] = (lambda bits=bits, bg=bg, shown=shown: png.encode(
                    encode.quantize_normal(shown, mask, bits, bg)))
            else:
                enc['normal']['exr'] = dict(channels={'R': 'n.x', 'G': 'n.y', 'B': 'n.z', 'A': 'mask 0/1'},
                                            type='FLOAT', signed=True, compression=exr_comp)
                prods['normal:EXR'] = (lambda: exr.encode(
                    {'R': normal[..., 0].astype(np.float32), 'G': normal[..., 1].astype(np.float32),
                     'B': normal[..., 2].astype(np.float32), 'A': mask.astype(np.float32)}, exr_comp))

    if outputs.get('object_id'):
        ids = _required(result, 'object_id')
        enc['object_id'] = {'raw': 'uint32, 0 = background, see id_map'}
        for fmt in outputs['object_id']:
            if fmt == 'PNG16':
                enc['object_id']['png'] = dict(bit_depth=16, mapping='pixel value == id (lossless)',
                                               max_id=encode.ID_PNG_MAX)
                prods['object_id:PNG16'] = (lambda: png.encode(encode.encode_id_u16(ids)))
            else:
                enc['object_id']['exr'] = dict(channels={'id': 'object id'}, type='UINT', compression=exr_comp)
                prods['object_id:EXR'] = (lambda: exr.encode({'id': ids.astype(np.uint32)}, exr_comp))

    if outputs.get('mask'):
        mask = _mask(result)
        enc['mask'] = {'png': dict(bit_depth=8, mapping='255 = foreground, 0 = background')}
        prods['mask:PNG8'] = (lambda: png.encode(encode.mask_to_u8(mask)))
    return prods, enc


def metadata(result, options, encodings, files):
    info = result.get('info', {})
    return {
        'format': 'viewpass-meta', 'format_version': FORMAT_VERSION,
        'generator': f"ViewPass {options.get('version', '')}".strip(),
        'blender': info.get('blender'),
        'created_utc': datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        'frame': info.get('frame'), 'frame_float': info.get('frame_float'),
        'resolution': [info.get('width'), info.get('height')],
        'pixels': {'origin': 'top-left', 'row_order': 'top-to-bottom', 'sample': 'pixel centre',
                   'antialiasing': 'none'},
        'camera': {
            'source': options.get('source', {}),
            'projection': info.get('projection'), 'near': info.get('near'), 'far': info.get('far'),
            'view_matrix': info.get('view_matrix'), 'projection_matrix': info.get('projection_matrix'),
            'convention': 'row-major, column vectors, OpenGL clip space (NDC z -1..1), view looks down -Z',
        },
        'normal_mode': info.get('normal_mode'), 'id_mode': info.get('id_mode'),
        'passes': encodings,
        'files': files,
        'id_map': {str(k): v for k, v in sorted(result.get('id_map', {}).items())},
        'warnings': list(result.get('warnings', [])),
        'stats': result.get('stats', {}),
    }


def export_capture(result, options, directory, *, exists=None):
    """Encode and write the selected outputs. Returns dict(stem, written, failed, files)."""
    items = export.output_items(options['outputs'])
    kwargs = {} if exists is None else {'exists': exists}
    the_plan = export.plan(directory, options['base_name'], items, numbering=options['numbering'],
                           overwrite=options['overwrite'], meta=options['meta'], **kwargs)
    prods, enc = producers(result, options)
    files = {k: n for k, n, _p in the_plan['files']}
    data_files = [f for f in the_plan['files'] if f[0] != 'meta']
    meta_files = [f for f in the_plan['files'] if f[0] == 'meta']
    status = export.write_batch(dict(the_plan, files=data_files), prods) if data_files \
        else dict(written=[], failed=[])
    if meta_files:
        # Written last so it lists exactly the files that were written and those that failed.
        ok = set(status['written'])
        meta = metadata(result, options, enc, {k: n for k, n in files.items() if k != 'meta' and n in ok})
        meta['failed_files'] = [dict(file=n, error=e) for n, e in status['failed']]
        st = export.write_batch(dict(the_plan, files=meta_files), {'meta': lambda: export.to_json_bytes(meta)})
        status = dict(written=status['written'] + st['written'], failed=status['failed'] + st['failed'])
    return dict(stem=the_plan['stem'], written=status['written'], failed=status['failed'], files=files)
