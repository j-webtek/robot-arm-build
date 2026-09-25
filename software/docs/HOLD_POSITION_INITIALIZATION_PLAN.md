# Hold-position initialization: reviewed design, no device authorization

## Implementation checkpoint — 2026-09-18

### Latest: first live hold stopped before action; pose revision proposed

The approved powered test captured all seven servos but stopped on elbow position
2901 outside its historical [2659,2787] window. One snapshot, zero servo actions;
no retry or reset. Saved observation:
`wizard-20260918T200008543182Z-dd9099e1620648589bdae768904d2b4d`.
`HOLD_SUPPORTED_POSE_REVIEW.md` proposes a separate [2893,2909] admission window
while holding the freshly measured count and retaining all other controls. It
passed the retained installed parser offline. Not staged or installed; approvals
for replacement preparation, provisioning/startup and another hold are pending.
Earlier ready-to-run and not-yet-challenged statements below are historical.

### Latest: approved hold filesystem write and startup verified

One approved filesystem provisioning completed with full readback and unchanged
protected regions, private recovery preservation and verified exports before one
startup. Final export: `wizard-20260918T194438073911Z-c5027a7bed73466d8d29ff51e49b553c`.
Status-only startup check returned IDLE/NOT_CONFIGURED on new boot
`749e200e399ad53b38f2fa35f4929ed8`; status export is
`wizard-20260918T194501474566Z-ea93ab25a2a940bd8412946a9c2d432c`.
This is expected before lazy challenge/configuration preparation, which was not
requested. No servo command occurred. Provisioning attempt is consumed; next is
configuration/runtime validation and separately authorized powered hold, not
another flash. See `HOLD_R7_PROVISIONING_REVIEW.md` for complete evidence links.

### Latest: candidate-specific provisioning command locally verified

Added `provision_hold_r7.py` with distinct local-only preflight and explicitly
authorized provisioning/startup modes. Exact staged digest, retained review,
policy and native validator are checked; device imports/key extraction are not
reachable from preflight. Real local preflight passed; 35 CLI/core tests passed.
No provisioning attempt occurred. Await separate approval for the exact candidate's
filesystem-only write and one startup, without a challenge or servo commands.

### Latest: approved offline candidate privately staged

One-use offline staging completed after explicit user approval. The exact reviewed
draft and newly generated key are in a preserved/remount-verified filesystem
candidate, saved and verified with current-user DPAPI. Four existing entries were
preserved. Candidate SHA-256:
`0bdfc4d3f300e811e03332a6a86df20e47c3d42c95282e9ddd2f00c211044e9b`.
Review export: `wizard-20260918T192754597401Z-66ce7c2b5fa041509937d7c61b69134f`.
No controller access occurred. Do not regenerate the key/candidate. Separate
provisioning/startup approval is still required; see `HOLD_R7_PROVISIONING_REVIEW.md`.

### Latest: private preservation and exports integrated

`run_hold_provisioning` now shares the tested orchestration while selecting only
r7 hold staging/execution/journal/private paths. Startup is explicit and defaults
off; a verified result export precedes any authorized startup. 58 tests passed,
including integrated success/fault cases for r6 and r7 with both startup choices.
Only synthetic credentials and devices were used. Real hold candidate/journal
paths remain absent. Next: separately approved offline private staging, then
review the exact candidate digest before asking for a controller write.

### Latest: r7 hold provisioning core and reviewed draft

Added separate hold image staging and installed-candidate native validator;
readable draft is `hold-r7-policy-draft.json`. Added a fixed r7 application profile
and distinct hold journal while retaining the existing one-write/protected-region
verification core. Both startup and hold profiles pass the full fault matrix;
42 targeted tests passed. No device/key access or real candidate staging occurred.
Next: compose private staging, execution and reproducible exports, then request
separate approvals. Details and historical-window limitations are recorded in
`HOLD_R7_PROVISIONING_REVIEW.md`.

### Latest: r7 app installed; status-only startup check passed

The explicitly approved app-only installation and single startup completed after
supported USB-only setup confirmation. Exact app readback/protected-region checks
passed. One status GET returned IDLE/NOT_CONFIGURED, zero records and no storage
fault. Evidence: `wizard-20260918T191322958288Z-a8f1786858e441619438af6e01245a46`.
No challenge, provisioning or servo commands were sent. r7's deployment journal
is consumed and cannot be rerun. See `HOLD_R7_INSTALLATION_REVIEW.md` for hashes
and boot identity. Next: separately reviewed hold provisioning and hardware-origin
collection before an authorized live hold trial; no hold/movement success yet.

### Latest: r6-to-r7 installation preflight corrected and verified

