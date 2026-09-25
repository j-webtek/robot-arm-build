# Camera settings readback: correct the stage-5/6 dependency

10 September 2026. Implementation work order within the
[camera/arm developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md). The preceding
[public probe checkpoint](CAMERA_PROBE_PUBLIC_WIZARD_CHECKPOINT.md) remains a
record of that earlier source/test snapshot, not current release evidence.

The first internal campaign/service/data slice is implemented and verified below.
The subsequent original-admission, public UI and stage-assessment slices remain
unfinished. The overall camera/arm application goal has not been completed.

## Finding and required outcome

Stage 5 is `camera_mode_controls`, not merely capability discovery. The native
probe intentionally has no requested mode, observed mode, control writes or
frames. Human approval of its capability list cannot prove settings readback.
The existing v2 capture registration belongs to stage 6,
`camera_frame_freshness`. Requiring stage 5 PASS before obtaining its first
settings readback creates a dependency cycle. Do not solve it by weakening PASS.

The corrected sequence is:

1. Authenticate the original setup and current logged camera identity; execute
   and retain the existing one-use capability probe at stage 5.
2. Explicitly select a reported native mode and supported electronic controls.
   Publish an immutable **staged, not applied** settings candidate. Mechanical
   lens focus is not an electronic control inferred from the camera listing.
3. Admit a separate, bounded **configuration-verification capture at stage 5**.
   Use the existing capture runtime, native owner, coordinator, original store,
   readback comparator and pixel-ingestion pipeline. No second camera controller.
4. Compare the observed native mode and each requested control against that
   exact candidate. Keep missing, mismatched or unsupported readbacks explicit.
   Retain failure/cleanup evidence; do not automatically repeat an uncertain run.
5. Obtain the remaining required mode/control and reopen evidence, assess it
   against the original stage policy, and obtain its separate human review.
   One successful readback image alone is not a stage-5 PASS.
6. Only then admit the existing stage-6 freshness capture(s). Freshness has its
   own timing/buffering criteria; identical pixels of a stationary board are
   not, by themselves, proof of stale acquisition.
7. Continue optics, measured placemat registration, arm connection/feedback and
   noncontact baselines. Motion and keyboard/phone contact remain separate gates.

## First implementation slice: exact campaign and internal data path

Add one closed application campaign profile, not a native protocol revision:

| Profile | Application plan | Fixed action | Required stage | Native purpose |
| --- | --- | --- | --- | --- |
| Existing probe | `rocell.physical_native_camera_activation_campaign.v2` | `physical-native-camera-activation-probe-v2` | 5: mode/controls | probe |
| New settings readback | `rocell.physical_native_camera_configuration_campaign.v1` | `physical-native-camera-configuration-capture-v1` | 5: mode/controls | capture |
| Existing freshness capture | Existing v2 plan | `physical-native-camera-activation-capture-v2` | 6: freshness | capture |

The new plan also carries the exact `verification_stage` field. This and its
distinct schema change the operation hash even when every native setting matches
an existing freshness plan. Original permits/evidence from the two stages must
not be interchangeable. The existing v2 canonical documents and action mapping
remain unchanged; unknown keys/schemas continue to fail exact restoration.

An exact boolean `configuration_verification` selects this closed profile in
internal Python planning APIs only. It is not a browser form field, admission
fact, policy override or permission. True is legal only with the v2 capture
runtime and explicit settings, a 5,000-ms native budget, one frame and equal
per-frame/total byte limits. The enclosing 25,000-ms camera campaign and existing
evidence/record/native byte ceilings remain unchanged. One open/close attempt,
exact control-write budget and actual observed accounting still apply.

Ownership:

- `camera_activation_campaign_contract.py`: recognize the fixed new action and
  validate its stage, worker, native purpose and one-frame budget independently.
- `physical_camera_activation_campaign.py`: construct/restore the exact plan;
  use the same capture preparation and original consumed-scope execution.
- `physical_camera_capture_workflow.py`: generate the distinct settings plan and
  require its original operation hash at readback/ingestion. The ordinary capture
  path cannot silently accept a settings-capture receipt, or vice versa.
- `physical_camera_acquisition_service.py`: plan/compare the same profile under
  its existing acquisition lock and pass it to the existing staged-data path.
- `physical_camera_dispatch.py`: derive the profile from the exact campaign,
  retain/reread the original permit and complete evidence pair, then explicitly
  propagate the profile to the sink. No current publication before completion.

