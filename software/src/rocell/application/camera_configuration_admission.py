"""Substantive original-bound facts for one stage-5 settings-readback capture.

Full setup/probe verification precedes this provider. It binds current reported
conditions, the explicit settings epoch and capture-specific headroom to a new
request. The same M1/core still owns permit issuance and one-use execution.
"""

import json
import time
from typing import Any

from .camera_configuration_original_scope import VerifiedCameraConfigurationOriginal
from .camera_activation_campaign_contract import SEALED_CONFIGURATION_CAPTURE_ACTION_ID
from .cell_commissioning_coordinator import RegisteredActionRequest
from .commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    M1PhysicalCameraTransaction,
    PhysicalCameraAdmissionFacts,
)
from .physical_camera_activation_campaign import PhysicalCameraActivationCampaign
from .physical_camera_mode_entry import camera_mode_operator_valid
from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from .physical_onboarding_v2 import V2SessionSnapshot
from rocell.providers.windows.native_camera_protocol import canonical, digest

HAZARD_SCHEMA = "rocell.camera_configuration_limited_hazard_assessment.v1"
EPOCH_SCHEMA = "rocell.camera_configuration_original_epoch.v1"
SEALED_HAZARD_SCHEMA = "rocell.camera_configuration_limited_hazard_assessment.v2"
SEALED_EPOCH_SCHEMA = "rocell.camera_configuration_original_epoch.v2"


class CameraConfigurationAdmissionError(ValueError):
    pass


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise CameraConfigurationAdmissionError(code)


