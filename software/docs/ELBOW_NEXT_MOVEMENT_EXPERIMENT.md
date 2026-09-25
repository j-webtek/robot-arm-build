# Next elbow experiment: displacement before gain tuning

Status: offline proposal, not authority to install, provision, recover, or move.
Date: 2026-09-19. Follow COMMAND_TO_SERVO_DIAGNOSTICS_PLAN.md.

## Latest hardware checkpoint — r19 installed

### Current visual reference and pose reconciliation

The user supplied five photos in attachment group
`DA002487-D0AD-4D46-8A39-953591C05ADC` showing the current folded arm, with the
gripper near the board, and asked us to assume they can observe positional changes.
Do not request routine per-leg visual attestations. The photos do not establish
exact clearance, registered joint coordinates, support forces, or temporal stability.

Verified retained reference source maps ID12 to SHOULDER_DRIVING_SERVO_ID and ID13
to SHOULDER_DRIVEN_SERVO_ID. Its shoulder command computes opposing offsets around
the midpoint. Observed sums remained4116 while positions changed+92/-92; that is
consistent with a coupled shoulder angle change, not two unrelated joint failures.
Do not assume the observed sum should be4096 or recalibrate offsets from this alone.
Updated history export: `wizard-20260919T133703886709Z-ad6bc49eb20541d689f13fa24a3bf8d4`.

Pose reconciliation sequence:

1. Keep the stopped recovery and prior policy immutable. No retry, return, torque
   enable or recentering follows from the photos.
2. Review an available acquisition-only route before using it. It must not prepare
   a motion owner, change torque/gains, erase the fault or hide a controller reset.
   If the installed image lacks that route, prepare the minimal change offline;
   deployment/startup requires separate approval, not a disguised read-only action.
3. Collect several bounded, fresh full-joint snapshots with validity and timestamps.
   Compare shoulder positions and their sum, torque/mode, elbow goal residual and
   all neighboring drift. A single old snapshot cannot certify present stability.
4. If stable, draft a new pose registration with explicit changed fields and a
   reason for each. Keep two-count arrival/drift, speed20 and acceleration1.
   Do not use wider limits as a substitute for physical path clearance review.
5. Select the smallest useful noncontact elbow path from the newly registered pose.
   The existing +12 test does not fit anchor2899; changing magnitude/direction is
   a new experiment, not successful completion of the old one.
6. Request approval for the exact policy installation/startup and finite movement
   scope. Export and independently replay each endpoint; stop on uncertainty.

Until step3 is satisfied, no replacement pose is installed or considered verified.

Acquisition-route review: r19 registers hold, pair, elbow configuration, elbow gain
and recovery routes. The legacy baseline-only source exists in its folder but is
not registered; GET evidence routes return retained data, not fresh positions.
No live probe, reset or alternative command was sent to bypass this limitation.

Offline component `pose_observation_sequence.h` now captures three full-joint
position/goal/control snapshots with at least100ms spacing, 100ms per-scan limit,
10ms read-pair limit and a1s overall polling deadline. It performs no movement,
torque writes, policy admission, reset or retry and retains partial failure data.
A compiled test with the movement method deleted covers success, all84 possible
read-failure positions, deadline expiry and clock reversal. This is a component,
not an installed route or a completed stability assessment. Next integrate exclusive
bus ownership, bounded retained-record serialization and host stability replay;
review a separate candidate before requesting deployment approval.

Serialization/replay checkpoint: `pose_observation_json.h` emits bounded raw
snapshot records plus a separate acquisition-only terminal. Host
`pose_observation_review.py` validates identities, read validity, order, timing,
register ranges and all-joint sampled drift; reports STABLE_SAMPLED_POSE,
POSE_NOT_STABLE or INCONCLUSIVE. It never grants movement authority. A compiled
native-to-Python test covers real emitted records, undersized buffers, changed
boot/index/timing, incomplete records, invalid reads and drift. Exclusive bus-owner
and HTTP registration, durable host capture/export and candidate build remain
unfinished. No deployment or hardware access occurred.

Acquisition-owner checkpoint: `pose_observation_owner.h` reserves through a caller
callback before polling, accepts one matching-boot request, retains up to four
records (including partial failure), and never releases/rearms itself. Native
tests cover denied reservation, competing claims, repeated requests, no reads at
admission, no writes, full success and retained failed scans. Two compiled tests
pass with the bus motion method deleted. Board callbacks must still enforce the
reservation against every actual ingress; this unit test alone does not establish
installed exclusivity. HTTP wiring, durable host export and candidate review remain.

