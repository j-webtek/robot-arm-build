# Retained stage-12 feedback presentation

The browser and terminal can display a retained **synthetic** feedback campaign.
This presentation does not connect to hardware, run a campaign, validate an M1
attempt, accept a review, or provide a power control. The application service
owns the due-stage action, retention, coordinator result and exact review.

Read with the [remaining-stage integration map](WIZARD_REMAINING_STAGE_INTEGRATION.md),
[arm feedback worker contract](ARM_FEEDBACK_WORKER.md), and
[shared retained-check presentation](WIZARD_RETAINED_ARM_POWER_CHECKS.md).

## Four results that must stay separate

1. **Technical response:** whether the retained response is a valid typed
   synthetic feedback packet. This can be true even if cleanup later fails.
   Complete feedback-receipt validity is displayed separately. Neither value
   proves installed firmware, calibrated position, stationarity or freshness
   from a device clock.
2. **Serial cleanup:** whether the incapable API reported confirmed serial
   cleanup, with effect uncertainty and code-only errors. Closing a handle is
   not a DC disconnect, physical emergency stop, or observed power-off state.
3. **Worker final-power knowledge:** always
   `UNKNOWN_REQUIRES_SEPARATE_OBSERVATION`. Neither response success nor close
   success replaces this honest worker limitation.
4. **Independent synthetic final-power observation:** a separately retained
   post-campaign fixture observation. `DEENERGIZED` is labeled synthetic only;
   `ENERGIZED`, `UNKNOWN`, missing and invalid observations remain visible holds.
   The observer summary never rewrites the worker's own UNKNOWN state and is
   not a measurement of real power.

The existing check categories remain distinct: nominal checks, expected-fault
handling and invariants. Passing an injected-fault test is not nominal feedback
acceptance. The frontend does not derive a stage PASS from any badge, observer
value or API counter. The backend's exact assessment and distinct review remain
necessary, and a quarantined/uncertain attempt cannot be cleared from this view.

There are no new serial endpoints, command inputs, protocol-code selectors,
power buttons or retry controls in the report. If a registered due-stage
campaign action is offered, use its normal preview and exact confirmation.
Viewing, refreshing, expanding details and reopening retained evidence do not
dispatch it or restore a prior approval.

## Cached projection

`commissioning_rehearsal.arm_feedback_evaluation` is nullable. When present it
uses the established retained-check contract with:

```text
stage: feedback_only_connection
outcome: REHEARSAL_CHECKS_PASSED | BLOCKED
evaluation_sha256, selected_inputs_sha256
checks: at most 16 explicit NOMINAL / EXPECTED_FAULT / INVARIANT rows
provenance, meaning, physical_authority: false
safe_summary: worker evidence's exact safe_summary() dictionary
final_power_observation: independent safe observer summary or null
```

The worker safe-summary schema is
`rocell.rehearsal_arm_feedback_summary.v1`. Displayed fields are explicitly
allowlisted: request/controller/source/binding hashes; worker outcome; strict
response/receipt/cleanup/uncertainty Booleans; 12 incapable serial API counters;
error `code`, `phase` and `error_type`; response/unexpected hashes and retained
or omitted byte counts; safe integer elapsed time and host-read-completion
timing provenance. `arm_connected`, firmware proof and physical authority must
remain false. A malformed summary is NOT_VERIFIED, not a passing response.

The independent observer summary is
`rocell.synthetic_final_power_observation.v1`, with origin
`SYNTHETIC_REHEARSAL`, kind `INDEPENDENT_POST_CAMPAIGN_FIXTURE`, bounded observer
ID, `observed_power_state`, `observed_after_worker: true`, permit/feedback-evidence/
observation hashes, `physical_observation: false`, and
`serial_close_used_to_infer_power: false`. Those display fields are not proof by
themselves: the service must authenticate the retained observation and its
post-campaign binding before supplying the projection.

## Data that is deliberately not displayed

- No raw request/response/boot bytes, hexadecimal payloads, arbitrary serial
  endpoint, parser unknown fields, or free-form serial exception messages.
- No generic expansion of feedback `check.observed` or `provenance` objects.
  Technical observations instead use the explicit safe-summary fields. Other
  stage presentations retain their existing bounded structured details.
- No absolute monotonic timestamps rendered as device time. Signed-63-bit
  timestamps can exceed JavaScript's exact-number range; they remain in the
  lossless evidence. Unsafe omitted-byte counts display NOT_EXACT rather than
  a rounded exact-looking value. Elapsed time must be a safe nonnegative integer.
- No full private lossless receipt in ordinary UI logs or generic page facts.
  Preserve the original evidence through its assigned storage workflow; a
  troubleshooting report is not automatically a full raw-evidence archive.

Browser content is literal text; terminal control characters are escaped.
Display validation cannot replace strict evidence verification, coordinator
accounting, independent observation or physical qualification.

## Tests and scope

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_arrival_wizard_feedback_ui.py -q
```

Tests use the pure DOM harness and injected terminal service. Cross-module
cases run the actual worker with the sealed memory-only serial backend, then
the lossless evidence writer's `safe_summary()`; hardware backend entry points
are forbidden. Nominal, close-failure, boot-byte, short-write and malformed
response cases are covered. They verify display separation and absence of raw
bytes/ports, not physical operation or completion of durable stage integration.
