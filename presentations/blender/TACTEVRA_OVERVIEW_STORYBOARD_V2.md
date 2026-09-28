# Tactevra overview film — story and storyboard v2

- **Status:** Production plan; not yet rendered
- **Target runtime:** exactly 100 seconds
- **Audience:** Technical buyers, collaborators, and first-time GitHub visitors
- **Central demonstration:** A user asks Tactevra to open Messages on the phone,
  type `READY`, and send it. The system interprets the intent, identifies the
  requested device and app state, admits a safe phone-interaction sequence,
  executes it with one continuous robot and stylus, and verifies the observed
  result. The physical keyboard remains a separate supported interaction
  surface; it is never presented as the phone's input or feedback device.
- **Evidence boundary:** Every physical action in this film is a presentation
  visualization until separately supported by physical qualification records.

## The new story

The film must feel like a complete transaction rather than a component tour.
It begins with a human objective, not a servo command. Tactevra turns that
objective into named actions, grounds them in the measured workcell, checks the
whole route, and then carries out a visible multi-step routine inside the
phone's own interface. The same servo-style RoArm and the same clamped stylus
remain on screen throughout the physical sequence.

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
6. **Independent devices:** the physical keyboard and phone have separate
   target maps, coordinate frames, interaction primitives, and observed
   states. Never show keystrokes on the physical keyboard appearing on the
   phone.
7. **Visible cause and effect:** each target is shown before the arm enters;
   contact is visible; the observed result is shown after contact.
8. **No teleporting:** robot motion continues across cuts. A shot may change
   camera angle, but the joint pose at the cut must match on both sides.
9. **No unsupported claim:** label the rendered action `SIMULATED WORKCELL
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
| 1 | 0:00–0:05 | — | **The ask** | Start on an unmistakable laptop/operator console, clearly separate from the target phone. The user request types in. | `Open Messages on the phone, type READY, and send it.` |
| 2 | 0:05–0:12 | — | **The physical stakes** | Match-cut to the hero wide and orbit 12–15 degrees. The detailed arm is parked and its stylus is visibly clamped. | No caption; let the narration explain that a guess becomes motion. |
| 3 | 0:12–0:19 | `1 · UNDERSTAND` | **Model proposal** | An amber proposal card appears beside the stationary workcell. The request becomes three named, ordered phone actions. | `OPEN phone:messages → TYPE_TEXT "READY" → TAP phone:send`; `device phone`; `frame board`; `confidence 0.96`; no joint angles. |
| 4 | 0:19–0:27 | `2 · LOCATE` | **See the scene** | Crane to the recognizable fixed camera, pass through its lens, and settle into a square overhead view. Exact board tags pulse and device outlines lock. | `keyboard found`; `phone found`; capture-quality indicators. |
| 5 | 0:27–0:33 | `2 · LOCATE` | **Resolve device and targets** | The keyboard and phone receive separate blue device outlines and target-map labels. The request selects the phone. On that phone, Messages, the on-screen R/E/A/D/Y keys, and Send illuminate in order. A thin blue path links only the selected phone targets. | `physical keyboard · compatible, not selected`; `phone · selected`; declared frame, candidate coordinates, and uncertainty. |
| 6 | 0:33–0:39 | `3 · CHECK` | **Reject stale evidence** | A red card occupies empty frame space while the actual arm remains visibly still. Do not imply that the proposal itself aged; the scene evidence did. | `scene capture 41 s old`; `limit 2 s`; `REJECTED · NO MOTION`. |
| 7 | 0:39–0:46 | `3 · CHECK` | **Admit the sequence** | A fresh capture arrives. The compiled contact route draws park → Messages → R → E → A → D → Y → Send → retract. Gates tick and the decision turns green. | `device · app state · frame · freshness · reach · clearance · order · speed`; `3 SEMANTIC ACTIONS · 7 CONTACTS ADMITTED`. |
| 8 | 0:46–0:53 | `4 · ACT` | **Transit to phone** | One continuous medium-wide: the same detailed arm leaves park, clears the physical keyboard and fixtures without approaching them, and reaches the phone hover plane. | Small persistent corner tag begins: `SIMULATED WORKCELL SEQUENCE`. |
| 9 | 0:53–0:59 | `4 · ACT` | **Open Messages** | The complete arm remains readable while the stylus taps the Messages app icon. The modeled phone transitions from its home screen into a message composer with an on-screen keyboard. | `ACTION 1 OF 3 · OPEN MESSAGES`; observed app state changes to `messages.compose`. |
| 10 | 0:59–1:11 | `4 · ACT` | **Type READY on the phone** | Track with the whole arm for five visible taps on the phone's on-screen keyboard, using no more than two contact inserts. Each character appears in the same phone's message field. The physical keyboard remains untouched in the wider composition. | `R ✓  E ✓  A ✓  D ✓  Y ✓`; use both checks and green so state is not color-dependent. |
| 11 | 1:11–1:16 | `5 · VERIFY` | **Verify the draft** | The arm holds above the phone. Camera observation reads `READY` in the phone's message field and confirms the expected composer state. | `EXPECTED draft: READY`; `OBSERVED draft: READY ✓`; `app: Messages ✓`. |
| 12 | 1:16–1:22 | `4 · ACT` | **Tap Send** | Begin medium-wide; use a contact macro no longer than two seconds. The same stylus taps the phone's Send control once and retracts. | `ACTION 3 OF 3 · SEND`; compiled contact `7 OF 7`. |
| 13 | 1:22–1:29 | `5 · VERIFY` | **Verify outcome** | The phone moves `READY` from its input field into a sent message bubble. Telemetry, app state, and camera observation combine into one green receipt. | `MESSAGE SENT: READY`; telemetry ✓; app state ✓; observation ✓; order ✓. |
| 14 | 1:29–1:36 | all | **Compatibility payoff** | Pull back while `UNDERSTAND → LOCATE → CHECK → ACT → VERIFY` lights in order. A simple compatibility graphic shows the same semantic `TYPE_TEXT` contract branching to a physical-keyboard target map or a phone on-screen-key target map; the completed phone branch stays green and the unused keyboard branch stays blue. | `ONE INTENT CONTRACT · DEVICE-SPECIFIC TARGET MAPS`; `ONE CHECKED PHYSICAL WORKFLOW.` |
| 15 | 1:36–1:40 | — | **End card** | Workcell silhouette, logo, and URL. If a suitable physical-workcell image exists, show it for the first two seconds under the label `THE REAL WORKCELL`, then resolve to the brand card. No black tail. | `TACTEVRA`; `Physical intelligence, checked.`; small grey line: `Concept visualization · physical qualification in progress`. |

## Draft narration

This approximately 150-word draft deliberately leaves scene 9 open for the
five typing sounds. Read it calmly and precisely; do not use a trailer voice.
The `/` marks a short natural breath.

```text
[0:05] When AI acts in the physical world, a guess becomes motion. /
       So intent can't go straight to the motors.
