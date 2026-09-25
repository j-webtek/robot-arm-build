"""Original v14 camera-identity review over the full unchanged v13 history.

The Session owner supplies original bytes, the real V2 snapshot and the audited
campaign family under its existing leases. Diagnostic caches are not originals.
This module grants no camera, arm, motion or contact permission.
"""

from typing import Any

from rocell.application.physical_camera_usb_absence import _record
from rocell.application.physical_camera_usb_reboot_constants import (
    SOURCE_WORKFLOW_USB_REBOOT_SCHEMA,
)
from rocell.application.physical_usb_reboot_phase import (
    UsbRebootOperatorEvent,
    UsbRebootQualificationPhase,
)
from rocell.application.physical_camera_prerequisites import (
    verify_physical_camera_prerequisites,
)
from rocell.application.physical_received_camera_submission import (
    ReceivedCameraSubmission,
    ReceivedCameraSubmissionAssessment,
    ReceivedCameraSubmissionReview,
)
from rocell.providers.windows.usb_identity_protocol import canonical

from .physical_camera_usb_complete_constants import SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
from .physical_camera_usb_complete_inputs import original_usb_complete_inputs
from .physical_usb_complete_series import (
    verify_complete_usb_subject_chain,
    REVIEW_ELIGIBLE,
)


def verify_usb_complete_workflow(
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
    *,
    original_campaigns=(),
    original_presence_campaigns=(),
) -> dict[str, Any]:
    """Closed public v14 entry point, without later-stage allowance."""
    return _verify_usb_complete_prefix(
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
    )


def _verify_usb_complete_prefix(
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
    *,
    original_campaigns=(),
    original_presence_campaigns=(),
    camera_mode_entry=None,
) -> dict[str, Any]:
    """Authenticate the suffix's meaning without substituting an old snapshot."""
    from rocell.application.physical_camera_session import (
        _require,
        PhysicalCameraSessionError,
    )

    from rocell.application.physical_camera_usb_reboot_readback import (
        _verify_usb_reboot_prefix,
    )
    from .physical_camera_usb_complete_layout import _verify_complete_usb_prefix_layout

    error = "CAMERA_SESSION_USB_COMPLETE_INVALID"
    try:
        _require(
            type(reboot_packages) is dict and type(complete_packages) is dict, error
        )
        final_records = [
            package["record"]
            for package in reboot_packages.values()
            if type(package) is dict and package.get("kind") == "phase_record"
        ]
        _require(len(final_records) == 1, error)
        raw_phase, phase_reference = _record(final_records[0])
        phase = UsbRebootQualificationPhase(raw_phase)
        pd = phase.to_dict()
        operator_records = [
            package["record"]
            for package in reboot_packages.values()
            if type(package) is dict and package.get("kind") == "operator_event"
        ]
        _require(len(operator_records) == 1, error)
        raw_operator, _ = _record(operator_records[0])
        operator = UsbRebootOperatorEvent(raw_operator).to_dict()
        _require(
            operator["phase_id"] == pd["context"]["operation_id"]
            and operator["plan_sha256"] == pd["plan_sha256"],
            error,
        )
        layout = _verify_complete_usb_prefix_layout(
            snapshot,
            complete_packages,
            expected_header_sha256=expected_header_sha256,
            # The binding belongs to the operator/plan subject; the phase
            # deliberately contains only hashes and observation context.
            expected_binding=operator["binding"],
            predecessor_phase_id=pd["context"]["operation_id"],
            predecessor_reference=phase_reference,
            predecessor_finished_at_utc_ns=pd["context"]["finished_at_utc_ns"],
            camera_mode_entry=camera_mode_entry,
        )
        later_ids = frozenset(record.reference.evidence_id for record in layout.records)
        _require(later_ids == frozenset(complete_packages), error)
        # The v13 private path checks ALL earlier original roles and campaigns
        # on this same full snapshot. Only these validated later IDs may be
        # excluded when reconstructing a historical query inventory.
        original = _verify_usb_reboot_prefix(
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
            original_campaigns=original_campaigns,
            original_presence_campaigns=original_presence_campaigns,
            prefix_event_count=layout.prefix_event_count,
            usb_complete_evidence_ids=later_ids,
            camera_mode_entry=camera_mode_entry,
        )
        _require(
            original["schema"] == SOURCE_WORKFLOW_USB_REBOOT_SCHEMA
            and original["usb_qualification_reboot"]["state"] == "RETAINED_BLOCKED"
            and original["usb_qualification_reboot"]["phase_record"]
            == final_records[0],
            error,
        )
        prerequisite_record = roles["prerequisites"]
        prerequisites = verify_physical_camera_prerequisites(
            canonical(prerequisite_record["document"]),
            expected_source_sha256=bound["source_sha256"],
            expected_session_id=bound["session_id"],
            expected_launch_session_id=bound["launch_id"],
            expected_evidence_sha256=prerequisite_record["evidence_sha256"],
        )
        cycle = original["received_camera_cycles"][-1]
        received = {
            role: cls(canonical(cycle[role]["document"]), prerequisites)
            for role, cls in (
                ("submission", ReceivedCameraSubmission),
                ("assessment", ReceivedCameraSubmissionAssessment),
                ("review", ReceivedCameraSubmissionReview),
            )
        }
        inputs = original_usb_complete_inputs(original, received=received)
        checked = verify_complete_usb_subject_chain(
            {record.role: record.payload for record in layout.records},
            expected_sha256s={
                record.role: record.reference.payload_sha256
                for record in layout.records
            },
            expected_series_id=layout.series_id,
            **inputs,
        )
        by_role = {subject.role: subject for subject in checked}
        count = len(layout.events)
        if count == 3:
            accepted = by_role["review"].to_dict()["verdict"] == REVIEW_ELIGIBLE
            state = "REVIEWED_PASS" if accepted else "REVIEWED_BLOCKED"
            _require(
                snapshot.stages[3].state.value == ("PASS" if accepted else "BLOCKED"),
                error,
            )
        elif count == 2 and len(checked) == 2:
            state = "REVIEW_PENDING"
        elif count == 1 and not checked:
            state = "ASSESSMENT_REQUESTED"
        else:
            state = "INCOMPLETE"
        # Recreate the ordinary original-record wrapper from independently
        # verified bytes/reference, rather than copying a caller's status claim.
        records = {
            record.role: dict(
                document=by_role[record.role].to_dict(),
                evidence_sha256=record.reference.payload_sha256,
                reference=record.reference.to_dict(),
                retention="M1_FULL_BYTES_READ_BACK",
            )
            for record in layout.records
        }
        return {
            **original,
            "schema": SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA,
            "usb_qualification_complete": dict(
                series_id=layout.series_id,
                state=state,
                events=[event.to_dict() for event in layout.events],
                **{
                    role: records.get(role)
                    for role in ("series", "assessment", "review")
                },
                meaning="Original camera-identity review only; no capture, arm, motion or contact permission.",
            ),
        }
    except PhysicalCameraSessionError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        IndexError,
        RecursionError,
    ) as exc:
        raise PhysicalCameraSessionError(error) from exc
