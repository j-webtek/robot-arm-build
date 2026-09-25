# Single-use diagnostic start authorization

Status: host signing, native authentication/admission/session composition, bounded
body receiver and offline tests exist; **not an enabled or installed endpoint**.
Implementation: `rocell.application.servo_start_authorization`. This does not
provision a key, send a command, upload firmware, or grant workspace clearance.

## Contract

The controller creates one challenge for its current boot. It contains a 128-bit
boot ID, a fresh 256-bit random nonce, and issued/expiry times from the controller's
monotonic clock. Maximum lifetime is 30 seconds. Host wall-clock time is not used.
The host freezes a baseline-bound session-plan (v3 for whole-arm admission) and signs its exact canonical
bytes. The plan's command boot ID must match the challenge.

Binary wire format, in order:

| Field | Encoding |
| --- | --- |
| Domain | ASCII `rocell.diagnostic-start.v1` followed by NUL |
| Boot ID | 16 decoded bytes |
| Challenge nonce | 32 decoded bytes |
| Issued time | unsigned big-endian 64-bit microseconds |
| Expiry time | unsigned big-endian 64-bit microseconds |
| Plan length | unsigned big-endian 16-bit byte count |
| Plan | exact canonical session-plan bytes, 1–16384 bytes |
| Authentication tag | HMAC-SHA256 over all preceding bytes, 32 bytes |

Use a separately generated, cryptographically random 32-byte shared authorization
key. Never reuse Wi-Fi credentials, use the public test fixture key, or log/export
the key or usable signed token. The challenge is public, not a credential. HMAC
authenticates integrity and possession of the key; it does not encrypt the request
or authenticate unsigned telemetry responses. Secure provisioning remains open.

## Controller order

1. Receive through the single controller owner; bound request bytes before parsing.
2. Reject a previously consumed challenge. Consume a terminal attempt before any
   parsing, admission, acknowledgment, or dispatch. No refund on failure/lost reply.
3. Require `issued <= now < expires`, using controller monotonic time.
4. Verify the tag in constant time and require the exact issued challenge bytes.
5. Verify the length and independently validate the complete canonical plan,
   including boot identity, native-execution origin, original payload, mapping,
   schedule, and baseline policy. A valid MAC never replaces semantic validation.
6. Apply controller-side approved workspace limits and fresh whole-arm/servo
   admission. The host-supplied bounds are not automatically trusted clearance.
7. Retain the plan identity and original request, then invoke exactly one native
   diagnostic write through the existing receipt/conversion/session path.
8. Capture/export the resulting evidence. Any uncertainty stops progression;
   never retry a start because its response was lost.

The reference gate consumes even an invalid attempt. This intentionally allows
denial of service from unauthenticated traffic, but never authorizes movement.
Restrict network access and rate-limit ingress before deployment. A future re-arm
protocol must be explicit; recreating a gate automatically defeats single-use
semantics. Do not reboot to clear the gate as an automatic retry.

## Completed and remaining

Completed: exact-byte signing, challenge validation, immutable plan validation,
single-use reference state machine, default rejection of simulation-origin plans
by native-mode verifier, and mutation/replay/expiry/wrong-key tests. Tests also
independently lay out the binary envelope and sign a malformed plan to verify
that authentication cannot bypass plan validation.

Remaining before live exposure: native HMAC verification using the pinned ESP32
crypto implementation on actual hardware; provisioning and revocation; reviewed
controller-owned policy/clearance; static owner allocation and runtime memory;
owner-only bounded HTTP framing/start handling; firmware compatibility and
authorized backup/deployment. Native plan parsing, command evidence identity and
whole-arm baseline composition are tested offline, not verified on the arm.
The diagnostic HTTP reader remains GET-only.

No claim is made yet that the controller implements this protocol. Keep
`start_supported=false` until the native path and its tests are complete.

## Native envelope verification checkpoint

