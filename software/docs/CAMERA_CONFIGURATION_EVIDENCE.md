# Camera probe, configuration and readback evidence

This software-only slice turns a retained capability probe into explicit,
immutable electronic-setting intent and compares that intent with a later
retained capture receipt. It does not connect, qualify or calibrate the purchased
camera. The current producer is an incapable process with fixed modeled
descriptors; its driver-unit values are not received-hardware specifications.

## Pure APIs and responsibility boundaries

[`rehearsal_camera_probe_evidence.py`](../src/rocell/application/rehearsal_camera_probe_evidence.py)
retains the complete bounded process, request, native receipt and owned payload:

```python
probe = retain_rehearsal_camera_probe_evidence(
    binding=binding,
    activation_request=request,
    process_result=process_result,
    native_receipt=native_receipt,
    owned_payload=prepared_owned_payload,
    error=None,
)
verified = verify_rehearsal_camera_probe_evidence(probe.payload, binding)
capabilities = verified.capabilities()
```

The exact binding fields are `session_id`, `attempt_id`, `source_sha256`,
`permit_sha256`, `operation_sha256` and `selected_identity_sha256`. The last
four are digests. There is no electronic-settings epoch before a probe exists.
The bytes-backed artifact exposes `payload`, `evidence_sha256`, `to_dict()` and
`view()`; returned documents are detached copies. The pure verifier receives
the independently expected binding, not a binding inferred from its payload.

Probe evidence uses `rocell.rehearsal_camera_probe_evidence.v1`. It retains
stdout and stderr losslessly as canonical base64 with byte counts and hashes,
plus the complete process report, typed request/native receipt, exact owned
payload and caller error. Limits are 32 KiB stdout, 8 KiB stderr and 128 KiB
total evidence. Oversize inputs are rejected, never silently truncated.

`COMPLETE_PROBE_REHEARSAL` requires the exact raw/parsed owned-result join,
successful process cleanup and a matching valid native probe receipt with one
modeled open and shutdown, zero control writes, samples and frames. The probe
request has no requested mode, controls or output directory. A failed or
malformed result remains `INCOMPLETE_PROBE_REHEARSAL` with retained bytes;
`capabilities()` refuses that incomplete artifact. Process cleanup, modeled
native cleanup and received-device cleanup remain separate observations.

These functions do not enumerate devices, invoke a process, read or write a
file, create an output directory, apply controls, or publish commissioning
authority. The parent coordinator owns exact consumed-permit admission and
durable retention before sealing. Reconstruction additionally audits its M1
records; a digest alone is not ledger authentication.

## Capabilities and immutable requested settings

[`camera_configuration.py`](../src/rocell/application/camera_configuration.py)
provides:

```python
configuration = stage_camera_configuration(
    capabilities,
    mode_choice_id,
    (CameraControlSetting("gain", 32, "manual"),),
    expected_probe_evidence_sha256=probe.evidence_sha256,
    expected_source_sha256=source_sha256,
    expected_selected_identity_sha256=selected_identity_sha256,
)
restored = verify_camera_configuration(
    configuration.payload, expected_capabilities=capabilities
)
readback = compare_camera_readback(
    restored, capture_receipt, expected_settings_epoch=restored.settings_epoch
)
```

`CameraCapabilities.from_payload(...)` also requires the original expected
probe digest and binding. It retains all reported modes (up to 128) and the
reported/unavailable partition of the six supported control identifiers:
exposure, gain, white balance, brightness, contrast and saturation. Each
reported control retains minimum, maximum, step, default, capability flags,
current value, current flags and its exact unit label. No unreported descriptor
is filled in from a camera name or product advertisement.

Each mode occurrence has a server-derived opaque choice ID. There is no
automatic first-mode choice. The generic format check permits only supported
even-width YUY2 layouts within the 64 MiB frame contract; unsupported reported
formats remain visible with blockers. The current placemat service further
restricts execution to the fixed 5472 × 3648, 9/1 fps fixture mode. Generic
format eligibility is not executable-mode or physical qualification.

Control requests must use unique known identifiers, exact integer values,
supported auto/manual mode, inclusive range and `(value - minimum) % step == 0`.
Capability bits are 1 for auto and 2 for manual; 3 means both are supported.
A current-flags value of 3 is retained as ambiguous, not an accepted active
readback mode. Missing controls do not imply an instruction to reset them.
An empty requested-control tuple is legal and means no electronic writes.

The configuration is bytes-backed and capped at 96 KiB. Its `settings_epoch`
is the digest of its complete canonical payload, including its original probe,
capability, source, endpoint and selected-identity references. It remains
`STAGED_NOT_APPLIED_REHEARSAL`. A staging or restoration call never applies it.

## Readback and the two settings epochs

Manual readback requires the exact requested value and flag 2. Auto readback
requires flag 1; its observed value may differ from the requested integer and
is displayed separately. Missing, mismatched or ambiguous observations hold
the comparison. Readback also checks the pinned capability ranges, steps and
units. An unchanged/unrequested control is not silently represented as a write.

This comparison consumes native-shaped retained metadata. It does not itself
authenticate the capture source, process, timestamps or pixels; the retained
camera campaign and file-content verifiers supply those joins.

There are deliberately two different electronic-related epochs:

| Value | Exact meaning |
| --- | --- |
| `configuration.settings_epoch` / `electronic_settings_epoch` | Immutable electronic-setting request |
| `effective_settings_epoch` | Canonical hash of synthetic image-settings epoch, electronic epoch and probe evidence digest |

The existing brightness fixture keeps its original `settings_epoch`. A
configured capture plan retains that brightness epoch and adds the full
electronic configuration, probe digest and effective epoch. Capture evidence
and dataset provenance use the effective epoch; readback uses the electronic
epoch. Neither is substituted for the other during restoration.

## Verification scope

The pure module tests are
[`test_camera_configuration.py`](../tests/unit/test_camera_configuration.py)
and
[`test_rehearsal_camera_probe_evidence.py`](../tests/unit/test_rehearsal_camera_probe_evidence.py).
Together they contain 99 checks of strict schemas, exact hashes and source
bindings, malformed raw results, bounds, detached snapshots, reported-mode
eligibility, ranges/steps/capability flags, staging and readback. The measured
nominal fixture is 10,566 bytes of full probe evidence, 1,986 bytes of
capabilities and 1,085 bytes of configuration; these are examples, not new caps.

With the 72 pure legacy/configured reopen checks, the focused lane is 171
passing tests. Those tests use explicitly unexecuted typed observations and
already-audited-record stand-ins. They neither exercise actual M1 publication
nor launch the incapable child. The separate source-frozen integration lane
owns real process/file retention and original-store reopen acceptance.

See [reopen contract](OWNED_CAMERA_REOPEN.md),
[integration sequence](WIZARD_CAMERA_CONFIGURATION_INTEGRATION.md) and
[cached presentation](WIZARD_CAMERA_CONFIGURATION_PRESENTATION.md).
