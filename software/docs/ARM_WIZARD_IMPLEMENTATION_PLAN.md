# Arm-to-wizard implementation plan

Plan ID: `ROCELL-ARM-WIZARD-001`  
Created: 2026-09-12  
Status: **working implementation plan; remaining milestones not implemented**  
Scope: received RoArm-M3 Pro, USB serial, existing RoCell wizard, static overhead
Arducam B0477 camera, keyboard and Android placemat tasks.

## Current handoff status — 2026-09-12

Latest actual capture (23:24 UTC) succeeded end to end through the public wizard:
56,384 bytes, 255 complete parsed pose samples, 323 timestamped reads, zero writes,
clean closure and verified export. See `MOVEMENT_TELEMETRY_TIMING.md` for IDs,
hashes and parser-coverage limitations. Motion qualification remains incomplete.
The following earlier failure is retained as historical evidence.

Actual telemetry capture (23:05 UTC): COM7 supplied 56,320 bytes in five seconds,
including 255 validated complete pose samples. Zero writes; all three serial
resources closed. The native collector completed, but the public operation
FAILED because the expanded report exceeded the supervisor's JSON node limit.
Original evidence/export remain unchanged. Fixed the transport representation to
retain all raw bytes plus a compact reconstructed summary; 48 regression tests
passed. Offline reanalysis of actual data passes the unchanged IPC limit and the
telemetry validator at 85,605 bytes. No second capture was needed for this fix.
This proves received unsolicited telemetry, not command-response causality,
voltage/torque state, calibration or movement readiness. See the attempt report.

Public telemetry action now implemented: `capture_powered_arm_telemetry` shares
the powered startup/identity/source/one-attempt gates, but selects the immutable
zero-write purpose. It presents sample count and latest observed known fields,
keeps absent optional fields visible, and exports original native bytes through
the existing powered diagnostic attachments. Empty captures remain FAILED with
`NO_COMPLETE_TELEMETRY_SAMPLE`; received samples do not grant motion authority.
Sixteen public/coordinator regression tests passed with simulated worker results.
The next gate is fresh operator setup confirmation for a five-second COM7 capture.
No live telemetry capture has yet run; earlier missing-public-action notes below
are historical and superseded by this increment.

Telemetry worker integration increment: native child now selects the zero-write
collector only for the telemetry intent; the closed archive includes collector,
framer and result validator. The validator reconstructs every parsed record from
retained bytes, enforces zero writes and checks completion/cleanup claims.
Seventy-nine offline tests passed, including isolated import checks with native
access forbidden. No valid live telemetry request was dispatched. Remaining:
coordinator/public action, concise UI presentation, export tests and a fresh
operator-confirmed COM7 capture. Earlier "child not wired" notes are superseded.

Next increment: a distinct `POWERED_UNSOLICITED_TELEMETRY_ZERO_WRITE` intent now
fixes maximum writes/outbound bytes at zero. The native API rejects writes for
that purpose, and query lifecycle entry rejects telemetry intents. Added the
bounded five-second telemetry collector, integrating raw framing, byte/read-call
limits, cancellation, resource cleanup and separately retained late-cleanup input.
Fifty focused offline tests passed; no physical telemetry capture was dispatched.
Remaining immediate integration: native child dispatch/result verification,
source-pinned archive roster, coordinator/public action, exports and UI tests.

Software increment after COM7 observation: `rocell.arm.telemetry_stream` now
provides bounded incremental unsolicited-telemetry framing with raw-byte retention,
explicit invalid-line/tail spans, missing-field reporting and no freshness,
query-response or motion authority. Fifteen offline tests passed. Reanalysis of
the actual retained 256-byte capture found a rejected 90-byte prefix and a
166-byte unfinished suffix, zero complete samples, with byte-for-byte retention.
This pure parser has no device access. The powered read-only collector, worker
integration and public wizard action are still to be implemented and tested;
the existing query path remains unchanged and rejects preexisting input.

Latest update (22:46 UTC): after the operator switched board USB sockets, the
ESP32-side candidate appeared on COM7, serial `52E4E1E8337FEF119E92181CEDD322A4`.
The wizard received 256 bytes containing T1051 robot telemetry fragments before
writing anything. It deliberately stopped with `PREEXISTING_INPUT` and closed
all resources cleanly. This establishes received robot-protocol data on the new
endpoint, not a validated complete feedback sample or command-response round trip.
Do not reuse the prior COM6 unit serial as the arm's control endpoint. Next:
implement bounded, zero-write telemetry-stream observation and framing with
original-byte retention; keep unsolicited samples distinct from solicited replies.
No movement or contact has been commanded. Details in the attempt report below.

Latest update (22:38 UTC): a second, explicitly confirmed public-wizard attempt
completed one 10-byte T105 write and closed all three serial resources cleanly.
It received zero reply bytes in five seconds and failed with
`FEEDBACK_DEADLINE_EXCEEDED`. The previous token-validation bug did not recur.
Feedback/pose/voltage and physical qualification remain unproven. The next check
is the actual board USB socket and OLED state, not an automatic retry. Both
attempts and verified exports are recorded in `POWERED_FEEDBACK_LIVE_ATTEMPT_20260912.md`.

Latest received-unit evidence (22:32 UTC): the public wizard matched the known
CP210x unit on COM6 and performed one native powered attempt. It opened the port
once, verified serial settings, then failed with `REUSED_IO_TOKEN` before any
outbound bytes. Serial cleanup was unconfirmed; the supervised process tree
exited. This is **not** successful feedback, movement or calibration acceptance.
The failed original and verified export remain unchanged. See
`POWERED_FEEDBACK_LIVE_ATTEMPT_20260912.md` for IDs, logs and the offline fix.
No live retry has occurred. The next physical attempt needs a current operator
observation after the port-open event, including whether startup movement occurred.

The software now provides supervised **memory-only** powered-feedback rehearsal,
five fixed scenarios, original-byte/process-log exports, durable powered attempt
records, one-use child claims, and read-only powered history inspection. The
execution ledger below and `POWERED_FEEDBACK_WIZARD_CHECKPOINT.md` contain exact
scope and test evidence. These are not live connection or calibration acceptance.

Current source: `powered_feedback_observation.py` now has separate rehearsal and
live-claim-admitted physical lifecycle entries. The shared backend accepts only
the exact admitted native facade and rejects ordinary/unadmitted construction.
There is now a separate physical child, closed supervisor registration, and a
public physical coordinator/action tested with simulated worker outcomes. The
received-unit live attempt has now failed before writing the query. A working supervised rehearsal
must not be presented as a finished live arm connection. Physical adapter startup movement was reported by
the operator, not produced by a wizard motion command.

The operator has now confirmed firmware **unchanged since delivery** and has
freshly confirmed the arm secured, stationary, clear, adapter-powered/ON and
USB-connected. The firmware-history blocker is resolved; do not ask it again
unless new information contradicts the report. These are operator reports, not
proof of an exact installed version/hash or measured power. See
`ARM_RECEIVED_FIRMWARE_HISTORY.md`. Do not substitute vendor download hashes for
received-unit identity. Use this basis to finish
the powered native API, source-pinned physical worker registration, coordinator
and journal joins. A fresh physical setup confirmation is required before the
eventual live attempt; historical USB/power reports are not renewed by this audit.

Full arm/camera-to-board calibration, bounded movement and keyboard/phone contact
tests remain unfinished. Do not mark the goal or A6–A10 complete. Additional
rehearsal success does not resolve the operator-evidence decision or those
physical milestones. The latest actual hardware access is recorded above;
earlier memory-only increments below retain their original scope.

## Earlier increment — powered-feedback original preparation

Connected `PoweredFeedbackIntent` to a bounded preparation helper that reopens
the exact public powered-startup original, verifies its hash, launch/source,
operator reports and unchanged timestamp, and reconstructs native identity from
the full generic review. It binds startup, identity, runtime/profile and protocol/
firmware-review byte originals to the request. Full generic-review bytes are
retained too, so a child need not borrow a later mutable UI selection.

Prepared evidence is immutable bytes and reports
`POWERED_ORIGINALS_ASSOCIATED_NOT_AUTHENTICATED`. Runtime and review hashes alone
do not qualify executable code or authenticate a firmware review; these remain
separate admission requirements. No fallback values, fabricated firmware identity,
native access, or current calibration approval are introduced.

Verification: **32 tests passed**, including preparation from the actual public
startup producer with fixture metadata/reviews, missing/changed originals, source
mismatch, path rejection, stale setup, timestamp-renewal rejection and altered
generic review. Test root:
`software/runs/pytest-powered-feedback-preparation-20260912-02`.
No feedback or motion command was sent. Next implement authenticated review/runtime
admission and the one-write worker/journal/service composition; A6 remains pending.

## Previous increment — fixed powered-feedback intent

Verified the vendor's documented T105/T1051 feedback semantics and recorded the
source and remaining installed-firmware uncertainty in
`POWERED_FEEDBACK_PROTOCOL_REVIEW.md`. Asked the operator whether the received
firmware has been modified; no answer has been assumed.

Added `PoweredFeedbackIntent`, a separate immutable domain from USB-only passive
requests. It permits only the existing fixed T105 encoding, one open/write,
bounded startup/response buffers, no retries and fixed observation/cleanup
budgets. It requires distinct original startup, native identity, protocol review,
firmware compatibility, source/runtime and serial-profile references. Clock
checks reject stale/future startup and insufficient cleanup lifetime. Parsing or
hash syntax never creates dispatch permission, and no raw command or motion
field is accepted.

Verification: **32 tests passed in 2.59 seconds**, covering fixed encoding,
domain separation, exact limits, boolean-coercion rejection, missing evidence,
clock checks and prior powered setup/passive preparation. Test root:
`software/runs/pytest-powered-feedback-intent-20260912-01`.
This is request-contract preparation, not a released feedback executor. Next
connect original-evidence preparation, bounded one-write provider/process and
public wizard execution without manufacturing canonical A5/A6 acceptance.
No hardware access or arm command occurred during this increment.

## Previous increment — powered-startup wizard record

Added the physical-mode **Record powered arm startup** action and immutable
original producer. It records explicit operator reports of external adapter ON,
USB connected, secured/clear workspace, stationary behavior and whether startup
motion was observed. It labels these as operator reports, not sensor readings:
voltage is unmeasured, installed firmware identity remains UNKNOWN, and canonical
power-stage acceptance, feedback permission and motion permission remain false.

A powered-startup report invalidates this session's USB-only setup before file
publication, including when saving fails. It cannot leave an old passive setup
available for the powered configuration. Export logs preserves the original
bytes and independently rechecks their hash; no serial endpoint is opened by
recording or exporting the report.

Verification: **81 tests passed in 5.03 seconds**, covering the action catalog,
powered record/export, false-checkbox rejection, physical/rehearsal separation,
USB-only invalidation on success and storage failure, plus prior passive actions.
Test root: `software/runs/pytest-powered-startup-record-20260912-01`.

Recorded the actual operator's preceding startup/reconnect reports through the
new public action (not a new physical observation):

