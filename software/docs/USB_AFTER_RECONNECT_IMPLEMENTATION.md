# AFTER_RECONNECT implementation work order

This work order continues the verified BASELINE and physical-node ABSENCE
workflow. It does not authorize a device operation. The default export parent
is `software/runs/wizard-exports`, as confirmed by the operator.

Current acceptance status (2026-09-09): **fresh public run 06 passed** in
1,062.33s, including the complete baseline/physical-absence/reconnect sequence,
full export/restore and fresh original reopening without replay. All hardware
and process observations were explicitly modeled; production storage,
supervisor and timing gates were real. This closes the reconnect increment,
not full USB qualification or physical camera/arm onboarding. Earlier failed
runs remain preserved and export-only. See the final record below.

The final pass-06 archive verifier also passed an independent root read-only
run: all 194 copied files/6,200,520 bytes match, all three public exports verify,
the final v5 restores the entire checkpoint diagnostics exactly, and all 173
log events verify. Source originals were unchanged during this check; no
operational reopen or replay was performed by the archive verifier.

## Scope and implementation order

1. Add an inert, typed reconnect observation codec that independently rebuilds
   the actual `UsbPresenceQualificationPhase` and its baseline sources. Extract
   the existing descriptor field derivation into one shared private helper;
   preserve every historical v1 phase byte and comparison rule.
2. Add original preparation and boot-intent counterparts, then the exact v12
   original suffix and reader. Authenticate the entire original prefix and
   sibling campaign ledgers. Only the new version admits the new suffix.
3. Route five explicit actions through the existing USB owner and coordinator:
   Begin, Prepare, Review, Collect host boot, Collect USB descriptors. Attach
   fresh metadata acquisitions to only the currently active phase.
4. Add versioned full diagnostics/export and strict UI/terminal projections.
5. Exercise the complete public wizard sequence against a fresh actual-storage
   hardware-free model, including restart, export/restore and no-replay failures.

Steps 2–5 are not implied by a passing pure-codec test. Actual camera/host/USB
observations, AFTER_REBOOT and final independent qualification remain pending.
No step releases capture, arm power, motion or contact authority.

## Typed observation contract (first implementation slice)

New module: `physical_usb_reconnect_phase.py`. New closed subjects:
`UsbReconnectOperatorEvent` and `UsbReconnectQualificationPhase`, each with its
own v1 schema, rather than changing the old endpoint-only schema.

`build_usb_reconnect_operator_event` takes the plan, typed absence, new phase ID,
launch ID, operator label, phase start and report times. Its meaning is exactly
`OPERATOR_REPORTED_CAMERA_USB_RECONNECTED`; it cannot prove mechanical cause.

`build_usb_reconnect_qualification_phase` takes independent `original_baseline`
inputs (the existing presence-binding keyword set), typed `absence`, original
`absence_sources`, the independently retained `ExactOperationPermit`, new
`context`, and exact `sources`/`references` roles:

| Role | Maximum original payload |
| --- | ---: |
| operation | 80 KiB (existing descriptor-operation limit) |
| operator_event | 8 KiB |
| native_enrollment | 768 KiB |
| owned_usb_run | 128 KiB |
| host_boot | 32 KiB |

The resulting phase manifest is at most 32 KiB. It binds the original baseline
and absence hashes, new operation/context and all five references; it retains
bounded exact-hash value views, execution facts, origin labels, boot relation,
ordered checks and explicit missing requirements. Its only successful local
status is `RECONNECT_OBSERVATIONS_RETAINED`, never stage PASS. The verifier
rebuilds independent sources and compares exact bytes and the expected hash.

Required joins:

- Rebuild absence and its full independent baseline; require genuine complete
  physical-node ABSENT observations, not endpoint absence, PRESENT or HELD.
- New phase starts after absence, with distinct phase/attempt/permit/operation
  identifiers. The phase-v2 operation names the exact absence predecessor.
- Rebuild the descriptor campaign preparation from its operation, identity,
  review and independently supplied original permit. Unlike presence evidence,
  descriptor preparation retains only the permit hash, not the full permit.
  Never synthesize one from that hash. The phase execution binds its hash; the
  later original campaign/export retains its complete bytes. No query invocation
  or permit minting belongs in this API.
- Operator report, runtime review, owned boot observation and descriptor query
  occur in that order and inside the new interval. The report is not proof that
  cables were physically moved.
- Require physical USB/metadata origins, current complete owned result, clean
  native/process cleanup and SAME_HOST_SAME_BOOT relative to absence.
- Compare received serial, generic VID/PID, exact physical node, USB3 operation,
  identity, topology and driver fields with the original baseline. Changed or
  unobserved fields hold the local result; a hash-only display is not unknown.
- Original-store authenticity, newly logged metadata acquisition freshness,
  independent actor procedure and event/permit membership belong to the later
  original preparation/reader. A codec record is not proof of those properties.

All authority flags remain false, including metadata acquisition freshness and
mechanical reconnection verification. Independent-store authentication is an
explicit caller responsibility, not a claim derived from JSON shape.

## Original v12 suffix (integration in progress)

