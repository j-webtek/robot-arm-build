# First powered baseline — 2026-09-18

User confirmed supports/inspection, then reported main power connected and no
observed movement, and authorized proceeding. One baseline-only request was sent.
No motion command, torque setting, servo configuration, firmware change or reset
was sent. Do not remove motor power without supporting the moving links first.

## Hardware evidence

Boot ID: `ed6197256410da0aefaa1a9bf3a926cd` (unchanged from r3 startup).
Scan ID: `powered-baseline-20260918-01`.
All 14 reads returned their expected lengths with device error 0. The host
independently assessed the ordered raw evidence as BASELINE_CAPTURED.
Acquisition spans controller times 240202083 to 240209987 us: 7,904 us overall.
This is a sequential scan, not simultaneous measurement or proof of future pose.

| Servo ID | Measured position (counts) | Goal register (counts) | Moving flag |
|---|---:|---:|---:|
| 11 | 2047 | 0 | 0 |
| 12 | 2390 | 0 | 0 |
| 13 | 1727 | 0 | 0 |
| 14 (elbow) | 2723 | 0 | 0 |
| 15 | 2041 | 0 | 0 |
| 16 | 2042 | 0 | 0 |
| 17 | 2051 | 0 | 0 |

Verified export:
`software/runs/wizard-exports/wizard-20260918T143723430707Z-40fff917f4d34c7781b6cc1d69e25e9f`.
Raw feedback and acceptance are retained. Export integrity was independently
rechecked. The durable baseline claim is consumed; no repeat POST or automatic
reset was attempted. Motion remains excluded for this controller session.

## Finding and implications

Position feedback works on all seven IDs without depending on a visual movement
confirmation. However, every separately acquired goal-position word was zero.
Pinned library definitions agree that goal is address 42 and present position is
56. These reads alone cannot prove why the goal words are zero, whether they
reflect uninitialized startup command state, or how they will behave after an
acknowledged command. They must NOT be used as destinations or as position errors
to compensate. No command-to-motion or reverse-motion accuracy claim follows.

Offline regression with these observed position/goal values confirms the current
whole-arm admission rejects narrow windows with WHOLE_ARM_OUTSIDE_WINDOW, and
fresh-elbow admission rejects BASELINE_OUTSIDE_PROFILE even for a requested target
equal to 2723. This is an initialization/admission assumption mismatch, not proof
that the arm failed a movement. The regression uses read-only bus doubles; existing
gates were not weakened or changed. Fifteen related tests passed.

## Next evidence-driven work

1. Design a separately identified first-command initialization mode. Keep normal
   post-command target-tracking checks intact. Do not broadly disable them or
   widen joint windows to admit zeros.
2. Require repeated fresh position/moving observations for initial stationarity,
   explicit actual-position bounds, and a small proposed delta from current
   elbow position. A single stationary flag is insufficient to prove stability.
3. Retain the zero goal as observed pre-command data with unknown command meaning.
   Capture exact dispatched count, acknowledgment, subsequent goal readback and
   fresh feedback to determine whether goal semantics become usable after a write.
4. Include torque/mode capability review: positions and moving flags alone do not
   establish torque-enabled state. No torque/configuration changes without review
   and separate authorization.
5. Simulate startup-zero, real target mismatch, stale/failed reads and unexpected
   motion cases before proposing a firmware/policy change. Do not reuse this
   historical scan as a fresh motion-boundary sample.
6. Preserve this boot's consumed baseline evidence. Any later reset, deployment,
   provisioning or motion session must follow its reviewed scope; no automatic
   recovery move or homing from zero-register values.

## Startup-observation implementation checkpoint

`startup_position_baseline.h` now implements a separate finite two-scan observation
for explicitly zero-goal startup state. It requires reviewed joint windows,
stationary moving flags on both scans, bounded drift, a minimum interval and a
maximum wait, valid read timing and a freshness check that permanently fails on
expiry/clock reversal. It retains both scans and never retries, generates a goal,
or calls a servo-write method. Normal target-tracking gates remain unchanged.

