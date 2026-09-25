# r7 hold provisioning review — not authorization

## Approved provisioning completed — 2026-09-18

The user explicitly approved one filesystem-only provisioning and one startup for
the staged candidate. Using the confirmed supported USB-only setup, the command
passed preflight, durably reserved the attempt, verified the controller and full
prewrite image, privately preserved the source filesystem, and issued one write.
Full postwrite flash matched the candidate in the filesystem partition and was
byte-identical outside it. No retry or recovery action occurred.

- Plan export: `wizard-20260918T193143788327Z-58d8e03162fa4fe1bb86a2f217d4c0a5`.
- Verified write export: `wizard-20260918T194437915141Z-489c46fc91b64b128d339f906937b48d`.
- Final run export: `wizard-20260918T194438073911Z-c5027a7bed73466d8d29ff51e49b553c`.
- Startup status export: `wizard-20260918T194501474566Z-ea93ab25a2a940bd8412946a9c2d432c`.
- New boot: `749e200e399ad53b38f2fa35f4929ed8`.

The verified write export preceded the single startup reset. A single status-only
GET then returned IDLE/NOT_CONFIGURED, zero records and no storage fault. Files
are verified installed, but the hold runtime loads them lazily on challenge
preparation; that route was deliberately not called. Configuration load and live
hold/servo readiness are NOT established by this status response.

Private `hold-r7-candidate.dpapi` and `hold-r7-prewrite-source.dpapi` preserve exact
candidate/source bytes. `hold-r7-provisioning-events.jsonl` is consumed. Do not
rerun provisioning or regenerate credentials. No challenge, torque enable or
movement command was sent. Pending-approval language below is historical.

## Exact candidate provisioning entry point ready for approval

`software/scripts/provision_hold_r7.py` now binds the staged candidate, policy,
validator and installed r7 hash. Its local-only preflight passed against the real
retained encrypted image and verified review export, without controller access,
key generation, key extraction or journal reservation. Five CLI boundary tests
and thirty execution-core tests passed (35 total, 1.23 s). Prior integrated
DPAPI/filesystem/device-double tests remain the orchestration evidence.

The requested next approval is **one filesystem-only provisioning and one startup**
for candidate SHA-256
`0bdfc4d3f300e811e03332a6a86df20e47c3d42c95282e9ddd2f00c211044e9b`.
The only flash write is the filesystem partition, offset `0x290000`, length
`0x160000`. The application/bootloader/partition table and other regions must
remain byte-identical across full pre/post reads. Live checks revalidate MAC,
flash/security state, r7 app and source filesystem before writing. The source
filesystem is privately preserved first; verified result export precedes startup.
Any uncertain write or failed check stops without retry/reset/recovery.

This scope does not include a challenge/start request, torque command or movement.
The hold policy/key are added to storage, but r7 does not engage servos at startup.
User last confirmed supported links and USB-only power. Do not connect motor power
for provisioning. Full pre/post flash acquisition may take several minutes at the
reviewed serial rate; observe the same process rather than starting another.

Only `--preflight-only` was executed. The provisioning journal remains unreserved;
device-write/startup approval is still pending.

## Approved offline staging completed

The user explicitly approved offline private staging. `stage_hold_r7.py` checked
private-directory ACLs, verified installed-r7 evidence and retained candidate
source hashes, validated the exact canonical draft through the r7 parser, and
verified the retained provisioned filesystem. It reserved a one-use local staging
record before generating one key. No serial/network/controller operation occurred.

The in-memory candidate was remounted and checked, then saved/readback-verified
using current-user DPAPI at
`software/private-backups/controller-20260918-session1/hold-r7-reviewed-candidate.dpapi`.
All four existing entries were preserved. Do not regenerate or overwrite it.

- Candidate SHA-256:
  `0bdfc4d3f300e811e03332a6a86df20e47c3d42c95282e9ddd2f00c211044e9b`.
- Source filesystem SHA-256:
  `567d3cc0f20b2a5843bf27c7aac069f0df18782234f8579fae48a73604e569c6`.
- Policy SHA-256:
  `f9663167513aadeb5666713c808128ddd834be5843e6570d22359338f93dc9e1`.
- Native validator SHA-256:
  `5bb34a17fa28066e2142f410d265c1739e60afa522e947a8a306692d771d1628`.
- Retained validator: `software/.firmware-tools/hold-r7-validator-imc7cqjb/validate.exe`.
- Verified public review export:
  `wizard-20260918T192754597401Z-66ce7c2b5fa041509937d7c61b69134f`.

No provisioning, startup or motion is authorized by staging. Next is the exact
candidate's filesystem-only provisioning review/entry point, followed by separate
approval before any device write/reset. The old statements below that no key or
candidate exists describe the pre-staging state and are superseded here.

## Orchestration checkpoint

