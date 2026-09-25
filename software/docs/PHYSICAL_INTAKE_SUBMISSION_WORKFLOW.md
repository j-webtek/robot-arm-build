# Received-hardware intake: plan, implementation and verified working contract

Date: 2026-09-08. Companion to the camera/arm developer playbook. This is the
next dependency toward an actual qualified camera connection, not a substitute
for that connection or a declaration that the overall wizard is complete.

## Starting state and intended outcome

Before this increment, the notebook recorded the original sixteen camera-receipt/
placemat questions but stored only text drafts. The source-stage assessment was
an immutable BLOCKED v1 assessment, and the camera session read only singleton
source roles and the initial configuration vector. Neither a draft nor the
vector supplied reviewed physical facts to the dormant native runtime.

This implementation now retains original operator-supplied attachment bytes and
a complete immutable intake submission in the same M1 setup store. A different
operator label can review the exact submission. Restart restores the original
submission and its references, without reading the inbox again or repeating a
write. The UI distinguishes byte integrity, procedural review, missing evidence
and actual physical acceptance. Bytes and labels cannot prove a measurement
true or authenticate an independent reviewer.

## Operator path

1. Initialize/collect and assess/review original workspace sources, or explicitly
   discover and open the original store. The original source verdict stays
   BLOCKED. A late original-store error must be resolved by inspection, not by
   selecting a replacement or silently retrying.
2. Complete each of the existing sixteen draft questions explicitly: OBSERVED
   with method/value, or UNKNOWN with reason. No nominal dimension or default
   observation is supplied.
3. Place relevant files in the fixed workspace inbox
   `software/runs/physical-intake-inbox`. Creation/discovery is explicit. This
   is an input folder, not the diagnostics export folder or a source of trusted
   release documents. Browser/terminal inputs never supply arbitrary paths.
4. Choose **Discover intake attachments**. The worker inspects only bounded
   immediate files and returns opaque, current-snapshot choices with type,
   size/hash and reasons for refusal. Status rendering does not scan files.
5. Choose **Submit intake evidence**. A closed batch form maps up to sixteen
   original question IDs to optional opaque attachment choices. One original
   file may support more than one question; it is retained once. OBSERVED rows
   require an attachment; UNKNOWN rows may omit one. The preview binds the
   exact notebook, choices and original setup context. Explicit confirmation
   permits only the described bounded local file writes and reads.
6. Submission retains each exact selected original file, a source/header-bound
   manifest and a deterministic completeness assessment. The assessment checks
   structure and references, not the physical truth of photographs or text.
7. **Review exact intake submission** binds the retained manifest, assessment
   and references. A distinct label may acknowledge the submission for later
   stage review or reject it. Neither outcome changes source-v1 BLOCKED or
   accepts a canonical physical stage. Review is never automatic on reopen.
8. Export logs includes a reserved full submission/assessment/review metadata
   attachment. Original media must not be silently inserted into the existing
   sanitizing text-only diagnostics exporter. A separate explicit, bounded
   byte-preserving evidence export is required for raw originals; it must warn
   that those files may contain private material and cannot be redacted while
   retaining their original hashes.

## Original-store lifecycle

