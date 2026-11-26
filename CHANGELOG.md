# Changelog

## 0.1.0 — unreleased (branch `feature/viewprism`)

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

### Removed
- Legacy `bgl`-based implementation (non-functional) and `memo.txt`.
