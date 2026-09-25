# Fixed long-window roll: first command held

## Implementation

v20 adds the enumerated long-window fixed targets to the authority, wizard
service, CLI and owned-native schema/budget paths. Older v17 and v19 contracts
are unchanged. Configuration binds measured starts and exact targets, not an
empirical correction. Tests: 86 focused tests passed, plus three v20 supervisor
cases. Native package/isolated imports, wizard execution/export, substitution
rejection, delayed changes, faults and one-write cleanup were covered.

CLI selection: `--roll-long-fixed increasing|decreasing`; no arbitrary angle.
Regression report: `software/runs/roll-long-fixed-regression-20260915.xml`.

## Actual execution

Fresh baseline `operation-48e3bdd5fa904af3bc24110786caa674` matched the required
high start. One decreasing command was transmitted:

```json
{"T":101,"joint":5,"rad":-0.0005795035199432953,"spd":20,"acc":1}
```

Campaign: `campaign-ddd0578c2a554851bca029b2f496a2f7`.
Report SHA256: `06afb04e693e352d320dd57177bbe3555d5c31f7cc8633ab33cf3bea70d0f3dd`.
One complete 66-byte write, no uncertainty, 35-second post capture, 397,543 raw
post bytes and 2,229 reads. Cleanup closed all handles within budget with no
pending I/O. The process succeeded in retaining diagnostics; the campaign HELD
with ValueError at verification. No further commands were sent.

Original integrity verifies (seven originals), but full campaign reconstruction
and endpoint completion do not pass. The recorded live verdict remains held.

## Boundary-framing finding

The only rejected decoded post line is its first four bytes: `0}\r\n`.
The baseline capture ends with a JSON pose fragment ending in `"tR":`.
Joining these exact retained boundary fragments parses as one complete T1051
pose, with roll 0.021475731 rad. This demonstrates a pose split between capture
windows, rather than evidence of an interior corrupt packet. The frame crosses
the command boundary and must not be reassigned as a fresh post-command sample.

No bytes were deleted, original modified, or live rejection retroactively
overridden. The existing post decoder treats the suffix alone as malformed;
the next software improvement is explicit continuity-aware handling of this
boundary, not a general rule to discard invalid telemetry.

## Separate late endpoint finding

Complete pose rows show:

| Horizon | Roll radians | Approximate degrees |
| --- | ---: | ---: |
| Starting pose | 0.021475731 | +1.230469 |
| 5 seconds | 0.004601942 | +0.263672 |
| 10 seconds | 0.004601942 | +0.263672 |
| 20 seconds | 0.003067962 | +0.175781 |
| 35 seconds | 0.003067962 | +0.175781 |

The transition appears at host read bounds 18.312–18.328 seconds after write,
within the same owned connection. It is a -0.087890580-degree reported change.
The other five joints show zero drift in complete records. This is diagnostic
evidence, not a passing endpoint verification: the original capture issue remains
attached to the offline analysis. It also does not establish the mechanical cause
or independently observed physical movement.

Even after a future boundary fix, the observed late change exceeds the 0.01-degree
persistence screen and the final value differs from the next required anchor
0.004601942 rad. Therefore the four-command repeat must remain incomplete; do
not reposition or relax the anchor to manufacture two matched pairs.

Last reported [b,s,e,t,r,g] radians:

```text
[0.007669904,0,1.593806039,0.047553404,0.003067962,3.149262558]
```

Roll movement count is ten; base remains 44. No additional reconnect observation
was made after this held trial, so the last report is not a fresh future baseline.

## Evidence and next implementation

Update: bounded offline framing and pinned replay are now implemented; see
`WRIST_ROLL_CROSS_WINDOW_REPLAY_20260915.md`. The replay isolates the late
endpoint change without overriding this historical hold. Native integration
remains pending; no further movement was sent.

Raw originals: `software/runs/wizard-exports/campaign-ddd0578c2a554851bca029b2f496a2f7/`.
Derived diagnostic (explicitly not completion):
`software/runs/WRIST_ROLL_LONG_FIXED_FIRST_HOLD_20260915.json`.

1. Implement a bounded cross-window framing proof using BOTH exact original
   captures and byte/timestamp ranges. Accept a split-frame explanation only
   when the joined fragment is valid expected telemetry; exclude that entire
   cross-command frame from post-motion evidence. Retain hashes and bytes.
2. Keep interior malformed lines, unmatched fragments, missing bytes, gaps and
   changed originals as faults. Test every split position and corrupt variants.
3. Reconstruct the existing held capture offline with the proposed diagnostic
   logic. Preserve its historical verdict. The late change should emerge as a
   distinct endpoint-persistence failure, not a transport success that permits
   movement. Improve exported error detail beyond generic ValueError.
4. Reassess the fixed-repeat route from fresh feedback before any new movement.
   Establish stable measured anchors before compensation fitting; do not issue
   the old increasing fixed command from this unmatched start.
