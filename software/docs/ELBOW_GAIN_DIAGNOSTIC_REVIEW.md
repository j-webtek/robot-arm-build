# Elbow control-parameter evidence review

Date: 2026-09-19. Offline source/documentation review only. No servo reads,
movement, tuning, deployment, reset or provisioning performed in this review.

## Decision

Latest evidence (2026-09-19 13:00 UTC): user explicitly approved one retained GET.
It completed once and matched the original POST byte-for-byte, on the same boot
and capture ID. Export and independent replay verified. P=32, D=32, I=0 are now
backed by matched acquisition/retention responses. This retrieves historical
register readings, not a fresh acquisition or endpoint position.

- Retention export: `wizard-20260919T130037515734Z-79eaa1fc12d1488089be0dbf31b17ccb`.
- Outcome: `RETAINED_GAIN_COPY_VERIFIED`.
- No repeated acquisition, servo commands, reset, settings changes or retries.
- The original timeout export remains unchanged and inconclusive for that original
  exchange; the separate retrieval resolves the saved-copy verification gap.
- Direction-dependent non-arrival remains unresolved. Do not infer a gain cause
  solely from I=0. Next work is an offline bounded experiment proposal with
  explicit tuning/recovery authority before any such hardware actions.

Before another movement/tuning experiment, add a **fixed read-only acquisition of
servo 14 registers 21, 22 and 23, one byte each** to a separately reviewed diagnostic
candidate. These addresses come from our pinned RoArm-M3 source, not guessed from
a generic servo table. Do not write these registers. Do not invoke the legacy PID
reset command to discover defaults. Installed r16 cannot expose these bytes through
its existing fixed configuration endpoint; deployment remains separately approved.

## Evidence and limits

- Actual device evidence: negative 2903→2897 arrived exactly; positive return
  requested/readback 2903 but remained at 2897. Earlier positive legs also fell
  short. Goal-register updates and measured negative travel were verified.
- Current 12-register capture reports deadbands 0/0, limits 0–4095, mode 0,
  torque enable 1, acceleration 1, speed 20 and torque limit 1000. It contains no
  P/I/D values. None of these facts establishes a control-gain cause.
- Pinned `RoArm-M3_config.h` defines `ST_PID_P_ADDR=21`, `ST_PID_D_ADDR=22`,
  `ST_PID_I_ADDR=23`. Its SHA-256 is
  `e8d5fc95a60fb8fbecb1340b9c45c3c8af0c18329a4d7626783cf3ee692de4f4`.
- Pinned `RoArm-M3_module.h` uses byte writes to P/I and defines a reset function
  assigning P=16 and I=0 to joints. SHA-256:
  `2497a3ddd1bf73eebc6eaaa0467dde978959aad77d2a0e12fd9516e77b72ea68`.
  Those are source-code values, **not measured current settings**. The diagnostic
  boot does not call this reset function. Do not change immutable candidate files.
- Waveshare's [RoArm-M2 command documentation](https://www.waveshare.com/wiki/RoArm-M2-S_JSON_Command_Meaning)
  describes integral gain as compensating load-related position error and warns
  that excessive P/I can produce shaking. This is related-model evidence, not an
  ST3235 tuning prescription. No numeric gain change is recommended here.