HTTP interface checkpoint: `pose_observation_routes.h` adds a bounded POST queue
request containing boot_id/scan_id and GET record indices0..3. Capture handlers
perform no acquisition themselves; the single-loop owner polls separately.
Malformed/duplicate fields are rejected, repeated capture is denied by the owner,
active acquisitions cannot be read as completed, and serialization faults return
an error. Three compiled tests pass across acquisition, owner and route behavior.
This generic route is not yet registered on the board. Actual ingress exclusion,
host capture/export, candidate build and deployment approval remain outstanding.

Durable replay checkpoint: `pose_observation_export.py` retains bounded raw record
bytes with hashes, explicit simulation/device origin and boot/scan identity. It
reopens the export and rebuilds the assessment; a modified assessment is rejected
even when republished with a valid file manifest. Native emitted snapshots pass
through this export/replay path in tests. Three compiled integration tests pass.
The network acquisition driver and board registration are still not implemented;
this does not claim fresh hardware sampling or authorize firmware changes.

Board-integration source checkpoint: optional ROCELL_POSE_OBSERVATION guards now
exclude hold preparation, pair preparation, recovery preparation and configuration/
gain bus reads once pose observation reserves ownership. The board adapter accepts
observation only before any motion-owner reservation and allocates the retained
record storage with checked allocation. It cannot observe after this boot's failed
recovery without a separately approved new startup. No existing fault is cleared.
Four host-compiled tests pass; an outdated board fixture was repaired to model its
already-present configuration/gain routes. Macro-enabled whole-board testing,
boot-loop wiring, immutable candidate staging/build and network capture remain.

R20 candidate staged from source-verified r19;100 files unchanged,11 changed/added.
Stage: `wizard-20260919T135052098154Z-43e75eefc68347ac8afce0906db64190`.
Full ESP32 compile passed with pose routes enabled and main-loop polling connected:
`wizard-20260919T135231068472Z-4ae0d39f68234b01abf2c114d5bf0a4c`.
App SHA `188e7a96ef11e516655f2f8b9e3efeecb4947a501bdc1ae2beda5cffb5da9572`.
Bootloader/partition hashes match the existing profile. Eighteen focused host
tests passed. No application deployment, startup, provisioning or movement occurred;
installed r19 remains faulted after the consumed recovery attempt. Network capture,
complete enabled-board behavioral tests and receipt-bound deployment review remain
before a live observation request. A successful build alone is not authorization.

Host network checkpoint: `pose_observation_capture.py` sends at most one POST and
four retained GETs, with fixed routes, numeric LAN destination, total per-exchange
deadline and bounded header/body sizes. It reserves the boot attempt before POST,
exports every completed response before the next request, and never retries.
Acquisition waits1.25s beyond the native1s budget instead of polling until success.
Ten tests pass across loopback exact requests, injected connection failures at
each exchange, consumed-boot rejection, native serialization and export replay.
No live acquisition was performed. Receipt-bound CLI and enabled-board behavior
tests remain before requesting r20 installation/startup and observation approval.

Receipt/launcher checkpoint: r20 installation profile pins app1127072bytes,
predecessor r19 and unchanged negative-six filesystem; local preflight passed
without reserving a journal or opening hardware. Candidate review:
`wizard-20260919T135301585758Z-88cd5f3bb83a49ffa7373e76fd7ef4ff`.
`run_pose_observation.py` requires an r20 startup receipt and checks fresh same-boot
IDLE before the one acquisition request. It does not load credentials or change
policy. Sixty-five focused tests passed, including invalid startup receipts and
missing-installation rejection before network access. Enabled-board behavioral
coverage remains before deployment approval; nothing has been installed or reset.

### Subsequent approved one-shot recovery: stopped before actuation

Trial `wizard-20260919T133346292433Z-9709fecbea69477f887e131be75ebbde`
on the same r19 boot received command acceptance, captured one fresh complete
snapshot, and terminated FAULT / HOLD_POSE_OR_CONTROL_INVALID with action_count0.
Transport was fully captured and stable; endpoint assessment remains INCONCLUSIVE
because no recovery hold was executed. No retry, reset or follow-on command was sent.

