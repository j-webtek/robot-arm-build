# Automated positional testing — implementation plan

## Current priority — finish the two-endpoint wizard workflow

Latest physical testing: see `LIVE_WRIST_CAMPAIGN_FINDINGS_20260914.md`. A real
wrist command and raw telemetry export have been exercised through the wizard.
The full two-leg campaign remains held by post-capture byte capacity, not by a
stop-device requirement. Fix capture sizing next; do not fit compensation from
incomplete endpoint windows. Metadata-constructor and pinned-directory retention
defects found during live testing were corrected. The registered suite now has
77 files, including those real-Windows/no-device regression checks.

### Wizard integration update — 2026-09-14

The physical-mode wizard now includes **Run two attended wrist endpoints**
(`run_positional_campaign`). It stays disabled until trusted host setup attaches
the reviewed originals, selected USB identity, six starting joint angles and two
explicit wrist targets. The action is not a browser command/upload endpoint.

Implemented flow:

1. `ArrivalWizardService.configure_positional_campaign(...)` stages an immutable
   runtime and the original records without USB access, a live signature or motion.
   It prepares the assigned export directory before execution can become available.
2. The arm action card and confirmation preview enumerate both targets, including
   any planned second movement back toward the start. They show the speed and
   acceleration settings and explain that cancellation is not a physical stop.
3. Accepting Start consumes the wizard attempt and establishes the original
   30-second deadline. The coordinator signs a fresh v2 intent, verifies retained
   references and current USB metadata, and reserves one native campaign launch.
4. The existing process owner executes the two-leg campaign. Each command still
   requires its fresh six-joint baseline; leg two is submitted only after leg one's
   endpoint passes. Failed endpoint, cancellation or timeout does not cause retry.
5. The parent reconstructs the actual trial records. Wizard success requires
   `ENDPOINTS_REPORTED_COMPLETE`, not merely a successful process exit or export.
6. The coordinator copies the finite report manifest and wrapped original bytes to
   `<assigned export directory>/<campaign-id>/`, then verifies that copied bundle.
   The wizard operation summary also appears in ordinary **Export logs** output.
   Reloading or reusing a Start ticket cannot launch the campaign again.

Implementation: `application/wizard_positional_campaign_coordinator.py`, the
existing arrival service/action catalog, and `ui/static/app.js`. Host setup usage
and remaining hardware validation are documented in
`ATTENDED_CAMPAIGN_WIZARD_PLAYBOOK.md`.

Tests cover real staging and wizard preview/Start/result/export with an incapable
executor. Separate joined coordinator tests use real signing, reference/metadata
bootstrap, launch claims, telemetry collection, endpoint reconstruction and
portable copying, with fake metadata/serial and a substituted process owner.
Those joined cases exercise successful completion, first-leg miss and cancellation.
No real hardware commands have been sent by these tests. Native Win32 process
containment plus physical arm behavior still needs an attended live demonstration.

Final regression for this integration: **555 tests passed in 55.97 seconds**,
including campaign modules, the owned supervisor, wizard actions and arrival
service. JavaScript syntax check (`node --check software/src/rocell/ui/static/app.js`)
also passed. Report: `software/runs/wizard-attended-campaign-regression-20260914.xml`.

### User-approved attended risk policy (supersedes blanket stop gate below)

A separate emergency-stop device or measured emergency-stop qualification is
not a prerequisite for the initial bounded, attended two-endpoint test. The
user confirmed USB and AC power and requested a proportionate risk policy.
Power/connection alone is not evidence of interruptible motion or safe clearance.

New v2 attended intents replace `stop_qualification_sha256` with a retained
`bounded_motion_risk_sha256` record. Review acknowledges that an accepted servo
goal may finish after software cancellation; the entire movement must therefore
be clear and acceptable, with the operator present, no contact and no added
payload. Existing fixed limits remain: two wrist-only commands, at most five
degrees per leg, wrist targets within +/-10 degrees, spd 20/acc 1, bounded
feedback/settling checks, no retry/automatic recovery and no later command after
a fault. Stop qualification is not fabricated or marked passed. Old v1 records
retain their original meaning and are not silently migrated.

This exception does not authorize unattended operation, broad joint/speed sweeps,
contact or automatic power/torque interruption. Section 10 remains unchanged.
Physical stop research/measurement is deferred for this attended milestone.

Correction to prior diagnosis: the supervisor's generic
PHYSICAL_PROVIDER_QUALIFICATION_HELD was reached because the native campaign
launch branch was unimplemented, not because it evaluated and rejected an
emergency-stop record. The attended-v2 branch is now implemented. Historical v1
intents are rejected from this native route with
CAMPAIGN_BOUNDED_ATTENDED_V2_REQUIRED; they are not silently upgraded.
No physical movement was performed in this change.

Native dispatch update (2026-09-14): the supervisor validates the fixed runtime,
rechecks the reserved authenticated campaign before execution, and launches the
isolated `execute-campaign` entry. The child verifies its actual invocation and
review before consuming the one-use claim and opening the serial connection.
Its compact receipt is checked against the exact intent; original trial bytes
must still be reconstructed by the parent before endpoint completion is accepted.
Preparation uses the existing 30-second intent lifetime, rather than demanding a
new 30 seconds at launch. At least 24 seconds must remain for the bounded work;
the execution deadline preserves the two-second cleanup allowance and never
extends the intent deadline.

Software evidence: 72 dispatch regression tests passed; 28 targeted positive
routing/child/prelaunch/package tests passed. The positive supervisor routing
test deliberately replaces prelaunch authentication and the process backend with
incapable test doubles. Separate tests exercise authenticated prelaunch and the
real collector against a fake serial kernel, including completion, miss and
cancellation. This is not an end-to-end physical or fully isolated native success.
Reports: `software/runs/attended-campaign-dispatch-regression-20260914.xml` and
`software/runs/attended-campaign-positive-routing-20260914.xml`.
Final combined regression: all 442 campaign and owned-supervisor tests passed in
41.34 seconds. Report:
`software/runs/attended-campaign-full-regression-20260914.xml`.

Parent operation integration: `application/positional_campaign_process_owner.py`
now joins runtime validation, one-use parent admission, the actual owned
supervisor, original retention and portable verification. It returns an explicit
operation status, supervisor error, report reference and verified endpoint
diagnostics. There is no caller-selected authorizer/backend. Repeated calls and
storage-failure retries cannot rearm the parent attempt. The native supervisor
route now accepts the scoped v2 policy, subject to original-reference and review
checks. The bounded wizard action now prepares fresh reviewed v2 inputs and calls
this parent operation after trusted-host staging. Software integration evidence
is described above; a complete attended hardware demonstration remains outstanding.
The registered owned-pipeline test roster now contains 75 files.

Diagnostic export integration: portable native export verification now returns
`endpoint_diagnostics` derived only after reconstruction succeeds. Each planned
leg includes its command/target, captured start/final angles, signed error,
approach direction, sample count, endpoint verdict and quiet-entry time bounds
relative to write completion. Skipped legs remain NOT_EXECUTED with null measured
values. Partial captures receive no fabricated verified endpoint summary. The
existing immutable export schema is unchanged; configuration references accompany
the returned projection for later comparisons. Tests cover complete, missed and
cancelled records using copied exports without source-workspace/device access.

Integration repair: campaign supervisor receipts now retain the exact request
hash even when admission rejects execution before child creation. Parent result
retention can operate from the immutable intent and actual supervisor receipt,
without requiring a live authenticated device reader after failure. The existing
reader-based API delegates to this same implementation. The actual supervisor
rejection -> retained originals -> portable verification path is exercised in
`test_positional_campaign_process_codec.py`. Failed-attempt originals remain
available even when no child is created; retention does not imply motion success.

User-approved priority: deliver one bounded, usable workflow from wizard preview
through two commanded endpoints, automatic verification and an independently
verifiable export. Do not add broader motion features or new generic validation
layers unless an actual integration failure makes them necessary. The full plan
remains in scope; optimization, additional joints and unattended release follow
this milestone, not precede it.

Acceptance criteria:

1. Preview enumerates exactly two targets and the applicable limits.
2. One Start action creates one operation; repeated submissions do not replay it.
3. Both measured/reported endpoints are individually classified against targets.
4. A first-leg failure withholds leg two and retains the failed result.
5. Export preserves target, command, baseline, feedback, verdict and journal;
   verification succeeds from exported originals without a device connection.
6. Prove the complete path with simulated hardware, then demonstrate the same
   bounded attended workflow on hardware after existing release checks pass.

Current distinction: the wizard rehearsal path exists; the native child entry
still rejects execution. Native runner components passing unit tests do not
complete criterion 6. Required physical evidence must not be fabricated or
bypassed, but unrelated qualification work must not expand this milestone.

Next integration sequence: exercise this exact two-leg wizard acceptance path;
connect the native supervisor/child/result publication path; expose its bounded
wizard action with concrete readiness/hold reasons; run the attended demonstration
when its required evidence is available. No additional general-purpose features.

Focused acceptance evidence: `software/runs/two-endpoint-wizard-acceptance-20260914.xml`
records 19 passing wizard tests, including new exact-two-leg success and first-leg
failure scenarios through service preview/start/status/export with the real
rehearsal worker. Both scenarios verify exported reports and journals; repeated
Start before/after completion and reload returns the original operation without
rerun. This is service/rehearsal evidence, not browser interaction or the native
two-leg arm demonstration. Next work is native integration, not more rehearsal
features or additional general validation layers.

### Complete registered boundary-suite integration run — 2026-09-14

Executed `wizard_worker.run(..., 'positional_campaign_boundary_tests', ...)`
against the current source without editing files during execution. All **729
tests across the registered 56 files passed in 114.16 seconds**; total worker
elapsed time was 114.422 seconds, below the existing 180-second diagnostic limit.
Retained actual output and exact test roster in
`software/runs/campaign-registered-suite-integration-20260914.json`.
The worker reported zero motion commands. This invoked the registered worker
function directly, not a browser or the outer subprocess timeout supervisor.
It is integration evidence for the selected simulated/native-fixture boundary
tests, not proof of native campaign execution or independent tool-tip accuracy.

Next native integration constraint: the existing endpoint/absolute Win32 facade
and connection deliberately enforce one write per connection. Do not reset
their one-use flags to create a campaign. The campaign needs its own exact
per-leg native dispatch boundary, preserving one connection, pending-IO ownership,
fresh-baseline checks, predecessor verification and irreversible holds on error.

### Endpoint verification layers clarified — 2026-09-14

Reviewed the retained report for `operation-a5ba0d2e1a3a4283ba422d08b5ca9d5b`:
the parent `claim_receipt_verified` and `endpoint_reported_settled` are both true.
Lower-level `owned_process_verified` flags intentionally remain false because
those functions reconstruct telemetry without access to the parent's process
receipt. They are not evidence that the parent verification failed.

New reports expose `verification_layers`: worker claim, owned-process completion,
reported serial cleanup, and reported joint destination. Independent tool
position, device-sample freshness, and physical stopping remain explicitly
unverified. Original reports are immutable and are not rewritten. A target miss
or uncertain process completion must not become a verified destination merely
because the report was saved successfully. These fields grant no motion authority.

Verification: 46 targeted coordinator, native-result and wizard tests passed
(`software/runs/absolute-wrist-verification-layers-20260914.xml`). Includes rejected
output, mismatched process identity, incomplete cleanup and missed destinations;
these tests used synthetic devices and sent no physical commands.

#### Practical progression toward destinations in space

1. **One joint, one destination:** preserve the requested target, fresh starting
   feedback, actual transmitted command, reported settled endpoint, signed error,
   settling duration, all other joints, and exact raw capture for each attempt.
   The latest +4-degree test is a completed example, not a new test to repeat
   automatically.
2. **Matched correction experiment:** from a newly checked +3.779-degree starting
   wrist pose, evaluate the existing one-shot zero-from-above candidate with
   nominal target 0 degrees and motor target -0.966796875 degrees. Retain nominal
   and motor errors separately. Use the reviewed correction workflow, not an
   ad-hoc command or reuse of the consumed session. The candidate remains untested
   on hardware; do not apply it as a global calibration.
3. **Repeatability before speed:** compare nominal-target errors for repeated
   approaches from both directions at the same speed and load. Change only one
   experimental variable at a time. A repeatable bias is not proof of backlash
   or a reason to relax endpoint tolerances.
4. **Joint-space to spatial evidence:** once the board/camera/tool are mounted,
   establish camera calibration, board frame, arm-to-board transform and measured
   tool-tip offset. Compare predicted tool positions against independent observed
   positions. Controller XYZ is not an independent physical measurement. A planar
   camera mapping alone cannot validate an elevated tip's Z coordinate.
5. **Noncontact spatial targets first:** verify reachable hover points and their
   observed residuals before keyboard or screen contact. Choose acceptance bounds
   from measured calibration uncertainty and target size, not from an invented
   millimetre-accuracy claim. Contact tests additionally require a qualified tip,
   approach height and travel/force limits.

### Attended live absolute destination test resumed — 2026-09-14

Using Jack's standing attended/secured/clear/powered report, started a fresh
physical wizard and correlated the expected COM7 unit (CP210x serial
`52E4E1E8337FEF119E92181CEDD322A4`). No automatic startup, homing or settings
commands were sent. Command-free stream capture
`operation-1ed8603c943343d9be50daf92434c411` retained 255 poses, zero written bytes,
and confirmed serial cleanup/process exit. It supplied the six-joint baseline
for a bounded absolute wrist draft.

Live movement `operation-a5ba0d2e1a3a4283ba422d08b5ca9d5b`:

- Start: +0.966796894 degrees; absolute target: +4 degrees, spd 20 / acc 1.
- Final reported wrist: +3.779296882 degrees; target error -0.220703118 degrees.
- 281 post samples; 220 final constant reports spanning 3.922 seconds.
- Endpoint `REPORTED_SETTLED` at the existing +/-0.5-degree tolerance;
  movement detected, no reported other-joint change or wrist excursion.
- Reconstructed transport clean, no capture issues, cleanup reported closed;
  supervisor exited successfully with no cleanup errors. The lower-level
  summary's owned-process-verification flags remain false; do not relabel them
  or infer independent physical accuracy/device freshness.
- No return or correction retry. One-profile-per-session hold remains active.

Verified wizard export:
`software/runs/wizard-exports/wizard-20260914T191819556426Z-614d8a1f2e984f9bb6512b0ad5a75d70`.
Trial SHA-256: `52bd46cee250f3fc0f064536ea9e13a80137df8156a0cf5185f359c22a912776`.

Next controlled destination experiment: evaluate the separately reviewed
zero-from-above correction from this matching +3.779-degree baseline, through
a new one-use reviewed attempt, not a bypass of this session's consumed profile.
Keep nominal target and motor target separate. Spatial tool-tip accuracy later
requires camera/board registration, the arm-to-board transform and measured tool
offset; encoder endpoint success alone does not establish millimetre accuracy.

### Integrated movement/telemetry regression clean — 2026-09-14

Reran the full `wrist or first_motion or endpoint or positional or telemetry`
unit-test selection after the source-cap and fixture repairs, without editing
sources during execution. **2104 passed, 16035 deselected, zero failures/errors
in 352.48 seconds**, retained in
`software/runs/movement-telemetry-integrated-recheck-20260914.xml`.
Eleven warnings concern pytest `record_property` with xunit2 report formatting;
they are not device or movement failures. The prior failed broad report remains
retained as evidence of the defects and subsequent repair.

This combined result covers the selected movement, endpoint, telemetry,
positional, wizard and isolated-worker tests. It is not the entire repository
suite, a physical calibration result, or release of native campaigns. No
connected hardware was commanded by this software regression run.

### Broad movement regression found and repaired two integration issues — 2026-09-14

Ran the wider `wrist or first_motion or endpoint or positional or telemetry`
unit-test selection after the framing fix. Initial report
`movement-telemetry-framing-regression-20260914.xml`: **2087 passed, nine failed,
eight setup errors in 346.68 seconds**. Do not describe this report as passing.

The eight setup errors came from trajectory implementation binding: the current
637 Python modules exceeded its old 512-file cap (13,067,147 source bytes at
inspection). Raised only that finite file cap to 1024, preserving the 20 MB
aggregate cap and per-file bounds and continuing to hash every module. Added
tests for successful current-tree binding and rejection under forced file/byte
overflow. No motion, capture or serial limits were enlarged.

The nine initial failures were stale operator-validation fixtures omitting new
required measurement/selection fields. Updated fixtures with synthetic values
and real closed method choices; dynamic empty selectors remain fixture-only.
Malformed operator IDs remain rejected. Measurement-specific error codes are
accepted where that codec rejects first. Production input rules were unchanged.

The affected files plus trajectory tests now pass: **173 passed in 31.36 seconds**,
`movement-broad-failures-fixed-20260914.xml`. Intermediate failed rechecks are
retained. This is a focused successful rerun after the broad failure, not a claim
that the full broad selection has been rerun successfully. No hardware I/O.

### Fragmented campaign stream: delimiter-boundary defect fixed — 2026-09-14

Added continuous-stream campaign tests with 23-, 37- and 61-byte reads; pending
packet bytes persist across baseline/post and leg boundaries without purging.
The first run found a genuine failure for 37-byte reads: the post window began
with the previous packet's lone LF, which was classified as an invalid joint
record even though the following 164 complete poses were valid.

`arm/telemetry_coverage.py` now accounts for exactly one leading LF or CRLF as
an unobserved attachment delimiter. Original bytes/hash/range and acquisition
times remain retained; no pose is reconstructed from the delimiter. Whitespace
records, repeated blank records and interior malformed records remain failures.

`campaign-fragmented-stream-20260914.xml` retains the initial failing test.
After the fix, `campaign-fragmented-stream-fixed-20260914.xml` records **235
passed, 17901 deselected in 11.88 seconds**. Successful fragmented campaigns
independently reconstruct both endpoints; interior corruption on either leg
prevents all later commands and retains the corrupt raw record with one cleanup.
This is a shared parser change requiring freshly staged source-bound runtimes;
historical reports are not overwritten or automatically promoted. No hardware I/O.

### Checklist reconciliation and campaign-specific capture tests — 2026-09-14

Inspected contract, sequence, journal, collector and wizard tests. Marked only
the immutable software-contract item complete and separated proven rehearsal
UI work from unfinished native dispatch/cancel integration. The reconciled
subset passed 115 tests in 2.86 seconds (`campaign-checklist-evidence-20260914.xml`).

Added direct campaign collector tests for its 16 KiB baseline and 48 KiB post
limits, plus late-read rejection in both phases. All four passed in 0.66 seconds
(`campaign-capture-bounds-20260914.xml`); each verifies retained original bytes
and rejection by the campaign validator. Registered the new file in the wizard's
closed pipeline suite (now 52 files). No device opens or native release changes.
The broader fragmented-attachment/fault coverage item remains open.

### Running-wizard route and fault proof — 2026-09-14

Started the updated application in rehearsal mode and exercised its authenticated
HTTP prepare/execute/result/export workflow without fixture-injected workers.
This is actual application execution with synthetic arm data, not physical motion.

- `operation-a0546ea83046430396615b7cf41a4fe5`: the preview enumerated
  0 -> -4 -> 0 -> +4 -> 0 degrees; four simulated commands, all four endpoints
  verified, `SIMULATION_COMPLETE`, zero physical writes.
- `operation-10a65aed35ef481d9b201141ccccb983`: same route with `NO_RESPONSE`
  on leg 2; two simulated commands, leg 2 held, legs 3/4 skipped. The diagnostic
  operation succeeded in producing evidence; its campaign correctly remained
  `SIMULATION_HELD`. No physical stop is claimed.
- Export `wizard-20260914T184912768551Z-b01a1331802f46c986a4710476d068f6`
  under `software/runs/wizard-exports`: independent manifest verification passed,
  and both reports and journal bundles independently reconstructed successfully.
  Use an absolute resolved path with `verify_export`; an initial relative-path
  invocation returned invalid and the resolved-path invocation verified the
  unchanged bundle (manifest SHA-256
  `5a6e786886c5c931a3370c911bb467ef7a9acdf1e962ec4daf98566699004183`).

No camera/serial device was opened. Native attended and unattended release are
not established by these application rehearsals.

### Readable finite-route wizard preview — 2026-09-14

The rehearsal preparation ticket now enumerates each leg's expected start and
absolute wrist target in degrees, alongside the immutable plan hash, maximum
simulated command count, route time bound, observation and endpoint criteria.
The existing confirmation UI renders these effects before execution. It remains
explicitly synthetic with zero physical commands; preparing it runs no worker.

`software/runs/campaign-route-preview-20260914.xml`: **82 passed in 2.53 seconds**.
New public-service tests cover two/eight-leg out-and-back and four/eight-leg
opposite-approach previews, exact target order/hash and no execution on prepare.
Existing campaign outcome and independently verified export tests also pass.
The change requires a fresh wizard process to load; no physical launch occurred.

### Software work resumed; final cancellation check — 2026-09-14

The user asked to continue without adding hardware. Additional hardware is not
a prerequisite for software implementation or simulation. Existing native release
gates remain separate; no stop certificate or physical observation was invented.

Fixed a cancellation race in `positional_owned_campaign.py`: cancellation arriving
during the final clock/admission check is now checked again before the simulated
write. The consumed claim remains burned and cleanup still runs. Tests inject
cancellation at that boundary on both the first and second leg, asserting zero
and one prior writes respectively, no selected-leg write or post capture, no
replay, and exactly one close. This does not promise atomic OS cancellation or
stopping an already-submitted servo target.

`software/runs/campaign-final-cancel-regression-20260914.xml`: **186 passed,
17931 deselected in 10.79 seconds** (`-k positional`). No hardware I/O occurred.

### Campaign pre-submission timing gap closed in simulation — 2026-09-14

The previous goal turn made software progress: query/stream diagnosis and a
verified public-service export regression. This turn inspected the still-open
P2/P3 campaign pipeline and found a separate timing gap. `consume_command()`
checked feedback age, but the executor had no final check between its return and
the simulated write callback. A scheduler pause there could allow submission
before the completed-result verifier later rejected its stale start timestamp.

Added `PositionalCampaignAdmission.check_dispatch_time()` and called it using
the executor's final pre-write timestamp. It checks the consumed state, process,
monotonic ordering, the existing 250 ms sample-age bound and remaining six-second
budget without more storage IO. Failure permanently holds the consumed claim.
The write record/count are created only after this check passes. No tolerance,
deadline or physical release gate was relaxed.

Validation: **184 passed, 17931 deselected in 10.82 seconds** in
`software/runs/campaign-dispatch-stall-regression-20260914.xml` (`-k positional`).
New tests model 251 ms and seven-second delays at the final dispatch check:
zero writes, one cleanup, the later leg skipped, and the durable dispatch claim
retained with no replay. Additional cases cover clock type/regression, expired
age, changed process, and the exact allowed age boundary. Existing successful
two-leg progression and independent endpoint reconstruction still pass.

Scope: this is the hardware-incapable campaign executor. Python clock checks
cannot preempt a subsequent OS pause or stop a servo. Native campaign dispatch
still requires its exact owned boundary and the unresolved installed stop,
failure-response and gravity-containment evidence. No hardware was opened or
moved by this work; P3/P4/P5 and section 10 remain incomplete.

### Query/stream recovery guidance implemented — 2026-09-14

The preceding turn made progress by preserving an actual zero-write connection
failure and identifying stream capture as the next appropriate workflow. This
continuation implements that diagnosis in the software rather than repeating a
hardware-status request.

`wizard_powered_feedback_native_coordinator.py` now publishes
`POWERED_INPUT_BEFORE_QUERY` only for a retained, cleanly closed, completed worker
whose observation failed solely with `PREEXISTING_INPUT`, with positive startup
bytes and exactly zero confirmed command bytes. The operation remains FAILED;
incoming bytes are not promoted to a complete pose, freshness or motion authority.
Its result guidance directs export/review and a separately reviewed new launch
using `capture_powered_arm_telemetry`. No retry, purge, deadline change, rearming,
source-record migration or native movement was added.

