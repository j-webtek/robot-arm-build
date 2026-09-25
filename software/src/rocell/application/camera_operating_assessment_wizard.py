"""Bounded diagnostic assessment action; no stage write or approval state."""

from copy import deepcopy
import json
from time import monotonic_ns

from .camera_operating_assessment_service import run_original_operating_assessment
from .wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical, digest

ACTION = "physical_camera_operating_assessment"
MAX_ATTEMPTS = 8


class CameraOperatingAssessmentWizard:
    def __init__(self, host):
        self._host = host
        self._attempts = {}

    def fields(self):
        with self._host._lock:
            choices = self._host._configuration_wizard.export_fields()[0]["options"]
            return tuple(
                dict(
                    name=f"capture_{i}",
                    label=f"Saved settings capture {i} (optional; none means incomplete)",
                    type="select",
                    required=True,
                    options=[
                        dict(value="none", label="None — incomplete evidence"),
                        *deepcopy(choices),
                    ],
                    default="none",
                )
                for i in (1, 2)
            )

    def preview_context(self, values=None):
        with self._host._lock:
            if len(self._attempts) >= MAX_ATTEMPTS:
                raise WizardError(
                    "OPERATING_ASSESSMENT_LIMIT",
                    "Export the bounded assessment history; earlier attempts are not erased.",
                )
            operation, payload, context = (
                self._host._operating_proposal.current_logged_proposal()
            )
            keys = tuple(
                v
                for v in (
                    (values or {}).get("capture_1", "none"),
                    (values or {}).get("capture_2", "none"),
                )
                if v != "none"
            )
            if len(set(keys)) != len(keys):
                raise WizardError(
                    "OPERATING_DUPLICATE_CAPTURE",
                    "Choose two distinct saved captures, or leave a selection empty.",
                )
            captures = {
                k: self._host._configuration_wizard.export_context(k) for k in keys
            }
            return dict(
                proposal_operation_id=operation,
                proposal_sha256=digest(payload),
                draft_context=context,
                capture_requests=list(keys),
                capture_contexts=captures,
            )

    def run(self, operation_id, values, *, cancellation, deadline_ns, progress):
        app = self._host
        with app._lock:
            context = self.preview_context(values)
            if (
                context != values["_operating_assessment_context"]
                or operation_id in self._attempts
            ):
                raise WizardError(
                    "OPERATING_ASSESSMENT_STALE",
                    "Preview the current proposal and selected originals again.",
                )
            _, payload, _ = app._operating_proposal.current_logged_proposal()
            # Detached copies of the already ticket-pinned capture packets.
            # No browser path/hash input, log import or filesystem read here.
            capture_packets = {
                key: app._configuration_wizard.packet(key)
                for key in context["capture_requests"]
            }
            owners = (
                app._physical_camera,
                app._physical_camera_setup.session,
                app._native_camera,
            )
            row = dict(context=canonical(context), result=None, completion=None)
            self._attempts[operation_id] = row

        def current():
            with app._lock:
                app._recheck_source(ACTION)
                # Do not call the attempt-limit preview after claiming the last slot.
                current_proposal_operation, current_payload, draft = (
                    app._operating_proposal.current_logged_proposal()
                )
                if (
                    app._running != operation_id
                    or app._closed
                    or app._log_error
                    or current_proposal_operation != context["proposal_operation_id"]
                    or cancellation.is_set()
                    or monotonic_ns() >= deadline_ns
                    or not all(
                        a is b
                        for a, b in zip(
                            owners,
                            (
                                app._physical_camera,
                                app._physical_camera_setup.session,
                                app._native_camera,
                            ),
                        )
                    )
                    or digest(current_payload) != context["proposal_sha256"]
                    or draft != context["draft_context"]
                    or any(
                        app._configuration_wizard.export_context(k) != v
                        for k, v in context["capture_contexts"].items()
                    )
                ):
                    raise WizardError(
                        "OPERATING_ASSESSMENT_CHANGED",
                        "Source, settings, owners, captures, logs or Stop changed. Assessment remains diagnostic-only.",
                    )

        current()
        report = run_original_operating_assessment(
            *owners,
            context=context["draft_context"]["settings_context"],
            proposal_payload=payload,
            expected_proposal_sha256=context["proposal_sha256"],
            capture_request_keys=tuple(context["capture_requests"]),
            request_key=operation_id,
            cancellation=cancellation,
            deadline_ns=deadline_ns,
            validate_current_context=current,
            progress=progress,
            capture_packets=capture_packets,
        )
        current()
        result = dict(
            schema="rocell.wizard_worker_result.v1",
            action_id=ACTION,
            status="SUCCEEDED",
            steps=[
                dict(name="original_operating_assessment", exit_code=0, report=report)
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
            current()
            row["result"] = canonical(result)
        return result

    def record_completion(self, operation):
        with self._host._lock:
            row = self._attempts.get(operation["operation_id"])
            if row is not None:
                row["completion"] = {
                    k: deepcopy(operation.get(k))
                    for k in (
                        "status",
                        "result_sha256",
                        "completion_log_persisted",
                        "message",
                    )
                }

    def packet(self):
        with self._host._lock:
            return dict(
                schema="rocell.wizard_camera_operating_assessment_diagnostics.v1",
                source_sha256=self._host.source_sha256,
                launch_session_id=self._host.session_id,
                attempts=[
                    dict(
                        operation_id=k,
                        context_sha256=digest(v["context"]),
                        completion=deepcopy(v["completion"]),
                        result=None if v["result"] is None else json.loads(v["result"]),
                    )
                    for k, v in self._attempts.items()
                ],
                original_stage_record_retained=False,
                approved_operating_policy=False,
                physical_authority=False,
                current_connection_restored=False,
            )