Raw transport: `wizard-20260919T133346177163Z-d82078c8739845daa3260dac030ae548`.
Assessment: `wizard-20260919T133346234592Z-1a9cb46d14b24c8cafdd1c70bdd5f16c`.
Valid position reads were [2047,2487,1629,2899,2035,2041,2054] for IDs11..17.
Servo12 is33 counts above its maximum2454; servo13 is34 below its minimum1663.
Those out-of-window readings explain the native pose rejection. Elbow14 measured
2899 with goal2903 (residual4), inside its window, so the six-count elbow allowance
was not the failing condition. These readings do not establish why the neighboring
joints changed, nor prove the physical location of the stylus.

This boot's recovery attempt is consumed. Do not repeat or enlarge policy limits
automatically. Next investigate the saved neighboring-joint history and determine
whether supported-pose registration must be updated under separate approval.
At measured anchor2899, the proposed +12 target2911 also exceeds the existing
maximum2909; that experiment is currently NOT_ELIGIBLE even if recovery were to
succeed. Do not silently substitute a different starting point or clip the target.

### Offline history findings

Reproducible comparison: `software/scripts/review_recovery_pose_history.py`.
Export: `wizard-20260919T133536846795Z-ea4f7ff481bd47afa726c15675115de3`.
Six forward and21 return snapshots show servo12 fixed at2395 and servo13 fixed
at1721 throughout the earlier r16 trial. The new r19 snapshot shows2487 and1629:
changes of +92 and -92 counts during an unobserved interval spanning startups.
Both joints reported torque0, mode0 and goal0 in every compared snapshot, including
the earlier successful negative elbow leg. Elbow torque alone was1. Thus these
neighbors were not reported as actively torque-held at the sampled times.

This is consistent with passive settling or repositioning, but does not prove
either cause, continuous torque state, or the time of change. The paired changes
must not be treated as elbow command compensation. No sampled neighbor movement
occurred during the earlier bounded trial; no servo write occurred in the failed
recovery. Review support/pose before accepting new windows. Do not enable neighbor
torque at saved goal0: any such later operation needs fresh target initialization,
coupled-joint compatibility review and separate configuration/movement approval.

Next decision: establish whether the supported pose was intentionally changed.
If unchanged, investigate mechanical support and coupled-joint behavior rather
than masking the shift with wider limits. If intentionally changed and stable,
prepare a narrowly scoped replacement pose policy offline, including updated
path eligibility; install only with separate approval. The single recovery
approval has been consumed and does not authorize a new startup or reattempt.

Under explicit one-installation/one-startup approval, r19 was installed app-only
at 0x10000. Full application readback matched SHA
`18d5586456f4d3552b88edcd3770c6c97677aacfce66eb6dcc33cd2b2914f8ce`;
protected regions were unchanged, including the negative-six settings and
credentials. Exactly one startup was issued; no recovery or servo command was
sent. This supersedes earlier statements below that r17 remains installed.

Installation evidence: `wizard-20260919T132826491747Z-9762a3ebda5948b5917c05ebc11e197b`.
Read-only startup observation: `wizard-20260919T132826831978Z-865b870a1c5643a1b199d246d7b1b992`.
Boot: `5211fb335a4453ce73865c2cd1b89bed`. Stable IDLE/NOT_CONFIGURED,
zero records, no storage fault, pair protocol observed. Free internal heap210236,
minimum206520, largest block110580 bytes; not proof of total runtime sufficiency.
The local six-count recovery preflight passes against this receipt without key
extraction, reservation or hardware access. Fresh positions remain unknown.

Next live step requires separate one-shot six-count recovery approval. It will
read fresh positions, refuse invalid/out-of-policy evidence, and only if eligible
target the measured elbow position; no pair, retry or automatic return is included.

## Decision

Do not change PID gains yet. First test whether the positive-direction shortfall
persists at a larger displacement, with the same speed, acceleration and gains.
One successful negative leg and multiple positive shortfalls do not justify a
global coordinate offset. Gain readings are now retained-copy verified, so no
more gain acquisition or firmware changes solely for reading gains are needed.

## Evidence used

- Negative 2903 to 2897 arrived exactly. Positive return requested/readback 2903,
  measured endpoint 2897. Earlier +6 tests ended five counts short.
- P=32, D=32, I=0 from servo14 registers21/22/23, validated original and retained
  responses. Retrieval export:
  `wizard-20260919T130037515734Z-79eaa1fc12d1488089be0dbf31b17ccb`.
