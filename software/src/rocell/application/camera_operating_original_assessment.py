"""Read saved camera originals, not devices; never publish a stage approval.

The caller supplies a freshly authenticated, in-process configuration owner.
No serialized report can replace that owner or the active original transaction.
Native readbacks are reconstructed here instead of trusting wizard display data.
"""

import json
from time import monotonic_ns
from typing import Any, Callable

from .camera_activation_campaign_contract import (
    ACTION_IDS,
    CONFIGURATION_CAPTURE_ACTION_ID,
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
    camera_activation_execution,
)
from .camera_activation_campaign_evidence import validate_camera_activation_evidence
from .camera_configuration_admission import HAZARD_SCHEMA, SEALED_HAZARD_SCHEMA
from .camera_sealed_capture_evidence import SealedCameraCaptureEvidence
from .camera_sealed_capture_contract import sealed_capture_execution
from .camera_configuration_original_scope import VerifiedCameraConfigurationOriginal
from .camera_operating_evidence_preflight import (
    CameraNativeEvidenceSubject,
    CameraReadbackSubject,
    assess_camera_operating_evidence,
)
from .camera_operating_pixels import (
    logged_pixel_reference,
    verify_operating_capture_pixels,
    verify_sealed_operating_capture_pixels,
    SEALED_SCHEMA as SEALED_PIXEL_SCHEMA,
)
from .camera_operating_stage_requirements import project_operating_requirements
from .commissioning_camera_persistence import M1PhysicalCameraTransaction
from .physical_camera_configuration import compare_physical_camera_readback
from .physical_camera_mode_entry import CameraModeEntry
from .physical_onboarding_attempts import AttemptState
from .wizard_diagnostic_coordinator import require_regular_path
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.vision.camera_profile import MAX_CAMERA_PROFILE_BYTES

SCHEMA = "rocell.camera_original_operating_assessment.v3"
SEALED_SCHEMA = "rocell.camera_original_operating_assessment.v4"
MEANING = (
    "Saved original inputs were authenticated at read time. This diagnostic "
    "assessment is not a stage record, operating approval, current connection "
    "or calibration. Pixel hashes are joined to retained launch completions, not "
    "canonical stage records. Reopening restores none of those permissions."
)
SEALED_MEANING = (
    "Saved original inputs were authenticated at read time. Each pixel check "
    "identifies its original receipt-bound checksum or older launch-only reference. "
    "Legacy references are not promoted to originals. This diagnostic assessment "
    "is not a retained stage assessment, review, connection or calibration."
)


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _native(transaction, attempt_id, action_id):
    """Join independently retained permit, native pair and durable outcome."""
    permit = transaction.read_campaign_permit(attempt_id)
    allowed = (action_id,) if type(action_id) is str else action_id
    _need(permit.registration.action_id in allowed, "OPERATING_ORIGINAL_ACTION")
    outcome = transaction.read_campaign_result(attempt_id)
    _need(
        outcome.state is AttemptState.SEALED_KNOWN
        and not outcome.quarantine_latched
        and outcome.receipt is not None,
        "OPERATING_ORIGINAL_TERMINAL_RESULT",
    )
    artifacts = transaction.read_camera_activation_evidence(attempt_id)
    if permit.registration.action_id == SEALED_CONFIGURATION_CAPTURE_ACTION_ID:
        _need(
            type(artifacts) is SealedCameraCaptureEvidence,
            "OPERATING_ORIGINAL_CHECKSUM_COLLECTION",
        )
        checked = validate_camera_activation_evidence(artifacts.native)
        accounting = sealed_capture_execution(
            permit,
            artifacts,
            expected_deadline_ns=checked.run.to_dict()["parent_deadline_ns"],
        )
        checksum, native = artifacts.checksum, artifacts.native
    else:
        checked = validate_camera_activation_evidence(artifacts)
        accounting = camera_activation_execution(
            permit,
            artifacts,
            expected_deadline_ns=checked.run.to_dict()["parent_deadline_ns"],
        )
        checksum, native = None, artifacts
    _need(accounting.receipt == outcome.receipt, "OPERATING_ORIGINAL_ACCOUNTING")
    return (
        permit,
        CameraNativeEvidenceSubject(
            checked.prepared,
            native,
            native[0].payload_sha256,
            native[1].payload_sha256,
        ),
        checksum,
    )


