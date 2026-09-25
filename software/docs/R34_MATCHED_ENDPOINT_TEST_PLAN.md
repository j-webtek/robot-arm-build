# Next movement experiment: repeatability before compensation

## Verified starting evidence

Source result export:
`wizard-20260920T152856234358Z-015ca31209b64e6cb052f6c53cb57326`.
Run export:
`wizard-20260920T152856753981Z-cd28202562ac448fabe01b74f13c33df`.

| Shoulder servo | Initial target | Initial measured | Final target | Final measured | Movement | Final residual |
|---|---:|---:|---:|---:|---:|---:|
| 12 | 2405 | 2414 | 2397 | 2407 | -7 | +10 |
| 13 | 1709 | 1702 | 1717 | 1710 | +8 | -7 |

Values are encoder counts, not millimetres. Position-minus-target residual changed
from +9/-7 to +10/-7. This single result is consistent with a local persistent
offset but does not establish its cause, repeatability, or direction dependence.
No compensation is justified yet. Neighbour feedback was unchanged in this trial.

## Installed capability and experiment limitation

r34 compiles the Smoke pattern, one -8/+8 register change relative to its newly
captured anchor. It has no network-selectable reverse pattern. Repeating the CLI
after restarting would walk farther in the same direction, not revisit a target.
Changing a signed host manifest cannot override the controller's prepared plan.

A register return to 2405/1709 from the last measured 2407/1710 would have
target-minus-measured -2/-1. Thus register reversal and expected physical direction
are not interchangeable when residuals are present. Do not bypass the current
direction guard merely to label this a return test. Encoder feedback must show
what actually occurred; do not assume the offset persists during reversal.

## Bounded experiment design

1. Keep the existing firmware installed while designing/testing offline.
2. Choose a small fixed paired-target set around a freshly captured anchor, with
   pair sum 4114, reviewed per-leg travel and total excursion. Include the same
   middle target approached from both sides and at least three visits per side.
   Repositioning legs count as measured experimental legs, not invisible setup.
3. Simulate both constant offsets and reversal-dependent offsets, deadband,
   delayed settling, lost delivery, changed neighbours and export failure.
   Explicitly test cases where register direction differs from measured-to-target
   direction. A physically conservative envelope must govern any future policy
   change; do not simply remove direction checks.
4. Reuse the existing Matched campaign machinery where applicable, rather than
   building a second command protocol. Review its 12-leg offsets and envelopes
   against the fresh baseline before selecting it for a future candidate.
5. Before deployment, review the exact candidate and seek deployment approval.
   Preserve settings and credentials. No candidate has been staged or installed
   as part of this document.
6. Release a finite experiment only after the host supports the exact manifest,
   per-leg result export and faults. Account for the known lost-receipt-ACK case:
   the controller may have accepted continuation even when the host lacks its
   reply. Never equate a stopped host with a stopped controller.
7. Compare endpoint residuals by target, approach direction, speed/acceleration,
   initial measured pose and load. Report sample count, range, settling duration,
   neighbouring-joint changes and excluded/failed trials.
8. Fit only the simplest supported correction, respecting coupled targets. Keep
   a held-out sequence to test it. Do not infer stylus-tip accuracy from encoders.

## Completion criteria

- Same-target observations from both directions are exported and independently
  re-assessed; misses remain labelled misses even if the campaign completes.
- We can distinguish repeatable bias from spread and direction-dependent effects.
- A correction must improve held-out endpoint error without worsening travel,
  neighbours or failure rate. Otherwise retain raw commands and gather evidence.
- Camera, contact and physical millimetre-accuracy claims remain deferred.

## Current boundary

No new startup, movement, settings change or firmware deployment was performed
for this review. The previous single-movement authorization is consumed. Next
software work is an offline matched-campaign admission review and failure tests;
next hardware scope must describe the actual finite experiment, not promise an
unsupported reverse command on r34.

## Offline validation completed, 2026-09-20

Extended the existing simulator with an optional bounded reversal residual; no
native or installed firmware policy changed. Eight tests passed: constant bias,
direction-dependent bias, and six failures on the reverse leg (no response,
wrong direction, unsettled, neighbour movement, uncertain delivery, export failure).
All failure cases stopped before the next leg with zero physical packets.

