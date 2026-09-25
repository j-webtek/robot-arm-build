# Stylus loading and measurement procedure

Status: **loading in progress; grip retention not verified**. The restricted
r93 gripper-loader app was installed and started on 2026-09-25, with app-slot
readback and protected-settings/filesystem checks passing. One 200-count open
step was verified (2049 to 1852 measured counts), then the operator reported
the stylus seated with hands clear. One separately requested 50-count close
step was verified (1847 to 1893 measured counts); the six other joint goals
were unchanged. No additional close step, arm movement, or tool-contact test
has been performed. The current grip is **not yet qualified** by a visual and
gentle retention check, and no stylus geometry has been measured. The loader
offers at most four manually requested 50-count close steps, bounded by the
pre-open count, with no timer-driven closure. Position counts are not a
measurement of grip force. Do not proceed to keyboard contact.

The immutable evidence is in the `software/runs/wizard-exports` open and close
attempts from 2026-09-25 at 15:15 and 15:19 UTC. Keep the same controller boot
for any further manually gated loading step; a boot change invalidates the
current sequence.

## Intent and controller prerequisite

Load the selected OASO disc-tip stylus by its **barrel**, then measure its
actual mounted geometry before repeating the ghost-keyboard study. Waveshare's
[RoArm-M3 SDK documentation](https://github.com/waveshareteam/waveshare_roarm_sdk/blob/main/doc/roarm_m3_zh.md)
describes `gripper_angle_ctrl(angle, speed, acc)` and gripper-angle readback.
The installed r93 app uses a dedicated, bounded gripper-only serial interface;
the SDK documentation is background, not a substitute for the verified app.

The software loading control should enforce a state machine:

`IDLE → VERIFIED_POSE → OPEN_VERIFIED → WAITING_FOR_STYLUS →
 HANDS_CLEAR_CONFIRMED → CLOSING_IN_STEPS → HOLD_VERIFIED → MEASURED`.

At any uncertain command delivery, stale feedback, other-joint motion,
unexpected closing, export failure, or changed arm boot, stop. Never restart a
partially completed close automatically. Export the current goal/position of
all joints, each gripper-only command and readback, time, operator gates, and
the measured-tool record to the workspace `software/runs/wizard-exports`.

## Physical preparation

1. Keep the arm base fixed and external servo power stable. Place the arm in a
   reviewed loading pose with room for the gripper to open, **not** above the
   keyboard or phone. Verify its current pose and that no other joint is moving.
   Position a soft catch below the stylus, outside the jaw's travel.
2. Set a nonconductive V-cradle or temporary stop that holds the stylus in the
   open jaws after the operator withdraws their hand. Do not rely on a timed
   command to close while the stylus is held between fingers.
3. Remove the cap. Confirm the disc and its stem are intact and free. Mark the
   intended barrel grip zone and a repeatable insertion depth. Do not grip the
   disc, stem, clip, cap, or a tapered section that can slide out.
4. Keep the keyboard, ruler, loose printed parts, cable loops and other objects
   outside the gripper/loading swept path. Use the ruler only after motion stops.

## One loading attempt

1. Read the live seven-joint baseline and current gripper goal/position. Check
   the exact controller release and that a gripper-only route is available.
   Freeze all other joint targets. Record a one-use attempt ID.
2. With nobody in the jaws, open the clamp in a bounded slow step. Verify the
   gripper's **fresh** position changed in the expected direction while the six
   non-gripper joints stayed within their no-motion band. If the opening is
   insufficient, explicitly review the next bounded step; do not jump to a
   guessed end stop.
3. Announce `OPEN_VERIFIED` and allow **at least 10 seconds** for placement.
   The timer is a placement window only; it never triggers closing. The
   operator seats the stylus barrel against the stop/cradle, withdraws both
   hands, and says **"stylus seated, hands clear"**. If the stylus cannot stay
   seated without a hand, stop and improve the cradle.
4. Recheck the live controller state. Close only the gripper in small, slow
   steps toward the barrel. Stop at first reliable contact/retention rather
   than command a hard mechanical end stop. Verify fresh gripper feedback and
   unchanged other joints after each step. Servo position is **not** a calibrated
   grip-force measurement; do not label a count offset as safe force.
5. With motion stopped, have the operator check for visible crushing, disc
   deformation, sliding, cable snagging, or barrel tilt. If any occurs, stop
   and reopen by a separately verified command. Do not continue to typing.
6. Remove the temporary cradle only after the stylus is retained. Perform a
   gentle manual slip check with the arm stationary; do not yank the stylus or
   use the arm's motion as a retention test. If retention is uncertain, keep
   the catch and treat the load as failed.

## Measure the mounted tool

With the arm stationary, take front and side ruler photos and record millimeters:

- gripper contact/jaw reference plane to the stylus disc's resting contact
  center (axial protrusion);
- left/right and front/back offset of that center from the hand/tool axis;
- barrel diameter at the grip, insertion depth, jaw opening after retention,
  and stylus orientation relative to the gripper;
- disc diameter, free articulation/deflection, and clearance between the disc,
  jaw, cable and keyboard at the intended approach orientation.

Record the exact reference planes and whether each measurement is direct or
photo-estimated. Overall pen length alone is insufficient. Replace the
simulation's hypothetical 100 mm offset only with a versioned measured tool
transform. Re-run noncontact route and collision screening with the loaded
stylus before any keyboard or phone contact test.

## Remaining work

1. Obtain the operator's visual assessment after the first close step. Stop if
   there is slipping, tilt, crushing, disc deformation, or cable snagging.
   Decide whether one further separately approved close step is needed. Do not
   infer secure retention from servo counts.
2. After verified retention, measure and export the mounted-tool geometry.
   Add read-only identity/baseline and explicit open/close-step actions to the
   wizard for future loading. Closing must never be scheduled solely by time.
3. Simulate normal load plus failed open, unexpected other-joint change,
   delayed/stale feedback, lost close acknowledgement, slip/reopen and export
   failure. Confirm no automatic retry or subsequent motion on these paths.
4. Complete this one attended stylus load. Preserve the command/readback and physical measurements in a new
   mounted-tool profile, not the nominal keyboard or frozen source profile.
