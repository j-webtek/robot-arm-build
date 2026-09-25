# Native-camera endpoint metadata in the workbench

The Camera page includes a **Native camera endpoint enrollment** card. The
terminal shows the same Camera-specific section; the Arm page does not show a
native-camera card. This is cached endpoint metadata, not an active camera feed.

## Explicit operator sequence

1. Complete the existing generic CAMERA metadata inventory and review. A native
   enrollment is tied to that exact current candidate, inventory report and
   inventory operation, plus session/source provenance.
2. Preview and execute `native_camera_inventory` with metadata-only consent when
   the service offers it. Rehearsal uses closed parser fixtures, with nominal,
   missing-mapping, wrong-device and duplicate-name scenarios. The default
   physical setup has no native provider registered until the separate
   [helper inspection/review workflow](WIZARD_CAMERA_HELPER_PRESENTATION.md)
   commits. The interface does not search for, install or execute an unregistered helper.
3. Inspect the native candidates and their endpoint hashes. Friendly names are
   metadata only; identical names remain distinct opaque choices. Select a
   candidate explicitly for `native_camera_identity`, acknowledge metadata-only
   effects, preview, then execute the exact ticket if intended.
4. Inspect the retained endpoint-mapping, generic-device-match and container-match
   results separately, including their blockers. A false result can reflect
   missing or inconsistent evidence; it is not itself a received-model verdict.
5. Use `native_camera_review` with the exact candidate, reviewer ID and explicit
   metadata-only consent. A held review remains held; a successful review is
   still endpoint metadata only. No candidate or consent is preselected.

Each card remains **NOT_CONNECTED**, **NOT_QUALIFIED**, with no persistent-unit
binding or physical authority. Even exact native endpoint mapping does not prove
the received camera model, USB3 topology/link speed, camera readiness, installed
calibration or permission to capture. These actions do not release power, robot
motion or contact. Full diagnostic evidence remains in operation results and
existing exports; the card does not display a raw symbolic endpoint.

## Cached view and reset behavior

Rendering and refreshing perform no inventory, identity lookup, review, helper
call or camera activation. The existing generic action form handles each
explicit preview/execute sequence. No filesystem path, endpoint string or helper
command can be entered through this card.

The strict `rocell.wizard_native_camera_enrollment.v1` display contract permits
128 native candidates, 1,024 UTF-8 bytes per friendly name and 32 unique blocker
codes. Unknown fields, over-limit lists, malformed values or stale generic-review
references produce a visible unverified message, without truncating a candidate
list or inventing identity. Both interfaces compare current generic candidate,
report, operation, source, session and mode references before displaying an
active enrollment as current.

A full invalidation clears inventory references, candidates, identity and review.
An identity reset can retain the inventory/choices but clears identity/review;
a review reset can retain identity but clears review. The latest reset or hold
is displayed, and nothing is replayed automatically. Baseline model, link-speed,
backend and physical-release holds remain visible even after a successful
metadata-only review.

`test_wizard_native_camera_enrollment_ui.py` exercises the browser DOM and
terminal with recording services and closed fixtures, including all enrollment
states, exact generic-review linkage, weak/missing mapping, duplicate-name
choices, bounded fields, absent helper registration and explicit consent. No
test in this presentation suite may enumerate or open physical hardware.
The suite also carries each of the four real incapable-provider scenarios
through the registry and public Arrival actions into both interfaces, and checks
the actual default physical-mode helper-registration hold. Native client launch,
OS inventory, serial connection and camera-open entry points are forbidden in
these tests; they provide software integration evidence, not hardware acceptance.
