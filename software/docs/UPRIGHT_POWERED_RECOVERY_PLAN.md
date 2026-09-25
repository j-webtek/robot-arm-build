# Powered recovery to upright reference pose

## Active strategy update

Follow [BOUNDED_MOTION_CHARACTERIZATION_PLAN.md](BOUNDED_MOTION_CHARACTERIZATION_PLAN.md).
Pause r32 deployment. Prioritize a reusable uncompensated finite campaign,
separating bounded settled misses from safety faults, then analyze whole trials
before choosing compensation. Historical single-step release instructions below
are superseded where they conflict with this update.

## Objective and authority

Supersedes the prior default request for padded support. Investigate and implement
powered recovery; physical support is not a blanket prerequisite. The user's
latest explicit approval covers reviewed firmware installation and staged tests
toward the upright/90-degree outcome. Do not repeatedly request approval for
those in-scope steps. This does not authorize blind homing, retries after faults,
configuration changes unrelated to the outcome, or bypassing feedback checks.
Controller restart is not homing, initialization is not a lift, and a received
command is not verified movement.

## Starting evidence

Latest release checkpoint: [r32 compensated candidate](R32_COMPENSATED_STEP_RELEASE_REVIEW.md)
is frozen, compiled and offline-reviewed. 101 board/regression tests passed.
No upload or hardware access occurred; r31 remains installed. Next is exact r32
installation/startup/live-runner binding and release checks before the first
prospective compensated step. Earlier checkpoint status below is historical.

Latest host checkpoint: independent compensated event review and a finite host
runner now exercise the native simulator end to end. They recompute endpoint
errors and arrival flags before signing progression receipts, preserve fault
settling as failure, and reject live operation pending a new release binding.
Next is board routing/resource admission and firmware release preparation.
No hardware access or changes occurred. See [compensated contract](COMPENSATED_SHOULDER_CONTRACT.md).

Latest native-session checkpoint: the compensated candidate now performs owned
capture, authenticated plan admission, one simulated packet, desired-endpoint
verification and fault-settling exports. **100 combined tests passed**. Events
separate desired-position error from raw goal residual. Next is independent host
review/runner integration, followed by board/release work. Installed r31 and
hardware state were not changed. See [contract status](COMPENSATED_SHOULDER_CONTRACT.md).

Latest authentication checkpoint: the compensated-step host signer and independent
native verifier are implemented offline, with **132 combined regression tests
passing**. The signed plan binds desired and command endpoints, fixed offsets,
capture digest and limits; native reconstruction rejects altered signed plans.
Next is finite session/event/export integration. r31 remains installed; no new
hardware access occurred. Details: [compensated contract](COMPENSATED_SHOULDER_CONTRACT.md).

Latest software checkpoint: [compensated endpoint contract](COMPENSATED_SHOULDER_CONTRACT.md).
Independent Python/native implementations now separate desired positions from
compensated goal registers, with 72 focused tests passing. They remain offline;
next is exact signed-capture binding and finite-session integration. r31 remains
installed; no additional movement or restart occurred in this checkpoint.

Latest offline follow-up: [local pair offset analysis](LOCAL_PAIR_OFFSET_ANALYSIS.md).
A frozen r29 +10/-7 offset predicts r31 settling within 1/0 counts. The pure
offline model preserves goal sum 4114; no compensation command was sent. Next is
a contract separating desired measured endpoints from commanded goals, followed
by one prospective trial after fresh-state and release review.

Latest hardware checkpoint: [r31 live local step](R31_LIVE_LOCAL_STEP_RESULT.md).
r31 is installed. One shoulder-pair packet moved actual positions -15/+14 counts,
but left +9/-7 count goal residuals. The parent stopped at ARRIVAL_DEADLINE;
same-boot read-only settling completed and all 53 referenced export checks passed.
No retry or return followed. Next is offline local-offset analysis and a newly
reviewed fresh-pose trial, not another execution of this consumed command.
Earlier candidate/deployment status below is historical.

Latest candidate: [r31 local-step board review](R31_LOCAL_STEP_RELEASE_REVIEW.md).
New board routes and memory checks are tested and compiled. The host runner and
independent endpoint review now pass the 24-test transport/native integration
suite. The installer/startup and live-runner binding are now implemented, with
147 installation/startup and 27 release/runner/HTTP regression tests passing.
The actual local r31 preflight passed. No installation or hardware motion has
occurred. Next is installation/startup evidence acquisition, then the bounded
fresh-pose step; see the r31 review for the precise remaining sequence.

Current development: [fresh-pose local shoulder step](LOCAL_SHOULDER_STEP_CONTRACT.md).
The candidate uses measured travel while preserving the existing commanded pair
sum; its historical example is 2405/1709, not a hardware command. Controller-owned
capture, native verification, one-shot dispatch and fault settling now pass the
integrated simulation tests. Board routing and the offline host workflow are
implemented, including live release binding; deployment remains pending. Installed r29
is unchanged. See the r31 review for current status; older checkpoints below
remain historical evidence, not outstanding copies of completed work.

Latest software checkpoint: [r30 offline release review](R30_FAULT_SETTLING_RELEASE_REVIEW.md).
The integration image is compiled, but preserves the obsolete r29 starting window;
do not replay that step from the newer pose. No new installation or movement occurred.

Software follow-up: the [fault-settling collector](FAULT_SETTLING_CAPTURE_IMPLEMENTATION.md)
now has authenticated sessions, opt-in board-owner wiring, candidate HTTP routes
and an integrated simulation host runner. Live revision binding and deployment
remain pending; no new firmware has been installed.
Installed firmware and latest physical evidence remain r29 below. Next integration
must preserve the motion fault while exporting fresh settling observations.

### Latest checkpoint: r29 produced additional shoulder movement

The three-snapshot baseline passed and one upward shoulder packet was sent.
The first postwrite scan detected transient wrist motion/drift and stopped
command progression. A separate diagnostic-only restart and three read-only
snapshots established settled positions:
`[2047,2429,1688,2904,1591,2041,2047]`, goals
`[2047,2419,1695,2907,1589,2040,2047]`, torques all1.
Shoulder changes were-19/+21counts, with10/7count residuals. Wrist pitch settled
to1count from its pre-command baseline. No return or additional target was sent.
This is movement evidence, not endpoint success or verified physical clearance.

Current boot `aabbadc2924d859bfacb57e1aeccd6cf` is reserved by completed read-only
pose capture. [Full r29 result and next priorities](R29_STABLE_CLEARANCE_RECOVERY.md).
Next add read-only settling observations after latched faults without restart,
and separate transient response from settled accuracy before admitting another
bounded step from fresh state. Do not reuse the obsolete r29 start bounds.

### Previous checkpoint: r28 installed; fresh elbow offset blocked the write

The reviewed recovery firmware was installed and started successfully. Its live
baseline was `[2047,2448,1667,2904,1590,2041,2047]`, with existing goals unchanged.
The elbow was3counts below its2907target, exceeding the current2-count baseline
tracking condition. The session faulted before any target write (confirmed0).
No retry or further movement was sent. Current boot:
`710c666ba04bc64b1c265bbbebf033a1`; stateFAULT / RISE_BASELINE_NOT_HELD.
See [r28 evidence and next design change](R28_CLEARANCE_RECOVERY.md).

