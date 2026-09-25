"""File-only final camera-identity review owned by the existing USB/Setup services.

No provider, boot collector, runtime registration or device admission is used.
The service rereads the complete original under its current stage lease before
writing. Partial writes are retained for diagnosis; they are never resumed.
"""

from copy import deepcopy
from time import time_ns
from uuid import uuid4

from .physical_camera_usb_complete_constants import (
    SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA,
    USB_COMPLETE_ROLE_BYTES,
    usb_complete_event,
    usb_complete_label,
)
from .physical_camera_usb_reboot_constants import SOURCE_WORKFLOW_USB_REBOOT_SCHEMA
from .physical_camera_usb_complete_inputs import (
    original_usb_complete_inputs,
    original_usb_complete_inputs_v14,
)
from .physical_usb_complete_series import (
    CompleteUsbSeries,
    CompleteUsbAssessment,
    REVIEW_ELIGIBLE,
    build_complete_usb_assessment_pair,
    review_complete_usb_series,
)
from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_v2 import V2StageState
from rocell.providers.windows.usb_identity_protocol import canonical
from .physical_usb_complete_projection import ASSESSMENT_FIELDS, REVIEW_FIELDS

ASSESS = "physical_usb_complete_assess"
REVIEW = "physical_usb_complete_review"
ACTIONS = frozenset((ASSESS, REVIEW))
EXPORT = "physical_usb_identity_export"
STAGE = STAGE_ORDER[3]
MEANING = (
    "Review the four original camera-identity observations only. Accepted identity "
    "does not mean hardware ready, calibrated images, camera capture, arm access, "
    "power, motion or contact. Partial publications are diagnostic-only. "
    "Reviewer labels are procedural, not proof of independent human identity."
)


def _require(*args):
    from .physical_usb_identity_service import _require as require

    return require(*args)


def _reference(record):
    from .physical_usb_identity_service import _reference as reference

    return reference(record)


def complete_action_boundary(workflow):
    """Cheap navigation/state check, never original authentication or approval."""
    if type(workflow) is not dict:
        return None
    reboot = workflow.get("usb_qualification_reboot")
    if type(reboot) is not dict or reboot.get("state") != "RETAINED_BLOCKED":
        return None
    if reboot.get("phase") != "AFTER_REBOOT" or not reboot.get("phase_record"):
        return None
    complete = workflow.get("usb_qualification_complete")
    if workflow.get("schema") == SOURCE_WORKFLOW_USB_REBOOT_SCHEMA:
        return ASSESS if complete is None else None
    if (
        workflow.get("schema") == SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
        and type(complete) is dict
        and complete.get("state") == "REVIEW_PENDING"
        and type(complete.get("series")) is dict
        and type(complete.get("assessment")) is dict
        and complete.get("review") is None
        and type(complete.get("events")) is list
        and len(complete["events"]) == 2
    ):
        return REVIEW
    return None


def _inputs(workflow, prerequisites):
    from .physical_camera_usb_trial_readback import _received

    received = dict(
        zip(("submission", "assessment", "review"), _received(prerequisites, workflow))
    )
    adapter = (
        original_usb_complete_inputs_v14
        if workflow.get("schema") == SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
        else original_usb_complete_inputs
    )
    return adapter(workflow, received=received)


def distinct_review_label(workflow, reviewer):
    """Cheap cached form check, repeated by the original codec before writing.

    Catch an obvious label mistake before consuming a one-shot operation. This
    does not authenticate people, originals, publication or reviewer authority.
    """
    try:
        actors = [
            workflow["usb_qualification_trial"]["plan"]["document"]["operator_id"]
        ]
        actors += [
            workflow["usb_qualification_" + phase]["phase_record"]["document"][
                "context"
            ]["operator_id"]
            for phase in ("baseline", "absence", "reconnect", "reboot")
        ]
        return type(reviewer) is str and all(
            type(actor) is str and reviewer.casefold() != actor.casefold()
            for actor in actors
        )
    except (TypeError, KeyError):
        return False


