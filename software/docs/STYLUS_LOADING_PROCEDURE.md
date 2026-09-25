# Stylus loading and measurement procedure

Status: procedure prepared; **not executed**. No stylus is yet calibrated or
approved for keyboard contact. The r91 five-leg A-cycle image was replaced by
a restricted r92 gripper-loader app on 2026-09-25. Its app-slot readback and
settings-preservation checks passed, but **no gripper movement has been sent**.
r92 can make one bounded open step and read feedback; it has no close path.
Do not begin loading a stylus with r92 alone. A manually gated, stepwise close
path must be built, verified, and installed before the first jaw opening so a
pen need not remain unsupported through another controller restart.

## Intent and controller prerequisite

Load the selected OASO disc-tip stylus by its **barrel**, then measure its
actual mounted geometry before repeating the ghost-keyboard study. Waveshare's
[RoArm-M3 SDK documentation](https://github.com/waveshareteam/waveshare_roarm_sdk/blob/main/doc/roarm_m3_zh.md)
describes `gripper_angle_ctrl(angle, speed, acc)` and gripper-angle readback.
That documents a possible actuator interface, **not** an interface already
qualified on the installed r91 diagnostic image. Implement and verify a
gripper-only, bounded, feedback-producing path before using this procedure.

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

## Immediate implementation work

1. Add a dedicated gripper-only controller route or use a verified firmware
   interface that coexists with the installed diagnostic application. Do not
   assume r91 accepts the official SDK's generic command endpoint.
2. Add read-only identity/baseline and explicit open/close-step actions in the
   wizard. The `WAITING_FOR_STYLUS` state may count down 10 seconds, but must
   remain paused until an affirmative hand-clear action. Closing cannot be
   scheduled solely by elapsed time.
3. Simulate normal load plus failed open, unexpected other-joint change,
   delayed/stale feedback, lost close acknowledgement, slip/reopen and export
   failure. Confirm no automatic retry or subsequent motion on these paths.
4. Qualify the empty gripper first, then perform exactly one attended stylus
   load. Preserve the command/readback and physical measurements in a new
   mounted-tool profile, not the nominal keyboard or frozen source profile.
