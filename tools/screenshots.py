# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regenerate docs/images with an isolated, empty Blender user directory (no private data).

    python tools/screenshots.py --blender <blender.exe>
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument('--blender', required=True)
a = ap.parse_args()
env = dict(os.environ, BLENDER_USER_RESOURCES=tempfile.mkdtemp(prefix='viewprism-shots-userres-'))
cmd = [a.blender, '--factory-startup', '--disable-autoexec', '--enable-event-simulate',
       '--python', str(ROOT / 'tools' / 'make_screenshots.py'), '--',
       '--repo', str(ROOT), '--out', str(ROOT / 'docs' / 'images')]
proc = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
print(proc.stdout[-3000:], proc.stderr[-2000:])
if 'SHOTS OK' not in proc.stdout:
    sys.exit(1)
# Published images must not carry text/EXIF metadata (Blender writes an EXIF resolution chunk).
sys.path.insert(0, str(ROOT / 'tools'))
from privacy_scan import strip_png_metadata  # noqa: E402
for png in sorted((ROOT / 'docs' / 'images').glob('*.png')):
    removed = strip_png_metadata(png)
    if removed:
        print('stripped', ','.join(removed), 'from', png.name)
sys.exit(0)
