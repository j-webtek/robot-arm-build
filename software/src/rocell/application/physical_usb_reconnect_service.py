"""Private AFTER_RECONNECT composition; never a second admission owner.

Begin records an operator report, not mechanical proof. Three independently
logged acquisitions precede preparation. Boot and descriptors have separate
explicit one-shot actions and original admissions. Reopened intervals cannot
be rebound to another launch; retained and uncertain work is export-only.
"""

from __future__ import annotations

from copy import deepcopy
from time import time_ns
from uuid import uuid4

from .physical_camera_usb_reconnect_constants import (
    USB_RECONNECT_ROLE_BYTES,
    usb_reconnect_event,
    usb_reconnect_label,
)
from .physical_camera_usb_reconnect import (
    UsbReconnectPreparation,
    build_usb_reconnect_preparation,
    original_usb_reconnect_predecessor,
    original_usb_reconnect_predecessor_v12,
)
from .physical_usb_reconnect_phase import (
    build_usb_reconnect_operator_event,
    build_usb_reconnect_qualification_phase,
    UsbReconnectQualificationPhase,
)
from .physical_camera_selection import PhysicalCameraSelection
from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_v2 import V2StageState, _parse_event
from .physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from .physical_usb_identity_campaign import (
    UsbIdentityOperation,
    PhysicalUsbIdentityCampaign,
    usb_identity_phase_operation,
)
from .physical_usb_identity_dispatch import PhysicalUsbIdentityDispatchOwner
from .commissioning_usb_identity_persistence import M1PhysicalUsbIdentityPersistence
from .commissioning_camera_persistence import physical_camera_source_binding
from .usb_identity_stage_policy import (
    UsbIdentityPolicyReview,
    UsbIdentityStagePolicy,
    UsbIdentityAdmissionIdentity,
    inspect_usb_identity_stage_policy,
)
from .physical_usb_reconnect_boot import (
    UsbReconnectBootIntent,
    OriginalUsbReconnectBootCollector,
    build_usb_reconnect_boot_intent,
)
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    compare_boot_observations,
)
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.usb_identity_registration import (
    UsbIdentityRuntimeRegistration,
    UsbIdentityRuntimeReview,
    usb_identity_runtime_candidate,
    inspect_usb_identity_runtime,
    review_usb_identity_runtime,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest


BEGIN = "physical_usb_reconnect_begin"
PREPARE = "physical_usb_reconnect_prepare"
REVIEW = "physical_usb_reconnect_review"
BOOT_COLLECT = "physical_usb_reconnect_boot_collect"
COLLECT = "physical_usb_reconnect_collect"
ACTIONS = frozenset((BEGIN, PREPARE, REVIEW, BOOT_COLLECT, COLLECT))
EXPORT = "physical_usb_identity_export"
STAGE = STAGE_ORDER[3]
FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    camera_capture_authorized=False,
    arm_access_authorized=False,
)
ACQUISITIONS = (
    ("GENERIC_INVENTORY", "inventory_devices"),
    ("NATIVE_INVENTORY", "native_camera_inventory"),
    ("NATIVE_IDENTITY", "native_camera_identity"),
)
NEXT = {
    "PREPARATION_REQUESTED": PREPARE,
    "PREPARED": REVIEW,
    "REVIEWED": BOOT_COLLECT,
    "BOOT_RETAINED": COLLECT,
}
MEANING = (
    "One AFTER_RECONNECT interval after original physical-node absence: an operator "
    "report, fresh reviewed metadata, separately owned boot observation and one "
    "separately admitted descriptor query. Not mechanical proof, reboot qualification, "
    "camera capture or arm authority. Stop is software cancellation, not a robot E-stop. "
    "Partial, uncertain or reopened intervals are export-only; never retry them."
)


def _require(*args):
    from .physical_usb_identity_service import _require as require

    return require(*args)


def _reference(record):
    from .physical_usb_identity_service import _reference as reference

    return reference(record)


def _predecessor(workflow):
    if workflow.get("schema") == "rocell.physical_camera_source_workflow_readback.v11":
        return original_usb_reconnect_predecessor(workflow)
    return original_usb_reconnect_predecessor_v12(workflow)


def _entry_history_boot(workflow, phase):
    """Read-only boot history after Setup has authenticated the full v15 store.

    The old phase-admission adapters intentionally do not accept stage 5. Do
    not relabel that workflow or turn historical display into a replayable
    predecessor. Decode only the exact retained boot observation for display.
    """
    from .physical_camera_mode_entry import SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA
    from .physical_camera_usb_absence import _record

    try:
        if (
            type(workflow) is not dict
            or workflow.get("schema") != SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA
            or workflow["camera_mode_entry"]["state"] not in {"ENTERED", "INCOMPLETE"}
            or workflow["usb_qualification_complete"]["state"] != "REVIEWED_PASS"
            or phase not in {"usb_qualification_absence", "usb_qualification_reconnect"}
        ):
            return None
        raw, _ = _record(workflow[phase]["host_boot"])
        return HostBootObservation(raw)
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