`run_hold_provisioning` now composes exact re-staging, r7-bound execution, separate
hold journal, private `hold-r7-candidate.dpapi` / `hold-r7-prewrite-source.dpapi`
preservation, verified exports and an explicit optional startup. The old r6 entry
point retains its own profile and paths. Startup defaults to false and cannot
precede a verified result export. The function does not generate keys or infer
approval; inputs must already be reviewed.

58 targeted tests passed in 35.48 seconds. Integrated tests use the real pinned
LittleFS parser and DPAPI storage with synthetic credentials and a fake device.
They cover both profiles, startup permitted/not permitted, storage failure,
uncertain write, result-export failure, consumed-journal rejection and no secret
key bytes in public exports. All private files in these tests are temporary
fixtures, not the arm's configuration. The real hold journal and candidate remain
absent.

Steps 1 and 2 below are complete. Next is approval for **offline private staging
only**: generate one authentication key, add the reviewed hold policy and key to
the verified retained filesystem in memory, privately save the candidate with
DPAPI, and export its nonsecret hash/review. That approval does not authorize
flashing, resetting, preparing a live challenge or engaging a servo. The resulting
candidate digest will be reviewed before separate provisioning approval.

## Current physical and software state

r7 was installed with full readback and protected-region verification. Startup
status was IDLE/NOT_CONFIGURED. User reconfirmed supported links, external motor
power disconnected and USB connected. Installation approval covered the app and
one startup only; it did not cover provisioning, torque engagement or movement.

No live hold key has been generated, no private hold candidate has been staged,
and no hold provisioning attempt has been made by this work.

## Proposed configuration

Readable draft: `software/docs/hold-r7-policy-draft.json`.
Provisioning uses its canonical JSON bytes, not the pretty-printed source file.
Canonical length: 456 bytes. SHA-256:
`f9663167513aadeb5666713c808128ddd834be5843e6570d22359338f93dc9e1`.

| Setting | Proposed value / interpretation |
| --- | --- |
| Command ID | `r7-elbow-hold-20260918` |
| Controlled servo | 14, elbow only |
| Target | Fresh native elbow position, not a preselected angle |
| Speed / acceleration | Native values 20 / 1; not mm/s |
| Permitted drift | 2 servo counts |
| Initial scan gap / settling | 100 ms / 100 ms |
| Pair / scan / age bounds | 10 ms / 100 ms / 250 ms |
| Maximum observation gap / deadline | 500 ms / 2 s |
| Explicit enable | Permitted once, only if hold readback still reports torque off |
| Start listener | Port 8081; one authenticated attempt, ten-second challenge |

The first position write can itself engage torque. Explicit enable means a
conditional RAM torque-register write, not calibration, EEPROM, servo-ID or mode
changes. No other joint is enabled. This does not make the whole arm ready.

Joint windows in the draft are retained from the earlier reviewed startup policy,
not newly measured after supporting the arm. If fresh positions are outside them,
the hold must stop before writing. Do not silently widen them to obtain a pass.
The policy passing the parser is not fresh workspace/pose validation.

## Offline implementation and evidence

`stage_hold_image` adds `/rocell-hold.json` and `/rocell-hold.key` exclusively to
a supplied verified source image, remounts it, and compares all existing entries.
It refuses existing destinations, malformed policy, corrupt filesystems and failed
native validation. It does not format a source or generate a credential.

`validate_hold_provisioning.cpp` uses the r7 candidate headers selected through
the include path, accepts bytes through stdin, and emits only a fixed verdict.
Windows streams use binary mode so newline conversion cannot alter that verdict.
The draft and synthetic preservation tests pass against this parser.

`HoldProvisioningExecution` shares the one-write/readback core but binds to the
exact r7 application hash and size. It verifies identity, full prewrite flash,
source filesystem, application and partition before preserving recovery bytes and
writing once. Full postwrite readback checks filesystem bytes and every protected
region. A distinct `hold-r7-provisioning-events.jsonl` journal prevents reuse of
the r6 provisioning attempt. No reset or motion method exists in this core.

42 targeted tests passed in 2.57 seconds, including all 14 fault cases for both
application profiles, synthetic filesystem preservation, and native draft parsing.
These are simulated provisioning tests, not evidence of a live filesystem write.

## Remaining steps before asking to write

1. Integrate hold staging, private DPAPI preservation, journal and evidence exports
   into a dedicated orchestration entry point; retain single-attempt behavior.
2. Verify it with synthetic device execution, export failure and interrupted-write
   cases. Ensure it never uses r6 paths or performs an implicit startup/reset.
3. Review the exact draft and obtain approval to generate/stage the private key and
   candidate. Retain only hashes and nonsecret review data in public exports.
4. Obtain separate approval for the resulting candidate digest and filesystem-only
   provisioning/startup scope. Revalidate supported USB-only state before opening
   serial; do not automatically reuse the application-installation approval.
5. Collect hardware-origin read-only evidence and runtime memory observations;
   then review authorization for one powered elbow hold. No contact, forward/
   reverse testing, whole-arm readiness or stylus-tip accuracy follows merely from
   successful provisioning.
