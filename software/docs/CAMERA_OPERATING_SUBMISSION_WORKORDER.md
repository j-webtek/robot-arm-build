# Original operating submission — remaining M1 work

2026-09-13. Software-only implementation under
[the roadmap](CAMERA_UI_COMMISSIONING_ROADMAP.md) and
[M1 work order](CAMERA_DURABLE_EVIDENCE_WORKORDER.md).
Status: compound/layout/storage, full-prefix/native reader, internal save service,
public one-use action, export and browser/terminal projections are implemented
under development testing. Fixed-input full public save/restart acceptance and
full-history integration remain open. No stage approval is implemented.

## Decision and purpose

Retain one immutable compound submission containing the exact existing proposal
and the exact original-input assessment. Both are separately hashed, bounded
subjects inside a single original evidence package. This avoids an orphaned
proposal/assessment pair between two package publications. It does not make the
assessment its own review, qualify stage 5, or restore a device permission.

The package uses `rocell.camera_operating_submission.v1`. Reuse the existing
`camera_operating_proposal.v1` and authenticate its original dependencies; there
is no second mode selector. The inner assessment is the existing v4 diagnostic
with its original wording, holds and false authority flags unchanged. Retention
is a fact established by the outer original reader, not a changed boolean inside
historical diagnostic bytes.

This first submission version requires exactly two explicitly named, separately
sealed-checksum capture attempts. Changed/unavailable pixel files may still be
recorded as failures; saving a submission does not turn them into successes.
Zero/one-capture and legacy/mixed selections remain existing diagnostics, not
silently converted originals. A subsequent version must explicitly design any
additional supported history, not relax this contract in place.

## Closed contract and bindings

- Maximum compound payload: 80 KiB. Inner proposal: existing 24 KiB maximum.
  Inner diagnostic assessment: 32 KiB. These are bounded metadata records, not
  another copy of the full-resolution pixels.
- Name the original source, cell/session/header, entry, probe preparation/review,
  creation journal head and original campaign-record inventory digest. Existing
  proposal/preflight/native references bind settings, selected identity, runtime,
  purchase profile, requested rational mode and both explicit captures.
- Preserve exact canonical JSON bytes, hashes, request/attempt IDs and native
  reference scopes. Require closed schemas and exact scalar types. A forged
  dataclass or a self-consistent uploaded JSON document proves no original owner.
- The independent verifier receives expected bindings and subjects from the
  active original owner. It must not derive expected values from the submission
  it is checking. Parsing and pure cross-field comparison remain non-authorizing.
- Recorded UTC time is submission bookkeeping, not capture/exposure time or
  proof of operation order. Original monotonic clocks retain their own domains.

## Original-store and stage integration to implement next

1. The existing owner authenticates the complete v16 history, exact proposal,
   current source and selected native/checksum records under existing leases and
   the operation's unchanged deadline. Compute the assessment there; accept no
   browser-provided pixel paths or report uploads.
2. Under the stage-only mutation owner, independently revalidate the exact
   subjects and creation head, retain the compound package through existing
   immutable publication, then read it back before committing the submission.
   Any change between camera-scope reading and stage mutation is a rejection,
   not a fresh permission or automatic retry.
3. Use the existing `WAITING_OPERATOR -> REVIEW_PENDING` stage-5 transition,
   citing the one submission reference. This accurately means an unreviewed
   submission, not approval. Do not introduce a self-transition or fake hold.
4. Define a closed v17 successor over the SAME complete snapshot: three v16
   stage-5 packages plus one submission, the exact v16 events plus zero/one
   submission event. A retained package without its event is incomplete and
   cannot be replayed/repaired automatically.
5. Extend private predecessor validation only with this revalidated typed
   suffix. Public v15/v16 readers continue rejecting later records/events.
   Never trim evidence, synthesize a previous snapshot or accept arbitrary IDs.
