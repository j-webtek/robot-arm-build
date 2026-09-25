"""Original probe + explicit settings -> read-only stage-5 capture context.

A completed probe is evidence, never a reusable capture permit. This handoff
authenticates its original M1 result/pair/facts and the candidate settings before
the separate configuration-capture admission provider may derive new facts.
There is no restore/import API or new device controller here.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from .camera_activation_campaign_contract import (
    ACTION_IDS,
    CONFIGURATION_CAPTURE_ACTION_ID,
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
    camera_activation_execution,
)
from .camera_activation_campaign_evidence import validate_camera_activation_evidence
from .camera_activation_runtime_policy import reviewed_activation_runtime_candidate
from .camera_probe_original_scope import VerifiedCameraProbeOriginal, _leases
from .cell_commissioning_coordinator import RegisteredActionRequest
from .commissioning_camera_persistence import M1PhysicalCameraTransaction
from .physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
    CONFIGURATION_PLAN_SCHEMA,
    SEALED_CONFIGURATION_PLAN_SCHEMA,
    verify_camera_activation_campaign_evidence,
)
from .physical_camera_configuration import (
    PhysicalCameraCapabilities,
    StagedPhysicalCameraConfiguration,
    verify_physical_camera_capabilities,
    stage_physical_camera_configuration,
)
from .physical_onboarding_attempts import AttemptState
from .physical_onboarding_v2 import V2SessionSnapshot
from .wizard_native_camera_enrollment import WizardNativeCameraEnrollment
from rocell.providers.windows.camera_worker_client import CameraCampaignBudget
from rocell.providers.windows.native_camera_protocol import canonical, digest

_ORIGINAL_READ = object()


class CameraConfigurationOriginalError(ValueError):
    pass


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise CameraConfigurationOriginalError(code)


def _probe_records_sha256(
    transaction: M1PhysicalCameraTransaction, attempt: str
) -> str:
    # Full original semantic decoding happens once before any short-lived
    # capture permit. Subsequent audits compare only this immutable attempt's
    # records; newly added capture records must not invalidate the old probe.
    records = transaction._audit_records()
    return _selected_probe_records_sha256(records, attempt)


def _selected_probe_records_sha256(records: dict[str, Any], attempt: str) -> str:
    selected = {
        name: record
        for name, record in records.items()
        if record["data"].get("attempt_id") == attempt
    }
    _need(bool(selected), "CONFIGURATION_ORIGINAL_PROBE_RECORDS_REQUIRED")
    return digest(canonical(selected))


@dataclass(frozen=True, slots=True)
class VerifiedCameraConfigurationOriginal:
    """In-process read provenance with a fixed capture request, not permission."""

    _setup: VerifiedCameraProbeOriginal = field(repr=False)
    _probe_request: RegisteredActionRequest = field(repr=False)
    _request: RegisteredActionRequest = field(repr=False)
    _enrollment: WizardNativeCameraEnrollment = field(repr=False)
    _enrollment_bytes: bytes = field(repr=False)
    _plan: bytes = field(repr=False)
    _capabilities: PhysicalCameraCapabilities = field(repr=False)
    _configuration: StagedPhysicalCameraConfiguration = field(repr=False)
    _probe_references: bytes = field(repr=False)
    _probe_admission: bytes = field(repr=False)
    _records_sha256: str
    _provenance: object = field(repr=False)

    def __post_init__(self) -> None:
        _need(
            self._provenance is _ORIGINAL_READ,
            "CONFIGURATION_ORIGINAL_RESTORE_FORBIDDEN",
        )

    def summary(self) -> dict[str, Any]:
        return dict(
            schema=(
                "rocell.camera_configuration_original_scope_summary.v2"
                if self._request.action_id == SEALED_CONFIGURATION_CAPTURE_ACTION_ID
                else "rocell.camera_configuration_original_scope_summary.v1"
            ),
            original_setup=self._setup.summary(),
            probe=json.loads(self._probe_references),
            probe_records_sha256=self._records_sha256,
            capabilities_sha256=self._capabilities.capabilities_sha256,
            settings_epoch=self._configuration.settings_epoch,
            plan_sha256=digest(self._plan),
            request_key=self._request.request_key,
            currentness_requires_revalidation=True,
            physical_authority=False,
            hardware_qualified=False,
            connected=False,
        )

    def assert_current(
        self,
        transaction: M1PhysicalCameraTransaction,
        request: RegisteredActionRequest,
        snapshot: V2SessionSnapshot,
    ) -> None:
        self._read_current_records(transaction, request, snapshot)

    def _read_current_records(
        self,
        transaction: M1PhysicalCameraTransaction,
        request: RegisteredActionRequest,
        snapshot: V2SessionSnapshot,
    ) -> dict[str, Any]:
        self.__post_init__()
        profile = PhysicalCameraActivationCampaign.from_plan(json.loads(self._plan))
        _need(
            type(request) is RegisteredActionRequest
            and request.cell_id == self._request.cell_id
            and request.session_id == self._request.session_id
            and request.action_id == self._request.action_id
            and request.action_id == profile.registration().action_id
            and request.action_id
            in (CONFIGURATION_CAPTURE_ACTION_ID, SEALED_CONFIGURATION_CAPTURE_ACTION_ID)
            and request.request_key == self._request.request_key,
            "CONFIGURATION_ORIGINAL_REQUEST_CHANGED",
        )
        # Read-only authentication uses the actual old probe request, not a
        # capture request relabelled to bypass the probe-only scope contract.
        records = self._setup._read_current_records(
            transaction, self._probe_request, snapshot
        )
        _need(
            canonical(self._enrollment.export_snapshot()) == self._enrollment_bytes,
            "CONFIGURATION_CURRENT_ENROLLMENT_CHANGED",
        )
        reference = json.loads(self._probe_references)
        _need(
            _selected_probe_records_sha256(records, reference["attempt_id"])
            == self._records_sha256,
            "CONFIGURATION_ORIGINAL_PROBE_CHANGED",
        )
        self._setup._check_context()
        transaction._check_scope()
        _need(
            transaction.held_leases
            == _leases(self._request.cell_id, self._request.session_id)
            and canonical(self._enrollment.export_snapshot()) == self._enrollment_bytes,
            "CONFIGURATION_ORIGINAL_FINAL_CONTEXT_CHANGED",
        )
        return records

    def observe_current_capacity(
        self,
        transaction: M1PhysicalCameraTransaction,
        request: RegisteredActionRequest,
        snapshot: V2SessionSnapshot,
    ) -> dict[str, Any]:
        """One fresh original audit shared only within this synchronous check.

        The final checks bracket disk observation and never renew a permit.
        No record or capacity observation is cached for subsequent calls.
        """
        from .camera_configuration_capacity import _capacity_from_current_records

        records = self._read_current_records(transaction, request, snapshot)
        capacity = _capacity_from_current_records(
            transaction,
            plan=json.loads(self._plan),
            request_key=request.request_key,
            snapshot=snapshot,
            records=records,
        )
        _need(
            transaction.snapshot() == snapshot,
            "CONFIGURATION_ORIGINAL_SNAPSHOT_CHANGED",
        )
        self._setup._check_context()
        transaction._check_scope()
        _need(
            transaction.held_leases == _leases(request.cell_id, request.session_id)
            and canonical(self._enrollment.export_snapshot()) == self._enrollment_bytes,
            "CONFIGURATION_ORIGINAL_FINAL_CONTEXT_CHANGED",
        )
        return capacity


def read_camera_configuration_originals(
    setup: VerifiedCameraProbeOriginal,
    transaction: M1PhysicalCameraTransaction,
    *,
    enrollment: WizardNativeCameraEnrollment,
    capabilities: PhysicalCameraCapabilities,
    configuration: StagedPhysicalCameraConfiguration,
    plan: dict[str, Any],
    request_key: str,
    expected_plan_sha256: str,
) -> VerifiedCameraConfigurationOriginal:
    """Read the same original store and independently derive the staged intent.

    The caller freshly authenticates setup for this bounded operation and guards
    current logged capability/settings publication. Serialized summaries cannot
    supply that owner or its guard. This function only reads files and data.
    """
    _need(
        type(setup) is VerifiedCameraProbeOriginal
        and type(transaction) is M1PhysicalCameraTransaction
        and type(enrollment) is WizardNativeCameraEnrollment
        and type(capabilities) is PhysicalCameraCapabilities
        and type(configuration) is StagedPhysicalCameraConfiguration,
        "CONFIGURATION_ORIGINAL_EXACT_OWNERS_REQUIRED",
    )
    setup._check_context()
    transaction._check_scope()
    snapshot = transaction.snapshot()
    _need(
        type(snapshot) is V2SessionSnapshot
        and transaction.held_leases
        == _leases(snapshot.header.cell_id, snapshot.header.session_id),
        "CONFIGURATION_ORIGINAL_CAMERA_SCOPE_REQUIRED",
    )
    capabilities = PhysicalCameraCapabilities(capabilities.payload)
    configuration = StagedPhysicalCameraConfiguration(configuration.payload)
    binding = capabilities.to_dict()["binding"]
    original_permit = transaction.read_campaign_permit(binding["attempt_id"])
    setup.assert_current(transaction, original_permit.request, snapshot)
    probe_plan = setup._preparation.to_dict()["plan"]
    probe = PhysicalCameraActivationCampaign.from_plan(probe_plan)
    _need(
        original_permit.registration.action_id == ACTION_IDS["probe"]
        and original_permit.permit_sha256 == binding["permit_sha256"],
        "CONFIGURATION_ORIGINAL_PROBE_PERMIT_CHANGED",
    )
    result = transaction.read_campaign_result(original_permit.attempt_id)
    _need(
        result.state is AttemptState.SEALED_KNOWN
        and not result.quarantine_latched
        and result.receipt is not None,
        "CONFIGURATION_SUCCESSFUL_ORIGINAL_PROBE_REQUIRED",
    )
    original_facts = transaction.read_campaign_admission_evidence(
        original_permit.attempt_id
    )
    artifacts = transaction.read_camera_activation_evidence(original_permit.attempt_id)
    _need(type(artifacts) is tuple, "CONFIGURATION_ORIGINAL_PROBE_PAIR_REQUIRED")
    assert type(artifacts) is tuple
    verify_camera_activation_campaign_evidence(
        artifacts, campaign=probe, expected_permit=original_permit
    )
    checked = validate_camera_activation_evidence(artifacts)
    accounting = camera_activation_execution(
        original_permit,
        artifacts,
        expected_deadline_ns=checked.run.to_dict()["parent_deadline_ns"],
    )
    _need(
        result.receipt == accounting.receipt,
        "CONFIGURATION_ORIGINAL_PROBE_ACCOUNTING_CHANGED",
    )
    prepared = probe.preparation_for_permit(original_permit)
    verified_caps = verify_physical_camera_capabilities(
        capabilities.payload,
        evidence=artifacts,
        expected_preparation=prepared,
        expected_evidence_sha256=artifacts[0].payload_sha256,
        expected_supervision_sha256=artifacts[1].payload_sha256,
        expected_source_sha256=probe_plan["source_sha256"],
        expected_capabilities_sha256=capabilities.capabilities_sha256,
    )
    intent = configuration.to_dict()
    derived = stage_physical_camera_configuration(
        verified_caps,
        intent["mode_choice_id"],
        configuration.controls,
        expected_capabilities_sha256=verified_caps.capabilities_sha256,
        expected_source_sha256=probe_plan["source_sha256"],
        expected_session_id=probe_plan["session_id"],
        expected_selected_identity_sha256=probe_plan["selected_identity_sha256"],
    )
    _need(
        derived.payload == configuration.payload,
        "CONFIGURATION_ORIGINAL_SETTINGS_CHANGED",
    )
    enrollment_bytes = canonical(setup._preparation.to_dict()["enrollment"])
    _need(
        canonical(enrollment.export_snapshot()) == enrollment_bytes,
        "CONFIGURATION_CURRENT_ENROLLMENT_CHANGED",
    )
    campaign = PhysicalCameraActivationCampaign.from_plan(plan)
    sealed = plan["schema"] == SEALED_CONFIGURATION_PLAN_SCHEMA
    _need(
        plan["schema"] in (CONFIGURATION_PLAN_SCHEMA, SEALED_CONFIGURATION_PLAN_SCHEMA),
        "CONFIGURATION_ORIGINAL_EXACT_PROFILE_REQUIRED",
    )
    expected = PhysicalCameraActivationCampaign.from_enrollment(
        setup._workspace,
        Path(probe_plan["assigned_parent_directory"]),
        enrollment=enrollment,
        launch_session_id=probe_plan["launch_session_id"],
        source_sha256=probe_plan["source_sha256"],
        cell_id=probe_plan["cell_id"],
        session_id=probe_plan["session_id"],
        runtime=reviewed_activation_runtime_candidate(
            setup._workspace,
            purpose="capture",
            source_sha256=probe_plan["source_sha256"],
        ),
        mode=configuration.mode,
        controls=configuration.controls,
        budget=CameraCampaignBudget(**plan["native_budget"]),
        configuration_verification=True,
        sealed_configuration_capture=sealed,
    )
    request = RegisteredActionRequest(
        probe_plan["cell_id"],
        probe_plan["session_id"],
        expected.registration().action_id,
        request_key,
        expected_plan_sha256,
    )
    _need(
        canonical(campaign.plan()) == canonical(expected.plan())
        and digest(canonical(plan)) == expected_plan_sha256,
        "CONFIGURATION_ORIGINAL_PLAN_CHANGED",
    )
    refs = dict(
        attempt_id=original_permit.attempt_id,
        request_key=original_permit.request.request_key,
        permit_sha256=original_permit.permit_sha256,
        operation_sha256=original_permit.registration.operation_sha256,
        evidence_sha256=artifacts[0].payload_sha256,
        supervision_sha256=artifacts[1].payload_sha256,
        preparation_sha256=prepared.preparation_sha256,
    )
    handoff = VerifiedCameraConfigurationOriginal(
        setup,
        original_permit.request,
        request,
        enrollment,
        enrollment_bytes,
        canonical(plan),
        verified_caps,
        derived,
        canonical(refs),
        canonical(original_facts),
        _probe_records_sha256(transaction, original_permit.attempt_id),
        _ORIGINAL_READ,
    )
    handoff.assert_current(transaction, request, snapshot)
    return handoff