- Operation: `operation-a9939b6e2ce44458bb2ba90970e57d97`.
- Original SHA-256:
  `299cfb48e683df28254fd5fa69dbe48cfad763e9b3bc29127384444471264e16`.
- Verified export:
  `software/runs/wizard-exports/wizard-20260912T205818999074Z-35cbf151ae2e4a2d87ef0fb28e4086c1`.

This advances A5 evidence recording but is not canonical A5 acceptance and does
not release A6. Next bind a separately reviewed powered-feedback request to
actual identity/firmware evidence and this distinct power/startup context. No
motion or feedback command was sent during this increment.

## Previous observation — adapter-powered startup and stable USB reconnect

Following the passive test, the operator confirmed the arm was assembled and
secured, connected the supplied adapter and switched it on. With USB initially
still attached, no startup movement was reported. The operator then removed USB
and powered the arm using the adapter alone; reported startup motion and supplied
a photo showing the raised/extended pose. The operator confirmed the arm was
stationary without shaking or persistent grinding/buzzing, and subsequently
reported **USB reconnected and stable** while adapter power remained on.

Current reported configuration is **external adapter ON plus USB connected**,
not USB-only. The earlier passive setup attestation must not be reused for this
configuration. No assistant-originated motion command has been sent. Startup
motion is operator-reported firmware behavior, not a verified commanded-motion
test or calibration result. No electrical voltage measurement was obtained.

Read-only pySerial port enumeration after reconnect found the same controller:
COM6, VID:PID `10C4:EA60`, USB serial `A02C8734397FEF11A7321C1CEDD322A4`,
location `1-8.3`. Enumeration did not open the endpoint or prove firmware identity.

Remaining software gap: `owned_arm_feedback_runner` still blocks its physical
composition. The USB-only passive lane must not be used with a false
power-disconnected declaration, nor should a raw transport bypass replace the
missing powered-feedback implementation. Next implement/verify the powered
startup evidence and bounded feedback-only admission under A5/A6 (or an explicitly
scoped prebuild engineering lane that does not claim canonical predecessor
completion). No additional power cycle is needed merely to continue software work.

## Previous increment — first real passive serial observation, 2026-09-12

After the operator freshly confirmed USB-only power, secured mounting and clear
movement radius, ran the public wizard metadata/setup/passive actions once.
Actual received-device metadata correlated successfully. The retained native
observation reports **OBSERVED_CLOSED**: one port open, verified serial settings,
four seconds of observation, zero outbound bytes, zero startup bytes, no
communication errors, two acquired/two closed handles, no unresolved resources
and no pending I/O. No initialization, torque, home, motion or contact command
was sent. This establishes the bounded passive port/settings lifecycle only;
with no received bytes it does not establish firmware identity or command/feedback
communication. No live command session remains open.

Evidence:

- Original session: `wizard-5f3f706c2a984be49c108c5ca0adf72e`.
- Setup: `operation-22db8808068d4e3f9a9188bc29680e2a`.
- Single hardware attempt: `operation-6e729ad8566441d7b0d9583998645287`.
- Immutable prepared/consumed/claimed/outcome files are in
  `software/runs/wizard-diagnostics`, keyed by that attempt ID.
- Outcome journal SHA-256:
  `d9726866e421c9ae75b8b301fa8dadd4c3312a5a765a985e11e069bcd16717d9`.
- Native result SHA-256:
  `3fd267cffc9926b00ecf66d3f158cc9c7a344521fa4f6c5f86081ae995a4491a`.
- Verified historical recovery export:
  `software/runs/wizard-exports/wizard-20260912T202315925322Z-55d589560d114b4baf3f176327bf2a52`.

**UI/export defect found during the real attempt:** the native child/process
succeeded and its raw outcome was durably saved, but embedding the entire nested
wire result inside the wizard summary exceeded its nesting budget. The public
operation therefore correctly retained a `RESULT_RETENTION_LIMIT` failure, and
its initial general export also failed. Do not rewrite that original operation
as an end-to-end wizard success.

Fixed the summary to omit the full parsed wire tree from the process display
while retaining a compact observation summary. Exact wire bytes remain in the
original outcome journal. **15 regression tests passed in 2.48 seconds**,
including a nested native-result presentation case. Test root:
`software/runs/pytest-passive-live-retention-20260912-01`.
Without repeating hardware access, a new wizard session inspected the saved
attempt and exported it successfully; export verification passed and every
exported stage matched the original file bytes. The corrected display path has
not yet been exercised by a second physical run.

Next: obtain the operator's observation of any reset/movement during the test,
then separately qualify firmware/feedback access. External actuator power stays
disconnected pending the appropriate powered-test preparation. Calibration,
keyboard contact and Android tapping are still unverified; the plan is not
complete. Historical source-held wording in the original lifecycle limitations
is not a new hardware finding and does not override its recorded native effects.

## Previous increment — broader wizard regression, 2026-09-12

Ran the passive connection path together with the general wizard service,
HTTP/terminal interface tests, action catalog, rehearsal/history, owned-process
supervisor and claim-reservation tests. The first run had 359 passes and one
stale expected-action catalog: five deliberately added passive actions were
missing from the test's explicit set. Updated that set without weakening its
exact-membership assertion or changing production behavior.

The complete rerun passed: **360 tests in 53.99 seconds**. Test root:
`software/runs/pytest-passive-wizard-regression-20260912-02`.
These are software/interface, fixture and process-lifecycle results, not actual
received-device acceptance. No arm port was opened and no motion command sent.

The next live step is paused pending a current operator confirmation that the
arm is secured, its movement radius is clear, USB is connected and the external
power adapter is disconnected. An automatic goal continuation is not that
confirmation. After confirmation, acquire fresh metadata/setup and run one
supervised passive attempt; retain/export its actual result before deciding the
next hardware step. The overall integration goal remains incomplete.

## Previous increment — scoped passive native admission, 2026-09-12

Implemented and connected the fixed child worker's scoped native admission.
`claim_for_child` registers the exact issued claim object in process-local memory;
copied, reconstructed or already consumed claims cannot release an API. The
passive factory consumes that live object, rechecks the retained claim chain,
entry-original freshness, exact selected endpoint and newly acquired metadata.
The identity must still be within one second at open, with the request's reserved
observation/cleanup lifetime available. Failed admission/open burns the attempt.

Ordinary `WindowsPassiveSerialApi` construction and the general native API remain
held. The admitted passive API alone reaches the internal native loader; it still
rejects all writes, allows one exact endpoint/open, and keeps cleanup available
after a deadline. This is trusted in-process composition, not a security sandbox
against arbitrary Python code. Parent runtime/source pins and child journal
checks remain part of the required composition. The lifecycle identifies this
path as `WINDOWS_PASSIVE_SERIAL_ENGINEERING`, never command commissioning.

The public action now warns explicitly that serial opening can reset the
controller or change control lines. With fresh operator setup it can attempt
actual serial observation; it is no longer unconditionally native-held. No
physical attempt has been performed on the received arm in this increment.

Verification: **140 tests passed in 6.33 seconds**, covering admission, fixed
package/supervisor, native call bodies, wire, serial lifecycle and public action.
New tests reject copied/reused claims and stale identity, verify expiry before
DLL loading, and run an admitted API against a fake DLL while confirming cleanup
after expiry. Native device access was forbidden or replaced with fake calls.
Test root: `software/runs/pytest-passive-admitted-composition-20260912-02`.
The first admission test fixture incorrectly blocked Windows filesystem DLL use;
its guard was narrowed to the serial loader. Production file safety was unchanged.

Remaining before claiming connection: fresh operator USB-only/secured-clear
confirmation and a supervised real attempt through the wizard. Its outcome may
expose actual-driver or hardware issues not covered by fixtures. Powered tests,
received firmware verification, calibration and keyboard/phone contact remain
unverified; do not mark the integration plan complete.

## Previous increment — native call-body tests and outcome mapping, 2026-09-12

Exercised the production ctypes call bodies against a wholly fake DLL, distinct
from the higher-level memory serial provider. Coverage includes exclusive
overlapped open arguments, DCB/timeout marshalling and readback, rejection of
unreviewed settings, passive query rejection before DLL calls, pending reads,
cancellation and terminal/uncertain completion. Buffer pins remain retained
after cancellation requests, timeouts and unconfirmed completion, and are removed
only after terminal completion. Test-only monkeypatches replace both the release
hold and DLL constructor; production release policy is unchanged. These tests
do not qualify the actual Windows serial driver or received device.

Replaced the wizard's blanket failed-attempt wording with outcome-specific
publication: software native-release hold (not an arm fault), cancellation,
timeout, uncertain process cleanup, failed journal persistence, or completed
bounded observation. Even an observed-and-closed success grants no connected
command session, commissioning approval or motion authority. Success wording is
covered by a modeled presentation test, not a physical acceptance result.

Verification: **122 tests passed**, covering the new native-call and presentation
tests plus serial backend, public wizard action, bound wire and supervised-child
regressions. Test root:
`software/runs/pytest-passive-native-readiness-20260912-02`.
No actual native DLL or serial endpoint was used by the new ctypes tests.

Next: complete the scoped native-release admission implementation and verify
its composition before requesting fresh operator setup for one real zero-write
USB-only observation. Powered tests, calibration and contact remain incomplete.

## Previous increment — physical attempt inspection after restart, 2026-09-12

Added **Inspect saved physical passive attempt** to the public wizard catalog.
It accepts only an exact saved `operation-` ID and reads the four known filenames
from the launcher's assigned log directory. It does not accept a path or discover
other folders. Unlike the older rehearsal-history action keyed by session ID,
this action reads physical-attempt journals and preserves partial records.

The UI receives compact file statuses and hashes; Export logs includes the
original collected bytes in `physical-passive-history.json`. Collection success
means readable historical bytes were found, not valid hardware evidence. Missing
all records or an unreadable record produces a failed inspection. No record is
repaired, executed or converted into a current setup receipt. To inspect after
restart, launch with the same assigned log directory and enter the operation ID
from the previous attempt's diagnostic report.

Verification: **24 tests passed in 3.71 seconds**. A real new service instance
using the same test log directory inspected/exported a deliberately partial claim
while its current setup remained absent and its live action remained blocked.
Other cases covered unknown IDs, path rejection and prior public setup/action
and export regressions. Test root:
`software/runs/pytest-passive-restart-history-20260912-02`.
The first test run exposed missing fixture-directory initialization; corrected
the test fixture only. No received hardware was accessed.

Next: qualify the native passive connection implementation and its end-to-end
result handling, then perform a fresh operator-supervised USB-only observation.
Powered checks, calibration and verified typing/tapping remain incomplete.

## Previous increment — complete current-attempt file export, 2026-09-12

Added `passive_arm_attempt_export.collect_attempt`, a bounded read-only collector
for the exact prepared/consumed/claimed/outcome filenames. Exports preserve
original bytes and SHA-256 hashes, including malformed partial records, in
bounded base64 chunks. Missing and unreadable records are explicit; collection
does not parse them as permission, repair them, retry, or prove device cleanup.
The output explicitly disclaims an atomic snapshot and authentication.

