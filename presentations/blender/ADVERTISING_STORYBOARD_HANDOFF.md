# Tactevra advertising storyboard handoff — v2.1

- **Purpose:** art-direction and motion-production brief
- **Runtime:** exactly 100 seconds, 17 scenes, 16:9, 24 fps
- **Status:** concept package; visuals are not engineering evidence

## Campaign idea

A request becomes two independently verified physical outcomes. Tactevra types
`ready` into a local test pad through the real black keyboard, then crosses the
same measured workcell and enters `on my way` on the phone before tapping Send.
The audience sees the boundary between a model proposal and physical authority.

The presentation-only floating operator display is both the opening request
console and the local test-pad surface. It sits left of and fully outside the measured
board; its two UI modes must look unmistakably different. The phone is a separate
target device and never acts as keyboard feedback.

## Product behavior the creative must preserve

The model supplies ordered semantic actions, named targets, proposed
coordinates, confidence, and bounded uncertainty. It does **not** supply joint
commands, speed, acceleration, contact depth, timing, retry policy, or authority.
Those are deterministic runtime responsibilities and appear greyed out and
locked on the amber proposal card.

The runtime may admit immutable batch facts once, but each press or tap requires
its own short-lived permit. It checks current state, grants one permit, consumes
it on one contact, observes the effect, and only then considers the next action.
The phone's expected screen is checked before every tap and re-observed after a
state change.

Public stages: `UNDERSTAND → LOCATE → CHECK → ACT → VERIFY`.

## Recurring visual system

1. A **green permit token** travels down the arm, authorizes one contact, and
   fades when consumed.
2. A **blue uncertainty circle** contracts until its complete bound fits inside
   the intended key or control.
3. A **dotted target ghost** is always labeled `preview · no authority`; it
   becomes solid only when its own permit arrives.

Amber belongs to model output, blue to measured geometry, red to rejection,
green to permit or verified outcome, and grey to explanation or locked runtime
policy.

## Hardware and layout authority

| Asset | Production authority |
|---|---|
| Board | 610 × 457 × 18 mm RC03 board from `dimension_manifest.json` |
| Keyboard | Measured 315 × 147 × 21 mm black RC03 chassis, six-row layout, legends, cable, and station |
| Phone | Measured 77.9 × 164.4 × 7.9 mm body, screen plane, controls, cable, and RC03 station |
| Robot | Detailed RoArm source geometry and servo rig; rear-center placement at 305, 457, 0 mm and −90° nominal yaw |
| Printed tool mount | Controlled 28 × 24 × 65 mm compliant-body STL, keyed-cap STL, split-collar STL, two visible M3 retainers, and grip-flat contact between the same opposing RoArm jaw pads |
| Stylus | One nominal 9 mm OASO-style aluminum barrel, constant protrusion, pivot, and capacitive disc carried by the printed cartridge throughout |
| Camera | Actual fixed-camera body, mount, lens, and matching optical view |
| Operator display | Presentation-only floating screen beside and fully outside the board; request-console and local-test-pad UI; visually independent from the phone and excluded from the overhead Locate view |

Existing images under `storyboard_v2/` are **geometry references only**. Their
device footprints and board relationships are authoritative; their overhead
framing is not final art direction.

## Six new art-direction anchors

### A. Cold-open authority macro

The capacitive disc hovers over lowercase `r`. The blue uncertainty disk is too
wide and the next target is dotted. Show enough of the real servo wrist,
opposing jaw pads, recessed grip-flat band, keyed cap, two M3 heads, and keyboard
to identify the complete tool stack. Do not add text before the viewer learns
what a permit is.

**Camera:** 85–100 mm equivalent; focus pull from key to wrist.

### B. Model proposal with locked policy

Low three-quarter hero of the stationary workcell. Amber card identifies
`keyboard.type "ready"` and `phone.send "on my way"`, named targets,
confidence, and error bounds. Grey locked rows read `runtime owned` for speed,
contact, retry, and timing.

