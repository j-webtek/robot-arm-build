# Prospective +2-degree matched pair

## Result

Frozen zero-target model was tested on newly collected nominal +2-degree
commands, without retraining or compensation. Both prediction errors meet the
predeclared <=0.25-degree screen on this first pair. This is not completion of
the planned repeatability study and does not establish corrected-command accuracy.

| Approach | Actual start | Frozen direction prediction | Reported final | Prediction residual | Nominal error | Nominal result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| From above | 3.779297 deg | 2.966797 deg | 2.900391 deg | -0.066406 deg | +0.900391 deg | TARGET_MISSED |
| From below | 0.966797 deg | 1.560547 deg | 1.669922 deg | +0.109375 deg | -0.330078 deg | REPORTED_SETTLED |

| Frozen model | Pair MAE | Pair RMSE | Maximum prediction error |
| --- | ---: | ---: | ---: |
| Nominal | 0.615234 deg | 0.678106 deg | 0.900391 deg |
| Constant bias | 0.615234 deg | 0.615609 deg | 0.636719 deg |
| Direction bias | 0.087891 deg | 0.090478 deg | 0.109375 deg |

Sample count is one per direction; telemetry frames are not extra trials.
The observations support limited transfer of the direction-conditioned model
from zero to +2 degrees in this setup. They do not prove the mechanism, servo
freshness or tool-tip position. Starting distances differ between approaches.
The failed nominal endpoint remains failed even though the model predicted it.

## Execution ledger

All commands used wrist joint 4, spd=20, acc=1, unchanged nominal +/-0.5-degree
tolerance and five-second observation. Three separate baselines and campaigns
were used. Every failed campaign stopped before a newly reviewed one began.

1. Baseline `operation-1e4c44c916ef40f9afed4aaf32dadaab`;
   campaign `campaign-7571a57e10014fe9a02c558dd92b149c`:
   nominal +2 from above missed; planned zero leg skipped. One confirmed
   63-byte write; 57,784 post bytes, 281 pose samples, final constant tail
   at least 4.235 s. Report SHA-256
   `ea140079be6ab9df0ae14231f59f4c2b10a22a868221449914a2fd4a20ac0b89`.
2. Baseline `operation-a04ea764736e4a98ba38ebdef7c8e433`;
   campaign `campaign-fb530fdb4c4346f1b7f615f243bc2506`:
   separate nominal zero positioning ended at +0.966797, a known bounded miss;
   planned +2 leg skipped. One 47-byte write; full capture, 57,408 bytes,
   constant final tail at least 4.406 s. This miss was retained and reviewed,
   not marked successful. Report SHA-256
   `23c7f7e3d8dc8eae1e8aeefc5134a0b73c18c67666a4b0bac8370d7638aaf355`.
3. Baseline `operation-f8f89d4eece248daacfa2263ebe5dcd3`;
   campaign `campaign-5afa454e84c24f95b2f7f3c0d7b92fbf`:
   new +2 from below passed, followed by explicitly planned +4, also passed
   at +3.779297 degrees. Two 63-byte writes; full captures of 57,910 and
   57,975 bytes, 281 and 280 samples. Report SHA-256
   `a0c3e7e68bf46f814df82aa455620fad610f6cf4a8958794198d47bbe02c1ab1`.

All three exports independently verify and reconstruct. No trial errors,
other-joint changes or wrist excursions; owned handles closed, no pending IO.
Original bundles are under `software/runs/wizard-exports/<campaign-id>/`.
Final session export:
`software/runs/wizard-exports/wizard-20260914T230937751170Z-8a95f32d93f845c0b329aa3e1f3959be/`.
Last reported wrist: +3.779296882 degrees. Motion stopped after that campaign.

## Software and reproducibility

Fixed bench profiles added: two-then-zero, zero-then-two and two-then-four.
No unrestricted target input or changed native motion limit. Simulated
complete/miss/cancel/start-mismatch composition plus existing authority/child
tests: `software/runs/two-degree-routes-20260914.xml`, 51 passed.

Frozen model artifact: `software/runs/WRIST_ENDPOINT_MODEL_COMPARISON_20260914.json`.
SHA-256 checked before scoring:
`82a4f18803b4963d192b216149066951a7c277ef6c2e5aae2e398c7b6c4a7fc6`.
Derived score: `software/runs/TWO_DEGREE_PROSPECTIVE_SCORE_20260914.json`.
Scoring uses verified executed target_rad=radians(2) endpoints only. Predicted
final = 2 + frozen bias; residual = reported final - predicted final. Score
the two directions separately and pooled. The intervening zero positioning
trial and conditional +4 leg are retained but excluded from the +2 score.
Training manifest and fitted model remain unchanged.

## Next

The two additional pairs are now complete. See
[full repetition results](TWO_DEGREE_REPETITION_RESULTS_20260914.md) and
`software/runs/TWO_DEGREE_REPETITION_SCORE_20260914.json`. The frozen model met
the prediction screen across three trials per direction. Compensation remains
disabled; a separately bounded correction proposal is the next development step.

Repeat the same nominal +2 matched pair twice more, preserving the frozen model,
commands and acceptance criteria, before considering a correction experiment.
No compensation or parameter tuning has been enabled. Baseline-framing
diagnostics remain a separate software improvement, not a reason to alter these
experiment controls.
