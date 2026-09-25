# From verified arm control to ghost typing: implementation plan

Status: active roadmap, 2026-09-20.

## Objective and scope

Build one understandable path from a requested destination to a measured result,
then reuse it for ghost-keyboard typing and eventual physical keyboard/Android
tapping. Prefer existing code and official Waveshare interfaces over duplicate
frameworks. Collect comparable evidence before tuning commands.

This plan authorizes no hardware effects by itself. Software and offline analysis
can progress independently. Physical execution requires current compatible device
state and bounded motion admission, not historical poses. Camera mounting,
registration, physical contact and claims of measured stylus accuracy remain later
work. Preserve installed settings, credentials and previous diagnostic evidence.

## Current baseline

- Official JSON encoding, serial feedback and custom diagnostic HTTP paths exist.
- The last documented installed r31 local-step path is not a general campaign
  executor: fixed starting envelope, one paired target write, sticky reservation
  and strict arrival checks. Current deployment is not freshly verified here.
- A twelve-leg synthetic campaign, independent endpoint classifier and verified
  exports exist. Batch review now publishes readable Markdown and JSON.
- Historical shoulder residuals are evidence to investigate, not a universal
  correction or a statement of Cartesian accuracy.
- Application code contains many historical experiments. Preserve them; identify
  supported entry points before consolidating.

See [source audit](CONTROL_ARCHITECTURE_AND_INTERFACE_AUDIT.md) and
[official tooling decisions](OFFICIAL_TOOLING_REUSE_PLAN.md). This document defines
the forward execution order; older experimental deployment steps are not implied.

## Intended ownership

| Layer | Responsibility | Must not do |
| --- | --- | --- |
| Wizard / CLI | Select workflow, preview, show state/results | Independently issue device commands |
| Application workflow | Finite sequencing, outcome checks, progression | Treat a sent command as arrival |
| Arm adapter | Existing protocol/transport and capability mapping | Retry uncertain movement silently |
| Controller | Supported bounded execution and fresh diagnostic acquisition | Require a new build for each test target |
| Evidence / analysis | Preserve observations, calculate errors, export reports | Mix simulation with physical evidence |
| Geometry / planning | Frames, stylus offset, targets, modeled paths | Claim modeled geometry is measured calibration |

Do not create all these as new packages. Reuse existing modules, extract code when
there is a concrete second caller, and move files only with regression coverage.

## Phase 1 — Review physical evidence already collected

Priority: first. No hardware access required.

Tasks:

- [ ] Inventory representative physical result bundles and their schema versions.
- [ ] Implement a read-only importer using existing bundle verification and native
  record decoders. Do not coerce physical records into the simulation schema.
- [ ] Retain source manifest hashes, boot/command identity, firmware/configuration
  identity where available, timestamps, raw positions and accepted targets.
- [ ] Represent absent freshness, delivery or status evidence as unknown. Reject
  corruption; distinguish an unsupported schema from a failed movement.
- [ ] Calculate endpoint error, measured change, settling evidence and repeatability
  only where supported. Group by target, direction, speed and configuration.
- [ ] Extend the readable report to include physical results, exclusions and
  limitations. Never pool synthetic and physical results into one statistic.

Deliverable: one verified physical-result review and a repeatable offline command
to produce it. Start with one known format, then add formats as needed.

Tests: valid bundle; corrupt hash; missing records; unsupported schema; stopped
movement; missing readback; mixed build/configuration; simulation/live separation.

Done when: an existing physical trial can be traced from original evidence to its
reported endpoint error without a device command or invented information.

## Phase 2 — Select and expose one control workflow

Tasks:

- [ ] Compare pinned r31 build provenance with current source and host clients.
  Source-level routes alone do not prove availability on the running controller.
- [ ] Inventory required capabilities: measured state, target submission, supported
  target readback, observation identity, terminal outcomes and fault evidence.
- [ ] Choose the smallest existing adapter supporting those capabilities. Retain
  official JSON. Do not install the SDK just to duplicate working serial code.
- [ ] If SDK reuse is justified, pin its revision and review units, serial-open
  effects, retry behavior, error handling and licensing before integration.
- [ ] Define a narrow shared workflow interface for preview, execute, observe and
  export. Keep requested target, transmitted command, accepted target and measured
  endpoint separate; unsupported fields remain explicit.
- [ ] Ensure one device owner, bounded timeouts and no automatic retry after
  uncertain delivery. Connection loss must not trigger blind resume or return.
- [ ] Record the specific controller gaps blocking repeated campaigns and choose
  the minimal implementation approach before changing firmware.

Deliverable: documented adapter decision and fake-transport integration tests.

Done when: the CLI and future wizard have one supported execution entry point,
and the exact remaining hardware capability gaps are known. Do not bypass the
existing r31 reservation by switching command paths.

## Phase 3 — Reusable finite physical campaigns

Tasks:

- [ ] Define host-side test plans with targets, repeats, supported speed/acceleration,
  travel bounds, deadlines, evidence requirements and a finite command budget.
- [ ] Address the controller's one-step lifecycle only as needed for a reusable
  bounded session. Preserve command correlation and fault records.
- [ ] Distinguish accurate arrival, stable bounded miss, and invalid/uncertain
  evidence. A miss may be useful data; only reviewed policy permits progression.
- [ ] Reacquire state before each leg. Do not substitute the previous target for
  the actual pose, or reuse stale starting coordinates.
- [ ] Export intent and observations through the existing verified export workflow.
  Export failure or uncertain delivery ends the affected sequence without retry.
