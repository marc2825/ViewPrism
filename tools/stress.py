# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the resource stress test in a fresh sandboxed Blender and sample GPU memory with nvidia-smi.

    python tools/stress.py --blender <blender.exe> [--gpu-backend vulkan|opengl] [--out DIR]

GPU memory is only available on NVIDIA GPUs with nvidia-smi on PATH; otherwise it is reported as not
measured. Results are written to <out>/stress.json (+ the Blender log).
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sample_gpu(stop, samples):
    exe = shutil.which('nvidia-smi')
    if not exe:
        return
    while not stop.is_set():
        try:
            out = subprocess.run([exe, '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                                 capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
            samples.append(int(out[0]))
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            pass
        time.sleep(0.1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blender', required=True)
    ap.add_argument('--gpu-backend')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--instances', type=int, default=40000)
    a = ap.parse_args()
    out = (a.out or Path(tempfile.mkdtemp(prefix='viewprism-stress-'))).resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = out / 'stress.json'
    cmd = [a.blender, '--factory-startup', '--disable-autoexec']
    if a.gpu_backend:
        cmd += ['--gpu-backend', a.gpu_backend]
    cmd += ['--python-exit-code', '1', '--python', str(HERE / 'stress_inner.py'), '--',
            '--repo', str(HERE.parent), '--result', str(result), '--instances', str(a.instances)]
    samples, stop = [], threading.Event()
    base = []
    sample_gpu_once = threading.Thread(target=sample_gpu, args=(stop, base))
    sample_gpu_once.start()
    time.sleep(1.0)
    stop.set()
    sample_gpu_once.join()
    stop = threading.Event()
    sampler = threading.Thread(target=sample_gpu, args=(stop, samples))
    sampler.start()
    with (out / 'stress.log').open('w', encoding='utf-8') as fh:
        code = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=1800).returncode
    stop.set()
    sampler.join()
    data = json.loads(result.read_text(encoding='utf-8')) if result.exists() else dict(status='fail')
    if samples and base:
        data['gpu_memory_mb'] = dict(baseline=min(base), peak=max(samples), peak_over_baseline=max(samples) - min(base),
                                     source='nvidia-smi (whole GPU, includes other processes)')
    else:
        data['gpu_memory_mb'] = 'not measured (nvidia-smi not available)'
    result.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(json.dumps(data, indent=2))
    print('Results:', out)
    return 0 if (code == 0 and data.get('status') == 'pass') else 1


if __name__ == '__main__':
    sys.exit(main())
