"""Pure original-subject binding for one intended physical-node absence phase.

The builder reconstructs the predeclared BASELINE from its complete original
sources. It never obtains an observation, checks a store, issues a permit, or
turns endpoint absence into physical-node evidence. An original-store owner must
authenticate every supplied reference and the current ordered journal before
using this subject for any separately admitted acquisition.
"""

from dataclasses import dataclass
import re
from typing import Any

from . import physical_camera_usb_qualification as qualification
from .physical_camera_usb_qualification import (
    UsbQualificationPhase,
    UsbQualificationPlan,
)
from .physical_onboarding import EvidenceReference, PhysicalOnboardingStage
from .physical_onboarding_v2 import V2JournalEvent, V2StageState, _parse_event
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    OWNED_SCHEMA,
)
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.providers.windows.usb_presence_protocol import physical_device_filter

SCHEMA = "rocell.usb_presence_phase_binding.v1"
SUMMARY_SCHEMA = "rocell.usb_presence_phase_binding_summary.v1"
MAX_BYTES = 16 * 1024
PHASE = "RECONNECT_ABSENCE"
ROLES = ("native_enrollment", "owned_usb_run", "host_boot")
FLAGS = {
    "physical_authority": False,
    "hardware_qualified": False,
    "native_release_allowed": False,
    "camera_capture_authorized": False,
    "canonical_stage_pass": False,
    "physical_absence_observed": False,
}
MEANING = (
    "Intended physical-node presence acquisition bound to a predeclared original "
    "trial and its complete BASELINE. No absence, mechanical unplug cause, "
    "continuous absence, permit or physical qualification is established. "
    "Original-store authenticity and current ordered admission remain required."
)
_STAGE = PhysicalOnboardingStage.CAMERA_IDENTITY
_TRIAL = re.compile(r"usbtrial-[0-9a-f]{32}\Z")
_TOP = {
    "schema",
    "binding",
    "phase",
    "ordinal",
    "plan",
    "declaration_event",
    "baseline",
    "sources",
    "target",
    "baseline_execution",
    "not_before_utc_ns",
    "meaning",
    *FLAGS,
}
_MANIFEST = {"sha256", "payload_bytes", "reference"}
_TARGET = {
    "physical_usb_instance_id",
    "physical_usb_instance_id_sha256",
    "physical_device_id",
    "selection_sha256",
    "native_identity_sha256",
    "endpoint_sha256",
    "endpoint_instance_id_sha256",
}
_EXECUTION = {
    "attempt_id",
    "permit_sha256",
    "operation_sha256",
    "request_sha256",
    "observation_sha256",
    "selected_identity_sha256",
}


class UsbPresenceBindingError(ValueError):
    """Closed original-subject mismatch, never a provider exception."""


def _need(ok: bool, code: str = "USB_PRESENCE_BINDING_INVALID") -> None:
    if not ok:
        raise UsbPresenceBindingError(code)


def _exact(value: Any, keys: set[str]) -> None:
    _need(type(value) is dict and set(value) == keys, "EXACT_FIELDS_REQUIRED")


def _manifest(value: Any, *, maximum: int) -> EvidenceReference:
    _exact(value, _MANIFEST)
    qualification._sha(value["sha256"])
    qualification._integer(value["payload_bytes"], 1, maximum)
    ref = qualification._reference(value["reference"])
    _need(
        ref.payload_sha256 == value["sha256"]
        and ref.payload_bytes == value["payload_bytes"],
        "ORIGINAL_REFERENCE_MISMATCH",
    )
    return ref


def _subject_manifest(subject: Any, reference: EvidenceReference) -> dict[str, Any]:
    _need(type(reference) is EvidenceReference, "EXACT_REFERENCE_REQUIRED")
    ref = qualification._reference(reference, subject.payload)
    return dict(
        sha256=subject.sha256,
        payload_bytes=len(subject.payload),
        reference=ref.to_dict(),
    )


def _declaration(
    value: Any, binding: dict[str, Any], plan: EvidenceReference
) -> V2JournalEvent:
    event = _parse_event(value)
    _need(
        event.stage is _STAGE
        and event.previous_state is V2StageState.WAITING_OPERATOR
        and event.state is V2StageState.REVIEW_PENDING
        and event.session_id == binding["session_id"]
        and event.session_header_sha256 == binding["header_sha256"]
        and event.sequence > 0
        and event.detail_code
        == "CAMERA_USB_QUALIFICATION_DECLARED_" + binding["trial_id"][9:].upper()
        and event.evidence == (plan,),
        "EXACT_ORIGINAL_DECLARATION_REQUIRED",
    )
    return event


