# ViewPass — competitive landscape (raw research notes)

- Date checked: **2026-11-26** (all entries unless noted).
- Method: public web pages only (WebSearch, page fetches, `curl` of public pages, GitHub public API via `gh` for repo metadata and reading public source). No code or assets were copied. Where I read source code, the approach is described in my own words only.
- Convention: "README/listing claims" = what the author says. "Evidence" = what I verified in source code, release metadata or the official docs. "unknown" = not stated and not verified. "unverified (could not access)" = page blocked, JS-only, or not opened.
- Current Blender manual at the time of checking is the **Blender 5.3** manual (`docs.blender.org/manual/en/latest/` resolves to 5.3).

---

## 1. Comparison table

Legend for "Camera needed?": **No** = works from the current viewport view without a camera object. **Temp** = creates or uses a camera behind the scenes. **Yes** = needs a scene camera (usually because it calls the normal F12 render).

| Tool | URL | Checked | Version/updated | License | Blender versions | Price | Camera needed? | Changes scene/settings? | Preview | Passes | Precision/format | Steps per export | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Blender built-in: View Layer passes + Compositor** | https://docs.blender.org/manual/en/latest/render/layers/passes.html | 2026-11-26 | Manual 5.3 | GPL (Blender) | all | Free | **Yes** (F12 render) | **Yes** (enables passes, builds compositor tree, output format) | Compositor Viewer/backdrop; viewport compositor | Depth, Mist, Normal (world space), Position, Vector, UV, Object/Material Index (Cycles only), Cryptomatte (Cycles/EEVEE), AOVs | Full-float EXR possible; PNG 8/16-bit after normalizing | First time ~6–10 actions; repeat ~3 (align camera to view, F12, save) + full render time | Cycles Depth is planar camera Z for persp/ortho since 2.90 (radial for panoramic). Data passes are not anti-aliased |
| **Blender built-in: Viewport Render** (View > Render Viewport Preview) | https://docs.blender.org/manual/en/latest/editors/3dview/viewport_render.html | 2026-11-26 | Manual 5.3 | GPL | all (Workbench/EEVEE only, not Cycles) | Free | **No** ("virtual camera" matches current view) | Uses render output settings (resolution, aspect, path, format); nothing else needed | Image editor | Only what the viewport shows (Combined). Depth/normal only via tricks (normal MatCap, viewport "Render Pass" display) | Display-referred color; bit depth from output format | 1–2 | Tricks are quantized and color-managed, not metric data |
| **PLAN8VR/Depth_Map** ("True Depthmap Export") | https://github.com/PLAN8VR/Depth_Map | 2026-11-26 | bl_info 0.0.2. Last commit 2024-03-06. No releases | GPL-2.0 (GitHub-detected LICENSE) | bl_info targets 4.0.2. Uses `scene.node_tree` (removed in 5.0), so likely broken on 5.x (inferred, not tested) | Free | **Yes** (README: camera required, ortho 1:1 recommended) | **Yes**: forces 1024×1024, EEVEE, Raw view transform, film transparent (these are restored). **Clears and replaces the compositor tree** and enables the Z pass (not restored) | Viewer node | Depth (inverted + normalized), plus Combined | 16-bit RGBA PNG, per-image normalized | 1 click + save dialog | Destroys an existing compositor setup |
| **Limbicnation/Blender-Depth-Map-Generator** | https://github.com/Limbicnation/Blender-Depth-Map-Generator | 2026-11-26 | Manifest 2.0.0. Last commit 2026-06-18. No GitHub releases | Apache-2.0 | Manifest min 4.2.0. README says tested on 4.5 LTS. Uses `scene.node_tree` without a 5.x fallback, so likely broken on 5.0+ (inferred) | Free | **Yes** (calls the regular render operator) | **Yes**: enables Z, IndexOB or Cryptomatte passes. Adds `DM_`-prefixed compositor nodes and keeps user nodes. Changes persist until "Reset Compositing" | Color-ramped preview via Viewer / Image Editor | Depth; alpha mask (Cryptomatte, or Object Index in Cycles) | Depth: EXR 32-bit float, but it is the Map Range output (normalized to user near/far). Mask: EXR 16-bit half | Depth: Setup, adjust, Render (≥2 clicks). Mask: 3+ | Supports animation sequences. Not found on extensions.blender.org |
| **x6ud/controlnet-render-blender-addon** | https://github.com/x6ud/controlnet-render-blender-addon | 2026-11-26 | v1.0.0, released 2023-06-19 (all 5 commits that day) | MIT | 3.5 (bl_info). Uses `scene.node_tree`, so likely broken on 5.x (inferred) | Free | **Yes** (regular render; camera rotation used to convert normals) | **Yes**: enables Z and Normal passes, adds compositor nodes and node groups (fake users), sets resolution. Not restored | Viewer nodes + Image Editor | Depth (normalized, inverted, color ramp), Normal (converted to camera space, X flipped), Edge (Laplace on depth+normal), Combined | File Output format not set, so Blender defaults apply (typically 8-bit PNG; inferred) | 1 click after setup (README: save the .blend first) | Generation half needs A1111 SD WebUI `--api` |
| **carson-katri/dream-textures** | https://github.com/carson-katri/dream-textures | 2026-11-26 | Last release v0.4.1, 2024-08-26. Last commit 2026-09-17 | GPL-3.0 | Release builds for "Blender 3.6 → 4.0" and "Blender 4.1+". 4.2+/5.x untested by me | Free on GitHub (a Blender Market badge was removed 2026-09; price there unverified) | **Mixed**: "Project Dream Texture" uses the **current viewport matrices (no camera)**. Render-engine annotation nodes use the scene camera | Project modifies selected objects' materials/UVs by design (details not verified). Engine requires the Dream Textures render engine | In node tree / Image Editor | Depth (from GPU depth buffer), Normal (view space), ADE20K segmentation colors, OpenPose, viewport color | In-memory float arrays. Depth is non-linear and min/max normalized. No dedicated file export | N/A (AI generation tool, not an exporter) | Closest **technical** precedent (GPU offscreen geometry draw). Heavy AI dependencies |
| **SDWebUITools** (Superhive) | https://superhivemarket.com/products/sdwebuitools | 2026-11-26 | Version not stated. "Published over 2 years ago" | MIT | 4.1 | $1 | Likely **Yes** (uses a compositing render; listing doesn't say explicitly) | Uses the Compositing workspace. Details unknown | unknown | Depth + canny for ControlNet | unknown | unknown | Windows only (not Chinese-locale OS). Needs A1111 WebUI + ControlNet |
| **ItsCubeTime/FastPBR** ("Fast PBR Viewport Render") | https://github.com/ItsCubeTime/FastPBR | 2026-11-26 | Release 1.8.0, 2023-04-11. Last push 2023-04-24 | No license file in repo (GitHub: none). Release zip license unverified | bl_info says 3.0 (README says the git source is outdated) | Free | **No** (viewport, or the camera you're looking through) | **Yes, temporarily**: switches renderer (Workbench/EEVEE) and render settings, then restores. Has a manual "restore settings" button for crashes | unknown | Diffuse, Albedo/MatID, Normal (normal-MatCap trick), Curvature, AO, Height (EEVEE mist), Transparency | PNG only. README: height "limited to 256 possible values" (8-bit) | 1 click after configuring | **Closest conceptual competitor** (camera-free multi-map from viewport). Windows only, PIL dependency, stale since 2023 |
| **joris-sta/Blended_Comfy** | https://github.com/joris-sta/Blended_Comfy | 2026-11-26 | v1.0.0, 2026-09-05 | MIT | 5.0 (bl_info) | Free | **Yes** (named scene camera) | Temporarily: sets camera and resolution, Z pass, temporary compositor. All restored | Live preview inside ComfyUI | Depth, Beauty, Normal, UV, Outline | Reads float via Viewer node, but depth is sent as normalized 16-bit gray PNG | Triggered from ComfyUI per request | localhost HTTP bridge (port 8199) |
| **Reshoot** (Superhive) | https://superhivemarket.com/products/reshoot | 2026-11-26 | Version not stated. "Published 4 months ago" | GPL-3.0-or-later (listing) | 4.5–5.2 | $39 | **Yes** (active camera) | Temporary view layer + compositor nodes. Listing claims everything is restored | Result in Image Editor; gallery | Combined, Depth (mist-based, white = near), Normal (world space), Albedo, Cryptomatte selection mask | Normal 8-bit RGB. Others not stated | 1 click (+ local ComfyUI + SDXL) | Commercial "one-click AI shot"; .json sidecar per image |
| **AIGODLIKE/ComfyUI-BlenderAI-node** | https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node | 2026-11-26 | v2.0.0, 2025-07-25. Last push 2025-11-28 | GPL-3.0 | README recommends 3.5, 3.6.x, 4.0 | Free | Depth/mist: **Yes** (checks for a scene camera, regular render). Viewport color: viewport render | Temporarily enables Z/mist passes + compositor. Restores the pass flags | ComfyUI node UI | Viewport color, render, depth, mist, projected masks | Via ComfyUI images | Node-graph workflow | ComfyUI front-end inside Blender |
| **sakalond/StableGen** | https://github.com/sakalond/StableGen | 2026-11-26 | v0.5.0, 2026-11-04 | GPL-3.0 | 4.2–4.5 and 5.1+ (README: 5.0 not supported) | Free | **Yes** (adds cameras around the mesh) | Yes, by design (cameras, materials, projections) | Rendered viewport | Depth/Canny/Normal guidance (internal) | Internal | Multi-step | Texturing tool, not an exporter. Needs a ComfyUI server |
| **benrugg/AI-Render** | https://github.com/benrugg/AI-Render | 2026-11-26 | v1.1.1, 2025-12-28 | MIT | 3.0+ | Free on GitHub. Also on Blender Market/Gumroad (price unverified) | **Yes** (F12 render) | Hooks the render | n/a | ControlNet via A1111 preprocessors on the rendered image (estimated depth, not geometric) | n/a | n/a | Not a pass exporter |
| **toyxyz "Character bones that look like Openpose"** (Gumroad) | https://toyxyz.gumroad.com/l/ciojz | 2026-11-26 | "Ver_101" in title. Date not shown | not stated | "3.5 or higher" | Listed at $0 (`price_cents: 0`; pay-what-you-want display ambiguous) | Render-based rig/template (camera). Details unverified | unknown | unknown | OpenPose, Depth, Canny, Landmark, MediaPipe face, finger, camera pose; body mesh for Depth/Normal/Seg/Lineart | unknown | unknown | 830 ratings, very popular for ControlNet pose work |
| **Pullusb/Quick_render** | https://github.com/Pullusb/Quick_render · https://pullusb.gumroad.com/l/quick_render | 2026-11-26 | Last push 2023-10-01 | GPL-3.0 | unknown | Free ($0 on Gumroad) | **Temp**: "creates a camera at current view before render" | Creates a camera object | n/a | Combined only | Scene output format | 1 click | Same UX goal (snapshot from view), no data passes |
| **adriflex/Textures_diffusion** (+ ComfyUI_Blender_Texdiff nodes) | https://github.com/adriflex/Textures_diffusion · https://github.com/adriflex/ComfyUI_Blender_Texdiff | 2026-11-26 | Add-on README 1.0.0/1.0.1, last push 2025-03-30. Nodes last push 2024-05-22 | Add-on GPL-3.0. Nodes: no license | 3.3 LTS | Free | **Yes** (creates an ortho "SD_Camera" in a new projection scene) | Creates new scenes/cameras | n/a | Depth + Normal reference images, camera-occlusion masks | PNG refs, EXR masks | Multi-step | ComfyUI node "From blender Viewport depth" only loads a file |
| **Blender Depth Map Generator** (Milad Kambari, Superhive) | https://superhivemarket.com/products/blender-depth-map-generator | 2026-11-26 | Version not stated. "Published 7 months ago" | GPL (listing) | Conflicting: "5.0 – 5.1" / "5.0 or newer" / "4.0, 4.5, 5.0+" | $12 | **No camera, no viewport**: BVH raycast of a selected mesh from 6 fixed axis directions | Claims non-destructive, "no compositor nodes" | Image Editor | Depth only | EXR/PNG/PSD 16-bit | 4 | Relief/CNC-style baking, different use case |
| **PassPilot** (Superhive) | https://superhivemarket.com/products/passpilot/docs | 2026-11-26 | 1.0.29 (docs) | not stated on docs page | 5.2 only | $9 | **Yes** (pre-render check errors if there's no active camera) | Enables View Layer passes. Claims compositor and output path untouched | n/a | All render passes, ID masks, Cryptomatte, OIDN option | PNG 16-bit default, EXR half/full, others | Tick passes + F12 | Windows x64 only |
| **Industrial AOV Connector** (extensions.blender.org) | https://extensions.blender.org/add-ons/industrial-aov-connector/ | 2026-11-26 | 5.3.0, "Updated 1 w" ago | GPL-3.0-or-later | 4.2 LTS+ | Free | **Yes** (render) | **Yes** (auto-builds compositor outputs) | n/a | All AOVs/passes | EXR (compositing pipeline) | Setup + render | 17.5k downloads. Render-pipeline tool |
| **Output Setup Helper** (extensions) | https://extensions.blender.org/add-ons/output-setup-helper/ | 2026-11-26 | 5.0.1 | GPL-3.0-or-later | 5.0+ | Free | **Yes** | **Yes** (compositor outputs, denoising) | n/a | Multi-pass | EXR | Setup + render | Render-pipeline tool |
| **CryptoMatte ID Color** (extensions) | https://extensions.blender.org/add-ons/cryptomatte-id-color/ | 2026-11-26 | 1.1.1 | GPL-3.0-or-later | 4.5 LTS+ | Free | **Yes** (render/compositor) | **Yes** (adds compositor nodes) | Compositor Viewer | Color-coded object IDs | Multilayer EXR option | Setup + render | ID maps only |
| **Rendersynth** (extensions) | https://extensions.blender.org/add-ons/rendersynth/ | 2026-11-26 | 1.0.0, published 2026-07-24 | GPL-3.0-or-later + MIT | 4.5 LTS+ | Free | **Yes** (randomized camera) | Yes, by design (randomizes the scene) | In-Blender preview of labels | Depth maps, normal maps, COCO segmentation/keypoints, YOLO, point clouds | Dataset formats | Batch pipeline | CV dataset generator. Permission: files |
| **Darkly** (extensions) | https://extensions.blender.org/add-ons/darkly-stream/ | 2026-11-26 | 0.4.1 | GPL-3.0-or-later | 5.1+ | Free | **No** (streams the viewport) | Optional film transparency | In the Darkly paint app | Color only | PNG stream | Start/stop | Shows viewport-capture UX on the platform; no data passes |
| **ectomia/Blender-to-Comfyui-Render-Passes-Addon** | https://github.com/ectomia/Blender-to-Comfyui-Render-Passes-Addon | 2026-11-26 | Last push 2026-07-22 | No license | 5.1+ (4.x fallbacks) | Free | **Yes** (F12) | **Yes**: replaces the compositor tree, disables other view layers, may switch the engine to EEVEE | n/a | Clay, Depth, Outline (Freestyle), Alpha | Depth 16-bit PNG (per-frame Normalize), others 8-bit | Build + F12 | Script distributed as .rar |
| **coolzilj/Blender-ControlNet** | https://github.com/coolzilj/Blender-ControlNet | 2026-11-26 | Last push 2023-03-26 | MIT | unknown | Free | **Yes** (F12 + compositor template) | Yes (template compositor) | n/a | Depth + segmentation to ControlNet | n/a | Edit code/nodes, then F12 | 768 stars. Stale |
| **DLR-RM/BlenderProc** | https://github.com/DLR-RM/BlenderProc | 2026-11-26 | v2.7.2, 2024-10-22. Last push 2026-01-20 | GPL-3.0 | own pipeline | Free | **Yes** (scripted cameras) | Scripted scenes | n/a | Depth, normals, segmentation, etc. | EXR/HDF5 etc. | Python scripting | CV pipeline, not a GUI add-on |
| **Viewport Render Multilayer** (Superhive) | https://superhivemarket.com/products/viewport-render-multilayer | 2026-11-26 | "about 5 years ago" | GPL | 2.9–2.93 | $1.11 (free via GitHub link on page) | **No** (viewport render) | unknown | n/a | View layers as viewport renders (no data passes stated) | unknown | 3 | Obsolete |
| **VP RENDER 2.0** (Superhive) | https://superhivemarket.com/products/vp--render-2 | 2026-11-26 | "almost 4 years ago" | GPL | 3.0–3.5 | $6 | unknown (viewport render) | unknown | n/a | Viewport/wireframe render, no passes | unknown | 1 | Obsolete |
| **Texturaizer** (Superhive) | https://superhivemarket.com/products/texturaizer | 2026-11-26 | v0.2.5. "almost 2 years ago" | GPL | 4.2–4.5 | $36–$499 tiers | unknown | unknown | Viewer panel | "multipass render layers" (unspecified) | unknown | unknown | ComfyUI texturing |

