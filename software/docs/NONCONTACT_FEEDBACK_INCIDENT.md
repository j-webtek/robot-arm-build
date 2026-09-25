# NC-01 public walkthrough: preceding feedback-stage incident

Date: 2026-09-08. Status: preserved historical incident analysis. This original
run stopped at stage 12, before reference-frame stage 13 and noncontact stage 14;
its quarantine remains latched. No replay or quarantine clearing is authorized
by this document. The subsequently implemented repair and separately identified
new-source successful NC-01 software lifecycle are recorded in
[Feedback single-window implementation](FEEDBACK_SINGLE_WINDOW_IMPLEMENTATION.md).
Those new results do not replace this failed run or recover its missing bytes.

## Original run and preserved evidence

The frozen production source was
`5b6599106dfb2476e547f3b9aaeaf937fadcb6fb0d990390fe003df5a4523a8b`.
The source-excluded smoke selected `--noncontact`, which implies `--reference`
and `--feedback`, but not `--owned-feedback`. Consequently the failed campaign
was the existing memory-only feedback lane, not the owned subprocess lane.

| Binding | Exact original value |
| --- | --- |
| M1 directory | `software/runs/wizard-rehearsal/wizard-fb32f71cdd6b407dad78c4e66525b517` |
| M1 session | `rehearsal-2209cd942ef14a71a0e48997c4245bfb` |
| Cell | `wizard-rehearsal-2209cd942ef14a71` |
| Attempt | `attempt-634ea628fcf840bc9104046ff4dcd68f` |
| UI operation | `operation-b770187c8b844ad49a1c9412d24619b8` |
| Registered action | `rehearsal-arm-feedback` |
| Registered worker | `incapable-arm-feedback-worker` |
| Permit SHA-256 | `ce6ac9565835cb4bba1df459b4349c2714dea503aaa38fc90bc925c64b79d5e1` |
| Energy envelope | `synthetic-energy-b36c86861a6a4c51a62bd0f390edd67a` |
| Diagnostic directory | `software/runs/wizard-diagnostics/wizard-69ed3baf7e504a129f861e880dceacfc` |

Inside the M1 directory, the original cell records are under
`cells/cell-a245f9cee18b5449f0f0c84c7188c5cbe0f263575348bddeb69bca98ddb12edb`.
The relevant files are:

- `rehearsal-records/request-27fc8f42288b702d93c7b1d003ac0d965ecd976067e3ed3b69e5a8579145ead9.json`:
  complete reserved permit; record hash
  `f159945a5248fa1965567d43ae6bd533a17b565eec65bdc2d21d2e4930515b3f`.
- `attempts/events/event-00000010.json` through `event-00000012.json`:
  durable intent, armed transition and uncertain seal.
- `rehearsal-records/result-attempt-634ea628fcf840bc9104046ff4dcd68f-sealed_uncertain.json`:
  record hash `67b92c004d52774bb28f60e2a48974b2936f810c318cca95be3bc8ab8ad43994`.
- `quarantine/events/event-00000000.json`: `SIDE_EFFECT_UNCERTAIN`, with
  `clearing_supported: false` and source attempt-event hash
  `28a9a4d6bdf1054d3659d84f7dcd63f22ae60574e07f56da28d92c07cb40cb10`.

These originals must remain intact. Diagnosis read files and metadata only; it
did not reopen them through a mutating runtime, issue another action or run a
camera, native helper, metadata inventory or serial API.

## Recovered facts versus timing inference

The reserved campaign budget is 10,000 ms. Permit and envelope retain monotonic
issuance `1586907765000000` and expiry `1586937765000000`: exactly 30 seconds,
not a renewed deadline. The allowed modeled API budgets are one open, one close,
512 read bytes, one write, zero frames and 131,072 output bytes. These are
ceilings, not evidence that any of those modeled operations occurred.

| Original observation | UTC, 2026-09-08 | Meaning and limit |
| --- | --- | --- |
| `INTENT_DURABLE.occurred_at_ns` | 13:18:35.5092616 | Timestamp captured before the persistence work; not its completion time. |
| Intent file `LastWriteTimeUtc` | 13:18:39.0441122 | Observed NTFS metadata, separate from the hashed event timestamp. |
| `EFFECT_ARMED.occurred_at_ns` | 13:18:39.2869284 | Captured before the armed append completes. |
| Armed file `LastWriteTimeUtc` | 13:18:39.7317506 | Publication cannot have returned before this file write; metadata is not a retained monotonic checkpoint. |
| `SEALED_UNCERTAIN.occurred_at_ns` | 13:18:39.9637228 | About 0.677 seconds after the armed event timestamp. |
| Quarantine event | 13:18:40.4410817 | Original uncertainty remained latched. |
| Diagnostic `ACTION_FINISHED` | 13:18:57.5351948 | Includes subsequent verification/publication work; it does not mean a worker ran for the whole UI operation. |

The retained result is `SEALED_UNCERTAIN`, `quarantine_latched: true`,
`receipt: null`, with reasons `WORKER_OR_POST_ARM_PUBLICATION_FAILED` and
`CommissioningCoordinatorError`. No full feedback campaign artifact or worker
receipt for this attempt was found. The exact exception message and the
post-consumption monotonic timestamp were **not** retained.

A later read-only simultaneous host-clock sample estimated the permit's wall
issuance as 13:18:19.519046 and expiry as 13:18:49.519046. Under that estimate,
the last time a full 10-second campaign could start was 13:18:39.519046. The
armed file write was about 0.213 seconds later. This conversion uses a later
wall/monotonic offset and assumes no intervening wall-clock adjustment. It is
not an exact historical timestamp recovered from M1.

