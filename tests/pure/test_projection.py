import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from viewprism import projection as P  # noqa: E402


def gl_persp(l, r, b, t, n, f):
    # Textbook glFrustum, written independently of the product helpers.
    return np.array([[2*n/(r-l), 0, (r+l)/(r-l), 0],
                     [0, 2*n/(t-b), (t+b)/(t-b), 0],
                     [0, 0, -(f+n)/(f-n), -2*f*n/(f-n)],
                     [0, 0, -1, 0]], dtype=float)


def gl_ortho(l, r, b, t, n, f):
    return np.array([[2/(r-l), 0, 0, -(r+l)/(r-l)],
                     [0, 2/(t-b), 0, -(t+b)/(t-b)],
                     [0, 0, -2/(f-n), -(f+n)/(f-n)],
                     [0, 0, 0, 1]], dtype=float)


class ClassifyAndClip(unittest.TestCase):
    def test_perspective(self):
        p = gl_persp(-1, 1, -.5, .5, .25, 80)
        self.assertEqual(P.classify(p), P.PERSPECTIVE)
        kind, n, f = P.clip_range(p)
        self.assertAlmostEqual(n, .25, places=12)
        self.assertAlmostEqual(f, 80, places=9)

    def test_off_center_perspective(self):
        p = gl_persp(-.2, 1.4, -.3, .9, .1, 10)
        kind, n, f = P.clip_range(p)
        self.assertEqual(kind, P.PERSPECTIVE)
        self.assertAlmostEqual(n, .1, places=12)
        self.assertAlmostEqual(f, 10, places=9)

    def test_orthographic_negative_near(self):
        p = gl_ortho(-2, 2, -1, 1, -500, 500)
        kind, n, f = P.clip_range(p)
        self.assertEqual(kind, P.ORTHOGRAPHIC)
        self.assertAlmostEqual(n, -500, places=9)
        self.assertAlmostEqual(f, 500, places=9)

    def test_infinite_far(self):
        p = gl_persp(-1, 1, -1, 1, .1, 1e9)
        p[2, 2], p[2, 3] = -1.0, -0.2       # limit f -> inf
        kind, n, f = P.clip_range(p)
        self.assertTrue(math.isinf(f))
        mode, near, scale = P.depth_mapping(p)
        self.assertEqual(mode, P.DEPTH_LOG)
        self.assertGreater(scale, 0)

    def test_generic(self):
        p = np.eye(4)
        p[3] = (0.1, 0, -1, 0.5)
        self.assertEqual(P.classify(p), P.GENERIC)
        self.assertEqual(P.depth_mapping(p)[0], P.DEPTH_HARDWARE)

    def test_invalid(self):
        with self.assertRaises(P.ProjectionError):
            P.as_matrix([[1, 2], [3, 4]])
        bad = np.eye(4)
        bad[0, 0] = np.nan
        with self.assertRaises(P.ProjectionError):
            P.as_matrix(bad)
        with self.assertRaises(P.ProjectionError):
            P.validate_projection(np.zeros((4, 4)))
        # near/far swapped perspective -> invalid range
        p = gl_persp(-1, 1, -1, 1, 10, 1)
        with self.assertRaises(P.ProjectionError):
            P.clip_range(p)


class DepthMapping(unittest.TestCase):
    def test_log_mapping_endpoints(self):
        p = gl_persp(-1, 1, -1, 1, .01, 1000)
        mode, near, scale = P.depth_mapping(p)
        self.assertEqual(mode, P.DEPTH_LOG)
        self.assertAlmostEqual(math.log(.01 / near) * scale, 0.0, places=9)
        self.assertAlmostEqual(math.log(1000 / near) * scale, 1.0, places=9)

    def test_log_mapping_resolves_millimetres_at_100m(self):
        # float32 depth buffer, adjacent surfaces 5 mm apart at 100 m (viewport defaults)
        p = gl_persp(-1, 1, -1, 1, .01, 1000)
        _m, near, scale = P.depth_mapping(p)
        a = np.float32(math.log(100.0 / near) * scale)
        b = np.float32(math.log(100.005 / near) * scale)
        self.assertLess(a, b)
        # the hyperbolic hardware depth collapses them (motivation for the remap)
        def hw(z):
            ndc = (-(1000+.01)/(1000-.01)*-z - 2*1000*.01/(1000-.01)) / z
            return np.float32(ndc * .5 + .5)
        self.assertEqual(hw(100.0), hw(100.005))

    def test_linear_mapping_ortho(self):
        p = gl_ortho(-1, 1, -1, 1, 2, 12)
        mode, near, scale = P.depth_mapping(p)
        self.assertEqual(mode, P.DEPTH_LINEAR)
        self.assertAlmostEqual((7 - near) * scale, .5, places=12)


