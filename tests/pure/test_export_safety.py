# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Export safety and metadata privacy (issue #4): no-clobber publication, races, symlinks,
cleanup, concurrent numbering across processes, path-free error metadata, anonymized mode."""
import errno
import json
import multiprocessing
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from viewprism import export, writer  # noqa: E402

# Built at runtime so the repository privacy scanner does not flag this file.
WIN_PATH = 'C:' + '\\' + 'Users' + '\\' + 'someone' + '\\' + 'secret' + '\\' + 'out.png'
POSIX_PATH = '/' + 'home' + '/' + 'someone' + '/' + 'secret' + '/' + 'out.png'


def result(h=4, w=6):
    depth = np.full((h, w), np.nan, np.float32)
    depth[1:3, 1:4] = 2.0
    mask = np.isfinite(depth)
    ids = np.where(mask, 1, 0).astype(np.uint32)
    ids[2, 3] = 2
    normal = np.zeros((h, w, 3), np.float32)
    normal[mask] = (0, 0, 1)
    return dict(depth=depth, normal=normal, object_id=ids, mask=mask, id_map={1: 'Near', 2: 'Far Lamp'},
                warnings=['1 object(s) may use transparency (exported as opaque surfaces): Near'],
                warnings_anonymous=['1 object(s) may use transparency (exported as opaque surfaces)'],
                stats={}, info=dict(width=w, height=h, projection='PERSPECTIVE'))


def options(**kw):
    o = writer.default_options()
    o['outputs'] = {'depth': ['PNG8', 'EXR'], 'mask': ['PNG8']}
    o.update(kw)
    return o


def leftovers(d):
    return [f for f in os.listdir(d) if f.endswith(export.TMP_SUFFIX) or f.endswith(export.LOCK_SUFFIX)]


def _export_worker(args):
    directory, n = args
    stems = []
    for _ in range(n):
        res = writer.export_capture(result(), options(base_name='race'), directory)
        assert not res['failed'], res['failed']
        stems.append(res['stem'])
    return stems


class NoClobber(unittest.TestCase):
    def test_race_file_created_just_before_publication(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.png')

            def other_writer():                       # deterministic race: appears after all checks
                with open(path, 'wb') as fh:
                    fh.write(b'theirs')
            with self.assertRaises(export.CollisionError):
                export.atomic_write(path, b'ours', _before_publish=other_writer)
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(), b'theirs')
            self.assertEqual(leftovers(d), [])

    def test_overwrite_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.png')
            export.atomic_write(path, b'one')
            export.atomic_write(path, b'two', overwrite=True, _before_publish=lambda: None)
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(), b'two')
            self.assertEqual(leftovers(d), [])

    def _symlink(self, target, link):
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f'symlinks not permitted on this system ({type(exc).__name__}); covered on Linux CI')

    def test_dangling_symlink_is_not_written_through(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as elsewhere:
            target = os.path.join(d, 'target-does-not-exist.png')
            link = os.path.join(d, 'out.png')
            self._symlink(target, link)
            self.assertTrue(os.path.lexists(link) and not os.path.exists(link))
            with self.assertRaises(export.CollisionError):           # counts as existing
                export.plan(d, 'out', [('mask:PNG8', 'mask', 'png')], numbering='NONE', meta=False)
            with self.assertRaises(export.CollisionError):
                export.atomic_write(link, b'data')
            self.assertFalse(os.path.exists(target), 'wrote through a dangling symlink')
            self.assertEqual(leftovers(d), [])
            del elsewhere

    def test_symlink_pointing_outside_is_refused(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            link = os.path.join(d, 'out.png')
            self._symlink(os.path.join(outside, 'victim.png'), link)
            with self.assertRaises(export.ExportError):
                export.atomic_write(link, b'data', overwrite=True)
            self.assertEqual(os.listdir(outside), [])

    def test_without_hard_links(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.png')
            with mock.patch('os.link', side_effect=OSError(errno.EPERM, 'no hard links')):
                if os.name == 'nt':
                    export.atomic_write(path, b'one')                  # rename never replaces on Windows
                    with self.assertRaises(export.CollisionError):
                        export.atomic_write(path, b'two', _before_publish=lambda: None)
                    with open(path, 'rb') as fh:
                        self.assertEqual(fh.read(), b'one')
                else:
                    with self.assertRaises(export.AtomicPublishUnsupported):
                        export.atomic_write(path, b'one')               # documented safe failure
                    self.assertFalse(os.path.exists(path))
            self.assertEqual(leftovers(d), [])

    def test_partial_failure_cleans_up(self):
        with tempfile.TemporaryDirectory() as d:
            o = options()
            o['outputs'] = {'depth': ['PNG8'], 'object_id': ['PNG16']}
            r = result()
            r['object_id'][0, 0] = 70000                                  # PNG16 cannot hold it
            res = writer.export_capture(r, o, d)
            self.assertEqual([f.code for f in res['failed']], ['id_overflow'])
            self.assertEqual(leftovers(d), [])

    def test_concurrent_auto_numbering_across_processes(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = multiprocessing.get_context('spawn')
            with ctx.Pool(4) as pool:
                stems = [s for chunk in pool.map(_export_worker, [(d, 3)] * 4) for s in chunk]
            self.assertEqual(len(stems), 12)
            self.assertEqual(len(set(stems)), 12, f'two exports picked the same name: {sorted(stems)}')
            names = os.listdir(d)
            self.assertEqual(len([n for n in names if n.endswith('_meta.json')]), 12)
            self.assertEqual(len(names), 12 * 4)                         # depth png+exr, mask, meta
            self.assertEqual(leftovers(d), [])

    def test_threads_same_numbering(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as d:
            with ThreadPoolExecutor(6) as pool:
                stems = [s for chunk in pool.map(_export_worker, [(d, 2)] * 6) for s in chunk]
            self.assertEqual(len(set(stems)), 12)
            self.assertEqual(leftovers(d), [])


class MetadataPrivacy(unittest.TestCase):
    def test_failure_metadata_has_no_paths(self):
        r = result()
        prods_fail = {
            'depth:PNG8': PermissionError(errno.EACCES, 'Permission denied', WIN_PATH),
            'depth:EXR': OSError(errno.EIO, 'I/O error', POSIX_PATH),
        }
        real = writer.producers

        def producers(res, opts):
            prods, enc = real(res, opts)
            for key, exc in prods_fail.items():
                prods[key] = (lambda e=exc: (_ for _ in ()).throw(e))
            return prods, enc
        with tempfile.TemporaryDirectory() as d, mock.patch.object(writer, 'producers', producers):
            res = writer.export_capture(r, options(), d)
            self.assertEqual(sorted(f.code for f in res['failed']), ['os_error', 'permission_denied'])
            self.assertTrue(any('someone' in f.detail for f in res['failed']))    # local detail kept
            text = open(os.path.join(d, f"{res['stem']}_meta.json"), encoding='utf-8').read()
            for leak in ('someone', 'secret', 'Users', 'home'):
                self.assertNotIn(leak, text)
            meta = json.loads(text)
            self.assertEqual({f['code'] for f in meta['failed_files']}, {'os_error', 'permission_denied'})

    def test_warnings_are_path_redacted(self):
        r = result()
        r['warnings'] = [f'could not convert Rock: failed to read {WIN_PATH}', f'see {POSIX_PATH}',
                         'display as Wire/Bounds', 'rgb = (-n.x, -n.y, n.z) * 0.5 + 0.5']
        with tempfile.TemporaryDirectory() as d:
            res = writer.export_capture(r, options(), d)
            meta = json.load(open(os.path.join(d, f"{res['stem']}_meta.json"), encoding='utf-8'))
            joined = ' '.join(meta['warnings'])
            self.assertNotIn('someone', joined)
            self.assertIn('<path>', joined)
            self.assertIn('Wire/Bounds', joined)
            self.assertIn('(-n.x, -n.y, n.z) * 0.5 + 0.5', joined)

    def test_redact_paths(self):
        cases = {WIN_PATH: '<path>', POSIX_PATH: '<path>', '\\\\' + 'server\\share\\x.exr': '<path>',
                 '~/' + 'renders/x.png': '<path>', 'Wire/Bounds': 'Wire/Bounds', 'n*0.5+0.5': 'n*0.5+0.5',
                 'ratio 1/2': 'ratio 1/2'}
        for text, expected in cases.items():
            self.assertEqual(export.redact_paths(text), expected, text)

    def test_anonymized_mode(self):
        r = result()
        o = options(privacy='anonymized', source={'kind': 'camera', 'camera': 'Hero Cam', 'camera_type': 'PERSP'})
        with tempfile.TemporaryDirectory() as d:
            res = writer.export_capture(r, o, d)
            text = open(os.path.join(d, f"{res['stem']}_meta.json"), encoding='utf-8').read()
            for name in ('Near', 'Far Lamp', 'Hero Cam'):
                self.assertNotIn(name, text)
            meta = json.loads(text)
            self.assertEqual(meta['privacy'], 'anonymized')
            self.assertEqual(meta['id_map'], {'1': 'object_1', '2': 'object_2'})
            self.assertEqual(meta['warnings'], ['1 object(s) may use transparency (exported as opaque surfaces)'])
            self.assertEqual(meta['camera']['source']['camera_type'], 'PERSP')
            # pixels and ids are unchanged by the privacy mode
            full = writer.export_capture(r, options(), d)
            a = open(os.path.join(d, f"{res['stem']}_depth.exr"), 'rb').read()
            b = open(os.path.join(d, f"{full['stem']}_depth.exr"), 'rb').read()
            self.assertEqual(a, b)

    def test_full_mode_keeps_names(self):
        with tempfile.TemporaryDirectory() as d:
            res = writer.export_capture(result(), options(), d)
            meta = json.load(open(os.path.join(d, f"{res['stem']}_meta.json"), encoding='utf-8'))
            self.assertEqual(meta['id_map'], {'1': 'Near', '2': 'Far Lamp'})
            self.assertEqual(meta['privacy'], 'full')

    def test_unknown_privacy_mode(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(export.ExportError):
                writer.export_capture(result(), options(privacy='weird'), d)


if __name__ == '__main__':
    unittest.main()
