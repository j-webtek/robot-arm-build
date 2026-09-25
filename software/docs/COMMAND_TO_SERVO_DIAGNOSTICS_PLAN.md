# Command-to-servo diagnostics and return-motion recovery

Current strategy: [bounded motion characterization](BOUNDED_MOTION_CHARACTERIZATION_PLAN.md).
Pause the r32 single-compensation deployment; develop reusable finite baseline
campaigns and analyze across movements before selecting compensation.

## Active objective update — powered upright recovery

Follow [UPRIGHT_POWERED_RECOVERY_PLAN.md](UPRIGHT_POWERED_RECOVERY_PLAN.md) for the
current user-selected objective: staged software-controlled recovery to an upright
approximately90-degree elbow pose. It supersedes the blanket padded-support
request and the old elbow-only next-test proposal. Contact and gravity must still
be assessed; deployment, initialization/enable and movement remain separately
approved actions. Prior captures and findings below are retained as evidence.

## Active priority — re-establish pose and clearance after repositioning

**Superseding physical finding:** user confirms the gripper is touching the board
in the latest photograph. Suspend the proposed elbow-only direction test from
this pose. First review a supported-clearance recovery and obtain its separate
execution approval; do not home, energize passive joints, remove support/power,
or sweep the elbow automatically. Current contact is a confound, not proof of
the cause of all earlier errors. See
[the contact checkpoint](CURRENT_POSE_DIRECTION_REVIEW_20260919.md#superseding-observation--board-contact-confirmed).

Latest execution, 2026-09-19: the user separately approved one startup and one
three-snapshot read-only capture. Both completed; independent offline replay
verified STABLE_SAMPLED_POSE. New boot `4391736215673ff84122c24fc6287d91`;
assessment `wizard-20260919T162409109808Z-482d849b3ab548a69c8b9eae7ef59b8f`.
Positions for servo IDs11–17: `[2047,2455,1659,2906,1589,2040,2047]`.
All spans0, modes0 and moving flags0 over approximately240ms. Only ID14 reports
torque1; its retained goal2907 differs from position2906 by1 count. Other torque
states are0 and their goal registers read0; these are not usable motion targets.
No hold, movement, settings write or retry was performed. This consumes the
approved startup/capture scope, not a new movement scope. Current readings do not
establish when or why the elbow changed from its earlier2897 reading.
User clarification: the base is fixed and did not move. Different photographic
viewpoints do not establish robot movement. Preserve any previously valid
base-to-board registration; this confirmation does not create a measured transform
where none existed. Do not attribute the measured joint differences to manual
repositioning as an established cause.
Next: assess current whole-path clearance,
and prepare a newly bounded movement proposal; do not reuse old policy windows.
See the next-test document for full receipt links and comparison.

2026-09-19: an earlier message was interpreted as arm repositioning; the user
subsequently confirmed the base never moved. Earlier
positions and prepared targets are historical and must not drive new commands.
This section supersedes next-action instructions in earlier checkpoints.
The user's latest agreement updates planning scope only: this document revision
does not consume or imply a startup, deployment or motion authorization.
See [reposition details](R20_OBSERVED_POSE_NEXT_TEST.md) and
[direction evidence](ELBOW_DIRECTION_COMPARISON_20260919.md).

1. Completed for this checkpoint: obtain explicit scope for one startup and one three-snapshot read-only pose
   capture, without a hold or movement command. The current r21 boot retains the
   failed trial and cannot admit a fresh pose capture in that owner state.
   A startup can have physical effects; preserve mechanical support and avoid
   unsupported power removal. This plan edit does not execute or authorize it.
2. Capture all seven servos' fresh positions, goals, mode/torque status and read
   validity with boot and acquisition timing. Export and replay the three scans;
   report sampled stability separately from ongoing stability. Never substitute
   stored trial records for current measurements.
3. Establish the current physical context using available photos/user observations
   and verified geometry: board, base, links, gripper/tool and cables. Record known
   constraints and unknowns. Validate the swept path, not only the target; count
   limits are not collision limits. Do not assume increasing counts means moving
   away from an obstacle. Ask only targeted questions that change the decision.
4. Produce an explicit new pose registration and bounded experiment proposal.
   Keep measured start, desired endpoint, encoded command and physical clearance
   distinct. Reconcile goal/position discrepancies only through a separately
   approved bounded procedure. Do not automatically enable unpowered joints,
   widen windows, change settings or return to a historical anchor.
5. With separate movement approval, test a small direction known to have clearance,
   assess/export its endpoint, and permit a return only after verified outbound
   arrival and export. Stop on non-arrival, invalid feedback, uncertain delivery,
   unexpected motion or export failure. Do not respond to increasing effort
   without displacement by commanding farther or tuning gains automatically.
6. Progress through matched bidirectional repeats and held-out targets, additional
   joints, coordinated noncontact approach/press/retract and short ghost-key
   sequences. Preserve comparable pose/load/settings and note confounders. Fit
   compensation only to repeatable actual motion, not a blocked/non-moving sample.
7. Integrate this workflow into wizard state and exports: manual reposition or
   changed mounting invalidates prior pose/path admission; display requested,
   encoded and readback targets, fresh measured endpoints, signed error and
   arrival/non-arrival/inconclusive verdict. Retain raw evidence and configuration
   provenance. A STOPPED sequence must not be presented as torque disabled.

### Practical completion gates

- First checkpoint: a reproducible fresh-pose export, with each joint's read
  validity, timing, measured position, available goal/torque/mode information and
  sampled stability. Unsupported fields remain explicitly unknown.
- Record whether repositioning changed joint angles, the base's location on the
  board, or both. Joint readings cannot establish the base-to-board transform;
  invalidate that registration separately if the base moved or its location is
  uncertain. Do not infer it from the historical photos.
- Before each approved test scope, record the current start, bounded targets,
  speed, arrival tolerance, observation deadline and clearance basis. Inspect
  intermediate poses and all links/tool/cables, not just the endpoint. Where
  geometry is uncertain, use a targeted observation and a conservative test
  envelope rather than claiming a complete collision model.
- A single approval may cover a clearly bounded finite campaign; no routine
  per-leg confirmation is needed within that scope when fresh feedback and
  clearance checks pass. Stop the scope on a failed gate; never enlarge it or
  reuse a consumed one-shot approval automatically.
- Success means exported, software-verified movement in both directions followed
  by repeatable noncontact sequences within declared tolerances. A received
  command, matching goal register or successful hold alone is not movement proof.
  Encoder-based endpoint evidence is not a physical stylus-tip measurement.

Completion still requires reliable software-verified movements and the planned
ghost-keyboard sequences, not merely firmware installation or successful holds.
Camera integration, physical contact and measured stylus-tip accuracy remain
deferred until mounting and registration are ready. Preserve recovery backups;
firmware deployment, provisioning and servo-configuration changes need explicit
separate approval. Work autonomously on software and read-only investigations.

### Replacement goal text

Implement software/docs/COMMAND_TO_SERVO_DIAGNOSTICS_PLAN.md to establish a
reliable, clearance-aware command-to-motion workflow for ghost-keyboard typing
and eventual physical keyboard typing and Android tapping.

First re-establish the arm's current pose after manual repositioning. Treat all
previous coordinates, prepared targets and clearance assumptions as historical.
After separately authorized startup if required, acquire and export fresh,
valid multi-joint position/goal/torque diagnostics, verify sampled stability and
register the new starting pose. Do not issue a hold, recovery or movement as part
of a read-only capture.

Determine whether repositioning changed joint angles, base placement, or both.
Invalidate base-to-board registration separately when needed; servo readings
cannot recover that transform. Report unsupported diagnostic fields as unknown.

Before movement, consider the board, base, links, tool and cables across the
entire proposed path. Distinguish encoder limits from physical clearance and
verified geometry from assumptions. Use targeted user observations when needed,
without requiring routine visual confirmation of every command. Never assume a
raw count direction is physically clear or command farther when position does
not change despite increasing effort.

Validate separately approved bounded movements using requested target, encoded
command, supported target-register readback and fresh positions before/after.
Automatically classify verified arrival, verified non-arrival or inconclusive
evidence, retain reproducible exports and gate returns on verified outbound
arrival and export. Investigate directional errors with matched pose/load/settings
and correct demonstrated causes. Apply compensation only after repeatable actual
motion and held-out endpoint tests support it.

Progress through bidirectional cycles, additional joints, coordinated noncontact
approach/press/retract and short ghost-key sequences, integrating setup, pose
invalidation, clearance checks, telemetry, results and export into the wizard.
Do not claim Cartesian or stylus-tip accuracy from encoder evidence alone.

Work autonomously on software and read-only investigations. Preserve backups and
recovery evidence. Obtain separate approval before startup/recovery, new physical
test scopes, firmware deployment, provisioning or servo-configuration changes.
Use finite, explicitly bounded test scopes with declared speeds, tolerances and
deadlines so approved campaigns can progress without routine per-leg prompts.
Stop affected sequences on uncertain delivery, invalid feedback, unexpected
motion, non-arrival or export failure; never automatically resend, reset, recover
or disable torque. Recognize that STOPPED does not mean torque-off, and avoid
unsupported power removal. Defer camera integration, physical contact and measured
stylus accuracy until mounting and registration are ready.

## Current checkpoint — r21 and observed-pose settings installed

Read-only follow-up after the failed +10 trial verified current settings without
reset or movement: configuration
`wizard-20260919T155259859927Z-2f5e054a3fdd40759d4c0d1787c52e97`, gains
`wizard-20260919T155316025837Z-ffc1aabe26234a9bb53c30c53904865d`.
Both matched retained GET responses. Deadbands0/0, mode0, torque1, speed20,
acceleration1, torque limit1000, position limits0–4095 and P32/D32/I0 remain
unchanged from earlier captures. No configuration writes or new movement.
See [the direction comparison](ELBOW_DIRECTION_COMPARISON_20260919.md) for
raw-unit limitations and remaining mechanical/load/control ambiguity.

Latest trial, 2026-09-19: approved +10/return stopped after **verified outbound
non-arrival**, with return withheld. Requested/encoded/readback target2907;
fresh measured position stayed2897 across21 snapshots (~2.03s post-command),
error-10 counts, elbow torque1. Controller reported one successful acknowledged
write; no measured displacement. No retry, recovery, reset or later movement.
Observation `wizard-20260919T154710417443Z-d47c57ebbdda4ebeb7c1493b5d14da9a`
independently replayed as CONTROLLER_REPORTED_NON_ARRIVAL. Final trial
`wizard-20260919T154710616339Z-fcfa5abf4fd74620ac39ab5a580cb92f`.
The feedback/export/stop pipeline worked; bidirectional movement did not pass.
Investigate control/feedback causes using retained evidence and compatible
read-only diagnostics before proposing another bounded experiment. No
compensation model or physical-tip accuracy claim follows from this result.

Newest result, 2026-09-19: the separately approved one startup and one ordinary
hold completed with no retry or follow-on pair movement. Startup
`wizard-20260919T152928348766Z-219fa2ba65434e9cb3c91d6106a5591c` establishes boot
`0b0e6cbe9e70093fb7be20fe6e117814`. Hold observation
`wizard-20260919T152952370406Z-262ee7d021ff4c9c84ee0343b8e96179`
replayed as `CONTROLLER_REPORTED_HOLD_VERIFIED`: one action/five snapshots,
requested/encoded/readback target2898, settled position2897, error-1 count.
Other six joints showed no sampled position, goal or torque changes. No explicit
torque enable. Next: prepare the exact +10/return trial offline and obtain its
separate movement approval. Bidirectional accuracy remains unverified.

Latest hardware result, 2026-09-19: one explicitly approved bounded observed-pose
recovery hold returned `CONTROLLER_REPORTED_RECOVERY_VERIFIED`, independently
replayed from export. Trial
`wizard-20260919T151914084323Z-50415a59bfa44a2db538ea67fb9c99db`;
assessment `wizard-20260919T151914023615Z-29b3e0f7ef4c4d09aac174c50139d3d6`.
One action/five snapshots: elbow goal2903 changed to requested/encoded/readback
2899, measured position2899 to2898 (settled error-1 count, tolerance2). Other six
joints showed no sampled position, goal or torque changes. No retry, reset,
explicit torque enable or follow-on movement. Current boot's recovery ownership
is consumed. This reconciles the hold target but does not resolve general reverse
motion or prove stylus accuracy. Next requires a separately authorized startup
and ordinary hold before any separately approved +10/return comparison.

2026-09-19 latest: the approved filesystem-only installation of candidate
`45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267`
and one startup completed. Full flash readback verified the candidate and
unchanged protected regions/recovery; credentials and unrelated entries preserved.
Installation receipt: `wizard-20260919T151102041680Z-273348d615584d5595ec7dcf92acd265`.
Startup receipt: `wizard-20260919T151121268410Z-011fdac590be4b2b9e5cdcd79534d38f`.
Boot `752f7b49cca73a121359f4cf1401d0b3`: IDLE/NOT_CONFIGURED,
zero records, no storage fault. Settings/startup receipt linkage independently
replayed. No recovery or movement commands sent; no fresh positions captured.
Next is a separately approved bounded observed-pose recovery hold, not an
automatic +10 test. The reverse-motion discrepancy remains unresolved.
This supersedes all staging/installation-pending checkpoints below.

Latest update, 2026-09-19: explicitly approved offline private settings staging
completed. Candidate SHA-256
`45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267`
is stored under current-user Windows DPAPI protection. Receipt:
`wizard-20260919T145415048349Z-1324830e574a4e9294c0302ecce85e39`.
Only the two reviewed hold/pair settings documents changed; five unrelated
entries, credentials and the existing key were preserved. Native validation,
remount verification and exact-rebuild local installation preflight passed.
No hardware access occurred. New settings remain **not installed**. Next is
separate approval for one filesystem-only installation of this exact candidate
and one startup, followed by receipt-bound startup observation; no movement.
This supersedes the staging-pending next step in the earlier checkpoint below.

2026-09-19: completed the explicitly approved **one r21 app-only installation
and one startup**, preserving existing settings and credentials. Full application
readback matched SHA-256
`035922452587280362fc1e6fe0120f274647eeb2b0f8ee3c7bc88cb8c3289051`
(1,127,424 bytes). Protected flash regions were unchanged. The installer exited
successfully with one startup attempt; no retry, filesystem provisioning,
recovery hold, servo command or movement test was performed.

- Installation receipt: `wizard-20260919T144917659983Z-6a8de2a695f347708de235263fbd1328`.
- Read-only startup receipt: `wizard-20260919T144917976537Z-2191dba2905f4ae89db9286f7b3575ee`.
- Boot: `f4ce9f7104c6f94a1f652c4433a7d55f`.
- Startup: `IDLE_AND_PAIR_PROTOCOL_OBSERVED`; IDLE/NOT_CONFIGURED,
  zero records, no storage fault; matching status before/after capability read.
- Preserved filesystem SHA-256:
  `d1c041bcb4e90082685babc16698bcef3c639d87464932d6534d8056b71ce3aa`.

R21 adds compatibility for the exact proposed observed-pose recovery policy;
it does not itself install that policy or resolve the reverse-motion discrepancy.
No fresh servo-position capture was taken in this scope. Next: separately approve
offline private staging of the two settings documents, review its resulting image
hash, then separately authorize filesystem-only installation/startup. Recovery
and movement remain separate operations. See
[the observed-pose plan](R20_OBSERVED_POSE_NEXT_TEST.md).

## Historical checkpoint — r20 installed; read-only pose capture verified

Next implementation proposal: [R20 observed-pose registration and +10 comparison](R20_OBSERVED_POSE_NEXT_TEST.md).
This replaces the ineligible +12 proposal for the current observed anchor only;
it is not installed, approved for motion, or a compensation policy.

2026-09-19: the explicitly approved r20 app-only installation, one startup and
one three-snapshot acquisition completed. Full app readback matched the reviewed
SHA below; protected flash regions were unchanged, preserving filesystem settings
and credentials. No provisioning, recovery, position command or torque change
was performed. This checkpoint supersedes the historical r19-installed and
r20-not-installed statements below.

- Installation: `wizard-20260919T140553029696Z-e97832bd40f44918b47acb5212ff0f53`.
- Startup: `wizard-20260919T140553419741Z-b0a4d7cb11394a48b3f75479445f980d`;
  IDLE/NOT_CONFIGURED, zero records, no storage fault.
- Boot: `9ac95466684dfbbfeb1fda95fc25e8e3`.
- Capture: `wizard-20260919T140602002302Z-e7d16f8b3fd241038851c0bad49d8dc7`.
- Replayed assessment: `wizard-20260919T140601952739Z-506d59e6e4044e8fb8f49b3b1f21ea17`.
- Terminal: CAPTURED, three snapshots, action_count=0; STABLE_SAMPLED_POSE.

All seven positions had zero observed count span. IDs11..17 were respectively
2047,2487,1629,2899,2035,2041,2054. Controls remained unchanged; only elbow14
reported torque enabled, with goal2903 and measured2899. Other joints reported
torque0 and goal0. Shoulder sum remains4116, matching the prior recovery snapshot.
This verifies sampled encoder stability, not ongoing stability, supported load,
Cartesian clearance, or stylus accuracy. The four-count elbow residual remains;
the reverse-motion problem is not resolved by this observation.

Next offline work: propose explicit pose registration using this evidence and
review an eligible noncontact elbow path. Preserve the old baseline and do not
silently widen it. Do not enable shoulder torque against zero goals. Observation
ownership is consumed for this boot; no automatic new startup or movement.
Any settings installation, startup/recovery and movement need their own approved
scope. The existing +12-from2899 proposal still exceeds elbow maximum2909.

## Historical checkpoint — r19 recovery rejected the changed shoulder pose

### Offline r20 readiness — 2026-09-19

R20 is built and reviewed, **not installed**. It adds a finite read-only pose
capture: three full-joint snapshots, retained raw records, software stability
assessment and independently replayable exports. Capture sends no position,
torque or configuration writes. Startup itself is a separate hardware operation;
do not describe installation/startup as guaranteed motion-free.

The focused validation suite passed **69 tests**. This includes the pose-enabled
board fixture: registration performs no bus reads or settings initialization,
conflicting ownership denies observation, and a reserved observation blocks pair
preparation and configuration access. Simulated acquisition/network/export cases
do not establish live hardware performance.

Candidate app SHA-256:
`188e7a96ef11e516655f2f8b9e3efeecb4947a501bdc1ae2beda5cffb5da9572`
(1,127,072 bytes). Offline review export:
`wizard-20260919T135301585758Z-88cd5f3bb83a49ffa7373e76fd7ef4ff`.

Next authorization scope: one r20 app-only installation preserving filesystem
settings and credentials, one startup, then one three-snapshot read-only pose
capture if startup verification passes. No recovery hold, movement test, torque
enable, settings change or automatic retry is included. Review the resulting
sampled stability and coupled shoulder positions before proposing new pose limits.

This section supersedes installed-state and next-action statements in the
historical checkpoints below. R19 is installed; its one approved startup passed.
The separately approved recovery attempt was accepted but stopped before any
servo write: HOLD_POSE_OR_CONTROL_INVALID, action_count0. Its initial snapshot
reported shoulder IDs12/13 at2487/1629, outside the older pose windows, and elbow14
at2899 with goal2903. Recovery is consumed for that boot; do not retry or restart
automatically. Exact receipts and the next-step decision are in
[ELBOW_NEXT_MOVEMENT_EXPERIMENT.md](ELBOW_NEXT_MOVEMENT_EXPERIMENT.md).

User supplied five current-pose photos (attachment group
`DA002487-D0AD-4D46-8A39-953591C05ADC`) and requests no routine visual confirmation
of individual movements. Use these as qualitative current-pose context, not
calibrated coordinates, clearance measurements, or evidence of stability over time.

Next: reconcile the present folded pose with the registered baseline. Establish
fresh multi-snapshot stability before proposing a replacement policy; retain the
old policy and failure evidence. Review the two shoulder servos as a coupled pair.
Do not enable their torque against goal0, automatically return to the old pose,
or silently widen limits. Any new acquisition route that requires reset/deployment
and any policy provisioning require separate approval. Camera/contact stay deferred.

The +12 experiment remains prepared offline, not currently eligible:2899+12=2911
exceeds the existing elbow maximum2909. Select a path only after pose reconciliation;
do not clip or reinterpret the experiment. Gain readings remain P32/D32/I0, with
no gain changes or validated compensation model from this work.

## Historical checkpoint — negative leg arrived; positive return did not

Next experiment proposal: [ELBOW_NEXT_MOVEMENT_EXPERIMENT.md](ELBOW_NEXT_MOVEMENT_EXPERIMENT.md).
Prefer a bounded +12-count displacement test at unchanged gains before tuning.
It requires a separately identified six-count initial recovery profile and an
explicit positive-pair settings receipt; neither is installed or authorized by
this proposal. Existing admission and arrival tolerances remain unchanged.

2026-09-19 13:00 UTC: the separately approved single retained GET succeeded.
Exact original POST bytes, boot and capture matched; export replay passed.
Gain evidence P=32, D=32, I=0 is retained-copy verified in
`wizard-20260919T130037515734Z-79eaa1fc12d1488089be0dbf31b17ccb`.
No fresh servo acquisition, movement, reset or gain change occurred. This resolves
the saved-copy gap described below, not the positive-direction motion error.

Latest update: r17 is now installed with verified app readback and one idle startup.
One read-only gain POST reported P=32, D=32, I=0; its retained GET timed out.
The valid POST is exported, but the complete capture workflow remains inconclusive.
No gain writes, recovery or movement occurred. See the gain review for exact
receipt IDs. This supersedes the earlier r16-installed/r17-offline state below.

2026-09-19: the approved direction-only filesystem installation preserved other
settings and credentials. Following the approved startup/recovery/hold sequence,
the elbow moved from 2903 to 2897 and software verified exact arrival. Only then
was the return sent: its goal readback was 2903, but measured position stayed
2897 over the observation window. The sequence stopped without retry or recovery.
This supersedes older "next experiment" statements below; those remain historical.

- Pair evidence: `wizard-20260919T122507527689Z-b52412aa30dc4f5ba55315fd35354bf7`.
- Configuration: `wizard-20260919T122842136476Z-63b26f504d1b4bd78fd7d46921872409`.
- Installed application remains r16; filesystem pair direction is now -6.
- Latest observed goal-position residual is six counts. No automatic recovery
  or silent widening of the existing five-count recovery admission is permitted.
- Next: [read-only gain diagnostics](ELBOW_GAIN_DIAGNOSTIC_REVIEW.md), staged
  offline as r17. Gain readings are not yet available. This investigates the
  direction-dependent response, not a proven PID cause or tip-accuracy correction.
- Firmware installation and any eventual gain changes need separate approval.
  No camera, contact, compensation or ghost typing success is claimed yet.

## Latest hardware checkpoint — approved r16 installation/startup complete

User approved one r16 app-only installation and one startup. The installer verified
controller MAC, r14 predecessor, partition and expected filesystem before its single
write. Full r16 application readback matched SHA-256
`dc8b6f0016d29495ef6403d6a04adcbc192ec45ccd1ede7c390c3d1b4b3ea05e`;
protected regions were unchanged. Exactly one startup reset followed. No retry,
provisioning, recovery preparation or servo command was issued.

- Journal: `private-backups/controller-20260918-session1/app-r16-deployment-events.jsonl`.
- Installation export: `wizard-20260919T114601318571Z-ee8963706ecb49aa9c6327053f2e70e2`.
- Startup export: `wizard-20260919T114601678092Z-14a8c052624c472a82193694b4b7fec4`.
- Boot: `c23f5bdf087bb87f4fa423c1dac183e1`; address `192.168.0.225`.
- Read-only status/capabilities/status agreed: IDLE, NOT_CONFIGURED, zero records,
  no storage fault. NOT_CONFIGURED is the lazy diagnostic state, not missing files.
- Local recovery preflight passed against these receipts; no key extraction,
  recovery-attempt reservation or additional device access in that preflight.

This establishes installation readback and observed idle startup, not a recovered
endpoint or successful movement. Next is the separately approved one-shot supported
recovery workflow; no automatic pair/return follows it.

## Recovery candidate checkpoint — r16 compiled, not installed

The explicit recovery path now has offline host/native admission, listener, board
wiring and export/replay tests. Full r15 compilation exposed a missing generated
include; preserved that failure and corrected it in a separate r16 candidate.
r16 compiled and passed artifact/profile/backup review, with app SHA-256
`dc8b6f0016d29495ef6403d6a04adcbc192ec45ccd1ede7c390c3d1b4b3ea05e`.
See [ELBOW_TRACKING_EXPERIMENT.md](ELBOW_TRACKING_EXPERIMENT.md) for evidence IDs,
scope and remaining launcher/installer work. No deployment or recovery motion has
occurred; installed r14 and historical non-arrival evidence remain unchanged.

## Next experiment plan — explicit recovery, then matched displacement/direction

See [ELBOW_TRACKING_EXPERIMENT.md](ELBOW_TRACKING_EXPERIMENT.md). The plan keeps
arrival/neighbor tolerances unchanged, separates supported recovery admission from
normal testing, and specifies matched +/-6 and conditionally +/-8-count pairs,
finite repetition, per-leg exports and held-out compensation criteria. Eight-count
pairs must fit both sides of the current [2893,2909] envelope; no clipping or
silent envelope expansion. The last observed five-count goal-position gap may
prevent ordinary hold admission, but current r14 position is not yet measured.
No recovery, reset, ordinary hold or pair command was sent while planning.
User approved the proposed one-shot supported recovery on 2026-09-19. Offline
implementation now separates a five-count initial residual ceiling from the
unchanged two-count drift/arrival tolerance. Existing r14 does not implement
separate recovery admission. No recovery command or new deployment has occurred;
Boot-bound admission and labelled recovery export/replay now pass offline native/
host tests. Separate transport/prepared-start integration and candidate build/review
remain; no installed recovery route or live recovery success is claimed. See the
experiment document for exact validation scope and remaining work.

## Latest hardware checkpoint — r14 configuration acquired, deadband registers zero

Receipt-bound local preflight passed, fresh same-boot capabilities matched, and
one read-only servo-14 configuration capture completed. All 12 reads returned the
expected lengths with device error zero. The retained GET matched the POST bytes;
host assessment/export replay passed. No servo writes, motion, reset, provisioning
or setting changes occurred. This boot's configuration capture is consumed.

- Boot: `911e3febd604e41619c0ccc160c29721`.
- Transport export: `wizard-20260919T105744009997Z-e964d2f548a948588adf16033aaaa67f`.
- Configuration export: `wizard-20260919T105743948843Z-86a974e2fd4944019f387ace0da0fda6`.
- Capture interval: 47064058–47068338 us (4280 us total).
- Raw register values: model 3=2057 (bytes 0908); min/max 9=0 / 11=4095;
  CW/CCW deadband 26=0 / 27=0; offset 31=2712 (bytes 980a); mode 33=0;
  torque 40=1; acceleration 41=1; goal speed 46=20; torque limit 48=1000;
  lock 55=1.

These are controller-reported raw values under the pinned SMS_STS register map.
Do not interpret raw model 2057 as a confirmed product identity or raw offset 2712
as an unsigned physical calibration angle. Model/offset encoding and physical unit
scaling remain separate compatibility questions. Zero deadband registers provide
no evidence for a configured five-count deadband; they do not rule out controller
thresholds, friction, load equilibrium, quantization or other dynamics.

Combined with the r13 trace, requested/encoded/readback targets agreed but position
undertracked. No automatic five-count compensation, deadband change, PID tuning or
torque-limit increase is justified by this single sample. The next useful motion
experiment should deliberately vary displacement and direction with fresh start
and endpoint telemetry, retaining residuals rather than relaxing arrival tolerance.
First plan an explicitly authorized supported hold/recovery admission: the last
observed goal-position gap was five counts, beyond the existing two-count initial
tracking guard. Do not automatically resend the failed pair or issue a recovery
move. No r14 hold/pair command has yet been attempted.

## Latest hardware checkpoint — approved r14 installation/startup completed

The explicitly approved one r14 app-only installation and one startup completed.
Controller identity, installed r13 predecessor, partition and settings filesystem
matched before writing. Full application readback matched r14; protected regions
were unchanged. No provisioning, servo command, configuration capture, movement
test or retry was performed. This installation/startup approval is consumed.

- App SHA-256: `83ad71a221168ae59c65fc711f781ba6532a996b9b9d28464647ca19e0441281`.
- Journal: `private-backups/controller-20260918-session1/app-r14-deployment-events.jsonl`.
- Installation export: `wizard-20260919T105703160637Z-8fbd14b135d64bd9b38b0a27e37dd285`.
- Startup export: `wizard-20260919T105703530086Z-0f34041b4c33482b995b4e927058f4d1`.
- Boot: `911e3febd604e41619c0ccc160c29721`; address `192.168.0.225`.

Read-only status/capabilities/status agree: IDLE, zero records, no storage fault,
hold-first-pair protocol available. NOT_CONFIGURED denotes the lazy hold runtime,
not missing files. Next use the receipt-bound configuration collector to read the
fixed servo-14 register set; no values have yet been acquired on r14. This result
supersedes the historical pending-r14-approval notes below. Failed r13 pair
evidence remains retained; do not replay its commands on this new boot.

## Host collector protocol checks — no hardware access

Twenty-three configuration tests passed, including the actual bounded HTTP
exchange over inert sockets for POST and GET: exact fixed paths, empty request
body, one connection/send, truncation, non-200 status, oversized/duplicate length,
encoded response rejection, total deadline exhaustion and guaranteed socket close.
No failure retries the capture. These tests did not use the network.

Added `scripts/capture_r14_configuration.py`: accepts an explicit saved r14 startup
export, checks its completed installation linkage and consistent boot, supports
local-only preflight, and checks current same-boot capabilities before the one-shot
read-only acquisition. It has no installation, configuration-write or motion path.
Its CLI loads successfully; live preflight cannot complete until the approved r14
installation/startup produces the required receipts. The r14 journal is absent.
Deployment still awaits separate approval. Do not substitute r13 startup receipts.

## Pending approval — r14 app-only installation and one startup

Explicit r13-to-r14 installer edge and revision-specific completed-installation
receipt binding are ready; read-only startup observer accepts r14. Thirty-eight
installer/evidence tests passed. Actual local preflight verified:

- r14 SHA-256 `83ad71a221168ae59c65fc711f781ba6532a996b9b9d28464647ca19e0441281`,
  1106528 bytes at the existing app offset 0x10000.
- Required r13 predecessor `4503aaa00409624ebc0a54876c45eec5af684a6717327046d34a5e7c644b9a6e`.
- Preserved filesystem `a5ca3cc090277da8952fec21ebc1b84d692819515fb9a9a3550c56539b7a4096`.
- No journal reserved, device access, deployment or startup during preflight.

Host `elbow_configuration_capture.py` reserves one capture per expected boot,
sends one bounded fixed-route POST, validates its response, retrieves the retained
result once, and requires exact byte equality before configuration export/replay.
Errors remain INCONCLUSIVE and preserve consumed claims. There is no retry,
fallback endpoint, motion command or settings write. Eight configuration tests
passed, including lost POST/GET responses, wrong boot, malformed/changed data and
duplicate-call rejection. Socket protocol tests and the installed-receipt-bound
CLI collector remain to be completed before live acquisition.

Request approval for **one r14 app-only installation and one startup**. Preserve
all settings/credentials; no provisioning, movement or configuration acquisition
in that installation procedure. Startup is a real controller reset; keep the arm
supported and clear. r13 approvals are consumed and do not authorize r14. After
installation, verify fresh startup identity and complete collector checks before
the read-only configuration acquisition. Do not resume the failed pair.

## r14 route integration — staged offline, not installed

Added `/rocell/elbow-configuration/capture` (explicit POST with no parameters)
and `/rocell/elbow-configuration/result` (GET retained result only). One admitted
capture per boot; unsuccessful acquisition also consumes it. No automatic capture
at startup. GET never accesses the bus. Both successful and partial records use
the independently validated configuration schema; HTTP 200 alone is not success.

Board integration denies acquisition during hold/pair exclusive work or hold
sampling, and permits only pair New/Complete/Fault (not awaiting return). The
existing single-threaded diagnostic web owner serializes the callback with motion.
Acquisition never retires hold, clears pair archives, changes torque, or rearms
either motion workflow. Fixed retained buffers avoid a large callback stack frame.

Five acquisition/serialization/route tests and three existing network-operation/
lifecycle/route tests passed. Route tests exercise denied active access, unwanted
parameters, duplicate capture, failure at every register and bus-free result reads.
Offline r14 staging changed two existing headers and added three configuration
headers; 94 predecessor sources remain unchanged. Staging export:
`wizard-20260919T041359060661Z-db255d20cb4e4b7d8501a0aa8d8531e1`.
Compilation and candidate/recovery review succeeded:

- Compile: `wizard-20260919T041541114321Z-30322c77b1374066ae0eb93579c5ed96`.
- Review: `wizard-20260919T041556699854Z-bcd5e94f20c3470c84479dcbf941d91e`.
- App SHA-256: `83ad71a221168ae59c65fc711f781ba6532a996b9b9d28464647ca19e0441281`.
- Slot headroom 204192 bytes; partition and bootloader unchanged; recovery verified.
- 80 inspected individual stack frames, largest 432 bytes (not total-stack proof).

Next implement the host one-shot capture/retained-result collector and exact r13
to r14 installer edge, then request separate app-only installation/startup approval.
No device access, firmware deployment, provisioning or movement in this checkpoint.

## Configuration evidence format and independent host replay — offline verified

Added bounded native `elbow_configuration_json.h` serialization, plus host
`elbow_configuration_review.py` validation/export/replay. Records bind boot,
capture ID, reference profile, byte order, completeness and exact ordered register
reads. The host checks sequence, widths, returned length, device error, timestamps
and canonical raw bytes before exposing a complete raw register-value map. Failed
or partial captures report INCONCLUSIVE with no configuration-value map; missing
values are never presented as zero. Compatibility, scaling and tuning authority
remain explicitly unverified/false.

The integration test compiles the native emitter and independently parses its
successful capture plus a short-read failure at each of the 12 registers. Every
case is exported and replayed. Mutated boot/address/length/error/time/sequence and
missing reads are rejected. Tiny-buffer serialization fails without partial JSON.
Four native/host tests passed (3.76 s); nothing installed or read from hardware.

Next wire the fixed acquisition into the diagnostic board's idle/stopped bus
ownership path, with one explicit capture and retained-result reads, without
clearing hold/pair evidence or rearming motion. Then compile and review before
requesting approval to deploy the new read-only capability.

## Read-only configuration acquisition — local implementation

Added `firmware/diagnostics/elbow_configuration_snapshot.h`: a single-use, fixed
servo-14 reader for model (3), min/max limits (9/11), CW/CCW deadband (26/27),
offset (31), mode (33), torque (40), acceleration (41), goal speed (46), torque
limit (48), and lock state (55), using pinned SMS_STS register widths. It records
each read's address, width, returned length, error and timestamps; no arbitrary
register input, decoding assumptions, configuration write or motion method.

The caller must supply an exclusive inactive-bus predicate, checked before every
read and after the sequence. Reads are bounded to 50 ms each / 500 ms total;
invalid byte order, clock, response length, servo error or ownership fails the
capture, with no retry. Failed payloads are cleared and remain explicitly invalid.
The snapshot never releases torque or rearms a stopped trial.

Native tests use a bus type with only Read (no write/reset API) and cover success,
short reads and servo errors at every register, repeated acquisition rejection,
inactive-bus denial, overlong acquisition, clock overflow and byte-order rejection.
The three snapshot/hold native test programs passed. This is not installed or
routed and does not establish actual servo configuration values.

Next add bounded serialization and independent host validation/export replay,
then wire acquisition only into an explicit idle/stopped read-only diagnostic.
Keep the current hold/pair archives intact. Build/review the combined candidate
before requesting separate deployment/startup approval; no hardware action yet.

## Local correction — preserve terminal cause; read-only route gap confirmed

A native authenticated-runtime regression reproduced the reason overwrite: an
acknowledged but untracked forward goal terminated as LEG_NOT_ARRIVED, then cleanup
replaced that reason. `HeldPairAuthenticatedRuntime::stop` now preserves the first
runtime/leg terminal failure. Repeated cleanup does not issue reads/writes or
change the retained record count. The test failed before the correction; all three
direct/socket/powered authenticated-runtime test variants passed afterward
(60.35 s), including signed hold, forward and return workflows. This change is
LOCAL ONLY; installed r13 and its recorded historical labels remain unchanged.

Inspection of the exact r13 diagnostic boot and registered routes confirms there
is no general register-read or deadband route, and no legacy serial command parser
in its active loop. Existing record endpoints return archived acquisitions, not
new configuration reads. Do not probe invented endpoints or send legacy commands.

Next implementation: a bounded, read-only servo-14 configuration snapshot with a
fixed reviewed register allowlist (including model, limits, CW/CCW deadband,
offset, mode, torque state and torque limit), acquisition timestamps, response
length/error checks, and reproducible host exports. Exclude all write/unlock/reset
operations. Require idle/stopped bus ownership and preserve current trial evidence;
do not rearm motion. Test failure cases and integration offline, then stage/review
an app-only candidate and obtain separate installation/startup approval. Existing
r13 approval does not authorize that deployment. Configuration readings are needed
to narrow the tracking hypothesis, not permission to auto-tune servo settings.

## Offline investigation — tracking evidence and misleading outer stop label

`scripts/review_r13_forward_tracking.py` replays the verified forward archive and
exports all 21 elbow samples with position, moving, speed, load, current and raw
voltage/temperature. Export:
`wizard-20260919T040511134235Z-d7372c658368429b8d3efbab4302e2d2`.
Decoder source is hash-bound to the retained SMS_STS.cpp. Values below are library
units/raw bytes, not calibrated torque, current, temperature or tool-tip motion.

- Baseline load/current: 0/0. After command, load was -49 then -53 while position
  stayed 2901; after position changed to 2902, load stayed -45 and current was 1–2.
- Speed read zero in every sampled frame. This does not exclude motion between
  samples. Raw voltage/temperature stayed 121/27.
- Goal changed to 2907 and load/current changed after the acknowledged command.
  This supports actuator response rather than an entirely missing command, but
  does not establish the cause of the residual or justify compensation.

The stop label has an identifiable software path: a NOT_ARRIVED leg sets the pair
to Stopped with LEG_NOT_ARRIVED; the listener exposes Fault; network lifecycle
cleanup calls runtime.interference(), overwriting the outer reason with
PAIR_EXTERNAL_INTERFERENCE. The immutable leg terminal still records non-arrival.
Preserve the first terminal reason in a future reviewed runtime correction; do
not interpret the cleanup label as evidence of physical interference.

Pinned SMS_STS.h defines CW/CCW deadband at registers 26/27. These registers were
NOT included in the captured scan and their installed values remain unknown.
Next useful diagnostic is a reviewed read-only snapshot of deadband/control
configuration and comparison with the measured small-step response, followed by
a separately admitted experiment. Do not invent those values, broaden an existing
route to arbitrary writes, reset a stopped trial automatically, or infer a global
five-count correction. No hardware I/O or configuration change in this review.

## Latest hardware checkpoint — r13 forward non-arrival, return withheld

`scripts/run_reviewed_r13_pair.py` binds the exact installation, settings, hold
preparation, boot and private-image hash; exports the actual admission basis and
same-boot completed hold before loading the key. Local preflight passed. The
standing bounded-test authorization was used for one finite pair attempt.

- Trial: `wizard-20260919T040312387144Z-1aa5140b12c942cf84af736a1539d497`.
- Admission: `wizard-20260919T040304445956Z-6620e4d0e18f4c438c8cc284bfd12065`.
- Forward observation: `wizard-20260919T040312216715Z-0275b1d6e250462abc207ceedd218a9a`.
- One acknowledged write: target 2907, payload `015b0b00001400`, ACK return 1,
  device error 0, command interval 322330646–322331065 us.
- First and final target readback: 2907. Start position: 2901. Final: 2902.
- 21 complete snapshots; final feedback about 2.03 s after ACK; signed error -5
  counts, outside tolerance 2. Assessment `CONTROLLER_REPORTED_NON_ARRIVAL`.
- First postwrite sample at about 104 ms: position 2901, moving 1. Moving cleared
  by about 217 ms. Position first read 2902 at about 556 ms and remained there
  through the final sample. This is not an immediate-collection failure.
- Leg terminal: `NOT_ARRIVED / LEG_NOT_ARRIVED`. Outer status: `STOPPED /
  PAIR_EXTERNAL_INTERFERENCE`; that outer label is not evidence a person intervened.

The requested/encoded/readback targets agree; observed displacement was only one
count for a six-count requested change. This narrows the discrepancy to tracking
or feedback behavior rather than a demonstrated target-encoding mismatch, but one
trial cannot establish deadband, friction, load, calibration or a compensation rule.
The return was correctly withheld. No retry, reset, recovery move, firmware or
servo-setting change followed. The current pair claim is consumed.

Next inspect the retained controller/servo implementation and available read-only
configuration evidence to explain the small-step behavior and outer stop label.
Do not widen tolerance just to pass, apply a five-count offset from this single
sample, or reuse the consumed trial. Any further startup/configuration change
requires its own approval; preserve this non-arrival as learning evidence.

## Pair execution preparation — correct image identity and observation timing

The trusted wizard binding can now identify the selected reviewed r13 image
instead of always labeling the trial r10. Unknown images and admission receipts
for a different image are rejected before key access. Twenty-nine wizard and
installation-evidence tests passed after this change.

Code review found that the pair runner collected immediately after delivery,
although its collector deliberately rejects active captures. This could turn a
valid in-progress leg into an inconclusive stop. The runner now waits once after
accepted delivery before collection: two native deadline budgets (prewrite and
postwrite), maximum observation gap, and a one-second publication margin. For the
installed policy this is 5.5 seconds per leg. Cancellation is checked before and
after the wait. Uncertain delivery never waits or advances, and this adds no
command retry or repeated polling until success. Invalid or over-30-second wait
budgets are rejected before trial reservation. Thirty-one trial/wizard tests pass,
including wait ordering, cancellation during the wait, and no return after a
failed or inconclusive forward endpoint.

No pair command has been sent. The r13 verified hold and prepared targets below
remain the source evidence. Next provide the concrete host admission/key-loading
launcher using these receipts and the existing standing bounded-test authorization,
then run the finite pair; do not substitute a synthetic approving reader or claim
that a local receipt establishes current physical position.

## Latest hardware checkpoint — r13 hold verified from fresh telemetry

After binding the launcher to the exact r13 installation/startup receipts, local
preflight and 29 receipt/installation tests passed. Under the standing bounded
testing authorization, one hold attempt completed on boot
`6bc1df9e5ac164fd009bcb40bf95d1fd`. No reset, provisioning, retry or travel move.

- Observation: `wizard-20260919T035853243817Z-40cd5ce173674899aef3caf769e802f5`.
- Assessment: `CONTROLLER_REPORTED_HOLD_VERIFIED`; export replay verified.
- Requested and encoded target, first and settled goal, start and settled position:
  all 2901 servo counts. Settled error and displacement both zero.
- One acknowledged action (404 us), five complete snapshots. Final observation
  225736 us after the command; stationary checks passed.
- Torque remained enabled; no explicit enable. Six other joints retained their
  positions, goals and torque states.

This demonstrates a settled hold with the timing correction, not motion between
different endpoints, direct wire measurement or physical stylus-tip accuracy.
The old early-busy failure did not recur in this single trial; do not infer broad
reliability or a universal settling time from one sample.

Offline forward/return preparation now replays from this real hold:
`wizard-20260919T035918294015Z-ca28470911a0407289605b59a400cbe6`, SHA-256
`b6a24a109938953e39a1161a75bf43ba7d71139f1b56834ef48e08706f30ec20`.
Targets: 2907 then 2901 counts, tolerance 2, matching installed pair settings.
No pair command sent yet. Next integrate the r13 installation binding into the
pair runner (the existing wizard preview still identifies r10), verify fresh
same-boot handoff and capability, then execute the finite pair with per-leg
endpoint/export checks. Stop on uncertainty; no automatic return after failure.

## Latest hardware checkpoint — approved r13 installation and startup completed

One explicitly approved r13 app-only installation and one startup completed.
The installer verified the controller MAC, installed r12 predecessor, partition
table and retained settings filesystem before writing. Full application readback
matched r13 and protected regions were unchanged. No provisioning, servo command,
movement test or retry was performed. This installation/startup approval is consumed.

- Installed SHA-256: `4503aaa00409624ebc0a54876c45eec5af684a6717327046d34a5e7c644b9a6e`.
- Journal: `private-backups/controller-20260918-session1/app-r13-deployment-events.jsonl`.
- Installation export: `wizard-20260919T035748449922Z-907529c651924599a539acfb3f810c5f`.
- Startup export: `wizard-20260919T035748835373Z-133bb218dcdd40018e2b609d220e54b3`.
- Boot: `6bc1df9e5ac164fd009bcb40bf95d1fd`; address: `192.168.0.225`.

Read-only status/capabilities/status agree: IDLE, zero records, no storage fault,
hold-first-pair protocol available. NOT_CONFIGURED is the lazy hold-runtime state,
not a diagnosis of absent settings. Startup reachability is confirmed; hardware
settling and endpoints remain untested on r13. Next bind the hold workflow to these
exact receipts and this fresh boot before a separate bounded hold/movement trial.
The historical pending-approval section below is superseded by this completion.

## Pending approval — r13 app-only installation and one startup

The explicit r12-to-r13 installer edge, revision-specific journal/receipt binding,
and read-only startup observer are implemented. Thirty-five offline installer and
installation-evidence tests passed, including cross-revision rejection, preserved
pair settings, consumed-journal rejection and no device-library import during
preflight. Full candidate-review receipt binding is tested for r10 through r13;
these receipts explicitly do not assert current health or authorize movement.
The r13 deployment journal remains absent. Actual local artifact preflight
returned `LOCAL_PREFLIGHT_VERIFIED`:

- r13 app: 1104048 bytes, SHA-256
  `4503aaa00409624ebc0a54876c45eec5af684a6717327046d34a5e7c644b9a6e`.
- Required predecessor: r12,
  `81227435b8d6b3e36da8e43cd06e88b7d5872e6fc6566eb8d0a5b9a69d7da41d`.
- Preserved filesystem:
  `a5ca3cc090277da8952fec21ebc1b84d692819515fb9a9a3550c56539b7a4096`.
- No journal reserved, hardware accessed, firmware uploaded or startup performed.

Request separate approval for **one r13 app-only installation and one startup**.
Scope: the reviewed postwrite observation dwell only; preserve settings and
credentials; no provisioning, servo-configuration change or movement test in the
installation procedure. Keep the arm supported and area clear: startup is a real
controller reset, not a guarantee that powered actuators cannot move. The installer
checks the actual device predecessor/partition/filesystem before writing, verifies
application readback and unchanged protected regions, and does not retry failures.
After successful installation, collect read-only startup evidence before binding
any later hold test to its new boot. Do not reuse the consumed r12 hold attempt.

## Offline checkpoint — rapid-poll settling and export replay

Native publisher tests now poll every 10 ms while a simulated powered elbow's
moving flag remains active for 100 ms after its single hold write. The first
postwrite scan is asserted to begin no earlier than 100 ms after the ACK. A flag
that clears produces a verified simulated hold; a persistent flag produces
INCONCLUSIVE evidence and stops without another write or torque-enable operation.
Both outcomes pass independent host assessment and durable export/replay.

The focused snapshot, publisher, real-library wire, host model and authenticated
pair-runtime suite passed: 27 tests in 67.83 seconds. These are simulation results,
not evidence that the physical servo clears its moving flag within 100 ms.

Immutable r13 staging changes only `hold_initialization_owner.h` from the reviewed
r12 source; 95 other source files remain unchanged. Staging export:
`wizard-20260919T030838930527Z-5ad90092fbbf4e18a2305a683be77d9c`.
The offline firmware build and candidate/recovery review completed successfully:

- Compile: `wizard-20260919T031028594578Z-700a0b7e52de427495497de6fbf3d9f6`.
- Review: `wizard-20260919T031040134363Z-d30ef69cb3924c718e1206385bd04545`.
- App SHA-256: `4503aaa00409624ebc0a54876c45eec5af684a6717327046d34a5e7c644b9a6e`.
- Application slot headroom: 206672 bytes; partition/bootloader hashes unchanged.
- Original backup pair, original recovery app and retained r7 app matched.
- Largest reviewed individual stack frame: 432 bytes, NOT a total stack bound.

No device access, restart, provisioning or motion was performed for this checkpoint.
Next: add and test the explicit r12-to-r13 app-only installer edge and receipt
bindings, then request separate r13 installation/startup approval. The existing
r12 approval is consumed and does not authorize r13. Candidate review alone is
not deployment admission or evidence of successful physical settling.

## Latest hardware checkpoint — r12 hold ACK and matching count readback

One fresh r12 hold request was sent after exact installation/startup/profile
preflight. Three complete stable baseline/prewrite scans passed, including the
already-powered elbow state. The controller then issued one acknowledged hold
write. It stopped during the first postwrite scan with
`HOLD_POSE_OR_CONTROL_INVALID`; no resend, reset, release, enable, forward move or
return move followed. The boot's hold attempt is now consumed/faulted.

- Observation: `wizard-20260919T030150836498Z-15dae39c28aa4879895890bd7b9914d5`.
- Transport: `wizard-20260919T030150763910Z-746eed4701854ccfac674f73f7270940`.
- Servo 14 target: 2901 counts; encoded payload: `01550b00001400`.
- ACK: library return 1, error 0; finished at 62998002 us.
- Fresh feedback began at 63012888 us (14886 us after ACK), finished 63013630 us.
- Target register and position both read 2901; torque 1, mode 0, moving flag 1.
- All six other joints retained their baseline position, goal, mode and torque;
  moving flags remained zero. Four complete scans and one action were exported.

This proves controller-reported acknowledged command and matching fresh target/
position counts, NOT settled arrival or physical movement. Position was already
2901 before the hold; no displacement claim is made. The endpoint remains
INCONCLUSIVE because stationary completion was not observed. A transient busy
flag is plausible, but later clearing is not established by this capture.

Local scheduling correction: ReadHold/ReadEnable now wait the existing policy's
settle_us (100000 us) after ACK before taking the first stationary scan. This is
one scheduled observation, not repeated reads until success, and does not change
limits or tolerate motion in a collected scan. Deadline, observation-gap, drift,
neighbor, read validity and stationary requirements remain. Tests first reproduced
the 15 ms immediate-observation failure, then passed after correction; they also
prove a flag still ON after the dwell faults without another write or enable.
Twenty-four targeted native/model/publisher/wire tests passed. The correction is
LOCAL ONLY; r12 is unchanged. Next: integrated runtime timing tests, reviewed
candidate build, and separate installation/startup approval before a new live
attempt. Do not claim 100 ms sufficient on hardware until a future capture proves it.

## Latest hardware checkpoint — approved r12 app-only installation completed

The user explicitly approved one r12 app-only installation and one startup.
The installer verified controller identity, exact r11 predecessor and current
pair-settings filesystem; wrote the reviewed application once; independently
verified full application readback and unchanged protected regions; then performed
one startup. Settings/credentials were preserved. No provisioning, movement,
servo-configuration change or automatic retry occurred. This approval is consumed.

- Installed app: `81227435b8d6b3e36da8e43cd06e88b7d5872e6fc6566eb8d0a5b9a69d7da41d`.
- Journal: `private-backups/controller-20260918-session1/app-r12-deployment-events.jsonl`.
- Installation export: `wizard-20260919T030050848279Z-c2c8420664584c10a97993072a3ffc0d`.
- Startup export: `wizard-20260919T030051107264Z-0f89c5116c0d4b09bc3c32524bd6e04f`.
- New boot: `39d9f96926e24a3d35d6889d2c9509d3`; address `192.168.0.225`.

Read-only status/capabilities/status observations agree: IDLE, zero records, no
storage fault, hold-first-pair protocol available. NOT_CONFIGURED is the lazy hold
runtime state, not proof of a missing settings file. Startup is verified reachable;
powered-hold and movement on r12 remain untested. Twenty-nine targeted installer
and installation-evidence tests passed, including rejection of cross-revision
journals. Next: bind the fresh hold to these r12 receipts, assess telemetry, then
advance to the bounded pair only on a verified hold. No old boot claim is reusable.
Historical pending-r12 deployment approval below is superseded by this result.

## Latest offline checkpoint — r12 powered-hold candidate ready for approval

The already-enabled path now has native publisher-to-host endpoint/export replay
coverage: retained goal 2724, measured hold target 2723, one position write, no
explicit enable, torque staying on, and matching first/settled target readbacks.
The actual pinned servo-library emulator confirms wire bytes match action records.
A signed native hold/forward/return test using real HMAC and a synthetic bus also
passed starting with elbow torque already enabled. These are software simulations,
not additional physical movements or measured stylus accuracy.

Validation: 24 publisher/model/wire tests passed; a focused suite of 44 tests
passed; the additional powered-start signed pair case passed (2 other cases
deselected); 17 installer tests passed. Existing disabled-start behavior remains
covered, and the new path rejects initial tracking mismatch and unexpected torque
loss without automatically re-enabling. No compensation was added.

r12 is staged from hash-verified r11 sources with only
`hold_initialization_owner.h` changed; 95 firmware files remain identical.

- Stage: `wizard-20260919T025401760501Z-9e8cd751e95a4ae1885db7a73e01c5e1`.
- Compile: `wizard-20260919T025548595225Z-0bd78758280d4d598f4fd9a25e4bc443`.
- Review: `wizard-20260919T025602273432Z-9146856eb72d43a59ff831b8d67b2254`.
- App SHA-256: `81227435b8d6b3e36da8e43cd06e88b7d5872e6fc6566eb8d0a5b9a69d7da41d`.
- Size: 1103920 bytes; slot headroom: 206800 bytes.
- Existing partition/bootloader profiles and recovery backups verified.
- Largest reviewed individual static frame: 432 bytes (not total-stack proof).

The local-only revision-12 installer preflight passed, requiring the exact r11
predecessor and current pair-settings filesystem. No port was opened and no
deployment journal was reserved. Next requires separate approval for ONE r12
app-only installation and ONE startup, preserving settings/credentials and
excluding movement from installation. Do not reuse the faulted r11 hold attempt.

## Latest hardware checkpoint — complete r11 baseline, powered-hold assumption

One fresh hold request on boot `76c002985bcf308b43c7dbd486ba72aa` was accepted.
The complete 28-read baseline was captured successfully (`HOLD_STATE_CAPTURED`),
then the owner stopped with `HOLD_EXPECTED_DISABLED_ELBOW`. The terminal reports
one snapshot and zero servo actions. No retry, reset, torque release, forward move
or return move followed. This confirms a complete scan on r11, not endpoint arrival.

- Observation: `wizard-20260919T025035567506Z-29c9f4fbcbf7449babc14b80057927e6`.
- Transport: `wizard-20260919T025035516833Z-98d25b5a6f234341a0010ebdf7a9fc2a`.
- Fresh elbow target register: 2902 counts; position: 2901 counts; mode: 0;
  torque: 1. All four reads returned the required bytes with error zero.

The disabled-only initialization assumption does not match retained servo power
across controller-only restarts. Local firmware/model now allow an already-enabled
elbow only when its initial goal/position are within the unchanged drift tolerance.
Two stable baselines and the fresh prewrite scan are still required; the one hold
targets the freshly measured position. No torque-off command was added, and an
unexpected torque loss after an enabled baseline cannot trigger an enable command.
The existing disabled-baseline optional-enable path remains intact.

Twenty-three targeted native/model/servo-wire tests passed, including already-on
success without an enable command, initial tracking mismatch rejection, and
unexpected torque-loss rejection. These changes are LOCAL ONLY; installed r11
remains unchanged and its latest hold attempt is consumed/faulted. Next: finish
integrated replay coverage for the powered-hold path, stage/review its application
candidate, and obtain separate deployment/startup approval. Do not reset or disable
the physical arm just to satisfy the old precondition.

The r10-named host launcher/evidence reader now accepts an explicit reviewed r11
profile and verifies the r11 startup-to-installation link. It does not substitute
the prior boot or its authorization. Twenty-four evidence tests and the actual
local r11 preflight passed before this attempt.

## Latest hardware checkpoint — approved r11 installation completed

The user approved one r11 app-only installation and one startup. The one-use
installer verified controller identity, the exact r10 predecessor and current
pair-settings filesystem, wrote r11 once, independently read the application back,
and verified protected regions unchanged before performing one startup. No
filesystem provisioning, servo-configuration change or movement command occurred.
The installer connection now uses one attempt rather than two; failures are not
automatically retried. The installation approval is consumed, not reusable.

- Installed image: `52979050aa4fabbe167f01fc1bb7b656105cb370d54f3dd9890c5f6703682b52`.
- Preserved filesystem: `a5ca3cc090277da8952fec21ebc1b84d692819515fb9a9a3550c56539b7a4096`.
- Journal: `private-backups/controller-20260918-session1/app-r11-deployment-events.jsonl`.
- Installation export: `wizard-20260919T024912245155Z-b48db070130f404f9bf945151cc774e0`.
- Read-only startup export: `wizard-20260919T024912549021Z-39ed12903fe04c10bd0731ed6b19b4f4`.
- New boot: `76c002985bcf308b43c7dbd486ba72aa`; Wi-Fi `192.168.0.225`.

Status/capabilities/status reads agree on the new boot and IDLE state, zero records,
no storage fault, and the available hold-first-pair protocol. `NOT_CONFIGURED`
describes the lazy hold runtime, not missing persisted settings. This verifies
startup reachability, not motion, pair-settings runtime loading or tip accuracy.
Forty targeted installer/evidence tests passed. The r10 records remain historical
and may not authorize this boot. Next: bind a fresh hold to the r11 installation
and startup receipts, assess its baseline/hold records, then prepare the bounded
forward/return pair only if the fresh hold is verified. No new movement was part
of this installation turn. Historical pending-r11 approval notes below are superseded.

## Latest offline checkpoint — r11 quantized-clock correction

Audited adjacent read boundaries independently of command/snapshot timing gates.
The same microsecond-equality defect existed in target/feedback acquisition and
at the position-to-control scan boundary. Local firmware now permits equality
between synchronous adjacent reads while rejecting time reversal. Host snapshot,
control-state and acquisition-pair validation follow the same distinction.
Command freshness, baseline spacing, settling dwell and inter-snapshot progression
checks remain unchanged. Sequence, byte-count, error, identity and age checks remain.

Regression coverage includes a full 28-read native snapshot with equal adjacent
boundaries and reversal failures at target/feedback, joint, and scan-type boundaries.
Host tests reject invalid bytes, incorrect sequences, backward timestamps and
reads not strictly after the command boundary. Nineteen native/host tests passed;
32 additional targeted acquisition/quantization tests passed. The broader selected
hold/held-pair/servo-evidence regression completed: 736 passed, 20840 deselected
in 923.90 seconds. This is offline software evidence, not a successful live move.

An offline r11 candidate was staged from hash-verified immutable r10 inputs,
changing exactly `servo_control_state_read.h`, `servo_evidence.h`, and
`hold_state_snapshot.h`; 93 files remain identical. Existing r10 artifacts were
not overwritten. Build and review succeeded:

- Stage: `wizard-20260919T022913131527Z-aa1ba8093cc04bba9fabad031258c4e1`.
- Compile: `wizard-20260919T023057492784Z-505d17097d1848248a31226581d8b2f2`.
- Review: `wizard-20260919T023155403856Z-39819880642a4b73ac23ab5198c64b15`.
- App SHA-256: `52979050aa4fabbe167f01fc1bb7b656105cb370d54f3dd9890c5f6703682b52`.
- App size: 1103872 bytes; slot headroom: 206848 bytes.
- Existing partition/bootloader profiles and recovery evidence verified.
- Largest reviewed individual static frame: 432 bytes, not a total-stack proof.

No firmware was uploaded, no filesystem was provisioned, and no reset or movement
was performed during this offline correction. Deployment needs separate approval.
The r10 hardware boot remains faulted/consumed; it must not be reused for a pair.
The installer is now bound to the current pair-settings filesystem (not the
pre-pair r7 filesystem), exact r10 predecessor and r11 candidate. Sixteen installer
tests passed, and the actual local-only `--revision 11 --preflight-only` passed:
candidate `52979050...3682b52`, predecessor `b07fd9a4...ef9389d`, filesystem
`a5ca3cc0...7a4096`. No serial import/access, journal reservation or startup occurred.
Approval is still required for one r11 app-only installation and one startup;
that scope preserves filesystem settings/credentials and excludes movement.
After an approved installation, observe the new boot, then explicitly bind the
fresh hold and pair workflow to its receipts; never reuse the consumed r10 boot.

## Latest hardware checkpoint — r10 hold stopped before any servo action

After verified pair provisioning, `scripts/run_hold_r10.py` replayed the exact r10
installation, filesystem plan/write/run receipts, startup raw responses, private
candidate/recovery hashes and retained hold policy. The live runner checked the
current boot before consuming its one-use hold claim. One hold request was
accepted; no reset, provisioning, resend or recovery movement followed.

The baseline stopped with `CONTROL_READ_INVALID` and controller-reported
`action_count: 0`. Endpoint assessment remains INCONCLUSIVE, not verified arrival
or verified non-arrival. The generic assessment says incomplete capture, while
the retained transport itself is complete and stable and contains the explicit
FAULT records. Do not confuse accepted delivery with a servo action.

- Hold observation: `wizard-20260919T022349333522Z-14184022c8794b148373ee0472feee81`.
- Raw transport: `wizard-20260919T022349264443Z-a35770140cab466ba6640bc3c2af2010`.
- Offline fault review: `wizard-20260919T022615253995Z-304b06d4fef84278aef46b31232d5be9`.
- Servo 15, register 33 returned one byte with device error zero. Its read started
  at 181846942 us, exactly the preceding read's finish; it finished at 181847272 us.
  The installed control-read predicate requires `start > previous_finish` and
  therefore rejects this valid adjacent clock boundary. The firmware discarded
  the raw byte on rejection; do not reconstruct or claim its value.

An offline native test reproduced the equality failure before the fix. The local
`servo_control_state_read.h` correction permits equal adjacent timestamps for
sequential synchronous reads, retaining reversal, duration, result and error
checks. The same test rejects a one-microsecond reversal and prohibits retry.
Twenty-four targeted tests passed after correction. The deployed r10 source/image
is untouched, and the hardware remains on the consumed, faulted boot.

Next: audit equivalent adjacency rules in `servo_evidence.h`,
`hold_state_snapshot.h`, `hold_record_replay.py`, and
`servo_control_state_assessment.py`; distinguish adjacent read boundaries from
intentional inter-snapshot dwell and post-command freshness. Add quantized-clock
regressions, keep invalid-feedback rejection, and make fault reporting expose the
specific captured reason without claiming endpoint success. Then prepare/review
a corrected application candidate and obtain separate deployment/startup approval.
Do not reset the current boot or bypass its fault to attempt the pair.

## Current authorized operation — preserving r10 pair settings

The user approved adding the pair-settings file and one startup, preserving all
existing settings and credentials. This supersedes the historical pending-approval
notes below. External power remains on under the previously approved r10 route.
No movement, servo-configuration changes or application rewrite is included.

`scripts/provision_pair_r10.py` provides local-only preflight and explicit live
execution. The native r10 parsers accepted the candidate; remount comparison
verified all six existing entries unchanged. Only `/rocell-pair.json` is added:
forward ID `r10-elbow-forward`, return ID `r10-elbow-return`, offset 6 counts,
tolerance 2 counts. These settings do not themselves start motion.

- Source filesystem: `4524696545583513b283348789b2e1f92ed37e178efcb10edf32dcbd639ec4bf`.
- Candidate filesystem: `a5ca3cc090277da8952fec21ebc1b84d692819515fb9a9a3550c56539b7a4096`.
- Plan export: `wizard-20260919T020745879558Z-a941c6791dfb47ffaa767ad02ffd49f7`.
- Completed: full flash readback matched the candidate, all flash outside the
  filesystem region remained unchanged, and the verified result was exported
  before exactly one startup. No servo commands were sent.
- Verified-write export: `wizard-20260919T022043593829Z-2486264d58b2411dac6d1039f6070aa7`.
- Completed-run export: `wizard-20260919T022043752542Z-414620623d6147db83e49a2f48894baa`.
- Read-only startup export: `wizard-20260919T022051699398Z-4436c2b821ca405588eace24e4acdf96`.
  Wi-Fi at `192.168.0.225` responded on new boot
  `4eaa09b8a66ab0b934de43e587522f4c`, with unchanged IDLE status across
  the capability read, zero records and no storage fault. The pair protocol is
  available. `NOT_CONFIGURED` is the uninitialized hold runtime, not evidence of
  an absent file. Runtime loading of pair settings is not yet tested: that occurs
  later in the hold-first flow, which was deliberately not armed here.
- Ten parser/provisioning regression tests passed (24 unrelated cases deselected).

Startup observation is complete. A future movement trial requires a
fresh same-boot hold and command-correlated forward/return evidence; old-boot hold
results are not reused. Physical stylus accuracy remains unmeasured.

## Latest offline checkpoint — production parser adapter compatibility

Added the bounded offline `validate_pair_provisioning.cpp` adapter for the actual
`NativeProvisioningValidator` contract. It compiles against immutable r10 headers,
uses binary stdin/stdout on Windows, and returns the exact accepted/rejected
protocol. This caught and corrected newline translation that would otherwise
reject valid settings. Differential settings tests now exercise this adapter;
the integrated pair provisioning cases use it instead of a permissive callback.
The obsolete test-only parser executable source was removed.

No controller access, private live-image staging or configuration write occurred.
Pair-settings provisioning approval remains pending; software preparation is not
approval, and the installed r10 application is unchanged.

## Latest offline checkpoint — r10 filesystem execution profile

Added an exact r10-only pair-settings provisioning profile using the existing
one-write/full-readback core and a separate durable journal. It verifies the
controller, r10 image, partition table and source filesystem; privately preserves
the prewrite source; writes only the filesystem region; and checks all other
flash bytes are unchanged. Failures consume the attempt without retry or restore.

The orchestration rebuilds the preserving candidate before execution, records
settings/hold-policy identities, and exports verified readback before any explicitly
authorized startup. No key generation or servo command is included. Tests use
synthetic controllers/images and private test storage, not the live arm or its
credential-bearing images. Real pair-settings provisioning and its required
approval remain outstanding.

## Latest offline checkpoint — preserving pair-settings staging

Added `stage_pair_settings_image` to add only `/rocell-pair.json` to an in-memory
LittleFS copy. It requires exact source-image identity, matching existing hold
configuration, retained valid key, canonical pair settings and native-parser
acceptance. Existing pair settings cause rejection, never overwrite. After remount,
all prior files/directories must remain identical and the new settings must read
back exactly. No new key is generated and no credentials enter the public report.

Twenty-eight synthetic filesystem/staging regression tests passed. This turn used
only synthetic images and credentials: no real private candidate was staged,
no device was accessed, no reset occurred and no provisioning approval was inferred.
The user's requested configuration-write approval is still pending. This prepares
the narrow file addition without expanding the movement or firmware scope.

## Latest hardware checkpoint — r10 installed with external power retained

The user explicitly approved keeping external power on for the r10 update.
One app-only installation and one startup completed. The installer verified the
controller MAC, r7 predecessor and supported-pose filesystem before writing;
full r10 readback matched and protected regions were unchanged. No retry,
provisioning or servo command was issued.

- Installed app: `b07fd9a442bfeb58a9b846828a5b6cedf25441fd9ce322be9f8f72f32ef9389d`.
- Installation evidence: `wizard-20260919T015507346666Z-a50c3d2d86f548268a12c6e267980433`.
- Startup observation: `wizard-20260919T015507996504Z-98cea384126b4bf685225bc82eed68cd`.
- New boot: `377b6215e21e4d1b6305ee8e418c0578`; address `192.168.0.225`.
- Three read-only GETs observed stable IDLE/NOT_CONFIGURED, zero records and no
  storage fault, with the expected hold-first-pair-v1 capability response.
- Reported free internal heap 228,260 bytes, minimum 224,420, largest block
  110,580. These are startup samples, not proof of peak runtime sufficiency.

The r10 installation authorization is consumed. No physical no-motion claim is
inferred from HTTP alone; no servo command was sent by this workflow. Old r7 boot
receipts cannot be reused. The user wants movement tests next, but the separate
pair-settings provisioning approval remains required before changing the retained
filesystem. Prepare that narrow change, then acquire fresh hold evidence and run
the bounded forward/return workflow. Do not reinstall or reset automatically.

## Latest checkpoint — concrete installation journal reader

Added a file-only reader for the exact r10 installer journal and retained r10
candidate review. It rejects incomplete, repeated, stopped, mismatched-controller,
wrong-offset/hash and duplicate-field histories. It exports host-reported flash
verification separately from startup health, current-device identity, pair
configuration and movement permission; those remain unverified. Ten focused
tests pass. There is no r10 deployment journal yet and no r7 fallback.

The exact r7-to-r10 local installer preflight passes. A separate app-only install
and one startup can now be requested without authorizing pair provisioning or
movement. Support the arm before removing external power; use USB only for that
installation. The r10 image is `b07fd9a442bfeb58a9b846828a5b6cedf25441fd9ce322be9f8f72f32ef9389d`,
1,103,808 bytes at `0x10000`. Preserve all other partitions and the currently
provisioned supported-pose filesystem. No automatic retry/recovery on failure.

After separately approved installation: inspect read-only startup/capability
evidence, complete and review pair-settings provisioning, then request its separate
authorization. A fresh powered hold and explicit bounded pair-trial approval are
still required before live forward/return. Concrete configuration/approval readers
remain unfinished; installation alone must not enable the wizard action.

## Latest checkpoint — wizard to persistent native runtime

Added a synthetic end-to-end test that drives the actual wizard action,
admission export, trial bridge, challenge receipts, HMAC authorization, loopback
command delivery, endpoint collection and source-chain replay. Both command bodies
are fed unchanged to one persistent native diagnostic process with a synthetic
servo bus. Its captured hold, forward and return share the same runtime/handoff;
the test no longer reconstructs a fresh runtime between these legs.

Successful evidence shows count changes +6 and -6 with final count 2723 and
continuous endpoints. A telemetry-loss variant stops after forward, with no
return challenge or second motion token. These are synthetic count-space results,
not hardware movement or physical accuracy. Capability and admission observations
are explicit test fixtures; HTTP timing and installed firmware are not validated.
No controller connection, firmware change or live command occurred.

Next remains concrete host readers for retained installation/configuration
evidence and explicit live approval, followed by separately authorized deployment,
configuration and powered trials. The full ghost-keyboard/contact goal is open.

## Latest checkpoint — host-bound wizard pair action

The wizard now exposes a physical-mode `run_held_pair` action, blocked by default
unless its host supplies a typed `HeldPairWizardBinding`. The preview shows exact
forward/return count targets. Browser values cannot supply addresses, keys or
approval. Execution replays the pinned preparation and requires a fresh exact-
subject host receipt covering the reviewed r10 installation, pair configuration,
powered-trial approval, support/clearance and exclusive control. The receipt is
exported/reopened before key loading. A denial or failure consumes the action.
Cancellation/expiry prevents subsequent operations, not already delivered motion.

The result panel lists stage exports and explicitly leaves stylus-tip accuracy
unqualified. Simulation tests exercise the service route and admission failures;
no real admission reader has been attached and no hardware action occurred.
Next: implement the concrete receipt readers from verified deployment/configuration
and explicit trial approval, then exercise the full native synthetic chain through
the wizard before separately authorized deployment and powered testing.

The expanded registry exposed a general-export byte-limit failure. Export
projections now omit form definitions consistently, while retaining action status,
labels, blocking reasons and separate evidence attachments. Live UI forms remain
unchanged; the shared snapshot size limit was not raised.

## Latest checkpoint — bounded pair execution bridge

Added `held_pair_trial.run_admitted_pair` to compose the existing preparation,
capability read, challenge receipts, source-linked signing, one-shot delivery,
endpoint collection and exports. It consumes a per-boot reservation before
network work and saves/reopens stage references before continuing. Return is
requested only after stable arrived forward evidence; uncertainty, cancellation,
non-arrival and export failures stop the sequence without recovery movement.

This is an internal trusted-host bridge, not a browser authorization endpoint.
The caller must still establish installed-image/configuration compatibility and
separate powered-trial approval. Tests use inert hardware seams with real durable
exports; they do not prove live motion or complete wizard wiring. Native protocol
integration, trusted wizard admission and separate deployment remain next.
Validation: 17 execution-order/failure tests plus the two existing native
authenticated-runtime integration cases passed (19 total). The new bridge's
hardware-facing seams remain simulated; the native cases independently exercise
the protocol, not the new bridge end to end.

## Latest checkpoint — exact r10 installer preflight

Implemented the r7-to-r10 app-only edge with a separate one-use journal. The
expected filesystem comes from both verified supported-pose replacement receipts
and its retained encrypted image, not the older r6 or original backup filesystem.
Real local preflight passed; fourteen offline installer tests pass. No journal
was reserved, hardware accessed or deployment performed. Live wizard admission
and separately approved deployment/provisioning remain outstanding.

## Latest checkpoint — r10 prepare-path stack reduction (offline)

Moved prepare/parsing scratch into checked temporary heap storage. Allocation
failure stops before filesystem/key access or hold retirement. The r10 compiled
audit's largest relevant individual frame is 432 bytes (r9: 3,808); the pair
parser frame is 320 bytes (r9: 1,328). These are not total-stack or runtime-heap
guarantees. Build and artifact/recovery review passed; no hardware was accessed,
no firmware was installed, and no further hold or motion was commanded.
See `R10_PAIR_RESOURCE_REVIEW.md` for immutable artifact identities and next steps.

## Latest checkpoint — offline candidate/recovery audit

Verified r9 source/binary hashes, app-slot fit, original matching backup pair,
original recovery slot and retained r7 rollback artifact. Added a reproducible
offline review export and `R9_PAIR_DEPLOYMENT_REVIEW.md`. Corrected a static-frame
filter that missed optimized mangled symbols; largest relevant individual frame
is 3,808 bytes, not a total stack bound. No hardware state changed. Resource review,
exact installer preflight/current-filesystem expectations and live wizard admission
remain before requesting separate deployment/provisioning authorization.

## Latest host checkpoint — receipt-linked authorization

Saved challenge receipts now replay through intent/claim/raw-response validation.
A workflow binds confirmed prepare/return receipts to their same-boot source
evidence and authorization contexts before releasing tokens. Native synthetic
integration uses local HTTP receipts for both legs; malformed/uncertain/wrong-
operation receipts cannot progress. No hardware access or installation occurred.
Final candidate/recovery review and explicit live wizard admission remain next.

## Latest wizard checkpoint — paired endpoint review

Added a service-owned offline review action and UI for saved forward/return
evidence. It replays the source chain and displays requested/encoded/read-back
targets, observed count changes/errors and timing without device access or
physical-tip qualification. Native synthetic complete/missing-return exports are
tested through the actual service and JS renderer. Live execution remains
unexposed pending source-linked challenge workflow and candidate/recovery review.

## Latest checkpoint — r9 config validation and capability/resource report

Pair settings are now parsed canonically before key access/hold retirement, with
actual board-callback fault tests. Added a read-only protocol/boot/internal-heap
report and strict host reader without claiming firmware attestation or memory
sufficiency. Twenty-six integration/configuration tests and seven capability tests
pass. Separate r9 app compiled and fits the target slot; verified export
`wizard-20260919T010713961695Z-58d0552f91cd48da8d66d2c3097fb042`.
Installed r7 and filesystem are unchanged. Wizard integration and final candidate/
recovery review remain before separate deployment/provisioning authorization.

## Latest host checkpoint — explicit challenge POST client

Implemented durable one-shot prepare/return-challenge POSTs with bounded replies,
expected-boot checks and result exports. Lost/malformed/redirected replies remain
uncertain and are never retried; post-request export failure consumes the attempt.
Thirty-two focused localhost transport/network tests pass. No arm connection or
firmware change occurred. Capability/resource/configuration review and wizard
workflow integration remain before a live-pair deployment proposal.

## Latest checkpoint — r8 main-sketch integration and full compile

A separate hold-first pair candidate now wires the owner, explicit prepare
callback/routes and diagnostic scheduler into the main sketch. Thirteen focused
integration tests passed. Full default-4MB/no-PSRAM build succeeded; verified
compile export `wizard-20260919T005941057037Z-4ed3536aafcc42e29d34a18e10bfc6f5`.
The 1,101,088-byte app fits the 0x140000 slot, but runtime resource/timing proof
is pending. See the held-pair plan for full hash and memory figures.
No firmware or filesystem installation occurred. Host challenge/capability and
configuration fault tests, wizard integration and resource review remain before
separate deployment/provisioning authorization is requested.

## Latest firmware checkpoint — pair routes and owner scheduling

Added explicit one-use prepare/return-challenge POST routes, bounded status/record
GET routes and a scheduler that excludes web work during either diagnostic owner's
exclusive operation. Native composition tests pass and real ESP32 WebServer
templates compile offline. Candidate main-sketch/configuration wiring, host
challenge POST integration, linked resource checks and wizard presentation remain.
This is not installed firmware functionality; no device action occurred.

## Latest firmware checkpoint — explicit hold-to-pair composition

Added terminal hold retirement into a verified handoff and an allocated pair/
network composition, with configuration/health checks and no automatic challenge
or movement. Old hold memory is freed before allocating the pair graph; failures
do not release torque or retry. Native transition/failure tests and ESP32
compile-only checks cover the new composition. Routes/loop scheduling, linked
candidate resource checks and wizard integration remain. No deployed firmware,
provisioning, servo configuration or physical motion changed at this checkpoint.

## Latest software checkpoint — delivery-gated return authorization

The return signer now requires replayed accepted forward delivery matching the
arrived observation's boot/session/context, with source export ID/hash retained
in a v2 return signing context. Uncertain/rejected delivery blocks token release
even if later telemetry reports arrival. This is enforced below the UI; older
contexts lacking delivery evidence are not silently upgraded. Native payloads and
installed firmware remain unchanged. Next integrate firmware entry points and
wizard workflow/report presentation before reviewing a deployment candidate.

## Latest software checkpoint — one-shot delivery and durable reports

Implemented explicit initial/return token delivery with saved intent, a durable
one-use send claim, bounded HTTP, and replayable delivery-result exports. Failed
or uncertain attempts cannot be retried by constructing another sender. Acceptance
is not endpoint verification. Loopback tests use real saved authorization chains;
the arm is not contacted. Next connect delivery-result gating to the trial
coordinator, firmware entry points and wizard reports before candidate review.

## Latest software checkpoint — return capture and paired review

Implemented exact-byte return telemetry export/replay linked to saved return
authorization and the forward source chain. Combined review reports both legs'
endpoint evidence and elbow-count continuity, requiring COMPLETE state for pair
arrival. Missing/wrong-leg/stopped return captures cannot qualify as successful
round trips. The synthetic native direct/socket integration exercises the full
saved hold -> forward -> return -> paired review path, without device access.
Next: concrete one-shot delivery reports, firmware entry-point integration and
candidate review, then wizard presentation. Physical bidirectional proof remains
pending; this checkpoint does not change the installed firmware or hardware.

## Latest software checkpoint — archive-bound return authorization

Return tokens now derive exclusively from a reopened stable arrived forward
archive and bind boot/session, plan, exact raw evidence, export hash and original
anchor. Context is durably saved and a shared one-use nonce consumed before token
release. No command is sent by these helpers. The combined synthetic integration
test now runs the real hold preparation -> pair authorization -> forward export
-> return authorization chain, then verifies native direct/socket acceptance and
return to the original count. Source-chain replay is no longer stubbed.

Next: one-shot pair delivery reports, return-leg capture/replay and pair summary,
then firmware entry-point integration/candidate review. No deployment, hardware
movement, reset, provisioning or servo configuration occurred at this checkpoint.
Earlier checkpoints below are historical; see `HELD_ELBOW_BIDIRECTIONAL_PLAN.md`.

## Latest software checkpoint — session-linked forward observations

Implemented saved initial-pair authorization replay and concrete read-only forward
collection/export/replay. Raw HTTP bytes and source context hashes are retained;
endpoint reports are independently recomputed after reopening the archive.
Results distinguish controller-reported arrival from delivery, provenance and
physical-tip accuracy, and grant no return authority. Partial reads remain
inconclusive. See `HELD_ELBOW_BIDIRECTIONAL_PLAN.md` for test scope and limitations.
Next implement archive-bound return signing, then firmware entry-point integration
and candidate review. This checkpoint is offline software only: installed r7 and
the consumed single powered hold authorization are unchanged.

## Current checkpoint and authorization — 2026-09-18

DURABLE INITIAL PAIR TOKEN RELEASE IMPLEMENTED: replay preparation, save/reopen
signing context, atomically consume shared boot/nonce claim and verify readback
before returning token. Duplicate, cross-hold reuse, wrong boot and storage
failure paths tested; claims are never refunded. Thirty-seven focused tests pass.
Tokens/keys are not exported; helper sends nothing and is not exposed by CLI/UI.
Observed-forward export/return signing and firmware entry points remain.

HOST PAIR PREPARATION LINKED TO HOLD EXPORT: saved plan derives from replayed
observed-hold/prepared-attempt/transport chain, retaining source hashes, boot,
policy and hold-plan identity. Reopening rebuilds all derived content; valid-
manifest tampering is rejected. Thirty-seven focused tests pass. This is offline
preparation only, with no signing, device opening or command authority. Durable
pre-send claims/signing and observed-forward return export linkage remain.

INITIAL/RETURN NETWORK LIFECYCLE IMPLEMENTED OFFLINE: explicit one-use challenges,
fresh nonces, only one active operation graph, no automatic return/rearm, and
failure on entropy/expiry/clock/allocation/bind issues. Thirty-seven focused tests
pass; actual ESP32 network/RNG lifecycle compilation succeeds. Known initial and
return fixed subtotals 95,608/103,668 bytes exclude dynamic allocations and stacks.
Session-linked durable host export/signing and firmware entry points remain;
no live listener, device access or deployment occurred.

CONCRETE ONE-SHOT NETWORK ASSEMBLED OFFLINE: server/client/socket/owner/session/
listener graph compiles against actual ESP32 network types. Scheduling tests for
both operation roles reject failed bind/request/reply/port without sampling and
prevent reaccept/rearm. Thirty-six focused tests pass. Concrete graph 19,624 bytes;
known fixed runtime/gates/bridge/network subtotal 103,396 excludes dynamic memory.
Top-level challenges/lifetime and durable hardware-export signing remain. No live
listener, device access or deployment occurred.

AUTHENTICATED HOLD HANDOFF IMPLEMENTED: only successful authenticated hold capture
can issue a noncopyable, one-use capsule bound to boot/hold-plan/policy. Pair start
requires it; wrong/missing/consumed identities stop before displacement. Full
simulated signed hold/pair lifecycle frees the old hold graph before allocating
pair. Thirty-five focused tests pass; ESP32 handoff size 1,888 bytes and runtime
72,088. Durable hold export before release and concrete network lifecycle remain
outer integration work. No live hardware or deployed firmware changes.

PAIR SOCKET OWNER INTEGRATED OFFLINE: initial/return adapters reuse the restricted
one-request socket machinery. Full signed lifecycle tested via simulated socket;
short reply sends stop before affected-leg motion. Thirty-four focused tests
pass. Target listener/connection instantiation succeeds; known fixed subtotal
including one connection/listener is 103,268 bytes, not a live heap measurement.
Concrete lifecycle/challenge/hold binding and hardware-export signing remain.
No port opened, firmware changed or live command sent.

READ-ONLY PAIR TRANSPORT IMPLEMENTED OFFLINE: native status/raw-string record
serialization and bounded host GET collector agree on exact bytes/digest, reject
active/changed/mismatched captures, and retain partial responses without retries.
Thirty-three focused tests pass; target serializer compilation succeeds at the
same 72,088-byte runtime layout. These routes are not installed or contacted.
Listener scheduling, session-linked hardware export/signing and live margins
remain. See `HELD_ELBOW_BIDIRECTIONAL_PLAN.md`.

COMPACT EVIDENCE STORAGE INTEGRATED: identical exported bytes are reconstructed
from retained raw snapshots and verified against publication hashes. All 32 scans
remain available. ESP32 runtime layout is now 72,088 bytes (previously 203,152);
known fixed runtime/gates/bridge subtotal 83,772 excludes dynamic allocations.
Twenty-five focused tests pass including full/compact byte comparisons and signed
lifecycle; target compilation succeeds. Live memory/timing fit remains unmeasured.
See `HELD_PAIR_MEMORY_REVIEW.md`; no deployment or hardware action occurred.

TARGET COMPILE/MEMORY EVIDENCE: actual ESP32/PSRAM-disabled compile-only probe
successfully instantiates pair runtime with SMS_STS. Runtime layout 203,152 bytes;
known fixed runtime/gates/bridge peak 214,836 bytes excludes dynamic networking,
JSON, stacks and overlapping hold objects. Deployment fit remains unproven.
New `HELD_PAIR_MEMORY_REVIEW.md` records measured components and next allocation
decisions. No link, flash, reset, serial access or hardware execution occurred.

AUTHENTICATED PAIR RUNTIME INTEGRATED OFFLINE: owns pair/store/publisher, accepts
verified hold handoff plus signed initial plan, derives forward-plan identity,
and permits store rollover only after stored-evidence signed return admission.
Full simulated hold/forward/return and rejected signatures tested; 24 focused
pytest cases pass. Host ABI size 204,008 bytes excludes temporary/network/stack
allocations, so ESP32 memory fit remains unproven. Outer same-boot hold binding,
transport, durable hardware-export signing and target memory review remain.
No deployment or hardware command. See `HELD_ELBOW_BIDIRECTIONAL_PLAN.md`.

INITIAL PAIR AUTHORIZATION CONTRACT IMPLEMENTED OFFLINE: host and native verifier
bind exact boot/hold/policy/command IDs/offset/tolerance, with matching session
hash. Eleven native signed scenarios plus invalid host geometry tests pass;
23 focused pytest cases passed overall. No live route or device action. Runtime
hold-to-pair wiring, leg-plan derivation, transport/export signing and embedded
memory review remain. See `HELD_ELBOW_BIDIRECTIONAL_PLAN.md`.

SIGNED PAIR CONTINUATION INTEGRATED OFFLINE: the finite scheduler now accepts a
concrete bridge to stored-record verification and one-use HMAC admission. Native
simulation completes forward/wait/signed-return with exactly two writes; rejection
and post-admission state/storage faults prevent return writes. Sixteen signed
scenarios and sixteen focused pytest cases pass. Initial pair admission, concrete
runtime/collector, hardware-export signing and embedded memory review remain.
No deployment or live commands. See `HELD_ELBOW_BIDIRECTIONAL_PLAN.md`.

RAW HOST ARCHIVE/REPLAY IMPLEMENTED: exact native record bytes are base64-retained
with kind/order, plan/policy and independent assessment; export is reopened,
manifest checked, digest recomputed and assessment replayed. Native fixtures cover
all three outcome classes, corruption and valid-manifest semantic tampering.
Sixteen focused pytest cases pass. This API is SIMULATION-only and cannot sign or
send; concrete session/transport integration is required before hardware-origin
export and return signing. No hardware access or deployment occurred.

STORED-EVIDENCE RETURN ADAPTER IMPLEMENTED OFFLINE: native records must match
the completed forward owner's scans/action/terminal byte-for-byte before local
digest calculation and HMAC return admission. Ten signed synthetic cases reject
individual record changes, wrong evidence digest, bad signature and duplicates
without bus I/O. Sixteen focused pytest cases pass. Top-level authenticated
session bridge, host durable export/replay and embedded memory review remain;
no live command or deployment. See `HELD_ELBOW_BIDIRECTIONAL_PLAN.md`.

SHARED EVIDENCE IDENTITY IMPLEMENTED OFFLINE: bounded native/Python SHA-256
record-chain digest matches on exact native publisher output for three simulated
outcomes. It binds storage kinds, ordering and raw bytes without reserialization.
Fifteen focused tests pass. This is not a signature, arrival assessment, origin
proof or durable-export proof. Return-gate/host-export integration still pending;
no live commands or deployment. Protocol in `HELD_ELBOW_BIDIRECTIONAL_PLAN.md`.

REAL EVIDENCE-STORE INTEGRATION FIX: actual-store testing reproduced terminal
publication failure because `held_leg_terminal` exceeded the store's 15-character
kind limit. Changed only its internal label to `held_leg_end`, retaining JSON
schema. Added full forward/return publisher-plus-store simulation in both signed
directions; seven focused harness cases pass. Signed continuation/host durable
export integration remains pending. No live access or deployment occurred.

FINITE PAIR MECHANICAL CORE IMPLEMENTED OFFLINE: bounded forward/wait/return
scheduler freezes the original anchor, requires cross-leg state binding and
reuses one leg-history allocation. Six focused harnesses pass, including signed
directions and failed movement/export/admission cases. Its injected admission is
synthetic in tests; actual authenticated runtime, durable-export continuation and
publisher/store rollover remain to integrate. Installed r7 is unchanged. Details
and remaining embedded memory work: `HELD_ELBOW_BIDIRECTIONAL_PLAN.md`.

CROSS-LEG CONTINUITY IMPLEMENTED OFFLINE: the native leg owner can bind a prior
verified endpoint and reject changed positions, goals or torque states before
dispatch rather than accepting them as a new baseline. Neighbor continuity is
also checked after dispatch. Five focused native/replay/wire/auth test harnesses
passed. See `HELD_ELBOW_BIDIRECTIONAL_PLAN.md`. Full session integration must
require this binding and supply the frozen original return target; that work and
embedded memory budgeting remain. No new live command or deployment occurred.

RETURN AUTHENTICATION CONTRACT IMPLEMENTED OFFLINE: one-use native HMAC gate
matches locally supplied session/forward-plan/evidence identities and original
anchor, requires forward-arrival state and a signed host export digest. Fourteen
synthetic cases pass with duplicate-consume rejection. No bus/route/deployment.
Host durable-export-before-signing and native finite session integration remain;
the gate alone neither proves disk persistence nor authorizes physical motion.

PINNED-LIBRARY LEG PACKETS VERIFIED IN HOST SIMULATION: new forward/return wire
harness exercises hash-verified real SCServo sources and compares emitted packets
with retained command encoding. Success, non-arrival, lost/corrupt write ACK after
simulated movement, bad read checksum and wrong response ID pass with no retry.
A missing return in the reused test harness was corrected; no production library
change. Both hold/leg wire variants pass. No hardware access or deployment.
Next finite authenticated session and export-gated continuation/memory integration;
the real arm's successful hold remains the latest live result.

INDEPENDENT SINGLE-LEG REPLAY IMPLEMENTED: `held_leg_replay.py` reconstructs raw
counts, checks a separately supplied plan/policy, exact command/ack, fresh held
baseline, timing/gaps, neighbor invariants, target readbacks, corridor, settling
and deadline coverage. It derives arrival/non-arrival before terminal-label
comparison; invalid or uncertain evidence remains inconclusive. Simulation-only
exports retain raw records and expectations and recompute on replay. Native
fixture plus mutation/export tests pass (12 focused tests). No hardware access.
Next integrate pinned-library wire coverage and finite authenticated session;
simulated verification is not live motion authority or physical accuracy.

SINGLE-LEG RAW PUBLICATION IMPLEMENTED OFFLINE: bounded 34-record publisher
retains raw scans/action/terminal and stops all subsequent bus activity on failed
publication. Native tests passed successful capture, non-arrival, partial read
failure, each success-path publication failure and uninitialized publisher; Python
decoded raw counts independently. No hardware access or installation. Full
independent endpoint replay, plan binding, pinned-wire coverage, memory budgeting
and authenticated two-leg continuation remain to implement before deployment.

NATIVE SINGLE-LEG MOVEMENT CORE IMPLEMENTED OFFLINE: `held_elbow_leg_owner.h`
uses fresh whole-arm scans, held-elbow admission, one write/ack, bounded elbow
corridor, neighbor invariants, separated settled observations and terminal
Arrived/NotArrived/Fault outcomes. Synthetic native test passes forward/reverse,
no-motion and fault cases, including all 140 read positions on the success path;
no retry writes after faults. No hardware access, deployment or new route.
Next integrate raw publication/replay and pinned-library wire tests, then finite
authenticated hold-plus-leg session and export-gated return. See
HELD_ELBOW_BIDIRECTIONAL_PLAN.md for limits and remaining memory/integration work.

FORWARD/RETURN PATH SPECIFIED: `HELD_ELBOW_BIDIRECTIONAL_PLAN.md` defines native
count-space A->A+6->A with fresh held anchor, distinct endpoint bands, per-leg
evidence, and durable verified export before a separately admitted return. The
existing single-command startup owner is not a multi-leg implementation; r7's
consumed hold runtime cannot run this draft. `held_elbow_trial_draft.py` replays
the actual hold source and produces a non-authoritative proposal, rejecting
overlapping bands or out-of-envelope targets. Ten tests passed. Actual-source
draft export `wizard-20260918T231106817443Z-656c4ce3781c4effa47b98527d0eaab4`
illustrates 2902->2908->2902; these are not live command targets. No hardware access.
Next implement/test the native per-leg movement owner, then authenticated finite
session/continuation integration; firmware and live approval still separate.

POWERED ELBOW HOLD VERIFIED AT CONTROLLER-COUNT LEVEL: user explicitly confirmed
supported/secured/clear powered setup and approved one hold. The supported-pose
runner sent once; saved replay returned CONTROLLER_REPORTED_HOLD_VERIFIED.
Five fresh snapshots and one action: initial/fresh requested count=2902,
encoded target=2902, first and settled goal register=2902, settled position=2902,
error=0 counts. Torque changed 0->1 following the position write; no separate
explicit-enable action was needed. All six neighboring positions, goals and
torque states were unchanged across all five snapshots. Final sample ended
136,388 microseconds after command completion. Controller state CAPTURED,
ELBOW_HOLD_CAPTURED, eight retained records, no storage fault. No retry/reset/
release/follow-up move. The new boot's hold claim is now consumed.

Observation: `wizard-20260918T230821752067Z-164698b57d1148429f455b24fce52c15`.
Raw transport: `wizard-20260918T230821675163Z-21ba31b6d6c14934864950b3d8b26496`.
Prepared attempt: `wizard-20260918T230818374347Z-e0a091ad351a47169f28de8e39cbbbbd`.
Export and raw replay verified offline after the trial. The pinned library's
argument encoding is checked, not independently observed wire traffic. This
proves reported hold initialization, NOT displacement, reverse motion, physical
tip accuracy, authenticated device provenance or whole-arm readiness. Other six
servos last reported torque off; keep mechanical support, particularly before
power removal. Elbow last reported torque on; no release was commanded.

Next review a bounded forward/reverse diagnostic owner starting from this hold
evidence, retain command/readback/position linkage and per-leg export/stop logic.
The installed r7 one-use hold runtime cannot execute that sequence or be reused.
Software/simulation work can continue; any new firmware/provisioning/servo change
needs its own review and approval. Prior awaiting-hold notes below are historical.

NEW-BOOT HOLD PREFLIGHT READY: explicit `--supported-pose` selection now binds
the replacement receipts, policy, encrypted recovery/candidate and boot
`35d977559eff75fd89c2f156abb5bc0c`. Real offline preflight passed; 16 focused
CLI/orchestration tests passed including cross-profile boot rejection. No hardware
access, key extraction, challenge or trial reservation. Await separate approval
for one powered elbow hold and confirmation of supported/secured/clear powered
setup. See HOLD_SUPPORTED_POSE_REVIEW.md for exact invocation and scope.

SUPPORTED-POSE FILESYSTEM INSTALLED WITH EXPLICIT APPROVAL: candidate
`4524696545583513b283348789b2e1f92ed37e178efcb10edf32dcbd639ec4bf`
passed full pre/post verification; all non-filesystem regions unchanged and
private recovery preserved. One startup followed verified result export.
Final run: `wizard-20260918T213520824547Z-50d496655d5d4796b58d39a0a8395a1a`.
Single status-only GET: IDLE/NOT_CONFIGURED, zero records, no storage fault, boot
`35d977559eff75fd89c2f156abb5bc0c`; export
`wizard-20260918T213547363926Z-f5e6fd8994844a3f8e4adf459e60fa35`.
No challenge, torque enable or movement. Replacement journal consumed, no retry.
Next bind hold trial preparation to these replacement receipts and new boot, not
the old hardcoded runner identity, then separately approve powered hold. Current
confirmed setup remains external power disconnected/USB connected. The following
pending-installation statements are historical; see HOLD_SUPPORTED_POSE_REVIEW.md.

SUPPORTED-POSE INSTALLATION PATH READY, NOT EXECUTED: exact replacement CLI
preflight passed on real retained artifacts with no hardware access or journal
reservation. Replacement orchestration has separate one-use journal/recovery
files and re-stages exact bytes before the existing r7-bound full-readback write
core. 24 integrated startup/hold/replacement tests passed. See
`HOLD_SUPPORTED_POSE_REVIEW.md`. Next requires separate approval for one
filesystem-only write and one startup of candidate `45246965…639ec4bf`, with
links supported before external power removal and USB left connected. No live
hold, firmware application write or servo configuration operation is included.

SUPPORTED-POSE PRIVATE CANDIDATE PREPARED WITH APPROVAL: exact policy replacement
preserved the existing credential and all five unrelated entries, remounted and
saved/readback-verified with DPAPI. Candidate SHA-256
`4524696545583513b283348789b2e1f92ed37e178efcb10edf32dcbd639ec4bf`.
Verified review export: `wizard-20260918T210720842126Z-374c9d9e3cfb41128c743accf9220ffc`.
No device access, key generation, installation, reset or motion occurred. Separate
staging reservation consumed; old artifacts preserved. See
`HOLD_SUPPORTED_POSE_REVIEW.md`. Next prepare/review the exact replacement
provisioning entry point; obtain separate installation/startup approval before
device writes. Prior pending private-staging statements below are superseded.

FAULT REPORT VISIBILITY IMPROVED: offline observed-hold replay now passes the
retained controller status and status-stability flag to the wizard. The UI shows
the reported state/reason separately from endpoint assessment, including partial
captures without claiming a stable final status. Nine focused tests passed.
Offline replay of the actual first hold export returned stable FAULT with reason
HOLD_POSE_OR_CONTROL_INVALID and three records; endpoint remains inconclusive.
No hardware was contacted. Revised-policy/private-staging approval remains pending.

SUPPORTED-POSE REVISION DRAFTED OFFLINE: see `HOLD_SUPPORTED_POSE_REVIEW.md` and
`hold-r7-supported-pose-draft.json`. Only command identity and elbow admission
window change; proposed window [2893,2909] surrounds the observed 2901 count pose,
without relaxing drift/timing or other joints. This is a proposed tolerance, not
a measured repeatability or clearance result. The retained installed-r7 parser
accepted its 460 canonical bytes, SHA-256
`2ab588877107ebbc067607c29003fb317867123780e40c8e9d41011907d312d1`.
No key extraction, staging, controller access, provisioning, reset or servo command
occurred. Await policy/private-replacement preparation approval before staging;
exact candidate provisioning and the subsequent hold remain separately approved
operations. Preserve old artifacts and consumed claims.

FIRST LIVE r7 HOLD ATTEMPT STOPPED BEFORE SERVO ACTION — 2026-09-18:
User confirmed external power and secured/clear setup and approved proceeding.
The exact-boot runner was executed once. Controller accepted the signed request;
the retained raw snapshot contains 28 successful reads across IDs 11–17 in
12,720 microseconds. Offline replay verified export linkage, plan/policy hashes,
challenge timestamps and raw snapshot decoding. All seven report mode=0,
moving=0, torque=0 and goal=0. Positions are 2047,2395,1722,2901,2035,2045,2047.
Elbow ID14 is outside its historical approved [2659,2787] window by 114 counts
above the upper bound; the other six are within their windows. Firmware reported
FAULT/HOLD_POSE_OR_CONTROL_INVALID, snapshot_count=1, action_count=0.
This is a starting-pose admission mismatch, NOT a demonstrated actuator failure
or failed movement arrival. Hold/torque enable was not attempted according to
the controller record. No resend, reset, provisioning or recovery motion followed.

Observation export: `wizard-20260918T200008543182Z-dd9099e1620648589bdae768904d2b4d`.
Raw transport: `wizard-20260918T200008468028Z-4aea2b566a4f4a1d862a79ddbd0fedee`.
Prepared attempt: `wizard-20260918T200005152664Z-b85a4ee0f40140fa9cd76da629c76b04`.
The boot claim is consumed. The generic endpoint assessment is inconclusive,
but the above raw evidence explains the pre-dispatch stop. Current reported pose
differs from historical provisioning windows; do not silently widen them. Next
review a bounded hold policy appropriate to the supported current pose, or an
explicitly agreed repositioning procedure. Any policy provisioning/reset and
subsequent torque trial require their own scope/approval. No motion accuracy or
reverse-motion claim is established by this run. Earlier ready-to-run notes below
are superseded by the consumed attempt.

EXACT r7 HOLD ENTRY POINT READY: `software/scripts/run_hold_r7.py --preflight-only`
passed against the retained real installation/provisioning/startup exports,
canonical reviewed policy, retained native validator, encrypted candidate and
recovery filesystem. No hardware access, credential extraction, reservation,
challenge or servo command occurred. This checks retained evidence, not current
physical power, controller identity over authenticated transport, or live readiness.
The live mode additionally requires `--authorized-powered-hold --expected-boot
749e200e399ad53b38f2fa35f4929ed8`; do not execute it without separate approval and
powered/support setup. It extracts the existing key only in memory, then the
runner rechecks fresh status before a single challenge/start. No credential
generation, provisioning, reset or automatic recovery is included. A different
boot or consumed claim stops rather than silently renewing permission.

FIRST HOLD ORCHESTRATION IMPLEMENTED (NOT EXECUTED ON HARDWARE):
`hold_first_trial_run.run_first_hold` validates explicit powered-hold admission,
configuration, key and destination before I/O; exports fresh boot status; reserves
a durable boot claim; exports the plan; requests the challenge immediately before
the existing one-use prepared send; then waits the policy deadline plus one second
and collects/replays HTTP observations. Accepted or uncertain delivery never
causes a resend. Challenge/export failures consume the attempt and stop; no reset,
provisioning, recovery movement or torque release is available in this runner.
Local tests replace all device I/O. The next live entry point must verify retained
r7 installation/provisioning evidence and load the private key before calling it.
Current latest physical confirmation remains supported, USB-only: powered-hold
authorization and physical power setup are still required before live execution.

WIZARD OBSERVATION REVIEW INTEGRATED: the separate `review_observed_hold` action
replays saved HTTP-observation exports without a network or serial connection.
It displays requested/encoded targets, goal-register readbacks, starting/settled
positions, count error, torque state and neighboring-joint changes. Incomplete
evidence displays inconclusive. The existing simulation action retains its own
origin and cannot consume observation exports. Neither action changes connection
readiness or grants movement authority. Integration tests exercise the service and
rendered result with synthetic successful/interrupted captures; no live trial has
been performed. The focused hold/HTTP/export/action-registry/UI suite passed
74 tests. Next is preparation of a separately authorized single powered-hold workflow,
with challenge acquisition immediately before start, never a standalone check.

READ-ONLY HOLD OBSERVATION PATH: `hold_observed_review.py` now collects from an
explicit private IPv4 endpoint using the bounded hold-only GET adapter, after
validating a retained prepared attempt. It preserves the raw transport export,
links its digest to the attempt, and exports/replays endpoint assessment offline.
Success is `CONTROLLER_REPORTED_HOLD_VERIFIED`, origin `HOST_HTTP_OBSERVATION`:
this establishes reported count agreement, not authenticated device provenance,
wire-level observation, physical-tip accuracy, whole-arm readiness or permission
for another command. Invalid/mixed/partial evidence remains inconclusive.
There is no challenge, start, reset, resend or motion route in this collector.
Tests use synthetic native records and substituted HTTP responses, not hardware.
Next integrate this report into the wizard and the separately approved powered
hold workflow. Keep challenge/config loading immediately adjacent to that trial:
requesting a challenge starts the boot's one-use ten-second admission window.
Do not consume it as a standalone configuration check. Earlier checkpoints below
are historical; completed provisioning supersedes their pending-approval text.

HOLD FILESYSTEM PROVISIONED WITH EXPLICIT APPROVAL: candidate
`0bdfc4d3f300e811e03332a6a86df20e47c3d42c95282e9ddd2f00c211044e9b`
was written once to the filesystem partition. Full pre/post flash acquisition
verified exact filesystem bytes and unchanged protected regions; private source
recovery was preserved. Result export preceded one authorized startup reset.
Run export: `wizard-20260918T194438073911Z-c5027a7bed73466d8d29ff51e49b553c`.
The hold provisioning journal is consumed; never rerun it.

One status-only GET after startup returned hold_transport.v1, IDLE/NOT_CONFIGURED,
zero records, no storage fault, new boot `749e200e399ad53b38f2fa35f4929ed8`.
Health export: `wizard-20260918T194501474566Z-ea93ab25a2a940bd8412946a9c2d432c`.
NOT_CONFIGURED here means the lazy hold runtime has not loaded its files via the
challenge route; it does not contradict verified on-flash provisioning. Config
loading, allocated runtime health and powered hold remain unverified. No challenge,
torque command or movement command was sent. Camera/contact remain deferred.

HOLD EXACT-CANDIDATE PREFLIGHT PASSED: `provision_hold_r7.py` binds the already
staged image/policy/validator and passed real local-only preflight. 35 targeted
CLI/core tests pass. No hardware access, key generation/extraction or reservation
occurred. Next needs separate approval: one filesystem-only provisioning plus
one startup for candidate `0bdfc4d3f300e811e03332a6a86df20e47c3d42c95282e9ddd2f00c211044e9b`.
No challenge, torque or movement is included. See `HOLD_R7_PROVISIONING_REVIEW.md`.

OFFLINE HOLD STAGING COMPLETED WITH APPROVAL: one key and preserving filesystem
candidate are saved in current-user DPAPI storage, not installed. Candidate hash
`0bdfc4d3f300e811e03332a6a86df20e47c3d42c95282e9ddd2f00c211044e9b`;
verified review export `wizard-20260918T192754597401Z-66ce7c2b5fa041509937d7c61b69134f`.
Four existing entries preserved; exact draft accepted by the retained r7 parser.
No device/network access occurred. Staging reservation is consumed. Next is
candidate-specific provisioning preparation and separate write/startup approval;
no hold/servo operation is authorized by the staging approval.

HOLD PROVISIONING ORCHESTRATION TESTED: r7 now has a dedicated entry point using
exact restaging, separate journal/private image names, verified exports and
explicit optional startup. Both profiles passed integrated synthetic-device tests
with real LittleFS/DPAPI, plus failure and no-reset cases: 58 tests passed.
No real hold candidate or journal exists. Next approval is offline private
staging of the reviewed draft/key only, not controller provisioning or movement.
See `HOLD_R7_PROVISIONING_REVIEW.md` for the exact scope.

HOLD PROVISIONING PREPARATION: separate hold filesystem staging, installed-r7
native policy validation, r7-bound one-write core and separate journal are now
implemented. Draft policy canonical SHA-256 is
`f9663167513aadeb5666713c808128ddd834be5843e6570d22359338f93dc9e1`.
42 targeted tests pass, including both profiles' fault paths. No live key,
candidate or provisioning was created. See `HOLD_R7_PROVISIONING_REVIEW.md`:
orchestration/export tests remain before staging/provisioning approvals. Draft
explicit torque enable is proposed, not authorized; historical windows are not
fresh pose evidence.

R7 INSTALLED AND STARTUP RESPONDING: after explicit app-only/startup approval and
confirmation of supported links, external power disconnected and USB connected,
the one-use r7 installation completed. Controller/predecessor/partition/filesystem
checks passed; full application readback matched SHA-256
`380d7a69e0b456b25b4ae50e34f8d947724ca5c22db42d75958df509e2618c33` and protected
regions were unchanged. One startup reset was sent. One read-only status GET
returned hold_transport.v1, IDLE/NOT_CONFIGURED, zero records, no storage fault,
boot `cb73246b081511962f682ed39f359919`.

Verified evidence export:
`wizard-20260918T191322958288Z-a8f1786858e441619438af6e01245a46`.
No hold provisioning, challenge, torque or movement command occurred. The r7
deployment journal is consumed: never rerun that installation. Next is separately
reviewed hold provisioning and hardware-origin collection; startup HTTP response
is not servo readiness, measured memory headroom, or physical hold verification.

R7 APP-ONLY APPROVAL RECEIVED: the user explicitly authorized “Install r7 app-only
and perform one startup, with no provisioning or movement.” This covers the
reviewed r7 application only, not hold configuration, torque engagement or motion.
Deployment has not begun: the r7 deployment journal is absent. Before opening
serial or resetting, confirmation is still needed that articulated links are
mechanically supported, external motor power is disconnected and USB is connected.
Do not infer that physical state from the installation approval. Support links
before removing motor power because the arm previously dropped on power removal.

R7 INSTALLER READY FOR APPROVAL: corrected the predecessor filesystem binding
using verified r6 provisioning evidence. Eleven installer tests and actual local
r7 preflight passed; no device access or journal reservation. The exact app-only
install/startup scope is in `HOLD_R7_INSTALLATION_REVIEW.md`. Separate approval
and supported USB-only state are required before deployment; provisioning and
servo engagement remain separate, unfinished steps.

WIZARD HOLD REVIEW: the Arm section can now replay a collected hold simulation
export and show count-level targets/readbacks/positions, delivery and neighboring
joint changes. It labels simulation and NOT QUALIFIED, retains inconclusive
outcomes, and opens no device. Real service/renderer coverage includes success,
interrupted collection and missing export. Hardware-origin collection and
separately approved provisioning/deployment/live hold remain unfinished.

ENDPOINT REVIEW DETAIL: simulated and exact-policy bound hold exports now include
an optional replay-verified count-level breakdown of target, encoded command,
goal readbacks, fresh positions, error, torque and neighboring-joint changes.
Old export assessments remain compatible. Fifty focused tests pass, with added
one-count-offset and legacy replay coverage. No live success/physical accuracy
claim or device action; hardware-origin collection/wizard wiring remain next.

HOLD-ONLY BOARD INTEGRATION: candidate r7 now selects a dedicated hold runtime,
separate `/rocell-hold.json` and `.key` paths, one-use challenge/listener and
hold-specific read-only status/record routes. Diagnostic boot still skips legacy
startup motion and command ingress. Fifty focused tests pass. Full target compile
succeeded for default 4 MB/no PSRAM; verified evidence is in export
`wizard-20260918T174440380311Z-592ae9d2f2484a13b103cc8e8b954407`.
Nothing has been installed or sent to the physical arm.
See `HOLD_POSITION_INITIALIZATION_PLAN.md` for the route behavior and remaining
hardware-origin collection, memory review and separately approved trial work.

END-TO-END COLLECTION LINK: prepared attempt now links to exact raw transport
export and recomputed policy/challenge-bound assessment. Interrupted collection
exports/replays as inconclusive without another send. Forty-nine focused tests
pass. Concrete ESP32 route/candidate build, hardware-origin review and wizard
integration remain; no live device or firmware was changed.

DURABLE HOLD TRANSPORT: exact bounded raw responses and fixed receive-failure
markers now export and replay offline. Native capture, interrupted GETs and
malformed JSON reproduce their outcomes; modified transcripts fail verification.
Forty-nine focused tests pass. Board routes/candidate build and final prepared-to-
transport linkage remain next. No network/device or controller image changed.

HOLD CONFIGURATION: strict canonical configuration parsing now precedes configured
runtime allocation. Complete scripted runtime/collector tests use this entry;
invalid/ambiguous policies reject without defaults. Forty-eight focused tests
pass. Board provisioning/routes and durable transport replay remain pending;
no live controller settings or image changed.

HOLD COLLECTOR: native record envelopes now have a matching bounded read-only
host collector, with boot/index/status checks and partial-response retention on
failure. Native-output-to-host tests and blocked command-route tests pass (47
focused tests). Durable transport replay, board route registration and config
parsing remain next. No real network/device access or deployment occurred.

CONFIGURED HOLD WRAPPER: explicit network/runtime composition now includes
read-only status and record access, one-request lifetime, and a distinct 4096-byte
transport schema. Scripted success/failure tests and ESP32 compile-only network
object-budget checks pass (42 focused tests). Concrete board routes/config parser,
host collector and full deployment build remain. No device/image changed.

LISTENER ADAPTER: allocated hold runtime now works through the existing one-shot
HTTP/socket listener under scripted tests. Chunked signed requests complete;
disconnect, trailing bytes, expiry and failed response writes prevent servo
writes. Forty-one focused tests pass. Concrete firmware mode/status/record routing
and deployment remain pending. No network port or physical device was opened.

LINKED HOLD REVIEW: prepared plan/challenge, consumed nonce claim, delivery report
and native simulation capture now replay as one digest-linked export chain.
Out-of-window records or a missing claim fail review without another send. Forty
focused tests pass. Live firmware mode/listener/record collection integration is
still pending; all tests used synthetic data and no device was contacted.

CHECKED ALLOCATION: one-lifetime runtime/store allocation now fails before any
bus I/O on invalid policy, expired/revoked setup or unavailable memory. Signed
simulation and forced-failure tests pass; ESP32 object-budget regression includes
the wrapper. Forty focused tests pass. Mode/network and linked-collection
integration remain pending; no device or installed image changed.

HOST HOLD PREPARATION: frozen plan/policy signing now matches native admission.
Prepared sends verify expectation exports and consume a shared nonce claim before
one adapter call; failures do not enable retries. Thirty-nine focused tests pass,
using mock senders/sockets only. Linked collection/replay and checked firmware
allocation remain next; no live key/device/image was accessed or changed.

TARGET MEMORY REVIEW: ESP32 compile-only runtime/store footprint is 76,520 bytes;
largest individual emitted stack frame is 336 bytes, not total live stack demand.
Integrated tests now use the real 12x4096 bounded store. Thirty-four focused tests
pass. See `HOLD_RUNTIME_MEMORY_REVIEW.md`; target heap/allocation and network-mode
integration remain open. No device access or firmware image deployment occurred.

BOUND REPLAY COMPLETE FOR SIMULATION: integrated native records now validate
against the independently supplied exact plan/policy and round-trip through
verified exports. Hash-consistent but policy-violating transcripts are rejected.
Thirty-three focused tests pass. Hardware provenance/challenge-bound collection,
target memory/store and firmware route integration remain pending; no live I/O.

INTEGRATED HOLD RUNTIME: authenticated admission now gates the private staged
controller and publisher; all records carry matching plan/policy hashes and an
authorization record retains the exact native policy. Tests prove zero bus calls
on rejected starts/reservation failures and no write after mid-scan admission
loss. Thirty-three focused tests pass. Bound host replay and actual firmware
route/store/memory integration are next. No live device or installed image changed.

AUTH/TERMINAL PROGRESS: a one-use native HMAC admission component now binds a hold
request to boot, command and the exact native policy digest. Real host/native
crypto tests pass. The publisher adds a terminal count/state record, required by
replay. Thirty-three focused tests pass. Admission-to-runtime wiring and hash
linkage to exports remain pending; no hardware/firmware/configuration change.

HOST REPLAY: native hold simulation records now pass raw-read/action validation,
default-policy sequence replay and durable diagnostic export/manifest round-trip.
Partial or altered evidence remains inconclusive. Expanded native-publisher tests
and focused regressions pass (32 pytest tests). These results are explicitly
simulation-only; authenticated hardware policy/terminal binding remains pending.
No device contact, servo write or deployment was performed.

RECORD PUBLICATION: staged hold snapshots and action/ACK records now serialize
with boot/command IDs and finite capacities. Scripted publisher failures stop
further bus work, preserving partial local evidence. Thirty-two focused tests
pass. Authentication, terminal manifest, durable host export/replay and reviewed
target-memory/store integration remain incomplete. No device/image change.

PINNED LIBRARY VERIFICATION: the staged hold controller now runs through actual
SMS_STS/SCS/SCSerial code with a host serial emulator. Emitted write bytes match
action evidence; missing/corrupt ACKs stop without resending. Source/header hashes
are checked. Thirty-one focused tests passed. This verifies software behavior,
not physical UART/servo execution; no deployment or hardware call occurred.

LATEST INITIALIZER: a native staged elbow controller now joins readback capture
to one hold-position attempt and an optional explicitly permitted enable attempt,
retaining action/ACK evidence and stopping on faults without retries or releases.
Thirty focused tests passed. This is local tested code only: authenticated outer
admission, serialization/export replay, actual pinned-library wire verification,
memory review and deployment remain pending. Installed r6 and physical state were
not changed. See `HOLD_POSITION_INITIALIZATION_PLAN.md` for scope and next work.

NATIVE INITIALIZATION PROGRESS: `hold_state_snapshot.h` now captures raw whole-arm
goal/position and mode/torque evidence without assuming torque is already enabled.
Scripted native tests inject short reads and device errors across all 28 reads;
18 focused tests passed including the hold model and existing control reader.
This is acquisition only, not the initialized write owner or deployed firmware.
No hardware calls occurred. Details: `HOLD_POSITION_INITIALIZATION_PLAN.md`.

LATEST SOFTWARE: a transport-free hold-initialization simulation now covers the
elbow's possible automatic-torque and explicit-enable behaviors, retaining partial
state and stopping on uncertain ACK/readback/export failures. Sixteen new tests
and twelve existing regressions passed (28 total). See the implementation checkpoint
in `HOLD_POSITION_INITIALIZATION_PLAN.md`. This is not yet a native initializer:
signed admission, raw evidence, durable export/replay and wizard integration remain.
No arm connection, reset, firmware write or servo action occurred in this step.

LATEST POWERED TRIAL: one authenticated startup request was accepted, but native
admission stopped with CONTROL_STATE_MISMATCH before any servo dispatch. Two
fresh scans were stable; elbow 2723 versus proposed 2727. All seven direct mode
reads were 0 (expected), and all torque-enable reads were 0 (policy requires 1).
This exposes the missing hold/torque initialization stage, not a positional error.
No automatic enable, resend or reset. See `FIRST_POWERED_STARTUP_RESULT_20260918.md`
for exact observations/exports and the required separately reviewed servo-state
change. Latest physical setup is powered and stationary per user confirmation;
older USB-only entries below are historical.

INITIALIZATION REVIEW: `HOLD_POSITION_INITIALIZATION_PLAN.md` supersedes any
assumption that a goal can be seeded without torque engagement. Official Waveshare
documentation says rotation commands can automatically turn torque on; the local
library's lack of an explicit enable is insufficient to disprove device side
effects. Stock moveInit also moves joints and recalibrates the driven shoulder,
so it is excluded. Next implement a separately authorized, evidence-retaining
hold initialization with both possible torque behaviors and explicit transition
to nonzero goal-ledger tracking. No servo-state change or reset was made.

LATEST NONMOTION INITIALIZATION: installed startup policy/key loaded successfully
on boot `f12a38eeea1c2b983197d02b38d9a4de`; one 10-second challenge was obtained,
with immediate IDLE / NONE and zero records. No start command was sent. After
lease expiry the owner reported FAULT / STARTUP_INTERFERENCE, consistent with
the pinned listener's expiry-to-interference mapping (not uniquely diagnosed by
that generic public label alone). Retained export references and source reasoning
are in `STARTUP_R6_PROVISIONING_PROPOSAL.md`. This boot's admission is consumed;
no automatic reset/re-arm. Next prepare the complete bounded trial before a
deliberate new startup. Motor power remains disconnected; no servo evidence was
acquired by this initialization check.

