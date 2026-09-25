# R20 observed pose: next movement proposal

## Current blocker — confirmed gripper/board contact

User confirms **Touching**, supported by the latest photograph. The next action
is a supported-clearance recovery review, not the hypothetical±6 elbow test.
See [contact finding and recovery requirements](CURRENT_POSE_DIRECTION_REVIEW_20260919.md#superseding-observation--board-contact-confirmed).
Do not use contact-constrained trials to fit free-space compensation. Contact is
confirmed now, not proven as the sole cause of previous non-arrival. No movement,
reset, torque change or settings change was authorized by this observation.

## Latest checkpoint — approved fresh capture completed

Offline [current-pose direction review](CURRENT_POSE_DIRECTION_REVIEW_20260919.md)
compares reference FK sensitivity for±6 elbow counts. It predicts primarily
horizontal endpoint displacement in this folded pose, not a simple up/down
motion. This is neither measured clearance nor movement approval. The next
targeted observation is whether the lowest gripper part is freely suspended or
touching the board/base; no new photographs or exact measurement is required.

User clarification: **the base is fixed and did not move**. Do not infer motion
from the photos' different viewpoints. Preserve any previously established
base-to-board registration; no new measured transform is established by this
statement. Joint-count changes below are controller evidence, not photo-derived
measurements, and their cause remains unresolved. Historical exports retain their
then-unknown base-placement label; this clarification supersedes that uncertainty
without rewriting original diagnostic evidence.

Wizard integration: the Arm action **Review repositioned pose against installed
settings (offline)** accepts the pose, settings-stage and installation export
folder names below. It replays the same receipts and shows the comparison in its
diagnostic result; **Export logs** retains that result. It does not connect,
register a current physical pose, grant clearance or enable motion. Preview,
worker dispatch and verified result export were tested in both physical and
rehearsal modes;56 focused tests passed. The actual saved receipts were also
reviewed through the worker, with zero motion commands. This is a review action,
not yet the full pose-registration/clearance workflow.

Offline compatibility follow-up:
`wizard-20260919T162655173375Z-7cc6372b950149cfba685b5a191318d0`.
`pose_policy_review.py` replays the device capture and installed-settings receipt
chain before exporting a reproducible comparison. IDs12,13,15,17 are outside
their installed narrow admission windows by30,28,444,5 counts respectively.
Reusing the +10 offset at elbow2906 would imply2916, beyond installed upper2909.
These are software-policy mismatches, not evidence of mechanical end stops.
No settings were changed and no target was sent. Establish clearance and prepare
a new bounded scope rather than making the current arm fit the old targets.

2026-09-19: one startup followed by one three-snapshot read-only capture completed.
No hold, recovery, motion, configuration write or retry. Historical blocked-owner
notes below describe the previous boot and are superseded by this checkpoint.

- Startup execution: `wizard-20260919T162331393517Z-e0bf394f3412448fac2259bca4d8f648`.
- Idle startup observation: `wizard-20260919T162358926320Z-a4a9533f866445209d1d40a64d9d89de`.
- New boot: `4391736215673ff84122c24fc6287d91`.
- Capture: `wizard-20260919T162409169501Z-69ec595e941b48059021d98083cfec58`.
- Assessment: `wizard-20260919T162409109808Z-482d849b3ab548a69c8b9eae7ef59b8f`.
- Independent absolute-path replay verified `STABLE_SAMPLED_POSE`; raw bundle SHA256
  `fa1227238fb4bb87e5c5ebb3f50c7b9598e904d21399a3f544ecdd292c1edc18`.

| Servo ID | Fresh position | Goal register | Torque | Change from previous trial |
| --- | ---: | ---: | ---: | ---: |
| 11 | 2047 | 0 | 0 | 0 |
| 12 | 2455 | 0 | 0 | -32 |
| 13 | 1659 | 0 | 0 | +30 |
| 14 | 2906 | 2907 | 1 | +9 |
| 15 | 1589 | 0 | 0 | -446 |
| 16 | 2040 | 0 | 0 | -1 |
| 17 | 2047 | 0 | 0 | -8 |

All values are raw counts. Each position span was0, every mode was0, and all
moving flags were0 across three scans. Acquisition intervals in controller
microseconds:35627458–35640229,35742195–35754536,35855195–35867587; total240129us.
Read validation passed. This proves sampled stability only, not ongoing support,
physical clearance or Cartesian accuracy. Torque-off joints' goal0 must not be
used as a commanded destination. No torque state was changed by this workflow.

The elbow now lies1 count below its retained goal, but this is not a successful
replay of the earlier failed trial: startup and an unobserved interval intervene,
and no continuous record establishes when or why it changed. Several other
positions also differ materially. Old windows therefore cannot admit a new hold.
The user confirms base placement is unchanged. Next is current-clearance assessment
and a new bounded proposal, not automatic movement or automatic policy widening.

The startup helper was tested with changed boot, active status, storage fault,
unexpected hold state and changed record count rejection.23 focused tests passed
before live execution. The existing recovery-gated restart script was not reused
or weakened; this startup has its own one-use receipt and no servo-write path.

## Reposition invalidation — 2026-09-19

An earlier user message was interpreted as manually moving the arm away; this
interpretation is not proof of manual joint movement. The user requests commands based on its
current position, with consideration of physical travel/clearance. All previous
pose observations, illustrative targets and clearance assumptions are now
historical only. Do not reuse2897/2907 or automatically return to any old anchor.
Determine whether this changed joint angles, base placement on the board, or
both. Fresh servo readings establish joint state, not base-to-board registration.
If base placement changed or is uncertain, invalidate that transform as well.
The active goal and completion gates are maintained in
[the command-to-servo plan](COMMAND_TO_SERVO_DIAGNOSTICS_PLAN.md#active-priority--re-establish-pose-and-clearance-after-repositioning).

Read-only status export
`wizard-20260919T161019606194Z-3160d9769ec14c7281fb94959c4f3180`
confirms the same boot `0b0e6cbe9e70093fb7be20fe6e117814`, hold
FAULT/HOLD_HANDED_OFF and pair STOPPED/LEG_NOT_ARRIVED with23 retained records.
These are old trial records, not new joint readings. No servo command or reset
was sent. Installed r21 `rocellReservePose` rejects a new pose scan after a hold
is configured or pair phase leaves New, including this stopped phase. Do not
invoke a known-ineligible scan or relabel old feedback as current.

Next scope requested: one startup and one three-snapshot read-only pose capture,
with no hold, movement or settings changes. Startup may have physical effects;
do not assume it is motion-free. After fresh position/goal/torque readings and
stability review, register the new pose explicitly. Any installed policy change
requires separate review/approval; no automatic widening of the old windows.

Before choosing another movement, combine the new joint state with current
physical clearance: board, base, adjacent links, cables and tool. Encoder bounds
are not collision limits, and an endpoint inside those bounds does not prove a
clear swept path. Choose only a bounded direction shown to move away from nearby
constraints; do not infer that direction from raw count sign alone. Stop on
non-arrival or rising effort without displacement rather than commanding farther.

Status: r21 and reviewed observed-pose settings installed; recovery and ordinary
holds verified. The +10 outbound trial failed arrival; return was withheld.
Current configuration/gains were subsequently read and matched earlier values.
No movement authorized by this document. Preserve the original policy and evidence.

## Capture launcher readiness — offline update 2026-09-19

`scripts/run_pose_observation.py` now accepts paired `--stage-export` and
`--installation-export` arguments to verify r21 observed-pose settings together
with `--startup-export`. Omitting both retains the original r20 receipt path.
The launcher rejects consumed pose captures and local hold/recovery/pair claims,
then requires fresh same-boot idle status before a single acquisition request.
Preflight is offline and does not establish current pose or authorize startup.
No reset, hold, recovery or motion command is included in this launcher.

Validation covers r20/r21 binding, offline preflight, missing/mismatched receipt
handling, consumed capture and actuation claims, non-idle rejection, acquisition
and sequence assessment. The current used boot remains unsuitable; use a new
verified startup receipt only after separately approved startup. Do not reuse the
historical idle receipt to claim that the device is idle now.

## Current checkpoint — +10 outbound verified non-arrival; return withheld

Further offline comparison: [direction evidence and next decision](ELBOW_DIRECTION_COMPARISON_20260919.md).
The earlier -6 leg replayed as arrival (2903 to2897), with changing position and
negative speed; its feedback review was exported separately. Historical
configuration and gain receipts were re-opened with manifest verification.
This narrows the issue beyond general command delivery but does not establish
a tuning/mechanical cause. The comparison is confounded by pose, firmware and
amplitude differences. No hardware was accessed or compensation applied.

Offline feedback review of the immutable forward export completed using
`software/scripts/review_pair_feedback.py`. It replays the source evidence before
decoding the pinned reference block, retains command-relative acquisition times,
and exports its summary plus samples. Receipt:
`wizard-20260919T154934892332Z-20bb7629b0d4452b99d27b825d4fa403`.
All values below are RAW_REFERENCE, not calibrated engineering units:

| Field | Before (3 samples) | After (18 samples) |
| --- | --- | --- |
| Position | 2897 | 2897 |
| Speed | 0 | 0 |
| Load | -13 | -85 to -57 |
| Current | 0 to 1 | 2 to 4 |
| Voltage | 121 | 121 |
| Temperature | 29 | 29 to 35 |
| Moving flag | 0 | 0 to 1 |

Interpretation: dynamic effort/status fields changed after the accepted goal
while measured position did not. This weakens the simple ignored-command or
wholly frozen-feedback explanation; it does not exclude a position-specific
feedback problem or prove actual motor displacement. Do not infer physical
current, force, stall thresholds or temperature without verified scaling.
Do not increase repeated effort/amplitude automatically. Next review retained
mode/deadband/gain/limit evidence and compare earlier successful-direction traces;
use that evidence to choose a bounded experiment rather than fit compensation
to a non-moving endpoint. No new controller access occurred for this review.

2026-09-19: executed the explicitly approved one +10/return trial. It stopped
after the outbound leg; **no return, retry, reset or subsequent movement**.
Boot `0b0e6cbe9e70093fb7be20fe6e117814` now has a consumed pair reservation.

- Admission: `wizard-20260919T154702533833Z-3710cda1badd41939ee20b09a2d4dd8e`.
- Delivery: `wizard-20260919T154703665304Z-2cefe24eec14414ab5c48a1be86fada7`.
- Outbound observation: `wizard-20260919T154710417443Z-d47c57ebbdda4ebeb7c1493b5d14da9a`.
- Final trial: `wizard-20260919T154710616339Z-fcfa5abf4fd74620ac39ab5a580cb92f`.

Independent local replay returned `CONTROLLER_REPORTED_NON_ARRIVAL`, not
inconclusive feedback. Requested target2907, library-encoded target2907 and
first/settled goal readback2907 agree. Measured start and final position both2897;
signed error-10, zero measured displacement across21 snapshots. Last observation
was2033523us after command. Historical anchor matched. Controller STOPPED with
LEG_NOT_ARRIVED; storage_fault=false. Host trial reason FORWARD_ENDPOINT_NOT_ELIGIBLE.

The retained action reports one servo14 write at41, width7, payload
`015b0b00001400`, enabled ACK, library_return1/device_error0/dispatch SUCCEEDED.
This is pinned-library encoding and controller-reported ACK evidence, not an
independent wire trace. Elbow torque readback remained1. All seven positions
were constant during the sampled trial; neighboring goal/torque values also
remained unchanged. Sampled positions11..17:2047,2487,1629,2897,2035,2041,2055.

Conclusion: the new trial demonstrates delivery/goal-register acceptance without
measured displacement under these settings. It does not establish backlash,
deadband, load, motor drive or encoder behavior as the cause. Do not fit a
compensation offset or claim successful reverse motion from this result.
Next investigate saved control/feedback evidence and compatible read-only
diagnostics. Any fresh movement or recovery needs a new explicit scope; never
return automatically now that outbound arrival failed. Earlier test-pending
statements below describe historical checkpoints.

## Current checkpoint — approved startup and ordinary hold completed

Offline pair preparation now completed from that verified ordinary hold:
`wizard-20260919T153051290977Z-35b3c7fa34f24015ae9989d47d016098`.
Preparation SHA-256
`b44f4b8dca6244ee9d588362c9354b07981b58109366294bd47955b0f42841c7`.
Replay and local preflight passed with no device access, key extraction or trial
reservation. Historical measured anchor2897 gives illustrative forward2907 and
return2897, inside the unchanged2893–2909 envelope. Offset10, tolerance2,
speed20 and acceleration1 remain pinned. Fresh native admission must confirm
the actual anchor before any command. Execution awaits explicit one-pair
approval; return only after verified outbound arrival and export, no retry,
recovery, reset or subsequent sequence.

2026-09-19: completed one separately approved startup and one ordinary hold,
without retry or follow-on pair movement. Extended the existing recovery-restart
launcher to accept the exact observed-pose installation/startup chain and
six-count evidence schema; added `observed_pose_hold` and its CLI to load the
exact installed hold settings. Sixteen focused hold-launch tests passed before
execution. No firmware, filesystem or servo-configuration changes were made.

- Restart: `wizard-20260919T152902403282Z-b579b1990e324345bb49d614ea016ffa`.
- New startup: `wizard-20260919T152928348766Z-219fa2ba65434e9cb3c91d6106a5591c`.
- New boot: `0b0e6cbe9e70093fb7be20fe6e117814`; startup IDLE/NOT_CONFIGURED,
  zero records, no storage fault and matching pair capabilities.
- Hold binding: `wizard-20260919T152948302998Z-301e97a36cca4ba48388e74e124f0d8b`.
- Replayed hold observation:
  `wizard-20260919T152952370406Z-262ee7d021ff4c9c84ee0343b8e96179`.

Result `CONTROLLER_REPORTED_HOLD_VERIFIED`, controller accepted, one command and
five snapshots. Elbow14 started2898 with previous goal2899. Requested and
library-encoded target2898 matched first/settled goal readback2898. Settled
position2897 gives signed error-1 count (tolerance2). Torque remained1; no explicit
enable used. Six neighboring joints had zero sampled position change and
unchanged goals/torques. This is ordinary-hold verification, not proof of the
untested +10/return path or Cartesian/stylus accuracy.

Next: offline preparation from this exact hold export, then separately approve
one bounded +10/return trial. Native fresh-anchor checks and export-verified
outbound arrival must gate the return. Do not repeat the hold or restart
automatically. Earlier ordinary-hold-pending notes below are historical.

## Current checkpoint — one observed-pose recovery hold verified

2026-09-19: executed the separately approved one-shot recovery with fresh joint
checks, no retry and no follow-on movement. Trial:
`wizard-20260919T151914084323Z-50415a59bfa44a2db538ea67fb9c99db`.
Assessment: `wizard-20260919T151914023615Z-29b3e0f7ef4c4d09aac174c50139d3d6`.
Raw transport: `wizard-20260919T151913972761Z-6e6b4fa227254ce7a396c2efec91cde8`.
Boot: `752f7b49cca73a121359f4cf1401d0b3`; ownership now consumed.

The independent saved-evidence replay returned
`CONTROLLER_REPORTED_RECOVERY_VERIFIED`: one action and five snapshots.
Elbow14 started at2899 with previous goal2903. Requested and library-encoded
target2899 matched first and settled goal-register readback2899. Measured settled
position2898 gives signed error-1 count, inside tolerance2. Torque remained1;
no explicit torque enable was used. All six neighboring joints had zero sampled
position change and unchanged goal/torque. Last observation was225544us after
the command; this is not a whole-motion latency benchmark.

This verifies the bounded hold/target-register reconciliation, not reverse-motion
accuracy, repeated bidirectional arrival, physical tip accuracy or independent
wire capture. Command encoding evidence is pinned-library argument encoding.
An initial manual replay invocation used a relative path and failed manifest
resolution; replay with the resolved absolute export path passed unchanged.
No device retry or artifact replacement followed that host-path error.

Offline follow-up corrected `replay_recovery` to resolve its input directory
before manifest validation. Native signed-evidence regression now covers both
relative Path/string inputs and tampered-report rejection. Nine focused native
recovery/replay tests passed. The unchanged real recovery export now replays
successfully via the original relative path, retaining verified category and
settled error-1. No hardware access occurred for this fix.

Next is a separately approved startup and ordinary hold to obtain a fresh
same-boot pair handoff. Do not reuse recovery ownership or automatically reset.
Only after verified ordinary hold may a separately approved +10/return trial run.
The software must derive its anchor from fresh evidence, not reuse2898 blindly.
All recovery-pending notes below are historical.

## Current checkpoint — settings installation and startup verified

Recovery readiness check against the actual retained installation/startup chain
passed: `LOCAL_R21_RECOVERY_PREFLIGHT_VERIFIED`, observed_pose profile, boot
`752f7b49cca73a121359f4cf1401d0b3`. No key extracted, hardware access or attempt
reservation. This is local readiness only, not evidence of current joint state.
Execution awaits separate bounded-recovery approval; do not substitute the
preflight success for that approval or for native fresh-position admission.

Offline runner follow-up: `observed_pose_pair` now prepares the exact +10/return
experiment from a replayed ordinary hold and delegates an explicitly approved
trial to the existing finite executor. Before delegation it checks the installed
settings/startup/boot chain, captures same-boot hold status, and verifies the
admission export. The shared executor retains one-use reservation and
arrival/export-gated return; no automatic retry, recovery or restart was added.
`software/scripts/run_observed_pose_pair.py` exposes mutually exclusive
`--prepare-only`, `--preflight-only`, and `--authorized-powered-pair` modes.
All modes require startup, stage and installation export IDs. Preparation takes
a hold export; preflight/execution take a preparation export. Private key loading
uses the hash-verified installed candidate and occurs only in execution mode.
Fifty-nine focused runner/CLI/shared-executor/legacy tests passed. New wrapper
tests use injected hardware dependencies, not live evidence. No real preparation
or trial has run: a verified ordinary hold remains missing, and the recovery hold
still needs separate approval. This supersedes earlier runner-unfinished notes.

2026-09-19: completed the explicitly approved one filesystem-only installation
and one startup for candidate
`45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267`.
The 1,441,792-byte filesystem at 0x290000 passed full readback verification.
Protected regions and recovery data were unchanged; staged credentials and all
unrelated entries were preserved. No automatic retry, recovery or servo command
was performed. The procedure took about 13 minutes including full flash reads.

- Plan: `wizard-20260919T145803795061Z-8889ef5f657f44389129a660035383e2`.
- Verified write: `wizard-20260919T151101878750Z-ccd94b534f4b4ba39873fd4ef4551622`.
- Installation/startup attempt: `wizard-20260919T151102041680Z-273348d615584d5595ec7dcf92acd265`.
- Startup observation: `wizard-20260919T151121268410Z-011fdac590be4b2b9e5cdcd79534d38f`.
- Boot: `752f7b49cca73a121359f4cf1401d0b3`.

Read-only startup observation reported IDLE/NOT_CONFIGURED, zero records,
storage_fault=false and a matching pair capability boot. Independent local replay
verified the staging/installation/startup receipt chain. Thirteen focused offline
provisioning/startup/CLI tests also passed. Installed bytes and startup health do
not prove that a motion owner has loaded the settings or that any endpoint was
reached. No fresh servo positions were acquired during this scope.

Next: separately authorize one bounded observed-pose recovery hold. It must use
fresh joint readings, the exact installed policy and the linked startup above;
stop on rejection, uncertain delivery or invalid feedback, without retry or
automatic follow-on movement. A subsequent ordinary hold and +10/return remain
separate steps. Earlier installation-pending statements below are historical.

## Current checkpoint — private settings staged, 2026-09-19

Offline follow-up: added `observed_pose_pair.review_observed_pair` to bind the
future +10/return preparation to the exact installed-settings/startup receipts,
boot and both configuration hashes. It rejects legacy command IDs/offsets,
changed tolerance/policy, an anchor whose +10 target exceeds the envelope, and
boots already consumed by recovery or a pair. It neither reads the controller
nor sends commands. Twenty-seven new-binding and legacy-runner tests passed.
The binding tests use synthetic receipts; they do not prove hardware arrival.
Live runner/CLI integration and a fresh ordinary hold remain required before
executing this experiment. Existing r16 +/-6 launcher pins were not relaxed.

Following explicit offline-staging approval, created the Windows current-user
DPAPI-protected candidate `observed-pose-plus10-candidate.dpapi`. No hardware
access, controller write, startup or movement occurred.

- Candidate SHA-256:
  `45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267`.
- Staging receipt:
  `wizard-20260919T145415048349Z-1324830e574a4e9294c0302ecce85e39`.
- Only `/rocell-hold.json` and `/rocell-pair.json` changed in the candidate.
  Five other entries, including credentials and the existing key, were preserved.
- Pinned r21 native parsers validated the settings; filesystem remount verified.
- Local installation preflight independently rebuilt the candidate exactly and
  returned `LOCAL_OBSERVED_POSE_PREFLIGHT_VERIFIED`, hardware_access=false,
  attempt_reserved=false.

Next approval scope: **one filesystem-only installation and one startup for
candidate `45320bab…08e7267`**, preserving credentials and unrelated settings.
After installation, observe startup with the staging/installation receipt bindings.
This scope does not include a recovery hold or movement. The following earlier
staging-pending statements describe historical checkpoints, not current status.

## Current checkpoint — r21 installation completed, 2026-09-19

The approved one app-only installation and one startup completed successfully.
Application readback matched the r21 SHA-256 below; protected flash regions were
unchanged, preserving settings and credentials. No provisioning, recovery hold or
servo command was performed. This supersedes the historical not-installed and
approval-pending statements below.

- Installation: `wizard-20260919T144917659983Z-6a8de2a695f347708de235263fbd1328`.
- Startup: `wizard-20260919T144917976537Z-2191dba2905f4ae89db9286f7b3575ee`.
- Boot: `f4ce9f7104c6f94a1f652c4433a7d55f`.
- Observed startup: IDLE/NOT_CONFIGURED, zero records, storage_fault=false;
  matching status around the pair-protocol capability read.
- Heap snapshot: free188008/minimum183880/largest110580 bytes. This is not a
  guarantee of runtime resource sufficiency or physical accuracy.

Next authorization: **offline private settings staging only**. Its output must
preserve credentials and unrelated entries, replace only the two reviewed settings
documents, and expose an image hash for subsequent installation review. No device
write or startup is part of staging. The later filesystem installation/startup,
bounded recovery and movement tests each retain their existing scoped approvals.
The reverse-motion discrepancy remains unresolved; startup health is not motion
or endpoint verification.

## Current compatibility finding — do not provision this draft onto r20

### Historical preparation — r21 offline candidate built and reviewed

R21 is **not installed**. Public staging verified all r20 source hashes, changed
only the recovery-policy header, recovery route and opt-in macro, and retained
108 other files. Stage receipt:
`wizard-20260919T142632895985Z-b8f11ecc6703406e8cb60308a9e001d7`.

ESP32 default4MB/no-PSRAM build completed successfully:
`wizard-20260919T142823450037Z-4bfd7a6265a24e2fac964fbd26d3bce8`.
App SHA-256:
`035922452587280362fc1e6fe0120f274647eeb2b0f8ee3c7bc88cb8c3289051`.
Application size1,127,424 bytes; slot headroom183,296 bytes. Partition and
bootloader hashes match the reviewed profile. Candidate/source hashes and retained
recovery backups verified in offline review:
`wizard-20260919T142847003629Z-01aecbc603a44160b7939da5f8545677`.

The disassembly review found179 relevant frames, largest individual frame432
bytes. These are not total-stack or runtime-heap guarantees. Thirty-two focused
tests passed alongside the build. Review remains `deployable=false`: completion
of receipt-bound installation/startup/recovery integration and explicit approvals
are still required. Private filesystem candidate staging has not occurred.
The controller remains on r20 with its original filesystem and consumed pose
observation. No controller connection, flash, reset or motion occurred here.

R21 is now wired into the app-only installer with the exact r20 predecessor,
1,127,424-byte app, a separate one-use journal, and the current negative6
filesystem identity. Local preflight passed against retained artifacts without
opening a device or reserving a journal. The startup observer and retained
startup verifier now recognize r21 and its pinned review receipt. Sixty-six
installer/startup tests passed, including wrong boot, revision, response hash,
status, capability and installation-link rejection. A stale test mock omitted
r21 initially; correcting the mock restored the new positive case without
weakening production validation.

This makes **one r21 app-only installation and one startup** ready for separate
approval, preserving the current filesystem. It does not install the new pose
settings or authorize recovery. The latter still needs the private candidate,
filesystem installation receipt and post-provisioning startup/recovery bindings.

Source review found that r20's board recovery route requires the old command ID
`r7-supported-hold-20260918` and `reviewed_recovery_source` requires the old
windows and explicit-enable permission. The new settings pass the JSON parsers
and core simulations but **fail this production recovery preparation gate**.
The host recovery launcher also binds its six-count profile to r19 and the old
source-policy receipts. None of those gates should be bypassed.

A native regression compiled against the immutable r20 headers now checks that
the original configuration is admitted and the proposed configuration rejected.
The earlier statement that private staging is ready means only that the offline
image composer exists; it is not approval or compatibility for deployment.

Next: prepare an explicit exact-policy recovery compatibility change offline,
with a distinct profile/command identity and corresponding host receipt checks.
Preserve the legacy profile. Review/build the resulting application candidate
before choosing an installation sequence. Defer actual private staging until
the application/settings combination is coherent. No new firmware, settings,
startup or recovery operation is currently authorized.

### Offline source compatibility change implemented

The development recovery route now has an opt-in
`ROCELL_OBSERVED_POSE_RECOVERY` profile. It requires the six-count recovery
runtime at compile time, recognizes only the exact new pose windows/timings,
requires torque-enabling permission to remain disabled, and checks the new hold
command ID. Its distinct recovery command is
`observed-pose-six-count-recovery-v1`. The legacy policy and command remain
separate and unchanged. Unknown IDs or mixed settings do not match either profile.

Fifteen focused tests passed. The new board-level fixture ran14 scenarios for
each of the legacy and observed configurations, covering missing/invalid settings,
key read failure, runtime initialization failure, ownership conflicts, mutated
policy/command and duplicate preparation. The immutable installed-r20 test still
confirms r20 rejects the new settings. This source change is **not enabled in or
deployed to r20**, and no new firmware candidate has yet been built.

Next: bind the host's recovery plan and receipt validation to this distinct
profile, then stage/build/review a coherent application candidate offline. Keep
private staging and controller operations pending separate explicit approval.

### Host exact-profile signing contract implemented

`observed_pose_recovery.py` replays the public candidate, checks the exact hold
and pair hashes, and freezes/signs only
`observed-pose-six-count-recovery-v1` for the supplied boot. It retains the native
`six_count` wire schema; a new command/policy identity does not require inventing
an incompatible wire format. Mixed legacy commands, boot IDs, altered pose limits
and changed settings are rejected. Twenty-one focused tests passed across this
contract and the native policy/board checks.

This module is pure preparation/signing with a caller-supplied key, not a live
entry point or installation-authority check. The deployment/startup/recovery
receipt chain is still outstanding and must gate its eventual live caller.
No real key was loaded in the tests, and no command was transmitted.

## Public candidate implementation checkpoint

The offline generator `scripts/draft_observed_pose_candidate.py` now independently
replays the pose export, checks the predecessor hold hash, and exports both public
settings objects without private-image access or hardware access. Draft receipt:
`wizard-20260919T141022680208Z-41667e86896345faae1e1c0362fc3e47`.

- Hold SHA: `cb844a0818b501f9186cf4e421628d28ea4c3e8c583e2171d6d15f62a0dc4354`.
- Pair SHA: `0dade56675bc9767358888d78c34258121f65e3eae7f92b95ed5b77cfc5b2835`.
- New IDs distinguish this hold and +10 pair from earlier trials.
- In addition to the proposed windows, `permit_explicit_enable` changes from1
  in the predecessor to0: an already enabled elbow is required, not re-enabled.
- Fifteen focused tests passed, including both r20 native settings parsers,
  predecessor preservation, incompatible evidence rejection and path boundaries.
  The immutable draft receipt predates parser testing and therefore correctly
  retains `native_parser_verified=false`; this later test result supplements it.

Still required before installation: receipt-bound provisioning and recovery
integration, finite native movement simulations with this exact policy, and a
reviewed private staging/install approval. Parser acceptance alone does not prove
the movement workflow compatible or authorize loading the draft on the arm.

### Exact-policy native core simulation completed

`test_observed_pose_movement.cpp` parses the generated hold settings and exercises
the recovery, ordinary-hold and finite-pair owners against a scripted servo bus.
The combined focused suite now passes16 tests. Native scenarios verify:

- Ordinary hold rejects the observed four-count residual without writing.
- The explicitly selected six-count recovery profile writes a hold at measured2899,
  without enabling torque; subsequent ordinary hold accepts the reconciled state.
- +10 reaches2909 and the explicitly admitted return reaches2899 in the ideal bus.
- Stuck outbound motion, uncertain write acknowledgement, publication failure and
  neighbor drift stop the sequence without authorizing a return.
- Rejected return admission, neighbor drift before return and stuck return stop
  further work. Additional polling performs no retries.
- Anchor2900 rejects +10 rather than clipping the target or recentering.

These are **core simulations**, not a proof of the authenticated/exported lifecycle
or physical motion. Return admission is synthetic in this fixture. Production
still needs recovery export, separately approved startup and ordinary hold, plus
signed commands and a verified forward export before return. Do not connect the
owners directly on hardware merely because this test does so offline. No settings,
firmware, servo configuration or live pose changed during these tests.

## Evidence

### Operational entry points complete for staging/install/recovery preparation

`install_observed_pose_settings.py` now has mutually exclusive local preflight
and explicitly authorized filesystem-install/startup modes. Both require the
staging export and exact candidate hash, verify r21 installation, replay the public
candidate, check native parser identities, and reproduce the complete preserving
filesystem image before any hardware libraries are imported. Execution identifies
the expected USB adapter and uses the single-attempt provisioning runner. No
automatic startup observer, recovery or movement is chained after installation.

Thirty-four focused CLI/provisioning/startup/recovery tests passed. Missing mode
or missing r21 installation stops before private-image or hardware-library access.
Positive provisioning uses a simulated controller; actual CLI positive preflight
still awaits the real approved staging output. No installation command was run.

The pending operational order is now explicit:

1. Obtain approval; install r21 app-only with one startup, preserving the existing
   negative6 filesystem. Run the read-only r21 startup observer and retain receipts.
2. Obtain offline private-staging approval; run `stage_observed_pose_settings.py`
   against public candidate `wizard-20260919T141022680208Z-41667e86896345faae1e1c0362fc3e47`.
3. Run the installation command in `--preflight-only` mode using the resulting
   staging export and candidate hash. Review the exact resulting private image.
4. Obtain approval for that exact filesystem candidate and one startup; execute
   `--authorized-filesystem-install-and-startup` once. Observe startup with both
   observed-pose receipt arguments; independently replay the combined binding.
5. Obtain approval for one bounded recovery hold; use the observed_pose recovery
   profile with stage, installation and linked startup receipt IDs. Export and
   assess before deciding further action. No automatic next movement.

Approval for one step does not imply approval for later hardware changes. The
requested goal remains incomplete: live reverse-motion resolution, repeated
cycles, additional joints and ghost-key sequences still require hardware evidence.

### Receipt-bound recovery runner integrated

`run_supported_recovery.py --profile observed_pose` now requires stage,
filesystem-installation and linked r21 startup receipt IDs. These are replayed
before hardware access and before key extraction. The coordinator then uses the
exact public candidate's hold policy and distinct observed recovery command over
the existing six-count wire protocol. Legacy profiles reject observed-pose receipt
arguments. The one-use boot claim, no-resend behavior, raw evidence collection,
export replay and no automatic follow-on movement remain shared with prior runs.

Thirty-three focused tests passed. The observed profile was included in success,
invalid baseline, uncertain prepare, send failure, uncertain delivery and capture
failure scenarios; missing receipt IDs fail before any network call. These are
injected-boundary tests, not evidence of a real recovery under the new settings.
No live invocation occurred. The filesystem installation CLI remains the final
missing operational entry point; r21/private staging/filesystem approvals and
resulting real receipts are still required before recovery can run.

### Post-provisioning startup linkage implemented

The startup observer now accepts paired `--observed-pose-stage-export` and
`--observed-pose-installation-export` arguments only for r21. Before any network
read, it verifies the completed filesystem chain; its exported health observation
retains that exact binding. `review_observed_startup` independently replays both
chains and rejects app-only startup evidence, a different installation ID or a
changed candidate hash. Its result grants neither recovery authority nor a fresh
pose claim. Fifty-five focused startup/provisioning tests passed.

No startup observer was run against hardware in this step. The live installation
CLI and recovery runner still need to consume these bindings; required r21 and
filesystem installation receipts do not yet exist.

### Completed-filesystem receipt verifier implemented

`observed_pose_installation.py` now checks the staged public-candidate linkage,
exact r21 application installation, source/candidate image identity, both policy
hashes, write/run receipt agreement, protected-region verification and the exact
single-startup journal sequence. Its result explicitly does not claim current
device bytes, startup health or movement authority. The later startup observer
must supply the separate health evidence; an app-only startup is insufficient.

Nineteen focused tests passed. The verifier consumed genuine exports/journal
from the synthetic provisioning flow and rejected seven mutations: candidate,
hold hash, app identity, repeated journal event, write receipt, missing startup,
and false protected-region verification. No real installation receipt exists yet.

The private staging script now requires verified **r21** installation and uses
the r21 parser snapshot. It therefore cannot accidentally stage a deployment plan
as though r20 supports the new recovery registration. It has not been executed
with its authorization flag. Next remains the installation CLI and explicitly
linked post-provisioning startup/recovery entry point.

### R21 filesystem execution profile integrated offline

The shared provisioning runner now supports an `observed-pose` profile pinned
to the exact r21 application hash/size and a separate one-use journal. It rebuilds
the approved two-file image, preserves the original filesystem privately, checks
device/app/partition/source identity, writes once, verifies full readback and
protected regions, exports the verified result, and only then permits the
separately requested startup. Its public plan binds both settings hashes and
both changed paths. No real device adapter was invoked during implementation.

Ten synthetic-image/provisioning tests passed, covering success, wrong installed
app, uncertain write, result-export failure, refusal to reuse a consumed attempt,
and two-file preservation. Eight legacy pair-settings lifecycle tests also passed.
An initial combined-policy digest attempted to serialize byte payloads; it was
corrected to hash the canonical pair of document digests before the passing run.

Remaining live wiring: exact private staging receipt/candidate identity,
installation CLI, completed-filesystem receipt replay and the post-provisioning
startup/recovery binding. App-only r21 startup is explicitly insufficient evidence
that the new pose settings have been installed. Hardware operations remain pending
approval; no filesystem candidate has been privately staged or installed.

### Private staging entry point ready, not executed

`scripts/stage_observed_pose_settings.py` now requires explicit offline-private-
staging authorization. It independently replays the public candidate back to the
pose evidence, reviews r20 installation evidence, checks private-directory ACLs,
pins the r20 parser headers, compiles native validators, and uses the exact
negative6 source image hash before composing the two-file replacement.
The output is a new DPAPI-protected candidate; an existing destination is never
overwritten. It cannot install firmware/settings, reset, or send motion commands.

The existing public candidate replayed successfully with report SHA
`92c4fd65ec3d5afd980d234e82c9f14b7fd7dbaffa179d5cb41e6d9b7815ee83`.
The entry point was tested **without authorization** and exited at argument
validation. No private backup was opened or candidate staged. The focused suite
passed24 tests, including altered-report rejection and the authorization refusal.

Next requested approval: offline private staging of this public candidate only.
After staging, review the resulting image hash and implement/verify its exact
installation/startup/recovery receipt bindings before requesting hardware writes.

### Offline filesystem replacement implementation

`replace_observed_pose_image` now composes the exact reviewed hold-policy and
pair-settings changes in memory. It pins all four old/new document hashes,
requires native-parser validation, checks the source image hash and existing
file bytes, then remounts and checks unrelated entries after each replacement.
Only the final complete candidate is returned; neither intermediate image is
saved. Diagnostic keys, credentials and unrelated filesystem entries are retained.

Seventeen filesystem-focused regression tests passed, including real LittleFS
operations on synthetic images, the older direction-only path, and rejection of
source/policy mismatches, native validation failure and second-file write failure.
These tests do not access the user's backup. No private candidate has been staged.

Still outstanding: bind public draft replay, installed r20/parser identities,
private-source identity and resulting installation/startup/recovery receipts in
the actual staging/runner entry points. Separate approval remains necessary for
private staging and hardware provisioning; this function is not a deployment tool.

### Signed-command and export simulation checkpoint

The authenticated runtime regression now includes the exact proposed hold policy,
hold command ID and +10 pair IDs. Using synthetic keys and a simulated servo bus,
it exercised real HMAC admission, hold-to-pair handoff, host delivery receipts,
native endpoint records, reproducible forward exports, evidence-linked return
authorization, return assessment and wizard rendering for2899→2909→2899.

Invalid signatures, mismatched handoffs, altered exports, uncertain delivery and
short acknowledgements remain rejected. Non-arrival stops progression. Export
replay contacts no hardware, and the wizard continues to show stylus accuracy as
unqualified. The combined regression passed **21 tests in88.24s**, including the
legacy direct/socket/powered variants, earlier +12 fixture, and new policy tests.

This completes the offline signed ordinary-hold/pair/export check, not live
qualification or the deployment/recovery receipt integration. The test begins
with a reconciled elbow goal2899; separate core tests cover recovery from2903.
Next implement the reviewed provisioning and startup/recovery receipt bindings
for the new policy before requesting a concrete installation/test approval.
The installed r20 app and filesystem remain unchanged.

Replayed device export:
`wizard-20260919T140601952739Z-506d59e6e4044e8fb8f49b3b1f21ea17`.
Raw bundle SHA-256:
`19f9755150098d7117713c664778699a9d596231964daa61e0e80d695622454e`.
Three samples showed zero position span for each joint. Elbow measured2899,
saved goal2903, torque1. All other joints reported torque0 and goal0.
The shoulder readings2487/1629 match the earlier recovery snapshot. This supports
registering a different observed pose, not expanding the physical workspace or
claiming the reverse-direction error has been fixed.

## Proposed registration for an elbow-only test

Keep the elbow envelope2893–2909 and existing speed20/acceleration1, arrival and
neighbor-drift tolerance2. For non-elbow joints, propose narrow admission windows
around the captured positions (below). These are **review candidates**, not
installed settings or certified collision limits.

| Servo | Observed position | Proposed admission window |
| --- | ---: | --- |
| 11 | 2047 | 2045–2049 |
| 12 | 2487 | 2485–2489 |
| 13 | 1629 | 1627–1631 |
| 14 | 2899 | 2893–2909 (unchanged) |
| 15 | 2035 | 2033–2037 |
| 16 | 2041 | 2039–2043 |
| 17 | 2054 | 2052–2056 |

Do not enable torque on the other joints: their goal registers are zero. Their
sampled stability does not prove they can support every load during elbow motion.
Monitor all neighbors and stop progression if they drift. Fresh native readings
must admit the actual starting pose; never substitute these historical samples.

## Useful next path

At the historical anchor2899, +6 reaches2905 and +10 reaches2909. Both fit the
existing encoder envelope; +12 reaches2911 and does not. Prefer a separately
identified **+10/return comparison**, after a verified recovery hold at the
current measured elbow position. This tests a larger positive displacement
without enlarging the elbow envelope. It is not a compensation command.

Because +10 reaches the upper bound at this anchor, fresh anchor movement can
make it ineligible. Require both A and A+10 inside2893–2909; do not clip, recenter,
reduce the offset silently, or move to the historical anchor first.

1. Implement a receipt-bound replacement registration and distinctly named +10
   settings, with offline tests for the new policy hash, bounds, wrong receipts,
   recovery residual4, failed arrival, neighbor drift and export failure.
2. Review exact provisioning/startup/recovery scope and obtain approval before
   installing anything. Preserve credentials, gains and unrelated settings.
   Current observation ownership is consumed; no hidden restart is permitted.
3. Obtain a fresh verified hold and endpoint A. If prerequisites cannot pass,
   export the rejection and stop without retries or automatic recovery.
4. Send A+10 once; record transmitted target, target-register readback, fresh
   position trace and neighbor state. Export and verify the outbound result.
5. Return to A only after verified arrival and successful export. Stop on
   non-arrival, invalid feedback or uncertain delivery; do not automatically resend.
6. Compare both directions against the earlier -6 trial. A successful test alone
   does not establish a general correction model. Repeat and use held-out targets
   before enabling compensation or progressing to coordinated ghost typing.

## Reproduce the offline path comparison

From the workspace root:

```powershell
.\.venv\Scripts\python.exe software/scripts/review_observed_elbow_paths.py --pose-export wizard-20260919T140601952739Z-506d59e6e4044e8fb8f49b3b1f21ea17
```

This replays the saved evidence and prints illustrative paths only. It accesses
no controller and supplies no movement authority. Five focused tests passed for
path arithmetic, retaining out-of-bounds targets and invalid-anchor rejection.
