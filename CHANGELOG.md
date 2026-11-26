# Changelog

## Unreleased

### Export safety and metadata privacy (#4)
- No-clobber publication: without overwrite, files are published through a hard link (Windows: a
  rename that never replaces). A file created by another writer in the meantime is never replaced.
  File systems without hard links (outside Windows) fail safely with an explanation.
- Automatic numbering reserves its number with an exclusive lock file (safe across processes).
- Dangling symlinks count as existing files; symlinks pointing outside the folder are refused.
- Failed files are recorded in metadata as stable error codes with fixed messages (no paths). Free
  text in metadata is path-redacted. Detailed errors stay in the local report.
- New *Metadata Names: Anonymized* option (neutral labels instead of object/camera names).

### Resource limits and responsiveness (#5)
- Memory guard: a capture or export that cannot fit into the memory that can still be allocated is
  refused with a clear message (lower the resolution or close other programs); one that would make the
  system page shows a warning. GPU allocation failures are reported as a GPU error and the next capture
  works again.
- Lower peak memory while exporting (chunked encoders, streamed PNG compression): an 8K export of all
  passes now needs no memory beyond the capture itself (+3.7 GB instead of +5.3 GB in the stress scene).
  Output files are bit-identical.
- Auto preview refreshes only once the view and the scene have been still, so orbiting or dragging in
  heavy scenes no longer stutters.

### QA and CI (#5)
- Stress test tool (`tools/stress.py`) and `docs/QA_REPORT.md` with every verified and untested
  configuration.
- CI: Blender 4.5, 5.0, 5.1, 5.2 and 5.3 on Linux; 4.5 and 5.3 on Windows (background); manual macOS
  probe. Actions pinned to commit SHAs, hashed Python requirements, no persisted checkout credentials,
  Blender archives re-verified every run, release publishing isolated from the build job.
- Secret scanning in CI: gitleaks over the whole history with a canary that must be detected, and the
  repository privacy scan (e-mails, user paths, credential formats, PNG metadata) over tree and history.
- Fixed: dangling-symlink collisions on Windows were reported as "outside the folder" (still refused).

## 0.1.0 — 2026-11-26 (pre-release)

Complete rewrite of the former "Depth Renderer" add-on as **ViewPrism — Viewport Pass Exporter**
(developed under the working name "ViewPass"; renamed on 2026-11-26).

### Added
- One-pass GPU capture (GPU module only) of depth, camera-space normal, object ID and mask from the
  current 3D viewport, pixel-aligned by construction.
- Camera-frame export in camera view; centred crop for custom aspect ratios; positive depths in free
  orthographic views (origin on the near plane, recorded in metadata).
- Logarithmic/linear remapped visibility depth: no z-fighting between surfaces millimetres apart at the
  default clip range.
- Evaluated geometry: modifiers, geometry nodes, collection and geometry-node instances, edit-mode edits;
  viewport visibility rules (hide, collection exclude/hide, local view, local collections, type filters).
- ID modes: per source object, per instancer, per instance.
- Export: PNG 8/16-bit and OpenEXR (float32/uint32, ZIP) written directly (no colour management, no
  image datablocks); metadata JSON; collision pre-check, auto numbering, atomic writes, per-file error
  reports; parallel encoding.
- Display-only preview overlay with manual or debounced auto refresh.
- Warnings for viewport/render modifier differences, shader displacement, transparency, unsupported
  object types, Wire/Bounds display, viewport clipping region.
- Settings kept out of .blend files; persistent defaults in preferences.
- Blender Extension manifest (Blender 4.5+) and build/validate tooling; test suites (pure, GUI/GPU, package
  lifecycle), benchmark with Cycles/EEVEE comparison, evidence collection.

### Fixed during verification
- Blender 4.5: GPU readback into flat buffers (4.5's default Buffer is not NumPy-viewable).
- OpenGL framebuffers are no longer cached across captures (they belong to one window's context;
  reusing one after its window closed crashed Blender 4.5).
- Redraw before capturing after windows were opened/closed (no current GPU context otherwise).
- `GPUTexture.filter_mode` is 5.x only (feature-guarded); `PATH_SUPPORTS_BLEND_RELATIVE` feature-probed.

### CI/CD
- GitHub Actions: lint, pure tests (Windows/Linux), Blender 4.5 LTS + 5.3 full checks on Linux,
  tag-triggered draft release with the validated ZIP; Dependabot for Actions.

### Name, logo and roadmap
- Renamed to ViewPrism: package `viewprism`, extension id `viewprism`, operators `viewprism.*`, sidebar
  tab "ViewPrism", default folder `//viewprism/`, metadata format `viewprism-meta`. A small `viewpass`
  alias remains at the repository root only for the unchanged independent harness (not packaged).
- Logo set in `branding/` (SVG source + rendered PNGs, `tools/make_logo.py`).
- `ROADMAP.md` for planned features (clipboard, ControlNet presets, Line Art/AO, sequences, ...).

### License
- GPL-3.0-or-later: `LICENSE`, SPDX headers, manifest copyright; the extension ZIP includes `LICENSE`.

### Removed
- Legacy `bgl`-based implementation (non-functional) and `memo.txt`.