Next evaluate a multi-snapshot measured baseline that distinguishes bounded
pre-existing goal offsets from new movement/drift. Keep selected-joint arrival
accuracy separate. Do not repeatedly broaden a single threshold merely to pass,
and do not claim either fresh ongoing state or physical clearance from this one
retained scan. The shoulder-lift command has not yet been sent under r28.

### Recovery candidate after the user's request to move away from the board

An offline, source-bound preview now evaluates one additional shoulder-only step
from the last r27 sample, without treating that historical sample as current.
See `kinematics/shoulder_clearance_recovery.py` and run
`python software/scripts/preview_shoulder_clearance_recovery.py` to reproduce.
The previous commanded pair sum4114 is preserved: candidate goals12=2419,
13=1695, a further24-count mirrored target change. From the last measured
positions2448/1667 this is29/28counts of proposed travel, below a32-count bound.
All other goals remain unchanged. The modeled end edge rises monotonically over
30 one-count samples, by7.052mm total. This does not measure lowest-gripper-point
clearance or establish absence of contact, link collision or cable interference.

Preview export: `wizard-20260919T204823069839Z-a52d5f642ca74cfa88768406ad265eb0`.
Fourteen offline tests passed, including changed-pose/goal and malformed-count
rejection. No controller access, restart, firmware deployment, settings change
or movement was performed for this preview. r27 remains the installed image.

Implementation remaining before the next movement:

1. Add a distinct bounded native/host recovery scope for the exact known residual
   state. Do not loosen r27's normal arrival criteria or silently reuse its
   consumed session. Existing goals must still match the prior commanded pair;
   fresh positions must be stationary, enabled and in the reviewed local window.
2. Acquire fresh seven-joint baseline, then intent, then immediate prewrite scan.
   Reject changed goals, unexpected residual direction, nonselected drift, stale
   reads or more than32counts actual-to-target travel. Keep target-pair sum4114;
   never independently recenter paired servos on their measured load errors.
3. Issue at most one paired target packet, speed20counts/s and acceleration1.
   Preserve elbow/wrist/base/gripper targets. Export targets and raw positions;
   retain the two-count endpoint test as an accuracy result, distinct from
   observed partial upward progress. A shortfall is not permission for a retry.
4. Verify the contract in native and host simulation, then review/build the app,
   preserve settings/credentials, and perform the approved bounded test. No blind
   home, torque-off, automatic return or second movement. Upward-pointing wrist
   and elbow changes follow only after the clearance step is established.

### Latest checkpoint: r27 installed; first shoulder rise moved but stopped short

The separately approved second USB attempt succeeded with the vendor's longer
reset timing. App readback and protected flash checks passed; one startup passed.
One shoulder packet was sent after fresh seven-joint checks. Servo12 moved
2455 to2448 toward2443; servo13 moved1659 to1667 toward1671. Correct target registers
were read back. Eleven samples over0.333–4.790 seconds after the write showed the
same5/4-count residual errors. The controller faulted at its5-second observation
deadline; no return, retry or additional motion was sent. All14 event exports were
verified and independently replayed offline. This establishes partial directional
motion, **not verified target arrival or Cartesian clearance**.

Current installed revision is27, boot `681c7954a64a176cc0a833d1419c203a`, session
FAULT / RISE_OBSERVATION_DEADLINE. The historical last sampled pose must not be
treated as a fresh current pose. See [full evidence and next steps](R27_SHOULDER_RISE.md).

Next: use the existing raw feedback to characterize the residual and review
controller/servo position-control settings read-only. Distinguish deadband/load/
paired-servo behavior before proposing compensation. A future bounded test must
start with fresh pose and target readings, account for the pending target errors,
and preserve the board-clearance direction. Do not increase travel merely to
force a pass or assume a longer timeout resolves a flat eleven-sample plateau.

### Prior checkpoint: r26 restored, r27 not installed; no rise sent

The r27 installation attempt failed during USB bootloader synchronization before
any flash write. One guarded recovery startup restored the unchanged r26 app.
Three fresh read-only captures confirmed unchanged positions/targets and all
seven torque states enabled. See [r27 deployment/recovery result](R27_SHOULDER_RISE.md).
The remaining immediate blocker is the USB bootloader handshake, not a measured
failure to reach a shoulder target: the rise packet has never been sent.
Preserve the failed deployment journal, and investigate the connection before a
separately recorded new attempt. Keep external servo power unchanged.

### Completed test definition: one mirrored shoulder rise, not preparation replay

r26 physically established same-position targets and enabled states for all four
auxiliary joints; its final persistence handshake faulted after all 24 records
were exported. See [r26 results](R26_POSE_PREPARATION.md). Do not rerun it.

r27 separates acquired-sample timing from terminal export waiting, and adds one
signed `SHOULDER_RISE` scope. It requires all seven joints freshly enabled and
tracking before action, and the host binds all seven positions within16 counts
of the last recorded folded pose. After exported intent and another fresh scan,
send one synchronized target packet: servo12 minus12 counts, servo13 plus12,
speed20 counts/s, acceleration1. Preserve every other joint target and the observed
pair relationship. No explicit torque action, retry, return or automatic next leg.

Read back both targets and all seven actual positions. Monitor the bounded
travel envelope and unchanged neighbors; require three settled arrival samples
within two counts before success. A five-second observation window is distinct
from the ten-second export barrier. No forward progression on failed evidence.
The nominal endpoint rises about2.86mm for this roughly1.05-degree shoulder step;
this is a model prediction, not measured gripper/board clearance.

Only a successful physical step supports expanding the movement campaign toward
upright. Do not interpret a transmitted packet or persisted receipt as arrival.

### Current work: r26 finite same-position preparation

The user explicitly approved updating firmware, installing, and testing. r26
extends the observed r25 target-write behavior to the remaining passive auxiliary
joints (11,15,16,17), in that fixed order. It requires both shoulders and elbow
already enabled and tracking. It never writes a nominal zero/home target: each
target comes from a fresh scan and is rechecked immediately before transmission.
Target writes may activate servos. No explicit torque command, lift, automatic
return, or retry is included in this preparation scope.

Each joint has six authenticated/exported records: baseline, intent, action, and
three readbacks. Only verified target/position/torque state with preserved neighbor
states permits the next joint. Any delivery, feedback, continuity, or export fault
stops progression. Cumulative encoder drift is bounded against the initial scan,
not reset at each joint. Preparing all four requires 24 records; fewer passive
joints require fewer blocks. This is holding-state evidence, not Cartesian accuracy.

After successful preparation, implement/review the shoulder-first movement path:
preserve the observed shoulder-pair relationship, use a small synchronized step,
read fresh joint positions, export the result, then expand only on verified
arrival. The final upright and 90-degree angles are reference-model goals until
confirmed against the installed geometry. No elbow-first descent while the
gripper may still touch the board; no claim of clearance from encoder data alone.

Older entries below are chronological history, not current installation authority.

### Requested next physical outcome: taller posture and 90-degree elbow

The user now requests upper arm upright and elbow approximately90 degrees.
The later explicit approval now includes reviewed firmware deployment and staged
testing, but not an arbitrary all-joint home. No movement was sent during the route
review. The current r25 session is completed and its same-position scope cannot
execute the requested lift. A reviewed movement-capable controller path is needed.

