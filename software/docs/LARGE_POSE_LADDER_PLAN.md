# Large Pose Ladder Plan

## Objective

Develop visibly distinct RoArm-M3 poses without sweeping the gripper into the
board, increasing the already-small elbow-limit margin, or jumping directly to
an untested extreme. This phase prioritizes repeatable encoder-space pose
transitions. It does not claim stylus-tip, camera, or millimetre accuracy.

## Evidence and starting state

The three r61 interval campaigns ended at the same measured seven-servo pose:

- positions: `[2047, 2415, 1700, 2904, 1591, 2041, 2047]`;
- goals: `[2047, 2413, 1701, 2907, 1589, 2040, 2047]`;
- shoulder pair sum: `4114`;
- all three cycles reproduced every endpoint count-for-count.

The pinned kinematic model is
`models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf`. It retains the official
joint graph, origins, axes and limits but intentionally omits visual and
collision meshes. At the starting pose, the modeled elbow is approximately
`2.884 rad`, only `0.066 rad` (`3.8 degrees`) below its `2.95 rad` upper limit.
Larger motion must therefore decrease elbow angle, never increase it.

Frozen simulation export:
`wizard-20260923T002558386911Z-d2593a863cfa467697466277d00d2bc8`.

## Route design

The route uses two unnamed transit waypoints so clearance is gained before a
joint near a limit is repositioned. No adjacent transition changes any logical
joint by more than approximately `0.10 rad` (65–66 counts).

| Stage | Purpose | Seven-servo command goals | Modeled TCP `(x,y,z)` mm | Height gain | Elbow upper-limit margin |
| --- | --- | --- | --- | --- | --- |
| P0 | Verified reference | `2047,2413,1701,2907,1589,2040,2047` | `159.5,0.2,6.6` | `0.0 mm` | `3.8°` |
| T1 | Lift before elbow relief | `2047,2348,1766,2907,1654,2040,2047` | `154.3,0.2,17.1` | `+10.6 mm` | `3.8°` |
| P1 | Elevated elbow relief | `2047,2348,1766,2842,1719,2040,2047` | `168.6,0.3,14.9` | `+8.3 mm` | `9.5°` |
| P2 | High-clearance staging | `2047,2283,1831,2842,1785,2040,2047` | `162.6,0.2,26.4` | `+19.8 mm` | `9.5°` |
| P3 | Elevated extension | `2047,2283,1831,2777,1850,2040,2047` | `177.0,0.3,27.0` | `+20.4 mm` | `15.2°` |
| T4 | Lift before larger extension | `2047,2217,1897,2777,1915,2040,2047` | `169.7,0.3,39.2` | `+32.7 mm` | `15.2°` |
| P4 | High extended pose | `2047,2217,1897,2711,1980,2040,2047` | `183.7,0.3,42.7` | `+36.2 mm` | `21.0°` |

The shoulder commands always preserve the measured pair sum of 4114. Base,
wrist roll and gripper remain fixed during this ladder.

## Swept-path proxy results

Every adjacent transition was sampled at 101 interpolated configurations. A
15 mm-radius capsule proxy was applied to the moving structural segments and
non-adjacent segment distances were evaluated.

| Transition | Minimum modeled TCP world-Z | Minimum capsule surface clearance | Maximum joint step |
| --- | --- | --- | --- |
| P0 → T1 | `6.6 mm` | `24.1 mm` | `65 counts` |
| T1 → P1 | `14.9 mm` | `24.1 mm` | `65 counts` |
| P1 → P2 | `14.9 mm` | `25.8 mm` | `65 counts` |
| P2 → P3 | `26.4 mm` | `25.8 mm` | `65 counts` |
| P3 → T4 | `27.0 mm` | `25.8 mm` | `65 counts` |
| T4 → P4 | `39.2 mm` | `25.8 mm` | `65 counts` |

World-Z zero is only an unregistered board-plane proxy. The strongest result
is relative: T1 is modeled to raise the TCP by 10.6 mm and no planned segment
drops below the modeled P0 starting height.

## Physical release sequence

### Release A — T1 only

1. Obtain a fresh all-joint baseline from the current P0 endpoint.
2. Require exact P0 goals and positions within the reviewed tolerance.
3. Command only T1 at speed 20 and acceleration 1.
4. Permit one write, no retry, and no automatic return.
5. Capture fresh endpoint telemetry and export it durably.
6. Compare measured joint deltas and passive-joint spans with the plan.
7. Stop at T1. Do not continue automatically to P1.

T1 is selected first because it changes shoulder and wrist pitch in opposite
directions while holding the near-limit elbow fixed. Its intended effect is to
increase tool clearance before elbow motion begins.

### Release B — P1 elbow relief

Only after T1 is verified, command P1 as a separate one-write transition. This
reduces the elbow angle by approximately 0.10 rad while counter-rotating wrist
pitch. The modeled elbow upper-limit margin increases from 3.8° to 9.5°.

### Releases C–F

Release P2, P3, T4 and P4 one transition at a time. Each release starts from
fresh measured state, uses the immediately preceding verified endpoint, and
produces an independent export. Do not skip transit waypoints or infer current
pose from an earlier acknowledgement.

## Stop conditions

Stop the affected sequence on any of the following:

- the fresh goals do not match the expected source stage;
- a selected joint begins outside the measured source tolerance;
- a passive joint changes beyond its review window;
- delivery is uncertain or more than one write is reported;
- endpoint feedback is missing, stale, moving, or internally inconsistent;
- the durable export cannot be verified;
- observed motion differs materially from the expected lift/relief direction;
- cable tension, frame contact, self-contact, or board contact is observed.

## Model limitations

- The URDF has no collision meshes, cable model, payload, or stylus geometry.
- The board plane has not been physically registered to the URDF world frame.
- The 15 mm capsules are conservative proxies, not collision certification.
- The r61 shoulder hysteresis correction is local and is not applied to these
  larger multi-joint commands.
- Modeled TCP displacement is a planning hypothesis until telemetry and later
  camera/physical registration validate it.

## Implementation order

1. Keep the exported ladder and tests as the immutable planning source.
2. Implement an exact one-transition T1 native owner and authenticated runner.
3. Compile and review a new app-only candidate without hardware access.
4. Install/start it only after explicit approval.
5. Run T1 once, assess and export.
6. Update subsequent pose commands from measured evidence rather than blindly
   executing the rest of the simulated ladder.

## r62 implementation status — 2026-09-23

Steps 1–3 are complete. Candidate r62 adds a dedicated authenticated T1 route
instead of using the generic all-joint command path:

- source is fixed to the exact P0 goals and a ±2-count measured-position gate;
- one synchronized `SyncWritePosEx` addresses only servo IDs 12, 13 and 15;
- fixed targets are `2348`, `1766` and `1654` at speed 20/acceleration 1;
- base, elbow, wrist roll and gripper are never included in the write;
- three fresh stable source samples and a final prewrite sample are required;
- three fresh stable endpoint samples are retained;
- passive-joint goal changes or more than two counts of passive drift fault the
  owner;
- a reversed selected-joint response, an endpoint residual over 12 counts,
  uncertain delivery, stale feedback, or failed evidence export faults the
  owner;
- there is no retry, automatic return, or follow-on pose command;
- the exact 1,133-byte retained record must receive a matching SHA-256 receipt
  before the operation is complete.

The synchronized write is intentional. Offline kinematics showed that a
shoulder-first sequential fallback raises the modeled TCP, but a wrist-first
sequence lowers it. r62 removes that ordering ambiguity by sending the three
targets in one bus operation.

Offline evidence:

- stage export:
  `wizard-20260923T003938781696Z-04680e734bcf44df857eba794f7de478`;
- compile export:
  `wizard-20260923T004133494491Z-9f85eff5009a41c5bf3b93353ed08145`;
- review export:
  `wizard-20260923T004326932983Z-b4de27904d67457cbc375b9240980c7d`;
- application SHA-256:
  `ee259799cb6b74b80cc4a45e16934ac6476b81d7a4536cc31406fffb766fd6e4`;
- application size: `1,192,368` bytes, leaving `118,352` bytes in the
  `0x140000` application slot;
- focused native, composition, board-service, ladder and URDF suite:
  `70 passed`;
- the host coordinator now signs/selects only literal `T1`, polls terminal
  status without retry, independently decodes and checks all seven joints,
  exports the raw record plus assessment, verifies the export, and only then
  returns the record SHA-256 receipt;
- hardware access, upload and movement during this implementation: none.

The next checkpoint is step 4: one app-only r62 installation and one startup,
preserving the existing filesystem settings and credentials. Installation is
not movement. After startup, the authenticated route remains inert until a
separate signed `T1` start request is sent. The physical T1 request remains a
second, distinct checkpoint so a fresh P0 source read can be reviewed first.

## r62 installation and startup status — 2026-09-23

Step 4 is complete:

- exact r61 predecessor, controller MAC, partition table and filesystem were
  verified before the write;
- the r62 application was written only at offset `0x10000` and its full
  readback matched SHA-256
  `ee259799cb6b74b80cc4a45e16934ac6476b81d7a4536cc31406fffb766fd6e4`;
- protected regions were unchanged;
- exactly one startup reset was sent;
- startup export:
  `wizard-20260923T011452527448Z-ccd23eda5c794a38afcb5fd1f7034c8b`;
- boot identity: `8b2dccefc3394fd2827130e5994efb08`;
- controller remained `IDLE`, with zero retained records and no storage fault;
- unsigned route-presence export:
  `wizard-20260923T011526549003Z-3279c02a47fb4f438eb47ecb646507e1`;
- `/rocell/large-pose-lift/status` returned authenticated-route rejection
  (`403`) while an unknown path returned `404`, proving route registration
  without invoking it;
- no servo command, movement request, provisioning action, or extra reset was
  issued;
- post-install host/owner/installation/geometry regression suite:
  `327 passed`.

The next operation is the physical T1 release. It consists of one signed
literal `T1` request. The native owner will first acquire and validate three
fresh P0 samples and a prewrite sample. A source mismatch faults before the
bus write. If accepted, it permits exactly one synchronized write and stops at
T1 after endpoint export; it does not return or continue to P1.

## First physical T1 result — 2026-09-23

The host authenticated transport was completed with an exact `T1` body
allowlist and a signed loopback test (`9 passed`). The one-use r62 runner
`scripts/run_large_pose_lift.py` validated the retained startup, checked the
live boot identity read-only, reserved a no-retry claim, and sent one signed
start. The controller accepted fresh P0 source samples and made one
synchronized write to servos 12, 13 and 15. No return or follow-on movement
was sent.

- Startup boot: `8b2dccefc3394fd2827130e5994efb08`.
- Verified result export:
  `wizard-20260923T013000217507Z-65942c5e2f9b42f4b683f0fbf0a32455`.
- Measured P0 joint positions, IDs 11–17:
  `2047, 2415, 1700, 2904, 1591, 2041, 2047`.
- Measured T1 joint positions, IDs 11–17:
  `2047, 2357, 1759, 2904, 1652, 2041, 2047`.
- Selected measured travels: shoulder `−58`, elbow `+59`, wrist pitch `+61`
  counts; selected endpoint errors against target goals: `+9`, `−7`, `−2`
  counts. All four unselected joints held their measured positions.
- The raw native record, independent decoder assessment, and export manifest
  replayed/verified. This establishes an encoder-domain T1 joint endpoint,
  **not** physical tool-center accuracy or observed clearance from the board.

Release A step 5 is complete for a joint-position endpoint. Do not assume the
arm is still at T1 on a later boot; reacquire its live source before any new
motion. The next movement should be a separately reviewed T1→P1 transition
with a fresh T1 source gate and swept-geometry assessment, not a rerun of the
consumed P0→T1 command. Camera and stylus accuracy remain deferred.

## Release B preparation — r63, 2026-09-23

The next exact transition is T1→P1: hold the shoulder pair at `2348,1766`,
move elbow servo 14 from goal `2907` to `2842`, and counter-rotate wrist-pitch
servo 15 from `1654` to `1719`. Speed 20 and acceleration 1 remain fixed. The
T1 source positions are pinned from the verified r62 record as
`2047,2357,1759,2904,1652,2041,2047`, with a ±3-count entry window. Three
fresh stable all-joint samples and a fresh prewrite sample are mandatory;
source mismatch stops before the only permitted synchronized write. A three-
sample P1 endpoint and durable raw-record export are mandatory before receipt.
There is no retry, automatic return or P2 continuation.

Re-running the kinematic proxy from the **measured** T1 positions predicts a
TCP change from approximately `(154.2,0.2,15.8)` to `(168.4,0.3,13.4)` mm.
The modeled minimum tool-center height is `13.4 mm`, about `2.4 mm` below
measured T1 but still above the P0 model reference; minimum capsule surface
clearance is `24.1 mm`. Board registration, cable behavior and physical
clearance remain unverified, so these values are planning checks only.

Offline preparation is complete:

- r63 stage export:
  `wizard-20260923T014941177721Z-df983f2919674966aa33f9e94ed2b904`;
- r63 compile export:
  `wizard-20260923T015145565967Z-a39d76aa5967494f9e831e9fee455f48`;
- r63 review export:
  `wizard-20260923T015237844562Z-190bcbdfaa974294a409e0373ce26ef6`;
- app-only SHA-256:
  `cbca0f164c49f480c282fe2ed435616a50a767db50b1048b24b7abb40e55604b`;
- app size `1,200,704` bytes, `110,016` bytes below slot capacity;
- bootloader and partition hashes match the retained r62 build;
- local deployment preflight verified the r62 predecessor and retained
  filesystem without opening the controller;
- native source/endpoint/fault tests, signed transport tests, and host export
  tests pass (`285 passed` in the focused regression suite).

At the end of offline preparation, the r62 boot was read-only checked as
`8b2dccefc3394fd2827130e5994efb08`, IDLE. This did **not** prove the
physical T1 pose would persist after installation. The two distinct release
checkpoints were (1) app-only r63 installation plus one startup with read-only
validation, then (2) one separately released P1 request. The installation
checkpoint is recorded below; r63's fresh source gate still must establish
the live T1 pose before the movement checkpoint can write.

## r63 installation and startup — 2026-09-23

Checkpoint (1) is complete. The one authorized app-only installer verified
controller MAC `fc:e8:c0:f8:d5:38`, the full r62 predecessor, partition table
and saved filesystem before writing. It wrote r63 only at app offset
`0x10000`, verified the entire `1,200,704`-byte readback against SHA-256
`cbca0f164c49f480c282fe2ed435616a50a767db50b1048b24b7abb40e55604b`,
and confirmed protected regions unchanged. It sent exactly one startup reset.

- Installation evidence export:
  `wizard-20260923T022848183808Z-c267f17fd3e64fe4b9fc2efe3c24c1a5`.
- Read-only startup export:
  `wizard-20260923T022848530879Z-f10f35e808214ae0ad7f49976666af2e`.
- New boot ID: `f7b522422be6edcb9ab740a776e32ae5`.
- Startup state: IDLE, zero records, no storage fault. No servo command was
  sent by the startup observer.
- Unsigned P1 route-presence export:
  `wizard-20260923T022924159877Z-60111d7d356a4aebb24ae76aaa356396`;
  the registered route rejected an unsigned GET with `403`, while an unknown
  route returned `404`.
- The authenticated P1 runner's *offline* boot/source/export binding passed.
  No authenticated P1 start, fresh native P1 source capture, servo write or
  movement has occurred on r63 yet.

Checkpoint (2) remains separate: one signed literal `P1` request. Its native
owner will sample all seven joints three times and reject anything outside
the measured T1 source gate before any write. If admitted, it permits only
the reviewed synchronized servo-14/15 write and stops after P1 endpoint
record/export. Do not infer physical clearance or proceed to P2 automatically.

## Release B physical result — 2026-09-23

The approved T1→P1 trial completed on r63 boot
`f7b522422be6edcb9ab740a776e32ae5`. The controller accepted the fresh source
pose, performed exactly one synchronized servo-14/15 write, and returned a
verified endpoint record. The host verified the durable export before sending
its receipt. No retry, return or later movement was sent.

- Verified result export:
  `wizard-20260923T024713112793Z-299f2bdab3454e0fb68cc1cdc7cd44f0`.
- Fresh source positions, IDs 11–17:
  `2047,2356,1759,2904,1653,2041,2047`.
- Final measured positions:
  `2047,2356,1759,2844,1720,2041,2047`.
- Final target readbacks:
  `2047,2348,1766,2842,1719,2040,2047`.