First-trial follow-up: `startup_first_trial.py` now constructs the exact-policy
bound single-elbow plan described in `FIRST_STARTUP_ELBOW_TRIAL.md`. Nine focused
tests passed, including the pinned Waveshare conversion for proposed count 2727.
Native fresh-position delta remains capped at 8 counts; no actual trial has been
sent. Live orchestration/power-startup coordination and endpoint evidence remain
outstanding. Do not mistake the proposed target for fresh measured position.

LATEST PROVISIONING: after explicit user installation approval and USB-only
confirmation, startup configuration/key were privately staged and installed once.
Full flash readback verified exact LittleFS image and unchanged outside regions.
Source recovery is privately retained. Result export
`wizard-20260918T162143542724Z-b2cd3fafbf42411cbe05d56827abf966` records one startup.
Passive status export `wizard-20260918T162150374348Z-694cefbdd194431d8cfc7f9fdc7f07cb`
is verified/replayed; new boot `f12a38eeea1c2b983197d02b38d9a4de`, IDLE,
NOT_CONFIGURED, zero records. Configuration-load initialization is not yet tested;
passive status does not trigger it. No motion or servo setting was changed.
This supersedes historical pending-provisioning entries below. See
`STARTUP_R6_PROVISIONING_PROPOSAL.md` for exact image and export references.

