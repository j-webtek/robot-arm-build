# Original source-stage admission: implementation plan

2026-09-08. Work order and implementation guide under the camera/arm developer
playbook and `CAMERA_ACQUISITION_DISPATCH_IMPLEMENTATION.md`. The source-stage
implementation is present and tested. The full camera/arm connection goal is
still in progress; physical release remains held.

## Outcome

Replace the missing source-stage reassessment workflow with a usable original-
store collect/assess/review path. Preserve original source-v1 and intake history.
Accepting workspace source prerequisites must not pretend that a native runtime,
received camera, controller firmware, installed geometry or actuator power is
qualified. Actual camera/arm admission remains a later, distinct decision.

No hardware is available during development. Positive physical observations in
tests are explicitly modeled. The actual application starts with UNKNOWN
isolation and cannot convert that into an observed disconnected condition.

## Stage-relative acceptance contract

The original source-v1 assessment remains BLOCKED forever as historical data.
A new source qualification can be assessed eligible only when:

1. Fresh controlled source/build/foundation/host checks all pass, with the
   original workspace/session/header/prerequisite lineage still verified.
2. The operator explicitly records having observed disconnected actuator power,
   supplies an original attachment and notes, and a distinct procedural reviewer
   reviews the exact resulting subject. An uploaded image or label alone proves
   neither its contents nor an electrical condition. UNKNOWN remains blocked.
3. A fixed server-owned, hardware-free ownership experiment completes with the
   required software-mechanism checks. It is not a generic test runner, a user-
   supplied 'tests passed' file or a native-device release credential.

HZ-012 is stage-relative: these tests establish software ownership/replay
mechanism coverage. Actual selected-device identity after lock acquisition and
received-hardware residuals must still be checked for each effectful admission.
The global hazard registry and native release holds are not cleared. Static
camera installation/release qualification is likewise a downstream obligation,
not a cyclic requirement for accepting controlled source files. Do not modify
Freeze-011, RC03, the existing source-v1 record or runtime activation flags.

## Ownership experiment — Windows agent

Implement `physical_ownership_qualification.py` and one fixed incapable child.
Use existing durability, ordered-lease and M1/coordinator implementations. Run
only within a fresh, assigned same-volume experiment directory; no camera,
serial, provider inventory or physical native helper may run.

Required cases:

- Actual on-volume Windows durability/locking qualification.
- A fixed child holds CELL -> SESSION -> CAMERA -> ARM_CONTROLLER in order.
- A live contender is denied and cannot mutate the original ownership record.
- Clean release/reacquisition preserves the expected owner lineage.
- Intentional exit of that owned child while leases are held leaves stale ACTIVE
  metadata; another contender is denied without takeover or repair.
- Controlled process-start/PID-mismatch input is denied. Label this fault
  injection, not observed operating-system PID reuse.
- A fixed NO_DEVICE_IO original-M1 attempt is retained; reopening cannot redeem
  an old permit or replay the consumed request key. Bind its lease, attempt,
  identity and source records. Do not import or launch pytest as qualification.

The collector returns a bounded immutable report with source/root/platform,
case outcomes, exact original file/owner/attempt references, zero device-effect
counters, actual-vs-modeled distinctions and downstream residual obligations.
Failed/partial experiments are preserved. No automatic retry or stale cleanup.
Provide a strict report verifier and an explicit deadline/Stop boundary.

## Durable successor grammar — storage agent

Extend the original reader with
`rocell.physical_camera_source_workflow_readback.v4`. Leave v1-v3 interpretation
unchanged. Verify the original source/intake prefix from the audited journal,
then a closed qualification-only suffix. Do not fabricate an earlier store.

Qualification IDs are `sourcequal-<32 lowercase hex>`. Each cycle uses these
labels with `:<qualification-id>` appended:

- `workspace-source-isolation-original-v1` (optional original binary/text bytes)
- `workspace-source-qualification-receipt-v1` (JSON)
- `workspace-source-qualification-assessment-v1` (JSON)
- `workspace-source-qualification-review-v1` (JSON)

The receipt binds original source/cell/session/header/origin, collection launch,
qualification ID, actor, exact original source receipt/assessment/review,
prerequisites and any predecessor qualification trio. It contains fresh software
observations, the ownership report and the explicit isolation statement/reference.
The assessment binds that receipt. The review binds both exact subjects and a
distinct procedural reviewer label. Labels are not authenticated identities.

