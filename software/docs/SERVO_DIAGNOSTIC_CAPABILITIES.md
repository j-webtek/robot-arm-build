# Diagnostic capabilities: evidence-scoped inventory

Initial inventory, 2026-09-17. Scope is the installed public interface, not a claim
that the underlying servo cannot support a feature. UNKNOWN means not established;
UNTESTED describes the new software contract before actual device integration.

| Capability | Status | Basis / limitation |
| --- | --- | --- |
| HTTP T105 positions and loads | SUPPORTED | Retained raw trial and passive captures; host transport times only |
| Host command payload/receipt correlation | SUPPORTED | Payload/response hashes in native exports; not bus execution |
| Installed firmware version | UNKNOWN | Served interface differs from pinned newer reference; version endpoint previously 404 |
| Exact installed servo register map/library | UNKNOWN | Product model alone is insufficient to select register operations |
| Controller command ID and boot-scoped dispatch timestamp | UNKNOWN | Not present in retained numeric telemetry |
| Actual bus write result and computed target record | UNKNOWN | Not exposed by reviewed public command definitions |
| Successfully acquired servo goal-register readback | UNKNOWN | No reviewed deployed getter; do not substitute host target |
| Per-servo acquisition success/device timestamp | UNKNOWN | Not present in current feedback; identical packets are inconclusive |
| Actual moving state/speed/error flags | UNKNOWN | No reviewed installed diagnostic route |
| Torque-enable, voltage | UNKNOWN | Absent from retained packets despite newer reference examples |
| Torque limits, mode, temperature and PID readback | UNKNOWN | Must verify exact servo/interface support before reads |
| New v1 diagnostic trace contract on actual arm | UNTESTED | Offline software only; no firmware deployment |

Sources: `ELBOW_REVERSE_DIAGNOSTIC_DECISION.md`, the exports referenced there, and
`TIP_REVERSE_FIRMWARE_DIAGNOSIS.md`. This inventory is an explicit starting point,
not completion of compatibility investigation. No feature is marked UNSUPPORTED
solely because it is absent from a packet.

## Minimum viable diagnostic path

Reference investigation now identifies a candidate vendor-library goal-register
readback path and fresh feedback block. See
[SERVO_READBACK_REFERENCE_REVIEW.md](SERVO_READBACK_REFERENCE_REVIEW.md) for pinned
source hash, register widths/sign handling and the cached ReadMode(-1) defect to
avoid. These are reference capabilities; installed statuses above remain UNKNOWN.
Separate target/position acquisition times and signed raw decoding now exist in
the offline v2 trace. Installed producer identity and capability binding remain
unverified; that implementation does not promote any UNKNOWN entry above.

Need an installed-compatible producer of correlated controller dispatch and fresh
servo acquisitions. Verify readback support and register semantics first. Keep raw
position count, conversion version, read validity and target readback distinct.
New host fields cannot recover evidence that firmware never exposes.

## Implemented offline contract slice

`rocell.application.servo_diagnostic_contract.assess_trace` accepts the versioned
`rocell.servo_diagnostic_trace.v1` object with command, dispatch, samples and frozen
policy. Angles are radians, positions counts and device times microseconds scoped
to one boot. Single-joint T101 payload hashes and dispatch settings must match.
Acquisition sequences and time intervals must increase; failures cannot contain
cached position values. Readback is separate from the command. At least three
eligible samples spanning the configured settling duration are required.

This slice uses caller-supplied counts and servo mappings; it does not certify the
angle/count conversion or installed mapping. It does not authenticate device
provenance. SIMULATION/DEVICE_CAPTURE labels do not grant hardware authority.
Every result retains provenance_verified=false and progression_authority=false.
Native adapters must establish capabilities/provenance separately before use.

Implemented next slice: bounded UTF-8/JSON decoder with 1 MiB and 2000-sample limits,
duplicate/nonfinite/unknown-field rejection and exact-byte SHA256. Deterministic
synthetic producer covers arrival, delayed arrival, bus failure, wrong readback,
failed position read, unsupported readback, stationary state, reboot and repeated
sequence. Decoder/contract/scenario tests: 46 passed. Synthetic mappings are not
installed calibration; the decoder does not authenticate its producer.

Export/replay increment: `servo_diagnostic_rehearsal` and
`software/scripts/rehearse_servo_diagnostics.py` publish named synthetic traces,
preserve exact bytes via base64/hash and recompute the outcome offline. All nine
scenarios were exported/replayed in the workspace; 58 focused tests passed. Failed
trace validation is retained as rejection, not a physical fault verdict. This is
not yet a registered wizard action or a live acquisition adapter.

Wizard integration now registers simulate_servo_diagnostics on the arm page and
automatically exports/replays the selected scenario. The dedicated app.js result
card labels all values synthetic and hardware NOT QUALIFIED. Service and inert-DOM
tests cover arrival, stationary, missing readback and rejection, including invalid
authority display. No real-browser visual QA or native acquisition is claimed.

Remaining: capability binding, individual health-field
semantics, controller rejection records, additional simulation scenarios, wizard
broader UI/HTTP acceptance and actual instrumentation. Do not
mark those complete based on the initial contract unit tests.

Latest reporting increment: `servo_diagnostic_summary` retains separate desired,
wire, final goal-register and final position values/residuals. The wizard displays
these stages and marks controller receipt, torque enable and mode unavailable.
V2 raw feedback health fields retain read validity and raw units in the export.
Replays recompute new summaries while preserving historical exports. Focused suite:
135 passed. Verified failure-case export:
`wizard-20260918T004817692168Z-8395f10cb72142fc980dec883572f5e4`.
No live diagnostics or hardware changes are implied.
