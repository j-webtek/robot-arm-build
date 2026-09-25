# r7 supported-pose hold revision — offline proposal only

## Approved powered hold completed successfully at reported-count level

One authorized trial on boot `35d977559eff75fd89c2f156abb5bc0c` produced five fresh
snapshots and one position-write action. Requested/encoded count, first/settled
goal readback and settled position all equal **2902**; error=0 counts. Elbow torque
changed 0->1 without a separate enable call. Other joints retained identical
positions/goals/torque throughout all five scans. Final observation ended 136,388
microseconds after the write. Controller reported CAPTURED/ELBOW_HOLD_CAPTURED.

Observation export: `wizard-20260918T230821752067Z-164698b57d1148429f455b24fce52c15`.
Raw export: `wizard-20260918T230821675163Z-21ba31b6d6c14934864950b3d8b26496`.
Prepared export: `wizard-20260918T230818374347Z-e0a091ad351a47169f28de8e39cbbbbd`.
Offline replay passed. No repeat, reset, torque release or recovery movement.
The hold claim is consumed. Do not rerun the command below.

This verifies a hold, not movement: start and end positions were intentionally
identical. No millimeter accuracy or reverse-motion result is implied. The six
other servos remain reported torque off; keep links supported. Elbow last reported
torque on. Next work is a reviewed bounded forward/reverse diagnostic sequence,
not more hold scaffolding or calibration compensation based on this zero delta.
Earlier preparation/approval-pending language below is historical.

## New-boot hold entry point ready — no trial executed

`run_hold_r7.py --supported-pose --preflight-only` passed against the installed
replacement's real receipts and encrypted candidate/recovery files. It uses boot
`35d977559eff75fd89c2f156abb5bc0c`, the approved 2893–2909 elbow window, and the new
command identity. The original profile remains separate and consumed. Sixteen
CLI/orchestration tests passed, including cross-profile boot rejection.
No key extraction, challenge, attempt reservation or hardware access occurred.

After separate powered-hold approval and supported/secured/clear powered setup,
the exact invocation is:

```powershell
.\.venv\Scripts\python.exe software/scripts/run_hold_r7.py --supported-pose --authorized-powered-hold --expected-boot 35d977559eff75fd89c2f156abb5bc0c
```

This can engage elbow torque, but requests the freshly measured count rather
than a new fixed position. No other joints are intentionally enabled. Fresh
readings outside the approved windows stop before a write; there is no widening,
automatic reset, resend or recovery move. The last physical confirmation remains
USB-only with external power disconnected. Do not execute on that setup or infer
trial permission from the completed installation approval.

## Approved filesystem installation and one startup completed

User approved the exact candidate and confirmed external power disconnected,
USB connected. The one-use replacement runner completed successfully: full
prewrite verification, private recovery preservation, one filesystem write,
full postwrite readback, verified result export, then one startup reset.
Candidate bytes matched exactly; all regions outside the filesystem remained
byte-identical. No retries, servo commands or recovery movements occurred.

- Plan: `wizard-20260918T212222293772Z-63b5b72a4b0a4cf19da8721aeed006fc`.
- Verified write: `wizard-20260918T213520661096Z-ba47bd4a42bf42a2ba60007158b265e1`.
- Final run: `wizard-20260918T213520824547Z-50d496655d5d4796b58d39a0a8395a1a`.
- Status-only startup export: `wizard-20260918T213547363926Z-f5e6fd8994844a3f8e4adf459e60fa35`.
- New boot: `35d977559eff75fd89c2f156abb5bc0c`.

One status GET returned IDLE/NOT_CONFIGURED, zero records, no storage fault.
Configuration is loaded lazily by the challenge route, which was NOT requested.
Installed filesystem is verified; configuration loading, hold and powered servo
readiness remain unverified. The replacement journal is consumed. Do not rerun
installation. Next prepare a trial tied to this new boot and replacement receipts;
the old `run_hold_r7.py` references the prior candidate/boot and is not suitable.
Obtain separate powered-hold approval before that trial. Keep links supported.
Earlier pending-installation language below is historical.

## Exact-candidate installation path prepared — not executed

`software/scripts/provision_hold_supported_pose.py --preflight-only` passed
against the real staged replacement and retained evidence without device access
or reserving an installation attempt. The live entry point requires explicit
`--authorized-filesystem-and-startup` and the full candidate SHA-256 below.

The shared provisioning runner now has an explicit replacement profile: it
rebuilds and byte-compares the preserving replacement before hardware access,
uses `hold-r7-supported-replacement-provisioning-events.jsonl`, and saves distinct
candidate and prewrite-source recovery files. The existing r7 application-bound
execution core verifies device identity and full pre/post flash, writes only the
filesystem once, and requires verified result export before the optional startup.
No retry, servo command or automatic recovery is provided.

24 integrated tests passed across original startup, original hold and replacement
profiles, including private storage failure, uncertain write, result-export
failure, startup disabled/enabled and consumed-journal rejection. They use real
LittleFS/parser/DPAPI with synthetic files and a fake controller. No installation
has occurred. Approval must cover one filesystem-only replacement plus one startup
for `4524696545583513b283348789b2e1f92ed37e178efcb10edf32dcbd639ec4bf`.
Before that operation: mechanically support links, then disconnect external
motor power while keeping USB connected. Never remove power before supporting
the arm. A later powered hold is a separate operation.