class _UsbCompleteReview:
    def __init__(self, owner):
        self.owner = owner
        self.complete = None
        self.attempt = None

    def adopt(self, workflow):
        # View adoption is inert. It cannot create a series or publish a review.
        self.complete = deepcopy(workflow.get("usb_qualification_complete"))

    def context(self):
        return dict(complete=deepcopy(self.complete), attempt=deepcopy(self.attempt))

    def has_diagnostics(self):
        return self.complete is not None or self.attempt is not None

    def diagnostics(self, workflow):
        if not self.has_diagnostics() and not workflow.get(
            "usb_qualification_complete"
        ):
            return {}
        return dict(
            qualification_complete=deepcopy(
                workflow.get("usb_qualification_complete") or self.complete
            ),
            qualification_complete_attempt=deepcopy(self.attempt),
        )

    def fields(self, action, check, actor):
        common = check(
            "confirm_identity_only",
            "Original identity records only; no camera, arm, power, movement or contact",
        )
        if action == ASSESS:
            return (
                check(
                    "confirm_file_assessment",
                    "Recheck and assess all four retained original phases; no new acquisition",
                ),
                common,
            )
        if action == REVIEW:
            return (
                actor(
                    "reviewer_id",
                    "Distinct reviewer label (not authenticated identity)",
                ),
                dict(
                    name="decision",
                    type="select",
                    label="Decision for this exact assessment",
                    required=True,
                    default="REJECT",
                    options=[
                        dict(value="REJECT", label="Reject / keep blocked"),
                        dict(
                            value="ACKNOWLEDGE_EXACT",
                            label="Acknowledge this exact assessment",
                        ),
                    ],
                ),
                check(
                    "confirm_exact_assessment",
                    "I reviewed the displayed assessment and its exact subject hash",
                ),
                common,
            )
        return ()

    def blocked_reason(self, action, workflow):
        if action not in ACTIONS or self.owner.setup.mode != "physical":
            return "Use an explicit original camera-identity review action."
        if self.owner.setup.view()["publication"]["status"] != "CURRENT":
            return "Refresh and publish the exact original session first."
        if complete_action_boundary(workflow) != action:
            return "Complete the preceding original phase or assessment. Partial and already reviewed records are read-only."
        if self.owner._attempt_key(action, workflow) in self.owner._attempted:
            return "This exact review action was attempted; inspect or export diagnostics without replay."
        return None

    def projection(self, value):
        workflow = self.owner._workflow or {}
        if not self.has_diagnostics() and complete_action_boundary(workflow) != ASSESS:
            return deepcopy(value)
        result = deepcopy(value)
        publication = deepcopy(self.owner._publication)
        if (
            publication["status"] == "CURRENT"
            and self.owner.setup.view()["publication"]["status"] != "CURRENT"
        ):
            publication = dict(status="HISTORICAL_HELD", operation_id=None)
        row = self.complete
        summary = None
        if row is not None:
            assessment = row.get("assessment")
            review = row.get("review")
            summary = dict(
                series_id=row["series_id"],
                state=row["state"],
                series_sha256=(row.get("series") or {}).get("evidence_sha256"),
                assessment_sha256=(assessment or {}).get("evidence_sha256"),
                review_sha256=(review or {}).get("evidence_sha256"),
                assessment=(
                    None
                    if assessment is None
                    else {
                        key: deepcopy(assessment["document"][key])
                        for key in ASSESSMENT_FIELDS
                    }
                ),
                review=(
                    None
                    if review is None
                    else {
                        key: deepcopy(review["document"][key]) for key in REVIEW_FIELDS
                    }
                ),
            )
        current = publication["status"] == "CURRENT"
        action = complete_action_boundary(workflow)
        if action is not None and self.blocked_reason(action, workflow) is not None:
            action = None
        result.update(
            schema="rocell.wizard_usb_qualification.v6",
            publication=publication,
            complete=summary,
            meaning=MEANING,
            status=(
                (row["state"] if row else "COMPLETE_REVIEW_READY")
                if current
                else "HISTORICAL_HELD"
            ),
            next_action=(
                (action or EXPORT)
                if current
                else (EXPORT if self.has_diagnostics() else None)
            ),
        )
        if publication["status"] == "PENDING":
            result.update(
                complete=None, next_action=None, status="NOT_DECLARED", plan=None
            )
            for key in ("baseline", "absence", "reconnect", "reboot"):
                result[key] = None
        return result

    def _retain(self, tx, subject, series_id, guard):
        role, raw = subject.role, subject.payload
        _require(
            type(raw) is bytes and 0 < len(raw) <= USB_COMPLETE_ROLE_BYTES[role],
            "USB_COMPLETE_ROLE_LIMIT",
        )
        guard()
        record = dict(
            document=subject.to_dict(),
            evidence_sha256=subject.sha256,
            reference=None,
            retention="COLLECTED_NOT_M1_RETAINED",
        )
        self.attempt["records"][role] = record
        ref = tx.store_evidence(
            STAGE,
            raw,
            label=usb_complete_label(role, series_id),
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        record.update(
            reference=ref.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        guard()
        _require(tx.read_stage_evidence(ref) == raw, "USB_COMPLETE_READBACK_CHANGED")
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        guard()
        return ref

    def _commit(self, tx, kind, state, series_id, refs, guard):
        guard()
        snapshot = tx.commit_stage_state(
            STAGE,
            state,
            occurred_at_ns=time_ns(),
            detail_code=usb_complete_event(kind, series_id),
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=tuple(sorted(refs, key=lambda r: r.evidence_id)),
        )
        event = snapshot.committed_events[-1]
        self.attempt["events"].append(event.to_dict())
        guard()
        return event

    def perform(self, action, values, *, cancellation, progress, deadline):
        from .physical_camera_session import _read_original_evidence_under_lease

        owner, setup = self.owner, self.owner.setup
        workflow, session = setup.original_source_workflow(), setup.session
        _require(
            self.blocked_reason(action, workflow) is None, "USB_COMPLETE_ACTION_BLOCKED"
        )
        if action == REVIEW:
            _require(
                values["decision"] in {"REJECT", "ACKNOWLEDGE_EXACT"},
                "USB_COMPLETE_DECISION_INVALID",
            )
            _require(
                distinct_review_label(workflow, values["reviewer_id"]),
                "REVIEWER_MUST_DIFFER",
            )
        series_id = (
            "usbseries-" + uuid4().hex
            if action == ASSESS
            else workflow["usb_qualification_complete"]["series_id"]
        )
        binding = canonical(session.descriptor())
        with owner._lock:
            self.attempt = dict(
                action_id=action, series_id=series_id, records={}, events=[]
            )
            owner._attempted.add(owner._attempt_key(action, workflow))
            owner.invalidate()
            generation = owner._generation

        def guard(*, source=True):
            owner._check(cancellation, deadline, source=source)
            _require(
                owner._generation == generation
                and setup.session is session
                and canonical(session.descriptor()) == binding,
                "USB_COMPLETE_CONTEXT_CHANGED",
            )

        try:
            with setup.usb_complete_transaction(
                cancellation=cancellation, progress=progress, deadline_ns=deadline
            ) as (prerequisites, current):
                _require(
                    canonical(current) == canonical(workflow),
                    "USB_COMPLETE_ORIGINAL_CHANGED",
                )
                guard()
                verification = session.view()["verification"]
                with session.stage_transaction(
                    expected_challenge_sha256=verification["challenge_sha256"]
                ) as tx:
                    # Use the existing lease; no nested transaction, old head,
                    # exported input or saved green verdict substitutes for it.
                    _, original = _read_original_evidence_under_lease(
                        tx,
                        bound=session.descriptor(),
                        expected_header_sha256=workflow["session_header_sha256"],
                        strict_workflow=True,
                        check=guard,
                    )
                    _require(
                        canonical(original) == canonical(workflow),
                        "USB_COMPLETE_ORIGINAL_CHANGED",
                    )
                    inputs = _inputs(original, prerequisites)
                    guard()
                    if action == ASSESS:
                        self._commit(
                            tx,
                            "ASSESSMENT_REQUESTED",
                            V2StageState.WAITING_OPERATOR,
                            series_id,
                            (inputs["reboot_reference"],),
                            guard,
                        )
                        series, assessment = build_complete_usb_assessment_pair(
                            series_id=series_id, **inputs
                        )
                        guard()
                        sr = self._retain(tx, series, series_id, guard)
                        ar = self._retain(tx, assessment, series_id, guard)
                        self._commit(
                            tx,
                            "ASSESSMENT_RETAINED",
                            V2StageState.REVIEW_PENDING,
                            series_id,
                            (sr, ar),
                            guard,
                        )
                    else:
                        row = original["usb_qualification_complete"]
                        series = CompleteUsbSeries(canonical(row["series"]["document"]))
                        assessment = CompleteUsbAssessment(
                            canonical(row["assessment"]["document"])
                        )
                        review = review_complete_usb_series(
                            series,
                            assessment,
                            **inputs,
                            reviewer_id=values["reviewer_id"],
                            review_launch_id=owner.launch_id,
                            reviewed_at_utc_ns=time_ns(),
                            decision=values["decision"]
                        )
                        guard()
                        rr = self._retain(tx, review, series_id, guard)
                        accepted = review.to_dict()["verdict"] == REVIEW_ELIGIBLE
                        self._commit(
                            tx,
                            "REVIEWED",
                            V2StageState.PASS if accepted else V2StageState.BLOCKED,
                            series_id,
                            (
                                _reference(row["series"]),
                                _reference(row["assessment"]),
                                rr,
                            ),
                            guard,
                        )
                guard()
            guard()
            with owner._lock:
                owner._adopt()
                return owner._result(action)
        except BaseException:
            owner.invalidate()
            setup.invalidate()
            raise
