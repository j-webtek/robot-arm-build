# Feedback dispatch: one qualified lease window

Date: 2026-09-08. Status: implemented; frozen-source public NC-01 walkthrough
passed. Physical connection, NC-02/03 and application handoff remain unfinished.
Starting production fingerprint:
`5b6599106dfb2476e547f3b9aaeaf937fadcb6fb0d990390fe003df5a4523a8b`.

## Objective and evidence

Repair the preceding memory-feedback timing problem so the real public wizard
can progress through its camera, feedback, reference and NC-01 rehearsal path.
The [original incident](NONCONTACT_FEEDBACK_INCIDENT.md) remains preserved and
quarantined. Its missing exception text is not reconstructed; its timing diagnosis
is strongly supported inference. This repair must not alter that original store.
The preceding goal turn made concrete code/test/export progress, but did not
complete the full onboarding objective or the NC-01 public walkthrough.

At the baseline, the owned-feedback lane kept one actual M1 CELL/SESSION/ARM_CONTROLLER
lease window across preflight, prepare and execute. The memory-only lane repeated
qualified lease acquisition. The plan was to reuse that adapter for exactly these two
registered incapable actions; remove repeated lease cycles, not fresh checks.

## Implementation ownership

- Adapter: extend its closed allowlist to the existing memory and owned feedback
  actions. Keep exact M1 class/composition, exact ordered leases, request binding,
  single-thread/single-use scope, two coordinator contexts and cleanup handling.
- Service: use that same window for both feedback branches. Preserve the chosen
  worker, preflight timing, synthetic envelope, one-use acknowledgement and
  complete retained outcome. No worker fallback or physical port activation.
- Independent tests/review: exercise deadline exhaustion after durable arming,
  source/Stop/cleanup failures and lane separation without touching devices.
- Integration owner: freeze production after review, run focused regression,
  then one explicitly recorded new-source public walkthrough with failure export.

## Invariants and acceptance

Keep the synthetic envelope at 30 seconds, memory campaign at 10 seconds and
owned campaign at 20 seconds. Do not renew, extend or substitute a permit or
envelope, skip freshness checks, cache admission, clear quarantine or replay an
original action. If the full budget no longer fits after durable arming, retain
uncertainty and do not dispatch a worker. Underlying leases must close inside
the coordinator's second context so cleanup failures remain visible to it.

Tests must establish both permitted actions and rejection of every other action;
exact request/lease binding; no phase-one mutation, third use, cross-thread use
or post-exit access; one real M1 acquisition with fresh coordinator reads;
prepare-without-execute cleanup; original deadline bounds; slow arm/Stop/source
fault holds; and memory/owned worker separation. Any test-owned store is separate
from the preserved failed store and must not be presented as received hardware.

The public acceptance run must use the normal memory lane (not switch to owned
to avoid proving this repair), first thirteen reviewed stages, then stage-14
collection, pure assessment, blocked review and original-store reopen. Retain
the complete NC-01 receipt through generic-result eviction and verify exports
in `software/runs/wizard-exports`. Expected final rehearsal states are thirteen
PASS, stage 14 BLOCKED and handoff PENDING. All fifteen physical stages stay
pending with zero actual device opens, serial writes, power, motion or contacts.

No physical connection gate, installed calibration requirement, active freeze,
native provider or motion/contact authority is changed. NC-02/03, physical
activation and the full application handoff remain separate unfinished work.

## Verification record

Record final source, test scopes/results, original new-run identity, exported
receipt hashes and any remaining failure here after actual verification.

Implemented service changes use the actual adapter for both branches; no worker
selection/fallback behavior changed. A late lease-exit exception now also retains
the memory worker's already-produced safe summary, exact artifact hash and
independent synthetic final-power record as historical, with M1 retention and
coordinator completion explicitly unconfirmed. Only the owned branch includes
process-specific metadata. Neither exception branch publishes nominal success.

Adapter verification: 49 pure tests plus 10 actual isolated NTFS/M1 cases passed.
The latter completed in 67.92 seconds and exercised both action IDs with one real
context enter/exit; nominal, cancellation and exit-failure cases performed four
fresh admission reads, changed facts three, and abandoned preparation two.
The original 30-second envelope and 10/20-second campaign budgets were asserted.
Adapter source SHA-256:
`9f8ce3fe8a9285f594293374acb43a01dafdebb50e23ac1ad5c78b71ce6583fc`.

