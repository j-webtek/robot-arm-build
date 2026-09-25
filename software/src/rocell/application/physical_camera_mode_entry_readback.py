"""Original stage-5 entry join over the complete unchanged identity history.

Only the Session owner supplies original bytes and the full audited snapshot.
The structural suffix is checked first to establish its closed allowance; the
whole v14 predecessor is then authenticated on that SAME snapshot. Finally the
entry is compared to dependencies derived from the authenticated predecessor.
No cached status, imported export or constructed layout grants device access.
"""

from typing import Any

from .physical_camera_mode_entry import (
    CameraModeEntry,
    HASH_FIELDS,
    verify_camera_mode_entry,
    SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA,
)
from .physical_camera_mode_entry_layout import verify_camera_mode_entry_layout
from .physical_camera_usb_absence import _record
from .physical_camera_usb_complete_constants import SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
from .physical_usb_complete_series import (
    CompleteUsbSeries,
    CompleteUsbAssessment,
    CompleteUsbReview,
    REVIEW_ELIGIBLE,
)
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .usb_identity_stage_policy import UsbIdentityAdmissionIdentity
from rocell.providers.windows.usb_identity_protocol import canonical, digest


class CameraModeOriginalError(ValueError):
    pass


def _need(ok):
    if not ok:
        raise CameraModeOriginalError("CAMERA_MODE_ORIGINAL_INVALID")


def camera_mode_entry_binding(workflow, *, entry_launch_id):
    """Pure dependency extraction AFTER owner authentication, not authentication.

    The selected identity is the historical reboot selection accepted by the
    final review. Actual probe admission still needs fresh current enrollment
    and continuity; this function never rewrites a stored launch or identity.
    """
    try:
        _need(
            type(workflow) is dict
            and workflow["schema"] == SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
        )
        complete = workflow["usb_qualification_complete"]
        _need(complete["state"] == "REVIEWED_PASS" and len(complete["events"]) == 3)
        subjects, references = {}, {}
        for role, cls in (
            ("series", CompleteUsbSeries),
            ("assessment", CompleteUsbAssessment),
            ("review", CompleteUsbReview),
        ):
            payload, reference = _record(complete[role])
            subjects[role], references[role] = cls(payload), reference
            _need(reference.stage is STAGE_ORDER[3])
        series, assessment, review = (
            subjects[role].to_dict() for role in ("series", "assessment", "review")
        )
        _need(
            review["verdict"] == REVIEW_ELIGIBLE
            and review["series_sha256"] == subjects["series"].sha256
            and review["assessment_sha256"] == subjects["assessment"].sha256
            and assessment["series_sha256"] == subjects["series"].sha256
            and review["binding"] == assessment["binding"] == series["binding"]
        )
        base, original = series["binding"], workflow["binding"]
        _need(
            all(
                base[key] == original[key]
                for key in ("cell_id", "session_id", "source_sha256")
            )
            and base["origin_launch_id"] == original["launch_id"]
            and base["header_sha256"] == workflow["session_header_sha256"]
            and base["prerequisites_sha256"]
            == workflow["prerequisites"]["evidence_sha256"]
        )
        identity_raw, identity_ref = _record(
            workflow["usb_qualification_reboot"]["identity"]
        )
        identity = UsbIdentityAdmissionIdentity(identity_raw).to_dict()
        _need(identity_ref.stage is STAGE_ORDER[3])
        # The legacy USB _record helper is deliberately stage-4-only. Do not
        # weaken it to read this separately owned original stage-1 dependency.
        epochs = workflow["configuration_epochs"]
        _need(
            type(epochs) is dict
            and set(epochs)
            == {
                "document",
                "evidence_sha256",
                "reference",
                "retention",
            }
        )
        epochs_ref = _parse_evidence_reference(epochs["reference"])
        epoch_bytes = canonical(epochs["document"])
        _need(
            epochs_ref.stage is STAGE_ORDER[0]
            and epochs["retention"] == "M1_FULL_BYTES_READ_BACK"
            and epochs_ref.payload_sha256
            == epochs["evidence_sha256"]
            == digest(epoch_bytes)
            and epochs_ref.payload_bytes == len(epoch_bytes)
        )
        result = {key: base[key] for key in HASH_FIELDS if key in base}
        result.update(
            cell_id=base["cell_id"],
            session_id=base["session_id"],
            origin_launch_id=base["origin_launch_id"],
            entry_launch_id=entry_launch_id,
            configuration_epochs_sha256=epochs_ref.payload_sha256,
            selected_identity_sha256=identity["selection_sha256"],
            complete_series_sha256=subjects["series"].sha256,
            complete_assessment_sha256=subjects["assessment"].sha256,
            complete_review_sha256=subjects["review"].sha256,
            complete_review_event_sha256=complete["events"][-1]["event_sha256"],
        )
        return result
    except CameraModeOriginalError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ) as exc:
        raise CameraModeOriginalError("CAMERA_MODE_ORIGINAL_INVALID") from exc


