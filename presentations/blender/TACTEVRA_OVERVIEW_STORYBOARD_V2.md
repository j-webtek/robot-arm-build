# Tactevra overview film — story and storyboard v2

- **Status:** Production plan; not yet rendered
- **Target runtime:** 100–105 seconds
- **Audience:** Technical buyers, collaborators, and first-time GitHub visitors
- **Central demonstration:** A user asks Tactevra to type `READY`, then tap
  `Send`. The system interprets the intent, locates the keyboard and phone,
  admits a safe action sequence, executes it with one continuous robot and
  stylus, and verifies the observed result.
- **Evidence boundary:** Every physical action in this film is a presentation
  visualization until separately supported by physical qualification records.

## The new story

The film must feel like a complete transaction rather than a component tour.
It begins with a human objective, not a servo command. Tactevra turns that
objective into named actions, grounds them in the measured workcell, checks the
whole route, and then carries out a visible multi-step routine. The same
servo-style RoArm and the same clamped stylus remain on screen throughout the
physical sequence.

The audience should understand this sentence without reading the repository:

> Ask for an outcome. Tactevra converts it into checked physical actions,
> performs them across real interfaces, and verifies what happened.

The five-stage architecture remains, but it supports the story rather than
becoming the story:

`UNDERSTAND → LOCATE → CHECK → ACT → VERIFY`

## Continuity rules

These rules are mandatory for the next render.

1. **One robot:** use the detailed, servo-style RoArm in every shot. Do not use
   the smooth block-arm proxy for contact or motion.
2. **One tool:** the same dark stylus is visibly seated between the gripper jaws
   before the first move and remains attached through the final phone tap.
3. **One workcell:** board, robot base, portal, camera, keyboard, phone, docks,
   tags, cables, and fixtures keep the same transforms in every scene.
4. **One keyboard:** the photographed black RC03 keyboard, with the six-row
   layout, legends, status lights, protective rear film, and cable, never
   changes material or proportion.
5. **One phone:** the same measured dark phone, bezel, glass, receiver, camera,
   controls, charging recess, cable, and modeled interface remains in its
   indexed station.
6. **Visible cause and effect:** each target is shown before the arm enters;
   contact is visible; the observed result is shown after contact.
7. **No teleporting:** robot motion continues across cuts. A shot may change
   camera angle, but the joint pose at the cut must match on both sides.
8. **No unsupported claim:** label the rendered action `SIMULATED WORKCELL
   SEQUENCE`. Do not present it as evidence of qualified autonomous typing.

## Visual grammar

- **Human intent:** warm neutral light and clean, minimal text.
- **Model proposal:** amber.
- **Measured geometry and frame relationships:** cool blue.
- **Rejected or blocked state:** red, used only for rejection.
- **Admitted and verified state:** green.
- **Robot motion:** predominantly full or medium-wide compositions. Macro shots
  are brief inserts, not substitutes for showing the whole mechanism move.
- **Camera movement:** motivated dolly, crane, orbit, and overhead moves with
  eased acceleration. No instant reframing, snap zoom, or unmotivated spin.
- **Screen information:** the architecture ribbon plus one principal card at
  most. Do not cover the arm, stylus, gripper, target, or contact point.

## Scene-by-scene storyboard

