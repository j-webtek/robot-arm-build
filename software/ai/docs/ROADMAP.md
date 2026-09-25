# AI implementation roadmap

The first deliverable is an **offline** English-to-RoCell plan loop. Physical
typing, phone calling, and vision-guided contact depend on separate RoCell
capability and evidence gates. See [the contract](CONTRACT.md).

## Current checkpoint

The v0 proposal and result schemas, read-only compiler adapter, and 28-case
sanity set are in place. The deterministic baseline matches 28/28 on v0 but
only 17/31 on the frozen v1 paraphrase set. A simulated semantic review found
31/31 internally consistent v1 labels; no person reviewed the English labels.
The baseline also makes one false execution proposal for an ungrounded pronoun.
The first local Llama 3.1 8B Q4 candidate also scores 17/31, with
five false execution proposals and one invalid response. Both remain blocked
from arm control. Its installed tag has a translation-oriented default system
prompt and no license or weight lineage in local metadata, so this result is
exploratory rather than an authenticated base-model comparison. Next: acquire
a provenance-verified small student candidate
and collect training examples outside both benchmark paraphrase families.
Before tuning any model or prompt against v1, create a new held-out split so
the final comparison remains meaningful. Require zero false execution
proposals before considering further integration.

| Order | Deliverable | Check before advancing |
| --- | --- | --- |
| 1. Versioned proposal | Define `type_text`, `clarify`, and `unsupported` result shapes; pin the RoCell source/profile identity. | Every supported proposal maps to the existing compiler; no coordinate or hardware command field exists. |
| 2. Frozen benchmark | Simulate review of supported lowercase keyboard/phone requests and unsupported uppercase, dialer, ambiguous, and stale-state requests. Reserve paraphrase families for evaluation. | Hash and labels are fixed before model experiments; record `human_reviewed: false` and label limitations. |
| 3. Deterministic baseline | Parse requests with a simple rule/template baseline and validate supported text using RoCell `plan`/`dry-run`. | Per-case exact text, device, operation, rejection, compiler result, and latency are recorded. |
| 4. Model baselines | Evaluate pinned unmodified teacher/student checkpoints on the same cases. The first locally available Llama 3.1 8B Q4 candidate is recorded. | Compare exact extraction and false execution against the deterministic baseline; no invented targets or false completion. |
| 5. Distillation | Build provenance-marked, checked training data and one reproducible SFT candidate only if baselines show a useful gap. Compare the served artifact against frozen cases. | No held-out leakage; unsupported-task rejection and exact text are preserved. |
| 6. Feedback loop | Integrate a versioned RoCell observation/result adapter when available; train safe continuation and stop behavior. | A sent command or predicted phone state is never scored as actual success. Uncertain effects do not auto-retry. |
| 7. Vision and physical tasks | Incorporate commissioned overhead-camera outputs and supervised input evidence. Extend modifiers and dialer tasks only after RoCell implements their semantic and verification contracts. | RoCell releases each physical capability separately; AI accuracy does not grant motion or contact authority. |

## Immediate work package

The first offline implementation of steps 1–3 starts with `"type test on the keyboard"`
and `"type test. on the phone"`; include `"type Hi!"` and
`"call 555-0102"` as understood but currently unsupported. The broader v1
benchmark is frozen with simulated review. Require zero false execution
proposals before considering any candidate for further integration. Store
only checked examples and manifests in Git. Keep raw captures, private
text, model weights, checkpoints, and run outputs outside the repository.

The hardware team can continue its noncontact and calibration work in parallel.
The AI work does not change RoCell's current physical release state.
