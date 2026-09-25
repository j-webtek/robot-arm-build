# Owned non-purging arm feedback runner

This development slice runs the **actual** `ArmFeedbackWorker` and
`NonPurgingArmFeedbackBackend` in a real, owned Windows child process. The only
dispatchable serial implementation is `IncapableWin32SerialApi`: a sealed
in-memory facade. It does not enumerate or open a COM device, load the native
serial DLL boundary, energize the arm, move it, or prove final power state.
The separate `OwnedArmFeedbackRunner` remains unconditionally physical-held.

## API and ownership

```python
runtime = prepare_owned_arm_runtime(workspace, assigned_package_parent)
prepared = prepare_owned_arm_feedback(
    runtime, inner_request,
    session_id=session_id,
    permit_sha256=consumed_permit_sha256,
    selected_identity_sha256=inner_request.controller.identity.identity_sha256,
    working_directory=server_assigned_empty_directory,
    scenario="nominal",
    deadline_ns=original_parent_deadline,
)
runner = IncapableOwnedArmFeedbackRunner(
    prepared, revalidate_consumed_permit=check_current_consumed_scope,
)
evidence = runner.run(cancellation=original_event, deadline_ns=original_parent_deadline)
```

Imports:

- `providers/windows/owned_arm_feedback_package.py`: `OwnedArmRuntime`,
  `prepare_owned_arm_runtime`, `revalidate_owned_arm_runtime`.
- `providers/windows/owned_arm_feedback_runner.py`: `PreparedOwnedArmFeedback`,
  `prepare_owned_arm_feedback`, both runner classes.
- `providers/windows/arm_owned_protocol.py` and `arm_owned_evidence.py`: strict
  peer-owned wire codecs and complete retained evidence/pure verification.

Runtime build is an **explicit file-only action**, before campaign admission.
Root assigns `software/runs/owned-arm-packages`; tests assign a temporary parent.
It creates a fresh `arm-runtime-UUID` directory with no overwrite/reuse, writes a
deterministic `runtime.zip`, and publishes `runtime.json` last. Partial failures
remain for diagnosis; there is no implicit repair, retry, or deletion.

`OwnedArmRuntime(payload)` reconstruction, `.to_dict()`, preparation, runner
construction and `.status()` are inert. Returned dictionaries are fresh copies.
The runtime document binds `workspace`, `workspace_source_sha256`,
`source_closure_sha256`, the exact roster, interpreter/child/archive pins, and
explicitly incapable development provenance. `runtime.runtime_sha256` hashes
the complete canonical descriptor. Deserialization is **not authentication**:
retained consumers must supply trusted expected operation/source/evidence hashes.

The pure preparation binds the complete runtime, inner request, session, permit,
selected controller identity, closed scenario, registration, cwd, budgets and
original deadline. It does not create the cwd or read the package. The application
must acknowledge the exact M1 permit once, then revalidate that same live consumed
scope at both callbacks—not redeem it twice. Callback must return `None` or raise.
It must compare the whole prepared snapshot, actual current source, original
deadline/cancellation, selected identity, energization envelope and live leases.
No browser-supplied executable, command, import root, archive roster or serial
backend enters this API.

## Exact runtime package

The explicit builder reads a closed roster of worker, non-purging backend,
protocol and complete evidence modules, plus a fixed Python-only `packaging`
dependency roster from the workspace `.venv`. These implementation files enter
the ZIP unchanged. Fixed inert namespace initializers isolate those modules from
the application's broad import-time re-export graph. Hashes of the original
namespace files are retained separately and the substitution is labeled
`FIXED_INERT_STUBS_ORIGINAL_HASHES_RETAINED`.

The archive uses sorted names, fixed timestamps/attributes and uncompressed
bounded entries. No arbitrary ZIP members are accepted. The supervisor reconstructs
the expected closed archive digest from current files and compares all file pins
before and after pinning. The child additionally verifies the archive members
against that fixed current source roster before importing them. It runs only the
fixed bootstrap via the exact base Python executable with `-I -S` and a minimal
owned environment. The Python/DLL dependency environment is not thereby physically
qualified or treated as a security sandbox.

Files are bounded regular single-link files; links, reparses, path aliases and
expanded pin budgets are refused. Windows directory ancestry is pinned while
publishing the package. The existing process owner pins executable, script,
archive and ancestry for the complete child lifetime. Hash checks alone are not
a replacement for those process pins or M1 durability qualification.

## Finite execution and admission

