# AI-to-RoCell integration contract

**Status:** grounded intent, compiler inspection, scene fusion, and zero-write
shadow preview are implemented; no AI-authorized live arm path exists.
**Source baseline:** pin the exact repository commit in every evaluation or
execution record. Recheck contracts before implementation.

All workers must follow the
[model-to-arm translation assurance process](MODEL_TO_ARM_TRANSLATION_ASSURANCE.md).
It defines ownership, translation invariants, evidence lineage, the minimum
test matrix, and the conditions required before controller encoding.

## Division of work

```text
English request + fresh observation
  -> AI: one compact semantic decision class
  -> deterministic binder: request IDs + exact quoted literal + capability policy
  -> MissionIntentV1
  -> RoCell typing compiler: ActionPlan + plan hash or error
  -> RoCell admission, geometry, controller, observations (when released)
  -> independently verified result or uncertain/failed state
```

The existing [`ActionPlan`](../../src/rocell/models/actions.py) schema is
`rocell.action_plan.v1`. It carries a device, semantic profile, text hash,
actions, required calibrations, and plan hash. Keyboard plans contain
`PressKey`; phone plans contain `TapPhoneTarget` and `VerifyPhoneState`.
A predicted phone `resulting_state` cannot authorize the next tap until
`VerifyPhoneState` confirms it. The
[keyboard](../../src/rocell/typing/keyboard_compiler.py) and
[phone](../../src/rocell/typing/phone_compiler.py) compilers own character-to-
target mapping. The AI does not emit coordinates, joint targets, PWM, dwell,
or arbitrary controller commands through the semantic intent contract.

A separate, image-bound
[`rocell.model_motion_proposal.v1`](../schemas/model_motion_proposal_v1.schema.json)
contract may propose a named target plus coordinates in `keyboard_local`,
`phone_screen_local`, or `board`. This is an internal model-to-planner proposal,
not a user-boundary robot command. Deterministic RoCell code must validate the
frame and confidence, compare the point with the versioned target map, apply
measured transforms, generate and screen the complete trajectory, and issue a
separate permit before a controller command can exist. The model may not emit
joint targets, PWM, protocol JSON, permits, or transport writes.

The offline intent-training target is now
[`rocell.mission_intent.v1`](MISSION_INTENT_V1.md). It binds an execute,
clarify, or unsupported decision to one request and observation reference.
Executable v1 missions carry only `type_text`, one device, exact literal text,
one capability ID, and its required observation policy. A strict adapter binds
the canonical mission hash and delegates to the existing read-only compiler,
producing `rocell.mission_compilation.v1`. The committed capability matrix
keeps phone calling and shifted keyboard typing unavailable and records zero
physical release for every capability. This is an offline dataset and
compilation boundary; `ModelMotionBatch` and physical authority are unchanged.

The current replacement-model target is the narrower
[`rocell.mission_decision.v1`](MISSION_DECISION_V1.md). The model chooses only
one of seven classes: keyboard execute, phone execute, three clarification
reasons, shifted-keyboard unsupported, or phone-call unsupported. It cannot
generate the payload, request binding, capability, or observation policy.
Deterministic code extracts one exact quoted literal from the source request,
grounds the declared device outside the quoted data, rejects known compound
operations, injects the request and observation references, and validates the
assembled `MissionIntentV1`. Failed grounding downgrades to clarification.

## Proposed first request

This is an AI adapter proposal, **not** an existing RoCell schema:

```json
{
  "schema": "rocell.ai_task_proposal.v0",
  "request_id": "example-001",
  "decision": "type_text",
  "device": "keyboard",
  "text": "test",
  "observation_ref": "offline-context-001"
}
```

The adapter checks the source revision, current profile, supported characters,
and capability mode, then returns the RoCell compiler's plan or explicit
rejection. The original requested text stays in a private task record; the
RoCell plan carries its SHA-256 hash. Future execution receipts must keep
requested, transmitted, controller-reported, and independently observed
effects separate.

The experimental [request-grounding gate](../rocell_ai/admission.py) sits
between model proposals and the read-only compiler adapter. It accepts a
single quoted payload only when it matches the proposal exactly, a single
device is explicit outside the quotes, the request asks for typing, the
observation is fresh, and the compiler accepts the text. It rejects listed
extra operations and multi-step phrasing. This narrow grammar can reject valid
English, and its checks do not prove that every possible extra instruction is
detected. It is not connected to the physical runtime.

The [grounded intent path](../rocell_ai/grounded.py) is a separate offline
architecture. It extracts one target device and either one quoted literal
payload or a narrow unquoted single-word payload from the request itself.
It rejects ungrounded pronouns, multiple targets or payloads, negation, extra
operations, and phrasing outside its finite vocabulary. RoCell's compiler
still decides whether the resulting text can be represented. A model may be
used for research on ambiguous intent, but its generated text and device do
not supply the evidence for this path. This prototype has no connection to
camera observations, hardware authorization, or execution.

The older model admission gate remains an offline comparison. On frozen v9 it
admitted a typing proposal from a request that also asked for emailing. This
failure is recorded in the evaluation scorecard; do not route it to a future
execution service as a safety boundary.

## Current capability boundary

The [development profiles](../../src/rocell/typing/development_profiles.py)
support lowercase keyboard text with digits and selected punctuation; the
phone profile supports lowercase text, space, period, and newline from a known
`KEYBOARD_LOWER` state. Shifted uppercase, dialer navigation, calling, and
general phone-app interaction need new RoCell semantic profiles and verified
outcome paths. The AI must identify those intents but return
`unsupported_by_profile` until the corresponding capability exists.

The selected Phase 1 camera is static overhead. Current pixel/pose rehearsals
are synthetic; physical camera registration and contact accuracy remain open.
Any future vision observation must carry frame identity/time, camera and
calibration identity, confidence, and separate controller/device outcome IDs.
Servo feedback alone does not prove that a key or screen target was activated.

RoCell's current [runtime policy](https://github.com/j-webtek/tactevra/blob/bb5d4afa689f1823b949ce769f28c3e9becef712/software/config/runtime.json) defaults to
simulation, disables live hardware and contact, and forbids automatic motion
retry after faults. AI proposals cannot override this policy.