Replaying the reference kinematics at the last r25 encoder positions gives
nominal shoulder35.77deg, elbow165.41deg and wrist pitch-40.34deg. These are
reference coordinates, not externally measured physical joint angles. The
shoulder-first route initially raises the modeled endpoint; elbow-first lowers
it slightly. Retain shoulder-first as the candidate sequence, not clearance proof.

Before proposing the exact movement-capable image and bounded test, address
the other passive joints (IDs11,15,16,17), shoulder pair correspondence (observed
sum4114 versus reference4094), and fresh-state handoff after the completed
experiment. Do not force the pair to nominal home counts or assume a passive
wrist will remain fixed while lifting. Preserve base direction and gripper
opening; do not turn on zero-goal passive joints. The first physical step should
increase clearance with verified endpoints; later steps unfold toward90 degrees.

### r25 installed; physical mixed-state target experiment succeeded

The approved one-write trial set servo13's target to its fresh position1659.
Three post-command scans showed position1659, goal1659 and torque1; before the
write torque was0. No explicit torque command was sent. Shoulder12 remained
position/goal2455 with torque1, and other joints retained their measured states.
The exported session completed without retry or follow-on movement. This verifies
same-position target establishment, not travel accuracy. Next is a separately
reviewed small enabled-pair movement with clearance and endpoint checks. See
[r25 physical result](R25_MIXED_TARGET_RESULT.md).

### r25 candidate compiled and reviewed; awaiting deployment scope

The mixed-state image is frozen with SHA-256
`483604c16de0b2061335873fdc176b90551e16e7552fcd2aa6058e6449bbde5f`.
It fits the existing partition profile; 67 regression tests passed. r24 remains
installed and no hardware was accessed. Follow
[r25 exact candidate and proposed scope](R25_MIXED_TARGET_APPROVAL_SCOPE.md).

### Authenticated mixed-state source integration validated

The mixed experiment now uses a distinct signed scope, resumable native session,
shared bus reservation, independent host review and verified export receipts.
The real host runner drove the native simulated owner successfully for passive
and enabled outcomes. Authentication/export failure tests stop without retry.
Current r24 is unchanged; the live runner refuses mixed execution until a reviewed
compatible image and installation binding exist. Next is offline candidate staging
and build review, not another attempt against the installed passive-only session.

### Mixed-state target experiment modeled and replayed

An offline one-write model now uses the actual captured mixed state, preserves
the enabled shoulder and checks target readback independently of acknowledgment.
Both passive and enabled post-write outcomes are simulated with no automatic
follow-on. Forty tests passed; a reproducible historical replay is exported.
This is not a deployed controller or a physical movement success. Follow
[mixed shoulder experiment](MIXED_SHOULDER_TARGET_EXPERIMENT.md) for the native
implementation and concrete progression to moving-endpoint tests.

### Read-only r24 capture completed: mixed shoulder state identified

The approved existing-image startup and three-snapshot capture succeeded.
Shoulder12 is enabled at position/goal2455; shoulder13 is disabled at position1659
with goal0. All seven encoder positions were unchanged across the three scans.
This explains SHOULDERS_NOT_PASSIVE. Do not repeat passive-only initialization;
review an explicit mixed-state procedure preserving the already-matched shoulder
and setting the other shoulder's fresh target before any enable. No new movement
was sent or authorized. See [captured state and next decision](R24_READ_ONLY_POSE_RESULT.md).

### Completed capture preparation: existing r24, not another firmware cycle

The existing r24 image already includes the three-snapshot read-only pose route.
The host pose CLI now supports explicit `--revision 24` and rejects a boot already
reserved by a shoulder session. The current faulted session owns the bus, so a
single explicitly approved startup is needed before using this route. Do not
reinstall firmware merely to obtain this capture, and do not power-cycle servos
or disable torque to make the passive-only initialization condition pass.

Proposed scope: one startup of existing r24, idle checks, then one three-snapshot
read-only pose capture; no hold, target write, torque change, settings change,
firmware installation or follow-on movement. Export seven-joint actual positions,
goals, torque, moving flags, timestamps and raw records. This describes the new
post-startup state, not a reconstruction of the discarded historical failure.

Classify the shoulders from the evidence: both passive, both enabled, or mixed.
Compare goals with actual positions and sampled drift before choosing a movement
path. An already-enabled or mixed pair needs a specifically reviewed procedure;
do not keep retrying passive-only initialization or overwrite goals blindly.
Once a supported state and increasing-clearance direction are established, the
next actuation should be one small space-clearing move with endpoint feedback,
not a blind full upright reset.

Offline baseline-failure retention now also covers SHOULDERS_NOT_PASSIVE and
ENABLED_JOINT_NOT_TRACKING with their complete acquired scans. That source fix is
not installed and is not required for the existing read-only capture. Thirty-seven
pose and shoulder regression tests passed; no hardware commands were sent during
this preparation. Full schema/reading validity checks remain in place.

### r24 installed; initialization stopped before writes

The approved r24 app-only installation and single startup completed with exact
readback and protected regions unchanged. The one initialization attempt stopped
at SHOULDERS_NOT_PASSIVE, with zero target writes and no pair-enable. This
baseline rejection still lacks a retained pose record; the post-preload capture
fix was not exercised. No retry or torque-off followed. See
[r24 result and next diagnostic step](R24_SHOULDER_INITIALIZATION_RESULT.md).

### First live r23 shoulder trial: stopped before pair enable

After the user's explicit request to proceed with live testing, one bounded
shoulder initialization was attempted. Fresh all-joint baseline matched prior
positions. Servo12 acknowledged a target preload to its measured2455 position,
but the next verification scan faulted STATE_CHANGED. Only one preload was
issued; servo13 preload and pair-enable were not attempted. No lift, reset,
retry or automatic torque-off followed. The one-use session is consumed.

Run export: `wizard-20260919T185232175443Z-7e43cb9dbdc34a71bcd945761fba2cea`.
See [R23_FIRST_SHOULDER_TRIAL_RESULT.md](R23_FIRST_SHOULDER_TRIAL_RESULT.md).
The failure scan was not retained by r23, so the offending joint/field remains
unknown. A narrow offline correction now retains the already-acquired mismatch
snapshot without changing command limits or adding bus traffic. It is NOT
installed. Further firmware/startup authority must be explicit; the current
fault must not be bypassed to produce a more visible movement.

### Completed r23 app-only installation and idle startup checks

The user explicitly approved one r23 application-only installation and startup,
preserving settings/credentials, followed by read-only idle checks and no hold,
torque changes or movement commands. This exact scope is now consumed.

- Application SHA256: `9edf6bbcf1052a8191d7ecac37195867bb8fafd0149bcaecf585834c807f579b`.
- Journal: `private-backups/controller-20260918-session1/app-r23-deployment-events.jsonl`.
- Installation export: `wizard-20260919T184819223012Z-cb87d6db097f4b4295c9ea658c40d94a`.
- Startup export: `wizard-20260919T184819488795Z-a3b00dfe774340749e3ac636aa903a03`.
- Boot: `6053f8c5292f9b6b4d59f2f690241314`.

The installer verified the expected controller, r22 predecessor and filesystem
before writing, then compared the complete application readback and protected
region digests. All matched. One startup reset was sent; no retry or filesystem
provisioning occurred. Startup status/capabilities/status reads reported IDLE,
NOT_CONFIGURED, zero records and no storage fault, unchanged across the checks.
Free internal heap was 174496 bytes, minimum 170260, largest block 110580.
This is idle resource evidence, not active-session stack/heap sufficiency proof.

