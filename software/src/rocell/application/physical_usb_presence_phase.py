"""Pure retained physical-node absence, separate from old endpoint-only records.

The operator event records a report, not mechanical truth. A phase is rebuilt
from full independent baseline and acquisition bytes; it does not authenticate
their storage, invoke a provider, issue a permit or advance a stage. The original
service/reader must separately authenticate references and ordered journal events.
"""

from dataclasses import dataclass
import re
from typing import Any

from . import physical_camera_usb_qualification as qualification
from .physical_usb_presence_binding import (
    UsbPresencePhaseBinding,
    verify_usb_presence_phase_binding,
)
from .physical_usb_presence_campaign import (
    MAX_OPERATION_BYTES,
    PhysicalUsbPresenceCampaign,
    UsbPresenceOperation,
    verify_usb_presence_campaign_evidence,
)
from .physical_usb_trial_boot import _terminal as boot_terminal
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    compare_boot_observations,
)
from rocell.providers.windows.owned_usb_presence_evidence import (
    OwnedUsbPresenceRunEvidence,
)
from rocell.providers.windows.usb_presence_protocol import canonical, digest

EVENT_SCHEMA = "rocell.usb_presence_operator_event.v1"
PHASE_SCHEMA = "rocell.usb_presence_qualification_phase.v1"
EVENT_LIMIT = 8 * 1024
PHASE_LIMIT = 16 * 1024
PHASE = "RECONNECT_ABSENCE"
ROLES = ("operation", "operator_event", "owned_presence_run", "host_boot")
ROLE_LIMITS = dict(
    operation=MAX_OPERATION_BYTES,
    operator_event=EVENT_LIMIT,
    owned_presence_run=128 * 1024,
    host_boot=32 * 1024,
)
FLAGS = dict(
    **qualification.FLAGS,
    mechanical_unplug_verified=False,
    continuous_absence_verified=False,
)
MEANING = (
    "An operator-reported unplug and two request-bound physical-node samples. "
    "Not proof of mechanical cause, continuous absence or completed four-phase "
    "qualification. No camera capture, arm, motion or contact authority."
)
CHECKS = (
    "HOST_BOOT_PHYSICAL_OWNED_CLEAN",
    "SAME_HOST_SAME_BOOT_AS_BASELINE",
    "OPERATOR_REPORT_BOOT_REVIEW_QUERY_ORDER",
    "PRESENCE_OBSERVATION_PHYSICAL_ORIGIN",
    "PRESENCE_OWNED_RESULT_COMPLETE",
    "PRESENCE_PROCESS_CLEANUP_CONFIRMED",
    "PRESENCE_NATIVE_CLEANUP_CONFIRMED",
    "EXACT_PHYSICAL_NODE_ABSENT",
)
_EVENT_FIELDS = {
    "schema",
    "binding",
    "phase_binding_sha256",
    "phase_id",
    "launch_session_id",
    "operator_id",
    "phase_started_at_utc_ns",
    "reported_at_utc_ns",
    "event",
    *FLAGS,
}
_PHASE_FIELDS = {
    "schema",
    "phase",
    "ordinal",
    "plan_sha256",
    "predecessor_sha256",
    "phase_binding_sha256",
    "context",
    "records",
    "target",
    "provenance",
    "presence_outcome",
    "boot_relation",
    "checks",
    "missing_requirements",
    "status",
    "physical_node_absence_observed",
    "meaning",
    *FLAGS,
}


