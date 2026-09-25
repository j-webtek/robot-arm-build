# Android phone tapping runbook

> **Active Freeze 011 camera architecture:** Phase 1 phone registration uses
> the purchased Arducam B0477/IMX283 USB 3.0 camera and delivered nominal
> 16 mm C-mount lens on a rigid static overhead eye-to-hand support. Received
> identity, final support/height, mode/settings, and calibration remain open.
> Eye-on-arm vision is optional Phase 2 research, never an automatic fallback,
> and this runbook grants zero physical authority.

## Current operating status

This runbook currently authorizes hardware-free planning and simulation only.
It does not authorize powering or moving the RoArm-M3-Pro, opening a serial
port, contacting the phone, or injecting Android input.

Active Freeze 011 names a bare Samsung Galaxy A16 5G candidate, variant
`SM-A166B`. The retained Freeze-005-derived nominal phone target map
approximates a portrait, lowercase Gboard-like layout with the USB connector at
the device front. It is synthetic, not a screenshot-derived calibration. The
received phone, display mode, Android and Gboard versions/settings, screen
geometry, target polygons, touch tool, and UI observer remain unqualified.

## Supported development input and state contract

The current phone profile supports lowercase `a` through `z`, space, period,
and Enter/newline. It does not support uppercase, digits, symbols other than
period, emoji, modifiers, language switching, clipboard actions, suggestions,
or any keyboard layout transition.

Every compiled plan begins with a `VerifyPhoneState("KEYBOARD_LOWER")`
requirement. Every tap also requires `KEYBOARD_LOWER`; Enter adds a following
state-verification requirement. These actions make the contract explicit, but
the current runtime has no Android UI observer. A `verify_phone_state` action or
`VERIFY` path phase is therefore a placeholder, not proof of the visible UI.

The intended physical state machine is:

```text
APP_READY -> TEXT_FIELD_FOCUSED -> KEYBOARD_LOWER -> TEXT_UPDATED
     |              |                   |                |
     +--------------+-------------------+----------------+
                            |
          dialog / rotation / lock / layout drift /
          keyboard hidden / ambiguous tap outcome
                            |
                            v
                  STOP_AND_RELOCALIZE
```

No physical tap may depend on an unobserved state transition.

## Hardware-free operator workflow

Install the package once from `software/`:

```powershell
python -m pip install -e ".[test]"
```

Then run these commands from the workspace root. If running elsewhere, place
`--workspace C:\path\to\robot-arm-build` before the subcommand.

### 1. Verify the controlled snapshot

```powershell
rocell status --json
rocell doctor --mode sim --json
```

Expected Freeze-011 authority remains `UNRELEASED`, with
`safe_to_power_robot: false` and `contact_enabled: false`. A manifest or
source-hash mismatch is a stop condition.

### 2. Validate the nominal placemat bundle

```powershell
rocell workcell --json
rocell rehearse-b0477-stack --require-pass --json
```

`workcell` cross-checks the RC03 scene, tag map, nominal phone envelope,
semantic target binding, retained camera-architecture hold, arm screening
placement, and physical holds. The additive B0477 rehearsal separately checks
the purchased-camera profile, static-support contract, fake UVC/mode/control
inventory, synthetic intrinsics, and pixel path. Neither command inspects a
real camera/screen or proves that Gboard is visible.

### 3. Compile and trace a small test

Use non-sensitive text: the command line may remain in shell history even
though RoCell output stores only the requested-text hash.

```powershell
rocell plan --device phone --text "test." --json
rocell dry-run --device phone --text "test." --json
```

Confirm that the action plan begins with the required `KEYBOARD_LOWER` state and
contains only named targets. `dry-run` traces semantic phases only; neither
command resolves physical screen coordinates or observes Android.

### 4. Run the nominal geometric simulation

```powershell
rocell simulate --device phone --text "test." --json
```

Review at least these fields:

| Field | Required interpretation |
| --- | --- |
| `simulation_only` | Must be `true` |
| `execution_authorized` | Must be `false` |
| `hardware_commands_generated` | Must be `0` |
| `required_simulation_checks_pass` | Nominal alignment, coarse tool-tip geometry, and fixed synthetic tag view passed |
| `all_sampled_ik_converged` | Diagnostic nominal reach screen only |
| `vision.required_scope` | Fixed synthetic overview fixture health only |
| `vision.eye_on_arm_coverage.status` | Historical schema field; must remain not run and must not be treated as the selected Phase-1 route |
| `verification.phone_ui_state_observation_performed` | Must be `false` today |
| `verification.tap_outcome_observation_performed` | Must be `false` today |
| `physical_readiness` | Must remain unchanged and unreleased |

