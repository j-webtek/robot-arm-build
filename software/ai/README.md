# RoCell AI work area

This folder is the small, reviewable AI addition to the
[`robot-arm-build`](https://github.com/j-webtek/robot-arm-build) repository. It
will translate English requests into RoCell's existing semantic typing plans.
RoCell remains the owner of target geometry, motion, calibration, physical
authorization, controller feedback, and independent input verification.

## Current scope

- **First milestone:** offline intent-to-plan for supported keyboard and phone
  text. Return clarification or `unsupported_by_profile` for requests the
  current semantic profiles cannot compile.
- **Current experiment:** a local small Llama response-SFT adapter trained on
  compiler-checked synthetic labels and evaluated against frozen benchmarks.
- **Future:** feedback-driven planning, physically verified typing, dialer
  workflows, and camera observations as RoCell releases those capabilities.

No file here authorizes arm motion. The current RoCell development runtime has
live hardware and contact disabled. See [project status](../../PROJECT_STATUS.md)
before treating any simulated or controller-feedback result as a physical
typing result.

## Run the offline baseline

From the repository root with Python 3.10 or newer:

```powershell
python software/ai/run_offline.py propose --request 'Type "test" on the keyboard'
python software/ai/run_offline.py inspect --request 'Type "test" on the keyboard'
python software/ai/run_offline.py evaluate
python software/ai/run_offline.py review
python software/ai/run_offline.py evaluate-model --model llama-3.1-8b-instruct-q4_k_m:latest
python software/ai/run_offline.py evaluate-model --model llama32-1b-meta-92131767:latest
python -m unittest discover -s software/ai/tests
```

The `propose` command uses caller-supplied fixture state only. Its phone state
defaults to `UNKNOWN`; pass `--phone-state KEYBOARD_LOWER` only for an offline
case where that state is part of the fixture. These commands do not open an arm
or camera and do not authorize typing. The committed
[baseline scorecard](eval/baseline_v0_scorecard.json) records the first 28-case
sanity benchmark. The [simulated review](eval/simulated_review_v1.json) and
[v1 scorecard](eval/baseline_v1_scorecard.json) cover the frozen 31-case
paraphrase set. No person reviewed the v1 labels; the baseline has one false
execution proposal, so it is not ready for arm control.

The local Llama 3.1 8B Q4 candidate is evaluated with `evaluate-model` using
an explicit task prompt and a pinned Ollama model digest. Its
[v1 scorecard](eval/llama31_8b_q4_v1_scorecard.json) is offline evidence only.
The installed artifact's weight origin and license are unverified; this run
does not authorize hardware execution or model redistribution.

The official Meta Llama 3.2 1B Instruct source revision and imported local
digest are recorded in the [candidate manifest](train/llama32_1b_candidate.json).
Its [offline v1 scorecard](eval/llama32_1b_official_v1_scorecard.json) shows
that the current strict proposal prompt fails on all 31 cases. A separate
[v2 challenge set](eval/benchmark_v2.manifest.json) was frozen before the
first training experiment.

The [first SFT result](train/sft_v0_result.json) scores 14/31 on v1 and 10/24
on v2. It still makes false execution proposals, so it is blocked from arm
control. v2 has been consumed for this pilot; future tuning needs a new
held-out set.

## Folder map

| Path | Purpose |
| --- | --- |
| [`docs/`](docs/README.md) | AI contract, source boundary, and implementation plan |
| [`schemas/`](schemas/README.md) | Versioned English-to-task proposal and result formats |
| [`eval/`](eval/README.md) | Frozen offline cases, scoring, and baseline comparisons |
| [`data/`](data/README.md) | Dataset manifests and provenance-marked examples only |
| [`train/`](train/README.md) | Pinned model and training manifests after baseline evidence |

The existing `software/src/rocell/models/actions.py` and
`software/src/rocell/typing/` are the integration boundary. Do not copy the
older ADB-agent source tree or model artifacts into this folder.
