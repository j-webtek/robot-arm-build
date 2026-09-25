# Elbow tracking experiment after r13 non-arrival

## Purpose and established evidence

Determine whether fresh encoder response depends on direction, displacement or
approach history before fitting compensation. Preserve the existing definition
of arrival: two valid stationary samples within two counts of the requested
target. A plateau outside that band is a measured non-arrival, not a pass.

The r13 test requested 2901 -> 2907. Goal readback was 2907; position plateaued
at 2902, signed error -5. r14 configuration reads found both deadband registers
zero. This does not establish the cause or a universal five-count correction.
Sources and exports are indexed in COMMAND_TO_SERVO_DIAGNOSTICS_PLAN.md.

## 1. Recover admission deliberately, not by retrying

No failed pair is to be resent. No automatic reset, torque release or return.
The last observed goal/position gap was five counts; those are historical values,
not a fresh r14 position. The ordinary hold guard allows only two counts, so it
must not be bypassed or silently widened to start a new experiment.

Proposed separately authorized operation: while the arm is supported, acquire
complete fresh stationary scans, then issue at most one hold target equal to the
freshly measured elbow position. Preserve other joints' targets and torque states.
Keep torque enabled; do not mechanically reposition or calibrate the servo.
The requested target is not an old anchor, the missed destination, or an overshoot.
Even this operation can physically move the actuator and needs explicit recovery
authorization plus a reviewed implementation before live use.

Implementation must separate the allowed *initial residual* for this one recovery
from normal drift and final arrival tolerances. Neither neighbor drift nor arrival
tolerance increases. Require a reviewed bound for the initial residual, fresh
readback, no moving flag, unchanged baseline and valid ACK. A failed hold stops;
there is no attempt loop. Existing r14 firmware has no such recovery admission.
Firmware deployment and any settings provisioning require separate approval.

## 2. Freeze an experiment from the new verified anchor

Use fresh verified anchor A, not a hard-coded assumption of 2901/2902. Keep the
current elbow envelope [2893, 2909], speed 20 and acceleration 1 initially.
Check both target and return against the envelope before admission.

| Stage | Requested motion | What it tests |
| --- | --- | --- |
| First direction | A -> A-6 -> A | Whether negative travel and its return can arrive |
| Matched direction | A -> A+6 -> A | Direction dependence at equal displacement |
| Second magnitude | A -> A-8 -> A, then A -> A+8 -> A | Whether residual changes with displacement |
| Repeatability | Repeat eligible matched pairs, maximum three per direction | Whether an apparent bias repeats |

Each arrow is independently assessed/exported. Return is allowed only after a
verified forward endpoint. A non-arrival halts the sequence and does not authorize
the next direction or a return. Future recovery is explicit, not scheduled as an
automatic part of the experiment.

Magnitude eight is eligible only when both endpoints fit. For example, A=2901
allows 2893 and 2909; A=2902 does not allow the positive eight-count target. Skip
that matched magnitude rather than clipping a target or widening the envelope.
Do not call different displacements a matched direction comparison. A broader
envelope or deliberate recentering is a later separately reviewed experiment.

## 3. Retain the data needed to learn

For every attempted leg export the exact software/firmware identity, boot, plan,
policy, requested target, encoded payload, ACK, target-register readback, sequence
and timestamps, and all seven joints' fresh positions/mode/torque/moving flags.
Also retain available speed/load/current and raw voltage/temperature bytes.

Report commanded delta, measured delta, final signed error, settling time when
verified, whether the endpoint plateaued, and why progression stopped. Never infer
arrival from command acceptance or moving=0 alone. Include non-arrivals in the
analysis; do not silently drop them from a success-rate calculation.

## 4. Decide what adjustment is supported

- If goal readback differs from payload, investigate command/readback handling.
- If payload and goal agree but position plateaus, compare residual against
  direction, displacement, load and history; do not label the cause prematurely.
- If position is still changing at the deadline, consider a separately reviewed
  observation-duration test without changing the success band.
- Fit no compensation from one failure. First demonstrate repeatable residuals
  in both directions, then reserve distinct trials as held-out validation.
- A candidate correction must reduce held-out endpoint error without causing
  unexpected direction, overshoot, neighbor movement or envelope violations.
- Encoder-count validation is not physical stylus-tip accuracy. Camera/board and
  tool registration remain necessary before contact typing or phone tapping.

## Current next action

User approved the proposed supported recovery on 2026-09-19. This covers one
hold targeting a freshly measured position after reviewed implementation; it
does not approve a firmware deployment, provisioning, servo-setting change or
automatic repetition. No recovery command has been sent.

The offline native candidate uses an explicit `SupportedRecoveryAdmission`
constructor, not an expanded ordinary hold policy. Its initial residual ceiling
is five counts, based on the observed discrepancy, checked at every prewrite
scan. Both current position and old goal must fit the configured envelope.
Torque must already be enabled and remain enabled; explicit enable is forbidden.
Speed remains 20, acceleration 1, drift and arrival remain two counts. Three
fresh stationary baseline scans precede one write to the latest measured position;
two stationary post-write scans must validate readback and arrival. Existing
timing, neighbor and ACK guards remain in force.

Boot/operation-bound admission and host recovery replay are now tested offline.
Host prepared-start/signing and loopback sending are now tested as well.
Native listener composition and bounded recovery collection are now tested.
Next wire the board-level recovery route and receipt-bound launcher, then
review a new candidate build. Installed r14 is
unchanged and has no recovery route. Deployment still needs separate approval.
Do not run another ordinary pair merely to rediscover the initial-tracking guard.

