# Printable Camera Frame Candidate Integration Map

**Document status:** CANDIDATE / PLANNING ONLY  
**Proposed route ID:** `camera_board_portal`  
**Primary material:** QIDI ABS Rapido  
**Printer basis:** QIDI Plus4, 0.4 mm nozzle, protected working envelope to be verified before release

> **Superseded for the standalone prototype build.** This is an earlier future-
> migration planning map and retains candidate one-file job names, tools, parts,
> and open interfaces that do not describe the frozen prototype package. Do not
> use it to print, buy hardware, or assemble. Use
> [`PRINTABLE_FRAME_BUILD_GUIDE.md`](PRINTABLE_FRAME_BUILD_GUIDE.md),
> [`print_jobs/printable_camera_frame_jobs.json`](print_jobs/printable_camera_frame_jobs.json),
> their same-base print sidecars, and [`BOM_PRINTABLE_FRAME.csv`](BOM_PRINTABLE_FRAME.csv).

## Release boundary

This document describes a possible future integration. **No migration into
`active-project/RoCell_v0_3`, controlled design revision, manufacturing release,
print authorization, or physical build authorization has occurred.** The current
active-project JSON, CSV, CAD, print jobs, build packages, manuals, gates, and
checksums remain authoritative until a reviewed change is implemented through
the normal generation and validation pipeline.

The proposed system is a fixed eye-to-hand camera portal whose structural frame,
camera holder, cable guides, and saddle bodies are 3D printed. Metal bolts, nuts,
washers, threaded inserts, compliant protective pads, and a secondary camera
tether are permitted. A printable part is not automatically a structurally
qualified part; the assembled portal must pass the physical evidence gates in
this document.

## Proposed no-drill interface

The portal would attach through removable **front-left and front-right corner
saddles**. Each saddle captures the existing board edge/corner with a
load-spreading upper and lower bearing surface and a mechanically retained clamp
stack. The interface must resist vertical lift, fore/aft slip, lateral slip, and
rotation without drilling or driving a fastener into the board.

The candidate interface has these non-negotiable rules:

- Add no camera-support holes, pilot holes, inserts, or threaded anchors to the
  board.
- Do not alter the released station-hole coordinates or add camera symbols to
  the 1:1 board drill guide.
- Measure the actual finished board thickness, corner geometry, edge condition,
  coatings, underside access, and local flatness before finalizing a saddle.
- Spread clamp load over replaceable protective pads. The clamp must not crush,
  split, permanently mark, or bow the board.
- Use captured metal nuts or inserts and accessible metal clamp bolts; do not
  rely on printed threads as the primary structural retention.
- Make left/right orientation unmistakable with embossed part IDs, hard stops,
  and keyed joints. A saddle must not be installable in a visibly plausible but
  unsafe partial-engagement state.
- Keep both saddles, fasteners, uprights, cable, and service loops outside the
  robot, station, device-loading, tag-visibility, and operator-access keepouts.
- Provide a secondary tether that prevents the camera from falling into the
  workcell after any single holder-fastener failure.

The board drill artifacts should therefore remain geometrically unchanged. A
future migration must still regression-check them and explicitly prove that no
camera-support bore or center mark was introduced.

## Proposed print route and jobs

All names below are candidate identifiers. The files do not become controlled
print inputs until their geometry, counts, orientations, profiles, prerequisites,
hashes, and inspection instructions appear in the active-project sources and
pass release validation.

| Job | Candidate plate | Proposed contents | Profile | Release sequence |
| --- | --- | --- | --- | --- |
| `00G` | `00G_ABS_camera_portal_fit_tests.3mf` | Front-corner saddle gap/edge fit ladder; keyed-splice clearance ladder; production-axis captive-nut, bolt-clearance, washer-seat, and pad-retention features | `abs_rapido_camera_frame_structural_0p4` | Diagnostic first. It establishes saddle and structural-joint selections; it does not prove the complete frame. |
| `08A` | `08A_ABS_camera_portal_left_first_article.3mf` | Left saddle, left upright segments, structural splice keys, gussets, and left upper corner | `abs_rapido_camera_frame_structural_0p4` | First structural side. Inspect and load-test before releasing the matched side. |
| `08B` | `08B_ABS_camera_portal_right_matched.3mf` | Right saddle, right upright segments, structural splice keys, gussets, and right upper corner | `abs_rapido_camera_frame_structural_0p4` | Released only after the `08A` side first article passes. |
| `08C` | `08C_ABS_camera_portal_crossbar.3mf` | Crossbar segments sized for the protected Plus4 envelope, keyed/bolted crossbar splices, camera-carriage rail, and service splice keys | `abs_rapido_camera_frame_structural_0p4` | Released after the structural coupons and first portal side pass. |
| `08D` | `08D_ABS_camera_holder_and_cable.3mf` | Production-equivalent camera-interface gauge, exact-camera holder, anti-rotation feature, strain-relief clips, cable guides, and secondary tether anchor | `abs_rapido_camera_holder_precision_0p4` | Camera-specific first article. Requires the actual camera and measured screw/interface data. |