Validation: **50 passed in 13.84 seconds** in
`software/runs/powered-stream-guidance-integration-20260914.xml`. Coverage includes
17 ambiguous/fault cases, existing silent-query behavior, serial observation/wire
tests, and a public wizard test with a hardware-incapable worker. That integration
test preserves a partial T1051 frame byte-for-byte in a verified export and proves
both query and stream actions stay unavailable after consumption, including after
another setup record. Tests are synthetic, not new physical observations.

The already-running wizard retains its old source snapshot; this source change
must be loaded in a new owned session before use. Historical exports remain
unchanged. Physical directional correction, native multi-leg stop qualification
and unattended release remain incomplete under the gates below.

### Confirmed bench session: query/stream mismatch — 2026-09-14

Jack confirmed the attended, powered, stationary bench setup and asked not to
repeat routine confirmation questions. Recorded that report and refreshed USB
inventory and native correlation for the expected COM7 controller. This is an
operator report, not an independently measured physical condition.

Actual powered-feedback operation
`operation-bec2fdda62f244e89a47373a1f15b8e7` opened the port but stopped with
`PREEXISTING_INPUT`: 128 retained bytes begin with a T1051 telemetry frame.
The frame is incomplete. **Zero command bytes were written**, serial cleanup
completed, and the owned process exited. This does not establish a complete
fresh pose or explain the previously measured directional endpoint bias.

The appropriate next connection action is `capture_powered_arm_telemetry`,
which collects existing telemetry for up to five seconds without commands.
Do not purge the data or retry the consumed query. The current launch has
consumed its one powered-feedback attempt; its five-minute startup report also
expired during investigation. No movement was dispatched or gate bypassed.

Verified export:
`software/runs/wizard-exports/wizard-20260914T182850156998Z-a2487607a107470db51f7314f3fa1642`.

Next sequence, prepared before another physical connection:

1. Preserve/review the export, then start a new owned wizard session.
2. Use command-free stream capture first for this streaming controller, with
   current setup evidence and USB correlation; do not assume a query reply.
3. Generate absolute wrist choices from that current retained capture. Reviewing
   an old export alone does not populate these live-session choices.
4. Stage the bounded +4-degree positioning target only if the complete six-joint
   baseline matches its reviewed start; verify the new endpoint independently.
5. Evaluate the experimental negative correction only from its matched start,
   keeping nominal target and motor target separate. Stop on a failed endpoint;
   no automatic replay, tolerance widening, or unbounded correction loop.

The repeated confirmation friction is a workflow issue, not missing user
permission. Prepare file-only work before time-limited physical setup checks;
do not renew an expired observation by copying an old confirmation timestamp.

### Full registered wizard suite timeout repaired — 2026-09-14

The actual wizard `positional_campaign_boundary_tests` action timed out after
60.203 seconds (`operation-bf22b5e1a6f04103a3b2c0de310bf23f`). Its closed roster
has grown from eight to 51 files; the old 60-second limit no longer covers the
real-clock fake-device and isolated-package tests. Process inspection confirmed
the timed-out worker was gone before a new operation was started.

Changed only this no-hardware diagnostic's explicit timeout to 180 seconds in
`application/wizard_actions.py`. No motion, write, feedback-age, capture, cleanup
or campaign release budget was changed. Ten focused tests passed in 1.47 seconds:
`software/runs/wizard-campaign-diagnostic-budget-20260914.xml`.

Preserved the failed-session export at
`software/runs/wizard-exports/wizard-20260914T132154247776Z-c2f3d1d024994d79bb2ed52ea93bbdd1`.
Restarted only the assistant-owned wizard to load the source change. The prior
staged correction runtime is historical: it must be restaged against current
sources and fresh metadata before any physical operation.

The new actual wizard operation `operation-dfc9860be379440e8809fb7e235f64f1`
completed successfully: **633 passed in 108.84 seconds**, all 51 registered
files, zero device opens, serial writes or motion commands. Export operation
`operation-4ff4361c68a3468f9ef9bfd76fa8300c` completed and verified its diagnostic
bundle. This validates the application-launched software suite, not hardware
motion, physical stop or unattended release.

Live correction is still pending a current powered/stationary observation and
the matched-start workflow. Native multi-leg qualification additionally needs
the scoped installed stop/failure-response and gravity-containment evidence
described in section 10 and POSITIONAL_STOP_SOURCE_REVIEW_20260913.md. Automatic
goal continuations do not supply missing physical observations. The full goal
remains incomplete; no physical command or automatic retry was sent.

### Received-controller metadata and real wizard staging — 2026-09-14

Started a fresh physical-mode wizard (session
`wizard-f64969dcb73d4719b4587fc98cf886f1`) without opening a device. Windows
present-device enumeration and the wizard's native metadata correlation identify
the expected CP210x on COM7, VID 10C4 / PID EA60, serial
`52E4E1E8337FEF119E92181CEDD322A4`. Win32_SerialPort alone omitted this device;
do not infer absence from that legacy inventory. Native correlation found one
generic match and one native match, with no blockers and all effect counts zero.

Completed through the actual authenticated wizard API, not injected fixtures:

- Inventory: `operation-424aa2eb4dd24fe6bba9198a4b461f71`.
- Metadata review: `operation-f26f173f37df4ef1b1a6473a206bab60`.
- Native correlation: `operation-6e9e3fd063644461b770b54bf3b5c70b`.
- Model/firmware source registration: `operation-36544e2c2ef747ca9c5adc6a6b0656f1`;
  explicitly based on Jack's prior report, not fresh binary verification.
- Saved physical-trial assessment: `operation-6c1f980fdb4d468ea055bd2571959175`.
- Controller/assessment matching: `operation-fe930463d2f34560a86aeb61dc681086`.
- Runtime preparation: `operation-b128b30faf574f28a7789ef8a74433ab`.

Prepared future attempt `operation-ae93a6b5ef0845e7857d4b1533120e0c`, nominal
zero / experimental motor target -0.966796875 degrees, runtime SHA-256
`d61c97a04ef72270348754d00d216ad2fcb48b20e052872a419485380b72a945`.
No final movement review has been signed or consumed, and no serial port has
been opened. Execution remains held for the existing fresh powered-startup
report/current-metadata gate. USB metadata cannot establish actuator supply,
stationarity or a matching six-joint starting pose. Do not manufacture a fresh
operator observation from old messages or bypass this gate.

Exported and verified the session's diagnostic evidence:
`software/runs/wizard-exports/wizard-20260914T131833085541Z-5e0d388dbda446a0808771f197f4c4a0`.
Export operation: `operation-32330e844431464fb40492ff6d56ff8c`.
Next live step requires a current powered/stationary observation, refreshed
metadata where expired, and the approved baseline/matched-start workflow. The
single correction must not be applied from an arbitrary current wrist pose.

### Actual observation end and successful real-clock software rehearsal — 2026-09-14

Final capture v2 stops when the remaining 30 ms read-admission guard is reached,
instead of waiting idle. `observation_end_ns` records the actual end separately
from the unchanged `window_deadline_ns` (start + 200 ms). Independent validation
requires the observation end in the final 30 ms, all reads inside the observed
interval, completion no later than the maximum deadline, and the unchanged
>=100 ms observed stable span and <=100 ms current feedback-age limit. No
timestamps, commands, retry counts, original deadlines or sample spans are
fabricated. Legacy final v1 and all ordinary baseline/post contracts remain.

The first real-clock fake run sent once and the child reconstructed a settled
endpoint, exposing a second issue: the parent applied the small IPC parser's
4096-node limit to the larger retained outcome. The outcome contains duplicate
read-window arrays in the full envelopes and trial projections. It now uses a
fixed 16,384-node budget within the existing 512 KiB/depth-16 bound. The small
IPC reference keeps its default 4096-node limit. Duplicate fields, nonfinite
numbers, excess depth/bytes/nodes and mismatched evidence are still rejected.

Verification:

- 132 targeted tests passed in 34.10 seconds:
  `software/runs/wrist-correction-observed-end-verified-20260914.xml`.
  The real-clock fake run had one command, a reconstructed settled endpoint,
  complete export, and 15 ms initial final-readback age versus the prior 47 ms.
- 519 regression tests passed in 103.87 seconds (17,568 deselected):
  `software/runs/wrist-correction-observed-end-regression-20260914.xml`.
  Coverage includes correction, shared process parsing, ordinary endpoint and
  first-motion capture behavior, failed/short-span/late capture, and legacy v1.
- The HTTP real-clock case was then tightened: it now requires exactly one fake
  write, REPORTED_SETTLED from independent parent reconstruction, and a complete
  export. A timing hold no longer counts as passing that case. All five HTTP
  cases passed in 27.41 seconds:
  `software/runs/wrist-correction-strict-wall-clock-20260914.xml`.

These are fake-kernel, in-process-owner rehearsals with real host time and
filesystem work; not native serial scheduling, hardware accuracy or physical
stop qualification. No real arm connection, movement or compensation occurred.
The previous diagnostic-only wall-clock acceptance is superseded by the strict
test above. No unattended or automatic campaign release is implied.

Next: restage the updated immutable runtime in a fresh wizard session, inspect
current hardware/baseline through the approved workflow, and qualify the
one-command experiment from its matched starting pose. Compare its endpoint
against saved uncompensated trials before permitting any repeat or opposite
approach. The directional mechanism and proposed correction remain unproven.

### Final review work reduction — 2026-09-14

Removed duplicate raw-capture reconstruction within each final review. The
review now reconstructs once at current time, checks the retained earlier
validation time follows actual capture completion, and compares the complete
saved summary after projecting only its two time-dependent fields. Current
freshness and the original deadline remain checked. This is local reuse within
one call, not caching authority or telemetry validation across calls. Also
removed an extra selection-file read: parsing uses the exact bytes whose hash
was checked in that verification. Every later verification rereads all records.

Verification:

- 48 tests passed in 27.69 seconds, including full fake-device HTTP rehearsal:
  `software/runs/wrist-correction-final-review-optimized-20260914.xml`.
- 77 targeted tests passed in 14.72 seconds after strengthening the changed
  selection test: `software/runs/wrist-correction-review-work-reduction-20260914.xml`.
- Tests cover altered saved age/count, validation before capture completion,
  wrong selection digest, exactly one reconstruction per review, and fresh
  selection reads on each verification (including rejecting later mutation).

The real-clock fake run still held with zero writes. Final-review checks were
below the observed clock resolution, but preparation still took 31 ms; the
capture initially had 47 ms age. Consumption now passed its pre-write check
and persisted its record, then rejected stale feedback on the required
post-publication verification. This is not a physical command or a successful
timing qualification; a consumed attempt must not be retried.

The next timing design to evaluate is the capture's idle tail. The current
shared collector deliberately waits to a fixed 200 ms deadline after stopping
read admission early. Do not simply change retained timestamps/deadlines or
claim an unobserved interval. Any variable-duration final-only capture must
explicitly represent its actual end and original maximum deadline, preserve
the >=100 ms observed stable span, bounded reads, late-byte retention and
same-handle accounting, and be independently reconstructed by the parent.
Legacy baseline/post capture contracts must remain unchanged. Hardware
compensation and the broader campaign goal remain incomplete.

### Integrated final-readback runner and timing diagnosis — 2026-09-14

The owned runner now uses v2 trials: original baseline selection, a distinct
retained final readback, one-use final review/consumption, one exact command,
post-command observation and cleanup. Original timestamps are not refreshed.
The parent independently reconstructs the final evidence, binds its owner to the
observed child PID, and accounts for initial plus final reads on the same handle.
The native dependency archive includes the five final-readback modules. New v2
exports include final claim/capture/reservation/consumption; the portable checker
still accepts the unchanged v1 roster of historical exports.

Verification: **409 passed, 17,659 deselected in 93.76 seconds**, report
`software/runs/wrist-correction-final-integration-regression-20260914.xml`.
This includes actual loopback HTTP/coordinator/export integration with a fake
kernel, isolated archive imports with device access disabled, successful and
missed endpoint reconstruction, changed final evidence/owner/counters, and
cancelled/stale/failed final capture. No fallback or retry write occurs on those
faults. These are software tests, not physical accuracy qualification.

The instrumented real-wall-clock fake-device run remains **held, zero writes**:

- Final capture was 47 ms old at initial validation (11 host samples).
- Final dispatch preparation took 31 ms, including two final review checks.
- Consumption verification took another 16 ms and rejected the aged evidence:
  `Final readback expired during retained-record verification`.
- Earlier original-baseline binding took 47 ms and ended with a 110 ms-old
  sample. The distinct final capture solves reuse of that original timestamp,
  but the subsequent durable verification path still consumes too much time.
- Clock observations are quantized around 15–16 ms; zero recorded duration means
  below observed resolution, not zero cost. Timings include instrumentation.

The real-clock test intentionally accepts a held outcome to verify fail-closed
behavior. Its passing status must NOT be interpreted as dispatch qualification.
There were no real serial connections, arm commands or new physical samples.

Next work, in order:

1. Reduce redundant reconstruction and file reads within the final review path,
   while preserving signature, unchanged-file, owner, cancellation, one-use,
   deadline and final <=100 ms age checks. Do not cache current authority or
   relabel samples. Test altered records between verification stages.
2. Repeat wall-clock rehearsals and record final-sample age at preparation,
   consumption and dispatch; distinguish timing holds from target misses.
3. Only after timing is qualified, use the existing bounded workflow to obtain
   the matched historical starting pose and run the single compensation candidate.
4. Compare nominal endpoint error against the uncompensated saved trials before
   trying repeats or the opposite approach. The physical error mechanism and
   candidate correction remain unvalidated; no multi-leg release is implied.

### Version-two result and record reconstruction — 2026-09-14

Extended the result reviewer with a strict v2 trial domain. It retains the old
baseline, adds final-readback hash/owner references and the native binding's
actual final dispatch-check timestamp. The original signed review is verified
normally; the distinct final review is authenticated and checked fresh at that
dispatch timestamp. Missing/mismatched evidence and invalid capture/write ordering
are rejected. V1 behavior and its existing baseline-age requirement remain intact.

V2 publication reconstructs the original reservation, final reservation and
consumption, final capture claim/original, and three selected-baseline records.
It checks all eight hashes, owner/command/review association, reservation/claim/
dispatch ordering, and rejects conflicting legacy consumption. Publication
rechecks retained records after storing trial bytes, without overwriting files.

54 tests passed in 6.57 seconds:
`software/runs/wrist-correction-final-result-review-20260914.xml`. Fake native
success and missed endpoints are reconstructed correctly; six invalid evidence
cases and seven changed/conflicting record cases are rejected. Read-only
reconciliation and legacy compatibility are covered. No real hardware accessed.
Wizard regression roster: 51 files.

Remaining: update owned-trial envelopes and parent lifecycle accounting, native
package inclusion and export roster, then enable the new path in the runner and
repeat complete synthetic/real-clock rehearsals before any physical correction.
No live runner or unattended/campaign release change occurred in this step.

### Native permit transition for final-readback dispatch — 2026-09-14

The owned collector now attaches an internal exact-connection/evidence-hash
association only after a valid capture is retained. New permit preparation
requires that association, consumes it once, reloads the originals, authenticates
the final review and creates durable final consumption. Changed records,
cancelled/revoked permits and substituted connections cannot prepare dispatch.

`FINAL_BOUND` uses the existing serial facade and exact payload checks. Dispatch
performs the existing two metadata checks, consumes final evidence durably and
rechecks <=100 ms age after the final identity check. It does not change the old
baseline timestamp or create legacy consumption. Revocation also invalidates
late-attached capture proof. The open connection and API instance remain pinned.

50 tests passed in 5.82 seconds:
`software/runs/wrist-correction-final-dispatch-20260914.xml`. A fake native write
succeeds once even though the original sample is older than 100 ms, because the
distinct final readback is fresh. Stale/changed evidence, cancellation, revoked
permits and substitution prevent writes. All real hardware remains untouched.
Wizard regression roster: 50 files.

Not yet enabled in the live runner: parent result reconstruction, complete child
evidence accounting, package inclusion and export rosters must be updated for
the distinct final reservation/consumption records first. Then re-run composed
synthetic and wall-clock tests. No unattended or multi-leg release is implied.

### Durable one-use final-readback consumption — 2026-09-14

Added `FinalReadbackConsumption` in `wrist_correction_final_consumption.py`.
It copies selected evidence, authenticates the final review, verifies retained
claim/capture/selection originals and the original signed bundle, and requires
same-process/current-context checks. A distinct exclusive reservation prevents
reconstruction after failure; consumption is exclusively saved before returning
the exact reviewed command record. Existing legacy consumption is a conflict.

The final readback's <=100 ms age is rechecked before and after durable
consumption and again after retained-record reads, which can themselves take
time. Cancellation, changed files/context/PID, clock regression, slow storage or
expiry leave the object held. No file is overwritten and no retry path exists.
Returned records explicitly deny motion authority/native dispatch implementation.

37 tests passed in 4.47 seconds:
`software/runs/wrist-correction-final-consumption-20260914.xml`. Tests include
normal one-use behavior, seven pre-consumption faults, expiry/tampering/storage
failure during consumption, failed reconstruction and delayed verification reads.
No hardware IO. Wizard regression roster: 49 files.

Remaining: native permit/binding transition to this consumption, all child/parent
evidence and package/export updates, then complete simulation and real-clock
qualification. The new reservation/consumption writes must be included in that
timing measurement; functionality tests do not establish adequate timing margin.
The live runner still uses its original guarded path.

### Authenticated final-readback association — 2026-09-14

Added `wrist_correction_final_review.py` and separate-domain final-readback
sealing/verification on the existing protected review authority. It verifies the
original signed review normally, reconstructs the retained new capture summary,
checks request/selection/connection/process association and original record-hash
roster, then rechecks current readback age. The signed intent includes the exact
original bundle, claim and capture hashes plus unchanged target and deadline.

No review timestamp or deadline is renewed. This does not weaken the existing
baseline validation. Changed records, owner, command, key or deadline are refused;
an authenticated readback still expires. The returned object explicitly has no
motion authority or one-use dispatch implementation. Actual process/connection
ownership must still be supplied and verified by the native integration, not by
browser assertions. Signature consistency is not physical provenance.

53 tests passed in 4.00 seconds:
`software/runs/wrist-correction-final-review-20260914.xml`. Tests use the owned
fake connection/capture originals, reject eight altered-input cases and expiry,
and verify no fake write occurs. No hardware IO. Wizard regression roster: 48
files. Remaining: durable one-use final dispatch consumption, native binding,
parent reconstruction and export/package integration, then timing qualification.

### One-use owned final capture and retention — 2026-09-14

Added `wrist_correction_owned_final_capture.py`. It requires the exact existing
correction connection/permit/request, open and unwritten, with the same process
and a bound selection. It holds the permit before work, rechecks retained
selection hashes, and exclusively publishes a capture claim before reads.
Reads go through that connection's existing cumulative baseline budgets; no new
handles, command, budget reset or automatic capture retry is introduced.

The claim records request/selection/connection/process association. The retained
result contains the complete capture envelope, validation or failure, claim
hash and diagnostic-only status. Even a valid readback leaves the permit held;
neither legacy selected_payload nor legacy dispatch can resume it. The caller
continues to own cleanup. Storage failure cannot make dispatch available.

47 tests passed in 3.44 seconds:
`software/runs/wrist-correction-owned-final-capture-20260914.xml`. Tests cover
same-connection accounting, cancellation, empty data, exhausted cumulative read
budget, changed selection, one-use capture, claim/result storage failures and
handle cleanup. No hardware IO; all connections use the fake serial kernel.
Wizard regression roster: 47 files.

Remaining: authenticate and consume this distinct final-readback evidence for
dispatch, validate its age before/after durable consumption, and integrate raw
evidence into child/parent reconstruction, native package and exports. This
helper is not yet called by the live runner, which retains its existing guards.

### Bounded final-readback collector — 2026-09-14

Added `wrist_correction_final_capture.py`, reusing the existing bounded capture
engine and clean-envelope validator. It takes a read callback supplied by the
owned caller, never creates/opens a connection, and sends no command. The final
window is 200 ms, at most 16 reads/8 KiB, 256 bytes per read, with 15 ms admission
spacing. A 5 ms extra tail guard plus the shared 25 ms allowance bounds late-read
risk; actual late completions remain retained and rejected. This does not change
the existing baseline collector or its guard, nor the 100 ms dispatch age limit.

The full envelope carries original bytes, acquisition windows, limits, errors,
late/abnormal/untimed completions and diagnostic-only flags. Clean captures feed
the final-readback validator with the original selection and request deadline.
Cancellation, read failures, malformed data or exhausted capture limits do not
trigger another window. Failures are retained but cannot validate as a fresh pose.

39 tests passed in 2.63 seconds:
`software/runs/wrist-correction-final-capture-20260914.xml`. Covered cancellation
before/during capture, late data, clock failure, oversized output, empty data,
reader exception, altered request/count/deadline/hash/authority flags and the
clean validator path. No native IO. Wizard test roster: 46 files.

Not yet wired into native dispatch. Integration must enforce same-connection and
one-use acquisition ownership, debit these reads against cumulative connection
budgets, authenticate/retain final evidence, and update parent reconstruction
and export together. The original live path and stale-baseline hold are unchanged.

### Final-readback validation contract — 2026-09-14

Added `wrist_correction_final_readback.py`, a pure validator with no acquisition
or dispatch capability. It reconstructs the historical selection from exact
originals, checks its hash, and evaluates a separate bounded raw readback:
maximum 200 ms acquisition, 16 read windows and 8 KiB (the shared parser also
limits each read to 256 bytes). Complete coverage, finite six-joint frames,
stable >=100 ms span and <=100 ms final host sample age are required. The new
reports must remain within the existing 0.5-degree diagnostic agreement bound
of the selected baseline and satisfy the original approach/envelope constraints.

Nominal target, motor command and proposal must remain unchanged. The output
distinguishes original/final sample timestamps and hashes, preserves the supplied
review deadline and explicitly denies motion authority/device freshness proof.
It does not refresh old timestamps. Host must still authenticate the deadline,
selection and connection association; this pure report is not an admission token.

48 targeted tests passed in 3.16 seconds:
`software/runs/wrist-correction-final-readback-20260914.xml`. Covered invalid
cases include stale/future/expired time, excessive bytes/reads/window, partial
frames, gaps/order, wrong USB/selection and changed joint pose. The wizard test
roster now includes 45 files. No hardware IO or execution change occurred.

Remaining integration: bounded read acquisition on the already-owned connection;
retained authenticated association with the existing selection; explicit one-use
admission consuming the final readback rather than relabeling old baseline data;
unchanged final age checks before/after durable consumption; raw evidence in
child/parent reconstruction, native package pins, and portable export validation.
Existing live dispatch behavior remains unchanged until that chain is complete.

### Remaining freshness budget breakdown — 2026-09-14

Extended wall-clock instrumentation with baseline sample age and named durable
record timings. Two additional incapable runs held before any fake write:

- `wrist-correction-freshness-breakdown-20260914.xml`: baseline binding 47 ms;
  owned selection save 32 ms; baseline age at consumption 109 ms.
- `wrist-correction-freshness-records-20260914.xml`: binding 47 ms; owned selection
  and consumption reservation saves 16 ms each; last sample age 110 ms at binding
  completion and consumption. One targeted diagnostic passed in 6.29 seconds.

The second run therefore entered binding with its last sample about 63 ms old.
The shared collector intentionally stops admitting reads near its fixed deadline
(`read_end_guard_ms + 25 ms`), and host scheduling adds time. This plus durable
publication exhausts the 100 ms budget even after historical analysis caching.
The timestamp resolution limits these figures to approximate intervals.

No freshness, collection, durability, or one-use safety policy was weakened.
Passing the diagnostic means the held result and export were handled correctly,
not that wall-clock execution is qualified. This remains a software timing issue,
not an explanation of the physical direction-dependent encoder offset.

Next design investigation: separate immutable experiment preparation from a
bounded final readback immediately before dispatch. Before implementing this,
specify and test: the same owned connection; finite read/byte/time budgets;
six-joint agreement with the selected baseline; unchanged nominal/motor targets;
retained raw readback and association with the one-use selection; unchanged
review lifetime; final sample age <=100 ms before and after durable consumption;
parent reconstruction from originals; and fault-stop for stale, missing, moved,
malformed or late readback. Do not relabel an old sample as fresh, issue another
movement to obtain freshness, omit durable consumption, or add automatic retries.
Until this contract is implemented and qualified, physical correction stays
unqualified and the existing guard continues to hold stale attempts.

