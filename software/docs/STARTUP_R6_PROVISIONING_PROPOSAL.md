# r6 startup provisioning — installed and readback verified

## Nonmotion configuration-load check completed — 2026-09-18

Following user permission to proceed, one challenge discovery initialized the
installed policy/key and listener on boot `f12a38eeea1c2b983197d02b38d9a4de`.
The response matched the boot and declared a 10,000,000 us lease. Immediate status
was IDLE / NONE, zero records, no storage fault. This demonstrates successful
configuration parsing/key loading/runtime allocation/listener initialization;
it does not demonstrate a signed command acceptance or servo communication.

- Initialization export: `wizard-20260918T162331576428Z-be800be6964145288f306af2e33d50e3`.
- Immediate status export: `wizard-20260918T162331773402Z-589abcdd9aa140f8b13eb6f4a0c5181b`.
- After waiting beyond the lease, status export:
  `wizard-20260918T162400167729Z-c104a670ce0a4e4b81c97c3009cb1fca`.

The final observed status is FAULT / STARTUP_INTERFERENCE with zero records.
Pinned `start_listener.h` maps expiry/clock failure through owner.interference(),
which `startup_authenticated_owner.h` reports as STARTUP_INTERFERENCE. Thus the
observed transition is consistent with intended expiry, but the public reason
alone does not uniquely distinguish expiry from other interference. No claim of
servo failure or verified motor movement is made. No start POST, baseline POST,
servo request or reset was issued by this check. The one-use boot is consumed;
do not automatically retry/re-arm. A later trial needs a separately deliberate
startup with its complete host plan ready before requesting the short lease.

## Active authorized installation — 2026-09-18

User subsequently explicitly approved installation and confirmed USB-only power.
This supersedes the earlier pending-approval statements below. Supported links
were confirmed before r6 deployment; no intervening support removal was reported.
Approval covers the reviewed startup configuration, not movement or servo changes.

Private staging completed with a new random signing key retained only in the
encrypted candidate image. Image SHA-256:
`567d3cc0f20b2a5843bf27c7aac069f0df18782234f8579fae48a73604e569c6`.
Verified staging export: `wizard-20260918T160835917968Z-2dbb01a47b894807ad084141c28a09fa`.
The one-attempt installation completed successfully. Do not start another
invocation or clear its consumed reservation.
Prewrite review export: `wizard-20260918T160845323205Z-10ea70dd642141d7bb0c1b931c45b865`.

Full 4 MB prewrite acquisition matched r6, partition table and retained source
filesystem. One LittleFS write completed; full postwrite acquisition matched the
candidate exactly and every byte outside LittleFS was unchanged. Private source
recovery was retained under DPAPI. A verified result export preceded one startup.

- Verified write export: `wizard-20260918T162143375438Z-d90ecc6ffbc74a6da9bcb8ad6fac1f24`.
- Final run export: `wizard-20260918T162143542724Z-b2cd3fafbf42411cbe05d56827abf966`.
- Passive startup status export: `wizard-20260918T162150374348Z-694cefbdd194431d8cfc7f9fdc7f07cb`.
- New boot: `f12a38eeea1c2b983197d02b38d9a4de`; stable IDLE / NOT_CONFIGURED,
  zero records, no storage fault; status export verified and replayed.

Filesystem installation is verified; runtime configuration loading has not yet
been exercised. Passive status does not initialize the configured owner. A scoped
nonmotion initialization/challenge check is next, before any motor-powered test.
No servo command, mode/torque write, baseline POST or motion start was sent.
Keep the links supported and USB-only; no motor-power restoration was requested.

## Current state and scope

r6 is installed with exact readback verification. Its passive endpoint reports
IDLE / NOT_CONFIGURED. The arm is supported, external motor power disconnected,
USB connected. Do not restore motor power as part of filesystem provisioning.

Proposed provisioning adds two files to the existing controller LittleFS:
`/rocell-startup.json` and `/rocell-startup.key`. The first holds the reviewed
configuration; the second is a new cryptographically random 32-byte signing key.
No servo mode, torque setting, calibration, ID or firmware application changes
are included. No start command or movement is included. Separate approval is
required before generating/staging the real secret and writing the device.

## Policy proposed for review

See `startup-r6-policy-draft.json`. This is a nonsecret draft, not a live policy.
The human-formatted file must be decoded and serialized with the project's
`canonical()` function before staging; direct formatted bytes are rejected by
the firmware parser. The r6-bound validator accepted the 924 canonical bytes,
SHA-256 `75047d49f29468cf69374198321be3f19d56b35a8f98340781458cae56b0a216`.
This establishes parser compatibility only, not physical-policy approval.
Seven position windows are the earlier powered observations plus/minus 64 counts:

| Servo | Historical position | Proposed allowed position |
| --- | ---: | ---: |
| 11 | 2047 | 1983–2111 |
| 12 | 2390 | 2326–2454 |
| 13 | 1727 | 1663–1791 |
| 14 (elbow) | 2723 | 2659–2787 |
| 15 | 2041 | 1977–2105 |
| 16 | 2042 | 1978–2106 |
| 17 | 2051 | 1987–2115 |

These are bounded software acceptance windows, NOT measured collision clearance
or a claim about the current pose. Support/power changes may invalidate the old
pose. Fresh observations must fit; otherwise stop and review, never automatically
widen windows. A previously observed zero goal is not a commanded zero position.

The draft caps elbow input at 2.5–2.7 radians, speed 40 and acceleration 1 in
the pinned firmware's native command units. This full interval is NOT a proposed
sweep. The later signed first-command plan must impose a maximum 8-count change
from the fresh measured elbow position, with one command only. That per-command
delta is not stored in this controller configuration; its enforcement is a
separate signed-plan/native admission requirement. No Cartesian accuracy follows
from a count delta.

Two stationary scans must agree within 2 counts, separated by 100 ms to 1 s.
Each goal/position read pair is limited to 10 ms, each whole-arm scan to 100 ms,
and the current scan/control evidence must be no older than 250 ms at use.
These are acquisition budgets, not promised move completion times. Actual
observed scan duration was about 7.9 ms; future overruns stop, not silently relax.

Direct mode register 33 must read 0 and torque-enable register 40 must read 1
for all seven servos. Mode 0 is a proposed required operating mode, not an actual
readback finding. A mismatch prevents movement; provisioning does not change it.
All startup goals must still be zero. The listener uses port 8081 and one-use
10-second challenges. HMAC authenticates requests; ordinary LAN HTTP diagnostic
responses are not cryptographically authenticated device telemetry.

## Filesystem preservation and execution procedure

1. Verify installed r6 hash, validator build binding, exact accepted policy bytes
   and the retained original backups. Freeze the reviewed policy digest.
2. Confirm links remain supported and motor power is disconnected before reset.
3. Read the current LittleFS partition into private storage using the reviewed
   backup path. Compare it with the previous snapshot. If changed, stop and
   review; do not overwrite intervening content. This acquisition/reset must be
   included explicitly in the provisioning authorization.
4. Generate the key only after approval. Keep key and image private; do not print
   them or put them in logs, source control or shared wizard exports. Use the
   existing current-user DPAPI image protection for retained staged bytes.
5. Stage only the two new files using pinned LittleFS 0.19.0 and the r6-bound native
   validator. Never format on mount failure or overwrite existing destinations.
   Remount; verify exact new bytes and every existing path/content hash.
6. Record the final staged-image digest in a nonsecret review record. The physical
   write covers the LittleFS partition, not just two isolated flash files:
   offset 0x290000, length 0x160000, exclusive end 0x3f0000.
7. Before writing, verify controller identity, r6 app, partition table and current
   source-filesystem digest again. Use one write attempt only. Read back the
   entire partition and compare exact bytes. Verify all outside regions unchanged.
   Keep the unmodified source recovery image. Never auto-retry or auto-restore.
8. One USB-only startup and passive status check may follow successful verification.
   The challenge endpoint initializes configuration/ownership; do not call it as
   a casual health check. Any configuration-load inspection must be explicitly
   scoped as a separate nonmotion action, with no start POST.
9. Export nonsecret hashes, checks, results and limitations. Stop if export fails.

## Readiness and remaining implementation

Offline filesystem staging, preservation checks, native policy validation and
DPAPI image storage exist and have synthetic tests. The one-shot core in
`startup_provisioning_execution.py` now enforces exact candidate digest/length,
controller identity, installed r6/partition/source hashes, private source retention
before write, one partition-scoped write, full readback and exact outside-region
preservation. It returns only after the final evidence callback succeeds. There
is no reset, retry, recovery write or movement method in this core.

The core and startup-image suite passed 23 tests using a synthetic device. Cases
include identity/source/app/partition/candidate mismatch, failed reservation or
recovery storage, failed prewrite/final logging, uncertain write, write exception,
short readback, wrong candidate readback and changed protected regions. Synthetic
tests substitute synthetic app/partition hashes; they are not live verification.

