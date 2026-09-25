# Live wrist campaign findings — 2026-09-14

## Outcome

The real arm accepted a wrist movement through the new wizard campaign path.
Its command bytes, post-movement telemetry and failure diagnostics are now
retained in an independently verified export. The full two-leg campaign has
**not passed**: the last run stopped after one command because its post-capture
byte budget was exhausted before the required five-second window finished.
No compensation was applied, no tolerance was widened, and no automatic second
command or recovery movement was sent after the hold.

## Actual observations

Device: CP210x COM7, VID 10C4/PID EA60, serial
`52E4E1E8337FEF119E92181CEDD322A4`. USB metadata matched the retained arm binding.
The operator's existing supplied-power, secured/clear and attended setup
confirmation was used. Clearance and tool configuration are user-reported,
not newly measured by the software.

| Stage | Command/observation | Result and qualification |
|---|---|---|
| Initial zero-write capture | Wrist 3.779296882° | 270 decoded pose records; initial mid-line fragment disclosed; no transmitted bytes |
| First dispatched campaign | Nominal wrist 0° | Dispatch claimed, but child trial publication failed; exact write/post history unavailable |
| Follow-up zero-write capture | Wrist 0.966796894° | Other five reported joints unchanged; consistent with the 0° command taking effect, but not a reconstructed campaign endpoint |
| Final dispatched campaign | Nominal wrist 4° | 63 command bytes confirmed; final reported wrist 3.779296882°; signed residual −0.220703118° |
| Planned second leg | Nominal wrist 0° | Not submitted: post-capture capacity hold on the first leg |

The final post-capture retained 49,152 bytes, 238 decoded pose records and
178 consecutive records at the final wrist value, spanning 3.172 seconds by
host acquisition bounds. Actual capture duration was 4.187 seconds rather than
the required five seconds. These are useful diagnostic observations, **not a
passed five-second endpoint verification**. All serial handles closed, no
pending IO remained, the child exited successfully, and parent cleanup passed.

The earlier follow-up value corresponds to approximately +0.967° relative to the
nominal 0° target. Together these observations suggest the residual is not one
constant global offset. Direction and target differ, so neither direction alone
nor a mechanical cause has been isolated. Servo feedback is not independent
tool-tip XYZ measurement, and firmware Cartesian fields are not camera ground truth.

## Software defects exposed by real integration

1. **Metadata reader constructor mismatch — fixed.** Campaign bootstrap requested
   a bounded 32 checks, while the actual Windows reader accepted at most eight.
   The first attempt stopped before native motion access. The reader now accepts
   the explicit 32-check campaign allowance without changing cumulative native
   API/byte budgets, default allowance or deadlines. 60 targeted tests passed.
2. **Publication under pinned directory — fixed.** The actual supervisor locks
   ancestor directories against rename. Atomic temporary-file rename failed for
   the endpoint record and child trial. A file-only real-Windows test reproduced
   the failure. Campaign child records now use exclusive create, flush and exact
   readback before advancement/receipt emission. Incomplete files remain consumed
   failures; no repair/replay occurs. Parent export publication is unchanged.
   64 targeted tests passed, including complete/missed simulated campaigns under
   actual Windows directory pins. The final live trial was retained successfully.
3. **Post-capture capacity mismatch — open.** The profile allows only 49,152 post
   bytes, which filled in 4.187 seconds on this firmware. A complete capture must
   preserve the observed stream, not discard frames or declare early completion.
   The 16,384 baseline + 49,152 post split and 65,536 per-leg / 131,072 campaign
   bounds must be reconsidered together under an explicitly versioned capture
   profile so existing signed records retain their original meaning.

New constructor/pinned-directory regression tests are included in the wizard's
registered owned-pipeline suite (77 files).
Final post-live regression: **452 tests passed in 46.53 seconds**. Report:
`software/runs/campaign-post-live-regression-20260914.xml`. No hardware access
was performed by that regression suite.