def _capture_subjects(original, transaction, records, capture_request_keys):
    """Resolve only named original requests; never pick a latest/best capture."""
    captures, selected, checksums = [], [], {}
    for key in capture_request_keys:
        original._setup._check_context()
        matches = [
            r["data"]["attempt_id"]
            for name, r in records.items()
            if name.startswith("request-")
            and r["data"]["permit"]["request"]["request_key"] == key
        ]
        _need(len(matches) == 1, "OPERATING_ORIGINAL_CAPTURE_MISSING_OR_AMBIGUOUS")
        attempt = matches[0]
        permit, native, checksum = _native(
            transaction,
            attempt,
            (
                CONFIGURATION_CAPTURE_ACTION_ID,
                SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
            ),
        )
        facts = transaction.read_campaign_admission_evidence(attempt)
        hazard = facts["hazard_assessment"]
        _need(
            hazard.get("schema")
            == (SEALED_HAZARD_SCHEMA if checksum is not None else HAZARD_SCHEMA)
            and (
                checksum is None
                or hazard.get("action_id") == permit.registration.action_id
            )
            and canonical(hazard["settings"]) == original._configuration.payload
            and hazard["request_key"] == key
            and hazard["source_sha256"] == original._setup._source_sha256
            and hazard["capabilities_sha256"]
            == original._capabilities.capabilities_sha256,
            "OPERATING_ORIGINAL_CAPTURE_SETTINGS",
        )
        readback = compare_physical_camera_readback(
            original._configuration,
            native.evidence,
            expected_preparation=native.preparation,
            expected_capture_evidence_sha256=native.expected_evidence_sha256,
            expected_supervision_sha256=native.expected_supervision_sha256,
            expected_settings_epoch=original._configuration.settings_epoch,
        )
        captures.append(
            CameraReadbackSubject(native, readback.payload, readback.readback_sha256)
        )
        selected.append(
            dict(
                request_key=key, attempt_id=attempt, permit_sha256=permit.permit_sha256
            )
        )
        if checksum is not None:
            checksums[key] = checksum
            selected[-1]["capture_checksum_sha256"] = checksum.sha256
    return captures, selected, checksums