The service pins the attempt ID before preparation, independently of any returned
process outcome. Export logs includes `passive-arm-attempt-files.json` even if
preparation failed before creating a journal or process. It preserves existing
export size limits and fails explicitly rather than silently truncating originals
that exceed the attachment budget. Exact binary diagnostics are not text-redacted;
review exported contents before sharing.

Verification: **37 tests passed in 4.70 seconds**, including public action/export,
setup, journal and supervised-child regressions. New coverage verifies exact
consumed-original collection, preservation of a deliberately corrupted partial
claim, path rejection and export following a preparation storage failure. Test
root: `software/runs/pytest-passive-history-export-20260912-02`.
All new hardware inputs are fixtures; no received arm endpoint was opened.

Remaining: public inspection/recovery of these physical attempt files after a
wizard restart, qualification of the native passive connection path, real USB-only
observation, powered tests, calibration and verified keyboard/phone contact.

## Previous increment — public passive action and log export, 2026-09-12

Added the physical-mode catalog action **Run supervised passive arm test** and
connected it to ArrivalWizardService and PassiveArmCoordinator. It requires a
successful setup receipt no older than five minutes, current matching native
metadata and the same generic selection. Preview context is checked again before
queueing and dispatch. Each launch permits one attempt; failures do not enable
automatic replay. The closed provider's native-serial hold is unchanged.

The service retains the original bounded process outcome outside recent-result
rotation and validates the displayed result against its own publication. The
new effectful result deliberately does not invent zero device-effect counters.
For now it reports the engineering attempt as failed/not qualified, never as a
connected arm; later qualified native release needs explicit outcome mapping.

Export logs now includes `passive-arm-process-logs.json`, with independently
hashed exact stdout/stderr in bounded base64 chunks, including when saving the
outcome journal failed. The attachment warns that binary logs are not text
redacted and should be reviewed before sharing. Full journal-stage attachment
export and interrupted-attempt recovery remain to be integrated.

Verification: **20 tests passed in 5.01 seconds**, covering public setup/action,
coordinator and existing supervised-child regression tests. The new public
action tests cancel before child creation and use synthetic hardware metadata.
They verify missing/changed setup rejection, durable cancellation, replay
blocking and exact export round-trip of synthetic 256-KiB output. Test root:
`software/runs/pytest-passive-live-action-20260912-02`.
No received arm endpoint was opened; live native qualification, calibration,
keyboard contact and phone tapping remain unverified and incomplete.

## Previous increment — service coordinator implementation, 2026-09-12

Added `application/wizard_passive_arm_coordinator.py`. This service-side owner
selects the fixed isolated runtime, prepares an attempt from the retained public
setup receipt, checks current service state, consumes the journal before
dispatch, runs the supervised worker and saves its raw outcome. One owner permits
one attempt, including failed preparation. It never selects an executable or
journal path from browser input. The caller must supply service-owned context
and a current-state check; the supervisor invokes that check again at admission.

Publication failure returns an explicit `OUTCOME_PERSISTENCE_FAILED` result
alongside the complete raw process result for the service to retain and export.
It does not retry, claim connection, or equate process exit with serial cleanup.
Native serial loading remains held by the existing provider.

Verification: **15 tests passed in 4.10 seconds** across the new coordinator,
public-setup preparation and existing supervised child tests. The coordinator
tests use synthetic hardware metadata and pre-cancelled dispatch: no received
device was accessed. They verify saved cancellation, rejected foreign receipts,
changed-state rejection before consumption, one-use ownership and explicit
failure with in-memory raw output when journal publication raises. Test root:
`software/runs/pytest-passive-coordinator-20260912-01`.

Remaining: wire this coordinator into ArrivalWizardService and the public action
catalog, retain its result beyond recent-operation rotation, export full attempt
records/raw logs, then qualify native release and perform operator-supervised
physical testing. The new coordinator is not yet a working live wizard button.

## Previous increment — complete passive output retention, 2026-09-12

Fixed a prerequisite for the wizard service coordinator: the supervisor allowed
256 KiB of stdout while the attempt journal accepted only 128 KiB. A valid-sized
worker failure could therefore lose its durable diagnostic outcome. The journal
now accepts the full 256 KiB stdout and 8 KiB stderr budgets; native registration
validation uses those same constants so the limits cannot silently diverge.
Base64-encoded streams remain within the existing one-MiB journal record bound.
The record format is unchanged, and earlier smaller outcomes remain readable.

Verification: **43 tests passed in 5.21 seconds**, including exact binary-output
round trips at both maximum sizes, rejection one byte beyond either budget,
no retry after rejected outcome publication, package loading, registration,
supervised child execution and child claims. Test root:
`software/runs/pytest-passive-output-budget-20260912-01`.
Oversized output is not silently truncated or reported as success: the retained
consumption remains an unknown outcome with replay prohibited.

No received arm endpoint was opened and no motion command was sent. The live
wizard service coordinator, full-attempt export and qualified native release
remain unfinished; this increment does not complete physical onboarding.

## Previous increment — supervisor integration and claim reservation, 2026-09-12

Connected the exact passive-native protocol to `OwnedWindowsWorker`:

- Validates fixed registration and retained consumed originals before pinning.
- Rechecks the consumed original immediately before child execution; a changed
  journal blocks thread resumption. Other physical protocols remain held.
- Uses the dedicated detached, pipe-only `WindowsOwnedPassivePipeProcess`,
  preserving the existing path/file pins, suspended creation, atomic Job
  assignment, handle/memory budgets and cleanup. This avoids a hidden console
  host spending the passive child's one-process budget.
- Validates the bound wire result and ties the returned claim digest back to
  the exact retained claim and consumption record. Process exit still proves
  neither serial cleanup nor physical acceptance.

The first supervised run exposed Win32 error 32 during the child claim's
rename-based publication. It occurred before metadata or serial access and was
retained as failure. Changed **only claim publication** to
`publish_reservation_bytes`: exclusive CREATE_NEW of the final name, write-through,
flush and readback, without rename. An interrupted/partial final record remains
occupied and blocks replay. This is a reservation, not atomic complete-record
publication; prepared/outcome records and canonical ledger publication retain
their original atomic scheme. Directory sharing/reparse protections were not
weakened. The reservation was verified while those same directory pins were held.

Verification: **144 tests passed in 23.07 seconds**, across supervised child
handoff, reservation interruption, claim/journal recovery, registration/wire,
real package loading, prior process ownership and durability. Test root:
`software/runs/pytest-passive-supervisor-regression-20260912-01`.
The supervised child actually started, saved its exclusive claim and rejected a
deliberately malformed setup before enumeration. Its tree exited; raw stderr was
retained and saved as the journal outcome. Replay was rejected before creating
another process. Cancellation and authorization-time journal corruption also
prevented child execution. All hardware inputs were test fixtures.

**Native serial loading remains held; no received arm endpoint was opened.**
Remaining: service coordinator to prepare/consume/dispatch/retain/export through
wizard live Start; scoped native release; complete public-path acceptance; then
the approved USB-only received-hardware observation. Feedback, calibration and
keyboard/phone contact milestones remain incomplete.

## Previous increment — owned native wire protocol, 2026-09-12

Implemented `providers/windows/passive_native_wire.py`, included it in the fixed
child archive, and changed the child observation command to require the owned
process envelope rather than accepting a bare handoff.

Request decoding checks exact fields, protocol/worker identity, envelope hash,
inner passive request, registration digest, attempt/session/source/selection and
exact deadline equality. Recomputing an envelope hash cannot conceal an inner
binding mismatch. Result encoding/validation binds the response to that same
request, validates the passive result codec and recomputed summary, rejects
rehearsal lifecycle substitution and authority/connection claims, and validates
the fresh native metadata report against the attempt context. These are bounded
consistency checks, not independent runtime or physical evidence authentication.

Verification: **31 tests passed in 3.60 seconds**, covering wire binding, exact
registration, real isolated import/error checks and a real child journal claim
followed by rejection of malformed setup evidence. Test root:
`software/runs/pytest-passive-native-wire-20260912-01`.
The observation fixture reports the actual native-loader hold, not a successful
open. No valid received-device handoff, metadata collection, serial open or arm
command was dispatched.

Next unfinished connection: the supervisor's physical admission branch must
validate retained consumed originals before dispatching this protocol, and its
result branch must retain/validate the bound response and uncertain outcomes.
Then connect wizard live Start and perform scoped native release/acceptance.
All existing physical/native holds remain in force in this increment.

## Previous increment — exact parent registration membership, 2026-09-12

Implemented `providers/windows/passive_native_registration.py` and added its
closed handoff schema to `OwnedWorkerRequest` syntax validation.

Registration validation requires the fixed passive child and `observe` command,
the base interpreter, the deterministic current-source archive and child hash,
the service-attempt working directory beside the assigned journal, exact
request/runtime/source/session/identity associations, and a fixed process budget:
20-second run, 2-second cleanup, one process, 64-KiB stdin, 256-KiB stdout and
8-KiB stderr, with the existing memory/handle limits unchanged.

Alternate commands, worker/schema/composition identities, archive hashes,
request bindings or caller-adjusted resource limits are rejected. The
import-only probe cannot be registered as the physical observation operation.

Verification: **35 tests passed in 15.11 seconds**, covering registration
membership, package/real isolated import checks and previous owned passive
process behavior. Test root:
`software/runs/pytest-passive-native-registration-20260912-01`.
The exact valid registration was also passed to the existing supervisor and
confirmed **PHYSICAL_PROVIDER_QUALIFICATION_HELD**, with no process created.
Syntax/membership validation is not dispatch authority or hardware acceptance.

Next unfinished integration: supervisor admission/result branches for this
specific protocol, owned-wire child decoding and exact result binding, durable
outcome retention, then scoped native release and public wizard live Start.
No received-unit metadata collection or serial access occurred in this increment.

## Previous increment — fixed isolated native child package, 2026-09-12

Implemented `providers/windows/passive_native_package.py` and
`providers/windows/_passive_native_child.py`.

The package uses an explicit source/dependency roster, deterministic archive
construction and isolated namespaces. It includes the required Windows pySerial
metadata modules, not the full wizard bootstrap or an arbitrary import directory.
The legitimate empty `serial/tools/__init__.py` is preserved through the bounded
regular-file reader; the older arm packager's nonempty-module rule is unchanged.

The fixed child checks the archive hash before importing it and supports an
import-only check. Its observation path validates the handoff, exclusively claims
the consumed journal, verifies the retained setup against its attestation hash,
acquires fresh metadata with reserved observation/cleanup time, and calls the
physical passive-observation entry. **Native serial loading remains held.**
The child is not yet registered with the parent supervisor or wizard live Start.
Archive hashing/byte association is not executable qualification by itself.

Verification: **36 tests passed in 14.22 seconds** across the new package,
exclusive claims, held physical observation and previous isolated child tests.
Test root: `software/runs/pytest-passive-native-package-20260912-03`.
Actual `-I -S` child processes verified imports, rejected an invalid archive hash
and invalid handoff, and exercised a consumed-journal claim followed by rejection
of a deliberately malformed setup attestation before metadata collection.
That failed child leaves its claim retained and outcome unknown; no retry occurs.
No valid hardware handoff, device enumeration, serial open, write or arm motion
was dispatched in these tests. Temporary disk-file access is real.