Authenticated runtime increment (offline): the native runtime now has an explicit
recovery specialization. It consumes a one-use authenticated
`rocell.supported_recovery_plan.v1` bound to boot, command identity and the hash of
`rocell.supported_recovery_policy.v1`. That policy wraps the unchanged hold policy
and the five-count initial residual limit. An ordinary hold token cannot authorize
recovery, nor can a recovery token authorize an ordinary hold. Authorization,
snapshot, action and terminal records use separate `rocell.supported_recovery_*`
schemas and retain plan/policy hashes. Recovery never yields an automatic pair
handoff. No settings parser, installed route, or deployment was changed.

Real-HMAC host/native tests verify valid recovery, wrong schema/boot/command/policy,
simulation-origin substitution, corrupted signatures, expiration, duplicate starts,
failed reservation/publication, prewrite admission loss, and lost ACK. The first
compile exposed a forward-declaration mismatch; it was corrected and all five
focused recovery/ordinary-admission/allocated-runtime pytest cases passed.
Remaining before candidate review: separate native transport/route integration,
receipt-bound live launcher/collection, and a complete ESP32 build. The retained controller
records alone do not establish durable host export or hardware success.
Broader regression also passed: eight cases covering native snapshots/recovery,
configuration parsing, and authenticated forward/return runtimes in direct,
socket and powered synthetic modes (63.08 seconds). Combined this increment ran
13 passing pytest cases; native cases each exercise multiple injected scenarios.

Host replay increment: `supported_recovery_review.py` validates the independent
plan/policy hashes and recovery-only schemas, then replays the actual native
producer's records through a recovery-aware model. Ordinary hold behavior remains
unchanged. Recovery demands exactly three baseline scans, one target write, two
post-write scans and a terminal record, in order. The old goal must be inside the
envelope; initial residual stays <=5, torque stays enabled, and arrival/drift stay
<=2. Command payload must encode the latest prewrite position. Post-write dwell,
fresh acquisition validity, ACK and neighbor checks are verified independently.

`export_recovery` retains source records, independent subject and assessment;
`replay_recovery` verifies the manifest and recomputes the assessment. Invalid or
failed records can still be exported as INCONCLUSIVE without endpoint claims.
SIMULATION and controller-reported acquisition are explicitly distinct; neither
establishes independently authenticated provenance, physical tip accuracy or
permission for another movement. No network or device access exists in this module.

Validation: 30 pytest cases passed (10.67 seconds) spanning actual native recovery
records, ordinary authenticated hold replay, recovery/ordinary state models and
native snapshot/hold cores. Mutations cover schema/identity mixing, wrong payload,
uncertain ACK, excessive residual, changed goal, out-of-band endpoint, torque loss,
device error, record order/count, incomplete/faulted terminal and export tampering.
No firmware was built or installed and no live recovery was performed this turn.

Prepared-start increment: `supported_recovery_start.py` freezes a distinct recovery
plan, validates exact approved policy/boot and signs the existing authenticated
start envelope. Its bytes match both independently generated HMAC test fixtures
and native recovery admission. The sender uses one connection and one request,
with no retry/fallback. It uses the existing dedicated listener's POST path, not
a legacy movement endpoint; the future native recovery listener must explicitly
instantiate the recovery runtime before this client can be used on hardware.

Before invoking any sender, the workflow exports/reopens its plan, policy and
challenge, then durably consumes the boot/nonce claim shared with ordinary start
paths. An uncertain reply or failed post-send export never refunds that claim.
Reports distinguish controller acceptance from endpoint verification, and contain
neither signing keys nor request tokens. No automatic wizard action or live CLI
was enabled. Caller-side deployment/recovery authorization remains required.

Validation: 29 tests passed (3.50 seconds), including localhost-only accepted,
rejected, lost and contradictory responses with exact-token/no-resend assertions;
pre-export/reservation/post-export failures; plan/boot/type/policy rejection;
duplicate preparation; and host-signed tokens verified by the native runtime.
The initial byte-for-byte export check rejected exporter formatting; it now
strictly decodes and compares canonical JSON, matching the existing hold path.
No arm connection, firmware installation, provisioning or servo command occurred.

Native listener increment: explicit recovery specializations of
`AllocatedHoldRuntime` and `ConfiguredHoldRuntime` retain the existing one-shot
HTTP parser and bounded allocations. Invalid recovery policy is rejected before
allocation. Ordinary persisted hold configuration cannot initialize recovery;
the board integration must explicitly supply the reviewed policy. Outer status
and record envelopes use `rocell.supported_recovery_transport.v1` and
`rocell.supported_recovery_record.v1`. Readout performs no servo reads/writes.
Failed recovery-to-pair handoff retains all recovery evidence and grants no move.

`collect_recovery_snapshot` accepts only those schemas, at most 12 records, and
stable same-boot terminal status before/after collection. Recovery CAPTURED requires
exactly eight records. It retains partial raw responses on error, never retries,
and does not itself assess endpoints. Ordinary collectors reject recovery records.

The native configured-listener harness exercises successful signed recovery,
both allocation failures, listener-start failure, truncated connection, expiry,
interference, and rejection of ordinary configuration. Host tests consume its
actual emitted records, verify endpoint replay/export, inject failure at all ten
collection reads, and reject a changed final boot. This is scripted network/bus
evidence, not an installed board route or live recovery. The first harness compile
had a nested-main fixture collision; a test-only include guard corrected it.
Combined regression: 24 pytest cases passed in 12.55 seconds across configured
recovery, prepared sending, authenticated recovery, ordinary allocated/listener
runtime and native snapshot/hold cores. No device was accessed.

