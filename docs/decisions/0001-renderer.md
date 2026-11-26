# ADR 0001 — Capture renderer: one custom GPU geometry pass (method A)

- Status: accepted (2026-11-26)
- Verified on: Blender 5.3.0, Windows 11, NVIDIA RTX 3060 Ti (driver 610.88), Vulkan and OpenGL 4.6 backends;
  Blender 4.5.17 LTS and 5.3.0 on Linux with Mesa llvmpipe OpenGL (CI)
- Not verified: Blender 5.0–5.2, Blender 4.5 on Windows/macOS, Metal, AMD/Intel GPUs

## Context

ViewPrism must export Depth / Normal / Object ID / Mask from the 3D viewport the user is working in,
without a camera, without touching scene, render or compositor settings, with all passes
geometrically consistent, using only Blender's current `gpu` module (no `bgl`, no raw OpenGL,
no private API). The legacy Depth Renderer code (removed in this branch, still in history) was not
salvageable:

| Legacy problem (verified by reading `utils.py` / `operators.py` at e86658a) | Effect |
|---|---|
| `bgl` used but never imported; `bgl` itself removed in Blender 5.0 | `NameError` at runtime, silently caught → always "rendering failed" |
| Fixed-function GL (`glBegin`, matrix stacks) | Not available in core profiles / Vulkan / Metal |
| `GL_TRIANGLES` fed with polygon loops | n-gons and quads drawn as garbage triangles |
| `perspective_matrix` (already view·projection) multiplied with `view_matrix` again | wrong projection |
| Raw non-linear depth buffer read, no normalisation, no background handling | not a usable depth |
| Image datablock created and pixels set in a Python loop | modifies the .blend, very slow |
| Original object `to_mesh()` | modifiers/instances ignored |

## Options evaluated (Phase 0 PoC, scripts in the session scratchpad; results below)

| | A. Custom GPU geometry pass | B. `draw_view3d` + depth readback | C. Render passes (EEVEE/Cycles) |
|---|---|---|---|
| Camera needed | no | no | **yes** |
| Scene/settings changes | none | none | view-layer passes, compositor or output format, camera |
| Passes | depth, normal, id, mask from one draw | colour from `GPUOffScreen`; depth only via the region's framebuffer in a draw callback (`read_depth`), not from `GPUOffScreen` | all |
| Depth semantics | exact planar −Z written per fragment | non-linear, 24/32-bit, includes overlays/X-ray state | planar Z (Cycles since 2.90) |
| Resolution | any (up to GPU limits) | viewport region only | any |
| Speed (1080p) | 50–180 ms capture | n/a | 0.2–0.4 s (1 spp) |
| Verdict | **chosen** | rejected: no IDs/normals, viewport-dependent depth, region-sized | comparison/validation only |

PoC measurements (Blender 5.3.0, RTX 3060 Ti):

1. **MRT works on both backends**: two `RGBA32F` colour targets + `DEPTH_COMPONENT32F` bound with
   `GPUFrameBuffer(depth_slot=…, color_slots=(…, …))`, shader from `GPUShaderCreateInfo` with two
   `fragment_out` slots. Readback via `read_color(..., slot, 'FLOAT')` is bottom-left origin on Vulkan
   and OpenGL alike (flip to top-left on the CPU).
2. **Portability trap found**: a `UINT` push constant set with `uniform_int` stays **0 on OpenGL**
   (works on Vulkan). Unused uniforms are optimised away on OpenGL (setting them raises). ⇒ no integer
   uniforms; the object id travels as a float in a `vec4`, exact up to 2²⁴.
3. **Push constants > 128 bytes** worked on NVIDIA Vulkan (140 B tested) but the layout was reduced to
   exactly 128 B to stay within the guaranteed minimum on other drivers: `vec4 MVRow0..2` (affine
   model-view rows), `mat4 ProjectionMatrix`, `vec4 Params(depth_near, depth_scale, depth_mode, id)`.
4. **Depth-buffer precision**: with the viewport's default clip range (0.01–1000), two surfaces 5 mm apart
   at 100 m are resolved in the *wrong* order with the standard hyperbolic depth (`DEPTH_COMPONENT32F`),
   on both backends. Writing `gl_FragDepth = log(d/near)/log(far/near)` (perspective) or linear
   (orthographic) with `depth_write('ANY')` orders them correctly. Kept as a regression test
   (`t_precision`).
5. Conversions: `np.frombuffer(gpu.types.Buffer)` is zero-copy (15 µs at 1080p); a 1 M-vertex batch is
   built from NumPy in ~15 ms.

## Decision