class CropAndShift(unittest.TestCase):
    def test_crop_keeps_square_pixels_and_centre(self):
        # 16:9 source cropped to 1:1 must keep full height, cut width symmetrically.
        p = gl_persp(-16/9*.1, 16/9*.1, -.1, .1, .1, 100)
        c = P.crop_to_aspect(p, 16/9, 1.0)
        view = np.eye(4)
        # a point on the top edge centre of the source stays on the top edge
        col, row, _d, _z = P.project(c, view, [(0, 5, -5)], 100, 100)   # tan = 1 = top edge
        self.assertAlmostEqual(row[0], 0.0, places=9)
        self.assertAlmostEqual(col[0], 50.0, places=9)
        # 45 deg to the right: inside the 16:9 source, exactly the right edge of the 1:1 crop
        col, row, _d, _z = P.project(c, view, [(5, 0, -5)], 100, 100)
        self.assertAlmostEqual(col[0], 100.0, places=9)   # x extent = height extent -> square
        # wide output from square source keeps width
        s = gl_persp(-.1, .1, -.1, .1, .1, 100)
        c2 = P.crop_to_aspect(s, 1.0, 2.0)
        col, row, _d, _z = P.project(c2, view, [(5, 2.5, -5)], 200, 100)
        self.assertAlmostEqual(col[0], 200.0, places=9)
        self.assertAlmostEqual(row[0], 0.0, places=9)

    def test_ortho_shift(self):
        p = gl_ortho(-2, 2, -1, 1, -500, 500)
        view = np.eye(4)
        view[:3, 3] = (0, 0, -10)        # eye 10 units in front of origin
        v2, p2, shift = P.shift_ortho_origin_to_near(view, p)
        self.assertAlmostEqual(shift, 500)
        pts = [(0, 0, 0), (1, .5, 3), (-1.5, -.2, -40)]
        a = P.project(p, view, pts, 40, 20)
        b = P.project(p2, v2, pts, 40, 20)
        np.testing.assert_allclose(a[0], b[0], atol=1e-9)    # same pixels
        np.testing.assert_allclose(a[1], b[1], atol=1e-9)
        np.testing.assert_allclose(a[3], b[3], atol=1e-9)    # same clip z (same visibility)
        np.testing.assert_allclose(b[2], a[2] + 500, atol=1e-9)
        self.assertTrue((b[2] > 0).all())
        k, n, f = P.clip_range(p2)
        self.assertAlmostEqual(n, 0.0, places=9)
        self.assertAlmostEqual(f, 1000.0, places=6)
        # no-op for positive near and for perspective
        po = gl_ortho(-1, 1, -1, 1, .1, 10)
        self.assertEqual(P.shift_ortho_origin_to_near(view, po)[2], 0.0)
        pp = gl_persp(-1, 1, -1, 1, .1, 10)
        self.assertEqual(P.shift_ortho_origin_to_near(view, pp)[2], 0.0)

    def test_locked_height(self):
        self.assertEqual(P.locked_height(1920, 1234, 567), round(1920 * 567 / 1234))
        self.assertEqual(P.locked_height(1, 1000, 10), 1)


class ProjectPixels(unittest.TestCase):
    def test_pixel_centres_top_left(self):
        p = gl_ortho(-2, 2, -1, 1, .1, 10)     # 4 x 2 units on 8 x 4 px -> 0.5 unit pixels
        col, row, d, _ = P.project(p, np.eye(4), [(-1.75, .75, -3), (1.75, -.75, -4)], 8, 4)
        np.testing.assert_allclose(col, [.5, 7.5])
        np.testing.assert_allclose(row, [.5, 3.5])
        np.testing.assert_allclose(d, [3, 4])


if __name__ == '__main__':
    unittest.main()