**Camera:** 40–50 mm equivalent; restrained push; card in negative space.

### C. The camera's own view

Show the recognizable fixed camera and lens, then pass through it into a
squared optical view. Blue outlines register the real board, devices, tags,
and uncertainty. Overhead appears nowhere else except this locate sequence and
the stale-evidence hold.

### D. Permit lands on the secured toolhead

Fresh evidence admits static batch facts, but the graphic reads
`BATCH ADMITTED → PERMIT · 1 ACTION`. A green token travels down the actual arm
and lands at the keyed cartridge/stylus assembly while `r` becomes solid. The
next `e` remains dotted and powerless. The push-in should reveal that the jaws
hold the printed body—not the barrel—and that the cap positively retains the
stylus route.

**Camera:** low three-quarter, 55–70 mm, slow push timed to token arrival.

### E. Arm-follow crossing

After the operator-display receipt `ready ✓`, follow the full arm through a high-clearance
arc from keyboard to phone. Preserve the same stylus, cable state, and rig; keep
both devices visible long enough to retain spatial understanding.

### F. Independent receipts hero

Balanced split evidence inside a hero wide: operator-display test pad reads `ready ✓`;
the actual phone reads `on my way · sent ✓`. The retracted arm sits between the
devices without visually connecting their data.

## Exact 17-scene director board

| # | Time | Stage | Required picture and action | Sound |
|---:|---:|---|---|---|
| 1 | 0:00–0:04 | — | Macro over `r`; disc, printed cartridge, jaw pads, keyed cap, and M3 heads readable; uncertainty too wide; no text. | Held mechanism tone. |
| 2 | 0:04–0:09 | — | Operator-display request close-up: `Type ready locally, then send on my way from the phone.` | Input ticks. |
| 3 | 0:09–0:15 | — | Hero wide of exact workcell and one detailed arm/stylus rig. Operator display is beside—not over—the board; keyboard cable exits toward it and ends off-frame. | Music pulse begins. |
| 4 | 0:15–0:21 | UNDERSTAND | Amber semantic proposal; confidence and uncertainty visible; runtime fields locked. | Data ticks. |
| 5 | 0:21–0:28 | LOCATE | Reveal real camera, pass through lens, register exact device geometry; blue circles shrink. | Registration pings. |
| 6 | 0:28–0:33 | CHECK | `scene capture 41 s old · limit 2 s → REJECTED · NO MOTION`; arm visible and still. | Music cuts; reject thud. |
| 7 | 0:33–0:40 | CHECK | Fresh capture; `BATCH ADMITTED → PERMIT · 1 ACTION`; a low three-quarter push establishes the complete toolhead while the token travels to the stylus. | Music returns; gate ticks. |
| 8 | 0:40–0:48 | ACT | Keep the complete arm readable in low three-quarter while the first `r` press teaches transit, align, settle, approach, contact, retract, verify. Use macro only as a brief insert of the key depressing, then return. Permit fades; operator display shows `r`. | One key click, one verify tick. |
| 9 | 0:48–0:55 | ACT | Lateral track through `e/a/d/y`; use only one permit and one receipt tick per contact after the lesson. | Four rhythmic key clicks. |
| 10 | 0:55–1:01 | ACT | Operator-display test pad: `EXPECTED ready · OBSERVED ready ✓`; phone unchanged. | Verify tone. |
| 11 | 1:01–1:07 | ACT | Full retract and continuous high-clearance arm-follow move to phone. | Transit texture. |
| 12 | 1:07–1:14 | ACT | Check `home`; one permit opens Messages; re-observe and verify `composer ready`. | Check, tap, check. |
| 13 | 1:14–1:22 | ACT | Build `on my way`; show `o` and `n` naturally, then disclose `2×` for the remaining contacts; every visible character follows its own observed contact. | Two measured taps, then controlled faster rhythm. |
| 14 | 1:22–1:27 | ACT | Confirm composer; Send receives its own permit; one tap and retract; outgoing bubble reads `Sent ✓`. | Distinct Send tap. |
| 15 | 1:27–1:33 | VERIFY | Split evidence: operator display `ready ✓`; phone `on my way · sent ✓`. | Two verify tones. |
| 16 | 1:33–1:36 | — | Five compact green ticks with `Every contact permitted. Every effect verified.` | Resolving rise. |
| 17 | 1:36–1:40 | — | Hero wide, Tactevra logo, `Physical intelligence, checked.`, and `SIMULATED WORKCELL SEQUENCE`. | Clean resolve; no black tail. |

