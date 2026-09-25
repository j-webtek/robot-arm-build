# M2: camera continuity and ordered close/reopen implementation

2026-09-13. **Pure comparison slice under development; M2 is not accepted.**
This refines M2 of [the commissioning roadmap](CAMERA_UI_COMMISSIONING_ROADMAP.md)
alongside M1's fixed-input acceptance work. It does not enable an
action, add a collector, query USB, open the camera, or advance a physical stage.

The first code slice is `application/camera_capture_lifecycle.py`, with explicit
modeled fault cases in `tests/unit/test_camera_capture_lifecycle.py`. After the
full-history lane terminated, its separate development batch passed 28 lifecycle
cases plus 6 export faults in 25.13 s. The later frozen checkpoint-08 smoke passed
the same 34-case selection in 27.01 s with unchanged source/inputs and exact
executed test identities. This accepts only that slice. The comparator is not wired to an original reader,
saved stage, action or UI. Its consistent verdict explicitly retains original-
store, admission and clock-context authentication obligations. It cannot fulfill
M2 by itself, and it does not alter v17 output or any older original bytes.

## 1. Keep three claims separate

1. **Selected identity:** the intended endpoint/device/driver was independently
   observed and matched the original expectation for a particular operation.
2. **USB continuity:** specific original descriptor/route/link observations name
   the same intended unit across explicitly defined observation boundaries.
3. **Source lifecycle order:** the first finite acquisition completed and its
   native/process cleanup was confirmed before the second acquisition started.

An endpoint string, matching image, USB-3 product label, separate attempt ID or
fresh application instance cannot substitute for these evidence joins. A saved
observation is not a current connection. M2 remains stage-local; optics, frame
freshness, robot calibration and contact are still owned by later stages.

## 2. Existing implementations to reuse

| Fact or mechanism | Existing code | What it provides; what it does not |
| --- | --- | --- |
| Original USB request, descriptor and link decoding | `providers/windows/usb_identity_protocol.py` | Bounded endpoint/physical-device/hub mapping, device and serial descriptors, EX/V2 observations, independent operation counts. Parsing alone is not original-store provenance. |
| Serial/received-label comparison and link assessment | `application/physical_camera_usb_qualification.py` | Existing descriptor/generic/received serial hash comparisons and operating-link checks. Unknown data must stay unknown. |
| Operating-speed semantics | `_operating_usb3()` in that module | Requires the available V2 **operating** SuperSpeed-or-higher observation. Capability flags and the older EX speed value are not substitutes; no exact Mbps value is supplied by this predicate. |
| Earlier disconnect/reconnect/reboot history | `physical_camera_usb_*_readback.py`, `physical_usb_*_phase.py` and `physical_usb_complete_series.py` | Original-bound phase, boot and review chains. These earlier observations are not automatically observations bracketing later camera captures. |
| Capture-time endpoint/device/driver match | `native_camera_activation_protocol.py`, `native_camera_activation_expectation.py` | The native operation independently observes metadata and compares it with its original expectation. This is not a new USB serial-descriptor or negotiated-speed query. |
| Complete native run plus supervision | `camera_activation_campaign_evidence.py` and `native_camera_activation_evidence.py` | Exact pair, request/READY/release/result correlation, original run interval, cleanup observations and bounded errors. Failed pairs remain diagnostic. |
| Cleanup order inside one operation | `native_camera_activation_supervisor.py` | Separate before/after-cleanup observations and cleanup-finished/run-finished timestamps. It does not by itself join two acquisitions or unrelated clock domains. |
| Durable attempt accounting | `commissioning_camera_persistence.py` | Exact original permits, admission facts, native evidence and terminal receipt checks. File-name or evidence-ID sorting is not execution order. |
| Two captures already named by M1 | `camera_operating_submission_native.py` | Exact original requests/settings/runtime/preflight/epoch comparison and historical checksum references. Distinct attempts do not yet satisfy M2's order or USB-continuity obligations. |

These are claims about the current source, not new observations of the purchased
camera. Tests must use the same production readers; no friendly-name fallback,
webcam-index fallback, imported diagnostic or caller-supplied success flag is
an alternative to independently read originals.

## 3. First slice: file-only ordering assessment

- Start with the exact two capture requests in a verified M1 submission. Preserve
  the operator's order; do not sort, choose the latest two, substitute another
  successful attempt, or manufacture a missing second capture.
- Read their original permits, admission facts, run/supervision pairs, sealed
  checksums and terminal receipts under the existing original-store ownership.
- Reconstruct each campaign against the original reviewed preparation, source,
  runtime, selection/expectation, settings and epochs. Use the existing M1 native
  verifier rather than a second relaxed reconstruction implementation.
- Prove the common launch/clock context from authenticated campaign/admission
  records. A persistent physical session ID alone is insufficient because it can
  span application launches and host reboots. Unproven cross-domain ordering is
  a hold, not a comparison of convenient timestamp magnitudes.
- Require accepted native capture results and separately confirmed native and
  process cleanup. Verify the first run's cleanup completion and terminal run
  interval precede the second run's actual start. A missing post-cleanup
  observation cannot be replaced by the earlier pre-cleanup snapshot.
- Report the exact original subject hashes, explicit first/second request keys,
  interval/clock meaning, cleanup outcomes and reason codes. This is historical
  source-lifecycle evidence, not a cable reconnect, host reboot, exposure-time
  measurement or claim that the camera remains connected.

