"""Application-owned original camera metadata collection, review and export.

Existing metadata owners supply already reviewed snapshots. This service has no
provider and cannot enumerate, activate or move hardware. Arrival owns tickets,
Stop, result retention and durable completion; M1 owns original byte readback.
"""

from __future__ import annotations

from copy import deepcopy
from threading import Event, Lock, RLock
from time import monotonic_ns, time_ns
from typing import Any
from uuid import uuid4

from .physical_camera_setup_service import PhysicalCameraSetupService
from .physical_camera_identity_submission import (
    CameraIdentityMetadata,
    CameraIdentityHelper,
    CameraIdentityReceipt,
    CameraIdentityAssessment,
    CameraIdentityReview,
    MAX_COLLECTIONS,
    ROLE_BYTES,
    MEANING,
    build_camera_identity_metadata,
    build_camera_identity_helper,
    build_camera_identity_receipt,
    assess_camera_identity,
    review_camera_identity,
    canonical,
    _observation,
    _text,
)
from .physical_camera_selection import selection_from_enrollment_snapshot
from .physical_received_camera_submission import ReceivedCameraSubmission
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_v2 import V2StageState
from .wizard_actions import WizardError
from .wizard_camera_helper_registration import WizardCameraHelperRegistration
from .wizard_native_camera_enrollment import WizardNativeCameraEnrollment
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.native_camera_protocol import digest

SUBMIT = "physical_camera_identity_submit"
REVIEW = "physical_camera_identity_review"
EXPORT = "physical_camera_identity_export"
ACTIONS = frozenset((SUBMIT, REVIEW, EXPORT))
SCHEMA = "rocell.wizard_camera_identity_onboarding.v1"
_FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    native_release_allowed=False,
    device_io_performed=False,
)
_STAGE = STAGE_ORDER[3]
_CODECS = dict(
    metadata=CameraIdentityMetadata,
    helper=CameraIdentityHelper,
    receipt=CameraIdentityReceipt,
    assessment=CameraIdentityAssessment,
    review=CameraIdentityReview,
)


def _require(value, code, message):
    if not value:
        raise WizardError(code, message)