No shoulder prepare/start, servo read, target write, torque change or movement
command was sent. Joint readings below remain historical; this startup did not
reacquire them or verify current mechanical pose. Recovery is not yet performed.
Next is a separately reviewed/approved bounded shoulder initialization with
fresh all-joint admission, not an immediate lift or home command.

### Completed r22 installation and shoulder capture

The user explicitly approved one r22 app-only installation, one startup and one
read-only shoulder capture, with no hold, torque change or movement command.
That scope is now consumed. Installation completed with exact application
readback and unchanged protected-region digests, including the existing
filesystem/settings/credentials. There was one startup reset, no retry.

- Installation evidence: `wizard-20260919T173513868280Z-20d252cc40994889bca5aa5dfa9aa445`.
- Idle startup: `wizard-20260919T173514085495Z-b36c3afd6188430db35605af58fda0fd`.
- Boot: `ed7eb7888e00e3893ca7a48eda9be57c`.
- Transport export: `wizard-20260919T173520345411Z-a749b7d191764163b819d7bb5f488aee`.
- Independently replayed assessment: `wizard-20260919T173520270864Z-9f6959bf4f50471ea34dd4ae6351b875`.

All 34 reads succeeded over 12,812 microseconds; retained GET matched the POST
result. Shoulder12 position2455, shoulder13 position1659; both torque0, goal0,
mode0, speed0 and moving0. Both reported model2057, limits0–4095, P32/D32/I0,
deadbands0/0, torque limit1000 and lock1. Offset register raw words were2039
and3613 respectively. Do not interpret unequal offsets as a fault or subtract
their difference as compensation without reviewing installed offset semantics.
The observed position sum4114 still differs by20 from reference mirrored sum4094;
one static capture cannot establish its cause or a safe correction.

These are controller-reported register observations, not whole-arm clearance,
pose stability over time, mechanical alignment or physical accuracy proof. No
new whole-arm pose capture or recovery movement was authorized/performed here.
Next work is offline target-preload and coupled-shoulder initialization design
using this evidence. Any further hardware mutation requires its defined scope.

Base is fixed according to the user. The gripper touches the board according to
the user and latest photograph. Freshest saved capture:
`wizard-20260919T162409109808Z-482d849b3ab548a69c8b9eae7ef59b8f`.
Positions11–17:2047,2455,1659,2906,1589,2040,2047. Torque only enabled on14.
Others had goal0. Treat these as historical until reacquired for execution.
Do not energize passive joints against their zero targets.

## Intended pose

Upper arm approximately vertical, elbow approximately90 degrees, forearm over
the board and gripper clear. Preserve base yaw and gripper opening. Reference
model candidate: shoulder0, elbow pi/2, wrist pitch0; the actual mechanical pose
requires validation. Do not command every joint to90 degrees. Counts from the
reference conversion are not yet verified installed targets.

## Offline route findings

`kinematics/upright_recovery_preview.py` samples all six shoulder/elbow/wrist
orders at no more than one count per changed axis using pinned reference FK.
At the captured pose, shoulder-first raises the configured endpoint initially
and never samples below its initial Z. Elbow-first dips about0.128mm;
wrist-first dips about5.56–15.07mm depending on subsequent ordering.
This supports evaluating shoulder-first, not admitting it: the model lacks
lowest-gripper geometry, link volumes, board transform, cables, contact dynamics
and passive-joint motion. It is a kinematic preview, not a physics simulation.

## Initialization and coupled shoulder investigation

1. Verify fresh positions/goals/modes/torques and record command-independent
   observations before any write. Exclude goal0 as an intended destination.
2. Review both shoulder servos12/13. Their sampled sum4114 differs by20 counts
   from the reference mirrored-goal sum4094. Do not treat this as calibrated
   offset or immediately force it away: determine whether offsets, compliance,
   loading or reference mismatch explain it using read-only evidence first.
3. Design target preloading at each measured passive-joint position, readback
   before enable, and rejection if the position changes between those steps.
   Confirm the actual servo write semantics; a position write may have effects
   beyond changing a target register. Model acknowledgement uncertainty.
4. Treat shoulder pair activation as a coupled operation with bounded skew and
   monitoring of both servos. Do not leave one driving the linkage toward an
   incompatible partner target. Determine a supported enable strategy before
   deployment. Preserve already-enabled elbow state unless separately reviewed.
5. Establish load-bearing holds without lifting first. Capture all-joint drift,
   goal/readback and available effort/status. No auto rollback/torque-off after
   partial success: export the exact resulting state and stop progression.

## Staged recovery

1. Once initialization is verified, evaluate a small shoulder-first lift away
   from contact, with all required joints holding and fresh multi-joint feedback.
2. Require evidence of clearance before advancing to larger waypoints; encoder
   arrival alone does not establish release of board contact. A targeted user
   observation is acceptable while camera integration remains deferred.
3. Progress toward upright shoulder, then unfold elbow toward the reviewed bend,
   then adjust wrist as needed. Review all links/tool/cables along each path.
   Freeze exact target counts, speed, acceleration, deadline, error tolerance and
   waypoint count in the execution proposal rather than invent them at runtime.
4. Withhold every later stage on non-arrival, invalid feedback, unexpected joint
   motion, uncertain command delivery or export failure. No automatic resend,
   reset, farther target, gain tuning, return or torque disable.
5. Export requested/encoded/readback/measured positions for each joint and stage.
   Capture a settled final pose; verify the physical upright interpretation once.
6. Use the verified reference for bounded bidirectional tests, then ghost typing.

## Implementation and test gates

### r23 installation profile ready; explicit approval pending

The app-only installer now pins r23 to the reviewed hash/1141360-byte image,
r22 predecessor and a fresh one-use r23 deployment journal. It binds the pinned
offline candidate review and preserves the current observed-pose filesystem.
Installation-evidence and read-only startup-observer profiles recognize r23.
`--revision 23 --preflight-only` returned LOCAL_PREFLIGHT_VERIFIED with no
hardware access, journal reservation or deployment authority. No live operation
was performed. The exact proposed scope and approval text are in
[R23_INSTALLATION_APPROVAL_SCOPE.md](R23_INSTALLATION_APPROVAL_SCOPE.md).

The next external-state change requires that explicit installation/startup
approval. It excludes all hold/preload/torque/movement commands. Offline work may
continue while awaiting approval, but do not treat goal continuation as consent
to flash or to execute the powered shoulder session.

### Restricted transport and native delayed-receipt tests

`application/shoulder_session_http.py` provides a fixed-route, numeric-private-IP
HTTP adapter. Construction performs no I/O. It only permits prepare/start/receipt
POSTs and status/record GETs with bounded bodies and a total deadline, rejects
redirects/encoded responses, and latches closed on protocol/I/O failure. It
consumes mutation attempts before opening the socket, so even uncertain delivery
cannot be retried through that adapter. No live CLI or runner release was added.

Seventeen tests passed across transport and native bridge. Transport tests use
fake sockets, never LAN traffic. Native bridge tests advance its controller clock
by 100ms per receipt and still finish; a 10.000001-second late enable-intent
receipt faults before the broadcast; a 600ms late post-enable receipt faults
with exactly the existing two preloads/one broadcast and no further writes.
No automatic return, retry or torque-off occurs. Delays are deterministic test
clock changes, not a real ESP32/network scheduling measurement.

