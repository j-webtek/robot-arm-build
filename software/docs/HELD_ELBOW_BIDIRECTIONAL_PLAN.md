# Held-elbow forward/return diagnostics

## Offline r9 artifact/recovery review completed

See `R9_PAIR_DEPLOYMENT_REVIEW.md` for verified artifacts, resource limits and
remaining deployment gates. Final review export:
`wizard-20260919T011856526245Z-9632e510ffd44a5eaee57787344f35e1`.
Sources/binaries still match the build; original backup pair, original app-slot
recovery and retained r7 artifact verify. No hardware was opened.

The first static frame filter missed optimized mangled symbols; the corrected
review finds 71 relevant frames and a 3,808-byte largest individual frame. A
regression test covers this omission. This is not total stack or live resource
proof. Next review/reduce nested prepare scratch, extend exact-image installer
preflight and resolve current-filesystem expectations before requesting any
deployment/provisioning approval. Existing installer does not admit revision 9.

## Receipt-linked authorization workflow implemented

`replay_pair_challenge` verifies saved intent, its consumed request claim, bounded
raw response bytes and decoded challenge. Received challenges require matching
boot, valid schema/lease and a recorded transmission; uncertain receipts cannot
supply a challenge. Replay neither contacts the device nor claims a lease is still
current. The native owner remains responsible for actual challenge expiry.

`held_pair_receipt_workflow.py` connects a confirmed receipt to initial pair
preparation or accepted-delivery/arrived-forward evidence for return. It requires
the correct operation and same boot, invokes the existing one-use signer, then
saves/reopens a workflow link before returning the memory-only token. That link
binds receipt ID/hash, source export and authorization context; replay verifies
their exact challenge agreement. Failure after signing leaves the signer claim
consumed. No networking, sending, key loading or retry occurs in authorization.

The full native simulation fixture now obtains both receipts from local HTTP
servers and runs this workflow before sending/admitting initial and return tokens.
Tests reject uncertain/wrong-operation receipts and changed workflow receipt hashes.
Lower-level signing helpers remain internal building blocks; the UI still exposes
offline review only, not a live execution action.
Regression result: 14 challenge-receipt and full native-chain pytest cases passed
in 43.57 seconds (including service/UI review inside the native-chain tests).

Next: perform final offline candidate/recovery review and define the explicit live
wizard trial admission using these linked receipts/results. Deployment and pair
settings provisioning remain separately authorized; installed r7 is unchanged.

## Wizard offline paired-endpoint review integrated

The arm section now offers `review_observed_pair` (Review saved forward/return
endpoints). Supply the observed-return `wizard-...` folder from the assigned export
directory. The service replays the full saved pair/source chain, retains its own
review result for publication/export and never invokes a hardware runner.

The UI displays both legs' requested/encoded targets, first/settled goal readback,
start/final positions, count deltas, signed errors, observation intervals and
between-leg count continuity. It keeps pair outcome distinct from successful
offline replay and explicitly labels controller provenance and stylus-tip accuracy
unverified. Missing return evidence stays inconclusive. Inconsistent arrival/state
or provenance fields render an unavailable warning rather than a success panel.

Integration tests exercise the real service action and actual JS renderer with
the native synthetic pair's complete and missing-return exports. No hardware
runner calls occur, and the service remains NOT_CONNECTED. This is a review action
only: challenge requests, signing and live execution are not exposed by this UI.
Regression result: 69 native-chain, action-registry and renderer pytest cases
passed in 38.64 seconds.

Next: bind challenge receipts into the explicit trial workflow, review candidate/
recovery evidence and present deployment/provisioning scope. Installed firmware,
filesystem, camera and arm state are unchanged by this work.

## r9 strict configuration and read-only memory report compiled

`controller_pair_config.h` now validates canonical pair settings before key
access: bounded input, exact schema/fields, distinct command IDs, integer count
values, nonoverlapping tolerance and bounded positive/negative offset. Duplicate
keys, noncanonical JSON and truncated reads are rejected. The actual board prepare
callback is tested with inert filesystem/runtime dependencies for missing/bad
settings, short reads, missing/short key, invalid hold config and uncaptured hold.
Rejected settings do not reach key loading or pair initialization.

GET `/rocell/held-pair/capabilities` now reports boot, declared protocol/count
limits and current/minimum-free/largest-block internal heap values using the
pinned ESP32 core APIs. Reading it has no filesystem or bus effects. Stack and
physical accuracy remain explicitly unmeasured. `held_pair_capabilities.py` reads
the single endpoint, validates the boot/contract, retains response bytes/hash,
and explicitly does not attest firmware identity or resource sufficiency.

Twenty-six board/configuration/boot/network/challenge tests passed in 17.10 seconds;
seven host capability tests also pass. All used native doubles or localhost.

Separate r9 full build succeeded with the default 4MB/no-PSRAM profile. Verified
compile export: `wizard-20260919T010713961695Z-58d0552f91cd48da8d66d2c3097fb042`.
App binary: 1,104,112 bytes, SHA-256
`2af941a662a36f711f9571e34c3ab48b44bb0c2247bab797381c1814e75d3da9`.
It fits the 0x140000 slot with 206,608 bytes remaining. Linker reports 68,896 bytes
globals; this is not live heap/stack/timing evidence. Neither r8 nor r9 has been
installed. No pair settings were provisioned and no arm command was issued.

Next: connect source-linked challenge receipts, delivery and paired review to the
wizard, finish candidate/partition/recovery review, then present separate app-only
deployment and filesystem-provisioning requests. Do not use declared capabilities
alone as proof that a particular binary is installed.

## Host one-shot challenge POST client implemented

`held_pair_challenge_http.py` implements explicit empty POSTs for prepare and
return-challenge. It validates numeric LAN addressing and expected boot, saves
and reopens intent, consumes a durable per-boot/per-operation claim, and performs
one request with a three-second total deadline, bounded header and 512-byte JSON
response. Challenge schema, lease and boot are checked before returning it.
No key, motion token, resend, redirect, discovery or legacy route is used.

The result export distinguishes CHALLENGE_RECEIVED from CHALLENGE_UNCERTAIN and
retains complete bounded response bodies when received. Partial headers/bodies
are not yet archived. Result export failure leaves the attempt consumed. This
helper is state-changing, not a read-only compatibility probe: prepare can retire
hold evidence. Its caller must first verify installed capability and save the
required hold/forward source evidence. It is not yet exposed by the wizard.

Thirty-two challenge/delivery/HTTP/network tests passed in 6.27 seconds, using
localhost only. Coverage includes both routes, wrong boot, malformed replies,
redirects, dropped replies, duplicate prevention, invalid inputs without network
access and post-request export failure. No device request was made.

Next: capability/resource reporting and board-configuration fault coverage,
then connect the exported challenge results and paired review into the wizard's
explicit trial workflow before deployment review. The staged r8 binary remains
unchanged and uninstalled.

