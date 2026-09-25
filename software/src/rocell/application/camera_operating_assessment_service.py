"""File-only composition of existing session/configuration original readers."""

from threading import Event
from time import monotonic_ns

from .camera_configuration_original_scope import read_camera_configuration_originals
from .camera_operating_original_assessment import assess_original_operating_proposal
from .camera_probe_original_scope import (
    read_camera_probe_originals,
    _leases,
    MAX_CONTEXT_NS,
)
from .commissioning_camera_persistence import M1PhysicalCameraPersistence
from .physical_camera_acquisition_service import PhysicalCameraAcquisitionService
from .physical_camera_session import PhysicalCameraSession
from .physical_camera_configuration import (
    PhysicalCameraCapabilities,
    StagedPhysicalCameraConfiguration,
)
from .wizard_native_camera_enrollment import WizardNativeCameraEnrollment
from .wizard_actions import WizardError
from rocell.providers.windows.camera_worker_client import CameraCampaignBudget
from rocell.providers.windows.native_camera_protocol import canonical, digest


def run_original_operating_assessment(
    service,
    session,
    enrollment,
    *,
    context,
    proposal_payload,
    expected_proposal_sha256,
    capture_request_keys,
    request_key,
    cancellation,
    deadline_ns,
    validate_current_context,
    progress,
    capture_packets=None,
):
    """Reuse ownership and storage; never dispatch, issue a permit or refresh.

    The configuration reader constructs an inert plan to authenticate settings;
    no capture admission or dispatcher is called. A missing open session is held.
    """
    started = monotonic_ns()
    if not (
        type(service) is PhysicalCameraAcquisitionService
        and type(session) is PhysicalCameraSession
        and type(enrollment) is WizardNativeCameraEnrollment
        and type(cancellation) is Event
        and type(deadline_ns) is int
        and started < deadline_ns <= started + MAX_CONTEXT_NS
        and callable(validate_current_context)
        and callable(progress)
    ):
        raise WizardError(
            "OPERATING_ORIGINAL_INPUT",
            "Exact owners and a bounded original-read operation are required.",
        )

    def current():
        if cancellation.is_set() or not started <= monotonic_ns() < deadline_ns:
            raise WizardError(
                "OPERATING_ORIGINAL_INTERRUPTED",
                "Stop or deadline ended the original evidence check.",
            )
        if validate_current_context() is not None:
            raise WizardError(
                "OPERATING_ORIGINAL_CONTEXT", "The current application context changed."
            )
        if cancellation.is_set() or monotonic_ns() >= deadline_ns:
            raise WizardError(
                "OPERATING_ORIGINAL_INTERRUPTED",
                "Original evidence check ended during validation.",
            )

    current()
    if not service._dispatch_lock.acquire(False):
        raise WizardError("CAMERA_DISPATCH_ACTIVE", "A camera operation is active.")
    try:
        with service._lock:
            workflow = service._capture_workflow
            if (
                service.mode != "physical"
                or session is not service._original_probe_session
                or enrollment is not service._original_probe_enrollment
                or workflow is None
                or not workflow._activation
                or workflow._capabilities is None
                or workflow._configuration is None
                or service._pending_workflow is not None
                or service._view["publication"]["status"] != "CURRENT"
            ):
                raise WizardError(
                    "OPERATING_ORIGINAL_OWNERS",
                    "The current original probe, settings, session and enrollment are required.",
                )
            bound = session.descriptor()
            if (
                bound["directory"] != str(service.directory)
                or bound["session_id"] != service.session_id
                or bound["cell_id"] != service.cell_id
                or bound["source_sha256"] != service.source_sha256
            ):
                raise WizardError(
                    "OPERATING_ORIGINAL_STORE",
                    "The original camera store differs from the selected service.",
                )
            capabilities = PhysicalCameraCapabilities(workflow._capabilities.payload)
            configuration = StagedPhysicalCameraConfiguration(
                workflow._configuration.payload
            )
            plan = service.preview_activation_plan(
                "capture",
                enrollment,
                capture_budget=CameraCampaignBudget(
                    **context["intent"]["capture_budget"]
                ),
                configuration_verification=True,
                sealed_configuration_capture=True,
            )
            if digest(canonical(plan)) != context["expected_capture_plan_sha256"]:
                raise WizardError(
                    "OPERATING_ORIGINAL_SETTINGS", "The selected settings plan changed."
                )
        if not session._operation_lock.acquire(False):
            raise WizardError(
                "CAMERA_SETUP_BUSY", "The original camera session is busy."
            )
        try:
            store = session._store
            if type(store) is not M1PhysicalCameraPersistence:
                raise WizardError(
                    "OPERATING_ORIGINAL_REFRESH_REQUIRED",
                    "Verify the existing original store first; no replacement is initialized.",
                )
            current()
            progress(
                "Reading saved setup, probe, settings and selected captures; no camera is opened."
            )
            with store.transaction(
                _leases(bound["cell_id"], bound["session_id"])
            ) as tx:
                expected = context["original_setup"]
                setup = read_camera_probe_originals(
                    tx,
                    workspace=service.workspace,
                    source_sha256=service.source_sha256,
                    launch_session_id=service.launch_id,
                    **{
                        k: expected[k]
                        for k in (
                            "expected_header_sha256",
                            "expected_preparation_sha256",
                            "expected_review_sha256",
                        )
                    },
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
                    expected_plan_sha256=context["expected_capture_plan_sha256"],
                )
                report = assess_original_operating_proposal(
                    original,
                    tx,
                    proposal_payload=proposal_payload,
                    expected_proposal_sha256=expected_proposal_sha256,
                    capture_request_keys=capture_request_keys,
                    capture_packets=capture_packets,
                )
                current()
        finally:
            session._operation_lock.release()
        current()
        return report
    finally:
        service._dispatch_lock.release()