Next: exact parent registration/validation and supervised result handling for this
fixed child, followed by scoped native release and live Start integration. Do not
invoke the observation command manually as a substitute for that registration.

## Previous increment — exclusive child claim, 2026-09-12

Implemented `application/passive_arm_child_claim.py` and added the immutable
`claimed` stage to the existing engineering-attempt journal.

Before a child can claim an attempt, the helper independently rereads prepared
and consumed records, checks the exact parent's consumption digest and request,
compares registration bytes/runtime reference, decodes the entry originals and
revalidates their associations and remaining lifetime. Unconsumed, completed,
already-claimed, changed, foreign-runtime or late handoffs are rejected.

The immutable claim publication is a cross-process one-winner boundary: two
potential children cannot both claim the same consumed intent. A claim is not
deleted or recovered for retry. A missing outcome remains unknown even when a
claim exists. The claim deliberately says `native_access_granted: false`; the
closed runtime registration and scoped native release remain separate work.

Verification: **28 tests passed in 2.56 seconds**, covering child claims,
concurrent claim attempts, journal persistence/recovery and public-setup request
preparation. Test root: `software/runs/pytest-passive-child-claim-20260912-01`.
These tests use temporary files and explicitly unregistered runtime placeholders,
not real worker processes or hardware. No serial port was opened.

Next: integrate the claim verifier into the fixed, source-pinned physical child
package and its parent process registration, then connect live Start. This helper
does not itself qualify an executable, launch a child, or release native access.

## Previous increment — physical passive observation entry, 2026-09-12

Added `observe_physical` to `providers/windows/passive_serial_observation.py`.
The rehearsal entry remains separately type/mode checked; both share the actual
bounded observation, late-byte retention and cleanup implementation.

The physical entry requires exact physical request, narrow passive binding,
passive native API and cancellation-event types. It binds the original native
report to the request's reference, reconstructs a fresh identity recheck from
the full generic review and new snapshot, and rejects changed/stale mappings
before lifecycle entry. It returns the full recheck alongside lifecycle results.
The lifecycle result now derives origin from the actual selected composition;
memory results remain synthetic. Native device-open accounting derives from
confirmed port acquisition instead of an unconditional zero.

**Native loading remains held.** The physical-shaped test reaches that hold,
reports open FAILED with no acquired handles, no required close and zero writes,
and retains the exact native-hold reason in lifecycle diagnostics. A cancelled
entry does not attempt open. No DLL/device access is permitted by the tests.

Verification: **133 tests passed in 16.83 seconds**, covering the physical entry,
legacy backend, shared observation routine and isolated passive child regressions.
Test root: `software/runs/pytest-passive-physical-entry-20260912-02`.
An initial fixture incorrectly invented a future completion time on Windows'
coarse monotonic clock; the fixture was corrected, not the freshness policy.

Still required: the exact source-pinned physical child/process registration,
consumed original-entry validation in that composition, scoped native loader
release, and the wizard's live Start/result/export integration. The new routine
alone issues no permit, proves no electrical isolation and commissions no arm.

## Previous increment — passive native API boundary, 2026-09-12

Implemented `providers/windows/passive_serial_api.py` and connected it to the
passive branch of `NonPurgingSerialConnection`.

- `WindowsPassiveSerialApi` validates one exact COM path during construction.
- The first open attempt is consumed before an OS call, including wrong-path
  and failed attempts. A lock prevents concurrent calls getting a second attempt.
- Submit, completion and cancellation entry points reject non-read tokens and
  outbound payloads before native code. The T105 feedback query is prohibited.
- Passive bindings now require this passive native facade (or the explicit
  incapable fixture), not the generic feedback-capable native facade. Endpoint
  mismatches are rejected at construction. Feedback bindings cannot use the
  passive facade as a substitute registration.
- The shared native loader remains unconditionally held. This increment does
  **not** enable physical I/O, qualify the received driver, or register a child.

Verification: **147 tests passed in 12.91 seconds**, covering the new API
restrictions, passive binding/lifecycle, legacy nonpurging backend and isolated
passive process regressions. Test root:
`software/runs/pytest-passive-native-boundary-20260912-01`.
Every native DLL load was forbidden in the facade tests. Actual serial opens,
writes, power changes and arm movements: none.

The next release task remains the registered physical child and supervisor
composition, using retained setup/request/journal, fresh identity and this
write-rejecting API. Native loader release must be scoped to that composition;
do not remove the generic feedback backend hold or relabel rehearsal as physical.

## Previous increment — setup-to-request preparation, 2026-09-12

Implemented `application/passive_arm_preparation.py` to connect the retained
wizard setup original to `PassiveBenchRequest`, `PassiveEntryEvidence`, the
narrow controller selection and `PassiveAttemptJournal`.

It reads only the service-named setup file under the assigned diagnostic root,
checks its exact receipt hash, launch and source, reconstructs the full metadata
correlation, validates operator/design limitations, and binds all request
references. It retains the original setup confirmation time: preparation cannot
refresh an old operator report. The fixed serial profile remains 115200/8N1 with
the existing disabled flow/control-line settings; zero outbound bytes and the
existing observation/cleanup limits are unchanged.

Preparation writes an **unconsumed** immutable journal. Stale or foreign setup,
changed original bytes and insufficient cleanup lifetime fail before journal
publication. The caller must separately consume the journal before dispatch.
No dispatcher is called by this helper, and no native capability is returned.

Verification: **107 tests passed in 4.03 seconds**, including a complete public
wizard setup -> original-file readback -> request preparation -> journal consume
test, plus setup export, persistence, entry policy, identity and passive-binding
regressions. Test root: `software/runs/pytest-passive-preparation-20260912-02`.
All hardware-shaped observations/operator reports were fixture-owned; only
temporary regular files were accessed. No received arm serial port was opened.

Remaining release boundary: validate a closed physical worker registration,
wire this preparation into explicit live Start, and supply the child-side fresh
identity/read-only native lifecycle and supervised result handling. Tests here
intentionally use a registration-shaped placeholder to prove association only;
it is **not an approved executable registration**. The generic native hold,
physical dispatcher hold and canonical commissioning state remain unchanged.

## Previous increment — public setup-original producer, 2026-09-12

Added the physical-mode wizard action **Record USB-only arm setup**
(`record_passive_arm_setup`). This is implemented through the actual action
catalog, preview/execute queue, service runner, durable original publication,
result retention and diagnostic export, not merely a standalone helper.

- Requires current correlated arm metadata and explicit operator reports that
  external power is disconnected and the arm is secured with clear radius.
- Preview binds both the exact generic review and native report; changed
  metadata or source rejects execution. Operator IDs are validated at preview.
- `application/wizard_passive_arm_setup.py` reconstructs the complete native
  report from the retained generic original and snapshot. It reads only the
  fixed approved policy/design-review files and retains their exact bytes.
- Stores operator reports separately from unknown measured isolation. Existing
  RoArm-M3 Pro association is labeled as the previous operator report, not a
  new model inspection. No firmware evidence is invented.
- Publishes `<operation-id>-passive-setup-original.json` immutably in the
  assigned wizard diagnostic folder, with independent byte readback.
- Pins the latest result for export. Attachment
  `attachment-passive-arm-setup-original.json` contains `original_base64` and
  `original_sha256`, preserving exact original bytes even though the general
  exporter reformats its surrounding JSON. Budget overflow fails, not truncates.
- Both browser and terminal expose the registered action. No serial endpoint,
  camera endpoint, power switching or motion is performed by it.

Verification: **134 tests passed in 32.38 seconds** across the new public setup
flow, wizard service, native metadata integration, readiness and passive
rehearsal. Test root: `software/runs/pytest-wizard-passive-setup-20260912-03`.
The initial export test correctly detected JSON reformatting; the final tests
decode the attachment and compare its exact original bytes and SHA-256.

This is a service-owned setup original, **not a native permit or canonical
commissioning pass**. No actual operator setup record was created during the
tests; their physical-shaped metadata and confirmations were fixture-owned.
The physical worker must still bind this retained original to its exact request,
check current setup freshness, consume the one-use journal, perform fresh native
identity resolution and execute the narrowly registered zero-write lifecycle.
Live Start and physical serial acceptance remain incomplete.

## Previous increment — passive lifecycle and one-use journal, 2026-09-12

Implemented executable connection/persistence components, not another approval
checklist. **The physical dispatcher and wizard Start are still not connected.**

- `providers/windows/passive_serial_binding.py` derives a narrow endpoint from
  the validated metadata selection without inventing feedback, firmware, model
  or boot qualifications. It cannot authorize an open by itself.
- `nonpurging_serial_backend.py` accepts that exact passive binding, creates only
  the read event, and rejects every write at both public write and internal I/O
  admission. Existing feedback behavior and its native hold remain unchanged.
  The selected memory tests execute actual open/configure/read/close lifecycle
  code, including partial-open cleanup and unknown cleanup without retry.
- `passive_serial_observation.py` accepts the narrow binding for the existing
  memory-only observation routine. Physical requests remain rejected there.
- `application/passive_arm_attempt_store.py` adds a separate engineering-attempt
  journal. It durably stores exact entry/request/original/registration bytes,
  independently reads back publication, consumes once before dispatch, and
  retains raw stdout/stderr without requiring successful result parsing.
  Concurrent consumers have one winner; failed consumption burns the instance;
  immutable attempt filenames prevent restart from replacing original intent.
  Recovery is diagnostic-only, with missing outcomes explicitly unknown.

The journal associates bytes; it does **not authenticate their provenance** or
issue native authority. A registered service producer is still required. Its
process-status record does not claim device cleanup or final power state.

Verification: **211 tests passed in 29.33 seconds**, covering the new journal
and passive binding plus serial backend, isolated process, public wizard
rehearsal, entry policy and identity checks. Test root:
`software/runs/pytest-passive-progress-20260912-01`.
No real serial endpoint opened, no outbound bytes sent, no external power change.

Next integration work:

1. Service-owned entry-original producer and exact registered passive child.
2. Child-side fresh identity recheck and native API write rejection, using the
   narrow binding and journal without relaxing the generic native backend hold.
3. Connect the wizard's explicit one-use Start, truthful physical effect/result
   handling, cancellation and export to that complete supervised composition.
4. Run full public-path fault acceptance, then the approved USB-only live test.

## Previous increment — live metadata and passive identity recheck, 2026-09-12

User authorized continuing toward physical/live testing. Ran the existing
physical wizard USB preflight against VID `10c4`, PID `ea60`, serial
`A02C8734397FEF11A7321C1CEDD322A4`, using the last operator-reported USB-only
configuration. Result: **METADATA_CORRELATED**, five candidates, exactly one
generic/native match, no blockers. No serial endpoint was opened.

- Session: `wizard-ae994a6d4b0f408594bd9135e566fa33`.
- Native operation: `operation-1bee346a5d924a529d54f1039f24b34a`.
- Source at acquisition: `b9258ee90495a8fcc18d35b94ada4b89267e4348db6be80d027a5e6f9db4b9aa`.
- Verified export: `software/runs/wizard-exports/wizard-20260912T185205462138Z-e84098443a5643bb9894430c42b5cea1`.

