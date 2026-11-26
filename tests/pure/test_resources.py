# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resource limits (issue #5): memory guard and chunked encoders that must stay bit-identical."""
import os
import sys
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from viewprism import encode as E  # noqa: E402
from viewprism import exr, png, resources  # noqa: E402

rng = np.random.default_rng(5)


class Guard(unittest.TestCase):
    def test_estimate(self):
        est = resources.estimate(100, 50)
        self.assertEqual(est['pixels'], 5000)
        self.assertEqual(est['gpu_bytes'], 5000 * resources.GPU_BYTES_PER_PIXEL)
        self.assertEqual(est['cpu_bytes'], 5000 * (resources.CAPTURE_BYTES_PER_PIXEL + resources.EXPORT_BYTES_PER_PIXEL))
        self.assertLess(resources.estimate(100, 50, export=False)['cpu_bytes'], est['cpu_bytes'])

    def test_hard_limit_uses_committable_memory(self):
        need = resources.estimate(7680, 4320)['cpu_bytes']
        commit = int(need / resources.HARD_FRACTION) - 1
        with self.assertRaises(resources.ResourceError) as cm:
            resources.check(7680, 4320, memory=dict(physical=10 ** 12, commit=commit))
        self.assertIn('lower the resolution', str(cm.exception))
        est = resources.check(7680, 4320, memory=dict(physical=10 ** 12, commit=commit + 2))
        self.assertIsNone(est['warning'])

    def test_soft_limit_warns_about_paging(self):
        need = resources.estimate(3840, 2160)['cpu_bytes']
        est = resources.check(3840, 2160, memory=dict(physical=need, commit=10 ** 12))
        self.assertIn('may be slow', est['warning'])
        est = resources.check(3840, 2160, memory=dict(physical=int(need / resources.SOFT_FRACTION) + 1,
                                                      commit=10 ** 12))
        self.assertIsNone(est['warning'])

    def test_unknown_memory_does_not_block(self):
        est = resources.check(16384, 2048, memory=dict(physical=None, commit=None))
        self.assertIsNone(est['warning'])

    def test_available_memory_on_this_system(self):
        mem = resources.available_memory()
        if sys.platform.startswith(('win', 'linux')):
            self.assertGreater(mem['physical'], 0)
            self.assertGreaterEqual(mem['commit'], 0)


class ChunkedEncoders(unittest.TestCase):
    def _depth_cases(self):
        d = rng.uniform(0.5, 40.0, size=(37, 23)).astype(np.float32)
        m = rng.random((37, 23)) > 0.3
        d[~m] = np.nan
        d[3, 3] = np.inf                       # non-finite foreground
        m[3, 3] = True
        flat = np.where(m, np.float32(5.0), np.float32(np.nan))
        empty = np.full((9, 11), np.nan, np.float32)
        return [(d, m), (flat, np.isfinite(flat)), (empty, np.zeros_like(empty, bool))]

    def test_quantize_depth_matches_reference(self):
        with mock.patch.object(E, 'CHUNK_PIXELS', 50):           # force many chunks
            for d, m in self._depth_cases():
                for args in [('AUTO', None, None, True, 'FAR'), ('AUTO', None, None, False, 'NEAR'),
                             ('FIXED', 2.0, 30.0, True, 0.25), ('FIXED', 30.0, 2.0, False, 'FAR')]:
                    for bits in (8, 16):
                        ref_img, ref_info = E.normalize_depth(d, m, *args, dtype=np.float64)
                        q, info = E.quantize_depth(d, m, bits, *args)
                        np.testing.assert_array_equal(q, E.quantize(ref_img, bits), err_msg=str(args))
                        for k in ('lo', 'hi', 'flat', 'empty', 'invalid_foreground'):
                            self.assertEqual(info[k], ref_info[k], k)

    def test_quantize_normal_chunked(self):
        n = rng.normal(size=(41, 29, 3)).astype(np.float32)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        m = rng.random((41, 29)) > 0.25
        ref = {bits: E.quantize(E.normal_to_rgb(n, m, (0.5, 0.5, 1.0), np.float64), bits) for bits in (8, 16)}
        with mock.patch.object(E, 'CHUNK_PIXELS', 30):
            for bits in (8, 16):
                np.testing.assert_array_equal(E.quantize_normal(n, m, bits, (0.5, 0.5, 1.0)), ref[bits])

    def test_png_streaming_roundtrip(self):
        with mock.patch.object(png, 'CHUNK_BYTES', 64):          # a few rows per chunk
            for dtype, c in ((np.uint8, 1), (np.uint16, 3), (np.uint8, 4)):
                hi = np.iinfo(dtype).max
                a = rng.integers(0, hi + 1, size=(53, 31, c), dtype=np.int64).astype(dtype)
                a[20:] = a[19]                                   # repeated rows exercise the Up filter
                np.testing.assert_array_equal(png.decode(png.encode(a))[0], a)

    def test_exr_blocks_roundtrip_odd_height(self):
        z = rng.normal(size=(37, 19)).astype(np.float32)
        ids = rng.integers(0, 1000, size=(37, 19)).astype(np.uint32)
        out, _ = exr.decode(exr.encode({'Z': z, 'id': ids}, 'ZIP'))
        np.testing.assert_array_equal(out['Z'], z)
        np.testing.assert_array_equal(out['id'], ids)


if __name__ == '__main__':
    unittest.main()