| # | Time | Story beat | Picture and motion | On-screen information | Narration intention |
|---:|---:|---|---|---|---|
| 1 | 0:00–0:06 | **The ask** | Start close on a simple AI conversation. A user message appears: “Type READY, then tap Send.” Pull back just enough to reveal that the request is connected to a physical workcell, not an ordinary chatbot. | User request only. Small status: `Awaiting interpretation`. | Establish that the user describes an outcome in ordinary language. |
| 2 | 0:06–0:13 | **The physical stakes** | Match-cut from the word `Send` to the stationary robot, keyboard, and phone in a complete hero wide. Slowly orbit 12–15 degrees. The detailed arm is parked and the stylus is already clamped. | `AI THAT ACTS IN THE PHYSICAL WORLD` | A software guess becomes real motion, so intent cannot go straight to motors. |
| 3 | 0:13–0:20 | **Understand the intent** | Split the request into a compact ordered task strip beside the still workcell: `TYPE "READY"` → `TAP phone:send`. The strip is large enough to read on a phone. | `1 · UNDERSTAND` and two semantic actions. No joint angles. | Explain that the AI produces named, ordered actions—not servo commands. |
| 4 | 0:20–0:28 | **See the scene** | Crane upward to show the recognizable overhead camera, then transition through its lens into a square top-down view. Exact board tags pulse once. Keyboard and phone outlines lock into place. | `2 · LOCATE`; `keyboard found`; `phone found`; capture-quality indicators. | The camera anchors both devices to the board's shared coordinate frame. |
| 5 | 0:28–0:36 | **Resolve the targets** | Keep the overhead view. The letters R, E, A, D, and Y illuminate in order on the accurate keyboard. Then the phone's Send control illuminates. A thin blue path links the six named targets without showing raw motor motion. | Named target list with declared frame and uncertainty. | Known layouts turn semantic targets into candidate board coordinates. |
| 6 | 0:36–0:43 | **Show the safety boundary** | A deliberately stale proposal briefly replaces the current scene record. A red `REJECTED` card appears in unused space while the arm remains completely still. | `STALE SCENE → REJECT`; `NO MOTION AUTHORIZED`. | Demonstrate that a plausible command is not enough when its evidence is stale. |
| 7 | 0:43–0:51 | **Check the complete sequence** | The fresh sequence returns. An uncluttered route visualization runs above the surfaces: park → R → E → A → D → Y → retract → phone Send → verify. Gates tick in sequence. Keep the actual arm visible at rest. | `3 · CHECK`; frame, freshness, reach, clearance, ordering, speed class. | The system checks the batch and the transitions between actions, not only isolated endpoints. |
| 8 | 0:51–0:57 | **Authorize execution** | Green admission state. The camera moves from the plan card to the real stylus clamped in the servo gripper, then widens to include the complete robot and first target. | `SEQUENCE ADMITTED`; `6 actions`; `SIMULATED WORKCELL SEQUENCE`. | Make the contract boundary clear: only the checked sequence reaches the controller. |
| 9 | 0:57–1:07 | **Move to the keyboard** | One continuous medium-wide shot. The detailed arm rises from park, clears the fixtures, rotates toward the keyboard, and approaches a shared hover plane. All links, motors, wiring, gripper, and stylus move as one rig. | Small route progress: `TRANSIT → KEYBOARD HOVER`. | Introduce smooth coordinated motion, with no contact yet. |
| 10 | 1:07–1:20 | **Type READY** | Track laterally with the complete arm while it moves across the keyboard. For each letter: hover, short vertical press, visible key travel, retract, then smooth transit. Use two match-cut angles while preserving joint continuity. Brief macro inserts may show R and Y contact, but always return to the full mechanism. | `R  E  A  D  Y`; each character changes from outline to green after observed contact. | Show a useful multi-target behavior rather than one isolated H press. |
| 11 | 1:20–1:28 | **Verify the text** | Arm holds above the keyboard. A host observation panel shows `READY`; telemetry and visual observation agree. Only then does the route advance. | `EXPECTED: READY`; `OBSERVED: READY`; `STEP VERIFIED`. | Verification is part of the action loop, not an end-of-film decoration. |
| 12 | 1:28–1:38 | **Cross-device transition** | Wide diagonal composition. The arm retracts to a safe height, sweeps across the board, rotates the wrist to the phone approach orientation, and settles above the phone. The camera dollies with it so the travel reads spatially. | Route progress moves from `keyboard` to `phone:send`. | Show that the same checked coordinate system supports movement between interfaces. |
| 13 | 1:38–1:46 | **Tap Send** | Begin medium-wide with the detailed arm and phone together. Cut to a short macro only for the final stylus descent. The same stylus taps the modeled Send control once, retracts, and remains visible. | `ACTION 6 OF 6 · TAP SEND`; target ring fades on contact. | Complete the user's original compound intent. |
| 14 | 1:46–1:55 | **Verify the outcome** | Phone interface changes to a clear sent/confirmed state. The fixed-camera observation and controller telemetry converge into one green receipt while the arm holds position. | `COMMAND SENT`; telemetry ✓, observation ✓, ordered batch ✓. | The result—not merely arrival at a coordinate—closes the loop. |
| 15 | 1:55–2:03 | **The system payoff** | Pull back to the full workcell. The architecture ribbon lights in sequence: Understand, Locate, Check, Act, Verify. A single line connects user request, task plan, devices, and result. | `ONE INTENT. ONE CHECKED PHYSICAL WORKFLOW.` | Summarize the system as a reusable workflow, not a keyboard trick. |
| 16 | 2:03–2:08 | **End card** | Clean branded frame using the workcell silhouette. Do not end on a disclaimer or black tail. | `TACTEVRA`; `Physical intelligence, checked.`; project URL. Small grey line: `Concept visualization · physical qualification in progress`. | Finish on the promise and provide a next step. |