- [ ] Simulate success, residual offsets, wrong direction, stale/missing feedback,
  unexpected neighboring-joint motion, disconnect and export failure.
- [ ] After compatibility/release review, begin with the existing small local
  envelope. Gather a fixed-build dataset before broadening travel or speeds.

Deliverable: a finite campaign whose ordinary target/repeat changes do not require
a firmware build, plus reproducible result exports.

Done when: bounded bidirectional repeats can be measured and reviewed under one
configuration, with no unverified continuation after a fault. A firmware change,
if necessary, is a reviewed reusable capability change, not an experiment loop.

## Phase 4 — Learn from patterns before compensating

Tasks:

- [ ] Test matched targets approached from both directions with repeats.
- [ ] Vary speed or other supported factors one at a time; record configuration.
- [ ] Compare persistent bias, direction-dependent error, endpoint spread and
  settling behavior. Report small sample sizes and confounded comparisons.
- [ ] Reserve separate movements for held-out validation before fitting a model.
- [ ] Apply the simplest correction supported by those results, with explicit
  validity bounds. Preserve mechanical coupling of paired shoulder servos.
- [ ] Compare corrected and uncorrected held-out results; retain a rollback path.

Deliverable: evidence-backed recommendation to keep baseline commands or enable
a bounded correction. No compensation is also a valid result.

Done when: any accepted correction improves held-out results without unexpected
travel or degraded repeatability. Encoder improvements are not millimetre claims.

## Phase 5 — Workcell geometry and official model reuse

Tasks:

- [ ] Inventory existing geometry, kinematics, keyboard and phone models before
  creating replacements. Consolidate dimensions and coordinate conventions.
- [ ] Make base-to-board, board-to-keyboard, board-to-phone and gripper-to-tip
  transforms explicit. Label assumed versus measured values and units.
- [ ] Configure key centers, screen targets, hover height and simulated press
  depth separately from control logic.
- [ ] Evaluate the official ROS 2/MoveIt model offline. Verify Pro geometry, joint
  mapping, limits and tool frame; do not auto-launch the physical driver.
- [ ] Add modeled board, devices, stylus and clearance objects. Check entire paths,
  not only endpoints, for reachability and modeled collisions.
- [ ] Compare model predictions with known joint observations where possible.

Deliverable: reproducible ghost workcell and previewable approach/press/retract
paths, using existing code or official planning tools where they reduce work.

Done when: target coordinates produce consistent modeled tool poses and rejected
unreachable/colliding paths. Model validation does not replace physical registration.

## Phase 6 — Ghost typing through the same execution path

Tasks:

- [ ] Translate a short key sequence into hover, approach, simulated press and
  retract segments. Keep the ghost typing plane physically clear of the board.
- [ ] Preview the whole sequence before execution; show assumptions and bounds.
- [ ] Start offline, then perform bounded non-contact execution when the required
  physical envelope is established. Verify each segment before advancing.
- [ ] Export per-key and per-segment outcomes, with missed/uncertain endpoints
  distinct from successful motion. No claim of a real keypress without evidence.

Deliverable: a short repeatable ghost-key sequence using the same control and
evidence workflow as characterization, not a separate robot-control implementation.

Done when: the sequence can be repeated, reviewed and interrupted on invalid
evidence without guessing current state or automatically continuing.

## Phase 7 — Wizard integration and later physical commissioning

Tasks:

- [ ] Expose connection status and actual available capabilities in the wizard.
- [ ] Add test preview, finite run progress, terminal outcomes and readable reports.
- [ ] Use the same application services as the CLI; avoid duplicate UI calculations.
- [ ] Keep exports in `software/runs/wizard-exports`, with an explicit configured
  destination where supported. Redact credentials from reports and logs.
- [ ] Keep firmware recovery and Wi-Fi configuration separate from normal runs;
  reuse official setup commands instead of inventing a new protocol.
- [ ] When hardware mounting is ready, register the camera, board and stylus tip;
  verify clearance, contact depth and actual keyboard/screen actuation separately.

Deliverable: one operator-facing workflow for connect, inspect, preview, execute
and review. Basic report UI can be wired earlier without waiting for ROS or contact.

## Working rules and progress tracking

- Prioritize Phase 1 now. Do not expand firmware while physical evidence can be
  analyzed offline. Advance phase-by-phase; update checkboxes with evidence links.
- Keep decisions short: what was reused, changed, verified and still unknown.
- Run focused unit and integration tests for each change; add regression coverage
  before consolidating live code. Preserve existing imports where practical.
- Use readable comments to explain units, device side effects and non-obvious
  constraints, rather than narrating straightforward code.
- Do not delete historical experiments merely to reduce file count. Mark supported,
  offline-only and superseded paths clearly, then consolidate covered features.
- Avoid new scaffolding without a concrete caller or demonstrated capability gap.
- No universal arbitrary accuracy target: choose tolerances from observed behavior
  and eventual target geometry, documenting the rationale before the test.

## First milestone

**Import one existing physical trial and produce a verified human-readable report
that separates accepted command, measured response and endpoint error.**

This provides immediate value and establishes the evidence contract for the later
campaign runner, wizard and ghost-keyboard work.

### First milestone implemented — 2026-09-20

`application/physical_local_step_review.py` imports the existing physical
`rocell.local_step_run.v1` format without hardware access. It verifies the run and
each referenced accepted movement bundle, reconstructs the plan from raw baseline
records using the existing validator, and exports JSON plus readable Markdown.
Sibling-only record references prevent arbitrary traversal. Source manifest hashes
are retained. Device authentication and installed firmware are not independently
verified by this offline importer.

