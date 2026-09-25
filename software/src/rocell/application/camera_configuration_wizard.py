"""One wizard's logged settings reference and explicit settings-capture queues.

This controller joins the existing Arrival operation/log lifecycle to the
original acquisition service. Cached references are comparisons, not permits.
The acquisition service/M1/native owner still authenticate and execute every
bounded capture. No file/device work occurs during view, preview or queueing.
"""

from collections import OrderedDict
from copy import deepcopy
import json
from typing import Any

from .camera_configuration_wizard_contract import (
    CAPTURE_ACTION_ID,
    EXPORT_ACTION_ID,
    VIEW_SCHEMA,
    SETTINGS_PUBLICATION_SCHEMA,
    MAX_CAPTURE_ATTEMPTS,
)
from .camera_configuration_attempt_export import DIAGNOSTICS_SCHEMA
from .wizard_actions import WizardError
from rocell.providers.windows.camera_worker_client import CameraCampaignBudget
from rocell.providers.windows.native_camera_protocol import canonical, digest


def _logged_digest(value: Any) -> str:
    # Arrival logs use pretty, ASCII JSON; native protocol hashes use compact
    # canonical JSON. Never substitute one serialization for the other.
    from .arrival_wizard_service import _json_payload

    return digest(_json_payload(value))


