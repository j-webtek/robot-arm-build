# Mission intent v1

`rocell.mission_intent.v1` is the stable structured target for offline intent
models. It sits above RoCell's existing semantic `ActionPlan` compiler. It
contains no coordinates, joints, motion timing, controller protocol, permits,
or success claims.

## Supported executable shape

The first executable operation is `type_text`:

```json
{
  "schema": "rocell.mission_intent.v1",
  "request_id": "request-001",
  "observation_ref": "frame-001",
  "decision": "execute",
  "operation": "type_text",
  "device": "keyboard",
  "arguments": {"text": "robot"},
  "required_capability": "keyboard.typing.lowercase",
  "observation_policy": "verify_after_each_action"
}
```

The compiler-backed adapter produces a hash-bound
`rocell.mission_compilation.v1`. For this example, the contained ActionPlan has
the exact ordered named-key sequence `R`, `O`, `B`, `O`, `T`. Coordinates are
resolved later from fresh perception evidence and a versioned target catalog.

Phone lowercase typing requires capability `phone.typing.lowercase`, policy
`verify_after_each_state_change`, and an independently supplied fresh
`KEYBOARD_LOWER` observation. The existing phone compiler inserts the required
state verification action before taps.

## Clarification and unavailable operations

An ambiguous request produces `decision: clarify` with one bounded reason.
Recognized operations without an offline semantic compiler produce
`decision: unsupported`, including `phone.dialer.call`. They create no
ActionPlan. This lets a model demonstrate that it understood “call this
number” without implying that dialer navigation, number entry, call
initiation, or outcome verification is available.

The committed capability matrix is
`software/ai/capabilities/mission_capabilities_v1.json`. It binds every
capability to its operation, device, observation policy, optional required
device state, and semantic profile. Every current entry explicitly records
`physical_runtime_released: false`.

## Model-training use

Training examples should map a user request and observation reference to one
exact mission object. A constrained decoder should use the JSON schema. The
runtime validator remains authoritative and rejects:

- duplicate or unknown fields;
- changed or empty literal text;
- operation, device, capability, or observation-policy mismatches;
- executable use of a capability without an offline compiler;
- joint, PWM, serial, controller, permit, or transport fields.

After validation, the adapter delegates to the existing read-only compiler.
The compiler determines character support and action order. The resulting
mission hash and ActionPlan hash remain distinct, making both the interpreted
request and deterministic semantic expansion independently traceable.

## Current authority

This boundary supports offline compilation and dataset construction. It does
not emit `ModelMotionBatch`, install a capability, authorize contact, access
hardware, or change arm/runtime status. A later dataset increment must freeze
compiler-checked positive, clarification, unsupported, adversarial, and
family-held-out examples before training the next student.

That first curriculum is now committed as `mission_curriculum_v1`. It contains
208 training, 80 validation, and 80 heldout cases with disjoint template-family
IDs. Each validation and heldout category has eight cases. Stale and unverified
state cases retain the correct semantic execute intent while the compiler
result blocks before an ActionPlan; ambiguous and unavailable targets produce
no plan. The heldout split is consumed only by a separately frozen evaluation.

## First mission student result

The frozen `mission_student_v1` study fitted one LoRA adapter on the pinned
Llama 3.2 1B Instruct base. Training used 208 records, checkpoint selection
used validation token loss only, and the selected third epoch reduced that
loss to `0.0535534`. The training process did not read heldout.

The selected adapter then ran once on all 80 untouched heldout cases through
Ollama 0.34.0 with the frozen JSON Schema decoder. It did not qualify: 23/80
outputs were exact, 74/80 were valid, and 7/23 expected executable cases were
accepted correctly. Six outputs were invalid. The candidate produced zero
wrong accepted operations and zero changed literal payloads, so the main
failure is conservative over-abstention and poor category transfer rather
than unsafe accepted substitutions.

This result is a failed offline candidate. It does not install a runtime model
or change any capability, motion, hardware, or integration status. The
heldout examples cannot be used to tune a replacement. A successor needs a
new preregistered development curriculum that improves ambiguity-reason
separation, keyboard execution, quoted literals, stale-state semantics, and
unavailable-operation classification before evaluation on a new confirmation
population.

The successor development curriculum is `mission_development_v2`. It contains
1,280 training and 320 validation records, balanced equally across all ten
mission categories. Training and validation use disjoint template families.
It was designed from the aggregate v1 category metrics and does not load the
consumed v1 heldout cases or predictions. It contains no confirmation split.
A confirmation generator must be authored and frozen only after the successor
model, prompt, decoder, selection rule, and promotion gates are fixed.

The frozen v2 fit produced two development checkpoints. Neither passed the
development gates. Epoch 2 reached 42.5% exact output but produced 22 wrong
accepted operations and two changed literals. Epoch 1 reached 19.7% exact
output with ten wrong accepted operations and no changed literals. The frozen
safety-first selector chose epoch 1 as the less unsafe candidate and marked it
unqualified. Because development gates failed, no confirmation generator or
confirmation data was created.