The installer now recognizes the exact r7 application, r6 predecessor and
separate r7 journal. Its r7-only filesystem expectation is derived from the
verified successful r6 provisioning receipt and hash-checked private DPAPI image,
not the obsolete original backup filesystem. It does not mount/extract keys or
write plaintext. Wrong app, partition or filesystem stops prewrite checking.
Eleven installer tests passed; actual local r7 preflight passed without opening
hardware or reserving a journal. Protected-region and readback checks remain.

The next hardware step needs separate approval: one app-only r7 installation
and startup, after supporting the links and confirming USB-only power. This does
not authorize hold provisioning, torque engagement, movement or recovery retries.
See `HOLD_R7_INSTALLATION_REVIEW.md`. Hardware-origin collection and live hold
validation remain incomplete; no physical state changed this turn.

### Latest: allocation failure coverage and installation review

The configured native wrapper now tests failure of both explicit allocations and
listener startup independently. All remain terminal with zero bus reads/writes
and no request acceptance; restoring availability does not rearm initialization.
Four focused tests passed. Candidate and recovery artifact hashes were rechecked
locally without reading them into public output or contacting the controller.

See `HOLD_R7_INSTALLATION_REVIEW.md`. Review found a concrete deployment-tool
compatibility issue: the app-only installer still expects the original filesystem,
but approved r6 provisioning changed it. Before adding an r7 upgrade edge, bind
its prewrite expectation to the successful provisioning evidence and test it.
Do not relax or skip the protected-region check. No install/provision/start was
performed; this is the next local implementation step toward the live trial.

### Latest: wizard offline hold review connected

The Arm section now offers **Review saved hold simulation and endpoints
(offline)** (`review_collected_hold`). Enter the collected export's `wizard-...`
folder name from the assigned export directory. The service replays the prepared
attempt, nonce claim, retained raw transport and policy-bound assessment; it then
recomputes the count-level endpoint detail for display. Missing or invalid exports
fail review. No reader, sender, connection or movement operation is invoked.

The result card separates host delivery from endpoint evidence, labels origin
SIMULATION and hardware NOT QUALIFIED, displays requested/encoded/readback/
measured values and neighbor changes, and keeps incomplete capture inconclusive.
It explicitly says wire observation and stylus-tip accuracy are not measured.
Review completion does not change arm connection/readiness or allow retries.

The real service and JavaScript renderer were tested with native-generated
successful and interrupted synthetic collections plus a missing export. The
sender stayed at one original simulated call and the hardware runner remained
unused; arm state stayed NOT_CONNECTED. Existing startup review tests also passed.
The combined focused regression suite passed **54 tests in 29.23 seconds**.
Hardware-origin collection, approved provisioning/deployment and a live hold
trial remain outstanding. This UI action reviews simulations only; it is not
a live hold button. The compiled r7 candidate is unchanged and uninstalled.

### Latest: count-level endpoint review in replayable exports

Successful simulated hold reviews now optionally produce a separate
`hold-endpoints.json` attachment, including the exact-policy bound export path.
It shows requested hold position, pinned-library encoded target, previous and
first/settled goal-register readbacks, measured start/settled positions, signed
error and position delta in servo counts, torque transition, explicit-enable
branch, command/observation timing and each other joint's changes. Invalid or
incomplete evidence never receives a verified endpoint breakdown.

Replay recomputes this attachment rather than trusting saved metrics. Existing
assessment schemas/outputs remain unchanged, and legacy exports without the
optional attachment still replay. Tests cover both hold branches, the bound
export, an observed one-count offset (not rounded to zero), and old-format export
compatibility. The focused suite passed **50 tests (21.53 s)**; the additional
legacy-compatibility assertions then passed the native publisher test (2.38 s).

All these results remain SIMULATION with no progression authority. Encoded
command bytes are not independent wire measurements, and servo-count errors are
not physical stylus-tip accuracy. No firmware/source candidate, controller
configuration or physical arm state was changed this turn. Hardware-origin
collection and wizard display remain pending; this supplies the useful review
data rather than granting motion from a success label.

### Latest: concrete hold-only ESP32 board composition

Added `configured_hold_owner.h` and `configured_hold_routes.h`, selected only by
the candidate generator's explicit `--hold-mode --configured` revision option.
This mode rejects mixing startup/baseline compositions. Candidate r7 selects just
the hold runtime, retains diagnostic-only setup/loop, and leaves the installed r6
image untouched. Legacy motion/mission/serial/ESP-NOW entry points are not started.

The challenge route reads **only** separately provisioned `/rocell-hold.json` and
`/rocell-hold.key`, once per boot. No file creation, fallback to startup policy,
lease renewal or automatic rearm occurs. Missing configuration fails closed.
The challenge starts a ten-second one-shot authenticated listener; it does not
itself read or write servos. Status/record GETs use the hold-specific schemas and
large response scratch is static, not on the control-task stack. The healthy
callback uses positive health semantics (`!rocellOwnerFault()`).

