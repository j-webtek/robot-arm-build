# Scoped M1 → incapable native admission integration

`application/incapable_native_admission_campaign.py` supplies the application-side
join between real scoped commissioning authority and the fixed, camera-incapable
Windows admission child. This is a stage-1 `NO_DEVICE_IO` diagnostic, not evidence
that the camera-mode stage passed, a real device connected, or hardware is ready.
It never constructs a physical-dispatch runner or approves native runtime pins.

```python
worker = IncapableNativeAdmissionCampaign(
    source_workspace, assigned_parent_directory,
    source_sha256=current_workspace_source_hash,
    selected_camera=incapable_native_admission_identity(),
)
registration = worker.registration()
coordinator = CellCommissioningCoordinator(
    persistence=qualified_rehearsal_m1,
    registrations=(registration,),
    workers={registration.worker_id: worker},
    retained_campaign_actions=(registration.action_id,),
    scoped_campaign_actions=(registration.action_id,),
)
```

The constructor/plan/registration are inert. The identity producer returns a
closed synthetic endpoint document; real endpoints and alternative provenance
are rejected. The registration binds source, selected identity, assigned parent
directory, complete finite plan and the fixed incapable executable hash. Device
open/read/write/frame/close budgets are all zero. The 20-second campaign must fit
the coordinator's original 30-second permit lifetime; the native admission
protocol still has its unmodified 2-second child release deadline.

Only `run_scoped_campaign` is supported. The coordinator owns the exact permit,
original deadline/cancellation event and original CELL/SESSION leases. Its closed
invocation is the trusted source of those arguments; the worker does not create
another authority object or accept a browser-provided context. After durable
arming, the worker verifies full permit/registration/source/identity equality and
calls `ConsumedCommissioningScope.acknowledge` exactly once. It then creates one
new assigned attempt directory without overwrite.

The worker constructs a dormant logical native probe request and the separate
fixed incapable process registration. These are different executable identities:
the native helper pins describe an unexecuted, unapproved logical request, while
only `rocell_camera_admission_entry_tests.exe` is dispatched by the closed runner.
The resulting evidence retains both bindings explicitly; neither is relabeled
as actual native camera observation.

After process-file pinning and again at the final RELEASE boundary, the callback
compares the complete prepared request, captured full permit, selected endpoint
and identity hash, original working directory, process registration and budgets.
It reads the current workspace source hash, calls the real
`authorization.revalidate(permit)` and rechecks current source/time/cancellation.
Revalidation audits the committed armed attempt and current facts under the
existing leases. It never acknowledges/consumes twice or extends a deadline.

The full immutable `OwnedNativeCameraRunEvidence` is returned as one bounded
`CampaignEvidence` object. The rehearsal `WorkerReceipt` has zero device effects,
unknown physical power, no physical authority and no native receipt claim.
Process cleanup is reported separately. Only a complete admission-only result
with confirmed process cleanup can be technically known; all other returned
results remain uncertain. The coordinator owns publication and sealing and must
not treat a known diagnostic as canonical stage acceptance.

## Verified integration

`test_incapable_native_admission_campaign.py` contains five pure constructor/
closed-input tests plus one explicit `slow` integration test. The latter creates
a real local NTFS-qualified M1 rehearsal cell/session, commits stage 1 to
`WAITING_OPERATOR`, uses actual scoped acknowledgement and read-only
revalidation, launches the fixed incapable C++ child through the real owned
Windows pipes/Job, and verifies complete evidence after durable retention.

To isolate this test from unrelated concurrent UI development, it copies the
complete real registered source/configuration closure. The source fingerprint
must match before copying, after copying and in the isolated destination. It
does not inject a constant source hash, mock M1 publication or replace the child
runner. The child has separate fixed native source/binary pins. The test's source
closure is historical test evidence, not a claim that later workspace edits were
tested.

The executed test passed with the diagnostic `SEALED_KNOWN`, all leases released,
no unresolved/uncertain attempts, exact full evidence re-read and verified, and
stage 1 still `WAITING_OPERATOR`. Re-executing the exact request returned its
retained result without replay. Six tests passed in 15.63 seconds; the new source
passed mypy. No device-capable helper, metadata enumeration, camera, serial port
or arm was accessed. Runtime latency observed in this minimal test is not a
qualification for larger evidence trees or received hardware/driver behavior.

Related contracts: `OWNED_NATIVE_CAMERA_RUNNER.md`, `NATIVE_CAMERA_ADMISSION.md`
and the coordinator's `ConsumedCommissioningScope`. Native activation, camera
capability qualification and all physical motion remain held.
