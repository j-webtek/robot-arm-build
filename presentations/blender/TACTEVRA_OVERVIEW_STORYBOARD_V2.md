# Tactevra overview film — storyboard v2.1

- **Status:** production plan with Blender framework and first-contact benchmark;
  full sequence not yet rendered
- **Runtime:** exactly 100 seconds
- **Format:** 16:9 master, 24 fps
- **Audience:** technical buyers, collaborators, and first-time GitHub visitors
- **Demonstration:** type lowercase `ready` into the operator display's local test
  pad, then separately enter lowercase `on my way` in the phone's Messages app
  and tap Send.
- **Evidence boundary:** every physical action shown is a workcell simulation until
  separately supported by physical qualification records.
- **Toolhead:** one continuous RoArm gripper carries the repository's controlled
  compliant body, keyed cap, split collar, two M3 retainers, and one nominal
  OASO-style capacitive stylus. Printed-part shapes are source-accurate;
  installed fit, protrusion, force, compliance, and TCP remain unmeasured.

## Product truth this film must preserve

The model does not drive motors. It identifies the requested action, names the
target and proposed coordinate frame, and supplies confidence plus bounded
uncertainty. The deterministic runtime owns transforms, reachability, collision
screening, speed, acceleration, contact depth, settling, retries, timing,
encoding, and verification.

The runtime may admit the static facts of an ordered batch, but physical
authority is always short-lived and always limited to **one contact**. Before
each press or tap, it rechecks the relevant state, grants one green permit,
consumes that permit on contact, observes the effect, and only then may
authorize the next action. A dotted next-target preview has zero authority.

The public stage vocabulary is:

`UNDERSTAND → LOCATE → CHECK → ACT → VERIFY`

## Operator-display decision

The **operator display is a presentation-only floating request and test-pad
surface**. It sits to the left of and fully outside the measured board, so it does not
cover localization tag T2, enter the arm workspace, or appear in the overhead
Locate view. This adds no fictional hardware to the board. Its UI changes from
the opening request console to a dedicated local test-pad panel before typing
begins. The phone remains an
independent target with its own screen, state machine, coordinate map, and
verification evidence.

The local test pad accepts `[a-z]{1,8}`. The film therefore types `ready`, not
`READY`; uppercase would require a Shift interaction that this demonstration
does not perform.

## Story and visual language

One natural-language request becomes two independently checked physical
outcomes. A stale scene fails closed. Fresh evidence permits one action at a
time. The first key is deliberately slow and teaches the control loop; the next
four create a measured rhythm; the phone sequence restores explicit screen
checks; Send slows down for the final commitment.

Three recurring graphics teach authority during the first contact:

1. **Green permit token** — travels from the runtime card down the arm, lands
   at the stylus, authorizes exactly one contact, then fades on use.
2. **Blue uncertainty disk** — surrounds the proposed target and shrinks only
   when current evidence brings the full error bound inside that target.
3. **Dotted target ghost** — previews the next key with the fixed label
   `preview · no authority`; it becomes solid only when its own permit arrives.

Color ownership is strict: amber is model proposal, blue is measured geometry
and uncertainty, red is rejection, green is permit or verified result, and
white/grey is explanation or locked runtime policy.

After scene 8 has taught the full loop, later contacts use only the green
one-contact permit and a compact verification tick. The blue uncertainty disk
and dotted preview do not repeat on every press. Phone state text is likewise
shown in full once, then reduced to check ticks. This preserves the contract
without asking the viewer to relearn it ten times.

## Shot palette and transition rules

- Macro for the cold open and brief evidence inserts.
- Low three-quarter for mechanism and contact readability.
- Lateral track for keyboard rhythm.
- Arm-follow dolly for the cross-workcell move.
- Overhead only as the fixed camera's own view during `LOCATE`.
- Split screens may place a physical cause beside its own observed effect, or
  compare two independent receipts. They never imply a data connection between
  the keyboard/operator-display workflow and the phone workflow.
