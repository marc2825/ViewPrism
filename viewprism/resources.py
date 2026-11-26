# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Memory estimates and guards (pure: no bpy).

The per-pixel constants were measured with tools/stress.py (process peak over baseline while capturing
and exporting all passes, docs/PERFORMANCE.md) and rounded up.

Policy:
* **refuse** when the estimate exceeds HARD_FRACTION of the memory that can still be committed
  (physical + pagefile/swap): allocations would fail or Blender could be killed;
* **warn** when it exceeds SOFT_FRACTION of the free physical memory: it will work but may page and be
  slow.
GPU memory cannot be queried portably from Blender; GPU allocation failures are reported as errors.
"""
import ctypes
import os
import sys

GPU_BYTES_PER_PIXEL = 36          # 2 x RGBA32F colour targets + DEPTH_COMPONENT32F
CAPTURE_BYTES_PER_PIXEL = 120     # readback buffers, NumPy outputs, Blender's staging copies
EXPORT_BYTES_PER_PIXEL = 100      # additional peak while encoding/writing all files (chunked encoders)
HARD_FRACTION = 0.9
SOFT_FRACTION = 0.8


class ResourceError(ValueError):
    pass


def estimate(width, height, export=True):
    px = int(width) * int(height)
    cpu = px * (CAPTURE_BYTES_PER_PIXEL + (EXPORT_BYTES_PER_PIXEL if export else 0))
    return dict(pixels=px, gpu_bytes=px * GPU_BYTES_PER_PIXEL, cpu_bytes=cpu)


def available_memory():
    """dict(physical=free physical bytes or None, commit=free committable bytes incl. swap or None)."""
    try:
        if os.name == 'nt':
            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                            ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                            ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                            ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            stat = MemoryStatusEx()
            stat.dwLength = ctypes.sizeof(MemoryStatusEx)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return dict(physical=int(stat.ullAvailPhys), commit=int(stat.ullAvailPageFile))
            return dict(physical=None, commit=None)
        if sys.platform.startswith('linux'):
            info = {}
            with open('/proc/meminfo', encoding='ascii') as fh:
                for line in fh:
                    key, _, rest = line.partition(':')
                    info[key] = int(rest.split()[0]) * 1024
            avail = info.get('MemAvailable')
            return dict(physical=avail, commit=None if avail is None else avail + info.get('SwapFree', 0))
        if sys.platform == 'darwin':
            # No stdlib "available" figure on macOS: half of the physical memory as a soft estimate.
            return dict(physical=int(os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') * 0.5), commit=None)
    except (OSError, ValueError, AttributeError, IndexError):
        pass
    return dict(physical=None, commit=None)


def check(width, height, *, export=True, memory=None):
    """Raise ResourceError if the estimate cannot fit into committable memory; otherwise return the
    estimate with 'warning' set when it exceeds the comfortable share of free physical memory."""
    est = estimate(width, height, export)
    memory = available_memory() if memory is None else memory
    est.update(memory=memory, warning=None)
    need = est['cpu_bytes']
    what = 'capture and export' if export else 'capture'
    commit, physical = memory.get('commit'), memory.get('physical')
    if commit is not None and need > commit * HARD_FRACTION:
        raise ResourceError(f'a {width}x{height} {what} needs about {need / 1e9:.1f} GB of memory but only '
                            f'{commit / 1e9:.1f} GB can still be allocated; lower the resolution or close '
                            'other programs')
    if physical is not None and need > physical * SOFT_FRACTION:
        est['warning'] = (f'a {width}x{height} {what} needs about {need / 1e9:.1f} GB of memory but only '
                          f'{physical / 1e9:.1f} GB is free; it may be slow while the system pages')
    return est
