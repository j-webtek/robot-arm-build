# Standard start and measured park progression

## Current checkpoint — REFERENCE_A, not park

The r54 app-only installation and one-use fixed pair re-anchor completed on
2026-09-21. The user confirmed the gripper was clear of the board before the
command. The native operation attempted exactly one synchronized target write,
then retained three fresh endpoint scans; the authenticated host verified and
durably exported the full 1,127-byte record before acknowledging it. Export:
`wizard-20260921T222923014318Z-d559019a180d41eaa9c43c62c39e6c48`.
The independent assessment says `GOAL_AND_ENDPOINT_VERIFIED`, with shoulder
encoder displacement `[0,-1]` counts. It does **not** prove a visible lift,
tool-tip coordinates, collision clearance, or physical park.

The reproducible seven-servo encoder checkpoint `REFERENCE_A` is exported at
`wizard-20260921T223040009414Z-19964cdec96940a3a6e08e9715fd7856`:

| Servo ID | Goal | Measured position | Torque |
| --- | ---: | ---: | ---: |
| 11 | 2047 | 2047 | 1 |
| 12 | 2389 | 2390 | 1 |
| 13 | 1725 | 1724 | 1 |
| 14 | 2907 | 2904 | 1 |
| 15 | 1589 | 1591 | 1 |
| 16 | 2040 | 2041 | 1 |
| 17 | 2047 | 2047 | 1 |

These are controller counts, not an immutable command to replay. Each later
session must capture its own fresh seven-servo baseline and reject drift.
The prior simulation park at board XY `(290,40)` has no measured joint mapping
and cannot be used as a live target.

## Why a second, higher pose is necessary

`REFERENCE_A` makes a repeatable **starting checkpoint** for developing a
park, but it is near the board. We want a separate `PARK_B` with the gripper
visibly and repeatably clear above the board, cables slack, and a measured
seven-joint endpoint. Without the static camera mount and stylus, this can be
qualified only as a joint/visual noncontact park, not a millimetre-accurate
keyboard or phone frame.

## First bounded rise experiment

The earlier r27 shoulder-rise trial used a synchronized `servo12 −12,
servo13 +12` target from another posture and measured correctly directed but
incomplete travel (`−7,+8` positions). This establishes a **candidate sign**
for lifting; it does not establish collision safety or the current posture's
tip displacement. Do not extrapolate its nominal 2.86 mm estimate as fact.

1. Build one reusable park-step interface, rather than a new firmware build
   per waypoint. It must reserve the bus, read all seven servos, verify this
   known reference and all joints torque-on/stable, and accept only a bounded
   paired shoulder step in the previously observed lift direction. No free-form
   JSON servo target, generic home, torque-off, or automatic return.
2. Before the first step, capture a new boot's fresh baseline. Require goals
   `[2389,1725]` and positions near `[2390,1724]`, with no changing neighbors.
   Propose only the first paired target `[2377,1737]` (speed 20,
   acceleration 1); recheck immediately before the sole write.
3. Retain requested targets, transmission attempt, raw register readbacks,
   three or more endpoint scans, torque/moving fields and all neighbors. Stop
   on stale feedback, goal disagreement, excessive travel, uncertain delivery,
   unexpected neighbor drift, contact, or export failure. Never automatically
   issue step two from a failed or unobserved endpoint.
4. Ask the operator only for the physical fact telemetry cannot supply yet:
   did the gripper rise farther from the board, remain effectively unchanged,
   or approach contact? Record that alongside the encoder evidence. An
   unchanged or opposite observation stops lift-direction assumptions.
5. If both encoder and physical direction are consistent, derive the next
   small target from the **new measured** joint position and goal, not from a
   frozen earlier count. Permit the next step only after the prior export is
   replayed and receipt-bound. Cap the finite ladder and total excursion;
   require a fresh admission for any later run. This avoids reflashing for
   each waypoint while preserving per-step fault stops.

## Park acceptance and next use

Select `PARK_B` only after the user confirms a visibly clear, cable-safe pose
and the system stores stable joint goals/positions with a reproducible return
trial. Label the first outbound lift as exploratory, not park achieved. Then
test a bounded return `PARK_B → REFERENCE_A → PARK_B` with fresh endpoint
readback, export each leg, and compare repeatability over several cycles.
Only afterward should ghost-keyboard moves start from `PARK_B`. Camera/board
registration, stylus tip offset, key depression and phone contact remain
separate commissioning steps.

## Current stop line

The r54 re-anchor boot is consumed. No `PARK_B` target or park-step route is
installed yet. Do not invoke the r54 ghost transition campaign as a shortcut:
its twelve-leg fixed sequence is a different experiment and may move toward
the board after its first leg.

The first offline boundary exists in `park_step_plan.py` and
`plan_first_park_step.py`. It rejects a missing/drifted seven-servo reference,
disabled or changing controls, and simulated pose sources. Given a new
read-only pose export, it can durably export the exact proposed first target
with `movement_authorized: false`. The current re-anchor endpoint is the
reference, **not** a fresh post-restart observation.

### r55 offline application candidate