LATEST DEPLOYMENT: user approved r6 app-only installation and confirmed supported
links with USB-only power. Installation completed with full exact image readback,
protected-region verification and one startup reset. Read-only status is stable
`IDLE / NOT_CONFIGURED`, boot `a92f8d4a46620f79609b26383134746e`. Deployment export
`wizard-20260918T155337255349Z-a811a3cc7e9d486ebe811b700b839cda`; status export
`wizard-20260918T155337593408Z-591d8b1edf354f3ab6ff0008cc52afd8`. Both verified;
status replay passed. Startup provisioning still needs separate review/approval.
No motion or servo-configuration change occurred. This supersedes older entries
describing r3 as installed or r6 deployment as pending. See
`STARTUP_R6_DEPLOYMENT_PROPOSAL.md` for the completed procedure and exclusions.

Offline provisioning review is now in `STARTUP_R6_PROVISIONING_PROPOSAL.md`, with
the nonsecret `startup-r6-policy-draft.json`. Canonically serialized policy bytes
passed the r6-bound native parser; formatted review bytes correctly do not.
No real key/image was staged and no filesystem write occurred. Startup-specific
write execution and separate provisioning approval remain outstanding. Draft
pose windows use historical observations only as bounded review inputs; fresh
feedback and the later per-command delta gate remain mandatory.

