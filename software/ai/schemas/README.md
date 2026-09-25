# Schemas

Version the AI task proposal and adapter result here. A schema must distinguish
`type_text`, `clarify`, and `unsupported`, preserve exact text when supported,
and bind a source observation. The task proposal contains no robot coordinates
or raw controller command. RoCell's existing `ActionPlan` remains authoritative.

The first implementation work package is in [the roadmap](../docs/ROADMAP.md).
The initial proposal shape is [`task_proposal_v0.schema.json`](task_proposal_v0.schema.json).
The read-only compiler inspection response is
[`plan_result_v0.schema.json`](plan_result_v0.schema.json). An accepted result
contains RoCell's own semantic `ActionPlan`; it is not an execution receipt.
The [synthetic visual target schema](visual_targets_v0.schema.json) is a
separate board-coordinate observation contract. It has no motion authority.
The [synthetic image-model prediction schema](visual_targets_v1.schema.json)
binds pixel and checkpoint hashes to predicted keyboard target coordinates;
its model scores are uncalibrated and it also has no motion authority.
The [scene-observation schema](scene_observation_v0.schema.json) binds a strict
multimodal scene assessment to exact image bytes. It describes visibility and
image quality and cannot contain coordinates or controller commands.
The [shadow-preview schema](shadow_preview_v0.schema.json) binds one request,
image, scene observation, precision observation, and guarded preview into a
replayable offline record with zero hardware writes and no permit.
