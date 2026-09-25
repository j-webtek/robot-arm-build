# Wrist directional error: saved-evidence recheck

## Result

Re-ran the saved-source assessment against two retained zero-from-above trials:

- `operation-b9fae47e71b8403ca09a916f85f4dcca`
- `operation-b77390c8f95b4aa190770b904e407941`

Both started at reported wrist angle 3.779296882 degrees, requested zero, and
ended at 0.966796894 degrees. The final reported angle remained constant for
3.906 and 3.953 seconds respectively (281 and 282 total samples). This supports
a repeatable local bias, not merely an endpoint sampled before settling.

The assessment reconstructed the saved evidence successfully and produced
`OFFLINE_EXPERIMENT_CANDIDATE`, proposal SHA-256:
`f2e5c9cf1ec3993fd5a5469447ec8c7c67284b2fc5375698a82ec52a736e3afb`.

## Interpretation and limits

The discrepancy is 11 reference encoder steps. Zero is exactly representable,
so ordinary target quantization cannot account for this residual. The existing
opposite-approach trial ended at -0.439453128 degrees, making approach dependence
the important experimental variable. This does not isolate backlash, friction,
servo deadband, loading, or stale device feedback as the root cause.

Repeated host samples do not prove fresh servo reads. The saved-source loader
checks consistency, not authenticated physical provenance. Encoder agreement
also does not establish tool-tip accuracy on the board.

## Next controlled experiment

The local constant-bias hypothesis proposes a motor target of -0.966796875
degrees (reference register 2037), while the desired endpoint remains zero.
This is an unvalidated candidate, not a calibrated correction or a general
offset for other poses, loads, speeds, or directions. Its near-zero predicted
residual is algebraic cancellation of the measured bias, not a measured result.

1. Finish binding the wizard's staged runtime and final review to these exact
   originals and the selected controller.
2. Rehearse the full path without hardware, including stale evidence and cleanup
   failures; preserve logs even when the endpoint fails.
3. Obtain a fresh baseline matching the historical starting pose through the
   bounded movement workflow. Do not apply the candidate from an arbitrary pose.
4. Run one candidate command at the same speed/acceleration and compare fresh
   endpoint telemetry with the nominal zero target. Stop on failure; no automatic
   correction retry.
5. Only after that result, compare repeatability and opposite approaches before
   deciding whether a direction-conditioned correction is justified.

No hardware connection, movement, firmware write, or servo-setting change was
performed during this recheck.