The r31 historical run yielded 20 validated movement records. Accepted goals were
2405/1709; last accepted movement positions were 2415/1702, giving +10/-7 counts
of endpoint error. The original STOPPED / ARRIVAL_DEADLINE outcome remains intact.
Post-fault settling is explicitly excluded in this first version; the separately
documented +9/-7 settled result must not be confused with this endpoint.

Reproduce from `software`:

```powershell
..\.venv\Scripts\python.exe -m rocell.application.physical_local_step_review --source runs/wizard-exports/wizard-20260919T234006065057Z-53ea59edfe2d4b20bfc7d3eaae25253e --exports runs/wizard-exports
```

Verified review bundle:
`runs/wizard-exports/wizard-20260920T050940661406Z-a1542de626764ae5a758d76eb6ae6a2a`.
Eight focused tests passed, including the real saved evidence regression. That
private-evidence test skips when the historical bundle is not distributed; generic
integrity, schema and reference validation tests remain available.

Phase 1 is partially complete: next add key-free post-fault settling validation,
more negative correlation cases, and additional physical schemas as required.
Multi-trial configuration grouping and repeatability remain pending. No physical
commands, firmware installation or compensation occurred.

### Post-fault settling importer implemented — 2026-09-20

The key-free `physical_settling_review.py` now validates the original fault against
the last accepted movement and validates settling records by boot, command,
sequence, fault digest, scan order, raw encoder bytes, unchanged targets/torque
and stationary sample evidence. It neither signs receipts nor accesses hardware.
The existing physical importer includes this as a separate report section.

Historical r31 review: 20 movement records plus the original fault and five
settling records; movement errors +10/-7 counts, post-fault errors +9/-7 counts.
Additional shoulder change was -1/0 counts. STOPPED / ARRIVAL_DEADLINE remains the
movement outcome, not a retrospectively passed endpoint test.

21 focused tests passed, including incorrect boot/command/sequence/fault linkage,
stale scans, duplicate samples, changed target/torque, inconsistent encoder bytes
and insufficient stability evidence. Verified report:
`runs/wizard-exports/wizard-20260920T131033373447Z-ba95e97da8804920a3dccd17e0b7e7b0`.

Next: inventory another physical trial format and compare compatible trials
without pooling firmware/configuration changes. Multi-trial repeatability and
firmware provenance verification remain pending; no compensation is inferred.

### Cross-trial comparison implemented — 2026-09-20

`application/physical_trial_comparison.py` compares the saved r29 derived recovery
analysis with revalidated r31 local-step and same-boot settling evidence. It checks
the r29 analysis bundle and its exact run/pose-assessment attachment digests,
validates arithmetic, and labels its evidence level separately. It does not claim
to independently replay all r29 raw pose records or verify firmware equivalence.

Settled shoulder residuals: r29 +10/-7 counts; r31 +9/-7 counts. Different targets,
different recorded revisions and r29's diagnostic restart prevent treating these
as matched repeatability trials. No pooled statistic or compensation is produced.

25 focused comparison/import/settling tests passed. Verified report:
`runs/wizard-exports/wizard-20260920T131335963170Z-bbb92b8eec544381b9950780b2db3edc`.

Run from `software`:

```powershell
..\.venv\Scripts\python.exe -m rocell.application.physical_trial_comparison --recovery-source runs/wizard-exports/wizard-20260919T212458408646Z-f7e6a7fbf4e942208ea216666ddf55f0 --local-source runs/wizard-exports/wizard-20260919T234006065057Z-53ea59edfe2d4b20bfc7d3eaae25253e --exports runs/wizard-exports
```

Next priority shifts to Phase 2's control-path decision: identify the minimum
reusable execution capability for matched bidirectional trials on one fixed
configuration, rather than accumulating more one-off analysis frameworks. Existing
reports provide the baseline; additional schema support should be need-driven.

### Phase 2 control-path decision — 2026-09-20

Follow [reusable campaign control decision](REUSABLE_CAMPAIGN_CONTROL_DECISION.md).
Reuse the existing offline native campaign owner and host evidence path; do not
create another executor. Remaining gaps are real-platform compile compatibility,
reviewed pattern preparation, board composition and end-to-end integration.

The existing simulator now accepts `pattern='matched'`, providing three approaches
in each direction to one identical target within 12 legs. The default is unchanged.
37 focused tests passed. Native preparation still uses the legacy pattern; no
controller support, installation or physical test is claimed for the new pattern.

### Native compatibility checkpoint — 2026-09-20

The real ESP32 compile/link probe now passes after fixing the HTTPMethod adapter
and preserving required platform compile flags. 50 focused native tests passed.
Host and native preparation generate identical legacy and matched target lists.
Preparation defaults remain unchanged; top-level matched-pattern selection and
full signed workflow integration are still pending. No installation or hardware
commands occurred. See the control decision document for scope and build caveats.

### Top-level pattern and signed admission — 2026-09-20

Trusted pattern selection now passes from `CharacterizationComposition` through
the controller into preparation. Legacy remains the default. No request-controlled
arbitrary target list or new network route was added; invalid selection is rejected
before capture/reservation.

Native/Python integration tests for both patterns verify the controller's signed
challenge response, decode and compare all targets with the host draft, sign host
admission and accept it through existing authenticated routes. The fake bus then
executes one leg and remains at the export barrier without a second write when
no receipt is supplied. This is simulated native integration, not physical motion.

