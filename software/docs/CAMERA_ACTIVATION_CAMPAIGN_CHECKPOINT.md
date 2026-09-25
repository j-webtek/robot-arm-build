# Camera v2 scoped campaign and output ownership

2026-09-10. This implements the next internal connection in the
[full application plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md), following
[original diagnostic retention](CAMERA_ACTIVATION_STORAGE_CHECKPOINT.md).

The installed v2 campaign now calls the production supervisor through an exact
consumed commissioning scope. It derives preparation and receipt accounting from
the same immutable plan, and the v2 Windows owner creates/pins fresh output
directories inside its existing cleanup lifecycle. No public camera or arm
control is enabled by this increment.

## How the pieces now connect

1. The original application constructs `PhysicalCameraActivationCampaign` using
   `from_enrollment`. Existing metadata readers derive the selected endpoint and
   activation expectation. The campaign binds their original identity hash,
   instance/container/endpoint, source, launch, runtime candidate, mode and limits.
2. Its `registration()` supplies the fixed v2 action/worker profile and the plan
   hash. `preparation_for_permit()` reconstructs the entire native request for
   one exact permit. Construction, restoration and these calls do no file or
   device I/O; a restored plan has no application guard or redeemable permit.
3. The application must bind its process-local current-context guard before
   dispatch. The core holds the original leases, writes/consumes the one-use
   permit, then gives the campaign its exact `ConsumedCommissioningScope`.
4. The campaign acknowledges that consumption once. It checks current context,
   source and full preparation before entering the supervisor, after pinning,
   at final release, and after the run. Normal modeled coverage observes four
   actual scope revalidations; none issues a new permit or deadline.
5. `camera_activation_execution()` converts the full run/supervision pair into
   exact observed counters or an absent native receipt. The existing core and
   original M1 store independently validate and retain that pair before deciding
   known/uncertain completion. Capture metadata does not verify image pixels.

`verify_camera_activation_campaign_evidence()` is the pure original-plan readback
join for the future acquisition reader. Its caller must independently authenticate
the original plan, permit and record references. Self-consistent bytes are not
their own source of trust.

## Output-directory lifecycle

Only the formal v2 application namespace opts into fresh creation:

```text
existing assigned parent/
  native-camera-attempt-<32 hex>/
    capture-attempt-<same 32 hex>/   (capture only)
```

The new Windows camera owner validates the exact registration/purpose/schema/
budget/arguments, pins existing ancestry, creates each new directory once and
pins it before the child can write. Directory handles participate in the existing
owner's cleanup observations. Existing output directories are refused even when
empty; there is no recursive creation, overwrite, reuse or deletion.

Legacy owners still require an existing working directory. The existing generic
v2 contained-process test path also retains that behavior. File pinning was
factored into shared helpers without changing its hash/read/sharing checks.
The entire new directory policy remains bounded to 128 ancestor/new-directory
handles, in addition to existing finite package/process/pipe limits.

Actual Windows tests verify rename denial while pinned, successful exclusive
child-file creation, preservation after cleanup, occupied-path refusal, partial
creation, one-use behavior, finite directory bounds and a modeled failed close
recorded as unclosed. That close test skips the kernel call and performs its first
real close only during test teardown; it does not retry an ambiguous production
close or clear a real supervisor uncertainty hold.

## Final context failure and interruption

A late source/guard failure cannot erase already-returned native diagnostics or
turn them into successful commissioning. The new refusal-only
`reject_completed_context()` handoff revokes the consumed scope and preserves
the original process-local exception. The worker returns its evidence; the core
retains it and seals uncertainty before propagating a `KeyboardInterrupt` or
other non-ordinary exception. Rejection cannot renew/revalidate a scope or replace
the first rejection with another result.

The campaign also checks plan/permit/guard identity after the last callback, so
a callback-time mutation cannot escape the final context check. Status exposes
only consumed/evidence-available/post-context-failed flags, not raw device paths
or pipe buffers. Detailed paired evidence stays private.

## Verification and limits