Use V2's existing explicit `BLOCKED -> WAITING_OPERATOR -> REVIEW_PENDING ->
BLOCKED` sequence for supplementary intake. The initial source receipt,
assessment and review are immutable historical subjects. They are not rewritten
as a new approval or confused with the currently pending supplementary review.

The versioned source reader must verify the original source prefix and each
supplementary collection/review link. Recognize only closed package roles;
reject unknown, duplicated, cross-source/session, orphaned or inconsistent
completed subjects. A partially published collection must remain inspectable
as incomplete after failure, without manufacturing a submission or replaying
the files. Current state and exact evidence citations must match the committed
journal. Later physical stages remain PENDING.

Selected files are source-stage supplementary material, with explicit intended
observation owner `camera_receipt`. They are not stage-three `BoundEvidence`.
A future stage-three adapter must independently read and exactly re-retain
the bytes with explicit original-reference provenance; no relabeling in place.

Corrections are append-only successor submissions with an exact predecessor
subject and preserved reviews, subject to bounded original-store capacity.
An unreviewed or partial predecessor must be inspected/reviewed first; failure
does not grant another automatic write attempt. Reuse unchanged already-read
original references where supported; do not erase history to regain capacity.

## Input and resource boundaries

- Exactly the original sixteen questions, original units and notebook codec.
  INT-005 flatness remains observation-only with stage-fourteen acceptance.
- Keep the existing 65,536-byte JSON HTTP request and closed form machinery.
  No file uploads/base64 payloads or path fields are added to those requests.
- Fixed inbox, no recursive traversal, no executable/archive types, no link,
  reparse point, hardlink, file replacement or source drift accepted. Read and
  hash through guarded/pinned scopes, before and after copying. A filename or
  extension alone is not content validation or evidence authenticity.
- Retain raw files as M1 binary payloads, never embedded in ordinary JSON cards.
  Inventory, per-file and aggregate budgets are checked before a stage write;
  no truncation, implicit downsampling, format conversion or quota recycling.
- Preserve the existing 32-reference/4-MiB original source-readback ceiling for
  this initial join; preflight includes existing source/epoch records and all
  submission/assessment/review overhead. Refuse an oversized batch before
  changing the stage. A future larger media pool requires its own reviewed
  reader/export contract rather than weakening generic limits.
- Background work has one original deadline, cancellation/source checks and
  single-use operation context. GET/status remains pure and never resumes work.
- Full metadata survives ordinary result rotation. Late readback/Stop/log
  failures retain historical diagnostics, never current acceptance.

## Agent ownership and order

1. Evidence agent: strict immutable submission, completeness assessment, exact
   review and successor codecs; original sixteen-question binding and tests.
2. Camera/storage agent: versioned original-source supplementary package and
   event-chain reader, actual M1 original readback/restart and failure tests.
3. UI agent: closed batch choice fields and browser/terminal displays; distinguish
   original source verdict, active supplementary state and unqualified records.
4. Root: guarded inbox discovery/read; application actions and transaction
   orchestration; publication/export, integration tests and public walkthrough.

Agree exact shared APIs before edits. Keep source modules frozen during the
actual public walkthrough; isolated tests must label modeled measurements and
must not observe or activate hardware. Preserve original failed/partial stores.

## Verification and remaining connection work

Tests must cover original bytes surviving loss/change of the inbox copy,
explicitly unknown rows, stale choice/notebook/session/source, replaced files,
duplicate/unknown roles, predecessor/reviewer drift, uncertain/partial writes,
late publication failure, restart without replay, and full export after result
rotation. Exercise the actual shared service and both renderers, not a separate
fixture-only application. Actual hardware remains disconnected and unqualified.

The native camera still needs reviewed isolation/HZ-012 source reassessment,
static contract and received-unit/identity stage adapters, assessed epoch
successors, a purpose-specific released-runtime qualification contract and
owned dispatch/readback. A new permanently-refusing connection button does not
satisfy those requirements. Arm startup/feedback, installed calibration and
later motion/contact release remain separate unfinished work.

## Implemented application joins

The browser and terminal use the same four registered actions:

| Action | Real local effect | Does not establish |
| --- | --- | --- |
| Discover intake attachments | Explicit fixed-inbox inventory and opaque choices | Evidence acceptance or a camera connection |
| Submit intake evidence | Original bytes, complete notebook, deterministic structural assessment and REVIEW_PENDING event | Measurement truth or physical readiness |
| Review exact intake submission | Exact-subject acknowledgement/rejection and BLOCKED event | Authenticated independent people or a stage PASS |
| Export private original intake files | Exact submission JSON, original attachment bytes and final manifest in the assigned export folder | Redaction, calibration, device admission or robot authority |

`physical_intake_evidence_service.py` orchestrates the original setup owner,
`physical_intake_inbox.py`, immutable `physical_intake_submission.py` codecs and
`physical_intake_original_export.py`. The existing setup service serializes
mutation and audits the original store after its lease scope. Arrival handles
one-use previews, worker execution outside its UI lock, Stop, source checks and
completion logging. Only successful logged completion publishes a current view.
The v3 original-source reader verifies the complete source prefix and each
append-only intake collection; legacy v1/v2 histories remain unchanged.

Discovery permits at most 32 immediate regular files, 2 MiB each and 16 MiB
total scanned. TXT/JSON must be UTF-8 without NUL; PNG/JPEG/PDF get header checks,
not semantic media validation. Selected inputs remain sharing-pinned through
original retention. Links, replacements, reserved Windows names and unsupported
types are refused, without modifying input files. One selection can support
multiple rows. Byte-identical prior references with the same basename/type are
re-read and reused in a successor; no package is overwritten.

Before START, retention checks the existing 32-reference/4-MiB inventory,
new original bytes and a conservative 384-KiB reserve for the three metadata
records. Eight collections are the maximum, not a promise that every collection
fits the remaining capacity. A reviewed predecessor and a revised notebook are
required for a successor. A partial write remains incomplete; there is no
automatic retry, repair, store replacement or quota recycling.

Generated metadata is retained diagnostically before an uncertain store call;
its state distinguishes COLLECTED_NOT_M1_RETAINED, publication awaiting readback,
and full original bytes read back. Raw attachment bytes never enter JSON caches.
Late-reader history survives failed current publication. Restored submissions
can be reviewed/exported without an inbox or draft. Unsubmitted draft restoration
and automatic cloning of a restored submission into a correction draft are not
implemented; explicitly start/complete a new draft when a correction is needed.

## Export and privacy contract

The selected parent remains:

`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`

Normal **Export logs** reserves `attachment-intake-evidence.json` for full
submission, assessment, review and historical-attempt metadata. It does not copy
photos/PDFs. Full notebook metadata remains in its own existing reserved
attachment. Sanitized content is labeled as such rather than passed off as the
original bytes named by an evidence hash.

Exports use an explicitly identified bounded snapshot projection: repeated UI
action-form definitions are omitted and the full notebook is referenced by its
reserved attachment/hash. Live UI forms remain complete. This preserves the
256-KiB snapshot limit without truncating original evidence. Full intake metadata
has the existing separate 1-MiB bound; tested eight-collection histories fit.

The separate private-originals action requires explicit file-only and private-
copy consent. It prepares the assigned export parent even if no generic export
has run, exclusively creates `physical-intake-originals-<id>`, copies and reads
back each original plus `submission.json`, and writes `manifest.json` last.
It never redacts or overwrites. Failed exports preserve partial files and a
truthful receipt for inspection; review private material before sharing it.

## Verified checkpoint — 2026-09-08

Final software source:

`254664d04637fd488ac801fe9c5d0c78f3bc4308cc320469d497c950b1780e30`

The actual public `wizard_intake_evidence_smoke.py` walkthrough passed:
initialization, prerequisite/configuration retention, original source assessment
and review, all sixteen explicitly UNKNOWN draft entries, fixed-inbox discovery,
one original explanatory software-fixture attachment mapped to all sixteen rows,
submission, full diagnostic export, shutdown, original-store discovery/reopen,
exact submission review, private-byte export, nine newer notes and another full
verified export. Original source review stayed unchanged; stage 1 stayed BLOCKED
after review and the remaining fourteen original stages stayed PENDING. All
fifteen public physical stages remained PHYSICAL_PENDING. No endpoint inventory,
native helper, device open, serial write, power, motion or contact action ran.

Original launch: `wizard-83ea22e76c6446c893e0e80c0d92dc41`.
Reopened launch: `wizard-8f71c8207dfb4541b2952ed07946490f`.
Collection: `intake-ce6cf7b95fac46c58c82d4641d2d8170`.
Submission SHA-256:
`e99eca9a52185d41823a627791bf55f6255cce60f8c368e37d575dc41e410832`.

Artifacts under the assigned export parent:

- Initial metadata: `wizard-20260908T211246042739Z-e0356bc9004641ea985a1ccfcb281e3e`.
- Reopened/reviewed metadata: `wizard-20260908T211326146925Z-5dcbc990c390489aafee499fe674e43e`.
- Exact originals: `physical-intake-originals-83d84a1a1cfb4b8e93c3a9a9d74abe1b`.
  Its 359-byte explanatory fixture is not physical evidence. Manifest SHA-256:
  `373af843300a2b8a788a6b4800e2296835b096e526b78c2a407ecf7a43dcd842`.

Final scoped verification (selections are reported separately, not summed with
earlier overlapping agent runs):

- 66 inbox/service/failure/budget/cache tests passed in 110.10 s. This includes
  actual isolated NTFS submission, restart after deleting only a test-fixture
  inbox copy, original review, and raw export with a newly prepared parent.
- 311 Arrival/action/browser/terminal/source/configuration/intake compatibility
  tests passed in 48.66 s.
- Additional agent checks: 87 codec/original-export tests; 153 cache/source/
  prerequisite-reader regressions; independent original NTFS partial/reviewed
  restart cases. These are scoped checks, not a whole-repository test claim.
- Black and mypy checks passed for the changed production modules. Both launcher
  startup-check modes returned READY_FOR_DIAGNOSTICS on the final source.
- A real browser rendered the Camera and retained-intake panels correctly in a
  read-only check. No UI action was executed; the temporary tab/server were closed.
- An offline host-Python wheel build passed; all 264 packaged code/UI entries
  matched workspace bytes. Wheel SHA-256:
  `ab7accafc1633d26907c79ba702ffad058a987f29346ebf30cd0324b1bc02bf4`.

Preserved failure and repair: the first actual walkthrough on source
`25de9523fc4fff43773aa123e054188b30ee870876fdcc40fd969ac866bf1776`
saved its original submission but export failed `IPC_STRUCTURE_LIMIT`. Original
launch `wizard-7e45a8d47738413ca039e1302c21386e` and its files remain untouched.
The combined source/configuration/intake cache exceeded the native small-message
decoder's 4,096-node bound. A dedicated private, strictly canonical history
decoder now checks 4 MiB + 64 KiB, 65,536 nodes and depth 16 before retaining or
copying that history. The native IPC limit was not changed. A real-codec
eight-collection regression verifies the larger history and late-error cache.
The successful final walkthrough used a fresh source-bound session; no uncertain
original write was retried or relabeled.

## Next implementation boundary

This increment is complete; the overall hardware-connection wizard is not.
Next work must turn qualified, original received-unit facts into separately
assessed stage/epoch successors and purpose-specific acquisition admission,
then join the owned probe/capture dispatcher to the already retained data
pipeline. Add genuine arm connection/startup and installed calibration adapters
under their separate physical gates. Do not replace these missing joins with
additional acknowledgement checkboxes or infer physical truth from this intake.
