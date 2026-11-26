# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from viewprism import encode as E  # noqa: E402

nan = np.nan


class DepthNormalize(unittest.TestCase):
    def setUp(self):
        self.d = np.array([[2.0, 4.0], [nan, 3.0]], np.float32)
        self.m = np.isfinite(self.d)

    def test_auto_near_white(self):
        img, info = E.normalize_depth(self.d, self.m)
        self.assertEqual((info['lo'], info['hi']), (2.0, 4.0))
        np.testing.assert_allclose(img, [[1.0, 0.0], [0.0, 0.5]])   # bg = far colour = 0
        self.assertEqual(img.dtype, np.float32)

    def test_auto_far_white(self):
        img, _ = E.normalize_depth(self.d, self.m, near_white=False)
        np.testing.assert_allclose(img, [[0.0, 1.0], [1.0, 0.5]])   # bg = far colour = 1

    def test_background_independent(self):
        img, _ = E.normalize_depth(self.d, self.m, background=0.25)
        self.assertAlmostEqual(float(img[1, 0]), 0.25)
        img, _ = E.normalize_depth(self.d, self.m, background='NEAR')
        self.assertAlmostEqual(float(img[1, 0]), 1.0)
        with self.assertRaises(E.EncodeError):
            E.normalize_depth(self.d, self.m, background=2.0)

    def test_empty(self):
        d = np.full((3, 3), nan, np.float32)
        img, info = E.normalize_depth(d, np.zeros((3, 3), bool))
        self.assertTrue(info['empty'])
        self.assertTrue((img == 0).all())

    def test_constant(self):
        d = np.array([[5.0, 5.0], [nan, 5.0]])
        img, info = E.normalize_depth(d, np.isfinite(d))
        self.assertTrue(info['flat'])
        np.testing.assert_allclose(img, [[1, 1], [0, 1]])
        img, _ = E.normalize_depth(d, np.isfinite(d), near_white=False)
        np.testing.assert_allclose(img, [[0, 0], [1, 0]])

    def test_fixed_clamps_and_reversed(self):
        d = np.array([[0.0, 1.0, 2.0, 3.0, 4.0]])
        m = np.ones_like(d, bool)
        img, _ = E.normalize_depth(d, m, 'FIXED', 1.0, 3.0)
        np.testing.assert_allclose(img, [[1, 1, .5, 0, 0]])
        img, _ = E.normalize_depth(d, m, 'FIXED', 3.0, 1.0)            # reversed range flips the ramp
        np.testing.assert_allclose(img, [[0, 0, .5, 1, 1]])
        with self.assertRaises(E.EncodeError):
            E.normalize_depth(d, m, 'FIXED', 2.0, 2.0)
        with self.assertRaises(E.EncodeError):
            E.normalize_depth(d, m, 'FIXED', 1.0, float('inf'))
        with self.assertRaises(E.EncodeError):
            E.normalize_depth(d, m, 'BOGUS')

    def test_nonfinite_foreground_is_background(self):
        d = np.array([[1.0, np.inf, 3.0]])
        m = np.ones_like(d, bool)
        img, info = E.normalize_depth(d, m)
        self.assertEqual(info['invalid_foreground'], 1)
        np.testing.assert_allclose(img, [[1, 0, 0]])

    def test_raw_not_modified(self):
        d = self.d.copy()
        E.normalize_depth(d, self.m, 'FIXED', 0, 1)
        np.testing.assert_array_equal(d, self.d)


class Others(unittest.TestCase):
    def test_quantize(self):
        np.testing.assert_array_equal(E.quantize([0.0, 0.5, 1.0], 8), [0, 128, 255])
        np.testing.assert_array_equal(E.quantize([0.0, 1.0, 2.0, -1.0], 16), [0, 65535, 65535, 0])
        self.assertEqual(E.quantize([0.5], 16).dtype, np.uint16)
        with self.assertRaises(E.EncodeError):
            E.quantize([nan], 8)
        with self.assertRaises(E.EncodeError):
            E.quantize([0], 12)

    def test_normal_rgb(self):
        n = np.array([[[0, 0, 1], [1, 0, 0]], [[0, -1, 0], [0, 0, 0]]], np.float32)
        m = np.array([[True, True], [True, False]])
        rgb = E.normal_to_rgb(n, m, background=(0.5, 0.5, 1.0))
        np.testing.assert_allclose(rgb[0, 0], [.5, .5, 1])
        np.testing.assert_allclose(rgb[0, 1], [1, .5, .5])
        np.testing.assert_allclose(rgb[1, 0], [.5, 0, .5])
        np.testing.assert_allclose(rgb[1, 1], [.5, .5, 1])

    def test_fast_normal_quantization_matches_reference(self):
        rng = np.random.default_rng(7)
        n = rng.normal(size=(64, 64, 3)).astype(np.float32)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        # include exact tie candidates such as 0.8 -> 229.5 and axis-aligned values
        n[0, :6] = [(0.6, 0, 0.8), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, 0, -1), (0.8, -0.6, 0)]
        m = rng.random((64, 64)) > 0.2
        for bits in (8, 16):
            for bg in ((0, 0, 0), (0.5, 0.5, 1.0)):
                ref = E.quantize(E.normal_to_rgb(n, m, bg, np.float64), bits)
                np.testing.assert_array_equal(E.quantize_normal(n, m, bits, bg), ref)

    def test_id_roundtrip_and_overflow(self):
        ids = np.array([[0, 1], [65535, 300]], np.uint32)
        enc = E.encode_id_u16(ids)
        self.assertEqual(enc.dtype, np.uint16)
        np.testing.assert_array_equal(E.decode_id_u16(enc), ids)
        with self.assertRaises(E.IdOverflowError):
            E.encode_id_u16(np.array([65536], np.uint32))

    def test_mask_and_colors(self):
        np.testing.assert_array_equal(E.mask_to_u8([[True, False]]), [[255, 0]])
        ids = np.array([[0, 1, 2, 1]])
        c = E.id_colors(ids)
        np.testing.assert_array_equal(c[0, 0], [0, 0, 0])
        np.testing.assert_array_equal(c[0, 1], c[0, 3])
        self.assertFalse(np.array_equal(c[0, 1], c[0, 2]))


if __name__ == '__main__':
    unittest.main()
