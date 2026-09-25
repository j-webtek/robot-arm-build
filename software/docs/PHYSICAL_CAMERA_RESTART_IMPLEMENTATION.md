# Camera setup restart continuity

Date: 2026-09-08. Status: implemented and two-launch public-service tested.
This completes the restart-continuity slice, not live device qualification.

The preceding camera-session workflow verifies only its current launch's
assigned store. The actual onboarding application must also explicitly reopen
an existing original store after application shutdown. This work connects that
missing workflow without creating replacement sessions or replaying devices.

## Plan recorded before implementation

1. Discover bounded original camera-store metadata beneath the single assigned
   `software/runs/physical-camera-acquisition` directory. No arbitrary browser
   path, recursive workspace search, storage qualification, device inventory,
   native helper or automatic selection. Retain exact metadata identities and
   visible issues; source-drift stores are listed but cannot be resumed.
2. Issue opaque current-discovery choices. Bind the explicit reopen ticket to
   its immutable selected descriptor/header/directory identity and discovery
   hash. Recheck the same metadata under directory guards before opening it.
   A timeout, changed selection or failure must not select another store.
3. Reuse the actual camera-only session refresh and original M1 auditing. Keep
   original cell/session/source/origin-launch identity, attempts, quarantine and
   stage journal. Reopening never initializes missing suffixes, changes stage
   evidence, repairs storage, grants camera facts or replays a campaign.
4. Read back the original requirements document under existing stage-only
   leases. Verify its payload/reference/source/session/origin binding, preserve
   full diagnostics and distinguish original historical metadata from new
   current-launch observations. Missing/ambiguous prerequisites remain visible
   holds, not instructions to regenerate them automatically.
5. Adopt the verified original store in the setup application and physical
   camera planning component together. A prepared native intent must not point
   at a fresh launch store while the UI displays an older original session.
   Connection/runtime review and received-unit qualification remain separate.
6. Add explicit Discover/Open actions and strict browser/terminal projections
   showing origin launch versus current launch, selected source match, original
   stage state and historical requirement provenance. Do not promote an old
   metadata selection, camera configuration, frame or physical stage PASS.
7. Test actual public first-launch initialize/collect/shutdown then second-launch
   discover/select/reopen/verify/export, using one original NTFS store and no
   device calls. Cover stale metadata, another source, partial/corrupt storage,
   cancellation, redaction, log failure and changed original requirements.

## Ownership and constraints

- Root: setup/acquisition/Arrival/action integration, source-bound public smoke,
  independent review and developer-facing usage/verification record.
- Discovery agent: bounded pure/cached registry plus explicit metadata discovery
  and selected-store revalidation; no runtime/session initialization.
- Session agent: narrow original-prerequisite readback in the camera lifecycle,
  using existing qualified storage and evidence checks; no camera provider.
- UI agent: current/origin/discovery presentation and strict producer tests.

Keep existing rehearsal reopening separate. Do not relabel a rehearsal store
or source-only physical-preflight store as camera acquisition. Preserve old
stores, exports, native catalog/build files and controlled hardware definitions.
The overall developer playbook remains the goal; restart continuity is one
required connection toward it, not a replacement for physical onboarding.

## Operator workflow

Launch `./start-rocell-wizard.ps1 -Mode physical`. To continue an existing
camera setup, do **not** initialize a new camera store:

1. Choose **Discover saved camera setup records** and confirm its metadata-only
   preview. The wizard scans only its assigned camera-store folder. Missing,
   partial, unsafe and source-mismatched entries are shown as issues/holds.
2. Explicitly select a source-matching original record and choose **Open selected
   original camera setup**. Confirm the original cell/session/origin and current
   app launch shown in its preview. No first/default record is auto-selected.
3. Inspect the recorded stage states and original requirements. Reopened
   requirements are labeled `REOPENED_ORIGINAL_CONTEXT`: they do not restore a
   currently connected camera, old control settings, frame, review or permit.
4. **Verify original camera setup records** rechecks exactly that original
   identity. After a failed opening, it uses the immutable original descriptor
   and an independent hash to revalidate the same metadata. It does not revive
   a revoked selection token, choose another store or replay a device action.
5. If the original source stage was still PENDING and no checklist existed,
   explicitly collect the fixed-build requirements. This is not automatic on
   opening. Its document remains bound to the original store's origin; current
   launch metadata/source-preflight observations are not relabeled as old ones.
   A previously collected WAITING_OPERATOR document is not recollected.
