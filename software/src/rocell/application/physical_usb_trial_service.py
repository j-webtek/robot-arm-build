"""Internal original BASELINE composition of the existing USB wizard owner.

This is not a second admission owner. Arrival supplies acquisition timing only
after its exact result has been durably logged. Original M1, the independently
owned boot collector and the existing USB consumed-permit dispatcher retain
their separate authority and one-shot boundaries.
"""

from __future__ import annotations

from copy import deepcopy
from time import time_ns
from uuid import uuid4

from .physical_usb_identity_service import (
    BEGIN,
    PREPARE,
    PHASE_REVIEW,
    PHASE_COLLECT,
    EXPORT,
    FLAGS,
    _require,
    _reference,
    _observation,
)
from .physical_camera_usb_phase import (
    USB_PHASE_ROLE_BYTES,
    UsbTrialBaselinePreparation,
    build_usb_trial_baseline_preparation,
    usb_phase_event,
    usb_phase_label,
)
from .physical_camera_usb_qualification import (
    UsbQualificationPlan,
    UsbQualificationPhase,
    build_usb_qualification_phase,
)
from .physical_camera_selection import (
    selection_from_enrollment_snapshot,
    PhysicalCameraSelection,
)
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
from .physical_usb_trial_boot import (
    UsbTrialBootIntent,
    OriginalUsbTrialBootCollector,
    build_usb_trial_boot_intent,
)
from .wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
    verify_native_camera_enrollment_snapshot,
)
from .wizard_camera_helper_registration import WizardCameraHelperRegistration
from rocell.providers.windows.host_boot_observation import HostBootObservation
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


STAGE = STAGE_ORDER[3]
ACQUISITIONS = (
    ("GENERIC_INVENTORY", "inventory_devices"),
    ("NATIVE_INVENTORY", "native_camera_inventory"),
    ("NATIVE_IDENTITY", "native_camera_identity"),
)
MEANING = (
    "One newly declared BASELINE interval: fresh reviewed metadata, independently "
    "owned local boot observation, then one separately admitted USB query. "
    "Not reconnect/reboot qualification, camera capture or arm authority. "
    "Partial or uncertain attempts cannot be replayed; export their originals."
)


