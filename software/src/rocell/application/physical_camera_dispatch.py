"""One acquisition transaction followed by original-store data handoff.

This is an internal application join, not an HTTP API or native release policy.
The production wrapper accepts the camera-only M1 persistence implementation.
Its reviewed facts and the native runner independently control admission; no
boolean, browser evidence upload or fixture fallback can release that runner.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Protocol, cast

from .cell_commissioning_coordinator import (
    AttemptResult,
    BoundedCommissioningWorker,
    CommissioningPersistence,
    ExactOperationPermit,
    PHYSICAL_CAMERA_COMPOSITION,
    PhysicalCameraAcquisitionCoordinator,
    RegisteredActionRequest,
)
from .commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    physical_camera_source_binding,
)
from .physical_camera_capture_workflow import RETENTION_TIMEOUT_MS
from .physical_native_camera_campaign import (
    PhysicalNativeCameraCampaign,
    verify_physical_native_camera_campaign_evidence,
)
from .physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
    CONFIGURATION_PLAN_SCHEMA,
    SEALED_CONFIGURATION_PLAN_SCHEMA,
    verify_camera_activation_campaign_evidence,
)
from .camera_activation_campaign_contract import camera_activation_execution
from .camera_activation_campaign_evidence import validate_camera_activation_evidence
from .camera_capture_checksum import CameraCaptureChecksum
from .camera_sealed_capture_evidence import SealedCameraCaptureEvidence
from .camera_sealed_capture_contract import sealed_capture_execution
from rocell.providers.windows.owned_worker_process import decode_owned_json
from .physical_onboarding_attempts import AttemptState
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .wizard_diagnostic_coordinator import source_fingerprint
from .wizard_native_camera_enrollment import WizardNativeCameraEnrollment
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
)


class PhysicalCameraDispatchError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self._diagnostic = deepcopy(diagnostic)
        super().__init__(code if message is None else f"{code}: {message}")

    @property
    def diagnostic(self) -> dict[str, Any] | None:
        """Detached historical summary, never a permit or raw native payload."""
        return deepcopy(self._diagnostic)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PhysicalCameraDispatchError(code)


class _ObservationSink(Protocol):
    """Existing staged-data APIs. None publishes an image or approves a stage."""

    def accept_retained_probe(
        self,
        enrollment: WizardNativeCameraEnrollment,
        evidence: Any,
        *,
        expected_preparation: Any,
        expected_evidence_sha256: str,
        expected_supervision_sha256: str | None = None,
    ) -> None: ...
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
    ) -> Any: ...
    def pending_observation_result(self, action_id: str) -> dict[str, Any]: ...
    def invalidate(self) -> None: ...


class _CameraDispatchTransaction:
    """Shared algorithm; protocol doubles belong only in the test suite.

    The one-use guard is acquired before any source or persistence read. An
    interrupted or failed invocation is never replayed by this object. The core
    additionally binds the request key in the original cell-global journal.
    """

    def __init__(
        self,
        persistence: CommissioningPersistence,
        campaign: PhysicalNativeCameraCampaign | PhysicalCameraActivationCampaign,
        *,
        revalidate_context: Callable[[], None] | None = None,
    ) -> None:
        _require(
            type(campaign)
            in (PhysicalNativeCameraCampaign, PhysicalCameraActivationCampaign),
            "EXACT_CAMERA_CAMPAIGN_REQUIRED",
        )
        _require(
            persistence.composition == PHYSICAL_CAMERA_COMPOSITION,
            "CAMERA_PERSISTENCE_DOMAIN_REQUIRED",
        )
        # Restoration is pure and detaches every mutable caller container.
        self._activation = type(campaign) is PhysicalCameraActivationCampaign
        _require(
            not self._activation or callable(revalidate_context),
            "ORIGINAL_ACTIVATION_CONTEXT_REQUIRED",
        )
        self._campaign = type(campaign).from_plan(campaign.plan())
        self._context_guard = revalidate_context
        if revalidate_context is not None:
            self._campaign._bind_application_guard(revalidate_context)
        self._plan = self._campaign.plan()
        self._operation = self._plan["purpose" if self._activation else "operation"]
        self._persistence = persistence
        registration = self._campaign.registration()
        self._core = PhysicalCameraAcquisitionCoordinator(
            persistence=persistence,
            registrations=(registration,),
            workers={
                registration.worker_id: cast(BoundedCommissioningWorker, self._campaign)
            },
            retained_campaign_actions=(registration.action_id,),
            scoped_campaign_actions=(registration.action_id,),
        )
        self._leases = (
            LeaseSpec(LeaseLevel.CELL, self._plan["cell_id"]),
            LeaseSpec(LeaseLevel.SESSION, self._plan["session_id"]),
            LeaseSpec(LeaseLevel.CAMERA, self._plan["cell_id"]),
        )
        self._lock = threading.RLock()
        self._used = False
        self._permit: ExactOperationPermit | None = None
        self._result: AttemptResult | None = None
        self._phase = "NOT_STARTED"
        self._historical_evidence: dict[str, Any] | None = None
        self._historical_admission: dict[str, Any] | None = None
        self._capture_checksum: CameraCaptureChecksum | None = None
        self._readback_scope = "NOT_READ"

    def view(self) -> dict[str, Any]:
        """Cached bounded status; no original-store read or device inventory."""
        with self._lock:
            return {
                "operation": self._operation,
                "phase": self._phase,
                "used": self._used,
                "attempt_id": None if self._permit is None else self._permit.attempt_id,
                "attempt_state": (
                    None if self._result is None else self._result.state.value
                ),
                "campaign_sha256": digest(canonical(self._plan)),
                "physical_authority": False,
                "automatic_replay": False,
                "reason_codes": (
                    [] if self._result is None else list(self._result.reason_codes)
                ),
            }

    def retained_diagnostics(self) -> dict[str, Any]:
        """Audited historical native diagnostics, never a substitute for M1."""
        import copy

        with self._lock:
            result = {
                "transaction": self.view(),
                "original_evidence": copy.deepcopy(self._historical_evidence),
                "readback_scope": self._readback_scope,
            }
            if self._historical_admission is not None:
                result["original_admission"] = copy.deepcopy(self._historical_admission)
            return result

    def _phase_is(self, value: str) -> None:
        with self._lock:
            self._phase = value

    def _uncertain_attempt_error(
        self, result: AttemptResult
    ) -> PhysicalCameraDispatchError:
        """Explain only the already-read original after successful lease exit.

        Keep the stable dispatch code, but distinguish an uncertain retained
        attempt from a missing attempt. Never infer source activation or release
        delivery from a constructed wire buffer or unavailable native accounting.
        Readback/lease failures occur before this method and keep their own error.
        """
        assert self._permit is not None and self._readback_scope == "EXITED"
        evidence = self._historical_evidence
        supervision = (
            evidence["supervision"] if self._activation and evidence is not None else {}
        )
        primary = supervision.get("primary_error")
        # This is a bounded presentation of verified retained supervision, not
        # arbitrary exception text or a new native receipt decoder.
        primary = (
            primary
            if type(primary) is str
            and re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", primary) is not None
            else None
        )
        release_check = supervision.get("release_check_passed")
        diagnostic = dict(
            schema="rocell.camera_attempt_failure_summary.v1",
            attempt_id=self._permit.attempt_id,
            attempt_state=result.state.value,
            operation=self._operation,
            readback_scope=self._readback_scope,
            reported_primary_error=primary,
            release_check_passed=(
                release_check if type(release_check) is bool else None
            ),
            native_accounting_available=result.receipt is not None,
            quarantine_latched=result.quarantine_latched,
            automatic_replay=False,
            physical_authority=False,
            hardware_qualified=False,
            meaning="Summary of retained original readback, not a new observation or permission. Missing accounting is unknown, not zero effects; a passed release check alone does not prove delivery.",
        )
        message = "The retained camera attempt has an uncertain outcome. "
        if self._capture_checksum is not None:
            diagnostic.update(
                schema="rocell.camera_attempt_failure_summary.v2",
                capture_checksum_status=self._capture_checksum.to_dict()["status"],
            )
            message += f"Post-cleanup pixel verification: {diagnostic['capture_checksum_status']}. "
        if primary == "ADMISSION_DEADLINE_EXPIRED":
            message += (
                "Native supervision reported ADMISSION_DEADLINE_EXPIRED while "
                "checking camera-startup prerequisites. "
            )
        elif primary is not None:
            message += f"Native supervision reported {primary}. "
        else:
            message += "No primary supervision cause is available in this summary. "
        if result.receipt is None:
            message += (
                "Native effect accounting is unavailable; do not infer zero effects. "
            )
        message += (
            "Export the exact attempt for review; do not replay it or bypass its hold."
        )
        return PhysicalCameraDispatchError(
            "CAMERA_ATTEMPT_NOT_KNOWN", message=message, diagnostic=diagnostic
        )

    def _read_activation_original(self, transaction, permit, result):
        """Read both original v2 roles before rejecting unknown/failed outcomes."""
        _require(
            type(self._campaign) is PhysicalCameraActivationCampaign,
            "EXACT_ACTIVATION_CAMPAIGN",
        )
        assert type(self._campaign) is PhysicalCameraActivationCampaign
        if (
            type(self._persistence) is M1PhysicalCameraPersistence
            and self._persistence.requires_original_admission_evidence
        ):
            original_admission = transaction.read_campaign_admission_evidence(
                permit.attempt_id
            )
            with self._lock:
                self._historical_admission = original_admission
        artifacts = transaction.read_camera_activation_evidence(permit.attempt_id)
        verify_camera_activation_campaign_evidence(
            artifacts, campaign=self._campaign, expected_permit=permit
        )
        sealed = self._plan["schema"] == SEALED_CONFIGURATION_PLAN_SCHEMA
        if sealed:
            _require(
                type(artifacts) is SealedCameraCaptureEvidence,
                "EXACT_ORIGINAL_SEALED_CAPTURE",
            )
            checked = validate_camera_activation_evidence(artifacts.native)
            expected = sealed_capture_execution(
                permit,
                artifacts,
                expected_deadline_ns=checked.run.to_dict()["parent_deadline_ns"],
            )
            checksum = artifacts.checksum
            native = artifacts.native
        else:
            checked = validate_camera_activation_evidence(artifacts)
            expected = camera_activation_execution(
                permit,
                artifacts,
                expected_deadline_ns=checked.run.to_dict()["parent_deadline_ns"],
            )
            checksum, native = None, artifacts
        _require(
            result.receipt == expected.receipt,
            "ORIGINAL_ACTIVATION_ACCOUNTING_MISMATCH",
        )
        with self._lock:
            self._historical_evidence = {
                "schema": (
                    "rocell.camera_activation_observation_with_checksum.v1"
                    if sealed
                    else "rocell.camera_activation_observation_pair.v2"
                ),
                "run": checked.run.to_dict(),
                "supervision": decode_owned_json(
                    checked.supervision_payload, maximum=1024 * 1024
                ),
            }
            if checksum is not None:
                self._historical_evidence.update(
                    capture_checksum=checksum.to_dict(),
                    capture_checksum_sha256=checksum.sha256,
                )
            self._capture_checksum = checksum
            self._readback_scope = "VERIFIED_BYTES_EXIT_PENDING"
        if result.state is AttemptState.SEALED_KNOWN:
            _require(
                checked.run.assessment().status == "SUCCEEDED_NATIVE_DIAGNOSTIC"
                and expected.receipt is not None
                and (
                    checksum is None
                    or checksum.to_dict()["status"] == "CAPTURE_BYTES_HASHED"
                ),
                "COMPLETE_ACTIVATION_RESULT_REQUIRED",
            )
        # Only the unchanged native pair enters existing native codecs. The
        # additional subject remains separately bound by the original receipt.
        return native

    def _current(
        self, cancellation: threading.Event, *, check_context: bool = True
    ) -> None:
        _require(not cancellation.is_set(), "CAMERA_DISPATCH_CANCELLED")
        if check_context and self._context_guard is not None:
            _require(
                self._context_guard() is None,
                "APPLICATION_GUARD_MUST_NOT_GRANT_AUTHORITY",
            )
        _require(
            source_fingerprint(Path(self._plan["workspace"]))
            == self._plan["source_sha256"],
            "CAMERA_DISPATCH_SOURCE_CHANGED",
        )
        if check_context and self._context_guard is not None:
            _require(
                self._context_guard() is None,
                "APPLICATION_GUARD_MUST_NOT_GRANT_AUTHORITY",
            )
        _require(not cancellation.is_set(), "CAMERA_DISPATCH_CANCELLED")

    def perform(
        self,
        *,
        request_key: str,
        sink: _ObservationSink,
        enrollment: WizardNativeCameraEnrollment,
        cancellation: threading.Event,
        settings_epoch: str | None = None,
    ) -> dict[str, Any]:
        """Execute once, read back the sealed original, then stage its data.

        The sink must belong to this campaign's application context; the public
        acquisition service performs that check before constructing this owner.
        No returned result is current until the outer completion log succeeds.
        """
        _require(isinstance(cancellation, threading.Event), "CANCELLATION_REQUIRED")
        capture = self._operation == "capture"
        _require(
            (
                (
                    type(settings_epoch) is str
                    and re.fullmatch(r"[0-9a-f]{64}", settings_epoch) is not None
                )
                if capture
                else settings_epoch is None
            ),
            "EXACT_CAPTURE_SETTINGS_EPOCH_REQUIRED",
        )
        with self._lock:
            _require(not self._used, "CAMERA_DISPATCH_ALREADY_USED")
            self._used = True
            self._phase = "CHECKING_ADMISSION"
        try:
            self._current(cancellation)
            # A placeholder challenge is used only to ask for the current facts;
            # it never reaches prepare/execute. Those reread admission under
            # their own scopes and reject any intervening head/epoch change.
            request = RegisteredActionRequest(
                self._plan["cell_id"],
                self._plan["session_id"],
                self._campaign.registration().action_id,
                request_key,
                digest(canonical(self._plan)),
            )
            with self._persistence.transaction(self._leases) as transaction:
                challenge = transaction.read_admission(request).challenge_sha256
            self._current(cancellation)
            permit = self._core.prepare(
                replace(request, expected_challenge_sha256=challenge)
            )
            with self._lock:
                self._permit = permit
                self._phase = "EXECUTING"
            self._current(cancellation)
            try:
                result = self._core.execute(permit, cancellation=cancellation)
            except BaseException:
                if self._activation:
                    # The core may have sealed/retained before propagating an
                    # interruption. Audit that original history without renewing
                    # authority or exposing it as current data; preserve the error.
                    try:
                        with self._persistence.transaction(self._leases) as transaction:
                            original_permit = transaction.read_campaign_permit(permit.attempt_id)  # type: ignore[attr-defined]
                            _require(
                                original_permit == permit,
                                "RETAINED_CAMERA_PERMIT_MISMATCH",
                            )
                            original_result = transaction.read_campaign_result(permit.attempt_id)  # type: ignore[attr-defined]
                            self._read_activation_original(
                                transaction, permit, original_result
                            )
                            with self._lock:
                                self._result = original_result
                        with self._lock:
                            self._readback_scope = "EXITED"
                    except BaseException:
                        with self._lock:
                            self._readback_scope = "INTERRUPTED_READBACK_UNCONFIRMED"
                raise
            with self._lock:
                self._result = result
                self._phase = "READING_ORIGINAL_ATTEMPT"
            # Do not expose even a successful in-memory result before the actual
            # transaction has exited and its retained terminal seal is audited.
            with self._persistence.transaction(self._leases) as transaction:
                original_permit = transaction.read_campaign_permit(permit.attempt_id)  # type: ignore[attr-defined]
                original_result = transaction.read_campaign_result(permit.attempt_id)  # type: ignore[attr-defined]
                _require(original_permit == permit, "RETAINED_CAMERA_PERMIT_MISMATCH")
                _require(original_result == result, "RETAINED_CAMERA_RESULT_MISMATCH")
                # Retain failed native diagnostics too, without handing them to
                # capabilities/settings/media. A raw-only failed worker may have
                # no campaign artifact; do not invent one from worker memory.
                if self._activation:
                    artifacts = self._read_activation_original(
                        transaction, original_permit, result
                    )
                    artifact, checked = artifacts[0], artifacts
                else:
                    assert type(self._campaign) is PhysicalNativeCameraCampaign
                    _require(
                        result.receipt is not None,
                        "CAMERA_ATTEMPT_WITHOUT_RETAINED_RECEIPT",
                    )
                    artifacts = transaction.read_campaign_evidence(permit.attempt_id)  # type: ignore[attr-defined]
                    _require(
                        type(artifacts) is tuple and len(artifacts) == 1,
                        "EXACT_RETAINED_CAMERA_ARTIFACT_REQUIRED",
                    )
                    artifact = artifacts[0]
                    assert result.receipt is not None
                    _require(
                        result.receipt.evidence_sha256s == (artifact.payload_sha256,)
                        and result.receipt.output_bytes == len(artifact.payload)
                        and artifact.label
                        == "physical-native-camera-" + self._plan["operation"],
                        "RETAINED_CAMERA_ARTIFACT_BINDING",
                    )
                    checked = verify_physical_native_camera_campaign_evidence(
                        OwnedNativeCameraRunEvidence(artifact.payload),
                        campaign=self._campaign,
                        expected_permit=original_permit,
                        expected_evidence_sha256=artifact.payload_sha256,
                    )
                    _require(
                        artifact.schema == checked.to_dict()["schema"],
                        "RETAINED_CAMERA_ARTIFACT_SCHEMA",
                    )
                    # Preserve verified historical bytes even if a later dependency
                    # comparison or scope exit fails. This status does not claim
                    # clean ownership or grant a current observation to the sink.
                    with self._lock:
                        self._historical_evidence = checked.to_dict()
                        self._readback_scope = "VERIFIED_BYTES_EXIT_PENDING"
                if result.state is AttemptState.SEALED_KNOWN:
                    # Journal/attempt heads necessarily change during execution;
                    # substantive admission dependencies must not change with them.
                    fresh = transaction.read_admission(original_permit.request)
                    original = original_permit.admission
                    _require(
                        not fresh.quarantine_latched
                        and not fresh.unresolved_attempts
                        and not fresh.open_blocker_ids
                        and all(
                            getattr(fresh, name) == getattr(original, name)
                            for name in (
                                "cell_id",
                                "session_id",
                                "mode",
                                "stage",
                                "stage_state",
                                "source_binding_sha256",
                                "stage_plan_sha256",
                                "hazard_assessment_sha256",
                                "durability_qualification_sha256",
                                "configuration_epoch_hashes",
                                "selected_identity_sha256",
                            )
                        ),
                        "CAMERA_ADMISSION_CHANGED_BEFORE_HANDOFF",
                    )
            # A lease-exit failure above must prevent every data handoff.
            with self._lock:
                self._readback_scope = "EXITED"
            if (
                result.state is not AttemptState.SEALED_KNOWN
                or result.quarantine_latched
            ):
                raise self._uncertain_attempt_error(result)
            self._current(cancellation)
            self._phase_is("STAGING_ORIGINAL_DATA")
            preparation = self._campaign.preparation_for_permit(original_permit)
            additional: dict[str, Any] = (
                {"expected_supervision_sha256": artifacts[1].payload_sha256}
                if self._activation
                else {}
            )
            if capture:
                assert settings_epoch is not None
                if self._activation and self._plan["schema"] in (
                    CONFIGURATION_PLAN_SCHEMA,
                    SEALED_CONFIGURATION_PLAN_SCHEMA,
                ):
                    # Derived from the exact retained campaign, never from a
                    # caller-supplied stage label or a native receipt claim.
                    additional["configuration_verification"] = True
                    additional["capture_reference_request_key"] = (
                        original_permit.request.request_key
                    )
                    if self._plan["schema"] == SEALED_CONFIGURATION_PLAN_SCHEMA:
                        _require(
                            self._capture_checksum is not None,
                            "ORIGINAL_CAPTURE_CHECKSUM_REQUIRED",
                        )
                        additional["capture_checksum"] = self._capture_checksum
                sink.stage_retained_capture(
                    checked,
                    expected_preparation=preparation,
                    expected_evidence_sha256=artifact.payload_sha256,
                    expected_settings_epoch=settings_epoch,
                    cancellation=cancellation,
                    # This is file ingestion time, never a renewed device permit.
                    deadline_ns=time.monotonic_ns() + RETENTION_TIMEOUT_MS * 1_000_000,
                    **additional,
                )
            else:
                sink.accept_retained_probe(
                    enrollment,
                    checked,
                    expected_preparation=preparation,
                    expected_evidence_sha256=artifact.payload_sha256,
                    **additional,
                )
            self._current(cancellation, check_context=False)
            from .camera_configuration_wizard_contract import CAPTURE_ACTION_ID

            pending = sink.pending_observation_result(
                CAPTURE_ACTION_ID
                if self._activation
                and self._plan["schema"]
                in (CONFIGURATION_PLAN_SCHEMA, SEALED_CONFIGURATION_PLAN_SCHEMA)
                else ("physical_camera_capture" if capture else "physical_camera_probe")
            )
            self._phase_is("PENDING_COMPLETION_LOG")
            return pending
        except BaseException:
            with self._lock:
                if self._readback_scope == "VERIFIED_BYTES_EXIT_PENDING":
                    self._readback_scope = "EXIT_OR_FINAL_VALIDATION_UNCONFIRMED"
            self._phase_is("FAILED_NO_REPLAY")
            sink.invalidate()
            raise


class PhysicalCameraDispatchOwner(_CameraDispatchTransaction):
    """Production join: original M1 camera storage, never an imported report.

    Construction is inert. The caller must establish supported original-stage
    admission before invoking it. V2 execution independently checks the installed
    runtime policy and consumed scope. Legacy registrations remain dormant; this
    class neither qualifies hardware nor provides a browser release switch.
    """

    def __init__(
        self,
        persistence: M1PhysicalCameraPersistence,
        campaign: PhysicalNativeCameraCampaign | PhysicalCameraActivationCampaign,
        *,
        revalidate_context: Callable[[], None],
    ) -> None:
        _require(
            type(persistence) is M1PhysicalCameraPersistence,
            "ORIGINAL_CAMERA_M1_PERSISTENCE_REQUIRED",
        )
        _require(
            type(campaign)
            in (PhysicalNativeCameraCampaign, PhysicalCameraActivationCampaign),
            "EXACT_CAMERA_CAMPAIGN_REQUIRED",
        )
        plan = campaign.plan()
        runtime = persistence._runtime
        _require(
            str(
                runtime.deployment_root / "native-camera-output"
                if type(campaign) is PhysicalCameraActivationCampaign
                else runtime.deployment_root
            )
            == plan["assigned_parent_directory"]
            and runtime.cell.cell_id == plan["cell_id"]
            and runtime.source_binding_sha256
            == physical_camera_source_binding(plan["source_sha256"]),
            "ORIGINAL_CAMERA_STORE_CONTEXT_MISMATCH",
        )
        # The adapter implements the core's checked runtime protocol; its
        # lease property and exact dataclass annotations are deliberately
        # narrower than the generic coordinator typing seam.
        super().__init__(
            cast(CommissioningPersistence, persistence),
            campaign,
            revalidate_context=revalidate_context,
        )