30 focused composition/controller/preparation/host-session tests passed. Next:
extend this same test bridge through result transfer, verified disk export and
receipt acknowledgement for the full finite campaign. Do not claim complete
end-to-end multi-leg coverage from this first-leg barrier check.

### Full native/host campaign bridge — 2026-09-20

The prior first-leg-only test now covers both complete 12-leg patterns through
signed result transfer, real verified disk exports, independent assessment and
native receipt acceptance. An injected export failure at leg 4 produces no receipt
and no fifth fake-bus write. See [offline integration result](CAMPAIGN_OFFLINE_END_TO_END_RESULT.md)
for reproduction and limits. Real sockets, timing and full-board deployment are
not established by this fixture. No physical testing occurred.

### Real-socket failure validation — 2026-09-20

Existing HTTP adapter tested on localhost for a received POST followed by dropped,
truncated, altered or delayed acknowledgement. Every uncertain case latches the
client and permits no retry or follow-on request. A valid 350 ms reply passes within
a 2-second budget. Cumulative header/body delay respects the total deadline.
28 focused HTTP and composition tests passed; production transport unchanged.
See [HTTP failure results](CAMPAIGN_HTTP_FAILURE_TEST_RESULT.md).

Next: connect the existing native route bridge and socket adapter through one
finite host workflow, including receipt-ACK loss. Separate passing tests are not
yet proof of that combined integration or physical deployment readiness.

### Combined socket/native/export checkpoint — 2026-09-20

Completed the preceding integration: both 12-leg patterns pass through real local
TCP, production host authentication and transfer code, native routes/controller,
fake servo bus and verified exports. Three new integration tests pass.

Receipt-ACK loss is now reproduced: the host latches stopped while an accepted
receipt permits the next native leg (two fake writes, one exported result).
Do not describe host transport failure as stopping physical motion. No hardware
operations occurred. See [HTTP failure results](CAMPAIGN_HTTP_FAILURE_TEST_RESULT.md).

Next implementation slice: explicitly report uncertain continuation, prove the
controller cannot progress beyond that permitted leg without another receipt,
and specify/test read-only reconciliation before fresh admission. Never blindly
retry a receipt or use the last host acknowledgement as current physical pose.
Live wizard release remains deferred until these semantics are handled.

### Uncertain continuation reporting — 2026-09-20

HTTP sessions now expose JSON-safe uncertainty evidence: original request method,
path, sequence and body digest, with explicit no-retry / reconciliation-required
flags. Receipt uncertainty identifies possible continuation; it never claims a
controller stop. Keys, signatures and payloads are omitted. The first uncertain
operation survives subsequent locally rejected requests.

The combined native/socket test now advances the fake controller clock another
30 seconds after the lost receipt ACK and asserts the write count stays at two:
the accepted receipt permits one next leg, not unrestricted campaign progression.
This is fake-bus evidence, not a physical stop guarantee.

#### Read-only reconciliation contract (next implementation)

1. Preserve the failed session and its uncertainty report; never reset its sequence
   or replay its receipt. Preserve the exported leg and receipt digest.
2. Review an authenticated recovery-read mechanism with independent freshness
   protection. Opening a new ordinary session at sequence zero is not recovery.
3. Read boot/campaign identity, current leg/phase, accepted receipt identity and
   retained result identity. Acquire fresh measured joint positions separately;
   neither last target nor last host acknowledgement is a current pose.
4. If identities, freshness or retained evidence disagree, stay unresolved and
   issue no control writes. A controller restart invalidates the previous context.
5. Retrieve and verify any unexported result without sending continuation permission.
   Read-only reconciliation must not call prepare/start/receipt or alter torque.
6. Only a separately reviewed fresh admission may resume movement. Test accepted
   versus unaccepted receipt, stale/replayed reads, reboot, missing evidence and
   export failure before integrating a live wizard recovery button.

This slice adds reporting and a bounded-progression regression; it does not yet
implement a recovery endpoint, automatic recovery, firmware installation or motion.

### Offline reconciliation policy — 2026-09-20

Added `characterization_reconciliation.py`, a pure evidence assessor. It separates
receipt-not-accepted, receipt-accepted/next-leg-possible, final campaign completion
and unresolved contradictions. Every outcome retains `resume_allowed=False` and
`physical_pose_verified=False`. Completed counts mean accepted receipts, not
measured motion. Twelve synthetic policy tests cover identity changes, progression,
receipt digest mismatch, missing/wrong retained evidence and final completion.
26 tests passed including native socket campaigns and HTTP session regressions.

Authentication review: current request authentication consumes its sequence before
dispatch and permits only the next sequence. Ordinary sequence-zero reconnection
is not a recovery channel. Existing status is not a complete recovery snapshot.

Next: design and test a nonce-bound read-only recovery route that leaves ordinary
request sequence and campaign state untouched. It must publish boot/campaign,
accepted-receipt count and digest, phase and retained record identity. The current
offline policy assumes these inputs have already been authenticated and checked
for freshness; it does NOT supply that security boundary or make raw dictionaries
trustworthy. Review native evidence retention and atomic snapshot consistency
before wiring this policy into transport or wizard controls. No live recovery,
firmware deployment or hardware test was performed in this checkpoint.

### Native recovery evidence checkpoint — 2026-09-20

The native session now retains SHA-256 of the last accepted decoded 124-byte
receipt. Hashing happens before acceptance; failure cannot advance the campaign.
This is distinct from the HTTP uncertainty report's hash of hexadecimal wire text.
The owner-task snapshot reports boot/campaign, accepted receipt count, phase,
receipt digest and retained result leg/size/digest. Pending evidence remains
identifiable after export timeout; leftover accepted predecessor bytes are not
reported as the current leg. Snapshot access neither polls nor accesses the bus.