### Wall-clock dispatch latency investigation — 2026-09-14

Added a wall-clock variant of the incapable HTTP rehearsal. Instrumentation
wraps the existing review/binding methods without replacing checks. Measurements
are retained as `wall_clock_diagnostics` JUnit properties. This diagnostic allows
either settling or a freshness hold: passing the test is not timing qualification.

Before optimization, repeated historical-trial verification took approximately
47–78 ms per call. Baseline binding took 406 ms and dispatch rejected
`Selected correction baseline expired`; zero fake writes occurred. Source:
`software/runs/wrist-correction-wall-clock-20260914.xml`.

Implemented a 16-entry bounded cache of pure historical trace analysis in
`wrist_correction_proposal.py`. Keys contain every immutable request/trial byte
and the expected evidence basis, not just operation IDs. Cached values are
serialized and decoded afresh to prevent caller mutation. Malformed analyses
are not cached. Live samples, current metadata, signatures, timestamps, admission,
filesystem evidence and consumption checks are not cached or relaxed.

The first optimized timing run measured 31 ms baseline binding and 16 ms
consumption, but still held with `Correction baseline expired after consumption`
and zero fake writes. Source:
`software/runs/wrist-correction-wall-clock-cached-20260914.xml`.
Timer granularity makes zero-duration entries below-resolution observations,
not proof of zero cost. These measurements use fake metadata/serial IO.

40 regression tests passed in 23.73 seconds:
`software/runs/wrist-correction-historical-cache-20260914.xml`. Tests cover
byte/basis changes, mutable returned reports, uncached failures, one-use binding,
review integrity and HTTP composition. No actual hardware moved.

Next: measure baseline sample age at binding/consumption boundaries and remaining
durable-write costs, preserving the existing 100 ms freshness limit. Native
timing remains unqualified. This software latency cause is separate from the
physical directional error; no physical bias correction has been validated.

### Portable correction export validation — 2026-09-14

Added the read-only `wrist_correction_export_validation` module/CLI. It validates
canonical manifests, complete request association, a request-derived fixed file
roster, byte limits/totals, local artifact hashes and stream prefixes. It never
reads the original workspace path embedded in a request. Path substitutions,
missing retained files, changed bytes and false completeness claims are rejected.

New exports include retained-prefix SHA-256 values for truncated streams. Older
untruncated exports remain verifiable; a legacy truncated stream without a prefix
hash is rejected explicitly. Missing artifacts and truncated streams remain
visible even in an internally consistent failure export. Integrity validation
does not authenticate provenance or independently verify the endpoint, and grants
no replay authority.

From the workspace, validate a copied export directory:

```powershell
.\.venv\Scripts\python.exe -m rocell.application.wrist_correction_export_validation "C:\assigned\copied-correction-export"
```

Exit 0 means integrity checks passed, not movement success; inspect
`artifact_roster_complete` and `streams_complete`. Exit 1 reports a validation
failure. The validator creates no files.

28 tests passed in 28.95 seconds:
`software/runs/wrist-correction-portable-export-20260914.xml`. These include a
copied-directory read-only test, seven corruption cases, truncation/CLI checks,
and validation of complete/incomplete real-coordinator HTTP rehearsal exports.
No hardware IO. Remaining: wall-clock timing diagnostics and contained-worker
qualification before the physical correction experiment; unattended/campaign
release still requires the original stop and clearance evidence.

### Composed HTTP endpoint verification rehearsal — 2026-09-14

Extended the HTTP test to run real correction child composition, admission,
single-write collection, child result encoding, parent endpoint reconstruction
and export. Controller metadata and serial kernel are incapable fixtures; the
owner calls the child in-process and supplies simulated process metadata. This
does not test actual child-process containment, USB IO, or physical provenance.

The successful synthetic endpoint produces `REPORTED_SETTLED` and a successful
wizard result. An injected wrong endpoint produces `WRIST_EXCURSION` and a failed
wizard result. Both issue exactly one fake write, close all three fake handles,
retain the complete artifact roster, and verify exported copies against originals.
The existing timeout/cancellation cases remain covered. Same-ticket HTTP retries
remain idempotent.

The test uses deterministic virtual time consistently for acquisition and idle
guards. An initial frozen-clock harness stalled the guard; a mixed wall/virtual
clock experiment was held before confirmed write. Neither is evidence of live
timing qualification. No freshness threshold or production guard was relaxed.

26 tests passed in 37.97 seconds:
`software/runs/wrist-correction-http-endpoints-20260914.xml`. No actual hardware
movement occurred. Remaining: independent portable-export validation, wall-clock
timing diagnostics and real contained-worker qualification before physical
correction. Native unattended/multi-leg stop and clearance gates remain unmet.

### Real-coordinator HTTP failure rehearsal — 2026-09-14

Added `test_wizard_wrist_correction_http.py`: an actual authenticated loopback
HTTP server executes assessment, binding, runtime staging, final acceptance,
real coordinator signing/preparation, incapable worker substitution, real parent
failure retention and exports. No device or native child is accessed. The
controller, powered-state context and signing key are explicitly test fixtures.

This found a real integration fault hidden by the earlier mocked coordinator:
the immutable binding stores a tuple of original pairs, but coordinator proposal
contracts require a list. The service now supplies a local list copy of the same
immutable pairs to both confirmation and execution; no contract was weakened.

Timeout and cancellation-after-worker cases both retain exports. Tests compare
each retained exported artifact byte-for-byte and by hash with its original,
retain partial stdout, and keep missing artifacts explicit. Repeated execute
requests return the original receipt without another run. Standard wizard log
exports also verify. Endpoint success through the full real child path has not
yet been rehearsed by this HTTP test; it deliberately tests process failure.

31 tests passed in 45.48 seconds:
`software/runs/wrist-correction-http-integration-20260914.xml`. The wizard
positional regression roster includes the new HTTP file (44 files total).
Next: successful synthetic child/endpoint reconstruction through the integrated
flow, plus portable exported-evidence validation, before physical correction.

### One-use correction wizard review/run integration — 2026-09-14

Added `run_wrist_correction` through the existing trusted correction coordinator.
The UI shows the nominal endpoint and distinct experimental motor target, fixed
speed/acceleration, starting-pose context, no-retry policy and shutdown warning.
Missing or malformed preview disables the form; host validation remains decisive.

Preview and final acceptance bind the prepared attempt/runtime and powered setup.
Saved originals are reconstructed again at acceptance. The original acceptance
timestamp reaches the signed-plan coordinator without renewal. Acceptance is
one-use even if execution fails. Other motion profiles and restaging are blocked
after acceptance within this session. Native prelaunch, current identity, baseline,
command admission, process containment and cleanup checks remain in place.

Runtime preparation now allocates a separate future execution ID: running cannot
overwrite the setup operation. The UI result reads the parent's reconstructed
endpoint verdict, not just process status or successful export. Endpoint misses,
cleanup holds, missing verdicts and export failures remain failures. Cancellation
does not qualify as physical stopping. No unattended or multi-leg release added.

46 targeted tests passed in 51.28 seconds:
`software/runs/wrist-correction-wizard-run-20260914.xml`. Coverage includes
setup-history preservation, one-use acceptance, changed originals after preview,
five endpoint/export outcomes, and pure-DOM target/warning rendering. Service run
tests use a fake coordinator; lower-layer tests are synthetic. No actual hardware
connection or correction occurred. This is not physical correction qualification.

Next: a full nonhardware HTTP workflow through the real coordinator with an
incapable process boundary, exported-original reconstruction, and failure paths;
then one appropriately reviewed physical experiment from a matched baseline.

### Wizard correction runtime preparation — 2026-09-14

Added `stage_wrist_correction`, a physical-session, no-hardware wizard action
with a closed choice of completed controller/assessment bindings. It reconstructs
the binding, checks the controller and protocol originals, rebuilds the proposal
from retained trials, and stages the pinned native runtime. All evidence is
checked again after staging. Replacement clears prior configuration first;
failures cannot leave an older setup active. Partial files remain as evidence,
not execution authority.

The setup receipt retains the binding/runtime/source hashes and distinguishes
the nominal endpoint from the experimental motor target. No launch reservation,
signed movement review, device open or command occurs. A future run must bind
its final accepted review and host operation ownership to this exact setup;
execution remains disabled in the UI pending that integration and rehearsal.

29 targeted tests passed in 22.69 seconds:
`software/runs/wrist-correction-wizard-runtime-20260914.xml`. Tests include
assessment -> controller matching -> real package staging -> standard log
export, five changed-evidence cases, and mutation during package creation.
Inputs were synthetic and no hardware was accessed. These are service-layer
tests, not a browser or physical correction qualification.

### Retained correction assessment/controller matching — 2026-09-14

Added `wrist_correction_assessment_binding.py` and the physical-session wizard
action `bind_saved_wrist_correction`. Closed choices select this session's
assessment and reviewed controller source. The host rechecks assessment hashes,
saved originals, experiment eligibility and USB unit identity, then retains the
binding. Changed evidence, ineligible hypotheses and a different controller are
rejected. This is historical identity matching, not current USB/pose verification;
no device open or movement is authorized.

21 binding/saved-source/wizard tests passed in 5.82 seconds:
`software/runs/wrist-correction-controller-binding-20260914.xml`. The service
test executed assessment then controller matching using synthetic originals and
reviewed fixture metadata. No hardware IO. The wizard roster now has 43 files.
Next: runtime setup from this binding and exact final-review/action ownership,
followed by an end-to-end nonhardware rehearsal before a physical correction.

### Saved-trial assessment in the wizard — 2026-09-14

Added `assess_saved_wrist_correction`, a read-only wizard action selecting two
to eight explicit saved absolute operation IDs from the assigned export folder.
The loader verifies byte wrappers, request/attempt association and reconstructed
absolute result evidence before deriving a proposal. It retains original hashes
and a proposal hash in the session log. Browser input supplies no command offset.
Historical provenance is explicitly unverified and a fresh baseline remains
required; this action cannot move the arm.

20 saved-source/UI/export and regression tests passed in 3.68 seconds:
`software/runs/wrist-correction-saved-ui-20260914.xml`. The service test executed
the action and verified its log export; inputs were synthetic saved trials.
No hardware IO. The wizard diagnostic roster now has 42 files. Next: bind this
retained assessment to current controller setup and explicit final review before
exposing a single physical correction through the existing coordinator.

### Correction coordinator and closed-roster exports — 2026-09-14

Added trusted-host `wizard_wrist_correction_coordinator.py`: final acceptance
seals the selected original-trial plan without renewing its timestamp, prepares
once, checks current host context at authorization, supervises once, and exports
even when cancellation follows an attempted run. Failures preserve the actual
owned result for recovery; export completion is not endpoint success.

`wrist_correction_export.py` copies a closed generated roster of original trials,
plan/runtime/process/endpoint records and archive into a new assigned export
directory. Each copy has byte/hash metadata; missing/unreadable files and stream
truncation are explicit. No source directory scan or replay authority is added.

20 coordinator/export/preparation/wizard tests passed in 8.02 seconds:
`software/runs/wrist-correction-coordinator-20260914.xml`. Coordinator supervision
used a fake owner and synthetic originals; no hardware IO occurred. The wizard
diagnostic roster now includes 40 files. Browser action/review binding and actual
UI/export rehearsal are still required before exposing a physical correction.

### Correction staging and preparation — 2026-09-14

Added `wrist_correction_worker_preparation.py`. Runtime staging retains canonical
controller/protocol originals and deterministic package pins before the review
clock begins. Preparation requires the exact staged context, matching reviewed
physical-controller identity and signed correction plan, stages original trials,
rechecks source/references and reserves a one-use launch. No plan is invented and
no process is started. Existing or partial staging/attempt files are not replaced.

28 preparation/prelaunch/process-owner/wizard tests passed in 8.11 seconds:
`software/runs/wrist-correction-preparation-20260914.xml`. Prepared fixture wires
also passed independent prelaunch and actual-invocation pin checks without
dispatch. Tests use synthetic controller/trial metadata, not real hardware
qualification. The wizard roster now has 38 files. Next: coordinator/operator
review integration, reproducible exports and end-to-end rehearsal before the
physical correction action is exposed.

### Contained process-owner correction integration — 2026-09-14

OwnedWindowsWorker now recognizes the correction execution branch: exact runtime
registration, signed/current prelaunch checks, fixed passive-pipe containment,
external authorizer, repeated pre-execution checks and bounded result decoding.
After process cleanup, it invokes retain-before-review finalization. Finalization
errors preserve an existing primary error and explicitly fail the result; no
retry is introduced. Physical wizard/coordinator admission is still pending.

83 correction/registration/package/wizard and shared owned-process tests passed
in 16.21 seconds (`software/runs/wrist-correction-process-owner-20260914.xml`).
Correction owner tests use an incapable fake backend and stubbed prelaunch only
to test plumbing; other tests separately validate prelaunch and entry guards.
No real correction process or arm movement occurred. The wizard test roster now
has 37 files. Next: end-to-end preparation/coordinator wiring and qualified
integration rehearsal before exposing the bounded physical correction action.

### Retain-before-review process finalization — 2026-09-14

Added `wrist_correction_process_finalization.py`, composing parent retention and
independent reconstruction. It saves process evidence first, checks complete
input, expected request hash, successful exit and confirmed tree cleanup, then
reconstructs eligible results. Reconstruction failures become a retained held
verdict; no success label or next-leg authority is inferred. Both process and
verdict originals are exclusive. Storage failures still propagate as holds.
Retention accepts the process owner's bounded cleanup list including appended
cleanup diagnostics.

23 finalization/retention/wizard tests passed in 11.43 seconds:
`software/runs/wrist-correction-finalization-20260914.xml`. Synthetic process
receipts exercise settled/missed endpoints, timeout, cleanup uncertainty,
incomplete stdin and malformed stdout. No real process dispatch or hardware IO.
The fixed wizard roster has 36 files. The finalizer must next be called by the
qualified process-owner/coordinator path; that live dispatch remains gated.

### Parent failure diagnostic retention — 2026-09-14

Added `wrist_correction_parent_retention.py` for exclusive bounded retention of
the original request, process-owner report and raw stdout/stderr. Child parsed
status is omitted. Output truncation includes observed/retained lengths and
hashes; missing, malformed or unreadable child outcomes do not become success.
Early admission hash mismatch is recorded rather than repaired. Existing records
cannot be overwritten, and storage errors propagate so the caller must hold.

25 retention/parent-review/wizard tests passed in 14.82 seconds:
`software/runs/wrist-correction-parent-retention-20260914.xml`. Synthetic tests
cover timeouts, early rejection, uncertain cleanup, missing/corrupt/unreadable
outcomes, truncation and storage failure. No hardware IO. The wizard roster
now has 35 files. The retention function still needs wiring into process-owner
dispatch and wizard exports; native correction remains unreleased.

### Guarded correction entry invocation — 2026-09-14

Added `wrist_correction_invocation.py` and the guarded `execute-one` child mode.
The fixed isolated entry supplies actual executable, argv, entry and cwd; these
must match exact registration fields, package paths, independent read bounds
and hashes before prelaunch can run. It then uses the existing signed evidence,
one-use process claim and correction permit chain. Failed entry checks emit a
bounded non-authorizing error. This does not yet provide parent process ownership
or expose a physical wizard action: OwnedWindowsWorker still rejects correction
dispatch before authorizer/backend creation.

36 invocation/package/registration/wizard tests passed in 12.76 seconds:
`software/runs/wrist-correction-invocation-20260914.xml`. Actual isolated processes
rejected empty and internally hash-consistent but unpinned requests. No valid
physical request was executed and no hardware IO occurred. The wizard roster
now has 34 files. Next: parent failure retention, qualified process-owner
integration and physical wizard composition before a bounded live experiment.

### Correction child composition — 2026-09-14

Added `wrist_correction_child_execution.py`: prelaunch validation, current
reference freeze, controller reconstruction, original-evidence loading, durable
process claim, current metadata reader, correction permit and claimed runner.
Permit revocation is unconditional after admission. The entry still has no
execution mode and the process owner still refuses correction dispatch.

Correction requires eight metadata snapshots: admission, two open-claim checks,
native open, two baseline-binding checks and two dispatch checks. The maximum
explicit allowance is now eight (default remains two); cumulative native-call,
byte and deadline limits remain unchanged. Tests verify the eighth allowance
is finite and rejects a ninth acquisition without another native call.

78 child/metadata/package/prelaunch/wizard tests passed in 7.78 seconds:
`software/runs/wrist-correction-child-composition-20260914.xml`. The child test
uses synthetic metadata and an execution stub after real original checks, not
actual arm IO. The wizard roster now has 33 files. Next: guarded entry invocation,
parent failure retention and qualified process-owner/wizard integration.

### Correction current-reference and prelaunch checks — 2026-09-14

Added current source/original reference reconstruction and a frozen snapshot
adapter, plus read-only prelaunch checks. Prelaunch rejects an existing claim,
requires the physical-evidence domain, loads the existing protected correction
authority, revalidates launch/signature/evidence, rechecks current source/runtime
and monotonic time, and checks the claim again. No key is provisioned or claim
created by this operation. Snapshot references are not current USB evidence.

37 prelaunch/package/registration/wizard tests passed in 10.97 seconds:
`software/runs/wrist-correction-prelaunch-20260914.xml`. The tests use synthetic
originals with physical-domain metadata; they do not prove physical provenance.
Actual isolated imports include the new prelaunch module. The fixed wizard
suite now has 32 files. No hardware IO. Guarded child composition, parent failure
retention and process-owner/wizard integration remain before native release.

### Correction runtime registration validation — 2026-09-14

Added exact typed runtime registration validation: interpreter and entry pins,
deterministic archive, retained controller/protocol originals, fixed arguments,
assigned working directory, resource budgets and full operation identity.
OwnedWorkerRequest recognizes the correction payload format; the process owner
still has no correction dispatch branch. A test proves it rejects the request
before authorizer/backend creation. The isolated child remains import-only.

34 registration/package/wizard tests passed in 11.36 seconds, recorded in
`software/runs/wrist-correction-registration-20260914.xml`. The fixed wizard
suite now includes 31 files. No device IO occurred. This validates runtime
descriptions, not hardware qualification or launch approval. Still required:
current-source/prelaunch checks, guarded child execution, parent failure
retention and qualified process-owner/wizard integration.

### Correction isolated import package — 2026-09-14

Added a deterministic correction archive with an explicit dependency roster and
`_wrist_correction_native_child.py`. The actual isolated Python import audit
requires `-I -S`, checks the bounded archive hash/name, disables native loader,
socket and subprocess access during imports, and loads the correction runner
and parent-review modules. The child currently accepts `check-imports` only;
`execute-one` is rejected before loading the archive. This does not implement
live launch or prove process containment for physical effects.

22 correction/absolute package and wizard tests passed in 6.61 seconds:
`software/runs/wrist-correction-isolated-imports-20260914.xml`. Real isolated
processes verified imports and rejected tampered packages/flags. No hardware IO.
The wizard diagnostic roster now contains 30 files. Next: source/runtime-bound
registration and guarded child execution, parent failure retention, then
physical wizard integration. Native correction remains unreleased.

### Independent correction parent reconstruction — 2026-09-14

Added `wrist_correction_parent_review.py` and factored read-only command-record
reconciliation out of publication. The parent now checks retained collector
envelopes against trial projections, independently recomputes the signed nominal
endpoint result, compares published originals, checks command reservation PID,
lifecycle counters and process-time bounds. Incomplete outcomes remain held;
cleanup uncertainty or late finish cannot become ordinary success. No new
records or device commands are written by parent review. Physical accuracy,
process containment and campaign progression remain explicitly unverified.

34 parent/publication/result-reference/wizard tests passed in 20.10 seconds:
`software/runs/wrist-correction-parent-review-20260914.xml`. Tests include a
fake-kernel settled endpoint and miss, cancellation and rehashed summary/capture
tampering. The wizard suite now contains 29 fixed files. No physical IO occurred.
Next remains isolated child/package/registration, parent failure retention and
physical wizard composition, before any bounded live correction experiment.

### Bounded correction result references — 2026-09-14

Added `wrist_correction_native_result.py`: an 8-KiB closed result reference
binds request/attempt, claim hash and fixed outcome filename/length/hash. No
success/status override field is accepted. Parent loading reconciles worker
records with owner observations and reads the bounded canonical outcome from
the assigned store. Changed bytes, unsafe paths, invalid lengths and failed
retention are rejected. The loader explicitly does not verify endpoint or
process containment; independent semantic reconstruction remains required.

44 result-reference/receipt/wizard tests passed in 12.33 seconds, including a
full fake-kernel claimed trial through result loading and subsequent tamper
rejection. Report: `software/runs/wrist-correction-result-reference-20260914.xml`.
The fixed wizard suite now lists 28 test files. No physical IO occurred.
Next: parent endpoint/lifecycle reconstruction, isolated launcher/package and
parent failure retention, then physical wizard admission.

### Parent correction receipt reconciliation — 2026-09-14

Added `verify_correction_worker_receipt` to reconcile the retained launch,
claim and consumption records against a parent-observed PID and process time
interval. It checks exact schemas, operation/claim hashes, ordered timestamps,
signature/evidence at claim and consumption, and rereads claim/consumption
originals to detect replacement. Late process completion is explicitly flagged.
The result proves record consistency only: process containment, endpoint and
physical authority remain false pending independent owner/result verification.

41 receipt/claimed-trial/wizard tests passed in 15.55 seconds, retained in
`software/runs/wrist-correction-worker-receipt-20260914.xml`. Coverage includes
mismatched or Boolean PID, missing consumption, changed signatures, impossible
timing and injected authority flags. No physical IO occurred. Next: bounded
child-result reconciliation, isolated launcher/package integration, parent
failure retention and physical wizard composition; no release claimed.

### Claimed correction trial composition — 2026-09-14

`wrist_correction_trial_execution.py` now composes the one-use process claim
with the exact admitted permit/facade and internal runner. It checks the root,
authority, basis, original manifest and request association before consuming
the worker claim durably, then constructing/opening the connection. The original
admitted request object is preserved for the serial facade's identity checks.
All exits revoke the permit. Process containment remains explicitly unverified.

41 integration/claim/runner/wizard tests passed in 20.93 seconds, including a
complete fake-kernel write/capture/nominal verification/publication chain,
nominal miss without return/retry, cancellation and changed selection/context.
Consumption also rejects a timestamp preceding its process claim. Evidence:
`software/runs/wrist-correction-claimed-trial-20260914.xml`. The wizard suite
contains 27 fixed files. No physical IO. Isolated child/package/registration,
parent receipt and failure retention, and physical wizard admission remain.

### Correction one-use worker claims — 2026-09-14

Added `wrist_correction_worker_claim.py`: exclusive launch reservation binds the
entire selected handoff except its self-referential launch hash. Claim and
consumption revalidate signed original evidence, source/runtime references and
remaining time. A claim is bound to its issuing PID and immutable operation;
consumption is sticky and publishes a separate durable record before returning.
Only one competing claimant succeeds. A storage error cannot trigger retry.

47 claim/store/protocol/wizard tests passed in 7.79 seconds, recorded in
`software/runs/wrist-correction-worker-claim-20260914.xml`. The wizard suite now
lists 26 fixed test files. No device IO occurred. These records are not proof
of executable approval or process containment: isolated child/package checks,
parent-observed receipt reconciliation and physical wizard composition remain
required before any native correction release.

### Correction evidence store — 2026-09-14

Implemented `wrist_correction_evidence_store.py`: exact assigned-root comparison,
generated attempt/content-hash filenames, bounded regular-file reads (8 KiB
request, 512 KiB trial, 64 KiB plan), exclusive staging and immutable loaded
originals. The loader rechecks the protocol manifest; authentication separately
revalidates the signed plan against those originals using the correction-only
authority. Partial staging is retained and cannot be repaired by replay.