Native simulation covers stable acquisition, early polling without extra reads,
nonzero goals, moving flags, read failure, drift, window violation, timeout,
invalid policy, clock reversal and freshness expiry. Three targeted test modules
passed (including the observed-zero-goal rejection regression and existing
whole-arm tracking tests). This is not deployed and not a complete first-command
admission path: command-delta binding, torque/mode evidence, identity/serialization,
host assessment and integration with the authenticated motion boundary remain.
Synthetic test bounds are not a commissioned hardware policy.

Target/control follow-up: startup observation now supports one consumed elbow
target-binding attempt, constrained to the reviewed elbow window, 1024..3071
reference range, a maximum allowed delta no larger than 64 counts, and fresh
second-scan positions. Failed binding cannot be retried; no command is sent.

The pinned SMS_STS header identifies operating mode at address 33 and torque
enable at 40, outside the existing 56..70 feedback block. Its `ReadMode(-1)`
cached branch indexes `33-56`, outside that cache; our implementation does not
use it. This source finding does not establish that it caused the historical
reverse-motion discrepancy. `servo_control_state_read.h` instead performs direct
one-byte reads for IDs 11..17 with fresh timestamps, exact lengths/device errors,
retained failure evidence, no retries and no writes. Matching requires a supplied
reviewed mode byte, torque-enable byte 1 and bounded freshness. Actual hardware
mode/torque state remains unknown; this producer is uninstalled. It does not
enable torque automatically. Identity/serialization and composition with the
authenticated write boundary still remain before deployment can be proposed.

Pre-command composition follow-up: `startup_precommand_evidence.h` now joins the
two-scan position observation, direct control-state reads, retained evidence and
one-shot elbow target binding. It publishes first scan, second scan and control
read records before declaring the target bound. Any publication/read/state failure
stops progression. The supplied write-boundary predicate checks the exact converted
target, both evidence ages and sink integrity; failure latches permanently.
The class has no servo-write method and does not authenticate or execute commands.

Native tests inject output failure at each of the three publication points,
disabled torque, changed target at boundary and expired evidence. Existing stable
startup, direct-register and normal-tracking regressions remain required. This
component is uninstalled. The remaining integration must define a distinct signed
startup command/policy mode and record ordering; it must not make an existing
normal-mode authorization silently permit zero-goal initialization. Host schema
assessment and authenticated execution tests must cover that distinction before
any future deployment/provisioning approval is requested.

Offline authorization contract checkpoint: `startup_command_contract.py` defines
`rocell.startup_session_plan.v1`, wrapping exact base64-encoded normal v3 command
bytes and an explicit ZERO_GOAL_TWO_SCAN policy. The startup verifier binds the
entire wrapper to the challenge, boot, expiry, execution origin and an exact local
policy; it consumes failed attempts. Existing normal authorization rejects the
wrapper, and startup authorization rejects normal plans. HMAC framing is reused,
but the plan parsers remain intentionally distinct. Thirty startup/normal
authorization tests passed, including cross-mode, policy, signature, expiry,
wrong-key, wrong-boot and replay rejection. Only public test inputs were used.

This is host reference-contract validation, not a native startup executor or a
deployment-ready capability. The installed firmware still rejects this new plan.
Next implement matching native parsing, asynchronous authenticated ownership over
the two scans and final guarded dispatch, retain all new records, and independently
assess them on the host. No actual key/policy has been provisioned, no startup token
has been sent, and no hardware activity occurred in this checkpoint.

Native parser follow-up: `startup_plan_structure.h` parses only the distinct
startup wrapper, checks exact controller-approved startup policy fields/windows,
strictly decodes the inner plan, and delegates existing command/payload validation
to `StartPlanStructure`. It requires a DEVICE_CAPTURE-origin v3 inner plan and
reserves capacity by limiting startup sample pairs to six. Structural parsing
does not expose a bound request until payload/hash/conversion binding succeeds.
Nine host/startup tests passed, including compiling the real C++ parser against
Python-produced synthetic request bytes and rejecting normal plans, mode/policy
changes and invalid base64. DEVICE_CAPTURE in those fixtures exercises parsing
only; these are not actual hardware records. Authenticated asynchronous execution
and independent host review of startup evidence remain to be connected/tested.

### Authenticated startup orchestration checkpoint (offline only)

