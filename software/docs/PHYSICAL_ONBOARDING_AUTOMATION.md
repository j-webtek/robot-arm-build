# Physical onboarding automation

This guide is the operating contract for bringing the physical RoCell host,
static Arducam B0477 camera, and Waveshare RoArm-M3 Pro together. It describes
the commands that exist in this checkout now, the evidence they retain, and
the physical decisions that software deliberately cannot make.

The current onboarding subsystem is **diagnostic-only and zero-authority**. It
does not power the robot, open a camera, open the arm serial port, initialize
or home the arm, send motion, descend toward a device, or release contact. A
successful environment check, inventory, or journal verification is not a
power, motion, calibration, or contact permit.

> **Current stop line:** `new --prepare-safe` can pass only
> `workspace_sources` and `static_camera_contract`. One challenge-protected
> `next --execute` can then place `camera_receipt` in `WAITING_OPERATOR`.
> Intake and file evidence may be retained, but they do not pass the stage.
> There is no reviewed physical-stage assessor in the public CLI yet, so the
> supported CLI-only workflow stops there. Do not bypass that stop by editing
> the journal or calling a hardware command directly.

> **M1 v2 stop line:** the qualified zero-hardware runtime can initialize its
> Windows/NTFS storage, verify cell-global attempt/quarantine ledgers, and create
> a blank source-bound v2 diagnostic session. It cannot advance a stage or
> perform an effect. `effects_allowed_by_m1_storage` is only a clear storage
> admission result; it is never permission to inventory, open, power, move, or
> contact hardware.

For the full physical acceptance criteria behind each stage, also use
[First-power-on onboarding](FIRST_POWER_ON_ONBOARDING.md),
[B0477 camera integration](B0477_CAMERA_INTEGRATION.md), and the
[static camera hardware guide](../../hardware/static_overhead_camera/README.md).
The reviewed v2 build roadmap for the guided wizard is
[Physical onboarding wizard implementation plan](PHYSICAL_ONBOARDING_WIZARD_IMPLEMENTATION_PLAN.md).
Its strict Phase-0 contract graph and validator are implemented and bound into
Stage-1 workspace verification. The M1 application layer now adds qualified
Windows/NTFS publication, ordered leases, cell-global attempt/quarantine
ledgers, and source-bound v2 session creation behind a public facade that has
no effect method. The effect-capable coordinator, permits, energization
envelopes, reviewed-stage service, physical providers, and UI are not
implemented. The aggregate remains `runtime_activation: false` with its
physical implementation gates and zero physical authority. Validate the
foundation read-only with
`python software/tools/validate_physical_onboarding_foundation.py` from the
workspace root, and use the
[M1 qualified zero-hardware runtime guide](M1_ZERO_HARDWARE_RUNTIME.md) for its
separate storage workflow. Neither check authorizes bypassing either stop line
above.
The operational onboarding, camera, and support documents above—not the
implementation roadmap—are controlled inputs to the session source binding;
changing one makes an existing session source-stale instead of silently
changing its operating contract. Wizard assets and procedures will be added to
that binding when they become executable.

## 1. Locked physical connection architecture

Phase 1 is an eye-to-hand system: the B0477 is rigidly mounted on the static
overhead support, not on the moving arm. The camera and arm connect separately
to the host, and the arm's 12 V power path remains physically independent.

```text
                                      rigid static overhead support
                                     +------------------------------+
Host USB 3 port ---- USB/UVC --------| Arducam B0477 / IMX283 / 16 mm |
                                     +------------------------------+
                                                    |
                                                    v
                                             placemat work area

Host USB port ----- USB-C serial ----- RoArm ESP32 controller
                                           |
                                           | servo/control bus
                                           v
12 V supply ---- physical power-cut E-stop ---- RoArm actuators
```

The software contract for these paths is:

- **Camera:** Arducam B0477, Sony IMX283, included 16 mm C-mount lens,
  USB 3.2 Gen 1 UVC, with the published full-resolution mode
  `5472 x 3648`, YUY2, at up to 9 fps. Connect it directly to a known host
  USB 3 port. A blue connector, a product name, or a USB-C plug does not prove
  the negotiated bus speed; topology and speed still require observed
  evidence.