Events use the qualification ID's uppercase hex suffix:

1. `WORKSPACE_SOURCE_QUALIFICATION_STARTED_<HEX>` -> stage 1 WAITING_OPERATOR.
2. `WORKSPACE_SOURCE_QUALIFICATION_ASSESSED_<HEX>` -> REVIEW_PENDING, with exact
   receipt and assessment references (and optional original attachment).
3. `WORKSPACE_SOURCE_QUALIFICATION_REVIEWED_PASS_<HEX>` or
   `WORKSPACE_SOURCE_QUALIFICATION_REVIEWED_BLOCKED_<HEX>` -> PASS or BLOCKED,
   citing exact original subjects and review.
4. Separate explicit `STATIC_CAMERA_CONTRACT_REQUESTED_<HEX>` -> stage 2
   WAITING_OPERATOR after a committed PASS. It cites no cross-stage evidence.

Support a bounded successor cycle after reviewed BLOCKED, without interleaving
new legacy intake cycles. Each new cycle may collect a new isolation original
directly from the same guarded inbox; it need not rewrite an earlier intake.
Preflight reference/byte limits before START. Keep the existing 32-reference and
4 MiB original-reader limits; do not evict old evidence to make room.

Readback must distinguish START-only, partial retained packages, complete but
uncommitted assessment/review, committed PASS with stage 2 still PENDING, and an
explicit stage-2 request. Refresh never synthesizes the missing event. Stages
3 onward stay PENDING until their own adapters are implemented.

## Application owner and exact subjects — root

Implement closed receipt/assessment/review codecs in
`physical_source_qualification.py`, plus a service that composes the existing
source collector, fixed ownership experiment, guarded inbox and original M1
transactions. Pass only server-resolved original bytes/references between them.

The service starts no experiment on import, constructor, GET, restored snapshot
or ordinary wizard startup. Explicit collection validates the selected context,
collects bounded facts, retains exact original subjects, commits REVIEW_PENDING
and audits readback. Explicit review reads originals and commits only their
deterministic verdict. An acknowledgement cannot upgrade BLOCKED to PASS.

Use the existing shared action/coordinator conventions: current context ticket,
one-use attempt, no automatic replay, work outside the Arrival lock, responsive
Stop, post-scope/source checks, complete result retention and completion-log
publication. Preserve late failures as historical diagnostics. Keep explicit
stage-2 entry separate from source review so restart cannot advance it silently.

## UI, diagnostics and recovery — UI agent / root integration

Add a separately versioned `source_reassessment` projection in the existing
Camera setup area. Keep closed legacy source and camera schemas unchanged.
Show current software checks, retained isolation statement, ownership coverage,
missing requirements, original subject hashes, commit state and next action.
Use the caption: 'Stage 1 accepted only — no camera runtime release.'

New actions collect/assess source qualification, review its exact subjects and
explicitly enter the static-camera contract stage. Original attachment choices
come from bounded guarded inbox discovery, not caller paths. UNKNOWN is the
default observation. No pass checkbox or operator-supplied qualification hash.

After reassessment begins, old source/intake reviews remain visible as historical
subjects; do not relabel their BLOCKED verdicts or make them claim the new
canonical stage state. Export full new metadata through the selected workspace
export parent. Original attachment export retains its separate privacy consent.

## Acceptance tests and completion record

Exercise actual fixed child contention and real M1 storage on Windows, with no
device calls. Separately model observation/qualification success and faults for
the full public wizard action chain, exact review, PASS -> explicit stage 2,
blocked successor correction, restart at every partial boundary, export and
both renderers. Test original prefix compatibility, orphan/wrong-subject
rejection, stale source/head, mismatched actors, Stop, unknown observations,
failed lease exit, failed logging, file limits and no automatic actions on GET.

Do not call the overall camera/arm goal complete when this stage is done.
Camera runtime release/output ownership, stages 2-8, physical arm stages 9-12,
installed calibration and later motion/contact admission remain in scope.

## Operator flow in the current application

From the workspace root:

```powershell
.\start-rocell-wizard.ps1 -Mode physical -Check
.\start-rocell-wizard.ps1 -Mode physical
```

The physical-mode shell is still a **file-only diagnostic workbench**, not an
instruction to plug in, energize or move the arm. Ordinary startup and page
refresh do not run qualification, discover an inbox or open a device.

