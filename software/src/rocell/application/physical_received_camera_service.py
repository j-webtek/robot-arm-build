"""Received-unit onboarding: explicit drafts, original evidence and exact review.

This owner has no camera, serial or motion provider. The setup service owns
original-store leases and replay/audit; Arrival owns consent tickets, Stop and
durable completion logging. Only their combined successful publication exposes
new work as current. A receipt PASS is not installed or native qualification.
"""

from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from threading import Event, Lock, RLock
from time import monotonic_ns, time_ns
from typing import Any, Callable
from uuid import uuid4
import re

from .commissioning_camera_persistence import physical_camera_source_binding
from .physical_camera_setup_service import PhysicalCameraSetupService
from .physical_intake_inbox import PhysicalIntakeInbox
from .physical_intake_notebook import PhysicalIntakeNotebook, MAX_NOTEBOOK_BYTES
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_receipts import (
    BoundEvidence,
    ReceiptBinding,
    CameraReceiptInspection,
    InspectionCondition,
    _text as receipt_text,
)
from .physical_onboarding_v2 import V2StageState
from .physical_received_camera_fields import received_camera_fields
from .physical_received_camera_submission import (
    ReceivedCameraSubmission,
    ReceivedCameraSubmissionAssessment,
    ReceivedCameraSubmissionReview,
    ReceivedCameraAttachment,
    ReceivedCameraRowLink,
    build_received_camera_submission,
    assess_received_camera_submission,
    review_received_camera_submission,
    RECORD_IDS,
    MAX_COLLECTIONS,
    MAX_STAGE_BYTES,
    MAX_STAGE_REFERENCES,
    MAX_ATTACHMENTS,
    MAX_SELECTED_BYTES,
    MAX_SUBMISSION_BYTES,
    MAX_ASSESSMENT_BYTES,
    MAX_REVIEW_BYTES,
)
from .wizard_actions import WizardError
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.native_camera_protocol import canonical, digest

PREFIX = "physical_received_camera_"
DISCOVER, START, RECORD, SUBMIT, REVIEW, EXPORT = (
    PREFIX + suffix
    for suffix in (
        "files_discover",
        "draft_start",
        "draft_record",
        "submit",
        "review",
        "export",
    )
)
IDENTITY = "physical_camera_identity_begin"
ACTIONS = frozenset((DISCOVER, START, RECORD, SUBMIT, REVIEW, IDENTITY, EXPORT))
SCHEMA = "rocell.wizard_received_camera.v1"
MEANING = (
    "Original received-camera records and procedural review only. PASS means "
    "receipt completeness, not installed geometry, flatness, focus, USB identity "
    "or camera/arm release. No device access, power, motion or contact occurs."
)
_FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    native_release_allowed=False,
    device_io_performed=False,
)
_STAGE = STAGE_ORDER[2]
_CODECS = dict(
    submission=ReceivedCameraSubmission,
    assessment=ReceivedCameraSubmissionAssessment,
    review=ReceivedCameraSubmissionReview,
)
_CAPS = dict(
    notebook=MAX_NOTEBOOK_BYTES,
    submission=MAX_SUBMISSION_BYTES,
    assessment=MAX_ASSESSMENT_BYTES,
    review=MAX_REVIEW_BYTES,
)


def _require(condition, code, message):
    if not condition:
        raise WizardError(code, message)


def _actor(value):
    _require(
        type(value) is str
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is not None,
        "RECEIVED_CAMERA_ACTOR_INVALID",
        "Use a portable 1–64 character operator/reviewer label.",
    )


def _refs(values):
    return tuple(sorted(values, key=lambda ref: ref.evidence_id))