## r8 full offline build succeeded

Compile export: `wizard-20260919T005941057037Z-4ed3536aafcc42e29d34a18e10bfc6f5`.
Target: `esp32:esp32:esp32:PartitionScheme=default,PSRAM=disabled`.
Application binary: 1,101,088 bytes, SHA-256
`de41c648deb6bdce2f72b210be64e533950b7b21d5d1d6f3f736d902fc0ba25c`.
It fits the 0x140000 app slot with 209,632 bytes remaining. Linker reports
1,094,517 bytes program storage and 68,888 bytes globals (258,792 bytes remaining
in the linker RAM accounting). These are not runtime free-heap/largest-block,
stack-watermark or live-timing measurements; resource suitability is not proven.

The report retains source/toolchain/artifact hashes and verified export manifest.
No binary was uploaded, no filesystem was provisioned, and no controller was
opened/reset. Deployment remains unapproved. Do not use merged/bootloader/partition
artifacts as an implicit install plan. Next finish host challenge requests,
capability/configuration fault coverage and runtime resource reporting before
presenting a reviewed app-only candidate and separate provisioning proposal.

## Separate r8 board candidate staged for offline build

The candidate builder now supports `--configured --configured-revision 8
--hold-mode --pair-mode`. It stages a new immutable source directory and does not
overwrite installed/retained r7. Pair composition selects the hold-first owner,
registers hold plus pair routes, and replaces diagnostic-loop scheduling with
the two-owner scheduler. Legacy handlers remain unregistered by diagnostic setup.

`configured_pair_board.h` supplies static runtime composition;
`configured_pair_board_routes.h` supplies the explicit prepare callback. It only
accepts a captured hold, reparses the cached hold policy, reads bounded local
`/rocell-pair.json` and existing `/rocell-hold.key`, and wipes the temporary key.
Missing or malformed pair settings fail without default motion/configuration.
The hold policy cache now reserves its NUL terminator for that reparse.

Required pair-settings schema (not provisioned): `rocell.controller_pair.v1`,
with exactly `schema`, `forward_command_id`, `return_command_id`, `offset_counts`,
and `tolerance_counts`. IDs, offset and tolerance must satisfy the native pair
contract. The start port and whole-arm policy come from the existing hold config.
Do not write these settings or install the candidate without separate approval.

Thirteen focused builder/route/boot/runtime/network pytest cases passed in 14.39
seconds. Full r8 compile evidence is the next checkpoint; staging alone does not
establish build success, resource suitability, deployment approval or live motion.
Host POST challenge integration, capability reporting, configuration validation
fault coverage and wizard presentation still remain.

## Pair route composition and diagnostic scheduler implemented offline

`configured_held_pair_routes.h` registers four routes without initializing or
moving hardware: POST `/rocell/held-pair/prepare`, POST
`/rocell/held-pair/return-challenge`, GET `/rocell/held-pair/status`, and GET
`/rocell/held-pair/record?index=N`. The two POSTs are explicit one-use operations;
duplicates never renew challenges or recreate the hold-to-pair transition.
The host must export hold evidence before requesting prepare. The prepare callback
must supply reviewed configuration/key material and perform the transition.

The route object owns off-stack challenge/response buffers, rejects invalid or
out-of-range record indices, marks responses no-store and stops the pair runtime
on serialization failure. It adds no legacy motion/configuration/reset endpoint.
`poll_hold_pair_diagnostics` polls the two owners and services the WebServer only
when neither reports exclusive work. It must replace—not run alongside—legacy
command handling in the candidate diagnostic loop.

Native fake-server tests cover registration without side effects, failed/duplicate
preparation, explicit return, active-operation exclusion, both scheduler gates,
record validation and serialization faults. Six composition/network pytest cases
passed in 10.10 seconds. The actual ESP32 WebServer route template and scheduler
compile with retained no-PSRAM flags. No firmware was linked, flashed or run.

Remaining integration: candidate main-sketch wiring, reviewed prepare callback,
host POST challenge client, capability identity, linked resource review and wizard
presentation. The route component by itself does not make installed r7 pair-capable.

## Firmware hold-to-pair composition implemented offline

`ConfiguredHoldRuntime.retire_to_pair` now permits a one-use transition only from
a finished captured hold with a valid native handoff. It deletes the completed
hold/network graph, retires its old record surface and does not issue a bus
command or release torque. The caller must already have exported hold evidence;
there is no claim that the controller verifies host disk durability itself.

`configured_held_pair_runtime.h` owns the verified handoff, pair runtime and
network lifecycle in a destruction-safe order. It validates configuration and
health, retires the hold graph before allocating pair memory, checks each
allocation, and requires explicit initial/return challenge requests. Constructor,
initialization and challenge issuance send no servo motion. Allocation failures,
expiry and interference leave the attempted transition terminal, with no recovery
move or reinitialization. It exposes existing bounded pair status/record serializers
and exclusive-work state for the future firmware loop/routes.

Native tests exercise a real authenticated synthetic hold before transition,
runtime/lifecycle/listener allocation failures, duplicate handoff/reinitialization,
premature return and challenge expiry. Bus read/write counts remain unchanged
through transition and expiry, and holding torque stays on. The new composition
and templated transition compile with retained ESP32 no-PSRAM target flags.
This is compile-only evidence, not a linked candidate, heap proof or deployment.
Focused composition/network/full-chain regression: 7 pytest cases passed in
45.96 seconds, including the native multi-scenario failure harnesses.

Next: wire explicit routes and single-owner loop scheduling to this composition,
retain/export memory-health diagnostics, connect wizard review, then build/review
a candidate. Installed r7 remains untouched; physical pair proof is still pending.

## Forward delivery now gates return token release

Return authorization requires an explicit forward delivery export ID. It replays
the saved intent, send claim and result, requires reported acceptance, and checks
that boot/session/signing-context hash match the arrived forward observation.
Uncertain or rejected delivery cannot be overridden by later ARRIVED telemetry.
No return token is released in those cases; read-only diagnosis remains possible.
Return-leg delivery reports are rejected before following their source links.

Return signing contexts are now v2 and bind the forward delivery export ID/hash.
Replay reassesses this dependency. Older v1 contexts without delivery evidence
are intentionally not accepted for token release or replay as v2; there is no
automatic migration, retry or recovery. The native signed payload is unchanged.
This gate is enforced inside the signing helper, not only in a future UI wrapper.

Tests exercise accepted delivery through the full saved chain and native runtime,
and verify that arrived forward evidence still cannot authorize a return after
uncertain/rejected delivery. Changed delivery hashes and return-as-forward reports
are rejected. Work is offline/local loopback only; installed firmware is unchanged.
Regression result: 54 focused pytest cases passed in 64.57 seconds.