Native route tests verify inert registration/status, missing/empty/oversized/
short-read policy, invalid key, runtime rejection, unchanged repeated challenges
and invalid record indices. **50 focused tests passed (22.20 s).** This includes
the prior raw-transport/export/replay, simulated servo wire and failure cases.
These tests do not establish physical hold success or absolute endpoint accuracy.

Full target compile succeeded with `default-4mb-no-psram`. Verified export:
`wizard-20260918T174440380311Z-592ae9d2f2484a13b103cc8e8b954407`.
Application binary: 1,070,912 bytes, SHA-256
`380d7a69e0b456b25b4ae50e34f8d947724ca5c22db42d75958df509e2618c33`.
Reported program usage is 1,064,341/1,310,720 bytes; static RAM is 57,232 bytes.
The partition table matches the reviewed 4 MB layout (app0 at 0x10000, size
0x140000). Linker RAM remainder is NOT measured available runtime heap or stack
headroom. No application, merged image, partition table or key was uploaded.

Next: account for live memory,
and complete hardware-origin collection/wizard integration before proposing a
separately approved provision/install/hold trial. Reconnected external power does
not clear r6's recorded startup mismatch or authorize a new firmware installation.

### Latest: prepared-to-raw-transport collection chain

`hold_collected_review.py` validates a saved prepared attempt before invoking its
injected read-only collector, then links the raw transport export to that
attempt's digest. Complete captured records receive exact-policy/challenge-bound
assessment; partial, faulted or invalid collection remains inconclusive while
retaining raw transport and delivery evidence. Final replay rechecks source
manifests, nonce claim, request context, raw transcript and derived assessment.

The native signed-runtime test now covers mock HTTP collection through this
entire chain and an interrupted GET capture. Both export/replay; only the complete
case verifies the simulated hold. The sender remains at one call throughout;
collection does not accept a sender and cannot resend. Forty-nine focused tests
pass with expanded integration cases. No real device/network/key was used.

Remaining next work is concrete ESP32 route registration and a dedicated hold-only
candidate build/review, including the physical-origin collection path and wizard
integration. Simulation integrity is not hardware motion proof.

### Latest: durable exact-byte transport export/replay

`hold_transport_export.py` establishes the export destination before the first
GET, retains bounded response bytes as base64 plus digest, and records fixed
receive-failure markers without raw exception text. It exports through the
existing durable diagnostic exporter and immediately replays the retained
transcript. Replay validates byte hashes, request order/budgets, complete use of
the transcript and recomputed collector summary; it performs no network I/O.

The native-configured-wrapper test now exports/replays both successful collection
and failures at each of ten GET positions. Malformed JSON is retained and replays
as inconclusive. Mutated bytes/digests, paths, extra/missing responses and forged
summary categories fail replay. Forty-nine focused tests passed. No device was
contacted; exports were created only in isolated test directories.

Next: join this raw transport export to prepared-request review and add concrete
ESP32 route registration/hold-only candidate build. Capture integrity does not
prove device authorship or endpoint accuracy; no hardware success is claimed.

### Latest: strict provisioned-configuration parser wired before allocation

`controller_hold_config.h` parses canonical `rocell.controller_hold.v1` bytes with
explicit command, policy and start port. Lexical checking plus exact typed fields,
native policy validation and canonical round-trip reject duplicate/extra keys,
floats/coercions, unsupported joints and inconsistent timing/windows. Parsing is
one-use and exposes no accepted configuration after failure. Scratch storage is
a parser member rather than a multi-KB local stack array.

Configured runtime `initialize_config` now parses before network/runtime
allocation. The complete scripted network/collector test enters through this
configuration path. An initial incorrect policy field count rejected the valid
test and was corrected to 14; malformed-input tests continue to reject.
Forty-eight focused tests passed, including ESP32 compile-only checks. No file
was provisioned on the controller, and no hardware or network port was opened.

Remaining next steps: durable raw transport export/replay, ESP32 route registration
and dedicated hold-only candidate build. The configuration parser itself does not
read LittleFS or select a mode; board integration must do that explicitly and
must not instantiate old/new motion runtimes concurrently.

### Latest: matching bounded read-only collector

Configured firmware composition now serializes indexed records as
`rocell.hold_record.v1`, with explicit boot identity and kind. The new
`hold_transport_snapshot.py` accepts only hold status and indices 0..11, with
512-byte status and 4608-byte enveloped-record budgets. It performs at most
14 GETs (status, <=12 records, status), rejects active/changed/mixed sessions and
retains prior bounded raw responses on failure without retrying. A stable
TRANSPORT_CAPTURED result explicitly does not mean endpoint verification.

Native wrapper output drives the host collector test directly. Simulated failure
at each of ten GET positions preserves prior responses and stops immediately;
changed final boot status is inconclusive. Reader tests refuse command routes and
oversized/index-out-of-range requests without socket creation. Forty-seven
focused tests passed. No real HTTP or device connection occurred.