Existing feedback/publication regression initially exposed two outdated modeled
transaction seams, not production failures. Tests now model the new lifetime
boundary without relaxing the adapter's exact-M1 checks; actual adapter behavior
is covered separately above. The updated feedback-stage/owned-Arrival/noncontact
service selection passed 86 tests in 12.25 seconds. The preflight test still
advances a simulated 40 seconds before original-envelope issuance, verifies all
eight immutable epoch hashes with the ledger newline codec, and verifies Stop
before issuance. No operating-system clock or original record is changed.

The new service/core composition suite passed eight tests in 0.59 seconds.
It uses the actual service, adapter, coordinator and memory worker with explicitly
modeled M1 method bodies. It proves one dispatch acquisition and three fresh
admission reads on that retained-memory branch, fresh original-envelope issuance
after a modeled 40-second preflight, original 30s/10s budgets, source/Stop holds,
and historical evidence after a late lease-exit exception. This differs from the
adapter's separate generic actual-M1 fixture's four-read path; neither count is
silently substituted for the other. A Stop during arming may invoke the worker
only to return CANCELLED_PRE_OPEN with all twelve modeled API counters zero;
budget exhaustion after arming prevents worker invocation entirely.

The 14-file coordinator/feedback/publication/smoke regression passed 406 tests
in 47.45 seconds:

```text
.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_coordinator.py software/tests/unit/test_commissioning_coordinator_cleanup.py software/tests/unit/test_commissioning_coordinator_deadline.py software/tests/unit/test_arm_feedback_rehearsal_campaign.py software/tests/unit/test_owned_arm_feedback_rehearsal_campaign.py software/tests/unit/test_rehearsal_feedback_binding.py software/tests/unit/test_rehearsal_feedback_stage.py software/tests/unit/test_wizard_feedback_stage_integration.py software/tests/unit/test_wizard_owned_arm_feedback_arrival.py software/tests/unit/test_wizard_owned_arm_feedback_ui.py software/tests/unit/test_arrival_wizard_feedback_ui.py software/tests/unit/test_wizard_noncontact_stage_integration.py software/tests/unit/test_wizard_noncontact_smoke.py software/tests/unit/test_wizard_arm_smoke_failure_export.py -m 'not slow' -q
```

Both changed production modules pass Black and mypy. Their final workspace
fingerprint is
`d2acf8276a66f48590b2a1d62b3cfd79795b22f2579e353fe40b0d121edc866d`.
The next actual public run was started only after that freeze, using:

```text
.venv\Scripts\python.exe software/scripts/wizard_noncontact_smoke.py --expected-source-sha256 d2acf8276a66f48590b2a1d62b3cfd79795b22f2579e353fe40b0d121edc866d
```

The assigned root contained 24 original rehearsal stores before the new run,
within the unchanged 32-store discovery limit. This run creates one separate
new-source store; it does not reopen/migrate the old quarantined source-5b659910
attempt to continue it. Its actual terminal results are recorded below separately
from focused test success.

The seven-file NC-01 binding/evaluator/reopen/UI/publication/service/smoke
selection passed 229 tests in 34.61 seconds on the new production source.
The larger 2,467-test result in the preceding checkpoint belongs to source
5b659910 and is not relabelled as a full new-source suite result. Counts overlap
other focused selections and must not be summed as unique coverage.

The no-index/no-dependency wheel build passed. Artifact:
`software/runs/wizard-package-check-d2acf827/rocell-0.1.0-py3-none-any.whl`,
1,848,412 bytes, SHA-256
`c3d2ae5ba9e2ba0be14aa6b0dee672691fa4b119519c417f355a04b85ae40c5b`.
All 254 packaged Python/HTML/CSS/JS entries exactly match the current source.
This is a development packaging check, not a qualified hardware installer.
Both launcher `-Check` modes started without opening a server/device; the
physical-mode check explicitly confirmed NOT_STARTED, no current gap report,
authority false and the selected workspace export directory.

Read-only inspection also reconfirmed the old uncertain-result record's original
hash `67b92c004d52774bb28f60e2a48974b2936f810c318cca95be3bc8ab8ad43994`,
null receipt and latched quarantine. It was not changed by the repair or new run.