Next: firmware entry-point integration and wizard presentation/coordinator state
handling, followed by offline candidate review. Live deployment/pair testing still
requires separate authorization and is not covered by prior consumed hold approval.

## One-shot pair delivery implemented

`held_pair_delivery.py` validates the released token's unsigned envelope against
the replayed signing context and saves/reopens destination-bound send intent.
It consumes a shared boot/nonce delivery claim before opening the TCP connection,
then uses the existing bounded single-attempt HTTP sender. The device, not this
keyless host helper, verifies the HMAC. A new sender instance cannot bypass the
persisted send claim. There is no retry, redirect, fallback, reset or recovery move.

Delivery-result exports retain context/intent hashes and distinguish reported
acceptance/rejection from uncertain delivery. Replay checks source, claim and
response-body consistency. Acceptance never sets endpoint verification or
progression authority. Failed result export leaves the send claim consumed.
Tokens and keys are excluded from report artifacts.

The combined native synthetic integration now sends the real initial and return
tokens through loopback HTTP, then exercises native admission and endpoint replay.
Additional loopback tests cover lost/contradictory replies, rejection, durable
duplicate prevention and post-send export failure. These are local test servers,
not the robot. No installed firmware or hardware state was changed.
Regression result: 54 focused pytest cases passed in 53.31 seconds.

Next: integrate delivery evidence into the higher-level trial coordinator so
uncertain/rejected delivery stops automatic progression even when later read-only
telemetry is available. Then connect firmware entry points and wizard reporting,
assemble/review a deployment candidate, and request separate live-pair approval.

## Return capture and paired endpoint report implemented

`held_pair_observed_return.py` replays the saved return authorization and its
forward archive, derives the expected return plan, then collects only bounded
read-only return telemetry. Exact HTTP bytes, source context hash and both leg
assessments are exported and reopened. Replay performs no device access.

The paired report includes requested/encoded/read-back targets, measured count
deltas, signed endpoint errors and timing from each leg's independent assessment.
It checks return-start versus forward-end position within the admitted tolerance
and labels this continuity explicitly ELBOW_SERVO_COUNTS, not Cartesian accuracy.
Successful paired arrival additionally requires terminal COMPLETE status. A
STOPPED session with historical ARRIVED records does not qualify as a completed
pair. Missing, mismatched or uncertain return evidence stays INCONCLUSIVE; a
valid non-arrival remains distinct from an invalid observation.

The native synthetic harness now emits return telemetry after a successful pair.
The combined integration test reopens the real saved authorization/source chain,
captures and replays 2723 -> 2729 -> 2723, checks +6/-6 deltas and zero between-leg
drift, and rejects altered reports/context/hashes. Disconnection, forward records
masquerading as return, and stopped-return status are exercised. No live arm I/O
or new firmware installation occurs in these tests.
Regression result: 37 focused pytest cases passed in 50.52 seconds.

Next: one-shot delivery and durable delivery-result reporting, followed by
firmware entry-point integration/candidate review and wizard presentation of the
paired review. Native deployment and live pair trials remain separately approved
operations. Installed hold-only r7 and consumed hold authorization are unchanged.

## Archive-bound return authorization and combined host/native test

`held_pair_return_authorization.py` now reopens the complete observed-forward
chain before deriving the return payload. Required evidence is independently
assessed controller-reported arrival, stable AWAITING_EXPORT state and an exact
match to the historical anchor. It binds the same boot/session, forward-plan
hash, exact evidence digest, forward archive hash and original return target.
The challenge must be same-boot, use a different nonce and have a later issued
timestamp than the initial challenge. The native gate still validates its own
actual challenge/expiry and locally retained evidence; host replay is not proof
of current posture, challenge freshness or authenticated device provenance.

Before releasing the memory-only token, the helper saves/reopens its signing
context, replays the forward source again, atomically consumes the shared nonce
claim and checks claim readback. A failed release never refunds that claim.
Saved return contexts can also be replayed without keys or network access.
No helper sends commands, loads keys or exposes a wizard/CLI execution path.

The native runtime fixture now retains its hold records for a combined integration
test. All actual preparation, signing-context, nonce, forward-export and return-
authorization replay code runs end to end; no source replay boundary is stubbed.
Only hardware sender/HTTP/bus boundaries are synthetic. The host-generated return
token is accepted by the native runtime both directly and through its socket
parser, producing a 2723 -> 2729 -> 2723 simulated cycle. Tests reject malformed
contexts, reused/cross-hold nonces, wrong boot/challenge, incomplete/stopped forward
captures, and storage failures before or after nonce consumption. This supersedes
the separate-fixture limitation in the preceding checkpoint.
Regression result: 37 focused pytest cases passed in 43.21 seconds.

Next: concrete one-shot pair delivery with delivery-result exports; return-leg
capture/replay and paired endpoint reporting; firmware entry-point/lifecycle
integration and an offline candidate review. Installed r7 remains unchanged and
hold-only. Deployment and live pair operation require their own authorization;
the consumed hold approval is not reused for either.

## Session-linked observed forward export implemented

`replay_initial_pair_authorization` verifies the saved preparation, exact
challenge/boot/session identity, manifest hashes and consumed shared nonce claim.
It does not prove token delivery, current challenge validity or device identity.

`held_pair_observed_forward.py` derives the expected forward leg from that source
and collects only bounded read-only pair endpoints through `HeldPairHTTPReader`.
Export storage is prepared before any GET. Exact HTTP response bytes are saved as
base64 with hashes, including partial captures. The saved archive is reopened and
the same transport checks and endpoint assessment are rerun without device access.
Unexpected identity, incomplete responses or altered assessments cannot become
verified arrivals. Endpoint results are HOST_HTTP_OBSERVATION/controller reports,
not independent wire or physical-tip measurements. No result grants progression;
an ARRIVED history in a STOPPED session is explicitly reported as STOPPED.

Tests use native authenticated-runtime output with a synthetic bus and patched
HTTP, never live hardware. That collector test stubs only the saved-source replay
boundary; separate hold integration tests exercise the real preparation/context/
claim chain. A single combined real-source-to-native-pair fixture remains useful
before release. Tests also cover zero/partial response failures, offline replay,
changed context/assessment/hash/order, extra responses and consumed-claim mismatch.
Focused regression suite: 37 pytest cases passed in 32.57 seconds.

Next: bind return signing to this reopened archive, requiring exact historical
anchor, independently assessed arrival, stable AWAITING_EXPORT state and matching
current challenge/session. Then integrate the firmware entry points and review a
deployment candidate. Installed r7 remains hold-only; no new firmware, key loading,
hardware read, motion, reset or configuration change occurred in this checkpoint.

## Durable one-use initial-pair token release implemented