Equality decision: the native supervisor accepts a nondecreasing monotonic clock,
so equal timestamp values are valid observations but cannot by themselves prove
which of two operations happened first. Require `first.finished_ns <
second.started_ns`, with confirmed first cleanup no later than its own finish.
There is no arbitrary additional minimum delay; a positive one-tick gap suffices
for this comparison. Native result/cleanup/timing checks remain mandatory even
when that gap is positive. Missing or different launch contexts produce no gap
calculation at all. A common persistent physical-session ID is not a substitute.

The pure comparator accepts two typed native bundles in operator order and
revalidates both complete run/supervision pairs and expected hashes. It retains
each supplied admission digest, launch context and settings epoch for the future
original owner to independently join. It compares native session/source/selected
identity/expectation/runtime and requested settings, without mistaking separate
output directories for changed settings. These are comparison data, not an
authentication token or a route to bypass the existing native-input verifier.

Integration boundary: the successor original reader must reuse
`verify_operating_submission_native_inputs` to authenticate the exact same two
captures and derive the context from their original admission records. Only that
owned route can establish the comparison's provenance. Do not replace it with a
caller-authored `authenticated` Boolean, copied diagnostic JSON, or a workflow
subset. Define and test the versioned persistent successor before publication.

## 4. USB evidence-boundary decision (must precede any new collector)

The existing four-phase USB history proves only the observations it actually
contains. Determine whether its exact acquisition boundaries, unit serial, route,
boot context and subsequent native identity observations satisfy a separately
specified stage-5 continuity policy. Document the join with concrete original
request/phase references; do not call an old speed observation capture-time speed.

If that join cannot supply a required before/after fact:

1. Return a precise missing-boundary reason and retain the useful historical facts.
2. Specify the smallest needed explicit observation using the existing bounded
   USB identity provider. Define its time/byte/count limits and exact selected
   endpoint/physical-unit binding before connecting it to an action.
3. Disclose the USB query separately from file-only assessment. No broad scan,
   automatic cable operation, reconnect loop or second-unit selection is allowed.
4. Keep absent serials, conflicting language descriptors, ambiguous route walks,
   unavailable link fields and slower operating links explicit. An alternate
   identity policy, if needed for this unit, requires its own reviewed contract;
   it cannot be inferred from a device-instance suffix.

## 5. Original-store versioning is a dependency, not an optional cleanup

M1's v17 submission reader deliberately binds the complete camera campaign
inventory. Appending an M2 campaign would change that inventory. Therefore:

- Do not append new observations under v17 and change its historical meaning.
- Define a closed successor layout and an exact authenticated allowance for its
  own new package/campaign suffix. Older public readers must continue to reject
  that suffix rather than ignore it.
- Authenticate the whole actual snapshot. Any historical digest projection must
  be derived from already authenticated exact boundaries and used only for
  comparison, never as a smaller substitute snapshot passed to an older reader.
- Preserve the original M1 assessment, including its historical unresolved-check
  text. A later continuity record can satisfy a separately evaluated requirement;
  it must not rewrite the bytes of the older assessment.
- Keep stage 5 REVIEW_PENDING until the separate M3 review requirements are met.
  No M2 diagnostic or review preview grants camera/arm authority.

## 6. UI and export slice

Use the existing Camera page, action registry, one-use preview/execute lifecycle
and assigned export folder. Display USB identity, operating-link observation and
native close/reopen order as separate rows with original references or explicit
unknown reasons. Add a next action only when the backend actually offers it.

The status view must be a small cached projection, not repeated full-history
validation or a background device query. Explain historical versus current facts.
Keep partial writes, late Stop, failed completion logging and uncertain cleanup
inspectable; never offer automatic replay. New original references and records
need exact export reconstruction within existing byte/depth/attachment bounds.
Test aggregate full-history exports, not only an isolated small new attachment.

## 7. Required test matrix

| Layer | Cases |
| --- | --- |
| Pure order semantics | Nominal non-overlap; reversed requests; same attempt; overlap; equality boundary; missing/reversed timestamps; clock reset; different or unproven launch domain. |
| Cleanup/effect meaning | Native close fails; child remains; missing post-cleanup fields; retained pre-cleanup-only observation; late errors; successful image with unconfirmed cleanup. |
| USB continuity | Matching explicit serial/route; same friendly name but different unit; missing/conflicting serial; duplicate route/candidate; capability-only flag; unavailable/slower negotiated link; old observation outside required boundary. |
| Binding | Source, runtime, settings, endpoint, driver, serial, boot or original inventory changes; independently rehashed wrong contextual fields; omitted and duplicate original subjects. |
| Actual storage and public workflow | Complete predecessor; immutable retain/read/commit; partial storage; Stop/deadline/logging failure; exact export and original reopen; old readers reject the new suffix; no import/replay. |
| UI | Separate fact rows; unavailable action reason; no startup dispatch; unchecked consent; original-hash display; malformed/unknown projection rejected; stale history does not become connected. |

Run fixed-input smoke and then the complete-history acceptance lane. Keep genuine
NTFS/native-process-edge simulation separate from received-unit hardware results.
Run representative load/performance separately, with unchanged safety budgets.

## 8. Exit gate

M2 is complete only when its actual original joins, persistence, public action,
UI, exports, restart and fault tests pass. This work order alone completes none
of those. M1 full-history acceptance is still in progress, and M3 review, M4
freshness, M5 integrated acceptance, S1 simulation migration and hardware
checkpoints remain explicitly open.
