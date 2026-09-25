# Authorized controller backup session — 2026-09-18

## Current result: matching full-flash backup pair verified

Single-connection session 36623 completed with exit 0. `flash-pair-a.bin` and
`flash-pair-b.bin` are each 4,194,304 bytes with SHA-256
`d9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9`.
Independent post-process disk hashes/sizes agree with the saved pair report;
the runner process is terminal. Both also match the earlier `flash-stub-b.bin`.
The earlier differing snapshot A remains preserved as evidence.

Nonsecret verified export:
`wizard-20260918T123027416050Z-c1136b3b46ee40d086d924ace37e6fe5`.
It contains metadata/hashes, NOT raw flash, credentials or keys. Backups remain
in the restricted private directory. This satisfies the two-copy backup criterion;
it does not establish that restoration has been tested.

The consistent uninterrupted pair supports the session-transition hypothesis for
the earlier NVS difference but does not prove its writer or exact cause. No flash
write/erase/provisioning/servo configuration command was issued. The script did
not request an application restart; post-close hardware runtime is unobserved.
Keep external motor power disconnected pending the deployment review.

Next: complete security/configuration/recovery review and present a precise,
separately approved layout-preserving deployment/provisioning proposal. No firmware
deployment is authorized by this backup result. Historical running states below
are superseded by this checkpoint.

Offline configuration follow-up: compatible littlefs-python 0.19.0 mounted the
saved filesystem through read-only in-memory callbacks without formatting. STA
configuration is structurally usable by the candidate; diagnostic policy/key are
absent. No secrets were printed. Older bundled filesystem tools failed on the
derived copy; this did not justify formatting or changing the controller.

User confirmed arm support, external motor power disconnected and USB connected.
Scope: backup/reset and identity inspection only; no firmware deployment,
provisioning, servo settings, application restart or motion commands.

## Acquired identity

Pinned esptool 4.6, COM7, 115200 baud, ROM-only (`--no-stub`), two connection
attempts, explicit `--after no_reset`. USB PnP: CP210x VID 10C4 / PID EA60.
`flash_id` exited successfully after authorized bootloader entry:

- ESP32-D0WD-V3, revision v3.1, 40 MHz crystal.
- MAC FC:E8:C0:F8:D5:38 matches recorded controller identity.
- Flash manufacturer 20, device 4016, detected size 4 MB.
- Tool reported staying in bootloader. This is not proof that subsequent port
  close/open transitions preserve the state.

## Backup progress

Private directory: `software/private-backups/controller-20260918-session1`.
Inheritance disabled; directory grants current Windows user FullControl, inherited
by files/subdirectories. Raw dumps may contain credentials and must not be copied
to normal wizard exports or printed.

The first separate `--before no_reset` read command failed to synchronize with
`No serial data received`; no dump file was produced. No flash-read completion or
backup claim follows from this failed attempt. No esptool process remained.

A deliberate second bootloader entry with `--before default_reset` starts a
ROM-only full-flash read in that connection. It terminated with exit code 1:
`Failed to read flash block (result was 01090000: CRC or checksum was invalid)`.
The private directory is empty and no esptool process remains. No full or partial
backup file was retained; a second matching copy, installed partitions and recovery
compatibility are not established. Firmware candidate compatibility remains unproven.

Completed/failed read handle: unified exec session `50284`; former Windows launcher
PID 49532 and child PID 38504. Do not poll or treat these as live. Increasing I/O
counters observed while running did not prove valid data or eventual completion.
No blind repeat was started. No successful post-operation bootloader message was
reported on failure, so current controller runtime state is not asserted.

## RAM-helper backup — explicitly authorized

The user explicitly approved: "Yes, use the RAM helper for backup only".
COM7 USB identity was rechecked; no esptool process or backup file remained before
starting. First helper-backed read uses pinned esptool 4.6 at 115200 baud, two
connection attempts, `--before default_reset --after no_reset_stub`, `read_flash
--no-progress 0 ALL`. It writes only the host file `flash-stub-a.bin` in the private
backup directory. The host refuses to overwrite an existing file.
The user was informed that the helper is left running rather than restarting the
arm application. No flash write/erase, provisioning or servo configuration is
authorized. Session 53755 completed successfully: 4,194,304 bytes in 382.0 seconds,
exit 0, tool reported staying in flasher stub. First host file SHA-256:
`90fd656c5946afb85f44986d459dcd2237b902aecbcafc79fecf3a2fc3f55672`.
File ACL inherits only the current user's FullControl from the restricted folder.

The second-copy attempt with `--before no_reset` failed synchronization before
producing a file. A deliberate bounded bootloader-entry read using the successful
`default_reset` method is running as session 33051, output `flash-stub-b.bin`.
No matching-pair claim is made until that session completes and hashes agree.

### Second copy complete: full-image mismatch localized to NVS

Session 33051 exited 0 after reading 4,194,304 bytes in 377.8 seconds and reported
staying in the flasher stub. SHA-256 B:
`d9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9`.
Both independently acquired files retain restricted inherited ACLs. Full-image
hashes do NOT match, so the matching-pair backup criterion remains unmet.

Byte comparison localizes all 6,043 differing bytes to NVS sectors 0xa000, 0xb000,
0xc000 and 0xd000. Prefix/bootloader/partition table, OTA data, both application
slots, filesystem and coredump are byte-identical. No credential values were
printed. Do not discard either snapshot or splice them into a claimed backup.

The agent issued no flash writes/erase or configuration commands. Nevertheless,
the differing NVS snapshots mean persistent state was not identical across the
sessions. Application startup during serial close/open/reset transitions is a
plausible hypothesis, NOT established fact. Do not claim the application never ran
or that all persistent state remained unchanged. Investigate port-control behavior
and a single-connection pair of reads before any further reset/retry/deployment.
No esptool read remains running after the terminal result.