Native/localhost tests compare the retained digest with the actual host receipt,
verify result identity survives timeout, and feed the real native snapshot to the
offline reconciliation policy. The snapshot seam is NOT an HTTP route and has no
independent authentication yet. Next work remains nonce-bound authentication and
route integration, followed by negative freshness/replay tests. No installation
or physical movement occurred.

### Independent recovery authentication — 2026-09-20

Added an offline native `recovery-read` POST route, separate from normal command
sequence authentication. Request HMAC binds a fresh host nonce and expected boot
under a recovery-specific domain; response HMAC binds boot, nonce, status and exact
snapshot digest under a separate response domain. Host verification is one-shot.
Replayed read requests may produce another snapshot, but cannot advance campaign
state; an old response cannot satisfy a new nonce. This is not a motion endpoint.

The localhost/native lost-ACK test now reads and verifies the snapshot through
this route while the original command session remains stopped. Native assertions
check zero bus reads/writes during the handler. A host-only authenticator supplies
framing/verification; production deadline-bounded recovery transport, exports and
wizard integration are still pending. No live client or firmware deployment is
released by this test. Next: negative native request-auth cases, real-platform
compile validation and bounded recovery transport with durable snapshot export.

### Physical-test prerequisite checks completed — 2026-09-20

- Native recovery rejects malformed bodies, wrong keys, wrong boot context and
  tampered requests. An unavailable pre-preparation read does not initialize the
  campaign. A complete campaign still starts at ordinary sequence zero afterward.
- ESP32 compile/link probe passes with the new route. This is the no-op probe,
  NOT deployable arm firmware or proof of full-runtime memory usage; never flash it.
- `CharacterizationRecoveryHTTP` provides a single fixed read endpoint with a
  total connect/send/header/body deadline (default 3 s), bounded parsing,
  duplicate-header rejection, response authentication and expected boot/campaign
  checks. Each instance is consumed on success or failure. No command/session
  reset, retry, continuation receipt or movement API is exposed.
- Verified exports include readable snapshot JSON, lossless authenticated-body
  hex, and verification framing without the key. JSON is reformatted by the
  shared exporter, so exact-byte verification uses the hex attachment.
- 47 focused tests pass, including native localhost recovery after ACK loss,
  tampering, truncation, timeout, duplicate headers, identity mismatch and injected
  export failure. The command session remains stopped after recovery.

Next milestone is one bounded physical movement, not further framework expansion:
inspect the deployable firmware composition and existing single-step runner;
integrate only the needed recovery capability, verify startup is non-moving and
compile the actual candidate. Review its diff/hash/settings preservation before
installation. Then obtain fresh pose/clearance evidence and perform one bounded
outbound move with endpoint export; return only after verified arrival. Do not use
the 12-leg campaign as the first physical smoke test. This checkpoint performed
no device connection, firmware installation or physical movement.

### Actual application audit — 2026-09-20

See [physical smoke candidate review](FIRST_PHYSICAL_SMOKE_CANDIDATE_REVIEW.md).
The actual staged r31 application compiled successfully with verified evidence,
but it does not contain the campaign/recovery implementation and its single-step
contract requires a historical exact pose envelope. Do not confuse the new
compile-only probe with a deployable image or force the arm into that old pose.
Next: a signed one-leg smoke pattern in the existing campaign path, followed by
opt-in board composition and actual candidate compilation. No live test occurred.

### One-leg smoke mode — 2026-09-20

Added trusted `Smoke` selection to the existing campaign preparation/composition
path and matching `smoke` host draft. Its signed manifest contains exactly one
-8/+8 paired goal step, not twelve legs with a host-side early exit. Legacy and
matched defaults remain unchanged. Native preparation checks fresh stable capture,
reviewed bounds, maximum 32-count measured-to-target travel, and at least two
counts in the intended direction for both selected servos. No automatic return.

Offline native/socket tests cover one write, verified export, normal completion
and lost final receipt ACK: after another 30 seconds of simulated polling, writes
remain one and recovery reports COMPLETE. Reconciliation now takes the reviewed
manifest length (default remains twelve), allowing one-leg completion without
granting resumption. Native negative tests reject wrong-direction and excessive
travel smoke baselines. This is not installed firmware or a physical result.

Next: wire this smoke-only selection into the opt-in deployable board composition
and compile that application. Do not install the previous twelve-leg probe.

### Actual smoke application compiled — 2026-09-20

Staged r33 from the verified r31 baseline with the existing campaign dependency
tree and a smoke-only board composition. Existing diagnostic boot source is
unchanged; the adapter loads the existing key read-only, allocates off-stack with
heap checks, and registers routes without servo acquisition or commands. The
campaign replaces the old shoulder owner under an exclusive compile-time selector.

Source review caught and corrected registration ordering: hold diagnostics must
establish the shared boot ID before smoke authentication is constructed. The
first r33 compile (`900b207d...5976fe5`) is superseded and must not be installed.
The initial staging export predates this correction; use the final compile source
hashes, not that initial staging receipt, for candidate identity.

Corrected actual application compiled with default 4 MB/no-PSRAM profile:
`runs/wizard-exports/wizard-20260920T142852905258Z-681d77e3d508428ea251f2e14b071d31`.
App SHA-256:
`170188fe380cc7a21ee5502e831f21c3050b34768bdbbbbc1ddf7f7e608b330d`.
41 native/socket/preparation/service tests and two source integration guards pass.

