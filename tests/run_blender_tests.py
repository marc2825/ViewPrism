"""Run the ViewPass Blender test suites in fresh Blender processes.

    python tests/run_blender_tests.py --blender <blender.exe> [--suite gui|package|all] [--gpu-backend vulkan|opengl]

A suite passes only if Blender exits with code 0 and writes JSON with status == "pass".
Timeouts, missing results and skips are failures. Logs and JSON are kept in --out.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SUITES = {'gui': HERE / 'blender' / 'gui_suite.py', 'package': HERE / 'blender' / 'package_suite.py'}


def run(blender, suite, out, timeout, backend, only, extra):
    result = out / f'{suite}.json'
    log = out / f'{suite}.log'
    cmd = [blender, '--factory-startup', '--disable-autoexec']
    if backend:
        cmd += ['--gpu-backend', backend]
    if suite == 'package':
        cmd += ['--background']
    cmd += ['--python-exit-code', '1', '--python', str(SUITES[suite]), '--',
            '--repo', str(HERE.parent), '--result', str(result)]
    if only:
        cmd += ['--only', only]
    cmd += extra
    print('Running', suite, cmd, flush=True)
    try:
        with log.open('w', encoding='utf-8') as fh:
            code = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout).returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f'{suite}: FAIL ({exc}); log {log}')
        return False
    try:
        data = json.loads(result.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'{suite}: FAIL (no result: {exc}); log {log}')
        return False
    ok = code == 0 and isinstance(data, dict) and data.get('status') == 'pass'
    for r in data.get('results', []):
        line = f"  {r['status'].upper():4} {r['test']}"
        if r['status'] == 'pass':
            line += f"  {r.get('seconds', '')}s  {r.get('detail', '')}"
        print(line)
        if r['status'] != 'pass':
            print('    ' + r.get('traceback', '').strip().replace('\n', '\n    '))
    if 'traceback' in data:
        print(data['traceback'])
    print(f"{suite}: {'PASS' if ok else 'FAIL'} (exit {code}, gpu {data.get('gpu')}); log {log}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--blender', required=True)
    ap.add_argument('--suite', choices=['gui', 'package', 'all'], default='all')
    ap.add_argument('--gpu-backend', choices=['vulkan', 'opengl', 'metal'])
    ap.add_argument('--only', default='', help='comma separated test names (gui suite)')
    ap.add_argument('--zip', help='extension ZIP for the package suite')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--timeout', type=int, default=600)
    a = ap.parse_args()
    out = a.out.resolve() if a.out else Path(tempfile.mkdtemp(prefix='viewpass-tests-'))
    out.mkdir(parents=True, exist_ok=True)
    print('Results:', out)
    suites = ['gui', 'package'] if a.suite == 'all' else [a.suite]
    ok = True
    for s in suites:
        extra = ['--zip', str(Path(a.zip).resolve())] if (s == 'package' and a.zip) else []
        if s == 'package' and not a.zip:
            print('package: FAIL (--zip is required; build it with tools/build_extension.py)')
            ok = False
            continue
        ok &= run(a.blender, s, out, a.timeout, a.gpu_backend, a.only if s == 'gui' else '', extra)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
