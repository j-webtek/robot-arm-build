# RC03 build alignment and Phase 0 system freeze

**Freeze ID:** `ROCELL-PHASE0-RC03-INT-R1-FREEZE-011`  
**Date:** 2026-09-06  
**Status:** `FROZEN_DIGITAL_ENGINEERING_HOLDS_CONTACT_BLOCKED`  
**Machine-readable authority:** [`software/config/system_manifest.json`](software/config/system_manifest.json)

## Current camera alignment hold and Job 03C1 rework

On 2026-09-05 the builder selected a rigid static overhead eye-to-hand camera
as the Phase 1 primary vision architecture. The controlled migration is defined
in [`STATIC_OVERHEAD_CAMERA_ARCHITECTURE_PLAN.md`](STATIC_OVERHEAD_CAMERA_ARCHITECTURE_PLAN.md)
and [`software/config/camera_architecture_plan.json`](software/config/camera_architecture_plan.json).
The additive, zero-authority detailed-screening baseline is in
[`hardware/static_overhead_camera/`](hardware/static_overhead_camera/README.md).

Freeze 010 originally synchronized the RC03 source hashes and recorded the
conflict between that selection and the still-historical arm-mounted camera
binding as an explicit `CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`. Active Freeze 011
carries that hold and those reconciled sources forward; neither revision
silently releases a camera route. Arm-mounted-primary and fixed-mast-fallback
statements retained below describe historical Freeze 009 provenance, not
current build instructions. Step 13, the final support geometry, collision
model, received hardware, optics, calibration, and physical evidence still
require a later controlled release.

Freeze 010 also originally recorded the operator-observed Job 00B results and
the controlled Job 03C1 rework, which active Freeze 011 retains. The passed
6.2 mm rod locator and 9.2 mm washer recess remain unchanged. The old nominal
N7.4 nut feature and narrow tie saddle are recorded `FAIL`; production geometry
now uses a true 7.2 mm captive M4 nut seat and a 5.6 x 2.2 mm passage for
nominal 4.8 mm-wide ties. Job 03C1 is the production-equivalent first article,
so no replacement coupon print is required.

Until then:

- static overhead is selected, with the purchased Arducam B0477/IMX283 and
  delivered nominal 16 mm lens, nominal
  1000 mm entrance-pupil height, and bench-anchored front portal now defined
  for simulation and CAD review; exact received identity, focus, dimensions,
  support release, collision/load proof, optics, and calibration remain
  `OPEN_BLOCKING`;
- the existing 700 mm paired mast and universal plate are unsuitable as the
  default static primary and remain unreleased historical candidates;
- the Waveshare IMX335-B and bundled upper-arm holder are no longer the Phase 1
  selection and remain optional-secondary research inputs;
- neither the old mast branch nor an arm-camera branch is released to print or
  install; and
- robot power, camera-guided descent, and contact remain disabled.

## 1. What “frozen” means

This freeze aligns the robot-typing roadmap to the current controlled RC03 build without turning nominal CAD values into false physical facts.

- **FROZEN-DIGITAL:** an RC03 design value or explicit system decision is fixed for this baseline.
- **SELECTED-UNQUALIFIED:** the mission route is selected, but its real article still needs the existing measurements, coupons, and acceptance gates.
- **NOMINAL-ONLY:** the value may be used for design, simulation, and conservative keepouts, but never as an executable contact coordinate.
- **OPEN-BLOCKING:** physical identity, evidence, approval, or a controlled hardware design is missing. The affected capability remains disabled.

`RELEASE_VALIDATION.json: PASS` means the digital RC03 package is internally consistent. It does **not** release printing, powered motion, or contact. The physical package remains `UNRELEASED`.

## 2. Frozen configuration aligned to RC03