The strongest supported explanation is therefore the coordinator's existing
post-consumption check: **the full bounded campaign no longer fit inside the
original consumed permit/envelope after the armed publication returned**.
That check is in `CellCommissioningCoordinator.execute`, immediately after
`transaction.consume_permit(permit)` and before the worker is called. The
short armed-to-uncertain interval and absent receipt support this explanation.
They do not recover the exact exception text or independently prove which
individual instruction ran. Do not label this a native-camera, physical-serial
or robot fault.

The registered composition and all retained authority flags remain
`HARDWARE_INCAPABLE_REHEARSAL` / false. Actual physical authority is zero; the
analysis supplies no physical operation, power-state or hardware qualification
evidence. Conservative quarantine must not be cleared from timing inference.

## Smallest proposed repair, not yet implemented here

`CommissioningRehearsalService._feedback_campaign` already uses
`ScopedRehearsalDispatch` for the owned feedback action. The memory-only branch
still releases/reacquires the real M1 leases separately for preflight, prepare
and execute. On this mature evidence tree, those repeated qualified acquisitions
consume time inside the original envelope.

Extend the adapter's closed action allowlist to exactly the existing memory-only
`rehearsal-arm-feedback` as well as `rehearsal-owned-arm-feedback`, and route
both existing implementations through the same one-lease-window structure.
Do not add a generic action, transaction injection or fallback worker. Preserve:

- exact M1 type, original cell/session/request binding and ordered CELL, SESSION,
  ARM_CONTROLLER leases;
- fresh preflight, prepare, execute, begin-intent and consumed-authority checks;
  no cached admission proof or skipped source/evidence verification;
- one fresh synthetic envelope issued only after preflight, with the original
  30-second lifetime; unchanged 10-second memory-worker and 20-second owned-worker
  campaign budgets, and unchanged worker/child cleanup and handshake bounds;
- one prepare and one execute context; release of the underlying real lease
  inside the second coordinator-context exit, so cleanup failures remain held;
- one-use consumption, no retry, no envelope renewal and no quarantine clearing.

Removing redundant acquisition is not a timing qualification or a promise that
all future evidence trees fit. If fresh reads or durable writes still consume
the budget, the existing hold must remain. Selecting `--owned-feedback` for a
separately authorized new-source smoke would use the existing optimized lane,
but would not demonstrate that the legacy memory lane has been repaired.

## Failed-operation observability gap

The diagnostic `event-00000008.json` records `ACTION_FINISHED`, `FAILED`,
`result_retention: FULL_JSON_RETAINED` and result hash
`95d0289361dbc4c2ed6a8571dde64c18de33d50def9cb62f49efe54cffadd922`.
That event contains the hash, not the full operation result. Its own hash is
`34991073ab8e3415ba8fdccb3e991ec4b1573c5dfda7b640894ccc2bac931e35`.
The in-memory full result can therefore be lost when the smoke raises on a
failed action and immediately shuts the wizard down before export. Exporting
the surviving historical event log must not be described as reconstructing the
missing full result from its hash.

The source-excluded smoke should, on a terminal action failure, attempt one
explicit export of that same operation's already-retained diagnostics before
shutdown, then report failure and stop. It must never repeat the failed action,
enter the next stage, create a replacement store or recursively export an
export failure. Preserve the primary failure if export itself fails. Separately,
a future bounded coordinator diagnostic should retain a fixed checkpoint/error
code and monotonic budget observations instead of only an exception class;
that would require its own reviewed schema and regression work.

Subsequent implementation: the source-excluded failure-export behavior above is
now implemented and covered by 32 passing script tests, including unknown-outcome
handling through the legacy wrapper and actual temporary export verification.
The production timing repair remains proposed. No campaign was rerun and no
earlier missing full result was reconstructed. See the current
[implementation checkpoint](WIZARD_NONCONTACT_IMPLEMENTATION.md) for script hashes.

## Required tests and acceptance before a new-source walkthrough

1. Pure adapter regressions for the two exact allowed actions; all other actions,
   substituted request bindings, phase-one writes, third transaction use,
   cross-thread use and reuse after exit remain refused.
2. Instrumented actual M1 tests in a new test-owned store: exactly one underlying
   lease acquisition, two coordinator contexts, every expected fresh admission
   read, unchanged deadline values, and lease exit inside core cleanup handling.
   Include prepare-without-execute and failure during real lease exit.
3. Deadline fault tests: slow arming past the full-budget boundary still yields
   uncertainty without worker invocation; expiration, source drift and Stop
   remain held. Tests must not lengthen the TTL or manufacture a replacement
   envelope to obtain a pass.
4. Memory-feedback service tests verify selection of the original memory worker,
   exact one-shot acknowledgement, complete retained nominal evidence when it
   fits, and no fallback to the owned worker. Keep owned-lane regressions.
5. Script tests for export-before-shutdown on failed campaign/assessment/review,
   one export attempt, no recursive export, primary-error preservation, and no
   next action or automatic retry. A failed export must not claim a verified
   bundle exists.
6. Freeze and record the new production source, then deliberately launch one
   recorded new-source/new-launch full walkthrough. Preserve this failed session and
   its exports. Do not reuse it, migrate it or promote its quarantine state.
   Record actual timing, identities and verified export hashes for the new run.
7. NC-01 acceptance still requires the planned stage-14 collect, retained
   assessment/review, dedicated full export after generic-result eviction, and
   original-store reopen without evaluator/solver/worker replay. The expected
   readiness outcome remains BLOCKED, with stage 15 PENDING and physical
   authority false; passing software tests is not physical acceptance.

Related plan: [NC-01 implementation](WIZARD_NONCONTACT_IMPLEMENTATION.md) and
[audited noncontact next slice](WIZARD_NONCONTACT_NEXT_SLICE.md).
