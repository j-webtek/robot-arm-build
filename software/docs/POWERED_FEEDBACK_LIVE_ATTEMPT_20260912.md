# First powered wizard attempt — 2026-09-12

## Outcome

**Failed before writing T105. No motion command sent. No automatic retry.**

Jack confirmed the secured, stationary, clear, supplied-adapter-powered and
USB-connected setup. The real `ArrivalWizardService` public actions performed
inventory, candidate review, native identity correlation, operator startup report,
one powered feedback attempt, and diagnostic export. No mock runner was used.
Startup motion for this recording was marked unknown rather than inventing a
new observation. Firmware history remains operator-reported unchanged since delivery.

Before dispatch, a UI conflict was corrected: metadata-only discovery no longer
requires a false power-disconnected report for a powered arm. The old optional
power report remains accepted; metadata discovery never grants port-open or
motion authority. New public-service tests exercise this route without devices.

## Actual evidence

- Session: `wizard-11fca8b61998407bb7b35147b5ddaa20`.
- Source at dispatch: `1849b58bdccf8c644fb12067b09256b703fae89a25c91f86c5592c914ab34bf4`.
- Startup original: `operation-c5dc85c1448e421aa89a97829fff1459`.
- Attempt: `operation-174bfe556e3b42bca7a8e73f569bc870`.
- Endpoint: COM6, VID/PID `10c4:ea60`, serial `A02C8734397FEF11A7321C1CEDD322A4`.
- Native metadata correlation succeeded; settings readback verified.
- One device open; confirmed outbound bytes **0**; robot commands **0**.
- Observation errors: `REUSED_IO_TOKEN`, `CLEANUP_UNCONFIRMED`, `CLEANUP_UNKNOWN`.
- Serial owner retained pending I/O and three unresolved resources; it did not
  prove serial cleanup. Process-tree exit was independently reported confirmed.
  Do not rewrite process termination as a successful serial close or power check.
- No feedback pose or voltage received. Camera inventory found Arducam B0477;
  this attempt did not open or test its stream.
- Durable outcome SHA: `2f93c9e9cb89c6709b6bc5b1fdc856bb0433e8f8452b90c4fc51f4c4b8b55a5e`.

Verified export under the assigned workspace folder:

`software/runs/wizard-exports/wizard-20260912T223237635074Z-85607d7fd05a441083b03cc97181e7a0`

It contains all prepared/consumed/claimed/outcome originals, raw native stdout and
stderr, operator report, native metadata, public result and event log. Export
verification returned `valid: true`; manifest SHA reported by verifier:
`4b7ae969f639e1bf64d75cbf48b905c48232d2e3d3ce6ea8ac22a0530bc0c7a6`.

## Root cause and offline correction

`WindowsPoweredFeedbackSerialApi.complete_io` and `cancel_io` incorrectly called
the validator for a **new, unsubmitted** token. Native submission marks the token
submitted and pins its buffer; completion consequently rejected precisely the
state it must accept. Cancellation then encountered the same mistake.

Validation now separates fixed payload/type validation, fresh-submission
validation, and exact owner/pinned-token validation for completion/cancellation.
This preserves the one-write limit, rejects foreign/copied/completed tokens, and
keeps buffers pinned until native completion establishes a terminal result.
The physical attempt was not repeated and its failed records were not modified.

Offline evidence:

- 59 tests passed: metadata acknowledgement, native-arm public integration,
  powered-feedback public integration. Basetemp `pytest-powered-metadata-20260912-02`.
- 123 tests passed: powered native facade, shared nonpurging backend, passive
  fake-DLL calls and feedback observation. Basetemp `pytest-powered-token-20260912-01`.
- New fake-DLL cases cover immediate/pending read and write completion,
  cancellation/abort, foreign tokens and forbidden resubmission. No real DLL
  endpoint or received-unit behavior is established by those tests.
- Post-fix isolated-worker regression: **86 passed in 18.59 seconds** across
  native package/import checks, registration, result wire validation, rehearsal
  package, shared process supervisor and public live-action integration.
  Basetemp `pytest-powered-postlive-package-20260912-01`. These tests use import
  checks, invalid physical requests, incapable rehearsal or simulated outcomes;
  they do not dispatch a valid live hardware request. The operator observation
  after the first port-open event is still pending; no live retry occurred.