Provisioning execution follow-up: the one-shot injected-device write/verification
core is implemented; 23 focused core/image tests passed with synthetic hardware.
It requires durable reservation and private source retention before any write,
checks full readback and outside-region preservation, and has no retry/reset.
The live USB adapter, durable integration and separate approval are still pending;
no actual provisioning has occurred. See the provisioning proposal's readiness
section for the distinction between tested core and deployable workflow.

LATEST HARDWARE EVIDENCE: after user-confirmed motor power and no observed motion,
one baseline-only scan succeeded on IDs 11–17. All moving flags were zero; all
goal-position registers were zero despite valid nonzero measured positions.
Export verified. No movement was commanded. See
`POWERED_BASELINE_RESULT_20260918.md` for raw evidence references, the reproduced
startup/admission assumption mismatch, and the first-command initialization work.
Do not compensate toward zero goals or reuse the historical scan as fresh proof.

Offline follow-up implements separate two-scan zero-goal startup observation,
signed startup-plan parsing and an asynchronous guarded execution owner. Normal
post-command tracking remains strict. The focused regression suite passed 29
tests; the owner orchestration test uses explicit doubles, so integrated real
authentication/parser execution and host export review remain required. None of
this startup path is installed or grants new motion permission. See the latest
checkpoint in `POWERED_BASELINE_RESULT_20260918.md` for the ordered next work.

