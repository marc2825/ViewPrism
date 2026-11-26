# Release readiness checklist (Blender Extensions)

Legend: ✅ done and verified · ⏳ open, can be done without the owner · 🔒 needs the owner's decision/approval

## Product gates

| Item | State |
|---|---|
| Capture core passes the independent harness (background + GPU) | ✅ Blender 5.3.0, Vulkan + OpenGL |
| GUI/GPU suite (20 cases) | ✅ Vulkan + OpenGL |
| Pure tests (48) | ✅ |
| Non-destructiveness (scene, datablocks, render/compositor/view-layer settings, selection, frame, mode) | ✅ automated `snapshot()` comparisons |
| File re-read verification (own decoders + Blender loader) | ✅ |
| Values cross-checked against Cycles (same camera) | ✅ `docs/PERFORMANCE.md` |
| Blender 4.5 LTS | ⏳ not installed here. Run `python tools/run_all_checks.py --blender "<4.5>/blender.exe"`; if it passes, lower `blender_version_min` |
| Blender 5.0–5.2 | ⏳ same procedure |
| macOS (Metal), Linux, AMD/Intel GPUs | ⏳ needs those machines; until then: "verified on Windows/NVIDIA only" |
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
| `blender_version_min` = only verified versions (currently 5.3.0) | ✅ (lower after 4.5 verification) |
| `website` field | 🔒 depends on the final repository name |
| `maintainer` field (currently the GitHub handle) | 🔒 confirm how the owner wants to be credited |

## Rights and naming

| Item | State |
|---|---|
| License (candidate GPL-3.0-or-later; add `LICENSE` file) | 🔒 |
| Final product name, extension `id`, trademark search (J-PlatPat / USPTO / EUIPO) | 🔒 |
| Repository rename (Depth_Renderer → ?) | 🔒 |
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
| Push branch / open PR | 🔒 not done (no push without approval) |
| Upload to extensions.blender.org, announcements, pricing | 🔒 not done |
