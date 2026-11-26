# QA report — 2026-11-26 (issue #5)

What was verified, where, with which evidence, and what is **not** verified. Support claims in the
README and the extension listing must not go beyond this page.

Automated gates count only real results: exit code 0 **and** a result JSON with `status == "pass"`.
Timeouts, missing results and skips are failures; "NOT TESTED" is never reported as PASS.

## 1. Environments

| # | Blender | OS | GPU / backend | Where | Pure | Harness | GUI suite | Build | Package | Stress |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 5.3.0 | Windows 11 Pro 26200 | RTX 3060 Ti (driver 610.88), **Vulkan** | local | 82 PASS | bg + GPU PASS | 22/22 PASS | PASS | PASS | PASS |
| L2 | 5.3.0 | Windows 11 Pro 26200 | RTX 3060 Ti, **OpenGL 4.6** | local | (same) | bg + GPU PASS | 22/22 PASS | — | — | PASS |
| C1 | **4.5.17 LTS** | Ubuntu (GitHub runner) | Mesa llvmpipe OpenGL 4.5 (software) | CI | PASS | bg + GPU PASS | PASS | PASS | PASS | — |
| C2 | 5.0.1 | Ubuntu | Mesa llvmpipe | CI | PASS | bg + GPU PASS | PASS | PASS | PASS | — |
| C3 | 5.1.2 | Ubuntu | Mesa llvmpipe | CI | PASS | bg + GPU PASS | PASS | PASS | PASS | — |
| C4 | 5.2.5 | Ubuntu | Mesa llvmpipe | CI | PASS | bg + GPU PASS | PASS | PASS | PASS | — |
| C5 | 5.3.0 | Ubuntu | Mesa llvmpipe | CI | PASS | bg + GPU PASS | PASS | PASS | PASS | — |
| C6 | **4.5.17 LTS** | Windows Server (GitHub runner) | none (background mode) | CI | PASS | **bg only** | NOT RUN (no GPU) | PASS | — | — |
| C7 | 5.3.0 | Windows Server (GitHub runner) | none (background mode) | CI | PASS | **bg only** | NOT RUN (no GPU) | PASS | — | — |
| — | Python 3.11 / 3.13 (NumPy from PyPI) | Windows + Ubuntu | — | CI | PASS | self-test PASS | — | — | — | — |

The CI rows are re-run on every pull request and on `main`; the exact counts of each run are in its
job summary and evidence artifact (section 6).

### Not tested (no hardware / no runner available)

| Configuration | Status | Closest coverage |
|---|---|---|
| Windows + Blender 4.5 LTS **with a GPU** | **NOT TESTED** | C6 (background), C1 (4.5 with a GPU on Linux) |
| macOS / **Metal** (Apple Silicon or Intel) | **NOT TESTED** | manual `macOS probe` workflow: background checks only, informational |
| **AMD** GPUs (any OS) | **NOT TESTED** | — |
| **Intel** GPUs (any OS) | **NOT TESTED** | — |
| Linux with hardware drivers (NVIDIA/AMD/Intel) | **NOT TESTED** | C1–C5 use Mesa llvmpipe (software rasteriser) |
| Blender < 4.5 | not supported | `blender_version_min = "4.5.0"` |

Tracking: issue #9 (anyone with that hardware can run `tools/run_all_checks.py` and `tools/stress.py`
and attach the sanitised `SUMMARY.md` / `stress.json`).

### Minimum version (reassessed)

`blender_version_min` stays **4.5.0**. 4.5.17 LTS passes every gate with a GPU on Linux and the
background gates on Windows. The 4.5-specific code paths (flat readback buffers, no framebuffer reuse
across window contexts, feature-guarded `filter_mode`) are exercised by C1 and C6. Older versions are
not tested and the extension platform requires 4.2+ anyway; there is no evidence that would justify
lowering the minimum.

## 2. Reproduce

```
# everything that the machine supports (stores sanitised evidence, ends with a privacy scan)
python tools/run_all_checks.py --blender <blender> --backends vulkan,opengl --out <dir>
# no GPU / no display (e.g. Windows CI):
python tools/run_all_checks.py --blender <blender> --backends opengl --harness-mode background \
    --steps pure,selftest,harness,build --out <dir>
# resources: 1080p/4K/8K, repeated 4K, 40 000 instances, preview timing, GPU failure injection
python tools/stress.py --blender <blender> --gpu-backend vulkan --out <dir>
```

## 3. Results by area

### Correctness (unchanged gates, independent harness untouched)

- Independent harness (`viewpass-dev/harness`, not modified): background registration and the GPU
  analytic cases pass in L1, L2, C1–C5; background in C6–C7.
- GUI/GPU suite (22 cases): projection matrices from real viewports, camera view, visibility, instances,
  modifiers, precision, multi-area/multi-window, view lost, operator export with re-reading by Blender,
  preview lifecycle, **preview debounce** (new), **resource guard** (new), fault injection, re-register.
- Package lifecycle: install → enable → export → disable → uninstall in an isolated user directory.