Then implemented `application/passive_arm_identity.py`. It retains an immutable
validated metadata selection and reuses the existing full wizard correlation
to compare a subsequent collection against the exact original review, launch,
source, mapping and driver. It does not construct `ReviewedControllerBinding`
or invent firmware/boot evidence. Changed/ambiguous mappings return no candidate
port. New collection and operation are required; the collection must finish
within one second of the supplied live check clock. This is a software freshness
restriction, not atomic COM-to-handle proof. Rehearsal origin remains rehearsal.

**144 tests passed in 2.92 seconds** covering identity, native metadata, approved
entry policy, public preflight and readiness UI. Test root:
`software/runs/pytest-passive-identity-20260912-03`.
The first test iteration exposed fixture review regeneration and a candidate
serialization-key mistake; these were corrected before this passing regression.

This helper is not yet wired into a registered physical worker. The live export
above predates these source edits and must not authorize the changed source.
Remaining: authenticated retained entry originals, separate read-only native
worker registration, durable one-use dispatch/outcome, and complete wizard
acceptance before the first serial open. No further policy approval is needed
for that software work. No motion, feedback query or power reconnect is released.

## Previous increment — approved USB-only entry, 2026-09-12

The user approved `ROCELL-ARM-USB-PASSIVE-ENTRY-002` with “Yes proceed”.
The decision is retained in [the entry policy](ARM_USB_ONLY_ENTRY_POLICY_PROPOSAL.md).
Do not ask for the same policy approval or repeat received-model identification.
Approval is not measured isolation, current setup evidence, or a dispatch token.

Implemented `application/passive_arm_entry_policy.py`: immutable bounded entry
evidence, exact attempt/session/source and original-byte association, closed
operator/design/unknown-measurement semantics, and stale/future setup rejection.
The initial software freshness window is five minutes within one live launch;
it cannot be renewed by reopening historical diagnostics. This is an additional
software restriction, not a measured guarantee about power state.
The existing v1 request field `electrical_isolation_review_sha256` binds the
design-review original; its name must not imply an isolation measurement.

The wizard's shared readiness guidance now reflects the approved evidence basis.
The new assessment deliberately returns `ASSOCIATED_NOT_AUTHENTICATED`, not a
physical permit. It is **not yet connected to a physical dispatcher**. The old
native backend hold and all canonical commissioning stages are unchanged.

Verification: **108 tests passed in 28.32 seconds**, covering entry policy,
existing request contract, readiness UI, contained passive process and wizard
rehearsal. Temporary test root:
`software/runs/pytest-passive-approved-entry-20260912-01`.
No physical device endpoint was opened in this increment.

Next implementation sequence (still outstanding):

1. Produce the entry envelope from service-owned, durably retained originals;
   authenticate origin and read it back before launch. Do not accept browser
   hashes or a successful pure assessment as authority.
2. Introduce a narrowly scoped passive identity binding without invented
   firmware/model/boot qualification. Resolve exact native identity immediately
   before open and block stale, ambiguous or changed mappings.
3. Register a separate pinned physical child and read-only native API. Reject
   writes at the API boundary, retain the generic feedback backend hold, and
   account for actual effects rather than reusing rehearsal zero-effect fields.
4. Consume a durable one-use intent before device access; preserve unknown and
   failed outcomes across interruption. Restart and export must never replay.
5. Exercise the complete wizard path with incapable fault injection, then
   current-source acceptance. Only after this perform the supervised USB-only
   zero-write test using current setup confirmation and explicit Start.

A4 physical connection, A5-A10 feedback/calibration/contact remain incomplete.

## 1. Objective and how to use this file

Deliver a wizard that identifies the received arm, explains its readiness,
performs explicitly requested supervised connection tests, retains diagnostics,
and eventually executes calibrated typing and phone-tapping tasks.

This file is the execution checklist for that work. It does not itself release
hardware access or replace the existing safety/stage contracts. Work through
the milestones below, update their status and evidence after each increment,
and retain failed runs as well as passes. Do not equate a code implementation,
simulation pass, metadata match, or successful export with a hardware pass.

The first deliverable is **reliable feedback-only onboarding**, not motion.
The second is a **calibrated, bounded noncontact executor**. Keyboard and phone
contact come only after those are accepted separately.

Related documents:

- [Received USB result and actual defect fix](ARM_USB_RECEIVED_UNIT_PROGRESS.md).
- [Overall application completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md).
- [Connection integration plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md).
- [Developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md).
- [Canonical arm-identity stage work order](ARM_IDENTITY_ONBOARDING_WORKORDER.md).
- [Pre-arm calibration plan](PRE_ARM_CALIBRATION_EXECUTION_PLAN.md).
- [Controlled stage catalog](../config/physical_onboarding_stage_catalog.json).

If a proposed change conflicts with a controlled contract, record the conflict
and review a versioned change before implementation. Do not silently relax the
contract, add a second stage catalog, or mark missing physical evidence as PASS.

## 2. Starting point: what is actually known

| Component | Evidence today | Still unknown or unavailable |
| --- | --- | --- |
| Arm | User identifies RoArm-M3 Pro, securely mounted and working radius clear | Independently retained chassis identity, installed firmware, boot/startup behavior |
| USB adapter | Actual wizard native/generic metadata correlation; COM6, VID 10c4, PID ea60, bridge serial A02C8734397FEF11A7321C1CEDD322A4 | Open-handle identity, serial communication, reconnect behavior under the new workflow |
| Windows driver | CP210x, Silicon Laboratories Inc., 6.7.3.350 | Validated serial lifecycle on this driver/controller combination |
| Power | Last user confirmation: external supply disconnected, USB connected | Electrical isolation measurement; future power state must be reconfirmed |
| Software | Metadata defect fixed; repeatable preflight/export script; 366 selected tests passed | Released physical arm backend, original arm stages, feedback connection and motion executor |
| Camera/build | Static overhead B0477 architecture selected | Installed optics, board coverage, final height, completed fixtures and calibration |

COM6 is a current locator, not a permanent identity. The bridge serial is not
the arm chassis serial. The reported MAC/AP/ST display does not establish USB
identity, firmware, or servo-power state. Do not overwrite unresolved fields in
`arm_connection.json` with inferred observations.

No serial port has been opened by the new preflight, and no arm command has
been sent. The existing full camera workflow also lacks a complete acceptance
PASS; see the received-unit progress document for the failed run-06 boundary.

## 3. Architecture to retain

```text
Wizard Arm page / terminal interface
    -> existing public action validation and operation queue
    -> arm onboarding service + current evidence/identity review
    -> one-use admission + exclusive device/process owner
    -> supervised child + non-purging Windows serial backend
    -> RoArm controller
    <- bounded raw result + shared feedback parser + cleanup result
    -> original retention + completion log + verified diagnostic export
    -> compact UI state (never a device handle)
```

The camera has a separate owner. Camera metadata, preview, or failures must not
open or move the arm. Later task execution consumes both calibrated coordinate
transforms and a bounded arm executor; it does not send raw JSON from the UI.

Reuse these existing components rather than creating parallel implementations:

| Concern | Existing source starting points |
| --- | --- |
| Wizard actions and ownership | `application/arrival_wizard_service.py`, `application/wizard_actions.py` |
| Native metadata | `application/wizard_native_arm_metadata.py`, `providers/windows/controller_metadata.py`, `providers/windows/legacy_usb_metadata.py` |
| Fresh controller mapping | `application/arm_controller_resolution.py` |
| Terminal preflight | `software/scripts/wizard_arm_usb_preflight.py` |
| Feedback codec | `arm/protocol.py`, `arm/feedback_wire.py`, `arm/feedback.py` |
| Feedback campaign | `providers/windows/arm_feedback_worker.py`, `providers/windows/arm_nonpurging_adapter.py` |
| Windows lifecycle | `providers/windows/nonpurging_serial_api.py`, `providers/windows/nonpurging_serial_backend.py` |
| Process protocol/runtime | `providers/windows/arm_owned_protocol.py`, `providers/windows/owned_arm_feedback_runner.py`, `providers/windows/owned_arm_feedback_package.py` |
| Retained process evidence | `providers/windows/arm_owned_evidence.py`, existing commissioning/original-storage services |
| Export | Existing wizard diagnostic export, attempt retention and export verification |

Source paths in this table are relative to `software/src/rocell` unless prefixed
with `software/`. Names below described as “proposed” are not existing APIs.

## 4. Rules that every milestone must preserve

- Application startup, GET/view, refresh and browser reopening perform no
  implicit serial open, power action, initialization or movement.
- Do not automatically invoke vendor SDK constructors until their startup
  effects have been audited. Connecting is not homing or initializing joints.
- Select an explicitly reviewed USB identity and freshly resolve its current
  native mapping. Missing, duplicate, changed or conflicting mappings block.
- One owner at a time. No fallback to Wi-Fi, another COM port, another program,
  or a raw serial script when the reviewed USB operation fails.
- Use finite time/output/attempt limits and a supervised process, not merely a
  Python timeout around a potentially stalled OS call.
- No blind retry, buffer purge that conceals startup evidence, unbounded read,
  arbitrary command box, firmware flash, automatic torque command or automatic
  home/park/reset action.
- Unknown outcome is a distinct retained state, not failure-with-zero-effects.
  Block subsequent effectful actions until its owner/cleanup state is resolved.
- Software Cancel/Stop is not a hardware emergency stop. Killing a process or
  closing a port does not prove actuator power is off or motion has stopped.
- Use fresh operator confirmation at physical transitions. A checkbox is an
  attestation, not a voltage measurement or independently observed fact.
- Preserve original evidence, quotas, source/runtime identity and export
  verification. Source changes invalidate current approval; never repin an old
  run as though it occurred on the new source.

## 5. Milestone checklist and dependencies

| ID | Deliverable | Depends on | Status |
| --- | --- | --- | --- |
| A0 | Current baseline and traceable work ledger | Existing USB result | Plan established; execution ledger below |
| A1 | Usable Arm readiness page and metadata workflow | A0 | Existing foundations; remaining UX/integration pending |
| A2 | Reviewed pre-build bench qualification contract | A0 | Pending design/review |
| A3 | Tested supervised serial lifecycle | A2 | Held implementation foundations exist; qualification pending |
| A4 | Physical USB-only open/observe/close qualification | A1–A3 | Not run |
| A5 | Canonical identity, power and startup services | Genuine predecessors, A1; informed by A4 | Pending |
| A6 | One-shot physical feedback through wizard | A3–A5 and explicit admission | Not run |
| A7 | Recovery, persistence, exports and repeatability acceptance | A1–A6 | Foundations exist; full arm acceptance pending |
| A8 | Static vision and arm/board/tool calibration | A6–A7, completed build and camera prerequisites | Pending physical setup |
| A9 | Bounded noncontact motion executor | A8 | Not released |
| A10 | Keyboard and Android contact workflows | A9 plus contact-specific acceptance | Not released |

A1 and pure A2/A3 work can advance before the board is finished. A5's original
stage acceptance and A8–A10 cannot be simulated into physical completion.