- **Arm data:** the RoArm-M3 Pro ESP32 connects directly to the host over its
  USB-C serial interface. The controlled profile is 115200 baud,
  newline-terminated JSON, RTS false, DTR false, one exclusive owner, no
  automatic connection, no automatic initialization, and no blind retry.
- **Arm power:** the 12 V actuator supply passes through an independent,
  physical power-cut E-stop before the arm power input. USB data connection is
  not a robot-power approval, and camera success is not an arm-power approval.
- **Power-on behavior:** Waveshare documents possible automatic movement toward
  a middle joint position at power-on. Applying arm power is therefore a
  possible motion event even when the host sends zero commands. The first
  power event requires a cleared startup sweep, passive gravity-safe
  containment, a tested physical E-stop, an observer at that E-stop, and a
  recorded result.

Do not route the B0477 through the arm controller or mount it on the arm for
this Phase-1 architecture. Do not let either USB cable carry the arm's 12 V
actuator-power function. Follow the manufacturer connection instructions for
the received hardware; do not add unreviewed power or ground wiring.

The lower-level provider-neutral `B0477NativeMode` receipt labels its bus family
as `USB_3_X`; that means only “USB 3 family” at the reusable contract seam. It
does not weaken or replace the selected B0477 profile and onboarding policy,
which require observed topology/negotiation specific to `USB_3_2_GEN_1` before
the physical mode gate can be accepted.

## 2. One-time controlled host setup

Run all commands from the repository root in PowerShell. Use the checked-in
launcher instead of a globally installed `rocell`; it anchors execution to
this checkout.

```powershell
Set-Location C:\Users\Jack\Desktop\robot-arm-build
.\setup-rocell.ps1 -Profile hardware
```

The setup script creates `.venv`, installs the project in editable mode with
the `serial` and `vision` extras, runs `pip check`, then runs only
hardware-free status, onboarding-foundation, host, simulator, incapable-provider
connection, and synthetic B0477 checks. The first
installation may need package-index access. The `runtime` profile does not
install the hardware-discovery dependencies, so use `hardware` for arrival.
Use `development` when the test dependencies are also needed.

The root launcher has two deliberate behaviors:

- when `.venv` exists, it runs `.venv\Scripts\python.exe` in isolated mode and
  clears external `PYTHONPATH` influence;
- if `.venv` is absent, hardware-free development commands may fall back to
  global Python, but every `physical-onboard` or `arm-feedback` command is
  refused.

Do not use `-SkipVerification` for normal setup. It skips the post-install
hardware-free checks; it does not make the environment more permissive.

After setup, run the host gate explicitly:

```powershell
.\rocell.ps1 host-doctor --profile hardware --require-pass --json
```

`host-doctor` checks the selected source tree, workspace virtual environment,
Python/platform metadata, Pillow, OpenCV, pyserial, conflicting OpenCV
distributions, and `pip check`. It does not enumerate a device, import a
camera backend, open a camera or arm port, or send a robot command.

Possible top-level results are:

- `READY`: the selected host profile is internally ready;
- `READY_WITH_PHYSICAL_HOLDS`: the host profile is ready but a physical hold,
  such as the unpromoted static-camera freeze, remains; or
- `BLOCKED`: fix the listed environment blockers before continuing.

`--require-pass` enforces the host environment only. It does **not** clear a
physical hold or change the active build release.

Validate the complete additive onboarding contract graph explicitly:

```powershell
.\rocell.ps1 physical-onboard verify-foundation --json
```

The expected result is `VALID_ZERO_AUTHORITY_FOUNDATION`, six validated
specialized contracts, `runtime_activation: false`, and ten open implementation
gates. This command reads bounded local files only. Those open gates are an
honest backlog; they are not failures that should be edited away on arrival.

Also run the exact connection lifecycle while hardware remains untouched:

```powershell
.\rocell.ps1 rehearse-physical-connections --require-expected --json
```

