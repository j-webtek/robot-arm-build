# Durable camera operating evidence — M1 implementation work order

2026-09-13. Active software-only work under the
[commissioning roadmap](CAMERA_UI_COMMISSIONING_ROADMAP.md). M1 is not complete.

## Ownership decision

The existing combined assessment is diagnostic. Its requirements belong to
different stages and must not become a cyclic stage-5 acceptance predicate:

| Requirement | Owning stage | Meaning |
| --- | --- | --- |
| Original source/store/currentness | camera_mode_controls | Revalidate for each stage-5 operation; no serialized permission |
| USB speed/identity continuity | camera_mode_controls | Original observations required; missing identity stays unknown |
| Ordered close/reopen | camera_mode_controls | Native lifecycle plus original ordering, not just distinct IDs |
| Saved pixels | camera_mode_controls | Earlier checksum provenance and verified original bytes |
| Separate reviewer decision | camera_mode_controls | Separate transaction; cannot approve later stages |
| Proposal/assessment original retention | camera_mode_controls | Original stage records, not exports or launch memory |
| Frame freshness | camera_frame_freshness | Later independent stage; no inferred exposure timestamp |
| Installed optics | optics_intrinsics | Later measured optics/intrinsics |
| Passive camera-to-board registration | static_registration | Later independent registration; not robot-world calibration |

Robot-world/controller correlation remains in reference_frame_calibration.
All stages retain their existing order, gates and effect domains. This work does
not enable a stage PASS or change the stage catalog/runtime activation policy.

## Implementation slices and invariants

1. Add a closed stage-ownership projection over existing diagnostic requirements.
   Unknown/malformed obligations must not silently disappear. Use this projection
   in original-assessment results and the UI without changing approval semantics.
2. Define a bounded immutable capture-reference codec using original native
   request/evidence identities, exact mode/layout and the capture-time checksum.
   Its builder/verifier is pure and cannot prove file or store provenance alone.
   Do not accept a path from the browser, hash a historical file to invent its
   expected digest, or treat the existing dataset manifest as M1 qualification.
3. Extend actual owned capture completion and M1 retention/readback with that
   reference. Keep old captures diagnostic-only when their durable reference is
   absent. Bind durable records before publication and test interrupted retention.
4. Add proposal/assessment original-stage subjects and a closed successor layout
   over the SAME complete snapshot. Preserve historical v15/v16 reader contracts;
   never filter an arbitrary suffix or manufacture a predecessor snapshot.
5. Join public service/UI/export and fresh-launch original reconstruction. Test
   the full source/owner/record chain, faults and no restored hardware permission.

The existing proposal codec is reused, not replaced by a second mode selector.
Any reference parsed from JSON remains untrusted data until an original owner
independently authenticates its bindings and stored bytes. No new physical
runner, bypass flag, arbitrary file importer or automatic retry is introduced.

## Verification strategy

Start with deterministic pure-contract and actual-JavaScript tests. Follow with
real M1/NTFS retention/reopening tests and original-owner/service composition.
Use incapable native producers, labeled synthetic pixels and separate fixed-input
reports. The complete M1 milestone requires slices 1–5, not only codecs or a UI.
The later review, continuity and freshness milestones stay open throughout M1.

## Progress

- [x] Read and reconcile existing diagnostic obligations with canonical stages.
- [x] Implement/test the stage-ownership projection and UI use (development tests).
- [x] Implement/test the capture-reference contract (development tests).
- [ ] Implement/test owned capture-time durable retention and readback.
  - [x] Implement guarded pre-seal checksum reader and versioned storage/accounting.
  - [x] Test original M1 write/read/reopen, tampering and failed final-index writes.
  - [x] Verify the owned checksum-bearing producer and pre-effect capacity slice.
  - [ ] Connect the actual public capture producer, capacity admission and readback.
- [ ] Implement/test the complete original-stage successor and reopening path.
- [ ] Verify public UI/export composition and record a fixed-input handoff.

No camera, USB metadata, arm, serial, settings, power, motion or contact action
is authorized by this work order. Hardware checkpoints remain operator-paced.

### Implemented foundation; not durable original retention

The v3 original diagnostic assessment now includes the closed
`rocell.camera_operating_stage_requirements.v1` projection. The actual UI groups
mode/control requirements separately from later freshness and installed checks.
All holds and false authority flags are retained. Historic v1/v2 rendering is
unchanged; an unknown or inconsistent v3 projection renders unavailable.