Next: persist/replay partial transport responses alongside prepared-attempt links,
add concrete ESP32 route registration and a strict provisioned hold-configuration
parser, then build/review the complete candidate before requesting deployment.

### Latest: configured hold-only network composition

`configured_hold_runtime.h` composes the allocated runtime with the one-shot
listener and socket session. It explicitly receives port, reviewed policy,
command, key/challenge and healthy predicate; it has no implicit filesystem
configuration, legacy motion path or reset/rearm. Network/request and runtime/
evidence graphs use two bounded checked allocations. Destruction closes network
objects and frees memory, not torque. This replaces the earlier expectation of
one allocation for the entire network graph; runtime/store itself remains one.

Read-only `status_json` and indexed `get` accessors expose retained evidence.
Status uses a distinct `rocell.hold_transport.v1` schema and advertises 4096-byte
record capacity to avoid old collector assumptions. Scripted tests verify inert
initialization, successful signed hold, disconnect/expiry/interference failures,
no reinitialization, and zero extra bus calls during status/record review.
The ESP32 compile-only probe now instantiates the network graph with adapter
declarations and enforces <=100 KB combined object budget (not live heap proof).
Forty-two focused tests passed. No real listener/device/image was opened/deployed.

Remaining integration: concrete ESP32 route adapters and policy-file parser,
matching host read-only collector, checked failures of both network/runtime
allocations, full target build with real networking/crypto and peak memory review,
then separately approved deployment/provisioning/servo engagement.

### Latest: existing one-shot listener integration tested

`hold_listener_owner.h` adapts the allocated hold runtime to the existing
StartSocketSession/StartListener interfaces. Runtime interference is now exposed
without reset, resending or torque release. A signed request arriving in 37-byte
chunks completes the simulated hold through the real framing/authentication path.
Peer EOF, trailing bytes, challenge expiry and short acceptance-response writes
fault with zero servo writes. Listener retirement prevents a second connection.

The initial success test failed because its fixture omitted the required
Connection: close header; correcting the fixture passed without relaxing HTTP
validation. Forty-one focused tests pass. Sockets/server/bus were scripted; no
real port opened and no device was contacted.

The adapter references an allocated runtime; it is not yet the final configured
network object graph. A concrete single-mode firmware wrapper, read-only status/
record routes, total network-buffer memory review and deployment candidate remain
next. After reply failure the retained authorization record may exist but no
terminal record is guaranteed; host replay must remain inconclusive, never retry.

### Latest: prepared-attempt-linked simulation review

`hold_started_review.py` verifies the saved pre-send plan/policy/challenge, exact
consumed shared nonce claim and delivery report before linking supplied native
simulation records. It validates reported acceptance bytes/digest separately from
endpoint evidence and checks recorded authorization/read/write times fall inside
the saved challenge window. The linked export retains prepared/capture attachment
digests; replay revalidates the entire chain and recomputes bound assessment.

The integration test now exercises one mock send, native execution records,
prepared/durable capture/link exports and replay. Out-of-window evidence and a
missing claim are rejected without invoking the sender again. Forty focused tests
pass with these expanded cases. No device, private key or firmware image was used.

This accepts supplied SIMULATION records, not live collection. It does not verify
device provenance or replace a firmware listener/status/record route. Next wire
the allocated runtime into a single exclusive diagnostic mode, with compatible
record-size bounds and read-only collection, then review/build the deployment
candidate. Do not mark hardware hold/return-motion validation complete from these
simulation results.

### Latest: checked one-lifetime allocation

`allocated_hold_runtime.h` owns the integrated runtime and real 12x4096 store in
one checked nothrow allocation. Policy/identity/key/clock/ACK-mode and external
healthy checks precede allocation; construction and initialization do not touch
the bus. Initialization is consumed even on failure. There is no reset, retry or
torque release in teardown. Native policy validation is shared with the staged
owner rather than duplicated.

Tests cover invalid policy, revoked setup, expired setup, forced allocation
failure, rejected reinitialization and a complete signed simulated hold through
the allocated wrapper. Every setup failure has zero reads/writes. ESP32
compile-only tests now instantiate the wrapper and enforce <=32 bytes for its
handle and <=80 KB for its heap object graph. Forty focused tests passed.
No live device or firmware image was accessed/deployed.

The wrapper does not itself select firmware modes or open a network listener.
Outer integration must ensure the old and new large runtimes are not active
together, preserve exclusive bus ownership and expose read-only collection.
Prepared-request-linked collection/replay and that mode/network integration
remain next, followed by separately authorized deployment review.

### Latest: frozen host contract and prepared one-use send

