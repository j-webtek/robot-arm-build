# Camera-v2 original-result and application handoff

10 September 2026. **Implemented internal handoff; full application unfinished.**
The previous checkpoint installed native builds and the enforced software policy.
This increment fixes a version mismatch: the executor/M1 store retain a v2
run/supervision pair, while the existing dispatch/data owner previously accepted
only v1 single-record evidence. The same owner and acquisition service now accept
an explicit v2 path. No public camera or arm activation hold was removed.

Confirmed export destination:
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
This developer checkpoint is not a wizard-export schema or hardware acceptance.

## Implemented scope

1. Extend the existing dispatch owner with an explicit v2 branch. Keep old
   readers/limits unchanged. Reconstruct the same exact campaign, consume one
   attempt, reread its original permit/result/pair under the camera lease and
   independently verify accounting and plan binding before any data handoff.
2. Retain failed/unknown diagnostics too. A missing native receipt is not a zero
   receipt, and uncertainty must never feed capabilities or image publication.
   Lease-exit/context failures prevent all current data handoff.
3. Add a pure v2 probe-to-capabilities join using the existing mode/control data
   model. Verify both evidence roles and the original preparation/hash references;
   do not fabricate a v1 native run or invent unsupported controls.
4. Connect that result to the existing acquisition service's staged-publication
   lifecycle. The outer Arrival completion log remains required before publication.
   No new connection manager, logger or public evidence-upload path is introduced.
5. Test modeled effects with the actual core/dispatch/parsers and real M1 readback
   where practical. Cover wrong originals, unavailable native results, changed
   context, failed lease exit, Stop and interrupted execution. Preserve hardware
   and software-fact modeling labels and all failed originals.

## How the existing components now join

```text
Original service (admission still required)
  -> PhysicalCameraAcquisitionService: exact v2 plan, current context, one operation
  -> PhysicalCameraDispatchOwner: actual core + camera-only M1 store
  -> PhysicalCameraActivationCampaign: installed policy + consumed scope + supervisor
  -> Original permit, result, run and supervision reread under the same camera lease
  -> Lease exit and final context check
  -> PhysicalCameraCaptureWorkflow: probe -> settings -> capture readback -> pixels
  -> Outer completion log -> publication -> retained PNG preview
```

The new methods `preview_activation_plan` and
`run_admitted_activation_campaign` are internal service methods, not routes or
buttons. The plan method is inert. The run method requires the original M1
adapter and a refusal-only current-context callback; a Boolean cannot approve
an action. It checks the exact current plan, source/launch/enrollment/settings
context, publication state and Stop signal before dispatch. The existing
dispatch lock prevents overlapping operations.

The dispatch owner reconstructs the exact campaign, obtains and consumes one
permit through the existing core, and rereads all original evidence. The two
independent hashes and paired preparation must match. It recomputes native
accounting and compares it with the stored result. It does not hand off data
before the original read transaction exits. A late interruption can still retain
and reread historical evidence, but never publish it or replay the attempt.

`physical_camera_configuration.py` verifies each evidence version explicitly,
then reuses the existing numeric mode/control models. There is no forged legacy
native envelope. Missing controls remain unavailable, and reported settings do
not mean that pixels or received hardware have been verified. V2 capture receipts
contain frame metadata, not preverified image hashes.

`physical_camera_capture_workflow.py` preserves both originals as an explicitly
named `rocell.camera_activation_observation_pair.v2` private diagnostic. Only
clean, matching readback reaches the existing file validator and image ingester.
They check actual YUY2 files, retain their hashes, and derive a bounded PNG.
Staged copies share a one-use retention ledger. Neither failure nor discarded
publication retries ingestion. The image is a retained diagnostic, not a live
camera stream, calibration result or authority to move the arm.

The private combined diagnostic bound is 4 MiB for v2: the existing 1 MiB
allowance plus two bounded 1.5 MiB pairs. The legacy 1 MiB workflow bound and
legacy/native/USB schemas remain unchanged. This does **not** increase public
export limits; that integration remains a specific task below.

## Hardware-free verification

New test modules:

| Test file | What is real | What is modeled |
| --- | --- | --- |
| `test_camera_activation_application_handoff.py` | Supervisor/codecs, settings/readback, small YUY2 files, hashes and PNG | Process owner, native result, source |
| `test_camera_activation_dispatch_handoff.py` | Dispatch/core, consumed-scope checks, evidence verification | Process owner, store, admission/source facts |
| `test_camera_activation_dispatch_handoff_m1.py` | Production wrapper, NTFS/M1 storage, OS leases, fresh reopen | Process owner, prerequisite/identity/runtime facts |
| `test_camera_activation_service_handoff.py` | Existing service, staged settings/result/publication and small-image ingestion | Store adapter, process/native/source facts; outer log completion |

