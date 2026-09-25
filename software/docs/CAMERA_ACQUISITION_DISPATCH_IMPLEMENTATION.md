# Camera acquisition dispatch: implementation work order

Date: 2026-09-08. Companion to `CAMERA_ARM_DEVELOPER_PLAYBOOK.md`, DEV-008.

## Outcome and limits

Connect the existing camera commissioning coordinator to the existing retained
capabilities/settings/frame workflow. The application must read the committed
attempt back from its original store before treating its result as current.
This is implementation of the connection path, not another evidence viewer.

The purchased camera remains the static overhead Arducam USB 3.0 20 MP camera
with the 16 mm C-mount lens (purchase profile B0477). The RoArm-M3 Pro is a
separate control endpoint. Neither is opened by this work. No arm startup,
torque, motion, calibration or contact authority follows from a camera result.

The current physical runtime registrations are dormant, and the original
physical source stage is blocked. They cannot admit acquisition today. Do not
change these records, build pins, Freeze-011, RC03, or physical activation flags.
Do not run a known-held campaign just to populate the screen: that can consume
an attempt and quarantine its original store without making connection progress.

## Existing components to reuse

1. `PhysicalNativeCameraCampaign` binds one exact operation, selection, runtime,
   finite budget and original consumed commissioning scope.
2. `PhysicalCameraAcquisitionCoordinator` owns prepare/execute, leases, intent,
   consumption, evidence retention and attempt outcome.
3. `M1PhysicalCameraPersistence` owns the original durable camera namespace.
4. `PhysicalCameraAcquisitionService` and `PhysicalCameraCaptureWorkflow` already
   accept retained probe/capture data, derive supported settings, validate actual
   frame bytes and stage a bounded PNG for post-log publication.
5. Arrival already has source/Stop/completion-log checks and diagnostic export.
   Extend these boundaries rather than publishing media directly from a worker.

## Implementation sequence and ownership

### A. Scoped original evidence reads — storage agent

Add a camera-transaction read method alongside the stage-only reader. Keep the
stage-only method's restriction unchanged. The new method accepts an exact
evidence reference, not a file path, and checks the audited inventory, original
session, payload hash and length while the camera leases remain held. Reuse the
existing guarded read logic. It must not mutate stages, approve facts, open a
device, or turn narrative intake into an accepted hardware observation.

### B. Bounded-effect outcome — Windows camera agent

Implement a named deterministic mapping from a verified native run to known or
uncertain bounded effects. Known completion requires the complete matching native
result and confirmed native/process cleanup. Missing counters, partial lifecycle,
failed cleanup, cancellation, protocol errors and pre-owner qualification holds
must not become successful acquisition. Preserve exact counter evidence.

This mapping is not physical stage acceptance, observed actuator isolation,
driver qualification or pixel validation. Keep runtime registration and runner
release checks unchanged. Test both probe and capture and the negative cases.

### C. Application dispatch transaction — root

Add an application owner with these responsibilities:

- Accept a server-owned campaign and original camera persistence context; no
  arbitrary browser paths, raw JSON commands, importable permits or backend flags.
- Prepare using a freshly read challenge, not a cached UI readiness flag.
- Execute at most once; wire Stop to the same coordinator cancellation token.
- After execution and lease cleanup, reopen the original store and retrieve the
  retained permit and campaign bytes using the attempt's references.
- Compare the exact prepared permit, campaign registration, selection, runtime,
  operation and independently retained evidence hash.
- Deliver only a known completed probe/capture to the existing staged observation
  APIs. Do not replace original retention with `campaign.evidence` in memory.
- Leave publication to Arrival after its current-source, Stop and completion-log
  checks. Preserve failed/uncertain attempt diagnostics and never auto-replay.

Current production composition must remain unavailable until a real supported
admission and release contract exists. A constructor parameter, test fixture,
operator label or successful file inspection is not that contract.

### D. Tests and presentation — UI agent

Add focused tests around the existing publication boundary and correct wording
that implies a hardware connection without an observed acquisition. Check that
the UI distinguishes the local service, metadata selection, finite capture and
unverified physical state. Avoid a second competing connection screen.

## Verification

Use incapable test doubles at the unqualified native backend boundary. Exercise
the real application transaction and coordinator where possible; label any
in-memory store as a protocol model, not an M1 durability test. Use real tiny
frame files for ingestion tests. Existing actual-NTFS tests continue to verify
the original store separately. Do not claim that Python wire fixtures exercise
production C++ COM/Media Foundation acquisition.

Required cases: successful probe, successful finite capture, unsupported or stale
settings, wrong identity/attempt/permit/evidence, unknown effect outcome, failed
native/process cleanup, cancellation before/after execution, failed readback,
lease-exit error, late publication failure, no implicit replay, and inert import,
constructor and status reads. Run existing camera/core/Arrival regressions.

Diagnostic export remains under `software/runs/wizard-exports`, with explicit
operator export and privacy consent for original attachments. Do not erase old
sessions, partial attempts or exported reports.

## Remaining work after this transaction