class CameraConfigurationAdmission:
    """Fixed original capture context and current conditions; no restore API."""

    def __init__(
        self,
        original: VerifiedCameraConfigurationOriginal,
        transaction: M1PhysicalCameraTransaction,
        *,
        operator_id: str,
        arm_actuator_supply_disconnected: bool,
        bounded_configuration_capture_consent: bool,
    ) -> None:
        _need(
            type(original) is VerifiedCameraConfigurationOriginal
            and type(transaction) is M1PhysicalCameraTransaction,
            "CONFIGURATION_ADMISSION_ORIGINAL_OWNERS_REQUIRED",
        )
        _need(
            camera_mode_operator_valid(operator_id)
            and arm_actuator_supply_disconnected is True
            and bounded_configuration_capture_consent is True,
            "CONFIGURATION_CURRENT_OPERATOR_CONDITIONS_REQUIRED",
        )
        original.assert_current(transaction, original._request, transaction.snapshot())
        plan = json.loads(original._plan)
        workflow = json.loads(original._setup._workflow)
        prerequisite = workflow["prerequisites"]
        catalogs = [
            row
            for row in prerequisite["document"]["source_files"]
            if row["role"] == "stage_catalog"
        ]
        _need(len(catalogs) == 1, "CONFIGURATION_ORIGINAL_STAGE_CATALOG_REQUIRED")
        catalog = json.loads(catalogs[0]["payload_utf8"])
        requirements = [
            row for row in catalog["stages"] if row["stage"] == STAGE_ORDER[4].value
        ]
        _need(
            len(requirements) == 1
            and requirements[0]["actuator_power_requirement"] == "DISCONNECTED_REQUIRED"
            and requirements[0]["required_effect_classes"]
            == ["BOUNDED_CAMERA_CAMPAIGN"],
            "CONFIGURATION_ORIGINAL_STAGE_REQUIREMENTS_CHANGED",
        )
        capacity = original.observe_current_capacity(
            transaction, original._request, transaction.snapshot()
        )
        recorded_at = time.time_ns()
        _need(
            type(recorded_at) is int and 0 < recorded_at < 2**63,
            "CONFIGURATION_CONDITION_TIME_REQUIRED",
        )
        prior = json.loads(original._probe_admission)
        sealed = original._request.action_id == SEALED_CONFIGURATION_CAPTURE_ACTION_ID
        # These are the retained original setup dependencies plus the candidate
        # settings, not a replacement qualified configuration vector. Changing
        # settings changes all dependent permit epoch hashes before new effects.
        epochs = tuple(
            dict(
                schema=SEALED_EPOCH_SCHEMA if sealed else EPOCH_SCHEMA,
                original_setup_epoch=entry,
                settings_epoch=original._configuration.settings_epoch,
                capabilities_sha256=original._capabilities.capabilities_sha256,
                original_probe_records_sha256=original._records_sha256,
                applied=False,
                physical_configuration_qualified=False,
            )
            for entry in prior["configuration_epochs"]
        )
        hazard = dict(
            schema=SEALED_HAZARD_SCHEMA if sealed else HAZARD_SCHEMA,
            source_sha256=plan["source_sha256"],
            launch_session_id=plan["launch_session_id"],
            session_id=plan["session_id"],
            cell_id=plan["cell_id"],
            request_key=original._request.request_key,
            action_id=original._request.action_id,
            original_context=original.summary(),
            plan_sha256=digest(original._plan),
            selected_identity_sha256=plan["selected_identity_sha256"],
            prerequisite_reference=prerequisite["reference"],
            stage_catalog_sha256=catalogs[0]["sha256"],
            stage_requirements=requirements[0],
            settings=original._configuration.to_dict(),
            capabilities_sha256=original._capabilities.capabilities_sha256,
            current_condition_report=dict(
                operator_id=operator_id,
                recorded_at_utc_ns=recorded_at,
                arm_actuator_supply_disconnected=True,
                bounded_configuration_capture_consent=True,
                provenance="CURRENT_OPERATOR_REPORT",
                instrument_verified=False,
                observed_power_state="UNKNOWN",
            ),
            capacity_at_admission=capacity,
            scope="ONE_SELECTED_CAMERA_SETTINGS_READBACK_FRAME",
            leases=["CELL", "SESSION", "CAMERA"],
            native_budget=plan["native_budget"],
            campaign_timeout_ms=plan["campaign_timeout_ms"],
            fresh_endpoint_and_driver_match_required=True,
            installed_runtime_recheck_required=True,
            new_consumed_capture_permit_required=True,
            energy_envelope=None,
            automatic_retry_allowed=False,
            arm_access_authorized=False,
            motion_authorized=False,
            contact_authorized=False,
            physical_authority=False,
            hardware_qualified=False,
            meaning="Original probe evidence and explicit settings plus current operator-reported isolation and observed full-output headroom. Not an electrical measurement, stage PASS or execution permit.",
        )
        self._original = original
        self._facts = PhysicalCameraAdmissionFacts(hazard, epochs, plan["selection"])
        self._facts.retained_documents()
        original.assert_current(transaction, original._request, transaction.snapshot())

    def __call__(
        self,
        transaction: M1PhysicalCameraTransaction,
        request: RegisteredActionRequest,
        snapshot: V2SessionSnapshot,
    ) -> PhysicalCameraAdmissionFacts:
        self._original.observe_current_capacity(transaction, request, snapshot)
        # Keep the original fact hashes stable; free space is independently
        # observed again instead of replacing already-retained admission facts.
        return self._facts

    def persistence(
        self, runtime: PhysicalOnboardingM1Runtime
    ) -> M1PhysicalCameraPersistence:
        plan = json.loads(self._original._plan)
        _need(
            type(runtime) is PhysicalOnboardingM1Runtime
            and str(runtime.deployment_root / "native-camera-output")
            == plan["assigned_parent_directory"],
            "CONFIGURATION_ORIGINAL_RUNTIME_REQUIRED",
        )
        return M1PhysicalCameraPersistence(
            runtime,
            workspace_source_sha256=plan["source_sha256"],
            scoped_admission_facts=self,
        )

    def campaign(self) -> PhysicalCameraActivationCampaign:
        return PhysicalCameraActivationCampaign.from_plan(
            json.loads(self._original._plan)
        )

    def retained_documents(self) -> dict[str, Any]:
        return self._facts.retained_documents()