`held_pair_prepared_authorization.py` replays saved preparation, freezes and
validates challenge/boot/policy/hold identity, saves a signing-context export,
reopens it, then atomically reserves the shared boot/nonce claim and reads the
claim back before releasing a token. The claim uses the same namespace as hold
start, preventing reuse across workflows. The returned token is excluded from
the result object's representation and is never written to the context export.
No key is loaded by this helper and no request is sent.

Integration tests cover valid release/HMAC, duplicate rejection, wrong boot,
pre-export failure (no claim/token), post-reservation readback failure (consumed
claim/no token), rejection of another attempt after that failure, and collision
with an already-consumed hold nonce without overwriting it. Thirty-seven focused
pytest cases pass. Synthetic test keys only; no device/network was accessed.

This is an explicit low-level helper, not a wizard/CLI execution path. Callers
still need installed-capability and live-trial admission before sending, and
must record delivery without reissuing the token. Next implement the analogous
session-linked observed-forward export and return-signing path, then connect
firmware entry points and assemble/review the candidate.

## Host pair preparation linked to verified saved hold evidence

`held_pair_preparation.py` derives a frozen pair plan only after replaying the
observed hold and its linked prepared attempt/transport chain. It retains source
export IDs/hashes, boot, prior hold-plan hash, exact policy, pair-plan hash,
historical anchor and illustrative targets. The saved preparation is reopened
and rebuilt from its source chain before reporting replay success.

The result is explicitly OFFLINE_PREPARATION, with no progression authority or
retry permission. It does not load keys, issue a challenge, sign, connect or send.
Its protocol plan requests DEVICE_CAPTURE, but the preparation does not establish
device provenance or replace the native same-boot handoff/fresh scans. An older
boot's reference requires a new verified hold/preparation after reset.

The existing native-authenticated hold integration test now covers observation
export -> pair preparation -> saved replay with expected 2723 -> 2729 -> 2723.
Valid-manifest changes to source digest, historical anchor, boot, authority and
fresh-handoff flag are rejected. Duplicate command IDs are rejected. Thirty-seven
focused pytest cases pass. No real device or installed firmware changed.

Next bind pre-send signing/one-use claims to this durable preparation, then link
hardware pair observations and verified forward exports to return signing. The
firmware entry-point/candidate assembly remains separately reviewed work.

## Explicit initial/return challenge lifecycle implemented

`HeldPairNetworkLifecycle` owns at most one initial or return network graph.
Initial completion releases its graph and waits; polling never issues the return
challenge. An explicit return request is admitted only in the verified-forward
wait state. It uses a fresh nonce, rejecting all-zero/repeated entropy, invalid
lease, boot mismatch, clock rollback and failed allocation/bind. Expired or
failed operations stop without rearming. Abandoning an active lifecycle closes
networking and logically stops progression, without releasing torque or moving.
Key copies are wiped on destruction. `Esp32PairEntropy` uses `esp_fill_random`.

Scheduling tests cover progression, no automatic return, one-use issuance,
entropy failure, short challenge output, expiry, repeated nonce and backward
clock. These use synthetic operation admission; actual signed lifecycle/socket
tests remain separate. Thirty-seven focused pytest cases pass. Target compiler
instantiates the lifecycle with real ESP32 network/RNG adapters.

ESP32 sizes: coordinator 184 bytes; initial network graph 21,448; return graph
20,864. With runtime and retained handoff, initial fixed subtotal is 95,608 bytes;
return admission including temporary bridge is 103,668 bytes. Dynamic Wi-Fi/JSON,
GET buffers, allocator overhead and stacks remain unmeasured.

Next connect session-linked durable host hold/pair exports and signing to this
coordinator and firmware entry points. Candidate review, separate deployment
approval and live margins are still required. No actual network listener was
opened or device/firmware changed.

## Concrete one-shot network assembly compiled and scheduling tested

`HeldPairNetworkOperation` owns server/client/socket/owner/connection/listener
for exactly one explicit initial or return operation. Runtime, authenticated
operation and clock remain externally owned with longer lifetimes. It requires
the expected pair phase and an explicit nonprivileged port, retires the accept
listener after one connection, and does not rearm. Destruction closes networking
only; it does not release torque or dispatch recovery.

Native scheduling tests cover both operation roles with successful completion,
short reply, failed bind, malformed request and invalid port. They assert no
sampling until the connection closes, no sampling for failed cases, and no second
accept or sampling after terminal state. This fixture isolates scheduling; the
separate signed runtime/socket harness continues testing actual HMAC and movement
owners. Thirty-six focused pytest cases pass.

The actual ESP32 compiler instantiates this assembly against `NetworkServer`,
`NetworkClient` and the existing `Esp32StartSocket` (not only probe stand-ins).
Its target layout is **19,624 bytes**, including connection/listener/wrappers.
Runtime + both gates + temporary return bridge + this network totals **103,396
bytes**, excluding dynamic networking/JSON/GET buffers/stacks and handoff lifetime.

Remaining integration: fresh challenge issuance and top-level initial-to-return
network lifetime, durable hold export before graph release, hardware pair capture
export/signing, firmware entry points and candidate review. No live listener was
opened, no device contacted and no firmware deployed.

## Authenticated one-use hold handoff implemented

Pair startup no longer accepts an arbitrary Captured hold-owner object.
`VerifiedHoldHandoff` can be sealed only by `HoldAuthenticatedRuntime`, after
authenticated hold capture, successful publication, nonfaulted storage and a
valid health predicate. It copies the verified endpoint and binds boot, hold-plan
hash and policy hash. Issuance and consumption are each one-use; copying is
disabled. Pair admission compares all identities before accepting the endpoint.
The endpoint remains historical; fresh per-leg scans are still mandatory.

The integrated test now signs/executes an authenticated hold, issues its handoff,
destroys the entire old hold runtime/store before allocating the pair, then
executes signed forward/return through direct and simulated socket paths. Wrong
boot/plan/policy, used handoff and empty handoff prevent movement beyond the hold.
Duplicate issuance/start is rejected. Thirty-five focused tests pass, including
the original authenticated-hold regression harness. ESP32 compilation succeeds;
handoff target size is **1,888 bytes**, runtime remains **72,088 bytes**.

The local handoff is not a host durable-export receipt. Production lifecycle must
preserve/export hold evidence before freeing its graph, retain exclusive bus
ownership, and integrate concrete challenge/listener scheduling. Hardware pair
observation export/signing, reviewed candidate assembly and live margins remain.
No firmware deployment or device action occurred.

## Pair owner connected to existing one-request socket machinery

`held_pair_listener_owner.h` adapts initial and return operations to the existing
`StartSocketSession`/`StartListener` interfaces. Each operation has its own gate
and owner lifetime. The existing restricted POST parser remains unchanged;
distinct plan schemas/nonces distinguish start from return. Runtime interference
now provides a terminal stop path for parser or response failures. No automatic
listener rearm or challenge issuance is added.