1. Use the existing source preflight and Camera original-store setup actions.
   Initialize a new original **or explicitly discover/reopen the existing one**;
   do not initialize replacements to work around a partial operation. For a new
   store collect its prerequisites, assess its original sources and review the
   exact original assessment. This older subject intentionally remains BLOCKED.
2. If a legacy intake collection is already underway, review its exact complete
   subject first. After reassessment starts, that older intake is historical;
   new source observations use the reassessment actions, not interleaved intake.
3. For actual isolation evidence, place a supported regular file in
   `software/runs/physical-intake-inbox`, then explicitly discover source
   isolation files. The first discovery can prepare the empty assigned inbox.
   Choose only a discovered file token; the browser never supplies a raw path.
   A photograph/text/PDF is retained evidence, not proof of its electrical claim.
4. Run source qualification with a portable operator label. The default is
   **UNKNOWN**, with no attachment and an optional empty statement. An actual
   observed disconnection requires an attachment and a descriptive one-line
   statement (12 or more characters, at most 512 UTF-8 bytes). Do not record
   an observation that has not occurred. Fresh software collection and the fixed
   ownership experiment run before any original source-stage mutation.
5. Read the outcome. Successful execution of this diagnostic can still produce
   a **BLOCKED assessment**. With hardware absent, isolation is UNKNOWN and the
   stage cannot pass. An eligible PASS assessment is only a review subject.
6. Run exact source-qualification review with a distinct reviewer label. The
   verdict is derived from the exact originals; there is no PASS checkbox or
   override. Distinct labels are a procedural check, not authenticated people.
7. Only a committed, logged stage-1 PASS offers the separate action to begin
   the static-camera contract stage. That action leaves stage 2
   **WAITING_OPERATOR**, not accepted. It does not register a native runtime,
   open the camera, start the arm, calibrate or enable typing/tapping.
