# Current working goal: hands-on arm control

User direction: prioritize actual supervised movement, telemetry review and
progressive complexity over additional general scaffolding.

Work in this loop: select one bounded motion, show its direction/speed, acquire
the current baseline, dispatch once, retain the full observation window,
compare requested/reported response and operator observation, then choose the
next separately admitted move. No automatic replay of uncertain commands.

Standing operator report: arm is stationary, powered and clear unless the user
says otherwise. Contradictory telemetry, a fault, interruption, unexpected motion
or changed setup invalidates that assumption. Serial closing is not an E-stop.

Immediate sequence:

1. Finish the existing telemetry pacing fix (no additional framework work).
2. Run one slow +5-degree wrist test from its newly acquired baseline, within
   the existing +/-10-degree software envelope. This is a new reviewed command,
   not an automatic return following the previous trial.
3. Review transport, five-second capture, endpoint/dwell and other-joint changes.
   Record operator observation; retain failures honestly and export results.
4. Repeat bounded wrist motions to establish reliability; change only one
   variable at a time. Do not silently introduce faster speed or larger travel.
5. After repeatable single-joint results, plan small isolated tests of other
   joints, then short multi-step non-contact sequences with telemetry per leg.
   Their swept clearance and command limits need review before enabling them.

Success means demonstrated, repeatable command/response behavior and usable
telemetry for successive moves, not merely tests passing or bytes being sent.
Board mapping, keyboard/phone contact and unrestricted sweeps remain separate.

Implementation checkpoint: observational read starts are now paced at least
10 ms apart, retaining the existing read/byte ceilings and fixed deadline.
This addresses short USB reads exhausting 512 calls early, without claiming
device timestamps or discarding bytes. Regression: 250 tests passed in 53.16 s,
`../runs/observational-read-pacing-20260913-01.xml`.

The product goal is still the existing paused movement-characterization goal;
the available goal API cannot rename or replace an unfinished goal. This file
records the user's updated working priority without falsely marking it complete.

## Live checkpoint: +5-degree wrist trial

Attempt `operation-22687c57cccb43e8a0f0811e8ec905b6` completed its owned
capture sequence with consistent reconstructed data. Retained post telemetry:
57,816 bytes, 279 complete pose samples. The target was selected from baseline
-0.072097097 rad plus 5 degrees. Reported final target error was approximately
-0.254 degrees. The analyzer found target dwell and no unexpected other-joint
change; its only outstanding issues were missing operator observation/coverage.
This is not a calibrated-accuracy claim. No subsequent motion has been sent.

Next: obtain the operator's observation of this specific test, record it through
the wizard, then select the next bounded repeat if the combined result supports it.

### Requested repeat

User requested another move. Attempt
`operation-e75e81c17c64474e99e46d45f5aaac8d` staged another +5-degree wrist
increment but was `HELD_BEFORE_WRITE`: no write attempted, zero confirmed
command bytes, no pending I/O or owned handles after close. One-second baseline
retained 10,688 bytes. Offline reconstruction reproduced
`INVALID_JOINT_RECORD`: the stream began with the partial tail
`,"tE":65,"tT":-13,"tR":20}\r\n` before its first complete pose record.
Latest complete baseline wrist remained 0.010737866 rad. Do not treat this
partial frame as a pose or bypass validation. No automatic retry occurred.
Logs exported by `operation-f39b24b8bb874784b97437b1845887a4`.

### Opening comma-fragment correction

The frame-boundary helper now recognizes a comma-led first-line remainder only
when its remaining object parses as unique known numeric fields with finite
values. Unknown fields, duplicate keys, strings, booleans, nested values,
nonfinite numbers, malformed objects and interior fragments remain rejected.
Original bytes and acquisition times are unchanged; the leading fragment is
explicitly unobserved, never interpreted as a pose.

Offline reconstruction of the failed attempt now finds 51 complete stable
baseline poses, excluding only bytes [0,28) and the unterminated suffix from
the analysis interval. All 10,688 original bytes remain retained, SHA-256
`f921677a642b20c92c9a4c90bd5f7573095375271468d6b26aef81c1fc15c0d6`.
This historical analysis is not replay authorization: the next attempt must
acquire a fresh baseline through the wizard.

Verification: 259 observational/framing tests passed in 52.94 seconds
(`../runs/observational-comma-fragment-20260913-01.xml`), plus 49 shared
telemetry/first-motion/endpoint capture tests in 1.42 seconds
(`../runs/telemetry-framing-regression-20260913-01.xml`).

### Live repeat after framing correction

Attempt `operation-dd8557b674a5490dabdeb5b5f147b24f` completed with
`COMPLETED_DATA_CONSISTENT`. Fresh baseline wrist 0.010737866 rad;
commanded absolute target 0.09800432859971647 rad (+5 degrees), spd 20,
acc 1. Post capture retained 57,572 bytes and 280 complete pose records.
Reported final target error was -0.0044315006 rad (about -0.254 degrees),
with target dwell and no unexpected other-joint change detected. The only
remaining assessment issues concern the not-yet-recorded operator observation.
No return or additional command was sent. Do not claim calibrated accuracy.

### Opposite-direction repeat

User requested another test. A further +5 degrees from the previous reported
5.36-degree wrist position would exceed the +/-10-degree envelope, so the
announced and staged increment was -5 degrees toward neutral instead.
Attempt `operation-8782fb2d9d024ddaa58b0c68a07e2f8f` produced consistent
retained data with 280 post-command pose samples. Baseline 0.093572828 rad;
target 0.006306365400283523 rad, spd 20, acc 1. Final reported error was
+0.0167033466 rad (about 0.96 degrees). No final target dwell was established:
the test remains HELD, not a successful target-completion qualification.
Operator observation is pending. No corrective or retry command was sent.
