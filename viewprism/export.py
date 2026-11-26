"""Pure export planning and safe file writing (no bpy).

* Output names are ``<stem>_<suffix>.<ext>`` inside one user-chosen directory.
* The whole batch is checked for collisions *before* anything is written; existing
  files are never overwritten unless the caller explicitly allows it.
* Every file is written to a temporary sibling and moved into place with
  ``os.replace`` (atomic on the same file system). Failures are reported per file.
"""
import json
import os
import re
import secrets

SUFFIX = {'depth': 'depth', 'normal': 'normal', 'object_id': 'id', 'mask': 'mask'}
FORMATS = {
    'depth': ('PNG8', 'PNG16', 'EXR'),
    'normal': ('PNG8', 'PNG16', 'EXR'),
    'object_id': ('PNG16', 'EXR'),
    'mask': ('PNG8',),
}
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
MAX_INDEX = 99999


class ExportError(Exception):
    pass


class NameError_(ExportError):
    pass


class CollisionError(ExportError):
    def __init__(self, names):
        self.names = list(names)
        super().__init__('files already exist: ' + ', '.join(self.names))


def sanitize_stem(stem):
    """Validate a user-provided base name. Returns it stripped; raises NameError_."""
    if not isinstance(stem, str):
        raise NameError_('name must be text')
    s = stem.strip()
    if not s:
        raise NameError_('name is empty')
    if _BAD_CHARS.search(s):
        raise NameError_('name contains characters that are not allowed in file names (<>:"/\\|?* or control)')
    if s in ('.', '..') or s.startswith('.'):
        raise NameError_('name must not start with a dot')
    if s.split('.')[0].upper() in _RESERVED:
        raise NameError_(f'"{s}" is a reserved file name on Windows')
    if len((s + '_normal.png').encode('utf-8')) > 240:
        raise NameError_('name is too long')
    return s


def output_items(passes):
    """passes: dict pass -> iterable of formats. Returns [(key, suffix, ext)] in a stable order.
    key is e.g. 'depth:PNG8'. Raises ExportError for unsupported formats or two PNG formats
    of the same pass (they would share a file name)."""
    items = []
    for p in ('depth', 'normal', 'object_id', 'mask'):
        fmts = list(passes.get(p, ()))
        for f in fmts:
            if f not in FORMATS[p]:
                raise ExportError(f'{p}: unsupported format {f}')
        if sum(f.startswith('PNG') for f in fmts) > 1:
            raise ExportError(f'{p}: choose one PNG bit depth')
        for f in FORMATS[p]:
            if f in fmts:
                items.append((f'{p}:{f}', SUFFIX[p], 'exr' if f == 'EXR' else 'png'))
    return items


def file_names(stem, items, meta=True):
    names = [(key, f'{stem}_{suffix}.{ext}') for key, suffix, ext in items]
    if meta:
        names.append(('meta', f'{stem}_meta.json'))
    return names


def plan(directory, base, items, *, numbering='AUTO', overwrite=False, meta=True,
         exists=os.path.exists, start=1):
    """Choose the final stem and paths. Returns dict(stem, files=[(key, name, path)]).

    numbering 'AUTO': stem = f'{base}_{n:04d}' with the smallest n >= start for which no
    output file exists (never overwrites). 'NONE': stem = base; existing files raise
    CollisionError unless overwrite=True.
    """
    base = sanitize_stem(base)
    if not items and not meta:
        raise ExportError('nothing to export')
    directory = os.path.abspath(directory)

    def build(stem):
        files = [(k, n, os.path.join(directory, n)) for k, n in file_names(stem, items, meta)]
        lowered = [n.casefold() for _k, n, _p in files]
        if len(set(lowered)) != len(lowered):
            raise ExportError('duplicate output names in one batch')
        return files

    if numbering == 'NONE':
        files = build(base)
        clash = [n for _k, n, p in files if exists(p)]
        if clash and not overwrite:
            raise CollisionError(clash)
        return dict(stem=base, files=files, overwrite=bool(overwrite))
    if numbering != 'AUTO':
        raise ExportError(f'unknown numbering mode {numbering!r}')
    for n in range(max(1, int(start)), MAX_INDEX + 1):
        stem = f'{base}_{n:04d}'
        files = build(stem)
        if not any(exists(p) for _k, _n, p in files):
            return dict(stem=stem, files=files, overwrite=False)
    raise ExportError('no free file number left')


def _inside(directory, path):
    d = os.path.realpath(directory)
    p = os.path.realpath(path)
    return os.path.commonpath([d, p]) == d and os.path.dirname(p) == d


def atomic_write(path, data, *, overwrite=False):
    """Write bytes to path via a temporary file in the same directory + os.replace."""
    directory = os.path.dirname(path)
    if not _inside(directory, path):
        raise ExportError('refusing to write outside the output directory')
    if not overwrite and os.path.exists(path):
        raise CollisionError([os.path.basename(path)])
    tmp = os.path.join(directory, f'.{os.path.basename(path)}.{secrets.token_hex(4)}.viewprism-tmp')
    try:
        with open(tmp, 'xb') as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if not overwrite and os.path.exists(path):
            raise CollisionError([os.path.basename(path)])
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def write_batch(the_plan, producers, workers=4):
    """producers: dict key -> zero-argument callable returning bytes.

    Writes every planned file, continuing after individual failures.
    Returns dict(written=[name], failed=[(name, message)]).
    """
    written, failed = [], []
    directory = os.path.dirname(the_plan['files'][0][2]) if the_plan['files'] else None
    if directory:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            return dict(written=[], failed=[(n, f'cannot create directory: {exc}') for _k, n, _p in the_plan['files']])
    def one(item):
        key, name, path = item
        try:
            data = producers[key]()
            atomic_write(path, data, overwrite=the_plan.get('overwrite', False))
            return name, None
        except Exception as exc:  # report per file, keep going
            return name, f'{type(exc).__name__}: {exc}'

    files = the_plan['files']
    if len(files) > 1 and workers > 1:
        # Encoders are pure NumPy/zlib (release the GIL); files are independent.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(workers, len(files))) as pool:
            results = list(pool.map(one, files))
    else:
        results = [one(f) for f in files]
    for name, err in results:            # keep the planned order in reports
        if err is None:
            written.append(name)
        else:
            failed.append((name, err))
    return dict(written=written, failed=failed)


def to_json_bytes(obj):
    def default(o):
        try:
            import numpy as np
            if isinstance(o, np.generic):
                return o.item()
            if isinstance(o, np.ndarray):
                return o.tolist()
        except ImportError:
            pass
        raise TypeError(f'not JSON serialisable: {type(o).__name__}')

    def clean(o):
        if isinstance(o, float) and (o != o or o in (float('inf'), float('-inf'))):
            return None if o != o else ('inf' if o > 0 else '-inf')
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        return o
    return (json.dumps(clean(obj), indent=2, ensure_ascii=False, default=default, allow_nan=False) + '\n').encode('utf-8')
