# AFTER_REBOOT implementation work order

Status, 2026-09-09: **v13 application integration passed fresh full public
hardware-free NTFS acceptance in run 07. Received-hardware qualification remains
unverified.**
The original reader, separate Setup scope, one-shot boot collector, five USB
owner actions, Arrival routing, browser/terminal cards and v6 diagnostics exporter
are installed. The verified foundation follows
[AFTER_RECONNECT run 06](USB_AFTER_RECONNECT_IMPLEMENTATION.md).
Final heterogeneous four-phase assessment/review, stage-5 capture admission,
physical camera activation and arm startup remain unfinished. No physical
provider was exercised in this increment; registered actions are not proof of
received-hardware readiness. See the verification checkpoint below.

The [v13 integration map](USB_AFTER_REBOOT_V13_INTEGRATION_MAP.md) records the
bounded reader, private prefix, Setup, service, UI and export contracts.
The [completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md) remains
the overall camera/arm application target.

The [storage admission checkpoint](STORAGE_ADMISSION_PERFORMANCE.md) records a
fresh per-gate report-pair observation, passing regressions, an approximately
18% improvement in the larger-history profile, and the subsequent full public
pass. Earlier failed originals remain immutable; no consumed operation was
retried or rebound to a new source.

## Latest full public acceptance — run 07

`reboot-root-public-20260909-07` **passed 1 test in 1,735.50 s**. JUnit reports
zero failures/errors/skips. The fresh full flow rebuilt its baseline, physical
absence and reconnect predecessors, then used a real new Arrival instance for
public discovery/reopen, Begin, fresh metadata/Refresh, Prepare, Review, boot
collection and USB collection. All eleven reboot roles/seven events were
retained; the final phase was `REBOOT_OBSERVATIONS_RETAINED` with every check
passing, and its attempt was `SEALED_KNOWN` with quarantine false. Complete v6
export/restore and another new application's exact original reopen/no replay
passed. Later stages stayed PENDING.

The public action timings were 68.281 / 83.297 / 82.625 / 127.375 / 182.734 s.
These measure the public dispatch/completion/idempotent-return sequence, not
one inner worker deadline. No deadline was enlarged. Reconnect's post-pin
remaining lifetime was 22.406 s; reboot's was **20.782 s**, only **0.782 s above
the unchanged 20-second reserve**. This single pass is not a hard real-time or
received-host performance guarantee.

Real NTFS, original leases/audits, service actions, logging and export machinery
executed. Boot, metadata, USB and process observations were explicitly modeled;
no physical provider or production native process ran. The fixture uses its
labeled modeled source binding. The actual application build was held fixed at
`b9170ade0d1e77d7bd5eb22e52045412af9cb32841b20b3eef5238368780e32e`,
with unchanged selected-test SHA-256
`0726b75836df94fd23518f37ce4c80f46279aae152df591cacb55beb489649d3`.

Preserved beneath the confirmed `software/runs/wizard-exports` parent:

- `hardware-free-usb-reboot-accepted-20260909-07`: **559 files / 14,231,112
  bytes SHA-matched**, before adding its explanatory README; originals unchanged.
- `wizard-20260909T235908605526Z-76ea6a4bce1a4ab29686608690d13b20`:
  ordinary v6 export from the closed cache, independently pinned to original
  diagnostics SHA-256 `99ec81e6f8339c86fd23f8953e0240d8f5fb79fb4f51d1b7c6fa153e6f626f28`.
  Verification reconstructed 53 subjects from 832,378 attachment bytes, without
  redaction or original-store reopening. Manifest SHA-256:
  `c3f1b78983ca81e1068cbf7bff649355a51971edbba0f31a0f6022417a115425`.

This completes the public v13 integration check, not the heterogeneous final
identity review, stage-5 entry, physical camera runtime or arm path. The next
work is the [complete-series review](USB_COMPLETE_SERIES_IMPLEMENTATION.md).
Earlier scoped results and failed-run history below are retained for diagnosis;
their pending-status statements describe those earlier checkpoints.

An isolated review draft may be prepared outside `software/src` and
`software/tests` while reconnect acceptance runs. Such a draft is not installed,
imported, tested against the running application or part of its frozen source.
Install and verify the successor only after the current acceptance closes.

Review-draft checkpoint (2026-09-09): the two proposed files are staged under
`.codex-preserved/reboot-draft-20260909-01`, outside the application. Source
`physical_usb_reboot_phase.py` SHA-256 is
`3ca03f3caffe7dfc25009b707f0688ca1e439faf847a8059170c88d38623c02c`;
test `test_physical_usb_reboot_phase.py` SHA-256 is
`a58074cfd655059d13fbe23faf70c18d4cd831adac636725014e9e9272a5dcd7`.
Root and independent static review found no concrete source defect. Cross-review
corrected two test-only issues: a new monotonic epoch needs its own absolute
deadline at the unchanged duration, and an invalid legacy phase-ID syntax is
rejected before the valid-ID reuse check. At that review checkpoint the files
were not installed, formatted, imported or executed. Those exact review copies
remain unchanged in the preserved folder; installed copies now have updated
headers/formatting. That earlier static review was not passing acceptance.
The current integration checkpoint supersedes its implementation status.

## Current application integration checkpoint

All paths below are beneath `.codex-preserved/`; each run used a fresh directory.
Root-observed completed test results:

| Suite / scope | Result | What it establishes |
| --- | --- | --- |
| `reboot-root-reader-suite-20260909-01` | 12 passed, 1,179.81 s | Complete original-shaped v1–v13 readback; every preparation write boundary, held/uncertain boot, campaign-only/partial transfer, unknown counters and invalid role/event/campaign rejection |
| `reboot-root-ui-reader-20260909-05` | 3 passed, 281.20 s | Actual reviewed/final owner projections in terminal and finite Node browser renderer; complete diagnostic export/restore; fixed same-transaction boot reader, source/launch/deadline/Stop checks and changed-head rejection |
| `reboot-root-composed-20260909-02` | 1 passed, 163.02 s | Actual new-launch Begin, three metadata publication routes, explicit-refresh handoff, Setup Prepare/Review, pending-publication holds and original-byte preservation |
| `reboot-root-contract-regression-20260909-01` | 251 passed, 3.76 s | Public action/result contracts, metadata routing, v6/v5 export and partial-result retention, reboot Setup/epoch limits and predecessor campaign-audit regression |
| `reboot-root-ui-regression-20260909-01` | 67 passed, 63.93 s | Earlier reconnect, declaration and restart interfaces remain functional |
| `reboot-root-legacy-readback-20260909-03` | 81 passed, 11.94 s | Earlier Session readback and reconnect storage/epoch behavior |
| `reboot-root-family-20260909-01` | 8 passed, 0.70 s | Fourth descriptor campaign only under the explicit reboot route; fifth rejected; whole-family audit, final attempt check and exact flag types preserved |

These are selected tests, not the entire repository suite. Hardware observations,
metadata, storage leases and campaign discovery are explicitly modeled in the
new integration fixtures. Real subject codecs, service methods, export/restore
and UI renderers execute. The fixed boot-reader test uses the complete actual
codec chain but modeled storage, not a real NTFS commissioning store.

Agent-confirmed prior checks also passed: 14 original boot-collector tests,
10 helper/inventory tests and 106 Setup/epoch tests. The agent's interrupted
full-reader run had no confirmed completion; the root's 12-test run above is the
confirmed replacement. No reset credit was consumed after agents stopped.

Integration testing corrected three production joins: historical reconnect
adoption under v13; browser boot checks accidentally placed in the absence
validator; and reboot adoption losing diagnostic predecessor data while Setup
awaited completion publication. Adoption now verifies the exact retained
prerequisite bytes for diagnostics, while actions still require CURRENT Setup
and independently obtain/recheck prerequisites in `perform`. Pending history
does not grant action permission.

Failed scopes remain preserved. Earlier UI runs also exposed test-only reopened
registry metadata and an incorrectly spelled expected export schema; those
fixtures were corrected without weakening validation. The earlier prerequisite-
only Session model now explicitly declares an empty journal. No existing
originals were rewritten, replayed, deleted or rebound.

Black formatted the changed sources/tests; scoped mypy passed nine joined source
files, and `node --check` passed. Both launcher `-Check` modes returned
`READY_FOR_DIAGNOSTICS`, camera/arm `NOT_CONNECTED`, zero operations/events and
false physical authority. Checked source:
`426140bffe1c6ad704708e1f902dfca1ce2a15c5f529757eb29eaee62212893f`.
The selected export parent remains
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.

Live browser QA was attempted using a temporary rehearsal server. Chrome
reported `ERR_BLOCKED_BY_CLIENT` for its loopback URL, so no live-page rendering
or screenshots were verified. The test tab was closed and the temporary server
was stopped with Ctrl+C; no security setting was changed and no hardware action
was run. The passing browser checks above are finite Node renderer tests.

The new `test_arrival_usb_reboot_ntfs_acceptance.py` collects successfully.
Its first full run, `reboot-root-public-20260909-01`, **failed after 1,006.80 s**
while rebuilding the AFTER_RECONNECT predecessor, before any new-launch v13
action. Baseline and absence completed their public actions, export/restore
and fresh reopening. Reconnect reached descriptor collection, which retained
`FULL_USB_LIFETIME_DOES_NOT_FIT` before process creation. A completed diagnostic
operation is not a passing qualification: the phase is `ORIGINAL_CAMPAIGN_HELD`,
the original attempt is `SEALED_UNCERTAIN`, and quarantine remains latched.

The unchanged 30-second permit spent 6.969 s before runner entry. PRE_PIN and
POST_PIN checks took 1.485 s and 1.422 s; the runner's 3.109 s interval left
19.922 s, **78 ms below the unchanged 20-second lifecycle floor**. No native
process or USB query ran. The consumed original must not be retried. All failed
originals and checkpoints remain in the fresh preserved test directory.
The earlier reconnect pass had only 0.703 s of margin; another nominal retry
alone would not establish reliable performance. Profile the remaining fresh
verification work without weakening deadlines, independent audits or readback.

The unexecuted v13 portion uses public discover/reopen forms in a new application
launch, not a fabricated reopened Setup owner. No passing full public v13
outcome is claimed; its scoped tests remain separate evidence.

The failed run is copied under the confirmed export parent in
`hardware-free-usb-reboot-held-20260909-01`. All 361 files / 3,818,609 bytes
were SHA-256 matched, including the original store, 171-event application log
and checkpoint. Its ordinary full v5 diagnostic export reconstructs exactly;
606,202 attachment bytes retain the held result. Original stores were not
reopened, mutated or replayed. The archive README distinguishes this file-copy
evidence from physical qualification.

### Verification-cost repair under test

A read-only closed-store V2 decoder profile observed 51 evidence references,
41 committed events and 145 bounded file reads in 0.254 s. It did not create
an M1 runtime, acquire a lease or execute a wizard action. A separate fresh
NTFS admission test profile identified repeated component metadata checks as a
larger cost: 37,265 component checks used existence, symlink, Windows attribute
and stat probes separately. The safe-root helper consumed 4.219 s under profiling.

`physical_onboarding_durability._reject_unsafe_component` now obtains all four
predicates from one fresh non-following `lstat`. Each caller still checks each
ancestor on every invocation, with no cached path observations. Nonmissing
inspection errors fail closed; Windows metadata without valid attributes is
refused. Opened-handle disk/reparse/link-count/size verification, all original
reads, independent family/global audits, leases and time budgets are unchanged.

