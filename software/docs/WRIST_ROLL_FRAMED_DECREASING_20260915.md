# Framing-enabled decreasing live result

Fresh feedback `operation-90d761749e724a3ba90365fa9db1b529` matched the required
six-joint high start. One new v21 fixed decreasing trial completed:
`campaign-aba218bc89224e91a0c3a830d56d0f39`.
Report SHA256: `b7944c052b571dc65cc84544ead6d83b3afdb7fb50c885aa7949a1a286480a8e`.

## Measurements and verification

| Quantity | Result |
| --- | ---: |
| Starting roll | 0.021475731 rad / 1.230469 deg |
| Commanded roll | -0.0005795035199432953 rad / -0.033203 deg |
| Reported final roll | 0.004601942 rad / 0.263672 deg |
| Reported travel | -0.966797 deg |
| Signed target error | +0.296875 deg |
| Complete post-command poses | 1,948 |
| Maximum host-read gap | 63 ms |

Same final value at 5/10/20/35 seconds; no after-five-second transitions or
reported other-axis drift. One confirmed 66-byte write with no uncertainty.
Handles closed within budget and pending I/O zero. Independent portable export
integrity, commit reconstruction and endpoint completion all pass.

The 0.297-degree error passes the existing 0.5-degree arrival tolerance, not an
exact-target criterion. No compensation was applied. This run and the previous
v21 increasing run return to identical reported low/high endpoints, but their
raw command targets and signed target errors differ.

## Framing on real captured bytes

Four baseline tail bytes [13628,13632) and 199 post-prefix bytes [0,199) formed
a valid 203-byte crossing pose. The entire frame was excluded from post-command
endpoint evidence, with hashes and offsets retained. Native verification and
independent reconstruction agree. Original captures remain untouched.

## Comparison with the historical held trial

The v20 trial `campaign-ddd0578c2a554851bca029b2f496a2f7` had the same staged
six-joint start and exact command. Its early endpoint was also 0.004601942 rad,
but it changed to 0.003067962 rad around 18.3 seconds. The new trial did not
show that late change during its 35-second capture. Its final endpoint is
0.087890580 degree higher than the historical final.

The original hold remains unchanged. The historical offline replay still
reports REPORTED_ENDPOINT_CHANGED; today's native verdict is
REPORTED_ENDPOINT_PERSISTENT. Schema, configuration, source/runtime and baseline
references differ; controller/protocol, payload/workcell and risk references
match. A single non-recurrence does not establish that late changes are resolved
or that framing software changed the arm's physical response.

## Evidence and next step

Reproduce with `software/scripts/review_roll_framed_decreasing_20260915.py`.
The script verifies the pinned new export, reruns the historical pinned replay,
checks geometry and records provenance differences without connecting to hardware.
Saved JSON: `software/runs/WRIST_ROLL_FRAMED_DECREASING_20260915.json`.

Roll command count sixteen; base remains 44. No retry, extra movement or
post-run reconnect. Last reported joints:
`[0.007669904,0,1.593806039,0.047553404,0.004601942,3.149262558]`.

Next useful bounded work: repeat this v21 increasing/decreasing pair once,
with separately admitted commands, fresh matching feedback and full 35-second
observations. Stop on any fault, late change or start mismatch. This gives two
same-profile samples per direction before evaluating a local compensation
candidate. Do not silently complete the old interrupted v20 campaign, widen
the envelope, or infer tool-tip accuracy from servo reports.