## Next gate

Ask whether the arm stayed stationary during the actual port-open event and
confirm the operator is still present with a secured, clear, powered setup.
Only then prepare a new explicitly authorized attempt through the wizard.
Do not replay the consumed journal or relabel this attempt successful.
Calibration, bounded motion, keyboard presses and phone contact remain incomplete.

## Second explicitly confirmed attempt — 22:38 UTC

Jack answered: "yes stationary, yes usb and powerr connected" to the pending
stationary/operator-present/clear-area question. A new public wizard session
repeated metadata discovery and exact known-unit correlation, recorded the report,
and consumed one new attempt. No failed journal was replayed.

- Session: `wizard-b2fca9d765224a48a7c0db89d19290ab`.
- Source: `3baa76855cc216e8d11fdb215bcb94623afe141bfa9abb9d77608fdd25a27324`.
- Startup operation: `operation-1d66a119a384481492e0672948ab82c4`.
- Attempt: `operation-9fe7cefb19cb4f6c8f3bd128bf7ab1e6`.
- Result: **FAILED / FEEDBACK_DEADLINE_EXCEEDED**.
- One COM6 open, verified 115200/8N1 configuration, one completed 10-byte
  `{"T":105}\n` write. This proves host-side write completion, not firmware receipt.
- Five-second observation: zero startup, response or late-cleanup bytes;
  no communication errors recorded. No pose/voltage obtained.
- All three serial resources explicitly closed; no pending I/O remained.
  Native cleanup and supervised process-tree exit both confirmed.
- Outcome SHA: `5fcda1834ae6760055a240317294f7a92021edda0469f98f9e4b98eb58689633`.
- Verified export: `software/runs/wizard-exports/wizard-20260912T223807412964Z-42c395a047e64e34b96009f9db646b1e`.
- Export manifest SHA: `ca2802f1eaaba2f2870440e6f8346d238d7b33b255a5ff447f2ba41560b9bf83`.

The previous token-lifecycle defect did not recur. This is progress in actual
transport lifecycle validation, **not** successful robot feedback or qualification.
No movement command, settings command, firmware flash or automatic retry occurred.

Official documentation rechecked after this result:

- https://www.waveshare.com/wiki/RoArm-M3 — serial default 115200.
- https://docs.waveshare.net/RoArm-M3/JSON-Command-Control/ — USB serial uses
  driver-board Type-C interface number 9; default AP address 192.168.4.1.

Next diagnostic: visually verify which board USB socket is connected and the
current OLED state without unplugging or restarting. The no-reply cause remains
unresolved; do not label the arm defective or blindly change baud, handshake,
firmware, response deadlines or transport. A valid Windows write does not prove
that the ESP32 application received or processed the command.

### Follow-up: photo declined; software investigation continued

Jack requested proceeding without a photo. A photo is not a software prerequisite
and has not been added as a gate. No third live request was made.

Official sources confirm both the T105 feedback command and 115200 default. The
board documentation lists separate CP2102 bridges for LiDAR and ESP32. Therefore
the matched VID/PID, unit serial and COM6 prove USB endpoint continuity, not the
application on the far end of that bridge. This is a possible explanation for
silence, not a diagnosed wrong-socket conclusion.

- https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control
- https://www.waveshare.com/product/robotics/robot-arm-control/roarm-m3.htm

The public result now distinguishes `POWERED_QUERY_WRITTEN_NO_REPLY` from a generic
incomplete attempt, only when retained evidence shows a completed 10-byte write,
zero startup/response/cleanup input, a sole response-deadline error, successful
process lifecycle, confirmed serial cleanup and durable outcome. It remains
FAILED and grants no connection, movement or retry authority. Missing results,
partial replies and cleanup/persistence failures cannot acquire that diagnosis.
The historical exported result is unchanged.

Validation: **13 passed in 4.40 seconds**, no hardware: new outcome-classification
tests and public live-action integration tests; basetemp
`pytest-powered-noreply-20260912-01`.

The next discriminating physical check can be a simple operator check of the
socket label (ESP32/USB UART, board interface 9), without supplying a photo.
Do not unplug, reset or switch cables until the desired change is explicit;
USB changes can trigger startup movement.

## Third attempt: switched board socket, telemetry received — 22:46 UTC

