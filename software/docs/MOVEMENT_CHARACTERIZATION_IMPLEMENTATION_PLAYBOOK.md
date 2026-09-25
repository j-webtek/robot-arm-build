# Movement characterization implementation playbook

Date: 2026-09-12
Status: implementation active; no new motion authority or live test approval.
Parent: [Movement characterization plan](MOVEMENT_CHARACTERIZATION_PLAN.md).

## Objective and boundaries

Build a wizard-driven, finite, non-contact campaign that compares approved poses
and speed settings, retains telemetry and failures, and recommends settings only
when actual measurements support them. Implement and simulate first; qualify a
single slow movement before repeatability or multi-pose testing.

This playbook does not authorize an unrestricted sweep, homing, firmware changes,
servo configuration changes, torque release, keyboard presses or phone contact.
The final placemat, camera mount and tool calibration are separate commissioning
requirements. Do not bypass existing physical-motion holds to demonstrate progress.

## Historical starting point (before implementation)

- RoArm-M3 Pro, operator-reported firmware unchanged since delivery.
- ESP32 USB identity: VID/PID `10c4:ea60`, serial
  `52E4E1E8337FEF119E92181CEDD322A4`; last observed COM7. Rediscover by identity.
- Public wizard read-only capture succeeded: 56,384 bytes, 255 complete parsed
  pose samples, 323 timestamped reads, zero writes and verified export.
- The 256-record cap left 3,233 retained bytes unparsed. Full-window analysis
  is not yet established. Missing voltage and torque states remain unknown.
- Read completion gaps were 0/16/31 ms minimum/median/maximum. These are host
  read timings, not controller sample cadence or proof of sample freshness.
- No software-commanded movement has been qualified.

Current progress supersedes the historical parser limitation above: full-window
reanalysis is implemented and accounts for 270 complete poses, one rejected
line and an explicit 113-byte unterminated suffix. See the chronological
checkpoints below and MOVEMENT_FULL_WINDOW_REANALYSIS_20260912.md. No software-
commanded movement has yet been qualified by this campaign.

Evidence and exact export hashes: [Telemetry timing](MOVEMENT_TELEMETRY_TIMING.md).
Preserve previous failed attempts and successful originals without rewriting them.

## Existing code and integration responsibilities

Paths below are relative to `software/src/rocell`.

| Area | Existing code | Planned responsibility |
| --- | --- | --- |
| Framing | `arm/telemetry_stream.py` | Bounded, lossless coverage and explicit parsing limits |
| Baseline | `arm/telemetry_baseline.py` | Preserve untimed statistics; add separate timed analysis |
| Capture | `providers/windows/powered_telemetry_observation.py` | Timed reads and bounded capture ownership |
| Validation | `providers/windows/powered_telemetry_wire.py` | Reconstruct and verify capture summaries and timings |
| Native packaging | `providers/windows/powered_feedback_native_package.py` | Source-pinned dependencies and isolated import checks |
| Wizard | `application/arrival_wizard_service.py`, `wizard_actions.py` | Registered actions, preview, progress, evidence and export |
| Native coordinator | `application/wizard_powered_feedback_native_coordinator.py` | Retain existing read-only workflow unchanged in purpose |
| Motion API | `arm/roarm_m3.py`, `arm/serial_transport.py` | Preserve exact-goal permits and held live transport |
| Geometry | `motion/geometric_sim.py` | Reuse nominal tip/segment checks with explicit limitations |

The current geometric simulator does not solve IK or model complete links/cables.
A tip-path PASS must never become an assertion that the entire arm is collision-free.
New module names below are proposed; reuse an existing compatible abstraction
after inspection rather than introducing duplicate sources of truth.

## Phase 1 — Complete telemetry coverage

Deliverables: bounded full-window decoder, explicit coverage summary, saved-data
regressions and a timed-analysis input format.

1. Preserve existing compact capture and historical schema interpretation.
2. Separate retained bytes, decoded records and UI-displayed records. A display
   limit must not silently become an analysis limit.
3. Implement incremental full-window decoding with bounded memory and work.
   Prefer streaming summaries plus bounded display samples over retaining every
   expanded dictionary. Keep a hard byte/line/work budget, including hostile
   input consisting of many tiny lines. Do not simply remove all record limits.
4. Specify coverage fields: retained/processed bytes, complete/incomplete/rejected
   lines, unprocessed ranges, initial partial line, final partial line and reason.
5. Reconcile every byte exactly once. Resynchronize only at line boundaries;
   preserve malformed data rather than searching it for a convenient JSON object.
6. Associate each frame with its contributing read-window range. Report host-time
   bounds; do not assign artificial per-frame timestamps within a shared read.
7. Update collector, validator, package roster and fixtures together if wire
   semantics change. Use a new schema when semantics differ; no historical edits.
8. Reanalyze the saved successful capture without touching hardware. Record new
   results as derived evidence linked to the original hash, not a replacement.

Acceptance: all complete lines within the accepted window are accounted for, or
the analysis is explicitly INCOMPLETE. Maximum-size output still passes existing
IPC byte/node limits. No change to the zero-write boundary or capture authority.

## Phase 2 — Define a frozen finite campaign

Proposed pure module: `motion/characterization_plan.py`.

Each trial specifies ID/order, starting pose, target pose, coordinate frame,
command family, documented native speed/acceleration parameters, dwell, timeout,
repetitions, expected observed change and stop criteria. Campaign metadata binds
source/configuration hashes, USB identity, firmware review, tool/payload and the
geometry evidence used. Hash the canonical reviewed plan.

Require explicit limits for maximum trials, duration, displacement per move,
workspace/joint ranges and parameter ranges. Reject Boolean-as-number, nonfinite
values, duplicate IDs, ambiguous units, missing frames and unbounded repetition.
Synthetic examples may use arbitrary clearly labeled test values; live defaults
must not be inferred from those examples.

Review official Waveshare protocol and firmware sources before selecting live
command semantics. Document model applicability, units, interpolation behavior,
speed/acceleration meanings and stop behavior with source links and review date.
Retain unknown installed firmware version as unknown. Existing Cartesian T104
support is a candidate, not an instruction to enable it automatically.

Sequence: one small slow trial, a separately reviewed return, repeatability pair,
then a finite one-variable-at-a-time speed ladder and broader approved poses.
Plan edits invalidate prior review. No automatic search toward hardware limits.

Acceptance: deterministic plan/hash; identical inputs yield identical ordering;
all trials remain simulation-only until their live prerequisites are satisfied.

## Phase 3 — Simulate execution and failures

Proposed module: `motion/characterization_sim.py`, using existing replay transport
and scene/configuration abstractions where compatible.

1. Check frame compatibility, nominal reach/limits and modeled tip-path clearance.
2. Report full-link, cable, mount and self-collision checks as UNKNOWN unless
   actually modeled and supported by measured geometry. Unknown blocks live
   clearance qualification; it need not prevent a labeled offline simulation.
3. Generate deterministic synthetic telemetry for normal movement, delayed
   response, quantization, overshoot, drift, stale repeated values, dropped reads,
   malformed frames, truncated captures and missing optional fields.
4. Exercise start, monitoring, dwell, timeout, cancellation and fault handling.
5. Never infer dynamics or real travel time from an unvalidated speed coefficient.
   Label any response model and its parameters as synthetic assumptions.

Acceptance: simulation performs no device opens or native writes. Every failure
case prevents advancement to the next trial; no automatic home/return command.
Publish modeled checks and missing checks separately, not one misleading PASS.

## Phase 4 — Implement timed movement analysis

Proposed module: `arm/movement_analysis.py`; pure analysis of retained evidence.

Compute endpoint error, peak observed overshoot, repeatability spread and
host-observed settling intervals only when target, timing and coverage permit.
Define settling as entering and remaining within a configured tolerance for a
minimum dwell with sufficient sample coverage. A gap cannot count as evidence
that the arm stayed inside tolerance. A final sample alone is not settling.

Validate tolerance units and angle wrap behavior per joint. Treat missing fields
as unknown, not zero. Distinguish transport success, reported target convergence,
operator-observed movement and independently calibrated physical accuracy.
No-change telemetry after a command must not silently qualify motion freshness.

Reject optimization conclusions with insufficient repetitions, incomplete motion
coverage or differences below measurement uncertainty. Rank successful trials
only; still include every failed/aborted trial in the report. Do not interpret
raw load as calibrated force or recommend contact settings from free-space tests.

Acceptance: fixture trajectories have analytically expected metrics; missing,
stale and gapped data produce unavailable/uncertain results instead of fabricated
numbers. Results identify whether evidence is simulated, reanalyzed or physical.

## Phase 5 — Integrate the wizard and bounded executor

Wizard workflow: baseline review -> campaign preview -> simulation results ->
prerequisite review -> single-trial arming -> execution/monitoring -> operator
result -> analysis/export. Live stages remain disabled until implemented and tested.

Show exact target/delta, native parameter units, trial count, estimated data budget,
modeled/unknown clearance checks and outstanding prerequisites. Provide separate
states for simulated readiness and physical readiness. Browser input must select
registered operations and validated fields, never arbitrary JSON commands.

Implement a separate, narrowly scoped motion intent/executor; do not broaden the
fixed T105 query or zero-write telemetry intent. Bind the exact reviewed trial,
current source/identity, time-limited operator presence and clearance evidence to
one-use execution. Consume authority at the final outbound boundary.

Before a write, obtain and check baseline evidence in the same owned session and
recheck cancellation, deadlines and target bounds. USB open can itself trigger
startup movement. Do not equate recently received buffered values with a fresh
physical pose; record the uncertainty and require an adequate qualification basis.

Keep command and observation on the owned connection where practical. Define
bounded pre/post capture storage and sustained recording before lengthening live
trials: current 64 KiB/5-second capture is not an unlimited campaign logger.
Preserve raw data on all exits. Ambiguous write completion means no retry.

Stop cancels future dispatch; serial closure is not an emergency stop and may not
stop motion already accepted by the controller. Document a practical supplied-
power shutdown procedure, including possible loss of holding torque and arm fall.
If firmware supports a verified controlled stop, test and document it separately;
do not invent a stop command or silently substitute torque release.

Acceptance: stale/replayed/mutated intents, wrong identity, source changes,
double-clicks, concurrent requests, cancellation races and uncertain cleanup
cannot issue additional movement. Physical admission is tested with incapable
fakes before any real motion. Source files are not edited during owned hardware runs.

## Phase 6 — Stage actual qualification and optimize

1. Confirm current secured setup, supplied power, clear swept volume, operator
   attendance and reachable shutdown. Obtain any missing measured geometry.
2. Show and approve one exact small slow target; no broad sweep authorization
   substitutes for this initial qualification. Numeric settings require the
   protocol review and actual clearance, not guessed values in this document.
3. Execute once, collect telemetry and ask whether observed movement matched.
   Stop on disagreement, stale response, fault, timeout or uncertainty.
4. Only after qualification, run the frozen repeatability subset. Treat the
   return path as another checked trial, not cleanup.
5. Review results before each expansion of pose range or speed tier. Keep the
   operator present for all live testing; pause between tiers for inspection.
6. Recommend conservative settings only for the tested region, payload and
   parameter range. State untested regions and outstanding calibration needs.

Acceptance: actual finite campaign completes with retained originals and reviewed
results. If any stage fails, preserve its evidence and revise/reapprove the plan;
do not silently rerun it or claim optimization from simulated outcomes.

## Export and developer verification

Use `software/runs/wizard-exports` through the existing export mechanism. Bundle
the frozen plan/hash, source/configuration references, raw bytes and read windows,
command/write timing, parsed coverage, metrics, operator observations, failures,
cleanup results and readable summary. Verify manifests after export. Derived
reports reference originals by hash; historical evidence remains immutable.

Test groups:

- Framing: fragmented CRLF/LF, partial prefix/suffix, >256 valid records, tiny
  invalid lines, maximum byte capacity, record/work limits and exact coverage.
- Timing/metrics: split frames, shared reads, gaps, quantized/stale values,
  timeout, overshoot, angle wrapping, insufficient dwell and numeric overflow.
- Planner/simulator: bounds, units, frames, limits, deterministic hashes,
  unknown geometry, collision flags, finite trial count and no hardware access.
- Wizard/executor: preview invalidation, one-use admission, stop races, worker
  failures, disconnect, partial/uncertain write, resource closure and no retry.
- Export: round-trip reconstruction, hashes, failure retention, path handling
  and distinction between simulated and physical evidence.

Run focused regressions after each phase and the relevant broader suite before
live admission. Use fresh pytest basetemp directories; never reuse/delete saved
hardware evidence. Report any known unrelated failing tests rather than claiming
the entire suite is green. Perform a browser wizard smoke test before operator use.

## Work queue and handoff checklist