## Exact retained records

- Initial baseline operation: `operation-64dcca560058402c898c1ca385df8f74`.
- Failed prelaunch campaign: `campaign-24ef94d76ba143319aea4c78ccbea398`.
- Missing-trial campaign: `campaign-f65bd4cd10ad4d56af7260d864e76adc`.
- Follow-up baseline operation: `operation-7210fabc28a748a1903753cd80562889`.
- Final campaign: `campaign-9880974857c8462389ecf1e180d962cc`.
- Final wizard operation: `operation-54ac83ecaf824c07b7c3adf7e8fd49f3`.

Verified standalone export:
`software/runs/wizard-exports/campaign-9880974857c8462389ecf1e180d962cc/`.
Report SHA-256:
`1bc4c1fbfefa28c30215c71ff64c954c7909abbde307ffb9d008d492be3a73be`.
Verification reports `valid=true`, but endpoint completion and reconstruction
are false because the required post window is incomplete. Preserve that distinction.

Session export:
`software/runs/wizard-exports/wizard-20260914T214757837651Z-3b3690ba9c044a4c8d9a1312e1d91884/`.

## Version 3 live result: complete capture, measured target miss

Regression: `software/runs/campaign-capacity-v3-regression-20260914.xml`:
472 tests passed. The previous v2 export still verifies with its unchanged hash
and incomplete-window status.

Fresh zero-command baseline: `operation-f5fe9f9c51654b7f8a1a91e2783b4b75`.
Campaign: `campaign-37c6f91ee84a4fe4ab057fb0df2a1d48`.
Wizard operation: `operation-520bbd3b23774fa8bd49bc9936656629`.

- Nominal wrist command: 0 degrees, spd 20, acc 1; 47 transmitted bytes confirmed.
- Reported start: 3.779296882 degrees; reported final: 0.966796894 degrees.
- Signed residual: +0.966796894 degrees; tolerance remains +/-0.5 degrees.
- Baseline: 11,008 bytes. Post: 57,344 bytes, full 5.0 seconds, 281 pose samples.
- Endpoint result: TARGET_MISSED; movement detected; other joints unchanged.
- Second nominal 4-degree leg: NOT_EXECUTED. No retry, recovery return or correction.
- No trial errors; handles closed, no pending IO, cleanup within budget.
- Export valid and reconstruction consistent; endpoint completion false.

The storage fix is now demonstrated on hardware. This result reproduces the
approximately +0.967-degree residual previously observed after a zero command,
but does not establish its cause or a general compensation formula. Host-read
telemetry is not independently verified device freshness or tool-tip position.
The last reported wrist position is approximately 0.967 degrees.

Standalone export: `software/runs/wizard-exports/campaign-37c6f91ee84a4fe4ab057fb0df2a1d48/`.
Report SHA-256: `203b3a9a5427e2ea9d86fd76ccf401f9aefde0fef9ef5160ef87f7855d47d3c4`.
Session export: `software/runs/wizard-exports/wizard-20260914T220416358504Z-b3742317757b46ffa977f1747cf31cca/`.

Next: inspect command-to-servo conversion and configured deadband in the reviewed
firmware, then collect comparable opposite-direction endpoints in a separately
staged campaign. Keep nominal commands and measurement tolerances unchanged
until enough evidence supports a separately validated compensation model.

## Experiment roadmap

Latest result: the [matched-zero experiment](MATCHED_ZERO_ENDPOINT_EXPERIMENT.md)
completed a passing 0 -> 4 degree campaign from a negative starting angle.
Zero from below reported -0.439453 degrees versus +0.966797 degrees from above,
a 1.406250-degree separation. All capture and export verification passed; no
compensation was applied. Repeatability, rather than tuning, is the next step.

### Completed two-command diagnostic, 22:40 UTC