### A0 — Freeze the baseline and expose the real remaining blockers

- [ ] Record current source/runtime identities, selected tests and latest actual
  metadata report in the execution ledger; preserve all historical exports.
- [ ] Audit all arm release holds and callers. List the evidence each hold is
  protecting and which milestone supplies it.
- [ ] Confirm which acceptance readers/builders currently exist for original
  stages 8–12; do not infer that rehearsal implementations are physical services.
- [ ] Reconcile stale “run 06 in progress” camera documentation without changing
  the failed store. Track the camera fixture repair separately.
- [ ] Establish a small fast-test command and new per-run artifact directories.

Acceptance: a developer can distinguish shipped code, passing tests, physical
observations, proposed services and missing release prerequisites without guessing.

### A1 — Make the Arm page useful before connection is possible

- [ ] Present separate fields for detected USB unit, current COM mapping, driver,
  metadata provenance/time, model/firmware unknowns, last test and cleanup state.
- [ ] Wire the existing inventory -> exact candidate review -> native correlation
  flow into an obvious sequence on the existing Arm page.
- [ ] Use the same public service actions as the terminal preflight; no new UI
  serial library or duplicated identity parser.
- [ ] Show why each action is disabled and its next concrete prerequisite. Do not
  show “Connected” for `METADATA_CORRELATED` or for a closed successful test.
- [ ] Display the assigned export folder and a one-click verified export action.
- [ ] On browser refresh/restart, show retained results as historical and require
  fresh acquisition before a new hardware attempt. Never resume I/O automatically.

Proposed presentation labels: Not inspected, Metadata matched, Review required,
Test prepared, Test running, Feedback verified / port closed, Cleanup uncertain,
Blocked. Map these onto existing states; do not invent conflicting authority flags.

Acceptance: public/UI tests cover nominal, missing, duplicate and changed adapter
cases; viewing the page causes zero device effects; export is accessible on failure.

### A2 — Resolve the pre-build qualification dependency explicitly

The canonical workflow requires genuine stage-8 static registration before arm
identity stage 9. However, an engineering USB/driver qualification can be useful
before that build exists. **Do not bypass stage 8 or fabricate stage-9/12 passes.**

- [ ] Design a separate, narrowly scoped bench-qualification attempt type using
  existing ownership and retention infrastructure, not a parallel evidence vault.
- [ ] Define its allowed effects and output: external-power-disconnected serial
  open/configuration/passive observation/close only initially; no outbound JSON.
- [ ] Specify required preconditions: exact received USB candidate/native review,
  explicit operator attestation of external-power isolation, exclusive access,
  source/runtime identity, time budget and clear physical setup.
- [ ] Review USB backfeed/servo supply separation and startup risks for the actual
  board. If electrical isolation cannot be established, stop for hardware review;
  “external cable removed” alone must not be labeled electrically verified.
- [ ] Define separate evidence for expected vendor firmware, observed installed
  firmware, configured control-line states, and measured boot/reset behavior.
  Avoid requiring a completed feedback transaction as proof needed to authorize
  the first passive port observation.
- [ ] Define how later canonical commissioning may cite bench evidence without
  promoting it to stage acceptance or motion permission.
- [ ] Review/version the effect policy and request/result contracts before making
  a native branch callable. No Boolean “ignore hold” or hidden developer override.

Acceptance: reviewed inputs, permitted effects, evidence semantics, stop rules,
storage limits and authority boundaries are written and covered by pure tests.
If this separate qualification lane is not approved, the canonical predecessors
remain prerequisites; do not add an alternate raw serial test as a workaround.

### A3 — Finish and test the supervised non-purging lifecycle

- [ ] Audit native ABI, structure sizes, handle ownership, DLL loading and exact
  COM path validation; reuse the existing Windows backend and process owner.
- [ ] Add the approved qualification request/result purpose without granting a
  general write API. Existing rehearsal paths remain incapable and clearly labeled.
- [ ] Resolve exact native identity immediately before opening, investigate
  possible COM-to-handle substitution, and document residual non-atomicity.
- [ ] Implement exclusive open, requested settings and readback verification;
  check the controlled 115200/8N1 and RTS/DTR policy against official firmware
  documentation and the existing configuration. Settings are not no-reset proof.
- [ ] Preserve bounded startup bytes, errors and banners. Do not send feedback
  merely to make an otherwise passive test return data.
- [ ] Contain native stalls with the existing process owner; establish finite
  cancellation and cleanup observation, including unresolved handles/pending I/O.
- [ ] Retain intent before effect and known/unknown outcome afterward. A crash
  before durable completion must not be replayed at restart.
- [ ] Implement the tests in section 7 before any physical serial opening.

Acceptance: real contained-process tests with incapable serial APIs demonstrate
bounded lifecycle and failure behavior. No test patches a live release hold to
access hardware. Native release requires the reviewed A2 contract and A3 evidence.

### A4 — Run the first physical qualification, USB-only

- [ ] Reconfirm current setup and power-isolation preconditions. Close other arm
  serial applications; do not stop unrelated applications automatically.
- [ ] Acquire/review fresh metadata through the wizard and prepare one attempt.
- [ ] Pause for explicit Start. Open only the selected endpoint, observe bounded
  startup input/settings, and close under the approved passive contract.
- [ ] Record operator observations separately from software telemetry: display
  changes, apparent reboot, sound/movement or disconnect. Unexpected behavior
  stops progression; investigate before any further attempt.
- [ ] Verify process/handle cleanup and export originals. Quiet serial input is
  not proof of correct firmware or proof that a reset did not occur.
- [ ] Review the result. If a repeat is necessary, use a new explicitly started
  attempt with fresh preconditions, retaining the prior one.

Acceptance: verified lifecycle on the received adapter/controller with declared
limitations; no motion/contact authority and no canonical commissioning PASS.

### A5 — Implement genuine identity, power review and startup stages

- [ ] Complete genuine predecessor producers, including stage-8 registration,
  before accepting canonical stage 9. Build/test codecs and services with labeled
  modeled predecessors while hardware is incomplete, but hold physical acceptance.
- [ ] Implement the arm identity work order's original submission, assessment,
  independent review, retention/readback, revision and export contracts.
- [ ] Collect model/chassis identity, controller association and available firmware
  evidence; retain UNKNOWN and reasons rather than defaulting to a nominal model.
- [ ] Implement stage-10 power safety and stage-11 startup observation as distinct
  services/attempts. Include mounting, supply/cable review, accessible isolation,
  startup swept-volume review and any required inert-load/electrical tests.
- [ ] Make every external power transition operator-controlled, with the specified
  stage envelope and end-disconnected policy. Never auto-energize after a review.
- [ ] Implement required independent review semantics explicitly; an assistant's
  automated metadata selection is not a substitute for a required human reviewer.

Acceptance: original stage acceptance, invalidation and fresh reopen pass through
the real service/UI/storage paths, with hardware facts honestly labeled and retained.

### A6 — Add the first feedback-only wizard exchange

- [ ] Implement the original stage-12 connection service and its evidence bindings.
- [ ] Prepare one exact, short-lived feedback attempt using qualified runtime,
  identity, firmware/boot policy and applicable power-stage evidence.
- [ ] Use the shared fixed T=105 encoder and T=1051 framing/parser. Verify the
  installed firmware's documented semantics before physical dispatch.
- [ ] Retain pre-request startup data separately. Stale or ambiguous feedback
  must not count as the response to the new request; no purge or blind retry.
- [ ] Validate framing, required fields, types, finite numeric values, units and
  supported firmware variants. Do not infer missing values as zeros or “safe.”
- [ ] Close after the one-shot onboarding test and show **Feedback verified;
  connection closed**, with timestamps, actual effects and cleanup outcome.
- [ ] If later adding a persistent telemetry session, review it as a separate
  lifecycle with bounded polling, expiry, explicit disconnect and ownership—not
  an automatic extension of this single-request test.

Acceptance: the actual wizard starts the real admitted request, receives a valid
response, retains exact evidence and confirms cleanup. No homing, torque change,
motion or contact occurs as a side effect of successful feedback.

### A7 — Make failure recovery and export dependable

- [ ] Provide actionable error cards for wrong/missing device, busy port, driver
  failure, changed identity, startup bytes, timeout, malformed reply and cleanup
  uncertainty. Distinguish a known failed attempt from an unknown outcome.
- [ ] Export source/runtime/profile hashes, generic/native identity, request and
  bounded response evidence, timings, error chain, settings/readback, process
  outcome, cleanup, operator observations and omitted-attachment reasons.
- [ ] Keep serials/local paths and raw bytes under the existing export/privacy
  rules; do not include camera images or credentials without applicable consent.
- [ ] Use the assigned default `software/runs/wizard-exports`; verify each export
  and show its location. Preserve a usable error even if export itself fails.
- [ ] Test real original retention, partial failures, browser refresh, app restart,
  source changes, disk/quota failures and a fresh read-only reopen without replay.
- [ ] Test that a second window/session cannot create a second arm owner.
- [ ] Run the full public arm onboarding acceptance workflow and report the exact
  observed result, duration, environment and residual limitations.

Acceptance: another developer can reconstruct what happened from an export, and
neither restart nor recovery silently repeats hardware activity.

### A8 — Connect static vision and physical calibration

- [ ] Finish camera onboarding acceptance separately; resolve the existing full
  camera-history fixture failure rather than claiming an unobserved PASS.
- [ ] Install/measure the static B0477 mount and actual placemat, keyboard and
  phone fixtures. Do not derive final height from the approximately 10-inch bench
  focus trial or assume the advertised field of view proves board coverage.
- [ ] Calibrate camera intrinsics/distortion at the installed focus/resolution;
  validate fiducial visibility, glare, image quality and board coverage.
- [ ] Define frames and units explicitly: image pixels, camera, board, robot base,
  tool tip, keyboard plane and phone plane. Store transforms with uncertainty,
  calibration version and validity conditions.
- [ ] Measure robot-base placement, tool/stylus offset, target heights and safe
  approach clearances. A board homography alone is not a 3D tool calibration.
- [ ] Check reachability, joint limits, singularities, collisions and error budget
  across actual target locations before allowing contact.
- [ ] Invalidate affected calibration after camera/focus/tool/fixture/base changes.

Acceptance: measured targets and independent validation points satisfy an agreed
task accuracy budget. Good-looking images or a marker detection alone do not pass.

### A9 — Release a bounded noncontact motion executor

- [ ] Implement a typed motion service behind the existing task planner and safety
  supervisor, not `SerialTransport.send_motion` bypasses or browser raw commands.
- [ ] Bind each goal to the current calibration, measured workspace, checked path,
  joint/tool limits, speed/acceleration policy and exact one-use authorization.
- [ ] Agree numerical limits from reviewed hardware/build data; this plan does
  not invent safe speed, force, clearance or positional tolerance values.
- [ ] Rehearse full paths and fault scenarios, then independently authorize a
  small noncontact test with a clear workspace and appropriate physical stop.
- [ ] Define actual stop behavior and stopping limitations before claiming a
  motion Stop button is safe. Verify feedback/freshness and failure response.