This slice must NOT expose a public configuration-capture button, admit the new
action through the probe facts provider, mutate original stage state or claim
received-unit qualification. Its purpose is to remove the incorrect internal
stage binding before building substantive original admission around it.

## Next slice: original-bound admission and public operation

This remains required after the first slice; no inert plan supplies these facts.

- Require the same current Session/store and logged enrollment objects, original
  v16 preparation/review chain, known original probe result, paired evidence,
  successful cleanup, retained admission documents and published capability hash.
- Bind the exact staged settings payload/epoch, selected identity, operator,
  operation hash and both reviewed native runtimes. Do not trust imported
  diagnostics or cached capability summaries as original admission.
- Retain the settings intent and fresh condition reports in the original request
  documents. Keep actuator supply disconnected as required by the stage catalog;
  an operator checkbox remains a report, not electrical observation.
- Pin the probe attempt's diagnostics independently before the acquisition
  service replaces its last dispatcher with a settings/freshness dispatcher.
  A later successful capture must not make the earlier probe export point at
  the wrong original attempt or lose its failure/publication history.
- Implement capture-specific headroom. It must include raw native frame output,
  ingested native-byte copies, bounded preview/dataset metadata, native process
  output and remaining original campaign records. The probe's zero-frame
  headroom calculation is not sufficient. Observe the assigned volume at each
  admission boundary; free space is observed, never reserved by a check.
- Reuse original authentication before the short-lived permit. Revalidate the
  actual original snapshot/leases, current enrollment/settings/source, Stop,
  runtime and capacity across reservation, release and publication. Do not extend
  device authority to pay for slow file ingestion.
- Add the explicit one-use UI queue before intent logging, two-stage result
  publication, pinned attempt completion and dedicated bounded diagnostic export
  to the confirmed workspace export root. A generic image/capture result must not
  be mislabeled as freshness or stage acceptance.
- Keep status/navigation inert. Show last-captured-image age and settings epoch;
  never start a stream/reconnect/retry through polling. Failed publication leaves
  only historical evidence, with no misleading current image.

## Stage assessment and reopen acceptance

Build a policy-derived evidence assessment, not a checkbox-to-PASS shortcut.
It must list required native mode/transport/manual-control/readback/reopen checks
individually and point to their original observations. Determine the exact
received camera/driver capabilities during onboarding; do not manufacture a
control or high-speed mode from an advertising title.

A separately authorized subsequent open may be needed for reopen consistency.
Each operation needs its own finite plan, current admission and cleanup. Do not
reuse a consumed permit or treat a successful subprocess restart as camera
reopen evidence. A pending reopen requirement keeps stage 5 incomplete.

Stage 6 must consume its own original captures/timing evidence under the accepted
settings epoch. Any lens, support, crop, resolution, orientation or fixture change
invalidates the dependent calibration according to the existing policy.

## Test and delivery gates

First-slice tests run without camera/serial access or camera-capable processes:

1. Pure restoration: no file/device access; old v2 plans unchanged; new profile
   has distinct operation/action/stage; nonliteral switches and widened budgets
   refused; unknown/partial plans rejected.
2. Core/retention: stage/action/worker substitutions refused; capture evidence
   binds to the new original permit; wrong native purpose and frame counts
   refused; one-use execution/accounting/uncertainty semantics unchanged.
3. Internal workflow/service: explicitly modeled probe -> settings -> settings
   capture -> pixel ingestion -> completion publication; then a separate
   freshness capture. Mismatched settings, changed stage profile, failed cleanup,
   Stop and stale context must withhold current data. Test pixels are synthetic.
4. Actual local original-store persistence: retain, close and reopen a modeled
   stage-5 capture, verify its unchanged full original pair and result, and show
   no replay or leaked lease. Model hardware/admission facts explicitly.
5. Regression: old probe/capture tests, probe-only admission refusal, startup
   diagnostics in both modes, type/format checks. Preserve fresh test reports;
   do not overwrite prior checkpoints or claim the entire suite was run.

The later public slice additionally needs the full original-history + real-store
path, log/source/identity failure publication cases, export/reconstruction and
real received-hardware qualification. Record unfinished gates in the handoff.

No physical device operation is authorized by this developer work order. It
specifies implementation and incapable testing, not a commissioning result.

## Verified first-slice checkpoint

Source fingerprint:

    2f2077e22d8e3183cf8cafb8aea7a779edcd5079041bbece3b75d3586bbde214