class CameraConfigurationWizard:
    """Process-local child of one Arrival service, never restored from JSON.

    All state access uses the owning Arrival RLock. Its global operation queue
    permits one running action; the per-attempt claim additionally forbids replay.
    Native calls run without holding the UI lock, with a re-entered current guard.
    """

    def __init__(self, host: Any) -> None:
        self._host = host
        self._settings: bytes | None = None
        self._settings_session: Any = None
        self._settings_enrollment: Any = None
        self._attempts: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def withdraw_settings(self) -> None:
        with self._host._lock:
            self._settings = None
            self._settings_session = self._settings_enrollment = None

    def _probe_receipt(self) -> dict[str, str]:
        app = self._host
        completed, queue = app._probe_attempt_completion, app._probe_dispatch_queue
        if (
            completed is None
            or queue is None
            or completed.get("action_id") != "physical_camera_probe"
            or completed.get("status") != "SUCCEEDED"
            or completed.get("completion_log_persisted") is not True
            or completed.get("operation_id") != queue.get("operation_id")
            or queue.get("claimed") is not True
            or not isinstance(completed.get("result"), dict)
            or completed.get("result_sha256") != _logged_digest(completed["result"])
        ):
            raise WizardError(
                "CONFIGURATION_LOGGED_PROBE_REQUIRED",
                "A successful original probe with its completion log is required.",
            )
        return {key: completed[key] for key in ("operation_id", "result_sha256")}

    def publish_settings(self, operation_id: str, result: dict[str, Any]) -> None:
        """Pin only after the original settings result was logged and published."""
        app = self._host
        with app._lock:
            operation = app._operations.get(operation_id)
            if (
                operation is None
                or operation.get("action_id") != "physical_camera_configuration"
                or operation.get("status") != "SUCCEEDED"
                or operation.get("completion_log_persisted") is not True
                or operation.get("result_sha256") != _logged_digest(result)
                or app._full_results.get(operation_id) != result
                or app._closed
                or app._log_error
                or not app._probe_metadata_current()
                or app._physical_camera.view()["publication"]
                != {"status": "CURRENT", "operation_id": operation_id}
            ):
                raise WizardError(
                    "CONFIGURATION_SETTINGS_NOT_PUBLISHED",
                    "Exact successful settings publication and completion log required.",
                )
            app._check_physical_camera_settings_identity()
            intent = app._physical_camera.configuration_capture_context()
            document = dict(
                schema=SETTINGS_PUBLICATION_SCHEMA,
                source_sha256=app.source_sha256,
                launch_session_id=app.session_id,
                operation_id=operation_id,
                result_sha256=operation["result_sha256"],
                completion_log_persisted=True,
                intent=intent,
                enrollment_sha256=digest(
                    canonical(app._native_camera.export_snapshot())
                ),
                probe=self._probe_receipt(),
                physical_authority=False,
                hardware_qualified=False,
            )
            self._settings = canonical(document)
            self._settings_session = app._physical_camera_setup.session
            self._settings_enrollment = app._native_camera

    def _current_context(self, *, idle: bool) -> dict[str, Any]:
        app = self._host
        if (
            app.mode != "physical"
            or self._settings is None
            or app._closed
            or app._source_changed
            or app._log_error
            or not app._probe_metadata_current()
            or app._physical_camera_setup.session is not self._settings_session
            or app._native_camera is not self._settings_enrollment
        ):
            raise WizardError(
                "CONFIGURATION_CURRENT_SETTINGS_REQUIRED",
                "Publish explicit camera settings after a logged original probe in this launch.",
            )
        settings = json.loads(self._settings)
        app._check_physical_camera_settings_identity()
        intent = app._physical_camera.configuration_capture_context()
        if (
            settings["source_sha256"] != app.source_sha256
            or settings["launch_session_id"] != app.session_id
            or settings["intent"] != intent
            or settings["probe"] != self._probe_receipt()
            or settings["enrollment_sha256"]
            != digest(canonical(app._native_camera.export_snapshot()))
        ):
            raise WizardError(
                "CONFIGURATION_SETTINGS_CHANGED",
                "The logged settings, original probe or current camera owner changed.",
            )
        if idle and (
            app._physical_camera.configuration_blocked_reason()
            or app._physical_camera.view()["publication"]["status"] != "CURRENT"
        ):
            raise WizardError(
                "CONFIGURATION_PUBLICATION_PENDING",
                "Finish or inspect the pending camera publication first.",
            )
        original = app._original_probe_context()
        budget = CameraCampaignBudget(**intent["capture_budget"])
        plan = app._physical_camera.preview_activation_plan(
            "capture",
            app._native_camera,
            capture_budget=budget,
            configuration_verification=True,
            sealed_configuration_capture=True,
        )
        return dict(
            original_setup=original,
            intent=intent,
            settings_publication_sha256=digest(self._settings),
            expected_capture_plan_sha256=digest(canonical(plan)),
        )

    def preview_context(self) -> dict[str, Any]:
        with self._host._lock:
            if len(self._attempts) >= MAX_CAPTURE_ATTEMPTS:
                raise WizardError(
                    "CONFIGURATION_ATTEMPT_LIMIT",
                    "This launch reached its bounded capture history. Export and inspect originals; do not erase or replay them.",
                )
            return self._current_context(idle=True)

    def queue(
        self, operation_id: str, context: dict[str, Any], values: dict[str, Any]
    ) -> None:
        app = self._host
        with app._lock:
            if operation_id in self._attempts or self.preview_context() != context:
                raise WizardError(
                    "CONFIGURATION_QUEUE_CHANGED",
                    "Preview the current settings capture again.",
                )
            self._attempts[operation_id] = dict(
                queue=dict(
                    operation_id=operation_id,
                    context_sha256=digest(canonical(context)),
                    claimed=False,
                ),
                context=canonical(context),
                phase="QUEUED_NOT_ADMITTED",
                admission=dict(
                    status="QUEUED_NOT_ADMITTED",
                    request_key=operation_id,
                    settings_intent=deepcopy(context["intent"]),
                    logged_settings_reference=json.loads(self._settings or b"null"),
                    current_operator_request={
                        key: values[key]
                        for key in (
                            "operator_id",
                            "arm_actuator_supply_disconnected",
                            "bounded_configuration_capture_consent",
                        )
                    },
                    physical_authority=False,
                    hardware_qualified=False,
                    automatic_retry_allowed=False,
                ),
                dispatch=None,
                completion=None,
            )
            # Retire presentation before intent logging, without invalidating
            # the immutable probe/settings needed by the new original admission.
            app._physical_camera.withdraw_capture_preview(context["intent"])

    def run(
        self,
        operation_id: str,
        values: dict[str, Any],
        *,
        cancellation: Any,
        deadline_ns: int,
        progress: Any,
    ) -> dict[str, Any]:
        app = self._host
        with app._lock:
            attempt = self._attempts.get(operation_id)
            if attempt is None or attempt["queue"]["claimed"]:
                raise WizardError(
                    "CONFIGURATION_QUEUE_REQUIRED",
                    "The exact unclaimed capture queue is required.",
                )
            context = json.loads(attempt["context"])
            if context != values["_configuration_capture_context"]:
                raise WizardError(
                    "CONFIGURATION_QUEUE_CHANGED",
                    "The queued context differs from its ticket.",
                )
            attempt["queue"]["claimed"] = True
            attempt["phase"] = "RUNNING_ORIGINAL_CAPTURE"
            original_session = app._physical_camera_setup.session
            original_enrollment = app._native_camera

        def current() -> None:
            with app._lock:
                app._recheck_source(CAPTURE_ACTION_ID)
                if (
                    app._running != operation_id
                    or app._closed
                    or app._log_error
                    or cancellation.is_set()
                    or self._attempts.get(operation_id) is not attempt
                    or attempt["queue"]["claimed"] is not True
                    or app._physical_camera_setup.session is not original_session
                    or app._native_camera is not original_enrollment
                    or self._current_context(idle=False) != context
                    or digest(canonical(context)) != attempt["queue"]["context_sha256"]
                ):
                    raise WizardError(
                        "CONFIGURATION_CURRENT_OWNER_CHANGED",
                        "Settings capture ownership, source, identity, logs or Stop changed. Preserve diagnostics without replay.",
                    )

        try:
            current()
            original = context["original_setup"]
            result = app._physical_camera.run_original_configuration_capture(
                original_session,
                original_enrollment,
                request_key=operation_id,
                **{
                    key: original[key]
                    for key in (
                        "expected_header_sha256",
                        "expected_preparation_sha256",
                        "expected_review_sha256",
                    )
                },
                expected_plan_sha256=context["expected_capture_plan_sha256"],
                capture_budget=CameraCampaignBudget(
                    **context["intent"]["capture_budget"]
                ),
                operator_id=values["operator_id"],
                arm_actuator_supply_disconnected=values[
                    "arm_actuator_supply_disconnected"
                ],
                bounded_configuration_capture_consent=values[
                    "bounded_configuration_capture_consent"
                ],
                cancellation=cancellation,
                deadline_ns=deadline_ns,
                progress=progress,
                validate_current_context=current,
                sealed_configuration_capture=True,
            )
            current()
            with app._lock:
                attempt["phase"] = "RESULT_STAGED_NOT_PUBLISHED"
            return result
        finally:
            with app._lock:
                retained = app._physical_camera.retained_configuration_diagnostics()
                admission = retained["admission"]
                # A preflight failure must not attach an earlier capture's data.
                if (
                    admission is not None
                    and admission.get("request_key") == operation_id
                ):
                    # Preserve the queued logged-settings/operator reference
                    # alongside later original admission, including failures.
                    attempt["admission"].update(admission)
                    attempt["dispatch"] = retained["dispatch"]
                    if admission["status"] == "FAILED_HELD":
                        attempt["phase"] = "FAILED_HELD"

    def record_completion(self, operation: dict[str, Any]) -> None:
        with self._host._lock:
            attempt = self._attempts.get(operation["operation_id"])
            if attempt is not None:
                attempt["completion"] = deepcopy(operation)
                if operation["status"] != "SUCCEEDED":
                    attempt["phase"] = "FAILED_HELD"

    def record_publication(self, operation_id: str) -> None:
        with self._host._lock:
            self._attempts[operation_id]["phase"] = "CAPTURE_PUBLISHED_UNQUALIFIED"

    def export_fields(self) -> tuple[dict[str, Any], ...]:
        with self._host._lock:
            options = [
                dict(value=key, label=f"Capture {index}: {row['phase']}")
                for index, (key, row) in enumerate(self._attempts.items(), 1)
            ]
            return (
                dict(
                    name="attempt_choice_id",
                    label="Retained settings-capture attempt",
                    type="select",
                    required=True,
                    options=options,
                    default=options[-1]["value"] if options else "",
                ),
            )

    def packet(self, choice: str) -> dict[str, Any]:
        with self._host._lock:
            if type(choice) is not str or choice not in self._attempts:
                raise WizardError(
                    "CONFIGURATION_EXPORT_EMPTY",
                    "Choose a retained settings-capture attempt.",
                )
            row = self._attempts[choice]
            return dict(
                schema=DIAGNOSTICS_SCHEMA,
                source_sha256=self._host.source_sha256,
                launch_session_id=self._host.session_id,
                **{
                    key: deepcopy(row[key])
                    for key in ("queue", "admission", "dispatch", "completion")
                },
                physical_authority=False,
                hardware_qualified=False,
                meaning="Cached original settings-capture attempt, including unknown or failed outcomes. Diagnostic copies cannot restore a connection, permit or replay.",
            )

    def export_context(self, choice: str) -> str:
        return digest(canonical(self.packet(choice)))

    def view(self) -> dict[str, Any]:
        """Small cached card only: no original-store/provider or filesystem read."""
        with self._host._lock:
            rows = [
                dict(
                    operation_id=key,
                    claimed=row["queue"]["claimed"],
                    phase=row["phase"],
                    outcome=(row["completion"] or {}).get("status"),
                )
                for key, row in self._attempts.items()
            ]
            return dict(
                schema=VIEW_SCHEMA,
                source_sha256=self._host.source_sha256,
                launch_session_id=self._host.session_id,
                settings_reference_retained=self._settings is not None,
                attempts=rows,
                maximum_attempts=MAX_CAPTURE_ATTEMPTS,
                capture_action=CAPTURE_ACTION_ID,
                export_action=EXPORT_ACTION_ID,
                export_available=bool(rows),
                physical_authority=False,
                hardware_qualified=False,
                connected=False,
                meaning="Logged settings and retained captures, not calibration or physical-stage acceptance. Actions revalidate current owners and originals; polling does not connect hardware.",
            )