This deterministic rehearsal checks the host dependency receipt; persistent
B0477 discovery, open, native mode, manual exposure/gain/white-balance,
flush/freshness, close/reopen identity, and final close; unpowered RoArm
identity; and exactly one synthetic T=105/T=1051 transaction. It accepts no
provider argument, performs no OS device inventory or physical open, and has no
T=104, torque, motion, power, or contact method. Its fault modes are regression
proofs, not observed hardware evidence.

### 2.1 Initialize and verify the M1 v2 store

M1 storage initialization is a separate, explicit, zero-device operation. Run
it on the final Windows/NTFS volume before creating a v2 session:

```powershell
.\rocell.ps1 physical-onboard init-v2-storage --cell-id CELL-A --json
.\rocell.ps1 physical-onboard verify-v2-runtime --cell-id CELL-A --json

$V2SessionId = 'arrival-v2-20260907-cell-a-001'
.\rocell.ps1 physical-onboard new-v2 `
  --cell-id CELL-A `
  --session-id $V2SessionId `
  --json
.\rocell.ps1 physical-onboard verify-v2-runtime `
  --cell-id CELL-A `
  --session-id $V2SessionId `
  --json
```

At every startup, `verify-v2-runtime` reruns the on-volume qualification and
compares its stable identity to the immutable anchor before opening the cell
ledgers. A clear result is
`M1_STORAGE_READY_ZERO_HARDWARE_AUTHORITY`; it must also report
`effect_methods_exposed: false`, `runtime_activation: false`, and zero hardware
operation counters. Do not interpret `effects_allowed_by_m1_storage` as a
hardware permit.

These commands are the supported M1 interface; do not replace them with direct
module calls. The complete storage layout, restart rules, and limitations are in
[M1 qualified zero-hardware onboarding runtime](M1_ZERO_HARDWARE_RUNTIME.md).

If verification instead reports reconciliation or quarantine, stop with the
arm de-energized and preserve the whole deployment. Do not retry an operation,
delete a ledger suffix or owner file, or create another session to escape the
hold. Recovery is evidence-only and manual-review gated; the current CLI has
no automatic recovery or quarantine-clearing command.

## 3. Create a source-bound arrival session

The preferred safe entry point combines the hardware-profile environment setup,
a repeated side-effect-free host gate, a fresh incapable-provider camera/arm
connection rehearsal immediately before binding, and session creation:

```powershell
$SessionId = 'arrival-20260906-cell-a-001'

.\start-rocell-onboarding.ps1 `
  -CellId CELL-A `
  -SessionId $SessionId
```

If `-SessionId` is omitted, the script generates a timestamped identifier and
prints it. `-SkipEnvironmentSetup` is only for a workspace whose `.venv` was
already prepared; the script still reruns `host-doctor --profile hardware
--require-pass`, `physical-onboard verify-foundation`, and
`rehearse-physical-connections --require-expected`. In
either form it never invokes inventory, imports a device backend, opens a camera
or serial port, applies arm power, or sends an arm command. It ends after
`new --prepare-safe` and prints the exact status command.

The lower-level equivalent follows. It is useful when troubleshooting, but does
not permit skipping the setup and host gates.

Choose a stable cell ID and a unique session ID. Omitting `--session-id`
generates one, but an explicit ID is easier to put on photographs and paper
records.

```powershell
$SessionId = 'arrival-20260906-cell-a-001'

.\rocell.ps1 physical-onboard new `
  --cell-id CELL-A `
  --session-id $SessionId `
  --prepare-safe `
  --json
```

`new` binds the session to the active build snapshot, the exact 15-stage plan,
the onboarding policy, every listed controlled input, and every `.py` source
under `software/src/rocell`. `--prepare-safe`
executes at most the first two stages:

1. `workspace_sources` verifies the controlled source closure and base
   fail-closed host state.
2. `static_camera_contract` verifies that the selected software contract is
   B0477/IMX283, USB UVC/USB 3.2 Gen 1, static overhead, persistent-identity
   required, with no backend fallback.

Both are controlled-file and host-metadata checks. They do not enumerate or
open the camera. Passing `static_camera_contract` means the selected contract
is coherent; the evidence still records that the superseding physical freeze
has not been promoted.

Without `--prepare-safe`, create the session and advance each zero-I/O stage
through the challenge workflow below.

