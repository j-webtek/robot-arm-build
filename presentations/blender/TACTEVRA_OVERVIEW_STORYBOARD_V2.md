# Tactevra overview film — story and storyboard v2

- **Status:** Production plan; not yet rendered
- **Target runtime:** exactly 100 seconds
- **Audience:** Technical buyers, collaborators, and first-time GitHub visitors
- **Central demonstration:** A user asks Tactevra to enter `READY` in a local
  computer interface, then send `ON MY WAY` as a phone message. The system types
  the local input through the physical keyboard, verifies that local result,
  then separately operates the phone's Messages app through physical screen
  taps and verifies the sent message. The two devices never share an input,
  display, or verification path.
- **Evidence boundary:** Every physical action in this film is a presentation
  visualization until separately supported by physical qualification records.

## The new story

The film must feel like a complete transaction rather than a component tour.
It begins with a human objective, not a servo command. Tactevra turns that
objective into named actions, grounds them in the measured workcell, checks the
whole route, and then carries out two visible device-local routines: physical
keyboard input to the local computer, followed by physical touchscreen taps on
the phone. The same servo-style RoArm and the same clamped stylus remain on
screen throughout the physical sequence.

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
| 1 | 0:00–0:05 | — | **The ask** | Start on an unmistakable operator console. The AI request appears in its own panel, visually separate from both target interfaces. | `Enter READY locally, then text ON MY WAY from the phone.` |
| 2 | 0:05–0:11 | — | **The physical stakes** | Match-cut to the hero wide and orbit 12–15 degrees. The detailed arm is parked and its stylus is visibly clamped. The physical keyboard, local-computer display, and phone are all legible as separate objects. | No caption; let the narration explain that a guess becomes motion. |
| 3 | 0:11–0:18 | `1 · UNDERSTAND` | **Model proposal** | An amber proposal card appears beside the stationary workcell. The request becomes two ordered, device-qualified intentions. | `LOCAL.TYPE_TEXT "READY" → PHONE.SEND_TEXT "ON MY WAY"`; `frame board`; `confidence 0.96`; no joint angles. |
| 4 | 0:18–0:25 | `2 · LOCATE` | **See the scene** | Crane to the fixed camera, pass through its lens, and settle into a square overhead view. Exact board tags pulse and independent device outlines lock. | `local keyboard found`; `local display found`; `phone found`; capture-quality indicators. |
| 5 | 0:25–0:31 | `2 · LOCATE` | **Resolve independent targets** | Use two clearly separated blue target maps. The local branch highlights physical R/E/A/D/Y keys and the local input field. The phone branch highlights Messages, the on-screen targets needed for `ON MY WAY`, and Send. No line connects one device's output to the other. | `local input · physical keyboard`; `message · phone touchscreen`; declared frames and uncertainty. |
| 6 | 0:31–0:37 | `3 · CHECK` | **Reject stale evidence** | A red card occupies empty frame space while the arm remains visibly still. | `scene capture 41 s old`; `limit 2 s`; `REJECTED · NO MOTION`. |
| 7 | 0:37–0:44 | `3 · CHECK` | **Admit both device-local routines** | A fresh capture arrives. The compiled route draws park → local R/E/A/D/Y → verify local → Messages → phone `ON MY WAY` → Send → verify phone. Gates tick and the decision turns green. | `device · app state · frame · freshness · reach · clearance · order · speed`; `2 INTENTS · 15 CONTACTS ADMITTED`. |
| 8 | 0:44–0:50 | `4 · ACT` | **Transit to physical keyboard** | One continuous medium-wide: the detailed arm leaves park and reaches the physical keyboard hover plane. | Small persistent corner tag begins: `SIMULATED WORKCELL SEQUENCE`. |
| 9 | 0:50–1:00 | `4 · ACT` | **Enter READY locally** | Track with the whole arm for five visible physical-key presses. R/E/A/D/Y appear only in the local computer's input field. The phone remains unchanged. | `LOCAL · R ✓  E ✓  A ✓  D ✓  Y ✓`; green plus checks. |
| 10 | 1:00–1:05 | `5 · VERIFY` | **Verify local input** | The arm holds above the keyboard. The local display reads `READY`; local input observation and telemetry agree. | `LOCAL EXPECTED: READY`; `LOCAL OBSERVED: READY ✓`; phone unchanged. |
| 11 | 1:05–1:11 | `4 · ACT` | **Cross to the phone** | Wide diagonal dolly follows a high-clearance arc away from the keyboard and toward the phone while the wrist reorients. | Route progress: `local keyboard complete → phone`. |
| 12 | 1:11–1:23 | `4 · ACT` | **Compose the phone message** | The same arm taps Messages, then physically taps the phone's on-screen keys for `ON MY WAY`. Each character appears only in the phone's message field. Use no more than two brief contact inserts. | `PHONE · Messages ✓ · ON MY WAY`; compiled contacts 6–14 of 15. |
| 13 | 1:23–1:28 | `4 · ACT` | **Tap Send** | Start medium-wide; use a contact macro no longer than two seconds. The same stylus taps Send once and retracts. | `PHONE.SEND_TEXT · CONTACT 15 OF 15`. |
| 14 | 1:28–1:35 | `5 · VERIFY` | **Verify both outcomes** | The local display still shows its independent local `READY`. Separately, the phone moves `ON MY WAY` into a sent message bubble. Two receipts resolve side by side without sharing data. | `LOCAL INPUT: READY ✓`; `PHONE MESSAGE: ON MY WAY · SENT ✓`; telemetry and observation ✓. |
| 15 | 1:35–1:40 | all | **Compatibility payoff and end card** | Pull back while `UNDERSTAND → LOCATE → CHECK → ACT → VERIFY` lights in order. The two device branches remain separate beneath one intent contract, then resolve into the logo and URL. No black tail. | `ONE INTENT CONTRACT · TWO DEVICE-SPECIFIC WORKFLOWS`; `TACTEVRA · Physical intelligence, checked.`; small grey boundary line. |