| System item | Frozen selection | Evidence state |
| --- | --- | --- |
| Hardware release | `RC03-INT-R1` | Digital validation PASS; physical release UNRELEASED |
| Printer | QIDI Plus4; nominal 305 × 305 × 280 mm; provisional protected 295 × 295 × 275 mm | Candidate digitally screened; actual-machine envelope/profile gates open |
| Robot | Waveshare RoArm-M3 Pro with factory rear-edge clamp | Model frozen from RC03 BOM; serial/controller/firmware still open |
| Board | 610 × 457 × 18 mm; origin front-left of finished top; +X right, +Y rear, +Z up | Geometry frozen; physical dimensions/flatness still unmeasured |
| Keyboard | Perixx PERIBOARD-409 U, USB-A, English-US, black candidate; nominal 315 × 147 × 21 mm | Selected-unqualified; label, physical dimensions, key map, and key heights open |
| Phone | Samsung Galaxy A16 5G SM-A166B candidate, bare body, nominal 77.9 × 164.4 × 7.9 mm | Selected-unqualified; regional identity, actual body/screen/features/UI state open |
| Phone case | No case in the RC03 baseline | Any case/protector geometry requires measured overrides and regeneration |
| Phone cable | StarTech R2CCR-1M-USB-CABLE candidate | Selected-unqualified; host/power, connector projection, relaxed bend, direction, strain relief, and port load open |
| Camera included with RoArm package | None | Official package image includes the holder but no camera; the page's ESP32 is the arm controller |
| Selected Phase-1 camera purchase | Static overhead Arducam B0477/IMX283 USB3 camera with delivered nominal 16 mm lens and metal case | `PURCHASED_PENDING_RECEIPT_INSPECTION`; selected by the additive architecture plan, not yet promoted into the legacy canonical manifest fields or physically qualified |
| Legacy canonical camera binding under hold | Arm-mounted eye-on-arm Waveshare IMX335 5MP USB Camera (B), SKU 26719 | Retained in Freeze 011 only under `CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`; not the selected Phase-1 hardware; optional Phase-2 research requires a separate controlled qualification |
| Legacy bundled camera holder | Waveshare RoArm holder on moving upper-arm twin 1020 rails | Included package inventory and historical binding; not the selected Phase-1 static support; any Phase-2 use needs exact revision, rail position, fasteners, mass/CG, cable, carrier-frame, payload, and collision evidence |
| Optional external camera | Logitech C920e candidate on the RC03 independent 2020 mast route | Route unselected and held as a fallback design; it would require separate qualification/calibration and can never be an automatic substitute |
| Keyboard tool | RC03 shared compliant body + 6 mm rod/bushing + TPU keyboard tip | Route selected; measurements and tool gates open |
| Phone tool | RC03 shared compliant body + passive capacitive stylus/collar | Route selected; measurements and tool gates open |
| Tool spring | Lee Spring LP022J01S316 candidate | Selected-unqualified; received dimensions, preload/rate, travel, return, route force, and retention open |
| Board tags | tag36h11 IDs 0–5, 55 mm tiles, 40 mm detection edge | Geometry frozen; installed XY/yaw/Z and measured map open |
| Calibration datum | Existing keyed RC03 calibration puck at nominal (441,180), Z 10.5 mm | Existing interface frozen; installed height/TCP evidence open |
| Selected Phase-1 arm/board calibration | Static eye-to-hand `Wv_T_C_overhead_optical`, measured tag map, controller/board correlation, and existing puck/TCP validation | Additive architecture selected; every physical transform and held-out validation remains open |
| Legacy Phase-2 arm-camera calibration | Eye-on-arm robot-world/hand-eye plus existing puck validation | Optional research only; `E_T_Carm`, carrier, frame/joint sync, and transform evidence open under a separate future qualification |
| Motion transport | USB serial, 115200, newline JSON, typed mm/rad adapter | Frozen software boundary |
| Contact primitive | T=104 only after characterization; T=1041 prohibited for contact | `spd` is a controller coefficient, not physical mm/s or mm/s² |

The retained legacy route fields are `phone_stylus_route: true`, `keyboard_rod_route: true`, and `camera_mast_optional: false`. The false historical mast route leaves that old external fallback unselected; it does not override the additive plan's selected static B0477 primary or promote that selection into Freeze 011. The current print state is 20 selected jobs (5 `READY`, 15 `WAITING`) and 4 `NOT_SELECTED`. A `READY` print job is not a release of the robot, camera, motion, or contact system.

### 2.1 Standalone RoArm package and camera binding

The purchased product is the standalone RoArm-M3 page with the Pro option, not the RoArm AI kit. The official Pro package image lists the arm, 12 V/5 A supply, accessory pack, expansion mounting plate, camera holder, EoAT expansion plate, and base mounting plate. No camera is listed. The description says the camera illustration is reference-only and identifies the onboard `ESP32-WROOM-32` as the arm controller.