One `usb_qualification_reconnect` suffix follows a complete eligible v11.
Its eleven roles are the existing nine BASELINE role categories plus an 8-KiB
operator report and a separately retained 80-KiB operation. Existing per-role
caps are unchanged (total 1,224 KiB). Role order is operator report, enrollment,
preparation, operation, policy review, runtime review, identity, boot request,
host boot, execution and phase record.
Use `camera-usb-trial-reconnect-<role>-v1:<phase-id>` labels and
`CAMERA_USB_TRIAL_RECONNECT_<EVENT>_<PHASE_HEX>` event names.

| Event | Stage-4 result | Exact role references |
| --- | --- | --- |
| PREPARATION_REQUESTED | WAITING_OPERATOR | Original absence phase |
| PREPARED | REVIEW_PENDING | Operator report, enrollment, preparation, operation |
| REVIEWED | BLOCKED | First eight roles including boot request |
| BOOT_REQUESTED | WAITING_OPERATOR | Boot request |
| BOOT_RETAINED / HELD / UNCERTAIN | BLOCKED / BLOCKED / SIDE_EFFECT_UNCERTAIN | Boot request, host boot |
| QUERY_REQUESTED | WAITING_OPERATOR | Identity, boot request, host boot |
| RETAINED | BLOCKED | All eleven roles |

No ENTERED transition is needed. Begin retains the operator report before any
new metadata acquisition. The first request plus exactly that report is a
normal preparation boundary; partial enrollment/preparation writes are not.
Freshness must come from the coordinator's three successful, durably logged
post-Begin acquisitions, not packet timestamps or the prior launch's cache.

The reconnect report and preparation are launch-bound. With this single-report,
single-successor contract, reopening the application leaves an existing
reconnect phase historical/export-only, including a Begin-only phase; merely
reacquiring metadata in the new launch cannot update the old report's launch.
Do not implement an implicit resume by rewriting it. A future recoverable
pre-effect restart would need a separately reviewed/versioned handover contract.
Partial or consumed boot/query work must never resume automatically.

The reader must preserve strict public v1–v11 behavior, explicitly account for
all new reference IDs when rebuilding historical inventories, and partition
exactly one additional descriptor campaign by the authentic reconnect operation.
Never blanket-ignore later evidence or relax the full sibling-ledger audit.

### Contract correction found during integration

The first draft omitted the standalone operation package. The phase codec
requires an exact operation reference as one of its five original inputs; a
reference to a preparation file containing the operation is not a reference to
the operation's own bytes. The new v12 suffix therefore retains the operation
separately, verifies it against preparation, and includes its real reference in
the phase. No historical schema or reference meaning is reinterpreted.

The v12-only snapshot allowance accounts for the actual role-cap sums: 1,136
KiB BASELINE, 264 KiB ABSENCE, and 1,224 KiB AFTER_RECONNECT. The baseline
allowance is unchanged. These totals are calculated from the imported caps,
not a separately maintained estimate. Existing role caps, native/permit
deadlines and global diagnostic-export limits do not increase.

### Preparation codec implementation

`physical_camera_usb_reconnect.py` adds an inert
`UsbReconnectPreparation` (`rocell.usb_reconnect_preparation.v1`) and the agreed
role/event naming helpers. It does not register a public action or admit v12
through an old reader. The preparation subject retains exact plan/absence/
operator/enrollment references, Start event, the unchanged phase-neutral
acquisition ledger, phase-bound operation, fixed-runtime inspection report and
preparation time/operator label. The 128-KiB preparation cap is unchanged.

The builder independently rebuilds physical absence and its baseline, verifies
the Start event's exact absence reference and report binding, then matches all
three ledger document hashes and operation IDs to the separately supplied
reviewed enrollment. Ledger scope is the current source/session/trial/phase/
launch. Each acquisition must begin after the reconnect report and the preceding
publication; all three need logged completion before preparation. Review does
not convert content-shaped ledger rows into authentic event-log evidence.
That final membership check belongs to the later service/original reader.

The verifier takes the original absence, report, Start event and enrollment
independently; it compares reconstructed bytes as well as the expected hash.
No schema promotion, device access, original-store migration or replay occurs.

`original_usb_reconnect_predecessor` is the small data adapter for the future
owner: it accepts only a completed v11 projection, checks both original campaign
results are known/non-quarantined with exact transferred execution bytes, and
reconstructs the typed baseline/absence inputs. It does not replace the original
reader or authenticate a diagnostic copy. The saved public absence run-02
checkpoint passes this read-only bridge with unchanged bytes: baseline hash
`9ea4f441e48cb27a7e6d4fe2d8c20c1dce3ab2427f9c542ac40c57bee2d5ea7d`, absence hash
`e35f926697157ba393d1ca4a3165da1159458c102a75f11cfa1987574bea1b29`.
Those earlier observations were modeled. No M1 store reopen, admission, process
or device access was performed by this cached-evidence check.

## Acceptance and stopping conditions

First test the inert codec with actual closed evidence codecs and explicitly
modeled device/process facts, forbidding process/device access. Include changed
or rehashed originals, old endpoint-only absence, unknown fields, wrong unit,
boot change, late report, reused admission, role swaps and forged authority.
Retain the historical suite and compare pre/post-refactor v1 output bytes.

Then exercise original partial writes, Stop, source drift, lost completion,
duplicate requests, reopened owners and unknown effects. Preserve every failed
original; no retry of consumed work, no widening inner permits to fit a test.
Only complete public acceptance proves the UI/service/export integration.
New application launch does not prove host reboot. Later stages remain PENDING.