def _document(payload: bytes) -> dict[str, Any]:
    try:
        value = qualification._load(payload, MAX_BYTES)
        _exact(value, _TOP)
        _need(value["schema"] == SCHEMA and value["meaning"] == MEANING)
        _need(all(value[key] is False for key in FLAGS), "ZERO_AUTHORITY_REQUIRED")
        binding = value["binding"]
        qualification._binding(binding)
        _need(bool(_TRIAL.fullmatch(binding["trial_id"])), "EXACT_TRIAL_ID_REQUIRED")
        _need(
            value["phase"] == PHASE
            and type(value["ordinal"]) is int
            and value["ordinal"] == 1
        )
        plan = _manifest(value["plan"], maximum=UsbQualificationPlan.limit)
        baseline = value["baseline"]
        _exact(baseline, _MANIFEST | {"context"})
        baseline_ref = _manifest(
            {key: baseline[key] for key in _MANIFEST},
            maximum=UsbQualificationPhase.limit,
        )
        qualification._context(baseline["context"])
        event = _declaration(value["declaration_event"], binding, plan)
        _need(
            event.occurred_at_ns <= baseline["context"]["started_at_utc_ns"],
            "DECLARATION_PRECEDES_BASELINE_REQUIRED",
        )
        qualification._manifest_check(
            value["sources"], ROLES, qualification.ROLE_LIMITS
        )
        ids = [plan.evidence_id, baseline_ref.evidence_id] + [
            row["reference"]["evidence_id"] for row in value["sources"]
        ]
        _need(len(set(ids)) == len(ids), "DISTINCT_ORIGINAL_ROLES_REQUIRED")
        _need(
            type(value["not_before_utc_ns"]) is int
            and value["not_before_utc_ns"] == baseline["context"]["finished_at_utc_ns"],
            "EXACT_PREDECESSOR_ORDER_REQUIRED",
        )
        target = value["target"]
        _exact(target, _TARGET)
        physical = target["physical_usb_instance_id"]
        _need(
            physical_device_filter(physical) == target["physical_device_id"],
            "PHYSICAL_TARGET_REQUIRED",
        )
        _need(
            digest(physical.encode("ascii"))
            == target["physical_usb_instance_id_sha256"],
            "TARGET_HASH_MISMATCH",
        )
        for key in _TARGET:
            if key.endswith("sha256"):
                qualification._sha(target[key])
        execution = value["baseline_execution"]
        _exact(execution, _EXECUTION)
        qualification._identifier(execution["attempt_id"])
        for key in _EXECUTION - {"attempt_id"}:
            qualification._sha(execution[key])
        return value
    except UsbPresenceBindingError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbPresenceBindingError("INVALID_ORIGINAL_BINDING_FIELDS") from exc