- Elbow travel: `−60 counts`; wrist-pitch travel: `+67 counts`.
- Selected endpoint errors: elbow `+2 counts`, wrist pitch `+1 count`.
- The five passive servos held their measured source positions. Across the
  three endpoint samples, elbow readings were `2843,2844,2844`, and wrist
  pitch remained `1720`. The final sample ended `2155.755 ms` after dispatch;
  this is capture timing, not an independently measured motion duration.
- The stored raw record independently replayed to
  `P1_JOINT_ENDPOINT_MEASURED`; all export checks passed.

Release B is complete for joint-position verification. Physical tool-center
accuracy and board clearance remain unmeasured. The original T1 entry values
must not be reused for future movement: P1 is now the latest recorded pose,
and any subsequent operation still needs fresh source acquisition.

The next planned transition is P1→P2, using goals
`2047,2283,1831,2842,1785,2040,2047`. An offline 101-point interpolation from
the measured P1 pose predicts approximately `+11.3 mm` tool-center height
change, with minimum modeled world-Z `13.2 mm` and capsule surface clearance
`25.8 mm`. These remain unregistered geometry proxies. P2 has not been
implemented or executed as a live release; its source gate must be based on
the P1 record above.

## P2 timing-order review: shoulder-first intermediate

The simultaneous P1→P2 proposal above is superseded by **P1→P2L→P2**.
An independent shoulder/wrist progress grid exposes a risk hidden by linear
interpolation: if the wrist completes first, modeled TCP height temporarily
falls from 13.16 to 9.07 mm. Shoulder-first raises it to 30.18 mm before the
wrist adjustment finishes at 24.45 mm. These are model values, not measured
board clearance or a continuous collision proof.

The offline review now replays the verified P1 binary record, derives its
actual endpoint, hashes the model and record, and exports all three timing
envelopes. Reproduce with `python scripts/review_p2_path.py` and `PYTHONPATH=src`.
Verified review export:
`wizard-20260923T025411427105Z-ab98706dba3c4335b20cc09fcc00d732`.

Next implementation and release steps:

1. Prepare P2L using goals `2047,2283,1831,2842,1719,2040,2047`:
   shoulder servos 12/13 only, with elbow and wrist unchanged. Reuse the
   existing bounded write/capture/export workflow; do not add a general jog API.
2. Bind its source gate to measured P1, but reacquire all joints immediately
   before writing. Retained evidence is not a fresh live position.
3. Test wrong source, passive drift, uncertain delivery, wrong-direction travel,
   endpoint failure and export failure before reviewing the firmware candidate.
4. Execute only the reviewed shoulder step, export and verify the actual P2L
   endpoint, then recalculate the wrist step from that endpoint. No automatic
   follow-on wrist movement or retry.

The grid assumes commanded angle deltas are realized monotonically, models
the shoulder pair as one logical joint, and excludes cables, attached tools,
full link meshes and a registered board. It does not certify the shoulder pair's
mechanical synchronization. No firmware was installed or hardware accessed
for this offline review; P2L native implementation and physical testing remain
pending.

## P2L implementation and offline build — 2026-09-23

P2L now has a staged r64 native candidate. It specializes the retained r63
workflow rather than adding another owner/route stack: only the policy, exact
write, record identifier and compiled selector change. Its only write is to
IDs 12/13 at targets 2283/1831, speed 20 and acceleration 1. The other five
servo goals are unchanged. Three fresh source samples, immediate prewrite
checks, bounded endpoint sampling and export acknowledgement remain required.

The shared host/decoder now accepts explicit reviewed profiles P1 and P2L;
P1 remains the default. P2L uses binary domain `RCP2LIFT01`, literal selector
`P2L` and receipt `LARGE_POSE_P2L_RECORDED`. Cross-profile records are rejected.
The HTTP adapter permits the two exact selectors, not arbitrary target inputs.

- Stage export: `wizard-20260923T094049867734Z-e4955e1c58944bd0b591e33ef609c204`.
- Compile export: `wizard-20260923T094333014308Z-df5a0efd5a874f0ab2de6dd4da1bc575`.
- Offline review: `wizard-20260923T094445930836Z-6bdb8da4d67b4bb495de827d4c5c8511`.
- App SHA-256: `a8480d215bdfce5768dd0fcd6d81c97bab9cae9c6b2d33ea0894eefe28275ba8`.
- Focused suite: 40 passed, including exact staged native success and seven
  fault cases, independent record decoding, host export/receipt and historical
  P1 regressions. The firmware compiled within the app slot; bootloader and
  partition identities match the predecessor build.

No installation, startup, live query or movement occurred during this work.
Remaining before the physical test: bind r64 into the reviewed installer and
add the boot/source-bound P2L runner, validate those integration paths, then
release the reviewed installation and one shoulder-only trial. The later wrist
step must be based on the newly measured P2L endpoint, not assumed success.

## P2L installer and runner integration — 2026-09-23

The r64 installer, installation-evidence validator and startup observer now
recognize the reviewed app SHA above, size 1,200,720 bytes, with r63 as the
required predecessor. Offline installer preflight passed and verified the
retained filesystem identity without accessing hardware or reserving a journal.
The shared `p2_lift_release.py` check pins the reviewed image, targets and scope.

`scripts/run_p2_lift.py` now binds one P1→P2L request to a verified r64 startup
export and independently replays the retained P1 source record. Before motion,
it checks that the live boot remains idle, durably claims that boot, and uses
the explicit P2L host profile. The native owner still acquires fresh positions;
the historical source replay is not substituted for live readings. Delivery
uncertainty does not trigger a retry, and no wrist follow-on is implemented.

Validation: 318 focused tests passed, including wrong-boot rejection before
dispatch, durable claim before dispatch, no retry on uncertain outcome,
preflight with no transport access, retained source replay, claimed-boot
rejection, native endpoint/fault tests and startup/installation regressions.

The next hardware release is one r64 app-only installation and one startup,
preserving settings and credentials, then one shoulder-only P1→P2L trial if
startup and fresh source checks pass. Capture and export the endpoint, then stop.
No automatic retry, return, wrist step or torque-off is included. This integration
turn did not install firmware, restart the controller, query it or move the arm.

## r64 installation attempt stopped before write — 2026-09-23

The authorized installation attempt reserved its journal and opened the expected
USB adapter, then failed during ROM synchronization: download mode was detected
but no sync reply arrived. The existing longer Windows reset timing was used.
This message does not by itself establish a defective cable or controller.

The journal contains only RESERVED and STOPPED. No flash write, app readback,
explicit startup reset, P2L request or servo command occurred. Entering the
bootloader did reset the controller; its current runtime state is unverified
and it may remain in download mode. Do not infer that the previous app is running.

Verified failure export:
`wizard-20260923T192629532955Z-a247925f78d749dd95c7a96845762233`.
The original `app-r64-deployment-events.jsonl` is preserved and no retry was
attempted. Recovery must use a separately authorized attempt and preserve this
failure evidence; do not delete the journal or send movement while boot state
is unresolved. The physical P2L trial remains unexecuted.

## r64 authorized recovery succeeded — 2026-09-23

The separately authorized second installation attempt succeeded using the
existing longer-reset connection strategy. The first failure journal and its
export remain unchanged. The second attempt is recorded independently in
`app-r64-attempt2-deployment-events.jsonl`; no third attempt was made.

The installer verified controller MAC, r63 predecessor and filesystem before
writing, then verified the complete 1,200,720-byte r64 application readback and
unchanged protected regions. It sent exactly one startup reset. No servo command
was sent during recovery or observation.

- Installation evidence: `wizard-20260923T194402666231Z-884216a8e8b34d10a7c2a2727802bee8`.
- Startup observation: `wizard-20260923T194403130929Z-4eb2f802a9404622a99ac2d77d164039`.
- Boot: `6d2f06e84d08620829bd579b7f337c8b`.
- Read-only startup: IDLE, zero records, no storage fault; status unchanged
  across the observation. Settings and credentials were preserved.
- Recovery/startup/runner regression tests: 308 passed.

Recovery is complete. The next operation is the single P1→P2L shoulder-only
trial, bound to this startup export and gated by freshly acquired joint data.
No lift, return or wrist movement was performed in this recovery turn.

## P1→P2L physical trial completed — 2026-09-23

The authorized shoulder-only trial passed fresh source checks and completed
exactly one synchronized write to IDs 12/13. The host verified the durable
export before sending the receipt. Independent replay of the binary record
also passed as `P2L_JOINT_ENDPOINT_MEASURED`.

- Result export: `wizard-20260923T194529289849Z-76fd6c1bf73a4a6eacf42e7510b2072d`.
- Boot: `6d2f06e84d08620829bd579b7f337c8b`.
- Fresh source positions: `2047,2356,1759,2844,1720,2041,2047`.
- All three endpoint snapshots: `2047,2291,1825,2844,1720,2041,2047`.
- Final target readbacks: `2047,2283,1831,2842,1719,2040,2047`.
- Shoulder travel: −65/+66 counts; final errors: +8/−6 counts, within the
  reviewed 12-count endpoint tolerance. All five passive positions unchanged.
- Final endpoint sample ended 1706.008 ms after dispatch; this is capture
  timing, not an independently measured movement duration.

The one-use owner is consumed. No retry, return, wrist step or subsequent
movement was sent. This verifies the joint endpoint, not physical TCP accuracy
or board clearance. Next, review the wrist-only P2L→P2 path from these measured
positions and prepare that bounded step; do not reuse the pre-lift P1 source.

## Wrist-only P2L→P2 contract and geometry review — 2026-09-23

The next contract is now defined from the independently replayed physical P2L
record. Only servo 15 changes, from goal 1719 to 1785: +66 command counts
(about 5.8 degrees), while the target is +65 counts from measured position 1720.
This distinction is retained explicitly rather than treating targets as positions.
All six other goals remain `2047,2283,1831,2842,2040,2047` in servo order with
15 omitted. Speed is 20, acceleration 1, one write attempt, no retry or return.

Offline export:
`wizard-20260923T194755484056Z-5ffeb0da809b45a3a0366966c609ac80`.
Reproduce using `python scripts/review_p2_wrist.py` with `PYTHONPATH=src`.

The measured-source model starts at TCP Z 30.178 mm. With the prior +1-count
wrist bias retained as a nominal assumption, the next endpoint is Z 24.446 mm.
A 161-point sweep covering the entire permitted positive travel of 0–80 counts
finds minimum TCP Z 23.443 mm and minimum 15-mm-radius capsule clearance
25.750 mm. These are unregistered geometry proxies, not board clearance
measurements or full multi-joint uncertainty/cable collision checks.

Implemented `p2_wrist_policy.h` reuses the existing source/endpoint checking
rules, specialized to this exact wrist-only step. Offline native tests cover
valid arrival, source mismatch, passive drift, wrong direction, excess travel,
wrong target and insufficient arrival. The focused suite passed 23 tests.

No hardware access, firmware installation or movement occurred in this review.
Next implementation work is to wire the single-servo owner/write and its record
format into a reviewed firmware candidate and host runner. The policy and path
review alone are not a deployable or physically tested P2 movement.

## r65 wrist-only implementation ready for release — 2026-09-23

The single-servo owner, board write, authenticated route, host record decoder,
export workflow and boot-bound runner are implemented. The staged r65 reuses
the r64 workflow but accepts only literal P2 and writes only servo 15 at target
1785, speed 20, acceleration 1. Its record is 1129 bytes with distinct domain
`RCP2WRST01`; no dummy second servo is written or encoded. Historical P1/P2L
records retain their formats and are rejected when supplied as P2 evidence.

- Stage: `wizard-20260923T195119093561Z-2da9d751633f4de5b22ce349fb0650c2`.
- Compile: `wizard-20260923T195319510419Z-f65208d64d6c478ca3fc038249eee01f`.
- Review: `wizard-20260923T195347216230Z-1526901a57e64f2b8ef1fa0d1083d0a0`.
- App SHA-256: `7ed18ca356194e2b226936c5146e46ec079c326d8140667a07a49923b935b4de`.
- App bytes: 1,200,624; offset 0x10000; bootloader/partition identities unchanged.
- Installer offline preflight passed, binding r64 as predecessor and preserving
  the retained filesystem. No deployment journal was reserved.
- Initial focused suite: 40 passed, covering native faults, profile separation,
  export failure without receipt, runner claim/no-retry behavior and regressions.

`run_p2_wrist.py` independently replays the retained P2L result, requires an r65
startup binding and checks the live boot before claiming the one-use operation.
Fresh native source checks still run before the write. No automatic follow-on
movement, return or retry is included.

No hardware access or installation occurred during implementation. The next
release requires one r65 app-only installation and startup, preserving settings
and credentials, followed by one wrist-only P2 trial if startup and fresh source
checks pass; capture/export and stop. A successful joint endpoint will still not
prove measured physical tip accuracy or board clearance.

## r65 installed; wrist-only P2 reached — 2026-09-23

The approved app-only installation succeeded on its first attempt. The installer
verified the controller and r64 predecessor, wrote the reviewed 1,200,624-byte
app, verified its full readback and unchanged protected regions, then sent one
startup reset. Settings and credentials were preserved.

- Installation evidence: `wizard-20260923T201506247234Z-fe9c40d34abf440b939eb97a2418d438`.
- Startup observation: `wizard-20260923T201506599579Z-56beebb6b3a74a5ca187468641c36ed9`.
- Boot: `ce3a5f51d59110826b67e3bf48d1f260`; startup IDLE, zero records,
  no storage fault, unchanged status across the read-only observation.

The authorized P2 trial then passed fresh source/prewrite checks and performed
exactly one wrist-only write. Its verified durable export and independently
replayed binary record both establish `P2_JOINT_ENDPOINT_MEASURED`.

- Result: `wizard-20260923T201517566882Z-2a37583111464777b465b59ccec7b9f0`.
- Fresh source: `2047,2291,1825,2844,1720,2041,2047`.
- All three endpoint snapshots: `2047,2291,1825,2844,1784,2041,2047`.
- Final goal readbacks: `2047,2283,1831,2842,1785,2040,2047`.
- Wrist travel +64 counts (5.625 degrees); endpoint error −1 count.
- All six passive joint positions unchanged. Final endpoint capture ended
  1703.985 ms after dispatch; not an independently measured motion duration.

P2 is now the latest verified joint endpoint. The host received the export
receipt, and no retry, return or subsequent motion was sent. This boot's one-use
owner is consumed. Next, evaluate the P2→P3 extension path from these measured
positions, accounting for independent joint progress rather than assuming
simultaneous arrival. Physical tip accuracy and board clearance remain unmeasured.

## P3 extension review: elbow first — 2026-09-23

Replace the simultaneous P2→P3 proposal with **P2→P3E→P3**. Independently
replayed P2 source positions are `2047,2291,1825,2844,1784,2041,2047`.
The first command changes only elbow servo 14 from goal 2842 to 2777 (−65
command counts; −67 counts from the measured position). Wrist remains at goal
1785. P3E goals are `2047,2283,1831,2777,1785,2040,2047`.

The measured-source model gives:

- P2 TCP: approximately `(159.83,0.24,24.60)` mm.
- Elbow-first intermediate: `(190.17,0.29,30.66)` mm, extending about 30.34 mm
  and raising about 6.07 mm.
- Wrist-first intermediate would lower modeled Z to 20.53 mm.
- Subsequent nominal P3: `(174.23,0.27,24.98)` mm, but must be recomputed
  from the actually measured P3E endpoint before any wrist command.

The 41×41 independent-progress grid exposes the wrist-first dip. The proposed
elbow-first sampled path never falls below the starting TCP height. A separate
161-point elbow sweep covers 0–80 counts, with minimum modeled capsule surface
clearance 25.75 mm. These checks exclude cables, full meshes, attached tools,
registered board geometry and full multi-joint uncertainty; they are not physical
clearance certification. No compensation is inferred from the nominal bias.

Verified offline export:
`wizard-20260923T210943213268Z-2d9a17713c0e4ea384795a7621520756`.
Reproduce using `python scripts/review_p3_extension.py` with `PYTHONPATH=src`.

Implemented and native-tested `p3_elbow_policy.h`: fresh source matching,
one selected joint, 80-count travel bound, 12-count endpoint tolerance, passive
drift at most 2 counts. The focused suite passed 21 tests, including incorrect
source, direction, target, excess travel and inadequate endpoint checks.

No hardware access or movement occurred in this review. Next is wiring this
policy into the single-servo firmware owner/record and boot-bound host runner,
then compiling and reviewing the candidate. No automatic wrist follow-on,
retry or return is authorized by this offline plan update.

## r66 P3E elbow-only workflow ready — 2026-09-23