Dedicated HTTP surface increment: `configured_recovery_routes.h` defines explicit
POST `/rocell/recovery/prepare` and read-only status/record routes. Registration
does not prepare, load settings or move. Preparation is consumed before calling
the injected board callback, including failure; subsequent attempts are refused.
Extra parameters and malformed/out-of-range record indices are rejected. Readout
is refused during exclusive acquisition, and serialization failure faults the
runtime rather than causing a retry. Buffers are owned by the route object, not
large per-request stack arrays.

The recovery collector and `RecoveryHTTPReader` now use those dedicated paths,
rejecting ordinary hold endpoints. Native route tests use fake WebServer/runtime
objects; the configured-listener test still supplies real emitted recovery JSON.
Remaining board work is concrete: provide the preparation callback that reserves
mutual exclusion with ordinary hold/pair challenges, checks retained settings,
loads the existing key, initializes the recovery-only listener and serializes its
finite challenge; include recovery in the single-owner poll/interference paths.
Do not expose the route on hardware before that wiring and a full build review.
Validation: 15 pytest cases passed in 10.26 seconds, including recovery path/budget
rejection and fault latching before network access, native route tests, configured
recovery collection/replay, and ordinary allocated-runtime regression. No device
was contacted, and installed r14 remains unchanged.

Board wiring increment: `configured_recovery_board_owner.h` adds an uninitialized
recovery runtime alongside hold/pair. `configured_recovery_board_routes.h` supplies
the preparation callback and route instance. Before file access it reserves
recovery, refusing prior ordinary hold challenge/configuration, non-new pair state
or owner fault. Ordinary hold challenge creation refuses a recovery reservation.
Thus the shared port cannot be claimed by both paths in the single-thread owner.

The callback reads existing `/rocell-hold.json` and `/rocell-hold.key` only. It
requires the exact reviewed source command, port, seven joint windows, timing,
speed and tolerances; no broad default is substituted. It derives an enabled-only
policy (explicit enable false), uses command `r15-supported-recovery`, generates
one ten-second challenge and wipes its local key copy after initialization. It
does not read or write servos. Preparation failures consume the attempt; no reset
or settings provisioning is implied. Recovery is included in interference and
configuration-capture exclusion checks.

`diagnostic_recovery_boot.h` preserves the no-motion startup behavior and calls
the hold/pair/recovery polling loop. Web handling is withheld during any runtime's
exclusive acquisition. The original boot source and immutable previous build
directories remain unchanged. These source files still need explicit mapping into
a fresh r15 candidate; they are not part of the installed r14 image.

Validation: 15 pytest cases passed in 7.98 seconds. The actual preparation callback
ran through 12 inert filesystem/state cases; ordinary hold rejection after recovery
reservation and recovery rejection after ordinary admission were tested. The
actual recovery boot header ran seven startup/failure cases with no servo-write API
available; loop tests covered all three exclusive runtimes. An initial fixture
failure used pretty JSON rather than the canonical provisioned bytes; corrected
the fixture, not the strict parser. No device access or firmware installation.

Next: stage the changed source set against immutable r14, compile/review the full
ESP32 image, and finish the receipt-bound recovery launcher/transport export.
Deployment remains separately approved; a passing offline board test is not a
live recovery result or authority to repeat a failed movement.

Full-build staging checkpoint: r15 staging retained 87 predecessor files and
mapped/added 15 files. The full compile failed because generated `diagnostic_http.h`
omitted its final include of `configured_pair_board_routes.h`; the component tests
had not covered that generated-file boundary. No app artifact or deployment
result was produced. Failed sources and export are preserved:
`wizard-20260919T113124085151Z-8d7590b10b994175a9195218a0c3b3a4`.

The corrected source set is staged separately as r16 from verified immutable r14,
not over the failed r15 directory. Stage export:
`wizard-20260919T113235844266Z-6176c2a627834905b1321f3f5387d752`.
The operation identifier remains `r15-supported-recovery`; it identifies the
reviewed recovery operation, while the image revision will be r16. Host plans must
use that exact operation identifier and independently bind the installed image.
New generated-wiring checks cover the missing include and guarded hold challenge.
Combined recovery/ordinary-hold regressions passed: 39 pytest cases in 19.73 seconds.

r16 full ESP32 build and offline artifact review succeeded:

- Compile export: `wizard-20260919T113420406745Z-1e5770617ccf427094e4960eacaf93df`.
- Review export: `wizard-20260919T113432413777Z-e84ef889a4df40b8bb58f3fdc2a7c827`.
- App SHA-256: `dc8b6f0016d29495ef6403d6a04adcbc192ec45ccd1ede7c390c3d1b4b3ea05e`.
- App size: 1,120,240 bytes; slot headroom: 190,480 bytes, default 4 MB/no PSRAM profile.
- Partition and bootloader hashes match the reviewed predecessor profile.
- Source/artifact hashes and retained original backup/recovery artifacts verified.
- 157 relevant disassembled function frames inspected; largest individual frame
  432 bytes. This is NOT total stack, runtime heap qualification, or live health.

No deployment, startup, filesystem provisioning or device connection occurred.
Installed r14 remains unchanged. Next finish receipt-bound installer/observer and
recovery launch/collection/export integration before requesting app-only deployment
approval. The full diagnostic/motion objective remains incomplete.

