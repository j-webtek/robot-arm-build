# USB identity: controlled wizard integration work order

Status: original baseline service/UI join verified with hardware-free tests.
Physical hardware execution NOT_RUN. The broader camera/arm plan remains open.
This is the next part of `CAMERA_USB_IDENTITY_IMPLEMENTATION.md`, not a
replacement for the camera/arm developer playbook or its acceptance criteria.

## Active application implementation

This increment implements the original-stage/service/UI join below. Work
is split into original v8 readback/session integration, the application USB
service, shared Arrival/browser/terminal actions, and complete bounded exports.
Public actions are explicit inspect, review, collect and export operations;
there is no device query on startup, refresh, inspection or review. Collection
must reach the existing consumed-permit owner using current original facts.
The initial observable result is one baseline USB diagnostic with saved failure
and recovery guidance, not completed reconnect qualification or camera capture.

Acceptance for this join includes actual original-store reopening, failure
retention, exact action confirmation and completion publication, reconstruction
of every supplied export subject, both launcher modes and shared UI tests.
Hardware-free tests must label modeled inputs and use only incapable children
where the real Windows ownership path is exercised. Existing stage-4 metadata
and physical authority semantics remain unchanged.

### Operator flow being integrated

1. Finish and separately review the original camera-identity metadata. This
   retains the selected native endpoint and the five metadata roles without
   pretending that metadata review has qualified camera identity.
2. Choose **Inspect fixed USB identity files**. It checks the pinned runtime
   files and original selected target; this action does not query a USB hub.
   The original stage enters inspection WAITING_OPERATOR, retains its exact
   inspection role, then enters REVIEW_PENDING.
3. Choose **Review exact USB baseline query** and review the displayed target,
   policy, fixed runtime and effects. Distinct operator/reviewer labels are a
   procedural check, not authentication of two different humans. Exact policy,
   runtime review and admission identity originals are retained separately.
4. Choose **Collect one controlled USB baseline** and confirm the one-shot
   query. It may open/query the selected camera's USB path; it does not capture
   frames, write camera settings, open arm serial or power/move the robot.
   Report actual opens when a native receipt exists and UNKNOWN when it does
   not. Do not translate a diagnostic HELD result into qualified identity.
5. Inspect the outcome and choose **Export original USB baseline evidence**.
   Export is available for retained failed/historical attempts too; it does not
   query or replay the device. A quarantined original remains read-only.

The exact five-event original suffix follows permitted V2 transitions:
INSPECTION_STARTED (WAITING_OPERATOR), INSPECTED (REVIEW_PENDING), REVIEWED
(BLOCKED), QUERY_REQUESTED (WAITING_OPERATOR), QUERY_RETAINED (BLOCKED).
For uncertain effects, the original campaign retains execution/result evidence
but quarantine prevents the later stage writes. The UI must show this narrower
retention instead of fabricating execution/outcome stage references.

### Developer export contract

`physical_usb_identity_export.py` exposes pure
`prepare_usb_identity_diagnostics_export()` and
`restore_usb_identity_diagnostics()`, plus explicit
`export_usb_identity_diagnostics()` with the assigned parent, source, launch,
Stop event and bounded deadline. Input is the service's complete cached
`rocell.wizard_usb_identity_diagnostics.v1`, not an arbitrary original-store
path. It includes the latest five metadata roles, USB baseline roles, file
inspection attempt and current retained dispatch attempt when present.

The standard export receipt lists README.md, report.json, events.jsonl,
manifest.json and `attachment-usb-identity-part-01.json` through at most `08`.
The report includes a compact state/failure index, per-subject hash coverage,
part hashes and reconstruction/redaction status. Ordinary JSON containers are
deduplicated and split without changing the existing eight-attachment,
one-MiB-per-attachment or eight-MiB-total limits. Credentials are redacted before
removing nesting; a changed subject is explicitly NOT reconstructible as its
original evidence. Identifiers, paths and operator labels can remain private.

All supplied records remain in the reconstruction, including duplicate paths
to the same original payload and partial terminal results with `receipt=None`.
Referenced earlier records are not claimed as copied originals unless their
bytes are actually supplied. Export verification is integrity checking, not
original-store authentication or permission to operate hardware.

