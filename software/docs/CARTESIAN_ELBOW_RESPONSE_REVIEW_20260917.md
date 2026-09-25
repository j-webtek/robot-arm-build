# Cartesian elbow response review

## Decision

### Matched-target design correction — 2026-09-17 16:23 UTC

Read-only preflight `wizard-20260917T162325952214Z-c07ff8a02f9e4d7f9a0a60b30a73898d`
screened a proposed high-side approach to the previous reverse target. No motion
was sent: because the current pose resulted from overshooting that very target,
the proposed command would simply resend the previous failed goal. That is not
an independent opposite-side approach. The temporary matched-target native mode
was removed; regression tests explicitly reject that mode (35 tests pass).

A valid matched-target experiment requires an explicit conditioning leg to a
different goal, a reviewed stable reported starting state, and only then the
comparison target. Conditioning and measurement must have distinct trial roles,
with no automatic chaining after a failed conditioning endpoint. Choose a common
target with adequate approach distance on both sides; the existing narrow interval
may not supply that distance given the roughly 3-degree lifting shortfall. Screen
any necessary modest corridor extension and its complete path separately rather
than falsely label a same-goal resend a matched comparison. No compensation has
been fitted or applied.

### Opposite-direction comparison — 2026-09-17 16:21 UTC

Added a named +3-degree elbow probe (CLI lift parameter `--elbow-degrees -3`),
constrained to the prior joint interval [1.4942677294,1.581534192] rad and sampled
endpoint displacement <=20 mm. Speed 20 / acceleration 1 unchanged. Only its
elbow excursion monitor permits 4 degrees; other scopes retain existing bounds.
34 targeted tests passed before execution; 38 including trace classification
passed afterward. No generic angle API, torque change or automatic return added.

Preflight: `wizard-20260917T162041920655Z-83fd3efd18db4ae9b91403d78b318b9b`.
One live trial: `wizard-20260917T162113108962Z-9d5d681c4a304b0195449e2e0ab3f489`.
Baseline 1.510971076 rad; target 1.5633309535598299; reported 1.572330308.
**+3 degrees requested, +3.5156 reported**, overshoot 0.5156 degrees / six predicted
counts. Other joint readings unchanged. Cartesian endpoint residual 2.8439 mm;
strict arrival still unverified, completion deadline exceeded. No second command.

Analysis: `wizard-20260917T162143607181Z-2688afc5a5a74ddab71bf7d5cbe16597`.
Last reported change 1.745 s after dispatch; unchanged final interval 7.970 s.
This contrasts with the two lifting trials' approximately 3-degree shortfall.
Direction/load/start pose or displacement may matter; this is not a clean
same-amplitude/same-target comparison and cannot isolate a single cause. It argues
against blindly applying one direction-independent offset. Next plan a matched
target comparison inside this same corridor before fitting compensation.

### Trace timing analysis — 2026-09-17 16:18 UTC

Verified both 5-degree source exports and analyzed all 32 retained rows per trial.
Results: `wizard-20260917T161850687498Z-793eee657f0642fea2b7222158d515b4`.
Reproduce with `software/scripts/analyze_elbow_traces.py <trial-export-id> ...`.

| Trial | Last reported change after dispatch | Unchanged final interval | Final angular shortfall |
| --- | ---: | ---: | ---: |
| First -5 degree lift | 0.906 s | 8.918 s | 3.0664 degrees |
| Side-view -5 degree lift | 0.609 s | 9.099 s | 2.9785 degrees |

Each final two-second window contains seven samples with zero reported elbow
span. Classification: REPORTED_PLATEAU_WITH_SHORTFALL. Three analyzer tests pass,
covering plateau, ongoing change and invalid chronology. Host timing is not servo
acquisition timing; unchanged samples cannot independently prove physical settling.
Nevertheless, neither trace supports extending the timeout as the primary remedy.

Next discriminating candidate: one bounded opposite-direction elbow trial at the
same speed/acceleration, screened from its fresh pose and kept inside the recent
tested elbow interval. This is not an automatic return or an admitted command;
it needs explicit target/path construction and the existing one-send checks.
Compare residual sign/magnitude against these descending trials. A directional
comparison helps separate a direction-dependent shortfall hypothesis from a
single constant coordinate offset. Do not yet apply a 3-degree correction.

### Operator confirmation — current interpretation