`startup_authenticated_owner.h` now composes authorization, plan/payload binding,
two position scans, direct mode/torque reads, evidence publication, final guarded
dispatch and strict post-command sampling. Each owner consumes one attempt; it
does not resend a command. Authorization and startup observations are recorded
before the existing receipt/converted/dispatch/write/sample records. Normal
post-write target readback must still match the transmitted count.

The focused nine-file regression suite passed **29 tests**. Its native owner test
executes twelve scenarios: success; rejected authentication; torque disabled;
control-record publication failure; disabled ACK checking; external fault;
post-write target mismatch; failed write acknowledgment; converted-record
publication failure; expired lease; reversed clock; and interference. Success
performs exactly one simulated write. Pre-write failures perform none; post-write
failures latch without retry.

Scope limitation: the owner orchestration test uses explicit authentication,
parser, converter and bus doubles. Separate tests exercise real native envelope
and startup parsing, but a single integrated real-authentication/parser-to-write
test remains required. These results are not hardware movement evidence.

Next work, in order:

1. Test real native authorization and parsing through the startup owner together.
2. Add independent host review of startup record ordering, identities, timestamps,
   control-state evidence and terminal outcome, including malformed exports.
3. Integrate distinct startup policy/configuration and exclusive runtime routing;
   compile and review the exact candidate and deployment scope.
4. Obtain separate firmware/provisioning approval before changing the controller.
   Support articulated links before any motor-power removal.
5. Only then acquire fresh live startup evidence and attempt one bounded command,
   followed by strict endpoint readback. Expand to reverse/cycles only on success.

The installed r3 image is unchanged. No key or motion policy was provisioned, no
startup request was sent, and no new physical motion was commanded in this work.

### Integrated native startup pipeline (offline follow-up)

`test_startup_native_pipeline.py` now sends Python-signed startup tokens through
the real native envelope, startup parser, payload/hash binding, startup owner,
two-scan/control-state checks and guarded write/sampling pipeline. Windows BCrypt
performs actual HMAC/SHA-256. The converter uses exact function bodies extracted
from the hash-verified pinned Waveshare source, with the production
`ReferenceElbowAdmission` adapter. Only clock and servo bus are simulated.

The ten cases cover success, post-write target mismatch, signature corruption,
authenticated wrong wire count, payload hash, boot identity, conversion version,
local mode policy, simulation origin and transmitted-payload substitution. The
success path produces exactly one write and all twelve ordered evidence records
(including three sample pairs). Pre-admission failures produce zero bus reads,
zero writes and no evidence records; post-write mismatch produces one pair and
faults without retry. Reference conversion preserves the shared goal variable.
The exported authorization hash is checked against the exact signed plan bytes.

This closes the real-authentication/parser orchestration test gap above, not the
hardware-validation gap. The host verifier for startup evidence and runtime/
configuration integration are still pending. Captured samples are not themselves
an independent endpoint-arrival assessment. No controller communication or
firmware/configuration changes occurred during this test.

### Independent startup session assessment (offline follow-up)

`startup_session_assessment.py` now validates the startup record prefix against
the exact frozen plan hash, boot/command identity and locally approved policy.
It independently decodes both seven-joint scans, checks zero goals, stationary
flags, windows, inter-scan delay and drift, then checks all fourteen direct
mode/torque reads. Evidence must precede receipt and remain fresh at the recorded
write boundary. The commanded elbow delta is checked against the measured second
scan, not the zero goal register. The frozen sampling schedule must match.

After those checks it delegates unchanged receipt/write/endpoint semantics to
`assess_session`; it does not synthesize a normal-mode baseline. The native
pipeline test now has eleven cases, including acknowledged dispatch with matching
target readback but a stationary simulated joint. The host distinguishes:

- Arrival: `DIAGNOSTIC_ENDPOINT_CRITERIA_MET`.
- Fresh position not settled at the requested endpoint during the captured
  interval: `FRESH_POSITION_NOT_SETTLED_AT_DESIRED_TARGET`.
- Post-write mismatch with terminal fault: `SESSION_FAULT`.

