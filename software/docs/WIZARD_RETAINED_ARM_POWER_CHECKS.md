# Retained arm identity and power/startup check presentation

This is the browser/terminal presentation contract for synthetic stages 9–11.
It does not activate a stage, connect to an arm, verify received hardware, or
provide a power control. Availability and exact assessment/review are owned by
the durable application service, not these display adapters.

## What the operator sees

The guided rehearsal page can show two separate retained-check cards:

- **Retained synthetic arm-identity checks:** profile policy and injected
  metadata checks. A synthetic chassis label is not identification of the real
  Pro arm. USB/serial enumeration, received-unit inspection, driver qualification
  and firmware verification remain distinct unverified work.
- **Retained synthetic power/startup checks:** the latest stage-10 or stage-11
  typed procedure/assessor report. Its observations describe synthetic fixture
  assessment, not actual actuator energy, a measured power-off state, startup
  motion, an E-stop test, or installed firmware.

Each card shows the evaluated stage, reported rehearsal outcome, evidence/input
hashes, compact provenance and concrete check observations. The terminal shows
the same information in plain text. Full protocol logs and nested technical
reports are not expanded as generic page facts; retain/export the original
evidence through the separate application workflow.

Check categories are deliberately distinct:

| Category | Meaning when its check passes |
| --- | --- |
| `NOMINAL` | The nominal synthetic input satisfied the actual check. |
| `EXPECTED_FAULT` | The injected failure had its expected handling, such as HOLD or UNCERTAIN. This cannot replace nominal success. |
| `INVARIANT` | A required invariant held, such as preserving zero physical authority. |

A failed nominal check remains visibly BLOCKED when expected-fault checks pass.
The UI does not combine row badges into an acceptance decision or convert a
successful negative test into physical readiness. A separate exact assessment
and distinct review remain required by the application workflow.

Viewing, refreshing, opening a check's details, or reopening a saved report
does not dispatch an evaluator, hardware action, prior ticket, or approval.
There are no new power-on, power-off, reset, firmware, or device-connect controls
in these cards. Software Stop elsewhere remains diagnostic cancellation, not a
physical emergency stop or evidence of de-energization.

## Service projection contract

The cached `commissioning_rehearsal` view has two nullable fields:

| Field | Allowed report stage |
| --- | --- |
| `arm_identity_evaluation` | `arm_identity` |
| `power_evaluation` | `power_safety` or `power_on_observation` |

Each non-null projection has:

```text
stage
outcome: REHEARSAL_CHECKS_PASSED | BLOCKED
evaluation_sha256: lowercase SHA-256
selected_inputs_sha256: lowercase SHA-256
physical_authority: false
meaning: short text
provenance: compact JSON object
checks: 1–16 rows
```

Every row has `check_id`, explicit `check_kind` (`NOMINAL`, `EXPECTED_FAULT` or
`INVARIANT`), strict Boolean `passed`, compact JSON `observed`, and short text
`meaning`. The frontend never infers a category from a check's name. Missing,
unknown or non-Boolean check data displays NOT_VERIFIED, never a passing badge.

The backend must derive this projection from verified retained evidence and
clear stale cached reports on source/state changes or failed replacement
collection. The projection is not an evidence-verification API: merely supplying
these fields cannot authorize an assessment, review, device or stage transition.
The existing optics projection and its dataset-dependency-only caption remain
unchanged.

## Presentation bounds and failures

Meanings are nonempty and at most 512 characters. Observed data and provenance
are limited to depth 6, 128 visited values, 32 entries per object/array, 2,048
characters per string, and 4,096 rendered characters. Displayed numeric magnitude
must not exceed the JavaScript safe-integer range; precise larger identifiers
must remain strings. These are display limits, not physical acceptance thresholds.

Wrong-stage, unknown-outcome, missing-hash, authority-claiming or oversized
projections show a visible NOT_VERIFIED warning. Oversized check lists are not
silently truncated into a seemingly complete passing report. Malformed rows
show their own warning without breaking the rest of the interface. Browser
values are literal text, and terminal control characters are escaped.

## Focused tests

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_arrival_wizard_arm_power_ui.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_arrival_wizard_optics_ui.py software/tests/unit/test_arrival_wizard_reopen_ui.py software/tests/unit/test_arrival_wizard_terminal.py software/tests/unit/test_arrival_wizard_ui.py -q
```

These tests use a pure DOM harness and injected terminal service. Cross-module
cases invoke closed hardware-incapable evaluators, then the real service's static
projection; they do not instantiate a service, qualify a store, or enumerate
host devices. Passing presentation tests does not complete the corresponding
durable stage integration or qualify physical hardware.
