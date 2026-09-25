# First live micro-commissioning workflow result

Date: 2026-09-17. Transport: Wi-Fi, pinned arm identity at 192.168.0.225.

## Outcome

The actual wizard service action `run_micro_commissioning` completed with
`NO_CORRECTION_NEEDED / PREDECESSOR_IN_DESIRED_BAND`. This was a native hardware
run, not a substituted provider. It was invoked through service preview/execute,
not by clicking Execute in the browser. No concurrent local robot Python process
was found before the run. External-controller exclusion remains an operating
assumption, not something this process inventory proves.

Two commands total were sent, each once: one separate positioning action followed
by the coordinator's predecessor. No optional micro-command, retry or automatic
return was sent. No global compensation or calibration was changed.

| Leg | Commanded roll | Desired reported endpoint | Observed endpoint | Endpoint verification after dispatch | Hold readings | Largest hold response gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Separate positioning | 2.5 deg | 2.5 deg | 2.285156222 deg | 1.218244 s | 120 | 371.558 ms |
| Descending predecessor | 0.95 deg | 1.25 deg | 1.230468748 deg | 1.221623 s | 119 | 418.209 ms |

Both commands used T101, joint 5, speed 20, acceleration 1. The first leg met
the existing broad arrival check, not the illustrative +/-0.05-degree accuracy
band. The predecessor met that narrow band with error -0.019531252 degrees.

All six reported joints remained unchanged during both passive holds. Response
spans were 34.857084 and 34.950386 seconds. Original-response replay independently
reconstructed both endpoint verdicts and unchanged holds. The coordinator final
export and enclosing wizard export also passed manifest verification.

## Evidence

Workspace root for these folders: `software/runs/wizard-exports/`.

- Positioning plus hold: `wizard-20260917T114034463638Z-2ca2721b65cf49bab117051e31e8c561`.
- Predecessor plus hold: `wizard-20260917T114136387057Z-8814afa2619443058843275609f6cd3a`.
- Coordinator outcome: `wizard-20260917T114136516460Z-ad0f09d93525419daad94412344c50ad`.
- Enclosing wizard operation: `wizard-20260917T114136921731Z-9e51d6f977164cadb0b5a944f801458d`.

The positioning and predecessor exports were replayed with
`software/scripts/review_wifi_roll_export.py`; both returned full validation
success. The 22 coordinator/native-composition/wizard unit tests also passed.

## Meaning and next work

This validates a real end-to-end path: fresh baseline, bounded dispatch, feedback
endpoint verification, passive hold, conditional decision and reproducible export.
It validates withholding an unnecessary correction. It does not validate the
optional 0.90-degree correction on hardware, physical tip accuracy, or a general
compensation model across joints or poses. Controller joint telemetry is the
measurement source; host verification time is not physical movement duration.

Keep this run as the in-band regression reference. Next useful software work is
to make this compact command-versus-desired-versus-observed summary available in
the wizard and exports, so operators do not confuse raw command error with desired
endpoint error. Future bounded campaigns should compare independent sessions and
directions rather than repeat this predecessor until an error happens to appear.
Any new physical leg must use a fresh baseline, not this saved pose as admission.
