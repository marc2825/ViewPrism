import json
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from viewprism import exr, export, png, writer  # noqa: E402


def synthetic_result(h=6, w=8):
    """Hand-made capture result with known values (independent of the GPU path)."""
    depth = np.full((h, w), np.nan, np.float32)
    depth[1:4, 1:5] = 2.0
    depth[2:5, 4:7] = 6.0
    mask = np.isfinite(depth)
    normal = np.zeros((h, w, 3), np.float32)
    normal[mask] = (0, 0, 1)
    normal[2:5, 4:7] = (0.6, 0, 0.8)
    ids = np.zeros((h, w), np.uint32)
    ids[1:4, 1:5] = 1
    ids[2:5, 4:7] = 2
    return dict(depth=depth, normal=normal, object_id=ids, mask=mask,
                id_map={1: 'Near', 2: 'Far ünïcödé'}, warnings=['w1'], stats={'s': 1},
                info=dict(width=w, height=h, projection='PERSPECTIVE', near=.1, far=100.0,
                          view_matrix=np.eye(4).tolist(), projection_matrix=np.eye(4).tolist(),
                          frame=7, blender='test'))


class Names(unittest.TestCase):
    def test_sanitize(self):
        self.assertEqual(export.sanitize_stem('  shot_01 '), 'shot_01')
        self.assertEqual(export.sanitize_stem('深度テスト'), '深度テスト')
        for bad in ('', '   ', 'a/b', 'a\\b', 'x:y', 'q?', '.hidden', '..', 'CON', 'nul.txt', 'a\x01b', 'x' * 300):
            with self.assertRaises(export.NameError_, msg=bad):
                export.sanitize_stem(bad)

    def test_items(self):
        items = export.output_items({'depth': ['EXR', 'PNG16'], 'mask': ['PNG8'], 'object_id': ['PNG16']})
        self.assertEqual([k for k, _s, _e in items], ['depth:PNG16', 'depth:EXR', 'object_id:PNG16', 'mask:PNG8'])
        with self.assertRaises(export.ExportError):
            export.output_items({'depth': ['PNG8', 'PNG16']})
        with self.assertRaises(export.ExportError):
            export.output_items({'mask': ['EXR']})

    def test_plan_auto_and_none(self):
        items = export.output_items({'depth': ['PNG8']})
        with tempfile.TemporaryDirectory() as d:
            p1 = export.plan(d, 'shot', items)
            self.assertEqual(p1['stem'], 'shot_0001')
            open(os.path.join(d, 'shot_0001_meta.json'), 'w').close()     # any member clashes
            self.assertEqual(export.plan(d, 'shot', items)['stem'], 'shot_0002')
            p = export.plan(d, 'exact', items, numbering='NONE')
            self.assertEqual([n for _k, n, _p in p['files']], ['exact_depth.png', 'exact_meta.json'])
            open(os.path.join(d, 'exact_depth.png'), 'w').close()
            with self.assertRaises(export.CollisionError) as cm:
                export.plan(d, 'exact', items, numbering='NONE')
            self.assertEqual(cm.exception.names, ['exact_depth.png'])
            self.assertTrue(export.plan(d, 'exact', items, numbering='NONE', overwrite=True)['overwrite'])


