"""Explicit source-stage reassessment over original M1 subjects.

This owner composes file collection, fixed hardware-free ownership experiments,
guarded isolation attachments and deterministic review. It has no camera/arm
provider. Arrival owns action tickets, Stop, result retention and completion-log
publication. Stage acceptance is deliberately separate from native release.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from threading import Event, Lock, RLock
from time import monotonic_ns, time_ns
from typing import Any, Callable
from uuid import uuid4

from .physical_camera_setup_service import PhysicalCameraSetupService
from .physical_intake_inbox import PhysicalIntakeInbox
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_v2 import V2StageState
from .physical_source_stage_evidence import collect_workspace_source_receipt
from .physical_source_qualification import (
    LABELS,
    MAX_RECEIPT_BYTES,
    MAX_ASSESSMENT_BYTES,
    MAX_REVIEW_BYTES,
    MAX_QUALIFICATIONS,
    SourceQualificationReceipt,
    SourceQualificationAssessment,
    SourceQualificationReview,
    build_source_qualification_receipt,
    assess_source_qualification,
    review_source_qualification,
    ownership_directory,
)
from .physical_ownership_qualification import (
    PhysicalOwnershipQualification,
    collect_physical_ownership_qualification,
    verify_physical_ownership_qualification,
)
from .wizard_actions import WizardError
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.native_camera_protocol import canonical, digest

ACTIONS = frozenset(
    {
        "physical_source_isolation_files_discover",
        "physical_source_qualify",
        "physical_source_qualification_review",
        "physical_static_contract_begin",
    }
)
SCHEMA = "rocell.wizard_source_reassessment.v1"
MEANING = (
    "Source-stage evidence only — no camera runtime release. Source checks and software "
    "ownership coverage do not qualify received hardware. An isolation statement "
    "is not current electrical telemetry; attachments do not prove measurement truth."
)
_CODECS = {
    "receipt": SourceQualificationReceipt,
    "assessment": SourceQualificationAssessment,
    "review": SourceQualificationReview,
}
_STAGE = STAGE_ORDER[0]
_FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    native_release_allowed=False,
    device_io_performed=False,
)


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise WizardError(code, message)


def _actor(value: Any) -> None:
    _require(
        type(value) is str
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is not None,
        "SOURCE_QUALIFICATION_ACTOR_INVALID",
        "Use a portable operator/reviewer label of 1–64 characters.",
    )


class PhysicalSourceQualificationService:
    """All views are cached and inert; every collection is an explicit action."""

    def __init__(self, setup: PhysicalCameraSetupService) -> None:
        if type(setup) is not PhysicalCameraSetupService:
            raise TypeError("Exact application-owned setup required")
        self.setup = setup
        self.workspace, self.launch_id, self.source_sha256 = (
            setup.workspace,
            setup.launch_id,
            setup.source_sha256,
        )
        self.inbox = PhysicalIntakeInbox(
            self.workspace, launch_id=self.launch_id, source_sha256=self.source_sha256
        )
        self._lock, self._operation_lock = RLock(), Lock()
        self._workflow: dict[str, Any] | None = None
        self._summary: dict[str, Any] | None = None
        self._stages: dict[str, str] | None = None
        self._publication = {"status": "NOT_PUBLISHED", "operation_id": None}
        self._attempt: dict[str, Any] | None = None
        self._pending_result: bytes | None = None
        self._discovery_published = False

    def _adopt(self) -> None:
        self._workflow = self.setup.original_source_workflow()
        cycles = self._cycles()
        # Verify and summarize once at audited adoption, not on every browser GET.
        self._summary = None if not cycles else self._compact(cycles[-1])
        stages = self.setup.session.view().get("stages")
        self._stages = (
            None
            if stages is None
            else {
                "workspace_sources": stages[0]["state"],
                "static_camera_contract": stages[1]["state"],
            }
        )

    def observe_setup(self) -> None:
        """Called after an explicit audited setup/reopen operation is logged."""
        with self._lock:
            if self.setup.view()["publication"]["status"] != "CURRENT":
                self.invalidate()
                return
            self._adopt()
            self._publication = deepcopy(self.setup.view()["publication"])
            if (self._workflow or {}).get("schema") in {
                "rocell.physical_camera_source_workflow_readback.v5",
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
                # This v1 card describes only the source/entry prefix. Later
                # stage state belongs to the current static-camera onboarding
                # card; keep these exact reviewed subjects as readable history.
                self._publication = {"status": "HISTORICAL_HELD", "operation_id": None}
            self._pending_result = None

    def invalidate(self) -> None:
        with self._lock:
            self._publication = {"status": "HISTORICAL_HELD", "operation_id": None}
            self._pending_result = None

    def _cycles(self) -> list[dict[str, Any]]:
        return (self._workflow or {}).get("qualification_cycles", [])

    def _context(self) -> dict[str, Any] | None:
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

    @staticmethod
    def _compact(cycle: dict[str, Any]) -> dict[str, Any] | None:
        if cycle.get("receipt") is None or cycle.get("assessment") is None:
            return None
        receipt = SourceQualificationReceipt(canonical(cycle["receipt"]["document"]))
        assessment = assess_source_qualification(receipt)
        _require(
            assessment.sha256 == cycle["assessment"]["evidence_sha256"],
            "SOURCE_QUALIFICATION_SUBJECT_CHANGED",
            "Exact assessment subject required.",
        )
        document, result = receipt.to_dict(), assessment.to_dict()
        binding, isolation = document["binding"], document["isolation"]
        ownership = PhysicalOwnershipQualification(
            canonical(document["ownership_report"])
        ).safe_summary()
        review = cycle.get("review")
        review_data = (
            None
            if review is None
            else SourceQualificationReview(canonical(review["document"])).to_dict()
        )
        return {
            "qualification_id": cycle["qualification_id"],
            "collection_launch_id": binding["collection_launch_id"],
            "operator_id": binding["operator_id"],
            "original_subjects": {
                role + "_sha256": sha
                for role, sha in binding["predecessor_source"].items()
            },
            "receipt_sha256": receipt.sha256,
            "assessment_sha256": assessment.sha256,
            "software_checks": document["software_receipt"]["software_checks"],
            "isolation": {
                "state": isolation["status"],
                "statement": isolation["statement"],
                "attachment_sha256": (
                    None
                    if isolation["original_reference"] is None
                    else isolation["original_reference"]["payload_sha256"]
                ),
                "measurement_truth_verified": False,
            },
            "ownership": {
                "status": (
                    "SOFTWARE_MECHANISMS_PASSED"
                    if ownership["status"] == "SOFTWARE_OWNERSHIP_COVERED"
                    else "HELD"
                ),
                "report_sha256": ownership["report_sha256"],
                "checks": [
                    {
                        "check_id": row["id"],
                        "passed": row["passed"],
                        "provenance": row["provenance"],
                    }
                    for row in ownership["checks"]
                ],
            },
            "verdict": result["verdict"],
            "missing_requirements": result["missing_requirements"],
            "review": (
                None
                if review_data is None
                else {
                    "review_sha256": cycle["review"]["evidence_sha256"],
                    "reviewer_id": review_data["reviewer_id"],
                    "review_launch_id": review_data["review_launch_id"],
                    "verdict": review_data["verdict"],
                    "distinct_operator_labels": True,
                    "authenticated_independent_people": False,
                }
            ),
        }

    def view(self) -> dict[str, Any]:
        with self._lock:
            latest = self._cycles()[-1] if self._cycles() else None
            pending = self._publication["status"] == "PENDING"
            current = (
                self._publication["status"] == "CURRENT"
                and self.setup.view()["publication"]["status"] == "CURRENT"
            )
            status, next_action = "NOT_STARTED", None
            qualification = None if pending else self._summary
            if latest:
                status = (
                    latest["state"]
                    if latest["state"]
                    in {"REVIEW_PENDING", "REVIEWED_PASS", "REVIEWED_BLOCKED"}
                    else "INCOMPLETE_HELD"
                )
                if not current:
                    status = "HISTORICAL_HELD"
            if current:
                for action in (
                    "physical_source_qualify",
                    "physical_source_qualification_review",
                    "physical_static_contract_begin",
                ):
                    if self.blocked_reason(action) is None:
                        next_action = action
                        break
            publication = deepcopy(self._publication)
            if not current and publication["status"] == "CURRENT":
                publication = {"status": "HISTORICAL_HELD", "operation_id": None}
            return deepcopy(
                dict(
                    schema=SCHEMA,
                    status=status,
                    source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                    original_context=self._context(),
                    publication=publication,
                    stage_states=self._stages,
                    qualification=qualification,
                    next_action=next_action,
                    meaning=MEANING,
                    **_FLAGS,
                )
            )

    def _original_material(self) -> dict[str, Any]:
        return {
            "workflow": self.setup.original_source_workflow(),
            "descriptor": self.setup.session.descriptor(),
            "verification": self.setup.session.view()["verification"],
            "publication": self.setup.view()["publication"],
            "inbox": self.inbox.view(),
        }

    def context_sha256(self) -> str:
        with self._lock:
            return digest(
                canonical(
                    {
                        "source_sha256": self.source_sha256,
                        "launch_id": self.launch_id,
                        "original": self._original_material(),
                        "attempt": self._attempt,
                    }
                )
            )

    def fields(self, action_id: str) -> tuple[dict[str, Any], ...]:
        file_only = {
            "name": "file_only",
            "label": "File-only source stage; no camera, arm, power or motion commands",
            "type": "checkbox",
            "required": True,
            "default": False,
        }
        actor = lambda name, label: {
            "name": name,
            "label": label,
            "type": "text",
            "required": True,
            "default": "",
        }
        if action_id == "physical_source_qualify":
            choices = [{"value": "", "label": "No attachment (UNKNOWN only)"}]
            if self._discovery_published:
                choices += self.inbox.choices()
            return (
                file_only,
                actor("operator_id", "Operator label (procedural, not authenticated)"),
                {
                    "name": "isolation_state",
                    "label": "Actuator power isolation observation",
                    "type": "select",
                    "required": True,
                    "default": "UNKNOWN",
                    "options": [
                        {"value": "UNKNOWN", "label": "UNKNOWN — not observed"},
                        {
                            "value": "OBSERVED_DISCONNECTED",
                            "label": "I observed disconnected actuator power (original evidence required)",
                        },
                    ],
                },
                {
                    "name": "isolation_statement",
                    "label": "Isolation statement (one line, maximum 512 UTF-8 bytes)",
                    "type": "text",
                    "required": False,
                    "default": "",
                },
                {
                    "name": "isolation_choice",
                    "label": "Original from the assigned intake inbox",
                    "type": "select",
                    "required": False,
                    "default": "",
                    "options": choices,
                },
            )
        if action_id == "physical_source_qualification_review":
            return (
                file_only,
                actor(
                    "reviewer_id",
                    "Distinct reviewer label (procedural, not authenticated)",
                ),
            )
        return (file_only,) if action_id == "physical_static_contract_begin" else ()

    def blocked_reason(self, action_id: str) -> str | None:
        if action_id not in ACTIONS or self.setup.mode != "physical":
            return "Source reassessment requires the physical file-only workspace."
        workflow = self.setup.original_source_workflow()
        if (
            self.setup.view()["publication"]["status"] != "CURRENT"
            or not workflow
            or not workflow.get("review")
        ):
            return "Explicitly verify and publish the original source review first."
        cycles, intakes = workflow.get("qualification_cycles", []), workflow.get(
            "intake_collections", []
        )
        if not cycles and (
            workflow["state"] != "BLOCKED"
            or (intakes and intakes[-1]["state"] != "REVIEWED_BLOCKED")
        ):
            return (
                "Complete the exact original source/intake review before reassessment."
            )
        last = cycles[-1] if cycles else None
        if action_id in {
            "physical_source_qualify",
            "physical_source_isolation_files_discover",
        }:
            if last and last["state"] != "REVIEWED_BLOCKED":
                return "Review the current exact subject; partial retention cannot be replayed."
            if len(cycles) >= MAX_QUALIFICATIONS:
                return "The eight-cycle budget is exhausted; retain and inspect the original history."
        elif action_id == "physical_source_qualification_review":
            if last is None or last["state"] != "REVIEW_PENDING":
                return "A complete original qualification must be awaiting review."
        elif (
            last is None
            or last["state"] != "REVIEWED_PASS"
            or workflow.get("static_camera_request") is not None
        ):
            return "Stage 1 must have an exact committed PASS and stage 2 must still be PENDING."
        return None

    def _check(self, cancellation: Event, deadline: int) -> None:
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline,
            "SOURCE_QUALIFICATION_INTERRUPTED",
            "Stopped or expired; no automatic replay.",
        )
        _require(
            source_fingerprint(self.workspace) == self.source_sha256,
            "SOURCE_QUALIFICATION_SOURCE_CHANGED",
            "Source changed; retained records are historical only.",
        )
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline,
            "SOURCE_QUALIFICATION_INTERRUPTED",
            "Stopped during verification; no next mutation admitted.",
        )

    @staticmethod
    def _refs(records):
        by_id = {ref.evidence_id: ref for ref in records}
        return tuple(by_id[key] for key in sorted(by_id))

    def _retain(
        self, transaction, payload, role, qualification_id, media="application/json"
    ):
        record = {
            "label": LABELS[role] + ":" + qualification_id,
            "evidence_sha256": digest(payload),
            "reference": None,
            "retention": "COLLECTED_NOT_M1_RETAINED",
        }
        if role in _CODECS:
            record["document"] = _CODECS[role](payload).to_dict()
        with self._lock:
            assert self._attempt is not None
            self._attempt["records"][role] = record
        reference = transaction.store_evidence(
            _STAGE,
            payload,
            label=record["label"],
            media_type=media,
            captured_at_ns=time_ns(),
            expected_head_sha256=transaction.snapshot().head.head_sha256,
        )
        with self._lock:
            record.update(
                reference=reference.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
            )
        _require(
            transaction.read_stage_evidence(reference) == payload,
            "SOURCE_QUALIFICATION_READBACK_CHANGED",
            "The original retained bytes differ.",
        )
        with self._lock:
            record["retention"] = "M1_FULL_BYTES_READ_BACK"
        return reference

    def _binding(self, workflow, qualification_id, operator_id):
        cycles = workflow.get("qualification_cycles", [])
        return dict(
            qualification_id=qualification_id,
            source_sha256=self.source_sha256,
            cell_id=workflow["binding"]["cell_id"],
            session_id=workflow["binding"]["session_id"],
            header_sha256=workflow["session_header_sha256"],
            origin_launch_id=workflow["binding"]["launch_id"],
            collection_launch_id=self.launch_id,
            operator_id=operator_id,
            prerequisites_sha256=workflow["prerequisites"]["evidence_sha256"],
            predecessor_source={
                role: workflow[role]["evidence_sha256"] for role in _CODECS
            },
            predecessor_qualification=(
                None
                if not cycles
                else {role: cycles[-1][role]["evidence_sha256"] for role in _CODECS}
            ),
            store_directory=workflow["binding"]["directory"],
        )

    def _collect_originals(
        self, transaction, workflow, binding, software, ownership, values, files, check
    ):
        snapshot = transaction.snapshot()
        reserve = MAX_RECEIPT_BYTES + MAX_ASSESSMENT_BYTES + MAX_REVIEW_BYTES
        _require(
            len(snapshot.evidence) + len(files) + 3 <= 32
            and sum(ref.payload_bytes for ref in snapshot.evidence)
            + sum(len(f.payload) for f in files)
            + reserve
            <= 4 * 1024 * 1024,
            "SOURCE_QUALIFICATION_ORIGINAL_STORE_BUDGET",
            "The original 32-reference / 4 MiB budget cannot retain this collection and review; nothing was appended.",
        )
        cycles, intakes = workflow.get("qualification_cycles", []), workflow.get(
            "intake_collections", []
        )
        start_records = (
            [cycles[-1][role] for role in _CODECS]
            if cycles
            else [workflow[role] for role in _CODECS]
        )
        if not cycles and intakes:
            start_records += [
                intakes[-1][role] for role in ("submission", "assessment", "review")
            ]
        # Bind the exact original predecessor bytes under the same storage leases.
        for item in start_records:
            check()
            _require(
                transaction.read_stage_evidence(
                    _parse_evidence_reference(item["reference"])
                )
                == canonical(item["document"]),
                "SOURCE_QUALIFICATION_SUBJECT_CHANGED",
                "The original predecessor subject differs.",
            )
        suffix, qid = (
            binding["qualification_id"][11:].upper(),
            binding["qualification_id"],
        )
        check()
        transaction.commit_stage_state(
            _STAGE,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=time_ns(),
            detail_code="WORKSPACE_SOURCE_QUALIFICATION_STARTED_" + suffix,
            expected_head_sha256=snapshot.head.head_sha256,
            evidence=self._refs(
                _parse_evidence_reference(item["reference"]) for item in start_records
            ),
        )
        refs = []
        original = None
        if files:
            check()
            original = self._retain(
                transaction,
                files[0].payload,
                "isolation_original",
                qid,
                files[0].media_type,
            )
            refs.append(original)
        receipt = build_source_qualification_receipt(
            binding=binding,
            software_receipt=software,
            ownership_report=ownership,
            isolation=dict(
                status=values.get("isolation_state", "UNKNOWN"),
                statement=values.get("isolation_statement", ""),
                original_reference=None if original is None else original.to_dict(),
                basename=None if not files else files[0].basename,
                recorded_at_ns=time_ns(),
            ),
        )
        for role, subject in (
            ("receipt", receipt),
            ("assessment", assess_source_qualification(receipt)),
        ):
            check()
            refs.append(self._retain(transaction, subject.payload, role, qid))
        check()
        transaction.commit_stage_state(
            _STAGE,
            V2StageState.REVIEW_PENDING,
            occurred_at_ns=time_ns(),
            detail_code="WORKSPACE_SOURCE_QUALIFICATION_ASSESSED_" + suffix,
            expected_head_sha256=transaction.snapshot().head.head_sha256,
            evidence=self._refs(refs),
        )

    def _review(self, transaction, latest, review, check):
        refs = []
        for role in ("isolation_original", "receipt", "assessment"):
            item = latest[role]
            if item is None:
                continue
            check()
            ref = _parse_evidence_reference(item["reference"])
            payload = transaction.read_stage_evidence(ref)
            _require(
                digest(payload) == item["evidence_sha256"]
                and (
                    role == "isolation_original"
                    or payload == canonical(item["document"])
                ),
                "SOURCE_QUALIFICATION_SUBJECT_CHANGED",
                "The original review subject differs.",
            )
            refs.append(ref)
        qid = latest["qualification_id"]
        check()
        refs.append(self._retain(transaction, review.payload, "review", qid))
        verdict = review.to_dict()["verdict"]
        check()
        transaction.commit_stage_state(
            _STAGE,
            V2StageState(verdict),
            occurred_at_ns=time_ns(),
            detail_code="WORKSPACE_SOURCE_QUALIFICATION_REVIEWED_"
            + verdict
            + "_"
            + qid[11:].upper(),
            expected_head_sha256=transaction.snapshot().head.head_sha256,
            evidence=self._refs(refs),
        )

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
            "SOURCE_QUALIFICATION_BUSY",
            "A source qualification action is active.",
        )
        duration = (
            60
            if action_id == "physical_source_isolation_files_discover"
            else 300 if action_id == "physical_source_qualify" else 120
        )
        deadline, mutated_setup = monotonic_ns() + duration * 1_000_000_000, False
        try:
            reason = self.blocked_reason(action_id)
            _require(
                reason is None, "SOURCE_QUALIFICATION_ACTION_BLOCKED", reason or ""
            )
            _require(
                self.context_sha256() == expected_context_sha256,
                "SOURCE_QUALIFICATION_CONTEXT_CHANGED",
                "Original subjects or choices changed; preview again.",
            )
            _require(
                action_id == "physical_source_isolation_files_discover"
                or values.get("file_only") is True,
                "SOURCE_QUALIFICATION_FILE_ONLY_REQUIRED",
                "Explicitly acknowledge this file-only source operation.",
            )
            self._check(cancellation, deadline)
            original_material = canonical(self._original_material())
            workflow = self.setup.original_source_workflow()
            assert workflow is not None
            prerequisites = self.setup.current_prerequisite_artifact()
            chosen: tuple[str, ...] = ()
            binding, software, ownership, review = None, None, None, None
            if action_id == "physical_source_qualify":
                _actor(values.get("operator_id"))
                observation, statement, choice = (
                    values.get("isolation_state", "UNKNOWN"),
                    values.get("isolation_statement", ""),
                    values.get("isolation_choice", ""),
                )
                _require(
                    observation in {"UNKNOWN", "OBSERVED_DISCONNECTED"}
                    and type(statement) is str
                    and statement == statement.strip()
                    and len(statement.encode("utf-8")) <= 512
                    and all(
                        ord(c) >= 32 and not 127 <= ord(c) <= 159 for c in statement
                    )
                    and type(choice) is str,
                    "SOURCE_QUALIFICATION_ISOLATION_INVALID",
                    "Use a supported isolation state and a trimmed control-free statement of at most 512 UTF-8 bytes.",
                )
                _require(
                    observation != "OBSERVED_DISCONNECTED"
                    or bool(choice)
                    and len(statement) >= 12,
                    "SOURCE_QUALIFICATION_ISOLATION_ORIGINAL_REQUIRED",
                    "An observed disconnection requires an original attachment and a descriptive statement.",
                )
                if choice:
                    _require(
                        self._discovery_published,
                        "SOURCE_QUALIFICATION_DISCOVERY_REQUIRED",
                        "Publish an explicit inbox discovery first.",
                    )
                    self.inbox.preview(choice)
                    chosen = (choice,)
                binding = self._binding(
                    workflow, "sourcequal-" + uuid4().hex, values["operator_id"]
                )
            elif action_id == "physical_source_qualification_review":
                _actor(values.get("reviewer_id"))
                latest = workflow["qualification_cycles"][-1]
                review = review_source_qualification(
                    SourceQualificationReceipt(
                        canonical(latest["receipt"]["document"])
                    ),
                    SourceQualificationAssessment(
                        canonical(latest["assessment"]["document"])
                    ),
                    reviewer_id=values["reviewer_id"],
                    review_launch_id=self.launch_id,
                    reviewed_at_ns=time_ns(),
                )
            self.invalidate()
            if action_id == "physical_source_isolation_files_discover":
                self._discovery_published = False
                progress(
                    "Discovering bounded originals in the assigned intake inbox; no device access."
                )
                self.inbox.discover(
                    cancellation=cancellation,
                    deadline_ns=min(deadline, monotonic_ns() + 60_000_000_000),
                )
            else:
                qid = (
                    binding["qualification_id"]
                    if binding is not None
                    else workflow["qualification_cycles"][-1]["qualification_id"]
                )
                with self._lock:
                    self._attempt = {
                        "qualification_id": qid,
                        "action_id": action_id,
                        "records": {},
                    }
                    if binding is not None:
                        self._attempt["ownership_directory"] = str(
                            ownership_directory(binding)
                        )
                if binding is not None:
                    progress(
                        "Collecting fresh controlled source checks, without hardware access."
                    )
                    software = collect_workspace_source_receipt(
                        self.workspace,
                        prerequisites=prerequisites,
                        source_sha256=self.source_sha256,
                        session_id=binding["session_id"],
                        origin_launch_id=binding["origin_launch_id"],
                        collection_launch_id=self.launch_id,
                        header_sha256=binding["header_sha256"],
                        operator_id=binding["operator_id"],
                        cancellation=cancellation,
                        progress=progress,
                    )
                    with self._lock:
                        self._attempt["software_receipt"] = software.to_dict()
                    self._check(cancellation, deadline)
                    progress(
                        "Running fixed software ownership and no-replay checks in a fresh assigned directory; no device access."
                    )
                    try:
                        ownership = collect_physical_ownership_qualification(
                            self.workspace,
                            assigned_directory=ownership_directory(binding),
                            source_sha256=self.source_sha256,
                            cancellation=cancellation,
                            progress=progress,
                            deadline_ns=min(deadline, monotonic_ns() + 120_000_000_000),
                        )
                    except Exception as error:
                        # The fixed collector can preserve an exact failed report
                        # on its exception. Keep that history without converting
                        # uncertain cleanup or interrupted work into assessment.
                        retained = getattr(error, "report", None)
                        if type(retained) is PhysicalOwnershipQualification:
                            verified = verify_physical_ownership_qualification(
                                retained,
                                expected_source_sha256=self.source_sha256,
                                expected_directory=ownership_directory(binding),
                                expected_report_sha256=retained.sha256,
                            )
                            _require(
                                verified.to_dict()["binding"]["workspace"]
                                == str(self.workspace),
                                "SOURCE_QUALIFICATION_WORKSPACE_CHANGED",
                                "The ownership report belongs to a different workspace.",
                            )
                            with self._lock:
                                self._attempt["ownership_report"] = verified.to_dict()
                        raise
                    ownership = verify_physical_ownership_qualification(
                        ownership,
                        expected_source_sha256=self.source_sha256,
                        expected_directory=ownership_directory(binding),
                        expected_report_sha256=ownership.sha256,
                    )
                    _require(
                        ownership.to_dict()["binding"]["workspace"]
                        == str(self.workspace),
                        "SOURCE_QUALIFICATION_WORKSPACE_CHANGED",
                        "The ownership report belongs to a different workspace.",
                    )
                    with self._lock:
                        self._attempt["ownership_report"] = ownership.to_dict()
                self._check(cancellation, deadline)
                _require(
                    canonical(self._original_material()) == original_material,
                    "SOURCE_QUALIFICATION_CONTEXT_CHANGED",
                    "Original setup changed during collection; retained diagnostics are historical, not replayed.",
                )
                # Keep input handles pinned through retention and its final audit.
                storage_deadline = min(deadline, monotonic_ns() + 120_000_000_000)
                with self.inbox.selected_files(
                    chosen, cancellation=cancellation, deadline_ns=storage_deadline
                ) as files:
                    mutated_setup = True
                    with self.setup.qualification_transaction(
                        cancellation=cancellation,
                        progress=progress,
                        deadline_ns=storage_deadline,
                    ) as (_, current):
                        _require(
                            canonical(current) == canonical(workflow),
                            "SOURCE_QUALIFICATION_CONTEXT_CHANGED",
                            "The exact original workflow changed before storage.",
                        )
                        verification = self.setup.session.view()["verification"]
                        with self.setup.session.stage_transaction(
                            expected_challenge_sha256=verification["challenge_sha256"]
                        ) as transaction:
                            snapshot = transaction.snapshot()
                            expected_stage = (
                                STAGE_ORDER[1]
                                if action_id == "physical_static_contract_begin"
                                else _STAGE
                            )
                            _require(
                                snapshot.head.head_sha256
                                == workflow["session_head_sha256"]
                                and snapshot.next_action.stage is expected_stage,
                                "SOURCE_QUALIFICATION_STAGE_CHANGED",
                                "The original stage/head changed; no replay.",
                            )
                            check = lambda: self._check(cancellation, storage_deadline)
                            if binding is not None:
                                self._collect_originals(
                                    transaction,
                                    workflow,
                                    binding,
                                    software,
                                    ownership,
                                    values,
                                    files,
                                    check,
                                )
                            elif review is not None:
                                self._review(
                                    transaction,
                                    workflow["qualification_cycles"][-1],
                                    review,
                                    check,
                                )
                            else:
                                check()
                                transaction.commit_stage_state(
                                    STAGE_ORDER[1],
                                    V2StageState.WAITING_OPERATOR,
                                    occurred_at_ns=time_ns(),
                                    detail_code="STATIC_CAMERA_CONTRACT_REQUESTED_"
                                    + qid[11:].upper(),
                                    expected_head_sha256=snapshot.head.head_sha256,
                                    evidence=(),
                                )
                            check()
                with self._lock:
                    self._adopt()
            self._check(cancellation, deadline)
            with self._lock:
                self._publication = {"status": "PENDING", "operation_id": None}
                report = {
                    "action_id": action_id,
                    "pending_completion_log": True,
                    "qualification": self._summary,
                    "stage_states": self._stages,
                    "discovery": (
                        self.inbox.view()
                        if action_id == "physical_source_isolation_files_discover"
                        else None
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
                "SOURCE_QUALIFICATION_RESULT_CHANGED",
                "Exact complete source result must be retained before publication.",
            )

    def publication_completed(self, operation_id: str) -> None:
        with self._lock:
            if (
                self._publication["status"] == "PENDING"
                and self._pending_result is not None
            ):
                self._publication = {"status": "CURRENT", "operation_id": operation_id}
                self._discovery_published = self.inbox.view()["status"] == "READY"
                self._pending_result = None

    def retained_diagnostics(self) -> dict[str, Any] | None:
        """Metadata only; private originals stay in their original guarded store.

        Flatten each receipt and its nested reports independently so the ordinary
        exporter never truncates deep ownership lineage into a misleading PASS.
        """
        with self._lock:
            workflow = self.setup.session.retained_source_workflow() or self._workflow
            cycles = deepcopy((workflow or {}).get("qualification_cycles", []))
            if not cycles and self._attempt is None:
                return None
            documents: dict[str, Any] = {}
            document_keys: dict[bytes, str] = {}

            def retain_document(document, key):
                # Deduplicate exact canonical bytes, not merely claimed hashes.
                # Successful attempts commonly repeat the just-audited cycle;
                # each role still points to its complete original subject.
                wire = canonical(document)
                if wire in document_keys:
                    return document_keys[wire]
                document_keys[wire] = key
                for nested in ("software_receipt", "ownership_report"):
                    if nested in document:
                        document[nested + "_document_key"] = retain_document(
                            document.pop(nested), key + "_" + nested
                        )
                documents[key] = document
                return key

            def flatten(record, key):
                if "document" not in record:
                    return
                record["document_key"] = retain_document(record.pop("document"), key)

            for index, cycle in enumerate(cycles):
                for role in _CODECS:
                    if cycle[role] is not None:
                        flatten(cycle[role], f"qualification_{index + 1}_{role}")
            attempt = deepcopy(self._attempt)
            if attempt:
                for nested in ("software_receipt", "ownership_report"):
                    if nested in attempt:
                        attempt[nested + "_document_key"] = retain_document(
                            attempt.pop(nested), "attempt_" + nested
                        )
                for role, record in attempt["records"].items():
                    flatten(record, "attempt_" + role)
            return {
                "schema": "rocell.wizard_source_qualification_diagnostics.v1",
                "original_context": self._context(),
                "publication": deepcopy(self._publication),
                "qualification_cycles": cycles,
                "attempt": attempt,
                "stage_states": deepcopy(self._stages),
                **documents,
                "meaning": MEANING,
                **_FLAGS,
            }