## Draft narration

This approximately 150-word draft deliberately leaves scene 9 open for the
five typing sounds. Read it calmly and precisely; do not use a trailer voice.
The `/` marks a short natural breath.

```text
[0:05] When AI acts in the physical world, a guess becomes motion. /
       So intent can't go straight to the motors.
[0:11] The model proposes two device-qualified intentions: / enter READY
       locally, then send ON MY WAY from the phone. Never joint angles.
[0:18] A fixed camera reads the board's tags / and locates each independent
       device in one shared workcell frame.
[0:25] Each device keeps its own targets, controls, and observed state.
[0:31] If the scene is stale, the plan is rejected. / Nothing moves.
[0:37] With fresh evidence, both routines are checked: / frame, reach,
       clearance, order, speed. / Only then is it admitted.
[0:44] One arm. One stylus. One controller.
[0:50] [No narration. Let the five physical-key clicks carry the sequence.]
[1:00] READY is confirmed in the local interface. / The phone is still unchanged.
[1:05] The arm clears the keyboard and crosses to the separate phone workflow.
[1:11] [No narration. Let the Messages and on-screen-key taps carry the sequence.]
[1:23] One physical tap on Send.
[1:28] The local input remains local. / The phone message is separately
       observed as sent.
[1:35] One intent contract. / Two device-specific workflows. /
       Tactevra. Physical intelligence, checked.
```

## Robot performance choreography

The motion must communicate control quality without pretending that a rendered
trajectory is qualified evidence.

### Local physical-keyboard sequence

1. Leave park with a vertical and rearward clearance move.
2. Travel to the physical keyboard's shared hover plane.
3. For each physical letter key, use
   `hover → controlled descent → visible key travel → retract`.
4. Blend only high-clearance lateral segments; do not round the contact
   descent.
5. Keep the stylus plausibly aligned with the key-normal direction.
6. Hold over the keyboard while the local-computer input field is observed.
7. Do not change any phone state during this sequence.

### Phone sequence

1. Retract completely from the physical keyboard, then travel in a visible
   high-clearance arc that clears the keyboard and fixtures.
2. Reorient the wrist before descending to the phone hover plane.
3. Tap the Messages icon using `hover → controlled descent → retract`, then
   hold while the modeled app transition is observed.
4. For each on-screen letter, repeat the same three-part tap primitive. Blend
   only the high-clearance lateral segments; do not round the contact descent.
5. Keep the stylus axis plausibly aligned with the phone-screen normal.
6. Pause over the phone while `ON MY WAY` and the composer state are checked.
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
- The film animates both selected branches in order, but their target maps,
  interaction state, observations, and verification receipts remain separate.

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
| Keyboard | Current measured black RC03 asset, consistent material in all shots, correct legends and six-row layout, individually animatable R/E/A/D/Y key caps, its own physical-key target map, and a clearly associated local-computer input field. |
| Phone | Current measured phone asset, consistent dark chassis and glass, home, Messages composer, on-screen keyboard, Send, and sent-confirmation states. Screen content is explicitly labeled as modeled UI. `ON MY WAY` appears in this phone's input field through its own on-screen targets. |
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
  fast. The viewer must be able to count five physical-key presses, followed
  later by the Messages tap, the phone-specific `ON MY WAY` entry, and Send.
- Deliver a high-quality 1920×1080 master, a web-optimized GitHub version, and
  captioned social derivatives from the same timeline.
- Build a 30-second social cut from the ask, stale-evidence rejection, one
  physical-key contact, one phone-key contact, dual verification, and end card.
  Give it separate burned-in captions rather than cropping the 100-second
  captions.

## Production checkpoints

The video is ready for final render only when all checkpoints pass.

- [ ] A greybox animatic communicates the full request-to-result story without
      narration.
- [ ] The greybox animatic remains understandable and every principal card is
      readable at a 390-pixel-wide phone preview.
- [ ] The identical robot mesh and rig are present in every physical shot.
- [ ] The stylus is visibly clamped before, during, and after all fifteen
      compiled contacts across the two workflows.
- [ ] Physical R, E, A, D, and Y keys visibly depress in order, and only the
      local computer's input field changes during those contacts.
- [ ] Messages, the `ON MY WAY` on-screen targets, and Send are correctly
      located on the phone and visibly tapped in order.
- [ ] The physical keyboard remains a separate device and is never used as the
      phone's input or verification display.
- [ ] The phone target and modeled confirmation state remain on the same phone.
- [ ] `ON MY WAY` appears in that phone's message field and the same text
      appears as a sent message after the Send tap, based only on the phone's
      own modeled app state.
- [ ] The local `READY` and phone `ON MY WAY` have separate observations and
      separate verification receipts; neither is evidence for the other.
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
the system plans it, and a single recognizable machine first enters local text
through a physical keyboard, then operates a separate phone through physical
screen taps. The compatibility payoff makes clear that both workflows can
share a semantic intent contract while retaining separate device-specific
target maps, controls, state, and verification. The result is more dynamic,
more legible, and more faithful to the project's intended architecture.
