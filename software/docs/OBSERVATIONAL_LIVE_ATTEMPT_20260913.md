# Observational wizard live attempt — 2026-09-13

No movement has been qualified. No automatic retry was performed.

## Verified progress

- User confirmed presence for supervised testing following the setup checklist.
- Public wizard metadata inventory and native correlation found the expected
  `10c4:ea60` / `52E4E1E8337FEF119E92181CEDD322A4` controller on COM7.
- Fixed private-key directory handling for Windows AppData virtualization.
  Logical children are checked for unsafe links before resolving; physical
  paths must remain under local application storage and outside the workspace.
  Existing keys are never replaced. 13 tests passed in
  `../runs/bench-key-virtualization-20260913-01.xml`.
- The restarted wizard provisioned and loaded its current-user DPAPI key:
  operation `operation-b8b39656d45e4802bbe75b9c33ab7c26` reported
  `KEY_AVAILABLE_NO_MOTION_APPROVAL`.
- Public read-only capture `operation-973131b683fa47639fdfbe94534ab65f`
  retained 55,552 bytes, reported zero writes, and confirmed serial cleanup
  and process-tree exit. Original outcome is in `../runs/wizard-diagnostics/`.

## Capture findings

Raw SHA-256: `3c6f78790b299a9a598b16363b8db9f2ff6508495403064f1c17cb42cc48930c`.
The capture begins inside a field name (`tS`), producing one rejected first line.
The first record arrives 125 ms after observation start; individual read widths
are 0 or 16 ms. A 171-byte incomplete suffix is retained. These are stream
attachment/host coverage findings, not measured mechanical faults. The existing
historical preview remains HELD; no data was removed or relabeled to clear it.

## One-use trial attempt

Wizard operation `operation-d15efee26a6c45deb486903b9b1c52e8` attempted the
baseline-derived -1 degree wrist-pitch policy, spd 20, acc 1, no return/retry.
The worker exited with code 1 after approximately 1.922 seconds; its bounded
error envelope reports `RuntimeError`. No worker-claim original or trial capture
was published. The supervisor confirmed process-tree exit. Result is
`RESULT_REJECTED`, not a movement result or physical pass.

Retained request, stdout, stderr and report originals are in
`../runs/wizard-exports/` with that operation prefix. They must not be replayed.

## Next diagnosis

The failure is before the retained worker claim. DPAPI loading is a candidate:
the same key loads successfully with the base interpreter under `-I -S` outside
the owned worker, but that does not prove it loads inside the supervised process.
The current child envelope omits the failing stage and native error code, so the
exact cause is not yet established. Diagnose with a no-device process probe and
bounded error-stage reporting before another separately reviewed trial.

Do not claim a commanded movement, successful wrist response, speed qualification
or campaign completion from this attempt. Operator observations remain separate.

## Root cause reproduced and corrected

The fixed no-device probe `../scripts/bench_key_process_probe.py` reproduced the
failure under `WindowsOwnedPassivePipeProcess` with the observational process
budget. The error was **Could not determine home directory**, not a DPAPI
decryption failure. The owner intentionally supplies only `SystemRoot`; the
previous `Path.home()` lookup depended on absent home environment variables.

Key storage now obtains current-user LocalAppData through
[SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)
using Microsoft's
[FOLDERID_LocalAppData](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid).
The allocated path is freed, unsafe-path checks remain, and the owner still
inherits no additional environment variables. Loading never provisions a key.

After the fix, the same supervised probe reported `KEY_LOAD_OK`, exit 0,
confirmed process-tree exit, no cleanup errors, and 485 ms elapsed. No serial
or camera API is in that probe's child path. The existing protected key was
loaded, not replaced. Fourteen key/storage tests passed in
`../runs/bench-key-minimal-environment-20260913-01.xml`, including a lookup with
home/AppData variables removed and `Path.home()` forbidden.
The broader observational/key regression run also passed: 237 tests in
`../runs/observational-key-regression-20260913-01.xml` (58.81 seconds).

This removes the reproduced pre-claim failure, not all live-test uncertainty.
The previous attempt remains consumed. A new source-bound wizard session and
current operator/setup confirmation are required for a separate live attempt.

## Subsequent supervised attempts