## Robot performance choreography

The motion must communicate control quality without pretending that a rendered
trajectory is qualified evidence.

### Keyboard sequence

1. Leave park with a vertical and rearward clearance move.
2. Travel to a shared keyboard hover plane.
3. For each letter, use a three-part press primitive:
   `hover → controlled descent → retract`.
4. Blend only the high-clearance lateral segments; do not round the actual
   contact descent.
5. Let the key cap depress visibly by a restrained amount at contact.
6. Keep the stylus axis plausibly aligned with the key-normal direction.
7. Pause above the keyboard while the observed string is checked.

### Phone sequence

1. Retract fully before leaving the keyboard envelope.
2. Use a visible high-clearance arc between the two devices.
3. Reorient the wrist before descending toward the phone.
4. Tap once with the same stylus and immediately retract.
5. Hold while the modeled phone state changes and the verification receipt is
   displayed.

### Animation quality

- Animate the actual servo-rig hierarchy; never substitute the generic press
  proxy.
- Use continuous joint-space curves with eased velocity and acceleration.
- Audit every edit for pose continuity by comparing outgoing and incoming
  frame transforms.
- Add restrained secondary cable motion, but prevent clipping through links,
  keyboard, phone, or board.
- Keep the whole arm readable during major transits. Contact inserts should be
  no longer than two seconds.

## Required asset corrections before animation

| Asset | Required condition |
|---|---|
| Robot | Detailed RoArm geometry, servo housings, dual links, fasteners, wiring, gripper, and one articulated rig used for every shot. |
| Stylus | Dark cylindrical body seated between visible jaws, plausible protrusion, finished compliant tip, no bulb-shaped placeholder. |
| Keyboard | Current measured black RC03 asset, consistent material in all shots, correct legends and six-row layout, individually animatable R/E/A/D/Y caps. |
| Phone | Current measured phone asset, consistent dark chassis and glass, readable Send and sent-confirmation states, screen content explicitly labeled as modeled UI. |
| Camera | Recognizable camera body, mount, lens, and optical point of view; visible during its introduction. |
| Board | Exact released tag36h11 IDs and stable device/fixture transforms. |

## Editorial and sound plan

- Compose narration first, then time motion to meaningful verbs: *asks*,
  *locates*, *rejects*, *checks*, *types*, *taps*, *verifies*.
- Maintain an audible music bed roughly 15–18 dB beneath speech.
- Use meaning-coded effects only: low thud for reject, short ticks for passed
  gates, light mechanism tone for transit, crisp key clicks for typing, soft tap
  for the phone, and one resolved chord for final verification.
- Do not use a whoosh on every edit.
- Give the typing sequence rhythmic variation without making it unnaturally
  fast. The viewer must be able to count five distinct contacts.
- Deliver a high-quality 1920×1080 master, a web-optimized GitHub version, and
  captioned social derivatives from the same timeline.

## Production checkpoints

The video is ready for final render only when all checkpoints pass.

- [ ] A greybox animatic communicates the full request-to-result story without
      narration.
- [ ] The identical robot mesh and rig are present in every physical shot.
- [ ] The stylus is visibly clamped before, during, and after all six actions.
- [ ] R, E, A, D, and Y are correctly located and visibly depress in order.
- [ ] The phone target and modeled confirmation state remain on the same phone.
- [ ] Every camera cut preserves robot pose continuity.
- [ ] The stale-plan example shows zero arm movement.
- [ ] No overlay hides the gripper, tool, target, or contact point.
- [ ] All device and fixture transforms match the dimension manifest.
- [ ] Captions, narration, graphics, and action order agree exactly.
- [ ] The end card accurately states the concept-visualization boundary.

## Why this version is stronger

The earlier film proves that Tactevra has a safety architecture, but its visible
payoff is only one isolated key. This treatment keeps the safety differentiator
while making the product understandable: the user asks for a compound outcome,
the system plans it, a single recognizable machine types a word and operates a
second device, and verification closes each phase. The result is more dynamic,
more legible, and more faithful to the project's intended architecture.
