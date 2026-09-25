# Guided physical intake notebook — implementation brief

Date: 2026-09-08. Status: implemented; final integration verification below.

## Outcome and boundary

Add a usable form to the existing local wizard for the sixteen passive camera
receipt / placemat / bench questions owned by `camera_receipt`. Requirements
come from the original, verified camera prerequisite artifact, not a duplicate
list of nominal dimensions. The operator can select a question, record an
actual observation and method, describe evidence to collect, revise the entry,
and export a complete current notebook through the assigned diagnostics folder.

This is deliberately a **draft notebook**, not an accepted camera receipt.
Recording notes out of canonical stage order must not append camera-receipt
stage events, review evidence, power assertions, configuration epochs or permits.
Source/isolation review and static-camera-contract acceptance still precede
canonical camera receipt. INT-005 has a measured value but no accepted flatness
limit until the target accuracy budget is closed at non-contact acceptance.

## Data and interaction contract

1. Require a CURRENT, original M1-read-back camera prerequisite artifact from
   explicit initialization/collection or verified original-store reopening.
2. Bind the notebook to its exact source, original camera session/origin launch,
   prerequisite hash and current application launch. Views are cached/pure;
   browser input never supplies an evidence path, native endpoint or command.
3. Derive exactly the sixteen `camera_receipt` questions from the typed artifact.
   Keep candidate requirements visibly separate from blank observation fields.
4. Two explicit actions: start the draft notebook; record/revise one selected
   question. Use the normal prepare/confirm/execute ticket with a notebook hash.
   No autosave, inferred observation, default measured value or automatic test.
5. Entries distinguish OBSERVED from UNKNOWN. OBSERVED requires a value and
   method. Physical dimensions/mass accept finite positive decimal values in the
   source unit (flatness may be zero); text questions accept bounded text.
   UNKNOWN stores a reason, not an invented numeric value. An evidence note is
   an operator description only: **no attachment bytes are read or verified**.
6. Retain a complete bounded notebook snapshot in every successful action result,
   including revision number and previous snapshot hash. Older entries are not
   physically erased from retained historical diagnostic results. Publish the
   new current notebook only after exact unredacted result retention, successful
   completion logging, source/context checks and no Stop request.
7. Export uses the user's assigned workspace `software/runs/wizard-exports`.
   Also include the latest notebook as a dedicated bounded export attachment so
   it survives the generic last-eight-operation retention window. No file is
   automatically imported on another launch. Export is currently the durable
   handoff; restart restoration of draft observations is a separate future task.
8. Source changes, selected-session changes and outer diagnostic holds hide
   current availability. Retained snapshots remain labelled historical drafts.

## Parallel ownership

- Notebook contract: pure typed immutable snapshot model, unit/input validation,
  question projection, tamper rejection, tests and contract documentation.
- Presentation: existing browser and terminal views; select question and display
  draft coverage, units, requirement, observations and non-acceptance messages;
  no automatic API calls or new independent web application.
- Verification: public-action smoke harness with explicit no-device assertions,
  exports and focused integration/failure tests, clearly separating modeled
  service faults from actual original-store file-only checks.
- Main integration: prerequisite accessor, closed action catalog, Arrival ticket
  context/staging/publication/export joins, launch/package and final review.

## Acceptance tests

- Sixteen original questions only; USB identity INT-018 is not a passive form.
- Nominal 610/457/38/86.8 values never populate observations automatically.
- Missing, invalid, nonfinite, signed-negative and authority-like input rejected;
  zero allowed only for flatness. UNKNOWN is not complete measured coverage.
- Requirements/source/origin/session/hash drift and stale ticket/context rejected.
- Revisions explicitly supersede drafts, never accept a stage or clear hazards.
- Stop, completion-log failure and diagnostic redaction cannot publish a draft.
- Current full notebook remains independently exportable after eight later
  operations; immutable export manifest and attachment bytes verify.
- Physical camera and arm stay NOT_CONNECTED; all device/power/motion/contact
  counters remain zero. No native camera, CM/serial or physical helper executed.
- Existing restart, setup, action, export and UI regression tests remain green.

## Not part of this increment

Verified attachment ingestion, authenticated operator/reviewer identity,
canonical stage-three acceptance, epoch issuance, native camera activation,
arm startup, installed calibration and physical key/tap execution. A completed
draft helps prepare these later reviews; it is not evidence that they passed.

## Operator procedure