Both synthetic 12-leg matched sequences completed and exported:

- Constant +10/-7 residual review:
  `wizard-20260920T153723988935Z-55795fa78e4b4a4b8b1b7bda15b7f509`.
- Reverse-direction +6/-4 versus forward +10/-7 residual review:
  `wizard-20260920T153724046630Z-67763ad1be5c4850a7f6963d7a808f19`.

The middle target has six visits, three per approach direction. Under constant
bias the reverse step moves +8/-8 even when target-minus-measured is -2/-1.
Under direction-dependent bias the middle-target residual differs by approach.
These are competing hypotheses, not hardware findings. They show why absolute
target direction alone is not a physical prediction, and why one offset fit is
premature. Existing measured-motion, neighbour, travel and export checks remain.

Next: validate the matched candidate's native admission/execution using these
same hypotheses and define live total-excursion bounds from fresh measurements.
The single-leg live runner must not silently accept twelve legs. No hardware
access, restart, installation, motion or compensation occurred during this work.

## Native controller hypothesis tests completed, 2026-09-20

Extended only the native test fake bus and relay, not production firmware. The
real native composition, authenticated socket transport, host signatures, record
transfer, independent assessment and verified disk exports now run both residual
hypotheses through all 12 matched legs. Six middle-target visits are confirmed,
three in each direction; exported errors distinguish constant +10/-7 from
direction-dependent +10/-7 versus +6/-4. Initial synthetic servo-12 position is
2415 for target 2405 with +10 residual; this is explicitly not a new live reading.

A frozen-actuator reverse test updates target readback but leaves measured
positions unchanged. The native controller reaches FAULT after two writes;
only the first successful leg receives an export receipt, and 100 additional
native polling cycles cause no third write. Existing lost-ACK regression cases
remain covered. Total: 16 native/socket/composition tests passed.

This establishes that the matched native implementation can discriminate these
synthetic cases. It does not validate physical reversal or qualify the installed
single-leg r34 image for twelve-leg execution. Next implementation work is a
bounded multi-leg host runner and candidate review with a local total-excursion
envelope; preserve per-leg measured assessment and receipt-loss reconciliation.
No hardware accessed and no firmware candidate installed in this step.

## Multi-leg host runner integrated, 2026-09-20

Refactored the single-leg runner to share bounded record transfer and per-leg
export/receipt sequencing. Its default reviewer still rejects anything except
one smoke leg, preserving the live r34 CLI's scope. Added MatchedRunner with
exact twelve-leg manifest matching, targets within 32 counts of the original
measured shoulder anchor, and review of every retained pose against that anchor
(32 selected / 2 neighbour counts). These are encoder-domain limits, not physical
clearance. Host checks withhold receipts; they cannot stop an in-flight command.

Eight matched/smoke/CLI tests passed. Constant and directional hypotheses complete
twelve legs; frozen reversal exports fault evidence and stops progression. Lost
receipt acknowledgement remains INCONCLUSIVE without retry: the controller can
already have sent the second command after accepting the first receipt. No false
controller-stop claim is made. This limitation must remain explicit at release.

MatchedRunner is not connected to the live CLI and is not live-qualified. Next:
review controller-enforced total excursion and receipt-loss reconciliation before
staging a candidate. No hardware access or installation occurred.

## Controller total-excursion enforcement — 2026-09-20

Changed source owner to freeze its anchor at the first measured baseline and
validate every campaign target against that anchor before any dispatch. Selected
joints are limited to 32 counts from the anchor; acquired measurements throughout
the campaign are limited to 32 selected / 2 neighbour counts. Existing absolute,
per-leg, direction, feedback, timing and receipt checks remain. An excessive future
target faults before the first write, avoiding cumulative small-step walking.

28 owner, excursion, matched-runner and smoke-runner tests passed. Dedicated native
cases prove a future target 33 counts away produces zero writes, the 32-count
boundary is admitted, and an observed 33-count excursion faults without another
write. Continued polling after faults produces no additional writes.

This is sampled encoder enforcement, not collision avoidance or guaranteed
mechanical stopping at a boundary. Source changes are not installed: the physical
arm remains on the previously reviewed r34 image. No hardware accessed. Next is
candidate staging/build/review for matched execution, with explicit deployment
approval required before any installation.