Installer/collection checkpoint: r16 is now a pinned installer edge from r14
(never from failed r15), with an independent `app-r16-deployment-events.jsonl`
one-use journal and unchanged pair-settings filesystem expectations. Installation
receipt verification and the startup observer recognize only the exact reviewed
r16 image. Neither local receipt validation nor startup observation authorizes
movement. Installer/receipt tests: 41 passed in 1.16 seconds.

Executed `deploy_reviewed_diagnostic_app.py --revision 16 --preflight-only`:
LOCAL_PREFLIGHT_VERIFIED, image 1,120,240 bytes, expected predecessor r14,
expected filesystem SHA-256
`a5ca3cc090277da8952fec21ebc1b84d692819515fb9a9a3550c56539b7a4096`.
This was local artifact verification only: no journal reservation, serial open,
reset, firmware write or deployment authorization.

Recovery transport now has exact-response-byte export/replay including receive
failures. It establishes the export destination before GETs, retains ordered
response paths/bytes/digests, and replays the same collector without network.
Recovery exports cannot be replayed as ordinary hold exports. Missing/mixed paths,
changed digests, extra responses and forged summaries are rejected. Partial capture
at each of ten read boundaries exports/replays as INCONCLUSIVE without retrying.
Ten configured-recovery/ordinary-runtime tests passed in 9.62 seconds.

Remaining before the live recovery attempt: receipt-bound launcher that checks
the observed r16 boot and installation, issues one explicit recovery preparation,
sends one signed hold, collects/replays telemetry and links all exports. Separate
app-only installation/startup approval remains outstanding. No hardware accessed.

Launcher implementation checkpoint: `run_supported_recovery.py` now offers local
preflight and explicitly authorized one-shot execution. It requires the exact r16
installation receipt and startup export, validates retained startup response bytes,
hashes, order, idle state and same-boot capabilities, checks private key-source
image identity/ACL, and loads the key only for authorized execution. Historical
receipt checks are not claims of current device bytes or permission to move.

The coordinator additionally captures fresh idle status and same-boot capabilities,
exports its plan/binding and reserves the boot attempt before one recovery prepare
POST. A valid same-boot challenge permits one signed hold send. It waits the finite
hold deadline plus one second, collects recovery records, exports/replays raw
transport and endpoint assessment, and retains links in the trial result. An
uncertain send can be followed by read-only collection, never a retry or another
motion; the overall trial cannot be verified on uncertain delivery. Preparation,
delivery or export failure consumes the attempt. Partial records remain available.

Validation: 33 tests passed in 4.87 seconds for strict startup response binding,
injected coordinator phases/failures, and real localhost challenge transport,
including recovery operation identity and duplicate refusal. Coordinator tests
inject device boundaries; they are not a physical trial. CLI `--help` passed.
No arm connection, firmware installation or recovery motion occurred.

## Next authorized operating sequence

### Live recovery result — 2026-09-19 11:50 UTC

Steps 5–6 below completed once on the installed r16 boot
`c23f5bdf087bb87f4fa423c1dac183e1`. Trial export:
`wizard-20260919T115015927901Z-7951824ace2d40b5aa493875846f317d`.
Assessment export:
`wizard-20260919T115015864147Z-8e3d7b19213e46e4ae60d2b8be130c63`.
The linked intent, baseline, challenge, delivery, raw transport and assessment
exports were retained and replayed by the launcher. Result:
`CONTROLLER_REPORTED_RECOVERY_VERIFIED`.

- Three fresh baseline scans preceded one elbow hold command. Previous goal was
  2907; measured position and requested hold target were 2902 servo counts.
- Pinned-library command encoding was `01560b00001400` (acceleration 1,
  target 2902, speed 20). Library return was 1 with enabled ACK and device error 0.
  This is instrumented library evidence, not an independent wire capture.
- Two fresh post-command scans reported goal 2902 and position 2902. Final
  observation was 225613 microseconds after command completion. Settled error 0.
- Elbow torque remained enabled; no explicit torque enable was issued. Other
  joints reported zero position change and no goal or torque changes.
- This was a successful hold/target reconciliation, **not verified travel**:
  start and final position were both 2902. It does not resolve bidirectional
  tracking, prove a compensation model, or establish stylus-tip accuracy.
- One action and five scans were recorded. No retry, reset, installation,
  servo-configuration change or follow-on pair occurred during this trial.

Next: resume the ordinary hold-to-pair route from a separately approved startup
of the existing r16 image, after reviewing this evidence. The current recovery
runtime deliberately cannot issue a pair handoff and its attempt is consumed.
Do not clear that reservation or repurpose its receipt as ordinary hold authority.
No new firmware is inherently needed for this transition; check host revision
compatibility before requesting the startup. After fresh ordinary hold verification,
derive a bounded matched-direction experiment from the new measured anchor (not
this historical 2902). At anchor 2902, proposed ±6 targets would be 2896 and 2908,
both within 2893–2909; these are planning values, not authorized commands. Stop
on the first uncertain delivery, invalid evidence or failed endpoint; never send
an automatic return after a failed outward leg.

Host compatibility check: `run_hold_r10.py` currently accepts revisions 10–13,
and `run_reviewed_r13_pair.py` pins the historical r13 boot/preparation and anchor
2901. Neither is a valid r16 launcher as-is. Next software work is receipt-bound
r16 ordinary hold/pair launch support using an explicitly supplied fresh startup
export, with offline stale-boot/recovery-receipt rejection tests. Do not merely
change a revision number or reuse those historical preparation constants. Prepare
and test this host path before asking for another startup; deployment is separate.