Seven additional mutations of actual native output test hash, order, disabled
torque, drift, corrupted acquisition time, schedule and missing-record rejection.
Invalid or incomplete pre-command evidence raises `ValueError`; callers must
retain it as inconclusive, never as a successful endpoint assessment. Transport
provenance, durable export and progression authority remain explicitly unverified
or false. CAMERA/stylus-space accuracy is not inferred from servo counts.

Remaining: connect this reviewer to the startup transport/export/UI path, add
distinct runtime/configuration integration, compile/review the candidate, obtain
separate deployment/provisioning approval, and validate fresh live endpoints.

### Startup collection and reproducible exports (offline follow-up)

The shared transport collector now accepts startup records only with explicit
`startup=True` and boot-bound v3 transport. It checks ordered prefixes, stable
terminal status and cross-record identities. Normal collection still rejects
startup records. Startup exports use a distinct v2 transport bundle with explicit
mode, and replay selects that mode rather than guessing from record contents.

`startup_planned_run.py` saves and verifies the plan and local review context
before the first injected GET. It links exact transport response evidence and
assessment in the existing wizard export format, then independently replays the
saved files. No POST, token, serial access, provisioning or recovery is performed.
Native-generated success, non-arrival and mismatch traces round-trip through
export/replay. A terminal partial startup prefix is exported as INCONCLUSIVE
without pretending it contains endpoint evidence. Replayed outcomes must match.

This is the application/export service, not completed wizard UI wiring or a live
startup transport capability. Malformed/unstable transport or export errors raise
and stop collection, without retry; incomplete transport-failure retention needs
further integration. GUI action wiring and distinct controller startup runtime/
configuration remain pending. No hardware activity occurred in this checkpoint.

### Separate startup configuration/runtime (offline follow-up)

`controller_startup_config.h` accepts only `rocell.controller_startup.v1`, with
explicit `controller_policy` and `startup_policy`. The unchanged normal parser
validates controller bounds, conversion, port, lease and whole-arm windows.
Startup validation requires matching policy ID/windows, explicit zero-goal mode,
integer mode/limits and a separation interval shorter than the challenge lease.
Normal configuration is not implicitly upgraded to permit startup.

`startup_listener_owner.h` maps both pre-command preparation and post-command
sampling to the existing listener's exclusive working state. The separate
`configured_startup_runtime.h` constructs that owner, bounded 16x2304 evidence
store, reference converter and one-use socket listener only after configuration
and key checks. It supplies the existing runtime/status interface without
modifying the installed normal runtime. Place it in static storage, not on the
ESP32 task stack. It does not load files, provision keys or enable torque.

The native pipeline now compiles/instantiates this runtime with inert network
adapters and verifies valid initialization, rejection of a second initialization,
idle polling and lease-expiry fault with zero servo reads/writes. Seven malformed
configuration variants are rejected. The focused regression run passed 40 tests.
Actual signed socket ingress through this runtime (rather than direct owner
ingress), exclusive route composition, embedded build size and runtime RAM remain
to be tested before a deployable candidate can be proposed. No firmware or
hardware configuration changed.

### Signed socket integration and embedded memory finding

The native pipeline now also drives the configured runtime through a scripted
nonblocking socket in 23-byte chunks. Each signed/invalid test token is exercised
with normal delivery, a short acceptance response, peer disconnect and trailing
request bytes. The valid path writes once; failed ingress/acceptance writes zero
times, performs zero servo reads and never re-arms the listener. This is host
simulation of the socket adapters, not an actual Wi-Fi delivery test.

Generated separate r4 startup candidate with retained baseline/motion claim
composition and separate `/rocell-startup.json` and `/rocell-startup.key` paths.
Its first ESP32 compile failed: static DRAM exceeded the linker region by 18,168
bytes. Verified failure export:
`wizard-20260918T151302862321Z-b4a63ff207ec48bd9f823b69c40881c0`.
There is no successful r4 application artifact and it must not be deployed.

The r5 candidate replaces the startup runtime's large static inner object with
one bounded, retained `new(std::nothrow)` allocation after policy/key validation.
Allocation failure latches `STARTUP_MEMORY_UNAVAILABLE` before opening a listener;
the temporary key is wiped on either allocation result. Host failure injection
verifies no bus activity and no retry after memory becomes available. The runtime
must still be long-lived; this is not per-command allocation or unbounded storage.
The focused regression suite passed 43 tests after this change. Embedded compile
and live heap/stack headroom are separate requirements, not proved by those tests.