44 evidence-store/protocol/current-context/wizard tests passed in 5.32 seconds;
`software/runs/wrist-correction-evidence-store-20260914.xml`. The fixed wizard
diagnostic suite contains 25 files. No hardware IO occurred. Contained child,
package/registration, parent failure retention and physical wizard admission
are still pending; this store does not authorize launch or motion.

### Correction worker handoff contract — 2026-09-14

Added `wrist_correction_native_protocol.py`: closed 64-KiB request decoding,
fixed single-process budget, context/runtime/USB/deadline association, signed
plan hash and ordered 2–8 original request/trial fingerprints. The operation
hash binds the entire payload rather than context alone. No command override
field is accepted. Resolved store bytes must match the manifest; hashes alone
are explicitly not authentication or launch authority. Plan authentication and
one-use owned admission remain separate required checks.

39 protocol/runner/wizard tests passed in 13.61 seconds, recorded in
`software/runs/wrist-correction-protocol-20260914.xml`. The wizard diagnostic
suite now includes 24 fixed test files. No hardware IO occurred. Still pending:
bounded store resolver, contained child/package/registration and parent outcome
retention, followed by physical wizard integration. No native release claimed.

### Correction outcome retention — 2026-09-14

The internal runner now exclusively retains a bounded canonical
`<attempt>-wrist-correction-outcome.original.json`, including partial captures,
write uncertainty and cleanup evidence. Returned receipts identify its byte
length and SHA-256. A retention failure becomes `OUTCOME_RETENTION_FAILED`,
preserving the previous status separately; it cannot look like ordinary success.
Catchable trial interruptions are retained and re-raised after cleanup, without
retrying motion. Hard process termination still needs parent-worker retention.

Verification: 29 tests passed with zero failures/errors in
`software/runs/wrist-correction-outcome-retention-20260914.xml` (15.414 seconds).
Coverage includes complete/missed trials, cancellation, setup and uncertain-write
failures, interruption and failed storage. All device activity was fake-kernel;
no physical correction was sent. Next remains source/runtime-contained worker
integration, parent failure retention and physical wizard admission. This is
diagnostic integrity progress, not evidence of improved physical accuracy.

### Internal correction single-trial runner — 2026-09-14

Composed typed connection, real bounded collectors, baseline binding, exact
one-write permit, post capture, unconditional cleanup and result publication
in `wrist_correction_owned_trial.py`. Fake-kernel complete and fault paths passed;
31 runner/publication/facade/wizard tests green. Short/uncertain writes do not
pass, and missed nominal endpoint never triggers return/retry. No actual hardware
IO. Runner is internal, without a source/runtime-contained launch registration.
Next: worker lifecycle containment, retained incomplete-result publication and
physical wizard composition; unattended release remains independently gated.

### Correction owned connection and collector adapters — 2026-09-14

Added exact correction serial connection with fixed runtime budgets and shared
bounded Win32 cleanup; added typed one-second baseline/five-second post collector
and validated raw-result projection. 27 owner/collector/facade/wizard tests
passed using fake kernel and synthetic clocks. Setup failure and pending-read
cancellation retain cleanup evidence; incomplete captures cannot become complete
raw results. No real hardware access. Next: integrate these adapters into the
single-trial worker with source/runtime ownership and retained failure outcomes.

### Dormant correction native permit/facade — 2026-09-14

Added disjoint correction admission/permit and Windows correction serial facade.
Reuses owned-handle/event/token checks and one-open/one-write machinery while
binding exact correction bytes to durable consumption. Old absolute/relative
interfaces remain unchanged; no physical wizard route registered. 37 fake-kernel,
binding, old-facade and wizard tests passed. No real serial open/write occurred.
Next: owned connection/collector composition and worker lifecycle integration.

### Correction open/baseline/dispatch binding — 2026-09-14

Added `application/wrist_correction_command_binding.py`. Pins original review
store, process, current port/plan; reserves before possible opening; claims open
once; binds/persists raw baseline and exact review; consumes command durably
before returning bytes, with current metadata/cancellation/freshness checks.
Failure holds and original reservation blocks restart. 34 scoped tests passed,
including concurrent dispatch, changed review/clock and cancelled/stale state.
No serial facade accepts this binding yet; no device IO or live correction.
Next: exact native adapter/permit and bounded worker composition.

### Correction Windows current-context adapter — 2026-09-14

Added immutable correction context request and an exact Windows metadata reader
using the existing reviewed-controller resolver. Authenticated reader reopens
the fixed signed plan, checks pinned unit/COM/source/attempt and metadata age,
then authenticates current plan context. No COM open or native permit. Shared
plan authentication also serves fresh-baseline binding without duplicate logic.
34 context/binding/wizard tests passed; context tests registered in wizard suite.
Next: durable open ownership and one-shot raw-baseline/dispatch composition.

### Reviewed plan to fresh raw baseline binding — 2026-09-14

Implemented a separate signed correction plan and conditional binding of a new
raw baseline to an exact command review. Rebuilds original proposal, checks
pre-acquisition approval, unchanged targets/context, full-capture integrity,
bounded age/duration and original deadline. No USB-opening authority is implied.
Wired into the full synthetic wizard chain, exporting both plan and bound review.
41 targeted authority/binding/wizard tests passed. Native current-context/port
ownership and correction dispatch remain the next integration gap.

### Full-chain public HTTP/export verification — 2026-09-14

All five correction scenarios ran through a newly launched rehearsal wizard.
Three completed synthetic chains each exported ten originals; independent
reconstruction from those files reproduced settled/overshoot outcomes exactly.
Two invalid-baseline cases held before consumption. Verified export
`wizard-20260914T103241388499Z-f22ae15dc56d4f91a729b8f0d8c170de`, manifest
`92399221fb3494b6b5fcf768e406350f47eae1750f8f763541a83c01fb0c8027`.
Wizard closed, no hardware IO. Updated `POSITIONAL_IMPLEMENTATION_AUDIT_20260914.md`
with the concrete owned-native acquisition/dispatch gap and remaining sequence.

### Connected correction evidence-chain rehearsal — 2026-09-14

Wizard correction rehearsals now run synthetic signed review, durable one-use
consumption, raw trial reconstruction and exclusive result publication together.
Held starting contexts stop before consumption. The generic export contains
chunked originals (historical trials/requests, signed context/review, reservation,
consumption, new raw trial and publication). A service/export test independently
rebuilds the missed nominal endpoint solely from exported bytes. 25 integration
tests passed. Public synthetic key only; no protected key or hardware access.
Per-string retention failure was fixed with chunked encoding, not larger limits.

### Correction wizard rehearsal available — 2026-09-14

Implemented `wrist_correction_rehearse`, a closed no-hardware wizard action.
Production synthetic original-trial generation uses the bounded collector;
the proposal and nominal endpoint checker run without test-module imports.
Five scenarios cover constant bias, disappearing bias, overshoot, wrong approach
and stale baseline. Nine action/service/export tests passed. Executed all five
through a running local rehearsal wizard's public prepare/execute API, then
verified every exported verdict and the final manifest. No hardware IO.
Export: `wizard-20260914T102803608794Z-304acc2fd589423c963d474a6273255a`.
Manifest: `7d9be34aaee75c3c1f5093e66fd5e54bb673c3178747f5d59f850067001668e7`.
Native correction execution and attended/unattended campaign release remain
incomplete; this action is explicitly a bias-model rehearsal, not calibration.

### Correction result-publication checkpoint — 2026-09-14

Added fixed-store reservation/consumption reconciliation and exclusive original
trial/result publication. Checks intent/bundle/payload hashes, nominal endpoint,
claim-before-write timing and record consistency across publication. Preserves
misses and partial-publication originals. 38 publication/raw-review/consumption/
wizard tests passed. Registered the publication tests in the wizard suite.
This proves synthetic record consistency, not owned native execution. Correction
worker ownership, hardware capture and correction-specific UI remain pending.

### Correction raw-result reconstruction checkpoint — 2026-09-14

Added `application/wrist_correction_result_review.py`: bounded raw baseline/post
decoding, exact signed command matching, timing/byte/cleanup validation, and
nominal-target endpoint reanalysis. Corrupt frames, gaps, short/uncertain writes
and cleanup failures cannot produce success. Registered reconstruction tests in
the wizard suite. This is offline evidence validation; consumed receipt/native
worker provenance and actual correction execution remain unverified.

### Correction durable-consumption checkpoint — 2026-09-14

Implemented `application/wrist_correction_consumption.py`: authenticated review
revalidation, exclusive durable attempt reservation, hash-checked retained
records, process/clock binding, burn-before-return consumption, and sticky holds.
58 correction/wizard tests passed, including competing consumers, interrupted
reservation, storage failure and expiry after durable claim. Registered tests
in the wizard suite. This consumes review data only; it grants no native permit.
Owned serial execution, baseline acquisition and correction UI remain pending.

### Correction signed-review checkpoint — 2026-09-14

Implemented disjoint host-authenticated correction review binding exact nominal
and motor targets, original evidence, baseline and current host context. 63
targeted tests passed; old absolute review authority rejects correction bundles.
New authority test registered in wizard suite. This is not native admission:
durable one-use consumption, owned execution and correction UI remain pending.
No device IO or live compensation in this checkpoint.

### Correction preview/simulation checkpoint — 2026-09-14

Added fresh-start/context-bound correction preview and a five-second synthetic
bias experiment using the actual nominal-endpoint monitor. Preserved nominal
overshoot faults, fixed tolerance, one-command limit and no native authority.
55 focused tests passed. Registered both correction suites in the wizard's
closed positional worker suite; real worker execution passed 230 tests with
zero device IO. Signed native admission and correction UI execution remain
pending; this does not release attended/unattended campaigns or compensation.

### Offline correction proposal checkpoint — 2026-09-14

Implemented provenance-retaining, original-trial-revalidating proposal analysis
in `application/wrist_correction_proposal.py`. Replayed two actual downward-zero
trials; candidate motor target -0.966796875 degrees for NOMINAL ZERO is explicitly
an unvalidated constant-bias experiment. 62 targeted tests passed. No new motion
or native authority. See `WRIST_ACCURACY_INTERNAL_FINDINGS_20260914.md` for
remaining admission, simulator, nominal-endpoint and wizard integration work.

### Directional repeatability checkpoint — 2026-09-14 10:09 UTC

Repeated +4 target: reported 3.779296882 degrees, identical to earlier endpoint,
REPORTED_SETTLED. Repeated zero from the same 3.779296882 start: reported
0.966796894 degrees, identical to earlier miss, TARGET_MISSED. No follow-on
command after the miss. Full evidence and next bounded correction-proposal
implementation are in `WRIST_ACCURACY_INTERNAL_FINDINGS_20260914.md`.

Fixed first-line colon attachment fragment recognition; 70 targeted regression
tests passed. Original held capture remains held. New captures and both one-use
movement records were exported with valid receipts; wizard closed afterward.
Root cause is narrowed to repeatable approach/load-dependent settling, not
proven mechanically. No compensation, PID tuning or wider campaign released.

### Independent matched-target live test — 2026-09-14 09:56 UTC

Under the user's explicit proceed instruction, obtained fresh native identity
and zero-write capture (`operation-1c90125eec3c443e9ab0f44ead05f7bd`, 269 complete
frames, 54 final-baseline samples). A separate admission then ran one absolute
0-degree wrist command from reported -3.251953 degrees:
`operation-e906bfd4c2434e8eb7dd06bb611662d4`.

Result REPORTED_SETTLED: final -0.439453 degrees, within unchanged +/-0.5-degree
tolerance. 280 post frames, no capture issues or other-joint change; clean
serial/process shutdown and verified claim. New accuracy/trace fields retained
successfully through the wizard. No tuning change, retry or return.

Compared with the earlier zero-degree approach from above (+0.966797 degrees),
the endpoint separation is 1.406250 degrees. This supports an approach effect,
not a fixed rounding offset, but one pair with different starting magnitudes
and elapsed times cannot prove causality or repeatability. The new pass margin
is only 0.060547 degrees. Keep campaign release held pending repeatability and
the other required safeguards. Detailed analysis is in
`WRIST_ACCURACY_INTERNAL_FINDINGS_20260914.md`.

Verified export:
`software/runs/wizard-exports/wizard-20260914T095701278724Z-28f7ae3de1a649098428989bee973316`.
Manifest SHA-256: `47e8b7ace2a4891e04f569daf330f76d9f1fe084e01ef35975bc299ded7f9929`.
Stdout SHA-256: `8e04c7d16953858506d577c6fa9b09b7f8275471e66a876599d44602b4759c28`.
Wizard stopped after export. Earlier failed trials remain failed; this was not
automatic continuation or relabeling of the failed positioning sequence.

### Owner-requested internal accuracy investigation — 2026-09-14 UTC

Continued internal diagnosis without requiring vendor contact. Added the
validated offline reference-conversion/load analyzer and included it in newly
published absolute reports. All three retained trials were reanalyzed:
reference goal residuals are approximately -3, +11 and +9 servo steps. Target
rounding is at most 0.042969 degrees here and cannot explain the larger misses.
Each constant-position tail contains changing tT readings, weakening the
completely frozen-cache hypothesis without proving per-sample freshness.

Detailed findings and staged improvement approach:
`WRIST_ACCURACY_INTERNAL_FINDINGS_20260914.md`.
75 tests passed, `software/runs/wrist-accuracy-analysis-20260914.xml`, covering
reference C++ rounding, unavailable load, corrupt originals and report retention.
No hardware command, compensation, parameter or firmware change was made.
Next diagnostic is a separately reviewed matched 0-degree approach from below,
not automatic continuation of the failed positioning sequence. Native campaign
release remains held; the user-requested internal investigation can proceed
without claiming that vendor contact is the only way forward.

### Release work blocked pending external evidence — 2026-09-14 UTC

Revalidated the same critical-path blockers across the implementation audit,
vendor-diagnostic review and this check: repeated physical endpoint misses,
unverified installed servo-feedback freshness, and no qualified stop/watchdog
behavior for already-issued goals. No Python wizard/worker process was running
at this check. No new device action was taken.

The goal is incomplete, not achieved. Native campaign composition remains
unreleased. Safe checks and simulation expose the limitations but cannot supply
the missing installed-firmware or physical evidence. Do not create further
rehearsals merely to imply progress toward release, or relabel failed positioning
as permission for the next leg.

Resume trigger: owner/vendor clarification of a supported read-only diagnostic
path or a separately approved firmware-investigation/deployment scope, followed
by review of the physical stop test method. `WAVESHARE_SUPPORT_BRIEF_20260914.md`
is ready for owner review and sending; it has not been transmitted. No flashing,
configuration writes or expanded motion tests are authorized by this checkpoint.

### Vendor diagnostic handoff prepared — 2026-09-14 UTC

Checked official command documentation and SDK revision
`d9893632aa7f5a9cb283136ab024faf3143ea7db` (roarm.py, common.py, generate.py).
No firmware-build or per-servo freshness query was identified in those inspected
files. This is not a comprehensive claim that none exists. No SDK installed,
device opened, query guessed or firmware changed.

Prepared `WAVESHARE_SUPPORT_BRIEF_20260914.md`, not sent. It contains the exact
three absolute trial results, conservative plateau evidence, source-level cache
concern, and questions on read-only build/servo diagnostics, expected positioning
behavior and already-issued T101 stop/watchdog behavior. Full logs remain local
pending privacy review. Vendor clarification or independently validated installed
diagnostic capability is needed before using an undocumented interface; the
existing native campaign release holds remain intact.

### Wizard freshness-test integration — 2026-09-14 UTC

Added the proposed servo-freshness suite to the closed source-owned test list
behind "Test owned movement pipeline (no hardware)". Browser input cannot add
test paths or pytest arguments. The action description explicitly distinguishes
proposed telemetry tests from installed firmware support. Registration/public
action regressions: 69 passed (`wizard-freshness-registration-20260914.xml`).

Executed the actual public prepare/execute/status/export workflow in rehearsal
mode, operation-6a195c2ee2774e8eba09cd34c0a9f174. The worker completed all nine
registered suites: **205 passed in 8.79 s**, zero device opens, serial writes,
power events, movement commands and contact commands. No physical qualification.

Verified export:
`software/runs/wizard-exports/wizard-20260914T040002496380Z-2eda650ba63a48b39a797498d5113a81`.
Manifest SHA-256: `a5777dd8e977e06523721654a92b21e44675df5573a5a2200c1fedd97f6442f2`.
Wizard stopped after export. The actual arm endpoint shortfall, installed
freshness support and stop qualification remain unresolved; tests do not release
native campaigns or authorize firmware deployment.

### Proposed freshness contract simulation — 2026-09-14 UTC

No existing per-servo acquisition sequence/boot contract was found in the arm
path. Added `arm/servo_freshness_proposal.py` and
`SERVO_FRESHNESS_PROTOCOL_PROPOSAL.md`: bounded simulation-only validation of
all-six-joint successful acquisitions, command/boot association and monotonic
report/acquisition sequences. Cached values, read failures, timestamp errors,
restarts and legacy T1051 cannot establish proposed freshness consistency.
Failures are sticky. No native import, serial command, firmware flash or release.

18 tests passed: `software/runs/servo-freshness-proposal-20260914.xml`.
The model deliberately leaves actual freshness, installed protocol support and
automatic-next-command permission false. Firmware truthfulness, host transport
age and physical stop evidence remain separate unfinished requirements.

### Cached-feedback release-boundary regression — 2026-09-14 UTC

Reviewed `positional_owned_campaign.py`: its entry rejects physical provenance
before IO; the multi-leg runner remains synthetic-only. Existing single-move
native facades also reject campaign admission. No native campaign was released.

Added a cached-at-goal regression to `test_wrist_endpoint_verification.py`:
100 identical target reports with progressing host timestamps can satisfy
REPORTED_SETTLED, but must leave device freshness, physical accuracy, motion
authority and automatic-next-command permission false. This explicitly captures
the source-level limitation; there is no host-only test that distinguishes these
rows from fresh stationary servo reads. Synthetic two-leg progression now also
asserts unverified device freshness and unreleased native execution.

Validation: **34 passed**, `software/runs/cached-feedback-release-boundary-20260914.xml`.
No device access. The previous live failure hold remains in force. Next required
design work is a versioned per-joint freshness/goal diagnostic contract, tested
against cached reads, stale sequences and controller restarts before considering
a firmware integration. That contract cannot be substituted for installed-device
evidence or physical stop/clearance qualification.

### Source-level stale-feedback failure mode — 2026-09-14 UTC

Read-only inspection of the SHA-pinned official reference firmware identified
a concrete cached-position path after failed servo reads. The angle publisher
does not check getFeedback success before converting cached positions, and
T1051 lacks per-joint freshness/status evidence. Details and source line references
are in `WRIST_DIRECTIONAL_TRACE_REVIEW_20260913.md`, "Servo-read freshness finding".
No device opened or commands issued; installed firmware equivalence is unproven.

This prevents promoting a constant reported endpoint into verified fresh physical
position, even when the endpoint error passes. Preserve existing false freshness
and physical-accuracy flags. Before autonomous release, identify a supported
read-only diagnostic path or review a versioned firmware extension exposing
per-joint acquisition success, sequence/age and goal association. No implicit
firmware flashing, PID writes, tolerance changes or motor-stop qualification.
The actual negative-direction shortfall remains undiagnosed; this source failure
mode is a hypothesis to distinguish, not a claimed root cause.

### Matched-target positioning trial held — 2026-09-14 UTC

Fresh metadata correlation and zero-write capture
`operation-440b42f7265749e8a791fbfc1dc070c9` succeeded: 270 complete frames,
55 final-baseline samples, startup 109 ms, reported wrist +0.966796894 degrees.
The complete fresh baseline admitted the proposed -4-degree target without
rounding or changing the five-degree displacement limit.

Executed one absolute diagnostic `operation-1f968b0dfb5d44fa8be8b76c79fcb26a`:
target -4 degrees, T101 joint 4, spd 20, acc 1. Result **TARGET_MISSED**;
reported final -3.251953116 degrees, error +0.748046884 degrees. Complete
post-command reconstruction had 281 frames and no capture issues. Other joints
did not change; transport and serial cleanup were clean, parent claim verified,
and the process exited. No retry or subsequent zero-degree command was sent.

The new trace diagnostic was exercised through the real wizard publication:
210 identical final reports, conservative span 3.734 s, first-final read
1.157–1.188 s after write completion. Full result retained and exported with
the failure label intact. This confirms live diagnostic integration, not endpoint
success, physical position accuracy, fresh device samples or campaign release.

Verified export:
`software/runs/wizard-exports/wizard-20260914T035142470717Z-731985c535f64d5b8d6f5347f89a861b`.
Manifest SHA-256: `a48de29579521d959345051e994069a42f67e55bec812126d4a5a5328e359634`.
Stdout SHA-256: `2f0b37e5cd502e8ca6a3e67f075f7850453f8c788dc8e185e72d6bab864b385a`.

Wizard stopped after export. The matched-target sequence is held because its
positioning leg failed. Do not label it accepted merely because the reported
position is below zero. Next work is diagnostic review of this repeated shortfall
and determining a supported read-only servo/firmware observation path; no PID
writes, angle compensation, tolerance widening, or continuous motion release.

### Integrated trace regression and next experiment — 2026-09-14 UTC

Verified the trace diagnostics survive the public wizard's existing nested
result sanitizer for both settled and missed endpoints, preserve the original
trial hash, and do not duplicate raw child trees in the supervisor summary.
Selected integration regression: **308 passed, 17,301 deselected**, 95.19 s;
`software/runs/absolute-wrist-integrated-trace-regression-20260914.xml`.
Selection covers absolute-wrist modules, historical capture preview and public
powered telemetry actions; it is not a claim that all repository tests passed.

The matched-target decision is specified in
`WRIST_DIRECTIONAL_TRACE_REVIEW_20260913.md`, section "Matched-target diagnostic
decision". The next proposed target is -4 degrees only if a fresh complete
baseline fits the existing five-degree displacement cap, followed by a separately
admitted zero-degree approach only after an accepted positioning result. Any
miss halts that sequence. Differing-target observations are not pooled as proof
of a direction-only effect. No hardware access or new motion in this checkpoint.

### Automated retained-trace diagnostics — 2026-09-14 UTC

Added `summarize_absolute_wrist_trace` and included its bounded output in newly
published absolute-wrist reports. It revalidates the request, original capture,
write and cleanup before calculating start/target/final degrees, endpoint error,
constant-report count, conservative constant-report span, and first-final-value
host-read bounds relative to write completion. Invalid capture/transport yields
UNAVAILABLE, not fabricated diagnostic values. Endpoint acceptance is unchanged;
these diagnostics never authorize another command or prove servo freshness.

The constant span excludes both edge read durations, unlike the earlier manual
outer-bound span. Offline replay of the retained zero-degree trial reproduces
281 frames, +0.966796894-degree final error and 220 identical final reports:
conservative span **3.906 s**; first-final read **0.984–1.000 s** after write.
Original files were not changed. No hardware was opened in this step.

Validation: **66 passed**, `software/runs/absolute-wrist-trace-diagnostic-20260914.xml`.
The existing pinned-source review already establishes that the available PID
commands are writes, not diagnostic reads. Do not send them to investigate this
shortfall. A same-target/opposite-approach experiment and firmware/servo diagnostic
transport review remain necessary; current differing-target trials do not isolate
direction as the cause. Native continuous/unattended release remains incomplete.

### Live opposite-direction endpoint and retention verification — 2026-09-14 UTC

Fresh native metadata and v3 zero-write capture were obtained through a new
public wizard session. Capture `operation-3c91d821953a44a68f667723de3f9768`
contained 270 complete frames, with startup measured separately at 94 ms and
54 final-baseline samples. The reported wrist remained at 3.7793 degrees.

One absolute zero-degree trial was then admitted and executed:
`operation-b9fae47e71b8403ca09a916f85f4dcca`.

- Exactly one T101 joint-4 command, target 0, spd 20, acc 1; 47 confirmed bytes.
- Complete post-command reconstruction: 281 frames, no capture issues.
- Reported final wrist: **+0.966796894 degrees**, outside the unchanged 0.5-degree
  arrival tolerance. Target band was never entered: **TARGET_MISSED**.