8. Use **Export logs**. The confirmed export parent is
   `C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
   Each export remains separately verifiable. Source reassessment metadata is
   retained in `attachment-source-qualification-data.json`, alongside the
   original source/setup metadata. Private isolation originals are not embedded
   in this sanitized JSON. They remain in their original M1 evidence store;
   a dedicated private-original export action for these new subjects is not yet
   implemented. The older intake private export applies only to intake files.

Collection has a 300-second overall bound (source collection, at most 120
seconds of ownership experiments, then at most 120 seconds of storage work).
Discovery is bounded to 60 seconds; review and explicit stage-2 entry to 120
seconds. Stop prevents further admitted work, but does not undo retained bytes
or committed events. Partial originals, failed experiments and historical
results are preserved; no retry, takeover, cleanup or stage advance occurs on
refresh. Reopen audits the original rather than recollecting its evidence.

## Developer implementation map

| Component | Responsibility | Does not provide |
| --- | --- | --- |
| `physical_source_qualification.py` | Closed canonical receipt/assessment/review codecs; deterministic stage-relative verdict | Filesystem collection, native admission, physical truth |
| `physical_ownership_qualification.py` and fixed child | Actual bounded Windows ownership/durability/replay mechanisms and strict retained-report verification | General command runner, device inventory, port/camera access |
| `physical_source_qualification_service.py` | Current context, guarded choices, fresh collection, original retention, exact review, pending publication | Automatic effects on GET/startup, replay or PASS override |
| `PhysicalCameraSetupService.qualification_transaction` | Exact original session/head/inventory checks, serialized storage and audited readback | Camera/controller permission or implicit stage entry |
| `physical_source_qualification_readback.py` | Closed append-only v4 grammar and original subject relationships, including partial prefixes | Repair, fabricated missing commits, rewriting source-v1 |
| Arrival + shared action catalog | Current action tickets, worker/Stop orchestration, exact complete result and durable log before publication | Caller-provided evidence hashes or arbitrary command execution |
| Browser/terminal + metadata exporter | Cached bounded presentation and assigned-folder diagnostics | Raw private isolation bytes or a claim that hardware is ready |

See [the fixed ownership API and failure contract](PHYSICAL_OWNERSHIP_QUALIFICATION_API.md)
before changing the collector or consuming its retained failure report.

The service verifies and caches its compact summary when adopting an audited
original. Browser GETs copy that cache; they do not repeatedly verify full nested
ownership reports or perform filesystem/device work. Full documents are flattened
in their dedicated metadata export so nested lineage stays readable and bounded.
Existing source-v1/v2 and intake display contracts are not widened or relabeled:
their original BLOCKED subjects become historical when qualification begins.
Byte-identical documents are stored once per export and referenced by document
keys, including duplicates between the latest attempt and an audited cycle.
Reconstruct a receipt by resolving its `document_key`, then restoring its nested
`software_receipt` and `ownership_report` from their `*_document_key` values.
Reconstruction is tested against the complete original canonical bytes, not
merely its claimed hash. Original evidence files and their hashes never change.

## What still blocks the full connection goal

This implementation replaces one previously missing stage-entry path; it does
not finish the camera/arm application. Remaining joins include static-camera
contract/received-unit qualification, qualified native runtime and assigned
output ownership, source-stage outputs in the progressive configuration record,
effectful original admission and public probe/capture dispatch, real controller
startup/feedback stages, installed calibration and separate noncontact/contact
approval. No firmware/native build pins, Freeze-011 or RC03 were changed here.

## Verification checkpoint

Final code/configuration source fingerprint:
`1a3ee05a4ee735f9ae0680f0f1b6f092560405f0888eb00cb8b0e9f3f4d7aa6a`.

Executed checks (these selections overlap; do not add their counts):

- 267 new-feature and adjacent camera-dispatch/acquisition regressions passed
  in 167.31 seconds before the final export deduplication change.
- The final deduplication candidate passed 35 service, maximum-history export
  and public composed-action tests in 37.99 seconds. It passed the separate
  two-case exact export-size/reconstruction rerun in 5.26 seconds.
- The UI/Arrival agent's finite nine-file regression passed 362 tests in 59.64
  seconds, including original producer to public tickets, durable logs, chosen-
  folder export and both production renderers. Browser rendering uses a Node
  fake DOM; this is not a live-browser or physical-camera observation.
- The original reader's combined compatibility run passed 166 tests in 208.09
  seconds, including actual NTFS restart at partial and committed boundaries.
  A final pure 60-case run covered the explicit original-workspace binding join.
- The fixed ownership suite passed 47 tests, including real Windows Job-contained
  child processes, actual leases/durability/M1, no replay, and Stop cleanup. Only
  the workspace fingerprint is modeled in those isolated process tests; no
  camera, serial port, native inventory, power or motion is invoked.
- Both launcher `-Check` modes report `READY_FOR_DIAGNOSTICS` on the final source.
  Changed production Python modules pass Black/mypy; browser JavaScript passes
  its syntax check. An offline wheel build contains 271 matching code/UI entries,
  with no missing, extra or differing entries against the workspace.

Physical isolation, received-device results and successful physical qualification
are **modeled only** in positive service/reader/UI fixtures. UNKNOWN remains
UNKNOWN in ordinary operation. Actual filesystem/process checks are not proof of
the installed bench, camera, electrical state, calibration or arm behavior.

Two actual-codec public workflows exercised UNKNOWN/BLOCKED and modeled
observed/PASS followed by explicit stage 2. Both exports fit the unchanged
eight-attachment cap and verify successfully with prerequisite/source/configuration
metadata present. Reserved qualification documents survive rotating action cards;
any omitted older generic action results are explicitly listed. Private original
attachment bytes stay out of the JSON bundle.

The representative eight-cycle, covered-ownership/BLOCKED history initially
exceeded the 1 MiB attachment cap because its latest attempt duplicated retained
subjects. Exact-byte deduplication reduced the final tested full-history-plus-
attempt metadata to 595,456 canonical / 756,124 formatted bytes, 11,768 sanitizer
nodes and depth 9. The source originals remain reconstructable byte-for-byte.
This is a tested representative maximum-cycle history, **not a guarantee that
every possible 4 MiB original store fits a 1 MiB diagnostic attachment**. Larger
unique metadata must fail the existing export bounds without truncation or a
complete-export claim. A future bounded multipart export can address that case;
no global limit was raised and no historical data was deleted.

Reproduce the final service/export integration selection from the workspace:

```powershell
.venv\Scripts\python.exe -m pytest software/tests/unit/test_physical_source_qualification_service.py software/tests/unit/test_source_qualification_export_limits.py software/tests/unit/test_arrival_source_qualification_composed.py -q
```
