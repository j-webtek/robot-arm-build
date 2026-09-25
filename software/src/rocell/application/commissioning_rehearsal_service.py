"""Explicit reviewed camera commissioning, in an incapable M1 namespace.

This includes a fourteenth-stage readiness gap report, not physical commissioning. Native
drivers are deliberately absent. Synthetic fixture provenance travels in the
immutable session, every receipt, assessment, review and coordinator permit.
Only ``perform`` mutates storage; construction and cached ``view`` are inert.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Protocol
import uuid

from rocell.application.cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignRegistration,
    CellCommissioningCoordinator,
    INCAPABLE_COMPOSITION,
    RegisteredActionRequest,
)
from rocell.application.camera_rehearsal_campaign import (
    FRAME_BYTES,
    SyntheticBinaryCameraWorker,
    camera_settings,
)
from rocell.application.camera_fault_diagnostics import camera_fault_diagnostic
from rocell.application.configuration_epochs import load_configuration_epoch_policy
from rocell.application.physical_onboarding import STAGE_ORDER, PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_leases import LeaseLevel
from rocell.application.physical_onboarding_stage_catalog import (
    load_physical_onboarding_stage_catalog,
)
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.wizard_actions import WizardError
from rocell.safety.effects import EffectClass


ACTIONS = frozenset(
    {
        "rehearsal_initialize",
        "rehearsal_discover",
        "rehearsal_reopen",
        "rehearsal_record_operator",
        "rehearsal_collect",
        "rehearsal_assess",
        "rehearsal_review",
        "rehearsal_camera_campaign",
        "rehearsal_owned_camera_campaign",
        "rehearsal_camera_settings",
        "rehearsal_camera_probe",
        "rehearsal_camera_configuration",
        "rehearsal_arm_feedback_campaign",
        "rehearsal_owned_arm_feedback_campaign",
        "rehearsal_refresh",
    }
)
_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_SUPPORTED_STAGES = STAGE_ORDER[:14]
_CAMERA_STAGES = STAGE_ORDER[4:6]
_OPTICS_STAGES = STAGE_ORDER[6:8]
_ARM_IDENTITY_STAGE = PhysicalOnboardingStage.ARM_IDENTITY
_POWER_STAGES = STAGE_ORDER[9:11]
_ARM_SETUP_STAGES = STAGE_ORDER[8:11]
_EVALUATED_STAGES = (*STAGE_ORDER[6:11], *STAGE_ORDER[12:14])
_FEEDBACK_STAGE = PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION
_REFERENCE_STAGE = PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION
_NONCONTACT_STAGE = PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE


class _RetainedEvaluation(Protocol):
    """Small publication interface shared by closed no-device evaluators."""

    @property
    def evidence_sha256(self) -> str: ...

    def to_dict(self) -> dict[str, Any]: ...


def _bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _hash(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _actor(value: object) -> str:
    if type(value) is not str or _ACTOR.fullmatch(value) is None:
        raise WizardError(
            "INVALID_REHEARSAL_ACTOR", "Use a 1–64 character operator identifier."
        )
    return value


class CommissioningRehearsalService:
    """Server-owned stage predicates and exact review over qualified M1 storage.

    Source/camera/optics/arm/reference rehearsals and a readiness gap report.
    Serial uses a retained incapable campaign; physical serial, installed
    calibration and handoff integration remain pending. No generic
    pass field is accepted; review can commit only the current pure assessment.
    """

    def __init__(self, workspace: Path, directory: Path, *, source_sha256: str) -> None:
        self.workspace, self.directory = workspace, directory
        self.source_sha256 = source_sha256
        suffix = uuid.uuid4().hex
        self.cell_id, self.session_id = (
            "wizard-rehearsal-" + suffix[:16],
            "rehearsal-" + suffix,
        )
        self._lock = threading.RLock()
        self._store: Any = None
        self._receipt: dict[str, Any] | None = None
        self._receipt_reference: Any = None
        self._assessment: dict[str, Any] | None = None
        self._assessment_reference: Any = None
        self._selected: dict[str, Any] | None = None
        self._operator: str | None = None
        self._camera_settings: dict[str, Any] | None = None
        self._latest_preview: bytes | None = None
        self._latest_capture: dict[str, Any] | None = None
        self._camera_process: dict[str, Any] | None = None
        self._camera_process_diagnostic: dict[str, Any] | None = None
        self._camera_fault_diagnostic: dict[str, Any] | None = None
        self._camera_probe: Any = None
        self._probe_receipt: dict[str, Any] | None = None
        self._electronic_configuration: Any = None
        self._configuration_receipt: dict[str, Any] | None = None
        self._camera_readback: dict[str, Any] | None = None
        self._configuration_hidden = False
        self._probe_attempted = False
        self._latest_optics: dict[str, Any] | None = None
        self._latest_arm_identity: dict[str, Any] | None = None
        self._latest_power: dict[str, Any] | None = None
        self._latest_arm_feedback: dict[str, Any] | None = None
        self._latest_reference: dict[str, Any] | None = None
        self._latest_noncontact: dict[str, Any] | None = None
        self._retained_noncontact: dict[str, Any] | None = None
        # Exact frozen admission facts exist only during an explicit serial
        # campaign. Status reads and reopening never reconstruct an energy permit.
        self._feedback_admission: Any = None
        self._feedback_diagnostic: dict[str, Any] | None = None
        self._arm_feedback_process: dict[str, Any] | None = None
        self._failed = False
        self._open_attempted: set[str] = set()
        self._registry: Any = None
        self._discovery_root = directory.parent
        self._cached: dict[str, Any] = {
            "schema": "rocell.commissioning_rehearsal_view.v1",
            "status": "NOT_STARTED",
            "composition": INCAPABLE_COMPOSITION,
            "physical_authority": False,
            "directory": str(directory),
            "session_id": self.session_id,
            "cell_id": self.cell_id,
            "stages": [],
            "stage": None,
            "stage_state": None,
            "assessment": None,
            "selected_camera": None,
            "camera_process": None,
            "camera_fault_diagnostic": None,
            "camera_configuration": None,
            "optics_evaluation": None,
            "arm_identity_evaluation": None,
            "power_evaluation": None,
            "arm_feedback_evaluation": None,
            "arm_feedback_process": None,
            "reference_evaluation": None,
            "noncontact_evaluation": None,
            "session_origin": "NEW_THIS_LAUNCH",
            "operator_id": None,
            "discovery": {
                "status": "NOT_DISCOVERED",
                "choices": [],
                "issues": [],
                "storage_qualified": False,
                "physical_authority": False,
            },
            "reopen_result": None,
            "next_step": "Explicitly initialize a separate qualified rehearsal store. No physical session is created.",
            "limitations": "Hardware-free rehearsal only. Stages 7–8 run synthetic intrinsics/pixel checks, not stage-six binary pixels; 9 uses the arm profile and injected serial metadata; 10–11 assess synthetic power procedures; 12 exercises the actual feedback worker with memory-only serial and separately modeled power observations; 13 checks nominal reference geometry, not installed calibration; 14 reports collision/accuracy readiness gaps separately from synthetic calculator controls. No measured optics, received arm qualification, actual power observation, physical serial connection, installed calibration, noncontact motion or physical release.",
        }

    def view(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._cached)

    def retained_noncontact_diagnostics(self) -> dict[str, Any] | None:
        """Cached original diagnostic data, never current acceptance or replay."""
        with self._lock:
            return deepcopy(self._retained_noncontact)

    def retained_feedback_diagnostics(
        self, *, include_resolution_trace: bool = True
    ) -> dict[str, Any] | None:
        """Historical cached diagnostics, including late publication holds.

        This never loads M1 files or revalidates/executes a worker. A returned
        record is not a current stage receipt, successful UI publication or a
        physical qualification. Current owned attempts include the bounded full
        metadata-resolution trace; raw serial/child bytes remain private in M1.
        A restart restores the verified summary, not the full metadata trace.
        """
        with self._lock:
            result = deepcopy(self._feedback_diagnostic)
            if not include_resolution_trace and result is not None:
                resolution = result.get("controller_resolution")
                if resolution is not None and resolution.get("trace") is not None:
                    # A worker-result steps/report wrapper adds several nesting
                    # levels. Keep its exact hashes and compact status while the
                    # dedicated export retains the complete original trace.
                    resolution["trace"] = None
                    resolution["status"] = "FULL_TRACE_IN_DEDICATED_EXPORT"
            return result

    def retained_camera_diagnostics(self) -> dict[str, Any] | None:
        """Historical raw-free camera evidence, including late publication holds.

        This cached read never opens M1 files or reruns a camera. A missing
        attempt result explicitly leaves durable retention unconfirmed; even a
        known result does not imply stage/UI publication or physical readiness.
        """
        with self._lock:
            return deepcopy(self._camera_process_diagnostic)

    def _clear_camera_diagnostics(self) -> None:
        """Retire history when an explicit new camera run/session replaces it."""
        with self._lock:
            self._camera_process_diagnostic = None
            self._camera_fault_diagnostic = None
            self._cached["camera_fault_diagnostic"] = None

    def _retain_camera_diagnostics(self, worker: Any, result: Any) -> None:
        """Project actual bytes already produced; never reconstruct observations."""
        evidence = worker.evidence
        if evidence is None:
            return
        process = evidence.view()
        fault = camera_fault_diagnostic(evidence)
        diagnostic = {
            "camera_process": process,
            "camera_fault_diagnostic": fault,
            "retained_campaign_sha256": evidence.evidence_sha256,
            "attempt_result": (
                None if result is None else json.loads(_bytes(asdict(result)))
            ),
            "raw_evidence_location": (
                "ORIGINAL_M1_CAMPAIGN_RECORD_NOT_PUBLIC_STATUS"
                if result is not None
                else "CAMPAIGN_WORKER_EVIDENCE_DURABLE_RETENTION_UNCONFIRMED"
            ),
            "physical_authority": False,
        }
        with self._lock:
            self._camera_process = process
            self._camera_fault_diagnostic = fault
            self._camera_process_diagnostic = diagnostic
            # Historical explanations survive a later preview/source/Stop hold.
            # They never restore the current camera image or authorize a retry.
            self._cached["camera_fault_diagnostic"] = deepcopy(fault)

    def latest_preview(self) -> bytes | None:
        """Already-derived bytes only; status/image reads never capture or load files."""
        with self._lock:
            return self._latest_preview

    def _clear_preview(self) -> None:
        # This clears only the cached display. Immutable files and prior result
        # receipts remain available for investigation; no historical data moves.
        with self._lock:
            self._latest_preview, self._latest_capture = None, None
            self._cached["capture_dataset"] = None
            self._camera_process = None
            self._cached["camera_process"] = None
            self._camera_readback = None
            self._cached["camera_configuration"] = self._configuration_projection()

    def _configuration_projection(self) -> dict[str, Any] | None:
        if self._camera_probe is None or self._configuration_hidden:
            return None
        probe = self._camera_probe.view()
        complete = probe["status"] == "COMPLETE_PROBE_REHEARSAL"
        candidate = self._electronic_configuration
        return {
            "schema": "rocell.wizard_camera_configuration.v1",
            "status": (
                "HELD"
                if self._failed or not complete
                else (
                    "READBACK_COMPLETE"
                    if self._camera_readback is not None
                    else (
                        "CONFIGURATION_STAGED"
                        if candidate is not None
                        else "PROBE_COMPLETE"
                    )
                )
            ),
            "probe": probe,
            "capabilities": (
                self._camera_probe.capabilities().view() if complete else None
            ),
            "candidate": candidate.view() if candidate is not None else None,
            "readback": deepcopy(self._camera_readback),
            "physical_authority": False,
            "qualified": False,
            "meaning": "Retained incapable probe and staged electronic intent. Only a later retained capture supplies independent readback. Manual focus/aperture, physical geometry and received hardware remain unqualified.",
        }

    def camera_configuration_fields(self) -> tuple[dict[str, Any], ...]:
        from .wizard_camera_configuration import configuration_fields

        with self._lock:
            capabilities = (
                self._camera_probe.capabilities()
                if self._camera_probe is not None
                and not self._configuration_hidden
                and self._camera_probe.view()["status"] == "COMPLETE_PROBE_REHEARSAL"
                else None
            )
            return configuration_fields(capabilities)

    def invalidate_camera_configuration(self) -> None:
        """Retire current display only; immutable probe/capture records survive."""
        with self._lock:
            self._configuration_hidden = True
            self._camera_readback = None
            self._cached["camera_configuration"] = None

    def blocked_reason(self, action_id: str) -> str | None:
        view = self.view()
        if action_id in {"rehearsal_discover", "rehearsal_reopen"}:
            if self._store is not None:
                return "This launch already owns a rehearsal session. Export/close it before selecting another; sessions are never silently switched."
            if self._failed:
                return "A storage operation failed ambiguously in this launch. Inspect/export before a fresh launch; no implicit retry."
            if action_id == "rehearsal_reopen" and not self.reopen_choices():
                return "Explicitly discover existing rehearsal stores and choose one not already attempted in this launch."
            return None
        if action_id == "rehearsal_initialize":
            return (
                None
                if view["status"] == "NOT_STARTED"
                else "Rehearsal initialization or selection was already attempted in this launch. Do not silently create a replacement session."
            )
        if self._store is None:
            return "Initialize the separate durable rehearsal session first."
        if action_id == "rehearsal_refresh":
            return None
        if (
            self._failed
            or view.get("quarantined")
            or view.get("unresolved_attempt_ids")
        ):
            return "This rehearsal is held. Verify retained state and export; do not clear or bypass uncertainty."
        if view["stage"] not in {s.value for s in _SUPPORTED_STAGES}:
            return "No later stage is implemented by this rehearsal. A readiness gap report is not noncontact acceptance or handoff; every physical stage remains held."
        state = view["stage_state"]
        if action_id == "rehearsal_record_operator":
            return (
                None
                if state == "WAITING_OPERATOR"
                and view["session_origin"] == "REOPENED_EXISTING"
                and view["stage"] in {s.value for s in _CAMERA_STAGES}
                and self._operator is None
                and self._receipt is None
                else "Only a reopened, uncollected camera stage without a retained operator can record a new operator."
            )
        if action_id == "rehearsal_camera_settings":
            return (
                None
                if state == "WAITING_OPERATOR"
                and view["stage"] == _CAMERA_STAGES[0].value
                and self._receipt is None
                and self._camera_settings is None
                and self._operator is not None
                else "Open the camera mode stage and record settings once, before its campaign. Later changes require new evidence, not reuse."
            )
        if action_id in {"rehearsal_camera_probe", "rehearsal_camera_configuration"}:
            if not (
                state == "WAITING_OPERATOR"
                and view["stage"] == _CAMERA_STAGES[0].value
                and self._receipt is None
                and self._operator is not None
                and self._selected is not None
            ):
                return "Open the first camera stage before probing or staging its exact settings."
            if action_id == "rehearsal_camera_probe":
                return (
                    "This probe was already attempted; inspect retained evidence without replay."
                    if self._probe_attempted
                    else None
                )
            return (
                None
                if self._camera_probe is not None
                and self._camera_probe.view()["status"] == "COMPLETE_PROBE_REHEARSAL"
                and self._camera_settings is not None
                and self._electronic_configuration is None
                else "Complete the retained probe and synthetic settings first, then stage electronic intent once before capture."
            )
        if action_id == "rehearsal_collect":
            if (
                view["stage"]
                in {s.value for s in (*_EVALUATED_STAGES, _FEEDBACK_STAGE)}
                and state != "PENDING"
            ):
                return "This evaluated-stage collection was already started. Assess its retained result or inspect/export a hold; never replay a missing or failed evaluation."
            return (
                None
                if state in {"PENDING", "BLOCKED"}
                else "Evidence collection is available only at the due unstarted or blocked stage."
            )
        if action_id in {
            "rehearsal_camera_campaign",
            "rehearsal_owned_camera_campaign",
        }:
            if self._probe_attempted and (
                self._electronic_configuration is None
                or action_id != "rehearsal_owned_camera_campaign"
            ):
                return "This session chose probe-based configuration. Stage its intent and use the contained capture; no silent no-control or in-process fallback."
            return (
                None
                if state == "WAITING_OPERATOR"
                and view["stage"] in {s.value for s in _CAMERA_STAGES}
                and self._receipt is None
                and self._camera_settings is not None
                and self._operator is not None
                else "Open the due camera stage and record its settings; an exact campaign is admitted only once before assessment."
            )
        if action_id in {
            "rehearsal_arm_feedback_campaign",
            "rehearsal_owned_arm_feedback_campaign",
        }:
            return (
                None
                if state == "WAITING_OPERATOR"
                and view["stage"] == _FEEDBACK_STAGE.value
                and self._receipt is None
                and self._operator is not None
                else "Open the due feedback stage after reviewing identity and both power stages. Choose only one retained incapable feedback campaign; no fallback, replay or physical serial endpoint is allowed."
            )
        if action_id == "rehearsal_assess":
            return (
                None
                if state == "WAITING_OPERATOR" and self._receipt is not None
                else "Collect current-stage evidence (or complete its camera campaign) before assessment."
            )
        if action_id == "rehearsal_review":
            return (
                None
                if state == "REVIEW_PENDING" and self._assessment is not None
                else "A current exact assessment is required before review."
            )
        return "Unknown rehearsal action."

    def bind(self, action_id: str, values: dict[str, Any]) -> dict[str, Any]:
        reason = self.blocked_reason(action_id)
        if reason:
            raise WizardError("REHEARSAL_ACTION_BLOCKED", reason)
        if (
            action_id == "rehearsal_owned_camera_campaign"
            and values.get("fault") == "control-readback-drift"
            and (
                self._electronic_configuration is None
                or not self._electronic_configuration.controls
            )
        ):
            raise WizardError(
                "CONTROL_READBACK_SCENARIO_REQUIRES_CONTROLS",
                "Stage at least one reported electronic control before selecting readback drift.",
            )
        if action_id == "rehearsal_reopen":
            choice = next(
                (
                    item
                    for item in self.reopen_choices()
                    if item["choice_id"] == values.get("choice_id")
                ),
                None,
            )
            if choice is None:
                raise WizardError(
                    "UNKNOWN_REOPEN_CHOICE",
                    "Choose a currently discovered server-issued session ID.",
                )
            values = {
                **values,
                "_discovery_sha256": choice["discovery_sha256"],
                "_selected_store": choice,
            }
        if action_id in {
            "rehearsal_camera_campaign",
            "rehearsal_owned_camera_campaign",
        }:
            import importlib.util

            missing = [
                name
                for name in ("numpy", "PIL")
                if importlib.util.find_spec(name) is None
            ]
            if missing:
                raise WizardError(
                    "REHEARSAL_IMAGE_DEPENDENCIES_MISSING",
                    "Run the explicit development setup before binary rehearsal. Missing: "
                    + ", ".join(missing),
                )
        if "operator_id" in values:
            _actor(values["operator_id"])
        if action_id == "rehearsal_camera_configuration":
            from .wizard_camera_configuration import stage_wizard_camera_configuration

            assert self._camera_probe is not None and self._selected is not None
            stage_wizard_camera_configuration(
                self._camera_probe.capabilities(),
                values,
                source_sha256=self.source_sha256,
                selected_identity_sha256=_hash(self._selected),
            )
        if "reviewer_id" in values:
            reviewer = _actor(values["reviewer_id"])
            if reviewer == self._operator:
                raise WizardError(
                    "DISTINCT_REVIEWER_REQUIRED",
                    "The rehearsal reviewer must differ from the evidence operator.",
                )
        return {**values, "_view_sha256": _hash(self.view())}

    def reopen_choices(self) -> list[dict[str, Any]]:
        """Cached opaque selections only; no implicit filesystem enumeration."""
        return [
            item
            for item in self.view()["discovery"]["choices"]
            if item["choice_id"] not in self._open_attempted
        ]

    def _discover(self) -> None:
        from rocell.application.commissioning_rehearsal_reopen import (
            KnownRehearsalRoot,
            RehearsalReopenRegistry,
        )

        if self._registry is None:
            self._registry = RehearsalReopenRegistry(
                (
                    KnownRehearsalRoot(
                        "assigned-workspace-rehearsals", self._discovery_root
                    ),
                ),
                workspace_source_sha256=self.source_sha256,
                catalog_sha256=load_physical_onboarding_stage_catalog(
                    self.workspace
                ).source_sha256,
                reference_workspace=self.workspace,
            )
        result = self._registry.discover()
        with self._lock:
            self._cached["discovery"] = {
                "status": "DISCOVERED",
                "choices": [
                    {**asdict(choice), "directory": str(choice.directory)}
                    for choice in result.choices
                ],
                "issues": [asdict(issue) for issue in result.issues],
                "storage_qualified": False,
                "physical_authority": False,
            }

    def _reopen(self, values: dict[str, Any], cancellation: threading.Event) -> None:
        choice_id = values["choice_id"]
        if self._registry is None or choice_id in self._open_attempted:
            raise WizardError(
                "REOPEN_NOT_PREPARED",
                "The selected opening is unavailable or was already attempted.",
            )
        self._open_attempted.add(choice_id)
        result = self._registry.open(
            choice_id,
            expected_discovery_sha256=values["_discovery_sha256"],
            admission_facts=self._facts,
        )
        restored = result.restored
        if result.status == "OPENED" and (restored is None or result.store is None):
            raise WizardError(
                "INVALID_REOPEN_RESULT",
                "Opening did not return its exact verified adapter/state; no session was attached.",
            )
        # Qualification is synchronous storage I/O. Stop prevents attachment,
        # not the already-observed qualification probes. Never replay a campaign.
        if cancellation.is_set():
            projection = {
                "status": "READ_ONLY_HOLD",
                "original_session_reopened": False,
                "disposition": None,
                "operator_id": None,
                "reasons": [
                    {
                        "code": "OPEN_CANCELLED_NOT_ATTACHED",
                        "message": "Storage opening finished after Stop; the session was not attached and nothing is replayed.",
                        "remediation": "Inspect retained state before a fresh explicit launch.",
                    }
                ],
            }
        else:
            projection = {
                "status": result.status,
                "original_session_reopened": result.status == "OPENED",
                "disposition": restored.disposition if restored else None,
                "operator_id": restored.operator_id if restored else None,
                "reasons": [asdict(reason) for reason in result.reasons],
            }
        with self._lock:
            self._cached["reopen_result"] = projection
            self._cached["status"] = "REOPEN_HELD"
            self._cached["next_step"] = (
                "The selected session is not attached. Inspect its hold/export; choose another unused discovered session or restart explicitly after review."
            )
        if projection["status"] != "OPENED":
            return
        if restored is None or result.store is None:
            raise WizardError(
                "INVALID_REOPEN_RESULT",
                "A successful opening did not return its exact verified adapter/state.",
            )
        with self._lock:
            self._store = result.store
            self.directory, self.cell_id, self.session_id = (
                restored.directory,
                restored.cell_id,
                restored.session_id,
            )
            self._receipt = restored.receipt.document() if restored.receipt else None
            self._receipt_reference = restored.receipt_reference
            self._assessment = (
                restored.assessment.document() if restored.assessment else None
            )
            self._assessment_reference = restored.assessment_reference
            self._selected = (
                restored.selected_camera.document()["candidate"]
                if restored.selected_camera
                else None
            )
            self._operator = restored.operator_id
            self._camera_settings = (
                restored.camera_settings.document()
                if restored.camera_settings
                else None
            )
            self._clear_preview()
            self._clear_camera_diagnostics()
            self._latest_capture = (
                restored.latest_capture.document()["capture_dataset"]
                if restored.latest_capture
                else None
            )
            self._camera_process = (
                restored.latest_capture.document().get("camera_process")
                if restored.latest_capture
                else None
            )
            optics_receipts = [
                item
                for item in restored.stage_evidence
                if item.document().get("schema") == "rocell.rehearsal_optics_receipt.v1"
            ]
            self._latest_optics = (
                self._optics_projection(
                    max(
                        optics_receipts,
                        key=lambda item: STAGE_ORDER.index(item.reference.stage),
                    ).document()
                )
                if optics_receipts
                else None
            )
            # Restore small already-verified projections, never replay identity
            # inventory fixtures, power assessors or camera operations on open.
            for schema, attribute in (
                ("rocell.rehearsal_arm_identity_receipt.v1", "_latest_arm_identity"),
                ("rocell.rehearsal_power_receipt.v1", "_latest_power"),
            ):
                candidates = [
                    item
                    for item in restored.stage_evidence
                    if item.document().get("schema") == schema
                ]
                latest = (
                    max(
                        candidates,
                        key=lambda item: STAGE_ORDER.index(item.reference.stage),
                    )
                    if candidates
                    else None
                )
                setattr(
                    self,
                    attribute,
                    self._arm_setup_projection(latest.document()) if latest else None,
                )
            feedback_receipts = [
                item
                for item in restored.stage_evidence
                if item.document().get("schema")
                in {
                    "rocell.rehearsal_feedback_receipt.v1",
                    "rocell.rehearsal_owned_feedback_receipt.v1",
                }
            ]
            self._latest_arm_feedback = (
                deepcopy(feedback_receipts[0].document()["evaluation"])
                if feedback_receipts
                else None
            )
            self._arm_feedback_process = (
                deepcopy(feedback_receipts[0].document().get("arm_feedback_process"))
                if feedback_receipts
                else None
            )
            self._feedback_diagnostic = (
                {
                    "attempt_result": deepcopy(
                        feedback_receipts[0].document()["attempt_result"]
                    ),
                    "safe_summary": deepcopy(
                        feedback_receipts[0].document()["evaluation"]["safe_summary"]
                    ),
                    "arm_feedback_process": deepcopy(self._arm_feedback_process),
                    "retained_campaign_sha256": feedback_receipts[0].document()[
                        "retained_campaign_sha256"
                    ],
                    "controller_resolution": {
                        "status": "FULL_TRACE_NOT_RESTORED_USE_ORIGINAL_M1",
                        "trace": None,
                        "trace_sha256": (
                            self._arm_feedback_process.get("resolution", {}).get(
                                "trace_sha256"
                            )
                            if self._arm_feedback_process.get("resolution") is not None
                            else None
                        ),
                        "physical_authority": False,
                    },
                    "raw_evidence_location": "ORIGINAL_M1_CAMPAIGN_RECORD_NOT_PUBLIC_STATUS",
                    "physical_authority": False,
                }
                if feedback_receipts and self._arm_feedback_process is not None
                else None
            )
            reference_receipts = [
                item
                for item in restored.stage_evidence
                if item.document().get("schema")
                == "rocell.rehearsal_reference_receipt.v1"
            ]
            self._latest_reference = (
                self._reference_projection(reference_receipts[0].document())
                if reference_receipts
                else None
            )
            noncontact_receipts = [
                item
                for item in restored.stage_evidence
                if item.document().get("schema")
                == "rocell.rehearsal_noncontact_receipt.v1"
            ]
            self._latest_noncontact = (
                self._noncontact_projection(noncontact_receipts[0].document())
                if noncontact_receipts
                else None
            )
            self._retained_noncontact = (
                deepcopy(noncontact_receipts[0].document())
                if noncontact_receipts
                else None
            )
            self._cached.update(
                directory=str(self.directory),
                cell_id=self.cell_id,
                session_id=self.session_id,
                session_origin="REOPENED_EXISTING",
                challenge_sha256=restored.challenge_sha256,
            )
        # Recheck exact state after attachment; an external change is a hold,
        # not permission to rebase a restored pending assessment.
        if any(
            item.document().get("schema") == "rocell.rehearsal_camera_probe_receipt.v1"
            for item in restored.stage_evidence
        ):
            with self._transaction() as tx:
                probe_doc, probe, config_doc, configuration = (
                    self._configuration_context(tx)
                )
                self._probe_receipt, self._camera_probe = probe_doc, probe
                self._configuration_receipt, self._electronic_configuration = (
                    config_doc,
                    configuration,
                )
                self._probe_attempted = probe is not None
                self._camera_readback = (
                    restored.latest_capture.document().get("camera_readback")
                    if restored.latest_capture
                    else None
                )
        self._refresh(expected_change=False)

    def _record_operator(self, values: dict[str, Any]) -> None:
        self._operator = _actor(values["operator_id"])
        with self._transaction() as tx:
            stage = tx.snapshot().next_action.stage
            self._store_json(
                tx,
                stage,
                self._camera_document("rocell.rehearsal_camera_stage_open.v1", stage),
                "Explicit reopened camera-stage operator",
            )

    def _refresh(self, *, expected_change: bool = True) -> None:
        assert self._store is not None
        snapshot = self._store.snapshot(self.session_id)
        verification = self._store.verification(self.session_id)
        next_stage = snapshot.next_action.stage
        with self._lock:
            if (
                not expected_change
                and self._cached.get("challenge_sha256")
                != verification.challenge_sha256
            ):
                # Refresh is observation, not permission to rebase a review on
                # another process's changes. Keep all durable evidence, discard
                # only this launch's pending in-memory approval capability.
                self._failed = True
                self._assessment = None
                self._assessment_reference = None
                self._latest_optics = None
                self._latest_arm_identity = self._latest_power = None
                self._latest_arm_feedback = None
                self._arm_feedback_process = None
                self._latest_reference = None
                self._latest_noncontact = None
                self._configuration_hidden = True
                self._clear_preview()
                self._cached["external_change_hold"] = (
                    "Durable state changed outside this operation. Pending review is invalid; inspect/export retained evidence."
                )
            self._cached.update(
                status=(
                    "HELD"
                    if self._failed
                    or verification.quarantined
                    or verification.unresolved_attempt_ids
                    else "ACTIVE_REHEARSAL"
                ),
                stage=next_stage.value if next_stage else None,
                stage_state=(
                    snapshot.next_action.stage_state.value
                    if snapshot.next_action.stage_state
                    else None
                ),
                stages=[item.to_dict() for item in snapshot.stages],
                journal_head_sha256=snapshot.head.head_sha256,
                challenge_sha256=verification.challenge_sha256,
                evidence_inventory_sha256=verification.evidence_inventory_sha256,
                attempt_event_count=verification.attempt_event_count,
                unresolved_attempt_ids=list(verification.unresolved_attempt_ids),
                quarantined=verification.quarantined,
                assessment=deepcopy(self._assessment),
                selected_camera=deepcopy(self._selected),
                operator_id=self._operator,
                camera_settings=deepcopy(self._camera_settings),
                capture_dataset=deepcopy(self._latest_capture),
                camera_process=deepcopy(self._camera_process),
                camera_fault_diagnostic=deepcopy(self._camera_fault_diagnostic),
                camera_configuration=self._configuration_projection(),
                optics_evaluation=deepcopy(self._latest_optics),
                arm_identity_evaluation=deepcopy(self._latest_arm_identity),
                power_evaluation=deepcopy(self._latest_power),
                arm_feedback_evaluation=deepcopy(self._latest_arm_feedback),
                arm_feedback_process=deepcopy(self._arm_feedback_process),
                reference_evaluation=deepcopy(self._latest_reference),
                noncontact_evaluation=deepcopy(self._latest_noncontact),
                next_step=(
                    "Noncontact readiness is blocked by the retained nominal gaps. Export and review the diagnostic; passing synthetic controls do not authorize handoff or motion."
                    if next_stage is _NONCONTACT_STAGE
                    and snapshot.next_action.stage_state is V2StageState.BLOCKED
                    else (
                        "Review the displayed exact synthetic assessment; it cannot qualify physical hardware."
                        if self._assessment
                        else "Follow the due stage: collect evidence, choose one eligible camera or incapable feedback campaign when required, assess, then review. No fallback/replay. Physical serial, installed calibration, handoff and every physical stage remain held."
                    )
                ),
            )

    def _facts(self, request: RegisteredActionRequest, snapshot: Any) -> Any:
        from rocell.application.commissioning_m1_persistence import (
            RehearsalAdmissionFacts,
        )

        if request.action_id in {
            "rehearsal-arm-feedback",
            "rehearsal-owned-arm-feedback",
        }:
            if (
                self._feedback_admission is None
                or snapshot.next_action.stage is not _FEEDBACK_STAGE
            ):
                raise WizardError(
                    "FEEDBACK_ADMISSION_MISSING",
                    "No exact current incapable feedback admission exists.",
                )
            return self._feedback_admission

        # Server-pinned source documents, never browser-authored authority hashes.
        policy = load_configuration_epoch_policy(self.workspace)
        catalog = load_physical_onboarding_stage_catalog(self.workspace)
        return RehearsalAdmissionFacts(
            hazard_assessment_document={
                "composition": INCAPABLE_COMPOSITION,
                "catalog_sha256": catalog.source_sha256,
                "stage": snapshot.next_action.stage.value,
                "physical_hazards_closed": False,
                "provider_set": "SYNTHETIC_CAMERA_ONLY",
            },
            configuration_epoch_documents=tuple(
                {
                    "composition": INCAPABLE_COMPOSITION,
                    "epoch_id": epoch.epoch_id,
                    "policy_sha256": policy.source_sha256,
                    "workspace_source_sha256": self.source_sha256,
                    "physical_epoch": "UNMEASURED",
                    "synthetic_camera_settings_epoch": (
                        self._camera_settings["settings_epoch"]
                        if self._camera_settings is not None
                        and epoch.epoch_id == "camera_support_optics"
                        else None
                    ),
                    **(
                        {
                            "electronic_camera_settings_epoch": self._electronic_configuration.settings_epoch,
                            "probe_evidence_sha256": self._electronic_configuration.to_dict()[
                                "probe_evidence_sha256"
                            ],
                        }
                        if self._electronic_configuration is not None
                        and epoch.epoch_id == "camera_support_optics"
                        else {}
                    ),
                }
                for epoch in policy.epochs
            ),
            selected_identity_document=deepcopy(self._selected),
        )

    def _initialize(self) -> None:
        from rocell.application.commissioning_m1_persistence import (
            M1CommissioningPersistence,
            rehearsal_source_binding,
        )
        from rocell.application.physical_onboarding_m1 import (
            PhysicalOnboardingM1Runtime,
        )
        from rocell.application.wizard_diagnostic_coordinator import (
            require_regular_path,
        )

        # No retry after an ambiguous initialization; partial evidence is kept.
        self._cached["status"] = "INITIALIZING"
        if not self.directory.parent.exists():
            require_regular_path(self.directory.parent.parent, directory=True)
            self.directory.parent.mkdir(exist_ok=False)
        require_regular_path(self.directory.parent, directory=True)
        self.directory.mkdir(exist_ok=False)
        require_regular_path(self.directory, directory=True)
        runtime = PhysicalOnboardingM1Runtime.initialize(
            self.directory,
            source_binding_sha256=rehearsal_source_binding(self.source_sha256),
            cell_id=self.cell_id,
        )
        runtime.create_session(
            self.session_id,
            mode="REHEARSAL",
            workspace_source_sha256=self.source_sha256,
        )
        self._store = M1CommissioningPersistence(
            runtime,
            workspace_source_sha256=self.source_sha256,
            admission_facts=self._facts,
        )

    def _transaction(self) -> Any:
        return self._store.stage_transaction(
            self.session_id, expected_challenge_sha256=self._cached["challenge_sha256"]
        )

    @staticmethod
    def _time(snapshot: Any) -> int:
        previous = (
            snapshot.committed_events[-1].occurred_at_ns
            if snapshot.committed_events
            else snapshot.header.created_at_ns
        )
        return max(time.time_ns(), previous + 1)

    def _store_json(
        self, tx: Any, stage: PhysicalOnboardingStage, value: dict[str, Any], label: str
    ) -> Any:
        snapshot = tx.snapshot()
        return tx.store_evidence(
            stage,
            _bytes(value),
            label=label,
            media_type="application/json",
            captured_at_ns=self._time(snapshot),
            expected_head_sha256=snapshot.head.head_sha256,
        )

    def _collect(self, values: dict[str, Any], cancellation: threading.Event) -> None:
        self._operator = _actor(values["operator_id"])
        self._clear_preview()
        self._latest_optics = None
        with self._transaction() as tx:
            snapshot = tx.snapshot()
            stage = snapshot.next_action.stage
            if stage not in _SUPPORTED_STAGES:
                raise WizardError(
                    "STAGE_NOT_IMPLEMENTED",
                    "This stage is not implemented by the rehearsal slice.",
                )
            tx.commit_stage_state(
                stage,
                V2StageState.WAITING_OPERATOR,
                occurred_at_ns=self._time(snapshot),
                detail_code="REHEARSAL_STAGE_OPENED",
                expected_head_sha256=snapshot.head.head_sha256,
            )
            self._receipt, self._assessment = None, None
            self._receipt_reference, self._assessment_reference = None, None
            if stage is _NONCONTACT_STAGE:
                self._collect_noncontact(tx, cancellation)
                return
            if stage is _REFERENCE_STAGE:
                self._collect_reference(tx, cancellation)
                return
            if stage is _FEEDBACK_STAGE:
                self._latest_arm_feedback = self._feedback_diagnostic = None
                self._arm_feedback_process = None
                self._store_json(
                    tx,
                    stage,
                    self._camera_document(
                        "rocell.rehearsal_feedback_stage_open.v1", stage
                    ),
                    "Incapable feedback stage operator; no serial campaign dispatched",
                )
                self._feedback_context(tx)
                self._check_cancelled(cancellation, "feedback-stage opening")
                return
            if stage in _ARM_SETUP_STAGES:
                self._collect_arm_setup(tx, stage, cancellation)
                return
            if stage in _OPTICS_STAGES:
                self._store_json(
                    tx,
                    stage,
                    self._camera_document(
                        "rocell.rehearsal_optics_stage_open.v1", stage
                    ),
                    "No-device synthetic optics stage operator",
                )
                self._collect_optics(tx, stage, cancellation)
                return
            if stage in _CAMERA_STAGES:
                if stage is _CAMERA_STAGES[0]:
                    self._camera_settings = None
                self._store_json(
                    tx,
                    stage,
                    self._camera_document(
                        "rocell.rehearsal_camera_stage_open.v1", stage
                    ),
                    "Synthetic camera stage operator",
                )
                return
            catalog = load_physical_onboarding_stage_catalog(self.workspace)
            self._receipt = {
                "schema": "rocell.rehearsal_stage_receipt.v1",
                "composition": INCAPABLE_COMPOSITION,
                "stage": stage.value,
                "session_id": self.session_id,
                "cell_id": self.cell_id,
                "workspace_source_sha256": self.source_sha256,
                "operator_id": self._operator,
                "catalog_sha256": catalog.source_sha256,
                "fixture": "SOURCE_BOUND_SYNTHETIC_PREREQUISITES",
                "physical_observation": False,
            }
            if stage is PhysicalOnboardingStage.CAMERA_IDENTITY:
                candidate = values["candidate"]
                self._receipt["candidate"] = {
                    "candidate_id": candidate,
                    "provenance": "SYNTHETIC_NOT_ENUMERATED",
                    "model": (
                        "B0477" if candidate == "synthetic-b0477" else "WRONG_MODEL"
                    ),
                    "unit_id": "SYNTHETIC-UNIT-A",
                    "endpoint": "incapable-fixture-only",
                }
            self._receipt_reference = self._store_json(
                tx, stage, self._receipt, "Synthetic stage receipt"
            )

    def _optics_context(
        self, tx: Any, stage: PhysicalOnboardingStage, operator: str
    ) -> tuple[Any, dict[str, Any]]:
        from rocell.application.commissioning_rehearsal_reopen import (
            _read_evidence,
            _optics_binding,
        )

        snapshot = tx.snapshot()
        catalog = load_physical_onboarding_stage_catalog(self.workspace).source_sha256
        evidence = _read_evidence(self.directory, snapshot, self.source_sha256, catalog)
        binding, camera = _optics_binding(
            snapshot, evidence, stage, operator, self.source_sha256, catalog
        )
        # The nominal evaluator does not use these pixels, but this stage still
        # depends on the exact accepted stage-six camera evidence being intact.
        self._verify_capture(camera.document(), tx=tx)
        return binding, evidence

    @staticmethod
    def _optics_projection(receipt: dict[str, Any]) -> dict[str, Any]:
        result = receipt["evaluation"]
        return {
            "stage": receipt["stage"],
            "outcome": result["outcome"],
            "checks": deepcopy(result["checks"]),
            "provenance": deepcopy(result["provenance"]),
            "evaluation_sha256": receipt["evaluation_sha256"],
            "selected_inputs_sha256": result["selected_inputs_sha256"],
            "physical_authority": False,
            "meaning": "Substantive synthetic checks only. No installed camera calibration or stage-6 dataset pixel evaluation is claimed.",
        }

    def _collect_optics(
        self, tx: Any, stage: PhysicalOnboardingStage, cancellation: threading.Event
    ) -> None:
        from rocell.application.rehearsal_optics_stages import (
            evaluate_rehearsal_optics_stage,
        )

        assert self._operator is not None
        if cancellation.is_set():
            raise WizardError(
                "OPTICS_CANCELLED",
                "Optics collection was cancelled after opening. No replay; inspect/export the held stage.",
            )
        binding, _ = self._optics_context(tx, stage, self._operator)
        if cancellation.is_set():
            raise WizardError(
                "OPTICS_CANCELLED_BEFORE_EVALUATION",
                "Stop arrived during dependency verification. No image probe was run; inspect/export the held stage.",
            )
        evaluated = evaluate_rehearsal_optics_stage(self.workspace, binding, sequence=0)
        if cancellation.is_set():
            raise WizardError(
                "OPTICS_CANCELLED_BEFORE_PUBLICATION",
                "Synthetic evaluation finished after Stop; no result was published. Reopening must not rerun it.",
            )
        receipt = self._camera_document("rocell.rehearsal_optics_receipt.v1", stage)
        receipt.update(
            evaluation=evaluated.to_dict(), evaluation_sha256=evaluated.evidence_sha256
        )
        reference = self._store_json(
            tx, stage, receipt, "Substantive no-device synthetic optics evaluation"
        )
        self._receipt, self._receipt_reference = receipt, reference
        self._latest_optics = self._optics_projection(receipt)

    def _verify_optics(self, tx: Any) -> Any:
        from rocell.application.commissioning_rehearsal_reopen import (
            _verify_optics_receipt,
        )

        assert self._receipt is not None and self._receipt_reference is not None
        snapshot = tx.snapshot()
        stage = snapshot.next_action.stage
        _, evidence = self._optics_context(tx, stage, self._receipt["operator_id"])
        retained = evidence[self._receipt_reference.evidence_id]
        if retained.document() != self._receipt:
            raise WizardError(
                "OPTICS_RECEIPT_CHANGED",
                "Cached optics receipt differs from its exact retained evidence.",
            )
        return _verify_optics_receipt(
            snapshot,
            evidence,
            retained,
            self.source_sha256,
            load_physical_onboarding_stage_catalog(self.workspace).source_sha256,
        )

    @staticmethod
    def _arm_setup_projection(receipt: dict[str, Any]) -> dict[str, Any]:
        result = receipt["evaluation"]
        return {
            "stage": receipt["stage"],
            "outcome": result["outcome"],
            "checks": deepcopy(result["checks"]),
            "provenance": deepcopy(result["provenance"]),
            "evaluation_sha256": receipt["evaluation_sha256"],
            "selected_inputs_sha256": result["selected_inputs_sha256"],
            "physical_authority": False,
            "meaning": (
                "Synthetic profile/injected inventory checks only. No host device inventory, received Pro/driver/firmware identity or serial connection was established."
                if receipt["stage"] == _ARM_IDENTITY_STAGE.value
                else "Synthetic typed procedure/assessor checks only. No energy event, startup trajectory prediction, E-stop test or final power observation occurred."
            ),
        }

    def _arm_setup_context(
        self, tx: Any, stage: PhysicalOnboardingStage, operator: str
    ) -> tuple[Any, dict[str, Any]]:
        from rocell.application.commissioning_rehearsal_reopen import (
            _read_evidence,
            _arm_identity_binding,
            _power_binding,
        )

        snapshot = tx.snapshot()
        catalog = load_physical_onboarding_stage_catalog(self.workspace).source_sha256
        evidence = _read_evidence(self.directory, snapshot, self.source_sha256, catalog)
        if stage is _ARM_IDENTITY_STAGE:
            binding, camera = _arm_identity_binding(
                snapshot, evidence, operator, self.source_sha256, catalog
            )
        elif stage in _POWER_STAGES:
            binding, camera = _power_binding(
                snapshot, evidence, stage, operator, self.source_sha256, catalog
            )
        else:
            raise WizardError(
                "ARM_SETUP_STAGE_MISMATCH",
                "No registered arm setup evaluator for this stage.",
            )
        # Earlier pixel results depend on these exact bytes being intact. Their
        # use here is dependency verification, not camera acquisition or solving.
        self._verify_capture(camera.document(), tx=tx)
        return binding, evidence

    def _collect_arm_setup(
        self, tx: Any, stage: PhysicalOnboardingStage, cancellation: threading.Event
    ) -> None:
        from rocell.application.commissioning_rehearsal_reopen import (
            _EVALUATED_OPEN_SCHEMAS,
            _EVALUATED_SCHEMAS,
        )

        assert self._operator is not None
        attribute = (
            "_latest_arm_identity" if stage is _ARM_IDENTITY_STAGE else "_latest_power"
        )
        setattr(self, attribute, None)
        self._check_cancelled(cancellation, "synthetic arm stage opening receipt")
        self._store_json(
            tx,
            stage,
            self._camera_document(_EVALUATED_OPEN_SCHEMAS[stage], stage),
            "No-device synthetic arm setup stage operator",
        )
        binding, _ = self._arm_setup_context(tx, stage, self._operator)
        self._check_cancelled(cancellation, "synthetic arm stage evaluation")
        result: _RetainedEvaluation
        if stage is _ARM_IDENTITY_STAGE:
            from rocell.application.rehearsal_arm_identity_stage import (
                evaluate_rehearsal_arm_identity_stage,
            )

            result = evaluate_rehearsal_arm_identity_stage(self.workspace, binding)
        else:
            from rocell.application.rehearsal_power_stages import (
                evaluate_rehearsal_power_stage,
            )

            result = evaluate_rehearsal_power_stage(self.workspace, binding, sequence=0)
        self._check_cancelled(cancellation, "synthetic arm stage result publication")
        receipt = self._camera_document(_EVALUATED_SCHEMAS[stage], stage)
        receipt.update(
            evaluation=result.to_dict(), evaluation_sha256=result.evidence_sha256
        )
        reference = self._store_json(
            tx, stage, receipt, "Retained no-device synthetic arm setup evaluation"
        )
        self._receipt, self._receipt_reference = receipt, reference
        setattr(self, attribute, self._arm_setup_projection(receipt))

    def _verify_arm_setup(self, tx: Any) -> Any:
        from rocell.application.commissioning_rehearsal_reopen import (
            _verify_evaluated_receipt,
        )

        assert self._receipt is not None and self._receipt_reference is not None
        snapshot = tx.snapshot()
        _, evidence = self._arm_setup_context(
            tx, snapshot.next_action.stage, self._receipt["operator_id"]
        )
        retained = evidence[self._receipt_reference.evidence_id]
        if retained.document() != self._receipt:
            raise WizardError(
                "ARM_SETUP_RECEIPT_CHANGED",
                "Cached arm setup receipt differs from its exact retained evidence.",
            )
        return _verify_evaluated_receipt(
            snapshot,
            evidence,
            retained,
            self.source_sha256,
            load_physical_onboarding_stage_catalog(self.workspace).source_sha256,
        )

    @staticmethod
    def _reference_projection(receipt: dict[str, Any]) -> dict[str, Any]:
        """Small cached UI view; full graph/points/matrices stay in M1 evidence."""
        result = receipt["evaluation"]
        return {
            "stage": receipt["stage"],
            "outcome": result["outcome"],
            "checks": deepcopy(result["checks"]),
            "provenance": deepcopy(result["provenance"]),
            "evaluation_sha256": receipt["evaluation_sha256"],
            "selected_inputs_sha256": result["selected_inputs_sha256"],
            "reference_summary": deepcopy(result["reference_summary"]),
            "physical_authority": False,
            "meaning": "Nominal frame-chain, rigid-fit and dependency-graph diagnostics only. Eight physical reference components remain pending; no installed transform, calibrated feedback joints, whole-board reachability, motion or contact authority is established.",
        }

    @staticmethod
    def _noncontact_projection(receipt: dict[str, Any]) -> dict[str, Any]:
        """Cached gaps only; complete typed inputs/calculations remain retained."""
        result = receipt["evaluation"]
        return {
            "stage": receipt["stage"],
            "outcome": result["outcome"],
            "checks": deepcopy(result["checks"]),
            "provenance": deepcopy(result["provenance"]),
            "evaluation_sha256": receipt["evaluation_sha256"],
            "selected_inputs_sha256": result["selected_inputs_sha256"],
            "safe_summary": deepcopy(result["safe_summary"]),
            "physical_authority": False,
            "meaning": "Readiness gap diagnostics only: historical collision inventory and separate static requirements, synthetic accuracy controls, and unmeasured real-build terms. Nominal gaps remain BLOCKED; no noncontact motion, handoff, power or contact authority.",
        }

    def _noncontact_context(self, tx: Any) -> tuple[Any, dict[str, Any]]:
        from rocell.application.commissioning_rehearsal_reopen import (
            _read_evidence,
            _noncontact_binding,
        )
        from rocell.application.rehearsal_noncontact_stage import (
            read_noncontact_source_context,
        )

        if self._operator is None:
            raise WizardError(
                "NONCONTACT_OPERATOR_MISSING",
                "An exact retained noncontact diagnostic operator is required.",
            )
        snapshot = tx.snapshot()
        catalog = load_physical_onboarding_stage_catalog(self.workspace).source_sha256
        evidence = _read_evidence(self.directory, snapshot, self.source_sha256, catalog)
        binding, camera = _noncontact_binding(
            snapshot,
            evidence,
            self._operator,
            self.source_sha256,
            catalog,
            tx._audit_records(),
            read_noncontact_source_context(self.workspace),
            reference_workspace=self.workspace,
            directory=self.directory,
        )
        # The exact camera dataset is an independently checked dependency, not
        # a new image measurement or an input to synthetic accuracy controls.
        self._verify_capture(camera.document(), tx=tx)
        return binding, evidence

    def _collect_noncontact(self, tx: Any, cancellation: threading.Event) -> None:
        from rocell.application.commissioning_rehearsal_reopen import (
            _EVALUATED_OPEN_SCHEMAS,
            _EVALUATED_SCHEMAS,
        )
        from rocell.application import rehearsal_noncontact_stage as noncontact

        self._latest_noncontact = None
        self._check_cancelled(cancellation, "noncontact diagnostic opening")
        self._store_json(
            tx,
            _NONCONTACT_STAGE,
            self._camera_document(
                _EVALUATED_OPEN_SCHEMAS[_NONCONTACT_STAGE], _NONCONTACT_STAGE
            ),
            "No-device readiness gap diagnostic operator",
        )
        binding, _ = self._noncontact_context(tx)
        self._check_cancelled(cancellation, "noncontact diagnostic evaluation")
        evaluated = noncontact.evaluate_rehearsal_noncontact_stage(
            self.workspace, binding
        )
        noncontact.verify_rehearsal_noncontact_evidence(
            evaluated.canonical_bytes(),
            expected_binding=binding,
            expected_evidence_sha256=evaluated.evidence_sha256,
            expected_evaluator_source_sha256=hashlib.sha256(
                Path(noncontact.__file__).read_bytes()
            ).hexdigest(),
        )
        self._check_cancelled(cancellation, "noncontact diagnostic retention")
        receipt = self._camera_document(
            _EVALUATED_SCHEMAS[_NONCONTACT_STAGE], _NONCONTACT_STAGE
        )
        receipt.update(
            evaluation=evaluated.to_dict(), evaluation_sha256=evaluated.evidence_sha256
        )
        receipt = json.loads(_bytes(receipt))
        retained = self._store_json(
            tx,
            _NONCONTACT_STAGE,
            receipt,
            "Complete readiness gaps and typed accuracy diagnostics",
        )
        self._receipt, self._receipt_reference = receipt, retained
        self._latest_noncontact = self._noncontact_projection(receipt)
        self._retained_noncontact = deepcopy(receipt)

    def _verify_noncontact(self, tx: Any) -> Any:
        from rocell.application import rehearsal_noncontact_stage as noncontact

        assert self._receipt is not None and self._receipt_reference is not None
        binding, evidence = self._noncontact_context(tx)
        retained = evidence[self._receipt_reference.evidence_id]
        if retained.document() != self._receipt:
            raise WizardError(
                "NONCONTACT_RECEIPT_CHANGED",
                "Cached gaps differ from exact retained evidence.",
            )
        return noncontact.verify_rehearsal_noncontact_evidence(
            _bytes(retained.document()["evaluation"]),
            expected_binding=binding,
            expected_evidence_sha256=retained.document()["evaluation_sha256"],
            expected_evaluator_source_sha256=hashlib.sha256(
                Path(noncontact.__file__).read_bytes()
            ).hexdigest(),
        )

    def _reference_context(self, tx: Any) -> tuple[Any, dict[str, Any], dict[str, Any]]:
        from rocell.application.commissioning_rehearsal_reopen import (
            _read_evidence,
            _reference_binding,
        )
        from rocell.application.rehearsal_reference_stage import (
            read_reference_source_context,
        )

        if self._operator is None:
            raise WizardError(
                "REFERENCE_OPERATOR_MISSING",
                "An exact retained reference-stage operator is required.",
            )
        snapshot = tx.snapshot()
        catalog = load_physical_onboarding_stage_catalog(self.workspace).source_sha256
        evidence = _read_evidence(self.directory, snapshot, self.source_sha256, catalog)
        records = tx._audit_records()
        binding, camera = _reference_binding(
            snapshot,
            evidence,
            self._operator,
            self.source_sha256,
            catalog,
            records,
            read_reference_source_context(self.workspace),
            directory=self.directory,
        )
        # Actual retained bytes remain prerequisites, not synthetic math inputs.
        self._verify_capture(camera.document(), tx=tx)
        return binding, evidence, records

    def _collect_reference(self, tx: Any, cancellation: threading.Event) -> None:
        from rocell.application.commissioning_rehearsal_reopen import (
            _EVALUATED_OPEN_SCHEMAS,
            _EVALUATED_SCHEMAS,
        )
        from rocell.application import rehearsal_reference_stage as reference

        self._latest_reference = None
        self._check_cancelled(cancellation, "reference-stage opening")
        self._store_json(
            tx,
            _REFERENCE_STAGE,
            self._camera_document(
                _EVALUATED_OPEN_SCHEMAS[_REFERENCE_STAGE], _REFERENCE_STAGE
            ),
            "No-device nominal reference calibration stage operator",
        )
        binding, _, _ = self._reference_context(tx)
        self._check_cancelled(cancellation, "reference-stage numerical evaluation")
        evaluated = reference.evaluate_rehearsal_reference_stage(
            self.workspace, binding
        )
        # Validate the very bytes that will be published. This is pure retained
        # algebra/schema checking, not a second fit or fixture execution.
        reference.verify_rehearsal_reference_evidence(
            evaluated.canonical_bytes(),
            expected_binding=binding,
            expected_evidence_sha256=evaluated.evidence_sha256,
            expected_evaluator_source_sha256=hashlib.sha256(
                Path(reference.__file__).read_bytes()
            ).hexdigest(),
        )
        self._check_cancelled(cancellation, "reference-stage result publication")
        receipt = self._camera_document(
            _EVALUATED_SCHEMAS[_REFERENCE_STAGE], _REFERENCE_STAGE
        )
        receipt.update(
            evaluation=evaluated.to_dict(), evaluation_sha256=evaluated.evidence_sha256
        )
        # Keep cache and later retained JSON reads equal (no tuple/enum drift).
        receipt = json.loads(_bytes(receipt))
        retained = self._store_json(
            tx,
            _REFERENCE_STAGE,
            receipt,
            "Complete nominal reference graph and numerical evidence",
        )
        self._receipt, self._receipt_reference = receipt, retained
        self._latest_reference = self._reference_projection(receipt)

    def _verify_reference(self, tx: Any) -> Any:
        from rocell.application import rehearsal_reference_stage as reference

        assert self._receipt is not None and self._receipt_reference is not None
        binding, evidence, _ = self._reference_context(tx)
        retained = evidence[self._receipt_reference.evidence_id]
        if retained.document() != self._receipt:
            raise WizardError(
                "REFERENCE_RECEIPT_CHANGED",
                "Cached reference result differs from its exact retained evidence.",
            )
        return reference.verify_rehearsal_reference_evidence(
            _bytes(retained.document()["evaluation"]),
            expected_binding=binding,
            expected_evidence_sha256=retained.document()["evaluation_sha256"],
            expected_evaluator_source_sha256=hashlib.sha256(
                Path(reference.__file__).read_bytes()
            ).hexdigest(),
        )

    def _feedback_context(self, tx: Any) -> tuple[Any, Any]:
        from rocell.application.commissioning_rehearsal_reopen import (
            _read_evidence,
            _feedback_binding,
        )

        if self._operator is None:
            raise WizardError(
                "FEEDBACK_OPERATOR_MISSING",
                "An exact retained stage operator is required.",
            )
        snapshot = tx.snapshot()
        catalog = load_physical_onboarding_stage_catalog(self.workspace).source_sha256
        evidence = _read_evidence(self.directory, snapshot, self.source_sha256, catalog)
        binding, camera = _feedback_binding(
            snapshot, evidence, self._operator, self.source_sha256, catalog
        )
        self._verify_capture(camera.document(), tx=tx)
        return binding, evidence

    def _verify_feedback(self, tx: Any) -> Any:
        from rocell.application.commissioning_rehearsal_reopen import (
            _verify_evaluated_receipt,
        )

        assert self._receipt is not None and self._receipt_reference is not None
        snapshot = tx.snapshot()
        _, evidence = self._feedback_context(tx)
        retained = evidence[self._receipt_reference.evidence_id]
        if retained.document() != self._receipt:
            raise WizardError(
                "FEEDBACK_RECEIPT_CHANGED",
                "Cached feedback status differs from its exact retained receipt.",
            )
        return _verify_evaluated_receipt(
            snapshot,
            evidence,
            retained,
            self.source_sha256,
            load_physical_onboarding_stage_catalog(self.workspace).source_sha256,
            records=tx._audit_records(),
            directory=self.directory,
        )

    def _feedback_campaign(
        self,
        cancellation: threading.Event,
        *,
        owned: bool = False,
        scenario: str = "nominal",
    ) -> None:
        """Choose one incapable implementation; no fallback or replacement cell."""
        from rocell.application import arm_feedback_rehearsal_campaign as campaign
        from rocell.application.cell_commissioning_coordinator import (
            EnergizationEnvelope,
        )
        from rocell.application.commissioning_m1_persistence import (
            RehearsalAdmissionFacts,
        )
        from rocell.application.physical_onboarding_leases import LeaseSpec
        from rocell.application.physical_onboarding_attempts import canonical_json_bytes
        from rocell.application.rehearsal_feedback_stage import (
            feedback_plan,
            feedback_power_dependencies,
            feedback_evaluation,
        )
        from rocell.application.scoped_rehearsal_dispatch import (
            ScopedRehearsalDispatch,
        )

        self._clear_preview()
        self._feedback_diagnostic = self._latest_arm_feedback = None
        self._arm_feedback_process = None
        # Verify the complete predecessor chain under the existing stage lease.
        # No one-use campaign capability exists during this potentially slow read.
        with self._transaction() as tx:
            snapshot = tx.snapshot()
            if (
                snapshot.next_action.stage is not _FEEDBACK_STAGE
                or snapshot.next_action.stage_state is not V2StageState.WAITING_OPERATOR
            ):
                raise WizardError(
                    "FEEDBACK_STAGE_NOT_DUE", "Open the due feedback stage first."
                )
            binding, _ = self._feedback_context(tx)
        self._check_cancelled(cancellation, "feedback admission preparation")
        if owned:
            from rocell.application.rehearsal_feedback_binding import (
                owned_metadata_feedback_binding,
            )

            binding = owned_metadata_feedback_binding(binding)
        plan = feedback_plan(binding)
        campaign_directory = self.directory / "owned-arm-feedback"
        if owned:
            from rocell.application.owned_arm_feedback_rehearsal_campaign import (
                prepare_owned_arm_feedback_campaign,
            )

            # The exact fixed package is prepared before the short-lived energy
            # envelope, never during an inert view or retained-evidence reopen.
            worker: Any = prepare_owned_arm_feedback_campaign(
                plan,
                workspace=self.workspace,
                directory=campaign_directory,
                scenario=scenario,
            )
            self._check_cancelled(cancellation, "contained package preparation")
        else:
            executable_sha = hashlib.sha256(
                Path(campaign.__file__).read_bytes()
            ).hexdigest()
            worker = campaign.ArmFeedbackRehearsalCampaign(
                plan, worker_executable_sha256=executable_sha
            )
        registration = worker.registration()
        provisional = RegisteredActionRequest(
            self.cell_id,
            self.session_id,
            registration.action_id,
            "request-" + uuid.uuid4().hex,
            "1" * 64,
        )
        # Reuse the source-bound eight-epoch documents, adding this exact serial
        # dependency binding. Never use camera selection as controller identity.
        base = self._facts(
            replace(provisional, action_id="source-facts-only"), snapshot
        )
        epochs = tuple(
            {**document, "synthetic_feedback_binding_sha256": binding.binding_sha256}
            for document in base.configuration_epoch_documents
        )
        power_dependencies = feedback_power_dependencies(binding)
        self._feedback_admission = RehearsalAdmissionFacts(
            {
                **base.hazard_assessment_document,
                "provider_set": "INCAPABLE_ARM_FEEDBACK_ONLY",
                "synthetic_feedback_binding_sha256": binding.binding_sha256,
            },
            epochs,
            binding.selected_identity_document,
        )

        def preflight(tx: Any) -> Any:
            if tx.verification().challenge_sha256 != self._cached["challenge_sha256"]:
                raise WizardError(
                    "STALE_REHEARSAL_ADMISSION",
                    "State changed after the displayed feedback preview; nothing was dispatched.",
                )
            return tx.read_admission(provisional)

        def dispatch(window: ScopedRehearsalDispatch, admission: Any) -> Any:
            coordinator = CellCommissioningCoordinator(
                persistence=window,
                registrations=(registration,),
                workers={registration.worker_id: worker},
                retained_campaign_actions=(registration.action_id,),
                scoped_campaign_actions=(registration.action_id,) if owned else (),
            )
            self._check_cancelled(cancellation, "synthetic energy envelope issuance")
            # No power envelope is needed for read-only storage preflight.
            # Issue its one fresh synthetic observation only AFTER preflight,
            # never extend or replace an already prepared operation's envelope.
            now = time.monotonic_ns()
            envelope = EnergizationEnvelope(
                envelope_id="synthetic-energy-" + uuid.uuid4().hex,
                operation_sha256=registration.operation_sha256,
                power_topology_sha256=power_dependencies["power_topology_sha256"],
                safety_review_sha256=power_dependencies["safety_review_sha256"],
                installed_object_inventory_sha256=power_dependencies[
                    "installed_object_inventory_sha256"
                ],
                # Ledger canonical JSON includes its trailing newline, unlike
                # ordinary stage JSON. Keep the cross-layer digest exact.
                configuration_epoch_vector_sha256=hashlib.sha256(
                    canonical_json_bytes(tuple(_hash(document) for document in epochs))
                ).hexdigest(),
                operator_id=binding.operator_id,
                observer_id=plan.final_power_observation.observer_id,
                issued_at_ns=now,
                expires_at_ns=now + 30_000_000_000,
            )
            self._feedback_admission = replace(
                self._feedback_admission, envelope=envelope
            )
            request = replace(
                provisional, expected_challenge_sha256=admission.challenge_sha256
            )
            window.bind_request(request)
            permit = coordinator.prepare(request)
            return coordinator.execute(permit, cancellation=cancellation)

        leases = (
            LeaseSpec(LeaseLevel.CELL, self.cell_id),
            LeaseSpec(LeaseLevel.SESSION, self.session_id),
            LeaseSpec(LeaseLevel.ARM_CONTROLLER, self.cell_id),
        )
        try:
            # Both incapable implementations keep one qualified lease window
            # across preflight, prepare and execute. All admission/armed reads
            # stay fresh; only redundant release/reacquire work is removed.
            # Issue the original envelope after preflight and never renew it.
            # The second core context releases the real leases, preserving its
            # cleanup-failure hold before any successful UI publication.
            with ScopedRehearsalDispatch(
                persistence=self._store, leases=leases, request=provisional
            ) as window:
                admission = preflight(window.preflight_transaction)
                result = dispatch(window, admission)
        except BaseException:
            if worker.evidence is not None:
                # A late lease-exit failure can prevent execute() returning even
                # after full worker evidence was verified. Preserve historical
                # summaries without inventing a known coordinator result.
                self._feedback_diagnostic = {
                    "attempt_result": None,
                    "safe_summary": worker.evidence.safe_summary(),
                    "final_power_observation": worker.evidence.final_power_observation,
                    "retained_campaign_sha256": worker.evidence.evidence_sha256,
                    "raw_evidence_location": "M1_RETENTION_UNCONFIRMED_INSPECT_ORIGINAL_STORE",
                    "m1_retention": "UNCONFIRMED_AFTER_EXCEPTION",
                    "coordinator_completion": "UNCONFIRMED_EXCEPTION",
                    "physical_authority": False,
                }
                if owned:
                    self._feedback_diagnostic["arm_feedback_process"] = (
                        worker.evidence.process_summary()
                    )
                    self._feedback_diagnostic["controller_resolution"] = (
                        worker.evidence.resolution_diagnostics()
                    )
            raise
        finally:
            # No refresh, process restart or browser request can reuse an envelope.
            self._feedback_admission = None
        known = result.state is AttemptState.SEALED_KNOWN
        self._feedback_diagnostic = {
            # asdict retains str-enum instances. Normalize this exact typed
            # public projection to JSON primitives; the complete private M1
            # campaign record and its hashes are not changed or republished.
            "attempt_result": json.loads(_bytes(asdict(result))),
            "safe_summary": worker.evidence.safe_summary() if worker.evidence else None,
            "final_power_observation": (
                worker.evidence.final_power_observation if worker.evidence else None
            ),
            "retained_campaign_sha256": (
                worker.evidence.evidence_sha256 if worker.evidence else None
            ),
            "raw_evidence_location": "ORIGINAL_M1_CAMPAIGN_RECORD_NOT_PUBLIC_STATUS",
            "physical_authority": False,
        }
        if owned and worker.evidence is not None:
            self._arm_feedback_process = worker.evidence.process_summary()
            self._feedback_diagnostic["arm_feedback_process"] = deepcopy(
                self._arm_feedback_process
            )
            self._feedback_diagnostic["controller_resolution"] = (
                worker.evidence.resolution_diagnostics()
            )
        if worker.evidence is not None:
            evaluated = feedback_evaluation(
                binding, worker.evidence, coordinator_known=known
            )
            self._latest_arm_feedback = evaluated.to_dict()
        self._refresh()
        if not known:
            self._failed = True
            return
        if worker.evidence is None:
            raise WizardError(
                "FEEDBACK_RETAINED_EVIDENCE_MISSING",
                "Known result has no complete evidence; inspect/export, never replay.",
            )
        self._check_cancelled(cancellation, "feedback stage receipt publication")
        receipt = self._camera_document(
            (
                "rocell.rehearsal_owned_feedback_receipt.v1"
                if owned
                else "rocell.rehearsal_feedback_receipt.v1"
            ),
            _FEEDBACK_STAGE,
        )
        receipt.update(
            evaluation=evaluated.to_dict(),
            evaluation_sha256=evaluated.evidence_sha256,
            attempt_result=asdict(result),
            retained_campaign_sha256=worker.evidence.evidence_sha256,
        )
        if owned:
            receipt.update(
                scenario=scenario,
                campaign_directory=str(campaign_directory),
                arm_feedback_process=deepcopy(self._arm_feedback_process),
            )
        # Cache exactly the JSON representation published below. Dataclass
        # tuples (reason codes/evidence hashes) otherwise differ from retained
        # JSON lists at the strict assessment/readback equality boundary.
        receipt = json.loads(_bytes(receipt))
        with self._transaction() as tx:
            # Complete private evidence is already durably retained by the
            # coordinator; this receipt only projects it for stage assessment.
            self._check_cancelled(cancellation, "feedback stage receipt retention")
            reference = self._store_json(
                tx,
                _FEEDBACK_STAGE,
                receipt,
                "Retained incapable feedback campaign projection",
            )
            self._receipt, self._receipt_reference = receipt, reference

    def _camera_document(
        self, schema: str, stage: PhysicalOnboardingStage
    ) -> dict[str, Any]:
        return {
            "schema": schema,
            "composition": INCAPABLE_COMPOSITION,
            "stage": stage.value,
            "session_id": self.session_id,
            "cell_id": self.cell_id,
            "workspace_source_sha256": self.source_sha256,
            "operator_id": self._operator,
            "catalog_sha256": load_physical_onboarding_stage_catalog(
                self.workspace
            ).source_sha256,
            "physical_observation": False,
        }

    def _settings(self, values: dict[str, Any]) -> None:
        settings = camera_settings(values["brightness_offset"])
        with self._transaction() as tx:
            stage = tx.snapshot().next_action.stage
            document = self._camera_document(
                "rocell.rehearsal_camera_settings.v1", stage
            )
            document.update(settings=settings, settings_epoch=_hash(settings))
            self._store_json(tx, stage, document, "Prepared synthetic camera settings")
            self._camera_settings = document

    def _campaign(
        self,
        values: dict[str, Any],
        cancellation: threading.Event,
        *,
        owned: bool = False,
    ) -> None:
        self._clear_preview()
        self._clear_camera_diagnostics()
        snapshot = self._store.snapshot(self.session_id)
        stage = snapshot.next_action.stage
        if (
            stage not in _CAMERA_STAGES
            or self._selected is None
            or self._camera_settings is None
        ):
            raise WizardError(
                "CAMERA_PREREQUISITES_MISSING",
                "Review camera identity before a camera campaign.",
            )
        count = values["frame_count"]
        if type(count) is not int or not 1 <= count <= 4:
            raise WizardError(
                "CAMERA_FRAME_BUDGET",
                "Choose one to four synthetic frame observations.",
            )
        fault = values["fault"]
        from rocell.application.owned_camera_rehearsal_campaign import (
            FAULTS as OWNED_FAULTS,
            OwnedBinaryCameraWorker,
        )

        if fault not in (
            OWNED_FAULTS
            if owned
            else {"none", "identity-mismatch", "cleanup-uncertain"}
        ):
            raise WizardError("UNKNOWN_CAMERA_SCENARIO", "Unknown synthetic scenario.")
        plan = {
            "composition": INCAPABLE_COMPOSITION,
            "selected_camera": self._selected,
            "mode": {
                "width": 5472,
                "height": 3648,
                "fps_numerator": 9,
                "fps_denominator": 1,
                "pixel_format": "YUY2",
            },
            "frame_count": count,
            "fault": fault,
            "settings": self._camera_settings["settings"],
            "settings_epoch": self._camera_settings["settings_epoch"],
            "native_frame_bytes_generated": fault == "none",
            "binary_artifact_budget_bytes": 2 * FRAME_BYTES * count + 128 * 1024 * 1024,
            "artifact_qualification": "DIAGNOSTIC_ONLY_NOT_M1_QUALIFIED",
        }
        from rocell.application import camera_rehearsal_campaign

        executable_sha = hashlib.sha256(
            Path(camera_rehearsal_campaign.__file__).read_bytes()
        ).hexdigest()
        worker: Any = (
            None
            if owned
            else SyntheticBinaryCameraWorker(
                self.workspace,
                self.directory,
                executable_sha256=executable_sha,
                source_sha256=self.source_sha256,
                frame_count=count,
                fault=fault,
                settings=plan["settings"],
                settings_epoch=plan["settings_epoch"],
            )
        )
        registration = CampaignRegistration(
            action_id="rehearsal-camera-campaign",
            stage=stage,
            effect_class=EffectClass.BOUNDED_CAMERA_CAMPAIGN,
            worker_id="incapable-camera-fixture",
            worker_executable_sha256=executable_sha,
            operation_sha256=_hash(plan),
            resources=(LeaseLevel.CAMERA,),
            budget=CampaignBudget(
                timeout_ms=60_000,
                maximum_output_bytes=4096,
                maximum_opens=1,
                maximum_reads=count,
                maximum_writes=0,
                maximum_frames=count,
                maximum_closes=1,
            ),
        )
        if owned:
            if self._probe_attempted:
                with self._transaction() as tx:
                    self._verify_configuration_context(tx, require_configuration=True)
            worker = OwnedBinaryCameraWorker(
                self.workspace,
                self.directory,
                source_sha256=self.source_sha256,
                frame_count=count,
                fault=fault,
                settings=self._camera_settings["settings"],
                settings_epoch=self._camera_settings["settings_epoch"],
                selected_camera=self._selected,
                configuration=self._electronic_configuration,
                capabilities=(
                    self._camera_probe.capabilities()
                    if self._electronic_configuration is not None
                    else None
                ),
            )
            plan, registration = worker.plan(), worker.registration(stage)
        try:
            result = self._execute_camera_worker(
                worker, registration, cancellation, retained=owned
            )
        except BaseException:
            if owned:
                try:
                    self._retain_camera_diagnostics(worker, None)
                except Exception:
                    # Preserve the primary dispatch/retention exception. Invalid
                    # evidence cannot create a diagnostic success or replace it.
                    pass
            raise
        if owned:
            self._retain_camera_diagnostics(worker, result)
        self._receipt = {
            "schema": "rocell.rehearsal_camera_campaign.v2",
            "composition": INCAPABLE_COMPOSITION,
            "session_id": self.session_id,
            "stage": stage.value,
            "operator_id": self._operator,
            "workspace_source_sha256": self.source_sha256,
            "plan": plan,
            "attempt_result": asdict(result),
            "capture_dataset": worker.capture.to_dict() if worker.capture else None,
            "physical_observation": False,
        }
        if owned:
            self._receipt.update(
                retained_campaign_sha256=(
                    worker.evidence.evidence_sha256 if worker.evidence else None
                ),
                camera_process=deepcopy(self._camera_process),
            )
            if self._electronic_configuration is not None:
                self._receipt["camera_readback"] = deepcopy(worker.readback)
        self._receipt = json.loads(_bytes(self._receipt))
        self._refresh()
        if result.state is not AttemptState.SEALED_KNOWN:
            self._failed = True
            return
        if owned and (
            worker.evidence is None
            or self._camera_process is None
            or self._camera_process["status"] != "RETAINED_COMPLETE_REHEARSAL"
            or worker.capture is None
        ):
            raise WizardError(
                "OWNED_CAMERA_EVIDENCE_MISSING",
                "Known campaign lacks complete retained process/capture evidence; inspect without replay.",
            )
        self._check_cancelled(cancellation, "camera stage receipt publication")
        if worker.capture is not None:
            self._latest_capture = worker.capture.to_dict()
            self._latest_preview = (
                worker.capture.latest_preview.png_bytes
                if worker.capture.latest_preview
                else None
            )
        with self._transaction() as tx:
            # Acquiring/validating durable storage can take time. A Stop during
            # that read must preserve the campaign record without publishing a
            # new assessable stage receipt after cancellation.
            self._check_cancelled(cancellation, "camera stage receipt retention")
            self._receipt_reference = self._store_json(
                tx, stage, self._receipt, "Synthetic camera campaign"
            )
            if owned and self._electronic_configuration is not None:
                self._camera_readback = deepcopy(worker.readback)

    def _execute_camera_worker(
        self,
        worker: Any,
        registration: CampaignRegistration,
        cancellation: threading.Event,
        *,
        retained: bool,
    ) -> Any:
        """One admission path for finite probe and capture; never auto-retries."""
        from rocell.application.physical_onboarding_leases import LeaseSpec

        coordinator = CellCommissioningCoordinator(
            persistence=self._store,
            registrations=(registration,),
            workers={registration.worker_id: worker},
            retained_campaign_actions=(registration.action_id,) if retained else (),
        )
        provisional = RegisteredActionRequest(
            self.cell_id,
            self.session_id,
            registration.action_id,
            "request-" + uuid.uuid4().hex,
            "1" * 64,
        )
        leases = (
            LeaseSpec(LeaseLevel.CELL, self.cell_id),
            LeaseSpec(LeaseLevel.SESSION, self.session_id),
            LeaseSpec(LeaseLevel.CAMERA, self.cell_id),
        )
        with self._store.transaction(leases) as tx:
            if tx.verification().challenge_sha256 != self._cached["challenge_sha256"]:
                raise WizardError(
                    "STALE_REHEARSAL_ADMISSION",
                    "Durable state changed after preview; no campaign was dispatched.",
                )
            admission = tx.read_admission(provisional)
        self._check_cancelled(cancellation, "camera permit preparation")
        request = replace(
            provisional, expected_challenge_sha256=admission.challenge_sha256
        )
        permit = coordinator.prepare(request)
        return coordinator.execute(permit, cancellation=cancellation)

    def _probe(self, values: dict[str, Any], cancellation: threading.Event) -> None:
        from .owned_camera_probe_campaign import OwnedCameraProbeWorker, STAGE

        assert self._selected is not None
        self._probe_attempted = True
        self._clear_preview()
        self._clear_camera_diagnostics()
        worker = OwnedCameraProbeWorker(
            self.workspace,
            self.directory,
            source_sha256=self.source_sha256,
            selected_camera=self._selected,
            fault=values["fault"],
        )
        result = self._execute_camera_worker(
            worker, worker.registration(), cancellation, retained=True
        )
        artifact = worker.evidence
        if artifact is not None:
            self._camera_probe = artifact
            self._camera_process_diagnostic = {
                "camera_probe": artifact.view(),
                "retained_probe_sha256": artifact.evidence_sha256,
                "attempt_result": json.loads(_bytes(asdict(result))),
                "raw_evidence_location": "ORIGINAL_M1_CAMPAIGN_RECORD_NOT_PUBLIC_STATUS",
                "physical_authority": False,
            }
        self._refresh()
        if result.state is not AttemptState.SEALED_KNOWN:
            self._failed = True
            return
        if artifact is None or artifact.view()["status"] != "COMPLETE_PROBE_REHEARSAL":
            raise WizardError(
                "CAMERA_PROBE_EVIDENCE_MISSING",
                "A known probe lacks complete retained evidence; do not replay.",
            )
        document = self._camera_document(
            "rocell.rehearsal_camera_probe_receipt.v1", STAGE
        )
        document.update(
            plan=worker.plan(),
            attempt_result=json.loads(_bytes(asdict(result))),
            retained_probe_sha256=artifact.evidence_sha256,
            probe=artifact.view(),
        )
        with self._transaction() as tx:
            from .commissioning_rehearsal_reopen import _verify_camera_probe_receipt

            _verify_camera_probe_receipt(
                document,
                self.source_sha256,
                tx._audit_records(),
                directory=self.directory,
            )
            self._check_cancelled(cancellation, "camera probe receipt retention")
            self._store_json(
                tx,
                STAGE,
                document,
                "Retained incapable camera capabilities; no settings applied",
            )
            self._probe_receipt = document

    def _configuration_context(self, tx: Any) -> Any:
        from .commissioning_rehearsal_reopen import (
            _read_evidence,
            _verify_camera_configuration_context,
        )

        evidence = _read_evidence(
            self.directory,
            tx.snapshot(),
            self.source_sha256,
            load_physical_onboarding_stage_catalog(self.workspace).source_sha256,
        )
        return _verify_camera_configuration_context(
            evidence,
            tx._audit_records(),
            self.source_sha256,
            self.session_id,
            directory=self.directory,
        )

    def _verify_configuration_context(
        self, tx: Any, *, require_configuration: bool
    ) -> Any:
        context = self._configuration_context(tx)
        probe_doc, probe, config_doc, configuration = context
        if (
            probe_doc != self._probe_receipt
            or config_doc != self._configuration_receipt
            or (require_configuration and configuration is None)
            or (
                probe is not None
                and (
                    self._camera_probe is None
                    or probe.payload != self._camera_probe.payload
                )
            )
            or (
                configuration is not None
                and (
                    self._electronic_configuration is None
                    or configuration.payload != self._electronic_configuration.payload
                )
            )
        ):
            raise WizardError(
                "CAMERA_CONFIGURATION_CHANGED",
                "Retained probe/configuration differs from its exact prepared state.",
            )
        return context

    def _configure_camera(
        self, values: dict[str, Any], cancellation: threading.Event
    ) -> None:
        from .wizard_camera_configuration import (
            stage_wizard_camera_configuration,
            effective_camera_settings_epoch,
        )

        assert self._camera_settings is not None and self._selected is not None
        with self._transaction() as tx:
            _, probe, _, _ = self._verify_configuration_context(
                tx, require_configuration=False
            )
            if probe is None:
                raise WizardError(
                    "CAMERA_PROBE_REQUIRED", "Retain the exact capability probe first."
                )
            candidate = stage_wizard_camera_configuration(
                probe.capabilities(),
                values,
                source_sha256=self.source_sha256,
                selected_identity_sha256=_hash(self._selected),
            )
            document = self._camera_document(
                "rocell.rehearsal_camera_configuration_receipt.v1", _CAMERA_STAGES[0]
            )
            document.update(
                probe_evidence_sha256=probe.evidence_sha256,
                configuration=candidate.to_dict(),
                electronic_settings_epoch=candidate.settings_epoch,
                synthetic_settings_epoch=self._camera_settings["settings_epoch"],
                effective_settings_epoch=effective_camera_settings_epoch(
                    self._camera_settings["settings_epoch"], candidate
                ),
            )
            self._check_cancelled(cancellation, "camera configuration retention")
            self._store_json(
                tx,
                _CAMERA_STAGES[0],
                document,
                "Immutable electronic camera intent; not yet applied",
            )
            self._configuration_receipt = document
            self._electronic_configuration = candidate

    @staticmethod
    def _check_cancelled(cancellation: threading.Event, boundary: str) -> None:
        if cancellation.is_set():
            raise WizardError(
                "REHEARSAL_CANCELLED_BEFORE_PUBLICATION",
                f"Stop arrived before {boundary}. Preserve retained state and inspect before any fresh explicit review; nothing is replayed.",
            )

    def _assess(self, cancellation: threading.Event) -> None:
        assert self._receipt is not None and self._receipt_reference is not None
        with self._transaction() as tx:
            snapshot = tx.snapshot()
            stage = snapshot.next_action.stage
            reasons: list[str] = []
            receipt = self._receipt
            if (
                receipt.get("composition") != INCAPABLE_COMPOSITION
                or receipt.get("physical_observation") is not False
            ):
                reasons.append("NOT_SYNTHETIC_EVIDENCE")
            if (
                receipt.get("session_id") != self.session_id
                or receipt.get("stage") != stage.value
                or receipt.get("workspace_source_sha256") != self.source_sha256
            ):
                reasons.append("RECEIPT_BINDING_MISMATCH")
            if (
                stage is PhysicalOnboardingStage.CAMERA_IDENTITY
                and receipt.get("candidate", {}).get("model") != "B0477"
            ):
                reasons.append("SYNTHETIC_CAMERA_MODEL_MISMATCH")
            if (
                stage in _CAMERA_STAGES
                and receipt.get("attempt_result", {}).get("state")
                != AttemptState.SEALED_KNOWN
            ):
                reasons.append("CAMERA_ATTEMPT_NOT_SEALED_KNOWN")
            if stage in _CAMERA_STAGES:
                dataset = receipt.get("capture_dataset")
                if not dataset:
                    reasons.append("NO_RETAINED_BINARY_DATASET")
                else:
                    self._verify_capture(receipt, tx=tx)
                if (
                    self._camera_settings is None
                    or receipt["plan"]["settings_epoch"]
                    != self._camera_settings["settings_epoch"]
                ):
                    reasons.append("CAMERA_SETTINGS_EPOCH_MISMATCH")
            if stage in _OPTICS_STAGES:
                evaluated = self._verify_optics(tx)
                reasons.extend(
                    "OPTICS_CHECK_FAILED:" + row["check_id"]
                    for row in evaluated.checks
                    if not row["passed"]
                )
            if stage in _ARM_SETUP_STAGES:
                from rocell.application.commissioning_rehearsal_reopen import (
                    _evaluation_reason_prefix,
                )

                evaluated = self._verify_arm_setup(tx)
                reasons.extend(
                    _evaluation_reason_prefix(stage) + row["check_id"]
                    for row in evaluated.checks
                    if not row["passed"]
                )
            if stage is _FEEDBACK_STAGE:
                evaluated = self._verify_feedback(tx)
                reasons.extend(
                    "FEEDBACK_CHECK_FAILED:" + row["check_id"]
                    for row in evaluated.checks
                    if not row["passed"]
                )
            if stage is _REFERENCE_STAGE:
                evaluated = self._verify_reference(tx)
                reasons.extend(
                    "REFERENCE_CHECK_FAILED:" + row["check_id"]
                    for row in evaluated.checks
                    if not row["passed"]
                )
            if stage is _NONCONTACT_STAGE:
                evaluated = self._verify_noncontact(tx)
                reasons.extend(
                    "NONCONTACT_CHECK_FAILED:" + row["check_id"]
                    for row in evaluated.checks
                    if not row["passed"]
                )
            self._check_cancelled(cancellation, "assessment publication")
            assessment = {
                "schema": "rocell.rehearsal_assessment.v1",
                "composition": INCAPABLE_COMPOSITION,
                "session_id": self.session_id,
                "stage": stage.value,
                "source_binding_sha256": snapshot.header.source_binding_sha256,
                "pre_assessment_head_sha256": snapshot.head.head_sha256,
                "receipt_sha256": _hash(receipt),
                "receipt_evidence_id": self._receipt_reference.evidence_id,
                "outcome": "BLOCKED" if reasons else "PASS",
                "reason_codes": reasons,
                "meaning": "Synthetic workflow acceptance only; no physical prerequisite is closed.",
            }
            assessment["assessment_sha256"] = _hash(assessment)
            reference = self._store_json(
                tx, stage, assessment, "Pure rehearsal assessment"
            )
            self._check_cancelled(cancellation, "assessment stage-state commit")
            tx.commit_stage_state(
                stage,
                V2StageState.REVIEW_PENDING,
                occurred_at_ns=self._time(snapshot),
                detail_code="REHEARSAL_ASSESSMENT_READY",
                expected_head_sha256=snapshot.head.head_sha256,
                evidence=(self._receipt_reference, reference),
            )
            self._assessment, self._assessment_reference = assessment, reference

    def _verify_capture(self, receipt: dict[str, Any], *, tx: Any) -> None:
        from rocell.application.windows_camera_capture_ingest import (
            verify_windows_capture_ingest,
        )

        assert self._camera_settings is not None and self._selected is not None
        capture = receipt["capture_dataset"]
        try:
            relative = Path(capture["envelope_path"]).relative_to(self.directory)
        except ValueError as error:
            raise WizardError(
                "CAPTURE_OUTSIDE_SESSION",
                "The saved capture is outside this exact rehearsal store.",
            ) from error
        if (
            len(relative.parts) != 4
            or re.fullmatch(r"binary-fixture-[0-9a-f]{32}", relative.parts[0]) is None
            or relative.parts[1] != "datasets"
        ):
            raise WizardError(
                "CAPTURE_OUTSIDE_SESSION",
                "The saved capture does not use this session's assigned binary artifact layout.",
            )
        sealed_hashes = (
            receipt["attempt_result"].get("receipt", {}).get("evidence_sha256s", ())
        )
        owned = (
            receipt["plan"].get("process_backend") == "OWNED_INCAPABLE_CAMERA_PROCESS"
        )
        # Audited reservations, not a mutable UI marker, identify the retained
        # process lane. Removing its marker must not downgrade verification.
        records = tx._audit_records()
        owned_reserved = any(
            record["kind"] == "EXACT_REQUEST_RESERVED"
            and record["data"].get("attempt_id")
            == receipt["attempt_result"]["attempt_id"]
            and record["data"]["permit"]["registration"]["action_id"]
            == "rehearsal-owned-camera-campaign"
            for record in records.values()
        )
        # Retained auxiliary evidence, not a mutable UI marker, identifies a
        # session that chose probe-based configuration. Never downgrade it.
        probe_reserved = any(
            record["kind"] == "EXACT_REQUEST_RESERVED"
            and record["data"]["permit"]["registration"]["action_id"]
            == "rehearsal-owned-camera-probe"
            for record in records.values()
        )
        configuration = config_doc = None
        if (
            probe_reserved
            or self._probe_attempted
            or "electronic_configuration" in receipt["plan"]
        ):
            probe_doc, probe, config_doc, configuration = (
                self._verify_configuration_context(tx, require_configuration=True)
            )
            if (
                not owned
                or configuration is None
                or (
                    receipt["plan"].get("electronic_configuration")
                    != configuration.to_dict()
                    or receipt["plan"].get("effective_settings_epoch")
                    != config_doc["effective_settings_epoch"]
                    or receipt["plan"].get("probe_evidence_sha256")
                    != probe.evidence_sha256
                )
            ):
                raise WizardError(
                    "CAMERA_CONFIGURATION_DOWNGRADE",
                    "Capture does not bind the retained electronic configuration.",
                )
        if owned or owned_reserved:
            from rocell.application.commissioning_rehearsal_reopen import (
                _verify_owned_camera_campaign,
                _read_evidence,
            )

            if configuration is not None:
                evidence = _read_evidence(
                    self.directory,
                    tx.snapshot(),
                    self.source_sha256,
                    load_physical_onboarding_stage_catalog(
                        self.workspace
                    ).source_sha256,
                )
                _verify_owned_camera_campaign(
                    receipt, self.source_sha256, records, evidence=evidence
                )
            else:
                _verify_owned_camera_campaign(receipt, self.source_sha256, records)
        sealed = owned or (
            capture["envelope_sha256"] in sealed_hashes
            and capture["dataset"]["manifest_sha256"] in sealed_hashes
        )
        if (
            not sealed
            or receipt["plan"]["selected_camera"] != self._selected
            or receipt["plan"]["settings"] != self._camera_settings["settings"]
            or receipt["plan"]["frame_count"] != capture["dataset"]["frames"]
        ):
            raise WizardError(
                "RETAINED_CAPTURE_BINDING_MISMATCH",
                "The retained capture is not the exact identity/settings/dataset sealed by this attempt.",
            )
        verify_windows_capture_ingest(
            capture,
            expected_source_sha256=self.source_sha256,
            expected_settings_epoch=(
                config_doc["effective_settings_epoch"]
                if configuration is not None and config_doc is not None
                else self._camera_settings["settings_epoch"]
            ),
            expected_campaign_id=receipt["attempt_result"]["attempt_id"],
            expected_endpoint_sha256=hashlib.sha256(
                self._selected["endpoint"].encode("utf-8")
            ).hexdigest(),
        )

    def _review(self, values: dict[str, Any], cancellation: threading.Event) -> None:
        assert self._assessment is not None and self._assessment_reference is not None
        reviewer = _actor(values["reviewer_id"])
        if reviewer == self._operator or values.get("accept_assessment") is not True:
            raise WizardError(
                "EXACT_REVIEW_REQUIRED",
                "A distinct reviewer must accept the exact current synthetic assessment.",
            )
        with self._transaction() as tx:
            snapshot = tx.snapshot()
            stage = snapshot.next_action.stage
            assessment = self._assessment
            if stage in _CAMERA_STAGES:
                # Diagnostic datasets are not M1-qualified. Verify again before
                # recording acceptance rather than trusting a prior content read.
                assert self._receipt is not None
                self._verify_capture(self._receipt, tx=tx)
            if stage in _OPTICS_STAGES:
                evaluated = self._verify_optics(tx)
                reasons = [
                    "OPTICS_CHECK_FAILED:" + row["check_id"]
                    for row in evaluated.checks
                    if not row["passed"]
                ]
                if assessment["reason_codes"] != reasons or assessment["outcome"] != (
                    "BLOCKED" if reasons else "PASS"
                ):
                    raise WizardError(
                        "OPTICS_ASSESSMENT_CHANGED",
                        "The exact retained optics checks do not support this assessment outcome.",
                    )
            if stage in _ARM_SETUP_STAGES:
                from rocell.application.commissioning_rehearsal_reopen import (
                    _evaluation_reason_prefix,
                )

                evaluated = self._verify_arm_setup(tx)
                reasons = [
                    _evaluation_reason_prefix(stage) + row["check_id"]
                    for row in evaluated.checks
                    if not row["passed"]
                ]
                if assessment["reason_codes"] != reasons or assessment["outcome"] != (
                    "BLOCKED" if reasons else "PASS"
                ):
                    raise WizardError(
                        "ARM_SETUP_ASSESSMENT_CHANGED",
                        "The exact retained arm setup checks do not support this assessment outcome.",
                    )
            if stage is _FEEDBACK_STAGE:
                evaluated = self._verify_feedback(tx)
                reasons = [
                    "FEEDBACK_CHECK_FAILED:" + row["check_id"]
                    for row in evaluated.checks
                    if not row["passed"]
                ]
                if assessment["reason_codes"] != reasons or assessment["outcome"] != (
                    "BLOCKED" if reasons else "PASS"
                ):
                    raise WizardError(
                        "FEEDBACK_ASSESSMENT_CHANGED",
                        "The exact retained serial exchange does not support this assessment.",
                    )
            if stage is _REFERENCE_STAGE:
                evaluated = self._verify_reference(tx)
                reasons = [
                    "REFERENCE_CHECK_FAILED:" + row["check_id"]
                    for row in evaluated.checks
                    if not row["passed"]
                ]
                if assessment["reason_codes"] != reasons or assessment["outcome"] != (
                    "BLOCKED" if reasons else "PASS"
                ):
                    raise WizardError(
                        "REFERENCE_ASSESSMENT_CHANGED",
                        "The exact retained reference checks do not support this assessment.",
                    )
            if stage is _NONCONTACT_STAGE:
                evaluated = self._verify_noncontact(tx)
                reasons = [
                    "NONCONTACT_CHECK_FAILED:" + row["check_id"]
                    for row in evaluated.checks
                    if not row["passed"]
                ]
                if assessment["reason_codes"] != reasons or assessment["outcome"] != (
                    "BLOCKED" if reasons else "PASS"
                ):
                    raise WizardError(
                        "NONCONTACT_ASSESSMENT_CHANGED",
                        "Retained readiness gaps do not support this assessment.",
                    )
            if (
                assessment["session_id"] != self.session_id
                or assessment["stage"] != stage.value
                or assessment["receipt_sha256"] != _hash(self._receipt)
            ):
                raise WizardError(
                    "STALE_ASSESSMENT",
                    "The assessment does not bind this receipt and stage.",
                )
            self._check_cancelled(cancellation, "review publication")
            review = {
                "schema": "rocell.rehearsal_review.v1",
                "composition": INCAPABLE_COMPOSITION,
                "session_id": self.session_id,
                "stage": stage.value,
                "assessment_sha256": assessment["assessment_sha256"],
                "reviewed_head_sha256": snapshot.head.head_sha256,
                "reviewer_id": reviewer,
                "operator_id": self._operator,
                "decision": "ACCEPT_EXACT_ASSESSMENT",
                "physical_release_effect": "NONE",
            }
            reference = self._store_json(
                tx, stage, review, "Exact synthetic assessment review"
            )
            self._check_cancelled(cancellation, "review stage-state commit")
            tx.commit_stage_state(
                stage,
                V2StageState(assessment["outcome"]),
                occurred_at_ns=self._time(snapshot),
                detail_code="REHEARSAL_ASSESSMENT_REVIEWED",
                expected_head_sha256=snapshot.head.head_sha256,
                evidence=(
                    self._receipt_reference,
                    self._assessment_reference,
                    reference,
                ),
            )
            if (
                stage is PhysicalOnboardingStage.CAMERA_IDENTITY
                and assessment["outcome"] == "PASS"
            ):
                assert self._receipt is not None
                self._selected = deepcopy(self._receipt["candidate"])
            self._receipt, self._assessment = None, None
            self._receipt_reference, self._assessment_reference = None, None

    def perform(
        self,
        action_id: str,
        values: dict[str, Any],
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
    ) -> dict[str, Any]:
        if action_id not in ACTIONS:
            raise WizardError(
                "UNKNOWN_REHEARSAL_ACTION", "The rehearsal action is not registered."
            )
        if values.get("_view_sha256") != _hash(self.view()):
            raise WizardError(
                "STALE_REHEARSAL_VIEW",
                "Rehearsal state changed after preparation; inspect current state.",
            )
        reason = self.blocked_reason(action_id)
        if reason:
            raise WizardError("REHEARSAL_ACTION_BLOCKED", reason)
        if cancellation.is_set():
            raise WizardError(
                "REHEARSAL_CANCELLED_BEFORE_MUTATION",
                "Cancelled before storage mutation; nothing was replayed.",
            )
        progress(
            "Explicit qualified-storage rehearsal; all camera observations are synthetic and all physical effects remain zero."
        )
        if cancellation.is_set():
            raise WizardError(
                "REHEARSAL_CANCELLED_BEFORE_MUTATION",
                "Cancelled during progress/diagnostic logging before storage mutation.",
            )
        try:
            if action_id == "rehearsal_initialize":
                self._initialize()
            elif action_id == "rehearsal_discover":
                self._discover()
            elif action_id == "rehearsal_reopen":
                self._reopen(values, cancellation)
            elif action_id == "rehearsal_record_operator":
                self._record_operator(values)
            elif action_id == "rehearsal_collect":
                self._collect(values, cancellation)
            elif action_id == "rehearsal_camera_campaign":
                self._campaign(values, cancellation)
            elif action_id == "rehearsal_owned_camera_campaign":
                self._campaign(values, cancellation, owned=True)
            elif action_id == "rehearsal_arm_feedback_campaign":
                self._feedback_campaign(cancellation)
            elif action_id == "rehearsal_owned_arm_feedback_campaign":
                self._feedback_campaign(
                    cancellation, owned=True, scenario=values["scenario"]
                )
            elif action_id == "rehearsal_camera_settings":
                self._settings(values)
            elif action_id == "rehearsal_camera_probe":
                self._probe(values, cancellation)
            elif action_id == "rehearsal_camera_configuration":
                self._configure_camera(values, cancellation)
            elif action_id == "rehearsal_assess":
                self._assess(cancellation)
            elif action_id == "rehearsal_review":
                self._review(values, cancellation)
            if self._store is not None and action_id not in {
                "rehearsal_discover",
                "rehearsal_reopen",
            }:
                self._refresh(expected_change=action_id != "rehearsal_refresh")
        except Exception:
            # No automatic restart, repair, repeated publication or campaign.
            self._failed = True
            self._configuration_hidden = True
            self._clear_preview()
            self._latest_optics = None
            self._cached["optics_evaluation"] = None
            self._latest_arm_identity = self._latest_power = None
            self._latest_arm_feedback = None
            self._arm_feedback_process = None
            self._cached["arm_feedback_evaluation"] = None
            self._cached["arm_feedback_process"] = None
            self._latest_reference = None
            self._cached["reference_evaluation"] = None
            self._latest_noncontact = None
            self._cached["noncontact_evaluation"] = None
            self._cached["arm_identity_evaluation"] = self._cached[
                "power_evaluation"
            ] = None
            self._cached["status"] = "HELD"
            raise
        failed = self._failed or (
            action_id == "rehearsal_reopen"
            and self._cached["reopen_result"]["status"] != "OPENED"
        )
        steps = [
            {
                "name": "durable-commissioning-rehearsal",
                "exit_code": 1 if failed else 0,
                "report": self.view(),
            }
        ]
        if (
            action_id == "rehearsal_collect"
            and self._receipt
            and self._receipt.get("schema")
            in {
                "rocell.rehearsal_optics_receipt.v1",
                "rocell.rehearsal_arm_identity_receipt.v1",
                "rocell.rehearsal_power_receipt.v1",
                "rocell.rehearsal_reference_receipt.v1",
                "rocell.rehearsal_noncontact_receipt.v1",
            }
        ):
            # Full technical data is available in the bounded operation result
            # and ordinary diagnostic exports, while cached stage UI stays small.
            # The original immutable M1 receipt outlives result-history retention.
            steps.append(
                {
                    "name": (
                        "retained-substantive-optics-evaluation"
                        if self._receipt["stage"] in {s.value for s in _OPTICS_STAGES}
                        else (
                            "retained-substantive-reference-evaluation"
                            if self._receipt["stage"] == _REFERENCE_STAGE.value
                            else (
                                "retained-substantive-noncontact-evaluation"
                                if self._receipt["stage"] == _NONCONTACT_STAGE.value
                                else "retained-substantive-arm-setup-evaluation"
                            )
                        )
                    ),
                    # Collection/retention succeeded even if technical checks
                    # failed. Only the explicit derived assessment can advance
                    # or block the stage; this is not an evaluator PASS flag.
                    "exit_code": 0,
                    "report": deepcopy(self._receipt["evaluation"]),
                }
            )
        if (
            action_id
            in {
                "rehearsal_arm_feedback_campaign",
                "rehearsal_owned_arm_feedback_campaign",
            }
            and self._feedback_diagnostic is not None
        ):
            # Public operation logs/exports contain hashes and safe diagnostics,
            # never lossless raw serial bytes. The original M1 record retains
            # those complete private bytes before the coordinator's known seal.
            diagnostic = self.retained_feedback_diagnostics(
                include_resolution_trace=False
            )
            assert diagnostic is not None
            steps.append(
                {
                    "name": "retained-incapable-feedback-diagnostics",
                    "exit_code": 1 if failed else 0,
                    "report": diagnostic,
                }
            )
        if (
            action_id in {"rehearsal_owned_camera_campaign", "rehearsal_camera_probe"}
            and self._camera_process_diagnostic is not None
        ):
            steps.append(
                {
                    "name": "retained-incapable-owned-camera-diagnostics",
                    "exit_code": 1 if failed else 0,
                    "report": deepcopy(self._camera_process_diagnostic),
                }
            )
        return {
            "schema": "rocell.wizard_worker_result.v1",
            "action_id": action_id,
            "status": "FAILED" if failed else "SUCCEEDED",
            "steps": steps,
            "device_open_count": 0,
            "serial_write_count": 0,
            "power_event_count": 0,
            "motion_command_count": 0,
            "contact_command_count": 0,
            "metadata_inventory_performed": False,
            "physical_authority": False,
        }