The native one-step policy, one-use owner, authenticated route, host record
decoder and durable export/receipt coordinator are implemented and tested
offline. The signed route accepts only bounded paired shoulder targets:
servo 12 decreases and servo 13 increases by exactly 12 counts per step,
within 48 counts total from `REFERENCE_A`. A step requires fresh stable
seven-servo readings and an immediate prewrite check. The board service
independently limits the IDs, direction, target envelope, speed 20 and
acceleration 1. Each boot allows only one write attempt. The first host
contract is deliberately fixed to `[2377,1737]`; later steps require their
own evidence-bound host plan, not an ad hoc request.

The r55 source was staged from pinned r54 at
`wizard-20260921T224503324003Z-81930b78d64e474c8e84d113b3d964f4`.
The app-only offline compile passed at
`wizard-20260921T224655422019Z-a0d634b9151d406aa3dd750cfa179dc7`.
The reviewed app is 1,175,216 bytes (135,504 bytes of app-slot headroom),
SHA-256 `1ea884af0cd717775c67046302ab5e9df82b9514b552b96fc8d27d5ad853d9a5`.
The source/artifact review is
`wizard-20260921T224805390919Z-0a91a71fa008405298c821df110663af`.
Its board composition enables the park route and disables the older r54
re-anchor route. The focused policy, owner, route, host, transport and
composition regression set passed 56 tests. These are **offline** results;
runtime heap, installed bytes, fresh pose and physical direction remain
unverified. No r55 firmware has been installed, no new startup occurred,
and no rise command has been sent.

The pinned r55 image is now integrated into the app-only installer, startup
review, pose-observation and one-step host launch paths. The local installer
preflight passed with r54 predecessor SHA-256 `c418af30…1f818fe` and expected
preserved filesystem SHA-256 `45320bab…08e7267`; it performed no device I/O.
The launch CLI requires a new r55 startup receipt, a same-boot read-only
seven-servo pose export matching `REFERENCE_A`, and a durable one-use claim
before its sole authenticated movement request. The route itself rechecks the
current seven-servo pose immediately before writing, retains raw feedback,
and refuses a second request on the same boot. The host exports, replays,
then acknowledges only the exact retained record digest.

### r55 installed and read-only checked (2026-09-21)

The user approved one app-only installation/startup and read-only checks,
**not** a park movement. The installer verified the controller MAC, exact r54
predecessor, partition table and protected filesystem before writing. The
full r55 app readback matched SHA-256 `1ea884af…53d9a5`; protected regions
were unchanged. One startup reset was sent. The installation journal is
`private-backups/controller-20260918-session1/app-r55-deployment-events.jsonl`.

Read-only startup export
`wizard-20260921T230249359050Z-8586865905ae4b53a00b2f8274c2e373`
reports idle boot `69c6050d2234a9ba244014797621f6dd`, no storage fault,
140,668 bytes free internal heap and a 73,716-byte largest block. Stack
headroom is not measured. The signed park-step status route returned `NEW|0`;
export `wizard-20260921T230313784880Z-300b4316c2e74d4289d70ab17e08dcc9`.

The seven-servo pose capture is
`wizard-20260921T230323146799Z-a350e92ba91145569438ec4d9261f602`.
It was stable over three snapshots: goals
`[2047,2389,1725,2907,1589,2040,2047]`, measured positions
`[2047,2390,1724,2904,1591,2041,2047]`, all torques enabled and all
position spans zero. The local first-step preflight passed for target
`[2377,1737]` on that boot without hardware I/O. **No rise command has been
sent and no `PARK_B` has been designated.**

The operator's physical direction observation and a durable movement record
remain required before planning a second step or designating `PARK_B`.

### First r55 live request: rejected before motion

The user approved one bounded first-rise attempt. The host one-use claim was
written for boot `69c6050d2234a9ba244014797621f6dd`, but its signed start
request failed response-sequence verification. A separately authenticated,
**read-only** reconciliation at
`wizard-20260921T230827444781Z-8ad4df27c01c4966adf216f3ad8f266d`
returned `NEW|0`: the park-step owner had not started and had attempted zero
writes. No motion result or endpoint assessment exists. The host claim remains
consumed; no resend or return was attempted. The incident and exact evidence
links are exported at
`wizard-20260921T230946213592Z-50f6f67c707747f5ac080b9b1f0e607d`.

Cause: the earlier authenticated `NEW|0` status probe consumed sequence 0 in
the controller's boot-scoped auth gate. The movement launcher constructed a
new sequence-zero client, so the gate rejected it before invoking the owner.
The status probe now records its gate use before network I/O, and the motion
preflight refuses such a boot before reserving a movement attempt.

### Second r55 live request: bus reservation conflict, zero writes

With the user's approval, one USB-only startup produced idle boot
`20db2beff494f5d17b7ae7916c52b1ac`. Its startup export is
`wizard-20260921T232040158693Z-3b3ffcdbd26049c6b9adebfdd38e7523`.
A three-snapshot pose capture was stable at `REFERENCE_A` and exported at
`wizard-20260921T232049560592Z-aeaa384fb7754238bb3c3c18c490c15a`.
The local target preflight passed for `[2377,1737]`. The one-use claim was
written, and the signed start request was accepted by the authentication gate,
but the host produced no movement export. Read-only signed reconciliation
reported `RESERVATION_FAILED|0` at
`wizard-20260921T232336559648Z-f6a665d9ef66480a8170cfe47b2c2214`.
The `|0` is the owner's write count: **no servo write occurred**. The claim
remains consumed; do not resend on this boot.