## r35 staged, compiled and reviewed — 2026-09-20

Pinned r34 sources were copied into a new immutable staging directory. Exactly
two headers differ: matched pattern selection and total-excursion enforcement.
Startup, settings and credential handling are unchanged. Two staging/envelope
tests passed. Default 4 MB / no-PSRAM ESP32 compilation succeeded.

- Stage: `wizard-20260920T155314447612Z-fffc642ca9b74451ae6d882ec653c090`.
- Compile: `wizard-20260920T155503166485Z-6860d55adcb74a55af2e93c63e8398ea`.
- Review: `wizard-20260920T155528364009Z-a5c2612298c14630b8b3b8ee32c95c54`.
- Application SHA-256: `c34ebe285db2e31be5c0f4ed35497cd13c280c82a130ac690e120c23f94cda91`.
- Application size: 1,155,456 bytes; slot headroom: 155,264 bytes.
- Largest reviewed individual stack frame: 1,072 bytes (not whole-stack proof).

Review verified pinned artifacts, unchanged bootloader/partition identities,
recovery backup compatibility, expected routes, absence of competing shoulder
routes, and compiled total-target excursion guard. Result remains deployable=false:
no live identity verification, installation or hardware action occurred.

Next: bind this exact candidate to the app-only installer and read-only startup
workflow. Separately complete receipt-loss reconciliation wiring for multi-leg
execution. Do not deploy or run twelve movements under prior r34 approval.

## r35 installer and receipt reconciliation wired — 2026-09-20

Installer pins the exact r35 hash/size, r34 predecessor, reviewed candidate export
and separate one-use journal. Retained installation/startup verification accepts
r35. Local preflight passed: no hardware access, no journal reservation, no
deployment authority. Existing settings/filesystem preservation checks remain.

The runner now optionally invokes one separately authenticated recovery read
after an uncertain receipt. It exports the snapshot and compares the accepted
receipt digest and campaign progress; it never resumes or replays. Native socket
testing confirms RECEIPT_ACCEPTED_NEXT_LEG_POSSIBLE when the acknowledgement is
lost after continuation, while the main report remains INCONCLUSIVE. Recovery
failure is recorded without retry. 142 regression tests passed.

No hardware accessed. Next approved deployment scope can be one r35 app-only
installation and one startup preserving settings/credentials, with read-only
startup checks and no movement. Multi-leg live entry-point/recovery-factory wiring
and explicit movement admission remain separate from installation approval.

## r35 installed; read-only startup passed — 2026-09-20

User approved proceeding with the stated app-only installation/startup/read-only
scope. Exactly one installation and one startup completed. Controller identity,
r34 predecessor, partition and filesystem checks passed before writing. Full app
readback matched `c34ebe285db2e31be5c0f4ed35497cd13c280c82a130ac690e120c23f94cda91`;
protected regions remained unchanged, preserving settings and credentials.

- Installation export: `wizard-20260920T160722206410Z-637492eb22a9486abe70bf932f6facb5`.
- Startup export: `wizard-20260920T160722548886Z-4565fe8bf4f34f0189e29a05d9ba53fd`.
- Boot: `30d4d1ac6fcd7b534054f47069deb946`.
- Observed IDLE / NOT_CONFIGURED, zero records, no storage fault; two status
  reads agreed. Free internal heap 151224 bytes, largest block 90100 bytes.

No preparation challenge, hold, torque or movement command was sent. Generic
startup checks do not establish fresh pose, matched-campaign route readiness,
physical clearance or endpoint accuracy. Installation approval is consumed.
Next: finish r35-specific live entry-point binding and offline tests, then obtain
explicit admission for the finite matched campaign with fresh reference capture.

## r35 live entry point ready for bounded admission — 2026-09-20

Added `scripts/run_r35_matched.py`, pinned to retained revision-35 startup evidence.
Its explicit live flag admits exactly the reviewed twelve-leg matched pattern,
including planned reversals, not an extra return or subsequent campaign. It uses
an exclusive fsynced per-boot claim before transport, fresh authenticated NEW
status and reference capture, and an independent one-shot recovery reader for
uncertain receipt delivery. No restart, flash or retry API is exposed.