Waveshare does not name or explicitly recommend a camera model on the standalone arm page; it instructs the builder to use a corresponding-size camera or an adapter. The included holder drawing has 21.0 × 13.5 mm camera-hole centers. Freeze 004 selected the Waveshare IMX335 5MP USB Camera (B), SKU 26719, as an unqualified geometrically matched candidate because its official drawing has the same pattern; Freeze 005 retained that selection, and active Freeze 011 carries the legacy binding forward under `CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`. It is historical Freeze-009-origin context, not the selected Phase-1 camera instruction. It is a USB/UVC camera, not an ESP camera. `usb_opencv` is the selected candidate backend for that legacy binding. `esp_http_mjpeg` is implemented only as an optional adapter for separately integrated hardware and is not selected. See [`software/config/camera_manifest.json`](software/config/camera_manifest.json) for the binding and evidence contract.

## 3. Source precedence and runtime import contract

The runtime shall consume RC03 read-only in this order:

1. active-build measurement and signoff evidence;
2. canonical `config/measurement_record.json`, `config/camera_architecture_decision.json`, and route decisions;
3. measured `fiducials/apriltag_map.json`;
4. `config/workcell_layout.json`, `config/v1_prehardware_configuration.json`, and generated geometry/fit/reach records;
5. pre-hardware readiness, digital release, documentation-sync, build-package, and checksum records.

The importer must create one immutable build snapshot. It must block hardware motion when the active build ID is null, the camera architecture is on hold, a required route is false, a required canonical gate or active-build signoff is missing/non-PASS, the tag map remains nominal, or any frozen hash disagrees.

The current active build is `2026-09-01_CELL-A`. Active Freeze 011 retains the regenerated Job 00B/03C1 package from Freeze 010 and removes a latent Job 03C2 self-dependency; that workflow-only correction has no geometry or physical-release effect. Job 00A remains `POSTPRINT_PASS`: its keyboard-corner coupon is `PASS` with 0.0 mm compensation, its tray-clearance coupon is `PASS` under an explicitly operator-authorized prototype functional-fit waiver, and its keyboard-station registration coupon is `PASS` at the operator-confirmed 6.2 mm round/slot selection. The M4 screw major diameter remains a 4.0 mm nominal designation assumption rather than caliper metrology; the actual station screw passed cleanly at 4.4 mm and no smaller candidate passed; the actual production washer fit all recess candidates, with the photographed/current 9.2 mm recess retained for assembly margin. The measurement record now has 15 `PASS`, 63 `NOT_TESTED`, 4 `NA`, and the two explicit Job 00B `FAIL` results that are reassigned to Job 03C1 production qualification. The separate print-readiness projection remains 5 `READY`, 15 `WAITING`, and 4 `NOT_SELECTED`. The camera alignment, final anchor drilling, robot power-up, motion, and contact remain blocked. Physical system release remains `UNRELEASED`, `safe_to_power_robot` is `false`, and `contact_enabled` is `false`.

The 2026-09-02 transition chain is intentionally append-only:

- **Historical Freeze 005:** the 14-source hardware-alignment and park/reach/simulation provenance baseline. Its recorded study results are historical evidence and are not re-run or relabeled by the later Job 00A evidence freezes.
- **Freeze 005 → 006:** a seven-source Job 00A lifecycle transition changed `config/measurement_record.json`, `BUILD_BY_STEP/INDEX.json`, `BUILD_BY_STEP/PACKAGE_VALIDATION.json`, `RELEASE_VALIDATION.json`, `PRINT_READINESS.json`, `BUILD_TRACKER.json`, and `PREHARDWARE_READINESS.json`; it recorded Job 00A as `PRINTED` and the keyboard-corner coupon as `PASS` at 0.0 mm compensation.
- **Freeze 006 → 007:** a five-source traceability synchronization changed `config/measurement_record.json`, `BUILD_BY_STEP/INDEX.json`, `BUILD_BY_STEP/PACKAGE_VALIDATION.json`, `RELEASE_VALIDATION.json`, and `PRINT_READINESS.json`; it added the post-Freeze-006 actual-screw/washer observation without changing the tray gate from `NOT_TESTED` or the 9/71/4 gate counts.
- **Freeze 007 → 008:** a seven-source operator-waived prototype functional-fit transition changed the same seven source paths as 005 → 006; it promoted only `tray_clearance_holes_coupon_pass` from `NOT_TESTED` to `PASS`, producing the then-current 10/70/4 counts. This waiver is scoped to that prototype coupon gate and confers no robot-power, motion, contact, or broader metrology authority.
- **Freeze 008 → 009:** a seven-source operator-confirmed functional-fit transition accepted `keyboard_station_registration_coupon_pass` at 6.2 mm round/slot geometry, advanced Job 00A to `POSTPRINT_PASS`, and produced the then-current 11/69/4 counts. It does not release any downstream print, robot power, motion, or contact capability.
- **Freeze 009 → 010:** a 14-source controlled reconciliation captured the static-camera architecture conflict as an alignment hold, preserved the passed Job 00A/00B fits, recorded the loose N7.4 nut and narrow tie saddle as two explicit failures, and regenerated the Job 03C1 production-equivalent rail with a 7.2 mm captive nut seat and 5.6 x 2.2 mm tie passage. The current gate counts are 15 `PASS`, 63 `NOT_TESTED`, 4 `NA`, and 2 `FAIL`; physical release remains `UNRELEASED`.
- **Freeze 010 → 011:** a four-source workflow correction removed Job 03C2's impossible self-dependency on `board_setup_template_scale_pass`, kept that paper-template check as an external prerequisite, and generalized validation against all postprint self-producer cycles. Geometry, Job 03C1 settings, gate counts, and physical authority are unchanged.

## 4. Nominal values that are not contact coordinates

The following remain design seeds only:

- keyboard origin (85,85) mm and nominal envelope;
- phone origin (499.2,84.2) mm and nominal screen Z 11.9 mm;
- TCP puck target Z 10.5 mm;
- station origins and candidate printed-fit dimensions;
- the rear arm-clamp allowed X range;
- nominal AprilTag XY with null optical Z.

Before contact, the runtime needs measured and accepted `B_T_Wv`, a separately qualified `R_ctrl` controller-model correlation, `B_T_K`, `B_T_P`, `B_T_S`, screen homography, route-specific free-state TCP, spring travel model, and target error budget.

The RC03 detector emits `C_T_B` translation in metres. The runtime frame graph is millimetres. The vision adapter must scale only the translation by 1000 and retain the source unit; a direct untyped matrix composition is an error.

## 5. Visibility and calibration policy

The Phase-1 primary is the purchased Arducam B0477/IMX283 in a rigid static
eye-to-hand support. Qualification must bind the received serial/USB identity,
delivered 16 mm C-mount lens and case, and one exact full-frame mode. The
published native `5472 x 3648 @ 9 fps YUY2` USB 3.0 mode is the receipt-test
target, not a commissioned fact; close/reopen and reboot tests must prove that
the driver has not silently changed the resolution, pixel format, crop, image
orientation, or controls.

At startup and each pre-descent observation posture, all six installed tags
must be accepted: T0–T3 solve the board pose, while K0 and P0 are excluded from
the fit and checked independently. A fresh `C_overhead_optical_T_B`
observation must pass identity, settings, freshness, distribution,
reprojection/covariance, and held-out residual gates. The same image campaign
must verify the expected keyboard or phone is present, seated, oriented, and
consistent with its qualified target map. Missing, stale, moved, ambiguous, or
weakly observed evidence blocks descent; there is no automatic arm-camera
fallback.

The selected Phase-1 calibration architecture is:

1. record the exact received B0477 camera, sensor claim, delivered 16 mm lens,
   metal case, persistent USB descriptors, driver, mode, crop/orientation,
   exposure, gain, white balance, focus, aperture, and every locked control;
2. qualify the final fixed support, camera retention, fixed cable and strain
   relief, lighting, complete collision/keepout geometry, settling behavior,
   and support-reference witness before collecting calibration evidence;
3. calibrate ChArUco intrinsics and distortion at those exact settings, retain
   varied training views and held-out residuals, and invalidate the result on
   any camera/lens/focus/aperture/mode/crop/orientation change;
4. measure the installed six-tag map in `B`, then solve and independently
   validate the constant static extrinsic `Wv_T_C_overhead_optical`;
