# Saved-pixel assessment and wizard continuation

2026-09-13. Software-only implementation; no camera or arm operations.

## Increment and rationale

The current operating assessment authenticates native metadata but leaves pixel
files unchecked. Native receipt metadata contains no pixel digest: hashing a
file for the first time now cannot prove it is the originally captured image.
Use the checksum from the exact, successfully logged settings-capture result,
then join its attempt/evidence/settings/endpoint to independently read M1 native
originals. Keep this launch-log provenance distinct from canonical stage storage.

## Implementation sequence

1. Extract a bounded pixel reference from each explicitly selected capture's
   retained completion, checking its exact result hash and source/session.
   Never accept a user-supplied path/hash, choose a latest capture or restore a
   reference from an imported export.
2. Reuse the original-assessment owner and existing regular-file/directory
   guards. Verify the exact single native YUY2 file in its original assigned
   capture directory with bounded streaming and cancellation/deadline checks.
   No image conversion, acquisition, file repair or settings writes.
3. Return a versioned assessment with per-capture pixel outcomes. Missing logged
   references or invalid files remain explicit; a successful file read is not
   frame freshness, USB continuity, ordered reopening or operating approval.
4. Extend the existing wizard checklist, retain legacy reports as historical,
   and include the new outcome through existing diagnostic exports. Keep all
   original action tickets, ownership, deadlines and stage gates unchanged.
5. Test valid/corrupt/missing/linked files, mismatched subjects, cancellation,
   legacy/new UI results and no-device wizard/export paths. Record exact scope
   and remaining work in this file.

## Still required after this increment

Execution order and completion gates are now consolidated in the
[camera/UI commissioning roadmap](CAMERA_UI_COMMISSIONING_ROADMAP.md).

- Canonical proposal/assessment journal records and independent exact review.
- USB speed/identity continuity and independently ordered close/reopen evidence.
- Separate frame-freshness qualification and received-unit wizard testing.
- Full-history/current-source acceptance and growing-history performance.
- Installed height, focus, iris, board coverage and calibration after assembly.

The 8-fps proposal remains an explicit reviewed variance; the frozen purchase
profile is not edited. Existing bench evidence and failed runs are preserved.

## Verification

Implemented: original-assessment report v2, bounded saved-file verification,
wizard packet binding and result checklist. No new action, automatic acquisition,
approval state or physical operation was introduced.

Development run `development-02.xml`: **116 passed in 289.01 s**. The earlier
`fast-01.xml` is retained: 103 passed and one test-fixture failure; the fixture
now supplies the packet API alongside its already modeled selection/context API.
Production capture selection and currentness checks were not weakened.

The fixed-input 20-module regression passed **601 tests, zero failures/errors/
skips, in 386.67 s**. Copied input roster and application source were unchanged
after execution. Its results and reproducible developer runner are under
`software/runs/wizard-exports/camera-pixel-assessment-20260913-01`; see its
[handoff](../runs/wizard-exports/camera-pixel-assessment-20260913-01/README.md).
This is selected regression testing, not the dedicated full-history lane.

The non-operating browser preview displayed two fictional verified files and
the six remaining requirements correctly. All preview POSTs are disabled; no
real wizard/device owner was constructed. Syntax checking passed the browser
script, Black passed the eight owned Python files, and focused Mypy passed all
four assessment production modules. No physical acceptance claimed.

## Code connections and operator flow

1. Use the existing Camera page and its prerequisite-gated settings/capture
   workflow. This increment does not enable prerequisites or acquire a frame.
2. After a logged operating-proposal draft, open **Check proposal against saved
   original evidence**. Explicitly select two distinct saved settings captures,
   or leave one/both empty to diagnose incomplete evidence. Preview and execute
   remain separate. Neither opening the page nor loading a result re-runs a check.
3. `camera_operating_assessment_wizard.py` pins the proposal and selected capture
   packets. The assessment service reuses the original owner, leases and deadline.
4. `camera_operating_original_assessment.py` independently reconstructs original
   capture subjects. `camera_operating_pixels.py` joins each subject to its
   previously logged completion checksum and streams the exact native YUY2 file.
   Reads use at most 1 MiB chunks and the existing 64 MiB per-frame limit; they
   do not decode, resize or duplicate full-resolution images in memory.
5. **Load assessment checklist** displays metadata and saved-pixel outcomes.
   Successful reads remove only the pixel-file hold when both selected files
   verify. Remaining USB, ordering, freshness, review, calibration and canonical
   stage-retention requirements remain visible. Older v1 reports retain their
   historical unchecked-pixel meaning.
6. Use **Diagnostics & exports** to retain the complete assessment through the
   existing assigned-folder export. The dedicated operating-assessment attachment
   survives generic card rotation. Imported exports cannot restore an operating
   permission or supply a missing current-launch checksum reference.

| Pixel outcome | Meaning and next step |
| --- | --- |
| VERIFIED_AT_READ | Saved bytes match the retained capture checksum at read time; continue reviewing the other holds. |
| LOGGED_REFERENCE_UNAVAILABLE | A valid earlier logged checksum is absent; preserve diagnostics. Do not invent a checksum from today's file. |
| REFERENCE_MISMATCH | Original subject, settings, endpoint or assigned path disagrees; preserve and investigate the selected records. |
| PIXEL_FILE_UNAVAILABLE_OR_CHANGED | The file cannot be safely opened or fails length, inventory, link or checksum checks; preserve diagnostics. No repair or recapture is automatic. |

The reference is retained launch-memory completion data joined to M1 native
originals. This does **not** authenticate a separately reopened on-disk completion
log or implement canonical stage-5 persistence. Tests distinguish real NTFS/M1
and tiny synthetic pixel reads from modeled hardware/predecessor observations.