## Verified component results — 2026-09-09

The preceding component slice was verified on these historical source bytes
(the integration below changes preparation and related files):

| File | SHA-256 |
| --- | --- |
| `physical_camera_usb_qualification.py` | `216fbb9a022e71459914f982745aff27fa0b88e462e065c6c3696b144facb88c` |
| `physical_usb_reconnect_phase.py` | `7f4329855f3e9012d31dd7d17eed6f240d2b039609dc921c50db37d28d097f47` |
| `physical_camera_usb_reconnect.py` | `5571944635b0060bebca5444156943996e01febd7de5a9b77128b39bd48ee895` |

The existing qualification and presence suites pass **80 tests in 170.29s**.
They include existing fixed incapable-child cases, not production hardware.
The new three-case compatibility regression independently captured outputs
from pre-refactor source `e4fb88ca77c7e6defb40411b85d241bc46571731336d22e9fe91cacce9cd8d13`
and passes **3 tests in 13.15s** on the refactor. It compares exact bytes/hashes
for four held v1 phases, plan/series/assessment/review and modeled EX2/EX3
descriptor cases. No child or device runs in these new compatibility tests.

The final combined run passes **190 tests in 259.90s**, including all 18 current
reconnect phase tests, six preparation tests, three compatibility cases and
163 existing v1–v4 export cases. This supersedes overlapping interim selections.
The reconnect tests retain HELD and unknown native counts when a released query
has no valid native result; a mechanical report cannot supply those facts.
They also reconstruct a current permit/request with a reused absence attempt ID
and reject it without invoking a worker. The bounded manifest model remains
under 24 KiB with a 32-KiB cap; no source/permit/export limit was increased.

Independent reconstruction/failure testing passes **27 tests in 275.79s**:
changed original sources, rehashed predecessor views, role swaps/aliasing,
forged authority and hash-only values, mismatched permits, reused IDs, delayed
reports, different serial/driver/physical node and original-campaign holds.
The owner-projection adapter tests use modeled projection bytes, not actual
v11/M1 authentication. No process, CIM, device or original-store access runs.

The fresh preparation suite separately passes **6 grouped tests in 74.72s**.
It tests post-report chronology, current launch, completed-log lineage, exact
document/operation joins, old baseline IDs, references, runtime inspection
shape and immutable/no-I/O reconstruction. Its logs and observations are modeled.
Black passes all seven changed/new Python files; mypy passes all three source
files. These are component results, not v12 or public reconnect acceptance.

Both inert launch checks pass on source
`354bd74643a7e13c4a3dc99202eef711b33e3b36ae954d164899679199e16c08`:
`READY_FOR_DIAGNOSTICS`, the confirmed workspace export parent, zero events,
zero operations, camera disconnected and physical authority false. No reconnect
action is registered yet. No browser/server, installation or physical operation
was started in this increment.

Reproduce the final combined run from the workspace root (no hardware required):

```powershell
$RocellReconnectTests = @(
    'software/tests/unit/test_physical_usb_reconnect_phase.py'
    'software/tests/unit/test_physical_camera_usb_reconnect_preparation.py'
    'software/tests/unit/test_usb_observation_refactor_compatibility.py'
    'software/tests/unit/test_physical_usb_identity_export.py'
    'software/tests/unit/test_usb_qualification_export.py'
    'software/tests/unit/test_usb_trial_baseline_export.py'
    'software/tests/unit/test_usb_absence_export.py'
)
.\.venv\Scripts\python.exe -m pytest @RocellReconnectTests -q --tb=short
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_usb_reconnect_phase_adversarial.py -q
```

No original v12 suffix, boot collector, service/UI action or successor export
was implemented in that preceding component slice. Its result is not the
acceptance result for the integration below.

## Original workflow integration — in progress, 2026-09-09

The original v12 reader, boot collector, dedicated reconnect storage scope and
v5 full-diagnostic exporter are now implemented. Service actions and both UI
projections are being joined; a passing complete public workflow is still
required before this increment is considered integrated.

The coordinator routes fresh metadata publications through a tagged USB-owner
interface. Each token names BASELINE or AFTER_RECONNECT; the selected owner
receives the completed result only after its completion log is persisted.
There is no fallback to the baseline owner on a failed reconnect publication.

The new Setup scope allows only a clean original v11 predecessor or an unused
same-launch v12 boundary. Its 180-second outer ceiling includes readback. It
does not enlarge the descriptor permit, native execution, READY, cleanup or
boot-observation budgets. Incomplete, attempted, held or earlier-launch records
remain inspection/export-only. Mixed storage-purpose flags are refused.

The intended operator sequence is:

1. Complete the original physical-node ABSENCE observation.
2. Reconnect manually, then explicitly **Begin** and record the operator report.
3. Run generic inventory/review and native inventory/identity/review through
   the existing metadata controls. Three successful logged acquisitions must
   belong to this phase and follow the report. These actions intentionally
   withdraw the previous Setup publication. Explicitly **Verify original camera
   setup records** (the existing `physical_camera_refresh` action) before
   Prepare. This verifies the same original and preserves the current launch's
   acquisition ledger; it does not reopen a phase or replay a device operation.
