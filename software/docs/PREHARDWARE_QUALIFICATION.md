# Prehardware software qualification

> **Camera architecture notice — 2026-09-05:** Phase 1 vision is now a rigid
> static overhead camera. The fixed-overview stack is the runtime migration
> target; moving/eye-on-arm cases in this qualification preserve prior or
> optional Phase 2 coverage and do not provide automatic fallback. Exact static
> hardware remains open, so this qualification retains zero physical authority.

## Purpose

`qualify-prehardware` is the aggregate, hardware-independent regression gate
for the RoCell keyboard and Android workcell. It exercises the existing
startup, typing compiler, trajectory, virtual arm, moving arm-camera,
registration correction, achieved-pose contact, device outcome, deterministic
fault, and mission-coverage services through their public application
boundaries.

It does not contain a second simulator and it does not open a camera, serial
port, or Waveshare transport. A passing result means only that the selected
software cases produced their exact expected results from one coherent frozen
source set.

## Readiness dimensions are intentionally separate

The report never compresses these facts into one ambiguous green state:

| Field | Meaning |
|---|---|
| `campaign_passed` | Every selected software assertion matched its expected complete or fail-stop result, resource caps held, zero authority was retained, and the source set revalidated after the last case. |
| `coverage_state` | `NOT_RUN`, `ALL_ROUTES_ACCEPTED`, `ROUTE_GAPS_REPORTED`, or `CATALOG_INCOMPLETE`. |
| `all_mission_routes_accepted` | True only after a fresh complete 75-route standard-profile screen accepts every route. It is false—not inferred—when quick coverage is not run. |
| `physical_ready` | Always false for this schema. Physical readiness requires later measured installation, calibration, controller, collision, contact, force, timing, and outcome evidence. |

Expected fault cases count as passing qualification cases only when the exact
fault is consumed once, the session fails closed, the virtual arm closes, and
the report retains zero hardware authority.

## Locked profiles

The case catalog is code-defined, ordered, bounded, and included in the policy
hash. The CLI intentionally exposes no arbitrary offsets, text, ports, or
fault selectors.

### Quick

The quick profile runs five cases:

1. coherent startup, alignment, calibration-inventory, and collision-inventory
   validation;
2. keyboard `a` with a hidden synthetic +12 mm Wv X board displacement,
   requiring `APPLY -> NO_CHANGE`, one accepted replacement suffix, achieved-FK
   contact, verified output, and park;
3. Android `a` with a hidden synthetic +8 mm Wv X displacement under the same
   adaptive requirements;
4. legacy fixed-overview JPEG tag-loss injection, requiring an exact fail-stop
   and closed plant; and
5. an independent rerun of the corrected keyboard case, requiring an identical
   complete child document and report hash.

Quick does not recompute all 75 routes. Its `coverage_state` is `NOT_RUN`.

### Standard

The standard profile is the default and is intentionally multi-minute. It adds:

- nominal adaptive keyboard and Android cases;
- an excessive +16 mm keyboard displacement that must be rejected before
  contact by the board-correction translation limit;
- all nine device-compatible deterministic fault families exposed by the
  legacy simulator: arm connect, arm reference, arm stall, camera unavailable,
  camera tag loss, missed contact, keyboard double contact, Android wrong UI,
  and focus loss; and
- a fresh independent park-to-target-to-park diagnostic for every one of the
  locked 46 keyboard and 29 phone targets.

The standard route case uses the locked promoted rank-1 virtual commissioning
overlay and requires fresh 75/75 acceptance. This is distinct from the
historical Freeze-005 baseline result of 38/75. Both are simulation-only. The
promoted overlay remains explicitly `UNMEASURED_SENSITIVITY_OVERLAY`; it is not
an installed arm pose, placemat change, or physical reach proof.

## Running it

From the workspace root after installing the package, or after setting
`PYTHONPATH` to `software/src`:

```powershell
python -m rocell qualify-prehardware --profile quick --require-pass --json
python -m rocell qualify-prehardware --profile standard --require-pass --json
python -m rocell qualify-prehardware --profile quick --require-pass --record --json
python -m rocell replay-prehardware-qualification --manifest software/runs/qualification-<report-prefix>/manifest.json --require-identical --json
```

Without `--require-pass`, a completed diagnostic is advisory and the command
returns zero even if one or more cases fail. With `--require-pass`, the exit
code is nonzero unless `campaign_passed` is true. That option never keys off or
changes `physical_ready`.

## Evidence and determinism

Each compact case result contains:

- the case-spec and private-input commitment hashes;
- only a hash/length commitment for requested text;
- a hash of the full child report;
- observed status and exact fault reason where applicable;
- bounded counts for virtual commands, captures, correction installations,
  contacts, ledger events, routes, IK solves, and Jacobian evaluations; and
- an explicit zero-authority result.

The aggregate report binds the active manifest, snapshot, bundle lock,
alignment report, virtual profile, study input, park probe, ordered case policy,
case results, coverage summary, resources, physical holds, and final source
revalidation into `report_sha256`. Wall-clock duration is intentionally absent
because it is nondeterministic.

