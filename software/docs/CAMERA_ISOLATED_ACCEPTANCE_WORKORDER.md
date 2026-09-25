# Camera-only isolated acceptance

Date: 2026-09-12. Status: **isolated camera lifecycle accepted; physical qualification remains open**.
Continues [P1 camera startup](STORAGE_EXISTING_ROOT_OBSERVATION_WORKORDER.md)
under [the preparation plan](PRE_ARM_CALIBRATION_EXECUTION_PLAN.md).

The user is developing the arm in parallel. This task owns camera test tooling,
camera lifecycle verification and this camera-specific handoff only. Do not edit
arm implementation, shared UI/service code or hardware configuration to make the
camera test pass. No physical camera, USB metadata query, serial, power or motion
operation is authorized by this software acceptance lane.

## Why isolation is required

Previous full-history run 07 passed its workflow assertions, but the shared
checkout changed while it ran. Its source-modeled fixture and already imported
modules cannot turn those changing bytes into one accepted software revision.
Preserve that result and its limitation. Do not seed another run with its store.

## Implementation

1. `software/scripts/camera_acceptance_snapshot.py` inventories explicit software,
   test, controlled-build and native-runtime input trees. It excludes previous
   runs, temporary work, `node_modules`, virtualenvs and caches. It refuses linked/reparse inputs, overlapping or
   existing destinations, changed-copy inputs and excessive file/byte inventories.
2. Copy into a new private input tree and require identical source-before,
   copied-byte and source-after inventories. Retain a per-input SHA-256 manifest.
   A failed partial copy is preserved and is not accepted or automatically retried.
3. Launch the **copied script** using the existing Python environment. Explicitly
   import `rocell` from the isolated `software/src`; assert that location. Disable
   external pytest plugin autoload and Python bytecode writes. No package, driver
   or firmware installation is performed. The shared interpreter/dependencies
   are reported, not represented as separately frozen executable artifacts.
4. Run a short fixture/contract selection before the complete history. Use unique
   result directories outside the input tree. Verify the whole manifest and the
   real application fingerprint again after each run, even when pytest fails.
   A pytest success plus a failed input audit is not acceptance.
5. The complete camera test now closes the capture application after successful
   capture/export/readback, constructs a fresh wizard and explicitly reopens the
   original setup. Require identical original subjects, clean leases, disconnected
   status, no image/current metadata/settings receipt/capture queue, and rejection
   of capture without a fresh current context. Verify the old export remains
   readable without importing it as device ownership.

The shared runner received two further developer-tool improvements after the
isolated full lane started: copying is bounded to each inventoried file length
(growth/shrinkage is rejected), and JUnit validation requires actual passing
cases rather than accepting an exit code of zero with skipped tests. These
changes have **25 passing small file-only tests in 0.84 s** recorded in
`.codex-preserved/camera-result-audit-20260912-02.xml`. They do not change the
already frozen container-02 runner. Do not describe that running copy as testing
these newer runner changes; separately check its terminal JUnit before acceptance.

The check is read-only and can be applied to the existing reports:

```powershell
.\.venv\Scripts\python.exe software/scripts/camera_acceptance_snapshot.py check-junit `
  --junit .codex-preserved/camera-isolated-20260912-02/smoke-01/junit.xml --lane smoke
# Only after the complete run returns a terminal result:
.\.venv\Scripts\python.exe software/scripts/camera_acceptance_snapshot.py check-junit `
  --junit .codex-preserved/camera-isolated-20260912-02/full-01/junit.xml --lane full
```

An absent, skipped, failed or differently selected complete test is not acceptance.
The smoke lane requires 23 distinct executed cases; the complete lane requires
the exact full-history camera case. These are local development reports, not
signed hardware evidence or permission to activate a device.

The snapshot is an explicit developer copy, not a security sandbox or an approval
of every parallel arm change it happens to contain. Do not write into its input
tree during acceptance. A later shared-checkout revision needs its own verification;
the passing copy is never silently rebound to that newer revision.

## Commands and acceptance evidence

From the shared workspace, create a new absent container, then a new input tree:

```powershell
New-Item -ItemType Directory -Path .codex-preserved/camera-isolated-20260912-02
.\.venv\Scripts\python.exe software/scripts/camera_acceptance_snapshot.py create `
  --source . --snapshot .codex-preserved/camera-isolated-20260912-02/input