4. **Prepare** the exact operation and inspect the fixed runtime files.
5. **Review** that preparation, policy, runtime, target and boot scope. Distinct
   actor labels document procedure; they do not authenticate independent people.
6. **Collect host boot**. Different host/boot, missing facts or uncertain cleanup
   hold this attempt. This step never automatically queries USB.
7. Separately **Collect USB descriptors**, then inspect/export the exact result.
   Successful local retention is not final qualification or camera/arm release.

### New hardware-free verification

The root's combined export/storage/coordinator/runner selection passes **256
tests in 6.87s**, including historical v1–v4 exports and new v5 round trips.
These tests do not claim original-v12 or physical qualification. The complete
public acceptance test is `test_arrival_usb_reconnect_ntfs_acceptance.py`; it
must run in a new preserved directory, never over a prior M1 original.

`test_usb_reconnect_runner_model.py` executes the unchanged production USB
supervisor with an in-memory process/pipe peer. It tests the real five-second
READY window, twenty-second post-pin lifetime floor, late-result accounting
and cleanup without launching any child or opening USB. It does not maintain
a duplicate permissive timing implementation. File inspection remains real;
process/native receipts are explicitly modeled.

The full onboarding goal remains active. AFTER_REBOOT, final qualification,
physical camera capture/calibration and physical arm commissioning remain open.

Additional joined-component checks on the frozen Python integration:

- The boot collector passes **26 tests in 246.42s**, including the separate
  operation original, exact eight-role review, changed host/boot, interrupted
  work and no replay. Its transactions and host observations are modeled.
- The reader passes **15 tests in 508.34s**, including the full eleven-role,
  seven-event chain and partial-write checkpoints. Eleven additive epoch-limit
  checks and four full sibling-campaign audit checks also pass. These are
  modeled-original grammar tests, not physical or real-store public acceptance.
- The full modeled owner projection passes the strict terminal's current,
  historical and malformed-input checks (**1 grouped test in 47.42s**).
- Metadata routing passes **12 tests in 0.57s**. A separate cheap public test
  passes actual generic/native inventory, identity and review actions through
  the coordinator and durable logs, using in-memory metadata providers.
- The coordinator/setup regression selection passes **91 tests in 16.27s**;
  this overlaps the root selection above and is not an additive suite total.

Independent review found and fixed a diagnostic gap: `_commit` now immediately
caches the exact successfully committed event in the private attempt. A Stop,
source change or failed later readback cannot omit that known event from an
immediate recovery export. This diagnostic copy does not grant replay or
replace the original journal.

### First joined public run: held before preparation

Fresh public run 01 failed after **799.52s** at a missing test-sequence step,
not an admitted hardware effect. BASELINE and physical-node ABSENCE completed
their actual-storage action/export/reopen checks. Reconnect Begin and the
generic/native acquisition and review controls succeeded, retaining all three
durable metadata-completion entries. Those metadata actions correctly marked
Setup historical. The test omitted the explicit same-original Refresh, so
Prepare was correctly refused before dispatch.

The test now checks that Prepare is refused before Refresh, then performs
Refresh and checks that the current phase and all three ledger rows survive.
Cached navigation now recommends that existing Refresh action
only for an unused, same-launch Begin with complete fresh metadata. This is
guidance, not permission; action eligibility and original-store guards remain
authoritative. A restarted or attempted phase stays export-only.

Run 01's original is preserved under
`.codex-preserved/usb-reconnect-public-20260909-01`. Its full checkpoint,
verified v5 diagnostic export and separately verified **121-event** application
log are copied to
`software/runs/wizard-exports/hardware-free-usb-reconnect-20260909-held`.
No reconnect Prepare, boot observation or descriptor query was admitted.
All test hardware/process observations were modeled. Fresh run 02's result is
recorded below; the launch-bound run-01 original must not be resumed or
overwritten.

The corrected composed-service smoke passes **1 grouped test in 76.03s**:
actual Prepare and Review code over modeled storage, cached Refresh guidance,
disabled-action navigation, old-launch/incomplete-ledger/attempted-Prepare/
source-change refusals, pending publication before logging, eight reviewed
original references and independently retained operation bytes. Both renderers
are exercised. The completed/historical real-codec renderer/navigation test
passes **1 grouped test in 49.16s**; its device facts are also modeled.
The agent's overlapping legacy-UI/routing/results/invariants selection passes
**100 tests in 8.14s**. The root's latest five-file reconnect regression selection
passes **105 tests in 2.30s**. These are scoped results, not a repository-wide
test total or physical acceptance.

The next unimplemented boundary is captured in
[AFTER_REBOOT design notes](USB_AFTER_REBOOT_DESIGN_NOTES.md). That planning
document does not register actions or relax this phase's launch-bound rules.

### Second public run: inventory digest mismatch before admission

Fresh run 02 failed after **1,076.28s** at descriptor collection. Baseline and
absence again passed. Reconnect Begin, actual fresh metadata controls,
same-original Refresh, Prepare, Review and owned modeled boot collection all
passed. Refresh preserved the phase identity and all three acquisition rows.

The reconnect facts provider used `digest(usb_identity_protocol.canonical(...))`
for the full inventory check. Original storage uses
`physical_onboarding_durability.canonical_sha256(...)`, whose canonical bytes
include a trailing newline. The same inventory therefore hashed differently.
This is a deterministic integration defect, not an observed changed camera.
Repair only this digest call; keep the complete leased inventory comparison,
original-head check, role membership and all admission conditions.

