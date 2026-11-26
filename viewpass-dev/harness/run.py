"""Run independent Blender checks. No external Python packages required."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def evaluate_result(code, result_path):
    if code != 0:
        return False, f'Blender exit code {code}'
    try:
        result = json.loads(result_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return False, f'missing/invalid result: {exc}'
    if not isinstance(result, dict) or result.get('status') != 'pass':
        return False, f'not passed: {result}'
    return True, 'pass'


def run_one(blender, repo, out, mode, timeout):
    result = out / f'{mode}.json'
    log = out / f'{mode}.log'
    cmd = [str(blender), '--factory-startup', '--disable-autoexec']
    if mode == 'background':
        cmd += ['--background']
    cmd += ['--python-exit-code', '1', '--python', str(HERE / 'blender_check.py'),
            '--', '--repo', str(repo), '--result', str(result), '--mode', mode]
    print(f'Running {mode}: {cmd}', flush=True)
    try:
        with log.open('w', encoding='utf-8') as f:
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
        ok, message = evaluate_result(proc.returncode, result)
    except (OSError, subprocess.TimeoutExpired) as exc:
        ok, message = False, str(exc)
    print(f'{mode}: {message}; log: {log}', flush=True)
    return ok


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--blender', required=True, help='Blender executable or executable name on PATH')
    p.add_argument('--repo', type=Path, default=HERE.parent.parent)
    p.add_argument('--out', type=Path)
    p.add_argument('--mode', choices=['all', 'background', 'gpu'], default='all')
    p.add_argument('--timeout', type=int, default=180)
    a = p.parse_args()
    if a.timeout <= 0:
        p.error('timeout must be positive')
    repo = a.repo.resolve()
    if not (repo / 'viewpass' / '__init__.py').is_file():
        p.error(f'product package not implemented: {repo / "viewpass"}')
    if a.out:
        out = a.out.resolve()
        out.mkdir(parents=True, exist_ok=False)
    else:
        out = Path(tempfile.mkdtemp(prefix='viewpass-harness-'))
    print(f'Results: {out}', flush=True)
    modes = ['background', 'gpu'] if a.mode == 'all' else [a.mode]
    results = [run_one(a.blender, repo, out, m, a.timeout) for m in modes]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