- Hero wide or crane for architecture and payoff.
- Cumulative use of any reusable camera setup stays at or below 25 percent of
  runtime: macro 16.8%, hero 22%, dolly 21%, arm-follow 21%, overhead 7%, and
  low three-quarter 12.2%. This includes the bounded scene-7 toolhead and
  scene-8 contact inserts and is validated from the canonical shot list.
- Cuts preserve identical joint pose, gripper, printed cartridge, stylus pose,
  cable state, and device placement. No teleporting, snap zooms, or decorative
  spins.
- The stale-evidence rejection cuts the music and holds the arm completely
  still. The next transition pushes toward the stylus as the permit token lands.

## Exact 17-scene board

| # | Time | Stage | Picture, motion, and required information | Sound |
|---:|---:|---|---|---|
| 1 | 0:00–0:04 | — | **Cold open.** Macro: the capacitive disc hovers over the `r` key while the source-accurate printed cartridge remains visibly captured between both jaw pads. The blue uncertainty disk is still wider than the key. Pull focus from disc to keyed cap and stationary wrist. No text appears yet. | One held mechanical tone; no narration. |
| 2 | 0:04–0:09 | — | Operator-display request console: `Type ready locally, then send on my way from the phone.` Phone and physical keyboard remain visibly separate. | Quiet input ticks. |
| 3 | 0:09–0:15 | — | Hero wide reveals the exact workcell, detailed RoArm, printed contact cartridge and stylus, off-board operator display, black RC03 keyboard, and indexed phone. The display remains entirely beside the board. The RC03 cable exits the board on the display side and continues off-frame; no direct hardware connection is claimed. | Music establishes restrained forward pulse. |
| 4 | 0:15–0:21 | `UNDERSTAND` | Amber model card: ordered semantic actions, named targets, board-frame points, confidence, and error bounds. `speed`, `contact depth`, `retry`, and `timing` are greyed and locked: `runtime owned`. | Amber data ticks. |
| 5 | 0:21–0:28 | `LOCATE` | Crane to the actual fixed camera, pass through its lens, then use its squared overhead view. Exact tags and device bounds lock; blue uncertainty disks contract. | Registration pings. |
| 6 | 0:28–0:33 | `CHECK` | Red card in empty space: `scene capture 41 s old · limit 2 s → REJECTED · NO MOTION`. Arm and stylus remain unobscured and still. | Music drops out; one low reject thud. |
| 7 | 0:33–0:40 | `CHECK` | Fresh capture. Immutable batch facts pass. Text reads `BATCH ADMITTED → PERMIT · 1 ACTION`. In a low three-quarter push, establish opposing jaw pads on the body's grip-flat band, the keyed cap and two M3 heads, on-axis barrel, and articulated disc while the green permit travels toward the stylus. End with a rack focus to the off-board operator display as its screen changes from request console to local test pad. | Music returns; restrained gate ticks. |
| 8 | 0:40–0:48 | `ACT` | **Teach the first key slowly with the complete arm readable in low three-quarter.** Label the seven phases: `transit → align → settle → approach → contact → retract → verify`. At contact only, cut briefly to a macro insert of `r` depressing, then return to low three-quarter. A cause/effect insert shows the operator-display test pad add `r`, and the permit fades. The stage bar remains on `ACT`; a small three-dot loop indicator pulses through check/contact/verify. | One precise click and one verify tick. |
| 9 | 0:48–0:55 | `ACT` | Lateral track across `e`, `a`, `d`, `y`. The contract is now visual shorthand: one permit arrives, one contact occurs, and one verification tick appears. Do not repeat uncertainty and dotted-preview graphics. The stage bar remains stable on `ACT`. | Four increasingly rhythmic clicks, never rushed. |
| 10 | 0:55–1:01 | `ACT` | Hold above keyboard. Operator-display test pad reads `ready`; receipt shows `EXPECTED ready · OBSERVED ready ✓`. Phone is unchanged. The stable `ACT` bar remains while the compact loop indicator resolves on verify. | Local verification tone. |
| 11 | 1:01–1:07 | `ACT` | Arm-follow dolly: full retract and high-clearance move from keyboard to phone, with continuous joint and cable motion. | Light transit mechanism texture. |
| 12 | 1:07–1:14 | `ACT` | Show `EXPECTED home · OBSERVED home ✓` in full once. One permit authorizes the Messages-app tap. The app changes to a portrait conversation with contact header, two prior message bubbles, a composer immediately above the software keyboard, and Send fixed at the composer's right edge. The arm retracts and a fresh observation verifies `composer ready`. Later checks reduce to ticks; the stage bar remains on `ACT`. | State-check tick, glass tap, second check tick. |
| 13 | 1:14–1:22 | `ACT` | `on my way` builds inside the lower composer while the existing conversation remains above it. Show `o` and `n` at natural pace with one permit and one tick each. Then display an honest `2×` badge and time-compress the remaining seven contacts. Each visible character still appears only after its own observed contact. | Two measured taps, then a controlled faster rhythm with quiet check ticks. |
| 14 | 1:22–1:27 | `ACT` | Slow down. Confirm the lower composer contains `on my way`. Its adjacent Send control receives a separate green one-contact permit; one tap occurs, the arm retracts, and the text moves into a right-aligned outgoing conversation bubble with `Sent ✓`. Keep the stage bar on `ACT`. | Bed narrows; one distinct Send tap. |
| 15 | 1:27–1:33 | `VERIFY` | Split screen: operator display independently shows `ready ✓`; phone independently shows `on my way · sent ✓`. No visual data line joins the devices. | Two verification tones, left then right. |
| 16 | 1:33–1:36 | — | One compact evidence line only: five green ticks for `UNDERSTAND · LOCATE · CHECK · ACT · VERIFY`, with `Every contact permitted. Every effect verified.` beneath it. | Restrained resolving rise. |
| 17 | 1:36–1:40 | — | Hero wide and Tactevra logo. Show only `Physical intelligence, checked.` plus the small persistent qualifier `SIMULATED WORKCELL SEQUENCE`. | Clean brand resolve; no black tail. |