The identical fresh admission test passes before and after the repair. In those
two instrumented runs its pytest elapsed time changed from 9.45 s to 6.43 s;
safe-root time changed from 4.219 s to 1.637 s. Both still made exactly 3,663
safe-root / 37,265 component checks. Native stat calls fell from 102,011 to
65,194 and the 37,044 separate Windows-attribute calls disappeared. This is
bounded local profiling, not a guaranteed dispatch-margin improvement.

The component, durability and V2 path regression selection passes **66 tests
in 2.04 s**, including real NTFS hard links, junction rejection, unchanged
byte bounds and rejection of a late hard link by the independent opened-handle
check. Scoped mypy passes the changed source. The broader storage, leases,
M1, attempts, quarantine, V2, fresh-observation, post-lease and USB-identity
regression selection passes **126 tests in 97.45 s**. Both selections use fresh
isolated test directories, not old commissioning originals.

Fresh public run `reboot-root-public-20260909-02` rebuilt and **passed the entire
baseline/absence/reconnect predecessor**, including each export/restore and fresh
reopening. The reconnect runner entered 4.985 s after permit issue; PRE_PIN and
POST_PIN took 0.953 s / 0.969 s. Its second lifecycle check had **22.984 s** left,
2.984 s above the unchanged floor. All five scope checks passed, the modeled
descriptor result was retained as `SEALED_KNOWN`, and no quarantine was latched.
This supports the local performance repair, not a guarantee under arbitrary load.

The full test nevertheless **failed after 942.74 s**, before any reboot action:
the genuinely new Arrival constructor ran on the isolated workspace, which
lacked `software/config/camera_profiles/arducam_b0477_imx283_16mm.json`.
The predecessor's shell had used the repository workspace while its Setup
owner used the isolated store, so that fixture gap had not previously surfaced.
Do not replace the new application with a fabricated Setup owner to avoid it.

The test now seeds both ordinary controlled launch profiles into the fresh
workspace before any original is constructed. A shared real constructor is
exercised by a cheap startup regression: both profiles loaded, camera/arm
disconnected, zero operations/events, no original store and unchanged input
files. It passes **1 test in 0.81 s**; the first smoke attempt had a test-only
incorrect `session is None` expectation, corrected to assert the inert owner's
original directory is absent. The long public case is marked `slow`; ordinary
`-m 'not slow'` selection runs this startup check without the long case.

Run 02's original store, complete application log, three preceding exports and
checkpoints are copied in `hardware-free-usb-reboot-fixture-held-20260909-02`
under the confirmed export parent. All **422 files / 7,716,550 bytes** were
SHA-256 matched. Its v3/v4/v5 diagnostic exports verify and reconstruct; the
v5 reconnect phase equals the final checkpoint. No originals were mutated.

Fresh public run `reboot-root-public-20260909-03` **failed after 994.32 s**.
Baseline, absence and reconnect public actions, export/restore and underlying
M1 original readback passed again. Reconnect retained `SEALED_KNOWN` with all
five scope checks and 22.250 s left at the second lifecycle check. The new
application constructor succeeded, but public discovery correctly rejected
the fixture's original as `LINEAGE_MISMATCH`, before any reboot action.
Lower-level fixtures had arbitrary cell/session labels; production discovery
requires identifiers derived from the original launch and source. A passing
M1 decoder does not prove discovery in a genuinely new application.

Run 03 is preserved in `hardware-free-usb-reboot-lineage-held-20260909-03`
under the confirmed export parent: **427 files / 7,727,779 bytes** matched by
SHA-256, including the new launch's discovery logs. Its three v3/v4/v5 exports
verify and reconstruct; the v5 reconnect result equals its final checkpoint.
No original identifiers, headers, evidence or bytes were repaired or replayed.

The revised fixture asks an inert production camera owner to derive lineage,
then supplies that lineage to all five test-fixture builders **before creating
any originals**. It does not change the production registry or relax discovery.
The two cheap startup/discovery checks pass in 5.77 s. A fuller real-NTFS trial
prefix passes in **71.87 s**, proving that a new real Arrival application can
publicly discover and reopen genuine setup, source, camera-receipt, identity
and trial records. Physical observations remain explicitly modeled. The first
prefix attempt exposed one remaining fixture binding; its failed store is
preserved, and the correction was tested only with a new original.

Fresh full public run `reboot-root-public-20260909-04` **failed**; its JUnit
suite duration is 1,522.831 s. The full baseline/absence/reconnect prefix passed,
followed by genuine public discovery/reopening in a new application, Begin
(72.03 s), fresh logged metadata/explicit Refresh, Prepare (86.23 s) and Review
(84.19 s). Host-boot collection then returned `ORIGINAL_STAGE_MISMATCH` before
its durable BOOT_REQUESTED event. No reboot observation or descriptor query ran.
This is not a full v13 pass.

The cause is a production join, not another arbitrary fixture identifier:
`physical_usb_reboot_boot._inventory` used the camera-identity-only reference
validator for the complete session inventory. A real session necessarily
includes earlier source, design and camera-receipt stages. The small collector
fixtures contained only camera-identity references, hiding the mismatch.
A new focused test reproduced the exact failure in 0.76 s before the fix.

The inventory comparator now uses the generic strict evidence-reference parser
on every reference, retaining all earlier stages in the comparison. The fixed
whole-original reader still authenticates the complete store; `_read` continues
to require camera-identity stage references for individual boot roles. No stage
reference is filtered out, no inventory check is removed, and no deadline is
changed. New tests cover mixed inventories, duplicate IDs, earlier-stage drift,
full modeled collection and the unchanged stage-only read rule. The full-reader
test now exercises its consumer's inventory and exact-original joins as well.
The mixed-inventory, one-shot collector and standalone verifier selection
passes **31 tests in 312.91 s**. The full-reader/consumer join passes **1 test
in 143.24 s**, including actual original-codec reconstruction over an explicitly
modeled store. Neither result is full public NTFS acceptance. Fresh full public
run `reboot-root-public-20260909-05` completed on the repaired source below,
with the same full-test hash and entirely new originals. Both source and test
remained fixed through its close. The run-04 original was not repaired or retried.