The fixed synthetic view checks only whether the six board tags project into a
virtual overview camera. It does not see the Galaxy A16 screen, Gboard, dialogs,
the text field, or an arm-mounted trajectory.

### 5. Screen the full nominal phone map

```powershell
rocell sweep-targets --device phone --phase contact --json
rocell calibration-status --device phone --json
```

The sweep independently screens nominal touch points and does not prove
branch-continuous, collision-free motion. Calibration status is expected to be
blocked until measured, qualified artifacts exist. Use `--require-all` or
`--require-ready` only when a nonzero exit on gaps is useful to automation.

At this checkpoint, all 29 synthetic phone contact targets solve in the
nominal -100 mm tool case. This is encouraging only for coarse reach. The
targets are unmeasured and smaller than a defensible open-loop error budget;
the result does not qualify the screen map, static-camera correction, stylus
contact, or UI-state/outcome verification.

The frozen nominal Cartesian park still rejects the contact tools. The bounded
park optimizer now provides a simulation-only overlay at
`B = (290, 10, 70) mm`, independently accepted for both selected 100 mm tools
with `0.2704734350` worst normalized arm margin and 10 mm modeled planar point
clearance.

```powershell
rocell optimize-park --require-both-routes --json
rocell simulate-trajectory --device phone --text "a" --use-optimized-park --json
```

The current phone `"a"` trajectory still fails closed at `APPROACH`: its
normalized arm-joint margin is `0.000657824`, below the `0.01` gate. Both fully
screened reach-study finalists also reject phone `key_a` contact. Thus the old
park failure is no longer masking the next gap, but the current nominal
base/tool/layout remains infeasible for phone typing. The 29/29 result above is
from a different nominal independent-contact screen and cannot override this
placement-specific full-route evidence. Trajectory schema v2 also fail-closes
on numerical rank loss in the solver's weighted five-constraint task while
keeping normalized conditioning report-only. Full collision, physical
six-dimensional singularity/manipulability, measured screen/tool transforms,
touch activation, and UI outcome verification also remain open.

## ADB boundary

ADB may later be used only as a read-only observer for screenshots, display
metadata, or UI hierarchy/state, subject to an explicit privacy policy and a
qualified observation pipeline. Do not use `adb shell input`, `input tap`,
`input text`, `input keyevent`, or any equivalent input-injection API. The
acceptance event must be a physical stylus tap made by the robot, and the
observer must remain independent of the commanded event.

ADB is not currently integrated into the CLI.

## Stop and review rules

Stop, retract in a future released system, and preserve evidence when any of
these occurs:

- snapshot, bundle, or source hashes fail verification;
- `workcell` or a required simulation check fails;
- a requested character is outside the lowercase phone profile;
- any nominal target or diagnostic IK point is rejected for the intended route;
- the phone rotates, locks, sleeps, moves, shows a dialog, changes keyboard
  layout/language, hides Gboard, loses text-field focus, or enables a floating or
  one-handed keyboard;
- glare, blur, occlusion, stale frames, or synchronization makes UI state
  uncertain;
- the observed text result is missing, duplicated, or ambiguous; or
- any output claims hardware access, command generation, or physical release.

Never blindly retry a tap. If the first event may have landed, retrying can
duplicate a character, submit a form, or activate a different control.

## Commissioning work required before a physical phone trial

Complete and accept the following work in dependency order:

1. Qualify the received arm/controller/firmware identities, exclusive serial
   port, installed joint signs/zeros/limits, and reference procedure.
2. Record and qualify the exact received B0477 USB identity, delivered
   IMX283/16 mm lens/metal-case configuration, driver, image orientation, and
   one locked resolution/pixel-format/crop and control set. Prove persistence
   after close/reopen and reboot; published `5472 x 3648 @ 9 fps YUY2` is an
   unverified receipt-test target, not a commissioned fact.