The single-servo P3E workflow is implemented and compiled. r66 is specialized
from the hash-verified r65 sources; it accepts only literal P3E, writes servo
14 at target 2777, speed 20/acceleration 1, and preserves the six passive goals.
Record domain `RCP3ELBW01` distinguishes its 1129-byte evidence from earlier
steps. The shared host verifies the explicit P3E profile and durable export
before receipt. The boot-bound `run_p3_elbow.py` replays the retained P2 source;
fresh native sampling still gates the actual write.

- Stage: `wizard-20260923T212310238666Z-ebcefdfcf6004f2ba8eb983333a84958`.
- Compile: `wizard-20260923T212500364477Z-7b5cc7144f3b41ae8fd03fafff18299e`.
- Review: `wizard-20260923T212529489183Z-9d668b37f0c44de79284a1566a79b076`.
- App SHA-256: `3dd1401b58cec43fb3c5c27c8d2072987487964d8a4609552d38cf8bf7e73812`.
- App length 1,200,656 bytes; bootloader and partition identities unchanged.
- Offline installer preflight passed against r65 and the retained filesystem.
- Integration/regression suite: 337 passed. Additional focused geometry,
  transport and historical movement suites also passed.

No hardware access, startup or movement occurred in this implementation turn.
Ready for one r66 app-only installation/startup preserving settings and
credentials, then one P2→P3E elbow-only test if startup and fresh position checks
pass, followed by export and stop. No automatic wrist adjustment, return or retry.
The predicted extension is not a measured Cartesian-accuracy claim.

## r66 installed; P3E elbow extension verified — 2026-09-23

The authorized app-only installation succeeded on its first attempt. Controller
identity and r65 predecessor checks passed before writing. Full readback verified
the reviewed 1,200,656-byte r66 app, protected regions were unchanged, and exactly
one startup reset was sent. Settings and credentials were preserved.

- Installation: `wizard-20260923T220923350502Z-4eeb2ae450d546609a056c78a3331b0d`.
- Startup: `wizard-20260923T220923579750Z-ecc67b42b0944ad781836a3c9b3cb51b`.
- Boot: `e61c5767d2d5b0616ac34cd847b2f59d`; IDLE, zero records, no storage
  fault, unchanged status across the startup observation.

The elbow-only trial passed fresh source and prewrite checks, performed exactly
one servo-14 write and completed its export/receipt handshake. Independent replay
of the retained binary record passed as `P3E_JOINT_ENDPOINT_MEASURED`.

- Result: `wizard-20260923T220934352526Z-00cc861d428f4b168b5c1ead42c5de8e`.
- Fresh source: `2047,2291,1825,2844,1784,2041,2047`.
- All three endpoint samples: `2047,2291,1825,2780,1784,2041,2047`.
- Goal readbacks: `2047,2283,1831,2777,1785,2040,2047`.
- Elbow travel −64 counts (−5.625 degrees), final error +3 counts; all six
  passive joint positions unchanged.
- Final sample ended 1701.892 ms after dispatch, a capture timestamp rather
  than independently measured movement duration.

No wrist command, retry, return or further movement was sent. This boot's
one-use owner is consumed. P3E is now the latest verified joint endpoint. Next,
review the wrist-only P3E→P3 path from these measured readings, not the nominal
P3E prediction. Physical TCP accuracy and actual board clearance remain unmeasured.

## P3E→P3 wrist review and policy — 2026-09-23

The verified P3E binary record was independently replayed before defining the
next step. Measured source is `2047,2291,1825,2780,1784,2041,2047`; source
goals are `2047,2283,1831,2777,1785,2040,2047`. The proposed command changes
only wrist servo 15 to goal 1850, a +65-count command change (about 5.71 degrees)
and +66 counts from measured position 1784. All six other goals remain fixed.

The source-based model places the TCP at approximately `(189.71,0.29,30.55)`
mm. Assuming the prior −1-count wrist bias persists, the nominal endpoint is
`(173.76,0.27,24.89)` mm: about 5.66 mm lower. The 161-point sweep across the
allowed 0–80 count positive travel gives minimum modeled Z 23.81 mm and minimum
capsule surface clearance 25.75 mm. This is not calibrated compensation or a
measurement of board clearance; full meshes, cables, tool, board registration
and multi-joint uncertainty remain excluded.

- Verified review export: `wizard-20260923T231153808532Z-d28902836e594464bf6e1a777b8e7890`.
- Reproduce: `python scripts/review_p3_wrist.py` with `PYTHONPATH=src`.
- `p3_wrist_policy.h` implements the exact source/target checks, 80-count travel
  bound, 12-count endpoint tolerance and 2-count passive-drift limit.
- Focused suite: 19 passed, including native policy checks and elbow workflow
  regressions. Historical source identity and framing failures are rejected.

No controller access or movement occurred in this review. Next, wire the policy
into the existing single-servo owner, record profile and boot-bound runner, then
compile/review the next firmware candidate. The review/policy alone does not
make the next movement deployable. No retry, return or further pose is included.

## r67 P3 wrist workflow ready for release — 2026-09-23

Implemented the exact P3E→P3 single-servo workflow in staged r67. Only servo
15 is written, target 1850, speed 20 and acceleration 1. Six passive goals stay
unchanged. The authenticated selector is P3; the 1129-byte binary record uses
domain `RCP3WRST01`. The explicit host profile rejects other pose records,
verifies endpoint evidence, exports durably and then acknowledges the receipt.
`run_p3_wrist.py` binds the r67 startup and replays the retained P3E result;
fresh native source and immediate prewrite checks still gate the actual write.

- Stage: `wizard-20260923T232743745151Z-316c6901ad9c4e3982e22f2f314fa754`.
- Compile: `wizard-20260923T232929118798Z-82280e00a0e24d50b7031e7ac31f016d`.
- Review: `wizard-20260923T232955852188Z-fb654061ff6b4aefa4d5a71b2276c7c5`.
- App SHA-256: `92623957b1a2bf9f11bafce8a3a8db6788121232d26cb6fed1406c0ecb002c05`.
- App size 1,200,640 bytes; bootloader/partition identities unchanged.
- Installer offline preflight passed against r66 and the retained filesystem.
- Final integration/regression suite: 346 passed. Focused movement/transport
  and historical workflow suites also passed.

No controller access, startup or motion occurred in this implementation turn.
Ready for one r67 app-only installation/startup preserving settings and
credentials, then one wrist-only P3 trial if startup and fresh source checks
pass, followed by export and stop. No retry, return or further pose is included.

## r67 installed; P3 wrist endpoint verified — 2026-09-23 local / 2026-09-24 UTC

The approved app-only installation succeeded on its first attempt. Controller
identity and r66 predecessor checks passed before writing. The entire
1,200,640-byte r67 app readback matched the reviewed hash; protected regions
were unchanged. Exactly one startup reset was sent, preserving settings and
credentials.

- Installation: `wizard-20260924T000613719828Z-9ba671c4d94847219606c2f83ce346cd`.
- Startup: `wizard-20260924T000614073680Z-2b2808104c3d4047897497a37104a8a4`.
- Boot: `f7af4364ee3b87335970ee6052674b12`; IDLE, zero records, no storage
  fault, unchanged status across the startup observation.

The approved wrist-only trial passed fresh source/prewrite checks and sent
exactly one servo-15 write. Durable export and receipt completed; independent
binary replay passed as `P3_JOINT_ENDPOINT_MEASURED`.

- Result: `wizard-20260924T000623600641Z-c2103044389a40f4a53461447c9b9ea8`.
- Fresh source: `2047,2291,1825,2780,1784,2041,2047`.
- All three endpoint samples: `2047,2291,1825,2780,1850,2041,2047`.
- Goal readbacks: `2047,2283,1831,2777,1850,2040,2047`.
- Wrist travel +66 counts (5.80078125 degrees), final error zero encoder counts;
  all six passive joint positions unchanged.
- Final sample ended 1705.214 ms after dispatch, a capture timestamp rather
  than independently measured motion duration.

No retry, return or further movement was sent. This boot's one-use owner is
consumed. P3 is now the latest verified joint endpoint, not a measurement of
physical TCP accuracy or board clearance. Next, review the next lift/extension
from these measured readings and retain the joint-order checks used for P2/P3.

## Measured P3 to T4 lift review — 2026-09-24 UTC

Reviewed the next path offline against the verified r67 P3 binary record,
not merely its commanded goals. Implementation: `t4_lift_review.py` and
`scripts/review_t4_lift.py`. Review export:
`wizard-20260924T001018191203Z-3355ce7816e842f891f99c34a0d54bfc`.

Choose shoulder-first P3 → T4L, then separately review the wrist step to T4
from the measured T4L endpoint. Source positions are
`2047,2291,1825,2780,1850,2041,2047`; source goals are
`2047,2283,1831,2777,1850,2040,2047`.

- Proposed first write: shoulder servos 12/13 to 2217/1897, speed 20,
  acceleration 1. Goal deltas are −66/+66; target minus measured position
  is −74/+72. Other goals stay unchanged.
- Modeled TCP height rises from 24.816 to 42.851 mm in the model frame;
  outward displacement is approximately 8.940 mm. This is not board clearance.
- Wrist-first would temporarily lower modeled height to 20.799 mm, so do
  not combine both movements in an unsequenced write.
- Reviewed 1,681 independent shoulder/wrist progress samples, 82 ordered
  samples and 161 samples over the first shoulder step's 0–80-count travel.
  The latter does not lower the nominal TCP below its starting height.
- Model assumptions exclude cables, full link meshes, tool and registered
  board. The paired shoulder is one logical joint: pair desynchronization
  and full multi-joint uncertainty are not covered. Discrete sampling is
  not a continuous collision proof.

Validation: five tests passed across the new T4 review and retained P3 wrist
review/native policy suite. Tests replay the source manifest and record,
reject wrong boot/truncated records, check movement ordering and preserve
the report's explicit non-authorization flags.

Next implementation: specialize the existing paired-shoulder owner and
record profile for T4L, add authenticated host/export integration, and compile
and review a candidate before deployment. Keep fresh source ±3 counts,
immediate prewrite ±1, selected travel ≤80, endpoint error ≤12 and passive
drift ≤2. One write, no retry, return or automatic wrist follow-on. Evaluate
the measured result before preparing T4.

No controller access, firmware installation, startup or motion occurred in
this review. r67's prior one-use owner remains consumed; this offline review
does not make another movement available on that boot.

## r68 T4L shoulder-lift workflow ready for release — 2026-09-24 UTC

Implemented and compiled the shoulder-first P3 → T4L step. Reused the
hash-verified r64 paired-shoulder workflow; its differences from r67 are
confined to the same four movement-specific files. No unrelated firmware
behavior was rolled back. The candidate writes servos 12/13 together to
2217/1897, speed 20, acceleration 1, with all other goals unchanged.

The authenticated selector is `T4L`; the 1131-byte record uses domain
`RCT4LIFT01`. Host verification independently decodes the record, checks
source/prewrite/endpoint evidence, exports and verifies the bundle, then
acknowledges its digest. `run_t4_lift.py` binds a reviewed r68 startup, replays
the retained measured P3 result, checks the live boot and takes an exclusive
one-use claim before invoking the existing host. It cannot retry or continue
to the wrist step. Startup and installation validators now recognize r68.

- Stage: `wizard-20260924T001621373379Z-062b05bcaec148b9b6a6729d1a416f4e`.
- Compile: `wizard-20260924T001828074672Z-b9c72a2480324229ac8283124d0e3e35`.
- Review: `wizard-20260924T001859367881Z-8f0f4bec18db4ba4b793e6c59f9ebab6`.
- App SHA-256: `70ea81de94d578360a6afb68462b1e87b660b0c7a4bf1d5c644491ba7136dbad`.
- App size: 1,200,720 bytes; offset 0x10000, within the 0x140000 app slot.
- Bootloader and partition hashes unchanged; installer offline preflight
  passed against r67 and the retained private filesystem hash.
- Tests: 47 focused/native/transport/staging checks and 344 runner,
  startup and installation regression checks passed (391 total).

No hardware access, startup, installation or motion occurred during this
implementation. Await explicit approval for one r68 app-only installation
and one startup preserving settings and credentials, followed by one T4L
shoulder-lift trial only if startup and fresh source checks pass. Export the
result and stop; no retry, return or automatic wrist movement. Modeled lift
remains a prediction, not a measured physical displacement or clearance.

## r68 installed; T4L shoulder endpoint verified — 2026-09-24

The approved app-only installation succeeded on its first attempt. The
controller identity and r67 predecessor checks passed before the write.
Full r68 app readback matched the reviewed SHA-256, protected regions were
unchanged, and exactly one startup reset was sent. Settings and credentials
were preserved.

- Installation: `wizard-20260924T094701103794Z-e5fa11396c644c0bb4e523188e456cec`.
- Startup: `wizard-20260924T094701413337Z-f2d8b328fe4445f08195910195f76fd7`.
- Boot: `3393ba5a435af3044f3b554f5622f2fa`; startup observations were
  identical, IDLE with zero records and no storage fault.
- Movement result: `wizard-20260924T094712566120Z-c199a22385e441c0b96efde228b164e1`.

The single approved paired-shoulder write passed fresh source and immediate
prewrite checks. Three endpoint samples were identical. The host completed
durable export and receipt; independent manifest verification and binary
replay matched the stored `T4L_JOINT_ENDPOINT_MEASURED` assessment.

- Source positions: `2047,2291,1825,2780,1850,2041,2047`.
- Endpoint positions: `2047,2225,1890,2780,1850,2041,2047`.
- Goal readbacks: `2047,2217,1897,2777,1850,2040,2047`.
- Shoulder travel: −66/+65 counts (−5.80078125/+5.712890625 degrees
  in the individual servo encoder coordinates).
- Shoulder endpoint errors: +8/−7 counts, within the reviewed 12-count
  tolerance. These are not zero-error arrivals or physical TCP measurements.
- All five passive servo positions unchanged. Exactly one write attempt.
- Final capture ended 1716.952 ms after dispatch; this is a capture timestamp,
  not an independently measured motion duration.

No retry, return or subsequent movement was sent. The r68 one-use owner is
consumed. T4L is the latest verified joint endpoint. Next review the remaining
wrist adjustment from these measured readings before preparing another
candidate; do not substitute the nominal T4L prediction for this source.
No measured stylus-tip accuracy or board-clearance claim is established.

## Measured T4L to T4 wrist review — 2026-09-24

Reviewed the remaining wrist adjustment against the measured r68 T4L binary
record and verified its export manifest. Source positions are
`2047,2225,1890,2780,1850,2041,2047`; source goals are
`2047,2217,1897,2777,1850,2040,2047`. No old commanded pose is substituted
for these measured readings.

- Proposed wrist-only command: servo 15 to 1915, +65 counts (5.712890625
  degrees), speed 20, acceleration 1. All six passive goals remain unchanged.
- Modeled TCP starts at `[182.452,0.279,42.851]` mm and nominally ends at
  `[166.507,0.255,37.194]` mm. This adjustment lowers modeled height by
  approximately 5.657 mm; the preceding shoulder lift provides the modeled
  height increase before this step.
- Swept all allowed positive travel from 0 to 80 counts in 161 samples.
  Minimum model-frame TCP height is 36.116 mm; minimum simplified
  nonadjacent capsule clearance is 25.750 mm. Neither value measures
  real board clearance. Cables, full meshes, tool, registered board and
  full multi-joint uncertainty remain outside this review.
- Export: `wizard-20260924T094919630266Z-14d0df26566b44dda25340bf923395a7`.
- Added `t4_wrist_review.py`, its export script, `t4_wrist_policy.h` and
  native policy tests. Sixteen focused/regression tests passed, including
  wrong boot, truncated record, reverse/excess travel, wrong goal, passive
  drift and endpoint/source rejection cases.

This turn was offline only. The native policy is not yet wired into a
deployable firmware candidate. Next specialize the existing single-servo
owner, authenticated record profile and boot-bound runner for T4, then
compile/review the next candidate. Retain one write, no retry or return,
fresh source/prewrite checks and verified export before acknowledgment.
r68 remains installed with its prior one-use operation consumed.

## r69 T4 wrist workflow ready for release — 2026-09-24

Integrated the measured T4L → T4 wrist-only step into the native owner,
authenticated selector, independent record assessment, durable export/receipt
workflow, startup binding and installer. Reused the hash-verified r67
single-servo source; r67/r68 differ only in the four movement-specific files
being specialized, so unrelated firmware behavior is unchanged.

- Only servo 15 is written: target 1915, speed 20, acceleration 1.
  Source wrist position/goal is 1850. Other six goals remain unchanged.