## Shot and editorial rules

- Cumulative use of any reusable camera setup stays at or below 25 percent:
  macro 16.8%, hero 22%, dolly 21%, arm-follow 21%, overhead 7%, and low
  three-quarter 12.2%. These shares include the bounded scene-7 toolhead and
  scene-8 contact inserts; the canonical shot-list validator enforces them.
- Use macro, low three-quarter, lateral track, arm-follow dolly, camera POV,
  split screen, and hero wide for narrative reasons—not decorative variety.
- Preserve exact joint, gripper, printed cartridge, stylus, cable, keyboard,
  phone, and fixture continuity.
- One principal card plus the stage ribbon is the maximum information load.
- Keep cards in negative space and never over the mechanism or target.
- Music sits 15–18 dB below narration and cuts completely for rejection.
- Test every graphic at 390 px width before final lighting.

## Non-negotiable copy and behavior

- Use lowercase `ready` and `on my way` everywhere; uppercase requires actions
  outside this demonstration.
- The presentation-only operator display—not an invented board display—shows
  the local test pad. It remains fully outside the board and overhead Locate view.
- The RC03 keyboard cable exits the board toward the operator-display side and
  ends off-frame; do not imply a direct connection that the film has not established.
- `BATCH ADMITTED` never means route-wide contact authority.
- Every contact gets and consumes exactly one green permit.
- The next target is dotted and marked `preview · no authority`.
- Every phone tap begins from a verified expected screen; changed screens force
  re-observation.
- Model-owned fields are amber; runtime-owned policy fields are grey and locked.
- The accurate RoArm, same jaw pair, same printed cartridge, and same stylus
  perform every physical action.
- The black keyboard and dark phone never change appearance or placement.
- Physical animation carries `SIMULATED WORKCELL SEQUENCE` throughout.

## Geometry-reference images

- `storyboard_v2/01-intent-hero-layout-accurate.jpg`
- `storyboard_v2/02-device-maps-layout-accurate.jpg`
- `storyboard_v2/03-stale-evidence-reject-layout-accurate.jpg`
- `storyboard_v2/04-local-keyboard-action-layout-accurate.jpg`
- `storyboard_v2/05-phone-action-layout-accurate.jpg`
- `storyboard_v2/06-dual-verification-layout-accurate.jpg`

## Requested advertising deliverables

1. Six new style frames matching anchors A–F while preserving measured layout.
2. A 100-second greybox animatic using all 17 timed scenes.
3. Two alternate treatments for the first-key lesson, crossing shot, and Send.
4. Motion tests for permit token, uncertainty circle, and no-authority ghost.
5. Typography and graphics at desktop and 390 px widths.
6. Sound concept for rejection, permits, keys, phone checks, Send, and receipts.
7. Poster, GitHub player thumbnail, and separately captioned 30-second social cut.
8. Continuity report confirming one robot, one printed cartridge/tool stack,
   one stylus, measured layout,
   lowercase copy, per-contact authority, and device-local verification.

## Review questions

- Can a viewer explain the difference between proposal and permit?
- Is it obvious that one permit authorizes exactly one contact?
- Does the operator display read as the local test-pad surface and the phone as a separate
  physical interface?
- Can the stale rejection be understood with sound off?
- Does every phone tap visibly originate from a verified screen state?
- Does the film remain clear and engaging on a phone-sized GitHub preview?
