## What and why

## Checks

- [ ] `python -m unittest discover -s tests/pure` passes
- [ ] GUI/GPU suite passes locally (`python tests/run_blender_tests.py --blender <blender> --suite gui`) — state Blender version, OS, GPU, backend
- [ ] No scene/datablock changes introduced (extend `snapshot()` if new state is touched)
- [ ] Expected values in new tests are independent of ViewPass output; no thresholds weakened
- [ ] `viewpass-dev/harness` unchanged
- [ ] Docs/CHANGELOG updated if behaviour changed