- Last endpoint and six-count residual are historical, not a current pose.
- Installed r17 is idle after its diagnostic startup; neither startup nor gain
  reads acquired fresh joint positions. Latest pair settings remain offset -6.
- Current elbow window is [2893,2909], arrival tolerance2, speed20, acceleration1.
- Existing recovery admission is initial residual <=5. Existing ordinary hold
  does not authorize accepting a six-count mismatch.

## 1. Prepare a distinct recovery profile offline

### Latest checkpoint: corrected r19 reviewed offline

R19 supersedes the rejected r18 transport envelope without modifying the retained
r18 artifact. Stage export:
`wizard-20260919T131522535307Z-5af3541f96c7439bbe16defdd5a591cb`.
Successful compile:
`wizard-20260919T131705393017Z-1368c2e209a64eb98a090bbd66a78b08`.
Offline artifact/backup review:
`wizard-20260919T131942528137Z-def7200ffc95431e902944799a079231`.
App SHA: `18d5586456f4d3552b88edcd3770c6c97677aacfce66eb6dcc33cd2b2914f8ce`;
1,122,896 bytes, 187,824 bytes application-slot headroom. Bootloader and partition
hashes match the retained profile. Original backup pair and recovery slot match.
Largest reviewed individual stack frame is 432 bytes, **not** a total-stack or
runtime-resource guarantee. This review does not authorize deployment.

Transport capture, export and independent replay now explicitly select the
six-count profile. The recovery coordinator binds this profile to the r19
installation/startup receipt; it cannot use an r16/r17 receipt. Missing installation
evidence stops before network access. Both profiles retain the shared one-use
boot claim, no retries, and no automatic next movement. Native fixtures and
coordinator fault tests remain simulations, not observed hardware recovery.

Installer/startup CLI wiring is now complete offline. The only r19 upgrade edge
is from r17; r18 remains rejected. Local preflight verified the exact app,
predecessor, backup and preserved negative-six filesystem hashes without opening
serial/network connections or reserving a deployment journal. Sixty-four focused
installer, startup receipt, recovery CLI and coordinator tests passed. This is
not a live startup or runtime-memory test.

Remaining before live use: obtain separate app-only installation/startup and
recovery approval. Current hardware remains r17 with unchanged negative-six
settings. The later +12 pair still requires its own settings review/approval.

### Operator sequence (commands are not approval)

From the workspace root, repeat the read-only local check if artifacts change:

```powershell
.\.venv\Scripts\python.exe software/scripts/deploy_reviewed_diagnostic_app.py --revision 19 --preflight-only
```

After explicit approval for **one r19 app-only installation and one startup**,
verify the connected controller identity and run the install once with
`--authorized-app-only-and-startup` instead of `--preflight-only`. The installer
checks actual predecessor and filesystem bytes before writing, verifies full app
readback and protected regions, and journals one startup. Never retry a consumed
journal or recover automatically. No filesystem replacement or gain change is
included. Controller reset may affect physical holding; links must be supported.

After a successful installation only, obtain the read-only startup receipt:

```powershell
.\.venv\Scripts\python.exe software/scripts/observe_r10_startup.py --revision 19
```

Require stable IDLE, the expected boot and valid installation evidence. With its
export ID, run the local recovery check using `run_supported_recovery.py
--profile six_count --startup-export <ID> --preflight-only`. A missing r19 receipt
fails before reading the private key image or connecting. Only after separate
one-shot recovery approval replace that last flag with
`--authorized-supported-recovery`; the profile must remain `six_count`.
That trial does not start a pair or authorize subsequent movement.

The following checkpoints are historical implementation notes; this latest
checkpoint supersedes their remaining-work statements.

Implementation checkpoint: the development recovery core now has a separate
`SixCountRecoveryAdmission` construction tag. The original
`SupportedRecoveryAdmission` remains capped at five; ordinary hold admission and
two-count final arrival are unchanged. Native scripted-bus tests cover +/-6
acceptance, +/-7 rejection, every acquisition-read failure, lost ACK, unchanged
goal readback, neighbor drift, moving flags, disabled torque and no retries.
The original recovery/ordinary-hold regressions are run separately as well.