`firmware/diagnostics/start_envelope.h` implements the consumed-before-verify
state machine with bounded framing, exact challenge comparison and a full-tag
constant-time comparison. It owns a copied key and erases that copy on destruction.
It returns only a borrowed authenticated byte view, not an admitted command.
The caller must retain immutable request storage while parsing. The gate is
single-owner, not a concurrent HTTP handler or thread-safe admission primitive.

`start_crypto_esp32.h` delegates HMAC-SHA256 to the pinned core's mbedTLS library;
it does not implement a custom hash. A nonexecuted compile probe checks ESP32
link compatibility. Host C++ tests use Windows BCrypt and verify Python-signed
requests through the actual gate. Cases include changed signatures and payloads,
correctly signed wrong challenges/lengths, expiry/rewind, truncation, oversize,
replay, invalid key/lease, and cryptographic-provider failure.

The tests intentionally show that an authenticated `{}` body passes the envelope
gate. It must subsequently fail semantic plan validation. Do not connect the
envelope gate directly to servo dispatch. Hardware execution of mbedTLS vectors,
native plan validation and admission remain unverified.

## Native structural validation checkpoint

`strict_plan_json.h` bounds input to 16384 bytes, object depth to five levels,
members to 80, keys to 64 bytes, and string values to 512 bytes. It rejects
whitespace outside strings, escaped/non-ASCII strings, arrays, booleans/null,
duplicate or unordered keys, invalid number syntax and trailing input before
ArduinoJson parsing. This restricted grammar covers the current ASCII session
plan; it is not a general-purpose JSON parser or proof of canonical numeric spelling.

`start_plan_structure.h` then requires exact root/nested fields, DEVICE_CAPTURE
origin, caller-selected boot and conversion identity, elbow joint 3/servo 14,
rad/count units, bounded identifiers, finite angles, profile-range counts, exact
T101 payload shape, matching payload/wire angle, and bounded compatible sampling,
assessment and baseline policies. Simulation-origin plans are rejected.

The `parse()` stage checks only the shape of the payload hash and encoded original
bytes. It must be followed by `bind_payload()` described below. Neither stage
proves canonical numeric spelling or supplies physical admission.

Tests execute the actual C++ parser against a valid host-generated plan and 33
malformed variants. The compile probe retains the parser without executing it.

## Original payload and conversion binding checkpoint

After successful structural parsing, `bind_payload()` hashes the exact sorted
payload-object bytes retained from the plan, using SHA-256, and compares the
declared payload hash. It strictly decodes `sent_base64` into at most 256 bytes,
including validating standard alphabet, padding position and zero padding bits.
The original bytes pass through the existing strict one-use controller receipt
parser. Parsed angle, speed and acceleration must match the plan; receipt parsing
also enforces T101, elbow joint 3, exact fields and no trailing input.

Only then does binding call the reviewed **no-write** conversion adapter, for both
wire angle and desired angle. Both results must match the plan's respective
expected counts. The reference adapter restores its temporary shared goal value.
Binding never silently corrects a count mismatch or applies compensation.

On success the parser owns and exposes the exact original command bytes, preserving
field order/whitespace for the later native receipt. Failure exposes no payload.
Reparsing clears prior binding state. No servo access is provided by this stage;
the injected converter must be the reviewed pure reference adapter, not the
fresh-baseline/read/write admission adapter.

Host C++ tests use Windows SHA-256 and the exact conversion functions extracted
from the manifest-verified reference archive. Positive fixtures accept canonical
and reordered/spaced original commands. Negative fixtures cover payload/hash/count
mismatches, duplicate/trailing content, wrong joint/settings, embedded NUL,
oversized decoding, invalid alphabet and padding. Tests assert zero servo writes
and restoration of the shared goal value. ESP32 probe uses mbedTLS SHA-256.

## Composed single-use owner checkpoint

`authorized_start.h` now composes envelope verification, structural parsing,
payload/conversion binding, evidence reservation/publication, admission callback,
expiry recheck, and a single start callback. It owns its parser and copied bound
request. Keep the native owner instance out of a small controller task stack;
runtime memory margin remains unverified. It has no network route or servo API.