[0:12] The model proposes named, ordered actions: open Messages, type READY, /
       then tap Send. Never joint angles.
[0:19] A fixed camera reads the board's tags / and locates the keyboard and
       the phone in one shared frame.
[0:27] The request selects the phone. / Its app controls and on-screen keys
       become measured targets.
[0:33] If the scene is stale, the plan is rejected. / Nothing moves.
[0:39] With fresh evidence, the whole sequence is checked: / frame, reach,
       clearance, order, speed. / Only then is it admitted.
[0:46] One arm. One stylus. One controller.
[0:53] Messages opens.
[0:59] [No narration. Let the five phone-key taps carry the sequence.]
[1:11] The draft is verified before the next step.
[1:16] One tap on Send.
[1:22] Telemetry, app state, and the camera agree: / the message was sent.
[1:29] One intent contract can safely target a keyboard or a phone, /
       with device-specific maps and controls.
[1:36] Tactevra. Physical intelligence, checked.
```

## Robot performance choreography

The motion must communicate control quality without pretending that a rendered
trajectory is qualified evidence.

### Phone sequence

1. Leave park with a vertical and rearward clearance move that visibly clears
   the physical keyboard and fixtures.
2. Reorient the wrist before descending to the phone hover plane.
3. Tap the Messages icon using `hover → controlled descent → retract`, then
   hold while the modeled app transition is observed.
4. For each on-screen letter, repeat the same three-part tap primitive. Blend
   only the high-clearance lateral segments; do not round the contact descent.
5. Keep the stylus axis plausibly aligned with the phone-screen normal.
6. Pause over the phone while `READY` and the composer state are checked.
7. Tap Send once with the same stylus and immediately retract.
8. Hold while the modeled sent state and final verification receipt appear.

### Device compatibility

- `TYPE_TEXT` is a semantic action, not a shared set of coordinates.
- A physical keyboard adapter resolves text into physical key targets and press
  primitives.
- A phone adapter resolves text into the active app's on-screen key targets and
  tap primitives.
- Each adapter declares its own device identity, target map, frame, app state,
  contact geometry, and verification rule before compilation.
- The film may show both maps for compatibility, but it must animate only the
  phone branch selected by this request.

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
| Keyboard | Current measured black RC03 asset, consistent material in all shots, correct legends and six-row layout, and its own physical-key target map. It remains stationary and untouched in this phone demonstration. |
| Phone | Current measured phone asset, consistent dark chassis and glass, home, Messages composer, on-screen keyboard, Send, and sent-confirmation states. Screen content is explicitly labeled as modeled UI. READY appears in this phone's input field as its five on-screen keys are tapped. |
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
  fast. The viewer must be able to count the Messages tap, five distinct
  on-screen-key taps, and the Send tap.
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
- [ ] The stylus is visibly clamped before, during, and after all seven compiled
      phone contacts.
- [ ] Messages, R, E, A, D, Y, and Send are correctly located on the phone and
      visibly tapped in order.
- [ ] The physical keyboard remains a separate, stationary device and is never
      used as the phone's input or verification display.
- [ ] The phone target and modeled confirmation state remain on the same phone.
- [ ] READY appears in that phone's message field one character at a time, and
      the same text appears as a sent message after the Send tap, based only on
      the phone's own modeled app state.
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
the system plans it, and a single recognizable machine opens an app, types a
message on the phone's own on-screen keyboard, and sends it. The compatibility
payoff makes clear that physical keyboards and phones use the same semantic
intent contract but retain separate device-specific target maps, controls, and
verification. The result is more dynamic, more legible, and more faithful to
the project's intended architecture.
