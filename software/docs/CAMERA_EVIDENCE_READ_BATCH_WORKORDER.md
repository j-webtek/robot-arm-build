# Camera evidence readback performance

Date: 2026-09-12. Status: implemented; frozen software acceptance passed.
Continues [camera-only acceptance](CAMERA_ISOLATED_ACCEPTANCE_WORKORDER.md).

## Evidence and scope

The accepted frozen full-history trace recorded 110 camera record audits
(45.706 s inclusive) and 106 session snapshots (18.032 s inclusive) during the
122.532 s instrumented settings-capture call. Nested spans overlap. The public
operation's separately recorded duration was 120.98 s. These are not sensor
capture times or exclusive CPU costs.

The original reader currently replays the entire session inventory for every
package; camera-scope package reads also re-audit the entire camera record family.
First isolate this repetition. Do not change the arm, shared Arrival service/UI,
hardware configuration, native runtime, admission rules, deadlines or quotas.
Preserve the prior frozen input tree, original stores and reports unchanged.

## Proposed implementation

1. Add a private synchronous readback scope to camera persistence. It obtains a
   fresh exact session snapshot, complete camera-family record audit, attempt and
   quarantine snapshots under the existing caller-owned leases. No caller-supplied
   or serialized snapshot can seed the scope.
2. Within that scope, allow each exact inventory reference once. Keep each
   package's existing pre/post manifest/payload verification and bounded original
   byte read. Check scope and exact lease ownership around every read. Reject
   nested scopes and use of a reader after scope exit, including exceptional exit.
3. Before successful scope exit, re-audit all camera-family records and compare
   them, attempts, quarantine and the complete session to the initial state.
   Any change rejects the result; failed body operations retain their original
   exception. No reads, snapshots or verdicts are reused across scopes.
4. Only after the isolated primitive passes, integrate it into the camera original
   reader. Preserve every semantic validator, source/Stop/deadline callback,
   manifest read, role/size limit and sibling-campaign reader. Recheck caller
   context after the closing audit. Diagnostic retention is not successful
   publication or permission to open a device.

## Verification and acceptance

- Test exact stage/camera leases, type/size/membership limits, duplicate reads,
  nested/reused readers, exceptions, changed snapshot/records/attempts/quarantine,
  and scope loss. Use actual fresh NTFS originals for package corruption and
  before/after read-count/timing comparisons; incapable hardware only.
- Run existing original readback and camera persistence regressions. Explicitly
  label modeled fixture adaptations; do not substitute those for actual NTFS tests.
- Keep single-package public APIs and camera admission comparisons unchanged.
- Record counts and measured baseline/candidate timings without flaky timing
  assertions or an inferred whole-wizard speedup. Final original/lease checks
  must still run even when earlier semantic validation succeeds.
- If integration is completed, obtain a new verified input snapshot and fresh
  original-history acceptance before claiming the changed full workflow passes.
  Never seed it with the previous run's original store or relabel old acceptance.

## Deferred work

The reviewed 8 fps operating policy, original stage-5 assessment, USB operating
speed/identity, sustained freshness and installed optics remain separate tickets.
No physical camera or arm action is authorized by this development work.

## Development checkpoint

The private batch and original-reader integration are implemented in
`commissioning_camera_persistence.py` and `physical_camera_session.py`. The
single-package methods remain unchanged. The original reader retains its existing
semantic checks and end-of-body family audit; the new batch adds its independent
opening/closing audits. A final source/Stop/deadline callback follows scope exit.

- Initial batch primitive: 24 PASS / 20.73 s in
  `.codex-preserved/camera-read-batch-20260912-01.xml`.
- Mixed actual NTFS camera/USB family: 1 PASS / 31.79 s, 24 other cases deselected,
  in `.codex-preserved/camera-batch-sibling-20260912-01.xml`. Corrupting an actual
  sibling identity record rejects despite an unchanged session snapshot.
- Original readback integration: 70 PASS / 314.43 s in
  `.codex-preserved/camera-read-batch-integration-20260912-02.xml`.
- Mypy checks both changed production modules; Black checks both modules and
  both changed/new test files. The missing annotation import caught by Mypy was
  added; it does not relax any runtime check.

The first integrated draft report is retained: 65 PASS, two failures. An inherited
modeled fixture replaced its snapshot provider as history grew, but the new
modeled batch captured the earlier fixture function. The fixture now calls its
current `tx.snapshot()` provider. No production header/source comparison was
disabled. Those fixture adaptations are not real NTFS acceptance evidence.

