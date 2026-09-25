"""Private five-action composition; the existing USB owner owns publication.

No provider is constructed on import, adoption, view or prepare-ticket calls.
Only explicit boot/query actions enter their independently reviewed one-shot
original scopes. A stored request or partial prefix is never replayed.
"""

from copy import deepcopy
import json
from time import time_ns
from uuid import uuid4

from .physical_camera_usb_absence import (
    UsbAbsencePreparation,
    build_usb_absence_preparation,
    original_usb_absence_baseline,
)
from .physical_camera_usb_absence_constants import (
    USB_ABSENCE_ROLE_BYTES,
    usb_absence_event,
    usb_absence_label,
)
from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_v2 import V2StageState, _parse_event
from .physical_usb_absence_boot import (
    OriginalUsbAbsenceBootCollector,
    UsbAbsenceBootIntent,
    UsbAbsenceBootReview,
    build_usb_absence_boot_intent,
    review_usb_absence_boot_intent,
)
from .physical_usb_presence_binding import (
    UsbPresencePhaseBinding,
    build_usb_presence_phase_binding,
)
from .physical_usb_presence_campaign import (
    PhysicalUsbPresenceCampaign,
    UsbPresenceOperation,
    usb_presence_operation,
)
from .physical_usb_presence_dispatch import PhysicalUsbPresenceDispatchOwner
from .physical_usb_presence_phase import (
    UsbPresenceOperatorEvent,
    build_usb_presence_operator_event,
    build_usb_presence_qualification_phase,
)
from .usb_presence_stage_policy import inspect_usb_presence_stage_policy
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    compare_boot_observations,
)
from rocell.providers.windows.owned_usb_presence_evidence import (
    OwnedUsbPresenceRunEvidence,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.providers.windows.usb_presence_registration import (
    UsbPresenceRuntimeRegistration,
    inspect_usb_presence_runtime,
    usb_presence_runtime_candidate,
)
from rocell.providers.windows.usb_presence_review import (
    UsbPresenceRuntimeReview,
    review_usb_presence_runtime,
)

BEGIN = "physical_usb_absence_begin"
BOOT_REVIEW = "physical_usb_absence_boot_review"
BOOT_COLLECT = "physical_usb_absence_boot_collect"
RUNTIME_REVIEW = "physical_usb_absence_runtime_review"
COLLECT = "physical_usb_absence_collect"
ACTIONS = frozenset((BEGIN, BOOT_REVIEW, BOOT_COLLECT, RUNTIME_REVIEW, COLLECT))
RESULT_SCHEMA = "rocell.wizard_usb_absence_action_result.v1"
STAGE = STAGE_ORDER[3]
MEANING = (
    "Operator-reported unplug followed by a separately reviewed local boot observation "
    "and two bounded exact physical USB-node samples. Not camera-endpoint absence, "
    "mechanical unplug proof, continuous absence or completed reconnect/reboot qualification. "
    "No camera capture, arm, power or motion authority. Stop is software cancellation, "
    "not a robot emergency stop. Export uncertain originals; never replay a request."
)
FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    camera_capture_authorized=False,
    arm_access_authorized=False,
)
_NEXT = {
    "PREPARED": BOOT_REVIEW,
    "BOOT_REVIEWED": BOOT_COLLECT,
    "PRESENCE_REVIEW_PREPARED": RUNTIME_REVIEW,
    "RUNTIME_REVIEWED": COLLECT,
}


def _require(ok, code):
    from .physical_usb_identity_service import _require as require

    require(ok, code)


def _reference(record):
    from .physical_usb_identity_service import _reference as reference

    return reference(record)


