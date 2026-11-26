# Performance and accuracy measurements

Raw data: [`docs/evidence/2026-11-26/benchmark__summary.json`](evidence/2026-11-26/benchmark__summary.json)
(+ `benchmark__bench.log`). Reproduce with:

```
python tools/benchmark.py --blender <blender.exe> --runs 5
```

## Setup

- Blender 5.3.0 (Steam build 02f0899d78e3), Windows 11 Pro, Intel i7-12700F, 16 GB RAM,
  NVIDIA GeForce RTX 3060 Ti (driver 610.88), **Vulkan** backend (Blender 5.3 default on this machine).
- Each run is a fresh `--factory-startup` GUI process. Run 0 of each scene also renders the comparison
  passes. 5 runs per scene; "cold" = first capture of a process (shader compile, target allocation),
  "warm" = 7 further captures per process (35 samples). Small sample counts: treat p95 as indicative.
- Resolution 1920 × 1080, camera-frame capture (the same camera is used for the render comparison).
- Scenes are generated procedurally (no third-party assets):
  - **simple**: ground plane + 12 cubes (146 triangles, 13 objects)
  - **complex**: ground, 30 smooth UV spheres (96×48), geometry-nodes scatter of 2 500 icospheres on a grid
    (1 103 042 triangles, 2 632 draw items, 2 601 instances, 33 unique meshes)
- Timing is wall-clock in Python (`time.perf_counter`). The GPU part is measured up to the synchronous
  readback (`read_color` waits for the GPU), so draw and readback cannot be separated.

## Results (2026-11-26)

| Scene | Cold capture median / p95 | Warm capture median / p95 | Encode + write 6 files (median) |
|---|---|---|---|
| simple | 92 ms / 107 ms | 53 ms / 93 ms | 182 ms |
| complex | 209 ms / 275 ms | 180 ms / 230 ms | 285 ms |

Warm stage medians:

| Scene | collect (depsgraph + `to_mesh`) | upload (batches) | GPU draw + readback | post (arrays) |
|---|---|---|---|---|
| simple | 0.9 ms | 0.1 ms | 22.0 ms | 27.8 ms |
| complex | 89.4 ms | 6.1 ms | 45.7 ms | 36.8 ms |

Files written per export (defaults + ID + mask): depth PNG8, depth EXR (Z + A, ZIP), normal PNG8,
ID PNG16, mask PNG8, meta JSON. Encoding runs in 4 threads (pure NumPy/zlib).

Back-to-back stability (GUI suite `t_repeat_and_leak`, 640×480, 6 objects): 40 captures with redraws,
median 8–11 ms; private memory flat in steady state (0 growth steps over the last 20 captures on both
backends).

## Comparison with Blender's render passes (method C, comparison only)

Same scene, same camera, 1080p, rendered in the sandbox process with the view-layer Depth + Normal
(+ Object Index for Cycles) passes, written as a multilayer EXR (ZIP, 32-bit). Times include writing the
EXR. Cycles ran on the **CPU** (factory settings: 1 sample, no denoising, 0 bounces, box filter 0.01 px);
GPU Cycles was not configured (that would change preferences).

| Scene | EEVEE (1 spp) render s | Cycles CPU (1 spp) render s |
|---|---|---|
| simple | 0.35, 0.20 | 0.29, 0.29 |
| complex | 0.29, 0.22 | 0.41, 0.40 |

**Interpretation (critical):** per export, ViewPass (capture + files ≈ 0.24 s simple / ≈ 0.47 s complex) is
in the same range as an EEVEE pass render with EXR output on this hardware. ViewPass is not faster than a
pre-configured EEVEE pass render. Its advantage is that it needs no camera, pass, compositor or output
setup and changes nothing in the scene. The methods also differ (EEVEE/Cycles shade the image and write
Combined), so no speed ratio is claimed. A first EEVEE render in a process can take several seconds for
shader compilation (4.0 s observed once); later processes reuse the shader cache.

### Accuracy vs. Cycles (independent renderer, same camera)

Interior = pixels that are foreground in both results, eroded by 2 px (to exclude silhouette pixels where
the single sample may hit different surfaces).

| Metric | simple | complex |
|---|---|---|
| foreground pixels (ours / Cycles) | 1 927 680 / 1 927 680 | 1 927 680 / 1 927 680 |
| mask disagreement (all pixels) | 0.0 | 0.0 |
| depth abs error median / p99 | 3.4e-5 / 1.5e-4 units | 5.7e-6 / 1.5e-4 units |
| depth relative error p99 / max | 4.2e-6 / 0.080 | 4.3e-6 / 0.128 |
| normal angle median / p99 | 0.017° / 0.027° | 0.015° / 0.027° |
| object ID agreement (interior) | 99.9999 % | 99.998 % |

The few large relative errors (max) are at depth discontinuities inside the eroded interior (one pixel
whose sample lands on a different surface). The p99 values confirm that ViewPass depth is the same
**planar** camera-Z as Cycles' Depth pass, and that the camera-frame projection matches Blender's render
framing.

## Not yet measured

- Other GPUs/vendors, Metal, Linux/macOS, Blender 4.5 LTS.
- 4K and 8K exports (resolution limit 33.5 MP; ≈ 36 bytes/pixel of GPU targets).
- Very large scenes (> 10 M triangles); the per-instance Python overhead in `collect` (≈ 30 µs per
  instance) dominates with tens of thousands of instances.
