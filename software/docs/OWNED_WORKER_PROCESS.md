# Owned Windows worker process boundary

Status: implemented and tested with explicitly incapable child processes on
this Windows host. **No physical camera or serial worker is dispatchable.**
This is a bounded DEV-003 / ARM-IPC-02 component, not completion of the physical
process harness, durable authority channel, or received-device qualification.

## Files and API

- `providers/windows/owned_worker_process.py`: pure registration/request models,
  strict bounded JSON, one-use admission, supervision and diagnostic receipt.
- `providers/windows/_owned_worker_win32.py`: private explicit Win32 resource
  owner. No import-time DLL load, process creation, enumeration or device access.
- `providers/windows/_owned_process_fixture.py`: fixed incapable test child;
  no camera/serial imports and no arbitrary command or executable input.
- `tests/unit/test_owned_worker_process.py` and
  `tests/fixtures/owned_process_parent.py`: pure faults and actual owned-process
  tests, including parent death. All file mutations use temporary fixtures.

The public entry is:

```python
worker = OwnedWindowsWorker(
    server_registration,
    authorizer=reviewed_parent_authorizer,
)
status = worker.status()  # Cached/inert; no launch, file read, DLL or device call.
result = worker.run(
    exact_request,
    cancellation=cancel_event,
    deadline_ns=parent_deadline_ns,
)
safe_projection = result.to_dict()
```

`PinnedWorkerFile` records an exact local path, SHA-256 and file-size ceiling.
`WorkerProcessRegistration` binds the executable, fixed argv, package-file pins,
working directory, composition, request/result schemas and all process budgets.
`OwnedWorkerRequest` binds attempt, session, source, operation, selected identity,
expiration and bounded JSON payload. The emitted request hash also covers the
complete registration, not just payload bytes. Response schema, attempt and
request hash must match exactly; unknown fields and coerced booleans are refused.

The mandatory external authorizer receives `(registration, request,
request_sha256)` and must consume the exact parent-held authority, returning
`None` or raising. A return Boolean is not authorization. The current fixture
acknowledgement has no durable or physical authority. No leases, permits,
controller identity or device authority are manufactured by this module.

Every object accepts one `run`, even after denial or cancellation. A process-wide
nonblocking reservation prevents overlapping owners. Uncertain cleanup retains
one owner strongly, including pending I/O buffers, unclosed raw handles and
failed file streams, and blocks further dispatch. There is no retry, reset or
public clear-hold method. Parent-level durable reconciliation remains necessary
across process/app restart; this in-memory hold is not its replacement.

## Implemented process and file ownership

Before launch, the executable/package bytes are hashed with at most 1 MiB read
blocks under single-link regular-file handles denying write/delete sharing.
At most 128 unique ancestor directories are checked and held with
`GENERIC_READ`, read-only sharing, backup semantics and open-reparse-point flags.
Handle identity must agree with the checked directory. The exact application
name and fixed argv are passed to `CreateProcessW`; no shell, PATH search,
arbitrary module, browser path, or inherited environment secrets are used.
Only `SystemRoot` is passed in the explicit child environment.

