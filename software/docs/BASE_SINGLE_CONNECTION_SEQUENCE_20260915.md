# Single-connection compensated base sequence

## Objective and fixed route

Run the already measured increasing/decreasing base pair twice on one owned USB
connection. Preserve commanded-versus-desired endpoint separation, per-leg fresh
feedback, durable write claims, original captures and fault-hold behavior.
No camera work, new targets, faster speeds or all-joint compensation in this step.

Desired degrees: `[1.0, 0.4, 1.0, 0.4]`.
Transmitted degrees: `[2.335749466, -0.684826381, 2.335749466, -0.684826381]`.
Speed/acceleration: 20/1. Measured expected base starts alternate between
0.007669904 and 0.018407769 radians. The other five joint coordinates stay fixed.

## Implemented core

- New v14 intent; older v1–v13 keep their original limits and meanings.
- Exactly four fixed corrected legs, 60-second overall lifetime, eight seconds
  per leg, five-second post observation, two-second cleanup reserve.
- Capture capacity 96 KiB per leg / 384 KiB total, preserving 16 KiB baseline
  and 80 KiB post limits. Synchronized baseline remains 1.25 seconds per leg.
- Immutable nested increasing/decreasing proposals bind model, context, desired
  target and transmitted command. Each retains its original single-leg policy;
  the enclosing v14 contract alone defines the four-leg order and budget.
- `base_alternating_sequence.prepare_base_alternating_template` rebuilds each
  proposal from eight original training exports and three held-out exports.
  It creates an inert template, not a native dispatch permit.
- Per-leg projection reuses existing v10/v12 endpoint mathematics without changing
  the sequence owner, deadline, durable predecessor chain or write count.
- Every fresh six-joint baseline must remain within 0.01 degree of its measured
  anchor, as well as satisfying the direction-specific fitted start domain.
  Requested targets are NOT substituted for measured predecessor positions.
- Existing incapable owned executor performs all four legs under one admission
  and one cleanup. Completed synthetic captures reconstruct independently.

## Native integration checklist (now implemented; validation below)

The wizard, versioned worker budget, supervisor allowlist, native connection/API
accounting and native reconstruction now support v14. Existing single-command
hardware profiles retain their original limits. No v14 physical command has yet
been issued; live validation is conditional on the regression suite below.

1. Trusted wizard staging: rebuild directional evidence, assign a new campaign ID,
   retain configuration originals, present all four intended/transmitted targets,
   and start the 60-second deadline only at final acceptance. Do not reuse the
   historical campaign ID from an offline preparation template.
2. Version-aware native process budget: select the longer bounded worker budget
   for v14 only, including registration, invocation checking and parent deadline.
   Preserve old registration hashes/interpretation for historical exports.
3. Native connection/API accounting: replace fixed two-leg/two-token ceilings
   with the validated intent's maximum writes. Keep exact-once submission,
   cancellation checks and cleanup callable after a held/expired campaign.
4. Native review/export: validate at most the intent's enumerated leg count,
   reconstruct the full ordered predecessor chain and phase/aggregate lifecycle.
   Exercise retained wrapper size/IPC budgets with four full-rate captures.
5. Full composition simulation: success; failed endpoint, malformed/stale feedback,
   uncertain write and cancellation on every leg; no fifth write; changed runtime,
   config or identity; no replay; exact portable export reconstruction.
6. Only after those pass, add v14 to the supervisor allowlist and remove the
   explicit native-facade hold. Run one fresh-start four-leg hardware campaign,
   compare it with the separate-session baseline and stop after that campaign.

## Interpretation

Single-connection sequencing still waits for settlement; it is not overlapping
trajectory streaming. Endpoint success is encoder-reported, not independent
Cartesian metrology. Keep sequence observations out of the frozen training set.
After native validation, consider a separately declared speed experiment; do not
change connection strategy and mechanical demand simultaneously.

## Validation status

Forty targeted tests passed, including a modeled 500 ms movement interval per
successful leg, complete four-leg capture reconstruction, all six handoff
coordinates, wrong direction/target/speed/model rejection, altered-result rejection,
and fault/cancellation injection on each of the four legs. Each injected fault
withheld all later writes and cleanup ran exactly once.

Targeted report: `../runs/base-sequence-ramped-simulation-20260915.xml`.
Broad compatibility report: `../runs/base-sequence-core-regression-20260915.xml`
finished with **838 passed, 156 intentionally skipped** in 228.69 seconds. The
40-test ramped-motion run followed separately; the broad run used the earlier
instantaneous-response fixture. Production code was unchanged between those runs.

The real offline preparation rebuilt both proposals from the original eight
training and three held-out exports per direction. The inert template is 7,785
bytes. See `../runs/BASE_SEQUENCE_PREPARATION_20260915.json`. This is a preparation
check, not a signed/staged native campaign. No device was opened or commanded.

