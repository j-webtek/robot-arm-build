# Product-size ghost typing: PERIBOARD-409U

Date: 2026-09-17
Status: active camera-free development direction; live qualification incomplete.

## Immediate execution agreement (2026-09-17)

Follow the active goal and autonomy rules in
[the main plan](PRACTICAL_PATH_TO_TYPING_AND_TAPPING.md). The offline A–S–D typing
rehearsal is complete: all 55 projected controller legs have interpolation and
endpoint checks, with fault-stop cases and reproducible exports. Preserve this
as regression coverage, including source hashes, key/phase mapping and bounded
per-leg subplans rather than widening existing runner limits.

The later side-view 5-degree test produced reported elbow movement and the user
confirmed seeing it. Two 5-degree trials reported approximately 2-degree changes;
arrival remains unverified. Follow the main plan's endpoint characterization
sequence: analyze saved traces, test a justified local adjustment, and validate
held-out endpoints rather than assume a universal compensation. Then validate
a live-pose approach before physical ghost cycles. Power/setup confirmation is a
standing assumption, not a reason for routine prompts; current telemetry still
must be checked. Camera and stylus mounting remain deferred and do not block
offline rehearsal. Actual contact and physical accuracy are separate later gates.

## Purpose

Represent the user's actual keyboard at full scale, plan an assumed stylus tip's
typing trajectory, and then exercise qualified parts of that trajectory with the
real arm in empty space. The camera stays deferred while its support is built.
Do not substitute the earlier artificial A/B/C row for this product geometry.

## 1. Product facts and modeling assumptions

Selected physical stylus: OASO disc-tip touchscreen stylus, ASIN B08Q7L85X2.
See [selected stylus reference](SELECTED_STYLUS_REFERENCE.md) for mounting and
robot-held touch validation. The 100 mm tool offset below remains a simulation
assumption, not this product's measured length or mounted tip calibration.