5. acquire a fresh per-observation `C_overhead_optical_T_B`, form
   `Wv_T_B = Wv_T_C_overhead_optical * C_overhead_optical_T_B`, and verify
   keyboard/phone presence, seating, orientation, pose, and target-map
   residuals before allowing the pending action to proceed;
6. correlate controller frame `R_ctrl` to `Wv` independently over the usable
   robot range; camera-board agreement must never be used as proof of encoder
   signs, zeros, limits, or controller-model correlation;
7. calibrate each route-specific free-state TCP and compliance model, then use
   the existing keyed puck for independent TCP, approach-axis, and Z/travel
   checks across both keyboard and phone regions; and
8. accept the complete static support, arm, tools, devices, lighting, cable,
   clamp, and fixture collision/swept-volume model plus held-out end-to-end
   keyboard and phone trials before contact capability is considered.

The support witness detects camera/support movement; it is not a substitute
for an accepted static extrinsic. A tool witness is conditional for identity,
seating, or spring deflection only when its motion is observable and its frame
is calibrated. No additional holes or permanent datums may be added under this
freeze; use a controlled removable fixture or a formal RC03 revision.

The Freeze-009 IMX335 eye-on-arm calibration chain (`E_T_Carm`, synchronized
joint/camera timing, moving cable, and route visibility) is retained only as
historical provenance and an optional Phase-2 research path. It cannot satisfy
or bypass any Phase-1 static-camera gate.

## 6. Controlled hardware addendum required before contact

The following items are valuable parts of the system architecture but are not yet released by RC03-INT-R1's controlled CAD/BOM/gates:

| Delta | Required controlled work |
| --- | --- |
| Primary static B0477 integration | Received camera/lens/case identity; retained-support geometry and fasteners; fixed USB/strain-relief/lighting geometry; collision and swept-volume proof; one-metre focus; intrinsics/distortion; `Wv_T_C_overhead_optical`; board/tag visibility; support drift; and held-out acceptance |
| Optional Phase-2 arm-camera integration | Exact camera/holder/carrier-link identity; mount geometry/fasteners; mass/CG/moment; moving cable service loop, strain relief, drag/flex/disconnect behavior; collision/swept volume; payload/reach/gravity consequences; intrinsics, `E_T_Carm`, frame/joint sync, zone visibility, and held-out acceptance; never an automatic fallback |
| Static calibration target and conditional route-specific tool witness | Board registration without new holes; target observability; witness attachment/mass/envelope/retention/visibility/transform and effect on travel/conductivity only if its measured role is justified |
| Inline contact sensor and local guard | Sensor range after force-envelope approval, mechanical stack, calibration, drift/sample rate, independent trip latency/topology, firmware hash, cable routing, and fail-safe tests |
| Gravity-safe power-loss containment | Representative-pose unpowered swept envelope, dummy load, support/catch/counterbalance identity, clearances, and evidence |
| Optional external mast camera | Separate `C_ext` frame, mount/keepout calibration, explicit verifier/fallback role, and reopened gates before any promotion; never automatic runtime fallback |

These require a controlled RC03 addendum or next revision before installation/use. Until those records and new gates pass, autonomous contact remains blocked. The master plan may define the requirements, but it must not claim the current RC03 release already contains them.

## 7. Immediate build-aligned sequence