class Writing(unittest.TestCase):
    def test_atomic_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.bin')
            export.atomic_write(path, b'one')
            with self.assertRaises(export.CollisionError):
                export.atomic_write(path, b'two')
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(), b'one')
            export.atomic_write(path, b'two', overwrite=True)
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(), b'two')
            self.assertEqual([f for f in os.listdir(d) if f.endswith('.viewprism-tmp')], [])

    def test_batch_partial_failure_reports_each_file(self):
        with tempfile.TemporaryDirectory() as d:
            items = export.output_items({'depth': ['PNG8'], 'mask': ['PNG8']})
            p = export.plan(d, 'b', items, meta=False)

            def boom():
                raise RuntimeError('encoder exploded')
            st = export.write_batch(p, {'depth:PNG8': lambda: b'ok', 'mask:PNG8': boom})
            self.assertEqual(st['written'], ['b_0001_depth.png'])
            self.assertEqual(len(st['failed']), 1)
            self.assertIn('encoder exploded', st['failed'][0][1])
            self.assertEqual(sorted(os.listdir(d)), ['b_0001_depth.png'])

    def test_unwritable_directory(self):
        with tempfile.TemporaryDirectory() as d:
            ro = os.path.join(d, 'ro')
            os.mkdir(ro)
            if os.name == 'nt':
                user = os.environ.get('USERNAME')
                subprocess.run(['icacls', ro, '/deny', f'{user}:(W,AD)'], check=True, capture_output=True)
            else:
                os.chmod(ro, 0o500)
            try:
                res = writer.export_capture(synthetic_result(), dict(writer.default_options(), outputs={'mask': ['PNG8']}), ro)
                self.assertEqual(res['written'], [])
                self.assertEqual(len(res['failed']), 2)      # mask + meta, each reported
            finally:
                if os.name == 'nt':
                    subprocess.run(['icacls', ro, '/remove:d', user], check=True, capture_output=True)
                else:
                    os.chmod(ro, 0o700)

    def test_directory_is_a_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'file')
            open(f, 'w').close()
            res = writer.export_capture(synthetic_result(), writer.default_options(), os.path.join(f, 'sub'))
            self.assertEqual(res['written'], [])
            self.assertTrue(res['failed'])