User product: [Amazon ASIN B007LQKFG0](https://www.amazon.com/dp/B007LQKFG0),
Perixx PERIBOARD-409U, USB, English US.
[Perixx's product specification](https://eu.perixx.com/products/periboard-409)
lists **315 mm width × 147 mm depth × 21 mm height**. Use these metric dimensions.
The retrieved Amazon dimension field contains an inconsistent 40-inch length;
do not use it as geometric input. Overall dimensions do not specify each key's
center, keycap contour, tilt or switch travel.

The workspace already contains the full-size nominal model:
`software/config/static_nominal_target_profiles.json`, keyboard profile
`periboard-409-us-nominal-sim-v1-static-v1`. Reuse it and its semantic compiler.
It includes alphanumeric rows and explicit TAB, ENTER and SPACE targets; it is
not an exhaustive, measured map of every physical key.

| Quantity | Initial value | Evidence/basis |
| --- | --- | --- |
| Housing dimensions | 315 × 147 × 21 mm | Manufacturer specification |
| Local frame | X right from left edge; Y rearward from front; Z up | Modeling convention |
| Nominal board placement | Front-left XY [85,85] mm | Existing design, not installed registration |
| Nominal key plane | Board Z=21 mm | Simplification; not a measured key-top plane |
| Nominal key pitch | 19.05 mm | Existing synthetic ANSI seed, not verified product drawing |
| Ordinary key interior | 14 × 14 mm centered on nominal key | Existing conservative simulation target |
| Assumed tool offset | 100 mm along negative modeled hand-TCP Z | Fixed numerical hypothesis, not physical stylus length measurement |

Keep the housing dimensions fixed. Label the key geometry NOMINAL_UNMEASURED.
For example, the current local centers of A/S/D are [36.3,69], [55.35,69] and
[74.4,69] mm. Do not call these manufacturer-confirmed coordinates.

## 2. What it means to know the space without a camera

We can define a consistent virtual coordinate system and compute expected tip
position. That is enough to develop commands and test reported response. It is
not independent knowledge of where the real tip or bench is located.

Keep these transforms separate:

- Keyboard-local → virtual board/world: chosen translation and orientation.
- Virtual world → controller: explicit nominal correlation, subsequently reviewed
  for the actual free-space test. Never equate URDF world and firmware R_ctrl.
- Controlled end effector → assumed tip: constant 100 mm offset in the named
  tool frame, rotated by tool orientation. Do not subtract 100 mm from world Z
  for arbitrary orientations, or add it twice to existing end-effector geometry.

Compute tip position using `p_tip = p_reference + R_reference * offset_tool`.
Solve reference goals from desired tip poses using the inverse transform. Keep
both desired tip and controller-reference targets in every result. When no stylus
is attached, the tip is imaginary; inspect clearance of the actual gripper/links.

## 3. Implement the full-size ghost overlay

1. Preserve the current frozen target files and earlier three-key regression suite.
2. Add a separately versioned product-size ghost overlay referencing the existing
   target profile and its hash. Store the assumed tool transform explicitly.
3. Allow whole-keyboard translation/yaw and a virtual plane height as simulation
   settings. Do not scale the keyboard or silently move individual difficult keys.
4. Start with A, A–S–A, then A–S–D; expand to rows and a short word after qualification.
   Unsupported characters must fail clearly, not map to arbitrary nearby keys.
5. Generate travel above the virtual plane → hover → virtual downstroke → retract.
   Lateral travel only after retraction. No physical contact during ghost trials.
6. Screen sampled inverse kinematics, joint margins, orientation and modeled
   geometry for the entire route. Report collision/geometry omissions explicitly.
7. Retain all failed placements, then compare a finite set of whole-layout placement
   candidates. Select a reachable subset before demanding whole-keyboard coverage.

## 4. Initial simulation evidence — already run

The existing static task pipeline operates without capturing a camera image.
Both runs used `--park-xy-mm 290 40 --tool-length-mm 100 --dense`.

| Requested text | Result | Interpretation |
| --- | --- | --- |
| `a` | DENSE_SAMPLES_PASS_NOT_EXECUTABLE; 38/38 waypoints | A useful initial numerical route, not hardware approval |
| `asd` | DENSE_ROUTE_FAILED; 30/58 evaluated | First failure at S APPROACH, waypoint 29: MINIMUM_NORMALIZED_ARM_JOINT_MARGIN_REJECTED |

Evidence under `software/runs/wizard-exports`:

- `a`: `wizard-20260917T151803853383Z-f4514bfb625941cb9d95d6c5a0f007fb`
- `asd`: `wizard-20260917T151749313488Z-10e35e2f2fb046f7aea0d338c9511338`

Reproduce from workspace:

```powershell
.\.venv\Scripts\python.exe software/scripts/rehearse_static_task.py --device keyboard --text a --park-xy-mm 290 40 --tool-length-mm 100 --dense
.\.venv\Scripts\python.exe software/scripts/rehearse_static_task.py --device keyboard --text asd --park-xy-mm 290 40 --tool-length-mm 100 --dense
```

Next numerical task: expose product-size placement as an explicit ghost overlay,
then evaluate a small declared set of placements at fixed 100 mm tool offset.
Do not remove the margin check simply to obtain a passing A–S–D route.

## 5. Connect the simulation to actual free-space motion

### Placement study implemented

`rehearse_static_task.py` now accepts `--keyboard-translation-mm DX DY` (each
axis bounded to +/-50 mm). It translates every nominal keyboard target and the
keyboard envelope together, preserving size, pitch and orientation. The existing
scene's other devices/obstacles remain in place. Fixture geometry is not redesigned
or relocated, so this is not a claim that the physical mounting permits the shift.
Source files are unchanged; a separate overlay hash and transform are exported.

Four declared offsets were evaluated for `asd`, fixed 100 mm tool and park [290,40]:

| XY shift mm | Result | First failed target/phase |
| --- | --- | --- |
| [+20,0] | Failed | A / APPROACH, joint margin |
| [-20,0] | Failed | D / APPROACH, joint margin |
| [0,+20] | Failed | A / HOVER, joint margin |
| [0,-20] | **56/56 sampled waypoints pass** | None |

The passing candidate changes nominal front-left origin from [85,85] to [85,65]
mm; housing remains 315 × 147 × 21 mm. This is a shift toward the board front,
not a change in the robot's coordinate convention. It is NOT executable clearance
or independently measured tool accuracy. No margin gate was relaxed.

Reproduce the selected candidate:

```powershell
.\.venv\Scripts\python.exe software/scripts/rehearse_static_task.py --device keyboard --text asd --park-xy-mm 290 40 --tool-length-mm 100 --dense --keyboard-translation-mm 0 -20
```

Passing export: `wizard-20260917T152617941503Z-4ec783651cc64029a66e4a7305b07139`.
Failed exports: `wizard-20260917T152604048517Z-26b68ca9b7b744f491c32e755a8ecd81`,
`wizard-20260917T152617582834Z-b87db038e6634a45a77e348db4a1f8e1`,
`wizard-20260917T152620881257Z-f0a4916d4d9845f5849d95cb16fb4657`.
All paths are under `software/runs/wizard-exports`.

1. Read a new controller baseline and retain device identity and raw feedback.
2. Restore confidence in elbow response with one bounded, observed diagnostic or
   supported actuator evidence. The earlier direct elbow trial had no reported
   change; a matching numerical model alone cannot clear that discrepancy.
3. Anchor the candidate virtual keyboard to a reviewed clear region near the real
   starting pose. No precise board mapping or mounted camera is required for a
   gross motion test, but nominal coordinates cannot certify obstacle clearance.
4. Compare the modeled elbow and other-joint changes with the actual reports for
   one approach and return, then one virtual press cycle. Request only a simple
   observed moved/not-moved/uncertain result if external confirmation is needed.
5. If those pass, execute three cycles, then A–S–A. Keep finite trial limits and
   per-leg verification. On a failed or uncertain leg, do not send the next leg,
   automatically return, replay the stroke, or increase torque.
6. Export the keyboard/transform/tool hashes, desired tip pose, exact command,
   reported joints, reconstructed tip pose, residual, timing and sequence outcome.

No automatic move from the current position to the nominal [85,85] board layout
is authorized by defining this model. Initial native ghost integration must
preserve request-bound execution and the existing uncertainty handling.

## 6. Evaluate and improve

### Controller-frame bridge implemented (offline)

`preview_product_ghost_controller.py --input <passing-static-task-export>` verifies
the source archive and projects each solved URDF arm-joint vector through the
pinned firmware FK. It does NOT send board XYZ to the arm or assume those frames
are equal. The original achieved virtual tip coordinates, phases, keys and 100 mm
tool hypothesis remain beside the firmware end-edge coordinates.

For the selected A–S–D route: 56 samples and 55 adjacent legs project successfully.
Maximum firmware FK/IK angular round-trip residual is approximately 1.33e-15 rad;
maximum adjacent reference translation is 14.9573 mm. This is mathematical
consistency, not measured accuracy. The first projected reference point is roughly
[419.526,-15.089,49.480] mm, substantially different from the recent live pose.
There is NO implicit permission or planned path to jump to that first point.

The same-sign/same-zero URDF-to-controller joint map remains unvalidated on the
installed arm. The bridge emits no native request or gripper target. Thirteen
targeted bridge/overlay tests pass, including incomplete-route and wrong-tool
rejection. Next screen firmware interpolation between these projected samples,
then connect the sequence to incapable endpoint rehearsal. Validate an approach
from live state separately before any physical sequence.

- Compare requested and reported motion per key, approach direction and speed.
- Compute assumed-tip residuals from reported joints using the same tool model,
  but label them CONTROLLER_DERIVED, not externally measured physical accuracy.
- Keep command/reference residuals separate from model/tool uncertainty. A 100 mm
  assumption simplifies tests; it does not remove backlash, deflection or offsets.
- After baseline response works, compare bounded compensation on held-out repeats.
  Do not fit correction to unchanged feedback or change global servo settings.
- Add speed profiles and continuous movement only after sequential routes work.
- Once the holder/camera/keyboard are installed, replace assumptions with measured
  transforms and validate actual key events using the existing input observer.

## Completion criteria for this increment

Endpoint rehearsal checkpoint (2026-09-17): the actual selected product-size
A–S–D route now runs through the existing owned synthetic endpoint runner, with
one-leg subplans preserving its existing limits. Normal and delayed-arrival cases
each verified 55/55 legs. Seven faults injected at leg 2 (baseline mismatch,
short write, unchanged feedback, cancellation, pending cleanup, missing feedback,
position bias) each stopped after two attempted trials and skipped the other 53.
The suite checks statuses, write counts and skipped IDs, not just a success label.

Verified suite index:
`wizard-20260917T154706066974Z-cd9cb2e96eef495485fb22cfb0f9ac88/attachment-product-suite.json`.
It links nine sibling case exports; each case links individually verified leg
archives with raw synthetic requests/feedback and parent plan hash. No evidence
was truncated to fit export limits. These are synthetic endpoint tests, not
servo-dynamics simulation, physical clearance checks, or actual input events.

Reproduce:

```powershell
.\.venv\Scripts\python.exe software/scripts/rehearse_product_ghost_suite.py --input software/runs/wizard-exports/wizard-20260917T152617941503Z-4ec783651cc64029a66e4a7305b07139
```

The new product route executes through this CLI. The wizard Tasks section now
offers **Review full-size keyboard simulation export**: enter a case folder,
not the suite index, to verify its parent plan and every referenced leg archive,
then inspect key, phase, endpoint status and simulated write count. Example normal
case: `wizard-20260917T154656958613Z-94fced6ca7194a4187149f1f12ddd130`.
Use normal wizard log export to retain the review. This does not rerun a case or
replay hardware commands. The earlier artificial ghost wizard action remains
separate. Next qualify live elbow response and the current-pose approach before
physical ghost typing; the offline milestone does not clear those requirements.

Saved-result binding follow-up: review now reconstructs each one-leg input plan,
validates the retained typed request, checks its selected trial and result hash,
and compares every retained simulated write with the exact encoded goal. Valid
archives with mismatched commands, plan hashes, request bindings or physical
authority claims are rejected. Ten targeted tests pass, and all nine actual saved
suite cases pass this strengthened review. This establishes internal evidence
consistency only, not authenticity of servo observations or physical movement.

Interpolation checkpoint (2026-09-17): the selected A–S–D route passes reference
IK/FK checks at **12,877 interpolation samples across all 55 legs**, at modeled
SPD coefficient 0.05. `preview_product_ghost_controller.py` now exports both the
bridge and interpolation report. Each leg is bounded to 1,024 samples and processed
separately; no export or endpoint-runner limits changed. An initial 8,192-sample
whole-route budget stopped at leg index 34; that incomplete result is retained.

Verified passing export:
`wizard-20260917T154412417721Z-75a289dcf14e4c9295c78d9040b672ce`.
Initial budget-limited export:
`wizard-20260917T154345247417Z-2559a342e77b46b88b41f1c9fcede290`.
These checks do not qualify tool clearance, installed limits, roll/gripper, real
speed or hardware response. Next connect the route to per-leg endpoint rehearsal.

- [x] Identify product and verify overall dimensions against the manufacturer.
- [x] Locate/reuse the existing nominal full-size key model.
- [x] Run and retain fixed-100-mm simulated typing results, including failures.
- [x] Implement a bounded product-size translation overlay and compare candidates (yaw study remains optional).
- [x] Project the selected route into controller-reference coordinates offline.
- [x] Screen controller interpolation between all 55 projected adjacent legs.
- [x] Connect chosen route to the existing endpoint simulation/export workflow.
- [x] Verify normal completion and representative feedback-fault stop behavior; export the result index.
- [ ] Verify elbow response and actual noncontact ghost cycles.
- [ ] Compare repeated reported endpoints and qualify a short live ghost sequence.

Physical elbow response is visually confirmed; coordinated ghost cycles and
accurate arrival are not yet confirmed. Real key actuation and independent tip accuracy remain later milestones. This plan
does not require the camera to resume camera-free development or gross-motion tests.
