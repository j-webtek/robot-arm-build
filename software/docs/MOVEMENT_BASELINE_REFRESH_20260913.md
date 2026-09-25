# Fresh powered-arm baseline — 2026-09-13 14:47 UTC

## Outcome

After Jack's fresh confirmation of the secured, clear, adapter-powered USB
setup and accessible power shutdown, the public wizard completed identity
inspection and one bounded unsolicited-telemetry capture. No motion command
was issued. This is a communication/baseline result, not movement qualification.

- Expected controller found uniquely: CP210x `10c4:ea60`, serial
  `52E4E1E8337FEF119E92181CEDD322A4`, currently COM7.
- Capture operation: `operation-5ba387f8710f48108e3c8ac1773dd4d7`.
- New setup original: `operation-56b2793979cf43a8885020342f9cf9a1`.
- Captured 52,339 bytes; 237 complete pose records.
- Confirmed write bytes: **0**. Serial cleanup and process-tree exit confirmed.
- Export verification succeeded in
  `software/runs/wizard-exports/wizard-20260913T144719196445Z-d494ec349ba84cb5960346445a947f89`.
- Export manifest digest reported by verifier:
  `d7c36481cd0ff28b7badf76deef911067afd17dac6c091049a307ad1528f9c7c`.

## Offline framing review

The existing complete-frame parser was applied to the original native outcome,
using its retained host read windows. No further device access was performed.

- Original raw SHA-256:
  `78df25e7e94c674f4d7010452b1f60a82a38ad6dd84c7eb3c548ddd885d088f5`.
- Analysis byte interval: `[63, 52203)`; prefix 63 bytes and suffix 136 bytes
  remain retained and unobserved, not silently discarded or called valid.
- Analysis SHA-256:
  `2c64906d87e3487216c2e7ffa6aa776fb17942a5bcb4325119f80730af37a8bb`.
- Complete interval: 237 pose records, zero rejected or incomplete records.
- First and last reported pose agree: XYZ
  `(347.3156446, -3.196743424, 207.4284741)` mm; pitch `0.046019424`,
  roll `-0.003067962`, gripper `3.149262558` radians.
- First acquisition bounds: `[204435890000000, 204435906000000]` ns;
  last: `[204440734000000, 204440750000000]` ns.
- Device sample freshness remains unverified. Voltage, torque-switch fields
  and gripper load are absent. Matching endpoint reports do not prove every
  intermediate report matches or establish independently observed stability.

The earlier baseline XYZ was `(345.3513288, -3.178663578, 210.1326353)` mm.
The new reported position differs by approximately 3.34 mm. Do not reuse the
old pose as an exact movement origin or infer the cause from these captures.

## Software verification checkpoint

The completed regression immediately preceding this capture reported
**568 passed in 83.11 seconds**, exit code zero. Evidence:
`software/runs/endpoint-readiness-final-20260913-01.xml`.
These are software tests, not proof of hardware motion or physical stopping.

## Remaining work before the first commanded endpoint

1. Assemble the eight actual-unit reference originals identified in
   `MOVEMENT_LIVE_EVIDENCE_AUDIT_20260913.md`. This capture supplies a new
   baseline observation, not all engineering approvals.
2. Select and review one small, slow, noncontact route using current pose,
   full-arm/cable clearance, startup behavior and shutdown limitations.
3. Retain explicit compatibility decisions while leaving the installed firmware
   binary/version unknown; never substitute synthetic test evidence.
4. Configure the live service binding, complete its final confirmation path,
   and execute one bounded endpoint through the existing native coordinator.
5. Inspect the retained result before any return, repetition or speed increase.

The present capture process has ended and closed its connection. No worker was
left moving or waiting to send a queued movement. Setup records retain their
original timestamps and must not be refreshed merely to satisfy freshness gates.