The authenticated lifecycle harness now runs both direct admission and actual
bounded socket-request parsing against a synthetic nonblocking socket. Valid
initial/return requests complete; invalid signatures stop. A deliberately short
acknowledgment write after otherwise valid admission stops before the affected
leg's first movement (one hold write for failed start reply; hold+forward only
for failed return reply). Thirty-four focused pytest cases pass.

Target toolchain explicitly instantiates the listener owner, socket session and
listener with probe network types. Connection layout adds 19,440 bytes and
listener layout 56 bytes. Combined known runtime/gates/bridge/connection/listener
subtotal is 103,268 bytes, still excluding concrete Wi-Fi objects, owner/operation
objects, GET buffers, JSON allocations, stacks and hold overlap.

Remaining: concrete network lifecycle/challenges and same-boot hold provenance,
hardware-observation export linkage and signing, candidate compilation/review,
then separately approved deployment and live margin checks. No port was opened,
no firmware changed, and no hardware command was sent.

## Read-only native transport format and bounded host collector implemented

`held_pair_transport_json.h` serializes runtime status and terminal/waiting leg
records, binding boot/session/active-leg/plan identity and record index. Record
JSON is carried as a string (`raw_json`), preserving exact internal bytes through
decoding rather than requiring host reserialization. Reading active leg records
is rejected. The caller supplies buffers and serializes access with runtime
polling/return admission; this helper opens no socket and invokes no bus methods.

`held_pair_transport.py` supplies a concrete private-IP GET adapter for planned
`/rocell/held-pair/status` and `/rocell/held-pair/record?index=N` routes, with limits
of 1024/9216 response bytes, 34 records and three seconds per request. Collection
reads status/records/status once (at most 36 requests), verifies identity/order/
kind/schema, preserves raw responses and exact record bytes, and computes the
shared digest. Active/changing/invalid captures are inconclusive; partial responses
remain available. HTTP capture is not authenticated provenance or endpoint success.

Native runtime serialization -> host collection differential tests preserve the
exact raw records and digest. Fault cases cover active/changing status, wrong
plan/index, missing response and malformed raw record. Route/budget tests reject
command routes, out-of-range records and retries after failure. Thirty-three
focused pytest cases pass; serializers compile with ESP32 toolchain and runtime
layout remains 72,088 bytes. No endpoint is installed or contacted.

Next integrate the actual listener with exclusive owner scheduling and retain
collector exports linked to the approved initial session before return signing.
Live heap/stack/latency measurement and separate candidate approval remain.

## Duplicated JSON storage removed with exact-byte verification

The runtime now uses `HeldCompactEvidenceStore`: retain all raw owner snapshots,
record hashes/capture reasons and exact terminal bytes; reconstruct and hash-check
JSON on demand. Failures latch and cannot silently return different evidence.
Forward lifetime/accepted-return rollover remain unchanged. Record pointers are
scratch views valid only until the next get/publish; transport must copy them.

Actual ESP32 runtime layout dropped from 203,152 to **72,088 bytes**; compact store
is **8,748 bytes**, with unchanged 32-scan capacity. Known fixed runtime/gates/
bridge subtotal is **83,772 bytes**, not including dynamic network/JSON/stacks.
Twenty-five focused tests pass, including byte-for-byte full-store comparisons
for three outcome classes, capture-reason/terminal stability after faults and
hash-failure latching. Signed lifecycle passes with the compact store, and the
actual ESP32 compiler instantiates it. See `HELD_PAIR_MEMORY_REVIEW.md`.

Next integrate hold-buffer handoff and listener/collector, retaining checked
allocation and measuring actual target heap/stack and serialization timing.
No deployment, firmware writes or live arm commands occurred.

## ESP32 compile-only memory probe completed

The actual retained ESP32 toolchain successfully instantiated the new runtime
against SMS_STS with PSRAM disabled. Target ABI size is **203,152 bytes**, of
which **139,816** is the fixed JSON evidence store; initial/return gates and return
bridge bring the known fixed peak to **214,836 bytes**, excluding networking,
JSON temporaries, stacks, allocator overhead and any overlapping hold graph.
This is not measured free heap or proof of fit. No code was linked/flashed/run.

Reproducible script: `software/scripts/measure_held_pair_memory.ps1`.
Detailed results and allocation decisions: `HELD_PAIR_MEMORY_REVIEW.md`.
The probe leaves the retained r7 build unchanged and records source/compiler/
build-database/header identities. Next resolve hold-to-pair allocation lifetime
and duplicated raw/JSON evidence memory before integrating the live listener;
do not reduce required sample coverage or discard unexported evidence to fit.

## Authenticated pair runtime integrated offline; memory review now material

`held_pair_authenticated_runtime.h` owns the finite pair, publisher and bounded
store. Start requires a Captured hold owner and matching initial signed plan;
the runtime derives the canonical forward-leg plan/hash from the frozen anchor,
offset and policy. It preserves forward evidence through the wait and every
rejected return. Accepted signed continuation alone permits store/publisher
rollover and construction of the return plan. Fresh state/storage checks still
precede dispatch; no reset, retry, release or automatic return is provided.

The integrated harness now performs an actual simulated hold initialization,
releases that owner after handoff, executes authenticated forward motion, derives
the host return token from dumped evidence and locally computed identities, and
completes the authenticated return. Exactly three writes occur: hold, forward,
return. Invalid start signature leaves one write; invalid return signature leaves
two. Host and native session/forward-plan hashes match. Twenty-four focused pytest
cases passed. The test return export hash remains synthetic, not durable evidence.

Host ABI `sizeof(runtime)` is **204,008 bytes**. This excludes JSON allocations,
the temporary return bridge, networking, stacks, other firmware objects and the
initial hold object's overlapping lifetime. It is NOT an ESP32 free-heap result
or proof of fit. Before candidate assembly, inspect the target memory layout and
allocation peak; avoid retaining an old hold runtime alongside the pair. Keep
large objects off task stacks and make allocation failures non-actuating.

Outer integration still must establish same-boot hold provenance and exclusive
bus ownership, issue fresh challenges, provide concrete transport and verified
host export/signing, and measure target memory. No installed route uses this
runtime; r7 remains unchanged. No hardware action or deployment occurred.

## Initial pair authorization contract implemented — not routed

`held_pair_command_contract.py` freezes and signs a canonical pair plan. Native
`held_pair_plan_admission.h` independently reconstructs that plan from local
reviewed values and accepts exactly matching HMAC bytes once. The plan binds boot,
prior hold-plan hash, policy hash, distinct forward/return command IDs, signed
offset and tolerance. Session identity is SHA-256 of the exact canonical plan;
native and Python hashes agree. Offsets remain bounded/nonoverlapping; later
runtime validation must also check actual targets against the pose envelope.