### Run 05: query retained, outer readback timed out

Run 05 **failed after 1,896.54 s**. The baseline/absence/reconnect public
predecessor, new-application discovery/reopen, Begin, fresh metadata/Refresh,
Prepare, Review and boot collection all passed. The mixed-stage inventory fix
therefore also passed the real public NTFS boot path, not just its scoped model.

The final descriptor action consumed one modeled in-memory peer exchange and
retained `SEALED_KNOWN`: confirmed process/USB cleanup, 3 opens, 37 reads,
3 closes, zero writes/frames and no quarantine latch. The full execution and
`REBOOT_OBSERVATIONS_RETAINED` phase record were read back and the `RETAINED`
event committed. The final original-workflow verification then raised
`CAMERA_SESSION_TIMED_OUT`. The action failed after 196.55 s; its previous
published view remains `BOOT_RETAINED`, and dispatch is still
`PENDING_COMPLETION_LOG`. An inner clean query is not a successful public action.
No physical process, CIM, USB, camera or arm provider executed.

The final reopen/audit took about 12.64 s, followed by approximately 49.52 s
before the readback failure was logged. Those are log intervals, not a CPU
profile. Keep the existing outer deadline and independent lifecycle limits;
profile and reduce redundant verification work before another fresh full run.
Do not replay the consumed operation or promote cached retained records.

The complete closed case is copied to
`software/runs/wizard-exports/hardware-free-usb-reboot-timeout-held-20260909-05`:
**540 files / 11,842,280 bytes** SHA-256 matched before adding its README.
Its cached failed diagnostic record was separately exported through the ordinary
v6 exporter to `wizard-20260909T222110298874Z-23dc6faf49d64f4f8b2e10b4582d66d3`.
The standalone verifier confirms 832,346 attachment bytes and 53 reconstructed
subjects, with original bytes preserved and no redaction. Original-diagnostics
SHA-256: `2b533e1421e7908d3e10d9073259eb47f21c445da70dee0da22f267a939b9f7f`.
This is verification of a saved diagnostic copy, not original-store admission.
No full public v13 passing result has yet been obtained.

### Text-validation performance repair

A fresh, full modeled reader profile (`reboot-modeled-reader-profile-20260909-05`)
passed its single read-only test in 136.64 s including fixture setup. The profiled
reader itself used 71.32 s / 361,628,370 function calls. It retained the complete
original codec chain but modeled storage and hardware: this is not NTFS timing.
Repeated prerequisite text scans alone generated 74,339,400 Python character
checks; hazard text generated another 23,979,900. A separate cached-JSON decode
profile took only 0.039 s, so removing diagnostic-copy validation was not justified.

The prerequisite JSON/template and hazard text scans now use compiled, fixed
character classes for their exact historical predicates. JSON still permits
CR/LF/TAB and DEL; template fields still reject C0; hazards still reject C0 and
DEL. UTF-8 byte bounds, surrogate behavior, types, depth and trimming rules are
unchanged. The hazard helper retains its previous str-subclass behavior.
No document, filesystem observation, original audit or permission is cached,
and no timeout, lifecycle floor or stage gate changed.

Before the repair, 58 compatibility tests passed, including all 1,114,112 Unicode
code points. After it, that suite plus prerequisite and hazard regressions
**passed 126 tests in 3.33 s**. Early test-only CSV-field/writer mistakes are
preserved in the first three `text-validation-before` runs; they were corrected
before application changes. Black and scoped mypy pass the two changed modules.
The same modeled full-reader profile then passed in a fresh `...-06` directory:
**44.79 s / 131,945,920 function calls**, versus 71.32 s / 361,628,370 before,
about 37% less profiled execution time. Total test time including fixtures was 93.12 s.
The counts of prerequisite decodes (950), owned USB evidence validations (394)
and process-JSON decodes (105,273) were unchanged: validation was not skipped.
This is a bounded modeled comparison using cProfile's timer, not a CPU-only
measurement, hardware result or unprofiled wall-clock guarantee.

Downstream notebook/received-camera consumers **passed 163 tests in 74.79 s**.
The final compatibility selection, adding str-subclass/type checks, **passed
59 tests in 1.43 s**. Full-reader source/Stop/deadline/changed-head regression
and cheap public startup/discovery checks **passed 3 tests in 112.82 s**.
Lifecycle/standalone-export regressions **passed 16 tests in 2.08 s**.
Both launcher modes remain disconnected with zero
operations/events on the repaired source; no physical provider is opened.

Repaired application fingerprint:
`1811e4f6f376b4404833234f96b654b3d05b402750a15d8166d00c07a2152646`.
The full public acceptance test SHA-256 remains unchanged. Failed run-05
originals stay historical under their old binding and are never migrated.

Fresh full public run `reboot-root-public-20260909-06` **failed after 1,696.91 s**
against this fixed build and unchanged test, with entirely new originals.
Baseline, absence and reconnect passed their actions, exports and fresh
reopening. Reconnect's final action took 141.843 s; the original campaign is
`SEALED_KNOWN`, with no quarantine latch. After POST_PIN it had 21.031 seconds
remaining, only 1.031 s above the unchanged 20-second lifecycle reserve.

