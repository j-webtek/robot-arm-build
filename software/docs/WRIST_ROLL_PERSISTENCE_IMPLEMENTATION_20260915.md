# Wrist-roll persistence implementation status

## Implemented and verified

`software/src/rocell/arm/endpoint_persistence.py` provides read-only analysis of
validated six-joint rows from a single uninterrupted capture. It does not open
hardware, authorize commands, attest original-byte integrity, or prove connection
provenance. Native callers must supply those guarantees separately.

- Separate host-observation horizons at 5, 10, 20 and 35 seconds.
- Existing endpoint monitor reused for early and whole-window checks; historical
  five-second campaign decisions remain unchanged.
- Early/final error, full observed min/max, maximum departure after five seconds,
  bounded transition details, and all-other-joint drift.
- A 0.01-degree persistence screen, separate from the existing 0.5-degree arrival
  band and 0.1-degree quiet-dwell span. This flags the observed ~0.088-degree
  change; it is not an assertion of physical accuracy at 0.01 degree.
- Distinct persistent, changed, incomplete, malformed, transport-fault, cancelled,
  and endpoint-not-verified outcomes. A change followed by return stays flagged.
- At most 4096 pose rows, 16 displayed transitions, and a 35-second input horizon.
  A host read gap/interval greater than 250 ms prevents complete coverage. A read
  spanning a horizon is not assigned to the earlier horizon.

Validation: **105 tests passed** (30 persistence tests plus 75 existing roll,
discovery and review tests). JUnit report:
`software/runs/roll-persistence-analysis-regression-20260915.xml`.

Replayed the actual second-point capture from its verified originals. Its early
endpoint remains REPORTED_SETTLED, while 35-second persistence correctly reports
OBSERVATION_INCOMPLETE. No later reconnected capture was spliced into this stream.
Derived evidence: `software/runs/WRIST_ROLL_PERSISTENCE_REPLAY_20260915.json`.

## Native integration update

v18 is now implemented: 35-second post capture, 39-second leg, 50-second campaign,
512 KiB post bytes, 4096 post reads, one write. The native supervisor reserves
47 seconds before launch and has a 48-second run / 2-second cleanup budget.
Admission, decoder capacity, retained records, reconstruction, isolated packaging,
wizard service, CLI and axis/duration preview support the new profile. v16/v17
limits and meaning remain unchanged. Persistent results pass; changed endpoints
are retained as HOLD with early/late evidence and no subsequent command.

Validation: broader suite 320 passed / 156 inapplicable combinations skipped;
three added v18 supervisor cases passed; final focused native/package/wizard
run 29 passed / 337 deselected; JavaScript syntax check passed. A supervisor
reservation bug found by the new deadline test was corrected before hardware.

First live scope: at most one decreasing one-degree roll command from fresh
feedback matching the last measured six-joint pose (r=0.016873789 rad), then
35 seconds without closing that serial connection. No return/retry/positioning.
If the baseline differs, reassess without a command. Independently reconstruct
the export before any further activity. A subsequent zero-command capture may
be used as a separately labelled reconnect comparison, never spliced into the
continuous trial. Standing user setup confirmation applies.

Physical validation: first v18 attempt held before request delivery; see the
failure/correction record below. The corrected v19 profile subsequently completed
its first one-command 35-second run with verified original reconstruction and a
matching separate reconnect baseline. See [live results](WRIST_ROLL_PERSISTENCE_LIVE_20260915.md).

## First launch result and versioned correction

The v18 launch `campaign-86a06585eeb04c529b108bdd89562714` failed before child
request delivery. Supervisor originals report zero stdin bytes, empty stdout and
stderr, zero retries, confirmed process-tree exit and no cleanup errors. No
campaign claim/trial or endpoint exists. No arm command was dispatched. The
preceding feedback-only baseline matched r=0.016873789 rad and all other joints.

Retained export:
`software/runs/wizard-exports/campaign-86a06585eeb04c529b108bdd89562714/`.
Report SHA256: `d652074e4b3db6546c72aaca627a34287c985482c611a026000c8b510240b34c`.
Portable verification passes original integrity (five originals); endpoint and
trial reconstruction are false because no motion trial occurred. This must not
be presented as a successful 35-second physical observation.