**Method A**: one draw of all visible evaluated geometry into an MRT framebuffer.

- Target 0 = (n.x, n.y, n.z, −z_view), target 1 = (id, coverage, 0, 0). Every pass comes from the same
  fragment, so depth, normal, id and mask are pixel-aligned by construction, with one coverage test
  (`mask == isfinite(depth) == (id > 0)`).
- Output depth is the interpolated view-space −Z (planar, scene units, float32), independent of the
  remapped value used only for visibility.
- Normals: per-corner normals of the evaluated mesh (`Mesh.corner_normals`: smooth/flat/auto-smooth/custom
  normals as displayed), or polygon normals (`FLAT`), transformed by the inverse-transpose of the
  model-view linear part. It is computed in the shader as the cofactor matrix times sign(det), so
  mirrored objects keep outward normals. Orientation follows the geometry (back faces are not flipped).
- No MSAA, no filtering: one sample per pixel centre (`(col + 0.5, row + 0.5)`), as Cycles' data passes.
- Matrices come in through the public contract as explicit row-major OpenGL-style matrices; the UI
  derives them from the operating region (`RegionView3D.view_matrix` and `window_matrix` — never
  `perspective_matrix` times view again).

### Scene collection (read-only)

`depsgraph.object_instances` with:

- `show_self`
- `Object.visible_get(view_layer, viewport)` on the object in the view layer (the instancer for
  instances). PoC showed that objects in an eye-hidden collection **are** present in the depsgraph, so
  this check is required. It also covers local view and per-viewport local collections.
- the viewport's object-type filters; objects displayed as Wire/Bounds are skipped (with a warning)
- `to_mesh()` / `to_mesh_clear()` on evaluated objects (modifiers, geometry nodes, edit-mode edits)
- meshes cached per capture by (evaluated object pointer, data pointer): object instances share
  pointers, while geometry-nodes geometry instances get distinct temporary pointers (PoC)

### UI-specific policies

- **Camera view** (`view_perspective == 'CAMERA'`, option on by default): the camera frame is exported
  with `Object.calc_matrix_camera(depsgraph, x, y, pixel aspect)`, i.e. the framing of a render at that
  size (lens shift and sensor fit included). Verified against `world_to_camera_view` and against a ray
  through each pixel centre built from `Camera.view_frame`.
- **Orthographic viewport**: Blender uses near = −clip_end/2, so depths in front of the eye would be
  negative. The view origin is moved back onto the near plane (pixels and visibility are unchanged, so
  all depths are positive) and the shift is recorded in the metadata.
- **Custom aspect**: a centred crop of the view (scale of NDC x or y); never shows outside the viewport.
- **Settings** live on the WindowManager (PoC: WM properties are not written into the .blend; Scene
  properties are). Persistent defaults are stored in the add-on preferences.

### Resource management

- Shader compiled once per session; freed on unregister.
- Render-target **textures** are reused for same-size captures up to ~2 MP. They are released after
  30 s idle, on size change, after any failure, when windows are opened/closed, and on unregister.
  Back-to-back captures without a redraw grew ~10 MB each because GPU backends free resources at frame
  boundaries; reuse removed that growth (measured flat). The **framebuffer is created and freed per
  capture**, because OpenGL framebuffers belong to one window's context. Caching it crashed Blender 4.5
  after the window that created it was closed (found by CI).
- When windows were opened/closed since the last capture, ViewPrism asks Blender to redraw once before
  any GPU work, so that a GPU context is current (4.5 has no Python-side check; 5.x raised an error).
- Readback goes into flat 1-D `gpu.types.Buffer`s: Blender 4.5 exports the default (h, w, 4) buffer
  through a non-contiguous buffer protocol that NumPy cannot view.
- GPU state (depth test/mask, blend, viewport, framebuffer) is restored on success and on failure
  (fault-injection test).

## Consequences

- Geometry only: shader displacement, bump/normal maps, alpha transparency, volumes, hair/curves, point
  clouds and Grease Pencil are not represented. The capture warns for render-vs-viewport modifier
  differences, shader displacement and transparency, and lists unsupported visible types.
- Aliased edges (one sample per pixel).
- Object id ≤ 2²⁴−1 per capture (error above); the 16-bit PNG encoding is limited to 65 535 (that file
  fails, EXR still works).
- Viewport clipping regions (Alt+B) are not applied (documented limitation).
- Values validated against Cycles from the same camera (1080p): depth p99 relative error 4.3e-6, normals
  median 0.015°, object ids 99.998 % equal on interior pixels, masks identical (see `docs/PERFORMANCE.md`).