## 4. Status, preview, and the exact challenge workflow

Read-only session status verifies the journal and evidence before printing the
current stage:

```powershell
.\rocell.ps1 physical-onboard status --session-id $SessionId --json
.\rocell.ps1 physical-onboard next --session-id $SessionId --json
```

`status` includes the current source-binding comparison and a `next` preview.
`next` without `--execute` is also a preview and has no session effect. Before
executing one controller action, capture and inspect all three preconditions
from the same preview:

```powershell
$PreviewDoc = .\rocell.ps1 physical-onboard next `
  --session-id $SessionId `
  --json | ConvertFrom-Json

$PreviewDoc.result.preview |
  Format-List operation, stage, stage_state, executable, explanation

$ExpectedStage = $PreviewDoc.result.preview.stage
$ExpectedHead = $PreviewDoc.status.journal.head_event_sha256
$ExpectedChallenge = $PreviewDoc.result.preview.challenge.challenge_sha256
```

Proceed only when the displayed stage and operation are the ones the operator
expects and `executable` is true:

```powershell
.\rocell.ps1 physical-onboard next `
  --session-id $SessionId `
  --execute `
  --expected-stage $ExpectedStage `
  --expected-head-sha256 $ExpectedHead `
  --expected-challenge-sha256 $ExpectedChallenge `
  --json
```

The challenge digest binds the session ID, current source binding, journal
event count and head, high-water record, evidence inventory, active stage and
state, and action code. It prevents a preview from being reused after state or
evidence changes. It is a stale-state guard, not an operator signature or a
safety permit.

Discard all three values after every execution or evidence addition. Preview
again before the next action. Never script a loop that previews and executes
physical stages without human inspection.

For either of the first two stages, execution performs the bounded zero-I/O
verification and records PASS or BLOCKED evidence. For any later PENDING stage,
the only executable action is `MARK_WAITING_OPERATOR`; it records
`WAITING_OPERATOR` and performs no physical action. Once a stage is waiting,
the preview becomes non-executable until a separate reviewed assessor acts.

## 5. Retain a physical evidence file

Start the applicable stage first so that it is `WAITING_OPERATOR`, then acquire
the evidence. A direct evidence record must be a nonempty, regular,
non-symlink file inside the workspace, no larger than 32 MiB. The caller must
supply the exact lowercase SHA-256 and a trustworthy UNIX-epoch nanosecond
capture time that is later than the stage's waiting event and not in the
future.

The following example records a newly captured camera-receipt image. Run the
timestamp expression immediately after that capture; do not use it to relabel
an older file.

```powershell
$EvidencePath = 'software\runs\incoming\camera-receipt-front.jpg'
$FileSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $EvidencePath).Hash.ToLowerInvariant()
$CapturedAtNs = [long](([DateTime]::UtcNow.Ticks - 621355968000000000L) * 100L)

$EvidencePreview = .\rocell.ps1 physical-onboard next `
  --session-id $SessionId `
  --json | ConvertFrom-Json

.\rocell.ps1 physical-onboard record `
  --session-id $SessionId `
  --stage camera_receipt `
  --file $EvidencePath `
  --file-sha256 $FileSha `
  --captured-at-ns $CapturedAtNs `
  --label 'received-b0477-front-label' `
  --media-type image/jpeg `
  --expected-challenge-sha256 $EvidencePreview.result.preview.challenge.challenge_sha256 `
  --json
