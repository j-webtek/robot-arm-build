# Servo acquisition telemetry — proposal, not installed protocol

Status: simulation-only. No Waveshare T command is assigned. No serial adapter,
native admission, firmware deployment or automatic motion uses this proposal.

The pinned reference firmware can preserve cached position after a failed read.
Host receive timing cannot identify that condition. A future supported telemetry
extension must report what was actually acquired, not merely re-label its cache.

## Proposed report

`rocell.proposed_servo_acquisition.v1` contains:

- `boot_id`: a new 32-character lowercase hexadecimal identifier per boot.
- `command_sha256`: hash of the exact accepted command; association is not an
  authentication claim or proof that the servo accepted the goal.
- `command_applied_us`: fixed controller monotonic time for this command epoch.
- `report_sequence`, `published_us`: strictly increasing report counter/time.
- `joints`: exactly b, s, e, t, r, g. Each contains `read_ok`, `sequence`,
  `acquired_us`, `position_rad`. Acquisition sequence/time advance only after
  a new successful servo read; publication must not advance a cached sample.

The model requires all six acquisitions after the command epoch and no more
than 100 ms old at publication. This is a provisional diagnostic bound, not a
validated hardware-rate requirement. Counter/time rollover or restart requires
a new reviewed epoch; never infer continuation across it. A failed read is a
failure even if its cached angle happens to equal the target.

`SimulatedServoFreshnessMonitor` accepts at most 512 reports of 8 KiB each,
keeps only the last decoded report, and holds permanently on invalid input.
It does not supply automatic rearm. Legacy T1051 is rejected, not upgraded.
Even consistent reports leave installed support, actual freshness and motion
authority false: the model cannot establish truthful device provenance.

## Required integration evidence

1. Identify installed firmware and vendor-supported diagnostic capability.
2. Review command hashing, boot identity, clock semantics and per-servo success
   handling against that implementation. Expose actual goal, speed, voltage,
   load and temperature separately when available; never invent missing values.
3. If an extension is needed, review a versioned firmware design and obtain
   explicit deployment approval. This proposal authorizes no flashing.
4. Replay acquired bytes through the host validator, then test bus-read failure,
   controller reset, host buffering, partial joint success and command rejection.
5. Bind evidence to the owned connection and exact campaign leg. Bound host-side
   delay too; device-relative freshness alone cannot detect stale transport.
6. Independently satisfy physical stop/watchdog and workcell release requirements.

Current tests cover the host-side proposed schema only. They do not complete
any installed-firmware, servo, transport or unattended release qualification.
