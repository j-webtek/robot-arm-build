# Camera capability and configuration integration

Status: implemented and verified as a rehearsal increment after the `05b56230`
contained-camera checkpoint. This advances DEV-008 software integration; it
does not close the full ticket, release physical operation or replace the
camera/arm developer playbook.

## Gap and operator outcome

Before this increment, the wizard could retain native-format fixture captures
but its only camera knob was a synthetic image-brightness offset. It lacked
reported mode/control inspection, pre-capture settings validation, and a
requested-versus-observed readback view. The existing native client already
exposed typed probe/capture/control contracts. This implementation reuses them;
do not add direct browser-to-device I/O or a parallel native camera client.

Add an explicit finite capability probe in the due first camera stage, followed
by a staged configuration bound to its exact retained report. Show every
reported mode and electronic control range/unit/auto-manual capability, and
explain unavailable controls. A selected capture uses the immutable staged
settings through the existing client and retained process path. Applying a new
configuration is a separate explicit campaign, never an in-stream write or
automatic renewal. Manual lens focus/aperture remain physical adjustments.

## Work boundaries

1. Windows owner: extend the fixed incapable camera runner/codec/child with
   probe and validated electronic-control capture requests. Preserve old
   no-control capture compatibility and the closed command/identity/output
   ownership rules. The child reports fixed, explicitly modeled capabilities;
   those values are not claims about the purchased unit. Leave the real native
   helper, native camera client and Win32 resource-owner implementation unchanged.
2. Evidence owner: a pure source/request-bound probe evidence and capability
   model, strict mode/control choice validation, immutable configuration hash,
   and requested/readback comparison. Retain full bounded process bytes before
   a known probe seal. A complete probe is not a complete capture or calibrated
   camera. Reuse existing native typed contracts and their validation semantics.
3. Interface owner: render cached capability/configuration/readback projections
   in browser and terminal. No rendering I/O, raw endpoints, executable paths,
   control-console text, hidden defaults or inferred hardware support.
4. Root integration: M1 probe registration and exact consumed-permit admission,
   due-stage sequencing, staged settings/capture join, retained result/reopen
   verification, action registry and public-service diagnostics/export tests.

Keep the existing in-process camera action available and distinctly labeled.
Do not silently substitute it after a contained-process failure. An uncertain
probe/capture holds its original cell; missing capability evidence is not an
invitation to guess ranges, choose the first mode, repair state or replay work.

## Verification and acceptance

- Imports, construction, status, action preview and configuration staging must
  never activate a camera or dispatch a child. Execution is explicit.
- Probe has no requested mode, controls, frames or output directory. It has one
  bounded source-open/close lifecycle; control writes/frame counts are zero.
- Exact reported modes are server-owned opaque choices. Capture requests must
  obey the supported YUY2/layout/budget contract; other reported formats can be
  displayed as unavailable, not silently converted or relabeled.
- Validate each requested control's identity, integer value, supported mode,
  inclusive range and step. Reject unknown/duplicate controls and stale probe,
  identity, source or settings epochs. Never infer support from a friendly name.
- Preserve requested values separately from observed readback. Manual values
  must match exactly; auto mode must actually read back auto and its observed
  value is not the requested fixed-value promise. Missing/coerced readback holds.
- Real owned fixture processes cover probe and configured finite capture;
  M1 tests cover full retention before sealing, stage review/reopen, cancellation,
  faults, and no replay. UI/API/export checks use the same service projections.
- Freeze production source before real-store/public smoke verification. Retain
  exact test scope, source hash and exported report identifiers in this document.

## Authority and remaining physical work

The shared configuration model consumes validated native-shaped observations;
the test producer is incapable and its reports are explicitly synthetic.
The physical camera action stays held until the existing physical coordinator,
provider admission, controlled static-primary migration and received-unit gates
are independently satisfied. No source activation flag or controlled hardware
file changes in this increment. No OS device inventory, real camera/serial open,
arm energization, motion or contact is part of the development tests.

Completing this increment will not complete the overall objective: native
physical runtime admission, real arm connection/startup integration, installed
calibration acquisition, the last two rehearsal stages and arrival release
qualification remain required by the playbook.

## Operator sequence implemented in this increment

Launch `start-rocell-wizard.ps1` in its default rehearsal mode. The assigned
export folder remains `software/runs/wizard-exports`, as selected by the user.
Use the guided durable rehearsal to collect, assess and review stages 1–4,
then collect the first camera stage. Every operation has a preview followed by
explicit execution; there is no automatic device discovery or power-on.