def assess_original_operating_proposal(
    original: VerifiedCameraConfigurationOriginal,
    transaction: M1PhysicalCameraTransaction,
    *,
    proposal_payload: bytes,
    expected_proposal_sha256: str,
    capture_request_keys: tuple[str, ...],
    capture_packets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Authenticate zero to two explicit captures under the existing owner scope.

    Reading zero/one captures is useful diagnosis, never a complete assessment.
    New captures use their authenticated sealed checksum; legacy captures require
    an exact logged reference and are never promoted to original checksums.
    This function does not write to the original journal or create pixel files.
    The original owner checks source, cancellation, leases and its fixed deadline.
    """
    _need(
        type(original) is VerifiedCameraConfigurationOriginal
        and type(transaction) is M1PhysicalCameraTransaction,
        "OPERATING_EXACT_ORIGINAL_OWNER",
    )
    _need(
        type(capture_request_keys) is tuple
        and len(capture_request_keys) <= 2
        and all(type(k) is str and 0 < len(k) <= 96 for k in capture_request_keys)
        and len(set(capture_request_keys)) == len(capture_request_keys),
        "OPERATING_EXPLICIT_CAPTURE_SELECTION",
    )
    snapshot = transaction.snapshot()
    records = original._read_current_records(transaction, original._request, snapshot)
    records_sha = digest(canonical(records))
    workflow = json.loads(original._setup._workflow)
    row = workflow["camera_mode_entry"]["entry"]
    entry = CameraModeEntry(canonical(row["document"]))
    _need(entry.sha256 == row["evidence_sha256"], "OPERATING_ORIGINAL_ENTRY_HASH")
    entry_data = entry.to_dict()
    profile = require_regular_path(
        original._setup._workspace
        / "software/config/camera_profiles/arducam_b0477_imx283_16mm.json",
        directory=False,
    )
    with profile.open("rb") as stream:
        profile_bytes = stream.read(MAX_CAMERA_PROFILE_BYTES + 1)
    original._setup._check_context()
    probe_refs = json.loads(original._probe_references)
    _, probe, _ = _native(transaction, probe_refs["attempt_id"], ACTION_IDS["probe"])
    captures, selected, checksums = _capture_subjects(
        original, transaction, records, capture_request_keys
    )

    pixel_checks = []
    verify_pixels: Callable[..., Any]
    for capture, row in zip(captures, selected):
        original._setup._check_context()
        checksum = checksums.get(row["request_key"])
        if checksum is not None:
            verify_pixels = verify_sealed_operating_capture_pixels
            reference_arguments = dict(checksum=checksum)
        else:
            verify_pixels = verify_operating_capture_pixels
            reference_arguments = dict(
                reference=logged_pixel_reference(
                    (capture_packets or {}).get(row["request_key"]),
                    request_key=row["request_key"],
                    source_sha256=original._setup._source_sha256,
                    session_id=snapshot.header.session_id,
                )
            )
        pixel_checks.append(
            verify_pixels(
                capture.native,
                **reference_arguments,
                request_key=row["request_key"],
                assigned_parent=json.loads(original._plan)["assigned_parent_directory"],
                settings_epoch=original._configuration.settings_epoch,
                cancelled=lambda: (
                    original._setup._cancellation.is_set()
                    or monotonic_ns() >= original._setup._deadline_ns
                ),
            )
        )
        original._setup._check_context()

    preflight = assess_camera_operating_evidence(
        proposal_payload=proposal_payload,
        expected_proposal_sha256=expected_proposal_sha256,
        entry_payload=entry.payload,
        expected_entry_id=entry_data["entry_id"],
        expected_entry_binding=entry_data["binding"],
        purchase_profile_payload=profile_bytes,
        expected_purchase_profile_sha256=digest(profile_bytes),
        capabilities_payload=original._capabilities.payload,
        expected_capabilities_sha256=original._capabilities.capabilities_sha256,
        configuration_payload=original._configuration.payload,
        expected_settings_epoch=original._configuration.settings_epoch,
        probe=probe,
        captures=tuple(captures),
    )
    # Same-call evidence only: no cross-operation cached read or renewed lease.
    ending = original._read_current_records(transaction, original._request, snapshot)
    _need(
        digest(canonical(ending)) == records_sha, "OPERATING_ORIGINAL_RECORDS_CHANGED"
    )
    original._setup._check_context()
    unresolved = [
        item
        for item in preflight.to_dict()["owner_obligations"]
        if item != "ORIGINAL_STORE_AND_CURRENTNESS_NOT_AUTHENTICATED"
        and not (
            item == "PIXEL_FILES_NOT_VERIFIED"
            and len(pixel_checks) == 2
            and all(check["content_verified_at_read"] for check in pixel_checks)
            and (
                not checksums
                or all(check["schema"] == SEALED_PIXEL_SCHEMA for check in pixel_checks)
            )
        )
    ] + ["PROPOSAL_AND_ASSESSMENT_ORIGINAL_STAGE_RETENTION_NOT_IMPLEMENTED"]
    return dict(
        schema=SEALED_SCHEMA if checksums else SCHEMA,
        status="ORIGINAL_INPUTS_CHECKED_APPROVAL_HELD",
        original_inputs_authenticated_at_read=True,
        session_id=snapshot.header.session_id,
        header_sha256=snapshot.header.header_sha256,
        journal_head_sha256=snapshot.head.head_sha256,
        original_records_sha256=records_sha,
        proposal_sha256=expected_proposal_sha256,
        captures=selected,
        pixel_checks=pixel_checks,
        pixel_reference_scope=(
            "PER_CAPTURE_ORIGINAL_OR_LEGACY_REFERENCE"
            if checksums
            else "RETAINED_LAUNCH_COMPLETION_JOINED_TO_M1_NATIVE_CAPTURE"
        ),
        preflight=preflight.to_dict(),
        preflight_sha256=preflight.sha256,
        unresolved_checks=unresolved,
        stage_requirements=project_operating_requirements(
            unresolved, preflight.to_dict()["failed_checks"]
        ),
        currentness_requires_revalidation=True,
        original_stage_record_retained=False,
        approved_operating_policy=False,
        physical_authority=False,
        hardware_qualified=False,
        connected=False,
        meaning=SEALED_MEANING if checksums else MEANING,
    )