The `authorization` record has schema `rocell.start_authorization.v1`, boot and
command IDs, exact session-plan SHA-256, request time and expiry, and
`authentication_verified=true`. Its `phase=BEFORE_ADMISSION` and
`dispatch_attempted=false` describe that point in the sequence, **not** the final
outcome or evidence that no later movement occurred. No key or signed token is
published. Host collection/assessment must be extended for this new prefix before
enabling it on hardware.

Host-prefix update: collection now accepts this record ahead of receipt/baseline
evidence on boot-bound v2 transport, checks its identity against transport and
receipt, and retains the exact response bytes. Planned assessment checks the exact
frozen plan hash, phase, controller claim, nine-pair capacity and time window through
receipt/write start. Both complete and supported partial-failure assessments can
include the non-secret `start_record` assessment. Raw records remain linked through
export/replay. Authorization-only/incomplete captures remain evidence-rejected,
not inferred successful starts or inferred proof of no movement.

The wizard labels this **controller-reported** authorization and separately shows
that authenticated telemetry provenance is not verified. Unsigned HTTP JSON cannot
prove the device performed HMAC verification. A matching pre-admission record never
overrides session faults, supplies endpoint proof, or grants progression authority.
Credential redaction remains unchanged; no usable signed token or key is exported.

The extra record limits this path to nine sample pairs in the 16-slot store.
Larger plans are rejected, not silently reduced. Authentication/plan failures
cannot reach admission; reservation/publication/admission/expiry failures cannot
reach start. A failed start callback is `START_NOT_VERIFIED`, not a promise that
the command was never delivered, and no second attempt is allowed.

The current tests compose actual native authentication, parsing, hashing and
reference conversion with **inert admission/start callbacks**. They check callback
ordering, plan-hash identity, rejection and no replay. They do not prove fresh
whole-arm clearance or hardware dispatch. ESP32 compile/link also succeeds without
executing the probe. Actual native admission/start adapters, retained outcome
integration, host prefix support, provisioning, compatibility and explicit
deployment authorization remain required. `start_supported` stays false.

## Whole-arm baseline reader checkpoint

`whole_arm_baseline.h` implements one read-only scan of servo IDs 11–17,
including both shoulder servos. Through the pinned read adapter it acquires a
fresh goal register and feedback block for each ID, retaining raw pair evidence,
statuses, timing and sequences. It stops after the failing bounded pair and never
retries or reads subsequent joints. The instance owns a copy of its supplied policy.

Policy supplies each servo's allowed count interval, tracking tolerance, maximum
pair duration, whole-scan duration and oldest-read age. Both target and position
must remain inside the controller-reviewed interval; moving flags must be zero
and target/position differences within tolerance. Supported raw range is 0–4095,
not a universal physical joint limit. Installed model/register compatibility must
be established before using it. Test intervals are synthetic, not approved live poses.

The freshness check ages from the **first goal-read start**, not the final joint,
and must run again immediately before dispatch. Backward/expired time irreversibly
invalidates the baseline. Reads are sequential, not simultaneous. Successful
reported state does not establish obstacle clearance, mechanical coupling accuracy,
or an independent physical position measurement.

Tests exercise success and five failure types at every servo ID, invalid policies,
scan timing, oldest-read staleness and no revival/retry. This reader is not wired
to a live bus owner/start handler yet. Raw evidence serialization, capacity budgeting,
host recomputation and the final pre-write freshness check remain integration work.

### Compact whole-arm evidence format and host checker

`whole_arm_baseline_json.h` now emits `rocell.whole_arm_baseline.v1` with boot/
command identity, pinned profile, explicit little-endian order, copied policy,
controller decision/reason/check time and retained reads. `reads[i]` identifies
servo `11+i` and contains `[target_read, feedback_read]`. Each read is the array
`[sequence, started_us, finished_us, returned_bytes, device_error, success, raw_hex]`.
Target address/width is fixed at 42/2; feedback at 56/15. Failed bytes are null;
device error -1 means unavailable. Failed scans may contain fewer than seven rows.

