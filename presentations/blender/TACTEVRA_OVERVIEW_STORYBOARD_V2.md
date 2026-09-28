# Tactevra overview film — storyboard v2.1

- **Status:** production plan with Blender framework and first-contact benchmark;
  full sequence not yet rendered
- **Runtime:** exactly 100 seconds
- **Format:** 16:9 master, 24 fps
- **Audience:** technical buyers, collaborators, and first-time GitHub visitors
- **Demonstration:** type lowercase `ready` into the operator laptop's local test
  pad, then separately enter lowercase `on my way` in the phone's Messages app
  and tap Send.
- **Evidence boundary:** every physical action shown is a workcell simulation until
  separately supported by physical qualification records.

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

## Workcell-display decision

The **operator laptop is the local test-pad display**. It is already the host
connected to the physical keyboard, so this choice adds no fictional hardware
to the board. Its UI changes clearly from the opening request console to a
dedicated local test-pad panel before typing begins. The phone remains an
independent target with its own screen, state machine, coordinate map, and
verification evidence.

The local test pad accepts `[a-z]{1,8}`. The film therefore types `ready`, not
`READY`; uppercase would require a Shift interaction that this demonstration
does not perform.

## What changed from v2

| v2 implication | v2.1 correction |
|---|---|
| One approval covers all contacts | Static batch facts may be admitted once; a fresh one-contact permit is required and consumed for every physical contact. |
| Uppercase `READY` / `ON MY WAY` | Use lowercase `ready` and `on my way`; the local test pad supports lowercase letters only, up to eight characters. |
| Phone taps follow a pre-approved route | Verify the expected phone screen before each tap and re-observe after every state-changing action. |
| Model supplies movement behavior | Model supplies target, frame, confidence, and uncertainty; runtime-owned dynamics and retry fields are shown locked. |
| Next target looks executable | The dotted ghost is explicitly labeled `preview · no authority` until its own permit arrives. |

## Story and visual language

One natural-language request becomes two independently checked physical
outcomes. A stale scene fails closed. Fresh evidence permits one action at a
time. The first key is deliberately slow and teaches the control loop; the next
four create a measured rhythm; the phone sequence restores explicit screen
checks; Send slows down for the final commitment.

Three recurring graphics make authority legible:

1. **Green permit token** — travels from the runtime card down the arm, lands
   at the stylus, authorizes exactly one contact, then fades on use.
2. **Blue uncertainty disk** — surrounds the proposed target and shrinks only
   when current evidence brings the full error bound inside that target.
3. **Dotted target ghost** — previews the next key with the fixed label
   `preview · no authority`; it becomes solid only when its own permit arrives.

Color ownership is strict: amber is model proposal, blue is measured geometry
and uncertainty, red is rejection, green is permit or verified result, and
white/grey is explanation or locked runtime policy.

## Shot palette and transition rules

- Macro for the cold open and brief evidence inserts.
- Low three-quarter for mechanism and contact readability.
- Lateral track for keyboard rhythm.
- Arm-follow dolly for the cross-workcell move.
- Overhead only as the fixed camera's own view during `LOCATE`.
- Split screen only for truly independent evidence.
- Hero wide or crane for architecture and payoff.
- No single framing occupies more than about 25 percent of runtime.
- Cuts preserve identical joint pose, stylus pose, cable state, and device
  placement. No teleporting, snap zooms, or decorative spins.
- The stale-evidence rejection cuts the music and holds the arm completely
  still. The next transition pushes toward the stylus as the permit token lands.

## Exact 17-scene board

