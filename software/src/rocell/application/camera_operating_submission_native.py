"""Read exact original native subjects for an unreviewed operating submission.

This is one part of the original reader, not a public import/approval API. Its
caller authenticates the full stage prefix and independently supplies the entry,
preparation, review, creation binding and purchase file. This function reads only
the active original transaction; it never restores an acquisition owner or opens
pixels/devices. Historical pixel verdicts stay historical, even on fresh launch.
"""

from pathlib import Path

from .camera_activation_campaign_contract import (
    ACTION_IDS,
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
)
from .camera_configuration_admission import SEALED_HAZARD_SCHEMA, SEALED_EPOCH_SCHEMA
from .camera_configuration_original_scope import _selected_probe_records_sha256
from .camera_operating_evidence_preflight import (
    CameraReadbackSubject,
    assess_camera_operating_evidence,
)
from .camera_operating_original_assessment import _native
from .camera_operating_submission import CameraOperatingSubmission
from .camera_probe_admission import HAZARD_SCHEMA as PROBE_HAZARD_SCHEMA
from .camera_probe_preparation import (
    CameraProbePreparation,
    CameraProbePreparationReview,
)
from .commissioning_camera_persistence import M1PhysicalCameraTransaction
from .physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
    verify_camera_activation_campaign_evidence,
)
from .physical_camera_configuration import (
    StagedPhysicalCameraConfiguration,
    compare_physical_camera_readback,
    derive_physical_camera_capabilities,
    verify_physical_camera_configuration,
)
from .physical_camera_mode_entry import CameraModeEntry
from .physical_camera_selection import PhysicalCameraSelection
from rocell.providers.windows.camera_worker_client import CameraCampaignBudget
from rocell.providers.windows.native_camera_activation_expectation import (
    CameraActivationExpectation,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("CAMERA_OPERATING_ORIGINAL_" + code)


def _setup_context(context, *, binding, plan, workflow_sha256):
    """Check the old original-scope summary without constructing its owner."""
    _need(type(context) is dict, "SETUP_CONTEXT")
    expected = dict(
        schema="rocell.camera_probe_original_scope_summary.v1",
        source_sha256=binding["source_sha256"],
        launch_session_id=plan["launch_session_id"],
        session_id=binding["session_id"],
        cell_id=binding["cell_id"],
        header_sha256=binding["header_sha256"],
        journal_head_sha256=binding["journal_head_sha256"],
        original_workflow_sha256=workflow_sha256,
        preparation_sha256=binding["probe_preparation_sha256"],
        review_sha256=binding["probe_review_sha256"],
        authenticated_at_read=True,
        currentness_requires_revalidation=True,
        physical_authority=False,
        hardware_qualified=False,
        connected=False,
        meaning="Original setup was authenticated under CAMERA ownership. This cached summary cannot authorize device access or restore the in-process guard.",
    )
    # Canonical bytes distinguish bools from integers and close the field roster.
    _need(canonical(context) == canonical(expected), "SETUP_CONTEXT")


def _resolve_request(records, request_key):
    attempts = [
        row["data"]["attempt_id"]
        for name, row in records.items()
        if name.startswith("request-")
        and row["data"]["permit"]["request"]["request_key"] == request_key
    ]
    _need(len(attempts) == 1, "EXACT_CAPTURE_REQUEST")
    return attempts[0]


def _historical_pixels(pixel, checksum):
    """Authenticate its old reference; do not reinterpret a past file read."""
    data = checksum.to_dict()
    _need(data["status"] == "CAPTURE_BYTES_HASHED", "SEALED_PIXEL_REFERENCE")
    _need(pixel["capture_checksum_sha256"] == checksum.sha256, "PIXEL_REFERENCE_HASH")
    if pixel["status"] != "REFERENCE_MISMATCH":
        _need(pixel["native_frame_sha256"] == data["frame"]["sha256"], "PIXEL_HASH")
    if pixel["content_verified_at_read"]:
        _need(pixel["verified_bytes"] == data["verified_pixel_bytes"], "PIXEL_LENGTH")


def verify_operating_submission_native_inputs(
    transaction: M1PhysicalCameraTransaction,
    *,
    submission: CameraOperatingSubmission,
    expected_binding: dict[str, str],
    entry: CameraModeEntry,
    preparation: CameraProbePreparation,
    review: CameraProbePreparationReview,
    creation_workflow_sha256: str,
    purchase_profile_payload: bytes,
) -> dict:
    """Rebuild the saved preflight from three explicit original attempts.

    The original session owner must authenticate the full stage history before
    calling. Supplying matching JSON, even to this function, does not authenticate
    that history. The returned data deliberately makes no stage/provenance claim.
    The initial submission contract has a closed campaign inventory; later
    milestones must explicitly version any historical-extension allowance.
    """
    _need(type(transaction) is M1PhysicalCameraTransaction, "TRANSACTION")
    _need(type(submission) is CameraOperatingSubmission, "SUBMISSION")
    _need(type(entry) is CameraModeEntry, "ENTRY")
    _need(type(preparation) is CameraProbePreparation, "PREPARATION")
    _need(type(review) is CameraProbePreparationReview, "REVIEW")
    transaction._check_scope()
    data = submission.to_dict()
    binding = data["binding"]
    _need(canonical(binding) == canonical(expected_binding), "BINDING")
    _need(
        entry.sha256 == binding["entry_sha256"]
        and preparation.sha256 == binding["probe_preparation_sha256"]
        and review.sha256 == binding["probe_review_sha256"],
        "STAGE_SUBJECTS",
    )
    prep = preparation.to_dict()
    _need(
        prep["entry_sha256"] == entry.sha256
        and review.to_dict()["preparation_sha256"] == preparation.sha256,
        "PREPARATION_REVIEW",
    )
    snapshot = transaction.snapshot()
    _need(
        snapshot.header.cell_id == binding["cell_id"]
        and snapshot.header.session_id == binding["session_id"]
        and snapshot.header.header_sha256 == binding["header_sha256"],
        "SESSION",
    )
    records = transaction._audit_records(include_family=True)
    _need(digest(canonical(records)) == binding["original_records_sha256"], "INVENTORY")
    plan = prep["plan"]
    probe_campaign = PhysicalCameraActivationCampaign.from_plan(plan)
    policy, report = data["proposal"], data["assessment"]
    probe_permit, probe, _ = _native(
        transaction, policy["probe_binding"]["attempt_id"], ACTION_IDS["probe"]
    )
    verify_camera_activation_campaign_evidence(
        probe.evidence, campaign=probe_campaign, expected_permit=probe_permit
    )
    probe_facts = transaction.read_campaign_admission_evidence(probe_permit.attempt_id)
    probe_hazard = probe_facts["hazard_assessment"]
    _need(probe_hazard.get("schema") == PROBE_HAZARD_SCHEMA, "PROBE_FACTS")
    _need(
        probe_permit.admission.journal_head_sha256 == binding["journal_head_sha256"]
        and probe_hazard["plan_sha256"] == digest(canonical(plan))
        and probe_hazard["request_key"] == probe_permit.request.request_key,
        "PROBE_ADMISSION",
    )
    _setup_context(
        probe_hazard["original_context"],
        binding=binding,
        plan=plan,
        workflow_sha256=creation_workflow_sha256,
    )
    capabilities = derive_physical_camera_capabilities(
        probe.evidence,
        expected_preparation=probe.preparation,
        expected_evidence_sha256=probe.expected_evidence_sha256,
        expected_supervision_sha256=probe.expected_supervision_sha256,
        expected_source_sha256=binding["source_sha256"],
    )
    probe_refs = dict(
        attempt_id=probe_permit.attempt_id,
        request_key=probe_permit.request.request_key,
        permit_sha256=probe_permit.permit_sha256,
        operation_sha256=probe_permit.registration.operation_sha256,
        evidence_sha256=probe.expected_evidence_sha256,
        supervision_sha256=probe.expected_supervision_sha256,
        preparation_sha256=probe.preparation.preparation_sha256,
    )
    probe_records_sha = _selected_probe_records_sha256(records, probe_permit.attempt_id)
    captures = []
    configuration = None
    for selected, pixel in zip(report["captures"], report["pixel_checks"]):
        transaction._check_scope()
        attempt = _resolve_request(records, selected["request_key"])
        _need(attempt == selected["attempt_id"], "CAPTURE_ATTEMPT")
        permit, native, checksum = _native(
            transaction, attempt, SEALED_CONFIGURATION_CAPTURE_ACTION_ID
        )
        _need(
            checksum is not None
            and permit.permit_sha256 == selected["permit_sha256"]
            and checksum.sha256 == selected["capture_checksum_sha256"]
            and permit.admission.journal_head_sha256 == binding["journal_head_sha256"],
            "CAPTURE_ADMISSION",
        )
        facts = transaction.read_campaign_admission_evidence(attempt)
        hazard = facts["hazard_assessment"]
        _need(hazard.get("schema") == SEALED_HAZARD_SCHEMA, "CAPTURE_FACTS")
        candidate = verify_physical_camera_configuration(
            canonical(hazard["settings"]),
            expected_capabilities=capabilities,
            expected_settings_epoch=policy["subjects"]["settings_epoch"],
        )
        _need(
            configuration is None or candidate.payload == configuration.payload,
            "SETTINGS",
        )
        configuration = candidate
        # Reconstruct the historical inert capture plan from its original native
        # runtime, reviewed selection/expectation and admitted budget/settings.
        # Do not load today's executable or construct a consumed permit/owner.
        campaign = PhysicalCameraActivationCampaign(
            Path(plan["workspace"]),
            Path(plan["assigned_parent_directory"]),
            source_sha256=binding["source_sha256"],
            cell_id=binding["cell_id"],
            session_id=binding["session_id"],
            selection=PhysicalCameraSelection(canonical(plan["selection"])),
            expectation=CameraActivationExpectation(canonical(plan["expectation"])),
            runtime=native.preparation.runtime,
            mode=candidate.mode,
            controls=candidate.controls,
            budget=CameraCampaignBudget(**hazard["native_budget"]),
            configuration_verification=True,
            sealed_configuration_capture=True,
        )
        _need(
            native.preparation.runtime.registration_sha256
            == prep["software"]["capture"]["runtime_registration_sha256"],
            "CAPTURE_REVIEWED_RUNTIME",
        )
        # The earlier _native call authenticated the complete original checksum
        # collection. Its pair must also reproduce this independently built plan.
        expected = campaign.preparation_for_permit(permit)
        _need(expected.payload == native.preparation.payload, "CAPTURE_PLAN")
        plan_sha = digest(canonical(campaign.plan()))
        _need(
            hazard["plan_sha256"] == plan_sha == permit.registration.operation_sha256
            and hazard["request_key"] == selected["request_key"]
            and hazard["action_id"] == SEALED_CONFIGURATION_CAPTURE_ACTION_ID
            and hazard["capabilities_sha256"] == capabilities.capabilities_sha256
            and all(
                hazard[k] == plan[k]
                for k in (
                    "source_sha256",
                    "cell_id",
                    "session_id",
                    "launch_session_id",
                    "selected_identity_sha256",
                )
            ),
            "CAPTURE_CONTEXT",
        )
        context = dict(
            schema="rocell.camera_configuration_original_scope_summary.v2",
            original_setup=probe_hazard["original_context"],
            probe=probe_refs,
            probe_records_sha256=probe_records_sha,
            capabilities_sha256=capabilities.capabilities_sha256,
            settings_epoch=candidate.settings_epoch,
            plan_sha256=plan_sha,
            request_key=selected["request_key"],
            currentness_requires_revalidation=True,
            physical_authority=False,
            hardware_qualified=False,
            connected=False,
        )
        _need(
            canonical(hazard["original_context"]) == canonical(context),
            "CAPTURE_ORIGINAL_CONTEXT",
        )
        epochs = [
            dict(
                schema=SEALED_EPOCH_SCHEMA,
                original_setup_epoch=item,
                settings_epoch=candidate.settings_epoch,
                capabilities_sha256=capabilities.capabilities_sha256,
                original_probe_records_sha256=probe_records_sha,
                applied=False,
                physical_configuration_qualified=False,
            )
            for item in probe_facts["configuration_epochs"]
        ]
        _need(
            canonical(facts["configuration_epochs"]) == canonical(epochs),
            "CAPTURE_EPOCHS",
        )
        readback = compare_physical_camera_readback(
            candidate,
            native.evidence,
            expected_preparation=native.preparation,
            expected_capture_evidence_sha256=native.expected_evidence_sha256,
            expected_supervision_sha256=native.expected_supervision_sha256,
            expected_settings_epoch=candidate.settings_epoch,
        )
        captures.append(
            CameraReadbackSubject(native, readback.payload, readback.readback_sha256)
        )
        _historical_pixels(pixel, checksum)
    _need(type(configuration) is StagedPhysicalCameraConfiguration, "TWO_CAPTURES")
    assert configuration is not None
    preflight = assess_camera_operating_evidence(
        proposal_payload=canonical(policy),
        expected_proposal_sha256=data["proposal_sha256"],
        entry_payload=entry.payload,
        expected_entry_id=entry.to_dict()["entry_id"],
        expected_entry_binding=entry.to_dict()["binding"],
        purchase_profile_payload=purchase_profile_payload,
        expected_purchase_profile_sha256=digest(purchase_profile_payload),
        capabilities_payload=capabilities.payload,
        expected_capabilities_sha256=capabilities.capabilities_sha256,
        configuration_payload=configuration.payload,
        expected_settings_epoch=configuration.settings_epoch,
        probe=probe,
        captures=tuple(captures),
    )
    _need(
        preflight.payload == canonical(report["preflight"])
        and preflight.sha256 == report["preflight_sha256"],
        "PREFLIGHT",
    )
    _need(
        digest(canonical(transaction._audit_records(include_family=True)))
        == binding["original_records_sha256"]
        and transaction.snapshot() == snapshot,
        "INPUTS_CHANGED",
    )
    transaction._check_scope()
    return dict(
        preflight_sha256=preflight.sha256,
        original_records_sha256=binding["original_records_sha256"],
        pixel_check_semantics="HISTORICAL_READ_NOT_CURRENT_FILE_VERIFICATION",
        original_stage_authenticated=False,
        approved_operating_policy=False,
        connected=False,
        physical_authority=False,
        hardware_qualified=False,
    )
