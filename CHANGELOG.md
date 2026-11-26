# Changelog

## 0.1.0 — unreleased (branch `feature/viewpass`)

Complete rewrite of the former "Depth Renderer" add-on as ViewPass (working name).

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
- Blender Extension manifest and build/validate tooling; test suites (pure, GUI/GPU, package
  lifecycle), benchmark with Cycles/EEVEE comparison, evidence collection.

### Removed
- Legacy `bgl`-based implementation (non-functional) and `memo.txt`.