This is a built candidate, not an installed or physically released image. Bounds
in this composition are encoder-domain limits (0–4095), not reviewed clearance
bounds. Before deployment/motion, review startup/runtime allocations, installation
compatibility and the current operating envelope; bind the physical test to fresh
feedback and the exact candidate. Settings/filesystem/credentials were not changed.

### Approved r33 installation and startup completed — 2026-09-20

Executed the user's explicit one-installation/one-startup authorization. The
installer verified controller MAC, USB identity, r31 predecessor, partition table
and expected filesystem before writing only app0. Full app readback matched r33
SHA-256 `170188fe380cc7a21ee5502e831f21c3050b34768bdbbbbc1ddf7f7e608b330d`.
Before/after protected-region digests matched. One startup reset was sent; no
retry, provisioning, hold, torque or motion command was sent.

Verified installation export:
`runs/wizard-exports/wizard-20260920T143711621244Z-871ba338119d4d61a0af5e6dc026daef`.
Read-only startup export:
`runs/wizard-exports/wizard-20260920T143712033495Z-a846470cabf7446f8f77cf1652a2d593`.
Boot `2f5df180dff259e1f05264e2c0674032` returned identical initial/final IDLE status,
NOT_CONFIGURED, zero records and no storage fault. Generic capabilities reported
151,892 bytes free internal heap and a 90,100-byte largest internal block. These
are startup observations, not proof of runtime sufficiency or physical accuracy.

Next: authenticated campaign-interface verification and fresh read-only pose
capture before review of the single movement. This startup check did not acquire
joint positions, prepare a campaign or authorize movement. The user's installation
and startup approval is consumed; it is not permission for a subsequent movement.

### First live authenticated status attempt — 2026-09-20

The preparation-only host workflow attempted GET campaign status at sequence zero
on boot `2f5df180dff259e1f05264e2c0674032`. Response validation raised ValueError;
the host stopped before POST prepare, so no joint capture or movement occurred.
Export: `wizard-20260920T144045919249Z-2bc12968f6604af3b842e32b9b4e86f4`.
The first runner retained the exception type but not its message or rejected raw
response, so the exact live rejection is not conclusively identified. Logging now
retains the error message for future attempts.

Source investigation found a concrete compatibility bug: route and authentication
wrapper both emit Cache-Control: no-store; the pinned ESP32 WebServer appends both,
whereas native test maps collapse them. The strict host rejected all duplicate
headers. Added a narrowly scoped host exception for identical no-store duplicates;
framing and authentication duplicates remain rejected. A real localhost regression
reproduces that response shape. 24 transport/session tests pass. No firmware change
or second device request was made for this fix.

Current command sequence may have been consumed; do not reconnect at zero or retry
prepare. A newly approved startup would establish a new boot/session for the
corrected read-only check. This is a transport finding, not evidence of servo failure.

### Approved restart and live read-only preparation passed — 2026-09-20

One startup was performed under explicit approval. An initial host precheck used
an older status schema and stopped before reset; corrected r33 status handling then
verified the prior boot and sent exactly one reset. New boot:
`2369c2a988af7459b0da33b177310c4b`.
Startup export: `wizard-20260920T144412907803Z-ecd4adda7e28455fa95e6b9f8903fd30`.

Authenticated GET status succeeded, then POST prepare scheduled read-only capture.
Observed transitions: NEW -> CAPTURING -> AWAITING_AUTHORIZATION; writes_attempted
remained zero. The signed challenge contained one paired target [2397,1717],
campaign identity and capture-reference digest. No start, receipt, hold, torque or
movement command was sent. Observation export:
`wizard-20260920T144425480787Z-c84087e5f859480399ea617f3831892a`.

Preparation success attests that controller checks passed over its three captured
poses; it does not export their raw positions. The targets are not measured joint
positions or Cartesian endpoints. The authorization window is 30 seconds and is
not renewed by this report. Do not reuse this old challenge for later movement.
Next physical execution must bind fresh admission and reviewed clearance; the host
workflow must preserve the reference evidence and actual endpoint observations.

### Raw reference evidence implemented offline — 2026-09-20

Added authenticated GET `/rocell/characterization/reference` to the source campaign
routes. It returns the existing 468-byte canonical preparation reference as hex;
it performs no new acquisition or lifecycle advancement. Host decoding verifies
the exact digest from the authenticated challenge, three timestamps and all seven
joints' measured positions, goals, torque flags and raw feedback, including timing,
stationarity and stability checks. Readable and lossless exports use the existing
diagnostic exporter. These stored samples are not a later live pose reading.

Native/socket campaigns now retrieve and verify this reference before admission;
negative tests cover corruption, invalid length, raw-position inconsistency,
movement flags, torque, instability and timing. No device was accessed this turn.
Installed r33 and its staged/hash-pinned image are unchanged and do NOT expose
this new route. Next: compile/stage a reviewed successor before any deployment;
do not request the unsupported route on r33 or reuse its expired challenge.

### r34 reference-export successor built and reviewed — 2026-09-20

Staged r34 from hash-verified r33, changing only characterization_prepare.h,
characterization_controller.h and characterization_prepare_routes.h. Startup,
settings/key access, movement policy and smoke-only selection are unchanged.
51 focused tests passed, including source diff guards, reference validation,
native/socket campaigns and unauthenticated/unavailable reference-route rejection.