@dataclass(frozen=True, slots=True)
class UsbPresencePhaseBinding:
    payload: bytes

    def __post_init__(self) -> None:
        _document(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _document(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        value = self.to_dict()
        return dict(
            schema=SUMMARY_SCHEMA,
            binding=value["binding"],
            phase=PHASE,
            ordinal=1,
            phase_binding_sha256=self.sha256,
            plan_sha256=value["plan"]["sha256"],
            baseline_sha256=value["baseline"]["sha256"],
            declaration_event_sha256=value["declaration_event"]["event_sha256"],
            target_instance_id_sha256=value["target"][
                "physical_usb_instance_id_sha256"
            ],
            not_before_utc_ns=value["not_before_utc_ns"],
            meaning=MEANING,
            **FLAGS,
        )


def build_usb_presence_phase_binding(
    *,
    plan: UsbQualificationPlan,
    plan_reference: EvidenceReference,
    declaration_event: V2JournalEvent,
    baseline: UsbQualificationPhase,
    baseline_reference: EvidenceReference,
    baseline_sources: dict[str, bytes],
) -> UsbPresencePhaseBinding:
    """Bind independently read originals; no caller-supplied target or verdict."""
    try:
        _need(
            type(plan) is UsbQualificationPlan
            and type(baseline) is UsbQualificationPhase,
            "EXACT_SUBJECT_TYPES_REQUIRED",
        )
        _need(type(declaration_event) is V2JournalEvent, "EXACT_EVENT_REQUIRED")
        plan = UsbQualificationPlan(plan.payload)
        _need(plan.to_dict()["mode"] == "PHYSICAL", "PHYSICAL_PLAN_REQUIRED")
        _need(
            type(baseline_sources) is dict and set(baseline_sources) == set(ROLES),
            "COMPLETE_BASELINE_ORIGINALS_REQUIRED",
        )
        baseline = qualification.verify_usb_qualification_phase(
            baseline,
            plan=plan,
            predecessor=None,
            sources=baseline_sources,
            expected_sha256=baseline.sha256,
        )
        data = baseline.to_dict()
        _need(
            data["phase"] == "BASELINE"
            and data["ordinal"] == 0
            and data["predecessor_sha256"] is None,
            "EXACT_BASELINE_REQUIRED",
        )
        _need(data["status"] == "OBSERVATIONS_RETAINED", "COMPLETE_BASELINE_REQUIRED")
        plan_record = _subject_manifest(plan, plan_reference)
        baseline_record = _subject_manifest(baseline, baseline_reference)
        binding = plan.to_dict()["binding"]
        event = _declaration(declaration_event.to_dict(), binding, plan_reference)
        _need(
            plan.to_dict()["created_at_utc_ns"]
            <= event.occurred_at_ns
            <= data["context"]["started_at_utc_ns"],
            "PREDECLARED_BASELINE_REQUIRED",
        )
        run = OwnedUsbIdentityRunEvidence(baseline_sources["owned_usb_run"])
        owned = run.to_dict()
        effect = run.bounded_effect_summary()
        _need(
            owned["provenance"] == "PHYSICAL_USB_QUERY"
            and data["provenance"]["metadata"] == "WINDOWS_NATIVE_METADATA"
            and run.status == "OBSERVED"
            and run.released
            and effect["current_complete"]
            and effect["process_cleanup_confirmed"]
            and effect["usb_cleanup_confirmed"],
            "PHYSICAL_OWNED_BASELINE_REQUIRED",
        )
        boot = HostBootObservation(baseline_sources["host_boot"]).to_dict()
        _need(
            boot["schema"] == OWNED_SCHEMA
            and boot["origin"] == "WINDOWS_LOCAL_CIM"
            and boot["status"] == "OBSERVED_HOST_BOOT",
            "CURRENT_OWNED_HOST_BOOT_REQUIRED",
        )
        observation = run.observation
        _need(observation is not None, "COMPLETE_OBSERVATION_REQUIRED")
        assert observation is not None
        observed = observation.to_dict()
        _need(
            observed["outcome"] == "OBSERVED"
            and observed["pre_mapping"] == observed["post_mapping"],
            "STABLE_PHYSICAL_MAPPING_REQUIRED",
        )
        physical = observed["pre_mapping"]["physical_usb_instance_id"]
        request = run.preparation.request.to_dict()
        identity = run.preparation.identity.to_dict()
        target = dict(
            physical_usb_instance_id=physical,
            physical_usb_instance_id_sha256=digest(physical.encode("ascii")),
            physical_device_id=physical_device_filter(physical),
            selection_sha256=identity["selection_sha256"],
            native_identity_sha256=request["native_identity_sha256"],
            endpoint_sha256=request["endpoint_sha256"],
            endpoint_instance_id_sha256=request["expected_device_instance_id_sha256"],
        )
        return UsbPresencePhaseBinding(
            canonical(
                dict(
                    schema=SCHEMA,
                    binding=binding,
                    phase=PHASE,
                    ordinal=1,
                    plan=plan_record,
                    declaration_event=event.to_dict(),
                    baseline={**baseline_record, "context": data["context"]},
                    sources=data["records"],
                    target=target,
                    baseline_execution=dict(
                        **{
                            key: request[key]
                            for key in (
                                "attempt_id",
                                "permit_sha256",
                                "operation_sha256",
                                "selected_identity_sha256",
                            )
                        },
                        request_sha256=run.preparation.request.request_sha256,
                        observation_sha256=observation.sha256,
                    ),
                    not_before_utc_ns=data["context"]["finished_at_utc_ns"],
                    meaning=MEANING,
                    **FLAGS,
                )
            )
        )
    except UsbPresenceBindingError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbPresenceBindingError("ORIGINAL_BASELINE_BINDING_MISMATCH") from exc


def verify_usb_presence_phase_binding(
    payload: bytes,
    *,
    expected_sha256: str,
    plan: UsbQualificationPlan,
    plan_reference: EvidenceReference,
    declaration_event: V2JournalEvent,
    baseline: UsbQualificationPhase,
    baseline_reference: EvidenceReference,
    baseline_sources: dict[str, bytes],
) -> UsbPresencePhaseBinding:
    """Reconstruct from independent originals; a self-consistent hash is not enough."""
    result = UsbPresencePhaseBinding(payload)
    original = build_usb_presence_phase_binding(
        plan=plan,
        plan_reference=plan_reference,
        declaration_event=declaration_event,
        baseline=baseline,
        baseline_reference=baseline_reference,
        baseline_sources=baseline_sources,
    )
    _need(
        result.sha256 == expected_sha256 and result.payload == original.payload,
        "ORIGINAL_BINDING_RECONSTRUCTION_MISMATCH",
    )
    return result