Host implementation checkpoint: `scripts/run_r16_hold.py` now accepts an explicit
`--startup-export` and either `--preflight-only` or `--authorized-powered-hold`.
`r16_hold_launch.py` reuses strict r16 installation/startup response validation,
pins the unchanged ordinary hold configuration, rejects any same-boot ordinary
hold or recovery claim, and exports/reopens its binding and configuration before
delegating once to `run_first_hold`. That existing runner checks fresh same-boot
idle status, durably consumes the attempt before challenge discovery, and retains
its finite observation/no-retry behavior. The CLI verifies the retained private
key-source image and ACL before extracting the key only in authorized live mode.
It never resets, installs, provisions, executes a pair or changes servo settings.

Validation: 25 tests passed in 2.34 seconds across the new launcher, strict startup
binding, and existing first-hold runner. Tests cover consumed ordinary/recovery
boots, changed policy, approval refusal, startup/export failures, no retry on
delegated failure, and unchanged ordinary tolerance/enable policy. Device I/O is
mocked. The actual retained r16 boot is correctly rejected by local preflight
because its recovery attempt is consumed; no hardware access was made. Remaining:
fresh-receipt-bound pair preparation/launch support, then separately approved
startup of the existing image and the bounded live experiment.

Pair binding checkpoint: `r16_pair_launch.py` now composes existing ordinary-hold
replay, pair preparation and finite execution. It binds startup and preparation
to the same r16 boot, pins the unchanged hold policy and installed pair command
IDs/+6 offset/2-count tolerance, rejects recovery and consumed pair boots, checks
fresh captured ordinary hold state, and exports/reopens admission before calling
the existing evidence-gated two-leg runner. Failed forward evidence prevents a
return; there is no retry/reset/recovery branch. The native fresh handoff remains
required; saved coordinates alone do not authorize motion.

Compatibility correction: installed `/rocell-pair.json` fixes outward offset +6.
The return leg supplies negative-direction travel back to the anchor, but a -6
outward trial from that anchor requires separately reviewed/approved settings.
The new host rejects -6 rather than submitting a plan the firmware cannot accept.
No settings changed. The full matched-direction experiment is therefore still
pending; this does not redefine it as one outward/return pair. Forty offline
tests cover the new pair/hold wrappers and existing finite pair runner, including
stale boot, altered policy/targets, consumed attempts, export failure and no retry.
No hardware was accessed in this implementation step. Remaining before live use:
CLI/key-loading adapter for pair preparation/execution and a separately approved
startup of the installed r16 image (no reflash needed).

### Runnable r16 host sequence

The pair adapter `scripts/run_r16_pair.py` is now implemented. Forty-two tests
passed in 6.41 seconds across CLI mode isolation, r16 admission, and the existing
finite pair runner. Preparation performs no private-key access. Preflight verifies
the retained key-source image/ACL without extracting a key or opening hardware.
Only explicitly selected live mode extracts a key and delegates to the bounded
runner. Invalid/mixed CLI modes and changed private-image identity stop locally.
These are offline tests, not new physical movement evidence.

Next hardware authorization needed: **one startup of the already installed r16
application**, no flash/provisioning/configuration writes. Current boot's recovery
attempt remains consumed. Do not use the legacy USB-only restart script while
external power is on: its declared preconditions do not match this setup. Review
the restart mechanism for the actual supported/powered setup before executing it;
do not treat startup approval as permission to reflash or change servo settings.

After the separately approved startup, run the following from the workspace root.
Replace placeholders with the exact export IDs produced by the preceding step;
never copy historical boot IDs or assume a successful endpoint from a process exit.

1. Read-only startup export:
   `.\.venv\Scripts\python.exe software/scripts/observe_r10_startup.py --revision 16`
2. Ordinary hold local preflight:
   `.\.venv\Scripts\python.exe software/scripts/run_r16_hold.py --startup-export <STARTUP> --preflight-only`
3. Under bounded powered-test approval, execute once with the same startup ID and
   `--authorized-powered-hold`. Review the resulting observed-hold export; only
   `CONTROLLER_REPORTED_HOLD_VERIFIED` with stable status can support preparation.
4. Offline pair preparation:
   `.\.venv\Scripts\python.exe software/scripts/run_r16_pair.py --startup-export <STARTUP> --hold-export <OBSERVED_HOLD> --prepare-only`
5. Local pair preflight:
   `.\.venv\Scripts\python.exe software/scripts/run_r16_pair.py --startup-export <STARTUP> --preparation-export <PREPARATION> --preflight-only`
6. Under bounded powered-test approval, execute once using the same IDs and
   `--authorized-powered-pair`. This permits one +6 outward leg and a return only
   after software-verified outward arrival and retained exports. No recovery or
   automatic resend on failure. Review requested/encoded target, ACK, fresh target
   register and measured position for each actual leg; record skipped legs as
   skipped, not failed physical motion. Preserve all linked exports.

No startup or hardware command was performed while implementing this adapter.

### Approved live r16 test — 2026-09-19 12:00 UTC

User approved one startup, one verified hold and one +6/conditional-return pair.
One controller EN reset was sent with external power retained, after replaying
and comparing the completed recovery records to a fresh read-only capture.
No flash/filesystem/servo configuration write occurred. New stable idle boot:
`c82c94bd9a12a83fb620a5cfc6bca1a0`.