Actual application compile export:
`wizard-20260920T145034031062Z-67bab9148ca244659164801ea1557449`.
Offline candidate review export:
`wizard-20260920T145114719151Z-3b726b92be3b4c3b81ee8f29bebb8751`.
App SHA-256:
`6637e0e6f06b731db23621d8a727cdc0f9b82a2473813eec9a3b8a98fbd09945`.
Application is 1,155,184 bytes with 155,536 bytes app-slot headroom; pinned
partition/bootloader profiles and rollback artifacts pass review. Largest inspected
individual frame remains 1,072 bytes, not a complete stack/resource proof.

r34 is not installed or yet added to the installation/startup allowlists. Next:
bind those existing paths to the exact r34 hash with r33 predecessor, extend the
read-only host check to export the reference before any movement admission, and
run local preflight. Deployment requires separate approval. No device requests,
restart, flash or movement occurred during this successor build/review.

### r33 offline installation compatibility — 2026-09-20

Extended the existing candidate reviewer (not the installer) for exact r33 identity,
smoke selection, boot-ID initialization order, compiled recovery routes and absence
of competing legacy shoulder start/local-step authorization routes. Review passed:
app 1,154,048 bytes in a 1,310,720-byte slot (156,672 bytes headroom); expected
partition/bootloader hashes; saved original backup pair, recovery slot and retained
rollback artifact match. Largest inspected individual frame is 1,072 bytes; this
does not prove total stack or runtime heap sufficiency.

Verified review export:
`runs/wizard-exports/wizard-20260920T143032812516Z-db0af315b7104c6ab6b857ea94ab53e5`.
No private contents were exported, and no device was accessed.

Remaining deployment work is explicit: add exact r33/predecessor binding to the
existing app-only installer and installation/startup evidence verifier, preserving
prewrite device-hash checks and protected-region checks. Do not bypass the current
revision allowlist or pass r33 as r31. Then review a non-moving startup and fresh
capture before admitting the one-leg smoke command. The candidate review remains
`deployable=false`; encoder range alone does not certify physical clearance.

### r33 installer and retained startup binding — 2026-09-20

The existing app-only installer now recognizes exactly r33 hash
`170188fe380cc7a21ee5502e831f21c3050b34768bdbbbbc1ddf7f7e608b330d`,
1,154,048 bytes, predecessor r31, and its own one-use journal. The exact candidate
review is pinned. Filesystem preservation follows the existing observed-pose
image checks, not factory defaults. Device MAC/USB identity, installed predecessor,
partition and filesystem checks, protected-region checks and app readback remain.
No r32 fallback or automatic retry was added.

Installation evidence and read-only startup observation/binding now accept r33.
These retained generic idle/pair observations do not prove smoke-route readiness,
fresh servo pose, runtime heap headroom or physical clearance. Verify the campaign
interface independently after an approved installation/startup.

Local-only preflight passed (`--revision 33 --preflight-only`): no port opened,
no journal reserved, no startup or flash. 160 installer/evidence/startup/integration
regression tests passed. No current-device identity is inferred from that result.

Next hardware action, when explicitly approved for this candidate: one app-only
installation and one non-moving startup, preserving settings/credentials, followed
by read-only startup/interface checks. Fresh pose and physical envelope review
remain necessary before the separately admitted single smoke movement.

### r34 installer and measured-reference export integration — 2026-09-20

Completed offline integration of r34 app hash
`6637e0e6f06b731db23621d8a727cdc0f9b82a2473813eec9a3b8a98fbd09945`
(1,155,184 bytes), requiring installed predecessor r33 and preserving the existing
filesystem/settings/credentials. The installer pins the reviewed candidate and
uses a separate one-use journal; installation evidence and startup binding accept
r34. No hardware connection, restart, installation or movement occurred here.

`scripts/observe_r33_campaign.py --revision 34 --startup-export <export-id>` now
retrieves the authenticated reference after preparation/challenge acquisition.
It verifies the exact reference hash and exports all three measured-position
snapshots, their target registers, timing and raw feedback bytes. The observation
report links that export to its boot and challenge/campaign. Invalid reference
or failed export cannot be reported as successful preparation. This script never
sends start, receipt, hold, torque or movement commands. Revision 33 remains
supported without claiming measured-reference export.

Validation: local `--revision 34 --preflight-only` passed with hardware_access=false
and journal_reserved=false. 184 installer, evidence, startup, reference, native
socket-campaign and route tests passed. These are offline results, not evidence
that r34 is installed or that physical endpoint accuracy is established.

Next: obtain approval for one r34 app-only installation and one startup,
preserving settings/credentials, followed by read-only capture/reference export.
Review measured pose and clearance before any separately authorized bounded
movement. Stored reference samples are historical, not continuously fresh pose;
expired challenges cannot authorize later movement. Camera/contact remain deferred.

### r34 approved live installation and reference capture — 2026-09-20

Completed the explicitly approved single app-only installation and single startup.
Full application readback matched r34 SHA-256; protected-region digests remained
unchanged, preserving settings and credentials. No movement/hold/torque command,
retry or additional startup was sent.

- Installation evidence: `wizard-20260920T150520282112Z-723298376ba3437fb7b5c192f18fe43f`.
- Startup: `wizard-20260920T150520748821Z-717da09958df485f86e44f123714c1f0`;
  IDLE, zero records, no storage fault; boot `d65494738c89ba849fdd6219f2b07c5c`.
- Authenticated capture: `wizard-20260920T150527505376Z-d0b557ea3c0f478eb15e3ec227236a16`;
  READ_ONLY_CAPTURE_PREPARED, zero target commands, reference export verified.