For the side-view repeat at 16:14 UTC, the user confirmed: "i did see it!"
Physical movement therefore corroborates the reported direction of response.
This supersedes the pending observation and blanket nonresponse framing below.
The current issue is incomplete travel: -5 degrees requested, about -2.02 degrees
reported (preceding trial about -1.93). Neither endpoint was verified. Analyze
the saved traces for ongoing travel versus stable shortfall before selecting a
timing or local compensation experiment. Do not assume a defective actuator or
a universal 3-degree correction. Earlier inspection/support directions remain
fallbacks, not prerequisites imposed despite this new evidence.

### Side-view repeat — 2026-09-17 16:14 UTC

After the operator agreed to a side-view bounded repeat (not a larger movement),
one further 5-degree elbow-only lift was sent from a fresh identity-matched
baseline. Preflight: `wizard-20260917T161349443525Z-921dd685e40549dd9f3a9bd1c5fb6d4d`.
Trial: `wizard-20260917T161418612421Z-8ee31488c2074a1aa540575121c14c54`.
Elbow start 1.547786615 rad, requested 1.4605201524002835 rad, final reported
1.512505057 rad: **-2.0215 degrees reported for -5 requested**. Other joints
reported no change. Residual 34 predicted encoder counts, endpoint error 16.4258 mm,
completion deadline exceeded. No return, extra command or configuration change.

The two 5-degree trials report similar approximately 2-degree responses, leaving
approximately 3 degrees of shortfall. That is a repeatable observation at these
two starts, not proof of deadband, a global compensation model, or actual tip
accuracy. Side-view physical observation for this latest trial is pending.

### New response evidence — user-requested visible 5-degree lift

The user reconfirmed powered/secured/clear state and requested a more visible
test after questioning their earlier observation. Added an explicit 5-degree
elbow-only lift, keeping speed 20 and acceleration 1 unchanged; no torque change.
Its sampled reference path is capped at 35 mm endpoint displacement; only the
elbow excursion monitor is extended to 6 degrees for this named test. Existing
2-degree and Cartesian scopes retain their original bounds. 32 targeted tests
passed before execution. This is a specific diagnostic, not arbitrary expansion.

Preflight export: `wizard-20260917T161120441186Z-a13290402f2a4fb1892bdcdb246b64a9`.
Executed once: `wizard-20260917T161146850072Z-bc2cb8169f9e450ab1e9ccbcb27d64fd`.
Baseline elbow 1.581534192 rad; target 1.4942677294002835 rad; last reported
1.547786615 rad. The elbow now reports **-1.9336 degrees of movement**, versus
-5 degrees requested (-22 observed counts versus -57 predicted). Other joints
reported no change. Endpoint error remained 16.9104 mm; arrival was NOT verified.
No retry or return was sent. Operator observation of this latest trial is pending.

This supersedes a blanket claim of no elbow response: the larger diagnostic
produced partial reported response. Investigate the response trajectory and
shortfall rather than assume a dead actuator or immediately fit compensation.

Manufacturer diagnostic research: the ST3235 documentation describes richer
servo-bus health reads, but no verified mapping of those reads through this
installed arm's JSON interface was found. Prepared an unsent
[diagnostic brief](ELBOW_SUPPORT_DIAGNOSTIC_BRIEF.md) with the exact watched command,
evidence and questions for a supported non-destructive diagnostic. Physical
inspection remains pending. No device access occurred during this research.

### Read-only command-path inspection — 2026-09-17 16:04 UTC

Fetched only `/` from the identity-matched controller; no JavaScript executed and
no command endpoint called. The served interface is 54,153 bytes, SHA-256
`2f93fdc878a0ecc24d8e6e3a3c5803184165a6d2ec3cf265d86c41e2408e75e8`.
Its own controls use GET `js?json=...`, matching our transport path, and expose
CMD_SINGLE_JOINT_CTRL. This reduces the likelihood of using the wrong HTTP route;
it does not prove execution of the elbow handler or identify the installed binary.
Verified export:
`wizard-20260917T160417646909Z-2677896abec143d782834a972a14bd53`.
Reproduce with `software/scripts/inspect_arm_interface.py` (home-page read only).

Re-downloaded the official reference archive and rechecked its pinned hash.
`uart_ctrl.h:16–22` passes joint/rad/spd/acc directly. The single-joint dispatcher
selects elbow control, and `RoArm-M3_module.h:353–360` converts radians, clamps
to counts 1024–3071 and calls `WritePosEx` when returnType is nonzero. The watched
target (count 2032) is inside that clamp. No elbow-specific suppression was found
in these reference functions. Installed equivalence remains unverified.