Follow-up: the integrated native pipeline test now joins real authentication,
startup parsing and hash-verified Waveshare conversion to guarded execution on a
simulated bus. This supersedes the real-parser integration gap noted above.
Independent host review of startup evidence, runtime integration, reviewed
deployment/provisioning and live endpoint validation remain incomplete.

Latest offline follow-up: independent startup session assessment is implemented
and exercised against native-generated simulated records, including arrival,
acknowledged-but-stationary behavior and target mismatch. Export/UI wiring and
runtime/configuration integration remain incomplete; see the powered-baseline
report for its exact evidence checks and limitations. Hardware remains unchanged.

Startup read-only collection and export/replay are now implemented in
`startup_planned_run.py` with explicit-mode transport support. Tests replay
native-generated simulated arrival, stationary/non-arrival, mismatch and partial
startup evidence. Remaining integration includes GUI wiring, transport-failure
retention and controller runtime/configuration; no new deployment is authorized.

The distinct startup configuration parser and runtime now exist and compile in
the native integration test. Valid initialization and expiry are tested with
inert networking; signed socket execution, exclusive route integration and an
ESP32 candidate build remain next. This runtime is not installed. Refer to the
latest powered-baseline checkpoint for exact tested versus pending scope.

Latest: signed socket/runtime integration passes in host simulation, including
short acceptance, disconnect and trailing-byte rejection without servo writes.
r4's embedded build exposed an 18,168-byte static-DRAM overflow. r5 uses one bounded
fail-closed runtime allocation and compiles successfully for the compatible 4 MB
no-PSRAM profile. See `POWERED_BASELINE_RESULT_20260918.md` for hashes, test/export
evidence and the still-required runtime-memory and deployment review. Installed
firmware remains r3; no provisioning or new motion is authorized by compilation.