The firmware, settings and live arm remain unchanged on r22. Next deployment
preparation is to pin r23 into the existing app-only installer/startup evidence
profiles and run its offline preflight. Only then present the exact app-only
installation/one-startup scope for explicit approval. That scope must not include
prepare/start of the shoulder hold; powered initialization is a separate approval
after post-install idle/resource evidence and fresh state checks.

### Actual board-adapter ingress and r23 compatibility review

`test_shoulder_board_session.cpp` compiles the actual board adapter with real
native owner/receipt code and BCrypt, substituting only platform files, clock,
HTTP server and servo bus. Eleven isolated-process cases pass: success, occupied
pose owner, missing key, unhealthy controller, busy bus, unexpected prepare
parameters, malformed/oversized start body, signature tampering, expired lease
and health lost before start. Preparation and start perform zero bus reads or
writes; the first successful poll performs 28 baseline reads and zero writes.
Repeated prepare does not reload the key; failed starts cannot be reused.
This is not an ESP32 HTTP socket or filesystem integration test.

Offline r23 review now verifies the compiled artifact hashes, staged source
inventory, expected app/partition/bootloader identities and retained original
backup/recovery artifacts. Review export:
`wizard-20260919T183847722083Z-b678aeb19d894ca698948a169a198c85`.
The application is 1141360 bytes, leaving 169360 bytes in its 0x140000 slot.
213 relevant individual frames were inspected; the largest is 496 bytes.
These are individual frames, not a call-chain bound. Runtime heap/stack and
current installed bytes were not inspected. The report remains deployable=false;
no installation or further startup is authorized by this offline review.

Remaining immediate work: connect the bounded host runner to a reviewed no-retry
transport and test delayed replies with the native owner clock; freeze a defined
installation/startup proposal and, separately, the initial shoulder-hold scope.
Do not skip these boundaries by interpreting offline test success as permission
to enable torque or lift away from the board.

### Host export timing measured and duplicate persistence removed

`scripts/measure_shoulder_export_latency.py` uses instantaneous synthetic test
responses and real exports in the workspace; it never opens a socket/serial
port or reads a private key. This is host overhead, not live loop timing.
Before optimization, maximum post-enable receipt gap was 522.18ms and cumulative
post-enable host overhead was 3.092s, already exceeding the candidate's 500ms gap
and 3s observation ceiling. Evidence:
`wizard-20260919T183536504970Z-f4e38789c404428f88b4c51a93cd7063`.

The runner no longer exports the entire growing report before and after each
GET. Read audit entries are persisted with the next POST intent or terminal/
failure report. Exact event bytes remain independently exported and verified
before any signed advancement receipt; POST intent and response persistence
remain. There is no relaxation of controller deadlines or receipt validation.

After the change, the same synthetic case measured 140.89ms maximum gap and
0.942s cumulative post-enable host overhead; total host run fell from 6.385s to
2.269s. Evidence:
`wizard-20260919T183604231027Z-c7ac4b1a7c0b4cf98757cb9782c18706`.
The fake transport's controller timestamps are synthetic: these measurements
do not prove a real two-second hold, Wi-Fi headroom, or successful live timing.
The runner/native bridge regression suites passed (13 tests); a further receipt
intent-export failure test verifies no receipt is transmitted when that export
fails, even after the exact event export succeeds (runner suite: 6 tests).
No firmware candidate or installed device changed in this increment.

### Bounded host runner and independent record review

`application/shoulder_session_runner.py` implements one prepare/start, bounded
status/record polling and export-before-receipt using an injected transport. It
is explicitly SIMULATION-only for now, with no default network adapter or live
CLI. It reserves a boot-bound run before I/O, exports request intent and response
evidence, never saves signed request tokens, and does not retry delivery failures.
It will retain a reported fault record read-only without acknowledging it.

`application/shoulder_session_review.py` independently checks event order,
identity, scan ordering, all seven raw position decodings, baseline-bound target
preloads, unchanged neighboring joint state, expected shoulder torque transition,
action result and stationary hold feedback before acknowledging a record. A
controller completion still is not physical accuracy or board-clearance proof.

Thirteen tests passed across the finite runner and native/host bridge. Runner
cases cover complete synthetic evidence, prepare/start/receipt delivery failure,
incorrect preload target and a second invocation rejected before I/O. The bridge
also passes the independent reviewer over real native-generated synthetic records.
The initial test run expected the wrong exception class for the deliberate
duplicate-run rejection; it was corrected to the existing durability exception.
No device access occurred. Live scheduling remains unverified: the runner's
per-exchange exports must be measured against the candidate's 500ms post-enable
gap and 3s observation ceiling before live release. New board-specific ingress
failure tests and candidate compatibility/resource review remain outstanding.

### Combined r23 candidate staged and compiled (not installed)

`stage_r23_shoulder_session_candidate.py` verifies the pinned r22 source
inventory, copies it to a new public candidate, adds the composed shoulder
session and patches the exact dispatch paths identified below. Stage export:
`wizard-20260919T182800627556Z-6b29a4992cb345c8b42d8f3d094fb278`.
The old r22 stage and installed image remain unchanged.

The new board adapter exposes one explicit POST prepare and one authenticated
POST start for fixed command `r23-shoulder-hold`, scope PAIR_HOLD. Preparation
loads the existing private key read-only and reserves the controller without
servo access. Start activates the owner; polling performs the fresh feedback,
receipt-gated preloads and optional pair enable. There is no lift endpoint.
All other prepare/capture paths reject the reservation, and the reserved loop
returns before polling the old owners. Reservations are not automatically freed.
Physical clearance is not inferred from the health callback or authentication.

Combined ESP32/default-4MB/no-PSRAM compile succeeded; verified export:
`wizard-20260919T182939587224Z-a44b766fe9a943deabd1777fb22ce582`.
App SHA256:
`9edf6bbcf1052a8191d7ecac37195867bb8fafd0149bcaecf585834c807f579b`.
Thirteen tests passed across staged dispatch guards, native/host bridge,
session transport routes and authorized starts. Staged guard tests are source
regressions, not live concurrency tests. No device was contacted or flashed.

Before deployment: review candidate compatibility/resource headroom; exercise
the new board prepare/start ingress and failure paths, not only generic routes;
implement the bounded host runner with durable exports and no retries; evaluate
host receipt timing against the post-enable observation deadlines. Then request
explicit installation/startup authority separately from any powered hold/lift.

### ESP32 owner build and dispatcher audit

The composed owner now compiles and links for the default 4 MB/no-PSRAM ESP32
profile. Verified export:
`wizard-20260919T182503367564Z-805b732ed3a34e6db9792e55ce504dfe`.
Application SHA256:
`ced551606d7bfc99ce72457194fb0c2dc8753c50842a8f756d2b6c7c708cb95c`.
Compiler reports 409137 program bytes and 115912 global-data bytes for the
probe, not the full recovery image. Linked `shoulder_owner_probe` occupies
9520 bytes (0x2530); it remains off the task stack. Setup retains the probe
function without calling it. Nothing was uploaded.