6. Export diagnostics to `software/runs/wizard-exports`. Keep the entire new
   export and its manifest; earlier reports and original M1 records remain.

One app launch owns at most one original camera store. After selecting it,
initializing a replacement or switching stores is blocked. The session and
camera-plan target are rebound together after successful original-store
verification; planning cannot silently target the new launch's unused path.

Saved stores remain bound to their exact software source. A store from another
version is visible but not resumable under the current source. This change does
not implement source migration or conversion. Preserve its original exports;
do not edit bindings or clear holds to make it appear current.

## Code/API map

- `physical_camera_reopen_registry.py`: bounded metadata discovery, immutable
  `PhysicalCameraStoreDescriptor`, opaque published choices, selected-scope
  before/after checks, and explicit `revalidate_original` after failure. See
  [registry API](PHYSICAL_CAMERA_REOPEN_REGISTRY.md). It never opens M1/devices.
- `physical_camera_session.py`: `read_original_prerequisites` reads the exact
  original labeled document under actual stage-only leases, checks the selected
  header and post-lease head/inventory, and retains complete historical bytes
  after late failures. No stage transitions or campaigns are performed.
- `physical_camera_setup_service.py`: owns one selected original, discovery
  publication, restart/refresh, origin/current distinction and failure history.
  The v2 cached view adds origin, requirement provenance and discovery metadata.
- `physical_camera_acquisition_service.py`: `bind_verified_session` updates
  camera planning to the actual original directory/cell/session. Each plan
  snapshots those identities atomically and retains the current metadata-launch
  binding separately from `camera_store_origin_launch_id`.
- Arrival/actions: closed discover/reopen controls, exact server ticket context,
  one-use initial selection, explicit same-original refresh, final-log gating
  and full-result export. No arbitrary browser path or descriptor is accepted.
- Browser/terminal: strict v2 producer validation, original-context captions,
  pending/held suppression and backward-compatible read-only v1 export views.
- `scripts/wizard_physical_camera_restart_smoke.py`: real two-launch public
  service integration; `--pending-original` also checks explicit continuation
  of a never-collected original store. No injected hardware/provider facts.

## Verification evidence

Normal/pending restart integration baseline source:
`ca9cdb8836d06f4b9154d5615603278850bff3b713c5d5e1d038dc89c00ff10c`.

Final production source:
`e28e04eee58b93d851e3d5548d9df0ce1f8f6e78f3c1893b26b7571f2535d710`.
The final change corrects the recovery action's preview folder to its immutable
original target even before camera-plan adoption. It does not change reopening,
storage, hardware gates or metadata restoration. It was independently exercised
by the final-source Stop/recovery public run and focused tests below.

Both public scenarios completed eight explicit actions across two app launches
using actual qualified NTFS/M1 storage. Each verified its chosen-folder export,
preserved the original origin/cell/session, and confirmed the unused second
launch directory was never created. Eleven semantic stage/evidence/cell/anchor
files were compared for unchanged bytes across reopen/refresh. Storage
qualification and lease metadata were intentionally not treated as immutable.

### Existing checklist

- Origin: `wizard-66879952056f4816920b25ad60514574`.
- Current launch: `wizard-a892203f11164f118036eb96475b6677`.
- Original session: `physical-camera-f9b1e898b51430d353d89f9e29c369a5`.
- Requirements SHA:
  `28303b277fc894fa167b85061b93db55bcfb8e82c7ea33c22630bd51515c6348`.
- Verified restarted export:
  `software/runs/wizard-exports/wizard-20260908T113927491670Z-298e4011553c48d5b3198f578001111a`
  (8 files, 350,971 bytes).
- Manifest binding:
  `3fc5654d45041ebed016c14cdb4497244474c89be77c2b8cbc0436e54bfda653`.

The original full document was compared with reopened, refreshed and exported
documents. Both strict interfaces also rendered this actual 117,573-byte
snapshot; current/origin identities differ correctly, first stage remains
WAITING_OPERATOR and fourteen remain PENDING. Pending/held variants suppress
current details and perform no automatic action/full-result fetch.

### Originally pending checklist

- Origin: `wizard-0ee0bae511a2415581bb19661ea5a9e8`.
- Current launch: `wizard-4eba16121b8b49e08abb26c3ed2cd049`.
- Original session: `physical-camera-93f19d0fa5bf61bfe8c5e8fb9de475d3`.
- Explicitly collected requirements SHA:
  `ffc6812eddc5537dbcd80849094502a051968c5f496171b08b3007fb7035cccd`.
