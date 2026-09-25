# Resume non-contact ghost typing after gripper loading

Status: offline B-key candidate screened; r94 installed; **all five bounded
non-contact B-cycle legs sent and verified**. The app permits no sixth leg or
automatic repeat. No physical keypress has been established.

The previous r91 A cycle ended at A_CLEAR. r93 then served the stylus-loading
attempt; its physical retention and protrusion were not verified. The operator
is handling stylus qualification separately and reported the stylus removed
before this bare-gripper ghost test. Do not treat it as a known tool transform.

## Offline candidate completed

`scripts/preview_ghost_typing_resume.py` pins the final seven-joint readback
from the verified first close step. It preserves the current gripper goal
(1897 counts), then screens five finite, non-contact virtual B-key legs:

`B_CLEAR → B_HOVER → B_VIRTUAL_DOWN → B_RETRACT → B_CLEAR_FINAL`.

The B arm-joint targets are inherited from the earlier A/B virtual-key recipe;
they do **not** locate the physical B key. Each leg has at most a 60-count arm
goal change, with no gripper write. The meshless model sampled 101 states per
leg and passed its provisional joint, TCP-height, and link-axis separation
checks. Minimum modeled TCP Z was 73.56 mm and minimum modeled link-axis
separation was 55.75 mm. The verified export is
`wizard-20260925T152842459332Z-0e76e56942764f21b2d4299d2db5cda4`.
Two focused tests pass. These results are numerical screening only; the model
omits the mounted stylus, keyboard, fixture, cable loops and full link meshes.

## r94 installation and five live legs

A dedicated r94 app compiled with SHA-256
`31bceb8f7eb92f220d5221549916d26c4ce0958d269b864600d1dca0d9416c59`.
The linked-image review found no generic serial/web command route. The r94
installer verified the r93 predecessor, wrote only the app slot once, read back
the complete app, verified protected regions unchanged, and started once with
the operator's soft catch beneath the arm. A read-only startup check returned
the reviewed source pose and zero completed legs. The operator then removed
the catch and confirmed the bare-gripper sweep clear.

One request for `B_CLEAR` leg 1 was sent on boot
`e39ad70582b67cec3b0f846b9d3f0486`. Controller-reported base position
moved from 2046 to 2001 counts toward goal 1994 (seven-count residual).
The other six reported positions and goals were unchanged. The command and
before/after seven-joint feedback were exported and verified at
`wizard-20260925T154253781204Z-6226d1d9fb574acc9f27a377de802e22`.
After the operator reviewed the B_CLEAR photograph and reported clearance,
one `B_HOVER` leg 2 request was sent on the same boot. The before pose matched
the verified leg-1 endpoint. The four selected joints (indices 1–4) reported
positions 2094, 2020, 2619 and 2199, within two counts of their respective
goals 2093, 2021, 2618 and 2197. Base and gripper readings remained unchanged.
The verified before/after export is
`wizard-20260925T162922982911Z-a1b2b3c564c646d986465857626bc704`.
The operator reported the B_HOVER sweep stayed clear.

One `B_VIRTUAL_DOWN` leg 3 request was then sent on the same boot. The fresh
before pose matched the verified leg-2 endpoint. The four selected joints
(indices 1–4) reported positions 2106, 2008, 2632 and 2175, within two
counts of their respective goals 2105, 2009, 2630 and 2173. Base and gripper
readings remained unchanged. The verified before/after export is
`wizard-20260925T163122665031Z-b07afdbf3ef24d9bb63469185c2cabb0`.
The operator confirmed clearance for this virtual-down leg.

One `B_RETRACT` leg 4 request was then sent on the same boot. The fresh
before pose matched the verified leg-3 endpoint. The four selected joints
(indices 1–4) reported positions 2099, 2015, 2626 and 2196, within eight
counts of their respective goals 2093, 2021, 2618 and 2197. Base and gripper
readings remained unchanged. The verified before/after export is
`wizard-20260925T163316562825Z-9726886cc32842d49a7b4cf183498937`.
The operator confirmed clearance for this retract leg.

One `B_CLEAR_FINAL` leg 5 request was then sent on the same boot. The fresh
before pose matched the verified leg-4 endpoint. The four selected joints
(indices 1–4) reported positions 2082, 2033, 2609 and 2233, within nine
counts of their respective goals 2075, 2039, 2600 and 2233. Base and gripper
readings remained unchanged. The verified before/after export is
`wizard-20260925T165306016823Z-d79a8b491ee847888bc0d52e1a07899d`.
No additional movement command followed. The operator confirmed the final
move stayed clear of the keyboard, cables and nearby objects.

This is controller feedback plus operator-reported visual clearance, not
independently measured TCP motion or physical key accuracy.

## Five-leg evidence review and next experiment

The read-only `scripts/analyze_r94_ghost_b_cycle.py` review verifies all five
immutable exports, their same-boot ordered endpoint chain, one-write claims,
selected joints, target goals, and reported position bounds. All five passed.
The largest selected-joint goal residual was nine servo counts, and every
unselected joint reported zero position change between each leg's before and
after snapshot. The final reported positions were
`[2001,2082,2033,2609,2233,2041,1900]`; the final goals were
`[1994,2075,2039,2600,2233,2040,1897]`. These are servo counts, not key
center errors in millimeters. The review neither contacts hardware nor grants
motion authority.

