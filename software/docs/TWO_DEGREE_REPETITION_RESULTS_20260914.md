# +2-degree prospective repetition results

## Completed outcome

Three matched pairs are now complete: the original pair and two further pairs.
All six nominal +2 measurements were scored against the same frozen model,
without retraining, tuning, compensation, tolerance changes or source changes
during these repetitions. Every original export independently verifies and
reconstructs. No further physical movement was attempted after the final campaign.

| Approach | Trials | Reported final, all trials | Nominal signed error | Nominal passes | Frozen prediction error magnitude |
| --- | ---: | ---: | ---: | ---: | ---: |
| From above | 3 | 2.900390625 deg | +0.900390625 deg | 0/3 | 0.066406269 deg |
| From below | 3 | 1.669921877 deg | -0.330078123 deg | 3/3 | 0.109375005 deg |

Reported final range and sample SD within each group were zero at the available
telemetry resolution. This is not zero physical variance or a reliability
guarantee. One trial is one endpoint, not each of its hundreds of frames.

| Frozen model | Six-trial MAE | RMSE | Maximum absolute prediction residual |
| --- | ---: | ---: | ---: |
| Nominal | 0.615234 deg | 0.678106 deg | 0.900391 deg |
| Constant bias | 0.615234 deg | 0.615609 deg | 0.636719 deg |
| Direction bias | 0.087891 deg | 0.090478 deg | 0.109375 deg |

The direction model meets the predeclared <=0.25-degree per-direction maximum
prediction residual and lower pooled MAE than both baselines for this dataset.
The nominal above-side misses remain misses. Predicting an error well does not
demonstrate that subtracting it from the command will improve actual positioning.
The encoder reports do not independently verify servo-read freshness, tool-tip
accuracy, deadband or backlash as the mechanism.

## Complete six-trial score

Derived report: `software/runs/TWO_DEGREE_REPETITION_SCORE_20260914.json`.
It includes each campaign/report hash, actual start, target, endpoint, pass/fail,
prediction residual and pooled/per-direction metrics. Only executed nominal
+2 endpoints are scored; zero-positioning and conditional +4 legs are retained
but excluded from this target's score.

Frozen model SHA-256, verified again before scoring:
`82a4f18803b4963d192b216149066951a7c277ef6c2e5aae2e398c7b6c4a7fc6`.
The original one-pair score and model artifact were not overwritten.

Original pair:

- Above: `campaign-7571a57e10014fe9a02c558dd92b149c`, leg-01.
- Below: `campaign-5afa454e84c24f95b2f7f3c0d7b92fbf`, leg-01.

## This turn's attempt ledger

Six separately baselined campaigns; eight confirmed motion writes. Same wrist
joint, spd 20, acc 1, five-second captures and nominal +/-0.5-degree tolerance.
Failed campaigns stopped. Their traces were reviewed before a new baseline
and new one-use diagnostic were prepared; no failed predecessor was relabelled
successful, resumed or automatically retried.

| Campaign suffix (all prefixed campaign-) | Role/outcome | Writes | Report SHA-256 |
| --- | --- | ---: | --- |
| e0502846158d4bc7935dabbf73f6fd73 | +2 above, missed; zero skipped | 1 | 203763dfcf78f6f8823994175d3667c0774ac397a97f2bfecfb1fe8ed4a1c20b |
| f4f13abcf6eb42ea987f25daae1f8f2d | Zero positioning, +0.966797 missed; +2 skipped | 1 | b56e98868865f1d2c20e53829345d7c1d5f6c0bd6b2eeb9102c3539b7760c80e |
| e81d1945ce91429abfa4551f5bd89e12 | +2 below and conditional +4 passed | 2 | a3c8fde7edd90a8673222352e14126e82c0bd09afe51ba73db71d469c647c9e5 |
| 59ab2a8acf144de8b952f244be03a70d | +2 above, missed; zero skipped | 1 | 6137413d79e9fc773c830785e1f6e7345f87ec544adc6300d83d5ce549000ea7 |
| 507096427bca4ccbb452d3b9fa44cd2e | Zero positioning, +0.791016 missed; +2 skipped | 1 | 7ac38d047299f41b08051be72f3815b6070cef80255e20a803172f208e959ec9 |
| 412a7d8918d64a8eac103d847e9829b7 | +2 below and conditional +4 passed | 2 | 83e302021451518b2a3d7cfd7e253a1db78481ec21212111946b10f61230777d |

Original bundles: `software/runs/wizard-exports/<campaign-id>/`.
All eight post-command windows completed; there were no trial errors, uncertain
writes, other-joint changes or wrist excursions. Owned handles closed and no
pending IO remained after each campaign. Final session export:
`software/runs/wizard-exports/wizard-20260914T231902321249Z-5471c14319fe48e6bf1605ef08191dca/`.
Final reported wrist: +3.779296882 degrees. No new unit tests were required or
run this turn because executable software was unchanged; this was hardware
validation and offline scoring of the previously tested routes.

## Variation retained rather than discarded

The final zero-positioning trial ended at +0.791016 degrees rather than the
previous +0.966797. Its final 242 frames were constant for at least 4.328 s,
with no other-joint change and clean transport. A fresh baseline confirmed it.
The final +2-from-below trial therefore started at +0.791016; the first two
started at +0.966797. All satisfy the preregistered below-side bound (<+1.5 deg).
This departure is included, not selected out; it illustrates why earlier
identical final reports should not be generalized into a claim of no variation.
The fitted model was not changed using the intervening zero-positioning results.

## Next development step

The offline proposal and nominal-versus-command simulation are now implemented;
see [bounded correction proposal](MODEL_CORRECTION_PROPOSAL_20260914.md).
Native integration and corrected hardware testing remain separate, unfinished
steps. This update does not enable compensation in the wizard.

Prepare an offline, explicitly bounded correction proposal, with nominal task
target distinct from transmitted servo target. Validate direction preservation,
actual-start delta, joint limits, representable counts, and immutable provenance
in simulation. Score success against the nominal task target, not the shifted
command. Keep correction proposals disconnected from execution by default.

Then design one separately reviewed corrected-command experiment with an
uncorrected comparison, full telemetry and no iterative convergence/retry.
The corrected target changes the mechanical response and must be measured;
these data do not authorize a general correction policy. Preserve current
motion/cleanup holds. Do not adjust PID, EEPROM or tolerance to manufacture a pass.
