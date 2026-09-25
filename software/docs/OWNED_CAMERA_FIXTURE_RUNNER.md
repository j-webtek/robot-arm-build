# Contained prepared-camera fixture runner

This is a software-only connection between the existing prepared-camera client,
owned Windows Job process boundary and native-shaped probe/capture receipts. It never
runs the native camera executable, enumerates devices or loads camera/serial
libraries. Physical registrations remain rejected before backend creation or
authority redemption. This is not camera/driver or durable physical-child
admission qualification.

## Public API

`providers/windows/owned_camera_runner.py` exposes:

```python
prepared = prepare_owned_camera_fixture(
    plan,  # exact PreparedCameraCampaign from the unchanged camera client
    session_id=session_id,
    operation_sha256=operation_sha256,
    selected_identity_sha256=selected_identity_sha256,
    expires_at_ns=parent_deadline_ns,
    templates=templates,          # tuple[PinnedWorkerFile], empty for probe
    executable=base_python_pin,  # exact sys._base_executable, reviewed hash
    fixture_script=script_pin,   # exact CAMERA_FIXTURE_PATH, reviewed hash
    working_directory=probe_dir, # required for probe; omit for existing capture
    scenario="nominal",
    budget=process_budget,
)
runner = OwnedPreparedCameraRunner(
    prepared,
    cancellation=cancellation,
    deadline_ns=parent_deadline_ns,
    authorize_owned=validate_same_consumed_permit,
)
```

Preparation and runner construction perform no filesystem operations. The
immutable preparation owns canonical bytes; `.registration`, `.request` and
`.plan` return fresh typed snapshots. `prepared.request_sha256(deadline_ns)` and
`runner.expected_request_sha256` use the exact same pure input-body builder as
actual owned-process dispatch. The request's campaign ID is the attempt ID.

For capture, omit `working_directory` or supply exactly the request's output
directory. For probe, supply a new, empty, server-assigned absolute directory;
the native-shaped probe request itself still has no output directory, mode or
controls. Preparation creates neither directory nor files. The probe working
directory is bound in the owned request and pinned before admission, even though
the probe writes no frame files. Probe templates must be empty.

Configure `WindowsCameraWorkerClient(CAMERA_FIXTURE_PATH, script_pin.sha256,
runner=runner)` and call its existing `probe(..., authorize=...)` or
`capture(..., authorize=...)`. The camera
authorizer must compare the complete exact `CameraActivationRequest` with the
reviewed, already acknowledged attempt. The owned authorizer validates that
**same consumed permit** and exact registration/request/digest after file pins
and before process creation/resume. Neither callback issues authority here;
do not redeem twice or substitute a no-op authorizer.

The runner accepts only the exact prepared native-shaped argument tuple,
existing client timeout (`duration_ms / 1000 + 5`) and 256 KiB IPC ceiling. It
is consumed even by an invalid call. No arbitrary command, script, scenario,
codec callable or public execute-prepared interface exists.

## Closed process and artifact contract

The only additional process command is the exact base Python executable with
`-I -S CAMERA_FIXTURE_PATH <closed-scenario>`. The native-shaped argv travels
inside a hashed stdin envelope; it is never executed. Existing generic process
fixtures keep their original allowlist and v1 protocol.

Empty-control capture retains this exact original v1 schema family:

- `rocell.owned_camera_fixture_request.v1`: existing owned envelope fields,
  including source, session, attempt, operation, selected identity, registration
  hash and both monotonic lifetime limits.
- `rocell.owned_camera_fixture_payload.v1`: exact provenance, scenario, full
  camera request, native-shaped arguments and ordered template pin records.
- `rocell.owned_camera_fixture_result.v1`: exact owned request hash and attempt,
  `physical_authority: false`, plus `fixture_result` containing scenario,
  provenance, complete camera-request hash, ordered template hashes and complete
  `native_receipt` (`rocell.windows_camera.v1`).

Probe and nonempty-control capture use the explicit corresponding `.v2` request,
payload and result schemas. The payload adds exactly `working_directory`; the
outer result field shape and unchanged native v1 receipt remain the same. Mixed
versions are rejected. No-control capture cannot silently migrate to v2, and v1
cannot accept probe or controls. `CONFIG_REQUEST_SCHEMA`, `CONFIG_PAYLOAD_SCHEMA`
and `CONFIG_RESULT_SCHEMA` expose these constants in `owned_camera_codec.py`.

Provenance is always `INCAPABLE_CAMERA_PROCESS_FIXTURE`. Native source counters
and media timestamps are explicitly modeled. Host frame completion uses Python
`perf_counter_ns` at a stated 1 GHz scale, **not** a claimed raw native QPC or
sensor timestamp. The retained native limitations say so. No received-camera
UVC capability, autofocus, real source open or received-unit identity is inferred.

## Modeled probe and electronic settings

A probe returns only the fixed 5472 × 3648 YUY2 mode at 9/1 fps and six explicitly
synthetic control descriptors. `fixture_control_observations()` returns fresh
native-shaped dictionaries; it performs no I/O. Their unit is always
`MODELED_INTEGER_DRIVER_UNITS_NOT_RECEIVED_HARDWARE`, not inferred seconds,
Kelvin or the purchased camera's driver units.