The Job is created and configured before the child. Windows 10+
`PROC_THREAD_ATTRIBUTE_JOB_LIST` assigns it during process creation, avoiding
the create-suspended/assign-later orphan window. A separate explicit inherited
handle list contains only the three standard pipe handles; the Job handle is
non-inheritable. The initial thread is suspended until Job membership and the
current cancellation/deadline boundary are checked. Unsupported Job attributes,
containment refusal or nested-Job restrictions fail closed with no fallback.
[Microsoft Job-list and handle-list contract](https://learn.microsoft.com/en-us/windows/desktop/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
[atomic assignment rationale](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812).

The Job enables kill-on-last-handle-close, active-process and committed-memory
limits, with neither breakaway flag enabled. Termination uses the owned Job,
never a PID or a name match. Process-handle signaling and bounded Job membership
observations establish tree exit. A 100 ms post-root-exit accounting/drain window
fits inside the unchanged campaign deadline; a lingering descendant is then a
failed campaign. Observed associated-process counts can briefly include rejected
creation attempts before Windows finishes termination; they are not a count of
successfully running provider lifecycles.
[Microsoft Job ownership](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[Job limit semantics](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information),
[committed-memory limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).

Only stdin uses a private remote-rejecting named pipe with overlapped writes.
A child that never reads therefore cannot block the supervisor in a synchronous
stdin write. Stdout/stderr are polled and read in bounded available-byte chunks;
their excess byte triggers failure while retaining only a capped prefix.
Cancellation requests `CancelIoEx`, terminates the owned Job where necessary,
and independently observes I/O completion. A pending `OVERLAPPED` and its buffer
are never freed merely because cancellation was requested.
[overlapped completion contract](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-getoverlappedresult),
[cancellation is not completion](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex).

## Exact bounds and known limits

| Resource | Default / hard ceiling |
| --- | --- |
| Run / cleanup time | 5 s / 2 s; allowed maxima 60 s / 5 s |
| Stdin | 64 KiB, including the complete bound request envelope |
| Retained stdout / stderr | 256 KiB / 64 KiB |
| Associated processes | 4 maximum, kernel-enforced creation policy |
| Committed memory | 256 MiB/process, 512 MiB/job; configurable finite maxima 1/2 GiB |
| Child handle threshold | 512/process default, sampled; not a kernel hard limit |
| Parent ownership | <=128 unique directory pins, <=9 file pins, and a fixed finite set of Job/process/pipe/event handles |
| JSON | <=4096 nodes, <=16 nested levels; duplicate/nonfinite/unknown-envelope fields rejected |

The request expiration must fit run and cleanup before admission. Cancellation
and time are checked before launch/resume, after every poll and before result
acceptance. A late cleanup return is separately `CLEANUP_DEADLINE_EXCEEDED`, even
when the backend says it closed successfully. An original failure is retained
alongside cleanup exceptions, pipe uncertainty and final-deadline failure.

Win32 Job objects have no general hard per-process handle-count quota here;
sampling detects excess only after it exists. Synchronous OS calls, executable
hash reads and close calls cannot be forcibly interrupted by this Python
supervisor. These constraints remain explicit physical-qualification blockers.
Unrelated parent components must also use safe explicit handle inheritance;
this module cannot control another component's broad inheritable-handle launch.
Jobs are not a security sandbox against a hostile worker, administrator, brokered
process creation, or an unqualified DLL/interpreter dependency graph.

Only the exact installed base Python executable, fixed isolated `-I -S` fixture
files and closed scenario lists can execute through the current public runner.
The additional [contained camera fixture codec](OWNED_CAMERA_FIXTURE_RUNNER.md)
joins the unchanged camera client's exact prepared request to this boundary.
It consumes pinned source-derived templates and writes actual finite YUY2
artifacts; its camera identity, timestamps and device counters remain synthetic.
The [application join](WIZARD_OWNED_CAMERA_INTEGRATION.md) acknowledges a consumed
M1 rehearsal permit once, then validates that same attempt after process-file
pinning. It is not physical child redemption or native helper qualification.
`PHYSICAL_UNQUALIFIED` registrations are rejected before DLL/backend creation
or external authority redemption. Real camera/arm adapters remain unchanged.
To integrate them later, review closed provider codecs, pinned dependency/build
identity, one-use child redemption under parent-held M1 leases, raw-evidence
retention, cancellation/cleanup behavior and native qualification separately.
Do not remove the physical hold or add a runtime bypass because tests pass.

`OwnedWorkerResult` distinguishes process creation/resume, tree exit, retained
stdout/stderr prefixes, parsed diagnostic result, primary error and cleanup
errors. `to_dict()` omits raw pipe bytes and always reports no physical authority,
no device-close proof, unqualified physical provider and unknown final power.
Process death cannot prove serial close, camera shutdown, stopped motion,
controller reset safety or servo de-energization.

## Test command and acceptance scope

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_owned_worker_process.py -q
```

Tests cover repeated nominal real processes; strict JSON; inert and denied
admission; source-hash and ancestry pin checks; containment refusal; cancellation
before resume; bounded floods, stalled stdin and deadlines; memory/process/handle
limits; attempted breakaway and lingering descendants; parent death; one-use
and two-owner admission; and primary-error preservation across cleanup failures.
Pure fault injections verify late final polls, late cleanup, failed stream
ownership and a root-exit/accounting race. No camera enumeration/activation,
serial open, native arm/camera helper, M1 physical run, power event or motion
command occurs. Full ARM-IPC-02 durable redemption and received-device electrical
qualification remain unimplemented and held.
