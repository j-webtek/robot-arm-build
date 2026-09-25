# Passive intake notebook presentation

The existing Camera page and terminal wizard display the same cached
`physical_intake` draft. Starting, recording and revising use the existing
prepare/confirm/execute workflow. Rendering and selecting a question do not
save observations, query hardware, read attachments or call a provider.

## Operator workflow

1. Explicitly publish the original camera setup requirements, then start the
   notebook using `physical_intake_start`.
2. Choose one of the sixteen original `camera_receipt` questions in
   `physical_intake_record`. There is no default question. Its source unit,
   candidate requirement and notes appear next to the browser form, or just
   after question selection in the terminal.
3. Choose OBSERVED or UNKNOWN. UNKNOWN is the default status, never a measured
   value. Enter a value or reason, method, evidence description and operator
   explicitly. All four narrative fields are required, single-line and bounded.
   Descriptions such as "Not measured" or "Not supplied" must be entered by the
   operator; the interface does not invent them.
4. Inspect the preview and explicitly confirm the exact ticket. Cancellation
   leaves the draft unchanged. There is no autosave or observation storage in
   browser localStorage/sessionStorage.
5. Review coverage and export to the assigned diagnostics folder before closing.
   The complete current notebook has a dedicated export attachment. Restoring
   draft observations on another launch is not implemented; exported drafts
   are currently the handoff, not an automatic import source.

The table distinguishes UNRECORDED, UNKNOWN and operator-reported OBSERVED.
Observed coverage is not accepted measurement coverage. Numeric mm/g values
remain plain decimal text in the original unit; no conversion or acceptance
limit is inferred. Only INT-005 flatness permits zero, and its acceptance remains
deferred until the target accuracy budget closes. INT-018 USB identity is not a
passive-intake question.

Operator narrative values are displayed literally, preserving underscores and
punctuation. Browser markup remains text, never executable content. Terminal
structured records use lossless JSON escapes for non-ASCII characters; neither
interface rewrites a narrative as a humanized enum label.

## Current-state and authority boundary

CURRENT_DRAFT requires a CURRENT setup projection, the exact current source and
application launch, original session and origin launch, and prerequisite hash.
Each question and acceptance requirement must exactly match the retained
prerequisite rows. Changed bindings, coerced flags, unknown fields, incorrect
coverage, control characters and oversized whole notebooks are withheld.
NOT_STARTED and HISTORICAL_HELD contain no current notebook.

The UI never presents stage PASS, resolved hazards, issued epochs, permits,
verified evidence bytes or connected hardware from these drafts. Evidence notes
are descriptions only. Absolute record nanoseconds are retained but not shown
as exact browser values or freshness proof. An original requirement can be
historical context even while a new draft records the current launch's notes.

## Verification scope

`test_wizard_physical_intake_ui.py` uses the real fixed-file prerequisite and pure
notebook producers with explicitly modeled storage facts. It checks both strict
renderers, the local question-change handler, blank defaults, explicit preview,
source/publication holds, byte limits and malformed inputs without hardware.
Optional read-only cases render the actual September 8 public export, including
its revision-1 UNKNOWN entry and a display-only historical-held variant. They
do not reopen the original M1 store or repeat its actions. The separate public
smoke supplies the actual original-store and export verification.