QUERY_REQUESTED was committed before admission was refused with
`USB_RECONNECT_CURRENT_INVENTORY_CHANGED`. No admitted attempt or permit was
returned and no query worker ran. The immediate diagnostics retain the exact
request event and full admission failure; the last published Setup projection
remains BOOT_RETAINED. Do not resume the used request after changing source.

Original run 02 remains under
`.codex-preserved/usb-reconnect-public-20260909-02`. Byte-checked checkpoint and
receipt copies, a verified full v5 export (592,128 payload bytes), and a verified
**167-event** application log are in
`software/runs/wizard-exports/hardware-free-usb-reconnect-20260909-held-02`.
Full export reconstruction equals the cached diagnostics, including the latest
QUERY_REQUESTED state. Device/process observations remain explicitly modeled.
Fresh public run 03 is required; the focused repair regression now passes as
recorded below.

The post-failure root export/storage/routing/results/runner selection passes
**268 tests in 6.89s**. This includes the historical export formats and current
v5 round trips, but does not test the repaired facts provider; that needs the
new composed regression and fresh original acceptance described above.

The inventory fix changes one import and one hash call, with a comment naming
the original-store canonical format. The new
`test_usb_reconnect_inventory_boundary.py` passes **1 grouped test in 55.27s**.
It uses the actual current-v12 facts provider over a typed modeled snapshot,
rejects same-head added/altered/removed unselected references, executes actual
`_collect_usb` transfer over modeled persistence/dispatch, independently decodes
the permit bound to the returned facts, and verifies all eleven final references
with the full original reader. Earlier baseline/absence originals stay unchanged.
There is no production M1, process, CIM or device operation in this component
test. A further **36 tests in 0.85s** cover service/routing/result behavior.
Black and mypy pass the corrected source.

Independent post-admission review found no additional permit/reference join
mistake, but found a descriptor-runner fault-path capacity gap: an owner could
return 32 cleanup labels, after which four derived conditions could exceed the
unchanged evidence codec's 32-label maximum. The repaired producer admits at
most 28 owner labels and reserves four slots for its own derived conditions.
Oversized/malformed receipts become an explicit uncertain cleanup result; they
are not truncated into a clean receipt. Malformed exception codes use the
existing bounded label normalizer. Original native streams and any parsed
effect counts remain retained; missing native results remain unknown.

The focused cleanup file passes **13 tests in 2.59s**. The combined new cleanup,
existing descriptor/deadline and reconnect runner-model selection passes
**66 tests in 5.22s**, with the two actual incapable-child cases explicitly
deselected (`-k 'not actual_incapable'`). No process, native helper or USB device
ran in this selection. Historical 32-label evidence still decodes and 33-label
evidence still fails. Black passes three files and mypy passes two source files.

Frozen source for fresh public run 03:

| File | SHA-256 |
| --- | --- |
| `physical_usb_identity_service.py` | `e559efc3c56e4a3c8e2394fd0760aa8107ead9582fbea51532c123cc2a8892fe` |
| `owned_usb_identity_runner.py` | `8942684063f080c73dc8468ed09cb72e8c87a94a152b3dc82098c0d5de2421a7` |
| `owned_usb_identity_evidence.py` | `80295cb79392e7ef5f449ae93631a84955f3e4ee5b9acf7c7448a74c57244338` |

Fresh run 03 executed in a new preserved directory. It retained the
original descriptor deadlines, READY/lifetime checks, cleanup budget, role
caps, full inventory equality and no-replay rules. Neither failed original is
used as its starting store. Its held outcome is recorded below; a passing full
result is still required.

The current strict terminal validator also accepts both preserved failed-run
snapshots as historical/export-only. This check reads diagnostic JSON copies;
it does not reopen original stores, execute actions or restore authority.

### Third public run: original verification exhausted pre-start slack

Fresh run 03 failed its nominal acceptance assertion after **1,212.15s**.
Baseline and physical-node absence completed their real-storage public actions,
exports and reopen checks. Reconnect Begin, fresh logged metadata, explicit
same-original Refresh, Prepare, Review and boot collection succeeded. The
repaired full-inventory hash check passed and the exact request was admitted.

The descriptor runner retained `FULL_USB_LIFETIME_DOES_NOT_FIT` at its second
full-lifecycle check, after pinning and two successful scope checks but **before
process creation**. The 30-second permit had already spent 9.781s before the
runner started. PRE_PIN and POST_PIN rechecks took 1.953s and 1.985s; only
16.109s remained after 4.110s of runner work, below the unchanged 20-second
required lifecycle. This is a software performance failure, not evidence of a
changed or malfunctioning camera. No native worker or actual device ran.

The original campaign is `SEALED_UNCERTAIN`, quarantine is latched, and the
reconnect projection is `ORIGINAL_CAMPAIGN_HELD`. Zero recorded opens/writes
must not be reinterpreted as permission to retry a consumed request. The strict
terminal validates the saved incomplete-held projection and recommends export.
All earlier originals remain unchanged under
`.codex-preserved/usb-reconnect-public-20260909-03`.