Root cause is an incompatible same-boot workflow, not a servo-position error.
The pose capture sets `rocellPoseReserved` and `rocellDiagnosticOwned` for the
remainder of its boot. The park-step service correctly refuses to reserve the
same bus afterward. Offline launch code now rejects a same-boot pose export
before claiming a movement attempt. It instead takes the previously verified
pose as a checkpoint on a *prior* boot, then requires a separate fresh idle
startup for the park-step attempt. The native park-step owner acquires three
fresh seven-servo samples, verifies the exact reference goals, positions,
torque and stillness, and checks a fourth prewrite sample immediately before
its one possible command. A changed pose fails without writing. The host
test now rejects a same-boot checkpoint; 14 focused tests pass.

For a future authorized attempt: start a new boot; verify idle startup and
controller identity using unsigned/read-only routes; do **not** run pose
capture or signed park status on that boot; preflight using the prior-boot
stable pose export above; then send at most one bounded first step. No return,
second step, physical park claim, or retry follows automatically. Confirm
physical rise separately from encoder movement.

### Third r55 live request: one write, endpoint gate failed

The user asked to proceed and fix the startup path. A new idle boot
`a921005e78fcd65941832cba6228ec4c` was established without a pose capture;
startup export `wizard-20260921T233327455924Z-af10c62cb63740c6a2667445bd37eb34`.
The host preflight used the prior-boot stable pose export and passed. One
authenticated target `[2377,1737]` was sent. The host stopped on a terminal
fault, and signed read-only reconciliation at
`wizard-20260921T233346991329Z-455fa25475b94000b72556d64fe82149`
returned `ENDPOINT_GATE_FAILED|1`. The suffix means **one servo write was
attempted**. It does not prove the endpoint or physical rise. No return,
retry, second step, or further servo command was sent. The one-use claim for
this boot remains consumed.

The present r55 fault path discards its three endpoint samples for export:
`copy_result` and the record route only accept the `AwaitExport` success state.
Consequently the immediate cause of the endpoint rejection cannot be proven
from retained joint values. The owner currently captures the first three
postwrite samples at approximately 100 ms spacing and requires those three to
already be stationary and on target; a slower-but-valid actuator response is
one plausible explanation, **not yet a finding**. Other possible causes
include a joint not moving, goal-readback mismatch, or a neighbor changing.

The host now exports the exact authenticated terminal status on any future
fault and never sends a receipt or retry in that branch. Before another
physical trial, the native route should retain and export the raw prewrite
and endpoint samples on fault, report which predicate failed, and allow a
bounded settling window that distinguishes in-progress motion from a final
miss. Review and simulate that change, then install it only as a new pinned
app-only candidate with settings preservation. Do not infer a successful park
or general endpoint accuracy from this request.

### Settled post-fault pose and uninstalled r56 candidate

One USB-only diagnostic restart, with no motion command, produced boot
`9bb203c423ec6077a5f5c59d130b526e`. Its stable three-snapshot pose
assessment is
`wizard-20260921T233849891293Z-bc2194f6401c458eac68fdab42bbf6d9`.
Servo 12 has goal 2377, measured position 2385; servo 13 has goal 1737,
measured position 1730. Compared with the prewrite reference positions
2390/1724, the observed changes are -5/+6 counts. The other five joints
retain their reference goals and positions within the prior small tolerance.
This confirms a paired directional response and persistent goal change,
but not exact arrival or physical direction. The later snapshot is after a
restart, so it cannot identify which early postwrite predicate failed.
It also means the arm is **not** at `REFERENCE_A`; a repeat first-step request
is not valid. This pose-capture boot owns the bus and must not be reused for
movement.

The offline r56 candidate retains r55's route and changes only
`park_step_policy.h` and `park_step_owner.h`. It samples through a bounded
settling window rather than deciding from the first three endpoint samples.
Each sample must still have the exact selected goals, remain within the
12-count directional envelope, and keep unrelated joints fixed. A fixed
eight-second timeout retains the last three samples as a read-only fault
record; no success receipt or retry is permitted on timeout. The host now
exports any available fault record without calling it a successful endpoint.
Other faults still expose terminal status only and need richer native fault
records before we can claim complete diagnostic coverage.
Native success, delayed-settling, timeout, wrong-goal and route fault-record
tests pass; 18 focused Python tests pass. The separate r56 app compiled
offline, 1,175,728 bytes, SHA-256
`09864d144d630b2655c78956b0ea8148b0525bcdef017caa843d74f1f4661e79`;
the reviewed candidate export is
`wizard-20260921T234210592410Z-e54a5c2690a746fd9b7459456cf6f6d0`.
The offline review preceded installation; its movement behavior has not been
physically tested.

Next, review a bounded way to return the now-offset shoulder pair to
`REFERENCE_A` using fresh readbacks, or adapt the owner to learn from the
current measured pose. Do not infer a return target from stale photos or
silently issue an inverse command. Any re-anchor movement requires explicit,
separately reviewed authorization.

