# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Every user-visible string of the add-on has a Japanese translation with the same placeholders.

Strings are collected from the source with `ast`: iface()/rpt() arguments, property names and
descriptions, enum item names and descriptions, bl_label/bl_description, popover titles and the
label tables (PASS_LABELS, LABELS, FILE_NOTES)."""
import ast
import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
from viewprism import i18n_data  # noqa: E402

SRC = os.path.join(ROOT, 'viewprism')
UI_MODULES = ('props.py', 'operators.py', 'preview.py', 'ui.py')
PLACEHOLDER = re.compile(r'\{[^{}]*\}')


def _const(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def collect():
    names, tips = set(), set()
    for mod in UI_MODULES:
        with open(os.path.join(SRC, mod), encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
                if fn in ('iface', 'rpt') and node.args and _const(node.args[0]) is not None:
                    names.add(_const(node.args[0]))
                if fn.endswith('Property'):
                    for kw in node.keywords:
                        if kw.arg == 'name' and _const(kw.value):
                            names.add(_const(kw.value))
                        if kw.arg == 'description' and _const(kw.value):
                            tips.add(_const(kw.value))
            if (mod == 'props.py' and isinstance(node, ast.Tuple) and len(node.elts) == 3
                    and all(_const(e) is not None for e in node.elts)):
                _ident, name, desc = (_const(e) for e in node.elts)          # enum item
                names.add(name)
                if desc:
                    tips.add(desc)
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target, value = node.targets[0].id, node.value
                if target in ('bl_label', 'title') and _const(value):
                    names.add(_const(value))
                if target == 'bl_description' and _const(value):
                    tips.add(_const(value))
                if target in ('PASS_LABELS', 'LABELS', 'FILE_NOTES') and isinstance(value, ast.Dict):
                    names.update(_const(v) for v in value.values if _const(v))
    return names, tips


class Translations(unittest.TestCase):
    def test_every_ui_string_is_translated(self):
        names, tips = collect()
        self.assertGreater(len(names), 80)
        self.assertGreater(len(tips), 40)
        self.assertEqual(sorted(names - set(i18n_data.NAMES_JA)), [], 'labels/messages without Japanese')
        self.assertEqual(sorted(tips - set(i18n_data.TIPS_JA)), [], 'tooltips without Japanese')

    def test_placeholders_match(self):
        for table in (i18n_data.NAMES_JA, i18n_data.TIPS_JA):
            for en, ja in table.items():
                self.assertTrue(ja.strip(), en)
                self.assertEqual(PLACEHOLDER.findall(en), PLACEHOLDER.findall(ja), en)

    def test_no_unused_entries(self):
        names, tips = collect()
        self.assertEqual(sorted(set(i18n_data.NAMES_JA) - names), [], 'translations nothing uses')
        self.assertEqual(sorted(set(i18n_data.TIPS_JA) - tips), [], 'tooltip translations nothing uses')

    def test_table_shape(self):
        t = i18n_data.table()
        self.assertEqual(set(t), set(i18n_data.LOCALES))
        ja = t['ja_JP']
        self.assertEqual(ja[(i18n_data.CONTEXT, 'Depth')], '深度')
        self.assertNotIn(('*', 'Depth'), ja, 'short labels must not change Blender\'s own strings')
        tip = 'Output width in pixels'
        self.assertEqual(ja[('*', tip)], ja[(i18n_data.CONTEXT, tip)])


def _raised(fn, *args, **kw):
    try:
        fn(*args, **kw)
    except Exception as exc:        # noqa: BLE001 - the message is what is tested
        return str(exc)
    raise AssertionError(f'{fn.__name__} did not raise')


class Messages(unittest.TestCase):
    """Messages of the capture/file layers are translated when shown (they stay English in metadata).
    Samples come from the real functions, so a changed wording breaks this test instead of silently
    falling back to English."""

    def samples(self):
        import numpy as np
        from viewprism import encode, export, resources
        out = [_raised(export.sanitize_stem, ''), _raised(export.sanitize_stem, 'a/b'),
               _raised(export.sanitize_stem, '.x'), _raised(export.sanitize_stem, 'CON'),
               _raised(export.sanitize_stem, 'a' * 300),
               _raised(encode.normalize_depth, np.ones((2, 2), np.float32), np.ones((2, 2), bool), 'FIXED', 2.0, 2.0),
               _raised(encode.normalize_depth, np.ones((2, 2), np.float32), np.ones((2, 2), bool), 'FIXED',
                       float('nan'), 2.0),
               _raised(encode.background_value, 2.0, True),
               _raised(encode.encode_id_u16, np.array([[70000]]))]
        for export_too in (True, False):
            need = resources.estimate(7680, 4320, export=export_too)['cpu_bytes']
            out.append(_raised(resources.check, 7680, 4320, export=export_too, memory=dict(physical=None, commit=1)))
            out.append(resources.check(7680, 4320, export=export_too,
                                       memory=dict(physical=need // 2, commit=10 ** 13))['warning'])
        out += ['Run ViewPrism from a 3D Viewport', 'The 3D Viewport is too small', 'Camera view without an active camera',
                'The 3D Viewport used for this export was closed or changed; run the export again',
                'resolution 20000x100 exceeds the maximum side of 16384 px',
                'resolution 9000x9000 exceeds the limit of 33,554,432 pixels',
                'GPU error (out of memory); try a lower resolution', 'nothing visible: the capture is empty',
                '2 object(s) have different viewport/render modifier settings (viewport result exported): A, B',
                '1 object(s) may use transparency (exported as opaque surfaces)',
                '1 object(s) use shader displacement (not included: geometry only): Rock',
                '3 object(s) skipped: unsupported type VOLUME', '1 object(s) skipped: display as Wire',
                'the viewport clipping region (Alt+B) is not applied to the export']
        return out

    def test_known_messages_have_japanese(self):
        for text in self.samples():
            ja = i18n_data.translate_message(text, 'ja_JP')
            self.assertNotEqual(ja, text, f'no Japanese for: {text}')
            self.assertNotIn('{', ja, ja)

    def test_values_and_names_are_kept(self):
        ja = i18n_data.translate_message('2 object(s) have different viewport/render modifier settings '
                                         '(viewport result exported): Cube, Rock', 'ja_JP')
        self.assertTrue(ja.startswith('2 個') and ja.endswith(': Cube, Rock'), ja)
        self.assertIn('20000x100', i18n_data.translate_message(
            'resolution 20000x100 exceeds the maximum side of 16384 px', 'ja_JP'))

    def test_english_and_unknown_messages_pass_through(self):
        for text in self.samples():
            self.assertEqual(i18n_data.translate_message(text, 'en_US'), text)
        self.assertEqual(i18n_data.translate_message('something new', 'ja_JP'), 'something new')


if __name__ == '__main__':
    unittest.main()