| ID | Minimum | Maximum | Step | Default | Supported modes |
| --- | ---: | ---: | ---: | ---: | --- |
| exposure | -13 | -1 | 1 | -6 | auto, manual |
| gain | 0 | 255 | 1 | 16 | manual |
| white_balance | 2800 | 6500 | 100 | 4500 | auto, manual |
| brightness | -64 | 64 | 1 | 0 | manual |
| contrast | 0 | 100 | 1 | 50 | manual |
| saturation | 0 | 100 | 1 | 50 | manual |

Requested settings must use unique supported IDs and exact integer values on
the reported range/step, with a supported mode. Observation flags are strictly
1 for auto or 2 for manual; 3 is a capability combination, not an accepted active
mode. Manual readback must equal the requested value. The fixture deliberately
uses the modeled default as auto readback, demonstrating that enabling auto does
not promise a fixed numeric setting. All six observations are retained, including
settings not changed in this campaign. Probe defaults are manual.

These settings model configuration and readback state only. They do not alter
the template pixels or simulate optical exposure, focus or white balance. Lens
focus/aperture, actual hardware controls and physical optical acceptance remain
separate, unqualified work.

Probe uses zero templates, samples, frames and control writes. Its native
source-open/shutdown counters are modeled once each. The recommended probe
budgets are native 5000 ms, supervisor 10000 ms, cleanup 2000 ms; use an explicit
`WorkerProcessBudget` because the preparer's 25000 ms default remains for the
existing capture path. The legacy camera request budget fields must remain
`max_frames=1` and `max_frame_bytes=max_total_bytes=39_923_712` but are unused by
probe: they do not authorize frame output. Coordinator byte/frame effects are
still zero for that operation.

## Capture bytes and budgets

Each of 1–4 distinct templates is exactly 2736 × 1824 GRAY8 (4,990,464 bytes),
already limited to luma 16–235. The parent pins the executable, fixture script,
templates and all relevant directory ancestors. Output is exactly the pinned
working directory. The child verifies complete template hashes, byte lengths,
luma bounds and empty assigned output before producing files. Templates must
be outside that output directory. Fixed 2× nearest expansion writes 5472 ×
3648 YUY2, 10,944-byte positive stride, 39,923,712 bytes per frame, modeled 9/1
fps, no padding or rotation. Expansion adds no optical detail.

Frames use exclusive `frame-000000.yuy2` creation, bounded row buffers and
flush/fsync. No raw frames enter JSON/base64 or stdout. Partial files survive
failure for explicit later review; the child never repairs, deletes or retries.
Capture byte quotas are exact. Parent dataset retention/preview quotas remain
separate and must reserve additional disk space.

Default budgets are native 20 seconds (assigned in the camera plan), process
25 seconds, cleanup 2 seconds, stdin 64 KiB, stdout 32 KiB and stderr 8 KiB. The
supervisor run budget must exceed the native duration and be no more than five
seconds longer; both fit the owned 60-second maximum and caller lifetime. Small
valid budgets are available for fault tests. The aggregate pipe budget cannot
exceed the existing native client's 256 KiB ceiling. Output prefixes after a
cap are retained as incomplete diagnostics, never relabeled complete JSON.

Both operations accept `nominal`, `identity-mismatch`, `cleanup-uncertain`,
`child-timeout`, and `malformed-result`. Configured capture additionally accepts
`control-readback-drift`: a valid stepped manual value or an auto/manual flag is
changed intentionally, causing the unchanged native client to reject settings
readback while the complete raw outer packet remains retained. This fault is
rejected for probe and no-control capture. Only the intentional timeout scenario
ignores its own completion deadline, so the parent Job must terminate it.

## Acceptance and retained evidence

Always inspect and retain `runner.owned_result`, including when the camera
client raises. Its immutable raw stdout/stderr and defensive parsed projection
are not silently discarded. A complete valid native FAILED receipt is retained
with owned `WORKER_EXIT_FAILED`; the unchanged camera client can return that
failed receipt with unconfirmed modeled source cleanup. A wrong endpoint remains
in the bound outer packet but fails the client's independent identity check.

Process cleanup failure or missing tree-exit proof after creation blocks a
normal native result, even when its inner packet says OK. Cancellation and
deadline statuses remain explicit. Process termination is not proof of camera
shutdown, serial close, stopped motion or final power. The current Job design's
synchronous-call, dependency graph and sampled handle-limit qualifications
remain held as described in `OWNED_WORKER_PROCESS.md`.

Only pass a fully verified receipt plus the exact request into existing capture
ingestion using `INCAPABLE_NATIVE_FIXTURE`. Durable M1 receipt retention, known
seal accounting, separate final-power evidence and UI review are caller
responsibilities, not a PASS granted by this adapter.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_owned_camera_runner.py software/tests/unit/test_owned_worker_process.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_owned_camera_configuration.py -q
```

The suite uses pure adversarial contracts and only the fixed incapable child for
real processes. It covers one/four native-size frames, exact client/request and
shared admission hashes, template/output drift, directory pins, no-overwrite,
inert construction, physical/protocol denial, cancellation before creation,
bounded pipes, timeouts and tree cleanup, raw failure retention, native cleanup
versus process cleanup, invalid luma and immutable projections. No native camera
helper or device inventory is run. The configuration tests also run actual
incapable probe and controlled native-size capture, manual/auto drift, no-frame
probe failures, descriptor isolation, version rejection and probe-directory pin
denial. Broader camera-client tests remain unchanged. None of these tests closes
the physical helper filesystem TOCTOU, received driver or owned physical-worker
qualification holds.
