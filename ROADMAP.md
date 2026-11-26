# ViewPrism roadmap

Status as of 2026-11-26. Nothing here is implemented yet unless marked otherwise. Priorities follow the
project rules: **correct output > non-destructive > UI > extra features**. Every item ships with tests
whose expected values do not come from ViewPrism itself. Approximations are labelled as such in the
UI, the metadata and the docs.

Legend: ⬜ not started · 🟨 in progress · ✅ done

## 0.1 — current (unreleased)

✅ Depth / Normal / Object ID / Mask from the current viewport in one GPU pass · ✅ PNG 8/16 + EXR +
metadata · ✅ display-only preview (manual/auto) · ✅ camera-frame export · ✅ Blender 4.5 LTS + 5.3 ·
✅ CI (lint, pure tests, Blender 4.5/5.3 on Linux) · ✅ extension packaging

## 0.2 — Faster round trips

| | Feature | Scope and approach | Acceptance criteria |
|---|---|---|---|
| ⬜ | **Clipboard image output** | "Copy" button for the previewed pass. Display encoding only (8-bit PNG/DIB); raw data stays in files. Windows first (`CF_DIB` + registered `PNG` format through ctypes), macOS/Linux later or not at all (no stdlib API). Needs the manifest `clipboard` permission. | Real round trip verified on Windows: write, read back through the Win32 API **and** an independent reader, then compare pixels. The test saves and restores the user's clipboard, or runs only when explicitly enabled. No silent fallback on unsupported OSes; the button is hidden there. |
| ⬜ | **Animation / frame-range export** | Frame range from the scene or custom; numbered files `<name>_<frame>_<pass>.<ext>`. Depth display range fixed for the whole sequence (fixed range, or a first pass that measures the global min/max) to avoid flicker. Modal operator with progress and cancel. Frame changes are restored on success, cancel and error. GPU targets are reused across frames. | Analytic animated scene: per-frame depth/ID at known pixels. `frame_current` and scene state unchanged afterwards (`snapshot()`). Cancel leaves a reported, consistent file set. Memory flat over 200 frames. |
| ⬜ | **ControlNet / ComfyUI presets** | One-click presets (e.g. "ControlNet depth", "ControlNet normal", "Segmentation") that set display encodings only: depth polarity and range, normal axis convention (Flip X/Y), background, size rounded to a multiple of 8/64, file naming. Raw EXR and metadata unchanged. | Each convention documented with a primary source (model card or preprocessor code), with link and date. Golden tests on analytic scenes check every preset's output. No preset is shipped whose convention could not be verified. |

## 0.3 — More passes

| | Feature | Scope and approach | Acceptance criteria |
|---|---|---|---|
| ⬜ | **Line Art (edge approximation)** | Edges from the captured, pixel-aligned passes: depth discontinuities (relative threshold), normal creases (angle threshold), object-ID boundaries. Line width and thresholds are adjustable. NumPy or GPU. Labelled "edge approximation from depth/normal/ID — not Freestyle or Grease Pencil Line Art". | Analytic scenes: expected silhouette/crease pixels within ±1 px, no edges inside flat faces. Behaviour at resolution changes documented. |
| ⬜ | **AO (screen-space approximation)** | Screen-space ambient occlusion from depth + normal (hemisphere/horizon sampling on the GPU), with radius and sample count. Labelled "SSAO approximation". | Deterministic output (fixed sample pattern). Accuracy reported, not claimed, against Cycles' AO pass on the benchmark scenes (mean/percentile difference in `docs/PERFORMANCE.md`). |
| ⬜ | World-space normals, position pass | Same draw, extra outputs; metadata records the space. | Analytic checks like the camera-space normal tests. |
| ⬜ | Selection-only mask, per-material ID | Mask/ID restricted to selected objects; material index as ID. | Visibility/selection matrix tests; ID map completeness. |
| ⬜ | Combined multi-layer EXR | All raw passes in one EXR (named layers). | Round trip with our decoder and Blender's loader. |
| ⬜ | Supersampled display passes | Optional anti-aliased depth/normal/mask PNGs (raw data and IDs stay single-sample). | Documented difference; IDs never blended. |
| ⬜ | Viewport clipping region (Alt+B) | Apply the region's clip planes (currently only warned). | Analytic clipped scene. |
| ⬜ | RGB / combined image | Viewport colour via `draw_view3d`, clearly separate from the data passes. | Size/framing identical to the data passes. |

## 0.4 — Scale and platforms

| | Item | Notes |
|---|---|---|
| ⬜ | Mesh cache across captures | Faster auto preview in large scenes (invalidate on depsgraph updates). |
| ⬜ | Fewer Python calls per instance | Batch matrices or GPU instancing for 10k+ instances (`collect` is ~30 µs per instance today). |
| ⬜ | Tiled capture above 33.5 MP | Sub-frustum tiles, exact seams. |
| ⬜ | Verification on more platforms | macOS/Metal, AMD/Intel GPUs, Blender 4.5 on Windows, 5.0–5.2. Extend the CI matrix where runners allow; otherwise record manual runs of `tools/run_all_checks.py`. |
| ⬜ | Hands-on QA by people | `docs/MANUAL_QA_RESULTS.md` checklist; feedback from 3–5 target users before adding features. |

## Release tasks (owner decisions)

| | Task |
|---|---|
| ⬜ | License (candidate GPL-3.0-or-later) and `LICENSE` file |
| ⬜ | Trademark search for "ViewPrism" (J-PlatPat / USPTO / EUIPO, classes 9 and 42) |
| ⬜ | Logo license: CC0 is required if the logo is ever bundled inside the extension (see `branding/README.md`) |
| ⬜ | Extension listing text and thumbnails, then submission to extensions.blender.org; making the repository public |