- Startup: `wizard-20260919T115938942331Z-41a2b11eb5664c30a09373bc67769953`.
- Ordinary hold: `wizard-20260919T115951996570Z-c11ac4bc62b849c28184edb8a6d14901`.
  Fresh anchor 2901, requested/encoded/readback/settled position all 2901,
  zero endpoint error, torque already enabled, no neighbor position change.
- Pair preparation: `wizard-20260919T120001353465Z-1b4982887ee7470995db4248b3ca0a96`.
- Trial: `wizard-20260919T120021188160Z-4befb9effa234a579f5ada45b6ff1e78`.
- Forward observation: `wizard-20260919T120021017760Z-f97ffa5f4b2d41148e0444cec35c5de2`.

Result: **CONTROLLER_REPORTED_NON_ARRIVAL**. Requested and encoded target 2907;
first and final goal-register readback 2907; starting position 2901; final
position 2902; observed change +1; signed endpoint error -5 counts. Twenty-one
scans were captured, with the final observation 2033662 microseconds after the
command. Stable controller state STOPPED and original reason LEG_NOT_ARRIVED
were retained. Return was withheld (not attempted), with trial reason
FORWARD_ENDPOINT_NOT_ELIGIBLE. No retry, recovery or additional reset was sent.

This reproduces the earlier r13 2901-to-2907 shortfall on r16, while showing that
the requested target reaches the servo's goal register. It narrows the remaining
issue to tracking/response rather than a demonstrated host target-encoding error;
it does not yet identify the mechanical/control cause or justify a universal
+5-count compensation. Next is offline comparison of both complete traces and a
bounded parameter/direction experiment proposal. Any further recovery/startup or
settings change requires its own approval; do not reuse this consumed attempt.

### Paired trace comparison and next discriminating experiment

Offline comparison export:
`wizard-20260919T120223491321Z-7bff50e8761345408585a903348dea62`.
`scripts/compare_elbow_forward_trials.py` replays each source's complete evidence
chain, retains both decoded traces and comparison, and reopens its export. No
network access or tuning. Summary unit tests cover contiguous final plateaus and
exclusion of precommand observations.

| Measurement | Earlier r13 trial | Current r16 trial |
| --- | --- | --- |
| Start / requested / final counts | 2901 / 2907 / 2902 | 2901 / 2907 / 2902 |
| Encoded payload | 015b0b00001400 | 015b0b00001400 |
| ACK / device error | 1 / 0 | 1 / 0 |
| Post-command samples | 18 | 18 |
| Final observed plateau begins | 555806 us | 442888 us |
| Last sample begins after ACK | 2024753 us | 2024805 us |
| Reported load range (library units) | -53 to -45 | -53 to -45 |
| Reported speed range (sampled) | 0 to 0 | 0 to 0 |
| Raw voltage range | 121 to 121 | 121 to 121 |

Interpretation: two trials reproduce the endpoint shortfall with target-register
agreement. There is no demonstrated host target-encoding discrepancy in these
trials. The long observed plateau weakens a simple early-observation explanation,
but does not prove that no later movement could occur. Sampled zero speed does
not prove no brief movement between samples. Raw load/voltage are not calibrated
force or supply-integrity measurements. No mechanical/control cause is proven.

Next proposed live experiment changes **direction only**: after separately
authorized recovery and startup, establish a fresh ordinary hold, use an outward
offset -6 at speed 20/acceleration 1/tolerance 2, and condition return on verified
arrival. At the last measured 2902 this would target 2896, but fresh measurements
must determine the actual target. Keep the existing 2893–2909 envelope. This needs
separately approved pair-settings provisioning; do not submit a -6 plan to the
currently installed +6 settings. Preserve original settings and recovery images.

- If negative travel arrives but positive travel repeatedly falls short, gather
  direction-specific repeats before modeling compensation.
- If both directions fall short, compare signed residuals and transient evidence;
  propose one bounded speed change next, not simultaneous speed/offset/tolerance
  changes or servo gain writes.
- Do not apply +5 counts globally: two repeats at one pose and one direction do
  not establish a transferable model. Held-out targets/directions remain required.
- Any failed leg terminates that sequence. No automatic return, recovery, reset,
  tolerance widening, or cumulative target nudging is authorized by this proposal.

Offline direction-change preparation: public settings draft exported as
`wizard-20260919T120433976427Z-eaabab0f3576487e832ec0efa4769096`.
Settings SHA-256:
`471898fe914f0843bdd88556b98aa1277c29d672c628df5892bd5bd849a8f314`.
Only offset changes from +6 to -6; both command IDs and tolerance 2 remain intact.
This is a public settings hash, **not** a deployable filesystem-image hash.

`replace_pair_direction_image` now supports exact prior-image/prior-settings
validation and a direction-only offline replacement. It requires native validators
and preserves the hold configuration, key and every other file, then remounts and
verifies the resulting image. Eighteen tests passed in 2.81 seconds for this path
and existing settings staging/encoding, using synthetic credentials and images.
Only `/rocell-pair.json` was written in the successful synthetic replacement.
Wrong source/prior/hold/key, rejected parser, altered magnitude or command IDs fail.
No actual private image has been staged, no controller connection occurred, and
no installed settings changed. The current r16 launcher still correctly rejects
negative plans until a new installed-settings receipt is supported.

Next approval boundary: offline private candidate staging only, using retained
verified source and this exact public settings draft, preserving credentials and
all other files. Review its exact candidate hash before separately approving any
filesystem-only installation/startup. Recovery from the current stopped pair is
also separate; this draft does not authorize it.

