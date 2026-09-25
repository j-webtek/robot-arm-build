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
exploratory rather than an authenticated base-model comparison. The official
Meta Llama 3.2 1B Instruct revision is pinned and evaluated: it scores 0/31
on v1 under the strict JSON proposal contract, with 13 invalid outputs and
no accepted plans.
The 24-case v2 challenge set was frozen before training and consumed once for
the first response-SFT LoRA pilot. That pilot uses 264 synthetic training and
36 validation examples. It scores 14/31 on v1 and 10/24 on v2, but makes five
and one false execution proposals respectively. It is blocked from arm
control. Require zero false execution proposals before considering further
integration.

The next offline step adds a request-grounding gate before compiler admission.
SFT v0 still makes four wrong compiler-accepted plans on the 30-case v3 model
holdout (11/30 exact). The gate accepts seven correct plans and no wrong plans
on v3, while blocking five supported requests. Its v3 result is exploratory:
one policy rule was adjusted after inspecting a v3 request. Model proposal
quality and admitted-plan quality must remain separate measurements.

The v4 challenge was committed before scoring against the unchanged gate. A
transcription error in the manifest's gate hash was corrected afterward;
neither the gate nor cases changed.
The deterministic parser reaches 13/30 exact with one false execution; SFT
v0 reaches 10/30 exact with six false executions. The gate admits six correct
plans, no wrong plans, and rejects six supported requests. This supports
continued offline gate development, while the model remains blocked from arm
control. The next cycle should improve ambiguous-intent rejection and valid
request coverage, then freeze a new challenge before another evaluation.

| Order | Deliverable | Check before advancing |
| --- | --- | --- |
| 1. Versioned proposal | Define `type_text`, `clarify`, and `unsupported` result shapes; pin the RoCell source/profile identity. | Every supported proposal maps to the existing compiler; no coordinate or hardware command field exists. |
| 2. Frozen benchmark | Simulate review of supported lowercase keyboard/phone requests and unsupported uppercase, dialer, ambiguous, and stale-state requests. Reserve paraphrase families for evaluation. | Hash and labels are fixed before model experiments; record `human_reviewed: false` and label limitations. |
| 3. Deterministic baseline | Parse requests with a simple rule/template baseline and validate supported text using RoCell `plan`/`dry-run`. | Per-case exact text, device, operation, rejection, compiler result, and latency are recorded. |
| 4. Model baselines | Evaluate pinned unmodified teacher/student checkpoints on the same cases. The local Llama 3.1 8B Q4 and official Meta Llama 3.2 1B Instruct candidates are recorded. | Compare exact extraction, invalid output, and false execution against the deterministic baseline; no invented targets or false completion. |
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