- Selector `T4`, record domain `RCT4WRST01`, 1129-byte record.
- `run_t4_wrist.py` independently replays the retained T4L result, requires
  a reviewed r69 startup and idle live boot, and reserves a one-use claim.
  Native fresh source/prewrite checks gate the write. No retry or return.
- Stage: `wizard-20260924T095113509627Z-9b3a3bd4412748d985f8532d2d4ebd6f`.
- Compile: `wizard-20260924T095347591688Z-949670757f6f46a6a8afa540063e58db`.
- Review: `wizard-20260924T095406798973Z-101a20213e394687ac42c076bedb9b43`.
- App SHA-256: `121a4c5b98c7fbb6e94ad448ac056341c284530416bf583c690850792b12a7a8`.
- App size 1,200,640 bytes; offset 0x10000, within the 0x140000 slot.
  Bootloader/partition hashes unchanged. Offline installer preflight passed
  against r68 and the retained private filesystem hash.
- Final combined suite: 405 tests passed, covering new wrist owner/policy,
  signed transport, source specialization, runner, historical movement
  workflows and startup/installation validation.

No controller access, installation, startup or motion occurred in this
implementation turn. Await approval for one r69 app-only installation and
one startup preserving settings and credentials, followed by one wrist-only
T4 trial if startup and fresh source checks pass, then verified export and
stop. No retry, return or follow-on movement. r68 remains installed and its
prior one-use owner remains consumed. Physical TCP accuracy and real board
clearance remain unmeasured.

## r69 installation attempt stopped before flash write — 2026-09-24

The approved first attempt identified the expected USB adapter and reserved
its exclusive journal, but ESP32 ROM synchronization failed. The boot log
indicated download mode; no synchronization reply arrived. Execution stopped
inside `esp.connect`, before controller MAC/predecessor verification, stub
upload, erase/write, or application startup reset. No wrist command was sent.

- Original journal preserved: `private-backups/controller-20260918-session1/app-r69-deployment-events.jsonl`.
- Journal SHA-256: `e39376fe1ca62161a027fcb31fcaa0338501c3e55ffbda8d5f8b99e6a2af80c1`.
- Verified failure export: `wizard-20260924T095613508466Z-57acb13dbf8a46da868933267443ac23`.
- `export_r69_prewrite_failure.py` validates the exact two-event journal
  shape before classifying the failure as prewrite. No device is opened.
- No flash write was attempted, so r68 remains the last verified installed
  image. Current running state is unknown: the controller may remain in ROM
  download mode. Do not describe it as a verified healthy r68 startup.

Espressif's troubleshooting guide associates this message with the host-to-
controller serial path, but this does not establish a permanent hardware
fault or its root cause. Similar prewrite failures were recorded in this
project previously. Reference:
https://docs.espressif.com/projects/esptool/en/latest/esp32/troubleshooting.html

No automatic retry, journal replacement, recovery reset or motion was
performed. Next requires separately authorized recovery/second installation
attempt, with the original failure retained, predecessor/settings verification
before writing, and fresh startup/source checks before the wrist trial.

## r69 retry installed; T4 wrist endpoint verified — 2026-09-24

The separately approved second attempt succeeded. Added a retry entry point
bound to the exact preserved first-failure journal/export and an exclusive
`app-r69-attempt2-deployment-events.jsonl`; the first journal was not altered.
Offline preflight and 33 existing installer/runner tests passed; an added
retained-failure/wrong-revision/tampered-report test also passed in the
30-test installer suite. No firmware source changes were needed.

The retry verified controller identity, installed r68 predecessor and settings
before writing. Full r69 image readback matched the reviewed hash and
protected regions were unchanged. Exactly one application startup reset
followed the successful write.

- Installation: `wizard-20260924T100111792398Z-e353d522b5d543b98ec35e62ac1b004a`.
- Startup: `wizard-20260924T100112147524Z-af49cad20ea342bc86eb5ab592724a00`.
- Boot: `4ea6cf4781ec4a1ff14ebbe6a45bf2bc`; stable IDLE, zero records,
  no storage fault before the trial.
- Result: `wizard-20260924T100122313690Z-ba8afa38d92b436c8f137dae16978a84`.

Fresh source and immediate prewrite checks passed; exactly one servo-15
write was sent. All three endpoint samples were identical. Durable export
and receipt completed; independent manifest verification and binary replay
matched the stored `T4_JOINT_ENDPOINT_MEASURED` assessment.

- Source positions: `2047,2225,1890,2780,1850,2041,2047`.
- Endpoint positions: `2047,2225,1890,2780,1912,2041,2047`.
- Goal readbacks: `2047,2217,1897,2777,1915,2040,2047`.
- Wrist movement: +62 counts (5.44921875 degrees) for a +65-count command.
  Final wrist error −3 counts (−0.263671875 degrees), within the configured
  12-count tolerance, not a zero-error arrival.
- All six passive servo positions unchanged. Final capture ended
  1590.095 ms after dispatch, not an independently measured motion duration.

No movement retry, return or follow-on command was sent. The r69 one-use
owner is consumed. T4 is now the latest verified joint endpoint. This
completes the shoulder-first then wrist sequence in encoder space; physical
TCP accuracy and board clearance remain unmeasured. Next analyze this
measured T4 endpoint against the larger-pose ladder before selecting any
further motion, and keep the original transient connection failure in the
diagnostic history rather than treating successful retry as a root-cause fix.

## Measured T4 to P4 extension review — 2026-09-24

Replayed the latest T4 record and verified its export before reviewing the
remaining P4 transition. Source positions:
`2047,2225,1890,2780,1912,2041,2047`; source goals:
`2047,2217,1897,2777,1915,2040,2047`.

Choose elbow-first T4 → P4E, then separately review the wrist adjustment
from the eventual measured P4E endpoint. Proposed first command: servo 14
to 2711, speed 20, acceleration 1. This is −66 counts from the goal but
−69 counts from the measured position. The other six goals remain unchanged.
Reducing this elbow angle moves away from its modeled upper limit.

The model predicts TCP `[167.254,0.256,37.419]` mm at the measured source
and `[197.670,0.302,46.544]` mm after the nominal elbow step: approximately
30.416 mm farther outward and 9.125 mm higher. Wrist-first would lower
modeled height to 33.302 mm. The later nominal P4 endpoint is
`[181.760,0.278,40.789]` mm, assuming previous encoder biases persist;
that assumption is not compensation or a measured physical result.

Reviewed 1,681 independent joint-progress samples, 82 elbow-first samples
and 161 samples over the first step's 0–80-count travel. The elbow-first
path did not lower nominal TCP height below its starting value; minimum
simplified capsule clearance was 25.750 mm. These are model-frame values,
not registered board clearance. Cables, full meshes, attached tool and full
multi-joint uncertainty remain unmodeled; samples are not collision proof.

- Review export: `wizard-20260924T100256902195Z-4d011572d1f24bdab6ed6cce4814c7b6`.
- Implementation: `p4_extension_review.py` and its offline export script.
- Sixteen focused/regression tests passed, including source replay, path
  ordering, wrong-boot rejection and truncated-record rejection.

No hardware access or movement occurred. Next implement the exact P4E
elbow policy, native owner/profile and authenticated runner, then compile
and review a candidate. Keep fresh-source/prewrite checks, the existing
80-count travel and 12-count endpoint bounds, durable export, one write,
no retry/return and no automatic wrist follow-on. r69 remains installed;
its prior one-use operation is consumed.

## r70 P4E elbow-extension workflow ready for release — 2026-09-24

Implemented the exact T4 → P4E elbow-only step from the hash-verified r69
source. Only four movement-specific firmware files changed: policy, owner,
routes and board-service write adapter. Servo 14 alone receives target 2711
at speed 20, acceleration 1; all six passive goals remain unchanged.

The authenticated selector is `P4E`, record domain `RCP4ELBW01`, and record
size 1129 bytes. Independent host assessment checks source, prewrite and
three endpoint samples before verified export/receipt. `run_p4_elbow.py`
replays the retained T4 result, binds a reviewed r70 startup and the live
idle boot, then takes an exclusive one-use claim. The native policy still
requires fresh source/prewrite readings before the only allowed write.

- Stage: `wizard-20260924T100455295758Z-b653676dd2154009b3887b84b383f6bb`.
- Compile: `wizard-20260924T100721432041Z-bec9d7ce872b4787bc49c972e7c6b265`.
- Review: `wizard-20260924T100747862852Z-c7418427c73b49d88f13873f383a6169`.
- App SHA-256: `d4e860492602492477e67e58436a681a252adc2b9eeb934315abb05b98113134`.
- App size 1,200,656 bytes; offset 0x10000, within the 0x140000 slot.
  Bootloader/partition identities unchanged. Offline installer preflight
  passed against r69 and the retained private filesystem hash.
- Final combined suite: 435 tests passed across the new owner, path review,
  runner, source specialization, signed transport, prior wrist workflow,
  startup/installation validation and installer preflight/retry guards.

No controller access, firmware installation, startup or movement occurred.
Await approval for one r70 app-only installation and one startup preserving
settings and credentials, followed by one elbow-only P4E trial if startup
and fresh position checks pass, then verified export and stop. No retry,
return or automatic wrist follow-on. r69 remains installed with its prior
one-use operation consumed. Modeled tip displacement is not measured
physical accuracy or registered board clearance.

## r70 installed; P4E elbow endpoint verified — 2026-09-24

The approved first installation attempt succeeded. Controller identity and
r69 predecessor/settings checks passed before writing. Full r70 app
readback matched the reviewed SHA-256; protected regions were unchanged.
Exactly one application startup reset was sent, preserving settings and
credentials.

- Installation: `wizard-20260924T101224074870Z-fe9c541323c64b76a2c405391a479197`.
- Startup: `wizard-20260924T101224479794Z-060e23e5efa1429b9236489f8f7d927a`.
- Boot: `30838e5a53f316c62ac21f976ce95424`; startup observations were
  stable IDLE, zero records and no storage fault.
- Result: `wizard-20260924T101235379282Z-701e8f9afca3454682c92dafbb258f43`.

The approved elbow-only trial passed fresh source/prewrite checks and sent
exactly one servo-14 write. Export and receipt completed. Independent
manifest verification and binary replay matched the stored
`P4E_JOINT_ENDPOINT_MEASURED` assessment.

- Source positions: `2047,2225,1890,2780,1912,2041,2047`.
- Endpoint samples: elbow 2717, 2716, 2716; all other servo readings fixed.
  The one-count span meets the configured stability rule; these are not
  three identical samples.
- Final positions: `2047,2225,1890,2716,1912,2041,2047`.
- Goal readbacks: `2047,2217,1897,2711,1915,2040,2047`.
- Elbow movement: −64 counts (−5.625 degrees), final error +5 counts
  (+0.439453125 degrees), within the configured 12-count tolerance.
- All six passive servo positions unchanged. Final capture ended
  1707.055 ms after dispatch; this is not independently measured motion time.

No retry, return or follow-on movement was sent. The r70 owner is consumed.
P4E is the latest verified joint endpoint. Next review the remaining wrist
step from these measured readings before preparing P4. Modeled outward/upward
tip displacement is not independently measured Cartesian accuracy.

## Measured P4E to P4 wrist review — 2026-09-24

Verified and replayed the latest P4E result before reviewing the final wrist
step of this ladder. Source positions:
`2047,2225,1890,2716,1912,2041,2047`; source goals:
`2047,2217,1897,2711,1915,2040,2047`.

Proposed command: servo 15 to 1980, speed 20, acceleration 1, with all six
passive goals unchanged. This is +65 counts from its previous goal and
+68 counts from its measured position. Nominal geometry assumes the prior
−3-count wrist bias persists; it is not a compensation correction or proof
that the next endpoint will retain that bias.

- Model-frame TCP: start `[196.763,0.301,46.223]` mm; nominal end
  `[180.835,0.277,40.516]` mm. This step lowers modeled height by about
  5.706 mm and follows the verified elbow extension.
- Swept 0–80 counts over 161 samples. Minimum model-frame TCP height:
  39.427 mm; minimum simplified capsule clearance: 25.750 mm.
- These are not real board-clearance or measured tip-accuracy values.
  Cables, full meshes, tool, registered board and full multi-joint
  uncertainty remain excluded; discrete sampling is not collision proof.
- Export: `wizard-20260924T101358360819Z-b5d80635ae6b4f5d814b0ceab56e1d68`.
- Added `p4_wrist_review.py`, its offline export script, exact
  `p4_wrist_policy.h` and native policy tests. Sixteen focused/regression
  tests passed, including source replay, wrong boot/truncated data and
  policy rejection of reverse/excess travel, drift and incorrect goals.

No controller access or movement occurred. Next wire the wrist policy into
the native owner/profile and authenticated runner, compile and review the
candidate. After a separately approved successful P4 trial, summarize the
whole ladder's measured errors before selecting another campaign; do not
extend the route automatically. r70 remains installed and its owner consumed.

## r71 P4 wrist candidate ready — 2026-09-24

Implemented the final P4 wrist step in the native one-use owner, authenticated
HTTP selector, host record assessment, startup binding and reproducible export
workflow. The runner independently replays the retained P4E source result.
Fresh source and prewrite checks are still required before the one write;
the retained endpoint is not treated as a permanently current pose.

- Command: servo 15 target 1980, speed 20, acceleration 1. Other goals unchanged.
- Profile/domain: `P4` / `RCP4WRST01`; record size 1129 bytes.
- One write attempt per boot; no retry, return or follow-on movement.
- Verify direction, endpoint tolerance, passive-joint drift and three stable
  fresh endpoint samples; export the record and acknowledge its digest.
- Stage: `wizard-20260924T181402812523Z-45ff9efa2a274067802d5b8524d00481`.
- Compile: `wizard-20260924T181633213678Z-41dc084be42d4fdc933239d4546d97ac`.
- Source/binary review: `wizard-20260924T181822158409Z-30e68aecefdc40658431d724744f39e9`.
- App SHA-256: `1ebaff62ea6348f072c35ce48005f67f5e2ff025c1c43de046ff23086bdcbf0b`.
- App size: 1,200,640 bytes; predecessor pinned to r70. Bootloader and
  partition artifacts unchanged. App-only deployment preserves settings
  and credentials, with protected-region verification.
- Installer offline preflight: `LOCAL_PREFLIGHT_VERIFIED`; no journal reserved.
- 444 software tests passed after release integration, covering native owner
  success/fault cases, exact source staging, authenticated transport,
  source/startup binding, installation evidence and deployment preflight.

No hardware access, startup, firmware installation or movement occurred in
this implementation turn. r70 remains the last installed image; P4E remains
the latest measured endpoint. P4 has not yet been physically tested.

Next approval scope: one r71 app-only installation and one startup preserving
settings and credentials, followed by one P4 wrist trial only if fresh checks
pass, with result export and stop. No retry, return or subsequent movement.
After a successful trial, aggregate the larger-pose ladder's endpoint errors
and limitations before choosing the next campaign. Camera, physical contact
and measured stylus/TCP accuracy remain deferred.

## r71 installed; P4 endpoint verified — 2026-09-24

Executed the approved one app-only installation, one startup and one wrist
trial. First installation attempt succeeded. Full app readback matched the
reviewed SHA-256; protected regions, settings and credentials were preserved.
Read-only startup checks found the same idle boot with no storage fault.

- Installation export: `wizard-20260924T182309016251Z-9f7e49bd105c4a55a9f701d7ed9eb0ff`.
- Startup export: `wizard-20260924T182309299685Z-0223594b3a744dcfabd5be4eed8de7ac`.
- Boot: `3ce87bcbe82e9ccdc6f8b46854e095b3`.
- Result export: `wizard-20260924T182321443347Z-87b68bc4624a4e1b80c6fb0af4027e5e`.
- Status: `P4_JOINT_ENDPOINT_MEASURED`; durable export receipt accepted.
- Wrist: measured 1912 to 1977, +65 counts (+5.712890625 degrees).
- Target readback: 1980; final wrist error -3 counts (-0.263671875 degrees).
- Three endpoint samples identical: `2047,2225,1890,2716,1977,2041,2047`.
- Final goals: `2047,2217,1897,2711,1980,2040,2047`.
- All six passive servo positions unchanged. Final capture completed
  1591.191 ms after dispatch; this includes settling/sampling, not pure motion time.

No retry, return or follow-on movement was sent. r71 is installed and its
one-use owner is consumed. P4 is the latest measured joint endpoint.

## Retained forward-ladder comparison — 2026-09-24

