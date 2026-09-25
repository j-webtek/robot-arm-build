# Decreasing base reversed-order repeat

## Predeclared procedure

Repeat the frozen +0.4-degree desired endpoint at speed 20 / acceleration 1.
Maximum two live commands: v13 uncorrected control (+0.4-degree command), then
v12 corrected (-0.684826381297-degree command). No positioning, return or retry.
Read fresh feedback before each command and independently reconstruct each export.
Proceed to correction only if the control has clean capture/cleanup and leaves
the eligible six-joint start matching the first pair within 0.01 degree.
Otherwise stop this pair and retain the result without forcing a matched start.

Expected start [b,s,e,t,r,g] radians:
`[0.018407769,0,1.593806039,0.050621366,-0.001533981,3.149262558]`.
Existing model, context, one-use admission, commanded/desired bounds and five-second
captures are unchanged. A clean control miss is evidence, not permission to retry.

Extend offline repeat aggregation with an explicit direction argument; preserve
increasing as the default and reject mixed-direction exports or reused trials.
Test before device access. Compare this reversed pair with the retained first
decreasing pair; never retrain on either pair.

This measures local encoder-reported endpoints, not physical tip accuracy or the
manufacturer's millimeter repeatability specification. After the repeat, plan
external metrology separately; do not broaden live motion in this session.

## Status

Completed: exactly two live commands, control then correction, with independent
original-export verification and fresh feedback between them. No return or retry.
The direction-aware offline aggregator and related tests passed (70 targeted tests).

## Results and original evidence

Both six-joint starts matched the first pair exactly. Desired base endpoint was
+0.4 degree. The control remained at +1.054687474 degrees; correction reached
+0.439453128 degrees. Corrected absolute error was 0.039453128 degree versus
0.654687474 degree for control: 93.973746% lower, reproducing the first pair.

- Control: `campaign-fb6182d6dd20456e879a27b95d464ad3`, report SHA256
  `c5fc927ef9fb41400b88b3dd1e94f67e6371af7d4e8811dd8368728d58ce2beb`.
- Corrected: `campaign-bd8fe09d8e73494ea5c55300dd55150c`, report SHA256
  `47142865e2c14c6e4e060d5c6405676a827ef7f7a3250a999eb5804f45a82799`.

Reports are in `software/runs/wizard-exports/<campaign-id>/`, named
`<campaign-id>-parent-report.json`. Both exports reconstructed consistently,
with no capture errors, uncertain writes, other-joint drift/excursion flags,
pending I/O or unclosed handles. Five-second captures contained 283 control and
282 corrected poses. Writes were 64 and 65 bytes, respectively. Constant final
reported tails spanned 4.922 and 4.515 seconds.

The control's `HELD / NO_RESPONSE` is an observed endpoint miss, not a transport
failure. It was reviewed, not retried. Correction passed its nominal endpoint screen.

## Two-pair assessment

[DECREASING_BASE_REPEATS_20260915.json](../runs/DECREASING_BASE_REPEATS_20260915.json)
contains pinned original selections and the independently rebuilt aggregate.
Reproduce from repository root with `summarize_base_compensation_repeats` using
the artifact's `selections` and `direction='DECREASING'`.

Both corrected trials reported identical final values, as did both controls.
Zero reported spread over two samples is not zero physical variation or global
repeatability. No coefficients were refit. The corrected final constant-value
entry was 828–844 ms in the first pair and 375–391 ms in the reversed pair;
host capture timing and actual device sampling/physical latency remain distinct.

Last reported vector `[b,s,e,t,r,g]` radians:
`[0.007669904,0,1.593806039,0.050621366,-0.001533981,3.149262558]`.

## Best next work

Freeze these local bidirectional results and avoid repeatedly testing the same
endpoint. Before claiming millimeter performance, connect independent tip
measurement to the existing capture/export pipeline:

1. Inventory existing camera calibration, marker tracking and coordinate-transform
   code; reuse it rather than add another capture stack.
2. Define an observation record linking campaign/leg, timestamp bounds, camera
   calibration hash, visible tip marker offset, measured position and uncertainty.
   Keep independently observed positions separate from firmware-computed XYZ.
3. Simulate known offsets, distorted images, occlusion, stale frames and camera
   movement. Reject uncalibrated or ambiguous measurements; never turn them into
   millimeter accuracy claims.
4. Once the static camera mount and measurement geometry are physically ready,
   validate scale and held-out reference points. A single planar image mapping
   cannot establish arbitrary three-dimensional tip position or contact height.
5. Plan bounded matched uncorrected/corrected tip measurements across multiple
   targets and repeated approaches. Report target bias, repeat spread and
   measurement uncertainty separately, with unchanged load and context.

This future measurement work does not authorize broader movements or transfer
the current base correction to unmeasured joints.
