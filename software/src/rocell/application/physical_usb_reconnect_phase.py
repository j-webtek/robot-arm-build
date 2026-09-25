"""Pure reconnect originals, following a verified physical-node absence.

This codec reconstructs observations; it neither authenticates their store nor
invokes an acquisition. In particular, an operator report is not mechanical
proof, and packet shape cannot establish a newly logged metadata acquisition.
The original owner must authenticate the supplied references and exact permit.
"""

from dataclasses import asdict, dataclass
import re
from typing import Any

from . import physical_camera_usb_qualification as qualification
from .cell_commissioning_coordinator import ExactOperationPermit
from .commissioning_usb_identity_persistence import decode_physical_usb_identity_permit
from .physical_usb_identity_campaign import (
    MAX_OPERATION_BYTES,
    PhysicalUsbIdentityCampaign,
    UsbIdentityOperation,
    verify_phase_operation_context,
    verify_usb_identity_campaign_evidence,
)
from .physical_usb_presence_phase import (
    UsbPresenceQualificationPhase,
    verify_usb_presence_qualification_phase,
)
from .physical_usb_trial_boot import _terminal as boot_terminal
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    compare_boot_observations,
)
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.owned_usb_presence_evidence import (
    OwnedUsbPresenceRunEvidence,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest

EVENT_SCHEMA = "rocell.usb_reconnect_operator_event.v1"
PHASE_SCHEMA = "rocell.usb_reconnect_qualification_phase.v1"
EVENT_LIMIT = 8 * 1024
PHASE_LIMIT = 32 * 1024
PHASE = "AFTER_RECONNECT"
ROLES = (
    "operation",
    "operator_event",
    "native_enrollment",
    "owned_usb_run",
    "host_boot",
)
ROLE_LIMITS = dict(
    operation=MAX_OPERATION_BYTES,
    operator_event=EVENT_LIMIT,
    native_enrollment=768 * 1024,
    owned_usb_run=128 * 1024,
    host_boot=32 * 1024,
)
FLAGS = dict(
    **qualification.FLAGS,
    metadata_acquisition_freshness_verified=False,
    mechanical_reconnection_verified=False,
)
MEANING = (
    "Operator-reported reconnect followed by exact retained USB/boot observations. "
    "Not proof of mechanical cause, fresh metadata acquisition or completed "
    "four-phase qualification. No capture, arm, motion or contact authority."
)
COMPARISON_FIELDS = tuple(sorted(qualification._VALUE_FIELDS - {"boot_time_utc"}))
CHECKS = (
    "HOST_BOOT_PHYSICAL_OWNED_CLEAN",
    "SAME_HOST_SAME_BOOT_AS_ABSENCE",
    "OPERATOR_REPORT_REVIEW_BOOT_QUERY_ORDER",
    "PHYSICAL_OBSERVATION_ORIGINS",
    "OWNED_RESULT_CURRENT_COMPLETE",
    *qualification.OBSERVATION_CHECK_IDS[1:],
    "RECEIVED_SERIAL_MATCH",
    "GENERIC_VID_PID_MATCH",
    "EXACT_ABSENCE_PHYSICAL_NODE_RETURNED",
    "BASELINE_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY",
)
_EVENT_FIELDS = {
    "schema",
    "binding",
    "plan_sha256",
    "baseline_sha256",
    "predecessor_sha256",
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
    "baseline_sha256",
    "predecessor_sha256",
    "context",
    "records",
    "values",
    "execution",
    "provenance",
    "boot_relation",
    "comparisons",
    "checks",
    "missing_requirements",
    "status",
    "meaning",
    *FLAGS,
}


class UsbReconnectPhaseError(ValueError):
    """Closed reconstruction failure; never includes original diagnostic data."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise UsbReconnectPhaseError(code)


def _phase_id(value: Any) -> None:
    _need(
        type(value) is str
        and re.fullmatch(r"usbphase-[0-9a-f]{32}", value) is not None,
        "EXACT_RECONNECT_PHASE_ID_REQUIRED",
    )


def _load(payload: bytes, *, event: bool) -> dict[str, Any]:
    try:
        d = qualification._load(payload, EVENT_LIMIT if event else PHASE_LIMIT)
        qualification._exact(d, _EVENT_FIELDS if event else _PHASE_FIELDS)
        _need(all(d[key] is False for key in FLAGS), "NO_RECONNECT_AUTHORITY")
        for key in ("plan_sha256", "baseline_sha256", "predecessor_sha256"):
            qualification._sha(d[key])
        if event:
            _need(
                d["schema"] == EVENT_SCHEMA
                and d["event"] == "OPERATOR_REPORTED_CAMERA_USB_RECONNECTED",
                "EXACT_RECONNECT_REPORT_MEANING",
            )
            qualification._binding(d["binding"])
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
            and d["ordinal"] == 2
            and d["meaning"] == MEANING,
            "EXACT_RECONNECT_PHASE_MEANING",
        )
        qualification._context(d["context"])
        _phase_id(d["context"]["operation_id"])
        qualification._manifest_check(d["records"], ROLES, ROLE_LIMITS)
        qualification._exact(d["values"], qualification._VALUE_FIELDS)
        for value in d["values"].values():
            qualification._display_check(value)
        # Reuse the strict historical execution/provenance shape, not a v1 phase.
        qualification._phase_details(dict(d, absence_scope=None), False)
        _need(
            d["boot_relation"]
            in ("HELD", "SAME_HOST_SAME_BOOT", "SAME_HOST_DIFFERENT_BOOT"),
            "EXACT_BOOT_RELATION",
        )
        rows = d["comparisons"]
        _need(
            type(rows) is list and len(rows) == len(COMPARISON_FIELDS),
            "EXACT_RECONNECT_COMPARISONS",
        )
        for field, row in zip(COMPARISON_FIELDS, rows):
            qualification._exact(
                row, {"field", "status", "baseline_sha256", "reconnect_sha256"}
            )
            _need(row["field"] == field, "EXACT_RECONNECT_COMPARISONS")
            for key in ("baseline_sha256", "reconnect_sha256"):
                if row[key] is not None:
                    qualification._sha(row[key])
            before, after = row["baseline_sha256"], row["reconnect_sha256"]
            status = (
                "NOT_OBSERVED"
                if before is None or after is None
                else ("MATCHED" if before == after else "CHANGED")
            )
            _need(
                row["status"] == status and after == d["values"][field]["sha256"],
                "EXACT_DERIVED_COMPARISON",
            )
        qualification._checks(d["checks"])
        _need(
            [row["check_id"] for row in d["checks"]] == list(CHECKS),
            "EXACT_RECONNECT_CHECKS",
        )
        missing = [row["check_id"] for row in d["checks"] if not row["passed"]]
        _need(
            d["missing_requirements"] == missing
            and d["status"]
            == ("HELD" if missing else "RECONNECT_OBSERVATIONS_RETAINED"),
            "EXACT_DERIVED_RECONNECT_STATUS",
        )
        return d
    except UsbReconnectPhaseError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbReconnectPhaseError("INVALID_RECONNECT_FIELDS") from exc


@dataclass(frozen=True, slots=True)
class UsbReconnectOperatorEvent:
    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload, event=True)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, event=True)


@dataclass(frozen=True, slots=True)
class UsbReconnectQualificationPhase:
    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload, event=False)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, event=False)


def verify_usb_reconnect_predecessor(
    *,
    original_baseline: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    absence_sources: dict[str, bytes],
) -> UsbPresenceQualificationPhase:
    """Rebuild physical absence and its independent baseline; never relabel v1."""
    try:
        _need(
            type(absence) is UsbPresenceQualificationPhase,
            "EXACT_PHYSICAL_ABSENCE_REQUIRED",
        )
        checked = verify_usb_presence_qualification_phase(
            absence.payload,
            expected_sha256=absence.sha256,
            original_baseline=original_baseline,
            sources=absence_sources,
        )
        d = checked.to_dict()
        _need(
            d["status"] == "ABSENCE_OBSERVATIONS_RETAINED"
            and d["physical_node_absence_observed"] is True,
            "COMPLETE_PHYSICAL_ABSENCE_REQUIRED",
        )
        return checked
    except UsbReconnectPhaseError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbReconnectPhaseError(
            "RECONNECT_PREDECESSOR_RECONSTRUCTION_MISMATCH"
        ) from exc


def build_usb_reconnect_operator_event(
    *,
    plan: qualification.UsbQualificationPlan,
    absence: UsbPresenceQualificationPhase,
    phase_id: str,
    launch_session_id: str,
    operator_id: str,
    phase_started_at_utc_ns: int,
    reported_at_utc_ns: int,
) -> UsbReconnectOperatorEvent:
    """Retain a literal report. The later phase independently rebuilds absence."""
    _need(
        type(plan) is qualification.UsbQualificationPlan
        and type(absence) is UsbPresenceQualificationPhase,
        "EXACT_RECONNECT_REPORT_SUBJECTS",
    )
    plan = qualification.UsbQualificationPlan(plan.payload)
    previous = UsbPresenceQualificationPhase(absence.payload).to_dict()
    _need(
        previous["plan_sha256"] == plan.sha256
        and previous["status"] == "ABSENCE_OBSERVATIONS_RETAINED"
        and previous["physical_node_absence_observed"] is True
        and type(phase_started_at_utc_ns) is int
        and phase_started_at_utc_ns >= previous["context"]["finished_at_utc_ns"]
        and phase_id != previous["context"]["operation_id"],
        "ORDERED_COMPLETE_ABSENCE_REQUIRED",
    )
    return UsbReconnectOperatorEvent(
        canonical(
            dict(
                schema=EVENT_SCHEMA,
                binding=plan.to_dict()["binding"],
                plan_sha256=plan.sha256,
                baseline_sha256=previous["predecessor_sha256"],
                predecessor_sha256=absence.sha256,
                phase_id=phase_id,
                launch_session_id=launch_session_id,
                operator_id=operator_id,
                phase_started_at_utc_ns=phase_started_at_utc_ns,
                reported_at_utc_ns=reported_at_utc_ns,
                event="OPERATOR_REPORTED_CAMERA_USB_RECONNECTED",
                **FLAGS,
            )
        )
    )


def build_usb_reconnect_qualification_phase(
    *,
    original_baseline: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    absence_sources: dict[str, bytes],
    permit: ExactOperationPermit,
    context: dict[str, Any],
    sources: dict[str, bytes],
    references: dict[str, Any],
) -> UsbReconnectQualificationPhase:
    """Rebuild originals and the independently supplied original campaign permit.

    The owned descriptor receipt retains only a permit hash. The full permit
    must therefore come separately from the original ledger, never be invented
    from that hash. This pure function cannot establish ledger authenticity.
    """
    try:
        previous = verify_usb_reconnect_predecessor(
            original_baseline=original_baseline,
            absence=absence,
            absence_sources=absence_sources,
        )
        old = previous.to_dict()
        plan = qualification.UsbQualificationPlan(original_baseline["plan"].payload)
        baseline = original_baseline["baseline"].to_dict()
        qualification._context(context)
        _phase_id(context["operation_id"])
        _need(
            type(sources) is dict
            and set(sources) == set(ROLES)
            and type(references) is dict
            and set(references) == set(ROLES),
            "EXACT_RECONNECT_ORIGINAL_ROLES",
        )
        records = [
            qualification._manifest(role, sources[role], references[role])
            for role in ROLES
        ]
        qualification._manifest_check(records, ROLES, ROLE_LIMITS)
        _need(
            old["context"]["finished_at_utc_ns"] <= context["started_at_utc_ns"]
            and context["operation_id"]
            not in (
                old["context"]["operation_id"],
                baseline["context"]["operation_id"],
            ),
            "ORDERED_DISTINCT_RECONNECT_PHASE_REQUIRED",
        )
        operation = verify_phase_operation_context(
            UsbIdentityOperation(sources["operation"]),
            plan,
            PHASE,
            context["operation_id"],
            previous.sha256,
        )
        event = UsbReconnectOperatorEvent(sources["operator_event"]).to_dict()
        _need(
            event["binding"] == plan.to_dict()["binding"]
            and event["plan_sha256"] == plan.sha256
            and event["baseline_sha256"] == original_baseline["baseline"].sha256
            and event["predecessor_sha256"] == previous.sha256
            and event["phase_id"] == context["operation_id"]
            and event["launch_session_id"] == context["launch_session_id"]
            and event["operator_id"] == context["operator_id"]
            and event["phase_started_at_utc_ns"] == context["started_at_utc_ns"],
            "RECONNECT_OPERATOR_EVENT_BINDING_MISMATCH",
        )
        _need(
            type(permit) is ExactOperationPermit, "EXACT_ORIGINAL_USB_PERMIT_REQUIRED"
        )
        # Strict domain decoding rejects bool/int aliases and malformed typed DTOs.
        permit = decode_physical_usb_identity_permit(
            qualification._load(canonical(asdict(permit)), 32 * 1024)
        )
        run = OwnedUsbIdentityRunEvidence(sources["owned_usb_run"])
        prepared = run.preparation
        campaign = PhysicalUsbIdentityCampaign(
            operation, identity=prepared.identity, review=prepared.review
        )
        run = verify_usb_identity_campaign_evidence(
            run,
            campaign=campaign,
            permit=permit,
            expected_evidence_sha256=digest(sources["owned_usb_run"]),
        )
        request, review = prepared.request.to_dict(), prepared.review.to_dict()
        _need(
            review["launch_session_id"] == context["launch_session_id"]
            and review["operator_id"] == context["operator_id"],
            "RECONNECT_REVIEW_CONTEXT_MISMATCH",
        )
        absence_run = OwnedUsbPresenceRunEvidence(absence_sources["owned_presence_run"])
        absence_request = absence_run.preparation.request.to_dict()
        for key in ("attempt_id", "permit_sha256", "operation_sha256"):
            _need(
                request[key] not in (baseline["execution"][key], absence_request[key]),
                "NO_REPLAY_OR_REUSED_ADMISSION",
            )
        boot, boot_data, boot_values = qualification._boot(
            plan, PHASE, context, sources["host_boot"]
        )
        absence_boot = HostBootObservation(absence_sources["host_boot"])
        relation = compare_boot_observations(absence_boot, boot)["status"]
        values, observed_checks, execution, provenance = (
            qualification._observed_usb_fields(
                plan, context, sources, boot_origin=boot_data["origin"]
            )
        )
        values.update(boot_values)
        d, effect = run.to_dict(), run.bounded_effect_summary()
        # For this descriptor lane the independent scope review precedes the
        # fresh boot observation; the literal report precedes both acquisitions.
        ordered = (
            context["started_at_utc_ns"]
            <= event["reported_at_utc_ns"]
            <= review["reviewed_at_ns"]
            <= boot_data["execution"]["started_utc_ns"]
            <= boot_data["execution"]["finished_utc_ns"]
            <= d["started_utc_ns"]
            <= d["finished_utc_ns"]
            <= context["finished_at_utc_ns"]
        )
        checks = [
            dict(check_id=key, passed=bool(passed))
            for key, passed in zip(
                CHECKS[:5],
                (
                    boot_terminal(boot) == "BOOT_RETAINED",
                    relation == "SAME_HOST_SAME_BOOT",
                    ordered,
                    provenance["usb"] == "PHYSICAL_USB_QUERY"
                    and provenance["metadata"] == "WINDOWS_NATIVE_METADATA"
                    and provenance["boot"] == "WINDOWS_LOCAL_CIM",
                    effect["current_complete"] and effect["released"],
                ),
            )
        ]
        checks.extend(observed_checks)
        displayed = {
            key: qualification._display(value) for key, value in values.items()
        }
        comparisons = []
        for field in COMPARISON_FIELDS:
            before, after = (
                baseline["values"][field]["sha256"],
                displayed[field]["sha256"],
            )
            comparisons.append(
                dict(
                    field=field,
                    baseline_sha256=before,
                    reconnect_sha256=after,
                    status=(
                        "NOT_OBSERVED"
                        if before is None or after is None
                        else ("MATCHED" if before == after else "CHANGED")
                    ),
                )
            )
        serial_hash = digest(canonical(plan.to_dict()["received_label"]["serial"]))
        passes = (
            displayed["descriptor_serial"]["sha256"]
            == serial_hash
            == displayed["generic_serial"]["sha256"],
            all(
                displayed[key]["sha256"] is not None
                and displayed[key]["sha256"] == displayed["generic_" + key]["sha256"]
                for key in ("vid", "pid")
            ),
            values["physical_usb_instance"]
            == old["target"]["physical_usb_instance_id"],
            all(row["status"] == "MATCHED" for row in comparisons),
        )
        checks.extend(
            dict(check_id=key, passed=bool(passed))
            for key, passed in zip(CHECKS[-4:], passes)
        )
        missing = [row["check_id"] for row in checks if not row["passed"]]
        return UsbReconnectQualificationPhase(
            canonical(
                dict(
                    schema=PHASE_SCHEMA,
                    phase=PHASE,
                    ordinal=2,
                    plan_sha256=plan.sha256,
                    baseline_sha256=original_baseline["baseline"].sha256,
                    predecessor_sha256=previous.sha256,
                    context=context,
                    records=records,
                    values=displayed,
                    execution=execution,
                    provenance=provenance,
                    boot_relation=relation,
                    comparisons=comparisons,
                    checks=checks,
                    missing_requirements=missing,
                    status="HELD" if missing else "RECONNECT_OBSERVATIONS_RETAINED",
                    meaning=MEANING,
                    **FLAGS,
                )
            )
        )
    except UsbReconnectPhaseError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbReconnectPhaseError(
            "RECONNECT_ORIGINAL_RECONSTRUCTION_MISMATCH"
        ) from exc


def verify_usb_reconnect_qualification_phase(
    payload: bytes,
    *,
    expected_sha256: str,
    original_baseline: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    absence_sources: dict[str, bytes],
    permit: ExactOperationPermit,
    sources: dict[str, bytes],
) -> UsbReconnectQualificationPhase:
    """A consistent self-hash cannot replace full independent original inputs."""
    _need(
        type(expected_sha256) is str
        and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
        "EXACT_EXPECTED_RECONNECT_HASH_REQUIRED",
    )
    current = UsbReconnectQualificationPhase(payload)
    d = current.to_dict()
    rebuilt = build_usb_reconnect_qualification_phase(
        original_baseline=original_baseline,
        absence=absence,
        absence_sources=absence_sources,
        permit=permit,
        context=d["context"],
        sources=sources,
        references={row["role"]: row["reference"] for row in d["records"]},
    )
    _need(
        current.sha256 == expected_sha256 and current.payload == rebuilt.payload,
        "RECONNECT_PHASE_RECONSTRUCTION_MISMATCH",
    )
    return current
