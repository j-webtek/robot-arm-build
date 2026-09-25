# Physical USB absence: application integration contract

Status: public hardware-free nominal acceptance passed, 2026-09-09. The presence
campaign, retained phase codec, reviewed boot collector, v11 original reader and
five-step service/UI are implemented. Component and original-reader tests pass;
the full five-step public NTFS run 02 passes in 700.42s, including export/restore
and fresh original reopening without replay. Observations remain explicitly
modeled; no received-hardware qualification or stage PASS follows. This continues
[the reconnect work order](USB_RECONNECT_WIZARD_IMPLEMENTATION.md), not a new or
reduced goal. The static Arducam/RoArm-M3 Pro build and Freeze 011 stay unchanged.

## Intended operator experience

After a complete original trial BASELINE, Camera shows the exact physical USB
instance and asks the operator to unplug that camera's labeled cable. The
operator explicitly reports unplugging; software does not infer that act from
an endpoint disappearing. The wizard checks the current host/boot, presents the
exact presence scope for review, then collects two bounded physical-node
samples. Each action has a preview, one-use ticket, progress, retained results
and export. Nothing here powers or moves the arm.

Keep five explicit actions and separate boot/presence approvals:

1. Begin/prepare absence, file-only. Establish the new original phase/interval;
   record the operator report, reconstruct the complete baseline binding,
   inspect the fixed presence runtime and retain operation plus boot intent.
2. Review the exact boot scope, file-only.
3. Collect boot once. Retain the full owned report; only a clean physical
   SAME_HOST_SAME_BOOT may prepare the final presence review. That preparation
   is file-only, not automatic query permission.
4. Review the exact presence target, helper, policy and operation, file-only.
5. Collect the separately admitted presence query once; preserve outcome and
   cleanup evidence, reconstruct the retained phase and export.

No live camera endpoint is required after unplugging. Derive the target only
from the authentic completed baseline physical USB mapping. Never fall back
to the first camera, friendly name, camera index or user-entered USB instance.

## Component and authority boundaries

| Component | Input/output | Authority |
| --- | --- | --- |
| physical_usb_presence_binding.py | Reconstructs plan/declaration/baseline and all baseline sources | Pure binding; original references still need authentication |
| physical_usb_presence_campaign.py | New phase/launch/nonce, full binding, fixed runtime, original review and consumed permit to full owned result | Existing consumed-scope runner only; no retry or arbitrary command |
| owned_usb_presence_runner.py | Fixed pinned helper, bounded request/READY/RELEASE/output, measured cleanup | Exact presence list scope; no device handles, frames, writes, serial or power |
| physical_usb_presence_phase.py | Operator event, operation, owned presence and fresh boot; independent baseline originals | Pure reconstruction; no stage PASS, capture, motion or contact |
| physical_usb_absence_boot.py | Exact baseline/operation/report intent, separate review, requested event and full boot report | One fixed bounded local boot scope; no presence query or reboot command |

PhysicalUsbIdentityService remains the public owner. Add a private absence
composition helper through it, not another queue, daemon or frontend state
machine. Arrival owns tickets, execution, cancellation, exact result retention
and durable completion publication. Setup serializes the original lifecycle.
M1 separately owns leases, current admission, one-use attempts and quarantine.

## Implemented retained phase codec

UsbPresenceOperatorEvent uses schema rocell.usb_presence_operator_event.v1.
It records the exact baseline binding, new phase ID, launch ID, operator label,
phase-start UTC and report UTC, with OPERATOR_REPORTED_CAMERA_USB_UNPLUGGED.
Both timestamps are server observations; report time is not a claimed physical
disconnect time. Mechanical-unplug, continuous-absence and authority flags stay
false. A new absence phase ID cannot equal its baseline phase ID.

UsbPresenceQualificationPhase uses the separate schema
rocell.usb_presence_qualification_phase.v1, not the older endpoint-only
rocell.usb_qualification_phase.v1.

Its independently referenced source roles are ordered:

| Role | Maximum bytes |
| --- | ---: |
| operation | 32 KiB |
| operator_event | 8 KiB |
| owned_presence_run | 128 KiB |
| host_boot | 32 KiB |