class UsbPresencePhaseError(ValueError):
    """Closed mismatch code, without paths or raw native diagnostic content."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise UsbPresencePhaseError(code)


def _phase_id(value: Any) -> None:
    _need(
        type(value) is str
        and re.fullmatch(r"usbphase-[0-9a-f]{32}", value) is not None,
        "EXACT_PRESENCE_PHASE_ID_REQUIRED",
    )


def _load(payload: bytes, *, event: bool) -> dict[str, Any]:
    try:
        d = qualification._load(payload, EVENT_LIMIT if event else PHASE_LIMIT)
        qualification._exact(d, _EVENT_FIELDS if event else _PHASE_FIELDS)
        _need(all(d[key] is False for key in FLAGS), "NO_PRESENCE_PHASE_AUTHORITY")
        if event:
            _need(
                d["schema"] == EVENT_SCHEMA
                and d["event"] == "OPERATOR_REPORTED_CAMERA_USB_UNPLUGGED",
                "EXACT_OPERATOR_REPORT_MEANING",
            )
            qualification._binding(d["binding"])
            qualification._sha(d["phase_binding_sha256"])
            _phase_id(d["phase_id"])
            qualification._identifier(d["launch_session_id"])
            qualification._text(d["operator_id"], 64)
            qualification._integer(d["phase_started_at_utc_ns"], 1)
            qualification._integer(
                d["reported_at_utc_ns"], d["phase_started_at_utc_ns"]
            )
            return d
        _need(
            d["schema"] == PHASE_SCHEMA
            and d["phase"] == PHASE
            and type(d["ordinal"]) is int
            and d["ordinal"] == 1
            and d["meaning"] == MEANING,
            "EXACT_PHYSICAL_ABSENCE_PHASE_MEANING",
        )
        for key in ("plan_sha256", "predecessor_sha256", "phase_binding_sha256"):
            qualification._sha(d[key])
        qualification._context(d["context"])
        _phase_id(d["context"]["operation_id"])
        qualification._manifest_check(d["records"], ROLES, ROLE_LIMITS)
        qualification._exact(
            d["target"], {"physical_usb_instance_id", "physical_device_id"}
        )
        from rocell.providers.windows.usb_presence_protocol import (
            physical_device_filter,
        )

        _need(
            physical_device_filter(d["target"]["physical_usb_instance_id"])
            == d["target"]["physical_device_id"],
            "EXACT_PHYSICAL_TARGET_REQUIRED",
        )
        qualification._exact(d["provenance"], {"presence", "native", "boot"})
        _need(
            d["provenance"]["presence"] == "PHYSICAL_USB_PRESENCE",
            "PHYSICAL_RUN_REQUIRED",
        )
        _need(
            d["provenance"]["native"] in (None, "WINDOWS_CONFIGURATION_MANAGER")
            and d["provenance"]["boot"]
            in (
                "WINDOWS_LOCAL_CIM",
                "INJECTED_CIM_EXECUTOR",
                "INCAPABLE_OWNED_CHILD",
            ),
            "EXACT_PRESENCE_PHASE_PROVENANCE",
        )
        _need(
            d["presence_outcome"] in (None, "PRESENT", "ABSENT", "HELD"),
            "EXACT_PRESENCE_OUTCOME",
        )
        _need(
            d["boot_relation"]
            in ("HELD", "SAME_HOST_SAME_BOOT", "SAME_HOST_DIFFERENT_BOOT"),
            "EXACT_BOOT_RELATION",
        )
        qualification._checks(d["checks"])
        _need(
            [row["check_id"] for row in d["checks"]] == list(CHECKS),
            "EXACT_PHASE_CHECKS",
        )
        missing = [row["check_id"] for row in d["checks"] if not row["passed"]]
        _need(
            d["missing_requirements"] == missing
            and d["status"] == ("HELD" if missing else "ABSENCE_OBSERVATIONS_RETAINED")
            and d["physical_node_absence_observed"] is (not missing),
            "EXACT_DERIVED_PHASE_STATUS",
        )
        return d
    except UsbPresencePhaseError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbPresencePhaseError("INVALID_PRESENCE_PHASE_FIELDS") from exc


@dataclass(frozen=True, slots=True)
class UsbPresenceOperatorEvent:
    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload, event=True)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, event=True)


@dataclass(frozen=True, slots=True)
class UsbPresenceQualificationPhase:
    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload, event=False)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, event=False)


def build_usb_presence_operator_event(
    *,
    phase_binding: UsbPresencePhaseBinding,
    phase_id: str,
    launch_session_id: str,
    operator_id: str,
    phase_started_at_utc_ns: int,
    reported_at_utc_ns: int,
) -> UsbPresenceOperatorEvent:
    """Record the exact report supplied by the operator; never infer unplugging."""
    _need(
        type(phase_binding) is UsbPresencePhaseBinding,
        "EXACT_BASELINE_BINDING_REQUIRED",
    )
    phase_binding = UsbPresencePhaseBinding(phase_binding.payload)
    _need(
        type(phase_started_at_utc_ns) is int
        and phase_started_at_utc_ns >= phase_binding.to_dict()["not_before_utc_ns"],
        "OPERATOR_PHASE_PRECEDES_BASELINE",
    )
    _need(
        phase_id != phase_binding.to_dict()["baseline"]["context"]["operation_id"],
        "DISTINCT_ABSENCE_PHASE_REQUIRED",
    )
    return UsbPresenceOperatorEvent(
        canonical(
            dict(
                schema=EVENT_SCHEMA,
                binding=phase_binding.to_dict()["binding"],
                phase_binding_sha256=phase_binding.sha256,
                phase_id=phase_id,
                launch_session_id=launch_session_id,
                operator_id=operator_id,
                phase_started_at_utc_ns=phase_started_at_utc_ns,
                reported_at_utc_ns=reported_at_utc_ns,
                event="OPERATOR_REPORTED_CAMERA_USB_UNPLUGGED",
                **FLAGS,
            )
        )
    )


def build_usb_presence_qualification_phase(
    *,
    original_baseline: dict[str, Any],
    context: dict[str, Any],
    sources: dict[str, bytes],
    references: dict[str, Any],
) -> UsbPresenceQualificationPhase:
    """Reconstruct full original bytes, not caller-provided outcome booleans.

    ``original_baseline`` is the exact keyword set for
    ``verify_usb_presence_phase_binding`` excluding payload/expected hash.
    Store authenticity and the original boot/review/request journal remain
    the service/readback owner's responsibility; this function is pure.
    """
    try:
        _need(
            type(sources) is dict
            and set(sources) == set(ROLES)
            and type(references) is dict
            and set(references) == set(ROLES),
            "EXACT_PRESENCE_ORIGINAL_ROLES_REQUIRED",
        )
        qualification._context(context)
        records = [
            qualification._manifest(role, sources[role], references[role])
            for role in ROLES
        ]
        qualification._manifest_check(records, ROLES, ROLE_LIMITS)
        operation = UsbPresenceOperation(sources["operation"])
        op = operation.to_dict()
        bound = canonical(op["phase_binding"])
        binding = verify_usb_presence_phase_binding(
            bound,
            expected_sha256=digest(bound),
            **original_baseline,
        )
        b = binding.to_dict()
        event = UsbPresenceOperatorEvent(sources["operator_event"]).to_dict()
        _need(
            event["binding"] == b["binding"]
            and event["phase_binding_sha256"] == binding.sha256
            and event["phase_id"] == context["operation_id"] == op["operation_id"]
            and context["operation_id"] != b["baseline"]["context"]["operation_id"]
            and event["launch_session_id"]
            == context["launch_session_id"]
            == op["launch_session_id"]
            and event["operator_id"] == context["operator_id"]
            and b["not_before_utc_ns"]
            <= context["started_at_utc_ns"]
            == event["phase_started_at_utc_ns"],
            "OPERATOR_EVENT_PHASE_BINDING_MISMATCH",
        )
        run = OwnedUsbPresenceRunEvidence(sources["owned_presence_run"])
        campaign = PhysicalUsbPresenceCampaign(operation, review=run.preparation.review)
        run = verify_usb_presence_campaign_evidence(
            run,
            campaign=campaign,
            permit=run.preparation.permit,
            expected_evidence_sha256=digest(sources["owned_presence_run"]),
        )
        d, effect = run.to_dict(), run.bounded_effect_summary()
        observation = run.observation
        observed = None if observation is None else observation.to_dict()
        boot, boot_data, _ = qualification._boot(
            original_baseline["plan"],
            PHASE,
            context,
            sources["host_boot"],
        )
        baseline_boot = HostBootObservation(
            original_baseline["baseline_sources"]["host_boot"]
        )
        boot_relation = compare_boot_observations(baseline_boot, boot)["status"]
        review = run.preparation.review.to_dict()
        _need(
            review["operator_id"] == event["operator_id"],
            "EXACT_REVIEW_OPERATOR_REQUIRED",
        )
        # Manual report -> fresh boot -> final runtime review -> query. Keeping
        # boot before review preserves M1's adjacent review/query-request rule.
        ordered = (
            context["started_at_utc_ns"]
            <= event["reported_at_utc_ns"]
            <= boot_data["execution"]["started_utc_ns"]
            <= boot_data["execution"]["finished_utc_ns"]
            <= review["reviewed_at_ns"]
            <= d["started_utc_ns"]
            <= d["finished_utc_ns"]
            <= context["finished_at_utc_ns"]
        )
        passed = (
            boot_terminal(boot) == "BOOT_RETAINED",
            boot_relation == "SAME_HOST_SAME_BOOT",
            ordered,
            d["provenance"] == "PHYSICAL_USB_PRESENCE"
            and observed is not None
            and observed["provider"] == "WINDOWS_CONFIGURATION_MANAGER",
            effect["current_complete"] and effect["released"] and observed is not None,
            effect["process_cleanup_confirmed"],
            effect["native_cleanup_confirmed"],
            observed is not None and observed["outcome"] == "ABSENT",
        )
        checks = [
            dict(check_id=key, passed=bool(value)) for key, value in zip(CHECKS, passed)
        ]
        missing = [row["check_id"] for row in checks if not row["passed"]]
        return UsbPresenceQualificationPhase(
            canonical(
                dict(
                    schema=PHASE_SCHEMA,
                    phase=PHASE,
                    ordinal=1,
                    plan_sha256=original_baseline["plan"].sha256,
                    predecessor_sha256=original_baseline["baseline"].sha256,
                    phase_binding_sha256=binding.sha256,
                    context=context,
                    records=records,
                    target={
                        key: b["target"][key]
                        for key in ("physical_usb_instance_id", "physical_device_id")
                    },
                    provenance=dict(
                        presence=d["provenance"],
                        native=None if observed is None else observed["provider"],
                        boot=boot_data["origin"],
                    ),
                    presence_outcome=None if observed is None else observed["outcome"],
                    boot_relation=boot_relation,
                    checks=checks,
                    missing_requirements=missing,
                    status="HELD" if missing else "ABSENCE_OBSERVATIONS_RETAINED",
                    physical_node_absence_observed=not missing,
                    meaning=MEANING,
                    **FLAGS,
                )
            )
        )
    except UsbPresencePhaseError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbPresencePhaseError(
            "PRESENCE_ORIGINAL_RECONSTRUCTION_MISMATCH"
        ) from exc


def verify_usb_presence_qualification_phase(
    payload: bytes,
    *,
    expected_sha256: str,
    original_baseline: dict[str, Any],
    sources: dict[str, bytes],
) -> UsbPresenceQualificationPhase:
    """Rebuild independently supplied evidence; a self-consistent hash is insufficient."""
    _need(
        type(expected_sha256) is str
        and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
        "EXACT_EXPECTED_PHASE_HASH_REQUIRED",
    )
    current = UsbPresenceQualificationPhase(payload)
    document = current.to_dict()
    rebuilt = build_usb_presence_qualification_phase(
        original_baseline=original_baseline,
        context=document["context"],
        sources=sources,
        references={row["role"]: row["reference"] for row in document["records"]},
    )
    _need(
        current.sha256 == expected_sha256 and current.payload == rebuilt.payload,
        "PRESENCE_PHASE_RECONSTRUCTION_MISMATCH",
    )
    return current
