# Contributing

Thanks for helping! The project values correct output over features, so please keep these rules.

## Ground rules

- **Use only Blender's `gpu` module** for drawing (no `bgl`, no raw OpenGL, no private APIs).
- **Never modify the user's scene**: no new datablocks, no settings changes, no undo steps. The GUI
  suite compares a `snapshot()` before and after; extend it if you touch new state.
- **No network access, no pip/wheels, no writing into the add-on directory.**
- Pure modules (`projection`, `encode`, `png`, `exr`, `export`, `writer`) must not import `bpy`.
- UI and tests must go through the same entry point: `viewprism.capture.capture(context, request)`.
- Tests compare against **independent** expectations (analytic geometry or Blender's own functions).
  Never derive expected values from ViewPrism output, never weaken a threshold to make a test pass,
  never turn a failure into a skip. If behaviour changes on purpose, document why in the ADR/CHANGELOG
  and update the test with the new independent expectation.
- `viewpass-dev/harness` is the independent harness from the specification; do not edit it to make
  the product pass.

## Running checks

```
# pure tests (any Python with NumPy; Blender's bundled Python works)
python -m unittest discover -s tests/pure
# GUI/GPU suite (opens Blender windows; needs a desktop session)
python tests/run_blender_tests.py --blender "<blender>" --suite gui [--gpu-backend vulkan|opengl]
# full gate incl. independent harness, build and package lifecycle, with sanitised evidence
python tools/run_all_checks.py --blender "<blender>" [--bench]
```

Report the Blender version, OS, GPU and backend (`gpu.platform`) with any result.

CI runs the same checks on every pull request (lint, pure tests on Windows/Linux, and the full Blender
checks on Linux for 4.5 LTS and 5.3 under Xvfb with Mesa software OpenGL); all jobs are required for
merging into `main`. Lint: `ruff check .` (config in `ruff.toml`).

## Releasing (maintainer)

1. Update `version` in `viewprism/blender_manifest.toml` and `VERSION` in `viewprism/operators.py`,
   and add a `## X.Y.Z — date` section to `CHANGELOG.md`.
2. Merge to `main` through a PR (all checks green).
3. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`. The release workflow validates and builds
   the ZIP with Blender, attaches it with its SHA-256 and publishes the release (pre-release for 0.x).

Please report security issues privately (see `SECURITY.md`), not in public issues.

## Style

- Code, UI text and commit messages in English. Keep functions small and side-effect free where possible.
- Line length ~110. Prefer NumPy vectorisation over Python loops for per-pixel work.
- Do not commit generated files (`dist/`, `__pycache__`), local paths or personal data. Evidence
  folders must be produced by `tools/run_all_checks.py` (it removes local paths).