The derived phase itself is capped at 16 KiB. It retains the literal physical
target/filter, provenance, outcome, boot relation and exact checks/missing
requirements. Full sample/counter/cleanup details remain in the owned result.

Use build_usb_presence_qualification_phase with original_baseline, context,
sources and references. The baseline mapping is the existing binding-builder
keyword set: plan/reference, declaration event, baseline/reference and all
baseline sources. Later verify_usb_presence_qualification_phase reconstructs
independently read originals. A syntax-valid record and its own hash do not
authenticate storage or establish measurement truth.

The record requires physical owned clean boot, same host/boot as baseline,
operator report → boot → final review → query chronology inside the phase,
physical provider provenance, complete released results, confirmed process/
native cleanup and two complete samples of the exact node absent.

PRESENT, native HELD, missing receipts, injected boot origins, host/boot changes
or uncertain cleanup yield HELD. Missing native receipt counts remain unknown.
ABSENCE_OBSERVATIONS_RETAINED is a narrow observation state, not completed
four-phase qualification or stage PASS. It proves neither mechanical cause
nor continuous absence.

## Original journal contract

### Active v11 implementation contract

The original reader/Setup owner, public service/UI owner and presence dispatcher
are now being integrated in parallel. These are active edits, not completed
public acceptance. The separate cached readback version is
`rocell.physical_camera_source_workflow_readback.v11`; v10 retains its meaning.
One absence suffix is allowed after an authentic completed v10 BASELINE. Its
full cached key is `usb_qualification_absence`, with phase ID, fixed phase name,
state, at most ten events, the nine nullable records below, and nullable
original campaign/result-event joins. Interrupted records are never replayed.

| Original absence role | Maximum bytes |
| --- | ---: |
| operation | 32 KiB |
| operator_event | 8 KiB |
| preparation | 16 KiB |
| boot_intent | 16 KiB |
| boot_review | 8 KiB |
| host_boot | 32 KiB |
| runtime_review | 8 KiB |
| execution | 128 KiB |
| phase_record | 16 KiB |

The roster totals 264 KiB. Closed constants live in
`physical_camera_usb_absence_constants.py`; services, reader and exporter share
them rather than duplicating an independent event grammar. Preparation is a
separate exact file-inspection record referring to the original operation and
operator report; it does not duplicate a different target or grant permission.

The public action IDs are `physical_usb_absence_begin`,
`physical_usb_absence_boot_review`, `physical_usb_absence_boot_collect`,
`physical_usb_absence_runtime_review` and `physical_usb_absence_collect`.
Their outer deadlines are respectively 180/120/180/120/180 seconds. A separate
explicit absence storage scope uses the same maximum 180 seconds as the
baseline phase; default/legacy storage stays 120 seconds. All effect, process,
permit and cleanup budgets remain unchanged.

`PhysicalUsbPresenceDispatchOwner` uses the existing seven-document original
admission facts, campaign and coordinator. It validates exact preparation before
arming, reads the complete actual terminal/evidence after execution, preserves
collected-only and unknown effects, and waits for the existing completion log
before publishing. Presence counters are Configuration Manager API calls,
device-handle opens, configuration writes and frames—not descriptor hub opens.

