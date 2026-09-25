"""Original static-design collection/review and explicit receipt-stage entry.

There is no device provider in this service. It binds the existing design
validators to the original camera session, while Arrival owns tickets, Stop,
exact-result retention and completion logging. Nominal design values never
become received measurements or camera/arm release credentials.
"""

from __future__ import annotations

from copy import deepcopy
import re
from threading import Event, Lock, RLock
from time import monotonic_ns, time_ns
from typing import Any, Callable
from uuid import uuid4

from .physical_camera_setup_service import PhysicalCameraSetupService
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_v2 import V2StageState
from .physical_source_qualification import SourceQualificationReceipt
from .physical_static_contract import (
    StaticCameraContractReceipt,
    StaticCameraContractAssessment,
    StaticCameraContractReview,
    collect_static_camera_contract,
    assess_static_camera_contract,
    review_static_camera_contract,
    verify_static_camera_contract_receipt,
)
from .wizard_actions import WizardError
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.native_camera_protocol import canonical, digest

ACTIONS = frozenset(
    {
        "physical_static_contract_collect",
        "physical_static_contract_review",
        "physical_camera_receipt_begin",
    }
)
SCHEMA = "rocell.wizard_static_camera_onboarding.v1"
MEANING = (
    "Static-camera design verification only. Nominal board, camera and support "
    "values are not received measurements; design acceptance does not release "
    "installation, native camera access, arm power, motion or contact."
)
_STAGE = STAGE_ORDER[1]
_FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    native_release_allowed=False,
    device_io_performed=False,
)
_CODECS: dict[str, Any] = {
    "receipt": StaticCameraContractReceipt,
    "assessment": StaticCameraContractAssessment,
    "review": StaticCameraContractReview,
}
_ROLE_CAPS = {"receipt": 256 * 1024, "assessment": 32 * 1024, "review": 32 * 1024}


def _require(condition, code, message):
    if not condition:
        raise WizardError(code, message)


def _actor(value):
    _require(
        type(value) is str
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is not None,
        "STATIC_CONTRACT_ACTOR_INVALID",
        "Use a portable operator/reviewer label of 1–64 characters.",
    )