r6 supersedes r5 as the proposed candidate after reducing the configuration-parser
stack frame from 5,152 to 1,040 bytes. It compiles and passes offline artifact/
partition review. `STARTUP_R6_DEPLOYMENT_PROPOSAL.md` records the exact app-only
scope awaiting separate approval. Provisioning, live testing and UI work remain
separate; no deployment or device changes have occurred.

The r6 installer binding and local-only preflight are implemented and tested.
Local preflight verifies the image, predecessor and recovery artifacts without
opening the controller or reserving a deployment journal. Approval remains
pending; software work may continue without treating automatic goal continuation
as permission to flash or provision.

Startup collection now retains/replays partial bounded responses and receive
failures as INCONCLUSIVE through the planned-run export flow. It does not retry,
claim endpoint success, or conceal export-verification failure. Focused tests
passed; UI integration and approved live execution remain incomplete.

Offline startup review is now wired into the wizard arm section with service-owned
replay results and explicit inconclusive/NOT QUALIFIED display. This completes the
saved-run review portion only. Live startup controls, matching provisioning and
separately approved deployment/physical endpoint validation remain pending.

Offline startup provisioning now has distinct paths, native r6-bound validation
and synthetic preservation/no-overwrite tests. Normal provisioning remains
separate. No real key, live policy or staged actual-controller image was created;
deployment/provisioning approvals are still outstanding.

Startup host request preparation now exports frozen expectations before its
one-use send and consumes the shared boot/nonce claim across normal/startup modes.
Fake-socket tests cover exact signing, uncertain delivery and export failures.
The sender is not wired to a live wizard action; delivery-to-capture linkage and
approved hardware commissioning remain pending.

Saved startup delivery is now linked to read-only capture and deterministic replay
with matching plan/context hashes and consumed-claim checks. A wizard action shows
delivery and endpoint verdicts separately. Native simulation and fake-transport
tests exercise arrival and uncertain/inconclusive cases without live access.
This does not resolve live reverse-motion ambiguity or grant deployment approval.

Repeatability gap reproduced: the first elbow command leaves a mixed goal state
(commanded elbow, untouched zero goals). Neither another zero-goal startup nor
the existing strict normal gate admits that state. The native simulation now
models target changes per servo and tests both refusals without extra writes.
`STARTUP_TO_REPEATABLE_MOTION_PLAN.md` specifies the explicit campaign/goal-ledger
transition needed for forward/reverse cycles. Do not work around it with resets,
goal rewrites or global gate relaxation; r6 remains a first-command candidate.

### Earlier deployment checkpoints (historical; superseded by baseline above)

LATEST EXECUTION: r3 installation was explicitly approved and completed. Full app
readback and protected-region checks passed; one USB-only startup returned stable
IDLE / NOT_CONFIGURED status. Export verified. See
`BASELINE_SCAN_R3_DEPLOYMENT_RESULT.md`. No baseline or motion request was sent.
Next: post-drop supported setup/power-up review, then a separately agreed finite
baseline-only scan. Earlier pending-r3-approval statements below are historical.

NEXT DECISION: review `BASELINE_SCAN_R3_DEPLOYMENT_PROPOSAL.md`. The separate r3
candidate compiles and has host one-shot request/collection/export support tested
in simulation. It adds standalone baseline acquisition after the reported drop,
without a guessed motion command. Installation requires explicit approval; r2
remains installed. The proposed app-only write and USB-only startup do not include
motor-power restoration, baseline acquisition, provisioning or movement.

POWER-LOSS UPDATE: user reports the arm dropped when main power was unplugged;
no damage reported. Support articulated links BEFORE power/torque removal, not
only the base. Earlier poses/clearance assumptions are stale. Continue offline
configuration work; inspect mechanics and reacquire positions before live motion.
See `POWER_LOSS_AND_PROVISIONING_CHECKPOINT.md` for the standing procedure and
filesystem-preserving provisioning preparation. No new device write is approved.

LATEST (supersedes the earlier checkpoints below): the user explicitly approved
the reviewed application image. App-only deployment, byte-exact independent
readback, one USB-only startup and stable read-only diagnostic status succeeded.
The controller is IDLE / NOT_CONFIGURED, with zero records and no storage fault.
See `DIAGNOSTIC_APP_DEPLOYMENT_RESULT_20260918.md` for the verified export.
Next: review exact policy/key provisioning and obtain its separate authorization;
then capture command-correlated servo evidence. No motion was sent, and reverse
motion and physical endpoint accuracy have not been resolved by installation.

### Earlier checkpoints (historical, not current execution instructions)

Next explicit decision: `DIAGNOSTIC_APP_ONLY_DEPLOYMENT_PROPOSAL.md` specifies
the exact layout-preserving app image, affected range, verification, USB-only
startup and recovery artifact. Security and offline filesystem compatibility
checks passed within their stated scope. This app-only stage does not provision
the missing policy/key or authorize motion. Await its separate deployment
approval before any persistent write or application startup.

Latest hardware checkpoint: the authorized single-connection RAM-helper backup
completed successfully. Two independent 4 MB reads match SHA-256
`d9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9`;
disk verification and nonsecret wizard export also passed. See
`CONTROLLER_BACKUP_SESSION_20260918.md` for the two older snapshots and NVS
discrepancy investigation. Installed dual-OTA layout is now known; the separate
default-4mb-no-psram candidate compiles, fits its app slot and has an exactly
matching partition binary. Remaining before deployment: security/configuration
and recovery review, precise proposed writes, and separate explicit approval.
No firmware was deployed; reverse-motion evidence and live validation remain open.

This checkpoint governs the next work; implementation notes below are historical.
The user explicitly authorized the previously described backup/reset inspection,
then requested a plan/goal update before execution. No device access is authorized
for this documentation-only turn. Backup permission is not firmware deployment,
filesystem provisioning, servo-configuration, or new motion authorization.

Physical setup for the backup session is not freshly verified by that permission:
before bootloader entry establish that the arm is supported against falling,
external motor power is disconnected, and USB controller power remains connected.
This is a setup check, not a request to visually confirm a test movement.

Immediate milestone: establish trustworthy command-to-joint-motion evidence, not
perfect accuracy. Earlier user observations confirm physical movement occurred;
the forward reported-position pass does not independently establish fresh encoder
acquisition or tip accuracy. Unchanged reverse reports do not prove no motion.
The feedback ambiguity can affect other joints; it is not inherently elbow-only.

Next work, in order:

1. Execute only the authorized backup/identity inspection under
   `NATIVE_DIAGNOSTICS_BACKUP_AND_FIRST_RUN_PLAYBOOK.md`: re-identify the adapter,
   use bounded reset/read operations, preserve two matching private full-flash
   backups, and retain nonsecret identity/hash evidence. No automatic application
   restart, formatting, provisioning, flashing, or motion.
2. Review actual chip, partitions, installed image and recovery compatibility
   against the retained diagnostic candidate. Present the exact proposed image,
   offsets, required configuration and recovery procedure for separate deployment
   approval. If incompatible, revise the candidate rather than guessing.
3. Following approval and deployment, validate diagnostic startup and acquisition
   on hardware before motion. Distinguish requested target, controller receipt,
   converted/written target, supported target-register readback, and valid fresh
   position reads. Do not substitute an acknowledgment or cached value.
4. Run one bounded forward leg and one bounded reverse leg with before/after
   acquisitions, per-leg endpoint/settling checks and verified exports. A denied
   or failed leg stops the sequence; do not automatically reverse or resend.
   Classify each leg as verified arrival, verified non-arrival, or inconclusive
   using evidence validity as well as the numerical result. Routine human visual
   confirmation is not a success criterion.
5. Correct demonstrated command/acquisition defects before fitting compensation.
   Then progress through finite bidirectional cycles, relevant joint/posture
   coverage, coordinated noncontact approach/press/retract, and short ghost-key
   sequences. Use predeclared tolerances and held-out trials for corrections.

Latest offline checkpoint: 117 focused tests passed; r2 firmware compiled and its
compile export integrity reverified. These do not qualify live hardware. Reverse
motion remains unresolved; camera, physical contact and measured tip accuracy
remain deferred.

Status: software diagnostic rehearsal implemented; installed capability verification
and live reverse-motion recovery remain pending.
Evidence-scoped capability inventory is in
[SERVO_DIAGNOSTIC_CAPABILITIES.md](SERVO_DIAGNOSTIC_CAPABILITIES.md). The offline v1
trace assessor, failure scenarios, wizard rehearsal, and verified export/replay exist.
The v2 offline trace now connects separately timed goal-register and feedback-block
reads to endpoint assessment. Four additional wizard cases cover paired arrival,
valid signed negative position, stale acquisition, and failed feedback. Raw pairs
remain in exports; settling uses position acquisition times, not later target reads.
Existing v1 scenarios and interpretation remain supported. The targeted diagnostic,
register, acquisition, wizard, and UI suite passes 128 tests. All results retain
simulation provenance and grant no hardware progression authority.
Live producer, installed compatibility, and health semantics are still pending.
No firmware changed and no hardware commands were sent during this implementation.
Reporting increment: the wizard now displays desired, transmitted, register-readback
and measured position counts separately, with independent residuals and stage
statuses. Raw health fields preserve validity without invented scaling. A failed
final read cannot be replaced by an earlier successful value. New exports include
the summary and replay recomputes it; historical exports remain supported. The
expanded focused suite passes 135 tests. See the deployment evidence decision in
[SERVO_DIAGNOSTIC_DEPLOYMENT_REVIEW.md](SERVO_DIAGNOSTIC_DEPLOYMENT_REVIEW.md).
This plan supersedes visual confirmation as the required next step. Video remains
optional supporting evidence, not a prerequisite for software work. It does not
release held movement paths or establish that the installed hardware supports
every proposed diagnostic field.

## Goal

Implement `software/docs/COMMAND_TO_SERVO_DIAGNOSTICS_PLAN.md` to establish a
reliable command-to-motion workflow for ghost-keyboard typing and eventual
physical typing and Android tapping. First perform the explicitly authorized
backup/reset and installed-hardware compatibility inspection once the backup
setup is verified; preserve recovery evidence and obtain separate approval before
firmware deployment, provisioning or servo-configuration changes. Validate the
diagnostic path on hardware so each command links requested and transmitted
targets, supported target-register readback, and fresh valid before/after servo
positions. Resolve reverse-motion ambiguity through bounded forward/reverse tests
with automatic per-leg assessment, wizard reporting and reproducible exports,
without routine visual-confirmation requests. Correct demonstrated defects, then
progress to repeatable bidirectional cycles, additional joints, coordinated
noncontact approach/press/retract and short ghost-key sequences. Apply compensation
only within evidence-supported limits after repeatable and held-out tests. Work
autonomously within approved scope; stop affected sequences on uncertain delivery,
invalid feedback, unexpected motion or export failure, without automatic resend
or recovery motion. Do not equate acknowledgments, cached feedback, simulated
passes or model-derived tip positions with verified physical accuracy. Defer
camera integration, physical contact and measured stylus-accuracy claims until
mounting and registration are ready.

## Established baseline

- One local forward elbow correction passed reported/model endpoint criteria.
- Reverse requests at speed 20 and 40 produced unchanged reported positions.
- HTTP receipt and agreement with earlier USB captures do not prove accepted servo
  target or fresh encoder acquisition. Neither actuator failure nor stale feedback
  has been established.
- Existing export assessments correctly mark these unavailable evidence fields.
  They are not yet an instrumented servo diagnostic implementation.
- Preserve original trials and local compensation scope. Keep native T104 held
  and do not deploy the failed coordinated affine model.

## 1. Capability and compatibility investigation

Identify installed controller/firmware where supported, actual servo model and bus
library/protocol. Use retained artifacts and documented read-only interfaces first.
Build a capability matrix with source/version and statuses SUPPORTED, UNSUPPORTED,
UNKNOWN and UNTESTED. Do not equate a reference source feature with installed support.

Assess availability and semantics of goal-position readback, present position,
speed/moving state, torque enable/limit, voltage, temperature, faults, current/load,
operating mode and PID readback. Document units, signedness, register widths,
read failure sentinels and whether any operation has side effects. No arbitrary
register probing, second bus master, PID/torque writes or firmware flashing.

Gate: a reviewed support matrix identifies the minimum achievable evidence path.
If direct readback is unavailable, label it unavailable and present the specific
instrumentation options; do not silently substitute HTTP acknowledgment.

## 2. Versioned evidence contract

Define separate command, dispatch, acquisition and outcome records. Include:

| Record | Required evidence |
| --- | --- |
| Command | Session/boot ID, unique command ID, payload hash, desired joint target, wire target, units, joint and servo mapping, speed/acceleration |
| Controller dispatch | Received/translated/dispatched timestamps or sequence, computed servo counts, actual settings, bus-write return and its documented meaning |
| Acquisition | Joint/servo ID, read start/end or sequence, success/error, raw position count and conversion version; failed reads must not become fresh samples |
| Target readback | Value, units and successful acquisition record if supported; distinguish commanded value from actual register readback |
| Health | Available torque/mode/limits/voltage/temperature/error/load fields, individual validity and units; missing is unknown |
| Outcome | Requested-versus-wire-versus-readback-versus-position comparisons, arrival/settling evidence, fault reason and export verification |

Use device monotonic time plus boot/session identity. Host times describe transport;
do not subtract unrelated host/device clocks without a defined mapping and error
bound. Require samples after dispatch on the device timeline where supported.
Distinguish duplicate/out-of-order samples, reboot, stale acquisition and an actually
stationary joint. A moving flag alone is not proof of completion.

Keep schemas bounded and validate finite values, enums, timestamps, units and IDs.
Retain raw responses with hashes. Diagnostics provide evidence, never movement
authority. Legacy feedback remains usable only with its existing limited claims.

Gate: contract and parser tests reject mismatched, stale, malformed and ambiguous
records without changing the existing motion guards.

## 3. Simulated diagnostic chain

Use injected controller/bus adapters with no native I/O. Model independently:
receipt, translation, bus dispatch, target readback, acquisition and actuator response.
Test normal arrival, controller rejection, bus failure, wrong servo/target, stale
cached position, failed read, delayed arrival, fresh stationary position, missing
readback, torque disabled, reboot, duplicate/out-of-order data and export failure.
Also test direction-dependent deadband and backlash as hypotheses, not claimed causes.

Gate: every case produces the expected evidence-level outcome; unknowns cannot
pass as accepted targets or fresh positions. Simulated passes never qualify hardware.

## 4. Wizard and reproducible exports

Show stages separately: connected, controller receipt, bus dispatch, target readback,
fresh position, endpoint settled, export verified. Display unsupported/unknown fields
explicitly. Show desired and wire residuals separately, raw counts and timing.
Use actionable fault categories without unsupported mechanical diagnoses.

Export raw packets, configuration/capability snapshot, command identity, schema and
conversion versions, chronological samples and outcome to the assigned workspace
export folder. Offline replay must reproduce the assessment without hardware access.
Test UI/service wiring and exported contents, not just helper functions. Do not
display or include network credentials.

Gate: simulated end-to-end wizard cases export and replay matching verdicts;
failures stop progression and do not trigger automatic retries or returns.

## 5. Instrumentation deployment decision

Prefer existing documented read-only support. If firmware changes are necessary,
prepare a minimal additive patch, exact version/board compatibility, backup and
recovery plan, and review boot motion, timing, bus contention and read/write effects.
Obtain explicit deployment authorization before flashing or changing controller or
servo configuration. General approval of this plan does not authorize an unknown
firmware image or unreviewed register changes. Do not bypass missing support by
placing a second active master on the servo bus.

Gate: supported acquisition verified on the actual installation; otherwise report
the exact remaining evidence gap and decision needed. Do not require a video simply
because software implementation has not yet been attempted.

## 6. Diagnose, correct and characterize movement

With usable instrumentation, freeze one finite experiment: fresh baseline and
configuration, command ID, bounded target, observation duration, endpoint/settling
tolerances and trial count. Gather target acceptance, fresh position and health
through onset, travel, settling and hold. Export before the next leg.

If computed targets are wrong, correct conversion. If goal readback differs,
investigate dispatch/addressing/settings. If acquisition fails, repair feedback
before fitting compensation. If fresh position remains away from a confirmed
target, investigate supported mode/torque/error evidence and response behavior.
Do not infer friction or obstruction from raw load alone.

Qualify each direction independently before repeated paired endpoints. Compare
approaches to the same destination, vary one factor at a time, and report onset
delay, settling, signed endpoint error, repeatability and direction dependence.
Freeze interpretable corrections and test separate held-out endpoints. Corrections
must not hide failed reads, uncertain delivery or unsafe paths.

Gate: finite bidirectional cycles pass their predeclared checks and verified exports.

## 7. Resume the full typing path

Qualify remaining joints at the relevant posture, coordinated noncontact
approach/press/retract, a single ghost key and a finite adjacent-key sequence.
Retain per-leg verification and exports throughout. Camera registration, real
stylus offset, flex/backlash metrology, physical key presses and Android contacts
remain later work. Joint diagnostic success is not proof of physical tip accuracy.

## Immediate implementation order

### Target-register mismatch stops native sampling — 2026-09-18 UTC

While backup/reset approval remained pending, source review found that an
otherwise valid acquisition with a goal register different from the actual
transmitted target could continue finite sampling. `DiagnosticSession` now
publishes that raw pair first, then faults with TARGET_READBACK_MISMATCH and
performs no subsequent acquisition or retry. The comparison uses the pinned
adapter's little-endian target register, not a cached position or physical-tip
estimate. This does not establish the real reverse-motion cause or implement
physical braking; the initial command may already have executed.

The new inert test observes one attempted write and two reads, retains the wrong
goal bytes and proves later sample calls perform no I/O. Five initial focused
tests and seven candidate/boot/session/native-pipeline checks passed. A separate
immutable `configured-diagnostic-candidate-r2` includes this fix; the earlier
candidate remains unchanged for audit. Candidate generation/compilation now
accept bounded revision names without overwriting prior builds.

Revision-2 full compile/link passed, verified export:
`wizard-20260918T042624382742Z-c1fc89f2ee4243cc9d6130201c48e193`;
application SHA-256
`b1cc73c97c7dadb626bd42701a547a3f2e275534d31ec859d864f53618ffb4db`.

No serial port, reset, flash read/write or arm movement was performed. Backup-only
bootloader authorization remains pending; this software work is not a substitute
for installed compatibility and recovery evidence.

### Deployment evidence review and backup boundary — 2026-09-18 UTC

Present-device PnP confirms a CP210x adapter on COM7, although Win32_SerialPort
omitted it. No serial port was opened. Local esptool image inspection validates
the ESP32 application checksum/hash; installed chip/flash/partition/PSRAM identity
is still unverified. The candidate's 4 MB huge_app layout must not be assumed to
match the controller. No backup or recovery image currently establishes that match.

Added [backup and first-run playbook](NATIVE_DIAGNOSTICS_BACKUP_AND_FIRST_RUN_PLAYBOOK.md),
separating backup-only authorization, offline compatibility review, separately
authorized deployment/provisioning and the first instrumented command. Raw flash
must stay private because it may contain credentials. No reset, flash operation,
motor command or configuration mutation was performed. The next hardware evidence
step requires an approved backup-only bootloader session with supported arm and
motor supply disconnected; compilation alone does not justify deployment.

### Wizard linked-start review — 2026-09-18 UTC

Added `review_started_servo_run`, an offline wizard action using the assigned
export directory. The service replays claim, prepared delivery, planned capture
and assessment links and retains its own immutable result publication. The UI
shows host delivery separately from endpoint evidence, identifies the pre-send
export, and explicitly says the claim is consumed and automatic resend disabled.
Controller acceptance is not labeled arrival, and successful review is not hardware
qualification. No live discovery/send action is exposed by this increment.

Seven focused tests passed across wizard review, planned review, linked-run replay
and native pipeline. New service/DOM tests cover uncertain delivery with rejected
evidence, altered claims, forged endpoint authority, no runner calls and unchanged
NOT_CONNECTED state. Existing planned-run review remains supported. No hardware
access, firmware deployment or new device configuration occurred.

Next: complete the installed-compatibility/provisioning admission and operator
workflow for an explicitly authorized native run, then qualify the candidate
through reviewed deployment and instrumented hardware evidence. Camera/contact
and physical stylus metrology remain deferred.

### Explicit discovery and send-to-capture export linkage — 2026-09-18 UTC

Added `DiagnosticChallengeReader`, separate from generic telemetry GETs because
challenge discovery initializes the candidate listener. It is one-use, bounded,
validates exact challenge fields and expected boot, and retains response bytes/hash
without claiming authenticated provenance. Generic `DiagnosticHTTPReader` still
rejects the challenge route. Invalid/duplicate JSON, wrong boot/nonce/expiry and
repeated discovery are tested on loopback without arm access.

Added `servo_started_run.py`: verify the prepared export, frozen plan/challenge,
delivery identity and exact exclusive-claim bytes before read-only collection.
Link the resulting planned-run export by hashes and replay all linked evidence.
This contains no sender and cannot retry a command. An uncertain send may be
investigated through later terminal capture; absent/invalid telemetry remains
EVIDENCE_REJECTED. Incomplete/modified claims block reads or replay, not trigger
recovery. Native inert runtime records also pass the new linked assessment/replay.

43 focused tests passed across discovery, prepared send, linked capture, native
runtime and the existing GET adapter. No live network, serial, firmware or servo
operation occurred. Next: expose this reviewed workflow in the wizard with explicit
installed-compatibility/provisioning admission and truthful outcome/status, then
prepare the authorized deployment/hardware evidence step. Do not infer physical
motion from the successful offline chain.

### Verified pre-send records and exclusive challenge claim — 2026-09-18 UTC

Added `servo_prepared_start.py`. Before an injected sender can run, the native v3
plan/challenge/key are validated, plan and public challenge exported and reread,
and an exclusive reservation published with existing write-through durability
primitives. The claim identity is boot+nonce, independent of command or plan edits.
An incomplete, previous or concurrently acquired claim blocks sending; claims
are never automatically erased or repaired. Delivery reports are exported and
verified after the attempt, including recognized uncertain-delivery outcomes.

Tests cover acceptance/uncertainty, repeat attempts via a new sender, concurrent
attempts, incomplete claims, pre-export/verification/reservation failures and
post-send export failure. A real sender runs through this wrapper against loopback
and produces a verified delivery export. 24 focused tests passed. No live device
was contacted. Keys and signed request bodies are not exported.

This is a low-level host composition, not motion admission or an enabled wizard
action. The configured export root must remain stable; moving/deleting claims is
not a retry mechanism. Volume qualification, installed compatibility and reviewed
policy remain prerequisites for physical use. Next: challenge discovery and linked
terminal telemetry collection/replay through the host workflow.

### One-use host start sender — 2026-09-18 UTC

Added `servo_diagnostic_start_http.py`: explicit numeric-LAN/loopback destination,
native v3 plan validation, exact signed POST matching the restricted native parser,
one total response deadline (maximum ten seconds), bounded JSON response parsing
and no redirects/reconnects/retries. The sender consumes an attempt before validation
or I/O. It marks transmission attempted before sendall, since a raised exception
can follow partial delivery. Delivery reports distinguish preparation, connection,
uncertain delivery and controller-reported acceptance/rejection. None grants
endpoint verification or progression. Key/token/request bytes are not returned
in reports. This low-level adapter is not connected to wizard startup or the arm.

59 focused host tests passed across sender, existing GET reader and authorization.
Loopback tests verify exact signature bytes/headers, acceptance/rejection, duplicate
JSON/headers, truncation, redirects, encoded responses and dropped replies. Injected
connect/partial-send failures verify one attempt and retained uncertainty; invalid
preparation makes no socket. Existing read-only reader behavior remains tested.

Next: compose challenge discovery, durable pre-send plan/export reservation, this
one-use sender and terminal telemetry collection into a reviewed host workflow;
test against the native candidate protocol before wizard exposure. No live device
was contacted or provisioned; deployment approval and physical diagnosis remain open.

### Full configured firmware candidate — 2026-09-18 UTC

Generated the separate `configured-diagnostic-candidate` using
`prepare_owner_firmware_candidate.py --configured`; old candidates remain intact.
The sketch replaces legacy startup/loop and binds the static configured runtime
to the actual reference converter, SMS_STS library and ESP32 network stack.
GET `/rocell/diagnostics/challenge` reads local policy/key files in read-only mode,
initializes one challenge/listener and returns the same challenge on repeat reads.
No default files, keys or poses are created. Failed loading cannot fall back to
legacy commands. During request/capture work, the loop prioritizes the runtime and
does not service potentially blocking WebServer reads.

Transport status v3 advertises the authenticated start capability, not availability
or permission; record envelopes remain v2. The host collector now accepts v3
terminal status without granting progression authority. Full native runtime
records pass assessment/export/replay through this schema. New challenge-route
tests verify file failures and repeat-read behavior; boot tests exercise both
legacy-preserved and configured paths and capture priority. A historical test
incorrectly expected the frozen old candidate to match newer source; it now checks
both versions explicitly rather than overwriting old audited inputs.