The dispatch adapter now passes **four actual-NTFS cases in 106.20s** and a
separate **nine pure cases in 9.87s**. The former use real original records,
leases, consumed permits, five scope rechecks, complete retained evidence and
fresh reopening. They cover known absence, missing native results/unknown
effects, readback faults and rejection of invalid preparation before intent.
Host/USB/process observations are explicitly modeled: neither invocation opens
a device, executes a child or queries CIM. Preserved actual-store fixtures are
under `.codex-preserved/presence-dispatch-20260909-02`; they are diagnostic test
originals, not received-hardware qualification. These two invocations are not a
combined 13-test public-wizard acceptance run.

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_physical_usb_presence_dispatch.py -q -s --tb=short -x --basetemp C:/Users/Jack/Desktop/robot-arm-build/.codex-preserved/presence-dispatch-20260909-02
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_physical_usb_presence_dispatch.py -q -k pure --tb=short -x
```

The first command records the historical four-case invocation, before the pure
cases were added. Do not reuse its existing `--basetemp`: pytest may clear it.
Choose a new unused directory for another actual-store run. The integrated
public baseline-to-absence acceptance test is written but has not yet passed;
it remains a separate gate from these component checks.

Diagnostic export v4 is implemented with unchanged v3 fields plus
`qualification_absence` and `qualification_absence_attempt`. It retains all
nullable roles, original campaign joins, partial attempts and unknown counts.
Its **163 combined v1–v4 tests pass in 5.09s**, including actual export files,
manifest verification, restoration, redaction, role/cap checks and refusal to
relabel new absence data as a legacy export. These tests use modeled caches,
not original-store or received-device proof. Black and scoped mypy pass; the
6 MiB input, attachment count and byte/depth/node limits are unchanged. The
selection includes the corrected ten-event roster and an interrupted
PRESENCE_REVIEW_REQUESTED export. Full
public v10→v11 export/reopen acceptance still requires the joined owners below.

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_usb_absence_export.py software/tests/unit/test_usb_trial_baseline_export.py software/tests/unit/test_usb_qualification_export.py software/tests/unit/test_physical_usb_identity_export.py -q -x --tb=short
```

Add a grammar after the complete v10 baseline without changing v10 meaning or
its nine-role roster. Authenticate the full unchanged prefix and all earlier
camera-family attempts before recognizing the new bounded suffix. Freeze the
new reader version and role caps with the original-store owner before editing
shared readers. Use shared closed event/role constants, not duplicated strings.

| Event intent | Existing stage transition | Required evidence |
| --- | --- | --- |
| Preparation requested | BLOCKED → WAITING_OPERATOR | Exact baseline predecessor; starts new interval |
| Prepared | WAITING_OPERATOR → REVIEW_PENDING | Operator event, exact binding/operation/runtime and boot intent |
| Boot scope reviewed | REVIEW_PENDING → BLOCKED | Exact independently reviewed boot intent |
| Boot requested | BLOCKED → WAITING_OPERATOR | Durable intent before one-shot dispatch |
| Boot retained / held | WAITING_OPERATOR → BLOCKED | Full owned report; no presence query if held |
| Boot uncertain | WAITING_OPERATOR → SIDE_EFFECT_UNCERTAIN | Preserve unknown effects; export-only |
| Presence review requested | BLOCKED → WAITING_OPERATOR | Clean physical same-host/same-boot; first six roles, file-only |
| Presence review prepared | WAITING_OPERATOR → REVIEW_PENDING | Same first six roles; file-only |
| Presence runtime reviewed | REVIEW_PENDING → BLOCKED | Exact original runtime-review record |
| Presence query requested | BLOCKED → WAITING_OPERATOR | Immediately after review, same reference |
| Phase retained | WAITING_OPERATOR → BLOCKED | Full acquisition/phase and original attempt join; no PASS |

The existing persistence conventions are
`CAMERA_USB_PRESENCE_RUNTIME_REVIEWED_<TRIAL_SUFFIX>` and
`CAMERA_USB_PRESENCE_QUERY_REQUESTED_<TRIAL_SUFFIX>`.
No boot or other journal event may intervene. The new original reader must
additionally bind the reviewed operation to the current absence phase.

The provisional nine-event sequence was corrected before public acceptance:
V2 does not permit BLOCKED directly to REVIEW_PENDING. The explicit file-only
PRESENCE_REVIEW_REQUESTED/PREPARED pair uses existing legal transitions without
changing V2 permissions, role caps or the five operator actions. There are now
fourteen closed absence states. Failure between the pair retains the requested
state for diagnosis/export; it does not automatically resume or query a device.
The separate final runtime-review/query pair remains adjacent.

The existing UsbTrialBootIntent and OriginalUsbTrialBootCollector accept
BASELINE only. Add an absence intent/review/collector with closed original
events and baseline joins; never relabel old bytes or allow arbitrary scripts.
Keep the fixed boot observer's 30-second admission, 10-second run and 2-second
cleanup. Do not renew or share a USB/presence permit for boot.