Other items seen but **not opened** (search snippets only, so treat as unverified): "Easy Render Passes Manager" (Superhive, ~$25, compositor-based pass export), "Build Export Node" (bookyakuno, Blender Market/Gumroad, view-layer pass export nodes), "Cid – Color IDs Simply" (Superhive), "B2ControlNet" (BOOTH 4548229, pose keypoints only), oimoyu/simple-comfyui-texture (no license; mist pass + scene camera), FrederikHasecke/diffused-texture-addon (GPL-3.0; scene camera + Z/normal passes). Image-to-depth AI estimators (EZdepth, AutoDepth AI, ADC AutoDepth, True Depth, EZtexture, AI Depth Modeller) estimate depth from 2D images and are out of scope, but they crowd the "Depth" naming space on Superhive.

---

## 2. Blender built-in alternatives (details)

Sources: Passes manual (5.3) https://docs.blender.org/manual/en/latest/render/layers/passes.html ; Viewport Render manual https://docs.blender.org/manual/en/latest/editors/3dview/viewport_render.html ; Shading manual https://docs.blender.org/manual/en/latest/editors/3dview/display/shading.html ; Camera Data node https://docs.blender.org/manual/en/latest/render/shader_nodes/input/camera_data.html . All fetched 2026-11-26. WebFetch was blocked with 403, so I used curl.

