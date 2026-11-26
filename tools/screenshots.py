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
env = dict(os.environ, BLENDER_USER_RESOURCES=tempfile.mkdtemp(prefix='viewpass-shots-userres-'))
cmd = [a.blender, '--factory-startup', '--disable-autoexec', '--enable-event-simulate',
       '--python', str(ROOT / 'tools' / 'make_screenshots.py'), '--',
       '--repo', str(ROOT), '--out', str(ROOT / 'docs' / 'images')]
proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
print(proc.stdout[-3000:], proc.stderr[-2000:])
sys.exit(0 if 'SHOTS OK' in proc.stdout else 1)