Still required before a real write: integrate the reviewed USB/esptool adapter
(with internal write retries disabled), persistent exclusive operation journal,
private DPAPI recovery/staged-image storage and nonsecret export. The caller must
bind the exact reviewed staged bytes to approval and source-preserving staging;
the core verifies hashes but does not independently parse the filesystem. A
fresh core object never authorizes repeating a consumed durable operation.
This document is not an instruction to use a generic flash command or bypass
those checks. No real key generation, staging, reset or write occurred in this
offline implementation step.

### USB adapter and persistent journal follow-up

`providers/windows/startup_provisioning_device.py` now provides an inert adapter
for explicitly supplied esptool 4.6 modules and COM7. Its first identity call
opens/reset-connects once, verifies identity/security before loading the helper,
then permits only the two full-flash reads around one exact LittleFS write.
It sets `WRITE_BLOCK_ATTEMPTS=1`, uses immutable in-memory bytes, and disables
chip erase, force and encryption options. Errors close without reset/retry.
There is intentionally no application-startup method in this adapter yet.

`startup_provisioning_journal.py` reserves one fixed exclusive journal filename
and flushes/fsyncs each bounded record. Existing and partial journals cannot be
resumed by constructing another object. It requires an already-established
private parent directory; it does not establish that directory's ACL itself.

The adapter, journal, core and image suites passed 30 tests. Adapter tests use
explicit doubles, not an actual USB connection. Still needed: an integrated
authorized runner binding validated staged bytes/private storage/export to these
components, and an explicit verified-success-only startup step. No real key,
device connection, reset or provisioning occurred in these offline tests.

### Integrated runner follow-up

`startup_provisioning_run.py` now joins preserving re-staging, native validation,
exclusive journal reservation, private DPAPI candidate/recovery storage, the
one-write core and verified public exports. Exact re-staged bytes must match the
approved candidate digest before any device call. A separately authorized startup
can occur once, only after full verification and verified write-result export.
The adapter now has that explicit one-use startup method; closing still does not
reset. Failure records contain a fixed label, not potentially secret exception
messages. A consumed journal prevents a new runner instance from resuming.

The combined suite passed 34 tests. Integration uses real LittleFS, the native
parser, Windows DPAPI and exporter, with synthetic keys/images and a fake device.
Private-storage failure prevents device reads/writes; uncertain write and failed
result export prevent startup. Public exports were checked for synthetic-key
leakage. This does not establish live USB or movement correctness.

Remaining operational packaging: explicit-authority CLI preflight with pinned
dependency paths, private-directory verification, real reviewed-source acquisition
and separate staged-image approval. No real key or secret-bearing image has been
created. No new controller connection, reset, provisioning or movement occurred.

### CLI ready for separately approved staging

`scripts/provision_startup_r6.py` implements three mutually exclusive modes:

- `--preflight-only`: local reads, current-user-only protected directory ACL,
  matching backup pair, r6 image, exact canonical policy and bound validator.
  No key creation, device imports, journal reservation or hardware access.
- `--authorized-stage-private`: after approval, create a random key, stage the
  preserving image and retain it as `startup-r6-reviewed-candidate.dpapi` in the
  private backup directory. Export a nonsecret image hash for separate write
  approval. Existing staging is never regenerated or overwritten.
- `--authorized-provision-and-startup --candidate-sha256 <approved hash>`: load
  that exact encrypted image, recover its key only in memory, independently
  re-stage/verify, reserve the operation, and invoke the reviewed adapter/core.
  A fresh full-flash read must match the retained source before any write; a
  changed filesystem stops rather than being replaced. Full readback and verified
  export precede one startup. No status GET, challenge, start token or servo command
  is automatically sent by this CLI.

Actual local preflight passed, including source filesystem SHA-256
`d219fd8b7e3946550acc7153671765a8fc327613dfdcc2952957b13bb331b022`.
The combined suite passed 40 tests. Preflight isolation tests prohibit serial,
esptool, LittleFS imports and key generation; ambiguous invocations are rejected.
The initial Windows PowerShell module-load problem was corrected by using the
available PowerShell 7 (`pwsh`) with terminating errors for ACL inspection.

No staging or provisioning approval has been received yet. The next requested
approval is PRIVATE OFFLINE STAGING ONLY; the resulting exact candidate digest
will be presented before requesting the device write/startup. USB-only support
remains the last confirmed physical setup, not an inferred future confirmation.

After provisioning, separately arrange motor power and support clearance, acquire
fresh evidence, select the bounded first target, and collect requested/transmitted
target, ACK, target register and fresh endpoint samples. A non-arrival remains
non-arrival. r6 supports one startup leg only; reverse/cycles need the explicit
continuation implementation in STARTUP_TO_REPEATABLE_MOTION_PLAN.md.
