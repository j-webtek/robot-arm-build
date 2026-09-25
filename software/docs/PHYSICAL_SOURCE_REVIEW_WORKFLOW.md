# Saved physical workspace-source assessment and review

## Objective and authority boundary

Connect the Camera wizard's original prerequisite document to actual saved V2
stage evidence, assessment, independent review and restart readback. This is
the first canonical physical-stage workflow, not another unsaved notes panel.
Use the existing original `PhysicalCameraSession` and stage-only M1 transaction;
do not create a replacement store or route camera actions through source-only
storage. The active hardware freeze and all received-hardware holds stay intact.

The source contract currently requires disconnected actuator power and HZ-012
qualification evidence. Neither is established by hashing files, inspecting
metadata or checking a consent box. The legacy V1 controller's software-only
PASS predicate must not be copied into V2 as physical acceptance. This initial
workflow can honestly commit a reviewed **BLOCKED** assessment from actual
source facts and missing prerequisites. It must not expose a force-PASS control.
Defining a later physical PASS requires the separately reviewed prerequisite
contracts and evidence, not changing this report's meaning after the fact.

## Intended operator flow

1. Explicitly initialize, or discover/open and verify, the original camera-only
   setup records for the current source. Collect the original build-derived
   prerequisites if the store is new. No device is opened.
2. **Assess saved workspace sources**: confirm file-only assessment and enter
   an operator label. Collect strictly validated controlled source/foundation
   facts, retain exact original prerequisite and session/source references,
   assess missing isolation/ownership/static-release obligations, store the
   bounded receipt and assessment, read them back, then commit
   `workspace_sources: REVIEW_PENDING`.
3. Display software facts separately from missing physical prerequisites. The
   assessment may be successfully produced while its verdict remains BLOCKED.
4. **Review exact workspace-source assessment**: enter a different reviewer
   label and confirm the exact retained receipt/assessment. Store/read back the
   review, then commit the original workspace stage BLOCKED. Labels record a
   procedure; they do not authenticate independent people.
5. Verify the original store after lease exit before publishing its current
   summary. Export the complete workflow to the assigned workspace folder.
   Restart through Discover/Open to recover the original evidence and stage
   without recollection, replay, relabeling origin or changing a verdict.

## Implementation responsibilities

- Pure codec/collector: strict source receipt, deterministic assessment and
  exact-subject review; bounded files/JSON/clock; no OS-device/native/helper
  calls. Use existing strict source/foundation loaders and retained prerequisites.
  Preserve full relevant source facts, fixed missing reasons and all false
  authority flags. Do not fabricate measurements or copy nominal hardware into
  observed fields.
- Original-store reader: extend the existing prerequisite reader with a closed
  role inventory for the prerequisite, receipt, assessment and review. Reject
  duplicate/unknown roles, unexpected stage ownership, invalid hashes, broken
  subject chains and inconsistent stage state. Reuse existing bounded full-store
  audits and stage-only leases; do not weaken trust to accept a new package.
- Setup/service: explicit actions and source/context tickets; append-only
  evidence and earliest-stage transitions; independent review; retain full
  evidence on failures; publish only after source/context, M1 readback and
  completion logging succeed. No automatic retry or repair after an uncertain
  write. Original origin and current app launch remain distinct on reopen.
- UI/export: cached summary and clear missing-prerequisite remediation, with
  exact report hashes and committed stage shown separately. A full workflow
  export survives ordinary diagnostic result rotation. No raw path, payload,
  self-authored authority hash, PASS switch or arbitrary command input.

## Verification

Exercise strict pure contracts and mutation/failure cases with incapable data.
Exercise actual local M1 transactions in isolated temporary stores and a bounded
public physical-mode **file-only** setup workflow. Verify original receipt,
assessment, reviewed BLOCKED commit, result rotation/export, and a second-launch
original-store readback. Check stale tickets, same reviewer, altered reference,
unknown/duplicate role, wrong source/session, Stop, log failure and incomplete
publication. Do not enumerate or open devices or run native helpers.