Acceptance: controlled noncontact validation at approved targets, retained path
and feedback evidence, and no automatic contact after a successful test.

### A10 — Enable keyboard and Android task workflows

- [ ] Version keyboard geometry, key centers, key heights/travel and fixture pose;
  compile text into individual press/release actions, including modifiers and
  layout-specific characters. Address missed/double presses explicitly.
- [ ] Use a harmless local text field for initial keyboard verification. Treat
  Enter/shortcuts as potentially consequential actions requiring task context.
- [ ] Version phone fixture/screen geometry, orientation and screen-to-board
  mapping. Verify capacitive stylus suitability, target size and contact limits.
- [ ] Begin with a dedicated benign phone tap-test screen; screen changes, stale
  images, unexpected dialogs or device movement invalidate pending targets.
- [ ] Use visual/application acknowledgement where available to detect a missed
  press/tap. Never blindly repeat consequential input when its outcome is unknown.
- [ ] Add task preview, dry-run, explicit Start, progress, bounded cancellation and
  task export. Do not treat receipt of an arm command as successful text entry.

Acceptance: measured keyboard and phone success rates and bounded contact behavior
meet agreed criteria on controlled test tasks before general task use.

## 6. Operator pauses and automation policy

| Transition | Software can automate | Required pause / condition |
| --- | --- | --- |
| Launch | Validate configuration, render retained state, list missing prerequisites | No automatic device access |
| Metadata inspection | Requested enumeration, exact correlation, logging/export | Current required power-disconnected acknowledgement |
| Bench serial qualification | Validated single attempt, observation, bounded cleanup | A2/A3 release review, isolation review, explicit Start |
| Apply external power | Present instructions and evidence checklist | Operator action under reviewed stage envelope |
| Feedback test | Exact request, strict parsing, cleanup and retention | Valid stage-12 admission and explicit Start |
| Failure | Retain result and offer export | No automatic replay; resolve unknown cleanup first |
| Calibration | Compute fits/residuals and show validation targets | Installed hardware measurements and separate authorized motion |
| Task run | Compile/check approved task and monitor permitted execution | Valid current calibration, task preview and explicit Start |

Preparation may be automated, but physical attestations, required independent
reviews and energization cannot be silently checked off on the user's behalf.

## 7. Required test matrix

| Area | Minimum cases | Expected behavior |
| --- | --- | --- |
| Identity | Nominal, missing, duplicates, COM renumbering, conflicting registry/interface fields, unplug during acquisition | Match exact current unit or block; never select by list position |
| Startup | Quiet input, reset banner, continuous unsolicited bytes, malformed/truncated stream | Preserve bounded observations; no invented feedback association |
| Ownership | Busy port, two sessions, second click, restart during attempt | One owner/attempt; no implicit takeover or replay |
| Native calls | Open/config/readback/read/close errors and stalls; cancellation at each boundary | Finite supervision; explicit known/unknown cleanup |
| Feedback | Correct response, wrong type, NaN/Infinity, missing fields, oversized data, short write, delayed/stale reply | Strict parser and no blind retry |
| Persistence | Log failure, quota exhaustion, partial originals, export failure, source change | Retain failure evidence; withdraw current approval |
| UI | Disabled explanations, double submission, stale revision, refresh, closed successful test | Truthful status; no hidden I/O |
| Calibration/task | Changed mount/focus/fixture, unreachable targets, occlusion, shifted phone, missed/double contact | Invalidate affected plans and stop unsafe progression |

Test layers, in order: pure contracts -> incapable backend tests -> real
contained-process tests with incapable device APIs -> public UI/service/original
storage integration -> admitted physical bench tests -> completed-build tests.
Do not use hardware while exercising injected fault cases intended to be incapable.

For long acceptance runs, stop source/config/runtime edits, use a new output and
pytest temporary directory, retain failures and wait for the terminal outcome.
Never reuse a `--basetemp` path that contains earlier evidence.

## 8. Definition of done

### Feedback-only onboarding release

- [ ] Wizard detects/reviews the exact received unit and reports missing evidence.
- [ ] Real supervised USB lifecycle and one-shot feedback are qualified and tested.
- [ ] Genuine required original stage producers/acceptance are implemented.
- [ ] Actual feedback, explicit close and cleanup status appear in the wizard.
- [ ] Export/reopen/recovery and duplicate-owner tests pass without replay.
- [ ] No automatic initialization, motion, torque changes or power transitions.
- [ ] Operator/developer runbooks and observed limitations are current.

### Complete typing/tapping system

- [ ] Static camera and completed physical cell pass their own acceptance.
- [ ] Measured transforms, tool geometry and error budgets are validated.
- [ ] Bounded noncontact executor passes physical validation.
- [ ] Keyboard and Android contact workflows pass separate controlled tests.
- [ ] Task-level verification, failure handling and exports are usable through UI.

## 9. Execution ledger

### Latest powered-feedback checkpoint — 2026-09-12

Public physical join increment: **Run one supervised powered feedback query**
now requires fresh powered startup, current correlated USB metadata and an
explicit unchanged-firmware confirmation. Preview/execute bind the exact setup;
the service pins one attempt per launch before preparation, calls the new
`wizard_powered_feedback_native_coordinator.py`, retains raw outcomes and exports
attempt files plus native process logs independently of UI rotation. The
coordinator joins fixed runtime/profile, operator history, protocol and startup
originals, durably consumes the journal, then invokes the supervised worker.
Success publication requires successful process start/exit, accepted feedback,
confirmed serial cleanup and durable outcome saving; it still enables no motion.
**77 tests passed in 18.49s** in
`software/runs/pytest-powered-feedback-live-join-20260912-02`, covering the public
join with simulated worker outcomes, missing/current setup checks, one-attempt
restriction, changed-preview rejection, success/persistence-failure publication,
raw exports, rehearsal/setup/history and shared supervisor regressions.
No live worker was dispatched in these tests; hardware access was forbidden.
Next: operator-present received-unit query through this action, followed by
review of reported pose/voltage and actual closure evidence. Physical calibration
and typing/tapping remain unfinished.

Physical worker/supervisor increment: added separate native child/package,
registration and wire codecs (`_powered_feedback_native_child.py` and
`powered_feedback_native_{package,registration,wire}.py`). The child verifies and
claims saved originals before fresh USB metadata, then invokes the admitted
one-query facade and retains fresh metadata plus observation. The supervisor now
recognizes this exact physical composition, revalidates consumed originals before
process creation/resume, and checks the returned claim against the journal.
**90 tests passed in 14.46s** in
`software/runs/pytest-powered-feedback-native-worker-20260912-03`: isolated import
checks, invalid/oversized handoffs, wire binding, exact registration, rejection of
missing originals before dispatch, native facade and shared supervisor/rehearsal
package regressions. No valid physical request was dispatched; no device access
occurred. An oversized test identifier caused initial setup errors; short explicit
test IDs fixed the test infrastructure without changing the input bound.
Next: implement the public physical coordinator's evidence/journal/runtime joins
and compact result/export publication; qualify that join before the live query.

Native facade/lifecycle increment: `powered_feedback_serial_api.py` now admits
one exact endpoint through an original-revalidated live child claim and fresh
metadata. It permits one fixed T105 write, rejects other command payloads and
copied/reused claims, preserves cleanup after expiry, and keeps ordinary
construction held. Joined into `nonpurging_serial_backend.py` and a separate
`observe_physical` entry sharing the tested loop with rehearsal. Added the facade
to the isolated package. **135 tests passed in 9.91s** in
`software/runs/pytest-powered-feedback-native-api-20260912-02`, covering facade,
loop, shared backend, passive facade and isolated package. Native calls used a
fake DLL; serial loading was otherwise forbidden. No actual hardware access
occurred. Physical worker registration/coordinator and the first live query are
still pending; this increment does not complete A6 or release motion.

Received-firmware evidence increment: the operator reported unchanged delivery
and reconfirmed current powered/secured/clear USB setup. Recorded that history in
`ARM_RECEIVED_FIRMWARE_HISTORY.md`; added explicit limited review representation
and validation in `powered_feedback_firmware_review.py`, joined it into powered
original preparation, and included the dependency in the isolated package.
**58 tests passed in 12.30s** in
`software/runs/pytest-powered-feedback-firmware-20260912-01`, covering review,
preparation, journal, child claim and package. No hardware access occurred.
The operator-evidence question is resolved. Remaining blockers to live execution
are software-native/runtime admission and coordinator integration, not a missing
firmware-history answer. Installed version/hash remain unknown by design.

Historical UI increment: **Inspect saved powered feedback attempt** now reads
exact operation-scoped journal files and exports their original byte chunks from
the assigned root, without reconnect, repair or replay. Implemented in
`wizard_powered_feedback_history.py`, shared catalog and service; tests in
`test_wizard_powered_feedback_history.py`. **75 tests passed in 18.09s** in
`software/runs/pytest-powered-feedback-history-20260912-02`, covering public
recovery in both modes, partial/missing/unreadable records, export integrity and
retention, traversal rejection, powered journal, supervised rehearsal and general
service regressions. No hardware access occurred. Export snapshots exceeding the
existing one-MiB attachment bound fail explicitly; multi-attachment support for
that case is not implemented. No physical connection or calibration milestone is
completed by historical inspection. Camera/catalog mismatch remains separate.

Supervised wizard increment: the public powered rehearsal now uses the existing
owned process supervisor via `wizard_powered_feedback_coordinator.py` and the
closed `powered_feedback_process_codec.py`. Fixed source-pinned artifacts,
request/result association, cancellation, time/output limits, durable process
diagnostics and separately pinned process exports are implemented. **75 tests
passed in 18.17s** in
`software/runs/pytest-powered-feedback-supervised-20260912-03`, including actual
wizard-owned incapable child processes, all five scenarios, process cleanup,
original/export integrity, cancellation and shared supervisor/passive regression.
No hardware access occurred. The previous broad run's unrelated action-catalog
mismatch for `physical_camera_operating_proposal` remains unresolved; its failure
is not covered by this green scoped run. See [supervised checkpoint](POWERED_FEEDBACK_WIZARD_CHECKPOINT.md).
Next: reviewed powered native admission and physical coordinator/journal joins;
the firmware-history answer and later physical calibration are still required.

Isolated package increment: `powered_feedback_package.py` and
`_powered_feedback_child.py` now deploy the real powered lifecycle/claim modules
in a deterministic closed archive with required `-I -S` startup and hash check.
Only import-check and five-scenario memory rehearsal modes exist; live mode is
rejected before imports. **33 tests passed in 11.15s** in
`software/runs/pytest-powered-feedback-package-20260912-02`, including real isolated
processes and passive package/claim/public wizard regressions. New coverage:
`test_powered_feedback_package.py`. All hardware behavior remained synthetic;
no native I/O or powered claim was executed by the child. The public wizard still
uses in-process rehearsal. Fixed owned-supervisor registration/wire contract,
coordinator integration and reviewed native admission remain the next work.

