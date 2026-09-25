"""Explicit logged proposal drafts; no original-store writes or device effects.

Arrival owns tickets, the running operation, source checks and durable logs.
This child owns only a bounded in-memory history. Cached original subjects are
comparison inputs, not fresh storage authentication or an approved policy.
"""

from copy import deepcopy
from dataclasses import asdict
import json
from time import monotonic_ns, time_ns
from typing import Any
from uuid import uuid4

from .camera_operating_proposal import (
    CameraOperatingProposal,
    REFERENCE_MODE,
    VARIANCE_MODE,
    build_camera_operating_proposal,
    _text,
)
from .physical_camera_configuration import StagedPhysicalCameraConfiguration
from .physical_camera_mode_entry import CameraModeEntry, camera_mode_operator_valid
from .wizard_actions import WizardError
from .wizard_diagnostic_coordinator import require_regular_path
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.vision.camera_profile import MAX_CAMERA_PROFILE_BYTES

ACTION = "physical_camera_operating_proposal"
SCHEMA = "rocell.wizard_camera_operating_proposal.v1"
MAX_ATTEMPTS = 8
TIMEOUT_NS = 30_000_000_000
MEANING = (
    "Logged proposal draft from cached subjects, not original-stage storage or "
    "operating-policy approval. No settings are applied and no device is opened. "
    "Export before closing; a fresh launch restores no current proposal."
)


def _need(ok: bool, code: str, message: str) -> None:
    if not ok:
        raise WizardError(code, message)


