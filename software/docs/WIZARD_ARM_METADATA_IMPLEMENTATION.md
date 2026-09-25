# Native arm identity onboarding increment

## Scope and operator flow

This increment connects the existing Arm page's reviewed serial candidate to
the existing Windows Configuration Manager metadata collector. It does not
open a COM port or construct a `ReviewedControllerBinding`. Model, firmware,
boot behavior, electrical isolation and physical qualification still require
their separate evidence. Freeze 011 and all physical stage holds remain intact.

Implementation status: integrated and tested on 2026-09-08. Production source
binding: `c3739a7e4f0c1211cd1813b30fc7d3d3f548f48de3f94a81f34d49f8621dd5b0`.
The [packet/correlation API](WIZARD_NATIVE_ARM_METADATA_API.md) specifies the
strict fields, provenance, resource bounds and deliberate limits.

1. Explicitly inspect generic device metadata with actuator power disconnected.
2. Review the intended SERIAL candidate from that exact inventory.
3. Explicitly inspect native arm metadata. The checked-in diagnostic child
   acquires present COM-interface and device-node properties, including driver
   identity. The main application never calls the native collector from a
   constructor, page read, refresh or preview.
4. Compare the fresh generic/native observations with the reviewed candidate.
   Missing fields, changed identity, duplicate matches and incomplete collection
   remain visible holds. No port is guessed from a friendly name or COM number.
5. Review the retained result in the Arm page and export to the assigned
   `software/runs/wizard-exports` folder. This is metadata evidence, not a
   successful hardware connection, calibration or stage acceptance.

For the default **rehearsal** launch, the existing shared inventory action is on
**Camera → Rehearse device discovery and selection**. Run its nominal fixture,
then return to **Arm → Review arm metadata candidate** and explicitly select the
synthetic candidate. Next use **Rehearse native arm identity correlation**. The
physical Windows inspection is a different action and stays unavailable in
rehearsal. No candidate or acknowledgment is automatically selected.

## Implementation contract

- Two closed actions: physical Windows metadata inspection and a separately
  labelled incapable rehearsal. Explicit consent fields default to false.
- Reuse `WindowsControllerMetadataAcquirer` in the existing fixed diagnostic
  subprocess. Its bounded native calls are enclosed by the parent's timeout,
  cancellation, output and cleanup checks. No new arbitrary executable or
  device-path inputs, retry loop, native-camera launch or serial API is added.
- Strictly decode the existing typed snapshot. Recompute hashes and correlation
  from retained bytes; reject unknown fields, normalization drift, provenance
  substitution, nonzero effects and malformed/oversized responses.
- Bind publication to the original current generic review, application launch
  and source. New inventory/review, Stop, source drift, diagnostic redaction or
  failed completion logging must not leave a current successful result.
- Cache a compact, truthful UI projection. Retain full bounded evidence for
  diagnostics independently of rotating result cards. Original observations
  are not edited to match the selected candidate.
- Distinguish `METADATA_CORRELATED` from `HELD`. Neither status grants persistent
  open authority or establishes that the received device is a RoArm-M3 Pro.

## Work ownership and verification

The native-metadata agent owns the strict snapshot/report codec, incapable
fixtures and fixed worker branch. The main agent owns the action registry,
service integration, cancellation/publication and documentation. The UI agent
owns the cached browser/terminal display and presentation checks. Independent
integration tests cover invalidation, result retention and exports.

Test with injected/incapable metadata only: nominal, missing native fields,
duplicate mapping, changed device, incomplete inventory, malformed IPC,
cancel/timeout, failed log, source change and redaction. Exercise the real
diagnostic subprocess only with rehearsal fixtures. Do not enumerate this
host's devices, open ports, execute camera helpers or claim received-hardware
verification as part of development. Record exact results after integration.

## Verification record

Production files: `application/wizard_native_arm_metadata.py` (strict codec and
correlation), `wizard_worker.py` (explicit child-only collector/fixture branch),
`wizard_actions.py` (two closed actions), `wizard_diagnostic_coordinator.py`
(metadata-effect schema), `arrival_wizard_service.py` (original-review binding,
publication, cached summary and dedicated retention), and `ui/static/app.js` /
`ui/terminal.py` (strict cached presentation). These paths are below
`software/src/rocell`.

- 66 new codec/worker tests, 51 public service integration tests, 57 UI tests,
  10 closed-action tests and five smoke-harness tests. All use incapable data;
  modeled physical-shaped tests explicitly forbid actual native collection.
