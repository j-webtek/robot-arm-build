# USB/boot qualification-series codec

Implemented in `application/physical_camera_usb_qualification.py`. This is an
inert original-evidence comparison layer, not a device dispatcher or a new
source-stage acceptance rule. Historical v7 identity metadata keeps its original
BLOCKED meaning. The complete camera/arm onboarding goal is not complete.

## Available result and explicit remaining gap

This version always assesses **BLOCKED**. It can retain and compare baseline,
endpoint absence, reconnect and post-boot observations, including failed owned
executions. The existing native camera inventory covers camera endpoints only;
even a complete empty roster does not establish physical USB-device removal.
`PHYSICAL_USB_ABSENCE_REQUIRED` therefore always remains missing. Its existing
packet also lacks a request nonce/acquisition bracket, so an absence phase
reports `ENDPOINT_INVENTORY_FRESHNESS_REQUIRED` as missing. Timeout, error or
incomplete cleanup never establishes endpoint absence.

No caller Boolean can bypass either gap. Supporting complete physical USB-node
absence requires a real bounded producer and an explicitly versioned codec and
policy change. This module contains no fabricated physical-absence provider or
speculative PASS branch. A MODELED series additionally fails physical-origin
requirements. Neither exact review nor file agreement upgrades those results.

## Immutable subjects and original roles

All five subjects expose immutable `.payload`, `.sha256` and detached
`.to_dict()`. Payloads are bounded canonical ASCII JSON with duplicate,
unknown-field and malformed-type rejection.

| Subject | Maximum | Meaning |
| --- | ---: | --- |
| `UsbQualificationPlan` | 16 KiB | Original context, received-subject references, recorded label and declared cable/port labels |
| `UsbQualificationPhase` | 16 KiB | Ordered phase, original role manifest and reconstructed observations/checks |
| `UsbQualificationSeries` | 8 KiB | Ordered prefix of zero to four original phase references |
| `UsbQualificationAssessment` | 32 KiB | Reconstructed comparison, always BLOCKED |
| `UsbQualificationReview` | 8 KiB | Separate exact-subject ACKNOWLEDGE_EXACT or REJECT, always BLOCKED |

The phase order is exactly BASELINE, RECONNECT_ABSENCE, AFTER_RECONNECT,
AFTER_REBOOT. Each phase binds its predecessor SHA, original plan, collector,
application launch, operation label and UTC bracket. Reusing an attempt,
permit hash or operation hash within observation phases is rejected. The M1
owner independently enforces actual attempt/nonces and original retention;
this pure codec does not replace that ledger.

An observation phase retains three **separate** original role payloads:

- `native_enrollment`: the full verified enrollment snapshot, at most 768 KiB.
- `owned_usb_run`: actual `OwnedUsbIdentityRunEvidence`, at most 128 KiB.
- `host_boot`: actual `HostBootObservation`, at most 32 KiB.

An absence phase retains `endpoint_inventory` (at most 256 KiB) and `host_boot`.
Each manifest row is exactly `{role, sha256, payload_bytes, reference}`. The
reference is the existing six-field `EvidenceReference`; new roles belong to
CAMERA_IDENTITY. The plan references the three original CAMERA_RECEIPT subjects
without copying them. A complete trial is 19 new role/manifest documents before
any separately retained policy/runtime subjects; storage admission remains the
owner's responsibility.

The caller must read and authenticate references in the original store before
supplying bytes. A syntactically valid reference is not proof that a file was
stored. There are no filesystem, registry, process, device or clock reads in
this module.

## Callable joins

`build_usb_qualification_plan(...)` takes:

- `binding`: trial_id, source_sha256, cell_id, session_id, header_sha256,
  origin_launch_id, prerequisites_sha256, identity_entry_sha256,
  stage_policy_sha256, stage_catalog_sha256, stage_order_sha256.
- `mode`: PHYSICAL or MODELED; operator_id, launch_session_id,
  created_at_utc_ns, cable_label and port_label.
- The exact typed `received_submission`, `received_assessment`,
  `received_review`, and their ordered `received_references`.

The actual received assessment/review are reconstructed. Both must say PASS;
their recorded inspection supplies manufacturer, product ID and serial. No
nominal product serial, instance suffix or notebook narrative is substituted.
That previous receipt PASS does not qualify USB identity or camera installation.

