# Discrete Wi-Fi endpoint testing

## Decision

The user approved a provisional **one-second feedback-gap allowance**, keeping
the tested **150-ms post-response cooldown**. The 250-ms statistic is historical
comparison data, not a hard requirement for discrete move/wait/verify testing.
Do not continue optimizing polling rates merely to satisfy that older number.

This policy is separate from continuous-motion qualification. Existing USB
persistence analyses and historical exports retain their original rules.

## Implemented

`software/src/rocell/arm/discrete_endpoint.py` defines versioned policy and a
hardware-independent endpoint verifier. It reuses existing joint checking:

- Arrival tolerance remains 0.5 degrees; no accuracy criterion was loosened.
- Existing quiet-span and dwell checks remain, with at least three consecutive
  in-band observations required additionally.
- Other-joint drift and selected-joint excursion fail the endpoint assessment.
- First response, response-completion gaps and trailing silence are checked
  against one second. This is host observation timing, not device timestamps.
- Completion deadline is independent of the feedback-gap allowance, selected
  before dispatch from expected duration plus settling margin. Caller supplies
  it explicitly; the verifier does not guess servo speed units. Maximum supported
  evaluation deadline is 120 seconds after dispatch completion.
- Reset, invalid feedback, cancellation, or excessive feedback silence invalidates
  arrival. No result authorizes an automatic retry or next movement.

Wizard Wi-Fi observations now include a separate discrete-timing assessment.
The UI explains the one-second allowance, retaining historical 250-ms counts.
Saved observations are not rewritten or retroactively relabeled as movement tests.

## Evidence

Offline reconstruction and export integrity checks passed again for:

- `wizard-20260916T142622962207Z-be62821521d64796b6cb4cab2505eaee`:
  maximum observed gap 426.889 ms.
- `wizard-20260916T142718951598Z-906bc07155ba48f8a2282d4cb658077a`:
  maximum observed gap 429.418 ms.

Both fit the provisional allowance for **stationary response timing only**.
Neither contains a movement command or establishes endpoint accuracy, device
sample freshness, or an externally measured tool-tip position.

## One-shot transaction engine and wizard simulation

Implemented `software/src/rocell/arm/discrete_transaction.py`. Its hardware-free
state machine binds a six-joint baseline, one roll target and a completion budget.
The initial envelope is a >0.5 to 1.5 degree roll delta, absolute target within
3 degrees, with previously used speed/acceleration coefficients 20/1. These
numerical limits alone are not movement admission or clearance evidence.

Dispatch consumes the sole attempt before returning command intent. A stale
baseline blocks dispatch; a lost acknowledgment leaves an uncertain result and
cannot restore the attempt. Completion budget starts at dispatch, not receipt
of an acknowledgment. Feedback uses the shared discrete verifier. The engine
exposes the next absolute deadline to its future I/O owner; it does not itself
interrupt a blocking socket operation.

The wizard action **Test discrete transaction logic (simulation only)** runs seven
deterministic cases: successful arrival, execution with lost acknowledgment,
feedback reset, feedback silence, missed target/deadline, other-joint drift and
cancellation. All command intents remain in memory. Results are service-owned and
available through ordinary diagnostic export. There is no arbitrary command input,
automatic return, retry, or registration as a native Wi-Fi sender.

Wizard simulation operation: `operation-a24faf1d525a4f06a9e6649510265204`.
All seven cases passed and the export independently verified:
`software/runs/wizard-exports/wizard-20260916T150642670962Z-aa20b277545d42b0ba3464c131781693`.
No network/USB access or physical movement was performed by this action.

The native I/O adapter and admission integration remain unfinished. This engine
does not by itself complete the following physical integration steps.

## Native deadline-bounded feedback adapter

Implemented `software/src/rocell/providers/windows/arm_wifi_deadline.py` and the
wizard action **Test Wi-Fi absolute deadlines (no movement)**. CLI equivalent:
`software/scripts/bench_wifi_feedback.py --observe-bounded`.

The fixed-address adapter uses nonblocking sockets and a shared absolute 800-ms
budget across connect, request sending, headers and body. Readiness checks poll
cancellation at most every 25 ms while scheduled. Slow/trickled data cannot reset
the budget. This is software deadline enforcement, not a hard real-time OS
guarantee; native neighbor lookups and cleanup are outside that HTTP I/O budget.
The future movement runner must also enforce its transaction-wide deadline.

Only the exact T105 GET is accepted. Content-Length framing, status 200 and bounded
headers/body are required. Redirects, chunking, duplicate headers, oversized or
incomplete bodies fail closed. All existing numeric-feedback parsing, original
retention and before/after MAC consistency checks remain. Error text is not
retained; HTTP header/body failures share an explicit exchange-phase label.

