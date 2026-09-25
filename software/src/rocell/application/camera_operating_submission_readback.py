"""Full-snapshot original stage-prefix and native joins for saved submissions.

Called only from the existing original session reader under its owned batch.
No old SessionSnapshot, device permission, action ticket or camera connection is
restored. A partial package is inspectable but never automatically committed.
"""

from pathlib import Path

from .camera_operating_submission import SOURCE_WORKFLOW_OPERATING_SCHEMA
from .camera_operating_submission_layout import (
    verify_camera_operating_submission_layout,
)
from .camera_operating_submission_native import (
    verify_operating_submission_native_inputs,
)
from .camera_probe_preparation_layout import _original_record
from .camera_probe_preparation_readback import _camera_probe_workflow
from .physical_camera_mode_entry_readback import _verify_camera_mode_entry_prefix
from .physical_onboarding_durability import canonical_sha256, read_bounded_regular_file
from .wizard_diagnostic_coordinator import require_regular_path
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.vision.camera_profile import MAX_CAMERA_PROFILE_BYTES


def read_camera_operating_submission_layout(
    snapshot, mode_packages, probe_packages, packages
):
    try:
        if type(mode_packages) is not dict or len(mode_packages) != 1:
            raise ValueError("EXACT_OPERATING_MODE_PACKAGE")
        if type(packages) is not dict or len(packages) != 1:
            raise ValueError("EXACT_OPERATING_SUBMISSION_PACKAGE")
        mode_id, mode = next(iter(mode_packages.items()))
        evidence_id, package = next(iter(packages.items()))
        if (
            set(mode) != {"entry_id", "record"}
            or mode["record"]["reference"]["evidence_id"] != mode_id
            or mode["record"]["document"]["entry_id"] != mode["entry_id"]
            or set(package) != {"submission_id", "record"}
            or package["record"]["reference"]["evidence_id"] != evidence_id
            or package["record"]["document"]["submission_id"]
            != package["submission_id"]
        ):
            raise ValueError("EXACT_OPERATING_PACKAGE_IDENTITY")
        return verify_camera_operating_submission_layout(
            snapshot, mode["record"], probe_packages, package["record"]
        )
    except (TypeError, KeyError, AttributeError, RecursionError) as error:
        raise ValueError("CAMERA_OPERATING_ORIGINAL_PACKAGE_INVALID") from error


def _creation_workflow(original, snapshot, layout):
    """Reproduce a historical digest, not a smaller snapshot for verification.

    The complete original prefix and exact one-package suffix have ALREADY been
    validated on the actual full snapshot. Only its two envelope digests changed
    since creation. Derive those from the authenticated original event prefix and
    inventory excluding the one independently identified new package. This value
    is used solely for comparison to the historical admission summary, never as
    input to a predecessor reader, admission guard or a device operation.
    """
    binding = layout.submission.to_dict()["binding"]
    return {
        **original,
        "session_head_sha256": binding["journal_head_sha256"],
        # This envelope is owned by the journal's newline-terminated canonical
        # format, not the native IPC JSON format used for the workflow itself.
        "evidence_inventory_sha256": canonical_sha256(
            [
                reference.to_dict()
                for reference in snapshot.evidence
                if reference.evidence_id != layout.reference.evidence_id
            ]
        ),
    }


def verify_camera_operating_submission_workflow(
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
    probe_packages,
    packages,
    *,
    transaction,
    original_campaigns=(),
    original_presence_campaigns=(),
):
    layout = read_camera_operating_submission_layout(
        snapshot, mode_packages, probe_packages, packages
    )
    original = _verify_camera_mode_entry_prefix(
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
    original = _camera_probe_workflow(original, layout.probe, bound)
    # Every stage original has been independently verified on the full snapshot
    # above. The native reader must additionally authenticate all campaign bytes.
    probe = layout.probe
    binding = dict(
        source_sha256=bound["source_sha256"],
        cell_id=snapshot.header.cell_id,
        session_id=snapshot.header.session_id,
        header_sha256=expected_header_sha256,
        entry_sha256=probe.mode_entry.entry.sha256,
        probe_preparation_sha256=probe.preparation.sha256,
        probe_review_sha256=probe.review.sha256,
        journal_head_sha256=layout.submission.to_dict()["binding"][
            "journal_head_sha256"
        ],
        original_records_sha256=digest(
            canonical(transaction._audit_records(include_family=True))
        ),
    )
    profile = require_regular_path(
        Path(bound["workspace"])
        / "software/config/camera_profiles/arducam_b0477_imx283_16mm.json",
        directory=False,
    )
    raw_profile = read_bounded_regular_file(
        profile,
        maximum_bytes=MAX_CAMERA_PROFILE_BYTES,
        label="operating purchase profile",
    )
    native = verify_operating_submission_native_inputs(
        transaction,
        submission=layout.submission,
        expected_binding=binding,
        entry=probe.mode_entry.entry,
        preparation=probe.preparation,
        review=probe.review,
        creation_workflow_sha256=digest(
            canonical(_creation_workflow(original, snapshot, layout))
        ),
        purchase_profile_payload=raw_profile,
    )
    return {
        **original,
        "schema": SOURCE_WORKFLOW_OPERATING_SCHEMA,
        "camera_operating_submission": dict(
            state=layout.state,
            submission=_original_record(layout.submission, layout.reference),
            events=[event.to_dict() for event in layout.events],
            native_inputs=native,
            original_stage_authenticated=True,
            currentness_requires_revalidation=True,
            stage_passed=False,
            approved_operating_policy=False,
            connected=False,
            physical_authority=False,
            hardware_qualified=False,
            device_io_performed=False,
            meaning="Original saved submission and native inputs only. Pixel checks describe their historical read. Separate continuity, review, freshness and installed calibration remain required. No connection or permission was restored.",
        ),
    }
