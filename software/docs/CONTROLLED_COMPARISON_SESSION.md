# Finite comparison-session core

Implemented `src/rocell/arm/comparison_session.py`. This is a tested scheduling
core with injected callbacks, not a live wizard action. No hardware was accessed
or moved during implementation. No timing requirement was added to ordinary
single-leg motion; the proposed 18–22 second window applies only to this experiment.

## Implemented behavior

- Exactly two blocks: high, center_down, high, lookup, repeated once (eight legs).
- The same frozen descending 0.95 command for desired 1.25, speed 20 / acc 1.
- One-use session object; re-entry or concurrent reuse is rejected. No recovery
  from serialized logs, retry, return, refit or unbounded continuation.
- Event sink must persist START and LEG_INTENT before executing a leg. The sink
  receives copies so it cannot mutate the scheduler's evidence through events.
- Execute one leg; retain its export path before independent review. Check exact
  protocol, candidate, one attempt, endpoint/hold success and distinct export ID.
- Link the predecessor's manifest hash and compare its hold-final pose with the
  next fresh baseline. Review finishes before scheduling another command.
- Schedule at previous hold completion plus 20 seconds. Check the proposed window
  before dispatch, again after intent publication, and against actual dispatch
  timing from the completed export. A missed window stops further progression;
  it never rewinds or retries a command that already happened.
- Check host-clock ordering and that exported dispatch/hold times fit the executor
  call. Tag events with a unique session ID and ONE_RUN_INVOCATION clock scope.
  This is not an independently verified Windows boot identity.
- Exceptions stop with bounded failure labels, without raw exception/response
  text. Failure of final event storage prevents a successful completion report.

## Simulation verification

40 focused tests passed across the session core, block auditor and export reviewer.
Virtual-clock simulations cover successful eight-leg completion, predecessor
links, reuse rejection, cancellation, execution failure, export-review failure,
endpoint failure, wrong command, baseline mismatch, review taking too long,
actual dispatch lateness, slow intent publication and final storage failure.
Tests import no native sender and perform no physical actions.

## Required integration before live execution

1. A wizard adapter must map only these four names to existing explicit actions.
   Each call must obtain its own existing native reservation and fresh baseline,
   run the unchanged endpoint checks and full passive hold, then export even if
   the action fails. The scheduler is not a substitute for native admission.
2. Supply `review_roll_comparison_block.load_leg` as the independent reviewer
   through a stable application interface. Do not trust the executor's success
   label in place of original-response reconstruction.
3. Add a durable, append-only event sink in the workspace export folder with
   exclusive session creation. Record process/host clock identity; do not claim
   that UUID equality alone attests the machine's boot epoch. Publication errors
   must stop continuation. Do not silently restore unfinished sessions.
4. Test the adapter and sink with fake wizard operations and injected storage
   faults, including export failure, cancellation and an uncertain first receipt.
5. Only then launch the explicitly requested physical experiment. Retain missed
   scheduling windows as failed comparability attempts without invalidating the
   individual move's original evidence or weakening ordinary movement safeguards.

The callback contract requires durable publication, but this core cannot prove
an arbitrary supplied sink is durable or an arbitrary executor is bounded. That
responsibility belongs to the not-yet-connected application adapter. Until that
integration is complete, no live controlled session is available or enabled.

## Wizard adapter and durable journal integration update

The integration described above is now implemented in
`application/comparison_wizard_adapter.py` and the opt-in launcher
`scripts/run_controlled_roll_comparison.py`. The earlier section describes the
core-only stage; this update records the current implementation.

The adapter permits only high, center_down and lookup (the block contains four
legs but only three distinct actions). Each leg creates a new physical wizard
service so its export contains one movement, then runs the existing one-use
native action and, on success, the existing bounded passive hold. It exports in
`finally` and shuts down the service. There is no raw-command bypass. Operations
have a 65-second polling bound; timeout does not establish a physical stop.
Independent export review remains necessary before progression.

SessionJournal exclusively reserves a header and numbered event files under
`software/runs/wizard-exports`, using existing flushed reservation primitives.
Each event references the prior record hash. It checks previous bytes before
appending; publication failure poisons the writer. Partial tails are retained,
not repaired or resumed. This is an append-only evidence journal, not an atomic
committed-ledger recovery mechanism. Process ID, hostname and clock implementation
are recorded, but independent Windows boot identity remains unverified.

The launcher defaults to help with no service construction or journal creation.
Explicit live launch (up to eight physical roll movements):

```powershell
.\.venv\Scripts\python.exe software/scripts/run_controlled_roll_comparison.py --live-two-blocks
```

The existing secured/powered/clear-arm commissioning conditions still apply.
This command uses the existing native single-use admissions; no limits or
candidate coefficients were changed. No automatic retries or restart/resume
from logs. Interruption may leave an incomplete session; do not infer the arm
stopped from process termination. Inspect original evidence and obtain a new
baseline before any later movement.

48 tests passed across adapter/journal, session core, block auditor and reviewer.
Fault cases cover failed movement/hold, execution exception, missing export,
observer publication failure, exclusive journal creation, changed records and
poisoned storage. Default launcher help was executed successfully without hardware
access. The full adapter/core composition has not yet been validated against
physical hardware; no live experiment was launched during this implementation.

Next: an explicitly launched controlled session using this tested path, with
review of each exported leg and retained session records. Timing misses remain
experimental comparability failures, not grounds to weaken native checks.

## First hardware execution

The first live eight-leg session has now completed with all checks passing and
independent post-run replay. See `CONTROLLED_COMPARISON_LIVE_RESULTS.md` for its
journal, exports and the persistent variation between compensated endpoints.
This verifies one complete native session, not general hardware reliability or
precision qualification. No controller policy or frozen candidate was changed.
