# First live two-block comparison completed

Session `17689373ad724aedb4c91a0629303527` completed all eight explicit roll legs.
Every leg passed original endpoint reconstruction, unchanged six-joint hold,
export integrity, command protocol and predecessor-baseline matching. No retry,
return, cancellation, connection failure, refit or policy change occurred.

## Paired results

Both blocks used high / uncorrected descending control / high / frozen lookup.
Desired control and lookup endpoint: 1.25 degrees. Speed 20, acceleration 1.

| Block | Control command | Control hold endpoint | Lookup command | Lookup hold endpoint | Lookup error |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 1.25 | 1.494140602 | 0.95 | 1.406250023 | +0.156250023 |
| 2 | 1.25 | 1.494140602 | 0.95 | 1.230468748 | -0.019531252 |

Each high positioning endpoint was 2.285156222 degrees. All endpoints above
remained unchanged during their subsequent holds. The absolute-error reduction
versus the paired control was 0.087890580 degrees in block 1 and 0.224609351 in
block 2. Only block 2's lookup met the illustrative +/-0.05 and +/-0.10 bands.
These bands remain sensitivity examples, not adopted accuracy requirements.

All seven measured hold-end-to-dispatch intervals were 20.885277–20.941038
seconds, inside the proposed 18–22 second window. Hold response spans ranged
34.702186–35.028109 seconds, with 115–117 responses per hold. Maximum response
gap across the holds was 501.3454 ms, below the existing one-second limit.

## Independent evidence verification

After the process exited successfully, all eight exports were independently
replayed again. Both four-leg block audits passed the individual-leg/protocol
and observed-interval checks. The historical block auditor still reports shared
boot identity unverified; it was not modified to claim stronger attestation.

The session header and 34 numbered journal records are directly in
`software/runs/wizard-exports`, with prefix
`comparison-17689373ad724aedb4c91a0629303527-`.
All sequence numbers and previous-record SHA-256 links checked. Final event:
FINISHED / COMPLETED / reviewed_legs=8. Final event-file SHA-256:
`92af6755df5fc2a05719ae42d1175a355eb3b8c9a97529560b953be636552824`.
The log records the same process/invocation, not an independently attested boot.
Hashes are integrity checks, not third-party authentication.

Ordered exports (all under `software/runs/wizard-exports/`):

1. `wizard-20260917T025422277494Z-7db621efd9aa4fe287a6475416b258b0`
2. `wizard-20260917T025520085502Z-b917fa91c10c4067b5b8d34a57555210`
3. `wizard-20260917T025617978823Z-07f1e86ff5be4c2fb48963e7f077f63f`
4. `wizard-20260917T025715945095Z-9f59e4d30a7d4fe58b45c4e99c2be4b4`
5. `wizard-20260917T025813939691Z-c523818ccc114167a235c99559a7fba7`
6. `wizard-20260917T025911731748Z-cb6312e00a4b453c91c9ea4fac27e357`
7. `wizard-20260917T030009614630Z-d6cbbb9c80f24d73a334b4b8d5280afa`
8. `wizard-20260917T030107530669Z-3e47bfea5df648319ea0ca71509f409e`

Their manifest hashes and predecessor links are retained in the verified journal.
The mapping record now includes five completed held-out lookup trials and four
selected uncorrected controls; other historical controls are not silently counted.
The earlier uncertain attempt remains separately retained.

## Conclusions and next work

The live session adapter, scheduling, evidence review and journaling path worked
end to end for this eight-leg experiment. This is not general reliability
qualification. The same frozen compensated command still produced different
stable reported endpoints despite consistent scheduling and matching reported
lookup baselines. Scheduling consistency alone did not remove the variation;
the experiment does not prove a mechanical or firmware cause.

Keep the candidate disabled and do not refit from these two outcomes. We now have
enough evidence to move beyond repeating this offset: design a separate bounded
small-step response/quantization experiment, or add independent tip measurement.
The small-step experiment must first reconcile the current minimum-step and
same-side rules explicitly; do not route around them through raw commands.
Continue retaining initial arrivals, holds, timing and failed trials separately.

Last reported roll: 1.230468748 degrees. No final return movement was sent.
All accuracy statements here concern controller joint feedback, not millimeter
tool-tip accuracy or a calibrated keyboard/phone contact position.

The next experiment is designed in `LOCAL_COMMAND_SPACING_EXPERIMENT.md`. It
tests small command differences from a common high position and therefore does
not require relaxing the current minimum physical step. Offline preflight is
implemented; new native probe actions are not yet available.