Every structural segment must fit within the physically verified protected QIDI
Plus4 envelope at its released orientation. Long members must be segmented with
keyed, mechanically bolted joints; adhesive-only structural splices are not an
acceptable primary load path.

## Proposed ABS process profiles

### `abs_rapido_camera_frame_structural_0p4`

- Candidate process file:
  `hardware/static_overhead_camera/slicer_profiles/QIDI_PLUS4/abs_rapido_camera_frame_structural_0p4.process.json`
- Intended scope: saddles, uprights, gussets, crossbar, structural keys, and
  carriage rail.
- Uses the exact QIDI ABS Rapido filament preset for the installed 0.4 mm nozzle.
- Requires its own profile calibration and production-axis saddle/splice coupon
  evidence. Evidence from ASA mast feet or PETG plates is not transferable.

### `abs_rapido_camera_holder_precision_0p4`

- Candidate process file:
  `hardware/static_overhead_camera/slicer_profiles/QIDI_PLUS4/abs_rapido_camera_holder_precision_0p4.process.json`
- Intended scope: camera holder, camera-interface gauge, anti-rotation feature,
  strain relief, cable guides, and tether anchor.
- Uses the exact QIDI ABS Rapido filament preset for the installed 0.4 mm nozzle.
- Requires separate dimensional, screw-engagement, retention, cable, and
  post-print inspection evidence.

The candidate process JSON files are supporting design inputs only. Their
presence under `hardware/static_overhead_camera` does not mean that either
profile is registered, calibrated, released, or selectable in the active
project.

## Proposed prerequisite and evidence gates

### Architecture and measured inputs

| Gate ID | Required evidence |
| --- | --- |
| `camera_board_portal_architecture_released` | Approved fixed eye-to-hand architecture, controlled route selection, camera/support scope, and revision reference |
| `camera_mount_interface_measured` | Exact camera identity; envelope; mass and center of mass; mounting pattern/thread; blind-thread depth; connector and cable-exit envelope |
| `camera_portal_saddle_interface_measured` | Finished board thickness and tolerances; corner/edge geometry; coating; flatness; underside access; protective-pad thickness; available clamp envelope |
| `camera_portal_load_requirements_approved` | Engineer-approved camera payload, portal height/span, proof load, allowed sag, permanent set, drift, disturbance shift, clamp pressure/damage criteria, and test durations |

### Profile and coupon gates

| Gate ID | Required evidence |
| --- | --- |
| `abs_rapido_camera_frame_profile_calibrated` | Exact spool/lot, drying record, nozzle, saved process revision, calibration results, and native QIDI evidence |
| `abs_rapido_camera_holder_profile_calibrated` | Exact spool/lot, drying record, nozzle, saved process revision, dimensional calibration, and native QIDI evidence |
| `camera_portal_saddle_coupon_pass` | Selected no-drill saddle gap, pad retention, clamp-hardware fit, full engagement, release/removal, and no-damage result on representative board material |
| `camera_portal_splice_coupon_pass` | Selected key clearance, bolt/nut/washer seating, assembly force, play, crack inspection, and retained-joint result |
| `camera_holder_interface_coupon_pass` | Correct screw engagement without bottoming, anti-rotation retention, cable clearance, and tether attachment using the actual camera |

### First-article and post-print gates

| Gate ID | Required evidence |
| --- | --- |
| `camera_portal_side_first_article_pass` | `08A` dimensions, saddle engagement, joint fit, upright straightness, cracks/warp, and controlled single-side proof result |
| `camera_portal_matched_frame_postprint_pass` | `08A`-`08C` part counts, left/right identification, crossbar fit, joint witness marks, straightness, and damage inspection |
| `camera_holder_postprint_pass` | `08D` dimensions, mount engagement, anti-rotation, cable/strain relief, tether, and camera-retention inspection |

### Installed structural, safety, and vision gates

