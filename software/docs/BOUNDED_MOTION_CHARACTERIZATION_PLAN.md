# Bounded motion characterization — active plan

## 2026-09-20 architectural update

Follow [Official tooling reuse and host-driven characterization](OFFICIAL_TOOLING_REUSE_PLAN.md)
for the next implementation steps. Pause further campaign-related firmware
expansion pending the installed-interface comparison. Reuse existing JSON,
simulation, diagnostic acquisition and exports; keep campaign sequencing and
analysis host-side where supported. The older firmware implementation checkpoints
below remain historical records, not instructions to deploy unfinished code.

## Decision and current status

Supersedes deployment of the single compensated r32 experiment. **Pause r32
installation.** Keep its frozen artifacts and prior evidence; do not discard or
relabel earlier failed endpoint tests. r31 remains installed. No new live campaign
is authorized by a simulation result or by historical pose values alone.

Objective: collect a finite, reproducible set of uncompensated movement responses,
then compare models and prospectively test compensation. Firmware should provide
a reusable bounded diagnostic interface, not encode a new target for every test.
Normal changes to test targets, repeats and supported speeds belong in signed
host plans inside the controller's fixed admissible envelope.

## Reuse rather than restart

Keep existing raw acquisition, command/boot identity, HMAC admission, durable export
receipts, independent host review and same-boot fault settling. The existing
`positional_campaign_rehearsal.py` and `positional_owned_campaign.py` provide prior
finite wrist/synthetic campaign patterns; they are not released shoulder-pair
transports. Do not silently enable them against the controller. The new shoulder
classification policy will be independently testable before integration.

## 1. Separate measurement outcome from safety progression

Every leg has independent fields: delivery certainty, raw feedback validity,
settled-state validity, endpoint error, export status and continuation eligibility.

- SETTLED_ACCURATE: three fresh stationary observations satisfy the endpoint
  criterion and all state/envelope checks.
- SETTLED_MISS: stationary, consistent observed pose inside a separately reviewed
  characterization error/travel envelope, but outside the accuracy criterion.
  Save the miss and permit consideration of the next leg; do not label it accurate.
- STOP: invalid/stale feedback, uncertain delivery, wrong goal readback, unexpected
  direction, excessive travel, nonselected-joint change, changed torque, unbounded
  residual, no observed response, no settling by deadline, or failed export.

Continuation eligibility is not a movement permit. Each next leg requires fresh
acquisition and replanning against the actual pose, unchanged context, a valid
remaining campaign budget and the preceding verified export. A return is a normal
checked leg. No corrective nudge, blind return or automatic retry follows a fault.
Stopping progression does not cancel an already active servo target or release
torque; retain that distinction in the UI.

## 2. Define a reusable, versioned campaign contract

The host supplies a bounded ordered manifest with campaign/leg IDs, goals, speed,
acceleration, maximum packets, absolute position bounds, per-leg travel bounds,
coupled goal sum, settle deadline, sample cadence and total duration. The controller
validates supported fields independently; no arbitrary bus writes or settings.
Authenticate the campaign and bind each leg to its own fresh capture digest and
predecessor export. No resume of a partially consumed manifest after restart.

Use one exclusive owner and one controller task. A measured miss can complete a
measurement leg without clearing a safety fault. Retain the last record until
exported and preserve finite same-boot settling after faults. Cap the campaign
by both number of commands and elapsed time; provide cancellation between legs.

Keep firmware stable after release. Reflash only for defects, missing protocol
capabilities or a reviewed envelope change that cannot be expressed safely in the
existing contract—not because one endpoint missed its target.

## 3. First baseline campaign, then deliberate expansion

Draft only: 12 legs at speed 20/acceleration 1, alternating small and medium
shoulder-goal offsets with returns to a fixed anchor, repeated three times.
Preserve paired goal sum 4114. Example manifest offsets from the captured goal
anchor: [-8, 0, -16, 0] repeated three times (secondary offset is opposite).
This gives repeated endpoints and direction reversals without fitting compensation.
These numbers are offline candidates, not an approved physical workspace.

Before release, review both directions and swept geometry from fresh measured
pose: the downward/return direction has NOT been established clear by the upward
trials. Do not assume a joint limit or a motor encoder proves board clearance.
Reduce/split the first batch if clearance permits only one direction. Historical
r31 starting positions and goals must not be treated as current observations.

After reviewing the first batch, add a second supported conservative speed, then
additional nearby poses. Change one factor at a time. Only subsequently test
other joints and coordinated paths. Do not start with an unrestricted workspace
sweep. Camera, stylus contact and physical registration remain deferred.

## 4. Record and analyze