- Raw and decoded reference: `wizard-20260920T150527447276Z-a91429abee10435e8d9b689d4be008c2`;
  SHA-256 `71d6b26582c01e3761ac14c6c806668575ad4e46df7a01bd76d728aa14a3fad3`.

All three acquired snapshots reported identical positions for IDs 11–17:
2047, 2414, 1702, 2904, 1591, 2041, 2047. Goal registers respectively:
2047, 2405, 1709, 2907, 1589, 2040, 2047. Position-minus-goal residuals:
0, +9, -7, -3, +2, +1, 0 counts. These are stationary encoder observations,
not proof of movement, physical tip accuracy, or a compensation calibration.

Next is offline review of the bounded motion runner against this actual baseline,
then a separately authorized finite movement with fresh admission, correlated
before/after feedback and export. Do not reuse this expiring preparation challenge
or assume encoder range alone establishes board clearance. This approval is consumed.

### Baseline-aware single-leg review — 2026-09-20

Added the offline `characterization_smoke_review` checker. It rejects multi-leg
or altered targets and measured-to-target travel outside the reviewed directional
2–32 count envelope. It grants no motion authority and does not claim clearance.
11 smoke-review and native socket-campaign tests passed, including end-to-end
export/receipt tests and lost-acknowledgement scenarios.

Important distinction for the actual r34 baseline: target registers change
2405/1709 -> 2397/1717 (-8/+8), but measured positions are 2414/1702.
Therefore target-minus-measured is -17/+15 counts, not -8/+8. Neither quantity
predicts achieved travel exactly; subsequent acquired positions must establish it.
This is why pre/post measured feedback must be retained alongside target registers.

Remaining before live testing: integrate this checker into a production bounded
runner (current end-to-end orchestration is test-only), with finite polling,
fault evidence export, no retry/automatic return, and fresh authenticated admission.
Review the physical path separately; encoder range is not obstacle clearance.
No hardware was accessed during this offline review.

### Single-leg runner integration — 2026-09-20

Implemented `characterization_smoke_runner.SmokeRunner` with injected authenticated
transport. It requires explicit admission, an unused campaign, a freshly captured
reference and the baseline-aware single-leg check. It exports the reference before
start, downloads bounded result chunks, independently assesses/exports the result
before receipt, and observes completion. Polling is finite. Fault evidence is
exported when the controller reports FAULT. Any exception stops further requests;
the runner is one-use with no retry, return or follow-on movement. Host stoppage
is deliberately not labeled controller stoppage.

Seven runner/review tests passed, including the native-controller loopback happy
path and lost final receipt acknowledgement: exactly one fake-bus movement, no
successor and no second execution. No physical hardware accessed.

Remaining release work: live CLI/wizard wiring with durable cross-process run
reservation and installed/startup identity binding, plus explicit physical motion
admission. The reusable runner alone does not establish physical clearance or
authorize live use. Existing r34 reference/challenge cannot be reused as fresh.

### Live entry-point wiring, offline validated — 2026-09-20

Added `scripts/run_r34_smoke.py`: retained r34 installation/startup verification,
local-only preflight, explicit one-movement/clearance admission, reviewed in-memory
key loading, and an exclusive, flushed/fsynced per-boot reservation shared with
the read-only capture script. It never resets, retries, returns or deletes claims.
Live authenticated status must be NEW before preparation; controller authentication
binds requests to the startup boot. Non-COMPLETE runs exit unsuccessfully and export
the runner report. Key-loading logic is shared with the read-only script.

Nine CLI/runner/review tests passed. Actual retained-startup preflight correctly
rejected boot `d65494738c89ba849fdd6219f2b07c5c` as already reserved by the completed
read-only capture. This check accessed local files only; no device access occurred.

Next hardware scope requires a separately approved single startup of existing r34,
read-only startup binding, then fresh preparation and one bounded shoulder-pair
smoke movement with verified result export. No firmware installation is needed.
Startup must use the reviewed restart path adapted/validated for r34; do not
reuse r33-only restart binding or silently broaden its accepted revisions.
No automatic return, follow-on movement or retry is included.

### First r34 live single-leg runner result — 2026-09-20

User approved proceeding with one startup, fresh checks and the single bounded
movement. Added explicit r34 restart binding without changing firmware. 112
startup-binding/CLI/runner regression tests passed before hardware access.
One startup verified boot `3a72fd72536cadf86400a2bed7323ca6`; startup export
`wizard-20260920T152843882696Z-822dc701d77b4d59b1f8385745929d23`.

The one-leg runner completed authenticated preparation, start, feedback acquisition,
independent assessment, verified result export, final receipt and COMPLETE status.
Run: `wizard-20260920T152856753981Z-cd28202562ac448fabe01b74f13c33df`.
Result: `wizard-20260920T152856234358Z-015ca31209b64e6cb052f6c53cb57326`.

Shoulder pair: measured baseline 2414/1702, target registers 2405/1709 ->
2397/1717, measured endpoint 2407/1710. Actual measured movement -7/+8 counts;
absolute endpoint residual +10/-7 counts. Other acquired joint positions unchanged.
Assessment SETTLED_MISS means successfully retained movement evidence, NOT target
accuracy success. Protocol COMPLETE must not be presented as an exact endpoint hit.
No retry, return, follow-on motion, firmware installation or settings change occurred.

Next: compare this result with the prior +9/-7 stationary residual, then plan a
separately admitted repeatability/direction trial. One movement is insufficient
to fit compensation; physical tip accuracy remains unverified. Current one-use
campaign and approval are consumed; do not replay start or final receipt.