The scene durations total exactly 100 seconds.

## Production implementation checkpoint

The timing plan is mirrored in `storyboard_v21_shots.json` and validated as 17
contiguous scenes across exactly 2,400 frames. The editable Blender scaffold
creates six reusable shot rigs, timeline camera bindings, locked reference
asset collections, and the three recurring authority graphics. The lowercase
`r` contact is implemented as the first visual benchmark at 0:40–0:48. The
scene-7 scaffold now includes a bounded toolhead macro and an animated depth-of-
field pull to a presentation-only operator display; that display is narrative
context, not a measured RC03 board interface. Its UI is stateful rather
than baked: request console in scene 2, empty test pad at the end of scene 7,
then `r → re → rea → read → ready` after the corresponding observed
contacts. The
same detailed rig then moves continuously through independently permitted
`e`, `a`, `d`, and `y` cycles at 0:48–0:55; no model or pose swap is used. The
contact-free scene-11 crossing is also blocked: the wrist retracts, traverses
a high corridor, and finishes above the measured phone center while the
arm-follow camera moves with it. Scenes 12–14 now continue on that same rig
through a fully checked Messages-app contact, nine independently permitted
lowercase `on my way` contacts, and a separate, slower Send permit. The first
two characters play at natural pace; the remaining seven carry a visible `2×`
badge. The modeled Messages UI fits the measured glass, shows each observed
composer prefix, and ends on a device-local sent receipt.

Run `python presentations/blender/validate_storyboard_v21.py`, then build the
local benchmark with the Blender command documented in `README.md` using the
`--preview-benchmark` option. Generated `.blend` and PNG output remains under
`tmp/` and is not a source artifact or physical qualification record.

## Narration script

Approximately 140 words; leave the action sounds exposed where marked.

