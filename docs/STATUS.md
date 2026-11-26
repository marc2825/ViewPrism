# Project status — 2026-11-26

Branch `feature/viewpass` (local only; nothing pushed). Working name **ViewPass**; nothing published.

## Implemented

| Area | State |
|---|---|
| Capture core (`viewpass/capture.py`, `gpu_draw.py`, `scene_geometry.py`) | single MRT GPU pass; depth / normal / ID / mask; perspective, orthographic, generic matrices; log/linear visibility depth; evaluated depsgraph with instances and viewport visibility; deterministic IDs (3 modes); render-target reuse; GPU state restore; explicit errors |
| View → request (`viewport.py`) | operating region; camera frame in camera view; custom size with aspect lock or centred crop; positive ortho depth; quad view uses the main region; re-find view after the file browser |
| Encoding / files (`encode.py`, `png.py`, `exr.py`, `export.py`, `writer.py`) | PNG 8/16, EXR float32/uint32 (ZIP/NONE), metadata JSON, collision pre-check, numbering, atomic writes, per-file errors, parallel encoding, no colour management |
| UI (`ui.py`, `operators.py`, `props.py`, `preview.py`) | N-panel, Export / Export As, preview overlay (manual + auto refresh), formats & advanced sub-panels, status box, View menu entry, defaults in preferences |
| Warnings | viewport/render modifier differences, shader displacement, transparency, unsupported types, Wire/Bounds, Alt+B clipping, empty capture |
| Packaging | extension manifest, validate/build/audit tool, install lifecycle test |
| Tooling | test runners, benchmark + Cycles/EEVEE comparison, README image generator, evidence collector |
| Docs | README (en/ja), ADR 0001, COMPETITORS (+ raw research), PERFORMANCE, TEST_MATRIX, MANUAL_QA_RESULTS, SECURITY_AND_RIGHTS, RELEASE_CHECKLIST, CHANGELOG, CONTRIBUTING |

## Not implemented (by decision or not yet)

- Animation / frame-range export; Line Art, AO, RGB, world-space normals, pose passes (spec "extensions").
- Clipboard image copy (spec allows it only if real Windows clipboard copies can be verified; the
  verification would overwrite the user's clipboard during automated tests, so it was deferred).
- ControlNet/ComfyUI presets (normal PNG Flip X/Y exists; the exact conventions per model are not verified).
- Supersampling / anti-aliased display passes; viewport clipping region (Alt+B) support.
- Cross-capture mesh cache (would speed up auto preview in very large scenes).

## Verified environments

| Blender | OS | GPU / backend | Result |
|---|---|---|---|
| 5.3.0 (02f0899d78e3) | Windows 11 Pro 26200 | RTX 3060 Ti, driver 610.88, **Vulkan** (default) | all gates PASS |
| 5.3.0 | Windows 11 Pro 26200 | RTX 3060 Ti, **OpenGL 4.6** | harness + GUI suite PASS |
| 4.5 LTS, 5.0–5.2 | — | — | **NOT TESTED** (not installed; downloading Blender was not permitted in this session) |
| any | macOS / Linux | Metal / AMD / Intel | **NOT TESTED** |

`blender_version_min` is therefore 5.3.0. The code avoids 5.x-only APIs where known (the
`PATH_SUPPORTS_BLEND_RELATIVE` option and the multilayer EXR media type are feature-probed), but that is
not a claim of compatibility.

## Test results

Latest full run: [`docs/evidence/2026-11-26/SUMMARY.md`](evidence/2026-11-26/SUMMARY.md) (raw JSON/logs
next to it, local paths replaced by `<HOME>`/`<USER>`).

| Suite | Count | Result |
|---|---|---|
| Pure unit tests | 48 | PASS |
| Independent harness self-test | 2 | PASS |
| Independent harness (background registration + GPU analytic cases) | 2 modes × 2 backends | PASS |
| GUI/GPU suite | 20 cases × 2 backends | PASS |
| Extension validate + build + ZIP audit | 1 | PASS |
| Package lifecycle (isolated user dir) | 1 | PASS |
| Benchmark / Cycles comparison | 2 scenes × 5 processes | done (see PERFORMANCE) |

Reproduce: `python tools/run_all_checks.py --blender "<path>/blender.exe" --bench`.

## Open issues / risks

1. **Differentiation is narrow** (see COMPETITORS): the value is "camera-free, untouched scene, raw
   aligned data in one click", not speed. An EEVEE pass render with an existing setup is about as fast.
2. 4.5 LTS compatibility unknown; Metal and non-NVIDIA drivers unknown (push constants are kept at 128 B
   and integer uniforms are avoided for portability, but this is untested).
3. No human hands-on QA yet (file browser save/cancel, visual preview check, external apps).
4. `collect` costs ~30 µs per instance in Python; scenes with 100k+ instances will take seconds.
5. Back-to-back captures without a redraw rely on render-target reuse (≤ ~2 MP) to avoid growth from
   deferred GPU deletion; repeated large (> 2 MP) captures in one script without redraws are untested.
6. `memo.txt` with a local WSL path remains in old commits (owner decision whether to rewrite history).

## Decisions needed from the owner

- License (candidate GPL-3.0-or-later) and adding a `LICENSE` file.
- Final name / extension id / repository rename; trademark search.
- Whether to push the branch / open a PR; whether to publish on extensions.blender.org.
- Optional: history cleanup for `memo.txt`.
- Permission to download Blender 4.5 LTS (or run the check script on a machine that has it).

## Next steps (proposed order)

1. Run `tools/run_all_checks.py` with Blender 4.5 LTS; fix what breaks; lower `blender_version_min`.
2. Hands-on QA (`docs/MANUAL_QA_RESULTS.md`, ~15 min) and collect feedback from 3–5 target users
   (illustration/compositing/AI-guide users) before adding features.
3. If requested by users: frame-range export, ControlNet presets (verified conventions), mesh cache for
   auto preview.
4. Owner decisions above, then extension listing text/thumbnails (CC0) and submission.
