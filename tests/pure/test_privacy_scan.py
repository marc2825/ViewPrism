# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Negative fixtures for tools/privacy_scan.py. All sensitive-looking values are clearly synthetic and
assembled at runtime, so this file itself never contains a matchable value."""
import os
import struct
import sys
import tempfile
import unittest
import zlib

import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', 'tools')))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..')))
import privacy_scan as ps  # noqa: E402
from viewprism import png  # noqa: E402

AT = '@'
BS = '\\'


def rules(text):
    return [f.split(': ')[1] for f in ps.scan_text(text, 'x')]


class Detects(unittest.TestCase):
    def test_emails_any_provider(self):
        for addr in ('someone' + AT + 'mail.' + 'jp', 'first.last+tag' + AT + 'corp-mail.' + 'co.uk'):
            self.assertIn('email address', rules(f'contact {addr} please'), addr)

    def test_allowed_addresses(self):
        for addr in ('123+user' + AT + 'users.noreply.github.' + 'com', 'noreply' + AT + 'github.com',
                     'dev' + AT + 'example.' + 'org', 'a' + AT + 'b.' + 'invalid'):
            self.assertEqual(rules(addr), [], addr)

    def test_user_paths(self):
        cases = {
            'C:' + BS + 'Users' + BS + 'alice' + BS + 'x': 'Windows user path',
            'D:/' + 'Users' + '/bob/renders': 'Windows user path',
            '/' + 'Users' + '/carol/Desktop': 'macOS user path',
            '/' + 'home' + '/dave/.config': 'Linux home path',
            BS + BS + 'wsl$' + BS + 'Ubuntu' + BS + 'home': 'WSL path',
        }
        for text, rule in cases.items():
            self.assertIn(rule, rules(text), text)

    def test_placeholders_are_fine(self):
        for text in ('<HOME>' + BS + 'AppData', 'C:' + BS + 'Users' + BS + '<name>' + BS + 'x',
                     '/' + 'home' + '/runner/work', '/' + 'Users' + '/Shared/x'):
            self.assertEqual(rules(text), [], text)

    def test_credential_formats(self):
        cases = {
            'gh' + 'p_' + 'A' * 36: 'GitHub token',
            'AK' + 'IA' + 'A' * 16: 'AWS access key',
            '-----BEGIN ' + 'OPENSSH ' + 'PRIVATE KEY-----': 'private key',
            'api_' + 'key = "' + 'Z' * 20 + '"': 'credential assignment',
        }
        for text, rule in cases.items():
            self.assertIn(rule, rules(text), rule)

    def test_values_are_masked(self):
        token = 'gh' + 'p_' + 'B' * 36
        out = ' '.join(ps.scan_text(f'token {token}', 'x'))
        self.assertNotIn(token, out)


class PngMetadata(unittest.TestCase):
    def _with_text_chunk(self):
        data = png.encode(np.zeros((2, 2), np.uint8))
        body = b'Author\x00someone'
        chunk = struct.pack('>I', len(body)) + b'tEXt' + body + struct.pack('>I', zlib.crc32(b'tEXt' + body) & 0xFFFFFFFF)
        i = data.index(b'IDAT') - 4
        return data[:i] + chunk + data[i:]

    def test_detect_and_strip(self):
        data = self._with_text_chunk()
        self.assertEqual(len(ps.png_metadata(data, 'a.png')), 1)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'a.png')
            with open(p, 'wb') as fh:
                fh.write(data)
            self.assertEqual(ps.strip_png_metadata(p), ['tEXt'])
            with open(p, 'rb') as fh:
                stripped = fh.read()
            self.assertEqual(ps.png_metadata(stripped, 'a.png'), [])
            np.testing.assert_array_equal(png.decode(stripped)[0], png.decode(data)[0])   # pixels intact

    def test_own_encoder_writes_no_metadata(self):
        self.assertEqual(ps.png_metadata(png.encode(np.zeros((3, 3, 3), np.uint8)), 'b.png'), [])


if __name__ == '__main__':
    unittest.main()