- Final value repeated for 220 frames spanning 3.953 seconds, beginning about
  0.984 seconds after write completion within the five-second observation.
  This supports a stable reported shortfall, not merely a late final sample.
- Other five reported joints had zero range over the post-command trace.
- Parent claim/receipt verified; serial closed with zero pending handles/IO;
  process exited cleanly. No replay, corrective command or return was issued.

The corrected wizard publication retained the full result and displayed the
actual TARGET_MISSED outcome, not RESULT_RETENTION_LIMIT. This is live evidence
for the reporting fix and single-trial failure hold. It does not prove a released
multi-leg runner or a physical emergency stop. The negative-direction shortfall
now occurs at an explicit absolute target as well as earlier relative targets;
the cause (controller behavior, servo/load effects, or reported-position semantics)
is not established. Do not compensate angles, alter PID, increase speed, or widen
tolerance based on these few samples.

Export verified:
`software/runs/wizard-exports/wizard-20260914T034235805862Z-20d5d8925f524c809891950900b1fe06`.
Manifest SHA-256: `73f785395ae75f5ac78e0039e2d6df5343ffa1626db9ff4c98e7dd19f32618c9`.
Original stdout SHA-256: `f639c616b181fecb8d2323110b663b39c30d3e69d89c48d7103c143c4a6ff654`.

Wizard stopped after export; no connection left open by the test. Next work:
automate the retained-trace plateau/directional comparison, inspect the pinned
vendor position/control semantics, and design a bounded matched-target diagnostic
that distinguishes direction from target without treating a failed leg as a pass.
Continuous and unattended movement remain unreleased.

### First live absolute endpoint and reporting fix — 2026-09-14 UTC

Fresh v3 zero-write capture `operation-8dab891d95ca406b827ca0d1dbce31e2`
passed full-stream checks: 55,552 bytes, 270 complete frames, startup 109 ms,
54 final-baseline frames, clean serial close and child exit. Acquisition and
startup were separately recorded; no thresholds or original deadlines changed.

The public wizard selected/staged the absolute 4-degree draft, then executed
one attended trial `operation-f05531b8aa8e4f969af7309d8a26d115`:

- Fresh reported wrist start: 1.845703 degrees; target: 4 degrees.
- T101 joint 4, spd 20, acc 1; one confirmed 63-byte command write.
- 51 complete baseline samples and 282 complete post-command samples.
- Final reported wrist approximately 3.7793 degrees; error -0.2207 degrees.
- Reconstructed endpoint: REPORTED_SETTLED, within unchanged 0.5-degree band;
  quiet dwell passed, no other-joint change or wrist excursion detected.
- Parent process receipt/claim verified; raw-result report RESULT_RETAINED;
  clean serial/process shutdown. No retry, return or next movement was sent.
- This is controller-reported endpoint evidence, not independent physical
  accuracy, device-sample freshness, calibration, or unattended qualification.

The public action displayed RESULT_RETENTION_LIMIT after the completed trial.
Diagnosis: the parent report duplicated the full parsed child tree (raw captures
and hundreds of read windows) inside its supervisor receipt, exceeding the
wizard's nesting/item budget. Original report and stdout survived. New reports
omit only this redundant parsed tree; immutable stdout, hashes, process receipt,
reconstructed endpoint and accounting remain. Limits were not increased.
25 regression tests passed in `software/runs/absolute-wrist-live-report-retention-20260914.xml`.
Read-only replay of the actual report with the duplicate removed also passes
the existing wizard sanitizer. The old failed UI result is not rewritten.

Verified export:
`software/runs/wizard-exports/wizard-20260914T033748579158Z-9b2dd53ec0ad4cf8a00ad3edbd75d88a`.
Manifest SHA-256: `83e9a1e221abd11c37ea93914b7afafa2c7e28cb77b4c38c4275b40dc41f1faa`.
Full independently retained report:
`software/runs/wizard-exports/operation-f05531b8aa8e4f969af7309d8a26d115-absolute-wrist-report.json`.

Wizard stopped before source changes; no connection is left open by this run.
Next: fresh session/capture, confirm corrected public result retention on the
next bounded trial, then collect opposite-direction endpoints. The earlier
negative-direction miss remains unresolved; no continuous campaign release.

### Live capture startup timing correction — 2026-09-14 UTC

Standing operator confirmation remains attended, secured, clear and powered;
it does not qualify unattended operation. No movement was sent in this check.
COM7 native identity was correlated before the public zero-write capture
`operation-afa9703a744a48aba8e0dfed0a395e96`. Serial close and process exit were
confirmed. Original bytes: 55,424; full offline reconstruction: 269 complete
frames (the legacy bounded display reported 255). The only coverage gap was
the first complete frame at 156 ms; its read began at 141 ms. The final gap
was 16 ms and there were no interior gaps exceeding 100 ms.

The collector started its observation clock before USB open/configuration.
The retained v2 capture cannot distinguish startup from acquisition latency:
keep it HELD, do not relabel it or use it to authorize a move. Verified export:
`software/runs/wizard-exports/wizard-20260914T032429425283Z-ea997aee52254e43964b0190cca1e5de`.
Manifest SHA-256: `dd9be7273b554106c2230ecc0a0a0be4cedd64d03ae02dbafc1301ab3abe1d8e`.

New collector v3 records acquisition start immediately after successful open.
The original five-second lifecycle deadline is unchanged; startup is not an
extra time allowance. Wire validation requires ordered acquisition/read times,
and historical preview checks the complete acquired stream with the unchanged
100 ms gap limit. v2 exports remain readable with their conservative original
timing. No timestamp is inferred for old captures; no interior data is dropped.
Tests cover missing/forged timestamps, initial/interior gaps, canceled opens,
v2 reconstruction, public wizard capture/select/export and native packaging.
Result: **75 passed**, `software/runs/telemetry-acquisition-boundary-20260914-03.xml`.

Next: restart with the new source identity, re-correlate metadata, obtain one
fresh zero-write capture and inspect its startup/acquisition evidence. Only a
qualified fresh baseline can lead to one bounded absolute wrist diagnostic.
The earlier negative-direction endpoint miss and multi-leg release remain open.

### Modeled full wizard flow and regression — 2026-09-14 UTC

Added `test_absolute_wrist_end_to_end_wizard.py`: actual public capture action
with stable synthetic telemetry and retained journal, onboarding association,
absolute draft selection/staging, single simulated run, target-miss display,
second-run refusal, and export recovery of exact capture and movement stdout.
Capture/selection use the real reconstruction path; final motion confirmation
and execution are explicitly incapable test substitutes, not hardware evidence.

Absolute run exports now have distinct `absolute-wrist-native-logs.json` and
`rocell.absolute_wrist_native_logs.v1` identifiers instead of relative-mode names.
Shipped-renderer tests verify the setup target selector. Relative exports remain
unchanged.

Validation: **310 passed** across the absolute suite and relative wizard/preview/
onboarding regressions (`software/runs/absolute-wrist-integration-regression-20260914.xml`).
After the export naming change, **18 focused tests passed**
(`software/runs/absolute-wrist-flow-export-20260914.xml`). No hardware accessed.

Next: bring up a fresh physical wizard, verify current metadata and powered
setup, capture zero-write telemetry, then select an eligible absolute target and
run one attended trial through the public controls. Stop progression on any
endpoint or transport fault, preserve exports, and investigate directional
accuracy before native multi-leg release. Unattended qualification remains open.

### Retained telemetry binding and setup selector — 2026-09-14 UTC

Added `absolute_wrist_telemetry_source.py`. It reconstructs the historical wire
request from prepared/runtime records and verifies session/source/native-identity
association, consumed/claimed/outcome chain, original stdout/stderr and owned
process receipt. It revalidates the telemetry interpretation from raw bytes and
rechecks records before returning historical draft choices. No current servo
freshness or physical accuracy is inferred.

Successful powered telemetry now caches eligible draft choices for the setup
selector. Selecting an absolute draft re-reads the evidence and requires the
controller source's onboarding identity to match that capture. The draft source
hashes are logged before staging. Relative remains the default; its fields do
not override an absolute draft's approach. Missing or unsuitable capture records
withhold draft choices without discarding the primary capture/export result.

Validation: **32 passed**,
`software/runs/absolute-wrist-telemetry-binding-20260914.xml`, across original-chain
mutations, capture publication and existing public wizard flows. An additional
8-test absolute wizard run passed after adding public selector checks for valid
selection, changed capture and wrong device association. All process receipts and
execution were synthetic; no hardware was accessed.

Next: complete a full modeled capture-to-select-to-run-to-export integration and
rendered setup check, then exercise the attended physical route. Native multi-leg
campaigns and separate unattended release requirements remain incomplete.

### Historical telemetry-to-draft reconstruction — 2026-09-14 UTC

Extracted shared `decode_historical_baseline` from the existing capture preview
and added `absolute_wrist_capture_drafts.py`. It verifies original raw-byte
length/hash, full-capture framing and timing before choosing a fixed final
one-second interval. All six joints must be stable. Candidate targets remain
the closed -4/0/4-degree set; each complete selected frame must permit the same
bounded approach. Out-of-range/no-op targets are recorded as held, not adjusted.

Drafts freeze the reported six-joint start and retain capture hash, acquisition
bounds and original capture-end time. They explicitly remain historical-only;
no timestamp renewal, current-pose assertion or movement authorization occurs.

Validation: **43 passed**,
`software/runs/absolute-wrist-capture-drafts-20260914.xml`, covering original
corruption, early malformed frames, unstable tails, unavailable targets,
unchanged input records, fixed timestamps and relative preview regressions.
No hardware access occurred.

Next: bind these choices to the wizard's retained powered telemetry outcome,
unit/source/session and original process records, then allow selecting a draft
in setup. Do not populate a browser selector from unbound normalized pose data.
Native campaign and unattended release work remains open.

### Wizard absolute endpoint mode — 2026-09-14 UTC

Added trusted-host `configure_absolute_wrist_movement` accepting an exact typed
draft and reviewed controller/protocol originals. It shares the existing
single-attempt wizard slot, powered-context binding, final acceptance timestamp,
cancellation and diagnostic export flow. The run form changes to a distinct
absolute label, target preview and confirmation effects; the existing relative
1/5-degree path is preserved. No browser command/JSON upload route was added.

Run dispatch selects the absolute coordinator only for that host-attached mode.
A retained target miss is presented as a failed movement test, with its endpoint
and retention status shown separately. Relative-only operator assessment is
disabled for absolute records pending an appropriate observation adapter.
The renderer displays the reviewed draft and fixed target, rejects conflicting
absolute/relative previews, and now recognizes the existing relative 5-degree
policy as well as 1 degree.

Validation: **28 passed**,
`software/runs/absolute-wrist-wizard-rendering-20260914.xml`, including public
prepare/confirm/run with incapable coordinators, changed setup, single acceptance,
settled/missed/export-failed outcomes, shipped JavaScript rendering and relative
regressions. Additional operator-mode regressions passed in the preceding
21-test run. No native hardware execution occurred.

Remaining UI work: select/reconstruct an absolute draft from retained telemetry
through the wizard (currently host attachment only), verify export recovery for
absolute results, and add absolute operator observations if needed. Then run an
attended bounded test through this route. Multi-leg/unattended release remains
incomplete; no movement is authorized by these test fixtures.

### Absolute coordinator and diagnostic exports — 2026-09-14 UTC

Added `wizard_absolute_wrist_coordinator.py` and
`absolute_wrist_result_publication.py`. Host confirmation binds the exact typed
draft, staged runtime, unit, session and original acceptance timestamp. Queue
delay cannot renew the 30-second intent. The coordinator prepares/supervises once
and retains attempted-run evidence even after cancellation. Export failure
returns the actual process receipt for recovery rather than retrying motion.

Publication retains immutable request/stdout/stderr originals with byte counts
and hashes, validates the owned receipt and reconstructed result, and records
endpoint status separately from report-retention status. Both a settled trial
and a target miss can be saved successfully; only the former gets the explicit
reported-settled field. Neither grants physical accuracy or campaign advancement.
Preflight zero-digest failures may be retained only without process/stream claims.

Validation: **44 passed**,
`software/runs/absolute-wrist-retention-coordinator-20260914.xml`, including
retained pass versus miss, immutable exports, wrong PID, failed cleanup,
cancellation before/after execution, export failure, stale acceptance,
authorization mismatch and existing relative-coordinator regressions.
All execution/receipts were synthetic. No hardware was accessed.

Next: expose distinct absolute setup/review/run actions in the existing wizard,
using this coordinator and its export outcome without weakening existing relative
controls. Native campaign and unattended release work remains incomplete.

### Complete supervisor receipt path — 2026-09-14 UTC

Exercised the actual absolute supervisor branch with an incapable backend:
fixed staged runtime and signed originals, pre-execution check, canonical child
result, independent reconstruction, and retained process-claim association.
The valid fixture completes; wrong PID, missing claim, wrong claim digest and
changed endpoint summary are rejected while raw stdout remains retained.
These synthetic backend receipts are not physical or real-process evidence.

Tightened prelaunch replay prevention: an existing child claim now refuses
another process before backend construction, with a second check after original
verification. Exclusive child claim publication still handles races at admission.

Validation: **65 passed**,
`software/runs/absolute-wrist-supervisor-receipts-20260914.xml`, across supervisor
receipt paths, prelaunch, process claims, child composition, isolated imports
and result validation. No hardware was accessed.

Wizard integration points inspected: existing observational setup/review/run
dispatch and `wizard_observational_coordinator.py` provide the session/context
and retention pattern. Next implement absolute result publication and the
trusted-host coordinator, then distinct absolute setup/review/run controls.
Keep the existing relative policy unchanged. Full native campaigns and unattended
qualification remain open.

### Guarded absolute entry and supervisor wiring — 2026-09-14 UTC

The absolute bootstrap now recognizes `execute-one` behind exact actual
interpreter/arguments/entry/archive pins and reserved signed-request checks.
Empty and internally consistent but unpinned requests fail before child
composition. Import audit remains host-IO-forbidden and reports no live test.

The owned supervisor now has a distinct absolute branch: fixed registration,
exact deadline, prelaunch verification, passive-pipe process ownership,
approval recheck immediately before execution, parent result reconstruction,
and process-receipt verification. Public wizard controls are not added yet.

Validation: **83 passed**, `software/runs/absolute-wrist-guarded-launch-20260914.xml`.
Coverage includes real isolated import/invalid-entry processes, invalid parent
dispatch refusing backend creation, approval changed after pinning refusing
execution, result reconstruction, and existing owned-process regression tests.
No hardware IO occurred. The new supervisor's complete successful result/receipt
path still needs an integrated incapable-backend test before wizard exposure.

Next: exercise that complete parent/child result-receipt association, then add
public wizard review/run/export controls and attended physical evidence. This
does not qualify native multi-leg campaigns or unattended operation.

### Absolute result wire and parent reconstruction — 2026-09-14 UTC

Added `absolute_wrist_native_result.py` with a bounded exact-schema result
envelope, request/attempt association, lifecycle accounting, and independent
reconstruction of every claimed endpoint review from retained original captures.
Changed endpoint summaries, status labels, capture/write counters, authority
flags and cleanup claims are refused. Settled status requires clean ownership
closure and no reported errors; cleanup overrides remain diagnostic-only even
when the retained endpoint itself was settled. Unopened labels cannot hide IO.

Validation: **67 passed**, `software/runs/absolute-wrist-result-wire-20260914.xml`,
covering wire mutation/budgets, settled and held endpoints, source capture
reconstruction, native fake-connection execution, child composition and isolated
package imports. The package now includes/import-audits the result codec.
No serial connection or physical movement occurred. Result consistency alone
does not verify the owned-process receipt, physical accuracy, or stop behavior;
automatic campaign advancement remains false.

Next: connect this codec to exact guarded CLI invocation and supervisor process
receipt verification, then public wizard review/run/export controls. The CLI
still rejects absolute `execute-one`; native campaigns and unattended release
remain incomplete.

### Absolute child composition and metadata budget — 2026-09-14 UTC

Implemented `absolute_wrist_child_execution.py`: decode the fixed request,
verify reserved originals/review, freeze verified references, reconstruct the
controller binding, claim the process once, acquire current metadata, admit
one absolute command, execute the owned trial, and revoke its permit on exit.
The isolated package includes and import-audits this composition. Its CLI
still rejects `execute-one`; no live launch route has been enabled.

Source tracing and a complete fake-connection native-composition test confirm
**seven** current-context checks: admission, before/after open reservation,
native open, baseline binding, and before/after dispatch reservation. The
metadata acquisition ceiling now allows seven explicitly requested snapshots;
default two and existing callers' five remain unchanged. Cumulative native-call,
allocation and deadline limits are unchanged. An eighth acquisition is refused.

Validation: **68 passed**,
`software/runs/absolute-wrist-child-composition-20260914.xml`, covering child
composition/refusal/replay, native execution and endpoint fault outcomes,
isolated package audit, metadata parsing and resource limits. These are fixture
and fake-connection tests, not physical movement or stop verification.

Next: bounded absolute result encoding and independent parent reconstruction,
then guarded CLI/supervisor integration and wizard review/run/export controls.
Native multi-leg campaigns and unattended qualification are still incomplete.

### Timed absolute preparation and reserved prelaunch — 2026-09-14 UTC

Added `prepare_absolute_wrist_worker`, an existing-key-only absolute review
loader, and `verify_reserved_absolute_wrist_entry`. Preparation reconstructs
controller identity/origin and runtime originals, verifies the domain-separated
signed review, requires 27 seconds remaining for the fixed supervisor budget,
and publishes exclusive review/launch records. It rejects clock regression.
Prelaunch rechecks the launch reservation, originals/source and signed review
before and after verification. Neither function opens serial or starts a child.

Validation: **40 passed**,
`software/runs/absolute-wrist-prelaunch-20260914-02.xml`. Tests cover valid staged
preparation, replay refusal, changed records/source, expiry, clock regression,
missing keys, existing-key-only derivation, and isolated package import audit.
The absolute bootstrap still rejects `execute-one`; no physical movement ran.

Next integration issue found by source inspection: the metadata acquirer currently
caps acquisitions at five, but the absolute latch performs additional checks
around durable publication. Before child composition, count the complete native
path and provide an explicitly bounded tested budget without weakening total
native-call, buffer or wall-clock limits. Then implement retained result encoding,
guarded child launch, owned supervision and public wizard controls. The finite
multi-leg and separate unattended release requirements remain incomplete.

### Absolute worker staging and original validation — 2026-09-14 UTC

Added immutable per-attempt staging, retained controller/protocol/runtime
originals, source/reference reconstruction, and fixed registration validation.
Registration checks the interpreter, child and archive bytes, exact arguments,
original hashes, execution budget, and outer request association. References
may be frozen only after reconstructing their retained originals; this is not
fresh USB identity evidence or physical qualification.

The first staging run exposed missing absolute-handoff parsing in
`OwnedWorkerRequest`. Added the exact schema validator without registering a
physical launch branch. The corrected staging/package/observational regression
run passed **23 tests** (`software/runs/absolute-wrist-staging-20260914-02.xml`).
Changed originals, archive, interpreter hash, arguments, budget and source are
rejected; duplicate staging does not overwrite an existing attempt.
An additional **63 tests passed** across handoff, native composition, worker
claims, serial admission and owned-trial boundaries
(`software/runs/absolute-wrist-staging-boundaries-20260914.xml`).

No hardware was accessed. Absolute `execute-one` remains disabled. Next:
timed preparation, verified prelaunch and retained-result composition, followed
by guarded wizard integration. Supervision is accepted as user-confirmed;
software validation must still precede release of this new command path.

### Isolated absolute package audit — 2026-09-14 UTC

`providers/windows/absolute_wrist_native_package.py` builds a deterministic
archive from the explicit shared dependency roster plus absolute modules; it
does not scan arbitrary workspace scripts. `_absolute_wrist_native_child.py`
checks isolated/no-site flags, exact archive filename, byte budget and digest
before importing that archive. Import audit disables native DLL loading,
subprocess creation, sockets and low-level opens. It reports no physical authority.

Validation: **25 passed**, `software/runs/absolute-wrist-package-20260914.xml`,
including a real isolated base-Python child, deterministic archive contents,
changed digest/bytes, incorrect filename/flags, and handoff regressions.
No hardware was accessed. The bootstrap currently accepts `check-imports` only
and explicitly rejects `execute-one`; it is not a live launcher yet.

Next: current-original reference reader, fixed registration and child prelaunch
validation must be composed before adding execute-one. Then connect the guarded
entry to owned supervision, retention and public wizard review/run controls.

### Closed absolute worker handoff — 2026-09-14 UTC

`providers/windows/absolute_wrist_native_protocol.py` defines the separate worker,
payload, request and result domains. The handoff binds the exact absolute intent,
attempt/session/unit, source, runtime-registration digest and identical parent/
child deadlines. No separate command override or extra approval flag is accepted.
It requires at least 27 seconds of intent lifetime for the fixed 25-second worker
and 2-second cleanup budget; this does not renew the original deadline.

Validation: **44 passed**, `software/runs/absolute-wrist-handoff-20260914.xml`,
including absolute wire checks, existing relative wire regression and absolute
worker claims. Rehashing a changed target/start does not bypass the operation
association. Tests reject substituted identity, worker domain, registration,
deadlines, relative roots, oversized input and extra command fields.

The inert test registration proves association only. Executable/archive pin
validation, isolated package/bootstrap and supervisor registration are still
outstanding; this decoder alone cannot authorize a launch. No device was opened.

### Process-bound absolute native composition — 2026-09-14 UTC

`providers/windows/absolute_wrist_trial_execution.py` now consumes the exact
source/runtime/process claim before creating the owned connection, checks the
exact permit/API association, and shares capture/reconstruction/cleanup with
the synthetic executor. A native-only adapter selects command bytes without
consuming them early: the serial facade consumes at the actual write boundary.
The public synthetic executor still rejects physical provenance.

Native execution revokes authority and closes the connection on terminal paths;
cleanup may be retried idempotently, but motion is never retried. Cancellation
before opening causes no open. Failure to consume the process claim cannot
reach connection callbacks. No wizard/CLI action has been registered yet.

Validation: **44 passed**, `software/runs/absolute-wrist-native-composition-20260914-02.xml`.
Tests replace connection methods with incapable fakes and forbid DLL loading.
They exercise the real authenticated latch, worker claim and shared executor,
including exact one-time native dispatch consumption, endpoint miss/excursion,
short writes, open/cleanup failures, cancellation, source mismatch and replay.
No physical hardware was accessed. Next: supervisor registration and pinned
worker protocol/package, original retention, then public wizard integration.

### Absolute worker ownership claims — 2026-09-14 UTC

`application/absolute_wrist_worker_claim.py` adds durable launch reservation,
exclusive process claiming, one-use claim consumption and parent receipt
association for the absolute intent domain. Records bind the exact request,
runtime original, review digest, source/runtime hashes and process ID. A failed
consumption burns that object; retained launch/claim records prevent automatic
restart or replay. Receipt verification can occur after execution expiry without
renewing launch permission. Storage association is not executable qualification.

Validation: **32 passed**, `software/runs/absolute-wrist-worker-claim-20260914.xml`,
covering new claims plus existing observational claims and absolute native-token
checks. A real isolated Python child created its claim and exited; its retained
claim was associated with its reported PID and rejected a subsequent claim.
Tests also reject changed hashes/originals, process mismatch, expired consumption
and incorrect parent receipt data. The child performed no device operations.

Remaining: compose these claims with the source-pinned supervisor registration,
absolute native connection/owned executor and complete original export. This
module neither launches a hardware worker nor adds a live wizard action.

### Exact absolute native facade, not launched — 2026-09-14 UTC

`safety/absolute_wrist_admission.py` adds a distinct typed permit adapting the
authenticated latch to open, baseline-selection and dispatch boundaries.
`providers/windows/absolute_wrist_serial_api.py` and
`absolute_wrist_serial_connection.py` reuse existing owned Win32 handle, token,
bounded read and cleanup logic. Dispatch consumes the exact selection immediately
before the native write boundary. Relative/measured/campaign permissions cannot
be substituted. The latch now rechecks remaining time after publishing its open
claim and supports separate token-preview versus dispatch-consumption calls.

