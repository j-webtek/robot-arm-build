# Camera operating-policy proposal and evidence preflight

Date: 2026-09-12. Camera-only, software-only successor to
`CAMERA_MODE_REVIEW_GUIDANCE_WORKORDER.md`. Status: pure implementation complete;
broader isolated verification and owner/UI integration tracked separately below.

## Outcome and boundary

Add a callable, tested proposal and native-evidence preflight for the purchased
B0477. This is the numerical/contract layer of stage 5, not a new wizard approval
action. Keep the original purchase profile, 9-fps reference, native protocols,
original-store owners, UI routes and arm code unchanged.

1. Encode a bounded immutable proposal with the exact selected rational mode,
   settings epoch, purchase-file and canonical hashes, original mode-entry hash
   and context, current probe selection, proposer label and rationale. An 8-fps
   proposal requires a separate explicit variance rationale. It does not rewrite
   or repair a prior failed 9-fps request. No automatic selection or fallback.
2. Reconstruct capabilities from native probe evidence and staged settings from
   those capabilities. Reconstruct each retained readback from its own native
   capture evidence. Support the existing legacy and v2 observation domains
   without converting one schema into another. Compare independently supplied
   hashes; do not trust UI summaries or objects solely because they parse.
3. Assess zero, one or two bounded capture subjects. Require exposure and white
   balance in manual mode, distinct probe/capture attempts and permits, successful
   closed reports, matching mode/layout and consistent capture runtime. Two
   reports are metadata evidence, not proof of physical reopen order or pixels.
4. Preserve explicit missing checks. A consistent result still has no stage PASS,
   capture permission, physical qualification or authenticated operator identity.
   Original storage/currentness, USB speed/identity continuity, ordered reopen,
   verified pixels and separate review remain owner-level obligations. Historical
   stage-entry identity and a fresh probe selection are separate hash domains.
5. Reject altered source, entry context, purchase bytes, settings epoch, evidence
   references and modified readbacks. Re-derive an assessment when verifying it;
   a copied JSON result is never an approval token. Use exact rational arithmetic.
6. Exercise the production codecs using explicit in-memory native observations,
   including faults and noncanonical inputs. Prohibit process/device operations
   in these tests. Run existing adjacent camera regressions and record the exact
   selection, then export a readable handoff to the workspace export folder.

## Wiring contract for the subsequent owner/UI increment

The original stage-5 owner must obtain independently verified entry, profile,
probe, settings and capture/readback bytes under its current operation scope.
Caller-supplied hashes are comparison inputs, not an original-store credential.
Retain proposal and assessment as separate original records; publish and read
back the assessment before offering a separate operator-review event. Recheck
source, setup, identity continuity, settings and Stop/revision at publication.

Do not offer approval until original-store retention, journal publication, export,
restart reconstruction and invalidation tests pass. Join the USB-speed subject,
original acquisition ordering and pixel-file verification there. Do not invent
a passing USB observation, infer hardware serial identity from endpoint hashes,
or treat two distinct report IDs as proof of reopening. Stage 6 freshness and
installed optical calibration remain separate. This increment intentionally adds
no active service action or UI approval button.

## Implemented developer interface

`rocell.application.camera_operating_proposal` owns the versioned proposal bytes.
Call `build_camera_operating_proposal` with operator intent and independently
checked entry/profile/configuration subjects. Keep its original payload/hash;
`verify_camera_operating_proposal` reconstructs it against supplied current
subjects. The target comes from staged settings, never from a default or a
request to silently switch modes. Only full-resolution YUY2 at exact rational
8 or 9 fps is in this first proposal schema. Other modes require later policy
design; they are not automatically proposed by this helper.

`rocell.application.camera_operating_evidence_preflight` accepts those same
subjects plus capability bytes, one `CameraNativeEvidenceSubject` for the probe,
and a tuple containing zero to two `CameraReadbackSubject` objects. Each native
subject includes its preparation, evidence and independently supplied original
hashes. V2 requires both run and supervision artifacts/hashes. These input
objects are data bundles, not authentication credentials or executable plans.

`assess_camera_operating_evidence` reuses the existing probe/configuration/
readback verifiers before producing its six named checks. Invalid provenance
joins raise `CameraOperatingPreflightError`; valid missing/failed observations
produce `BLOCKED_METADATA`. Successful comparison produces only
`CONSISTENT_METADATA_PENDING_ORIGINAL_REVIEW`. The report retains all unresolved
owner obligations and all authority flags remain false. Matching manual readback
values on two captures does not establish that settings survived a reopen without
being reapplied. Physical reopen order must be established separately.

`verify_camera_operating_evidence_preflight` takes the saved bytes, independent
report hash and the assessor's original named inputs. It recomputes every check;
editing checks and recomputing a JSON hash cannot substitute for the native
evidence. Outputs are detached dictionaries over frozen canonical bytes.

