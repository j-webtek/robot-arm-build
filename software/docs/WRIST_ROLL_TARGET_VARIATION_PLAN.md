# Wrist-roll target variation and precision assessment

Status: enumerated offline cases, v22 native integration and host-staged wizard
case selection implemented and tested with fake hardware. First physical v22
trial remains pending: expected USB controller absent at latest discovery.
Updated: 2026-09-16.

## Purpose

Learn a local relationship between the commanded joint angle and the settled,
controller-reported endpoint. Use that evidence to test bounded compensation.
This does not measure tool-tip position in physical space or establish millimetre
accuracy. External measurement and board calibration remain separate work.

## Evidence and current position

The pinned [history assessment](WRIST_ROLL_HISTORY_ASSESSMENT_20260915.md)
contains 19 exports, with 10 clean long-window samples. Same-context increasing
repeats matched; decreasing repeats differed. In the latest v21 comparison the
decreasing endpoints differed by 0.175781 degrees. A predictor evaluated on four
later samples improved reported-error prediction, but those samples do not
validate corrected commands or identify a response slope across target angles.

Last retained roll position: 0.007669904 rad. Other reported joints:
`[0.007669904, 0, 1.593806039, 0.047553404, r, 3.149262558]`.
This is historical evidence, not a fresh baseline. The existing fixed increasing
profile requires roll 0.004601942 rad; the last endpoint does not match it.
Do not widen that profile's gate or silently insert a reset move.

## 1. Distinguish delivery, settling and precision

Implemented read-only `rocell.endpoint_quality.v1` export projection:

- Arrival: preserve the existing endpoint decision and 0.5-degree arrival band.
- Persistence: preserve the 35-second observation result; short trials are not
  silently treated as equivalent.
- Precision: compare absolute reported endpoint error to a proposed 0.1-degree
  diagnostic screen. This is not a new admission rule or established physical
  accuracy requirement.
- Repeatability: not assessable from a single trial; use matched history groups.
- Next start: compare all six reported joints to the opposite fixed profile's
  anchor, where applicable, using the existing 0.01-degree comparison tolerance.
- Authority: no projection grants motion permission or substitutes for fresh
  feedback. Original reports and their historical decisions remain unchanged.

The wizard displays these separately. Legacy results without this projection
show an unavailable message, not an inferred precision pass.

## 2. Implement an enumerated experiment, not arbitrary target entry

Add a new versioned experiment intent without changing v19/v20/v21 semantics.
Every case must name the selected joint, all six starting joints, target,
direction, speed, acceleration, observation duration and configuration hashes.
Retain one-use admission, existing finite limits and stop-on-fault progression.
No automatic retries or corrective moves after a miss or ambiguous capture.

Candidate first geometry, subject to simulation and fresh baseline validation:
use the last reported roll anchor 0.007669904 rad, and increasing displacements
of 0.9, 1.0 and 1.1 degrees. Targets are computed from that anchor, not rounded
display values. These remain within the existing local 1.5-degree delta and
3-degree absolute target ceilings. Hold speed 20 and acceleration 1 unchanged,
and capture 35 seconds per move. Do not vary speed while estimating target
sensitivity. The 0.1-degree spacing is an experiment choice, not a claim about
encoder resolution.

Only one case can start from a given fresh anchor. A return route needs its own
enumerated geometry, bounded validation and retained evidence. It cannot be
assumed to land at the anchor. If it misses, retain that result and stop that
matched-start block; do not relabel the new position as the original anchor.
If no reliable return route exists, collect discovery samples labelled by their
actual starts and defer matched comparisons and model promotion.

## 3. Offline tests before any new live profile

- Validate every target and start, joint index, direction, units and full-pose
  limits. Reject non-finite values, out-of-range values and unenumerated cases.
- Simulate ideal response, directional bias, deadband, quantized reports,
  delayed settling, late departure, stale feedback, partial writes and timeouts.
- Test bounded return routes independently; reject anchor mismatches rather
  than manufacturing a baseline. No queued continuation after a fault.
- Verify framing and raw-byte provenance remain reproducible. A report must
  distinguish submission, reported arrival, persistence and precision.