class _UsbTrialReconnect:
    def __init__(self, owner):
        self.owner = owner
        self.reconnect = self.attempt = self.ledger = self.predecessor = None
        self.query_attempted = False

    def adopt(self, workflow):
        before = (self.reconnect or {}).get("phase_id")
        self.reconnect = deepcopy(workflow.get("usb_qualification_reconnect"))
        if before != (self.reconnect or {}).get("phase_id"):
            self.ledger = None
        if self.reconnect and self.reconnect.get("preparation"):
            self.ledger = deepcopy(
                self.reconnect["preparation"]["document"]["acquisition_ledger"]
            )
        try:
            if workflow.get("schema") in {
                "rocell.physical_camera_source_workflow_readback.v13",
                "rocell.physical_camera_source_workflow_readback.v14",
            }:
                # Display the authenticated old boot relation under its real
                # successor schema. This never makes reconnect replayable.
                from .physical_camera_usb_reconnect import (
                    _original_usb_reconnect_predecessor,
                )

                self.predecessor = _original_usb_reconnect_predecessor(
                    workflow,
                    successor=True,
                    reboot_successor=True,
                    complete_successor=workflow["schema"].endswith(".v14"),
                )
            else:
                self.predecessor = _predecessor(workflow)
        except (ValueError, TypeError, KeyError, AttributeError):
            self.predecessor = None

    def invalidate(self):
        # No new launch, renewed interval or implicit retry is created here.
        pass

    def has_diagnostics(self):
        return self.reconnect is not None or self.attempt is not None

    def diagnostics(self, workflow):
        if not self.has_diagnostics():
            return {}
        attempt = deepcopy(self.attempt)
        if attempt is not None:
            attempt["acquisition_ledger"] = deepcopy(self.ledger)
        return dict(
            qualification_reconnect=deepcopy(
                workflow.get("usb_qualification_reconnect") or self.reconnect
            ),
            qualification_reconnect_attempt=attempt,
        )

    def _report(self):
        record = (self.reconnect or {}).get("operator_event")
        return None if record is None else record["document"]

    def _start(self):
        if not self.reconnect:
            return None
        return next(
            (
                event
                for event in self.reconnect["events"]
                if event["detail_code"]
                == usb_reconnect_event(
                    "PREPARATION_REQUESTED", self.reconnect["phase_id"]
                )
            ),
            None,
        )

    def acquisition_started(self, action_id, operation_id, started_at_ns):
        with self.owner._lock:
            report = self._report()
            if (
                not self.reconnect
                or self.reconnect["state"] != "PREPARATION_REQUESTED"
                or report is None
                or report["launch_session_id"] != self.owner.launch_id
                or action_id not in {a for _, a in ACQUISITIONS}
                or started_at_ns < report["reported_at_utc_ns"]
            ):
                return None
            if self.ledger is None:
                plan = self.owner._qualification_trial["plan"]["document"]
                self.ledger = dict(
                    schema="rocell.usb_phase_metadata_acquisition_ledger.v1",
                    source_sha256=self.owner.source_sha256,
                    session_id=plan["binding"]["session_id"],
                    launch_session_id=self.owner.launch_id,
                    trial_id=plan["binding"]["trial_id"],
                    phase_id=self.reconnect["phase_id"],
                    phase_started_at_utc_ns=self._start()["occurred_at_ns"],
                    entries=[],
                )
            index = [a for _, a in ACQUISITIONS].index(action_id)
            self.ledger["entries"] = self.ledger["entries"][:index]
            return dict(
                phase_id=self.reconnect["phase_id"],
                action_id=action_id,
                operation_id=operation_id,
                started_at_utc_ns=started_at_ns,
                source_sha256=self.owner.source_sha256,
                launch_session_id=self.owner.launch_id,
            )

    def acquisition_published(self, token, *, finished_at_ns, document, result_sha256):
        if token is None:
            return
        with self.owner._lock:
            report = self._report()
            if (
                not self.reconnect
                or self.reconnect["state"] != "PREPARATION_REQUESTED"
                or report is None
                or self.ledger is None
                or report["launch_session_id"] != self.owner.launch_id
                or token["phase_id"] != self.reconnect["phase_id"]
                or token["source_sha256"] != self.owner.source_sha256
                or token["launch_session_id"] != self.owner.launch_id
            ):
                return
            index = [a for _, a in ACQUISITIONS].index(token["action_id"])
            previous = (
                report["reported_at_utc_ns"]
                if index == 0
                else (
                    self.ledger["entries"][-1]["published_at_utc_ns"]
                    if len(self.ledger["entries"]) == index
                    else None
                )
            )
            now = time_ns()
            if (
                previous is None
                or not previous <= token["started_at_utc_ns"] <= finished_at_ns <= now
            ):
                return
            self.ledger["entries"].append(
                dict(
                    role=ACQUISITIONS[index][0],
                    action_id=token["action_id"],
                    operation_id=token["operation_id"],
                    started_at_utc_ns=token["started_at_utc_ns"],
                    finished_at_utc_ns=finished_at_ns,
                    published_at_utc_ns=now,
                    document_sha256=digest(canonical(document)),
                    result_sha256=result_sha256,
                    completion_logged=True,
                )
            )

    def _enrollment(self, native_camera, helper):
        # This seam has no BASELINE stage assumptions; it verifies exact current
        # owner/helper/three-document lineage and does not acquire anything.
        from .physical_usb_trial_service import _UsbTrialBaseline

        return _UsbTrialBaseline._enrollment(self, native_camera, helper)

    def context(self, native_camera, helper):
        result = dict(
            reconnect=self.reconnect, attempt=self.attempt, ledger=self.ledger
        )
        if self.reconnect and self.reconnect["state"] == "PREPARATION_REQUESTED":
            result.update(
                native_camera=(
                    None if native_camera is None else native_camera.export_snapshot()
                ),
                helper=None if helper is None else helper.export_snapshot(),
            )
        return result

    def fields(self, action, check, actor):
        return {
            BEGIN: (
                actor("operator_id", "Operator reporting the camera USB reconnection"),
                check("file_only", "Record a new interval only; no boot or USB query"),
                check(
                    "confirm_reconnected",
                    "I report manually reconnecting the declared camera USB cable/port after the retained physical-node absence",
                ),
            ),
            PREPARE: (
                actor(
                    "operator_id",
                    "Same operator label as the original reconnect report",
                ),
                check(
                    "file_only",
                    "Retain fresh reviewed metadata and inspect fixed files only",
                ),
            ),
            REVIEW: (
                actor(
                    "reviewer_id",
                    "Distinct reviewer label (not authenticated identity)",
                ),
                check(
                    "confirm_policy_review",
                    "Review the exact bounded descriptor-query policy",
                ),
                check(
                    "confirm_runtime_review", "Review the exact inspected fixed runtime"
                ),
                check(
                    "confirm_exact_target",
                    "Review this freshly observed camera target against the declared original unit",
                ),
                check(
                    "confirm_boot_metadata",
                    "Review one fixed local host-boot observation; no Windows restart",
                ),
            ),
            BOOT_COLLECT: (
                check(
                    "confirm_host_boot",
                    "Collect one owned local host/LastBootUpTime observation only",
                ),
                check(
                    "confirm_no_capture_or_arm",
                    "No USB query, camera capture, arm access, power, motion, restart or automatic retry",
                ),
            ),
            COLLECT: (
                check(
                    "confirm_usb_query",
                    "Run one separately admitted USB descriptor query; hub handles will be opened",
                ),
                check(
                    "confirm_no_capture_or_arm",
                    "No capture, settings, arm, power, motion, restart or automatic retry",
                ),
            ),
        }[action]

    def blocked_reason(self, action, workflow, native_camera, helper):
        if self.predecessor is None:
            return "Complete and publish the exact original physical-node ABSENT phase after a clean BASELINE first. Endpoint absence or unknown effects cannot substitute."
        if self.owner._attempt_key(action, workflow) in self.owner._attempted:
            return "This reconnect action was attempted already; export original diagnostics without replay."
        phase = workflow.get("usb_qualification_reconnect")
        if action == BEGIN:
            return (
                None
                if phase is None and self.attempt is None
                else "This reconnect interval already exists or was attempted; export without starting it again."
            )
        if phase is None or NEXT.get(phase["state"]) != action:
            return "Complete the preceding explicit reconnect action. Partial, requested or uncertain work is export-only."
        report = phase.get("operator_event")
        if (
            report is None
            or report["document"]["launch_session_id"] != self.owner.launch_id
        ):
            return "The reconnect report belongs to another app launch; export this historical interval without rebinding or retrying it."
        if (
            phase.get("original_campaign") is not None
            or phase.get("original_campaign_event") is not None
        ):
            return "An original reconnect campaign exists; do not replay it. Export its complete diagnostics."
        if action == PREPARE:
            try:
                self._enrollment(native_camera, helper)
            except (ValueError, TypeError, KeyError, AttributeError):
                return "After this reconnect report, acquire/review fresh generic and native metadata in this launch, then explicitly refresh the original session."
        return None

    def execution(self):
        record = (self.reconnect or {}).get("execution") or (
            (self.attempt or {}).get("records") or {}
        ).get("execution")
        if record is not None:
            evidence = OwnedUsbIdentityRunEvidence(canonical(record["document"]))
            _require(
                evidence.sha256 == record["evidence_sha256"],
                "USB_RECONNECT_EXECUTION_HASH_CHANGED",
            )
            return evidence
        original = (self.reconnect or {}).get("original_campaign") or (
            ((self.attempt or {}).get("dispatch") or {}).get("original")
        )
        if original and original.get("evidence") is not None:
            evidence = OwnedUsbIdentityRunEvidence(canonical(original["evidence"]))
            _require(
                evidence.sha256 == original["evidence_sha256"],
                "USB_RECONNECT_EXECUTION_HASH_CHANGED",
            )
            return evidence
        return None

    def boot_summary(self):
        attempt = (self.attempt or {}).get("boot") or {}
        record = (self.reconnect or {}).get("host_boot") or attempt.get("host_boot")
        if record is None:
            return None
        report = HostBootObservation(canonical(record["document"]))
        _require(
            report.sha256 == record["evidence_sha256"],
            "USB_RECONNECT_BOOT_HASH_CHANGED",
        )
        data = report.safe_summary()
        phase_id = (self.reconnect or self.attempt)["phase_id"]
        events = list((self.reconnect or {}).get("events", []))
        if attempt.get("terminal_event"):
            events.append(attempt["terminal_event"])
        state = "BOOT_REQUESTED" if attempt.get("requested_event") else "INCOMPLETE"
        for event in reversed(events):
            matched = next(
                (
                    name
                    for name in (
                        "BOOT_RETAINED",
                        "BOOT_HELD",
                        "BOOT_UNCERTAIN",
                        "BOOT_REQUESTED",
                    )
                    if event["detail_code"] == usb_reconnect_event(name, phase_id)
                ),
                None,
            )
            if matched:
                state = matched
                break
        prior = (
            _entry_history_boot(self.owner._workflow, "usb_qualification_absence")
            if self.predecessor is None
            else HostBootObservation(self.predecessor["absence_sources"]["host_boot"])
        )
        return dict(
            schema="rocell.wizard_usb_reconnect_boot_summary.v1",
            original_state=state,
            observation_sha256=report.sha256,
            status=data["status"],
            origin=data["origin"],
            host_key_sha256=data["host_key_sha256"],
            boot_key_sha256=data["boot_key_sha256"],
            last_boot_up_time_utc=(
                None
                if data["response"] is None
                else data["response"]["last_boot_up_time_utc"]
            ),
            process_status=data["process_status"],
            tree_exit_confirmed=data["tree_exit_confirmed"],
            blockers=data["blockers"],
            boot_relation=(
                "HELD"
                if prior is None
                else compare_boot_observations(prior, report)["status"]
            ),
            physical_authority=False,
            hardware_qualified=False,
            device_io_performed=False,
        )

    def _refresh_recommended(self):
        """Cached navigation only; the explicit Refresh action rechecks originals."""
        phase, ledger, report = self.reconnect, self.ledger, self._report()
        workflow = self.owner._workflow or {}
        if (
            not phase
            or phase["state"] != "PREPARATION_REQUESTED"
            or report is None
            or report["launch_session_id"] != self.owner.launch_id
            or phase.get("original_campaign") is not None
            or phase.get("original_campaign_event") is not None
            or ledger is None
            or len(ledger["entries"]) != 3
            or ledger["source_sha256"] != self.owner.source_sha256
            or workflow.get("binding", {}).get("source_sha256")
            != self.owner.source_sha256
            or ledger["launch_session_id"] != self.owner.launch_id
            or ledger["phase_id"] != phase["phase_id"]
            or (self.attempt is not None and self.attempt["action_id"] != BEGIN)
            or any(
                key.startswith(action + ":")
                for key in self.owner._attempted
                for action in ACTIONS - {BEGIN}
            )
        ):
            return False
        previous = report["reported_at_utc_ns"]
        for row, (role, action) in zip(ledger["entries"], ACQUISITIONS):
            if (
                row["role"] != role
                or row["action_id"] != action
                or row["completion_logged"] is not True
                or not previous
                <= row["started_at_utc_ns"]
                <= row["finished_at_utc_ns"]
                <= row["published_at_utc_ns"]
            ):
                return False
            previous = row["published_at_utc_ns"]
        return True

    def projection(self, value):
        if not self.has_diagnostics() and self.predecessor is None:
            return deepcopy(value)
        from .physical_usb_identity_service import _observation

        value = deepcopy(value)
        value.update(
            schema="rocell.wizard_usb_qualification.v4", reconnect=None, meaning=MEANING
        )
        current = value["publication"]["status"] == "CURRENT"
        phase = self.reconnect
        if phase:
            prep = phase.get("preparation")
            data = (
                None
                if prep is None
                else UsbReconnectPreparation(canonical(prep["document"])).to_dict()
            )
            report = self._report()
            target = None
            if data:
                selected = PhysicalCameraSelection(
                    canonical(data["operation"]["selection"])
                )
                identity = selected.identity_document
                target = dict(
                    selection_sha256=selected.sha256,
                    native_identity_sha256=identity["native_identity_sha256"],
                    endpoint_sha256=identity["endpoint_sha256"],
                    symbolic_link=identity["symbolic_link"],
                    device_instance_id=identity["metadata_review"][
                        "observed_instance_id"
                    ],
                )
            record = phase.get("phase_record")
            final = None
            if record:
                parsed = UsbReconnectQualificationPhase(canonical(record["document"]))
                _require(
                    parsed.sha256 == record["evidence_sha256"],
                    "USB_RECONNECT_PHASE_HASH_CHANGED",
                )
                final = dict(
                    phase_sha256=parsed.sha256,
                    **{
                        key: parsed.to_dict()[key]
                        for key in (
                            "status",
                            "boot_relation",
                            "values",
                            "comparisons",
                            "checks",
                            "missing_requirements",
                        )
                    },
                )
            evidence = self.execution()
            value["reconnect"] = dict(
                phase_id=phase["phase_id"],
                state=phase["state"],
                phase_start_event_sha256=(
                    None if self._start() is None else self._start()["event_sha256"]
                ),
                phase_started_at_utc_ns=(
                    None if self._start() is None else self._start()["occurred_at_ns"]
                ),
                operator_event=(
                    None
                    if report is None
                    else dict(
                        evidence_sha256=phase["operator_event"]["evidence_sha256"],
                        **{
                            key: report[key]
                            for key in (
                                "operator_id",
                                "launch_session_id",
                                "reported_at_utc_ns",
                                "event",
                            )
                        },
                    )
                ),
                acquisition_ledger=deepcopy(self.ledger),
                preparation=(
                    None
                    if data is None
                    else dict(
                        preparation_sha256=prep["evidence_sha256"],
                        **{
                            key: data[key]
                            for key in (
                                "operator_id",
                                "prepared_at_utc_ns",
                                "enrollment_sha256",
                                "operation_sha256",
                            )
                        },
                        runtime_registration_sha256=data["runtime_report"][
                            "runtime_registration_sha256"
                        ],
                        file_count=len(data["runtime_report"]["files"]),
                    )
                ),
                target=target,
                review=(
                    None
                    if not phase.get("identity") or not phase.get("boot_request")
                    else dict(
                        identity_sha256=phase["identity"]["evidence_sha256"],
                        policy_review_sha256=phase["policy_review"]["evidence_sha256"],
                        runtime_review_sha256=phase["runtime_review"][
                            "evidence_sha256"
                        ],
                        operator_id=phase["policy_review"]["document"]["operator_id"],
                        reviewer_id=phase["policy_review"]["document"]["reviewer_id"],
                        review_launch_id=phase["runtime_review"]["document"][
                            "launch_session_id"
                        ],
                        boot_request_sha256=phase["boot_request"]["evidence_sha256"],
                    )
                ),
                host_boot=self.boot_summary(),
                execution=None if evidence is None else evidence.safe_summary(),
                observation=_observation(evidence),
                phase_record=final,
                **FLAGS,
            )
            if current:
                value["status"] = (
                    "RECONNECT_RETAINED_BLOCKED"
                    if phase["state"] == "RETAINED_BLOCKED"
                    else (
                        "RECONNECT_ACTIVE"
                        if phase["state"] in NEXT
                        else "INCOMPLETE_HELD"
                    )
                )
                if (
                    report is not None
                    and report["launch_session_id"] != self.owner.launch_id
                ):
                    value["status"] = "HISTORICAL_HELD"
                    value["publication"] = dict(
                        status="HISTORICAL_HELD", operation_id=None
                    )
                    current = False
        value["next_action"] = (
            (
                BEGIN
                if phase is None
                and self.predecessor is not None
                and self.attempt is None
                else NEXT.get((phase or {}).get("state"), EXPORT)
            )
            if current
            else None
        )
        if (
            not current
            and self.has_diagnostics()
            and value["publication"]["status"] == "HISTORICAL_HELD"
        ):
            value["next_action"] = (
                "physical_camera_refresh" if self._refresh_recommended() else EXPORT
            )
        if value["publication"]["status"] == "PENDING":
            value.update(
                reconnect=None, next_action=None, status="NOT_DECLARED", plan=None
            )
        return value

    def _retain(self, tx, payload, role, phase_id):
        import json

        _require(
            type(payload) is bytes
            and 0 < len(payload) <= USB_RECONNECT_ROLE_BYTES[role],
            "USB_RECONNECT_ROLE_LIMIT",
        )
        record = dict(
            document=json.loads(payload),
            evidence_sha256=digest(payload),
            reference=None,
            retention="COLLECTED_NOT_M1_RETAINED",
        )
        self.attempt["records"][role] = record
        ref = tx.store_evidence(
            STAGE,
            payload,
            label=usb_reconnect_label(role, phase_id),
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        record.update(
            reference=ref.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        _require(
            tx.read_stage_evidence(ref) == payload, "USB_RECONNECT_READBACK_CHANGED"
        )
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        return ref

    def _commit(self, tx, event, state, phase_id, refs):
        snapshot = tx.commit_stage_state(
            STAGE,
            state,
            occurred_at_ns=time_ns(),
            detail_code=usb_reconnect_event(event, phase_id),
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=tuple(sorted(refs, key=lambda ref: ref.evidence_id)),
        )
        committed = snapshot.committed_events[-1]
        # Preserve the exact already-known original before a later source,
        # cancellation or outer readback failure. This cache is diagnostic
        # coverage only and cannot resume or publish the original interval.
        self.attempt.setdefault("events", []).append(committed.to_dict())
        return committed

    def _refresh(self, cancellation, progress, deadline):
        from .physical_usb_trial_service import _UsbTrialBaseline

        return _UsbTrialBaseline._refresh(self, cancellation, progress, deadline)

    def perform(
        self, action, values, *, cancellation, progress, deadline, native_camera, helper
    ):
        owner, setup = self.owner, self.owner.setup
        workflow, session = setup.original_source_workflow(), setup.session
        predecessor = _predecessor(workflow)
        plan = predecessor["original_baseline"]["plan"]
        phase = workflow.get("usb_qualification_reconnect")
        phase_id = "usbphase-" + uuid4().hex if phase is None else phase["phase_id"]
        binding = canonical(session.descriptor())
        enrollment = selection = None
        if action == PREPARE:
            _require(
                values["operator_id"]
                == phase["operator_event"]["document"]["operator_id"],
                "USB_RECONNECT_OPERATOR_CHANGED",
            )
            enrollment, selection = self._enrollment(native_camera, helper)
        with owner._lock:
            self.attempt = dict(
                action_id=action,
                phase_id=phase_id,
                records={},
                boot=None,
                dispatch=None,
                acquisition_ledger=deepcopy(self.ledger),
            )
            owner._attempted.add(owner._attempt_key(action, workflow))
            owner.invalidate()
            owner._dispatch = owner._dispatch_result = None
            generation = owner._generation
            self.query_attempted = False

        def guard():
            owner._check(cancellation, deadline)
            _require(
                owner._generation == generation
                and setup.session is session
                and canonical(session.descriptor()) == binding,
                "USB_RECONNECT_LIVE_CONTEXT_CHANGED",
            )

        try:
            with setup.usb_reconnect_transaction(
                cancellation=cancellation, progress=progress, deadline_ns=deadline
            ) as (prerequisites, current):
                _require(
                    canonical(current) == canonical(workflow),
                    "USB_RECONNECT_ORIGINAL_CHANGED",
                )
                guard()
                verification = session.view()["verification"]
                with session.stage_transaction(
                    expected_challenge_sha256=verification["challenge_sha256"]
                ) as tx:
                    if action == BEGIN:
                        absence_ref = predecessor["absence_reference"]
                        _require(
                            tx.read_stage_evidence(absence_ref)
                            == predecessor["absence"].payload,
                            "USB_RECONNECT_ABSENCE_CHANGED",
                        )
                        start = self._commit(
                            tx,
                            "PREPARATION_REQUESTED",
                            V2StageState.WAITING_OPERATOR,
                            phase_id,
                            [absence_ref],
                        )
                        guard()
                        event = build_usb_reconnect_operator_event(
                            plan=plan,
                            absence=predecessor["absence"],
                            phase_id=phase_id,
                            launch_session_id=owner.launch_id,
                            operator_id=values["operator_id"],
                            phase_started_at_utc_ns=start.occurred_at_ns,
                            reported_at_utc_ns=time_ns(),
                        )
                        self._retain(tx, event.payload, "operator_event", phase_id)
                    elif action == PREPARE:
                        policy = inspect_usb_identity_stage_policy(owner.workspace)
                        runtime = usb_identity_runtime_candidate(
                            owner.workspace, source_sha256=owner.source_sha256
                        )
                        operation = usb_identity_phase_operation(
                            plan=plan,
                            phase="AFTER_RECONNECT",
                            operation_id=phase_id,
                            predecessor_sha256=predecessor["absence"].sha256,
                            selection=selection,
                            runtime=runtime,
                            policy=policy,
                        )
                        report = inspect_usb_identity_runtime(
                            runtime,
                            cancellation=cancellation,
                            deadline_ns=deadline,
                            progress=progress,
                        )
                        self.attempt["runtime_report"] = deepcopy(report)
                        owner._read_records(tx, [phase["operator_event"]], guard)
                        raw = canonical(enrollment)
                        ref = self._retain(tx, raw, "enrollment", phase_id)
                        from .physical_usb_reconnect_phase import (
                            UsbReconnectOperatorEvent,
                        )

                        preparation = build_usb_reconnect_preparation(
                            **predecessor,
                            phase_start_event=_parse_event(self._start()),
                            phase_id=phase_id,
                            operator_event=UsbReconnectOperatorEvent(
                                canonical(phase["operator_event"]["document"])
                            ),
                            operator_event_reference=_reference(
                                phase["operator_event"]
                            ),
                            enrollment=raw,
                            enrollment_reference=ref,
                            acquisition_ledger=deepcopy(self.ledger),
                            operation=operation,
                            runtime_report=report,
                            prepared_at_utc_ns=time_ns(),
                            operator_id=values["operator_id"],
                        )
                        guard()
                        prep_ref = self._retain(
                            tx, preparation.payload, "preparation", phase_id
                        )
                        op_ref = self._retain(
                            tx, operation.payload, "operation", phase_id
                        )
                        self._commit(
                            tx,
                            "PREPARED",
                            V2StageState.REVIEW_PENDING,
                            phase_id,
                            [
                                _reference(phase["operator_event"]),
                                ref,
                                prep_ref,
                                op_ref,
                            ],
                        )
                    elif action == REVIEW:
                        self._review(tx, phase, plan, values, guard)
                    elif action == BOOT_COLLECT:
                        intent = UsbReconnectBootIntent(
                            canonical(phase["boot_request"]["document"])
                        )
                        collector = OriginalUsbReconnectBootCollector(
                            owner.workspace, intent
                        )
                        try:
                            collector.collect(
                                tx,
                                intent_reference=_reference(phase["boot_request"]),
                                cancellation=cancellation,
                                deadline_ns=deadline,
                                revalidate_context=guard,
                            )
                        finally:
                            self.attempt["boot"] = collector.retained_diagnostics()
                    elif action == COLLECT:
                        refs = owner._read_records(
                            tx,
                            [
                                phase[role]
                                for role in ("identity", "boot_request", "host_boot")
                            ],
                            guard,
                        )
                        self._commit(
                            tx,
                            "QUERY_REQUESTED",
                            V2StageState.WAITING_OPERATOR,
                            phase_id,
                            refs,
                        )
                guard()
                if action == COLLECT:
                    current = self._refresh(cancellation, progress, deadline)
                    self.reconnect = deepcopy(current["usb_qualification_reconnect"])
                    self._collect_usb(
                        current, prerequisites, predecessor, guard, cancellation
                    )
                guard()
            owner._check(cancellation, deadline)
            with owner._lock:
                owner._adopt()
                return owner._result(action)
        except BaseException:
            owner.invalidate()
            setup.invalidate()
            raise

    def _review(self, tx, phase, plan, values, guard):
        owner, phase_id = self.owner, phase["phase_id"]
        roles = ("operator_event", "enrollment", "preparation", "operation")
        refs = owner._read_records(tx, [phase[role] for role in roles], guard)
        preparation = UsbReconnectPreparation(
            canonical(phase["preparation"]["document"])
        )
        data = preparation.to_dict()
        operation = UsbIdentityOperation(canonical(phase["operation"]["document"]))
        _require(
            operation.payload == canonical(data["operation"]),
            "USB_RECONNECT_OPERATION_CHANGED",
        )
        op = operation.to_dict()
        policy = inspect_usb_identity_stage_policy(owner.workspace)
        _require(op["policy_sha256"] == policy.sha256, "USB_RECONNECT_POLICY_CHANGED")
        selection = PhysicalCameraSelection(canonical(op["selection"]))
        sd = selection.identity_document
        reviewer, operator = values["reviewer_id"], data["operator_id"]
        policy_review = UsbIdentityPolicyReview(
            canonical(
                dict(
                    schema="rocell.usb_identity_stage_policy_review.v1",
                    **{
                        key: plan.to_dict()["binding"][key]
                        for key in (
                            "cell_id",
                            "session_id",
                            "source_sha256",
                            "header_sha256",
                        )
                    },
                    policy=policy.to_dict(),
                    policy_sha256=policy.sha256,
                    operator_id=operator,
                    reviewer_id=reviewer,
                    reviewed_at_utc_ns=time_ns(),
                    purpose="REVIEW_EXACT_USB_QUERY_POLICY_ONLY",
                    **FLAGS,
                    motion_authorized=False,
                    contact_authorized=False,
                )
            )
        )
        runtime_review = review_usb_identity_runtime(
            UsbIdentityRuntimeRegistration(canonical(op["runtime"])),
            selection_sha256=selection.sha256,
            native_identity_sha256=sd["native_identity_sha256"],
            endpoint_sha256=sd["endpoint_sha256"],
            device_instance_id_sha256=digest(
                sd["metadata_review"]["observed_instance_id"].encode("utf-8")
            ),
            operation_sha256=operation.sha256,
            operator_id=operator,
            reviewer_id=reviewer,
            launch_session_id=owner.launch_id,
            reviewed_at_ns=time_ns(),
        )
        guard()
        pr = self._retain(tx, policy_review.payload, "policy_review", phase_id)
        rr = self._retain(tx, runtime_review.payload, "runtime_review", phase_id)
        rd = runtime_review.to_dict()
        identity = UsbIdentityAdmissionIdentity(
            canonical(
                dict(
                    schema="rocell.usb_identity_admission_identity.v1",
                    **{
                        key: plan.to_dict()["binding"][key]
                        for key in (
                            "cell_id",
                            "session_id",
                            "source_sha256",
                            "header_sha256",
                        )
                    },
                    stage_policy_sha256=policy.sha256,
                    policy_review_sha256=policy_review.sha256,
                    runtime_review_sha256=runtime_review.sha256,
                    runtime_registration_sha256=digest(canonical(op["runtime"])),
                    **{
                        key: rd[key]
                        for key in (
                            "selection_sha256",
                            "native_identity_sha256",
                            "endpoint_sha256",
                            "device_instance_id_sha256",
                            "operation_sha256",
                        )
                    },
                    original_subjects=[
                        dict(
                            role=role,
                            reference=ref.to_dict(),
                            document_sha256=ref.payload_sha256,
                        )
                        for role, ref in zip(
                            ("metadata", "policy_review", "runtime_review"),
                            (refs[1], pr, rr),
                        )
                    ],
                )
            )
        )
        ir = self._retain(tx, identity.payload, "identity", phase_id)
        intent = build_usb_reconnect_boot_intent(
            preparation=preparation,
            preparation_reference=_reference(phase["preparation"]),
        )
        br = self._retain(tx, intent.payload, "boot_request", phase_id)
        guard()
        self._commit(
            tx, "REVIEWED", V2StageState.BLOCKED, phase_id, [*refs, pr, rr, ir, br]
        )

    def _collect_usb(self, workflow, prerequisites, predecessor, guard, cancellation):
        owner = self.owner
        phase = workflow["usb_qualification_reconnect"]
        _require(
            phase["state"] == "QUERY_REQUESTED"
            and phase["original_campaign"] is None
            and phase["original_campaign_event"] is None,
            "USB_RECONNECT_ORIGINAL_ATTEMPT_EXISTS",
        )
        operation = UsbIdentityOperation(canonical(phase["operation"]["document"]))
        campaign = PhysicalUsbIdentityCampaign(
            operation,
            identity=UsbIdentityAdmissionIdentity(
                canonical(phase["identity"]["document"])
            ),
            review=UsbIdentityRuntimeReview(
                canonical(phase["runtime_review"]["document"])
            ),
        )
        policy = UsbIdentityStagePolicy(
            canonical(phase["policy_review"]["document"]["policy"])
        )
        runtime = owner.setup.session._store._runtime
        _require(
            type(runtime) is PhysicalOnboardingM1Runtime
            and runtime.source_binding_sha256
            == physical_camera_source_binding(owner.source_sha256),
            "USB_EXACT_ORIGINAL_RUNTIME_REQUIRED",
        )
        persistence = M1PhysicalUsbIdentityPersistence(
            runtime,
            workspace_source_sha256=owner.source_sha256,
            stage_policy=policy,
            expected_usb_query_policy_sha256=policy.sha256,
            admission_facts=owner._facts_provider(
                workflow, prerequisites, campaign, guard
            ),
        )
        dispatcher = PhysicalUsbIdentityDispatchOwner(
            persistence, campaign, revalidate_context=guard
        )
        owner._dispatch = dispatcher
        self.query_attempted = True
        try:
            owner._dispatch_result = dispatcher.perform(
                request_key="usb-reconnect-" + phase["phase_id"],
                cancellation=cancellation,
            )
        finally:
            self.attempt["dispatch"] = dispatcher.retained_diagnostics()
        original = dispatcher.retained_diagnostics()["original"]
        guard()
        evidence = (
            None
            if not original or original.get("evidence") is None
            else OwnedUsbIdentityRunEvidence(canonical(original["evidence"]))
        )
        effects = None if evidence is None else evidence.bounded_effect_summary()
        if not (
            original
            and original["result"]["state"] == "SEALED_KNOWN"
            and effects
            and effects["current_complete"]
            and effects["process_cleanup_confirmed"]
            and effects["usb_cleanup_confirmed"]
        ):
            return
        # The exact independently retained permit is indispensable: descriptor
        # evidence has only its hash; do not reconstruct a permit from that hash.
        from .commissioning_usb_identity_persistence import (
            decode_physical_usb_identity_permit,
        )

        permit = decode_physical_usb_identity_permit(original["permit"])
        verified = persistence.verification(workflow["binding"]["session_id"])
        with persistence.stage_transaction(
            workflow["binding"]["session_id"],
            expected_challenge_sha256=verified.challenge_sha256,
        ) as tx:
            roles = tuple(USB_RECONNECT_ROLE_BYTES)[:-2]
            owner._read_records(tx, [phase[role] for role in roles], guard)
            er = self._retain(tx, evidence.payload, "execution", phase["phase_id"])
            final = build_usb_reconnect_qualification_phase(
                original_baseline=predecessor["original_baseline"],
                absence=predecessor["absence"],
                absence_sources=predecessor["absence_sources"],
                permit=permit,
                context=dict(
                    operator_id=phase["preparation"]["document"]["operator_id"],
                    launch_session_id=owner.launch_id,
                    operation_id=phase["phase_id"],
                    started_at_utc_ns=self._start()["occurred_at_ns"],
                    finished_at_utc_ns=time_ns(),
                ),
                sources=dict(
                    operation=operation.payload,
                    operator_event=canonical(phase["operator_event"]["document"]),
                    native_enrollment=canonical(phase["enrollment"]["document"]),
                    owned_usb_run=evidence.payload,
                    host_boot=canonical(phase["host_boot"]["document"]),
                ),
                references=dict(
                    operation=_reference(phase["operation"]),
                    operator_event=_reference(phase["operator_event"]),
                    native_enrollment=_reference(phase["enrollment"]),
                    owned_usb_run=er,
                    host_boot=_reference(phase["host_boot"]),
                ),
            )
            fr = self._retain(tx, final.payload, "phase_record", phase["phase_id"])
            guard()
            self._commit(
                tx,
                "RETAINED",
                V2StageState.BLOCKED,
                phase["phase_id"],
                [*[_reference(phase[role]) for role in roles], er, fr],
            )
            guard()