```

Use the script inside that copy, not the shared copy, for both lanes:

```powershell
.\.venv\Scripts\python.exe -I `
  .codex-preserved/camera-isolated-20260912-02/input/software/scripts/camera_acceptance_snapshot.py run `
  --snapshot .codex-preserved/camera-isolated-20260912-02/input `
  --results .codex-preserved/camera-isolated-20260912-02/smoke-01 --lane smoke

# Run only after smoke passes with a matching input audit.
.\.venv\Scripts\python.exe -I `
  .codex-preserved/camera-isolated-20260912-02/input/software/scripts/camera_acceptance_snapshot.py run `
  --snapshot .codex-preserved/camera-isolated-20260912-02/input `
  --results .codex-preserved/camera-isolated-20260912-02/full-01 --lane full
```

Existing destinations are never reused. Each result directory contains JUnit,
fresh pytest originals and `execution-audit.json`. Record the snapshot manifest,
source/test hashes, exact exports, terminal audit and physical-effect limitations
before closing P1. Software success is not camera-unit qualification, installed
calibration, stage acceptance or permission to operate the arm.

Initial development check: **34 passed, one slow case deselected, 5.81 s**, in
`.codex-preserved/camera-isolation-fast-20260912-01.xml`. Eleven snapshot-tool
cases cover exact copying, changing/added/missing input, concurrent edits,
destination preservation, manifest mismatches and an isolated NTFS junction.
Nine pure assertion cases cover fresh camera restart state. Remaining cases
exercise the existing source-fixture and terminal-fingerprint guards.
This short selection does not execute the new complete post-capture restart.

## Execution ledger

The complete workflow and its post-run audit passed; the terminal record below
defines that claim. No overall P1 closure or actual camera observation is claimed.
Source isolation does not isolate shared CPU/disk load or establish worst-case
startup performance.

The first inventory refused a reparse point in the build's temporary workbook
verification `node_modules`. No input snapshot or accepted manifest was created.
Temporary work and dependency caches are now explicitly excluded; the rejection
of links in actual selected inputs remains unchanged. Container 01 is preserved.
Use a new container 02 for the corrected inventory.

Container 02 accepted **3,831 input files / 898,102,427 bytes**, with identical
source-before, copied and source-after inventories. Input roster SHA-256:
`f575f5d791ab0141fa1284bf4e1f57b507b062c81166fe8107eba3f7edf058fe`.
The 13 final snapshot-tool cases pass in 0.96 s after the explicit temporary/cache
exclusions. Their isolated NTFS link test still rejects links in selected inputs.

The isolated smoke returned **23 passed, one slow case deselected, 8.74 s**.
Its `smoke-01/execution-audit.json` records `accepted: true`, unchanged full
input inventory and matching actual application fingerprints:
`426eb8a21300dec278d0eaf3e48e62051ef2ec5bc4fa54e70f49969e67762e69`.
The recorded import is the copied `input/software/src/rocell/__init__.py`, not
the mutable editable checkout. Python 3.10.10 / pytest 8.4.2 are shared installed
dependencies; no environment installation or driver change was performed.

The complete lane started around 14:05 local using `full-01` and the same frozen
input tree. Keep that tree unchanged. Camera test/tool work in the shared
checkout may continue, but any later version must be labeled separately and
must not be substituted into this run or described as its tested inputs.

### Terminal acceptance — 14:44 local

The full lane returned **one executed PASS, seven non-slow cases deselected,
2,326.08 s (38:46)**. A separate JUnit check confirms the exact full-history case
executed with zero skips. The frozen runner reports `accepted: true`, exit zero,
no input audit error and identical starting/ending actual application source
fingerprints (`426eb8a2…62e69`). All 3,831 selected input files match the original
roster after the test. No copied inputs were updated or rebound during execution.

All eight camera-successor public operations succeeded. The capture export was
independently verified using the **isolated production verifier**, not a replaced
test verifier: four payload files / 135,799 bytes, with a matching manifest.
Its diagnostic source identity remains modeled `a` × 64, separate from the
actual executing application fingerprint; `PHYSICAL_DIAGNOSTIC` is the tested
export format, not a claim that physical camera observations were made.

The new post-capture application reopened the same original directory and exact
original subjects. It had a distinct launch ID, both devices `NOT_CONNECTED`,
no current image, no retained settings reference, no attempts and no automatic
replay. A new capture request was rejected without fresh current context. The
old export remained readable. Original leases were clean; simulated stages 1–4
remained PASS, stage 5 `WAITING_OPERATOR`, and later stages PENDING. This is an
application restart, not another real or simulated host reboot.

Retained artifacts below are relative to
`.codex-preserved/camera-isolated-20260912-02`:

| Artifact | SHA-256 |
| --- | --- |
| `full-01/junit.xml` | `6f6a4329db7012eeed1344e65549cb7841bcb2bf8bd28a3f694ae0537dc9d5a3` |
| `full-01/execution-audit.json` | `32d5dad205e0c3df498def9513243d5d1ca85c5b0536a2f4cb8b82b174e928e7` |
| `full-01/pytest/test_full_original_history_reo0/camera-full-history-checkpoint.json` | `0111b15d6a8ea845a0372f199dbf5c3b7384c22c04abc96afb6e8ca8ac131c9a` |
| `input/camera-input-manifest.json` | `3f6e786344b4d0afdd9b8bcd153598fc53f4910b507991b539e5a126a399d0ad` |

Capture operation: `operation-ef692de807a6461e8af7ba91e20b7a9d`.
Export under the test root:
`reboot-exports/wizard-20260912T184206573060Z-8552e521189b4a8c94e0664ebbc35149`.
Export verifier's canonical manifest digest (not the manifest file-byte hash):
`38ccc723418b386dff61f57976059d645247f7bdb657df453575a0ef5454e76f`.
The exact `manifest.json` file-byte SHA-256 is
`525d19d18daa60fd629894208d4a6a37b13799aae10c101c7b9120a65522c72a`.

The isolated original store contains 280 files / 1,572,839 bytes at termination.
Twenty-eight copied native runtime files were verified by the fixture; no
camera-capable process executed. Hardware facts and native owners are modeled;
frames are tiny synthetic YUY2 inputs, not a 20 MP throughput test. These are
nominal full-history sizes, not maximum quota/growing-history qualification.

The trace contains 1,484 finished spans, no unfinished/dropped spans and no
observer errors. Probe release returned in 1,766 ms, with 31 ms from `begin`
return to release start (1,797 ms combined observed interval). Capture release
returned in 2,156 ms with a 47 ms gap (2,203 ms combined). Existing purpose-specific
limits remain 2,000 ms and 5,000 ms. These intervals are not exact internal
deadline timestamps or worst-case margins; nested durations must not be summed
as exclusive work and shared-host load was not controlled.

End-to-end public action timing also matters for wizard usability:

| Public operation | Observed seconds |
| --- | ---: |
| Initial original refresh | 49.92 |
| Probe preparation | 94.62 |
| Probe review | 99.41 |
| Probe | 89.39 |
| Stage reported settings | 0.03 |
| Settings-verification capture | 120.98 |
| Export exact capture attempt | 0.30 |
| Final original refresh | 57.17 |

The capture duration includes original validation and publication; it is not
sensor exposure time. This passing run does **not** establish a fast onboarding
experience. Profile repeated pre-admission original validation in a future
camera-only performance ticket, retaining current checks, quotas and deadlines.

This closes the fixed-source nominal capture/export and actual new-application
restart evidence gaps for this snapshot. It does not close every P1 ticket:
growing-history coverage, current-source UI integration and the plan's complete
export matrix still need reconciliation. This full case exports the settings
attempt and preserves the original probe packet; it does not itself perform a
separate public probe-attempt export. Later shared arm/UI changes are not accepted
by this frozen run. P5 mode review and genuine camera qualification remain open.

## Next camera-only implementation target

After the terminal acceptance is reviewed, continue P5.2/P5.5 with a focused
mode-policy integration design. Do not start another arm workstream.

- Reuse `physical_camera_configuration.py` for native capability selection,
  exact requested/observed mode and control readback, settings epoch and original
  identity/source joins. A supported selection and matching still frame are not
  the same thing as an approved commissioning mode.
- Audit the existing `vision/uvc_inventory.py::assess_uvc_inventory` prototype
  before adding a parallel comparator. It currently tests an exact native
  **5472 × 3648, 9 fps, YUY2** tuple, manual exposure/white balance, identity,
  negotiated USB category and settings stability across reopen observations.
  Its outcome is explicitly diagnostic rehearsal, not physical stage acceptance.
- Preserve the received-camera discrepancy: the separate bench utility reported
  and captured **8 fps**, and rejected a 9 fps request. The source profile and
  bench records must remain distinct. A future reviewed operating profile needs
  its own version/digest and source bindings; no fallback or silent alteration
  of the purchased-camera catalog is permitted.
- Compose an original-bound stage-5 assessment and a separate operator review
  from verified probe/settings/readback evidence. Missing serial, negotiated
  speed, required electronic-control readback or reopen evidence must stay
  separately visible. Preserve rational frame rates and pixel-layout evidence
  from the native path; do not convert observed unknowns into defaults.
- Keep stage-6 freshness independent. One retained image cannot qualify
  buffering, sustained latency or exposure stability. Equal image bytes in a
  static scene are not independently sufficient to diagnose a replay.

This is the next implementation target, **not completed by the acceptance
tooling**. Lens focus, aperture, working height, coverage, installed calibration
and physical camera qualification remain separate. The approximate 10-inch bench
focus observation is not a mounting specification. Any next real camera action
must use the supported, currently eligible workflow and its disclosed consent;
the simulated originals from these tests must never be imported as real setup.