- Reconstruct original pinned campaigns unchanged. Old schema tests and native
  package/source-binding tests must continue to pass.
- Exercise wizard plan preview, single-case execution, stop, result review and
  export using simulated providers. No live hardware access in these tests.

## 4. Finite live discovery and matched blocks

After implementation and offline validation, acquire fresh feedback through the
existing owned wizard path. Reconcile the current six-joint pose with the staged
case. Execute one enumerated move, verify its endpoint and persistence, export,
then evaluate eligibility for the next case. A successful serial write alone is
not completion. Stay inside the validated local envelope and existing operating
conditions; do not expand to broad sweeps or simultaneous axes in this phase.

Begin with the nominal increasing case. Then qualify a return route separately.
If matched anchors can be reproduced, collect at least three samples per target
in finite blocks, rotating target order across blocks. Record approach direction,
prior endpoint, return route and time since the previous command. Use a separate
decreasing block with its own anchor; never pool both directions by default.
Three repeats are an initial diagnostic sample, not a reliability guarantee.

## 5. Fit and validate only what the data supports

First plot/tabulate target versus reported endpoint grouped by direction, start,
approach and configuration. Compare the existing constant-bias predictor with a
local affine response model only when distinct targets support a slope estimate.
Reject an inverse if the response is non-monotonic, nearly flat, unstable or
insufficiently sampled. Retain fit residuals and sample coverage.

Keep acquisition-order train/holdout separation. Never tune on the holdout and
then report it as independent validation. Compare uncompensated controls against
bounded corrected commands on new trials, not just retrospective predictions.
Clamp corrections inside the validated envelope; do not extrapolate. Report
median, mean absolute and worst error, repeat spread, late departures and failures.
The proposed 0.1-degree screen is diagnostic; model promotion requires an explicit
documented operating criterion supported by new evidence.

## 6. Reproducible exports and progression

Each derived result links campaign IDs and original report hashes, exact command,
fresh start, final six-joint feedback, signed error, persistence horizons, timing,
model version, correction (if any), configuration references and cleanup status.
Keep failed, held and incomplete trials; exclude them from fits only with an
explicit reason. Export to the workspace wizard export folder. Never overwrite
original evidence with a derived model assessment.

Done for this phase means: versioned cases tested offline; finite hardware trials
reconstructable; matched-start evidence or a clearly documented failure to obtain
it; held-out corrected-command comparison; and no claim of external spatial
accuracy. Expand to another joint only after this process works for wrist roll.

## Work checklist

- [x] Read-only quality projection and wizard display.
- [x] Separate diagnostic precision from historical arrival decisions.
- [x] Enumerated offline outward/return cases and 60-case response/fault matrix.
- [x] Versioned target-variation intent and finite return-route design.
- [x] Simulated providers, fault cases and native packaging regression tests.
- [x] Wizard experiment preview and controlled host-side case selection.
- [ ] Finite live discovery and matched-start blocks.
- [ ] Held-out comparison of uncompensated and corrected commands.
- [ ] Decide whether the evidence supports another joint or requires more work.

No hardware was accessed to create this plan.

## Validation of the diagnostic update

The focused Python/UI/export/wizard simulated-execution/history suite completed
with 190 passed and 156 skips for deliberately inapplicable base-only profile
combinations. An earlier endpoint/export/framing subset passed 30 tests. Node
syntax checking passed, and five Node display-branch tests exercised outcome
labels and missing/invalid projection fallbacks. These are not a live browser
or physical arm acceptance test.

All four pinned v21 repeat exports reconstructed with their original hashes.
The derived review is [saved separately](../runs/WRIST_ROLL_QUALITY_REVIEW_20260916.json).
Both increasing trials meet the diagnostic precision screen; both decreasing
trials do not. Historical arrival/persistence verdicts remain unchanged.

## Offline target-variation implementation (2026-09-16)

`rocell.arm.roll_target_variation` now defines six immutable-by-validation cases:
low/nominal/high outward targets and their separately defined returns. Each case
includes the full starting pose, joint mapping, target, fixed speed/acceleration,
observation duration, limits and a canonical configuration hash. Modified fields
are rejected, even if a caller supplies a different hash. Its simulation schema
is intentionally rejected by the native intent validator.