Twelve CLI/runner tests passed, including reservation-before-transport, preserved
claims on failure, correct runner/recovery wiring, and native end-to-end scenarios.
Local preflight against startup export
`wizard-20260920T160722548886Z-4565fe8bf4f34f0189e29a05d9ba53fd` passed without
accessing hardware or reserving this boot. Fresh device state is still checked
at execution, not inferred from that local result.

Next approval scope: one twelve-leg matched shoulder campaign from a freshly
captured pose, with per-leg verification/export and one read-only reconciliation
if a receipt acknowledgement is uncertain. No restart, firmware/settings change,
automatic retry, extra return or follow-on campaign. Physical clearance must cover
the finite sequence; encoder envelope is not collision avoidance. No movement
was sent while implementing this entry point.

## First live matched campaign: stopped on reverse response — 2026-09-20

User explicitly confirmed clearance and approved the finite campaign. Executed
once on existing r35 boot, without restart, installation or settings changes.
Run export: `wizard-20260920T161229533473Z-1e7293b38c764a9fb997ede23c57fcb4`.

Fresh anchor positions (IDs 11–17): 2047,2406,1710,2904,1591,2041,2047.
First leg target 2389/1725, measured endpoint 2398/1718: actual -8/+8 counts,
residual +9/-7. Independent result SETTLED_MISS exported and acknowledged:
`wizard-20260920T161228234411Z-6fadfc9699cc4ddbbb6ccaf400961169`.

Reverse leg target readbacks became 2397/1717. The fault's last valid measured
positions were 2398/1716: relative to the first endpoint, 0/-2 counts. Controller
faulted in Observe with NO_CLEAR_RESPONSE after exactly two attempted writes.
Fault export: `wizard-20260920T161229453486Z-cd5f6515301d42d9907b7ebd5f0ee008`.
No second receipt, third movement, retry or extra return was sent. Overall run
INCONCLUSIVE; this is not twelve completed measurements. The retained fault pose
is historical, not a fresh current-position claim.

Interpretation: target-register reversal was observed but did not produce the
minimum measured response on both paired servos. The constant-bias model is not
adequate to predict this reversal. A deadband/direction-dependent response is a
hypothesis, not an established mechanical cause. Do not fit a universal offset
from the successful forward steps or weaken the response criterion to mark this
as successful movement.

Next offline work: reproduce the observed asymmetric 0/-2 reversal in the native
fixture; inspect whether early stable samples terminate observation too soon;
design a bounded diagnostic that distinguishes delayed response from local
deadband. Do not replay the consumed campaign. Any new hardware experiment must
use fresh admission and specify the changed observation or displacement policy.

## Visual observation incorporated; diagnostic changes tested — 2026-09-20

Operator reports seeing slight movement during the failed reversal. Record this
as observed movement, not a contradiction of NO_CLEAR_RESPONSE: that criterion
requires at least two counts of final displacement on both servos. Historical
feedback showed 0/-2 relative to the prior endpoint, not proof of zero transient
motion. Failed-leg intermediate samples were not exported by installed r35, so
the actual transient/return hypothesis cannot be confirmed retroactively.

Offline source changes now wait at least two seconds after the single write
before terminating a settled NO_CLEAR_RESPONSE assessment. Other faults still
stop immediately; no resend was introduced. Terminal assessment failures retain
the baseline and acquired observation array for authenticated chunk export with
STOP outcome. Failed records cannot earn continuation receipts. This does not
yet cover every early acquisition failure with a full timeline; compact faults
remain available. Accepted predecessor bytes are cleared to avoid misattribution.

Readable result exports now separate sampled peak absolute movement, sampled
signed range, final net displacement, sample count and observation span. Peaks
are sampled lower bounds, not continuous-motion measurements. Runner downloads
NO_CLEAR_RESPONSE history without signing a receipt; older firmware may report
history unavailable, which is recorded without retry.

42 native/socket/owner/codec tests passed. A synthetic +4/-4 transient settling
back to 0/-2 is correctly exported as peak movement 4/4 and final movement 0/-2;
it remains a stopped campaign with only two writes. A delayed-response model
previously vulnerable to early stable-sample termination completes without resend.
These validate competing explanations, not the physical cause of the live event.

Installed firmware remains r35. Next is review/staging/build of these diagnostic
changes and compatibility checks (STOP result encoding extends the codec), before
seeking approval to install and repeat a finite test. No hardware accessed here.