### r56 installed; read-only post-install baseline

The user approved r56 app-only installation and startup, but no return
movement. The deployment preflight verified the exact reviewed r56 image,
installed r55 predecessor and protected filesystem. The single app write
read back as SHA-256
`09864d144d630b2655c78956b0ea8148b0525bcdef017caa843d74f1f4661e79`;
partition table and filesystem were unchanged. The retained installation
journal is `private-backups/controller-20260918-session1/app-r56-deployment-events.jsonl`.
No provisioning or servo command was performed by installation.

The one startup produced healthy idle boot
`03137a0ed96846b69056b502bdfd8e29`, exported at
`wizard-20260921T234957251395Z-836fb790b2234ccaa7d9eeceecd52c3f`.
One read-only three-snapshot capture on that boot is stable, export
`wizard-20260921T235010665264Z-0a91ec360d7c40b3b4c56f3af8300823`.
Its shoulder goals/positions remain `2377/2385` and `1737/1730`;
all seven torques are enabled and all measured spans are zero. Thus the
installation did not establish reference pose or improve the residual by
itself. The pose capture owns this boot's diagnostic bus; do not send a park
step on it. No r56 movement trial has occurred.

Before any new movement, design and review a bounded re-anchor from the
*measured current* shoulder state to an accepted starting state, accounting
for the existing 8/7-count residual and possible downward tool motion.
That route needs its own native fresh-prewrite checks, exact target envelope,
one-use claim, fault record, no automatic retry, and separate authorization.

### Return-from-offset design checkpoint (offline, no new arm command)

The r56 capture above is the only current measured basis: goals on servos
12/13 are `2377/1737`, but positions are `2385/1730`. An inverse *goal*
change to `2389/1725` is not a 12-count physical move from those positions;
its nominal measured-to-reference displacement is only about `+5/-6`
counts. That distinction matters because the remaining goal error is real:
neither a goal acknowledgement nor an encoder change proves that the tool has
cleared the board. The reference positions `2390/1724` are prior observations,
not guaranteed endpoints.

The inert planner in `src/rocell/application/park_reanchor_plan.py` now accepts
only a stable seven-servo capture matching this offset state (within one count
per position, exact goals and torque). It produces a one-write candidate for
servo IDs 12/13, with speed 20 and acceleration 1, no automatic retry or
follow-on step. Eight focused tests cover changed goal, position, torque,
motion, identity and source rejection. The planner accepted the actual r56
pose-assessment JSON; it did not contact the controller or create movement
authority.

The return route is **not implemented or installed**. Before any powered
trial, it must (1) reserve a fresh boot with no earlier pose capture, (2)
sample all seven servos three times plus a prewrite sample, (3) reject any
shift from the offset envelope or changing torque/goal, (4) record the exact
single transmission attempt and a bounded postwrite sample series including
fault cases, and (5) export the retained record before declaring success.
Postwrite encoder limits are diagnostic fault gates, not a physical barrier
that can prevent an unexpected move. Because an inverse shoulder motion may
lower the gripper, **confirm current tip-to-board clearance and intended
return path separately before authorizing that motion**. If the tip remains
in contact, do not use this inverse route; first design a contact-free
recovery strategy from a fresh measured pose. The old r54 fixed-pair
re-anchor is incompatible with the current source goals/positions and must
not be reused as-is.

At the initial offline checkpoint, `park_reanchor_policy.h` mirrored the
source-pose gate and tested a simulated settled return, source mismatch,
overshoot and wrong goal. Its eight-count postwrite envelope is an anomaly
detector only; it does not make a contact-path claim. The owner, route and
host record handling added next remain uninstalled.

### Offline return workflow completed; not installed

The return now has a one-use native owner and fixed-target route, plus a
board-service adapter and a default-off composition switch. The existing
firmware remains r56; no return route is registered on that installed image.
The route accepts no caller-selected servo IDs, target, speed or retry. It
captures three fresh start samples and a fourth prewrite sample, then permits
at most one paired write to `2389/1725` only if the offset state still matches.
It retains the last three postwrite samples through a bounded settling
window. An uncertain write, bad feedback, out-of-envelope position, missed
deadline or evidence failure stops progression. A fault record is readable
but cannot receive a successful receipt. The return route cannot be enabled
alongside the existing fixed re-anchor or park-step routes.

The host `park_reanchor_record.py` decodes raw native records independently,
classifies `MEASURED_RETURN` versus `FAULT_RECORDED`, and writes/replays a
wizard diagnostic export for either outcome. Even a measured return does not
prove physical tip clearance or authorize another move. Native policy,
owner, route, host decoding/export and composition tests passed (42 focused
tests). This is offline evidence; it is **not** a physical return test.
An additional 23 existing board-service, configured-route and park-step
regression tests passed after the new default-off integration.

Remaining before movement: stage and review a pinned app-only image with only
this return route enabled; implement the signed host one-use runner and
preflight; check that the current gripper has actual clearance along the
potential downward path; separately authorize the specific installation and
return trial. If clearance is absent, do not use the return command.

### r57 return-only candidate installed; no return commanded