| # | Time | Stage | Picture, motion, and required information | Sound |
|---:|---:|---|---|---|
| 1 | 0:00–0:04 | — | **Cold open.** Macro: stylus hovering over the `r` key; blue uncertainty disk is still wider than the key. Pull focus to the stationary joints. `NO PERMIT · NO CONTACT`. | One held mechanical tone; no narration. |
| 2 | 0:04–0:09 | `UNDERSTAND` | Operator laptop request console: `Type ready locally, then send on my way from the phone.` Phone and physical keyboard remain visibly separate. | Quiet input ticks. |
| 3 | 0:09–0:15 | — | Hero wide reveals the exact workcell, detailed RoArm, clamped stylus, laptop, black RC03 keyboard, and indexed phone. | Music establishes restrained forward pulse. |
| 4 | 0:15–0:21 | `UNDERSTAND` | Amber model card: ordered semantic actions, named targets, board-frame points, confidence, and error bounds. `speed`, `contact depth`, `retry`, and `timing` are greyed and locked: `runtime owned`. | Amber data ticks. |
| 5 | 0:21–0:28 | `LOCATE` | Crane to the actual fixed camera, pass through its lens, then use its squared overhead view. Exact tags and device bounds lock; blue uncertainty disks contract. | Registration pings. |
| 6 | 0:28–0:33 | `CHECK` | Red card in empty space: `scene capture 41 s old · limit 2 s → REJECTED · NO MOTION`. Arm and stylus remain unobscured and still. | Music drops out; one low reject thud. |
| 7 | 0:33–0:40 | `CHECK` | Fresh capture. Immutable batch facts pass. Text reads `BATCH ADMITTED → PERMIT · 1 ACTION`. A green permit token begins traveling toward the stylus; the next target remains dotted. | Music returns; restrained gate ticks. |
| 8 | 0:40–0:48 | `ACT → VERIFY` | **Teach the first key slowly.** Label all seven phases: `transit → align → settle → approach → contact → retract → verify`. The permit lands, `r` depresses, local test pad shows `r`, permit fades, and only then does the ghost move to `e`. | One precise click and one verify tick. |
| 9 | 0:48–0:55 | `CHECK → ACT → VERIFY` | Lateral track across `e`, `a`, `d`, `y`. Each cycle visibly repeats: uncertainty fits, one permit arrives, one contact occurs, result is observed, permit disappears. The next key is always a dotted preview until authorized. | Four increasingly rhythmic clicks, never rushed. |
| 10 | 0:55–1:01 | `VERIFY` | Hold above keyboard. Laptop test pad reads `ready`; receipt shows `EXPECTED ready · OBSERVED ready ✓`. Phone is unchanged. | Local verification tone. |
| 11 | 1:01–1:07 | `ACT` | Arm-follow dolly: full retract and high-clearance move from keyboard to phone, with continuous joint and cable motion. | Light transit mechanism texture. |
| 12 | 1:07–1:14 | `CHECK → ACT → VERIFY` | Phone screen is checked first: `EXPECTED home · OBSERVED home ✓`. Permit authorizes one Messages tap. App changes, arm retracts, fresh observation verifies `composer ready`. | State-check tick, glass tap, second check tick. |
| 13 | 1:14–1:19 | `CHECK → ACT → VERIFY` | Controlled montage: `on my way` builds in the phone composer. Before every tap the expected screen is checked; each contact consumes one permit; each visible character is confirmed before the next. | Short glass-tap rhythm with quiet check ticks. |
| 14 | 1:19–1:24 | `CHECK → ACT → VERIFY` | Slow down. Confirm composer contains `on my way`; blue Send uncertainty fits; dotted Send ghost becomes solid only when the green one-action permit arrives. One tap, retract, permit fades. | Bed narrows; one distinct Send tap. |
| 15 | 1:24–1:31 | `VERIFY` | Split screen: laptop independently shows `ready ✓`; phone independently shows `on my way · sent ✓`. No visual data line joins the devices. | Two verification tones, left then right. |
| 16 | 1:31–1:36 | all | Evidence trail: request, model proposal, capture IDs, one-action permit receipts, contact observations, and final device-local results align without covering hardware. | Restrained resolving rise. |
| 17 | 1:36–1:40 | all | Hero wide and logo. Stage ribbon lights in order. `ONE INTENT CONTRACT · DEVICE-SPECIFIC CONTROL · ONE CONTACT AT A TIME`. Persistent qualifier: `SIMULATED WORKCELL SEQUENCE`. | Clean brand resolve; no black tail. |

The scene durations total exactly 100 seconds.

## Production implementation checkpoint

The timing plan is mirrored in `storyboard_v21_shots.json` and validated as 17
contiguous scenes across exactly 2,400 frames. The editable Blender scaffold
creates four reusable shot rigs, timeline camera bindings, locked reference
asset collections, and the three recurring authority graphics. The lowercase
`r` contact is implemented as the first visual benchmark at 0:40–0:48. The
same detailed rig then moves continuously through independently permitted
`e`, `a`, `d`, and `y` cycles at 0:48–0:55; no model or pose swap is used. The
contact-free scene-11 crossing is also blocked: the wrist retracts, traverses
a high corridor, and finishes above the measured phone center while the
arm-follow camera moves with it.