The remaining useful physical check is a power-isolated inspection of the elbow
servo cable/connectors and visible binding, with the arm supported before power
removal. Do not disconnect servo wiring under power, force joints, or infer a
failed servo from this evidence alone. If inspection is normal, seek a supported
servo diagnostic/installed-version identification rather than blind tuning.

### Watched follow-up — 2026-09-17 15:59 UTC

The user confirmed they were watching; one fresh-baseline, elbow-only -2 degree
trial was executed. The user then reported **no visible movement**. This is an
observation at that test's scale, not a precision measurement or proof of a dead
servo. It corroborates the absent reported response and makes a purely stale-
feedback explanation insufficient to assume successful physical motion.

- Preflight: `wizard-20260917T155853552107Z-2f0080763b494b5988b4d4ee8ec6f794`.
- Trial: `wizard-20260917T155919439246Z-4bd875f42550457a956eab38b96b4a25`.
- Baseline elbow 1.581534192 rad; requested 1.5466276069601133 rad.
- Expected reconstructed count change -23; observed 0. Other joint reports also
  remained unchanged. Endpoint error 11.0302 mm; completion deadline exceeded.
- No retry, return, larger command, torque toggle or configuration write followed.

The baseline differs from the earlier 1.596874 rad reading; the cause of that
inter-test change is unknown and must not be attributed to this watched command.
The native path sends the reserved payload to `/js?json=...`; an HTTP receipt is
not an actuator execution acknowledgement. Official documentation still identifies
T101 joint 3 as elbow and `rad` as radians. No indexing/unit mismatch was found.

Next investigate controller/actuator state and the installed command handling,
using supported diagnostics or power-isolated hardware inspection. Do not change
PID, midpoint or torque limits to compensate for nonresponse. Missing voltage and
torque-state telemetry prevent ruling out power/configuration causes in software.

### Operator observation update — 2026-09-17

The operator answered **unsure / did not watch that joint** for the earlier
elbow-only trial. This is not confirmation of either movement or nonmovement.
No additional motion was issued on receiving that answer. The offline product
keyboard interpolation and endpoint suite have since passed, but cannot resolve
this physical feedback ambiguity.

Next discriminating experiment: coordinate one watched, bounded elbow-only trial
using the existing diagnostic, after its fresh baseline and preview checks pass.
The operator should watch the elbow hinge (between the upright upper arm and
forearm), without touching the arm, and report moved / still / unsure. Do not
expand the displacement or automatically repeat/return. Compare that observation
with the saved commanded target and reported joint change:

- Visible movement with unchanged telemetry: investigate feedback freshness or
  reporting before relying on automatic endpoint completion.
- No visible movement and unchanged telemetry: investigate actuator state,
  command handling or mechanics; do not fit compensation to nonresponse.
- Visible movement and corresponding telemetry: review endpoint residual and
  repeatability before progressing to coordinated ghost routes.
- Unsure: retain uncertainty; do not claim restored elbow operation.

This is a request for a specific diagnostic observation, not renewed general
permission or a camera prerequisite. Existing standing setup authorization
continues to apply.

Do not apply Cartesian compensation or repeat vertical moves yet. Two bounded
tests produced the predicted wrist response but not the predicted elbow response.
The next investigation should isolate elbow command delivery/actuation, not fit
a global XYZ correction from these observations. No torque, PID, firmware or
servo configuration was changed in this work.

## Raw-response audit — follow-up

Re-read the original trial attachments and decoded every retained raw response.
Each decoded response matched its saved SHA-256. Rows without a retained raw
response were counted separately, not interpreted as successful observations.

| Trial | Retained feedback rows | Rows with raw response | Distinct raw payloads | Reported elbow radians | Raw elbow load |
| --- | ---: | ---: | ---: | --- | --- |
| +2 mm Z | 33 | 32 | 1 | 1.593806039 | 41 |
| +5 mm Z | 34 | 33 | 2 | 1.596874 | 101 |
| Elbow-only -2 degrees | 32 | 32 | 1 | 1.596874 | 97 |

The elbow-only request retained in the export is exactly T101, joint 3,
rad 1.5619674149601133, spd 20, acc 1. The official command documentation
identifies joint 3 as elbow and `rad` as radians; no joint-index or degree/radian
mix-up was found in that request. This does not prove installed firmware handling
or that the underlying servo received its goal.

