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
| simple | 58 ms / 86 ms | 45 ms / 58 ms | 138 ms |
| complex | 204 ms / 338 ms | 182 ms / 321 ms | 257 ms |

Warm stage medians:

| Scene | collect (depsgraph + `to_mesh`) | upload (batches) | GPU draw + readback | post (arrays) |
|---|---|---|---|---|
| simple | 0.9 ms | 0.1 ms | 14.5 ms | 26.8 ms |
| complex | 81.2 ms | 5.1 ms | 65.4 ms | 30.6 ms |

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
| simple | 0.28, 0.19 | 0.30, 0.27 |
| complex | 0.35, 0.30 | 0.41, 0.41 |

**Interpretation (critical):** per export, ViewPrism (capture + files ≈ 0.18 s simple / ≈ 0.44 s complex) is
in the same range as an EEVEE pass render with EXR output on this hardware. ViewPrism is not faster than a
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
whose sample lands on a different surface). The p99 values confirm that ViewPrism depth is the same
**planar** camera-Z as Cycles' Depth pass, and that the camera-frame projection matches Blender's render
framing.

## Resource stress (issue #5)

Raw data: [`docs/evidence/2026-11-26-stress/`](evidence/2026-11-26-stress/) (`stress-vulkan.json`,
`stress-opengl.json`). Reproduce with:

```
python tools/stress.py --blender <blender.exe> --gpu-backend vulkan|opengl --out <dir>
```

Same machine as above (16 GB RAM, RTX 3060 Ti 8 GB), Blender 5.3.0, fresh `--factory-startup` GUI
process, nothing else running. Scene: ground plane, 20 UV spheres (96×48) and a geometry-nodes scatter of
**40 000** icosphere instances → **3 412 562 triangles**. All passes are captured; the export writes
depth PNG16 + EXR, normal PNG8, ID PNG16, mask PNG8 and metadata.
"Process memory" is Windows *private bytes* of the Blender process over its value before the step;
"GPU memory" is `nvidia-smi` for the whole GPU (includes the desktop and Blender's own viewport), so it
is an upper bound for ViewPrism.

| Size | Backend | Capture | Export (6 files) | Process peak, capture | Process peak, capture + export | Failed files |
|---|---|---|---|---|---|---|
| 1920 × 1080 (2.1 MP) | Vulkan | 0.57 s | 0.23 s | +457 MB | +539 MB | 0 |
| 3840 × 2160 (8.3 MP) | Vulkan | 0.83 s | 0.83 s | +1 229 MB | +1 311 MB | 0 |
| 7680 × 4320 (33.2 MP) | Vulkan | 2.03 s | 3.18 s | +3 706 MB | +3 706 MB | 0 |
| 1920 × 1080 | OpenGL | 0.46 s | 0.23 s | +389 MB | +463 MB | 0 |
| 3840 × 2160 | OpenGL | 0.64 s | 0.81 s | +907 MB | +971 MB | 0 |
| 7680 × 4320 | OpenGL | 1.50 s | 2.92 s | +2 968 MB | +2 968 MB | 0 |

- **GPU memory**, whole run (8K included): peak +1.85 GB (Vulkan) / +1.43 GB (OpenGL) over the idle
  desktop. ViewPrism's own targets are 36 bytes/pixel (1.2 GB at 8K).
- **Repeated 4K captures** (8 in a row, without and with redraws in between): no growth. Private
  bytes relative to before the series never exceed +0.19 GB on either backend and do not trend upwards
  (negative values: memory of the preceding 8K step being released); median capture 0.64–0.74 s.
- **Failure recovery**: an injected GPU allocation failure at 4K is reported as
  `GPU error (…); try a lower resolution`; the next capture succeeds (0.68 s, foreground present).
- **Auto preview**: one preview capture at the default 50 % scale (787 × 444) of this scene takes
  0.41 s (Vulkan) / 0.37 s (OpenGL), dominated by `collect` (≈ 0.25 s for 40 000 instances in Python).
  Before issue #5 the auto refresh fired 0.2 s after the *first* change, so orbiting a heavy scene
  triggered a blocking capture every few tenths of a second (8 captures during 2.5 s of simulated
  navigation). It now waits until the view and the scene have been **still** for
  max(0.2 s, last capture time), capped at 1 s, and never captures while you navigate or drag
  (`t_preview_debounce`).
- The chunked encoders (1 MiPx depth/normal chunks, streamed zlib for PNG, per-block EXR interleave)
  cut the 8K export peak from +5.3 GB to +3.7 GB in this scene: the export no longer adds memory on
  top of the capture.

### Memory guard

`viewprism/resources.py` estimates **220 bytes/pixel** of process memory for capture + export
(120 capture + 100 export, rounded up from the 112 B/px capture peak measured above) and 36 B/px on the
GPU. Policy (tests: `tests/pure/test_resources.py`, GUI `t_resource_guard`):

- **refuse** with a clear message ("… lower the resolution or close other programs") when the estimate
  exceeds 90 % of the memory that can still be committed (free RAM + page file/swap);
- **warn** (export still runs) when it exceeds 80 % of the *free physical* memory, because the system
  may page;
- GPU memory cannot be queried portably from Blender's Python API; GPU allocation errors are reported as
  errors and the capture can be retried.

The 33.5 MP resolution limit is a hard sanity limit, not a memory guarantee: at 33.2 MP the export
needs ≈ 7.3 GB by the estimate (3.7 GB measured), which a machine with 8 GB RAM and a busy desktop may
not have. The guard decides that from the actual free memory.

## Not yet measured

- Other GPUs/vendors (AMD, Intel), Metal; Linux/macOS hardware drivers (CI uses Mesa llvmpipe, which
  measures correctness, not speed).
- Scenes beyond ~3.5 M triangles / 40 000 instances; `collect` costs ≈ 6 µs per instance here, so
  100 000+ instances will take about a second per capture.