Validation: **63 passed**, `software/runs/absolute-wrist-native-boundary-20260914.xml`.
Tests replace the kernel loader with an incapable fake before any API call.
They check exact bytes, one write, changed target/speed/command rejection, missing
baseline, stale/changed context, revocation, unadmitted construction, cross-domain
rejection, and existing endpoint/latch/owned-trial regressions. No Windows serial
device was opened and no live movement was sent.

These facades are dormant library components: no wizard or CLI launch route was
added. Native worker process/source/runtime claim composition is still required,
as is adapting owned execution without consuming the selection twice. Keep the
synthetic runner's native-provenance rejection until that exact composition is
implemented and tested. Native/physical acceptance is not complete.

### Owned absolute diagnostic pipeline — 2026-09-14 UTC

`application/absolute_wrist_owned_trial.py` integrates the signed request,
authenticated one-use latch, bounded baseline, exact selected write, five-second
post capture, unconditional cleanup attempt and independent endpoint review.
The caller owns the synthetic connection and has claimed it before entering.
The runner accepts only SYNTHETIC_WIRE_REHEARSAL: native provenance is rejected
before any callback. Internal callbacks are not a public serial-command route.

Uncertain/short/exceptional writes retain post data without retry. Cancellation,
invalid telemetry, target misses, ownership/freshness errors and unclean cleanup
prevent successful classification; revoked bindings cannot reopen or resend.
Cleanup is attempted despite clock failure. Reports never claim physical stop,
physical movement verification, campaign advancement or replay authority.

Validation: **69 passed**, `software/runs/absolute-wrist-owned-20260914.xml`,
covering the integrated pipeline, capture/reconstruction/latch tests and existing
observational owned-trial regressions. Broader absolute/relative regression:
`software/runs/absolute-wrist-integrated-regression-20260914.xml`.
No hardware was accessed. Remaining work: typed native facade and isolated-worker
composition, public wizard controls and exported originals, then scoped attended
qualification. Automatic/unattended campaign release remains a separate gate.

### Absolute capture and endpoint reconstruction — 2026-09-14 UTC

`application/absolute_wrist_capture.py` supplies exact-type wrappers around the
existing paced, bounded collector and original-capture validator. The absolute
intent now exposes fixed collector budgets (16 KiB baseline, 64 KiB post,
one-second baseline, five-second post) without changing authenticated fields.

`application/absolute_wrist_result_review.py` reconstructs the fixed absolute
target from the approved draft plus original baseline, compares exact command
bytes and write accounting, validates capture hashes/coverage/deadlines and
cleanup timing, and runs the common endpoint engine. It records controller
endpoint evidence separately from physical truth or process authentication.
Incomplete envelopes remain diagnostics, not reconstructed successes. Short or
uncertain writes and unclean cleanup yield TRANSPORT_FAULT even at the target.

Validation: **94 passed**, `software/runs/absolute-wrist-reconstruction-20260914.xml`.
The new tests run the actual shared collector with paced synthetic reads in both
directions. Cases include exact arrival, 0.87-degree miss, no response, target
departure, malformed interior feedback, other-joint change, mutated raw hashes,
coverage, payload, deadlines, write counts and cleanup. No hardware was opened.

Next remains the owned executor/native boundary and public wizard composition.
Result reconstruction cannot substitute for authenticated ownership or physical
qualification, and this checkpoint grants no campaign advancement authority.

### Absolute current-context and one-use selection — 2026-09-14 UTC

`providers/windows/absolute_wrist_current_context.py` reuses the persistent
controller resolver with a distinct absolute intent/context. Every boundary
re-reads the original authenticated bundle and compares identity, port, source
references and timestamps; metadata older than 100 ms is rejected.

`application/absolute_wrist_command_binding.py` reserves the attempt durably,
permits one open claim, validates a bounded owned raw baseline, retains its
original bytes/windows and exact target selection, and consumes dispatch once.
Each check verifies process ownership and saved original hashes. Dispatch
reservation precedes returned bytes; freshness is rechecked after publication.
Faults burn the latch; duplicate construction cannot reuse a reserved attempt.
The selected command bytes are data, not native serial permission. No existing
native facade accepts this type and none was changed by this work.

Validation: **112 passed**, `software/runs/absolute-wrist-binding-20260914-02.xml`.
Coverage includes synthetic metadata changes, altered original approval/selection,
concurrent consumption, stale baselines, storage delay/failure, corrupt or drifted
captures, process mismatch, cancellation and prior relative-path regressions.
The first run expected a generic file-exists exception; Windows correctly raised
the durability layer's CREATE_NEW error. The test now accepts that exact error
class without changing reservation behavior. Original report retained.

Remaining: exact native permit/facade and worker composition, complete-capture
result reconstruction, wizard preview/review/run/export integration, then bounded
attended qualification. No live movement or new unattended authority occurred.

### Absolute-target authentication checkpoint — 2026-09-14 UTC

`safety/absolute_wrist_review_authority.py` now authenticates a distinct
`AbsoluteWristIntent` containing the exact immutable draft, session/attempt,
USB identity, current source/runtime/protocol/controller references and bounded
11–30-second lifetime. Its start-budget check reserves at least 11 seconds.
The four explicit operator checks are retained; nothing defaults to approved.

`BenchReviewAuthority.for_absolute_wrist_diagnostic()` derives a separate key
domain without creating or changing host key storage. The absolute bundle has
its own schema and HMAC domain. Relative and absolute intents/bundles are not
interchangeable. Shared identity/reference/time validation was extracted without
changing the relative-policy allowlist. Changed targets, frozen starts, limits,
identity, references, attempt, timestamps or authenticated bytes are rejected.

Validation: **122 passed**, `software/runs/absolute-wrist-auth-20260914.xml`,
covering new authentication/draft tests and existing relative review, wizard run,
and campaign authority regressions. Tests use fixture keys and identities only.
Authentication still reports motion authority and physical-truth verification
false. No native facade accepts this type and no device was opened.

Next integration boundary: current-original revalidation and durable single-use
selection/dispatch binding for this exact type, followed by owned capture/result
reconstruction and the public wizard. Do not pass a review bundle directly to a
serial writer or interpret authentication as physical release.

### Absolute-target diagnostic draft — 2026-09-14 UTC

`motion/absolute_wrist_diagnostic.py` adds a distinct immutable single-command
draft with closed absolute targets (-4, 0, +4 degrees), explicit approach
direction and frozen six-joint expected start. It checks every current baseline
sample against the expected start, +/-10-degree envelope, and greater-than-0.5
through 5-degree displacement bounds; target remains fixed despite accepted
small baseline variation. Speed/acceleration stay 20/1; no retry or return.

Relative and absolute previews share `validated_wrist_baseline`, preserving
all-joint stability, timestamp/gap/age bounds and finite-value checks. The raw
capture entry point uses existing complete-frame analysis and rejects interior
corruption. Tests cover both approaches to each target, changed starts, stale
or conflicting samples, altered limits, exact immutable hashes and rejection
by the existing native observational intent. The first raw fixture lacked
required geometry fields and was correctly rejected; the fixture was corrected
without weakening the parser. Validation: **122 passed** in
`software/runs/absolute-wrist-draft-20260914-03.xml`; earlier reports retained.

The latest physical trial's retained baseline also produced a bounded +4-degree
absolute-target preview offline (negative approach). That historical capture is
not current-state evidence and the preview was not dispatched.

This completes draft selection only, not P1/P4 physical acceptance. The draft
cannot authorize native IO. Remaining integration must version and authenticate
the absolute target/start policy, bind it through the owned one-use command
latch and native byte matcher, reconstruct its endpoint from originals, and
show exact absolute targets in wizard review/run/export. Existing relative
intent semantics were not broadened. No new movement occurred in this work.

### Live status correction — 2026-09-14 UTC

The completed physical trial exposed misleading generic RUNNING text claiming
no hardware endpoint was opened. The observational action now explicitly says
the arm may open/move and software cancellation is not a physical stop. Other
generic actions defer device-activity claims to retained results rather than
claiming zero access. The existing incapable-coordinator lifecycle test inspects
the actual RUNNING operation before returning and checks this distinction.
The completed physical wizard session was stopped before source changes; no
new movement was sent. Validation report:
`software/runs/wizard-live-status-regression-20260914.xml`.

Read-only command-path investigation is recorded in the directional trace review.
The inspected PID/reset commands are not diagnostic getters. Same-target policy
integration remains outstanding; no absolute-target live authority was added.

### Attended physical endpoint trial — 2026-09-14 01:56 UTC

Following the operator's confirmation of attended supervision and shutdown
access, the fresh public wizard session correlated COM7, recorded powered setup,
staged the existing bounded observational policy, and executed exactly one
negative 5-degree wrist command at spd 20 / acc 1. This was not a campaign or an
unattended release. Operation: `operation-98a13adedc3d4e3fb08f7151df04f403`.

- Controller-reported start: 5.976563 degrees; absolute target: 0.976563 degrees.
- Final reported position: 1.845703 degrees; observed change: -4.130859 degrees.
- Final error: +0.869141 degrees; unchanged arrival tolerance: +/-0.5 degrees.
- 51 baseline and 280 post-command complete pose samples; five-second post window.
- Machine result: `TARGET_MISSED`; movement detected, target band never entered,
  no unexpected other-joint change reported. Automatic advancement remained false.
- One 63-byte command write, no write uncertainty, no retry or return. Worker
  exited and the connection lifecycle reported CLOSED. This is not proof of
  physical stopping or independently measured position/sample freshness.
- Visual outcome remains UNKNOWN; supervision confirmation is not an outcome report.

The wizard exported and verified originals at
`software/runs/wizard-exports/wizard-20260914T015705414159Z-b27c142d888e44d99ae0b524aff8a98f`.
Export operation: `operation-5bbc18f888b448cfa30a97db8fb55b6f`.
This adds evidence of the unresolved negative-direction shortfall. Do not loosen
tolerance, silently compensate, or advance into complex motions on this result.
Follow-up original-byte reconstruction found 203 identical final-angle reports
over at least 3.609 s; the final angle first appeared 1.297–1.313 s after write
completion. No complete-frame parsing/host-gap issues were found. See the
[directional trace review](WRIST_DIRECTIONAL_TRACE_REVIEW_20260913.md) for the
source hash and limitations. Extending the timeout alone is not supported as
the leading fix; installed configuration and same-target approach behavior
remain unresolved.

### Latest onboarding correction — 2026-09-14 UTC

The physical wizard metadata-only check correlated the connected controller on
COM7. Initial wrist-test staging failed with `POWERED_SETUP_REQUIRED`: the UI
had offered preparation before a current powered-startup record existed. After
recording the operator's supplied setup report, staging succeeded. No serial
open or movement action was executed in that session. The session was then
stopped for the following software correction; its staged runtime is not a
current launch context.

`arrival_wizard_service.py` now checks the existing powered-setup prerequisite
when rendering/validating the preparation action as well as at execution.
Missing, stale or uncorrelated setup is shown before accepting preparation;
the underlying freshness rule and movement authority are unchanged.
New incapable-backend tests cover the disabled and ready states and reject a
prepare ticket when setup is missing. Targeted onboarding/run/5-degree tests:
**28 passed**, `software/runs/observational-setup-preflight-20260914.xml`.
Broader wizard checks initially found the registry expectation missing the two
already-implemented no-hardware campaign actions. Added those exact IDs to the
expected set (no wildcard or weakened comparison). Rerun: **105 passed** in
`software/runs/observational-setup-wizard-regression-20260914-02.xml`; the original
one-failure report remains retained alongside it.

Next physical step: obtain the pending operator confirmation that power
shutdown is reachable from outside the movement area, then start a fresh wizard
session and rebuild its current metadata/setup/staging before one attended
bounded trial. Do not interpret automatic goal continuation as that confirmation.
Independent native campaign stop/containment qualification remains unresolved;
this UI correction does not release multi-leg or unattended operation.

Status: **implementation in progress; simulation slice available, native campaigns not released**.
Owner: robot-arm-build. Hardware: received RoArm-M3 Pro, USB controller,
supplied external power; static Arducam vision system for later independent
workcell verification. This document authorizes no motion by itself.

## 1. Objective and scope

Build a practical wizard-driven test runner that sends a finite set of reviewed
commands, reads new positions, verifies each endpoint, records evidence, and
advances without a separate user prompt for every successful move. Progress
from single-joint positioning to sequential joints and finally qualified
coordinated non-contact paths. Optimize reliability first, then throughput.

Success is not simply writing bytes or seeing movement: the exact requested
endpoint must be verified against current feedback under the selected policy.
Visual reports are supplementary evidence, not overrides for failed checks.

Deliver two distinct operating modes:

1. **Attended automatic testing:** operator reviews one finite campaign, starts
   it, remains nearby with shutdown reachable, and receives prompts only for
   exceptions or a new campaign. This is the first deliverable.
2. **Unattended testing:** no person needs to monitor the running campaign.
   This remains disabled until the separate safeguards in section 10 have
   actually been demonstrated. A standing statement that the area is clear
   cannot establish continuing clearance after the operator leaves.

"Operational compliance" in this plan means conformance to our reviewed
software and workcell policies. It does not claim regulatory certification,
safety-rated operation, or compliance with an industrial robot standard.

Out of initial scope: contact with a keyboard/phone, automatic PID/EEPROM writes,
firmware flashing, unbounded sweeps, autonomous overtravel compensation, and
silently widening tolerances to obtain passing results.

## 2. Baseline: what exists and what does not

Existing components to reuse:

- Wizard identity selection, powered setup, source/runtime binding and exports.
- Exact one-use observational admission and isolated native worker ownership.
- T101 single wrist command selected from a stable owned baseline; 1 or 5
  degrees, spd 20, acc 1, and a provisional +/-10-degree wrist envelope.
- One-second baseline and five-second post-command capture, raw bytes/hashes,
  host read bounds, bounded framing, 10 ms minimum read-start spacing and cleanup.
- Endpoint verifier separating movement, arrival and quiet settling: +/-0.5
  degrees arrival, <=0.1-degree reported span for >=200 ms quiet dwell.
- Reconstructed results and a wizard endpoint summary independent of visual
  approval. These thresholds are provisional diagnostics, not physical accuracy.

Current limitations:

- Exactly one command per admission; no multi-leg live authority or scheduler.
- Endpoint evaluation runs on completed captures, not a qualified live watchdog.
- Feedback freshness is host-observed; repeated packets do not prove new servo
  measurements. Installed firmware identity and stop semantics remain incomplete.
- No validated unattended clearance/interlock or safe power-loss behavior.
- Positive 5-degree tests ended approximately 0.25–0.34 degrees short; negative
  tests about 0.96 degrees short. The negative endpoint remained constant for
  several seconds. Directional positioning error is unresolved.

Reference records: [endpoint update](ENDPOINT_VERIFICATION_UPDATE.md),
[directional traces](WRIST_DIRECTIONAL_TRACE_REVIEW_20260913.md),
[command review](MOVEMENT_COMMAND_REVIEW.md), and
[movement testing guide](LIVE_MOVEMENT_TESTING_GOAL.md).

## 3. Architecture and data flow

```text
Wizard: finite plan + setup review + start
  -> immutable campaign specification + authenticated campaign approval
  -> single-owner campaign coordinator
  -> fresh per-leg context and baseline
  -> one-use leg permit -> native command submission
  -> bounded raw telemetry + incremental evidence checker
  -> complete-capture reanalysis + durable leg result
  -> continue only if current leg passes and next leg remains admitted
  -> campaign summary + verified export
```

Do not loop the existing wizard's run action or reuse its consumed permits.
Keep the existing single-command path available for diagnosis and regression.
Introduce an explicitly versioned campaign contract, not a bypass or generic
JSON command console. Browser input never contains executable callbacks,
arbitrary native commands, file paths to trusted reviews, or blanket approval.

### Campaign specification

Include campaign ID, unit identity, source/runtime/protocol/configuration hashes,
workcell/profile revision, allowed mode, expiry, ordered leg IDs, maximum number
of writes, total duration, data/storage budgets, permitted joints and envelopes,
speed/acceleration limits, expected start region, path constraints, target policy,
arrival/settling thresholds, per-leg timeout, fault policy and export destination.

Each leg records its exact absolute target in radians, command family, native
speed units, acceleration, intended moving joints, nonmoving-joint tolerances,
deadline, precursor leg digest and expected predecessor endpoint. Initial
relative proposals may compile to absolute targets only from the owned baseline.
Absolute targets are never accumulated from requested deltas when feedback differs.

One campaign approval may authorize its enumerated legs, but each native write
still requires a fresh one-use leg permit. A changed target, speed, identity,
software version, workcell or threshold invalidates the applicable approval.

## 4. Command / observe / verify state machine

States:

`DRAFT -> VALIDATED -> ARMED -> BASELINE -> COMMAND_PENDING -> OBSERVING
-> VERIFYING -> LEG_COMMITTED -> NEXT_LEG or COMPLETE`

Any active state may transition to `HELD`, `CANCELLED`, or `FAULTED`. These are
terminal for that campaign's command admission; no automatic resume/replay.

Per-leg procedure:

1. Recheck campaign expiry, operator mode, interlocks where present, exclusive
   ownership, exact controller, source/configuration, available storage and logs.
2. Acquire fresh stable feedback for all required joints. Compare against the
   last verified endpoint and permitted start region. Unexpected drift is a hold.
3. Check exact target and path/envelope before motion. Endpoint reachability
   alone is insufficient for collision clearance or coordinated motion.
4. Durably reserve the leg ID and command digest before native submission.
5. Submit exactly once. A short write, exception, timeout or lost acknowledgement
   is an uncertain outcome—not permission to resend.
6. Observe through a bounded acquisition loop. Track `AWAITING_RESPONSE`,
   `MOVEMENT_DETECTED`, `TARGET_BAND_ENTERED`, `SETTLING` and fault evidence.
   Start/arrival deadlines are fixed from dispatch, never renewed by feedback.
7. Initially retain the entire five-second window. Use the existing final
   verifier to recompute raw evidence independently of the live progress state.
8. Commit the result and its original hashes. Only a clean endpoint pass,
   valid context and durable result may make the next enumerated leg eligible.
9. At campaign end, hold the last accepted position; do not append a home/return
   move. Such a move must be an explicit independently checked plan leg.

Later efficiency optimization: allow early completion only after arrival plus
quiet dwell AND an additional fixed observation tail. Keep a maximum deadline,
and validate this against recorded full-window traces before enabling it live.
Do not shorten acquisition just to hide a later target departure.

## 5. Telemetry and endpoint correctness

Use one shared endpoint engine for online progress and offline reanalysis.
Retain original serial chunks, including invalid/partial data. Only documented
attachment fragments may be excluded from the analysis interval; never filter
interior faults to manufacture a pass. Keep byte offsets and host receipt bounds.

Add or verify:

- Monotonic timestamps, bounded gaps, missing joint fields, nonfinite values,
  duplicate/conflicting fields, malformed messages and source-unit association.
- First response, direction of travel, excursion/overshoot, final target error,
  quiet dwell and unexpected noncommanded-joint movement.
- Robust handling of zero-byte, very short and batched native reads; finite
  call/byte/CPU budgets remain sufficient for the entire approved duration.
- Clear distinction between serial write completion, controller-reported
  movement, endpoint evidence and independently measured physical performance.
- Device sequence/timestamps or motion-state feedback only if actually supported
  and validated. Missing fields remain unknown; never invent freshness.
- For stationary reports outside the target band: `TARGET_MISSED`, not settled.
  For quiet reports inside the band with clean evidence: `REPORTED_SETTLED`.

Changing any threshold creates a new profile revision and a stated engineering
reason. Existing failures remain failures under the profile used to execute them.

## 6. Progressive test ladder

All numbers below are proposed initial engineering caps, not device-certified
limits. Final compiled limits must be checked against actual source/protocol,
current pose, clearance and approved workcell profile.

### Stage A — offline fault and sequence tests

Implement the state machine and run against an incapable device backend before
native activation. Include successful legs, directional offsets observed in our
logs, quantization, delayed motion, oscillation, gaps and disconnects. No mock
success is recorded as physical qualification.

Acceptance: every failure case prevents the next write; old/reordered leg IDs
and mutated approvals cannot dispatch; complete results reproduce from originals.

### Stage B — one-joint endpoint characterization

Keep wrist-only, spd 20/acc 1 and +/-10-degree envelope initially. Add a reviewed
absolute-target profile alongside the existing relative-only policies.

Compare approaches to the SAME target from opposite sides, with starting points
at most 5 degrees away. Propose targets near neutral only after a fresh pose and
clearance check. Each repositioning is itself a plan leg, never hidden setup.

Begin with at most two legs per campaign. Since the negative direction currently
misses tolerance, expect a hold: do not use that failed arrival to advance into
another leg. Separate attended diagnostic trials can collect additional evidence
after a new admission and reviewed current state.

Read-only firmware/servo configuration inspection should determine available
position, commanded goal, motion state, deadband and load information. Do not
assume such queries exist, write settings, reset midpoint, or change PID.

Acceptance: explain or bound the discrepancy before certifying bidirectional
arrival. Seek at least three valid repetitions per approach/target cell without
faults, then ten consecutive successful legs within the proposed operating cell.
These are engineering release gates, not statistical reliability guarantees.

### Stage C — attended automatic wrist sequences

Start with two explicitly enumerated legs at a qualified speed/target pair.
Increase to four, then eight only after the prior batch passes cleanly. Proposed
first campaign ceiling: eight commands and 120 seconds, with a smaller initial
two-leg limit. No runtime route expansion or unattended repetition.

Verify every endpoint in software; no routine per-leg visual question. Prompt
for exceptions, contradictory evidence, new types of movement, or changed setup.

Acceptance: demonstrate pass -> next leg, miss -> no next write, feedback loss
-> terminal fault, and cancellation -> no queued motion. Inspect actual wire
logs to verify command counts and ordering, not just the UI's final status.

### Stage D — additional isolated joints

Add one joint at a time with an explicit joint mapping, absolute envelope,
small displacement and checked swept space. Do not copy wrist limits to base,
shoulder or elbow. Review the shoulder's coupled servos and gravity effects.
Retain all-joint feedback; only approved moving joints may change beyond tolerance.

Acceptance: direction, target arrival, settling and repeated behavior demonstrated
for each joint/profile. Any unexplained load/noise/position change blocks expansion.

### Stage E — sequential multi-joint poses

Combine previously qualified single-joint legs into short two-pose sequences,
with stop-and-verify at every intermediate pose. Validate the full arm and cable
swept volume. Start with two moving joints, sequentially, not simultaneously.

Acceptance: every intermediate pose passes, no unexpected joint movement, and
the sequence is repeatable under its frozen start, load and workcell conditions.

### Stage F — coordinated paths and speed characterization

Introduce synchronized joints or Cartesian paths only with separately verified
command-family semantics, path/IK limits, telemetry during movement, and stop
behavior. Existing reference concerns about blocking T104 telemetry remain open.
Do not assume endpoint interpolation is continuously observable.

Change one speed setting at a time; no preset faster ladder until native units
and observed timing are reconciled. Compare endpoint error, settling, overshoot,
latency and smoothness at identical routes and payload. Report unavailable metrics
as unavailable. Host-batched feedback cannot establish true velocity/jerk.

Acceptance: proposed faster profile performs within unchanged acceptance limits
over repeated trials. Keep slower validated settings as an explicit selectable
profile; do not automatically switch profiles during a failing movement.

### Stage G — board/vision and contact tasks

Integrate the static camera as independent position/workcell evidence after
mounting, focus, intrinsics, board transform and timestamp alignment are qualified.
Then validate non-contact board targets, approach heights and tool geometry.
Keyboard pressing and phone tapping require separate force/compliance, depth,
surface and fixture limits. A free-space pose pass does not qualify contact.

## 7. Fault handling and recovery