Run `python presentations/blender/validate_storyboard_v21.py`, then build the
local benchmark with the Blender command documented in `README.md` using the
`--preview-benchmark` option. Generated `.blend` and PNG output remains under
`tmp/` and is not a source artifact or physical qualification record.

## Narration script

Approximately 140 words; leave the action sounds exposed where marked.

```text
[0:04] Ask for an outcome, and Tactevra turns language into named physical targets.
[0:09] But a proposal is not permission to move.
[0:15] The model supplies what to touch, where it is, and how uncertain that estimate is.
       Speed, contact, timing, and retries remain locked to the runtime.
[0:21] A fixed camera locates each device in the measured workcell.
[0:28] Stale evidence fails closed. Nothing moves.
[0:33] Fresh evidence can admit the plan, but authority stays narrow: one permit, one contact.
[0:40] Transit. Align. Settle. Approach. Contact. Retract. Verify.
[0:48] [No narration. Let four key cycles establish the rhythm.]
[0:55] The local result is observed before the workflow continues.
[1:01] The arm clears the keyboard and crosses to a separate phone interface.
[1:07] Before every tap, Tactevra checks the expected screen; after change, it checks again.
[1:14] [No narration. Let the phone-entry rhythm play.]
[1:19] Send receives its own final permit.
[1:24] Two interfaces. Two independent receipts.
[1:31] One intent contract, deterministic control, and evidence for every committed action.
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
2. One dark stylus visibly seated between the same gripper jaws throughout.
3. One immutable workcell: board, robot, camera, keyboard, phone, fixtures,
   tags, cables, laptop, and transforms do not drift.
4. One measured black RC03 keyboard with correct legends, proportions, cable,
   protective rear film, and individually animatable `r/e/a/d/y` keys.
5. One measured dark phone with consistent chassis, glass, camera, controls,
   station, cable, and modeled app states.
6. The operator laptop is the request console and local test-pad host. Its UI
   modes are clearly distinct; it is never confused with the phone.
7. Keyboard actions affect only the laptop test pad. Phone taps affect only the
   phone.
8. Lowercase copy remains lowercase in request, proposal, screens, captions,
   receipts, and narration.
9. A preview is always dotted and always labeled `no authority`; only an active
   green permit may become solid.
10. No overlay covers the robot, stylus, gripper, target, or contact point.
11. Every cut preserves outgoing and incoming joint, stylus, and cable pose.
12. `SIMULATED WORKCELL SEQUENCE` persists throughout rendered physical action.

## Asset and production requirements

| Asset | Required condition |
|---|---|
| Robot | Detailed RoArm geometry, servo housings, dual links, fasteners, wiring, gripper, and one articulated rig used in all scenes. |
| Stylus | Dark cylindrical body, plausible protrusion, finished compliant tip, correctly clamped between visible jaws. |
| Keyboard | Measured black RC03 asset, correct six-row layout and legends, animated lowercase target keys, associated only with the laptop test pad. |
| Laptop | Distinct request-console and local-test-pad UI modes; displays `ready` only after physical keyboard presses. |
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

## Production gates

- [ ] Greybox communicates the complete story without narration and at 390 px width.
- [ ] Timings total exactly 100 seconds and all 17 scenes are present.
- [ ] Laptop visibly serves as the local test-pad display; no new board display is invented.
- [ ] All typed strings are lowercase and the local string is at most eight characters.
- [ ] Model card contains only model-owned outputs; runtime-owned fields are visibly locked.
- [ ] Static batch admission is never depicted as physical authority for the full route.
- [ ] Every contact receives, consumes, and clears exactly one permit.
- [ ] Every phone tap begins from a verified expected screen; state changes force re-observation.
- [ ] Blue uncertainty is fully inside a target before its permit becomes active.
- [ ] Dotted previews remain zero-authority until promoted by their own permit.
- [ ] Accurate robot, stylus, keyboard, phone, camera, board, and transforms persist across all cuts.
- [ ] Local and phone observations remain independent through final receipts.
- [ ] README player, captions, transcript, chapters, poster, and social cut use this vocabulary and timing.
- [ ] Simulation qualification remains visible and no rendered action is presented as physical evidence.