- Waveshare's [RoArm-M3 product page](https://www.waveshare.com/product/ai/robots/roarm-m3.htm)
  identifies five ST3235 servos in the Pro. An older English wiki FAQ calls the
  metal servos ST3215; the current [Chinese FAQ](https://docs.waveshare.net/RoArm-M3/FAQ/)
  calls them ST3235. The user's label photo reads ST3235. Do not map raw model word
  2057 to a precise firmware/register-table version without authoritative support.
- [ST3235 documentation](https://www.waveshare.com/wiki/ST3235_Servo) describes
  position/load/speed/voltage/current feedback. It also warns that protruding
  mounting screws can cause mechanical resistance. That is a potential inspection
  consideration, not a diagnosis from our modest uncalibrated current readings.
- The reviewed sources do not establish a model-specific starting-force address.
  Exclude that parameter from an initial extension rather than invent an address.

## Minimal implementation and acceptance

1. Implement a separate gain snapshot schema with exactly three fixed reads,
   servo 14, byte widths 1, monotonic acquisition timestamps, returned length,
   device error and raw bytes. Keep existing configuration schema/replay unchanged.
2. Require inactive diagnostic bus ownership; no acquisition while a motion is
   active or an admitted return is waiting. One acquisition per boot; GET only
   returns the retained capture. No arbitrary-address input, writes, unlocks,
   defaults, startup acquisition or motion handoff.
3. Host analysis labels values as controller-reported P/D/I raw bytes; incomplete
   captures are inconclusive. Retain exact responses and replay before conclusions.
4. Test successful reads, every read failure, wrong length/device error, clock
   failure, active bus, repeated acquisition and unchanged ordinary routes.
5. Build/review the candidate offline; obtain separate approval before installation.
   Gain capture itself must not demand recovery or move the elbow. Preserve the
   existing stopped test and its six-count residual as evidence.
6. Decide from measured values and authoritative semantics whether a bounded
   gain experiment is justified. Any servo writes need separate approval, exact
   original-value backup, readback and rollback planning. Do not use a global
   PID reset or automatically apply I=8 based on related-model documentation.

## Implementation checkpoint — offline only

- Added separate fixed three-register snapshot, JSON schema and one-shot HTTP
  routes in the development firmware tree. Registered them using the existing
  inactive-bus guard; the immutable r16 candidate and installed image are unchanged.
- Added host acquisition, exact POST/GET response retention, raw P/D/I labels,
  export validation and replay. Incomplete evidence does not expose inferred gains.
- Targeted native/host tests cover each read failure and device error, timing,
  inactive-bus refusal, repeat refusal, serialization, HTTP bounds, changed
  retained responses and export replay. Existing configuration tests remain intact.
- Remaining: full board candidate build/resource review and deployment review.
  No new firmware installation, servo gain write or movement was performed for
  this implementation. Real gain values are still unknown.

## Interpretation limits

## r17 build and authorized installation checkpoint

- Candidate staging: `wizard-20260919T123845554179Z-e4b8bcd5e8f24e9599c53816dcd11e15`.
  Exactly 101 predecessor files unchanged; three gain headers added and one route
  registration header changed. Startup and all movement/recovery code unchanged.
- Full ESP32 compile: `wizard-20260919T124030530895Z-4b08188d6ec14f308e9c7923fd5be8e3`.
- Artifact/backup review: `wizard-20260919T124054166083Z-399e1eb0287e4e47a30bd9409a3469aa`.
- App SHA-256: `0ed01a2294b19047d95aeeeaf48af6c12d5610128cebe0bd94ca4119ccd5715b`;
  1,122,416 bytes, 188,304 bytes slot headroom. Bootloader and partition hashes
  match r16. Largest reviewed individual frame 432 bytes (not a total stack bound).
- Compiler reports global variables 85,504 bytes. Runtime resource availability
  remains to be observed; compilation alone does not establish runtime health.
- User said "Ok proceed" after the explicit proposal for one r17 app-only install,
  one startup and one read-only gain capture, without movement or gain changes.
- Installer now pins r16 as predecessor and the verified negative-direction
  filesystem. Local preflight passed; 84 targeted tests passed. COM7 identity matched.
- Installation was started once. Its authoritative journal is
  `private-backups/controller-20260918-session1/app-r17-deployment-events.jsonl`.
  Do not infer completion from this checkpoint; inspect final journal and startup
  receipts. No recovery or movement is authorized by this diagnostic step.

## Interpretation of measured gains

### Persistence review and explicit retained retrieval

The [ST3235 vendor tutorial](https://www.waveshare.com/wiki/ST3235_Servo)
states EPROM changes need unlocking to survive power loss. The pinned library
maps unlock/lock to address55 values0/1. M3's setJointPID writes P/I bytes without
unlocking, readback, or checking the returned acknowledgments. Therefore do not
copy that helper as a verified configuration transaction. Do not infer that a
controller reset restores servo values; separately powered servos are not reset
by resetting the ESP32. Exact gain persistence still needs validation before a
tuning experiment. No EPROM unlock or gain write occurred in this review.

`scripts/retrieve_r17_gains.py` now supports local `--preflight-only` and a distinct
`--authorized-one-retained-get` mode. It requires the saved valid POST, issues at
most one GET, compares exact bytes and boot/capture identity, preserves the
original inconclusive export, and writes a separate retrieval report. It cannot
send POST, movement, recovery, resets or settings. Five offline tests passed for
success, timeout, changed values, wrong boot and malformed response; each proves
no second attempt. Local preflight passed against the actual saved capture.
No retrieval was executed. Await an explicit one-GET request rather than silently
retrying the failed capture workflow.

The retrieval export now has independent offline replay: it reopens the original
POST export, checks its digest and boot/capture binding, recomputes exact-byte
agreement, and rejects unsupported success flags or altered assessments. Tests
also reseal a deliberately false report to verify semantic rejection rather than
only checksum rejection. The retention/capture/HTTP subset passed 26 tests.
This does not change the hardware checkpoint; the GET remains unexecuted.

### Offline follow-up: separate transport uncertainty from movement evidence

The GET timeout has no retained phase trace, so its cause is not established.
Review of the installed ESP32 3.0.7 WebServer source shows ordinary non-SSE
requests release their client after handling; its five-second close-wait constant
alone is not evidence that this request necessarily waited five seconds. The gain
GET route returns retained bytes only and never reacquires servo registers.
Do not interpret this HTTP failure as another servo non-arrival or a PID fault.

Host exchange failures now preserve method, connect/send/header/body phase,
accepted header/body byte counts, expected body length when known, and elapsed
time. No timeout increase, automatic retry or firmware update was introduced.
These fields cannot reconstruct the missing detail from the historical timeout.

Pinned M3 source resets P to 16 and I to 0; our measured P=32 differs from that
reset value, but the diagnostic boot deliberately does not invoke the reset.
This is not evidence of corruption and does not justify resetting every joint.
The [official M2 PID guidance](https://www.waveshare.com/wiki/RoArm-M2-S_JSON_Command_Meaning)
describes integral compensation for load-related error and warns of oscillation.
It remains related-model evidence, not a validated ST3235 gain prescription.

Next bounded decision: a separately requested retained-result GET can compare
against the already exported POST without repeating acquisition or moving the
arm. If a gain experiment is proposed afterward, require explicit original-value
backup, documented address/value semantics and persistence behavior, single-joint
scope, unchanged P/D for an I-only experiment, readback, and a reviewed rollback
path. Do not silently send a stale-target hold: the last known residual is six
counts and ordinary recovery admission remains five. No tuning experiment is
approved or implemented by this review.

### Actual r17 installation and capture — 2026-09-19 12:51 UTC

The authorized app-only installation completed: full application readback matched
the r17 hash; protected regions were unchanged; exactly one startup reset occurred.
Startup observation was idle and consistent on boot
`bfe2b391ed7dbd171e10ec5758b73e0e`. No servo hold, movement or gain writes occurred.

- Installation evidence: `wizard-20260919T125113527709Z-8f441fae5a7b4d15a564a87920cdcac3`.
- Startup: `wizard-20260919T125113789207Z-35972580c846419b9ab1f67decfb1fd2`.
- Capture transport: `wizard-20260919T125127605007Z-59c46c3936b146fb93e5740563d2c276`.
- Saved-response review: `wizard-20260919T125212308484Z-e5a2383d8c6443358498e8f1e63cf7f3`.

The POST response contained three successful byte reads with device error zero:
P/address21 = 32 (hex20), D/address22 = 32 (hex20), I/address23 = 0 (hex00).
Acquisition timestamps 18061614–18062773 us span 1159 us. Offline validation of
this response passed. However, the follow-up retained GET timed out under its
three-second exchange deadline. Therefore the transport workflow is INCONCLUSIVE;
the retained-copy comparison is not verified. Preserve that distinction: valid
saved POST evidence is not a claim that both network exchanges completed.

The capture is consumed on this boot. No automatic retry, reset, recovery or
movement followed. No new endpoint position was acquired by these gain reads.
Next work is to review transport retention and source-supported gain semantics,
then propose a separately authorized bounded experiment if justified. I=0 does
not by itself prove the cause or justify an unreviewed gain change.

A measured I=0 would be consistent with a steady load-related error hypothesis,
not proof. A nonzero I would change the next investigation. Neither outcome alone
establishes physical tip accuracy, compensation across poses, or permission to
resume movement. The goal remains reliable bidirectional motion and ghost typing,
not perfect identification of every mechanical cause.