Added `hold_command_contract.py` and `hold_prepared_start.py`. Frozen plan/policy
bytes are validated and signed with the existing exact challenge format. The
prepared workflow exports and reads back plan/policy/challenge before consuming
the shared diagnostic boot/nonce claim and calling the injected sender once.
Uncertain delivery and unexpected adapter exceptions retain the claim; diagnostic
reports contain neither token/key nor raw exception text. Construction is inert.
No CLI/wizard route exposes this path yet and deployment/servo approval remains
required before an actual send.

Tests cover frozen-policy mismatch, wrong boot/noncanonical bytes, invalid keys
before export, successful mock sends, uncertain sends, consumed-claim duplicate
prevention and real adapter connection failure through a mocked socket. The
production signer matches the bytes accepted by the real native crypto pipeline.
Thirty-nine focused tests passed. All send tests used fake adapters or blocked
mock sockets; no device was contacted. No private live key was loaded.

Next: prepared-export/claim/delivery-linked collection and replay, checked
allocation in a single diagnostic firmware mode, then artifact compatibility and
deployment review. Merely receiving acceptance remains distinct from a servo
dispatch, a verified hold, or permission to proceed to another movement.

### Latest: ESP32 compile-only memory/store review

The pinned target toolchain reports 76,520 bytes for the integrated runtime plus
`EvidenceStore<12,4096>`; largest reported individual stack frame is 336 bytes.
These are compile-only measurements, not available live heap or total stack use.
`HOLD_RUNTIME_MEMORY_REVIEW.md` records sizes, reproduction and remaining target
integration requirements. The real bounded store now backs integrated runtime
tests; a maximum-identity/timestamp full record plus hashes also fits a slot.
No generic store limit or installed r6 image was changed. The focused suite passes
34 tests, including the new cross-compile budget regression. Next prepare the
host challenge-linked request path and a single-mode checked-allocation runtime.

### Latest: exact-policy bound replay/export

`hold_bound_replay.py` accepts independently supplied expected plan/policy,
validates their exact schemas and native limits, and checks every native record's
boot/command/plan/policy linkage. It checks authorization precedes acquisition,
then assesses raw records against those specific windows, speed, drift and timing
limits. The common replay engine now supports explicit limits internally while
the legacy public simulation entry point retains its original default behavior.

Integrated native runtime output round-trips through the durable diagnostic
exporter and recomputed bound replay. Tests reject changed authorization, missing
terminal, mixed hashes and policy mismatches. Re-hashed synthetic transcripts
with insufficient settling, different speed or excluded joint windows remain
inconclusive; a valid alternate settling limit succeeds. Thirty-three focused
pytest tests pass with expanded bound-replay cases. No hardware was contacted.

This validates consistency, not physical provenance or record authenticity:
controller authorization is still an assertion in exported evidence, and export
hashes are not signatures. All new results stay SIMULATION. Challenge expiry and
the native owner's exact start boundary are not independently replayed yet;
retain that limitation before introducing hardware-origin conclusions. Next
review target memory/storage and the host prepared-request/challenge linkage,
then integrate the runtime into a separately reviewed deployment candidate.

### Latest: authenticated native workflow integrated

`hold_authenticated_runtime.h` now joins one-use admission, reviewed native policy,
the staged owner and bounded publisher. It reserves 12 records: authorization,
up to eight snapshots, two actions and terminal. Every published record receives
the same admitted plan/policy hashes; authorization includes the exact native
policy. Enriched records use a 4608-byte buffer. The wrapper owns the controller
privately and does no I/O on construction or before successful admission.

A required external healthy predicate is checked before polling and again at
the actual write boundary after the prewrite scan. Tests revoke it during that
scan and observe zero writes. Invalid authentication, failed reservation and
failed authorization publication produce zero bus calls. Terminal publication
failure faults without retrying or releasing torque. Real signed host bytes
exercise the integrated runtime; Python checks hashes/policy across all resulting
records. The focused suite passes 33 pytest tests with expanded runtime scenarios.

This wrapper is not a mutex or a network route. Outer firmware must still provide
exclusive bus routing, a truthful physical/interference predicate, storage and
clock integration. No firmware image was built/deployed, and the arm was not
contacted. Existing host replay intentionally rejects these enriched records
until exact policy/hash/authorization replay is implemented next. Target-platform
memory/store review, host signing/UI workflow and deployment review remain open.

### Latest: authenticated plan admission and terminal evidence

Added `hold_plan_admission.h`: a one-use HMAC envelope check followed by an exact
comparison with a locally constructed canonical hold plan. The plan binds boot,
reviewed command, DEVICE_CAPTURE origin and SHA-256 of the actual supplied native
policy (windows, timing, speed, drift and explicit-enable permission). Policy and
plan hashes are exposed only after acceptance. Replay cannot consume the same
gate twice. This component does not read/write the bus and has not yet been wired
to an exclusive runtime or publisher authorization record.