```

Recording copies and hashes the bytes into the session; it never passes the
stage. Because the evidence inventory changes, its challenge is immediately
stale. Preview again before recording another item. Do not put evidence files
directly inside the session directory.

### Typed receipt foundation for reviewed evidence

The strict receipt types in
[`physical_onboarding_receipts.py`](../src/rocell/application/physical_onboarding_receipts.py)
give selected evidence a canonical, stage-specific meaning without adding a
public stage-advance path:

| Receipt | Schema | Bound stage | Diagnostic purpose |
| --- | --- | --- | --- |
| `CameraReceiptInspection` | `rocell.physical_onboarding.camera_receipt_inspection.v1` | `camera_receipt` | Exact Arducam/B0477/16 mm identity, condition, package, purchase-record, and image-evidence review |
| `PowerSafetyReview` | `rocell.physical_onboarding.power_safety_review.v1` | `power_safety` | Power-off state, E-stop evidence, 12 V / at-least-5 A supply observation, polarity, mounts, cables, keepout, and emergency-access review |
| `FirstPowerObservation` | `rocell.physical_onboarding.first_power_observation.v1` | `power_on_observation` | One externally controlled possible-motion event, its timing, observed startup motion, effect certainty, attempts/retries, clearance, E-stop/collision/contact outcome, and media |
| `ControlledOperatorDecision` | `rocell.physical_onboarding.controlled_operator_decision.v1` | One of the three stages above | Exact review binding to the subject receipt and its diagnostic assessment |

Every receipt binds the current source digest, immutable session header, cell,
stage-plan digest, exact stage, and one or more content-addressed evidence
packages. The parser requires canonical UTF-8 JSON, exact fields, bounded data,
and matching internal hashes. The only derived dispositions are
`DIAGNOSTIC_READY`, `HOLD`, and `SIDE_EFFECT_UNCERTAIN`. There is no generic
PASS receipt. An operator acknowledgement cannot upgrade a hold or uncertainty,
and even `DIAGNOSTIC_READY` permanently reports no power, motion, contact,
release, build-promotion, or session-mutation effect.

These types and assessors are a tested Python foundation only. The current
public CLI cannot create one from free-form input, apply one to the journal, or
pass a reviewed stage. Store the underlying evidence through `record` and wait
for the separately reviewed assessor instead of editing the journal.

## 6. Validate the 55-row hardware intake

Work on a copy of the controlled template, never the template itself:

```powershell
New-Item -ItemType Directory -Force -Path software\runs\intake | Out-Null
Copy-Item `
  -LiteralPath hardware\static_overhead_camera\hardware_intake_template.csv `
  -Destination software\runs\intake\arrival-20260906-cell-a-001.csv
```

Rows must remain ordered `INT-001` through `INT-055`, and the first six
question columns are locked. Only `observed_value`, `instrument_or_method`,
`evidence_path`, `status`, and `notes` may be filled in. Evidence paths must be
workspace-relative regular files. A `PASS` or `NA` row requires an observed
value, method, and evidence path. `HOLD` and any not-captured/not-measured/open
status keep the sheet incomplete.

Validate a partial or completed copy without attaching it to a session:

```powershell
.\rocell.ps1 physical-onboard intake `
  --file software\runs\intake\arrival-20260906-cell-a-001.csv `
  --json
```

The current v1 validator is whole-template-only. Add `--require-review-ready`
only when all 55 rows are expected to be PASS or NA; do not interpret that as a
Stage-3 requirement. The v2 roadmap assigns rows progressively to their first
honest measurement stage and keeps `INT-055` post-diagnostic. To retain the
generated legacy full-template assessment in an active, waiting
`camera_receipt` stage, use a fresh challenge:

```powershell
$IntakePreview = .\rocell.ps1 physical-onboard next `
  --session-id $SessionId --json | ConvertFrom-Json

.\rocell.ps1 physical-onboard intake `
  --file software\runs\intake\arrival-20260906-cell-a-001.csv `
  --session-id $SessionId `
  --expected-challenge-sha256 $IntakePreview.result.preview.challenge.challenge_sha256 `
  --json
```

The assessment binds the template, intake, and every referenced evidence file
by hash. `ready_for_human_review: true` means the question set is complete
enough for human review; it is not an acceptance verdict and does not pass
`camera_receipt`.

## 7. Read-only camera and serial inventory

Inventory is the one implemented command that reads physical-device metadata,
so run it only after the hardware-profile host doctor passes and the intended
USB cables have been connected under the staged physical procedure:

```powershell
.\rocell.ps1 physical-onboard inventory `
  --session-id $SessionId `
  --json
```

On Windows it runs a fixed, bounded Plug-and-Play camera query. On Linux it
reads video sysfs/by-id metadata. It uses `pyserial` only for
`list_ports.comports()` metadata. It does not instantiate `Serial`, open a COM
port, open a `/dev/video*` node, open a UVC stream, capture a frame, or select a
device.