**What the manual says (5.3):**
- **Depth** (formerly "Z") is listed for Cycles, EEVEE **and Workbench**: "Distance to the nearest visible surface." The manual notes it is noisy with DoF/motion blur and suggests Mist instead.
- **Mist** (Cycles, EEVEE): distance "mapped to the 0.0 - 1.0 range". The mapping uses the World mist settings (start, depth, falloff), so the normalization depends on the user.
- **Normal** (Cycles, EEVEE): "Surface normals in **world space**." Camera-space normals need extra compositor math or an AOV/shader trick.
- **Position** (Cycles, EEVEE): world-space positions.
- **Object Index / Material Index: Cycles only.** For EEVEE the route is **Cryptomatte** (Cycles + EEVEE). Cryptomatte stores hashed IDs plus coverage, not simple integer IDs, and you extract a matte with the Cryptomatte node. The ID Mask node needs the IndexOB/IndexMA pass.
- "The **Depth, Position, Object Index, and Material Index passes are not anti-aliased**." Cycles' Alpha Threshold controls which surfaces write data passes.

**What the Cycles Depth pass really encodes (evidence from Blender source on the GitHub mirror, read 2026-11-26):**
- In current `main` (and tags v2.90.0 through v4.5.0), the Cycles depth pass writes `camera_z_depth()` on the **first sample only**.
- For **perspective and orthographic cameras**, that function returns the camera-space Z coordinate, i.e. **planar distance along the view axis**.
- For **panoramic** cameras it returns the **Euclidean distance** to the camera position.
- The switch happened in commit `18cda8be87` "Cycles: change perspective depth pass to be more standard" (2020-06-02), so it shipped in **Blender 2.90**. Before that (e.g. v2.82) Cycles wrote the radial `camera_distance()`.
- Archived issue #76585 (Blender 2.82, May 2020) shows the old radial behavior and an EEVEE vs. Cycles mismatch: https://projects.blender.org/blender/blender/issues/76585 . Forum posts from that era claiming Cycles Z is radial are outdated for 2.90+.
- **EEVEE Depth**: per #76585 commentary and third-party code comments (Blended_Comfy calls it "linear camera-space depth in scene units"), EEVEE gives planar camera depth. The manual itself does not state the metric, so treat this as **not officially documented**.
- Sign convention: the passes store a positive distance. Camera-space "−Z" in ViewPass terms equals this positive planar depth.