class EndToEnd(unittest.TestCase):
    def test_all_outputs_roundtrip(self):
        r = synthetic_result()
        opts = writer.default_options()
        opts['outputs'] = {'depth': ['PNG16', 'EXR'], 'normal': ['PNG8', 'EXR'],
                           'object_id': ['PNG16', 'EXR'], 'mask': ['PNG8']}
        with tempfile.TemporaryDirectory() as d:
            res = writer.export_capture(r, opts, d)
            self.assertEqual(res['failed'], [])
            stem = res['stem']
            names = sorted(os.listdir(d))
            self.assertEqual(names, sorted(f'{stem}_{s}' for s in (
                'depth.png', 'depth.exr', 'normal.png', 'normal.exr', 'id.png', 'id.exr', 'mask.png', 'meta.json')))
            rd = lambda n: open(os.path.join(d, f'{stem}_{n}'), 'rb').read()
            # depth PNG16: near(2.0) -> 65535, far(6.0) -> 0, background -> 0 (far colour)
            dp = png.decode(rd('depth.png'))[0][..., 0]
            self.assertEqual(int(dp[1, 1]), 65535)
            self.assertEqual(int(dp[3, 5]), 0)
            self.assertEqual(int(dp[0, 0]), 0)
            # depth EXR is raw & bit exact
            ch, _ = exr.decode(rd('depth.exr'))
            np.testing.assert_array_equal(ch['Z'], r['depth'])
            np.testing.assert_array_equal(ch['A'], r['mask'].astype(np.float32))
            # normal PNG8: (0,0,1) -> (128,128,255), (0.6,0,0.8) -> round(1.6*127.5)=204
            npng = png.decode(rd('normal.png'))[0]
            np.testing.assert_array_equal(npng[1, 1], [128, 128, 255])
            np.testing.assert_array_equal(npng[3, 5], [204, 128, 230])
            np.testing.assert_array_equal(npng[0, 0], [0, 0, 0])
            ch, _ = exr.decode(rd('normal.exr'))
            np.testing.assert_array_equal(np.stack([ch['R'], ch['G'], ch['B']], -1), r['normal'])
            # ids exact in both encodings
            np.testing.assert_array_equal(png.decode(rd('id.png'))[0][..., 0], r['object_id'])
            np.testing.assert_array_equal(exr.decode(rd('id.exr'))[0]['id'], r['object_id'])
            np.testing.assert_array_equal(png.decode(rd('mask.png'))[0][..., 0] == 255, r['mask'])
            meta = json.loads(rd('meta.json').decode('utf-8'))
            self.assertEqual(meta['id_map'], {'1': 'Near', '2': 'Far ünïcödé'})
            self.assertEqual(meta['passes']['depth']['png']['range'], [2.0, 6.0])
            self.assertEqual(meta['frame'], 7)
            self.assertEqual(meta['failed_files'], [])
            self.assertEqual(sorted(meta['files'].values()), sorted(n for n in names if not n.endswith('meta.json')))
            text = rd('meta.json').decode('utf-8')
            self.assertNotIn(d, text)                         # no absolute paths
            self.assertNotIn(os.path.expanduser('~'), text)

    def test_unicode_directory_and_name(self):
        r = synthetic_result()
        opts = dict(writer.default_options(), outputs={'depth': ['PNG16', 'EXR'], 'mask': ['PNG8']},
                    base_name='深度テスト é')
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, '出力 フォルダ', 'ñ')
            res = writer.export_capture(r, opts, sub)
            self.assertEqual(res['failed'], [])
            self.assertTrue(res['stem'].startswith('深度テスト é_'))
            z = exr.decode(open(os.path.join(sub, f"{res['stem']}_depth.exr"), 'rb').read())[0]['Z']
            np.testing.assert_array_equal(z, r['depth'])

    def test_normal_flip_only_changes_png(self):
        r = synthetic_result()
        opts = dict(writer.default_options(), outputs={'normal': ['PNG8', 'EXR']})
        opts['normal'] = {'background': (0, 0, 0), 'flip_x': True, 'flip_y': True}
        with tempfile.TemporaryDirectory() as d:
            res = writer.export_capture(r, opts, d)
            stem = res['stem']
            npng = png.decode(open(os.path.join(d, f'{stem}_normal.png'), 'rb').read())[0]
            # (0.6, 0, 0.8) flipped -> (-0.6, -0, 0.8) -> round((-0.6*0.5+0.5)*255)=51, 128, 230
            np.testing.assert_array_equal(npng[3, 5], [51, 128, 230])
            ch, _ = exr.decode(open(os.path.join(d, f'{stem}_normal.exr'), 'rb').read())
            np.testing.assert_array_equal(ch['R'], r['normal'][..., 0])          # raw stays canonical
            meta = json.load(open(os.path.join(d, f'{stem}_meta.json'), encoding='utf-8'))
            self.assertEqual(meta['passes']['normal']['png']['mapping'], 'rgb = (-n.x, -n.y, n.z) * 0.5 + 0.5')

    def test_id_overflow_fails_only_that_file(self):
        r = synthetic_result()
        r['object_id'] = r['object_id'].copy()
        r['object_id'][1, 1] = 70000
        opts = dict(writer.default_options(), outputs={'object_id': ['PNG16', 'EXR']})
        with tempfile.TemporaryDirectory() as d:
            res = writer.export_capture(r, opts, d)
            self.assertEqual([n for n, _e in res['failed']], [f"{res['stem']}_id.png"])
            self.assertIn(f"{res['stem']}_id.exr", res['written'])
            meta = json.load(open(os.path.join(d, f"{res['stem']}_meta.json"), encoding='utf-8'))
            self.assertEqual(meta['failed_files'][0]['file'], f"{res['stem']}_id.png")
            self.assertNotIn('object_id:PNG16', meta['files'])

    def test_missing_pass_is_an_error_not_a_silent_skip(self):
        r = synthetic_result()
        del r['normal']
        opts = dict(writer.default_options(), outputs={'normal': ['PNG8']})
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(export.ExportError):
                writer.export_capture(r, opts, d)
            self.assertEqual(os.listdir(d), [])


if __name__ == '__main__':
    unittest.main()