The signed host `ParkReanchorHost` and `run_park_reanchor.py` launcher are now
implemented. They require a reviewed installed r57 startup, a stable pose
capture from a *different* boot, a matching one-use source claim, and no
same-boot diagnostic capture or prior return claim. The live CLI additionally
requires an explicit current tool-path clearance confirmation; its default
plan remains inert. It reserves the one-use claim before network access,
exports a success or fault record, sends a receipt only after a successful
replay-verified export, and never retries or sends a second motion.
`CharacterizationHTTP` now recognizes only the four fixed park-return paths
and rejects caller-supplied targets before network access.

Candidate r57 was staged exclusively from the verified r56 source. The
changed set is the return policy, owner and route headers, board services,
composition, and the board opt-in; the r56 park-step route is disabled in the
new board opt-in. Stage export:
`wizard-20260922T002841249867Z-803adda070224eb3ab82ac9493ab4998`.
The offline build succeeded using the unchanged bootloader and partition
artifacts. App SHA-256 is
`7d8ac14ae59272368fbf3031ebc3ad5a5835e84913d85ee5758df46670767b68`,
size 1,183,296 bytes in a 1,310,720-byte slot. Compile export:
`wizard-20260922T003055181870Z-087edefca56649f3a79cc1b33ea83d05`.
The exact-source and binary review passed; review export:
`wizard-20260922T003202822812Z-8aa82ffd1c644837abfcc3d6609357a4`.
The installer `--preflight-only --revision 57` passed, checking the installed
r56 predecessor image, protected filesystem snapshot and reviewed app hash,
without accessing hardware or reserving the install journal. Return host,
record, native route/owner/policy, installation-evidence and startup-binding
tests passed (310 focused tests); 19 authenticated transport/host tests passed.

The approved r57 app-only installation and one startup completed. The flash
readback matched the reviewed SHA-256, and the protected filesystem and
settings remained unchanged. The deployment journal is
`private-backups/controller-20260918-session1/app-r57-deployment-events.jsonl`.
The read-only startup export
`wizard-20260922T004406602738Z-39d08a110513469fa8d91831c6329bf1`
reported `IDLE_AND_PAIR_PROTOCOL_OBSERVED` on boot
`ec87a6cf10ca4b7995b35dc2f596a653` at `192.168.0.225`. A signed
read-only route probe timed out before TCP connection and consumed its
one-use authentication-gate claim; it did not establish signed-route health.
An unsigned park-return status GET returned 403 while a nonexistent route
returned 404, supporting route registration only. That read-only evidence is
exported as `wizard-20260922T004648965388Z-9d5cf2264641453e82b47fb3f1a25f55`.

One read-only r57 pose capture on the same boot exported
`wizard-20260922T012752540966Z-79228ba5f663422fab581df4fedc81ce`
with assessment
`wizard-20260922T012752488800Z-89e7446adcc344389c29447582c202c3`.
All seven positions were stable across snapshots. Shoulder goals remained
`2377/1737` and measured positions `2385/1730`, unchanged from r56. The
inert return planner proposes `2389/1725` and explicitly reports movement
unauthorized. An offline preflight using that real pose export and a mocked
future distinct r57 boot accepted the evidence without creating a claim or
accessing hardware. No hold, torque change, or movement command was sent.

At this checkpoint, the pose-capture boot was owned by that capture. A fresh
startup and signed route check were needed before a one-use return. More importantly,
the tool-tip path requires *current physical clearance confirmation*; a
prior user photo showed the gripper touching the board. An encoder envelope
detects a problem after a read, not contact or clearance. Do not invoke the
return if the tip is still touching or its possible path is obstructed.

### First r57 return from measured offset

The user supplied current side-view photographs showing the gripper visibly
above the placemat and approved one fresh startup, a signed connection check,
and one bounded return conditional on the controller's fresh joint checks.
The one USB reset produced boot `4abc3be94735693483ecbe18d27162a7`;
read-only startup export
`wizard-20260922T103123778758Z-35f59323d3324542b4d416bc7d748c52`
reported `IDLE_AND_PAIR_PROTOCOL_OBSERVED`. A signed idle-route GET was added
to the *same authenticated transport session* immediately before the only
motion-capable POST. It requires `NEW|0`, so a failed or uncertain signed GET
stops before any motion request, while successful sequence numbers remain
continuous. Host and transport tests passed (12 tests).

The real r57 pose export passed the fresh-boot preflight without network or
motion. The one-use live return then passed the signed idle check, the native
fresh seven-joint start checks, and endpoint verification. Result export
`wizard-20260922T103231158446Z-98c83ad043314ff29c447ecdc24069fb`
replayed successfully. The controller recorded exactly one target write;
shoulder measured deltas were `+6/-6` counts, with final errors `+2/-1`
counts relative to target goals `2389/1725`. Assessment is
`MEASURED_RETURN`, **not** a claim of physical tip clearance, Cartesian
accuracy, or keyboard readiness. The boot is now one-use claimed. No retry,
follow-on motion, torque command, settings change, or additional startup was
performed. Obtain a new pose and plan before any later movement.