Real Python HMAC -> Windows BCrypt tests accept the matching request and reject
bad signatures, changed command/policy/origin and noncanonical bytes. Firmware
request generation/signing is still test-only; a reviewed host contract/UI path
must be added. The native owner retains its own physical-policy validation.

The publisher now reserves 11 records (eight snapshots, two actions, one terminal)
and publishes terminal state/reason/counts once. Replay requires that record and
rejects missing, faulted or contradictory completion claims. Failure at terminal
publication stops the session just like an earlier export failure. Terminal
records are not signed and not yet linked to the new admission hashes.

Combined focused suite: 33 pytest tests passed. No device, image or configuration
was changed. Next integrate admission, policy/plan hashes, terminal evidence and
the exclusive runtime; extend host replay to the exact bound policy, then review
target memory and deployment artifacts. Current simulated replay uses defaults
only and must not be used for arbitrary policies or hardware-origin conclusions.

### Latest: simulation export and independent host replay

`hold_record_replay.py` decodes native raw records, validates register order,
lengths, timestamps, identity and action bytes/ACKs, and replays the default
simulation policy through the hold model. Successful evidence is labeled
SIMULATED_HOLD_VERIFIED, never physical arrival; invalid/partial/uncertain evidence
is INCONCLUSIVE. No result grants motion authority. Hardware-origin assessment
is deliberately not implemented until signed policy/terminal binding exists.

Both successful native branches and the partial-failure transcript now round-trip
through WizardDiagnosticExporter and manifest verification. Replay recomputes the
assessment and compares it with the saved result. Mutation tests reject missing
records, changed identities/targets/ACKs/raw feedback and bad indices. The initial
export test exposed and corrected an attachment-prefix path mismatch. The focused
suite remains 32 passing pytest tests, with expanded export/replay cases inside
the native-publisher integration test. Exports were created in isolated test
directories, not collected from the arm. No physical I/O occurred.

Remaining: authenticated admission and exact policy/terminal-manifest binding,
hardware-origin assessment and non-arrival classification, wizard action wiring,
target-platform memory/store review and separately approved deployment.

### Latest: bounded native record publication

Added `hold_evidence_json.h` and `hold_evidence_publisher.h`. Snapshot records
bind boot/command/index to all acquired goal/feedback/control reads, including
partial failures with null raw data. Action records retain argument-derived
payload bytes, timestamps, library return/error and ACK status. This is identity
labeling, not cryptographic admission. The publisher reserves ten records before
polling and faults the owner on serialization/publication failure; no further
bus calls occur after publisher failure. Maximum serialized record buffer is
4096 bytes. This exceeds r6's 2304-byte store slot and needs a new reviewed store
configuration; these headers have not been wired to the installed route.

Native tests serialize both successful branches and a partial control-read
failure; Python independently parses every record and verifies fields/raw lengths.
Injected publication failures at every record position in the nine-record
explicit-enable branch stop subsequent calls. Tiny output buffers fail empty.
The combined focused suite passes 32 tests. No device was accessed.

Important limits: reservation/publication uses a scripted sink, not durable host
export. Records carry timestamps because publication order is not causal order.
No terminal manifest, signed request, policy digest or host replay assessment is
provided yet. Next implement those links and real export verification before
considering deployment. A sink failure after a write retains local action/scan
evidence and stops future work, but cannot undo the already-issued write.

### Latest: pinned-library byte/ACK verification

`test_hold_servo_wire.cpp` compiles the actual pinned SMS_STS.cpp, SCS.cpp and
SCSerial.cpp, with a host-only HardwareSerial emulator. The pytest wrapper binds
all three implementation files and four relevant headers to SHA-256 hashes.
The complete staged owner runs through real read packet generation, response
parsing, WritePosEx/EnableTorque encoding, checksums and ACK handling.

Verified each emitted write packet's ID, address, width and payload against the
owner's action evidence. Both torque behaviors complete in simulation; executed
writes with missing ACK or corrupted ACK checksum fault without repetition. The
combined focused suite passes 31 tests. This closes the local pinned-library byte
verification item, not a physical UART capture or confirmation of servo behavior.
The Arduino shim is isolated in a host-test include directory and must never be
included in deployed firmware builds. Vendor sources were not changed.

Remaining before deployment review: authenticated identity/admission, bounded
serialization and durable export/replay, target-platform memory review, and
integration into a reviewed candidate. No live device or installed image changed.

### Latest: staged native controller implemented, not deployed

`software/firmware/diagnostics/hold_initialization_owner.h` now consumes native
whole-arm snapshots in a finite elbow sequence: baseline, separated baseline,
fresh prewrite scan, one hold write, postwrite scan, and separated settled scan.
If the hold write leaves torque off, an explicitly enabled policy permits one
freshly checked torque-enable attempt and its own postwrite/settled scans.

