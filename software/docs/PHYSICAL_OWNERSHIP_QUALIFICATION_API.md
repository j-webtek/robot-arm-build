# Fixed software ownership qualification

This is the software HZ-012 mechanism experiment used by the source-stage
successor. It is not a received-device qualification, a native runtime release
credential, an electrical isolation observation, or a canonical stage transition.
Import, construction and historical verification perform no experiment.

## Explicit API

```python
collect_physical_ownership_qualification(
    workspace: Path,
    *,
    assigned_directory: Path,
    source_sha256: str,
    cancellation: threading.Event,
    progress: Callable[[str], None],
    deadline_ns: int | None = None,
) -> PhysicalOwnershipQualification

verify_physical_ownership_qualification(
    value: bytes | PhysicalOwnershipQualification,
    *,
    expected_source_sha256: str,
    expected_directory: Path | str,
    expected_report_sha256: str,
) -> PhysicalOwnershipQualification
```

The application supplies the exact fresh, same-volume directory, normally
`<original-camera-M1>/source-ownership-<qualification-id-hex>`. There is no
caller-selected program, module roster, command, device endpoint or test runner.
An existing directory is refused, never overwritten or resumed.

The frozen report exposes `.payload`, `.sha256`, `.to_dict()` and
`.safe_summary()`. The report is strict canonical ASCII JSON without a newline,
at most 128 KiB. The verifier is pure and requires an independently trusted
original digest and assigned directory. A self-hash alone is not authentication.

## Fixed experiment

1. Run the existing on-volume Windows/NTFS startup qualification: real
   LockFileEx contention, write-through/flush/replacement and torn-tail handling.
2. Launch the fixed child through the existing Windows owned-process backend.
   The host base-Python executable, child source and two production modules are
   hash-pinned; the child uses `-I -S -B` and fixed namespace stubs. It does not
   import application initializers, site packages, pytest or device providers.
3. The child acquires CELL → SESSION → CAMERA → ARM_CONTROLLER. The parent
   observes actual original ACTIVE metadata and an actual live contender refusal.
4. A clean release and fresh parent acquisition retain exact ACTIVE → RELEASED →
   ACTIVE → RELEASED lineage. Every originally observed owner is retained.
5. A separate fixed child intentionally exits with code 73 while holding all
   four leases. Kernel process exit releases handles but does not rewrite ACTIVE
   metadata. A new contender receives `StaleLeaseOwnerError`; no repair is run.
6. A separately labeled controlled metadata fault combines the live parent's
   observed PID with the observed, now-dead child's process creation identity.
   It exercises PID/start mismatch refusal. **This is not observed OS PID reuse.**
7. Create a separate original, qualified NO_DEVICE_IO M1 experiment session.
   Its only stage change is workspace_sources → WAITING_OPERATOR. One retained
   campaign acknowledges its consumed permit and records actual CELL/SESSION
   owner identities, source, selected software-experiment identity and exact
   attempt hash. Same-owner invocation returns the cached result without work.
   A new runtime/coordinator refuses the old permit and the consumed request key.
   Exact five request/evidence/receipt/result records and before/after M1
   verification are retained; replay does not append an attempt or call a worker.

The Job has a one-process cap. Each child has a 15-second run and 2-second cleanup
budget, bounded input/output and memory; unresolved cleanup joins the existing
global owned-process hold. The collector has a 120-second original deadline,
which a supplied deadline may shorten. Stop and deadline checks surround bounded
file/M1 operations and progress callbacks; the existing synchronous filesystem
primitives are not falsely described as interruptible kernel calls. Source is
fingerprinted before and after the experiment. The fixed child receives no
native/device admission capability.

The process working directory is its fixed source directory, not the mutable
lease directory: the owned backend's strict read-only directory pins conflict
with Windows atomic lease-pointer replacement when applied directly to that
directory. The separate assigned experiment ancestry is instead held by the
existing M1-compatible directory guard (write sharing allowed, delete/rename
sharing denied), and actual M1/lease path and content checks remain in place.

## Report and failure semantics

`rocell.physical_ownership_qualification.v1` retains:

- `binding`: original workspace, assigned directory and source digest;
- `runtime`: exact executable/child paths and executable/child/two-module hashes;
- `started_at_ns`, `elapsed_ns`, original durability report;
- separate clean/crash process pipes and owner observations, plus labeled PID fault;
- original M1 identity, permit, full worker bytes, record filenames/documents and
  original verification projections;
- seven independently derived check rows, terminal error code/type, fixed
  residual obligations, zero device-effect counters and false authority flags.

Original owner filenames are deterministically derived from each retained
`lease_level` and `resource_sha256`. M1 record paths derive from the retained cell
descriptor and exact `records` filenames in its `physical-diagnostic-records`
directory. No raw inbox paths, device observations or caller-authored PASS
receipts are consumed.

`PhysicalOwnershipQualificationError.report` retains a valid historical report
when the failure occurs after report context preparation. Pre-entry rejection
may have no report because no experiment began. Completed earlier observations
survive Stop, source drift and callback failures. All created experiment/store
directories, including stale and partial records, remain. The collector never
retries, reconciles a stale lease, clears quarantine or deletes that history.

The compact summary schema is
`rocell.physical_ownership_qualification_summary.v1`. Its exact keys are
`schema, report_sha256, source_sha256, status, checks, residuals, device_effects,
physical_authority, hardware_qualified`. Status is `SOFTWARE_OWNERSHIP_COVERED`
only if all seven checks pass and no terminal error exists; otherwise `HELD`.
Checks contain `id, passed, provenance`, ordered by `CHECK_IDS` in the module.
Only the process-start fault is `CONTROLLED_FAULT_INJECTION`; the other checks
are `ACTUAL_HOST_MECHANISM`. Retained artifacts in unit fixtures are explicitly
modeled records, not actual qualification observations.

The fixed residuals remain:

- selected-device identity must be rechecked after each effectful lock;
- received-hardware HZ-012 residuals remain open;
- native runtime release requires its independent qualification.

## Verification evidence

The dedicated test module has 47 cases covering strict immutable records,
independent subject hashes, changed source/identity/record lineage, false numeric
aliases, raw byte counters, cleanup failures, partial retention, cancellation,
global process ownership and no effects during pure verification. Its real
Windows cases execute only the fixed incapable child and actual NTFS/M1
mechanisms, including Stop after READY. The workspace-source fingerprint is
explicitly modeled in those tests to isolate concurrent development edits;
process, file, lease, M1 consumption and readback are not mocked in the nominal
actual case. No physical camera, native metadata, serial, power or motion call
is made. A modeled covered report is approximately 62 KiB, depth 8; integrations
must measure their complete retained/export wrapper without truncation.