Live operation `operation-cd913859a72c46b7bf61af66c9f0581f` completed 35.047 s with
115 successful responses and no reset. Maximum completion gap: 414.802 ms, within
the provisional one-second stationary timing allowance. No motion or USB access.
Export independently verified and original-response reconstruction matched:
`software/runs/wizard-exports/wizard-20260916T151215687012Z-1603592ee71041f38f5b2a9047cab436`.
Manifest SHA-256: `37d893a9d9c286ae76fad67b07fd1b855c59f478dfb803d74924212c79521a96`.

Existing AbsoluteWristPermit/PositionalCampaignAdmission native composition is
bound to serial port/USB identity and owned serial processes. It was not repurposed
for HTTP. Wi-Fi movement admission and the live transaction runner remain pending;
the successful feedback observation does not grant motion authority.

## Durable Wi-Fi reservation and injected transaction runner

Implemented `software/src/rocell/safety/wifi_dispatch_reservation.py` and
`software/src/rocell/application/wifi_discrete_runner.py`. These do not repurpose
USB permits and are not registered as a physical wizard command action.

The reservation verifies original baseline bytes and their digest, six-joint
pose, pinned IP/MAC checks, cleanup, freshness and the bounded roll target. It
persists the exact baseline, command, owner process and completion budget under a
unique attempt id. Dispatch checks identity again, exact command equality, age,
process ownership and unchanged reservation bytes, then durably publishes a
consumed record BEFORE releasing command bytes. The existing reservation blocks
reuse of the same attempt id after restart. A failed consumption burns the object.
This is a dispatch latch, not cryptographic device authentication or independent
evidence of physical clearance.

The injected runner performs one send attempt, processes acknowledgment separately
from arrival, waits the selected cooldown, and passes absolute feedback deadlines
to its transport. It retains successful original responses and uses the shared
endpoint verifier. Lost acknowledgment ends uncertain without further polling,
resend or return. A second call returns ATTEMPT_ALREADY_USED, even after success.
All production clocks must use the same perf-counter time basis as the probes.

Tests cover arrival, execution with lost acknowledgment, reset, late feedback,
pre-dispatch cancellation, stale baseline/expiry, changed command, wrong MAC,
repeated invocation and durable attempt-id reuse. The transport in these tests is
simulated: no physical command has been sent by this integration.