The existing legacy session evidence package is not reused for this report: it
has a strict seven-file schema tied to `VirtualSessionReport`. Qualification
now has a separate six-artifact package plus `manifest.json`. The manifest is
written last, and strict verification rejects extra/missing/partial files,
duplicate JSON keys, noncanonical or oversized data, path/symlink escapes,
hash drift, source/policy/resource/child-report mismatch, forbidden private
payload fields, and any nonzero authority. Replay verifies those bytes first,
then reconstructs the locked policy and reruns the public qualification
service; recorded PASS data is never an execution oracle.

The inner `rocell.prehardware_qualification.v1` report deliberately preserves
its historical hash and its legacy runner-local `evidence_recording` field.
That field therefore still says recording/replay are unavailable *inside the
v1 runner*. When a package exists, the outer
`rocell.prehardware_qualification_evidence_manifest.v1` record is the
authoritative recording/replay declaration. This schema separation avoids
silently changing old report identities.

## Camera-path scope

Adaptive cases exercise the intended moving arm-camera chain from achieved six
joint values through camera FK, real synthetic JPEG bytes, tag detection,
board-pose estimation, registration decision, corrected suffix replacement,
and truth-derived achieved contact.

The standard aggregate's historical camera-unavailable and tag-loss cases
still exercise the older fixed-overview pixel service and retain the explicit
`LEGACY_FIXED_OVERVIEW_PIXEL_SERVICE` metric. Separately, the adaptive runner
now accepts an immutable, hash-bound, one-based camera fault schedule. Direct
adaptive integration tests cover camera unavailable, tag loss, excess blur,
excess noise, unqualified timestamps, and stale frames. Every mode must be
consumed exactly once, fault before contact, halt the remaining queue, close
the plant, and retain zero authority. A fault on the corrected re-observation
also proves that an installed replacement suffix cannot continue into contact.

The ESP HTTP adapter has an independent freshness boundary: once sequence,
timestamp, or ETag evidence appears it may not disappear; all established
channels must advance coherently; cached responses and nonadjacent A-B-A token
replay are rejected; and rejected frames never become the next freshness
baseline.

## Source-mutation behavior

The campaign validates one startup snapshot, and every child service retains
its own source checks. After the last case, the aggregate runner revalidates the
entire bootstrap. A controlled RC03 regeneration that changes source bytes
during a run aborts the campaign instead of producing mixed-snapshot evidence.

## Additional software-only campaigns

Two separate commands extend the fixed quick/standard gate without changing
its v1 case catalog:

```powershell
python -m rocell stress-adaptive-session --seed 20260903 --generated-cases 8 --require-pass --json
python -m rocell screen-adaptive-mission-routes --require-all --json
```

`stress-adaptive-session` runs fixed positive/negative X/Y and yaw cases,
over-limit safe-rejection cases, and cross-version deterministic SHA-256-seeded
combined perturbations. Exact hidden transforms are never serialized; their
inputs and results are committed by hashes. `screen-adaptive-mission-routes`
runs all 46 keyboard and 29 phone targets as independent complete moving-camera
observation/contact/outcome/park sessions. This is stronger and slower than
the trajectory-only 75-route screen, but it still uses nominal synthetic
truth, unmeasured camera/calibration assumptions, and no collision release.

These campaigns bind separate synthetic policies. Full-catalog coverage uses
2.5 mm translation and 0.5 degree yaw/tilt deadbands, 5 px maximum inlier
reprojection RMSE, and at most 128 executions per single-target route. With
planar estimator v1.1.0 and monotonic consensus, the 2026-09-04 run verified
75/75 sessions; report SHA-256:
`232dcdd5c7bb6cb7afb6e4dcac6001797991faa54587dd7e0979e67880d8d4e2`.
Perturbation uses 1.5 mm / 0.25 degree / 3 px and the same per-case ceiling. Its
2026-09-04 estimator-v1.1 rerun passed all 20/20 declared outcomes, including
four expected safe rejections; report SHA-256:
`9dda1bc28015ee6943d0e5017e16756dd30c6d0530d950a818161c28aa15dd20`.
These remain zero-authority software results; every physical camera,
calibration, collision, contact, controller-correlation, and
hardware-validation hold remains closed.

The hardware-neutral runtime boundary also has deterministic VIRTUAL/REPLAY
adapters and a complete mission-through-ports rehearsal. It exercises startup,
cancellation/deadlines, observation, execution, fresh correlated achieved
feedback, opaque contact, independent outcome, append/finalize evidence, and
mandatory stop/close cleanup. This proves adapter substitutability and
fail-stop orchestration; the production adaptive geometry state machine is not
yet a commissioned physical adapter and no physical mode is enabled.

## Remaining improvements and physical holds

1. Feed recorded physical camera/feedback datasets through the same typed
   observation and achieved-state boundaries after the hardware identities and
   clocks are measured.
2. Complete the holder, camera, cable, tool, robot-link, self-collision, and
   environment geometry needed for meaningful full-body route collision
   diagnostics. The present 19-body audit correctly remains blocked.
3. Correlate the controller frame/joint order/signs and real T=1051 timing with
   the pinned kinematic model; characterize tracking error and repeatability.
4. Replace synthetic intrinsics, tag map, eye-on-arm, TCP/compliance, device
   maps, and contact thresholds with measured, versioned, held-out-validated
   artifacts.
5. Only then introduce low-energy feedback/empty-cell hardware gates under the
   physical E-stop and gravity-safe setup; device contact remains later and
   separately released.

Implementation: `rocell/application/prehardware_qualification.py` and the
`qualify-prehardware` CLI adapter in `rocell/cli.py`.
