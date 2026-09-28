# Tactevra overview film — story and storyboard v2

- **Status:** Production plan; not yet rendered
- **Target runtime:** exactly 100 seconds
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

The film adopts one buyer-facing five-stage vocabulary. It must replace the
older public vocabulary in the player, chapters, captions, transcript, and
README in the same change that publishes the new render:

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

| # | Time | Stage | Beat | Picture and motion | On-screen information |
|---:|---:|---|---|---|---|
| 1 | 0:00–0:05 | — | **The ask** | Start on an unmistakable laptop/operator console, clearly separate from the target phone. The user request types in. | `Type READY, then tap Send.` |
| 2 | 0:05–0:12 | — | **The physical stakes** | Match-cut to the hero wide and orbit 12–15 degrees. The detailed arm is parked and its stylus is visibly clamped. | No caption; let the narration explain that a guess becomes motion. |
| 3 | 0:12–0:19 | `1 · UNDERSTAND` | **Model proposal** | An amber proposal card appears beside the stationary workcell. The request becomes two named, ordered actions. | `TYPE "READY" → TAP phone:send`; `frame board`; `confidence 0.96`; no joint angles. |
| 4 | 0:19–0:27 | `2 · LOCATE` | **See the scene** | Crane to the recognizable fixed camera, pass through its lens, and settle into a square overhead view. Exact board tags pulse and device outlines lock. | `keyboard found`; `phone found`; capture-quality indicators. |
| 5 | 0:27–0:33 | `2 · LOCATE` | **Resolve targets** | R, E, A, D, and Y illuminate in order, followed by the phone's Send control. A thin blue path links the named targets. | Declared frame, candidate coordinates, and uncertainty. |
| 6 | 0:33–0:39 | `3 · CHECK` | **Reject stale evidence** | A red card occupies empty frame space while the actual arm remains visibly still. Do not imply that the proposal itself aged; the scene evidence did. | `scene capture 41 s old`; `limit 2 s`; `REJECTED · NO MOTION`. |
| 7 | 0:39–0:46 | `3 · CHECK` | **Admit the sequence** | A fresh capture arrives. The route draws park → R → E → A → D → Y → retract → Send. Gates tick and the decision turns green. | `frame · freshness · reach · clearance · order · speed`; `6 ACTIONS ADMITTED`. |
| 8 | 0:46–0:53 | `4 · ACT` | **Transit** | One continuous medium-wide: the same detailed arm leaves park, clears the fixtures, and reaches the keyboard hover plane. | Small persistent corner tag begins: `SIMULATED WORKCELL SEQUENCE`. |
| 9 | 0:53–1:05 | `4 · ACT` | **Type READY** | Track laterally with the whole arm for five visible presses and no more than two brief contact inserts. As each key is pressed, that letter appears in the target phone's message field. | `R ✓  E ✓  A ✓  D ✓  Y ✓`; use both checks and green so state is not color-dependent. |
| 10 | 1:05–1:10 | `5 · VERIFY` | **Verify the text** | The arm holds above the keyboard. The same phone—not a floating host panel—shows `READY` in its message field. | `EXPECTED READY`; `OBSERVED READY ✓`. |
| 11 | 1:10–1:17 | `4 · ACT` | **Cross to phone** | Wide diagonal dolly follows a high-clearance arc from keyboard to phone while the wrist reorients. | Route progress: `keyboard → phone:send`. |
| 12 | 1:17–1:23 | `4 · ACT` | **Tap Send** | Start medium-wide; use a contact macro no longer than two seconds. The same stylus taps Send once and retracts. | `ACTION 6 OF 6`. |
| 13 | 1:23–1:30 | `5 · VERIFY` | **Verify outcome** | The phone moves `READY` from its input field into a sent message bubble. Telemetry and camera observation combine into one green receipt. | `MESSAGE SENT: READY`; telemetry ✓; observation ✓; order ✓. |
| 14 | 1:30–1:36 | all | **Payoff** | Pull back while `UNDERSTAND → LOCATE → CHECK → ACT → VERIFY` lights in order and a single line connects request, plan, devices, and result. | `ONE INTENT. ONE CHECKED PHYSICAL WORKFLOW.` |
| 15 | 1:36–1:40 | — | **End card** | Workcell silhouette, logo, and URL. If a suitable physical-workcell image exists, show it for the first two seconds under the label `THE REAL WORKCELL`, then resolve to the brand card. No black tail. | `TACTEVRA`; `Physical intelligence, checked.`; small grey line: `Concept visualization · physical qualification in progress`. |

