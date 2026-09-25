# First-motion commissioning decision required

Update: Jack's “do whats best” selects development of route 2. See
`FIRST_MOTION_COMMISSIONING_PLAN.md`. The earlier unanswered design-choice hold
is resolved; this does not mark the baseline qualified or authorize a live move.

## What is established

The actual USB unit is identifiable; bounded zero-write capture works; the new
photo confirms the expected coarse posture; retained joint angles reproduce
reported Cartesian coordinates under the pinned vendor reference equations.
The proposed +2 mm endpoint path has regular reference IK solutions with sampled
joint changes below 0.8 degrees. These are useful but distinct observations.

## Why the current launch remains held

`application/endpoint_owned_trial.py::_baseline_context` explicitly delegates
pose meaning and freshness to an independent baseline review. The mandatory
`controller_frame_and_baseline_qualified` engineering check has not been approved.
Host read times, a photograph and repeated numerical consistency do not supply
an independent device freshness guarantee. This is not a diagnosed stale-data
fault; it is an unresolved evidence requirement.

There is also no production set of all five approved engineering reviews and
seven current exact-request operator records. The staged supporting originals
must not be relabeled as that set. More repeated baseline captures or copies of
these files cannot resolve the semantic requirement on their own.

## Two legitimate next routes

1. Obtain sufficient independent technical evidence for the current baseline
   requirement, such as received-firmware feedback behavior validated with a
   suitable measurement/observation method. A vendor reference binary alone
   does not identify installed firmware. No firmware change is proposed.
2. Design a separately reviewed **initial-motion commissioning procedure**
   which explicitly treats feedback freshness as unknown before the experiment
   and determines what bounded physical test can establish command/feedback
   behavior. This is a new admission policy requiring an explicit decision,
   not an override checkbox for the existing endpoint executor.

Route 2 must not merely mark the old baseline check APPROVED. Its design must
specify how actual starting posture, maximum joint travel, payload, full-arm and
cable envelope, controller/servo command semantics, startup behavior, operator
presence and power-loss behavior bound the test even if feedback is stale.
Any proposed joint command family needs a separate official-source review;
do not silently substitute it for T104 or expose arbitrary JSON.

## Non-negotiable limits for any new design

- Preserve the expected USB identity and pre-open rechecks, source binding,
  owned process/connection, one-use attempt, one exact command and no retry.
- Preserve original evidence, unknowns and failures. Do not refresh old
  attestations or claim physical position from a simulation result.
- No homing, firmware/servo configuration changes, torque release, continuous
  sweep, automatic return, keyboard contact or phone contact.
- Do not treat serial close or worker cancellation as a physical stop.
- Require supervised observation of the outcome and retain raw pre/post data;
  an uncertain result must end the procedure, not advance the campaign.
- Define acceptance separately for communications, observed movement and
  quantitative calibration. No false claim of path tracking or measured speed.

## Status

No new commissioning policy is approved or implemented by this document. No
live command was sent. The original movement-characterization goal is intact:
qualify the first move, then progressively characterize approved poses/speeds.
The user must select the commissioning route before we change admission policy.