The executable examples are in
`software/tests/unit/test_camera_operating_evidence_preflight.py`. Its `case`
fixture creates full-resolution metadata without allocating camera images or
opening devices. Both legacy and current v2 records pass through the production
codecs. The v2 supervisor receives an explicit modeled owner. Existing autouse
guards reject real process/native-library/device operations. Do not import these
fixtures into the application or treat their generated data as physical evidence.

## Verification ledger

Initial development selection: **69 passed in 30.98 s**, recorded in
`.codex-preserved/camera-operating-preflight-20260912-01.xml`. Subsequent schema
hardening adds 13 tests; this initial run is a subset, not additional unique
coverage. The two new production modules pass focused Mypy checks. Black formats
only the three newly owned Python files. Full-history acceptance and original
stage-5 publication/restart are not claimed by this pure-contract increment.

Two full-workspace snapshot attempts (`camera-operating-preflight-isolated-20260912-01`
and `-02`) detected concurrent changes and remain preserved, unaccepted partial
copies. Observed differences included shared Arrival/actions and powered-arm
files; these were not edited by this camera increment. Use a smaller, explicitly
scoped software-contract snapshot for these new pure modules. Do not relabel it
as the existing full-history lane or whole-workspace acceptance. Keep the full
original publication/restart gate for the subsequent owner integration.

### Completed scoped acceptance

Snapshot: `.codex-preserved/camera-operating-contracts-scoped-20260912-01/input`,
created 20:59:55 UTC. Its explicit developer scope contains `software/src`,
`config`, `tests`, `scripts`, `docs`, plus software README and pyproject:
**1,229 files / 24,017,762 bytes**. The snapshot helper's input-tree constants were
set only in the inline developer process; its installed/copied code was not
edited. Hardware/native asset trees and the full workspace are not in this scope.
The complete selected inventory matched before, during copy and after creation.

Input roster: `d5c499b491eaba65063013db6667a0f6778ddf4f908dfa8ef44b416d8547e62a`.
Software-source file-roster digest:
`18f32ec23c4027b127c30e314cb993d64bb9df1766790a84ea5ddf82487d3f05`.
This is explicitly not the application's full-workspace `source_fingerprint`.
The first scoped invocation (`tests-01`) stopped before collecting any tests
because that full-workspace function requires files intentionally outside the
scope. It remains preserved, not counted as a test result. The successor uses
the scoped manifest and source roster without changing any application validator.

`tests-02/junit.xml`: **474 passed in 60.33 s**, zero failures/errors/skips;
all 474 collected identities executed. The 82 new cases include both native
evidence versions, rational 8/9-fps modes, missing manual controls, duplicate
captures, changed runtime/layout, failed capture/cleanup, stale entry/settings,
forged readbacks/reports and bounded closed-schema rejection. Adjacent cases:
41 physical configuration, 28 guidance, 18 purchase profile, 147 mode-entry
contract, 88 native-v2 evidence, 38 activation-pair and 32 multipart evidence.

JUnit SHA-256:
`c6d0fb67978697e5d0b1305da6f2bc96036c0687cd17d94bbcb512b7b81c8037`.
All copied input hashes and the source roster matched again after pytest. The
isolated invocation used `python -I`, imported the copied application and runner,
disabled plugin autoload, bytecode and pytest cache writes, and used a new
external result/basetemp directory. The adjacent execution audit preserves its
structured stdout; it is unsigned developer bookkeeping. Python 3.10.10,
pytest 8.4.2 and installed dependencies are shared, not separately frozen.

Final Black checks pass all three new Python files; focused Mypy passes both new
production modules. No native binary, driver, camera, USB query, arm connection,
serial, power, motion or live UI ran. No whole-repository static check, full UI
regression, end-to-end original-store review or physical qualification is claimed.

Readable export:
`software/runs/wizard-exports/camera-operating-preflight-20260912-01/README.md`.
The next implementation remains the original-owner proposal/assessment retention,
publication/readback and separate wizard review event described above. This pure
backend is not yet an active wizard action and does not complete stage 5.

## Successor: logged proposal-draft UI — 2026-09-12

The [proposal wizard work order](CAMERA_OPERATING_PROPOSAL_WIZARD_WORKORDER.md)
now connects the proposal builder to existing preview, execution, logging,
browser/terminal status and export. This is a cached-subject draft, not an
original-store assessment or approval route. The evidence-preflight backend is
not automatically called with an incomplete cached capture list. Its successor
regression passed 605 cases, including 37 new draft/UI cases, with unchanged
copied inputs and no device access. See that ledger; this does not replace the
prior acceptance record or close stage 5.