Added `scripts/summarize_p1_to_p4_ladder.py` to verify all nine source exports,
decode their raw records, independently reassess each endpoint, compare the
stored assessments and export a reproducible comparison without hardware access.
Executed successfully against all nine retained records. Summary export:
`wizard-20260924T182507431843Z-e99abc0411a8449780de7d2a9d9b0d4f`.

| Endpoint | Selected servos | Measured movement (counts) | Final target error (counts) |
| --- | --- | --- | --- |
| P1 | 14, 15 | -60, +67 | +2, +1 |
| P2L | 12, 13 | -65, +66 | +8, -6 |
| P2 | 15 | +64 | -1 |
| P3E | 14 | -64 | +3 |
| P3 | 15 | +66 | 0 |
| T4L | 12, 13 | -66, +65 | +8, -7 |
| T4 | 15 | +62 | -3 |
| P4E | 14 | -64 | +5 |
| P4 | 15 | +65 | -3 |

All nine transitions passed their encoder-domain endpoint checks. Maximum
selected-servo absolute endpoint error was 8 counts (0.703125 degrees);
mean absolute error across the 12 selected-servo endpoints was 3.9167 counts
(about 0.3442 degrees). Passive measured drift was zero in every transition.
Each subsequent measured starting pose exactly matched the preceding endpoint.

The shoulder pair shows a consistent signed offset in the two included pair
moves, while wrist errors range from +1 to -3 counts and elbow errors from
+2 to +5. These observations support testing for repeatable bias; they do not
justify applying a universal correction from this one forward traversal.

Next: review a bounded reverse/repeat route from the fresh P4 pose, including
intermediate geometry and preserved clearance margins, then compare repeated
and opposite-direction arrivals at shared endpoints. Do not automatically
reverse this ladder or assume a forward path validates the return. Prefer a
reviewed finite campaign over more isolated firmware revisions where practical.
No new compensation, larger extension or contact is authorized by this report.
The comparison excludes the initial P0-to-T1 transition and does not establish
repeatability, external TCP accuracy, keyboard accuracy or board clearance.

## Offline P4 reverse/repeat campaign review — 2026-09-24

Prepared an offline, wrist-only finite campaign from the verified P4 result.
No hardware access, installation, startup or movement occurred during review.
The current r71 one-use owner remains consumed; this proposal cannot run on it.

Two identical cycles, six legs each:
`1980 -> 1915 -> 1947 -> 1980 -> 1947 -> 1915 -> 1980`.
Only servo 15 changes; shoulder, elbow, base, roll and gripper goals remain
at the P4 values. Each command delta is 32, 33 or 65 counts. Proposed speed
20 and acceleration 1 remain unchanged to avoid confounding speed with direction.

This provides two positive-direction and two negative-direction arrivals at
midpoint 1947, plus repeated low/high endpoints. Compare signed target error,
within-direction spread, midpoint direction bias, passive drift and timing.
Two cycles are an initial screening dataset, not a general compensation model.
Do not change compensation during the campaign; retain failures as well as passes.

Implementation artifacts:
- `src/rocell/application/p4_repeat_campaign_review.py`: source-bound route and sweep.
- `scripts/review_p4_repeat_campaign.py`: independently replay and export review.
- `tests/unit/test_p4_repeat_campaign_review.py`: route, direction coverage,
  passive goals, source identity/framing and model hash rejection tests.
- Review export: `wizard-20260924T182815946525Z-43b9ae42fe5f41b1b6c13daf14ecf825`.

The review covers the union of the proposed 80-count per-leg travel envelopes,
including the 12-count preceding endpoint tolerance: wrist 1855..2039 counts,
369 half-count samples. Minimum model TCP Z is 36.577 mm; minimum simplified
capsule clearance is 25.750 mm. Passive logical angles are held fixed in this
review; full multi-joint uncertainty, cables, meshes, attached tool and board
registration remain excluded. These are not measured physical clearances.

Next implementation sequence:
1. Add one exclusive finite campaign owner for these 12 fixed legs, not a
   firmware revision per leg. No arbitrary targets or automatic retry.
2. Bind initial admission to fresh three-snapshot P4 checks. Before each leg,
   compare fresh position to the previous measured endpoint, not just its goal.
3. Verify goal readback, motion direction, bounded travel, settled endpoint
   and passive drift. Passive drift must remain within two counts of the
   campaign baseline so small per-leg deviations cannot accumulate unchecked.
4. Export each leg's raw evidence and obtain its durable receipt before the
   next leg. Stop on uncertain delivery, bad feedback, timeout, drift or export
   failure. Never attempt a recovery return after failure.
5. Test simulated completion and failures at every leg boundary, including
   duplicate/reordered receipts, lost delivery and export failure. Review the
   geometry against the final implemented limits and uncertainty handling.
6. Build/review a single candidate, then obtain approval for its installation,
   startup and bounded campaign. No physical campaign is authorized by this review.
7. Summarize results before expanding to elbow/shoulder reverse tests. These
   require their own route review; wrist results do not validate them.

## Finite campaign core and export simulation implemented — 2026-09-24

Implemented offline components, not a deployed firmware candidate:
- `firmware/diagnostics/p4_repeat_policy.h`: fixed twelve-leg wrist targets;
  initial P4 gate; subsequent source based on last measured endpoint; passive
  drift bounded against the original campaign baseline as well as per leg.
- `firmware/diagnostics/p4_repeat_owner.h`: fresh start/prewrite/endpoint
  capture, one write attempt per leg, ten-second leg deadline, immutable
  leg record, ordinal/digest-bound receipt, finite completion and fault stop.
- `src/rocell/application/p4_repeat_campaign.py`: independent record assessment,
  boot/leg/target/chronology checks, per-leg durable exports, failure exports
  retaining invalid raw records, no command or receipt retry.
- `scripts/simulate_p4_repeat_campaign.py`: compiles and runs the native test
  executable, then drives the host against those records without hardware.

Important two-phase progression: accepting an export receipt enters READY_NEXT,
not movement. A separate next-leg command is required after the host receives
the receipt acknowledgment. Lost receipt replies therefore do not start the
next leg. A lost next-leg reply can mean that leg started: the host stops and
does not retry; native per-leg bounds and the next export gate still apply.
Receipt/next admission expires after thirty seconds when attempted late.
Completed or faulted owners cannot restart, and wrong/duplicate/reordered
receipts cannot advance them.

Validation: 135 focused/native/regression tests passed, including completion,
native delivery/evidence/drift/source/prewrite/timeout/receipt-expiry failures
at every leg, host export and lost-receipt failures at every leg, and uncertain
next-command delivery at every next-leg boundary. Native tests use a mock
digest callback; production integration must supply SHA-256 over exact record
bytes and authenticate all state-changing routes.

The end-to-end simulation completed twelve legs and verified twelve exports
explicitly labeled `source_kind=simulation`. First export:
`wizard-20260924T183546718438Z-73de638d4ce1434e885b169ade32781f`;
last export: `wizard-20260924T183547174982Z-9a506b5794c74c8f914bb414273e92f1`.
They are synthetic native-owner evidence, not physical motion measurements.

Remaining before physical release: connect authenticated start/status/record/
receipt/next routes and real acquisition/write/hash adapters, enforce exclusive
ownership against other diagnostic paths, bind to reviewed startup and campaign
intent, add replay/route/resource tests, review final geometry against exact
runtime limits, then compile/review one candidate. The host currently rejects
claims of a released live transport. No firmware was installed, no startup
performed and no hardware moved this turn. r71 remains installed/consumed;
P4 remains the most recent physical endpoint.

## r72 authenticated campaign candidate prepared — 2026-09-24

Connected the fixed twelve-leg core to authenticated firmware routes:
`/rocell/p4-repeat/start`, `/status`, `/record`, `/receipt`, `/next`.
Start accepts only `P4R12`; next accepts the exact current ordinal; receipts
bind ordinal and SHA-256 of the immutable record. Methods, paths, bodies, boot
and sequence are covered by the existing request HMAC and signed responses.
The host transport validates exact request forms before opening a socket.

The existing enabled one-shot route slot now aliases the repeat routes; the
old wrist route is not registered alongside it. Existing shared reservation
checks exclude other diagnostic owners and configuration activity. The board
adapter reuses fresh seven-servo acquisition and permits only servo 15 with
targets 1915/1947/1980, speed 20 and acceleration 1; the native owner enforces
the exact twelve-leg order. Reservation also checks available memory.

`scripts/run_p4_repeat_campaign.py` requires reviewed r72 installation/startup
evidence, independently replays the retained P4 source record, checks the live
boot remains idle, and creates an exclusive campaign claim before the signed
start. The compiled owner still checks freshly acquired physical positions;
retained P4 data is not treated as a current observation. No claim or hardware
request is made in the runner's offline preflight mode. Result exports label
controller feedback separately from simulated data. They do not claim external
physical accuracy.

Build/review evidence:
- Initial offline compile failed on an array-reference versus pointer mismatch
  in the SHA-256 callback. Failure retained as
  `wizard-20260924T183929745331Z-73f4deb415fb41de8f9c3f1795548320`.
  Corrected the callback signature; no hardware was involved.
- Corrected stage: `wizard-20260924T183936479338Z-7b77caf74e79412fbf3851dfec999faf`.
- Successful compile: `wizard-20260924T184102787182Z-e6daa16054ff4961875b00e4ea99ee77`.
- Source/binary review: `wizard-20260924T184141008989Z-79063803346e4c808f31072252a55339`.
- App SHA-256: `e8d27dc8085d4e21ae6450be4eff0c41eb46a39962ba2d47baf084b01ee3afe9`.
- App size 1,202,960 bytes; predecessor r71 pinned. Bootloader and partition
  artifacts unchanged; deployment is app-only with protected-region checks.
- Offline installer result: `LOCAL_PREFLIGHT_VERIFIED`, no journal reserved.
- 543 focused tests passed: native campaign and staged twelve-leg routes,
  host fault/export handling, signed loopback request validation, source/startup
  binding, installation evidence and deployment preflight regression checks.

The native/host boundaries and actual built route were tested offline, not as
a physical campaign. The sampled geometry review remains conditional on its
fixed passive angles and omissions; it is not board-clearance certification.
Full runtime heap/stack sufficiency is still to be observed at startup and
during the approved campaign. Early native faults currently export terminal
status/context; raw completed-leg records are exported when available, but
this is not a continuous trace of every rejected/transient sample.

Next approval scope: one r72 app-only installation and one startup preserving
settings and credentials, followed by the fixed twelve-leg wrist campaign
only if fresh admission checks pass. Export each verified leg before explicitly
admitting the next; stop on any failure. No retry, recovery movement, extra
cycles, other-joint moves or contact. The campaign may finish at its high goal
but must never force a return after a failure. Afterward summarize direction
bias and repeated arrivals before selecting more tests.

No firmware installation, startup, hardware query or movement occurred in this
implementation turn. r71 remains installed and consumed; P4 is the last
physical endpoint. r72 is only a reviewed local candidate until approved.

## r72 physical twelve-leg campaign completed — 2026-09-24

Approved app-only installation succeeded on the first attempt. Independent
full readback matched the reviewed r72 hash; protected regions, settings and
credentials were unchanged. One startup passed idle/status checks.

- Installation export: `wizard-20260924T184756167890Z-bba9dcbafc854aabb5fc6ec3222d25f5`.
- Startup export: `wizard-20260924T184756493434Z-16cba9d682274d04bd3422db31b95065`.
- Boot: `bc34f3be743dad1a774e82cfac95280e`.
- Startup reported free heap 125,652 bytes and largest block 59,380 bytes.
  No continuous heap/stack trace was collected; these are startup observations.
- Campaign status: `CAMPAIGN_COMPLETE`, twelve verified legs and twelve
  accepted durable-export receipts. No retry or extra movement was sent.
- First leg export: `wizard-20260924T184809085534Z-0f2f1de8868040d8907b9bac40cd6590`.
- Last leg export: `wizard-20260924T184828853128Z-3b158e1a3d1b4dde88ab51efacd18f37`.
- Summary export: `wizard-20260924T184928945241Z-a5a64a08eb254bd0bb0a2b7110fdc2da`.
  `scripts/summarize_r72_campaign.py` independently replays all twelve raw
  records and checks their saved assessments before generating the comparison.

| Wrist target | Approach | Measured endpoints | Target errors | Spread |
| --- | --- | --- | --- | --- |
| 1915 | decreasing | 1918, 1918, 1918, 1918 | +3 each | 0 counts |
| 1947 | increasing | 1947, 1947 | 0 each | 0 counts |
| 1947 | decreasing | 1950, 1950 | +3 each | 0 counts |
| 1980 | increasing | 1979, 1979, 1977, 1977 | -1, -1, -3, -3 | 2 counts |

Maximum selected-wrist absolute error: 3 counts (0.263671875 degrees).
Mean absolute selected-wrist error: 2.1667 counts (0.1904296875 degrees).
All reported endpoints kept the six passive servo positions unchanged.
The midpoint's decreasing-versus-increasing arrival offset repeated at
3 counts in both cycles. This demonstrates a local direction-dependent
endpoint difference, not a proven mechanical root cause. The high endpoint
also varied by two counts between cycles despite the same approach direction.

Final measured positions: `2047,2225,1890,2716,1977,2041,2047`.
Final goals: `2047,2217,1897,2711,1980,2040,2047`.
r72 remains installed, and this boot's campaign owner is consumed. Movement
has stopped. These are controller-feedback results, not external stylus-tip
measurements, and no compensation was applied.

Best next step: preserve this baseline and repeat the unchanged campaign in
a separately approved startup/session before changing commands or firmware.
This tests whether the same direction effect survives another admission and
whether the high-end variation is consistent. Fresh P4 checks still apply.
Then evaluate a small direction-aware correction offline and validate any
candidate on held-out arrivals before applying it broadly. Do not expand to
shoulder/elbow or change speed simultaneously with compensation. Reusing the
same reviewed image avoids a firmware change per experiment.

## Unchanged r72 campaign repeated across startup — 2026-09-24

Performed one approved startup of the existing r72 image, then twelve more
verified physical wrist legs. No firmware, settings, speed or compensation
changes were made. The new restart helper initially failed to import serial
before USB was opened or any reset claim was reserved. Fixed its local module
path to use the installer's bundled serial tools, then sent exactly one reset.

- Restart receipt: `wizard-20260924T185129548730Z-906955ceaf1747d98fb26a0b9395c038`.
- Startup: `wizard-20260924T185156636944Z-5e8111ae734e4499b8742e6579e933f7`.
- New boot: `62d0bf638a2d7763a452fa8eb7c19198`.
- First leg: `wizard-20260924T185209342095Z-e971ca519e004b439811f12c235c9612`.
- Last leg: `wizard-20260924T185228366510Z-b0da455a91d347afb407d54fb53ed9e0`.
- Independently replayed summary:
  `wizard-20260924T185253127570Z-3b13c2395f064910a7cb46aeaf469527`, generated by
  `scripts/summarize_r72_second_campaign.py`.

All twelve legs passed with durable receipts; no retry or follow-on movement.
Second-session wrist endpoint errors: low/decreasing +3 counts on four
arrivals; midpoint/increasing 0 on two; midpoint/decreasing +3 on two;
high/increasing -3 on four. Every target/direction group had zero endpoint
spread within this session. Worst absolute error remained 3 counts (0.264
degrees); mean absolute error was 2.5 counts (0.220 degrees). All six passive
servo endpoints remained unchanged.

Across the two sessions, 24 physical legs are now verified. Midpoint direction
bias repeated at 3 counts; low/decreasing arrivals repeated exactly. High/
increasing arrivals range from 1977 to 1979 across sessions, so a constant
correction there still carries observed variability. This is a local wrist
result at the tested pose/speed, not a model for every joint or configuration.

Final measured positions remain `2047,2225,1890,2716,1977,2041,2047`; goals
remain `2047,2217,1897,2711,1980,2040,2047`. The second boot's campaign owner
is consumed. r72 remains installed and movement has stopped.

Next: freeze a small goal-and-direction prediction table from session one,
score it against session two without fitting to those held-out results, and
review a bounded physical correction comparison. Separate prediction of
unchanged-command feedback from proof that modified commands improve arrival.
Do not change firmware or apply a correction until the candidate comparison
and its movement envelope are reviewed. No additional session is implied by
the completed second-session approval.

## Frozen local endpoint prediction evaluated — 2026-09-24

Implemented `p4_endpoint_prediction.py` and
`scripts/review_p4_endpoint_prediction.py`. Independently replayed the raw
records in both sessions, fitted only session-one cell means, exported the
immutable table before evaluation, and scored session two without refitting.
Both sessions had already been observed: this is a retrospective split, not
a prospectively blinded held-out experiment.