### Single-connection pair started after source review

Windows pyserial opens with DTR/RTS defaults asserted unless configured before
opening; its close releases the Windows handle. This makes transition effects a
plausible explanation, not a demonstrated NVS writer. Avoided reopening between
copies in `software/scripts/backup_controller_pair.py`.

Pinned esptool Python API 4.6 and dependencies were installed into the isolated
`.firmware-tools/esptool-api-4.6` directory, not the project runtime. Reviewed
loader/reset/CLI source: standard stub read validates stream length/digest; no
flash erase/write is needed. Security-disabled stub paths are rejected. The runner
sets DTR/RTS false before opening, then performs one bounded bootloader connection,
verifies MAC and flash ID, starts the approved helper and performs two reads on
that same object. It does not reset or reconnect between copies. Closing the port
afterward still does not prove electrical pin levels or application runtime state.

Five tests passed for matching/mismatching reads, short/error reads, preserved
existing files and no retry. After rechecking COM7 identity/private ACLs/no other
esptool process, session 36623 started successfully. It verified MAC and flash ID
and began copy 1. Output files are `flash-pair-a.bin` and `flash-pair-b.bin`, plus
nonsecret `pair-report.json`. Both original mismatching snapshots are preserved.
This job is pending; poll session 36623 and do not start another connection.

### Offline image validation while the pair runs

Using the pinned esptool 4.6 `ESP32FirmwareImage` parser on in-memory slices of
snapshot A, installed bootloader (0x1000..0x8000) and app0 (0x10000..0x150000)
both pass calculated checksum and appended SHA-256 comparisons. The new
default-4mb-no-psram candidate passes the same checks. All three identify chip ID
0 (ESP32), minimum revision fields 0 and maximum full revision 65535. No conflict
with detected ESP32 revision v3.1 appears in these image-header constraints.
This does not establish eFuse security state, active OTA selection, filesystem
configuration, runtime memory behavior or deployment readiness. No raw payloads,
NVS values or Wi-Fi credentials were printed or exported by these checks.

### Saved OTA-selection metadata

Snapshot A has sequence 1 / state 0xffffffff / CRC 0x4743989a at 0xe000, and
sequence 0 / state 0xffffffff / CRC 0xffffffff at 0xf000. Both CRCs match CRC32 of
the little-endian sequence with seed 0xffffffff; OTA regions in A and B match.
ESP-IDF v5.1.4 standard selection chooses the highest valid sequence and maps
`(sequence - 1) % app_count`; with two OTA slots this implies app0 / 0x10000.
This is source-supported inference from saved metadata, not a live boot report or
proof of the exact installed bootloader configuration/security/fallback behavior.
No OTA data was modified. Sources:
https://github.com/espressif/esp-idf/blob/v5.1.4/components/bootloader_support/src/bootloader_common_loader.c
and https://github.com/espressif/esp-idf/blob/v5.1.4/components/bootloader_support/src/bootloader_utility.c .

## Preliminary offline findings from copy A

Vendor core-3.0.7 `gen_esp32part.py` parsed the table at 0x8000, validated its
structure and flash bounds. Installed partitions:

| Name | Offset | Size |
| --- | --- | --- |
| nvs | 0x9000 | 0x5000 |
| otadata | 0xe000 | 0x2000 |
| app0 | 0x10000 | 0x140000 |
| app1 | 0x150000 | 0x140000 |
| spiffs | 0x290000 | 0x160000 |
| coredump | 0x3f0000 | 0x10000 |

This differs materially from the candidate's huge_app layout. Do NOT deploy its
merged image or replace the installed partition table. The 1,087,376-byte candidate
app fits one slot numerically, but that alone is not compatibility approval.
Plan a layout-preserving rebuild/review after the matching backup is established.

Read-only header inventory finds ESP32 headers at 0x1000 and 0x10000, not 0x150000.
The app descriptor reports IDF `v5.1.4-972-g632e0c2a9f-dirty`, project
`arduino-lib-builder`, version `769c168`, build `Oct 22 2024 21:30:11`.
These are descriptor metadata, not proof of Waveshare source version, active OTA
selection, full image integrity, PSRAM availability or security configuration.

Review of Espressif esptool v4.6 identifies the bundled RAM flasher stub as the
standard alternative to ROM-only reads. It is temporary executable code, not a
persistent firmware installation. Its read path validates stream length and an
end-to-end MD5 digest; two independent host SHA-256-matching copies remain required.
This is not a proven fix for the checksum failure; cable/transport and other causes
are unresolved. Do not claim flash corruption from this one failed operation.

Approval received to use that RAM helper for backup only, retaining 115200 baud,
bounded connection attempts, no flash writes/erase/provisioning and no application
restart. With the stub, `--after no_reset` exits to ROM via a soft reset;
`--after no_reset_stub` instead leaves the helper running. Review/communicate that
end state before execution. Keep motor power disconnected and the arm supported.

Sources: https://docs.espressif.com/projects/esptool/en/release-v4/esp32/esptool/flasher-stub.html
and pinned v4.6 `esptool/loader.py` and `esptool/__init__.py` at
https://github.com/espressif/esptool/tree/v4.6 .

## Offline candidate check during the read

The current r2 app was independently inspected with `image_info`: ESP32, five
segments, valid checksum and validation hash, 1,087,376 bytes. SHA-256 matches the
retained compile export:
`b1cc73c97c7dadb626bd42701a547a3f2e275534d31ec859d864f53618ffb4db`.
This verifies the local artifact, not installed partition/PSRAM compatibility.