The core retains up to eight snapshots and two action records (fixed capacity).
Actions retain intended register payload, timestamps and individual library ACK
result/error. These payload bytes are reconstructed from the pinned WritePosEx
layout, not independently captured wire bytes. A pinned-library transport test is
still needed to prove the actual transmitted byte sequence. Captured is an
export-ready state, not durable-export verification, motion admission or all-arm
readiness. The component requires an outer exclusive bus owner and authenticated,
boot/operation-bound admission; it does not itself provide those integrations.

Tests exercise both torque behaviors, no implicit enable, missing ACK after an
executed write, unchanged goal, failed enable, all 140 read-failure positions in
the five-snapshot automatic-enable path, changed neighbor state, drift, ACK-level
changes, deadline/gap/clock faults and invalid policy. Terminal states perform no
further reads or writes; no release/reset/retry function exists. Thirty focused
pytest tests passed including native capture/controller, simulation model,
control-state and first-trial regressions. No physical device was accessed.

Next implementation: signed identity/admission and record serialization/export
replay, native-library byte verification and bounded memory review. Then review
the exact firmware/provisioning and supported-elbow engagement proposal for
separate authorization. Existing installed r6 behavior has not changed.

Added `software/src/rocell/application/hold_initialization_model.py`: an offline,
transport-free elbow state machine. It proposes at most one hold-position write
and, if explicitly selected in the simulated policy, one separate torque-enable
write. Both automatic-torque and explicit-enable branches require settled goal,
position and control readback before simulated export completion. Initial goals,
torque states and the actual shoulder positions are preserved. First faults latch;
there is no retry, reset or torque-release path.

Validation: 16 new model tests passed; 28 tests passed including existing first
trial, trial-run and native control-read regressions. Cases include lost ACK,
stale/replayed snapshots, drift before hold or enable, neighbor changes, wrong
goal/mode/moving flag, failed enable, and export failure after partial engagement.

This completes only the initial **simulation model**, not the native initializer.
Decoded synthetic snapshots do not prove raw acquisition or hardware provenance;
`finish_export(verified=True)` is a simulated input, not a durable exporter.
No live adapter, signed initialization contract, firmware deployment, wizard
integration or all-arm readiness is provided by this model. No hardware I/O was
performed. The powered, stationary setup is noted without clearing the r6 fault.

Next: bind this behavior to a bounded signed contract and native raw-read/write
owner, add timestamped action/ACK evidence and reproducible export replay, then
review the exact supported-elbow commissioning proposal. Shoulder engagement
remains a separate design; do not generalize this elbow model to the coupled pair.

### Native acquisition follow-up

Added `software/firmware/diagnostics/hold_state_snapshot.h`, a one-use capture
primitive retaining seven raw goal/feedback pairs and fourteen raw mode/torque
reads. It preserves zero or nonzero goals and torque-off states without weakening
the existing movement-admission checks. Capture timing spans both acquisition
groups; freshness failure latches. Partial read evidence remains inspectable,
but no decoded snapshot is accepted after incomplete acquisition.

Native scripted-bus tests cover both torque states, seeded goals, short reads and
device errors at all 28 read positions, incorrect byte order, invalid torque byte,
whole-capture timing, repeated use and stale evidence. The native capture test,
16 simulation-model tests and existing control-read test passed (18 pytest tests).
An initial test-only compile failure from a missing standard header was corrected.

This component has no writes, bus-owner lock, boot/command envelope or serializer.
The outer initialization owner must provide exclusive acquisition and identity
binding, then perform its own admission before any write. No firmware image was
built or installed and no device was contacted. Next wire this raw acquisition to
the bounded native initialization owner and correlated action/ACK evidence; signed
contract, durable exports and commissioning approval remain required.

## Why this is the next required work

The first powered startup trial accepted authentication and captured two stable
whole-arm scans, then stopped before dispatch because all seven torque-enable
registers were 0. No positional error was measured by that trial. The diagnostic
boot intentionally omits normal reference initialization and servo writes.

The existing r6 route requires all goals zero and all torque flags one. A hold
initialization will change that state. It therefore needs an explicit new phase
and goal-ledger transition; weakening r6's check or resetting until it passes is
not a solution. No current fault is cleared by this plan.

## Source findings and changed assumptions

Reviewed local pinned files:

- `software/.firmware-tools/user/libraries/SCServo/SMS_STS.cpp`:
  `WritePosEx` writes seven bytes starting at 41: acceleration, goal position,
  time=0 and speed. It does not explicitly write torque-enable address 40.
  `EnableTorque` writes address 40; `CalibrationOfs` writes 128 to that address.
- `SMS_STS.h`: mode=33, torque=40, goal=42/43, present position=56/57.
- `SCS.cpp`: individual writes call `Ack(ID)`. Broadcast/sync writes do not
  provide the per-servo acknowledged transaction required by this diagnostic path.
