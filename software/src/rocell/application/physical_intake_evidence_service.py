"""Application-owned passive intake, original bytes and procedural review.

This service is deliberately separate from acquisition. It can append to the
original source-stage history, but cannot accept that stage or open a device.
The setup service owns storage leases; Arrival owns tickets, Stop and durable
completion logging. Current UI publication requires both owners to complete.
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
from .physical_intake_inbox import PhysicalIntakeInbox, IntakeInboxFile
from .physical_intake_notebook import PhysicalIntakeNotebook
from .physical_intake_submission import (
    ASSESSMENT_LABEL,
    ORIGINAL_LABEL,
    REVIEW_LABEL,
    SUBMISSION_LABEL,
    MAX_COLLECTIONS,
    MAX_RECORD_BYTES,
    RECORD_IDS,
    IntakeAttachment,
    IntakeRowAttachment,
    PhysicalIntakeSubmission,
    PhysicalIntakeAssessment,
    PhysicalIntakeReview,
    build_physical_intake_submission,
    assess_physical_intake_submission,
    review_physical_intake_submission,
)
from .physical_onboarding import PhysicalOnboardingStage, _parse_evidence_reference
from .physical_onboarding_v2 import V2StageState
from .wizard_actions import WizardError
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.native_camera_protocol import canonical, digest

ACTIONS = frozenset(
    {
        "physical_intake_files_discover",
        "physical_intake_submit",
        "physical_intake_review",
        "physical_intake_export_originals",
    }
)
SCHEMA = "rocell.wizard_physical_intake_evidence.v1"
MEANING = (
    "Original retained attachments and exact-subject procedural review only. "
    "UNKNOWN stays unknown; byte integrity is not measurement truth. The original "
    "source verdict remains BLOCKED, and no camera, arm or motion is enabled."
)
_STAGE = PhysicalOnboardingStage.WORKSPACE_SOURCES
_CODECS: dict[
    str,
    Callable[
        [bytes],
        PhysicalIntakeSubmission | PhysicalIntakeAssessment | PhysicalIntakeReview,
    ],
] = {
    "submission": PhysicalIntakeSubmission,
    "assessment": PhysicalIntakeAssessment,
    "review": PhysicalIntakeReview,
}


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise WizardError(code, message)


class PhysicalIntakeEvidenceService:
    """Cached views are inert; all filesystem work is an explicit action."""

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
        self._empty_discovery = self.inbox.view()
        self._lock, self._operation_lock = RLock(), Lock()
        self._workflow: dict[str, Any] | None = None
        self._publication = {"status": "NOT_PUBLISHED", "operation_id": None}
        self._attempt: dict[str, Any] | None = None
        self._export_receipt: dict[str, Any] | None = None
        self._discovery_published = False

    def observe_setup(self) -> None:
        """Adopt only an explicitly audited original, never an exported import."""
        with self._lock:
            if self.setup.view()["publication"]["status"] != "CURRENT":
                self.invalidate()
                return
            self._workflow = self.setup.original_source_workflow()
            if (self._workflow or {}).get("qualification_cycles"):
                self.invalidate()
                return
            if self._collections():
                self._publication = deepcopy(self.setup.view()["publication"])

    def _collections(self) -> list[dict[str, Any]]:
        return (self._workflow or {}).get("intake_collections", [])

    def _context(self) -> dict[str, Any] | None:
        workflow = self._workflow
        if not workflow or not workflow.get("prerequisites"):
            return None
        binding = workflow["prerequisites"]["document"]["binding"]
        return {
            "source_sha256": self.source_sha256,
            "session_id": binding["session_id"],
            "cell_id": workflow["binding"]["cell_id"],
            "origin_launch_id": binding["launch_session_id"],
            "header_sha256": workflow["session_header_sha256"],
            "prerequisites_sha256": workflow["prerequisites"]["evidence_sha256"],
        }

    def view(self) -> dict[str, Any]:
        with self._lock:
            pending = self._publication["status"] == "PENDING"
            collections = self._collections()
            latest = collections[-1] if collections else None
            collection = None
            if latest is not None and not pending:
                collection = {
                    "collection_id": latest["collection_id"],
                    "state": latest["state"],
                }
                for role, codec in _CODECS.items():
                    record = latest[role]
                    collection[role] = (
                        None
                        if record is None
                        else codec(canonical(record["document"])).safe_summary()
                    )
            current = (
                self._publication["status"] == "CURRENT"
                and self.setup.view()["publication"]["status"] == "CURRENT"
            )
            status = "NOT_STARTED"
            if latest is not None:
                status = {
                    "REVIEWED_BLOCKED": "REVIEWED",
                    "REVIEW_PENDING": "SUBMITTED_REVIEW_PENDING",
                }.get(latest["state"], "INCOMPLETE_HELD")
                if not current:
                    status = "HISTORICAL_HELD"
            elif current and self._discovery_published:
                status = "DISCOVERED"
            return deepcopy(
                {
                    "schema": SCHEMA,
                    "source_sha256": self.source_sha256,
                    "launch_session_id": self.launch_id,
                    "original_context": self._context(),
                    "publication": self._publication,
                    "status": status,
                    "discovery": (
                        self.inbox.view()
                        if self._discovery_published and not pending
                        else self._empty_discovery
                    ),
                    "collection": collection,
                    "collection_count": len(collections),
                    "physical_authority": False,
                    "hardware_qualified": False,
                    "meaning": MEANING,
                }
            )

    def retained_diagnostics(self) -> dict[str, Any] | None:
        """Full metadata in a dedicated export, not raw private attachment bytes.

        Flatten each document to keep notebook requirements below the shared
        diagnostic nesting limit. Hashes describe originals, not redacted text.
        """
        with self._lock:
            # A late Stop/audit failure can leave a fully read-back new subject
            # in the original reader while the adopted view stays at its
            # predecessor. Export that reader cache as history, never readiness.
            workflow = self.setup.session.retained_source_workflow() or self._workflow
            collections = deepcopy((workflow or {}).get("intake_collections", []))
            if (
                not collections
                and self._attempt is None
                and self._export_receipt is None
            ):
                return None
            documents = {}
            for index, item in enumerate(collections):
                for role in _CODECS:
                    if item[role] is not None:
                        key = f"collection_{index + 1}_{role}"
                        documents[key] = item[role].pop("document")
                        item[role]["document_key"] = key
            attempt = deepcopy(self._attempt)
            if attempt:
                for role, record in attempt.get("records", {}).items():
                    if "document" in record:
                        key = "attempt_" + role
                        documents[key] = record.pop("document")
                        record["document_key"] = key
            return {
                "schema": "rocell.wizard_physical_intake_evidence_diagnostics.v1",
                "original_context": self._context(),
                "publication": deepcopy(self._publication),
                "collections": collections,
                "attempt": attempt,
                "private_original_export": deepcopy(self._export_receipt),
                **documents,
                "physical_authority": False,
                "hardware_qualified": False,
                "meaning": MEANING,
            }

    def invalidate(self) -> None:
        with self._lock:
            self._publication = {"status": "HISTORICAL_HELD", "operation_id": None}

    def publication_completed(self, operation_id: str) -> None:
        with self._lock:
            if self._publication["status"] == "PENDING":
                self._publication = {"status": "CURRENT", "operation_id": operation_id}
                self._discovery_published = self.inbox.view()["status"] == "READY"

    def context_sha256(self, notebook: PhysicalIntakeNotebook | None) -> str:
        return digest(
            canonical(
                {
                    "source_sha256": self.source_sha256,
                    "launch_id": self.launch_id,
                    "setup": self.setup.original_source_workflow(),
                    "setup_publication": self.setup.view()["publication"],
                    "notebook_sha256": None if notebook is None else notebook.sha256,
                    "discovery": self.inbox.view(),
                    "attempt": self._attempt,
                }
            )
        )

    def submission_fields(
        self, notebook: PhysicalIntakeNotebook | None
    ) -> tuple[dict[str, Any], ...]:
        # Each row chooses one existing opaque token. There is deliberately no
        # HTTP upload, arbitrary filesystem path or unbounded multi-selection.
        choices = [{"value": "", "label": "No attachment (UNKNOWN only)"}]
        if self._publication["status"] == "CURRENT":
            choices += self.inbox.choices()
        return tuple(
            {
                "name": "attachment_" + record_id,
                "label": record_id + " original attachment",
                "type": "select",
                "required": False,
                "default": "",
                "options": deepcopy(choices),
            }
            for record_id in RECORD_IDS
        )

    def blocked_reason(
        self, action_id: str, notebook: PhysicalIntakeNotebook | None
    ) -> str | None:
        if action_id not in ACTIONS or self.setup.mode != "physical":
            return "Passive original intake requires the physical file-only workspace."
        setup = self.setup.view()
        workflow = self.setup.original_source_workflow()
        if (
            setup["publication"]["status"] != "CURRENT"
            or not workflow
            or not workflow.get("review")
        ):
            return "Verify the original requirements and complete the original source review first."
        collections = workflow.get("intake_collections", [])
        if workflow.get("qualification_cycles"):
            return "Source reassessment has begun. Legacy intake remains historical; use the source reassessment actions."
        latest = collections[-1] if collections else None
        if action_id == "physical_intake_files_discover":
            return None
        if action_id == "physical_intake_submit":
            if latest and latest["state"] != "REVIEWED_BLOCKED":
                return "Review the existing submitted collection; incomplete retention requires inspection, not replay."
            if len(collections) >= MAX_COLLECTIONS:
                return "The eight-collection budget is exhausted; export and review the original history."
            if notebook is None or any(
                row["observation"] is None for row in notebook.to_dict()["rows"]
            ):
                return "Explicitly complete all 16 draft observations or UNKNOWN reasons before submitting."
            if (
                notebook.to_dict()["binding"]["prerequisites_sha256"]
                != workflow["prerequisites"]["evidence_sha256"]
            ):
                return "The draft belongs to other original requirements."
            if (
                latest
                and latest["submission"]["document"]["binding"]["notebook_sha256"]
                == notebook.sha256
            ):
                return "Revise at least one draft entry before submitting a successor; no unchanged replay."
        elif action_id == "physical_intake_review":
            if latest is None or latest["state"] != "REVIEW_PENDING":
                return "An exact original submission must be awaiting review."
        elif latest is None or latest["state"] not in {
            "REVIEW_PENDING",
            "REVIEWED_BLOCKED",
        }:
            return "Submit and read back an original collection before exporting its private bytes."
        return None

    def _check(self, cancellation: Event, deadline_ns: int) -> None:
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline_ns,
            "INTAKE_INTERRUPTED",
            "Stopped or expired; inspect retained records without replay.",
        )
        _require(
            source_fingerprint(self.workspace) == self.source_sha256,
            "INTAKE_SOURCE_CHANGED",
            "Source changed; original records are historical only.",
        )
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline_ns,
            "INTAKE_INTERRUPTED",
            "Stopped during verification; no next mutation admitted.",
        )

    @staticmethod
    def _sorted_refs(references):
        return tuple(sorted(references, key=lambda item: item.evidence_id))

    def _retain(
        self, transaction, payload: bytes, label: str, media_type: str, role: str
    ):
        # Preserve generated metadata before an uncertain publication. The raw
        # attachment itself remains outside every JSON cache, even on failure.
        with self._lock:
            assert self._attempt is not None
            record: dict[str, Any] = {
                "reference": None,
                "label": label,
                "retention": "COLLECTED_NOT_M1_RETAINED",
                "evidence_sha256": digest(payload),
            }
            if role in _CODECS:
                record["document"] = _CODECS[role](payload).to_dict()
            self._attempt["records"][role] = record
        reference = transaction.store_evidence(
            _STAGE,
            payload,
            label=label,
            media_type=media_type,
            captured_at_ns=time_ns(),
            expected_head_sha256=transaction.snapshot().head.head_sha256,
        )
        with self._lock:
            assert self._attempt is not None
            self._attempt["records"][role].update(
                reference=reference.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
            )
        _require(
            transaction.read_stage_evidence(reference) == payload,
            "INTAKE_READBACK_CHANGED",
            "The original retained bytes differ.",
        )
        with self._lock:
            record = self._attempt["records"][role]
            record["retention"] = "M1_FULL_BYTES_READ_BACK"
        return reference

    def _submit(
        self, transaction, prerequisites, workflow, notebook, values, files, check
    ):
        _require(
            type(notebook) is PhysicalIntakeNotebook,
            "INTAKE_DRAFT_REQUIRED",
            "Complete an original draft first.",
        )
        assert notebook is not None
        collections = workflow.get("intake_collections", [])
        previous = collections[-1] if collections else None
        predecessor = (
            None
            if previous is None
            else PhysicalIntakeSubmission(canonical(previous["submission"]["document"]))
        )
        # Reuse a previously retained byte-identical original only when all
        # semantic descriptors match; re-read its M1 package under these leases.
        reusable = {}
        for collection in collections:
            if collection["submission"]:
                for item in collection["submission"]["document"]["attachments"]:
                    ref = _parse_evidence_reference(item["reference"])
                    reusable[
                        (item["basename"], item["media_type"], ref.payload_sha256)
                    ] = ref
        new_files = [
            f
            for f in files
            if (f.basename, f.media_type, f.payload_sha256) not in reusable
        ]
        snapshot = transaction.snapshot()
        _require(
            len(snapshot.evidence) + len(new_files) + 3 <= 32
            and sum(ref.payload_bytes for ref in snapshot.evidence)
            + sum(len(f.payload) for f in new_files)
            + 3 * MAX_RECORD_BYTES
            <= 4 * 1024 * 1024,
            "INTAKE_ORIGINAL_STORE_BUDGET",
            "The original 32-reference / 4 MiB budget cannot retain this collection and its review. Use smaller original attachments; nothing was appended.",
        )
        collection_id = "intake-" + uuid4().hex
        suffix = collection_id.removeprefix("intake-").upper()
        with self._lock:
            self._attempt = {"collection_id": collection_id, "records": {}}
        start = workflow if previous is None else previous
        subjects = (
            ("receipt", "assessment", "review")
            if previous is None
            else ("submission", "assessment", "review")
        )
        check()
        transaction.commit_stage_state(
            _STAGE,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=time_ns(),
            detail_code="PHYSICAL_INTAKE_STARTED_" + suffix,
            expected_head_sha256=snapshot.head.head_sha256,
            evidence=self._sorted_refs(
                _parse_evidence_reference(start[role]["reference"]) for role in subjects
            ),
        )
        by_choice, attachments = {}, []
        new_index = 0
        for item in files:
            check()
            reference = reusable.get(
                (item.basename, item.media_type, item.payload_sha256)
            )
            if reference is None:
                reference = self._retain(
                    transaction,
                    item.payload,
                    f"{ORIGINAL_LABEL}:{collection_id}:{new_index:02d}",
                    item.media_type,
                    f"original_{new_index:02d}",
                )
                new_index += 1
            else:
                _require(
                    transaction.read_stage_evidence(reference) == item.payload,
                    "INTAKE_REUSED_ORIGINAL_CHANGED",
                    "The previously retained original differs.",
                )
            by_choice[item.choice_id] = reference
            attachments.append(
                IntakeAttachment(reference, item.basename, item.media_type)
            )
        links = tuple(
            IntakeRowAttachment(
                record_id, by_choice[values["attachment_" + record_id]].evidence_id
            )
            for record_id in RECORD_IDS
            if values.get("attachment_" + record_id)
        )
        submission = build_physical_intake_submission(
            prerequisites,
            notebook,
            cell_id=self.setup.session.descriptor()["cell_id"],
            header_sha256=workflow["session_header_sha256"],
            collection_id=collection_id,
            operator_id=values["operator_id"],
            submitted_at_ns=time_ns(),
            attachments=tuple(
                sorted(attachments, key=lambda item: item.reference.evidence_id)
            ),
            row_attachments=links,
            evidence_inventory=transaction.snapshot().evidence,
            predecessor=predecessor,
        )
        check()
        refs = [item.reference for item in attachments]
        for role, label, artifact in (
            ("submission", SUBMISSION_LABEL, submission),
            (
                "assessment",
                ASSESSMENT_LABEL,
                assess_physical_intake_submission(submission),
            ),
        ):
            check()
            refs.append(
                self._retain(
                    transaction,
                    artifact.payload,
                    f"{label}:{collection_id}",
                    "application/json",
                    role,
                )
            )
        check()
        transaction.commit_stage_state(
            _STAGE,
            V2StageState.REVIEW_PENDING,
            occurred_at_ns=time_ns(),
            detail_code="PHYSICAL_INTAKE_SUBMITTED_" + suffix,
            expected_head_sha256=transaction.snapshot().head.head_sha256,
            evidence=self._sorted_refs(refs),
        )

    def perform(
        self,
        action_id: str,
        *,
        expected_context_sha256: str,
        notebook: PhysicalIntakeNotebook | None,
        values: dict[str, Any],
        cancellation: Event,
        progress: Callable[[str], None],
        export_parent: Path,
    ) -> dict[str, Any]:
        _require(
            self._operation_lock.acquire(blocking=False),
            "INTAKE_BUSY",
            "An intake action is active.",
        )
        deadline = monotonic_ns() + 120_000_000_000
        mutated_setup = False
        try:
            reason = self.blocked_reason(action_id, notebook)
            _require(reason is None, "INTAKE_ACTION_BLOCKED", reason or "")
            _require(
                action_id == "physical_intake_files_discover"
                or values.get("file_only") is True,
                "INTAKE_FILE_ONLY_REQUIRED",
                "Explicitly acknowledge the file-only operation.",
            )
            _require(
                self.context_sha256(notebook) == expected_context_sha256,
                "INTAKE_CONTEXT_CHANGED",
                "The original subjects or file choices changed; preview again.",
            )
            self._check(cancellation, deadline)
            self.invalidate()
            if action_id == "physical_intake_export_originals":
                _require(
                    values.get("include_private_originals") is True,
                    "INTAKE_PRIVATE_EXPORT_CONSENT_REQUIRED",
                    "Explicitly approve copying private, unredacted original files.",
                )
                # Reuse the assigned-folder validation/creation policy. This
                # explicit export must also work before the first generic log
                # export; constructor/GET never creates the export directory.
                from .wizard_diagnostic_export import WizardDiagnosticExporter

                WizardDiagnosticExporter(export_parent).prepare(create=True)
                self._check(cancellation, deadline)
            if action_id == "physical_intake_files_discover":
                self._discovery_published = False
                progress(
                    "Discovering only bounded regular files in the assigned intake inbox."
                )
                self.inbox.discover(cancellation=cancellation, deadline_ns=deadline)
            else:
                chosen: tuple[str, ...] = ()
                if action_id == "physical_intake_submit":
                    _require(
                        type(values.get("operator_id")) is str
                        and re.fullmatch(
                            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", values["operator_id"]
                        )
                        is not None,
                        "INTAKE_OPERATOR_INVALID",
                        "Use a portable operator label of 1–64 characters.",
                    )
                    assert notebook is not None
                    # Validate every row and token before any original stage mutation.
                    notebook = PhysicalIntakeNotebook.from_payload(
                        notebook.payload,
                        prerequisites=self.setup.current_prerequisite_artifact(),
                        expected_sha256=notebook.sha256,
                    )
                    tokens = []
                    for row in notebook.to_dict()["rows"]:
                        token = values.get("attachment_" + row["record_id"], "")
                        _require(
                            type(token) is str,
                            "INTAKE_CHOICE_INVALID",
                            "Choose an explicit discovered original.",
                        )
                        _require(
                            bool(token) or row["observation"]["status"] == "UNKNOWN",
                            "INTAKE_OBSERVED_ATTACHMENT_REQUIRED",
                            "Each OBSERVED row requires an original attachment; notes alone are not evidence.",
                        )
                        if token:
                            self.inbox.preview(token)
                            tokens.append(token)
                    chosen = tuple(dict.fromkeys(tokens))
                # Input handles remain pinned while original retention occurs.
                # Empty selection supports all-UNKNOWN submissions and review
                # after restart without depending on the former inbox files.
                with self.inbox.selected_files(
                    chosen, cancellation=cancellation, deadline_ns=deadline
                ) as files:
                    mutated_setup = True
                    with self.setup.intake_transaction(
                        cancellation=cancellation,
                        progress=progress,
                        deadline_ns=deadline,
                    ) as (prerequisites, workflow):
                        verification = self.setup.session.view()["verification"]
                        with self.setup.session.stage_transaction(
                            expected_challenge_sha256=verification["challenge_sha256"]
                        ) as transaction:
                            snapshot = transaction.snapshot()
                            _require(
                                snapshot.head.head_sha256
                                == workflow["session_head_sha256"]
                                and snapshot.next_action.stage is _STAGE,
                                "INTAKE_STAGE_CHANGED",
                                "The original stage/head changed; no replay.",
                            )
                            check = lambda: self._check(cancellation, deadline)
                            if action_id == "physical_intake_submit":
                                _require(
                                    snapshot.next_action.stage_state
                                    is V2StageState.BLOCKED,
                                    "INTAKE_STAGE_CHANGED",
                                    "The original source stage must remain blocked.",
                                )
                                self._submit(
                                    transaction,
                                    prerequisites,
                                    workflow,
                                    notebook,
                                    values,
                                    files,
                                    check,
                                )
                            else:
                                latest = workflow["intake_collections"][-1]
                                submission = PhysicalIntakeSubmission(
                                    canonical(latest["submission"]["document"])
                                )
                                assessment = PhysicalIntakeAssessment(
                                    canonical(latest["assessment"]["document"])
                                )
                                # Re-read every exact subject, including bytes, from M1.
                                for role in ("submission", "assessment"):
                                    reference = _parse_evidence_reference(
                                        latest[role]["reference"]
                                    )
                                    _require(
                                        transaction.read_stage_evidence(reference)
                                        == canonical(latest[role]["document"]),
                                        "INTAKE_SUBJECT_CHANGED",
                                        "The original review subject differs.",
                                    )
                                originals = []
                                for item in submission.to_dict()["attachments"]:
                                    check()
                                    reference = _parse_evidence_reference(
                                        item["reference"]
                                    )
                                    originals.append(
                                        (
                                            reference,
                                            item["basename"],
                                            item["media_type"],
                                            transaction.read_stage_evidence(reference),
                                        )
                                    )
                                if action_id == "physical_intake_review":
                                    review = review_physical_intake_submission(
                                        submission,
                                        assessment,
                                        reviewer_id=values["reviewer_id"],
                                        review_launch_id=self.launch_id,
                                        reviewed_at_ns=time_ns(),
                                        decision=values["decision"],
                                    )
                                    with self._lock:
                                        self._attempt = {
                                            "collection_id": latest["collection_id"],
                                            "records": {},
                                        }
                                    check()
                                    reference = self._retain(
                                        transaction,
                                        review.payload,
                                        REVIEW_LABEL + ":" + latest["collection_id"],
                                        "application/json",
                                        "review",
                                    )
                                    refs = (
                                        [row[0] for row in originals]
                                        + [reference]
                                        + [
                                            _parse_evidence_reference(
                                                latest[role]["reference"]
                                            )
                                            for role in ("submission", "assessment")
                                        ]
                                    )
                                    check()
                                    transaction.commit_stage_state(
                                        _STAGE,
                                        V2StageState.BLOCKED,
                                        occurred_at_ns=time_ns(),
                                        detail_code="PHYSICAL_INTAKE_REVIEWED_"
                                        + latest["collection_id"]
                                        .removeprefix("intake-")
                                        .upper(),
                                        expected_head_sha256=transaction.snapshot().head.head_sha256,
                                        evidence=self._sorted_refs(refs),
                                    )
                                else:
                                    from .physical_intake_original_export import (
                                        export_physical_intake_originals,
                                    )

                                    try:
                                        receipt = export_physical_intake_originals(
                                            export_parent,
                                            submission=submission,
                                            originals=tuple(originals),
                                            include_private_originals=values.get(
                                                "include_private_originals"
                                            )
                                            is True,
                                            cancellation=cancellation,
                                            deadline_ns=deadline,
                                        )
                                    except Exception as error:
                                        with self._lock:
                                            self._export_receipt = deepcopy(
                                                getattr(error, "receipt", None)
                                            )
                                        raise
                                    with self._lock:
                                        self._export_receipt = deepcopy(receipt)
                            check()
                with self._lock:
                    self._workflow = self.setup.original_source_workflow()
            self._check(cancellation, deadline)
            with self._lock:
                self._publication = {"status": "PENDING", "operation_id": None}
                report = {
                    "action_id": action_id,
                    "pending_completion_log": True,
                    "collection_count": len(self._collections()),
                    "discovery": (
                        self.inbox.view()
                        if action_id == "physical_intake_files_discover"
                        else None
                    ),
                    "private_original_export": deepcopy(self._export_receipt),
                    "meaning": MEANING,
                }
                if self._collections():
                    last = self._collections()[-1]
                    report["collection_id"] = last["collection_id"]
                    report["state"] = last["state"]
                    for role, codec in _CODECS.items():
                        record = last[role]
                        report[role] = (
                            None
                            if record is None
                            else codec(canonical(record["document"])).safe_summary()
                        )
            return {
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
        except BaseException:
            self.invalidate()
            if mutated_setup:
                self.setup.invalidate()
            raise
        finally:
            self._operation_lock.release()