Inventory reports all camera and serial candidates, observed VID/PID, unit
serial where available, OS instance identity, possible persistent IDs,
ephemeral locator, driver information, and unresolved identity blockers. A
bare camera index, `COM` number, or `/dev/videoN` ordinal is not accepted as a
persistent identity. Use `--require-candidates` only when at least one camera
and at least one serial candidate are both expected; it does not require or
prove that either candidate is the correct device.

When a matching identity stage has already been placed into
`WAITING_OPERATOR`, inventory can retain its generated report:

```powershell
$InventoryPreview = .\rocell.ps1 physical-onboard next `
  --session-id $SessionId --json | ConvertFrom-Json

.\rocell.ps1 physical-onboard inventory `
  --session-id $SessionId `
  --record-stage camera_identity `
  --expected-challenge-sha256 $InventoryPreview.result.preview.challenge.challenge_sha256 `
  --json
```

`--record-stage` accepts only `camera_identity` or `arm_identity`, and it must
match the active waiting stage. The current CLI does not yet contain the
reviewed assessor needed to advance `camera_receipt`, so a CLI-only session
cannot reach those identity stages yet. Inventory without `--record-stage`
still provides a zero-selection diagnostic report.

Most importantly, inventory does **not** open, select, connect, or qualify the
B0477 or the RoArm. It does not observe camera modes, controls, USB 3 topology,
negotiated link speed, stream freshness, RoArm firmware, serial framing, or one
T=105/T=1051 exchange. Those remain separate evidence gates.

## 8. Verify session integrity

Run this after every evidence-capture block and before any handoff:

```powershell
.\rocell.ps1 physical-onboard verify --session-id $SessionId --json
```

Verification rechecks the current controlled-source binding, immutable header,
contiguous hash-chained journal, high-water record, exact directory shapes,
content-addressed evidence manifests, payload hashes, sizes, and authority
invariants. Use the stricter completion gate only when the complete diagnostic
workflow is expected:

```powershell
.\rocell.ps1 physical-onboard verify `
  --session-id $SessionId `
  --require-complete `
  --json
```

With the current controller, `--require-complete` is expected to return nonzero
after the first manual stage because the reviewed physical assessor is not yet
implemented. Do not suppress that result or edit the journal to make it pass.

## 9. Session and evidence layout

Sessions are created only below the policy-selected root:

```text
software/runs/physical-onboarding/
  onboarding-<session-id>/
    header.json
    journal/
      high-water.json
      event-000000.json
      event-000001.json
      ...
    evidence/
      evidence-<package-sha256>/
        payload.bin
        manifest.json
```

`header.json` is immutable and binds the session/cell identity, stage plan, and
controlled-source digest. Journal events are append-only and chained through
the previous event hash. `high-water.json` anchors the committed tail and
records whether an uncertain side effect was ever committed. Each evidence
directory is content-addressed; `payload.bin` is written before
`manifest.json`, and the manifest is the final package file.

Do not rename a session, edit JSON, replace a payload, add a note file, add a
shortcut/symlink, or delete an event. The verifier intentionally rejects any
extra or missing entry. Keep human working files under a separate workspace
path such as `software/runs/incoming/` and let `record` copy them into the
immutable store.

## 10. Arrival-day stage sequence

The exact stage order is locked. A later stage cannot fill an earlier gap.

