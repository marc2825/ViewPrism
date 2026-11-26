# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure export planning and safe file writing (no bpy).

* Output names are ``<stem>_<suffix>.<ext>`` inside one user-chosen directory.
* The whole batch is checked for collisions *before* anything is written; existing
  files are never overwritten unless the caller explicitly allows it.
* Every file is written to a temporary sibling and then published atomically: without
  overwrite through a no-replace rename (Windows) or a hard link (elsewhere); both fail if
  anything exists at the name, so a file created by another writer in the meantime is never
  replaced. File systems without hard links (FAT/exFAT, some network shares) use an exclusive
  placeholder instead. With overwrite: ``os.replace``.
* Automatic numbering reserves its number with an exclusive lock file, so concurrent exports
  (also from other Blender processes) never pick the same name.
* Failures are reported per file with a stable error code and a path-free message for
  shareable metadata; the detailed exception text stays local.
"""
import ctypes
import ctypes.util
import errno
import json
import os
import re
import secrets
import sys
import time

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
TMP_SUFFIX = '.viewprism-tmp'
LOCK_SUFFIX = '.viewprism-lock'
STALE_LOCK_SECONDS = 15 * 60   # an export takes seconds; an older lock was left by a crash


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
    # Longest file name: the stem with the highest AUTO number and the longest suffix, written first
    # under a temporary sibling name; it must fit into the usual 255-byte name limit.
    if len(_temp_name(f'{s}_{MAX_INDEX}_normal.png').encode('utf-8')) > 255:
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
         exists=os.path.lexists, start=1, reserve=False):
    """Choose the final stem and paths. Returns dict(stem, files=[(key, name, path)], overwrite, lock).

    numbering 'AUTO': stem = f'{base}_{n:04d}' with the smallest n >= start for which no output file
    (nor a reservation of another export) exists; it never overwrites. With reserve=True the number is
    reserved by creating `.<stem>.viewprism-lock` exclusively, so concurrent exports (threads or other
    Blender processes) cannot pick the same stem; call release(plan) afterwards. A lock older than
    STALE_LOCK_SECONDS whose files do not exist was left by a crash: that number is used again (with
    reserve=True the stale lock is replaced; exclusive creation still decides between racing exports).
    'NONE': stem = base; existing files raise CollisionError unless overwrite=True.
    Existence uses lexists, so dangling symlinks count as existing.
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
        return dict(stem=base, files=files, overwrite=bool(overwrite), lock=None)
    if numbering != 'AUTO':
        raise ExportError(f'unknown numbering mode {numbering!r}')
    if reserve:
        os.makedirs(directory, exist_ok=True)
    for n in range(max(1, int(start)), MAX_INDEX + 1):
        stem = f'{base}_{n:04d}'
        files = build(stem)
        lock = os.path.join(directory, f'.{stem}{LOCK_SUFFIX}')
        if any(exists(p) for _k, _n, p in files):
            continue
        if exists(lock):
            if not _lock_is_stale(lock):
                continue                      # reserved by an export in progress
            if reserve:
                try:
                    os.remove(lock)           # left by a crash; re-reserved exclusively below
                except OSError:
                    pass
        if reserve:
            try:
                os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            except FileExistsError:
                continue                      # another export reserved this number just now
            if any(exists(p) for _k, _n, p in files):
                release(dict(lock=lock))      # files appeared meanwhile: try the next number
                continue
        return dict(stem=stem, files=files, overwrite=False, lock=lock if reserve else None)
    raise ExportError('no free file number left')


def _lock_is_stale(lock):
    try:
        return time.time() - os.path.getmtime(lock) > STALE_LOCK_SECONDS
    except OSError:
        return False


def release(the_plan):
    lock = the_plan.get('lock')
    if lock:
        try:
            os.remove(lock)
        except OSError:
            pass


def _inside(directory, path):
    d = os.path.realpath(directory)
    p = os.path.realpath(path)
    return os.path.commonpath([d, p]) == d and os.path.dirname(p) == d


def _temp_name(name):
    return f'.{name}.{"0" * 8}{TMP_SUFFIX}'