The additive boot component's agreed API is UsbAbsenceBootIntent,
UsbAbsenceBootReview and OriginalUsbAbsenceBootCollector(workspace, intent,
review). Intent cap is 16 KiB; review is 8 KiB; host report is 32 KiB. Build the
intent from exact operation/reference, operator-event/reference, original
phase-start event and independently reconstructed original_baseline mapping.
Review derives the original operator and requires a distinct reviewer label,
current launch and later review time; it does not authenticate two people.

The collector takes an actual original M1 transaction, intent/review references,
cancellation, original action deadline and live-context guard. Before requesting,
it reads operation/report and all baseline evidence, confirms actual declaration,
start and review event membership, and checks current header/stage/leases. Event
names are `CAMERA_USB_TRIAL_ABSENCE_<KIND>_<PHASE32>` for PREPARATION_REQUESTED,
BOOT_REVIEWED, BOOT_REQUESTED, BOOT_RETAINED, BOOT_HELD and BOOT_UNCERTAIN.
Multi-reference event lists are sorted by evidence ID. Start cites baseline
only; reviewed cites intent plus review; request cites intent only; terminal
cites intent plus host report. Role labels are
`camera-usb-absence-{boot-intent|boot-review|host-boot}-v1:<phaseid>`.
This component is implemented: **81 focused tests pass in 61.55s**, with actual
codecs and explicitly modeled transaction/observer effects. Black and scoped
mypy pass. These tests invoke no actual M1 lease, process, CIM or device API.
They cover independent original reconstruction/omissions, exact byte drift,
changed/injected boot, uncertain cleanup, pending requests, replay refusal and
partial retention. Stop/source loss during report storage or readback retains
the bytes but holds progression; a later successful check cannot erase earlier
context loss. The outer service must still independently validate completion.
That component test alone does not establish original-reader or public-service
integration; the current joined checks are recorded below.

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_physical_usb_absence_boot.py -q --tb=short -x
```

### Current original-reader and application checks

The additive v11 reader and Setup integration are now frozen. The final focused
reader/Setup selection passes **49 tests in 364.28s**. It reconstructs the full
unchanged baseline prefix, every absence boundary, clean and held boot reports,
known/unknown campaign outcomes, exact phase transfer and the legal ten-event
grammar. Requested-only phases are not resumable. A clean report conservatively
saved as BOOT_HELD stays readable; uncertain cleanup cannot be downgraded to
that state. **67 earlier deadline/public-prefix tests pass in 14.88s**. These
tests use real codecs/V2 types but modeled storage and OS observations, not
genuine NTFS admission or received hardware. Black/scoped mypy pass.

A separate exact typed v11 export crosscheck passes in 27.71s: the complete
modeled original workflow is 683,469 bytes, depth 13, with 12,637 nodes. Its
dedicated v4 export is 356,522 payload bytes in one part. Actual export files,
manifest verification and complete restoration pass without changing export
byte, depth or node limits.

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_physical_camera_usb_absence_readback.py software/tests/unit/test_usb_absence_storage_scope.py -q -x --tb=short
```

Earlier source/design/receipt/metadata cards recognize v11 as read-only history,
using the same restrictions as v10. Eight cross-owner tests pass in 82.29s over
explicitly modeled successor labels and the existing real-codec fixtures; they
do not substitute for the full original-reader checks. All non-export earlier
actions remain blocked. Four service files gained only the version roster
entries; Black and scoped mypy pass.

The baseline commit helper now consumes M1's already verified post-sync
snapshot instead of immediately repeating a full inventory read. Two focused
contract tests and ten existing composed baseline tests pass together in
254.95s; scoped mypy passes. This is transaction-local reuse only, not caching
across source/lease/action boundaries. No wall-clock improvement is claimed
before the new public acceptance run.

Five-action forms/catalog/result validation passes **166 pure cases in 0.73s**.
The real result-envelope producer and Arrival validator distinguish CM API
calls from device-handle opens, preserve unknowns, reject Boolean-as-integer
counter substitutions and forbid command/authority overrides. These tests run
no process, original store or device.