| Action | What it establishes | What it does not establish |
| --- | --- | --- |
| Prepare synthetic camera settings | Image fixture brightness epoch | A UVC exposure or brightness setting |
| Probe contained camera capabilities | One retained process report with exact modeled mode/control descriptors | Real camera support, capture, or settings application |
| Stage reported camera mode and controls | Validated immutable intent bound to that report, source and identity | Applied settings or readback |
| Run contained incapable camera-process campaign | Exact finite capture, retained bytes and independent modeled readback | A live camera connection or physical calibration |
| Assess and review | Acceptance of the exact retained rehearsal evidence | Any physical-stage release |

The mode selector starts blank. Six electronic controls are modeled by the
fixed incapable producer: exposure, gain, white balance, brightness, contrast
and saturation. Their ranges are driver-unit test fixtures, **not purchased-unit
specifications**. Each intent starts at **Do not request a change**; a manual or
auto request must be supported by the exact report. Only the fixed full-size
5472 × 3648, 9/1 fps YUY2 mode is executable in this placemat rehearsal. Other
generic format-contract eligibility is not an alternate executable fixture.

A complete probe can be reopened before configuration without rerunning it.
Configuration is staged once in stage 5. Stage 6 reuses its exact settings and
requires a new explicit capture; it does not silently reconfigure the device.
Once a session chooses the probe path, it cannot fall back to the legacy
in-process or unconfigured capture. Faults preserve original diagnostics and
hold the session, without repair or automatic retries.

The contained probe owns a new empty `camera-probe-<attempt-id>` subdirectory
inside its session. It creates no image files. A successful capture has a
separate `binary-fixture-<id>` tree; its dataset epoch binds both the image
fixture brightness and electronic configuration plus the original probe hash.
Raw child output remains in the original M1 record. Normal exports include
bounded readable projections and exact retrieval hashes, not raw frames.

Lens focus and aperture must still be adjusted physically and verified with
the installed overhead geometry. Electronic control changes are protocol and
readback tests; their effect on real image noise, exposure and color is not
photometrically simulated or qualified.

Developer presentation details: [browser and terminal contract](WIZARD_CAMERA_CONFIGURATION_PRESENTATION.md).
Evidence and restart details: [pure evidence contracts](CAMERA_CONFIGURATION_EVIDENCE.md)
and [audited original-store reopening](OWNED_CAMERA_REOPEN.md).

## Reproducible software checks

The focused real-storage integration test is
`software/tests/unit/test_wizard_camera_configuration_integration.py`. It uses
actual Windows NTFS M1 storage and the fixed incapable child, not a physical
camera or a cloned/pre-passed stage journal. It collects/reviews stages 1–4,
probes, reopens before staging, captures with manual gain and auto exposure,
reopens pending review and performs stage-six configuration reuse. Run it only
with production source frozen; its source checks fail if the workspace changes.

The public-service smoke runner also supports the complete configured path:

```powershell
.\.venv\Scripts\python.exe software\scripts\wizard_owned_camera_smoke.py --probe-and-configure --assess-and-review --frame-count 1 --fault none --expected-source-sha256 SOURCE_HASH
```

Replace `SOURCE_HASH` with the current verified full fingerprint recorded below.
This creates a fresh rehearsal and verified diagnostic export in the assigned
workspace folders. It is not a command to reopen, repair or replay an old store.
`--fault control-readback-drift --probe-and-configure` instead exercises a
held configured capture and exports its failure; omit `--assess-and-review`
for that fault run. The script uses the same public prepare/execute API as the
UI and asserts physical camera/arm status stays `NOT_CONNECTED`.

## Verified checkpoint — 2026-09-08

Frozen production fingerprint:
`0b8507b80c5ab95b6157e1c1ab37adc82ab8913c31c1ae2d4c3233e4f1246ba2`.
Rechecked unchanged before/after the source-bound integration and public smoke.

- **1,996 selected tests passed**, 3,310 deselected, in 141.55 seconds. Selection
  includes Arrival/actions/workers/diagnostics, device selection/native helper,
  Windows camera preparation/identity/ingestion, owned process/camera, reference
  and feedback stage integration, plus the new camera configuration/probe tests;
  excludes the two slow actual-M1 camera integration files. This is not a whole
  repository-suite claim. Earlier agent test selections overlap this lane and
  must not be added to its count.
- **Actual NTFS + contained-process workflow: 1 passed in 276.45 seconds.**
  The test executed one probe and two full-resolution captures; passed exact
  probe-only reopening, staged settings, readback, pending-review reopening,
  review and stage-six reuse. Camera workers did not rerun during reopening or
  review. Fresh source-derived prerequisites were actually collected/reviewed.
- Black checked 15 production Python files; mypy passed those 15 files; Node
  checked `app.js`. Browser/terminal tests include actual producer projections,
  malformed-data rejection, closed fields and publication/logging boundaries.
  No fresh visual browser inspection or physical camera image is claimed.