The serializer preflights size and clears output on failure. Tests establish that
accepted evidence with 128-character identities and near-maximum signed-64-bit
timestamps fits a 2048-byte record. Failure to serialize must still block start;
no truncation is permitted. One aggregate record adds one slot to the composed
path; the final owner must reserve it before admission rather than borrowing a
sample slot or silently shortening a plan.

`servo_whole_arm_baseline.assess_whole_arm_baseline` takes an independently frozen
policy, acquisition boundary and actual write-start time. It expands each compact
row through the existing read-pair validator, checks every joint window/tracking/
moving flag, and recomputes scan duration and oldest-read age at dispatch. It grants
neither physical clearance nor progression. Incomplete/rejected scans remain raw
failure evidence and cannot pass this positive-admission checker.

Native output passes host assessment and verified standalone export/re-read tests.
Altered identity/policy/sequence/time/moving data is rejected. Full session-prefix
integration, frozen policy binding in the session plan, native admission wiring
and final dispatch-time freshness remain unfinished; no live endpoint is enabled.

### Host v3 session-plan integration

Session-plan v3 freezes `whole_arm_policy` alongside the elbow baseline policy.
The eight-record prefix is `authorization`, `whole_arm`, `receipt`, `baseline`,
`converted`, `hook`, `dispatch`, `write`; at most eight acquisition pairs fit the
16-record store. Freeze rejects a larger requested count rather than changing it.
V1/v2 plan handling remains supported without claiming whole-arm verification.

Collection recognizes the aggregate record only after authorization on boot-bound
transport, checking contextual identity through receipt. V3 planned assessment
requires both records, binds authorization to the v3 plan hash, independently checks
the whole-arm policy and raw reads, enforces scan completion before native receipt,
and recomputes oldest-read age at actual write start. Session faults remain faults.
Wizard reporting separates the seven-servo baseline result from physical clearance.
Full session export/replay includes the immutable policy and these assessments.

The v3 integration test combines a simulated whole-arm/authorization prefix with
inert native session output; it is not a single hardware run. Native structural
parsing and host signing still support v2 only at this checkpoint. Do not attempt
to transmit v3 until the native parser/owner is upgraded and integrated. Partial
v3 failures remain retained raw evidence but are not yet independently classified.

### Native v3 and controller-owned policy equality

The host signer and native structural/binding path now support v3. The lexical
preflight permits bounded numeric arrays; semantic validation accepts exactly
seven two-count joint windows only in the required whole-arm policy field.
Boolean/string/object substitutes, reversed/out-of-range windows and unknown
fields remain rejected. V3 cannot parse without a controller-supplied approved
policy; every window, tolerance and timing limit must match it exactly.

The native owner copies that approved policy at construction. A request cannot
widen its limits even with a valid HMAC, and later mutation of the caller's policy
does not change the owner's copy. Bound request metadata includes the matched
whole-arm policy. V3 reserves eight prefix records and allows eight sample pairs;
v2 retains its historical seven-record/nine-pair budget.

Native tests sign v3 through the host and exercise actual authentication, parsing,
payload hashing and reference conversion before inert admission/start callbacks.
They accept matching policies, reject missing approval and signed policy changes,
and verify copied-policy behavior. No live policy values have been selected or
approved by these synthetic fixtures. Actual fresh-baseline callback and final
pre-write freshness enforcement remain required before enabling an endpoint.

### Final native write-boundary guard

`WriteBoundaryGuard` is now threaded through `ReceivedSession` and
`DiagnosticSession` to `ReferenceWriteCapture`. The hook samples its monotonic
write-start time and evaluates the predicate immediately before `WritePosEx`.
The predicate must be bounded/nonblocking and do no bus I/O or writes; it is for
rechecking retained whole-arm freshness, authorization expiry and owner fault state.

Denial consumes the hook and stops the session with `WRITE_NOT_ATTEMPTED`, retaining
a hook outcome `PREWRITE_REJECTED` and `write_attempted=false`. No dispatch or ACK
record is fabricated when no library write occurred. Evidence publication failure
also prevents progression; a refused attempt cannot be retried through that session.
The default empty guard preserves older offline/native interfaces, so authenticated
v3 wiring must explicitly require and supply the real guard before exposure.