A local 200-iteration validation microbenchmark measured 0.509 ms median and
0.699 ms maximum per template decode/validation. This is descriptive host timing,
not a worst-case execution guarantee or hardware-response measurement.

## Native qualification run

The 16 full staging/native-shaped collector/export cases passed: success, miss,
cancellation and starting mismatch, with fault locations across all four legs.
The UI preview and v14 supervisor dispatch/deadline/receipt tests also passed.
One UI assertion was corrected to count only leg descriptions, not the explanatory
text. An earlier concurrently edited-source attempt correctly held; a fixed-source
rerun passed. No native I/O was used in these tests.

Predeclared first live scope: one v14 campaign, at most four writes, unchanged
speed and fixed route, one serial connection. Acquire fresh baseline first; require
current identity, measured lower start and unchanged five other joints. Any held
leg ends progression. No retry, positioning substitute or automatic return.
Afterwards reconstruct every retained original and compare final/start handoffs
and reported timing with the separate-session baseline.

Before live dispatch, two read-only baselines (`operation-3b996ae8590b4025a8cac39d73185aa3`
and `operation-e95737d5245241459ab3c07ff170af0f`) agreed exactly. Wrist pitch was
0.047553404 rad rather than the earlier 0.050621366 rad (about -0.176 degree).
This is within the existing frozen model's 0.5-degree other-joint context gate;
no gate was widened. The live sequence will bind the newly observed wrist value
and require its existing 0.01-degree per-leg handoff tolerance. All other starting
coordinates matched. This run is not an identical-six-joint-start comparison
with the earlier separate-session sequence; retain the difference explicitly.

## First native result and targeted optimization

The integrated broad regression passed: **858 passed, 156 intentionally skipped**
in 409.96 seconds. Report: `../runs/base-sequence-native-regression-20260915.xml`.

The first physical campaign was `campaign-ff05d87630574d38897f9b378d8b4eed`, report
SHA256 `3e9a9d2857c9ad0588a3886a84af2e2d157899618fcf9e4e76c11a1f45debffc`.
It sent exactly two commands on one owned connection:

| Leg | Desired base degrees | Reported final degrees | Absolute error degrees |
| --- | ---: | ---: | ---: |
| 1 | 1.0 | 1.054687474 | 0.054687474 |
| 2 | 0.4 | 0.439453128 | 0.039453128 |

Both endpoints passed and their original captures independently recompute the
recorded endpoint decisions exactly. Nonselected joints remained unchanged
during those captures. The third baseline matched the lower anchor, but the
reservation stage raised ValueError before any third dispatch record or write.
Leg four was skipped. Cleanup closed all handles with zero pending I/O.

Original export integrity verifies, but **full-campaign reconstruction is false**
because the third leg is incomplete. Do not label this a completed four-leg run
or confuse an intact diagnostic export with endpoint completion.

Selected-sample age at writes 1/2 was 234/218 ms. The third baseline ended 78 ms
after its selected sample; cleanup began 297 ms after that sample. No third
dispatch record exists. This is consistent with expiry at the unchanged 250 ms
age gate before dispatch. The historical exception records only ValueError at
reserve, so the exact branch is not conclusively recorded.

After retaining the failed attempt, baseline admission was optimized to decode
the immutable intent once per boundary rather than once for every sample.
All sample checks, context authentication, durable records and the 250 ms limit
remain unchanged. This removes redundant work, not safety/verification checks.
Post-change validation: **101 admission/collector/core tests passed**, then
**16 complete staging/native-shaped/export composition cases passed**. The speed
improvement has not yet been measured in another physical campaign.

Machine-readable partial review:
[BASE_SINGLE_CONNECTION_PARTIAL_20260915.json](../runs/BASE_SINGLE_CONNECTION_PARTIAL_20260915.json).
The original report and seven retained originals are in the corresponding
`software/runs/wizard-exports/<campaign-id>/` directory.

No second physical attempt, automatic retry, positioning command or return was
sent. Total base commands across the project now number 28. Last reported vector
is `[0.007669904,0,1.593806039,0.047553404,-0.001533981,3.149262558]` radians.

Next: add explicit bounded reservation-failure reason/timing diagnostics, then
predeclare one fresh-start run of the optimized four-leg profile. Preserve and
compare the failed attempt rather than replacing it or relaxing recency limits.

Update: reservation diagnostics are implemented and the optimized retest completed
all four physical legs on one connection, with complete export reconstruction.
Selected-sample ages were 140,156,172,172 ms versus the unchanged 250 ms gate.
See [the completed retest and evidence](BASE_SINGLE_CONNECTION_RETEST_20260915.md).
The earlier partial run above remains historical evidence, not a completed run.
