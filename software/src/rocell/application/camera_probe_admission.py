"""Current, original-bound facts for a single bounded camera-probe request.

This is the substantive provider used by the existing camera M1/core, not a
permit issuer. Current metadata provenance belongs to the original handoff's
application guard. Sensor power/arm isolation are not inferred from a checkbox:
the retained condition is explicitly a current operator report, not a measured
electrical observation. No arm, control write or image capture is admitted.
"""

import json
from pathlib import Path
import time
from typing import Any

from .camera_activation_campaign_contract import ACTION_IDS
from .camera_probe_capacity import (
    observe_probe_capacity,
    _capacity_from_current_records,
)
from .camera_probe_original_scope import VerifiedCameraProbeOriginal
from .cell_commissioning_coordinator import RegisteredActionRequest
from .commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    M1PhysicalCameraTransaction,
    PhysicalCameraAdmissionFacts,
    _freeze_document,
)
from .physical_camera_activation_campaign import PhysicalCameraActivationCampaign
from .physical_camera_mode_entry import camera_mode_operator_valid
from .physical_camera_selection import selection_from_enrollment
from .physical_configuration_epochs import PhysicalConfigurationEpochs
from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from .physical_onboarding_v2 import V2SessionSnapshot
from .wizard_native_camera_enrollment import WizardNativeCameraEnrollment
from rocell.providers.windows.native_camera_protocol import canonical, digest

HAZARD_SCHEMA = "rocell.camera_probe_limited_hazard_assessment.v1"
EPOCH_SCHEMA = "rocell.camera_probe_original_configuration_epoch.v1"


class CameraProbeAdmissionError(ValueError):
    pass


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise CameraProbeAdmissionError(code)