Tests exercise the actual received-session/write hook with a freshly acquired
seven-servo baseline on an inert bus. A delay introduced while publishing the
converted-command record expires the baseline and causes zero writes, demonstrating
that an earlier admission check alone is insufficient. Expired authorization,
owner fault and publication failure also prevent writing. This proves software
ordering under test, not physical braking or real-device timing. Integration of
the mandatory v3 guard and raw whole-arm record into the live candidate is pending.

### Integrated read/admission/session adapter

`admitted_session.h` now supplies the actual admission and start callbacks for the
authenticated owner. It requires v3 policy equality, a supplied owner-fault check,
bounded sample count and reserved evidence capacity. It reads/exports the whole-arm
baseline, retains a copy of the bound request, and refuses changed requests at start.
The receipt path then performs the reviewed no-write conversion again, reads and
exports the fresh elbow baseline, and invokes the existing finite session with a
mandatory final boundary guard. That guard checks whole-arm age, elbow age,
authorization expiry and owner fault state at the write hook. The sample path
also terminates on owner fault. No network route is registered by this adapter.

The integrated native test now runs a host-signed v3 plan through actual BCrypt
authentication/hash checks, pinned reference conversion, whole-arm/elbow readers,
receipt/write hook and three feedback pairs, using only an inert bus. Simulated
feedback starts at 2128 counts and changes to the requested 2132 after the single
simulated write. The resulting native records pass host planned assessment and
verified export/replay without a synthetic prefix. Movement/physical-accuracy
claims remain false. Additional cases inject whole-arm read failure, conversion-
publication delay, owner fault, baseline publication failure and failed write ACK;
all prevent further progression/retry, with exactly one attempted write in the ACK
failure case and zero writes in the preceding-admission failures.

This completes library-level composition, not deployment: actual embedded owner
allocation, routes/status mapping, secure provisioning, policy selection, memory
margin and compatibility/recovery review remain pending. Joint count windows do
not independently establish collision clearance or measured stylus accuracy.

### Unified owner lifecycle and status

`AuthenticatedDiagnosticOwner` now owns the authorization/admission/session lifetime
and is noncopyable. It references a single bus, clock, evidence sink, converter and
crypto implementation; all must outlive it. Admission rejection is a terminal FAULT
even if no inner session started. Export failure and interference latch the first
owner reason and prevent subsequent acquisition. External fault and failed evidence
storage stop the next sampling call without bus reads. Duplicate starts do not retry,
reset or erase evidence. Status reads do not themselves sample hardware.

The shared bounded status encoder is used by the existing GET route and the new
owner test; serialization failure clears truncated output. Start support remains
false because no authenticated start route is deployed or exposed. The native
integration fixture emits this actual status followed by actual evidence records;
host assessment and export/replay consume them together. Ten inert modes include
four post-start stop conditions. Five focused tests and the ESP32 compile/link probe
passed; see the main plan for the verified build export. This is software integration,
not installed firmware or proof of actual arm motion.

### Start body reception

`StartRequestBody` receives at most 16507 bytes into owned fixed storage. Declared
length is bounded before copying; a monotonic total deadline is at most three
seconds. No acquisition occurs until a complete body is explicitly finished and
the authenticated owner accepts it. Partial/excess input, timeout, clock reversal
and disconnect terminate the attempt and fault the owner. Token bytes are erased
after terminal processing and are never exported. The type is noncopyable and
must live outside small callback stacks.

This adapter does not parse HTTP: the eventual transport must reject duplicate or
conflicting Content-Length, Transfer-Encoding, unsupported methods/content types
and extra framing, and must actively time out disconnected/silent clients. It must
not use an unbounded WebServer body allocation before this limit. Tests cover the
body adapter with the actual authenticated owner, including twelve receipt cases;
no network start route or provisioning is implied.

### Restricted HTTP framing adapter