| Event | Required response |
|---|---|
| Target miss, no response, oscillation | Do not issue the next leg; retain evidence and hold campaign |
| Short/uncertain write or disconnect | Never retry/reconnect-and-resume automatically; state is uncertain |
| Stale/malformed/conflicting feedback | Stop future command admission; invoke only separately qualified stop mechanism |
| Unexpected joint motion or clearance fault | Terminal fault and qualified protective response; no automatic corrective move |
| User cancellation | Burn pending leg authority; clear host-owned queue; do not claim physical stop from cancellation |
| Log/disk failure | Admit no new leg; preserve bounded emergency diagnostics; uncertain result remains uncertain |
| Process/UI/network crash | Native/device watchdog response must be independently established; restart stays disarmed |
| Temperature/load/voltage issue | Use only validated available fields/limits; unknown safety-critical values block unattended release |

Closing serial, releasing torque, or removing power is not automatically a safe
stop: the arm may continue to a queued goal or drop under gravity. Never clear
a stop flag or energize/re-home automatically after a fault. Recovery requires
inspection, current-state reconciliation and a new campaign approval.

## 8. Wizard workflow and evidence

Screens: **Select profile -> Preview finite route -> Preflight -> Start campaign
-> Live leg status -> Results / exception review -> Export**.

Show exact unit, affected joints, absolute/relative targets, native speed units,
limits, current leg, remaining legs, capture health and clear endpoint results.
Distinguish Stop queued testing from a hardware E-stop. No browser reload, result
fetch, double-click or reconnect may create another command.

Each export should include campaign spec/approval, software and configuration
hashes, original command bytes and accounting, raw telemetry, parsing coverage,
per-leg transitions and host times, target/actual/error/dwell, sensor availability,
faults, cleanup, operator reports where supplied, and the final campaign decision.

Use the assigned workspace directory `software/runs/wizard-exports`, with a
separate campaign subdirectory and bounded storage budget. Verify hashes and
manifest before marking export complete. Export success is not motion success.

## 9. Implementation work packages and acceptance tests

### P1 — contracts, baseline tests and same-target diagnostic plan

- [ ] Inventory current endpoint, admission, capture and result code; retain
  the existing tests and recent hardware traces as regression fixtures.
- [x] Add immutable campaign/leg contracts with exact units, finite budgets,
  configuration revision, expiry and explicit start/target bounds.
  Evidence: `safety/positional_campaign_authority.py` defines the canonical
  two-leg intent, fixed 30-second lifetime, exact unit and configuration/evidence
  hashes, six-joint start, ordered targets and bounded command fields.
  `test_positional_campaign_authority.py` tests expiry, changed references,
  duplicate legs, non-finite input and signed-byte mutation. This completes the
  software contract only; no native campaign executor accepts it yet.
- [x] Add absolute-target wrist policy and opposite-approach test compilation.
  Evidence: `motion/absolute_wrist_diagnostic.py`, `motion/positional_campaign.py`,
  absolute native trials and `test_opposite_approaches_include_repositioning_to_same_absolute_target`.
  Compilation does not establish physical opposite-approach completion.
- [ ] Validate duplicate targets/IDs, invalid numbers, joint limits and path holds.
- [ ] Complete a focused directional-shortfall diagnostic; do not add compensation.

### P2 — common endpoint engine and simulated sequencer

- [x] Refactor completed-capture verification into a bounded incremental engine,
  keeping identical offline reconstruction and conservative host-time semantics.
- [x] Add finite sequencer states, per-leg persistence, no replay and failure holds.
  Evidence: simulated campaign/reconstruction, durable campaign journal and tests
  for interrupted commits, concurrent reservations and process-exit recovery.
  This P2 item is simulation software; P3 native lifecycle remains incomplete.
- [x] Simulate successful two-leg/eight-leg runs, target departure after arrival,
  quiet but wrong endpoint, reversed direction, delayed response and offsets.
- [x] Test byte/call limits, fragmented attachment, interior corruption, CPU stall,
  no samples, duplicate timestamps, missing joints and timestamp regression.
  Campaign-specific evidence reconciled on 2026-09-14:
  `test_positional_campaign_capture.py` checks both actual byte caps (16/48 KiB),
  late completion, cancellation before/during a read, and immediate empty/one-byte
  reads. Actual 10-ms pacing and the final guard constrain these to 95 baseline
  and 495 post reads, below the immutable 256/512 call caps without modifying
  runtime limits. `test_positional_owned_campaign.py` checks 23/37/61-byte
  fragmentation across capture boundaries, interior corruption on either leg,
  dispatch stalls and cancellation with no later write and exactly one close.
  `test_positional_campaign.py` checks no samples, batched identical timestamps,
  missing joints, time regression and CPU stall; reconstruction tests verify
  retained results. The combined five-file run (including frame-boundary tests)
  passed 135 tests, retained in
  `software/runs/campaign-capture-qualification-20260914.xml`.
  This completes P2's simulated capture coverage, not native process or physical
  stop qualification. Python callbacks cannot preempt a blocked native read.
- [x] Assert exact simulated write count/order; no later simulated command after any failed leg.

### P3 — native ownership, durable per-leg authority and stop qualification

Stop measurement reconstruction checkpoint (2026-09-14):
`application/positional_stop_reconstruction.py` recomputes sampled angular
stationarity and maximum residual angular displacement from bounded retained
independent sensor/video records. It requires an explicit stationarity band,
observation span, maximum sample gap, common measurement clock, exact fault-time
sample and pre-fault sample. A linear suffix-range calculation rejects apparent
early settling followed by later motion. Original digest, fault and scope must
match each claimed trial; missing/reused/unassociated originals are rejected.
Results distinguish original consistency from authentication/calibration and
physical stopping. No Cartesian safety or between-sample behavior is inferred.
Nine targeted tests pass; all records are synthetic fixtures. Wizard roster: 72
files. Next: original-backed engineering review and scoped release integration;
actual independent measurements and physical qualification remain outstanding.

Measured stop assessment checkpoint (2026-09-14):
`application/positional_stop_assessment.py` defines bounded physical observation
records scoped to USB unit, protocol/source/configuration, workcell, tool and
exact campaign legs. It calculates response times and compares residual motion
against explicitly supplied engineering limits; no universal safe threshold is
invented. Coverage includes operator stop, feedback loss, USB loss and host loss,
with independent protective response required for the latter two. Missing timing,
measurement-original references, terminal observations or gravity/load review,
and any failed repeat remain held. Complete records are only ready for engineering
review: originals, reviewer identity, physical stop and release remain unverified.
Fifteen synthetic-record tests pass; no physical fault test was performed. This
assessment is not yet a qualification certificate or a dispatch gate. Next:
reconstruct measurement originals and add explicit scoped engineering review,
then connect qualified evidence to native release. Wizard test roster: 71 files.

Prelaunch reservation checkpoint (2026-09-14):
`providers/windows/positional_campaign_prelaunch.py` connects the authenticated
reader bootstrap to the immutable launch reservation. It checks unclaimed state
before and after review/metadata/launch association, cancellation, and remaining
start budget. It does not consume the attempt: the child's atomic claim remains
required to handle a race after prelaunch returns. Tests cover valid unclaimed
reservation, already claimed state, modified launch/review/digest, cancellation,
and a claim occurring during verification. The isolated archive includes this
module, and the wizard roster now has 70 files. Physical-evidence semantic
qualification and composed supervisor/child dispatch remain unfinished; no
execution mode was enabled by this checkpoint.

Authenticated reader bootstrap checkpoint (2026-09-14):
`providers/windows/positional_campaign_bootstrap.py` reconstructs/freeze-checks
the retained originals, matches the runtime original to the wire, decodes the
reviewed controller, derives campaign authority from the existing protected host
key, constructs bounded metadata acquisition, and verifies the signed review
against fresh resolved controller metadata. Cancellation and remaining start
budget are checked before expensive stages. It creates no process/serial claim
and opens no serial port. Tests use real reference/signature/binding logic with
incapable metadata and reject signature, identity, original, expiry and
cancellation failures. Isolated import audit includes the bootstrap. Test roster:
69 files. Semantic qualification of physical evidence, prelaunch reservation
association and final execution wiring remain separate unfinished gates.

Supervisor codec checkpoint (2026-09-14):
`OwnedWorkerRequest` now accepts the exact campaign handoff format without
enabling execution. `providers/windows/positional_campaign_process_codec.py`
maps the reviewed intent to the actual supervisor wire and round-trips it through
the campaign decoder. It preserves intent SHA as operation identity (not the
single-trial payload hash), exact deadline, selected USB identity, and runtime
registration. Tests reject changed operation/deadline/registration and prove
the unregistered native path is held before authorizer/backend creation.
The wizard roster now contains 68 files. The remaining prelaunch/host bootstrap
must be composed before enabling the supervisor's campaign execution branch.

Parent runtime checkpoint (2026-09-14):
`providers/windows/positional_campaign_native_registration.py` now validates an
exact supervisor registration against the sealed campaign wire, fixed host
interpreter/entry, bounded current file bytes, fixed invocation/budget, and
freshly reconstructed source archive. A rehashed replacement archive is rejected
even when the replacement digest is copied into the wire. This is read-only
parent validation; it does not register an execution branch or authenticate the
physical review. Nine targeted tests pass. The wizard roster now has 67 files.
Next: construct/authenticate host bootstrap evidence and connect parent validation
to owned process preparation/supervision; the child execution mode stays disabled
until those gates are composed.

Invocation association checkpoint (2026-09-14):
`providers/windows/positional_campaign_invocation.py` compares observed child
entry/interpreter/argv/working directory with the reviewed registration,
requires the fixed campaign process budget and schemas, and rechecks bounded
executable, entry, archive, controller and protocol bytes. The process owner's
existing eight-pin maximum remains unchanged; the other reviewed evidence
originals belong to the dedicated reference reader, not extra package pins.
The checker is included in the isolated archive/import audit. It does not
authenticate a caller-provided runtime by itself: parent source/archive
validation and signed review verification remain separate bootstrap gates.
The child still rejects execute-campaign; no live launch was added. Test roster:
66 files. Next: parent runtime registration validation and host bootstrap.

Host-owned reference checkpoint (2026-09-14):
`application/positional_campaign_reference_reader.py` reconstructs all nine
campaign references: current source fingerprint and eight fixed-path retained
originals (runtime, protocol, controller, configuration, workcell, tool/payload,
stop qualification, owned baseline). Bounded regular-file reads reject missing,
changed, or non-structured originals. The frozen startup snapshot double-checks
references during construction and avoids repeated full-workspace hashing in
each motion leg. It is explicitly historical, not fresh device/clearance proof.
The module is included in the isolated import audit; the wizard roster now has
65 files. Semantic validation of these records and pinned invocation verification
remain necessary in the bootstrap before calling the existing child composition.

Isolated packaging checkpoint (2026-09-14):
`providers/windows/positional_campaign_native_package.py` produces an immutable,
deterministic archive from an explicit dependency roster. Its isolated `-I -S`
child imports the real campaign composition, protocol, review and retention
modules with native-library, process and network access disabled during audit.
The first actual interpreter test exposed a missing shared dependency; using
the existing observational shared roster resolved it. Seven package tests pass,
including altered bytes/digest, wrong filename/flags, and denied execution mode.
No hardware execution mode is registered by this checkpoint. The remaining
bootstrap must construct host-owned references/reader and verify actual pinned
invocation before delegating to the private composition. The fixed wizard test
roster now contains 64 files.

Registered-suite integration evidence:
`software/runs/campaign-package-registered-suite-20260914.json` records 816
passing tests across the actual 64-file wizard roster, 133.375 seconds total
(below the 180-second diagnostic budget), and zero hardware commands/opens.
This invoked the worker directly, not the outer browser/process timeout path.

Child composition checkpoint (2026-09-14):
`providers/windows/positional_campaign_child_execution.py` now connects the
decoded request and internally authenticated reader to durable process claim,
admission, native facade, one owned connection, two-leg collector/verifier,
cleanup, and compact retained-result receipt. No caller-selected serial factory
is accepted. Root and intent must match the reader; cancellation before claim
does not access a device. A failed result export cannot replay consumed claims.
This private composition is not an executable bootstrap or live wizard route.
Tests use the actual composition with an incapable streamed kernel, covering
completion, missed endpoint, cancellation, invalid preparation, replay, and
retention failure after cleanup. The test roster now contains 63 files.
Next remains host-owned reader construction, package/invocation verification,
owned child supervision, and wizard integration; physical release stays gated.

Portable native evidence checkpoint (2026-09-14):
`application/positional_campaign_native_export.py` can reproduce recorded
endpoint and process-record consistency from copied parent exports, without
opening a device or reading the original workspace. Parent exports now retain
launch and claim originals. A shared pure verifier checks their association
with the request and supervisor record. This proves internal consistency, not
independent process authenticity, physical stop behavior, or measured XYZ accuracy.
Eight portable-export tests pass (complete, missed-target, cancellation,
changed originals, false completion, path traversal, and missing originals).
Twenty-five process-original/retention regression tests also pass. Evidence:
`software/runs/campaign-portable-native-export-20260914.xml` and
`software/runs/campaign-process-originals-refactor-20260914.xml`.
The wizard test roster now includes 62 files. No live movement was sent.
Next: finish the isolated native campaign child and owned-process wiring, then
expose the bounded campaign in the wizard. Start with joint endpoint validation;
board/tool/camera calibration and independent measurements are required before
claiming that an XYZ destination has been physically achieved.

- [ ] Define campaign-owned process/serial lifecycle with finite aggregate budgets;
  do not inherit single-trial timing unchanged for a multi-minute campaign.
  Timing implementation checkpoint, 2026-09-14: the immutable two-leg intent now
  centralizes remaining-time checks for open (24 seconds: 4 open + 16 legs + 2
  serial cleanup + 2 handoff allowance), leg start (8 leg + 2 cleanup), and
  dispatch (1 write + 5 observation + 2 cleanup). No deadline is renewed. The
  owned synthetic executor checks the leg budget before baseline IO, retaining
  a hold/skipped-leg result and closing once when insufficient time remains.
  Consumption and post-reservation checks enforce dispatch cleanup reserve;
  the final no-storage dispatch check reserves the same eight seconds.
  Earlier baseline/freshness checks already constrained the normal path; the
  previous six-second dispatch check was a local inconsistency, not proof of
  an observed physical deadline violation.
  Exact-boundary, invalid-time and no-IO/one-close tests plus seven related
  suites passed 134 tests in
  `software/runs/campaign-lifecycle-budget-regression-20260914.xml`.
  Still incomplete: native process registration/package, serial lifecycle
  composition, native cancellation/parent cleanup, and original-bound aggregate
  result publication. No native campaign entry point was enabled by this work.