### Resources (details and numbers: `docs/PERFORMANCE.md`)

- 8K (33.2 MP) capture + export of all passes in a 3.4 M-triangle / 40 000-instance scene: Vulkan
  2.0 s + 3.2 s, process peak +3.7 GB; OpenGL 1.5 s + 2.9 s, +3.0 GB. No failed files.
- Repeated 4K captures with and without redraws: no memory growth.
- Injected GPU allocation failure → explicit error ("try a lower resolution"); next capture succeeds.
- Memory guard: refuses above 90 % of committable memory, warns above 80 % of free RAM (pure tests +
  GUI `t_resource_guard`). The 33.5 MP limit alone is not treated as a memory guarantee.
- Auto preview: no capture while the view or scene keeps changing; one refresh after stillness
  (`t_preview_debounce` fails on the previous implementation: 8 captures during 2.5 s of navigation).

### Supply chain and secrets (CI)

| Measure | Where |
|---|---|
| Actions pinned to full commit SHAs (version in a comment), Dependabot for Actions + pip | `.github/workflows/*.yml`, `.github/dependabot.yml` |
| Python tools installed with `--require-hashes`, one directory per tool / Python version (NumPy 2.5 dropped Python 3.11, so 3.11 stays on 2.4.x; Dependabot is told the Python version and ignores NumPy >= 2.5 there) | `ci/lint/`, `ci/pure/` (Python 3.13), `ci/pure-py311/` |
| `persist-credentials: false` on every checkout; default token read-only | all workflows |
| Release: build job read-only; publish job (`contents: write`) runs no repository code and re-verifies the checksums; manual runs are dry runs | `.github/workflows/release.yml` |
| Blender download: archive cached, official checksum list fetched fresh each run, archive re-verified before extraction, mismatching cache deleted | `.github/scripts/fetch_blender.sh` |
| gitleaks 8.30.1 (tarball SHA-256 pinned) over all refs, values redacted | CI job "Secrets and privacy scan" |
| Negative fixture: a random canary committed to a throw-away repository must be reported by gitleaks (custom rule in `.gitleaks.toml`) | same job |
| Repository privacy scan of the tree and of every reachable blob: e-mail addresses (any provider), Windows/macOS/Linux/WSL user paths, GitHub/AWS/Google/Slack tokens, private keys, credential assignments, PNG text/EXIF/time chunks; values masked in output | `tools/privacy_scan.py`, reviewed history findings in `tools/privacy_allowlist.txt` |
| Synthetic negative fixtures for the privacy scan and the evidence sanitiser (assembled at runtime, nothing matchable stored) | `tests/pure/test_privacy_scan.py` |
| Evidence and ZIP: evidence files are sanitised (home directory incl. Windows 8.3 short form, user name) and scanned before a run can pass; the extension ZIP is scanned by `tools/build_extension.py` | `tools/run_all_checks.py`, `tools/build_extension.py` |
| Screenshots: `tools/screenshots.py` strips PNG text/EXIF/time chunks; the scan rejects new ones | `docs/images/`, `branding/` |
| GitHub: secret scanning + push protection enabled; Dependabot security updates enabled | repository settings |

The PR that introduced these checks ran them on itself. On its first run, the evidence scan caught a
real gap: the Windows runner's 8.3 short home path was not being sanitised. That gap is fixed.

Not available: GitHub's *non-provider patterns* and *validity checks* for secret scanning could not
be enabled through the API for this personal repository (they stay disabled). gitleaks and the
repository scan cover generic patterns instead.

### Manual QA

No human has done the hands-on pass yet. `docs/MANUAL_QA_RESULTS.md` separates AUTOMATED evidence
from what a person must still check: the real file browser (save/cancel), the visual preview check,
external readers (GIMP/Krita/Nuke/ComfyUI), and multi-view use in a real project. **Blocker:** issue #9.

## 4. Known limitations found by this QA

- `collect` costs ≈ 6 µs per instance in Python (0.25 s for 40 000 instances); 100 000+ instances
  take about a second per capture, and auto preview waits accordingly.
- During continuous depsgraph updates (for example animation playback) the auto preview does not
  refresh until playback stops. This is by design: it never blocks the UI while things change.
- GPU memory cannot be queried from Blender's Python API; GPU exhaustion is reported as an error, not
  prevented.

## 5. Decisions left to the owner

- Hands-on QA (issue #9) before a non-pre-release.
- Hardware coverage (issue #9) before claiming macOS/AMD/Intel support.

## 6. Evidence index

| Evidence | Content |
|---|---|
| [`evidence/2026-11-26/`](evidence/2026-11-26/SUMMARY.md) | L1 + L2 full run (sanitised logs/JSON) |
| [`evidence/2026-11-26-stress/`](evidence/2026-11-26-stress/) | L1 + L2 stress results |
| [`evidence/ci-2026-11-26/`](evidence/ci-2026-11-26/) | C1–C7 job evidence of the PR that closed issue #5 |
| CI artifacts `evidence-*` (30 days) | every later CI run |