```text
[0:04] Ask for an outcome, and Tactevra turns language into named physical targets.
[0:09] When AI acts in the physical world, a guess becomes motion.
       But a proposal is not permission to move.
[0:15] The model says what to touch and how sure it is.
       Speed, force, and timing stay locked to the runtime.
[0:21] A fixed camera locates each device in the measured workcell.
[0:28] Stale evidence fails closed. Nothing moves.
[0:33] Fresh evidence can admit the plan, but authority stays narrow: one permit, one contact.
[0:40] Transit. Align. Settle. Approach. Contact. Retract. Verify.
[0:48] [No narration. Let four key cycles establish the rhythm.]
[0:55] The local result is observed before the workflow continues.
[1:01] The arm clears the keyboard and crosses to a separate phone interface.
[1:07] Before every tap, Tactevra checks the expected screen; after change, it checks again.
[1:14] [No narration. Let the phone-entry rhythm play.]
[1:22] Send receives its own final permit.
[1:27] Two interfaces. Two independent receipts.
[1:33] Every contact permitted. Every effect verified.
[1:36] Tactevra. Physical intelligence, checked.
```

## Contact choreography

Every keyboard press and phone tap uses the same authority and motion cycle:

1. Transit only in a cleared corridor.
2. Align to the named target and interaction normal.
3. Settle while current evidence is checked.
4. Grant a short-lived permit for that single action.
5. Approach using runtime-owned dynamics and contact depth.
6. Contact once; consume the permit immediately.
7. Retract and observe the device-local effect before considering the next
   dotted preview.

No automatic retry follows a possible or ambiguous contact. Ambiguity returns
to `CHECK` and holds position safely.

For phone actions, verify the required screen before each tap. Any state change
invalidates the prior screen evidence and requires a fresh observation before
the next action.

## Mandatory continuity

1. One detailed servo-style RoArm mesh and rig in every physical shot.
2. One controlled printed cartridge visibly captured at its grip-flat band by
   the same opposing jaw pads throughout. Its keyed cap and two M3 heads never
   change or disappear.
3. One nominal 9 mm OASO-style stylus remains on the cartridge axis with the
   same exposed length, collar, pivot, and capacitive disc throughout.
4. One immutable workcell: board, robot, camera, keyboard, phone, fixtures,
   tags, cables, operator display, and transforms do not drift.
5. One measured black RC03 keyboard with correct legends, proportions, cable,
   protective rear film, and individually animatable `r/e/a/d/y` keys.
6. One measured dark phone with consistent chassis, glass, camera, controls,
   station, cable, and modeled app states.
7. The presentation-only operator display is the request console and local
   test-pad surface. It remains fully outside the board and overhead Locate
   view, and is never confused with the phone. The RC03 cable leaves the board
   on the display side and ends off-frame; the film does not claim a direct
   physical connection.
8. Keyboard actions affect only the operator-display test pad. Phone taps affect only the
   phone.
9. Lowercase copy remains lowercase in request, proposal, screens, captions,
   receipts, and narration.
10. A preview is always dotted and always labeled `no authority`; only an active
   green permit may become solid.
11. No overlay covers the robot, cartridge, stylus, gripper, target, or contact point.
12. Every cut preserves outgoing and incoming joint, cartridge, stylus, and cable pose.
13. `SIMULATED WORKCELL SEQUENCE` persists throughout rendered physical action.
14. The visible arm always uses the same five-stage presentation chain:
    base yaw, shoulder pitch, elbow, wrist pitch, and tool wrist. The fixed
    lower chassis exposes the controller board and standoffs beneath the
    rotating yaw deck. The elbow servo remains on
    the upper link, the wrist-pitch servo remains on the forearm, and the tool
    wrist servo remains on the short wrist link.
15. Link endpoints remain joined at their servo pivots through interpolation;
    no rail may stretch, detach, or slide through its housing. The terminal
    tool frame counter-rotates so the stylus stays vertical to the board during
    keyboard and phone contact scenes. A contact descent is solved through the
    whole chain; the toolhead never translates independently of its wrist.

