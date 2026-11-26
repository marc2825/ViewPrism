# Test matrix

All suites gate on real results: a suite passes only with exit code 0 **and** a result JSON with
`status == "pass"`. Timeouts, missing results and skips count as failures. Expected values come from
analytic geometry or from Blender's own functions, never from ViewPass output.

Run everything (stores sanitised evidence in `docs/evidence/<date>/`):

```
python tools/run_all_checks.py --blender "<path>/blender.exe" [--backends vulkan,opengl] [--bench]
```

## Environments

| Environment | Pure | Harness bg | Harness GPU | GUI suite | Build | Package | Benchmark |
|---|---|---|---|---|---|---|---|
| Windows 11, Blender 5.3.0, RTX 3060 Ti, **Vulkan** | 48 PASS | PASS | PASS | 20/20 PASS | PASS | PASS | done |
| Windows 11, Blender 5.3.0, RTX 3060 Ti, **OpenGL 4.6** | (same) | PASS | PASS | 20/20 PASS | — | — | — |
| CI: Ubuntu, Blender **4.5.17 LTS**, Mesa llvmpipe **OpenGL 4.5** (software) | 48 PASS | PASS | PASS | 20/20 PASS | PASS | PASS | — |
| CI: Ubuntu, Blender 5.3.0, Mesa llvmpipe OpenGL 4.5 (software) | 48 PASS | PASS | PASS | 20/20 PASS | PASS | PASS | — |
| CI: pure tests on Windows + Ubuntu, Python 3.11 / 3.13 (NumPy from PyPI) | PASS | | | | | | |
| Blender 4.5 on Windows/macOS; Blender 5.0 / 5.1 / 5.2 | NOT TESTED | | | | | | |
| macOS / Metal, AMD / Intel GPUs, Linux hardware drivers | NOT TESTED | | | | | | |

Evidence: local Windows run [`docs/evidence/2026-11-26/SUMMARY.md`](evidence/2026-11-26/SUMMARY.md); CI Linux runs
[`ci-2026-11-26-linux-blender-4.5.17`](evidence/ci-2026-11-26-linux-blender-4.5.17/SUMMARY.md) and
[`ci-2026-11-26-linux-blender-5.3.0`](evidence/ci-2026-11-26-linux-blender-5.3.0/SUMMARY.md). Every CI run uploads its
evidence as an artifact (`.github/workflows/ci.yml`).

## Independent harness (`viewpass-dev/harness`, unchanged since import)

| Check | Where |
|---|---|
| register/unregister twice (background) | `blender_check.py` |
| analytic depth/normal/ID at known points; perspective + orthographic; nearest-wins; hidden object; background corner; ID map completeness; alignment depth/mask/ID; non-uniform scale normal; repeat determinism; first result not mutated; scene/datablock state unchanged | `gpu_cases.py` |
| result gate (exit code + JSON status) | `test_runner.py` (self-test PASS) |

## TEST_CONTRACT additional requirements → tests

| Requirement | Test(s) |
|---|---|
| pure: depth normalisation (empty / constant / NaN / range / invert) | `test_encode.DepthNormalize.*` |
| pure: projection | `test_projection.*` (clip ranges, infinite far, generic, log/linear mapping, crop, ortho shift, pixel centres) |
| pure: ID encode/decode | `test_encode.Others.test_id_roundtrip_and_overflow`, `test_export.EndToEnd.*` |
| pure: file names / collisions | `test_export.Names.*`, `Writing.test_atomic_no_overwrite` |
| pure: metadata | `test_export.EndToEnd.test_all_outputs_roundtrip` (content, no absolute paths), `test_id_overflow_fails_only_that_file` |
| CPU reference vs. small analytic cases | `test_codecs` (hand-built PNG with Average/Paeth filters, EXR byte layout, hand-built multi-part EXR) |
| GPU: empty scene | `t_empty_scene` |
| GPU: local view | `t_local_view` |
| GPU: collection exclusion (+ hidden collection, hide, viewport-disabled, wire display) | `t_visibility` |
| GPU: evaluated modifier (position change) | `t_modifier_and_scale` (Array copy at analytic position), `t_edit_mode` |
| GPU: collection / geometry instances | `t_instances` (collection instances + geometry-nodes instances, 3 ID modes) |
| GPU: negative scale | `t_modifier_and_scale` (mirrored closed cube keeps outward normal) |
| GPU: orthographic / perspective from a real viewport | `t_viewport_matrices` (expected pixel from `RegionView3D.perspective_matrix`, depth from `view_matrix`) |
| GPU: camera view | `t_camera_view` (`world_to_camera_view` + rays from `Camera.view_frame`, lens shift) |
| GPU: repeated capture | `t_repeat_and_leak` (60 captures, determinism, memory trend) |
| GPU: retry after GPU failure | `t_fault_injection` (exception after draw; GPU state + scene restored; retry identical) |
| GPU: resolution change / wide / tall | `t_sizes` (1×1, 3×7, 640×160, 160×640, 1080p; oversize + singular rejected) |
| GPU: multi-area | `t_multi_area`, `t_multi_window`, `t_view_lost` |
| UI entry point | `t_operator_export` (operator → files), `t_preview_lifecycle` |
| IO: real 8/16-bit PNG | `test_codecs.Png.test_header_layout_matches_spec`, `t_operator_export` (Blender loads 16-bit PNG as float; values agree to 1/65535) |
| IO: EXR float precision | `test_codecs.Exr.test_roundtrip` (bit-exact incl. NaN/inf), `t_operator_export` (Blender's loader reads the normal EXR identically) |
| IO: ID round trip | `test_export` (PNG16 + EXR UINT), `t_operator_export` |
| IO: colour management | PNG/EXR bytes written directly (no view transform); Blender re-read with `is_data` matches; normal PNG values checked exactly |
| IO: background / orientation | `t_operator_export` (mask re-read by Blender matches capture), harness corner check |
| IO: collisions | `test_export.Names.test_plan_auto_and_none`, `t_operator_export` (exact name refused, file untouched) |
| IO: write permission error | `test_export.Writing.test_unwritable_directory` (real ACL deny via `icacls`), `test_directory_is_a_file` |
| IO: several files failing | same tests (each file reported), `test_batch_partial_failure_reports_each_file` |
| packaging: install / disable / re-enable / uninstall | `tests/blender/package_suite.py` (isolated `BLENDER_USER_RESOURCES`) |
| render comparison (method C) | `tools/benchmark.py` (Cycles depth/normal/ID/mask comparison) |
| precision regression | `t_precision` (5 mm at 100 m, clip 0.01–1000) |
| geometry deviation warnings | `t_deviation_warnings` (no false positive for a default material) |
