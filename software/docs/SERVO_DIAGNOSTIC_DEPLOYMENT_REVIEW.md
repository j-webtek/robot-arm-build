# Diagnostic instrumentation: deployment evidence decision

LATEST: explicit application-installation approval was received and carried out.
The exact approved app passed independent flash readback and is serving stable
IDLE / NOT_CONFIGURED diagnostic status after one USB-only startup. Export
verification passed. See `DIAGNOSTIC_APP_DEPLOYMENT_RESULT_20260918.md`.
No policy/key provisioning, servo configuration or movement occurred. Earlier
pending-deployment statements below are retained historical review checkpoints.

Status: investigation, NOT deployment approval. Reviewed 2026-09-18 UTC.

Stage 1 decision is now specified in
`DIAGNOSTIC_APP_ONLY_DEPLOYMENT_PROPOSAL.md`: exact app-only write and USB-only
startup, no provisioning or motion. Targeted controller reads confirmed MAC,
revision 301, secure boot false, flash encryption false and encrypted-download
restriction false. Three security-getter tests passed, including read failure and
wrong identity. Original app0 recovery artifact was extracted from the verified
pair and reread exactly; restoration remains unexercised. No deployment occurred.

Latest backup checkpoint: the single-connection pair completed and matches in
full, including NVS; both 4,194,304-byte files have SHA-256
`d9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9`.
Verified nonsecret export:
`wizard-20260918T123027416050Z-c1136b3b46ee40d086d924ace37e6fe5`.
Earlier notes about the unmatched separate-session pair are retained history.
Recovery has not been exercised, security/configuration review remains pending,
and deployment/provisioning still requires a separate decision.

Latest authorization update: the user has now explicitly approved backup/reset
inspection, with execution following the requested plan/goal update and physical
backup setup verification. Prior references below to pending backup authorization
are historical. Firmware deployment and configuration/provisioning remain
unapproved; no device operations occurred in this documentation update.

## Configured candidate checkpoint

### Offline filesystem compatibility review