Save exact raw bytes, acquisition timestamps, intended goal, prior goal, transmitted
payload identity, target readback, positions during motion and final settled pose.
Record desired error, goal residual, movement direction, command delta, actual
delta, time-to-settle interval, repeat number, speed/acceleration and neighbor
changes. Include validated supported load/current/temperature readings with
documented units where available; do not invent capabilities or decode units by
guessing. Include firmware/configuration IDs and terminal status for every leg.

Compare repeatability, directional bias, amplitude, speed and pose effects; report
individual results plus median and worst observed errors. Keep failures visible.
Do not treat repeated samples from one move as independent trials. Encoder
prediction is not external endpoint or stylus accuracy.

## 5. Fit after baseline; evaluate on separate trials

First compare no correction, constant local offset and direction-dependent offset.
Use more complex models only if the data warrants them. Preserve coupled shoulder
constraints. Split by whole trials/campaigns, not adjacent samples. Freeze the
chosen model before a prospective comparison batch with the same conditions.
Check worst errors, overshoot, settling and neighbor behavior as well as averages.
The existing +10/-7 offset remains a hypothesis, not production calibration.

## 6. Implementation and release checkpoints

1. Offline policy/planner and classification tests. Validate misses can remain
   measurements while invalid state/export failures stop all later legs.
2. Extend native owner and signed schemas for reusable legs and bounded budgets;
   independently replay the same cases in host and native implementations.
3. Integrate wizard manifest preview, progress table, cancellation, exports and
   clear distinction between accuracy misses and safety faults.
4. Review controller memory, routes, startup behavior and physical local envelope;
   freeze one campaign-capable candidate and exact installation/startup bindings.
5. Install only after review; run the first bounded baseline batch, export and
   analyze it. No automatic compensation fitting/application during acquisition.

Completion: a single installed diagnostic release can run multiple reviewed
finite manifests without reflashing; every leg is reconstructible from exports;
normal bounded endpoint misses are recorded without false success or unnecessary
firmware churn; safety faults prevent subsequent dispatch.

## First implementation checkpoint

Added `application/shoulder_characterization.py`: a pure offline 12-leg manifest
draft and single-leg classification policy. It distinguishes SETTLED_ACCURATE,
SETTLED_MISS and STOP without producing movement authority. It checks explicit
absolute bounds, coupling, maximum travel, direction, target readback, enabled
joints, neighbor stability, ordered/gap-bounded observations, settling, observed
response and export/delivery prerequisites. The initial two-count accuracy and
12-count residual ceiling are **provisional offline policy**, not released limits.

Thirteen focused tests passed. The draft is simulation-only and uncompensated.
Existing firmware safety thresholds and live paths were not changed. No device
connection, firmware update or movement occurred. Next implement a finite
multi-leg simulation that reacquires state and refuses later dispatch after a
safety/export fault, then port the reviewed policy to the native campaign owner.

## Finite simulation checkpoint

Implemented `application/shoulder_characterization_sim.py`, a built-in synthetic
servo simulation with no transport or injectable hardware callbacks. It performs
the fixed 12-leg manifest with a finite time budget, fresh simulated acquisition
before each leg, fixed absolute bounds, a campaign-wide neighbor anchor, preserved
goal coupling and command/prewrite limits. It verifies and records intent before
simulated dispatch, exports observations and assessment, then binds the next leg
to that verified predecessor result. It never starts the next leg from an assumed
goal position. Existing live firmware and policy remain untouched.

The synthetic +9/-7 offset case completed all 12 legs as SETTLED_MISS, with no
compensation enabled and no physical packets. The zero-offset scenario completes
as SETTLED_ACCURATE. Fault injection covers neighbor movement, reverse movement,
wrong goals, disabled torque, no response, failure to settle, feedback gaps,
uncertain delivery, result-export failure, baseline drift and cancellation.
Fault on leg four prevents a fifth dispatch; baseline drift/cancellation before
dispatch prevents the fourth as well. No automatic return or retry occurs.

The initial simulator suite passed 14 tests. Exported 12-leg demonstration:
`wizard-20260920T004932651541Z-92af26f59c0b4a23ac86a1359000bf37`, under
`software/runs/wizard-exports`, attachment `campaign-result.json`.
This is software control-flow evidence only: the constant residuals, fresh samples
and dynamics are synthetic and do not establish real direction/clearance safety.

Next: define the native campaign manifest and per-leg admission protocol so the
controller can enforce the same distinction between measured misses and safety
faults. Reuse existing authenticated captures/export barriers; preserve finite
budgets and one-use identities. Run native/host parity and failure tests before
board integration or a new firmware release. r32 installation remains paused.

## Native classification-policy checkpoint