The service and browser/terminal changes are now frozen. All **27 new composed
cases** have passed across bounded selections (not one aggregate invocation):
19 initial cases, three additional service/facts/failure-export cases, one
requested-only case and four early-dispatch refusal cases. Known/unknown final
renderer cases were rerun after the phase-summary wording changes. Separately,
166 existing UI/Arrival cases pass in 33.15s and four strict original USB
producer-to-renderer cases pass in 63.06s. These renderers use a finite Node
fake-DOM subprocess; they invoke no production helper, CIM or device. Black
and scoped mypy pass.

Additional integration review verified:

- Fresh admission compares the entire original evidence inventory, not only
  reference membership and journal head. A same-head extra-reference negative
  test passes in 24.16s over real facts code and modeled typed snapshots.
- The refreshed phase must still be QUERY_REQUESTED with no original campaign
  before constructing a dispatcher. Existing M1 reservation already consumes
  the deterministic `usb-absence-<phase_id>` key under actual leases; no new
  global deduplication mechanism was needed.
- Each successfully committed service event is retained in private attempt
  diagnostics immediately. A later file-inspection failure can be exported
  without automatically rereading or replaying the original.
- Both phase summaries show retained RECONNECT_ABSENCE state instead of the
  earlier contradictory NOT ACQUIRED label. Review text no longer implies a
  query has not happened when its result is already present.

Both inert launch checks pass on source
`3d609d319ea26092c99bca16cf9819dc466b18bb35128a1a68752c63d819fc0a`:
READY_FOR_DIAGNOSTICS, zero operations/events, NO_PHYSICAL_AUTHORITY, trial
NOT_DECLARED and all five absence actions disabled until their original
prerequisites exist. Both modes use the operator-confirmed workspace export
parent. No server, camera, arm or device action is started by `-Check`.

```powershell
.\start-rocell-wizard.ps1 -Check
.\start-rocell-wizard.ps1 -Mode physical -Check
```

The first public NTFS absence acceptance **failed after 769.53s** in
`.codex-preserved/usb-absence-public-20260909-01`. The baseline and first four
absence actions passed, but collection failed. Its observations are explicitly
modeled: zero actual processes and zero device queries. Keep that original and
`test_actual_public_baseline_to0/absence-public-checkpoint.json` unchanged; never
clear, reuse or replay the consumed attempt. There is no full public absence
receipt/export/restore/fresh-reopen pass yet.

The retained original terminal is SEALED_UNCERTAIN with quarantine, no receipt
and no worker artifact. Its reasons include `WORKER_OR_POST_ARM_PUBLICATION_FAILED`
and `OwnedUsbPresenceEvidenceError`. A later strict artifact read masked that
primary result with "retained campaign evidence is missing or ambiguous".
The presence-specific optional reader now accepts no artifact only for an
audited original failed terminal without a receipt; known outcomes still require
their complete artifact. Present-artifact corruption and all audit failures
continue to propagate. The generic evidence reader remains strict.

The first fixture did not preserve the finalizer's exact exception message or
absolute timing, so its precise primary cutoff cannot be reconstructed from
rounded check durations. Review also found that the model omitted real runner
timing gates: the 15s remaining-fit check, the fixed 5s READY/release window and
the 13s run/2s cleanup split. PRE_START plus PRE_RELEASE alone took 6.375s in
that run, exceeding the real 5s window. Before another **new** public session,
make the model enforce the unchanged gates, retain exact failure timing and
profile the repeated original verification. Do not extend budgets, alter saved
timestamps, bypass guards or claim that modeled absence proves physical absence.

The terminal-only fix passes **18 pure cases in 9.93s** and **five actual-NTFS
dispatch cases in 133.39s**, the latter in a fresh separate
`.codex-preserved/presence-terminal-only-20260909-01` scope. An explicitly
modeled evidence-construction exception now preserves the authentic uncertain
terminal, quarantine and original reasons without inventing an artifact or
zero-effect receipt. Present/unknown outcomes, readback faults and preparation
refusal regressions also pass. No process or device ran; scoped mypy passes.
The revised timing model and pure action matrix pass 173 cases in 7.07s,
including truthful no-create, pre-release timeout and late-result retention.

