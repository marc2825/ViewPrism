# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""UI translation. English is the default; Blender shows the Japanese text when its interface
language is Japanese (Preferences > Interface > Translation)."""
import bpy

from .i18n_data import CONTEXT, table


def iface(msg):
    """Translate a label or message for the interface (add-on context)."""
    return bpy.app.translations.pgettext_iface(msg, CONTEXT)


def rpt(msg):
    """Translate a report message (Info editor / status bar)."""
    return bpy.app.translations.pgettext_rpt(msg, CONTEXT)


def register():
    bpy.app.translations.register(__package__, table())


def unregister():
    bpy.app.translations.unregister(__package__)
