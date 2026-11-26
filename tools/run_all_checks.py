# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run every ViewPrism check and store sanitised evidence in docs/evidence/<date>/.

    python tools/run_all_checks.py --blender <blender.exe> [--backends vulkan,opengl] [--bench]

Steps (each must pass; skips are reported as NOT RUN, never as PASS):
  1. pure unit tests (Blender's bundled Python, no bpy)
  2. independent harness self-test (system Python)
  3. independent harness, background + GPU, once per GPU backend
  4. ViewPrism GUI/GPU suite, once per GPU backend
  5. extension validate/build/audit
  6. package install/enable/export/disable/uninstall in an isolated user directory
  7. (optional) benchmark + Cycles/EEVEE comparison
Local user paths are replaced by placeholders before anything is written to docs/.
"""
import argparse
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sanitise(text):
    home = str(Path.home())
    user = os.environ.get('USERNAME') or os.environ.get('USER') or ''
    for variant in {home, home.replace('\\', '/'), home.replace('\\', '\\\\'), home.replace('/', '\\')}:
        text = text.replace(variant, '<HOME>')
    if user and len(user) > 2:
        text = re.sub(rf'(?i)(?<![A-Za-z0-9]){re.escape(user)}(?![A-Za-z0-9])', '<USER>', text)
    return text


def wrapper(blender, backend, tmp):
    """Launcher that forwards a GPU backend flag (the harness calls Blender directly)."""
    if os.name == 'nt':
        p = Path(tmp) / f'blender_{backend}.cmd'
        p.write_text(f'@echo off\r\n"{blender}" --gpu-backend {backend} %*\r\nexit /b %ERRORLEVEL%\r\n', encoding='utf-8')
    else:
        p = Path(tmp) / f'blender_{backend}.sh'
        p.write_text(f'#!/bin/sh\nexec "{blender}" --gpu-backend {backend} "$@"\n', encoding='utf-8')
        p.chmod(0o755)
    return str(p)


STEPS = ('pure', 'selftest', 'harness', 'gui', 'build', 'package', 'bench')
DEFAULT_STEPS = 'pure,selftest,harness,gui,build,package'


def bundled_python(blender):
    """Blender's bundled interpreter (has NumPy); ignores e.g. python3.13-config on Linux."""
    name = re.compile(r'^python(\.exe|3(\.\d+)?)$')
    cands = [p for p in glob.glob(str(Path(blender).resolve().parent / '*' / 'python' / 'bin' / 'python*'))
             if name.match(Path(p).name)]
    return sorted(cands)[-1] if cands else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blender', required=True)
    ap.add_argument('--backends', default='vulkan,opengl')
    ap.add_argument('--steps', default=DEFAULT_STEPS,
                    help=f'comma separated subset of {",".join(STEPS)}; only these are run and judged')
    ap.add_argument('--bench', action='store_true', help='same as adding "bench" to --steps')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    steps = {s for s in a.steps.split(',') if s} | ({'bench'} if a.bench else set())
    unknown = steps - set(STEPS)
    if unknown:
        ap.error(f'unknown steps: {sorted(unknown)}')
    stamp = datetime.date.today().isoformat()
    out = (a.out or ROOT / 'docs' / 'evidence' / stamp).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    tmp = Path(tempfile.mkdtemp(prefix='viewprism-checks-'))
    summary = []

    def record(name, ok, detail='', files=()):
        summary.append(dict(step=name, result='PASS' if ok else 'FAIL', detail=detail))
        for f in files:
            f = Path(f)
            if f.is_file():
                dst = out / f'{name}__{f.name}'
                dst.write_text(sanitise(f.read_text(encoding='utf-8', errors='replace')), encoding='utf-8')
        print(f'{name}: {"PASS" if ok else "FAIL"} {detail}', flush=True)

    def run(cmd, log, **kw):
        with open(log, 'w', encoding='utf-8') as fh:
            return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, **kw).returncode

    ver = subprocess.run([a.blender, '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    py = bundled_python(a.blender)
    # 1. pure
    log = tmp / 'pure.log'
    if 'pure' not in steps:
        pass
    elif py:
        code = run([py, '-m', 'unittest', 'discover', '-v', '-s', str(ROOT / 'tests' / 'pure'), '-p', 'test_*.py'], log, cwd=ROOT)
        txt = log.read_text(encoding='utf-8', errors='replace').strip()
        m = re.search(r'Ran (\d+) tests', txt)
        record('pure_unit_tests', code == 0 and txt.splitlines()[-1].startswith('OK'), f"{m.group(1) if m else '?'} tests", [log])
    else:
        summary.append(dict(step='pure_unit_tests', result='NOT RUN', detail='bundled Python not found'))
    # 2. harness self-test
    if 'selftest' in steps:
        log = tmp / 'harness_selftest.log'
        code = run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'viewpass-dev' / 'harness'), '-p', 'test_*.py'], log, cwd=ROOT)
        record('harness_selftest', code == 0, '', [log])
    backends = [b for b in a.backends.split(',') if b]
    for be in backends:
        exe = wrapper(a.blender, be, tmp)
        # 3. independent harness
        if 'harness' in steps:
            hout = tmp / f'harness_{be}'
            log = tmp / f'harness_{be}.log'
            code = run([sys.executable, str(ROOT / 'viewpass-dev' / 'harness' / 'run.py'), '--blender', exe, '--mode', 'all',
                        '--out', str(hout)], log, cwd=ROOT)
            record(f'harness_{be}', code == 0, '', [log, hout / 'background.json', hout / 'gpu.json',
                                                    hout / 'background.log', hout / 'gpu.log'])
        # 4. GUI suite
        if 'gui' not in steps:
            continue
        gout = tmp / f'gui_{be}'
        log = tmp / f'gui_{be}.log'
        code = run([sys.executable, str(ROOT / 'tests' / 'run_blender_tests.py'), '--blender', a.blender, '--gpu-backend', be,
                    '--suite', 'gui', '--out', str(gout)], log, cwd=ROOT)
        try:
            res = json.loads((gout / 'gui.json').read_text(encoding='utf-8'))
            n = len(res.get('results', []))
            npass = sum(r['status'] == 'pass' for r in res.get('results', []))
        except (OSError, ValueError):
            n = npass = 0
        record(f'gui_suite_{be}', code == 0, f'{npass}/{n} cases', [log, gout / 'gui.json', gout / 'gui.log'])
    # 5. build
    dist = tmp / 'dist'
    zips = []
    if 'build' in steps or 'package' in steps:
        log = tmp / 'build.log'
        code = run([sys.executable, str(ROOT / 'tools' / 'build_extension.py'), '--blender', a.blender, '--out', str(dist)], log, cwd=ROOT)
        zips = sorted(dist.glob('viewprism-*.zip'))
        record('extension_build', code == 0 and bool(zips), zips[0].name if zips else '', [log])
        if a.out and zips:
            shutil.copy2(zips[0], out / zips[0].name)
    # 6. package
    if 'package' not in steps:
        pass
    elif zips:
        pout = tmp / 'package'
        log = tmp / 'package_runner.log'
        code = run([sys.executable, str(ROOT / 'tests' / 'run_blender_tests.py'), '--blender', a.blender, '--suite', 'package',
                    '--zip', str(zips[0]), '--out', str(pout)], log, cwd=ROOT)
        record('package_lifecycle', code == 0, '', [log, pout / 'package.json', pout / 'package.log'])
    else:
        summary.append(dict(step='package_lifecycle', result='NOT RUN', detail='no ZIP'))
    # 7. benchmark
    if 'bench' in steps:
        bout = tmp / 'bench'
        log = tmp / 'bench.log'
        code = run([sys.executable, str(ROOT / 'tools' / 'benchmark.py'), '--blender', a.blender, '--runs', '5',
                    '--out', str(bout)], log, cwd=ROOT, timeout=3600)
        record('benchmark', code == 0, '', [log, bout / 'summary.json'])
    lines = [f'# ViewPrism check run {stamp}', '', f'- Blender: `{ver}`', f'- Platform: `{sys.platform}`',
             f'- Backends: {", ".join(backends)}', f'- Selected steps: {", ".join(s for s in STEPS if s in steps)}',
             '', '| Step | Result | Detail |', '|---|---|---|']
    lines += [f"| {s['step']} | {s['result']} | {s['detail']} |" for s in summary]
    if not summary:
        summary.append(dict(step='(none)', result='NOT RUN', detail='no step selected'))
    lines += ['', 'Files in this folder are the raw logs/JSON of each step with local paths replaced by `<HOME>`/`<USER>`.']
    (out / 'SUMMARY.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    ok = all(s['result'] == 'PASS' for s in summary)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
