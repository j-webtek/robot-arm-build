# Tactevra overview storyboard changelog

## Servo-form and articulation correction

- Replaced the simplified two-link animation with the RoArm-shaped visible
  shoulder–elbow–wrist-pitch–tool-wrist chain.
- Mounted each servo housing and link group on the physically correct side of
  its driven pivot and parented the chain to prevent gaps during interpolation.
- Kept the gripper, printed cartridge, and stylus on one terminal tool frame;
  that frame remains vertical at keyboard and phone contacts.
- Added canonical articulation rules, build-time mount assertions, and five
  full-arm QA renders spanning keyboard alignment, rhythm typing, crossing,
  phone typing, and Send.

This file keeps revision history out of the artist-facing production board.

## v2.1 corrections from v2

| v2 implication | v2.1 correction |
|---|---|
| One approval covers all contacts | Static batch facts may be admitted once; a fresh one-contact permit is required and consumed for every physical contact. |
| Uppercase `READY` / `ON MY WAY` | Use lowercase `ready` and `on my way`; the local test pad supports lowercase letters only, up to eight characters. |
| Phone taps follow a pre-approved route | Verify the expected phone screen before each tap and re-observe after every state-changing action. |
| Model supplies movement behavior | Model supplies target, frame, confidence, and uncertainty; runtime-owned dynamics and retry fields are shown locked. |
| Next target looks executable | The dotted ghost is explicitly `preview · no authority` until its own permit arrives. |

## v2.1 cognitive-load pass

- Removed explanatory text from the cold open.
- Delayed public stage labels until the model interpretation begins.
- Kept the stage bar on `ACT` through repeated contacts; compact contact-loop
  ticks carry the local check/contact/verify rhythm.
- Reduced repeated contact graphics to a permit and verification tick after the
  first fully taught keyboard contact.
- Extended the phone-entry scene from five to eight seconds. The first two
  characters play naturally; the remaining seven are visibly marked `2×`.
- Reduced the evidence and end-card copy to one contract line and one tagline.
- Moved the presentation-only operator display fully off-board so localization
  tags remain visible; its request-console/test-pad transition stays explicit.
- Routed the RC03 cable toward the operator-display side and off-frame without
  asserting an unverified direct connection.
- Named the source scenes for the 30-second edit.