Implemented `firmware/diagnostics/shoulder_characterization_policy.h` as a pure
typed policy with no servo bus, dispatcher, signing or live routes. It independently
checks the same absolute bounds, coupled goals, actual travel, commanded direction,
enabled state, neighboring joints, timing/gaps, stationary tail, response magnitude
and residual ceiling as the host policy. Its result distinguishes STOP,
SETTLED_ACCURATE and SETTLED_MISS; continuation eligibility is not dispatch authority.

Host/native parity: **58 tests passed in 1.76 seconds**. These include 42 residual
boundary combinations and 16 failure cases: uncertain delivery, export failure,
torque/neighbor changes, moving endpoint, wrong goals, reversed motion, bounds,
timestamp order/gaps, excessive scan duration, no response, insufficient samples,
unstable tail, zero movement and changed coupling. The native test process receives
the same synthetic poses as Python; no real controller or servo is involved.

This policy evaluates an already acquired bounded sample batch. The future owner
must still acquire/validate raw feedback, bind it to actual command identity,
enforce deadlines during acquisition, verify authentic export receipts and prevent
further dispatch. Boolean policy inputs are not substitutes for those checks.
No firmware build, installation, startup or movement occurred in this checkpoint.

Next implementation: a finite native campaign owner and typed manifest admission,
with fixed campaign limits, fresh baseline before each leg, predecessor export
binding and latched stop semantics. Test misses continuing and safety/export faults
preventing later writes using a fake bus before adding network or board routes.

## Native finite-owner checkpoint

Implemented `firmware/diagnostics/shoulder_characterization_owner.h` with a typed
manifest limited to 12 legs and 60 seconds. Each leg acquires three stationary
baselines, records intent, reacquires immediately before dispatch, attempts one
paired target packet, and validates fresh goal/position feedback. It records the
result before considering another leg. The next baseline must agree with the
previous measured endpoint, not the requested target. Campaign-wide bounds and
neighbor checks remain active. Faults latch: no retry, return or subsequent write.

Fifteen fake-bus tests pass, covering accurate and bounded-miss batches, rejected
manifests, neighbor/reverse movement, incorrect goal readback, disabled torque,
no response, failure to settle, failed acquisition, result/intent export failures,
expired prewrite evidence, cancellation and campaign expiry. Tests also verify
that repeated calls after completion/fault cause no additional reads or writes.

This is an offline integration candidate, not a released controller interface.
Admission and evidence callbacks are test seams; they do not yet verify signed
manifests or authenticated export receipts. Those bindings, retrievable fault
records, board integration and resource checks remain required before live use.
The send event is explicitly unacknowledged; matching subsequent goal readback
is separate from actual-position arrival. Synthetic endpoint agreement does not
establish physical clearance or stylus accuracy.

Next: bind the finite owner to authenticated manifest/receipt identities and
retain fault evidence for export; test replay, stale receipts and interrupted
exports before adding live routes. Installed r31 remains unchanged, and r32
deployment remains paused. No hardware access occurred in this checkpoint.

## Authenticated result-barrier checkpoint

Added `firmware/diagnostics/characterization_export_barrier.h`, reusing the
existing SHA-256/HMAC export-receipt verifier. It stages the digest of exact
controller-owned result bytes and requires a receipt matching boot, campaign,
leg sequence and digest before permitting the next leg. One result can be pending
at a time; replay, reordering, overwritten pending results, altered bytes, wrong
campaign, reversed time or a receipt older than five seconds latch failure.
The five-second receipt window is an offline provisional value, not a movement
latency requirement. No receipt means no next-leg permission.

The existing host export test now exercises this barrier using actual Windows
SHA/HMAC verification and host-signed, verified export artifacts. Together with
the fake-bus owner suite, 18 tests pass. This proves the standalone barrier,
not end-to-end authenticated campaign operation.

Remaining integration: an asynchronous result-awaiting state in the owner,
controller-owned canonical result serialization and fault retention, signed
manifest admission bound to the same campaign identity, and host orchestration.
Do not substitute a request-supplied result or a boolean export flag for this
binding. Run integrated replay/interruption tests before board routes or release.
Installed firmware and hardware state remain unchanged.

## Integrated asynchronous result-export checkpoint

The native owner now enters `AwaitExport` after an eligible measured result.
It retains canonical result bytes and stages their digest directly into the
authenticated barrier. A receipt request cannot substitute different result
bytes. Only matching receipt acceptance increments the completed-leg count,
including the final leg. While waiting, owner advancement performs no bus reads
or writes; admission loss, campaign expiry or the five-second export deadline
latch a fault. Missing export never triggers a return or retry.

After receipt acceptance, three fresh stationary baselines must still agree with
the retained measured predecessor. An export wait is not interpreted as a servo
feedback gap, but never makes the prior endpoint current by assumption.

