# Project status — GitHub baseline, 2026-09-25

## Objective

Build a reliable command-to-motion interface for a Waveshare RoArm-M3, progressing
from verified joint movements to ghost-keyboard sequences, then mounted-stylus
typing and Android tapping. Keep requested commands, actual transmissions, fresh
servo feedback, modeled coordinates, and externally measured accuracy distinct.

## Current checkpoint

- Hardware designs and assembly instructions are in `active-project/RoCell_v0_3`;
  `RoCell_v0_2` is the frozen prior baseline. Preserve vendor attribution and
  hash-controlled package bytes; do not silently normalize or regenerate them.
- Software includes the onboarding wizard, simulated tests, command/feedback
  diagnostics, native firmware owners, and reviewed export workflows.
- The recorded r90 physical first leg reached `A_HOVER` from `A_CLEAR` with a
  verified seven-servo export. This is endpoint feedback evidence, not measured
  stylus accuracy or proof of an entire typing sequence.
- The previous host did not persist its exact authentication sequence. Do not
  guess that sequence or resume the consumed boot. Resetting alone does not
  satisfy r90's required `A_CLEAR` source when the arm is at `A_HOVER`.
- r91 recovery work is **offline**, not installed or physically verified. The
  fixed recipe, native policy/owner/signed route, authenticated client checks,
  and independent raw-record verifier are implemented. The plan records the
  related 219-test checkpoint and later diagnostic additions separately.
- Camera mounting/integration and physical stylus contact remain deferred.

The authoritative detail and remaining checklist are in
[the r91 recovery plan](software/docs/R91_HOVER_RECOVERY_AND_A_CYCLE_PLAN.md).
The [reviewed-hover protocol plan](software/docs/REVIEWED_HOVER_RUNTIME_PROTOCOL_PLAN.md)
records the surrounding command and export contracts.

## Next development milestone

Complete the five-leg host/export runner and failure exports; compose and review
the candidate image; then carry out the separately authorized bounded physical
campaign. Proposed path: `A_HOVER → A_CLEAR → A_HOVER → A_DOWN → A_HOVER → A_CLEAR`.
No GitHub upload, clone, test run, or merge authorizes deployment or motion.

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