`start_http_request.h` now performs that framing step on raw input before any
general-purpose HTTP body allocation. It accepts exactly `POST
/rocell/diagnostics/start HTTP/1.1` with one each of Host, Content-Length,
Content-Type (`application/octet-stream`) and Connection (`close`). Header names
are case-insensitive; values follow this intentionally narrow client contract.
Unknown fields, duplicates, transfer encoding, Expect, header folding, bare-LF
framing, invalid lengths, unsupported paths/methods and excess body bytes are
rejected. Header storage is bounded to 2047 bytes plus NUL; signed-body storage
retains the existing 16507-byte limit. One total deadline covers headers and body.

The transport must feed raw socket bytes, call poll while a client is silent,
call abort on disconnect, and close after every terminal result. It must drain
already-available input through feed before finish so excess buffered bytes are
rejected. A valid declared-length request is complete without waiting for socket
EOF; bytes arriving after a terminal result are not another authorized request.
No connection reuse or retry is permitted. This adapter owns no sockets and
registers no live routes. Host headers are syntactic routing information, not
authentication or device identity.

The actual authenticated native owner is tested through this adapter with valid
whole-request and byte-at-a-time input. Malformed requests are tested at both
fragmentation extremes; disconnect, silent timeout, clock reversal and bad HMAC
also prevent bus reads/writes. A discovered blank-header-terminator rejection was
fixed before the positive tests passed. Embedded allocation, socket-loop wiring,
provisioning/policy and reviewed deployment still remain.

### Accepted socket lifecycle

`StartSocketSession` now connects the parser to a nonblocking accepted socket. Each
poll reads at most 512 bytes, and even a silent client is checked against the total
deadline. It waits for would-block after complete input before committing, so
already-buffered extra input is rejected. EOF/error aborts even if buffered data
previously looked complete. A terminal result sends one short HTTP response and
closes; no reconnection or second request is accepted. Partial, failed or would-block
reply sends produce RESPONSE_UNCERTAIN and fault the owner without retry. A complete
local send still does not prove delivery to the host; the host must never resend
on a lost response. 202 denotes local admission, not endpoint verification.

`Esp32StartSocket` uses MSG_DONTWAIT recv/send on a dedicated NetworkClient fd,
avoiding the normal write method's internal select/retry loop. Do not use buffered
NetworkClient reads or another server/parser on that same client. The client and
owner references must outlive the connection. Listener registration, static storage,
provisioning/policy and application scheduling remain to integrate. No sockets are
opened by construction, and compile-probe functions are never executed.

Pinned source review: ESP32 core 3.0.7 NetworkClient.cpp SHA-256
`e7c418dd4364404c414f528cd36cbba00eb7db1dac5451fdb3272bb634a1762b`;
NetworkClient.h SHA-256
`e0dfd8822fc48c4bc8c4e6340f2ae0555056f1709d0d27140251439caf79e317`.
Seven inert connection cases exercise the actual parser/authenticated owner.
Host tests and ESP32 compile/link pass; this is not runtime network/hardware proof.

### Listener ownership and capture scheduling

`StartListener` now supplies the accepted-connection orchestration. The caller
provides a server, retained client, connection, owner, clock and challenge expiry.
All references must remain valid; no port, key or physical policy is invented by
the listener. It checks startup and deadline, accepts at most one client, closes
the listener before processing that request, and never reconstructs or retries.
After the request becomes terminal it polls the owner only while SAMPLING, until
CAPTURED or FAULT. Later polling cannot accept another client or acquire more data.

Five inert scenarios cover full three-pair capture, listener startup failure,
expiry before acceptance, backward clock and a lost command reply. The complete
success path uses the native authenticated owner and actual reference conversion
with an inert bus. The ESP32 compile probe instantiates NetworkServer/NetworkClient
against pinned core 3.0.7; the probe is never called by setup/loop. Production
configuration loading, static allocation, challenge discovery and coexistence with
read-only evidence routes still need to be integrated into a distinct candidate.

### Controller-owned configuration and separate key material

`controller_diagnostic_config.h` adds strict local policy parsing, capped at 4096
bytes, with duplicate/unknown-field rejection and no defaults. Policy JSON uses
the existing sorted-key, compact ASCII grammar. Root schema is
`rocell.controller_diagnostics.v1`; required fields are:

- `policy_id`: bounded diagnostic identity for the reviewed local policy.
- `conversion_version`: must match the caller's compiled expected conversion ID.
- `start_port`: explicit nonprivileged TCP port, 1024–65535.
- `challenge_lifetime_us`: positive, at most 30000000.
- `elbow_bounds`: minimum/maximum radians within [0, pi], maximum speed and
  maximum acceleration, all explicitly supplied.
- `whole_arm_policy`: seven ordered count windows plus tracking tolerance and
  pair/scan/age budgets, using the same ranges as the native whole-arm gate.

This validates representability and consistency, not clearance, a safe speed or
measured accuracy. Reviewed values still must be selected for the actual setup.
Successful parsing copies the policy into owned storage; a later parse failure
invalidates and clears it rather than retaining an old valid policy.

`DiagnosticKeyMaterial` reads a separately opened binary file of exactly 32 bytes
and closes it on success or failure. It never creates/repairs a file, logs a key,
or substitutes defaults. Zero keys and the public byte-sequence fixture 0..31 are
rejected; this is not an entropy test or a comprehensive weak-key detector. Actual
provisioning must generate a cryptographically random key. Failed reads clear
previous key material; destruction/clear uses volatile erasure. Caller copies
must also be erased after the authorized owner has copied the key.

No real policy/key file was created or read. Inert tests cover malformed policy,
unsupported conversion, types/ranges, duplicate fields, size limits, missing and
short key reads, invalid lengths and the rejected key patterns. Production file
paths, permission/revocation handling and runtime wiring remain to integrate.

### Configured runtime composition

`ConfiguredDiagnosticRuntime` now owns the entire object graph in aligned storage:
evidence store, local-policy converter, crypto provider, listener/client, socket
adapter, authenticated owner and finite capture scheduler. Initialization is
single-use, including failed initialization. It takes compact local policy bytes,
the compiled conversion ID, loaded key material, boot/nonce and external owner
fault callback. It does not open files or generate identities. A failed policy,
missing key, invalid time, owner fault or listener failure cannot fall back to an
uninstrumented command path. Temporary key bytes are erased after owner creation.

Place the runtime in static storage; referenced library and clock must outlive it.
Destruction closes sockets and destroys the owner/key. Records stay in the same
owned store used for admission and capture. Accessors expose status and records
without additional hardware reads. No endpoint-accuracy claim or durable export
is inferred from CAPTURED. A native test clears caller policy/key storage after
initialization, then completes the signed request and three feedback pairs through
the actual runtime; emitted records pass host assessment and export replay.

This composition has not yet been bound into the full candidate's boot, filesystem
and challenge/status routes. The separate compile probe instantiates the ESP32
network/library types and statically allocates the runtime, but does not execute
it. Final provisioning, full firmware memory, hardware compatibility and recovery
still require review before explicit deployment authorization.

### Full candidate wiring

The separate configured firmware candidate now binds the runtime to startup and
read-only status/record routes. The first challenge GET loads the local policy and
separate binary key, generates a nonce using ESP32 hardware RNG after Wi-Fi startup,
and initializes one listener. Repeat GETs return the original challenge, including
after expiry, never a refreshed nonce or lease. The host uses the port from its
reviewed policy; the exact challenge schema does not add an unsigned port field.
File loading is read-only and failures produce 503 plus a faulted runtime. There
is no upload, provisioning or configuration-edit HTTP endpoint.

Status schema v3 signals that this candidate implements authenticated starts;
it does not assert current availability or deployment approval. Terminal v3
collection uses the same v2 record envelopes and independent host assessment.
During finite work the loop services the runtime before read-only WebServer work,
and skips that potentially blocking server while request/capture is active.
The full candidate compiles with pinned dependencies. Actual provisioning, board
compatibility, backup/recovery, memory headroom and authorized live validation
remain outstanding; see the deployment review for exact build evidence.

### Explicit host POST adapter

