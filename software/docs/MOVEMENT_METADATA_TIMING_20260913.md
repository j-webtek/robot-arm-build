# Actual supervised metadata timing — 2026-09-13

Two explicit metadata-only runs used the existing `inspect_native_arm_metadata`
child through `DiagnosticProcessRunner`, with a three-second original work
deadline. Neither opened a device port or sent a serial/motion command; returned
counters were zero. These were not endpoint trials and did not qualify power,
firmware, clearance or physical pose.

Both found the expected CP210x on COM7: VID/PID 10c4:ea60, serial
52E4E1E8337FEF119E92181CEDD322A4. Its native metadata blockers were empty.
Driver: Silicon Laboratories Inc., silabser, 6.7.3.350, oem65.inf.

| Observation | Total host call | Snapshot age at host return | 100 ms gate |
| --- | ---: | ---: | --- |
| Original 50 ms polling | 984 ms | 140 ms | Too old |
| Deadline-bound 5 ms polling | 984 ms | 93 ms | Inside by 7 ms at this point only |

These are single observations, not a repeatability distribution or guarantee.
The second result's small margin does not qualify the full endpoint path:
adapter retention, context checks and scheduling add time afterward. Original
timestamps and the existing 100 ms context gate remain unchanged.

## Retained originals

Under `software/runs/wizard-diagnostics/`:

- `wizard-0a3c40692ea24c9dbb9f6d7f147a07ac`: pre-change; verified head SHA-256
  `532cc9529a18bc064fa747648ddf5a4730140e47116c9d1d1ccb9d955712f262`.
- `wizard-2918ee6e00214dad98dc4511e4cd7bb3`: post-change; verified head SHA-256
  `13d7df386b3d9e09b580f4396b0c81fde7e34989bba7eae2bd343fab2052df5c`.

Both logs contain request/result events, full snapshots, source hashes and host
times. Both passed `WizardDiagnosticLog.verify`: VERIFIED_DIAGNOSTIC_ONLY.

## Software connection and remaining qualification

`SupervisedEndpointMetadataFactory` adapts the fixed diagnostic to the existing
current-context reader, with trusted cancellation, retention and current-context
callbacks. The remaining pre-launch cutoff is passed to the diagnostic runner.
Deadline checks occur before dispatch, during polling and after cleanup. Existing
process-tree/pipe cleanup remains mandatory; the work cutoff is not a guarantee
that exceptional cleanup ends at that instant. Cleanup uncertainty is a failure,
not a successful snapshot. There is no raw native fallback or serial open.

437 endpoint/campaign/diagnostic-runtime tests passed in 80.91 seconds, exit 0.
Result: `software/runs/endpoint-supervision-integrated-20260913-01.xml`.
The full adapter path has synthetic tests but is not physically timing-qualified.
Next: wire the factory into host assembly and measure final context freshness
with retention enabled. Do not reuse these historical snapshots for a new live
request or infer current operator presence from metadata.

## Shared acquisition plus retention probe

Added `software/scripts/bench_metadata_timing.py`, a finite metadata-only probe
(one to five samples; three by default). It calls the same
`acquire_supervised_metadata` function used by the endpoint factory, with actual
diagnostic-log retention before measuring return age. No synthetic motion
request or qualification record is needed to run this probe.

Actual run: `wizard-27f51f7be4524198a546caf3560df657`, under the diagnostic log root.
Verified head: `84653ab3238f7a3d0fe27e08795c823bcc9e7da4176394747e4709f166319332`.
Log verification returned VERIFIED_DIAGNOSTIC_ONLY.

| Sample | Acquisition/retention elapsed | Snapshot age at probe return |
| --- | ---: | ---: |
| 1 | 859 ms | 62 ms |
| 2 | 844 ms | 62 ms |
| 3 | 860 ms | 78 ms |

All three were inside 100 ms at probe return. Source verification ran before
acquisition, consistent with existing endpoint reference-check ordering.
The in-window callbacks checked cancellation; they did not establish operator
presence, a reviewed physical controller binding or full-cell qualification.
This is acquisition/retention timing evidence, not qualification of the final
endpoint context or motion. Full snapshots remain retained; no serial port or
motion command was used.

A composed context test proves retention delay counts against the unchanged
age gate: a synthetic 20 ms delay passes; 120 ms fails as stale.
79 adapter/assembly/diagnostic-runtime tests passed, exit 0, in 8.85 seconds.
Result: `software/runs/endpoint-retained-metadata-20260913-01.xml`.