Actual, newly constructed 12-package NTFS microbenchmarks returned identical
payloads and unchanged original snapshots, with clean lease exit:

| Scope | Existing single reads | Batch | Whole-inventory reads | Family audits |
| --- | ---: | ---: | --- | --- |
| Stage-only | 0.440 s | 0.234 s | 12 → 2 | 0 → 2 |
| Camera | 0.634 s | 0.263 s | 12 → 2 | 12 → 2 |

These are single local samples of the primitive, not a full-wizard speedup.
Measurement files are in the initial test directory under
`software/runs/pytest-camera-read-batch-20260912-01`. The full original reader
also keeps its existing semantic/sibling audit, so its audit count is not simply
the primitive's count. Different draft selections are not one frozen-source
release. The later frozen acceptance below establishes the successor result.

## Frozen successor

Additional camera persistence/original-scope regressions passed **94 cases in
218.29 s**, recorded in `.codex-preserved/camera-read-batch-regression-20260912-01.xml`.
The development selections are retained separately, not summed as one release.

New input snapshot: `.codex-preserved/camera-isolated-20260912-03/input`, created
at 19:08:53 UTC. All **3,854 files / 899,285,832 bytes** matched source-before,
copied bytes and source-after inventories. Roster digest:
`811b5f508458c5bc17a977e76066100f76dc61e75661903584fa3eb1f782acd2`.

The isolated smoke passed **23 cases / 5.45 s**, one slow case deselected and zero
skips. Its final input/source audit was accepted. Actual application fingerprint:
`adfc02617d55e9ecc71d3c40dd2f1d69f952e86883efd822d68fa5bb4af809f1`.
JUnit SHA-256: `e3c9b5e101f8f8517625183219eed4eebc51b6aea5e05711f721a37014bba171`.

The full lane passed in `full-01`, using the copied runner and new originals.
Do not edit the input copy or seed it from the previous accepted store. Shared
arm changes captured between snapshots remain independently owned and unreviewed
by this camera task; a cross-revision end-to-end timing difference cannot be
attributed exclusively to this patch. The side-by-side primitive microbenchmark
uses the same implementation/revision for its old and new read paths.

The manifest comparison identifies two owned changed production modules and
17 other changed source files between the accepted snapshots. Their contents
were preserved, not inspected or reverted as part of this camera patch.
Owned production file-byte SHA-256 values at the new freeze:

- `commissioning_camera_persistence.py`:
  `5231679cca9c4ab6600989be7d2c216c9f65ec339564efcb3c61b1830befbeaa`.
- `physical_camera_session.py`:
  `8982daecb62b3f186c2a41123015fe968a6e3d3e4a904d61ea4f310cf9e1b6c3`.

The primitive benchmark is intentionally small. Opening/closing audits add
fixed work, so a batch with very few packages need not be faster. No claim of
maximum-history, worst-case latency or hardware qualification follows from it.

## Developer integration notes

The existing wizard action and original-reader entry points do not change. A
caller still owns the exact cell/session leases (plus camera lease when required)
before entering the reader. The new helper is private persistence plumbing, not
a new wizard action or a device connection API.

1. `_read_original_evidence_in_scope` verifies the transaction and expected lease
   set, then opens the private `_original_evidence_readback` context.
2. Persistence supplies a freshly observed session and a scope-bound package
   reader. `_read_original_evidence_from_batch` runs the existing role-specific
   validation against those original bytes. Diagnostic retention may occur, but
   does not authorize a connection or publish a successful workflow.
3. Normal context exit verifies complete store stability. The application then
   checks source, Stop and deadline state again before returning the workflow.
   An exception anywhere takes the existing held/error path; it must not trigger
   an automatic retry or restore a native owner from saved diagnostics.

Do not persist the callable, accept a batch seeded from JSON, carry observations
across actions, catch a closing-audit failure and use a retained workflow anyway,
or remove the final context callback. Keep isolated single-package callers on
their unchanged APIs. The batch is useful only within one synchronous read.

For a follow-up change, run the batch tests and original-reader regressions first,
then create a **new** input snapshot and new result directory using the existing
`camera_acceptance_snapshot.py` commands. Never reuse pytest basetemp directories
or edit an accepted input copy. A test pass with a changed source roster, skipped
Windows execution or unsuccessful export verification is not accepted evidence.