class PhysicalStaticCameraOnboardingService:
    """Inert cached UI, with one explicit original design cycle per session."""

    def __init__(self, setup: PhysicalCameraSetupService) -> None:
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
        self._contract: dict[str, Any] | None = None
        self._stages: dict[str, str] | None = None
        self._publication = {"status": "NOT_PUBLISHED", "operation_id": None}
        self._pending_result: bytes | None = None
        self._attempt: dict[str, Any] | None = None
        self._attempted: set[str] = set()

    def _adopt(self) -> None:
        self._workflow = self.setup.original_source_workflow()
        stages = self.setup.session.view().get("stages")
        self._stages = (
            None
            if stages is None
            else {
                stage.value: stages[index]["state"]
                for index, stage in enumerate(STAGE_ORDER[:3])
            }
        )
        record = (self._workflow or {}).get("static_contract")
        self._contract = (
            None
            if record is None
            else {
                "contract_id": record["contract_id"],
                "state": record["state"],
                **{
                    role: (
                        None
                        if record[role] is None
                        else codec(canonical(record[role]["document"])).safe_summary()
                    )
                    for role, codec in _CODECS.items()
                },
            }
        )

    def observe_setup(self) -> None:
        """Adopt only after explicit original readback has been durably logged."""
        with self._lock:
            if self.setup.view()["publication"]["status"] != "CURRENT":
                self.invalidate()
                return
            self._adopt()
            self._publication = deepcopy(self.setup.view()["publication"])
            if (self._workflow or {}).get("schema") in {
                "rocell.physical_camera_source_workflow_readback.v6",
                "rocell.physical_camera_source_workflow_readback.v7",
                "rocell.physical_camera_source_workflow_readback.v8",
                "rocell.physical_camera_source_workflow_readback.v9",
                "rocell.physical_camera_source_workflow_readback.v10",
                "rocell.physical_camera_source_workflow_readback.v11",
                "rocell.physical_camera_source_workflow_readback.v12",
                # Future successor: historical display only, not reader acceptance.
                "rocell.physical_camera_source_workflow_readback.v13",
            }:
                # The received-stage owner now presents the four-stage state.
                # Preserve exact design subjects without projecting later work
                # as a new current stage-2 publication.
                self._publication = {"status": "HISTORICAL_HELD", "operation_id": None}
            self._pending_result = None

    def invalidate(self) -> None:
        with self._lock:
            self._publication = {"status": "HISTORICAL_HELD", "operation_id": None}
            self._pending_result = None

    def _context(self):
        workflow = self._workflow
        if not workflow or not workflow.get("prerequisites"):
            return None
        binding = workflow["prerequisites"]["document"]["binding"]
        return dict(
            source_sha256=self.source_sha256,
            session_id=binding["session_id"],
            cell_id=workflow["binding"]["cell_id"],
            origin_launch_id=binding["launch_session_id"],
            header_sha256=workflow["session_header_sha256"],
            prerequisites_sha256=workflow["prerequisites"]["evidence_sha256"],
        )

    def view(self) -> dict[str, Any]:
        with self._lock:
            publication = deepcopy(self._publication)
            if (
                publication["status"] == "CURRENT"
                and self.setup.view()["publication"]["status"] != "CURRENT"
            ):
                publication = {"status": "HISTORICAL_HELD", "operation_id": None}
            current, pending = (
                publication["status"] == "CURRENT",
                publication["status"] == "PENDING",
            )
            status = "NOT_STARTED"
            if self._contract is not None:
                state = self._contract["state"]
                status = (
                    state
                    if state in {"REVIEW_PENDING", "REVIEWED_PASS", "REVIEWED_BLOCKED"}
                    else "INCOMPLETE_HELD"
                )
                if not current:
                    status = "HISTORICAL_HELD"
            entry = (self._workflow or {}).get("camera_receipt_request")
            return deepcopy(
                {
                    "schema": SCHEMA,
                    "source_sha256": self.source_sha256,
                    "launch_session_id": self.launch_id,
                    "original_context": self._context(),
                    "publication": publication,
                    "status": status,
                    "stage_states": self._stages,
                    "contract": None if pending else self._contract,
                    "camera_receipt_entry": (
                        None if pending or entry is None else entry["event_sha256"]
                    ),
                    "next_action": next(
                        (
                            action
                            for action in (
                                "physical_static_contract_collect",
                                "physical_static_contract_review",
                                "physical_camera_receipt_begin",
                            )
                            if current and self.blocked_reason(action) is None
                        ),
                        None,
                    ),
                    "meaning": MEANING,
                    **_FLAGS,
                }
            )

    def _original_material(self):
        return {
            "workflow": self.setup.original_source_workflow(),
            "binding": self.setup.session.descriptor(),
            "verification": self.setup.session.view()["verification"],
            "publication": self.setup.view()["publication"],
        }

    def context_sha256(self) -> str:
        with self._lock:
            return digest(
                canonical(
                    {
                        "source_sha256": self.source_sha256,
                        "launch_id": self.launch_id,
                        "original": self._original_material(),
                        "attempted": sorted(self._attempted),
                        "attempt": self._attempt,
                    }
                )
            )

    def fields(self, action_id):
        file_only = {
            "name": "file_only",
            "type": "checkbox",
            "label": "File-only design/receipt entry; no device or physical release",
            "required": True,
            "default": False,
        }
        if action_id not in ACTIONS:
            return ()
        if action_id == "physical_camera_receipt_begin":
            return (file_only,)
        actor = (
            "operator_id"
            if action_id == "physical_static_contract_collect"
            else "reviewer_id"
        )
        return (
            file_only,
            {
                "name": actor,
                "type": "text",
                "label": (
                    "Operator label"
                    if actor == "operator_id"
                    else "Distinct reviewer label (procedural, not authenticated)"
                ),
                "required": True,
                "default": "",
                "max_length": 64,
            },
        )

    def blocked_reason(self, action_id: str) -> str | None:
        if action_id not in ACTIONS or self.setup.mode != "physical":
            return "Static-camera onboarding requires the physical file-only workspace."
        workflow = self.setup.original_source_workflow()
        if self.setup.view()["publication"]["status"] != "CURRENT" or not workflow:
            return "Explicitly verify and publish the original camera session first."
        qualifications = workflow.get("qualification_cycles", [])
        if (
            not qualifications
            or qualifications[-1]["state"] != "REVIEWED_PASS"
            or workflow.get("static_camera_request") is None
        ):
            return "Review source-stage PASS and explicitly request the static-camera contract stage first."
        if action_id in self._attempted:
            return "This one-use action has already been attempted. Inspect/reopen the original; no replay or replacement is automatic."
        record = workflow.get("static_contract")
        if action_id == "physical_static_contract_collect":
            if record is not None:
                return "A static contract is already retained; review that exact subject or inspect partial retention without replay."
        elif action_id == "physical_static_contract_review":
            if record is None or record["state"] != "REVIEW_PENDING":
                return "A complete original static design assessment must be awaiting review."
        elif (
            record is None
            or record["state"] != "REVIEWED_PASS"
            or workflow.get("camera_receipt_request") is not None
        ):
            return "A committed reviewed design PASS and a still-pending received-camera stage are required."
        return None

    def _check(self, cancellation: Event, deadline: int) -> None:
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline,
            "STATIC_CONTRACT_INTERRUPTED",
            "Stopped or expired; no automatic replay.",
        )
        _require(
            source_fingerprint(self.workspace) == self.source_sha256,
            "STATIC_CONTRACT_SOURCE_CHANGED",
            "Source changed; retain and inspect the original diagnostics.",
        )
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline,
            "STATIC_CONTRACT_INTERRUPTED",
            "Stopped during source verification; no next mutation admitted.",
        )

    def _binding(self, workflow, operator_id):
        qualification = workflow["qualification_cycles"][-1]
        return dict(
            contract_id="staticcontract-" + uuid4().hex,
            source_sha256=self.source_sha256,
            cell_id=workflow["binding"]["cell_id"],
            session_id=workflow["binding"]["session_id"],
            header_sha256=workflow["session_header_sha256"],
            origin_launch_id=workflow["binding"]["launch_id"],
            collection_launch_id=self.launch_id,
            operator_id=operator_id,
            prerequisites_sha256=workflow["prerequisites"]["evidence_sha256"],
            source_qualification={
                role: qualification[role]["evidence_sha256"] for role in _CODECS
            },
            static_request_event_sha256=workflow["static_camera_request"][
                "event_sha256"
            ],
            store_directory=workflow["binding"]["directory"],
        )

    def _retain(self, tx, artifact, role, contract_id):
        payload = artifact.payload
        _require(
            len(payload) <= _ROLE_CAPS[role],
            "STATIC_CONTRACT_EVIDENCE_BUDGET",
            "The complete static subject exceeds its fixed budget.",
        )
        record = {
            "document": artifact.to_dict(),
            "evidence_sha256": artifact.sha256,
            "reference": None,
            "retention": "COLLECTED_NOT_M1_RETAINED",
        }
        with self._lock:
            assert self._attempt is not None
            self._attempt["records"][role] = record
        reference = tx.store_evidence(
            _STAGE,
            payload,
            label=f"static-camera-contract-{role}-v1:{contract_id}",
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        with self._lock:
            record.update(
                reference=reference.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
            )
        _require(
            tx.read_stage_evidence(reference) == payload,
            "STATIC_CONTRACT_READBACK_CHANGED",
            "The exact retained design subject changed.",
        )
        with self._lock:
            record["retention"] = "M1_FULL_BYTES_READ_BACK"
        return reference

    @staticmethod
    def _originals(tx, records, check):
        refs = []
        for record in records:
            check()
            reference = _parse_evidence_reference(record["reference"])
            _require(
                tx.read_stage_evidence(reference) == canonical(record["document"]),
                "STATIC_CONTRACT_ORIGINAL_CHANGED",
                "The exact original predecessor/review subject changed.",
            )
            refs.append(reference)
        return refs

    def perform(
        self,
        action_id: str,
        values: dict[str, Any],
        *,
        expected_context_sha256: str,
        cancellation: Event,
        progress: Callable[[str], None],
    ) -> dict[str, Any]:
        _require(
            self._operation_lock.acquire(blocking=False),
            "STATIC_CONTRACT_BUSY",
            "A static-camera onboarding action is active.",
        )
        deadline = (
            monotonic_ns()
            + (180 if action_id == "physical_static_contract_collect" else 120)
            * 1_000_000_000
        )
        mutated_setup = False
        try:
            reason = self.blocked_reason(action_id)
            _require(reason is None, "STATIC_CONTRACT_ACTION_BLOCKED", reason or "")
            _require(
                values.get("file_only") is True,
                "STATIC_CONTRACT_FILE_ONLY_REQUIRED",
                "Explicitly acknowledge this file-only operation.",
            )
            _require(
                self.context_sha256() == expected_context_sha256,
                "STATIC_CONTRACT_CONTEXT_CHANGED",
                "The original context changed; preview again.",
            )
            self._check(cancellation, deadline)
            material = canonical(self._original_material())
            workflow = self.setup.original_source_workflow()
            assert workflow is not None
            prerequisites = self.setup.current_prerequisite_artifact()
            parent = SourceQualificationReceipt(
                canonical(workflow["qualification_cycles"][-1]["receipt"]["document"])
            )
            binding, receipt, assessment, review = None, None, None, None
            if action_id == "physical_static_contract_collect":
                _actor(values.get("operator_id"))
                binding = self._binding(workflow, values["operator_id"])
                contract_id = binding["contract_id"]
            else:
                original = workflow["static_contract"]
                contract_id = original["contract_id"]
                if action_id == "physical_static_contract_review":
                    _actor(values.get("reviewer_id"))
                    receipt = StaticCameraContractReceipt(
                        canonical(original["receipt"]["document"])
                    )
                    assessment = StaticCameraContractAssessment(
                        canonical(original["assessment"]["document"])
                    )
                    review = review_static_camera_contract(
                        receipt,
                        assessment,
                        reviewer_id=values["reviewer_id"],
                        review_launch_id=self.launch_id,
                        reviewed_at_ns=time_ns(),
                    )
            self.invalidate()
            with self._lock:
                self._attempted.add(action_id)
                self._attempt = {
                    "action_id": action_id,
                    "contract_id": contract_id,
                    "records": {},
                }
            if binding is not None:
                progress(
                    "Verifying the original static camera, support and nominal board design; no device access."
                )
                try:
                    receipt = collect_static_camera_contract(
                        self.workspace,
                        binding=binding,
                        source_qualification=parent,
                        cancellation=cancellation,
                        progress=progress,
                        deadline_ns=deadline,
                    )
                except Exception as error:
                    candidate = getattr(error, "receipt", None)
                    if type(candidate) is StaticCameraContractReceipt:
                        verified = verify_static_camera_contract_receipt(
                            candidate,
                            prerequisites=prerequisites,
                            source_qualification=parent,
                            expected_binding=binding,
                            expected_receipt_sha256=candidate.sha256,
                        )
                        with self._lock:
                            self._attempt["collected_receipt"] = verified.to_dict()
                    raise
                receipt = verify_static_camera_contract_receipt(
                    receipt,
                    prerequisites=prerequisites,
                    source_qualification=parent,
                    expected_binding=binding,
                    expected_receipt_sha256=receipt.sha256,
                )
                with self._lock:
                    self._attempt["collected_receipt"] = receipt.to_dict()
                assessment = assess_static_camera_contract(receipt)
            self._check(cancellation, deadline)
            _require(
                canonical(self._original_material()) == material,
                "STATIC_CONTRACT_CONTEXT_CHANGED",
                "The original context changed during collection; no replacement or replay is followed.",
            )
            storage_deadline = min(deadline, monotonic_ns() + 120_000_000_000)
            mutated_setup = True
            with self.setup.static_contract_transaction(
                cancellation=cancellation,
                progress=progress,
                deadline_ns=storage_deadline,
            ) as (_, current):
                _require(
                    canonical(current) == canonical(workflow),
                    "STATIC_CONTRACT_CONTEXT_CHANGED",
                    "The exact original workflow changed before storage.",
                )
                verification = self.setup.session.view()["verification"]
                with self.setup.session.stage_transaction(
                    expected_challenge_sha256=verification["challenge_sha256"]
                ) as tx:
                    snapshot = tx.snapshot()
                    stage = (
                        STAGE_ORDER[2]
                        if action_id == "physical_camera_receipt_begin"
                        else _STAGE
                    )
                    _require(
                        snapshot.head.head_sha256 == workflow["session_head_sha256"]
                        and snapshot.next_action.stage is stage,
                        "STATIC_CONTRACT_STAGE_CHANGED",
                        "The original stage/head changed; no replay.",
                    )
                    check = lambda: self._check(cancellation, storage_deadline)
                    if binding is not None:
                        _require(
                            not any(ref.stage is _STAGE for ref in snapshot.evidence),
                            "STATIC_CONTRACT_ALREADY_RETAINED",
                            "An original static subject already exists.",
                        )
                        # Reserve all three fixed-size stage-2 subjects before any
                        # append. The source-stage inventory retains its own cap.
                        _require(
                            len(
                                [
                                    ref
                                    for ref in snapshot.evidence
                                    if ref.stage is STAGE_ORDER[0]
                                ]
                            )
                            <= 32
                            and sum(
                                ref.payload_bytes
                                for ref in snapshot.evidence
                                if ref.stage is STAGE_ORDER[0]
                            )
                            <= 4 * 1024 * 1024,
                            "STATIC_CONTRACT_ORIGINAL_STORE_BUDGET",
                            "The original source-stage budget is exceeded.",
                        )
                        self._originals(
                            tx,
                            [
                                workflow["qualification_cycles"][-1][role]
                                for role in _CODECS
                            ],
                            check,
                        )
                        assert receipt is not None and assessment is not None
                        refs = []
                        for role, artifact in (
                            ("receipt", receipt),
                            ("assessment", assessment),
                        ):
                            check()
                            refs.append(self._retain(tx, artifact, role, contract_id))
                        target, code = (
                            V2StageState.REVIEW_PENDING,
                            "STATIC_CAMERA_CONTRACT_COLLECTED_",
                        )
                    elif review is not None:
                        refs = self._originals(
                            tx,
                            [
                                workflow["static_contract"][role]
                                for role in ("receipt", "assessment")
                            ],
                            check,
                        )
                        check()
                        refs.append(self._retain(tx, review, "review", contract_id))
                        verdict = review.to_dict()["verdict"]
                        target, code = (
                            V2StageState(verdict),
                            "STATIC_CAMERA_CONTRACT_REVIEWED_" + verdict + "_",
                        )
                    else:
                        self._originals(
                            tx,
                            [workflow["static_contract"][role] for role in _CODECS],
                            check,
                        )
                        refs = (
                            []
                        )  # Do not cite another stage's evidence in a new event.
                        target, code = (
                            V2StageState.WAITING_OPERATOR,
                            "CAMERA_RECEIPT_REQUESTED_",
                        )
                    check()
                    tx.commit_stage_state(
                        stage,
                        target,
                        occurred_at_ns=time_ns(),
                        detail_code=code
                        + contract_id.removeprefix("staticcontract-").upper(),
                        expected_head_sha256=tx.snapshot().head.head_sha256,
                        evidence=tuple(sorted(refs, key=lambda ref: ref.evidence_id)),
                    )
                    check()
            self._check(cancellation, deadline)
            with self._lock:
                self._adopt()
                assert self._workflow is not None
                self._publication = {"status": "PENDING", "operation_id": None}
                report = {
                    "action_id": action_id,
                    "pending_completion_log": True,
                    "contract": self._contract,
                    "stage_states": self._stages,
                    "camera_receipt_entry": (
                        None
                        if not self._workflow.get("camera_receipt_request")
                        else self._workflow["camera_receipt_request"]["event_sha256"]
                    ),
                    "meaning": MEANING,
                    **_FLAGS,
                }
                result = {
                    "schema": "rocell.wizard_worker_result.v1",
                    "action_id": action_id,
                    "status": "SUCCEEDED",
                    "steps": [{"name": action_id, "exit_code": 0, "report": report}],
                    "device_open_count": 0,
                    "serial_write_count": 0,
                    "power_event_count": 0,
                    "motion_command_count": 0,
                    "contact_command_count": 0,
                    "metadata_inventory_performed": False,
                    "physical_authority": False,
                }
                self._pending_result = canonical(result)
                return deepcopy(result)
        except BaseException:
            self.invalidate()
            if mutated_setup:
                self.setup.invalidate()
            raise
        finally:
            self._operation_lock.release()

    def validate_publication(self, result: dict[str, Any]) -> None:
        with self._lock:
            _require(
                self._publication["status"] == "PENDING"
                and self._pending_result is not None
                and canonical(result) == self._pending_result,
                "STATIC_CONTRACT_RESULT_CHANGED",
                "Retain the exact complete design result before publication.",
            )

    def publication_completed(self, operation_id: str) -> None:
        with self._lock:
            if (
                self._publication["status"] == "PENDING"
                and self._pending_result is not None
            ):
                self._publication = {"status": "CURRENT", "operation_id": operation_id}
                self._pending_result = None

    def retained_diagnostics(self) -> dict[str, Any] | None:
        """Full metadata, with exact duplicate attempt documents referenced once."""
        with self._lock:
            workflow = (
                self.setup.session.retained_source_workflow() or self._workflow or {}
            )
            record = deepcopy(workflow.get("static_contract"))
            if record is None and self._attempt is None:
                return None
            documents, keys = {}, {}

            def keep(document, name):
                wire = canonical(document)
                if wire not in keys:
                    keys[wire] = name
                    documents[name] = document
                return keys[wire]

            if record:
                for role in _CODECS:
                    if record[role] is not None:
                        record[role]["document_key"] = keep(
                            record[role].pop("document"), "static_" + role
                        )
            attempt = deepcopy(self._attempt)
            if attempt:
                if "collected_receipt" in attempt:
                    attempt["collected_receipt_document_key"] = keep(
                        attempt.pop("collected_receipt"),
                        "static_attempt_collected_receipt",
                    )
                for role, item in attempt["records"].items():
                    item["document_key"] = keep(
                        item.pop("document"), "static_attempt_" + role
                    )
            return {
                "schema": "rocell.wizard_static_camera_onboarding_diagnostics.v1",
                "original_context": self._context(),
                "publication": deepcopy(self._publication),
                "stage_states": deepcopy(self._stages),
                "static_contract": record,
                "camera_receipt_request": deepcopy(
                    workflow.get("camera_receipt_request")
                ),
                "attempt": attempt,
                **documents,
                "meaning": MEANING,
                **_FLAGS,
            }