All 32 post-command elbow-only raw payloads were byte-identical. Elbow load
differs between campaigns but does not vary within the retained observations of
any of these three trials. Thus there is no changing per-sample elbow load signal
here that establishes fresh servo acquisition. HTTP response time is not servo
acquisition time. Identical data is compatible with both a stationary joint and
cached feedback; it does not diagnose either one.

Consequently, use **no reported elbow response**, not **proven actuator failure**.
The earlier source review documents a cached-position failure mode in the pinned
reference, but installed firmware equivalence remains unverified. Resolve this
ambiguity using independent observed motion or supported servo-read diagnostics;
do not gather another identical movement batch or increase compensation to force
a result. The missing torque-switch and voltage fields remain unknown.

Attachment hashes for reproducibility, in table order:

- `ec5cdaac84cea54df8b2f1aec69ed03cd6d5066eed755417112173d2d2233934`
- `f3b21b21d980e05031f0c61840b6664e1bf0ee698e8229a15a15172ed2156482`
- `f3d3e5b480b6f697d5ac043d9937233aab01894f2db33780d2f8bd14a234b16a`

Sources: [official joint command documentation](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control)
and the local [servo-read freshness review](WRIST_DIRECTIONAL_TRACE_REVIEW_20260913.md).

## Wizard review and current status visibility

The Arm section now includes **Review saved Cartesian/elbow trial (no movement)**.
Enter this workspace export folder name to review the elbow-only failure:

`wizard-20260917T135935556409Z-931dbc16f2cb451d90eeea4391da9295`

The action verifies the source export and attachment hash, recomputes expected
joint response from the retained command, displays commanded versus uncommanded
joints and preserves the original outcome. It does not connect, retry, approve
motion or apply compensation. Use the normal wizard log export afterward to
retain this review with its source hashes. Hardware and rehearsal modes both
support the same read-only action.

The Wi-Fi feedback card now shows optional elbow torque switch, raw load and
supply voltage. Missing fields display NOT REPORTED, not OFF or zero. This
matches the optional T105 fields described in the
[official feedback documentation](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control).

Fresh read-only export
`wizard-20260917T140632454881Z-ee50004ac26141f2b8df4e405b84ac9d`
contained elbow raw load 97, but no torque-switch fields and no supply voltage.
This does not establish torque enablement, available torque, wiring condition,
mechanical freedom or calibrated contact force. No movement was sent during
this status/review integration. An observational question about elbow motion,
noise or visible obstruction has been presented to the operator; no answer is
assumed and no manual manipulation of the powered arm is requested.

The saved-trial review was exercised on the actual retained elbow export and
returned NO_REPORTED_RESPONSE for elbow (-23 predicted counts, 0 reported),
with zero device opens and zero motion commands. Service tests verify normal
wizard publication/export and actual JavaScript rendering. Tampered exports,
arbitrary paths and inconsistent authority claims are rejected.

## What was checked