**Steps for the built-in route:**
1. Need an **active camera**. F12 does not render without one. To match the viewport you would align the camera to view (View > Align View > Align Active Camera to View) or use "Lock Camera to View".
2. View Layer > Passes: enable Depth / Normal / (Cycles) Object Index or Cryptomatte.
3. Compositor: wire Render Layers outputs to File Output, use EXR (Float Full) for raw data, or add Normalize/Map Range for a PNG preview. Note: since **Blender 5.0**, `scene.node_tree` was removed and `scene.use_nodes` is deprecated (compositor is now a node group via `scene.compositing_node_group`) — https://developer.blender.org/docs/release_notes/5.0/python_api/ . This breaks several older add-ons below.
4. Color management: use Standard/Raw/Non-Color for PNG data outputs.
5. Render (full engine render: Cycles samples, or EEVEE/Workbench). Workbench is fastest and supports Depth but not Normal/IndexOB per the manual table.
6. Save or collect the files.

Repeat exports are about 3 actions plus render time. This route modifies the scene's view layer, compositor and output settings.

**Viewport Render (View > Render Viewport Preview; "Render Playblast" for animation in 5.x naming):**
- "lets you create quick preview renders from the current viewpoint (rather than from the active camera …) … if you are not in an active camera view, a virtual camera is used to match the current perspective."
- "only works for the Workbench and EEVEE render engines. It's not supported for Cycles."
- Uses Resolution, Aspect, Output path and File format from the output settings.
- Output is what the viewport displays (Combined), so there are no data passes. Common tricks:
  - **Workbench MatCap with a normal-encoding MatCap.** FastPBR ships its own normal MatCap EXR for this.
  - Viewport shading **"Render Pass"** dropdown (Material Preview/Rendered: "Instead of the combined render, show a specific render pass").
  - EEVEE mist for height. FastPBR's README says this is 8-bit-limited.
- Whether Viewport Render captures a non-Combined "Render Pass" display: **unverified**.
- These tricks are quantized, display-referred and color-managed, not metric depth or integer IDs.

---

## 3. Per-tool notes (claims vs. evidence)

### 3.1 PLAN8VR/Depth_Map — https://github.com/PLAN8VR/Depth_Map
- **Claims:** "A simple Blender plugin to export depth maps"; a "one hit" button in Render properties that sets up a normalised Z-pass compositor and exports a PNG. "Camera required in scene (will change soon)"; recommends an ortho 1:1 camera.
- **Evidence (source `depthmap.py`, read 2026-11-26):**
  - bl_info: name "True Depthmap Export", version 0.0.2, Blender 4.0.2.
  - Uses the scene's active camera.
  - Temporarily forces resolution 1024×1024 at 100%, EEVEE, film transparent, view transform Raw, look None, sequencer colorspace Non-Color. These are restored afterward.
  - Enables the view-layer Z pass.
  - **Clears the existing compositor node tree** and builds Render Layers, Invert, Normalize, Set Alpha, Viewer and File Output (slots "Depth" + "Diffuse").
  - Calls the regular render operator with write-still.
  - Output: PNG RGBA 16-bit.
  - The compositor tree, use-nodes, compositing toggle and Z pass are **not restored**.
  - Uses `scene.node_tree` (removed in 5.0).
- Metadata: 11 stars. Last commit 2024-03-06. No releases. License GPL-2.0 per GitHub detection (whether "or later" applies: unknown).

### 3.2 Limbicnation/Blender-Depth-Map-Generator — https://github.com/Limbicnation/Blender-Depth-Map-Generator
- **Claims:**
  - Automates Z-depth creation with a clean UI.
  - Blender 4.2+, tested on 4.5 LTS / EEVEE Next and Cycles.
  - Depth chain "Depth → MapRange → Contrast → ColorRamp" for preview, with File Output tapping the raw Map Range so the export "stays linear".
  - EXR only (depth 32-bit float ZIP, mask 16-bit half). Masks via Cryptomatte (default) or Object Index (Cycles).
  - Animation rendering supported. "Reset Compositing" removes add-on nodes.
- **Evidence (source, read 2026-11-26):**
  - Manifest: id `depth_map_generator`, version 2.0.0, `blender_version_min` 4.2.0, license `SPDX:Apache-2.0`, tags Render/Pipeline/ComfyUI. No permissions declared, even though it writes files.
  - Setup enables `use_pass_z`, `use_pass_object_index` or Cryptomatte object passes (accurate mode, depth 6) and sets use-nodes.
  - Creates `DM_`-named compositor nodes and removes only `DM_` nodes on re-setup or reset, so user nodes are preserved.
  - Render and mask export call the regular render operator, so a camera is required.
  - Exported depth is the Map Range output: **normalized to user near/far, not raw metric**.
  - Accesses `scene.node_tree` without a 5.x fallback, so likely incompatible with 5.0+ (inferred, not tested).
- Metadata: 3 stars. Last commit 2026-06-18. Apache-2.0 is GPL-3-compatible. Not found in extensions.blender.org searches.