Worker-claim increment: `powered_feedback_child_claim.py` validates the exact
prepared/consumed chain and all original associations, then reserves one durable
child claim. Copied/reused live objects and partial/existing claim files cannot
be used to replay. `powered_feedback_attempt_store.py` now retains the claimed
stage. **66 tests passed in 9.51s** in
`software/runs/pytest-powered-feedback-claim-20260912-02`; new coverage is in
`test_powered_feedback_child_claim.py`, with powered/passive journal/preparation
and public rehearsal regression. Concurrency exercised actual Windows exclusive
file reservation; hardware data was modeled and no device access occurred.
The native supervised worker, reviewed firmware/runtime admission and live wizard
dispatch remain incomplete; these lifecycle claims are not physical permits.

Durable-attempt increment: `powered_feedback_attempt_store.py` now retains
associated originals, revalidates them before one-use consumption, reserves the
consumed filename before writing, and preserves bounded raw outcomes and partial
historical records. New tests: `test_powered_feedback_attempt_store.py`.
**63 tests passed in 8.27s** in
`software/runs/pytest-powered-feedback-journal-20260912-03`, covering new journal,
preparation, shared passive journal/durability and public rehearsal/export.
Initial missing-file classification was corrected using explicit absence checks;
subsequent read uncertainty remains UNREADABLE. No device access occurred.
This is storage for the future live coordinator, not native dispatch or a new
physical wizard action. Child-side claim, reviewed runtime/firmware admission,
supervised worker and public live connection remain unfinished. Details and
integration order: [powered feedback checkpoint](POWERED_FEEDBACK_WIZARD_CHECKPOINT.md).

Additional wizard increment: the shared Arm action **Rehearse powered feedback
(no hardware)** now runs five closed memory-only scenarios and exports the latest
full original independently of rotating UI cards. Physical mode rejects this
action. **178 tests passed in 23.72s** in
`software/runs/pytest-powered-feedback-wizard-20260912-03`, including public
service/export, byte integrity after rotation, action catalog, powered setup,
general wizard, native metadata and feedback lifecycle regression coverage.
Source: `wizard_powered_feedback_rehearsal.py`, `wizard_actions.py`,
`arrival_wizard_service.py`; tests: `test_wizard_powered_feedback_rehearsal.py`
and the explicit action catalog. See [usage and remaining integration work](POWERED_FEEDBACK_WIZARD_CHECKPOINT.md).
This increment performed no hardware access. Full originals require export
before shutdown; live durable attempt handling and native dispatch are not done.

Current operator-reported configuration is external adapter ON and USB
reconnected/stable, following adapter-only startup movement. It is **not** the
USB-only passive configuration. The startup movement was not a software-issued
motion test. Previous passive observation does not qualify powered feedback.

Implemented a memory-only powered-feedback binding and single-query observation
using the existing non-purging serial lifecycle. Startup bytes are retained and
reject the query; malformed/incomplete/duplicate replies fail; partial writes
are not retried; unresolved cleanup cannot report success. The shared backend
rejects native access through this new binding.

Changed modules: `powered_feedback_binding.py`, `powered_feedback_observation.py`,
`nonpurging_serial_backend.py`; tests: `test_powered_feedback_observation.py`.
Validation: **103 passed in 4.77s**, run directory
`software/runs/pytest-powered-feedback-lifecycle-20260912-03` (observation,
shared backend and passive native package suites). The initial fixture used
mismatched review/session context and was corrected; production identity checks
were not weakened. No physical device access occurred in this increment.

Next: finish reviewed powered admission, durable one-use attempt handling,
supervised native worker and public wizard integration. Obtain the operator's
firmware-change history without inventing an installed version/hash. Then run
one supervised live feedback observation before planning any bounded movement.
See [protocol review](POWERED_FEEDBACK_PROTOCOL_REVIEW.md). Full calibration,
keyboard contact and phone tapping remain incomplete.

Update this section after each increment; do not mark the whole plan complete
because a single connection test or software suite passes.

| Date | Milestone/increment | Source/tests/evidence | Outcome | Next dependency |
| --- | --- | --- | --- | --- |
| 2026-09-12 | Baseline USB detection fix | Received-unit progress document; 366 selected tests; actual verified metadata exports | Metadata correlated; serial still unopened | A0 audit, A1 readiness integration, A2 contract |
| 2026-09-12 | This execution plan | Documentation only; no hardware actions | Plan saved | Implement next slice below |
| 2026-09-12 | A0 hold/dependency audit; A1 initial readiness UI; A2 request codec | [Release audit](ARM_WIZARD_RELEASE_AUDIT.md); 385 selected tests passed in 24.89s; both new modules passed scoped Mypy | Shared browser/terminal next-step guidance and existing action forms; passive request syntax only; no hardware access | A1 interaction acceptance; A2 result/admission/retention; A3 supervised integration |
| 2026-09-12 | A2 passive result codec | 169 selected tests passed in 5.32s; `pytest-arm-passive-result-20260912-03` | Exact-request evidence, bounded startup bytes, known/unknown/incident outcomes; no authentication or physical dispatch | Original evidence admission, retained raw results and supervised-child integration |
| 2026-09-12 | A3 initial passive contained-process integration; isolated feedback import fix | [Process checkpoint](ARM_PASSIVE_PROCESS_CHECKPOINT.md); 212 selected tests passed in 63.36s, including real contained processes | Fixed incapable passive child; exact outer/inner result binding; raw failed output retained; physical dispatch still held | Original admission/storage and public wizard service; capable backend qualification |
| 2026-09-12 | A1/A3/A7 public passive rehearsal and diagnostic export | [Wizard checkpoint](ARM_PASSIVE_WIZARD_CHECKPOINT.md); 239 tests; actual application rehearsal/export verified | Rehearsal-only Arm action, retained result card, raw output export and rotation protection; no device I/O | Durable original attempt storage/readback and authenticated physical entry; capable lifecycle qualification |

| 2026-09-12 | A7 durable rehearsal diagnostic checkpoint | [Checkpoint implementation and evidence](ARM_PASSIVE_WIZARD_CHECKPOINT.md); 248 selected tests passed in 26.20s; actual application export and post-shutdown readback verified | Immutable bounded diagnostic publication; save failure retains raw results and fails operation; explicit read-only historical inspector; event-log scratch-directory separation; no device I/O | Recovery UI, original physical intent/outcome storage and authenticated entry remain unfinished; no physical-stage completion |

| 2026-09-12 | A1/A2 physical-entry guidance and vendor startup review | [Entry guidance](ARM_PHYSICAL_ENTRY_GUIDANCE.md); 156 selected tests passed in 20.31s in `pytest-arm-entry-guidance-20260912-01`; official vendor guide reviewed | Browser/terminal expose six owner-specific prerequisites and automatic-startup-motion warning; guidance cannot authorize I/O; received-board photo requested; stale camera fixture diagnosis corrected | Actual board/electrical evidence, original admission, qualified physical lifecycle and A4-A10 remain unfinished; no device access |

| 2026-09-12 | A3 passive observation using existing serial lifecycle | [Lifecycle checkpoint](ARM_PASSIVE_LIFECYCLE_OBSERVATION.md); 186 selected tests passed in 6.53s in `pytest-passive-lifecycle-20260912-02`, including real-clock four-second memory-provider observation | Actual lifecycle methods exercised; bounded startup retention, no write, partial-open/configuration distinction and uncertain cleanup preserved; all device observations synthetic | Package and pin lifecycle in contained wizard child; original physical admission/retention and qualification remain unfinished; no hardware access |

| 2026-09-12 | A3 contained lifecycle wired to public wizard | [Lifecycle integration](ARM_PASSIVE_LIFECYCLE_OBSERVATION.md); 361 tests passed in 45.39s in `pytest-passive-lifecycle-child-20260912-03`; actual application rehearsal/export verified | Three lifecycle scenarios, fixed source-checked archive and contained child, timeout/tamper rejection, actual lifecycle details retained/exported; serial API remains memory-only | Original physical admission/intent/outcome, capable registration and received-unit qualification remain open; A4-A10 not completed |

| 2026-09-12 | A3/A7 exact pre-dispatch rehearsal intent and paired recovery | [Wizard checkpoint](ARM_PASSIVE_WIZARD_CHECKPOINT.md); 142 tests passed in 36.14s in `pytest-passive-intent-20260912-02`; actual application export and post-shutdown pair inspection verified | Immutable prepared inputs before dispatch; write failure prevents child start; missing/mismatched outcomes remain non-replayable; exported intent preserved | Physical admission/authenticated originals, qualified storage and capable registration remain unfinished; no physical device access |

| 2026-09-12 | A1/A7 public historical passive inspection | [Wizard history usage](ARM_PASSIVE_WIZARD_CHECKPOINT.md); 189 tests passed in 30.87s in `pytest-passive-history-ui-20260912-02`; actual application historical inspection/export verified | Explicit named-session read in both modes, shared browser/terminal card, stale-source context and failed-outcome preservation; invalid paths rejected; no reconnect or replay | Physical admission/qualified storage/capable registration and A4-A10 remain unfinished; no hardware access |

| 2026-09-12 | A2 vendor electrical/control-line design review | [Design review and preserved source](ARM_USB_ELECTRICAL_DESIGN_REVIEW.md); full-page and detailed visual schematic inspection; vendor PDF hash retained | Separate nominal USB/servo supply nets and shared ground documented; reset/boot circuit confirmed; CreateFile-to-DCB uncertainty identified; no measured isolation claim | Accepted physical-entry evidence policy, capable registration, physical original storage and native qualification remain open; no device access |

| 2026-09-12 | A2 first physical-entry evidence decision isolated | [Policy proposal 002](ARM_USB_ONLY_ENTRY_POLICY_PROPOSAL.md); existing camera admission/original-scope and arm identity work-order reviewed | Identified unresolved evidence standard; proposed a narrowly scoped vendor-design/operator-report basis without measured-isolation claims; no policy applied | Explicit decision required before treating that basis as sufficient; capable registration/physical originals still required; no hardware access |

Implementation checkpoint: A0's hold/dependency map is documented, but individual
stale camera status entries still need reconciliation. A1's shared readiness
projection and guided form are implemented; its full interaction/recovery
acceptance is not complete. A2 has tested request and result codecs, not an accepted
physical-entry policy or authenticated evidence reader. A3 now has an initial
incapable process integration; physical lifecycle qualification is unfinished.
A4–A10 remain unfinished.
Do not mark an entire milestone complete from the initial slice's test count.

For every subsequent row record: changed files, exact test results, actual versus
modeled facts, export/run paths, failed/unknown outcomes, cleanup, remaining
blockers and whether any physical access occurred.

## 10. First implementation slice after this plan

1. Complete A0's release-hold/dependency map and update the ledger.
2. Audit the existing Arm UI against A1, then implement only the missing readiness
   explanations and guided metadata/export transitions with public UI tests.
3. Write and review A2's exact bench request/result/effect contract, including the
   electrical-isolation and firmware-evidence dependency decisions.
4. Implement A3 behind the reviewed boundaries and run its incapable test matrix.
5. Stop for the A4 physical-test entry conditions; do not silently open COM6 merely
   because this plan has been accepted or the arm was previously reported clear.

These are the next development actions. The remaining milestones stay visible
so early diagnostics lead toward the complete application rather than becoming
an unrelated collection of test scripts.