After performance acceptance, the next separate camera work item is an explicit,
versioned operating-mode review: retain the measured 8 fps versus requested 9 fps
discrepancy, surface the distinction in stage 5, and test unsupported mode/control
readback behavior before another physical camera session. Do not silently change
the frozen catalog profile or treat a clear bench image as installed calibration.

## Terminal frozen acceptance

The complete case passed in **1,869.04 s (31:09)** with seven other cases
deselected, zero skips, and matching before/after source and file inventories.
The runner accepted the outcome, independently of pytest's exit code. Full JUnit
SHA-256: `076f79b2c3368b1ef559e81663e73a2f59dad6d295dc45a4531e9b338ea03811`.
The full execution audit is
`.codex-preserved/camera-isolated-20260912-03/full-01/execution-audit.json`.

All eight public successor operations succeeded. Capture produced an independently
verified exact-attempt export. Original readback and a genuinely fresh application
restart passed with clean leases. No connection, image or capture permission was
restored, and a stale capture request remained held without automatic replay.
The simulated stage states remain four PASS, stage 5 WAITING_OPERATOR and ten
PENDING. This is not physical stage acceptance or a current shared-checkout release.

| Public operation | Prior snapshot seconds | Candidate seconds |
| --- | ---: | ---: |
| Initial original refresh | 49.922 | 40.016 |
| Probe preparation | 94.625 | 73.953 |
| Probe review | 99.407 | 76.891 |
| Probe | 89.391 | 65.219 |
| Stage reported settings | 0.031 | 0.047 |
| Settings-verification capture | 120.985 | 83.281 |
| Export exact capture attempt | 0.297 | 0.203 |
| Final original refresh | 57.172 | 46.719 |

The capture trace records **42 family audits versus 110**, and **37 session
snapshots versus 106**. Their inclusive durations are 19.079 s and 6.535 s;
the enclosing instrumented action is 84.844 s. These overlap, include tracing
overhead and differ from the separately timed public operation. All 814 retained
spans finished with no drops or observer errors. These are one-run, cross-revision
observations, not a controlled attribution of the entire improvement to this
patch, a worst-case bound, or proof of a responsive wizard.

Probe release returned in 1.703 s, with a 0.031 s gap after `begin` returned
(1.734 s combined observed interval). Capture release returned in 2.218 s with
a 0.047 s gap (2.265 s combined). The existing 2 s / 5 s purpose-specific limits
were unchanged. Observed intervals are not exact internal deadline timestamps.

After the full lane finished, a separate isolated invocation ran all **25 batch
cases in 55.65 s**, with zero skipped/failed cases and matching complete input
inventories and source before/after. It imported the copied source explicitly
under Python `-I`, disabled plugin autoload/bytecode/cache writes, and used a new
external basetemp. Its `batch-01/junit.xml` SHA-256 is
`89d5bc798f941509c9300e6e9a02f53dc8325be6f7915f606d15e05d5fa47117`.
The adjacent execution audit is developer-transcribed from that invocation's
structured output, not the smoke/full runner's signed or automatic certificate.
Neither audit is cryptographically signed. No competing suite was launched by
this task during the full timing run; unrelated host workload was not controlled.

The exact capture export directory is
`wizard-20260912T194010929018Z-6ef2e159a8b94ee8aabdda2d710e5987` under the full
test's `reboot-exports`. Verification returned `VERIFIED_DIAGNOSTIC_EXPORT`,
135,799 payload bytes, no physical authority and canonical manifest digest
`cd176470f9862b79b924ff7b6e97fdb4f18a6be15cb49b30fb6324e97823100b`.
The **whole manifest file's** SHA-256 is separately
`9d3f29417b01db19e91d8dfbd933d9655c819ed5bd18945097c54d04f22b06fe`.
Its modeled source is `a` repeated 64 times; its physical-diagnostic schema label
must not be mistaken for actual camera measurements.

Developer handoff:
`software/runs/wizard-exports/camera-readback-performance-20260912-01/README.md`.
It contains exact copies and a file-byte copy index, not the full input tree,
runtime dependencies or an importable hardware setup. Prior bundles and original
stores remain unchanged. P1 latency/growing-history/export-matrix reconciliation,
P5 operating policy/control review and real camera qualification remain open.