Current export verification: 34 tests pass in 2.83 seconds, including an actual
incapable one-process Windows helper, refused admission with no owner creation,
exact original-byte reconstruction, partial diagnostics, credential redaction,
large/deep reports, changed parts and no-overwrite exports. A preceding combined
new/legacy export selection passed 61 tests in 19.43 seconds. These selections
overlap. The export module passes mypy and formatting checks. Combined public
service/original-store integration is still being verified below.

### Integration findings and repairs

Independent review found that the export's top source label could differ from
the source inside the supplied diagnostic graph. The USB exporter now requires
the same source in preparation and reconstruction; a new exporting launch is
still permitted. Historical evidence retains the original service/source label,
not a replacement label for today's checkout. The expanded export suite passes
36 tests in 2.88 seconds, with formatting and mypy clean.

The first actual original-store/public-action run successfully completed USB
inspection and review with current logged publication. Query integration is
still under test. A separate full-history test exposed that the existing
coordinator started the permit clock before read-only leased admission checks.
Those checks could consume the slack between a 30-second permit lifetime and
the required 25-second query campaign before a permit was returned.

For the exact new USB composition only, first issuance is now timestamped after
the complete read-only prepare scope has successfully released its leases and
before the first permit is constructed. A second actual-storage run showed
that lease cleanup itself also consumed the original five-second slack; it is
part of preparation, not worker execution. There is still no energy envelope.
The permit remains 30
seconds, the campaign remains 25 seconds, and execution must fit its original
remaining window. Repeated prepare returns the same original permit, never a
renewal; slow consumption still refuses dispatch. Legacy camera/energy issuance
timestamps are unchanged. Seven clock tests cover those boundaries, including
slow cleanup and a cleanup fault that cannot publish or cache a permit. A
combined 116-case new/legacy coordinator selection passes (three actual-storage cases
were deliberately deselected). Actual full-history timing must still be measured
before this repair is claimed to make the complete query path usable.

The public test also exposed an original-record mismatch: the reused legacy
identity fixture has no initial eight-domain configuration record. Current
setup deliberately retains that record when prerequisites are collected. USB
preflight now explicitly holds a legacy session that lacks it; it does not
create a record or invent its observations during inspection or query. The new
full-flow fixture uses the actual current builder and original-store write at
the same prerequisite boundary, while old tests preserve the legacy default.

The local browser's fresh rehearsal Camera page and new USB baseline panel
have been visually checked. All four physical USB forms are disabled there,
the panel reports NOT_STARTED/NOT_PUBLISHED, and viewing it makes no hardware
call. The temporary server and tab were closed after inspection. A combined
export, USB service-boundary/UI, action catalog, policy, campaign and owned
runner regression passes 346 tests in 11.26 seconds. This includes incapable
Windows child tests, not physical USB execution, and is not the entire suite.

### Reviewed timing correction for the full original history

The post-cleanup timestamp correction alone did not make dispatch usable:
the actual full-history run still spent more than five seconds reacquiring
leases, independently auditing originals, rereading admission and durably
reserving/consuming the permit. It correctly refused worker entry. Keep these
fresh checks; do not replace them with stale admission caches.

Independent application and Windows reviews confirmed that the existing
25-second campaign budget is a **ceiling**, not a requirement to grant exactly
25 seconds. The USB-only coordinator correction now uses
`min(armed_at + 25 seconds, original permit expiry)` and refuse dispatch unless
at least the fixed 20-second prepared lifecycle remains. The 30-second permit,
25-second ceiling, 18-second owned execution cap, two-second cleanup reserve,
native ten-second limit, source checks and no-replay behavior stay unchanged.
Legacy camera and energy-envelope full-window behavior stays unchanged.

This is not a guarantee that a query starts: the existing runner independently
requires 20 seconds before inspection and again after pinning. Further fresh
PRE_START/RELEASE checks may still exhaust the remaining window and cause a
retained hold. No deadline is renewed, and no cleanup budget is borrowed.
Verify clipped-window dispatch, insufficient-window refusal, post-pin refusal,
legacy bounds and full original-store/public UI behavior before acceptance.

The corrected actual NTFS full-history test passed in 143.36 seconds: one
modeled worker entered after actual durable consumption, and its unknown-count
evidence survived quarantine and fresh original-store reopening. The complete
execution time includes original retention and sealing; it is not a native USB
timing measurement. All later stages remained PENDING. Eight original-join and
substitution tests also pass the strengthened independent deadline verifier.
That verifier checks the recorded deadline against the original permit and
25-second ceiling; it does not invent an unretained armed timestamp.

