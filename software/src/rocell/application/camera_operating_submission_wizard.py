"""One-use file-only submission child; Arrival owns tickets, logs and publication.

No action is registered by this module. It must be wired through the existing
application lifecycle, never called as a second endpoint or an import API.
"""

from copy import deepcopy
import json
from time import monotonic_ns
from typing import Any

from .camera_configuration_wizard import _logged_digest
from .camera_operating_submission_service import (
    run_original_operating_submission,
    submission_boundary,
)
from .camera_operating_submission import SOURCE_WORKFLOW_OPERATING_SCHEMA
from .physical_camera_mode_entry import camera_mode_operator_valid
from .wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical, digest

ACTION = "physical_camera_operating_submit"
MAX_ATTEMPTS = 3


def _need(ok, code, message):
    if not ok:
        raise WizardError("OPERATING_SUBMIT_" + code, message)


class CameraOperatingSubmissionWizard:
    def __init__(self, host):
        self._host = host
        self._attempts = {}

    def fields(self):
        with self._host._lock:
            choices = self._host._configuration_wizard.export_fields()[0]["options"]
            # Neither capture is implicitly selected, including when there are
            # exactly two choices. The operator must name both originals.
            return (
                dict(
                    name="operator_id",
                    label="Submission operator label",
                    type="text",
                    required=True,
                    max_length=64,
                ),
                *(
                    dict(
                        name=f"capture_{i}",
                        label=f"Original sealed settings capture {i}",
                        type="select",
                        required=True,
                        options=deepcopy(choices),
                        default="",
                    )
                    for i in (1, 2)
                ),
                dict(
                    name="save_for_review",
                    label="Save these originals for separate review; this does not approve the camera",
                    type="checkbox",
                    required=True,
                    default=False,
                ),
            )

    def preview_context(self, values=None):
        app = self._host
        with app._lock:
            _need(
                len(self._attempts) < MAX_ATTEMPTS,
                "LIMIT",
                "Export and inspect the bounded submission history; no earlier record is erased.",
            )
            operation, payload, draft = (
                app._operating_proposal.current_logged_proposal()
            )
            setup = app._physical_camera_setup
            with setup._lock:
                boundary_available = submission_boundary(setup._source_workflow)
            _need(
                boundary_available,
                "STAGE_REQUIRED",
                "Only the original reviewed-probe stage can receive one operating submission. Partial or submitted records are read-only.",
            )
            choices = app._configuration_wizard.export_fields()[0]["options"]
            _need(
                len(choices) >= 2,
                "TWO_CAPTURES_REQUIRED",
                "Retain two separate sealed settings captures first; missing or legacy inputs are diagnostic-only.",
            )
            if values is None:
                # Availability polling stays small: no full-history copy/hash,
                # original read, path access or implicit capture selection.
                return dict(available=True, proposal_operation_id=operation)
            workflow = setup.original_source_workflow()
            keys = (values.get("capture_1"), values.get("capture_2"))
            if values is not None:
                _need(
                    camera_mode_operator_valid(values.get("operator_id"))
                    and values.get("save_for_review") is True,
                    "CONSENT",
                    "Enter a bounded operator label and confirm saving for separate review.",
                )
                _need(
                    all(
                        type(k) is str and k in {c["value"] for c in choices}
                        for k in keys
                    )
                    and len(set(keys)) == 2,
                    "EXPLICIT_CAPTURES",
                    "Select two distinct saved capture attempts; no latest or replacement capture is selected automatically.",
                )
            return dict(
                proposal_operation_id=operation,
                proposal_sha256=digest(payload),
                draft_context=draft,
                proposal_log=app._operating_proposal.logged_record_binding(operation),
                original_workflow_sha256=digest(canonical(workflow)),
                capture_requests=list(keys),
                capture_contexts={
                    key: app._configuration_wizard.export_context(key) for key in keys
                },
            )

    def run(self, operation_id, values, *, cancellation, deadline_ns, progress):
        app = self._host
        with app._lock:
            context = self.preview_context(values)
            _need(
                context == values["_operating_submission_context"]
                and operation_id not in self._attempts,
                "STALE",
                "Preview the current proposal and exact selected originals again.",
            )
            _, payload, _ = app._operating_proposal.current_logged_proposal()
            setup = app._physical_camera_setup
            owners = (app._physical_camera, setup.session, app._native_camera)
            workflow_payload = canonical(setup.original_source_workflow())
            # These stable owned values survive our deliberate stage transition.
            # Do not restore old original-probe eligibility after REVIEW_PENDING.
            frozen = dict(
                settings=app._configuration_wizard._settings,
                intent=canonical(app._physical_camera.configuration_capture_context()),
                enrollment=canonical(app._native_camera.export_snapshot()),
                probe=canonical(app._configuration_wizard._probe_receipt()),
                configuration=app._physical_camera.operating_proposal_configuration(),
            )
            row = dict(
                context=canonical(context),
                attempt={},
                workflow=None,
                result=None,
                completion=None,
                state="RUNNING",
                deadline_ns=deadline_ns,
            )
            self._attempts[operation_id] = row

        def current(*, finishing=False):
            with app._lock:
                app._recheck_source(ACTION)
                _need(
                    # Arrival clears its running slot when it durably finishes
                    # the operation. Only publish(), after checking that exact
                    # log/result, may use the finishing form of this guard.
                    (
                        app._running is None
                        if finishing
                        else app._running == operation_id
                    )
                    and not app._closed
                    and not app._log_error
                    and not cancellation.is_set()
                    and monotonic_ns() < deadline_ns
                    and self._attempts.get(operation_id) is row
                    and app._physical_camera_setup is setup
                    and all(
                        a is b
                        for a, b in zip(
                            owners,
                            (app._physical_camera, setup.session, app._native_camera),
                        )
                    ),
                    "INTERRUPTED",
                    "Source, owner, logs, Stop or deadline changed. Any saved bytes remain historical; no automatic replay.",
                )
                _need(
                    app._operating_proposal.logged_record_binding(
                        context["proposal_operation_id"]
                    )
                    == context["proposal_log"]
                    and app._configuration_wizard._settings == frozen["settings"]
                    and canonical(app._physical_camera.configuration_capture_context())
                    == frozen["intent"]
                    and canonical(app._native_camera.export_snapshot())
                    == frozen["enrollment"]
                    and canonical(app._configuration_wizard._probe_receipt())
                    == frozen["probe"]
                    and app._physical_camera.operating_proposal_configuration()
                    == frozen["configuration"]
                    and canonical(setup.original_source_workflow()) == workflow_payload
                    and all(
                        app._configuration_wizard.export_context(k) == v
                        for k, v in context["capture_contexts"].items()
                    ),
                    "INPUTS_CHANGED",
                    "The pinned proposal, original setup, settings or captures changed during saving.",
                )

        row["current"] = current  # Process-local guard; never serialized or restored.
        try:
            current()
            workflow = run_original_operating_submission(
                *owners,
                context=context["draft_context"]["settings_context"],
                expected_workflow_payload=workflow_payload,
                proposal_payload=payload,
                expected_proposal_sha256=context["proposal_sha256"],
                capture_request_keys=tuple(context["capture_requests"]),
                request_key=operation_id,
                operator_id=values["operator_id"],
                cancellation=cancellation,
                deadline_ns=deadline_ns,
                validate_current_context=current,
                progress=progress,
                attempt=row["attempt"],
            )
            current()
            saved = workflow["camera_operating_submission"]
            record = saved["submission"]
            report = dict(
                schema="rocell.camera_operating_submission_result.v1",
                original_workflow_sha256=digest(canonical(workflow)),
                state=saved["state"],
                submission_id=record["document"]["submission_id"],
                submission_sha256=record["evidence_sha256"],
                proposal_sha256=record["document"]["proposal_sha256"],
                assessment_sha256=record["document"]["assessment_sha256"],
                reference=deepcopy(record["reference"]),
                original_stage_authenticated=saved["original_stage_authenticated"],
                review_required=True,
                stage_passed=False,
                pixel_check_semantics="HISTORICAL_READ_NOT_CURRENT_FILE_VERIFICATION",
                physical_authority=False,
                connected=False,
                approved_operating_policy=False,
            )
            result = dict(
                schema="rocell.wizard_worker_result.v1",
                action_id=ACTION,
                status="SUCCEEDED",
                steps=[
                    dict(
                        name="original_operating_submission", exit_code=0, report=report
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
                current()
                row.update(
                    workflow=canonical(workflow),
                    result=canonical(result),
                    state="AWAITING_COMPLETION_LOG",
                )
            return result
        except BaseException:
            self.withhold(operation_id)
            raise

    def publish(self, operation_id, result, cancellation):
        app = self._host
        with app._lock:
            row = self._attempts.get(operation_id)
            try:
                operation = app._operations.get(operation_id, {})
                _need(
                    row is not None
                    and row["state"] == "AWAITING_COMPLETION_LOG"
                    and canonical(result) == row["result"]
                    and operation.get("status") == "SUCCEEDED"
                    and operation.get("completion_log_persisted") is True
                    and operation.get("result_sha256") == _logged_digest(result)
                    and app._full_results.get(operation_id) == result,
                    "LOG_REQUIRED",
                    "The exact saved result and its successful durable completion log are required before publication.",
                )
                assert row is not None
                row["current"](finishing=True)
                setup = app._physical_camera_setup
                workflow = json.loads(row["workflow"])
                _need(
                    setup.session.retained_source_workflow() == workflow,
                    "ORIGINAL_CHANGED",
                    "The reopened original workflow changed before publication.",
                )
                setup._adopt_source_workflow(workflow)
                # Adopt only after the operation has durably completed. This
                # publishes historical evidence, not a connection or approval.
                with setup._lock:
                    setup._publication = dict(status="PENDING", operation_id=None)
                app._recheck_source(ACTION)
                _need(
                    not cancellation.is_set() and monotonic_ns() < row["deadline_ns"],
                    "INTERRUPTED",
                    "Stop or deadline withheld the saved submission.",
                )
                setup.publication_completed(operation_id)
                row["state"] = "RETAINED_UNREVIEWED"
            except BaseException:
                self.withhold(operation_id)
                raise

    def withhold(self, operation_id):
        with self._host._lock:
            row = self._attempts.get(operation_id)
            if row is not None:
                row["state"] = "HISTORICAL_HELD"
                # A partial write may have changed the original boundary. Keep
                # the old setup unpublishable until a separate explicit reread.
                if row["attempt"]:
                    self._host._physical_camera_setup.invalidate()

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
                if operation.get("status") != "SUCCEEDED":
                    self.withhold(operation["operation_id"])

    def view(self):
        """Small historical projection; polling never rereads files or devices."""
        app = self._host
        with app._lock, app._physical_camera_setup._lock:
            setup = app._physical_camera_setup
            workflow = setup._source_workflow or {}
            original = workflow.get("camera_operating_submission")
            original_row = original if type(original) is dict else {}
            authenticated = (
                workflow.get("schema") == SOURCE_WORKFLOW_OPERATING_SCHEMA
                and type(original) is dict
                and original.get("original_stage_authenticated") is True
            )
            latest = (
                next(reversed(self._attempts.values()), None)
                if self._attempts
                else None
            )
            record = (
                original_row.get("submission")
                if authenticated
                else (latest or {}).get("attempt", {}).get("record")
            )
            document = (record or {}).get("document", {})
            return dict(
                schema="rocell.wizard_camera_operating_submission.v1",
                source_sha256=app.source_sha256,
                launch_session_id=app.session_id,
                action_id=ACTION,
                state=(
                    original_row["state"]
                    if authenticated
                    else (latest or {}).get("state", "NOT_STARTED")
                ),
                publication=deepcopy(setup._publication),
                original_stage_authenticated=authenticated,
                submission_id=document.get("submission_id"),
                submission_sha256=(record or {}).get("evidence_sha256"),
                proposal_sha256=document.get("proposal_sha256"),
                assessment_sha256=document.get("assessment_sha256"),
                reference=deepcopy((record or {}).get("reference")),
                retention=(record or {}).get("retention"),
                capture_requests=[
                    r["request_key"]
                    for r in document.get("assessment", {}).get("captures", [])
                ],
                attempted=len(self._attempts),
                maximum_attempts=MAX_ATTEMPTS,
                review_required=True,
                stage_passed=False,
                approved_operating_policy=False,
                connected=False,
                physical_authority=False,
                hardware_qualified=False,
                pixel_check_semantics="HISTORICAL_READ_NOT_CURRENT_FILE_VERIFICATION",
                meaning="A saved submission is unreviewed historical evidence. Original authentication does not restore a connection, prove current pixels, qualify calibration or enable the arm.",
            )

    def packet(self):
        """Flatten exact documents once, outside attempt/result wrappers.

        This preserves the general export's existing depth limit and avoids
        duplicating each compound inside its result and failure bookkeeping.
        References remain explicit; these copies are never importable originals.
        """
        with self._host._lock:
            documents: dict[str, Any] = {}
            attempts = []
            for key, row in self._attempts.items():
                attempt = deepcopy(row["attempt"])
                record = attempt.get("record")
                if record is not None:
                    document = record.pop("document")
                    sha = record["evidence_sha256"]
                    _need(
                        sha not in documents or documents[sha] == document,
                        "DOCUMENT_CONFLICT",
                        "Conflicting original submission documents cannot be exported.",
                    )
                    documents[sha] = document
                    record["document_sha256"] = sha
                attempts.append(
                    dict(
                        operation_id=key,
                        context_sha256=digest(row["context"]),
                        state=row["state"],
                        attempt=attempt,
                        completion=deepcopy(row["completion"]),
                        result=(
                            None if row["result"] is None else json.loads(row["result"])
                        ),
                    )
                )
            setup = self._host._physical_camera_setup
            with setup._lock:
                workflow = (
                    setup._source_workflow
                    or setup.session.retained_source_workflow()
                    or {}
                )
                original = deepcopy(workflow.get("camera_operating_submission"))
            if original is not None:
                record = original["submission"]
                document = record.pop("document")
                sha = record["evidence_sha256"]
                _need(
                    sha not in documents or documents[sha] == document,
                    "DOCUMENT_CONFLICT",
                    "Conflicting original submission documents cannot be exported.",
                )
                documents[sha] = document
                record["document_sha256"] = sha
            return dict(
                schema="rocell.wizard_camera_operating_submission_diagnostics.v1",
                source_sha256=self._host.source_sha256,
                launch_session_id=self._host.session_id,
                attempts=attempts,
                documents=documents,
                original_readback=original,
                approved_operating_policy=False,
                physical_authority=False,
                current_connection_restored=False,
                meaning="Submission and failure diagnostics only. No callback, owner, acquisition permission or connection is serialized. Separate review and later stages remain required.",
            )