Implemented in the five production modules listed above. The exact settings
profile now runs through the existing core/dispatcher/service and native capture
preparation. Its readback and actual test-pixel ingestion remain completion-gated.
An internal composition test performs probe -> explicit settings -> stage-5
readback capture -> separate stage-6 capture, with distinct original operations.
No public action/catalog field, original facts provider or stage-PASS path was
added. Probe-only original authentication rejects both capture action IDs.

Final selected JUnit reports in `.codex-preserved`:

| Report | Passed | Seconds |
| --- | ---: | ---: |
| `settings-readback-regression-20260910-01.xml` | 167 | 68.453 |
| `settings-readback-storage-20260910-01.xml` | 2 | 25.407 |
| `settings-readback-public-final-20260910-01.xml` | 72 | 210.134 |

These contain **241 distinct passing test IDs**, zero failures, errors or skips.
They are selected regression/composition tests, not the entire repository suite.
Black checked all 11 changed Python files; Mypy checked all five changed
production modules. No production file changed after those test runs began.

The first draft had one invalid test expectation: it compared two separately
timestamped enrollment owners. The test now compares profiles derived from the
same exact identity snapshot. A second draft had two fixture-import setup errors;
the required fixture imports were corrected, independently tested, and the whole
72-case public regression lane rerun. Earlier reports remain preserved, not
silently replaced or counted as clean final runs.

Both actual launchers passed `-Check` in physical and rehearsal modes on the
fingerprint above: READY_FOR_DIAGNOSTICS, zero operations, camera and arm
NOT_CONNECTED, probe NOT_ATTEMPTED, no physical authority. The public capture and
arm-connect actions remain disabled. Startup opened no server or device. Both
use the confirmed default export directory:

    C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports

All 46 native files from the preceding v2-runtime checkpoint still matched their
indexed hashes. No native source/binary was changed, rebuilt, repinned or executed.
The incapable test owners produce explicitly modeled native observations; tiny
YUY2 test pixels are synthetic. Actual NTFS original-store tests cover both known
and uncertain settings captures, full paired evidence/facts, fresh reopen, lease
release and no replay. Their predecessor/admission facts remain modeled; they do
not prove a full original onboarding history or received-unit operation.

Copy-only developer delta:

    software/runs/wizard-exports/developer-checkpoint-settings-readback-20260910-01

This includes the changed modules/tests/guides, selected reports and a hash index.
It is not a complete source archive, importable original Session or device permit.
No hardware-build files or existing diagnostic bundles were overwritten.

### Immediate continuation

Implement the original-bound settings-capture admission/public slice above,
starting with capture-specific output/ingestion/record capacity and immutable
settings/probe-original references. Preserve the probe attempt packet when the
service advances to another dispatcher. Then add explicit public operation/log
publication/export, followed by policy-derived stage-5 readback/reopen assessment.
Do not return to the old capability-approval -> stage-5 PASS shortcut.

Received-camera verification, measured overhead-camera/placemat calibration,
RoArm identity/startup/feedback integration and separately authorized keyboard/
phone contact still remain. A passed simulated readback does not close them.

## Original-admission continuation: timing design correction

The first original-bound service composition exposed a real timing failure:
duplicated ledger audits consumed the short permit's pre-dispatch allowance.
Sharing one freshly audited record set for immediate same-call probe-reference
and capacity calculations fixed the first capture without retaining a cache.
The subsequent explicit capture still failed as the retained ledger grew.
Both draft reports are preserved; neither is a clean verification checkpoint.

Before further implementation, narrow the timing correction to the distinct
settings-capture action only:

- Keep the original 30-second maximum permit lifetime and 25-second campaign
  ceiling unchanged. Set its worker deadline to the lesser of that ceiling and
  the original permit expiry, as already done for bounded USB campaigns.
- Require at least the fixed native capture process lifetime (15 seconds run +
  2 seconds cleanup) before dispatch. The native preparation/handshake must still
  repeat its complete-lifetime checks before process start and release. No
  renewed expiry, automatic retry, shortened native cleanup or changed binaries.
- Validate the exact configuration permit before applying this rule. Older
  probe/freshness actions, energy envelopes and arm actions retain their rules.
- Add clock-boundary tests for a shortened but sufficient remaining window,
  an insufficient window and unchanged legacy capture behavior. Confirm the
  floor against the actual fixed process budget. Repeat the actual NTFS service
  test with two separately requested captures and the real original admission.

This is a deadline ceiling correction, not proof of acceptable worst-case
full-history performance. Full-history and maximum-record performance remain
public-release gates. All observations in these tests use incapable native
owners and explicitly modeled setup authentication, never received hardware.

## Verified original-admission checkpoint

