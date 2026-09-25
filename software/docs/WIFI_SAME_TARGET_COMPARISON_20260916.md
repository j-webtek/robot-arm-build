# Same-target comparison: roll 1.25 degrees

Preselected finite plan: at most five distinct commands, compensation disabled.
Each leg must independently pass fresh-baseline direction, >0.5 to <=1.5-degree
delta, +/-3-degree target envelope, one-use dispatch and endpoint verification.
Speed/acceleration remain 20/1. Stop on any failed leg; no retry or replacement
sequence. Do not loosen limits to complete the plan.

1. Position at 1 degree descending using existing low-target action.
2. Position at 0 degrees descending (distinct new action).
3. Approach 1.25 degrees ascending; follow with 35-second read-only observation.
4. Position at 2.5 degrees ascending using existing high-target action.
5. Approach 1.25 degrees descending; follow with 35-second read-only observation.

Positioning legs still require the full endpoint verification; only their separate
35-second follow-up is omitted. Each invocation exports originals/results. No
script automatically issues the next movement. The operator/agent reviews each
result before invoking another leg. Each invocation has its own attempt id.

Compare original reconstructed endpoint errors and within-window stability at the
same target; keep starting pose, step magnitude and direction in the record.
One pair is not enough to establish repeatability or fit production compensation.
Controller feedback does not establish external Cartesian position accuracy.

Implementation: three new fixed choices (`zero`, `center_up`, `center_down`) in
the wizard and bench script; arbitrary target entry is not exposed. CLI
`--position-only` skips only the passive follow-up, never endpoint verification.

## Results

All five separately invoked legs passed. No retry, compensation, correction or
automatic return was sent. The comparison approaches produced:

| Approach to 1.25° | Reported start | Reported endpoint | Signed error | Follow-up readings |
| --- | ---: | ---: | ---: | ---: |
| From below | 0.263672° | 1.142578° | −0.107422° | 118 |
| From above | 2.285156° | 1.494141° | +0.244141° | 119 |

The two reported endpoints differ by **0.351562491°** despite the same commanded
target. All six reported joint values remained unchanged within each separate
35-second follow-up window and matched the preceding terminal pose. No other
joint changed during the verified movements. This is consistent with a
direction/history-dependent effect, but does not prove backlash, friction or a
firmware cause. Starting pose, prior path, ordering and travel magnitude also
differ; this is one pair, not a repeatability distribution.

The positioning legs ended at 1.230469° (target 1°), 0.263672° (target 0°), and
2.285156° (target 2.5°). All used the original position/timing limits. The last
reported roll is 1.494140602°; no parking/return command followed.

## Evidence verification

Each export passed integrity verification. Every endpoint row was reconstructed
from validated original feedback bodies and reproduced its stored verdict using
the discrete endpoint verifier. All passive originals matched their trial's
terminal six-joint pose. Follow-up windows are separate actions; no continuity
claim is made for gaps between them.

Exports below are under `software/runs/wizard-exports/` in leg order:

1. `wizard-20260916T161243562142Z-a256fd163be9409ab909903d61fda1b9`
   - SHA-256: `59b6b3cc523e783bac52c1d978071c7aca9a0e600d00f1e5933fad96c7f089e0`
2. `wizard-20260916T161251449091Z-165447a48fd24ea2a4b44cbbf6161b67`
   - SHA-256: `dd3c240bde4ffd5165327e0ab01fcf06a663e8d0869559a9bd95e3adc55c1d8f`
3. `wizard-20260916T161335874219Z-2361a48da18b4a0384d012cb739e59d8`
   - SHA-256: `d44641afc65fc35acc925922fed10b5127b32fe1e13cd1058b868cd9154912b8`
4. `wizard-20260916T161343762499Z-087192f187214f54a54e502758cf274d`
   - SHA-256: `30d8b999a6849f7b6963e65dd5c0c5d2aed920bf802f423ddd416b6aeb1da6cf`
