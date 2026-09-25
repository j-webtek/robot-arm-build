# First provisioned startup elbow trial

## Deliberate restart completed — 2026-09-18

After explicit user approval, one supported USB-only reset was sent using the
pinned esptool HardReset RTS sequence. No serial payload, bootloader connection,
flash write, challenge or servo command was sent. COM7 USB identity matched.
New boot `89dcfb9d20c27693caf3f46be6efefd7` reports stable IDLE / NOT_CONFIGURED,
zero records. Verified/replayed status exports:

- Before: `wizard-20260918T163115361623Z-a387df454bb34432b6db3939b7f7ba07`.
- After: `wizard-20260918T163120865407Z-2f343b6adaf043e8a06022ee67ff77f0`.

The consumed reset reservation is retained. The new boot's challenge has NOT
been requested; leave it untouched until the full powered trial is ready.
Motor-power restoration and stationary physical setup confirmation are next.

Status: offline plan builder tested; no command sent. Current hardware remains
USB-only, links supported, with its deliberately unused challenge expired.
Do not reset/re-arm automatically or infer motor power from USB connectivity.

## Runner checkpoint

`startup_first_trial_run.py` joins the frozen plan, verified preflight status,
durable boot-level claim, one challenge, prepared send and linked endpoint export.
It requires a matching IDLE / NOT_CONFIGURED boot before challenge discovery.
Keys are validated before device reads; plan export precedes the short lease.
After the single send it waits four seconds for the six-pair finite schedule,
then collects once. Nonterminal/incomplete data is inconclusive, not an automatic
poll/retry. Uncertain delivery permits this read-only collection but no resend.
Existing claims prevent another process from repeating the boot's trial.

The first-trial suites passed 11 tests, including accepted/uncertain delivery
with incomplete endpoint evidence and attempted duplicate execution. The earlier
native pipeline additionally exercises real authentication and successful endpoint
replay with a simulated servo bus. No physical trial is claimed by these tests.

CLI: `scripts/run_first_startup_trial.py --prepare-only --boot-id <simulation-id>
--command-id <review-id>` performs local-only plan validation. This was run with
an explicitly synthetic boot and succeeded. Live mode requires the separate
`--authorized-one-move` flag plus the actual fresh boot/command IDs. It verifies
the encrypted installed-image binding and loads the private key before creating
LAN adapters. Neither mode resets the arm or changes servo configuration.

Do not run live mode against the currently expired boot. The next physical step
is a deliberate supported USB-only controller restart, followed by coordinated
motor-power setup before challenge discovery. No reset occurred in this checkpoint.

## Proposed single command

`startup_first_trial.build_first_trial` binds the exact provisioned configuration
digest and an explicit boot/command identity. Default origin is SIMULATION.
The proposed absolute target is servo 14, count 2727. This is an experiment target
near the historical 2723 observation, NOT a claim about the current position.
Pinned conversion is `round(rad / (2*pi) * 4096) + 1024`; the chosen radians lie
at the centre of count 2727. A native test compiles the hash-verified Waveshare
function bodies and confirms the conversion without calling the servo bus.

- Elbow only; speed 20, acceleration 1 in native command units.
- No compensation: requested and transmitted target are identical.
- Native fresh-position delta must be at most 8 counts; otherwise no write.
- All seven position windows and zero-goal startup requirements remain enforced.
- Two stable scans and direct mode/torque checks precede dispatch.
- Six post-write target/position pairs at 500 ms intervals, maximum pair 10 ms.
- Endpoint tolerance 2 counts, settling observation 1 s, maximum sample gap 600 ms.
- No retries, return movement, reverse move or second command in this trial.

The 8-count limit is relative to fresh measurements inside native admission, not
to the historical observation. A target already reached may require no physical
motion; arrival alone must not be described as verified displacement. Preserve
the measured before/after change and requested change separately. This does not
prove Cartesian positioning or stylus accuracy.

## Remaining execution preparation

1. Assemble/export the complete proposed plan and load the private key before
   requesting the short challenge. Bind the plan to the actual new boot ID, not
   the expired boot or a simulated ID. Never export the key or signed request.
2. Confirm the deliberate startup/power procedure for the supported arm; no
   automatic reset of the existing fault and no forced joint repositioning.
3. Establish motor power and clear supports appropriately before any live motion
   attempt. USB-only is not a motor-powered test setup.
4. Fetch one challenge only when ready to send. Perform the existing pre-send
   persistence and one-use claim, then exactly one authenticated startup request.
5. Collect terminal records and export/replay with the startup assessment path.
   Report acceptance/ACK/target readback/position arrival as separate results.
6. Stop on invalid feedback, mismatched control state, too-large fresh delta,
   uncertain delivery, non-arrival or export failure. Do not use a rejected trial
   as permission to widen windows or bypass torque/mode requirements.

Nine focused first-trial/native-pipeline tests passed. The trial builder has no
network, key, reset or dispatch operation. These tests do not constitute an actual
movement or proof that the controller's current pose satisfies the policy.
