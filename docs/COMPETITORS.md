# Competitive landscape and differentiation (checked 2026-11-26)

Method: public web pages, public repositories and official Blender documentation only. Where source
code was read, the technical approach is described in our own words; nothing was copied. "Claims" are
the author's statements, "evidence" is what was verified in source, release metadata or official docs.
Items marked *unverified* could not be opened or were only seen in search snippets. Trademark databases
(USPTO, EUIPO, WIPO, J-PlatPat) were **not** checked.

## Summary table

"Camera?": **No** = works from the current viewport without a camera object; **Temp** = creates one;
**Yes** = needs a scene camera (renders with F12).

| Tool | License | Last update | Camera? | Changes scene/settings? | Passes | Precision | Notes |
|---|---|---|---|---|---|---|---|
| Blender View Layer passes + Compositor ([manual](https://docs.blender.org/manual/en/latest/render/layers/passes.html)) | GPL | 5.3 manual | Yes | Yes (passes, compositor/output, camera) | Depth, Mist, Normal (world space), Object/Material Index (Cycles only), Cryptomatte, AOVs | full float EXR | Reference route; full render each time. Cycles Depth = planar Z since 2.90 (source commit 18cda8be87) |
| Blender Viewport Render | GPL | 5.3 manual | No | uses output settings | Combined only (tricks: normal MatCap, mist) | display-referred | Not metric data |
| [PLAN8VR/Depth_Map](https://github.com/PLAN8VR/Depth_Map) | GPL-2.0 | 2024-03 | Yes | **Clears the compositor tree**, enables Z (not restored) | normalized depth | 16-bit PNG | Uses `scene.node_tree` (removed in 5.0) → likely broken on 5.x (inferred) |
| [Limbicnation/Blender-Depth-Map-Generator](https://github.com/Limbicnation/Blender-Depth-Map-Generator) | Apache-2.0 | 2026-06 | Yes | Enables passes, adds prefixed compositor nodes until reset | depth (Map Range-normalized), masks | EXR | Uses `scene.node_tree` without 5.x fallback (inferred broken on 5.x) |
| [x6ud/controlnet-render-blender-addon](https://github.com/x6ud/controlnet-render-blender-addon) | MIT | 2023-06 | Yes | Passes, compositor nodes, resolution (not restored) | depth, camera-space normal (X flipped), edges | Blender defaults (8-bit inferred) | needs A1111 for generation |
| [Dream Textures](https://github.com/carson-katri/dream-textures) | GPL-3.0 | release 2024-08 | Mixed (projection uses viewport matrices) | by design (AI texturing) | depth (non-linear, normalized), view-space normal, ADE20K colours | in-memory only | **Closest technical precedent**: GPU offscreen geometry draw from viewport matrices; no file export, no integer IDs, multi-GB AI install |
| [FastPBR](https://github.com/ItsCubeTime/FastPBR) | no license file | 2023-04 | No | **Temporarily swaps engine/settings** (manual restore button) | diffuse, albedo/MatID, normal (MatCap), curvature, AO, height (mist) | 8-bit PNG | **Closest conceptual competitor**; Windows only, stale |
| [Blended_Comfy](https://github.com/joris-sta/Blended_Comfy) | MIT | 2026-09 | Yes | temporary camera/res/Z pass/compositor, restored | depth, beauty, normal, UV, outline | normalized 16-bit PNG | ComfyUI localhost bridge |
| Reshoot (Superhive, $39) | GPL-3.0+ (listing) | 2026 | Yes | temporary view layer + compositor (claimed restored) | combined, mist depth, world normal, albedo, Cryptomatte mask | normal 8-bit | listing only |
| PassPilot (Superhive, $9) | not stated | 1.0.29 | Yes | enables passes | all render passes | PNG16/EXR | Windows, 5.2 only (listing) |
| [ComfyUI-BlenderAI-node](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node) | GPL-3.0 | 2025-11 | Yes for depth | temporary passes/compositor | depth, mist, viewport colour | via ComfyUI | |
| [StableGen](https://github.com/sakalond/StableGen), [AI Render](https://github.com/benrugg/AI-Render), BlenderProc | GPL-3.0 / MIT / GPL-3.0 | 2024–2026 | Yes | by design | internal guidance / estimated depth / CV datasets | — | different scope |
| [Quick render](https://github.com/Pullusb/Quick_render) | GPL-3.0 | 2023-10 | Temp (creates a camera) | creates camera | combined only | — | same UX goal, no data passes |
| extensions.blender.org (Industrial AOV Connector, Output Setup Helper, CryptoMatte ID Color, Rendersynth, …) | GPL-3.0+ | 2026 | Yes | compositor/output setup | render passes / datasets | EXR | **no camera-free viewport data-pass exporter found** (searched 2026-11-26) |

Full raw notes with per-tool claims vs. evidence, URLs and check dates:
[`docs/research/competitors_raw_2026-11-26.md`](research/competitors_raw_2026-11-26.md).

## Measured comparison with Blender's own passes (same scene, same camera, 1080p)

From `docs/PERFORMANCE.md` (Blender 5.3.0, RTX 3060 Ti, 5 fresh processes per scene):

| | ViewPass capture (warm median) | ViewPass encode+write (6 files) | EEVEE 1 spp render + multilayer EXR | Cycles CPU 1 spp, 0 bounces + EXR |
|---|---|---|---|---|
| Simple (146 tris) | 51 ms | 147 ms | 0.18–0.29 s | 0.30–0.33 s |
| Complex (1.1 M tris, 2 601 instances) | 180 ms | 287 ms | 0.21–0.33 s | 0.42–0.46 s |

Values vs. Cycles (independent renderer, same camera): depth p99 relative error 4.3e-6, normal median
0.015°, ID agreement 99.998 % (interior pixels), mask identical.

Steps (after installation): ViewPass = 1 click (Export Passes) from any viewport, no setup. Built-in route
the first time ≈ 6–10 actions (camera, align to view, passes, compositor/file output, colour management,
render), then ≈ 3 actions + render per export, and the .blend keeps the changed settings.

## Critical assessment

**Where ViewPass is genuinely better**

1. **No camera and no setup.** Every render-based tool needs a scene camera; Quick render creates one.
2. **Verifiably non-destructive.** The test suites compare scene/datablock/render/compositor/view-layer
   state before and after (`snapshot()`), and settings are not stored in the .blend. Several competitors
   wipe or leave compositor nodes or swap engines.
3. **Data semantics in one click.** Metric planar depth as float EXR (validated against Cycles),
   camera-space normals, plain integer object IDs **with any engine** (built-in Object Index is
   Cycles-only), an exact mask, and a metadata JSON with matrices and the ID map, all from one
   pixel-aligned draw.
4. **Current API**: GPU module only, works on Vulkan and OpenGL in 5.3. Several competitors use APIs
   removed in 5.0.

**Where it is not better (or weaker)**

1. **Speed is not a differentiator.** Capture + writing files (≈0.20 s simple / ≈0.47 s complex at
   1080p) is comparable to an EEVEE 1-spp pass render with EXR output on this machine. Rendering with
   Cycles at production sample counts is much slower, but most users who want guide images can use EEVEE
   or Workbench. The real saving is setup work and scene changes, not milliseconds.
2. **Pixel alignment alone is table stakes**: all passes from one Blender render are aligned too.
3. **Geometry only**: no shader displacement, bump/normal maps, alpha transparency, volumes, hair, point
   clouds or Grease Pencil. ViewPass warns about displacement, transparency and viewport/render
   modifier differences instead of silently differing.
4. **Aliased** (one sample per pixel) — fine for data/IDs and ControlNet, worse than anti-aliased mist
   for compositing.
5. **No animation/sequence export and no ComfyUI/A1111 bridge** yet. Users of AI round-trip tools may
   prefer those.
6. **Normal conventions**: camera space, +X right, +Y up, +Z to the viewer (OpenGL). Flip X/Y options
   exist for the PNG; verifying the exact expectations of each ControlNet normal model is open work.

**Conclusion**: a real but narrow differentiation. The defensible product is "camera-free, untouched
scene, correct raw data (EXR depth/normal/ID/mask + metadata) in one click from the current view,
with any engine". It should not be marketed on speed or on "AI" features. Demand should first be
validated as a free OSS release; sequence export and a local ComfyUI-friendly preset are the obvious next
steps if users ask for them.

## Name check (web search only — not legal clearance)

| Candidate | Finding | Verdict |
|---|---|---|
| ViewPass | No 3D/graphics product found. Generic name: a password-visibility Chrome extension and a Django package on GitHub; "VPass" visitor-management software | usable as working name; a descriptive subtitle helps ("Viewport Pass Exporter") |
| Viewport Pass Exporter | nothing found | descriptive, weakly distinctive |
| PassSnap | nothing in 3D; similar-sounding PassPilot (render-pass add-on) | mild confusion risk |
| SnapPass | Pinterest's password-sharing tool; an iOS AI image editor | avoid |
| PassGrab | GitHub repositories with this name are password stealers | avoid |

Blender Extensions rules forbid "Blender" in the extension name. Final name, trademark search and the
`id` are owner decisions (not taken).