Validation: 27 focused pytest tests passed. Full candidate compile/link passed;
verified export `wizard-20260918T040423513553Z-e1d5302d2aa2415fa13e83e778fe9349`.
Application SHA-256:
`e0391c059eb88d538d76ac1896169c26926bce6b546d6c1253f02f6f504344c8`.
Flash usage: 1080745 bytes; static RAM: 118400 bytes, leaving a reported 209280
bytes before runtime heap/stack use. This is NOT measured operational headroom.

Next: validate provisioning/revocation and host-side discovery/sign/send/export
against the candidate protocol, review actual board/partition/backup compatibility
and runtime memory, then obtain explicit deployment authorization. No key/policy
was provisioned, firmware uploaded, live listener opened or arm moved. The real
reverse-motion ambiguity is still unresolved.

### Configured runtime owns the complete object graph — 2026-09-18 UTC

Added `configured_diagnostic_runtime.h`. A single-use initializer parses local
policy, checks a separately loaded key and owner fault, validates challenge-time
overflow, then constructs the evidence store, converter, crypto, server/client,
socket adapter, authenticated owner, connection and listener in aligned owned
storage. The temporary key copy is wiped after construction. No callback-local
owner references or automatic reconstruction are used. Runtime status and record
access expose the same owned capture; failed initialization reports FAULT.

Five inert runtime cases cover full capture, bad policy, missing key, listener
failure and an existing owner fault. The successful run retains 11 records after
22 reads and one simulated write, despite clearing the caller's policy/key copies.
Its actual status/records pass host endpoint assessment and verified export/replay.
Three focused pytest tests passed. No real key/configuration was provisioned and
no network listener or arm was accessed.

ESP32 static-runtime compile/link passed; verified export:
`wizard-20260918T035912387826Z-2d2d8a5874e2433f8d12d31ff90f22e9`.
Application SHA-256:
`f842ee5705e630a879017622a6f5178ba437ca88e01acc21f37c4a86d51982d6`.

Next: bind this runtime into a distinct full firmware candidate's startup and
challenge/status/record routes, with bounded local file loading and explicit
configuration failure reporting. Review full-candidate memory and recovery before
requesting deployment approval. Physical reverse-motion ambiguity remains open.

### Explicit local policy and key loader — 2026-09-18 UTC

Added `controller_diagnostic_config.h`: bounded exact-schema policy parsing with
conversion identity matching, elbow bounds, seven joint windows, port and lease.
No key is embedded in policy JSON. A separate read-only exact-32-byte key loader
closes files, clears stale key state, rejects zero/public fixture keys and provides
no fallback. No real configuration/key file was provisioned; format validation is
not physical admission, and nonzero bytes alone do not prove key entropy.

Two focused pytest tests passed: the new parser/key matrix and the existing full
native request/listener/capture matrix. Native configuration tests reject invalid
types/ranges, duplicate/extra fields, oversize input, wrong conversion and failed
key reads. Next: use these validated inputs for static runtime allocation and a
distinct integrated candidate, with challenge/status routing and memory review.
Compatibility/recovery review and explicit deployment approval remain mandatory.

ESP32 compile/link passed after moving the FS include ahead of Arduino-generated
prototypes. Verified successful export:
`wizard-20260918T035517308250Z-8f84cfce03a24b80babe38bba0344963`;
application SHA-256
`851d17b81e42c2e3fd7724b2f1859c3873a6d1064642fb99196144d0f638286f`.
The preceding failed compile is retained separately as
`wizard-20260918T035357189553Z-ca7b92fe042b489f82b9c65b8b7a5dd8`.

### One-connection listener orchestration — 2026-09-18 UTC

Added `start_listener.h`, connecting a listener, retained accepted client,
nonblocking request session and authenticated command owner. Listener startup is
one-use and deadline-bound. The listening socket closes before the first accepted
request is processed; no timeout/failure automatically accepts a replacement.
After request completion, polling advances finite servo acquisition to CAPTURED
or FAULT. CAPTURED remains raw evidence, not arrival/accuracy/export authority.

The actual native parser/authentication/admission/write/sampling chain now runs
through an inert listener to all three feedback pairs (22 reads, one write).
Listener startup failure, pre-accept expiry, reversed clock and reply loss are
tested; terminal polling/start calls produce no extra reads or accepts. Four
focused pytest tests passed. No arm access, live listener or deployment occurred.

ESP32 compile/link passed with verified export
`wizard-20260918T035039975001Z-6e69e5a5cb5c49ac995fd08b628b8e08`;
application SHA-256
`0a5884f72bbfa33645a3755f8825d3cca81f6d5515672c60c7408e022a41d7e6`.

Still required: approved configuration/key loading and static runtime allocation,
challenge/status/read routing, full distinct candidate generation, runtime memory
and compatibility/recovery review, then explicit firmware deployment authorization.
The compile-only fixture's port 8081 is not a commissioned network setting.

### Nonblocking accepted-connection driver — 2026-09-18 UTC

Added `start_socket_session.h` and `start_socket_esp32.h`. A connection performs
one bounded nonblocking read per poll, enforces silent-client deadlines, feeds the
strict parser, and drains already-available excess input before admission. A
terminal result gets one reply attempt and connection close. An absent, partial
or would-block reply faults the owner without command retry; no subsequent
sampling occurs through that owner. A 202 response means admitted locally, not
endpoint arrival or verified host receipt.

Reviewed pinned ESP32 3.0.7 NetworkClient source: normal write uses select/retry;
the dedicated adapter instead uses fd recv/send with MSG_DONTWAIT and does not mix
raw input with buffered NetworkClient reads. No listener is opened by these types.
Seven inert connection cases cover acceptance, disconnect, read failure, silent
timeout and three reply-loss forms. Two focused pytest tests passed, including
the expanded native pipeline matrix. ESP32 compile/link passed, verified export:
`wizard-20260918T034645202967Z-b1397dad2f0e40d78a8a60ef3a65f957`.
Application SHA-256:
`9f74d941ea0b228c3884958f940fe8befc09060741c502cd6631da3b5310eba6`.

Next: integrate static owner/connection allocation and listener into a distinct
candidate, with explicit controller policy and separately provisioned key; assess
runtime memory, compatibility and recovery before requesting deployment approval.
These components were not installed, no live connection was made, and the physical
reverse-motion cause remains unresolved.

### Raw HTTP framing connected to authenticated owner — 2026-09-18 UTC

Added `start_http_request.h`, a bounded raw-byte HTTP/1.1 start parser feeding the
existing single-use body receiver and authenticated owner. Only the exact POST
path and required four headers are accepted; duplicate/ambiguous framing,
unsupported headers, transfer encoding, invalid lengths, truncated/excess body,
timeout, clock reversal and disconnect fail before bus activity. One deadline
covers headers plus body. No unbounded WebServer body parse is used in this path.

The native integration matrix exercises complete and byte-fragmented signed
requests plus malformed framing under both fragmentation patterns. Initial tests
found a valid-header terminator bug; corrected implementation passes. Three
focused pytest tests passed. ESP32 compile/link also passed; verified export:
`wizard-20260918T034343307735Z-352a2b2901af407fac141aa5e730171f`.
Application SHA-256:
`dd7ac1bbb6788f3dd03af41906abe24ddab1ad335638de5b6b47c277aaf8b3d2`.
This remains socket-independent software: no live
route, deployment or physical command was issued. Next is long-lived embedded
allocation and socket-loop integration with provisioning/controller policy, then
compatibility/recovery review and explicit deployment authorization.

### Bounded start-body admission — 2026-09-18 UTC

Added `start_request_body.h`: one-use, fixed-capacity reception for the signed
binary envelope, with a total reception budget capped at three seconds. It checks
declared length before accepting bytes, rejects overflow/truncation/backward time,
consumes the attempt before invoking the authenticated owner, and erases retained
token bytes after terminal processing. Disconnect or reception failure faults the
owner. Chunk receipt alone cannot start servo acquisition or dispatch.

Twelve native integration cases exercise chunked success, incomplete/excess input,
timeout during receipt/finish, clock reversal, disconnect, undersized/oversized
declarations, zero/excessive time budgets and deadline overflow. Repeated calls
cannot restart. Failed cases have zero bus reads/writes. Three focused pytest tests
passed (including the expanded native matrices); ESP32 compile/link passed with
verified export `wizard-20260918T033952311603Z-9ed1a476d5e2489181337ffa1c525317`.
Application SHA-256:
`3b7768d46af576b5b703878b53148cccf32d6add341e09e7f31f1b1092ac4bb1`.

This is the body-reception boundary, not an HTTP parser or deployed route. The
eventual transport must reject ambiguous HTTP framing before begin, enforce the
deadline when a client stops sending, and call abort on disconnect. The receiver's
16507-byte buffer must be long-lived/static, not allocated on a callback stack.
Next remains actual embedded allocation, provisioning/controller policy, bounded
HTTP integration, compatibility/recovery review and explicit deployment approval.
No arm access or firmware/configuration changes occurred.

### Authenticated owner lifecycle and truthful status — 2026-09-18 UTC

Added `authenticated_diagnostic_owner.h`, a noncopyable, single-lifetime composition
of authorization and admitted session. It consumes admission attempts, retains the
first owner failure, exposes pre-session failures as FAULT rather than IDLE, and
prevents subsequent reads/writes after export failure, interference, external owner
fault or evidence-store failure. Repeated starts never retry or discard evidence.
References to the bus, clock, sink, converter and crypto must outlive the owner;
the eventual embedded instance must use static/long-lived storage.

Extracted `diagnostic_status_json.h` for the existing GET status route and the new
owner. The complete native-to-host test now assesses/exports/replays actual native
status and records, not a synthetic successful status. Ten inert integration modes
cover success and admission/write/sampling-stop failures. Five focused pytest tests
passed. ESP32 compile/link passed with verified evidence:
`wizard-20260918T033712564201Z-c81316b51d994c28998bfb787b0126b4`;
application SHA-256
`5e8c649112a8d4a91a6ca3f2719e8bcdc112a757e82687e7d1748ada0c55b195`.

No start endpoint, key provisioning, actual embedded owner allocation, firmware
deployment or hardware test was performed. `start_supported` remains false and
RAM capture is not durable export. Next: embed the owner with controller-owned
configuration and bounded ingress, verify runtime memory and compatibility, then
obtain explicit deployment authorization. Existing generated candidates were not
overwritten. Camera, contact and physical accuracy remain deferred.

### Complete native admission/session library path — 2026-09-18 UTC

Added `admitted_session.h` and connected it in the native integration test to the
authenticated v3 owner. The actual sequence now performs whole-arm read/export,
owned-request consistency checks, native receipt, no-write conversion, elbow
baseline read/export, mandatory final freshness/fault guard, one write hook and
finite feedback sampling. Evidence capacity is checked before admission reads.

The end-to-end native fixture starts at 2128 counts and reports 2132 only after
the simulated write. Its complete emitted records, without synthetic prefixes,
pass the host endpoint assessment and verified planned export/replay. Fault cases
cover whole-arm read failure, stale data during conversion publication, owner
fault, baseline publication failure and failed ACK. Earlier faults yield zero
writes; failed ACK yields one attempt and no retry. No physical accuracy follows.

Validation: five focused pytest tests passed, with the native test containing the
complete pipeline and fault matrix. ESP32 compile/link probe passed; verified export:
`wizard-20260918T032908941843Z-6a09f5ed6b984979b1a9567b3a22d68a`.
Application SHA-256:
`712567339c58c6dd130a99aca429d09e2338895c4ff4dd9592f52d5e3aba0aaf`.
All bus data was inert; no arm access, upload or servo configuration change occurred.

Next: embed the composed owner with coherent status/read routes and static lifetime,
review key/policy provisioning and runtime memory, and prepare the explicit
compatibility/backup/deployment decision. This is tested library composition, not
an enabled or installed start endpoint. Camera/contact/metrology remain deferred.

### Freshness at the final write boundary — 2026-09-18 UTC

Threaded an owner-supplied final predicate through receipt/session into the actual
`WritePosEx` hook. It checks at the recorded write-start timestamp after conversion
evidence publication. Denial consumes the attempt, records `PREWRITE_REJECTED`,
and leaves no fabricated dispatch/ACK records. No later sample or retry occurs.

Validation: eight focused pytest tests passed across two runs. The new native
harness acquires all seven baseline pairs, then tests normal ordering, expiry
during conversion-record publication, expired authorization, owner fault and
evidence-publication failure. Rejected cases produce zero writes; repeat attempts
stay rejected. All bus interactions use inert test data.

ESP32 compile/link probe passed; verified export:
`wizard-20260918T032417941229Z-48ff421872d745d68e8e18dd8e45b4d9`.
Application SHA-256:
`962aaf31ecb6240f96e5b6b0cd236c3e3300b4a7542847e3846b410e50d05bec`.
No hardware access, deployment or servo configuration change occurred.

Next: compose the real whole-arm admission/export callback and mandatory v3 guard
with native session start. Legacy interfaces still allow an empty guard; the v3
adapter must not. Rejected partial records are retained but host cause-specific
classification remains follow-up work. Start remains unsupported.

### Native v3 and approved-policy binding — 2026-09-18 UTC

Upgraded host signing and native parsing/binding for v3. Numeric joint-window
arrays are bounded lexically and validated semantically. V3 requires an explicit
controller-owned whole-arm policy; all seven windows, tolerances and timing limits
must match exactly. Signed requests cannot widen admission limits. The owner copies
the approved policy and reserves eight prefix records, leaving eight sample pairs.
Legacy v2 behavior remains available for offline/reference compatibility.

Validation: 36 focused tests passed across two runs. Native host-signed v3 tests
cover matched policy, missing approval, signed policy changes and mutation of the
caller's policy after owner construction; admission/start callbacks remain inert.
No live pose policy is approved by these fixtures. ESP32 compile/link probe passed;
verified export `wizard-20260918T032058327271Z-e29184b1d5234e3bac9bcf155a225e74`.
Application SHA-256:
`f2c7014f3ea26371103eb0c04c91b60ad7966a12f1e1813199d638a915bb2d3f`.
No hardware access, upload or servo configuration change occurred.

Next: connect the actual seven-servo read/export admission callback to the owner,
and enforce freshness at the final native write boundary, then retain a complete
authenticated native session through host replay. Start remains unsupported until
integration, compatibility and explicit deployment review are complete.

### Frozen whole-arm plan and host session integration — 2026-09-18 UTC

Added session-plan v3 with immutable whole-arm policy plus elbow baseline policy.
Its eight-record prefix explicitly reserves capacity for authorization and the
aggregate seven-servo baseline, permitting at most eight sample pairs. Larger
plans fail instead of silently losing samples. Legacy v1/v2 behavior is retained.

Collection, complete-session assessment, export/replay and wizard reporting now
accept the whole-arm prefix. The host requires its frozen policy/identities,
checks scan completion before command receipt and freshness at actual write start,
and retains faults and no-clearance/no-progression distinctions. Missing or
contradictory baseline evidence is rejected. The native/session integration test
uses a simulated authorization/whole-arm prefix, not live physical evidence.

Validation: 30 focused session/transport/wizard tests passed. No firmware change,
arm access, servo configuration change or movement occurred in this checkpoint.

Next: upgrade native v3 parsing and signing, enforce controller-owned whole-arm
policy equivalence, and wire read/export/final freshness into native start. Current
native parser and signer intentionally still reject v3; no endpoint is enabled.
Partial v3 failure classification remains separate follow-up work.

### Whole-arm raw evidence and independent host assessment — 2026-09-18 UTC

Implemented compact whole-arm serialization retaining all goal/feedback bytes,
read statuses/counts/errors, sequence/timing, policy and controller decision. A
maximum-length accepted record fits the existing 2048-byte slot. Serialization
failure refuses output rather than truncating evidence. The aggregate record will
require one additional reserved slot when integrated with the start owner.

Added a host checker against independent frozen policy and write-start time. It
reuses the read-pair validator, checks each joint window/target/position/moving flag,
and recomputes scan duration and oldest-read age. Invalid/incomplete/rejected data
cannot become admission evidence. No physical clearance or progression is granted.

Validation: 22 focused tests passed, plus a rerun of the native/host round-trip
test after adding verified standalone export/re-read. Native success/failure and
maximum-size records, policy/identity/sequence/time mutations and moving flags are
covered. ESP32 compile/link probe succeeded; verified export:
`wizard-20260918T031350757228Z-1d71a5c77d6247559760b51f0451df71`.
Application SHA-256:
`8561099494c79a367a3457397e57f49625e74e756b5ec341e3c5f9c4b64ada9f`.
No hardware access, upload or servo configuration change occurred.

Next: bind whole-arm policy into the frozen session plan, add the aggregate record
to collection/assessment, and integrate native admission plus final pre-write
freshness with the correct record budget. Live start remains unsupported.

### Fresh seven-servo baseline reader — 2026-09-18 UTC

Implemented a one-use read-only scan of all seven servo IDs (11–17), retaining
fresh goal/feedback bytes and per-read status/timing. Checks use controller-supplied
joint count windows, tracking tolerance, moving flags, pair/scan budgets and oldest
read age. Invalid/stale data stops subsequent joint reads; no retries occur. The
pre-write freshness API irreversibly rejects expired or backward time. Sequential
joint reads are not simultaneous or proof of physical clearance.

Validation: four focused pytest tests passed, including the new compiled native
harness with 43 baseline scenarios plus owner/payload regression checks. ESP32
compile/link probe succeeded with verified export:
`wizard-20260918T030948935443Z-8c6614b3b0754750882a136e0375fa0b`.
Application SHA-256:
`838ef6555e4af717814ff0215265f85669724252a1a511ac026c547e9e1db878`.
All bus activity was inert test data; no arm I/O, upload or configuration change.

Next: serialize retained whole-arm evidence with explicit storage budgeting,
independently assess it on the host, and connect admission/final freshness to the
single-owner native start. Test count windows are not approved live pose bounds.
The diagnostic endpoint remains start-disabled pending integration and deployment
review; the reverse-motion hardware cause remains unresolved.

### Host authorization-prefix collection and review — 2026-09-18 UTC

Added boot-bound transport support for the pre-admission authorization record.
The host checks controller/receipt identities, exact frozen-plan hash, supported
phase, sample capacity, and receipt/write-start times within the authorization
window. Complete and supported partial-failure assessments retain a non-secret
`start_record`; export/replay and the wizard preserve it without changing credential
redaction. Missing/contradictory evidence remains rejected, and faults stay faults.

Validation: 39 focused tests passed, including an authorization prefix combined
with actual inert native session output through collection, assessment, export,
offline replay, service and UI. Tests reject changed hashes/identities/phase/claims,
invalid time windows and transport/receipt identity mismatches. The prefix is
simulated in this host integration test, not a hardware authentication claim.

No arm access, firmware upload or servo configuration change occurred. Unsigned
transport cannot prove authenticated device provenance; the UI explicitly calls
the record controller-reported and grants no movement or endpoint authority.

Next: fresh whole-arm admission and actual native start callback wiring, retaining
the plan/start identity through that full native path, then compatibility and
explicit deployment review. Do not enable start merely because exports now parse.

### Composed authenticated start owner — 2026-09-18 UTC

Added `authorized_start.h`: authentication -> native plan/binding -> reserved
authorization evidence -> admission callback -> expiry recheck -> one start
callback. Requests are copied after binding; the owner never refunds a consumed
attempt. The pre-admission record binds boot/command identity and the exact plan
hash without publishing keys/tokens. The extra record reduces this path's maximum
sample pairs to nine; oversized requests are rejected rather than shortened.

Validation: 27 focused tests passed. The native test exercises successful ordering,
invalid authentication/plan, evidence failure, admission denial, expiry during
admission, and failed/uncertain start result. All reject repeated attempts. Real
native crypto/parsing/reference conversion are combined with inert callbacks;
these tests do not perform hardware admission or dispatch.

ESP32 compile/link probe succeeded; verified export:
`wizard-20260918T030225539441Z-62312f0d2fe646b295f7ebc157fd568c`.
Application SHA-256:
`762dc9dbfe2ffd322b9f2a9f093863c86b3484520404a0f6f0d02363a32bcb6e`.
No arm access, deployment or configuration change occurred.

Next: support the authorization prefix in host exports/assessment, implement fresh
whole-arm admission and native callback wiring, then complete explicit deployment
review. The composed library is not a live endpoint; `start_supported` remains false.

### Native original-payload and conversion binding — 2026-09-18 UTC

Completed the binding stage after native structural validation: SHA-256 over the
retained payload-object bytes, strict bounded base64 decoding, original-command
receipt parsing and field comparison, then wire/desired count checks through the
reviewed no-write reference converter. Exact original bytes remain owned for later
receipt capture only after successful binding. No mismatched count is corrected
silently, and this stage does not perform fresh hardware admission or dispatch.

Validation: 27 focused tests passed. Native binding tests use Windows SHA-256 and
manifest-verified reference conversion function bodies, exercise 19 positive/
negative payload variants, and assert zero servo writes with shared goal restored.
The fixture 1.7 radians converts to 2132 counts; this is reference arithmetic,
not a live position measurement or proof of the reverse-motion root cause.

ESP32 compile/link probe succeeded with verified export:
`wizard-20260918T025759123397Z-1b90a83bdb174413aaa4c1728657a9f9`.
Probe application SHA-256:
`432327fb1e54f16cab541b6e517b4b8cdb4e1b863be15ee51c87a1c69f9570b7`.
No upload, serial/network arm query, motion or servo configuration change occurred.

Next: compose the authenticated envelope and bound plan into a one-use owner path,
retain start/plan identity, and require fresh whole-arm admission before dispatch.
The actual endpoint remains unsupported pending this integration and deployment
review. See `DIAGNOSTIC_START_AUTHORIZATION.md` for exact implemented boundaries.

### Native plan structure and limits — 2026-09-18 UTC

Added a bounded lexical preflight before ArduinoJson, preventing duplicate-key
collapse, unsupported nested values, trailing input and oversized structures.
The native structural validator requires exact fields, native origin, known
boot/conversion identity, elbow mapping, rad/count units, finite profile-range
values, matching requested payload angle, and compatible bounded schedules and
baseline policies. It deliberately returns no dispatch-ready command.

Validation: 30 focused tests passed, including actual C++ parsing of a valid host
plan and 33 malformed variants. ESP32 compile/link probe succeeded; verified export:
`wizard-20260918T025418336327Z-9043b11dee6743bab150f672eb3db1f8`.
Probe application SHA-256:
`6472f1a6d46a6a813527d8776b5c7dea0b1986432202e754b6e4ef500c598bca`.
No hardware I/O, upload, configuration change or motion occurred.

Remaining immediately before native start integration: decode and bind original
payload bytes, recompute their canonical payload hash, compare actual conversion
with expected counts, and perform fresh whole-arm/clearance admission. Structural
validation alone is not semantic completion, canonical-number proof, or permission
to move. See `DIAGNOSTIC_START_AUTHORIZATION.md` for the exact stage boundary.

### Native authenticated-envelope checkpoint — 2026-09-18 UTC

Implemented the native single-use envelope gate and ESP32 mbedTLS HMAC adapter.
The gate consumes attempts before verification, enforces bounded framing and the
issued challenge/clock window, and compares the full tag without early exit.
It returns authenticated bytes only, never a dispatch or clearance decision.

Validation: 23 focused tests passed. The compiled C++ gate processes 19 request
variants signed by Python using actual Windows BCrypt verification; tests cover
tampering, signed wrong challenges/framing, expiry, replay, invalid key/lease and
provider failure. Authenticated malformed plan bytes are deliberately shown to
require a subsequent semantic validator. No hardware authentication claim follows.

ESP32 compile/link probe succeeded and export verified:
`wizard-20260918T024958349085Z-43e5f3e264e94cae8f1f22e9eef1a9d6`.
Probe application SHA-256:
`b89d027b89f13d918ce5bec71703bfc7ee85c8d52c421ec943d6ec037711fc1d`.
The probe does not execute the gate in setup/loop. No deployment or arm I/O occurred.

Next: bounded native plan parsing with origin/identity/units/limits checks, then
whole-arm admission and owner-only start integration. Continue to advertise
`start_supported=false` until the complete path is ready for deployment review.

### Single-use start authorization contract — 2026-09-18 UTC

Implemented exact-byte HMAC-SHA256 signing and an offline single-owner verification
model binding session-plan v2 to a controller boot, random challenge, and bounded
controller-clock expiry. Attempts consume the reference gate before verification;
valid authentication still provides no movement or clearance authority. Native
mode rejects simulation-origin plans. Keys are separate from Wi-Fi credentials,
and no key provisioning, network start, or firmware change was performed.

Validation: 28 authorization/plan tests passed, covering modified fields, wrong
key/challenge, expiry, clock rewind, replay, signed malformed plans, canonical
bytes, and missing baseline binding. See `DIAGNOSTIC_START_AUTHORIZATION.md` for
wire format, trust boundaries, and remaining native work. This is a reference
contract, not an installed or complete authenticated command interface.

Next: native verification against shared vectors, bounded request parsing, and
whole-arm admission before integrating the start handler. Keep start unsupported
until those checks and deployment review are complete.

### Diagnostic-only boot candidate — 2026-09-18 UTC

Removed inherited startup side effects from a separate candidate entry path:
no format-on-mount-failure, PID/torque reset, move-init/final positioning, stored
boot mission playback, credential logging, or legacy command-route servicing.
Existing reference/owner/baseline candidates remain unchanged. The diagnostic
candidate reads bounded existing STA configuration, connects with a deadline,
initializes UART transport without servo transactions, and exposes only diagnostic
read routes. Failure leaves diagnostic service inactive; no fallback opens control.

