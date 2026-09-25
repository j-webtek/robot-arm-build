# Control architecture and interface audit

2026-09-20. Source inspection only: no device access, startup, motion, flash or
settings changes. r31 is the last documented installed release; this inspection
does not freshly identify the running controller or its pose.

## What works together today

| Path | Main files | Scope |
| --- | --- | --- |
| Standard JSON | `arm/protocol.py`, `arm/serial_transport.py` | Existing encoding and gated serial feedback; not a newly released general movement API |
| r31 local movement | `application/local_shoulder_step_runner.py`, `local_shoulder_step_review.py`, `local_shoulder_step_release.py` | One release-bound local shoulder step with exports and fault settling |
| Existing HTTP | `application/shoulder_session_http.py` | No-retry route-restricted transport; responses are not authenticated |
| Firmware local owner | `firmware/diagnostics/local_shoulder_step_board.h`, `local_shoulder_step_session.h` | Owns raw acquisition, one paired target write, receipt progression and endpoint checks |
| Synthetic campaign | `application/shoulder_characterization_sim.py`, `shoulder_characterization.py` | Twelve-leg simulation and independent classifier; no hardware adapter |
| Batch analysis | `application/characterization_batch_review.py` | Verifies export, reassesses observations, groups residuals and exports results |
| Presentation | `application/characterization_report.py` | Pure Markdown renderer, usable by CLI and future UI |
| Export storage | `application/wizard_diagnostic_export.py` | Existing diagnostic bundle integrity and publication |
| Experimental campaign | `application/characterization_*`, `firmware/diagnostics/characterization_*` | Partially implemented authenticated campaign path, not established as installed |

Current offline sequence:

1. Existing simulator creates a finite campaign and raw observation exports.
2. Batch review verifies the final bundle and reassesses the raw observations.
3. Pure presentation renders the same results for humans.
4. Existing exporter publishes JSON and Markdown together under a new manifest.

There is no new simulator, SDK dependency, connection manager or command language.

## Concrete installed-path limitations found in source

These explain why simply adding a loop around the existing r31 runner is not a
valid implementation of a repeated bidirectional campaign:

1. `local_shoulder_step.py` admits a fixed seven-servo starting envelope and
   expected goal set. It constructs a shoulder-decreasing/partner-increasing
   step, not arbitrary endpoints or both directions from any pose.
2. `local_shoulder_step_session.h` sends at most one pair packet. Speed 20 and
   acceleration 1 are fixed there. Three arrived samples within two counts are
   required, with a five-second observation deadline.
3. `local_shoulder_step_board.h` sets sticky `rocellShoulderReserved` and
   `rocellDiagnosticOwned` flags; setup rejects when already reserved. No normal
   completed-session release is present in this composition.
4. `local_shoulder_step_runner.py` also publishes a boot-specific reservation
   and uses the fixed identity `local-step-1`. Reusing it repeatedly is not an
   existing campaign contract.
5. Fault settling is read-only evidence collection, not permission to dispatch
   another movement. A settled endpoint miss still faults the local session.
6. `local_shoulder_step_release.py` binds revision 31 and fresh same-boot idle
   state. Historical installation evidence is not proof of current flash bytes.

The existing HTTP adapter lists several route families. A host-side route name
or capability flag is not proof the corresponding firmware composition is live.
Likewise, a source header marked "candidate" can have stale comments; use release
artifacts and recorded installation evidence, not comments alone, to establish
deployment status.

**Decision:** reuse diagnostic records, codecs, export and analysis. Do not bypass
sticky reservation or use stock JSON to evade the local session owner. Before
physical campaigns, compare the pinned r31 composition with alternatives and
choose one coherent execution path. A narrow controller lifecycle/policy change
may still be necessary; it is not equivalent to a firmware change per test.

## Structural issues and incremental improvements

### 1. Make the supported path discoverable

Inspection found 584 top-level Python modules in `application`, plus many
historical experiment names. Module presence currently says little about whether
it is offline, live-capable, installed, or superseded.

Start with this index and the active reuse plan. For each newly touched entry
point document: input/output, units, side effects, evidence basis and deployment
status. Avoid a mass move or deleting historical evidence during integration.

### 2. Keep calculation separate from side effects

Implemented first slice: `characterization_report.py` only renders a reviewed
summary. It neither reads files nor imports a device. The batch review now loads
the simulator only for `--simulate`, not when reviewing an existing bundle.

Next extract reusable analysis from orchestration only where a second real caller
exists. Do not create an abstract framework or another generic runner in advance.

### 3. Give the wizard one application workflow

The new batch review is currently CLI-only. Future UI wiring should call the same
review/export service and show its Markdown/JSON, not duplicate calculations in
UI handlers. Do not let UI routes open serial or independently issue commands.

### 4. Distinguish evidence from transport success

Keep requested target, transmitted command, accepted target and fresh position
separate. The future live importer must validate the actual native schema and
retain boot/command identity, sample times, raw reads and firmware/config identity.
Do not convert live data into the current synthetic schema just to reuse analysis.

### 5. Separate test outcome from permission to continue

Accurate arrival, bounded stable miss and invalid/uncertain evidence are different
outcomes. The offline classifier represents this distinction; the r31 local owner
does not implement campaign progression after a miss. A host-only relabel must
never pretend it changed controller policy.

### 6. Isolate simulation, integration and hardware tests

Use pure tests for policy/presentation, bundle tests for exports, fake-transport
tests for lifecycle and no-retry behavior, and explicit hardware tests for device
claims. Preserve real measurements separately from generated examples. Test the
actual SDK/driver boundary before claiming compatibility, not only a fake API.

### 7. Consolidate after behavior is covered

Suggested eventual ownership boundaries: `arm` for wire/transport, `application`
for finite workflows, `evidence` for validated observations and review, `ui` for
presentation. Move one covered feature at a time and retain import compatibility
where needed. No sweeping renaming is needed to begin experiments.

## Next concrete work, in order

1. Check pinned r31 build provenance and available native diagnostic records
   against this source audit; no movement is needed for this review.
2. Implement a read-only importer for existing physical result bundles, preserving
   their different schema and provenance. Reuse raw endpoint calculations where
   valid, but do not manufacture freshness or missing delivery evidence.
3. Present old physical trials alongside synthetic results with separate labels.
4. Decide the minimum reusable execution change required for a finite campaign;
   specify lifecycle, bounds, bidirectional targets and retained fault evidence.
5. Validate that change with fake-device and integration tests before release.

This order gives useful analysis of data already collected before another live
test or firmware change. Camera and physical-contact calibration remain deferred.

## Validation of this increment

22 focused tests passed for presentation, batch review and classification. The
offline CLI generated and verified a new JSON/Markdown review bundle:
`runs/wizard-exports/wizard-20260920T044546427470Z-094ab971a3f94081b42a94a1f025b16c`.
The rendered report is synthetic; no new physical accuracy evidence was acquired.
