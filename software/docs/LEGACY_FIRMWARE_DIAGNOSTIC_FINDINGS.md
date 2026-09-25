# Older firmware: concrete instrumentation candidate

Reviewed 2026-09-18 UTC. No hardware requests, firmware execution, uploads or servo
configuration changes. This supersedes the inability to obtain any older source,
not the requirement to verify an installed-compatible deployment.

## Source and reproducible evidence

Official wiki revision 110226 (2026-03-10) links
[RoArm-M3_example20260115.zip](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example20260115.zip).
Archive: 7,554,775 bytes; SHA256
`d627e180c4814776ef0ccf78f237482d48dcd3745be1e37378c25fd9005fd6a9`.
The revision was obtained through the official MediaWiki revisions API; no guessed
diagnostic route or third-party firmware was used.

Run `software/scripts/review_legacy_firmware_reference.py` with the workspace Python
to repeat the bounded download/hash/page comparison and verified export. It only
reads archive members as bytes/text and never extracts or executes vendor code.
Verified report:
`wizard-20260918T005525646006Z-61cb1423cc794f03a8b1741cb3002df6`.

The LF-normalized `index_html` is 54,152 bytes. The retained served page is 54,153
bytes. At reference byte offset 49,385, `6` is replaced by `11`; all other bytes
match. This changes one example-command numeric default, not the HTTP handler.
The exact hashes and member hashes are in the export. This is strong evidence of
a closely related UI, NOT proof of identical installed firmware or servo library.

## Findings that change our next implementation

Line numbers below normalize CRCRLF/CRLF to LF before counting.

| Location | Reviewed reference behavior | Diagnostic consequence |
| --- | --- | --- |
| `http_server.h`, `/js` handler | Runs JSON handler synchronously, serializes `jsonInfoHttp` | Fits observed numeric HTTP feedback; no need to assume the newer WebSocket transport |
| `RoArm-M3_config.h:69` onward | Joint/servo mapping: base 11, shoulder 12+13, elbow 14, wrist 15, roll 16, gripper 17 | Joint number is not servo bus address; synthetic servo ID 3 fixtures are not installed mappings |
| `RoArm-M3_module.h:72–98` | Successful `FeedBack` refreshes position/cache fields; failure marks status false but leaves position intact | Repeated position values can be stale after a read failure; timestamped host replies cannot distinguish this |
| Same function | Mode and torque use separate bus reads; failed feedback sets stored torque status to zero | Preserve individual read validity; do not label a failed read as confirmed torque-off |
| `RoArm-M3_module.h:577–594` | Acquisition results are ignored before converting stored positions to angles/FK | Numerical pose coherence is not proof of acquisition success |
| `RoArm-M3_module.h:599–632` | Publishes positions/load and attempts torque/voltage fields, but no per-read validity, command IDs or goal readback | Existing output cannot supply the missing causal evidence |
| `RoArm-M3_module.h:305–312` | Elbow computes goal count, writes servo 14, discards `WritePosEx` return | Instrument the actual write boundary, not just host target or HTTP receipt |
| `uart_ctrl.h`, complete command switch | No goal-register diagnostic getter found | A new host field alone cannot obtain goal readback |
| `RoArm-M3_example.ino`, setup | PID reset, initialization motion, torque configuration, boot mission and final pose movement | Do not execute this sketch as a benign probe or assume upload/reset is motion-free |

The archive includes an application binary, ELF/map and boot/partition images,
but does not bundle servo-library sources. Its map identifies SCServo objects and
an ArduinoJson V731 namespace. These are reference build clues only, not installed
dependency identification. Do not infer a fixed JSON-buffer overflow solely from
the `StaticJsonDocument<256>` declaration; the linked implementation matters.

## Next implementation

Prepare a minimal additive instrumentation design against this pinned source:
capture T101 identity and actual write return, then independently acquire goal
register and feedback-block data on the existing bus owner. Preserve raw bytes,
errors, timing, mapping and build identity. Do not change PID, torque, deadband,
calibration, default movement or old HTTP command semantics.

Before deployment, resolve the exact linked servo implementation and build inputs,
test with injected bus failures, and review a backup/recovery and boot-motion plan.
Firmware deployment still requires explicit authorization. The reference cache
behavior is a candidate explanation, not a demonstrated installed root cause, so
do not fit new motion compensation or resume uninstrumented reverse sweeps yet.