- Original stage-1 reassessment and stage-2/3/4 acceptance adapters, plus reviewed
  observed epoch successors and substantive admission-facts construction.
- Qualified native runtime release, exact output-directory ownership and received
  camera/driver validation. Dormant registrations cannot be used as credentials.
- Original arm stages 9–12: installed firmware/boot-policy/controller binding,
  manual power observations and one bounded feedback-only connection.
- Installed intrinsics, board registration, tool/reference-frame calibration,
  noncontact acceptance and separately authorized typing/tapping tests.

The overall wizard goal remains incomplete until these are integrated and the
hardware-dependent steps are clearly guided. Do not call this increment a
plug-in-and-type release.

## Implementation results

Implemented application APIs:

- `M1PhysicalCameraTransaction.read_camera_evidence(reference)` reads stage
  evidence under camera leases. The original stage-only method stays restricted.
- `read_campaign_result(attempt_id)` reconstructs the result matching the actual
  durable terminal state; saved result JSON alone is not a known seal.
- `assess_native_camera_bounded_effect(...)` maps exact verified native lifecycle,
  counters, original deadline and cleanup into CONFIRMED or UNCERTAIN effects.
- `PhysicalCameraDispatchOwner` binds the exact original deployment root, cell
  and source; runs the real coordinator; then audits original permit, terminal
  result and campaign evidence before any staged-data handoff.
- `PhysicalCameraAcquisitionService.run_admitted_campaign(...)` connects that
  transaction to the existing probe/settings/capture workflow. It seals the
  enrollment and settings/session context before planning and checks them at
  preflight and the native pre-start/READY/RELEASE boundaries. It rejects an
  already retained probe or pending observation before creating another owner.
- `dispatch_view()` is cached diagnostic state. It is deliberately separate from
  the existing closed camera UI response schema. `retained_capture_diagnostics()`
  includes transaction and audited historical native diagnostics, including
  uncertainty. A failed final validation/lease exit preserves verified bytes but
  explicitly does not claim a completed readback scope.

The owner returns the existing `pending_observation_result`; it does not call
`publish_retained_observation`. The later Arrival integration must retain the
exact result and completion log before invoking its existing
`_publish_physical_camera_observation` handoff. Export uses the existing
`native-camera-data.json` metadata attachment path and privacy/redaction limits.
There is no raw-media embedding or second exporter.

### What is actually exercised

The modeled end-to-end test runs the real application owner, coordinator,
consumed-scope checks, Python parent handshake and native result parsers through
probe, explicit settings and finite capture. It creates a real 16-byte YUY2 test
frame, ingests/verifies it and derives a PNG. A separate actual-NTFS suite runs
the **public** dispatch owner with real M1 retention, lease exit, original
readback and restart verification. Its predecessor stage records and native
camera/process observations are explicitly modeled, not hardware qualification.

Negative cases cover changed source/identity-context/settings epochs, plan-time
mutation, context drift during the final source hash at native admission,
substituted permit/result/artifact schema/bytes, cleanup uncertainty, Stop,
readback failure, lease-exit failure and repeated invocation. The UI regression
uses a Node fake DOM and actual isolated Arrival publication snapshots; it is
not a browser-on-hardware test.

### Still not connected to public physical actions

`physical_camera_probe` and `physical_camera_capture` remain held in the action
catalog. Arrival does **not** yet manufacture a valid physical persistence/facts
composition or call the new dispatch method. Native output directory ownership
and a qualified runtime release remain missing. No successful test record is
imported to bypass those requirements. The new transaction is implemented and
exercised, but the public physical connection feature is still incomplete.

The next implementation should supply original stage reassessment/acceptance,
observed epoch successors and a closed admission-facts owner, then native release
and output ownership, and finally replace the public holds with those real
prerequisite decisions. Do not route the buttons to a known-held attempt just
to make them look functional. Arm identity/power/feedback onboarding is a
separate outstanding integration, followed by installed calibration and motion.

Final source fingerprint:
`81afc87b6341515156a066d3d611aa66d85cc5dec79a859ab5401e906ac2b00e`.
Both launcher startup-check modes report `READY_FOR_DIAGNOSTICS`. Black and mypy
pass for all five changed Python production modules.

Final, non-overlapping regression selections on that source:

| Selection | Result |
| --- | --- |
| Application dispatch and camera browser/terminal presentation | 109 passed, 20.75 s |
| Public M1 dispatch owner, native campaign and bounded-effect assessment | 97 passed, 123.17 s |
| Scoped evidence readers, coordinator, acquisition/data/publication regressions | 159 passed, 112.85 s |
| Total across those three selections | **365 passed** |

An additional post-format dispatch-only rerun passed 28 tests in 4.28 s; it is
already included above, not added to the total. Earlier exploratory runs exposed
an invalid placeholder challenge, fixture setup mistakes and a closed-UI-schema
compatibility regression. Those were repaired before the final green selections;
they are not counted as successful verification.

No hardware, native camera helper, serial port, power control or arm motion was
invoked by this work. No original workspace session/export was deleted or reset.
