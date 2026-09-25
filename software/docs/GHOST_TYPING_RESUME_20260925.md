# Resume non-contact ghost typing after gripper loading

Status: offline B-key candidate screened; **no arm movement authorized or sent**.

The previous r91 A cycle ended at A_CLEAR. r93 is now installed for stylus
loading; it has only gripper control, not an arm-motion route. The stylus has
been seated and the gripper has completed one small closing step, but physical
retention and protrusion are unverified. The operator is handling stylus
qualification separately. Do not treat the stylus as a known tool transform or
move the arm with it merely because the gripper reached a servo count.

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

## Boundary before any live B-key cycle

1. For a tool-free test, remove the loose/unqualified stylus with the arm
   stationary and confirm the bare gripper and full swept region are clear.
   If the stylus remains mounted instead, qualify retention and measured
   protrusion and re-screen the entire sweep with its envelope first. Do not
   substitute the earlier hypothetical 100 mm tool offset.
2. Obtain fresh seven-joint feedback after any manual change. Reject a source
   that differs from the exported close-step source; never replay the old pose.
3. Build a new, separately reviewed arm-motion app/host route. The installed
   r93 loader cannot execute the B cycle. Preserve protected settings and
   credentials on any app change, and account for arm drop risk on restart.
4. Before live command, check the actual keyboard/objects/cables and confirm
   the complete path remains non-contact. Photo placement is approximate, not
   a collision or key-center certificate.
5. Use one bounded leg at a time, with fresh source/health checks, a durable
   command reservation, readback and export before advancing. On a failed or
   uncertain leg, stop without retry, automatic return or next movement.

After B is established, expand by explicit layout/key hypotheses for other
letters, number row, and punctuation. Do not label a virtual pose as a physical
keypress or an accurate stylus-tip position.
