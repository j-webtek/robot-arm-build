# Endpoint verification update

The existing native command/capture path now includes a software-only endpoint
summary reconstructed from the retained joint reports. It separates movement,
entry into the target band, final position inside that band, and quiet settling.
The wizard displays the summary when the full observational result is loaded.
Old retained records without this schema display verification unavailable;
they are not silently upgraded or rewritten.

## Criteria

- Existing provisional arrival tolerance remains +/-0.5 degrees.
- Quiet reported wrist span must be at most 0.1 degrees for at least 200 ms,
  while remaining inside the arrival band. These are diagnostic thresholds,
  not physical safety limits or calibrated precision specifications.
- Host read intervals bound dwell; batched identical samples do not invent time.
- A later departure or renewed oscillation invalidates final settled status.
- Invalid/gapped feedback, transport faults, wrist excursions or other-joint
  changes take precedence over endpoint success.
- A visual confirmation cannot override a failed software endpoint check.

Possible summaries: REPORTED_SETTLED, TARGET_MISSED, NOT_SETTLED, NO_RESPONSE,
FEEDBACK_INVALID, OTHER_JOINT_CHANGED, WRIST_EXCURSION, TRANSPORT_FAULT.
These classify completed captures, not a new live-stream UI or servo watchdog.

## Evidence and limits

Offline reanalysis (without changing original trial records) classified
`22687c57cccb43e8a0f0811e8ec905b6` and
`dd8557b674a5490dabdeb5b5f147b24f` as REPORTED_SETTLED, and
`8782fb2d9d024ddaa58b0c68a07e2f8f` as TARGET_MISSED.
No compensation, PID, EEPROM, speed or tolerance relaxation was applied.

The verifier is included explicitly in the isolated native-worker package.
The first regression run caught the missing package member; it was corrected
before any hardware test. See the subsequent -02 regression report.

Final regression: **312 tests passed in 57.74 seconds**, including isolated
worker imports, observational evidence checks, endpoint faults/dwell boundaries
and wizard UI tests. Report:
`../runs/wrist-endpoint-verification-20260913-02.xml`.
`node --check software/src/rocell/ui/static/app.js` also passed. The new panel
has not received a separate visual browser inspection in this turn.

## Remaining work, not claimed complete

Automatic command sequencing and early termination of the capture on settling
are **not enabled**. The existing one-use permit remains one command, and the
full five-second capture is retained to reveal subsequent departure/oscillation.
A live sequence will need a separately bounded multi-leg authority and fresh
identity/baseline checks at each leg; it must stop on any target miss instead of
replaying or issuing a correction. The current directional shortfall remains
unexplained and is not fixed by this verification improvement.

## Live verification

After tests, a fresh source-bound wizard staged and sent one +5-degree wrist
trial, `operation-03dee735dac54417924486aeb34377f8`, spd 20, acc 1.
The revised verifier returned **REPORTED_SETTLED**: movement detected, target
band entered, final position in band, quiet dwell verified. Final reported
error was -0.0059654806 rad (about -0.342 degrees). No other-joint change or
wrist excursion was detected. This verifies the new software result path;
independent physical accuracy and servo-sample freshness remain unverified.
No automatic second command was issued. Diagnostic logs were exported.
