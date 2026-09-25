# Resume non-contact ghost typing after gripper loading

Status: offline B-key candidate screened; r94 installed; **B_CLEAR leg 1 and
B_HOVER leg 2 sent and verified**. No later leg or automatic return was sent.

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

## r94 installation and first two live legs

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
No B_VIRTUAL_DOWN command followed.

This is controller feedback and an operator clearance setup, not independently
measured TCP motion or physical key accuracy. The B_HOVER visual clearance
assessment is still pending from the operator.

## Boundary before each remaining live B-key leg

1. Confirm the stylus remains removed and the bare gripper and full swept
   region are clear. If the stylus is remounted, qualify retention and its
   envelope and re-screen first; do not substitute the hypothetical 100 mm
   tool offset.
2. Obtain fresh seven-joint feedback. For leg 3, bind to the verified leg-2
   endpoint on the same r94 boot. Reject a changed source or controller boot;
   never replay a stale pose.
3. Before each live command, check the actual keyboard/objects/cables and confirm
   the complete path remains non-contact. Photo placement is approximate, not
   a collision or key-center certificate.
4. Use one bounded leg at a time, with fresh source/health checks, a durable
   command reservation, readback and export before advancing. On a failed or
   uncertain leg, stop without retry, automatic return or next movement.

After B is established, expand by explicit layout/key hypotheses for other
letters, number row, and punctuation. Do not label a virtual pose as a physical
keypress or an accurate stylus-tip position.