Success for this increment is durable, reviewed source-stage evidence and
honest restart/export behavior. The overall application goal is not complete:
static-camera contract/receipt/identity qualification, actual camera acquisition
and calibration, arm power/firmware/feedback qualification and separately
authorized motion/contact remain required.

## Developer entry points

- `application/physical_source_stage_evidence.py`: immutable strict receipt,
  deterministic assessment and exact-subject review. Read its [API companion](PHYSICAL_SOURCE_STAGE_EVIDENCE_API.md)
  before extending the software checks or evidence schema.
- `application/physical_camera_session.py`: new
  `read_original_source_workflow` closes the complete inventory to prerequisites,
  receipt, assessment and review. Its old prerequisite-only reader keeps its
  legacy API; the wizard now uses the strict reader. Partial stored evidence
  never implies a committed state.
- `application/physical_camera_setup_service.py`: explicit source-bound actions,
  one-attempt mutation rules, original-session transactions, retained attempt
  diagnostics, post-lease audit and cached publication.
- `application/arrival_wizard_service.py`: action preview/actor mapping,
  completion-log/source/Stop publication boundary and reserved source-workflow
  export. Full documents are flattened only for diagnostic depth, not truncated.
- Browser `ui/static/app.js` and terminal `ui/terminal.py`: optional versioned
  panel preserving older exported views. Status, original actors/launches,
  report hashes and committed stage are checked separately.

The assigned destination is
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
The existing launcher can select another destination explicitly; this task uses
the user's chosen workspace folder. Export files remain local.

## Reproducible file-only integration check

`software/scripts/wizard_workspace_sources_smoke.py` has a closed action set.
Given `--expected-source-sha256 <current inspected fingerprint>`, it creates one
original store, assesses/reviews sources, rotates ordinary results, verifies the
dedicated export, then discovers and reopens the exact original in a second app
launch. It compares original documents and stage state and verifies a second
export. A failure stops without deleting evidence or repeating an uncertain
operation. It never selects inventory, native helper, camera, serial or motion
actions. This is a development check, not the received-hardware procedure.

Verification results are recorded below after the source is frozen. Unit tests
with modeled storage, isolated actual NTFS tests, and the actual public wizard
walkthrough are distinct forms of evidence; none qualifies robot hardware.

### Initial public-storage verification and live-UI finding

On source `129c50e767be3cc0ad6e852ad3f04d260e65999af135d6f60ef10ae8d647d94b`,
the public script completed successfully with actual local M1 storage, nine
ordinary-note rotations, exact original reopening and two verified exports.
Original launch: `wizard-8d51266203294957ae89bd58dda3780b`; second launch:
`wizard-645c43ab8c2c4e2895e5fbb1027f5f29`. The original camera session is
`physical-camera-dd583ce4b4a984a6214de31a6228cd9b`; the review SHA-256 is
`920acfdef8a35b88bed5027e1a66512280d03a7c336bbc8b740403e9c24ec9e8`.

Preserved export folder leaves beneath the assigned destination:

- `wizard-20260908T162549276384Z-71fbe06e33f24c479041ef18314e0894`
- `wizard-20260908T162558337607Z-0052699bacce42e3b115a3d1603c7ba7`

The subsequent actual browser discovery/opening also succeeded, but exposed a
presentation bug that modeled unique-list fixtures missed. The real V2 stage
snapshot appends evidence-reference occurrences across committed events:
receipt+assessment followed by receipt+assessment+review yields **five ordered
occurrences and three unique inventory objects**. Both UI validators incorrectly
required those occurrences to be unique and withheld the otherwise valid panel.
The actual export is only 37,134 compact bytes for this setup projection; it did
not exceed the display size limit. The repair is confined to stage-reference
list presentation, not evidence inventory validation, storage, source codecs or
physical acceptance. The original records were not rewritten or deleted.

This first public-storage result must not be described as a successful live-UI
result. The corrected source and repeated full/browser checks are recorded in
the final verification section below.

Broad selected regression on that initial source: **2,991 passed, eight slow
tests deselected (396.76 seconds)**. The selection covered arrival/wizard,
physical camera/intake/source, owned/native camera and arm-controller tests.
This run preceded the live-UI ordered-reference correction and its new portable
and exact-export reproductions. Do not attribute those later tests to this run.