`DiagnosticStartSender` is a low-level, one-use client, not an automatic wizard
action. It requires a native v3 frozen plan, the exact challenge and dedicated key,
then emits the four-header binary POST expected by the candidate. Construction
performs no network access. Only explicit numeric RFC1918/loopback destinations
are accepted; no DNS, proxy, redirect or legacy fallback is used. It consumes its
attempt before preparation and never retries on any outcome.

The total connect/send/reply budget is at most ten seconds. This is distinct from
the controller's three-second request-reception budget: the controller then needs
time for admission reads. A timeout may therefore mean the command was attempted,
not rejected. The report marks transmission attempted before sendall and leaves
delivery uncertain after a partial send or invalid/lost reply. A valid 202 or 400
records only controller-reported acceptance/rejection; even rejection is not proof
of zero servo writes, because admission/write verification could have failed after
an attempted write. Neither response proves endpoint arrival or host export.

Reports contain plan/command identity and a bounded response body/hash, never keys
or signed request bodies. The application still must verify durable pre-send plan
storage, installed compatibility and local policy before calling this adapter, and
then retrieve/assess/export terminal evidence. Creating another sender object is
not an authorized retry. The adapter is not wired to live startup or any existing
motion action. All new network tests use loopback; connection/partial-send faults
are injected without a real device.

### Pre-send publication and challenge consumption

`send_prepared_start` now validates and snapshots the request, publishes/verifies
the plan and public challenge, then uses the existing exclusive reservation writer
to consume boot+nonce before calling an injected sender. It creates no socket or
sender itself. Existing/incomplete claim files block even a new sender instance;
concurrent attempts have one reservation winner. Claim identity intentionally
excludes plan/command/expiry fields so editing them does not refund the nonce.
Claims are never automatically removed, repaired or treated as proof of dispatch.

Recognized delivery outcomes, including uncertainty, are exported and reread after
sending. A pre-send export/verification/reservation failure makes no sender call.
A post-send export failure leaves the claim consumed and must stop progression.
Unexpected process errors also leave the claim intact; absence of a delivery
report cannot justify retry. The reservation's presence means possible dispatch,
not verified motion. Keep the export root stable and do not bypass a claim by
changing folders. Physical-volume qualification and deployment admission remain
separate requirements; no new wizard or hardware action has been enabled.

### Explicit discovery and later capture linkage

`DiagnosticChallengeReader.discover(expected_boot)` is deliberately separate from
read-only telemetry collection. It invokes the challenge GET at most once, binds
the exact validated challenge to the expected current boot, and retains its raw
response and hash. It cannot prove authenticated device identity or freshness of a
previously issued challenge; native expiry checks remain authoritative. Generic
GET collection still cannot invoke this route. No discovery is automatic.

`collect_started_run` takes a saved prepared-start export and an injected read-only
reader. It first verifies the saved plan/challenge, delivery identity and exact
consumed claim. It then captures/assesses terminal evidence and exports hashes
linking the send record to the planned-run result. `replay_started_run` rechecks
those links, the claim and the underlying assessment. Neither function constructs
or invokes a sender. Missing or inconsistent evidence cannot turn HTTP acceptance
into verified motion. A lost reply can therefore be investigated without resending.

Tests cover wrong/duplicate challenges, altered claims, uncertain-send fault capture
and successful linked assessment of records emitted by the native inert runtime.
Automatic wait/poll scheduling and wizard admission remain separate; calling
collection while the controller is still busy may fail rather than auto-retry or
re-arm. Actual firmware deployment and physical endpoint validation remain pending.

### Wizard review of saved attempts

The offline `review_started_servo_run` action accepts a started-run export ID from
the assigned export folder. It independently replays the linked claim, delivery
record, capture and assessment, then renders host-delivery status separately from
endpoint evidence. A completed review is never hardware qualification; uncertain
delivery remains uncertain even when reviewing the file succeeds. The UI states
that the challenge claim remains consumed, with no automatic resend. It rejects
inconsistent authority fields and the service rejects altered claims/exports.
This action creates no connection or sender and does not change arm connection
state. Live submission still requires separate reviewed admission and deployment.
