"""Original stage-4 USB query owner, not camera/arm qualification.

Only COLLECT reaches the fixed physical dispatcher. Inspection, review, cached
views and export cannot create a native owner. Original stage records and the
independent campaign journal remain distinct; quarantine is never bypassed to
copy a failed campaign into stage evidence.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from threading import Event, Lock, RLock
from time import monotonic_ns, time_ns
from typing import Any
from uuid import uuid4

from .commissioning_camera_persistence import physical_camera_source_binding
from .commissioning_usb_identity_persistence import (
    M1PhysicalUsbIdentityPersistence,
    PhysicalUsbIdentityAdmissionFacts,
)
from .physical_camera_identity_submission import CameraIdentityMetadata
from .physical_camera_usb_qualification import UsbQualificationPlan
from .physical_camera_setup_service import PhysicalCameraSetupService
from .physical_camera_selection import PhysicalCameraSelection
from .physical_camera_usb_baseline import (
    UsbBaselineInspection,
    build_usb_baseline_inspection,
    build_usb_baseline_outcome,
    USB_ROLE_BYTES,
    METADATA_ROLES,
)
from .physical_configuration_epochs import (
    _verify_physical_configuration_epochs_after_usb_identity,
)
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_durability import canonical_sha256
from .physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from .physical_onboarding_v2 import V2StageState
from .physical_usb_identity_campaign import (
    UsbIdentityOperation,
    PhysicalUsbIdentityCampaign,
    usb_identity_operation,
)
from .physical_usb_identity_dispatch import PhysicalUsbIdentityDispatchOwner
from .physical_usb_absence_service import (
    ACTIONS as ABSENCE_ACTIONS,
    COLLECT as ABSENCE_COLLECT,
)
from .physical_usb_reconnect_service import (
    ACTIONS as RECONNECT_ACTIONS,
    PREPARE as RECONNECT_PREPARE,
    BOOT_COLLECT as RECONNECT_BOOT_COLLECT,
    COLLECT as RECONNECT_COLLECT,
)
from .physical_usb_reboot_service import (
    ACTIONS as REBOOT_ACTIONS,
    PREPARE as REBOOT_PREPARE,
    BOOT_COLLECT as REBOOT_BOOT_COLLECT,
    COLLECT as REBOOT_COLLECT,
)
from .physical_usb_complete_service import ACTIONS as COMPLETE_ACTIONS
from .usb_identity_stage_policy import (
    UsbIdentityAdmissionIdentity,
    UsbIdentityPolicyReview,
    UsbIdentityStagePolicy,
    inspect_usb_identity_stage_policy,
)
from .wizard_actions import WizardError
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.providers.windows.usb_identity_registration import (
    UsbIdentityRuntimeRegistration,
    UsbIdentityRuntimeReview,
    usb_identity_runtime_candidate,
    inspect_usb_identity_runtime,
    review_usb_identity_runtime,
)

INSPECT = "physical_usb_identity_inspect"
REVIEW = "physical_usb_identity_review"
COLLECT = "physical_usb_identity_collect"
EXPORT = "physical_usb_identity_export"
DECLARE = "physical_usb_qualification_declare"
BEGIN = "physical_usb_qualification_begin"
PREPARE = "physical_usb_qualification_prepare"
PHASE_REVIEW = "physical_usb_qualification_review"
PHASE_COLLECT = "physical_usb_qualification_collect"
PHASE_ACTIONS = frozenset((BEGIN, PREPARE, PHASE_REVIEW, PHASE_COLLECT))
ACTIONS = frozenset(
    (
        INSPECT,
        REVIEW,
        COLLECT,
        EXPORT,
        DECLARE,
        *PHASE_ACTIONS,
        *ABSENCE_ACTIONS,
        *RECONNECT_ACTIONS,
        *REBOOT_ACTIONS,
        *COMPLETE_ACTIONS,
    )
)
SCHEMA = "rocell.wizard_usb_identity.v1"
QUALIFICATION_SCHEMA = "rocell.wizard_usb_qualification.v1"
QUALIFICATION_MEANING = (
    "Trial-plan workflow only; no phase evidence, boot observation or qualification. "
    "The earlier USB baseline remains historical and is not a trial BASELINE. "
    "Disconnect/reconnect and Windows Restart are manual; no automatic device action. "
    "Full original plan/events are in the separate USB metadata export."
)
RESULT_SCHEMA = "rocell.wizard_usb_identity_action_result.v1"
MEANING = "One original USB baseline query; not reconnect/reboot qualification, camera capture or arm authority."
FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    camera_capture_authorized=False,
    arm_access_authorized=False,
)
_STAGE = STAGE_ORDER[3]
_PRE_QUERY_ROLES = ("inspection", "policy_review", "runtime_review", "identity")


def _require(
    value: bool,
    code: str,
    message: str = "Original USB context changed; inspect/export without replay.",
) -> None:
    if not value:
        raise WizardError(code, message)


def _actor(value: Any) -> None:
    _require(
        type(value) is str
        and 1 <= len(value) <= 64
        and value == value.strip()
        and all(32 <= ord(c) < 127 for c in value),
        "USB_OPERATOR_LABEL_INVALID",
    )


def _plan_label(value: Any) -> None:
    _require(
        type(value) is str
        and 0 < len(value.encode("utf-8")) <= 128
        and value == value.strip()
        and all(ord(c) >= 32 and ord(c) != 127 for c in value),
        "USB_PLAN_LABEL_INVALID",
        "Use a nonempty, trimmed, single-line cable or port label of at most 128 UTF-8 bytes.",
    )


def _reference(record: dict[str, Any]):
    ref = _parse_evidence_reference(record["reference"])
    payload = canonical(record["document"])
    _require(
        record["retention"] == "M1_FULL_BYTES_READ_BACK"
        and record["evidence_sha256"] == ref.payload_sha256 == digest(payload)
        and len(payload) == ref.payload_bytes,
        "USB_ORIGINAL_RECORD_CHANGED",
    )
    return ref


def _selection(metadata: dict[str, Any]) -> PhysicalCameraSelection:
    artifact = CameraIdentityMetadata(canonical(metadata["document"]))
    _require(
        artifact.sha256 == metadata["evidence_sha256"], "USB_METADATA_HASH_CHANGED"
    )
    selected = artifact.to_dict()["selection"]
    _require(selected is not None, "USB_REVIEWED_NATIVE_SELECTION_REQUIRED")
    result = PhysicalCameraSelection(canonical(selected["document"]))
    _require(result.sha256 == selected["sha256"], "USB_SELECTED_TARGET_CHANGED")
    return result


def _observation(evidence: OwnedUsbIdentityRunEvidence | None) -> dict[str, Any] | None:
    original = None if evidence is None else evidence.observation
    if original is None:
        return None
    data = original.to_dict()
    device, link = data["device_descriptor"] or {}, data["link"] or {}
    mapping = data["post_mapping"] or data["pre_mapping"] or {}
    hops = mapping.get("hops") or []
    return dict(
        outcome=data["outcome"],
        serial_values=[
            row["value"]
            for row in data["serial_descriptors"]
            if row["value"] is not None
        ],
        vid=device.get("vid"),
        pid=device.get("pid"),
        bcd_usb=device.get("bcd_usb"),
        i_serial_number=device.get("i_serial_number"),
        physical_usb_instance_id=mapping.get("physical_usb_instance_id"),
        host_controller_instance_id=mapping.get("host_controller_instance_id"),
        hub_port=None if not hops else hops[0]["connection_index"],
        ex_speed=link.get("ex_speed"),
        ex_v2_available=link.get("ex_v2_available", False),
        operating_at_superspeed=link.get("operating_superspeed_or_higher"),
        operating_at_superspeed_plus=link.get("operating_superspeed_plus_or_higher"),
    )


class PhysicalUsbIdentityService:
    def __init__(self, setup: PhysicalCameraSetupService):
        if type(setup) is not PhysicalCameraSetupService:
            raise TypeError("Exact application-owned camera setup required")
        self.setup = setup
        self.workspace, self.source_sha256, self.launch_id = (
            setup.workspace,
            setup.source_sha256,
            setup.launch_id,
        )
        self._lock, self._operation_lock = RLock(), Lock()
        self._workflow: dict[str, Any] | None = None
        self._baseline: dict[str, Any] | None = None
        self._qualification_trial: dict[str, Any] | None = None
        self._stages: dict[str, str] | None = None
        self._publication = dict(status="NOT_PUBLISHED", operation_id=None)
        self._pending_result: bytes | None = None
        self._pending_action: str | None = None
        self._attempt: dict[str, Any] | None = None
        self._inspection_attempt: dict[str, Any] | None = None
        self._attempted: set[str] = set()
        self._export_receipt: dict[str, Any] | None = None
        self._export_publication: dict[str, Any] | None = None
        self._dispatch: PhysicalUsbIdentityDispatchOwner | None = None
        self._dispatch_result: dict[str, Any] | None = None
        self._generation = 0
        self._declaration_attempted = False
        from .physical_usb_trial_service import _UsbTrialBaseline

        self._trial = _UsbTrialBaseline(self)
        from .physical_usb_absence_service import _UsbTrialAbsence

        self._absence = _UsbTrialAbsence(self)
        from .physical_usb_reconnect_service import _UsbTrialReconnect

        self._reconnect = _UsbTrialReconnect(self)
        from .physical_usb_reboot_service import _UsbTrialReboot

        self._reboot = _UsbTrialReboot(self)
        from .physical_usb_complete_service import _UsbCompleteReview

        self._complete = _UsbCompleteReview(self)

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

    def _adopt(self):
        self._workflow = self.setup.original_source_workflow()
        self._baseline = deepcopy((self._workflow or {}).get("usb_baseline"))
        self._qualification_trial = deepcopy(
            (self._workflow or {}).get("usb_qualification_trial")
        )
        self._trial.adopt(self._workflow or {})
        self._absence.adopt(self._workflow or {})
        self._reconnect.adopt(self._workflow or {})
        self._reboot.adopt(self._workflow or {})
        self._complete.adopt(self._workflow or {})
        rows = self.setup.session.view().get("stages")
        self._stages = (
            None
            if rows is None
            else {
                stage.value: rows[n]["state"] for n, stage in enumerate(STAGE_ORDER[:4])
            }
        )

    def observe_setup(self):
        with self._lock:
            if self._pending_result is not None:
                return
            if self.setup.view()["publication"]["status"] != "CURRENT":
                self.invalidate()
                return
            self._adopt()
            self._publication = deepcopy(self.setup.view()["publication"])
            if (self._workflow or {}).get("camera_mode_entry") is not None:
                # The closed v6 identity card ends at stage 4. Keep its complete
                # history visible/exportable, but do not label it as the current
                # stage-5 workflow or weaken its public future-stage restrictions.
                self._publication = dict(status="HISTORICAL_HELD", operation_id=None)

    def invalidate(self):
        with self._lock:
            self._generation += 1
            self._publication = dict(status="HISTORICAL_HELD", operation_id=None)
            self._pending_result = self._pending_action = None
            if self._dispatch is not None:
                self._dispatch.invalidate()
            self._absence.invalidate()
            self._reconnect.invalidate()
            self._reboot.invalidate()

    def _acquisition_owner(self):
        # A successor attempt owns routing even before its first retained role.
        # An unavailable successor must never fall back to historical phases.
        if self._reboot.reboot is not None or self._reboot.attempt is not None:
            return "AFTER_REBOOT", self._reboot
        if self._reconnect.reconnect is not None or self._reconnect.attempt is not None:
            return "AFTER_RECONNECT", self._reconnect
        return "BASELINE", self._trial

    def acquisition_started(self, action_id, operation_id, started_at_ns):
        """Route one server token to exactly one active original interval."""
        with self._lock:
            phase, subject = self._acquisition_owner()
            token = subject.acquisition_started(action_id, operation_id, started_at_ns)
            return None if token is None else dict(phase=phase, token=token)

    def acquisition_published(self, routed, *, finished_at_ns, document, result_sha256):
        """Only Arrival calls this after exact retention and durable completion."""
        if routed is None:
            return
        with self._lock:
            if type(routed) is not dict or set(routed) != {"phase", "token"}:
                return
            active, subject = self._acquisition_owner()
            if routed["phase"] != active:
                return
            subject.acquisition_published(
                routed["token"],
                finished_at_ns=finished_at_ns,
                document=document,
                result_sha256=result_sha256,
            )

    def _execution(self) -> OwnedUsbIdentityRunEvidence | None:
        baseline = self._baseline or {}
        record = baseline.get("execution")
        if record is not None:
            result = OwnedUsbIdentityRunEvidence(canonical(record["document"]))
            _require(
                result.sha256 == record["evidence_sha256"], "USB_EXECUTION_HASH_CHANGED"
            )
            return result
        original = baseline.get("original_campaign")
        if original is None and self._attempt:
            original = (self._attempt.get("dispatch") or {}).get("original")
        if original and original.get("evidence") is not None:
            result = OwnedUsbIdentityRunEvidence(canonical(original["evidence"]))
            _require(
                result.sha256 == original["evidence_sha256"],
                "USB_EXECUTION_HASH_CHANGED",
            )
            return result
        return None

    def _summaries(self):
        baseline = self._baseline or {}
        record = baseline.get("inspection") or self._inspection_attempt
        inspection = review = None
        if record is not None:
            original = UsbBaselineInspection(canonical(record["document"]))
            d = original.to_dict()
            op = d["operation"]
            selected = PhysicalCameraSelection(canonical(op["selection"]))
            sd = selected.identity_document
            inspection = dict(
                evidence_sha256=original.sha256,
                operator_id=d["binding"]["operator_id"],
                collection_launch_id=d["binding"]["collection_launch_id"],
                policy_sha256=d["policy_sha256"],
                operation_sha256=d["operation_sha256"],
                runtime_registration_sha256=d["runtime_report"][
                    "runtime_registration_sha256"
                ],
                helper_sha256=op["runtime"]["helper"]["sha256"],
                files_verified=len(d["runtime_report"]["files"]),
                target=dict(
                    selection_sha256=selected.sha256,
                    native_identity_sha256=sd["native_identity_sha256"],
                    endpoint_sha256=sd["endpoint_sha256"],
                    symbolic_link=sd["symbolic_link"],
                    device_instance_id=sd["metadata_review"]["observed_instance_id"],
                ),
            )
        if all(baseline.get(role) is not None for role in _PRE_QUERY_ROLES[1:]):
            saved = UsbIdentityRuntimeReview(
                canonical(baseline["runtime_review"]["document"])
            ).to_dict()
            review = dict(
                policy_review_sha256=baseline["policy_review"]["evidence_sha256"],
                runtime_review_sha256=baseline["runtime_review"]["evidence_sha256"],
                identity_sha256=baseline["identity"]["evidence_sha256"],
                reviewer_id=saved["reviewer_id"],
                review_launch_id=saved["launch_session_id"],
            )
        evidence = self._execution()
        return (
            inspection,
            review,
            None if evidence is None else evidence.safe_summary(),
            _observation(evidence),
        )

    def view(self):
        with self._lock:
            publication = deepcopy(self._publication)
            if (
                publication["status"] == "CURRENT"
                and self.setup.view()["publication"]["status"] != "CURRENT"
            ):
                publication = dict(status="HISTORICAL_HELD", operation_id=None)
            baseline = self._baseline
            metadata = (self._workflow or {}).get("camera_identity_cycles", [])
            status = (
                "AWAITING_INSPECTION"
                if metadata and metadata[-1]["state"] == "REVIEWED_BLOCKED"
                else "NOT_STARTED"
            )
            if baseline:
                status = {
                    "REVIEW_PENDING": "AWAITING_REVIEW",
                    "READY_TO_QUERY": "READY_TO_QUERY",
                    "ORIGINAL_CAMPAIGN_HELD": "HELD",
                    "RETAINED_BLOCKED": "HELD",
                }.get(baseline["state"], "INCOMPLETE_HELD")
            inspection, review, execution, observation = self._summaries()
            if (
                baseline
                and baseline["state"] == "RETAINED_BLOCKED"
                and execution
                and execution["status"] == "OBSERVED"
            ):
                status = "OBSERVED_UNQUALIFIED"
            if publication["status"] != "CURRENT" and (self._workflow or self._attempt):
                status = "HISTORICAL_HELD"
            if (
                self._qualification_trial is not None
                and publication["status"] != "PENDING"
            ):
                publication = dict(status="HISTORICAL_HELD", operation_id=None)
                status = "HISTORICAL_HELD"
            pending = publication["status"] == "PENDING"
            next_action = {
                "AWAITING_INSPECTION": INSPECT,
                "AWAITING_REVIEW": REVIEW,
                "READY_TO_QUERY": COLLECT,
                "HELD": EXPORT,
                "INCOMPLETE_HELD": EXPORT,
                "OBSERVED_UNQUALIFIED": EXPORT,
            }.get(status)
            if (
                publication["status"] != "CURRENT"
                or next_action
                and self.blocked_reason(next_action) is not None
            ):
                next_action = None
            return deepcopy(
                dict(
                    schema=SCHEMA,
                    source_sha256=self.source_sha256,
                    launch_session_id=self.launch_id,
                    original_context=self._context(),
                    publication=publication,
                    status=status,
                    stage_states=self._stages,
                    usb_id=(baseline or self._attempt or {}).get("usb_id"),
                    inspection=None if pending else inspection,
                    review=None if pending else review,
                    execution=None if pending else execution,
                    observation=None if pending else observation,
                    next_action=next_action,
                    export_receipt=self._export_receipt,
                    meaning=MEANING,
                    **FLAGS,
                )
            )

    def qualification_view(self):
        """Only cached original declaration facts; no boot or phase acquisition."""
        with self._lock:
            publication = deepcopy(self._publication)
            if (
                publication["status"] == "CURRENT"
                and self.setup.view()["publication"]["status"] != "CURRENT"
            ):
                publication = dict(status="HISTORICAL_HELD", operation_id=None)
            trial = self._qualification_trial
            status = (
                "NOT_DECLARED"
                if trial is None
                else (
                    "DECLARED"
                    if trial["state"] == "PLAN_DECLARED"
                    else "INCOMPLETE_HELD"
                )
            )
            if publication["status"] == "HISTORICAL_HELD":
                status = "HISTORICAL_HELD"
            plan = None
            if trial is not None and trial.get("plan") is not None:
                record = trial["plan"]
                original = UsbQualificationPlan(canonical(record["document"]))
                _require(
                    original.sha256 == record["evidence_sha256"],
                    "USB_PLAN_HASH_CHANGED",
                )
                data = original.to_dict()
                _require(
                    data["mode"] == "PHYSICAL", "USB_PLAN_PHYSICAL_CONTEXT_REQUIRED"
                )
                plan = dict(
                    plan_sha256=original.sha256,
                    **{
                        key: data[key]
                        for key in (
                            "binding",
                            "operator_id",
                            "launch_session_id",
                            "cable_label",
                            "port_label",
                            "received_label",
                            "phases",
                        )
                    },
                )
            next_action = (
                DECLARE
                if publication["status"] == "CURRENT"
                and status == "NOT_DECLARED"
                and self.blocked_reason(DECLARE) is None
                else None
            )
            if publication["status"] == "PENDING":
                plan, next_action = None, None
                status = "NOT_DECLARED"
            result = dict(
                schema=QUALIFICATION_SCHEMA,
                source_sha256=self.source_sha256,
                launch_session_id=self.launch_id,
                original_context=self._context(),
                publication=publication,
                status=status,
                plan=plan,
                next_action=next_action,
                export_receipt=self._export_receipt,
                meaning=QUALIFICATION_MEANING,
                **FLAGS,
            )
            return self._complete.projection(
                self._reboot.projection(
                    self._reconnect.projection(
                        self._absence.projection(self._trial.projection(result))
                    )
                )
            )

    def _material(self):
        return dict(
            workflow=self.setup.original_source_workflow(),
            binding=self.setup.session.descriptor(),
            verification=self.setup.session.view()["verification"],
            publication=self.setup.view()["publication"],
        )

    def context_sha256(self, *, native_camera=None, helper=None):
        with self._lock:
            return digest(
                canonical(
                    dict(
                        source_sha256=self.source_sha256,
                        launch_id=self.launch_id,
                        original=self._material(),
                        attempted=sorted(self._attempted),
                        attempt=self._attempt,
                        qualification=self._trial.context(native_camera, helper),
                        absence=self._absence.context(),
                        reconnect=self._reconnect.context(native_camera, helper),
                        reboot=self._reboot.context(native_camera, helper),
                        complete=self._complete.context(),
                    )
                )
            )

    def fields(self, action_id):
        def check(name, label):
            return dict(
                name=name, type="checkbox", label=label, required=True, default=False
            )

        def actor(name, label):
            return dict(
                name=name,
                type="text",
                label=label,
                required=True,
                default="",
                max_length=64,
            )

        if action_id in PHASE_ACTIONS:
            return self._trial.fields(action_id, check, actor)
        if action_id in ABSENCE_ACTIONS:
            return self._absence.fields(action_id, check, actor)
        if action_id in RECONNECT_ACTIONS:
            return self._reconnect.fields(action_id, check, actor)
        if action_id in REBOOT_ACTIONS:
            return self._reboot.fields(action_id, check, actor)
        if action_id in COMPLETE_ACTIONS:
            return self._complete.fields(action_id, check, actor)

        return {
            DECLARE: (
                actor("operator_id", "Declaring operator label"),
                *(
                    dict(
                        name=name,
                        type="text",
                        label=label,
                        required=True,
                        default="",
                        max_length=128,
                    )
                    for name, label in (
                        ("cable_label", "Declared cable label"),
                        ("port_label", "Declared host port label"),
                    )
                ),
                check(
                    "confirm_file_only",
                    "Save the original trial plan only; no USB query, boot observation, disconnect or restart",
                ),
            ),
            INSPECT: (
                actor("operator_id", "Inspecting operator label"),
                check(
                    "confirm_file_inspection",
                    "Inspect only the fixed USB-query files and original selected target",
                ),
            ),
            REVIEW: (
                actor(
                    "reviewer_id",
                    "Distinct reviewer label (not authenticated identity)",
                ),
                check(
                    "confirm_policy_review", "Review the exact stage-4 USB-query policy"
                ),
                check(
                    "confirm_runtime_review", "Review the exact inspected USB runtime"
                ),
                check(
                    "confirm_exact_target",
                    "Review only this original selected camera target",
                ),
            ),
            COLLECT: (
                check(
                    "confirm_usb_query",
                    "Run one bounded USB descriptor query; hub handles will be opened",
                ),
                check(
                    "confirm_no_capture_or_arm",
                    "This does not authorize camera capture, arm access, power or motion",
                ),
            ),
            EXPORT: (
                check(
                    "confirm_metadata_export",
                    "Export full original USB metadata, including device identifiers and failure bytes",
                ),
            ),
        }.get(action_id, ())

    def _attempt_key(self, action, workflow):
        return action + ":" + workflow["session_head_sha256"]

    def blocked_reason(self, action_id, *, native_camera=None, helper=None):
        if action_id not in ACTIONS or self.setup.mode != "physical":
            return "Original USB identity requires physical diagnostic mode."
        if action_id == EXPORT:
            return (
                None
                if self.retained_diagnostics() is not None
                else "No USB inspection or attempted query is retained."
            )
        workflow = self.setup.original_source_workflow()
        if not workflow or self.setup.view()["publication"]["status"] != "CURRENT":
            return "Explicitly refresh/reopen and publish the original camera session first."
        if workflow.get("configuration_epochs") is None:
            return "The original configuration-epoch vector is absent; this legacy session cannot admit a USB query."
        if action_id in COMPLETE_ACTIONS:
            return self._complete.blocked_reason(action_id, workflow)
        if (
            workflow.get("usb_qualification_complete") is not None
            or self._complete.attempt is not None
        ):
            return "Final identity review supersedes earlier USB actions; inspect or export the retained history without replay."
        if action_id in REBOOT_ACTIONS:
            return self._reboot.blocked_reason(
                action_id, workflow, native_camera, helper
            )
        if (
            workflow.get("usb_qualification_reboot") is not None
            or self._reboot.attempt is not None
        ):
            return "The original reboot interval or its attempted Begin supersedes earlier USB mutation actions; inspect or export their history without replay."
        if action_id in RECONNECT_ACTIONS:
            return self._reconnect.blocked_reason(
                action_id, workflow, native_camera, helper
            )
        if workflow.get("usb_qualification_reconnect") is not None:
            return "The original reconnect interval supersedes earlier USB mutation actions; inspect or export their history."
        if action_id in ABSENCE_ACTIONS:
            return self._absence.blocked_reason(action_id, workflow)
        if action_id in PHASE_ACTIONS:
            return self._trial.blocked_reason(
                action_id, workflow, native_camera, helper
            )
        if action_id == DECLARE:
            if (
                self._declaration_attempted
                or workflow.get("usb_qualification_trial") is not None
            ):
                return "This original trial declaration already exists or was attempted; refresh/export the original record without replay."
            metadata = workflow.get("camera_identity_cycles", [])
            if not metadata or metadata[-1]["state"] != "REVIEWED_BLOCKED":
                return "Complete the original received-camera PASS and exact metadata review before declaring the trial."
            from .physical_camera_usb_trial_readback import (
                usb_qualification_predecessor_references,
            )

            try:
                usb_qualification_predecessor_references(workflow)
            except (ValueError, KeyError, TypeError):
                return "The trial requires exact received PASS, reviewed identity originals and no partial, uncertain or unclean prior USB attempt."
            verification = self.setup.session.view()["verification"]
            if (
                not verification
                or verification.get("effects_allowed_by_m1_storage") is not True
            ):
                return "The original store must be verified and unheld; declaration cannot clear quarantine."
            return None
        metadata = workflow.get("camera_identity_cycles", [])
        if not metadata or metadata[-1]["state"] != "REVIEWED_BLOCKED":
            return "Complete exact original stage-4 metadata review first."
        try:
            _selection(metadata[-1]["metadata"])
        except (ValueError, TypeError, KeyError):
            return (
                "Original metadata must contain an unambiguous reviewed native target."
            )
        if self._attempt_key(action_id, workflow) in self._attempted:
            return "This exact action has already been attempted; inspect/export without replay."
        baseline = workflow.get("usb_baseline")
        if workflow.get("usb_qualification_trial") is not None:
            return "The original qualification trial supersedes baseline actions; export the separate original records."
        required = {INSPECT: None, REVIEW: "REVIEW_PENDING", COLLECT: "READY_TO_QUERY"}
        if (None if baseline is None else baseline["state"]) != required[action_id]:
            return "Complete the preceding original USB step; partial writes or existing attempts cannot be replayed."
        return None

    def _check(self, cancellation, deadline, *, source=True):
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline,
            "USB_ACTION_INTERRUPTED",
        )
        if source:
            _require(
                source_fingerprint(self.workspace) == self.source_sha256,
                "USB_SOURCE_CHANGED",
            )
        _require(
            not cancellation.is_set() and monotonic_ns() < deadline,
            "USB_ACTION_INTERRUPTED",
        )

    def _record(self, artifact, role, usb_id):
        return dict(
            document=artifact.to_dict(),
            evidence_sha256=artifact.sha256,
            reference=None,
            retention="COLLECTED_NOT_M1_RETAINED",
            label=f"camera-usb-{role.replace('_', '-')}-v1:{usb_id}",
        )

    def _retain(self, tx, artifact, role, usb_id):
        record = self._record(artifact, role, usb_id)
        with self._lock:
            assert self._attempt is not None
            self._attempt["records"][role] = record
            if role == "inspection":
                self._inspection_attempt = record
        ref = tx.store_evidence(
            _STAGE,
            artifact.payload,
            label=record["label"],
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        record.update(
            reference=ref.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        _require(
            tx.read_stage_evidence(ref) == artifact.payload,
            "USB_ORIGINAL_READBACK_CHANGED",
        )
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        return ref

    def _read_records(self, tx, records, check):
        refs = []
        for record in records:
            check()
            ref = _reference(record)
            _require(
                tx.read_stage_evidence(ref) == canonical(record["document"]),
                "USB_ORIGINAL_SUBJECT_CHANGED",
            )
            refs.append(ref)
        return refs

    @staticmethod
    def _commit(tx, phase, state, usb_id, refs):
        tx.commit_stage_state(
            _STAGE,
            state,
            occurred_at_ns=time_ns(),
            detail_code="CAMERA_USB_"
            + phase
            + "_"
            + usb_id.removeprefix("usbidentity-").upper(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=tuple(sorted(refs, key=lambda ref: ref.evidence_id)),
        )

    def _build_identity(self, inspection, policy_review, runtime_review, references):
        data = inspection.to_dict()
        op = UsbIdentityOperation(canonical(data["operation"]))
        selection = PhysicalCameraSelection(canonical(op.to_dict()["selection"]))
        sd = selection.identity_document
        return UsbIdentityAdmissionIdentity(
            canonical(
                dict(
                    schema="rocell.usb_identity_admission_identity.v1",
                    **{
                        k: data["binding"][k]
                        for k in (
                            "cell_id",
                            "session_id",
                            "source_sha256",
                            "header_sha256",
                        )
                    },
                    stage_policy_sha256=data["policy_sha256"],
                    policy_review_sha256=policy_review.sha256,
                    runtime_review_sha256=runtime_review.sha256,
                    runtime_registration_sha256=data["runtime_report"][
                        "runtime_registration_sha256"
                    ],
                    selection_sha256=selection.sha256,
                    native_identity_sha256=sd["native_identity_sha256"],
                    endpoint_sha256=sd["endpoint_sha256"],
                    device_instance_id_sha256=digest(
                        sd["metadata_review"]["observed_instance_id"].encode("utf-8")
                    ),
                    operation_sha256=op.sha256,
                    original_subjects=[
                        dict(
                            role=role,
                            reference=ref.to_dict(),
                            document_sha256=ref.payload_sha256,
                        )
                        for role, ref in zip(
                            ("metadata", "policy_review", "runtime_review"), references
                        )
                    ],
                )
            )
        )

    def _facts_provider(self, workflow, prerequisites, campaign, check):
        """Freeze verified subjects once; compare them to EACH actual leased snapshot.

        The original vector is an observed software dependency record, not a
        claim that its UNOBSERVED physical configuration has been qualified.
        """
        reconnect = workflow.get("usb_qualification_reconnect")
        phase = (
            reconnect
            if reconnect is not None
            else workflow.get("usb_qualification_baseline")
        )
        baseline = workflow["usb_baseline"] if phase is None else phase
        _require(
            workflow.get("configuration_epochs") is not None,
            "USB_ORIGINAL_CONFIGURATION_EPOCHS_REQUIRED",
        )
        if phase is None:
            inspection = UsbBaselineInspection(
                canonical(baseline["inspection"]["document"])
            )
            policy = UsbIdentityStagePolicy(canonical(inspection.to_dict()["policy"]))
        elif reconnect is not None:
            from .physical_camera_usb_reconnect import UsbReconnectPreparation

            inspection = UsbReconnectPreparation(
                canonical(reconnect["preparation"]["document"])
            )
            policy = UsbIdentityStagePolicy(
                canonical(reconnect["policy_review"]["document"]["policy"])
            )
        else:
            from .physical_camera_usb_phase import UsbTrialBaselinePreparation

            inspection = UsbTrialBaselinePreparation(
                canonical(phase["preparation"]["document"])
            )
            policy = UsbIdentityStagePolicy(
                canonical(phase["policy_review"]["document"]["policy"])
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
            workflow["camera_identity_cycles"][-1][role] for role in METADATA_ROLES
        ]
        if phase is None:
            records += [baseline[role] for role in _PRE_QUERY_ROLES]
        else:
            records += [workflow["usb_qualification_trial"]["plan"]]
            records += [
                phase[role]
                for role in (
                    "enrollment",
                    "preparation",
                    "policy_review",
                    "runtime_review",
                    "identity",
                    "boot_request",
                    "host_boot",
                )
            ]
            if reconnect is not None:
                from .physical_camera_usb_reconnect_constants import (
                    USB_RECONNECT_ROLE_BYTES,
                )

                records += [reconnect[role] for role in ("operator_event", "operation")]
                for key in ("usb_qualification_baseline", "usb_qualification_absence"):
                    records += [
                        record
                        for record in workflow[key].values()
                        if type(record) is dict
                        and set(record)
                        == {"document", "evidence_sha256", "reference", "retention"}
                    ]
        refs = tuple(_reference(record) for record in records)
        epoch_record = workflow["configuration_epochs"]
        # The reader authenticated every role's semantics. This additional
        # vector verification uses the fresh committed prefix, not a fabricated
        # historical snapshot or an equality test against today's full inventory.
        identity = campaign.identity
        op = campaign.operation.to_dict()
        expected_query = canonical(
            baseline["query_event"] if phase is None else phase["events"][-1]
        )
        expected_binding = canonical(workflow["binding"])

        def facts(request, snapshot):
            check()
            _require(
                canonical(self.setup.session.descriptor()) == expected_binding
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
                and snapshot.next_action.stage is _STAGE
                and snapshot.next_action.stage_state is V2StageState.WAITING_OPERATOR
                and snapshot.committed_events
                and canonical(snapshot.committed_events[-1].to_dict())
                == expected_query,
                "USB_CURRENT_ADMISSION_CONTEXT_CHANGED",
            )
            inventory = {
                ref.evidence_id: canonical(ref.to_dict()) for ref in snapshot.evidence
            }
            _require(
                all(
                    inventory.get(ref.evidence_id) == canonical(ref.to_dict())
                    for ref in refs
                ),
                "USB_CURRENT_ORIGINAL_REFERENCE_CHANGED",
            )
            if reconnect is not None:
                # This is an original-store inventory hash, whose canonical JSON
                # includes LF; the nearby USB wire serializer deliberately does not.
                _require(
                    canonical_sha256([ref.to_dict() for ref in snapshot.evidence])
                    == workflow["evidence_inventory_sha256"],
                    "USB_RECONNECT_CURRENT_INVENTORY_CHANGED",
                )
            if phase is None:
                epoch_verifier = (
                    _verify_physical_configuration_epochs_after_usb_identity
                )
            elif reconnect is not None:
                from .physical_configuration_epochs import (
                    _verify_physical_configuration_epochs_after_usb_reconnect,
                )

                epoch_verifier = (
                    _verify_physical_configuration_epochs_after_usb_reconnect
                )
            else:
                from .physical_configuration_epochs import (
                    _verify_physical_configuration_epochs_after_usb_phase,
                )

                epoch_verifier = _verify_physical_configuration_epochs_after_usb_phase
            epochs = epoch_verifier(
                canonical(epoch_record["document"]),
                prerequisites=prerequisites,
                snapshot=snapshot,
                expected_sha256=epoch_record["evidence_sha256"],
            )
            hazard = dict(
                schema="rocell.usb_query_limited_hazard_assessment.v1",
                source_sha256=self.source_sha256,
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

    def _collect(self, workflow, prerequisites, runtime, cancellation, deadline, guard):
        baseline = workflow["usb_baseline"]
        inspection = UsbBaselineInspection(
            canonical(baseline["inspection"]["document"])
        )
        operation = UsbIdentityOperation(canonical(inspection.to_dict()["operation"]))
        identity = UsbIdentityAdmissionIdentity(
            canonical(baseline["identity"]["document"])
        )
        review = UsbIdentityRuntimeReview(
            canonical(baseline["runtime_review"]["document"])
        )
        campaign = PhysicalUsbIdentityCampaign(
            operation, identity=identity, review=review
        )
        policy = UsbIdentityStagePolicy(canonical(inspection.to_dict()["policy"]))
        _require(
            type(runtime) is PhysicalOnboardingM1Runtime
            and runtime.deployment_root == Path(workflow["binding"]["directory"])
            and runtime.cell.cell_id == workflow["binding"]["cell_id"]
            and runtime.source_binding_sha256
            == physical_camera_source_binding(self.source_sha256),
            "USB_EXACT_ORIGINAL_RUNTIME_REQUIRED",
        )
        facts = self._facts_provider(workflow, prerequisites, campaign, guard)
        persistence = M1PhysicalUsbIdentityPersistence(
            runtime,
            workspace_source_sha256=self.source_sha256,
            stage_policy=policy,
            expected_usb_query_policy_sha256=policy.sha256,
            admission_facts=facts,
        )
        owner = PhysicalUsbIdentityDispatchOwner(
            persistence, campaign, revalidate_context=guard
        )
        self._dispatch = owner
        try:
            result = owner.perform(
                request_key="usb-baseline-" + baseline["usb_id"],
                cancellation=cancellation,
            )
            self._dispatch_result = deepcopy(result)
        finally:
            assert self._attempt is not None
            self._attempt["dispatch"] = owner.retained_diagnostics()
        original = owner.retained_diagnostics()["original"]
        guard()
        evidence = (
            None
            if not original or original.get("evidence") is None
            else OwnedUsbIdentityRunEvidence(canonical(original["evidence"]))
        )
        effect = None if evidence is None else evidence.bounded_effect_summary()
        if (
            original
            and original["result"]["state"] == "SEALED_KNOWN"
            and effect
            and effect["current_complete"]
            and effect["process_cleanup_confirmed"]
            and effect["usb_cleanup_confirmed"]
        ):
            # A separate stage package joins the audited campaign original.
            # This path is not entered under quarantine or uncertain cleanup.
            verified = persistence.verification(workflow["binding"]["session_id"])
            with persistence.stage_transaction(
                workflow["binding"]["session_id"],
                expected_challenge_sha256=verified.challenge_sha256,
            ) as tx:
                self._read_records(
                    tx, [baseline[role] for role in _PRE_QUERY_ROLES], guard
                )
                guard()
                execution_ref = self._retain(
                    tx, evidence, "execution", baseline["usb_id"]
                )
                outcome = build_usb_baseline_outcome(
                    inspection=inspection,
                    identity=identity,
                    execution_reference=execution_ref,
                    campaign_original=original,
                    recorded_at_ns=time_ns(),
                )
                guard()
                outcome_ref = self._retain(tx, outcome, "outcome", baseline["usb_id"])
                refs = [_reference(baseline[role]) for role in _PRE_QUERY_ROLES]
                guard()
                self._commit(
                    tx,
                    "QUERY_RETAINED",
                    V2StageState.BLOCKED,
                    baseline["usb_id"],
                    [*refs, execution_ref, outcome_ref],
                )
                guard()

    def _result(self, action_id, *, export_receipt=None):
        inspection, review, execution, observation = self._summaries()
        if action_id in PHASE_ACTIONS:
            execution = self._trial.execution_summary()
            observation = _observation(self._trial.execution())
        if action_id in RECONNECT_ACTIONS:
            evidence = (
                self._reconnect.execution() if action_id == RECONNECT_COLLECT else None
            )
            execution = None if evidence is None else evidence.safe_summary()
            observation = _observation(evidence)
        if action_id in REBOOT_ACTIONS:
            evidence = self._reboot.execution() if action_id == REBOOT_COLLECT else None
            execution = None if evidence is None else evidence.safe_summary()
            observation = _observation(evidence)
        coverage, opens = "NO_DEVICE_IO", 0
        if (
            action_id == COLLECT
            or (action_id == PHASE_COLLECT and self._trial.query_attempted)
            or action_id == RECONNECT_COLLECT
            or action_id == REBOOT_COLLECT
        ):
            coverage = (
                "NOT_REPORTED" if execution is None else execution["counter_coverage"]
            )
            opens = (
                None
                if execution is None or execution["actual_counts"] is None
                else execution["actual_counts"]["hub_open_attempts"]
            )
        report = dict(
            original_context=self._context(),
            usb_id=(self._baseline or self._attempt or {}).get("usb_id"),
            inspection=inspection,
            review=review,
            execution=execution,
            observation=observation,
            metadata_export=export_receipt,
            pending_completion_log=True,
            meaning=MEANING,
            **FLAGS,
        )
        if action_id in COMPLETE_ACTIONS:
            from .physical_usb_complete_service import MEANING as COMPLETE_MEANING

            # Build this result only after withdrawing all current phase
            # details. Historical query summaries are not effects of a new
            # file-only action; they remain in the original diagnostic export.
            self._publication = dict(status="PENDING", operation_id=None)
            report.update(
                qualification=self.qualification_view(),
                meaning=COMPLETE_MEANING,
                usb_query_attempted=False,
                inspection=None,
                review=None,
                execution=None,
                observation=None,
            )
        if action_id == DECLARE or action_id in PHASE_ACTIONS:
            report["qualification"] = self.qualification_view()
            if action_id in PHASE_ACTIONS:
                from .physical_usb_trial_service import MEANING as PHASE_MEANING

                report["meaning"] = PHASE_MEANING
            else:
                report["meaning"] = QUALIFICATION_MEANING
        if action_id == PHASE_COLLECT:
            report["usb_query_attempted"] = self._trial.query_attempted
            report["host_boot"] = self._trial.boot_summary()
        if action_id in RECONNECT_ACTIONS:
            from .physical_usb_reconnect_service import MEANING as RECONNECT_MEANING

            report.update(
                qualification=self.qualification_view(),
                meaning=RECONNECT_MEANING,
                host_boot=self._reconnect.boot_summary(),
                usb_query_attempted=action_id == RECONNECT_COLLECT
                and self._reconnect.query_attempted,
            )
        if action_id in REBOOT_ACTIONS:
            from .physical_usb_reboot_service import MEANING as REBOOT_MEANING

            report.update(
                qualification=self.qualification_view(),
                meaning=REBOOT_MEANING,
                host_boot=self._reboot.boot_summary(),
                usb_query_attempted=action_id == REBOOT_COLLECT
                and self._reboot.query_attempted,
            )
        result = dict(
            schema=RESULT_SCHEMA,
            action_id=action_id,
            status="SUCCEEDED",
            steps=[dict(name=action_id, exit_code=0, report=report)],
            device_open_count=opens,
            serial_write_count=0,
            power_event_count=0,
            motion_command_count=0,
            contact_command_count=0,
            counter_coverage=coverage,
            physical_authority=False,
            hardware_qualified=False,
        )
        self._publication = dict(status="PENDING", operation_id=None)
        self._pending_result, self._pending_action = canonical(result), action_id
        return deepcopy(result)

    def _declare(self, values, *, cancellation, progress, deadline):
        """Persist one predeclared trial; never invoke USB, boot or inventory."""
        from .physical_camera_usb_trial_readback import (
            build_original_usb_qualification_plan,
            usb_qualification_event,
            usb_qualification_predecessor_references,
        )

        workflow = self.setup.original_source_workflow()
        assert workflow is not None
        original_session = self.setup.session
        original_binding = canonical(original_session.descriptor())
        trial_id = "usbtrial-" + uuid4().hex
        with self._lock:
            self._declaration_attempted = True
            self._attempt = dict(
                action_id=DECLARE, trial_id=trial_id, records={}, dispatch=None
            )
            self._attempted.add(self._attempt_key(DECLARE, workflow))
            self.invalidate()
            generation = self._generation

        def check():
            self._check(cancellation, deadline)
            _require(
                self._generation == generation
                and self.setup.session is original_session
                and canonical(original_session.descriptor()) == original_binding,
                "USB_TRIAL_CONTEXT_CHANGED",
            )

        mutated = False
        try:
            progress(
                "Saving a predeclared original USB trial only; no phase, boot or device observation is acquired."
            )
            with self.setup.usb_qualification_transaction(
                cancellation=cancellation,
                progress=progress,
                deadline_ns=min(deadline, monotonic_ns() + 120_000_000_000),
            ) as (prerequisites, current):
                _require(
                    canonical(current) == canonical(workflow),
                    "USB_ORIGINAL_WORKFLOW_CHANGED",
                )
                check()
                verification = original_session.view()["verification"]
                with original_session.stage_transaction(
                    expected_challenge_sha256=verification["challenge_sha256"]
                ) as tx:
                    _require(
                        tx.snapshot().head.head_sha256
                        == workflow["session_head_sha256"],
                        "USB_ORIGINAL_HEAD_CHANGED",
                    )
                    refs = usb_qualification_predecessor_references(workflow)
                    metadata = workflow["camera_identity_cycles"][-1]
                    records = [metadata[role] for role in METADATA_ROLES]
                    baseline = workflow.get("usb_baseline")
                    if baseline:
                        records += [baseline[role] for role in USB_ROLE_BYTES]
                    received = workflow["received_camera_cycles"][-1]
                    records += [
                        received[role]
                        for role in ("submission", "assessment", "review")
                    ]
                    self._read_records(tx, records, check)
                    check()
                    mutated = True
                    requested = tx.commit_stage_state(
                        _STAGE,
                        V2StageState.WAITING_OPERATOR,
                        occurred_at_ns=time_ns(),
                        detail_code=usb_qualification_event("REQUESTED", trial_id),
                        expected_head_sha256=tx.snapshot().head.head_sha256,
                        evidence=refs,
                    )
                    with self._lock:
                        self._qualification_trial = dict(
                            trial_id=trial_id,
                            state="INCOMPLETE",
                            request_event=requested.committed_events[-1].to_dict(),
                            declaration_event=None,
                            plan=None,
                        )
                    check()
                    plan = build_original_usb_qualification_plan(
                        prerequisites,
                        workflow,
                        trial_id=trial_id,
                        operator_id=values["operator_id"],
                        launch_session_id=self.launch_id,
                        cable_label=values["cable_label"],
                        port_label=values["port_label"],
                        created_at_utc_ns=time_ns(),
                    )
                    ref = self._retain(tx, plan, "qualification_plan", trial_id)
                    with self._lock:
                        assert self._qualification_trial is not None
                        self._qualification_trial.update(
                            state="PLAN_RETAINED_NOT_COMMITTED",
                            plan=dict(
                                document=plan.to_dict(),
                                evidence_sha256=plan.sha256,
                                reference=ref.to_dict(),
                                retention="M1_FULL_BYTES_READ_BACK",
                            ),
                        )
                    check()
                    declared = tx.commit_stage_state(
                        _STAGE,
                        V2StageState.REVIEW_PENDING,
                        occurred_at_ns=time_ns(),
                        detail_code=usb_qualification_event("DECLARED", trial_id),
                        expected_head_sha256=tx.snapshot().head.head_sha256,
                        evidence=(ref,),
                    )
                    with self._lock:
                        self._qualification_trial.update(
                            state="PLAN_DECLARED",
                            declaration_event=declared.committed_events[-1].to_dict(),
                        )
                    check()
            check()
            with self._lock:
                self._adopt()
                return self._result(DECLARE)
        except BaseException:
            self.invalidate()
            if mutated:
                self.setup.invalidate()
            raise

    def perform(
        self,
        action_id,
        values,
        *,
        expected_context_sha256,
        cancellation,
        progress,
        export_parent=None,
        native_camera=None,
        helper=None,
    ):
        _require(self._operation_lock.acquire(blocking=False), "USB_ACTION_BUSY")
        deadline = (
            monotonic_ns()
            + (
                180
                if action_id
                in {
                    COLLECT,
                    PREPARE,
                    PHASE_COLLECT,
                    "physical_usb_absence_begin",
                    "physical_usb_absence_boot_collect",
                    ABSENCE_COLLECT,
                    RECONNECT_PREPARE,
                    RECONNECT_BOOT_COLLECT,
                    RECONNECT_COLLECT,
                    REBOOT_PREPARE,
                    REBOOT_BOOT_COLLECT,
                    REBOOT_COLLECT,
                    *COMPLETE_ACTIONS,
                }
                else 120
            )
            * 1_000_000_000
        )
        mutated = False
        try:
            reason = self.blocked_reason(
                action_id, native_camera=native_camera, helper=helper
            )
            _require(reason is None, "USB_ACTION_BLOCKED", reason or "")
            fields = self.fields(action_id)
            _require(
                type(values) is dict
                and set(values) == {field["name"] for field in fields},
                "USB_ACTION_FIELDS_INVALID",
            )
            for field in fields:
                if field["type"] == "checkbox":
                    _require(
                        values[field["name"]] is True,
                        "USB_EXPLICIT_ACKNOWLEDGEMENT_REQUIRED",
                    )
                elif action_id == DECLARE and field["name"] in {
                    "cable_label",
                    "port_label",
                }:
                    _plan_label(values[field["name"]])
                else:
                    _actor(values[field["name"]])
            if action_id == EXPORT:
                self._check(cancellation, deadline, source=False)
                from .physical_usb_identity_export import (
                    export_usb_identity_diagnostics,
                )

                self._export_publication = deepcopy(
                    (
                        self.qualification_view()
                        if self._qualification_trial is not None
                        else self.view()
                    )["publication"]
                )
                receipt = export_usb_identity_diagnostics(
                    self.retained_diagnostics(),
                    export_parent=export_parent,
                    source_sha256=self.source_sha256,
                    launch_id=self.launch_id,
                    cancellation=cancellation,
                    deadline_ns=deadline,
                )
                self._export_receipt = deepcopy(receipt)
                return self._result(action_id, export_receipt=receipt)
            _require(
                self.context_sha256(native_camera=native_camera, helper=helper)
                == expected_context_sha256,
                "USB_CONTEXT_CHANGED",
            )
            self._check(cancellation, deadline)
            if action_id in COMPLETE_ACTIONS:
                return self._complete.perform(
                    action_id,
                    values,
                    cancellation=cancellation,
                    progress=progress,
                    deadline=deadline,
                )
            if action_id in REBOOT_ACTIONS:
                return self._reboot.perform(
                    action_id,
                    values,
                    cancellation=cancellation,
                    progress=progress,
                    deadline=deadline,
                    native_camera=native_camera,
                    helper=helper,
                )
            if action_id in RECONNECT_ACTIONS:
                return self._reconnect.perform(
                    action_id,
                    values,
                    cancellation=cancellation,
                    progress=progress,
                    deadline=deadline,
                    native_camera=native_camera,
                    helper=helper,
                )
            if action_id in ABSENCE_ACTIONS:
                return self._absence.perform(
                    action_id,
                    values,
                    cancellation=cancellation,
                    progress=progress,
                    deadline=deadline,
                )
            if action_id == DECLARE:
                return self._declare(
                    values,
                    cancellation=cancellation,
                    progress=progress,
                    deadline=deadline,
                )
            if action_id in PHASE_ACTIONS:
                return self._trial.perform(
                    action_id,
                    values,
                    cancellation=cancellation,
                    progress=progress,
                    deadline=deadline,
                    native_camera=native_camera,
                    helper=helper,
                )
            workflow = self.setup.original_source_workflow()
            prerequisites = self.setup.current_prerequisite_artifact()
            assert workflow is not None
            original_session = self.setup.session
            original_binding = canonical(original_session.descriptor())
            metadata = workflow["camera_identity_cycles"][-1]
            baseline = workflow.get("usb_baseline")
            usb_id = (
                "usbidentity-" + uuid4().hex if baseline is None else baseline["usb_id"]
            )
            policy_review = runtime_review = None
            if action_id == REVIEW:
                inspection = UsbBaselineInspection(
                    canonical(baseline["inspection"]["document"])
                )
                data = inspection.to_dict()
                operation = UsbIdentityOperation(canonical(data["operation"]))
                runtime_registration = UsbIdentityRuntimeRegistration(
                    canonical(data["operation"]["runtime"])
                )
                sd = PhysicalCameraSelection(
                    canonical(data["operation"]["selection"])
                ).identity_document
                reviewer = values["reviewer_id"]
                policy_review = UsbIdentityPolicyReview(
                    canonical(
                        dict(
                            schema="rocell.usb_identity_stage_policy_review.v1",
                            **{
                                k: data["binding"][k]
                                for k in (
                                    "cell_id",
                                    "session_id",
                                    "source_sha256",
                                    "header_sha256",
                                )
                            },
                            policy=data["policy"],
                            policy_sha256=data["policy_sha256"],
                            operator_id=data["binding"]["operator_id"],
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
                    runtime_registration,
                    selection_sha256=PhysicalCameraSelection(
                        canonical(data["operation"]["selection"])
                    ).sha256,
                    native_identity_sha256=sd["native_identity_sha256"],
                    endpoint_sha256=sd["endpoint_sha256"],
                    device_instance_id_sha256=digest(
                        sd["metadata_review"]["observed_instance_id"].encode("utf-8")
                    ),
                    operation_sha256=operation.sha256,
                    operator_id=data["binding"]["operator_id"],
                    reviewer_id=reviewer,
                    launch_session_id=self.launch_id,
                    reviewed_at_ns=time_ns(),
                )
            with self._lock:
                self._attempt = dict(
                    action_id=action_id, usb_id=usb_id, records={}, dispatch=None
                )
                self._attempted.add(self._attempt_key(action_id, workflow))
                self.invalidate()
                generation = self._generation

            def guard():
                self._check(cancellation, deadline, source=False)
                _require(
                    self._generation == generation
                    and self.setup.session is original_session
                    and canonical(original_session.descriptor()) == original_binding
                    and self.source_sha256 == workflow["binding"]["source_sha256"],
                    "USB_LIVE_CONTEXT_CHANGED",
                )

            progress(
                "Retaining the original USB query subjects; no capture or arm authority."
            )
            mutated = True
            # Setup owns the shared operation lock; no M1 lease is held during
            # yield, so the dispatcher can acquire its exact independent scope.
            with self.setup.usb_identity_transaction(
                cancellation=cancellation,
                progress=progress,
                deadline_ns=min(deadline, monotonic_ns() + 120_000_000_000),
            ) as (_, current):
                _require(
                    canonical(current) == canonical(workflow),
                    "USB_ORIGINAL_WORKFLOW_CHANGED",
                )
                guard()
                if action_id == COLLECT:
                    runtime = original_session._store._runtime
                    self._collect(
                        workflow, prerequisites, runtime, cancellation, deadline, guard
                    )
                else:
                    verification = original_session.view()["verification"]
                    with original_session.stage_transaction(
                        expected_challenge_sha256=verification["challenge_sha256"]
                    ) as tx:
                        _require(
                            tx.snapshot().head.head_sha256
                            == workflow["session_head_sha256"],
                            "USB_ORIGINAL_HEAD_CHANGED",
                        )
                        refs = self._read_records(
                            tx, [metadata[role] for role in METADATA_ROLES], guard
                        )
                        if action_id == INSPECT:
                            self._commit(
                                tx,
                                "INSPECTION_STARTED",
                                V2StageState.WAITING_OPERATOR,
                                usb_id,
                                refs,
                            )
                            self._check(cancellation, deadline)
                            policy = inspect_usb_identity_stage_policy(self.workspace)
                            selection = _selection(metadata["metadata"])
                            runtime_registration = usb_identity_runtime_candidate(
                                self.workspace, source_sha256=self.source_sha256
                            )
                            operation = usb_identity_operation(
                                cell_id=workflow["binding"]["cell_id"],
                                session_id=workflow["binding"]["session_id"],
                                selection=selection,
                                runtime=runtime_registration,
                                policy=policy,
                            )
                            file_report = inspect_usb_identity_runtime(
                                runtime_registration,
                                cancellation=cancellation,
                                deadline_ns=deadline,
                                progress=progress,
                            )
                            binding = dict(
                                usb_id=usb_id,
                                source_sha256=self.source_sha256,
                                cell_id=workflow["binding"]["cell_id"],
                                session_id=workflow["binding"]["session_id"],
                                header_sha256=workflow["session_header_sha256"],
                                origin_launch_id=workflow["binding"]["launch_id"],
                                collection_launch_id=self.launch_id,
                                operator_id=values["operator_id"],
                                metadata={
                                    role: metadata[role]["evidence_sha256"]
                                    for role in METADATA_ROLES
                                },
                            )
                            inspection = build_usb_baseline_inspection(
                                binding=binding,
                                policy=policy,
                                operation=operation,
                                runtime_report=file_report,
                                collected_at_ns=time_ns(),
                            )
                            self._check(cancellation, deadline)
                            ref = self._retain(tx, inspection, "inspection", usb_id)
                            guard()
                            self._commit(
                                tx,
                                "INSPECTED",
                                V2StageState.REVIEW_PENDING,
                                usb_id,
                                [ref],
                            )
                        else:
                            self._read_records(tx, [baseline["inspection"]], guard)
                            assert (
                                policy_review is not None and runtime_review is not None
                            )
                            policy_ref = self._retain(
                                tx, policy_review, "policy_review", usb_id
                            )
                            guard()
                            runtime_ref = self._retain(
                                tx, runtime_review, "runtime_review", usb_id
                            )
                            identity = self._build_identity(
                                inspection,
                                policy_review,
                                runtime_review,
                                [
                                    _reference(metadata["metadata"]),
                                    policy_ref,
                                    runtime_ref,
                                ],
                            )
                            guard()
                            identity_ref = self._retain(
                                tx, identity, "identity", usb_id
                            )
                            refs = [
                                _reference(baseline["inspection"]),
                                policy_ref,
                                runtime_ref,
                                identity_ref,
                            ]
                            guard()
                            self._commit(
                                tx, "REVIEWED", V2StageState.BLOCKED, usb_id, refs
                            )
                            guard()
                            self._commit(
                                tx,
                                "QUERY_REQUESTED",
                                V2StageState.WAITING_OPERATOR,
                                usb_id,
                                refs,
                            )
                        guard()
            self._check(cancellation, deadline)
            with self._lock:
                self._adopt()
                return self._result(action_id)
        except BaseException:
            if self._dispatch is not None and self._attempt is not None:
                self._attempt["dispatch"] = self._dispatch.retained_diagnostics()
            self.invalidate()
            if mutated:
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
                "USB_EXACT_PUBLICATION_REQUIRED",
            )
            if (
                self._pending_action
                in {COLLECT, PHASE_COLLECT, RECONNECT_COLLECT, REBOOT_COLLECT}
                and self._dispatch_result is not None
            ):
                assert self._dispatch is not None
                self._dispatch.validate_publication(self._dispatch_result)
            if self._pending_action == ABSENCE_COLLECT:
                self._absence.validate_publication()

    def publication_completed(self, operation_id):
        with self._lock:
            if self._publication["status"] != "PENDING" or self._pending_result is None:
                return
            if (
                self._pending_action
                in {COLLECT, PHASE_COLLECT, RECONNECT_COLLECT, REBOOT_COLLECT}
                and self._dispatch_result is not None
            ):
                assert self._dispatch is not None
                self._dispatch.publication_completed(operation_id)
            if self._pending_action == ABSENCE_COLLECT:
                self._absence.publication_completed(operation_id)
            self._publication = (
                (
                    self._export_publication
                    or dict(status="HISTORICAL_HELD", operation_id=None)
                )
                if self._pending_action == EXPORT
                else dict(status="CURRENT", operation_id=operation_id)
            )
            self._pending_action = self._pending_result = None

    def retained_diagnostics(self):
        with self._lock:
            workflow = (
                self.setup.session.retained_source_workflow() or self._workflow or {}
            )
            baseline = workflow.get("usb_baseline") or self._baseline
            trial = workflow.get("usb_qualification_trial") or self._qualification_trial
            if baseline is None and self._attempt is None and trial is None:
                return None
            metadata = workflow.get("camera_identity_cycles", [])
            # Campaign DTOs are trusted typed originals, but dataclasses.asdict
            # keeps str-Enum members and tuples. Project them to exact JSON at
            # this service boundary, preserving the canonical bytes/hashes;
            # the exporter must not accept arbitrary Python objects instead.
            return json.loads(
                canonical(
                    dict(
                        schema=(
                            "rocell.wizard_usb_identity_diagnostics.v7"
                            if self._complete.has_diagnostics()
                            else (
                                "rocell.wizard_usb_identity_diagnostics.v6"
                                if self._reboot.has_diagnostics()
                                else (
                                    "rocell.wizard_usb_identity_diagnostics.v5"
                                    if self._reconnect.has_diagnostics()
                                    else (
                                        "rocell.wizard_usb_identity_diagnostics.v4"
                                        if self._absence.has_diagnostics()
                                        else (
                                            "rocell.wizard_usb_identity_diagnostics.v3"
                                            if self._trial.has_diagnostics()
                                            else (
                                                "rocell.wizard_usb_identity_diagnostics.v2"
                                                if trial is not None
                                                else "rocell.wizard_usb_identity_diagnostics.v1"
                                            )
                                        )
                                    )
                                )
                            )
                        ),
                        source_sha256=self.source_sha256,
                        launch_session_id=self.launch_id,
                        original_context=self._context(),
                        publication=self._publication,
                        stage_states=self._stages,
                        metadata=(
                            None
                            if not metadata
                            else {role: metadata[-1][role] for role in METADATA_ROLES}
                        ),
                        baseline=baseline,
                        inspection_attempt=self._inspection_attempt,
                        attempt=self._attempt,
                        meaning=MEANING,
                        **FLAGS,
                        **({"qualification_trial": trial} if trial is not None else {}),
                        **self._trial.diagnostics(workflow),
                        **self._absence.diagnostics(workflow),
                        **self._reconnect.diagnostics(workflow),
                        **self._reboot.diagnostics(workflow),
                        **self._complete.diagnostics(workflow),
                    )
                )
            )

    def export_metadata(self):
        return deepcopy(self._export_receipt)