`camera_capture_reference.py` defines the bounded immutable v1 capture-reference
codec and independently rebuilds its native/configuration joins. The exact
original configuration-capture dispatcher supplies the retained request key to
the existing owned ingestion path. After its pixels have been verified, ingestion
creates a candidate from that earlier checksum, native metadata, manifest and
ingest-envelope hashes. This does not hash historical pixels to invent provenance.

The candidate is currently kept in workflow diagnostics with the literal label
`LAUNCH_DIAGNOSTIC_ONLY_NOT_M1_ORIGINAL`. Early failed new captures do not inherit
an older candidate; late Stop preserves available diagnostic evidence without
publishing current pixels. There is no new action, import endpoint, review, stage
PASS or permission restoration. Slices 3–5 remain open.

Development reports are under
`../runs/wizard-exports/camera-durable-evidence-20260913-01/`.
`development-02.xml` passed 148 tests; `reference-development-01.xml` passed 52.
These are different selections, not one release total. The first handoff run
preserved a fixture failure (the existing short-file guard raised CameraWorkerError
instead of the test's expected ValueError); the expectation was corrected without
weakening production rejection.

The subsequent fixed-input 30-module regression passed **866 tests** with no
failures/errors/skips in 759.08 seconds. Source and selected input manifests
were unchanged. See the [implementation evidence](../runs/wizard-exports/camera-durable-evidence-20260913-01/README.md)
for exact input/source identities, executed test IDs, dependency scope and limits.
This completes verification of the foundation, not slices 3–5 or milestone M1.

### Foundation checkpoint handoff (before the later public migration below)

| Boundary | What crosses it | What is still withheld |
| --- | --- | --- |
| Exact dispatcher to acquisition service | Independently read original native pair, preparation, settings epoch and retained request key | No current frame until staged ingestion and outer completion succeed |
| Service to a staged workflow copy | The same bounded capture inputs; previous published workflow remains separate | A failed new capture cannot overwrite the published workflow |
| Workflow ingestion to reference codec | Verified frame hash plus exact native metadata, configuration, manifest and ingest hash | Codec parsing/rebuilding alone proves no original-store provenance |
| Workflow to pending result | Diagnostic candidate and a digest of the complete workflow diagnostics | Candidate is launch-only, not restartable M1 qualification |
| Outer completion to publication | Exact pending result after existing logging/currentness checks | No stage PASS, camera freshness, connected-state or motion authority |

Existing capability, preview, export and action owners remain authoritative for
their own projections; no second browser command catalog or pixel-path selector
was added. Tests cover both the pure codec and the real service-to-ingestion join.

## Next retention integration: boundaries established by source inspection

The current dispatcher seals and independently reads the native attempt **before**
calling `stage_retained_capture`. Consequently, today's launch candidate cannot
simply be appended to that already sealed result. Its hashes would not be among
the receipt's journal-bound evidence hashes. Do not modify a sealed result, add an
unbound sidecar, or expand the closed v2 artifact pair in place.

The following records the two storage designs considered before implementation.
Design 1 was subsequently selected below; this comparison is retained to explain
why a later ingestion candidate cannot be appended to an already sealed result:

1. A separately versioned settings-capture evidence contract could retain a
   checksum subject before terminal sealing, using the existing consumed scope,
   native acquisition and immutable multipart storage. This requires a bounded
   post-cleanup pixel read within the original deadline, independent accounting
   and capacity admission, and compatibility with incomplete/failed native runs.
   Keep the existing v2 pair, its original IDs and historical accounting exact.
   The present full candidate includes a later ingest-manifest hash; do not move
   it earlier without resolving that dependency or explicitly designing a
   different capture-time subject. Never fabricate a missing manifest hash.
2. A versioned original stage successor could retain and journal-bind the
   ingestion-produced subject after native cleanup. This needs complete-snapshot
   predecessor authentication, exact inventory/event/state semantics, independent
   readback, and new original-guard reconstruction before another admission.
   Current v15/v16 readers intentionally reject later records and events. A
   WAITING_OPERATOR-to-itself event is not an available transition; do not use
   fake state changes or trimmed snapshots to make it appear supported.

Whichever design is selected must prove capture-time hash provenance, immutable
binding, clean scope exit, interrupt/deadline handling and fresh-launch readback
before public success claims durable retention. Keep native completion distinct
from later ingestion or retention failures; never repeat the physical capture to
repair a file-only failure. Proposal/assessment subjects still require their own
closed stage successor and separate review, regardless of the capture design.

### Selected integration design — pre-seal capture checksum

The next increment selects design 1. Add `rocell.camera_capture_checksum.v1`, a
bounded checksum subject created by the existing capture owner after native
cleanup and before terminal sealing. It has no ingest-manifest fields: those
files do not exist at that point. Keep the prior `camera_capture_reference.v1`
launch candidate as a later ingestion join, not a substitute for this subject.

The checksum records exact native pair/preparation/request identities, native
frame metadata and byte hash, and bounded host read timing under the original
deadline. Failed/incomplete/interrupted observations remain explicit and cannot
claim verified bytes. The guarded reader is internal to owned capture completion,
derives its only pixel path from the exact prepared request, reads in bounded
chunks, and starts no camera/helper or new physical attempt.

Implement a separately versioned settings-capture evidence/permit contract next,
binding this subject into existing immutable multipart storage and receipt
accounting before any durable-success publication. Do not widen the legacy pair
codec, raise native effect limits, extend deadlines or treat a standalone checksum
file as an original. Tests of the checksum/reader alone do not complete retention.

### September 13 — pre-seal storage/accounting increment

Implemented the checksum codec and internal guarded reader, a separately typed
`SealedCameraCaptureEvidence` collection, its immutable part/index codec, and the
`physical-native-camera-configuration-capture-v2` original accounting contract.
The existing coordinator and M1 adapter route that exact contract independently
of the legacy native pair. All native camera counts remain intact. The combined
receipt includes the checksum digest/bytes and withholds overall cleanup and a
known-success seal when the checksum read is not successful.

Development tests exercise actual M1/NTFS write/read/reopen, consistently rehashed
tampering, missing checksum parts and a failed final-index write. They use modeled
predecessors/native producers and synthetic hashes. A separate reader test reads
a real 5472 × 3648 YUY2 synthetic file in bounded chunks, not a physical camera.
This is a storage/contract increment, **not yet the public camera-to-store chain**.

The subsequent fixed-input 20-module compatibility batch passed **384 tests**,
with no failures/errors/skips in 683.91 seconds. Source and selected inputs were
unchanged; all eight edited backend files matched the copy at handoff. See the
[storage/accounting evidence](../runs/wizard-exports/camera-durable-evidence-20260913-02/README.md)
for exact identities and scope. This does not close the public integration gate.

The public campaign constructor, original configuration admission, capacity
headroom calculation, dispatcher, ingestion and assessment still use their
existing production flow. Before selecting the new profile there, wire the
guarded checksum reader inside the existing consumed capture lifetime, retain it
before terminal publication, and authenticate it on subsequent original readback.
Do not use this internal read later to promote a historical unsealed checksum.
Preserve failed native diagnostics when a later checksum read cannot complete.
Include the extra bounded record/index bytes in pre-effect capacity admission;
keep the 25-second outer capture deadline and native effect limits unchanged.

The original proposal/assessment stage successor, reviewer/UI/export joins and
public fresh-launch reconstruction remain open. Current wizard captures do not
yet claim the newly implemented durable checksum path. M1 remains in progress.

### Next bounded slice — owned producer and pre-effect headroom

Add the exact inert plan schema
`rocell.physical_native_camera_configuration_campaign.v2`, selecting the already
defined checksum-bearing action/worker and maximum evidence bytes. Existing
probe, activation-capture and configuration-v1 plans must restore byte-for-byte;
their default construction and historical semantics remain unchanged. This is a
versioned contract selector, not an authority flag or browser action.

For this new profile only, use the existing consumed capture owner once, preserve
its native evidence immediately after cleanup, and bracket the guarded checksum
read with the existing original/source/runtime revalidation. The read, both
checks and cleanup use the unchanged outer deadline and check budget. A denied
context, invalid clock or interrupted reader must retain native counters without
inventing read timestamps or a digest. Introduce the closed
`PIXEL_READ_NOT_ATTESTED` failure status for that explicit absence; the combined
receipt stays uncertain. Late KeyboardInterrupt is propagated only after the
existing core retains the returned diagnostics and seals uncertainty.

Extend the existing read-only capacity arithmetic for exactly this action: one
additional bounded base64 checksum record and the versioned final index fit the
unchanged original quotas. Do not credit partial pixels, create directories,
reserve disk, increase physical limits, renew a permit or replay a capture.

Verify real file reads through the actual campaign/core with modeled native
owners, plus exact plan restoration, currentness faults, Stop/deadline, malformed
reader returns, repeat refusal and capacity thresholds. This slice must not
select the new profile in the wizard until original admission, dispatcher,
ingestion and assessment joins are all ready. Public migration is a subsequent
integration gate, not something these isolated producer tests prove.

Implementation of this slice is now present in the existing campaign and capacity
owners. It adds no new native helper or public action. New tests compose the
actual campaign/core with guarded synthetic pixels and also real M1 write/read/
fresh-store reopen, while explicitly modeling original setup and native owners.
The first development batches exposed test-fixture issues (a pure-code DLL guard
used for a file test, a 17-byte fixture for a 16-byte frame, and a cancellation
expectation inconsistent with the retained native status). Corrections preserve
the production size, cleanup, cancellation and ownership checks.

The corrected producer/storage development batch passed **55 tests** in 231.05
seconds. Its subsequent fixed-input 15-module compatibility batch passed **268
tests**, with no failures/errors/skips, in **701.62 seconds**. All 15 modules
actually executed; source and selected inputs were unchanged. Four touched
backend files and seven edited/new test files matched the snapshot. See the
[producer verification checkpoint](../runs/wizard-exports/camera-durable-evidence-20260913-03/README.md)
for exact identities, preserved failures, test-layer boundaries and remaining
work. This verifies the internal producer/storage slice, not the public wizard
chain, full-history acceptance, whole-repository type checking or roadmap M1.

### Public migration work package — inspected integration points

This is the next dependency-complete slice. Do not flip only the wizard's profile
selector and leave the following joins on the legacy pair contract.

1. `camera_configuration_original_scope.py`: recognize the exact new plan/action
   together, independently reconstruct it from the same original probe,
   enrollment, settings and reviewed runtime, and bind the request action on all
   currentness/capacity checks. Continue validating the probe through its actual
   old request and complete original snapshot; never relabel or trim originals.
2. `camera_configuration_admission.py`: bind the exact versioned action and
   checksum-aware capacity into retained hazard/epoch facts. Preserve current
   operator conditions, qualified publication, CAMERA leases and no-envelope
   semantics. Introduce a distinct schema where record meaning changes; legacy
   readback must retain its original interpretation.
3. `physical_camera_capture_workflow.py`,
   `physical_camera_acquisition_service.py`, `camera_configuration_wizard.py`
   and `camera_operating_assessment_service.py`: carry the same exact profile
   through plan preview, restoration, original preparation comparison and
   dispatch. Avoid a second browser selector or a fallback to an older mode.
4. `physical_camera_dispatch.py`: authenticate the complete checksum-bearing
   collection and its three-digest receipt inside the original transaction;
   preserve failed collections in diagnostics. After clean lease exit, hand the
   unchanged native pair plus its earlier authenticated checksum to ingestion.
   Preserve the existing final context/logging/publication gates. No pixel
   handoff is allowed on uncertain outcomes or readback-scope exit failure.
   Explain the checksum/read outcome separately from native camera completion;
   missing read times remain unknown, and successful native counts must not make
   a later pixel, retention or context failure look like a successful UI capture.
5. The acquisition service and capture workflow: independently join the native
   preparation/request/settings to the checksum, hash guarded current pixels,
   and require equality with that earlier sealed digest before dataset/preview
   publication. The later ingestion deadline is file-only; it must not renew the
   consumed device attempt. Update bounded diagnostic/bridge allowances for the
   additional subject rather than silently exceeding an old pair budget.
6. `camera_operating_original_assessment.py` and `camera_operating_pixels.py`:
   select only explicitly named attempts, verify their exact original receipt/
   admission/settings, and source expected hashes from those sealed originals.
   Keep old launch-only captures diagnostic-only. Preserve stage-local versus
   later holds; durable capture bytes alone do not approve a stage or review.
7. Add full original-owner/service tests for legacy compatibility, fresh-launch
   reconstruction, changed bytes after sealing, wrong request/settings/plan,
   late Stop, failed logging, export after result-card rotation, and no replay.
   Only then switch new wizard requests to this profile and expose its truthful
   original-storage provenance. Proposal/assessment original stage records and
   separate review remain required to finish M1 and enter the later milestones.

The inspected production dispatcher currently computes the legacy two-part
receipt and the service rebuilds configuration-v1. Both are explicit remaining
boundaries, not evidence that the new producer is already available in the UI.

### Public migration contract decisions

Keep configuration-v1 readable and lower-level legacy construction explicit.
New public wizard requests will select configuration-v2 only after the complete
handoff is tested. The existing public action and consent fields do not change.
Use distinct v2 original-scope summaries, limited hazard facts and settings-epoch
documents for the new action; preserve v1 document bytes for old requests.

The dispatcher authenticates the complete M1 collection/receipt first, then
passes its unchanged native pair and exact checksum subject to the existing
staged ingestion method. The subject's presence selects the new inert plan for
independent preparation comparison. Omitting it cannot downgrade a new plan,
because its operation hash differs from configuration-v1. Compare the guarded
file's measured hash with the earlier checksum before creating an ingested
dataset. Keep the later ingestion candidate distinct from the original subject.

Expose new provenance through versioned diagnostic projections, not a permission
flag: original operating assessment v4 and original-checksum pixel-check v2.
The old v3 assessment/v1 pixel checks retain their exact meanings. Mixed legacy
and new capture selections must state each reference's origin; legacy logged
checksums never become sealed originals. Neither projection is a retained stage
assessment/review. Public UI and exports must display that remaining hold.

### Public migration implementation in progress

The original-scope/admission, complete dispatcher readback, staged pixel hash
comparison and versioned original/legacy assessment/UI projections are now
implemented. Their first guarded-file/JavaScript development batch passed 81
tests; real-store/service and full-size synthetic composition tests remain in
progress. The public wizard selector has not yet switched. See the
[active integration evidence](../runs/wizard-exports/camera-durable-evidence-20260913-04/README.md).

Integration source inspection also found that the camera coordinator's existing
settings-capture time ceiling recognized only the legacy action. The new action
now follows the identical original-expiry and minimum-lifecycle-window branch.
No new deadline, retry, native effect or arm-domain change is introduced. The
focused ceiling/floor tests passed six cases after correcting a test's field
name. This is a necessary public integration fix, not milestone acceptance.

Profiling the checksum contract selection identified repeated pure native-pair
decoding, including a large display projection built only to derive metadata.
The checksum metadata helper now derives its native assessment directly from
the exact pair it just verified, once per call, and reuses its local preparation.
No cached admission, shared parsed owner, skipped file audit or deadline change is
introduced. Equivalence and per-call revalidation tests accompany this change;
integration performance remains unaccepted until a separate serialized run.

The first serial full-resolution service test still reached the unchanged native
lifecycle-time hold. Two further pure redundancies are removed: collection
validation relies on the checksum verifier's existing exact-pair decode rather
than decoding that same pair immediately before it; permit binding compares the
additional original request key after the collection has independently rebuilt
all native/checksum joins. It does not rebuild the entire checksum again using
the same bytes and hashes. Legacy codecs, native counters, full store audits and
every source/lease/deadline boundary remain unchanged. All malformed-input and
original receipt tests must pass before public selection or acceptance.

The complete collection/contract batch subsequently passed 102 tests, with four
additional forged-object rejection cases also passing. Both full-resolution
service/store/reopening cases then passed (379.97 seconds total), including
mixed legacy/new reference handling. No stage assessment/review was retained and
no permission was restored. These remain development tests with modeled setup
semantics/native producers, not full-history acceptance.

The public wizard and read-only assessment service now select the exact v2 plan;
legacy lower-level construction remains explicit and readable. The existing
public queue/log/export tests are running, with additional assertions for the
exported checksum, request key and v2 admission facts. Final public composition,
fixed-input regression and original proposal/assessment stage records remain
open. No hardware call was made to perform this migration.

The first public test completed/exported its first capture, but the second still
reached the unchanged native startup-time hold. The execution verifier now checks
closed scalar/type fields and independently reconstructs its expected execution,
whose constructor authenticates collection/native semantics, before comparing
receipts and exact counter/enum types. This removes one redundant constructor
decode immediately before that same reconstruction; it adds no cache or bypass.
All 86 selected contract/campaign/deadline tests passed, including mutated frozen
execution fields. A new isolated public test is running; public acceptance remains
open regardless of that local optimization.

The isolated public two-capture/log/export test and current assessment service
subsequently passed (two tests, 121.68 seconds). The next gate is a frozen
21-module compatibility/public-composition selection including remaining UI and
failure cases, full-size original/legacy reopening, storage contracts and no
replay. It remains distinct from the nominal full-history acceptance lane and
does not retain original proposal/assessment stage records or approve hardware.

### Fixed-run failures and next receipt comparison

Checkpoint 04's frozen selection is still running. Its missing-pixel negative
case exposed a test expectation error: the existing path guard raises
`FileNotFoundError`. That exact absence expectation is corrected without changing
production rejection. The full-resolution all-new capture case also failed;
its retained run and supervision both report `FULL_LIFETIME_DOES_NOT_FIT`, with
14.766 seconds remaining against the unchanged 17-second lifecycle floor. The
mixed legacy/new case passed. These are not waived acceptance failures.

The next bounded optimization removes another redundant pure construction in
the M1 reader's new-camera branch only: a stored receipt is now compared directly
to one independently reconstructed sealed execution. The previous code first
constructed an execution from that same stored receipt/collection, then rebuilt
an expected execution again. Exact receipt types, native availability, permit
binding, checksums, counters, enums and absent-receipt semantics remain checked.
Legacy storage/arm branches, original file audits, quotas and deadlines are
unchanged. Tests must verify both execution and direct stored-receipt paths.

The new comparison passed a combined 102-case development selection (103.38 s)
and a separate actual-store/campaign/evidence/deadline selection of 69 tests
(180.92 s). These are different scopes, not a release total or an isolated
public-wizard latency acceptance. The broad frozen run still uses the preceding
implementation and its failures remain preserved.

Source inspection found the same redundant construction in the original
two-part camera receipt reader (including original probes). Apply the same narrow
direct comparison there: validate the exact legacy native binding, independently
derive its expected receipt and compare exact counters/enums/absence. Preserve
the public legacy execution constructor/validator, two-part bytes and stored
result reasons. No legacy record becomes a checksum-bearing record. This extends
the optimization to camera-only legacy reading, not arm domains or source/file
audit policy; it requires separate legacy compatibility tests before acceptance.

The separate [original submission work order](CAMERA_OPERATING_SUBMISSION_WORKORDER.md)
now defines a compound proposal/assessment record and a closed complete-snapshot
successor. Its pure contract passed 61 development cases; its initial layout
selection passed 18. A narrow M1 storage guard now binds the current original
three-package reviewed-probe boundary and full campaign-record inventory before
immutable publication. Five actual NTFS tests passed (53.59 s), with modeled
predecessors/native assessments: same-owner normal completion and fresh reopen,
distinct partial no-resume, corrupted payload and publication/readback failures.
The updated closed-error layout and old-reader compatibility selection is still
running. A full v17 original/native reader, public action, restart UI and separate
approval are not implemented. These files are outside checkpoint 04's active
frozen input and require their own fixed-input verification.

### Final checkpoint 04 and serial recovery

The frozen 21-module run finished **325 passed / 6 failed in 3103.01 seconds**,
with no errors/skips and unchanged source/input manifests. One failure was the
missing-file test expectation; the other five were native lifecycle-time holds
in nominal all-new/full-size, legacy/sealed second-capture, public wizard and
two-capture assessment paths. Preserve this failed revision as such.

The direct legacy receipt path passed **33 tests in 48.11 seconds**, including
native-unavailable accounting, exact scalar types, original bindings/deadlines
and actual M1 reopen. The preceding layout compatibility run finished **91 passed
in 448.98 seconds**. Neither is the full acceptance lane.

Checkpoint 05 freezes the receipt optimization and selects six serial nominal
paths. Its first copy was rejected for concurrent shared-workspace changes and
remains preserved. The separate `input-02` was created successfully; the nominal
run finished **6 passed in 673.30 seconds**, with exact test selection and
unchanged source/inputs. No competing test job was intentionally run alongside it.

New submission reader modules and v17 session routing are now implemented in the
working tree, with their remaining gates listed in the submission work order.
They are outside that nominal copy. Public submission/restart/export acceptance,
continuity/review, freshness and later roadmap milestones remain open.
