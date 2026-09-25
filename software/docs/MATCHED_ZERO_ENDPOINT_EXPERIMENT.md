# Matched zero endpoint experiment

Compare nominal 0-degree wrist endpoints approached from above and below,
keeping spd=20, acc=1, +/-0.5-degree tolerance and five-second captures unchanged.
Prior zero-from-above reports repeatedly ended at +0.966797 degrees.

1. Take a fresh zero-command baseline; stage fixed -4 -> 0 degrees using
   `bench_attended_campaign.py --order minus-four-then-zero`.
2. The existing native gate must accept the actual starting pose (each move
   remains at most five degrees). No bypass if the baseline differs.
3. If -4 passes, the campaign may automatically execute and evaluate zero.
   If it misses, retain the result and stop this campaign. Do not replay it.
4. A failed positioning move does not establish a valid -4 endpoint. Inspect
   its complete trace and actual final pose. Only if the miss is the known
   bounded residual, with clean transport, stable feedback and unchanged other
   joints, may a separately staged zero-from-below diagnostic be considered.
   That diagnostic requires a fresh baseline and new one-use request; it must
   not inherit a successful predecessor claim from the failed campaign.
5. Compare the zero endpoints, raw samples, vendor load range, direction,
   nominal error and reference-model error. Preserve original exports.

No tuning, EEPROM writes, compensation, overtravel or widened acceptance bands.
Controller telemetry is not independent physical tool-tip or freshness proof.
One comparison is an experiment, not a trained correction model. The next test
after a valid comparison is replication before changing any commands.

## Negative-side positioning review, 2026-09-14

Campaign `campaign-914468dcb40f4236aeb3719c0db13cbe` commanded -4 degrees from
+0.966797 degrees. The reported endpoint was -3.251953 degrees: TARGET_MISSED.
Its zero leg was skipped. The miss is preserved, not relabelled successful.
The original export verifies and reconstructs consistently (report SHA-256
`e09697f44f0662fa27cbe293845a6a86dcaa438a70f62a93c9997dddace4a687`).

Review: 64 bytes confirmed, full five-second post window (57,981 bytes), no
trial errors, no other-joint change or wrist excursion, clean native cleanup.
The final 215 frames repeated the same wrist angle for at least 3.828 seconds
by host acquisition bounds. This matches the previously observed negative
target residual, rather than an unbounded or unexplained trajectory.

A separate nominal 0 -> 4 degree diagnostic is justified for the matched-target
measurement, conditional on a newly captured baseline and the native current
start gate. This does not resume or retry the failed -4 command; it starts at
the actually reported negative angle. No compensation is applied. Its second
leg remains conditional on zero passing the unchanged criterion.

## Matched-target result: 22:45 UTC

Fresh baseline `operation-a0527d55ee8440ab9c3010fe1f442a8d` confirmed the
reported -3.251953-degree starting position. New campaign
`campaign-b722539816a44cbd957f35fc62877d4b` ran nominal 0 -> 4 degrees through
wizard operation `operation-e5df4fa345f744a890454d637cc0d538`.

| Zero-target approach | Actual reported start | Reported endpoint | Error to nominal zero | Result |
| --- | ---: | ---: | ---: | --- |
| From above (prior campaign 8692dabab46d4826a5cac99ec2c76386, leg 02) | +3.779297 deg | +0.966797 deg | +0.966797 deg | TARGET_MISSED |
| From below (current campaign, leg 01) | -3.251953 deg | -0.439453 deg | -0.439453 deg | REPORTED_SETTLED |

Separation at the same nominal target: **1.406250 degrees** (about 16 encoder
counts under the reference model). The positive and negative starts are not
perfectly symmetric. This isolates nominal target identity but does not isolate
all approach-history, load or mechanical effects. It supports an approach-
dependent reported endpoint, not a proven backlash or deadband mechanism.

The following nominal +4-degree leg passed at +3.779297 degrees. Both legs had
full five-second post windows (58,368 and 58,191 bytes; 281 and 282 samples),
confirmed writes (47 and 63 bytes), no other-joint change and no trial errors.
Native cleanup closed all handles with no pending IO. The campaign reports
ENDPOINTS_REPORTED_COMPLETE; no motion followed it. Last reported wrist: +3.779297
degrees. This is a passing joint-telemetry diagnostic, not physical-space proof.

Zero's final 223 constant-position samples spanned at least 3.968 seconds by
host acquisition bounds; vendor tT varied from -25 to -17. At +4 degrees, the
final 221 samples spanned at least 3.938 seconds with tT -13..-9. tT is not
calibrated torque and changing load is not proof of per-servo sample freshness.

Verified standalone export:
`software/runs/wizard-exports/campaign-b722539816a44cbd957f35fc62877d4b/`.
Report SHA-256: `d40dfa473010ec6ebb9921a16d4ebae9711ed4464a374518e8de311d7ccb2052`.
Independent offline verifier: valid=true, reconstruction_consistent=true,
endpoint_completion_consistent=true. Session export:
`software/runs/wizard-exports/wizard-20260914T224524418286Z-ca9527754db54938b1cd33e3fcad9ddf/`.

Software change: one fixed minus-four-then-zero bench profile; no arbitrary
target input or changed native limits. Complete/miss/cancel composition tests
now cover both signs: `software/runs/matched-zero-route-20260914.xml`, 30 passed.

## Next experiment

The minimum repetition campaign is now complete. See
[repeatability results and full attempt ledger](WRIST_ZERO_REPEATABILITY_20260914.md):
zero from above failed 4/4 at +0.966797 degrees; from below passed 3/3 at
-0.439453 degrees. No compensation was applied. The next phase is offline
model comparison and held-out experiment design, not more identical repetitions.

Replicate the zero-from-below condition before enabling any preferred-approach
policy. Its pass margin is only 0.060547 degrees, less than one encoder count.
Collect at least three independently baselined results per approach and report
range, signed bias and pass rate; do not fit or apply a universal correction.
Use separately staged bounded positioning legs where necessary, preserving
misses and requiring review before a new diagnostic. Do not command +3.779 to
-4 directly: that exceeds the five-degree per-move bound.