The first build failed because the probe retained both the old standalone
session and the new owner's session, overflowing its static DRAM region by
208 bytes. Removing the superseded standalone instance fixed the link, without
changing the owner's behavior or reducing its evidence buffers. Failure export:
`wizard-20260919T182416349855Z-e11b5db85f2d40c1af67f5153aa1a402`.

Inspection of the exact staged r22 sources identifies the required integration
points (not yet wired):

- `diagnostic_boot.h` runs only diagnostic polling and pose polling. Its setup
  does not call the legacy `webCtrlServer`, so the legacy `/js` handler is not
  registered by this boot. Preserve this separation.
- `diagnostic_http.h` contains the actual staged hold preparation entry point;
  editing only the similarly named public `configured_hold_routes.h` would not
  protect the staged image. Block hold preparation under shoulder reservation.
- `configured_pair_board_routes.h`: block pair preparation and the shared
  configuration-capture admission callback under shoulder reservation.
- `configured_recovery_board_routes.h`: block recovery preparation. Conversely,
  shoulder preparation must reject any previously attempted/active hold, pair,
  recovery or pose owner, rather than merely pausing an existing command stream.
- `pose_observation_board.h`: block pose reservation; do not interleave its bus
  reads with the shoulder session's acquisition.
- Replace the loop's scheduler branch for a reserved shoulder session: poll its
  owner and service its receipt/status HTTP surface on the same task, without
  polling old owners or pose acquisition. Keep the reservation after terminal
  failure/success; no automatic fallback to legacy or prior diagnostic owners.

The combined-image audit must verify these exact staged files and actual route
registration, not just public template files or a mock scheduler. Resource
headroom and scheduling with HTTP remain unproven until that integration build.

### One-use shoulder start integration candidate

Follow-up composition: `shoulder_session_owner.h` now owns the gate, receipt
verifier and resumable session with a common boot/command/scope. Before a valid
start, session access is null and polling does nothing. Activation performs no
servo I/O; receipt-gated progression begins only through explicit owner polling.
`application/shoulder_start_authorization.py` signs the canonical shoulder plan
offline using the existing start-envelope framing. It does not send requests.

The native/host bridge now enters through this owner using Python-generated
signatures verified with Windows BCrypt, followed by actual filesystem exports
and signed receipts. Ten tests passed (bridge, authorized-start and resumable
session suites), including real-signature rejection for tampering, wrong scope
and wrong command ID with zero simulated writes/broadcasts. The successful
simulated pair-hold still performs exactly two preloads and one pair-enable
broadcast. No hardware state changed. Remaining: wire the shared reservation
into every existing firmware dispatch path, expose reviewed start ingress,
compile the composed owner for ESP32 and review combined resources. These
simulation results do not establish physical clearance or prove a safe lift.

`shoulder_authorized_start.h` now reuses `StartEnvelopeGate` to authenticate
an exact controller-built `rocell.shoulder_start.v1` plan. The plan binds boot,
command and the explicitly approved PRELOAD_ONLY or PAIR_HOLD scope; it cannot
carry arbitrary targets or speeds. A separate admission callback remains required.
The activation callback receives that same scope and must only activate the
reviewed session, not advance it or send commands. Subsequent target writes still
wait for the session's exported-intent receipt and fresh feedback.

`ShoulderBusReservation` supplies a sticky single-owner reservation. Admission,
expiry or activation failure does not release it automatically. This is only
effective when every hardware dispatch path honors the same reservation on the
serialized control task; that actual firmware integration remains unfinished.
No start route is exposed and no hardware was accessed for this increment.

Validation: 7 tests passed across the new authorized-start test, resumable-session
test and native/host export-receipt bridge. Start tests cover success, scope
mismatch, occupied bus, rejected admission, initial expiry, expiry during
admission, failed activation and non-reusable attempts. The start unit test uses
a stub HMAC implementation for framing/ownership; it is not cryptographic proof.
The bridge tests exercise real receipt cryptography separately. Still required:
prove all dispatch paths respect the reservation and compile/review
the combined firmware before requesting a defined deployment/initialization scope.

### Initial synthetic implementation

### Shoulder grouped-enable packet investigation

The retained `SCS::syncWrite` accepts an arbitrary start address and byte width.
An **uninstalled candidate** in
`firmware/diagnostics/shoulder_enable_packet_candidate.h` forms one sync-write
packet forIDs12/13, address40, value1 each. A memory-transport test linked against
the actual retained `SCS.cpp` verified exact bytes
`ff ff fe 08 83 28 01 0c 01 0d 01 32` and no repeat transmission from the same
candidate object. It performs no reads and returns only SENT_UNACKNOWLEDGED,
never success/arrival. This proves packet construction, not device acceptance,
atomic physical activation, safe timing skew or matched shoulder loading.
The candidate is not part of r21, a firmware image or an exposed command route.
It must sit behind reviewed preload/freshness/admission checks before any native
integration; the helper alone grants no safe execution authority.