| # | Stage | What software can do now | What still requires physical evidence/review |
| ---: | --- | --- | --- |
| 1 | `workspace_sources` | Automatically hash the controlled checkout and strictly validate the runtime-inactive six-contract v2 foundation plus base fail-closed state | Confirm this is the intended build/cell; open v2 implementation gates remain blockers |
| 2 | `static_camera_contract` | Automatically verify the selected static B0477 software contract | Promote a reviewed superseding static-camera freeze only after physical evidence exists |
| 3 | `camera_receipt` | Mark waiting; the current CLI can validate/retain only the legacy whole-template intake and direct files | Photograph and measure the received B0477, lens, cable, case, fasteners, and labels; v2 progressive due-stage intake and reviewed assessor are not implemented |
| 4 | `camera_identity` | Inventory OS metadata without opening/selecting; retention hook exists | Prove unique VID/PID/unit serial/persistent path and reconnect/reboot stability |
| 5 | `camera_mode_controls` | Contract and fake-provider schemas/tests exist for native mode plus manual exposure/gain/white balance; software does not read the lens rings | Open the correct UVC device under an explicit gate; read back `5472 x 3648 @ 9 YUY2`, exact USB topology/speed, exposure/WB/gain, and reopen stability; physically set, lock, witness, photograph, and later verify focus/aperture |
| 6 | `camera_frame_freshness` | Synthetic stale/rewrapped-frame rejection exists | Use a visible time-varying challenge and measure sequence, negotiated stride/sample length, timestamps, latency, drops, freshness, and stability on the received unit; distinct hashes alone are insufficient |
| 7 | `optics_intrinsics` | Synthetic optical and ChArUco rehearsals exist | Perform preliminary focus/FOV/lighting/throughput screening and precommit the production acquisition/partition plan; do not promote temporary-fixture intrinsics |
| 8 | `static_registration` | Synthetic tag detection, pose, tag-loss, and artifact graph exist | With actuator 12 V disconnected, retain the final mount/light/cable/focus stack; acquire production intrinsics, measure the tag map and camera-to-board transform, and test held-out K0/P0, bump/reseat/drift and route visibility |
| 9 | `arm_identity` | Inventory serial metadata without opening the port | Prove exact Pro/controller/supply/USB/serial/firmware identity and one exclusive owner while 12 V remains off |
| 10 | `power_safety` | Keep the stage blocked until evidence exists | Install/test physical E-stop, gravity containment, anti-shift, startup sweep, observer procedure, and limits with arm off |
| 11 | `power_on_observation` | Record only a waiting/evidence boundary; issue zero commands | Under the future unique envelope, clear the cell, apply power once under observation, record any automatic motion/power-cut consequence, and prove final de-energization |
| 12 | `feedback_only_connection` | Strict 115200/RTS-off/DTR-off/T=105/T=1051 contracts and fake tests exist | Use a new energization envelope; consume the one-use effect permit before serial open; retain any reset/pre-request bytes; make one bounded feedback transaction with no retry; close and prove final de-energization |
| 13 | `reference_frame_calibration` | Artifact dependencies and synthetic stale-edge tests exist | Run a conservative externally permitted empty-cell bootstrap first, then a separately permitted reference campaign; solve joint/controller/arm-to-board/free-state-TCP/device-map artifacts with held-out checks; independently prove final actuator disconnection after each campaign; contact compliance remains open |
| 14 | `noncontact_acceptance` | Dense virtual keyboard/phone routes, collision diagnostics, failure injection, and outcome flows exist | Separately release reduced-speed empty-cell motion, stop/power-loss/safe-park tests, then device-by-device hover routes with no descent; every campaign ends with independently proven actuator disconnection, while unknown final power seals uncertain and quarantines |
| 15 | `physical_handoff` | Verify immutable diagnostic evidence and enumerate open gates | Build/review the four-phase `CommissioningBundle` and target error budget; `INT-055`, promotion, keyboard contact, and phone contact remain later controlled releases |

The practical physical order is therefore: inspect everything with all power
off; qualify the static camera while the arm is de-energized; retain the final
camera installation and calibration; identify the arm with actuator power off;
finish E-stop/gravity/collision controls; observe the first power event with
zero host commands; perform one feedback-only exchange; then conduct separate
reference, empty-cell, and noncontact programs. Keyboard and Android contact
come last and are independent releases.

## 11. Recovery and no-retry rules

Resume is verification, not replay.

- `PENDING` may be previewed again. A zero-I/O check may be rerun only under a
  fresh challenge.
- `WAITING_OPERATOR` means collect and review evidence; the controller will not
  pass it automatically.
- In the current v1 journal, `ACQUIRING` after a crash means an action may have
  started. The only derived next action is manual reconciliation; do not rerun
  it. V2 will replace this overloaded state with a cell-global unsealed attempt
  plus quarantine, but that coordinator is not implemented yet.