| Command goal | Approach | Session-one learned readback bias | Predicted readback |
| --- | --- | --- | --- |
| 1915 | decreasing | +3 | 1918 |
| 1947 | increasing | 0 | 1947 |
| 1947 | decreasing | +3 | 1950 |
| 1980 | increasing | -2 | 1978 |

Session-two prediction errors were zero on eight arrivals and -1 count on
the four high-goal arrivals. Mean absolute prediction error: 0.3333 counts;
maximum: 1 count (0.087890625 degrees). Predicting readback equal to the
command goal instead gives mean error 2.5 and maximum error 3 counts.
These compare predictions of unchanged-command feedback, not physical
accuracy improvements from compensation. No command was modified or sent.

- Model export: `wizard-20260924T190541946562Z-56d909092e904531b2ff8779c3e92a00`.
- Model SHA-256: `ba2bb2d9cc7151cd97dab7bcf6a8719d4a7824f4d6eb6de5a286f5be622b880a`.
- Evaluation: `wizard-20260924T190542092699Z-be39d5697321406a86b95d8cf655c024`.
- Eight tests passed, covering retained split scoring, immutable fit,
  unseen goal/direction rejection, changed speed/passive goals, reused training
  boot, incomplete/reordered evaluation and no refitting during evaluation.

The lookup is deliberately local: four observed command/direction cells,
fixed passive goals, speed 20 and acceleration 1. It rejects unseen cells
and does not interpolate, extrapolate, or compensate other joints. The actual
tested pose/load context still matters; checking goals alone cannot establish
that all physical conditions are unchanged.

Next experiment to review offline: compare the unmodified decreasing-direction
midpoint command 1947 against candidate command 1944, both aiming for desired
measured endpoint 1947 and approached from the same high anchor. The -3-count
correction is a hypothesis based on repeated local bias, not a prediction at
an already-trained command: 1944 is an unseen command. Preserve separate fields
for desired endpoint, transmitted goal, readback goal and measured endpoint.
Use a predeclared balanced baseline/candidate order, unchanged speed and
anchor, and measure improvement against desired endpoint as well as variation.
Do not tune the correction using its validation arrivals. Review the resulting
path and failure bounds before compiling or authorizing physical testing.
Defer the more variable high-goal correction until this cleaner comparison.

No hardware access, startup, firmware/settings change or movement occurred
during this analysis. r72 remains installed with the second campaign consumed.

## Local correction comparison reviewed offline — 2026-09-24

Implemented `p4_correction_comparison.py`, its offline export script and four
tests. Replayed both retained sessions: the four decreasing midpoint arrivals
all had +3-count command-to-readback error. The new command 1944 remains an
untested hypothesis, not a validated lookup cell.

Predeclared comparison: desired measured wrist endpoint 1947; baseline command
1947 versus candidate command 1944. Condition order is A,B,B,A,B,A,A,B, where
A is baseline and B is candidate. Each comparison is followed by a separately
verified/exported anchor command 1980: 16 total legs, four arrivals per condition,
balanced mean order, fixed servo 15, speed 20 and acceleration 1. No other
joint is commanded. Maximum command separation is 36 counts. All descending
comparisons require measured high-anchor position 1977..1979; retain exact
anchor position for stratified analysis. Same commanded anchor does not imply
identical physical starting position.

Keep four distinct values in every result: desired endpoint, transmitted goal,
goal readback and measured position. A candidate reaching 1947 has zero desired
error but +3 command-tracking error. Do not conflate these metrics.

Success criteria frozen before execution: all 16 legs verified and exported;
candidate maximum absolute desired-endpoint error <=1 count; mean absolute
error improvement >=2 counts over baseline; candidate spread <=2 counts and
no larger than baseline spread. Report all signed errors and anchor strata.
Incomplete runs are inconclusive, not successful. Scientific failure must not
trigger retuning, extra trials, retries or relaxation of execution bounds.
A successful screen is local evidence only; replication precedes wider use.

Sampled wrist envelope 1888..2039 counts (303 half-count samples) lies within
the prior 1855..2039 review. Minimum model TCP Z is 36.5766 mm and minimum
model capsule clearance is 25.7501 mm. These use fixed passive logical angles,
not full joint uncertainty, meshes, cables, stylus or registered board. They
are not measured physical clearance or proof of collision-free execution.

Review export: `wizard-20260924T191123383234Z-e63788ad468144eba7a92798afc4ae22`,
attachment `p4-correction-comparison.json`. Twelve focused tests passed (four
comparison tests plus eight prediction tests), covering balanced routing,
desired-versus-command separation, envelope, frozen criteria, model pinning
and prior prediction scope. Export integrity verified.

Next implementation: add the exact finite comparison route to a separately
reviewed native candidate and independent host assessment, retaining fresh
source/prewrite checks, passive/global drift bounds, one-write semantics and
per-leg export admission. Simulate failures and condition-specific scoring
before candidate build/deployment review. r72 does not accept this route;
do not send new targets through its consumed owner or reuse its boot claims.
Installation/startup and the physical campaign remain separate future actions.

No hardware access, startup, firmware/settings changes or movement occurred.

## Finite correction core implemented and simulated — 2026-09-24

Added isolated `p4_correction_policy.h` / `p4_correction_owner.h` candidate
cores and independent `p4_correction_campaign.py` host assessment. Existing
r72 repeat-policy files and installed firmware are unchanged. The candidate
uses fixed 16-leg order and domain `RCWRCMP001`; its prospective route prefix
is `/rocell/p4-correction/` with start token `P4C16`. No authenticated route,
release runner or deployment candidate has been connected yet.

Native and host checks enforce high-anchor range 1977..1979 throughout each
comparison's three source samples and prewrite sample. Existing freshness,
source matching, endpoint direction/travel, passive/global drift, exclusive
ownership and per-leg receipt/explicit-next semantics are retained. Candidate
target 1944 does not alter the prior r72 command allowlist.

Added `p4_correction_scoring.py`: independently replay all 16 records, then
calculate desired-endpoint errors separately from command-tracking error.
Apply frozen improvement/spread criteria and report actual anchor distribution.
Unequal anchor distributions require review, even if numeric criteria pass.
Incomplete/reordered records cannot yield a completed screening result.
Caller still must verify exported evidence integrity and provenance.

`scripts/simulate_p4_correction_campaign.py` compiled the native core, produced
16 synthetic records, passed them through the host's independent verification
and per-leg export/receipt workflow, and exported summary
`wizard-20260924T191454801535Z-ae0dbba0d5504aaeb9d1460cb318c2c3`.
Synthetic plant deliberately supplies +3-count descending bias: baseline
desired errors are +3 and candidate errors zero. This tests software scoring,
not real correction effectiveness. Summary and all leg exports are explicitly
labelled simulation; no physical accuracy or hardware validation is claimed.

Regression run: 287 tests passed across correction core/comparison and existing
repeat core. An additional no-benefit synthetic-plant case verifies that 16
valid moves can correctly fail correction success (zero MAE improvement).
Fault tests exercise delivery, passive drift, evidence, source, prewrite,
timeout and receipt expiry at every leg, plus host receipt loss, export failure
and uncertain next-command responses without retries or subsequent admission.

Next: integrate this fixed candidate with authenticated routes and release
bindings, build/review its source and binary, then seek the scoped installation
and physical comparison approval. No hardware was accessed or moved here.

## r73 authenticated comparison candidate — 2026-09-24

The fixed sixteen-leg comparison now has authenticated controller routes,
bounded HTTP requests, native owner tests, a host runner, and an independent
review of exported leg records before scoring. The installed r72 route is
replaced in the r73 candidate's exclusive composition slot; the board write
adapter accepts only wrist targets 1944, 1947 and 1980 with speed 20 and
acceleration 1. Start selector is `P4C16`, record domain `RCWRCMP001`, and
the route prefix is `/rocell/p4-correction/`.

The r73 candidate was reconstructed from pinned r72 staged sources. The
source and binary review verified exact source hashes, selector/route/domain
markers, build profile, app slot size and unchanged bootloader/partition
artifacts. Local installer preflight verified the predecessor r72 app and the
preserved filesystem image. Results:

- Stage export: `wizard-20260924T191757232558Z-320c6ffdacd04bb093466d3248b2953e`.
- Compile export: `wizard-20260924T192012116855Z-79eccb30246b41a9a6bfb7c2d150a932`.
- Source/binary review: `wizard-20260924T192053184753Z-50d3d6002a3a4585aeb61fe82f63621c`.
- App SHA-256: `ec2b9f63e6c2157185584f596a7a04551c995bed9de811d9bcd94b7bc3c2373a`;
  1,203,040 bytes at app offset `0x10000` in `0x140000` slot.

`run_p4_correction_campaign.py` binds an installed r73 startup to one new
boot claim, checks idle live status, executes the fixed campaign once and
scores all sixteen independently verified exports. The scorer rejects missing,
duplicate, changed, reordered or boot mismatched records. It reports endpoint
improvement separately from command tracking and marks the comparison for
review if starting anchor distributions differ. Its summary is an evidence
export, not a Cartesian or stylus accuracy measurement.

The candidate is locally reviewed; the physical correction experiment has not
yet run. The prior two r72 sessions provide the comparison hypothesis only.

## r73 physical correction comparison — 2026-09-24

r73 was installed with one app-only write and one startup. The installer
verified the full application readback and reported unchanged protected
regions. The read-only startup observation returned stable IDLE status,
matching boot `3b61679887bee5e72bc70ca6ffdf7344`, no storage fault and
unchanged paired capabilities. Its startup export is
`wizard-20260924T192921249845Z-23e995d3edff4751a64d9b7d69c3f92a`.
The read-only campaign preflight independently replayed the retained source.

The one-use physical comparison completed all 16 legs. Each leg's raw
controller record was independently assessed and exported before the next leg.
No retries or follow-on commands were sent. Passive joints remained within
the campaign's baseline bounds. The final verified positions were
`2047,2225,1890,2716,1978,2041,2047`; final goals were
`2047,2217,1897,2711,1980,2040,2047`. The boot campaign owner and host claim
are consumed.

| Condition | Command | Measured wrist positions | Mean absolute error from desired 1947 |
| --- | ---: | --- | ---: |
| Baseline | 1947 | 1950, 1950, 1949, 1949 | 2.5 counts |
| Candidate | 1944 | 1946, 1946, 1946, 1946 | 1 count |

The candidate improved mean error by 1.5 counts and met the predeclared
maximum-error and spread limits. It did **not** meet the predeclared
improvement threshold of 2 counts. Starting anchor positions also differed:
baseline `1979,1979,1978,1978`; candidate `1978,1977,1978,1977`. On the two
arrivals per condition sharing anchor 1978, baseline absolute error was 2
counts and candidate absolute error was 1 count. This local matched subset is
informative but was not the registered primary comparison. The result remains
`REVIEW_REQUIRED`; command 1944 is not promoted as a general wrist correction.

Physical summary export:
`wizard-20260924T193000463098Z-0dd40c9e0c784847bda008593634ad38`.
Its original `limitation` field uses a generic scorer phrase mentioning
synthetic records; this run's `source_kind` is `controller_feedback` and all
16 underlying leg exports were replayed. The scorer text was clarified after
the immutable export. These observations concern servo joint readback, not
externally measured stylus position.

Next analysis should treat this as exploration for a new, separately frozen
comparison. An intermediate command 1945 is a plausible hypothesis because
1944 arrived at 1946 while 1947 arrived at 1949–1950; it is untested and
must not be silently substituted into normal control. A stronger design
balances actual anchor positions or stratifies by them, and compares a new
candidate on a fresh boot. Do not reuse the consumed r73 owner, reinterpret
the failed success threshold, or add trials to this finished campaign.

## Prospective r74 midpoint screen — frozen before testing

The next question is whether wrist command 1945 can land near desired readback
1947 from the familiar high anchor. This is a new test informed by r73, not a
rescoring or extension of its consumed campaign.

Use the r73 final measured pose as source: positions
`2047,2225,1890,2716,1978,2041,2047`; goals
`2047,2217,1897,2711,1980,2040,2047`. Keep servo 15, speed 20,
acceleration 1 and the same passive-joint bounds. Compare existing 1944 (A)
with untested 1945 (B), both aimed at desired measured 1947. Use fixed order
`A,B,B,A,B,A,A,B`, each low arrival followed by high-anchor command 1980:
16 maximum writes, four arrivals per condition. Admit the next leg only after
fresh verification and a durable export receipt; no retry or new target input.

Primary screen: all 16 legs and exports complete; all four B arrivals within
one count of 1947; B mean absolute error at most 0.5 count; B spread at most
one count. Compare A and B within overlapping observed anchor strata and
report anchor distributions. If conditions have no common anchor, the
comparative result is inconclusive even if the absolute B screen passes.
Do not demand a 2-count improvement: r73 showed only one count of potential
gain from 1944. A passing local readback screen still does not validate stylus
contact position or transfer across other poses, speeds or loads. Run no extra
trials to rescue a failure. Do not adopt 1945 before physical results and a
later independent check if broader use is needed.

## r74 physical midpoint screen — 2026-09-24

The r74 app-only image (SHA-256
`1f2c6822f428b9dd9fdf2eb17444d3f89f5d7243a7aad89edae4acda0b721bc5`)
was installed with full application readback verification. The bootloader,
partition table, settings, and credentials were preserved. The read-only
startup was stable and IDLE on boot `05b842d721c1ec3519d8a7bc7909b061`;
startup export: `wizard-20260924T194400190225Z-31375c578b884d52ad4e738a4cd265c6`.
The runner's read-only preflight then matched the installed boot and replayed
the r73 source evidence before admitting movement.

The single-use physical campaign completed all 16 predeclared wrist legs,
with an independently verified export after every leg. No retry or additional
movement was issued. The last anchor leg left measured positions
`2047,2225,1890,2716,1979,2041,2047` and goals
`2047,2217,1897,2711,1980,2040,2047`. The boot owner and host claim are
consumed. The immutable campaign summary and its source-export list are in
`runs/wizard-exports/wizard-20260924T194534566569Z-9bccccf548084617b78cd5290a1482ef`.

| Condition | Wrist command | Four measured low endpoints | Error from desired 1947 |
| --- | ---: | --- | ---: |
| A, existing candidate | 1944 | 1946, 1946, 1946, 1946 | -1 count each |
| B, midpoint candidate | 1945 | 1947, 1947, 1947, 1947 | 0 counts each |

The predeclared B screen passed: 16 verified/exported legs, all four B
arrivals within one count, B mean absolute error zero, and B spread zero.
Starting anchors were not balanced (A: `1978,1977,1977,1977`; B:
`1978,1978,1979,1978`). There was one overlapping anchor-1978 A arrival and
three B arrivals; their respective mean absolute errors were 1 and 0 count.
That supports only a narrow local comparison, not a general command map.
The result is `LOCAL_SCREEN_PASS`, not a measured Cartesian or stylus-position
accuracy claim. Do not silently apply command 1945 to other starting poses,
speeds, loads, or directions. A later independent check can decide whether to
make it an explicitly bounded local calibration entry; meanwhile use this
evidence to advance the ghost-keyboard movement work rather than continuing
one-count tuning in this single joint/pose.

## P4-to-ghost route gap review — 2026-09-24

The existing three-key A–B–A ghost layout remains a nominal simulation at
`software/config/ghost_keyboard_v1.json`, not a registered location on the
plywood board. Its 12-leg sampled route passed offline, and the nine-case
synthetic endpoint/fault suite passed with verified export
`wizard-20260924T194916391573Z-ed0ecd550e8b48e5b41d341640df6bf7`.
Nineteen focused ghost/ladder tests passed. These checks sent no commands to
the arm and observed no actual keys or tip position.

The r74 last-leg controller positions, under the existing provisional
count-to-angle and pinned firmware-reference FK assumptions, project to an
end-edge reference of approximately `(182.62, 0.28, -83.46)` mm with pitch
`1.1904` rad. The nominal ghost route begins at `(340, 0, 230)` mm with pitch
zero. Their straight-line separation is about **350.75 mm**, before considering
link/cable sweep or the large pitch change. This is a comparison within an
unregistered controller model, **not** a measured physical gap or a safe
trajectory. The paired shoulder feedback is also not a complete independent
geometry measurement. Therefore neither the r74 local wrist correction nor
the passing ghost simulation admits a direct live move to the old ghost route.

Next, construct a separate *local* ghost preview anchored to a freshly read
P4-class pose, with small upward free-space offsets and three virtual key
positions. Retain the old layout unchanged for regression. Screen every
interpolated joint and link proxy, preserve the observed starting pose, and
compare the proposed route with the current physical clearance before any
live first leg. Run one finite noncontact leg at a time, exporting verified
endpoint feedback before advancing. Do not call the local virtual plane the
real keyboard or infer stylus-tip accuracy from controller readback.