class PhysicalCameraIdentityService:
    def __init__(self, setup: PhysicalCameraSetupService):
        if type(setup) is not PhysicalCameraSetupService:
            raise TypeError("Exact application-owned setup required")
        self.setup = setup
        self.workspace, self.source_sha256, self.launch_id = (
            setup.workspace,
            setup.source_sha256,
            setup.launch_id,
        )
        self._lock, self._operation_lock = RLock(), Lock()
        self._workflow: dict[str, Any] | None = None
        self._stages: dict[str, str] | None = None
        self._cycles: list[dict[str, Any]] = []
        self._publication = dict(status="NOT_PUBLISHED", operation_id=None)
        self._pending_result: bytes | None = None
        self._pending_action: str | None = None
        self._attempt: dict[str, Any] | None = None
        self._attempted: set[str] = set()
        self._export_receipt: dict[str, Any] | None = None
        self._export_publication: dict[str, Any] | None = None

    def _context(self):
        workflow = self._workflow
        if not workflow or not workflow.get("prerequisites"):
            return None
        return dict(
            source_sha256=self.source_sha256,
            session_id=workflow["binding"]["session_id"],
            cell_id=workflow["binding"]["cell_id"],
            origin_launch_id=workflow["binding"]["launch_id"],
            header_sha256=workflow["session_header_sha256"],
            prerequisites_sha256=workflow["prerequisites"]["evidence_sha256"],
        )

    def _adopt(self, prerequisites=None):
        self._workflow = self.setup.original_source_workflow()
        stages = self.setup.session.view().get("stages")
        self._stages = (
            None
            if stages is None
            else {
                stage.value: stages[index]["state"]
                for index, stage in enumerate(STAGE_ORDER[:4])
            }
        )
        originals = (self._workflow or {}).get("camera_identity_cycles", [])
        self._cycles = []
        if originals and prerequisites is None:
            prerequisites = self.setup.current_prerequisite_artifact()
        for original in originals:
            item = {key: original[key] for key in ("identity_id", "sequence", "state")}
            for role, codec in _CODECS.items():
                record = original[role]
                if record is None:
                    item[role] = None
                else:
                    args = (canonical(record["document"]),)
                    artifact = (
                        codec(*args, prerequisites)
                        if role == "receipt"
                        else codec(*args)
                    )
                    item[role] = artifact.safe_summary()
            self._cycles.append(item)

    def observe_setup(self):
        """Adopt already verified originals only after their completion log."""
        with self._lock:
            if self.setup.view()["publication"]["status"] != "CURRENT":
                self.invalidate()
                return
            self._adopt()
            self._publication = deepcopy(self.setup.view()["publication"])
            if (self._workflow or {}).get("schema") in {
                "rocell.physical_camera_source_workflow_readback.v8",
                "rocell.physical_camera_source_workflow_readback.v9",
                "rocell.physical_camera_source_workflow_readback.v10",
                "rocell.physical_camera_source_workflow_readback.v11",
                "rocell.physical_camera_source_workflow_readback.v12",
                # Future successor: historical display only, not reader acceptance.
                "rocell.physical_camera_source_workflow_readback.v13",
            }:
                self._publication = dict(status="HISTORICAL_HELD", operation_id=None)
            self._pending_result = self._pending_action = None

    def invalidate(self):
        with self._lock:
            self._publication = dict(status="HISTORICAL_HELD", operation_id=None)
            self._pending_result = self._pending_action = None

    def view(self):
        with self._lock:
            publication = deepcopy(self._publication)
            if (
                publication["status"] == "CURRENT"
                and self.setup.view()["publication"]["status"] != "CURRENT"
            ):
                publication = dict(status="HISTORICAL_HELD", operation_id=None)
            entry = (self._workflow or {}).get("camera_identity_request")
            status = "NOT_STARTED" if entry is None else "WAITING_METADATA"
            if self._cycles:
                state = self._cycles[-1]["state"]
                status = (
                    state
                    if state in {"REVIEW_PENDING", "REVIEWED_BLOCKED"}
                    else "INCOMPLETE_HELD"
                )
            if publication["status"] != "CURRENT" and (entry or self._attempt):
                status = "HISTORICAL_HELD"
            pending = publication["status"] == "PENDING"
            return deepcopy(
                dict(
                    schema=SCHEMA,
                    source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                    original_context=self._context(),
                    publication=publication,
                    status=status,
                    stage_states=self._stages,
                    cycles=[] if pending else self._cycles,
                    identity_entry=(
                        None if pending or entry is None else entry["event_sha256"]
                    ),
                    next_action=(
                        REVIEW
                        if publication["status"] == "CURRENT"
                        and status == "REVIEW_PENDING"
                        and self.blocked_reason(REVIEW) is None
                        else None
                    ),
                    export_receipt=self._export_receipt,
                    meaning=MEANING,
                    **_FLAGS,
                )
            )

    def _original_material(self):
        return dict(
            workflow=self.setup.original_source_workflow(),
            binding=self.setup.session.descriptor(),
            verification=self.setup.session.view()["verification"],
            publication=self.setup.view()["publication"],
        )

    @staticmethod
    def _metadata_material(native_camera=None, helper=None):
        return dict(
            enrollment=(
                None if native_camera is None else native_camera.export_snapshot()
            ),
            helper=None if helper is None else helper.export_snapshot(),
        )

    def context_sha256(self, *, native_camera=None, helper=None):
        with self._lock:
            return digest(
                canonical(
                    dict(
                        source_sha256=self.source_sha256,
                        launch_id=self.launch_id,
                        original=self._original_material(),
                        metadata=self._metadata_material(native_camera, helper),
                        attempted=sorted(self._attempted),
                        attempt=self._attempt,
                    )
                )
            )

    def fields(self, action_id):
        if action_id not in ACTIONS:
            return ()

        def checkbox(name, label):
            return dict(
                name=name, type="checkbox", label=label, required=True, default=False
            )

        def text(name, label, size):
            return dict(
                name=name,
                type="text",
                label=label,
                required=True,
                default="",
                max_length=size,
            )

        def select(name, label, choices):
            return dict(
                name=name,
                type="select",
                label=label,
                required=True,
                default=choices[0],
                options=[
                    dict(value=value, label=value.replace("_", " "))
                    for value in choices
                ],
            )

        base = checkbox(
            "file_only",
            "File-only identity evidence; no camera activation or arm authority",
        )
        if action_id == SUBMIT:
            return (
                base,
                text("operator_id", "Operator label", 64),
                select(
                    "observation_state",
                    "INT-018 observation state",
                    ("UNKNOWN", "OBSERVED"),
                ),
                text(
                    "observed_value",
                    "Observed USB identity or explicit reason unknown",
                    1024,
                ),
                text("method", "How this observation or unknown was established", 512),
                text("evidence_note", "Observation evidence and limitations", 1024),
                checkbox(
                    "observation_current",
                    "I recorded this observation or reason unknown for this collection",
                ),
            )
        if action_id == REVIEW:
            return (
                base,
                text(
                    "reviewer_id",
                    "Distinct reviewer label (not authenticated identity)",
                    64,
                ),
                select(
                    "decision",
                    "Review exact retained metadata",
                    ("ACKNOWLEDGE_EXACT", "REJECT"),
                ),
            )
        return (
            base,
            checkbox(
                "confirm_metadata_export",
                "Export full retained metadata, including device identifiers and notes",
            ),
        )

    def _attempt_key(self, action, workflow):
        return action + ":" + workflow["session_head_sha256"]

    def blocked_reason(self, action_id, *, native_camera=None, helper=None):
        if action_id not in ACTIONS or self.setup.mode != "physical":
            return "Original camera identity records require physical file-only mode."
        if action_id == EXPORT:
            return (
                None
                if self.retained_diagnostics() is not None
                else "No retained original or attempted identity metadata is available."
            )
        workflow = self.setup.original_source_workflow()
        if workflow and workflow.get("schema") in {
            "rocell.physical_camera_source_workflow_readback.v8",
            "rocell.physical_camera_source_workflow_readback.v9",
            "rocell.physical_camera_source_workflow_readback.v10",
            "rocell.physical_camera_source_workflow_readback.v11",
            "rocell.physical_camera_source_workflow_readback.v12",
            # Future successor: deny replay only, not schema acceptance.
            "rocell.physical_camera_source_workflow_readback.v13",
        }:
            return "The original metadata prefix is historical after USB inspection starts; export it without replay."
        if self.setup.view()["publication"]["status"] != "CURRENT" or not workflow:
            return "Explicitly refresh or reopen and publish the original camera session first."
        received = workflow.get("received_camera_cycles", [])
        if (
            not received
            or received[-1]["state"] != "REVIEWED_PASS"
            or workflow.get("camera_identity_request") is None
        ):
            return "Review the received camera and explicitly request original identity stage first."
        if self._attempt_key(action_id, workflow) in self._attempted:
            return "This exact original action has already been attempted; inspect/export without automatic replay."
        cycles = workflow.get("camera_identity_cycles", [])
        if action_id == REVIEW:
            return (
                None
                if cycles and cycles[-1]["state"] == "REVIEW_PENDING"
                else "A complete original metadata assessment must await exact review."
            )
        if cycles and cycles[-1]["state"] != "REVIEWED_BLOCKED":
            return "Review the complete retained metadata, or inspect partial retention; do not replay an uncertain write."
        if len(cycles) >= MAX_COLLECTIONS:
            return "The four original metadata collections are exhausted; export history for review."
        if (
            type(native_camera) is not WizardNativeCameraEnrollment
            or type(helper) is not WizardCameraHelperRegistration
        ):
            return "Complete generic camera, helper and native metadata reviews before submitting their exact server-owned records."
        try:
            values = self._metadata_material(native_camera, helper)
            report = values["enrollment"]
            selection_from_enrollment_snapshot(
                report,
                source_sha256=self.source_sha256,
                launch_session_id=self.launch_id,
            )
            registration = helper.registration()
            if (
                registration is None
                or registration.payload["source_sha256"] != self.source_sha256
                or registration.payload["session_id"] != self.launch_id
                or registration.payload["mode"] != "physical"
                or registration.payload["helper_sha256"]
                != report["view"]["provenance"]["helper_sha256"]
            ):
                return "The exact current helper registration must match the reviewed native metadata."
        except (ValueError, TypeError, KeyError, AttributeError):
            return "Complete current-source/current-launch native and helper metadata reviews first."
        return None

    def _check(self, cancellation, deadline, *, source=True):
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline,
            "CAMERA_IDENTITY_INTERRUPTED",
            "Stopped or expired; inspect original records without replay.",
        )
        if source:
            _require(
                source_fingerprint(self.workspace) == self.source_sha256,
                "CAMERA_IDENTITY_SOURCE_CHANGED",
                "Source changed; retained identity evidence is historical only.",
            )
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline,
            "CAMERA_IDENTITY_INTERRUPTED",
            "Stopped during verification; no next mutation admitted.",
        )

    def _binding(self, workflow, operator):
        return dict(
            identity_id="cameraidentity-" + uuid4().hex,
            **self._context(),
            collection_launch_id=self.launch_id,
            operator_id=operator,
            received_camera={
                role: workflow["received_camera_cycles"][-1][role]["evidence_sha256"]
                for role in ("submission", "assessment", "review")
            },
            identity_request_event_sha256=workflow["camera_identity_request"][
                "event_sha256"
            ],
        )

    def _record(self, artifact, role, identity_id):
        return dict(
            document=artifact.to_dict(),
            evidence_sha256=artifact.sha256,
            reference=None,
            retention="COLLECTED_NOT_M1_RETAINED",
            label=f"camera-identity-{role}-v1:{identity_id}",
        )

    def _retain(self, tx, artifact, role, identity_id):
        record = self._record(artifact, role, identity_id)
        with self._lock:
            self._attempt["records"][role] = record
        ref = tx.store_evidence(
            _STAGE,
            artifact.payload,
            label=record["label"],
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        with self._lock:
            record.update(
                reference=ref.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
            )
        _require(
            tx.read_stage_evidence(ref) == artifact.payload,
            "CAMERA_IDENTITY_READBACK_CHANGED",
            "Exact original metadata bytes changed.",
        )
        with self._lock:
            record["retention"] = "M1_FULL_BYTES_READ_BACK"
        return ref

    def _read_records(self, tx, records, check):
        refs = []
        for record in records:
            check()
            ref = _parse_evidence_reference(record["reference"])
            _require(
                tx.read_stage_evidence(ref) == canonical(record["document"]),
                "CAMERA_IDENTITY_ORIGINAL_CHANGED",
                "The exact original identity predecessor changed.",
            )
            refs.append(ref)
        return refs

    def _result(self, action_id, report):
        result = dict(
            schema="rocell.wizard_worker_result.v1",
            action_id=action_id,
            status="SUCCEEDED",
            steps=[dict(name=action_id, exit_code=0, report=report)],
            device_open_count=0,
            serial_write_count=0,
            power_event_count=0,
            motion_command_count=0,
            contact_command_count=0,
            metadata_inventory_performed=False,
            physical_authority=False,
        )
        self._publication = dict(status="PENDING", operation_id=None)
        self._pending_result, self._pending_action = canonical(result), action_id
        return deepcopy(result)

    def perform(
        self,
        action_id,
        values,
        *,
        native_camera,
        helper,
        expected_context_sha256,
        cancellation,
        progress,
        export_parent=None,
    ):
        _require(
            self._operation_lock.acquire(blocking=False),
            "CAMERA_IDENTITY_BUSY",
            "An identity operation is active.",
        )
        deadline, mutated_setup = monotonic_ns() + 120_000_000_000, False
        try:
            reason = self.blocked_reason(
                action_id, native_camera=native_camera, helper=helper
            )
            _require(reason is None, "CAMERA_IDENTITY_ACTION_BLOCKED", reason or "")
            _require(
                type(values) is dict
                and set(values) == {field["name"] for field in self.fields(action_id)}
                and values.get("file_only") is True,
                "CAMERA_IDENTITY_FIELDS_INVALID",
                "Complete the exact file-only form; additional fields are not accepted.",
            )
            if action_id == EXPORT:
                _require(
                    values.get("confirm_metadata_export") is True,
                    "CAMERA_IDENTITY_EXPORT_ACK_REQUIRED",
                    "Explicitly acknowledge full metadata export.",
                )
                self._check(cancellation, deadline, source=False)
                from .physical_camera_identity_export import (
                    export_camera_identity_metadata,
                )

                with self._lock:
                    self._export_publication = deepcopy(self._publication)
                    diagnostic = self.retained_diagnostics()
                receipt = export_camera_identity_metadata(
                    diagnostic,
                    export_parent=export_parent,
                    source_sha256=self.source_sha256,
                    launch_id=self.launch_id,
                    cancellation=cancellation,
                    deadline_ns=deadline,
                )
                # Successful export evidence survives a subsequent Stop/log fault.
                with self._lock:
                    self._export_receipt = deepcopy(receipt)
                    return self._result(
                        action_id,
                        dict(metadata_export=receipt, meaning=MEANING, **_FLAGS),
                    )
            _require(
                self.context_sha256(native_camera=native_camera, helper=helper)
                == expected_context_sha256,
                "CAMERA_IDENTITY_CONTEXT_CHANGED",
                "The original or reviewed metadata changed; preview again.",
            )
            self._check(cancellation, deadline)
            material = canonical(self._original_material())
            workflow = self.setup.original_source_workflow()
            prerequisites = self.setup.current_prerequisite_artifact()
            received = ReceivedCameraSubmission(
                canonical(
                    workflow["received_camera_cycles"][-1]["submission"]["document"]
                ),
                prerequisites,
            )
            cycles = workflow.get("camera_identity_cycles", [])
            predecessor = None
            if cycles:
                latest = cycles[-1]
                prior_receipt = CameraIdentityReceipt(
                    canonical(latest["receipt"]["document"]), prerequisites
                )
                prior_assessment = CameraIdentityAssessment(
                    canonical(latest["assessment"]["document"])
                )
                if latest["review"] is not None:
                    predecessor = (
                        prior_receipt,
                        prior_assessment,
                        CameraIdentityReview(canonical(latest["review"]["document"])),
                    )
            metadata = registered = review = None
            if action_id == SUBMIT:
                _text(values["operator_id"], 64)
                _require(
                    values["observation_current"] is True,
                    "CAMERA_IDENTITY_OBSERVATION_ACK_REQUIRED",
                    "Record an observation or explicit unknown for this collection.",
                )
                observation = dict(
                    record_id="INT-018",
                    state=values["observation_state"],
                    value=values["observed_value"],
                    method=values["method"],
                    evidence_note=values["evidence_note"],
                )
                _observation(observation)
                binding = self._binding(workflow, values["operator_id"])
                identity_id = binding["identity_id"]
                reports = self._metadata_material(native_camera, helper)
                selection = selection_from_enrollment_snapshot(
                    reports["enrollment"],
                    source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                )
                collected = time_ns()
                metadata = build_camera_identity_metadata(
                    binding,
                    len(cycles) + 1,
                    reports["enrollment"],
                    (
                        None
                        if selection is None
                        else dict(
                            document=selection.identity_document,
                            sha256=selection.sha256,
                        )
                    ),
                    collected,
                )
                registered = build_camera_identity_helper(
                    binding, len(cycles) + 1, reports["helper"], collected
                )
                records = {
                    role: self._record(obj, role, identity_id)
                    for role, obj in (("metadata", metadata), ("helper", registered))
                }
            else:
                identity_id = cycles[-1]["identity_id"]
                review = review_camera_identity(
                    prior_receipt,
                    prior_assessment,
                    decision=values["decision"],
                    reviewer_id=values["reviewer_id"],
                    review_launch_id=self.launch_id,
                    reviewed_at_ns=time_ns(),
                )
                records = {"review": self._record(review, "review", identity_id)}
            self._check(cancellation, deadline)
            _require(
                canonical(self._original_material()) == material,
                "CAMERA_IDENTITY_CONTEXT_CHANGED",
                "The original context changed before collection storage.",
            )
            with self._lock:
                self._attempt = dict(
                    action_id=action_id, identity_id=identity_id, records=records
                )
                self._attempted.add(self._attempt_key(action_id, workflow))
            # Confirm complete known packet representation fits unchanged export
            # limits before any original write. Receipt/reference fields have
            # their own strict small role caps and are checked at construction.
            from .physical_camera_identity_export import (
                prepare_camera_identity_metadata_export,
            )

            prepare_camera_identity_metadata_export(
                self.retained_diagnostics(),
                source_sha256=self.source_sha256,
                launch_id=self.launch_id,
            )
            self.invalidate()
            mutated_setup = True
            progress(
                "Retaining exact reviewed camera metadata in the original setup record; no device access."
            )
            with self.setup.identity_transaction(
                cancellation=cancellation, progress=progress, deadline_ns=deadline
            ) as (_, current):
                _require(
                    canonical(current) == canonical(workflow),
                    "CAMERA_IDENTITY_CONTEXT_CHANGED",
                    "Original workflow changed before storage.",
                )
                verification = self.setup.session.view()["verification"]
                with self.setup.session.stage_transaction(
                    expected_challenge_sha256=verification["challenge_sha256"]
                ) as tx:
                    snapshot = tx.snapshot()
                    _require(
                        snapshot.head.head_sha256 == workflow["session_head_sha256"]
                        and snapshot.next_action.stage is _STAGE,
                        "CAMERA_IDENTITY_STAGE_CHANGED",
                        "Original stage or head changed; no replay.",
                    )
                    _require(
                        len([ref for ref in snapshot.evidence if ref.stage is _STAGE])
                        <= 5 * MAX_COLLECTIONS
                        and sum(
                            ref.payload_bytes
                            for ref in snapshot.evidence
                            if ref.stage is _STAGE
                        )
                        <= MAX_COLLECTIONS * sum(ROLE_BYTES.values()),
                        "CAMERA_IDENTITY_STORE_BUDGET",
                        "Original identity budget is exceeded.",
                    )
                    check = lambda: self._check(cancellation, deadline)
                    self._read_records(
                        tx,
                        [
                            workflow["received_camera_cycles"][-1][role]
                            for role in ("submission", "assessment", "review")
                        ],
                        check,
                    )
                    suffix = identity_id.removeprefix("cameraidentity-").upper()
                    if metadata is not None:
                        if cycles:
                            previous_refs = self._read_records(
                                tx, [cycles[-1][role] for role in ROLE_BYTES], check
                            )
                            check()
                            tx.commit_stage_state(
                                _STAGE,
                                V2StageState.WAITING_OPERATOR,
                                occurred_at_ns=time_ns(),
                                detail_code="CAMERA_IDENTITY_METADATA_STARTED_"
                                + suffix,
                                expected_head_sha256=tx.snapshot().head.head_sha256,
                                evidence=tuple(
                                    sorted(
                                        previous_refs, key=lambda ref: ref.evidence_id
                                    )
                                ),
                            )
                        check()
                        metadata_ref = self._retain(
                            tx, metadata, "metadata", identity_id
                        )
                        check()
                        helper_ref = self._retain(tx, registered, "helper", identity_id)
                        receipt = build_camera_identity_receipt(
                            prerequisites,
                            metadata=metadata,
                            helper=registered,
                            received_submission=received,
                            metadata_reference=metadata_ref,
                            helper_reference=helper_ref,
                            observation=observation,
                            submitted_at_ns=time_ns(),
                            predecessor=predecessor,
                        )
                        assessment = assess_camera_identity(
                            receipt,
                            metadata=metadata,
                            helper=registered,
                            received_submission=received,
                        )
                        refs = [metadata_ref, helper_ref]
                        for role, obj in (
                            ("receipt", receipt),
                            ("assessment", assessment),
                        ):
                            check()
                            refs.append(self._retain(tx, obj, role, identity_id))
                        target, phase = V2StageState.REVIEW_PENDING, "COLLECTED"
                    else:
                        refs = self._read_records(
                            tx,
                            [cycles[-1][role] for role in tuple(ROLE_BYTES)[:-1]],
                            check,
                        )
                        check()
                        refs.append(self._retain(tx, review, "review", identity_id))
                        target, phase = V2StageState.BLOCKED, "REVIEWED_BLOCKED"
                    check()
                    tx.commit_stage_state(
                        _STAGE,
                        target,
                        occurred_at_ns=time_ns(),
                        detail_code="CAMERA_IDENTITY_METADATA_" + phase + "_" + suffix,
                        expected_head_sha256=tx.snapshot().head.head_sha256,
                        evidence=tuple(sorted(refs, key=lambda ref: ref.evidence_id)),
                    )
                    check()
            self._check(cancellation, deadline)
            with self._lock:
                self._adopt(prerequisites)
                entry = self._workflow["camera_identity_request"]
                return self._result(
                    action_id,
                    dict(
                        action_id=action_id,
                        pending_completion_log=True,
                        original_context=self._context(),
                        cycles=self._cycles,
                        stage_states=self._stages,
                        identity_entry=entry["event_sha256"],
                        meaning=MEANING,
                        **_FLAGS,
                    ),
                )
        except BaseException:
            self.invalidate()
            if mutated_setup:
                self.setup.invalidate()
            raise
        finally:
            self._operation_lock.release()

    def validate_publication(self, result):
        with self._lock:
            _require(
                self._publication["status"] == "PENDING"
                and self._pending_result is not None
                and canonical(result) == self._pending_result,
                "CAMERA_IDENTITY_RESULT_CHANGED",
                "Retain exact complete identity result before durable publication.",
            )

    def publication_completed(self, operation_id):
        with self._lock:
            if self._publication["status"] != "PENDING" or self._pending_result is None:
                return
            self._publication = (
                (
                    self._export_publication
                    or dict(status="HISTORICAL_HELD", operation_id=None)
                )
                if self._pending_action == EXPORT
                else dict(status="CURRENT", operation_id=operation_id)
            )
            self._pending_result = self._pending_action = None

    def retained_diagnostics(self):
        with self._lock:
            workflow = (
                self.setup.session.retained_source_workflow() or self._workflow or {}
            )
            cycles = workflow.get("camera_identity_cycles", [])
            if not cycles and self._attempt is None:
                return None
            return deepcopy(
                dict(
                    schema="rocell.wizard_camera_identity_diagnostics.v1",
                    source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                    original_context=self._context(),
                    publication=self._publication,
                    stage_states=self._stages,
                    cycles=cycles,
                    attempt=self._attempt,
                    meaning=MEANING,
                    **_FLAGS,
                )
            )

    def export_metadata(self):
        return deepcopy(self._export_receipt)
