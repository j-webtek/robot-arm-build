# RoArm-M3 Pro elbow nonresponse — diagnostic brief

2026-09-17. Draft for review; not sent to the manufacturer.

Update: a subsequent 5-degree side-view trial produced about 2.02 degrees of
reported movement and the operator confirmed seeing it. An earlier 5-degree trial
reported about 1.93 degrees. The immediate investigation is now repeatable
undershoot, not total nonresponse. This unsent brief preserves the earlier
2-degree failure; revise its scope to include these newer trials if support is
later needed. No support escalation is currently required by this document.

## Observed problem

A bounded T101 elbow-only request returned HTTP 200 but no observed elbow motion
and no reported joint change. Other-joint motion was not commanded. The operator
watched this test and reported no visible movement. This is not a diagnosis of a
failed servo; installed command handling, actuator state and mechanics remain open.

Exact request:

```json
{"T":101,"acc":1,"joint":3,"rad":1.5466276069601133,"spd":20}
```

Baseline and final elbow: 1.581534192 rad. Requested change: -2 degrees, approximately
-23 encoder counts under the published conversion. Observation window: 10 seconds;
32 saved feedback rows; result COMPLETION_DEADLINE_EXCEEDED. No automatic return,
retry, torque/PID/midpoint change or firmware flash was performed.

The served controller page uses GET `js?json=...`, as does our client. The exact
installed firmware version is unknown. The pinned public July 2026 reference
accepts this joint number and target without clamping it. An HTTP response does
not demonstrate that the installed handler sent the servo goal.

## Diagnostic visibility gap

Current T105 responses include angles and raw loads but omit torque-switch and
voltage fields. Servo acquisition success, temperature, current, protection status
and register settings are not exposed by our verified interface. Do not interpret
those missing values as OFF or zero, or send guessed register commands.

Waveshare's [ST3235 documentation](https://www.waveshare.com/wiki/ST3235_Servo)
describes servo-level feedback for position, load, speed, voltage, current and
temperature. Its examples use the servo bus/library; this is not evidence that
the assembled arm's ESP32 JSON endpoint exposes those reads. Running a standalone
servo demo or flashing driver firmware could change the arm setup and is not part
of the present investigation.

The same manufacturer page warns that overly long mounting screws can cause
mechanical resistance if they contact the servo body. This is a possible inspection
item, not evidence that this arm has that problem. A power-isolated visual check
of cables, connectors and visible binding is pending; do not force a joint or
remove structural screws as a blind test.

## Questions for Waveshare if inspection is inconclusive

1. How can the installed RoArm-M3 Pro firmware version be identified without a
   reset, flash or motion command?
2. Is there a supported, read-only command on this firmware that reports elbow
   servo communication success, voltage, temperature, torque enable/protection
   state and current goal position?
3. Can the supported diagnostics read mode, torque limit, deadband and position
   limits without altering EEPROM, midpoint, servo ID or holding torque?
4. Is T101 joint 3 at spd 20 / acc 1 expected to execute a -23-count change on the
   shipped Pro elbow configuration? Are there documented conditions that suppress
   such a request while still returning normal T1051 feedback?
5. What is the recommended non-destructive isolation procedure if that request
   produces neither observed motion nor reported position change?

## Local evidence (share only after reviewing exports)

- Watched trial: `wizard-20260917T155919439246Z-4bd875f42550457a956eab38b96b4a25`.
- Interface inspection: `wizard-20260917T160417646909Z-2677896abec143d782834a972a14bd53`.
- Detailed history: [elbow response review](CARTESIAN_ELBOW_RESPONSE_REVIEW_20260917.md).

Exports reside in `software/runs/wizard-exports`. Do not send whole workspace logs
or network credentials. No support ticket has been submitted and no new hardware
or adapter purchase is implied by this draft.