## Asset and production requirements

| Asset | Required condition |
|---|---|
| Robot | Detailed RoArm geometry with an open controller chassis, rotating base-yaw deck, and one parented base-yaw–shoulder-pitch–elbow–wrist-pitch–tool-wrist chain; correctly mounted servo housings, dual links, short wrist link, fasteners, segmented wiring, gripper, and one articulated rig used in all scenes. |
| Gripper/tool mount | Same RoArm jaw architecture in every moving shot. Opposing pads contact the controlled 28 × 24 × 65 mm compliant body at its recessed grip band; keyed cap, split collar, and two M3 retainers use the repository STLs. |
| Stylus | Nominal 9 mm OASO-style aluminum barrel running through the printed cartridge, with constant protrusion and an articulated capacitive contact disc. Installed dimensions remain explicitly unmeasured. |
| Keyboard | Measured black RC03 asset, correct six-row layout and legends, animated lowercase target keys, associated only with the operator-display test pad. Its cable exits toward the display side and ends off-frame. |
| Operator display | Presentation-only floating screen with distinct request-console and local-test-pad UI modes; displays `ready` only after physical keyboard presses. It does not overlap the board or appear in the overhead Locate view. |
| Phone | Measured phone/station asset with home, Messages composer, keyboard, Send, and sent-confirmation states; all UI labeled as modeled. |
| Camera | Recognizable physical camera body, mount, lens, and matching overhead optical view. |
| Board | Exact released dimensions, tag36h11 IDs, indexed transforms, fixtures, and cable paths. |

Six new art-direction stills precede animation: cold-open macro, locked model
proposal, physical-camera POV, permit landing on stylus, arm-follow crossing,
and dual-receipt hero. Existing overhead composites remain geometry references,
not substitutes for this shot palette.

Maintain an audible music bed about 15–18 dB under speech, cut it for rejection,
and use meaning-coded effects rather than a whoosh on every edit. Deliver a
1920×1080 master, web-optimized GitHub version, captions, poster, and a separate
30-second social cut.

The 30-second cut is not improvised. Use these named beats in order:
`S01 cold-open-r-hover`, `S02 operator-request`, `S06 stale-evidence-reject`,
`S08 r-contact-benchmark`, `S11 keyboard-to-phone-crossing`,
`S14 phone-send-permit`, `S15 independent-receipts`, and `S17 brand-resolve`.

## Production gates

- [ ] Greybox communicates the complete story without narration and at 390 px width.
- [ ] Timings total exactly 100 seconds and all 17 scenes are present.
- [ ] Operator display visibly serves as the local test-pad surface, remains off-board, and never obscures a localization tag.
- [ ] All typed strings are lowercase and the local string is at most eight characters.
- [ ] Model card contains only model-owned outputs; runtime-owned fields are visibly locked.
- [ ] Static batch admission is never depicted as physical authority for the full route.
- [ ] Every contact receives, consumes, and clears exactly one permit.
- [ ] Every phone tap begins from a verified expected screen; state changes force re-observation.
- [ ] Scene 13 shows two natural-speed contacts before a visible `2×` badge appears.
- [ ] Stage labels begin with scene 4 and remain stable on `ACT` through scenes 8–14.
- [ ] Blue uncertainty is fully inside a target before its permit becomes active.
- [ ] Dotted previews remain zero-authority until promoted by their own permit.
- [ ] Accurate robot, stylus, keyboard, phone, camera, board, and transforms persist across all cuts.
- [ ] The printed cartridge, keyed cap, M3 retainers, collar, stylus, pivot, and
      contact disc remain one continuous toolhead with no asset swap.
- [ ] Local and phone observations remain independent through final receipts.
- [ ] README player, captions, transcript, chapters, poster, and social cut use this vocabulary and timing.
- [ ] Simulation qualification remains visible and no rendered action is presented as physical evidence.