This is a core-only implementation, not a firmware candidate or installed route.
Follow-up implementation: signed policy/plan identity, authenticated runtime
selection, distinct record schemas and host replay/export are now implemented
offline. `rocell.six_count_recovery_*` is separate from the original
`rocell.supported_recovery_*` identity. The runtime limit is compile-time selected,
restricted to the reviewed five/six-count profiles, and defaults remain five.
Ordinary hold and legacy recovery reject a signed six-count plan. Both recovery
profiles still refuse automatic handoff into a pair.

Fifty targeted tests passed across real HMAC/native scripted-bus execution,
six-count boundaries, old recovery, configured runtime, host model and signing.
Native records replayed as a six-count recovery with original goal2729 and fresh
hold target2723 in the simulation fixture; a seven-count residual and altered
plan/schema are rejected. No physical recovery is implied by these fixtures.

Remaining before deployment review: host frozen-plan/sender selection for the new
profile, explicit board route/command identity, complete candidate build/resource
review and receipt-bound launch wiring. No candidate is installed. No new recovery,
startup, provisioning or motion occurred.

### Sender/board integration checkpoint

The frozen-plan signer and sender now take explicit `profile='six_count'`; defaults
still select the old profile. Loopback tests cover exact signed requests, rejected
commands, one-use consumption and send/export failures without a robot connection.
Board composition explicitly selects limit6 and command `r18-six-count-recovery`.

Offline r18 staged from verified r17:
`wizard-20260919T131057013441Z-92661117b5104715b4b810c4b4b4e341`.
Full build passed:
`wizard-20260919T131244088434Z-ee249802e67b474aa33b159fd0e8052b`;
app SHA `88d4e4a1a3e542974da60b06856d66476b0a6c6d65210e2a2f07d506c3999db5`.
**Do not deploy this r18 artifact:** subsequent integration review found old
transport-envelope schemas around new six-count record bodies.

The development headers and host collector now use explicit matching six-count
transport schemas. A native scripted network/servo test collects all eight records
and replays the endpoint; the old collector intentionally rejects that profile.
Fourteen targeted transport/sender/legacy tests passed after this correction.
R18 is preserved unchanged as evidence. Next: finish profile-aware transport export
replay, stage a corrected successor, build/review it, and complete receipt-bound
launcher tests before seeking deployment authority. No installation or live command
occurred during these changes; actual controller remains r17.

Implement a separately identified profile that permits an initial residual of at
most six counts, justified by the recorded failed return. Do not overwrite the
old five-count profile or reinterpret its historical exports. This changes only
the initial recovery admission, not final arrival, neighbor drift, joint windows,
speed, acceleration, torque state, or freshness requirements.

After separate deployment/recovery approval, obtain fresh stationary snapshots.
Require all existing neighbor and timing checks and elbow torque already enabled.
If the residual is above six, the pose is out of range, motion is detected, or a
read is invalid: no hold write. Stop and export the reason.

The one recovery target must equal the freshly measured elbow position, never the
old goal2903, a guessed anchor2897, or an overshoot. Verify goal readback, stationary
arrival within two counts and unchanged neighbors. Recovery can physically move
the actuator despite targeting its measured position; do not call it read-only.
No torque release, power-cycle, calibration, automatic resend or automatic return.

## 2. Prepare one positive 12-count pair

Signed-path integration: real HMAC admission and the native socket owner accept
the distinct +12 experiment IDs and offset12, publish the expected forward target,
and stop at AWAITING_EXPORT. A correctly signed offset6 request against that
configuration is rejected before a pair write. The translated synthetic fixture
uses2723->2735, not a claimed live endpoint. Four authenticated integration tests
passed, including legacy direct/socket/powered fixtures. These changes affect
test code only; no installation, private staging, recovery or motion occurred.

Native pair-owner simulation now exercises anchors2893..2897 with +12 and a
verified return under the exact elbow window [2893,2909], and rejects anchor2898
before any write. Stuck feedback, lost ACK and export failure stop the sequence
without return; waiting alone cannot trigger return. Fifty-five tests passed
across the compiled native fixture and host displacement review. This tests the
actual owner logic with a synthetic instant-response bus, not real servo response,
signed network admission or current hardware eligibility. No production firmware
header or installed artifact changed for these tests.

Public settings draft exported (not privately staged or installed):
`wizard-20260919T132939872453Z-625555464d7b42929a7fe85120c3ecae`.
Canonical settings SHA:
`67f476d121102fa1a52088b8e96b6ab2841e1c1ba1602f69cb560487b7864863`.
Reproduce with `software/scripts/draft_positive12_settings.py`. Settings-to-plan
matching now compares canonical field types, rejecting floating-point values
that Python previously considered equal to integer counts. Seventy-three tests
passed across settings, displacement review and the finite pair runner, including
source replay rejection and no return after failed arrival/export. No hardware
was contacted in this preparation step. The installed settings remain -6.

