# CI evidence — PR #10 (issue #5), 2026-11-26

Downloaded from the `evidence-*` artifacts of GitHub Actions run
[45835513267](https://github.com/marc2825/ViewPrism/actions/runs/45835513267). Each file is already
sanitised by `tools/run_all_checks.py`, and each run ends with a privacy scan of its own evidence.

| Folder | Runner | Steps | Result |
|---|---|---|---|
| `linux-blender-4.5.17/` | Ubuntu, Xvfb + Mesa llvmpipe OpenGL | pure (82), harness (all), GUI 22/22, build, package | PASS |
| `linux-blender-5.0.1/` | same | same | PASS |
| `linux-blender-5.1.2/` | same | same | PASS |
| `linux-blender-5.2.5/` | same | same | PASS |
| `linux-blender-5.3.0/` | same | same | PASS |
| `windows-blender-4.5.17/` | Windows Server, no GPU | pure (82), harness (background), build | PASS |
| `windows-blender-5.3.0/` | same | same | PASS |

The same run also passed lint, the pure tests on Windows/Ubuntu with Python 3.11 and 3.13, and the
"Secrets and privacy scan" job: the gitleaks canary was detected, gitleaks found no leaks in any ref,
and the repository privacy scan found nothing in the tree or the history (beyond reviewed allowlisted
findings).