1. From the workspace root run `./start-rocell-wizard.ps1 -Mode physical`.
   This opens a local diagnostic UI, not a camera or arm connection.
2. In Camera, explicitly initialize and collect original camera requirements;
   when continuing existing setup, Discover and Open the original matching store
   instead. Do not create a replacement to bypass an original-store failure.
3. Choose **Start passive intake draft**, inspect the preview and confirm.
   Candidate dimensions remain requirements, never initial observation values.
4. Choose **Record or revise an intake draft entry**, select a question, and
   enter an OBSERVED value in its printed unit or an UNKNOWN reason. Explicitly
   enter the method, evidence description and operator label. These are plain
   single-line descriptions, not pasted reports, credentials or sensitive data.
   An operator label is not an authenticated reviewer identity.
5. Inspect the complete draft and its revision after confirmation. "Observed"
   counts operator-entered drafts; it does not indicate accepted measurements.
   INT-005 flatness remains unaccepted even when a value is supplied.
6. Export diagnostics before closing. The assigned folder is
   `C:/Users/Jack/Desktop/robot-arm-build/software/runs/wizard-exports`.
   Each immutable report directory contains `attachment-physical-intake-notebook.json`
   whenever a draft has been successfully published. This dedicated attachment
   reserves one of eight slots, leaving up to seven rotating full worker results;
   any omitted result is listed with its reason and available hash.
7. Export performs a pre-export source observation when a notebook exists. Source
   mismatch/read failure labels the draft historical but does not block export.
   This is not an atomic lock against a concurrent source writer. No notebook is
   imported, relabeled or accepted automatically on a later launch.

## Code map

- `application/physical_intake_notebook.py`: strict immutable draft codec,
  source-derived questions, original/current binding and revision hash.
- `application/physical_camera_setup_service.py`: pure accessor restricted to
  the currently published, original M1-read-back prerequisite artifact.
- `application/wizard_actions.py`: two closed semantic form actions.
- `application/arrival_wizard_service.py`: exact ticket context, staged draft
  replacement after logging, current/historical projection and reserved export.
- `ui/static/app.js`, `ui/terminal.py`: guided questions and non-acceptance display.
- `scripts/wizard_physical_intake_smoke.py`: actual file-only public action and
  dedicated export check, with an explicit UNKNOWN instead of synthetic measured
  hardware. Unit fault injection is distinct from this original-store check.

The [notebook contract](PHYSICAL_INTAKE_NOTEBOOK.md) gives limits and exact data
semantics. Tests and executed source/export identities are recorded below after
integration verification; this brief was written before implementation.

## Executed verification

### Integration baseline

Production source fingerprint:
`83912c3b3cf45e7290605745f1ddf9440ec0bd00d8688eed1f2b622aa5a600f2`.
On this source one selected non-slow invocation passed **2,109 tests**, with
4,714 deselected, in 230.53 seconds:

```powershell
.venv/Scripts/python.exe -m pytest software/tests/unit -m 'not slow' -k 'arrival or wizard or physical_camera or physical_intake' -q
```

This is not the entire repository suite. It covers the Arrival/action/export
and UI workflows plus original camera session/restart and intake behavior.
Independent modeled faults include Stop, intent/context mismatch, diagnostic
redaction, failed completion logging, source drift/read failure during direct
export, reopened-original binding, and maximum legal notebook preservation.
The UI tests drive the existing code through a fake DOM and terminal renderer;
they do not constitute an interactive browser or physical-device qualification.

The actual file-only public smoke completed **14 explicit actions**, without
retry or native/device calls: initialize, retain/read back requirements, start
blank notebook, record UNKNOWN, append nine later notes, export. Generic results
had rotated out, but the dedicated complete draft remained exact and verifiable.

- Launch: `wizard-2be345b1e6584f6b85204da5964b109c`.
- Cell: `wizard-physical-camera-771b340dbca62801`.
- Original M1 session: `physical-camera-d5e987a13959c6ed8a6b19c4905fb8e8`.
- Requirements SHA-256: `2e9f447076f5a79d0aa3323c7340f562f45637e3fd396675471cf83ee6b1c786`.
- Draft SHA-256: `b667e888928a206ae4ce0dfd453032d2cd19bc1adc1a0986f5f4c76e1e88d8c1`.
- Export: `software/runs/wizard-exports/wizard-20260908T121815319658Z-459748eec82047bbb3a22a67c534c683`.
- Manifest binding hash reported by `verify_export`: `ee30cad6ee324dcce640a93004e087c4f8e07117f01b3b051e2bca07f2353586`.
- Manifest file SHA-256: `75cc5e6edd82b08b58b34478a6694d6d9c2585420c9662c6abd577c0562447cb`.
- Dedicated attachment: 14,784 bytes, SHA-256 `81abdaadc6c8018b439fe12881c9b2017939092c67b55c9f93eaf10da2501be6`.

