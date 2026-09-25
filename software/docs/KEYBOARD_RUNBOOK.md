# Keyboard typing runbook

> **Active Freeze 011 camera architecture:** Phase 1 keyboard registration
> uses the purchased Arducam B0477/IMX283 USB 3.0 camera and delivered nominal
> 16 mm C-mount lens on a rigid static overhead eye-to-hand support. Received
> identity, final support/height, mode/settings, and calibration remain open.
> Eye-on-arm vision is optional Phase 2 research, never an automatic fallback,
> and this runbook grants zero physical authority.

## Current operating status

This runbook currently authorizes hardware-free planning and simulation only.
It does not authorize powering or moving the RoArm-M3-Pro, opening a serial
port, lowering a tool, or pressing the keyboard.

Active Freeze 011 names the Perixx PERIBOARD-409 U, USB Type-A, English (US),
black as the selected-unqualified keyboard candidate. Its exact identity,
physical layout, OS layout, pose, keys, press travel, and safe regions are not
yet measured. The retained Freeze-005-derived nominal ANSI target map is a
synthetic simulation seed, not a product drawing or calibration.

## Supported development input

The current keyboard semantic profile supports:

- lowercase `a` through `z`;
- digits `0` through `9`;
- space, Enter/newline, and Tab; and
- `.`, `,`, `-`, `=`, `/`, `;`, and `'`.

Uppercase letters, shifted symbols, modifiers, shortcuts, chords, function
keys, navigation keys, and locale-specific characters fail during planning.
Failing on an unsupported character is expected; do not silently substitute a
different key sequence.

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
`safe_to_power_robot: false` and `contact_enabled: false`. A source-hash or
manifest mismatch is a stop condition, not a reason to bypass verification.

### 2. Validate the nominal placemat bundle

```powershell
rocell workcell --json
rocell rehearse-b0477-stack --require-pass --json
```

`workcell` checks that the profile, RC03 geometry, tag map, nominal keyboard
envelope, semantic target binding, retained camera-architecture hold, and
physical holds agree. The additive B0477 rehearsal separately checks the
purchased-camera profile, static-support contract, fake UVC/mode/control
inventory, synthetic intrinsics, and pixel path. A pass means nominal software
sources align; it does not mean the camera, support, board, or keyboard has been
received, measured, installed, or calibrated.

### 3. Compile and trace a small test

Use non-sensitive text: the command line may be retained in shell history even
though RoCell output stores only the requested-text hash.

```powershell
rocell plan --device keyboard --text "test 123" --json
rocell dry-run --device keyboard --text "test 123" --json
```

`plan` emits named key actions. `dry-run` traces semantic phases only. Neither
command resolves geometry, imports hardware libraries, or observes a desktop
result.

### 4. Run the nominal geometric simulation

```powershell
rocell simulate --device keyboard --text "test 123" --json
```

Review at least these report fields:

| Field | Required interpretation |
| --- | --- |
| `simulation_only` | Must be `true` |
| `execution_authorized` | Must be `false` |
| `hardware_commands_generated` | Must be `0` |
| `required_simulation_checks_pass` | Alignment, coarse geometry, and fixed synthetic tag view passed |
| `all_sampled_ik_converged` | Diagnostic reach screen only; false reports provisional gaps |
| `vision.eye_on_arm_coverage.status` | Historical schema field; must remain not run and must not be treated as the selected Phase-1 route |
| `verification.status` | Outcome observers are not implemented; a planned `VERIFY` phase is not an observed keypress |
| `physical_readiness` | Must remain unchanged and unreleased |

The current geometry checks only the tool-tip path against coarse nominal AABB
proxies. They do not clear links, the camera/holder, wiring, clamps, fixtures,
or self-collision.

### 5. Screen the full nominal keyboard map

```powershell
rocell sweep-targets --device keyboard --phase contact --json
rocell calibration-status --device keyboard --json
```

The sweep solves each nominal target independently and may expose targets that
need workcell, tool, or IK changes. It does not prove a continuous collision-free
typing path. Calibration status is expected to be blocked until commissioned
artifacts exist. Use `--require-all` or `--require-ready` only when a nonzero
exit on gaps is useful to automation.

At this checkpoint, the nominal -100 mm tool case accepts only 6/46 contact
targets: `A`, `C`, `SPACE`, `TAB`, `X`, and `Z`. Treat that result as a hard
design/simulation gap for keyboard typing. Do not optimize offsets around those
six successes; sweep revised base placement, tool length/orientation, and the
measured keyboard layout before choosing hardware geometry.