## Approved private candidate preparation completed — 2026-09-18

The user approved the 2893–2909 elbow policy and offline private preparation only.
`stage_hold_supported_pose.py` verified retained installation/provisioning exports,
private ACLs, source image, exact old/new policies and installed parser. It reserved
a separate staging claim, replaced only the policy in memory, verified remount and
all five other entries (including the unchanged key), and saved/readback-verified
the candidate with current-user DPAPI. No controller access or key generation.

- Candidate SHA-256: `4524696545583513b283348789b2e1f92ed37e178efcb10edf32dcbd639ec4bf`.
- Source SHA-256: `0bdfc4d3f300e811e03332a6a86df20e47c3d42c95282e9ddd2f00c211044e9b`.
- Policy SHA-256: `2ab588877107ebbc067607c29003fb317867123780e40c8e9d41011907d312d1`.
- Private file: `software/private-backups/controller-20260918-session1/hold-r7-supported-pose-candidate.dpapi`.
- Verified public export: `wizard-20260918T210720842126Z-374c9d9e3cfb41128c743accf9220ffc`.

Three focused replacement/draft tests passed before execution. Staging reservation
is consumed; do not repeat it. Old images, policies and device contents are unchanged.
Next is a reviewed exact-candidate provisioning path and separate approval for
filesystem-only installation/startup. No installation, reset or hold is authorized
by this completed preparation. Pending-staging language below is historical.

## Replacement helper tested, real staging still pending approval

`replace_hold_policy_image` now provides the explicit in-memory replacement path.
It requires the exact source-image digest and previous policy bytes, validates
both policies through the caller-supplied installed parser, preserves the existing
key, and remounts to verify all unrelated file/directory entries remain unchanged.
Initial provisioning still rejects existing destinations. There is no device I/O,
credential generation or format/recovery fallback. Twenty-one focused staging
tests passed, including synthetic replacement, stale source/prior-policy rejection,
missing configuration, unchanged-policy rejection and exact key preservation.
No real private image was opened or staged during this work. The helper is not
an approved deployment path or permission to provision the revised policy.

## Evidence and diagnosis

The authorized first hold returned fresh mode, torque, goal and position reads
from all seven servos, then stopped before any servo action. Elbow ID14 reported
2901 counts against the historical 2659–2787 admission window. Other joints were
inside their respective windows. All reported mode=0, moving=0, torque=0, goal=0.
Snapshot acquisition took 12,720 microseconds. The terminal record reported
`HOLD_POSE_OR_CONTROL_INVALID`, one snapshot and zero actions.

Source observation export:
`wizard-20260918T200008543182Z-dd9099e1620648589bdae768904d2b4d`.
Raw transport export:
`wizard-20260918T200008468028Z-4aea2b566a4f4a1d862a79ddbd0fedee`.

This supports a starting-pose mismatch. It does not demonstrate movement error,
backlash, required compensation, stable repeated samples, or physical tip accuracy.
One snapshot cannot establish a universally safe elbow range.

## Proposed change

`hold-r7-supported-pose-draft.json` preserves the installed policy except:

- A new command identity: `r7-supported-hold-20260918`.
- Elbow admission window: **2893–2909**, centered on the observed 2901 count pose.

The ±8 count width is a conservative proposed admission tolerance, not a measured
noise bound or calibration result. It replaces rather than expands the old range
to include both poses. The six other windows, speed=20, acceleration=1,
maximum drift=2 counts, timing limits and conditional elbow-only torque enable
remain unchanged. Fresh scans must still meet every check; otherwise stop.

The command must hold the fresh acquired elbow count, not command 2901 as a fixed
destination. Enabling torque can still cause physical movement under load. Keep
links mechanically supported without constraining the joint against a rigid stop.
Do not assume the other six servos are holding: the last reads reported torque off.

## Execution scope still requiring approval

1. Review and approve this bounded policy. Do not alter the old approved draft,
   installed configuration, old encrypted candidate, or consumed journals.
2. Prepare a separate private filesystem candidate, preserving all unrelated
   bytes/files and the existing credential. This is a configuration replacement,
   not regeneration of keys and not application deployment. The current staging
   helper refuses existing hold files; use a separately reviewed replacement path,
   never bypass that check or reuse its journal.
3. Obtain approval for the exact candidate's filesystem-only write and one startup.
   Support links before any power removal. Preserve and verify recovery and
   unchanged non-filesystem flash as before. No implicit motion in this scope.
4. After powered setup and separate trial approval, check the new boot and execute
   exactly one hold trial. Configuration loading/challenge belongs immediately
   before the start; do not consume it in a standalone setup check.
5. Verify requested/encoded fresh hold count, goal readback, torque state, settled
   position and neighboring-joint drift from saved raw records. Stop on uncertain
   delivery, invalid evidence or failed export; no resend or recovery move.

No implementation or safety claim in this proposal authorizes these device actions.
Only after successful hold evidence should we design the next bounded forward/
reverse trial. Do not treat this hold as proof of displacement or typing accuracy.