def read_camera_mode_entry_layout(snapshot, packages):
    """Validate the already-read original package shape, not its predecessor."""
    try:
        _need(type(packages) is dict and len(packages) == 1)
        evidence_id, package = next(iter(packages.items()))
        _need(type(package) is dict and set(package) == {"entry_id", "record"})
        record = package["record"]
        entry = CameraModeEntry(canonical(record["document"]))
        _need(record["reference"]["evidence_id"] == evidence_id)
        return verify_camera_mode_entry_layout(
            snapshot,
            record,
            expected_entry_id=package["entry_id"],
            expected_binding=entry.to_dict()["binding"],
        )
    except CameraModeOriginalError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ) as exc:
        raise CameraModeOriginalError("CAMERA_MODE_ORIGINAL_INVALID") from exc


def verify_camera_mode_entry_workflow(
    bound,
    snapshot,
    expected_header_sha256,
    roles,
    intake_packages,
    qualification_packages,
    qualification_originals,
    static_packages,
    received_packages,
    received_originals,
    identity_packages,
    usb_packages,
    trial_packages,
    phase_packages,
    absence_packages,
    reconnect_packages,
    reboot_packages,
    complete_packages,
    mode_packages,
    *,
    original_campaigns=(),
    original_presence_campaigns=(),
) -> dict[str, Any]:
    layout = read_camera_mode_entry_layout(snapshot, mode_packages)
    return _verify_camera_mode_entry_prefix(
        bound,
        snapshot,
        expected_header_sha256,
        roles,
        intake_packages,
        qualification_packages,
        qualification_originals,
        static_packages,
        received_packages,
        received_originals,
        identity_packages,
        usb_packages,
        trial_packages,
        phase_packages,
        absence_packages,
        reconnect_packages,
        reboot_packages,
        complete_packages,
        layout,
        original_campaigns=original_campaigns,
        original_presence_campaigns=original_presence_campaigns,
    )


def _verify_camera_mode_entry_prefix(
    bound,
    snapshot,
    expected_header_sha256,
    roles,
    intake_packages,
    qualification_packages,
    qualification_originals,
    static_packages,
    received_packages,
    received_originals,
    identity_packages,
    usb_packages,
    trial_packages,
    phase_packages,
    absence_packages,
    reconnect_packages,
    reboot_packages,
    complete_packages,
    layout,
    *,
    original_campaigns=(),
    original_presence_campaigns=(),
) -> dict[str, Any]:
    """Private complete-prefix join; the typed allowance is revalidated below."""
    from .physical_camera_usb_complete_readback import _verify_usb_complete_prefix
    from .camera_probe_preparation_layout import CameraProbePreparationLayout
    from .camera_operating_submission_layout import CameraOperatingSubmissionLayout

    original = _verify_usb_complete_prefix(
        bound,
        snapshot,
        expected_header_sha256,
        roles,
        intake_packages,
        qualification_packages,
        qualification_originals,
        static_packages,
        received_packages,
        received_originals,
        identity_packages,
        usb_packages,
        trial_packages,
        phase_packages,
        absence_packages,
        reconnect_packages,
        reboot_packages,
        complete_packages,
        original_campaigns=original_campaigns,
        original_presence_campaigns=original_presence_campaigns,
        camera_mode_entry=layout,
    )
    if type(layout) is CameraOperatingSubmissionLayout:
        layout = layout.probe
    if type(layout) is CameraProbePreparationLayout:
        layout = layout.mode_entry
    document = layout.entry.to_dict()
    binding = camera_mode_entry_binding(
        original,
        entry_launch_id=document["binding"]["entry_launch_id"],
    )
    verify_camera_mode_entry(
        layout.entry.payload,
        expected_entry_id=document["entry_id"],
        expected_binding=binding,
    )
    return {
        **original,
        "schema": SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA,
        "camera_mode_entry": dict(
            entry_id=document["entry_id"],
            state=layout.state,
            events=[event.to_dict() for event in layout.events],
            entry=dict(
                document=document,
                evidence_sha256=layout.entry.sha256,
                reference=layout.reference.to_dict(),
                retention="M1_FULL_BYTES_READ_BACK",
            ),
            meaning="Original stage-5 entry only; no camera probe/capture, runtime, arm or motion permission.",
        ),
    }
