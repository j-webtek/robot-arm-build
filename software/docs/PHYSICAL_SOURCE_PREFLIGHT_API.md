# Physical diagnostic source-file preflight

This is an actual local-file check, not a rehearsal report and not hardware
qualification. It can run before hardware arrives. It never enumerates devices,
launches the native camera helper, imports a native device DLL, opens serial, or
instructs an operator to change actuator power. There are no UI controls in this
module; the application owns explicit action preparation and durable publication.

## Public API

Module: `rocell.application.physical_source_preflight`.

```python
registration = source_preflight_registration(workspace)
worker = PhysicalSourcePreflightWorker(
    workspace,
    expected_source_sha256=current_software_fingerprint,
    worker_executable_sha256=registration.worker_executable_sha256,
    operator_id="operator-label",
)
execution = worker.run_retained_campaign(
    permit,
    deadline_ns=deadline,
    cancellation=cancellation_event,
    authorize_consumed_permit=persistence.revalidate_consumed_permit,
)
```

The constructor is inert. `source_preflight_registration` is an explicit,
read-only preparation step that hashes the one fixed worker source file. It
does not register or enable physical device access. The action ID is
`physical_source_preflight`; its stage is `workspace_sources`, effect class is
`NO_DEVICE_IO`, and resources are empty. Its fixed budget is 20 seconds,
96 KiB of returned evidence, and zero device opens/reads/writes/frames/closes.
The worker independently rechecks the exact registration and physical source
domain, then acknowledges the already-consumed permit before reading sources.
One worker instance can be attempted once; even rejected authorization consumes
its local one-use latch. `run_campaign` is deliberately refused: retained evidence
and the exact consumed-permit callback are required.

The result is a `RetainedCampaignExecution` containing one `CampaignEvidence`
and a typed `WorkerReceipt`. Its composition is
`PHYSICAL_DIAGNOSTIC_NO_DEVICE_IO`, effect certainty is known, all device counters
are zero, and final power is `UNKNOWN`. That final power is not a manufactured
observation of disconnection. The worker itself does not write M1 files or
advance any stage; the domain-specific coordinator and persistence do that.

## Actual checked scope

`SOURCE_PREFLIGHT_SCOPE` is the authoritative sorted list of 59 fixed relative
paths. It includes:

- The physical foundation, its six contracts, all nine ICD source bindings,
  and the static support's additional robot-reach screening source.
- Named current foundation, policy, ICD, support, camera-profile, hazard,
  physical persistence/coordinator, native camera runner/protocol, non-purging
  serial owner/adapter and file-check implementations.
- Separately: the owned native development build manifest, its exact ten
  C++/CMake source files, and its three declared build artifacts.

The report distinguishes that fixed closure from the existing wizard software
fingerprint. The latter binds software Python/UI/configuration sources,
`pyproject.toml`, and `rocell.ps1`; it is not a whole-repository, installed
dependency, hardware-build, native-release, or running-memory attestation.

Only the fixed native manifest source/artifact sets are accepted. Paths in a
modified manifest cannot expand the scope. The expected hashes in that local
development record are compared with actual bytes, not promoted into trusted
release pins. The historical metadata build is not silently reapproved.

Before semantic validation, all fixed files must be ordinary, single-link,
non-reparse files beneath the assigned local workspace. Fixed source files are
capped at 2 MiB each, native artifacts at 8 MiB each, and each complete fixed
snapshot at 32 MiB. The aggregate budget is checked before content reads. On
Windows the fixed files and ancestry remain pinned against writes/deletion/
rename while the existing source validators run. On portable hosts the report
explicitly records the weaker before/after-only boundary.

The worker compares fixed snapshots and the software fingerprint before and
after calling the existing real foundation validator. That validator checks the
source-bound authority, stage, epoch, hazard, ICD, accuracy, B0477 and static
support contracts. No virtual bootstrap, fake inventory, synthetic camera
probe, image detector or calibration fitter is called. The fixed closure pins
bound the legacy validators' path rereads; the broader software fingerprint is
a diagnostic source-drift check, not hostile-writer isolation.

Deadline and cancellation checks run at admission, between file operations,
after validators/fingerprints, and immediately before returning retained
evidence. The 20-second timeout is cooperative: it cannot preempt a stalled
in-process filesystem call. The coordinator must reject expired completion;
this is not a qualified device-process supervisor.

## Retained report and verification

`worker.report` is initially `None`. On completion it is an immutable
`PhysicalSourcePreflightReport` with `payload: bytes`, `sha256: str`, and
`safe_summary() -> dict`. The full strict versioned report retains file
hashes/sizes, before/after digests, the actual foundation result references,
native manifest comparisons, binding, checks, errors and standing holds.
The summary omits the full file list and never includes an absolute path or raw
file contents. `failed_source` is null or one fixed relative source name.

```python
verified = verify_physical_source_preflight(
    committed_evidence.payload,
    expected_source_sha256=session_workspace_source,
    expected_permit_sha256=committed_permit.permit_sha256,
    expected_worker_sha256=committed_permit.registration.worker_executable_sha256,
    expected_report_sha256=committed_evidence.payload_sha256,
)
```

Verification is pure and never rereads sources or reruns a validator. It checks
the exact schema, field types, canonical bytes, fixed scope and resource limits,
foundation/native references against retained source rows, recomputed
comparisons/checks/outcome, and the caller's expected source/permit/worker.
Always supply the optional `expected_report_sha256` from independently verified
M1 evidence when reviewing or reopening. Without a trusted retained digest,
schema/binding consistency alone does not authenticate a report's origin.
Current-source freshness requires a separate explicit source check.

## Coherent is not canonical PASS

The report outcome is only `FILE_CHECKS_COHERENT` or `HELD`. Missing/unreadable
fixed files retain `HELD`, `SOURCE_FILE_UNAVAILABLE`, and the fixed failed source
name; no partial inventory is presented as a complete snapshot. Source, contract,
manifest or worker drift remains held. Cancellation/deadline/authorization
failure produces no new report; persistence owns the conservative attempt result.

Even a coherent report always retains:

- `canonical_stage_pass: false` and `physical_authority: false`.
- `DISCONNECTED_REQUIRED_NOT_OBSERVED`: actual actuator power state is unknown.
- `HZ_012_CANONICAL_EVIDENCE_NOT_CLOSED`: file agreement does not establish the
  complete stage-1 concurrency, stale-owner, crash and device-identity evidence.
- Received camera/arm, static installation, driver/process qualification,
  canonical-stage completion and physical release holds.

Storage qualification is a separate real Windows NTFS property. Neither it nor
this report permits advancing the physical camera, power, feedback, motion,
calibration or contact workflow.

## Tests and integration ownership

`tests/unit/test_physical_source_preflight.py` uses actual copied fixed files and
the actual source validators. It tests strict permit/source-domain bounds,
missing/drifted/oversized/linked files, report tampering, cancellation, pure
verification and real Windows source write/rename exclusion. Its hand-built
typed permits are explicitly not M1 durability proof. Separate parent-owned
tests exercise the real physical diagnostic store and coordinator. No test in
this module performs device enumeration or connection.