The public wizard test subsequently completed inspection, review and collection
with correct unknown counts and one-shot behavior, then found an export type
mismatch. `dataclasses.asdict` preserves enum and tuple objects. The service
now projects its trusted typed originals through canonical JSON at the export
boundary; original canonical bytes/hashes remain identical. The exporter stays
strict about JSON values. Three focused real-file export/restore regressions
pass. The full public flow is being rerun with both unknown accounting and a
fully accounted known-HELD diagnostic outcome.

### Frozen-source startup and packaging check

Current application source binding:
`fe0c6c85831a76cd418a88ddd2e8b47125477722bca562e43ff6980ab3b89dd6`.
Both launcher `-Check` modes exit zero with READY_FOR_DIAGNOSTICS, zero
operations, USB NOT_STARTED and no physical authority. Both use the confirmed
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports` parent.
The CLI now flushes its local launch URL before entering the server loop;
13 parser/launcher tests pass, including that pipe-backed startup regression.

At this source, the combined USB/export/UI/actions/legacy coordinator/CLI
selection passes **480 tests in 11.25 seconds**, with 11 actual-file/process
cases deliberately deselected for their separately recorded runs. These are
scoped selections, not a full repository suite. The actual incapable Windows
child also passes with a 24-second original window: peak process count one,
five consumed checks, 65 modeled native calls, five opens/five closes and both
cleanup confirmations. Six pure deadline cases cover 24/25-second compatibility,
rehashed out-of-range deadlines and post-pin time depletion before child start.

The offline wheel at
`software/runs/usb-baseline-wheel-7d33ccf4446f4c75a92e0e3e7ef41ed8/`
matches all **299** source package entries (296 Python and three UI assets),
with no missing, extra, duplicate, case-colliding or changed entries. All 303
hashed wheel RECORD entries verify. Wheel SHA-256:
`71c83980b556d9948793466578e878e6158cb955aa643607034e3e1f80000af2`.
The adjacent `verification.json` retains the full packaging check. No dependency
installation, network package fetch, native rebuild or physical query occurred.
The earlier provisional wheel was left untouched and is not this checkpoint.

### Public-flow acceptance harness correction

The next two-scenario run passed every application, original-store, no-replay,
counter, export reconstruction and strict cached-view assertion, then failed
only when its blanket no-process fixture rejected the fixed Node DOM renderer.
Both complete exports were verified and preserved original bytes; no production
change was needed. The test now permits only the exact existing Node executable,
`-e` and fixed renderer script, only after the service/export assertions. All
device entrypoints and every other process command remain forbidden. It uses
mocked fetch with a cached snapshot, not a running server or native provider.
The corrected run passes **both scenarios in 482.44 seconds**, including actual
Arrival tickets and completion logs, original NTFS retention/readback, strict
browser/terminal rendering and exact export reconstruction. All four actions
succeed as diagnostic operations; each test worker runs exactly once. The
unknown-count case keeps receipt/counts unknown and quarantines the original;
the known-HELD case retains the six-role outcome without quarantine. Both keep
stage 4 held and every later stage PENDING. Physical USB, camera and arm
entrypoints were not executed. Only the fixed cached Node renderer ran in that
test; separate incapable Windows-child results are recorded above.

### Preserved acceptance exports

The passing public-flow bundles were copied unchanged into the user's assigned
workspace export folder, under
`software/runs/wizard-exports/hardware-free-usb-baseline-20260909-verified/`.
Both copies pass `verify_export()` with absolute local paths. That API rejects
relative paths by design; resolve a trusted workspace path before calling it.
No manifest or exported payload was changed, and no previous export was
overwritten. The collection's README labels modeled physical-mode inputs and
the prohibition on using them as real commissioning evidence.

- Unknown accounting/quarantine: bundle
  `wizard-20260909T063642434428Z-a5dc526e392e4f52a5217788facda456`,
  manifest SHA-256
  `f911ba548ec703ba26c76a0a0c5b1dc10816271547b00ef870ea8527ee323c2b`.
- Known-HELD/six roles: bundle
  `wizard-20260909T064059998774Z-7531eff15d504bf1b67523104df3078b`,
  manifest SHA-256
  `d85d68f4288906b7c1404b8cfb95ef7d49e3e044185310ee90a166ba8a844613`.

Integrity verification does not qualify the purchased camera or arm. Both
reports retain no physical authority and must not be imported into an actual
received-hardware onboarding session.

## Remaining work after this baseline

1. Implement and qualify a separate bounded physical USB-node absence producer
   and fresh host-boot acquisition. An empty camera endpoint list or a new app
   launch cannot substitute for either observation. Audit the host-boot process
   owner separately; the USB child tests do not qualify CIM execution.
2. Join the existing four-phase comparison codec to original series records,
   explicit unplug/reconnect/reboot guidance and exact review. The current
   baseline and cached export must remain readable without replay.
3. Complete stage admission for finite camera probe/settings/frame acquisition,
   then measured intrinsics, fixed-overhead registration and target validation.
4. Join received RoArm identity, explicit safe power procedure and bounded
   feedback-only serial commissioning. No automatic homing, movement or port
   fallback is introduced by this USB baseline.
5. Complete measured robot/board/tool calibration and supervised noncontact
   acceptance before releasing individual keyboard presses or Android taps.
   Existing simulation and task planning remain usable without this release.

## Operator outcome

The local wizard must let an operator inspect and explicitly review the exact
USB-query helper and selected camera, collect a bounded identity observation,
see both successful values and actionable failures, and export the complete
original diagnostics to `software/runs/wizard-exports`. Merely opening the UI,
refreshing status, inspecting files or reviewing a report must not open a hub.
No camera capture, arm serial access, power, motion or contact is authorized by
this operation. Hardware-free tests must exercise the same ownership and
original-storage seams using a separately linked incapable child.

## Versioned admission decision

Preserve the existing stage catalog v2/revision 3 and all historical readers.
Add a closed, versioned **stage-4 policy amendment**, not a replacement stage
list or a general-purpose override. `rocell.usb_identity_stage_policy.v1` binds
the original catalog hash and canonical stage-order hash. Only the new
`PHYSICAL_DIAGNOSTIC_USB_IDENTITY` domain may interpret this amendment, only
for `physical-native-usb-identity` at CAMERA_IDENTITY, using
BOUNDED_CAMERA_CAMPAIGN and CELL -> SESSION -> CAMERA leases. The old catalog
still admits only metadata at stage 4 for its existing consumers.

Use a fresh original camera session under the new source. Its header remains
immutable. Retain and separately review the exact amendment, target and runtime
subjects as original stage-4 evidence before an effectful action is possible.
Existing v7 metadata assessments remain BLOCKED with their original meaning;
they are not upgraded by recognizing a new schema. A later closed original
workflow extension owns the new policy/review/observation series.

The new coordinator challenge and permit bind the policy SHA-256 explicitly.
The new M1 reservation retains the complete policy, hazard, eight configuration
epochs and selected-identity document. The selected identity binds exact
original references and the policy/runtime reviews, underlying metadata
selection, native identity, endpoint, device instance and operation. A review
does not hash itself: the operation subject excludes its subsequent review;
the prepared request and admission identity include the review hash.

## Independent implementation lanes

1. Root: this work order, exact policy/identity codecs, application campaign and
   dispatch/service joins, original role grammar and wizard publication/export.
2. Windows agent: new runtime registration/review/preparation, owned parent and
   retained evidence. Keep old native camera runners and native USB source
   build pins unchanged unless a concrete defect requires a separately logged
   repair. The real runner is callable only after exact consumed M1 admission;
   no unconditional production hold and no Boolean enable switch.
3. Persistence agent: new coordinator domain, exact policy-bound snapshot,
   retained M1 facts/readback and a purpose-specific runtime transaction.
   The original camera and new USB record directories must be audited together
   against the complete cell-global attempt ledger. Do not ignore attempts
   belonging to another domain or accept duplicate reservations/nonces.
4. Series agent: immutable role-split USB/boot comparison and human-readable
   value differences. Consume the actual runner's typed execution evidence,
   not caller assertions about process ownership or cleanup.

## Process and evidence limits

One operation, no automatic retry, 25-second outer campaign budget,
128 KiB retained campaign evidence, at most 32 hub opens, 128 bounded query
reads, zero configuration writes, zero frames and 32 closes. Descriptor
control reads remain a bounded camera effect, not passive OS inventory.
The parent allows 18 seconds execution plus 2 seconds cleanup within the
original permit deadline; native admission is 5 seconds and acquisition
10 seconds. Require sufficient native/cleanup time before RELEASE.

Create suspended, assign a kill-on-close Job before first instruction,
validate READY and exact child/request challenge, then release once and close
stdin. Acknowledge the consumed scope once; at most five planned scope
revalidations leave room within its eight-check cap. Polling uses cheap
Stop/deadline/application checks without renewing the permit. Retain bounded
stdout/stderr prefixes, late valid bytes, actual resource counts and cleanup
uncertainty. Killing a process is not proof of USB handle cleanup.

Pin the fixed EXE and immutable build record; inspect the full fixed source
roster before launch. File agreement approves neither the Windows driver nor
received hardware. Production USB/CIM/device entry points are NOT_RUN here.

## Qualification series

Retain baseline, explicit disconnect observation, fresh reconnect observation,
and an observation after an actual host restart. Distinguish provider-reported
host/boot identity from cryptographic attestation. Compare received serial,
VID/PID, physical unit, host, native target, driver and port topology values;
show differences alongside exact original references.

USB3 qualification requires an available EX_V2 operating-SuperSpeed flag.
Capability bits alone do not pass. EX can report HighSpeed while EX_V2 reports
operating SuperSpeed; do not invent an exact negotiated Mbps value.
An endpoint-only absence observation is narrower than physical USB absence:
retain it as a diagnostic and keep physical-disconnect qualification blocked.
Timeout, incomplete enumeration or error never proves absence. Missing phases
and inconsistent originals remain BLOCKED, not silently omitted from review.

## Verification and handoff

- Pure validation: extra fields/types, changed policy/catalog/source/target,
  review substitution, serialization limits, malformed raw USB evidence.
- Owned incapable process: actual Job/pipe handshake, Stop, deadline, bad READY,
  stale scope, no retry, retained failure bytes and terminal cleanup outcomes.
- M1 integration: exact prepare/intent/arm/consumption, failed and successful
  original readback, camera/USB shared-ledger coexistence, restart and quarantine.
- Service/UI: no effect on GET/refresh/review, exact action confirmation,
  stale-context rejection, original completion before current publication,
  readable blocked reasons and full export to the assigned parent.
- Series: new app launch is not reboot; V2 speed semantics; serial/unit swaps;
  absent/missing/partial records; complete fixture series clearly labeled.
- Re-run both launcher checks and relevant legacy camera/rehearsal tests.

Record actual commands, outcomes and source checkpoint below. Do not report
full onboarding complete while capture, calibration, serial commissioning,
noncontact acceptance or task execution remains pending.

## Implementation evidence

Implemented in this increment:

- `usb_identity_stage_policy.py`: fixed policy amendment, exact policy review,
  and review/reference-bound admission identity. The historical catalog hash
  stays `5cfd61200815afcf1c3568e9eb312d8d2ae9176a85d446930b29322a962ddd3a`;
  the amendment hash is
  `ede85912b512ca4936d972f26d2cdf4c3a6011e0b4564542c11004dc04252ad6`.
- `commissioning_usb_identity_persistence.py`, coordinator and M1 runtime:
  purpose-specific original transactions, policy-bound challenges, complete
  retained admission facts and a shared camera-family original-record audit.
- `usb_identity_registration.py`, `owned_usb_identity_runner.py`,
  `owned_usb_identity_evidence.py`: fixed intended runtime, separate review,
  owned handshake, bounded execution, cleanup and retained original streams.
- `physical_usb_identity_campaign.py`: one exact pre-review operation subject,
  actual-permit preparation, consumed-scope runner and evidence/effect mapping.
- `physical_usb_identity_dispatch.py`: exact production M1 owner, one-shot
  prepare/execute, stage-only terminal readback and pending/current publication.
- `physical_camera_usb_qualification.py`: role-split plan/phase/series,
  human-readable comparison, blocked assessment and separate exact review.

Important storage distinction: a retained `CampaignEvidence` lives in the
coordinator's immutable domain record, **not** the stage evidence inventory.
Dispatch returns a `rocell.usb_identity_campaign_reference.v1` identifying that
original record. It never fabricates a stage `EvidenceReference`. The next
original-stage series writer must explicitly retain and join a stage role to
the audited campaign original before a phase may reference it.

Missing native counters after release produce the new USB-only
`RetainedUncertainCampaignExecution`: retain the complete bounded evidence,
then quarantine with `receipt=None`. Unknown counts are never replaced by
zero. A complete clean native HELD result can be a known diagnostic failure;
neither a known result nor a successful descriptor query is qualification.

Executed verification so far (selections overlap; not a full repository run):

- Root policy tests: 78 passed; campaign operation/permit tests: 27 passed.
- Root new/legacy pure selection: 169 passed, 3 deselected in 1.25 seconds.
- Root combined policy/campaign/owned-runner/series/USB-core selection:
  168 passed, 2 actual-M1 cases deselected in 63.46 seconds. Some additional
  peer test cases were being added after that command began.
- Persistence lane: 110 pure tests (25 new, 85 legacy); 2 genuine isolated
  NTFS/M1 USB cases in 73.15 seconds; 6 existing actual camera persistence
  cases in 62.11 seconds; 18 selected legacy source/rehearsal cases in
  42.28 seconds. Device facts/workers in these storage cases are modeled.
- Root three new production modules pass mypy; formatting checks pass.

Actual owned-process plus M1/application-owner integration and final source/
launcher checks are complete for this internal increment; results appear below.
All physical USB/CIM/camera/serial calls remain NOT_RUN. The following
application step is still required; these components do not by themselves add
a public camera-connect button.

## Next application join: original stage roles and visible actions

Implement a closed v8 original stage-4 suffix, initially for one explicit
baseline query. Preserve public v7 validation and its metadata-only BLOCKED
assessment; a private prefix verifier must receive the real complete original
snapshot and authenticate only its already committed metadata prefix. Never
construct a fabricated earlier snapshot/head or silently drop unknown packages.

1. File-only inspection collects the exact policy, fixed runtime file report
   and operation subject from the original reviewed metadata selection. Show
   target values and the distinction between file agreement and received-unit
   qualification. GET/view/review performs no device query.
2. A separate review retains the exact policy review, runtime review and
   prepared-operation subject under three closed stage-role labels. Bind the
   real header, source, metadata original and both review references. Partial
   writes are visible as incomplete originals, not accepted or auto-retried.
3. Commit an explicit USB-query WAITING_OPERATOR event after the reviewed v7
   prefix; no stage PASS or implicit stage-5 entry. The selected-identity document
   includes those original references. Authenticate originals under real leases
   before every fresh facts snapshot; cached UI labels are not admission.
4. The explicit collect action uses `PhysicalUsbIdentityDispatchOwner` with the
   same original runtime/header/source, frozen policy, actual eight-domain
   configuration vector and current hazard/selection facts. Fresh source,
   original reference, Stop and deadline checks remain mandatory.
5. Read the sealed campaign originals under stage-only leases. Transfer the
   observed run to a stage-owned role only through an explicit bounded original
   writer, retaining the campaign-reference join. A failed or uncertain result
   stays inspectable/exportable and cannot grant identity qualification.
6. Add a separate bounded local host-boot action and the declared trial plan;
   continue the four-phase series with fresh reviewed metadata. Endpoint-only
   absence and its missing acquisition nonce/time remain explicit blockers;
   a complete physical-disconnect provider is not implemented by these codecs.
7. Arrival owns tickets, confirmation, Stop, result retention and completion
   logging; the USB service owns original semantics; shared browser/terminal
   presentation consumes only cached views. Add an exact complete diagnostic
   export under the confirmed workspace parent, with private-value notices.

Test the complete public action lifecycle, exact source/camera changes between
prepare and release, original restart, partial writes, no retry, quarantine
readback, full export reconstruction and both startup modes before calling
that UI join complete. The broader playbook still includes capture/controls,
installed calibration, serial/firmware commissioning and supervised arm tests.

## Process-accounting correction before final verification

Final validation found an actual second member in the incapable helper's owned
Job: `C:\Windows\System32\conhost.exe`. A bounded test queried only members
of that exact Job and confirmed two distinct live PIDs, both members, while the
configured active-process limit was still one. Do not describe earlier passing
pipeline tests as verification of the newly enforced one-process observation.
The stricter USB runner now retains a specific process-count failure before
RELEASE instead of losing the evidence or accepting an unexplained overrun.

The existing shared owner uses CREATE_NO_WINDOW. Microsoft distinguishes that
flag from DETACHED_PROCESS, which does not inherit the parent's console; this
is not a Job breakaway flag. See [process creation flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags)
and [Job process identifiers](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list).
The helper uses inherited stdin/stdout pipes and has no AllocConsole or
AttachConsole call in its reviewed source.

Implemented `WindowsOwnedUsbPipeProcess`, a purpose-specific detached-pipe
owner for the new USB runner only. The legacy owner's default flags remain
unchanged. Suspended creation, atomic Job assignment, explicit handle
inheritance, the one-process limit and memory/stream/deadline bounds remain.
There is no caller-selectable flags parameter, conhost exclusion or widened
process budget. Both actual incapable Job/pipe tests observed a peak of one
process after this correction. An extra member still causes a retained hold.
Native build records and EXEs remain unchanged; the shared Python owner changed
and historical runtime reviews are not silently renewed.

## Verified internal checkpoint — 2026-09-09

Source binding observed by both launchers:
`a662818db01e70d493a8a9778a2c80358a4152f14591f98d5050e245c54917f0`.
This is the application's code/configuration fingerprint, not a digest of this
document or a new native build approval. These selections overlap and are not
a full repository test run.

- Post-correction root regression: **267 passed in 12.43 seconds**, covering
  owned-process/native-camera/admission transport, the new USB policy/campaign,
  owned USB runner and actual Job accounting.
- Existing wizard actions and Arrival service: **105 passed in 16.82 seconds**.
  This selection ran before the narrow USB console correction; legacy launch
  behavior is unchanged and is covered in the post-correction selection above.
- Final series module: **35 passed in 122.40 seconds**. Its two actual owned
  process cases also passed separately in 16.46 seconds using four incapable
  child executions. Modeled boot changes do not become actual CIM observations.
- Windows runner lane: **45 passed in 2.98 seconds**, including the two actual
  one-process Job cases. Formatting and type checks pass for the new runner,
  registration and evidence modules.
- Original M1/application dispatch lane: **6 passed in 89.37 seconds** with
  real isolated storage and a modeled runner. A strengthened partial-terminal
  readback regression separately passed in 22.67 seconds.
- The corrected combined original-M1-to-incapable-child test passed in
  **27.50 seconds**. The owned runner interval was **3.657 seconds**, leaving
  **21.328 seconds** before its original deadline. Five actual M1 scope checks
  took 0.671/0.672/0.672/0.688/0.688 seconds; the journal's EFFECT_ARMED to
  SEALED_KNOWN interval was 4.9983921 seconds. Do not confuse whole-test setup
  time with the bounded campaign interval.
- That combined case retained **44,901 bytes** of original evidence, SHA-256
  `ccafdb412db4a22518a44c63285f74acb8e0382de241754b02d883b80be35aff`,
  with peak process count one, confirmed process/native cleanup and modeled
  native counters of 65 seams, 55 queries, 5 opens and 5 closes. Configuration
  writes and frames were zero; power remained UNKNOWN. These are incapable
  test observations, not received-camera measurements.
- Three existing native CTest groups passed in 5.91 seconds. The production
  USB executable and build record were not rebuilt or executed.
- Root policy/campaign/dispatch modules and the corrected Windows owner pass
  mypy; selected production/test files pass Black. The final series module
  also passes its own formatting and type checks.

Both `start-rocell-wizard.ps1 -Mode rehearsal -Check` and
`start-rocell-wizard.ps1 -Mode physical -Check` exited zero with the source
binding above, `READY_FOR_DIAGNOSTICS`, zero operations and no physical
authority. Both report the user's confirmed default export parent:
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
Neither check connected a camera or arm. Camera runtime dispatch remains
dormant; arm connection and received-unit verification remain NOT_RUN.

Next implementation must follow the original-stage/service/UI join above and
the [series API guide](PHYSICAL_CAMERA_USB_QUALIFICATION_API.md). A complete
trial needs up to **3,200 KiB across 19 new role documents** (excluding existing
received originals referenced in place); preserve those split originals rather
than forcing a complete trial into one 1 MiB attachment. Series display remains
24 KiB and must be paired with the owned-run summary for actual execution,
failure, no-attempt and effect-count information.

Before introducing an actual host-boot action, audit its separate local CIM
process owner and budget on this Windows host. It currently derives from the
legacy process owner; this USB-only detached-process verification does not
qualify that different launch path. No actual CIM query was performed here.
Physical USB-removal evidence, live camera capture/settings, installed
calibration, serial/firmware commissioning, supervised noncontact acceptance
and typing/tapping UI execution remain outside this completed increment.