Post-trial photographs from front and both sides show a visible gap between
the gripper and placemat. The operator reported no observed contact and did
not notice the movement. That is consistent with the small measured
`+6/-6`-count adjustment: the encoder evidence establishes that the joints
changed, while the photographs and operator report establish only that no
contact was observed. They do not establish millimetre-scale Cartesian
motion or accuracy.

### Post-return capture and r58 visible-step candidate

After the operator approved proceeding, one fresh r57 startup produced boot
`f759ca95e180c3cdae6a0db5a3d7720d`; no motion command was sent. Startup
export `wizard-20260922T193925665800Z-4dfbf660941f41eba16417651985e79c`
reported a stable idle controller. Its one-use read-only pose capture exported
`wizard-20260922T193938648730Z-2ceb496efa3749bc85cae0a565ae348d`
with assessment
`wizard-20260922T193938597852Z-c07d7abddd8840acb2d77517b8a64085`.
All seven joints again had zero sample span. Shoulder goals were `2389/1725`
and measured positions `2391/1724`, exactly matching the r57 endpoint export.
This proves persistence of the controller-reported endpoint across a startup;
it does not prove Cartesian position.

The inert next-step planner binds only that captured pose. It proposes fixed
goals `2413/1701`, a `+24/-24`-count paired shoulder change—four times the
measured first return—with expected encoder positions `2415/1700`. The native
policy allows at most 28 counts of directional travel, one target write,
speed 20/acceleration 1, no retry and no automatic return. Neighboring joints
must retain their goals, torque and tight encoder envelopes. The expected
positions retain the repeatedly observed `+2/-1` goal residual; they are not
a tool-tip or Cartesian prediction.

r58 was staged from the exact reviewed r57 source by replacing only
`park_reanchor_policy.h`; the signed route and one-use native owner are
unchanged. Stage export:
`wizard-20260922T194423914331Z-623ded2b34774085a9b6d13895e12939`.
The offline default-4-MB/no-PSRAM build succeeded with app SHA-256
`944155ce47d2eeb60e6c7e7cb12d687a9250c6b3c030de49d39c9e923dc544f5`
and 1,183,232 bytes. Compile export:
`wizard-20260922T194627054855Z-9bc643483a50464ea3b3e127600ae487`.
Exact-source/app review export:
`wizard-20260922T194754620618Z-50534b00d3c94ccaa7e9f83706caeae5`.
The app-only installer preflight passed locally and did not access hardware or
reserve a journal. The visible-step planner, native policy/record path,
legacy return regression, installation and startup bindings passed 330
focused tests. **r58 has not been installed or started, and no larger move
has been sent.** Installation/startup and the later one-use physical trial
remain separate explicit checkpoints.

The user then approved one r58 app-only installation and one startup followed
by read-only health checks only. The installation journal
`private-backups/controller-20260918-session1/app-r58-deployment-events.jsonl`
records one write attempt, full app readback matching
`944155ce47d2eeb60e6c7e7cb12d687a9250c6b3c030de49d39c9e923dc544f5`,
unchanged protected regions, and one startup reset. The first host health
invocation stopped before network access because its newly added r58 evidence
selector incorrectly fell through to a legacy attachment name. That local
selector was corrected without another startup or controller command.

Read-only startup export
`wizard-20260922T200044746790Z-e5fe82f89d964a24a5377ed1c3e20839`
then verified boot `8ffcdb982aa9843508ec1b2f574bdb3b` as stable `IDLE`,
`NOT_CONFIGURED`, zero records and no storage fault. It requested no signed
challenge and sent no servo command, provisioning, reset or retry. The same
330-test focused regression passed after the selector repair. **r58 is now
installed and healthy, but its visible step has not been invoked.** The
current startup remains unclaimed by pose capture or movement. A live trial
still requires the retained r57 pose export, current clearance, the exact
r58 startup binding, and separate authorization for one movement.

### r58 pre-bus rejection and r60 single-source correction

The authorized r58 visible-step attempt stopped with
`WRITE_DELIVERY_UNCERTAIN|1`. Its terminal export is
`wizard-20260922T202308007058Z-c762d278d9824b3eb5df5bc74cda07ea`;
the fault record is
`wizard-20260922T202307927819Z-f7b8c601ba8343dcaef20c25d48dfb90`.
The generic runtime classification is intentionally conservative, but source
inspection established a narrower result: the board-services adapter still
accepted only the former `2389/1725` return target. It rejected the r58
`2413/1701` target before calling `SyncWritePosEx`. Therefore the controller
accepted one authenticated HTTP write attempt, but **no servo-bus movement
write was issued**. The r58 boot is nevertheless consumed and must not be
retried.

The correction removes that duplicate target definition. The board adapter
now imports `ParkReanchorPolicy` and validates the requested goals against
the policy's `target12` and `target13`; the policy, owner and adapter therefore
share one target source. No envelope, speed, acceleration, one-write, no-retry
or endpoint-verification rule was relaxed.

The first corrected staging revision, r59, stopped during offline compilation
because the copied adapter did not explicitly include the policy declaration.
No artifact was installed and no hardware was accessed. The preserved failed
compile export is
`wizard-20260922T202808438722Z-86271b878fd84537b1bf5eb339bf3f0c`.