The assigned-folder archive is
`software/runs/wizard-exports/hardware-free-usb-reconnect-20260909-held-03`.
Its 186 copied files were verified byte-for-byte, including the **171-event**
application log and preceding baseline/absence exports. A separate full v5
export verifies 624,984 payload bytes and restores exactly to the saved USB
diagnostics. It retains the original held campaign, not a retryable session.
The export manifest's semantic SHA-256 is
`1903c7897e40e6318ccbfef4eed20f952efb72f827630e0e2edd82e04f522b1f`.

A checkpoint-only timing review measured repeated immutable preparation
parsing at roughly 5.5ms per scope projection/binding check, not seconds.
Changing that parser would not recover the missing lifecycle allowance; keep
the runner unchanged and investigate duplicate original-store reads instead.

The next repair must target proven duplicate verification work while preserving
fresh original/head/inventory/sibling checks at every required boundary. Do not
extend or renew the permit, shrink lifecycle reserves, or substitute a faster
test-only implementation. A new preserved nominal public run remains necessary.

The bounded repair under test has two parts. A private M1 verification helper
returns its already-fresh selected snapshot together with the verification
report; only the USB-identity admission path opts into that pair. It checks
their exact types, source/header/head/qualification/reconciliation fields and
LF-canonical full inventory agreement. The global/sibling audit and independent
selected-session pass remain separate. Each admission/revalidation calls this
helper afresh; no snapshot is cached between boundaries. Historical domains
retain their separate snapshot/verification calls.

The USB transaction's initial header check also uses the existing single-read
`_open_session_with_snapshot` helper instead of opening and reading the same
session repeatedly. Lease challenges, post-acquisition initialization, all
family audits, before-intent verification, consumed-scope checks and runner
deadlines are unchanged. Root and independent source reviews found no omitted
check in this narrow change. The focused paired-observation suite passes
**22 tests in 29.46s** over new isolated NTFS originals and modeled zero-I/O
subjects. Its count checks verify initial header loads **3 to 1**, and a fresh
admission with a globally referenced selected session **3 to 2**, preserving
both global-head observations and the independent global/selected passes.
These are read-count reductions, not claimed measured end-to-end speedups.

Root regressions also pass **18 tests in 29.77s** for existing fresh-read and
physical-presence behavior, and **27 tests in 49.94s** for the older USB domain,
including genuine storage coexistence, sibling tamper and quarantine readback.
All use fresh isolated originals; no device or native child runs. The unchanged
runner's modeled timing tests pass **4 tests in 1.02s**, including a slow
post-pin refusal with no process creation. These are separate scoped results,
not a repository-wide test total. A fresh complete public result is still
required; passing components do not establish sufficient real timing slack.

The changed-inventory negative now requires the exact stale-challenge error,
so an unrelated permit expiry cannot satisfy it. That strengthened case passes
**1 test in 10.67s** in another fresh original directory. Final test SHA-256:
`b5483edc74078998dfcf926b6c6a4dc3c49c715cb9323d9e5bb23994a15288b3`.
Black passes all four changed files; mypy passes the three source files.

Frozen additional source for fresh public run 04:

| File | SHA-256 |
| --- | --- |
| `physical_onboarding_m1.py` | `fbc96d7834e8e1d219a44cbfc804cd55e95a14354dc1ba396bdac0462c84f7a1` |
| `commissioning_m1_persistence.py` | `f9fac04d0c8bb9687917bf7bc85d8f2c641a0fb6ce320c13fd8734014130407b` |
| `commissioning_usb_identity_persistence.py` | `3ac088e1c7b88f41a3878ed561975933d322278cdf9601baefc11b53b9f5b8b7` |

The earlier service/runner/evidence hashes remain unchanged. Fresh public
run 04 started at approximately 16:24 UTC on 2026-09-09 in
`.codex-preserved/usb-reconnect-public-20260909-04`. Its held result is below.
All original deadlines, role caps and real M1/production-supervisor checks
remain in force; hardware and process observations remain explicitly modeled.

### Fourth public run: improved timing, still below the required lifecycle

Fresh run 04 failed nominal acceptance after **1,155.34s**. Its baseline and
physical-node absence passed all public actions, complete export/restore and
fresh reopening. Reconnect Begin/metadata/Refresh/Prepare/Review/boot collection
also passed. Collection retained a held original before process creation with
`FULL_USB_LIFETIME_DOES_NOT_FIT`; the 20-second post-pin floor stayed unchanged.

Permit issuance to runner entry fell from 9.781s to **7.969s**. PRE_PIN and
POST_PIN rechecks took **1.531s / 1.532s**. The 3.250s runner interval left
**18.781s**, still 1.219s short of the required floor. This comparison records
two actual runs, not a controlled benchmark or a guarantee on another host.
No process was created and the modeled peer recorded no release. The durable
campaign remains `SEALED_UNCERTAIN`; its consumed request is not retryable.

Verified failure copies are in
`software/runs/wizard-exports/hardware-free-usb-reconnect-20260909-held-04`:
186 byte-matched copied files, a 171-event application log, and a full v5
624,984-byte diagnostic export that restores exactly to the checkpoint.
The new full manifest-file SHA-256 is
`49f886df3b5b5412639d004d71897d7e51d20a149e84a8923f288e19cea55c05`.
Originals and all previous archives remain unchanged.