class _UsbTrialAbsence:
    def __init__(self, owner):
        self.owner = owner
        self.absence = self.attempt = self.binding = None
        self.dispatch = self.dispatch_result = None
        self.query_attempted = False

    def adopt(self, workflow):
        self.absence = deepcopy(workflow.get("usb_qualification_absence"))
        self.binding = None
        try:
            original = original_usb_absence_baseline(workflow)
            self.binding = build_usb_presence_phase_binding(**original)
        except (ValueError, TypeError, KeyError):
            pass

    def invalidate(self):
        if self.dispatch is not None:
            self.dispatch.invalidate()

    def context(self):
        return dict(
            absence=self.absence,
            attempt=self.attempt,
            binding_sha256=None if self.binding is None else self.binding.sha256,
        )

    def has_diagnostics(self):
        return self.absence is not None or self.attempt is not None

    def diagnostics(self, workflow):
        if not self.has_diagnostics():
            return {}
        return dict(
            qualification_absence=deepcopy(
                workflow.get("usb_qualification_absence") or self.absence
            ),
            qualification_absence_attempt=deepcopy(self.attempt),
        )

    def fields(self, action, check, actor):
        return {
            BEGIN: (
                actor("operator_id", "Reporting operator label"),
                check(
                    "confirm_unplug_report",
                    "I report manually unplugging the declared camera USB connection; this is not proof of physical absence",
                ),
                check(
                    "confirm_file_inspection",
                    "Record this report and inspect the fixed presence files only; no boot or USB query",
                ),
            ),
            BOOT_REVIEW: (
                actor("reviewer_id", "Distinct boot-scope reviewer label"),
                check(
                    "confirm_exact_boot_scope",
                    "Review the exact original local host-boot intent; no USB, reboot or camera permission",
                ),
            ),
            BOOT_COLLECT: (
                check(
                    "confirm_boot_observation",
                    "Run the reviewed local host-boot observation once",
                ),
                check(
                    "confirm_no_usb_query",
                    "This step performs no USB query and does not automatically run the next step",
                ),
            ),
            RUNTIME_REVIEW: (
                actor("reviewer_id", "Distinct presence-scope reviewer label"),
                check(
                    "confirm_policy_review",
                    "Review the exact bounded physical-node presence policy",
                ),
                check(
                    "confirm_runtime_review",
                    "Review the exact fixed runtime and operation",
                ),
                check(
                    "confirm_exact_target",
                    "Review the literal physical USB target retained by the completed BASELINE, not a live camera endpoint",
                ),
            ),
            COLLECT: (
                check(
                    "confirm_presence_query",
                    "Run one bounded exact physical USB-node presence query; no automatic retry",
                ),
                check(
                    "confirm_no_capture_or_arm",
                    "No capture, arm, power or motion authority; Stop is software cancellation, not an emergency stop",
                ),
            ),
        }.get(action, ())

    def blocked_reason(self, action, workflow):
        if self.binding is None:
            return "A complete original physical-origin BASELINE with known clean boot and USB observations is required; export held evidence."
        if self.owner._attempt_key(action, workflow) in self.owner._attempted:
            return "This original absence action was attempted; refresh/export without replay."
        verification = self.owner.setup.session.view().get("verification")
        if (
            not verification
            or verification.get("effects_allowed_by_m1_storage") is not True
        ):
            return "Original storage is held or unverified; export evidence without clearing quarantine."
        a = workflow.get("usb_qualification_absence")
        if action == BEGIN:
            return (
                None
                if a is None and self.attempt is None
                else "The original absence interval already exists or was attempted; export without repeating it."
            )
        if a is None or _NEXT.get(a["state"]) != action:
            return "Complete the preceding exact absence step; partial, requested, held or uncertain records cannot be automatically resumed."
        operation = a.get("operation")
        if (
            operation is None
            or operation["document"]["launch_session_id"] != self.owner.launch_id
        ):
            return "Prepared absence belongs to another application launch; inspect/export it without rebinding or replay."
        return None

    def execution(self):
        record = (self.absence or {}).get("execution")
        if record is None:
            record = ((self.attempt or {}).get("records") or {}).get("execution")
        if record is not None:
            evidence = OwnedUsbPresenceRunEvidence(canonical(record["document"]))
            _require(
                evidence.sha256 == record["evidence_sha256"],
                "ABSENCE_EXECUTION_HASH_CHANGED",
            )
            return evidence
        original = (self.absence or {}).get("original_campaign")
        if original is None:
            original = ((self.attempt or {}).get("dispatch") or {}).get("original")
        if original and original.get("evidence") is not None:
            evidence = OwnedUsbPresenceRunEvidence(canonical(original["evidence"]))
            _require(
                evidence.sha256 == original["evidence_sha256"],
                "ABSENCE_ORIGINAL_EXECUTION_HASH_CHANGED",
            )
            return evidence
        return None

    def boot_summary(self):
        record = (self.absence or {}).get("host_boot")
        attempt = (self.attempt or {}).get("boot") or {}
        record = record or attempt.get("host_boot")
        if record is None:
            return None
        report = HostBootObservation(canonical(record["document"]))
        _require(
            report.sha256 == record["evidence_sha256"], "ABSENCE_BOOT_HASH_CHANGED"
        )
        data = report.safe_summary()
        events = list((self.absence or {}).get("events", []))
        if attempt.get("terminal_event"):
            events.append(attempt["terminal_event"])
        phase_id = (self.absence or self.attempt)["phase_id"]
        state = "BOOT_REQUESTED" if attempt.get("requested_event") else "INCOMPLETE"
        for event in reversed(events):
            state_match = next(
                (
                    s
                    for s in (
                        "BOOT_RETAINED",
                        "BOOT_HELD",
                        "BOOT_UNCERTAIN",
                        "BOOT_REQUESTED",
                    )
                    if event["detail_code"] == usb_absence_event(s, phase_id)
                ),
                None,
            )
            if state_match:
                state = state_match
                break
        baseline_record = (
            (self.owner._workflow or {}).get("usb_qualification_baseline") or {}
        ).get("host_boot")
        relation = (
            "HELD"
            if baseline_record is None
            else compare_boot_observations(
                HostBootObservation(canonical(baseline_record["document"])), report
            )["status"]
        )
        return dict(
            schema="rocell.wizard_usb_absence_boot_summary.v1",
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
            boot_relation=relation,
            physical_authority=False,
            hardware_qualified=False,
            device_io_performed=False,
        )

    def projection(self, value):
        if not self.has_diagnostics() and self.binding is None:
            return value
        value = deepcopy(value)
        value.update(
            schema="rocell.wizard_usb_qualification.v3", absence=None, meaning=MEANING
        )
        a = self.absence
        if a is not None:
            operation = a.get("operation")
            op = None if operation is None else operation["document"]
            prepared = a.get("preparation")
            boot_review, review = a.get("boot_review"), a.get("runtime_review")
            execution = self.execution()
            observation = None if execution is None else execution.observation
            phase = a.get("phase_record")
            value["absence"] = dict(
                phase_id=a["phase_id"],
                phase="RECONNECT_ABSENCE",
                state=a["state"],
                phase_start_event_sha256=(
                    None if not a["events"] else a["events"][0]["event_sha256"]
                ),
                phase_started_at_utc_ns=(
                    None if not a["events"] else a["events"][0]["occurred_at_ns"]
                ),
                target=(
                    None
                    if op is None
                    else dict(
                        physical_usb_instance_id=op["phase_binding"]["target"][
                            "physical_usb_instance_id"
                        ],
                        physical_device_id=op["phase_binding"]["target"][
                            "physical_device_id"
                        ],
                        phase_binding_sha256=digest(canonical(op["phase_binding"])),
                        baseline_sha256=op["phase_binding"]["baseline"]["sha256"],
                        operation_sha256=operation["evidence_sha256"],
                        runtime_registration_sha256=digest(canonical(op["runtime"])),
                        policy_sha256=op["policy_sha256"],
                        launch_session_id=op["launch_session_id"],
                    )
                ),
                operator_event=(
                    None
                    if a.get("operator_event") is None
                    else dict(
                        evidence_sha256=a["operator_event"]["evidence_sha256"],
                        **{
                            k: a["operator_event"]["document"][k]
                            for k in ("operator_id", "event", "reported_at_utc_ns")
                        }
                    )
                ),
                preparation=(
                    None
                    if prepared is None
                    else UsbAbsencePreparation(
                        canonical(prepared["document"])
                    ).safe_summary()
                ),
                boot_intent_sha256=(
                    None
                    if a.get("boot_intent") is None
                    else a["boot_intent"]["evidence_sha256"]
                ),
                boot_review=(
                    None
                    if boot_review is None
                    else dict(
                        evidence_sha256=boot_review["evidence_sha256"],
                        **{
                            k: boot_review["document"][k]
                            for k in (
                                "operator_id",
                                "reviewer_id",
                                "launch_session_id",
                                "intent_sha256",
                            )
                        }
                    )
                ),
                host_boot=self.boot_summary(),
                runtime_review=(
                    None
                    if review is None
                    else dict(
                        evidence_sha256=review["evidence_sha256"],
                        **{
                            k: review["document"][k]
                            for k in (
                                "operator_id",
                                "reviewer_id",
                                "launch_session_id",
                                "operation_sha256",
                                "helper_sha256",
                                "usb_presence_policy_sha256",
                            )
                        }
                    )
                ),
                execution=None if execution is None else execution.safe_summary(),
                observation=None if observation is None else observation.safe_summary(),
                phase_record=(
                    None
                    if phase is None
                    else dict(
                        phase_sha256=phase["evidence_sha256"],
                        **{
                            k: phase["document"][k]
                            for k in (
                                "status",
                                "presence_outcome",
                                "boot_relation",
                                "checks",
                                "missing_requirements",
                                "physical_node_absence_observed",
                            )
                        }
                    )
                ),
                **FLAGS
            )
        current = value["publication"]["status"] == "CURRENT"
        if current:
            value["next_action"] = None
            if a is not None:
                value["status"] = (
                    "ABSENCE_RETAINED_BLOCKED"
                    if a["state"] == "RETAINED_BLOCKED"
                    else "ABSENCE_ACTIVE" if a["state"] in _NEXT else "INCOMPLETE_HELD"
                )
                if (
                    a.get("operation")
                    and a["operation"]["document"]["launch_session_id"]
                    != self.owner.launch_id
                ):
                    value["status"] = "HISTORICAL_HELD"
            candidate = BEGIN if a is None else _NEXT.get(a["state"])
            value["next_action"] = (
                candidate
                if candidate and self.owner.blocked_reason(candidate) is None
                else "physical_usb_identity_export"
            )
        else:
            value["next_action"] = None
        if value["publication"]["status"] == "PENDING":
            value.update(
                absence=None,
                baseline=None,
                plan=None,
                next_action=None,
                status="NOT_DECLARED",
            )
        return value

    def _retain(self, tx, artifact, role, phase_id):
        payload = artifact.payload
        _require(0 < len(payload) <= USB_ABSENCE_ROLE_BYTES[role], "ABSENCE_ROLE_LIMIT")
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
            label=usb_absence_label(role, phase_id),
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        record.update(
            reference=ref.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        _require(tx.read_stage_evidence(ref) == payload, "ABSENCE_READBACK_CHANGED")
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        return ref

    def _commit(self, tx, kind, state, phase_id, refs, trial_id=None):
        snapshot = tx.commit_stage_state(
            STAGE,
            state,
            occurred_at_ns=time_ns(),
            detail_code=usb_absence_event(kind, phase_id, trial_id=trial_id),
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=tuple(sorted(refs, key=lambda r: r.evidence_id)),
        )
        event = snapshot.committed_events[-1]
        self.attempt["events"].append(event.to_dict())
        return event

    def perform(self, action, values, *, cancellation, progress, deadline):
        owner, setup = self.owner, self.owner.setup
        workflow, session = setup.original_source_workflow(), setup.session
        original = original_usb_absence_baseline(workflow)
        a = workflow.get("usb_qualification_absence")
        phase_id = "usbphase-" + uuid4().hex if a is None else a["phase_id"]
        descriptor = canonical(session.descriptor())
        with owner._lock:
            self.attempt = dict(
                action_id=action,
                phase_id=phase_id,
                records={},
                events=[],
                boot=None,
                dispatch=None,
            )
            self.query_attempted = False
            owner._attempted.add(owner._attempt_key(action, workflow))
            owner.invalidate()
            self.dispatch = self.dispatch_result = None
            generation = owner._generation

        def guard():
            owner._check(cancellation, deadline)
            _require(
                owner._generation == generation
                and setup.session is session
                and canonical(session.descriptor()) == descriptor,
                "ABSENCE_LIVE_CONTEXT_CHANGED",
            )

        try:
            with setup.usb_absence_transaction(
                cancellation=cancellation, progress=progress, deadline_ns=deadline
            ) as (prerequisites, current):
                _require(
                    canonical(current) == canonical(workflow),
                    "ABSENCE_ORIGINAL_CHANGED",
                )
                guard()
                with session.stage_transaction(
                    expected_challenge_sha256=session.view()["verification"][
                        "challenge_sha256"
                    ]
                ) as tx:
                    if action == BEGIN:
                        self._begin(
                            tx,
                            original,
                            phase_id,
                            values,
                            guard,
                            cancellation,
                            deadline,
                            progress,
                        )
                    else:
                        owner._read_records(
                            tx,
                            [a[r] for r in USB_ABSENCE_ROLE_BYTES if a[r] is not None],
                            guard,
                        )
                        if action == BOOT_REVIEW:
                            intent = UsbAbsenceBootIntent(
                                canonical(a["boot_intent"]["document"])
                            )
                            review = review_usb_absence_boot_intent(
                                intent,
                                reviewer_id=values["reviewer_id"],
                                launch_session_id=owner.launch_id,
                                reviewed_at_ns=time_ns(),
                            )
                            ref = self._retain(tx, review, "boot_review", phase_id)
                            guard()
                            self._commit(
                                tx,
                                "BOOT_REVIEWED",
                                V2StageState.BLOCKED,
                                phase_id,
                                [_reference(a["boot_intent"]), ref],
                            )
                        elif action == BOOT_COLLECT:
                            collector = OriginalUsbAbsenceBootCollector(
                                owner.workspace,
                                UsbAbsenceBootIntent(
                                    canonical(a["boot_intent"]["document"])
                                ),
                                UsbAbsenceBootReview(
                                    canonical(a["boot_review"]["document"])
                                ),
                            )
                            try:
                                collector.collect(
                                    tx,
                                    intent_reference=_reference(a["boot_intent"]),
                                    review_reference=_reference(a["boot_review"]),
                                    cancellation=cancellation,
                                    deadline_ns=deadline,
                                    revalidate_context=guard,
                                )
                            finally:
                                self.attempt["boot"] = collector.retained_diagnostics()
                        elif action == RUNTIME_REVIEW:
                            op = UsbPresenceOperation(
                                canonical(a["operation"]["document"])
                            )
                            data = op.to_dict()
                            policy = inspect_usb_presence_stage_policy(owner.workspace)
                            review = review_usb_presence_runtime(
                                UsbPresenceRuntimeRegistration(
                                    canonical(data["runtime"])
                                ),
                                phase_binding=UsbPresencePhaseBinding(
                                    canonical(data["phase_binding"])
                                ),
                                policy=policy,
                                operation_sha256=op.sha256,
                                operator_id=a["operator_event"]["document"][
                                    "operator_id"
                                ],
                                reviewer_id=values["reviewer_id"],
                                launch_session_id=owner.launch_id,
                                reviewed_at_ns=time_ns(),
                            )
                            ref = self._retain(tx, review, "runtime_review", phase_id)
                            guard()
                            self._commit(
                                tx,
                                "RUNTIME_REVIEWED",
                                V2StageState.BLOCKED,
                                phase_id,
                                [ref],
                                original["plan"].to_dict()["binding"]["trial_id"],
                            )
                        else:
                            self._commit(
                                tx,
                                "QUERY_REQUESTED",
                                V2StageState.WAITING_OPERATOR,
                                phase_id,
                                [_reference(a["runtime_review"])],
                                original["plan"].to_dict()["binding"]["trial_id"],
                            )
                guard()
                if action in {BOOT_COLLECT, COLLECT}:
                    current = owner._trial._refresh(cancellation, progress, deadline)
                    self.absence = deepcopy(current["usb_qualification_absence"])
                    if (
                        action == BOOT_COLLECT
                        and self.absence["state"] == "BOOT_RETAINED"
                    ):
                        # This only prepares a separate review. It never runs a query.
                        with session.stage_transaction(
                            expected_challenge_sha256=session.view()["verification"][
                                "challenge_sha256"
                            ]
                        ) as tx:
                            refs = owner._read_records(
                                tx,
                                [
                                    self.absence[r]
                                    for r in list(USB_ABSENCE_ROLE_BYTES)[:6]
                                ],
                                guard,
                            )
                            self._commit(
                                tx,
                                "PRESENCE_REVIEW_REQUESTED",
                                V2StageState.WAITING_OPERATOR,
                                phase_id,
                                refs,
                            )
                            guard()
                            self._commit(
                                tx,
                                "PRESENCE_REVIEW_PREPARED",
                                V2StageState.REVIEW_PENDING,
                                phase_id,
                                refs,
                            )
                    elif action == COLLECT:
                        self._collect(
                            current, prerequisites, original, guard, cancellation
                        )
                guard()
            owner._check(cancellation, deadline)
            with owner._lock:
                owner._adopt()
                return self.result(action)
        except BaseException:
            owner.invalidate()
            setup.invalidate()
            raise

    def _begin(
        self, tx, original, phase_id, values, guard, cancellation, deadline, progress
    ):
        owner = self.owner
        binding = build_usb_presence_phase_binding(**original)
        start = self._commit(
            tx,
            "PREPARATION_REQUESTED",
            V2StageState.WAITING_OPERATOR,
            phase_id,
            [original["baseline_reference"]],
        )
        guard()
        runtime = usb_presence_runtime_candidate(
            owner.workspace, source_sha256=owner.source_sha256
        )
        policy = inspect_usb_presence_stage_policy(owner.workspace)
        op = usb_presence_operation(
            phase_binding=binding,
            runtime=runtime,
            policy=policy,
            operation_id=phase_id,
            launch_session_id=owner.launch_id,
            request_nonce=uuid4().hex + uuid4().hex,
        )
        event = build_usb_presence_operator_event(
            phase_binding=binding,
            phase_id=phase_id,
            launch_session_id=owner.launch_id,
            operator_id=values["operator_id"],
            phase_started_at_utc_ns=start.occurred_at_ns,
            reported_at_utc_ns=time_ns(),
        )
        report = inspect_usb_presence_runtime(
            runtime, cancellation=cancellation, deadline_ns=deadline, progress=progress
        )
        self.attempt["runtime_report"] = deepcopy(report)
        guard()
        op_ref = self._retain(tx, op, "operation", phase_id)
        event_ref = self._retain(tx, event, "operator_event", phase_id)
        common = dict(
            operation=op,
            operation_reference=op_ref,
            operator_event=event,
            operator_event_reference=event_ref,
            phase_start_event=start,
            original_baseline=original,
        )
        preparation = build_usb_absence_preparation(
            **common, runtime_report=report, prepared_at_utc_ns=time_ns()
        )
        prep_ref = self._retain(tx, preparation, "preparation", phase_id)
        intent_ref = self._retain(
            tx, build_usb_absence_boot_intent(**common), "boot_intent", phase_id
        )
        guard()
        self._commit(
            tx,
            "PREPARED",
            V2StageState.REVIEW_PENDING,
            phase_id,
            [op_ref, event_ref, prep_ref, intent_ref],
        )

    def _facts(self, workflow, prerequisites, campaign, policy, guard):
        from .commissioning_camera_persistence import physical_camera_source_binding
        from .commissioning_usb_presence_persistence import (
            PhysicalUsbPresenceAdmissionFacts,
        )
        from .physical_onboarding_durability import canonical_sha256
        from .physical_configuration_epochs import (
            _verify_physical_configuration_epochs_after_usb_absence,
        )

        a, op = workflow["usb_qualification_absence"], campaign.operation.to_dict()
        records = []

        def visit(value):
            if type(value) is dict:
                if set(value) == {
                    "document",
                    "evidence_sha256",
                    "reference",
                    "retention",
                }:
                    records.append(value)
                else:
                    for child in value.values():
                        visit(child)
            elif type(value) is list:
                for child in value:
                    visit(child)

        visit(workflow)
        refs = tuple(_reference(r) for r in records)
        expected_descriptor = canonical(workflow["binding"])
        review_event = _parse_event(a["events"][-2])
        query_event = canonical(a["events"][-1])
        epoch = workflow["configuration_epochs"]

        def facts(request, snapshot):
            guard()
            _require(
                canonical(self.owner.setup.session.descriptor()) == expected_descriptor
                and snapshot.header.header_sha256 == workflow["session_header_sha256"]
                and snapshot.header.cell_id == request.cell_id == op["cell_id"]
                and snapshot.header.session_id == request.session_id == op["session_id"]
                and snapshot.header.source_binding_sha256
                == physical_camera_source_binding(op["source_sha256"])
                and request.action_id == "physical-native-usb-presence"
                and snapshot.head.head_sha256 == workflow["session_head_sha256"]
                and canonical_sha256([r.to_dict() for r in snapshot.evidence])
                == workflow["evidence_inventory_sha256"]
                and not snapshot.reconciliation_required
                and all(
                    snapshot.state_for(s) is V2StageState.PASS for s in STAGE_ORDER[:3]
                )
                and snapshot.next_action.stage is STAGE
                and snapshot.next_action.stage_state is V2StageState.WAITING_OPERATOR
                and snapshot.committed_events
                and canonical(snapshot.committed_events[-1].to_dict()) == query_event,
                "ABSENCE_CURRENT_ADMISSION_CONTEXT_CHANGED",
            )
            inventory = {
                r.evidence_id: canonical(r.to_dict()) for r in snapshot.evidence
            }
            _require(
                all(
                    inventory.get(r.evidence_id) == canonical(r.to_dict()) for r in refs
                ),
                "ABSENCE_ORIGINAL_REFERENCE_CHANGED",
            )
            epochs = _verify_physical_configuration_epochs_after_usb_absence(
                canonical(epoch["document"]),
                prerequisites=prerequisites,
                snapshot=snapshot,
                expected_sha256=epoch["evidence_sha256"],
            )
            hazard = dict(
                schema="rocell.usb_presence_limited_hazard_assessment.v1",
                source_sha256=self.owner.source_sha256,
                session_id=op["session_id"],
                header_sha256=op["header_sha256"],
                policy_sha256=policy.sha256,
                operation_sha256=campaign.operation.sha256,
                phase_binding_sha256=campaign.phase_binding.sha256,
                runtime_review_sha256=campaign.review.sha256,
                reviewed_originals=[r.to_dict() for r in refs],
                scope="EXACT_PHYSICAL_USB_NODE_PRESENCE_ONLY",
                enforced_budget=policy.to_dict()["budget"],
                leases=["CELL", "SESSION", "CAMERA"],
                observed_power="UNKNOWN",
                energy_envelope=None,
                automatic_retry_allowed=False,
                physical_isolation_verified=False,
                **FLAGS
            )
            documents = tuple(
                dict(
                    schema="rocell.usb_presence_original_configuration_epoch.v1",
                    original_vector_sha256=epoch["evidence_sha256"],
                    original_reference=epoch["reference"],
                    original_binding=epochs.to_dict()["binding"],
                    entry=entry,
                    physical_configuration_qualified=False,
                )
                for entry in epochs.to_dict()["entries"]
            )
            guard()
            return PhysicalUsbPresenceAdmissionFacts(
                hazard,
                documents,
                campaign.phase_binding.to_dict(),
                stage_policy=policy,
                phase_binding=campaign.phase_binding,
                runtime_review=campaign.review,
                runtime_review_reference=_reference(a["runtime_review"]),
                runtime_review_event=review_event,
            )

        return facts

    def _collect(self, workflow, prerequisites, original_baseline, guard, cancellation):
        from .commissioning_usb_presence_persistence import (
            M1PhysicalUsbPresencePersistence,
        )

        a = workflow["usb_qualification_absence"]
        _require(
            a["state"] == "QUERY_REQUESTED"
            and a["original_campaign"] is None
            and a["original_campaign_event"] is None,
            "ABSENCE_ORIGINAL_ATTEMPT_ALREADY_RETAINED",
        )
        campaign = PhysicalUsbPresenceCampaign(
            UsbPresenceOperation(canonical(a["operation"]["document"])),
            review=UsbPresenceRuntimeReview(canonical(a["runtime_review"]["document"])),
        )
        policy = inspect_usb_presence_stage_policy(self.owner.workspace)
        persistence = M1PhysicalUsbPresencePersistence(
            self.owner.setup.session._store._runtime,
            workspace_source_sha256=self.owner.source_sha256,
            stage_policy=policy,
            expected_usb_presence_policy_sha256=policy.sha256,
            admission_facts=self._facts(
                workflow, prerequisites, campaign, policy, guard
            ),
        )
        self.dispatch = PhysicalUsbPresenceDispatchOwner(
            persistence, campaign, revalidate_context=guard
        )
        self.query_attempted = True
        try:
            self.dispatch_result = self.dispatch.perform(
                request_key="usb-absence-" + a["phase_id"], cancellation=cancellation
            )
        finally:
            self.attempt["dispatch"] = self.dispatch.retained_diagnostics()
        original = self.dispatch.retained_diagnostics()["original"]
        guard()
        run = (
            None
            if not original or original.get("evidence") is None
            else OwnedUsbPresenceRunEvidence(canonical(original["evidence"]))
        )
        effects = None if run is None else run.bounded_effect_summary()
        if not (
            original
            and original["result"]["state"] == "SEALED_KNOWN"
            and effects
            and effects["current_complete"]
            and effects["process_cleanup_confirmed"]
            and effects["native_cleanup_confirmed"]
        ):
            return
        verified = persistence.verification(workflow["binding"]["session_id"])
        with persistence.stage_transaction(
            workflow["binding"]["session_id"],
            expected_challenge_sha256=verified.challenge_sha256,
        ) as tx:
            before = [a[r] for r in list(USB_ABSENCE_ROLE_BYTES)[:7]]
            refs = self.owner._read_records(tx, before, guard)
            execution_ref = self._retain(tx, run, "execution", a["phase_id"])
            phase = build_usb_presence_qualification_phase(
                original_baseline=original_baseline,
                context=dict(
                    operator_id=a["operator_event"]["document"]["operator_id"],
                    launch_session_id=a["operation"]["document"]["launch_session_id"],
                    operation_id=a["phase_id"],
                    started_at_utc_ns=a["events"][0]["occurred_at_ns"],
                    finished_at_utc_ns=time_ns(),
                ),
                sources=dict(
                    operation=canonical(a["operation"]["document"]),
                    operator_event=canonical(a["operator_event"]["document"]),
                    owned_presence_run=run.payload,
                    host_boot=canonical(a["host_boot"]["document"]),
                ),
                references=dict(
                    operation=_reference(a["operation"]),
                    operator_event=_reference(a["operator_event"]),
                    owned_presence_run=execution_ref,
                    host_boot=_reference(a["host_boot"]),
                ),
            )
            phase_ref = self._retain(tx, phase, "phase_record", a["phase_id"])
            guard()
            self._commit(
                tx,
                "RETAINED",
                V2StageState.BLOCKED,
                a["phase_id"],
                [*refs, execution_ref, phase_ref],
            )
            guard()

    def result(self, action):
        evidence = self.execution()
        execution = None if evidence is None else evidence.safe_summary()
        observation = None if evidence is None else evidence.observation
        coverage, opens, calls = "NO_DEVICE_IO", 0, 0
        if action == COLLECT:
            coverage = (
                "NOT_REPORTED" if execution is None else execution["counter_coverage"]
            )
            counts = None if execution is None else execution["actual_counts"]
            opens = None if counts is None else counts["device_handle_opens"]
            calls = None if counts is None else counts["api_calls"]
        report = dict(
            original_context=self.owner._context(),
            qualification=self.owner.qualification_view(),
            host_boot=self.boot_summary(),
            execution=execution,
            observation=None if observation is None else observation.safe_summary(),
            pending_completion_log=True,
            meaning=MEANING,
            **FLAGS
        )
        result = dict(
            schema=RESULT_SCHEMA,
            action_id=action,
            status="SUCCEEDED",
            steps=[dict(name=action, exit_code=0, report=report)],
            device_open_count=opens,
            presence_api_call_count=calls,
            presence_query_attempted=action == COLLECT and self.query_attempted,
            counter_coverage=coverage,
            serial_write_count=0,
            power_event_count=0,
            motion_command_count=0,
            contact_command_count=0,
            physical_authority=False,
            hardware_qualified=False,
        )
        self.owner._publication = dict(status="PENDING", operation_id=None)
        self.owner._pending_result, self.owner._pending_action = (
            canonical(result),
            action,
        )
        return deepcopy(result)

    def validate_publication(self):
        if self.dispatch_result is not None:
            self.dispatch.validate_publication(self.dispatch_result)

    def publication_completed(self, operation_id):
        if self.dispatch_result is not None:
            self.dispatch.publication_completed(operation_id)