6. On original readback, authenticate all original predecessors, selected
   permits/receipts/native/checksum parts and the exact creation head. Historical
   pixel-read observations remain historical; a current pixel recheck must be a
   separate observation and cannot rewrite the earlier result.
7. Fresh launch restores historical submission/readback and export identities,
   never capture workflow ownership, old previews/tickets, approval or connection.
   M2–M3 add continuity and a separate review; approval stays unavailable now.

## Verification and handoff

- Pure tests: roundtrip, independent expected subject/binding mismatch, altered
  proposal/preflight/pixel joins, changed settings, duplicate attempts, legacy
  references, malformed/oversized documents, scalar tricks, unsupported versions
  and every authority field. These tests do not prove storage provenance.
- Layout tests: exact complete inventory/event chain, partial submission, future
  stage material, wrong entry/header/session and unchanged older reader behavior.
- Real M1/NTFS: read/write/reopen, failed publication/readback/commit, stale head,
  disk/permission/owner errors, Stop/deadline and no operation replay.
- Public service/UI/export: service-owned forms and one-use tickets; show saved
  diagnostic versus authenticated original submission, historical image checks,
  all remaining holds and no stage approval. Independently verify export manifests.
- Preserve every failed revision and fixed-input result. The running checkpoint
  04 tests the prior public checksum migration, not this new submission contract.

No camera, USB scan, serial, arm power, motion or contact is performed or
authorized by this work order. No hardware measurement is inferred.

## Development checkpoint

- The immutable compound codec passed 61 pure cases. It preserves both exact
  inner subjects and their original diagnostic holds. Independent expected
  bindings/subjects, malformed wire data and rehashed cross-field mutations are
  tested. The native metadata/assessment references in these tests are modeled.
- The v17 structural suffix passed 18 tests in 218.84 seconds. It validates the
  same full snapshot, original creation head, exact inventory and chronological
  stage citations. Public v15/v16 layouts still reject its later material. These
  are layout tests, not v17 original native/campaign authentication.
- The first layout runner was stopped after its first passing test because it
  unnecessarily rebuilt the expensive complete modeled predecessor for every
  pure mutation. The replacement builds that value once and deep-copies only
  data for each test. It caches no transaction, runtime owner, active permission,
  file observation or original currentness check. The stopped run is not accepted.
- `M1PhysicalCameraTransaction.store_camera_operating_submission` now binds the
  compound record to an exact current three-package reviewed-probe boundary,
  source/header/session, full campaign-record inventory and creation head. It
  uses existing stage-only leases, guarded original batch reading and immutable
  publication. It commits no event and accepts no replacement/partial replay.
- The first actual NTFS test reached retention, fresh adapter readback and the
  modeled REVIEW_PENDING commit, then failed on a test's incorrect header
  attribute name. The header exposes its fixed authority flags in `to_dict()`;
  that assertion is corrected. Failure cases and the corrected batch are running.

The corrected combined development selection passed **102 tests in 103.38
seconds**: storage guards, the pure compound codec, direct receipt comparison and
guarded ingestion. A subsequent refined storage selection passed **5 tests in
53.59 seconds**. It separates a normal same-transaction write/commit followed by
reopening from an interrupted write which is reopened but never resumed. It also
rejects modified original payload bytes and tests failed publication/closing
readback. The store and OS leases are real NTFS; stage predecessors and native
assessment observations remain explicitly modeled. Focused type checking passed
the seven touched/new backend modules, not the whole repository.

### Next independent original-input join

Before enabling the writer from any public action:

1. Authenticate the complete v16 prefix (or the exact v17 structural suffix for
   historical reading) on the same real snapshot. Extend only the private typed
   prefix allowance, retaining original public v15/v16 behavior.
2. Read the selected original probe permit/result/native pair and independently
   reconstruct capabilities. Resolve each of the two explicit capture request
   keys to one original permit/result/native/checksum collection. Verify their
   original admission facts, exact settings, context, source and preparation/
   review hashes; no input can be substituted from launch memory or uploaded JSON.
