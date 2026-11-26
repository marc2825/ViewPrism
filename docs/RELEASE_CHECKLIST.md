# Release readiness checklist (v0.3.0, Blender Extensions)

Legend: ✅ done and verified · ⏳ open, can be done without the owner · 🔒 needs the owner

## Product gates

| Item | State |
|---|---|
| Independent harness (background + GPU) | ✅ Windows 11 + NVIDIA (Vulkan, OpenGL); Linux CI Blender 4.5.17, 5.0.1, 5.1.2, 5.2.5, 5.3.0 (Mesa); Windows CI 4.5.17 + 5.3.0 (background) |
| GUI/GPU suite (26 cases, incl. every panel state in English and Japanese) | ✅ local Vulkan + OpenGL; Linux CI on all five versions |
| Pure tests (100, incl. translation completeness and decoder limits) | ✅ local + CI (Windows/Linux, Python 3.11/3.13) |
| Resource stress (1080p/4K/8K, repeated 4K, 40 000 instances, GPU failure, preview with/without thumbnails) | ✅ `docs/PERFORMANCE.md` |
| Independent code review of the changes since the previous release | ✅ v0.2.0 (`docs/QA_REPORT.md`); v0.3.0 UI redesign (see the release PR) |
| Non-destructiveness, file re-read, Cycles cross-check | ✅ |
| macOS (Metal), AMD/Intel GPUs, Linux hardware drivers, Windows 4.5 with a GPU | ⏳ not tested; stated in README and listing (issue #9). Not a publication requirement (owner, 2026-11-26) |
| Hands-on QA by a person | 🔒 owner, before submitting (`docs/EXTENSION_SUBMISSION.ja.md` §2, issue #9) |

## Package

| Item | State |
|---|---|
| Manifest validates (source and built ZIP), version 0.3.0 = `operators.VERSION` = tag | ✅ checked by `tools/build_extension.py` and the release workflow |
| ZIP contains only add-on files + `LICENSE`; privacy scan of the ZIP | ✅ |
| Install / enable / export / disable / re-enable / uninstall in a clean user dir | ✅ `tests/blender/package_suite.py` (CI, all versions) |
| `permissions`: `files` only, with reason; no network, wheels or binaries | ✅ |
| Tag → validated ZIP + SHA-256 as GitHub pre-release | ✅ v0.1.0, v0.2.0 (released ZIP re-downloaded: SHA-256, contents, privacy and install/export/uninstall checked); v0.3.0: same checks after publishing |

## Rights and naming

| Item | State |
|---|---|
| License GPL-3.0-or-later (`LICENSE`, SPDX headers, manifest, inside the ZIP) | ✅ |
| Name "ViewPrism" | ✅ kept by the owner after the follow-up review (`docs/NAMING.md`); no formal trademark clearance |
| Logo and listing media: original, no Blender logo, metadata stripped | ✅ |
| Git history (author e-mail, old local path) | ✅ accepted by the owner; no rewrite. Secret scanning of all history stays in CI |

## Publication

| Item | State |
|---|---|
| GitHub pre-releases | ✅ v0.2.0 (2026-11-27); v0.3.0 with the redesigned UI (2026-11-27, owner: release the newest version and submit that one) |
| Listing text, media, review answers | ✅ `docs/EXTENSION_LISTING.md` (0.3.0 panel, `docs/images/`) |
| Submission procedure and owner checks | ✅ `docs/EXTENSION_SUBMISSION.ja.md` |
| Upload to extensions.blender.org | 🔒 owner, after the hands-on check |