Timing diagnosis: failure completion was 3.281 s after acceptance, leaving 46.719 s
of the 50 s lifetime. Prelaunch requires 47 s. A deterministic test reproduces
that reservation rejection. The generic retained ValueError does not identify
its exact throw site, but the timing identifies an independently reproducible
launch-budget defect. No physical motion limits or observation duration need
loosening to correct it.

**Current staging uses v19**, with a 60 s campaign lifetime and 58 s supervised
run budget plus 2 s cleanup. The 47 s prelaunch reserve, 39 s leg, 35 s observation,
one command, geometry, speed, acceleration and all byte/read limits are unchanged.
Only preparation allowance increased. v18 retains its original 50 s / 48 s values
so the failed original remains verifiable. No automatic retry or replay occurred.

Final focused versioned tests: **38 passed / 331 deselected**, including both
versions in the isolated interpreter, v18/v19 supervisor dispatch/deadline cases,
long native-shaped capture/export, delayed-change holds, wizard execution and
no-replay behavior. Report:
`software/runs/roll-persistence-versioned-launch-regression-20260915.xml`.

Next physical step is a fresh baseline and separately admitted v19 decreasing
one-degree test, followed by the full same-connection observation. Do not reuse
the old attempt or manufacture endpoint evidence from its failed launch. Roll
motion command count remains seven; base remains 44. No compensation was fitted.

## Original integration checklist (now implemented)

The analyzer-only first step sent no movement. Native integration above was added
in the subsequent step; live results must be recorded separately below.

## Next native integration, in dependency order

Create a separately versioned, one-write roll-persistence profile; leave v16/v17
unchanged. Its initial command should remain the existing bounded one-degree roll
probe from a fresh current pose, not an arbitrary target input.

| Boundary | Current constraint | Required new-profile work |
| --- | --- | --- |
| Intent/runtime limits | 5 s post, 8 s leg, 30 s campaign | Explicit 35 s post, approximately 39 s leg and 50 s campaign; prove reservation arithmetic and cleanup slack |
| Campaign collector | Hardcoded 5000 ms | Read version-bound post duration; old profiles retain 5000 ms |
| Byte/read budgets | 80 KiB post, 512 reads | Profile-only candidate 512 KiB post and 4096 reads; bounded overflow must hold, never truncate into success |
| Telemetry decoding | Allowed byte budgets up to 98304, 512 windows | Add explicit extended budget domain without widening old defaults; reject oversize, malformed and sparse captures |
| Native supervisor | 28 s for ordinary profiles | New profile-specific process timeout aligned with intent; no global timeout increase |
| Admission and reconstruction | One post endpoint decision | Preserve 5 s result, add separately derived full-window persistence, and reconstruct both from original bytes |
| Export/package | Explicit source package and retained-size limits | Include analyzer, validate aggregate encoded sizes, and exercise real isolated interpreter imports |
| Wizard/service/CLI | Existing relative/fixed probe choices | Explicit persistence choice and bounded duration preview; one use, no extra writes or return |

The budget numbers above are proposed constants, not active permissions. A 35 s
stream at the observed ~11 KiB/s needs about 385 KiB raw storage, but encoded
trial/window metadata also counts toward retention limits. Validate worst-case
supported limits, not just expected traffic.

Before release, test a delayed step within the same connection, continuing drift,
other-joint movement, cancellation, stale/late/malformed input, empty/gapped
telemetry, read/byte exhaustion, write uncertainty, and cleanup failure. Preserve
raw data from clean endpoint changes and misses. Do not let a positive early
endpoint allow another command while the long observation is pending.

Run the new profile once only after native-shaped execution, deterministic export
reconstruction, wizard tests and actual isolated-package tests pass. Compare the
same-connection late endpoint with a separately labelled reopened baseline.

Current last reported roll is 0.016873789 rad. The old v17 anchors do not match it.
Re-read all six joints before choosing the new profile's direction; do not send
an old fixed-anchor command as a positioning shortcut. There is no need for new
routine user confirmation while the standing setup remains unchanged.
