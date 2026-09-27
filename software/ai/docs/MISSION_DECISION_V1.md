# Compact mission decision v1

`rocell.mission_decision.v1` is the replacement training target for the small
offline language model. It separates semantic classification from literal
copying and contract assembly.

The model emits one of seven classes:

- execute on keyboard;
- execute on phone;
- clarify device ambiguity;
- clarify payload ambiguity;
- clarify intent ambiguity;
- unsupported shifted keyboard text;
- unsupported phone call.

The decision contains no request ID, observation reference, text, capability,
policy, coordinate, joint, controller, permit, transport, or outcome field.

## Deterministic assembly

`mission_decision.py` binds a valid decision to the original request. For an
execute decision it requires exactly one nonempty double-quoted literal and
one matching device mention outside the quoted data. Known compound-operation
words outside the literal cause an `intent_ambiguous` downgrade. Missing,
multiple, conflicting, or ungrounded fields also downgrade to clarification.

Only deterministic code copies the literal, request ID, and observation
reference and assigns the capability and observation policy. The resulting
object must pass the existing strict `MissionIntentV1` validator before it can
reach the existing read-only compiler.

This deliberately rejects some valid natural language, including currently
unquoted typing payloads. That limitation is explicit and measurable. It
prevents the model from changing literal text or inventing execution bindings,
which were observed failure modes in the v1 and v2 full-object students.

## Authority

This is an offline semantic boundary. It grants no motion, hardware, contact,
permit, transport, or success authority and does not change ModelMotionBatch,
arm runtime, or integration status.

## Development curriculum

The first compact curriculum derives from the frozen balanced
mission-development-v2 records. It contains 1,280 training and 320 validation
examples. All 1,600 compact labels reassemble to their original MissionIntent
targets exactly. The seven class frequencies are recorded with inverse-class
frequency weights so training can balance class mass without duplicating
requests. No confirmation split exists.