A read-only profile of the closed run's V2 file decoder found 51 references
and 145 bounded file reads in 0.339s under instrumentation. Repeated metadata
calls dominated: 6,798 `stat` calls and 3,227 `lstat` calls. This invoked only
the file decoder, not an M1 runtime/lease, wizard action, admission, native
worker or device. It neither replayed the campaign nor mutated its originals.

Two further narrow reductions are being tested: reuse the existing single-load
helper for the USB transaction's post-lease open while retaining both fresh
constructor checks, and inspect each ancestor once per link-chain check using
one `lstat` result for both symlink mode and Windows reparse attributes. No
ancestor is skipped or cached across calls. Required audits, current reads,
regular-file/by-handle/hardlink protections and all time budgets remain intact.

### Additional read reductions verified before run 05

The post-lease USB open now uses the existing single-load helper. It does not
pass a cached snapshot to the transaction: both constructors still perform
their independent fresh reads. Five focused tests passed in 29.82s, including
header/head corruption after lease acquisition and before construction; all
four failures close the held leases without publishing a transaction.

The V2 ancestor check now derives symlink mode and reparse attributes from one
fresh `lstat` per component, through the root. Missing components do not skip
parents, other inspection errors fail closed, and the separate bounded-file,
by-handle and hardlink checks are unchanged. Twenty-nine new tests passed in
0.65s, including real isolated symlinks and a Windows junction; eight existing
V2 tests passed in 0.92s. Independent review found no concrete defect in either
change. Black passes all four changed source/test files; mypy passes both
source files.

The same closed-run read-only V2 decoding profile measured 0.245s versus 0.339s
before the ancestor change, with the same 51 references and 145 bounded file
reads. `stat` calls fell from 6,798 to 3,716 and `lstat` calls from 3,227 to 145.
This single instrumented comparison is not an end-to-end timing guarantee.
It did not open an M1 runtime, acquire leases, replay actions or mutate originals.
Root also independently reran the run-04 archive verifier: all 186 copies,
171 log events and exact full-export restoration passed, with no writes.

Frozen changed files for the next acceptance:

| File | SHA-256 |
| --- | --- |
| `physical_onboarding_m1.py` | `ff0b36ba8a8de1c0dc7cbe2c83742b30a74640314c5e6986153ade5ca45c736e` |
| `physical_onboarding_v2.py` | `d89152a9f9468a1d12566f8f72a7f0ef7fbadff70456f8d5c91c2f0c3a92fa0f` |
| `test_usb_identity_postlease_open.py` | `cb612868f50081ff25019e96d1e49c99db94e82b1b3a5673e1d0d8205736cd44` |
| `test_v2_link_chain_observation.py` | `a2b411f0b693e04d650df28f864569dc2b42c5dbca10c308abb4f34a5bc50219` |

All earlier run-04 frozen service/persistence/runner/evidence files remain
unchanged. A fresh combined regression run and public acceptance are required
before this increment can be considered complete. The broader connection,
physical camera, arm and handoff gaps remain tracked in the completion matrix.

The combined regression run passed **132 tests in 139.78s** in fresh
`.codex-preserved/usb-v2-combined-20260909-01`, covering V1/V2 storage,
durability, both new read reductions, paired observations, M1 fresh reads,
physical-presence fresh admission and the older USB domain. Rehearsal and
physical launcher `-Check` both report `READY_FOR_DIAGNOSTICS`, the assigned
export folder, camera/arm `NOT_CONNECTED`, zero events/operations and no
physical authority. Their current source binding is
`cf99218f9a0b15dbbd82e996d8ac73837709576a72bf6090c3d80ad7ff71532e`.

Fresh public run 05 is started next in
`.codex-preserved/usb-reconnect-public-20260909-05`, with source/tests frozen
for its duration and every original production timing limit unchanged.

### Fifth public run: timing passed, mismatched nominal fixture correctly held

Run 05 failed the final nominal-phase assertion after **978.10s**. All five
public reconnect actions completed, and all eleven roles/seven events were
retained. The actual supervisor over an in-memory peer passed every scope and
timing check, returned `OBSERVED`, and sealed the campaign `SEALED_KNOWN` with
confirmed cleanup and no quarantine. No actual process or device was executed.

Permit issuance to runner entry took **6.687s**; PRE_PIN/POST_PIN checks took
**1.344s / 1.297s**. At the second unchanged 20-second lifecycle floor, **20.469s**
remained. The full five-boundary runner interval was **6.813s**. This establishes
one successful timing result on this host, not comfortable slack under every
load or a guarantee for a larger successor. Collection took **138.594s**.

The final pure phase was `HELD` solely for `RECEIVED_SERIAL_MATCH`. All other
sixteen checks passed. The original receipt/plan reported
`MODELED-NOT-HARDWARE-001`, whereas both retained generic and descriptor serials
were `MODELED-ONLY`. Baseline-to-reconnect continuity correctly matched those
USB observations, but did not make them match the separate received label.
The nominal public test had inherited inconsistent fixture inputs. Production
serial checks and historical data must remain unchanged.

The repair chooses `MODELED-ONLY` in this public test's receipt-input factory
before any new original submission, assessment, review or plan is constructed.
It is scoped to this nominal test module; other fixture defaults remain intact.
New checks compare receipt/generic/descriptor input serials cheaply and verify
the newly retained original prefix before the full sequence. The full test also
asserts the received serial before starting baseline/absence. This neither
rewrites the failed original nor changes an expected failure into an approval.

