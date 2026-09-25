# Powered feedback protocol review

Reviewed: 2026-09-12. Status: vendor protocol checked; installed-firmware
compatibility and physical feedback admission remain incomplete.

## Vendor semantics

Waveshare documents `{"T":105}` as the feedback request and `T=1051` as its
response. The response includes endpoint coordinates, joint angles in radians,
loads, torque-switch states and voltage in 0.01-V units. Reading torque-switch
state is not permission to change it. The adjacent direct-target command is a
different operation and must not be included in this feedback request.

Source: [Waveshare RoArm-M3-S Robotic Arm Control](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control).

## Software binding

`PoweredFeedbackIntent` uses the existing fixed encoder and cannot include a
caller-supplied command, endpoint, motion target or permission flag. It describes
one open, one T105 write, bounded startup/response retention, no retry, and reserved
cleanup time. References to original powered startup, identity, protocol review,
firmware compatibility review and runtime must be verified by future preparation
and dispatch code; syntactically valid hashes are not approval.

The existing shared T1051 parser and strict transaction framing remain the
response authority. Preserve pre-request bytes separately; an unsolicited or
stale T1051 packet cannot be accepted merely because its shape looks correct.

## Received-unit evidence update

The operator reported successful adapter-powered startup and stable USB reconnect.
USB identity matched COM6, but that does not identify the installed firmware.
The operator has now explicitly reported firmware **unchanged since delivery**.
See `ARM_RECEIVED_FIRMWARE_HISTORY.md`. This resolves the pending history question,
but does not identify a firmware version or binary hash. Do not invent either or
replace UNKNOWN with the vendor archive hash. The operator also reconfirmed the
arm secured, stationary, powered by the supplied adapter and connected over USB
with a clear movement area; this is a current operator report, not a sensor reading.

Waveshare's documented T105/T1051 semantics were rechecked using the official
indexed control documentation after a direct-page request returned HTTP 403.
The review basis is unchanged delivery plus vendor protocol, not binary verification.

`powered_feedback_firmware_review.py` now represents that limited basis explicitly.
Powered original preparation validates its exact model, session/source, original
operator-report bytes and protocol-document hash. It rejects modified/unknown
history, invented firmware identity, different commands and permission claims.
It associates recorded evidence; it does not authenticate an operator by itself.
Native/runtime admission and the live coordinator remain separate unfinished work.

Verification: **58 tests passed in 12.30s** in
`software/runs/pytest-powered-feedback-firmware-20260912-01`, covering review,
preparation, journal, child claim and isolated packaging regressions. Test inputs
remain explicitly modeled. No live T105 or movement was sent during this increment.

This review does not authorize a port open, issue a safety permit, complete
canonical power/startup stages, or enable motion. No live T105 has been sent.

## Tested implementation checkpoint

`providers/windows/powered_feedback_observation.py` now exercises the existing
non-purging lifecycle through an exact memory-only API. Its endpoint binding
checks the intent's original metadata hash, session, mode and source. The shared
backend explicitly rejects native I/O for this new binding.

The rehearsal preserves pre-request bytes, permits one fixed T105 write, requires
one complete typed pose/voltage response, checks a post-response quiet interval,
and closes on failure as well as success. Partial writes are not retried. Result
bytes, errors and resource cleanup are retained separately; failure to confirm
cleanup prevents success. No simulation result grants physical authority.

T1051 contains no host transaction identifier. Quiet intervals cannot prove that
a delayed unsolicited packet was caused by this request. Physical admission must
consider that limitation and installed firmware behavior; this observation alone
must not authorize motion.

Validation: 103 tests passed in 4.77 seconds, including powered observation,
shared non-purging backend and passive native packaging, using
`software/runs/pytest-powered-feedback-lifecycle-20260912-03`.
All device I/O in these tests was synthetic. Live powered feedback dispatch,
its reviewed admission, and the corresponding wizard action remain unfinished.