## Actual public workflow completed

The command above exited 0 on 2026-09-08 after its final export at 14:01:54 UTC.
It used the normal memory-feedback action, not the owned action as a substitute.
Each original action was attempted once. Thirteen stages were assessed/reviewed
PASS; stage fourteen was collected, assessed and reviewed BLOCKED, and stage
fifteen remained PENDING. A successful diagnostic execution did not convert its
three nominal readiness gaps into passing acceptance.

| Binding | Verified value |
| --- | --- |
| Original directory | `software/runs/wizard-rehearsal/wizard-e627da8473e54fb4b88bce1229693f48` |
| Original session | `rehearsal-231018f61113403b87e7809e611ea3f6` |
| Original cell | `wizard-rehearsal-231018f61113403b` |
| Final journal head | `edf8fb26d467be7e3e41227714ad82a4257b903e84847d82ab24fcce83d4147f` |
| Attempt-event count | 15, unchanged through stage-14 reopening |
| NC-01 evaluation SHA-256 | `047d97f84d2fd328150caa13df5a8bedadad9d5e6ff9db6a2a888075efff943d` |
| NC-01 receipt SHA-256 | `429e5338ddb165d39e3fc7442b84891201d34be500caed1beded135b99d06188` |
| Dedicated export attachment | 128,872 bytes; SHA-256 `7cb1c5a85c32a6f9a591889c1a45072cbf9214dbb7075327333a1dea41ee7500` |

The full retained receipt survived nine newer note results evicting its generic
result and was byte-identical in all five NC-01 exports. Four separate application
launches exercised collection, pure assessment, distinct-reviewer blocked review,
and final original-store verification. Reopen guards prohibited campaign, fitting,
FK/evaluator and device replay. Five synthetic controls passed separately from
three failed nominal checks. Every physical stage remained pending; actual device
opens, serial writes, power events, motion and contact commands were zero.

Final independently verifiable bundle in the operator-selected folder:
[final NC-01 diagnostic export](../runs/wizard-exports/wizard-20260908T140154814962Z-6b70f89d305b4aafb6b12b1a0666d57e/README.md).
Its six payload files have manifest binding
`e7d543c96e7bd3c231c60d6f9ca7b6f696c0b606eced283b5d8ba6468c045f58`.
The dedicated `attachment-noncontact-readiness.json` is a diagnostic wrapper around
the original receipt; its formatted byte length differs from the canonical M1
record length. Do not compare that wrapper length to the M1 report size limit.

The other four complete diagnostic exports, in order, are:

- `wizard-20260908T135937519289Z-8dcfa342f448433e8d0e9ff50827c679` (collection).
- `wizard-20260908T135938248024Z-8cb30777fbfb403088dc3087f3d8b329` (after result eviction).
- `wizard-20260908T140029325275Z-d44c7bc419b840659a0cf5c3a5f1fc35` (assessment).
- `wizard-20260908T140121093412Z-f9df734f52744957a50ef11a29785b7d` (blocked review).

These are new-source results, not a rewrite or recovery of the source-5b659910
incident. That original uncertainty, missing in-memory failure bytes and
quarantine remain disclosed. The repair closes the bounded dispatch integration
problem and proves the NC-01 software lifecycle; it does not close physical
commissioning or the full onboarding application objective.

## Separate actual-browser spot check

A separate `start-rocell-wizard.ps1 -NoBrowser` launch served the unchanged source
on a temporary loopback port. The actual in-app browser loaded the overview,
Camera, Arm and Diagnostics pages. Camera layout was inspected in a screenshot;
the displayed purchase profile, NOT CONNECTED states, disabled physical controls
and the exact selected export folder were checked through the rendered UI.
Navigation alone left revision zero and the diagnostic event count zero.

The browser then previewed and executed exactly one nominal **Test one-shot arm
feedback worker** action, loaded its complete retained result, and previewed and
executed one export. This is the standalone incapable worker diagnostic, not the
separate M1-bound stage-12 workflow proved above. The visible result distinguished
one modeled API write from zero physical serial operations, zero metadata
enumeration, zero power/motion/contact and no persistent connection.

