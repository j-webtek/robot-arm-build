# Tactevra overview storyboard changelog

## Scene-7 visibility and current tool truth

- Reframed the closing scene-7 focus pull so the lowered operator display is
  visibly inside frame 960 instead of merely becoming the focus distance.
- Replaced the hand-set overhead-visibility flag with a camera-frustum
  calculation using the authored lens, camera position, display dimensions,
  and a required exclusion margin.
- Removed the uninstalled printed cartridge, cap, collar, and retaining screws;
  the bare nominal stylus barrel is now held directly by both RoArm jaw pads.

## Keyboard cord removal

- Removed the presentation keyboard cord from all generated Blender scenes.
- Updated the storyboard and advertising handoff to avoid implying any
  unverified wired, wireless, or direct operator-display connection.

## Base and articulation verification correction

- Replaced the solid presentation pedestal with an open controller PCB,
  standoffs, fixed lower chassis, bearing, and separate rotating yaw deck.
- Added base yaw and shoulder pitch to the declared five-stage visible joint
  chain and mounted each servo on the mechanically carrying link.
- Reworked contact descent to use complete-chain IK instead of moving the
  toolhead independently of the wrist.
- Added sampled full-timeline checks for fixed base position, link-length and
  pivot continuity, vertical yaw/tool axes, and bounded joint/yaw steps.
- Added close full-arm and joint-interface QA render modes for review without
  adding presentation claims or editorial cameras.

## Servo-form and articulation correction

- Replaced the simplified two-link animation with the RoArm-shaped visible
  shoulder–elbow–wrist-pitch–tool-wrist chain.
- Mounted each servo housing and link group on the physically correct side of
  its driven pivot and parented the chain to prevent gaps during interpolation.
- Kept the gripper and bare stylus on one terminal tool frame;
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
- Previously routed the RC03 cord off-frame without asserting a direct
  connection; the later keyboard-cord-removal revision supersedes this choice.
- Named the source scenes for the 30-second edit.