Binary result format: `RCCRESULT01` plus NUL, one-byte leg and manifest leg count,
eight-byte campaign budget, two-byte paired goals for each manifest leg, two-byte
lower/upper bounds for seven joints, one-byte outcome (1 accurate, 2 bounded miss),
and one-byte observation count. All multibyte fields are big-endian. Next are the
baseline and each observation: eight-byte start/finish timestamps followed by
seven rows of two-byte position, two-byte goal, one-byte torque state and 15 raw
feedback bytes. No compiler struct padding is exported. Existing receipt framing
binds the digest to boot, campaign identity and leg sequence.

Integrated native tests use real Windows SHA/HMAC with a fake servo bus and a
test receipt signer. They cover delayed valid receipts, replay, altered digest,
expiry, interrupted export and post-export pose drift, alongside existing motion
and acquisition faults. The signer is a test fixture, not proof of disk export;
the separate host receipt test covers verified artifact export before signing.

Remaining before live release: signed manifest admission and controller-owned
campaign identity lifecycle, retained/exportable fault records for early failures,
host decoding/orchestration of the binary artifact, board memory/resource review
(the retained result buffer adds 11,000 bytes), and authenticated network routes.
No firmware build, install, startup or physical command occurred here.

## Host decoding and retained runtime-fault checkpoint

Added `application/characterization_result_codec.py`: strict bounded decoding of
the native binary artifact, validating framing, manifest bounds/goals, timestamps,
joint fields and raw position consistency. It rejects truncated/trailing data.
The review export contains readable JSON and lossless raw hexadecimal bytes;
the existing exporter verifies the artifact, then the codec verifies byte equality.
This review path does not sign receipts or authorize progression.

Native-to-host tests decode actual fake-bus runner output, confirming the synthetic
+9/-7 residuals. Malformed framing/raw feedback and failed export verification
are rejected. Decoding is not authentication or proof of physical accuracy.

The owner retains its first runtime fault, phase, leg, write-attempt count and
last owner-loop timestamp, plus the last successfully acquired, bounds-valid pose
when available. Later invalid receipt requests cannot overwrite that first cause.
The retained pose can be stale and is not permission to move; failed/partial scans
are not represented as valid evidence. Pre-admission manifest rejection still
has only its rejection status rather than a populated runtime-fault record.

Remaining: serialize/export retained faults, signed manifest and identity lifecycle,
host receipt orchestration, and board resource/network integration. No hardware
connection, firmware change or movement was performed.

## Retained fault export checkpoint

Implemented `firmware/diagnostics/characterization_fault_record.h` and
`application/characterization_fault_codec.py`. Native serialization is bounded,
allocation-free and read-only; the host validates framing and evidence, then
exports readable JSON plus lossless raw hexadecimal through the verified wizard
exporter. This is available for retained runtime faults, not yet pre-admission
manifest rejections. Reports do not issue receipts or authorize recovery.

Format: `RCCFAULT01` plus NUL, one-byte reason length, ASCII reason, one-byte
origin phase/leg/write-attempt count, eight-byte last-owner-loop timestamp,
one-byte pose-present flag, and optionally one 156-byte pose using the result
format. Multibyte fields are big-endian. The loop timestamp is not an exact
failure timestamp. The pose is the last bounds-valid acquisition and may predate
the fault; reports explicitly set `pose_is_current=false`.

Native-to-host export tests cover acquisition failure, neighbor movement,
receipt replay, export interruption and cancellation. Truncated, extended and
wrong-magic records are rejected; records with no valid pose are supported.
The existing native harness also checks insufficient output-buffer handling and
that later rejected requests preserve the first fault. All are fake-bus tests.

Next: signed manifest admission bound to controller-owned campaign identity,
then host orchestration and board resource/routes integration. No live hardware
access, startup, installation or movement occurred in this checkpoint.

## Signed campaign admission checkpoint

Added `characterization_admission.h` and `application/characterization_admission.py`.
The host signs canonical bounded manifest bytes inside the existing single-use
start envelope. Native verification binds the envelope to boot, nonce and lease,
then compares the payload exactly against its own expected campaign ID, reference
capture digest, goals, bounds, time budget and fixed speed/acceleration. A consumed
attempt cannot be reused even when rejected. Only a match initializes the owner;
initialization itself performs no bus access or target write.

Payload: `RCCADMIT01` plus NUL, 32-byte campaign identity, 32-byte reference digest,
one-byte leg count, eight-byte time budget, seven pairs of two-byte bounds, paired
two-byte goals for each leg, two-byte speed 20 and one-byte acceleration 1.
Multibyte payload fields are big-endian. Native expected-state inputs must come
from reviewed controller-owned state, never the request being verified.