The operator supplied photos; comparison with Waveshare's actual board diagram
showed the occupied socket appeared to be LiDAR (8), with the ESP32 socket (9)
immediately beside it. Jack moved the cable and explicitly confirmed external
power ON, stationary arm and clear area before this attempt.

Read-only Windows enumeration after the switch showed COM6 absent and COM7
present, VID/PID `10c4:ea60`, serial `52E4E1E8337FEF119E92181CEDD322A4`.
The public wizard independently rediscovered and reviewed this new identity;
the former COM6 serial was not silently reused.

- Session: `wizard-2e9754e7cdbf427cb6f95e222544948b`.
- Source: `cf1d67ff9b0eaabc3dc625d108f64ef4ff9f95af84d77d6c8189e8d9f6023d07`.
- Startup: `operation-4ac41780b27a428cad2c18a4eb53f534`.
- Attempt: `operation-c52f0c1296e84272b0ff3061e2dfb288`.
- Public result: FAILED / `PREEXISTING_INPUT`; **zero outbound bytes**.
- Actual startup capture: 256 bytes, SHA
  `2cb2332710b8f5bf0180aad571302bbb06063f71f258d5a206a78468446c46d7`.
- Bytes begin in a partial frame, include a CRLF boundary and the start of
  another `{"T":1051,...}` frame with x/y/z and joint-angle fields. Neither
  captured fragment is a complete validated sample. Do not use its numeric
  fields as calibration or fresh command-response evidence.
- One native open/read; all three resources closed, no unresolved pending I/O,
  no communication errors, supervised process-tree exit confirmed.
- Outcome SHA: `a4a75f4d147009ebd67f7f845d7c9944b52584b0cf66536a4b88eea2b8360612`.
- Verified export: `software/runs/wizard-exports/wizard-20260912T224656814346Z-7ab4d175df3f4160a0bfd1ae07b67799`.
- Manifest SHA: `06ebdd4430f6c88ade0583bb0d687988e88ad4c579e10e684ff37775da09e5dd`.

This is positive evidence of robot-protocol input on COM7. It explains why the
strict quiet-before-query workflow cannot yet proceed there. The input may be
ongoing unsolicited feedback or buffered telemetry; a bounded observation is
needed to distinguish these, without clearing buffers or changing firmware.

Next software work: a separate powered zero-write telemetry observation using
the existing owned native worker, identity recheck and durable evidence pattern.
Frame incrementally across reads; retain partial prefix/suffix and all original
bytes, validate complete samples, label them unsolicited, tolerate the observed
firmware's optional-field differences without inventing missing voltage/torque
state, and never promote these samples into query replies or motion permission.
Do not disable streaming or send initialization/movement merely to satisfy the
current one-request test. Actual motion/calibration/contact qualification remains
incomplete. No automatic retry followed this attempt.

### Offline telemetry framing implementation

Added `software/src/rocell/arm/telemetry_stream.py`: incremental LF/CRLF framing,
64 KiB capture cap, 4 KiB line cap, 256 parsed-record cap, raw bytes/SHA/base64,
record offsets, explicit rejected lines and retained unfinished/unparsed suffix.
Oversized input chunks are rejected atomically rather than silently truncated;
a future collector must limit reads to the remaining byte capacity. Record-cap
overflow retains bytes without continuing unbounded decoding. Missing voltage
and torque fields stay missing. Only a frame containing all core pose fields
counts as a pose sample. No freshness or query-response claim follows parsing.

Tests: **15 passed in 0.27 seconds**, basetemp
`pytest-telemetry-stream-20260912-01`. Covered byte fragmentation, multiple frames,
invalid prefixes, missing fields, nonfinite/duplicate/nontext/wrong-type input,
overlong lines, buffer/record limits, sealed snapshots and empty captures.

Actual evidence reanalysis (no hardware access): decoded the retained native
stdout from the third-attempt export, verified the startup blob byte count and
SHA, fed those exact bytes in seven-byte chunks, and verified lossless retention.
Result: offset 0–90 rejected as malformed JSON; offset 90–256 unterminated suffix;
**zero complete pose samples**. This does not fabricate missing frame contents.

Remaining: implement the explicitly zero-write powered collector, source-pinned
worker/journal integration and public wizard presentation, then perform a new
operator-confirmed capture. The pure parser alone is not a live stream feature.