The official reference archive was downloaded in memory and its SHA-256 checked
against `a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
The installed firmware binary has NOT been independently matched to that archive.

Source: https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip

- `RoArm-M3_module.h` 531–555 and 723–731: inverse kinematics matches our regular
  branch calculation, including pitch handling.
- Lines 749–758: Cartesian control computes all seven servo targets and issues
  one synchronous position write.
- Lines 895–936: T104 interpolation ends with an explicit final-goal write.
- Config lines 94/96: command midpoint 2047, range 4096 counts.
- Module lines 42–62: feedback conversion uses the equivalent of midpoint 2048
  for base, shoulder, wrist pitch and roll. Elbow uses offset 1024.
- Lines 306–398: command angles are rounded to counts and applicable limits are
  clamped. The tested elbow targets are inside those reference limits.

The midpoint difference explains some one-count angle residuals. It does not
explain an unchanged elbow nine counts from target, or a 24-count elbow miss.
Predicted bus targets are a software reconstruction, not captured bus writes.

## Live results

Both commands retained pitch/roll/gripper and requested positive controller Z.
No return or automatic retry was sent. These are controller-reported positions,
not camera-measured physical tool-tip coordinates.

| Diagnostic | Expected elbow count change | Reported elbow count change | Expected wrist count change | Reported wrist count change | Last XYZ target error |
|---|---:|---:|---:|---:|---:|
| +2 mm Z | -9 | 0 | +8 | +8 | 4.106 mm |
| +5 mm Z from new baseline | -22 | +2 | +22 | +22 | 11.755 mm |

The +5 mm target was Z 217.4470354 mm; last reported Z was 205.72691 mm.
There were 33 accepted observations in that trial. It ended
`COMPLETION_DEADLINE_EXCEEDED`, not successful arrival. The read-only follow-up
was retained separately; its successful geometric preview is NOT qualification
to execute another move after this failed test.

All export names below are under `software/runs/wizard-exports`:

- Earlier +2 mm trial: `wizard-20260917T134750110509Z-43eed641415c4961b4fe26655bd3b341`.
- +5 mm read-only preflight: `wizard-20260917T135319013506Z-05f2bc874dac4959a5f9152860ef039f`.
- +5 mm live trial: `wizard-20260917T135344915424Z-aaae27810b914109bfbc1328fc1fd25d`.
- Read-only follow-up: `wizard-20260917T135428741452Z-d7308fb8acaf445895e41c535e221841`.

## Software changes and verification

- Added pinned servo-count conversion and per-joint response comparison to the
  existing firmware reference module and Cartesian endpoint result.
- Reports distinguish ideal angle error from predicted servo-count error.
- Added exactly one alternative diagnostic size: +5 mm. Existing three-degree
  modeled joint-excursion and one-degree adjacent-sample limits remain unchanged.
  Arbitrary step sizes and automatic returns are still unsupported.
- 143 tests passed across reference conversion, preview, Cartesian transport and
  wrist regressions before the +5 mm live trial.

## Next finite diagnostic

### Update: elbow-only diagnostic completed

One T101 joint-3 command was sent with fresh baseline, target
1.5619674149601133 rad (baseline 1.596874 minus 2 degrees), speed 20 and
acceleration 1. No command was sent to the other joints.

- Predicted elbow bus target: count 2042; initial and final reconstructed count:
  2065. No reported elbow movement occurred during the observation window.
- Other joint readings remained unchanged. The predicted endpoint was about
  11 mm above the starting endpoint; reported XYZ stayed at the starting pose.
- The run ended `COMPLETION_DEADLINE_EXCEEDED`, never arrival. There was no
  return, retry, larger movement, torque/PID change, reset or firmware write.
- Preflight export: `wizard-20260917T135911797580Z-8ada5e682ddc47c4ac2040224b2567a9`.
- Live export: `wizard-20260917T135935556409Z-931dbc16f2cb451d90eeea4391da9295`.

This contradicts the hypothesis that the failure occurs only in Cartesian
interpolation or synchronous multi-servo writes. It does NOT establish whether
the cause is installed command handling, torque/configuration, servo communication,
mechanics or feedback validity. Stop further movement attempts while this is
unresolved; do not attempt to overcome it by increasing displacement or torque.

The pinned public command list exposes feedback T105 but no general read-only
servo-register API. T210 changes torque, T503 changes PID and T502 changes the
servo middle position; none were issued. Installed torque-enable state and
firmware binary remain unknown. The configuration history says delivered firmware
was unchanged, which does not attest its exact version.

The initial elbow-only export includes hypothetical reference count targets for
uncommanded joints in its diagnostic comparison. Those are NOT transmitted
commands; the exact retained command contains only joint 3. Subsequent reports
now explicitly mark commanded joints and leave uncommanded count targets/errors
null, while retaining their observed drift.

Next: resolve elbow control/actuator state through read-only evidence or a safe
hardware inspection. Keep software onboarding and holder/fixture work moving,
but do not qualify coordinated routes or contact until elbow response is restored.

### Original diagnostic sequence (retained for traceability)

1. Inspect available read-only servo/firmware information and retained startup
   configuration. Determine whether installed behavior differs from the pinned
   reference or elbow actuation is disabled/limited. Do not infer torque enable
   or electrical condition from a normal Wi-Fi response.
2. If no fault indication is found and a direct-joint trial can be admitted,
   compare one bounded elbow-only command against its quantized expected target,
   with fresh baseline, no other-joint commands, and an absolute timeout. Retain
   other-joint observations and stop after that one trial.
3. If direct elbow control succeeds but T104 does not, investigate the installed
   Cartesian/synchronous-write path. If direct elbow control also fails, stop
   increasing commands and inspect actuator/configuration/mechanical causes.
4. Qualify a useful noncontact route only after coordinated response is restored.
   Keep holder/fixture development independent; do not claim board accuracy from
   these tests or enable contact based on a passing numerical preview.