Assigned-folder archive:
`software/runs/wizard-exports/hardware-free-usb-reconnect-20260909-held-05`.
It preserves 186 byte-matched files (5,512,971 bytes), the 171-event application
log, earlier baseline/absence exports, and a separate full v5 export of 683,448
payload bytes which restores exactly to the saved diagnostics. Checkpoint SHA:
`9ac24da3880a96a2c5ac0e64f6e5528d941c3399ec6af63d0c21bd19adcf51cc`.
Full manifest-file SHA:
`3621e5728986a6aba66e4f1b0fa1144833e5a3a9d0c0b60cd1129ee3d20165e6`.
Clean campaign accounting is not a retry permission; this used phase remains
historical/export-only. The failed assertion prevented its final public export
and reopen checks, so those still require a fresh complete nominal acceptance.

The input-consistency and genuine-original-prefix checks passed **2 tests in
61.29s** in `.codex-preserved/usb-reconnect-serial-inputs-20260909-01`.
Independent read-only review confirmed that the test-scoped factory runs before
original creation, changes only the modeled inspection serial, and is restored
after each test. Shared defaults, original payloads and production code are
unchanged. Root independently reran the run-05 archive verifier read-only; its
copies, log and full restoration passed. The corrected public test file SHA is
`05f5f4f9d875e897cf78839d3a098e776902d0befa6bf02d9f2c1844dd207bde`.
Existing reconnect-codec, supervisor and public metadata regressions are being
run before the next fresh complete acceptance.

Those regressions passed **23 tests in 177.43s** in fresh
`.codex-preserved/usb-reconnect-serial-regressions-20260909-01`, including the
existing serial-mismatch HELD case and slow post-pin refusal. Black passes the
changed test file. Both optimized production source hashes remain unchanged.
Fresh public run 06 starts at approximately 17:27 UTC on 2026-09-09 in
`.codex-preserved/usb-reconnect-public-20260909-06`; only the nominal input
choice/early assertions differ from run 05. Source and tests remain frozen for
its duration, and no previous original request is reused.

### Sixth public run: full hardware-free reconnect acceptance passed

Fresh run 06 passed **1 test in 1,062.33s (17m42s)**. It rebuilt the entire
prefix with consistent nominal input before retention, then exercised actual
public metadata tickets/completion logs, explicit same-original Refresh,
Prepare, exact Review, separate boot collection and descriptor collection.
All eleven original roles/seven events survived; all seventeen phase checks
passed with `RECONNECT_OBSERVATIONS_RETAINED`. The original campaign is
`SEALED_KNOWN`, cleanup confirmed, quarantine false. Earlier phase subjects
remained unchanged. Fresh original reopening matched the retained workflow
exactly and could not replay any consumed action. Later stages remain PENDING.

Permit issuance to runner entry was **6.500s**; PRE_PIN/POST_PIN took
**1.328s / 1.297s**, leaving **20.703s** at the unchanged 20-second floor.
The complete runner interval was **6.719s**. Reconnect action durations were
46.656s Begin, 53.422s Prepare, 56.515s Review, 59.218s boot collection and
135.781s descriptor collection. This is measured host-specific timing with a
limited margin, not a guarantee under arbitrary load or for the larger reboot
successor. Do not change time budgets to accommodate later regressions.

The final public v5 export manifest-file SHA-256 is
`476f4b1c1eda3ac5a1285d7b31f4d6f0427e3b49dc16bc3671d46dcd5db8f756`.
Phase SHA:
`e6ba6fa4cd4b09baa88a12573c425330a0edd55ca9aa80012b2fea602dc835f6`.
Permit SHA:
`348411227bb44d9ef4d788dade03ca87130207c791a2064cc1b9cbc0df31fd9b`.
Execution evidence SHA:
`88dd044dac22949a55a304455653c8d6f59e9c549a9372e2140d3f81403c4a87`.
The accepted original head is
`c3cf42a42174c602b3427e37b0c637d8887697b36111a7a06894003de8305949`.

After process exit, launcher `-Check -Mode physical` still reported source
`cf99218f9a0b15dbbd82e996d8ac73837709576a72bf6090c3d80ad7ff71532e`,
`READY_FOR_DIAGNOSTICS`, assigned exports, disconnected camera/arm and no
operations/physical authority. The separately reviewed reboot draft was only
installed after that frozen-build check; its tests and later integration are
tracked in the [reboot work order](USB_AFTER_REBOOT_IMPLEMENTATION.md).

Passing evidence is archived and verified under
`software/runs/wizard-exports/hardware-free-usb-reconnect-20260909-pass-06`.
All 194 copied files (6,200,520 bytes) match their sources. All three public
exports verify; the final v5 export restores the entire checkpoint diagnostics
exactly. The complete log contains 173 verified events. Acceptance-file SHA:
`d7953031e611825cf94417f5609592a061b9e5444f5e61a6d751f723e9cf3787`.
Checkpoint SHA:
`c4324186fe270b9c9c5f54ff09d8fddf4b138588591a05e9039f236d1c629610`.
No new export was needed; the actual final public bundle was preserved.
No actual USB query, camera/COM access, native worker or physical qualification
occurred. Reconnect retention does not complete the four-phase qualification,
accept stage 4, enter capture, energize the arm or authorize motion/contact.