`build_usb_qualification_phase(plan, *, phase, predecessor, context, sources,
references)` reconstructs a phase. `sources` maps the exact role names to original
bytes; `references` maps the same names to original references. `context` is
exactly launch_session_id, operation_id, operator_id, started_at_utc_ns and
finished_at_utc_ns. The host-boot request must match the phase/source/session/
trial/launch/operation. USB preparation must match original context and the
actual reviewed native selection, endpoint, instance and native identity.

`build_usb_qualification_series(plan, *, phases, references)` binds an exact
ordered prefix. `assess_usb_qualification_series(plan, series, *, phases,
phase_sources, received)` re-verifies every phase from originals and re-verifies
the plan against `received={submission, assessment, review}`. It does not trust
a frozen object's previously derived labels or Boolean checks.

`review_usb_qualification_series(plan, series, assessment, *, phases,
phase_sources, received, reviewer_id, review_launch_id, reviewed_at_utc_ns,
decision)` reconstructs the assessment again. The reviewer label is casefold-
distinct from plan and phase collector labels. Labels do not authenticate
independent people. Separate `verify_usb_qualification_plan`,
`verify_usb_qualification_phase`, `verify_usb_qualification_assessment` and
`verify_usb_qualification_review` additionally require `expected_sha256` and
compare exact reconstructed payloads.

Constructors validate closed syntax; the verify functions and assessment join
validate the original cross-subject semantics. Consumers must use those joins,
not treat a deserialized manifest alone as current qualification.

## Values, provenance and presentation

`assessment.safe_summary()` returns `rocell.usb_qualification_summary.v1`,
bounded to 24 KiB. It retains original binding and subject hashes, mode,
BLOCKED verdict, exact missing requirement IDs, phase observations/provenance,
recorded receipt label, declared cable/port labels and comparison rows.
Passed/failed full check rows remain in the assessment; the compact view avoids
duplicating them and reports missing requirements per phase and overall.

Values live once in each phase. Comparison rows are exactly field,
before_phase, after_phase, status (MATCHED, CHANGED or NOT_OBSERVED). They compare
BASELINE with AFTER_RECONNECT or AFTER_REBOOT. Fields include descriptor serial,
VID/PID, endpoint, interface/physical USB instance, host controller/topology,
native driver provider/service/version/INF, generic serial/VID/PID/service,
container ID, machine UUID and reported boot time. Boot relation is assessed
separately; a changed app launch is never a reboot.

Each display value is `{status, value, sha256}`. Short values are preserved
literally. Larger values or values omitted under the total presentation budget
use VALUE_IN_ORIGINAL with an exact canonical-value hash and null display value;
this is distinct from NOT_OBSERVED. Originals remain unchanged in their role
files. No prefixes are compared as if they were complete values.

The USB V2 **operating** SuperSpeed flag is required; capability bits alone do
not suffice. Raw EX.Speed remains unchanged: Windows can report HighSpeed in
EX alongside operating SuperSpeed in V2. No exact Mbps value is inferred.
See Microsoft's [USB_NODE_CONNECTION_INFORMATION_EX documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbioctl/ns-usbioctl-_usb_node_connection_information_ex)
and [EX_V2 documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbioctl/ns-usbioctl-_usb_node_connection_information_ex_v2).

Process cleanup, reported USB handle cleanup, runtime provenance and boot
provenance stay separate. Host UUID and LastBootUpTime are provider reports, not
cryptographic attestation. These subjects deliberately do not claim that USB
descriptor queries perform no device I/O. All physical/hardware/capture/native
release/stage-pass and authenticated-identity authority flags remain false.
Those flags mean that the report grants no new authority; they do not erase an
already admitted USB query or its retained READY/RELEASE delivery. For execution
status, exact error code, no-attempt distinction and bounded effects, display the
owned-run safe summary alongside this series view rather than infer those facts
from the qualification verdict.

## Verification

`tests/unit/test_physical_camera_usb_qualification.py` uses actual received,
enrollment, preparation, owned evidence, USB wire and boot codecs. Pure fixtures
explicitly model receipt/metadata/boot facts and original-store references.
The two owned-process tests use only the separately linked incapable USB child
through the real one-process Job/pipe/READY/RELEASE path. The four-phase case
also demonstrates a new app launch with the same boot, then a separately modeled
later boot report without changing the original USB process bytes. No physical
USB or actual CIM observation is performed.

Final verification: `python -m pytest
software/tests/unit/test_physical_camera_usb_qualification.py -q
--disable-warnings` — 35 passed in 122.40 seconds. Black check passed for the
module/test; mypy passed for the module. Production module SHA-256:
`e4fb88ca77c7e6defb40411b85d241bc46571731336d22e9fe91cacce9cd8d13`.
