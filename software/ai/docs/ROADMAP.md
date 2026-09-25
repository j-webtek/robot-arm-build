# AI implementation roadmap

The first deliverable is an **offline** English-to-RoCell plan loop. Physical
typing, phone calling, and vision-guided contact depend on separate RoCell
capability and evidence gates. See [the contract](CONTRACT.md).

## Current checkpoint

The v0 proposal and result schemas, read-only compiler adapter, 28-case
agent-authored sanity set, deterministic scorecard, and focused tests are in
place. The baseline matches 28/28 on that narrow set, with 16 accepted
compiler plans and zero hardware commands. This does not measure general
English robustness. Next: human-review and broaden the held-out benchmark,
then compare unmodified model candidates if they are available. Do not use
the current cases as training examples.

| Order | Deliverable | Check before advancing |
| --- | --- | --- |
| 1. Versioned proposal | Define `type_text`, `clarify`, and `unsupported` result shapes; pin the RoCell source/profile identity. | Every supported proposal maps to the existing compiler; no coordinate or hardware command field exists. |
| 2. Frozen benchmark | Human-review supported lowercase keyboard/phone requests and unsupported uppercase, dialer, ambiguous, and stale-state requests. Reserve paraphrase families for evaluation. | Gold labels are fixed before model experiments; unsupported tasks cannot become executable plans. |
| 3. Deterministic baseline | Parse requests with a simple rule/template baseline and validate supported text using RoCell `plan`/`dry-run`. | Per-case exact text, device, operation, rejection, compiler result, and latency are recorded. |
| 4. Model baselines | Evaluate pinned unmodified teacher/student checkpoints on the same cases. | Improvement opportunity is measured against the deterministic baseline; no invented targets or false completion. |
| 5. Distillation | Build reviewed training data and one reproducible SFT candidate only if baselines show a useful gap. Compare the served artifact against frozen cases. | No held-out leakage; unsupported-task rejection and exact text are preserved. |
| 6. Feedback loop | Integrate a versioned RoCell observation/result adapter when available; train safe continuation and stop behavior. | A sent command or predicted phone state is never scored as actual success. Uncertain effects do not auto-retry. |
| 7. Vision and physical tasks | Incorporate commissioned overhead-camera outputs and supervised input evidence. Extend modifiers and dialer tasks only after RoCell implements their semantic and verification contracts. | RoCell releases each physical capability separately; AI accuracy does not grant motion or contact authority. |

## Immediate work package

The first offline implementation of steps 1–3 starts with `"type test on the keyboard"`
and `"type test. on the phone"`; include `"type Hi!"` and
`"call 555-0102"` as understood but currently unsupported. Freeze a broader,
human-reviewed benchmark and pass thresholds **before** evaluating model candidates.
Store only reviewed examples and manifests in Git. Keep raw captures, private
text, model weights, checkpoints, and run outputs outside the repository.

The hardware team can continue its noncontact and calibration work in parallel.
The AI work does not change RoCell's current physical release state.
