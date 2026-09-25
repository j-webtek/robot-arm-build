# First live base-mapping probe

## Verified outcome

The v6 wizard/native path sent one uncorrected base command and retained a
reproducible five-second capture. Endpoint arrival failed. No retry or return
was sent; serial cleanup completed without pending I/O or handle leaks.

| Measurement | Degrees |
|---|---:|
| Reported start | 0.4394531285 |
| Intended and transmitted target | 1.4394531285 |
| Requested change | +1.0000000000 |
| Reported final | 0.5273437656 |
| Reported change | +0.0878906372 |
| Final minus intended error | -0.9121093628 |

The preserved monitor verdict is `NO_RESPONSE`: its movement-detected threshold
is 0.5 degree, so this label does **not** mean zero reported encoder movement.
There were 281 post-command pose samples in 57,526 bytes. The final 250 base
samples were identical, spanning at least 4.453 seconds of host acquisition.
No other joint exceeded the 0.5-degree drift threshold; no base excursion was
reported. One 64-byte command was confirmed, with no write uncertainty.

## Provenance

- Baseline: `operation-5007f35865e64cf7999c3fbbdece9638`, zero motion-write bytes,
  expected unit identity and clean closure.
- Campaign: `campaign-69af3485692843cd959fba234e3eb200`.
- Export: `software/runs/wizard-exports/campaign-69af3485692843cd959fba234e3eb200/`.
- Parent report SHA-256:
  `7299dd35206a6c1f094c5915009183c06b0a5f68709ddc72b57c569809c5d70c`.
- Independent verification: originals valid, reconstruction consistent, endpoint
  completion false, native capture errors empty, all handles closed.
- Test reports: `base-mapping-regression-20260915.xml` (553 passed) and
  `base-mapping-additional-20260915.xml` (28 passed; overlaps the regression).

## Interpretation and next experiment

This establishes an auditable first command/response point for base, not a model.
The pinned reference conversion predicts 1.494140625 degrees for this command;
the observed endpoint differs substantially. Reference rounding alone does not
explain this particular discrepancy. Installed firmware equivalence, encoder
freshness, actual Cartesian accuracy and mechanical cause remain unverified.

Do not simply add 0.912109 degrees to the next command or copy the wrist bias.
Next characterize a separately admitted reverse-direction local probe and
repeat comparable endpoints in a matching six-joint/load/speed context. Preserve
misses as data. Only fit after repeatability and held-out prediction checks;
then compare corrected trials against uncorrected controls. No automatic
retries, increased-speed sweep, or simultaneous multi-joint move was released.
