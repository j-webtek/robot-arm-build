# One-lease memory and owned-arm rehearsal dispatch

`application/scoped_rehearsal_dispatch.py` removes repeated lease acquisition
from both memory-only and owned-arm rehearsal integration. It does **not** cache admission,
renew an envelope, increase a deadline, skip a storage audit or enable hardware.
The prior failed session is retained unchanged; this adapter is for a newly
requested operation, not replay or repair.

```python
with ScopedRehearsalDispatch(
    persistence=exact_m1_rehearsal_store,
    leases=(cell_lease, session_lease, arm_controller_lease),
    request=provisional_request,
) as window:
    tx = window.preflight_transaction
    admission = tx.read_admission(provisional_request)
    # Complete existing preflight. Issue the original fresh synthetic envelope
    # now, once. Do not extend or replace it after preparing the operation.
    request = replace(provisional_request,
                      expected_challenge_sha256=admission.challenge_sha256)
    window.bind_request(request)
    coordinator = CellCommissioningCoordinator(persistence=window, ...)
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit, cancellation=original_event)
```

Only the exact `M1CommissioningPersistence` rehearsal class, the two fixed
`rehearsal-arm-feedback` / `rehearsal-owned-arm-feedback` actions and CELL → SESSION → ARM_CONTROLLER lease
tuple are accepted. Construction/status are inert. Entering the window performs
one actual qualified M1 context acquisition; it retains the existing OS leases.
Preflight exposes the actual exact `M1RehearsalTransaction` to trusted internal
service code, not to browser input. That internal reference must not be reused
outside its preflight role.

`bind_request()` permits only the fresh challenge to differ from the provisional
request. It can run once. The coordinator receives a closed proxy whose admission
and envelope reads must use that exact bound request. All reads still reach M1.
The first coordinator context is prepare-only and cannot call mutation methods.
The second is execution; it forwards the existing intent, consumption, scoped
revalidation, evidence, transition and uncertainty methods unchanged. Nested,
cross-thread, substituted and third contexts are refused. Saved proxies stop
working when their own context ends.

The actual underlying context closes **inside the second coordinator context's
exit**, not later when the UI's outer `with` ends. Consequently an actual lease
exit failure still reaches the core's existing cleanup-failure hold. A known
durable attempt is not rewritten or retried to hide that cleanup uncertainty.
If preparation is abandoned or fails, the outer context closes the original
lease once. `ExitStack` ownership is detached before close, so a failed close is
never automatically retried. The adapter retains the cleanup cause and reports
`cleanup_uncertain` in its inert status.

This lease adapter does not change the existing 30-second synthetic envelope,
10-second memory campaign, 20-second owned campaign or post-arming full-lifetime test. The subsequent
versioned arm IPC increment separately binds a 5-second v2 child RELEASE wait;
historical v1 evidence keeps its 2-second bound. Neither version renews the
original envelope or campaign expiry. Fresh source,
identity, epoch, journal, evidence, qualification, quarantine and consumed-permit
checks remain the responsibility of their existing core/M1/application methods.

## Tests and measurement

```powershell
.venv/Scripts/python.exe -m pytest software/tests/unit/test_scoped_rehearsal_dispatch.py -q -s
```

The actual-M1 tests use new, small NTFS cells and an incapable modeled worker;
they do not run a child, open serial/camera devices or qualify stage12. A modeled
manual-energy category exercises the same ARM lease and original envelope
without any physical energy change. Tests count **one real context enter/exit**
and four unchanged fresh admission reads: preflight, preparation, execution and
the additional pre-intent revalidation. They also verify cancellation, changed
epochs before intent, and an injected exit error after actual lease cleanup.

Observed minimal-cell runs took approximately 0.67–1.13 seconds to enter the
real context and 0.26–0.53 seconds per fresh admission read. These are diagnostic
host measurements, not latency qualification for a full retained wizard session.
The full original-store integration must still demonstrate that its remaining
fresh checks and child admission fit the unchanged deadlines.

The two-action extension has 49 passing pure adapter tests and 10 passing
isolated actual-M1 cases (both actions: nominal, changed facts, cancellation,
lease-exit failure and preparation abandoned before execution). Those cases
keep the original envelope/worker budgets and one real acquisition/release.
See [the service integration checkpoint](FEEDBACK_SINGLE_WINDOW_IMPLEMENTATION.md)
for the distinct full-session acceptance result; minimal-store timings are not
proof of that larger workload or hardware readiness.