Staging CLI prepared: `scripts/stage_negative_pair_settings.py` requires
`--authorized-offline-private-staging` before any private image access. It checks
r16 installation receipts, public source/proposed policy hashes and pinned parser
headers, compiles native validators, derives a direction-only candidate, and
publishes it exclusively to current-user DPAPI storage with a public review export.
It contains no controller adapter, flashing operation, reset or motion operation.
The retained source is not claimed to prove the controller's current filesystem;
an eventual installer must verify current source bytes before any write.
Only `--help` and the no-approval argument-rejection path were executed here.
Private staging has not run; its end-to-end candidate result is still unverified.

### Direction-change approval and execution checkpoint

User approved direction-only staging/installation, necessary startup/recovery hold,
and one -6 test with return only after verified arrival. Private staging completed:
`wizard-20260919T120836418654Z-a650a5a7eb314cc9b756964c18b236ce`.
Candidate filesystem SHA-256:
`d1c041bcb4e90082685babc16698bcef3c639d87464932d6534d8056b71ce3aa`.
Six other entries preserved; native parsing/remount checks passed; encrypted
candidate saved without overwriting the retained source. No firmware change.

The filesystem installer uses a pinned r16 execution profile and the existing
one-write/full-readback/protected-region checks. Sixty-nine core/image tests passed
before invocation. The live installation was started once; its journal is
`private-backups/controller-20260918-session1/pair-negative6-provisioning-events.jsonl`.
Do not rerun this installer on a timeout or missing console output. Completion is
unproven until the journal and final export show readback and one startup.

Host negative pair support now requires a completed direction-change installation
receipt via `--negative-installation-export`; default +6 behavior remains unchanged.
Tests reject missing/invalid negative receipts and positive plans under a negative
receipt. This receipt requirement is not a substitute for fresh same-boot hold and
native prewrite checks. Movement and recovery have not yet run under these settings.

### Negative-direction live result — 2026-09-19 12:25 UTC

Approved work completed through the single conditional-return test. Installation
export `wizard-20260919T122314132214Z-9a1e2bb36ed8412cb54610a1ca58fa9f`
confirms one filesystem write, full readback, unchanged protected regions/r16 app,
retained source and one startup. Private settings remain at **offset -6**; there
was no automatic restoration. USB reads took several minutes each; original
process 60748 completed successfully, without another invocation.

Recovery export `wizard-20260919T122337278288Z-762371fbbccb4ac49e69ac84e97a0a56`
verified a fresh-position hold at 2903 (old goal 2907). Necessary approved startup
then produced boot `8ec007e96f76cafac23bac9739437efc`, observed in
`wizard-20260919T122408991664Z-eba0fa5ad92d4d819636ab1447bd5014`.
Ordinary hold `wizard-20260919T122425387295Z-55145896e1824184b1c862267fee77a4`
verified position/goal 2903, zero error, no neighbor position changes.

Trial: `wizard-20260919T122507527689Z-b52412aa30dc4f5ba55315fd35354bf7`.
Forward: `wizard-20260919T122458244741Z-9b5a28f3770a4b8593c0ef6851b12cf7`.
Return: `wizard-20260919T122507135457Z-e2d89bf807aa4c6ea4836a10a05db5e7`.
Full return-chain replay passed, including forward evidence and endpoint continuity.

| Leg | Start | Requested/encoded/readback target | Final position | Error | Result |
| --- | --- | --- | --- | --- | --- |
| Negative outward | 2903 | 2897 | 2897 | 0 | ARRIVAL, 338425 us final observation |
| Positive return | 2897 | 2903 | 2897 | -6 | NON_ARRIVAL, 2033618 us final observation |

Forward had 6 scans; return had 21. Return was authorized only after verified
outward arrival/export; between-leg position delta was zero. The controller and
host stopped on RETURN_ENDPOINT_NOT_VERIFIED. No retry, extra movement, recovery,
settings restoration or reset followed. Latest recorded goal is 2903 and position
2897; these are historical observations, not a guarantee of current physical state.

Interpretation: negative travel succeeded while positive travel again fell short,
now at a second target in the same narrow range. This is useful evidence for
direction-dependent response, not proof of backlash, friction, gravity, gain,
deadband or a particular compensation model. This was not an identical-anchor
matched experiment: prior positive tests started at 2901, this trial at 2903/2897.
No physical tool-tip accuracy claim. Next safe work is offline comparison of
forward/return transient load/speed/current and a bounded follow-up proposal.
The new 6-count residual exceeds the existing recovery admission maximum of 5:
do not widen that policy, reset/retry, or nudge the target automatically.

### Same-pair transient analysis

Offline export `wizard-20260919T122653214781Z-96a8884bc224497c8d1199484da4e8c2`
retains decoded forward/return traces and their replay-linked comparison.
The analyzer now supports return records only after the complete paired evidence
chain replays; paired comparison also checks that the selected forward assessment
matches the return's linked forward assessment.

| Post-command quantity | Negative outward | Positive return |
| --- | --- | --- |
| Samples | 3 | 18 |
| Position range | 2897–2899 | 2897 only |
| Sampled speed, library units | -50 to 0 | 0 only |
| Load, library units | 0 to 21 | -53 to -49 |
| Current, library units | 0 to 1 | 1 to 2 |
| Raw voltage | 121 | 121 |
| Raw temperature | 30 | 30 |
| Final plateau first observed after ACK | 216692 us | 103752 us |