Final application source fingerprint:

    580c3e02c2a8582fb4282e057b321de0516fa66c3a55406ca6090802fea1ef5c

Implemented the original-bound configuration reader, substantive scoped facts,
capture-specific capacity, internal service entry and independent probe/capture
diagnostic snapshots. The Arrival probe exporter now uses its pinned original
probe snapshot rather than whichever dispatcher ran last. The new operation
uses the existing M1/core/native supervisor/ingestion/publication mechanisms.
No new public capture action or physical-stage PASS shortcut was added.

Each current configuration admission performs one fresh complete-family record
audit. Only immediate in-call computations share those bytes; subsequent calls
audit again. Capacity includes earlier USB records under the unchanged shared
record/byte quotas. Original Session/source/enrollment/Stop/snapshot checks still
bracket the read-only capacity observation. No output is created by admission.

The settings-only deadline now uses at most the original remaining permit time,
with the unchanged 17-second capture-process/cleanup floor. Clock tests verify
sufficient/insufficient remaining time, an unchanged legacy capture rule and
alignment with the actual fixed native budget. Actual local-store composition
passes two separately requested settings captures with distinct attempts, no
replay and no leaked leases. Failed/unknown observations cannot publish a frame.

Final selected JUnit reports in `.codex-preserved`:

| Report | Passed | Seconds |
| --- | ---: | ---: |
| `configuration-admission-complete-20260910-01.xml` | 28 | 609.077 |
| `configuration-core-final-20260910-01.xml` | 311 | 81.829 |
| `configuration-public-final-20260910-01.xml` | 160 | 468.169 |

These are **499 distinct passing test IDs**, with zero failures, errors or skips.
This is a selected suite, not the entire repository. The complete new lane and
the public lane ran concurrently in different fresh disposable stores. Their
wall times are not received-hardware performance measurements. The source above
was unchanged throughout these final runs. Black checked 14 changed Python files;
Mypy checked all eight changed production modules.

Earlier failed drafts remain preserved:

- `configuration-admission-20260910-01.xml`: 12 passes, then a settings attempt
  held before native evidence. Repeated audits consumed the dispatch allowance.
- `configuration-admission-nominal-20260910-01.xml`: the first capture completed,
  but a separately requested second capture could not fit the full 25-second
  ceiling. The settings-only remaining-time correction above addresses it.
- `configuration-admission-final-20260910-01.xml`: four passes and a test-fixture
  failure. Its supposedly changed source hash was identical to the fixture's
  source. The test now uses a genuinely different hash and verifies late source,
  enrollment, snapshot and Stop changes. Modeled audit fixtures were also aligned
  with the actual complete-family keyword and dictionary return contract.

Clean intermediate runs also remain on disk, but are not counted again in the
499 final IDs. They include the five-case nominal/deadline lane, the 19-case
failure lane and the earlier 311-case core regression. The complete final lanes
above rerun the changed behavior after the shared-family capacity correction.

Both actual launchers passed `-Check` in physical and rehearsal modes on the
final fingerprint: READY_FOR_DIAGNOSTICS, zero operations, camera/arm NOT_CONNECTED,
probe NOT_ATTEMPTED, public capture and arm-connect disabled, no physical authority.
They use the user-confirmed workspace export folder. All 46 indexed native files
still match the preceding runtime checkpoint. None was rebuilt, repinned or
executed as a camera-capable process, and no camera/serial hardware was opened.

Copy-only developer delta:

    software/runs/wizard-exports/developer-checkpoint-configuration-admission-20260910-01

See `CAMERA_CONFIGURATION_ADMISSION_HANDOFF.md` for the exact component joins,
test boundaries and next public operation/log/export steps. The current actual
NTFS service tests still explicitly model setup semantic authentication; they
are not a full original-history or received-unit qualification. The quota test's
injected USB sibling is only an arithmetic model. Full-history/max-record timing,
public configuration UI/export, policy-derived mode/reopen/freshness assessment,
measured calibration, RoArm connection/startup/feedback and separately authorized
keyboard/phone contact remain unfinished. The overall wizard goal is not complete.

### Public wizard integration follow-through

The later `CAMERA_CONFIGURATION_WIZARD_WORKORDER.md` implements the queued
settings-capture/publication/export join. Its current component map, operator
sequence, verification appendix and remaining full-history/qualification work
are in `CAMERA_CONFIGURATION_WIZARD_HANDOFF.md`. Earlier checkpoint claims and
copies above remain historical; this continuation does not qualify hardware or
complete the overall camera/arm onboarding application goal.