3. Positively retain the camera on the final rigid support and qualify the
   installed height/aim, fasteners, fixed cable/strain relief, controlled
   lighting, stiffness/settling, bump/remove-reinstall/thermal behavior, and
   support-reference witness. Add the complete support/camera/cable/light
   geometry to collision acceptance.
4. Calibrate B0477 intrinsics/distortion at the exact lens, focus, aperture,
   mode, crop/orientation, and settings. Measure the installed six-tag map and
   solve the constant `Wv_T_C_overhead_optical` with independent held-out
   residuals.
5. At startup and before each descent, acquire a uniquely fresh
   `C_overhead_optical_T_B`; use T0–T3 to fit board pose and keep K0/P0 as
   independent checks. Verify camera settings/freshness, support witness, and
   the expected phone's presence, seating, orientation, pose, active UI, and
   target-map residuals. Any mismatch blocks descent.
6. Correlate the firmware `R_ctrl` frame independently to `Wv` and the installed
   URDF over the usable configuration range; never infer controller signs,
   zeros, or limits from the camera-board transform.
7. Lock the exact Galaxy A16 variant, bare/case/protector state, portrait
   orientation, holder seating, USB cable routing, screen resolution, display
   scaling, rotation policy, brightness, and camera exposure interaction.
8. Lock Android, Gboard, language, theme, keyboard height, autocorrect,
   suggestions, haptics, long-press behavior, one-handed/floating modes, and a
   dedicated acceptance app/text field. Any UI-affecting update requires
   requalification.
9. Measure the phone pose, active-screen homography, insets, screen plane,
   per-state target polygons, and eroded safe regions with held-out residuals.
10. Install and qualify a conductive, non-scratching phone tool; measure its
    free-state TCP, compliance, touch activation, hover margin, maximum travel/
    load, drag risk, and recovery behavior. Validate TCP, approach axis, Z, and
    travel at the keyed puck and across representative phone regions.
11. Accept full swept-link, self, tool, static-support, camera, cable, lighting,
    clamp, phone, station, and fixture collision checking against the real
    system.
12. Commission E-stop, gravity containment, anti-shift, contact guard,
   stale-frame detection, power-loss behavior, and a single-use motion permit.
13. Implement and qualify a visual and/or read-only-ADB observer for app state,
    focus, `KEYBOARD_LOWER`, dialogs/rotation, touch outcome, and resulting text.
14. Complete independent held-out board-registration, device-map, TCP/puck,
    collision, one-tap, and end-to-end phone acceptance trials.
15. Record immutable calibration and run evidence tied to the manifest, active
    build, hardware/software identities, tool, screen/UI profile, and source
    hashes.

The retained Waveshare IMX335/bundled-holder path is historical Freeze-009
provenance or a separately controlled optional Phase-2 experiment. It requires
its own carrier transform, hand-eye calibration, exposure/joint timing,
payload, moving-cable, collision, and route-visibility evidence and cannot
satisfy or bypass any item above.

Until all dependencies are valid, `calibration-status --device phone` must
remain blocked.

## Future physical trial skeleton — not executable today

This is an architectural handoff, not a current operator instruction:

```text
controlled cell empty and E-stop proven
    -> board/arm/phone/tool/camera identities match
    -> phone seated, unlocked, acceptance app open, field focused
    -> observer confirms APP_READY + TEXT_FIELD_FOCUSED + KEYBOARD_LOWER
    -> fresh calibration, localization, collision, and interlock preflight
    -> one-tap permit and bounded physical tap
    -> independent observer confirms target and resulting text
    -> retract to verified safe state
    -> accept, or stop without automatic retry
```

Begin with one low-consequence lowercase character in a dedicated offline test
field. Do not test near submit, purchase, call, delete, navigation, or other
consequential controls.

## Evidence and privacy

For each future commissioned run, retain manifest/snapshot and plan hashes,
calibration hashes, arm/controller/firmware and phone identities, Android/Gboard
versions and controlled settings, tool identity, camera mode and synchronized
frame metadata, preflight/interlock result, expected state/target, observed
before-and-after state, touch outcome, faults, operator action, and recovery.

Screenshots and UI dumps may contain messages, accounts, notifications, or other
personal data. Use an offline acceptance app, disable notifications, minimize
capture, redact before sharing, apply retention limits, and store a hash or
derived pass/fail record when the raw image is unnecessary.