- UI session: `wizard-41fa183c078244a395ef6d198dcf8399`.
- Test operation: `operation-7ae6c640f76d48c1b423f1dc767efb54`, SUCCEEDED.
- Retained result SHA-256: `cc4dc588d93ae403437cafbc3619fd79b4bea2e33c85ccf729a6ca1f1ebc7b2b`.
- [UI-driven diagnostic export](../runs/wizard-exports/wizard-20260908T140443541569Z-557d6d6d384047718920d301a7c58033/README.md).
- Manifest binding: `db156bc08d33949d85eaf1785e0c26887683eda049b92fc4c39ab12e8705065e`.
- Independent file verification: four payload files, 82,685 bytes, valid, no reasons.
- Browser console: no captured warning/error entries during this spot check.

No source/build changes or physical actions occurred. This is a limited real-browser
interaction check, not every wizard screen or the full NC-01 lifecycle through a
browser. The temporary tab was closed and only its own launcher was stopped;
the evidence and other sessions were preserved. Read-only listener inspection
confirmed zero remaining listeners on that temporary port. No browser security/privacy
settings or device permissions were changed.

## Independent retained-export presentation verification

An independent developer verified the actual final export, then passed its exact
`report.json.snapshot` through the real application JavaScript in the existing
Node fake-DOM harness and through the actual terminal renderer. This is distinct
from the real-browser spot check above. The retained NC-01 receipt is 82,393
canonical bytes and its complete numerical evaluation is 81,812 bytes. The full
exported report is 163,640 bytes. All four expected source/receipt/attachment/
evaluation hashes matched; the ordinary export integrity check was valid.

Both rendering adapters preserve BLOCKED_UNBOUNDED, no real-build error/margin
bound, three failed nominal checks, five passing synthetic checks, and the
separate +3000 / -1500 micrometre synthetic-control margins. The exact exported
snapshot shows thirteen rehearsal PASS, stage fourteen BLOCKED, handoff PENDING
and fifteen physical stages pending. The fake DOM issued only `GET /api/view`;
the terminal called `view()` once, with no prepare, execute or shutdown. Original
export and production-source bytes were unchanged after presentation.

The [development-only reproducer](../scripts/verify_noncontact_export_presentation.py)
passed after formatting in 0.92 seconds; its syntax compilation also passed.
It relies on development test helpers and Node, uses assertions, and is not a
runtime acceptance or physical-qualification API. Script SHA-256:
`ac67bf89fe99e4801c2f8ef0632ac86cf927818c21fadbbf87b99729876d48fc`.

```text
.venv\Scripts\python.exe software/scripts/verify_noncontact_export_presentation.py software/runs/wizard-exports/wizard-20260908T140154814962Z-6b70f89d305b4aafb6b12b1a0666d57e --source d2acf8276a66f48590b2a1d62b3cfd79795b22f2579e353fe40b0d121edc866d --receipt 429e5338ddb165d39e3fc7442b84891201d34be500caed1beded135b99d06188 --attachment 7cb1c5a85c32a6f9a591889c1a45072cbf9214dbb7075327333a1dea41ee7500 --evaluation 047d97f84d2fd328150caa13df5a8bedadad9d5e6ff9db6a2a888075efff943d
```

## Remaining application work

This verified checkpoint does not complete the user's full connection-to-typing
objective. Continue using the developer playbook and existing bounded plans:

1. NC-02/03: retain complete uncertainty, coverage and collision evidence with
   measured result-size/runtime budgets; do not silently substitute an unmeasured
   placement/tool hypothesis or turn an expected-fault pass into readiness.
2. Physical camera: complete received-evidence review, purpose-specific runtime
   qualification and the guarded service joins for finite probe/settings/capture.
   A prepared acquisition plan is not a working physical camera connection.
3. Physical arm: complete exact-controller enrollment, power/startup prerequisites
   and reviewed one-shot feedback service activation. Opening serial is not
   inert and a successful packet is not installed firmware or power evidence.
4. Installed reference, TCP, accuracy, clearance and untouched acceptance evidence
   remain required before later motion, individual keystrokes or Android tapping.
   No current rehearsal result, note, export or handoff label grants that authority.

These are unfinished software/integration and received-hardware qualification
items, not just a request to plug in the devices. No freeze or physical gate was
changed to conceal them.