### Final verification — corrected source

Final source fingerprint:
`fd63cecb4c8e4652e76b841e250da563596679b11c7048e3401901e1383d6c4e`.
Only browser/terminal presentation changed after the preceding broad regression;
source evidence, persistence and acceptance semantics did not change.

- **424 focused tests passed (73.64 seconds)** on final source, covering the new
  codec, strict and legacy original readback, service failures/publication,
  actions, setup/restart and both UI renderers. Included actual isolated NTFS
  tests, real-file collection with processes forbidden, and the retained-export
  regression. The root service fixture now models V2's cumulative occurrences.
- Black checks passed for seven modified production/script files; mypy passed
  for the setup, session, evidence, Arrival and terminal modules; Node syntax
  passed. The narrow UI repair independently passed 219 targeted tests.
- The complete public two-launch script passed again on final source. Original
  launch `wizard-1551f989f4fa4b61ab51828213bd1d11`, original camera session
  `physical-camera-7f0df12c929203df6f3567abcefb3ce8`, second launch
  `wizard-2d55b761bf6c470e87357682b3cab80b`. Exact full prerequisite, receipt,
  assessment and review documents survived restart and nine result rotations.
- Review SHA-256:
  `41536b84e01cad579aee6aacfc497e51141a3f06a1847bbdddc06afd7a609569`.
  The original stage is BLOCKED with five reference occurrences / three unique
  stage-evidence IDs. Four packages exist in the closed inventory when the
  separate prerequisite document is counted. All fourteen later saved stages
  remain PENDING; the overall physical-qualification checklist remains pending.
- Final public export leaves:
  `wizard-20260908T163630272263Z-63308b7f27ce4d2285ef522761f4c2b7` and
  `wizard-20260908T163638462364Z-56dd0f0f710348cb8ac103b888bc0f19`.
  Both verified successfully; full source-workflow attachments are respectively
  119,096 and 117,017 bytes, without truncation or redaction.
- Actual corrected browser launch
  `wizard-409025ab259b4db9843d272b8d023dae` explicitly discovered and reopened
  that same original store. The rendered panel displayed REVIEWED_BLOCKED,
  UNKNOWN power, the three missing physical prerequisites and the exact
  original subjects. Visual inspection passed; browser error/warning log was
  empty. Browser export
  `wizard-20260908T164001710869Z-8f793173738c463b9fc0ea444a27e9be`
  independently verified with manifest digest
  `2499ef3373eb53ad2bd29e01ea9d55c323b152b1f31577e13e5ea5aed62999eb`.
  The temporary browser and server were closed and the listener was absent.
- Offline package build succeeded at
  `software/runs/wizard-package-check-fd63cecb/rocell-0.1.0-py3-none-any.whl`:
  1,900,696 bytes, SHA-256
  `a5d772d3cd53fdd204f3be329008cb8fcc10b0fd76bd637b6f3aecb80e222cd8`.
  All 257 packaged Python/browser assets matched the workspace byte-for-byte,
  including the new evidence module. This is package-content verification,
  not a fresh-machine installation or physical qualification.

No device inventory, native camera helper, serial port, robot power, motion or
contact action was executed in these public workflows. No old records, exports,
active freeze, native executable/build manifest or qualification pin was changed.
Use `start-rocell-wizard.ps1 -Mode physical` for the operator launcher; direct
CLI invocation must include the workspace, for example
`python -m rocell --workspace C:/Users/Jack/Desktop/robot-arm-build physical-onboard wizard --mode physical`.

## Remaining implementation and received-hardware work

This increment is complete; the overall connection application is not complete.
The next implementation needs reviewed stage-specific prerequisite contracts and
their original-evidence adoption, especially static-camera architecture/receipt,
native release qualification, and arm identity/power/feedback stage workflows.
The current version cannot turn this BLOCKED source assessment into PASS.
Real camera acquisition, installed calibration, qualified serial connection and
later constrained motion/contact still require additional software integration
and received-hardware evidence. These features remain disabled; neither these
tests nor the saved review authorizes connecting power or running a typing task.