Tests cover six invalid geometry/type combinations and eleven signed native
cases: valid request, altered offset/tolerance/hold/policy/command IDs/boot/origin,
extra field and corrupted signature. Native duplicate consumption is rejected.
The combined focused set passed 23 pytest cases. No hardware or deployment.

Signing is a low-level explicit helper, not a wizard/CLI action or an automated
hardware path. Protocol DEVICE_CAPTURE intent does not establish provenance.
Runtime must supply same-boot verified hold evidence and locally authenticated
identities, reserve storage, enforce bus ownership and establish fresh state.
Next wire this initial gate into hold-to-pair lifecycle and derive leg-plan hashes
there, then complete concrete transport/export signing and embedded memory review.

## Signed continuation connected to finite pair in native simulation

`held_pair_return_bridge.h` now implements the pair scheduler's continuation
interface using the stored-evidence adapter, local clock, retained store and
one-use HMAC gate. It copies local boot/command/session/plan identities so they
cannot change through caller string mutation during admission. Token/store/gate
lifetimes remain owned by the calling runtime. Admission itself performs no bus
access; fresh state and storage checks still run before the return write.

The integrated native harness now uses the finite pair, real publisher/store,
Python-signed synthetic request and Windows HMAC verification. A matching request
produces exactly one forward and one return write, reaches the frozen count 2902,
and saves seven return records. Rejection leaves the pair stopped with just the
forward write. Sixteen signed scenarios cover each stored-record mutation, wrong
digest/signature/target/session/plan, expired envelope, duplicates, neighbor
movement after acceptance and return-store failure before dispatch. Sixteen
focused pytest cases pass across the broader set of harnesses.

This is still simulation with a synthetic key and initial session identities.
Initial pair authentication, concrete hold-to-pair runtime and network collector,
host hardware-export-before-signing, and embedded allocation review remain to
integrate. Rollover is exercised in the harness; the installed r7 application has
not changed and exposes no pair route. No hardware command or deployment occurred.

## Exact-byte host archive and replay implemented — simulation origin only

`held_leg_raw_export.py` saves ordered kind/base64-raw pairs alongside independent
plan, policy, digest and derived assessment. It reopens the saved export through
the manifest verifier, decodes bounded raw bytes, checks kind/schema agreement,
recomputes the native-compatible digest and independently repeats endpoint
assessment before returning `replay_verified`. Export SHA identifies the complete
bundle attachment; evidence SHA identifies the controller's ordered raw records.
They are deliberately distinct. These APIs neither sign nor send commands.

Tests use native publisher output for arrival, non-arrival and failed acquisition.
They verify identical cross-language evidence hashes, exact whitespace retention,
post-save corruption rejection and rejection of semantically altered archives
even when those archives have valid manifests (origin/authority promotion, changed
digest/assessment, malformed base64 and wrong storage kind). Sixteen focused
pytest cases pass. Hardware remains untouched.

This path explicitly accepts SIMULATION only. A concrete hardware transport and
initial session linkage must establish collected-evidence origin; accepting an
arbitrary caller-provided DEVICE_CAPTURE flag would not establish provenance.
Next integrate the native session bridge and collector, then reuse this raw-byte
archive/replay procedure in the hardware path before permitting host signing.

## Stored forward evidence connected to native signature gate

`held_stored_return_admission.h` requires a completed ARRIVED leg, matching
original anchor, exactly the expected record count and a healthy store. It
reconstructs every snapshot/action/terminal record from the retained native
owner and compares byte-for-byte against stored records in publication order.
Only then does it derive the local evidence digest and invoke the existing
one-use HMAC return gate with locally supplied session/forward-plan identities.
The adapter itself is one-use even when matching fails. It performs no bus I/O.
The terminal serializer is shared with publication to prevent format divergence.

Ten native signed-request cases cover exact matching, mutations to each of seven
stored records, incorrect signed evidence digest and invalid signature; every
case also checks duplicate rejection and unchanged bus read/write counts. Tests
use synthetic keys and bus reads, not a device. Sixteen focused pytest cases pass
across stored admission, cross-language digest, pair/leg, publication/replay,
pinned-library wire and return admission.

Remaining: the top-level authenticated session must supply frozen initial
session/plan identities, call this adapter from its continuation bridge, retain
exclusive ownership, and roll over evidence only after acceptance. Host durable
raw export/replay before signing and embedded allocation review remain pending.
The adapter currently conservatively requires the initial forward count to
equal the frozen original anchor; it does not silently substitute a drifted
anchor. No deployment, provisioning, or live command occurred.

## Shared exact-byte evidence digest implemented and cross-tested

`held_evidence_digest.h` and `held_evidence_digest.py` compute the same bounded
record-chain SHA-256 identity without parsing/reserializing JSON. This avoids
host JSON key-order differences silently changing what the controller signed.
The host must retain raw bytes, not recreate them from parsed objects.

Protocol: H0 = SHA256(ASCII `rocell.held-evidence-chain.v1` followed by one NUL).
For each zero-based record i, Hi+1 = SHA256(Hi || uint16-BE(i) || uint8(kind-length)
|| ASCII kind || uint16-BE(raw-length) || raw JSON bytes). Return the final digest
as lowercase hex. Accept 1..34 records, only kinds `held_leg_scan`,
`held_leg_action`, `held_leg_end`, and 1..4095 NUL-free raw bytes per record.
Native failed stores reject hashing. Order, kind, index, lengths and exact bytes
are bound. This protocol is an identity, NOT arrival/provenance/durability proof.

Differential tests feed actual native publisher output from three simulated
outcomes (arrival, non-arrival, failed read) through Python and Windows native
SHA-256; hashes match. Ordering, truncation and whitespace mutations change the
digest. Invalid bounds/types are rejected on the host. Fifteen focused tests
passed including owner/pair, actual store/publisher, replay, wire and return HMAC.
Removed redundant nested execution of base-owner test cases inside the publisher
harness after reproducing a host stack overflow; base-owner tests still run
separately. No deployed code or hardware was changed.

Next connect this locally computed digest and verified forward records to the
one-use return gate, then make the host verify/replay durable raw export before
signing. Neither a digest alone nor a valid terminal label permits progression.

## Actual fixed-store integration exposed and corrected terminal-save defect

The earlier vector-backed publisher test accepted arbitrary record-kind lengths.
`EvidenceStore` accepts at most 15 characters, but `held_leg_terminal` is 17.
The new actual-store test reproduced a publication fault at terminal capture.
The internal routing label is now `held_leg_end`; JSON schema remains unchanged
as `rocell.held_leg_terminal.v1`. No store layout or installed firmware changed.