Offline implementation: `elbow_displacement_experiment.py` defines distinct
`elbow-plus12-forward` / `elbow-plus12-return` settings and reviews the actual
A -> A+12 -> A path through the existing independently replayed preparation.
The permitted illustrative anchors are 2893 through 2897 inclusive; an anchor of
2898 is in the joint window but cannot fit this experiment. No clipping, negative
target requirement, policy widening or fresh-pose assumption is introduced.
Eighty-two tests passed across this review, existing finite pair execution and
legacy matched-direction admission. The latter stays unchanged. These tests do
not prove current hardware eligibility or install the +12 settings.

The new review is preparation only: live +12 admission still needs the separately
reviewed settings installation, r19 ordinary-hold startup linkage, and fresh
native handoff. Do not bypass those by calling the generic pair runner directly.

Use the existing finite pair protocol with separate experiment IDs and exact
settings receipt for +12. Leave the original -6 settings receipt unchanged.
Settings replacement requires separate approval and preserves all unrelated files.

From fresh verified ordinary-hold anchor A, the only proposed path is:

1. A to A+12, speed20, acceleration1.
2. A+12 to A, only after software-verified arrival and successful export of leg1.

Check A and A+12 against [2893,2909]. A=2897 would yield2909, but that is an
example, not a hard-coded start assumption. If the fresh anchor cannot fit this
pair, export NOT_ELIGIBLE; do not clip, recenter or enlarge the workspace.
Do not require A-12 to fit: this is a one-direction displacement experiment, not
a matched +/-12 campaign. Preserve the existing matched-direction launcher for
its original purpose; use a distinct reviewed admission for this experiment.

There are at most two position commands, each once. Keep the two-second endpoint
deadline for direct comparison initially. A failure to arrive within that window
is not proof it can never arrive, and is not permission to automatically reissue.
Any reset needed to move from recovery ownership to ordinary hold remains a
separately approved, explicit startup, not hidden inside the pair launcher.

## 3. Export and interpret the outcome

Retain requested/encoded/readback targets, ACK status, complete timed position
traces, moving flags, neighbor positions and raw load/current/speed/voltage/temp.
Record configuration, boot, recovery receipt, settings receipt and software hashes.
Independent replay must reproduce each leg classification before progression.

| Observation | Interpretation and next decision |
| --- | --- |
| +12 moves but leaves about the prior 5–6 count residual | Supports a local direction-dependent residual; not a universal compensation map. Propose one controlled gain or approach-history comparison. |
| +12 arrives and return arrives | Shows small-displacement behavior differs. Validate a held-out magnitude before drawing conclusions or compensating. |
| +12 shows no encoder change despite valid goal readback | Do not escalate size or gain automatically. Revisit actuator/load/feedback evidence. |
| Invalid/stale feedback, uncertain delivery, or export failure | Inconclusive; stop without retry or recovery. |

For later compensation: collect repeated local endpoints and separate held-out
targets. Compare against uncompensated commands at identical speed, pose and load.
Do not train on a test result and call that same result held-out validation.

## 4. Conditional gain experiment, not the first next action

If evidence warrants tuning, review the exact ST3235 semantics and persistence
before selecting a value. Do not assume an ESP32 restart resets powered servos.
Freeze a single parameter change, preserve original P/D/I and lock state, prepare
readback and rollback, and obtain explicit authorization. Do not use all-joint
PID reset, EPROM unlock, or I=8 solely because related-model documentation uses it.
Never alter gains while an unhandled stale target remains six counts away: a gain
change alone could cause motion toward that target.

## Acceptance and remaining scope

Offline tests must cover residual6 acceptance only in the new profile, residual7
rejection, unchanged ordinary admission, actual-path bounds, no return after
failed forward, export failure, and boot/settings linkage. Candidate review and
explicit approvals precede deployment/provisioning/recovery/testing.

This experiment is a short path toward reliable bidirectional motion, not proof
of task-space accuracy. After repeatable joint-space endpoints, resume coordinated
noncontact strokes and ghost keys. Camera, contact and stylus-tip claims remain
deferred until mounting and registration are available.
