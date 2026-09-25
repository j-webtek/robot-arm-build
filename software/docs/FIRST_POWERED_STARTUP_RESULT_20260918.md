# First powered startup trial: torque-disabled admission stop

User confirmed motor power connected and stationary. On boot
`89dcfb9d20c27693caf3f46be6efefd7`, one signed request for elbow count 2727 was
accepted by the controller. No retry, return movement or reset followed.

## Verified observations

Two complete fresh seven-servo scans reported identical positions:
IDs 11–17: 2048, 2390, 1727, 2723, 2041, 2042, 2051. All moving flags were zero,
all goal registers were zero. Both scans met position/stability requirements.
The elbow proposal was four counts from its freshly measured position.

Fourteen direct control reads succeeded with exact one-byte lengths and zero
device errors. Mode register 33 returned 0 for all seven servos, matching policy.
Torque-enable register 40 also returned 0 for all seven, while policy requires 1.
The controller stopped at CONTROL_STATE_MISMATCH before dispatch. Four retained
records are authorization, first scan, second scan and control reads. There is
no movement-dispatch or write record and no endpoint acquisition.

Host delivery is CONTROLLER_REPORTED_ACCEPTANCE, while endpoint result remains
INCONCLUSIVE: accepted request is not an executed movement. This is a concrete
precommand blocker, not a measurement of command-to-position error or evidence
of a broken actuator. We cannot claim arrival, non-arrival after motion, or any
improvement in physical accuracy from this trial.

## Explanation and next change boundary

The installed diagnostic-only setup explicitly skips reference initialization
and all startup servo writes. It does not enable torque. Restoring motor power
has therefore not established the torque-enabled state required by this trial.
The readings prove torque was off; they do not uniquely establish when/how it
became off or the servo's undocumented power-up behavior.

Do not blindly enable torque with all target registers still zero. A reviewed
initialization method must establish safe current-pose targets, verify readback,
and account for the mechanically coupled shoulder pair before torque engagement.
Writing hold targets or enabling torque is a servo-state change with possible
physical movement, not a passive diagnostic query. It needs separate review and
explicit approval. The present zero-goal startup contract will also need an
explicit transition to seeded hold goals; do not weaken it or reset to bypass it.

Next: review pinned servo/reference initialization semantics and design/test a
bounded hold-current-position initialization transaction. Preserve exact writes,
ACKs and new readbacks, stop on uncertainty, and never auto-retry or disable
holding torque as a generic error response. Any new firmware or provisioning
requires separate approval. Keep mechanical support; no power change requested.

## Retained evidence

- Linked trial: `wizard-20260918T163241427881Z-9b3d92713ca740ddab62e51a4ea9af64`.
- Raw transport: `wizard-20260918T163241257794Z-1216cea71e3247d281182a9ce9f83925`.
- Offline decoded review: `wizard-20260918T163348227223Z-d415871f241e4ffb815608703eea5c45`.

Trial and transport exports verified and replayed. A first attempt to create the
additional offline review omitted exporter.prepare() and failed before publication;
it was corrected locally, with no device access or retry of the live trial.
