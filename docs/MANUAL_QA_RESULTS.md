# Manual QA results (MANUAL_QA.md U01–U14)

Environment for automated equivalents: Windows 11, Blender 5.3.0, RTX 3060 Ti, Vulkan and OpenGL; the same
GUI suite also passes in CI on Linux with Blender 4.5.17 LTS and 5.3.0 (Mesa software OpenGL).

**Important:** no human clicked through these steps yet. "AUTOMATED" means a GUI test drives the same
operators/functions in a real GUI session with an analytic or Blender-derived expectation. That is
evidence, but it does not replace a hands-on pass (visual check, file browser, external apps). Items a
person must still do are marked **NOT TESTED (manual)**.

| ID | Check | Result | Evidence / what is still missing |
|---|---|---|---|
| U01 | No camera; switch persp/ortho; export | AUTOMATED PASS | `t_viewport_matrices` (both projections, Blender-projected pixel + depth), camera list unchanged (`snapshot`). Manual: NOT TESTED |
| U02 | Two 3D views at different angles | AUTOMATED PASS | `t_multi_area` (matrices from the invoking view; object left vs right), `t_multi_window` |
| U03 | File dialog, then save / cancel | PARTIAL | View frozen before the browser + explicit error when the view is gone (`t_view_lost`, `export_as` without invoke refused). Real browser save/cancel: **NOT TESTED (manual)** |
| U04 | Local view / hidden / collection exclusion | AUTOMATED PASS | `t_local_view`, `t_visibility` |
| U05 | Modifier / instance / non-uniform scale | AUTOMATED PASS | `t_modifier_and_scale`, `t_instances`, harness |
| U06 | Reversed near/far, fixed range, empty scene | AUTOMATED PASS (code) | `test_encode` (reversed, fixed, near==far error), `t_empty_scene`; preview and export use the same `normalize_depth`. Visual comparison preview vs. file: **NOT TESTED (manual)** |
| U07 | 1080p, tall, square, extreme sizes | AUTOMATED PASS | `t_sizes` (incl. rejection of 20000 px side and > 33.5 MP) |
| U08 | Same name, read-only folder, unicode | AUTOMATED PASS | collisions (`test_export`, `t_operator_export`), ACL-denied folder (`icacls`), unicode folder and name |
| U09 | Preview updating while view closed / file loaded / add-on disabled | AUTOMATED PASS | `t_preview_lifecycle` (closed view, `load_pre`), `t_reregister_clean` (disable with auto preview active) |
| U10 | 20 captures, cancel, fault injection + retry | AUTOMATED PASS | `t_repeat_and_leak` (60), `t_fault_injection`. "Cancel": export is synchronous (no cancel step) |
| U11 | Re-read PNG/EXR in Blender and other apps | PARTIAL | Blender loader + own decoders agree (`t_operator_export`). Other apps (GIMP, Krita, Nuke, ComfyUI, PIL): **NOT TESTED (manual)** |
| U12 | Extension ZIP in a clean configuration | AUTOMATED PASS | `package_suite.py` (isolated user directory) |
| U13 | Scene before/after (camera, material, nodes, selection, frame) | AUTOMATED PASS | `snapshot()` compared in camera, fault, operator, preview tests |
| U14 | Edit mode, camera view, multiple windows | AUTOMATED PASS | `t_edit_mode`, `t_camera_view`, `t_multi_window` |

## Hands-on checklist for the owner (≈15 minutes)

1. Install `viewprism-0.1.0.zip` (Edit › Preferences › Get Extensions › Install from Disk) in Blender 4.5 or 5.3.
2. Open a real project, N-panel › ViewPrism: toggle passes, press the preview refresh icon, try
   Depth / Normal / Object ID / Mask previews and Auto Refresh while orbiting.
3. Export Passes on a saved file (`//viewprism/`), then Export As… and cancel once.
4. Open the PNG/EXR files in the tools you actually use (e.g. image viewer, Krita/GIMP, Nuke, ComfyUI).
5. Undo history and the scene should be unchanged (Edit › Undo History shows no ViewPrism entries).
6. Note anything confusing in the panel; report back.