## r36 diagnostic update built, reviewed and installed — 2026-09-20

User approved the build and diagnostic update. Staged exactly two changed headers
from pinned r35: owner observation/STOP record retention and session read-only
access to those records. Movement pattern, limits, startup, settings and credential
handling are unchanged. STOP encoding extends the existing result codec; host
tests reject continuation signing for such records.

- Stage: `wizard-20260920T161915542753Z-9602dd9f67c24b618e3f4706d3fed1c0`.
- Compile: `wizard-20260920T162104226298Z-6457ab96d6274648bdfeb735db1e2b74`.
- Review: `wizard-20260920T162126924287Z-507358b7b1d44303ad72a448d8cd046f`.
- App SHA-256: `1e8564d204aa773149ad54fc58fd70bee294bdfdea74e8d29b2f07de19417dfd`.
- App bytes: 1155600; slot headroom 155120; largest individual reviewed frame 1072.
- Installation: `wizard-20260920T162521983936Z-f39644314b8447c4a957a44c2625642a`.
- Startup: `wizard-20260920T162522354165Z-7862b2f2a8044447a0679268108c24fc`.
- New boot: `63ddc0b62b2bee091ad4b9fbef4e9bb3`.

44 installer/CLI/staging/host-codec tests passed; local preflight passed before
installation. One app-only write and startup completed, with exact readback and
unchanged protected-region digests. Settings/credentials preserved. Read-only
startup checks returned stable IDLE, zero records and no storage fault.

No movement or preparation command sent in this update. r36-specific runner is
wired to the same finite matched sequence. Next is a fresh admitted campaign to
capture actual peak/net movement and failed-leg history; no assumption that the
new observation policy will make the physical reverse move succeed.

## r36 physical diagnostic: slight response captured — 2026-09-20

Approved bounded run executed once, no restart/retry. Run export:
`wizard-20260920T162633849060Z-2b7594830e634c8e9739a441a2ff6ae0`.
Stopped on leg 0 after one attempted write, NO_CLEAR_RESPONSE; no receipt or
later leg sent. Full STOP record successfully exported:
`wizard-20260920T162633791002Z-eee288e20c1446ba8b5d489b339b7985`.
Compact fault: `wizard-20260920T162633535769Z-44ed7c2cc75a4f78b7dcbf0c02b0c191`.

Fresh measured pair 2398/1716; target registers changed 2397/1717 -> 2389/1725.
18 acquired observations spanning 1,943,726 microseconds show servo 12 unchanged
at 2398; servo 13 progresses 1716 -> 1717 -> 1718 then remains there. Sampled
peak movement 0/2 counts; final net 0/+2. No sampled transient-return pattern or
late extra response in this window. Sub-sample movements remain unobservable.
The first acquisition occurs after dispatch; observation span is not exactly
the controller's two-second dispatch-to-decision interval.

Important experiment context: 2389/1725 is the SAME forward target as the first
r35 campaign leg, whose endpoint was 2398/1718. The preceding r35 reverse command
left measured pose at 2398/1716, so revisiting that target produced little physical
displacement despite an eight-count register change. This is consistent with a
history-dependent local response, not proof of failed communication or a fixed
universal compensation model. It supports the operator's report of slight motion
without claiming that this new run reconstructs the previous visual event.

Next: account for prior target/pose history in experiment selection. Distinguish
settled target revisits with little response from tests intentionally demanding
new physical displacement. Do not merely lower the movement criterion or replay
the same relative sequence. Plan a bounded excursion beyond the previously visited
target with fresh measurements and unchanged overall travel limits; retain this
as a proposed experiment, not an automatic command. Current campaign is consumed.

Follow-on experiment design now lives in `SHOULDER_VARIANT_MOVEMENT_MATRIX_PLAN.md`:
12 legs covering 4/8/12-count register changes in both directions, two repeats,
one fixed speed, with explicit small-response classification. Its initial offline
review and ten tests passed; installed r36 progression has not been relaxed.

The follow-on matrix now has offline native preparation, a typed small-response
outcome, matching host receipt rules, and a loopback runner. See the matrix plan's
2026-09-20 integration section for simulated full-run and fault-stop evidence.
No matrix firmware has been staged or installed; r36 remains unchanged.
