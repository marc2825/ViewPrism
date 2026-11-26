"""Run the ViewPrism benchmark / render-pass comparison in fresh sandboxed Blender processes.

    python tools/benchmark.py --blender <blender.exe> [--runs 5] [--gpu-backend vulkan] [--out DIR]

Each run is a new factory-startup GUI process (the first capture of a process is the "cold"
sample). The first run of each scene also renders EEVEE/Cycles passes for comparison.
"""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blender', required=True)
    ap.add_argument('--runs', type=int, default=5)
    ap.add_argument('--scenes', default='simple,complex')
    ap.add_argument('--gpu-backend')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--timeout', type=int, default=900)
    a = ap.parse_args()
    out = a.out.resolve() if a.out else Path(tempfile.mkdtemp(prefix='viewprism-bench-'))
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    ok = True
    for scene in a.scenes.split(','):
        runs = []
        for i in range(a.runs):
            res = out / f'{scene}_{i}.json'
            cmd = [a.blender, '--factory-startup', '--disable-autoexec']
            if a.gpu_backend:
                cmd += ['--gpu-backend', a.gpu_backend]
            cmd += ['--python-exit-code', '1', '--python', str(HERE / 'bench_inner.py'), '--',
                    '--repo', str(HERE.parent), '--result', str(res), '--scene', scene]
            if i == 0:
                cmd += ['--compare']
            with (out / f'{scene}_{i}.log').open('w', encoding='utf-8') as fh:
                code = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=a.timeout).returncode
            try:
                data = json.loads(res.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                data = dict(status='fail', reason='no result')
            if code != 0 or data.get('status') != 'pass':
                ok = False
                print(scene, i, 'FAIL', data.get('traceback', data))
                continue
            runs.append(data)
            print(scene, i, f"cold {data['viewprism_cold_s']*1000:.1f} ms, warm median {data['viewprism_warm_median_s']*1000:.1f} ms")
        if not runs:
            continue
        cold = [r['viewprism_cold_s'] for r in runs]
        warm = [w for r in runs for w in r['viewprism_warm_s']]
        q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]
        summary[scene] = dict(
            runs=len(runs), scene_stats=runs[0]['scene_stats'], capture_stats=runs[0]['capture_stats'],
            gpu=runs[0]['gpu'], blender=runs[0]['blender'],
            cold_ms=dict(median=1000 * statistics.median(cold), p95=1000 * q(cold, .95), samples=[1000 * c for c in cold]),
            warm_ms=dict(median=1000 * statistics.median(warm), p95=1000 * q(warm, .95), n=len(warm)),
            warm_stage_median_ms={k: 1000 * statistics.median([r['viewprism_stage_median_s'][k] for r in runs])
                                  for k in runs[0]['viewprism_stage_median_s']},
            encode_write_ms=dict(median=1000 * statistics.median([r['encode_write_s'] for r in runs])),
            files_bytes=runs[0]['files_bytes'],
            render_engines=runs[0].get('render_engines'), cycles_comparison=runs[0].get('cycles_comparison'))
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    print('Results:', out)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