All eleven manifest-listed payload files (187,221 bytes) verified. Revision one
contains zero OBSERVED entries, one UNKNOWN and fifteen unrecorded questions.
The original requirement/stage snapshot is unchanged by draft recording: source
stage WAITING_OPERATOR, fourteen later stages PENDING; all public physical
progress entries remain PHYSICAL_PENDING. Camera and arm are NOT_CONNECTED.
Both renderers recognize the actual 144,432-byte report and its historical-held
variant without preparing or executing an action.

Review found one final presentation-only correction after the baseline: generic
human-readable formatting replaced underscores in operator narratives. The final
checkpoint preserves those strings literally as text. Baseline evidence above
is not silently relabeled as that later source; final checks are listed next.

### Final source and handoff

Final production fingerprint:
`457e5a81058a053de122659d3cef3517e64e89326a54ea927de9e1c187d4a977`.
After the literal-text display correction, one combined focused invocation passed
**234 tests in 25.66 seconds**: notebook, service, independent review, smoke
validator, intake UI, action catalog, original camera restart and setup service.
The separate intake/browser/terminal regression invocation passed 141 tests;
these sets overlap and are not a summed suite. The broader 2,109-test baseline
was not rerun after the display-only change. Five production Python modules pass
mypy and Black; final JavaScript passes Node syntax checking.

A new explicitly source-bound public file-only run passed the same fourteen
actions on final source. It preserves the successful baseline store/export;
this is a new build verification, not replay or repair of an old attempt.

- Launch: `wizard-5efc943ae42f45bea149e12f3b7dbb19`.
- Cell: `wizard-physical-camera-23dfe5d94e18823b`.
- Original M1 session: `physical-camera-f70a914ad458c5d35d8896c9b1a113ac`.
- Requirements SHA-256: `fad58e1a5d80043f8395bd9f9be048de7a8512371c1a6b56f3ca8cf57933b526`.
- Notebook SHA-256: `a5e8349325c17c67c703177228aaf53d389825bc8cebeb17dd2362f5ec37c9f6`.
- Export: `software/runs/wizard-exports/wizard-20260908T122532389056Z-a5aa22362c5f4070bbaedadd46418ac3`.
- Manifest binding hash: `36bdfe2499f46c76f17e54ff91d01c9d107db57344fd459d8e4effae58b53532`.
- Manifest file SHA-256: `d70d5b0a0a6d12e1c824681fe4bce1b208ba00265168ad6ae669c815964ab087`.
- Dedicated attachment: 14,784 bytes, SHA-256 `f3eb97fe42c78a1e9415a8dcd1f8d567b46c323ccf33b241a892719599c6429c`.

Independent verification found all eleven payload files exact (187,221 bytes).
Both final renderers recognize the actual final-source report as revision one,
one UNKNOWN and fifteen unrecorded questions without opening hardware. Canonical
stage states and original requirements remain unchanged; all effect counters
are zero. No synthetic measurement was written as a physical observation.

The final wheel is
`software/runs/wizard-package-check-457e5a81/rocell-0.1.0-py3-none-any.whl`,
1,827,668 bytes; SHA-256
`7fa29e8b5029e4a2e356edbe649cb20776ea5afc90c974dc5a67187614aa5b9c`.
All **252** packaged Python/HTML/CSS/JavaScript entries byte-match final source.
The physical launcher's read-only `-Check` reports that same fingerprint, both
devices NOT_CONNECTED, notebook NOT_STARTED, fifteen PHYSICAL_PENDING stages,
and the user-selected workspace export folder. It opens no server or device.

The [presentation contract](WIZARD_PHYSICAL_INTAKE_PRESENTATION.md) documents the
exact-text and current/historical display behavior. Physical connection,
calibration and typing/tapping remain unfinished and disabled; the next required
joins include bounded verified attachment ingestion, explicit original draft
restoration, independent receipt review and canonical predecessor acceptance.
