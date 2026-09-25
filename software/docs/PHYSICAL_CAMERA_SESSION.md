# Original camera-only M1 session ownership

`application/physical_camera_session.py` supplies explicit initialization and
original-store refresh for the existing physical camera storage domain. It does
not connect a camera, query a device, launch a helper, execute a campaign, or
invent prerequisite, identity, hazard, epoch or runtime-release evidence.

## API and path binding

`PhysicalCameraSession(workspace, directory, *, launch_id, source_sha256,
cell_id, session_id)` is inert. Paths are canonical local absolute Windows paths.
The exact directory must be
`<workspace>/software/runs/physical-camera-acquisition/<launch_id>`; there is no
arbitrary browser path or automatic selection of another previous store.

The frozen descriptor has exactly `workspace`, `directory`, `launch_id`,
`source_sha256`, `cell_id` and `session_id`. Namespace requirements are
`wizard-<32 lower hex>`, `wizard-physical-camera-<16 lower hex>` and
`physical-camera-<32 lower hex>`. The source is the separately supplied current
workspace hash, bound through `physical_camera_source_binding` to this domain.

- `descriptor()` and `view()` return detached cached documents without I/O.
- `initialize(cancellation=Event, progress=callback)` is explicitly one-use,
  even if cancelled before creation. It creates a fresh assigned directory
  exclusively, qualifies existing Windows/NTFS M1 storage, and creates one
  `PHYSICAL_DIAGNOSTIC` session. All 15 canonical stages must be `PENDING`, with
  no journal events, evidence, camera records, attempts or quarantine records.
- `refresh(cancellation=Event, progress=callback)` opens only the original path.
  It audits V2 evidence/journal state and camera records under actual leases;
  it never initializes a missing suffix, repairs records, clears quarantine,
  replays actions, retries failed effects or passes a stage. A newly constructed
  owner can use explicit refresh to inspect its matching original store.
- `retained_verification()` returns a detached historical
  `{binding, verification, stages}` document, or `None`. This observation remains
  available after a late failure but is not promoted to a current usable store.

Initialization and refresh have an original 120-second monotonic deadline.
Stop, source and deadline checks occur around storage calls and immediately
before successful publication. A slow synchronous OS call cannot be forcibly
interrupted by this API; a late return is held, not reported as timely success.
Progress does not renew the budget. Concurrent operations are refused.

## Cached projection and failure semantics

The exact `rocell.physical_camera_session_view.v1` fields are:

`schema`, `binding`, `status`, `operation`, `verification`, `stages`, `error`,
`partial_store_possible`, `initialize_attempted`, `physical_authority`,
`device_io_performed`, `hardware_qualified`, `replay_allowed`.

The last four fields are always false. `operation` is null, `INITIALIZE` or
`REFRESH`. Status is `NOT_INITIALIZED`, `RUNNING`, `STORAGE_READY_PENDING`,
`REFRESHED_STORAGE_ONLY` or `HELD`. Verification is the existing bounded full
`M1RuntimeVerification.to_dict()`, not a new hardware-ready summary. Stages are
the existing canonical stage snapshots; a refresh preserves actual states and
never treats all stages as passed. Error is null or a fixed `{code, type}` pair;
exception messages and dynamically named external exception classes are not
projected. Verification and stages are cleared from the current view on failure.

The retained summary is at most 96 KiB. Current and historical nested data are
owned copies. The initial store path is never overwritten or deleted, including
after a partially completed initialization. `partial_store_possible` describes
possible original bytes, not successful qualification or automatic recoverability.
Explicit refresh may diagnose a partial store but cannot resume its creation.

## Restart prerequisite readback

After a successful explicit original-store refresh, call
`read_original_prerequisites(expected_header_sha256=..., cancellation=Event,
progress=callback, deadline_ns=None)`. The mandatory nonzero header SHA is the
independently selected immutable header from the original-store registry; it
must not be learned from a substituted path during readback. It is checked
against fresh storage verification, the stage-lease snapshot and post-lease
verification. Original source, session and origin launch remain unchanged.