def _publish_no_clobber(tmp, path):
    """Move tmp to path only if nothing exists at path. Returns once the file is published.

    * Windows: ``os.rename`` (MoveFileEx without REPLACE_EXISTING) is atomic and fails if anything,
      even a dangling link, is at `path`. One step, so nothing is left behind.
    * Elsewhere: a hard link fails the same way; the temporary name is then removed. Once the link
      exists the file is published, so a failure to remove the temporary name is not an export error.
    * File systems without hard links (FAT/exFAT, some network shares): the platform's no-replace
      rename (Linux renameat2 RENAME_NOREPLACE, macOS renamex_np RENAME_EXCL), which is atomic too.
    * Only if the file system supports neither: an exclusive placeholder (see _publish_via_placeholder).
      Files that already exist and other ViewPrism exports are still never replaced; the remaining gap
      is a program that itself *replaces* the placeholder in the microseconds before it is swapped.
    """
    name = os.path.basename(path)
    if os.name == 'nt':
        try:
            os.rename(tmp, path)
        except FileExistsError:
            raise CollisionError([name])
        return
    try:
        os.link(tmp, path)
    except FileExistsError:
        raise CollisionError([name])
    except (OSError, NotImplementedError, AttributeError):
        try:
            if _rename_noreplace(tmp, path):
                return
        except FileExistsError:
            raise CollisionError([name])
        _publish_via_placeholder(tmp, path)
        return
    try:
        os.remove(tmp)
    except OSError:
        pass                                  # published; at worst a second name for the same data stays


_NOREPLACE = {}


def _libc():
    if 'libc' not in _NOREPLACE:
        try:
            _NOREPLACE['libc'] = ctypes.CDLL(ctypes.util.find_library('c') or None, use_errno=True)
        except (OSError, TypeError):
            _NOREPLACE['libc'] = None
    return _NOREPLACE['libc']


def _rename_noreplace(src, dst):
    """Atomic rename that fails if `dst` exists. True when done, False when the platform or the file
    system has no such rename (the caller falls back), FileExistsError when `dst` exists."""
    if os.name == 'nt':
        return False                          # Windows uses os.rename, which never replaces
    libc = _libc()
    if libc is None:
        return False
    if sys.platform.startswith('linux'):
        fn = getattr(libc, 'renameat2', None)
        args = (-100, os.fsencode(src), -100, os.fsencode(dst), 1)        # AT_FDCWD, RENAME_NOREPLACE
        argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    elif sys.platform == 'darwin':
        fn = getattr(libc, 'renamex_np', None)
        args = (os.fsencode(src), os.fsencode(dst), 0x4)                  # RENAME_EXCL
        argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    else:
        return False
    if fn is None:
        return False
    fn.argtypes, fn.restype = argtypes, ctypes.c_int
    if fn(*args) == 0:
        return True
    err = ctypes.get_errno()
    if err == errno.EEXIST:
        raise FileExistsError(err, os.strerror(err), dst)
    if err in (errno.EINVAL, errno.ENOSYS, errno.ENOTSUP, getattr(errno, 'EOPNOTSUPP', errno.ENOTSUP)):
        return False
    raise OSError(err, os.strerror(err), dst)


def _publish_via_placeholder(tmp, path, _before_replace=None):
    """Last resort without hard links or a no-replace rename: create an empty placeholder exclusively
    (fails if anything exists), check right before the swap that the placeholder is still ours (same
    file, still empty) and then replace it atomically. `_before_replace` is a test seam."""
    name = os.path.basename(path)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o644)
    except FileExistsError:
        raise CollisionError([name])
    try:
        mine = os.fstat(fd)
    finally:
        os.close(fd)
    try:
        if _before_replace is not None:
            _before_replace()
        now = os.lstat(path)
        if (now.st_dev, now.st_ino) != (mine.st_dev, mine.st_ino) or now.st_size != 0:
            raise CollisionError([name])       # someone else replaced our placeholder: leave theirs
        os.replace(tmp, path)
    except CollisionError:
        raise
    except BaseException:
        try:
            now = os.lstat(path)
            if (now.st_dev, now.st_ino) == (mine.st_dev, mine.st_ino):
                os.remove(path)               # our own empty placeholder
        except OSError:
            pass
        raise


