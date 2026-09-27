# Local offline baseline demonstration

Open `software/ai/eval/local_baseline_demo_v0/index.html` in a browser. The committed HTML is self-contained: no server, model download or internet connection is required to view it. It contains six recorded cases and a simulator-truth toggle.

## What the demo shows

- Existing grounded parser and semantic compiler, including exact repeated-key order.
- Actual local KeyboardPoseNet inference on synthetic keyboard images.
- Predicted XY locations beside simulator truth and per-key errors.
- The existing shared v2 shadow runner's decision with `inputs=None`: qualified perception evidence is missing, so no motion batch is assembled.
- Explicit obstruction, stale-observation, ambiguous-intent and unsupported-call examples.

Freshness and obstruction are fixture declarations, not detector predictions. Simulator truth only scores/displays predictions. It is never supplied to admission. The preview runs inference even for blocked examples so users can inspect the scene; those predictions cannot authorize movement. XY is in a synthetic board frame, with no calibrated physical transform or contact Z.

## Regenerate or try another request

From the repository root, with the existing AI Python dependencies and local checkpoint available:

```powershell
python software/ai/rocell_ai/local_baseline_demo.py --output software/ai/results/my-baseline-demo
python software/ai/rocell_ai/local_baseline_demo.py --output software/ai/results/my-request-demo --request 'Type "robot" on the keyboard'
```

Choose a new output directory each time. The optional request adds a case on the first synthetic scene. Open that output's `index.html`. The browser page displays recorded results; it does not run an LLM or new inference interactively.

The required checkpoint is `software/ai/results/translation_weighted_v0_translation_weighted/pose_model.pt`, SHA256 `0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d`. It is ignored in Git; a fresh clone can view the demo but cannot regenerate predictions without those local bytes. Frozen source/checkpoint hashes are checked before generation.

## Recorded cases

| Case | Semantic result | Motion result | Maximum requested-key error |
|---|---|---|---|
| Clear keyboard | Accepted | Perception evidence required | 0.762 mm |
| Lighting variation | Accepted | Perception evidence required | 4.100 mm |
| Arm obstruction | Accepted | Abstain: obstructed | 4.687 mm |
| Stale observation | Blocked | Stale observation | No target plan |
| Ambiguous request | Blocked | Clarification required | No target plan |
| Phone call | Blocked | Unsupported request | No target plan |

These illustrative cases are selected from reused synthetic development, not a new benchmark. No batch, hardware write, physical movement or localization qualification is produced. Phone perception and physical execution are not demonstrated.

## Verification

`python -m pytest -q software/ai/tests/test_local_baseline_demo.py`

Tests cover repeated-key order, unsupported/stale decisions, embedded-JSON script escaping, artifact hashes, image binding, coordinate error calculations and the missing-evidence path stopping before assembly. Browser review confirmed case selection, populated target tables and the simulator-truth toggle.