- Verified restarted export:
  `software/runs/wizard-exports/wizard-20260908T114022632584Z-64d6d7efc9e64622a1b7a7e43e09564c`
  (9 files, 379,006 bytes).
- Manifest binding:
  `95d52ff6bf963210cc21ad033aa697ba9d1708ba8b0226a2861728059bd2aea5`.

Neither scenario connected hardware, observed power, captured a physical frame
or passed a physical stage. All fifteen overall physical progress entries
remain pending; camera acquisition and arm/typing execution remain held.

### Actual Stop and explicit same-original recovery (final source)

The third scenario uses `--stop-after-original-read`. Its test harness inserts
one scheduling barrier **after the actual original M1 readback**, then issues
the real public Stop action. It replaces no storage result, provider, header,
permit or evidence. The selected scope correctly fails with a cancellation
diagnostic, revokes its token, retains original bytes, and withholds current
readiness. A separately requested Refresh then revalidates only the frozen
original descriptor. A later ordinary Refresh, held plan and export succeed.

- Origin: `wizard-334eb8c41e54434cb9922b991bf93700`.
- Current launch: `wizard-f43fe4a3f58049cbb4ef7b4a3e5880fa`.
- Original session: `physical-camera-58d55763582de4c3965700f6534d4cea`.
- Requirements SHA:
  `85be170b45217bb11fb83c832db4ce2659106163187c53e382555bbea754e532`.
- Verified failure-plus-recovery export:
  `software/runs/wizard-exports/wizard-20260908T115141880508Z-82ec9cba2af84626b4cde35013a10c0c`
  (10 files, 453,217 bytes).
- Manifest binding:
  `a75078443cdb5386b3df82679f653be0e2d71bd3d6a839305374e70e474f7ffb`.

This scenario completed ten explicit actions across two launches. Eleven
semantic files remained byte-identical across Stop, reopen and verification;
no replacement directory or device connection was created. The recovery
preview was asserted to name the original directory, not the unused new one.

### Tests and review

Component invocations: 65 registry/revalidation tests; 41 original readback tests
plus 29 existing session tests; 103 setup/acquisition/action tests; 219 focused
UI regressions; 44 expanded restart UI tests; 14 new restart service/failure
tests. These counts overlap and are not a single summed suite. Some fault
tests deliberately model metadata/storage; the actual-M1 public checks above
provide the separate original-store integration evidence. Six production
modules pass mypy. The broad selected non-slow run completed with **3,310 passed,
3,355 deselected in 545.22 seconds** on the integration baseline source above.
It covered Arrival/wizard, native/Windows camera, capture ingestion, controller/
arm feedback, owned processes, coordinator scopes and camera persistence. It
was not the entire repository suite and was not rerun after the final preview
folder correction. On final source, the combined registry/restart/UI/setup/
acquisition/action subset passed **226 tests in 16.02 seconds**, including
before-scope, after-scope and late-readback recovery-preview assertions.

Final package: `software/runs/wizard-package-check-e28e04ee/rocell-0.1.0-py3-none-any.whl`,
1,816,042 bytes; SHA-256
`70f799454892f77145a632bb7151da91c42c2cb7ef26d93688accde415401268`.
All **251** packaged Python/HTML/CSS/JavaScript entries match final workspace
bytes. Final-source mypy checks pass, and the physical launcher's read-only
`-Check` reports both devices NOT_CONNECTED, discovery NOT_DISCOVERED, all
fifteen physical progress entries pending, and the selected workspace export
folder. It starts no server and opens no hardware.

Independent review identified and fixed the revoked-token Refresh defect before
the successful public checks. Failed opening now preserves the original typed
descriptor for a separately requested same-original verification. Revoked
tokens remain invalid. There is no automatic retry or alternative-store fallback.

## Remaining full-playbook work

The [passive intake notebook increment](PHYSICAL_INTAKE_NOTEBOOK_IMPLEMENTATION.md)
adds draft forms and complete diagnostic export, not canonical receipt acceptance.
Verified attachment ingestion, draft restoration and independent evidence review;
actual
configuration epochs and stage acceptance; native runtime/device qualification;
physical camera controls and verified bounded frame publication; supervised
arm startup and feedback connection; installed calibration, non-contact
acceptance, and independently gated individual key/Android-tap execution.
Restart continuity does not close these physical connection requirements.
