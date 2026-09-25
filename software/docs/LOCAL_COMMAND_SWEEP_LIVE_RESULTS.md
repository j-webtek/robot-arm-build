# First local command-spacing sweep: incomplete hold on final probe

Session `e784590de9be4024a88297a0bb8ef335` attempted all twelve planned movement
legs. Eleven passed full endpoint/unchanged-hold/export review. The final probe
passed endpoint replay but its subsequent read-only hold failed, so the session
stopped and remains incomplete. No retry, return or corrective command was sent.

## Probe results

All probes descended from reported roll 2.285156222, with desired 1.25 degrees,
speed 20 / acceleration 1. Each had its own high positioning leg and fresh baseline.

| Command (deg) | First result | Repeat result | Full holds verified |
| --- | ---: | ---: | ---: |
| 0.85 | 1.142578111 | Arrival 1.142578111; hold incomplete | 1 of 2 |
| 0.95 | 1.230468748 | 1.230468748 | 2 of 2 |
| 1.05 | 1.230468748 | 1.230468748 | 2 of 2 |

All successfully completed holds had unchanged reported joint positions. A
0.10-degree command increase from 0.95 to 1.05 produced no reported endpoint
difference in these four trials. This is an observed local response plateau,
not proof of deadband, encoder resolution, backlash or a firmware defect.
Older 0.95-command outcomes include 1.406250023 and remain part of the evidence;
the new samples do not erase that variation or establish a unique inverse map.

At desired 1.25, errors for the two reported endpoints are -0.107421889 and
-0.019531252 degrees. These are controller joint errors, not physical tip errors.
No compensation candidate was updated or globally enabled. These are
characterization probes, not extra held-out lookup validation trials.

## Final failure

Final export:
`wizard-20260917T032028360335Z-be9aaa7fb7de41809a84988617b7718b`.
Export integrity passed and original movement feedback independently reproduced
`REPORTED_ENDPOINT_VERIFIED` at 1.142578111 degrees.

The separate hold collected 91 successful responses spanning 26.303616 seconds,
then its 92nd request failed: TIMEOUT during REQUEST_SEND, shared HTTP deadline
budget 0.8 seconds. Hold elapsed time was 27.410395 seconds. Its last successful
sample was still 1.142578111 degrees with no recorded joint change. The hold is
not complete and must not be counted as a second fully verified 0.85 sample.

The session's generic `CALLBACK_OR_EVIDENCE_ERROR` label arose when the reviewer
rejected the failed hold; the original export provides the more specific cause.
The arm's position after the last successful read is not independently known.
No later observation or command was sent in this turn.

## Audit and artifacts

All eleven successful legs were independently re-reviewed after the process
exited. Final export integrity and endpoint replay were checked separately.
The header and 49 event files with prefix
`comparison-e784590de9be4024a88297a0bb8ef335-` under
`software/runs/wizard-exports` passed sequence and hash-chain checks. Final event
is FINISHED / STOPPED / reviewed_legs=11, not COMPLETED. Its file SHA-256 is
`5f10e525704d665f81d656f62a563b41e429689cdd7fc43231f5126fe13b1d90`.

`LOCAL_COMMAND_SWEEP_EVIDENCE.json` records all six probes, separating the failed
hold. Each export and its predecessor/manifest hash is retained in the journal.
The first ten transitions accepted by the runner were 20.880925–20.950620 seconds.
The final leg did not reach full review and is not included in that accepted
transition range. Host/process identity remains recorded rather than independently
attested boot identity. Hashes detect changes but do not authenticate hardware.

## Next useful work

First expose the hold timeout explicitly in the compact reviewer/session report
so an incomplete hold is not hidden behind a generic exception. Add regression
tests preserving a verified initial arrival while denying full-hold completion.
This is reporting improvement, not a reason to loosen deadlines or retry motion.

For physical follow-up, use a separate fresh read-only health check and a newly
admitted bounded trial if appropriate; do not resume this consumed sweep or
silently replace the failed record. Keep the plateau finding descriptive. Before
building fine inverse compensation, compare richer servo feedback or independent
position measurements rather than inferring sub-step precision from these six
commands alone.

The reporting improvement is now implemented; see `INCOMPLETE_HOLD_REPORTING.md`.
Replaying the final export preserves its verified arrival and explicitly reports
the hold timeout, while retaining nonzero failure status. The historical stopped
session and incomplete sweep classification are unchanged.

## Separate 0.85-degree follow-up completed

A new high positioning leg and separately admitted 0.85 probe both passed full
original endpoint/hold reconstruction and export integrity. Neither command was
a retry of the consumed sweep reservation. The original session remains stopped.

- Positioning export: `wizard-20260917T032640916595Z-d2842cbf37784f228533b16cf76c1423`.
  Fresh start 1.142578111 degrees; command 2.5; endpoint 2.285156222. All six joints
  unchanged over 119 hold responses spanning 34.730974 seconds. Manifest SHA-256
  `1b7c8749f459bcbe31a2058577f37e81a062569802146f76d15355c853e0705e`.
- Probe export: `wizard-20260917T032746522159Z-b4027a972a934b6882ed3b2f35f77354`.
  Fresh start 2.285156222; command 0.85; desired 1.25; verified endpoint and entire
  hold 1.142578111 degrees, error -0.107421889. All six joints unchanged across
  122 hold readings spanning 34.836074 seconds, maximum gap 450.8695 ms. Manifest
  SHA-256 `0717e6ec814c446ce3189ffbc7d6fbce4d657a6196a3b0878f6449798d863638`.

The measured predecessor-hold-to-dispatch interval was 28.874544 seconds, outside
the sweep's proposed timing window. This was a standalone follow-up, not a timed
sweep continuation. Preserve that distinction when comparing repetitions. No
narrow-band criterion was relaxed: the -0.107421889 error still fails both
illustrative +/-0.05 and +/-0.10 bands despite a stable full hold.

Across the original sweep and this separate follow-up, two completed 0.85 holds
report 1.142578111, with the interrupted arrival retained separately. This does
not repair the original six-probe completeness flag or establish zero physical
variation. The evidence JSON stores the follow-up outside its original probes.

Next consolidate the local response data, including older variable 0.95 outcomes,
and inspect which additional servo fields are actually retained and trustworthy
before choosing another movement experiment. Avoid endlessly refitting offsets
or declaring the reported plateau a mechanical diagnosis. Independent tool-tip
measurement remains necessary for Cartesian accuracy claims.

Latest reported roll: 1.142578111 degrees. No final return or correction was sent.
