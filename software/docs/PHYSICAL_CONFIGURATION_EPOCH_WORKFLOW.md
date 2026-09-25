# Progressive configuration records for camera onboarding

Date: 2026-09-08. Implementation plan and verification record for the next
camera/arm playbook increment. The full onboarding objective remains unchanged.

## Why this is required for a real connection

The camera persistence contract requires exactly eight server-owned
configuration documents. The checked-in policy names bindings that become
available at different stages. For example, `camera_support_optics` includes
`camera_mode_controls`, which the first probe is meant to observe. Board
registration and phone target geometry are later products too.

Requiring every binding to be qualified before the first probe would create a
dependency cycle. This is a design gap in the unfinished physical facts
assembler, not a reproduced failure of an already operating camera dispatcher.
The present camera session refuses all acquisition facts; it must continue to
do so until the complete admission and release paths exist.

The remedy is a progressive record of exact current knowledge, separate from
acceptance. Missing values must remain explicit. A future or same-stage result
must not masquerade as an earlier observation or a prerequisite already passed.
An actual retained file/reference must not be mistaken for independent review,
hardware qualification, actuator isolation or permission to open a camera.

## Implementation sequence and ownership

1. **Dependency model and strict artifact — diagnostic agent.** Reuse the exact
   eight domains and binding names from the original retained epoch policy.
   Define closed producer-stage ownership for each binding and compare it with
   the requested stage boundary. Validate supplied original evidence references
   against the exact V2 session inventory. Reject unknown/duplicate bindings,
   cross-session/source references and unsupported authority claims. Record
   missing predecessors separately from outputs not yet due. Constructors and
   verification remain pure.
2. **Original durable records — camera agent.** Extend the existing camera M1
   source workflow with a precise optional epoch-evidence role. Store and read
   back exact bytes under the existing stage leases; preserve the original
   source receipt/assessment/review semantics. Existing v1 histories without
   epoch records remain readable and explicitly missing, not silently upgraded.
   Any supported revision must retain predecessor linkage and original evidence;
   no record may be overwritten, no stage accepted and no attempt replayed.
3. **Actual setup-service join — root.** Collect the first vector from the
   original verified prerequisites/session, retain it in that original store,
   restore it after an explicit original-store reopen, and project its exact
   status through the current setup view. A status read must not inspect files,
   rewrite evidence, enumerate devices or create configuration records.
4. **Browser and terminal — UI agent.** Display the eight domains and concise
   counts/reasons from the service. Clearly separate retained observations,
   missing required predecessors and same/later-stage outputs. Do not label
   record completeness as connected, calibrated, qualified or safe to move.
5. **Export and verification — root with agents.** Retain the complete bounded
   vector in assigned-folder diagnostics. Test exact original-store readback,
   stale/cross-source input, dependency boundaries, publication/log failure and
   old-store compatibility. Run a public hardware-free setup/restart/export
   workflow on a fixed final source, then a proportionate scoped regression.

## Contract decisions

The pure API is `build_physical_configuration_epochs(prerequisites, snapshot,
evidence_bindings=(), boundary_stage=None, boundary="BEFORE_STAGE")`. It uses
the original retained `PhysicalCameraPrerequisites` and exact V2 snapshot.
The default boundary is the snapshot's active stage; an explicit boundary
cannot jump to a different stage. `AFTER_STAGE` can describe missing outputs,
but does not complete that stage.

`EpochBindingName` is the closed set of the policy's 32 binding names.
`EpochEvidenceBinding` accepts one to four exact original `EvidenceReference`s
at the binding's producer stage, not a browser-authored proof hash. Reference
presence is labeled `RETAINED_REFERENCE_UNASSESSED`. Absent values are
`MISSING_PREDECESSOR`, `PENDING_CURRENT_OUTPUT` or `PENDING_FUTURE_OUTPUT`;
after a stage, absent same-stage products become `MISSING_CURRENT_OUTPUT`.

The artifact binds the original source, session/header, prerequisites, policy,
stage catalog, original committed prefix and reference inventory. Contextual
verification authenticates that prefix and inventory against the current
audited original store; a later review does not invalidate an earlier record
merely by extending the journal. It does not infer filesystem observation
chronology, semantic evidence qualification or permission from those hashes.

Producer ownership used by this data-dependency classifier:

| Domain | Binding producers |
| --- | --- |
| software_build | All four bindings: workspace_sources |
| camera_support_optics | camera_receipt: camera_receipt; camera_identity: camera_identity; camera_mode_controls: camera_mode_controls; support_witnesses: static_registration |
| board_tags_bench | board_measurement and bench_identity: camera_receipt; tag_map and board_reseat_test: static_registration |
| arm_controller_tool | arm_identity: arm_identity; controller_identity and firmware_identity: feedback_only_connection; tool_identity: reference_frame_calibration |
| power_system | All four bindings: power_safety |
| keyboard_station | All three bindings: reference_frame_calibration |
| phone_station | All five bindings: reference_frame_calibration |
| empty_cell_safety | installed_object_inventory and empty_cell_witness: power_safety; startup_sweep: power_on_observation; collision_geometry: noncontact_acceptance |

These aliases mean completed binding products: support witnesses correspond to
installed optical stability; tool identity includes free-state tool/TCP; the
controller/firmware binding corresponds to qualified controller identity and
INT-011 owned by stage twelve. Earlier inventory candidates or expected firmware
are not silently substituted. **Producer ownership is not a waiver of earlier
mechanical, isolation, firmware, containment or hazard prerequisites.** Those
remain separate mandatory checks for each effectful action.

The first implemented durable path writes one initial immutable vector during
the existing prerequisite collection, after the prerequisite bytes have been
stored and read back, with `evidence_bindings=()`. It uses label
`physical-configuration-epochs-v1` and no extra stage transition. The original
source reader returns its existing v1 shape when the record is absent, and
readback.v2 with `configuration_epochs` when it is present. There is no
automatic legacy upgrade, refresh-time record creation or same-stage retry.
Append-only successor vectors and their invalidation joins remain subsequent
work; this increment must not claim those transitions already exist.

## Constraints that do not change

- Preserve the controlled epoch policy, stage catalog, active hardware freeze,
  purchased static camera architecture and physical activation holds.
- Preserve exactly eight domains. Do not invent a ninth domain or use a freeze
  number as the identity of a configuration.
- The source-v1 assessment remains BLOCKED for its existing unfulfilled physical
  requirements. Missing records are not replaced with nominal board dimensions,
  synthetic camera results, notes, checkboxes or self-supplied proof hashes.
- Do not invoke the current native camera campaign merely to demonstrate its
  known pre-owner release hold: that campaign deliberately seals uncertainty and
  can quarantine the original cell. Known prerequisite gaps must be refused
  before any eventual effectful prepare/execute path consumes an attempt.
- No physical device inventory, native camera process, serial open, power event,
  motion or contact test is performed during this increment.
- Do not rebuild or repin existing native camera artifacts to conceal the
  retained source/build mismatch.

## What this closes, and what it does not

This supplies a missing progressive, original-store configuration dependency
record for the real onboarding service. It is not the complete facts assembler,
hazard acceptance contract, physical camera dispatcher or a release certificate.

Still required afterwards: authentic received-unit evidence intake/review;
stage-owned physical acceptance and hazard/isolation observations; exact
service-owned acquisition scope; release-qualified runtime and private output
directory ownership; native dispatch/readback/publication; installed calibration;
remaining noncontact/handoff integration; separate later motion/contact release.

## Verification

The implementation now retains the first vector during the existing **Collect
prerequisites** action, after the original prerequisite bytes are read back.
The initial vector has four current-stage outputs pending, 28 later outputs
pending and zero retained observation bindings. None of the eight domains is
qualified. The original source reader checks the exact sole-prerequisite
inventory as well as the original committed prefix; it does not accept a
self-referential or abbreviated initial inventory.

The setup view is now `rocell.wizard_physical_camera_setup.v3`. Its new
`configuration_records` sibling is a compact cached projection, withheld while
result publication is pending and held after source/log/shutdown faults.
Historical v1/v2 setup displays and v1 source stores remain supported without
an automatic migration. The immutable vector is never regenerated by refresh,
status reads or original-store reopening.

**Export logs** reserves `attachment-configuration-records.json` before ordinary
result history. The complete original document is kept shallow enough for the
existing diagnostic limits; its independently retained hash can be verified.
Partial attempts remain diagnostic-only. Redacted or over-budget data cannot
claim a complete current export. The selected parent directory is
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.

Completed scoped selections (the earlier overlapping reruns are not added):