### P4-relative ghost preview implemented

`local_p4_ghost_preview.py` now uses only the exact final r74 feedback counts
and the pinned URDF/reference equations. Its read-only runner replays all 16
r74 exports and checks the saved summary before producing a separate local
preview. The virtual row is A–B–A at 10 mm pitch in the model's controller
frame. Its imaginary surface is 30 mm above the projected P4 end edge; each
key has travel at +40 mm, hover at +34 mm, imaginary downstroke to +30 mm,
and retract to +40 mm. This does **not** move the old full-size ghost layout
or assert a physical keyboard position.

The 12-leg, 2-mm-sampled route passed reference IK/roundtrip and provisional
joint bounds. Minimum modeled nonadjacent link-axis proxy separation was
55.75 mm and minimum modeled URDF TCP Z was 42.37 mm, both in unregistered
model coordinates. These numbers omit cables, the actual tool, bench contact,
installed controller interpolation and independent tip tracking; they are
not physical clearance margins. Four new preview tests and the related
regressions passed (186 tests total). Verified offline export:
`wizard-20260924T195246740464Z-536e1f2467f143b2a0c31711b4e557cd`.
The earlier export
`wizard-20260924T195233210478Z-040cf04359a143a59e6740883f3ecfd8`
is superseded because its report digest did not include the later-added source
identifiers; the corrected export does.

Next candidate for physical review is only the upward *approach* from P4,
not the 12-leg key sequence. Split the 40 mm modeled rise into small bounded
targets, compare the native command/sweep representation against the model,
refresh the real source pose and clearance, then qualify one leg with a
durable endpoint export. No movement follows automatically from this preview.

## Larger noncontact A–B–A movement — prospective r75

The user wants visible dynamic motion without a mounted stylus. The r74
one-use owner is consumed, and the vendor all-joint angle command would
recompute both shoulder servo goals from a single logical angle, discarding
the paired-goal offset preserved in the verified P4 source. Do not use that
generic command as a shortcut for this campaign. Prepare a new fixed-count,
one-boot finite route retaining the paired source goals.

`local_air_typing_recipe.py` freezes a 17-leg hypothesis: four 10-mm modeled
upward increments; A hover/imaginary downstroke/retract; 30-mm lateral travel
to B in two 15-mm increments; B hover/downstroke/retract; two 15-mm increments
back to A; final A hover/downstroke/retract. The imaginary surface is 30 mm
above the provisional P4 end-edge reference, with a 4-mm virtual stroke and
40-mm travel offset. The 30-mm virtual key spacing is intentionally enlarged
for visibility and is **not** a real keyboard pitch. Joint goals are derived
as deltas from the r74 verified source goals, including the shoulder follower.
Each leg changes any one servo goal by no more than 80 counts at planned speed
20/acceleration 1. No tool, camera, phone or physical key contact is involved.

Before live use: pin and review all 17 seven-servo target rows and sampled
model sweep; implement a single native owner that admits only that recipe;
test wrong source, passive drift, stale feedback, partial/uncertain write,
bad endpoint and missing export receipt. On a fresh startup, require three
current source samples matching the P4-class position and exact goals. For
each leg, export and independently replay the controller's raw before,
prewrite and endpoint record before admitting the next. Stop on any fault,
with no retry or automatic return. The first four lift legs are the initial
physical milestone; lateral/virtual-key legs only follow if each prior leg
passes. The board/cable clearance and installed interpolation remain unproven
by the model, so modeled pass alone is not permission to descend or contact.

### r75 implementation and first physical trial — 2026-09-24

The fixed `AIR17` native owner, authenticated routes, board adapter, independent
host record verifier, export-gated progression, offline stage/review, and
read-only startup check were implemented. Native owner/host tests passed 141
cases, including fault injection at every one of the 17 legs. The compiled
app-only image SHA-256 is
`da56d6d353918f2654f919914a48a8de4f3a7377ee718c5c122dac397bb92f2d`.
The application was installed and read back; protected bootloader, partition
table and filesystem/settings were unchanged. Startup was stable and IDLE on
boot `a04ef5947ac2e620be6ab80acd16a4d5` (export
`wizard-20260924T203256664624Z-fe37e22bcd32471a9b3f02b8c3d97ad5`).

The one-use physical run verified and durably exported **eight** consecutive
legs. These included four upward approach/travel increments, the first A
virtual hover/downstroke/retract, and the first lateral increment toward B.
No stylus or physical key was contacted. On leg 8, controller positions were
`[2001,2082,2033,2609,2233,2041,2047]`, with reported goals
`[1994,2076,2038,2598,2234,2040,2047]`; the largest absolute count error
was 11. These are controller feedback values, not a measured tool-tip path.

The ninth leg did **not** verify. The host stopped on an unexpected controller
state and exported the fault in
`wizard-20260924T203339762923Z-c480bd69c444485fab0514416b8d5801`.
A separate signed GET-only status reconciliation, with no command or retry,
found `DEADLINE_EXPIRED|9` in
`wizard-20260924T203544393845Z-e1c183d31bd343c98202384153bcb3f9`.
The current joint pose and whether the leg-9 write occurred are **not**
established by the eight completed leg records. Do not treat leg 8 as the
current physical pose or continue the remaining route. The owner is consumed
for this boot.

Next: improve fault records to retain the latest raw pose, phase and write
attempt count (including after a deadline), then independently acquire a
fresh post-fault pose on a reviewed read-only path before any new movement.
Determine whether leg 9 timed out because of settling, positional error,
feedback cadence, or delivery. Do not loosen the 10-second deadline or
endpoint tolerance without that evidence. Any next trial must be a newly
reviewed finite route starting from a fresh measured pose, not a replay of
the first eight legs from assumed P4.

### r75 leg-nine post-fault investigation — 2026-09-24

The requested read-only investigation is complete. One controlled USB reset
started the unchanged r75 application; no firmware, settings, torque, hold or
movement command was sent. Restart evidence is
`wizard-20260924T221605299970Z-fe3cca4604a042af81c3a4b1fc1ebffa`.
The new boot `4d696fa864f6e4defa4893a3db98ac7f` passed an IDLE startup
check (export `wizard-20260924T221631344722Z-83c29b7010f44953a9db237ef133abce`).
One read-only three-snapshot capture reported all seven positions unchanged,
torque on, and no control changes (assessment export
`wizard-20260924T221646916450Z-89afb8ef3c6041cdafa23e899c271bf3`).

The captured goals exactly match leg nine:
`[1941,2080,2034,2591,2236,2040,2047]`. Positions were
`[1949,2082,2033,2600,2235,2041,2047]`. Thus all seven joints were within
the existing 12-count endpoint window, and the base changed 52 counts in the
requested direction relative to leg eight. This establishes that the leg-nine
goal write took effect and that the *later post-reset* position was near the
requested goal. It does not reconstruct the precise state at the 10-second
deadline.

An immutable offline comparison of leg-eight evidence with the post-fault
capture is exported at
`wizard-20260924T222145207821Z-f0f832f8647347bc9415e09a1eee255b`.
The old endpoint rule rejects servos 12 and 13 because each received a
four-count goal correction but showed zero travel. Crucially, they began only
two and one counts from their *new* targets. The old rule conflates command
size with required physical travel. This is the leading explanation for the
timeout; a transient feedback/timing issue cannot yet be excluded.

A proposed r76 joint rule has been implemented separately from the deployed
r75 verifier, with Python and native C++ tests. It preserves the 12-count
endpoint bound and directional/travel bounds. It waives the two-count minimum
travel only when both the initial and final measured positions are within
three counts of that joint's new target. The test suite also rejects a
non-moving joint that starts farther away, wrong-direction movement, large
unrealized moves and excessive travel. This is an *offline proposal*, not a
deployed change or retroactive verification of leg nine.

The pose-capture owner has consumed the current boot, and no movement is
authorized on it. The next live candidate must be a new finite continuation
starting from a **freshly reacquired** leg-nine-class pose, not P4 or leg
eight. It must pin the eight original remaining targets (legs 10–17), require
exact leg-nine goals and tight fresh-position matching before its first write,
independently verify each leg under the new rule, and export each record before
the next. The first release should stop after only the B-hover transition;
later virtual downstroke/retract and A return are admitted only if that
endpoint and clearance remain acceptable. The candidate needs renewed
native/host fault tests, sampled model sweep, app-only build review and
read-only startup checks. No stylus, camera or physical key is involved.

The eight remaining target rows (original legs 10–17) have now passed a
separate offline **count-interpolation** sweep from the captured leg-nine
positions. At 101 modeled samples per transition, the smallest provisional
TCP world-Z was `73.46 mm` and the smallest nonadjacent link-axis separation
was `55.75 mm`. Export:
`wizard-20260924T222354001496Z-61801fa3c16244049c43e482bf3dadf6`.
These are unregistered model coordinates and cannot establish real clearance.
The focused r76 endpoint/preview and r75 regression suite passed `145` tests;
the standalone native C++ r76 rule test also passed. The r76 owner, authenticated
continuation route, host export contract, reviewed image and physical trial
remain to be built. The current boot was only read for pose; no continuation
movement was sent.

### r76 one-move B-hover release — 2026-09-24

The reviewed r76 app-only candidate retained the r75 source and replaced the
17-leg route with a single fixed `AIRB1` B-hover. Its application SHA-256 was
`874c89ca5af7bbb5e492cb5b3cf95ea47116c19fc65190151c638e47aeac0987`
(1,202,960 bytes). Stage, compile, and binary-review exports are respectively
`wizard-20260924T224024890431Z-a2ca8ee3c88e47a2b6a29c3e0a536fd5`,
`wizard-20260924T224457688000Z-eeab1c5d887b4c6f8f94386202cfd727`, and
`wizard-20260924T224547887579Z-0aadc7abbb7c44d9a366db3945b7dc58`.
The combined r75/r76/transport regression passed 185 tests before installation.

The app-only installation verified the exact predecessor, controller identity,
full flash readback and unchanged protected regions. One startup produced boot
`c788314e681f90d7021042d1bcef8f76`; its read-only startup export is
`wizard-20260924T225236297976Z-5f22f348ad9446a8b85f84339ecb6927`.
No servo target was sent during installation or startup.

One signed fixed B-hover request then passed the native fresh-source gate and
completed with one synchronized target write and a verified export:
`wizard-20260924T225254423367Z-ad13c5528ce84c49a196d58651ccc6be`.
Final goals were `[1941,2098,2016,2609,2201,2040,2047]`; final positions
were `[1949,2099,2015,2610,2203,2041,2047]`. Selected shoulder-pair,
elbow and wrist-pitch goal errors were `+1,-1,+1,+2` counts. Base and other
passive feedback were unchanged. The r76 owner and host claim are consumed;
no retry or next leg was attempted. This is joint feedback evidence only, not
measured physical stylus/key accuracy.

Next, use this measured seven-joint endpoint as the exact source for a new
finite seven-leg route (original legs 11–17): B virtual downstroke/retract,
two lateral increments toward A, A hover/downstroke/retract. Do not reset the
source to the original P4 or leg-nine values. Check the swept proxy and
source gate, preserve the r76 exception only for joints already within three
counts of their new target, independently export every leg before advancing,
and stop on any mismatch. No physical contact is intended.

### r77 physical finale and source-gate stop — 2026-09-24

The fixed seven-leg r77 candidate passed 248 combined r75/r76/r77/transport
tests, offline review, and an app-only install with full readback and unchanged
protected regions. App SHA-256:
`7a2059d76243b37e9b443c822093ef597611f136f5497a055f01278c3bcda496`.
The r77 startup was IDLE on boot `e91da6050722ca7c4d09615eeeb4d0c1`;
startup export: `wizard-20260924T230951658407Z-3d00a9510017405fb75990b0750f057c`.

The one-use physical campaign completed and durably exported three legs:

| Leg | Virtual action | Final feedback (base, shoulder pair, elbow, wrist pitch) | Export |
| --- | --- | --- | --- |
| 1 | B downstroke | `1949,2112,2002,2622,2179` | `wizard-20260924T231007953994Z-f7add203b3ab484fb3d4a278efab903e` |
| 2 | B retract | `1949,2087,2028,2600,2235` | `wizard-20260924T231010203228Z-1541dd002726476b9f78f56c6c0b52d1` |
| 3 | first lateral move toward A | `1985,2082,2031,2600,2235` | `wizard-20260924T231012251808Z-1613945c126b4a16bd1950ddf6b51bcc` |

All seven-joint records independently met the r77 endpoint rule, and all three
exports plus the fault export passed integrity verification. Before leg four's
write, the controller reported `SOURCE_POSE_REJECTED|4`; no fourth target was
sent. Fault export: `wizard-20260924T231012845117Z-4906f73579e64de797ecbd3ad2ac9f29`.
The host's error text originally discarded the exact controller reason; a
subsequent authenticated **read-only** status request recovered it at sequence
41. The host now retains `last_controller_status` in future fault exports,
covered by a regression test. No retry or further movement occurred.

The likely issue is the inter-leg source gate's one-count tolerance from the
previous endpoint. A loaded servo can settle by more than one count after an
endpoint snapshot; the current fault record does not retain the three rejected
source samples, so this is a hypothesis, **not yet a measured diagnosis**.
Do not simply widen that gate or replay leg four. The next candidate should
first export the *fresh* source triple and explicit failed comparison without
writing a target; then choose a justified bounded settling window and test it
against stale/wrong-goal/moving/large-drift cases. Continue only from the
newly measured leg-three-class pose with a finite remaining-leg campaign.
The controller's joint readback does not establish physical tip accuracy or
clearance; no stylus, camera, or real key contact was involved.

### r77 post-fault read-only pose and continuation criterion — 2026-09-24

The signed post-fault status `SOURCE_POSE_REJECTED|4` was durably exported at
`wizard-20260924T232506596686Z-78cd7bcbfd4c4ca6b645d0ef79917ebc`.
One USB reset started the **unchanged** r77 app, with no flash, settings, hold
or movement command. Restart intent/result:
`wizard-20260924T232633726070Z-9800366ef395408283c5c5003ae16841`.
The new boot `fd934f2b31b13316ee4392b1bfedbf45` passed read-only IDLE
startup checks (`wizard-20260924T232657644374Z-8b42df9c7547438889338bf5a07e5461`).
Its one-use pose capture reported `STABLE_SAMPLED_POSE`, unchanged goals and
controls, torque on, and zero span across three samples. Pose assessment:
`wizard-20260924T232712748224Z-e462f96c2c1b4561895acf10ba434231`.
This boot is now reserved by pose observation, so it must not run a movement
campaign.

An independent offline comparison is exported at
`wizard-20260924T232837264746Z-8fdde03f975e4b17aca685ab9d0bf882`.
The base moved from leg-three's exported endpoint 1985 to post-reset 1987
counts; every other joint's position and all seven goals matched. Thus this
later stable pose **fails** the r77 one-count source comparison but **passes**
a proposed three-count comparison plus a 12-count distance-to-goal cap. This
strongly supports settling drift as the cause; because the actual failed
triple was not retained and the comparison crossed a reset, it is not proof
of the exact failure-time values.

Next continuation should use a new reviewed, finite **four-leg** candidate
anchored to the measured pose above, not replay r77 from B. It should:

1. Keep exact seven-joint goal matching and fresh, stable three-sample reads.
2. Accept no more than three counts of difference from the previous verified
   endpoint **and** no more than 12 counts of error from each joint's goal;
   fail on motion flags, changed torque/control, stale reads, or inconsistent
   position bytes.
3. Retain the fresh source triple and individual comparison outcome on a
   failed start, before any write, so a future rejection is diagnosable.
4. Pin only original finale legs 4–7 (A travel, hover, virtual downstroke,
   retract), export each endpoint before admitting the next, and stop on any
   uncertain delivery or failed verification. Do not infer tip or key accuracy.
5. Test ±1/±2/±3 acceptance and ±4, wrong-goal, >12-to-goal, moving, stale,
   and passive-joint drift rejection in native and host simulations before an
   app-only review and bounded physical release.

The post-reset comparison is diagnostic evidence only; it does not itself
authorize movement. The next candidate will need a fresh startup and source
check because this boot has consumed its pose-observation owner.

At this planning checkpoint, the candidate joint-local three-count/12-to-goal
comparison was encoded in both Python and C++ as
`air_typing_r78_source_rule`; 10 focused tests, including a native C++
execution, passed. It had not yet been installed and did not replace the r77
image or full fresh/stable/torque checks. The outcome is recorded below.