Campaign `campaign-8692dabab46d4826a5cac99ec2c76386`, wizard operation
`operation-3212b167c3e44e3299f0a3fe9ca7b697`, used a new zero-command baseline
`operation-66660c79cb55406680ed4465f68f9ffc`. Both motion writes completed and
both post windows were complete (5.0 seconds, 282 pose samples each).

| Leg | Nominal target | Reported final | Signed error | Outcome | Post bytes |
| --- | ---: | ---: | ---: | --- | ---: |
| Increasing wrist | 4 degrees | 3.779297 degrees | -0.220703 degrees | REPORTED_SETTLED | 58,080 |
| Decreasing wrist | 0 degrees | 0.966797 degrees | +0.966797 degrees | TARGET_MISSED | 57,536 |

The first leg passed the unchanged tolerance/dwell criterion; the system then
captured a new baseline and issued the second command. The final miss held the
campaign. There were two confirmed writes (63 and 47 bytes), no trial errors,
no other-joint change, all handles closed and no pending IO. No retry, tuning,
offset, overtravel or tolerance change was applied. This demonstrates execution
and verification of both endpoints, NOT successful positioning at both targets.

Each endpoint had 221 final constant-position frames. Vendor tT load ranges were
-13..-9 at 4 degrees and 45..53 at zero. These are not calibrated torque values
and do not prove deadband, friction, backlash or successful fresh servo reads.
Final reported positions repeat the earlier observations. Target and approach
direction remain confounded; the next discriminating experiment is the same
target approached from opposite sides, not another identical 4-to-0 loop.

The offline reference model was corrected separately to match the verified
[official archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip):
command midpoint 2047, feedback midpoint 2048. See the correction at the top of
`WRIST_ACCURACY_INTERNAL_FINDINGS_20260914.md`. Under this unverified-for-the-unit
reference, residuals are -2 counts at 4 degrees and +12 counts at zero. The
one-count model correction cannot explain the actual zero-target miss.

Standalone verified export:
`software/runs/wizard-exports/campaign-8692dabab46d4826a5cac99ec2c76386/`.
Report SHA-256: `d2093816b428258aca84e6c952c84d335fde76e3702bd4e206789a670cae7341`.
Verifier: valid=true, reconstruction_consistent=true, endpoint completion=false.
Session export:
`software/runs/wizard-exports/wizard-20260914T224035615898Z-f24209f90ee542aea2411b21ed41157f/`.
Last reported wrist angle: 0.966797 degrees. No further movement attempted.

### Capture-capacity implementation update

New staging selects intent v3: post-command capacity is 81,920 bytes, with
98,304 bytes per leg and 196,608 bytes total. Only storage limits change;
the five-second window and motion/verification limits remain unchanged.
The shared decoder retains its historical 65,536-byte default, with explicit
bounded opt-in for v3 capture, admission, reconstruction and export review.
Synthetic throughput tests cover streams above the observed rate, including
captures above 64 KiB, and verify that byte exhaustion still produces a hold.
Old v1/v2 records are not migrated or reinterpreted.

1. Fix and version capture sizing using actual retained T1051 line sizes/rates;
   reproduce capacity, cleanup and retention in tests before any new motion.
2. Run one fresh reviewed two-leg campaign, with no correction, from an owned
   matching baseline; retain both complete endpoint windows.
3. Repeat identical nominal endpoints from both directions within the approved
   wrist envelope. Track signed residual, scatter, time to settle and other-joint
   drift. A single observation is insufficient to fit a compensation model.
4. Evaluate a direction/target-dependent correction only on separate validation
   runs. Do not simply apply +0.221° or −0.967° globally.
5. Use calibrated external vision and tool geometry before claiming physical
   workspace/typing accuracy. Joint telemetry alone cannot validate that claim.

The helper `software/scripts/bench_attended_campaign.py` invokes the actual
wizard action and never writes directly to serial. It supports only the two
nominal endpoints 0° and 4° in either order, preserves failed session exports,
requires operator setup confirmation, and does not retry a failed campaign.