| Gate ID | Required evidence |
| --- | --- |
| `camera_portal_saddle_installation_pass` | Both saddles fully seated at the controlled front corners; specified clamp stacks and torque/turn method; board flatness; no crushing, marking, lift, slip, or interference |
| `camera_portal_static_load_sag_pass` | Unloaded and loaded crossbar/camera position, applied mass/load, hold time, elastic sag, permanent set after unloading, instrument ID, and photos |
| `camera_portal_24h_drift_pass` | Initial and 24-hour camera/crossbar position, temperature, camera payload, joint witness marks, board condition, and measured drift |
| `camera_portal_disturbance_stability_pass` | Measured shift after controlled cable pull, operator bump/disturbance, and representative printer/robot vibration; no joint or saddle slip |
| `camera_portal_tether_cable_pass` | Secondary tether retention, strain relief, service loop, bend clearance, connector security, and snag-free routing |
| `camera_portal_collision_clearance_pass` | De-energized sweep review plus controlled reduced-speed empty-cell evidence for frame, fasteners, camera, tether, and cable |
| `camera_intrinsics_calibration_pass` | Controlled camera settings, accepted calibration views, calibration file/hash, and approved reprojection result |
| `camera_board_extrinsics_fov_pass` | Board transform, required-tag visibility, solved board pose, repeatability, and full accepted operating field of view |
| `camera_runtime_settings_persistence_pass` | Focus, exposure, white balance, resolution, and camera identity remain controlled after disconnect/restart |

Acceptance limits for sag, permanent set, drift, disturbance shift, clamp load,
and clearance must come from the responsible engineering approval. The operator
records raw values; the documentation must not manufacture default limits merely
to produce a PASS.

## Proposed job prerequisite map

Common machine prerequisites for every job are
`plus4_machine_confirmed`, `plus4_protected_envelope_verified`, and
`nozzle_0p4_confirmed`.

| Job | Additional prerequisites before printing |
| --- | --- |
| `00G` | `camera_board_portal_architecture_released`; `camera_portal_saddle_interface_measured`; `abs_rapido_camera_frame_profile_calibrated` |
| `08A` | `camera_board_portal_architecture_released`; `camera_portal_saddle_interface_measured`; `camera_portal_load_requirements_approved`; `abs_rapido_camera_frame_profile_calibrated`; `camera_portal_saddle_coupon_pass`; `camera_portal_splice_coupon_pass`; `geometry_matches_measurements`; `qidi_studio_roundtrip_confirmed` |
| `08B` | All `08A` prerequisites plus `camera_portal_side_first_article_pass` |
| `08C` | All `08A` prerequisites plus `camera_portal_side_first_article_pass` |
| `08D` | `camera_board_portal_architecture_released`; `camera_mount_interface_measured`; `abs_rapido_camera_holder_profile_calibrated`; `camera_holder_interface_coupon_pass`; `geometry_matches_measurements`; `qidi_studio_roundtrip_confirmed` |

Route selection alone is not print authorization. A future readiness report must
continue to mark a selected job `WAITING` until all of its applicable gates pass.

## Proposed controlled kits

| Kit | Job | Contents that must be controlled together |
| --- | --- | --- |
| `KIT-CAM-PORTAL-COUPONS` | `00G` | Historical candidate kit only; superseded by the no-caliper, actual-board/camera go/no-go route in `PRINTABLE_FRAME_BUILD_GUIDE.md` and the exact `00G-*` sidecars |
| `KIT-CAM-PORTAL-LEFT` | `08A` | Accepted left saddle/upright/corner parts, keys, gussets, matched metal joint and saddle hardware, protective pads, inspection record |
| `KIT-CAM-PORTAL-RIGHT` | `08B` | Accepted right saddle/upright/corner parts, keys, gussets, matched metal joint and saddle hardware, protective pads, inspection record |
| `KIT-CAM-PORTAL-CROSSBAR` | `08C` | Crossbar segments, keyed splices, carriage rail, joint bolts/nuts/washers, witness-mark material, inspection record |
| `KIT-CAM-HOLDER` | `08D` | Exact identified camera, accepted holder/interface gauge, measured camera screw, anti-rotation restraint, cable clips, strain relief, tether and tether hardware, inspection record |

No kit may contain a board-drilling fastener or instruction. Saddle clamp-bolt
lengths and tightening controls remain open until the actual board, pad, saddle,
washer, and nut/insert stack is measured and qualified.

## Active-project sources affected by a future migration

A controlled migration would need coordinated changes to at least:

- `config/camera_architecture_decision.json`
- `config/measurement_record.json`
- `config/print_profiles.json`
- `config/print_jobs.json`
- `config/job_build_record.json`
- `config/assembly_steps.json`
- `config/workcell_layout.json` for saddle envelopes, portal pose, keepouts,
  camera frame, and cable corridor, but **not new board holes**
- `config/hardware_candidates.json`
- `config/v1_prehardware_configuration.json`
- `config/parameters.json`
- `config/user_overrides.example.json`
- `config/digital_fit_report.json`
- `config/robot_reach_screening.json`
- `BOM.csv`
- `JOB_KITS.csv`
- `FASTENER_MAP.csv` only if its schema is deliberately expanded to include
  non-drilling clamp stacks; no portal bore may be added to its board-feature map
