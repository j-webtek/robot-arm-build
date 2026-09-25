# r31 local-step board candidate — offline review

## Status

Current status: **installed and tested**. See [live result](R31_LIVE_LOCAL_STEP_RESULT.md).
One target packet produced measured shoulder movement but missed the endpoint
criterion; same-boot read-only fault settling and exports completed. No retry.
The release-preparation checkpoints below are retained as historical evidence.

Frozen and successfully compiled for the ESP32 default 4 MB/no-PSRAM profile.
Offline artifact review passed. Not installed; installed r29 is unchanged.
No hardware connection, startup or movement occurred in this checkpoint.

## Board interface

Build selection: `ROCELL_LOCAL_SHOULDER_STEP`.

- `POST /rocell/local-step/prepare`: reserve exclusive ownership, load the existing
  private key, allocate owners, return the nonce/boot/time challenge. The handler
  sends no servo commands; subsequent same-task polling begins read-only capture.
- `GET /rocell/local-step/status` and `/record`: return retained status/evidence.
- `POST /rocell/local-step/receipt`: accept a signed durable-export receipt.
- `POST /rocell/local-step/authorize`: verify the exact local-step signed plan.
- Existing `/rocell/shoulder-settling/*` routes attach only to this faulted parent.

No `/rocell/shoulder-session/start` route is compiled into this selected image.
No generic arbitrary-target, home, torque-off or retry route was added.

## Memory checks

Preparation checks free heap against both owner object sizes plus 32,768 bytes,
and the largest available block against the larger individual allocation. It
checks free heap again after allocation. Rejection leaves no active owners; a
partially reserved setup is not automatically released to another dispatcher.

Large reference/authorization buffers are owner members allocated off the control
task stack. Transport token storage is a global route-object member. The 32 KiB
reserve is an explicit candidate policy, not measured proof that all runtime
allocation peaks fit. ESP32 runtime heap/stack behavior still needs observation.

## Reproducible exports

Under `software/runs/wizard-exports/`:

- Stage: `wizard-20260919T230730144501Z-e9e844c39827420a8fb99c08c7414e82`
- Compile: `wizard-20260919T230936882184Z-326af6c41c454280821a58dd32f1e6c4`
- Review: `wizard-20260919T230957322878Z-6f34bf866bef4865b33f91f01e03ecea`

App SHA-256: `e8400d1c302a70bed3283c4102fa6b202785c1ea35826de2e98754a09b80fae3`.
Size 1,150,592 bytes, offset `0x10000`, slot `0x140000`, headroom 160,128 bytes.
Bootloader and partition hashes match r29/r30. Review checked 236 relevant static
frames; largest individual frame 1,040 bytes. This is not a total-stack bound.
Current-device bytes and runtime resources were not checked by the offline review.

Validation: 88 board tests passed (including opt-in local build and low-memory/
fragmentation rejection); another 21 native integration/authentication/route tests
passed. These are focused, overlapping project coverage—not hardware validation.

## Next release work

1. Completed offline: host workflow and independent local-step event review.
   See the host integration checkpoint below. Live execution remains disabled.
2. Completed in software: reviewed app hash, installation evidence, startup boot,
   fresh idle capture and transport binding. Actual installation/startup evidence
   must still be acquired; see the release-binding checkpoint below.
3. Complete release checks, install app-only preserving settings/credentials, and
   observe diagnostic-only startup. No automatic home or torque changes.
4. Acquire fresh state through the interface. If inside the explicit local
   envelope, admit one bounded upward step; otherwise export the changed pose and
   replan. Do not use historical position values as fresh observations.
5. Export arrival or fault plus settling, and review before any further movement.

The prior intermittent export failure remains recorded in the settling plan.
Later suites passed, but no unsupported claim of its root cause or fix is made.

## Host integration checkpoint

`local_shoulder_step_runner.py` now orchestrates prepare, three reference captures,
signed authorization, export receipts and terminal review. Its independent
`local_shoulder_step_review.py` checks record order, identity, timestamps, goals,
actual positions, neighboring joints and three qualifying arrival observations.
Raw records are retained before independent review, including rejected feedback.
Fault settling can finish successfully while the parent movement remains STOPPED.
The runner does not issue a retry, return, home or torque command.

The HTTP adapter requires an explicit local-step capability for these routes;
larger authorization payloads are allowed only on the local authorization route.
The runner rejects DEVICE_CAPTURE and the live HTTP adapter pending release
binding, before attempting transport.

Validation command:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_shoulder_session_http.py software/tests/unit/test_local_shoulder_step_runner.py software/tests/unit/test_local_shoulder_step_session.py -q
```

Result: **24 passed in 29.61 seconds**. Cases include successful arrival, short
arrival, neighbor drift, changed prewrite pose, malformed feedback, premature
completion and rejection of unreleased live execution. Native-interface tests
translate route calls into a native process protocol with a simulated servo bus;
they do not prove real HTTP delivery, ESP32 runtime behavior or physical motion.

Deployment audit: existing install/evidence/startup bindings currently stop at
r29. r31 must name r29 as its installed predecessor (r30 was never installed),
pin the reviewed r31 hash and size above, use a new exclusive deployment journal,
and preserve the existing filesystem. Only after verified installation and a
fresh startup may the live runner bind that boot and acquire current pose.
No installation, startup, controller read or movement occurred in this checkpoint.

## Release-binding checkpoint (supersedes the earlier closed-runner status)

The installer, installation-evidence reader and startup observer now accept the
exact reviewed r31 image. The upgrade edge is r29 -> r31, with an exclusive
`app-r31-deployment-events.jsonl` journal. r30 remains excluded from installation.
The existing filesystem hash and settings-preservation checks remain enforced.

`local_shoulder_step_release.py` connects the runner to reviewed r31 installation
and retained startup evidence. DEVICE_CAPTURE requires an unused, nonfaulted
HTTP adapter with both local-step and settling capabilities, port 80, the bound
address/boot and the workspace export directory. A fresh, exported same-boot
idle capture is required before command reservation or any POST. SIMULATION
still rejects a live adapter. The run report retains release-binding evidence.
Existing signed native plan checks and fresh prewrite observations remain the
final motion admission checks; historical startup evidence is not a current pose.

Verification:

- Installation/preflight/startup regression: **147 passed in 1.95 seconds**.
- Release-binding/runner/HTTP regression: **27 passed in 21.96 seconds**.
- Actual local r31 preflight passed: pinned app hash and 1,150,592-byte size,
  retained original backups, r29 predecessor artifact, review export and existing
  filesystem SHA-256 `45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267`.
  This was local inspection only; private material was not printed or staged in
  plaintext, and no deployment journal was reserved.

No installation, startup, controller read or motion occurred. Next: reviewed
app-only installation with protected-region verification and one diagnostic
startup; export/review startup evidence, then use the bound runner for one fresh-
pose local step. A rejected pose must be exported and replanned, not overridden.
Real HTTP timing, runtime heap and physical endpoint behavior remain unverified
for r31. Installation evidence is host-recorded flash verification, not a claim
that subsequent HTTP responses cryptographically attest firmware identity.
