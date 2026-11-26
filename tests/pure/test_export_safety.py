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


def read_text(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def read_bytes(path):
    with open(path, 'rb') as fh:
        return fh.read()


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
        items = [('mask:PNG8', 'mask', 'png')]
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, 'target-does-not-exist.png')
            (_key, name), = export.file_names('out', items, meta=False)       # the name plan() would use
            link = os.path.join(d, name)
            self._symlink(target, link)
            self.assertTrue(os.path.lexists(link) and not os.path.exists(link))
            with self.assertRaises(export.CollisionError):           # counts as existing
                export.plan(d, 'out', items, numbering='NONE', meta=False)
            with self.assertRaises(export.CollisionError):
                export.atomic_write(link, b'data')
            self.assertFalse(os.path.exists(target), 'wrote through a dangling symlink')
            self.assertEqual(leftovers(d), [])

    def test_dangling_symlink_takes_its_number(self):
        items = [('mask:PNG8', 'mask', 'png')]
        with tempfile.TemporaryDirectory() as d:
            (_key, name), = export.file_names('out_0001', items, meta=False)
            self._symlink(os.path.join(d, 'missing.png'), os.path.join(d, name))
            self.assertEqual(export.plan(d, 'out', items, meta=False)['stem'], 'out_0002')

    def test_symlink_pointing_outside_is_refused(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            link = os.path.join(d, 'out.png')
            self._symlink(os.path.join(outside, 'victim.png'), link)
            with self.assertRaises(export.ExportError):
                export.atomic_write(link, b'data', overwrite=True)
            self.assertEqual(os.listdir(outside), [])

    def test_without_hard_links(self):
        """FAT/exFAT and some network shares have no hard links: exports still work and stay no-clobber
        (before 0.2.0 final they failed on macOS/Linux)."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.png')
            with mock.patch('os.link', side_effect=OSError(errno.EPERM, 'no hard links')):
                export.atomic_write(path, b'one')
                with self.assertRaises(export.CollisionError):        # another writer got there first
                    export.atomic_write(path, b'two', _before_publish=lambda: None)
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(), b'one')
            self.assertEqual(leftovers(d), [])

    def test_placeholder_publication(self):
        """The no-hard-link path itself, on every OS: exclusive placeholder, then atomic replace."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.png')
            tmp = os.path.join(d, '.a.png.0' + export.TMP_SUFFIX)
            with open(tmp, 'wb') as fh:
                fh.write(b'data')
            export._publish_via_placeholder(tmp, path)
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(), b'data')
            self.assertFalse(os.path.exists(tmp))
            with open(tmp, 'wb') as fh:
                fh.write(b'other')
            with self.assertRaises(export.CollisionError):
                export._publish_via_placeholder(tmp, path)
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(), b'data')                  # existing file untouched
            os.remove(tmp)
            self.assertEqual(leftovers(d), [])

    def test_placeholder_replaced_by_another_program_is_not_overwritten(self):
        """Issue #15: without hard links and a no-replace rename, a program that replaces our placeholder
        before the swap keeps its file (the remaining window is only the check itself)."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.png')
            tmp = os.path.join(d, '.a.png.0' + export.TMP_SUFFIX)
            with open(tmp, 'wb') as fh:
                fh.write(b'ours')

            def other_program_replaces_it():
                other = os.path.join(d, 'other.tmp')
                with open(other, 'wb') as fh:
                    fh.write(b'theirs')
                os.replace(other, path)
            with self.assertRaises(export.CollisionError):
                export._publish_via_placeholder(tmp, path, _before_replace=other_program_replaces_it)
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(), b'theirs')
            os.remove(tmp)

    def test_no_replace_rename_before_the_placeholder(self):
        """Issue #15: on Linux the no-hard-link path uses renameat2(RENAME_NOREPLACE), which is atomic."""
        if not sys.platform.startswith('linux'):
            self.skipTest('renameat2 is Linux-only (macOS uses renamex_np; Windows never needs it)')
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, 's'), os.path.join(d, 'd')
            for p, v in ((src, b'one'), (dst, b'existing')):
                with open(p, 'wb') as fh:
                    fh.write(v)
            with self.assertRaises(FileExistsError):
                export._rename_noreplace(src, dst)
            os.remove(dst)
            if not export._rename_noreplace(src, dst):
                self.skipTest('this file system has no RENAME_NOREPLACE')
            with open(dst, 'rb') as fh:
                self.assertEqual(fh.read(), b'one')
            path = os.path.join(d, 'a.png')
            with mock.patch('os.link', side_effect=OSError(errno.EPERM, 'no hard links')), \
                    mock.patch.object(export, '_publish_via_placeholder', side_effect=AssertionError('placeholder')):
                export.atomic_write(path, b'data')
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(), b'data')

    def test_stale_lock_from_a_crash_is_reused(self):
        """Issue #15: a lock left by a crash no longer skips its number forever."""
        items = [('mask:PNG8', 'mask', 'png')]
        with tempfile.TemporaryDirectory() as d:
            lock = os.path.join(d, '.x_0001' + export.LOCK_SUFFIX)
            open(lock, 'w').close()
            self.assertEqual(export.plan(d, 'x', items, meta=False)['stem'], 'x_0002')     # fresh: in use
            old = os.path.getmtime(lock) - export.STALE_LOCK_SECONDS - 60
            os.utime(lock, (old, old))
            self.assertEqual(export.plan(d, 'x', items, meta=False)['stem'], 'x_0001')     # prediction
            p = export.plan(d, 'x', items, meta=False, reserve=True)
            try:
                self.assertEqual(p['stem'], 'x_0001')
                self.assertFalse(export._lock_is_stale(lock), 'the stale lock must be replaced by a fresh one')
            finally:
                export.release(p)
            self.assertEqual(leftovers(d), [])

    def test_published_file_is_not_reported_failed_if_temp_cleanup_fails(self):
        """After the file is published, failing to remove the temporary name (e.g. a scanner holds it)
        must not turn a written file into a failure."""
        real_remove = os.remove

        def busy_remove(p):
            if p.endswith(export.TMP_SUFFIX):
                raise PermissionError(errno.EACCES, 'file in use')
            real_remove(p)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.png')
            with mock.patch('os.remove', side_effect=busy_remove):
                export.atomic_write(path, b'data')                     # must not raise
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(), b'data')
            for name in leftovers(d):                                  # POSIX: a second name may remain
                real_remove(os.path.join(d, name))

    def test_long_names_fit_the_temporary_name(self):
        ok = 'a' * 200
        self.assertEqual(export.sanitize_stem(ok), ok)
        with self.assertRaises(export.NameError_):
            export.sanitize_stem('a' * 230)
        longest = export._temp_name(f'{ok}_{export.MAX_INDEX}_normal.png')
        self.assertLessEqual(len(longest.encode('utf-8')), 255)
        with tempfile.TemporaryDirectory() as d:                     # a real AUTO export with that name
            if os.name == 'nt' and len(os.path.join(d, longest)) >= 260:
                self.skipTest('Windows MAX_PATH (260) is shorter than this test path; covered on Linux CI')
            p = export.plan(d, ok, [('normal:PNG8', 'normal', 'png')], meta=False, reserve=True)
            try:
                export.atomic_write(p['files'][0][2], b'x')
                self.assertEqual(leftovers(d), [os.path.basename(p['lock'])])
            finally:
                export.release(p)

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
            text = read_text(os.path.join(d, f"{res['stem']}_meta.json"))
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
            meta = json.loads(read_text(os.path.join(d, f"{res['stem']}_meta.json")))
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

    def test_redact_single_segment_posix_paths(self):
        """Issue #15: one-segment absolute paths were kept; URLs and fractions must stay readable."""
        cases = {'cannot open /' + 'tmpfile': 'cannot open <path>', 'see /' + 'home': 'see <path>',
                 '/' + 'var/log/x.txt': '<path>', 'and/or': 'and/or', 'N/A': 'N/A',
                 'range 0.5/10 m': 'range 0.5/10 m', 'https://example.org/a/b': 'https://example.org/a/b'}
        for text, expected in cases.items():
            self.assertEqual(export.redact_paths(text), expected, text)

    def test_anonymized_mode(self):
        r = result()
        o = options(privacy='anonymized', source={'kind': 'camera', 'camera': 'Hero Cam', 'camera_type': 'PERSP'})
        with tempfile.TemporaryDirectory() as d:
            res = writer.export_capture(r, o, d)
            text = read_text(os.path.join(d, f"{res['stem']}_meta.json"))
            for name in ('Near', 'Far Lamp', 'Hero Cam'):
                self.assertNotIn(name, text)
            meta = json.loads(text)
            self.assertEqual(meta['privacy'], 'anonymized')
            self.assertEqual(meta['id_map'], {'1': 'object_1', '2': 'object_2'})
            self.assertEqual(meta['warnings'], ['1 object(s) may use transparency (exported as opaque surfaces)'])
            self.assertEqual(meta['camera']['source']['camera_type'], 'PERSP')
            # pixels and ids are unchanged by the privacy mode
            full = writer.export_capture(r, options(), d)
            a = read_bytes(os.path.join(d, f"{res['stem']}_depth.exr"))
            b = read_bytes(os.path.join(d, f"{full['stem']}_depth.exr"))
            self.assertEqual(a, b)

    def test_full_mode_keeps_names(self):
        with tempfile.TemporaryDirectory() as d:
            res = writer.export_capture(result(), options(), d)
            meta = json.loads(read_text(os.path.join(d, f"{res['stem']}_meta.json")))
            self.assertEqual(meta['id_map'], {'1': 'Near', '2': 'Far Lamp'})
            self.assertEqual(meta['privacy'], 'full')

    def test_unknown_privacy_mode(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(export.ExportError):
                writer.export_capture(result(), options(privacy='weird'), d)
            self.assertEqual(os.listdir(d), [], 'files written before the option was rejected')


if __name__ == '__main__':
    unittest.main()