- `SIDE_EFFECT_UNCERTAIN` is terminal for the session. Preserve the session and
  determine the physical state under an approved recovery procedure.
- Source-binding drift blocks execution. Preserve the old session for audit,
  review the controlled changes, and create a new session; never rewrite its
  header.
- After disconnect, timeout, controller reset, camera loss, E-stop, power loss,
  or uncertain power behavior, do not automatically reconnect, reopen, retry,
  initialize, home, or park. First make the cell physically safe, then obtain
  fresh identity/preflight evidence and use the future reviewed recovery path.
- The T=1051 reply has no echoed host transaction ID. A stale line cannot be
  made trustworthy by retrying; the eventual feedback procedure requires a
  quiet buffer, exactly one request, retained raw timing/bytes, and close.

The current public CLI exposes no command to pass a reviewed physical stage,
invalidate/release a physical calibration, reconcile an in-flight device
effect, or grant power/motion/contact. That is an intentional current gap, not
an operator step to work around manually.

## 12. Current implementation boundary

Automated now:

- reproducible workspace `.venv` setup and dependency consistency checks;
- a safe combined starter that reruns the hardware-profile host gate and creates
  only a `--prepare-safe` diagnostic session;
- strict read-only validation of the source-bound v2 foundation: closed effect
  classes, progressive intake design, epochs, hazards, workcell ICD, and target
  accuracy, with runtime activation and every physical authority false;
- the M1 zero-hardware runtime: fresh Windows/NTFS qualification against a
  stable anchor, guarded write-through publication, ordered OS leases,
  cell-global attempt and quarantine ledgers, source-bound v2 session creation,
  and cross-store verification with zero hardware-operation counters;
- source-anchored launcher and side-effect-free host doctor;
- a ten-step incapable-provider B0477/RoArm connection rehearsal with nine
  deterministic fail-stop cases and permanent zero physical effects;
- source-bound, append-only onboarding sessions with exact next-action state;
- zero-I/O verification of the first two stages;
- stale-state challenge enforcement for every session mutation;
- strict legacy whole-template 55-row intake validation and evidence hashing;
- bounded Windows/Linux camera and serial metadata inventory with no device
  opens or selection;
- canonical, exactly bound zero-authority receipt and assessment schemas for
  camera receipt, power safety, first power, and operator review; these are not
  yet connected to a CLI stage assessor;
- immutable, content-addressed evidence retention; and
- full session/source/journal/high-water/evidence verification.

Not automated or physically proven now:

- v2 progressive intake execution, effect-capable coordination, bounded
  workers/one-use permits, every-energization envelopes, calibration phases,
  accuracy closure, or the `CommissioningBundle` runtime boundary;
- full independent deployment qualification of the M1 fault matrix and an
  off-machine anchor against coordinated rollback; torn suffixes, stale owners,
  and quarantine are manual-review stops with no automatic repair or retry;
- exact received camera or arm identity;
- persistent device selection, USB 3 topology/speed, UVC opening, mode/control
  readback, physical frame capture/freshness, focus, intrinsics, or static
  registration;
- arm serial opening, firmware readback, live T=105 feedback, controller
  initialization, reference calibration, or safe park;
- the E-stop, gravity containment, anti-shift, collision envelope, power-on
  motion, motion limits, force/compliance, keyboard press, phone tap, or outcome
  observation; and
- reviewed physical-stage PASS decisions, a superseding static-camera freeze,
  application of the typed receipt assessments to a session, or any physical
  release.

The active build remains `2026-09-01_CELL-A`, Freeze 011, with physical release
`UNRELEASED` and `safe_to_power_robot: false`. Current status permits digital
planning and simulation only. Camera capture is blocked by missing exact
identity and qualification; arm feedback is blocked by unreleased robot power;
empty-cell motion, descent, keyboard contact, and phone contact remain blocked.

The legacy and M1 command names and controlled-source references are covered by
parser-help, source-binding, and M1 integration tests. M1 tests create only
temporary qualified storage and v2 diagnostic sessions. No device inventory
was run, no camera or serial port was opened, no power operation was performed,
and no hardware, motion, or contact command was sent.