New-launch discovery/reopen and fresh metadata/Refresh passed. Reboot Begin,
Prepare, Review and boot collection passed in 69.062, 80.218, 82.515 and
124.844 s respectively. The final action returned diagnostic `SUCCEEDED` in
169.313 s, but the original phase is **`ORIGINAL_CAMPAIGN_HELD`**, not qualified.
It refused release with `FULL_USB_LIFETIME_DOES_NOT_FIT`: 8.156 s elapsed from
permit issuance to runner entry, followed by PRE_PIN 1.594 s and POST_PIN
1.438 s. Only 18.578 s remained, **1.422 s short** of the required reserve.
No process was created, no peer release occurred and no device call executed.
The conservative original result remains `SEALED_UNCERTAIN`, cleanup unconfirmed
and quarantine latched; zero counts must not override that decision.

The outer action completed, but this held branch omitted the nominal query
and final phase retention. It therefore does **not** prove the nominal outer
timeout is fixed. Profile fresh admission/scope overhead and add bounded
regression evidence before another full run; do not retry until green or
extend/shorten the existing budgets. No new full run 07 has been started.

Run 06 is copied under the confirmed export parent as
`hardware-free-usb-reboot-reserve-held-20260909-06`: **533 files / 11,645,937 bytes**
SHA-256 matched. Its complete cached v6 diagnostics were separately exported
to `wizard-20260909T230500521571Z-ba3e8972b0dd45e583fc73c900c99051` and verified
against the independent cached-byte hash. The 769,313 attachment bytes reconstruct
49 subjects exactly with no redaction. Original-diagnostics SHA-256:
`4493bce35c0734bc4a46de6189c11c031e15599b39ff1f3fd840c0e452bd10f4`.
Neither failed original was reopened, repaired, migrated or replayed.

Run 04 is preserved under the confirmed export parent as
`hardware-free-usb-reboot-stage-held-20260909-04`: **507 files / 10,993,670 bytes**
were SHA-256 matched before adding its README. Its complete failed cache was
exported separately through the ordinary v6 exporter. All 719,213 attachment
bytes reconstruct exactly, including the failed action's retained diagnostics.
The original-diagnostics SHA-256 is
`0fa53bba1c4b54c44e67e0fda0b39cafa9fd0c1ce905b02a7980d20369085734`.
Neither that cached export nor its verification opens an M1 store or replays
the failure. The archive README identifies the exact bundle.

Full public test source SHA-256 (unchanged during run 04):
`0726b75836df94fd23518f37ce4c80f46279aae152df591cacb55beb489649d3`.
Run-04 application source: `d04c4aad4915d6bae6ee41a45a09d0317fe9ff6f6233a3c33e12f04a2f3a46aa`.
Current source after the inventory repair:
`d59bf034459b076d4d686a2c6a08083f6bbeead9f4894126f776fc2f41e8dd6a`.
Boot module SHA-256:
`45db4912ea4efa8da139f8b18ffb04ed7cb3ad09e2d22c728dbeb15c68afdd8e`.
Changed durability source SHA-256:
`418f2689e5b1640e2d17c1074c6f521a57c0d8c07a07348013e80b891e6d9c2e`.
Scoped mypy passes the repaired boot module and new developer verifier script.
Both rehearsal and physical launcher `-Check` modes on the repaired build remain
disconnected with zero operations/events and the confirmed export parent.

Additional unchanged lifecycle regressions pass **4 tests in 1.14 s** for the
five-second admission window, 20-second post-pin floor, modeled nominal result
and late-result accounting, plus **1 test in 0.51 s** for a short original
deadline refusing owner construction. These do not execute a physical worker.

Next acceptance work is a **fresh complete public v13 flow** with real Arrival
tickets/completion logs, actual original NTFS retention, modeled observations,
all five actions, assigned-folder exports and fresh reopening/no replay. Build
the complete predecessor under the final frozen source; do not migrate the
preserved reconnect run. Then implement independent complete-series assessment
and stage-5 entry before the camera activation work; the
[next-slice contract](USB_COMPLETE_SERIES_IMPLEMENTATION.md) records that gap
without changing historical series semantics. This checkpoint does not
complete the overall onboarding application.

## Scope and decisions

The operator completes and exports reconnect, closes the wizard, manually
restarts the host, then opens and verifies the same original store in a new
application launch. A new **Begin AFTER_REBOOT** references the completed,
clean historical v12 reconnect. An interrupted reconnect is ineligible.

Do not resume the old reconnect transaction, rewrite its launch-bound report,
or carry any live request, preparation, admission or permit across launches.
The new phase is also launch-bound: restarting it before completion leaves
historical/export-only evidence, not an implicitly resumable request.

Require unchanged source and the same reported host, received camera, serial,
physical USB node, topology and driver. Missing observations, source changes,
driver changes and clock inconsistencies hold the workflow. Requalification
after such changes needs a separate contract. No automatic reboot, camera
capture/settings, arm access, motion/contact authority or final stage PASS is
included. The confirmed export parent remains `software/runs/wizard-exports`.

## Slice 1: minimal inert phase codec

The new `application/physical_usb_reboot_phase.py` contains immutable,
canonical bytes-only `UsbRebootOperatorEvent` and
`UsbRebootQualificationPhase` subjects. Both expose `payload`, `sha256`,
detached `to_dict()` and bounded `safe_summary()`. Use separate v1 schemas;
do not modify old endpoint-absence, physical-presence or reconnect codecs.

The operator subject means only `OPERATOR_REPORTED_HOST_RESTARTED`. It binds
the original plan, reconnect hash, new server-generated `usbphase-<32hex>` ID,
current launch/operator, phase start and report time. It is not reboot proof.

Installed and verified phase-codec APIs:

```python
build_usb_reboot_operator_event(
    *, plan, reconnect, phase_id, launch_session_id, operator_id,
    phase_started_at_utc_ns, reported_at_utc_ns,
)
build_usb_reboot_qualification_phase(
    *, original_baseline, received,
    absence, absence_reference, absence_sources,
    reconnect, reconnect_reference, reconnect_sources, reconnect_permit,
    permit, context, sources, references,
)
verify_usb_reboot_qualification_phase(
    payload, *, expected_sha256,
    original_baseline, received,
    absence, absence_reference, absence_sources,
    reconnect, reconnect_reference, reconnect_sources, reconnect_permit,
    permit, sources, references,
)
```

