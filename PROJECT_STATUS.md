# Project status — 2026-09-25

## Objective

Build a robot that can carry out keyboard and phone tasks on a person's behalf
from a plain-language request to an AI. AI integration is a later phase: the
long-term aim is to train or adapt an AI to translate intent into device actions,
use the arm's verified control interface, observe results, and check task success.

The immediate objective is reliable command-to-motion control for a Waveshare
RoArm-M3, progressing from verified joint movements to ghost-keyboard sequences,
then mounted-stylus typing and Android tapping. Keep requested commands, actual
transmissions, fresh servo feedback, modeled coordinates, and externally measured
accuracy distinct. These tests establish the control and evidence foundation;
they do not yet demonstrate AI-directed operation.

## Current checkpoint

- Hardware designs and assembly instructions are in `active-project/RoCell_v0_3`;
  `RoCell_v0_2` is the frozen prior baseline. Preserve vendor attribution and
  hash-controlled package bytes; do not silently normalize or regenerate them.
- Software includes the onboarding wizard, simulated tests, command/feedback
  diagnostics, native firmware owners, and reviewed export workflows.
- The r91 app was installed and completed the supervised five-leg noncontact
  cycle on 2026-09-25, recovering from the preceding r90 `A_HOVER` endpoint:
  `A_CLEAR → A_HOVER → A_DOWN → A_HOVER → A_CLEAR`.
- Each leg produced a controller record, checked joint feedback, and an
  independently verified export before the next command. The terminal status
  was `REVIEWED_HOVER_COMPLETE|5`. The largest final joint-goal difference
  across those legs was 9 servo counts; this is not measured tip accuracy.
- The r91 plan retains the earlier reservation failure, sequencing correction,
  and successful run as separate evidence. The completed run is historical
  evidence, not a fresh reading of the arm's present pose.
- Keyboard placement has been screened using photo estimates. Those estimates
  are not a measured registration or proof of clearance across the keyboard.
- The stylus loading procedure is prepared but unexecuted. r91 has no general
  gripper-control interface; a verified gripper-only path and mounted-tool
  measurements are still needed.
- Camera mounting/integration and physical stylus contact remain deferred.

The authoritative detail and remaining checklist are in
[the r91 recovery plan](software/docs/R91_HOVER_RECOVERY_AND_A_CYCLE_PLAN.md).
The [reviewed-hover protocol plan](software/docs/REVIEWED_HOVER_RUNTIME_PROTOCOL_PLAN.md)
records the surrounding command and export contracts.

## Next development milestone

Implement and verify the gripper-only loading path, then load and measure the
stylus using the [loading procedure](software/docs/STYLUS_LOADING_PROCEDURE.md).
Use the [photo-estimated keyboard screen](software/docs/PHOTO_ESTIMATED_KEYBOARD_SCREEN.md)
to review placement assumptions before further ghost-typing routes. Keyboard
registration, actual tool geometry, and physical contact accuracy remain open.
No GitHub upload, clone, test run, or merge authorizes deployment or motion.

For other topics, use the [documentation guide](docs/README.md). Detailed
historical plans preserve earlier checkpoints; this page summarizes the latest
recorded result.

## How to read the evidence

Classify each result as **simulated**, **controller-feedback verified**,
**visually observed**, or **externally measured**. Record firmware identity,
configuration identity, test command, pass/fail counts, and an export identifier.
Historical documents may point to local `software/runs/` evidence intentionally
excluded from this repository. A reference is not a downloadable evidence bundle.
Share reviewed, sanitized copies when another developer needs to reproduce an
analysis; retain original private evidence locally.

## GitHub scope

Included: code, documentation, tests, model/configuration contracts, CAD/print
packages, project photos already in the hardware package, and status plans.
CAD/print binary formats use ordinary Git because the account's LFS budget
blocked the initial upload. This is the first Git baseline, not a
reconstruction of historical commits or a complete archive of chat history.

Excluded: device flash backups, credentials/signing keys, raw runs and camera
captures, virtual environments, local toolchains, temporary/build outputs,
duplicate legacy archives, and calibration artifacts. Existing local files are
not deleted. Keep an independent private backup of irreplaceable evidence.