Read-only profiling of preserved run 01 measured one full V2 read at
0.218–0.222s, the pure facts callback at 0.031–0.033s, and strict retained-record
components at 0.012–0.014s. The latter excludes leases/live guards and is not a
complete admission benchmark. All 144 original files (771,172 bytes) remained
byte-identical; profiling did not reopen the M1 runtime or write lease metadata.
Call inspection found ten full V2 reads per consumed recheck, six inside runtime
verification alone. New `open_with_snapshot` helpers let those two independent
runtime observations consume their already verified snapshots, reducing six
loads to two. The presence subclass also reuses its one post-admission snapshot
for header and event joins. There is no saved cache between observations,
boundaries or actions; double global-ledger head checks, full family audits,
leases and fresh package checks remain unchanged. Seventeen new snapshot tests
pass in 14.47s; 21 existing V2/M1 tests pass in 31.12s. Black/scoped mypy pass.

These changes do not prove received-hardware timing fitness. The public fixture
still explicitly models checkout fingerprint, pin/process/native observations
and wire latency. Actual source rechecks and process handshake costs must fit
the same fixed budgets in the separate received-hardware path.

Both renderers now show UNKNOWN / NOT_REPORTED when a requested/held partial
attempt lacks owned execution evidence. They explicitly warn that missing
evidence is not proof of no query or zero effects and direct the operator to
export terminal reasons without replay. Four strict reader/service/renderer and
saved-checkpoint tests pass in 84.94s; Black/scoped mypy pass. The renderer
harness uses only a finite Node fake DOM, not a production helper or device.

The failed public01 cached diagnostics were exported with the v4 application
exporter into the confirmed workspace parent:
`software/runs/wizard-exports/hardware-free-usb-absence-20260909-held`.
Its README identifies the exact bundle and original checkpoint. Manifest
verification and complete restore equality pass; all terminal reasons, unknowns
and missing phase records survive. This is a **held diagnostic export**, not a
successful public absence acceptance or a fresh original-store inspection.

After these source changes, both inert startup modes pass on
`cc88a827341471163b7fda04a825de6fbdfa0766d45d809670d598d5c48634e0`:
READY_FOR_DIAGNOSTICS, NO_PHYSICAL_AUTHORITY, zero operations/events, trial
NOT_DECLARED, five registered disabled absence actions, and the confirmed
workspace export directory. No server or hardware action was started.

The presence subclass's fresh-context change passes a combined **14 cases in
154.62s** (four actual-NTFS and ten pure) in a new preserved
`presence-fresh-admission-20260909-01` scope. The new actual-storage case checks
two independently fresh post-super snapshots, the complete family audit and
pre/payload/post package checks, then refuses twelve changed header/review/
request/package observations. Its original is unchanged and no permit or
worker is invoked. Existing terminal/sibling-audit/reopen, unknown quarantine/
no-replay and changed-current-facts regressions also pass. A final combined
mypy check of the four affected storage/dispatch source files passes.

Fresh public acceptance 02 **passes one test in 700.42s** in
`.codex-preserved/usb-absence-public-20260909-02` on frozen source above. It is a
new original with faithful modeled timing gates, not a retry of run 01. The full
baseline prerequisite, all five absence actions, nine roles/ten events, exact
original campaign, complete v4 export/restore, fresh original reopening and
no-replay checks pass. No source, policy or guard changed during the run.

Action times in order: 45.937s, 41.344s, 87.031s, 43.718s and 138.203s.
Presence rechecks: PRE_PIN 2.094s, POST_PIN 2.140s, PRE_START 2.078s,
PRE_RELEASE 2.063s, POST_RESULT 2.062s. The modeled inner admission pair fits
the unchanged five-second gate (4.141s). The nominal modeled outcome is ABSENT;
the original terminal is SEALED_KNOWN and the phase is RETAINED_BLOCKED, not
hardware acceptance. All stage-5-and-later states remain PENDING. These timings
are observations of this run, not a controlled benchmark or physical deadline
fitness guarantee.

