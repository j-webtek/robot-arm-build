# NC-01 original-store reopening

The stage-14 integration extends the existing incapable rehearsal store. It does
not create a physical store, advance stage 15, execute a worker or replay a fit.
An expected rejection test passing is independent of nominal build readiness.
Missing installed geometry and measured accuracy remain blocked.

## Exact dependency join

`commissioning_rehearsal_reopen._noncontact_binding(snapshot, evidence, operator,
source, catalog, records, source_context, *, reference_workspace, directory=None)`
returns `(RehearsalNoncontactBinding, original_camera_receipt)`.

- `snapshot`, `evidence` and `records` come from the original audited M1 store.
- `reference_workspace` is assigned by the application, never a stored or browser
  path. `source_context` is the canonical bytes returned by the current fixed
  `read_noncontact_source_context`.
- The join selects the unique reviewed stage-13 PASS and reconstitutes its exact
  reference binding through the existing stage-7/8/12 checks. Those checks retain
  camera settings/dataset identity, controller and complete campaign evidence,
  and the independent final **synthetic** power observation.
- The original stage-13 operator is retained inside that binding. The new
  noncontact operator is a separate field. Three predecessor hashes cover full
  canonical receipt/assessment/review payloads, including embedded self-hashes;
  `reference_evidence_sha256` covers the full original reference evaluation.
- Original reference algebra is verified without running a fitter or solver.
  The new source context must match its original reference geometry context.

The returned camera receipt is not hash-only pixel proof. The service separately
calls its existing guarded capture verifier; reopening checks all original binary
camera datasets in its existing bounded loop. This avoids adding repeated large
file reads to every recursive predecessor join. Callers must not omit that check.

## Retained evidence and lifecycle

`_verify_noncontact_receipt` reads fixed source context at the explicit guarded
verification boundary and calls the pure noncontact verifier with independently
expected binding, full evidence digest and bounded current evaluator-file digest.
The generic retained dispatch requires both audited records and the assigned
workspace before invoking it. Cached views/export do not call this boundary.

The exact schemas are:

- `rocell.rehearsal_noncontact_stage_open.v1`
- `rocell.rehearsal_noncontact_receipt.v1`

Both use existing immutable evidence packages and unchanged limits: 128 KiB per
outer document, 128 evidence items and 1 MiB aggregate JSON reconstruction. The
full evaluator report must fit; there is no truncation, repair or replacement.

Each failed substantive check generates `NONCONTACT_CHECK_FAILED:<check_id>`.
The assessment is BLOCKED if any such check fails. Reviewing that exact blocked
assessment retains BLOCKED; it cannot transform successful expected-fault checks
into a nominal PASS or handoff. All physical authority remains false.

An opened stage lacking its retained result fails with
`EVALUATION_RECEIPT_MISSING`, without replay. One exact current unassessed receipt
restores as `RECEIPT_READY`; duplicates, mismatched operators or orphan evidence
remain held. `REVIEW_PENDING` restores the original receipt and assessment.

## Focused validation

`tests/unit/test_noncontact_reopen.py` exercises actual schema/dispatch/journal
predicates and the actual original reference verifier. Its minimal lifecycle and
already-reviewed predecessor fixtures are explicitly injected, not substitutes
for full qualified M1 progression. Full public stage-14 store/export verification
must run separately against a frozen source. No test in this focused lane opens
hardware or launches a device-capable process.

Focused checkpoint: **37 dedicated cases**, including the actual NC-01 producer
and full retained report verifier; **147 combined cases** across that file,
reference lifecycle/join tests, configured/owned camera reopening and owned-arm
directory checks passed in 11.48 s. The original assessor/evaluator and fitter
are forbidden after fixture creation; fixed context reads are permitted only at
the explicit source boundary and forbidden inside the pure NC-01 verifier.
Changed report hashes, rehashed PASS, altered counts and dropped geometry are
rejected. Black and targeted mypy checks pass. This checkpoint does not claim the
separate full original-store fourteen-stage workflow has run.