The next useful **offline** candidate is a bounded non-contact survey of
several keyboard regions, not another replay of B or a purported keypress.
First register the keyboard's approximate footprint and orientation against
the board marks, and establish the bare-gripper reference point and envelope.
Use at least three widely separated landmarks (for example a letter, a number
and punctuation key) as labeled hypotheses, with uncertainty margins. Then
generate high, non-contact transitions from the freshly observed arm pose and
screen the entire arm-and-cable sweep. Keep photo estimates explicitly
provisional; do not extrapolate a physical C or number-row target from the
53-count A-to-B base offset alone. Any eventual live candidate requires a
separate reviewed app, startup/drop precautions and one attended leg at a time.

## Boundary before another ghost-key exercise

1. Confirm the stylus remains removed and the bare gripper and full swept
   region are clear. If the stylus is remounted, qualify retention and its
   envelope and re-screen first; do not substitute the hypothetical 100 mm
   tool offset.
2. Obtain fresh seven-joint feedback and establish a new reviewed source and
   targets. r94's five-leg sequence is exhausted and cannot be restarted on
   the same boot. Do not use a controller restart merely to replay it.
3. Check the actual keyboard/objects/cables and confirm the complete path
   remains non-contact. Photo placement is approximate, not a collision or
   key-center certificate.
4. Use one bounded leg at a time, with fresh source/health checks, a durable
   command reservation, readback and export before advancing. On a failed or
   uncertain leg, stop without retry, automatic return or next movement.

After B is established, expand by explicit layout/key hypotheses for other
letters, number row, and punctuation. Do not label a virtual pose as a physical
keypress or an accurate stylus-tip position.

## Next bare-gripper hover checkpoint (2026-09-25)

The r94 app is still on boot `e39ad70582b67cec3b0f846b9d3f0486`, with
`STATUS:...:5:0:0`: all five allowed legs are consumed. A fresh read-only USB
snapshot repeated its verified final positions
`[2001,2082,2033,2609,2233,2041,1900]` and goals
`[1994,2075,2039,2600,2233,2040,1897]`. No actuator command was issued.

The new photo fit locates 46 *nominal* keyboard centers on the board, but does
not register those points to the controller or establish the lower edge of
the bare gripper. In particular, the older A/B servo-count recipe is **not**
an 85 mm physical A-to-B key mapping. Do not relabel its poses as key centers.

`application/bare_gripper_hover_preview.py` now screens a manually gated,
five-leg two-region hover candidate from the verified r94 endpoint:
`B_CLEAR → B_HOVER → B_CLEAR → A_CLEAR → A_HOVER → A_CLEAR` (five target
legs after the initial B_CLEAR). It commands neither the gripper nor a
virtual downstroke. The largest selected-joint goal change is 53 counts.
The meshless interpolation's minimum modeled hand-TCP height is 77.50 mm,
and minimum link-axis separation is 55.75 mm. This is an **offline pass, not
a physical clearance certificate**: the gripper volume, keyboard, cables,
fixtures and installed board-to-arm transform are missing. Any physical
trial needs a newly reviewed, dedicated app, fresh same-pose checks,
controller-only startup catch precautions, catch removal before movement,
and one attended exported leg at a time. r94 cannot take another leg.

### r95 installation checkpoint

The dedicated r95 image was built offline with SHA-256
`d4aafbbb0ede6e93f7085fe07eb7a064344120f9493a423f5d2e2eb65aa73045`.
Its staged source is deterministically derived from r94 with only the
dedicated board and boot changed. Linked-symbol review found its fixed
`BareGripperHoverBoard::dispatch` and no generic serial/web motion parser.
It has five fixed, manually gated hover/clear legs, no gripper write, no
virtual downstroke, and no startup servo command.

With the operator's soft catch beneath the arm, one app-slot-only write was
performed and fully read back. The installer verified the r94 predecessor,
controller MAC, partition and filesystem identities, and unchanged protected
flash regions; it did not rewrite settings or credentials. One controller
startup followed. r95 reported boot `818844fc46074ad9e965c8a4e61f33ee`,
status `0:0:0`, and a fresh read-only seven-joint snapshot identical to the
pre-startup r94 endpoint (positions
`[2001,2082,2033,2609,2233,2041,1900]`, goals
`[1994,2075,2039,2600,2233,2040,1897]`). No r95 motion leg has yet been
sent. The catch must be removed from the entire sweep and the path freshly
confirmed clear before exactly one first-leg request; do not retry or advance
automatically.

After the operator confirmed the catch was out of the entire sweep and the
path clear, exactly one r95 `REGION_B_HOVER` leg 1 was sent on that boot. The
fresh before snapshot matched the r94 endpoint. Controller verification and
the durable export
`wizard-20260925T175239899544Z-b01b2d4bd0014798bcd16078e6fac8a3`
record selected joints 1–4 ending at positions `2094,2020,2620,2199`
against goals `2093,2021,2618,2197`; base, wrist roll and gripper readings
were unchanged. The arm is now at the hover pose. This is joint feedback,
not evidence of physical key-center alignment or visual clearance. Await the
operator's observation before any retract or other leg.