To repeat the hardware-free public acceptance, create a **new** test scope;
never supply either preserved run's directory to pytest:

```powershell
$rocellAcceptanceName = 'usb-absence-public-' + [Guid]::NewGuid().ToString('N')
$rocellAcceptancePath = Join-Path (Get-Location).Path ('.codex-preserved/' + $rocellAcceptanceName)
if (Test-Path -LiteralPath $rocellAcceptancePath) { throw 'Do not reuse an original acceptance directory' }
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_arrival_usb_absence_ntfs_acceptance.py -q -s --tb=short -x --basetemp $rocellAcceptancePath
```

The fixture forbids actual production process/device APIs. Expected runtime is
several minutes; keep exact failed checkpoints and timing if the host cannot
meet a gate. Do not loosen the gate or rerun the consumed original.

The actual public checkpoint separately passes both strict renderers without
mutation (finite Node fake-DOM harness, no production helper). The passing
bundle and both phase receipts/checkpoints are preserved in
`software/runs/wizard-exports/hardware-free-usb-absence-20260909-verified`.
Nine generated files are byte-identical to their originals; both bundles pass
manifest verification and full restoration equals the entire saved diagnostic
cache. Its README records exact paths, timing limits and the separate manifest
file/receipt hashes. No canonical M1 original was copied, cleared or replayed.

A separate real-browser visual check of the unchanged frozen source passed in
rehearsal mode: Overview clearly showed the selected static Arducam and RoArm
as NOT CONNECTED, the zero-authority banner and pending physical stages;
Diagnostics & exports showed the exact confirmed workspace destination, zero
events and no replay. Only page navigation was performed, not a diagnostic or
hardware action. The temporary tab/server were closed after inspection and the
local listener was confirmed closed. This is visual/startup verification,
separate from public absence acceptance.

After coordinator preparation, call campaign.preparation_for_permit before
arming to reject oversize/mismatched preparation without acquiring. The runner,
not the application or campaign, acknowledges the consumed scope exactly once.

## Failure, restart and exports

- A precommitted request with no terminal result is incomplete/export-only;
  never automatically replay it.
- Late Stop, source change or failed completion logging withholds current UI
  publication even if originals exist. Failed action does not mean no effect.
- A new absence phase after app restart requires unchanged source/authentic
  baseline and fresh current-boot evidence. Prepared/reviewed absence from an
  earlier launch remains historical/export-only.
- A boot change during unplugging is not the later AFTER_REBOOT success.
- Reopen from original campaign records, not only volatile last-result caches.
  Preserve quarantined/partial evidence and unknown counts.
- Export all new roles/events/phase/attempt within declared caps, with explicit
  omission reasons. Keep the user-confirmed workspace export parent.

## Acceptance and implementation order

1. Completed prerequisite: actual-NTFS modeled-nominal baseline public acceptance
   passes two tests (397.09s), including strict service projection, all nine
   original roles, export/restore and fresh reopening/no replay. Both renderers
   also pass the separate strict projection regression. Runs 01/02 remain
   preserved failures; run 03 is a new original, not a replay. See the work order
   for commands and scope; no physical observations were acquired by these tests.
2. Freeze additive absence boot, original journal and readback contracts.
3. Test genuine M1-to-presence-campaign integration with explicitly incapable/
   modeled providers; forbid actual device APIs in hardware-free tests.
4. Implement all five steps through existing owners, with honest partial states,
   complete export and fresh readback.
5. Exercise ABSENT/PRESENT/HELD, partial receipts, boot changes, wrong unit,
   source/launch drift, Stop, deadline, cleanup, duplicate tickets and restart.
6. Add AFTER_RECONNECT/AFTER_REBOOT and a new four-phase assessment that consumes
   physical absence; keep historical endpoint-only assessment blocked.
7. Continue separately reviewed capture, optical/board calibration, arm
   connection, noncontact and contact qualification from the main playbook.

Pure codec, incapable-child or modeled nominal passes do not verify the received
camera, cable, USB speed, field of view, arm or calibration.