class CameraProbeAdmission:
    """One original setup and request; no restoration or generic action selector."""

    def __init__(
        self,
        original: VerifiedCameraProbeOriginal,
        transaction: M1PhysicalCameraTransaction,
        *,
        enrollment: WizardNativeCameraEnrollment,
        operator_id: str,
        arm_actuator_supply_disconnected: bool,
        bounded_probe_consent: bool,
        request_key: str,
        expected_plan_sha256: str,
    ) -> None:
        _need(
            type(original) is VerifiedCameraProbeOriginal
            and type(transaction) is M1PhysicalCameraTransaction
            and type(enrollment) is WizardNativeCameraEnrollment,
            "CAMERA_PROBE_ORIGINAL_OWNERS_REQUIRED",
        )
        _need(
            camera_mode_operator_valid(operator_id)
            and arm_actuator_supply_disconnected is True
            and bounded_probe_consent is True,
            "CAMERA_PROBE_CURRENT_OPERATOR_CONDITIONS_REQUIRED",
        )
        preparation = original._preparation.to_dict()
        self._plan = canonical(preparation["plan"])
        plan = preparation["plan"]
        self._request = RegisteredActionRequest(
            plan["cell_id"],
            plan["session_id"],
            ACTION_IDS["probe"],
            request_key,
            expected_plan_sha256,
        )
        _need(
            digest(self._plan) == expected_plan_sha256,
            "CAMERA_PROBE_EXACT_PLAN_REQUIRED",
        )
        original.assert_current(transaction, self._request, transaction.snapshot())
        # Validate the complete fixed-purpose plan; no files or devices are
        # accessed by restoration. Execution still checks the installed runtime.
        campaign = PhysicalCameraActivationCampaign.from_plan(plan)
        _need(plan["purpose"] == "probe", "CAMERA_PROBE_ONLY")
        self._original, self._enrollment = original, enrollment
        self._enrollment_bytes = canonical(preparation["enrollment"])
        self._check_enrollment()

        workflow = json.loads(original._workflow)
        prerequisite = workflow["prerequisites"]
        sources = prerequisite["document"]["source_files"]
        catalogs = [row for row in sources if row["role"] == "stage_catalog"]
        _need(len(catalogs) == 1, "CAMERA_PROBE_ORIGINAL_CATALOG_REQUIRED")
        catalog = json.loads(catalogs[0]["payload_utf8"])
        requirements = [
            row for row in catalog["stages"] if row["stage"] == STAGE_ORDER[4].value
        ]
        _need(
            len(requirements) == 1
            and requirements[0]["actuator_power_requirement"] == "DISCONNECTED_REQUIRED"
            and requirements[0]["required_effect_classes"]
            == ["BOUNDED_CAMERA_CAMPAIGN"],
            "CAMERA_PROBE_ORIGINAL_STAGE_REQUIREMENTS",
        )
        epoch_record = workflow["configuration_epochs"]
        epochs = PhysicalConfigurationEpochs(_freeze_document(epoch_record["document"]))
        _need(
            epochs.sha256 == epoch_record["evidence_sha256"],
            "CAMERA_PROBE_ORIGINAL_EPOCH_CHANGED",
        )
        epoch_document = epochs.to_dict()
        epoch_documents = tuple(
            dict(
                schema=EPOCH_SCHEMA,
                original_vector_sha256=epoch_record["evidence_sha256"],
                original_reference=epoch_record["reference"],
                original_binding=epoch_document["binding"],
                entry=entry,
                physical_configuration_qualified=False,
            )
            for entry in epoch_document["entries"]
        )
        # A current/future capture or calibration output cannot be a prerequisite
        # for this initial producer. The full original reader already validated
        # the progressive epoch contract and every completed predecessor.
        capacity = observe_probe_capacity(
            transaction, plan=plan, request_key=request_key
        )
        recorded_at = time.time_ns()
        _need(
            type(recorded_at) is int and 0 < recorded_at < 2**63,
            "CAMERA_PROBE_CONDITION_TIME_REQUIRED",
        )
        historical_reviews = [
            workflow["qualification_cycles"][-1]["review"],
            workflow["static_contract"]["review"],
            workflow["received_camera_cycles"][-1]["review"],
            workflow["camera_identity_cycles"][-1]["review"],
        ]
        selected = selection_from_enrollment(
            enrollment,
            source_sha256=plan["source_sha256"],
            launch_session_id=plan["launch_session_id"],
        )
        _need(
            selected.sha256 == plan["selected_identity_sha256"],
            "CAMERA_PROBE_CURRENT_SELECTION_CHANGED",
        )
        hazard = dict(
            schema=HAZARD_SCHEMA,
            source_sha256=plan["source_sha256"],
            session_id=plan["session_id"],
            cell_id=plan["cell_id"],
            launch_session_id=plan["launch_session_id"],
            request_key=request_key,
            original_context=original.summary(),
            plan_sha256=digest(self._plan),
            operation_sha256=campaign.registration().operation_sha256,
            selected_identity_sha256=selected.sha256,
            prerequisite_reference=prerequisite["reference"],
            original_review_references=[row["reference"] for row in historical_reviews],
            stage_catalog_sha256=catalogs[0]["sha256"],
            stage_requirements=requirements[0],
            current_condition_report=dict(
                operator_id=operator_id,
                recorded_at_utc_ns=recorded_at,
                arm_actuator_supply_disconnected=True,
                bounded_probe_consent=True,
                provenance="CURRENT_OPERATOR_REPORT",
                instrument_verified=False,
                observed_power_state="UNKNOWN",
            ),
            capacity_at_admission=capacity,
            scope="ONE_SELECTED_CAMERA_PROBE_NO_CONTROL_WRITES_OR_IMAGES",
            leases=["CELL", "SESSION", "CAMERA"],
            native_budget=plan["native_budget"],
            campaign_timeout_ms=plan["campaign_timeout_ms"],
            fresh_endpoint_and_driver_match_required=True,
            installed_runtime_recheck_required=True,
            original_first_four_stages="REVIEWED_PASS",
            physical_isolation_instrument_verified=False,
            energy_envelope=None,
            automatic_retry_allowed=False,
            capture_authorized=False,
            arm_access_authorized=False,
            motion_authorized=False,
            contact_authorized=False,
            physical_authority=False,
            hardware_qualified=False,
            meaning="Original reviewed setup plus current operator-reported conditions and measured storage headroom. Not electrical measurement, hardware qualification, a permit, or arm authorization.",
        )
        self._facts = PhysicalCameraAdmissionFacts(
            hazard, epoch_documents, selected.identity_document
        )
        self._facts.retained_documents()  # Enforce aggregate retention capacity now.
        original.assert_current(transaction, self._request, transaction.snapshot())
        self._check_enrollment()

    def _check_enrollment(self) -> None:
        _need(
            canonical(self._enrollment.export_snapshot()) == self._enrollment_bytes,
            "CAMERA_PROBE_CURRENT_ENROLLMENT_CHANGED",
        )

    def __call__(
        self,
        transaction: M1PhysicalCameraTransaction,
        request: RegisteredActionRequest,
        snapshot: V2SessionSnapshot,
    ) -> PhysicalCameraAdmissionFacts:
        _need(
            type(request) is RegisteredActionRequest
            and request.request_key == self._request.request_key,
            "CAMERA_PROBE_REQUEST_CHANGED",
        )
        # The original guard just authenticated this complete record family in
        # the exact current scope. Reuse those bytes only for immediate headroom
        # arithmetic, instead of re-reading the same ledger solely to total it.
        records = self._original._read_current_records(transaction, request, snapshot)
        self._check_enrollment()
        _capacity_from_current_records(
            transaction,
            plan=json.loads(self._plan),
            request_key=request.request_key,
            snapshot=snapshot,
            records=records,
        )
        # Keep the full post-disk audit: a family-record-only mutation would
        # not necessarily change the session snapshot, source or enrollment.
        self._original.assert_current(transaction, request, snapshot)
        self._check_enrollment()
        # Facts remain the originally retained observation, so ordinary changes
        # in free disk bytes or attempt heads do not change permit dependencies.
        # Current capacity and context above are independently checked each time.
        return self._facts

    def persistence(
        self, runtime: PhysicalOnboardingM1Runtime
    ) -> M1PhysicalCameraPersistence:
        plan = json.loads(self._plan)
        _need(
            type(runtime) is PhysicalOnboardingM1Runtime
            and str(runtime.deployment_root / "native-camera-output")
            == plan["assigned_parent_directory"],
            "CAMERA_PROBE_ORIGINAL_RUNTIME_REQUIRED",
        )
        return M1PhysicalCameraPersistence(
            runtime,
            workspace_source_sha256=plan["source_sha256"],
            scoped_admission_facts=self,
        )

    def campaign(self) -> PhysicalCameraActivationCampaign:
        """Inert plan for the existing one-use acquisition/dispatch owner."""
        return PhysicalCameraActivationCampaign.from_plan(json.loads(self._plan))

    def retained_documents(self) -> dict[str, Any]:
        """Private diagnostics only; cannot restore this provider."""
        return self._facts.retained_documents()