[Waveshare ST3235 documentation](https://www.waveshare.com/wiki/ST3235_Servo)
documents synchronized position writes and torque-lock operation. It does not
by itself validate this application's synchronized torque-enable and load-sharing
sequence. Local packet-source testing supplements but cannot replace device
verification. Never treat broadcast completion as two acknowledgements.

Current offset evidence gap: the installed configuration capture is explicitly
elbow14-only (`elbow_configuration_snapshot.h`). Saved elbow offsets/gains do not
explain shoulder12/13's20-count residual. Do not alter either shoulder offset or
apply a20-count correction based solely on the summed position readings. A new
bounded read-only shoulder-configuration capability is needed if those values
cannot be obtained through an already reviewed read-only interface.

The offline candidate `firmware/diagnostics/shoulder_configuration_snapshot.h`
now acquires a fixed34 reads:17 registers/blocks each on12 and13 (model, limits,
P/D/I, deadbands, offset, mode, torque, acceleration, goal, speed, torque limit,
lock and position-through-current feedback). It requires exclusive inactive bus
ownership, little-endian library mode, per-read validity and timing, and a finite
one-second sequence budget. The budget is checked between reads and on return;
the native bus timeout must still bound a stalled read. It is not atomic or a
stability test: every individual read retains acquisition timestamps.

It is single-use even on failure, retains partial evidence and clears invalid
payloads. Native tests inject short reads and servo errors at all34 locations,
loss of bus admission at every boundary, oversized read duration, total-budget
failure and incompatible byte order. The fake bus has only a Read method, proving
this component requires no mutating API. Tests passed; the component remains
uninstalled. JSON/host replay and candidate route integration are now implemented
as described below; actual shoulder measurements are still outstanding.

JSON/replay checkpoint: `shoulder_configuration_json.h` and
`application/shoulder_configuration_review.py` now complete the offline path.
A native read-only fake emits the actual JSON serializer output, which the host
validates, exports and independently replays. Tests reject wrong servo IDs at
every row, altered timing/status/byte fields and truncated captures; partial
captures remain inconclusive without usable configuration values. Simulation
origin is explicit. No calibration correction is inferred and the two captures
are never described as simultaneous. Native route integration/deployment and
real shoulder configuration measurements remain outstanding.

### r22 read-only route integration checkpoint

`scripts/stage_r22_shoulder_capture_candidate.py` verifies the r21 compile source
inventory before staging a separate candidate. It adds three shoulder headers
and modifies only the route-registration file. Existing movement code, startup,
settings and credentials are not changed. The grouped-enable packet candidate
is NOT integrated. Staging receipt:
`wizard-20260919T172205067206Z-b580e64722df4b86bf6a71c413ca670f`.

The added POST `/rocell/shoulder-configuration/capture` permits one fixed capture
per boot, rejects parameters and uses the existing inactive-bus callback,
including its pose-reservation restriction. GET
`/rocell/shoulder-configuration/result` retrieves retained bytes without servo
reads. Tests cover pre-capture retrieval, bus busy, parameter rejection,
all 34 read-failure positions, no repeat acquisition, and retained retrieval.
The combined route, host replay, packet, initialization-model and geometry suite
passed 19 tests. These are offline tests, not evidence of physical recovery.

r22 compiled successfully with the default 4 MB/no-PSRAM profile. Verified build
export: `wizard-20260919T172412279738Z-60d710244bc94554994cea79527eb2a3`.
Application SHA256:
`047beb3ac792a2c5f85c2b10138d0ca9bd47ae80359af7312138e56f0d132679`.
Compilation is not a deployment or hardware validation.

Offline compatibility review completed:
`wizard-20260919T172516138131Z-f0115efad48f4fd7b8b20ef60d7e96bb`.
The application fits the installed slot with 181,072 bytes remaining. Partition
and bootloader profile hashes match; original backup pair, original recovery
slot and retained r7 rollback artifact verify. The reviewer now includes shoulder
symbols: 187 relevant compiled frames, largest individual frame 432 bytes. These
are not worst-case call-chain bounds or live heap measurements. The focused
reviewer and native shoulder tests passed (3 tests). Current device bytes have
not been re-read, and deployment remains unauthorized.

Host transport is now implemented in
`application/shoulder_configuration_capture.py`: 8192-byte response budget
(the elbow client only permits 4095), fixed routes, one-attempt reservation,
durable intent and raw-response export before subsequent I/O, and retained-result
equality checking. It performs one POST and, only after valid complete evidence
and export, one GET. No retry, redirect, reset or motion path is provided.
Simulation origin requires an injected transport. Tests exercise response loss,
boot mismatch, invalid JSON, changed retained results, response limits,
truncation, redirects, duplicate attempts and export failure before POST/GET.
The combined focused suite passes 33 tests. No device capture was performed.

The entry point `scripts/run_shoulder_configuration.py` now binds its expected
boot through the r22 installation journal and startup response review. Its
`--preflight-only` mode performs no network access. Its separately authorized
observation mode rejects conflicting local capture/actuation reservations and
requires fresh same-boot idle status before calling the primitive. The primitive
alone does not establish installation provenance. The r22 profile pins the
actual 1,129,648-byte application, digest and candidate review. Launcher,
installation/startup and capture tests pass together (86 tests). No r22 install
journal or startup observation has been created; none may be fabricated to
satisfy this entry point.
Do not
send a request using the existing elbow client or silently repeat an uncertain
POST. Read shoulder configuration before pose reservation: the shared inactive
callback intentionally rejects new acquisitions once pose capture reserves the
boot. This ordering does not authorize later actuation on that boot.

Next hardware authorization scope: one reviewed r22 app-only installation and
one startup, preserving filesystem/settings/credentials, followed by one
read-only shoulder configuration capture and retained-result retrieval. No
hold, torque enable, gain/offset change, lifting or follow-on movement is within
that scope. The existing supported app-only installer must be bound to r22 and
the current predecessor before execution. This document records a proposal,
not approval. The controller reset/startup is not a homing operation and must
not be represented as mechanically inert merely because the diagnostic startup
code sends no servo movement commands.

r22 requires build review and explicit installation/startup/capture approval
before device use. Its new routes do not implement a lift or whole-arm hold.

### Synthetic preload/enable model

Session HTTP adapter checkpoint: `shoulder_session_routes.h` now supplies GET
status, GET retained record and POST authenticated export receipt for a session
provided by an authorized-owner accessor. Registration, reads and receipt
handlers never call `advance` or servo operations. There is deliberately no
prepare/start/reset/movement endpoint in this adapter. Missing sessions, wrong
request shapes, invalid receipt encoding and receipts outside the waiting phase
are rejected. Fault evidence remains retrievable. The route test plus full
offline session bridge pass6 tests. Native tests use a fake WebServer and session
for handler isolation; real cryptographic/session integration is covered by the
bridge separately. ESP32 WebServer compilation and combined-firmware wiring are
still outstanding, as are authorized session creation and exclusive ownership.
No route has been installed on r22.

ESP32 compile/link checkpoint: the compile-only probe now retains the resumable
session's native SMS_STS operations and Esp32StartCrypto receipt verifier without
calling them from setup/loop. Successful verified build:
`wizard-20260919T181208661717Z-c27a3e90ea6d44ab9e499442fa79964e`.
Symbol inspection confirms the advance implementation and receipt verification
are linked; the initial probe build was superseded because linker elimination
had removed an unreferenced function. The session object occupies8,776 bytes in
target static storage and must not be allocated on the control-task stack.
Probe image407,193bytes; total probe globals115,264bytes. These are probe-only
figures, NOT combined r22-plus-session application headroom or runtime guarantees.
No probe image was installed. Nine host/integration tests also passed this turn.

End-to-end offline checkpoint: `test_shoulder_session_bridge.py` connects a
native resumable PairHold session to actual host filesystem exports and Python
HMAC receipts, verified natively with Windows BCrypt. Every native record must
be exported before its receipt is returned. This replaces the receipt/digest
doubles for this integration test, while retaining an explicitly simulated bus
and clock. Successful flow includes two preload writes, one paired broadcast and
timed observations. Export abort, damaged preload receipt, damaged enable-intent
receipt and damaged post-enable receipt all stop at their respective boundaries
without subsequent actuator commands. A post-enable fault does NOT disable
torque or undo the partial state. No hardware or real controller key is used.

This test does not validate live timing, ESP32 heap/stack, HTTP handling,
mechanical behavior, current limits or endpoint clearance. Those limitations
remain before the next approved hardware initialization attempt.

Authenticated persistence receipts: `application/shoulder_export_receipt.py`
exports an exact UTF-8 event attachment, verifies the bundle and compares saved
bytes before issuing HMAC-SHA256. The124-byte domain-separated receipt binds
boot, command hash, sequence and exact event SHA256. If export redaction changes
bytes, signing is refused. `shoulder_export_receipt.h` verifies that format using
the existing standard-crypto adapter interface. Three tests pass, including
Python-to-native Windows BCrypt verification and alteration of every token byte.
No real controller key was read or used; tests use synthetic keys. The receipt
asserts persistence only, not valid motion or arrival. Native route integration,
key lifecycle, complete event-semantic replay and the host polling loop remain
outstanding before physical use.

Storage integration correction: existing `EvidenceStore` and
`HeldCompactEvidenceStore` retain evidence in RAM, not durable storage. A
successful `publish` cannot satisfy the new candidate's durable-export callback.
Do not wire those calls together and claim durability. No filesystem writes
have been added to work around this distinction.

`shoulder_export_barrier.h` now models the required pause/resume boundary:
retain one bounded record, bind its sequence and digest, wait for a verified
host-export receipt, and release exactly once. Replaced records, wrong sequence
or digest, invalid receipts, clock reversal and timeout fault without releasing.
The original pending bytes remain available for diagnosis. Tests pass with
explicit digest/verifier doubles; this does NOT prove cryptography or actual
host persistence. Four focused native/serialization tests passed.

Resumable preload integration is now implemented in `shoulder_preload_session.h`:
baseline, intent, write-result and verified-readback records each pause on the
export barrier. Every actuator step reacquires all-joint state after receipt
acceptance. No bus progression occurs while waiting; invalid receipts, timeout,
changed pose and uncertain write delivery stop without retry. Uncertain-result
bytes remain retrievable. The sequence has exactly two possible preload writes,
seven exported events and no torque-enable operation. Tests pass for a complete
sequence and these injected failures (5 focused tests together with barrier,
serialization and synchronous native tests).

The resumable owner now also supports an explicit `PairHold` scope. PreloadOnly
remains the default. PairHold adds enable intent/export, a fresh pre-enable scan,
one broadcast, sent-record export, verified readback and timed observation.
Every event pauses for its receipt. After enable, a receipt or scheduler gap over
500ms and a total observation window over3seconds terminate progression;
successful observation requires2seconds and at least5 timed samples. These remain
provisional test timing parameters, not manufacturer safety limits. Completion
requires receipt of the final observation; no lift or follow-on write is issued.
Tests cover complete scoped hold, partial enable, pre-enable drift, invalid
receipt and delayed receipt after transmission; the combined focused native
suite passes5 tests. Broadcast delivery is still unacknowledged, not a servo ACK.

Remaining integration: connect authenticated receipt verification and real host
export, then review native network/ownership integration. The session tests explicitly
use noncryptographic digest/verifier doubles. Neither this session nor its
barrier is installed, exposed on HTTP or granted hardware authority.

Native evidence checkpoint: `shoulder_hold_event_json.h` adds bounded,
boot/command/sequence-tagged event records, all-joint feedback bytes, requested
preload targets, write timing/return/device error and explicit PRE_ACTION versus
OBSERVATION labels. Pre-action snapshots must never be interpreted as post-write
readback. A sink failure latches and stops later publication/progression. A
terminal record distinguishes timed observation completion from not-attempted
or incomplete work; whole-arm readiness and lift authority are always false.
Native serialization and host JSON checks pass with preload/hold tests (3 tests).
The tested sink is memory-only, not durable storage. Actual controller persistence,
host export/replay and network admission remain to be connected before deployment.

Composed native candidate: `shoulder_hold_candidate.h` now joins the preload
primitive to the one-shot grouped-enable packet. It reacquires all seven joints
after durable enable intent, rejects drift/changed goals/torques, transmits once,
then performs three bounded readback scans with no subsequent actuator writes.
The outcome is named `SAMPLED_PAIR_HOLD_ONLY`, not whole-arm readiness or lift
clearance. Broadcast delivery remains `SentUnacknowledged` even when sampled
readback agrees; no per-servo acknowledgement is invented.

Offline tests cover dropped broadcast, partial enable, changed target, neighbor
drift, all 336 possible failed-read positions, all 12 export boundaries, drift
during intent export, admission loss and repeated invocation. Native candidate
tests pass. No deployment or physical enable has occurred. Actual feedback
timing, sustained load/effort monitoring, exclusive-owner admission and durable
record adapters remain required before this candidate is runnable on hardware.
Three immediate scans do not establish long-term holding or safe load sharing.

Timed observation extension: initial three-scan agreement now transitions to
`OBSERVING_PAIR_HOLD`, not completion. A nonblocking `poll` performs read-only
all-joint sweeps, nominally at least100ms apart, for at least2seconds and5samples,
with a3second observation ceiling. Scheduler/export gaps over500ms stop the
observation; these are provisional bounded test parameters, not hardware safety
ratings. Each sweep includes the full15-byte position-through-current block and
start/end timestamps. Changed goals, torque, >2count positional drift, nonzero
reported speed/moving, invalid reads, admission loss or export failure terminate
without another actuator write. Completion is `TIMED_PAIR_HOLD_OBSERVED` only.

Tests exercise successful timed observation, late drift, loss of one shoulder's
torque, nonzero speed, scheduler gaps, read failures and export failures. All13
focused native/model tests pass. Raw load/current, voltage and temperature are
retained but do not yet gate this candidate: validated scaling and reviewed
limits are still missing. Therefore a successful timed observation is not yet
sufficient admission for a lift. The candidate remains uninstalled, with no
network route or live bus owner; r22 on the device is unchanged.

Native preload checkpoint: `firmware/diagnostics/shoulder_preload_candidate.h`
implements a one-use, uninstalled two-write primitive. It reads all seven joints'
mode, torque, goal and position before action; requires passive shoulders and
already-enabled joints within two counts of their goals; preserves the measured
shoulder targets individually. It reacquires after intent export and verifies
goals, torques and neighbor positions after each `WritePosEx`. It does not
include or call the grouped-enable helper. There is no HTTP route or deployment.

Native memory-bus tests cover every one of 196 possible failed read locations,
all seven export callbacks, lost write acknowledgement, wrong goal readback,
unexpected torque, neighbor drift and repeated invocation. Each stops further
writes, without rollback or torque-off. This is native control-flow evidence,
not proof of physical preload semantics or safe contact release. Evidence and
admission callbacks still require integration with an exclusive controller owner,
durable export, actual bus timeouts and command-correlated records before use.

`application/upright_initialization_sim.py` now rehearses preload of all passive
targets before any enable; already-enabled joints retain their original goals.
It preserves the measured shoulder-pair residual rather than forcing mirrored
targets. The simulated enable groups shoulder12/13 and verifies both before
continuing. This is an explicitly abstract group operation, NOT an implemented
atomic bus instruction or demonstrated mechanical safety. No transport exists.

Fault cases cover preload acknowledgement loss, wrong target readback, unexpected
torque during preload, pre-enable drift, partial shoulder enable, enable
acknowledgement loss, neighbor movement and export failure. They stop with the
partial resulting state, without compensating writes, retry or torque-off.
Together with the route preview,16 tests passed. Timing, real electrical skew,
load dynamics and contact release are not simulated by this first model.

Local library review: `SCServo/SMS_STS.cpp` writes7 bytes starting at41 for
`WritePosEx` (acceleration, goal, zero time, speed); torque40 is outside that
payload. `EnableTorque` separately writes40. This establishes library packet
contents, not physical ST3235 behavior under load. `SyncWritePosEx` returns void
and uses broadcast; do not claim acknowledged simultaneous enable from it.
`RegWritePosEx` queues position data for a separate action; it does not implement
the abstract torque-enable group. Native strategy and readback remain to be
designed and verified before installation is requested.

- Installed r21 is elbow-only: it cannot perform this sequence. Do not route
  around that limitation through stock startup or generic homing.
- Build host/native contracts for multi-joint target preload, enable and bounded
  steps. Test stale target, changed pose before enable, shoulder disagreement,
  partial enable, missing acknowledgement, neighbor drift, contact not cleared
  and failed export. Test that no subsequent write follows failure.
- Review source/build and preserve backups before requesting deployment approval.
- If powered initialization cannot safely establish load-bearing holds, explain
  the specific failure and required assistance. Do not demand padding merely
  because previous tests used supported-recovery terminology.

Status: offline kinematic route comparison implemented; full-arm initialization,
contact-release validation and hardware recovery remain unimplemented/unverified.
