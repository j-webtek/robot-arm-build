# First speed-10 native base trial

Predeclared scope: one increasing v15 base command after a fresh read-only
baseline. No second movement, retry, positioning move, or automatic return in
this run. Existing standing operator confirmation covers secured/clear arm,
operator presence, supplied adapter ON and USB; connection identity and fresh
six-joint pose are still verified by software.

- Desired reported endpoint: +1 degree.
- Frozen transmitted absolute target: 0.04076651868282478 rad (~2.335749466 deg).
- Speed 10, acceleration 1; only speed differs from the corrected v10 command.
- Expected base start near 0.007669904 rad; all other joints come from the fresh
  baseline and must satisfy existing model context and current admission gates.
- Five-second post capture, one-use write, unchanged 250ms selected-sample-age
  limit, endpoint/drift/excursion checks and owned serial cleanup.
- Review original export integrity, reconstruction, actual endpoint, settling,
  write age and all-six-joint drift. A missed target is retained, not corrected
  by adding another command. No speed-specific model or physical accuracy claim.

Preflight: 334 regression tests passed; 156 inapplicable old-profile combinations
skipped. Pinned vendor reference firmware and the documented unchanged-delivery
compatibility basis are recorded in the parent speed comparison plan.

Status at declaration: no baseline captured or live command sent for this trial.

## First attempt: isolated dependency omission, no command

Baseline `operation-130f2bd2d5094304a8d56ddf516c6ccf` reported the expected six-joint
pose with zero write bytes and confirmed cleanup. Staged campaign
`campaign-d7532db063fe4f939863173340f4d95c` stopped during child request validation:
`ModuleNotFoundError: No module named 'rocell.application.base_speed_experiment'`.
The deterministic native archive omitted a lazy dependency. This happened in
invocation validation, before native serial execution. There is no endpoint trial
or movement command for this attempt. It is consumed and will not be replayed.

Export report SHA256:
`fc424dc46731920386f07b9eb837092de82ff6a09dfeac4e3e335bb6dc19e307`.
Diagnostic originals verify, but there is no endpoint reconstruction to score.

Fix: include the speed specification and its timing dependency in the explicit
native archive manifest. Added real `-I -S` interpreter tests validating each
direction's v15 intent from that archive with native access forbidden. A parent
process import test alone did not exercise this lazy dependency.
Post-fix regression: **47 passed**, 248 unrelated cases deselected, including
isolated imports/validation, speed faults and wizard/native/export integration.
Report: `runs/base-speed-isolated-fix-20260915.xml`.

Separately admitted post-fix trial: re-read the current baseline, allocate a new
campaign and new source/package hashes, then allow at most the same one increasing
speed-10 command described above. This is not replay of the failed attempt and
does not authorize a return, second movement, or altered target.

## Post-fix result: one movement completed

Fresh baseline `operation-1c30000d7f0b48a0ab0c38e692845140` matched the expected
six-joint pose. New campaign: `campaign-273d8b3ec34b480f9e2be6f4865cdf02`.
Report SHA256:
`3e0f0d99b6430a0b6c040e3371be2f7ef73ec16dd47e4d57d96a01118802fea0`.

- Exactly one native submission, 63 confirmed bytes, no uncertainty.
- Start base: 0.439453128 degrees; final: 1.054687474 degrees.
- Desired: 1 degree; signed error: +0.054687474 degrees; endpoint screen passed.
- Five-second post capture: 281 parsed pose reports; seven reported transitions.
- First changed report: 515-547ms after write; final constant-run entry: 828-843ms.
- Selected baseline sample age at write: 157ms, below the unchanged 250ms gate.
- All five other reported joints unchanged; no excursion flagged.
- All handles closed, no pending I/O, cleanup within budget.
- Portable original integrity, reconstruction and endpoint-completion consistency
  independently verified through the retained-export reader.

Final reported joints [b,s,e,t,r,g] radians:
`[0.018407769,0,1.593806039,0.047553404,-0.001533981,3.149262558]`.

Machine-readable result: `runs/BASE_SPEED_FIRST_NATIVE_RESULT_20260915.json`.
Raw originals: `runs/wizard-exports/campaign-273d8b3ec34b480f9e2be6f4865cdf02/`.

Interpretation: this speed-10 observation has the same reported endpoint as the
earlier speed-20 runs. Its host-observed constant-run entry is also within the
earlier observed range. No improvement is demonstrated, and one observation
cannot establish a speed law or prove that the speed field has no effect.
No physical tip accuracy or true device sample-time claim is made.

The matched single-leg speed-10/speed-20 comparison is not complete. Earlier
single-leg v10 observations used a slightly different wrist pose; recent v14
observations used a sequence, not the same single-leg connection strategy. Do
not feed either into the strict pair comparator as if all context matched.

Next finite trial: separately stage one decreasing speed-10 command toward
+0.4 degree, only after a fresh baseline matches this actual final pose and its
existing domain gates. Review/export independently, then plan matched speed-20
single-leg references and counterbalanced repeats. No reverse command was sent
in this run. Historical base-command count is now 37.