### 3.3 x6ud/controlnet-render-blender-addon — https://github.com/x6ud/controlnet-render-blender-addon
- **Claims:** "One-click shortcut to render normal map, depth map, and edge for ControlNet input." Workflow: Rendering workspace, N panel, ControlNet tab, check options, **save file**, click "Render Input Images". Needs SD WebUI with `--api` for generation.
- **Evidence (source, read 2026-11-26):**
  - bl_info Blender 3.5.0, version (1, 0).
  - Compositor setup enables the Z and Normal passes (object index commented out) and sets render resolution from add-on properties. Engine is not changed. **Nothing is restored**.
  - Depth branch: normalize, invert, color ramp.
  - Normal branch: custom node groups rotate world normals by the inverse camera rotation (camera space), then negate X. A switch allows raw world normals.
  - Edge branch: Laplace filters on depth and normal, thresholded with color ramps, combined with Lighten.
  - A File Output node writes image/depth/edge/normal. Format and bit depth are not set (Blender defaults).
  - The render operator is the regular `render.render` with the `use_viewport` flag. That flag uses the viewport's layers/local camera, so a camera object is still required.
  - Loaded results are PNG. Generation posts base64 PNGs to `/sdapi/v1/txt2img|img2img`.
  - Uses `scene.node_tree`, so likely broken on 5.x.
- Metadata: 10 stars, MIT, single release v1.0.0 (2023-06-19).

### 3.4 carson-katri/dream-textures — https://github.com/carson-katri/dream-textures
- **Claims:** "Stable Diffusion built-in to Blender"; depth-to-image texturing; Cycles render pass re-styling; node system; ControlNet (v0.2.0+); ControlNet pre-processors (v0.4.0).
- **Evidence (source, read 2026-11-26):**
  - **Depth annotation:** creates a `GPUOffScreen`, loads view and projection matrices, draws every mesh (evaluated) with a uniform-color shader with depth test, and reads back the **depth buffer** (non-linear NDC depth). It then inverts and min/max-normalizes it to 0–1. The result is relative and perspective-non-linear, not metric.
  - **Normal annotation:** the same offscreen approach with a custom shader that outputs view-space normals (rotated by the model-view matrix). Background is cleared to (0.5, 0.5, 1).
  - **ADE20K:** per-object user-assigned category colors drawn the same way.
  - **Viewport color:** uses `draw_view3d` into an offscreen.
  - The annotation functions default to the **scene camera**'s matrices. However, the "Project Dream Texture" operator passes the **current viewport's** `region_3d.view_matrix` / `window_matrix` and region size. That is effectively a camera-free GPU geometry pass from the current view, which is the same core technique ViewPass plans.
  - Outputs stay in memory as numpy/Blender images feeding the diffusion pipeline. There is no user-facing "export depth/normal/ID as files" feature.
  - `realtime_viewport.py` is marked "still under development, and is not currently used" and captures color only.
- Metadata: 8.3k stars. GPL-3.0. Last release v0.4.1 (2024-08-26), builds for 3.6–4.0 and 4.1+. Commits as late as 2026-09-17. Heavy install (multi-GB, 7z archives on Windows).

### 3.5 SDWebUITools — https://superhivemarket.com/products/sdwebuitools
- **Claims:**
  - $1, MIT, Blender 4.1, Windows only, by Derek Wang (mixshaders).
  - Needs stable-diffusion-webui + ControlNet. "Supports 3 ControlNet units/Lora/Interrogate/ADetailer."
  - Workflow: a "Compositing Render" for depth + canny ControlNet inputs, then "Project from View" UV mapping from the current camera or viewport view.
- **Evidence:** none beyond the listing (closed download). Camera need, settings changes, precision and steps: **unknown**.

### 3.6 FastPBR (Fast PBR Viewport Render) — https://github.com/ItsCubeTime/FastPBR
- **Claims:**
  - Fetches curvature, AO, normal, transparency, MatID and height "from the camera you're currently looking through or **directly from your viewport**" using Blender's "Render viewport" operator ("what you see is what you get").
  - "works by modifying your render settings and renderer (it uses Eevee and workbench …)" and restores them, with a manual "restore settings" fallback.
  - Several 4K maps in seconds. Multi-camera batch. File naming system.
  - **Windows only.** PNG only.
  - Normal maps need its bundled normal MatCap EXR.
  - Height uses EEVEE mist, "limited to 256 possible values per pixel".
- **Evidence:** repo tree (README + `__init__.py`, `fileRenamer.py`, an assets .blend). bl_info Blender 3.0 (README says the git source is outdated vs. releases). Imports PIL. Latest release 1.8.0 (2023-04-11). **No license file in the repo** (GitHub reports none), so redistribution terms are unclear.
- **Relevance:** the only found tool that is camera-free **and** multi-map **and** one-click. Its approach (separate viewport renders per pass with engine/setting swaps, 8-bit PNG, MatCap normals, mist height) is exactly the "viewport render trick" family. It is not a raw-data exporter.

### 3.7 Blended_Comfy — https://github.com/joris-sta/Blended_Comfy
- **Claims:** a Blender add-on plus ComfyUI nodes. Renders "the current camera view" as Depth, Beauty, Normal, UV, Outline over localhost HTTP. No temp files. Blender 5.
- **Evidence (source):**
  - Per request it switches `scene.camera` to the requested camera and sets the resolution (both restored).
  - Enables the Z pass (restored) and builds a temporary compositor with a Viewer node (cleaned up).
  - Calls the regular render, reads float pixels from the Viewer image, masks background by camera clip end, robust-normalizes, and encodes 16-bit grayscale PNG.
  - Camera is **required**.

### 3.8 Reshoot (Superhive) — https://superhivemarket.com/products/reshoot
- **Claims:**
  - $39, Pardesco LLC, GPL-3.0-or-later, Blender 4.5–5.2, Windows tested.
  - Renders the active camera with Combined, mist-based depth, world-space 8-bit normal, albedo and a Cryptomatte selection mask. Sends them to a local ComfyUI "capsule" and returns the result.
  - Temporary view layer and compositor, with everything restored. No telemetry.
- **Evidence:** listing only.

### 3.9 ComfyUI-BlenderAI-node (AIGODLIKE) — https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node
- **Claims:** ComfyUI inside Blender; "camera input"; "Input image from viewport (supports real-time refresh)"; "Composite depth channel"; masks by projecting objects on the camera.
- **Evidence (source `SDNode/utils.py`, `operators.py`):**
  - Data sources include camera_viewport (viewport render with view context; checks for a scene camera), render_viewport (regular render), depth_viewport and mist_viewport.
  - Depth/mist temporarily enable the Z/mist pass and compositor, call the regular render, and then restore the pass flags.
  - Other operators set up compositor depth chains and render with the camera.
  - So depth needs a **camera** and a full render.

