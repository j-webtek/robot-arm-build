# Model coordinate proposal integration

`rocell.model_motion_proposal.v1` is the supported handoff from a
coordinate-producing model to RoCell's deterministic motion stack.

The proposal is a real planning input, not prose and not a hidden prompt. It is
also not a serial command. RoCell owns frame conversion, target-map comparison,
calibration, inverse kinematics, trajectory smoothness, collision screening,
execution admission, protocol encoding, and transport writes.

## Contract

```json
{
  "schema": "rocell.model_motion_proposal.v1",
  "proposal_id": "keyboard-h-001",
  "device": "keyboard",
  "target_id": "H",
  "coordinate_frame": "keyboard_local",
  "target_mm": {"x": 131.55, "y": 69.0, "z": 0.0},
  "interaction": "HOVER",
  "approach_clearance_mm": 25.0,
  "speed_class": "SLOW",
  "confidence": 0.98,
  "source": {
    "model_id": "candidate-model-v1",
    "frame_id": "frame-001",
    "image_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
}
```

Allowed coordinate frames are:

- `keyboard_local`: X from keyboard left, Y from keyboard front, Z upward from
  the key surface;
- `phone_screen_local`: X from phone left, Y from the USB/device front, Z normal
  to the screen;
- `board`: the RC03 board frame in millimetres.

Version 1 requires a named target as well as coordinates. This gives the
deterministic boundary two independent facts to compare: what the model believes
the target is and where it believes that target lies. A coordinate outside the
named target's safe rectangle fails closed.

`target_mm.z` identifies the device surface, not the hover height. The requested
clearance is carried separately so a planner can generate approach, hover/contact,
and retract waypoints without confusing surface geometry with motion policy.

The complete JSON Schema is
[`model_motion_proposal_v1.schema.json`](../schemas/model_motion_proposal_v1.schema.json).

## Offline bridge

Run the zero-write bridge from the `software` directory:

```powershell
$env:PYTHONPATH = "src"
python -m rocell.application.model_motion_bridge `
  --workspace .. `
  --proposal ai/examples/model_motion_proposal_keyboard_h.json
```

The output binds the proposal and nominal target-map hashes, converts an approved
device-local coordinate into the nominal board frame, checks confidence and the
named target safe region, and emits board-frame planning waypoints.

Current output deliberately contains:

```json
{
  "controller_commands": [],
  "hardware_commands_generated": 0,
  "physical_authority": false
}
```

That is the next integration seam, not a dead end. Once measured device placement,
board-to-controller correlation, and tool geometry are commissioned, the accepted
board-frame candidate can enter deterministic IK, smooth trajectory generation,
full-route screening, exact Waveshare command encoding, and the single-writer
executor.

Generate the machine-checkable translation trace from the repository root:

```powershell
python software/ai/run_offline.py assure-motion-proposal `
  --proposal software/ai/examples/model_motion_proposal_keyboard_h.json `
  --output motion-assurance.json
```

The trace binds the proposal, target catalog, converted candidate, source frame,
and image identity. The current implementation passes proposal validation,
named-target resolution, and coordinate conversion, then blocks at missing
commissioned physical calibration. IK, route screening, admission, encoding,
and verification remain `not_run`, with zero permits, commands, writes, and
retries.

## Training use

The current nominal profiles provide 46 keyboard and 29 phone targets. They are
appropriate seed labels for model training and offline integration tests. They are
marked `SIMULATION_ONLY_NOMINAL_UNMEASURED` and must not be represented as observed
physical truth.

Recommended model supervision preserves:

- device and named target;
- device-local surface coordinate;
- source image/frame identity;
- coordinate uncertainty or confidence;
- interaction mode and requested clearance;
- exact configuration/profile version used to create the label.

A later sequence contract should contain an ordered array of these target proposals
plus transition intent. It should not be implemented by concatenating raw controller
JSON emitted by a model.

## Planner-admission gate

The next deterministic boundary is implemented by
`rocell.application.model_motion_planner_gate`. It binds the accepted coordinate
candidate to the frozen build snapshot, simulation bundle, target catalog,
kinematic model, arm-frame contract, configuration-epoch policy, and complete
device calibration graph. Its output is
`rocell.model_motion_planner_gate.v1`.

The current repository correctly reports
`BLOCKED_CALIBRATION_MISSING_OR_STALE`: the physical calibration registry is
empty. A strict decoder now accepts only hash-matched `VALID` artifacts with
exact payload schemas for robot reference, `B_T_Wv`, separate `R_ctrl`
correlation, measured device pose, and `G_T_T`. After those artifacts exist,
the next gate is reprojecting the model's device-local target through the
measured device transform. The gate executes no IK, route screen, controller
encoding, or hardware write.

Run the zero-write gate from the repository root:

```powershell
$env:PYTHONPATH = "software/src"
python -m rocell.application.model_motion_planner_gate `
  --workspace . `
  --proposal software/ai/examples/model_motion_proposal_keyboard_h.json
```
