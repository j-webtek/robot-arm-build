# RoArm-M3 Pro movement characterization

Status: active objective; no motion test completed or authorized by this file.
Detailed implementation queue and acceptance criteria:
[Implementation playbook](MOVEMENT_CHARACTERIZATION_IMPLEMENTATION_PLAYBOOK.md).
Requested by Jack: compare various poses and speeds using collected telemetry
to optimize movement. This supersedes general wizard completion as the immediate
work priority, while retaining its connection and safety requirements.

## Starting evidence

Timestamped capture implementation: the collector now emits telemetry observation
v2 with up to 512 compact per-read windows: start/end byte offsets and monotonic
host-call start/finish times. The result validator checks exact byte coverage,
read counts, ordering and containment within the observation interval. These are
host read intervals, not device sample timestamps or proof of fresh data.
Forty-five offline regression tests passed, including full-capacity IPC framing.
The operator-confirmed physical v2 capture at 23:24 UTC succeeded through the
public wizard: 56,384 bytes, 255 complete parsed pose samples, 323 timestamped
reads, zero writes, clean serial closure and verified export. See
`MOVEMENT_TELEMETRY_TIMING.md` for evidence and limitations. Earlier captures
remain untimed and must not be backfilled. No movement command was sent.

Offline baseline analysis is recorded in `MOVEMENT_BASELINE_20260912.md`.
All 255 complete parsed samples contain identical core pose values. This is not
proof of zero physical noise or fresh measurement. Timestamped receive evidence
is now available; confirmation that a small approved movement produces corresponding
telemetry is still pending. The pure baseline analyzer and framing
tests passed (22 tests); no new hardware access or motion occurred in this increment.

- Control USB endpoint observed as COM7, VID/PID 10c4:ea60,
  serial 52E4E1E8337FEF119E92181CEDD322A4. Rediscover by identity each launch;
  do not assume the COM number remains fixed. Prior COM6 was the other bridge.
- Latest five-second zero-write capture: 56,384 bytes, 255 complete parsed pose
  records, no writes, serial resources closed, public operation SUCCEEDED.
  The earlier 23:05 public IPC failure remains preserved; the 23:24 run is a
  separate successful post-fix capture, not a revision of that failure.
  The 256-record parser limit left 3,233 retained bytes unparsed. Address this
  coverage limit before using longer captures for movement characterization.
- Input is unsolicited/buffered T1051, not transaction-correlated feedback.
  Missing voltage and torque-state fields are unknown, not acceptable defaults.
- No software-commanded movement demonstrated. Final board/camera/tool geometry
  is not calibrated. Initial characterization must be non-contact and exclude
  keyboard, phone, board and nearby objects from every swept path.
- Existing RoArm client has a permit-gated Cartesian interface; do not bypass
  the held physical transport or assume a permit is sufficient commissioning.

## Execution sequence and gates

1. **Finish receive baseline.** Run the fixed public zero-write capture with
   fresh setup confirmation. Export and verify originals, identify frame rate,
   gaps, malformed frames, missing fields, truncation and stationary joint noise.
   Add host monotonic receive timestamps; do not claim device-time precision.
2. **Build the test planner and simulator.** Represent each trial by baseline,
   target, command family, firmware speed/acceleration parameters, dwell,
   timeout, repetitions and stop criteria. Freeze a reviewed matrix before live
   use. Simulate travel, swept clearance and joint/reach limits; unknown physical
   geometry is an explicit blocker, not a successful collision test.
3. **Qualify a single slow move.** Verify the official command semantics for
   installed-model compatibility. Show exact target and predicted travel in the
   wizard. Require current pose, safe swept volume, operator presence and a
   practical power-off procedure. Send one small move only, then observe it.
   Opening USB and power cycling can themselves move the arm. Host cancellation
   or serial close is not a robot emergency stop. Do not automatically return
   home, release torque or issue recovery movement on a fault.
4. **Repeatability trials.** Only after the first move matches observation,
   repeat a small reviewed pair of poses with dwell at each endpoint. Each
   return is a separately checked move, not an unconditional cleanup action.
   Stop if telemetry, tracking or operator observations contradict expectations.
5. **Progressive speed/pose matrix.** Start with low settings, then increment
   one variable at a time. Expand from short travel to representative mid-workspace
   poses and, only when geometry supports it, longer paths. Avoid singularities,
   joint limits and maximum reach during initial qualification. Predetermine
   finite trial counts; never automatically search toward hardware limits.
6. **Analyze and choose settings.** Rank only measured successful trials.
   Produce a recommended conservative speed/acceleration and settle policy for
   tested regions. Separate free-space transit from future contact approach;
   neither typing speed nor touch force is established by this campaign.

## Data retained for every trial

- Campaign/trial IDs, source/configuration hashes, USB identity, firmware history,
  payload/tool description, geometry assumptions and operator approvals.
- Exact outbound bytes, host send/completion times, original inbound bytes,
  per-read monotonic times, framing offsets, parsed values and missing fields.
- Initial/target/observed positions, speed coefficient and acceleration setting
  in their documented native units. Do not relabel a coefficient as mm/s.
- Termination reason, acquisition limits, controller/transport errors, resource
  cleanup and separate operator observation. Failures are retained, never retried
  invisibly or replaced with a later success.

## Metrics and selection rules

- Position/joint endpoint error; peak observed overshoot; repeatability spread.
- Time to enter and remain within a justified tolerance; observed settling time.
- Command-to-observed-change latency as a host-side estimate, with buffering and
  missing device timestamps disclosed. No claim of exact servo response latency.
- Sample cadence/gaps, malformed/partial records and sample coverage per motion.
- Loads where reported, without treating raw servo load as calibrated contact force.
- Speed differences must exceed baseline noise and measurement uncertainty to
  support an optimization claim. Choose repeatable low-error settings over the
  shortest isolated completion time; publish applicability limits and failures.

Numeric motion limits, tolerances, speed ladder and repetition counts must be
selected from baseline evidence, reviewed hardware/firmware specifications and
verified clearance before live execution. They are intentionally not guessed here.

## Deliverables and completion evidence

- Wizard campaign preview, explicit arming, trial progress, fault/stop reporting,
  telemetry plots and verified export to software/runs/wizard-exports.
- Deterministic tests for matrix bounds, stale/absent telemetry, partial frames,
  overshoot, timeout, cancellation, endpoint mismatch and non-replay behavior.
- Actual staged pose/speed campaign results and readable comparison report,
  with raw evidence and justified recommended settings for the tested setup.
- Clearly separate simulated, offline-reanalyzed and actual physical results.

The goal is not complete until an approved finite live campaign and its analysis
are finished. If physical prerequisites are missing, continue software/simulation
work where useful and pause the affected physical stages explicitly.