class PhysicalReceivedCameraService:
    """Cached, inert views with explicit single-use original mutations."""

    def __init__(self, setup: PhysicalCameraSetupService):
        if type(setup) is not PhysicalCameraSetupService:
            raise TypeError("Exact application-owned setup required")
        self.setup = setup
        self.workspace, self.source_sha256, self.launch_id = (
            setup.workspace,
            setup.source_sha256,
            setup.launch_id,
        )
        self.inbox = PhysicalIntakeInbox(
            self.workspace, launch_id=self.launch_id, source_sha256=self.source_sha256
        )
        self._empty_discovery = self.inbox.view()
        self._lock, self._operation_lock = RLock(), Lock()
        self._workflow: dict[str, Any] | None = None
        self._collection: dict[str, Any] | None = None
        self._stages: dict[str, str] | None = None
        self._draft: PhysicalIntakeNotebook | None = None
        self._draft_origin: str | None = None
        self._draft_predecessor: str | None = None
        self._publication = dict(status="NOT_PUBLISHED", operation_id=None)
        self._pending_result: bytes | None = None
        self._pending_action: str | None = None
        self._pending_draft: PhysicalIntakeNotebook | None = None
        self._pending_origin: str | None = None
        self._pending_draft_predecessor: str | None = None
        self._failed_draft: PhysicalIntakeNotebook | None = None
        self._failed_origin: str | None = None
        self._failed_draft_exported_sha256: str | None = None
        self._attempt: dict[str, Any] | None = None
        self._attempted: set[str] = set()
        self._discovery_published = False
        self._export_receipt: dict[str, Any] | None = None
        self._export_publication: dict[str, Any] | None = None

    def _cycles(self):
        return (self._workflow or {}).get("received_camera_cycles", [])

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
        prior = self._context()
        self._workflow = self.setup.original_source_workflow()
        if prior is not None and self._context() != prior:
            self._draft, self._draft_origin = None, None
            self._draft_predecessor = None
            self._discovery_published = False
        stages = self.setup.session.view().get("stages")
        self._stages = (
            None
            if stages is None
            else {
                stage.value: stages[index]["state"]
                for index, stage in enumerate(STAGE_ORDER[:4])
            }
        )
        cycles = self._cycles()
        self._collection = None
        if cycles:
            latest = cycles[-1]
            if prerequisites is None:
                prerequisites = self.setup.current_prerequisite_artifact()
            self._collection = dict(
                receipt_id=latest["receipt_id"],
                sequence=latest["sequence"],
                state=latest["state"],
                notebook=None,
                inspection=None,
            )
            if latest["notebook"] is not None:
                self._collection["notebook"] = {
                    key: deepcopy(latest["notebook"][key])
                    for key in ("document", "evidence_sha256", "reference")
                }
            for role, codec in _CODECS.items():
                item = latest[role]
                self._collection[role] = (
                    None
                    if item is None
                    else codec(
                        canonical(item["document"]), prerequisites
                    ).safe_summary()
                )
            if latest["submission"] is not None:
                self._collection["inspection"] = deepcopy(
                    latest["submission"]["document"]["inspection"]
                )
            if (
                self._draft is not None
                and latest["notebook"] is not None
                and latest["receipt_id"] != self._draft_predecessor
                and latest["notebook"]["evidence_sha256"] == self._draft.sha256
            ):
                # Original readback, including recovery after a lost completion
                # log, owns this exact submitted notebook now. Do not let its
                # editable copy mask REVIEW_PENDING or prevent explicit revision.
                # The parent ID protects a newly requested blank successor whose
                # bytes happen to equal the preceding blank notebook.
                self._draft, self._draft_origin, self._draft_predecessor = (
                    None,
                    None,
                    None,
                )

    def observe_setup(self):
        """Read no files here; adopt only already logged original readback."""
        with self._lock:
            if self._pending_draft is not None:
                # Refresh is not a substitute for the candidate's completion
                # log. Preserve it as failed history before adopting originals.
                self.invalidate()
            if self.setup.view()["publication"]["status"] != "CURRENT":
                self.invalidate()
                return
            self._adopt()
            self._publication = deepcopy(self.setup.view()["publication"])
            if (self._workflow or {}).get("schema") in {
                "rocell.physical_camera_source_workflow_readback.v7",
                "rocell.physical_camera_source_workflow_readback.v8",
                "rocell.physical_camera_source_workflow_readback.v9",
                "rocell.physical_camera_source_workflow_readback.v10",
                "rocell.physical_camera_source_workflow_readback.v11",
                "rocell.physical_camera_source_workflow_readback.v12",
                # Future successor: historical display only, not reader acceptance.
                "rocell.physical_camera_source_workflow_readback.v13",
            }:
                # Stage 3 remains reviewed original history. The new identity
                # owner presents current stage-4 progress, not this old panel.
                self._publication = dict(status="HISTORICAL_HELD", operation_id=None)
            self._pending_result, self._pending_action = None, None
            # An unlogged candidate is never promoted by a later refresh.
            self._pending_draft, self._pending_origin = None, None

    def invalidate(self):
        with self._lock:
            if self._pending_draft is not None:
                self._failed_draft, self._failed_origin = (
                    self._pending_draft,
                    self._pending_origin,
                )
                self._pending_draft, self._pending_origin = None, None
            self._publication = dict(status="HISTORICAL_HELD", operation_id=None)
            self._pending_result, self._pending_action = None, None
            # Preserve failed candidate in diagnostics, not in the editable UI.
            self._discovery_published = False

    def _current(self):
        return (
            self._publication["status"] == "CURRENT"
            and self.setup.view()["publication"]["status"] == "CURRENT"
        )

    def view(self):
        with self._lock:
            publication = deepcopy(self._publication)
            if publication["status"] == "CURRENT" and not self._current():
                publication = dict(status="HISTORICAL_HELD", operation_id=None)
            current, pending = (
                publication["status"] == "CURRENT",
                publication["status"] == "PENDING",
            )
            status = "NOT_STARTED"
            if self._collection is not None:
                state = self._collection["state"]
                status = (
                    state
                    if state in {"REVIEW_PENDING", "REVIEWED_PASS", "REVIEWED_BLOCKED"}
                    else "INCOMPLETE_HELD"
                )
            if self._draft is not None:
                status = "DRAFT"
            elif self._collection is None and self._discovery_published:
                status = "DISCOVERED"
            if not current and (
                self._collection is not None
                or self._draft is not None
                or self._attempt is not None
            ):
                status = "HISTORICAL_HELD"
            choices = (
                self.inbox.choices() if current and self._discovery_published else []
            )
            entry = (self._workflow or {}).get("camera_identity_request")
            next_action = None
            if current:
                preferred = (
                    (REVIEW, IDENTITY, START)
                    if self._draft is None
                    else (
                        (
                            (SUBMIT, RECORD)
                            if self._discovery_published
                            else (DISCOVER, SUBMIT, RECORD)
                        )
                        if self._draft.to_dict()["coverage"]["unrecorded"] == 0
                        else (RECORD, SUBMIT, DISCOVER)
                    )
                )
                if (
                    self._failed_draft is not None
                    and self._failed_draft.sha256 != self._failed_draft_exported_sha256
                ):
                    preferred = (EXPORT,)
                next_action = next(
                    (
                        action
                        for action in preferred
                        if self.blocked_reason(action) is None
                    ),
                    None,
                )
            return deepcopy(
                dict(
                    schema=SCHEMA,
                    source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                    original_context=self._context(),
                    publication=publication,
                    status=status,
                    stage_states=self._stages,
                    draft=(
                        None if pending or self._draft is None else self._draft.view()
                    ),
                    draft_origin_notebook_sha256=(
                        None if pending else self._draft_origin
                    ),
                    collection=None if pending else self._collection,
                    inbox=dict(
                        discovery=(
                            self.inbox.view()
                            if self._discovery_published and not pending
                            else self._empty_discovery
                        ),
                        choices=choices,
                    ),
                    identity_entry=(
                        None if pending or entry is None else entry["event_sha256"]
                    ),
                    metadata_export=self._export_receipt,
                    next_action=next_action,
                    meaning=MEANING,
                    **_FLAGS,
                )
            )

    def fields(self, action):
        with self._lock:
            return (
                ()
                if action not in ACTIONS
                else received_camera_fields(
                    action,
                    notebook=self._draft,
                    choices=(
                        self.inbox.choices()
                        if self._current() and self._discovery_published
                        else []
                    ),
                )
            )

    def _original_material(self):
        return dict(
            workflow=self.setup.original_source_workflow(),
            binding=self.setup.session.descriptor(),
            verification=self.setup.session.view()["verification"],
            publication=self.setup.view()["publication"],
        )

    def context_sha256(self):
        with self._lock:
            return digest(
                canonical(
                    dict(
                        original=self._original_material(),
                        publication=self._publication,
                        draft=None if self._draft is None else self._draft.sha256,
                        draft_origin=self._draft_origin,
                        draft_predecessor=self._draft_predecessor,
                        inbox=self.inbox.view(),
                        attempted=sorted(self._attempted),
                        attempt=self._attempt,
                        source_sha256=self.source_sha256,
                        launch_id=self.launch_id,
                    )
                )
            )

    @staticmethod
    def _attempt_key(action, workflow):
        cycles = workflow.get("received_camera_cycles", [])
        subject = (
            cycles[-1]["receipt_id"]
            if cycles
            else workflow["camera_receipt_request"]["event_sha256"]
        )
        return action + ":" + subject

    def blocked_reason(self, action):
        if action not in ACTIONS or self.setup.mode != "physical":
            return (
                "Received-camera onboarding requires the physical file-only workspace."
            )
        if action == EXPORT:
            return (
                None
                if self.retained_diagnostics() is not None
                else "Record a draft, collection or retained attempt before exporting received-camera metadata."
            )
        if (
            action in (START, RECORD, SUBMIT)
            and self._failed_draft is not None
            and self._failed_draft.sha256 != self._failed_draft_exported_sha256
        ):
            return "Export the complete failed draft before editing or submitting another candidate."
        workflow = self.setup.original_source_workflow()
        if not workflow or self.setup.view()["publication"]["status"] != "CURRENT":
            return "Explicitly verify and publish the original camera session first."
        contract = workflow.get("static_contract")
        if (
            not contract
            or contract["state"] != "REVIEWED_PASS"
            or workflow.get("camera_receipt_request") is None
        ):
            return "Review the original static design PASS and explicitly begin camera receipt first."
        if workflow.get("camera_identity_request") is not None:
            return "Receipt collection is frozen; the separate identity stage has been requested."
        cycles = workflow.get("received_camera_cycles", [])
        latest = cycles[-1] if cycles else None
        if (
            action in (SUBMIT, REVIEW, IDENTITY)
            and self._attempt_key(action, workflow) in self._attempted
        ):
            return "This exact one-use mutation was attempted. Inspect/reopen originals; no automatic replay or repair."
        if action == REVIEW:
            return (
                None
                if latest and latest["state"] == "REVIEW_PENDING"
                else "An exact original received-camera assessment must be awaiting review."
            )
        if action == IDENTITY:
            return (
                None
                if latest and latest["state"] == "REVIEWED_PASS"
                else "A committed original reviewed receipt PASS is required."
            )
        if latest and latest["state"] != "REVIEWED_BLOCKED":
            return "Review the original collection; a partial record is held for inspection and is not replayed."
        if len(cycles) >= MAX_COLLECTIONS:
            return "The four-cycle receipt budget is exhausted; export and inspect the original history."
        if action == START and self._draft is not None:
            return "A draft already exists; revise its explicit entries rather than silently replace it."
        if action in (RECORD, SUBMIT) and self._draft is None:
            return "Explicitly start a received-camera draft first."
        if action == DISCOVER and self._discovery_published:
            # Discovery may be explicitly repeated, but is not an endless next step.
            return None
        return None

    def _check(self, cancellation, deadline, *, source=True):
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline,
            "RECEIVED_CAMERA_INTERRUPTED",
            "Stopped or expired; no automatic replay.",
        )
        if source:
            _require(
                source_fingerprint(self.workspace) == self.source_sha256,
                "RECEIVED_CAMERA_SOURCE_CHANGED",
                "Source changed; retain originals as historical diagnostics.",
            )
            self._check(cancellation, deadline, source=False)

    def _binding(self, workflow, operator):
        return dict(
            receipt_id="receivedcamera-" + uuid4().hex,
            source_sha256=self.source_sha256,
            cell_id=workflow["binding"]["cell_id"],
            session_id=workflow["binding"]["session_id"],
            header_sha256=workflow["session_header_sha256"],
            origin_launch_id=workflow["binding"]["launch_id"],
            collection_launch_id=self.launch_id,
            operator_id=operator,
            prerequisites_sha256=workflow["prerequisites"]["evidence_sha256"],
            static_contract={
                role: workflow["static_contract"][role]["evidence_sha256"]
                for role in ("receipt", "assessment", "review")
            },
            camera_request_event_sha256=workflow["camera_receipt_request"][
                "event_sha256"
            ],
        )

    def _inspection_values(self, values):
        """Validate scalar input before any original append, with no fake refs."""
        # A categorical UNKNOWN-style default avoids a prechecked answer in the
        # UI. The receipt contract remains boolean; strict programmatic callers
        # may supply that boolean directly, never truthy integers/other strings.
        uncertain = values.get("inspection_uncertain", True)
        if type(uncertain) is str:
            _require(
                uncertain in ("UNCERTAIN", "CERTAIN"),
                "RECEIVED_CAMERA_INSPECTION_INVALID",
                "Choose UNCERTAIN or CERTAIN for inspection certainty.",
            )
            uncertain = uncertain == "UNCERTAIN"
        _require(
            type(uncertain) is bool,
            "RECEIVED_CAMERA_INSPECTION_INVALID",
            "Inspection uncertainty must be an explicit category or boolean.",
        )
        state = values.get("inspection_state", "UNKNOWN")
        _require(
            state in {"UNKNOWN", "RECORDED"},
            "RECEIVED_CAMERA_INSPECTION_INVALID",
            "Choose UNKNOWN or RECORDED inspection.",
        )
        if state == "UNKNOWN":
            _require(
                not values.get("purchase_choice")
                and not values.get("inspection_image_choice")
                and not values.get("inspection_observed_now")
                and all(
                    values.get(name, "") == ""
                    for name in (
                        "observed_manufacturer",
                        "observed_product_id",
                        "observed_camera_serial",
                        "observed_lens_focal_length_mm",
                    )
                )
                and all(
                    values.get(name, "UNCERTAIN") == "UNCERTAIN"
                    for name in (
                        "body_condition",
                        "lens_condition",
                        "connector_condition",
                    )
                )
                and all(
                    values.get(name, False) is False
                    for name in (
                        "identity_label_legible",
                        "purchase_record_matches",
                        "package_contents_complete",
                    )
                )
                and uncertain is True,
                "RECEIVED_CAMERA_INSPECTION_INVALID",
                "Select RECORDED before entering a structured inspection, or clear those fields. UNKNOWN never silently discards observations.",
            )
            return None
        _require(
            values.get("inspection_observed_now") is True,
            "RECEIVED_CAMERA_INSPECTION_CONFIRMATION",
            "Explicitly attest that this inspection was performed for this submission.",
        )
        fields = {
            name: receipt_text(values.get(name), name)
            for name in (
                "observed_manufacturer",
                "observed_product_id",
                "observed_camera_serial",
            )
        }
        focal = values.get("observed_lens_focal_length_mm", "")
        _require(
            type(focal) is str
            and (
                focal == ""
                or re.fullmatch(r"[1-9][0-9]{0,2}", focal) is not None
                and int(focal) <= 500
            ),
            "RECEIVED_CAMERA_FOCAL_INVALID",
            "Use a whole observed focal length of 1–500 mm, or leave unknown.",
        )
        fields["observed_lens_focal_length_mm"] = int(focal) if focal else None
        for name in ("body_condition", "lens_condition", "connector_condition"):
            fields[name] = InspectionCondition(values.get(name, "UNCERTAIN"))
        for name in (
            "identity_label_legible",
            "purchase_record_matches",
            "package_contents_complete",
            "inspection_uncertain",
        ):
            value = (
                uncertain if name == "inspection_uncertain" else values.get(name, False)
            )
            _require(
                type(value) is bool,
                "RECEIVED_CAMERA_INSPECTION_INVALID",
                "Inspection flags must be explicit booleans.",
            )
            fields[name] = value
        _require(
            bool(values.get("purchase_choice"))
            and bool(values.get("inspection_image_choice")),
            "RECEIVED_CAMERA_INSPECTION_ORIGINALS",
            "Select a purchase original and an inspection PNG/JPEG original.",
        )
        return fields

    def _selection(self, values, inspection):
        assert self._draft is not None
        selections = {
            record: values.get("attachment_" + record, "") for record in RECORD_IDS
        }
        for row in self._draft.to_dict()["rows"]:
            value = selections[row["record_id"]]
            _require(
                type(value) is str,
                "RECEIVED_CAMERA_ATTACHMENT_INVALID",
                "Choose an opaque discovered original.",
            )
            _require(
                not row["observation"]
                or row["observation"]["status"] != "OBSERVED"
                or bool(value),
                "RECEIVED_CAMERA_ROW_ORIGINAL_REQUIRED",
                "Every OBSERVED row must select an original attachment.",
            )
        selected = set(value for value in selections.values() if value)
        if inspection is not None:
            selected.update(
                (values["purchase_choice"], values["inspection_image_choice"])
            )
        _require(
            len(selected) <= MAX_ATTACHMENTS,
            "RECEIVED_CAMERA_ATTACHMENT_LIMIT",
            "Select at most sixteen unique originals.",
        )
        if selected:
            _require(
                self._discovery_published,
                "RECEIVED_CAMERA_DISCOVERY_REQUIRED",
                "Discover and publish original-file choices first.",
            )
        return tuple(sorted(selected)), selections

    def _retain(
        self,
        tx,
        payload,
        role,
        receipt_id,
        *,
        label=None,
        media_type="application/json",
    ):
        if role in _CAPS:
            _require(
                len(payload) <= _CAPS[role],
                "RECEIVED_CAMERA_BYTE_LIMIT",
                "The complete subject exceeds its fixed role budget.",
            )
        label = label or f"received-camera-{role}-v1:{receipt_id}"
        record = dict(
            reference=None,
            label=label,
            evidence_sha256=digest(payload),
            retention="COLLECTED_NOT_M1_RETAINED",
        )
        if role in _CAPS:
            import json

            record["document"] = json.loads(payload)
        with self._lock:
            assert self._attempt is not None
            self._attempt["records"][role] = record
        reference = tx.store_evidence(
            _STAGE,
            payload,
            label=label,
            media_type=media_type,
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        with self._lock:
            record.update(
                reference=reference.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
            )
        _require(
            tx.read_stage_evidence(reference) == payload,
            "RECEIVED_CAMERA_READBACK_CHANGED",
            "The exact retained original bytes changed.",
        )
        with self._lock:
            record["retention"] = "M1_FULL_BYTES_READ_BACK"
        return reference

    def _read_originals(self, tx, collection, check):
        """Re-read every metadata and private media original while leases live."""
        refs = []
        for role in ("notebook", *_CODECS):
            record = collection[role]
            if record is not None:
                check()
                ref = _parse_evidence_reference(record["reference"])
                _require(
                    tx.read_stage_evidence(ref) == canonical(record["document"]),
                    "RECEIVED_CAMERA_ORIGINAL_CHANGED",
                    "An exact review subject changed.",
                )
                refs.append(ref)
        for record in collection["originals"]:
            check()
            ref = _parse_evidence_reference(record["reference"])
            payload = tx.read_stage_evidence(ref)
            _require(
                len(payload) == ref.payload_bytes
                and digest(payload) == ref.payload_sha256,
                "RECEIVED_CAMERA_ORIGINAL_CHANGED",
                "A private original changed during review.",
            )
            refs.append(ref)
        return refs

    def _trio(self, collection, prerequisites):
        return (
            None
            if collection is None
            else tuple(
                codec(canonical(collection[role]["document"]), prerequisites)
                for role, codec in _CODECS.items()
            )
        )

    def _submit(
        self,
        tx,
        workflow,
        prerequisites,
        binding,
        values,
        files,
        row_choices,
        inspection_values,
        check,
    ):
        assert self._draft is not None
        cycles = workflow.get("received_camera_cycles", [])
        previous = cycles[-1] if cycles else None
        owned = [ref for ref in tx.snapshot().evidence if ref.stage is _STAGE]
        _require(
            len(owned) + len(files) + 4 <= MAX_STAGE_REFERENCES
            and sum(ref.payload_bytes for ref in owned)
            + sum(len(item.payload) for item in files)
            + sum(_CAPS.values())
            <= MAX_STAGE_BYTES
            and sum(len(item.payload) for item in files) <= MAX_SELECTED_BYTES,
            "RECEIVED_CAMERA_STORE_BUDGET",
            "The complete received-stage originals exceed their stage-owned budget.",
        )
        # Prove the unchanged design predecessor under the same storage scope.
        for role in ("receipt", "assessment", "review"):
            check()
            item = workflow["static_contract"][role]
            _require(
                tx.read_stage_evidence(_parse_evidence_reference(item["reference"]))
                == canonical(item["document"]),
                "RECEIVED_CAMERA_ORIGINAL_CHANGED",
                "The original reviewed design changed.",
            )
        identifier = binding["receipt_id"]
        suffix = identifier.removeprefix("receivedcamera-").upper()
        if previous is not None:
            self._read_originals(tx, previous, check)
            # WAIT→WAIT is forbidden: only a reviewed BLOCKED predecessor gets
            # a successor-start event. The first cycle uses the existing entry.
            check()
            tx.commit_stage_state(
                _STAGE,
                V2StageState.WAITING_OPERATOR,
                occurred_at_ns=time_ns(),
                detail_code="CAMERA_RECEIPT_COLLECTION_STARTED_" + suffix,
                expected_head_sha256=tx.snapshot().head.head_sha256,
                evidence=_refs(
                    _parse_evidence_reference(previous[role]["reference"])
                    for role in _CODECS
                ),
            )
        check()
        notebook_ref = self._retain(tx, self._draft.payload, "notebook", identifier)
        attachments, chosen = [], {}
        for index, item in enumerate(files):
            check()
            ref = self._retain(
                tx,
                item.payload,
                f"original_{index:02}",
                identifier,
                label=f"received-camera-original-v1:{identifier}:{index:02}",
                media_type=item.media_type,
            )
            attachments.append(
                ReceivedCameraAttachment(ref, item.basename, item.media_type)
            )
            chosen[item.choice_id] = ref
        inspection = None
        if inspection_values is not None:
            inspection = CameraReceiptInspection(
                binding=ReceiptBinding(
                    source_binding_sha256=physical_camera_source_binding(
                        self.source_sha256
                    ),
                    session_header_sha256=workflow["session_header_sha256"],
                    session_id=binding["session_id"],
                    cell_id=binding["cell_id"],
                    stage=_STAGE,
                    evidence=tuple(
                        BoundEvidence.from_reference(ref)
                        for ref in _refs((notebook_ref, *chosen.values()))
                    ),
                ),
                operator_id=values["operator_id"],
                observed_at_ns=time_ns(),
                **inspection_values,
                purchase_record_evidence_id=chosen[
                    values["purchase_choice"]
                ].evidence_id,
                inspection_image_evidence_ids=(
                    chosen[values["inspection_image_choice"]].evidence_id,
                ),
            )
        submission = build_received_camera_submission(
            prerequisites,
            self._draft,
            binding=binding,
            notebook_reference=notebook_ref,
            inspection=inspection,
            attachments=tuple(
                sorted(attachments, key=lambda item: item.reference.evidence_id)
            ),
            row_links=tuple(
                ReceivedCameraRowLink(
                    record,
                    (
                        chosen[row_choices[record]].evidence_id
                        if row_choices[record]
                        else None
                    ),
                )
                for record in RECORD_IDS
            ),
            submitted_at_ns=time_ns(),
            evidence_inventory=tx.snapshot().evidence,
            predecessor=self._trio(previous, prerequisites),
            draft_origin_notebook_sha256=self._draft_origin,
        )
        assessment = assess_received_camera_submission(submission)
        refs = [notebook_ref, *chosen.values()]
        for role, artifact in (("submission", submission), ("assessment", assessment)):
            check()
            refs.append(self._retain(tx, artifact.payload, role, identifier))
        check()
        tx.commit_stage_state(
            _STAGE,
            V2StageState.REVIEW_PENDING,
            occurred_at_ns=time_ns(),
            detail_code="CAMERA_RECEIPT_COLLECTION_SUBMITTED_" + suffix,
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=_refs(refs),
        )

    def _result(self, action, report):
        result = dict(
            schema="rocell.wizard_worker_result.v1",
            action_id=action,
            status="SUCCEEDED",
            steps=[dict(name=action, exit_code=0, report=report)],
            device_open_count=0,
            serial_write_count=0,
            power_event_count=0,
            motion_command_count=0,
            contact_command_count=0,
            metadata_inventory_performed=False,
            physical_authority=False,
        )
        self._publication = dict(status="PENDING", operation_id=None)
        self._pending_result, self._pending_action = canonical(result), action
        return deepcopy(result)

    def perform(
        self,
        action_id: str,
        values: dict[str, Any],
        *,
        expected_context_sha256: str,
        cancellation: Event,
        progress: Callable[[str], None],
        export_parent=None,
    ):
        _require(
            self._operation_lock.acquire(blocking=False),
            "RECEIVED_CAMERA_BUSY",
            "A received-camera operation is active.",
        )
        deadline = (
            monotonic_ns()
            + (120 if action_id in (SUBMIT, REVIEW, IDENTITY, EXPORT) else 60)
            * 1_000_000_000
        )
        mutated_setup = False
        try:
            reason = self.blocked_reason(action_id)
            _require(reason is None, "RECEIVED_CAMERA_ACTION_BLOCKED", reason or "")
            _require(
                values.get("file_only") is True,
                "RECEIVED_CAMERA_FILE_ONLY_REQUIRED",
                "Explicitly acknowledge this file-only operation.",
            )
            if action_id == EXPORT:
                # Recovery export deliberately survives changed source/failed
                # completion logs. It publishes no new original or stage state.
                self._check(cancellation, deadline, source=False)
                from .physical_received_camera_export import (
                    export_received_camera_metadata,
                )

                with self._lock:
                    self._export_publication = deepcopy(self._publication)
                    diagnostic = self.retained_diagnostics()
                receipt = export_received_camera_metadata(
                    diagnostic,
                    export_parent=export_parent,
                    source_sha256=self.source_sha256,
                    launch_id=self.launch_id,
                    cancellation=cancellation,
                    deadline_ns=deadline,
                )
                with self._lock:
                    self._export_receipt = deepcopy(receipt)
                    if self._failed_draft is not None:
                        self._failed_draft_exported_sha256 = self._failed_draft.sha256
                    return self._result(
                        action_id,
                        dict(metadata_export=receipt, meaning=MEANING, **_FLAGS),
                    )
            _require(
                self.context_sha256() == expected_context_sha256,
                "RECEIVED_CAMERA_CONTEXT_CHANGED",
                "The original/draft context changed; preview again.",
            )
            self._check(cancellation, deadline)
            material = canonical(self._original_material())
            workflow = self.setup.original_source_workflow()
            assert workflow is not None
            prerequisites = self.setup.current_prerequisite_artifact()
            candidate, origin = None, self._draft_origin
            draft_predecessor = self._draft_predecessor
            if action_id == START:
                cycles = workflow.get("received_camera_cycles", [])
                draft_predecessor = cycles[-1]["receipt_id"] if cycles else None
                mode = values.get("mode")
                _require(
                    mode in ("BLANK", "REVISE_LAST"),
                    "RECEIVED_CAMERA_DRAFT_MODE",
                    "Explicitly choose a blank or revised draft.",
                )
                if mode == "BLANK":
                    candidate = PhysicalIntakeNotebook.start(
                        prerequisites, launch_session_id=self.launch_id
                    )
                    origin = None
                else:
                    cycles = workflow.get("received_camera_cycles", [])
                    _require(
                        bool(cycles) and cycles[-1]["state"] == "REVIEWED_BLOCKED",
                        "RECEIVED_CAMERA_REVISION_BLOCKED",
                        "Only an exact reviewed BLOCKED original can be revised.",
                    )
                    item = cycles[-1]["notebook"]
                    original = PhysicalIntakeNotebook.from_payload(
                        canonical(item["document"]),
                        prerequisites=prerequisites,
                        expected_sha256=item["evidence_sha256"],
                    )
                    candidate = original.revise_for_launch(
                        launch_session_id=self.launch_id
                    )
                    origin = original.sha256
            elif action_id == RECORD:
                assert self._draft is not None
                candidate = self._draft.record(
                    **{
                        name: values.get(name, "")
                        for name in (
                            "record_id",
                            "observation_status",
                            "observed_value",
                            "method",
                            "evidence_note",
                            "operator_id",
                        )
                    },
                    recorded_at_ns=time_ns(),
                )
            review, binding, selected, row_choices, inspection = (
                None,
                None,
                (),
                {},
                None,
            )
            if action_id == SUBMIT:
                _actor(values.get("operator_id"))
                assert self._draft is not None
                _require(
                    self._draft.to_dict()["binding"]
                    == PhysicalIntakeNotebook.start(
                        prerequisites, launch_session_id=self.launch_id
                    ).to_dict()["binding"],
                    "RECEIVED_CAMERA_DRAFT_CONTEXT_CHANGED",
                    "The draft belongs to other original requirements or launch.",
                )
                inspection = self._inspection_values(values)
                selected, row_choices = self._selection(values, inspection)
                binding = self._binding(workflow, values["operator_id"])
            elif action_id == REVIEW:
                _actor(values.get("reviewer_id"))
                latest = workflow["received_camera_cycles"][-1]
                submission = ReceivedCameraSubmission(
                    canonical(latest["submission"]["document"]), prerequisites
                )
                assessment = ReceivedCameraSubmissionAssessment(
                    canonical(latest["assessment"]["document"]), prerequisites
                )
                review = review_received_camera_submission(
                    submission,
                    assessment,
                    decision=values.get("decision", ""),
                    reviewer_id=values["reviewer_id"],
                    review_launch_id=self.launch_id,
                    reviewed_at_ns=time_ns(),
                )
            with self._lock:
                self._pending_draft, self._pending_origin = candidate, origin
                self._pending_draft_predecessor = draft_predecessor
            if action_id == DISCOVER:
                progress(
                    "Reading selected-folder file metadata; no camera or arm access."
                )
                self._discovery_published = False
                self.inbox.discover(cancellation=cancellation, deadline_ns=deadline)
            elif action_id in (SUBMIT, REVIEW, IDENTITY):
                scope: Any = (
                    self.inbox.selected_files(
                        selected, cancellation=cancellation, deadline_ns=deadline
                    )
                    if selected
                    else nullcontext(())
                )
                with scope as files:
                    if inspection is not None:
                        image = next(
                            item
                            for item in files
                            if item.choice_id == values["inspection_image_choice"]
                        )
                        _require(
                            image.media_type in ("image/png", "image/jpeg"),
                            "RECEIVED_CAMERA_INSPECTION_IMAGE",
                            "Inspection image must be an original PNG or JPEG.",
                        )
                    self._check(cancellation, deadline)
                    _require(
                        canonical(self._original_material()) == material,
                        "RECEIVED_CAMERA_CONTEXT_CHANGED",
                        "The exact original context changed before storage.",
                    )
                    with self._lock:
                        self._attempted.add(self._attempt_key(action_id, workflow))
                        identifier = (
                            binding["receipt_id"]
                            if binding
                            else workflow["received_camera_cycles"][-1]["receipt_id"]
                        )
                        self._attempt = dict(
                            action_id=action_id, receipt_id=identifier, records={}
                        )
                    self.invalidate()
                    mutated_setup = True
                    progress(
                        "Retaining and rereading exact received-camera originals; no device access."
                    )
                    with self.setup.received_camera_transaction(
                        cancellation=cancellation,
                        progress=progress,
                        deadline_ns=deadline,
                    ) as (_, current):
                        _require(
                            canonical(current) == canonical(workflow),
                            "RECEIVED_CAMERA_CONTEXT_CHANGED",
                            "The original workflow changed before its transaction.",
                        )
                        verification = self.setup.session.view()["verification"]
                        with self.setup.session.stage_transaction(
                            expected_challenge_sha256=verification["challenge_sha256"]
                        ) as tx:
                            snapshot = tx.snapshot()
                            stage = STAGE_ORDER[3] if action_id == IDENTITY else _STAGE
                            _require(
                                snapshot.head.head_sha256
                                == workflow["session_head_sha256"]
                                and snapshot.next_action.stage is stage,
                                "RECEIVED_CAMERA_STAGE_CHANGED",
                                "The original stage/head changed; no replay.",
                            )
                            check = lambda: self._check(cancellation, deadline)
                            if action_id == SUBMIT:
                                self._submit(
                                    tx,
                                    workflow,
                                    prerequisites,
                                    binding,
                                    values,
                                    files,
                                    row_choices,
                                    inspection,
                                    check,
                                )
                            else:
                                latest = workflow["received_camera_cycles"][-1]
                                refs = self._read_originals(tx, latest, check)
                                suffix = (
                                    latest["receipt_id"]
                                    .removeprefix("receivedcamera-")
                                    .upper()
                                )
                                if review is not None:
                                    check()
                                    refs.append(
                                        self._retain(
                                            tx,
                                            review.payload,
                                            "review",
                                            latest["receipt_id"],
                                        )
                                    )
                                    verdict = review.to_dict()["verdict"]
                                    target, code = (
                                        V2StageState(verdict),
                                        "CAMERA_RECEIPT_COLLECTION_REVIEWED_"
                                        + verdict
                                        + "_",
                                    )
                                else:
                                    refs = (
                                        []
                                    )  # New stage never cites other-stage evidence.
                                    target, code = (
                                        V2StageState.WAITING_OPERATOR,
                                        "CAMERA_IDENTITY_REQUESTED_",
                                    )
                                check()
                                tx.commit_stage_state(
                                    stage,
                                    target,
                                    occurred_at_ns=time_ns(),
                                    detail_code=code + suffix,
                                    expected_head_sha256=tx.snapshot().head.head_sha256,
                                    evidence=_refs(refs),
                                )
                            check()
                with self._lock:
                    self._adopt(prerequisites)
            self._check(cancellation, deadline)
            if not mutated_setup:
                _require(
                    canonical(self._original_material()) == material,
                    "RECEIVED_CAMERA_CONTEXT_CHANGED",
                    "The original context changed during draft/discovery work.",
                )
            with self._lock:
                # Full candidate stays dedicated in the service/export cache;
                # ordinary result cards retain exact small identity/coverage.
                report: dict[str, Any] = dict(
                    action_id=action_id,
                    pending_completion_log=True,
                    original_context=self._context(),
                    original_head_sha256=(self._workflow or {}).get(
                        "session_head_sha256"
                    ),
                    inbox_discovery_sha256=(
                        digest(canonical(self.inbox.view()))
                        if action_id == DISCOVER
                        else None
                    ),
                    draft_sha256=None if candidate is None else candidate.sha256,
                    draft_origin_notebook_sha256=origin,
                    collection=self._collection,
                    stage_states=self._stages,
                    identity_entry=(self._workflow or {}).get(
                        "camera_identity_request"
                    ),
                    meaning=MEANING,
                    **_FLAGS,
                )
                if report["collection"] is not None:
                    report["collection"] = {
                        key: value
                        for key, value in report["collection"].items()
                        if key not in ("notebook", "inspection")
                    }
                return self._result(action_id, report)
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
                "RECEIVED_CAMERA_RESULT_CHANGED",
                "Retain the exact complete result before durable publication.",
            )

    def publication_completed(self, operation_id):
        with self._lock:
            if self._publication["status"] != "PENDING" or self._pending_result is None:
                return
            action = self._pending_action
            if action == EXPORT:
                self._publication = self._export_publication or dict(
                    status="HISTORICAL_HELD", operation_id=None
                )
            else:
                self._publication = dict(status="CURRENT", operation_id=operation_id)
                if action in (START, RECORD):
                    self._draft, self._draft_origin = (
                        self._pending_draft,
                        self._pending_origin,
                    )
                    self._draft_predecessor = self._pending_draft_predecessor
                if action == SUBMIT:
                    self._draft, self._draft_origin = None, None
                    self._draft_predecessor = None
                if action == DISCOVER:
                    self._discovery_published = self.inbox.view()["status"] == "READY"
            self._pending_result, self._pending_action = None, None
            self._pending_draft, self._pending_origin = None, None

    def retained_diagnostics(self):
        """Full bounded metadata only. Raw private originals never enter JSON."""
        with self._lock:
            workflow = (
                self.setup.session.retained_source_workflow() or self._workflow or {}
            )
            cycles = workflow.get("received_camera_cycles", [])
            draft = self._pending_draft or self._draft
            if (
                not cycles
                and draft is None
                and self._attempt is None
                and self._failed_draft is None
            ):
                return None
            return deepcopy(
                dict(
                    schema="rocell.wizard_received_camera_diagnostics.v1",
                    original_context=self._context(),
                    publication=self._publication,
                    stage_states=self._stages,
                    cycles=cycles,
                    draft=None if draft is None else draft.to_dict(),
                    draft_origin_notebook_sha256=(
                        self._pending_origin
                        if self._pending_draft
                        else self._draft_origin
                    ),
                    attempt=self._attempt,
                    failed_draft=(
                        None
                        if self._failed_draft is None
                        else dict(
                            document=self._failed_draft.to_dict(),
                            draft_origin_notebook_sha256=self._failed_origin,
                        )
                    ),
                    camera_identity_request=workflow.get("camera_identity_request"),
                    meaning=MEANING,
                    **_FLAGS,
                )
            )

    def export_metadata(self):
        return deepcopy(self._export_receipt)