### 3.10 StableGen — https://github.com/sakalond/StableGen
- README: "It renders guidance images from **cameras in your scene**". First step: "Select the mesh and click **Add cameras**". Multiple ControlNet units (Depth/Canny/Normal) are used internally. Blender 4.2–4.5 and 5.1+ (5.0 unsupported). v0.5.0 (2026-11-04), GPL-3.0, 1.7k stars.

### 3.11 AI Render — https://github.com/benrugg/AI-Render
- README: "Blender 3.0.0+", Win/Mac/Linux. Free on GitHub releases, also Blender Market/Gumroad.
- Evidence: the operator calls the regular render. ControlNet uses A1111 preprocessor "module" on the rendered image, so depth is estimated, not geometric. MIT. v1.1.1 (2025-12-28).

### 3.12 toyxyz rig (Gumroad) — https://toyxyz.gumroad.com/l/ciojz
- Listing text (from page JSON): "Blender version 3.5 or higher is required". Version log up to V101. Outputs listed: Depth, Canny, Landmark, MediaPipe face, finger, camera pose; body meshes for Depth/Normal/Seg/Lineart. 830 ratings, average 5.0.
- Render pipeline details (camera, compositor) were not inspected (download required), so they are **unverified**.

### 3.13 Quick render (Pullusb) — https://github.com/Pullusb/Quick_render
- README/listing: "export view snapshots in 3D view"; "The button render view **creates a camera at current view** before render to make a 'real' render". Combined only. GPL-3.0. Last push 2023-10-01. $0 on Gumroad, 23 ratings.