### r78 four-leg A-side physical continuation — 2026-09-24

The formerly pending r78 continuation is complete. The immutable app-only
candidate (`3b9989e03cd64690e831049c4e19ff38d6c10ab6e2c6c22f3ad1d7e61e1f3aaa`,
1,204,848 bytes) passed a 101-point-per-leg proxy sweep, 80 focused native,
host, and transport tests, and pinned offline review
`wizard-20260924T234109427898Z-cee1f774526e4a7f95a8bfa8000af08c`.
The app-only write was readback-verified with protected regions unchanged.
Startup export `wizard-20260924T234840372928Z-c92efcc6e9c949a49654e2e4b3eb6d0e`
reported IDLE, no storage fault, boot `a3b09306a9791e2d95807a55f6dfc214`.

One signed, one-use physical campaign then completed the four remaining
noncontact legs. Each leg has an independently verified seven-joint controller
record and an integrity-verified export before the next leg was admitted.
The table reports the first five joint positions (base, shoulder pair, elbow,
wrist pitch), not measured tip coordinates.

| Leg | Virtual action | Final position counts | Export |
| --- | --- | --- | --- |
| 1 | Return travel to A | `2041,2082,2031,2601,2235` | `wizard-20260924T234854794776Z-12d69d99f9e9461286f1467b8922b6be` |
| 2 | A hover | `2041,2094,2020,2619,2199` | `wizard-20260924T234856604621Z-6b2c8c4752e245c6b8403aa1e29e947b` |
| 3 | A virtual downstroke | `2041,2106,2008,2631,2175` | `wizard-20260924T234858074423Z-e609cecbe5104fe2bcecaa83720e4713` |
| 4 | A retract | `2041,2081,2033,2609,2233` | `wizard-20260924T234900259937Z-5d6c8c652fe24e2abb137b9046dc7811` |

The r77 three verified legs plus these r78 four legs now cover a complete
B downstroke/retract, lateral B-to-A travel, A hover/downstroke/retract
sequence, across two boots. The previously rejected source gate was avoided
with a reviewed three-count settling window and a 12-count goal-error cap;
the rejected r77 source triple remains unavailable, so the precise original
fault mechanism is still not proven. On the final A retract, the elbow
feedback was nine counts from its commanded goal; this passed the existing
joint endpoint rule but should not be described as nine-count TCP accuracy.

No real keyboard, stylus, camera, or contact was used. Controller readback
confirms command-correlated servo motion, not physical tip placement, surface
clearance, or key actuation. Next work should favor repeated finite noncontact
cycles and measured pose-to-pose consistency on fresh one-use boots, then
physical registration and tip/contact calibration once tooling is mounted.
Do not replay the consumed r78 boot or treat its completion as authority for
unbounded motion.

### Seven-leg raw-record review and next repeatability experiment — 2026-09-24

`air_typing_cycle_review.py` re-reads all three r77 and four r78 retained
raw controller records, independently re-runs their original leg verifiers,
matches the archived assessments, and exports a seven-leg review. The review
is at `wizard-20260925T003533019701Z-9614bbd272424cac8555242bb654b17b`;
98 focused campaign/review tests pass. It opened no device and sent no
command.

The A return-travel and A retract legs commanded the **same seven-joint
target** within the r78 boot. Their final feedback differed by
`[0, -1, +2, +8, -2, 0, 0]` counts (servo IDs 11–17). The eight-count
maximum was on the elbow (ID 14). This is a useful within-cycle comparison,
but just two arrivals, from different approach directions, cannot establish
a repeatability distribution or justify a compensating offset. All seven
legs were controller-verified; none measured TCP/key accuracy.

The next *physical* experiment should be a fresh-start, finite noncontact
A-target repeat campaign, sourced from the r78 final goal/feedback rather
than from an old nominal pose. Include several A hover → virtual downstroke
→ retract cycles and at least one same-target arrival from each approach
direction. Record fresh seven-joint feedback, command/time lineage, and one
durable export per leg; stop on a source, delivery, endpoint, or export fault.
Review median, spread, and direction-conditioned offsets on held-out cycles.
Do not apply an elbow compensation merely because the two current arrivals
differ by eight counts. Before any new motion, review the proposed swept
path and source window against the r78 final measured pose. A bounded
parameterized campaign would reduce app rebuilds, but must retain strict
target limits, one-use admission, and export-gated progression; this is a
design improvement, not permission to send arbitrary trajectories.

### r79 two-cycle A repeatability run — 2026-09-24

The fixed six-leg `AIR6` candidate repeated A hover → virtual downstroke →
retract twice, starting from the r78 final feedback, with no stylus or
contact. The reviewed app-only image was
`f82f1f87e6e9917dfdf2e9c60c30aaedf18025bdbd3b9777600b46a1458f7e82`
(1,204,896 bytes). The app readback matched and protected regions were
unchanged. Its IDLE startup was exported at
`wizard-20260925T005141484781Z-d565d3dec9f747248b5d961913368467`
on boot `2f1d91bf952cd1304e5953ed63b8d947`. The unregistered URDF sweep
reported minimum modeled TCP Z 73.56 mm and minimum link-axis separation
55.75 mm (`wizard-20260925T003809476577Z-68c0aaffc48140e7ac466642e87cb77b`);
these are not measured physical clearances. Before deployment, 128 focused
native/host/transport tests passed.

All six physical legs completed, with a fresh seven-joint endpoint record
and durable export before the next leg. Independent raw-record review:
`wizard-20260925T005305256389Z-e69ad3ea85154c909b2b031685c7f0d1`.
The two arrivals at each identical target differed by at most **one servo
count**; the two retract arrivals matched exactly. The six leg exports, in
order, are:

1. `wizard-20260925T005159100448Z-12fe39d6cb8745bcb761578ef8f7e6c9` — hover 1.
2. `wizard-20260925T005200560072Z-50f86394b0d644c1a8008f9816808f72` — virtual downstroke 1.
3. `wizard-20260925T005202801676Z-47cff071716441b78315a24b17983c22` — retract 1.
4. `wizard-20260925T005204430544Z-b7b0a64dd53d46f1ac5dabf6a0b838e6` — hover 2.
5. `wizard-20260925T005205863579Z-d7822fd515084f419fa541dd794efd0e` — virtual downstroke 2.
6. `wizard-20260925T005208116238Z-9058a361c92f4d81ba686b724286c712` — retract 2.

This is encouraging *servo-feedback repeatability* at the tested A poses,
not accuracy in space. In both retracts the elbow feedback was +9 counts
from its commanded goal, an apparently consistent directional residual.
The prior r78 retract also read +9, while r78 A travel to the same goal
approached from a different direction and read +1. This supports a
direction-conditioned effect rather than a universal elbow offset, but the
sample is small and the physical tip is unmeasured. Do not apply a global
compensation. The next experiment should vary approach direction to the
same A target on a fresh, bounded campaign and hold out some arrivals for
prediction validation. Alternatively, once the tool and camera are mounted,
register physical TCP/board positions and assess whether these count-level
differences materially affect key targeting. The r79 boot is consumed;
there is no follow-on movement authority from this run.

### r81 isolated-elbow approach-direction comparison — 2026-09-24

The first r80 multi-joint approach draft was **not deployed**: its native
endpoint fault sweep failed because tiny commanded changes on several joints
could not be distinguished reliably from their existing goal error. We
replaced it with an isolated-elbow experiment. The fixed eight-leg sequence
was `2570 → 2600 → 2630 → 2600`, repeated twice, while every other joint
goal remained at the r79 final A goal. Each elbow step was 30 counts. The
unregistered, meshless model preview passed (minimum modeled TCP Z 77.26 mm,
minimum link-axis separation 55.75 mm); that is a screen, not proof of
physical clearance or stylus location.

The reviewed r81 app-only image is
`2580a872ce612c331cb02dce15be9b34f75f1e19ac4bc6043072e438e8b948d1`
(1,204,944 bytes). Its write/readback matched, protected regions were
unchanged, and its startup was IDLE on boot
`551645e4800ee3afda519357227cd8b1` (startup export
`wizard-20260925T011650348265Z-93b570315a944257bbe19419d8315926`).
All eight noncontact legs completed and each was verified and exported before
the next was admitted. Independent raw-record re-evaluation is at
`wizard-20260925T011824456855Z-8806a761fb68408d8fdb044ba64a17a3`.

At the identical A elbow goal of 2600, both arrivals from below were 2602
(+2 counts), while both arrivals from above were 2609 (+9 counts). A model
using the first cycle predicted the held-out second cycle exactly (0-count
error for both approach directions). The 7-count direction difference is
therefore repeatable *in servo feedback at this pose* and explains why a
single global elbow offset is inappropriate. The low endpoint read 2580 at
a 2570 goal in both cycles; the high endpoint read 2632 and 2631 at a 2630
goal. The raw evidence is controller feedback, not measured end-effector
position or physical key accuracy. The r81 boot is consumed; do not replay it.

Next, encode approach direction as part of the endpoint model and test a
different held-out A-like pose or another joint. Only after a mounted tool and
registered workspace should we translate this count-level behavior into
physical key-target compensation. Do not blindly offset a target by seven
counts: the sign and final TCP effect remain unmeasured.

### r82 nearby held-out target — 2026-09-24

The next fixed eight-leg noncontact campaign shifted the compared elbow goal
from 2600 to 2610 counts. The sequence was `2580 → 2610 → 2640 → 2610`,
twice, with all other joint goals unchanged. It was screened offline with
minimum modeled TCP Z 75.30 mm and link-axis separation 55.75 mm. The r82
app-only image
`0be3db4edf21396c881ee9eeee62f625bc99ebaf33bf96b35656c5dffd3a937c`
was installed with matching readback and unchanged protected regions. Startup
was IDLE on boot `76b0b408fc1eada6d6e09cacda3bce05` (export
`wizard-20260925T013503495658Z-75c2d0a1a596435fbfe92aaac64dbeea`).
All eight legs completed with per-leg endpoint verification and durable
export. The independent raw-record cross-pose review is
`wizard-20260925T013627628446Z-e49fe8af2ba34277853de292999a5ff5`.

At the new 2610 goal, arrivals from below were 2610 and 2611; arrivals
from above were 2619 and 2619. The simple direction-conditioned offsets
learned at the earlier 2600 goal (+2 from below, +9 from above) predicted
2612 and 2619. On the four held-out arrivals its errors were −2, 0, −1,
and 0 counts: mean absolute error **0.75 counts**, versus **4.75 counts**
for predicting the unadjusted goal. This is encouraging local servo-feedback
prediction across one adjacent goal, not validated global compensation or
physical TCP precision. The r82 boot is consumed; there is no follow-on
movement authority.

The next efficiency improvement should be a *single pre-reviewed batch*
covering more distinct goals, approach directions and a modest speed change,
with per-leg export and a true held-out subset. Once stylus mount and workspace
registration are available, measure physical tip coordinates and key-center
error directly. Until then, never equate these count-level predictions with
millimeter or key-press accuracy.

### r83 two-goal elbow grid — 2026-09-24

We ran one fixed-speed, 16-leg noncontact campaign with elbow goals
`2560 → 2590 → 2620 → 2590 → 2650 → 2620 → 2590 → 2620`, repeated twice.
All other joint goals remained fixed. This deliberately tested the two
intermediate goals (2590 and 2620) from both approach directions and repeated
each comparison without changing firmware mid-run. The offline meshless
screen reported minimum modeled TCP Z 73.40 mm and link-axis separation
55.75 mm; these are not physical-clearance measurements.

The reviewed r83 app-only image is
`5baaa670dd27e1e1f621fa5357f67eba765101b182be4513908e30192d4a00d6`
(1,205,024 bytes). Write/readback matched, protected regions were unchanged,
and startup was IDLE on boot `8cc5527a4db7993c0f90d8ec319ebc6d` (export
`wizard-20260925T015223250169Z-b946093779bd443e99958df7bd3e25dd`).
All 16 legs completed with fresh selected-joint feedback and durable export
before each successor. Independent raw-record review is exported at
`wizard-20260925T015434799104Z-6fe33e2f7f5e4d8786dbcd8e209a0073`.

Using only the +2-count from-below and +9-count from-above offsets learned
at the prior 2600-count goal, the eight held-out comparison arrivals were
predicted with **0.375 count mean absolute error**, compared with **5.625
counts** when predicting the command goal exactly. The observed arrivals
were 2592 and 2599 at goal 2590, and 2621/2622 from below and 2629/2631
from above at goal 2620. Repeats varied by 0–2 counts. The 16-leg r83 boot
is consumed; do not replay it.

This supports a local direction-conditioned model of *reported elbow servo
position* in this narrow region at one speed and load. It does not prove
physical tip accuracy, general compensation, safe contact, or keyboard
typing. The next test should remain noncontact: pre-review a bounded
multi-joint path between distinct hover poses, verify every waypoint and
durable export, and hold out a repeated cycle. Build that from fresh source
feedback and the currently observed board-free clearance; do not extrapolate
the elbow offsets to other joints or to the stylus tip. A later speed
comparison should be isolated from the pose/direction experiment.

### r84 first multi-joint lateral hover cycle — 2026-09-24

The next campaign used the exact r83 final source and a five-leg fixed path:
return elbow to A, move five joints together to a lateral noncontact hover,
return to A, then repeat that lateral/A pair. Its lateral goal was
`[1994,2093,2021,2618,2197,2040,2047]`; A was
`[2047,2075,2039,2600,2233,2040,2047]`. Every changed joint had at least
a 10-count goal change, avoiding the earlier ambiguity of asking the
endpoint verifier to prove movement from a 1–2-count command. The maximum
per-joint step was 53 counts. The offline meshless sweep passed with minimum
modeled TCP Z 77.02 mm and link-axis separation 55.75 mm, but that is not a
physical clearance certificate. Preview export:
`wizard-20260925T015708190225Z-bd58d70ff1634aee926f10143ca8cc90`.

The reviewed r84 app-only image
`d1e141a9b73d0b104ffb2ac1b07cae213c1321300a2251bd8cd3dcf0596f97cd`
matched write/readback, preserved protected regions, and started IDLE on
boot `e76048f2ab49a67cc473b55b6b2b1149` (startup export
`wizard-20260925T021042000421Z-fd8162e1fe0542c0a308516e52ee71f3`).
All five physical legs completed; each selected joint was checked using
fresh controller feedback, and each leg was durably exported before the
next. The independent raw-record review is
`wizard-20260925T021200873450Z-6ef10880b2eb49af96c397a866909582`.

The two lateral arrivals had **identical reported positions across all
seven joints**. The two A returns differed by at most **one servo count**
(base −1, shoulder +1 on the second return). This is a strong repeatability
result for these two controller-reported poses under the tested speed/load,
not a measured physical tool-tip result. The base and shoulder still showed
goal residuals, so do not infer millimeter accuracy from identical counts.
The r84 boot is consumed; do not replay it.

Next: design a finite noncontact *ghost-key* sequence that traverses more
than two hover targets and includes a small virtual downstroke/retract at
each, using this verified A/lateral path as a seed. Hold out a repeat and
report per-joint endpoint residuals by target and approach direction.
Do not add physical contact or keyboard coordinates until the tool mount,
camera mount, and board registration are measured. Separately, replace the
revision-by-revision firmware recipe mechanism with a reviewed bounded
runtime recipe format so subsequent experiments do not require a new app
flash for each fixed path; preserve the same one-use, fresh-feedback and
export-before-next semantics.

### Next ghost-key sequence prepared offline — 2026-09-24

The source-bound A/B/A/B ghost-key proposal uses two repeated eight-leg
cycles: A hover → virtual downstroke → retract hover → clear, then the same
four phases at B. The proposed targets are drawn from the tested A and
lateral-hover region, with each changed joint stepping 10–60 counts. Its
16-leg interpolated meshless sweep passed (minimum modeled TCP Z **73.56
mm**, link-axis separation **55.75 mm**) and was exported at
`wizard-20260925T021445026561Z-b90703eb95f64348be910cffedb1a70d`.
This is **not executable** in the installed r84 firmware and does not
establish physical clearance or typing.

To avoid flashing a new application for every fixed test, the first offline
`reviewed_hover_manifest.py` contract permits only the six A/B named poses,
their allowed edges, 16 or fewer legs, speed 20/acceleration 1, and
export-gated one-use progression. It rejects arbitrary targets and policy
changes. The controller does not yet implement that contract; see
`REVIEWED_HOVER_RUNTIME_PROTOCOL_PLAN.md` for the native owner, transport,
simulation, release, and staged physical-validation work still required.
