# Current-pose elbow direction review

## Superseding observation — board contact confirmed

The user explicitly reports **Touching**, with photograph
`C3FF96BD-0ED3-433F-8698-5F5337410D67/1-Photo-1.jpg` showing the lowest gripper
part at the board surface. Treat the present pose as contact-constrained, not
free-space. The hypothetical±6 comparisons below are NOT eligible test proposals.
No hardware action was taken in response to this observation.

This establishes current contact, not its force, how much weight the board
supports, or whether contact existed during every earlier trial. The previous
non-arrival remains valid evidence of that trial, but must not be used as an
unconstrained servo-error or compensation sample without resolving this confound.
Stable counts likewise do not prove active joint support: the latest sample had
only elbow torque enabled. Do not automatically energize passive joints against
their zero goal registers, home the arm, disable elbow torque, reset, or command
an elbow-only sweep while the gripper rests on the board.

Next task is a separately reviewed supported-clearance recovery, not another
accuracy test. Establish a method that supports the links and clears the gripper
without forcing an energized joint; preserve the fixed base. Any powered recovery
must explicitly define joint support, fresh pose/goal capture, safe target
initialization before any enable, and the full-link path. Obtain separate approval
before executing it. Do not instruct unsupported power removal: the arm previously
fell when power was removed. Recapture the resulting clear pose before tests.

### Installed recovery capability review

Inspection of retained r21 source confirms that the existing recovery is an
**elbow goal reconciliation**, not an all-joint supported lift:

- `hold_initialization_owner.h` dispatches `WritePosEx(14,...)`; its optional
  torque-enable path also addresses only14.
- `configured_recovery_board_routes.h` explicitly forces
  `permit_explicit_enable=false`. It does not hold the six passive servos.
- `supported_recovery_board_policy.h` pins the old neighbor windows, which the
  new capture no longer meets. A settings-only widening does not fix lack of
  support or establish a safe contact-release path.
- The pose capture reserves this boot (`rocellPoseReserved`); recovery preparation
  rejects that state. No reset or route bypass is authorized as a workaround.

Consequently, neither the installed recovery nor the ordinary pair runner is a
ready-made way to lift the gripper off the board. Keep the current contact out of
free-space compensation data. The next practical input is whether stable padded
support for the moving links is available. Do not reposition, insert a support
under load, force a joint, or disconnect power merely to answer that question.
If a software-driven full-arm recovery is chosen instead, it is a new reviewed
capability requiring coupled-shoulder handling, fresh per-servo target
initialization, staged enable/readback and load/support validation—not a blind
home command or a generic torque-on operation.

## Purpose and limits

Offline comparison only; no startup, register writes, movement, configuration
change or clearance admission. User confirms the base remained fixed. Photographs
show a folded arm and a gripper near the base/board, but do not establish exact
contact or a measured clearance. The changing camera viewpoint is not motion
evidence. This review must not be used to claim a proven collision-free path.

## Inputs

Replayed stable device capture:
`wizard-20260919T162409109808Z-482d849b3ab548a69c8b9eae7ef59b8f`.
Servo positions11–17:2047,2455,1659,2906,1589,2040,2047.
Only elbow14 reported torque enabled; do not assume the other joints will resist
disturbance during elbow movement. Fresh all-joint checks are required for any
subsequent approved test.

Reference implementation: `src/rocell/arm/joint_mapping.py` and
`src/rocell/kinematics/firmware_reference.py`, pinned source SHA256
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
The locally retained r21 `RoArm-M3_module.h` elbow conversion is
`calculatePosByRad(radInput)+1024`, clamped1024–3071. This confirms the code's
count/angle sign, not installed mechanical orientation or calibration.

Using reference feedback offsets and2*pi/4096 radians/count gives base0.08789°,
shoulder35.77148°, elbow165.41016°, wrist pitch−40.34180°.
Reference FK predicts configured end-edge XYZ approximately
(153.979,0.236,−126.773)mm in R_ctrl. That Z is NOT height above the board:
the equations omit base height and have no registered board transform or stylus.

## Local endpoint sensitivity, not a movement instruction

All other logical joint angles held mathematically constant:

| Hypothetical elbow offset | Target count | Reference ΔX mm | Reference ΔY mm | Reference ΔZ mm |
| --- | ---: | ---: | ---: | ---: |
| −6 counts | 2900 | +2.7742 | +0.0043 | −0.0682 |
| +6 counts | 2912 | −2.7735 | −0.0043 | +0.0937 |

Each offset is0.52734°. These are differences of nominal FK endpoints, not
measured displacement, clearance, or a swept-volume simulation. In this modeled
folded pose, the primary predicted endpoint change is horizontal, not vertical.
Therefore the source comment that increasing elbow angle moves down cannot be
used as a general board-clearance rule.

−6 is worth evaluating as a candidate because it stays inside the existing elbow
window2893–2909 and increases nominal radial reach. +6 exceeds that window.
Neither is admitted: other joints no longer fit their installed windows; full
link/gripper/base/cable clearance is unresolved; the sampled pose is historical.
Do not widen windows or transmit either target from this analysis.

## Next decision

1. Establish whether the lowest gripper/tool part is hanging freely or resting
   against the board/base; a targeted user observation is adequate to distinguish
   these cases. Do not ask the user to touch or force a powered joint.
2. Review the short path and passive-neighbor behavior, not just the end edge.
   If there is contact, do not use a powered test to push through it.
3. If clearance supports a test, prepare an explicit narrowly bounded proposal
   based on fresh start readings. Review required neighbor-window changes and
   their deployment separately; do not treat this document as approval.
4. Verify outward arrival and export before any return. Non-arrival or neighbor
   movement stops the campaign; no automatic compensation, farther target,
   reset, torque change or retry.