Thirteen focused tests cover host/native real-HMAC agreement, altered signatures,
different campaigns/references/manifests/boots/nonces, expired and premature
requests, trailing bytes, repeat attempts and invalid host budgets. These do not
establish physical clearance or capture freshness: owner acquisition checks still
apply, and production reference/challenge lifecycle integration remains pending.

Next: unify campaign identity across admission and export receipts in a controller
session wrapper, implement host orchestration, then review board resources and
routes before release. Existing direct owner entry points remain offline test
seams, not public live routes. No hardware or installed firmware was changed.

## Unified controller-session checkpoint

Added `characterization_session.h`. One private owner, admission gate and export
barrier now share the same boot/key and campaign identity. Receipt command identity
is the lowercase 64-character hex encoding of the 32-byte admission campaign ID.
The wrapper exposes signed start, bounded advancement, receipt acceptance and
read-only result/fault access; it does not expose a mutable owner or direct begin.
It stages its own retained result automatically on entering AwaitExport.

Integrated tests use a Python-signed start and real native HMAC/SHA with a fake
servo bus. A two-leg campaign completes; wrong-campaign receipts, previous-leg
replay and missing receipts stop progression. There is no bus access before
accepted admission or after a terminal state. Repeated start attempts cannot
restart a session. Seventeen admission/session tests pass.

This remains offline: expected manifest/reference/challenge construction still
needs a controller-owned lifecycle, and host transport/export orchestration and
board memory/network integration are not implemented by this wrapper. Test
receipt signing is not disk-persistence evidence. Production must retain the
existing verified-export-before-signing requirement. No hardware was accessed.

## Host export/signing coordinator checkpoint

Added `application/characterization_host_session.py`. The offline coordinator
freezes a copy of the approved manifest and checks source boot/campaign, exact
manifest and expected leg. It exports readable/raw artifacts with verification,
then independently applies the host movement classifier before signing the exact
result digest using the existing receipt format. It issues at most one receipt
per leg; rejection latches the host session. A receipt being issued is explicitly
not confirmation that the controller accepted it.

Tests use actual native fake-bus result bytes. Verified signing succeeds for the
bounded-miss case; failed exports, source identity mismatch, manifest mismatch,
false accurate outcome and replay cannot produce another receipt. Rejected
classification artifacts can remain exported for investigation, without signing.

Transport is intentionally absent. Result bytes do not contain boot/campaign;
the future adapter MUST obtain source identity from authenticated session context,
not trust response-body identity fields. Lost receipts need reconciliation, not
automatic resend or repeat movement. Remaining work includes transport/session
lifecycle integration, board memory review and live-route release checks. No
hardware connection, firmware installation or motion occurred.

## Bounded record-transfer interface checkpoint

Existing host HTTP workflows accept records below 4096 bytes; the campaign's
retained binary result can exceed that. Added host `RecordTransfer` assembly
bounded to 11,000 bytes and 1,024-byte chunks, with exact identity, offset, length
and final SHA-256 checks. Invalid, duplicate or incomplete transfers latch failure.

The controller session now exposes owner-thread-only `record_info` and
`record_chunk`. Both are read-only and available only while awaiting export.
Each chunk request binds the current leg and retained-result digest; stale legs,
wrong digests, excessive capacity and out-of-range offsets are rejected. No bus
read/write or session progression occurs while serving chunks. No network route
has been exposed. Future handlers must authenticate the session and serialize
access with the owner; these methods are not thread-safe transport authentication.

Native tests reassemble chunks, compare exact retained bytes, exercise invalid
requests and verify no bus activity. A native-to-host test feeds the resulting
artifact through the host assembler and decoder. Host maximum-size and malformed
transfer tests cover the larger-record boundary separately. Session size is also
checked against a 32 KiB host-ABI regression budget; this is NOT ESP32 free-heap,
stack, timing or combined-runtime resource validation.

Next: authenticated route/session lifecycle integration and actual board compile
and memory review, then a reviewed finite physical campaign. No firmware or
hardware changes were made in this checkpoint.

## Transport-dispatch seam checkpoint

Added `characterization_transport.h`, a bounded transport-neutral adapter for
signed start, receipt acceptance, record metadata/chunks and retained fault reads.
It obtains the reserved session through an access callback; denied access returns
403 before changing state. That callback is a mandatory integration contract,
not a newly implemented network authentication mechanism. No bus or advance API
is available to handlers. Actual acquisition/movement remains in owner polling.

Start envelopes are limited to 512 bytes; receipts require exactly 124 bytes.
Record metadata is 35 binary bytes: leg, two-byte big-endian size, SHA-256 digest.
Chunk requests are 35 bytes: leg, two-byte big-endian offset, expected digest;
responses contain at most 1024 raw bytes. Fault responses use RCCFAULT01. Invalid
sizes and stale/nonavailable records are rejected. Routes must preserve these
bytes, authenticate request context and run serially with the owner.

