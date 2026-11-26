# Release readiness checklist (Blender Extensions)

Legend: ✅ done and verified · ⏳ open, can be done without the owner · 🔒 needs the owner's decision/approval

## Product gates

| Item | State |
|---|---|
| Capture core passes the independent harness (background + GPU) | ✅ Blender 5.3.0 Windows (Vulkan + OpenGL); 4.5.17 + 5.3.0 Linux (CI) |
| GUI/GPU suite (20 cases) | ✅ Vulkan + OpenGL |
| Pure tests (48) | ✅ |
| Non-destructiveness (scene, datablocks, render/compositor/view-layer settings, selection, frame, mode) | ✅ automated `snapshot()` comparisons |
| File re-read verification (own decoders + Blender loader) | ✅ |
| Values cross-checked against Cycles (same camera) | ✅ `docs/PERFORMANCE.md` |
| Blender 4.5 LTS | ✅ 4.5.17 on Linux/Mesa in CI (all gates); Windows 4.5 not tested |
| Blender 5.0–5.2 | ⏳ same procedure |
| macOS (Metal), AMD/Intel GPUs, Linux hardware drivers | ⏳ needs those machines; until then: "verified on Windows/NVIDIA and Linux (Mesa software OpenGL) only" |
| Hands-on manual QA by a person (`docs/MANUAL_QA_RESULTS.md`) | ⏳ |

## Package

| Item | State |
|---|---|
| `blender_manifest.toml` validates (source and built ZIP) | ✅ `blender --command extension validate` |
| ZIP contains only add-on files (no tests, harness, caches, private paths) | ✅ audited by `tools/build_extension.py` |
| Install / enable / export / disable / re-enable / uninstall in a clean user dir | ✅ `tests/blender/package_suite.py` |
| `permissions`: `files` only, with reason | ✅ |
| No network, no wheels, no bundled binaries | ✅ |
| Relative imports, `__package__` for preferences, no `sys.path` changes, nothing written to the add-on dir | ✅ |
| `blender_version_min` = only verified versions (4.5.0) | ✅ |
| CI on every PR (lint, pure tests, Blender 4.5 + 5.3 full checks) and protected `main` | ✅ |
| Tag → validated ZIP + SHA-256 in a GitHub (pre-)release | ✅ v0.1.0 published as pre-release |
| `website` field | ✅ https://github.com/marc2825/ViewPrism |
| `maintainer` field (currently the GitHub handle) | 🔒 confirm how the owner wants to be credited |

## Rights and naming

| Item | State |
|---|---|
| License (candidate GPL-3.0-or-later; add `LICENSE` file) | 🔒 |
| Product name "ViewPrism — Viewport Pass Exporter", extension `id` `viewprism` | ✅ decided by the owner |
| Trademark search for "ViewPrism" (J-PlatPat / USPTO / EUIPO) | 🔒 |
| Logo (`branding/`) license; CC0 if bundled in the extension | 🔒 |
| Repository rename (Depth_Renderer → ViewPrism) | ✅ (GitHub redirects the old URL) |
| History cleanup of `memo.txt` (would need a force push) | 🔒 optional |
| Code origin / no copied code / no third-party assets | ✅ `docs/SECURITY_AND_RIGHTS.md` |

## Documentation

| Item | State |
|---|---|
| README (en/ja) with real output images, limitations | ✅ |
| CHANGELOG, CONTRIBUTING | ✅ |
| Extension listing text and thumbnails (CC0, no Blender logo) | ⏳ draft after the name is decided |

## Publication

| Item | State |
|---|---|
| Push branch / open PR / merge | ✅ PR #1 merged into `main` (merge commit) |
| Repository public | ✅ (owner, 2026-11-26) |
| Upload to extensions.blender.org, announcements, pricing | 🔒 not done |
