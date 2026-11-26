"""Validate and build the ViewPrism extension ZIP with Blender's own tooling, then audit it.

    python tools/build_extension.py --blender <blender.exe> [--out dist]

Fails if validation/build fails or if the ZIP contains anything other than add-on files
(no tests, harness, caches, VCS data, absolute user paths).
"""
import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'viewprism'
ALLOWED = re.compile(r'^(blender_manifest\.toml|[a-z_]+\.py)$')
PRIVATE = [re.compile(p, re.I) for p in (r'[A-Z]:\\Users\\', r'/home/[a-z]', r'/Users/[A-Za-z]', r'wsl\$', r'@gmail\.com')]


def run(cmd, log):
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    log.write(f'$ {" ".join(map(str, cmd))}\n{proc.stdout}{proc.stderr}\nexit {proc.returncode}\n\n')
    return proc


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
    with logp.open('w', encoding='utf-8') as log:
        v = run([a.blender, '--factory-startup', '--command', 'extension', 'validate', str(SRC)], log)
        ok &= v.returncode == 0
        b = run([a.blender, '--factory-startup', '--command', 'extension', 'build', '--source-dir', str(SRC),
                 '--output-filepath', str(zpath)], log)
        ok &= b.returncode == 0 and zpath.is_file()
        if ok:
            vz = run([a.blender, '--factory-startup', '--command', 'extension', 'validate', str(zpath)], log)
            ok &= vz.returncode == 0
    problems = []
    if zpath.is_file():
        with zipfile.ZipFile(zpath) as zf:
            names = zf.namelist()
            for n in names:
                if not ALLOWED.match(n):
                    problems.append(f'unexpected file in ZIP: {n}')
                text = zf.read(n).decode('utf-8', errors='replace')
                for pat in PRIVATE:
                    if pat.search(text):
                        problems.append(f'{n}: matches private pattern {pat.pattern}')
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