The native admission/session harness now exercises the adapter for denied and
accepted start, metadata/chunk retrieval, malformed chunk requests, receipts and
fault retrieval. Eighteen focused tests pass. Board build tools were located under
`software/.firmware-tools`; no board compilation, route registration, installation
or physical command has yet occurred for this adapter. Next work is concrete
board composition, challenge lifecycle and resource validation, not another
movement-policy change.

## WebServer route-binding checkpoint

Implemented `characterization_routes.h`, compatible with the existing WebServer
registration pattern. Routes are start/receipt (POST), record-info (GET),
record-chunk (POST, read-only operation) and fault (GET), all under
`/rocell/characterization/`. Bodies and responses use lowercase hex, keeping a
1024-byte chunk response at 2048 text bytes within the existing response budget.
Input decoding caps at 512 bytes and wipes the token buffer after dispatch.
Registration does not create a session or access the bus.

Every route calls a mandatory request-authorization callback before parsing or
dispatch. Production must supply that callback from authenticated reserved
controller context; the header does not implement an authentication mechanism
by itself. Existing transport access checks remain in force. Offline route tests
cover duplicate registration, denied access, missing/invalid/oversized bodies,
unexpected GET parameters and maximum response encoding. Combined route/admission
tests pass (19 tests).

Not yet board-integrated: prepare/reservation lifecycle, reference capture and
challenge generation, actual authentication callback, polling composition and
ESP32 build/resource verification. These headers have not been registered in
the installed firmware or a deployable candidate. No hardware access occurred.

## Controller-preparation policy checkpoint

Added `characterization_prepare.h`: a one-attempt preparation owner that reserves
before capture and never refunds partial setup. Trusted capture supplies three
recent stationary enabled snapshots. Preparation verifies timing/order, fixed
goals, position stability, raw position consistency and separately reviewed
absolute bounds. It derives the fixed 12-leg offset sequence from current goal
readback, checks each target against actual positions and reviewed bounds, and
hashes canonical capture bytes for the reference identity.

Trusted entropy supplies distinct nonzero nonce/campaign bytes; successful setup
creates a 30-second controller-clock challenge. Failure returns no prepared result.
The helper has no target/torque API. The manifest is a draft within supplied bounds,
not a claim of physical collision clearance. Bounds must not be generated from
position alone and treated as clearance approval.

Thirteen fake-service tests cover success, reservation/capture failures, moving
or disabled joints, raw mismatch, goal drift, stale/out-of-order timestamps,
out-of-envelope targets and failed/degenerate entropy. Repeat attempts do not
recapture or reserve again. Actual board reservation, capture and entropy services
are still to be wired into this helper; no ESP32 compile or deployment is claimed.

## Polled capture and ESP32 header-check checkpoint

Added `characterization_capture.h` using the existing private read-only servo
acquisition routine. A one-use reservation precedes capture; polling acquires
three snapshots at least 100 ms apart within a 1.5-second budget. Admission loss,
clock reversal or deadline failure stops acquisition. Completed snapshots feed
the preparation helper through its trusted capture callback, not request input.
Five native integration tests pass; success performs 84 register reads and zero
writes. Terminal polling performs no more reads.

The installed Xtensa ESP32 compiler successfully ran `-std=c++17 -fsyntax-only`
on `characterization_esp32_smoke.cpp`, checking the header composition and target
ABI size assertions: session below 32 KiB, capture and preparation each below
2 KiB. This is a cross-compiler header/ABI smoke check, NOT a full Arduino firmware
compile, link, heap measurement, stack analysis or release artifact. The compiler
was found under `software/.firmware-tools/data/packages/esp32/tools/esp-x32/2302`.

Still required: bind existing board-exclusive reservation flags, key loading,
entropy, authenticated request context and polling into one concrete composition;
then compile/link that candidate and measure combined resources. No firmware was
installed and no live hardware connection was opened.

## Controller composition and board-service adapter checkpoint

Added `characterization_controller.h` to own reservation, polled capture,
preparation, existing-key loading, session allocation and subsequent polling.
The session is not exposed until preparation and key loading succeed; failed
partial preparation never refunds reservation. Temporary key bytes are wiped.
Five fake-service tests cover success, health/heap rejection, ownership conflict
and missing key. Successful preparation performs 84 reads and zero writes;
polling an unsigned session does not access the bus.

Added opt-in `characterization_board_services.h`, mapping services to existing
board reservation flags, clock, servo bus, health checks, LittleFS key loader,
ESP heap checks, boot identity and hardware randomness. Its evidence sink remains
a required constructor dependency, not an always-success stub. Including this
header does not instantiate a controller, register routes or perform I/O.