### Zero-write collector increment (offline only)

Added a telemetry-purpose variant of the immutable powered intent, with zero
write attempts and zero outbound bytes. Access to `outbound_line` raises; the
native API independently rejects query writes for this purpose. Existing query
lifecycle rejects telemetry intents before opening a port. No change to normal
query write limits or acceptance of preexisting input.

Added `powered_telemetry_observation.py`: shared admitted connection owner,
five-second collection window, 64 KiB input capacity, 512 read-call cap, 256-byte
reads, explicit stop reasons, cancellation, resource cleanup and raw late-cleanup
input retained outside the parsed observation. `CAPTURED_CLOSED` describes capture
completion, not feedback validity: empty captures remain zero-sample outcomes.
Complete frames are explicitly unsolicited/buffered and grant no motion authority.

Validation: **50 passed in 17.56 seconds**, basetemp
`pytest-telemetry-collector-20260912-02`: collector, intent, native facade and
existing query-observation tests. Native write-guard coverage uses a test-only
request injection with the DLL loader forbidden; it is not physical admission
evidence. Collector tests use memory I/O only. No further COM7 open occurred.

Still required before actual capture: child dispatch and result codec branch,
archive dependency inclusion, public coordinator/action/export integration and
tests. The current native child continues to choose the query lifecycle, which
rejects telemetry-purpose input before opening; it cannot yet run this collector.

### Telemetry worker integration (supersedes prior child limitation)

The fixed native child now dispatches telemetry-purpose intents to the zero-write
collector after the same source-pinned registration, consumed-original claim and
fresh endpoint checks. Query-purpose requests still enter the existing query path.
The archive contains the telemetry framer, collector and result validator; its
isolated import check explicitly imports these with native/process access forbidden.

Result validation reconstructs the capture from original bytes and compares the
complete interpretation, including frame spans, optional-field absence and sample
counts. It rejects fabricated pose/freshness, bytes/hash mismatch, nonzero writes,
early successful observation-window claims, unconfirmed cleanup and substitution
between query and telemetry schemas. Raw late-cleanup bytes remain separately
bounded and hashed, never parsed as observation-window samples.

Tests: **79 passed in 14.86 seconds**, basetemp
`pytest-telemetry-worker-20260912-03`: telemetry/native wire, native package and
registration, shared supervisor. Wire success fixtures are memory-capture results
converted to physical-shaped test records, not actual device observations.
No valid physical request or additional COM7 open was performed.

Remaining immediate work: coordinator/public-action selection, compact telemetry
result UI and original export coverage, then operator-confirmed live capture.
Calibration, motion and contact qualification remain incomplete.

### Public wizard telemetry integration

Added `capture_powered_arm_telemetry` / "Capture arm telemetry (no commands)" to
the shared browser/terminal action catalog. It requires the same fresh powered
operator report, current native USB review, unchanged firmware acknowledgement,
source-bound ticket and single powered attempt per launch as the query action.
Either action consumes that launch's attempt slot; switching actions is not a retry.

The coordinator maps this action to the zero-write intent. Public presentation
is compact: sample count, captured byte count, latest observed known pose/optional
fields, missing optional fields, closure and persistence outcomes. It explicitly
denies sample-freshness verification and motion permission. Empty or partial-only
captures return FAILED / `NO_COMPLETE_TELEMETRY_SAMPLE`, even when the underlying
capture process exited normally. Complete raw records remain in native exports.

Tests: **16 passed in 11.48 seconds**, basetemp
`pytest-telemetry-wizard-20260912-01`: public telemetry action, existing query
action, no-reply publication. Real service/coordinator/filesystem with a simulated
worker result; no actual child claim or COM7 open. Tests verify zero-write intent
selection, data/empty outcomes, mode/setup gates, shared attempt limit, and exact
native stdout recovery from exported base64 chunks. Existing query tests cover
changed-setup ticket invalidation and persistence-failure publication.

Next: obtain fresh current setup confirmation and run this action once on COM7,
serial `52E4E1E8337FEF119E92181CEDD322A4`; inspect and export actual samples before
any bounded-motion/calibration work. No live capture was run during implementation.

## First full zero-write telemetry capture — 23:05 UTC