- [x] P1: Full-window bounded decoding and saved-capture reanalysis.
- [ ] P2: Canonical finite plan, parameter review and validation tests.
- [ ] P3: Deterministic simulator and fault scenarios.
- [ ] P4: Timed metrics and uncertainty/coverage tests.
- [ ] P5a: Wizard preview, simulated trial workflow and verified exports.
- [ ] P5b: Separately admitted bounded motion executor and boundary tests.
- [ ] P6a: One physically qualified slow movement and telemetry response.
- [ ] P6b: Approved repeatability subset and progressive pose/speed campaign.
- [ ] P6c: Evidence-backed settings report with applicability limits.

P1 evidence: [Full-window reanalysis](MOVEMENT_FULL_WINDOW_REANALYSIS_20260912.md).
New `arm/telemetry_coverage.py` processes complete retained lines independently
of display limits; shared decoding preserves the legacy live wire format.
50 focused tests passed. Saved-data reanalysis recovered 270 complete poses
(15 additional), with the final 113-byte suffix still explicit. No hardware I/O.
Wizard display of this derived summary remains P5a, not completed by P1.

### P2/P3 implementation checkpoint

Implemented `motion/characterization_plan.py`: immutable canonical bytes and
content hash; explicit start/target continuity, returns and repetition trials;
typed XYZ/angle envelopes, per-move displacement bounds, coefficient bounds,
finite trial/duration budgets and explicit stop/tolerance policies. No-op moves,
unsupported command fields (including T104 acceleration), nonfinite numbers,
ambiguous frames and implicit repetitions are rejected. Preview always reports
physical readiness false. Evidence hashes identify references, not approvals.

Implemented `motion/characterization_sim.py`: deterministic linear endpoint
sequencing with explicit synthetic travel time, bounded sample work, no-response,
stale, disconnect, cancellation, timeout and read-gap scenarios. Failure skips
later trials, including the return. Native speed coefficients are deliberately
not converted into modeled travel durations. No device access or motion authority.

Verification: 43 tests passed in the core planner/simulator/coverage run at
`software/runs/pytest-characterization-core-20260912-02`.

P2 remains unchecked: official firmware semantics review and actual usable
parameter selection are pending. P3 remains unchecked: integration with nominal
scene/path checks and additional overshoot/drift/malformed/dropout scenarios are
pending. Current simulation explicitly reports IK/link/cable/dynamics UNKNOWN;
MODEL_COMPLETED is only a sequencing result, not collision clearance or settling.

Next slices: timed movement metrics, richer fault fixtures and nominal geometry
integration, then wizard preview/export. P2-P4 and P5a
can continue while physical prerequisites are unavailable. Each handoff updates
this checklist with changed files, tests, evidence paths, limitations and the
next pending gate. Do not mark a physical milestone complete from offline tests.

### Timed analysis and wire-connected simulation checkpoint

Implemented `arm/movement_analysis.py`: original-byte parsing, explicit trial
lookup/hash, post-command host acquisition bounds, reported endpoint error,
directional observed XYZ overshoot and conservative settling-entry intervals.
It rejects settling evidence with no observed change, bad/incomplete frames,
capture suffixes, excessive read gaps, insufficient dwell or a later departure
from tolerance. Angles are unwrapped; no joint winding equivalence is invented.
Numeric-range problems produce unavailable metrics/issues, not NaN/Infinity.
Freshness, physical accuracy and motion authority remain unverified/false.

Implemented `motion/characterization_wire_sim.py`: bounded synthetic original
T1051 bytes plus read windows feed the real coverage/analysis modules. Synthetic
joint placeholders are labeled as such, not an IK solution. Original bytes,
hashes, timestamps and derived metrics are retained in the simulation result.
The simulator now requires its real analyzer's settling criterion before
advancing a successful modeled trial; an analysis failure prevents the return.

Added overshoot, drift, dropout and malformed-frame injection alongside prior
no-response, stale, disconnect, cancellation and timeout cases. All simulated
timing is explicitly idealized and is not a prediction of the real controller.
Trial wire capture is capped at 512 reads and 64 KiB; excessive models fail
explicitly instead of silently truncating successful evidence.

Verification: **56 passed in 0.89 seconds**, basetemp
`software/runs/pytest-movement-wire-20260912-02`, covering timed metrics,
wire-connected simulation, campaign planning and full-window coverage.
No physical capture or movement occurred during this increment.

Remaining P4: repeatability aggregation, uncertainty-aware comparison/settings
selection and integration of real execution evidence. Remaining P3: nominal
geometry integration and fuller trajectory/coverage cases. Neither stage is
marked complete based on this focused suite. Next substantial step is geometry
and wizard preview/export integration so operators can use these components.

### Wizard campaign integration checkpoint

Registered `movement_campaign_preview` and `movement_campaign_simulate` in the
Arm section, available in both modes but always simulation-only. Each uses an
editable, strictly validated JSON plan; the default is an explicitly synthetic
out-and-back example, not current robot pose or measured placemat geometry.
The ticket shows exact plan hash, targets, speed coefficients and timeouts.
The fixed worker runs only the pure planner/simulator, never serial or camera I/O.

Wizard input is bounded to 6000 plan characters, four trials and 20 modeled
seconds. Duplicate keys and unsupported/invalid fields fail before ticket
creation and are revalidated by the worker. Fixed synthetic timing is 0.5-second
travel and 0.05-second sampling; these are not recommended hardware settings.
The first-trial fault selector exercises the existing failure scenarios.

Existing full-result retention and Export logs now carry the frozen plan,
preview, synthetic wire originals/read windows, analysis and skipped-trial
results. An executed fault rehearsal can have a SUCCEEDED diagnostic envelope
while its modeled campaign is STOPPED; inspect the nested campaign status.
Neither status changes physical readiness.

Verification: **92 passed in 9.35 seconds**, basetemp
`software/runs/pytest-wizard-movement-regression-20260912-02`. This includes public
service preview/run/export/manifest verification in both modes, planner,
simulator, analysis and broader wizard service regressions. One pre-existing
metadata-inventory test was updated to the already implemented metadata-only
confirmation/input contract; no inventory runtime behavior was changed.
An actual diagnostic-worker subprocess also completed the default simulation
with zero device opens and zero motion commands. This was not a hardware trial.

Operator use: open the Arm section, choose Preview finite movement campaign,
review its synthetic JSON and effects, then use Simulate movement campaign with
the same JSON. Inspect nested simulation/analysis results and use Export logs.

P5a remains incomplete pending browser visual smoke testing and better dedicated
results presentation; nominal geometry checks and real-evidence selection are
also pending. No live executor or pose/speed sweep has been enabled.

### Nominal geometry integration checkpoint

Implemented `motion/characterization_geometry.py` using the existing
`load_rc03_nominal_scene` and `NominalWorkcellScene.check_segment_clearance`.
It does not duplicate placemat dimensions or obstacle geometry. No obstacles
are ignored for these non-contact trials. Each checked endpoint segment is
transformed explicitly into board coordinates.

Campaigns now preserve either explicit `R_ctrl` or `robot_base` frame labels;
these are distinct, not aliases. The default synthetic wizard example uses
`R_ctrl`, consistent with the existing controller simulation's frame label.
Existing robot_base plans keep their original frame and canonical meaning.
No inferred map between controller, URDF/model and board frames was introduced.

The wizard accepts a 16-value row-major rigid board transform, or `null` for
unavailable mapping, and an explicit nominal tip-clearance margin. The result
hash binds the complete imported nominal scene, transform and margin. A changed
transform/source/margin invalidates the plan's geometry reference. Reference
hashes are still not physical calibration or review authority.

When the transform is missing, the report provides board dimensions, obstacle
count and source hashes but says TRANSFORM_REQUIRED without checking points in
the wrong frame. A detected collision stops simulated sequencing before that
trial, with no automatic return. Clear bound segments are labeled
NOMINAL_TIP_PATH_CLEAR_ONLY. Full links, cables, IK and actual controller path
remain unqualified; the existing deeper controller/collision models still need
explicit integration and validated frame/pose bindings.

Verification: **44 passed in 1.51 seconds**, basetemp
`software/runs/pytest-campaign-geometry-20260912-02`. Coverage includes actual
nominal source import, missing/wrong transform, geometry hash invalidation,
collision detection, blocked sequencing, wizard export and campaign regressions.
The tests use synthetic transforms and do not establish actual hardware clearance.

Next: browser-level verification and clearer result presentation, plus connecting
the existing controller model and firmware review to meaningful pose/speed trials.
No new hardware capture or motion occurred in this increment.

### Browser workflow verification and readable results

Using the computer/browser automation workflow, opened a fresh loopback rehearsal
wizard, navigated Arm -> Simulate movement campaign -> Preview -> Execute,
observed SUCCEEDED, loaded its full result and exported diagnostics through the
browser. Export reported verified and separate disk verification passed:
`software/runs/wizard-exports/wizard-20260912T235758050903Z-7c8ec09a9443457990148d229b98dde0`.
Original UI smoke session: `wizard-8d898d0eb90a4c9b88dbd2e30a99a5da`.
This was actual application execution with synthetic data, not hardware motion.

The visual check exposed raw-JSON-only results. Added `appendMovementCampaignResult`
to `ui/static/app.js`: compact plan/frame/geometry/outcome summary plus trial
endpoint-error/overshoot/settling/issues table, skipped-trial notice and persistent
NOT QUALIFIED guidance. Raw original results remain expandable and exportable.
Schema/basis/authority inconsistencies withhold the metric presentation. Full-result
loading now verifies action and operation IDs for every action, not just the
camera assessment. Rendering uses text nodes, not input-derived HTML.

Restarted the temporary rehearsal server to load its startup-cached static assets,
ran another synthetic campaign through the browser and visually verified the new
table, TRANSFORM_REQUIRED, NOT QUALIFIED and synthetic-only settling labels.
Both temporary servers were stopped after their operations had completed. Saved
logs/exports were preserved; no device was opened or commanded.

Verification: Node syntax check passed; **10 renderer/public-wizard tests passed
in 1.45 seconds**, basetemp `software/runs/pytest-movement-ui-20260913-01`.
The renderer tests execute the actual JavaScript function in an inert DOM and
cover success, disconnect/skipped return, missing metrics and inconsistent data.

P5a has a browser-verified synthetic preview/run/result/export path. Remaining
work is not waived: retained physical-evidence selection/full-window presentation,
deeper controller/path integration, campaign aggregation, and the separately
admitted live executor and staged qualification remain pending.

### Existing controller-model integration — 2026-09-13

Added `motion/characterization_controller.py` and joined it to both campaign
wizard actions. This reuses `simulation/controller.py`, not a second firmware
equation implementation. Only explicitly labeled `R_ctrl` plans are modeled;
`robot_base` is not silently treated as the same frame.

The preview retains the existing T104 cosine interpolation, its mixed mm/rad
delta and its separate gripper behavior. Each trial records its sample count
and first/middle/last modeled landmarks. Work is bounded to 512 samples per
trial and 4096 per campaign. Excessive traces are explicitly unavailable,
not truncated into a successful result. Gripper target changes are identified
as distinct from Cartesian easing.

No elapsed time is assigned to these interpolation samples. Duration remains
null; installed firmware identity and physical readiness remain unverified.
The separate linear wire rehearsal continues to exercise analysis/failure
handling using declared synthetic timing. Neither model recommends a hardware
speed. The wizard summary now names the controller-model status, checks its
plan-hash binding and explains this distinction; full details remain in exports.

Verification before the summary addition: **20 passed in 1.67 seconds**,
`software/runs/pytest-controller-campaign-20260913-02`, covering controller math,
campaign integration, public wizard behavior and existing renderer tests.
After the summary addition: **21 passed in 1.85 seconds**,
`software/runs/pytest-controller-summary-20260913-01`; Node syntax check passed.
This includes rejecting a mismatched controller-model plan hash in the summary.
These are focused regression checks, not a full-suite or live-hardware claim.

Next priorities remain: reference firmware/stop-semantics review, retained
physical-evidence selection, repeatability/uncertainty comparison, and a
separate narrowly admitted executor before any first live move. No serial port
was opened and no physical motion was commanded in this increment.

### Reference firmware review and executor constraint — 2026-09-13