After the user reconfirmed readiness and requested physical testing:

- `operation-ee0175ccc3b3475ba55c4e2e9b9f37de` stopped before serial open.
  The metadata acquirer allowed two snapshots, but observational admission/open/
  baseline/dispatch requires five. The observational child now explicitly selects
  a maximum of five; other callers retain two by default. Total native-call,
  buffer, identity and deadline checks remain unchanged. 54 tests passed in
  `../runs/observational-five-checks-20260913-01.xml`. An actual metadata-only
  five-check probe completed in 16/15/16/16/0 ms per acquisition, using 445 API
  calls and 71,620 reserved bytes, with no serial access.
- `operation-e818c2ab38af458892aba4c86e636eb2` opened serial and retained a
  one-second, 10,624-byte baseline (51 complete pose records, plus attachment
  fragments). It stopped before writing; cleanup confirmed closed handles,
  no pending I/O, and process-tree exit. Confirmed command bytes: **zero**.
  The leading eight bytes were `R":20}\r\n`, a field-name attachment tail.

The framing helper now recognizes only a suffix of a known numeric field name
with a parseable remaining object, at the first line only. The original prefix
and suffix remain retained and explicitly unobserved. Whole malformed objects,
unknown fields and interior fragments are not discarded. 44 tests passed in
`../runs/observational-key-fragment-20260913-01.xml`.

Offline reanalysis of the second baseline now derives a valid historical
candidate: T101, joint 4, rad -0.018987273519943296, spd 20, acc 1. This is
**not a command sent to the arm** and cannot replace the next owned baseline.
Original SHA-256:
`a08dcf0d44c43a42ecb194130e94ec9c5aead34a09e528dc03dbd1a78180e795`.
Analysis interval is bytes [8,10463); all 10,624 original bytes remain available.

Both attempts and exports are retained. There is still no qualified physical
movement, and neither attempt may be replayed.

## Dispatch host-age allowance (software revision, not a movement pass)

Attempt `operation-183bc064c3db4b4294f4ba81c79f9a69` retained a
10,752-byte, one-second baseline with 52 complete pose samples. Selection
succeeded, but dispatch returned `WRITE_UNCERTAIN_NO_RETRY`, `ValueError`,
and **zero confirmed command bytes**. This does not establish that the arm
did not move; operator observation remains unresolved. No automatic retry.

The retained last host receipt was 227690625000000 ns, selection was
227690718000000 ns, and the write interval was
[227690734000000,227690750000000] ns. Thus the selected sample was already
109 ms old at write start and 125 ms old by failure, exceeding the previous
100 ms admission allowance. The generic error does not independently identify
every internal failure point. Original baseline SHA-256:
`d6f4e9f7af80448d6afb26e1ae4f33c9ec926787943233d8f613243b3b5fdd47`.

The observational selection latch now permits at most **250 ms** from last
host receipt to dispatch admission. This bounded host-processing allowance
includes capture closing time and authenticated checks. It is limited to the
existing stationary-start, one-degree wrist test; it is not a manufacturer
safety guarantee, device-sample freshness claim, or calibration tolerance.
Baseline-end-to-selection remains at most 100 ms. Identity/source checks,
remaining trial budget, one-use consumption, speed and excursion limits are
unchanged. No measured-motion policy was relaxed.

Boundary tests cover the observed 125 ms case, exactly 250 ms, rejection at
250 ms plus one nanosecond, consumed-attempt rejection after success/failure,
and the unchanged baseline-end limit. Regression report:
`../runs/observational-dispatch-age-20260913-01.xml`.
Result: **280 passed in 83.72 seconds**, covering observational components,
telemetry key-fragment handling and Windows controller metadata. These are
software tests, not a physical motion qualification.

The wizard verified export
`../runs/wizard-exports/wizard-20260913T211949164312Z-4ec57bdff54e43f0a13aefe42889b2e3/README.md`
contains this attempt's retained result and native logs. The export predates
the revised software's next launch and does not authorize movement.

Before another live attempt: resolve the prior operator observation, restart
the source-bound wizard, retain a new reviewed attempt, and acquire a new
owned baseline. Historical selections cannot be replayed. Do not progress
to wider poses or higher speeds until an actual response is qualified.
