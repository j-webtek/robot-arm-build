"""Explicit file-only camera setup, with original M1 evidence and no device IO.

The application owns the directory and context. Tickets bind cached context;
execution checks it again before one-use collection. Storage readiness and a
requirements document never substitute for delivered-unit observations/review.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import json
import re
import threading
from time import monotonic_ns, time_ns
from typing import Any, Callable, Iterator

from .physical_camera_acquisition_service import PhysicalCameraAcquisitionService
from .physical_camera_prerequisites import (
    PhysicalCameraPrerequisites,
    collect_physical_camera_prerequisites,
    verify_physical_camera_prerequisites,
)
from .physical_camera_selection import selection_from_enrollment
from .physical_camera_session import (
    PhysicalCameraSession,
    SOURCE_WORKFLOW_INTAKE_SCHEMA,
)
from .physical_configuration_epochs import (
    PhysicalConfigurationEpochs,
    build_physical_configuration_epochs,
)
from .physical_camera_reopen_registry import (
    PhysicalCameraReopenRegistry,
    PhysicalCameraStoreDescriptor,
)
from .physical_onboarding import PhysicalOnboardingStage, STAGE_ORDER
from .physical_onboarding_v2 import V2StageState
from .physical_onboarding_durability import canonical_sha256
from .physical_source_preflight import PhysicalSourcePreflightReport
from .wizard_actions import (
    PORTABLE_SETUP_OPERATOR_HELP,
    WizardError,
    portable_setup_operator_valid,
)
from .wizard_diagnostic_coordinator import source_fingerprint
from .wizard_native_camera_enrollment import WizardNativeCameraEnrollment
from rocell.providers.windows.native_camera_protocol import canonical, digest

SETUP_ACTIONS = frozenset(
    {
        "physical_camera_initialize",
        "physical_camera_refresh",
        "physical_camera_prerequisites",
        "physical_camera_discover",
        "physical_camera_reopen",
        "physical_camera_assess_sources",
        "physical_camera_review_sources",
        "physical_camera_mode_enter",
        "physical_camera_probe_prepare",
        "physical_camera_probe_review",
    }
)


class PhysicalCameraSetupService:
    """One explicit original store per launch; no automatic repair or replay."""

    def __init__(self, acquisition: PhysicalCameraAcquisitionService) -> None:
        if type(acquisition) is not PhysicalCameraAcquisitionService:
            raise TypeError("Exact application-owned camera composition required")
        self.workspace = acquisition.workspace
        self.mode = acquisition.mode
        self.source_sha256 = acquisition.source_sha256
        self.launch_id = acquisition.launch_id
        self._acquisition = acquisition
        self._registry = PhysicalCameraReopenRegistry(
            self.workspace,
            current_launch_id=self.launch_id,
            source_sha256=self.source_sha256,
        )
        self._empty_discovery = self._registry.view()
        self._discovery_published = False
        self._last_action: str | None = None
        self.session = PhysicalCameraSession(
            self.workspace,
            acquisition.directory,
            launch_id=self.launch_id,
            source_sha256=self.source_sha256,
            cell_id=acquisition.cell_id,
            session_id=acquisition.session_id,
        )
        self._lock = threading.RLock()
        self._operation_lock = threading.Lock()
        self._collection_attempted = False
        self._reopen_attempted = False
        self._reopen_verified = False
        self._selected_original: dict[str, Any] | None = None
        self._original_descriptor: PhysicalCameraStoreDescriptor | None = None
        self._prerequisites: dict[str, Any] | None = None
        self._retained: dict[str, Any] | None = None
        self._source_workflow: dict[str, Any] | None = None
        self._source_summaries: dict[str, Any] = {}
        self._source_attempt_records: dict[str, Any] = {}
        self._epoch_record: dict[str, Any] | None = None
        self._epoch_attempt_record: dict[str, Any] | None = None
        self._assessment_attempted = False
        self._review_attempted = False
        # A queued entry is consumed before intent logging. Even a stopped or
        # partially written entry is not silently retried in this launch.
        self._mode_entry_attempted = False
        self._mode_entry_queue: dict[str, Any] | None = None
        self._mode_entry_attempt: dict[str, Any] | None = None
        self._probe_queues: dict[str, dict[str, Any]] = {}
        self._probe_attempts: dict[str, dict[str, Any]] = {}
        self._publication = {"status": "NOT_PUBLISHED", "operation_id": None}

    def view(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(
                {
                    "schema": "rocell.wizard_physical_camera_setup.v3",
                    "source_sha256": self.source_sha256,
                    "launch_session_id": self.launch_id,
                    "origin_launch_id": self.session.descriptor()["launch_id"],
                    "reopening": (
                        self._registry.view()
                        if self._discovery_published
                        else self._empty_discovery
                    ),
                    "requirements_provenance": (
                        "NONE"
                        if self._publication["status"] != "CURRENT"
                        or self._prerequisites is None
                        else (
                            "CURRENT_LAUNCH_ORIGINAL"
                            if self.session.descriptor()["launch_id"] == self.launch_id
                            else "REOPENED_ORIGINAL_CONTEXT"
                        )
                    ),
                    "session": self.session.view(),
                    "prerequisites": (
                        self._prerequisites
                        if self._publication["status"] == "CURRENT"
                        else None
                    ),
                    "publication": self._publication,
                    "source_workflow": self.source_workflow_view(),
                    "configuration_records": self.configuration_records_view(),
                    "physical_authority": False,
                    "hardware_qualified": False,
                    "meaning": "Original camera-only storage and requirements, not connected hardware or accepted physical stages. No device operation or replay is available.",
                }
            )

    def retained_diagnostics(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(
                {
                    "session": self.session.view(),
                    "retained_verification": self.session.retained_verification(),
                    "prerequisites": self._retained
                    or self.session.retained_prerequisites(),
                    "collection_attempted": self._collection_attempted,
                    "reopen_attempted": self._reopen_attempted,
                    "selected_original": self._selected_original,
                    "reopening": self._registry.view(),
                    "configuration_records": self.configuration_records_view(),
                    "physical_authority": False,
                }
            )

    def mode_entry_view(self) -> dict[str, Any]:
        """Cached display only; reading this view cannot queue or enter a stage."""
        from .physical_camera_mode_entry_projection import project_mode_entry

        with self._lock:
            return project_mode_entry(
                self.view(),
                self._source_workflow,
                attempted=self._mode_entry_attempted,
                attempt=self._mode_entry_attempt,
                available=self.blocked_reason("physical_camera_mode_enter") is None,
            )

    def mode_entry_diagnostics(self) -> dict[str, Any] | None:
        """Full bounded entry/attempt bytes for the existing diagnostic export.

        USB history retains its existing export format. This separately named
        camera-stage attachment binds that history's exact review hash without
        relabeling its schema or creating another logging/export system.
        """
        from .physical_camera_mode_entry import FALSE_FIELDS

        with self._lock:
            workflow = (
                self.session.retained_source_workflow() or self._source_workflow or {}
            )
            original = workflow.get("camera_mode_entry")
            if original is None and not self._mode_entry_attempted:
                return None
            return deepcopy(
                dict(
                    schema="rocell.camera_mode_entry_diagnostics.v1",
                    source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                    publication=self._publication,
                    original=original,
                    attempted=self._mode_entry_attempted,
                    queued_operation_id=(self._mode_entry_queue or {}).get(
                        "operation_id"
                    ),
                    attempt=self._mode_entry_attempt,
                    meaning="Original and attempted file-only camera setup entry; diagnostic evidence, not permission to connect or replay.",
                    **{flag: False for flag in FALSE_FIELDS},
                )
            )

    def configuration_records_view(self) -> dict[str, Any]:
        """Project cached dependency records, never acquisition eligibility.

        The record describes its original stage boundary. A later stage/review
        does not silently recalculate it or promote an absent observation.
        """
        with self._lock:
            record = self._epoch_record
            summary = None
            status = "NOT_RETAINED"
            if record is not None and self._publication["status"] != "PENDING":
                raw = canonical(record["document"])
                artifact = PhysicalConfigurationEpochs(raw)
                if artifact.sha256 != record["evidence_sha256"]:
                    raise WizardError(
                        "CAMERA_CONFIGURATION_RECORD_CHANGED",
                        "The retained configuration record differs; verify the original store.",
                    )
                summary = artifact.safe_summary()
                status = (
                    "CURRENT"
                    if self._publication["status"] == "CURRENT"
                    and record["retention"] == "M1_FULL_BYTES_READ_BACK"
                    else "HISTORICAL_HELD"
                )
            return deepcopy(
                {
                    "schema": "rocell.wizard_physical_configuration_records.v1",
                    "status": status,
                    "summary": summary,
                    "physical_authority": False,
                    "hardware_qualified": False,
                }
            )

    def retained_configuration_diagnostics(self) -> dict[str, Any] | None:
        """Full bounded original record, separate from ordinary nested cards."""
        with self._lock:
            record = self._epoch_record or self._epoch_attempt_record
            if record is None:
                # A new owner may read the original bytes successfully and
                # then fail a late lease/source/Stop check before adoption.
                # Preserve that reader's cache for diagnostics, not the live
                # configuration view or acquisition eligibility. No IO here.
                workflow = self.session.retained_source_workflow()
                record = (
                    None if workflow is None else workflow.get("configuration_epochs")
                )
            if record is None:
                return None
            return deepcopy(
                {
                    "schema": "rocell.wizard_physical_configuration_diagnostics.v1",
                    "record": record,
                    "record_is_current_original": self._epoch_record is not None,
                    "publication": (
                        self._publication
                        if self._epoch_record is not None
                        else {"status": "HISTORICAL_HELD", "operation_id": None}
                    ),
                    "physical_authority": False,
                    "hardware_qualified": False,
                }
            )

    def source_workflow_view(self) -> dict[str, Any]:
        """Cached display only; stored bytes do not imply a committed verdict."""
        with self._lock:
            state = (self._source_workflow or {}).get("state")
            collections = (self._source_workflow or {}).get("intake_collections")
            reassessed = bool((self._source_workflow or {}).get("qualification_cycles"))
            status = "NOT_STARTED"
            if self._source_summaries:
                status = "HISTORICAL_HELD"
                if self._publication["status"] == "CURRENT" and not reassessed:
                    if collections:
                        # The supplementary cycle is not a reassessment of the
                        # immutable original source-v1 BLOCKED subject.
                        status = "REVIEWED_BLOCKED"
                    elif (
                        state == "REVIEW_PENDING"
                        and (self._source_workflow or {}).get("review") is None
                    ):
                        status = "REVIEW_PENDING"
                    elif state == "BLOCKED":
                        status = "REVIEWED_BLOCKED"
            # Do not expose a newly produced summary before completion logging.
            summaries = (
                {}
                if self._publication["status"] == "PENDING"
                else self._source_summaries
            )
            result = {
                "schema": "rocell.wizard_workspace_source_workflow.v1",
                "status": "NOT_STARTED" if not summaries else status,
                **{
                    role: summaries.get(role)
                    for role in ("receipt", "assessment", "review")
                },
                "physical_authority": False,
                "canonical_stage_pass": False,
                "device_io_performed": False,
                "power_state": "UNKNOWN",
            }
            if collections:
                result.update(
                    schema="rocell.wizard_workspace_source_workflow.v2",
                    original_source_state="BLOCKED",
                    supplementary=(
                        None
                        if self._publication["status"] == "PENDING"
                        else {
                            "collection_id": collections[-1]["collection_id"],
                            "state": "BLOCKED" if reassessed else state,
                        }
                    ),
                )
            return deepcopy(result)

    def retained_source_diagnostics(self) -> dict[str, Any] | None:
        """Full original evidence, reserved separately from rotating result cards."""
        with self._lock:
            original = self._source_workflow or self.session.retained_source_workflow()
            if not self._source_attempt_records and not (original or {}).get("receipt"):
                return None
            result: dict[str, Any] = deepcopy(
                {
                    "schema": "rocell.wizard_workspace_source_diagnostics.v1",
                    "original": original,
                    "attempt_records": self._source_attempt_records,
                    "assessment_attempted": self._assessment_attempted,
                    "review_attempted": self._review_attempted,
                    "physical_authority": False,
                }
            )
            # Flatten full documents to preserve the shared diagnostic depth
            # bound without truncating a prerequisite catalog or source facts.
            if result["original"] is not None:
                # Later USB originals already have their own complete export.
                # Duplicating their nested runtime/campaign records here breaks
                # the general report's fixed depth budget. Keep exact pointers,
                # just as for the older USB/received families below.
                from .physical_camera_usb_reconnect_constants import (
                    USB_RECONNECT_ROLE_BYTES,
                )
                from .physical_camera_usb_reboot_constants import USB_REBOOT_ROLE_BYTES
                from .physical_camera_usb_complete_constants import (
                    USB_COMPLETE_ROLE_BYTES,
                )

                for family, id_key, roles in (
                    (
                        "usb_qualification_reconnect",
                        "phase_id",
                        USB_RECONNECT_ROLE_BYTES,
                    ),
                    ("usb_qualification_reboot", "phase_id", USB_REBOOT_ROLE_BYTES),
                    (
                        "usb_qualification_complete",
                        "series_id",
                        USB_COMPLETE_ROLE_BYTES,
                    ),
                ):
                    subject = result["original"].pop(family, None)
                    if subject is not None:
                        result[family + "_sha256"] = digest(canonical(subject))
                        result[family + "_summary"] = {
                            id_key: subject[id_key],
                            "state": subject["state"],
                            **{
                                role
                                + "_sha256": (subject.get(role) or {}).get(
                                    "evidence_sha256"
                                )
                                for role in roles
                            },
                        }
                        result["usb_separate_metadata_export_required"] = True
                operating = result["original"].pop("camera_operating_submission", None)
                if operating is not None:
                    result["camera_operating_submission_sha256"] = digest(canonical(operating))
                    result["camera_operating_submission_summary"] = {
                        "state": operating["state"],
                        "submission_sha256": operating["submission"]["evidence_sha256"],
                        "attachment": "attachment-camera-operating-submissions.json",
                        "original_documents_included": False,
                    }
                probe = result["original"].pop("camera_probe_preparation", None)
                if probe is not None:
                    result["camera_probe_preparation_sha256"] = digest(canonical(probe))
                    result["camera_probe_preparation_summary"] = {
                        "state": probe["state"],
                        "preparation_sha256": (probe.get("preparation") or {}).get(
                            "evidence_sha256"
                        ),
                        "review_sha256": (probe.get("review") or {}).get(
                            "evidence_sha256"
                        ),
                        "required_action": "physical_camera_probe_export",
                        "original_documents_included": False,
                    }
                entry = result["original"].pop("camera_mode_entry", None)
                if entry is not None:
                    result["camera_mode_entry_sha256"] = digest(canonical(entry))
                    result["camera_mode_entry_summary"] = {
                        "state": entry["state"],
                        "entry_sha256": entry["entry"]["evidence_sha256"],
                        "attachment": "attachment-camera-mode-entry.json",
                    }
                absence = result["original"].pop("usb_qualification_absence", None)
                if absence is not None:
                    from .physical_camera_usb_absence_constants import (
                        USB_ABSENCE_ROLE_BYTES,
                    )

                    result["usb_qualification_absence_sha256"] = digest(
                        canonical(absence)
                    )
                    result["usb_qualification_absence_summary"] = dict(
                        phase_id=absence["phase_id"],
                        phase=absence["phase"],
                        state=absence["state"],
                        **{
                            role
                            + "_sha256": (
                                None
                                if absence[role] is None
                                else absence[role]["evidence_sha256"]
                            )
                            for role in USB_ABSENCE_ROLE_BYTES
                        },
                    )
                    result["usb_separate_metadata_export_required"] = True
                phase = result["original"].pop("usb_qualification_baseline", None)
                if phase is not None:
                    result["usb_qualification_baseline_sha256"] = digest(
                        canonical(phase)
                    )
                    result["usb_qualification_baseline_summary"] = dict(
                        phase_id=phase["phase_id"],
                        phase=phase["phase"],
                        state=phase["state"],
                        **{
                            role
                            + "_sha256": (
                                None
                                if phase[role] is None
                                else phase[role]["evidence_sha256"]
                            )
                            for role in (
                                "enrollment",
                                "preparation",
                                "policy_review",
                                "runtime_review",
                                "identity",
                                "boot_request",
                                "host_boot",
                                "execution",
                                "phase_record",
                            )
                        },
                    )
                    result["usb_separate_metadata_export_required"] = True
                trial = result["original"].pop("usb_qualification_trial", None)
                if trial is not None:
                    result["usb_qualification_trial_sha256"] = digest(canonical(trial))
                    result["usb_qualification_trial_summary"] = dict(
                        trial_id=trial["trial_id"],
                        state=trial["state"],
                        plan_sha256=(
                            None
                            if trial["plan"] is None
                            else trial["plan"]["evidence_sha256"]
                        ),
                    )
                    result["usb_separate_metadata_export_required"] = True
                usb = result["original"].pop("usb_baseline", None)
                if usb is not None:
                    result["usb_baseline_sha256"] = digest(canonical(usb))
                    result["usb_baseline_summary"] = {
                        "usb_id": usb["usb_id"],
                        "state": usb["state"],
                        **{
                            role
                            + "_sha256": (
                                None
                                if usb[role] is None
                                else usb[role]["evidence_sha256"]
                            )
                            for role in (
                                "inspection",
                                "policy_review",
                                "runtime_review",
                                "identity",
                                "execution",
                                "outcome",
                            )
                        },
                    }
                    result["usb_separate_metadata_export_required"] = True
                identity = result["original"].pop("camera_identity_cycles", None)
                if identity is not None:
                    result["camera_identity_cycles_sha256"] = digest(
                        canonical(identity)
                    )
                    result["camera_identity_cycles_summary"] = [
                        {
                            "identity_id": item["identity_id"],
                            "sequence": item["sequence"],
                            "state": item["state"],
                            **{
                                role
                                + "_sha256": (
                                    None
                                    if item[role] is None
                                    else item[role]["evidence_sha256"]
                                )
                                for role in (
                                    "metadata",
                                    "helper",
                                    "receipt",
                                    "assessment",
                                    "review",
                                )
                            },
                        }
                        for item in identity
                    ]
                    result["camera_identity_separate_metadata_export_required"] = True
                received = result["original"].pop("received_camera_cycles", None)
                if received is not None:
                    # Camera receipt originals have a separate complete metadata
                    # bundle. Never duplicate them into the source-owned budget.
                    result["received_camera_cycles_sha256"] = digest(
                        canonical(received)
                    )
                    result["received_camera_cycles_summary"] = [
                        {
                            "receipt_id": item["receipt_id"],
                            "sequence": item["sequence"],
                            "state": item["state"],
                            **{
                                role
                                + "_sha256": (
                                    None
                                    if item[role] is None
                                    else item[role]["evidence_sha256"]
                                )
                                for role in (
                                    "notebook",
                                    "submission",
                                    "assessment",
                                    "review",
                                )
                            },
                        }
                        for item in received
                    ]
                    result["received_camera_separate_metadata_export_required"] = True
                contract = result["original"].pop("static_contract", None)
                if contract is not None:
                    # The combined source/static export owns the complete
                    # documents. Keep an exact family hash and role references
                    # here, rather than nesting a second copy of the originals.
                    result["static_contract_sha256"] = digest(canonical(contract))
                    result["static_contract_summary"] = {
                        "contract_id": contract["contract_id"],
                        "state": contract["state"],
                        **{
                            role
                            + "_sha256": (
                                None
                                if contract[role] is None
                                else contract[role]["evidence_sha256"]
                            )
                            for role in ("receipt", "assessment", "review")
                        },
                    }
                qualifications = result["original"].pop("qualification_cycles", None)
                if qualifications is not None:
                    # Full successor documents have their own bounded export;
                    # legacy BLOCKED subjects keep their original interpretation.
                    result["qualification_cycles_sha256"] = digest(
                        canonical(qualifications)
                    )
                    result["qualification_cycles_summary"] = [
                        {
                            "qualification_id": item["qualification_id"],
                            "state": item["state"],
                            **{
                                role
                                + "_sha256": (
                                    None
                                    if item[role] is None
                                    else item[role]["evidence_sha256"]
                                )
                                for role in ("receipt", "assessment", "review")
                            },
                        }
                        for item in qualifications
                    ]
                collections = result["original"].pop("intake_collections", None)
                if collections is not None:
                    # Original notebooks are carried by the dedicated intake
                    # exporter, not nested again in the ordinary source report.
                    result["intake_collections_sha256"] = digest(canonical(collections))
                    result["intake_collections_summary"] = [
                        {
                            "collection_id": item["collection_id"],
                            "state": item["state"],
                            "attachment_count": len(item["attachments"]),
                            **{
                                role
                                + "_sha256": (
                                    None
                                    if item[role] is None
                                    else item[role]["evidence_sha256"]
                                )
                                for role in ("submission", "assessment", "review")
                            },
                        }
                        for item in collections
                    ]
                for role in (
                    "prerequisites",
                    "receipt",
                    "assessment",
                    "review",
                    "configuration_epochs",
                ):
                    record = result["original"].get(role)
                    if record is not None:
                        result[role + "_document"] = record.pop("document")
            for role, record in result["attempt_records"].items():
                result["attempt_" + role + "_document"] = record.pop("document")
            return result

    def operating_proposal_entry(self) -> dict[str, Any]:
        """Small cached entry only; never copy the full USB/native history on polling."""
        with self._lock:
            workflow = self._source_workflow or {}
            return deepcopy({
                "camera_mode_entry": workflow.get("camera_mode_entry"),
                "session_header_sha256": workflow.get("session_header_sha256"),
                "publication": self._publication,
            })

    def original_source_workflow(self) -> dict[str, Any] | None:
        """Detached last adopted original readback; publication is separate.

        This cached accessor never scans, refreshes, collects or repairs. A
        failed later mutation may leave it as a historical predecessor only.
        """
        with self._lock:
            return deepcopy(self._source_workflow)

    @contextmanager
    def intake_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Legacy intake is not allowed to interleave a qualification suffix."""
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
        ) as original:
            yield original

    @contextmanager
    def qualification_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Source-stage successor only; no device admission or implicit advance."""
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=True,
        ) as original:
            yield original

    @contextmanager
    def received_camera_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Serialize original received-unit work without device admission."""
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
            received_camera=True,
        ) as original:
            yield original

    @contextmanager
    def identity_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Original metadata suffix only; no live endpoint or device admission."""
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
            camera_identity=True,
        ) as original:
            yield original

    @contextmanager
    def usb_identity_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Serialize original USB roles; no device lease or admission is supplied.

        A caller may execute the exact admitted campaign inside this service
        scope. Its post-yield audit uses stage-only leases, including quarantine.
        A new mutation still requires the original non-quarantined entry below.
        """
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
            usb_identity=True,
        ) as original:
            yield original

    @contextmanager
    def usb_qualification_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Declare one original trial only; grants no phase/device execution."""
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
            usb_trial=True,
        ) as original:
            yield original

    @contextmanager
    def usb_phase_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Serialize the original new-trial BASELINE; no device lease/permit.

        Exact action-specific state and no-replay checks remain with the phase
        service. Post-effect readback is stage-only even for retained quarantine.
        The original action deadline may cover at most 180 seconds, including
        final storage/readback. It is never renewed here and changes no inner
        boot, USB, permit or cleanup budget. Other storage scopes retain 120s.
        """
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
            usb_phase=True,
        ) as original:
            yield original

    @contextmanager
    def static_contract_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Stage-2 design records after explicit entry, never native admission."""
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
            static_contract=True,
        ) as original:
            yield original

    @contextmanager
    def usb_absence_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Serialize one v11 absence step with the unchanged original 180s ceiling.

        No device lease, permit or replay is supplied. Pending/uncertain records
        are read back only; the public owner must require the exact next step.
        """
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
            usb_absence=True,
        ) as original:
            yield original

    @contextmanager
    def usb_reconnect_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Serialize a clean same-launch reconnect boundary, not device admission.

        The existing 180-second outer ceiling covers original readback too.
        Boot/USB/permit/cleanup budgets remain independently bounded. Reopened,
        incomplete, consumed or uncertain reconnect work is export-only.
        """
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
            usb_reconnect=True,
        ) as original:
            yield original

    @contextmanager
    def usb_reboot_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Serialize a new-launch reboot step; never resume a consumed phase.

        A complete reconnect is historical input only. A fresh v13 operator
        report binds later steps to this launch; original readback and the
        outer completion publication are still required before CURRENT.
        """
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
            usb_reboot=True,
        ) as original:
            yield original

    @contextmanager
    def usb_complete_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Serialize file-only final assessment/review, never device admission.

        The bounded 180-second outer window includes full original readback.
        It neither renews the caller's deadline nor changes any device budget.
        Partial/consumed publications are read-only; review is a separate action.
        """
        with self._source_transaction(
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
            qualification=False,
            usb_complete=True,
        ) as original:
            yield original

    @contextmanager
    def _source_transaction(
        self,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        deadline_ns: int,
        qualification: bool,
        static_contract: bool = False,
        received_camera: bool = False,
        camera_identity: bool = False,
        usb_identity: bool = False,
        usb_trial: bool = False,
        usb_phase: bool = False,
        usb_absence: bool = False,
        usb_reconnect: bool = False,
        usb_reboot: bool = False,
        usb_complete: bool = False,
    ) -> Iterator[tuple[PhysicalCameraPrerequisites, dict[str, Any]]]:
        """Serialize a closed supplementary mutation and its original readback.

        The caller is the application-owned intake service; it still opens the
        exact session's stage-only M1 transaction and checks its expected head.
        This scope supplies no admission facts, physical acceptance or retry.
        Normal exit is PENDING until the outer action's completion log succeeds.
        """
        started = monotonic_ns()
        # Exactly one extended original-workflow scope may use 180 seconds.
        # Default/source scopes keep their original 120-second limit.
        extended_scopes = (
            usb_phase,
            usb_absence,
            usb_reconnect,
            usb_reboot,
            usb_complete,
        )
        storage_window_ns = (
            180_000_000_000
            if all(type(value) is bool for value in extended_scopes)
            and sum(value is True for value in extended_scopes) == 1
            and not any(
                (
                    qualification,
                    static_contract,
                    received_camera,
                    camera_identity,
                    usb_identity,
                    usb_trial,
                )
            )
            else 120_000_000_000
        )
        if (
            not isinstance(cancellation, threading.Event)
            or type(usb_reconnect) is not bool
            or type(usb_reboot) is not bool
            or type(usb_complete) is not bool
            or (
                usb_complete
                and any(
                    value is not False
                    for value in (
                        qualification,
                        static_contract,
                        received_camera,
                        camera_identity,
                        usb_identity,
                        usb_trial,
                        usb_phase,
                        usb_absence,
                        usb_reconnect,
                        usb_reboot,
                    )
                )
            )
            or (
                usb_reboot
                and any(
                    value is not False
                    for value in (
                        qualification,
                        static_contract,
                        received_camera,
                        camera_identity,
                        usb_identity,
                        usb_trial,
                        usb_phase,
                        usb_absence,
                        usb_reconnect,
                        usb_complete,
                    )
                )
            )
            or (
                usb_reconnect
                and any(
                    (
                        qualification,
                        static_contract,
                        received_camera,
                        camera_identity,
                        usb_identity,
                        usb_trial,
                        usb_phase,
                        usb_absence,
                    )
                )
            )
            or not callable(progress)
            or type(deadline_ns) is not int
            or not started < deadline_ns <= started + storage_window_ns
        ):
            raise WizardError(
                "INTAKE_STORAGE_CONTEXT_INVALID",
                "An original bounded intake operation is required.",
            )
        if not self._operation_lock.acquire(blocking=False):
            raise WizardError("CAMERA_SETUP_BUSY", "A camera setup action is active.")
        try:
            original_session = self.session
            original_binding = original_session.descriptor()

            def check() -> None:
                if (
                    self.session is not original_session
                    or self.session.descriptor() != original_binding
                ):
                    raise WizardError(
                        "INTAKE_ORIGINAL_STORE_CHANGED",
                        "The original intake store changed; no replacement is followed.",
                    )
                if cancellation.is_set() or monotonic_ns() >= deadline_ns:
                    raise WizardError(
                        "INTAKE_STORAGE_INTERRUPTED",
                        "Stopped or expired; inspect original records without replay.",
                    )
                if source_fingerprint(self.workspace) != self.source_sha256:
                    raise WizardError(
                        "CAMERA_SETUP_SOURCE_CHANGED",
                        "Source changed; original records are historical only.",
                    )
                if cancellation.is_set() or monotonic_ns() >= deadline_ns:
                    raise WizardError(
                        "INTAKE_STORAGE_INTERRUPTED",
                        "Stopped or expired during source verification.",
                    )

            check()
            with self._lock:
                workflow = deepcopy(self._source_workflow)
                view = self.session.view()
                verification = view["verification"]
                if (
                    self.mode != "physical"
                    or self._publication["status"] != "CURRENT"
                    or workflow is None
                    or verification is None
                    or verification["effects_allowed_by_m1_storage"] is not True
                    or any(
                        workflow[role] is None
                        for role in ("prerequisites", "receipt", "assessment", "review")
                    )
                    or workflow["binding"] != self.session.descriptor()
                    or workflow["session_header_sha256"]
                    != verification["session"]["header_sha256"]
                    or workflow["session_head_sha256"]
                    != verification["session"]["head_sha256"]
                    or workflow["evidence_inventory_sha256"]
                    != verification["session"]["evidence_inventory_sha256"]
                    or workflow["state"] != view["stages"][0]["state"]
                    or (
                        workflow["state"] != "BLOCKED"
                        and workflow["schema"] != SOURCE_WORKFLOW_INTAKE_SCHEMA
                        and not (
                            qualification
                            and workflow["schema"]
                            == "rocell.physical_camera_source_workflow_readback.v4"
                        )
                        and not (
                            static_contract
                            and workflow["schema"]
                            in {
                                "rocell.physical_camera_source_workflow_readback.v4",
                                "rocell.physical_camera_source_workflow_readback.v5",
                            }
                        )
                        and not (
                            received_camera
                            and workflow["schema"]
                            in {
                                "rocell.physical_camera_source_workflow_readback.v5",
                                "rocell.physical_camera_source_workflow_readback.v6",
                            }
                        )
                        and not (
                            camera_identity
                            and workflow["schema"]
                            in {
                                "rocell.physical_camera_source_workflow_readback.v6",
                                "rocell.physical_camera_source_workflow_readback.v7",
                            }
                        )
                        and not (
                            usb_phase
                            and workflow["schema"]
                            in {
                                "rocell.physical_camera_source_workflow_readback.v9",
                                "rocell.physical_camera_source_workflow_readback.v10",
                            }
                        )
                        and not (
                            usb_absence
                            and workflow["schema"]
                            in {
                                "rocell.physical_camera_source_workflow_readback.v10",
                                "rocell.physical_camera_source_workflow_readback.v11",
                            }
                        )
                        and not (
                            usb_complete
                            and workflow["schema"]
                            in {
                                "rocell.physical_camera_source_workflow_readback.v13",
                                "rocell.physical_camera_source_workflow_readback.v14",
                            }
                        )
                        and not (
                            usb_reboot
                            and workflow["schema"]
                            in {
                                "rocell.physical_camera_source_workflow_readback.v12",
                                "rocell.physical_camera_source_workflow_readback.v13",
                            }
                        )
                        and not (
                            usb_reconnect
                            and workflow["schema"]
                            in {
                                "rocell.physical_camera_source_workflow_readback.v11",
                                "rocell.physical_camera_source_workflow_readback.v12",
                            }
                        )
                        and not (
                            (usb_identity or usb_trial)
                            and workflow["schema"]
                            in {
                                "rocell.physical_camera_source_workflow_readback.v7",
                                "rocell.physical_camera_source_workflow_readback.v8",
                            }
                        )
                    )
                    or (
                        not qualification
                        and not static_contract
                        and not received_camera
                        and not camera_identity
                        and not usb_identity
                        and not usb_trial
                        and not usb_phase
                        and not usb_absence
                        and not usb_reconnect
                        and not usb_reboot
                        and not usb_complete
                        and bool(workflow.get("qualification_cycles"))
                    )
                    or (
                        received_camera
                        and (
                            workflow["state"] != "PASS"
                            or not workflow.get("static_contract")
                            or workflow["static_contract"]["state"] != "REVIEWED_PASS"
                            or workflow.get("camera_receipt_request") is None
                        )
                    )
                    or (
                        (
                            camera_identity
                            or usb_identity
                            or usb_trial
                            or usb_phase
                            or usb_absence
                            or usb_reconnect
                            or usb_reboot
                            or usb_complete
                        )
                        and (
                            workflow["state"] != "PASS"
                            or not workflow.get("static_contract")
                            or workflow["static_contract"]["state"] != "REVIEWED_PASS"
                            or not workflow.get("received_camera_cycles")
                            or workflow["received_camera_cycles"][-1]["state"]
                            != "REVIEWED_PASS"
                            or workflow.get("camera_identity_request") is None
                        )
                    )
                    or (
                        (
                            usb_identity
                            or usb_trial
                            or usb_phase
                            or usb_absence
                            or usb_reconnect
                            or usb_reboot
                            or usb_complete
                        )
                        and (
                            not workflow.get("camera_identity_cycles")
                            or workflow["camera_identity_cycles"][-1]["state"]
                            != "REVIEWED_BLOCKED"
                        )
                    )
                    or (
                        static_contract
                        and (
                            workflow["state"] != "PASS"
                            or not workflow.get("qualification_cycles")
                            or workflow["qualification_cycles"][-1]["state"]
                            != "REVIEWED_PASS"
                            or workflow.get("static_camera_request") is None
                        )
                    )
                ):
                    raise WizardError(
                        "INTAKE_ORIGINAL_SOURCE_REVIEW_REQUIRED",
                        "Verify and publish the original reviewed source records first.",
                    )
                prerequisites, artifacts = self._source_artifacts(workflow)
                assert prerequisites is not None and "review" in artifacts
                if usb_complete:
                    from .physical_usb_complete_service import complete_action_boundary

                    if complete_action_boundary(workflow) is None:
                        raise WizardError(
                            "USB_COMPLETE_ORIGINAL_REQUIRED",
                            "A completed original reboot or exact unreviewed assessment is required; partial or consumed work is read-only.",
                        )
                if usb_reboot:
                    from .physical_camera_usb_reboot import (
                        original_usb_reboot_predecessor,
                        original_usb_reboot_predecessor_v13,
                    )
                    from .physical_received_camera_submission import (
                        ReceivedCameraSubmission,
                        ReceivedCameraSubmissionAssessment,
                        ReceivedCameraSubmissionReview,
                    )

                    try:
                        row = workflow["received_camera_cycles"][-1]
                        received = {
                            role: cls(canonical(row[role]["document"]), prerequisites)
                            for role, cls in (
                                ("submission", ReceivedCameraSubmission),
                                ("assessment", ReceivedCameraSubmissionAssessment),
                                ("review", ReceivedCameraSubmissionReview),
                            )
                        }
                        reboot = workflow.get("usb_qualification_reboot")
                        if workflow["schema"].endswith(".v13"):
                            original_usb_reboot_predecessor_v13(
                                workflow, received=received
                            )
                            if (
                                type(reboot) is not dict
                                or reboot.get("state")
                                not in {
                                    "PREPARATION_REQUESTED",
                                    "PREPARED",
                                    "REVIEWED",
                                    "BOOT_RETAINED",
                                }
                                or type(reboot.get("operator_event")) is not dict
                                or reboot["operator_event"]["document"][
                                    "launch_session_id"
                                ]
                                != self.launch_id
                                or reboot.get("original_campaign") is not None
                                or reboot.get("original_campaign_event") is not None
                            ):
                                raise ValueError(
                                    "Reboot is incomplete, consumed or from an earlier launch"
                                )
                        else:
                            original_usb_reboot_predecessor(workflow, received=received)
                            if (
                                reboot is not None
                                or workflow["usb_qualification_reconnect"][
                                    "operator_event"
                                ]["document"]["launch_session_id"]
                                == self.launch_id
                            ):
                                raise ValueError(
                                    "A distinct launch after complete reconnect is required"
                                )
                    except (ValueError, TypeError, KeyError, IndexError) as error:
                        raise WizardError(
                            "USB_REBOOT_ORIGINAL_REQUIRED",
                            "Verify the clean completed reconnect and an unused current-launch reboot boundary.",
                        ) from error
                if usb_reconnect:
                    from .physical_camera_usb_reconnect import (
                        original_usb_reconnect_predecessor,
                        original_usb_reconnect_predecessor_v12,
                    )

                    try:
                        reconnect = workflow.get("usb_qualification_reconnect")
                        if workflow["schema"].endswith(".v12"):
                            original_usb_reconnect_predecessor_v12(workflow)
                            if type(reconnect) is not dict or reconnect.get(
                                "state"
                            ) not in {
                                "PREPARATION_REQUESTED",
                                "PREPARED",
                                "REVIEWED",
                                "BOOT_RETAINED",
                            }:
                                raise ValueError(
                                    "Incomplete or consumed reconnect cannot be replayed"
                                )
                            report = reconnect.get("operator_event")
                            if (
                                type(report) is not dict
                                or report["document"]["launch_session_id"]
                                != self.launch_id
                                or reconnect.get("original_campaign") is not None
                                or reconnect.get("original_campaign_event") is not None
                            ):
                                raise ValueError(
                                    "Reconnect belongs to an earlier launch or attempt"
                                )
                        else:
                            original_usb_reconnect_predecessor(workflow)
                            if reconnect is not None:
                                raise ValueError("Unexpected reconnect record")
                    except (ValueError, TypeError, KeyError) as error:
                        raise WizardError(
                            "USB_RECONNECT_ORIGINAL_REQUIRED",
                            "A complete original physical absence and unused same-launch reconnect boundary are required.",
                        ) from error
                if usb_absence:
                    from .physical_camera_usb_absence import (
                        original_usb_absence_baseline,
                    )

                    try:
                        original_usb_absence_baseline(workflow)
                        absence = workflow.get("usb_qualification_absence")
                        if workflow["schema"].endswith(".v11"):
                            if type(absence) is not dict or absence.get(
                                "state"
                            ) not in {
                                "PREPARED",
                                "BOOT_REVIEWED",
                                "PRESENCE_REVIEW_PREPARED",
                                "RUNTIME_REVIEWED",
                            }:
                                raise ValueError(
                                    "Incomplete or consumed absence cannot be replayed"
                                )
                        elif absence is not None:
                            raise ValueError("Unexpected absence record")
                    except (ValueError, TypeError, KeyError) as error:
                        raise WizardError(
                            "USB_ABSENCE_ORIGINAL_REQUIRED",
                            "A complete original BASELINE and exact unused absence boundary are required.",
                        ) from error
                if usb_phase:
                    trial = workflow.get("usb_qualification_trial")
                    phase = workflow.get("usb_qualification_baseline")
                    if (
                        type(trial) is not dict
                        or trial.get("state") != "PLAN_DECLARED"
                        or workflow.get("configuration_epochs") is None
                        or (
                            workflow["schema"].endswith(".v10")
                            and (
                                type(phase) is not dict
                                or phase.get("state")
                                not in {
                                    "PREPARATION_REQUESTED",
                                    "PREPARED",
                                    "REVIEWED",
                                    "BOOT_RETAINED",
                                }
                            )
                        )
                        or (workflow["schema"].endswith(".v9") and phase is not None)
                    ):
                        raise WizardError(
                            "USB_PHASE_ORIGINAL_REQUIRED",
                            "A clean original phase boundary is required; partial or uncertain work cannot be replayed.",
                        )
                if usb_trial:
                    from .physical_camera_usb_trial_readback import (
                        usb_qualification_predecessor_references,
                    )

                    try:
                        usb_qualification_predecessor_references(workflow)
                    except (ValueError, KeyError, TypeError) as error:
                        raise WizardError(
                            "USB_QUALIFICATION_ORIGINAL_REQUIRED",
                            "A clean reviewed original is required; incomplete or uncertain work cannot be retried.",
                        ) from error
                expected_header = workflow["session_header_sha256"]
            # Withdrawal happens after the exact cached inputs have been
            # validated, before any caller-controlled storage body is entered.
            self.invalidate()
            self._last_action = (
                (
                    "physical_usb_qualification"
                    if usb_trial
                    or usb_phase
                    or usb_absence
                    or usb_reconnect
                    or usb_reboot
                    or usb_complete
                    else (
                        "physical_camera_usb"
                        if usb_identity
                        else "physical_camera_identity"
                    )
                )
                if camera_identity
                or usb_identity
                or usb_trial
                or usb_phase
                or usb_absence
                or usb_reconnect
                or usb_reboot
                or usb_complete
                else (
                    "physical_received_camera"
                    if received_camera
                    else (
                        "physical_static_contract"
                        if static_contract
                        else (
                            "physical_source_qualification"
                            if qualification
                            else "physical_intake_submission"
                        )
                    )
                )
            )
            check()
            yield prerequisites, workflow
            check()
            self.session.refresh(cancellation=cancellation, progress=progress)
            check()
            refreshed = self.session.read_original_source_workflow(
                expected_header_sha256=expected_header,
                cancellation=cancellation,
                progress=progress,
                deadline_ns=deadline_ns,
            )
            self._adopt_source_workflow(refreshed)
            check()
            with self._lock:
                self._publication = {"status": "PENDING", "operation_id": None}
        except BaseException:
            # Keep the adopted predecessor and the reader's complete late-error
            # cache for historical export. Never restore CURRENT or retry here.
            self.invalidate()
            raise
        finally:
            self._operation_lock.release()

    def current_prerequisite_artifact(self) -> PhysicalCameraPrerequisites:
        """Return exact original requirements, never a historical failed collection.

        This is a pure bytes/hash check over our retained copy. The application
        still checks its source/log/Stop state before publishing any derivative.
        No draft observation is written into canonical onboarding stages.
        """
        with self._lock:
            retained = deepcopy(self._retained)
            if (
                self._publication["status"] != "CURRENT"
                or self._prerequisites is None
                or retained is None
                or retained["retention"] != "M1_FULL_BYTES_READ_BACK"
                or retained["evidence_sha256"] != self._prerequisites["evidence_sha256"]
            ):
                raise WizardError(
                    "INTAKE_REQUIREMENTS_UNAVAILABLE",
                    "Explicitly collect or reopen and verify original camera requirements first.",
                )
            bound = self.session.descriptor()
            return verify_physical_camera_prerequisites(
                canonical(retained["document"]),
                expected_source_sha256=self.source_sha256,
                expected_session_id=bound["session_id"],
                expected_launch_session_id=bound["launch_id"],
                expected_evidence_sha256=retained["evidence_sha256"],
            )

    def invalidate(self) -> None:
        with self._lock:
            self._publication = {"status": "HISTORICAL_HELD", "operation_id": None}
            self._prerequisites = None

    def publication_completed(self, operation_id: str) -> None:
        with self._lock:
            if self._publication["status"] == "PENDING":
                self._publication = {"status": "CURRENT", "operation_id": operation_id}
                if self._last_action == "physical_camera_discover":
                    self._discovery_published = True

    def begin_mode_entry(self, expected_context_sha256: str, operation_id: str) -> None:
        """Consume the explicit entry at queue time, before intent-log writes.

        Arrival owns the ticket; this token only binds its one Setup dispatch.
        It is not physical admission, and no original file is written here.
        """
        with self._lock:
            reason = self.blocked_reason("physical_camera_mode_enter")
            if reason:
                raise WizardError("CAMERA_SETUP_BLOCKED", reason)
            if (
                type(expected_context_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", expected_context_sha256) is None
                or type(operation_id) is not str
                or not 1 <= len(operation_id) <= 96
            ):
                raise WizardError(
                    "CAMERA_MODE_QUEUE_INVALID",
                    "An exact queued setup action is required.",
                )
            self._mode_entry_attempted = True
            self._mode_entry_queue = dict(
                context_sha256=expected_context_sha256,
                operation_id=operation_id,
                claimed=False,
            )
            self.invalidate()

    def begin_probe_record(
        self, action_id: str, expected_context_sha256: str, operation_id: str
    ) -> None:
        """Consume one file-only action before Arrival attempts its intent log."""
        from .camera_probe_setup_service import ACTIONS

        with self._lock:
            reason = self.blocked_reason(action_id)
            if action_id not in ACTIONS or reason:
                raise WizardError(
                    "CAMERA_SETUP_BLOCKED", reason or "Unknown probe record action."
                )
            if (
                type(expected_context_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", expected_context_sha256) is None
                or type(operation_id) is not str
                or not 1 <= len(operation_id) <= 96
            ):
                raise WizardError(
                    "CAMERA_PROBE_QUEUE_INVALID",
                    "An exact queued probe record action is required.",
                )
            self._probe_queues[action_id] = dict(
                context_sha256=expected_context_sha256,
                operation_id=operation_id,
                claimed=False,
            )
            self.invalidate()

    def probe_record_view(self) -> dict[str, Any]:
        """Small cached UI/export pointer; full compound records stay separate."""
        with self._lock:
            row = (self._source_workflow or {}).get("camera_probe_preparation") or {}
            pending = self._publication["status"] == "PENDING"
            return deepcopy(
                dict(
                    schema="rocell.wizard_camera_probe_setup.v1",
                    source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                    publication=self._publication,
                    state=(
                        "PENDING_PUBLICATION"
                        if pending
                        else row.get("state", "NOT_PREPARED")
                    ),
                    preparation_sha256=(
                        None
                        if pending
                        else (row.get("preparation") or {}).get("evidence_sha256")
                    ),
                    review_sha256=(
                        None
                        if pending
                        else (row.get("review") or {}).get("evidence_sha256")
                    ),
                    attempts={
                        action: dict(
                            claimed=queue["claimed"],
                            status=self._probe_attempts.get(action, {}).get(
                                "status", "QUEUED_NOT_DISPATCHED"
                            ),
                        )
                        for action, queue in self._probe_queues.items()
                    },
                    export_available=bool(row or self._probe_queues),
                    export_action="physical_camera_probe_export",
                    original_documents_included=False,
                    physical_authority=False,
                    hardware_qualified=False,
                    connected=False,
                    meaning="File-only preparation/review. CURRENT describes logged records, not camera admission. Inspect incomplete attempts; no automatic retry. Camera access and arm movement remain held.",
                )
            )

    def probe_record_diagnostics(self) -> dict[str, Any] | None:
        """Full file-only cache for a dedicated export, never the general card."""
        with self._lock:
            workflow = (
                self.session.retained_source_workflow() or self._source_workflow or {}
            )
            original = workflow.get("camera_probe_preparation")
            if original is None and not self._probe_queues:
                return None
            return deepcopy(
                dict(
                    schema="rocell.camera_probe_setup_diagnostics.v1",
                    source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                    publication=self._publication,
                    original=original,
                    attempts=self._probe_attempts,
                    queues=self._probe_queues,
                    physical_authority=False,
                    hardware_qualified=False,
                    connected=False,
                    meaning="Original/attempted file-only preparation and review. Currentness and device admission cannot be restored from an export.",
                )
            )

    def blocked_reason(self, action_id: str) -> str | None:
        if action_id not in SETUP_ACTIONS:
            return "Unknown camera setup action."
        if self.mode != "physical":
            return "Camera-only physical diagnostic storage requires physical mode; no device is opened."
        state = self.session.view()
        from .camera_probe_setup_service import (
            ACTIONS as PROBE_ACTIONS,
            PREPARE,
            record_boundary,
        )

        if action_id in PROBE_ACTIONS:
            if action_id in self._probe_queues:
                return "This probe record action was attempted. Inspect/export its outcome without replay."
            if self._publication["status"] != "CURRENT" or not record_boundary(
                self._source_workflow, action_id
            ):
                return "Publish the exact original camera setup boundary first. Partial or already reviewed records are diagnostic-only."
            verification, stages = state["verification"], state["stages"]
            expected_stage = "WAITING_OPERATOR" if action_id == PREPARE else "BLOCKED"
            if (
                not verification
                or verification.get("effects_allowed_by_m1_storage") is not True
                or not stages
                or len(stages) != len(STAGE_ORDER)
                or any(row["state"] != "PASS" for row in stages[:4])
                or stages[4]["state"] != expected_stage
                or any(row["state"] != "PENDING" for row in stages[5:])
            ):
                return "Verify the original stage and storage before retaining a probe record."
            assert (
                self._source_workflow is not None
            )  # record_boundary checked the cache.
            if (
                action_id != PREPARE
                and self._source_workflow["camera_probe_preparation"]["preparation"][
                    "document"
                ]["plan"]["launch_session_id"]
                != self.launch_id
            ):
                return "A reopened preparation is historical-only; it cannot restore its prior current enrollment."
            return None
        if action_id == "physical_camera_mode_enter":
            from .physical_camera_mode_entry_service import entry_boundary

            if self._mode_entry_attempted:
                return "Camera setup entry was attempted. Inspect/export the original outcome; do not replay it."
            if self._publication["status"] != "CURRENT":
                return "Refresh/reopen and publish the original camera setup first."
            if not entry_boundary(self._source_workflow):
                return "A complete accepted original camera-identity review is required. Partial or already entered records are read-only."
            verification, stages = state["verification"], state["stages"]
            if (
                not verification
                or verification["effects_allowed_by_m1_storage"] is not True
                or not stages
                or len(stages) != len(STAGE_ORDER)
                or any(row["state"] != "PASS" for row in stages[:4])
                or any(row["state"] != "PENDING" for row in stages[4:])
            ):
                return "Verify the exact original stage boundary before continuing camera setup."
            return None
        if action_id in {"physical_camera_discover", "physical_camera_reopen"}:
            if self._reopen_attempted or state["status"] != "NOT_INITIALIZED":
                return "This launch already owns or attempted an original camera store. Verify/export it; do not switch to a replacement."
            if action_id == "physical_camera_reopen" and not self.reopen_choices():
                return "Explicitly discover and select a source-matching original camera store first."
            return None
        if action_id == "physical_camera_initialize":
            return (
                "Initialization is one-use; inspect the original store without replacing it."
                if self._reopen_attempted
                or state["initialize_attempted"]
                or state["status"] != "NOT_INITIALIZED"
                else None
            )
        if action_id == "physical_camera_refresh":
            return (
                "Initialize this assigned camera store explicitly first."
                if state["status"] == "NOT_INITIALIZED"
                and self._original_descriptor is None
                else None
            )
        if action_id in {
            "physical_camera_assess_sources",
            "physical_camera_review_sources",
        }:
            verification = state["verification"]
            stages = state["stages"]
            if (
                not verification
                or verification["effects_allowed_by_m1_storage"] is not True
                or not stages
            ):
                return "Verify the original camera setup records first."
            workflow = self._source_workflow
            if not workflow or workflow["prerequisites"] is None:
                return (
                    "Collect or reopen and verify original build prerequisites first."
                )
            if action_id == "physical_camera_assess_sources":
                if self._assessment_attempted or workflow["receipt"] is not None:
                    return "Source assessment was already attempted. Verify/export the original evidence; do not replay it."
                if stages[0]["state"] != "WAITING_OPERATOR":
                    return "Assessment requires the original waiting workspace-sources stage."
            else:
                if self._review_attempted or workflow["review"] is not None:
                    return "Source review was already attempted. Verify/export the original evidence; do not replay it."
                if (
                    stages[0]["state"] != "REVIEW_PENDING"
                    or workflow["assessment"] is None
                ):
                    return "Produce and verify the original source assessment before review."
            return None
        with self._lock:
            if self._collection_attempted:
                return "This launch already attempted prerequisite collection. Export and review the original evidence; do not replay it."
        verification = state["verification"]
        if (
            not verification
            or verification["effects_allowed_by_m1_storage"] is not True
        ):
            return "Explicitly initialize or verify unheld original camera-only storage first."
        stages = state["stages"]
        if not stages or stages[0]["state"] != "PENDING":
            return "Prerequisite collection requires the original pending workspace-sources stage."
        return None

    def reopen_choices(self) -> list[dict[str, Any]]:
        return self._registry.choices() if self._discovery_published else []

    def target_directory(self) -> str:
        """Actual explicit setup target, even before failed-reopen plan adoption."""
        return (
            str(self._original_descriptor.directory)
            if self._original_descriptor is not None
            else self.session.descriptor()["directory"]
        )

    def reopen_preview(self, choice_id: str) -> dict[str, Any]:
        return self._registry.preview(choice_id)

    def original_probe_context(
        self, enrollment: WizardNativeCameraEnrollment
    ) -> dict[str, Any]:
        """Small cached ticket binding, never the substantive admission reader.

        Arrival owns current logged enrollment. The acquisition service must
        still authenticate the complete original history under CAMERA ownership.
        This accessor performs no refresh, filesystem read or device operation.
        """
        from .camera_probe_preparation import SOURCE_WORKFLOW_PROBE_SCHEMA

        with self._lock:
            workflow = self._source_workflow or {}
            row = workflow.get("camera_probe_preparation") or {}
            state = self.session.view()
            verification, stages = state["verification"], state["stages"]
            if (
                self.mode != "physical"
                or self._publication["status"] != "CURRENT"
                or workflow.get("schema") != SOURCE_WORKFLOW_PROBE_SCHEMA
                or row.get("state") != "REVIEWED_FOR_ADMISSION"
                or not verification
                or verification.get("effects_allowed_by_m1_storage") is not True
                or not stages
                or len(stages) != len(STAGE_ORDER)
                or any(stage["state"] != "PASS" for stage in stages[:4])
                or stages[4]["state"] != "WAITING_OPERATOR"
                or any(stage["state"] != "PENDING" for stage in stages[5:])
            ):
                raise WizardError(
                    "CAMERA_PROBE_SETUP_REQUIRED",
                    "Publish and verify the original preparation and separate review before probing. No setup is synthesized automatically.",
                )
            preparation = row["preparation"]
            plan = preparation["document"]["plan"]
            if (
                type(enrollment) is not WizardNativeCameraEnrollment
                or plan["launch_session_id"] != self.launch_id
                or canonical(enrollment.export_snapshot())
                != canonical(preparation["document"]["enrollment"])
                or workflow["session_header_sha256"]
                != verification.get("session", {}).get("header_sha256")
            ):
                raise WizardError(
                    "CAMERA_PROBE_CONTEXT_CHANGED",
                    "The current enrollment, launch or original setup changed; a saved enrollment cannot substitute for its current owner.",
                )
            return dict(
                session=self.session.descriptor(),
                publication=deepcopy(self._publication),
                verification_sha256=digest(canonical(verification)),
                expected_header_sha256=workflow["session_header_sha256"],
                expected_preparation_sha256=preparation["evidence_sha256"],
                expected_review_sha256=row["review"]["evidence_sha256"],
                expected_plan_sha256=digest(canonical(plan)),
                enrollment_sha256=digest(canonical(enrollment.export_snapshot())),
            )

    def planning_blocked_reason(self) -> str | None:
        if self._reopen_attempted and (
            not self._reopen_verified or self._publication["status"] != "CURRENT"
        ):
            return "Original camera-store opening is not currently verified/published. Inspect or verify the same store before planning; no replacement is selected."
        return None

    def context_sha256(
        self,
        action_id: str,
        enrollment: WizardNativeCameraEnrollment,
        source_report: PhysicalSourcePreflightReport | None,
        choice_id: str | None = None,
    ) -> str:
        """Pure server-side ticket context; no caller-provided evidence hash."""
        return digest(
            canonical(
                {
                    "action_id": action_id,
                    "session": self.session.view(),
                    "collection_attempted": self._collection_attempted,
                    "assessment_attempted": self._assessment_attempted,
                    "review_attempted": self._review_attempted,
                    "source_workflow_sha256": (
                        None
                        if self._source_workflow is None
                        else digest(canonical(self._source_workflow))
                    ),
                    "reopen_attempted": self._reopen_attempted,
                    "discovery_published": self._discovery_published,
                    "selected_original": self._selected_original,
                    "discovery": self._registry.view(),
                    "requested_original": (
                        None if choice_id is None else self._registry.preview(choice_id)
                    ),
                    "enrollment": enrollment.export_snapshot(),
                    "source_report_sha256": (
                        None if source_report is None else source_report.sha256
                    ),
                }
            )
        )

    @staticmethod
    def source_report_from_retained(
        value: dict[str, Any] | None,
    ) -> PhysicalSourcePreflightReport | None:
        """Restore only the application's own retained source-only report."""
        if value is None:
            return None
        if value.get("retention") != "M1_FULL_BYTES_READ_BACK":
            raise WizardError(
                "CAMERA_SOURCE_REPORT_RETENTION",
                "Original retained source report required.",
            )
        payload = (
            json.dumps(
                value["retained_source_report"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("ascii")
        report = PhysicalSourcePreflightReport(payload)
        if report.sha256 != value["retained_report_sha256"]:
            raise WizardError(
                "CAMERA_SOURCE_REPORT_HASH", "Original source report hash differs."
            )
        return report

    def perform(
        self,
        action_id: str,
        *,
        expected_context_sha256: str,
        operator_id: str,
        enrollment: WizardNativeCameraEnrollment,
        source_report: PhysicalSourcePreflightReport | None,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        choice_id: str | None = None,
        deadline_ns: int | None = None,
        validate_current_enrollment: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        if not self._operation_lock.acquire(blocking=False):
            raise WizardError("CAMERA_SETUP_BUSY", "A camera setup action is active.")
        try:
            from .camera_probe_setup_service import ACTIONS as PROBE_ACTIONS

            if action_id == "physical_camera_mode_enter":
                queue = self._mode_entry_queue
                if (
                    queue is None
                    or queue["claimed"] is not False
                    or queue["context_sha256"] != expected_context_sha256
                ):
                    raise WizardError(
                        "CAMERA_MODE_QUEUE_REQUIRED",
                        "Use the one-time explicit queued camera setup action.",
                    )
                queue["claimed"] = True
                reason = None
            elif action_id in PROBE_ACTIONS:
                queue = self._probe_queues.get(action_id)
                if (
                    queue is None
                    or queue["claimed"] is not False
                    or queue["context_sha256"] != expected_context_sha256
                ):
                    raise WizardError(
                        "CAMERA_PROBE_QUEUE_REQUIRED",
                        "Use the wizard's one-time queued probe record action.",
                    )
                queue["claimed"] = True
                reason = None
            else:
                reason = self.blocked_reason(action_id)
            if reason:
                raise WizardError("CAMERA_SETUP_BLOCKED", reason)
            if action_id == "physical_camera_mode_enter" or action_id in PROBE_ACTIONS:
                from .physical_camera_mode_entry import camera_mode_operator_valid

                # Entry labels are data only, unlike the older portable-ID
                # workflows. Reuse the exact codec rule instead of rejecting a
                # label that the action preview already accepted.
                operator_valid = camera_mode_operator_valid(operator_id)
                operator_message = "Use a trimmed setup label of 1–64 UTF-8 bytes, without control characters."
            else:
                operator_valid = portable_setup_operator_valid(operator_id)
                operator_message = PORTABLE_SETUP_OPERATOR_HELP
            if not operator_valid:
                raise WizardError("CAMERA_SETUP_OPERATOR", operator_message)
            if (
                self.context_sha256(action_id, enrollment, source_report, choice_id)
                != expected_context_sha256
            ):
                raise WizardError(
                    "CAMERA_SETUP_CONTEXT_CHANGED",
                    "Preview the current original-store context again.",
                )
            self.invalidate()
            self._last_action = action_id
            if action_id == "physical_camera_mode_enter":
                from .physical_camera_mode_entry_service import enter_camera_mode

                enter_camera_mode(
                    self,
                    operator_id=operator_id,
                    cancellation=cancellation,
                    progress=progress,
                    deadline_ns=deadline_ns,
                )
            elif action_id in PROBE_ACTIONS:
                from .camera_probe_setup_service import write_probe_record

                write_probe_record(
                    self,
                    action_id,
                    operator_id=operator_id,
                    enrollment=enrollment,
                    cancellation=cancellation,
                    progress=progress,
                    deadline_ns=deadline_ns,
                    validate_current_enrollment=validate_current_enrollment,
                )
            elif action_id == "physical_camera_discover":
                self._discovery_published = False
                progress(
                    "Inspecting original camera-store metadata only; no store or device is opened."
                )
                self._registry.discover(
                    cancellation=cancellation,
                    deadline_ns=monotonic_ns() + 30_000_000_000,
                )
            elif action_id == "physical_camera_reopen":
                if choice_id is None:
                    raise WizardError(
                        "CAMERA_ORIGINAL_CHOICE",
                        "Choose the original camera store explicitly.",
                    )
                with self._lock:
                    self._reopen_attempted = True
                    self._selected_original = self._registry.preview(choice_id)
                    self._original_descriptor = self._registry.descriptor(choice_id)
                self._open_selected(cancellation, progress, replace_owner=True)
            elif action_id == "physical_camera_prerequisites":
                with self._lock:
                    self._collection_attempted = True
                self._collect(enrollment, source_report, cancellation, progress)
                self._read_source_workflow(cancellation, progress)
            elif action_id in {
                "physical_camera_assess_sources",
                "physical_camera_review_sources",
            }:
                self._advance_source_workflow(
                    action_id, operator_id, cancellation, progress
                )
            elif action_id == "physical_camera_initialize":
                self.session.initialize(cancellation=cancellation, progress=progress)
            elif self._selected_original is not None:
                self._open_selected(cancellation, progress, replace_owner=False)
            else:
                self.session.refresh(cancellation=cancellation, progress=progress)
                self._read_source_workflow(cancellation, progress)
            with self._lock:
                self._publication = {"status": "PENDING", "operation_id": None}
            report = self.retained_diagnostics()
            report["source_workflow"] = self.source_workflow_view()
            if report["prerequisites"] is not None:
                # Keep the complete readable document one level shallower:
                # its catalog has eight levels and the shared diagnostic wire
                # contract permits twelve. Do not weaken that global bound or
                # truncate nested intake/acceptance requirements.
                report["prerequisite_document"] = report["prerequisites"].pop(
                    "document"
                )
            return {
                "schema": "rocell.wizard_worker_result.v1",
                "action_id": action_id,
                "status": "SUCCEEDED",
                "steps": [
                    {
                        "name": action_id,
                        "exit_code": 0,
                        "report": {
                            "operator_id": operator_id,
                            "context_meaning": "Original store context only; reopening never imports old metadata as a current connection or replays hardware.",
                            **report,
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
        except BaseException:
            if action_id == "physical_camera_mode_enter" or action_id in {
                "physical_camera_probe_prepare",
                "physical_camera_probe_review",
            }:
                self.invalidate()
            raise
        finally:
            self._operation_lock.release()

    def _open_selected(
        self,
        cancellation: threading.Event,
        progress: Callable[[str], None],
        *,
        replace_owner: bool,
    ) -> None:
        selected = self._selected_original
        if selected is None:
            raise WizardError(
                "CAMERA_ORIGINAL_CHOICE", "No original camera store selected."
            )
        original_descriptor = self._original_descriptor
        if original_descriptor is None:
            raise WizardError(
                "CAMERA_ORIGINAL_CHOICE",
                "The immutable original selection is missing; no replacement is opened.",
            )
        deadline = monotonic_ns() + 120_000_000_000
        self._reopen_verified = False
        scope = (
            self._registry.selected(
                selected["choice_id"],
                selected["discovery_sha256"],
                cancellation=cancellation,
                deadline_ns=deadline,
            )
            if replace_owner
            else self._registry.revalidate_original(
                original_descriptor,
                selected["descriptor_sha256"],
                cancellation=cancellation,
                deadline_ns=deadline,
            )
        )
        with scope as descriptor:
            if (
                replace_owner
                or self.session.descriptor()["launch_id"] != descriptor.origin_launch_id
            ):
                if (
                    not replace_owner
                    and self.session.view()["status"] != "NOT_INITIALIZED"
                ):
                    raise WizardError(
                        "CAMERA_ORIGINAL_OWNER_CHANGED",
                        "Refresh cannot switch an existing camera-store owner.",
                    )
                # Bind the explicit original path even if its refresh later
                # fails. Do not leave a fresh launch as an implicit fallback.
                self.session = PhysicalCameraSession(
                    self.workspace,
                    descriptor.directory,
                    launch_id=descriptor.origin_launch_id,
                    source_sha256=self.source_sha256,
                    cell_id=descriptor.cell_id,
                    session_id=descriptor.session_id,
                )
            self.session.refresh(cancellation=cancellation, progress=progress)
            workflow = self.session.read_original_source_workflow(
                expected_header_sha256=descriptor.header_sha256,
                cancellation=cancellation,
                progress=progress,
                deadline_ns=deadline,
            )
            self._adopt_source_workflow(workflow)
        # The registry's after-yield check verifies original immutable metadata,
        # identity and deadline again before any current planning target changes.
        self._acquisition.bind_verified_session(self.session)
        self._reopen_verified = True

    def _read_source_workflow(
        self, cancellation, progress, *, deadline_ns=None
    ) -> None:
        verification = self.session.view()["verification"]
        if not verification:
            raise WizardError(
                "CAMERA_SOURCE_AUDIT_REQUIRED", "Verify the original store first."
            )
        workflow = self.session.read_original_source_workflow(
            expected_header_sha256=verification["session"]["header_sha256"],
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
        )
        self._adopt_source_workflow(workflow)

    def _source_artifacts(self, workflow):
        """Verify the exact retained chain again; inputs never come from the UI."""
        from .physical_source_stage_evidence import (
            verify_workspace_source_receipt,
            verify_workspace_source_assessment,
            verify_workspace_source_review,
        )

        bound = self.session.descriptor()
        record = workflow["prerequisites"]
        prerequisites = (
            None
            if record is None
            else verify_physical_camera_prerequisites(
                canonical(record["document"]),
                expected_source_sha256=self.source_sha256,
                expected_session_id=bound["session_id"],
                expected_launch_session_id=bound["launch_id"],
                expected_evidence_sha256=record["evidence_sha256"],
            )
        )
        artifacts: dict[str, Any] = {}
        if workflow["receipt"] is not None:
            assert prerequisites is not None
            record = workflow["receipt"]
            artifacts["receipt"] = verify_workspace_source_receipt(
                canonical(record["document"]),
                prerequisites=prerequisites,
                expected_source_sha256=self.source_sha256,
                expected_session_id=bound["session_id"],
                expected_origin_launch_id=bound["launch_id"],
                expected_header_sha256=workflow["session_header_sha256"],
                expected_receipt_sha256=record["evidence_sha256"],
            )
        if workflow["assessment"] is not None:
            record = workflow["assessment"]
            artifacts["assessment"] = verify_workspace_source_assessment(
                canonical(record["document"]),
                receipt=artifacts["receipt"],
                expected_assessment_sha256=record["evidence_sha256"],
            )
        if workflow["review"] is not None:
            record = workflow["review"]
            artifacts["review"] = verify_workspace_source_review(
                canonical(record["document"]),
                receipt=artifacts["receipt"],
                assessment=artifacts["assessment"],
                expected_review_sha256=record["evidence_sha256"],
            )
        return prerequisites, artifacts

    def _adopt_source_workflow(self, workflow) -> None:
        prerequisites, artifacts = self._source_artifacts(workflow)
        with self._lock:
            self._source_workflow = deepcopy(workflow)
            self._retained = deepcopy(workflow["prerequisites"])
            self._prerequisites = (
                None if prerequisites is None else prerequisites.safe_summary()
            )
            self._source_summaries = {
                role: artifact.safe_summary() for role, artifact in artifacts.items()
            }
            self._collection_attempted |= (
                prerequisites is not None or workflow["state"] != "PENDING"
            )
            self._assessment_attempted |= "receipt" in artifacts
            self._review_attempted |= "review" in artifacts
            # The original reader verifies the epoch's prefix, references and
            # prerequisites against the current audited original store. Legacy
            # histories without this role stay missing, never auto-generated.
            self._epoch_record = deepcopy(workflow.get("configuration_epochs"))

    def _advance_source_workflow(
        self, action_id, actor, cancellation, progress
    ) -> None:
        from .physical_source_stage_evidence import (
            WorkspaceSourceEvidenceError,
            collect_workspace_source_receipt,
            assess_workspace_source_receipt,
            review_workspace_source_assessment,
        )

        deadline = monotonic_ns() + 120_000_000_000

        def check():
            if cancellation.is_set() or monotonic_ns() >= deadline:
                raise WizardError(
                    "CAMERA_SOURCE_WORKFLOW_INTERRUPTED",
                    "Stopped or expired; verify/export original records without replay.",
                )
            if source_fingerprint(self.workspace) != self.source_sha256:
                raise WizardError(
                    "CAMERA_SETUP_SOURCE_CHANGED",
                    "Source changed; retained records are historical only.",
                )
            if cancellation.is_set() or monotonic_ns() >= deadline:
                raise WizardError(
                    "CAMERA_SOURCE_WORKFLOW_INTERRUPTED",
                    "Stopped or expired during source verification; no next mutation is admitted.",
                )

        check()
        workflow = deepcopy(self._source_workflow)
        if workflow is None:
            raise WizardError(
                "CAMERA_SOURCE_AUDIT_REQUIRED",
                "Original source workflow must be audited first.",
            )
        prerequisites, artifacts = self._source_artifacts(workflow)
        bound = self.session.descriptor()
        reviewing = action_id == "physical_camera_review_sources"
        new: dict[str, Any]
        if reviewing:
            # Validate distinct procedural labels before recording any attempt.
            review = review_workspace_source_assessment(
                artifacts["receipt"],
                artifacts["assessment"],
                reviewer_id=actor,
                review_launch_id=self.launch_id,
            )
            with self._lock:
                self._review_attempted = True
            new = {"review": review}
        else:
            with self._lock:
                self._assessment_attempted = True
            try:
                receipt = collect_workspace_source_receipt(
                    self.workspace,
                    prerequisites=prerequisites,
                    source_sha256=self.source_sha256,
                    session_id=bound["session_id"],
                    origin_launch_id=bound["launch_id"],
                    collection_launch_id=self.launch_id,
                    header_sha256=workflow["session_header_sha256"],
                    operator_id=actor,
                    cancellation=cancellation,
                    progress=progress,
                )
            except WorkspaceSourceEvidenceError as error:
                if error.receipt is not None:
                    with self._lock:
                        self._source_attempt_records = {
                            "receipt": {
                                "document": error.receipt.to_dict(),
                                "evidence_sha256": error.receipt.sha256,
                                "retention": "COLLECTED_NOT_M1_RETAINED",
                                "reference": None,
                            }
                        }
                raise
            new = {
                "receipt": receipt,
                "assessment": assess_workspace_source_receipt(receipt),
            }
        with self._lock:
            self._source_attempt_records = {
                role: {
                    "document": item.to_dict(),
                    "evidence_sha256": item.sha256,
                    "retention": "COLLECTED_NOT_M1_RETAINED",
                    "reference": None,
                }
                for role, item in new.items()
            }
        check()
        verified = self.session.view()["verification"]
        stage = PhysicalOnboardingStage.WORKSPACE_SOURCES
        expected_state = (
            V2StageState.REVIEW_PENDING if reviewing else V2StageState.WAITING_OPERATOR
        )
        from .physical_onboarding import _parse_evidence_reference

        references = (
            []
            if not reviewing
            else [
                _parse_evidence_reference(workflow[role]["reference"])
                for role in ("receipt", "assessment")
            ]
        )
        with self.session.stage_transaction(
            expected_challenge_sha256=verified["challenge_sha256"]
        ) as transaction:
            snapshot = transaction.snapshot()
            if (
                snapshot.next_action.stage is not stage
                or snapshot.next_action.stage_state is not expected_state
                or snapshot.head.head_sha256 != workflow["session_head_sha256"]
            ):
                raise WizardError(
                    "CAMERA_SETUP_STAGE_CHANGED",
                    "Original assessed stage/head changed; no evidence replayed.",
                )
            for role, item in new.items():
                check()
                reference = transaction.store_evidence(
                    stage,
                    item.payload,
                    label="workspace-source-" + role + "-v1",
                    media_type="application/json",
                    captured_at_ns=time_ns(),
                    expected_head_sha256=transaction.snapshot().head.head_sha256,
                )
                with self._lock:
                    self._source_attempt_records[role].update(
                        retention="M1_PUBLISHED_READBACK_PENDING",
                        reference=reference.to_dict(),
                    )
                raw = transaction.read_stage_evidence(reference)
                if raw != item.payload:
                    raise WizardError(
                        "CAMERA_SOURCE_READBACK_CHANGED",
                        "Original evidence readback differs.",
                    )
                with self._lock:
                    self._source_attempt_records[role][
                        "retention"
                    ] = "M1_FULL_BYTES_READ_BACK"
                references.append(reference)
            check()
            transaction.commit_stage_state(
                stage,
                V2StageState.BLOCKED if reviewing else V2StageState.REVIEW_PENDING,
                occurred_at_ns=time_ns(),
                detail_code=(
                    "WORKSPACE_SOURCES_REVIEWED_BLOCKED"
                    if reviewing
                    else "WORKSPACE_SOURCES_ASSESSMENT_SAVED"
                ),
                expected_head_sha256=transaction.snapshot().head.head_sha256,
                evidence=tuple(references),
            )
            check()
        # Only an audit after lease exit can restore current publication.
        self.session.refresh(cancellation=cancellation, progress=progress)
        self._read_source_workflow(cancellation, progress, deadline_ns=deadline)
        check()

    def _collect(
        self,
        enrollment: WizardNativeCameraEnrollment,
        source_report: PhysicalSourcePreflightReport | None,
        cancellation: threading.Event,
        progress: Callable[[str], None],
    ) -> None:
        deadline = monotonic_ns() + 120_000_000_000

        def check() -> None:
            if cancellation.is_set() or monotonic_ns() >= deadline:
                raise WizardError(
                    "CAMERA_SETUP_COLLECTION_INTERRUPTED",
                    "Collection stopped or expired; inspect retained state without replay.",
                )
            if source_fingerprint(self.workspace) != self.source_sha256:
                raise WizardError(
                    "CAMERA_SETUP_SOURCE_CHANGED",
                    "Source changed; original evidence is historical only.",
                )
            if cancellation.is_set() or monotonic_ns() >= deadline:
                raise WizardError(
                    "CAMERA_SETUP_COLLECTION_INTERRUPTED",
                    "Collection stopped or expired; no current publication.",
                )

        check()
        selected = (
            None
            if enrollment.binding() is None
            else selection_from_enrollment(
                enrollment,
                source_sha256=self.source_sha256,
                launch_session_id=self.launch_id,
            )
        )
        bound = self.session.descriptor()
        if bound["launch_id"] != self.launch_id:
            # A newly requested fixed-build checklist may continue an untouched
            # pending original store. New-launch metadata cannot be silently
            # relabeled as observations made by its origin launch.
            selected, source_report = None, None
        progress(
            "Reading the four fixed build requirement sources; missing physical observations remain pending."
        )
        artifact = collect_physical_camera_prerequisites(
            self.workspace,
            source_sha256=self.source_sha256,
            session_id=bound["session_id"],
            launch_session_id=bound["launch_id"],
            cancellation=cancellation,
            deadline_ns=min(deadline, monotonic_ns() + 30_000_000_000),
            selection=selected,
            source_preflight_report=source_report,
            expected_source_preflight_sha256=(
                None if source_report is None else source_report.sha256
            ),
        )
        with self._lock:
            self._retained = {
                "document": artifact.to_dict(),
                "evidence_sha256": artifact.evidence_sha256,
                "retention": "COLLECTED_NOT_M1_RETAINED",
                "reference": None,
            }
        check()
        verified = self.session.view()["verification"]
        stage = PhysicalOnboardingStage.WORKSPACE_SOURCES
        with self.session.stage_transaction(
            expected_challenge_sha256=verified["challenge_sha256"]
        ) as transaction:
            snapshot = transaction.snapshot()
            if (
                snapshot.next_action.stage is not stage
                or snapshot.next_action.stage_state is not V2StageState.PENDING
            ):
                raise WizardError(
                    "CAMERA_SETUP_STAGE_CHANGED",
                    "Original pending source stage required.",
                )
            check()
            # V2 permits evidence publication only after the operator-wait stage
            # begins. This event requests evidence; it does not accept anything.
            snapshot = transaction.commit_stage_state(
                stage,
                V2StageState.WAITING_OPERATOR,
                occurred_at_ns=time_ns(),
                detail_code="CAMERA_PREREQUISITES_REQUESTED",
                expected_head_sha256=snapshot.head.head_sha256,
            )
            check()
            reference = transaction.store_evidence(
                stage,
                artifact.payload,
                label="camera-prerequisites-requirements-only",
                media_type="application/json",
                captured_at_ns=time_ns(),
                expected_head_sha256=snapshot.head.head_sha256,
            )
            with self._lock:
                self._retained.update(
                    retention="M1_PUBLISHED_READBACK_PENDING",
                    reference=reference.to_dict(),
                )
            raw = transaction.read_stage_evidence(reference)
            retained = verify_physical_camera_prerequisites(
                raw,
                expected_source_sha256=self.source_sha256,
                expected_session_id=bound["session_id"],
                expected_launch_session_id=bound["launch_id"],
                expected_evidence_sha256=artifact.evidence_sha256,
            )
            with self._lock:
                self._retained.update(retention="M1_FULL_BYTES_READ_BACK")
            check()
            # Snapshot all eight dependency domains after the real prerequisite
            # bytes exist. No source/catalog file is relabeled as an observed
            # hardware binding. This initial record has no observed bindings.
            epochs = build_physical_configuration_epochs(
                retained, transaction.snapshot(), evidence_bindings=()
            )
            with self._lock:
                self._epoch_record = {
                    "document": epochs.to_dict(),
                    "evidence_sha256": epochs.sha256,
                    "retention": "COLLECTED_NOT_M1_RETAINED",
                    "reference": None,
                }
                self._epoch_attempt_record = deepcopy(self._epoch_record)
            check()
            epoch_reference = transaction.store_evidence(
                stage,
                epochs.payload,
                label="physical-configuration-epochs-v1",
                media_type="application/json",
                captured_at_ns=time_ns(),
                expected_head_sha256=transaction.snapshot().head.head_sha256,
            )
            with self._lock:
                self._epoch_record.update(
                    retention="M1_PUBLISHED_READBACK_PENDING",
                    reference=epoch_reference.to_dict(),
                )
                self._epoch_attempt_record = deepcopy(self._epoch_record)
            if transaction.read_stage_evidence(epoch_reference) != epochs.payload:
                raise WizardError(
                    "CAMERA_CONFIGURATION_READBACK_CHANGED",
                    "Original configuration record readback differs; no retry is permitted.",
                )
            with self._lock:
                self._epoch_record.update(retention="M1_FULL_BYTES_READ_BACK")
                self._epoch_attempt_record = deepcopy(self._epoch_record)
            check()
        # Refresh is a storage audit after our own stage-only mutation, never a
        # device retry or automatic repair. It has its own explicit bounded IO.
        self.session.refresh(cancellation=cancellation, progress=progress)
        with self._lock:
            self._prerequisites = retained.safe_summary()

    def _restore_prerequisites(
        self,
        enrollment: WizardNativeCameraEnrollment,
        source_report: PhysicalSourcePreflightReport | None,
    ) -> None:
        """Re-display original requirements only after a fresh full-store audit.

        Session.refresh re-hashes original packages under storage leases. Its
        verified inventory must identify exactly our retained package; an added,
        changed or missing item never licenses recollection or substitution.
        This is a cached document projection, not fresh physical observations.
        """
        with self._lock:
            original = deepcopy(self._retained)
        state = self.session.view()
        verification = state["verification"]
        if (
            original is None
            or original["retention"] != "M1_FULL_BYTES_READ_BACK"
            or not verification
        ):
            return
        reference = original["reference"]
        if verification["session"]["evidence_inventory_sha256"] != canonical_sha256(
            [reference]
        ):
            return
        bound = self.session.descriptor()
        payload = canonical(original["document"])
        artifact = verify_physical_camera_prerequisites(
            payload,
            expected_source_sha256=self.source_sha256,
            expected_session_id=bound["session_id"],
            expected_launch_session_id=self.launch_id,
            expected_evidence_sha256=original["evidence_sha256"],
        )
        if reference["payload_sha256"] != artifact.evidence_sha256 or reference[
            "payload_bytes"
        ] != len(payload):
            raise WizardError(
                "CAMERA_SETUP_RETAINED_REFERENCE",
                "Retained requirements reference differs.",
            )
        summary = artifact.safe_summary()
        selected = (
            None
            if enrollment.binding() is None
            else selection_from_enrollment(
                enrollment,
                source_sha256=self.source_sha256,
                launch_session_id=self.launch_id,
            ).safe_summary()
        )
        preflight_hash = None if source_report is None else source_report.sha256
        original_preflight = summary["source_preflight"]
        if (
            summary["metadata_selection"] != selected
            or (
                None
                if original_preflight is None
                else original_preflight["report_sha256"]
            )
            != preflight_hash
        ):
            return
        with self._lock:
            self._prerequisites = summary