Jack explicitly confirmed current operator presence and secured/stationary,
adapter-powered/ON, USB-connected, clear-area setup. The actual public telemetry
action ran once on the reviewed COM7 identity; no retry occurred.

- Session: `wizard-1a35531db00c4c7d9d6753629df30cc5`.
- Source: `027d06830f8b980fce352ce1a412a4d89d5b5bcda4ddd62d4d94c1ec63c146ea`.
- Startup operation: `operation-146cebee43ac49fd91a622c50e88b7b9`.
- Capture operation: `operation-531fb7e94a254e3ca988eec2394af57c`.
- Native result: `CAPTURED_CLOSED`, no errors, five-second observation window.
- 56,320 received bytes; zero outbound bytes; three resources closed; no unresolved
  pending I/O. Supervised process exited normally and tree exit was confirmed.
- Public operation: **FAILED**, supervisor `IPC_STRUCTURE_LIMIT`, not device silence.
- Native stdout: 192,705 bytes, SHA
  `647ee418f790c45f062d00bf48726c4fcf4e97e209c6046a1d36f262d2ff6006`.
- Outcome SHA: `66519dd524cd921cd671d04bf7058f27cf62c6eab1d0f2dbdac338bf806b87e2`.
- Verified export: `software/runs/wizard-exports/wizard-20260912T230532370345Z-b8bf9b50fbe14fe9b4f4390340712601`.
- Export manifest SHA: `8e263b6e56f36a6b9c28ddc5c6a6d2008857041db43a976d7a7b3d5bd46f5e3a`.

Offline reconstruction from that exact saved stdout verified its SHA and rebuilt
the capture byte-for-byte: **255 complete pose samples**, one rejected leading
line. The 256-record parsing cap left offsets 53,098–56,320 retained but unparsed.
The latest *parsed* sample reports x=345.3562001, y=-5.298113331, z=210.3949988 mm,
plus all core joint angles. These are robot-reported coordinates, not board
coordinates. Voltage `v`, gripper load `tG` and torque-switch fields were absent;
none were fabricated. Buffered versus newly emitted sample timing is unverified.

### Report representation fix and validation

The raw report fit the byte limit but repeated hundreds of pose dictionaries,
exceeding the shared 4096-node decoder limit. Keep that global limit intact.
`compact_capture` now transfers all original bytes, counts, tail coverage and one
latest parsed pose record; the parent reparses original bytes to verify the entire
compact interpretation. Full per-frame analysis remains reconstructible from raw
bytes, without transferring every repeated dictionary through IPC.

Tests: **48 passed in 29.26 seconds**, basetemp
`pytest-telemetry-compact-20260912-01`: framer, full-capacity IPC regression,
telemetry collector/wire, public telemetry/query integration and native packaging.
No hardware in tests. Offline transformation of the actual saved report produced
85,605 bytes, passed the unchanged strict IPC decoder and telemetry validator
against the retained intent, and preserved all 56,320 received bytes. This was
offline reanalysis, not a rerun or revision of the original failed public record.

The received-unit telemetry milestone now has actual sample evidence. Successful
post-fix end-to-end public publication remains to be confirmed on a later explicit
capture. Motion, command-response qualification, arm-to-board/tool calibration
and keyboard/phone contact remain incomplete. No movement command was sent.

## Successful timestamped public capture — 23:24 UTC

After current operator confirmation, session
`wizard-f176d2fbbe994cba9c46b5b5fd4e5a58` rediscovered and reviewed the ESP32
identity and recorded supplied-adapter/USB/secured/stationary startup evidence.
Operation `operation-a5afb35b43a847e58ada659c61121297` then completed a real
five-second zero-write capture: public SUCCEEDED / UNSOLICITED_TELEMETRY_CAPTURED,
native CAPTURED_CLOSED, 56,384 bytes, 255 complete parsed pose samples, 323 timed
reads, no writes, clean serial closure and confirmed process-tree exit.

Export and verification succeeded. Full identifiers, hashes, host read timing
and the retained-but-unparsed 3,233-byte tail are documented in
`MOVEMENT_TELEMETRY_TIMING.md`. This resolves the pending successful post-fix
public capture checkpoint. It does not change the earlier failed record or
establish fresh telemetry, accurate physical pose, or motion qualification.