A second integration harness now runs the finite pair with the actual publisher
and `EvidenceStore<34,4096>`, preserving the forward terminal before test-only
store/publisher rollover, then capturing the return under a distinct command ID.
Both offset signs complete with two writes, seven records per leg, frozen return
2902, and no extra I/O during the continuation wait. Seven focused pytest cases
pass across scheduler/storage, raw replay, pinned-library wire and HMAC admission.

The first expanded publisher harness overflowed the host's default stack; placing
its additional large owner/store off-stack resolved that test issue. Embedded
allocation and total-memory measurement remain required. Initial integration
work was redirected to this demonstrated storage defect; production signed
continuation plus durable host export is still NOT connected. Pair integration
tests continue to use synthetic admission, not live movement authority.

## Finite mechanical pair scheduler implemented — not deployed

`held_elbow_pair_owner.h` now drives a bounded Forward -> AwaitingExport -> Return
-> Complete lifecycle. It freezes the original held count, constructs the forward
target from a bounded signed offset without clamping, requires cross-leg binding,
and never polls the bus while awaiting continuation. Non-arrival, uncertain
dispatch, changed state, failed publication/admission or lost boundary health
stop progression. There is no third leg, automatic return, retry or torque release.

The scheduler retains one leg owner in aligned reusable storage. It copies the
forward endpoint before reconstructing that same storage for the return; forward
raw evidence remains intact until continuation accepts. A host-ABI size assertion
guards against accidentally duplicating the entire 32-scan owner. This is NOT an
ESP32 memory-budget measurement: evidence store, JSON allocations, network stack,
hold owner lifetime and runtime free heap still need integrated review.

Six focused pytest harnesses passed. The new native harness covers both signed
directions, exact frozen return, waiting without I/O, stuck motion, lost ACK,
publication failures, rejected/duplicate continuation, between-leg neighbor
movement, boundary revocation, terminal repolling and invalid offsets.

Important remaining integration: this mechanical core uses an injected driver
and continuation interface. Tests use synthetic admission, not production
authority. The actual runtime must authenticate initial entry, supply a verified
hold endpoint, pair driver polling with raw publication, derive local evidence
identities, connect `HeldReturnAdmission` and host durable-export replay, and roll
over the publisher/store only after accepted continuation. No live route uses
this class. Installed r7 remains hold-only; no deployment or live move occurred.

## Cross-leg state continuity implemented — offline only

`HeldElbowLegOwner.bind_start` copies the preceding verified endpoint's seven
positions, goals and torque states before the new leg starts. Every fresh
pre-dispatch scan must agree with that retained state within the existing
position tolerances; neighbors remain checked against it after dispatch too.
A changed baseline cannot silently become acceptable just because it is stable
within the new leg. The return target remains the constructor's frozen value,
not a recalculated offset from a later reading. Rebinding, incomplete snapshots,
or binding after acquisition fault the owner without further bus activity.

Five focused pytest harnesses passed, including native forward/return binding,
between-leg position/goal/torque changes, repeated binding, incomplete state,
publisher/replay regressions, pinned-library fake UART and HMAC return admission.
This adds only a compact seven-joint state copy, not a second scan history.
No hardware commands, firmware installation or provisioning occurred.

Integration remains required: only the finite session may supply a successfully
verified preceding endpoint, it must require binding for both displacement legs,
freeze the original return target, authenticate plans, and verify durable forward
export before return admission. The standalone owner's optional binding is not
itself authorization. Embedded memory budgeting and the full session are pending.

## Native one-use return authentication gate implemented, not integrated

`held_return_admission.h` uses the existing HMAC challenge envelope but requires
the distinct canonical `rocell.held_return_authorization.v1` payload. It compares
the request with locally supplied boot/session/forward-plan/raw-evidence hashes
and original anchor. It rejects requests without prior forward arrival, invalid
HMAC, expired/not-yet-valid challenge, changed target/identities, simulation origin,
extra fields, noncanonical encoding or invalid export digest. Every attempted
gate is one-use, including rejection. No bus access or movement is exposed.

Native Windows HMAC test passed 14 cases, each also rejecting a repeated consume.
Tokens, keys and evidence in this test are synthetic. This is not a deployed
continuation endpoint. The signed export digest is the host's assertion of saved
evidence; firmware cannot independently inspect the host filesystem. The host
must verify durable export/replay before signing, and the outer native owner must
derive forward-arrival/local hashes itself, freeze the original anchor, retain
exclusive ownership and reacquire fresh state before dispatch. Those integration
steps, finite hold/forward/return lifecycle and embedded memory review remain.

## Pinned-library packet path tested — simulated UART only

`test_held_leg_servo_wire.cpp` runs the native leg owner through the unchanged,
hash-verified SMS_STS/SCS/SCSerial implementation with a host-only HardwareSerial
emulator. It verifies packet checksum, servo ID14, write address41, acceleration,
little-endian target/speed, zero time bytes and exact equality with retained
argument encoding for forward 2908 and return 2902. It also covers non-arrival,
lost/corrupt write acknowledgment after simulated actuation, corrupt read checksum
and wrong read-response ID. Terminal repolling adds no packets; invalid baseline
reads cause zero writes. No torque, mode, broadcast or recovery writes are used.

The initial combined harness failed because the reused test main, renamed to a
regular function, lacked an explicit return. Adding `return 0` fixed this test-only
undefined behavior; the pinned production library was not changed. Both pinned
wire test variants then passed. These are software packets on a fake UART, not
independently measured packets or motion on the real arm. Next implement the
finite session's authentication and export-gated return, with memory budgeting.

## Independent host replay and simulation exports implemented

`held_leg_replay.py` accepts independently supplied target/tolerance/identity and
hashed policy. It reconstructs all raw register snapshots and checks acquisition
ordering, scan/age/gap budgets, baseline spacing, held control state, neighbor
invariants, exact encoded command and successful acknowledgment, postwrite goal
readbacks, movement corridor, separated settling and deadline coverage. It derives
VERIFIED_ARRIVAL or VERIFIED_NON_ARRIVAL before comparing the terminal label.
Missing/invalid/uncertain or contradictory evidence remains INCONCLUSIVE. All
outputs remain explicitly SIMULATION with no progression authority or provenance/
wire/tip-accuracy claim; authenticated native session integration is still pending.

Exporter retains records, independent plan/policy and assessment, then manifest
checks and recomputes the assessment on replay. Native fixtures cover arrival,
stuck non-arrival and failed read. Mutation tests reject changed identities,
targets/policy hashes, write bytes/ack/timing, scan order, missing scans, goal
changes, out-of-corridor position and contradictory terminal state. All three
fixture outcomes exported and replayed. Twelve focused tests passed. No hardware
access or firmware installation occurred. Next: real pinned-library fake-UART
coverage, integrated authenticated session and memory budget; no live trial yet.

## Single-leg raw publisher implemented — offline only

