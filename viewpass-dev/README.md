# Specification and independent verification harness

This folder holds the original product specification and the **independent verification harness**
the add-on was built against (written in Japanese, under the working name "ViewPass"). The harness is
kept unchanged on purpose: it computes its own analytic expectations and must not be adapted to the
implementation. CI runs it for every pull request.

| Path | Content |
|---|---|
| `docs/SPEC.md` | product specification v0.1 (MVP scope, conventions, output contract) |
| `docs/TEST_CONTRACT.md` | contract between the harness and `capture()`, required test areas |
| `docs/MANUAL_QA.md` | manual QA list U01–U14 (results: `../docs/MANUAL_QA_RESULTS.md`) |
| `harness/` | `run.py` (gate), `blender_check.py`, `gpu_cases.py` (analytic GPU cases), `test_runner.py` |

The harness imports `viewpass`. The repository root keeps a tiny `viewpass/` alias that forwards to
the product package `viewprism`. Run it with:

```
python viewpass-dev/harness/run.py --blender "<path>/blender.exe" --mode all
python -m unittest discover -s viewpass-dev/harness -p "test_*.py"
```

The development prompt and research brief that came with this kit were removed from the tree
(they remain in the git history).