3. Reconstruct the preflight and compare every original proposal/native/readback
   hash. Verify stored pixel-reference hashes/lengths against the earlier sealed
   checksums. Historical pixel-read verdicts remain observations of that read;
   they must not be relabeled as current file verification or camera freshness.
4. Compare the submission's original campaign-record inventory digest with the
   original owner. This initial v17 contract is closed: a later campaign family
   cannot be silently ignored to recreate a matching earlier inventory. Later
   milestone successor contracts must explicitly define their historical joins.
5. The stage owner then revalidates the exact creation head/subjects before
   retaining and independently reading the compound package, and commits its
   REVIEW_PENDING event in the same bounded operation. After a failed or partial
   write, no new owner automatically resumes that commit.
6. Add original-session schema/cache/role routing, exact export and historical
   reconstruction, then the existing service-owned UI form/ticket/publication
   path. Do not select the new public action until these dependencies and failure
   tests are ready. M2–M3 still own continuity and separate review.

Reports are under `../runs/wizard-exports/camera-durable-evidence-20260913-04/`.
They are development selections, separate from the earlier active frozen public
checksum run. A writer guard is not the complete original-reader/service chain;
M1 and all later milestone approval gates remain open.

## Reader integration under test

The new `camera_operating_submission_native.py` reads the exact original probe
and two explicit capture requests from the active M1 transaction. It reconstructs
capabilities, settings, historical capture plans, readbacks and preflight; joins
the original setup summaries and configuration epochs; and compares historical
pixel references to their earlier sealed checksum. It audits the complete record
family before and after. It does not reopen devices, read today's pixels as a
historical observation, reconstruct an acquisition owner or confer approval.

`camera_operating_submission_readback.py` revalidates the entire stage prefix on
the same full snapshot and then calls that native join. For the old admission's
workflow digest only, it reprojects the two envelope hashes from the already
authenticated creation event prefix and inventory excluding the one validated
submission reference. This is never a synthetic SessionSnapshot or input to an
older reader/permission check. Old public v15/v16 readers still reject successors.

The original session's v17 route adds exactly one bounded submission role and
80 KiB package allowance, plus its bounded workflow wrapper. Legacy per-version
workflow budgets remain unchanged. A retained package without its one expected
event stays INCOMPLETE, not an automatically resumable operation. New workflow
output remains historical, unreviewed, disconnected and non-authorizing.

Verification is deliberately split: pure context/request/reference comparisons;
full modeled history with a clearly labeled native-subject seam; then actual
three-attempt M1/native integration and public write/reopen/export. The first two
layers cannot substitute for the third. These new reader modules and routing are
not in checkpoint 05's nominal input copy and have not been accepted as a release.

The corrected full-prefix routing selection passed 7 tests in 239.93 seconds;
the original-store missing-native negative passed 1 test in 9.42 seconds. The
actual three-attempt native/M1 test initially failed before acquisition because
its fixture's output parent was outside the exact deployment. Correcting only
that fixture produced a pass in 132.23 seconds. The test uses synthetic pixels,
incapable native owners and modeled stage/admission facts; original protocol,
receipt, storage and native reader paths run unchanged. Historical pixel-file
changes do not alter an old verdict, and a rehashed forged reference is rejected.

`camera_operating_submission_service.py` now implements the internal file-only
assessment-to-stage handoff. It accepts no uploaded report. It compares the full
original creation workflow, independently reads native inputs, stores and rereads
the exact compound, commits REVIEW_PENDING once, and verifies committed/reopened
originals before returning. The wizard still must log and publish that return;
the public action is not enabled yet. Partial storage/commit outcomes are recorded
before the next fallible call, never erased or automatically resumed. Development
tests are running with real M1 storage and explicitly modeled prefix/native seams.
The optional parent deadline on session refresh only shortens its existing cap;
the new file-only service uses one 300-second budget, not a native device permit.

