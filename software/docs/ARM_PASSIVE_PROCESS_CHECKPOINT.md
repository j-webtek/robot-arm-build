# Passive arm process checkpoint

Date: 2026-09-12. Plan: [ROCELL-ARM-WIZARD-001](ARM_WIZARD_IMPLEMENTATION_PLAN.md).

## Outcome

The passive request/result contracts now have a fixed **hardware-incapable**
process integration using the existing Windows process owner. A real contained
child receives a bound request and returns a strictly validated passive result.
This is process/IPC evidence only. The child models device fields; it does not
exercise a serial driver, call the non-purging serial API, or qualify hardware.

The actual received arm remains unopened. No physical hold was removed, no power
was changed, and no serial/camera access occurred in this increment.

## Implementation

- `_passive_arm_process_fixture.py`: fixed stdlib-only child, no device libraries
  or arbitrary code/command input. Closed synthetic scenarios cover nominal,
  failed open, uncertain close, malformed output, wrong binding and stall.
- `passive_arm_process_codec.py`: exact payload/registration/result membership,
  fixed interpreter/child/argv, package membership, one-process budget, request
  and runtime bindings. Physical-mode payloads are rejected before dispatch.
- `owned_worker_process.py`: additive closed fixture protocol alongside existing
  process/camera protocols. Reuses the process owner, exclusive dispatch lock,
  source-file pinning, time/output limits, cancellation and cleanup observations.
- Result validation binds both outer process and inner passive requests. A
  successful child exit is not a successful device lifecycle: modeled failed
  opens and uncertain closes survive as distinct passive result states.
- Malformed/untrusted stdout is retained by the existing process result even
  when parsing fails. No automatic second attempt is introduced.

The registration digest is a consistency binding to pinned process inputs, not
a signed runtime certificate, independent source approval or physical release.
The selected identity in tests is synthetic; its hash does not authenticate the
received controller. The passive result continues to report runtime authentication,
connection, qualification and physical authority as false.

## Regression found and fixed before extending supervision

The actual isolated arm-feedback child initially failed after the prior CP210x
fix introduced a top-level `legacy_usb_metadata` import outside its closed archive.
Moving that dependency to the explicit legacy-registry lookup restores the
hardware-incapable child without changing historical archive membership or
granting it registry access. Injected CM fixtures without a registry backend
return before that import. Actual/injected legacy registry paths still pass.

A future capable package **must include and pin** the legacy registry dependency;
the lazy import is not a way to omit required code from a physical runtime.

## Tests and evidence

| Run | Coverage | Result |
| --- | --- | --- |
| `pytest-arm-child-import-20260912-01` | Actual pre-fix nominal owned child | Failed; preserved |
| `pytest-arm-child-import-20260912-02` | Nominal owned child plus CM/legacy registry | 63 passed |
| `pytest-arm-owned-regression-20260912-01` | Full owned-arm runner plus metadata and passive contracts | 171 passed in 52.40s |
| `pytest-passive-arm-owned-20260912-01` | New passive contained-process integration | 12 passed in 1.89s |
| `pytest-passive-arm-owned-20260912-02` | Passive, shared process, camera runner, arm runner, request/result contracts | 212 passed in 63.36s |

Run directories are under `software/runs/`. The new process codec and edited
shared owner passed scoped Mypy. Tests used new temporary paths and retained
earlier failures. No claim is made that the full repository or application
acceptance suite has passed.

## Still required for the actual wizard connection

1. Authenticate the bench-entry evidence references through their original
   producers/readers; hashing a supplied claim must not authorize serial opening.
2. Implement retained attempt intent, outcome, raw output and readback through
   existing storage, with incomplete/unknown attempts preserved and not replayed.
3. Join the service to the existing public action queue, UI and verified exports.
   The new fixture is not yet a wizard button or an operator hardware workflow.
4. Complete the passive physical lifecycle/owner integration and reviewed runtime
   registration; replacing a synthetic child with a capable one is not a release.
5. Obtain the required electrical-isolation/received-unit/boot-policy evidence and
   fresh physical entry confirmation before any real port opening.
6. Continue canonical stages, feedback, calibration and task execution milestones.

The full plan remains active. This checkpoint advances process integration, not
the physical arm-connection or typing/tapping acceptance criteria.