Independent inputs must be closed and exact:

- `original_baseline` is the existing presence-binding keyword set: original
  `UsbQualificationPlan`, its full `EvidenceReference`, declared
  `V2JournalEvent`, original `UsbQualificationPhase` BASELINE, its reference,
  and all three baseline source byte strings. `received` contains the original
  received-camera submission, assessment and review used to verify the plan.
- `absence` is the complete `UsbPresenceQualificationPhase`; its four source
  roles are operation, operator_event, owned_presence_run and host_boot. Require
  genuine physical-node ABSENT provenance and complete clean ownership, not
  endpoint absence, PRESENT, HELD or a mechanical report.
- `reconnect` is the complete `UsbReconnectQualificationPhase`, with all five
  independent source roles and its separately retained `ExactOperationPermit`.
  Rebuild it against the same baseline/absence. Require locally complete
  `RECONNECT_OBSERVATIONS_RETAINED`, not merely a cached status or self-hash.
- `permit` is the distinct original AFTER_REBOOT `ExactOperationPermit`.
  Descriptor evidence retains its hash, not the full permit: never synthesize
  the missing original from that hash. Original-store authentication of both
  permits remains the later reader's responsibility.
- New `context` has the existing launch/operation/operator/start/finish fields.
  New `sources` and `references` have exactly operation, operator_event,
  native_enrollment, owned_usb_run and host_boot. Each full reference must match
  its own exact payload hash/length; a preparation reference cannot substitute
  for the separately retained operation. Reject aliases and role swaps.

Proposed source caps remain 80/8/768/128/32 KiB respectively; operator and phase
subjects remain bounded at 8 and 32 KiB. Retain only bounded manifests, exact
hash-backed value views, provenance, execution facts, boot relation, ordered
checks and missing requirements in the phase, not nested copies of history.
The immediate predecessor is reconnect; bind the plan/baseline/absence hashes
as well. The only successful local status is `REBOOT_OBSERVATIONS_RETAINED`;
otherwise retain `HELD`. All authority flags remain false.

### Reconstruction and chronology

Reuse `usb_identity_phase_operation` and `verify_phase_operation_context`:
AFTER_REBOOT is already ordinal 3, with predecessor equal to the exact reconnect
phase SHA. Rebuild the full campaign/preparation from that operation, current
identity/runtime review and independent permit; verify retained owned evidence.
Phase, metadata operation, campaign operation, attempt and permit identities
must not reuse any earlier phase's corresponding identities.

Use the existing owned `HostBootObservation` v2 and
`compare_boot_observations`, but add the stronger phase bound:

```text
reconnect completion < reported new boot epoch <= new phase Begin/start
Begin/start <= operator report <= fresh acquisitions/publications <= preparation
preparation <= exact scope review <= boot observation <= USB query <= phase finish
```

Require clean physical owned boot provenance, the same host and
`SAME_HOST_DIFFERENT_BOOT` relative to reconnect. The existing comparison checks
the new boot against the prior boot observation, which can precede reconnect's
USB query; that alone is insufficient. Use the full provider response to check
the new epoch against reconnect completion and the new context start. Same boot
after app restart or Fast Startup, reused observations, another host and unknown
ownership must hold. SMBIOS UUID and confirmed LastBootUpTime are provider
reports, not cryptographic attestation.

No duplicate acquisition-ledger input is needed in the first codec. The
post-reboot start bound plus the later preparation's requirement that every
logged acquisition follow that exact Begin/report proves the required order
transitively. Native packets do not supply trusted acquisition timestamps.
The inert codec must keep metadata-acquisition freshness false: the service
must later authenticate the context/start event equality and all three actual
Arrival completion-log joins. Do not claim that a declared time proves them.

Enforce the stronger boot-epoch bound in the separate boot collector before
`QUERY_REQUESTED`, as well as in this final codec. An invalid restart must not
consume a descriptor attempt first. Cross-phase chronology uses UTC and the
provider boot epoch: monotonic counters can restart with Windows, so a lower
counter in the new boot is valid. Keep monotonic ordering and deadlines local
to each owned execution; never compare those counters across the host restart.

Reuse `_observed_usb_fields` for descriptor/native interpretation. Require
received-label and generic/descriptor serial agreement, VID/PID agreement,
actual USB3 operation, and exact baseline/reconnect identity, physical node,
topology and driver continuity. Boot time is expected to differ; other missing
or changed identity/driver observations hold. Preserve native HELD data and
unknown counts without converting them to zero or a fabricated observation.

## Slice 2: inert preparation and boot-report contracts

New modules are `physical_camera_usb_reboot.py`,
`physical_camera_usb_reboot_constants.py` and `physical_usb_reboot_boot.py`.
They do not create an original store, acquire metadata, construct an observer,
run a query or register a wizard action. Their actual original-store admission
and service composition remain the next slice, not a hardware-only dependency.

`UsbRebootPreparation` binds the exact new Start event, operator report,
enrollment/reference, phase-bound operation, runtime file report and all three
metadata publication rows. Its builder takes the same nine predecessor inputs
as `verify_usb_reboot_predecessor`, followed by those new subjects, preparation
time and operator. Its verifier rebuilds the bytes against independently supplied
predecessors, Start/report and enrollment originals. The unchanged phase-neutral
ledger validator checks order, closed roles, timestamps and completion flags;
current metadata IDs cannot reuse either baseline or reconnect acquisitions.
All freshness/authority flags remain false until the future owner authenticates
the real completion log. Timestamps alone do not prove a publication.