## Public integration checkpoint (development only)

The subsequent 29-case service/native selection passed in 294.92 seconds. It
includes the three actual saved native attempts, actual M1 retain/read/commit and
historical reopening, plus altered returned-context/epoch and reference checks.
The complete older stage-prefix verification is explicitly modeled in that test.
The separate full-prefix tests do not substitute for composing both paths in a
full original-history public save case. That acceptance remains required.

`physical_camera_operating_submit` now uses the existing Arrival action lifecycle.
The operator selects both captures (neither is defaulted), names an operator and
explicitly confirms saving for review. The service computes fresh diagnostic
inputs; it never accepts a browser-uploaded report. Stage 5 becomes REVIEW_PENDING
only after retained-byte comparison. Changed inputs, Stop, time, source or logging
prevent current publication. The historical diagnostic's inner retention hold
is not rewritten as approval. Approval, continuity and freshness remain separate.

An owned logged-proposal comparison survives the operation's deliberate stage
change without restoring old original-probe eligibility. It is not an admission
or restore API. The setup is adopted only after an exact successful completion
log and reopened-original comparison. Unexpected late failures withhold pending
bookkeeping; partial writes remain inspectable and are not replayed.

The Camera page and terminal now show an unreviewed original-submission card.
Closed projection checks reject altered authority/source/reference fields.
Availability polling does not copy or hash the full original history. General
exports include a flat, de-duplicated compound document map and explicit original
references, including original readbacks on fresh launch. No executable, callback,
permission owner, image pixels or import mechanism is exported. General sanitizer,
depth/byte/attachment caps remain unchanged; redaction is disclosed.

The latest public/proposal/browser/terminal/export development selection passed
61 tests in 8.57 seconds. Public backend and setup-adoption seams are modeled;
this is not full native/store/public acceptance. Detailed failed revisions and
fixes are preserved in checkpoint 05's README. A new fixed-input selected run is
next, followed by complete-history public save/reopen/export and latency evidence.

## Subsequent acceptance checkpoint

Checkpoint 06 completed with 529 passed and 38 setup errors, not acceptance.
All 38 errors rejected a reduced test snapshot missing required original source
documentation. Its frozen inputs and results remain unchanged. Checkpoint 07
retains the complete declared input tree, including all required documentation;
its exact nine-case smoke lane passed with unchanged source and input audits.
The separate full-history public two-capture save/reopen/export lane failed at
the earlier probe's admission deadline, before the new submission, in 1,931.95 s.
Inputs/source remained unchanged. Its retained uncertain attempt is not replayed;
the next task is validation-cost diagnosis without changing the 2-second probe
admission window. Detailed inputs, boundaries and results are in the checkpoint-06
and checkpoint-07 READMEs. Full-history submission acceptance remains open.

The operator guide now describes the implemented draft/diagnostic/save-for-review
sequence without labeling it hardware-ready or stage-approved. A real rehearsal
browser inspection corrected misleading action-location text; it verified only
the empty/held UI and issued no action. An additional six-case export fault batch
passed with modeled cached provenance, outside the fixed input; it is not added
to the frozen smoke count or treated as acceptance of the whole workflow.

Checkpoint 09 removes one duplicate root walk within each qualified file read;
fresh per-call qualification, containment and opened-file checks remain, with no
cache or deadline change. Its frozen seven-module storage/native-admission lane
passed 147 tests in 13.42 s, and the public nine-case smoke passed in 6.38 s with
unchanged complete inputs/source. The preceding failed full-history attempt is
not replayed. A fresh complete-history lane is still required before claiming
the admission timing or M1 public submission is accepted. Checkpoint 08's broader
601-case selection subsequently passed in 2,324.606 s on its earlier frozen
revision, with exact collected/executed identities, no failures/errors/skips and
unchanged source/inputs. Checkpoint-09 `full-01` then started as a fresh modeled
public two-capture submission/reopen/export history. It has no terminal result yet.