Initial focused success: 46 tests (16 + 17 + 3 + 10). They include wrong or
missing evidence hashes, wrong purposes, missing/truncated pixels, native cleanup
failures, unknown native accounting, readback/lease-exit failures, Stop, late
interruption, stale contexts, publication failure and refusal of repeat attempts.
The three actual M1 cases cover known probe, known capture and unknown result;
fresh reopening preserves the exact permit/result/two-part evidence.

Initial failing reports are preserved. Test-fixture corrections, not relaxed
production checks, addressed an intentionally negative codec timestamp, exact
exception classes, a misnamed protocol-store retention method and a non-app
launch label. The negative timestamp remains unsupported by the current dataset
ingester; that is not a claim about what every physical driver will return.

These tests do not exercise a camera-capable executable, authenticate the full
original v15 predecessor chain, connect hardware, or test the public v2 UI. The
later aggregate reports below define the final tested source rather than adding
overlapping focused counts together.

## Still required for public acquisition

The accepted original v15 entry needs an additive acquisition/admission suffix;
the existing Session reader currently accepts only its entry record/event and
USB campaigns. Current enrollment, runtime-review provenance, original stage/
epoch/hazard facts and output/storage capacity must be authenticated before
dispatch. The default original store's denied facts are not to be removed until
that substantive provider exists. Public probe/capture/preview and arm startup
remain unfinished software work, not merely waiting for delivered hardware.

This handoff is one dependency of that complete service path, not a reduced
definition of the goal or permission to exercise a camera while developing.

### Next production implementation order

1. Extend the original v15 mode-entry workflow with a closed acquisition suffix.
   Bind current enrollment, both runtime-review roles, original stage/hazard/
   eight-epoch facts, purpose, settings and exact plan. Preserve the same full
   snapshot and all prior USB/camera campaign records. Do not filter a history
   into an apparently valid prefix or substitute a copied report for originals.
2. Implement the substantive original admission-facts reader under the exact
   required leases. Revalidate fresh device identity and original dependencies
   at the existing guard boundaries. Keep `PhysicalCameraSession._denied_facts`
   as the default until this reader exists. Initial software approval must not
   require a previously successful hardware acquisition: avoid a circular gate.
3. Admit bounded output/storage capacity before consuming an attempt. Include
   requested frame bytes, paired diagnostics, dataset/preview bytes, incomplete
   publication and disk reserve. Test exhaustion, wrong roots and source/context
   changes without opening a camera or relaxing the native deadline.
4. Connect the original action to the existing Arrival intent/completion log and
   these internal service methods. Add public probe/settings/capture/Stop states,
   single-operation behavior and opaque preview IDs. No GET/status call, page
   refresh, import, restart or retry may start a camera. Persist and validate
   original result completion before publishing data.
5. Extend camera-specific diagnostic export/readback within explicit per-role and
   total limits. Account for current, pending and dispatch diagnostics; do not
   silently raise every legacy export limit or truncate original evidence. Test
   complete and failed publication, redaction and export-folder failures. Export
   must remain file-only and must not reopen devices to gather information.
6. Add a fresh public wizard rehearsal using the actual M1 store and an incapable
   producer, then reopen/export without replay. Keep source pins, modeled facts
   and hardware verification clearly separate. Finish the original RoArm identity,
   startup/feedback and UI path separately; connection does not authorize motion.

Only after these production joins and tests are complete can delivered-hardware
commissioning begin through the wizard. Placemat calibration, clearance checks,
and separately authorized keyboard/phone contact remain subsequent stages.

## Final verification, 10 September 2026

Application source fingerprint:
`fee94db6a2fa3bcc8ee71516e42b6e11a5efb03a6d8e41eed8ff172fb807e473`.

- `activation-handoff-final-20260910-01.xml`: **400 passed**, 138.41 s.
  Includes all 46 new tests and selected legacy/configuration/publication/native
  supervisor, campaign, runtime-policy and paired-evidence regressions.
- `activation-handoff-compatibility-20260910-01.xml`: **269 passed**, 78.02 s.
  Covers the existing Arrival service/UI, diagnostic exports, physical-camera
  views/runtime UI and legacy production dispatch against actual M1 storage.
- Mypy: four changed production modules clean. Black: eight changed Python files
  clean. These are selected regression lanes, not a full repository test run.
- Both launcher modes passed `-Check` on this source with camera/arm
  `NOT_CONNECTED`, zero operations, no physical authority and the confirmed
  workspace export directory.
- All 46 native build/input/manifest files indexed by the preceding runtime
  checkpoint still match their hashes. No native rebuild, repinning or execution
  of a camera-capable worker occurred in this increment.

Copy-only evidence bundle:
`software/runs/wizard-exports/developer-checkpoint-camera-v2-handoff-20260910-01`.
It preserves source/test inputs, successful and failed draft reports, and selected
actual-storage test originals. These are developer diagnostics, not an importable
physical session, runtime approval or a passed hardware commissioning stage.