class CameraOperatingProposalWizard:
    def __init__(self, host: Any) -> None:
        self._host = host
        self._attempts: dict[str, dict[str, Any]] = {}
        self._current: str | None = None

    def _inputs(self) -> tuple[dict[str, Any], bytes, bytes]:
        """Only cached owner data. Caller holds Arrival's RLock; no file reads."""
        app = self._host
        controller = app._configuration_wizard
        settings_context = controller._current_context(idle=True)
        setup = app._physical_camera_setup
        workflow = setup.operating_proposal_entry()
        _need(
            type(workflow) is dict and type(workflow.get("camera_mode_entry")) is dict,
            "MODE_PROPOSAL_ENTRY_REQUIRED",
            "A published original camera mode-entry reference is required.",
        )
        row = workflow["camera_mode_entry"]
        _need(
            row.get("state") == "ENTERED"
            and workflow["publication"]["status"] == "CURRENT",
            "MODE_PROPOSAL_ENTRY_REQUIRED",
            "The camera entry is incomplete or not currently published.",
        )
        try:
            record = row["entry"]
            entry = CameraModeEntry(canonical(record["document"]))
            binding = entry.to_dict()["binding"]
            _need(
                entry.sha256 == record["evidence_sha256"]
                and binding["header_sha256"] == workflow["session_header_sha256"]
                and binding["source_sha256"] == app.source_sha256,
                "MODE_PROPOSAL_ENTRY_CHANGED",
                "The cached entry differs from its recorded source/header/hash.",
            )
            # Get exact settings bytes through the owning camera service, not a
            # browser projection or a deserialized replacement workflow.
            payload = app._physical_camera.operating_proposal_configuration()
            config = StagedPhysicalCameraConfiguration(payload)
            _need(
                config.settings_epoch == settings_context["intent"]["settings_epoch"]
                and config.to_dict()["binding"]["session_id"] == binding["session_id"],
                "MODE_PROPOSAL_SETTINGS_CHANGED",
                "Logged settings and entry/session context differ.",
            )
            _need(
                config.mode.same_format(REFERENCE_MODE)
                or config.mode.same_format(VARIANCE_MODE),
                "MODE_PROPOSAL_UNSUPPORTED_MODE",
                "This proposal schema covers only full-resolution YUY2 at 8 or 9 fps; no fallback is selected.",
            )
            context = dict(
                source_sha256=app.source_sha256,
                launch_session_id=app.session_id,
                settings_context=settings_context,
                entry_sha256=entry.sha256,
                settings_epoch=config.settings_epoch,
                mode=asdict(config.mode),
            )
            return context, entry.payload, payload
        except WizardError:
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise WizardError(
                "MODE_PROPOSAL_SUBJECT_INVALID",
                "Exact cached entry and settings subjects are required.",
            ) from exc

    def preview_context(self) -> dict[str, Any]:
        with self._host._lock:
            _need(
                len(self._attempts) < MAX_ATTEMPTS,
                "MODE_PROPOSAL_ATTEMPT_LIMIT",
                "The bounded proposal history is full. Export it; do not erase or replay earlier attempts.",
            )
            return self._inputs()[0]

    def validate_values(self, values: dict[str, Any]) -> None:
        with self._host._lock:
            context = self.preview_context()
            try:
                _need(
                    camera_mode_operator_valid(values["operator_id"]),
                    "MODE_PROPOSAL_OPERATOR",
                    "Use a trimmed operator label of at most 64 UTF-8 bytes.",
                )
                _text(values["rationale"])
                variance = values["variance_rationale"]
                # Exact integer comparison, without a float or silent rounding.
                mode = context["mode"]
                if mode["fps_numerator"] == 8 * mode["fps_denominator"]:
                    _text(variance)
                else:
                    _need(
                        variance == "",
                        "MODE_PROPOSAL_UNEXPECTED_VARIANCE",
                        "Leave the variance rationale empty for the 9-fps reference proposal.",
                    )
            except (ValueError, KeyError, TypeError) as exc:
                if isinstance(exc, WizardError):
                    raise
                raise WizardError(
                    "MODE_PROPOSAL_RATIONALE",
                    "Supply a trimmed, bounded rationale; an 8-fps proposal also needs an explicit variance rationale.",
                ) from exc

    def run(self, operation_id, values, *, cancellation, deadline_ns, progress):
        app = self._host
        with app._lock:
            self.validate_values(values)
            context, entry_payload, config_payload = self._inputs()
            _need(
                context == values["_operating_proposal_context"]
                and operation_id not in self._attempts,
                "MODE_PROPOSAL_CONTEXT_CHANGED",
                "Preview the current entry and logged settings again; nothing is replayed.",
            )
            owners = (
                app._physical_camera_setup.session,
                app._native_camera,
                app._physical_camera,
            )
            row = dict(
                context=canonical(context),
                owners=owners,
                result=None,
                completion=None,
                state="RUNNING_DRAFT",
                deadline_ns=deadline_ns,
            )
            self._attempts[operation_id] = row
            self._current = None

        def check():
            with app._lock:
                app._recheck_source(ACTION)
                _need(
                    type(deadline_ns) is int and monotonic_ns() < deadline_ns,
                    "MODE_PROPOSAL_DEADLINE",
                    "The bounded draft deadline expired; no current proposal is published.",
                )
                _need(
                    not cancellation.is_set()
                    and not app._closed
                    and not app._log_error
                    and app._running == operation_id
                    and self._attempts.get(operation_id) is row,
                    "MODE_PROPOSAL_INTERRUPTED",
                    "Draft operation, logs or Stop changed; no current proposal is published.",
                )
                _need(
                    all(
                        a is b
                        for a, b in zip(
                            owners,
                            (
                                app._physical_camera_setup.session,
                                app._native_camera,
                                app._physical_camera,
                            ),
                        )
                    )
                    and canonical(self._inputs()[0]) == row["context"],
                    "MODE_PROPOSAL_CONTEXT_CHANGED",
                    "Source, owner, entry or settings changed; retain diagnostics without approval.",
                )

        try:
            _need(
                type(deadline_ns) is int
                and monotonic_ns() < deadline_ns <= monotonic_ns() + TIMEOUT_NS,
                "MODE_PROPOSAL_DEADLINE",
                "Use the original bounded draft deadline.",
            )
            check()
            progress(
                "Reading the fixed purchase profile for a proposal draft; no device or original store is opened."
            )
            profile = require_regular_path(
                app.workspace
                / "software/config/camera_profiles/arducam_b0477_imx283_16mm.json",
                directory=False,
            )
            with profile.open("rb") as stream:
                profile_bytes = stream.read(MAX_CAMERA_PROFILE_BYTES + 1)
            check()
            entry = CameraModeEntry(entry_payload).to_dict()
            proposal = build_camera_operating_proposal(
                proposal_id="modepolicy-" + uuid4().hex,
                operator_id=values["operator_id"],
                recorded_at_utc_ns=time_ns(),
                rationale=values["rationale"],
                variance_rationale=values["variance_rationale"] or None,
                entry_payload=entry_payload,
                expected_entry_id=entry["entry_id"],
                expected_entry_binding=entry["binding"],
                purchase_profile_payload=profile_bytes,
                expected_purchase_profile_sha256=digest(profile_bytes),
                configuration_payload=config_payload,
                expected_settings_epoch=context["settings_epoch"],
            )
            check()
            result = dict(
                schema="rocell.wizard_worker_result.v1",
                action_id=ACTION,
                status="SUCCEEDED",
                steps=[
                    dict(
                        name="operating_proposal_draft",
                        exit_code=0,
                        report=dict(
                            proposal=proposal.to_dict(),
                            proposal_sha256=proposal.sha256,
                            cached_context_sha256=digest(row["context"]),
                            original_stage_record_retained=False,
                            assessment_performed=False,
                            meaning=MEANING,
                        ),
                    )
                ],
                device_open_count=0,
                serial_write_count=0,
                power_event_count=0,
                motion_command_count=0,
                contact_command_count=0,
                metadata_inventory_performed=False,
                physical_authority=False,
            )
            with app._lock:
                check()
                row.update(
                    result=canonical(result), state="DRAFT_AWAITING_COMPLETION_LOG"
                )
            return result
        except BaseException:
            with app._lock:
                row["state"] = "HISTORICAL_HELD"
            raise

    def publish(self, operation_id, result, cancellation) -> None:
        """Arrival calls only after _finish has persisted the completion log."""
        app = self._host
        with app._lock:
            row = self._attempts.get(operation_id)
            try:
                operation = app._operations.get(operation_id, {})
                from .camera_configuration_wizard import _logged_digest

                _need(
                    row is not None
                    and row["state"] == "DRAFT_AWAITING_COMPLETION_LOG"
                    and row["result"] == canonical(result)
                    and not cancellation.is_set()
                    and not app._closed
                    and not app._log_error
                    and not app._source_changed
                    and operation.get("status") == "SUCCEEDED"
                    and operation.get("completion_log_persisted") is True
                    and operation.get("result_sha256") == _logged_digest(result)
                    and app._full_results.get(operation_id) == result,
                    "MODE_PROPOSAL_NOT_PUBLISHED",
                    "Exact draft result and successful completion log are required; no approval is inferred.",
                )
                app._recheck_source(ACTION)
                assert row is not None  # The publication guard above rejects absence.
                _need(
                    canonical(self._inputs()[0]) == row["context"]
                    and all(
                        a is b
                        for a, b in zip(
                            row["owners"],
                            (
                                app._physical_camera_setup.session,
                                app._native_camera,
                                app._physical_camera,
                            ),
                        )
                    ),
                    "MODE_PROPOSAL_CONTEXT_CHANGED",
                    "The draft context changed before publication.",
                )
                _need(
                    not cancellation.is_set() and monotonic_ns() < row["deadline_ns"],
                    "MODE_PROPOSAL_INTERRUPTED",
                    "Stop or deadline changed before final draft publication.",
                )
                row["state"] = "LOGGED_DRAFT_NOT_APPROVED"
                self._current = operation_id
            except BaseException:
                if row is not None:
                    row["state"] = "HISTORICAL_HELD"
                self._current = None
                raise

    def view(self) -> dict[str, Any]:
        """Small detached cache projection; no original-store, source or file I/O."""
        app = self._host
        with app._lock:
            current = self._current
            row = self._attempts.get(current) if current else None
            if row is not None:
                try:
                    _need(
                        not app._closed
                        and not app._source_changed
                        and not app._log_error
                        and canonical(self._inputs()[0]) == row["context"]
                        and all(
                            a is b
                            for a, b in zip(
                                row["owners"],
                                (
                                    app._physical_camera_setup.session,
                                    app._native_camera,
                                    app._physical_camera,
                                ),
                            )
                        ),
                        "MODE_PROPOSAL_CONTEXT_CHANGED",
                        "Historical draft only.",
                    )
                except (WizardError, ValueError, TypeError, KeyError):
                    current = None
            proposal = None
            if current is not None and row is not None:
                report = json.loads(row["result"])["steps"][0]["report"]
                document = CameraOperatingProposal(
                    canonical(report["proposal"])
                ).to_dict()
                proposal = dict(
                    proposal_sha256=report["proposal_sha256"],
                    policy_kind=document["policy_kind"],
                    target_mode=document["target_mode"],
                    settings_epoch=document["subjects"]["settings_epoch"],
                )
            pending = self._attempts.get(app._running, {}).get("state") in {
                "RUNNING_DRAFT",
                "DRAFT_AWAITING_COMPLETION_LOG",
            }
            return dict(
                schema=SCHEMA,
                source_sha256=app.source_sha256,
                launch_session_id=app.session_id,
                current_operation_id=current,
                proposal=proposal,
                attempted=len(self._attempts),
                maximum_attempts=MAX_ATTEMPTS,
                action_id=ACTION,
                state=(
                    "LOGGED_DRAFT_NOT_APPROVED"
                    if current
                    else (
                        "PENDING_PUBLICATION"
                        if pending
                        else "HISTORICAL_HELD" if self._attempts else "NOT_STARTED"
                    )
                ),
                physical_authority=False,
                hardware_qualified=False,
                approved_operating_policy=False,
                original_stage_record_retained=False,
                connected=False,
                meaning=MEANING,
            )

    def current_logged_proposal(self) -> tuple[str, bytes, dict[str, Any]]:
        """Exact current draft bytes for an explicit read-only original assessment."""
        with self._host._lock:
            view = self.view()
            operation_id = view["current_operation_id"]
            _need(
                operation_id is not None,
                "MODE_PROPOSAL_CURRENT_REQUIRED",
                "Record a current logged proposal draft first.",
            )
            row = self._attempts[operation_id]
            proposal = json.loads(row["result"])["steps"][0]["report"]["proposal"]
            return operation_id, canonical(proposal), json.loads(row["context"])

    def logged_record_binding(self, operation_id: str) -> dict[str, Any]:
        """Compare a pinned owned log through a deliberate stage transition.

        Unlike current_logged_proposal this does not recheck stage-5 admission:
        a file-only submission changes that stage itself. This is a historical
        log comparison, never eligibility, an original reader or a permission.
        The submission owner separately guards current settings, source and the
        complete original history. There is no deserialization/restore path.
        """
        from .camera_configuration_wizard import _logged_digest

        with self._host._lock:
            row = self._attempts.get(operation_id)
            _need(
                row is not None
                and self._current == operation_id
                and row["state"] == "LOGGED_DRAFT_NOT_APPROVED"
                and row["result"] is not None
                and type(row["completion"]) is dict,
                "MODE_PROPOSAL_LOGGED_RECORD_REQUIRED",
                "The exact previously logged proposal must remain owned by this launch.",
            )
            assert row is not None
            result = json.loads(row["result"])
            completion = row["completion"]
            _need(
                completion.get("status") == "SUCCEEDED"
                and completion.get("completion_log_persisted") is True
                and completion.get("result_sha256") == _logged_digest(result),
                "MODE_PROPOSAL_LOGGED_RECORD_CHANGED",
                "The pinned proposal's saved result or completion log changed.",
            )
            return dict(
                operation_id=operation_id,
                context_sha256=digest(row["context"]),
                result_sha256=completion["result_sha256"],
                proposal_sha256=result["steps"][0]["report"]["proposal_sha256"],
                authority_restored=False,
            )

    def withhold(self, operation_id: str) -> None:
        with self._host._lock:
            row = self._attempts.get(operation_id)
            if row is not None:
                row["state"] = "HISTORICAL_HELD"
            if self._current == operation_id:
                self._current = None

    def record_completion(self, operation: dict[str, Any]) -> None:
        """Retain log outcome even after Arrival rotates its operation summaries."""
        with self._host._lock:
            row = self._attempts.get(operation["operation_id"])
            if row is not None:
                row["completion"] = deepcopy(
                    {
                        key: operation[key]
                        for key in (
                            "status",
                            "result_sha256",
                            "completion_log_persisted",
                            "message",
                        )
                        if key in operation
                    }
                )
                if operation["status"] != "SUCCEEDED":
                    self.withhold(operation["operation_id"])

    def packet(self) -> dict[str, Any]:
        """Bounded diagnostic history survives normal full-result cache eviction.

        No owner objects, native pipe buffers, pixels or restore credentials are
        serialized. The ordinary exporter sanitizes before writing these copies.
        """
        with self._host._lock:
            return dict(
                schema="rocell.wizard_camera_operating_proposal_diagnostics.v1",
                source_sha256=self._host.source_sha256,
                launch_session_id=self._host.session_id,
                attempts=[
                    dict(
                        operation_id=key,
                        state=row["state"],
                        context_sha256=digest(row["context"]),
                        completion=deepcopy(row["completion"]),
                        result=(
                            None if row["result"] is None else json.loads(row["result"])
                        ),
                    )
                    for key, row in self._attempts.items()
                ],
                physical_authority=False,
                original_stage_record_retained=False,
                meaning=MEANING,
            )