This is not a complete deployable board image yet. The adapter still needs its
platform integration test, bounded evidence retention sink, authenticated request
context and preparation/status handlers. Full Arduino linking/resource checks
remain pending. No firmware was installed and no physical commands were sent.

## Board-service platform-test checkpoint

Added a native platform harness exercising the actual board-service adapter with
fake ESP/filesystem/servo interfaces and real crypto. Fourteen cases pass:
successful preparation, missing key, unhealthy/busy bus, insufficient/fragmented
heap, all existing reservation flags, non-new pair runtime and invalid boot
identity. Success performs 84 reads and zero writes; preflight conflicts perform
no reads. Failed key/boot setup retains ownership. Evidence sink refusal propagates.

This verifies adapter mappings and failure behavior, not ESP32 runtime resources.
Remaining: bounded evidence retention, prepare/status handlers, authenticated
request context and full firmware build/resource review. Platform stubs are not
live-device validation. No board connection or installation occurred.

## Bounded evidence-retention checkpoint

Added `characterization_evidence.h`: a fixed 71-record per-leg RAM store covering
three baselines, intent, prewrite, unacknowledged send, up to 64 observations and
result. It rejects unexpected phases, wrong leg, capacity exhaustion, invalid
result presence and reuse before receipt confirmation. Faulted/incomplete records
are preserved. RAM retention is not durable export.

Controller polling now releases the previous leg only after reading an increment
from its private session's completed counter (advanced by authenticated receipt
acceptance). Release failure stops controller polling before further acquisition
or movement. The board-service adapter forwards release to the evidence sink;
no request-body completion counter is accepted.

Twenty focused store/controller/platform tests pass. The store test covers
twelve maximum-size legs, release and invalid progression. Xtensa header/ABI
smoke checks pass with evidence below 24 KiB. This additional allocation must be
included in combined board-memory review; existing session-only heap checks do
not establish total application headroom. Full board composition/compile and
prepare/status handlers remain pending. No hardware was accessed.

## Prepare/status handler checkpoint

Added `characterization_prepare_routes.h`: authenticated POST prepare accepts no
parameters and copies reviewed bounds from board construction, never the request.
It schedules capture with HTTP 202; acquisition remains in controller polling.
Repeated preparation returns 409. Authenticated GET status reports controller
phase, completed legs and attempted writes without acquisition or dispatch.
Both routes reject extra parameters and disable caching.

Controller status now distinguishes capture, authorization, baseline, prewrite,
observation, export wait, completion and fault. Session allocation is followed by
an additional 32 KiB free-heap check; failed headroom drops the unstarted session
without refunding reservation. This is not a substitute for accounting for the
controller, evidence store, route buffers and other firmware allocations together.

Twenty focused route/controller/platform tests pass. Full challenge publication,
authenticated request binding and concrete board composition/full build remain
pending. No firmware installation, startup or arm movement occurred.

## Challenge publication checkpoint

Added `characterization_challenge.h`, a bounded public challenge encoder, and
`application/characterization_challenge.py`, its strict host decoder. Publication
includes boot, nonce, campaign, reference digest, lease and exact prepared manifest;
it contains no key. GET `/rocell/characterization/challenge` is authorization-gated,
rejects parameters and returns lowercase hex. It is available only while the
prepared session awaits start authorization, not before capture or during motion.

Binary format: `RCCCHAL001` plus NUL; 16-byte boot; 32-byte nonce, campaign and
reference; eight-byte issued/expiry times; one-byte leg count; eight-byte budget;
seven pairs of two-byte bounds; paired two-byte goals. Multibyte values are
big-endian, maximum 224 bytes (448 hex characters). Host validates expected boot,
lease framing and manifest semantics before passing data to the existing signer.

Twenty-five publication/route/controller/platform tests pass. Actual native
board-service test output decodes into the expected 12-leg host manifest and
produces a bounded signed token; wrong-boot/truncated/trailing/magic cases reject.
This is offline publication-to-signing evidence, not live transport authentication
or physical validation. Remaining: authenticated board composition and full build.

## Request-authentication binding checkpoint

Inspection found existing step routes authenticate start/receipt payloads, not
all HTTP requests. Added `characterization_request_auth.h` and the matching host
signer instead of supplying a permissive callback. HMAC binds domain, boot,
strictly increasing request sequence, actual GET/POST method, exact path and
SHA-256 of the exact body. Successful authentication consumes the sequence before
handler execution; replay fails. Invalid signatures do not consume a valid slot.
The gate must be instantiated once per boot/authorization context, never per
request or recreated with sequence zero under the same boot/key. Limit: 4096
accepted requests, 128-byte path and 1024-byte request body.