Remaining native composition: implement the exact-command HTTP sender (without
expanding the T105-only adapter's public command surface), acquire the cooperative
transport lock for the entire trial, obtain the baseline directly from the native
provider, compose the durable reservation in the wizard service and retain/export
the final result. The sender must enforce the passed absolute deadline, consume
only the selected payload, distinguish valid acknowledgment from endpoint feedback,
close its sockets on all paths, and never retry. Native command acknowledgment
framing on this installed firmware still needs bounded verification. No generic
raw-command UI or physical movement action was enabled here.

## First native Wi-Fi command attempt and follow-up evidence

Implemented a restricted native sender in `wifi_discrete_native.py` and the
explicit wizard action **Move roll +1 degree and verify (Wi-Fi)**. It holds the
cooperative transport lock across baseline/dispatch/feedback, selects +1 degree
from fresh roll feedback (absolute target within +/-3 degrees), uses speed 20 /
acceleration 1, and a ten-second completion budget. Native dispatch has an
additional one-use durable claim. It sends no initialization or return command.

One live attempt was made: `operation-fb14d82e13c641b2b2e688374aab277d`.
The command response was not accepted; the transaction ended
COMMAND_OUTCOME_UNCERTAIN without a retry. The historical failure did not retain
enough response details to establish whether HTTP framing, receipt validation or
transport caused the rejection. Do not retrospectively label it a reset.

A separate wizard publication bug omitted `physical_authority=False` from the
result envelope. It caused INVALID_WORKER_RESULT after execution; raw metadata
was still retained/exported. The envelope is now fixed, and tests assert both
successful and failed trial reports pass publication without that error. Future
sender faults retain fixed categories, without exception text or unknown bodies.

Historical attempt export, independently verified:
`software/runs/wizard-exports/wizard-20260916T155310975150Z-c99e383bafdb46068b11909bf9350583`.

An explicitly separate feedback-only observation then completed 35 seconds with
116 successful readings, maximum completion gap 599.476 ms, and zero within-run
joint spans. No additional movement or return was sent.

- Before roll: 0.001533981 rad.
- Requested roll: 0.018987273519943296 rad (+1 degree).
- Follow-up roll: 0.016873789 rad.
- Reported change: +0.878906257 degrees.
- Reported target error: -0.121093743 degrees, within the unchanged 0.5-degree
  arrival band. Other five reported joint positions matched the pre-command pose.

Follow-up operation: `operation-ed79697489fc4eb698f54ec0c1d0ae20`.
Export independently verified and original reconstruction matched:
`software/runs/wizard-exports/wizard-20260916T155414943339Z-e0eb651552324040b848208e8d84020b`.

This establishes a before/after change in controller-reported position consistent
with the attempted command. It is not external tool-tip measurement, nor does it
repair the missing in-transaction acknowledgment/arrival evidence. The original
trial stays uncertain. Current sender accepts only `{}` or `{"ok":1}` receipts,
and the strict shared parser requires positive Content-Length. Installed movement
receipt framing remains unresolved; do not resend the old attempt to inspect it.

Next: obtain bounded response-framing evidence for the installed command path,
add regression fixtures, and make receipt handling compatible without treating
HTTP acceptance as endpoint verification. Any further movement must be a distinct
fresh-baseline trial with its own attempt id, never a retry of this one.

## Receipt compatibility resolved; first verified end-to-end trial

Investigation confirmed the public Waveshare HTTP examples do not prescribe a
uniform command acknowledgment schema ([official HTTP documentation](https://www.waveshare.com/wiki/RoArm-M3-S_Python_HTTP_Request_Communication)).
An empty HTTP 200 response is now supported for command receipts only; empty
T105 feedback remains rejected. This was a compatibility correction, but it did
not explain the next observed command response, which was nonempty.

Distinct attempt `operation-65753f86fc474a4994eeb4015911fccd` received HTTP 200,
Content-Length 202, but failed receipt-schema validation. No retry was made.
Its export independently verified:
`software/runs/wizard-exports/wizard-20260916T155720295419Z-56d1b09570da4ec8a3f0da91a09c8464`.
Unknown body bytes were not retained, so do not retrospectively claim their schema.

The sender now also accepts strictly parsed numeric T1051 bodies with all six
joints and only known numeric fields as **transport receipts only**. Unknown
fields, secrets, duplicate fields, missing joints, NaN, malformed responses and
error objects remain rejected. `ok:true` is not accepted as integer `ok:1`.
The receipt is explicitly excluded from endpoint verification. The runner's
`acknowledgment_received` means HTTP transport receipt, not proof of execution.

Distinct fresh-baseline attempt `operation-00cf0d918a73452786c73d703f148da6`
then completed successfully through the wizard:

- Before roll: 0.030679616 rad.
- Target: 0.0481329085199433 rad (+1 degree).
- Final roll: 0.046019424 rad (2.636718771 degrees).
- Reported change: +0.878906257 degrees; target error -0.121093743 degrees.
- Three independently requested post-command T105 responses agreed at the final
  position, satisfying existing settling/dwell and three-consecutive-reading rules.
- Maximum feedback gap: 316.249 ms, within the provisional one-second allowance.
- All five other joints unchanged. One command attempt, no retry or return.

Crucially, the command's HTTP receipt was a valid T1051 body **byte-for-byte
identical to the pre-command baseline**. This directly confirms why command
response content must not be treated as arrival evidence. The three later
position queries, not the receipt, establish REPORTED_ENDPOINT_VERIFIED.

Export independently verified; exact successful feedback originals reconstructed
all three endpoint rows and reproduced the stored endpoint verdict:
`software/runs/wizard-exports/wizard-20260916T155815304578Z-90d5896b37c544749ac53b6897248893`.
Manifest SHA-256: `4251795212851ba6c1a375a1c673605c3d7c170ec34269db4cec4255eec22d28`.

This is one successful end-to-end discrete roll trial, not long-term reliability
qualification or external tool-tip accuracy. Earlier uncertain trials remain
uncertain. Current reported roll is near the +3-degree local envelope boundary;
another +1-degree action should be rejected from this pose. Do not enlarge that
envelope merely to keep increasing. Next useful extension is a separately bound
negative-direction trial with a fresh baseline, not an automatic return or replay.

## Negative-direction trial: verified, but close to the arrival limit

Added the separate explicit wizard action **Move roll -1 degree and verify
(Wi-Fi)**, backed by a fixed negative-direction entry point. It acquires its own
baseline and attempt id; it is not an automatic return. Positive-direction
behavior remains unchanged. Negative reports use `rocell.native_wifi_roll_trial.v2`
and record requested_delta_deg=-1. Both directions retain the +/-3-degree absolute
target limit, one-degree step, speed 20/acceleration 1, and existing timing rules.
Offline tests cover negative target binding, out-of-range rejection, inert preview,
and publication/export of both success and failure.

Live operation `operation-ee333141b84b4fb78d603b9673d0ddaf` succeeded:

- Start roll 0.046019424 rad (2.636718771 degrees).
- Requested target 0.028566131480056708 rad (-1 degree relative).
- Final roll 0.036815539 rad (2.109375005 degrees).
- Reported movement **-0.527343766 degrees**, signed target error
  **+0.472656234 degrees**: within 0.5 degrees, but close to that limit.
- Four post-command responses; the last three were in-band and settled.
- Maximum feedback gap 328.040 ms; decision 1.219 seconds after dispatch.
- Other five joints unchanged. One attempt; no retry, correction or return.

The command receipt again matched the pre-command response and was excluded from
arrival analysis. The exact retained post-command responses reconstructed the
endpoint rows and reproduced the stored verdict. Export independently verified:
`software/runs/wizard-exports/wizard-20260916T160125354817Z-c85452a576654f5196b2666640377f7c`.
Manifest SHA-256: `d5ef38d2d8c24ec00f0395261832d95e56737fdbb4ad82b85c215d685db499f8`.

Comparison of the two completed opposite-direction trials:

| Requested delta | Reported delta | Signed target error |
| --- | --- | --- |
| +1 degree | +0.878906257 degrees | -0.121093743 degrees |
| -1 degree | -0.527343766 degrees | +0.472656234 degrees |

These are different starting poses and one completed trial per direction, not a
controlled repeatability campaign. They show that a transport/arrival pass does
not imply high precision. Do not relax positional tolerance or fit compensation
from this pair. Next useful work is a small, fixed-target, direction-tagged repeat
set with separately admitted legs, original response exports and a longer passive
post-arrival observation to distinguish early settling from persistent offset.
Preserve the current no-retry behavior on any fault. No external Cartesian
accuracy is established by joint telemetry.

## Fixed-target repetitions and longer observations

Completed four fixed-target trials (two descending to 1 degree, two ascending
to 2.5 degrees), each followed by 35 seconds of read-only observation. All passed,
and all endpoint originals/exports independently verified. Results, limitations,
new wizard actions and evidence references are in
[fixed-target results](WIFI_FIXED_TARGET_RESULTS_20260916.md).
No compensation was applied. The next priority is comparing approaches to the
same target from both sides, rather than conflating direction with target angle.

## Same-target approach comparison completed

Completed the five-leg bounded plan approaching 1.25 degrees from both sides.
All legs passed; the two reported endpoints differed by 0.351562491 degrees and
persisted in their separate 35-second follow-up windows. Original exports and
endpoint reconstructions verified. See [same-target comparison](WIFI_SAME_TARGET_COMPARISON_20260916.md)
for full results, scope limits and next repeated/held-out validation steps.
No compensation was enabled.

## Reverse-order repeat and disabled candidate

The reverse-order same-target set completed with four successful distinct legs
and verified exports. See the updated [same-target comparison](WIFI_SAME_TARGET_COMPARISON_20260916.md)
and [disabled local candidate](WIFI_ROLL_125_CANDIDATE.json). No corrected command
has been sent. Separate desired endpoint from command angle in the verifier before
held-out correction testing; do not silently repurpose existing arrival semantics.

## Original integration checklist (historical; see updates above)

The existing Wi-Fi provider is deliberately T105-only. No wireless movement was
sent as part of this change. The new verifier is not yet a live movement runner.

1. Add a separate bounded single-joint command adapter under the existing
   transport lock and command admission boundary. Do not turn the feedback probe
   into a generic JSON command sender.
2. Acquire a fresh six-joint baseline, select a previously tested small excursion,
   and bind the exact command, target, timing policy and deadline before dispatch.
3. Send once. If the response is lost, the command may still have executed: record
   an uncertain outcome and do not resend or automatically return to start.
4. Poll at the selected cooldown, evaluating each growing capture through the new
   verifier. A one-second watchdog must include socket waits; merely checking after
   a blocking two-second HTTP read is insufficient. Add bounded/cancellable read
   handling or a supervising deadline before calling the live runner complete.
   The new nonblocking feedback adapter implements the HTTP I/O portion; wire its
   absolute deadline to the transaction's remaining budget when composing the runner.
5. Stop progression on fault, excursion, drift or deadline. Software cancellation
   means no further commands; it does not prove the arm physically stopped.
6. Export baseline, exact attempted command, timestamps, successful original
   feedback bodies, failures, policy and final assessment through the wizard.
7. Prove the runner in simulation (including lost acknowledgment with command
   execution), then execute one bounded live trial. Keep larger/continuous
   movement out of scope until separately qualified.

The immediate priority is this single-command transaction, not a 75-ms polling
experiment. No firmware changes or Wi-Fi settings changes are required by this
policy implementation.