Verified backup pair inspected by `scripts/inspect_backup_configuration.py`.
The bundled mklittlefs unpack/list commands could not mount a derived local copy;
mkspiffs also failed. This was not treated as permission to format or as evidence
of damaged controller storage. An isolated littlefs-python 0.19.0 reader mounted
the actual LittleFS image successfully at 4096-byte blocks / 352 blocks.
The script uses in-memory read-only callbacks, `mount=False` followed by explicit
mount (bypassing the library's auto-format fallback), and verifies the buffer
remained unchanged. Original backups remain intact; no device access occurred.

`wifiConfig.json` exists and has candidate-compatible STA string fields/lengths;
no credential values are printed. `rocell-diagnostics.json` and
`rocell-diagnostics.key` are absent. Consequently an app-only upload alone cannot
enable authenticated diagnostic motion: reviewed policy/key provisioning is needed
and requires separate approval. Preserve existing filesystem content and Wi-Fi
settings. Security/read-protection inspection and precise recovery/provisioning
proposal remain next; do not request approval for an incomplete write list.

### Installed-layout review update

The first successful, integrity-checked 4 MB backup exposes the default dual-OTA
layout, not huge_app. A second independent read is pending; details are retained in
`CONTROLLER_BACKUP_SESSION_20260918.md`. Do not flash the historical merged image.

`compile_diagnostic_reference.py` now accepts `--profile default-4mb-no-psram`:
`esp32:esp32:esp32:PartitionScheme=default,PSRAM=disabled`. It uses a separate build
directory suffix and records the profile in its verified export, preserving the
previous binaries. Two profile-selection tests pass. This removes an unverified
PSRAM dependency; it does not prove PSRAM is absent or validate runtime memory.
The offline build compiled successfully; verified export
`wizard-20260918T121159084880Z-c4061a611eba4557a6732828f0dbaf2e`.
App SHA-256 `5d1e081a1b33ddf9eb85a248112c6d18484e04417a1b87042f805875414ba481`.
Its 3,072-byte partition binary exactly matches the installed table in copy A
(and that region matches copy B). App file size 1,072,832 bytes fits the 1,310,720
byte slot; vendor image_info validates its checksum and appended hash. Compile
reports 118,336 static RAM bytes and 209,344 remainder, not runtime headroom proof.
Two full backup reads succeeded but differ only in NVS; full-pair verification
remains unmet. Active-slot/security/recovery review, runtime validation and explicit
deployment/provisioning approval are still required. No build has been deployed.

Consolidated offline regression checkpoint (2026-09-18): 117 focused diagnostic
tests passed in 26.94 seconds, covering native contracts, boot/routes, start
authorization and delivery, retained claims, capture/replay, and wizard review.
The r2 compile export below was independently reverified using its absolute local
path: VERIFIED_DIAGNOSTIC_EXPORT. These are software/artifact checks, not live
servo evidence. No serial connection, reset, backup, deployment or movement was
performed. Progress to installed-device compatibility inspection awaits the
backup-only authorization described in
`NATIVE_DIAGNOSTICS_BACKUP_AND_FIRST_RUN_PLAYBOOK.md`; deployment remains a
separate approval boundary.

Latest candidate: `configured-diagnostic-candidate-r2`, adding immediate
TARGET_READBACK_MISMATCH fault after retaining a mismatching target-register pair.
Full compile/link passed; verified export
`wizard-20260918T042624382742Z-c1fc89f2ee4243cc9d6130201c48e193`.
Application SHA-256:
`b1cc73c97c7dadb626bd42701a547a3f2e275534d31ec859d864f53618ffb4db`.
Generate with `--configured --configured-revision 2`; compile target
`configured-diagnostic-candidate-r2`. Earlier image hashes below are historical,
not the current proposed candidate. No deployment or backup session is authorized.

`configured-diagnostic-candidate` is a separate full build, not a deployed update.
Generate with `prepare_owner_firmware_candidate.py --configured`; compile with
`compile_diagnostic_reference.py configured-diagnostic-candidate`. It retains the
diagnostic-only startup restrictions below and adds the configured static runtime.

The first GET `/rocell/diagnostics/challenge` reads `/rocell-diagnostics.json`
(at most 4096 bytes) and `/rocell-diagnostics.key` (exactly 32 bytes), read-only.
Conversion identity must be `roarm-m3-example20260115-elbow-v1`. Successful loading
opens the locally configured start port for one connection; repeat challenge reads
do not refresh the lease or accept another attempt. Missing/invalid configuration
produces a fault/503, not defaults. No provisioning files are bundled or created.
The GET itself does not read or write servos. The subsequent authenticated POST
can dispatch one admitted elbow command. This change in capability requires an
explicit reviewed deployment decision, not merely successful compilation.

Status v3 `start_supported=true` means protocol capability, not an active lease,
clearance, endpoint verification or authority. Terminal record retrieval remains
read-only with v2 record envelopes. The host verifies schema/identity/status and
retains raw data, but unsigned HTTP remains unauthenticated device provenance.

Full build passed: export
`wizard-20260918T040423513553Z-e1d5302d2aa2415fa13e83e778fe9349`;
application SHA-256
`e0391c059eb88d538d76ac1896169c26926bce6b546d6c1253f02f6f504344c8`.
1080745 bytes flash; 118400 bytes static RAM; 209280 bytes reported remainder.
Heap/stack under Wi-Fi, JSON parsing and actual servo acquisition remain unmeasured.
27 focused tests passed, including inert runtime export/replay and actual route/
startup headers. Installed firmware identity, partition compatibility, backup and
recovery still require review. No deployment authorization is implied.

## Diagnostic-only startup changeset

The `diagnostic-boot-candidate` now replaces the reference sketch's setup/loop
with `firmware/diagnostics/diagnostic_boot.h`. Earlier candidates remain intact.
Generate with `prepare_owner_firmware_candidate.py --diagnostic-boot`; compile
with `compile_diagnostic_reference.py diagnostic-boot-candidate`. Neither command
uploads or connects to the arm.

Source review identified these inherited behaviors requiring removal from the
diagnostic entry path:

| Reference path | Observed behavior | Diagnostic-only replacement |
| --- | --- | --- |
| `initFS()` | `LittleFS.begin(true)` permits formatting after mount failure | `LittleFS.begin(false)`; failure leaves service inactive |
| setup PID reset / dynamic adaptation / hand torque | Writes joint configuration/torque settings | No calls from diagnostic startup |
| move-init / final Bessel positioning | Commands startup movement | No calls from diagnostic startup |
| boot mission playback | Executes stored commands | Neither creates nor plays boot missions |
| serial/HTTP/ESP-NOW legacy handlers | Broad command/configuration surface | Not registered or serviced by diagnostic entry points |
| `emergencyStopProcessing()` | Broadcast torque off, ten-second delay, then torque on | Not exposed by diagnostic routes; no automatic torque changes |
| reference Wi-Fi loader | Can print credential-bearing configuration and populate response JSON | Bounded file parse, no credential logging or response publication |

New boot behavior reads `/wifiConfig.json` (at most 1024 bytes), requires a
nonempty STA SSID and 8–63-byte password, disables Wi-Fi persistence, and attempts
STA connection for at most 15 seconds. It deliberately does not create a default
AP, repair storage, rewrite configuration, or fall back to legacy control. UART
transport is initialized only after connection; no servo reads/writes occur in
the boot function. The loop handles diagnostic HTTP and an already-owned finite
diagnostic session only. No start endpoint exists yet.

These source-level properties are tested with the actual boot header and inert
dependencies, including filesystem/configuration/connection failures. They do
not prove that reset or power transitions cannot move the physical arm. Existing
servo targets, controller reset behavior, board pins and library initialization
still require hardware compatibility review. This changes available interfaces
and must be explicitly described in any deployment authorization request.

Before deployment: establish backup/recovery and partition compatibility; review
authenticated one-use start, whole-arm baseline/clearance admission, runtime stack
margin, and fault behavior. A software fault latch prevents later commands; it is
not evidence of immediate physical braking or an emergency-stop implementation.

Update: an older official source has now been obtained through English wiki
revision history and compared to the retained arm page. See
[LEGACY_FIRMWARE_DIAGNOSTIC_FINDINGS.md](LEGACY_FIRMWARE_DIAGNOSTIC_FINDINGS.md).
The page differs in only one numeric default; the reference directly exposes
the cached-position ambiguity and missing per-read validity. Source investigation
can now proceed against the pinned January archive. Installed binary/library
identity and deployment approval remain unverified.

## Decision and reason

Do not flash the newer reference archive to obtain diagnostics. Its HTTP response
path differs from the installed interface. The exact installed source/library and
board build configuration are not established. Matching product names or web-page
behavior is insufficient to claim binary compatibility.

The [official secondary-development guide](https://docs.waveshare.net/RoArm-M3/Secondary-Development/)
currently links a differently dated `RoArm-M3_example20251206.zip` source package.
Its linked file page returned a web application firewall page during this review,
so its contents were not downloaded or compared. This is a candidate older source,
not identified installed firmware. The guide also warns that upload changes the
current program and calls for backing up the original program/configuration.

No SDK constructor, vendor sketch, serial reset, firmware tool, motor command or
configuration mutation was executed for this investigation. No installed-version
claim is based on the documentation's development environment settings.

## Next evidence to acquire, in priority order

1. Obtain the older official source archive via a working official resource link;
   hash it, inspect it as text, compare the HTTP feedback handler and served page
   with the already retained installed-page hash. A match is a narrowing clue,
   not proof of the complete firmware or linked servo library.
2. Determine whether that source contains a documented diagnostic getter exposing
   actual per-read status and target readback. Review its call graph for writes,
   initialization, shared cache and bus ownership before any live invocation.
3. If no such getter exists, prepare an additive instrumentation patch for a pinned
   source plus pinned dependencies. Do not invent an installed diagnostic endpoint.
   Require a reproducible build and simulated producer/host contract tests first.
4. Prepare a separately authorized deployment decision with exact image/hash,
   board/partition settings, backup and recovery procedure. Flash readout/reset
   itself can interrupt control and trigger boot behavior; do not quietly treat
   a backup command as an ordinary telemetry query.

## Minimum patch behavior to review before deployment

- One existing controller owns the servo bus. Copy return bytes/error immediately
  before another transaction changes shared library state.
- Capture received command identity, actual converted target/settings, dispatch
  result and device monotonic time; never substitute an HTTP receipt for bus result.
- Independently time goal-register and fresh feedback reads. Preserve errors,
  missing data and raw bytes; do not use cached mode helper `ReadMode(-1)` from
  the reviewed library archive.
- Bound diagnostic sampling and buffer use. Demonstrate no new boot movement,
  implicit torque/PID/mode writes, automatic retry or background motion path.
- Define build identity, servo mapping, profile and byte-order binding. Unknown
  identity or unsupported semantics must remain unknown rather than guessing.
- Test interruption, read failures, duplicate commands, reboot identity, and
  dispatch failure in simulation before any hardware deployment request.

## What this review does not establish

The actual reverse-motion cause is still unknown. Current HTTP positions cannot
distinguish stationary hardware from reused cached feedback. The software can now
represent and replay the missing distinctions, but no installed producer supplies
them yet. Camera registration and physical tip metrology remain deferred.