- [ ] Derive one-use leg permits from the approved immutable campaign; bind
  predecessor result, fresh baseline, exact unit and native dispatch boundary.
  Submission-boundary checkpoint, 2026-09-14: campaign admission now separates
  durable reservation (`DISPATCHED`) from one-use submission (`SUBMITTED`).
  `claim_submission` validates exact immutable bytes and current dispatch timing
  under the admission lock; a changed payload burns the leg, concurrent/repeated
  claims cannot both succeed, and `commit_endpoint` rejects an unsubmitted leg.
  The owned synthetic sequencer uses this boundary and rechecks cancellation
  before actual callback invocation. Cancellation after a claim retains the
  reservation but withholds that write and closes once. Successful two-leg
  progression still requires the first reconstructed endpoint before a second
  baseline/claim. Five related suites passed 112 tests in
  `software/runs/campaign-one-use-submission-regression-20260914.xml`.
  This is not the Win32 submission boundary: native handle/IO-token binding,
  native facade composition and observed completion remain required. Existing
  single-move facade guards were not changed or reset.
  Win32-facade checkpoint, 2026-09-14:
  `providers/windows/positional_campaign_serial_api.py` adds a separate dormant
  facade requiring the exact campaign intent, admission and one-use worker claim.
  It reuses owned-handle/read/cleanup checks but has its own maximum-two-write
  token path; no single-trial write flag is reset. Each write requires the owned
  port/event, fresh exact token/payload, no outstanding IO and a one-use submission
  claim after buffer allocation. Failed/short synchronous or asynchronous write
  completion holds later writes and preserves cleanup access. A fake-kernel
  two-leg test verifies the first endpoint before preparing the second command
  on the same connection. Negative tests exercise invalid handles/events/payloads,
  stale time, reused token state, short completion and pending-then-aborted IO.
  Six related suites passed 108 tests in
  `software/runs/campaign-native-facade-regression-20260914.xml`; the fixed wizard
  suite now includes 57 files. No Windows DLL/device was loaded by these tests.
  The facade is not registered with the wizard or process launcher. Still required:
  a campaign-owned serial connection/phase collector, native cancellation wiring,
  pinned child package, worker composition and release evidence. The existing
  synthetic callback executor must not preconsume the native facade's submission
  claim: the native composition must let the facade own that final boundary.
  Connection-owner checkpoint, 2026-09-14:
  `positional_campaign_serial_connection.py` now owns one port/two events across
  two enumerated legs, gates each `begin_leg` on admission's verified predecessor,
  and keeps per-leg plus aggregate read/write accounting without resetting any
  single-trial guard. Empty reads consume the leg call budget. It uses inherited
  bounded pending-IO cancellation and reverse-order cleanup, retaining late read
  bytes and correctly attributing late write bytes to the current leg. Facade
  construction now requires a cancellation Event, checked before native load and
  before/after submission claiming. Once cancellation is observed by the owner,
  clearing the Event does not rearm it. Five related suites passed 76 tests in
  `software/runs/campaign-connection-lifecycle-regression-20260914.xml` using only
  incapable fake kernels. The wizard boundary roster now contains 58 files.
  No live connection was opened. The existing conservative two-second open-setup
  check is inherited (within the campaign's four-second maximum); no timing is
  enlarged. Native worker/sequencer/result composition, package pinning and
  independent physical stop/clearance qualification remain incomplete.
  Streamed native-layer integration checkpoint, 2026-09-14:
  `test_positional_campaign_native_capture.py` composes the actual campaign
  collector, admission, Win32 facade and connection owner over an incapable
  timed-stream kernel. Both endpoints are derived from captured telemetry, not
  supplied verdicts. Whole packets and 23/37-byte fragments cross baseline/post
  and command boundaries without purging buffered tails. Per-leg lifecycle
  byte/call counters match collector originals. Misses on either leg hold later
  writes; cancellation after the first native-shaped write closes without a
  second. Five integration suites passed 75 tests in
  `software/runs/campaign-native-capture-integration-20260914.xml`; the wizard's
  fixed test roster now contains 59 files. This is an in-process test loop, not
  a registered native worker or a real arm trial. Production sequencer/child
  composition and parent-retained native results are still required.
  Production runner checkpoint, 2026-09-14:
  `providers/windows/positional_campaign_execution.py` now implements the finite
  native-layer sequence on the exact admitted unopened connection: open once,
  begin leg, capture/bind baseline, reserve, let the facade claim/write, capture
  and verify the endpoint, then advance only on success. It always revokes and
  attempts cleanup; attempted writes, capture originals, verification, skipped
  legs, lifecycle and cleanup are retained in the returned trial. Results use
  `NATIVE_PATH_UNQUALIFIED`, not synthetic or physically verified provenance.
  The streamed test harness now invokes this production runner instead of its
  own loop. Setup/read/uncertain-write failures and pre-open/post-write
  cancellation return diagnostic outcomes without retry; late write completion
  remains separate from an uncertain original write receipt. Five suites passed
  79 tests in `software/runs/campaign-production-runner-regression-20260914.xml`.
  All native calls were fake-kernel fixtures. No launcher/wizard route was enabled.
  Next: independently reconstruct this native result domain, retain it alongside
  the exact parent process receipt, package/pin the child and compose the gated
  application path. Parent termination and physical release evidence remain required.
  Native reconstruction checkpoint, 2026-09-14:
  `application/positional_campaign_native_review.py` independently checks fully
  evaluated native runner records, including whole/fragmented streams and held
  target misses. It reuses extracted common capture/endpoint/commit mathematics
  from `positional_campaign_reconstruction.py`; each entry point retains its
  own strict provenance envelope. Native records are not renamed synthetic.
  The native review additionally reconstructs exact per-leg/aggregate lifecycle
  counters, connection identity, write accounting and clean terminal state.
  Altered captures, verdicts, counters, cleanup times, provenance and success
  claims are rejected; incomplete/cancelled runs remain diagnostic-only.
  Five native/shared/legacy suites passed 98 tests in
  `software/runs/campaign-shared-reconstruction-regression-20260914.xml`.
  The wizard's fixed boundary-test roster includes 60 files. Process identity,
  authenticated review and independent physical accuracy remain separate and
  explicitly unverified by this data-only reconstruction. Next work is native
  original/result retention combined with the exact parent process receipt.
  Native retention checkpoint, 2026-09-14:
  `application/positional_campaign_native_retention.py` retains the full trial
  separately and emits a compact hash/size/claim receipt rather than duplicating
  capture trees into IPC. Parent retention stores immutable request/stdout/stderr,
  supervisor and trial originals with raw-byte hashes. Uniform base64 JSON
  wrappers preserve empty output too; initial tests caught the storage primitive's
  rejection of zero-length payloads and this was fixed without weakening it.
  The parent verifies claim/process association, reconstructs native data and
  checks that capture/cleanup timestamps fit the observed process lifetime.
  Endpoint completion requires both successful process completion and a complete
  reconstructed campaign; held, cancelled, altered and incomplete evidence stays
  diagnostic. Paths are campaign-derived, never supplied by child stdout.
  Four related suites passed 64 tests in
  `software/runs/campaign-native-parent-retention-regression-20260914.xml`.
  The fixed wizard test roster includes 61 files. All process/kernel fixtures
  were incapable; no live application path was enabled. Portable native-bundle
  verification, child package/registration and release gates remain to complete.
- [ ] Test concurrent requests, close/reopen, duplicate submission, source change,
  ambiguous write, process death and durable-reservation recovery.
  Owned-result export checkpoint, 2026-09-14:
  `application/positional_campaign_export.py` publishes immutable intent/result
  originals followed by a manifest in a new campaign-specific directory. The
  completed-result verifier is reused, not replaced. Fully evaluated held misses
  can reconstruct; cancelled, partial or inconsistent results remain diagnostic
  only, regardless of their saved status label. Missing/changed files fail export
  verification; copies verify without access to the source workspace. Duplicate
  publication cannot overwrite the first run. No record grants replay or motion.
  `test_positional_campaign_export.py` and owned/reconstruction regression suites
  passed 57 tests in `software/runs/owned-campaign-export-20260914.xml`.
  The new tests are included in the wizard's fixed boundary-test suite (53 files).
  This exporter currently accepts synthetic owned results only. Parent-owned
  native receipt association and partial native campaign publication are still
  required; this checkpoint is not physical release or finished P3.
  Native handoff checkpoint, 2026-09-14:
  `providers/windows/positional_campaign_native_protocol.py` defines a separate
  campaign request domain, binds campaign/session/unit/source/runtime hashes and
  both immutable deadlines, and permits no command override outside the reviewed
  two-leg intent. The aggregate process cap is 28 seconds plus 2 seconds cleanup,
  one process, 64-KiB input and 256-KiB receipt output; actual operation must also
  fit the intent's remaining lifetime. Large per-leg originals are not to be
  duplicated into IPC. Decoding is only byte association, not authenticated stop
  evidence or verification of a native runtime package. All-zero launch-reference
  rejection was added after its negative test exposed the missing check.
  Protocol/authority/wizard registration suites passed 63 tests in
  `software/runs/campaign-native-handoff-recheck-20260914.xml`; the fixed wizard
  test suite now includes 54 files. No launcher registration, executable entry,
  serial facade or hardware release was added. Next composition work must bind
  actual pinned runtime files and one-use launch claims before a native child
  can receive this handoff.
  Launch-accounting checkpoint, 2026-09-14:
  `application/positional_campaign_launch.py` now reserves the exact reviewed
  intent/runtime/current port and review digest before a process attempt; a
  separate immutable worker claim binds its PID. Claim consumption rechecks the
  signed review, current context, originals and remaining lifetime, and is burned
  even on failed checks. Concurrent claimants cannot both create the same record.
  It uses the existing authenticated campaign reader and publication primitives;
  it opens no serial port, launches no process and grants no leg permission.
  Runtime mismatch and stale context cannot produce a claim; original records
  remain available for review without overwrite/replay. Five related suites
  passed 87 tests in `software/runs/campaign-launch-authentication-regression-20260914.xml`.
  The fixed wizard boundary suite includes the claim tests (55 files total).
  Still required: pinned executable/package validation, parent receipt binding,
  native child/facade integration and hardware stop/clearance release evidence.
  Parent-receipt checkpoint, 2026-09-14:
  `verify_campaign_claim_receipt` in `positional_campaign_launch.py` binds exact
  parent request bytes and its typed process receipt to stored launch/claim
  hashes, campaign identity, PID and historical timestamps. Current device
  metadata is not queried after execution and expired review times are not
  renewed. Matching claim records are distinct from successful completion:
  cancellation, late finish, incomplete stdin, cleanup errors and unconfirmed
  process exit cannot report completion. Neither layer asserts authenticated
  review revalidation, claim consumption, serial cleanup, endpoint success or a
  physical stop. Those checks belong to the future composed parent/native result
  path, not to a child's self-reported status. Four related suites passed 63
  tests in `software/runs/campaign-parent-association-regression-20260914.xml`;
  the fixed wizard suite includes the receipt tests (56 files total). All receipt
  fixtures are synthetic. Native launch/package and serial integration remain open.
- [ ] Inspect official/installed stop behavior; establish safe response to host
  loss and already-issued servo goals. Keep unproven modes blocked.

### P4 — wizard integration and attended physical release

- [ ] Add finite campaign preview/start/status/cancel/result/export actions.
  - [x] Rehearsal preview/run/status/result/export via the actual HTTP wizard:
    operations `operation-a0546ea83046430396615b7cf41a4fe5` and
    `operation-10a65aed35ef481d9b201141ccccb983`; independently verified reports
    and journals in export `wizard-20260914T184912768551Z-b01a1331802f46c986a4710476d068f6`.
  - [ ] Native campaign ownership/dispatch and live cancel integration. Modeled
    cancellation and generic diagnostic cancellation do not complete this item.
- [ ] Verify browser double-click/reload/network loss cannot dispatch twice.
  Partial service-boundary proof: `test_wizard_positional_campaign.py` now
  submits the same campaign ticket concurrently and confirms one operation and
  one worker invocation. Repeated execute requests return the existing receipt
  (idempotency), including after cancellation; they intentionally do not raise
  an error. Public `stop_operation` delivers cancellation to the diagnostic
  runner in both wizard modes, and the cancelled result survives verified export.
  All 17 file tests passed in
  `software/runs/campaign-wizard-cancel-admission-recheck-20260914.xml`.
  Initial assertions incorrectly expected duplicate-ticket rejection; inspection
  confirmed the intended same-receipt contract and tests were corrected without
  changing production admission. These use an incapable blocked runner, not a
  native child or browser/network interruption. Native cancellation and retention
  of a partially completed campaign still need their own integration evidence.
- [x] Show machine endpoint status without requiring per-leg visual approval.
  Evidence: live absolute reports independently classified REPORTED_SETTLED and
  TARGET_MISSED, retained by the wizard without a post-move visual verdict.
  This does not remove pre-dispatch admission or qualify autonomous progression.
- [ ] Execute one physically observed diagnostic leg, then a qualified two-leg
  attended automatic campaign. Retain native evidence and inspect results.
- [ ] Increase through the test ladder only after the documented gates pass.

### P5 — optimization and unattended release review

- [ ] Analyze same-route repetitions by direction, target, load and speed;
  report count, failures, error distribution and settling variation honestly.
- [ ] Qualify shorter observation tails against full recordings before enabling.
- [ ] Complete section 10, then run a short unattended pilot only inside the
  independently safeguarded cell and within the frozen qualified profile.

Implementation order: P1 -> P2 -> P3 -> P4; P5 follows physical evidence.
Do not begin with a general motion editor, arbitrary script execution, or broad
UI redesign. Prioritize the smallest two-leg vertical slice and fault tests.

## 10. Separate unattended-operation release gate

All must be demonstrated, not assumed from visual success:

- [ ] Rigid mounting and validated arm/tool/cable swept-volume containment.
- [ ] Controlled access or protective separation that remains effective without
  the operator watching; a consumer camera alone is not a safety-rated interlock.
- [ ] Independent stop/watchdog behavior on controller, USB and host failures,
  including measured response and the consequences of gravity/power removal.
- [ ] Defined safe terminal condition after fault, completion and loss of power.
- [ ] Available thermal/electrical/load monitoring and conservative validated
  limits, or an explicit engineering justification for independent alternatives.
- [ ] Sufficient device-state/freshness evidence for the permitted unattended
  behavior; inability to distinguish stale data remains a documented blocker.
- [ ] No automatic rearming, homing, stop clearing, replay or firmware/config writes.
- [ ] Fault-injection and short attended campaign evidence cover the exact profile.
- [ ] Explicit unattended release record scoped to unit, workcell, tool, route,
  software/configuration and maximum campaign duration; change invalidates release.

Do not use a reminder/background scheduler as a substitute for this campaign
controller or these safeguards. Automatic scheduling is outside this plan.

## 11. Definition of done

**Attended automation complete:** the wizard runs a reviewed finite sequence,
verifies each endpoint without routine prompts, advances only on a clean result,
withholds all later writes on injected and real faults, and exports reproducible
records. At least a two-leg physical campaign demonstrates this end to end.

**Complex-motion release complete:** each added joint/path/speed cell has passed
its applicable test stage and carries its own validated limits and evidence.

**Unattended release complete:** section 10 is satisfied for a specific bounded
operating profile and a documented pilot has demonstrated its required behavior.
Software unit tests or successful USB writes alone cannot satisfy this release.

Update this file after each work package with changed files, test report paths,
physical attempt IDs, remaining holds and the next concrete test. Never mark
the entire plan complete when only the software or simulation phase is finished.

## 12. Implementation checkpoint — 2026-09-13

Implemented a usable simulation vertical slice, not native unattended testing:

- `motion/positional_campaign.py`: immutable canonical simulation-only contracts,
  1–8 ordered absolute wrist targets, fixed limits, predecessor/start bounds,
  explicit commands, and separate out/back and opposite-approach compilers.
  Opposite-approach compiles every repositioning and revisits the same zero
  target from both sides. No connected pose is inferred from synthetic zero.
- `application/positional_campaign_rehearsal.py`: bounded command/observe/verify
  sequence, original synthetic serial bytes and host bounds, per-leg chained
  digests, explicit skipped legs, deterministic report reconstruction and fault
  injection. It has NO native adapter or device-opening function.
- `arm/wrist_endpoint_verification.py`: constant-memory incremental monitor,
  shared with full-capture verification, finite row budget, sticky invalid data,
  and settling revoked on later departure. It is not yet a native streaming
  decoder/watchdog; the campaign replays synthetic parsed rows incrementally.
- Wizard action `positional_campaign_rehearse`: finite profile/length/fault
  selectors, plan-hash preview, worker execution, result panel and existing
  verified export integration. Available as simulation in either wizard mode.

Important partial boundaries: the pure simulator models reservations in memory;
wizard runs also publish durable rehearsal records (see below), not physical
permissions. P1's authenticated identity/configuration/expiry
contract and P3's native multi-leg ownership remain to implement. Existing live
single-command contracts were not widened. No native/unattended mode or arbitrary
command input is accepted by the new campaign schema or wizard action.

Fault cases include no response, oscillation, target departure, directional
offset, unexpected joint motion, overshoot, malformed/gapped/batched telemetry,
baseline drift, context change, uncertain write, cancellation, modeled persistence
failure and expiration. These are modeled faults; native crash/interlock/stop
qualification is still outstanding.

Additional closed cases now cover reversed direction, arrival too late to
establish quiet dwell, timestamp regression, a missing joint, no samples, and
host-read stalls. The wizard and engine fault catalogs are checked for equality.
These cases assert explicit machine reasons, not merely a generic failed run.

### Running-wizard proof and retained evidence

The real local HTTP prepare/execute/worker/result/export path was exercised in
rehearsal mode. No arm or camera device was opened and no physical commands were
sent. A successful diagnostic operation may contain a held campaign; both
statuses are deliberately preserved and shown separately.

| Operation | Synthetic case | Result |
| --- | --- | --- |
| `operation-af371e37835b42e0b10f4253ca7662af` | Two-leg out/back | Both endpoints verified; 2 simulated writes |
| `operation-8a13d1b935874e05853dc08b1d16aac1` | Four legs, directional offset at leg 2 | Held at leg 2; legs 3 and 4 skipped; 2 simulated writes |
| `operation-b2e96573134249d586915431ca0d80e6` | Eight-leg opposite approaches | All endpoints verified; 8 simulated writes |

Export operation: `operation-5be5baf698ff4e0986e58a8aea7f5801`.
Retained directory, relative to the workspace:
`software/runs/wizard-exports/wizard-20260913T230853754221Z-ac88328f856544a68defaa27b2e37609`.
The export manifest was independently verified using its resolved absolute path;
all three retained result attachments reproduced exactly through
`verify_rehearsal_report`. Hash verification is integrity evidence, not proof
that synthetic telemetry represents physical motion.

### Developer/operator rehearsal procedure

1. Launch the existing wizard in `--mode rehearsal`. In the Arm section choose
   **Rehearse automatic wrist testing (no hardware)**.
2. Select `OUT_AND_BACK`, 2 legs, `NONE`. Review the fixed absolute synthetic
   targets and plan hash, then execute. Expect `SIMULATION_COMPLETE` and zero
   physical writes. The synthetic starting pose is not the connected arm pose.
3. Select 4 legs with `DIRECTIONAL_OFFSET` injected at leg 2. Expect
   `SIMULATION_HELD`, endpoint `TARGET_MISSED`, and skipped legs 3 and 4.
4. Exercise the closed fault list and `OPPOSITE_APPROACH` with 4 or 8 legs.
   No corrective move, return, retry, or later leg should follow a failure.
5. Use **Export diagnostic report**. Results go to the configured workspace
   export folder and include original synthetic bytes and endpoint decisions.
   Do not import these results as native commissioning or clearance evidence.

Validation records:

- `software/runs/positional-campaign-regression-20260913-01.xml`: 379 passed;
  one Windows socket abort during an HTTP authentication test. No authentication
  check was weakened. Full UI rerun passed all 59 tests in
  `software/runs/positional-campaign-ui-rerun-20260913.xml`.
- `software/runs/positional-campaign-faults-20260913.xml`: 88 passed after the
  expanded synthetic fault set, before adding seven reason/catalog assertions.
- `software/runs/positional-campaign-regression-20260913-02.xml`: **399 passed**
  in 60.69 seconds, covering observational regression, incremental endpoint
  verification, the new campaign, wizard/export integration, existing campaign
  behavior and HTTP/UI checks, including the seven added assertions.
- JavaScript syntax check: `node --check` on `ui/static/app.js` passed.

The original failed report is retained alongside reruns for traceability.

### Native integration inventory for the next work package

- `application/observational_owned_trial.py` owns one baseline, one command,
  one post window and unconditional permit revocation/connection cleanup.
  It explicitly forbids campaign advance. Do not call it repeatedly as a
  shortcut to native multi-leg execution: it closes ownership after each trial.
- `application/observational_worker_claim.py` already supplies durable exclusive
  launch/claim records, source/runtime checks and process-bound one-use claims.
  Campaign ownership must preserve these properties without minting a new
  independent trial approval for every leg or weakening existing claims.
- `application/physical_onboarding_durability.py` provides bounded regular-file
  reads and exclusive reservation publication. Reuse these primitives for the
  new campaign journal rather than introducing an unrelated file-write mechanism.
- `application/mission_journal.py` is an existing zero-authority contact journal.
  Its restart semantics are useful reference; it is not a native campaign permit.
- `application/observational_capture.py` validates complete raw capture coverage;
  the incremental monitor does not replace that validation or prove controller
  sample freshness. Complete original-bound verification still gates advancement.

Next work must test durable reservation before possible dispatch, exact
predecessor-result binding, concurrent/duplicate claims, interrupted publication,
process death and no replay after recovery under a hardware-incapable executor.
The new simulation contract deliberately lacks native identity, authenticated
release and expiry fields; do not promote it into a live request by changing
`mode` or by accepting a browser-supplied authority flag.

Next implementation milestone: authenticated campaign/per-leg admission
and original-capture-bound final result commits, first under an incapable backend.
Only then extend native ownership and qualify a bounded attended two-leg run.
The unexplained directional miss and section 10 unattended gates remain open.

### Durable rehearsal execution checkpoint — 2026-09-13

`application/positional_campaign_journal.py` now supplies a hardware-incapable
durable execution journal integrated with the simulated sequencer and wizard
worker. This establishes persistence ordering without broadening native authority.

- Every wizard run gets a private directory under
  `software/runs/positional-campaign-journals`.
- Exclusive reservation, flush and readback precede each simulated write.
  Partial records are never removed or repaired automatically.
- Reservations bind the exact plan leg, original baseline digest and predecessor
  result digest. Successful results use immutable atomic publication and readback
  before advancement; an interrupted result cannot clear the prior reservation.
- Each subsequent operation rechecks all retained originals and the exact
  directory entry set. Changed predecessor data causes an irreversible hold.
- The creating process owns the object. Duplicate reservations and reopening a
  populated directory cannot resume or replay a run.
- Endpoint failure leaves an unresolved reservation. Publication exceptions
  abort the worker; files remain for read-only investigation, not automatic retry.
- Wizard results include original journal bytes in a separate step, carried by
  normal exports. Verification reconstructs the synthetic run and compares exact
  reservations/results, not only saved flags or self-consistent hashes.

`tests/unit/test_positional_campaign_journal.py` covers two/four/eight-leg runs,
concurrent duplicate reservation, failures before/after publication, changed
process ownership, changed predecessor data, and a real child-process exit after
reservation. Export tests reject missing/duplicated originals and altered records
even when the supplied hash is recomputed.

`software/runs/positional-campaign-journal-20260913.xml`: **112 passed**, covering
journal, campaign, incremental verification, wizard and export integration.

Remaining boundaries: these records are not authenticated native permits. There
is no native multi-leg backend or new stop/unattended release. The read-only
inspector reports file presence with `contents_verified=false`; use the
original-bound export verifier when a complete replayable result exists.
Neither grants recovery movement. P2/P3 remain partially complete.

### Authenticated attended contract checkpoint — 2026-09-13

`safety/positional_campaign_authority.py` adds an immutable, separately tagged
`PositionalCampaignIntent` and host review authenticator. This is not a native
permit and is deliberately incompatible with simulation and single-trial schemas.

The initial profile freezes exactly two absolute wrist targets, native `T101`
speed/acceleration fields, per-leg start bounds, six-joint initial feedback,
30-second lifetime, acquisition/cleanup/storage budgets, fail-without-retry
behavior and workspace export policy. Starting requires at least 24 seconds
remaining; changing these limits requires a separately reviewed profile.

Authenticated references cover source, runtime, protocol/controller review,
configuration, workcell, tool/payload, stop qualification and owned baseline.
Each is a required non-placeholder digest. Verification compares the exact
current identity and every reference, not only the saved plan hash. Explicit
operator checks are required; there are no default true reviews in production.

This module uses a distinct HMAC domain and requires a protected derived key;
the host authority now has a separate campaign key-derivation method, but the
wizard/native composition does not yet issue live campaign reviews.
Tests supply fixture keys and fixture evidence, not claims about the live arm.
Signatures prove association only: referenced originals and their physical
validity must still be checked before native admission. The return value always
reports `motion_authorized=false` and `physical_truth_verified=false`.

`software/runs/positional-campaign-authority-20260913.xml`: **22 passed**.
Tests reject expanded limits, wrong modes/identity, missing references, invalid
numbers, duplicate/out-of-order legs, changed signed content, missing reviews,
wrong keys, changed current evidence and expired/insufficient time budgets.

Next: connect protected host review/current-original verification to a
campaign-owned native admission boundary. Derive each one-use leg claim only
after fresh baseline validation and the committed predecessor check. Do not
reuse this review receipt directly as a serial-open or command token.

### Current-context binding checkpoint

`providers/windows/positional_current_context.py` reuses the established persistent
controller resolver without opening serial. It re-reads the signed campaign
review and obtains a fresh metadata snapshot at each check, enforcing exact
identity/port, current reference equality, the 100 ms metadata age bound and
campaign expiry. Duplicate/missing devices and changed originals are rejected.

`BenchReviewAuthority.for_positional_campaign()` derives a distinct campaign key
from the existing host authority. It does not initialize a new key, modify host
storage, or default any operator review. Unit tests use fixture keys only.

`software/runs/positional-context-admission-regression-20260913-02.xml` records
the campaign context/authentication tests alongside existing observational
context, review and one-command admission tests. No native dispatch composition
or attended/unattended release has been added by this checkpoint.

### Per-leg admission checkpoint

`safety/positional_campaign_admission.py` adds the separate authenticated campaign
state machine. It is not yet accepted by any native facade and opens no device.

- Factory admission requires the exact campaign intent and authenticated current
  reader. It retains an exclusive process-owned campaign record; reopening the
  same campaign cannot obtain another owner record.
- One open claim precedes baseline binding. Each leg requires a one-second clean
  stable six-joint capture, bounded displacement, agreement with both expected
  start and the preceding actual endpoint, and remaining campaign budget.
- Baseline originals are persisted before command eligibility. A distinct durable
  dispatch claim is consumed once; context and receipt recency are checked again
  after publication so storage latency cannot silently age a baseline.
- Result admission independently parses the full five-second post capture and
  runs the common endpoint verifier. Write uncertainty, timing errors or target
  misses remain held even when some position samples look plausible.
- Only a durably published, clean endpoint result enables the next enumerated
  leg. Retained predecessor originals are re-read at later boundaries. Completion
  and revocation cannot append a return/home movement or rearm the campaign.
- Raw-data limits apply both to baseline-plus-post bytes per leg and campaign
  totals. Host timestamps do not establish controller sample freshness.

`tests/unit/test_positional_campaign_admission.py` exercises the two-leg route,
duplicate/concurrent consumption, stale/drifted baselines, altered originals and
reviews, negative-direction shortfall, uncertain writes, storage failures after
reservation/dispatch/result publication, and irrevocable revocation. Tests use
synthetic wire captures and an explicitly controlled authenticated-reader clock;
the real metadata resolver/authentication path is tested separately.

Validation: `software/runs/positional-admission-regression-20260913-02.xml`.
Native execution remains unreleased: exact native facade tokens, worker lifecycle,
original stop/workcell evidence validation, cancellation/physical-stop behavior,
and public wizard campaign dispatch still require integration and qualification.
Do not pass returned command bytes to a serial shortcut or interpret an admission
state as unattended permission.

### Owned collector / sequence integration checkpoint

`application/positional_campaign_capture.py` now wraps the established bounded
read loop and original-capture validator with the exact campaign request domain.
Its limits partition the per-leg raw budget into 16 KiB baseline and 48 KiB post,
with fixed read-call caps, pacing, an end guard and reserved cleanup time.

`application/positional_owned_campaign.py` connects collection, authenticated
admission, one-use command selection, write accounting, post verification and
cleanup across both legs on one already-owned test connection. It currently
requires synthetic provenance; no native facade accepts the campaign admission
object. Internal callback adapters are not browser inputs or permission to use
serial directly, and a future native parent must enforce IO/process deadlines.

Integrated tests exposed and corrected two mismatches with the real collector:
the one-second guarded baseline can contain fewer than 20 frames, and collector
start can lag write completion. Admission now accepts at least 10 clean baseline
frames across the bounded capture (still requiring stability and coverage), and
post verification remains anchored to write completion, allowing at most 100 ms
start lag without extending the five-second deadline. A dedicated 30 ms delayed
start test verifies the original deadline and endpoint acceptance together.

Tests exercise the actual shared collector with paced synthetic reads rather
than only prebuilt captures. Faults cover malformed data, late reads, uncertain
or short writes, no response, cancellation, cleanup error and broken clocks.
Cleanup is attempted even when clock validation fails; serial closure is still
not claimed as a physical stop. Post originals are retained after uncertain writes.

Validation: `software/runs/positional-owned-campaign-regression-20260913.xml`.
Remaining release work is unchanged: native typed facade/worker composition,
stop/workcell original qualification, public native campaign UI and attended
evidence before any unattended release.

### Stop-path source finding — 2026-09-13

See [Positional stop source review](POSITIONAL_STOP_SOURCE_REVIEW_20260913.md).
The pinned official archive confirms a stop flag used by interpolation/mission
loops, but does not establish cancellation of an already-issued direct T101
wrist servo goal. Installed behavior remains unverified. Do not implement T0,
torque release, reset or USB closure as a presumed physically safe abort.

This changes the native release decision: a digest in `stop_qualification_sha256`
must not be accepted as sufficient proof by the future current-original reader.
It must validate the scoped qualification and failure-response evidence. Until
that exists, native campaign controls must remain held even if contract,
authentication, endpoint and simulation checks pass.

### Independent owned-result reconstruction checkpoint

Physical stop details remain missing, but the existing owned-connection
simulation can now verify its results independently before reporting completion.
`application/positional_campaign_reconstruction.py` recomputes validated capture
coverage, baseline stability, previous-endpoint agreement, timing/write accounting,
endpoint decisions, chained commit digests, skipped legs and terminal cleanup.
The actual dispatch-claim timestamp is now included in committed results, rather
than approximating it with the later host write timestamp.

The owned runner invokes reconstruction for fully evaluated results. Any mismatch
becomes `RECONSTRUCTION_FAILED`, not success. Incomplete, cancelled or unclean
captures remain diagnostics and cannot pass this completed-result verifier.
Reconstruction is integrity/consistency evidence, not authentication or proof of
physical accuracy/stop. Native and unattended authority remain false.

`software/runs/positional-reconstruction-regression-20260913.xml`: **193 passed**.
Tests cover successful and endpoint-held runs, uncertain writes, changed raw
bytes, endpoint flags, commit hashes, order, counts, dispatch times and cleanup.
The physical release question about independent cutoff and gravity containment
remains unanswered; this software progress does not resolve that requirement.

### Wizard-owned pipeline test action

The Arm section now includes **Test owned movement pipeline (no hardware)**,
action ID `positional_campaign_boundary_tests`. It executes eight fixed software
test files in the existing bounded worker; no browser-controlled paths, test
options, devices or native profiles are accepted. The result panel displays the
test output separately from hardware readiness. Normal diagnostic export retains
the suite output and source-owned target list, not the temporary test fixtures.

The real HTTP prepare/execute/subprocess/export path passed on 2026-09-13:

- Operation `operation-08c3a4c9f3cd4650bfcc417b2aa450b3`: **186 tests passed**
  in 8.50 seconds; worker reported zero device opens and motion commands.
- Export `operation-ddcfb862c5e24f86898b94a31d9c0775` verified at
  `software/runs/wizard-exports/wizard-20260913T234741334807Z-1d18ad27f76f4006b08e43fb10e106fc`.

This is a repeatable application-level software validation action, not a native
campaign launch button. Continue using the finite rehearsal action for synthetic
per-leg telemetry views and original journal exports. Native stop qualification
and physical release remain outstanding.

### Blocker checkpoint — physical stop strategy required

The full goal is **not complete**. Software simulation, admission, reconstruction
and the wizard software-test action are available, but native campaign worker/UI
dispatch, physical acceptance, optimization and unattended release remain open.

The same unresolved release condition has persisted across successive goal
continuations: no installed, qualified stop/cutoff and gravity-containment strategy
has been supplied. HZ-001/HZ-002 remain OPEN_BLOCKING. The reference source does
not establish a safe abort for an already-issued direct T101 target. Additional
passing simulations cannot choose the actual physical failure response.

Before continuing the native abort/release implementation, obtain a description
of the installed independent arm-power cutoff/E-stop, what power it interrupts,
and how the arm is contained or supported if torque is lost. If none is installed,
record that explicitly and select the hardware strategy before qualification.
Do not test power removal, infer approval, flash firmware or clear stops merely
to advance this checklist. Once that decision is available, resume the remaining
native work and bounded attended qualification; do not relabel this checkpoint
as completion of the entire plan.