- `ASSEMBLY_MANUAL.md`, `README_FIRST.md`, `RC03_INTEGRATED_BUILD_PLAN.md`,
  `MANUFACTURING_REVIEW.md`, `PRINT_ENHANCEMENT_PLAN.md`, and
  `FASTENER_AND_PRINT_UX_GUIDE.md`
- the camera and configuration records under `PRODUCTIZATION/`

The implementing change would also need updates to the CAD, plate, job-card,
measurement, readiness, release-validation, package, illustration, manual, and
workbook generators, plus their tests. In particular, any route whitelist or
validator that currently requires the exact legacy set
`03C3`/`06`/`07A`/`07B` must be revised deliberately rather than bypassed.

## Generated artifacts affected by a future migration

After the canonical changes, regenerate and validate:

- portal and holder STL/STEP files and the full-cell assembly STEP;
- CAD verification, mesh/part validation, digital-fit, load-screening, and
  collision/reach reports;
- Jobs `00G` and `08A`-`08D` 3MF plates, machine-readable print sidecars,
  readable print settings, and QIDI process references;
- `PRINT_PLAN.csv`, `PLATE_MANIFEST.csv`, `PRINT_READINESS.*`,
  `PREHARDWARE_READINESS.*`, `BUILD_TRACKER.*`, `JOB_CARDS.*`, and
  `JOB_KITS.csv`-derived outputs;
- part previews, assembly illustrations, Step 13 camera views, illustrated guide,
  assembly manual, and PDFs;
- affected `BUILD_BY_STEP` packages, manifests, indexes, evidence templates, and
  hashes;
- the print compatibility workbook, `RELEASE_VALIDATION.json`, and
  `SHA256SUMS.txt`.

The board drill DXF/SVG/PDF geometry and board-hole coordinate list are expected
to remain unchanged. They must be compared against the prior controlled version
and fail validation if the candidate camera route introduces any new board bore,
pilot, or center mark.

## Assembly-step integration

- **Step 00:** identify the exact camera and hardware; measure the saddle
  interface; qualify both ABS profiles; print and accept `00G`, `08A`-`08D`; kit
  all accepted components.
- **Step 01:** make no new camera-support hole. Inspect the finished front corners
  and preserve the released drill pattern.
- **Step 02:** confirm the saddle envelopes and lower clamp hardware do not
  interfere with the arm clamp, board reinforcement, bench support, or board
  anti-shift method.
- **Step 12:** retain ownership of AprilTag placement and
  `tag_direct_installation_pass`.
- **Step 13:** install the two no-drill saddles and printed portal; install and
  tether the camera; route its cable; perform sag, drift, disturbance, retention,
  calibration, FOV, and extrinsic checks.
- **Step 15:** repeat final portal/cable collision clearance and vision checks with
  the complete cell before controlled device contact.

## Legacy job disposition

Jobs `03C3`, `06`, `07A`, and `07B` must remain inactive and `NOT_SELECTED`
during candidate development:

- `03C3` is a PETG universal plate for the former fixed-mast fallback.
- `06`, `07A`, and `07B` qualify and produce ASA parts for a 2020-extrusion mast.
- They use different geometry, materials, hardware, interfaces, load paths,
  calibration assumptions, and evidence from the proposed printed saddle portal.
- Their coupon, first-article, and installation results cannot qualify any
  `camera_board_portal` job.
- Keeping the records inactive preserves traceability and avoids silently
  rewriting historical intent. Removal or formal deprecation should be a separate
  controlled decision after the new portal has passed qualification.

The proposed route must never turn
`fixed_camera_fallback_architecture_released` into a substitute for
`camera_board_portal_architecture_released`, and the new route must not make a
legacy mast job printable.

## Candidate exit criteria

This map is ready to enter controlled implementation only after all of the
following are available:

1. Exact camera model, mass/center of mass, mount, connector, and cable envelope.
2. Actual finished-board front-corner and thickness measurements.
3. Approved portal height/span, load cases, acceptance limits, and test methods.
4. CAD showing every part inside the verified print envelope and every structural
   joint mechanically captured.
5. A digital fit/collision review covering the complete robot sweep, stations,
   devices, tags, saddles, clamp hardware, frame, holder, tether, and cable.
6. A reviewed migration plan that updates canonical sources, generators, tests,
   operator documentation, generated artifacts, and release hashes together.

Until those conditions are met and the controlled validators pass, this remains
a candidate design map—not permission to print production parts, attach the
portal, enable the robot, or claim vision-system qualification.