| Selection | Result | Scope |
| --- | --- | --- |
| New pure configuration codec | 70 passed, 1.81 s | Actual strict codec over typed modeled V2 snapshots; no store/device access |
| Epoch session + source workflow + prerequisite readers, `-k 'not actual'` | 114 passed, 3 deselected, 19.96 s | Actual readers/codecs with modeled scopes and injected faults |
| New actual NTFS epoch publication/reopen case | 1 passed, 14.08 s | Actual original storage and new owner, no hardware |
| Configuration service + setup/restart/source service, final source | 72 passed, 16.04 s | Includes 19 new actual-codec/model-retention/public-export cases, including late failed reopening |
| Setup restore + diagnostic export + wizard actions | 127 passed, 4.36 s | Existing closed software regression |
| Arrival service | 45 passed, 19.44 s | Includes existing actual original-store no-replay reopening |
| CLI + local HTTP integration + web server | 92 passed, 10.05 s | Local software interface; no device connection |
| Configuration display + existing setup/restart/source UI | 199 passed, 22.57 s | Actual renderers with typed/modeled inputs; this run preceded four final added cases |
| Final focused configuration UI file | 60 passed, 7.38 s | Overlaps 52 cases in the preceding row; adds four absent/pending prerequisite cases and four actual-export cases |
| Preserved actual original/reopened v3 exports (also included above) | 4 passed, 1.33 s | Both production renderers consume the full actual snapshots; all exported bytes unchanged |

These are bounded software checks, not hardware qualification. Deselected tests
are not claimed as passed. Black, Node syntax and scoped mypy checks pass.

### Final public lifecycle

Final application source fingerprint:
`c3202a941a9a51a8c66ec800b8b032ffa2c23efc51b45e075b9d9a5b786b58a5`.

The actual public ticket/service flow completed successfully: initialize,
collect prerequisites/vector, assess sources, review with a distinct label,
nine note/result rotations, full export, shutdown, new launch, explicit original
discovery/reopening and a second full export. There were no device/process,
serial, power, motion or contact actions. The original source stage remained
BLOCKED, the 14 downstream original stages PENDING and the separate physical
progress checklist all 15 PHYSICAL_PENDING. Successful file operations do not
convert those states into acceptance.

- Original launch: `wizard-1366edf060064230a0c532b0c8ec386f`.
- Reopened launch: `wizard-941ddc15777a45bebb315eed7d0d41e3`.
- Original session: `physical-camera-69b035611c1952eb6b8ae67b2f4e8577`.
- Original cell: `wizard-physical-camera-47fca095dd613c19`.
- Immutable vector SHA-256, identical across both exports:
  `2d0ee2d03b6b2bd9a7382bb8b2abfe08b90f6ea02c84a2612f2b98012245df1d`.
- [First verified configuration export](../runs/wizard-exports/wizard-20260908T193352199430Z-82026b2978e44258babc9bec71bffa66/attachment-configuration-records.json).
- [Verified reopened configuration export](../runs/wizard-exports/wizard-20260908T193402708784Z-469cf7ade6f64c94a3392971972ba502/attachment-configuration-records.json).

Reproduce once from the workspace root only while that exact source is current:

```powershell
.\.venv\Scripts\python.exe software/scripts/wizard_workspace_sources_smoke.py --expected-source-sha256 c3202a941a9a51a8c66ec800b8b032ffa2c23efc51b45e075b9d9a5b786b58a5
```

The script uses a fresh isolated original store and never retries an uncertain
operation. It preserves its reports/stores for inspection. Do not replace its
expected fingerprint to misrepresent this verification as covering edited code.

The first pre-final source `61856b76de80d41589b47e292c581f79d540c9ac7d8ef5b0d50f70ed58605006`
also completed the normal lifecycle. Subsequent read-only review identified a
different failure case: a new owner could cache verified bytes, fail a late
Stop/source/lease check before adoption, and omit the vector from the dedicated
export. The final source preserves the original reader cache as historical-only
diagnostics; it never populates the current UI or admission state from it.
Three injected late-error/export regressions pass. The first run and its two
exports remain preserved; neither failed operations nor original evidence were
replayed, overwritten or relabeled as the newer source.

### Startup and package checks

Both rehearsal and physical `start-rocell-wizard.ps1 -Check` exit 0. The physical
check confirms the selected workspace export root, no connected camera/arm,
no initial configuration record and all physical stages pending.

The runtime `.venv` could not build an offline wheel because it lacks
`bdist_wheel`; no dependency was installed or changed to conceal that result.
An offline `--no-deps --no-index --no-build-isolation` build using the existing
host Python (setuptools 81.0.0, wheel 0.47.0) passed. All 260 packaged Python,
HTML, CSS and JavaScript entries match their source bytes, with no duplicate
entries. Wheel SHA-256:
`6b1dc90c41d3c950dfd3d914aa82aaaf1e79e70f9a9cf3a4e15013df4c465f66`.
This is a package-content check, not a clean-host installation or a release.
Both native camera executables and their build manifests retain their earlier
hashes; neither was rebuilt, repinned or run.
