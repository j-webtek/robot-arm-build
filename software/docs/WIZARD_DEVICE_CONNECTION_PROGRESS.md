# Device-selection and native-request integration checkpoint

Date: 2026-09-08 UTC (2026-09-07 local). This increment continues DEV-004/005/006/008/009;
it does not close those tickets or release physical onboarding.

This checkpoint is historical. The newer
[native endpoint checkpoint](WIZARD_IMPLEMENTATION_PROGRESS.md#current-native-endpoint-checkpoint)
implements its first planned join (generic review to native metadata receipts
and prospective endpoint artifact). Default physical provider registration,
native activation and received-unit qualification remain pending.

## Implemented connection preparation

The existing explicit OS camera/serial metadata action now feeds a strict,
server-owned candidate registry. Camera and Arm pages show its exact snapshot
and allow a separately previewed metadata acknowledgement. The browser sends
only an opaque choice, reviewer ID and explicit consent, never an endpoint,
COM port, camera index, raw command or authority flag.

`WizardDeviceSelection` reconstructs the existing typed inventory contract,
checks its canonical hash and aggregate blockers, bounds its complete bytes,
and preserves missing and duplicate identities. Reviewing metadata is not
enrollment of a verified unit or a persistent native endpoint binding.

`ArrivalWizardService` owns ticket/revision/source checks, worker-result
validation, cancellation, full-result retention, logging and publication.
Selection changes are staged and become visible only after successful result
retention and completion logging. New inventories invalidate both reviews
before dispatch, even when the refresh fails. Source drift and log failure also
invalidate choices. No selection is restored implicitly after restart.

The new `rehearse_device_inventory` action exercises the same parser/registry/
review/UI/export path using four fixed injected scenarios. The existing physical
metadata action still requires the disconnected-power acknowledgement and
never opens an endpoint. Development tests inject OS-shaped physical-mode
receipts; they do not inspect this host's actual camera or serial devices.

Full inventory bytes are retained in explicit review results and diagnostic
exports; status views contain only bounded summaries. Raw device identifiers
can be identifying, so exports stay under the operator-assigned directory.

## Exact native capture request preparation

`WindowsCameraWorkerClient.prepare_probe` and `prepare_capture` now return
`PreparedCameraCampaign`: exact immutable request plus canonical arguments.
They perform no filesystem or device I/O. Existing probe/capture use the same
builder, run the existing helper/output preflight and require the authorizer
to accept that exact request before invoking a runner. There is no new
`execute(plan)` entry point and no native helper invocation in this increment.

Preparation allows the future coordinator and ingestion planner to retain the
actual intended operation before execution. The complete request must be bound;
an argv hash alone omits source/campaign/binding provenance. Filesystem races,
owned-process containment and physical admission are not solved by preparation.

## Current evidence

Frozen workspace fingerprint:
`f515fc7500ab5a5c1aabaf42b59f71293326ca2a14fdfd8191e84a5b342f36c2`.
The combined selected regression passed **904 tests, with 3408 deselected**.
Seven-module type checks and eleven-file formatting checks passed. The inert
launcher check and offline development wheel build also passed. These are not
a whole-suite pass or a qualified installation package.

The browser rehearsed a missing-identity inventory and explicitly reviewed the
camera without clearing its blockers. After two lost browser tabs, UI automation
stopped; arm review and export completed through the same service's loopback
API. Session `wizard-256fb82156224a0c8847e681341304ac` retained all three full
operation results. The independently verified export is
`software/runs/wizard-exports/wizard-20260908T011500539401Z-9efe87a0a55244cfbf26206d1dca2aa5`,
manifest SHA-256
`f76cf1d28b06242cf6007da9db3dabb74e723ae9dd2bfa083b5c22f3975c9cd0`.
Both reviews remain unconnected, unqualified and without a persistent binding.
See [the implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md#current-device-selection-checkpoint)
for precise test scope and packaging evidence. Agent selections overlap and
must not be added together.

The previous thirteen-stage public run remains valid evidence for its own
historical source `c29ed441…`, not a fresh thirteen-stage run on this source.
Original stores and their source bindings are preserved; no migration or rebase
was used to carry their results into this increment.

## Nearest remaining integration work

1. Add the server-owned **native-camera enrollment adapter**. Join explicit
   `enumerate_metadata` and `resolve_identity_metadata` receipts to exact
   endpoints, immutable reviewed identity and helper/source registration. The
   generic PnP candidate acknowledgement implemented here cannot substitute
   for that boundary.
2. Join reviewed bindings and these prepared requests to exact coordinator
   admission, native-compatible owned-process dispatch and complete capture
   ingestion. The current owned-process fixture runner is not a native-camera
   runner. Mode/control probing activates a camera; it is not metadata discovery.
3. Join the arm's native feedback-only facade to separately reviewed identity,
   power/startup and one-use authorization, preserving no retry or buffer purge.
4. Complete installed calibration intake, noncontact acceptance and handoff,
   static-primary migration, packaging and independent physical qualification.

The [noncontact plan](WIZARD_NONCONTACT_NEXT_SLICE.md) remains necessary for
whole-board feasibility and accuracy; coordinate roundtrips do not establish
reachability. Received-camera identity/modes/focus, received-arm firmware and
all physical measurements remain pending. No power, motion or contact occurred.

## Developer navigation

- [Metadata selection API](WIZARD_DEVICE_SELECTION_API.md)
- [Browser/terminal presentation](WIZARD_DEVICE_METADATA_PRESENTATION.md)
- [Native prepared-request API](WINDOWS_CAMERA_PREPARED_REQUESTS.md)
- [Operator launch and workflow](WIZARD_WORKBENCH.md)
- [Full developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md)