The method uses exact CELL + SESSION leases and makes no stage mutation. It
selects only WORKSPACE_SOURCES evidence with the exact original producer label
`camera-prerequisites-requirements-only`; unrelated labels and other stages are
not treated as prerequisite documents. The content-addressed manifest is read
under its original directory guard and compared with the snapshot's manifest
hash. Matching JSON payloads are read through `read_stage_evidence`, then passed
to the strict pure prerequisite verifier with original source/session/launch
and the independently retained payload hash. A wrong media type, malformed or
unverifiable matching document, or multiple matching references holds the
session. It never recollects missing documents. `None` means no matching original
document was present in the verified inventory, not that prerequisites passed.

Before document loads it caps relevant stage references at 32 and declared
aggregate payload bytes at 4 MiB; each manifest is bounded to 16 KiB and a
matching prerequisite payload to the existing 112 KiB ceiling. Existing M1
snapshot/audit readers retain their own global file/inventory bounds. The
returned record is at most 128 KiB, with exactly `document`, `evidence_sha256`,
`retention: M1_FULL_BYTES_READ_BACK` and `reference`. Storage and stage snapshots
are audited after the read, and fresh post-lease header/head/inventory/attempt/
quarantine coherence is required before the cached view becomes current.

The readback has its own original 120-second maximum. An external monotonic
deadline may shorten this budget, never renew it; an outer reopen action should
pass its original deadline. Stop/source/time checks occur before and after
storage reads and before current publication. View schema stays unchanged;
readback uses `operation: REFRESH` and ends `REFRESHED_STORAGE_ONLY` or `HELD`.

`retained_prerequisites()` is an inert detached historical accessor. Complete
verified bytes are saved before any later Stop, source/coherence failure,
progress exception or guard/lease-exit failure. That historical record survives
a held current view for diagnostic export; it does not authenticate current
metadata selection, assign a new origin launch, approve a stage, or grant
camera permission. A new application service must separately withhold old
metadata/configuration/frame projections and review current prerequisites.

## Stage-only evidence integration

After a successful current open,
`stage_transaction(expected_challenge_sha256=...)` yields the exact existing
`M1PhysicalCameraTransaction` under CELL + SESSION leases. The current source,
challenge and original records are checked; no CAMERA lease or admission facts
are supplied. The owner's camera facts callback always rejects with
`TRUSTED_CAMERA_ADMISSION_FACTS_REQUIRED`. Storage qualification is not device
permission. Scope exit invalidates the cached current store and requires an
explicit refresh before another stage transaction.

The narrow `M1PhysicalCameraTransaction.read_stage_evidence(reference)` method
returns original payload bytes only for an exact typed reference in a fresh
verified original session snapshot, in an active stage-only scope. It pins the
content-addressed package ancestry, checks the exact manifest/file set and
session binding, bounds the regular payload read by the trusted payload length,
compares actual byte length/SHA, then verifies the package and scope again.
It accepts no arbitrary path, cannot read during a CAMERA acquisition scope,
and does not substantively approve the payload it returns.

Existing V2 ordering remains unchanged: evidence can be stored only for the
active `WAITING_OPERATOR` or `REVIEW_PENDING` stage, not `PENDING`. A service can
enter `WAITING_OPERATOR`, retain its actual report, read it back and apply its
strict report verifier under the same stage lease before requesting review.
This method does not grant `PASS` or bypass the review policy.

## Tests and remaining qualifications

`test_physical_camera_session.py` exercises pure construction/view, exact path
binding, bounded error projection, Stop/source/deadline failures, one-use and
concurrent action handling, actual isolated NTFS initialization/original reopen,
partial-store retention, record tampering and post-audit head mismatch.
`test_camera_stage_evidence_readback.py` uses actual isolated NTFS stores and
leases for exact byte readback, changed references, ended/device scopes, file
and manifest changes, extra members, hardlinks and post-read ownership checks.
Test sources and retained payloads are explicitly incapable fixtures. No native
helper, camera, serial or metadata process is invoked.

`test_physical_camera_session_readback.py` adds bounded injected scope tests and
an actual new-owner NTFS reopen/readback of the original immutable prerequisite
document, preserving the stage journal, attempt/quarantine heads and inventory.
It covers missing/unrelated/ambiguous/malformed packages, expected header and
origin binding, pre-read budgets and historical retention after late failures.

This is storage onboarding, not camera or driver qualification, native process
release, calibration, power verification, arm motion or physical readiness.
The outer service remains responsible for trusted report review and for not
publishing a current session after its own late Stop/source/log failure.