`original_usb_reboot_predecessor(workflow, *, received)` is an owner-supplied
data adapter for complete v12, not a filesystem reader. It requires all eleven
retained reconnect roles, exact source manifests, the independently decoded
original permit and a full clean result/receipt consistent with the verified
owned execution. The received submission/assessment/review trio is explicit.
The caller must first authenticate the entire original workflow, journal,
admission facts and sibling campaign family; a saved diagnostic JSON copy does
not satisfy that requirement.

The pure boot APIs are:

```python
build_usb_reboot_boot_intent(
    *, preparation, preparation_reference, reconnect, reconnect_reference,
)
verify_usb_reboot_boot_intent(
    value, *, expected_sha256,
    preparation, preparation_reference, reconnect, reconnect_reference,
)
verify_usb_reboot_boot_observation(
    value, *, intent, expected_sha256, requested_event,
)
classify_usb_reboot_boot_observation(
    value, *, intent, expected_sha256, requested_event, reconnect_boot,
)
```

The intent retains the exact historical host-boot manifest and reconnect finish
derived from the supplied reconnect, plus the current preparation/report/Start
references. It binds the existing fixed script hash and unchanged 30-second
admission, 10-second process and 2-second cleanup budgets. It is explicitly
`DECLARED_BOOT_SCOPE_NOT_EXECUTABLE`. The report join requires one exact intent
reference in the original-shaped BOOT_REQUESTED event and checks its source,
session, trial, phase, launch, header and preparation/request/execution order.

The classifier preserves uncertain cleanup before testing restart relations.
An otherwise clean report requires the exact independent old boot original,
same host/different boot and `reconnect finish < new epoch <= Begin`. All
cross-boot times are UTC; new lower monotonic counters remain valid. Its output
is a derived terminal label, not permission to query USB. The future collector
must retain a returned report even after Stop/context loss, authenticate and
commit its terminal outcome, and leave USB collection as a separate action.
That original collector is **not implemented** by these pure APIs.

### Verification checkpoint (2026-09-09)

These are scoped software checks, not a whole-repository pass or physical
commissioning. All host/device/process facts in the new fixtures are explicitly
modeled. The selected predecessor regression command excludes the twelve
actual incapable-child cases; no actual child, CIM or device call is claimed.

| Scope | Result | Preserved fresh directory under `.codex-preserved` |
| --- | --- | --- |
| Initial reboot phase suite | 24 passed / 537.82s | `usb-reboot-codec-20260909-01` |
| Exact epoch endpoints and received-stage reference alias | 2 passed / 40.20s | `usb-reboot-codec-extra-e012e3ce738b4fd5b60f89bec0b4c8eb` |
| Reboot preparation and owner data adapter | 8 passed / 222.02s in root rerun; prior full-run completion unavailable and not counted | `reboot-preparation-root-20260909-03`; earlier `reboot-preparation-20260909-01` and `reboot-preparation-20260909-02` preserved |
| Boot scope/report/classifier | 10 passed / 146.41s | `reboot-boot-scope-20260909-03` |
| Extra boot request header/cardinality/payload boundaries | 1 passed / 17.53s | `reboot-boot-request-boundaries-20260909-01` |
| Earlier-card historical display/denial and payload preservation | 5 passed / 32.75s | `usb-reboot-prefix-history-974b439de0a64820a718c3b82a449d21` |
| Host-boot, unchanged reconnect boot and preparation regressions | 94 passed, 12 deliberately deselected / 315.95s | `reboot-predecessor-boot-regressions-20260909-01` |

The new groups above cover 50 distinct passing tests, separate from the 94
selected predecessor regressions. Do not add the two earlier preparation smoke
tests again or infer a result for the full run whose completion was unavailable.
Black checked all eight reboot source/test files; scoped mypy checked eight
source files, including the four historical-card corrections. Independent
static review found no concrete phase/boot-codec defect. This does not replace
the future original-reader/collector/service/UI acceptance.

Two earlier boot test runs are preserved. Scope 01 stopped during fixture setup
because a test blocked the generic observer facade used by the predecessor's
incapable injected fixture; native/CIM/process entry points remained blocked.
Scope 02 passed six tests, then the reference-substitution test supplied an
invalid content-addressed reference before reaching its intended comparison.
Only these test inputs/guard placement were corrected. Production budgets and
validation rules were not changed to obtain the passing scope-03 result.

Both launcher `-Check` modes returned `READY_FOR_DIAGNOSTICS`, with camera/arm
`NOT_CONNECTED`, zero events/operations and false physical authority. Export
directory was the confirmed workspace folder. Current checked source binding:
`fcbd7115705e27c5e465cf0551c848b57adf4a50e35cd2109d66ce61132ddc93`.
This is newer than the independently frozen reconnect run-06 build. Do not
rewrite old originals to this new fingerprint or treat them as current sessions.

## Installed v13 original and application contract

The constants, original reader, private prefix propagation, storage grammar,
preparation, boot owner, service and exporter now use the following layout.
Full public acceptance remains pending as distinguished above.

Use one `usb_qualification_reboot` sibling after an eligible full v12. Use
new `camera-usb-trial-reboot-<role>-v1:<phase-id>` labels and
`CAMERA_USB_TRIAL_REBOOT_<EVENT>_<PHASE_HEX>` events. Reuse these eleven ordered
role categories and unchanged individual caps:

| Role | KiB |
| --- | ---: |
| operator_event | 8 |
| enrollment | 768 |
| preparation | 128 |
| operation | 80 |
| policy_review | 8 |
| runtime_review | 8 |
| identity | 16 |
| boot_request | 16 |
| host_boot | 32 |
| execution | 128 |
| phase_record | 32 |

Total: 1,224 KiB, calculated from the role caps. The seven-event path
uses existing V2 transitions, without same-state events or stage PASS:

| Event | Stage-4 result | Exact references, sorted by evidence ID |
| --- | --- | --- |
| PREPARATION_REQUESTED | WAITING_OPERATOR | Original reconnect phase |
| PREPARED | REVIEW_PENDING | First four new roles |
| REVIEWED | BLOCKED | First eight new roles |
| BOOT_REQUESTED | WAITING_OPERATOR | Boot request |
| BOOT_RETAINED / BOOT_HELD / BOOT_UNCERTAIN | BLOCKED / BLOCKED / SIDE_EFFECT_UNCERTAIN | Boot request and host boot |
| QUERY_REQUESTED | WAITING_OPERATOR | Identity, boot request and host boot |
| RETAINED | BLOCKED | All eleven roles |

The cache shape follows v12: phase_id, phase, state, events, the eleven
role records, original_campaign and original_campaign_event. Role records keep
document/evidence_sha256/reference/retention. Keep the existing distinction
between a complete request-plus-report preparation boundary, INCOMPLETE writes,
reviewed/boot/query boundaries, held/uncertain boot, ORIGINAL_CAMPAIGN_HELD and
RETAINED_BLOCKED. Only the appropriate unused current-launch boundaries admit
the next explicit action. A pending boot/query or partial attempt is never
automatically completed or replayed.

Implementation contract (steps 1–4 installed; full public acceptance and step 5 pending):

1. Join the inert preparation/report contracts above to actual original
   completion-log authentication and independently reviewed originals. Implement
   the one-shot original-stage boot collector. It must verify DIFFERENT_BOOT, not
   reuse reconnect's SAME_BOOT classifier. Preserve returned reports on Stop;
   conservative HELD cannot downgrade uncertain cleanup. No USB query follows
   held boot, and boot collection never starts USB automatically.
2. Add an original v13 reader and separate Setup purpose. Authenticate the
   complete real v12 snapshot/prefix and all original roles/campaigns before
   accepting the successor. Preserve public v1-v12 defaults. Exclude only the
   exact authenticated new IDs when reconstructing historical inventories;
   never fabricate an earlier snapshot/head. Admit at most the fourth
   descriptor campaign, partitioned by its exact operation, while preserving
   the complete sibling/global-attempt audit and separate presence family.
   Do not mistake `original_usb_reconnect_predecessor_v12` for a complete
   reconnect verifier: that helper returns its absence predecessor. Add a new
   adapter requiring original `RETAINED_BLOCKED`, a locally complete reconnect
   phase, a clean `SEALED_KNOWN` campaign and the separately retained permit.
3. Add five explicit actions to the existing USB owner: Begin, Prepare, Review,
   Collect host boot, Collect USB. Route fresh metadata publications only to
   this phase after durable completion logging. Existing metadata controls and
   explicit same-original Refresh remain prerequisites. Every action rechecks
   current source, header/head, full inventory and unused original state; use
   original-store canonical inventory hashing, not a different JSON dialect.
   Historical reconnect must remain historical after a new app launch. The
   reboot owner needs a separately verified current Setup context; do not relax
   reconnect's launch guard or fall back into an older phase on a missing or
   stale new token. Prioritize explicit reboot routing only for its own tokens.
4. Add bounded cached UI/terminal projections and a versioned full export.
   Preserve all older subjects, partial action diagnostics, campaign originals
   and known committed events even after outer publication failure. Reopen is
   readback, not authorization. Keep the selected export parent, existing
   sanitizer/attachment budgets and authority ceilings. Derive any v13-only
   snapshot allowance from actual added role caps; test rather than enlarge
   unrelated historical/cache/export limits. Inner process, READY, permit and
   cleanup budgets remain unchanged.
5. Separately specify a heterogeneous four-phase series/assessment/review.
   Existing `UsbQualificationSeries` v1 accepts only old homogeneous phases
   and intentionally remains BLOCKED for physical-node absence. Reconstruct
   BASELINE, physical ABSENCE, reconnect and reboot through their own codecs;
   never relabel them into v1 or remove its hold. Final stage-4 acceptance and
   any explicit stage-5 entry require a further reviewed contract.

## Negative tests and completion gates

First exercise only the inert codecs, forbidding filesystem/process/device
access and using explicitly modeled physical-shaped originals:

- Change/re-hash each predecessor or source; reject wrong references, swapped
  roles, unknown fields, forged dataclasses, noncanonical/invalid hashes and
  caller-authored success/authority/value claims.
- Reject endpoint-only absence, physical PRESENT/HELD, incomplete reconnect,
  old standalone descriptor operations and reused admission/phase identifiers.
- Hold same boot/new launch, a different host, legacy/unowned/injected boot,
  new boot before reconnect completion or after Begin, reversed observation
  order, clock discontinuity and missing native counts.
- Hold serial/unit/physical-node/topology/driver changes and missing values;
  test USB2 versus actual USB3 operating semantics without changing the parser.
- Ensure the report alone never proves reboot and old v1 phase/series bytes and
  unconditional assessment holds remain unchanged.

Then test the original/application joins: actual completion-log membership and
fresh IDs; source/launch/inventory drift; exact role/event membership and extra
sibling attempts; every partial write; lost completion, Stop, unknown cleanup,
recreated owner and new-launch no-replay. Test before-admission and post-effect
failures separately, retaining full originals and unknown accounting.

Finally run a fresh isolated hardware-free public flow with real original
storage, tickets/logs and production timing contracts over explicitly modeled
peers. Verify full export/restore, fresh original reopen, unchanged earlier
subjects and all later-stage holds. Preserve failed runs; never retry their
consumed requests or widen a budget to obtain green acceptance. This proves
software integration only. Actual received-unit/host observations and final
independent qualification remain required.

Adding this successor changes the source fingerprint. Create its entire test
prefix under the final frozen reboot-enabled build, then model the new launch
and boot. Do not migrate today's preserved v12 original to the new source or
rewrite its source binding. Reuse the existing runtime/operation/campaign and
metadata-ledger components; no generic phase framework or extra registration
layer is needed for this successor.