r60 adds the missing explicit include and otherwise retains the r58 movement
policy. Stage export:
`wizard-20260922T202919030806Z-b486fb383fa64b7cbcdf332df9bc6c9b`.
Its offline build succeeded with app SHA-256
`6f98f372b5a927b016ae81f0673df1ee8ddd0f0b78bc714d181746e575df7211`
and size 1,183,360 bytes; compile export:
`wizard-20260922T203120491645Z-474a80e233d44303a95718d8188c0f2c`.
Exact-source and binary review export:
`wizard-20260922T203245596804Z-4cfdf2e1f7934171aed092479582e7be`.
The native adapter tests passed (14 tests), the host integration regression
passed (307 tests), and the r60 installer preflight verified the reviewed
image, installed-r58 predecessor, retained settings filesystem and unused
one-shot journal without hardware access.

**r60 is reviewed but not installed.** The arm still runs r58, and no movement
was transmitted by the failed r58 attempt. The next checkpoint is one r60
app-only installation and one startup with settings and credentials preserved,
followed only by read-only health verification. The one-use visible step is a
later, separately evaluated action after that health evidence exists.

The user subsequently approved that installation/startup checkpoint. The r60
app-only installation completed with an exact full-image readback of
`6f98f372b5a927b016ae81f0673df1ee8ddd0f0b78bc714d181746e575df7211`;
the protected regions were unchanged. The one-use deployment journal is
`private-backups/controller-20260918-session1/app-r60-deployment-events.jsonl`.
One startup produced boot `8a630c8a8bd6411d3f883b41db3bbd61`.
Read-only startup export
`wizard-20260922T204545846486Z-2e607f7c27bf411582a4028716915796`
reported stable `IDLE`, `NOT_CONFIGURED`, zero records and no storage fault.
It requested no signed challenge and performed no servo command,
provisioning, additional reset or retry. Installation evidence export:
`wizard-20260922T204545487414Z-ff13ee2f784d4efeb92b48b13c1add88`.

The corrected one-use visible-step runner passed offline binding against that
fresh r60 boot and the retained stable pose assessment. It proposes source
goals `2389/1725` and fixed targets `2413/1701`; offline preflight accessed no
hardware and did not reserve the movement claim. **r60 is installed and
healthy, but no r60 movement has been commanded.**

The user then approved exactly one corrected r60 visible step. The native
fresh-start checks passed and the controller issued exactly one paired target
write to `2413/1701`. Export
`wizard-20260922T221447372736Z-d5aa776279fb4e80b0f965d50bfd632e`
replayed successfully with assessment `MEASURED_VISIBLE_STEP`. Measured
shoulder deltas were exactly `+24/-24` counts and endpoint errors were the
predicted `+2/-1` counts. The retained reference pose was verified, one write
was attempted, and no retry or automatic return occurred. This confirms the
r58 failure was the stale pre-bus adapter check and that the r60 single-source
correction transmits and verifies the intended bounded command. It remains
encoder-space evidence, not a Cartesian or tool-tip accuracy measurement.
The r60 boot is now consumed; obtain a fresh startup and pose capture before
planning another movement.

One approved non-motion follow-up startup produced fresh r60 boot
`de63804e91fe320165a3e3a2f3c7ac91`; restart observation exports are
`wizard-20260922T221631378318Z-b01126d414aa48cbad9eccdfc67564b1`
and `wizard-20260922T221637315609Z-a7103d6ffe8f4d34a339b16222bfac16`.
Read-only startup binding
`wizard-20260922T221644206364Z-00416bf888694956a1bb515c9d1197e9`
again reported stable idle state, zero records and no storage fault.

The subsequent three-snapshot pose capture exported raw evidence as
`wizard-20260922T221654131989Z-3a3ff519ca1049a6a1f089adba192cf8`
and assessment as
`wizard-20260922T221654077384Z-cbe8a0451e0c4d82bf0904275445e437`.
Every joint had zero position span and unchanged controls. Shoulder goals
persisted at `2413/1701`, with measured positions `2415/1700`, exactly the
r60 trial endpoint and predicted residual. All other joint goal/position
pairs also matched the pre-trial pose. This confirms stable encoder-space
endpoint persistence across startup; it still does not establish Cartesian
tip accuracy. The pose-capture boot is read-only claimed and must not be used
for movement.

### r61 bounded visible-interval campaign

The next movement phase is deliberately a small campaign rather than another
firmware revision per destination. It reuses the existing native multi-leg
characterization owner and its authenticated host/export workflow. The frozen
route starts only from the verified r60 persistent endpoint (goals
`2413/1701`, measured positions `2415/1700`, tolerance one count) and contains
four exact paired targets with constant sum 4114:

1. midpoint inbound: `2401/1713`;
2. lower endpoint: `2389/1725`;
3. midpoint outbound: `2401/1713`;
4. upper endpoint: `2413/1701`.

Each leg requires a fresh three-sample baseline, permits at most one servo-bus
write, observes the endpoint, and requires a verified durable export receipt
before the next leg can begin. The whole campaign permits at most four writes,
has no retry and no automatic return, and stops on uncertain delivery or
invalid feedback. The repeated midpoint supplies the first same-target
comparison from opposite approach directions while the two endpoints retain
the already demonstrated 24-count interval. These results remain encoder-space
evidence and do not establish Cartesian or stylus-tip accuracy.