- Inert launcher: zero operations, no configuration report, both devices
  `NOT_CONNECTED`, all 15 physical stages pending, chosen workspace export root.
  The six-contract foundation validates with runtime activation false. Nominal
  placemat checks pass under unchanged Freeze 011; its static-primary successor
  remains a separate controlled migration, not performed here.
- Offline wheel built without dependencies, network resolution or installation:
  `software/runs/wizard-package-check-0b8507b8/rocell-0.1.0-py3-none-any.whl`.
  Size 1,610,498 bytes; SHA-256
  `851031a914b0da4fe4688b18cec5f0db514be3815742670cfb9ec0c59dada84b`.
  All 16 selected changed source/UI entries byte-match the working source.
  This is an offline packaging check, not an installed-hardware qualification.

### Public API nominal run and assigned-folder export

The public smoke completed 21 explicit actions including stage-five assessment,
review and export. It used manual gain 32 and automatic exposure in modeled
driver units, with exact observed flags/values matching the requested semantics.
No native hardware helper, OS device inventory, serial endpoint, power, motion
or contact action was invoked. The nominal smoke shut down its service after export.

- Launch: `wizard-af32c22d265a4e6d80099ebd6dd379d0`.
- Rehearsal: `rehearsal-4935fc5405ef4e22bbfa54f468dec060`.
- Probe evidence:
  `88a0373fb413e7e1cf63511890812f14c5441ac7b4dca45586f95da0a87c7f8e`.
- Capture attempt: `attempt-bed51fb083c4410ea86411a2990f01f8`.
- Complete private retained capture hash:
  `177b80046db2e335e0ea478b8208119f1d59ac1f08269aecfebbe79a928de8b7`.
- Effective dataset epoch:
  `87bbc2c8228542f73ac53e61bbaf70d42acb6d63b143b1090d994ee7edb8d95a`.
  Retained dataset: 40,108,288 logical bytes, including full YUY2 frame and PNG.
- [Readable export](../runs/wizard-exports/wizard-20260908T044554437410Z-3560405ff7fc41e8b087917e4322bd52/README.md):
  independently `VERIFIED_DIAGNOSTIC_EXPORT`, 11 payload files, 291,829 bytes,
  physical authority `NONE`. Manifest SHA-256:
  `c36771c5593d1d48b11f6d0bd7440b2bdbab2eea4e74f5fe5a0db6caf60779f0`.
  The export contains bounded probe/configuration/readback projections and exact
  retrieval hashes. Full raw process/capture evidence remains in its original
  M1 record and native dataset, not the public report.

### Public API readback-drift run

A separate fresh session completed 19 explicit actions, ending in the expected
failed capture and a successful verified export. Launch
`wizard-049d0a05fd334371bf3e7122110a776e`; rehearsal
`rehearsal-bf3bdc6cf4364687890fb43887ea7288`.

The fixed child completed and its OS tree exit was confirmed, but its raw
response reported manual exposure flags after an auto request. The unchanged
camera client rejected this with `INVALID_CAMERA_CONTRACT: requested control
did not read back exactly`. No typed native receipt, accepted dataset, new
preview, stage assessment or review was published. The campaign sealed
`SEALED_UNCERTAIN` and latched quarantine; process exit alone did not establish
a valid camera response or accepted native cleanup. No retry or fallback ran.

- Failed capture attempt: `attempt-17c9d58ba40c4c3e8f79f4a6a691693a`.
- Complete private failed evidence: 10,669 bytes, SHA-256
  `64c4ccaed3ea52828ef08b30baa98b13c8811a25771fe0638eea8f235e594fcc`.
  It retains the exact request, 3,199 raw stdout bytes, process observations and
  parser error. Raw content was inspected after the run to confirm the injected
  mismatch, not promoted into a trusted native receipt.
- [Readable fault export](../runs/wizard-exports/wizard-20260908T044808516258Z-8ece33b8d5ae430f816d781499282199/README.md):
  independently `VERIFIED_DIAGNOSTIC_EXPORT`, 11 payload files, 215,166 bytes,
  physical authority `NONE`. Manifest SHA-256:
  `7ecbdb129cc531f9511ce2ccda25965334f0c845944b14604d24172b8b26a842`.

The current UI shows the hold and process/native-validation blockers, while
the exact parser message/raw failed response stays in original M1 evidence.
A bounded, verified failure-code/detail projection is a useful next developer
improvement; do not weaken native validation merely to render a rejected receipt
as a successful readback. The fault smoke also shut down its service after export.

Existing prior-source sessions, datasets and exports were not migrated,
rebased, overwritten or repaired. The broader goal remains active: physical
camera/arm admission, installed calibration, the final two rehearsal stages,
and eventual separately authorized motion/contact are still required.