The frozen nominal Cartesian park still converges only for the no-extension
`hand_tcp_only` case at zero effective joint margin. The bounded park optimizer
now offers a simulation-only replacement at `B = (290, 10, 70) mm`: both
selected 100 mm tool poses pass independently with `0.2704734350` worst
normalized arm margin and 10 mm modeled planar point clearance.

```powershell
rocell optimize-park --require-both-routes --json
rocell simulate-trajectory --device keyboard --text "a" --use-optimized-park --require-pass --json
```

The current keyboard `"a"` run accepts 24/24 densified waypoints and reports
`DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_PASS_WITH_UNSUPPORTED_CHECKS`.
Trajectory schema v2 also verifies numerical rank of the solver's weighted
five-constraint task at each selected state; its conditioning values are
report-only.
That is useful end-to-end simulation coverage, not a release: the candidate is
pointwise tool-tip/IK evidence only, the broader keyboard contact catalog is
still incomplete, and full links, camera/holder, tool body, cable, fixtures,
self-collision, physical six-dimensional singularity, measured transforms,
and a path from the installed arm state remain unproven.

## Stop and review rules

Stop the workflow and preserve the error/report when any of these occurs:

- the snapshot, bundle lock, or source hashes do not verify;
- `workcell` or a required simulation check fails;
- the requested text contains an unsupported character;
- IK returns a gap or a controller-intersection rejection that affects the
  intended route;
- any output claims hardware access, command generation, or physical release;
- keyboard identity, seating, layout, tool, board, or camera configuration
  differs from the versioned assumptions; or
- an eventual physical outcome is uncertain.

Never blindly retry a physical press: an unobserved first press may already have
produced a duplicate character.

## Commissioning work required before a physical keyboard trial

The following work must be completed and accepted in dependency order:

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
   the expected keyboard's presence, seating, orientation, pose, and target-map
   residuals. Any mismatch blocks descent.
6. Correlate the firmware `R_ctrl` frame independently to `Wv` and the installed
   URDF over the usable configuration range; never infer controller signs,
   zeros, or limits from the camera-board transform.
7. Lock the exact PERIBOARD-409 variant, US physical layout, controlling OS
   layout, feet/tilt, cable routing, station seating, and anti-shift interface.
8. Measure the keyboard pose, per-key polygons and eroded safe regions, top Z,
   surface normals, press travel, and held-out targeting residuals.
9. Install and qualify the keyboard contact tool; measure its free-state TCP,
   compliance, free/contact signatures, maximum travel/load, and no-damage
   recovery. Validate TCP, approach axis, Z, and travel at the keyed puck and
   across representative keyboard regions.
10. Accept full swept-link, self, tool, static-support, camera, cable, lighting,
   clamp, keyboard, and fixture collision checking against the real system.
11. Commission E-stop, gravity containment, board anti-shift, contact guard,
   stale-data detection, power-loss behavior, and a single-use motion permit.
12. Implement and qualify a controlled desktop acceptance application that
   observes the expected-versus-actual key result without relying on the robot
   command as evidence.
13. Complete independent held-out board-registration, device-map, TCP/puck,
    collision, one-key, and end-to-end keyboard acceptance trials.
14. Record immutable calibration and run artifacts tied to the manifest, active
    build, hardware identities, tool, keyboard/OS layout, and source hashes.

The retained Waveshare IMX335/bundled-holder path is historical Freeze-009
provenance or a separately controlled optional Phase-2 experiment. It requires
its own carrier transform, hand-eye calibration, exposure/joint timing,
payload, moving-cable, collision, and route-visibility evidence and cannot
satisfy or bypass any item above.

Until all dependencies are valid, `calibration-status --device keyboard` must
remain blocked.

## Future physical trial skeleton — not executable today

This sequence documents the intended operator shape only. It becomes a real
procedure after a separately reviewed executor, observers, limits, interlocks,
and release record exist.

```text
controlled cell empty and E-stop proven
    -> board/arm/keyboard/tool/camera identities match
    -> keyboard seated; acceptance app focused; OS layout verified
    -> fresh localization, calibration, collision, and interlock preflight
    -> one-key permit and bounded press
    -> independent desktop outcome observation
    -> retract to verified safe state
    -> accept result or stop without automatic retry
```

The first physical acceptance should use one low-consequence key in a dedicated
test field, not free-form text. Expansion to sequences must be evidence-driven,
one bounded capability at a time.

## Evidence to retain later

For each commissioned physical run, retain the manifest/snapshot and plan
hashes, calibration artifact hashes, arm/controller/firmware and keyboard
identity, OS/keyboard layout, tool identity, camera mode and frame timestamps,
preflight/interlock result, requested semantic action, measured feedback/load,
independently observed key result, faults, operator action, and recovery state.
Do not store sensitive typed content when a hash or redacted acceptance string
is sufficient.