- Final combined native-arm plus diagnostic-runner selection: **249 passed**
  in 16.29 s. This includes the two added stalled-child/uncertain-cleanup tests.
- Broader selected regression: **2,800 passed, one failed, eight slow tests
  deselected** in 342.89 s. The failure was Windows `ConnectionAbortedError`
  10053 while an existing HTTP rejection test waited for its response, not a
  failed status/authority assertion. The entire HTTP/UI test file subsequently
  passed **59 tests in 5.38 s**, without production or test changes. Do not
  describe the original broad run as wholly green or claim its OS error cause
  has been established. The broad run predates the five new harness tests.
- Black checks, mypy on the touched application/terminal modules, Node syntax,
  and both launcher `-Check` modes pass. No driver or dependency installation.
- Offline local wheel builds successfully with `--no-index --no-deps
  --no-build-isolation ./software`; all **256** packaged source/assets match.
  Wheel under `software/runs/wizard-package-check-c3739a7e/`, SHA-256
  `d5a13489796f0593b0042a5c4c8cebced1abd2d2a508cc12dab47bbdf9670234`.

### Actual public subprocess workflow and export

The source-excluded script `software/scripts/wizard_native_arm_metadata_smoke.py`
uses the real public service and fixed subprocess for **incapable** inventory
and native metadata. It then runs nine notes to rotate the ordinary report,
exports once, verifies the full dedicated report byte-for-byte and checks all
15 physical stages remain pending. It requires the independently recorded
source hash and refuses physical/native inventory actions.

The first run completed every action and verified the export, but its harness
called nonexistent `service.close()` in `finally`. That cleanup-only script
error is preserved in the turn output; it does not invalidate the already
verified diagnostic artifact. The script now calls the existing `shutdown()`;
a no-device cleanup regression test covers that API. A separately identified
fresh rehearsal validated the corrected harness and exited **0 in 3.74 s**.
No uncertain physical operation or original M1 attempt was replayed.

Corrected-harness session: `wizard-673e341fd6d144498c578e6a20d63dca`.
Correlation operation: `operation-a65696e39bf3473eb1a066f3a1554f88`.
Full report SHA: `b1ab7c6bf6d16d96c4ff31c27888ed0ec6b43bbfc93b627c727573f6fce053f8`.
Export leaf: `wizard-20260908T154418394768Z-5809f794653e4f8081b36eb19e022aaa`.
Manifest SHA: `2728d2b2c000276c53e60e724c0d603d5910f8397b6080b5978a13d0135092bb`.

The original first-run export remains unchanged at
`wizard-20260908T153546595990Z-8e5957456fc14b808f7fcf2ba807e5d2`, manifest SHA
`174dd249416397bf72d476365da0808ea0df0f9864cb26851b37549687a10d25`.
Its complete report remains independently verifiable after result rotation.

### Actual browser verification

A fresh rehearsal launcher and in-app browser performed the shared fixture
inventory, explicit synthetic candidate selection/reviewer acknowledgment,
native fixture inspection and assigned-folder export. The visible panel showed
`CURRENT / METADATA_CORRELATED`, all nine fields observed, and explicit
`INCAPABLE REHEARSAL / NOT_CONNECTED / NOT_QUALIFIED`. The original launch,
source and candidate hashes remained visible. No browser errors/warnings were
reported. The computer-use skill guided this UI verification; no OS settings,
native device controls or permission dialogs were touched.

Browser session: `wizard-98103d05c6114f648d88a0f2c23b9ba3`.
Correlation operation: `operation-6a095c059ec8455c8590dfc316859061`.
Full report SHA: `e57b100fbb6f88849613a126f36a452f35bc91a657fec3efd93f4a58be0daf15`.
Export leaf: `wizard-20260908T154117635195Z-3b684e7e2aad4dbb92d8f5548f7bab9c`.
Manifest SHA: `31c7f2c3337799df4717595b5c2f84f1cf7941f0b9e6ba5d7783cff1caac55eb`.
Independent file-only export and strict full-report verification passed.
The owned test tab/server were closed; its listener was confirmed gone.

All export leaves above are under the user-selected
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
These are diagnostics, not hardware receipts or installation qualification.

## Remaining path to physical use

This is one connection prerequisite, not completion of the application goal.
Still needed: durable physical prerequisite submission/assessment/review,
reviewed static-camera migration, physical runtime qualification, camera
acquisition and calibration publication, arm model/firmware/boot evidence and
identity-to-open validation, reviewed power/first-feedback stages, installed
geometry/TCP/accuracy validation, and separately authorized motion/contact.