def atomic_write(path, data, *, overwrite=False, _before_publish=None):
    """Write bytes to `path` through a temporary file in the same directory.

    overwrite=False never replaces anything at `path`, even if another writer creates it between the
    checks and the publication (see _publish_no_clobber). overwrite=True uses os.replace. The
    temporary file is removed on every failure. `_before_publish` is a test seam.
    """
    directory = os.path.dirname(path)
    # Anything already at the name (file, link, dangling link) is a collision first: on Windows the
    # real path of a dangling link can keep 8.3 short names and would otherwise look "outside".
    if not overwrite and os.path.lexists(path):
        raise CollisionError([os.path.basename(path)])
    if not _inside(directory, path):
        raise ExportError('refusing to write outside the output directory')
    tmp = os.path.join(directory, f'.{os.path.basename(path)}.{secrets.token_hex(4)}{TMP_SUFFIX}')
    try:
        with open(tmp, 'xb') as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if _before_publish is not None:
            _before_publish()
        if overwrite:
            os.replace(tmp, path)
        else:
            _publish_no_clobber(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


# Stable, path-free error codes for shareable metadata (details stay in the local UI report).
_MESSAGES = {
    'exists': 'a file with this name already exists',
    'permission_denied': 'permission denied by the operating system',
    'not_found': 'the folder does not exist or was removed',
    'bad_path': 'the output path is not a usable folder',
    'no_space': 'not enough disk space',
    'id_overflow': 'object id too large for this format',
    'encode_failed': 'the image could not be encoded',
    'export_failed': 'the file could not be exported',
    'os_error': 'operating system error',
    'internal_error': 'internal error',
}


def error_code(exc):
    from .encode import EncodeError, IdOverflowError
    import errno
    if isinstance(exc, CollisionError) or isinstance(exc, FileExistsError):
        return 'exists'
    if isinstance(exc, IdOverflowError):
        return 'id_overflow'
    if isinstance(exc, EncodeError):
        return 'encode_failed'
    if isinstance(exc, ExportError):
        return 'export_failed'
    if isinstance(exc, PermissionError):
        return 'permission_denied'
    if isinstance(exc, FileNotFoundError):
        return 'not_found'
    if isinstance(exc, (IsADirectoryError, NotADirectoryError)):
        return 'bad_path'
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return 'no_space'
    if isinstance(exc, OSError):
        return 'os_error'
    return 'internal_error'


def safe_message(code):
    return _MESSAGES.get(code, _MESSAGES['internal_error'])


_ABS_PATHS = [
    re.compile(r'(?:(?<![A-Za-z])[A-Za-z]:[\\/]|\\\\)[^\s"\'<>|*?]*'),  # Windows drive or UNC paths
    re.compile(r'(?<![\w.~:/-])/[^\s/"\'<>]+(?:/[^\s/"\'<>]*)*'),  # POSIX absolute paths (1+ segments)
    re.compile(r'~[\\/][^\s"\'<>]*'),                                  # home-relative paths
]


def redact_paths(text):
    """Replace absolute file system paths in free text with <path>."""
    for rx in _ABS_PATHS:
        text = rx.sub('<path>', text)
    return text


class Failure:
    """A failed file: `code` and `message` are safe to share; `detail` is for the local report only."""
    __slots__ = ('name', 'code', 'message', 'detail')

    def __init__(self, name, exc):
        self.name = name
        self.code = error_code(exc)
        self.message = safe_message(self.code)
        self.detail = f'{type(exc).__name__}: {exc}'

    def as_dict(self):
        return dict(file=self.name, code=self.code, message=self.message)

    def __iter__(self):                      # (name, detail) for callers that unpack pairs
        return iter((self.name, self.detail))


def write_batch(the_plan, producers, workers=4):
    """producers: dict key -> zero-argument callable returning bytes.

    Writes every planned file, continuing after individual failures.
    Returns dict(written=[name], failed=[Failure]).
    """
    written, failed = [], []
    directory = os.path.dirname(the_plan['files'][0][2]) if the_plan['files'] else None
    if directory:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            return dict(written=[], failed=[Failure(n, exc) for _k, n, _p in the_plan['files']])

    def one(item):
        key, name, path = item
        try:
            data = producers[key]()
            atomic_write(path, data, overwrite=the_plan.get('overwrite', False))
            return name, None
        except Exception as exc:  # report per file, keep going
            return name, Failure(name, exc)

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
            failed.append(err)
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
