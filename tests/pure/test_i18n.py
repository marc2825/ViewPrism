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


if __name__ == '__main__':
    unittest.main()
