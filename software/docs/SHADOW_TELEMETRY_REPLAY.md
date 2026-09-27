# Shadow telemetry replay qualification

ARM-058 joins the existing zero-write Waveshare command preview to offline
T=1051 telemetry. It answers a narrow but important question:

> If these planned T=102 waypoint targets had been issued, would this replayed
> telemetry satisfy the declared joint-arrival and stability policy?

It does not answer whether the physical arm moved, whether the feedback came
from an authentic controller, whether the swept path was safe, or whether a
keyboard/phone action succeeded.

## Inputs and result

`assess_shadow_telemetry_replay_v1` accepts:

- one typed `ZeroWriteWavesharePreviewReceiptV1`;
- ordered, typed T=1051 samples bound to the same correlation ID, controller
  session, and waypoint sequence;
- an explicit `SYNTHETIC` or `RETAINED_EXPORT` origin; and
- a bounded arrival/stability/freshness policy.

For each command waypoint it compares all six controller joint values with the
exact preview target. A waypoint is settled only after the required consecutive
samples are both within target tolerance and mutually stable. Every command
waypoint must settle for `SIMULATION_REPLAY_PASS`; otherwise the result is
`SIMULATION_REPLAY_UNVERIFIED`.

Crossed correlation/session identities, unknown waypoints, timestamps before
the scheduled dispatch, stale or non-monotonic samples, malformed T=1051
messages, and incomplete joint feedback fail closed instead of being discarded.
Retained telemetry must bind a source-export SHA-256. That binding does not
authenticate the export as a live controller transaction.

## Structural zero-write boundary

The implementation imports the typed preview receipt and the existing feedback
parser. It owns no serial factory, port, socket, callback, writer, permit issuer,
or retry loop. Every report retains:

- `transport_opened: false`;
- `transport_write_count: 0`;
- `automatic_retry: false`;
- `execution_authorized: false`;
- `hardware_access: false`; and
- `physical_authority: false`.

The JSON schema additionally fixes `physical_arrival_proven` and
`independent_visual_outcome_proven` to false. Therefore a synthetically perfect
replay cannot be promoted into a physical success claim.

## Accuracy interpretation

This assessor can exactly verify command/feedback mapping, joint residual
arithmetic, ordering, freshness, stability policy, deterministic hashing, and
fail-closed behavior. Its physical predictive value depends on the quality of
the replay source and the calibration that produced the planned trajectory.

The next accuracy step is to feed independently retained, authenticated
controller evidence through this same boundary and compare the replay verdict
with a separate visual observation. That remains blocked on the ARM-054
independent-review dependency and later read-only endpoint qualification. It is
not authorized by ARM-058.