Review also confirmed that the reference emergency-stop function re-enables torque
after ten seconds. The diagnostic-only route set does not expose it. This is not
a replacement physical stop implementation or proof that reset cannot cause motion.

Validation: 31 focused tests passed, including seven scenarios executing the real
boot header with inert dependencies. Full ESP32 build completed and its export
verified: `wizard-20260918T024358863983Z-307aa5b17f81466b830930273a028d09`.
Application SHA-256:
`2105194e08ef040bccefc0b6900945e56a3f3e17174dc88b52673a72a3bb7f0d`.
No upload, arm I/O, or servo configuration change occurred. Compile success does
not establish runtime stack margin, installed compatibility, or physical behavior.

Next: authenticated single-use diagnostic start and whole-arm admission, followed
by the explicit compatibility/backup/deployment decision. Read the expanded
`SERVO_DIAGNOSTIC_DEPLOYMENT_REVIEW.md` before any deployment request.

### Bounded read-only host transport — 2026-09-17

Implemented a concrete HTTP reader for the existing collection/export pipeline.
It only permits the two diagnostic GET routes and record indexes 0–15, uses an
explicit numeric LAN address without DNS/proxies, and enforces a total request
deadline plus strict header/body budgets. Redirects, non-200 responses, ambiguous
framing, encoding, truncation, and unsupported routes fail closed; transport
failure latches the reader and never triggers retry or a legacy command fallback.

Validation: 53 focused transport/snapshot/export/planned-run tests passed, including
24 real-loopback and request-validation tests. No arm connection, serial access,
movement, firmware deployment, or configuration write occurred. This removes the
previous injected-reader-only gap but does not establish installed capability or
authenticate LAN evidence. See `DIAGNOSTIC_TRANSPORT_CANDIDATE.md` for usage and limits.

Next remains reviewed single-use start admission and compatibility/deployment
preparation. Do not bypass explicit deployment authorization or interpret these
transport tests as resolution of the live reverse-motion discrepancy.

### Partial admission failure reporting — 2026-09-17

The host now independently explains supported receipt-plus-baseline fault captures:
failed register acquisition, out-of-profile values, or moving/tracking-not-settled
feedback. It checks frozen policy, payload/identity correlation, read chronology,
and raw register values. Unsupported or contradictory explanations remain rejected.
No dispatch record is fabricated; absent dispatch evidence is explicitly not proof
of no physical motion. These outcomes never authorize progression or retry.

Planned-run v2 exports preserve the partial assessment for deterministic replay;
v1 replay keeps its original rejection semantics. The wizard displays the supported
failure separately from endpoint and acknowledgment verification. Native inert tests
cover failed reads and moving feedback through export, replay, service, and rendering;
altered reasons, accepted flags, and policy limits remain rejected.

This closes a reporting gap, not the live reverse-motion investigation. No hardware
I/O, deployment, or configuration writes were performed. Next is the controlled
start protocol and deployment/compatibility review, not more uninstrumented motion.

### Host baseline verification checkpoint — 2026-09-17

Implemented independent host assessment of the candidate's pre-write elbow
baseline. Session-plan v2 freezes maximum displacement, tracking tolerance,
read-pair duration, and age at the actual write start before collection. The
host decodes retained goal/position/moving bytes, checks command identity and
chronology, and recomputes admission rather than trusting `accepted`. Missing
baseline evidence, changed limits, stale reads, motion, and excessive displacement
reject assessment. Historical v1 plans remain supported without retroactively
claiming baseline verification.

The planned-run export/replay path retains these expectations and assessments.
Wizard offline review now displays baseline position, goal, age, and independent
check status separately from the overall session result. A passed baseline does
not override a session fault or establish physical clearance.

Validation: 30 focused tests passed, including compiled native C++ records through
host assessment, immutable plan, export/replay, service review, and UI rendering.
Injected accepted-flag/limit changes, stale evidence, moving feedback, and excessive
displacement are rejected. These are inert simulated tests; no live arm commands,
firmware deployment, or servo configuration changes were performed.

Next: improve reporting for partial admission failures; review authenticated,
single-use diagnostic start and compatibility/deployment requirements. Actual
reverse-motion diagnosis remains open until authorized instrumented hardware
evidence exists. Do not treat these software checks as endpoint accuracy proof or
permission for contact, camera integration, or compensation.

Native baseline integration: `baseline-candidate` now reads a fresh servo-14
baseline inside admission, publishes read pair plus selected limits/reason, then
rechecks age and owner fault immediately before returning to dispatch. Invalid
or moving feedback prevents any write. Six boundary slots are reserved, limiting
this revision to ten pairs; old candidate directories remain untouched. The host
collector now retains baseline records and checks receipt/servo identity. Twenty
focused tests pass; the full ESP32 build succeeded with verified export:
`wizard-20260918T022218388776Z-58eb429b5d32431d83b59549927fc41c`.
Remaining: host re-evaluation of baseline limits/freshness against write time,
frozen baseline-policy binding, full-run wizard assessment for the new layout,
runtime stack/boot review and authorized deployment. No hardware was accessed.

Fresh baseline gate: `fresh_elbow_baseline.h` performs new guarded goal/feedback
reads for servo 14, retains failed acquisition evidence, and requires explicit
read-span/age, target delta and tracking-error limits. It rejects moving flags,
out-of-profile counts, byte-order mismatch, stale/invalid reads and excessive
requested delta without issuing any write. Seven inert scenarios pass. The gate
is one-use; zero moving flag is not proof of full-arm stationarity or clearance.
Initial diagnostic policy bounds cap delta at 64 counts and read age/span at one
second; callers must select tighter reviewed values as appropriate. This gate is
not yet wired into the native start path: next integrate its retained baseline,
storage reservation and immediate pre-write age check, then rebuild the candidate.

Wizard planned-run review: `review_planned_servo_run` now accepts a saved report
folder from the assigned export root, verifies linked artifacts and recomputes
the assessment offline. Its dedicated UI separates exact receipt, bus ACK,
endpoint result, plan hash and replay verification. Successful review is not
successful movement; rejected evidence and assessed results both show hardware
NOT QUALIFIED. Service-owned publication checks prevent substitute results.
Seventeen wizard/UI/integration tests pass, including actual C++ session records
through plan-first export and the real service/render path. Missing exports fail
without hardware access. Browser/manual visual QA is not claimed. Native-start
admission, deployment review and live diagnostic evidence still remain.

Plan-first collection runner: `servo_planned_run.py` freezes and exports the plan,
verifies retained canonical content before the first GET, collects/verifies raw
transport evidence, and publishes a linked assessment report. Offline replay
verifies both referenced exports and recomputes the outcome. Incomplete boundary
evidence is retained as `EVIDENCE_REJECTED`, never success or a retry. Tests verify
zero reads after plan verification failure, mutation isolation during collection,
actual C++ record collection/replay and linked-artifact tamper rejection. The
19-test focused runner/plan/export integration suite passes. Export file hashes
and canonical plan hashes are deliberately distinct because the exporter formats
JSON. Next expose planned-run review in wizard UI; no live adapter/start enabled.

Frozen session expectations: `servo_session_plan.py` snapshots exact sent bytes,
independent expected command, endpoint policy and sampling schedule into immutable
canonical bytes with SHA256. Validation limits captures to the current 11-pair
candidate capacity. Planned assessment rejects controller schedule differences
and revalidates persisted plans rather than trusting a supplied hash. Seven tests
pass, including mutation isolation, invalid schedules and actual C++ session
assessment bound to a plan hash. The production collection runner must still
persist/freeze this plan BEFORE collecting; a plan created afterward does not
prove a predeclared test. Wizard integration and combined run export remain next.

Combined session assessment: `servo_session_assessment.py` now binds exact receipt,
converted target/settings/schedule, raw write evidence and hook chronology to
fresh acquisition-pair endpoint assessment. The requested command and endpoint
policy come from independent host expectations, never the observed result.
Actual C++ ReceivedSession records pass this combined assessment after durable
export/replay. Corrupt conversion, missing expected samples, clock/status or ACK
contradictions are rejected; a terminal session fault overrides a matching endpoint
with `SESSION_FAULT`. All components remain visible separately and no progression,
provenance or physical-accuracy authority is granted. Native wizard presentation,
frozen campaign-policy binding and incomplete/fault-only boundary reporting remain.

Host receipt validation: `servo_controller_receipt.py` checks exact sent bytes,
strict T101 payload, command/boot identity, elbow mapping, settings and receipt-to-
dispatch chronology. It retains requested versus parsed radians and reports the
parser delta without compensation or motion authority. Contradictory parsed-value
representations are rejected. Thirteen focused tests pass, including consumption
of the actual C++ ReceivedSession receipt against independently supplied sent
bytes and its real emitted dispatch. Integration into the combined native-run
assessment and wizard reporting remains; successful receipt is not motor motion.

Full native receipt candidate: generate with `prepare_owner_firmware_candidate.py
--received`, compile target `received-candidate`. It integrates the real reference
converter, ReceivedSession, ESP32 monotonic clock, bounded evidence store, timed
polling and read-only HTTP retrieval. Internal start has no registered external
route. Once owned, JSON commands fault the sequence and are rejected (the existing
emergency handler remains callable); direct ESP-NOW pose commands are rejected;
ordinary constant/background feedback paths are skipped. Ownership never releases
automatically. Actual native-header inert tests cover missing boot identity, owner
fault, interference, denied bounds and duplicate starts; generated wiring checks
verify ingress/background guards. Four focused tests pass. Full ESP32 build passed:
`wizard-20260918T020604142941Z-521281c438384debb7e66524a7b115a1`.
Still required: fresh-baseline/workspace admission, authenticated start protocol,
host receipt/endpoint assessment integration, wizard-native controls, full ingress
runtime tests and deployment/boot review. Reference startup motion/configuration
remains unchanged. No flash, live query, servo configuration or movement occurred.

Reference conversion integration: `reference_elbow_admission.h` calls the pinned
`RoArmM3_elbowJointCtrlRad` with returnType=0 and restores its temporary shared
goal afterward. Explicit angle/speed/acceleration limits reject requests before
conversion; no fabricated standalone kinematic conversion replaces vendor code.
The test extracts exact conversion functions from hash-verified staged source,
compiles them, tests finite/range/settings rejection and target restoration, and
then runs the real converter inside ReceivedSession. A 1.7-radian fixture produces
2132 counts in both conversion and dispatch, with exactly one inert bus write.
Three focused integration tests pass. Bounds in these tests are synthetic, not
newly approved hardware limits. This adapter still requires native candidate
compilation, fresh-baseline/clearance admission and exclusive owner integration;
it does not establish any measured spatial accuracy or authorize a live trial.

Receipt/session integration: `received_session.h` now retains the original
receipt before admission/conversion, reserves all five boundary records plus
pairs, then performs the one write and timed reads through the existing session.
It carries the receipt's owned identities forward. Reuse, insufficient storage
and denied admission cause no extra write. Actual C++ output including receipt
passes through host collection, disk export and replay; 28 focused tests pass.
The integrated ESP32 probe builds; verified export:
`wizard-20260918T015958343216Z-9aa4a3a1a7bb4a37b53796859a438a05`.
Admission/conversion is still injected and simulated. Native reference conversion
with reviewed movement bounds, all-ingress exclusion, complete host receipt
validation and full candidate wiring remain required. A 16-record store can now
hold at most 11 pairs when the receipt is included. No live start route or upload.

Controller receipt capture: `diagnostic_receipt.h` retains exact accepted payload
bytes, boot/command identity, device receipt time and actual parsed T101 values.
Initial support is elbow joint 3 only; this is structural parsing, not workspace
or speed-envelope admission. One-use input rejects duplicates, trailing objects,
nested values, invalid settings and reuse. Host tests compile the actual pinned
ArduinoJson parser; native ESP32 probe also passes. Latest verified build:
`wizard-20260918T015631043553Z-92767364a85c426fb1c44dd30b63761d`.
Testing exposed an Arduino `radians` macro naming conflict (fixed) and float
quantization of 1.7 to 1.7000000476837158 in the pinned host parser. Exact payload
and a 17-digit parsed-value text field preserve that distinction; this tiny
difference is not an established reverse-motion cause. Still connect receipt
publication to session reservation, actual conversion/admission and host validation.

Timed sampling: the session now records requested sample count, interval,
lateness allowance and pair budget in `rocell.converted_command.v2`. Polls before
the next due time perform no bus reads; missed deadlines and reversed clocks
latch faults. Next due time follows actual acquisition finish, preventing catch-up
bursts. Default interval is one second, configurable 1 ms–60 s (a contract bound,
not a hardware rate recommendation); lateness allowance is one interval.
Callers must distinguish a not-due false return from `Fault` using session state.
Timing tests cover early polls, late polls, clock reversal and no burst/rewrite;
the C++ record-to-host/export integration still passes. The updated native probe
compiles; verified export `wizard-20260918T015221818199Z-b5c473ee800b4ec7a90a58b912a6a636`.
Previously generated full transport candidates remain immutable and do not yet
contain this scheduling increment. Next integrate command receipt/admission and
the timed session into the next candidate revision; do not deploy old snapshots.

Durable transport export/replay: `servo_transport_export.py` now preserves each
bounded response's exact bytes in base64 with SHA256, verifies the workspace
export, then replays the original GET sequence and recomputes its collection
summary. Missing/extra/reordered responses, hash changes, altered authority or
summary, malformed encoding and export-verification failures cannot report success.
The actual C++ finite-session output is tested through injected HTTP envelopes,
collection, disk export and replay without reconstructing its servo records.
Twenty-nine focused session/HTTP/collector/export tests pass. No network adapter
is constructed, device accessed or motion authorized. Collection consistency is
distinct from endpoint assessment and durable export does not yet acknowledge
the controller or release another movement. Next: original command/session binding
and native admission/scheduling, then wizard-native collection integration.

Boot-instance transport binding: v2 status and indexed records now carry one
128-bit instance ID generated at registration after Wi-Fi initialization. Host
collection rejects mixed instances and same-count reboot replacements; v1 remains
explicitly unbound. Eighteen transport tests plus 34 related regressions pass.
Separate `transport-v2-candidate` full ESP32 compilation succeeded; export
`wizard-20260918T014820781886Z-a05179047f97469689573aa9d92e0d28` is verified.
The original candidate is preserved. This is correlation, not authentication.
Command-session identity and original receipt binding, timed admission, durable
export and actual diagnostic starts remain unfinished. No upload or live query.

Host transport collection: `servo_transport_snapshot.py` reads only the two
candidate GET paths through an injected bounded reader. It requires terminal
status, bounds count/response size, checks indexed record ordering and supplied
boot/command/servo identities, and rejects status changes during collection.
It retains exact response bytes/hashes and grants neither endpoint assessment
nor motion authority. Eight tests cover valid/idle snapshots, active sessions,
excess record count, reordering, mismatched identity, changed status and missing
responses without retries. No live network adapter is constructed or called.
The v1 status/hook records lack complete session identity, so unchanged status is
not proof against reboot/replacement; native identity binding must precede live use.

Native read-only transport candidate now integrates the finite session/store and
GET status/indexed-record handlers into the source-verified firmware. Actual
handler host tests pass and the full ESP32 candidate compiles. Verified export:
`wizard-20260918T014319155000Z-053925ff6b084512b1631a622833bc77`.
See [DIAGNOSTIC_TRANSPORT_CANDIDATE.md](DIAGNOSTIC_TRANSPORT_CANDIDATE.md) for routes,
memory budget and remaining boundaries. No start endpoint exists yet; ordinary
commands are not instrumented by this candidate. Next bind original receipt,
session identity, admission and timed sampling before enabling diagnostic starts.
Reference boot/configuration behavior remains, so this image is not deployable.

Bounded evidence retention: `evidence_store.h` is an append-only, single-owner RAM
sink with indexed repeatable reads, copied records, no eviction/reset, and latched
overflow failure. Sessions reserve four boundary records plus all requested pairs
before dispatch; insufficient capacity causes zero writes. Native storage must
remain off the small task stack and must not be mistaken for persistent export.
The actual C++ session's retained dispatch/write/pairs now enter Python assessment
directly (only the requested-command envelope is a labeled synthetic fixture).
Three valid timed pairs meet synthetic endpoint criteria with no motion authority.
Twenty focused producer/session/rehearsal tests pass. Full ESP32 probe compilation
with the concrete store succeeded; verified export:
`wizard-20260918T014019513628Z-f9fae3f28bba487499302b02b0c21511`.
Still required: native receipt and session-status binding, HTTP transport of
retained records, ingress admission, scheduling, and host durable export acknowledgment.

Finite session integration: `diagnostic_session.h` connects converted-command
retention, exactly one write hook, raw write/outcome publication and bounded fresh
read pairs. It stops on duplicate starts, interfering commands, read faults or
publication failure; rejection before dispatch causes zero writes. Unsupported
byte order is rejected rather than mislabeled. `Captured` only means the bounded
sample set was retained, not endpoint settlement or host disk export. Ten inert
host scenarios pass and the session compiles against pinned native `SMS_STS` in
the non-executing ESP32 probe. Verified build:
`wizard-20260918T013834009778Z-49500cefd21a4760b7f2c51ae93521eb`.
Remaining native work: original receipt/payload binding, actual bounded evidence
sink and transport, owner admission at every ingress, sample cadence/deadline,
session-status export, and candidate-sketch integration. The session primitive
does not itself intercept other firmware callers or enforce a physical envelope.

Write-hook build review: the inert ESP32 probe now instantiates the wrapper
against actual pinned `SMS_STS`, not just a fake interface. Compile succeeded;
verified export `wizard-20260918T013617765097Z-358c050ea31d48cfa5a4c05d18f0ae98`.
No probe function executes from setup/loop. A separate hook-outcome record now
retains raw before/after clocks, whether a write was attempted, and stop status;
ACK success cannot conceal a reversed-clock fault. Six host cases pass, including
the clock fault and input rejection. Outcome-to-session identity binding and
host ingestion remain required before using this record for native progression.
The actual elbow replacement point is `RoArmM3_elbowJointCtrlRad` after the
existing conversion/clamp and in place of its one `st.WritePosEx` call. Admission
must distinguish controlled diagnostic execution from boot and ordinary callers;
do not globally replace that call without this session boundary. No deployment.

Candidate write hook: `reference_write_capture.h` now provides a one-use wrapper
that replaces (does not accompany) a pinned `WritePosEx` call, retaining actual
post-conversion target/settings, immediate ACK result and post-write clock
boundary. It rejects out-of-range single-turn targets before I/O and forbids
reuse, clears unavailable error semantics, and stops capture on clock reversal.
Host tests use an inert library for success, servo error, missing ACK, disabled
ACK, reversed clock and invalid target; actual emitted JSON enters the host
validator. This wrapper is not yet wired into the candidate sketch, and caller
admission/receipt identity, clock-fault export detail and session transport remain
required. It is not a physical safety envelope or an installed fix.

Write-evidence export integration: named wizard rehearsals now attach
`servo-write-evidence.json`, retain its canonical hash and classification, and
replay the attachment against both its deterministic simulation fixture and the
dispatch identity. Historical bundles without write metadata remain readable;
partial metadata, contradictory evidence and attachment tampering are rejected.
This is explicitly synthetic evidence, never fabricated for hardware traces.
The producer/write/rehearsal suite passes 36 tests; wizard/UI/decoder/v2 regression
passes 42 tests. Verified failure-case export:
`wizard-20260918T013317216454Z-e499331821cb4859b7989cdfa17591b7`.
Despite matching simulated endpoint counts, its failed write remains
`BUS_DISPATCH_NOT_VERIFIED` with no retry/progression authority. Next integrate
native receipt/write hooks and session transport; no installed firmware or live
motion claim follows from these export tests.

Raw write-evidence milestone: `CommandCapture::encode_write_evidence` emits a
separate `rocell.servo_write_evidence.v1` record retaining library return, device
error, ACK policy, boot/command/servo identity and dispatch timestamp. The host
`servo_write_evidence.py` recomputes classification and rejects contradictions or
misbound records. A failed ACK is not proof that a write never reached the servo;
no retry or movement authority is granted. The actual C++ output is consumed by
the Python validator. Twenty focused producer, owner and write-contract tests
pass. This additive record does not change historical trace schemas or replay.
It still needs native hook integration and attachment to wizard/export replay;
the existing ESP32 candidate build predates this serialization increment.

Native owner-handoff milestone: generated a separate source-verified candidate,
moved ESP-NOW parsing/dispatch into the main-loop owner, and added fault admission.
The full candidate ESP32 build succeeded; verified export
`wizard-20260918T012510140256Z-d6d784c7cf51430f868b895f2674e2bf`.
Actual owner-header host tests cover five inert scenarios; producer/concurrency
tests also pass. See the ownership review for availability and serial-reporting
limitations. Next integrate command-correlated diagnostic receipt/write/sampling
and complete evidence transport. This image is not approved or deployed.

Build milestone: workspace-isolated Arduino CLI/ESP32 3.0.7 toolchain now builds
both the inert diagnostic probe and the January reference with guarded SCS reads.
Resolved the INA219_WE API mismatch by pinning 1.3.8. Verified logs/artifact hashes
and reproduction commands are in
[FIRMWARE_COMPILE_BASELINE.md](FIRMWARE_COMPILE_BASELINE.md).
This is a compile baseline, not an integrated diagnostic image or deployment
approval. Next wire owner handoff/capture into a separate candidate and rebuild.

Ownership review: pinned ESP-NOW callbacks directly execute motion/general JSON
handlers and mutate shared JSON, so main-loop diagnostic ownership alone is not
sufficient. Added a bounded callback-copy handoff with host-tested FIFO, fault
latching and 100 concurrent-producer trials. Native wiring is specified in
[SERVO_BUS_OWNERSHIP_REVIEW.md](SERVO_BUS_OWNERSHIP_REVIEW.md), not yet applied to
the firmware. This is a reference concurrency risk, not an installed-cause claim.

Protocol/adapter increment: tested eight truncation points, checksum corruption,
stale error flags and a separate subsequent valid read against original/candidate
vendor code. The new guarded read adapter passed seven cases including both target
and feedback block widths. Export
`wizard-20260918T010841190393Z-cce9a90947dd459f858ad359c6497356` includes
harness/adapter/source hashes. The 29 focused producer/host contract regressions
also pass. Still needed: native single-owner integration, delayed-packet/flush
semantics, full command evidence transport and pinned ESP32 build. No hardware
was accessed; neither installed root cause nor physical accuracy is established.

Native-adapter review found and reproduced a reference protocol defect: `SCS::Read`
accepts wrong-servo and malformed-length replies with valid checksums. The actual
pinned source was compiled against an in-memory transport; a candidate response
ID/length check rejected both cases without rejecting the valid packet. Verified
export `wizard-20260918T010622609994Z-a504a8aa51b447359993742f2b1eefda` retains
source hashes and results. Before native binding, expand this protocol regression
and use a reviewed identity-validating read path. This finding is not proof of the
installed cause and does not authorize firmware deployment.

Command capture increment: one-use C++ capture copies command identity and actual
dispatch settings/result, snapshots acquired records, bounds sample count/timing,
and stops acquisition on uncertain delivery or faults. Its dispatch and read JSON
pass through the host decoder without rebuilding those fields in Python. The
51-test producer/v2/rehearsal/wizard/pair suite passes. Native receipt and conversion
hooks, exclusive bus integration, raw-write-evidence transport, full serialization
and ESP32 build/deployment review remain required. No live movement was attempted.

Serialization increment: the portable producer now emits acquisition-pair JSON
with bounded identity fields, explicit byte order and failure-null semantics.
Cross-language testing consumes emitted success/failure records directly and tests
small-buffer refusal and malformed identity rejection. The outer command/dispatch
envelope, native ownership and deployed build remain unfinished; no hardware
authority follows from a valid serialized pair.

Producer increment: `software/firmware/diagnostics/servo_evidence.h` now provides
portable C++ write-result classification and independently timed read-pair capture.
Injected-bus C++ assertions run on the host; actual captured output enters the
Python v2 decoder in a cross-language test. The 51-test producer/v2/rehearsal/wizard/
pair suite passes. The reviewed library can return write success without an ACK;
the producer therefore keeps ACK policy and error separate and does not promote
unknown/disabled ACKs to verified dispatch. See the firmware diagnostics README
for remaining native binding, serialization, concurrency and deployment work.
No complete ESP32 build or installed producer is claimed.

Latest evidence: the January 2026 official archive closely matches the installed
page (one numeric default differs) and uses direct HTTP feedback. Its failed-read
path retains old positions and its public response omits acquisition validity.
See [LEGACY_FIRMWARE_DIAGNOSTIC_FINDINGS.md](LEGACY_FIRMWARE_DIAGNOSTIC_FINDINGS.md)
and the verified report referenced there. Next prepare the additive producer against
that pinned reference, preserving actual bus addresses and individual read status;
do not substitute more host-side position polling. This narrows the candidate
implementation but does not establish the installed fault or authorize flashing.

Start with the support matrix and evidence schema, then injected simulation and
wizard/export integration. Review deployment only after these are tested. No more
uninstrumented reverse speed/amplitude trials as an automatic next action.