- Pinned `RoArm-M3_module.h`: `RoArmM3_moveInit` moves the base and driving
  shoulder to middle positions, releases/re-enables the driven shoulder, invokes
  its midpoint calibration, and moves other joints. It is not a hold-current-pose
  routine. Do not invoke it or its calibration helpers for this task.

Official [RoArm-M3 documentation](https://www.waveshare.com/wiki/RoArm-M3), checked
2026-09-18, states that rotation commands can turn torque back on after torque-off.
The local WritePosEx implementation lacks an explicit enable, so the library
alone cannot prove a goal write remains torque-free at the actuator. The exact
mechanism and applicability to each installed servo are not yet established.

**Correction to the earlier provisional idea:** seeding a goal while torque reads
zero must be treated as a possibly torque-enabling, physically moving command.
Never promise that torque remains off until a later explicit enable operation.
Direct register writes may also have device side effects; do not assume they
avoid this issue without authoritative evidence and a bounded test.

## Scope and constraints

Aim to hold the observed current pose, not home or recalibrate. No EEPROM unlock,
offset calibration, mode change, ID change, automatic return move or global torque
disable. The links must remain safely supported during commissioning. Support
must not force a powered joint against an obstacle; a base clamp alone is not link
support. An uncertain action stops further writes but does not automatically
release torque, since that previously caused a drop.

Existing shoulder measurements were 2390 and 1727, summing to 4117. Reference
mirrored targets sum to 4096. This 21-count difference is an observation, NOT a
calibration error diagnosis. Do not force a mirrored pair or change its offsets.
The pair is mechanically coupled and requires a specific engagement strategy;
independent single-servo success does not validate shoulder behavior.

## Ordered implementation

1. Define a new explicit signed initialization contract: boot/operation identity,
   permitted servo IDs, actual held-pose windows, finite action count, speed and
   acceleration limits, deadline, freshness and maximum drift. Permission must
   cover possible torque engagement on the first position write, not merely a
   later torque register write. No script sends anything on construction/startup.
2. Acquire two fresh full-arm goal/position/control scans under one bus owner.
   Require exact successful raw reads, expected mode, stationary flags and stable
   measured positions. Retain every original goal/torque state, including zero.
   Determine the initial joint target inside that owner from fresh position, not
   a rounded historical Cartesian estimate or a stored zero goal.
3. Before each permitted action, recheck position age/drift and other joints.
   A hold-position write must use the native known encoding for the measured count,
   low reviewed speed/acceleration, one attempt, and individual ACK. Record exact
   ID/register/bytes and timestamp. Treat it as potentially producing motion.
4. Read back goal, position, moving, mode and torque immediately afterward and
   across a bounded settling window. Explicitly model both device behaviors:
   position-write enables torque, or it does not. If it remains off, a separately
   authorized torque-enable step is a distinct recorded write, never implied.
   Reject unexpected torque/mode changes on other joints, drift or non-arrival.
5. Start with the elbow transaction in a supported arrangement in simulation,
   then propose the exact hardware test. Do not relax all-arm eligibility in the
   current movement route to force that test through. Design a dedicated staged
   initialization owner with partial-state evidence.
6. Review the coupled shoulder strategy separately before any shoulder writes.
   Preserve its actual coordinate offsets. Require bounded differential behavior
   and supported mechanics, rather than silently homing/recalibrating. The final
   whole-arm readiness result requires all necessary joints actually holding with
   accepted feedback, not just successful elbow engagement.
7. Build a verified goal ledger from each successful action. Seeded/held goals are
   not zero-goal startup state. Use an explicit continuation contract linked to
   that ledger for the first small movement and reverse test. Do not re-enter
   zero-goal initialization after a partial completion or fault.
8. Keep exports finite and complete. Per-joint initialization adds more evidence
   than r6's 16-record store; budget records/bytes and stop at boundaries with
   durable host review rather than evicting old records or making storage unbounded.
9. Simulate both torque behaviors, missing ACK despite execution, unchanged goal,
   stale reads, drift between target selection/write, enable-with-no-arrival,
   shoulder offset preservation, unexpected other-joint motion, export failure
   and partial initialization. No repeated writes or automatic torque release.
10. Only after software/native tests and compatibility review, propose an exact
    new firmware/configuration artifact and exact servo-state experiment. Obtain
    separate explicit deployment/provisioning/servo-change approval. r6 remains
    installed and the current fault remains retained until that review.

## Success criteria

A successful initialization proves reported fresh positions remained inside the
reviewed hold envelope, expected goals were read back, torque/control state is
known, and each write has its own correlated evidence and export. It does not
prove stylus accuracy or absence of all mechanical load. Only afterward resume
bounded forward/reverse endpoint tests and ghost-keyboard progression.

No device call, setting change, firmware compilation/deployment, provisioning or
reset was performed during this source review and plan update.