r5 embedded compile succeeded using `default-4mb-no-psram`. Verified build export:
`wizard-20260918T151519611374Z-b1140684e23d4df4a01e82e8c354f0e7`.
Compiler reports 1,075,353 program bytes and 56,304 static RAM bytes. The app binary
is 1,081,936 bytes, SHA-256
`ceb0fe25bc03aac0eb26f6d02aff17c59198f322cf872b6f403ecafeac458698`.
Partition and bootloader digests match the prior compatible profile. The reported
271,376 remaining RAM bytes are not measured runtime free heap or stack headroom:
Wi-Fi, the bounded session object and JSON parsing allocate additional memory.
No deployment, policy/key provisioning, controller reset or movement occurred.

### r6 stack/compatibility review

Disassembly showed the r5 startup configuration parser had a 5,152-byte frame
against the toolchain's configured 8,192-byte loop task stack. r6 moves its bounded
4 KiB JSON scratch buffer into the long-lived parser. The compiled frame is now
1,040 bytes; this reduces a demonstrated stack-pressure source without claiming
a full call-chain bound. r6 compiles with 60,400 static RAM bytes and a 1,081,872-byte
app binary. `review_startup_candidate.py` independently checks build/source hashes,
app-slot fit, profile partition/bootloader digests and selected ELF stack frames,
and exports reproducible offline evidence. Focused regressions: 43 passed.

See `STARTUP_R6_DEPLOYMENT_PROPOSAL.md` for exact artifact identity, export IDs,
installation boundaries, physical support requirements and remaining limitations.
This is a proposal, not deployment approval. r3 remains installed.

Installer preparation follow-up: the deployment script now supports only the
reviewed 2, 3 and 6 revisions, with r6 requiring the retained r3 image as expected
predecessor. New `--preflight-only` verifies local artifacts and existing-journal
absence before any device-library import. The actual workspace preflight passed;
five offline regression tests passed. Verified app bytes are retained in memory
for flashing to remove the image-path reopen race. No deployment journal was
reserved and no device was opened. Explicit r6 approval and supported USB-only
physical setup are still pending; see the proposal for exact scope.

### Retained startup collection failures

The startup transport export now retains bounded response bodies received before
semantic/chronology rejection, plus fixed error codes for receive failure or
invalid size/type. It never exports arbitrary exception messages or retries the
failed request. Oversized bodies are rejected without storing them; failures
inside the socket adapter cannot preserve bytes it did not return to the caller.

`rocell.startup_transport_failure.v1` bundles replay through the same explicit
startup collector. Replay must fail at the recorded point, consume exactly the
retained responses and preserve each response hash/path. A successful collection
cannot be relabeled a failure; extra/missing/reordered/altered data is rejected.
Planned-run review links this failure export and returns INCONCLUSIVE, not arrival.
Export verification failure itself raises and stops the workflow.

Focused transport/planned-run/native pipeline tests: 38 passed, covering timeout,
malformed JSON, oversize, changed status, late failure, altered bundles, no retry,
failed export verification and full planned-run failure replay. This closes the
startup collection-failure retention gap noted above for responses available at
the bounded reader boundary. GUI wiring and approved hardware deployment/testing
remain pending. No controller activity occurred.

### Wizard startup review action