class _UsbTrialBaseline:
    def __init__(self, owner):
        self.owner = owner
        self.baseline = None
        self.attempt = None
        self.ledger = None
        self.query_attempted = False

    def adopt(self, workflow):
        prior = None if self.baseline is None else self.baseline["phase_id"]
        self.baseline = deepcopy(workflow.get("usb_qualification_baseline"))
        phase_id = None if self.baseline is None else self.baseline["phase_id"]
        if prior != phase_id:
            self.ledger = None
        if self.baseline and self.baseline.get("preparation"):
            self.ledger = deepcopy(
                self.baseline["preparation"]["document"]["acquisition_ledger"]
            )

    def has_diagnostics(self):
        return self.baseline is not None or self.attempt is not None

    def diagnostics(self, workflow):
        if not self.has_diagnostics():
            return {}
        attempt = deepcopy(self.attempt)
        if attempt is not None:
            attempt["acquisition_ledger"] = deepcopy(self.ledger)
        return dict(
            qualification_baseline=deepcopy(
                workflow.get("usb_qualification_baseline") or self.baseline
            ),
            qualification_attempt=attempt,
        )

    def _start(self):
        if not self.baseline:
            return None
        return next(
            (
                e
                for e in self.baseline["events"]
                if e["detail_code"]
                == usb_phase_event("PREPARATION_REQUESTED", self.baseline["phase_id"])
            ),
            None,
        )

    def _new_ledger(self):
        start = self._start()
        if start is None:
            return None
        plan = self.owner._qualification_trial["plan"]["document"]
        return dict(
            schema="rocell.usb_phase_metadata_acquisition_ledger.v1",
            source_sha256=self.owner.source_sha256,
            session_id=plan["binding"]["session_id"],
            launch_session_id=self.owner.launch_id,
            trial_id=plan["binding"]["trial_id"],
            phase_id=self.baseline["phase_id"],
            phase_started_at_utc_ns=start["occurred_at_ns"],
            entries=[],
        )

    def acquisition_started(self, action_id, operation_id, started_at_ns):
        """Server-only token; no packet or observation is invented at start."""
        with self.owner._lock:
            if (
                not self.baseline
                or self.baseline["state"] != "PREPARATION_REQUESTED"
                or action_id not in {a for _, a in ACQUISITIONS}
                or self._start() is None
            ):
                return None
            if (
                self.ledger is None
                or self.ledger["launch_session_id"] != self.owner.launch_id
            ):
                self.ledger = self._new_ledger()
            index = [a for _, a in ACQUISITIONS].index(action_id)
            # A new upstream observation invalidates downstream freshness, even
            # when its bytes happen to equal a prior packet.
            self.ledger["entries"] = self.ledger["entries"][:index]
            return dict(
                phase_id=self.baseline["phase_id"],
                action_id=action_id,
                operation_id=operation_id,
                started_at_utc_ns=started_at_ns,
                source_sha256=self.owner.source_sha256,
                launch_session_id=self.owner.launch_id,
            )

    def acquisition_published(self, token, *, finished_at_ns, document, result_sha256):
        """Called only after exact Arrival retention AND durable completion log."""
        if token is None:
            return
        with self.owner._lock:
            if (
                not self.baseline
                or self.baseline["state"] != "PREPARATION_REQUESTED"
                or self.ledger is None
                or token["phase_id"] != self.baseline["phase_id"]
                or token["source_sha256"] != self.owner.source_sha256
                or token["launch_session_id"] != self.owner.launch_id
            ):
                return
            index = [a for _, a in ACQUISITIONS].index(token["action_id"])
            previous = (
                self.ledger["phase_started_at_utc_ns"]
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
        _require(
            type(native_camera) is WizardNativeCameraEnrollment,
            "USB_FRESH_NATIVE_OWNER_REQUIRED",
        )
        raw = verify_native_camera_enrollment_snapshot(
            native_camera.export_snapshot(),
            source_sha256=self.owner.source_sha256,
            launch_session_id=self.owner.launch_id,
        )
        selection = selection_from_enrollment_snapshot(
            raw,
            source_sha256=self.owner.source_sha256,
            launch_session_id=self.owner.launch_id,
        )
        _require(selection is not None, "USB_FRESH_REVIEWED_SELECTION_REQUIRED")
        # The native owner revalidates its generic review, packet helper and
        # independently reviewed endpoint. The current helper owner is also
        # sealed into the Arrival ticket; it is never provided by an HTTP body.
        _require(
            type(helper) is WizardCameraHelperRegistration
            and helper.registration() is not None,
            "USB_CURRENT_HELPER_REVIEW_REQUIRED",
        )
        registration = helper.registration().payload
        _require(
            registration["source_sha256"] == self.owner.source_sha256
            and registration["session_id"] == self.owner.launch_id
            and registration["mode"] == "physical"
            and registration["helper_sha256"]
            == raw["view"]["provenance"]["helper_sha256"],
            "USB_CURRENT_HELPER_SUBJECT_CHANGED",
        )
        _require(
            self.ledger is not None and len(self.ledger["entries"]) == 3,
            "USB_FRESH_METADATA_LEDGER_REQUIRED",
        )
        docs = (
            raw["generic_review"]["inventory_report"],
            raw["inventory_packet"],
            raw["identity_packet"],
        )
        ids = (
            raw["generic_review"]["operation_id"],
            raw["view"]["inventory_operation_id"],
            raw["view"]["identity"]["operation_id"],
        )
        _require(
            all(
                row["operation_id"] == op
                and row["document_sha256"] == digest(canonical(doc))
                for row, op, doc in zip(self.ledger["entries"], ids, docs)
            ),
            "USB_FRESH_METADATA_SUBJECT_CHANGED",
        )
        return raw, selection

    def context(self, native_camera, helper):
        value = dict(baseline=self.baseline, attempt=self.attempt, ledger=self.ledger)
        if self.baseline and self.baseline["state"] == "PREPARATION_REQUESTED":
            value.update(
                native_camera=(
                    None if native_camera is None else native_camera.export_snapshot()
                ),
                helper=None if helper is None else helper.export_snapshot(),
            )
        return value

    def fields(self, action, check, actor):
        return {
            BEGIN: (
                actor("operator_id", "Operator beginning the new BASELINE interval"),
                check(
                    "file_only",
                    "Record the phase boundary only; then acquire fresh metadata explicitly",
                ),
            ),
            PREPARE: (
                actor(
                    "operator_id",
                    "Operator preparing the exact fresh metadata and files",
                ),
                check(
                    "file_only",
                    "Inspect fixed files and retain fresh metadata; no boot or USB query",
                ),
            ),
            PHASE_REVIEW: (
                actor(
                    "reviewer_id",
                    "Distinct reviewer label (not authenticated identity)",
                ),
                check(
                    "confirm_policy_review", "Review the exact bounded USB-query policy"
                ),
                check(
                    "confirm_runtime_review", "Review the exact inspected fixed runtime"
                ),
                check(
                    "confirm_exact_target", "Review this fresh original camera target"
                ),
                check(
                    "confirm_boot_metadata",
                    "Review one fixed local host-boot observation; this does not restart Windows",
                ),
            ),
            PHASE_COLLECT: (
                check(
                    "confirm_host_boot",
                    "Collect one owned local host/LastBootUpTime observation",
                ),
                check(
                    "confirm_usb_query",
                    "After clean boot retention, request one separate bounded USB descriptor query",
                ),
                check(
                    "confirm_no_capture_or_arm",
                    "No capture, settings, arm, power, motion, reboot or automatic retry",
                ),
            ),
        }[action]

    def blocked_reason(self, action, workflow, native_camera, helper):
        trial = workflow.get("usb_qualification_trial")
        baseline = workflow.get("usb_qualification_baseline")
        if not trial or trial["state"] != "PLAN_DECLARED":
            return "Declare and publish the exact original qualification trial first."
        if self.owner._attempt_key(action, workflow) in self.owner._attempted:
            return "This phase action was already attempted; refresh/export originals without retry."
        expected = {
            BEGIN: None,
            PREPARE: "PREPARATION_REQUESTED",
            PHASE_REVIEW: "PREPARED",
            PHASE_COLLECT: "REVIEWED",
        }[action]
        if (None if baseline is None else baseline["state"]) != expected:
            return "Complete the preceding original phase action; partial or requested observations are export-only."
        if baseline and baseline.get("preparation"):
            launch = baseline["preparation"]["document"]["acquisition_ledger"][
                "launch_session_id"
            ]
            if launch != self.owner.launch_id:
                return "This prepared phase belongs to an earlier launch; export it without rebinding metadata or replaying collection."
        if action == PREPARE:
            try:
                self._enrollment(native_camera, helper)
            except (ValueError, TypeError, KeyError, AttributeError):
                return "After Begin, acquire/review fresh generic and native camera metadata in this launch, then explicitly refresh the original session."
        return None

    def execution(self):
        record = (self.baseline or {}).get("execution")
        if record:
            evidence = OwnedUsbIdentityRunEvidence(canonical(record["document"]))
            _require(
                evidence.sha256 == record["evidence_sha256"],
                "USB_PHASE_EXECUTION_HASH_CHANGED",
            )
            return evidence
        original = (self.baseline or {}).get("original_campaign")
        if original is None:
            original = ((self.attempt or {}).get("dispatch") or {}).get("original")
        if original and original.get("evidence"):
            evidence = OwnedUsbIdentityRunEvidence(canonical(original["evidence"]))
            _require(
                evidence.sha256 == original["evidence_sha256"],
                "USB_PHASE_EXECUTION_HASH_CHANGED",
            )
            return evidence
        return None

    def execution_summary(self):
        evidence = self.execution()
        return None if evidence is None else evidence.safe_summary()

    def boot_summary(self):
        record = (self.baseline or {}).get("host_boot")
        if record is None:
            record = ((self.attempt or {}).get("boot") or {}).get("host_boot")
        if record is None:
            return None
        report = HostBootObservation(canonical(record["document"]))
        data = report.safe_summary()
        response = data["response"]
        boot_attempt = (self.attempt or {}).get("boot") or {}
        events = list((self.baseline or {}).get("events", []))
        if boot_attempt.get("terminal_event") is not None:
            events.append(boot_attempt["terminal_event"])
        phase_id = (self.baseline or self.attempt)["phase_id"]
        original_state = (
            "BOOT_REQUESTED" if boot_attempt.get("requested_event") else "INCOMPLETE"
        )
        for raw_event in reversed(events):
            event = _parse_event(raw_event)
            matched = next(
                (
                    name
                    for name in (
                        "BOOT_RETAINED",
                        "BOOT_HELD",
                        "BOOT_UNCERTAIN",
                        "BOOT_REQUESTED",
                    )
                    if event.detail_code == usb_phase_event(name, phase_id)
                ),
                None,
            )
            if matched is not None:
                original_state = matched
                break
        return dict(
            schema="rocell.wizard_usb_trial_boot_summary.v1",
            original_state=original_state,
            observation_sha256=report.sha256,
            status=data["status"],
            origin=data["origin"],
            host_key_sha256=data["host_key_sha256"],
            boot_key_sha256=data["boot_key_sha256"],
            last_boot_up_time_utc=(
                None if response is None else response["last_boot_up_time_utc"]
            ),
            process_status=data["process_status"],
            tree_exit_confirmed=data["tree_exit_confirmed"],
            blockers=data["blockers"],
            physical_authority=False,
            hardware_qualified=False,
            device_io_performed=False,
        )

    def projection(self, value):
        trial = self.owner._qualification_trial
        if not trial or (
            trial["state"] != "PLAN_DECLARED" and not self.has_diagnostics()
        ):
            return deepcopy(value)
        value = deepcopy(value)
        value["schema"] = "rocell.wizard_usb_qualification.v2"
        value["meaning"] = MEANING
        value["baseline"] = None
        current = value["publication"]["status"] == "CURRENT"
        if self.baseline:
            b = self.baseline
            p = b.get("preparation")
            pd = None if p is None else p["document"]
            target = None
            if pd:
                identity = PhysicalCameraSelection(
                    canonical(pd["operation"]["selection"])
                ).identity_document
                target = dict(
                    selection_sha256=digest(canonical(pd["operation"]["selection"])),
                    native_identity_sha256=identity["native_identity_sha256"],
                    endpoint_sha256=identity["endpoint_sha256"],
                    symbolic_link=identity["symbolic_link"],
                    device_instance_id=identity["metadata_review"][
                        "observed_instance_id"
                    ],
                )
            phase = b.get("phase_record")
            phase_summary = (
                None
                if phase is None
                else dict(
                    phase_sha256=phase["evidence_sha256"],
                    checks=phase["document"]["checks"],
                    provenance=phase["document"]["provenance"],
                )
            )
            value["baseline"] = dict(
                phase_id=b["phase_id"],
                state=b["state"],
                phase_start_event_sha256=(
                    None if self._start() is None else self._start()["event_sha256"]
                ),
                phase_started_at_utc_ns=(
                    None if self._start() is None else self._start()["occurred_at_ns"]
                ),
                acquisition_ledger=deepcopy(self.ledger),
                preparation=(
                    None
                    if p is None
                    else UsbTrialBaselinePreparation(canonical(pd)).safe_summary()
                ),
                target=target,
                review=(
                    None
                    if not b.get("identity") or not b.get("boot_request")
                    else dict(
                        identity_sha256=b["identity"]["evidence_sha256"],
                        policy_review_sha256=b["policy_review"]["evidence_sha256"],
                        runtime_review_sha256=b["runtime_review"]["evidence_sha256"],
                        operator_id=b["policy_review"]["document"]["operator_id"],
                        reviewer_id=b["policy_review"]["document"]["reviewer_id"],
                        review_launch_id=b["runtime_review"]["document"][
                            "launch_session_id"
                        ],
                        boot_request_sha256=b["boot_request"]["evidence_sha256"],
                    )
                ),
                host_boot=self.boot_summary(),
                execution=self.execution_summary(),
                observation=_observation(self.execution()),
                phase_record=phase_summary,
                **FLAGS,
            )
            if current:
                value["status"] = (
                    "BASELINE_RETAINED_BLOCKED"
                    if b["state"] == "RETAINED_BLOCKED"
                    else (
                        "BASELINE_ACTIVE"
                        if b["state"]
                        in {"PREPARATION_REQUESTED", "PREPARED", "REVIEWED"}
                        else "INCOMPLETE_HELD"
                    )
                )
                launch = (
                    None
                    if pd is None
                    else pd["acquisition_ledger"]["launch_session_id"]
                )
                if (
                    launch is not None
                    and launch != self.owner.launch_id
                    and b["state"] != "RETAINED_BLOCKED"
                ):
                    value["status"] = "HISTORICAL_HELD"
        if current:
            state = None if self.baseline is None else self.baseline["state"]
            value["next_action"] = {
                None: BEGIN,
                "PREPARATION_REQUESTED": PREPARE,
                "PREPARED": PHASE_REVIEW,
                "REVIEWED": PHASE_COLLECT,
            }.get(state, EXPORT)
            if value["status"] == "HISTORICAL_HELD":
                value["next_action"] = EXPORT
        else:
            value["next_action"] = None
        if value["publication"]["status"] == "PENDING":
            value.update(
                baseline=None, next_action=None, status="NOT_DECLARED", plan=None
            )
        return value

    def _retain(self, tx, payload, role, phase_id):
        _require(
            type(payload) is bytes and 0 < len(payload) <= USB_PHASE_ROLE_BYTES[role],
            "USB_PHASE_ROLE_LIMIT",
        )
        import json

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
            label=usb_phase_label(role, phase_id),
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        record.update(
            reference=ref.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        _require(tx.read_stage_evidence(ref) == payload, "USB_PHASE_READBACK_CHANGED")
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        return ref

    @staticmethod
    def _commit(tx, event, state, phase_id, refs):
        snapshot = tx.commit_stage_state(
            STAGE,
            state,
            occurred_at_ns=time_ns(),
            detail_code=usb_phase_event(event, phase_id),
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=tuple(sorted(refs, key=lambda r: r.evidence_id)),
        )
        # M1 returns the fully read-back snapshot after syncing the committed
        # head. Reuse that exact result within this transaction; a second full
        # inventory read here adds cost without crossing a new guard boundary.
        return snapshot.committed_events[-1]

    def _refresh(self, cancellation, progress, deadline):
        session = self.owner.setup.session
        session.refresh(cancellation=cancellation, progress=progress)
        return session.read_original_source_workflow(
            expected_header_sha256=self.owner._context()["header_sha256"],
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline,
        )

    def perform(
        self, action, values, *, cancellation, progress, deadline, native_camera, helper
    ):
        owner, setup = self.owner, self.owner.setup
        workflow = setup.original_source_workflow()
        session = setup.session
        binding = canonical(session.descriptor())
        baseline = workflow.get("usb_qualification_baseline")
        phase_id = (
            "usbphase-" + uuid4().hex if baseline is None else baseline["phase_id"]
        )
        plan_record = workflow["usb_qualification_trial"]["plan"]
        plan = UsbQualificationPlan(canonical(plan_record["document"]))
        # Fresh evidence is sealed before withdrawing publication. No user
        # packet, arbitrary path or provider is accepted by this entry point.
        enrollment = selection = None
        if action == PREPARE:
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
                "USB_PHASE_LIVE_CONTEXT_CHANGED",
            )

        try:
            with setup.usb_phase_transaction(
                cancellation=cancellation,
                progress=progress,
                deadline_ns=deadline,
            ) as (prerequisites, current):
                _require(
                    canonical(current) == canonical(workflow),
                    "USB_PHASE_ORIGINAL_CHANGED",
                )
                guard()
                verification = session.view()["verification"]
                with session.stage_transaction(
                    expected_challenge_sha256=verification["challenge_sha256"]
                ) as tx:
                    owner._read_records(tx, [plan_record], guard)
                    if action == BEGIN:
                        self._commit(
                            tx,
                            "ENTERED",
                            V2StageState.BLOCKED,
                            phase_id,
                            [_reference(plan_record)],
                        )
                        guard()
                        self._commit(
                            tx,
                            "PREPARATION_REQUESTED",
                            V2StageState.WAITING_OPERATOR,
                            phase_id,
                            [_reference(plan_record)],
                        )
                    elif action == PREPARE:
                        policy = inspect_usb_identity_stage_policy(owner.workspace)
                        runtime = usb_identity_runtime_candidate(
                            owner.workspace, source_sha256=owner.source_sha256
                        )
                        operation = usb_identity_phase_operation(
                            plan=plan,
                            phase="BASELINE",
                            operation_id=phase_id,
                            predecessor_sha256=None,
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
                        guard()
                        raw = canonical(enrollment)
                        ref = self._retain(tx, raw, "enrollment", phase_id)
                        preparation = build_usb_trial_baseline_preparation(
                            plan=plan,
                            plan_reference=_reference(plan_record),
                            phase_start_event=_parse_event(self._start()),
                            phase_id=phase_id,
                            enrollment=raw,
                            enrollment_reference=ref,
                            acquisition_ledger=deepcopy(self.ledger),
                            operation=operation,
                            runtime_report=report,
                            operator_id=values["operator_id"],
                            prepared_at_utc_ns=time_ns(),
                        )
                        guard()
                        prep_ref = self._retain(
                            tx, preparation.payload, "preparation", phase_id
                        )
                        self._commit(
                            tx,
                            "PREPARED",
                            V2StageState.REVIEW_PENDING,
                            phase_id,
                            [ref, prep_ref],
                        )
                    elif action == PHASE_REVIEW:
                        self._review(tx, baseline, plan_record, plan, values, guard)
                    else:
                        intent = UsbTrialBootIntent(
                            canonical(baseline["boot_request"]["document"])
                        )
                        collector = OriginalUsbTrialBootCollector(
                            owner.workspace, intent
                        )
                        try:
                            collector.collect(
                                tx,
                                intent_reference=_reference(baseline["boot_request"]),
                                cancellation=cancellation,
                                deadline_ns=deadline,
                                revalidate_context=guard,
                            )
                        finally:
                            self.attempt["boot"] = collector.retained_diagnostics()
                guard()
                if action == PHASE_COLLECT:
                    current = self._refresh(cancellation, progress, deadline)
                    self.baseline = deepcopy(current["usb_qualification_baseline"])
                    if self.baseline["state"] == "BOOT_RETAINED":
                        verification = session.view()["verification"]
                        with session.stage_transaction(
                            expected_challenge_sha256=verification["challenge_sha256"]
                        ) as tx:
                            refs = owner._read_records(
                                tx,
                                [
                                    self.baseline[r]
                                    for r in ("identity", "boot_request", "host_boot")
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
                        current = self._refresh(cancellation, progress, deadline)
                        self._collect_usb(
                            current, prerequisites, plan, guard, cancellation
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

    def _review(self, tx, baseline, plan_record, plan, values, guard):
        owner = self.owner
        phase_id = baseline["phase_id"]
        refs = owner._read_records(
            tx, [baseline[r] for r in ("enrollment", "preparation")], guard
        )
        data = UsbTrialBaselinePreparation(
            canonical(baseline["preparation"]["document"])
        ).to_dict()
        operation = UsbIdentityOperation(canonical(data["operation"]))
        op = operation.to_dict()
        policy = inspect_usb_identity_stage_policy(owner.workspace)
        _require(op["policy_sha256"] == policy.sha256, "USB_PHASE_POLICY_CHANGED")
        selection = PhysicalCameraSelection(canonical(op["selection"]))
        sd = selection.identity_document
        reviewer, operator = values["reviewer_id"], data["operator_id"]
        policy_review = UsbIdentityPolicyReview(
            canonical(
                dict(
                    schema="rocell.usb_identity_stage_policy_review.v1",
                    **{
                        k: plan.to_dict()["binding"][k]
                        for k in (
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
        identity = UsbIdentityAdmissionIdentity(
            canonical(
                dict(
                    schema="rocell.usb_identity_admission_identity.v1",
                    **{
                        k: plan.to_dict()["binding"][k]
                        for k in (
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
                    selection_sha256=selection.sha256,
                    native_identity_sha256=sd["native_identity_sha256"],
                    endpoint_sha256=sd["endpoint_sha256"],
                    device_instance_id_sha256=digest(
                        sd["metadata_review"]["observed_instance_id"].encode("utf-8")
                    ),
                    operation_sha256=operation.sha256,
                    original_subjects=[
                        dict(
                            role=role,
                            reference=ref.to_dict(),
                            document_sha256=ref.payload_sha256,
                        )
                        for role, ref in zip(
                            ("metadata", "policy_review", "runtime_review"),
                            (refs[0], pr, rr),
                        )
                    ],
                )
            )
        )
        ir = self._retain(tx, identity.payload, "identity", phase_id)
        intent = build_usb_trial_boot_intent(
            plan=plan,
            plan_reference=_reference(plan_record),
            phase_start_event=_parse_event(self._start()),
            phase_id=phase_id,
            launch_session_id=owner.launch_id,
        )
        br = self._retain(tx, intent.payload, "boot_request", phase_id)
        guard()
        self._commit(
            tx, "REVIEWED", V2StageState.BLOCKED, phase_id, [*refs, pr, rr, ir, br]
        )

    def _collect_usb(self, workflow, prerequisites, plan, guard, cancellation):
        owner = self.owner
        baseline = workflow["usb_qualification_baseline"]
        data = baseline["preparation"]["document"]
        operation = UsbIdentityOperation(canonical(data["operation"]))
        campaign = PhysicalUsbIdentityCampaign(
            operation,
            identity=UsbIdentityAdmissionIdentity(
                canonical(baseline["identity"]["document"])
            ),
            review=UsbIdentityRuntimeReview(
                canonical(baseline["runtime_review"]["document"])
            ),
        )
        policy = UsbIdentityStagePolicy(
            canonical(baseline["policy_review"]["document"]["policy"])
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
                request_key="usb-trial-" + baseline["phase_id"],
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
        verified = persistence.verification(workflow["binding"]["session_id"])
        with persistence.stage_transaction(
            workflow["binding"]["session_id"],
            expected_challenge_sha256=verified.challenge_sha256,
        ) as tx:
            owner._read_records(
                tx,
                [
                    baseline[r]
                    for r in (
                        "enrollment",
                        "preparation",
                        "policy_review",
                        "runtime_review",
                        "identity",
                        "boot_request",
                        "host_boot",
                    )
                ],
                guard,
            )
            execution_ref = self._retain(
                tx, evidence.payload, "execution", baseline["phase_id"]
            )
            phase = build_usb_qualification_phase(
                plan,
                phase="BASELINE",
                predecessor=None,
                context=dict(
                    operator_id=baseline["policy_review"]["document"]["operator_id"],
                    launch_session_id=data["acquisition_ledger"]["launch_session_id"],
                    operation_id=baseline["phase_id"],
                    started_at_utc_ns=self._start()["occurred_at_ns"],
                    finished_at_utc_ns=time_ns(),
                ),
                sources=dict(
                    native_enrollment=canonical(baseline["enrollment"]["document"]),
                    owned_usb_run=evidence.payload,
                    host_boot=canonical(baseline["host_boot"]["document"]),
                ),
                references=dict(
                    native_enrollment=_reference(baseline["enrollment"]),
                    owned_usb_run=execution_ref,
                    host_boot=_reference(baseline["host_boot"]),
                ),
            )
            phase_ref = self._retain(
                tx, phase.payload, "phase_record", baseline["phase_id"]
            )
            guard()
            refs = [
                _reference(baseline[r])
                for r in (
                    "enrollment",
                    "preparation",
                    "policy_review",
                    "runtime_review",
                    "identity",
                    "boot_request",
                    "host_boot",
                )
            ]
            self._commit(
                tx,
                "RETAINED",
                V2StageState.BLOCKED,
                baseline["phase_id"],
                [*refs, execution_ref, phase_ref],
            )
            guard()
