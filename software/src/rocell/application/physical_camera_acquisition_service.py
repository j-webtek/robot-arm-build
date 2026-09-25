"""Service-owned physical camera intent, separately held from native execution.

Status is cached. Explicit planning binds the current reviewed endpoint and the
two distinct dormant runtime candidates without inspecting files or devices.
Separate explicit file inspection/review retains diagnostic evidence only; it
does not register the candidates or lift any physical acquisition hold.
An intent is not a permit, passed stage, applied setting or received camera.
The separate camera M1/campaign composition owns eventual acquisition effects.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, TYPE_CHECKING

from .physical_camera_selection import selection_from_enrollment
from .camera_activation_expectation import expectation_from_enrollment
from .camera_activation_runtime_policy import reviewed_activation_runtime_candidate
from .camera_configuration_wizard_contract import (
    CAPTURE_ACTION_ID as CONFIGURATION_CAPTURE_PUBLIC_ACTION_ID,
    configuration_capture_budget,
)
from rocell.providers.windows.native_camera_activation_registration import (
    PreparedOwnedNativeActivation,
)
from .physical_camera_runtime_inspection import (
    PhysicalCameraRuntimeInspection,
    PhysicalCameraRuntimeInspectionError,
    inspect_physical_camera_runtime_pair,
    verify_physical_camera_runtime_inspection,
)
from .wizard_actions import WizardError
from .wizard_native_camera_enrollment import WizardNativeCameraEnrollment
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.native_camera_registration import (
    create_native_camera_runtime_registration,
)
from rocell.providers.windows.native_camera_capture_registration import (
    create_native_camera_capture_runtime_registration,
)

if TYPE_CHECKING:
    from .camera_capture_checksum import CameraCaptureChecksum
    from .physical_camera_capture_workflow import PhysicalCameraCaptureWorkflow
    from .physical_camera_activation_campaign import PhysicalCameraActivationCampaign
    from .commissioning_camera_persistence import M1PhysicalCameraPersistence
    from rocell.providers.windows.camera_worker_client import CameraCampaignBudget

VIEW_SCHEMA = "rocell.wizard_physical_camera.v1"
PLAN_SCHEMA = "rocell.physical_camera_acquisition_intent.v1"
RUNTIME_VIEW_SCHEMA = "rocell.wizard_physical_camera_runtime_review.v1"
RUNTIME_ACTIONS = frozenset(
    {"physical_camera_runtime_inspect", "physical_camera_runtime_review"}
)
RUNTIME_MEANING = (
    "Retained development runtime file observations and diagnostic review only. "
    "A matching file or distinct reviewer label is not native registration, a "
    "trusted release, current execution-time file ownership or driver/device "
    "qualification. No device is connected and no runtime is enabled."
)
# Fixed development identities, not hashes learned from an arbitrary executable
# and not runtime review or current-file verification. Historical builds remain
# untouched. Native release remains independently unavailable.
PROBE_HELPER = "e6072f26efa335ada46ef1459a66830a687b2d66c7ff45584aa4ac949eb027a1"
PROBE_RECORD = "705228b1595e1efeb2b8ceef171e3f6fdffad505b6e680b847cec352d712d7b6"
CAPTURE_HELPER = "31d2f2742b18c0935b3d7af07f8058f129421871be00860a3d7768e1e940ae2f"
CAPTURE_RECORD = "b6b60e92b1f95487be7c9230ddade77827b64a30063377b2f41a66d526eda2a5"
BASE_HOLDS = (
    "PURPOSE_SPECIFIC_RUNTIME_REVIEW_REQUIRED",
    "PHYSICAL_CAMERA_RELEASE_QUALIFICATION_REQUIRED",
    "PHYSICAL_PREREQUISITE_EVIDENCE_REQUIRED",
    "ACTUATOR_POWER_ISOLATION_NOT_VERIFIED",
)


class PhysicalCameraAcquisitionService:
    """Application intent/review state, not an alternate device dispatcher."""

    def __init__(
        self, workspace: Path, *, launch_id: str, source_sha256: str, mode: str
    ) -> None:
        if (
            not isinstance(workspace, Path)
            or not workspace.is_absolute()
            or type(launch_id) is not str
            or re.fullmatch(r"wizard-[0-9a-f]{32}", launch_id) is None
            or type(source_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None
            or source_sha256 == "0" * 64
            or mode not in ("physical", "rehearsal")
        ):
            raise WizardError(
                "PHYSICAL_CAMERA_BINDING", "Exact launch/source required."
            )
        self.workspace, self.source_sha256, self.launch_id, self.mode = (
            workspace,
            source_sha256,
            launch_id,
            mode,
        )
        self.directory = (
            workspace / "software/runs/physical-camera-acquisition" / launch_id
        )
        self.origin_launch_id = launch_id
        # Reserve a distinct camera-domain namespace without creating a store
        # or claiming that its physical prerequisite stages have been passed.
        lineage = digest(canonical({"launch": launch_id, "source": source_sha256}))
        self.cell_id = "wizard-physical-camera-" + lineage[:16]
        self.session_id = "physical-camera-" + lineage[16:48]
        catalog = digest(
            canonical(
                {
                    "schema": "rocell.physical_camera_development_runtime_pair.v1",
                    "probe_helper": PROBE_HELPER,
                    "probe_record": PROBE_RECORD,
                    "capture_helper": CAPTURE_HELPER,
                    "capture_record": CAPTURE_RECORD,
                    "qualified": False,
                }
            )
        )
        self.probe_runtime = create_native_camera_runtime_registration(
            workspace,
            source_sha256=source_sha256,
            catalog_sha256=catalog,
            helper_sha256=PROBE_HELPER,
            build_record_sha256=PROBE_RECORD,
        )
        self.capture_runtime = create_native_camera_capture_runtime_registration(
            workspace,
            source_sha256=source_sha256,
            catalog_sha256=catalog,
            helper_sha256=CAPTURE_HELPER,
            build_record_sha256=CAPTURE_RECORD,
        )
        self._lock = threading.RLock()
        self._retained_intent: bytes | None = None
        # The data workflow does not run a camera. Only a future admitted
        # dispatcher may supply its original retained probe/capture records.
        # Browser inputs can stage settings, never upload physical evidence.
        self._capture_workflow: PhysicalCameraCaptureWorkflow | None = None
        self._pending_workflow: PhysicalCameraCaptureWorkflow | None = None
        self._pending_configuration_result: bytes | None = None
        self._pending_configuration_context: str | None = None
        self._pending_observation_context: str | None = None
        self._pending_observation_ready = False
        self._pending_observation_action: str | None = None
        self._runtime_inspection: PhysicalCameraRuntimeInspection | None = None
        self._runtime_review: dict[str, Any] | None = None
        self._runtime_pending_review: dict[str, Any] | None = None
        self._runtime_pending_action: str | None = None
        self._runtime_pending_context: str | None = None
        self._runtime_pending_operation: str | None = None
        self._runtime_publication_context: str | None = None
        self._runtime_publication: dict[str, Any] = {
            "status": "NOT_PUBLISHED",
            "operation_id": None,
        }
        # One application transaction at a time. This is not a runtime release
        # switch; an original M1 admission context is still required by the
        # internal dispatch method and native execution remains independently held.
        self._dispatch_lock = threading.Lock()
        self._dispatch_owner: Any = None
        self._original_probe_attempted = False
        self._original_probe_diagnostics: dict[str, Any] | None = None
        self._original_probe_dispatch: dict[str, Any] | None = None
        self._original_probe_session: Any = None
        self._original_probe_enrollment: WizardNativeCameraEnrollment | None = None
        self._original_configuration_claims: set[str] = set()
        self._original_configuration_diagnostics: dict[str, Any] | None = None
        self._original_configuration_dispatch: dict[str, Any] | None = None
        self._view: dict[str, Any] = {
            "schema": VIEW_SCHEMA,
            "status": "NOT_STARTED",
            "source_sha256": source_sha256,
            "session_id": launch_id,
            "reviewed_endpoint": None,
            "runtimes": {
                "probe": self._runtime_view(self.probe_runtime),
                "capture": self._runtime_view(self.capture_runtime),
            },
            "plan": None,
            "configuration": {
                "capabilities": None,
                "candidate": None,
                "readback": None,
            },
            "last_frame": None,
            "fault": None,
            "publication": {"status": "NOT_PUBLISHED", "operation_id": None},
            "blockers": ["REVIEWED_PHYSICAL_ENDPOINT_REQUIRED", *BASE_HOLDS],
            "physical_authority": False,
            "hardware_qualified": False,
            "connected": False,
            "meaning": "Physical camera acquisition intent only. Runtime candidates remain dormant; separate file diagnostics are not runtime approval. No camera, settings or frame has been observed by this service.",
        }

    @staticmethod
    def _runtime_view(runtime: Any) -> dict[str, Any]:
        value = runtime.to_dict()
        return {
            "purpose": value["purpose"],
            "registration_sha256": runtime.registration_sha256,
            "helper_sha256": value["helper"]["sha256"],
            "build_record_sha256": value["build_record"]["sha256"],
            "status": value["status"],
            "dispatch_enabled": False,
            "driver_qualified": False,
        }

    def view(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(
                {
                    **self._view,
                    "runtime_inspection": self.runtime_view(),
                }
            )

    def _workflow_projection(self) -> None:
        """Publish already retained data; never infer connection or authority."""
        assert self._capture_workflow is not None
        observed = self._capture_workflow.view()
        self._view.update(
            status={
                "PROBE_ACCEPTED": "OBSERVATION_RETAINED",
                "SETTINGS_STAGED": "CONFIGURATION_STAGED",
                "CONTENT_VERIFIED": "CONTENT_VERIFIED",
                "HELD": "HELD",
            }[observed["status"]],
            session_id=self.session_id,
            configuration=observed["configuration"],
            last_frame=observed["last_frame"],
            plan=None,
            meaning=(
                "Retained native metadata, explicit settings intent and separately "
                "verified captured bytes. A finite closed capture is not a live "
                "connection, calibrated geometry, passed physical stage or received-unit qualification."
            ),
        )

    def dispatch_view(self) -> dict[str, Any] | None:
        """Cached transaction outcome for diagnostics; never reconnect on read."""
        with self._lock:
            owner = self._dispatch_owner
        return None if owner is None else owner.view()

    def run_admitted_campaign(
        self,
        operation: str,
        enrollment: WizardNativeCameraEnrollment,
        *,
        persistence: Any,
        request_key: str,
        expected_plan_sha256: str,
        cancellation: threading.Event,
    ) -> dict[str, Any]:
        """Internal original-store dispatch to the existing staged-data path.

        The setup composition must supply supported original-stage admission
        and a qualified runtime before this is exposed as a wizard action. This
        method does not build those facts from planning holds or intake labels.
        Original M1 readback precedes the handoff; Arrival remains responsible
        for result retention, completion logging and final image publication.
        """
        from .physical_camera_dispatch import PhysicalCameraDispatchOwner
        from .physical_native_camera_campaign import PhysicalNativeCameraCampaign

        if not self._dispatch_lock.acquire(False):
            raise WizardError(
                "CAMERA_DISPATCH_ACTIVE", "A camera transaction is active."
            )
        try:
            selected = enrollment.staged_copy()
            selected_bytes = canonical(selected.export_snapshot())
            # Seal the context before planning as well as after it, so an old
            # plan cannot accidentally be guarded by a newly published setting.
            with self._lock:
                before_plan = (
                    self.configuration_context_sha256(),
                    canonical(self._view["publication"]),
                )
                plan = self.preview_plan(operation, selected)
            if (
                digest(canonical(plan)) != expected_plan_sha256
                or plan["native_campaign_plan"] is None
                or cancellation.is_set()
            ):
                raise WizardError(
                    "CAMERA_DISPATCH_CONTEXT",
                    "The exact camera operation changed or stopped.",
                )
            with self._lock:
                if before_plan != (
                    self.configuration_context_sha256(),
                    canonical(self._view["publication"]),
                ):
                    raise WizardError(
                        "CAMERA_DISPATCH_CONTEXT_CHANGED",
                        "Camera context changed while preparing its plan.",
                    )
                if self._pending_workflow is not None or (
                    operation == "probe" and self._capture_workflow is not None
                ):
                    raise WizardError(
                        "CAMERA_DISPATCH_LIFECYCLE",
                        "Finish the existing observation; do not replay a probe or pending capture.",
                    )
                candidate = self._view["configuration"]["candidate"]
                settings_epoch = (
                    None if operation == "probe" else candidate["settings_epoch"]
                )
                sealed_context = self.configuration_context_sha256()
                sealed_publication = canonical(self._view["publication"])

            def revalidate_context() -> None:
                # No I/O, and no authority is returned. Run before prepare and
                # at the consumed scope's pre-start/READY/release boundaries.
                with self._lock:
                    if (
                        cancellation.is_set()
                        or canonical(enrollment.export_snapshot()) != selected_bytes
                        or self.configuration_context_sha256() != sealed_context
                        or canonical(self._view["publication"]) != sealed_publication
                        or self._pending_workflow is not None
                    ):
                        raise WizardError(
                            "CAMERA_DISPATCH_CONTEXT_CHANGED",
                            "Camera enrollment, settings or session changed during dispatch.",
                        )

            revalidate_context()
            owner = PhysicalCameraDispatchOwner(
                persistence,
                PhysicalNativeCameraCampaign.from_plan(plan["native_campaign_plan"]),
                revalidate_context=revalidate_context,
            )
            with self._lock:
                self._dispatch_owner = owner
            return owner.perform(
                request_key=request_key,
                sink=self,
                enrollment=selected,
                cancellation=cancellation,
                settings_epoch=settings_epoch,
            )
        finally:
            self._dispatch_lock.release()

    def preview_activation_plan(
        self,
        operation: str,
        enrollment: WizardNativeCameraEnrollment,
        *,
        capture_budget: CameraCampaignBudget | None = None,
        configuration_verification: bool = False,
        sealed_configuration_capture: bool = False,
    ) -> dict[str, Any]:
        """Inert original-service plan, including a distinct stage-5 readback.

        The profile switch is internal plan selection, not admission or a
        browser release switch. Capture still requires its own original facts.
        """
        from .physical_camera_activation_campaign import (
            PhysicalCameraActivationCampaign,
        )

        if (
            self.mode != "physical"
            or operation not in ("probe", "capture")
            or type(configuration_verification) is not bool
            or configuration_verification
            and operation != "capture"
            or type(sealed_configuration_capture) is not bool
            or sealed_configuration_capture
            and not configuration_verification
        ):
            raise WizardError(
                "ACTIVATION_PLAN_SCOPE", "An exact physical camera purpose is required."
            )
        if type(enrollment) is not WizardNativeCameraEnrollment:
            raise WizardError(
                "ACTIVATION_PLAN_ENROLLMENT",
                "A current reviewed enrollment is required.",
            )
        selected = selection_from_enrollment(
            enrollment,
            source_sha256=self.source_sha256,
            launch_session_id=self.launch_id,
        )
        with self._lock:
            if operation == "capture":
                if (
                    self._capture_workflow is None
                    or not self._capture_workflow._activation
                    or capture_budget is None
                ):
                    raise WizardError(
                        "ACTIVATION_CAPTURE_SETTINGS",
                        "Publish the exact v2 probe and stage its settings before planning capture.",
                    )
                plan = self._capture_workflow.capture_plan(
                    budget=capture_budget,
                    configuration_verification=configuration_verification,
                    sealed_configuration_capture=sealed_configuration_capture,
                )
                if plan["selected_identity_sha256"] != selected.sha256:
                    raise WizardError(
                        "ACTIVATION_PLAN_ENROLLMENT",
                        "Current enrollment differs from the retained probe.",
                    )
                return plan
            if capture_budget is not None:
                raise WizardError(
                    "ACTIVATION_PROBE_BUDGET",
                    "Probe has no capture settings or frame budget.",
                )
            return PhysicalCameraActivationCampaign.from_enrollment(
                self.workspace,
                self.directory / "native-camera-output",
                enrollment=enrollment,
                launch_session_id=self.launch_id,
                source_sha256=self.source_sha256,
                cell_id=self.cell_id,
                session_id=self.session_id,
                runtime=reviewed_activation_runtime_candidate(
                    self.workspace, purpose="probe", source_sha256=self.source_sha256
                ),
            ).plan()

    def run_original_probe(
        self,
        session: Any,
        enrollment: WizardNativeCameraEnrollment,
        *,
        request_key: str,
        expected_header_sha256: str,
        expected_preparation_sha256: str,
        expected_review_sha256: str,
        expected_plan_sha256: str,
        operator_id: str,
        arm_actuator_supply_disconnected: bool,
        bounded_probe_consent: bool,
        cancellation: threading.Event,
        deadline_ns: int,
        progress: Callable[[str], None],
        validate_current_context: Callable[[], object],
    ) -> dict[str, Any]:
        """Authenticate originals, derive scoped facts, and use the same dispatcher.

        Internal application entrypoint, not an HTTP release API. Arrival must
        supply its current logged metadata/operation guard and one-use intent.
        Result publication still belongs to Arrival's successful completion log.
        One nonreentrant acquisition lock covers authentication through staging.
        """
        from .camera_probe_admission import CameraProbeAdmission
        from .camera_probe_original_scope import (
            read_camera_probe_originals,
            MAX_CONTEXT_NS,
        )
        from .commissioning_camera_persistence import M1PhysicalCameraPersistence
        from .physical_camera_session import PhysicalCameraSession
        from .physical_camera_mode_entry import camera_mode_operator_valid
        from .physical_onboarding_leases import LeaseLevel, LeaseSpec
        from .cell_commissioning_coordinator import RegisteredActionRequest
        from .camera_activation_campaign_contract import ACTION_IDS

        started = time.monotonic_ns()
        if (
            self.mode != "physical"
            or type(session) is not PhysicalCameraSession
            or type(enrollment) is not WizardNativeCameraEnrollment
            or type(cancellation) is not threading.Event
            or type(deadline_ns) is not int
            or not started < deadline_ns <= started + MAX_CONTEXT_NS
            or not callable(progress)
            or not callable(validate_current_context)
            or not camera_mode_operator_valid(operator_id)
            or arm_actuator_supply_disconnected is not True
            or bounded_probe_consent is not True
        ):
            raise WizardError(
                "CAMERA_PROBE_ORIGINAL_INPUT",
                "Current original setup, bounded operation and explicit operator conditions are required.",
            )

        def current() -> None:
            if (
                cancellation.is_set()
                or not started <= time.monotonic_ns() < deadline_ns
            ):
                raise WizardError(
                    "CAMERA_PROBE_OPERATION_ENDED",
                    "Stop or the original operation deadline ended this probe.",
                )
            if validate_current_context() is not None:
                raise WizardError(
                    "CAMERA_PROBE_CONTEXT_CHANGED",
                    "The application guard must validate current context, not return approval.",
                )
            if (
                cancellation.is_set()
                or not started <= time.monotonic_ns() < deadline_ns
            ):
                raise WizardError(
                    "CAMERA_PROBE_OPERATION_ENDED",
                    "Context checking cannot extend the original deadline.",
                )

        if not self._dispatch_lock.acquire(False):
            raise WizardError(
                "CAMERA_DISPATCH_ACTIVE", "A camera transaction is active."
            )
        began = False
        try:
            with self._lock:
                if (
                    self._original_probe_attempted
                    or self._dispatch_owner is not None
                    or self._capture_workflow is not None
                    or self._pending_workflow is not None
                ):
                    raise WizardError(
                        "CAMERA_PROBE_ALREADY_ATTEMPTED",
                        "Inspect the retained original outcome; do not replay or replace the probe.",
                    )
                self._original_probe_attempted = True
                began = True
                self._original_probe_diagnostics = {
                    "status": "AUTHENTICATING_ORIGINALS",
                    "physical_authority": False,
                    "hardware_qualified": False,
                    "automatic_retry_allowed": False,
                }
            current()
            self.bind_verified_session(session)
            with self._lock:
                self._original_probe_session = session
                self._original_probe_enrollment = enrollment
            bound = session.descriptor()
            RegisteredActionRequest(
                bound["cell_id"],
                bound["session_id"],
                ACTION_IDS["probe"],
                request_key,
                expected_plan_sha256,
            )
            if not session._operation_lock.acquire(False):
                raise WizardError("CAMERA_SETUP_BUSY", "The original session is busy.")
            try:
                store = session._store
                if type(store) is not M1PhysicalCameraPersistence:
                    raise WizardError(
                        "CAMERA_PROBE_REFRESH_REQUIRED",
                        "Refresh the existing original store before probing; no store is created automatically.",
                    )
                progress(
                    "Authenticating the complete reviewed setup under camera ownership; no device is open."
                )
                leases = (
                    LeaseSpec(LeaseLevel.CELL, bound["cell_id"]),
                    LeaseSpec(LeaseLevel.SESSION, bound["session_id"]),
                    LeaseSpec(LeaseLevel.CAMERA, bound["cell_id"]),
                )
                with store.transaction(leases) as tx:
                    original = read_camera_probe_originals(
                        tx,
                        workspace=self.workspace,
                        source_sha256=self.source_sha256,
                        launch_session_id=self.launch_id,
                        expected_header_sha256=expected_header_sha256,
                        expected_preparation_sha256=expected_preparation_sha256,
                        expected_review_sha256=expected_review_sha256,
                        cancellation=cancellation,
                        deadline_ns=deadline_ns,
                        validate_current_context=current,
                    )
                    with self._lock:
                        assert self._original_probe_diagnostics is not None
                        self._original_probe_diagnostics.update(
                            status="ORIGINALS_AUTHENTICATED",
                            original=original.summary(),
                        )
                    admission = CameraProbeAdmission(
                        original,
                        tx,
                        enrollment=enrollment,
                        operator_id=operator_id,
                        arm_actuator_supply_disconnected=arm_actuator_supply_disconnected,
                        bounded_probe_consent=bounded_probe_consent,
                        request_key=request_key,
                        expected_plan_sha256=expected_plan_sha256,
                    )
                    with self._lock:
                        assert self._original_probe_diagnostics is not None
                        self._original_probe_diagnostics.update(
                            status="ADMISSION_DERIVED",
                            original=original.summary(),
                            admission=admission.retained_documents(),
                        )
                runtime = store._runtime
            finally:
                session._operation_lock.release()
            current()
            progress(
                "Running one identity-bound capability probe through the existing bounded camera dispatcher."
            )
            result = self._dispatch_activation_locked(
                admission.campaign(),
                enrollment,
                persistence=admission.persistence(runtime),
                request_key=request_key,
                expected_plan_sha256=expected_plan_sha256,
                cancellation=cancellation,
                revalidate_original_context=current,
            )
            current()
            with self._lock:
                assert self._original_probe_diagnostics is not None
                self._original_probe_diagnostics["status"] = (
                    "RESULT_STAGED_NOT_PUBLISHED"
                )
            return result
        except BaseException:
            if began:
                with self._lock:
                    assert self._original_probe_diagnostics is not None
                    self._original_probe_diagnostics["failed_phase"] = (
                        self._original_probe_diagnostics["status"]
                    )
                    self._original_probe_diagnostics["status"] = "FAILED_HELD"
                self.invalidate()
            raise
        finally:
            self._dispatch_lock.release()

    def run_original_configuration_capture(
        self,
        session: Any,
        enrollment: WizardNativeCameraEnrollment,
        *,
        request_key: str,
        expected_header_sha256: str,
        expected_preparation_sha256: str,
        expected_review_sha256: str,
        expected_plan_sha256: str,
        capture_budget: CameraCampaignBudget,
        operator_id: str,
        arm_actuator_supply_disconnected: bool,
        bounded_configuration_capture_consent: bool,
        cancellation: threading.Event,
        deadline_ns: int,
        progress: Callable[[str], None],
        validate_current_context: Callable[[], object],
        sealed_configuration_capture: bool = False,
    ) -> dict[str, Any]:
        """One explicitly requested settings capture against the actual originals.

        The outer wizard must bind logged probe/settings publication and queue
        intent once. This service authenticates original files before a new
        short-lived permit, derives substantive facts, and stages data only.
        New explicit request keys may support later reopen checks; a consumed
        key never retries, and original quarantine is still enforced by M1/core.
        """
        from .camera_configuration_admission import CameraConfigurationAdmission
        from .camera_configuration_original_scope import (
            read_camera_configuration_originals,
        )
        from .camera_probe_original_scope import (
            read_camera_probe_originals,
            MAX_CONTEXT_NS,
        )
        from .camera_activation_campaign_contract import (
            CONFIGURATION_CAPTURE_ACTION_ID,
            SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
        )
        from .commissioning_camera_persistence import M1PhysicalCameraPersistence
        from .cell_commissioning_coordinator import RegisteredActionRequest
        from .physical_camera_configuration import (
            PhysicalCameraCapabilities,
            StagedPhysicalCameraConfiguration,
        )
        from .physical_camera_session import PhysicalCameraSession
        from .physical_camera_mode_entry import camera_mode_operator_valid
        from .physical_onboarding_leases import LeaseLevel, LeaseSpec
        from rocell.providers.windows.camera_worker_client import CameraCampaignBudget

        started = time.monotonic_ns()
        if (
            self.mode != "physical"
            or type(session) is not PhysicalCameraSession
            or type(enrollment) is not WizardNativeCameraEnrollment
            or type(capture_budget) is not CameraCampaignBudget
            or type(cancellation) is not threading.Event
            or type(deadline_ns) is not int
            or not started < deadline_ns <= started + MAX_CONTEXT_NS
            or not callable(progress)
            or not callable(validate_current_context)
            or not camera_mode_operator_valid(operator_id)
            or arm_actuator_supply_disconnected is not True
            or bounded_configuration_capture_consent is not True
            or type(sealed_configuration_capture) is not bool
        ):
            raise WizardError(
                "CAMERA_CONFIGURATION_ORIGINAL_INPUT",
                "Exact original owners, finite capture and current operator conditions are required.",
            )
        if not self._dispatch_lock.acquire(False):
            raise WizardError(
                "CAMERA_DISPATCH_ACTIVE", "A camera transaction is active."
            )
        began = False
        previous_owner = None
        try:
            with self._lock:
                workflow = self._capture_workflow
                if (
                    session is not self._original_probe_session
                    or enrollment is not self._original_probe_enrollment
                    or self._original_probe_dispatch is None
                    or self._original_probe_dispatch["transaction"]["attempt_state"]
                    != "SEALED_KNOWN"
                    or self._original_probe_dispatch["readback_scope"] != "EXITED"
                    or workflow is None
                    or not workflow._activation
                    or workflow._capabilities is None
                    or workflow._configuration is None
                    or self._pending_workflow is not None
                    or self._view["publication"]["status"] != "CURRENT"
                ):
                    raise WizardError(
                        "CAMERA_CONFIGURATION_ORIGINAL_CONTEXT",
                        "The same original probe/session/enrollment and published explicit settings are required.",
                    )
                bound = session.descriptor()
                if (
                    bound["directory"] != str(self.directory)
                    or bound["cell_id"] != self.cell_id
                    or bound["session_id"] != self.session_id
                    or bound["source_sha256"] != self.source_sha256
                ):
                    raise WizardError(
                        "CAMERA_CONFIGURATION_ORIGINAL_CONTEXT",
                        "The original camera store changed.",
                    )
                request = RegisteredActionRequest(
                    self.cell_id,
                    self.session_id,
                    (
                        SEALED_CONFIGURATION_CAPTURE_ACTION_ID
                        if sealed_configuration_capture
                        else CONFIGURATION_CAPTURE_ACTION_ID
                    ),
                    request_key,
                    expected_plan_sha256,
                )
                if (
                    request_key in self._original_configuration_claims
                    or len(self._original_configuration_claims) >= 128
                ):
                    raise WizardError(
                        "CAMERA_CONFIGURATION_REQUEST_CONSUMED",
                        "This capture key was already attempted or the bounded session limit was reached; inspect originals without replay.",
                    )
                plan = self.preview_activation_plan(
                    "capture",
                    enrollment,
                    capture_budget=capture_budget,
                    configuration_verification=True,
                    sealed_configuration_capture=sealed_configuration_capture,
                )
                if digest(canonical(plan)) != expected_plan_sha256:
                    raise WizardError(
                        "CAMERA_CONFIGURATION_PLAN_CHANGED",
                        "The exact current settings capture differs from the preview.",
                    )
                capabilities = PhysicalCameraCapabilities(
                    workflow._capabilities.payload
                )
                configuration = StagedPhysicalCameraConfiguration(
                    workflow._configuration.payload
                )
                sealed_context = self.configuration_context_sha256()
                sealed_enrollment = canonical(enrollment.export_snapshot())
                self._original_configuration_claims.add(request.request_key)
                self._original_configuration_diagnostics = dict(
                    status="AUTHENTICATING_ORIGINALS",
                    request_key=request_key,
                    plan_sha256=expected_plan_sha256,
                    settings_epoch=configuration.settings_epoch,
                    physical_authority=False,
                    hardware_qualified=False,
                    automatic_retry_allowed=False,
                )
                self._original_configuration_dispatch = None
                previous_owner, began = self._dispatch_owner, True

            def current() -> None:
                if (
                    cancellation.is_set()
                    or not started <= time.monotonic_ns() < deadline_ns
                ):
                    raise WizardError(
                        "CAMERA_CONFIGURATION_OPERATION_ENDED",
                        "Stop or the original deadline ended this settings capture.",
                    )
                if validate_current_context() is not None:
                    raise WizardError(
                        "CAMERA_CONFIGURATION_CONTEXT_CHANGED",
                        "The application guard validates current context; it cannot grant approval.",
                    )
                with self._lock:
                    if (
                        cancellation.is_set()
                        or not started <= time.monotonic_ns() < deadline_ns
                        or session is not self._original_probe_session
                        or enrollment is not self._original_probe_enrollment
                        or canonical(enrollment.export_snapshot()) != sealed_enrollment
                        or self.configuration_context_sha256() != sealed_context
                    ):
                        raise WizardError(
                            "CAMERA_CONFIGURATION_CONTEXT_CHANGED",
                            "Original identity, settings or operation lifetime changed.",
                        )

            current()
            if not session._operation_lock.acquire(False):
                raise WizardError("CAMERA_SETUP_BUSY", "The original session is busy.")
            try:
                store = session._store
                if type(store) is not M1PhysicalCameraPersistence:
                    raise WizardError(
                        "CAMERA_CONFIGURATION_REFRESH_REQUIRED",
                        "Refresh the existing original store first; capture never initializes a replacement store.",
                    )
                leases = (
                    LeaseSpec(LeaseLevel.CELL, bound["cell_id"]),
                    LeaseSpec(LeaseLevel.SESSION, bound["session_id"]),
                    LeaseSpec(LeaseLevel.CAMERA, bound["cell_id"]),
                )
                progress(
                    "Authenticating original setup, probe evidence and selected settings; no new device is open."
                )
                with store.transaction(leases) as tx:
                    setup = read_camera_probe_originals(
                        tx,
                        workspace=self.workspace,
                        source_sha256=self.source_sha256,
                        launch_session_id=self.launch_id,
                        expected_header_sha256=expected_header_sha256,
                        expected_preparation_sha256=expected_preparation_sha256,
                        expected_review_sha256=expected_review_sha256,
                        cancellation=cancellation,
                        deadline_ns=deadline_ns,
                        validate_current_context=current,
                    )
                    original = read_camera_configuration_originals(
                        setup,
                        tx,
                        enrollment=enrollment,
                        capabilities=capabilities,
                        configuration=configuration,
                        plan=plan,
                        request_key=request_key,
                        expected_plan_sha256=expected_plan_sha256,
                    )
                    with self._lock:
                        assert self._original_configuration_diagnostics is not None
                        self._original_configuration_diagnostics.update(
                            status="ORIGINALS_AUTHENTICATED",
                            original=original.summary(),
                        )
                    admission = CameraConfigurationAdmission(
                        original,
                        tx,
                        operator_id=operator_id,
                        arm_actuator_supply_disconnected=arm_actuator_supply_disconnected,
                        bounded_configuration_capture_consent=bounded_configuration_capture_consent,
                    )
                    with self._lock:
                        assert self._original_configuration_diagnostics is not None
                        self._original_configuration_diagnostics.update(
                            status="ADMISSION_DERIVED",
                            admission=admission.retained_documents(),
                        )
                runtime = store._runtime
            finally:
                session._operation_lock.release()
            current()
            progress(
                "Running one selected-camera settings-readback frame through the existing bounded dispatcher."
            )
            result = self._dispatch_activation_locked(
                admission.campaign(),
                enrollment,
                persistence=admission.persistence(runtime),
                request_key=request_key,
                expected_plan_sha256=expected_plan_sha256,
                cancellation=cancellation,
                revalidate_original_context=current,
            )
            current()
            with self._lock:
                assert self._original_configuration_diagnostics is not None
                self._original_configuration_diagnostics["status"] = (
                    "RESULT_STAGED_NOT_PUBLISHED"
                )
            return result
        except BaseException:
            if began:
                with self._lock:
                    assert self._original_configuration_diagnostics is not None
                    self._original_configuration_diagnostics["failed_phase"] = (
                        self._original_configuration_diagnostics["status"]
                    )
                    self._original_configuration_diagnostics["status"] = "FAILED_HELD"
                self.invalidate()
            raise
        finally:
            if began:
                with self._lock:
                    if (
                        self._dispatch_owner is not previous_owner
                        and self._dispatch_owner is not None
                    ):
                        self._original_configuration_dispatch = (
                            self._dispatch_owner.retained_diagnostics()
                        )
            self._dispatch_lock.release()

    def run_admitted_activation_campaign(
        self,
        campaign: PhysicalCameraActivationCampaign,
        enrollment: WizardNativeCameraEnrollment,
        *,
        persistence: M1PhysicalCameraPersistence,
        request_key: str,
        expected_plan_sha256: str,
        cancellation: threading.Event,
        revalidate_original_context: Callable[[], object],
    ) -> dict[str, Any]:
        """Existing owner, v2 original-store handoff, still no public route.

        The original service must supply substantive current facts and capacity
        admission. This method does not derive them from a display or report.
        The same operation lock and outer completion/publication contract apply.
        """
        from .physical_camera_activation_campaign import (
            PhysicalCameraActivationCampaign,
        )

        if type(campaign) is not PhysicalCameraActivationCampaign or not callable(
            revalidate_original_context
        ):
            raise WizardError(
                "ACTIVATION_ORIGINAL_CONTEXT",
                "An exact v2 campaign and original-context guard are required.",
            )
        if (
            self.mode != "physical"
            or type(enrollment) is not WizardNativeCameraEnrollment
            or type(cancellation) is not threading.Event
        ):
            raise WizardError(
                "ACTIVATION_SERVICE_SCOPE",
                "Physical mode, exact enrollment and an explicit Stop signal are required.",
            )
        if not self._dispatch_lock.acquire(False):
            raise WizardError(
                "CAMERA_DISPATCH_ACTIVE", "A camera transaction is active."
            )
        try:
            return self._dispatch_activation_locked(
                campaign,
                enrollment,
                persistence=persistence,
                request_key=request_key,
                expected_plan_sha256=expected_plan_sha256,
                cancellation=cancellation,
                revalidate_original_context=revalidate_original_context,
            )
        finally:
            self._dispatch_lock.release()

    def _dispatch_activation_locked(
        self,
        campaign: PhysicalCameraActivationCampaign,
        enrollment: WizardNativeCameraEnrollment,
        *,
        persistence: M1PhysicalCameraPersistence,
        request_key: str,
        expected_plan_sha256: str,
        cancellation: threading.Event,
        revalidate_original_context: Callable[[], object],
    ) -> dict[str, Any]:
        """Shared dispatch body; caller holds the existing nonreentrant lock."""
        from .physical_camera_dispatch import PhysicalCameraDispatchOwner
        from .physical_camera_activation_campaign import (
            CONFIGURATION_PLAN_SCHEMA,
            SEALED_CONFIGURATION_PLAN_SCHEMA,
        )
        from rocell.providers.windows.camera_worker_client import CameraCampaignBudget

        selected = enrollment.staged_copy()
        sealed_enrollment = canonical(selected.export_snapshot())
        plan = campaign.plan()
        operation = plan["purpose"]
        with self._lock:
            context = self.configuration_context_sha256()
            publication = canonical(self._view["publication"])
            if self._pending_workflow is not None or (
                operation == "probe" and self._capture_workflow is not None
            ):
                raise WizardError(
                    "CAMERA_DISPATCH_LIFECYCLE",
                    "Finish the existing observation; do not replay or replace it.",
                )
            expected = self.preview_activation_plan(
                operation,
                selected,
                configuration_verification=plan["schema"]
                in (CONFIGURATION_PLAN_SCHEMA, SEALED_CONFIGURATION_PLAN_SCHEMA),
                sealed_configuration_capture=plan["schema"]
                == SEALED_CONFIGURATION_PLAN_SCHEMA,
                capture_budget=(
                    CameraCampaignBudget(**plan["native_budget"])
                    if operation == "capture"
                    else None
                ),
            )
            if (
                canonical(plan) != canonical(expected)
                or digest(canonical(expected)) != expected_plan_sha256
            ):
                raise WizardError(
                    "ACTIVATION_PLAN_CHANGED",
                    "The exact current camera profile/plan differs from the original intent.",
                )
            epoch = (
                None
                if operation == "probe"
                else self._view["configuration"]["candidate"]["settings_epoch"]
            )

        def current():
            if revalidate_original_context() is not None:
                raise WizardError(
                    "ACTIVATION_ORIGINAL_CONTEXT",
                    "The original guard may refuse, never grant authority.",
                )
            with self._lock:
                if (
                    cancellation.is_set()
                    or canonical(enrollment.export_snapshot()) != sealed_enrollment
                    or self.configuration_context_sha256() != context
                    or canonical(self._view["publication"]) != publication
                    or self._pending_workflow is not None
                ):
                    raise WizardError(
                        "CAMERA_DISPATCH_CONTEXT_CHANGED",
                        "Original camera context changed during dispatch.",
                    )

        current()
        owner = PhysicalCameraDispatchOwner(
            persistence, campaign, revalidate_context=current
        )
        with self._lock:
            self._dispatch_owner = owner
        try:
            return owner.perform(
                request_key=request_key,
                sink=self,
                enrollment=selected,
                cancellation=cancellation,
                settings_epoch=epoch,
            )
        finally:
            if operation == "probe" and self._original_probe_attempted:
                # Later captures replace the last dispatcher. Pin this original
                # probe's exact diagnostic outcome before that can happen.
                with self._lock:
                    self._original_probe_dispatch = owner.retained_diagnostics()

    def accept_retained_probe(
        self,
        enrollment: WizardNativeCameraEnrollment,
        evidence: Any,
        *,
        expected_preparation: Any,
        expected_evidence_sha256: str,
        expected_supervision_sha256: str | None = None,
    ) -> None:
        """Internal data handoff from the future admitted camera dispatcher.

        The caller must supply the independent retained-record digest and exact
        original preparation. This is not admission, M1 retention or a browser
        evidence-import API. No native runner or fixture fallback is invoked.
        Call ``publish_retained_observation`` only after outer result logging.
        """
        from .physical_camera_capture_workflow import PhysicalCameraCaptureWorkflow

        if self.mode != "physical":
            raise WizardError(
                "PHYSICAL_CAMERA_SCOPE", "Physical data context required."
            )
        selection = selection_from_enrollment(
            enrollment,
            source_sha256=self.source_sha256,
            launch_session_id=self.launch_id,
        )
        activation = type(expected_preparation) is PreparedOwnedNativeActivation
        native_arguments: dict[str, Any] = {
            "probe_runtime": self.probe_runtime,
            "capture_runtime": self.capture_runtime,
        }
        if activation:
            native_arguments = {
                "probe_runtime": reviewed_activation_runtime_candidate(
                    self.workspace, purpose="probe", source_sha256=self.source_sha256
                ),
                "capture_runtime": reviewed_activation_runtime_candidate(
                    self.workspace, purpose="capture", source_sha256=self.source_sha256
                ),
                "activation_expectation": expectation_from_enrollment(
                    enrollment,
                    source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                ),
            }
        with self._lock:
            if self._pending_workflow is not None or self._capture_workflow is not None:
                raise WizardError(
                    "CAMERA_PROBE_ALREADY_RETAINED",
                    "Do not replace or replay an existing probe.",
                )
            candidate = PhysicalCameraCaptureWorkflow(
                self.workspace,
                (
                    self.directory / "native-camera-output"
                    if activation
                    else self.directory
                ),
                source_sha256=self.source_sha256,
                cell_id=self.cell_id,
                session_id=self.session_id,
                selection=selection,
                **native_arguments,
            )
            self._pending_workflow = candidate
            self._view["reviewed_endpoint"] = selection.safe_summary()
            self._view["status"] = "HELD"
            self._pending_observation_context = self.configuration_context_sha256()
            self._pending_observation_ready = False
            self._view["publication"] = {"status": "PENDING", "operation_id": None}
            try:
                candidate.accept_probe(
                    evidence,
                    expected_preparation=expected_preparation,
                    expected_evidence_sha256=expected_evidence_sha256,
                    expected_supervision_sha256=expected_supervision_sha256,
                )
            except Exception:
                self._view["publication"] = {
                    "status": "HISTORICAL_HELD",
                    "operation_id": None,
                }
                raise
            self._pending_observation_ready = True

            self._pending_observation_action = "physical_camera_probe"

    def stage_retained_capture(
        self,
        evidence: Any,
        *,
        expected_preparation: Any,
        expected_evidence_sha256: str,
        expected_settings_epoch: str,
        cancellation: threading.Event,
        deadline_ns: int,
        expected_supervision_sha256: str | None = None,
        configuration_verification: bool = False,
        capture_reference_request_key: str | None = None,
        capture_checksum: CameraCaptureChecksum | None = None,
    ) -> Any:
        """Verify/retain original pixels without re-running the native campaign.

        Called after a separately admitted finite capture has stopped. The
        explicit retention deadline cannot extend or redeem its device permit.
        Partial files and failed readback stay diagnostic, never current media.
        """
        if type(configuration_verification) is not bool:
            raise WizardError(
                "CAMERA_CAPTURE_PROFILE", "An exact capture profile is required."
            )
        with self._lock:
            if self._capture_workflow is None or self._pending_workflow is not None:
                raise WizardError(
                    "CAMERA_CAPTURE_CONTEXT",
                    "A current staged configuration is required.",
                )
            candidate = self._capture_workflow.staged_copy()
            self._pending_workflow = candidate
            self._pending_observation_context = self.configuration_context_sha256()
            self._pending_observation_ready = False
            self._view["last_frame"] = None
            self._view["publication"] = {"status": "PENDING", "operation_id": None}
        # File ingestion can take time: never hold the UI/status lock while it
        # streams the retained dataset. Stop remains responsive at the caller.
        result = candidate.accept_capture(
            evidence,
            expected_preparation=expected_preparation,
            expected_evidence_sha256=expected_evidence_sha256,
            expected_settings_epoch=expected_settings_epoch,
            cancellation=cancellation,
            deadline_ns=deadline_ns,
            expected_supervision_sha256=expected_supervision_sha256,
            configuration_verification=configuration_verification,
            capture_reference_request_key=capture_reference_request_key,
            capture_checksum=capture_checksum,
        )
        with self._lock:
            if (
                cancellation.is_set()
                or self._pending_workflow is not candidate
                or self._view["publication"]["status"] != "PENDING"
                or self._pending_observation_context
                != self.configuration_context_sha256()
            ):
                raise WizardError(
                    "CAMERA_CAPTURE_CONTEXT",
                    "Capture data context changed before publication.",
                )
            self._pending_observation_ready = True
            self._pending_observation_action = (
                CONFIGURATION_CAPTURE_PUBLIC_ACTION_ID
                if configuration_verification
                else "physical_camera_capture"
            )
        return result

    def publish_retained_observation(self, operation_id: str) -> None:
        """Final internal handoff, after exact result retention/completion log.

        This method cannot issue a permit or pass a physical stage. The main
        wizard has no probe/capture dispatcher calling it until release wiring
        is complete; tests inject modeled records only at this internal seam.
        """
        with self._lock:
            if (
                self._pending_workflow is None
                or self._pending_configuration_result is not None
                or self._view["publication"]["status"] != "PENDING"
                or not self._pending_observation_ready
                or self._pending_observation_context
                != self.configuration_context_sha256()
            ):
                raise WizardError(
                    "CAMERA_OBSERVATION_PUBLICATION", "No pending native data handoff."
                )
            if (
                not isinstance(operation_id, str)
                or re.fullmatch(r"operation-[0-9a-f]{32}", operation_id) is None
            ):
                raise WizardError(
                    "CAMERA_OBSERVATION_PUBLICATION", "Exact operation ID required."
                )
            self._capture_workflow = self._pending_workflow
            self._pending_workflow = None
            self._pending_observation_context = None
            self._pending_observation_ready = False
            self._pending_observation_action = None
            self._workflow_projection()
            self._view["publication"] = {
                "status": "CURRENT",
                "operation_id": operation_id,
            }

    def operating_proposal_configuration(self) -> bytes:
        """Exact cached settings for a diagnostic draft, never device admission."""
        with self._lock:
            self.configuration_capture_context()
            assert self._capture_workflow is not None
            assert self._capture_workflow._configuration is not None
            return self._capture_workflow._configuration.payload

    def configuration_capture_context(self) -> dict[str, Any]:
        """Stable cached intent for a logged settings reference, not admission.

        Successful captures change workflow status and the last image. Those
        must not rewrite which original capabilities/settings were selected.
        This excludes transient publication state; idle availability and the
        active-operation guard check that state at their distinct boundaries.
        """
        with self._lock:
            workflow = self._capture_workflow
            if (
                self.mode != "physical"
                or workflow is None
                or not workflow._activation
                or workflow.view()["status"] == "HELD"
                or workflow._capabilities is None
                or workflow._configuration is None
                or self._view["reviewed_endpoint"] is None
            ):
                raise WizardError(
                    "CAMERA_CONFIGURATION_INTENT_REQUIRED",
                    "Current original native capabilities and explicit settings are required.",
                )
            from dataclasses import asdict

            configuration = workflow._configuration
            return dict(
                source_sha256=self.source_sha256,
                session_id=self.session_id,
                cell_id=self.cell_id,
                directory=str(self.directory),
                origin_launch_id=self.origin_launch_id,
                probe_runtime_sha256=self.probe_runtime.registration_sha256,
                capture_runtime_sha256=self.capture_runtime.registration_sha256,
                endpoint=deepcopy(self._view["reviewed_endpoint"]),
                capabilities_sha256=workflow._capabilities.capabilities_sha256,
                probe_attempt_id=workflow._capabilities.to_dict()["binding"][
                    "attempt_id"
                ],
                settings_epoch=configuration.settings_epoch,
                settings_sha256=digest(configuration.payload),
                capture_budget=asdict(configuration_capture_budget(configuration)),
                physical_authority=False,
                hardware_qualified=False,
            )

    def withdraw_capture_preview(self, expected_intent: dict[str, Any]) -> None:
        """Retire the image before queue logging, preserving exact settings.

        CURRENT still describes the logged settings, not a live connection. Do
        not change workflow/permit inputs or leave an evicted image reference.
        """
        with self._lock:
            if self.configuration_capture_context() != expected_intent:
                raise WizardError(
                    "CAMERA_CONFIGURATION_INTENT_CHANGED",
                    "The current capture intent changed before queueing.",
                )
            self._view["last_frame"] = None
            self._view["status"] = "CONFIGURATION_STAGED"

    def configuration_context_sha256(self) -> str:
        with self._lock:
            return digest(
                canonical(
                    {
                        "source": self.source_sha256,
                        "session": self.session_id,
                        "cell": self.cell_id,
                        "directory": str(self.directory),
                        "origin": self.origin_launch_id,
                        "probe_runtime": self.probe_runtime.registration_sha256,
                        "capture_runtime": self.capture_runtime.registration_sha256,
                        "endpoint": self._view["reviewed_endpoint"],
                        "workflow": (
                            None
                            if self._capture_workflow is None
                            else self._capture_workflow.view()
                        ),
                    }
                )
            )

    def configuration_blocked_reason(self) -> str | None:
        with self._lock:
            if (
                self._capture_workflow is None
                or self._capture_workflow.view()["status"] == "HELD"
            ):
                return "An exact retained native probe is required before staging physical camera settings; metadata inventory is not a probe."
            if self._pending_workflow is not None:
                return (
                    "A camera data publication is pending; finish or inspect it first."
                )
            return None

    def begin_configuration_action(self, expected_context_sha256: str) -> None:
        """Retire the prior image before intent logging or queued execution."""
        with self._lock:
            if (
                self.configuration_blocked_reason()
                or expected_context_sha256 != self.configuration_context_sha256()
            ):
                raise WizardError(
                    "CAMERA_CONFIGURATION_CONTEXT",
                    "The retained probe/settings context changed before execution.",
                )
            # Preserve immutable probe/settings for the ticket, but do not leave
            # a CURRENT last_frame pointing to already-evicted image bytes.
            self._view.update(
                status="HELD",
                last_frame=None,
                plan=None,
                publication={"status": "PENDING", "operation_id": None},
            )

    def configuration_fields(self) -> tuple[dict[str, Any], ...]:
        """Build only reported choices. No guessed modes, autofocus or defaults."""
        from .camera_operating_mode_guidance import mode_choice_label
        from rocell.providers.windows.camera_worker_client import NativeCameraMode

        with self._lock:
            config = (
                None
                if self._capture_workflow is None
                else self._capture_workflow.view()["configuration"]
            )
            caps = None if config is None else config["capabilities"]
            fields: list[dict[str, Any]] = [
                {
                    "name": "mode_choice_id",
                    "label": "Explicitly select a reported native mode",
                    "type": "select",
                    "required": True,
                    "options": [
                        {
                            "value": row["choice_id"],
                            "label": (
                                f"{row['mode']['width']} × {row['mode']['height']} "
                                f"{row['mode']['fps_numerator']}/{row['mode']['fps_denominator']} fps "
                                f"{row['mode']['subtype']} — native reported, unqualified; "
                                f"{mode_choice_label(NativeCameraMode(**row['mode']))}"
                            ),
                        }
                        for row in ([] if caps is None else caps["modes"])
                        if row["selectable"]
                    ],
                }
            ]
            for control in ([] if caps is None else caps["controls"]):
                cid = control["control_id"]
                fields.extend(
                    (
                        {
                            "name": cid + "_mode",
                            "label": cid + " control intent",
                            "type": "select",
                            "required": True,
                            "default": "unchanged",
                            "options": [
                                {
                                    "value": "unchanged",
                                    "label": "Do not request a change",
                                }
                            ]
                            + [
                                {"value": name, "label": name}
                                for flag, name in ((2, "manual"), (1, "auto"))
                                if control["capability_flags"] & flag
                            ],
                        },
                        {
                            "name": cid + "_value",
                            "label": f"{cid} ({control['unit']}; used only if changed)",
                            "type": "number",
                            "required": True,
                            "default": control["value"],
                            "min": control["minimum"],
                            "max": control["maximum"],
                            "step": control["step"],
                        },
                    )
                )
            fields.append(
                {
                    "name": "operator_id",
                    "label": "Settings operator label",
                    "type": "text",
                    "required": True,
                    "max_length": 64,
                }
            )
            return tuple(deepcopy(fields))

    def stage_configuration(
        self,
        values: dict[str, Any],
        *,
        expected_context_sha256: str,
        cancellation: threading.Event,
    ) -> dict[str, Any]:
        from .wizard_actions import ActionDefinition, validate_action_input
        from rocell.providers.windows.camera_worker_client import CameraControlSetting

        with self._lock:
            if (
                self.configuration_blocked_reason()
                or cancellation.is_set()
                or expected_context_sha256 != self.configuration_context_sha256()
            ):
                raise WizardError(
                    "CAMERA_CONFIGURATION_CONTEXT",
                    "The retained probe/settings context changed or was stopped.",
                )
            public = validate_action_input(
                ActionDefinition(
                    "physical_camera_configuration",
                    "Stage native settings",
                    "camera",
                    "",
                    "physical_camera_configuration",
                    fields=self.configuration_fields(),
                ),
                values,
            )
            # Shared input validation enforces the existing portable operator
            # ID rule at both ticket preview and this execution boundary.
            assert self._capture_workflow is not None
            candidate = self._capture_workflow.staged_copy()
            caps = candidate.view()["configuration"]["capabilities"]
            controls = []
            for control in caps["controls"]:
                cid = control["control_id"]
                mode, value = public[cid + "_mode"], public[cid + "_value"]
                if type(value) is not int:
                    raise WizardError(
                        "CAMERA_CONFIGURATION_INTEGER",
                        "Controls use integer native driver units.",
                    )
                if mode != "unchanged":
                    controls.append(CameraControlSetting(cid, value, mode))
            staged = candidate.stage_settings(
                public["mode_choice_id"],
                tuple(controls),
                expected_capabilities_sha256=caps["capabilities_sha256"],
            )
            result = {
                "schema": "rocell.wizard_worker_result.v1",
                "action_id": "physical_camera_configuration",
                "status": "SUCCEEDED",
                "steps": [
                    {
                        "name": "physical_camera_configuration",
                        "exit_code": 0,
                        "report": {
                            "configuration": staged.to_dict(),
                            "settings_epoch": staged.settings_epoch,
                            "operator_id": public["operator_id"],
                            "applied": False,
                            "meaning": "Exact reported mode and electronic intent staged; no settings applied, capture dispatched or physical stage passed.",
                        },
                    }
                ],
                "device_open_count": 0,
                "serial_write_count": 0,
                "power_event_count": 0,
                "motion_command_count": 0,
                "contact_command_count": 0,
                "metadata_inventory_performed": False,
                "physical_authority": False,
            }
            if cancellation.is_set():
                raise WizardError(
                    "CAMERA_CONFIGURATION_CANCELLED",
                    "Settings staging stopped before publication.",
                )
            self._pending_configuration_context = expected_context_sha256
            self._pending_observation_context = expected_context_sha256
            self._pending_observation_ready = True
            self._pending_configuration_result = canonical(result)
            self._pending_workflow = candidate
            self._view["last_frame"] = None
            self._view["publication"] = {"status": "PENDING", "operation_id": None}
            return result

    def validate_configuration_publication(self, result: dict[str, Any]) -> None:
        with self._lock:
            if (
                self._pending_workflow is None
                or self._pending_configuration_result != canonical(result)
                or self._pending_configuration_context
                != self.configuration_context_sha256()
            ):
                raise WizardError(
                    "CAMERA_CONFIGURATION_PUBLICATION",
                    "Exact staged settings or retained context changed.",
                )

    def publish_configuration(self, operation_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            self.validate_configuration_publication(result)
            self._pending_configuration_result = None
            self._pending_configuration_context = None
            self.publish_retained_observation(operation_id)

    def original_probe_progress(self) -> dict[str, Any]:
        """Small cached status; polling never copies native pipe originals."""
        with self._lock:
            return dict(
                attempted=self._original_probe_attempted,
                status=(self._original_probe_diagnostics or {}).get(
                    "status", "NOT_ATTEMPTED"
                ),
                failed_phase=(self._original_probe_diagnostics or {}).get(
                    "failed_phase"
                ),
            )

    def retained_probe_diagnostics(self) -> dict[str, Any]:
        """Only the original probe packet; later capture data cannot replace it."""
        with self._lock:
            return dict(
                admission=deepcopy(self._original_probe_diagnostics),
                dispatch=deepcopy(self._original_probe_dispatch),
            )

    def retained_configuration_diagnostics(self) -> dict[str, Any]:
        """Last explicit settings capture, including partial/unknown outcomes."""
        with self._lock:
            return dict(
                admission=deepcopy(self._original_configuration_diagnostics),
                dispatch=deepcopy(self._original_configuration_dispatch),
            )

    def retained_capture_diagnostics(self) -> dict[str, Any] | None:
        with self._lock:
            # Keep both prior and pending bytes if a later publication fails.
            if (
                self._capture_workflow is None
                and self._pending_workflow is None
                and self._dispatch_owner is None
                and self._original_probe_diagnostics is None
            ):
                return None
            diagnostics = {
                "current": (
                    None
                    if self._capture_workflow is None
                    else self._capture_workflow.retained_diagnostics()
                ),
                "pending": (
                    None
                    if self._pending_workflow is None
                    else self._pending_workflow.retained_diagnostics()
                ),
            }
            if self._dispatch_owner is not None:
                diagnostics["dispatch"] = self._dispatch_owner.retained_diagnostics()
            if self._original_probe_diagnostics is not None:
                diagnostics["original_probe"] = deepcopy(
                    self._original_probe_diagnostics
                )
            return diagnostics

    def pending_observation_result(self, action_id: str) -> dict[str, Any]:
        """Exact bounded diagnostic result for the future admitted dispatcher.

        Original native evidence must already have been retained by that
        dispatcher. This result binds its full cached diagnostic chain; it is
        not a replacement for the M1 receipt or a way to authorize hardware.
        """
        with self._lock:
            if (
                action_id
                not in {
                    "physical_camera_probe",
                    "physical_camera_capture",
                    CONFIGURATION_CAPTURE_PUBLIC_ACTION_ID,
                }
                or action_id != self._pending_observation_action
                or self._pending_workflow is None
                or not self._pending_observation_ready
                or self._view["publication"]["status"] != "PENDING"
            ):
                raise WizardError(
                    "CAMERA_OBSERVATION_PENDING",
                    "No completed pending native data result.",
                )
            observed = self._pending_workflow.view()
            expected_status = (
                "PROBE_ACCEPTED"
                if action_id == "physical_camera_probe"
                else "CONTENT_VERIFIED"
            )
            if observed["status"] != expected_status:
                raise WizardError(
                    "CAMERA_OBSERVATION_INCOMPLETE",
                    "Native observation or pixels did not complete.",
                )
            return {
                "schema": "rocell.wizard_retained_native_camera_data.v1",
                "action_id": action_id,
                "status": "SUCCEEDED",
                "steps": [
                    {
                        "name": "retained_native_camera_data",
                        "exit_code": 0,
                        "report": {
                            "source_sha256": self.source_sha256,
                            "session_id": self.session_id,
                            "workflow_sha256": digest(
                                canonical(self._pending_workflow.retained_diagnostics())
                            ),
                            "configuration": observed["configuration"],
                            "last_frame": observed["last_frame"],
                            "meaning": "Retained data and content verification only; no current connection, physical-stage acceptance, native release or power-off inferred.",
                        },
                    }
                ],
                "physical_authority": False,
            }

    def validate_observation_publication(
        self, action_id: str, result: dict[str, Any]
    ) -> None:
        with self._lock:
            if canonical(result) != canonical(
                self.pending_observation_result(action_id)
            ):
                raise WizardError(
                    "CAMERA_OBSERVATION_RESULT",
                    "Logged native observation differs from pending original data.",
                )

    def cache_published_preview(self, image_id: str) -> bytes | None:
        """Attach one server-generated opaque ID to verified, already published bytes."""
        with self._lock:
            if (
                self._capture_workflow is None
                or self._view["status"] != "CONTENT_VERIFIED"
                or self._view["publication"]["status"] != "CURRENT"
            ):
                return None
            preview = self._capture_workflow.last_preview()
            frame = self._view["last_frame"]
            if (
                type(image_id) is not str
                or re.fullmatch(r"image-[0-9a-f]{32}", image_id) is None
                or preview is None
                or frame is None
                or digest(preview.png_bytes) != frame["preview_sha256"]
            ):
                raise WizardError(
                    "CAMERA_PREVIEW_BINDING",
                    "Exact retained preview and opaque image ID required.",
                )
            self._view["last_frame"] = {**frame, "image_id": image_id}
            return preview.png_bytes

    def runtime_view(self) -> dict[str, Any]:
        """Cached, detached file observations; no filesystem or native calls."""
        with self._lock:
            publication = self._runtime_publication
            current = publication["status"] == "CURRENT"
            inspection = self._runtime_inspection
            status = (
                "HISTORICAL_HELD"
                if publication["status"] == "HISTORICAL_HELD"
                else (
                    "NOT_INSPECTED"
                    if inspection is None
                    else (
                        "REVIEW_RECORDED"
                        if current and self._runtime_review is not None
                        else "INSPECTION_RETAINED"
                    )
                )
            )
            return deepcopy(
                {
                    "schema": RUNTIME_VIEW_SCHEMA,
                    "status": status,
                    "inspection": (
                        None if inspection is None else inspection.safe_summary()
                    ),
                    "review": (
                        None
                        if publication["status"] == "PENDING"
                        else self._runtime_review
                    ),
                    "publication": publication,
                    "dispatch_enabled": False,
                    "driver_qualified": False,
                    "hardware_qualified": False,
                    "connected": False,
                    "physical_authority": False,
                    "meaning": RUNTIME_MEANING,
                }
            )

    def runtime_context_sha256(self) -> str:
        """Bind the candidate pair and original report, not caller-supplied pins."""
        with self._lock:
            return digest(
                canonical(
                    {
                        "source_sha256": self.source_sha256,
                        "launch_session_id": self.launch_id,
                        "probe": self.probe_runtime.to_dict(),
                        "capture": self.capture_runtime.to_dict(),
                        "inspection_sha256": (
                            None
                            if self._runtime_inspection is None
                            else self._runtime_inspection.sha256
                        ),
                        "review": self._runtime_review,
                    }
                )
            )

    def runtime_blocked_reason(self, action_id: str) -> str | None:
        with self._lock:
            if self.mode != "physical":
                return "Installed runtime inspection requires physical mode; it opens no device."
            if action_id not in RUNTIME_ACTIONS:
                return "Unknown runtime file action."
            if action_id == "physical_camera_runtime_review":
                if (
                    self._runtime_inspection is None
                    or self._runtime_publication["status"] != "CURRENT"
                ):
                    return "Explicitly inspect and publish the fixed runtime pair before reviewing its exact report."
                if self._runtime_review is not None:
                    return "This report already has a recorded review. Export it or explicitly inspect again; no review is replayed."
            return None

    def begin_runtime_action(
        self, action_id: str, expected_context_sha256: str
    ) -> None:
        """Retire current review before intent logging or explicit file access."""
        with self._lock:
            reason = self.runtime_blocked_reason(action_id)
            if reason or expected_context_sha256 != self.runtime_context_sha256():
                raise WizardError(
                    "CAMERA_RUNTIME_CONTEXT_CHANGED",
                    reason or "Runtime report or candidates changed.",
                )
            self._runtime_pending_action = action_id
            self._runtime_pending_context = expected_context_sha256
            self._runtime_pending_review = None
            self._runtime_pending_operation = None
            self._runtime_publication_context = None
            self._runtime_publication = {"status": "PENDING", "operation_id": None}

    def invalidate_runtime(self) -> None:
        """Keep historical evidence; do not turn failed logging into a review."""
        with self._lock:
            self._runtime_publication = {
                "status": "HISTORICAL_HELD",
                "operation_id": None,
            }
            self._runtime_pending_review = None
            self._runtime_pending_action = None
            self._runtime_pending_context = None
            self._runtime_pending_operation = None
            self._runtime_publication_context = None

    def _verify_runtime_inspection(self, value: Any) -> PhysicalCameraRuntimeInspection:
        payload = (
            value.payload
            if type(value) is PhysicalCameraRuntimeInspection
            else canonical(value)
        )
        return verify_physical_camera_runtime_inspection(
            payload,
            expected_source_sha256=self.source_sha256,
            expected_launch_session_id=self.launch_id,
            expected_probe_candidate=self.probe_runtime,
            expected_capture_candidate=self.capture_runtime,
            expected_report_sha256=digest(payload),
        )

    def perform_runtime_action(
        self,
        action_id: str,
        *,
        expected_context_sha256: str,
        actor_id: str,
        operation_id: str,
        cancellation: threading.Event,
        progress: Callable[[str], None],
    ) -> dict[str, Any]:
        """Stage real file evidence or a pure review; Arrival owns publication."""
        if (
            type(actor_id) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", actor_id) is None
        ):
            raise WizardError(
                "CAMERA_RUNTIME_ACTOR", "Use a bounded operator/reviewer label."
            )
        if (
            type(operation_id) is not str
            or re.fullmatch(r"operation-[0-9a-f]{32}", operation_id) is None
        ):
            raise WizardError(
                "CAMERA_RUNTIME_OPERATION", "Exact diagnostic operation required."
            )
        with self._lock:
            if cancellation.is_set():
                raise WizardError(
                    "CAMERA_RUNTIME_CANCELLED",
                    "Runtime file action stopped before dispatch.",
                )
            if (
                self._runtime_pending_action != action_id
                or self._runtime_pending_context != expected_context_sha256
                or self.runtime_context_sha256() != expected_context_sha256
            ):
                raise WizardError(
                    "CAMERA_RUNTIME_CONTEXT_CHANGED",
                    "Runtime action context changed or stopped.",
                )
            original = self._runtime_inspection
            probe_candidate, capture_candidate = (
                self.probe_runtime,
                self.capture_runtime,
            )
            self._runtime_pending_operation = operation_id
        if action_id == "physical_camera_runtime_inspect":
            try:
                inspected = inspect_physical_camera_runtime_pair(
                    self.workspace,
                    expected_source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                    operator_id=actor_id,
                    probe_candidate=probe_candidate,
                    capture_candidate=capture_candidate,
                    cancellation=cancellation,
                    progress=progress,
                )
            except PhysicalCameraRuntimeInspectionError as error:
                # A bounded partial may survive Stop or a late check. Its
                # structural validity is separate from successful inspection.
                if error.inspection_report is not None:
                    try:
                        partial = self._verify_runtime_inspection(
                            error.inspection_report
                        )
                    except Exception:
                        partial = None
                    if partial is not None:
                        with self._lock:
                            self._runtime_inspection = partial
                            self._runtime_review = None
                self.invalidate_runtime()
                raise
            inspected = self._verify_runtime_inspection(inspected)
            if inspected.safe_summary()["operator_id"] != actor_id:
                raise WizardError(
                    "CAMERA_RUNTIME_ACTOR_MISMATCH",
                    "Inspection operator differs from the exact action.",
                )
            with self._lock:
                context_current = (
                    self._runtime_pending_action == action_id
                    and self._runtime_pending_context == expected_context_sha256
                    and self.runtime_context_sha256() == expected_context_sha256
                )
                # Preserve returned evidence even when Stop/logging withdrew
                # the pending action during I/O; it must remain historical.
                self._runtime_inspection = inspected
                self._runtime_review = None
                if not context_current:
                    self.invalidate_runtime()
                    raise WizardError(
                        "CAMERA_RUNTIME_CONTEXT_CHANGED",
                        "Runtime context changed during inspection; original report retained as historical.",
                    )
                if inspected.to_dict()["terminal_error"] is not None:
                    self.invalidate_runtime()
                    raise WizardError(
                        "CAMERA_RUNTIME_INCOMPLETE",
                        "A partial inspection is retained only as historical diagnostics.",
                    )
            review = None
        else:
            if original is None:
                raise WizardError(
                    "CAMERA_RUNTIME_REPORT_REQUIRED",
                    "No original inspection is retained.",
                )
            inspected = self._verify_runtime_inspection(original)
            summary = inspected.safe_summary()
            if actor_id.casefold() == summary["operator_id"].casefold():
                raise WizardError(
                    "CAMERA_RUNTIME_DISTINCT_REVIEWER",
                    "Use a reviewer label different from the inspection operator; labels are not authenticated identities.",
                )
            review = {
                "reviewer_id": actor_id,
                "review_operation_id": operation_id,
                "inspection_sha256": inspected.sha256,
                "status": (
                    "ACKNOWLEDGED_FILE_MATCH"
                    if summary["status"] == "FILES_MATCHED"
                    else "ACKNOWLEDGED_HELD_REPORT"
                ),
                "distinct_operator_labels": True,
            }
            with self._lock:
                if (
                    self._runtime_pending_action != action_id
                    or self.runtime_context_sha256() != expected_context_sha256
                ):
                    self.invalidate_runtime()
                    raise WizardError(
                        "CAMERA_RUNTIME_CONTEXT_CHANGED",
                        "Runtime context changed during review.",
                    )
                self._runtime_pending_review = review
        if cancellation.is_set():
            self.invalidate_runtime()
            raise WizardError(
                "CAMERA_RUNTIME_CANCELLED",
                "Runtime file action stopped; retained observations are historical only.",
            )
        with self._lock:
            if (
                self._runtime_pending_action != action_id
                or self._runtime_pending_operation != operation_id
            ):
                raise WizardError(
                    "CAMERA_RUNTIME_CONTEXT_CHANGED",
                    "Runtime action was withdrawn before result retention.",
                )
            self._runtime_publication_context = self.runtime_context_sha256()
        return {
            "schema": "rocell.wizard_worker_result.v1",
            "action_id": action_id,
            "status": "SUCCEEDED",
            "steps": [
                {
                    "name": "physical_camera_runtime_files",
                    "exit_code": 0,
                    "report": {
                        "inspection": inspected.to_dict(),
                        "inspection_sha256": inspected.sha256,
                        "review": review,
                        "meaning": RUNTIME_MEANING,
                    },
                }
            ],
            "device_open_count": 0,
            "serial_write_count": 0,
            "power_event_count": 0,
            "motion_command_count": 0,
            "contact_command_count": 0,
            "metadata_inventory_performed": False,
            "physical_authority": False,
        }

    def validate_runtime_publication(
        self, operation_id: str, result: dict[str, Any]
    ) -> None:
        """Pure final join of exact staged report, operation and candidate pair."""
        with self._lock:
            if (
                self._runtime_pending_action not in RUNTIME_ACTIONS
                or self._runtime_pending_operation != operation_id
                or self._runtime_inspection is None
                or self._runtime_publication_context != self.runtime_context_sha256()
            ):
                raise WizardError(
                    "CAMERA_RUNTIME_PUBLICATION",
                    "Runtime context changed before publication.",
                )
            self._verify_runtime_inspection(self._runtime_inspection)
            expected = {
                "inspection": self._runtime_inspection.to_dict(),
                "inspection_sha256": self._runtime_inspection.sha256,
                "review": self._runtime_pending_review,
                "meaning": RUNTIME_MEANING,
            }
            if result.get("action_id") != self._runtime_pending_action or result.get(
                "steps"
            ) != [
                {
                    "name": "physical_camera_runtime_files",
                    "exit_code": 0,
                    "report": expected,
                }
            ]:
                raise WizardError(
                    "CAMERA_RUNTIME_RESULT_BINDING",
                    "Retained result differs from the exact staged inspection/review.",
                )

    def publish_runtime_action(self, operation_id: str) -> None:
        """Called only after exact result retention and successful outer logging."""
        with self._lock:
            if (
                self._runtime_pending_action not in RUNTIME_ACTIONS
                or self._runtime_inspection is None
                or self._runtime_pending_operation != operation_id
                or self._runtime_publication_context != self.runtime_context_sha256()
            ):
                raise WizardError(
                    "CAMERA_RUNTIME_PUBLICATION", "No pending exact runtime report."
                )
            self._runtime_review = self._runtime_pending_review
            self._runtime_pending_review = None
            self._runtime_pending_action = None
            self._runtime_pending_context = None
            self._runtime_pending_operation = None
            self._runtime_publication_context = None
            self._runtime_publication = {
                "status": "CURRENT",
                "operation_id": operation_id,
            }

    def retained_runtime_diagnostics(self) -> dict[str, Any] | None:
        with self._lock:
            if self._runtime_inspection is None:
                return None
            return deepcopy(
                {
                    "inspection": self._runtime_inspection.to_dict(),
                    "inspection_sha256": self._runtime_inspection.sha256,
                    "review": self._runtime_review,
                }
            )

    def bind_verified_session(self, session: Any) -> None:
        """Target the original verified camera store, not a replacement launch.

        Only the application calls this after explicit selected-store auditing.
        This changes planning identity, not native registration, admission facts
        or device authority. No previous intent/settings/image is promoted.
        """
        from .physical_camera_session import PhysicalCameraSession

        if type(session) is not PhysicalCameraSession:
            raise WizardError(
                "PHYSICAL_CAMERA_ORIGINAL_SESSION",
                "Exact original camera session required.",
            )
        bound, current = session.descriptor(), session.view()
        if (
            bound["workspace"] != str(self.workspace)
            or bound["source_sha256"] != self.source_sha256
            or current["status"]
            not in {"STORAGE_READY_PENDING", "REFRESHED_STORAGE_ONLY"}
            or current["verification"] is None
            or current["verification"]["session"]["session_id"] != bound["session_id"]
        ):
            raise WizardError(
                "PHYSICAL_CAMERA_ORIGINAL_SESSION",
                "Current original-store verification and matching workspace source required.",
            )
        directory = (
            self.workspace
            / "software/runs/physical-camera-acquisition"
            / bound["launch_id"]
        )
        if str(directory) != bound["directory"]:
            raise WizardError(
                "PHYSICAL_CAMERA_ORIGINAL_SESSION",
                "Assigned original camera directory differs.",
            )
        with self._lock:
            self.invalidate()
            self.directory = directory
            self.cell_id, self.session_id = bound["cell_id"], bound["session_id"]
            self.origin_launch_id = bound["launch_id"]

    def invalidate(self) -> None:
        """Withdraw current intent, preserving only private historical bytes."""
        with self._lock:
            self.invalidate_runtime()
            if self._capture_workflow is not None:
                self._capture_workflow.invalidate()
            if self._pending_workflow is not None:
                self._pending_workflow.invalidate()
            self._pending_observation_ready = False
            self._pending_observation_action = None
            self._view.update(
                status="HELD",
                reviewed_endpoint=None,
                plan=None,
                last_frame=None,
                configuration={
                    "capabilities": None,
                    "candidate": None,
                    "readback": None,
                },
                publication={"status": "HISTORICAL_HELD", "operation_id": None},
                blockers=["ACQUISITION_CONTEXT_INVALIDATED", *BASE_HOLDS],
            )

    def withdraw_plan_publication(self) -> None:
        """A new inert plan retires its display, not retained probe/settings."""
        with self._lock:
            self._view["status"] = "HELD"
            self._view["plan"] = None
            self._view["last_frame"] = None
            self._view["publication"] = {
                "status": "HISTORICAL_HELD",
                "operation_id": None,
            }

    def preview_plan(
        self, operation: str, enrollment: WizardNativeCameraEnrollment
    ) -> dict[str, Any]:
        """Pure detached plan, not state mutation or current-permit issuance."""
        if self.mode != "physical" or operation not in ("probe", "capture"):
            raise WizardError(
                "PHYSICAL_CAMERA_PLAN_SCOPE", "Select a physical camera operation."
            )
        if type(enrollment) is not WizardNativeCameraEnrollment:
            raise WizardError(
                "PHYSICAL_CAMERA_ENROLLMENT", "Exact current enrollment required."
            )
        with self._lock:
            directory, cell_id, session_id, origin = (
                self.directory,
                self.cell_id,
                self.session_id,
                self.origin_launch_id,
            )
        # All hashes and selection facts must come from the same detached
        # snapshot, even if a different caller changes enrollment concurrently.
        enrollment = enrollment.staged_copy()
        snapshot = enrollment.export_snapshot()
        provenance = snapshot["view"]["provenance"]
        if (
            provenance["mode"] != "physical"
            or provenance["source_sha256"] != self.source_sha256
            or provenance["session_id"] != self.launch_id
        ):
            raise WizardError(
                "PHYSICAL_CAMERA_ENROLLMENT",
                "Enrollment source, launch or mode differs.",
            )
        # Missing metadata is an explicit planning hold. Once a binding exists,
        # invalid provenance/hash/source is a rejection, not a silent fallback.
        selection = None
        if enrollment.binding() is not None:
            selection = selection_from_enrollment(
                enrollment,
                source_sha256=self.source_sha256,
                launch_session_id=self.launch_id,
            )
        blockers = list(BASE_HOLDS)
        if selection is None:
            blockers.insert(0, "REVIEWED_PHYSICAL_ENDPOINT_REQUIRED")
        configuration_ready = False
        with self._lock:
            if self._capture_workflow is not None:
                workflow = self._capture_workflow.view()
                configuration_ready = (
                    workflow["status"] in {"SETTINGS_STAGED", "CONTENT_VERIFIED"}
                    and selection is not None
                    and workflow["configuration"]["capabilities"]["binding"][
                        "selected_identity_sha256"
                    ]
                    == selection.sha256
                )
        if operation == "capture" and not configuration_ready:
            blockers.extend(
                (
                    "RETAINED_PHYSICAL_PROBE_REQUIRED",
                    "REVIEWED_PHYSICAL_SETTINGS_REQUIRED",
                )
            )
        campaign_plan = None
        if operation == "probe" and selection is not None:
            from .physical_native_camera_campaign import PhysicalNativeCameraCampaign

            # Compose the real purpose-specific preparation while still pure.
            # The native runner remains independently held. A prepared campaign
            # is not a consumed M1 permit or a substitute for reviewed stages.
            campaign_plan = PhysicalNativeCameraCampaign(
                self.workspace,
                directory,
                source_sha256=self.source_sha256,
                cell_id=cell_id,
                session_id=session_id,
                selection=selection,
                runtime=self.probe_runtime,
            ).plan()
        elif operation == "capture" and configuration_ready:
            from rocell.providers.windows.camera_worker_client import (
                CameraCampaignBudget,
            )

            with self._lock:
                assert self._capture_workflow is not None
                campaign_plan = self._capture_workflow.capture_plan(
                    budget=CameraCampaignBudget(
                        5000, 1, 64 * 1024 * 1024, 64 * 1024 * 1024
                    )
                )
        return {
            "schema": PLAN_SCHEMA,
            "operation": operation,
            "source_sha256": self.source_sha256,
            "launch_session_id": self.launch_id,
            "stage": (
                "camera_mode_controls"
                if operation == "probe"
                else "camera_frame_freshness"
            ),
            "camera_cell_id": cell_id,
            "camera_session_id": session_id,
            "camera_store_origin_launch_id": origin,
            "enrollment_snapshot_sha256": digest(canonical(snapshot)),
            "selected_identity_sha256": None if selection is None else selection.sha256,
            "reviewed_endpoint": (
                None if selection is None else selection.safe_summary()
            ),
            "probe_runtime_sha256": self.probe_runtime.registration_sha256,
            "capture_runtime_sha256": self.capture_runtime.registration_sha256,
            "assigned_parent_directory": str(directory),
            "required_owned_lifetime_ms": 12000 if operation == "probe" else 17000,
            "admission_timeout_ms": 2000 if operation == "probe" else 5000,
            "native_duration_ms": 5000,
            "native_campaign_plan": campaign_plan,
            "native_campaign_plan_sha256": (
                None if campaign_plan is None else digest(canonical(campaign_plan))
            ),
            "blockers": blockers,
            "admitted": False,
            "physical_authority": False,
        }

    def record_plan(
        self,
        operation: str,
        enrollment: WizardNativeCameraEnrollment,
        *,
        expected_plan_sha256: str,
        operator_id: str,
        cancellation: threading.Event,
    ) -> dict[str, Any]:
        if (
            type(operator_id) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", operator_id) is None
            or not isinstance(cancellation, threading.Event)
        ):
            raise WizardError(
                "PHYSICAL_CAMERA_PLAN_INPUT", "Operator and cancellation required."
            )
        plan = self.preview_plan(operation, enrollment)
        encoded = canonical(plan)
        if digest(encoded) != expected_plan_sha256 or cancellation.is_set():
            raise WizardError(
                "PHYSICAL_CAMERA_PLAN_CHANGED",
                "Planning context changed or stopped; no plan was published.",
            )
        with self._lock:
            self._retained_intent = encoded
            self._view.update(
                status="HELD",
                reviewed_endpoint=plan["reviewed_endpoint"],
                plan={
                    "plan_sha256": digest(encoded),
                    "operation": operation,
                    "stage": plan["stage"],
                    "status": "PREPARED_NOT_ADMITTED",
                },
                blockers=plan["blockers"],
                publication={"status": "PENDING", "operation_id": None},
            )
        return {
            "schema": "rocell.wizard_worker_result.v1",
            "action_id": "physical_camera_plan",
            "status": "SUCCEEDED",
            "steps": [
                {
                    "name": "physical_camera_acquisition_intent",
                    "exit_code": 0,
                    "report": {
                        "intent": plan,
                        "intent_sha256": digest(encoded),
                        "operator_id": operator_id,
                        "meaning": "Planning completed; acquisition remains held. No M1 permit or hardware observation was produced.",
                    },
                }
            ],
            "device_open_count": 0,
            "serial_write_count": 0,
            "power_event_count": 0,
            "motion_command_count": 0,
            "contact_command_count": 0,
            "metadata_inventory_performed": False,
            "physical_authority": False,
        }

    def publication_completed(self, operation_id: str) -> None:
        with self._lock:
            if self._view["publication"]["status"] != "PENDING":
                raise WizardError(
                    "PHYSICAL_CAMERA_PUBLICATION", "No pending planning result."
                )
            self._view["publication"] = {
                "status": "CURRENT",
                "operation_id": operation_id,
            }

    def retained_intent(self) -> dict[str, Any] | None:
        import json

        with self._lock:
            return (
                None
                if self._retained_intent is None
                else json.loads(self._retained_intent)
            )