1. Check the one-use runner, exact original request/deadline, cancellation and
   shared active/unresolved-process holds. Physical composition stops here.
2. Revalidate the fixed runtime and empty cwd, then pin the owned process inputs.
   Repeat file/cwd checks and revalidate the consumed M1 scope.
3. Start the fixed child in a Job, passing one bounded request line while keeping
   inherited stdin open. It verifies the archive, parses the exact incapable
   request, and emits READY with its actual PID and unpredictable challenge.
4. Validate READY against the owned PID and request digest. Immediately at the
   second pipe-write boundary, check cancellation, original budgets and the same
   current consumed scope again. Send the exact challenge/permit-bound RELEASE.
5. Child requires exactly one RELEASE and EOF within its 5-second v2 admission
   window, with the full feedback/cleanup lifetime still available. Only then
   does it construct the sealed memory serial API and run the actual worker.
6. Retain both actual pipe streams and independently verify the full feedback
   and native-resource companion. Observe Job/tree/pipe cleanup separately.

The worker executes its existing one-shot T105 lifecycle: exact controller
identity checks, quiet-buffer observation, **one** fixed query, bounded T1051
parsing/timing and non-purging close. No extra queries, purge, flush, reset or
automatic retries are added. The protocol request allows at most 2,048 response
line bytes. Parent defaults are 20 seconds execution, 2 seconds cleanup, 64 KiB
stdin/stdout, 8 KiB stderr and one owned process. Parent run time reserves cleanup
inside its original deadline. Sampled handle limits remain sampled, not kernel
hard limits. Cleanup exceptions preserve the primary error. An uncertain process
owner is retained in-process under the same global admission lock as existing
camera/process runners, preventing pending-buffer loss or a second dispatch.

New runtime preparation and the child accept only `rocell.arm_owned_request.v2`
with its fixed 5,000 ms admission wait. Pure v1 evidence decoding preserves its
original 2,000 ms wait; it is not an execution fallback. The v2 increment permits
bounded live M1 revalidation at READY, but neither renews the original 30-second
envelope nor extends the 20-second campaign. Release still requires the full
5-second inner feedback budget and 2-second cleanup to fit the original deadline.
Native-camera admission is unchanged. Tests exercise actual fixed-child release
after a 3-second check and refusal after 5 seconds, without device access.

## Faults and truthful evidence

Closed scenarios are `nominal`, `boot-bytes`, `short-write`, `timeout`,
`identity-change`, `close-failure`, `malformed-response`, `extra-response`,
`child-timeout`, and `malformed-result`. None selects a physical serial backend.

`runner.owned_result` retains the actual process result even when native protocol
parsing fails. `ArmOwnedEvidence` retains raw READY/RELEASE, request, stdout/stderr,
the process report, and—only when actually received and valid—the complete
feedback and native companion. Exit code 0 / `FEEDBACK_RETAINED` means a valid
diagnostic result was serialized, **not** that the serial transaction succeeded.
For example, a valid response and failed serial close can coexist with clean
process exit. An owned process kill cannot establish port cleanup or power removal.

The final power state remains `UNKNOWN_REQUIRES_SEPARATE_OBSERVATION`. No stage
PASS, hardware identity, installed firmware, electrical acceptance or motion
authority is produced. Only `safe_summary()` belongs in the UI; full wire bytes
stay in the bounded private retained artifact. Pipe hashes describe retained
bytes; a pipe-limit failure does not claim a hash or length for unseen bytes.
The 128 KiB evidence bound is enforced without truncation. Outer application
envelopes must independently enforce their aggregate quota, including runtime
and binding documents, before publication.

## Focused verification

```powershell
.venv/Scripts/python.exe -m pytest software/tests/unit/test_owned_arm_feedback_runner.py -q
python -m mypy --follow-imports=silent --check-untyped-defs software/src/rocell/providers/windows/owned_arm_feedback_package.py software/src/rocell/providers/windows/owned_arm_feedback_runner.py software/src/rocell/providers/windows/_owned_arm_feedback_child.py
```

Tests execute only the fixed incapable child or injected no-OS owners. They cover
real nominal/fault worker execution, exact two-boundary admission, raw malformed
output, finite child timeout, cancellation, denied/replayed admission, package
drift/foreign members, inert reconstruction, nonempty cwd, separate process and
serial cleanup, and the shared unresolved-owner hold. No camera helper, metadata
inventory or physical serial endpoint is executed by this suite.