Both writes had enabled ACK, library return 1 and device error 0. The successful
leg provides evidence that acquisition is capable of reporting changing position
and nonzero speed; this is not a universal proof against all feedback faults.
Positive return reports a different load/current response without detected travel.
Do not interpret these raw values as calibrated torque/current or infer a specific
friction/gravity/gain fault. Supply transients between samples remain unmeasured.

Next: review read-only servo control-parameter coverage and command semantics
against the pinned source before selecting a single-variable follow-up. Prefer
learning why positive commands produce reported effort without travel over blindly
adding counts. No applied compensation or servo tuning is authorized by this
analysis. Any subsequent physical trial needs a supported recovery route for the
6-count residual; the existing maximum-5 recovery must not be silently bypassed.

### Read-only configuration and command-semantics check — 2026-09-19

The stopped r16 bus permits its fixed configuration acquisition (phase Fault),
without resetting or moving. Captured once and replayed:
`wizard-20260919T122842136476Z-63b26f504d1b4bd78fd7d46921872409`.
Transport: `wizard-20260919T122842203031Z-4ac022feb0594ce9aac9be54248fff54`.
All 12 reads valid; POST acquisition and GET retained response matched exactly.
The capture CLI now accepts revision 16 using the strict r16 startup validator;
its default revision 14 path remains unchanged. Twenty-three configuration
capture/review/HTTP tests passed in 5.26 seconds.

Raw values match the previously recorded r14 configuration: limits 0 and 4095;
CW/CCW deadband registers both 0; mode 0; torque enable 1; acceleration 1; goal
speed 20; torque limit 1000; lock 1; offset word 2712; model word 2057. Labels
come from the pinned SMS_STS header; model-specific compatibility and physical
scaling are not independently established. In particular, the raw offset word
must not be interpreted as an unsigned physical angle.

Pinned `SMS_STS::WritePosEx` encodes acceleration, absolute position, zero goal-time,
and unsigned speed in seven bytes at address 41. Our decreasing target 2897 is
still a positive absolute count; it does not require negative speed or a negative
position argument. Both observed payloads match that encoding. No basis was found
to fix this by negating speed, changing byte order, or sending a relative target.

The two observed deadband registers being zero do not support blaming a configured
5/6-count deadband. Requested positions are within reported limits and torque was
enabled. These facts narrow the possibilities, not establish a cause. The fixed
12-register endpoint does NOT read gain coefficients, starting-force parameters,
or a full model-specific control table. Do not invent their addresses or change
them based on this capture. Next investigate the authoritative model-specific
control map before choosing a read-only diagnostic extension or a one-variable
speed experiment. The stopped movement sequence remains stopped; no tuning,
configuration write, reset, recovery or movement occurred during this check.

Source-review follow-up: [ELBOW_GAIN_DIAGNOSTIC_REVIEW.md](ELBOW_GAIN_DIAGNOSTIC_REVIEW.md)
records pinned M3 register definitions P=21, D=22, I=23 (one byte each), manufacturer
documentation limits, and a minimal read-only extension plan. Current gains remain
unmeasured. Prefer obtaining those three bytes over blindly changing speed or
applying a fixed target offset. No gain writes or firmware deployment authorized
by that review; the existing six-count residual and stopped state remain intact.

Checkpoint 2026-09-19: steps 1–4 below completed. User explicitly approved the r16
app-only installation/startup. Full app readback and protected-region checks passed;
six-event journal is complete. Read-only startup export
`wizard-20260919T114601678092Z-14a8c052624c472a82193694b4b7fec4` observed stable idle
boot `c23f5bdf087bb87f4fa423c1dac183e1`. Installation export is
`wizard-20260919T114601318571Z-ee8963706ecb49aa9c6327053f2e70e2`.
Local recovery preflight passed with key_extracted=false and attempt_reserved=false.
No recovery preparation or motion command was sent in this installation turn.

1. Obtain separate approval for one r16 app-only installation and one startup.
   Image SHA-256 is `dc8b6f0016d29495ef6403d6a04adcbc192ec45ccd1ede7c390c3d1b4b3ea05e`.
   Preserve existing filesystem/settings; no provisioning or movement in this step.
2. Run the existing installer with revision 16 and its explicit authorization flag.
   Stop on any mismatch or uncertain result; do not retry/reset automatically.
3. Run `observe_r10_startup.py --revision 16` to export read-only startup observations.
4. Use that exact export with `run_supported_recovery.py --startup-export <id>
   --preflight-only`. This cannot run before a real r16 installation/startup receipt.
5. Under the user's approved one-shot supported recovery scope, run the same script
   with `--authorized-supported-recovery`, once. No automatic follow-on pair.
6. Review the linked trial, transport and recovery endpoint exports. A failed or
   inconclusive recovery halts; a verified recovery supplies evidence for planning
   subsequent matched-direction testing, not automatic permission or tip accuracy.

Offline validation checkpoint: 28 pytest cases passed across
`test_hold_state_snapshot.py`, `test_hold_initialization_model.py`,
`test_hold_plan_admission.py`, `test_controller_hold_config.py`, and
`test_allocated_hold_runtime.py`. The native recovery harness additionally loops
through residuals -6..+6, every read-failure position in five scans, changed
baseline/neighbor states, lost ACK, ignored target, torque loss and arrival error.
All use scripted buses, not hardware. This is not an ESP32 build or live recovery
result, and the ordinary hold constructor retains its original admission guard.