The deterministic simulator feeds synthetic six-joint traces into the production
endpoint/persistence evaluator and quality projection. It checks all six starting
joints before even a simulated write. It never chains a return or retries a
failure. Return cases assume exact nominal outward endpoints; biased outward
results are not silently used as those anchors. This is an experiment design,
not a claim that the physical arm follows the simulated response models.

Ten response/fault scenarios across six cases produced 60 independent results:
23 persistent, 10 changed after the early horizon, nine endpoint-not-verified,
six known-stale feedback failures, six transport faults and six incomplete
observations. Delayed settling can fail either early arrival or persistence,
depending on geometry; it never becomes an accepted persistent result here.

Validation: 71 focused simulator/persistence/quality tests passed, plus 43
framing/export/native-package regression tests, including isolated imports.
No hardware connection or command occurred.

Run from the workspace with:

```powershell
.\.venv\Scripts\python.exe software/scripts/simulate_roll_target_variation.py
```

The command prints the full deterministic matrix without writing files. A compact
review containing case/trace hashes, outcomes, precision and next-start checks is
[saved here](../runs/WRIST_ROLL_TARGET_VARIATION_SIMULATION_20260916.json).
Synthetic trace hashes are reproducibility identifiers, not hardware provenance.

Next implementation at that checkpoint: map an explicitly selected case into a new native intent
version; propagate it through admission, packaging, execution, reconstruction and
wizard preview. Preserve all old schemas and capture/framing checks. Test the full
owned path with fake serial before a single fresh-baseline physical discovery
move. The return route remains separately admitted and conditional on its actual
starting pose. No compensation model or live target variation is enabled yet.

## Native integration and connection attempt (2026-09-16)

Implemented `rocell.attended_positional_intent.v22`. Its six case IDs are `low`,
`nominal`, `high`, `return-low`, `return-nominal`, and `return-high`. Exact
configurations and full starting poses are checked during staging and fresh
admission. Each intent admits at most one raw T101 joint-5 command at speed 20,
acceleration 1, with 35 seconds of observation. No automatic return, correction,
retry or tolerance widening was introduced.

The profile shares the explicit framing path with v21, including reconstruction
and export, and retains the long-observation process and storage budgets.
Older schemas retain their previous interpretation. Export diagnostics include
the case ID and compare against the separately defined next-case anchor.

Trusted-host API: `ArrivalWizardService.configure_roll_target_variation(...)`.
Bench launcher selection: `--roll-variation nominal` (or another listed case).
It stages the case into the existing wizard review/run action; the preview shows
the case and starting pose. Case selection is host-side, not an unrestricted
browser angle editor. v22 framing is intrinsic; no additional framing flag is
needed. Required baseline/controller evidence and ordinary launch arguments
remain unchanged. Do not reuse a previous run's permission or stale baseline.

Validation: 125 tests passed across v22 geometry, substitutions, fresh-pose
checks, fake-serial capture/export, wizard staging, owned-coordinator completion/
miss/cancel, isolated native package loading, older v20/v21 profiles and the
offline simulator. JavaScript syntax checking and CLI help passed. Four pinned
hardware exports reconstructed with original hashes unchanged. These tests do
not establish physical v22 accuracy or demonstrate a real process stop.

A baseline session at 2026-09-16 13:15 UTC observed only Bluetooth serial ports,
not USB VID 10C4 / PID EA60 / serial 52E4E1E8337FEF119E92181CEDD322A4. It stopped
before opening any port. No baseline was acquired and no motion was attempted.
The exported diagnostic directory is
`software/runs/wizard-exports/wizard-20260916T131504706336Z-eb18d0e90c624300927e697911c4c0ec`.

Next: restore the expected USB connection, acquire a new baseline, and compare
all six joints to the nominal anchor. If matched, execute one nominal v22 case,
reconstruct/export its 35-second result, and assess the separately gated return.
If unmatched, retain the mismatch and plan a bounded repositioning case rather
than changing the experiment anchor silently. Roll movement count remains 18;
base count remains 44. No compensation has been enabled.