1. Continue active build `2026-09-01_CELL-A` through Step 00 without claiming any unperformed PASS; retain its build ID in every evidence record.
2. Record the RoArm serial/controller/firmware, exact PERIBOARD-409, bare Galaxy A16 5G, received Arducam B0477/IMX283 identity, delivered 16 mm lens/case, persistent USB identity/modes/controls/cable, static-support parts and fasteners, clamp, spring, rod, stylus, board, and materials. Record the bundled arm-camera holder only as package inventory unless a separately controlled Phase-2 experiment is opened.
3. Preserve Job 00A's `POSTPRINT_PASS` evidence and record Jobs 00B–00F before releasing any dependent production print; treat print readiness and lifecycle state as separate authoritative projections.
4. Use the historical Freeze-005 simulation foundation, retained unchanged as provenance under active Freeze 011—the exact-byte bounded pinned Waveshare URDF projection and typed transforms/FK, separately framed controller FK/T=104 easing emulator, nominal RC03 scene, real-JPEG fixed-overview tag detection/planar pose, nominal target maps, deterministic tool-tip paths, bounded reach/park/full-route IK, solver-task numerical-rank diagnostics, strict virtual-workcell bootstrap, locked rank-1 multi-action virtual commissioning with pixel-gated hover/fault/record/replay, aggregate prehardware qualification, and offline raw-feedback/capture-bundle eye-on-arm checks—to reject bad assumptions early. It is simulation-only and supplies no physical evidence or authority.
   The current software checkpoint additionally binds semantic profiles to their target catalogs, validates the placemat across 17 cross-source checks, locks the software simulation inputs by SHA-256, and can sweep every nominal target/phase/tool case plus required park. Under the nominal -100 mm virtual tool, contact screening accepts only 6/46 keyboard targets (`A`, `C`, `SPACE`, `TAB`, `X`, `Z`) but 29/29 phone targets. Across all tools and phases, 625/1200 target poses solve. The frozen nominal park solves only for the no-extension `hand_tcp_only` case at zero effective joint margin; the 80, 100, and 120 mm contact-tool cases reject it.

   A bounded park optimizer now selects the simulation-only board-frame overlay `(290, 10, 70) mm`. Both selected 100 mm tools accept that point independently, with `0.2704734350` worst normalized arm-joint margin and 10 mm modeled planar tool-tip clearance. With this overlay, the keyboard `"a"` route accepts 24/24 sampled waypoints and reports a diagnostic pass with unsupported checks. The phone `"a"` route still stops at `APPROACH` because its normalized arm margin is `0.000657824`, below the `0.01` gate; both fully screened reach finalists also reject phone `key_a` contact. The trajectory schema-v2 gate now rejects numerical rank loss in the solver's weighted five-constraint task Jacobian, but normalized conditioning is report-only. Full physical six-dimensional singularity/manipulability and all link/holder/camera/tool/cable collision volumes remain blockers. Treat the combined evidence as a mandatory base/tool/layout redesign input, not measured physical reach evidence.

   The strict offline eye-on-arm capture bundle binds exact T=1051 wire lines, JPEG bytes, normalized detections, and declared pre/exposure/post brackets to exact-file-pinned dataset/evidence inputs. Its result is structural only because device measurement time, clock-correlation content, registry-resolved camera/artifact identities, and raw tag corner/inlier/covariance evidence remain unqualified.
   The six-artifact simulation bundle now locks the rank-1 virtual commissioning profile as `UNMEASURED_SENSITIVITY_OVERLAY`. Keyboard `test` and Android `test.` exercise 48 and 61 virtual joint waypoints respectively. Before every physical action, a fresh fixed-overview JPEG is independently decoded into IDs 0-5 and a planar `camera_overview_optical_T_board` estimate; synthetic tag/residual/fixture-pose gates must pass before approach. The processor receives no action/target, and association occurs afterward. Each contact is then derived from the IK solver's achieved board-frame tip position and tool axis and resolved against the complete nominal target polygons plus synthetic depth, normal, dwell, focus, and UI-state policy. The device receives neither the planned target nor a per-action expected character; a separate exact-once observer receives only the resulting `ContactResult` stream and verifies output hash/length. Schema-v3 reports and manifest-v2 packages cross-bind the redacted vision ledger and all contact-result hashes, strictly reconstruct nested records, and fully recompute every artifact. These are stronger software regression checks, but they do not apply robot-frame correction or alter RC03 geometry, calibration state, power/contact gates, or physical release.
5. Define and measure the exact static support/carriage and `Wv_T_C_overhead_optical`, B0477 intrinsics/distortion and locked controls, controller-frame correlation, complete arm/tool/support/camera/lighting/fixed-cable collision geometry, capture/feedback timing, and route TCP/device calibrations.
6. Close the robot-reach and static-camera architecture holds with installed-system IK/orientation, payload, singularity, cable, approach/retract, collision, calibration, visibility, drift, and held-out validation evidence. Release the controlled camera/static-target/contact-guard/gravity-stop addendum without inventing mount dimensions or changing board holes informally.
7. Proceed to hardware-in-loop feedback and empty-cell characterization only after the E-stop, gravity-safe containment, active-build evidence, frame contract, and relevant gate projections permit it. Keep contact separately blocked.
8. Regenerate RC03 after every accepted override, rerun its validators, and update the system-manifest snapshot.

Run the alignment check from the workspace root:

```text
python software/tools/validate_build_alignment.py
```

A valid result is `ALIGNED_CAMERA_HOLD_CONTACT_BLOCKED` at this stage. Any hash or contract mismatch is `FAIL`. Contact only becomes possible through a later manifest revision after the physical and new addendum gates pass.

### 7.1 Controlled re-freeze procedure

A changed RC03 source set must first be regenerated and pass its own release,
print-readiness, build-step, documentation-sync, checksum, and pre-hardware
checks. Some RC03 commands named `--check` refresh deterministic generated
reports; treat them as controlled regeneration operations, not universally
read-only probes. Review their resulting source hashes before continuing.

Prepare the next software-only freeze without writing anything:

```powershell
python software/tools/refreeze_build_alignment.py `
  --expected-current-freeze-id ROCELL-PHASE0-RC03-INT-R1-FREEZE-011 `
  --new-freeze-number 12 `
  --date YYYY-MM-DD `
  --reason "Approved complete RC03 source reconciliation" `
  --approval-reference "controlled review record or signer reference"
```

Review every changed source, the prospective validation result, archive path,
transaction path, input-set hash, and `plan_sha256`. Apply only that exact plan:

```powershell
python software/tools/refreeze_build_alignment.py `
  --expected-current-freeze-id ROCELL-PHASE0-RC03-INT-R1-FREEZE-011 `
  --new-freeze-number 12 `
  --date YYYY-MM-DD `
  --reason "Approved complete RC03 source reconciliation" `
  --approval-reference "controlled review record or signer reference" `
  --expected-plan-sha256 <reviewed-plan-sha256> `
  --apply
python software/tools/validate_build_alignment.py
```

The apply invocation locks before rebuilding the reviewed plan, requires the
exact reviewed hash in that lock, recomputes the digest of the immutable
rendered payloads, and requires the expected, summarized, and recomputed hashes
to agree. It rechecks every consumed input both before staging and immediately
before the first replacement, prospectively runs the production alignment
validator, archives the prior seven provenance aliases, writes an append-only
transition record, commits dependency leaves and the bundle, and switches
`system_manifest.json` last. A no-source-change freeze is rejected unless an
explicit `--companion-change-reason` is recorded.

If the process is interrupted, do not delete `.refreeze.lock` until no writer is
running and the active aliases have been inspected. If the active manifest is
still the old ID, restore the old camera manifest, simulation hardware profile,
gate projection, simulation bundle lock, calibration registry, and system
manifest from `software/freezes/<old-manifest-id>/` to their active paths. Leave
the archive and transaction evidence untouched, remove only the stale lock,
rerun the dry plan, review its hash, and apply again. If the active manifest is
already the new ID, run the alignment validator; treat any error as a failed
transaction requiring controlled recovery, never as permission to refresh one
hash.

For an old-manifest recovery, use the inspected prior-freeze directory and
restore the manifest last. The calibration-registry archive intentionally has a
different filename from its active alias:

```powershell
$priorFreeze = "software/freezes/<old-manifest-id>"
Copy-Item -LiteralPath "$priorFreeze/camera_manifest.json" -Destination "software/config/camera_manifest.json"
Copy-Item -LiteralPath "$priorFreeze/simulation_hardware_profile.json" -Destination "software/config/simulation_hardware_profile.json"
Copy-Item -LiteralPath "$priorFreeze/gate_projection.json" -Destination "software/config/gate_projection.json"
Copy-Item -LiteralPath "$priorFreeze/calibration_registry.json" -Destination "software/calibrations/registry.json"
Copy-Item -LiteralPath "$priorFreeze/simulation_bundle_lock.json" -Destination "software/config/simulation_bundle_lock.json"
Copy-Item -LiteralPath "$priorFreeze/system_manifest.json" -Destination "software/config/system_manifest.json"
python software/tools/validate_build_alignment.py
```

Do not run those copies until the exact prior directory and active manifest have
been inspected. If an expected archive file is missing or its transaction hash
does not match, stop for controlled recovery rather than reconstructing it.

If hardware files change while this freeze remains selected, the validator and
runtime importer must fail on the old expected hashes. Do not update the
manifest piecemeal. Finish the hardware-side revision, regenerate its dependent
records, then publish one synchronized manifest/bundle revision and invalidate
all affected simulation and calibration artifacts.