Source changed from
`457e9586ecc197d244efe3eebe9f786dd3e2df154eff1bd05290335ce3f25cad` to
`1f89e1c4261949d224d798ad99542dc06a0c83351c845eadfbd09cd45a88b0c3`.
Native C++ worker source, installed legacy binaries and the fixed incapable
helper pins are unchanged. Earlier whole-public-wizard acceptance belongs to
its historical source; it was not rerun here.

- Final focused campaign/receipt/scope/directory tests: **108 passed, 41.83 s**.
  This includes 27 campaign cases, 18 directory cases (two actual M1 integrations),
  24 receipt-contract cases and 39 consumed-scope cases.
- Selected camera/core/USB/legacy regressions: **663 passed, 132.10 s**.
- Windows ownership/parent/contained-process regressions: **152 passed, 13.56 s**.
  This includes 20 real contained exchanges with an incapable test helper, not a
  camera worker. The other cases exercise the existing owner/parent contracts.
- Original diagnostic-storage regressions: **17 passed, 174.64 s**.
- Four changed production modules pass targeted mypy; seven changed production/
  test files pass Black.

These four final lanes total **940 passing checks**, not a full-suite or
whole-wizard acceptance claim. Their reports are respectively
`activation-campaign-final-20260910-03.xml`,
`activation-campaign-selected-20260910-01.xml`,
`activation-campaign-owned-20260910-02.xml` and
`activation-campaign-store-20260910-01.xml` in `.codex-preserved`.

The campaign tests model camera/identity/runtime-review/source facts and process
effects; no native camera owner is constructed there. Directory tests use real
Windows file/directory handles but fake helper bytes and prohibit process startup.
The two composed M1 tests use real clocks, leases, directories, original records
and fresh reopening. Their guard deliberately refuses after pinning: no helper
is executed, counters remain unavailable, and quarantine persists after reopening.
These are not successful physical-camera acquisition or general timing guarantees.

Initial test failures are preserved. One inertness test's global `Path` patch
interfered with pytest's reporting of a wrong fixture session-key lookup; the
patch was scoped and the fixture uses its actual launch constant. Another draft
test misplaced an existing pre-effect assertion into the new rejection test;
that assertion was restored to its original test. These were test corrections,
not changes to production behavior or weaker checks.

## Exact next application handoff

The internal campaign is callable, not approved by its own constructor. Before
exposing it in the wizard, the original service still must:

1. Install and independently verify the purpose-specific v2 native build and its
   approved software policy. Preserve the historical v1 builds/holds. **Software
   approval must allow the initial supervised diagnostic probe while received-
   hardware qualification is still false.** Requiring a successful probe to
   authorize that same first probe would be a circular gate.
2. Authenticate current enrollment and accepted original identity/continuity,
   acquisition intent, runtime review, source/stage/epoch facts and operator action.
   Bind those checks to the required guard and original M1 admission facts. Do
   not use a permissive lambda, detached report or candidate's `dispatch_enabled`
   field as approval. A matched executable alone does not qualify its environment.
3. Assign/create the private output parent outside the immutable records directory
   and admit metadata/frame/disk capacity before effects. The existing post-run
   retention capacity check is not a substitute for pre-effect admission.
4. Add the original stage-5 acquisition successor to the accepted v15 entry,
   then connect probe/capture, Stop, image-byte verification, preview and both
   original/private export/reopen paths through the existing service and UI.
5. Continue installed optics/placemat calibration and the independent arm
   identity/startup/feedback services. Later keyboard/Android contact remains
   separately qualified work, not a side effect of connection.

The confirmed export parent is still
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
See the [work order](CAMERA_ACTIVATION_CAMPAIGN_WORKORDER.md) and
[developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md) for the full objective.

## Preserved developer checkpoint

The [copy-only checkpoint](../runs/wizard-exports/developer-checkpoint-camera-v2-campaign-20260910-01/README.md)
contains 1,011 verified copies (19,544,596 bytes), including all 378 application
fingerprint inputs, the final/draft reports, 97 original M1 test files and 20
real incapable-process supervision observations. Independent rehashing found no
mismatches. Both launch checks start disconnected with zero operations and the
confirmed export parent. This navigation paragraph was added after copying;
the archived checkpoint notes retain their pre-copy bytes.