Frozen plan export:
`wizard-20260922T223155774570Z-3eabfb9d99bf4b4c8b7fe6ac7c57eafb`;
plan SHA-256:
`0fac0479a582f4213ea01757993d17b6355ab36512e3adcd394ee6ee04c5e8fa`.
Stage export:
`wizard-20260922T223318549875Z-c870a0f57a5e47a5be7058c71c992b2b`.
The offline default-4-MB/no-PSRAM r61 build succeeded with app SHA-256
`5f713ae53577b3a4dc6a6419f2a3b84563b2db89f903be9c24bc496482f41451`
and size 1,183,616 bytes. Compile export:
`wizard-20260922T223520640680Z-05e034234f474e6993f41fec78cba262`.
Exact-source/binary review export:
`wizard-20260922T223654552605Z-59f4fa79d37b4eefac69b23d7406508e`.

The r61 installer, installation-evidence reader, startup binder and one-use
campaign CLI are integrated. Its local installer preflight verified the exact
r60 predecessor, reviewed r61 image, retained filesystem hash and unused
deployment journal without accessing hardware or reserving the journal. The
native preparation path, frozen route, reused multi-leg runner, CLI one-use
rules and r61 installation/startup evidence passed 337 focused tests.

The approved r61 app-only installation then completed. The one-use journal is
`private-backups/controller-20260918-session1/app-r61-deployment-events.jsonl`.
Full application readback matched
`5f713ae53577b3a4dc6a6419f2a3b84563b2db89f903be9c24bc496482f41451`,
and the protected flash regions were unchanged. The one approved startup
produced boot `2dac24417d23427deeb99a196eedc6dc`.

Installation evidence export:
`wizard-20260922T225230875704Z-5f2d84ebed144777b34e77bb60e687c9`.
Read-only startup export:
`wizard-20260922T225231246174Z-636d9f51c9cf45be94556f35f939144b`.
Both status reads were identical `IDLE / NOT_CONFIGURED`, with zero records
and no storage fault. The observation requested no challenge and performed no
servo command, provisioning, reset or retry. Offline replay then verified the
exact startup, installation and frozen four-leg plan bindings without hardware
access or reserving the boot.

**r61 is installed and healthy, but no r61 movement has been commanded.** The
fresh r61 boot remains unclaimed and is eligible for the exact four-leg
campaign after separate authorization and confirmation that its bounded
movement area is clear.

The user then approved the exact four-leg campaign with the movement area
clear. The campaign completed without a transport or controller fault. Run
export:
`wizard-20260922T231423278414Z-463b7c1b98f2430bad7765444b08786e`;
mapping result export:
`wizard-20260922T231423328861Z-4964be9217f44d1e97bfab522fe2e743`.
All four per-leg exports, the aggregate run and mapping result replayed with
valid manifests.

The measured rows were:

| Leg | Target | Direction | Measured endpoint | Target residual | Result |
| --- | --- | --- | --- | --- | --- |
| 0 | `2401/1713` | decreasing primary | `2410/1706` | `+9/-7` | settled miss, retained |
| 1 | `2389/1725` | decreasing primary | `2398/1718` | `+9/-7` | settled miss, retained |
| 2 | `2401/1713` | increasing primary | `2403/1712` | `+2/-1` | settled accurate |
| 3 | `2413/1701` | increasing primary | `2415/1700` | `+2/-1` | settled accurate |

The same `2401/1713` midpoint settled at `2410/1706` when approached in the
decreasing-primary direction and at `2403/1712` when approached in the
increasing-primary direction. The seven-count primary and six-count secondary
difference is direct encoder-space evidence of direction-dependent lost motion
(mechanical slack/backlash plus any servo deadband), rather than random target
scatter. After the first command in each direction took up that slack, the next
same-direction 12-count command tracked by the full 12 counts. No generic
compensation model is promoted from this single cycle. The arm ended at the
verified upper endpoint `2415/1700`.

Two further independently started r61 campaigns were then run with the same
unchanged route. Cycle-two mapping export:
`wizard-20260922T232910754318Z-d79be2ed34814a949658bfad4e269eae`;
cycle-three mapping export:
`wizard-20260922T233002049318Z-4108c0fe4ee5457fbde2efaed2564591`.
All eight endpoint values in both repeats matched cycle one count-for-count.
Across the three cycles, each direction therefore has six samples and every
per-leg endpoint has zero run-to-run span.

The frozen offline direction analysis exported as
`wizard-20260922T233255655734Z-9e6a65d489e449b09f35267b3f969804`.
It fits pair-sum-preserving local corrections of `-8/+8` counts for decreasing
primary motion and `-2/+2` counts for increasing primary motion. It proposes
one unseen decreasing-direction endpoint: desired `2407/1707`, candidate
command `2399/1715`, predicted endpoint `2408/1708`. The expected maximum
error is one encoder count. The model is fitted only for this local interval;
it remains unpromoted and has not been held-out validated, generalized to
other joints, or translated into Cartesian/tool-tip accuracy.