Inspected the official firmware archive in memory and reproduced its pinned
SHA-256. The detailed source locations and findings are in
[Movement command review](MOVEMENT_COMMAND_REVIEW.md#pinned-reference-source-inspection--2026-09-13).
T104 blocks normal feedback refresh in that reference. Its independent serial
StopFlag path exits interpolation but does not establish servo hold, measured
stop latency or physical rest. This changes executor design: a continuously
observed T104 sweep cannot be presumed workable from existing captures.

Controller previews now export these reference observation/stop limitations.
No settings were recommended, no firmware was changed and no live permission
was granted. Before live admission, explicitly select and qualify the observation
contract: supervised bounded endpoint-only T104, a separately reviewed command
family, or independently qualified external observation. Retain the full campaign
objective; do not convert missing in-motion evidence into successful metrics.

Verification: **15 focused tests passed in 1.81 seconds**,
`software/runs/pytest-reference-review-20260913-01`, covering controller reference
labels, wizard reports/export and summary rendering. The same reference warning
is also displayed directly in the wizard movement summary.

### Campaign repeatability and host timing comparison — 2026-09-13

Implemented `arm/movement_campaign_analysis.py` and integrated it with simulated
wizard runs and retained exports. Each supplied original is length/hash checked
and decoded again through the timed analyzer; cached analysis cannot override
wire evidence. Maximum input is one observation per planned trial (128 total),
each constrained to the existing 64 KiB/read-window bounds. Missing trials,
failed outcomes and insufficient coverage remain visible and are not zero-valued
measurements. Reused physical capture bytes cannot count as independent repeats.

Comparison groups require identical starting/target poses, command family,
coefficient, dwell, timeout and stop policy, within the same frozen plan and
evidence basis. Different approach directions or policies are not pooled.
Reported endpoint spread is the maximum pairwise XYZ distance; angular spread
uses unwrapped values. One eligible endpoint produces unavailable spread, not
zero. Three eligible repetitions are required by default for a descriptive
median host-settling interval; a configurable larger threshold is supported.

Only otherwise-identical route groups at different coefficients are compared.
Overlapping/touching host bounds are explicitly unresolved. Disjoint median
host bounds are described, not converted into a physical speed ranking or
recommendation: these intervals are descriptive order statistics, NOT confidence
intervals, and unknown USB/device latency remains outside them. Synthetic timing
does not depend on coefficient. All reports retain null recommended settings
and no authority. A qualified physical recommendation policy still remains work.

Wizard summary now shows eligible repeat counts and insufficiency. Its default
out/back example is intentionally not enough repeated trials to qualify even a
descriptive comparison. General analysis supports larger finite plans while the
wizard rehearsal remains capped at four trials; no live limit was enlarged.

Initial verification: **25 passed in 1.96 seconds**,
`software/runs/pytest-campaign-aggregation-20260913-01`, covering original-byte
reanalysis, known spread, failure retention, duplicate capture exclusion,
wizard export equality and existing renderer/analysis regressions. Subsequent
checks also cover disjoint timing bounds and the visible summary:
**26 passed in 2.02 seconds**, `software/runs/pytest-campaign-aggregation-20260913-02`;
Node syntax check passed. These are focused checks, not a full-suite claim.
No hardware was opened or commanded.

### Executor prerequisite audit and clock handling — 2026-09-13

Reviewed `arm/roarm_m3.py`, `arm/serial_transport.py`, `safety/permit.py` and
`safety/supervisor.py` before introducing a new outbound boundary. The existing
SerialTransport intentionally remains feedback-only; a MotionPermit does not
make its live motion method available. ReplayTransport consumes exact-goal
permits in memory. The richer `authorization_v2` ordered permit is also explicitly
simulation-only and must not be repurposed as live commissioning authority.

Found and fixed a prerequisite expiry-check defect: the legacy MotionPermit
could evaluate an injected nonfinite clock without refusing consumption. Both
feedback and motion issuance/consumption now use checked finite numeric clocks;
Boolean, string and overflowing clocks are rejected. Failed clock validation
does not consume a goal. A later valid replay dispatch still consumes it exactly
once. This is an expiry-boundary correction, not a native executor or new permit
issuer. Supervisor build/calibration/interlock gates remain unchanged.

Verification: **80 tests passed in 5.03 seconds**,
`software/runs/pytest-executor-clock-20260913-01`. Scope: safety core, ordered
simulation authorization and campaign-analysis regression tests. New tests use
supervisor-issued motion permits and ReplayTransport; existing tests continue
to assert that live serial motion stays blocked even with a valid permit.
No physical communication occurred. The single-trial native executor remains
unimplemented, pending the explicit observation/stop contract described above.

### Single-trial incapable execution lifecycle — 2026-09-13

Added `motion/characterization_executor.py`, with an explicitly incapable
single-trial qualification entry point. This is NOT the native executor and is
not wired to a live wizard button. It requires an exact FrozenCampaign in R_ctrl,
one selected trial, one supervisor-issued EMPTY_CELL_MOTION permit matching the
plan/build snapshot, an unused closed ReplayTransport, and an exact incapable
session. It cannot accept SerialTransport or mint a permit from a simulation.

The session claim is one-use and locked. Source/identity/evidence context is
checked before replay open and again after retaining a synthetic baseline.
Baseline mismatch, unavailable samples, coverage gaps and cancellation prevent
dispatch. The selected CartesianGoal is encoded/consumed at the existing replay
transport's final outbound boundary. No second trial, implicit return, query,
home, torque change, reset or retry is issued.

Post-command analysis reuses the actual wire analysis adapter. All exits revoke
remaining permit authority, attempt close and return retained baseline/post
evidence (when acquired), exact replay lines, ordered lifecycle events and errors.
An uncertain-write fixture preserves the possibly-sent line without retry;
uncertain cleanup overrides success. The report never asserts physical stopping,
device access, qualified freshness or physical readiness.

Initial verification: **41 tests passed in 0.47 seconds**,
`software/runs/pytest-trial-executor-20260913-01` (single-trial lifecycle and safety
core). Coverage includes one selected command without return, failure retention,
double/concurrent use, changed source/identity context, cancelled dispatch and
wrong plan/snapshot. Further checks cover baseline gaps, expired permits and
refusal of a native transport before any open.

Expanded verification: **63 passed in 0.98 seconds**,
`software/runs/pytest-trial-executor-20260913-02`, also covering campaign simulation
and comparison regressions. No hardware process or device connection was started.

Remaining P5b work is substantive: native request/claim and dependency packaging,
qualified same-session baseline and physical observation contract, bounded native
write/capture/cleanup ownership, authoritative live evidence binding and wizard
single-trial arming/result integration. Replay tests do not satisfy those gates.

### Saved physical capture review through wizard — 2026-09-13

Added Arm -> Review saved arm telemetry (no hardware), in both wizard modes.
Select an exact existing export folder name under the workspace's
`software/runs/wizard-exports`; paths/traversal are rejected. The default points
to the historical successful zero-write capture, not a current session.

`application/wizard_movement_capture.py` verifies the complete diagnostic export,
reads the exact native-log attachment through the bounded regular-file reader
and rechecks its manifest length/hash. It reconstructs stdout from independently
decoded chunks, validates its length/hash and wrapper identity, then checks the
capture bytes/hash. Native-worker request and inner observation intent hashes
are distinct and preserved separately; neither grants authority here.

The full-window decoder uses original bytes/read windows, not the old capped
parser. Actual saved evidence reproduced **270 complete poses, one rejected line,
zero incomplete lines, 56,271 processed bytes and 113 unterminated bytes**.
Capture SHA-256 remains
`279f7a7827440ab97dfd374b79cdc705c909b20538c9781769245463210993d1`.

The wizard shows counts, unprocessed range and historical-only status. New
exports retain derived analysis and every capture byte in bounded base64 chunks
plus read windows. An initial public-path test rejected one oversized base64
string; chunking corrected packaging without relaxing retention limits.

Verification checkpoint: **14 passed in 1.94 seconds**,
`software/runs/pytest-saved-capture-ui-20260913-04`, including actual saved-export
reanalysis, public service/re-export equality and renderer regressions. Follow-up
tests cover both wizard modes and byte reconstruction. Historical-artifact tests
skip explicitly if that local export is missing; pure fixture tests are portable.
No hardware communication occurred; native movement remains unqualified.

Follow-up verification: **15 passed in 2.22 seconds**,
`software/runs/pytest-saved-capture-ui-20260913-05`; Node syntax check passed.
Both local historical-artifact mode cases ran (not skipped).

### Integrated regression checkpoint and live-path decision

**177 tests passed in 7.84 seconds**,
`software/runs/pytest-movement-integrated-20260913-01`. This combined telemetry
coverage, campaign validation/simulation/controller/geometry, incapable execution,
timed analysis/comparison, wizard saved-capture/run/export/rendering, safety core
and ordered simulation authorization. It does not demonstrate native movement
or prove completion of P5b/P6; those remain outstanding.

Before implementing the native T104 observation contract, request the operator's
decision: may the first small supervised hardware trial be explicitly endpoint-
only, deferring continuous in-motion characterization until an appropriate
observation path is qualified? This does not replace the full campaign goal or
approve a target. A later exact target, current presence, clearance, same-session
baseline and reachable shutdown review would still be mandatory. If continuous
in-motion evidence is required from the first trial, qualify the alternate
command/observation approach before writing that executor. Do not silently
weaken coverage criteria or infer this choice from prior broad sweep approval.

### Operator decision: endpoints first, continuous later — 2026-09-13

The operator explicitly selected endpoint measurements first, followed by
continuous observation. The goal resumes with that initial observation contract;
the full characterization objective is unchanged. This is not approval of any
numeric target, current hardware session or live move.

Implemented `analyze_endpoint_trial` alongside the unchanged continuous-coverage
entry point in `arm/movement_analysis.py`. Both reuse the same bounded decoder,
timeout, numeric and dwell checks. Endpoint-only analysis records the initial
unobserved interval before the first valid pose. It still rejects gaps after
feedback begins, invalid frames, insufficient dwell, stale/no-change values,
late replies outside the trial deadline and multiple buffered samples that share
one acquisition time. The continuous contract still rejects an initial gap.

Endpoint results have a separate schema/status and observed endpoint-dwell
bounds. Travel time, full-motion settling time and directional overshoot are
unavailable, never zero-valued estimates. Physical rest, freshness, accuracy and
motion authority are not asserted. The incapable single-trial executor now uses
this explicit endpoint-only post-observation contract; continuous campaign
simulation retains its existing stricter analysis. Wizard guidance names the
selected commissioning sequence without enabling a live button.

Initial verification: **33 passed in 0.96 seconds**,
`software/runs/pytest-endpoint-contract-20260913-01`, covering endpoint contract,
unchanged continuous analysis, comparison and incapable execution. Further
integration tests exercise delayed post-move endpoint feedback in the executor.
Next: native single-trial request/admission and bounded owned write/capture
implementation, retaining exact-target/current-clearance/operator gates.

Integration verification: **58 passed in 2.56 seconds**,
`software/runs/pytest-endpoint-contract-20260913-02`; Node syntax check passed.
Continuous comparison ingestion also explicitly rejects endpoint-only evidence,
so that evidence cannot silently acquire stronger continuous-coverage semantics.
Endpoint-specific campaign aggregation remains separate follow-up work.

### Bounded endpoint request and replay binding — 2026-09-13

Implemented `application/endpoint_trial_contract.py`. Canonical immutable request
bytes select exactly one trial from the embedded frozen campaign in R_ctrl.
There is no caller-supplied raw command: the typed T104 goal is derived from the
selected target and coefficient. The request binds an operation ID, exact USB
VID/PID/serial, campaign/source/configuration/firmware/geometry references, build
snapshot, received-unit/native-controller review, operator presence, shutdown
review and baseline qualification hashes. The campaign's USB identity must match
the request serial; a COM port is not accepted as identity.

Fixed limits: one open attempt, one motion-write attempt, no retries, at most
512 command bytes, 2 seconds for open, 1 second/32 KiB/256 reads for baseline,
5 seconds/64 KiB/512 reads for post-observation and 2 seconds for cleanup.
The selected trial timeout must fit the post-observation budget. The request
is at most 16 KiB and must reserve 10 seconds of execution/cleanup time within
a 10–30 second issued/deadline interval. These are host work bounds, NOT physical
stopping guarantees or servo-motion deadlines.

References are syntax/binding data, not authenticated approval. Request parsing
grants no permission, performs no I/O and exposes no consume/allow method. A
future native claim issuer must independently validate original reviews and
current conditions. No live admission or transport gate was weakened.

`execute_request_rehearsal` now checks this request's time/context and passes the
selected trial through the existing exact incapable single-use executor. The
report retains request hash and attempt ID. A supervisor-issued empty-cell
permit is still required; the request cannot mint or replace it.

Initial verification: **31 passed in 0.81 seconds**,
`software/runs/pytest-endpoint-request-20260913-01`, covering request bounds,
mutation rejection, selected goal, expiry budget and endpoint lifecycle/analysis.
Additional coverage binds the native-shaped request to one replay command and
rejects reuse. Native execution and the first live trial remain outstanding.

Integrated verification: **64 passed in 1.00 seconds**,
`software/runs/pytest-endpoint-request-20260913-02`, including the supervisor/
permit safety regressions. No hardware was opened or commanded.

### Separate one-write boundary — 2026-09-13

Reviewed the existing Windows serial facade and connection owner. Their fixed
T105 token/payload checks and passive-write prohibitions remain unchanged.
Added `application/endpoint_write_boundary.py` as a separate component for the
future owned endpoint connection. It opens no port and exposes no raw browser
command. Its context reader and one-write callback are trusted service/provider
dependencies, not public request fields; no native callback has been attached.

The locked boundary attempts once. It checks exact request, plan/build permit,
owned connection ID, USB serial, all current reference bindings, operator presence
expiry and a recent baseline matching the planned start. The 100 ms host-baseline
age check is only a recency bound; authenticated baseline qualification must still
resolve buffered/stale device data. It consumes the exact-goal supervisor permit
immediately before the one writer call and revokes remaining authority on exit.

Partial, exceptional or malformed write completion is retained as uncertain with
no retry. Known partial byte counts are preserved. Driver exception text is not
copied into diagnostic reasons. Cancellation and time are rechecked after permit
consumption; changed context prevents writing. A successful byte write never
asserts movement, physical rest or a stop.

Corrected the request work budget to include a **1-second write allowance**:
the initial minimum reserved interval is now **11 seconds**, not the previous
10; issued/deadline span is 11–30 seconds. The final boundary reserves 8 seconds
for write, post-observation and cleanup. Over-budget completion is an error.
The future native writer must enforce its timeout with owned pending-I/O cleanup;
this callback boundary alone cannot preempt a blocked driver call.

Initial verification: **70 passed in 0.96 seconds**,
`software/runs/pytest-endpoint-write-20260913-01`, covering one-use, concurrent
attempts, cancellation during context collection, mismatched/stale evidence,
partial/unknown writes, request bindings and safety regressions. No hardware
was accessed. Remaining work includes authenticated native claim/ownership,
actual bounded I/O, worker supervision and wizard single-trial arming.

Final checkpoint: **72 passed in 0.96 seconds**,
`software/runs/pytest-endpoint-write-20260913-03`, including late write completion
and context expiry between permit consumption and the writer call. Tests used
only in-memory byte sinks; no native serial callback was attached.

### Bounded endpoint capture and analysis integration — 2026-09-13

Added `application/endpoint_capture.py` for baseline/post reads on a connection
already owned by the future executor. It has no open, write, purge or close API.
Its trusted reader must honor supplied byte/time limits; parent supervision and
native pending-I/O ownership remain necessary to handle a blocked driver.

The collector uses request-specific byte/read budgets, reads at most 256 bytes
per call, brackets reads with host timestamps, and stores raw bytes in bounded
exportable chunks. Capacity exhaustion, cancellation and reader failure are
explicit terminal outcomes, not completed observation. Late completions remain
retained and labeled separately from in-window bytes. Returned bytes preceding a
clock failure are preserved separately without fabricated timestamps. Broken
reader oversize results retain a bounded diagnostic prefix with explicit loss;
they never expand the capture budget or qualify a trial.

Post capture requires the actual command-completion timestamp and uses its trial
deadline, not a new timeout starting when the collector runs. Integration tests
exposed and corrected that distinction for delayed collector start. Cleanup time
remains reserved against the parent request deadline.

`analyze_endpoint_capture` reconstructs/hash-checks originals, validates the request
association and reruns endpoint analysis. Any failed, cancelled, incomplete or
capacity-limited capture withholds endpoint-dwell qualification even if some
reported endpoint coordinates appear correct. No result asserts physical rest,
current freshness or safe stopping.

Verification: **44 passed in 1.00 second**,
`software/runs/pytest-endpoint-capture-20260913-03`, covering storage/call bounds,
timeouts, cancellation, late/untimed data retention, command-relative deadline,
analysis fault exclusion, request/write boundary and endpoint analysis regression.
All readers were incapable fixtures. Native ownership/admission, actual bounded
I/O and wizard arming remain outstanding; no hardware communication occurred.

### Actual release-scope audit — 2026-09-13

A read-only import of the real build confirmed EMPTY_CELL_MOTION is denied for
`2026-09-01_CELL-A` (snapshot
`a1e5d4ed21a48890bb0a70aea31c96e8afee175ad8679fe95013ba593d18604e`).
The existing supervisor requires full-cell release/calibration evidence; the
endpoint tests instead used an explicitly synthetic released fixture. Those
tests cannot admit actual hardware. This is an integration scope mismatch if
the first requested move is a bare-arm commissioning trial before cell completion.

See [Endpoint native admission gap](ENDPOINT_NATIVE_ADMISSION_GAP.md) for actual
findings, limitations and the two legitimate routes. Confirm the current physical
commissioning scope before implementing a separate bench admission policy or
expecting the existing full-cell permit path to succeed. Existing release gates
were not edited, and no device was opened or commanded.

### Confirmed bench scope and separate permit — 2026-09-13

The operator confirmed bare-arm movement/functionality testing before board
mapping. This supersedes the pending scope question above. Camera/placemat
calibration is not a prerequisite for this separate non-contact bench route.

Implemented a request- and connection-bound `BenchEndpointPermit` with twelve
required authenticated-service reviews, pinned review hashes, fresh revalidation,
and irreversible one-attempt consumption. Integrated it with the existing
endpoint write boundary without relaxing full-cell/contact permissions.

Validation: **140 passed** across bench admission, endpoint request/write/capture,
rehearsal executor, safety core and authorization-v2 tests. Tests used incapable
writers and synthetic reviews; no physical I/O was performed.

Still required before live dispatch: trusted original-review service, durable
attempt claim, exclusive native worker/write/cleanup integration, wizard target
review and fresh operator setup/target approval. This checkpoint is not a live
commissioning success, a release of the build, or completion of this playbook.

### Persistent bench-attempt reservation — 2026-09-13

Implemented `application/endpoint_attempt_reservation.py` and made reservation
mandatory in bench permit issuance. The attempt ID is occupied before record
writing begins; an empty/partial record prevents retry. The permit rechecks
reservation integrity and authenticated-service evidence before consumption.
Cancellation/revocation never removes reservations. No restart/resume path exists.

**145 tests passed**, covering real separate-process issuance competition,
interrupted reservation publication, changed records/reviews, one-write behavior,
endpoint capture, rehearsal execution, and existing safety/authorization tests.
No native device was opened. Previous turn was concrete implementation progress;
this checkpoint adds persistent duplicate-attempt protection, not live motion.

Remaining next integration: a trusted service-selected/qualified root and review
originals, worker ownership/claim, bounded native movement I/O and cleanup, then
single-target wizard review and fresh operator-approved live qualification.

### Integrated owned-session endpoint sequence — 2026-09-13

Implemented `application/endpoint_owned_trial.py` to compose the existing bench
permit, bounded capture, one-write guard and endpoint analyzer on one already
owned connection. Sequence: baseline capture and start/coverage checks, exact
single write, post capture, analysis, unconditional permit revocation and one
cleanup attempt. No implicit query, return move, reset, torque operation or retry.

Baseline context is derived from retained raw frames, not a supplied pose summary.
Invalid frames, unmatched start, unframed suffix, coverage gaps or insufficient
host-observed span prevent dispatch. Recent host timestamps still do not prove
device freshness; that remains an independent authenticated review requirement.
Uncertain writes retain post evidence without qualifying the trial. Cleanup
failure, pending I/O or exceeding its time budget overrides an otherwise good
endpoint result without erasing the earlier evidence. Handle cleanup never
means physical stopping.

**160 tests passed** across the integrated sequence and existing endpoint,
reservation, executor and safety tests. Integrated fault cases include bad or
buffered baselines, cancellation before/after write, short/failed writes, read
failures, unchanged poses, cleanup exceptions, slow cleanup and pending I/O.
All I/O callbacks were incapable doubles with synthetic telemetry. No native
motion writer, device open or physical movement was performed.

The sequence requires trusted timeout-enforcing worker callbacks and a parent
supervisor; it cannot preempt arbitrary blocking Python callbacks. Live review
authentication, exclusive native worker claim/adapter, wizard composition, and
operator-approved physical qualification remain unfinished.

### Wizard single-endpoint rehearsal and export — 2026-09-13

Added the Arm action **Rehearse one endpoint trial (no hardware)**. Select one
explicit trial ID from the synthetic campaign; it executes the integrated
baseline/write/endpoint/cleanup sequence using an incapable byte reader/writer
and synthetic clock. Fault choices cover baseline mismatch, short write,
unchanged feedback, cancellation after write, and pending cleanup I/O. Other
campaign targets are not executed and there is no automatic return.

The worker uses internally labeled synthetic review evidence and persistent
reservations under `software/runs/endpoint-rehearsals`; it never imports a native
serial provider. Permits are consumed/revoked internally and not returned to the
UI. Reports preserve both input and synthetic plan hashes, the request, raw
baseline/post bytes and host windows, write outcome, and cleanup status.

Public wizard service tests verify the action in both wizard modes, unchanged
NOT_CONNECTED arm status, zero physical command count, and byte-equivalent
structured results in manifest-verified exported diagnostics. JavaScript syntax
validation passed. Browser visual verification was not performed at this checkpoint.
Combined endpoint, wizard, export, reservation and safety regression: **173 passed**.

The sequence/write guard now accept a trusted injected clock for deterministic
rehearsal (not a browser field). Write clocks reject invalid/backwards values;
clock failure during cleanup cannot skip the close attempt. Live USB execution,
authenticated physical review originals, worker claiming/ownership and operator
qualification remain incomplete. This action must not be used as hardware proof.

### Authenticated bench-review reader — 2026-09-13

Implemented a bounded service-authenticated bundle of the twelve bench review
originals and a reader that reopens the fixed attempt record, verifies its HMAC,
checks exact request/scope/reviewer/decision/expiry, and joins it to freshly
validated owned USB identity and source/configuration references. It returns
the existing bench evidence type for permit admission/consumption; no hardware
permission follows from knowing hashes or supplying unsigned JSON.

The signer is a private coordinator dependency, not a wizard action. It refuses
missing, denied, stale or mismatched originals and never upgrades engineering
reviews into operator attestations. It does not establish that a physical claim
is true. No production signing key or actual operator review was fabricated.

Combined regression: **194 passed**. New tests cover wrong keys, altered records,
missing/duplicate originals, scope and target mismatch, stale reviews, changed
USB/source context, and changed records after permit issuance. Host key lifecycle,
actual review issuance in the wizard, the native worker and current physical
qualification remain required. No device was opened or commanded.

### Separate Windows endpoint facade — 2026-09-13

Implemented `providers/windows/endpoint_serial_api.py` without changing the
existing fixed-query/zero-write validators or providers. Default construction
remains held. Its separate factory requires a bench permit backed by the exact
authenticated review reader and a fresh USB-to-COM association. It claims one
open; revocation before DLL loading prevents that open.

The facade accepts a motion submission only after the write boundary has consumed
the permit, then claims native dispatch once and rechecks its authenticated
context. Only the exact request-derived T104 bytes are accepted; T105, reset,
stop, direct-servo and other payloads are rejected by this motion write path.
Owned port/event checks, 256-byte read submissions, pinned native buffers,
terminal completion checks and no-retry semantics are preserved. Pending I/O
prevents handle closure; cleanup availability after expiry is not a physical stop.

Fake-kernel tests exercise exact successful submission, refused unconsumed or
revoked permits, changed COM association, unowned handles/events, wrong payloads,
one-use dispatch and retained pending buffers. The facade is NOT registered with
the wizard or owned backend yet. No real DLL/serial device was accessed in these
tests. Source/runtime worker claims, backend lifecycle integration, protected key
issuance, live operator review and physical qualification remain unfinished.
Combined endpoint/native-facade, wizard and safety regression: **206 passed**.

### Native handle ownership and complete trial composition — 2026-09-13

Implemented `EndpointSerialConnection`: one exclusive open, fixed DCB/timeout
readback, separate baseline/post read budgets, one exact write, pending-I/O
ownership and reverse-order cleanup. Setup failures close acquired handles.
Cancellation NOT_FOUND still requires terminal completion; late bytes are
retained separately. Unresolved I/O keeps handles/buffers alive and reports
CLEANUP_UNCONFIRMED. Repeated close does not retry cancellation or failed closes.

Empty input queues return an empty poll rather than submitting a driver read
with the longer configured timeout. Nonempty reads request only the available
bytes within the collector's limit. Nothing purges or silently discards input.

`execute_native_endpoint_trial` now composes the admitted facade, owner and
baseline/write/endpoint/cleanup sequence, retaining both the trial and lifecycle
diagnostics. Cancellation before open avoids native effects. There is no CLI or
wizard activation route for this entry point yet; it is a trusted child primitive.

Fake-kernel tests cover successful complete composition, baseline refusal,
pre-open cancellation, DCB/setup failure, empty queues, late cancellation
completion and unresolved native buffers. No actual Windows DLL/device access
or hardware movement was performed. The source/runtime-admitted parent/child
claim and supervisor, protected key and real review issuance, wizard activation,
and operator-approved hardware qualification remain required.
Combined endpoint/native-owner, wizard and safety regression: **216 passed**.

### Durable endpoint launch and process-bound child claim — 2026-09-13

Added `application/endpoint_worker_claim.py`. The parent reserves a launch ID
before process creation, retaining the exact request, original runtime registration
and review-bundle hash. The child rechecks these associations plus the current
source/runtime hashes and deadline, then exclusively reserves its claim. Empty
or partial records are never deleted or resumed. The live claim is one-use and
bound to its creating PID; disk inspection cannot recreate it.

The native trial composition now requires consumption of this exact claim before
constructing/opening its connection owner. It rechecks the launch and claim
originals and review bundle at consumption. Failed or completed trials cannot
reuse a consumed claim. Synthetic tests include actual separate-process claim
races and interruption immediately after claim-file creation.

This binds records; it does not independently qualify an executable or package.
The parent must still verify fixed executable/argv/package pins through the
existing owned Windows worker registration, launch/supervise the child, and retain
its result. No new child process or native wizard route was enabled by this
checkpoint. Protected key/review issuance and actual physical qualification also
remain outstanding. No serial device was opened or commanded.
Combined endpoint/claim/native-owner, wizard and safety regression: **224 passed**.

### Isolated endpoint package and feedback import regression — 2026-09-13

An actual isolated feedback-worker import check found an integration regression:
the wizard catalog imported the movement engine to construct its default example,
but that engine was outside the existing closed feedback archive. Moved the inert
example into the catalog and retained a compatibility wrapper for callers. No
planner/decoder validation or fixed-query permission was loosened. The existing
powered and passive package checks pass again.

Added an explicit deterministic endpoint dependency roster and
`_endpoint_native_child.py` import-check entry. The source bundle includes the
endpoint request/review/claim/permit/owner/execution stack with inert namespace
bootstraps. The real isolated `-I -S` subprocess verifies its archive hash and
imports the stack with native DLL, subprocess, socket and os.open access blocked.
Import success is labeled NOT_HARDWARE_TESTED. Wrong archive hashes and all
unregistered execution modes are rejected before any claim or native entry.

This verifies deployable dependencies, not a live parent/child protocol. The
child currently exposes only `check-imports`; fixed live registration, bounded
handoff/result decoding, protected key/review issuance and owned supervisor
integration remain required. No actual serial device was opened or commanded.
Expanded regression: **374 passed**, including real isolated package checks,
catalog/diagnostic tests, endpoint/native ownership, claims and safety tests.
The catalog's exact expected-action test was updated for the already implemented
movement/telemetry actions and explicit metadata-only acknowledgement; unconfirmed
metadata inspection still fails rather than defaulting approval to true.

### Fixed endpoint handoff and registration checks — 2026-09-13

Added closed endpoint handoff and parent-wire schemas. They bind the exact
request, attempt/session, source and selected USB identity, launch reservation,
runtime registration and deadline. Unknown fields (including raw commands,
ports, signing keys and resume flags) are rejected. Rehashing an envelope cannot
make a mismatched inner/outer context acceptable.

Registration validation pins the current base interpreter, fixed isolated child
argv/package source, assigned per-attempt directory, and one-process resource
budget: 25-second run, 2-second process cleanup, 64 KiB stdin, 256 KiB stdout,
8 KiB stderr. Native handoff requires at least 27 seconds of original request
lifetime; the shorter pure-component/rehearsal request contract is unchanged.

`OwnedWorkerRequest` recognizes the new data schema, but `OwnedWindowsWorker`
continues to reject its physical composition before backend creation. A test
proves that a valid registration cannot call an authorizer or launch backend.
The isolated child still rejects `execute-one`; only import checking is enabled.

Still required: result-envelope validation and parent publication, protected key
loading and actual review issuance, current hardware/source reconstruction in
the child, parent supervisor activation, wizard review/launch and supervised live
qualification. These checks create no process or device authority.
Expanded regression, including owned process supervision: **453 passed**.

### Endpoint result validation — 2026-09-13

Confirmed scope: secured, noncontact arm command/function testing comes before
board mapping. Final camera/board calibration is not a prerequisite for this
separate bench scope; it remains necessary before keyboard or phone contact.

Added `endpoint_native_result.py` to validate bounded result envelopes against
their requests, reconstruct capture bytes and hashes, recalculate telemetry
coverage and endpoint analysis, and reject unsupported success reports. A full
write and closed handles are required for an observed-endpoint result; neither
proves physical stopping or independently verifies movement. Cancellation and
baseline rejection remain valid failure reports without a motion submission.

The isolated dependency package now includes and import-checks the validator.
Tests use the native executor with fake Windows calls and synthetic pose bytes,
including modified raw hashes, coverage, analysis, write counts, pending cleanup
and false physical-verification claims. **135 focused regression tests passed**
in `software/runs/pytest-endpoint-result-20260913-04`.

No serial port was opened or hardware command sent during this checkpoint.
The result envelope's claim hash is an association, not authentication: parent
verification of the owned worker claim and durable publication is still needed.
Protected review issuance/loading, current child context reconstruction, parent
activation and the wizard's supervised single-move launch remain unfinished.
The physical child entry remains disabled; this checkpoint is not live approval.

### Retained endpoint diagnostics and parent receipt — 2026-09-13

Added `verify_endpoint_worker_receipt` for post-exit association of the original
launch, request, runtime, review bundle and child claim with the parent-owned PID.
It checks original claim timing rather than renewing expired movement authority.
The PID and process completion facts must come from the trusted supervisor.

Added `endpoint_result_publication.py`: immutable request/stdout/stderr originals
are stored before output interpretation, followed by a diagnostic report. Base64
storage wrappers preserve empty streams and exact original bytes/hashes. Invalid
or malformed output produces `RESULT_REJECTED`; valid evidence with failed exit
or unconfirmed process-tree closure produces `PROCESS_COMPLETION_UNCONFIRMED`.
No result authorizes replay or claims independently verified physical stopping.
Interrupted publication leaves retained originals; duplicate publication fails
without overwriting evidence. Storage failures propagate rather than reporting
successful export.

Verification: **40 tests passed** in
`software/runs/pytest-endpoint-publication-20260913-02`, covering fake-native
execution through retained result publication, original claim checks, altered
parent facts, malformed/empty output, duplicate publication and isolated imports.
These are software-only tests. No hardware access or movement occurred.

This publication component is not yet called by the wizard's live supervisor.
Remaining integration includes protected review issuance/loading, child current
context reconstruction, parent launch activation and the supervised wizard route.

### Supervisor receipt integration — 2026-09-13

`OwnedWindowsWorker` now retains its backend-owned Windows process ID and parent
completion timestamp in `OwnedWorkerResult`, independently of child JSON.
`publish_supervised_endpoint_result` adapts that exact receipt to retained
endpoint diagnostics, binds the request/runtime, and prevents cancellation,
cleanup errors, failed exit or incomplete process ownership from becoming a
successful completion report. It does not reread executable pins after the run,
so subsequent source changes do not prevent diagnostic retention.

Verification: **98 tests passed** in
`software/runs/pytest-endpoint-supervisor-receipt-20260913-02`, including 20 actual
Windows inert-child runs, endpoint retention checks, and powered/passive isolated
package regressions. Inert child processes are not hardware tests. No serial
connection or physical motion was performed. Physical endpoint launch remains
held pending the review/child-context/wizard integration described above.

### Protected review authority storage — 2026-09-13

Added `providers/windows/bench_review_key.py` with explicit provisioning and
load-only entry points. A random 32-byte key is protected with current-user
Windows DPAPI, noninteractive UI-forbidden flags, fixed application entropy and
a versioned plaintext domain. Protected bytes are exclusively published and
read back; existing or partial files are never replaced automatically. Missing,
corrupt, wrong-domain or wrong-length data cannot become a signing authority.
No plaintext key is written, returned in status, or placed in diagnostic exports.
Native temporary buffers are cleared and released; immutable Python byte copies
cannot be guaranteed to be securely erased. DPAPI does not isolate this key from
other programs running as the same Windows user.

The isolated endpoint package includes the loader and verifies importing it does
not load native APIs. **61 tests passed** in
`software/runs/pytest-bench-key-20260913-02`, including actual current-user DPAPI
operations with disposable test keys, corruption/no-regeneration, review signing
and verification, package isolation and diagnostic-publication regressions.
No production key was provisioned and no arm was accessed.

Integration still required: choose and enforce the host-private key location
outside exports, explicit local provisioning in setup, actual request-specific
review collection/issuance, child current-context reconstruction, and parent/
wizard live activation. The existence of a key never approves a physical check.
Current sources: Microsoft [CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
and [CryptUnprotectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata).

### Wizard private-key setup action — 2026-09-13

Added the physical-mode catalog action **Set up private bench review key**
(`bench_review_key_setup`) and its registered worker handler. Default `CHECK`
is read-only; explicit `PROVISION` plus acknowledgement creates the protected
key only if missing. Repeating setup loads the existing authority rather than
rotating it. Corruption remains an error, never automatic replacement.

The host-selected location is `~/AppData/Local/RoCell/private/bench-review-v1` on
Windows, outside the selected workspace. Each directory is checked using the
existing canonical/no-reparse-path storage primitive. Neither private path,
key material nor ciphertext is included in the wizard result. Browser input
cannot supply a key or path. This protects storage at rest with current-user
DPAPI; it is not a same-user process isolation boundary or movement approval.

**85 tests passed** in `software/runs/pytest-wizard-key-20260913-02`, including
the public wizard worker route, default read-only behavior, explicit provisioning
and repeated loading using actual DPAPI in a temporary test directory, catalog
validation and isolated package regressions. The rendered browser interface was
not visually checked. No production key was created, and no arm was accessed.

Next live-path dependencies: actual exact-request review collection/issuance,
shared host-private location loading in the isolated child, reconstruction of
current identity/source context, parent activation and supervised motion UI.

### Coordinator review issuance and shared key location — 2026-09-13

Moved host key-location resolution into the shared Windows provider. Setup may
explicitly create its fixed directory; parent/child loading is read-only and
fails when not configured. Existing no-workspace/no-reparse checks remain.

Added `application/bench_review_issuance.py`. The trusted coordinator supplies
separate operator and engineering readers returning complete, already-recorded
canonical reviews for the exact endpoint request. The service loads the host's
protected authority, validates and signs originals without changing timestamps,
exclusively publishes the bundle, verifies readback, then checks current owned
identity/references and remaining lifetime. Missing, stale or crossed reviews
do not become approvals. A failure after publication leaves an occupied record;
it cannot be overwritten or reused. Successful issuance is not a motion permit.

**118 tests passed** in `software/runs/pytest-bench-issuance-20260913-02`, including
protected-key-to-issuance integration with synthetic reviews, missing subsets,
duplicate issuance, changed identity, expiry and existing wizard/package tests.
All keys/reviews produced here are test fixtures, not production approvals.
No hardware access occurred. Actual review UI/reader wiring, current-context
reconstruction, isolated live entry and parent activation remain unfinished.

### Endpoint current-controller context adapter — 2026-09-13

Added `EndpointCurrentContextReader`, reusing the existing persistent native
interface/instance, driver and generic USB metadata comparison. The reviewed
binding digest is bound to `native_controller_review_sha256` in the endpoint
request. A changed COM mapping requires a fresh review; no automatic substitution
or first-match selection is permitted. Missing, duplicated, incomplete, changed
or stale metadata is rejected. Acquisition must start during the current call;
its age, including reference validation, is limited to 100 ms.

The adapter requires an independent trusted reference reader for current source,
configuration and review reconstruction. It does not substitute request hashes
for current evidence. The returned context retains acquisition start time rather
than making older metadata appear newly observed. It opens no serial port and
does not establish an atomic metadata-to-open-handle binding, power, firmware,
clearance or model verification.

Included the adapter in isolated package import checks. **100 tests passed** in
`software/runs/pytest-endpoint-context-20260913-02`, covering current-controller
matching, ambiguity/port changes, stale metadata, changed references and existing
controller/review/package tests. No actual metadata enumeration or hardware
connection occurred. Current reference reconstruction and wiring into the
isolated live entry still remain to be implemented before launch activation.

### Current source/build/reference reconstruction — 2026-09-13

Added `EndpointReferenceReader`. Each call recomputes the existing workspace
source fingerprint, imports the checksum-verified build snapshot, and rereads
eight fixed attempt-scoped original JSON documents. Exact original byte hashes
must match all request references. Files containing malformed/empty documents,
missing files, source/build changes or altered originals stop the check. The
reader does not accept caller-supplied digest callbacks or arbitrary filenames.
The native controller original must use bytes whose digest is the reviewed
binding digest; its semantic binding is independently checked by the context
reader. Other original receipt semantics still require their engineering and
operator reviewers: matching bytes alone never establish readiness.

Reference reconstruction now occurs before fresh metadata acquisition in the
context reader. USB acquisition age remains capped at 100 ms; lengthy source
verification is not disguised as fresh USB evidence. Overall execution remains
subject to the request deadline and parent process supervision.

Added these dependencies to the isolated package. **63 tests passed** in
`software/runs/pytest-endpoint-references-20260913-02`, including reconstruction
against actual current workspace/build files, changed source/build/originals,
context checks and package/result regressions. No device was accessed. Next is
assembling retained original receipts and actual reviews in the coordinator,
then wiring this reader into the isolated endpoint execution path.

### Fixed endpoint child composition — 2026-09-13

Added `endpoint_child_execution.py`: decode the bound request, reconstruct source/
build/original references, restore the exact retained persistent controller
binding, load the host-protected authority, claim the launch once, construct the
metadata/current-context/authenticated-review readers, obtain the bench permit,
and call the existing one-trial native executor. The permit is revoked in a
finally block, including failures after admission. The presence-expiry callback
rereads authenticated reviews rather than copying request expiry as approval.
Cancellation before preparation/admission prevents proceeding to the next stage.

Controller restoration rejects mismatched original hashes, extra/dropped fields,
changed nominal settings and semantic digest mismatches. Import checking includes
the full composition without executing it. **40 tests passed** in
`software/runs/pytest-endpoint-child-20260913-02`: restoration, early failure,
mocked dependency ordering and revocation, existing fake-native executor,
reference/context and isolated package checks. The new full composition has not
yet been exercised with real native I/O or qualified as a live runtime.

The isolated CLI still rejects `execute-one`, and the parent retains its launch
hold. Next required work is coordinator original/review assembly, end-to-end
fake-native child testing, then explicit parent/CLI/wizard activation and fresh
operator-approved physical testing. No hardware access occurred here.

### End-to-end fake-native child and timing finding — 2026-09-13

Exercised the assembled child with real workspace source/build reconstruction,
retained reference/review/launch files, actual request/claim/permit processing,
and the native ownership/write/capture code against fake metadata and Windows
I/O. The endpoint result codec validates the returned originals. Cases cover
observed endpoint, baseline mismatch (zero writes), and unchanged endpoint
(insufficient evidence). **40 regression tests passed** in
`software/runs/pytest-endpoint-e2e-20260913-02`.

A real host timing sample measured source fingerprinting at **167.49 ms** and
build import at **16.71 ms**, combined **184.20 ms**, before original-file reads.
The synthetic clock had hidden this cost. Authentication currently invokes full
reference reconstruction after baseline capture and again during permit checks,
while the write boundary requires a baseline no older than 100 ms. This is a
concrete live-path timing defect; the no-write boundary is working as designed.

Added a deterministic 184 ms reference-delay case. It confirms zero motion writes
and closed handles instead of falsely qualifying success. **All four end-to-end
cases passed** in `software/runs/pytest-endpoint-e2e-20260913-03`. These tests use
fake device I/O and do not qualify real motion or host worst-case timing.

Before live activation, move expensive source/build verification outside the
baseline-to-write critical interval while retaining trustworthy immutability/
change detection and current operator/identity checks. Do not merely widen the
100 ms limit or replace fresh verification with unchecked cached hashes. This
timing correction now precedes parent/CLI activation and physical qualification.

### Timing experiment and selected correction — 2026-09-13

Tested four bounded concurrent source reads while retaining per-file ancestor
checks, original inventory/order and digest layout. The resulting fingerprint
matched the sequential reader. One host measurement was **170.02 ms sequential**
versus **129.76 ms concurrent**, excluding build import and receipt reads. This
is still above the entire 100 ms baseline-age allowance. The experimental reader
was removed rather than adding an unused optimization or weakening limits.

Inspection confirms the existing owned Windows process backend already pins
registered package files with read-only sharing (no write/delete sharing), hashes
their opened handles, and holds path ancestors against replacement. Use that
mechanism to bind a per-attempt immutable execution/evidence snapshot:

1. Before launch, reconstruct current workspace/build and validate the eight
   original references. Freeze the exact approved originals and build snapshot
   into a bounded evidence archive, separate from the closed code archive.
2. Extend the fixed endpoint registration to pin that evidence archive for the
   entire child lifetime. Bind its hash into the launch record and wire. No
   browser-selected archive path, fallback, wildcard package or mutable cache.
3. The child verifies and loads those exact bytes once. Its reference reader then
   describes the **pinned execution snapshot**, explicitly not a claim that the
   editable workspace is still current. A later workspace edit belongs to a new
   attempt; it must not replace the running process's frozen code/configuration.
4. Preserve fresh operator-review expiry, exact owned USB/COM checks, live
   baseline freshness, cancellation and one-use dispatch checks in the short
   critical interval. Do not cache those physical-state checks.
5. Test replacement/write attempts against the pinned archive, source changes
   before pinning, wrong archive/request hashes, missing originals, cleanup and
   cancellation. Measure the remaining critical interval with real monotonic
   time before enabling the CLI or issuing a first physical command.

This is the selected implementation direction, not a completed timing fix.
No live path was enabled and no hardware was accessed during the experiment.

### Frozen evidence format and required registration pin — 2026-09-13

Implemented `endpoint_evidence_snapshot.py`: a deterministic, bounded 2 MiB
JSON envelope (`endpoint-evidence.json`) containing the exact endpoint request,
build snapshot and base64-preserved bytes of all eight original documents.
Preparation reconstructs current references before and after assembly, validates
all embedded hashes, publishes immutably and verifies readback. Decoding requires
the exact request and field set, build digest and every bounded original digest.
Matching bytes are not semantic approval or proof that a parent holds a lock.

The fixed endpoint registration now requires three package-file pins: isolated
child, closed code archive, and the exact evidence file in the assigned child
directory. Its digest participates in the existing canonical runtime and launch
association. Missing/changed evidence pins are refused. Live supervisor activation
remains held, so actual lock qualification for this third file is still pending.

Verification: **48 tests passed** in `pytest-endpoint-snapshot-20260913-02`
(registration/package/wire/result/end-to-end fake child), followed by **33 tests
passed** in `pytest-endpoint-snapshot-20260913-03` (snapshot, registration including
missing/altered third pin, and retained publication). These suites overlap.
The existing child still uses current-reference rereads: switching it to the
pinned snapshot, testing actual Windows write/delete exclusion, and measuring
the critical interval are the next steps. No hardware access occurred.

### Frozen child references and final-dispatch timing — 2026-09-13

The child now verifies and uses the registered immutable evidence snapshot after
an initial current-workspace check. Controller restoration also reads its frozen
original. This describes the execution snapshot, not ongoing workspace freshness
or a cache of live physical state. Parent launch pinning remains mandatory.

Actual Windows tests verified that parent pinning prevents write, delete and
rename of temporary evidence, then releases the locks on cleanup. No process or
arm was started. The 184 ms source-delay fake-native case now reaches its endpoint:
full source hashing is outside the baseline-to-write interval.

A read-only Windows metadata acquisition measured **47.0 ms**, no collection
blockers, and `device_ports_opened=False`. This is one timing sample, not a
worst-case bound or model/power/firmware verification. Simulating that delay
exposed a gap: final native review could age the baseline after the outer write
boundary's check. Fixed by carrying the original baseline deadline through
permit consumption and enforcing it after native review at dispatch admission.
Missing baseline evidence is also refused. No limit was widened or retry added.

**39 tests passed** for snapshots/Windows locks/child/registration/imports, then
**56 passed** for fake-native child, facade, connection, write boundary and bench
permits (`pytest-endpoint-frozen-reader-20260913-02` and `-04`). The simulated
47 ms repeated-metadata case now correctly sends zero writes. Full live timing
practicality remains unresolved: next reduce redundant metadata work or acquire
the final baseline after expensive approval work while retaining its deadline.
Live launch remains held. No serial port opened or arm command was sent.

### Remove redundant USB scan from expiry-only checks — 2026-09-13

Added `AuthenticatedBenchReviewReader.presence_expiry()`. It rereads and HMAC-
authenticates the complete original review bundle and validates its request and
timestamps, but returns only an expiry integer. It does not enumerate USB or
return native admission evidence. `__call__` and `verify_endpoint` still perform
their current identity/context checks, and permit consumption/native dispatch
still use those full checks. No approval or device snapshot is cached.

Wired the child executor's presence-expiry callback to that narrower operation.
End-to-end simulated 47 ms metadata acquisition now permits the expected single
write; simulated 60 ms acquisition still sends zero writes. The fake native
WriteFile hook explicitly asserts the latest baseline age is at most 100 ms.
Tests also show an expiry read cannot replace missing current USB context and
that changed bundles or expired timestamps are rejected after an earlier success.

**87 tests passed** in `software/runs/pytest-endpoint-presence-20260913-02`, including
end-to-end child timing, review/permit/native/write boundaries, isolated imports
and actual Windows snapshot locks. Timing cases use a synthetic clock and fake
device I/O, not worst-case host qualification. No hardware access occurred.
Next is coordinator/wizard assembly and isolated parent activation testing;
real supervised timing and first-movement qualification remain outstanding.

### Coordinator worker preparation — 2026-09-13

Added `endpoint_worker_preparation.py`. It authenticates retained signed reviews,
restores the exact physical-origin controller record and matches its USB identity,
reconstructs current references, assembles immutable evidence/code snapshots,
pins the fixed interpreter/child/code/evidence paths in the registration, and
reserves one launch ID bound to that runtime and review bundle. It returns typed
registration/request data without creating a process, serial connection or permit.

The entire fixed 27-second parent run/cleanup budget must still fit before and
after preparation. No deadline extension, fallback, overwrite or automatic retry
is allowed. Partial directories remain for diagnosis. Signature validation here
does not replace live identity, expiry, clearance or native dispatch checks.

Tests exercise actual workspace/build/package preparation with synthetic signed
reviews and controller evidence, bad-review rejection, repeated-attempt refusal,
time consumed during preparation, and proof that the prepared registration still
cannot launch through the held supervisor. Next is explicit parent activation
and isolated entry integration, then the wizard review/launch interface. No
production approvals or hardware commands were issued.

Verification: **45 tests passed** in
`software/runs/pytest-endpoint-preparation-20260913-02`, including preparation,
fixed registration/imports, fake-native child, Windows evidence locks and result
publication. Physical endpoint launching remains held.

### Reserved parent protocol and fixed isolated entry — 2026-09-13

Connected the endpoint protocol to `OwnedWindowsWorker` and added the isolated
`execute-one` entry. This supersedes the blanket code-level launch hold recorded
above: execution now requires fixed registration validation, the exact launch
reservation, current source/build/original verification, protected-key review
authentication, an external parent authorizer, parent-owned file pins/process
supervision, and the child's existing one-use admission/identity/baseline gates.
The wizard still has no live endpoint launch action, and no production approval
was issued in this checkpoint.

The parent repeats reserved-entry checks before execution, uses fresh monotonic
time after potentially slow file/key reads, and binds returned child evidence to
the parent-owned process ID and durable claim. The fixed CLI reads only a bounded
request, rejects missing/malformed input before claiming, and emits a bounded
failure diagnostic rather than exposing internal exception text. Unknown modes
remain rejected; import-check mode still disables native access.

Tests use an incapable injected backend to prove an authenticated, reserved job
can reach pin/authorize/start/cleanup in the correct order, retains failed child
bytes, and cannot be run twice. Other tests exercise real isolated import/empty-
input rejection and existing inert process supervision. No endpoint worker was
launched with a valid physical request; no serial port opened or arm moved.
Next: extend valid-result parent/child integration tests and wire the wizard's
explicit exact-target review, launch, cancellation and log export flow.

Verification: **78 tests passed** in
`software/runs/pytest-endpoint-activation-20260913-03`. An earlier injected-backend
test mixed synthetic request time with real cleanup time, correctly creating a
cleanup hold; the fixture clocks were corrected, with production cleanup checks
unchanged. No valid physical endpoint request was executed during these tests.

### Wizard-parent endpoint coordinator — 2026-09-13

Added `wizard_endpoint_coordinator.py` to connect one already-reviewed exact
request to preparation, owned supervision and the assigned diagnostic export
folder. It requires the parent service's current authorization check, verifies
dispatch inputs against the prepared request/registration/digest, and never
retries. Cancellation before dispatch stops preparation; cancellation after a
run does not skip diagnostic retention. Failed child bytes are retained just as
successful observations would be. Publication failures are explicitly reported
and the in-memory owned result still carries original stdout/stderr.

This is a parent-service component, not yet a browser action. Actual review
collection, selection of retained engineering originals, UI launch/cancellation
and displaying these outcomes in the arrival wizard remain to be wired. The
coordinator does not synthesize approvals or expose raw motion commands.

Tests use an incapable worker stub plus real file/package preparation and export
publication. They cover pre-dispatch refusal, cancellation after a failed run,
assigned-folder retention and disk-publication failure. No real endpoint worker
was launched, and no serial connection or arm command was issued.

Verification: **82 tests passed** in
`software/runs/pytest-endpoint-coordinator-20260913-02`, including coordinator,
parent admission/preparation, publication, isolated imports and inert process
supervision regressions.

### Wizard exact-request inspection panel — 2026-09-13

Added `movement_endpoint_review` to the registered wizard catalog and worker,
with upfront strict endpoint-request validation. Its retained result displays
request hash, trial, coordinate frame, six axis start/target/delta values with
units, firmware speed coefficient, dwell/observation timeout, and the separate
operator and engineering checks. The browser renders these values as text and
labels the result `REVIEW_ONLY_NO_AUTHORITY`. No signing, device opening,
permission creation or launch is attached to this inspection action.

The action accepts retained request JSON for inspection; it does not assert that
the request is still timely or approved. Actual request creation from selected
engineering originals, timed operator approval and live launch controls remain
unfinished. Inspection is a component of that UI, not a substitute for it.

**85 tests passed** in `software/runs/pytest-endpoint-review-ui-20260913-01`,
covering the public worker action, exact values/units/limits, malformed requests,
authority-claim rejection, catalog, isolated package and coordinator regressions.
`node --check software/src/rocell/ui/static/app.js` passed. Rendered-browser visual
verification was not performed. No hardware access or arm movement occurred.

### Incremental testing delegation and untimed selection — 2026-09-13

The user explicitly delegated judgement on system checks and safe incremental
noncontact commands without repeated per-command confirmation. This does not
establish unmeasured clearance, fresh baseline, or continuous-motion performance.
Progression remains endpoint-first; unexpected observations stop advancement.

A fresh read-only Windows metadata acquisition detected COM7, CP210x
10c4:ea60, serial 52E4E1E8337FEF119E92181CEDD322A4, with no native blockers
on that controller entry. Collection reported zero device ports opened. This
confirms enumeration only, not servo power, installed firmware or motion.

Added `endpoint_trial_draft.py`: an immutable untimed selection containing all
material request fields. Its hash must match when compiling a newly timed
request. The existing strict request codec still enforces identity, geometry,
limits and deadlines. No approvals are copied or created; authenticated reviews
must bind the new request. Durable launch records still govern attempt reuse.
This avoids spending the execution deadline while a target is being reviewed.

Verification: 30 tests passed in
`software/runs/pytest-endpoint-draft-20260913-02` across draft, request contract,
inspection and coordinator tests. An initial test reused its fixture attempt ID;
the test was corrected to use a distinct ID. No motion command was sent.

Remaining before live execution: connect draft selection and actual current
engineering reviews to the wizard launch path, then obtain a fresh owned
baseline and execute one bounded small slow noncontact trial with retained logs.
Do not treat this draft component or USB enumeration as motion qualification.

### Draft-to-reviewed execution integration — 2026-09-13

`wizard_endpoint_coordinator.run_endpoint_draft` now connects an unchanged draft
to the existing live-request pipeline. Trusted parent dependencies supply the
eight immutable reference originals, separate operator/engineering review
readers, current-context factory, cancellation and current-session check.
The function does not convert delegated authority into fabricated observations.

The sequence is: check current parent state; compile the exact draft into a
30-second request; validate all original bytes and hashes; exclusively retain
the request to reserve the attempt; stage the originals; reconstruct current
source/build references; recheck parent state; issue authenticated original
reviews for this new request; call the existing supervised runner and exporter.
Failures retain partial artifacts and return their stage. No attempt overwrite,
automatic retry, approval renewal or alternative raw-command path was added.

Verification: **34 tests passed** in
`software/runs/pytest-endpoint-draft-launch-20260913-02`. Tests include real
review signing/publication, reference staging, package/evidence preparation,
launch reservation and export of failed child output, with an incapable worker
stub. Changed selection/originals, incomplete engineering reviews, cancellation
and duplicate attempts are refused. These tests did not launch a native hardware
worker or send a command. Browser action wiring and actual current physical
review collection remain unfinished; the integration is a trusted parent API.

### Wizard endpoint action and current-session routing — 2026-09-13

Added the physical-mode `run_endpoint_trial` action and a typed, trusted-host
`EndpointWizardBinding` constructor dependency. The browser displays the exact
bound draft and hash; it supplies only that hash and an acknowledgement, not
coordinates, serial commands, original files, provider types or approval bytes.
The acknowledgement does not substitute for the independent current operator
and engineering review readers in the host binding.

The action stays disabled with no binding, absent/stale powered setup, rehearsal
mode or a previous attempt. Preparation and execution both compare the draft and
powered context. The parent repeats source/setup checks through dispatch, passes
the original action deadline to the coordinator, and retains its owned outcome
and report location. The generic diagnostic runner cannot execute this action.
Preview explicitly warns about serial-open startup movement and explains that
cancellation is not an emergency stop. The request deadline is capped by the
original parent deadline; delayed dispatch cannot renew the action budget.

Verification: 86 targeted tests passed in
`software/runs/pytest-endpoint-ui-launch-20260913-02`; 45 service regressions
passed in `software/runs/pytest-endpoint-service-regression-20260913-01`.
JavaScript syntax checking passed. Public-action tests use an incapable
coordinator and synthetic binding; no hardware connection or movement occurred.
Rendered-browser verification and provisioning a real current host binding are
still required. The default launch does not yet assemble that binding from the
received arm's retained/current engineering evidence automatically.

### Actual startup verification and remaining evidence intake — 2026-09-13

Checked current processes: no wizard server was running. The assigned diagnostic
folder contained historical powered-startup records, but no endpoint review
bundle was found. The retained firmware-history document records unchanged
delivery firmware; installed version/binary remain unknown. These findings do
not justify manufacturing the missing request-bound reviews.

Launched the actual physical-mode loopback wizard with no endpoint binding and
inspected its rendered browser accessibility tree. The overview loaded and
reported the local service connected, arm/camera NOT_CONNECTED and no physical
authority. No hardware action was clicked. This verifies overview startup only;
the bound endpoint form layout and live action remain unverified in a browser.
The temporary server was stopped after inspection.

Found and fixed a real onboarding defect: an omitted `--workspace` reached
`Path(None)` in the wizard handler. It now uses the existing CLI workspace
resolver (explicit path, environment, project discovery). **14 CLI tests passed**
in `software/runs/pytest-wizard-startup-default-20260913-01`, including actual
headless handler startup with no workspace argument and proof that the endpoint
action remains disabled. Default invocation is now:

```powershell
.venv\Scripts\python.exe -m rocell physical-onboard wizard --mode physical
```

Next evidence-intake work must supply actual configuration, firmware compatibility
rationale, noncontact geometry review, received-unit review, native controller
binding, operator presence/shutdown originals and baseline qualification. Source
and build hashes must be reconstructed, not pasted. A trusted host attachment
must keep independent current review readers; accepting arbitrary uploaded
approval JSON would not complete this integration. No live move is qualified.

### Endpoint-only campaign summaries and wizard rehearsal — 2026-09-13

Added `summarize_endpoint_campaign` alongside the existing continuous analyzer,
sharing bounded byte validation and grouping logic without weakening the old
contract. Endpoint observations must explicitly declare
`SUPERVISED_ENDPOINT_ONLY`; they cannot enter continuous comparisons. Original
bytes are decoded again rather than trusting cached success/analysis fields.

The report preserves missing/failed trials, excludes repeated physical byte
captures from independent repetition counts, and groups identical routes,
orientations, dwell, timeout, tolerance policy, speed coefficient and evidence
basis. It reports endpoint spread and median host endpoint-dwell-entry bounds.
It does not report travel duration, continuous overshoot, physical stopping or a
physical speed ranking. Recommended settings remain NOT_QUALIFIED until actual
evidence supports qualification; synthetic success cannot fill that gap.

The public campaign simulator now produces both contracts from explicitly
synthetic bytes without mutating its continuous evidence. The UI labels the
endpoint summary separately; standard verified wizard exports retain it. The
default out/back pair correctly reports insufficient repeated trials.

Verification: **24 tests passed** in
`software/runs/pytest-endpoint-campaign-wizard-20260913-01`, including delayed
initial feedback, later coverage faults, failed/missing/reused captures, exact
route separation, original-byte reanalysis and public export round-trip.
JavaScript syntax checking passed. No physical acquisition or movement occurred.
Joining actual retained native trial exports into this endpoint campaign input
and producing the measured settings report remain required live-campaign work.

### Saved native endpoint exports to campaign analysis — 2026-09-13

Added `application/endpoint_campaign_import.py`. The offline importer uses fixed
attempt-derived filenames and bounded reads for the retained report, request,
stdout and stderr wrappers. It verifies every original length/hash and exact
request/campaign association, then reruns native result validation and compares
the reconstructed summary with the retained summary. It never opens hardware,
renews approval, overwrites evidence or retries a command.

Invalid published results remain failed observations with no endpoint evidence.
Parent-completion/cleanup uncertainty stays ineligible even if endpoint dwell
was observed. `summarize_saved_endpoint_campaign` accepts at most 128 explicit,
distinct attempt IDs, not a directory sweep or automatic best-run selection.
Unobserved planned trials remain visible through the campaign analyzer. Offline
integrity is not authentication of the historical parent process or protection
against filesystem modification; no current physical approval is inferred.

Verification: **24 tests passed** in
`software/runs/pytest-endpoint-campaign-import-20260913-02`. The integration uses
fake native execution with real export publication, decode and campaign
aggregation. Tests cover wrong campaign, changed digest/path/summary, invalid
output and unconfirmed parent completion. No physical acquisition or move ran.
Actual measured campaign inputs, wizard selection of those saved attempts and
the evidence-backed hardware settings report remain outstanding.

### Public saved endpoint campaign review — 2026-09-13

Added `review_endpoint_campaign` to the wizard. It accepts the exact saved plan
JSON and whitespace-separated operation IDs, validates the bounded selection
before creating a ticket, and reads only the service-assigned export directory.
The browser cannot supply a filesystem root or report filename. Preview names
the assigned root and the read-only effects. The parent performs cancellation,
original-deadline and source checks between imports and around aggregation.

The UI renders the saved plan hash, selected-attempt count, eligible repetitions,
reported endpoint spread and explicit limitations. Standard diagnostic export
retains the full derived report, with no automatic speed selection, device open
or command. A successfully completed diagnostic review does not mean its selected
motion trials passed; failed/missing trials remain represented inside the report.

Verification: **72 tests passed** in
`software/runs/pytest-saved-endpoint-wizard-20260913-01`, including a public
physical-mode action with native-shaped synthetic exports, assigned-root use,
verified export round-trip, bad/duplicate/path selections and pre-import
cancellation. JavaScript syntax checking passed. No live hardware action ran.
Actual measured campaign acquisition, physical qualification and supported
hardware settings recommendations remain unfinished.

### Physical-stage readiness recheck — 2026-09-13 13:20 UTC

Fresh Windows metadata again found the expected CP210x controller on COM7:
VID/PID 10c4:ea60, serial 52E4E1E8337FEF119E92181CEDD322A4, native metadata
blockers empty. This check opened no serial port and sent no command.

The latest saved powered-startup original is
`operation-11fa2d0f2dc04429a31fadd34a8e2fe1-powered-startup-original.json`,
from session `wizard-f176d2fbbe994cba9c46b5b5fd4e5a58`. Its operator-reported
setup is approximately 13.95 hours old on the current monotonic clock, far
outside the wizard's five-minute current-setup window. It reports startup motion
as unknown and establishes neither measured supply voltage nor installed
firmware identity. Do not refresh its timestamp or reuse it as a current report.

No `*-endpoint-report.json` files were present directly in the assigned wizard
export folder. There is no completed live endpoint campaign to analyze there.
The user's delegation to choose bounded commands remains valid task authority;
it is not an observation of current operator presence, clearance or power state.
Pause physical acquisition pending a current factual setup confirmation, then
collect a fresh baseline and finish the real evidence binding. Software tests
and historical synthetic exports do not satisfy this physical stage.

### Combined endpoint regression checkpoint — 2026-09-13

With physical acquisition paused pending the current factual setup confirmation,
ran all unit files matching `test_*endpoint*.py` plus the continuous campaign and
wizard campaign regression files. **273 tests passed in 50.14 seconds** using
`software/runs/pytest-endpoint-combined-20260913-01`. This verifies the combined
software paths exercised by those tests, not received-arm performance. No live
endpoint command was issued, and the pending physical confirmation was not
inferred from the automatic goal continuation.

### Fresh operator confirmation and actual baseline — 2026-09-13

The operator confirmed current clear/powered setup and requested continuation.
Ran `software/scripts/bench_baseline_session.py` through public wizard actions,
not direct serial calls. Exact controller metadata matched; a new setup original
was recorded and one actual zero-command capture completed with confirmed serial
cleanup/process exit and verified export. Full reanalysis found 270 identical
reported poses in 56,000 bytes, with explicit partial boundary fragments.
See [the live baseline report](MOVEMENT_BASELINE_20260913.md) for hashes, pose,
limitations and the frame-boundary integration issue. No movement command ran.

### Frame-boundary issue resolved — 2026-09-13

Implemented explicit complete-frame subinterval handling shared by endpoint
baseline admission, endpoint reanalysis and native-result verification. Raw
bytes, original read timing and boundary ranges remain retained. Malformed
interior records and timing violations still fail; continuous analysis was not
relaxed. Added regression coverage for quoted and numeric partial prefixes,
partial suffixes, bad complete records and late reads.

A second actual public-wizard capture sent zero command bytes and retained
55,936 bytes. Updated reanalysis finds 269 complete poses in `[85, 55768)` with
zero rejected lines inside that interval; prefix/suffix remain explicitly
unobserved. See [the baseline report](MOVEMENT_BASELINE_20260913.md) for exact
export identity, hashes, verified test checkpoints and limitations.

Next unfinished implementation is real host evidence binding/request-bound
reviews for the supervised first small endpoint trial. The serial framing fix
does not itself enable motion or qualify movement performance. No pose/speed
campaign or hardware settings recommendation is complete yet.

### Concrete review intake — 2026-09-13

Added `application/endpoint_review_intake.py`: a trusted-parent collector for
actual decisions on an exact issued request. Each check is immutably published
with actor, rationale, host-recorded monotonic timestamp and bounded expiry.
DENIED/UNKNOWN originals are retained and cannot be overwritten. Separate
operator and engineering reader methods feed `issue_bench_reviews` without
refreshing timestamps, synthesizing missing approvals or opening devices.

Verified **40 tests passed** across intake, issuance and authority in
`software/runs/pytest-endpoint-review-intake-20260913-01`. The integration test
records explicitly synthetic decisions, issues a test-key bundle through the
existing coordinator and verifies it. This is not hardware approval.

Host integration sequence: collect actual decisions for the exact request via
`EndpointReviewIntake.record`, provide its two reader methods to the existing
issuance coordinator, then continue through current-context validation and the
one-shot executor. Review intake alone does not authenticate an actor; the host
must associate input with the actual reviewer. It is not a public signing API.
The UI/host must finish this connection and reference selection before live
launch; no production review records or motion commands were created here.

### Review-to-launch timing audit and regression — 2026-09-13

Current-state inspection identified a concrete UI integration constraint:
`EndpointTrialRequest` permits at most a 30-second lifetime, and
`prepare_endpoint_worker` requires 27 seconds remaining for the fixed parent
run/cleanup budget. Thus staging and review issuance have at most three seconds,
including their disk I/O. A human multi-step review cannot reasonably be placed
inside this synchronous path. The concrete intake is useful, but it alone does
not make interactive onboarding ready. Earlier fixed-clock integration tests
did not establish that timing feasibility.

The preparation reserve is now a shared constant. The draft coordinator checks
it before and after issuance and reports `REVIEW_BUDGET_FAILED` without reaching
the worker when exhausted. Original request deadlines and any already-published
reviews remain unchanged. Added tests advance time four seconds during staging
or review; neither launches a worker or renews the request. The native worker's
own reserve checks remain in place.

Verification: **294 tests passed, zero failures/errors/skips**, combined endpoint
and campaign suite, process exit 0. Durable JUnit result:
`software/runs/endpoint-review-integrated-20260913-01.xml`; pytest basetemp:
`software/runs/pytest-endpoint-review-integrated-20260913-01`.
These are software/synthetic tests, not motion-performance evidence.

Next integration work must explicitly resolve the review lifecycle: human
inspection of immutable draft material before the short execution window,
followed by an authenticated final launch decision and current-state checks.
Any draft-review bridge must retain the original decision timestamps, bind all
target/speed/device/reference fields, reject changes and expiry, and preserve
one-use launch and native execution/cleanup limits. Do not silently relabel an
old draft decision as a fresh exact-request review. That bridge is not implemented
or authorized by the current request-review codec; document and test its trust
contract before enabling it in the UI. Actual hardware evidence and the first
bounded live trial remain unfinished. No serial port was opened in this work.

### Engineering draft-review binding implemented — 2026-09-13

Implemented the [engineering draft review contract](ENDPOINT_ENGINEERING_DRAFT_REVIEW_CONTRACT.md).
Engineering decisions can precede the execution window while retaining their
original bytes, time and expiry. A distinct v2 binding records association with
the unchanged exact request; the authenticated verifier rechecks nested material
and refuses operator-check substitutions. Existing fresh operator checks,
native baseline, one-use and execution/cleanup boundaries remain unchanged.
Native packaging explicitly includes the two required draft-review modules.

**309 combined endpoint/campaign tests passed**, exit 0, with durable JUnit at
`software/runs/endpoint-engineering-integrated-20260913-01.xml`. Production
evidence collection and the atomic final-operator-input/request association
remain to be connected in the wizard. No actual reviews were fabricated and no
device was opened. This is not first-move or campaign qualification.

### Engineering reader connected to coordinator — 2026-09-13

Added `EngineeringDraftReviewReader` as a concrete host dependency for the
existing wizard binding/launch coordinator. It requires all five unique reviews
for one draft, binds them to the coordinator's exact request and consumes its
invocation even on failure. Concurrent calls cannot issue two bindings.
An integration test verifies the original bytes survive real authenticated
issuance; denied, unknown, changed and expired reviews retain the attempt but
never reach the terminal runner. No production approvals are manufactured.

37 focused tests passed; 29 adapter/native package/child regression tests passed,
both exit 0. See the engineering review contract for durable JUnit paths and test
scope. Actual engineering evidence intake and final operator-input/request
association remain unfinished, followed by the first supervised hardware trial.

### Engineering decision form and export connected — 2026-09-13

Added the physical-mode `record_endpoint_engineering_review` wizard action with
exact draft, self-reported reviewer, engineering check, explicit decision and
rationale fields. UNKNOWN is the default. The parent records immutable original
draft/review files with real execution timestamps; previews do not create
approvals. Different-source drafts cannot publish a review. Standard verified
diagnostic export retains the report and hashes; successful recording is labeled
NOT_AUTHORIZED and does not install an endpoint binding or access hardware.

**329 combined tests passed**, process exit 0, durable result
`software/runs/endpoint-intake-integrated-20260913-01.xml`. This includes the public
action/export round trip and negative cases, not actual hardware engineering
approval. Next: assemble verified originals and connect final current operator
input to the exact request; then qualify the first slow noncontact hardware move.

### Retained engineering evidence loader — 2026-09-13

Connected operation-scoped wizard review originals to `EngineeringDraftReviewReader`
using a bounded, read-only loader. It accepts five explicit trusted-host receipts,
checks retained bytes/hashes, exact draft/current source, decision, expiry and
unique engineering checks, with current-context checks around reads. No latest-
approval discovery, caller-selected paths, timestamp renewal or device access.
The reader rechecks validity when the exact live request is subsequently bound.

31 selection/intake/reader tests passed, exit 0; durable result
`software/runs/endpoint-engineering-selection-20260913-01.xml`. These verify
software assembly with synthetic records, not actual hardware approval. The
remaining launch integration must obtain final current operator input and bind
it to the exact request before the first supervised hardware trial.

### Final-confirmation host transaction — 2026-09-13

Implemented exact-request creation at final confirmation acceptance, before
recording seven explicit current operator answers. This uses existing v1
operator reviews and preserves their exact-request timestamp rules. The
coordinator accepts the prepared request only if draft/attempt/deadline match
and does not renew it. Retained partial transactions and duplicate attempts
remain refused; missing, false or inferred answers are not approvals.

350 combined endpoint/campaign tests passed, exit 0; result
`software/runs/endpoint-confirmation-integrated-20260913-01.xml`. The next concrete
UI step is invoking this host transaction when authenticated final button input
is accepted, before queueing, and passing its unchanged request/operator reader
to the coordinator. Production evidence assembly and first live qualification
remain unfinished. No hardware was accessed in this checkpoint.

### Final Run button connected — 2026-09-13

The public `run_endpoint_trial` form now requires operator identity and all seven
explicit operator checks, with no affirmative defaults. Acceptance records the
exact request and original operator reviews before queueing, consumes the
attachment before publication, and retains both in diagnostic events. Failures
do not dispatch or silently retry. The worker passes the unchanged prepared
request and recorded operator reader into the existing coordinator; queue delay
does not create fresh approval or extend the deadline.

479 endpoint/campaign/catalog/wizard-service/CLI tests passed, exit 0; durable
result `software/runs/endpoint-button-integrated-20260913-01.xml`. Tests include
deferred queue acceptance, duplicate clicks, each required check, failed
publication and verified export. No hardware was accessed and no browser visual
QA was performed. The default wizard remains held without an actual host-bound
trial. Next is production evidence/binding assembly, then fresh physical checks
and first slow noncontact trial—not unrestricted pose/speed execution.

### Host binding assembly implemented — 2026-09-13

Added inert assembly of the exact draft, eight original references, five selected
engineering reviews and existing current USB/reference context reader. Current
source/build/hash checks run during assembly and are repeated for the actual
request via existing readers. Assembly signs nothing and does not enumerate or
open hardware. The public wizard still supplies its explicit final operator
confirmation; the assembly's fallback operator callback refuses.

39 assembly/context/selection/button tests passed, exit 0; result
`software/runs/endpoint-binding-assembly-20260913-02.xml`. The production host
must wire a process-supervised metadata provider; there is deliberately no raw
Windows metadata fallback in the UI process. Actual evidence selection/provider
wiring and first live qualification remain unfinished. No actual motion ran.

### Supervised metadata adapter and actual timing — 2026-09-13

Added `SupervisedEndpointMetadataFactory`, reusing the existing fixed no-actuation
diagnostic child and process cleanup. The runner accepts an original work cutoff
and refuses dispatch/late results without deadline renewal. Deadline-bound
polling uses 5 ms rather than the usual 50 ms; snapshot timestamps are preserved.

Two actual metadata-only runs found the expected COM7 controller with zero opens
or writes. Both completed in 984 ms; snapshot age at return was 140 ms before the
polling change and 93 ms after it. The latter is marginal and does not qualify
the full retention/context path. The 100 ms gate is unchanged. See
[actual timing and retained log hashes](MOVEMENT_METADATA_TIMING_20260913.md).

437 combined endpoint/campaign/diagnostic-runtime tests passed, exit 0; result
`software/runs/endpoint-supervision-integrated-20260913-01.xml`. Next: complete
host wiring and full-path timing qualification, then actual evidence selection
and fresh physical checks for one slow trial. No motion command was sent.

See also the subsequent [actual-unit evidence audit](MOVEMENT_LIVE_EVIDENCE_AUDIT_20260913.md):
the production endpoint originals/reviews are not yet assembled, the last setup
record is outside its five-minute window, and an older different USB serial must
not be reused. Fresh factual setup confirmation is required for the next serial
baseline/live stage; historical metadata and synthetic tests are not substitutes.

### Shared-path metadata retention timing — 2026-09-13

Extracted the factory acquisition/retention code into one shared function and
added the finite `bench_metadata_timing.py` diagnostic script. Three actual
metadata-only samples, including log retention, returned at ages 62/62/78 ms
with elapsed calls 859/844/860 ms. All were inside the unchanged 100 ms gate at
probe return. The verified log session and hash are recorded in
[the timing report](MOVEMENT_METADATA_TIMING_20260913.md).

The probe checks cancellation in the age-sensitive window and verifies source
before acquisition. It does not construct a physical controller approval or
qualify the final endpoint context. A composed test verifies retention latency
is included in the age check. 79 adapter/assembly/runtime tests passed, exit 0;
`software/runs/endpoint-retained-metadata-20260913-01.xml`. No serial open or
motion command occurred. Actual host binding/evidence selection and fresh
physical readiness remain required before the first slow trial.

### Service-level reviewed attachment installation — 2026-09-13

Connected `configure_endpoint_trial` to the real assembler and supervised
metadata factory. The trusted host selects five completed review operation IDs;
the service derives receipt hashes from its own retained results. Successful
installation is NOT_AUTHORIZED, opens nothing and does not clear fresh setup
or final confirmation holds. Busy, already-bound or attempted attachment
replacement is refused. The method is not exposed as an arbitrary browser route.

32 service/assembly/button tests passed, exit 0; durable result
`software/runs/endpoint-service-binding-20260913-02.xml`. A real-assembler test
uses public review records with current source hashes but explicitly synthetic
hardware reference contents, without metadata acquisition or movement. Remaining
work is actual unit/reference review selection, final live-context qualification
and first slow movement before any repeatability or speed campaign.
