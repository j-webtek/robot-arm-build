"""Explicit wizard-to-M1 integration for actual files, never device onboarding.

The service creates its own immutable PHYSICAL_DIAGNOSTIC session, consumes one
source-only permit, and reads back complete evidence through the qualified store.
Neither a coherent report nor a known attempt completes a canonical stage.
Construction/status are inert; there is no implicit reopen, retry or cleanup.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, cast
import uuid

from rocell.application.cell_commissioning_coordinator import (
    PHYSICAL_DIAGNOSTIC_COMPOSITION,
    CommissioningPersistence,
    PhysicalDiagnosticPreflightCoordinator,
    RegisteredActionRequest,
)
from rocell.application.commissioning_physical_persistence import (
    M1PhysicalDiagnosticPersistence,
    PhysicalDiagnosticAdmissionFacts,
    physical_diagnostic_source_binding,
)
from rocell.application.configuration_epochs import load_configuration_epoch_policy
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_onboarding_stage_catalog import (
    load_physical_onboarding_stage_catalog,
)
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.physical_source_preflight import (
    SOURCE_PREFLIGHT_ACTION_ID,
    PhysicalSourcePreflightWorker,
    source_preflight_registration,
    verify_physical_source_preflight,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_coordinator import (
    require_regular_path,
    source_fingerprint,
)
from rocell.application.wizard_diagnostic_export import _directory_guard


class PhysicalSourcePreflightService:
    """One explicit, finite file campaign per launch; physical effects absent."""

    def __init__(self, workspace: Path, *, launch_id: str, source_sha256: str) -> None:
        if (
            not isinstance(workspace, Path)
            or not workspace.is_absolute()
            or type(launch_id) is not str
            or re.fullmatch(r"wizard-[0-9a-f]{32}", launch_id) is None
            or type(source_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None
        ):
            raise WizardError("PREFLIGHT_BINDING", "Exact launch/source required.")
        self.workspace, self.source_sha256 = workspace, source_sha256
        self.directory = (
            workspace / "software/runs/physical-source-preflight" / launch_id
        )
        suffix = uuid.uuid4().hex
        self.cell_id = "wizard-physical-diagnostic-" + suffix[:16]
        self.session_id = "physical-diagnostic-" + suffix
        self._lock = threading.RLock()
        self._used = False
        self._retained_report: dict[str, Any] | None = None
        self._cached: dict[str, Any] = {
            "schema": "rocell.physical_source_preflight_view.v1",
            "status": "NOT_STARTED",
            "directory": str(self.directory),
            "session_id": self.session_id,
            "cell_id": self.cell_id,
            "composition": PHYSICAL_DIAGNOSTIC_COMPOSITION,
            "report": None,
            "attempt": None,
            "error": None,
            "canonical_stage_state": None,
            "canonical_stage_pass": False,
            "physical_authority": False,
            "power_state": "UNKNOWN",
            "device_io_performed": False,
            "replay_allowed": False,
            "next_step": "Explicitly run the source preflight. It checks files only; leave hardware disconnected.",
        }

    def view(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._cached)

    def blocked_reason(self) -> str | None:
        with self._lock:
            if os.name != "nt":
                return "Durable source preflight requires the qualified Windows/NTFS storage implementation."
            if self._used:
                return "This launch already attempted source preflight. Export its evidence; restart explicitly for a new diagnostic session. No attempt is replayed."
            return None

    def retained_report(self) -> dict[str, Any] | None:
        """Already read-verified historical bytes, including after late failure."""
        with self._lock:
            return deepcopy(self._retained_report)

    def _current_source(self) -> None:
        if source_fingerprint(self.workspace) != self.source_sha256:
            raise WizardError(
                "PREFLIGHT_SOURCE_CHANGED",
                "Source changed; retain this run and restart after reviewing the change.",
            )

    def _facts(
        self, request: RegisteredActionRequest, snapshot: Any
    ) -> PhysicalDiagnosticAdmissionFacts:
        # These eight source-derived placeholders are not installed hardware
        # epochs or claims that the physical hazard register has been closed.
        self._current_source()
        policy = load_configuration_epoch_policy(self.workspace)
        catalog = load_physical_onboarding_stage_catalog(self.workspace)
        if (
            request.cell_id != self.cell_id
            or request.session_id != self.session_id
            or request.action_id != SOURCE_PREFLIGHT_ACTION_ID
            or snapshot.next_action.stage
            is not PhysicalOnboardingStage.WORKSPACE_SOURCES
        ):
            raise WizardError("PREFLIGHT_SCOPE", "Source-only session/stage mismatch.")
        return PhysicalDiagnosticAdmissionFacts(
            {
                "composition": PHYSICAL_DIAGNOSTIC_COMPOSITION,
                "catalog_sha256": catalog.source_sha256,
                "workspace_source_sha256": self.source_sha256,
                "physical_hazards_closed": False,
                "disconnected_condition_observed": False,
                "device_io_permitted": False,
            },
            tuple(
                {
                    "composition": PHYSICAL_DIAGNOSTIC_COMPOSITION,
                    "epoch_id": epoch.epoch_id,
                    "policy_sha256": policy.source_sha256,
                    "workspace_source_sha256": self.source_sha256,
                    "physical_epoch": "UNMEASURED",
                }
                for epoch in policy.epochs
            ),
            None,
        )

    def perform(
        self,
        operator_id: str,
        *,
        cancellation: threading.Event,
        progress: Callable[[str], None],
    ) -> dict[str, Any]:
        if (
            type(operator_id) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", operator_id) is None
        ):
            raise WizardError(
                "PREFLIGHT_OPERATOR", "Use a 1–64 character operator identifier."
            )
        if not isinstance(cancellation, threading.Event) or not callable(progress):
            raise WizardError(
                "PREFLIGHT_LIFETIME", "Cancellation and progress required."
            )
        with self._lock:
            reason = self.blocked_reason()
            if reason:
                raise WizardError("PREFLIGHT_HELD", reason)
            self._used = True
            self._cached["status"] = "RUNNING"
        started = time.monotonic_ns()
        deadline = started + 120_000_000_000

        def check() -> None:
            if cancellation.is_set():
                raise WizardError(
                    "PREFLIGHT_CANCELLED",
                    "Source preflight stopped. Retain partial records; no automatic retry.",
                )
            if time.monotonic_ns() >= deadline:
                raise WizardError(
                    "PREFLIGHT_TIMED_OUT",
                    "Source preflight exceeded its original diagnostic window.",
                )

        try:
            check()
            self._current_source()
            registration = source_preflight_registration(self.workspace)
            worker = PhysicalSourcePreflightWorker(
                self.workspace,
                expected_source_sha256=self.source_sha256,
                worker_executable_sha256=registration.worker_executable_sha256,
                operator_id=operator_id,
            )
            progress(
                "Qualifying a separate source-only diagnostic store; no hardware is queried."
            )
            check()
            runs = require_regular_path(
                self.workspace / "software/runs", directory=True
            )
            # Pin ancestry for exclusive directory creation. M1 additionally
            # owns its qualified storage leases and content verification.
            with _directory_guard(runs, allow_directory_write_sharing=True):
                check()
                if not self.directory.parent.exists():
                    self.directory.parent.mkdir(exist_ok=False)
                require_regular_path(self.directory.parent, directory=True)
                with _directory_guard(
                    self.directory.parent, allow_directory_write_sharing=True
                ):
                    check()
                    self.directory.mkdir(exist_ok=False)
                    require_regular_path(self.directory, directory=True)
                    check()
                    runtime = PhysicalOnboardingM1Runtime.initialize(
                        self.directory,
                        source_binding_sha256=physical_diagnostic_source_binding(
                            self.source_sha256
                        ),
                        cell_id=self.cell_id,
                    )
                    check()
                    runtime.create_session(
                        self.session_id,
                        mode="PHYSICAL_DIAGNOSTIC",
                        workspace_source_sha256=self.source_sha256,
                    )
                    check()
                    store = M1PhysicalDiagnosticPersistence(
                        runtime,
                        workspace_source_sha256=self.source_sha256,
                        admission_facts=self._facts,
                    )
                    with store.stage_transaction(
                        self.session_id,
                        expected_challenge_sha256=store.verification(
                            self.session_id
                        ).challenge_sha256,
                    ) as tx:
                        snapshot = tx.snapshot()
                        check()
                        tx.commit_stage_state(
                            PhysicalOnboardingStage.WORKSPACE_SOURCES,
                            V2StageState.WAITING_OPERATOR,
                            occurred_at_ns=max(
                                time.time_ns(), snapshot.header.created_at_ns + 1
                            ),
                            detail_code="SOURCE_PREFLIGHT_PENDING",
                            expected_head_sha256=snapshot.head.head_sha256,
                        )
                    check()
                    leases = (
                        LeaseSpec(LeaseLevel.CELL, self.cell_id),
                        LeaseSpec(LeaseLevel.SESSION, self.session_id),
                    )
                    request = RegisteredActionRequest(
                        self.cell_id,
                        self.session_id,
                        registration.action_id,
                        "source-preflight-once",
                        "a" * 64,
                    )
                    with store.transaction(leases) as tx:
                        request = replace(
                            request,
                            expected_challenge_sha256=tx.read_admission(
                                request
                            ).challenge_sha256,
                        )
                    core = PhysicalDiagnosticPreflightCoordinator(
                        persistence=cast(CommissioningPersistence, store),
                        registrations=(registration,),
                        workers={registration.worker_id: worker},
                        retained_campaign_actions=(registration.action_id,),
                    )
                    progress(
                        "Consuming one file-only permit and retaining actual source/build observations."
                    )
                    check()
                    permit = core.prepare(request)
                    outcome = core.execute(permit, cancellation=cancellation)
                    with self._lock:
                        self._cached["attempt"] = json.loads(
                            json.dumps(asdict(outcome))
                        )
                    if (
                        outcome.state is not AttemptState.SEALED_KNOWN
                        or worker.report is None
                    ):
                        raise WizardError(
                            "PREFLIGHT_ATTEMPT_HELD",
                            "Source attempt did not seal known. Export the outcome and preserve the original store; no retry or device effect is authorized.",
                        )
                    progress(
                        "Reading back full retained evidence under storage leases. Canonical physical stages remain pending."
                    )
                    with store.transaction(leases) as tx:
                        retained = tx.read_campaign_evidence(permit.attempt_id)
                        snapshot = tx.snapshot()
                    if (
                        len(retained) != 1
                        or retained[0].payload_sha256 != worker.report.sha256
                    ):
                        raise WizardError(
                            "PREFLIGHT_RETENTION",
                            "Read-back evidence differs from the source worker report.",
                        )
                    report = verify_physical_source_preflight(
                        retained[0].payload,
                        expected_source_sha256=self.source_sha256,
                        expected_permit_sha256=permit.permit_sha256,
                        expected_worker_sha256=registration.worker_executable_sha256,
                        expected_report_sha256=retained[0].payload_sha256,
                    )
                    summary = report.safe_summary()
                    # Retain the historical observation before any late
                    # cancellation, source drift or publication failure. This
                    # is evidence availability, not current readiness.
                    with self._lock:
                        self._retained_report = {
                            "retained_source_report": json.loads(report.payload),
                            "retained_report_sha256": report.sha256,
                            "retention": "M1_FULL_BYTES_READ_BACK",
                            "canonical_stage_pass": False,
                            "physical_authority": False,
                        }
                        self._cached["report"] = summary
                    self._current_source()
                    check()
                    with self._lock:
                        self._cached.update(
                            {
                                "status": summary["outcome"],
                                "report": summary,
                                "canonical_stage_state": snapshot.state_for(
                                    PhysicalOnboardingStage.WORKSPACE_SOURCES
                                ).value,
                                "next_step": "Review the file checks and export logs. Received hardware, power isolation, native providers and installed calibration are still unverified.",
                            }
                        )
            return {
                "schema": "rocell.wizard_worker_result.v1",
                "action_id": SOURCE_PREFLIGHT_ACTION_ID,
                "status": (
                    "SUCCEEDED"
                    if summary["outcome"] == "FILE_CHECKS_COHERENT"
                    else "FAILED"
                ),
                "steps": [
                    {
                        "name": "actual_source_preflight",
                        "exit_code": (
                            0 if summary["outcome"] == "FILE_CHECKS_COHERENT" else 1
                        ),
                        "report": {
                            "view": self.view(),
                            "retained_source_report": json.loads(report.payload),
                            "retained_report_sha256": report.sha256,
                            "retention": "M1_FULL_BYTES_READ_BACK",
                            "canonical_stage_pass": False,
                            "physical_authority": False,
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
        except BaseException as error:
            with self._lock:
                self._cached.update(
                    {
                        "status": "HELD",
                        "error": {
                            "code": getattr(error, "code", "SOURCE_PREFLIGHT_FAILED"),
                            "type": type(error).__name__,
                        },
                        "next_step": "Export diagnostics and preserve the original store. Investigate the reported cause before starting a new explicit session.",
                    }
                )
            raise
