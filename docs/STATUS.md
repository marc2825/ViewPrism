# Project status — 2026-11-26

Product name: **ViewPrism — Viewport Pass Exporter** (decided 2026-11-26; developed as "ViewPass").
Merged into `main` on 2026-11-26 (PR #1, merge commit, full history kept) in the private repository
`ViewPrism` (renamed from `Depth_Renderer`). Nothing published; the repository stays private. Planned
features: `ROADMAP.md`.

## Implemented

| Area | State |
|---|---|
| Capture core (`viewprism/capture.py`, `gpu_draw.py`, `scene_geometry.py`) | single MRT GPU pass; depth / normal / ID / mask; perspective, orthographic and generic matrices; log/linear visibility depth; evaluated depsgraph with instances and viewport visibility; deterministic IDs (3 modes); texture reuse; per-capture framebuffer; GPU state restore; redraw before capturing after window changes; explicit errors |
| View → request (`viewport.py`) | operating region; camera frame in camera view; custom size with aspect lock or centred crop; positive ortho depth; quad view uses the main region; re-find view after the file browser |
| Encoding / files (`encode.py`, `png.py`, `exr.py`, `export.py`, `writer.py`) | PNG 8/16, EXR float32/uint32 (ZIP/NONE), metadata JSON, collision pre-check, numbering, atomic writes, per-file errors, parallel encoding, no colour management |
| UI (`ui.py`, `operators.py`, `props.py`, `preview.py`) | N-panel, Export / Export As, preview overlay (manual + auto refresh), formats & advanced sub-panels, status box, View menu entry, defaults in preferences |
| Warnings | viewport/render modifier differences, shader displacement, transparency, unsupported types, Wire/Bounds, Alt+B clipping, empty capture |
| Packaging | extension manifest (min Blender 4.5.0), validate/build/audit tool, install lifecycle test |
| CI/CD (GitHub Actions) | lint; pure tests (Windows/Linux × Python 3.11/3.13); real Blender 4.5 LTS and 5.3 on Linux (Xvfb + Mesa llvmpipe OpenGL) running the independent harness, GUI/GPU suite, build and package lifecycle; tag → validated ZIP in a draft release |
| Tooling | test runners, benchmark + Cycles/EEVEE comparison, README image generator, evidence collector |
| Docs | README (en/ja), ADR 0001, COMPETITORS (+ raw research), PERFORMANCE, TEST_MATRIX, MANUAL_QA_RESULTS, SECURITY_AND_RIGHTS, RELEASE_CHECKLIST, NAMING, CHANGELOG, CONTRIBUTING |

## Not implemented (by decision or not yet)

- Animation / frame-range export; Line Art, AO, RGB, world-space normals, pose passes (spec "extensions").
- Clipboard image copy. The spec allows it only if real Windows clipboard copies can be verified, and
  that verification would overwrite the user's clipboard during automated tests, so it was deferred.
- ControlNet/ComfyUI presets. Normal PNG Flip X/Y exists, but the exact convention of each model is
  not verified.
- Supersampling / anti-aliased display passes; viewport clipping region (Alt+B) support.
- Cross-capture mesh cache (would speed up auto preview in very large scenes).

## Verified environments

| Blender | OS | GPU / backend | Where | Result |
|---|---|---|---|---|
| 5.3.0 (02f0899d78e3) | Windows 11 Pro 26200 | RTX 3060 Ti, driver 610.88, **Vulkan** (default) | local | all gates PASS |
| 5.3.0 | Windows 11 Pro 26200 | RTX 3060 Ti, **OpenGL 4.6** | local | harness + GUI suite PASS |
| 5.3.0 | Ubuntu (GitHub runner) | Mesa llvmpipe, OpenGL 4.5 core (software) | CI | all gates PASS |
| **4.5.17 LTS** | Ubuntu (GitHub runner) | Mesa llvmpipe, OpenGL 4.5 core (software) | CI | all gates PASS |
| 4.5 LTS on Windows/macOS; 5.0–5.2 | — | — | — | **NOT TESTED** |
| any | macOS | Metal | — | **NOT TESTED** |
| any | any | AMD / Intel GPUs, Linux hardware drivers | — | **NOT TESTED** |

`blender_version_min` is 4.5.0, based on the 4.5.17 CI verification. Blender 4.5 needed two fixes,
both found by CI: a flat readback buffer (4.5 exports a non-contiguous buffer protocol), and never
reusing an OpenGL framebuffer across window contexts. The second one was a real ViewPrism bug that
crashed 4.5 after a capture from a second, later closed window.

## Test results

- Local (Windows): [`docs/evidence/2026-11-26/SUMMARY.md`](evidence/2026-11-26/SUMMARY.md)
- CI (Linux): [`docs/evidence/ci-2026-11-26-linux-blender-4.5.17/`](evidence/ci-2026-11-26-linux-blender-4.5.17/SUMMARY.md),
  [`docs/evidence/ci-2026-11-26-linux-blender-5.3.0/`](evidence/ci-2026-11-26-linux-blender-5.3.0/SUMMARY.md);
  every CI run also uploads its evidence as an artifact.

| Suite | Count | Result |
|---|---|---|
| Pure unit tests | 48 | PASS (local + CI on Windows/Linux, Python 3.11/3.13) |
| Independent harness self-test | 2 | PASS |
| Independent harness (background registration + GPU analytic cases) | per environment above | PASS |
| GUI/GPU suite | 20 cases per environment | PASS |
| Extension validate + build + ZIP audit | 1 | PASS |
| Package lifecycle (isolated user dir) | 1 per Blender version | PASS |
| Benchmark / Cycles comparison | 2 scenes × 5 processes (local) | done (see PERFORMANCE) |

Reproduce locally with `python tools/run_all_checks.py --blender "<path>/blender.exe" --bench`.

## Repository settings applied (visibility unchanged: private)

- Description, topics; wiki/projects off; delete branch on merge; "update branch" button; squash
  commits use the PR title/body.
- `main` protection: all CI jobs required (strict); no force pushes, no deletion; conversations must be
  resolved; no required review (single maintainer); admins can bypass in an emergency.
- Actions: only GitHub-owned actions allowed; default token read-only; workflows request write only
  where needed (draft release).
- Dependabot alerts + automated security fixes on; Dependabot version updates for Actions (weekly).
- Secret scanning: **not available** for this private repository on the current plan (HTTP 422).
- Issue templates (bug/feature, environment fields) and a PR checklist.

## Open issues / risks

1. **Differentiation is narrow** (see COMPETITORS): the value is "camera-free, untouched scene, raw
   aligned data in one click", not speed. An EEVEE pass render with an existing setup is about as fast.
2. Metal, AMD/Intel and Windows 4.5 are untested. Push constants are kept at 128 B and integer
   uniforms are avoided for portability, but this is unverified on those platforms.
3. No human hands-on QA yet (file browser save/cancel, visual preview check, external apps).
4. `collect` costs ~30 µs per instance in Python; scenes with 100k+ instances will take seconds.
5. Repeated large (> 2 MP) captures in one script without redraws are untested. Their textures are not
   reused, so GPU memory is freed only at frame boundaries.
6. `memo.txt` with a local WSL path remains in old commits; rewriting history is the owner's decision.
7. Blender prints "push constants … 144 bytes" warnings from its own built-in drawing (seen on 4.5 and
   5.3, also without ViewPrism shaders). The ViewPrism capture shader uses exactly 128 bytes.

## Decisions needed from the owner

- License (candidate GPL-3.0-or-later) and adding a `LICENSE` file.
- Trademark search for "ViewPrism" (web search only so far: `docs/NAMING.md`); logo license.
- Publication on extensions.blender.org (and making the repository public) later.
- Optional: history cleanup for `memo.txt`.

## Next steps (proposed order)

1. Hands-on QA (`docs/MANUAL_QA_RESULTS.md`, ~15 min).
2. Collect feedback from 3–5 target users (illustration/compositing/AI-guide users) before adding
   features.
3. If requested by users: frame-range export, ControlNet presets (verified conventions), mesh cache for
   auto preview.
4. Owner decisions above, then extension listing text/thumbnails (CC0) and submission.
