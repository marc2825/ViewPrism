# Project status — 2026-11-26

Product name: **ViewPrism — Viewport Pass Exporter** (decided 2026-11-26; developed as "ViewPass").
Merged into `main` on 2026-11-26 (PR #1, merge commit, full history kept). The repository
`ViewPrism` (renamed from `Depth_Renderer`) is **public** since 2026-11-26. GitHub **pre-releases**:
v0.1.0 and v0.2.0. License: **GPL-3.0-or-later** (#6). extensions.blender.org: listing and submission
kit ready (`docs/EXTENSION_LISTING.md`, `docs/EXTENSION_SUBMISSION.ja.md`); the owner submits after a
hands-on check. Planned features: `ROADMAP.md` (feature work paused until publication).

Review issues of 2026-11-26: #6 licensing and rights (closed by PR #7), #4 export safety and metadata
privacy (PR #8), #5 QA, resource limits and CI security (PR #10). CI dependencies per Python version and
pinned Blender builds: PR #12 (supersedes Dependabot #11). Open follow-up: #9 (human hands-on QA,
untested hardware).

## Implemented

| Area | State |
|---|---|
| Capture core (`viewprism/capture.py`, `gpu_draw.py`, `scene_geometry.py`) | single MRT GPU pass; depth / normal / ID / mask; perspective, orthographic and generic matrices; log/linear visibility depth; evaluated depsgraph with instances and viewport visibility; deterministic IDs (3 modes); texture reuse; per-capture framebuffer; GPU state restore; redraw before capturing after window changes; explicit errors (GPU errors suggest a lower resolution) |
| Resources (`resources.py`) | memory estimate per pixel; refuse above 90 % of committable memory, warn above 80 % of free RAM; chunked/streamed encoders (8K export adds no memory beyond the capture) |
| View → request (`viewport.py`) | operating region; camera frame in camera view; custom size with aspect lock or centred crop; positive ortho depth; quad view uses the main region; re-find view after the file browser |
| Encoding / files (`encode.py`, `png.py`, `exr.py`, `export.py`, `writer.py`) | PNG 8/16, EXR float32/uint32 (ZIP/NONE), metadata JSON (full or anonymized names, path-free error codes), collision pre-check, numbering with exclusive reservation, no-clobber atomic publication, symlink handling, per-file errors, parallel encoding, no colour management |
| UI (`ui.py`, `operators.py`, `props.py`, `preview.py`) | N-panel, Export / Export As, preview overlay (manual + auto refresh after stillness), formats & advanced sub-panels, status box, View menu entry, defaults in preferences |
| Warnings | viewport/render modifier differences, shader displacement, transparency, unsupported types, Wire/Bounds, Alt+B clipping, empty capture, low memory |
| Packaging | extension manifest (min Blender 4.5.0, GPL-3.0-or-later), validate/build/audit tool (ZIP privacy scan, LICENSE included), install lifecycle test |
| CI/CD (GitHub Actions) | lint; pure tests (Windows/Linux × Python 3.11/3.13); Blender 4.5 LTS, 5.0, 5.1, 5.2, 5.3 on Linux (Xvfb + Mesa llvmpipe OpenGL) with harness, GUI/GPU suite, build and package lifecycle; Blender 4.5 LTS and 5.3 on Windows (background); secrets job (gitleaks + canary, privacy scan of tree and history); manual macOS probe; tag → validated ZIP + SHA-256 as a GitHub (pre-)release from an isolated publish job |
| Tooling | test runners, benchmark + Cycles/EEVEE comparison, stress test, README image generator, evidence collector with sanitising and privacy scan, privacy scanner |
| Docs | README (en/ja), ADR 0001, COMPETITORS (+ raw research), PERFORMANCE, QA_REPORT, TEST_MATRIX, MANUAL_QA_RESULTS, SECURITY_AND_RIGHTS, RELEASE_CHECKLIST, NAMING, EXTENSION_LISTING, CHANGELOG, CONTRIBUTING |

## Not implemented (by decision or not yet)

- Animation / frame-range export; Line Art, AO, RGB, world-space normals, pose passes (spec "extensions").
- Clipboard image copy. The spec allows it only if real Windows clipboard copies can be verified, and
  that verification would overwrite the user's clipboard during automated tests, so it was deferred.
- ControlNet/ComfyUI presets. Normal PNG Flip X/Y exists, but the exact convention of each model is
  not verified.
- Supersampling / anti-aliased display passes; viewport clipping region (Alt+B) support.
- Cross-capture mesh cache (would speed up auto preview in very large scenes).

## Verified environments

Full list with untested configurations: [`QA_REPORT.md`](QA_REPORT.md).

| Blender | OS | GPU / backend | Where | Result |
|---|---|---|---|---|
| 5.3.0 (02f0899d78e3) | Windows 11 Pro 26200 | RTX 3060 Ti, driver 610.88, **Vulkan** (default) | local | all gates + stress PASS |
| 5.3.0 | Windows 11 Pro 26200 | RTX 3060 Ti, **OpenGL 4.6** | local | harness + GUI suite + stress PASS |
| **4.5.17 LTS**, 5.0.1, 5.1.2, 5.2.5, 5.3.0 | Ubuntu (GitHub runner) | Mesa llvmpipe, OpenGL 4.5 core (software) | CI | all gates PASS |
| **4.5.17 LTS**, 5.3.0 | Windows Server (GitHub runner) | none (background mode) | CI | pure, harness (background), build PASS |
| 4.5 LTS on Windows **with a GPU** | — | — | — | **NOT TESTED** (#9) |
| any | macOS | Metal | — | **NOT TESTED** (#9) |
| any | any | AMD / Intel GPUs, Linux hardware drivers | — | **NOT TESTED** (#9) |

`blender_version_min` stays 4.5.0 (reassessed in QA_REPORT). Blender 4.5 needed two fixes, both found
by CI: a flat readback buffer (4.5 exports a non-contiguous buffer protocol), and never reusing an
OpenGL framebuffer across window contexts. The second one was a real ViewPrism bug that crashed 4.5
after a capture from a second, later closed window.

## Test results

- Local (Windows): [`docs/evidence/2026-11-26/SUMMARY.md`](evidence/2026-11-26/SUMMARY.md), stress:
  [`docs/evidence/2026-11-26-stress/`](evidence/2026-11-26-stress/)
- CI: [`docs/evidence/ci-2026-11-26/`](evidence/ci-2026-11-26/) (PR #10); every CI run also uploads its
  evidence as an artifact.

| Suite | Count | Result |
|---|---|---|
| Pure unit tests | 82 | PASS (local + CI on Windows/Linux, Python 3.11/3.13; symlink cases run in CI) |
| Independent harness self-test | 2 | PASS |
| Independent harness (background registration + GPU analytic cases) | per environment above | PASS |
| GUI/GPU suite | 22 cases per environment | PASS |
| Extension validate + build + ZIP audit | 1 | PASS |
| Package lifecycle (isolated user dir) | 1 per Blender version | PASS |
| Secrets (gitleaks all refs + canary) and privacy scan (tree + history) | CI | PASS |
| Stress (1080p/4K/8K, repeated 4K, 40 000 instances, GPU failure) | 2 backends (local) | PASS (see PERFORMANCE) |
| Benchmark / Cycles comparison | 2 scenes × 5 processes (local) | done (see PERFORMANCE) |

Reproduce locally with `python tools/run_all_checks.py --blender "<path>/blender.exe" --bench`.

## Repository settings applied (public repository)

- Description, topics; wiki/projects off; delete branch on merge; "update branch" button; squash
  commits use the PR title/body (merges use merge commits to keep history).
- `main` protection: changes only through pull requests (0 approvals, single maintainer); all CI jobs
  required (strict), including the secrets job and every Blender job; no force pushes or deletion;
  conversations must be resolved; admins can bypass in an emergency.
- Actions: only GitHub-owned actions allowed, pinned to commit SHAs; default token read-only;
  checkouts without persisted credentials; only the release publish job requests `contents: write`.
  Fork PRs from first-time contributors need approval before CI runs.
- Security: secret scanning + push protection, private vulnerability reporting (`SECURITY.md`),
  CodeQL code scanning (default setup), Dependabot alerts + security fixes, weekly Actions and pip
  updates. Non-provider secret patterns and validity checks are not available for this repository
  through the API.
- Releases: tag `vX.Y.Z` → validated ZIP + SHA-256 published by `.github/workflows/release.yml`;
  versions < 1.0.0 or with a suffix are marked pre-release. README badges: CI, release, Blender versions,
  license, tested platforms.
- Issue templates (bug/feature, environment fields) and a PR checklist.
- Not possible through the API: the social preview image (upload `branding/viewprism-wordmark-dark.png`
  under Settings → General if wanted).

## Open issues / risks

1. **Differentiation is narrow** (see COMPETITORS): the value is "camera-free, untouched scene, raw
   aligned data in one click", not speed. An EEVEE pass render with an existing setup is about as fast.
2. Metal, AMD/Intel and Windows 4.5 with a GPU are untested (#9). Push constants are kept at 128 B and
   integer uniforms are avoided for portability, but this is unverified on those platforms.
3. No human hands-on QA yet (#9: file browser save/cancel, visual preview check, external apps).
4. `collect` costs ≈ 6 µs per instance in Python; 100 000+ instances take about a second per capture.
5. GPU memory cannot be queried from Python; GPU exhaustion is reported as an error, not prevented.
6. Blender prints "push constants … 144 bytes" warnings from its own built-in drawing (seen on 4.5 and
   5.3, also without ViewPrism shaders). The ViewPrism capture shader uses exactly 128 bytes.

## Owner decisions (2026-11-26)

- Name: **ViewPrism is kept** after the follow-up review of similar names (`docs/NAMING.md`). No formal
  trademark clearance was done.
- Git history: the published author e-mail and the old local path are **accepted**; no rewrite.
  Credential and third-party-data scanning stays mandatory in CI.
- GitHub pre-release v0.2.0: **approved**.
- extensions.blender.org: free distribution; the owner submits after a hands-on check. Untested OS/GPU
  combinations are stated, not a blocker.

## Next steps (proposed order)

1. Owner: hands-on check and submission (`docs/EXTENSION_SUBMISSION.ja.md`, issue #9).
2. Answer the moderators' review comments; fix-ups as 0.2.x.
3. Collect feedback from target users (illustration/compositing/AI-guide users) before adding features.
4. If requested by users: frame-range export, ControlNet presets (verified conventions), mesh cache for
   auto preview.