`held_leg_evidence_publisher.h` reserves 34 record slots before polling the owner:
up to 32 raw whole-arm snapshots, one action and one terminal. Records retain raw
read bytes/timestamps/statuses plus write encoding/acknowledgment. Snapshot and
terminal schemas are leg-specific; action uses the existing raw hold-action
schema within a distinct `held_leg_action` envelope kind. Publication failure
faults the owner and latches the publisher; neither performs subsequent bus I/O.
Failure to initialize the publisher prevents even baseline reads.

The native publisher test passed success, valid non-arrival and partial-read
failure; Python independently decoded successful/non-arrival raw snapshots.
Tests also failed each of the seven publication positions on the success path
and verified no subsequent reads/writes. This is record serialization coverage,
not complete independent endpoint replay or physical/wire validation.

Next add independently supplied plan/policy binding and full host replay of
timing, target, direction, settling, terminal consistency and fault semantics.
Then integrate pinned-library wire tests and authenticated finite continuation.
Record reservation is RAM capacity, not durable host export. The larger 34-slot
store plus snapshots must be measured/budgeted before embedded integration; it is
not allocated in the installed r7 firmware by this offline-only change.

## Native single-leg core implemented — offline only

`held_elbow_leg_owner.h` implements a one-use single-leg state machine. It acquires
two held baseline snapshots plus a fresh prewrite scan, requires torque=1 and
goal/position agreement, validates count displacement and envelope, reserves one
write, records its argument encoding/acknowledgment, then samples all seven joints.
Elbow movement is checked against a bounded start/target corridor; neighbors keep
their baseline goal/torque and drift limits. Two separated settled in-band samples
are required for arrival. Complete valid sampling through deadline without arrival
can produce NotArrived; invalid feedback/goal/control/direction/timing, lost ack,
ownership loss, storage exhaustion or export failure produces Fault/inconclusive.
Terminal polling does not read or write again. No enable/release/reset API exists.

The native test compiled and passed, including forward and reverse arrival,
stuck position, lost ack, wrong goal, wrong direction, disabled elbow, neighbor
drift, ownership failure, export failure, observation gap, and each of 140 raw
read failure positions. This uses a synthetic register bus, not physical movement
or the real UART wire implementation. Return in this test is a separately created
test object, NOT implemented/authorized production continuation.

Remaining before deployment: raw publisher and independent replay integration,
pinned-library fake-UART coverage, finite session authentication/continuation,
hold-plus-leg composition, storage/heap budget, full candidate build/review,
wizard integration and separately approved deployment/live testing. The core
retains up to 32 scans; runtime memory budget has not yet been qualified. No route
in the installed firmware exposes this core, and no hardware action was performed.

## Starting evidence and scope

The supported-pose r7 hold succeeded at 2902 counts: requested/encoded target,
goal readback and final position matched; torque became 1; five snapshots showed
no neighboring-joint change. Export:
`wizard-20260918T230821752067Z-164698b57d1148429f455b24fce52c15`.
This is not a displacement test. The installed runtime is one-use hold-only and
its session is consumed. Do not invoke old stock movement routes or reset/rearm
it implicitly. No camera, contact, typing or compensation in this next trial.

## Proposed first displacement trial

Use native servo counts first to separate command transport/register behavior
from Cartesian/angle conversion. Elbow ID14 only, speed 20, acceleration 1.
Proposed legs: fresh admitted anchor A -> A+6 -> A. A must be established by
fresh stable scans after hold initialization, not copied from the old export.
At the historical anchor 2902 this illustrates 2902 -> 2908 -> 2902.
Both targets must remain within the approved pose envelope; never clamp targets
or widen the envelope automatically. Six counts exceeds twice the proposed
two-count endpoint tolerance so arrival bands cannot overlap. This is a small
diagnostic displacement, not a clearance guarantee or physical-accuracy claim.

The second leg is an explicitly planned reverse movement, not fault recovery.
It is allowed only after first-leg verified arrival AND successful export/readback.
On any failure stop where the controller is; never auto-return, release torque,
reset, reissue a command, or proceed to a third leg. Keep links supported since
other joints have not been enabled or qualified.

## Implementation sequence

1. Build an offline draft from replay-verified hold evidence. Retain source export,
   plan/policy hashes, prior boot, count units and proposed offsets. Mark draft
   non-authoritative; firmware/provisioning and powered trial approval remain
   separate. Reject overlapping endpoint bands and targets outside the envelope.
2. Implement a bounded native per-leg owner reusing `HoldStateSnapshot`, pinned
   SCServo encoding/ack capture and exclusive-bus checks. Do not reuse the hold
   owner's initial-position drift check for commanded elbow motion: check elbow
   against per-leg trajectory bounds and neighbors against their baseline.
   Require position-mode elbow, torque=1, moving=0 and fresh goal agreement
   before each dispatch. Freeze A once; return target must not track drift.
3. Integrate hold initialization and displacement under one explicit finite
   session in a new reviewed candidate. A firmware reset may invalidate torque
   and position assumptions; re-establish hold rather than trusting prior evidence.
   Keep only one owner active and budget storage/heap for all raw scans/actions.
4. Distinguish per-leg outcomes: verified arrival (valid fresh goal/position and
   settled observations), verified non-arrival (complete valid endpoint sampling
   through deadline, no other fault, outside target tolerance), and inconclusive
   (bad/missing/stale/conflicting evidence, uncertain delivery or export failure).
   A wrong goal register is command-path discrepancy, not positional compensation.
5. Publish raw records before host assessment. Add a one-use, exact-leg/hash-bound
   continuation admission AFTER durable verified export of the first leg. Do not
   make the return automatic inside a timer or use a response timeout as permission.
   Late/duplicate/wrong-boot continuation must be rejected without a servo write.
6. Extend host replay and wizard to show requested counts, encoded command bytes,
   acknowledgment, first/final goal, pre/post positions, direction, signed error,
   dwell/timing and neighbor changes for each leg. Distinguish controller reports
   from independently measured wire traffic or stylus-tip coordinates.
7. Test native owner plus real pinned-library fake-UART path: exact forward/return,
   non-arrival, wrong-direction movement, stale/repeated reads, torque/mode changes,
   neighbor drift, lost write reply, export failure, expired/duplicate continuation,
   and power/reset between legs. Assert zero further writes for every failed case.
8. Compile and review the complete candidate before requesting deployment;
   preserve backups and protected regions. Obtain explicit deployment/provisioning
   and bounded live-trial approval. No implementation milestone alone enables motion.

## Completion and progression

First milestone is one exported, replay-verified forward/return pair with actual
nonzero controller-position changes of the expected signs. Then repeat finite
pairs in both starting directions and compare errors before changing speed or
adding joints. Compensation requires repeated bias and held-out validation, not
a single zero-error hold. Later combine qualified joints for noncontact ghost-key
approach/press/retract. Camera registration and physical contact remain deferred.