### 3.14 Textures Diffusion (adriflex) — https://github.com/adriflex/Textures_diffusion
- Evidence: the operator creates a new projection scene with an **orthographic "SD_Camera"**. "Render ref images" requires a scene camera and renders normal/depth reference PNGs. Bakes camera-occlusion masks to EXR.
- The companion ComfyUI node "From blender Viewport depth" (`ViewportDepth`, https://comfy.icu/node/ViewportDepth) only loads an image file. Its page notes that 16-bit PNG depth gets flattened to 8-bit.

### 3.15 Blender Depth Map Generator (Milad Kambari) — https://superhivemarket.com/products/blender-depth-map-generator
- Claims: "Uses BVH raycasting for pixel-perfect accuracy, no render engine needed". Selected mesh, 6 fixed directions (Front/Back/Top/Bottom/Left/Right). 256–4096 px. EXR/PNG/PSD 16-bit. "Non-destructive". $12, GPL. Blender version claims conflict (5.0–5.1 vs 4.0+).
- Not view-based. It targets relief/CNC/reference depth of a single object.

### 3.16 Render-pipeline helpers on extensions.blender.org
- Industrial AOV Connector, Output Setup Helper, CryptoMatte ID Color, AutoAOV, LayerCake and Sync Render Sets all require a camera render and modify compositor/view-layer setup.
- Rendersynth (CV datasets with depth/normal/segmentation) is camera/batch-based.
- **No camera-free viewport data-pass exporter was found on extensions.blender.org.** Searches run 2026-11-26: depth, depth map, z depth, zdepth, normal map, viewport, controlnet, passes, render passes, mist, object id, mask, comfyui, stable diffusion, ai render, synthetic, segmentation, screenshot, export viewport, plus page 2 where available.

### 3.17 Other GitHub items
- **ectomia/Blender-to-Comfyui-Render-Passes-Addon:** README says it "REPLACES the scene's compositor node tree", "Disables every other view layer", and switches the engine to EEVEE if on Workbench. Depth is 16-bit PNG with per-frame Normalize ("pulse" warning).
- **coolzilj/Blender-ControlNet:** F12 plus a compositor template sending depth + segmentation to A1111. 768 stars. Stale since 2023-03.
- **BlenderProc:** a GPL-3.0 CV rendering pipeline (camera-based, scripted).
- GitHub code search for viewport depth readback (`read_depth` + `region_3d.view_matrix`) only surfaced Dream Textures and its forks (including intel/dream-textures-openvino), plus unrelated repos.

### 3.18 BOOTH (booth.pm)
- Search (JP terms for depth/normal/ControlNet) found **B2ControlNet** (https://booth.pm/ja/items/4548229, pose keypoints as image/json, no depth/normal per snippet). The page itself was not opened, so details are **unverified**.
- No BOOTH depth/normal exporter was found.

---

## 4. Differentiation assessment (critical)

**Bottom line:** I found **no existing tool that combines all of these:**
- camera-free (current viewport)
- no scene/render/compositor changes
- metric linear depth in float EXR
- camera-space normal
- integer object ID + mask
- one click, written to files

The closest pieces exist separately:
- **Dream Textures** already does a camera-free GPU offscreen geometry draw from viewport matrices, but only as an internal AI conditioning step: normalized non-linear depth, no files, no integer IDs, heavy AI install, last release 2024.
- **FastPBR** already does camera-free one-click multi-map export, but through viewport-render tricks: 8-bit PNG, MatCap normals, mist height, temporary render-setting swaps, Windows only, stale since 2023, no license file.
- **Blender's own compositor** already gives pixel-aligned, full-float, metric depth plus IDs, but needs a camera, scene changes and a full render.

**Where ViewPass would be genuinely better:**
1. **No camera object.** Every render-based tool (PLAN8VR, Limbicnation, x6ud, Blended_Comfy, Reshoot, PassPilot, BlenderAI-node depth, StableGen, AI Render) needs a scene camera. Quick render creates one.
2. **Truly non-destructive.**
   - PLAN8VR wipes the compositor.
   - x6ud and ectomia leave or replace nodes and passes.
   - Limbicnation leaves passes and `DM_` nodes until reset.
   - FastPBR swaps engine and settings (restore can fail on crash).
   - Even "restoring" tools (Blended_Comfy, Reshoot) touch the scene during export.
   - ViewPass touching nothing is a real, auditable differentiator, especially for users with production compositor setups.
3. **Speed.** No path-tracing samples and no engine switch, so it is near-instant at any engine setting. Cycles users avoid a full render just to get a guide image.
4. **Metric linear depth in float EXR from a camera-free tool.** Most AI-oriented tools export normalized 8/16-bit (x6ud, Blended_Comfy, ectomia, Reshoot mist, PLAN8VR, FastPBR). Limbicnation's EXR is Map Range-normalized. Dream Textures' depth is non-linear. Only the manual compositor route matches on precision.
5. **Integer object ID without Cycles.** Built-in IndexOB is Cycles-only. EEVEE users must use Cryptomatte (hashed float IDs needing a decoder). A plain integer ID map is directly usable for segmentation and masking.
6. **Engine-independent and modern platform compliance.** Several competitors use `scene.node_tree` (removed in Blender 5.0), so they are likely broken on 5.x. A 4.2+ extension with a manifest, GPL-3.0-or-later and files-only permission fits extensions.blender.org, where no direct competitor is listed.

**Where ViewPass would NOT be better (or is weaker):**
1. **Pixel alignment is not unique.** All passes from one Blender render are pixel-aligned too (compositor route, Reshoot, Blended_Comfy, Limbicnation). Alignment is table stakes, not a selling point by itself. It only beats per-pass separate renders (FastPBR) if the view changed between renders.
2. **Geometry-only.** A raster pass of evaluated meshes will miss or differ from the render on:
   - shader displacement, bump and normal maps (shading normals vs. geometric normals)
   - alpha-clip/blend transparency (leaves, decals)
   - volumes
   - hair/curves and point clouds, unless handled explicitly
   - Grease Pencil
   - holdout/visibility flags and ray-visibility settings
   - render-only modifiers or levels (viewport vs. render subdivision)
   - instancing via geometry nodes (must iterate depsgraph instances)
   
   Render-engine passes handle these natively.
3. **Not the final render camera.** If the user needs passes that match the production camera (sensor fit, lens shift, overscan, DoF, exact resolution, clip range, panoramic), camera-based tools are the correct choice. Viewport aspect and clip start/end differ from the camera's. ViewPass should at least support "use camera when in camera view".
4. **Aliasing.** A single-sample raster pass is aliased, like Cycles' non-AA data passes. That is fine for IDs and ControlNet but worse than AA'd Mist/Normal for compositing. Supersampling conflicts with integer IDs unless handled carefully.
5. **No animation/sequence export** (if not planned). Limbicnation, Blended_Comfy, ectomia and the compositor route do frame ranges, which matters for video ControlNet (AnimateDiff, Wan, etc.).
6. **No AI round-trip.** Reshoot, Blended_Comfy, StableGen, BlenderAI-node and Dream Textures push straight into SD/ComfyUI. "Local files only" means extra manual loading. ViewPass's ComfyUI users may still prefer a bridge.
7. **Normal convention mismatch risk.** ControlNet normal models expect specific axis and sign mappings (x6ud flips X). Camera-space normals must be documented or offered with presets, or users will see "wrong" colors.
8. **Technical risk areas:**
   - GPU offscreen availability in background/headless mode.
   - Metal/Vulkan backend differences.
   - Depth-buffer precision if depth is derived from the depth attachment instead of written linearly to a float target.
   - Python-side batch building for large scenes (Dream Textures rebuilds batches per mesh per call, so heavy scenes can take seconds).
9. **"Free + simple" is crowded at the low end.** Users can already do it manually with the compositor once and reuse the .blend. The value proposition must lean on *camera-free + untouched scene + raw float data + EEVEE/Workbench integer IDs*.

---

## 5. Name collision check (web search only — **not legal clearance**)

Checked 2026-11-26 on extensions.blender.org (search), GitHub (repo-name search via API), general web search, and Superhive via web search (Superhive's own search is JS-only, so I did not query it directly).

| Candidate | extensions.blender.org | GitHub | Superhive / web | Verdict |
|---|---|---|---|---|
| **ViewPass** | No match (results: View Layer Plus, Palette Colorizer) | ~20 repos named viewpass: AppifyDevs/viewpass (Chrome extension that toggles password-field visibility), joelburton/django-viewpass (token access to Django pages), ApolloXoN/ViewPass ("Viewings Pass application"), several bus-pass page dumps | Similar-sounding **VPass** visitor-management software (vpass.io, Capterra/App Store). A Nieman Lab PDF proposal for a publisher payment system "ViewPass" (https://www.niemanlab.org/pdfs/ViewPass.pdf). No 3D/graphics product found | No obvious collision in 3D/graphics. The name is generic and carries a "view password" connotation in software |
| **"View Pass" Blender** | Generic pass add-ons only | n/a | Only Blender manual pass pages | No obvious collision found |
| **Viewport Pass Exporter** | No match | 0 repos | No product found | No obvious collision found (descriptive, so weakly distinctive) |
| **PassSnap** | No match | AryeBorgen/PassSnap, prajapativiv/passsnap- (no descriptions), passsnapper-chrome | Nothing in 3D. Note **PassPilot** (Superhive, $9 render-pass saver) is similar-sounding in the same niche | No obvious collision. Mild confusion risk with PassPilot |
| **SnapPass** | No match | **pinterest/snappass** (906 stars, password-sharing tool), Snappass.NET, SnapPass forks | **"SnapPass – AI image editor"** iOS app (image editing) | **Collision, avoid** |
| **PassGrab** | No match | Repos named PassGrab/passGrabber are **password-stealing tools** | No product found | **Avoid** (reputational risk) |
| **ViewportPasses / Viewport Passes** | No match | 0 repos | No product found | No obvious collision found |
| **DepthNormal Snap / DepthNormal** | n/a | SnazzyGaz/DepthNormal, vito0131/ComfyUI-DepthNormalizer, research repos | No product found | No obvious collision. Clunky |
| **ViewSnap** (my candidate) | n/a | anttiromppanen/viewsnap (3 stars), iOS snapshot-test libs (ViewSnapshots) | No product named ViewSnap found. Similar: Artec "ViewShape" 3D viewer | No obvious collision. Some dev-tool overlap |
| **ViewGrab** (my candidate) | No match | 0 repos | No product found. Similar: Unigine "AppGrabber", VidGrab | No obvious collision found |
| **DepthSnap** (my candidate) | No match | Bell-South/DepthSnap (GoPro distance toolkit, 0 stars) | Depth-camera iOS apps with different names | No obvious collision. Implies depth-only |
| **PassCam** (my candidate) | No match | zekariass/PassCam (4 stars) and others | n/a | No obvious collision. Ambiguous meaning |

- **Not checked:** USPTO (tmsearch.uspto.gov), EUIPO eSearch, WIPO Global Brand Database, J-PlatPat. These are JS apps or need interactive sessions, so no queries were made.
- Also not checked: Apple App Store / Google Play beyond what web search surfaced.
- Recommendation from the web evidence: "ViewPass" has no 3D-space collision, but a descriptive subtitle helps distinctiveness and searchability (e.g., "ViewPass — Viewport Pass Exporter"). Avoid "SnapPass" and "PassGrab".
- Blender Extensions ToS (2.1) forbids "Blender" in the extension name, so "ViewPass for Blender" is not allowed as the name itself.

---

## 6. Blender Extensions platform rules relevant to publishing (checked 2026-11-26)

Sources:
- Terms of Service (last updated 10 August 2026): https://extensions.blender.org/terms-of-service/
- About / publishing flow: https://extensions.blender.org/about/
- License page (manual 5.3): https://docs.blender.org/manual/en/latest/advanced/extensions/licenses.html
- Add-on extension page (manual): https://docs.blender.org/manual/en/latest/advanced/extensions/addons.html
- Add-on Guidelines: https://developer.blender.org/docs/handbook/extensions/addon_guidelines/
- Moderation guidelines: https://developer.blender.org/docs/features/extensions/moderation/guidelines/
- Manifest schema 1.0.0: https://developer.blender.org/docs/features/extensions/schema/1.0.0/

The developer.blender.org and docs.blender.org pages returned 403 to the fetch tool but loaded fine via curl.

**License**
- Manual: "The Blender Extensions Platform only supports free and open source extensions compliant with the Blender's license." Add-ons: "The required license is **GNU General Public License v3.0 or later**." "For assets used in add-ons, the required license is **Public Domain (CC0)**."
- ToS 1.1: "Uploaded add-ons must be wholly compliant with the GNU General Public License, version 3 or later."
- ToS 1.2: "Binary files or other types of assets included in the extension (images, SVG files, fonts, etc.) must be licensed as Public Domain (CC0)." This applies to icons, thumbnails and bundled MatCaps.
- ToS 1.3: credit bundled copyrighted code in the manifest `copyright` field.
- Manifest example: `license = ["SPDX:GPL-3.0-or-later"]`.
- Observation: some listed add-ons declare GPL-3.0-or-later plus MIT (e.g. Rendersynth), so GPL-compatible permissive components appear to be accepted alongside GPL-3.0-or-later.

**Manifest (`blender_manifest.toml`, schema 1.0.0)**
- Required: `schema_version`, `id`, `version` (semver), `name`, `tagline` (no end punctuation), `maintainer`, `type` ("add-on"), `blender_version_min` (at least "4.2.0"), `license`.
- Optional: `blender_version_max`, `website`, `copyright`, `tags`, `platforms`, `wheels`, `permissions`, `[build] paths_exclude_pattern`.
- Fields present must not be empty.
- **Permissions** for add-ons: `files`, `network`, `clipboard`, `camera`, `microphone`. Each needs a one-sentence reason with no trailing period.
- Moderation guidelines: "`files` is expected for most I/O add-ons". ViewPass writes EXR/PNG, so declare `files` (e.g. `files = "Write exported depth, normal, ID and mask images to disk"`).
- No `network` permission is needed for a local-only tool.

**Bundled binaries / dependencies**
- ToS 3.5: "Extension code must be reviewable: no obfuscated code or byte code is allowed."
- ToS 3.6: "Source code of the extension must be fully written in Python. Depending on external, pre-compiled packages is not allowed."
- Guidelines: "Add-ons must not install Python modules, PIP packages, Python-wheels etc." The manual says to bundle dependencies with Python wheels via the manifest `wheels` ("recommended way") or vendorize pure-Python modules.
- These two statements are in some tension for compiled wheels. Safest for ViewPass: rely only on Blender-bundled modules (`bpy`, `gpu`, `gpu_extras`, `mathutils`, `numpy`) and Blender's own image I/O for EXR/PNG, with no wheels.
- ToS 5.1: must be self-contained and "not load remote code". ToS 5.2: no external components to download. ToS 5.3: no dependency on other extensions.

**Network / online access**
- ToS 4.1–4.5 and the Guidelines: if connecting to the internet, request `network`, respect `bpy.app.online_access`, and send nothing without explicit user action.
- Moderation guidelines: "It should not depend on external servers (localhost is fine)."
- "Open in browser" buttons don't need the network permission (ToS 4.4).
- A local-only ViewPass needs none of this.

**Other code rules (guidelines / moderation)**
- Use `__package__` (not `__name__`) for preferences.
- Use relative imports.
- Never write into the add-on directory. Use `bpy.utils.extension_path_user(__package__, create=True)` for user data.
- No `sys.path` manipulation.
- No auto-updater.
- Don't interfere with other add-ons.
- Avoid hard-coded datablock names and `bpy.data.objects` misuse.
- Handle `keyconfigs.addon` being None in background mode.
- No backslash path separators.
- The moderation guidelines suggest a ruff check.

**Content, branding and ads**
- No "Blender" in the name (2.1). No Blender logo in icons or thumbnails (2.2). No implied endorsement (2.3).
- Third-party logos (e.g., ComfyUI, ControlNet) only with permission evidence (2.4).
- Clear description of everything it does (3.1). Fully functional and maintained (3.3).
- No ads or donation buttons in the Blender UI (6.1). Donation links are allowed in the platform description.

**Review process**
- About page: "Read the Terms of Service → Follow the guidelines in the User Manual → Upload your Extension → Wait for Review."
- Moderators work from an **Approval Queue** (https://extensions.blender.org/approval-queue/) using the moderation guidelines:
  - actually runs it
  - checks manifest/permissions
  - checks `__file__`/`open`/`sys`/`requests`/`urllib` usage
  - checks image weight (no heavy GIFs)
  - checks author ownership
- Extensions don't auto-update; users check for updates manually.
- Typical review latency was not stated on the pages I read.

---

## 7. Access problems / unverified items
- docs.blender.org, developer.blender.org, projects.blender.org and devtalk.blender.org returned 403 to WebFetch. Content was retrieved via curl or the Gitea API instead, except devtalk thread 13081, which I did not open.
- Superhive on-site search is JS/Cloudflare-gated, so I used web search with listing pages fetched individually. Easy Render Passes Manager, Build Export Node and Cid were not opened.
- Gumroad listing details were parsed from embedded page JSON. toyxyz rig internals are unverified.
- SDWebUITools internals, Reshoot internals and PassPilot internals are listing claims only.
- Trademark databases (USPTO, EUIPO, WIPO, J-PlatPat) were **not checked**.
- "Likely broken on Blender 5.x" for PLAN8VR, x6ud and Limbicnation is an inference from their use of the removed `scene.node_tree` API. None were tested.
