# Matched speed-20 reference collection

## Purpose

Compare the two completed speed-10 observations against new speed-20 single-leg
observations using the same six-joint starting poses, raw targets, acceleration,
payload/protocol context, and five-second capture. Older single-leg tests differ
in wrist pose; recent speed-20 sequence runs differ in connection strategy.

Candidate originals (one per direction):

- Increasing: campaign-273d8b3ec34b480f9e2be6f4865cdf02, report SHA256
  3e0f0d99b6430a0b6c040e3371be2f7ef73ec16dd47e4d57d96a01118802fea0.
- Decreasing: campaign-a2b64fc6844c4e569fb5f7d5bb09e9c4, report SHA256
  1e0b433df333ee6aadfdfd2f5a5c2a1f70697e127e3de5c26562e83a60c0f4f7.

## Finite order

1. Fresh read-only baseline; require the actual low anchor pose:
   `[0.007669904,0,1.593806039,0.047553404,-0.001533981,3.149262558]`.
2. One existing v10 corrected increasing command, spd=20/acc=1, raw target
   0.04076651868282478 rad, desired +1 degree. No return or retry.
3. Independently verify/export; compare against the increasing candidate with
   `base_speed_comparison.compare_base_speeds`. Keep a clean miss as evidence,
   but end physical progression on any failed endpoint or other gate.
4. Only after a passing endpoint and a fresh baseline matching the high anchor
   `[0.018407769,0,1.593806039,0.047553404,-0.001533981,3.149262558]`,
   separately stage one v12 decreasing corrected command, spd=20/acc=1,
   raw target -0.011952475158143525 rad, desired +0.4 degree.
5. Verify/export and compare against the decreasing candidate. End the run.

At most two movement commands, independently admitted. No extra positioning to
force an eligible start, no threshold widening, no speed change within a command,
and no automatic corrective move. Each serial session owns its fresh baseline,
single write, capture and cleanup. Actual matched starts, not nominal anchors,
determine comparison eligibility within the existing 0.01-degree matching rule.

## Interpretation and later repeat

Preserve signed/absolute endpoint errors, transitions and host-acquisition bounds,
write age and cleanup. Equal endpoints mean no demonstrated endpoint improvement,
not proof that speed cannot matter. Do not infer physical rates from USB timing.
Report the first pair even if it is unfavorable. A later separately declared
repeat should reverse speed order (20 before 10) to investigate order effects;
that repetition is not included in this two-command plan.

Status: ready for the next finite run; no reference command sent yet.

## Completed: two reference commands

Both planned references completed, independently admitted and reconstructed from
portable originals. No extra positioning, retry, recovery, or configuration
change. Both matched comparisons passed their same-start/context/target checks.

| Direction | Speed 10 final deg | Speed 20 final deg | Absolute error at either speed deg | Speed 10 final constant entry ms | Speed 20 final constant entry ms |
| --- | ---: | ---: | ---: | --- | --- |
| Increasing | 1.054687474 | 1.054687474 | 0.054687474 | 828-843 | 875-891 |
| Decreasing | 0.439453128 | 0.439453128 | 0.039453128 | 860-875 | 813-828 |

Endpoint error reduction was exactly zero for each pair. Host-observed timing
differences went in opposite directions; neither setting has demonstrated a
consistent timing advantage. These are acquisition bounds, not physical speed
measurements. One pair per direction cannot establish equivalence or repeatability.

Increasing baseline: `operation-a621f9cde56f46d6b8ab96735121fac9`.
Reference: `campaign-f52f146beeaa478cb2c6814148096bd1`.
Report SHA256: `a670780a6315c2b987ec4f9bc1c4a4eede2002eeaa14cd362da6b4b1abaee4f1`.

Decreasing baseline: `operation-1a1ddd62de424d649deaff46e6e285e7`.
Reference: `campaign-5eed8b201c0744d5b9ca234e487c0f46`.
Report SHA256: `b0bdfe26bbee0edda45ede480c173b2bc7913e5b14f8c9548fbc9e6879a5a6d6`.

Each baseline captured zero command bytes. Each campaign made exactly one
submission (63 increasing / 65 decreasing bytes), without uncertainty. Selected
sample ages at write were 140ms and 156ms. All five other reported joints remained
unchanged; all handles closed with no pending I/O within the cleanup budget.
Portable integrity, reconstruction and completion checks passed for each.

Machine-readable paired observations and native accounting:
`runs/BASE_SPEED_MATCHED_REFERENCES_20260915.json`.
Raw originals remain in their campaign folders under `runs/wizard-exports/`.
Final joints [b,s,e,t,r,g] radians:
`[0.007669904,0,1.593806039,0.047553404,-0.001533981,3.149262558]`.
Historical base-command count: 40.

## Next finite repeat (not executed)

Reverse the setting order: speed 20 increasing, speed 20 decreasing, then
speed 10 increasing, speed 10 decreasing. At most four separately admitted
single-leg campaigns, each with a fresh baseline, endpoint/export review and the
same fixed targets, acceleration 1 and five-second captures. Stop immediately
on a failed endpoint or admission gate; no positioning or retry. Match the two
new same-direction observations using the existing original-export comparator.
Keep these new pairs distinct from the first pairs; do not reuse trials to inflate
the sample count. Report both repeats regardless of outcome, then decide whether
this speed range merits more testing. No larger route or faster value is included.

Update: the declared reversed-order repeat is now complete: four of four
movements passed with identical directional endpoints at both speeds. Both old
and new pairs were rebuilt from eight distinct original exports. No consistent
timing or endpoint advantage appeared. See `BASE_SPEED_REVERSED_REPEAT_20260915.md`.
Retain the existing speed-20 default; this local comparison is complete.
