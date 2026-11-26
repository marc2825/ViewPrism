# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate and build the ViewPrism extension ZIP with Blender's own tooling, then audit it.

    python tools/build_extension.py --blender <blender.exe> [--out dist]

The add-on sources (viewprism/) are staged together with the repository LICENSE (GPL-3.0-or-later
requires distributed copies to include the license text) and built with
`blender --command extension build`. The build fails if validation fails or if the ZIP contains
anything other than add-on files + LICENSE (no tests, harness, caches, VCS data, private data).
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'viewprism'
LICENSE = ROOT / 'LICENSE'
ALLOWED = re.compile(r'^(blender_manifest\.toml|LICENSE|[a-z_][a-z0-9_]*\.py)$')

sys.path.insert(0, str(Path(__file__).resolve().parent))
from privacy_scan import scan_text  # noqa: E402


def run(cmd, log):
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    log.write(f'$ {" ".join(map(str, cmd))}\n{proc.stdout}{proc.stderr}\nexit {proc.returncode}\n\n')
    return proc


def stage(dst):
    """Copy the add-on sources (no caches) plus LICENSE into a fresh staging directory."""
    for f in sorted(SRC.iterdir()):
        if f.is_file() and f.suffix in ('.py', '.toml'):
            shutil.copy2(f, dst / f.name)
    shutil.copy2(LICENSE, dst / 'LICENSE')
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blender', required=True)
    ap.add_argument('--out', type=Path, default=ROOT / 'dist')
    a = ap.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    version = re.search(r'^version\s*=\s*"([^"]+)"', (SRC / 'blender_manifest.toml').read_text(encoding='utf-8'), re.M).group(1)
    zpath = out / f'viewprism-{version}.zip'
    if zpath.exists():
        zpath.unlink()
    logp = out / 'build.log'
    ok = True
    staging = stage(Path(tempfile.mkdtemp(prefix='viewprism-stage-')))
    with logp.open('w', encoding='utf-8') as log:
        v = run([a.blender, '--factory-startup', '--command', 'extension', 'validate', str(staging)], log)
        ok &= v.returncode == 0
        b = run([a.blender, '--factory-startup', '--command', 'extension', 'build', '--source-dir', str(staging),
                 '--output-filepath', str(zpath)], log)
        ok &= b.returncode == 0 and zpath.is_file()
        if ok:
            vz = run([a.blender, '--factory-startup', '--command', 'extension', 'validate', str(zpath)], log)
            ok &= vz.returncode == 0
    shutil.rmtree(staging, ignore_errors=True)
    problems = []
    if zpath.is_file():
        with zipfile.ZipFile(zpath) as zf:
            names = zf.namelist()
            if 'LICENSE' not in names:
                problems.append('LICENSE missing from the ZIP')
            elif zf.read('LICENSE') != LICENSE.read_bytes():
                problems.append('LICENSE in the ZIP differs from the repository LICENSE')
            for n in names:
                if not ALLOWED.match(n):
                    problems.append(f'unexpected file in ZIP: {n}')
                for finding in scan_text(zf.read(n).decode('utf-8', errors='replace'), n):
                    problems.append(f'{n}: {finding}')
    op_version = re.search(r"^VERSION = '([^']+)'", (SRC / 'operators.py').read_text(encoding='utf-8'), re.M)
    if not op_version or op_version.group(1) != version:
        problems.append(f'operators.VERSION does not match manifest version {version}')
    print(logp.read_text(encoding='utf-8'))
    if zpath.is_file():
        print('ZIP:', zpath, f'({zpath.stat().st_size} bytes)')
        with zipfile.ZipFile(zpath) as zf:
            for n in sorted(zf.namelist()):
                print('  ', n)
    for p in problems:
        print('PROBLEM:', p)
    ok &= not problems
    print('BUILD', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