## Draft narration

This approximately 150-word draft deliberately leaves scene 9 open for the
five typing sounds. Read it calmly and precisely; do not use a trailer voice.
The `/` marks a short natural breath.

```text
[0:05] When AI acts in the physical world, a guess becomes motion. /
       So intent can't go straight to the motors.
[0:12] The model proposes named, ordered actions: type READY, then tap Send. /
       Never joint angles.
[0:19] A fixed camera reads the board's tags / and locates the keyboard and
       the phone in one shared frame.
[0:27] Each named target becomes a measured coordinate.
[0:33] If the scene is stale, the plan is rejected. / Nothing moves.
[0:39] With fresh evidence, the whole sequence is checked: / frame, reach,
       clearance, order, speed. / Only then is it admitted.
[0:46] One arm. One stylus. One controller.
[0:53] [No narration. Let the five key clicks carry the sequence.]
[1:05] The text is verified before the next step.
[1:10] The arm clears the keyboard and crosses to the phone.
[1:17] One tap on Send.
[1:23] Telemetry and the camera agree: / the message was sent.
[1:30] Ask for an outcome. / Tactevra turns it into checked physical actions, /
       and verifies what happened.
[1:36] Tactevra. Physical intelligence, checked.
```

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
| Phone | Current measured phone asset, consistent dark chassis and glass, readable message-input, Send, and sent-confirmation states, screen content explicitly labeled as modeled UI. READY must appear in this phone's input field as the five keyboard contacts occur. |
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
- Build a 30-second social cut from the ask, stale-evidence rejection, READY
  typing, sent-message verification, and end card. Give it separate burned-in
  captions rather than cropping the 100-second captions.

## Production checkpoints

The video is ready for final render only when all checkpoints pass.

- [ ] A greybox animatic communicates the full request-to-result story without
      narration.
- [ ] The greybox animatic remains understandable and every principal card is
      readable at a 390-pixel-wide phone preview.
- [ ] The identical robot mesh and rig are present in every physical shot.
- [ ] The stylus is visibly clamped before, during, and after all six actions.
- [ ] R, E, A, D, and Y are correctly located and visibly depress in order.
- [ ] The phone target and modeled confirmation state remain on the same phone.
- [ ] READY appears in that phone's message field one character at a time, and
      the same text appears as a sent message after the Send tap.
- [ ] Every camera cut preserves robot pose continuity.
- [ ] The stale-plan example shows zero arm movement.
- [ ] No overlay hides the gripper, tool, target, or contact point.
- [ ] All device and fixture transforms match the dimension manifest.
- [ ] Captions, narration, graphics, and action order agree exactly.
- [ ] The player page, stage buttons, chapter track, captions, transcript,
      poster, social preview, and README adopt the new stage vocabulary and
      timings in the same PR that publishes the replacement render.
- [ ] A 30-second social cut exists with its own burned-in captions.
- [ ] The end card accurately states the concept-visualization boundary.

## Why this version is stronger

The earlier film proves that Tactevra has a safety architecture, but its visible
payoff is only one isolated key. This treatment keeps the safety differentiator
while making the product understandable: the user asks for a compound outcome,
the system plans it, a single recognizable machine types a word and operates a
second device, and verification closes each phase. The result is more dynamic,
more legible, and more faithful to the project's intended architecture.
