# Camera and arm metadata review in the workbench

The Camera and Arm pages now show separate metadata candidate cards. The
terminal shows both sections in its status view. These are cached inventory
snapshots, not live device status or physical commissioning evidence.

## Operator flow

1. Run an eligible inventory action explicitly. Rehearsal offers the closed
   nominal, missing-identity, duplicate-identity and partial-inventory fixtures.
   Physical metadata inventory retains the service's existing explicit
   prerequisites; this page does not provide power or cable-handling directions.
2. Inspect the correct device card, including snapshot provenance, report and
   operation references, metadata name, USB IDs, unit serial and identity
   blockers. Expand a browser candidate to inspect its full bounded metadata.
   Candidate labels show the number of identity blockers before expansion.
3. Choose the exact opaque candidate in the separate review action, enter a
   reviewer ID and affirm the metadata-only acknowledgment. No candidate or
   consent checkbox is preselected. Previewing is separate from execution.
4. Execute the exact prepared ticket if its effects are intended. The card then
   shows an acknowledgment for investigation, not a connection or device binding.
   Missing or ambiguous identity remains visible after acknowledgment.
5. Inspect the inventory operation result and diagnostics for collection
   failures. A new inventory or invalidation clears prior choices/reviews.
   Export logs through the existing assigned-folder action when needed. Full
   explicit review results contain the original metadata report, including unit
   identifiers; consider that information before sharing an export.

The cards always distinguish **NOT_CONNECTED**, **NOT_QUALIFIED** and received
model **UNKNOWN** from a recorded metadata acknowledgment. A name, VID/PID or
unit serial does not prove the purchased camera/arm model, installed firmware,
current endpoint availability, native backend readiness, or permission to
capture, use serial, change power, move or contact the placemat.

## Developer contract

The frontend consumes `device_selection` using the exact versioned contract in
[WIZARD_DEVICE_SELECTION_API.md](WIZARD_DEVICE_SELECTION_API.md). It never
enumerates, selects, previews, opens or connects a device during rendering.
The existing action schema supplies separate review controls; the card itself
creates no action, filesystem field, command or endpoint input.

Both frontends bound each device class to 128 candidates, each metadata text
field to 2,048 UTF-8 bytes and each blocker list to 32 unique codes. They reject
unknown fields, authority-bearing flags, malformed metadata and inconsistent
review references rather than silently truncating a list or displaying a stale
acknowledgment. The terminal's generic select bound is 128 to match the same
inventory contract; 129 choices remain rejected.

A review must match its current candidate token/hash, inventory report hash and
inventory operation. The four follow-up requirements remain explicit. Review
status must agree with the presence of current reviews. Invalidated/no-inventory
snapshots must have cleared candidates, reviews and inventory references.
Absolute nanosecond timestamps are labeled retained/not interpreted, never
displayed as an exact JavaScript number or accepted as a freshness check.

`test_arrival_wizard_device_selection_ui.py` covers pure DOM/terminal rendering,
missing/weak/duplicate identity, malformed and stale views, size limits, explicit
preview/execute consent and the real closed inventory producer. It also routes
actual Arrival service snapshots to both frontends after public inventory and
review actions. Physical-mode tests inject OS-shaped reports and forbid native
providers/camera/serial access; they are not physical connection evidence.
