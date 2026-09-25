"""Private AFTER_REBOOT composition; never a second admission owner.

The completed reconnect stays historical after a new launch. Current original
Setup, a new operator report and three independently logged acquisitions bind
the new interval. Boot and descriptors have separate one-shot original
admissions. This helper never restarts the host or resumes an old interval.
Retained, uncertain and reopened reboot work is export-only.
"""

from __future__ import annotations

from copy import deepcopy
from time import time_ns
from uuid import uuid4

from .physical_camera_usb_reboot_constants import (
    USB_REBOOT_ROLE_BYTES,
    usb_reboot_event,
    usb_reboot_label,
)
from .physical_camera_usb_reboot import (
    UsbRebootPreparation,
    build_usb_reboot_preparation,
    original_usb_reboot_predecessor,
)
from .physical_usb_reboot_phase import (
    build_usb_reboot_operator_event,
    build_usb_reboot_qualification_phase,
    UsbRebootQualificationPhase,
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
from .commissioning_usb_identity_persistence import PhysicalUsbIdentityAdmissionFacts
from .commissioning_camera_persistence import physical_camera_source_binding
from .physical_onboarding_durability import canonical_sha256
from .usb_identity_stage_policy import (
    UsbIdentityPolicyReview,
    UsbIdentityStagePolicy,
    UsbIdentityAdmissionIdentity,
    inspect_usb_identity_stage_policy,
)
from .physical_usb_reboot_boot import (
    UsbRebootBootIntent,
    build_usb_reboot_boot_intent,
    classify_usb_reboot_boot_observation,
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


BEGIN = "physical_usb_reboot_begin"
PREPARE = "physical_usb_reboot_prepare"
REVIEW = "physical_usb_reboot_review"
BOOT_COLLECT = "physical_usb_reboot_boot_collect"
COLLECT = "physical_usb_reboot_collect"
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
    "One AFTER_REBOOT interval after a complete original AFTER_RECONNECT: an operator "
    "report, fresh reviewed metadata, separately owned boot observation and one "
    "separately admitted descriptor query. A new app launch is not a host restart. "
    "Provider-reported boot metadata is not cryptographic attestation or final "
    "series qualification, camera capture or arm authority. Stop is software "
    "cancellation, not a robot E-stop. "
    "Partial, uncertain or reopened intervals are export-only; never retry them."
)


def _require(*args):
    from .physical_usb_identity_service import _require as require

    return require(*args)


def _reference(record):
    from .physical_usb_identity_service import _reference as reference

    return reference(record)


def _predecessor(workflow, prerequisites):
    # These exact received subjects come from the already authenticated original
    # workflow, not user input or an exported JSON file used as an admission.
    from .physical_camera_usb_trial_readback import _received

    received = dict(
        zip(("submission", "assessment", "review"), _received(prerequisites, workflow))
    )
    if workflow.get("schema") == "rocell.physical_camera_source_workflow_readback.v12":
        return original_usb_reboot_predecessor(workflow, received=received)
    if workflow.get("schema") == "rocell.physical_camera_source_workflow_readback.v14":
        # Historical display under the real successor schema, never a replay.
        from .physical_camera_usb_reboot import _original_usb_reboot_predecessor

        return _original_usb_reboot_predecessor(
            workflow, received=received, successor=True, complete_successor=True
        )
    _require(
        workflow.get("schema") == "rocell.physical_camera_source_workflow_readback.v13",
        "USB_REBOOT_EXACT_ORIGINAL_SCHEMA_REQUIRED",
    )
    from .physical_camera_usb_reboot import original_usb_reboot_predecessor_v13

    return original_usb_reboot_predecessor_v13(workflow, received=received)


class _UsbTrialReboot:
    def __init__(self, owner):
        self.owner = owner
        self.reboot = self.attempt = self.ledger = self.predecessor = None
        self.query_attempted = False

    def adopt(self, workflow):
        before = (self.reboot or {}).get("phase_id")
        self.reboot = deepcopy(workflow.get("usb_qualification_reboot"))
        if before != (self.reboot or {}).get("phase_id"):
            self.ledger = None
        if self.reboot and self.reboot.get("preparation"):
            self.ledger = deepcopy(
                self.reboot["preparation"]["document"]["acquisition_ledger"]
            )
        try:
            # Adoption also runs while the completed action awaits its log
            # publication. Rebuild diagnostic subjects from the exact retained
            # original bytes; CURRENT is not required to display that history.
            # blocked_reason and perform still require CURRENT Setup, and
            # perform separately obtains its prerequisite through Setup again.
            from .physical_camera_prerequisites import (
                verify_physical_camera_prerequisites,
            )

            record, binding = workflow["prerequisites"], workflow["binding"]
            _require(
                record["retention"] == "M1_FULL_BYTES_READ_BACK",
                "USB_REBOOT_ORIGINAL_REQUIREMENTS_REQUIRED",
            )
            prerequisites = verify_physical_camera_prerequisites(
                canonical(record["document"]),
                expected_source_sha256=self.owner.source_sha256,
                expected_session_id=binding["session_id"],
                expected_launch_session_id=binding["launch_id"],
                expected_evidence_sha256=record["evidence_sha256"],
            )
            self.predecessor = _predecessor(workflow, prerequisites)
        except (ValueError, TypeError, KeyError, AttributeError):
            self.predecessor = None

    def invalidate(self):
        # No new launch, renewed interval or implicit retry is created here.
        pass

    def has_diagnostics(self):
        return self.reboot is not None or self.attempt is not None

    def _new_launch(self):
        if self.predecessor is None:
            return False
        prior = self.predecessor
        return self.owner.launch_id not in {
            subject.to_dict()["context"]["launch_session_id"]
            for subject in (
                prior["original_baseline"]["baseline"],
                prior["absence"],
                prior["reconnect"],
            )
        }

    def diagnostics(self, workflow):
        if not self.has_diagnostics():
            return {}
        attempt = deepcopy(self.attempt)
        if attempt is not None:
            attempt["acquisition_ledger"] = deepcopy(self.ledger)
        return dict(
            qualification_reboot=deepcopy(
                workflow.get("usb_qualification_reboot") or self.reboot
            ),
            qualification_reboot_attempt=attempt,
        )

    def _report(self):
        record = (self.reboot or {}).get("operator_event")
        return None if record is None else record["document"]

    def _start(self):
        if not self.reboot:
            return None
        return next(
            (
                event
                for event in self.reboot["events"]
                if event["detail_code"]
                == usb_reboot_event("PREPARATION_REQUESTED", self.reboot["phase_id"])
            ),
            None,
        )

    def _metadata_open(self):
        report = self._report()
        return (
            self.reboot is not None
            and self.reboot["state"] == "PREPARATION_REQUESTED"
            and report is not None
            and report["launch_session_id"] == self.owner.launch_id
            and (self.owner._workflow or {}).get("binding", {}).get("source_sha256")
            == self.owner.source_sha256
            and self.reboot.get("original_campaign") is None
            and self.reboot.get("original_campaign_event") is None
            and (self.attempt is None or self.attempt["action_id"] == BEGIN)
            and not any(
                key.startswith(action + ":")
                for key in self.owner._attempted
                for action in ACTIONS - {BEGIN}
            )
        )

    def acquisition_started(self, action_id, operation_id, started_at_ns):
        with self.owner._lock:
            report = self._report()
            if (
                not self._metadata_open()
                or action_id not in {a for _, a in ACQUISITIONS}
                or type(started_at_ns) is not int
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
                    phase_id=self.reboot["phase_id"],
                    phase_started_at_utc_ns=self._start()["occurred_at_ns"],
                    entries=[],
                )
            index = [a for _, a in ACQUISITIONS].index(action_id)
            self.ledger["entries"] = self.ledger["entries"][:index]
            return dict(
                phase_id=self.reboot["phase_id"],
                action_id=action_id,
                operation_id=operation_id,
                started_at_utc_ns=started_at_ns,
                source_sha256=self.owner.source_sha256,
                launch_session_id=self.owner.launch_id,
            )

    def acquisition_published(self, token, *, finished_at_ns, document, result_sha256):
        if (
            type(token) is not dict
            or set(token)
            != {
                "phase_id",
                "action_id",
                "operation_id",
                "started_at_utc_ns",
                "source_sha256",
                "launch_session_id",
            }
            or token["action_id"] not in {action for _, action in ACQUISITIONS}
            or type(token["started_at_utc_ns"]) is not int
            or type(finished_at_ns) is not int
        ):
            return
        with self.owner._lock:
            report = self._report()
            if (
                not self._metadata_open()
                or self.ledger is None
                or token["phase_id"] != self.reboot["phase_id"]
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
        result = dict(reboot=self.reboot, attempt=self.attempt, ledger=self.ledger)
        if self.reboot and self.reboot["state"] == "PREPARATION_REQUESTED":
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
                actor("operator_id", "Operator reporting the host restart"),
                check("file_only", "Record a new interval only; no boot or USB query"),
                check(
                    "confirm_host_restarted",
                    "I report manually restarting this host after the completed original AFTER_RECONNECT; a new app launch alone is not reboot evidence",
                ),
            ),
            PREPARE: (
                actor(
                    "operator_id",
                    "Same operator label as the original host-restart report",
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
        if action not in ACTIONS:
            return "Use an explicit AFTER_REBOOT action."
        if (
            self.owner.setup.mode != "physical"
            or self.owner.setup.view()["publication"]["status"] != "CURRENT"
            or not workflow
            or workflow.get("configuration_epochs") is None
        ):
            return "Explicitly reopen/refresh and publish the exact original session under the unchanged source first."
        if self.predecessor is None:
            return "Complete, retain and independently verify the original clean AFTER_RECONNECT first. Incomplete, held or unknown original effects cannot substitute."
        if self.owner._attempt_key(action, workflow) in self.owner._attempted:
            return "This reboot action was attempted already; export original diagnostics without replay."
        phase = workflow.get("usb_qualification_reboot")
        if action == BEGIN:
            if not self._new_launch():
                return "After completing and exporting reconnect, close the wizard, manually restart the host and reopen the same original in a new app launch. The report is not reboot proof."
            return (
                None
                if workflow.get("schema")
                == "rocell.physical_camera_source_workflow_readback.v12"
                and phase is None
                and self.attempt is None
                else "This reboot interval already exists or was attempted; export without starting it again."
            )
        if phase is None or NEXT.get(phase["state"]) != action:
            return "Complete the preceding explicit reboot action. Partial, requested or uncertain work is export-only."
        report = phase.get("operator_event")
        if (
            report is None
            or report["document"]["launch_session_id"] != self.owner.launch_id
        ):
            return "The reboot report belongs to another app launch; export this historical interval without rebinding or retrying it."
        if (
            phase.get("original_campaign") is not None
            or phase.get("original_campaign_event") is not None
        ):
            return "An original reboot campaign exists; do not replay it. Export its complete diagnostics."
        if action == PREPARE:
            try:
                self._enrollment(native_camera, helper)
            except (ValueError, TypeError, KeyError, AttributeError):
                return "After this host-restart report, acquire/review fresh generic and native metadata in this launch, then explicitly refresh the original session."
        if action == COLLECT:
            boot = self.boot_summary()
            if (
                boot is None
                or boot["original_state"] != "BOOT_RETAINED"
                or boot["restart_status"] != "BOOT_RETAINED"
            ):
                return "The exact original host-boot observation must be clean, same-host/different-boot and within the reconnect-finish/Begin epoch bounds. Export held or unknown results without retry."
        return None

    def execution(self):
        record = (self.reboot or {}).get("execution") or (
            (self.attempt or {}).get("records") or {}
        ).get("execution")
        if record is not None:
            evidence = OwnedUsbIdentityRunEvidence(canonical(record["document"]))
            _require(
                evidence.sha256 == record["evidence_sha256"],
                "USB_REBOOT_EXECUTION_HASH_CHANGED",
            )
            return evidence
        original = (self.reboot or {}).get("original_campaign") or (
            ((self.attempt or {}).get("dispatch") or {}).get("original")
        )
        if original and original.get("evidence") is not None:
            evidence = OwnedUsbIdentityRunEvidence(canonical(original["evidence"]))
            _require(
                evidence.sha256 == original["evidence_sha256"],
                "USB_REBOOT_EXECUTION_HASH_CHANGED",
            )
            return evidence
        return None

    def boot_summary(self):
        from .physical_usb_reconnect_service import _entry_history_boot

        attempt = (self.attempt or {}).get("boot") or {}
        record = (self.reboot or {}).get("host_boot") or attempt.get("host_boot")
        if record is None:
            return None
        report = HostBootObservation(canonical(record["document"]))
        _require(
            report.sha256 == record["evidence_sha256"],
            "USB_REBOOT_BOOT_HASH_CHANGED",
        )
        data = report.safe_summary()
        phase_id = (self.reboot or self.attempt)["phase_id"]
        events = list((self.reboot or {}).get("events", []))
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
                    if event["detail_code"] == usb_reboot_event(name, phase_id)
                ),
                None,
            )
            if matched:
                state = matched
                break
        prior = (
            _entry_history_boot(self.owner._workflow, "usb_qualification_reconnect")
            if self.predecessor is None
            else HostBootObservation(self.predecessor["reconnect_sources"]["host_boot"])
        )
        intent_record = (self.reboot or {}).get("boot_request") or (
            (self.attempt or {}).get("records") or {}
        ).get("boot_request")
        requested = next(
            (
                event
                for event in events
                if event["detail_code"] == usb_reboot_event("BOOT_REQUESTED", phase_id)
            ),
            attempt.get("requested_event"),
        )
        intent = (
            None
            if intent_record is None
            else UsbRebootBootIntent(canonical(intent_record["document"]))
        )
        if intent is not None:
            _require(
                intent.sha256 == intent_record["evidence_sha256"],
                "USB_REBOOT_BOOT_INTENT_HASH_CHANGED",
            )
        restart_status = "NOT_EVALUATED"
        if intent is not None and prior is not None and requested is not None:
            restart_status = classify_usb_reboot_boot_observation(
                report,
                intent=intent,
                expected_sha256=report.sha256,
                requested_event=_parse_event(requested),
                reconnect_boot=prior,
            )
        scope = {} if intent is None else intent.to_dict()
        return dict(
            schema="rocell.wizard_usb_reboot_boot_summary.v1",
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
            restart_status=restart_status,
            reconnect_finished_at_utc_ns=scope.get("reconnect_finished_at_utc_ns"),
            phase_started_at_utc_ns=scope.get("phase_started_at_utc_ns"),
            physical_authority=False,
            hardware_qualified=False,
            device_io_performed=False,
        )

    def _refresh_recommended(self):
        """Cached navigation only; the explicit Refresh action rechecks originals."""
        phase, ledger, report = self.reboot, self.ledger, self._report()
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
        if not self.has_diagnostics() and not self._new_launch():
            return deepcopy(value)
        from .physical_usb_identity_service import _observation

        value = deepcopy(value)
        # A completed reconnect belongs to its older launch and remains
        # historical. Its projection cannot decide whether freshly verified
        # Setup permits a NEW reboot interval in this launch.
        publication = deepcopy(self.owner._publication)
        if (
            publication["status"] == "CURRENT"
            and self.owner.setup.view()["publication"]["status"] != "CURRENT"
        ):
            publication = dict(status="HISTORICAL_HELD", operation_id=None)
        value.update(
            schema="rocell.wizard_usb_qualification.v5",
            publication=publication,
            reboot=None,
            meaning=MEANING,
        )
        current = publication["status"] == "CURRENT"
        value["status"] = "REBOOT_READY" if current else "HISTORICAL_HELD"
        phase = self.reboot
        if phase:
            prep = phase.get("preparation")
            data = (
                None
                if prep is None
                else UsbRebootPreparation(canonical(prep["document"])).to_dict()
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
                parsed = UsbRebootQualificationPhase(canonical(record["document"]))
                _require(
                    parsed.sha256 == record["evidence_sha256"],
                    "USB_REBOOT_PHASE_HASH_CHANGED",
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
            value["reboot"] = dict(
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
                    "REBOOT_RETAINED_BLOCKED"
                    if phase["state"] == "RETAINED_BLOCKED"
                    else (
                        "REBOOT_ACTIVE" if phase["state"] in NEXT else "INCOMPLETE_HELD"
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
                if phase is None and self._new_launch() and self.attempt is None
                else NEXT.get((phase or {}).get("state"), EXPORT)
            )
            if current
            else None
        )
        if phase is None and self.attempt is not None:
            value["status"] = "INCOMPLETE_HELD" if current else "HISTORICAL_HELD"
            value["next_action"] = EXPORT
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
                reboot=None, next_action=None, status="NOT_DECLARED", plan=None
            )
        return value

    def _retain(self, tx, payload, role, phase_id):
        import json

        _require(
            type(payload) is bytes and 0 < len(payload) <= USB_REBOOT_ROLE_BYTES[role],
            "USB_REBOOT_ROLE_LIMIT",
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
            label=usb_reboot_label(role, phase_id),
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        record.update(
            reference=ref.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        _require(tx.read_stage_evidence(ref) == payload, "USB_REBOOT_READBACK_CHANGED")
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        return ref

    def _commit(self, tx, event, state, phase_id, refs):
        snapshot = tx.commit_stage_state(
            STAGE,
            state,
            occurred_at_ns=time_ns(),
            detail_code=usb_reboot_event(event, phase_id),
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
        _require(
            self.blocked_reason(action, workflow, native_camera, helper) is None,
            "USB_REBOOT_ACTION_BLOCKED",
        )
        predecessor = _predecessor(workflow, setup.current_prerequisite_artifact())
        plan = predecessor["original_baseline"]["plan"]
        phase = workflow.get("usb_qualification_reboot")
        phase_id = "usbphase-" + uuid4().hex if phase is None else phase["phase_id"]
        binding = canonical(session.descriptor())
        enrollment = selection = None
        if action == PREPARE:
            _require(
                values["operator_id"]
                == phase["operator_event"]["document"]["operator_id"],
                "USB_REBOOT_OPERATOR_CHANGED",
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
                "USB_REBOOT_LIVE_CONTEXT_CHANGED",
            )

        try:
            with setup.usb_reboot_transaction(
                cancellation=cancellation, progress=progress, deadline_ns=deadline
            ) as (prerequisites, current):
                _require(
                    canonical(current) == canonical(workflow),
                    "USB_REBOOT_ORIGINAL_CHANGED",
                )
                guard()
                verification = session.view()["verification"]
                with session.stage_transaction(
                    expected_challenge_sha256=verification["challenge_sha256"]
                ) as tx:
                    if action == BEGIN:
                        reconnect_ref = predecessor["reconnect_reference"]
                        _require(
                            tx.read_stage_evidence(reconnect_ref)
                            == predecessor["reconnect"].payload,
                            "USB_REBOOT_RECONNECT_CHANGED",
                        )
                        start = self._commit(
                            tx,
                            "PREPARATION_REQUESTED",
                            V2StageState.WAITING_OPERATOR,
                            phase_id,
                            [reconnect_ref],
                        )
                        guard()
                        event = build_usb_reboot_operator_event(
                            plan=plan,
                            reconnect=predecessor["reconnect"],
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
                            phase="AFTER_REBOOT",
                            operation_id=phase_id,
                            predecessor_sha256=predecessor["reconnect"].sha256,
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
                        from .physical_usb_reboot_phase import (
                            UsbRebootOperatorEvent,
                        )

                        preparation = build_usb_reboot_preparation(
                            **predecessor,
                            phase_start_event=_parse_event(self._start()),
                            phase_id=phase_id,
                            operator_event=UsbRebootOperatorEvent(
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
                        self._review(tx, phase, plan, predecessor, values, guard)
                    elif action == BOOT_COLLECT:
                        from .physical_usb_reboot_boot import (
                            OriginalUsbRebootBootCollector,
                        )

                        intent = UsbRebootBootIntent(
                            canonical(phase["boot_request"]["document"])
                        )
                        collector = OriginalUsbRebootBootCollector(
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
                    self.reboot = deepcopy(current["usb_qualification_reboot"])
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

    def _review(self, tx, phase, plan, predecessor, values, guard):
        owner, phase_id = self.owner, phase["phase_id"]
        roles = ("operator_event", "enrollment", "preparation", "operation")
        refs = owner._read_records(tx, [phase[role] for role in roles], guard)
        preparation = UsbRebootPreparation(canonical(phase["preparation"]["document"]))
        data = preparation.to_dict()
        operation = UsbIdentityOperation(canonical(phase["operation"]["document"]))
        _require(
            operation.payload == canonical(data["operation"]),
            "USB_REBOOT_OPERATION_CHANGED",
        )
        op = operation.to_dict()
        policy = inspect_usb_identity_stage_policy(owner.workspace)
        _require(op["policy_sha256"] == policy.sha256, "USB_REBOOT_POLICY_CHANGED")
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
        intent = build_usb_reboot_boot_intent(
            preparation=preparation,
            preparation_reference=_reference(phase["preparation"]),
            reconnect=predecessor["reconnect"],
            reconnect_reference=predecessor["reconnect_reference"],
        )
        br = self._retain(tx, intent.payload, "boot_request", phase_id)
        guard()
        self._commit(
            tx, "REVIEWED", V2StageState.BLOCKED, phase_id, [*refs, pr, rr, ir, br]
        )

    def _facts_provider(self, workflow, prerequisites, campaign, check):
        """Freeze subjects, not authorization: verify EACH actual leased snapshot."""
        from .physical_configuration_epochs import (
            _verify_physical_configuration_epochs_after_usb_reboot,
        )

        workflow = deepcopy(workflow)
        phase = workflow["usb_qualification_reboot"]
        _require(
            workflow["schema"] == "rocell.physical_camera_source_workflow_readback.v13"
            and workflow.get("configuration_epochs") is not None
            and phase["state"] == "QUERY_REQUESTED"
            and phase["original_campaign"] is None
            and phase["original_campaign_event"] is None,
            "USB_REBOOT_CURRENT_QUERY_REQUIRED",
        )
        inspection = UsbRebootPreparation(canonical(phase["preparation"]["document"]))
        policy = UsbIdentityStagePolicy(
            canonical(phase["policy_review"]["document"]["policy"])
        )
        _require(
            inspection.sha256 == phase["preparation"]["evidence_sha256"]
            and canonical(inspection.to_dict()["operation"])
            == campaign.operation.payload
            and campaign.identity.sha256 == phase["identity"]["evidence_sha256"]
            and campaign.identity.to_dict()["runtime_review_sha256"]
            == phase["runtime_review"]["evidence_sha256"],
            "USB_REBOOT_CURRENT_REVIEW_CHANGED",
        )
        records = [workflow["prerequisites"], workflow["configuration_epochs"]]
        records += [
            workflow["qualification_cycles"][-1][role]
            for role in ("receipt", "assessment", "review")
        ]
        records += [
            workflow["static_contract"][role]
            for role in ("receipt", "assessment", "review")
        ]
        records += [
            workflow["received_camera_cycles"][-1][role]
            for role in ("submission", "assessment", "review")
        ]
        records += [
            workflow["camera_identity_cycles"][-1][role]
            for role in ("metadata", "helper", "receipt", "assessment", "review")
        ]
        records += [workflow["usb_qualification_trial"]["plan"]]
        records += [phase[role] for role in tuple(USB_REBOOT_ROLE_BYTES)[:-2]]
        for key in (
            "usb_qualification_baseline",
            "usb_qualification_absence",
            "usb_qualification_reconnect",
        ):
            records += [
                record
                for record in workflow[key].values()
                if type(record) is dict
                and set(record)
                == {"document", "evidence_sha256", "reference", "retention"}
            ]
        refs = tuple(_reference(record) for record in records)
        _require(
            len({ref.evidence_id for ref in refs}) == len(refs),
            "USB_REBOOT_DISTINCT_CURRENT_REFERENCES_REQUIRED",
        )
        epoch_record = workflow["configuration_epochs"]
        identity = campaign.identity
        op = campaign.operation.to_dict()
        expected_query = canonical(phase["events"][-1])
        _require(
            phase["events"][-1]["detail_code"]
            == usb_reboot_event("QUERY_REQUESTED", phase["phase_id"]),
            "USB_REBOOT_CURRENT_QUERY_REQUIRED",
        )
        expected_binding = canonical(workflow["binding"])

        def facts(request, snapshot):
            check()
            _require(
                canonical(self.owner.setup.session.descriptor()) == expected_binding
                and snapshot.header.header_sha256 == workflow["session_header_sha256"]
                and snapshot.header.cell_id == request.cell_id == op["cell_id"]
                and snapshot.header.session_id == request.session_id == op["session_id"]
                and snapshot.header.source_binding_sha256
                == physical_camera_source_binding(op["source_sha256"])
                and request.action_id == "physical-native-usb-identity"
                and snapshot.head.head_sha256 == workflow["session_head_sha256"]
                and not snapshot.reconciliation_required
                and all(
                    snapshot.state_for(stage) is V2StageState.PASS
                    for stage in STAGE_ORDER[:3]
                )
                and snapshot.next_action.stage is STAGE
                and snapshot.next_action.stage_state is V2StageState.WAITING_OPERATOR
                and snapshot.committed_events
                and canonical(snapshot.committed_events[-1].to_dict())
                == expected_query,
                "USB_REBOOT_CURRENT_ADMISSION_CONTEXT_CHANGED",
            )
            inventory = {
                ref.evidence_id: canonical(ref.to_dict()) for ref in snapshot.evidence
            }
            _require(
                all(
                    inventory.get(ref.evidence_id) == canonical(ref.to_dict())
                    for ref in refs
                ),
                "USB_REBOOT_CURRENT_ORIGINAL_REFERENCE_CHANGED",
            )
            # Original-storage canonical JSON includes LF. USB wire canonical
            # bytes deliberately do not; neither format can replace the other.
            _require(
                canonical_sha256([ref.to_dict() for ref in snapshot.evidence])
                == workflow["evidence_inventory_sha256"],
                "USB_REBOOT_CURRENT_INVENTORY_CHANGED",
            )
            epochs = _verify_physical_configuration_epochs_after_usb_reboot(
                canonical(epoch_record["document"]),
                prerequisites=prerequisites,
                snapshot=snapshot,
                expected_sha256=epoch_record["evidence_sha256"],
            )
            hazard = dict(
                schema="rocell.usb_query_limited_hazard_assessment.v1",
                source_sha256=self.owner.source_sha256,
                session_id=op["session_id"],
                header_sha256=workflow["session_header_sha256"],
                policy_sha256=policy.sha256,
                inspection_sha256=inspection.sha256,
                admission_identity_sha256=identity.sha256,
                operation_sha256=campaign.operation.sha256,
                reviewed_originals=[ref.to_dict() for ref in refs],
                scope="SELECTED_CAMERA_USB_DESCRIPTORS_AND_PARENT_MAPPING_ONLY",
                enforced_budget=policy.to_dict()["budget"],
                leases=["CELL", "SESSION", "CAMERA"],
                original_first_three_stages="REVIEWED_PASS",
                original_query_state="WAITING_OPERATOR",
                observed_power="UNKNOWN",
                energy_envelope=None,
                automatic_retry_allowed=False,
                physical_isolation_verified=False,
                camera_capture_authorized=False,
                arm_access_authorized=False,
                motion_authorized=False,
                contact_authorized=False,
                meaning="Query-only software controls; not received hardware, isolation or general hazard qualification.",
            )
            documents = tuple(
                dict(
                    schema="rocell.usb_original_configuration_epoch.v1",
                    original_vector_sha256=epoch_record["evidence_sha256"],
                    original_reference=epoch_record["reference"],
                    original_binding=epochs.to_dict()["binding"],
                    entry=entry,
                    physical_configuration_qualified=False,
                )
                for entry in epochs.to_dict()["entries"]
            )
            check()
            return PhysicalUsbIdentityAdmissionFacts(
                hazard, documents, identity.to_dict(), stage_policy=policy
            )

        return facts

    def _collect_usb(self, workflow, prerequisites, predecessor, guard, cancellation):
        owner = self.owner
        phase = workflow["usb_qualification_reboot"]
        _require(
            phase["state"] == "QUERY_REQUESTED"
            and phase["original_campaign"] is None
            and phase["original_campaign_event"] is None,
            "USB_REBOOT_ORIGINAL_ATTEMPT_EXISTS",
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
            admission_facts=self._facts_provider(
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
                request_key="usb-reboot-" + phase["phase_id"],
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
            roles = tuple(USB_REBOOT_ROLE_BYTES)[:-2]
            owner._read_records(tx, [phase[role] for role in roles], guard)
            er = self._retain(tx, evidence.payload, "execution", phase["phase_id"])
            final = build_usb_reboot_qualification_phase(
                **predecessor,
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