A real host/native HMAC test passes for status GET and rejects changed method,
path, body, sequence and replay. This is a request-authentication primitive, not
yet a wired HTTP header adapter or authenticated response channel. It does not
provide encryption or response authenticity. Actual route/header binding, response
identity protection, complete board composition and full build remain pending.
No firmware or hardware state was changed.

## Response authentication and header-decoding checkpoint

Added one-response-per-accepted-request signing to the native authentication gate.
HMAC binds response domain, boot, accepted sequence, status code and exact response
body digest. The host verifies those bytes before decoding; wrong boot/sequence,
status or body fails authentication. A new request cannot supersede a pending
response. Only one signing attempt is allowed for the accepted request.

Added strict `X-Rocell-Sequence` / `X-Rocell-Signature` header decoding: canonical
decimal sequence, lowercase 64-character signature, and actual adapter-provided
method/path/body. Real native/host tests cover header acceptance, noncanonical
sequence rejection, replay, response verification and altered-response rejection.

Still required: register collected headers and connect this decoder and response
signing to every WebServer send path, plus a host outstanding-request tracker.
This is not TLS/encryption and does not make the existing raw routes automatically
authenticated. No live server was changed and no hardware was accessed.

## Host outstanding-request checkpoint

Added `application/characterization_http_session.py`. It permits one outstanding
request, produces sequence/signature headers, and authenticates exact response
bytes before callers can parse them. Responses must match the outstanding sequence;
unsolicited/replayed/malformed replies, overlapping requests, authenticated HTTP
errors and uncertain delivery latch the host workflow stopped. No retry, redirect,
socket access or automatic recovery is implemented.

Eleven tracker/native-auth tests pass, including sequential success, timeout,
wrong sequence/signature/body, noncanonical sequence and duplicate response.
The eventual HTTP adapter must reject duplicate/missing authentication headers,
preserve exact bytes, call delivery_uncertain on transport failure, and keep this
tracker exclusive for its boot context. Reconstructing it at sequence zero after
uncertain delivery is not recovery. Network adapter and board response wrapping
remain pending. No firmware installation or physical movement occurred.

## Real host HTTP adapter checkpoint

Added `application/characterization_http.py`: explicit private IPv4/loopback,
allowlisted campaign methods/paths, bounded hex requests, one connection/request,
total deadline up to three seconds, no DNS/proxy lookup, redirect or retry.
It rejects duplicate headers, transfer/content encodings, missing/invalid lengths
and unauthenticated responses before exposing bytes to callers. Any failure
latches its outstanding-request tracker stopped. Construction performs no I/O.

Fifteen HTTP/tracker tests pass, including actual localhost socket exchanges
against a fake controller for valid signatures, duplicate/missing auth headers,
tampering and redirects. Failure cases issue exactly one request; a second call
is refused before network access. No connection to the arm was made.

The host adapter exists, but installed firmware does not implement the matching
response-authentication wrapper. Do not use it live until server integration,
complete candidate build and compatibility review are finished. Board-side response
wrapping, final composition/resource checks and live release remain pending.

## Authenticated WebServer facade checkpoint

Added `characterization_authenticated_web.h`. It collects sequence/signature
headers, authenticates actual registered method/path and raw body before invoking
handlers, and signs each handler response before forwarding it. Unsigned/replayed
requests never invoke the handler. Duplicate sends are suppressed; a handler that
does not send receives a signed 500 fallback. Authentication failures return an
unsigned 403 and the host treats these as terminal failures. No bus access exists
in this facade.

A native-to-host test verifies collected headers, denied access, valid handler
execution, signed response verification and replay rejection. Actual ESP32
WebServer parser behavior (including duplicate request header handling) and full
route/controller composition still require validation; this fake-Web test is not
a completed board build. One facade/authentication gate must live for the boot,
not be reconstructed per request. No live server or firmware was changed.

## Assembled authenticated composition checkpoint

Added `characterization_composition.h`, composing the controller, boot-lifetime
request gate, signed-response WebServer facade, transport, operation routes and
prepare/status/challenge routes. Access to the private session is conditional on
the facade's current authenticated handler context. Services and evidence store
must outlive the composition; polling remains separate from handlers.

An integrated native platform test now uses the real board-service adapter and
bounded evidence store: unsigned prepare rejects without reservation; signed
prepare reserves without immediate reads/writes; polling performs 84 reads and
zero writes; signed challenge/status succeed; challenge replay rejects. The
published status is AWAITING_AUTHORIZATION. This joins the previously separate
components but still uses fake WebServer/ESP/filesystem/bus services.

Next release work is a full ESP32 sketch composition/build with real WebServer
and existing firmware services, combined memory/stack review, and an end-to-end
host/native campaign test beyond preparation. No firmware deployment or live
hardware access occurred. The native integration test is not a full board build.