5. `wizard-20260916T161426845181Z-64867a5dd3f94813b70de7bd1d4aed78`
   - SHA-256: `d0da13b931025c2d7af44cec52f07b81222f2457aaaea2513e3312b419d2e260`

## Next step

Repeat a small predeclared same-target set with reversed approach order, continuing
to admit each positioning leg against its actual fresh baseline. Stop rather than
widen limits if a positioning move becomes inadmissible. Only then estimate a
local direction-conditioned correction candidate and validate it on held-out
trials. Do not enable production compensation from this first pair or extrapolate
the result to other joints/targets or external Cartesian accuracy.

## Reverse-order repeat plan

Predeclared next set: at most four commands, compensation disabled:
high positioning (2.5 degrees), center_down (1.25 degrees) plus 35-second
observation, zero positioning (0 degrees), center_up (1.25 degrees) plus
35-second observation. Every leg remains separately invoked with fresh-baseline
admission. Stop the set on any failure, including out-of-envelope positioning;
do not substitute a new positioning route or widen limits to finish the set.

## Reverse-order repeat results

All four legs passed without retry or compensation. The two comparison endpoints
again remained unchanged through separate 35-second observations (116 descending
and 114 ascending responses). All five non-selected joints remained unchanged.

| Approach | Run 1 error | Reverse-order repeat error | Mean error |
| --- | ---: | ---: | ---: |
| Ascending to 1.25° | −0.107422° | −0.019531° | −0.063477° |
| Descending to 1.25° | +0.244141° | +0.156250° | +0.200195° |

Repeat descending endpoint: 1.406250023°, starting at 2.285156222°.
Repeat ascending endpoint: 1.230468748°, starting at 0.439453128°.
The earlier ascending start was 0.263671854°, so starting position/travel differ.
Direction/history remains a useful hypothesis, not an isolated causal finding.
Each direction's two-trial endpoint spread is approximately 0.087891°.

All four export integrity checks passed. Original response bodies reconstructed
the exact endpoint rows and reproduced each verdict. All passive originals
matched their trial's terminal six-joint pose. Export names under
`software/runs/wizard-exports/`, in command order:

1. High positioning: `wizard-20260916T161621264819Z-fcad4e13d60649c0b7547d8d8de813b6`
   - Manifest: `008dcf3c8a1bf6ab4b0ebda3601b686abaed79fa8d662f46aaabae5d314705b8`
2. Descending comparison: `wizard-20260916T161704104373Z-8d1f137f6aab4873887e7227841a3582`
   - Manifest: `df04dba27d9d7d8978d41762e8e4278e4c289729aa4d6b9cdbe67953f9351b94`
3. Zero positioning: `wizard-20260916T161711142227Z-e39f4575fdbd4078980ad9327392e2e5`
   - Manifest: `bf35aa8a3895b980e7a0de18221b919fea902b390758f07dee483b4c97e9ae63`
4. Ascending comparison: `wizard-20260916T161756980743Z-a0cafe710f944f17834b3e9e0c25c9f1`
   - Manifest: `597f678907e360c47de99766c7dd52596276dd4e20b5f5407b25195f0b051183`

## Disabled local correction candidate

Saved [candidate](WIFI_ROLL_125_CANDIDATE.json), not loaded by the native actions.
The hypothesis subtracts direction-specific mean training error from the desired
1.25° endpoint: command 1.313476570° when ascending, 1.049804688° descending.
These are proposed commands, NOT physically validated corrected endpoints.
In-sample residual arithmetic is not evidence that correction improves hardware.

Before a corrected live test, represent **desired endpoint** and **commanded
angle** separately. The current transaction verifier uses the commanded angle
as its target; blindly replacing it with a correction would evaluate the wrong
objective. Keep native admission bound to exact command bytes, use desired 1.25°
for accuracy/settling assessment, and retain a separate path excursion check that
covers the commanded path. Compare new held-out trials against the same uncorrected
controls without refitting on the held-out outcomes. No broader compensation is
enabled by this candidate. The current last reported roll is 1.230468748°.
