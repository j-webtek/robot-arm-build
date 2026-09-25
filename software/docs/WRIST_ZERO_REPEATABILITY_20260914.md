# Zero-target repeatability, 2026-09-14

## Outcome

Completed the planned minimum of three separately baselined zero endpoints per
approach, including the previously verified matched-target records. No command
compensation, tuning, firmware changes, tolerance changes or parser changes.

| Approach to nominal zero | Valid endpoint trials | Mean signed error | Observed final range | Sample SD | Pass count |
| --- | ---: | ---: | --- | ---: | ---: |
| From above, decreasing | 4 | +0.966796894 deg | +0.966796894 to +0.966796894 deg | 0 deg | 0/4 |
| From below, increasing | 3 | -0.439453128 deg | -0.439453128 to -0.439453128 deg | 0 deg | 3/3 |

Between-approach separation is 1.406250023 degrees. Starts were consistently
+3.779297 degrees from above and -3.251953 degrees from below, not exactly
symmetric. All use nominal zero, spd 20, acc 1, five-second observation and
unchanged +/-0.5-degree endpoint tolerance. Each trial, not each telemetry
frame, is one observation. No bootstrap confidence or high reliability claim
is justified by this small, single-setup sample.

Zero sample SD describes the retained quantized final reports only. It does not
mean zero physical variation, independent fresh servo reads, or exact tool-tip
position. Root cause remains unresolved: the data support approach/history-
dependent reported positioning, not proof of deadband, friction or backlash.
The passing side has just 0.060546872 degrees of tolerance margin, less than
one reference encoder count. It is not yet a robust production positioning rule.

## Exact zero-endpoint sources

Every campaign below has a verified original export with consistent endpoint
reconstruction. Paths are `software/runs/wizard-exports/<campaign-id>/`.

| Campaign ID | Leg | Approach |
| --- | --- | --- |
| campaign-37c6f91ee84a4fe4ab057fb0df2a1d48 | leg-01 | Above |
| campaign-8692dabab46d4826a5cac99ec2c76386 | leg-02 | Above |
| campaign-5b875a109ce645d5b93e852de572c240 | leg-01 | Above |
| campaign-bafc0b37ef7645efa021270829cca972 | leg-01 | Above |
| campaign-b722539816a44cbd957f35fc62877d4b | leg-01 | Below |
| campaign-abf46afb0e8d4e40999dd26e4f77f4bb | leg-01 | Below |
| campaign-aa183c275d524a60901f29af951575de | leg-01 | Below |

Statistics were recomputed from `verify_native_retained_export` endpoint
diagnostics, selecting executed target_rad=0 entries, grouping by direction
and using degrees(signed_error_rad). Incomplete or unexecuted legs were not
included. Above-side failures remain failures in both the data and pass rate.

## This turn's complete attempt ledger

Seven fresh campaigns were attempted; eight motion writes were confirmed.
Each campaign ended before any new one was prepared. Failed positioning traces
were reviewed for bounded residual, full capture, other-joint stability and
clean cleanup, followed by a fresh zero-command baseline. No old request was
replayed or failed predecessor marked successful.

| Campaign suffix | Outcome | Confirmed writes | Report SHA-256 |
| --- | --- | ---: | --- |
| 5b875a109ce645d5b93e852de572c240 | Zero from above missed; later leg skipped | 1 | e20c7721144b629a2c1c671cdc14d47ab17b29082d44810565aba6891c9174ed |
| 7b1603a79ced44a1becf4d92a1f38de4 | -4 positioning missed at -3.251953; later leg skipped | 1 | bf0669359e70b8f3e18d893ea4d3068c7f66bf69f2aad919a854f937bc0b02e1 |
| abf46afb0e8d4e40999dd26e4f77f4bb | Zero from below and +4 both passed | 2 | 6ca97eacc1ffc06e4b7c56a90bb412042d0ed9012539625db23129ecc8e0a464 |
| 6411b91b4db0410d8ae811e3ee4f8967 | Baseline rejected before dispatch | 0 | d084c6fc0d60f959283d39c765f5a09affed432a9ab98b83cc3c7084e73636fb |
| bafc0b37ef7645efa021270829cca972 | Zero from above missed; later leg skipped | 1 | 7b3ca9009d2d61bf612018c10f0d4270284f97f7f550d7bd3bf8d514efd9124e |
| bf8a4546b2ca4f7ea10c0543773f7b3b | -4 positioning missed at -3.251953; later leg skipped | 1 | 49b955ac1237ed8430e5d82340cfd19d7b962a7b8ef6b81500c3f3bd64e7f004 |
| aa183c275d524a60901f29af951575de | Zero from below and +4 both passed | 2 | a85630b5f1d6f3abd109afb684fbce96965f796cc965cea37a1bfcfe37e45d4d |

All completed endpoint traces showed no other-joint change or wrist excursion;
transport and cleanup were clean. The last negative positioning capture ended
15 ms after its five-second deadline, with retained in-window bytes validated
by the existing rules. Its last-second positions ranged -3.251953 to -3.164062
degrees (one count); the final constant tail was only 0.297 s. This variation
is retained and is not described as a perfectly static positioning trace.

### Separate transport failure

Campaign 6411... baseline began with bytes `0}\r\n`, then full T1051 records.
The strict parser reported INVALID_JOINT_RECORD. Its native lifecycle records
zero submission attempts and zero confirmed write bytes; all handles closed.
The original capture was retained, not repaired or counted as a position trial.
After inspecting this connection-boundary fragment, a new baseline and one-use
campaign were prepared; the failed campaign itself was not resumed. Improve
the wizard's specific error explanation and test stream attachment separately
before considering any narrowly scoped framing change.

## Final state and next steps

Offline comparison is implemented; see
[model results and prospective +2-degree validation plan](WRIST_ENDPOINT_MODEL_VALIDATION_PLAN.md).
This adds no live compensation or motion. Its zero-target validation is explicitly
retrospective; prospective new-target testing remains to be implemented and run.

Last campaign aa183... fully verified both endpoints. Its final reported wrist
is +3.779296882 degrees, other joints unchanged, no pending native IO, all owned
handles closed. Session export:
`software/runs/wizard-exports/wizard-20260914T225337691889Z-e3ae398bb6f94847b82a0cc6f2ef23b1/`.
No further motion was attempted.

1. Build an **offline-only** direction-conditioned error model from verified
   exports, with explicit training/held-out split, provenance and sample counts.
   Compare it with a constant-offset model; do not auto-apply either.
2. Design a bounded held-out nominal-target test to distinguish target-dependent
   error from approach direction. The present data cover only one matched target.
3. Improve baseline-fragment diagnostics and simulate stream attachments without
   weakening interior-corruption rejection or silently dropping original bytes.
4. Only then evaluate a separately reviewed correction experiment. Require an
   improvement on held-out endpoints and preserved timing/drift limits. Do not
   enable a global +0.439-degree correction based on three zero-target passes.
5. Use external calibrated vision before claiming board/tool-tip accuracy.