The arm section now registers `review_startup_servo_run` ("Review saved startup
command and endpoint (offline)"). It takes a startup-run export folder name from
the assigned export root and replays the linked plan, context, capture and
assessment. The parent service owns the published result; no diagnostic worker,
network, serial or movement action runs during replay.

The result panel shows replay status separately from endpoint category, initial
elbow position/count delta and startup checks. Inconclusive results explicitly
say the endpoint is not verified. Hardware remains NOT QUALIFIED and stylus-tip
accuracy remains unmeasured, even when retained endpoint criteria were met.
Service and actual JavaScript renderer tests cover failed-collection replay,
missing exports and inconsistent authority flags. The focused wizard/native/
failure-retention suite passed 16 tests. This is offline review UI, not live
startup commissioning or an installation button; those remain separate.

### Startup provisioning preparation (offline, synthetic only)

`stage_startup_image` now stages only `/rocell-startup.json` and
`/rocell-startup.key` in an in-memory LittleFS copy. It requires an explicit
startup configuration envelope and the supplied native validator, refuses either
existing destination, preserves all prior file/directory content, remounts and
verifies the result. Normal staging keeps its original filenames and schema.

The r6 host validator uses `ControllerStartupConfigParser` from the exact copied
r6 candidate header set, verified against the successful compile export. Its
angle-bracket include prevents accidentally using adjacent edited source instead
of candidate headers. Build export:
`wizard-20260918T152918382049Z-043741e4bc364fa5b13ff370e145957b`.
Executable: `.firmware-tools/bound-policy-validator-5juihe6t/validate.exe`, SHA-256
`3a6c5647f80891237942639ed497441ccc105b5f455addf0119c16519ba44fe5`.
The original ArduinoJson per-file build hashes were not recorded; this known
historical library-binding limitation remains explicit in the validator report.

32 tests passed across normal/startup filesystem staging, native policy validation
and build binding. Synthetic tests verify normal-key preservation, exact startup
paths, no overwrite, and wrong schema/mode/windows/ID/type/conversion rejection.
No real key or live policy was created, no actual backup image was staged, and no
controller/filesystem was modified. r6 deployment and subsequent provisioning
each still require separate approval and exact live policy review.

### Startup host send preparation (fake transport only)

`StartupStartSender` now uses the existing bounded one-use HTTP transport with a
distinct startup policy/parser/signature preparation step and delivery schema.
Normal plans are rejected before socket access. `send_prepared_startup` saves and
verifies exact startup plan, policy context and challenge before consuming a
durable boot/nonce claim and invoking the supplied sender once. The claim uses
the same namespace as normal starts, so changing mode cannot bypass consumption.
No key or signed token is exported. Controller-reported acceptance and uncertain
delivery both remain explicitly separate from endpoint verification.

27 focused startup/normal send tests passed. Startup tests used fake sockets and
synthetic keys, covering exact signed bytes, lost reply, cross-mode retry denial,
invalid normal plan, failed pre-send export (zero send) and failed post-send
verification (claim retained). Existing transport regressions use loopback only.
No arm address was contacted, no live request was sent and no UI live-start action
was enabled. Linking this delivery export to later startup capture/replay and
reviewing live-start admission remain next; actual firmware/provisioning approval
is still outstanding.

### Delivery-to-endpoint linkage and wizard review

`startup_started_run.py` verifies the prepared startup export, exact plan/context,
challenge, delivery flags/acceptance-body hash and consumed boot/nonce claim before
read-only collection. It links the resulting startup review by hashes and checks
that replay uses the same plan and policy context. It never sends, reconstructs
a token or releases a claim. Modified claims fail before any GET.

Tests link native-generated simulated arrival to a synthetic acceptance record,
and independently cover acceptance/uncertain delivery followed by inconclusive
collection. Endpoint outcome is not inferred from delivery. The wizard action
`review_started_startup_run` now displays delivery and endpoint outcomes together,
with resend disabled and hardware NOT QUALIFIED. Service/renderer tests verify
that reviewing a lost-reply/inconclusive result makes no new send or connection.

This completes saved delivery-to-startup-capture review, not live commissioning.
No actual request, firmware or provisioning change occurred. Existing r6 approval
request remains pending; repeatable reverse-motion operation still needs subsequent
runtime/session design and fresh hardware validation after first-command evidence.
# Offline mixed-goal ledger follow-up — 2026-09-18

Implemented `servo_goal_ledger.py` to rebuild per-servo goals from verified linked
startup exports and assess a later seven-servo observation. Native simulated
records demonstrate an elbow-only updated goal with six untouched zero goals.
Invalid continuity and uncertain predecessor evidence are rejected. The focused
ledger/native/startup-link/wizard/contract suite passed 21 tests. This does not
authorize continuation, establish physical accuracy or add hardware evidence.
See `STARTUP_TO_REPEATABLE_MOTION_PLAN.md` for remaining native campaign work.
