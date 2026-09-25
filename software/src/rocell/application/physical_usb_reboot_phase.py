"""Pure AFTER_REBOOT originals; never an acquisition permission.

Full independent received, baseline, physical absence and reconnect originals
are reconstructed before the new observation is interpreted. References and
permits remain caller-authenticated original-store inputs, not proof of storage
authenticity supplied by this codec. A literal restart report is not reboot
proof, and native packet shape cannot prove fresh metadata acquisition.

Across boots only UTC and the provider's boot epoch are compared. Every owned
execution retains its own unchanged monotonic/deadline validation. Structurally
out-of-phase executions are rejected by the existing helpers; validly framed
but inconsistent observations produce HELD. The later original owner must
retain failure source bytes even when no valid phase can be constructed.
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
    PHASE_LIMIT as ABSENCE_LIMIT,
    UsbPresenceQualificationPhase,
)
from .physical_usb_reconnect_phase import (
    PHASE_LIMIT as RECONNECT_LIMIT,
    UsbReconnectQualificationPhase,
    verify_usb_reconnect_qualification_phase,
)
from .physical_usb_trial_boot import _terminal as boot_terminal
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    _utc_ns,
    compare_boot_observations,
)
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.owned_usb_presence_evidence import (
    OwnedUsbPresenceRunEvidence,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest

EVENT_SCHEMA = "rocell.usb_reboot_operator_event.v1"
PHASE_SCHEMA = "rocell.usb_reboot_qualification_phase.v1"
EVENT_LIMIT = 8 * 1024
PHASE_LIMIT = 32 * 1024
SUMMARY_LIMIT = 16 * 1024
PHASE = "AFTER_REBOOT"
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
PREDECESSOR_ROLES = ("absence", "reconnect")
PREDECESSOR_LIMITS = dict(absence=ABSENCE_LIMIT, reconnect=RECONNECT_LIMIT)
FLAGS = dict(
    **qualification.FLAGS,
    metadata_acquisition_freshness_verified=False,
    host_restart_verified=False,
    cryptographic_attestation=False,
)
MEANING = (
    "Operator-reported restart followed by exact retained USB/boot observations. "
    "Provider-reported boot identity is not cryptographic or causal reboot proof. "
    "No fresh metadata acquisition or completed four-phase qualification is "
    "certified here. No capture, arm, motion or contact authority."
)
COMPARISON_FIELDS = tuple(sorted(qualification._VALUE_FIELDS - {"boot_time_utc"}))
CHECKS = (
    "HOST_BOOT_PHYSICAL_OWNED_CLEAN",
    "SAME_HOST_DIFFERENT_BOOT_AS_RECONNECT",
    "REBOOT_EPOCH_AFTER_RECONNECT_BEFORE_BEGIN",
    "OPERATOR_REPORT_REVIEW_BOOT_QUERY_ORDER",
    "PHYSICAL_OBSERVATION_ORIGINS",
    "OWNED_RESULT_CURRENT_COMPLETE",
    *qualification.OBSERVATION_CHECK_IDS[1:],
    "RECEIVED_SERIAL_MATCH",
    "GENERIC_VID_PID_MATCH",
    "EXACT_ABSENCE_PHYSICAL_NODE_RETURNED",
    "BASELINE_AND_RECONNECT_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY",
)
_HASH_FIELDS = (
    "plan_sha256",
    "baseline_sha256",
    "absence_sha256",
    "predecessor_sha256",
)
_EVENT_FIELDS = {
    "schema",
    "binding",
    *_HASH_FIELDS,
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
    *_HASH_FIELDS,
    "context",
    "predecessor_records",
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
_BASELINE_INPUTS = {
    "plan",
    "plan_reference",
    "declaration_event",
    "baseline",
    "baseline_reference",
    "baseline_sources",
}


class UsbRebootPhaseError(ValueError):
    """Closed reconstruction error, without arbitrary original data in messages."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise UsbRebootPhaseError(code)


def _phase_id(value: Any) -> None:
    _need(
        type(value) is str
        and re.fullmatch(r"usbphase-[0-9a-f]{32}", value) is not None,
        "EXACT_REBOOT_PHASE_ID_REQUIRED",
    )


def _comparison_status(*hashes: str | None) -> str:
    if any(value is None for value in hashes):
        return "NOT_OBSERVED"
    return "MATCHED" if len(set(hashes)) == 1 else "CHANGED"


def _load(payload: bytes, *, event: bool) -> dict[str, Any]:
    try:
        d = qualification._load(payload, EVENT_LIMIT if event else PHASE_LIMIT)
        qualification._exact(d, _EVENT_FIELDS if event else _PHASE_FIELDS)
        _need(all(d[key] is False for key in FLAGS), "NO_REBOOT_AUTHORITY")
        for key in _HASH_FIELDS:
            qualification._sha(d[key])
        if event:
            _need(
                d["schema"] == EVENT_SCHEMA
                and d["event"] == "OPERATOR_REPORTED_HOST_RESTARTED",
                "EXACT_REBOOT_REPORT_MEANING",
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
            and d["ordinal"] == 3
            and d["meaning"] == MEANING,
            "EXACT_REBOOT_PHASE_MEANING",
        )
        qualification._context(d["context"])
        _phase_id(d["context"]["operation_id"])
        qualification._manifest_check(
            d["predecessor_records"], PREDECESSOR_ROLES, PREDECESSOR_LIMITS
        )
        _need(
            d["predecessor_records"][0]["sha256"] == d["absence_sha256"]
            and d["predecessor_records"][1]["sha256"] == d["predecessor_sha256"],
            "EXACT_REBOOT_PREDECESSOR_MANIFESTS",
        )
        qualification._manifest_check(d["records"], ROLES, ROLE_LIMITS)
        ids = [
            row["reference"]["evidence_id"]
            for row in d["predecessor_records"] + d["records"]
        ]
        _need(len(ids) == len(set(ids)), "DISTINCT_REBOOT_ORIGINAL_ROLES_REQUIRED")
        qualification._exact(d["values"], qualification._VALUE_FIELDS)
        for value in d["values"].values():
            qualification._display_check(value)
        # This is an unchanged strict field validator, not a fabricated v1 phase.
        qualification._phase_details(dict(d, absence_scope=None), False)
        _need(
            d["boot_relation"]
            in ("HELD", "SAME_HOST_SAME_BOOT", "SAME_HOST_DIFFERENT_BOOT"),
            "EXACT_BOOT_RELATION",
        )
        rows = d["comparisons"]
        _need(
            type(rows) is list and len(rows) == len(COMPARISON_FIELDS),
            "EXACT_REBOOT_COMPARISONS",
        )
        for field, row in zip(COMPARISON_FIELDS, rows):
            qualification._exact(
                row,
                {
                    "field",
                    "status",
                    "baseline_sha256",
                    "reconnect_sha256",
                    "reboot_sha256",
                },
            )
            _need(row["field"] == field, "EXACT_REBOOT_COMPARISONS")
            hashes = tuple(
                row[key]
                for key in ("baseline_sha256", "reconnect_sha256", "reboot_sha256")
            )
            for value in hashes:
                if value is not None:
                    qualification._sha(value)
            _need(
                row["status"] == _comparison_status(*hashes)
                and row["reboot_sha256"] == d["values"][field]["sha256"],
                "EXACT_DERIVED_REBOOT_COMPARISON",
            )
        qualification._checks(d["checks"])
        _need(
            [row["check_id"] for row in d["checks"]] == list(CHECKS),
            "EXACT_REBOOT_CHECKS",
        )
        missing = [row["check_id"] for row in d["checks"] if not row["passed"]]
        _need(
            d["missing_requirements"] == missing
            and d["status"] == ("HELD" if missing else "REBOOT_OBSERVATIONS_RETAINED"),
            "EXACT_DERIVED_REBOOT_STATUS",
        )
        return d
    except UsbRebootPhaseError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbRebootPhaseError("INVALID_REBOOT_FIELDS") from exc


@dataclass(frozen=True, slots=True)
class UsbRebootOperatorEvent:
    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload, event=True)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, event=True)

    def safe_summary(self) -> dict[str, Any]:
        d = self.to_dict()
        summary = dict(
            schema="rocell.usb_reboot_operator_summary.v1",
            event_sha256=self.sha256,
            event=d["event"],
            phase_id=d["phase_id"],
            launch_session_id=d["launch_session_id"],
            operator_id=d["operator_id"],
            phase_started_at_utc_ns=d["phase_started_at_utc_ns"],
            reported_at_utc_ns=d["reported_at_utc_ns"],
            **{key: d[key] for key in _HASH_FIELDS},
            **FLAGS,
        )
        _need(len(canonical(summary)) <= EVENT_LIMIT, "REBOOT_SUMMARY_LIMIT")
        return summary


@dataclass(frozen=True, slots=True)
class UsbRebootQualificationPhase:
    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload, event=False)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, event=False)

    def safe_summary(self) -> dict[str, Any]:
        d = self.to_dict()
        summary = dict(
            schema="rocell.usb_reboot_qualification_summary.v1",
            phase_sha256=self.sha256,
            phase=PHASE,
            ordinal=3,
            **{
                key: d[key]
                for key in (
                    *_HASH_FIELDS,
                    "context",
                    "values",
                    "execution",
                    "provenance",
                    "boot_relation",
                    "checks",
                    "missing_requirements",
                    "status",
                    "meaning",
                )
            },
            original_sha256={row["role"]: row["sha256"] for row in d["records"]},
            **FLAGS,
        )
        _need(len(canonical(summary)) <= SUMMARY_LIMIT, "REBOOT_SUMMARY_LIMIT")
        return summary


def _predecessor_records(
    absence: UsbPresenceQualificationPhase,
    absence_reference: Any,
    reconnect: UsbReconnectQualificationPhase,
    reconnect_reference: Any,
) -> list[dict[str, Any]]:
    records = [
        qualification._manifest("absence", absence.payload, absence_reference),
        qualification._manifest("reconnect", reconnect.payload, reconnect_reference),
    ]
    qualification._manifest_check(records, PREDECESSOR_ROLES, PREDECESSOR_LIMITS)
    return records


def _historical_ids(
    original_baseline: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    reconnect: UsbReconnectQualificationPhase,
) -> set[str]:
    ids = {
        qualification._reference(original_baseline[key]).evidence_id
        for key in ("plan_reference", "baseline_reference")
    }
    for subject in (original_baseline["baseline"], absence, reconnect):
        ids.update(
            row["reference"]["evidence_id"] for row in subject.to_dict()["records"]
        )
    # These are an earlier stage; do not reinterpret them as CAMERA_IDENTITY refs.
    ids.update(
        row["reference"]["evidence_id"]
        for row in original_baseline["plan"].to_dict()["received"]
    )
    return ids


def verify_usb_reboot_predecessor(
    *,
    original_baseline: dict[str, Any],
    received: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    absence_reference: Any,
    absence_sources: dict[str, bytes],
    reconnect: UsbReconnectQualificationPhase,
    reconnect_reference: Any,
    reconnect_sources: dict[str, bytes],
    reconnect_permit: ExactOperationPermit,
) -> UsbReconnectQualificationPhase:
    """Rebuild the full typed prefix; cannot authenticate its original store."""
    try:
        _need(
            type(original_baseline) is dict
            and set(original_baseline) == _BASELINE_INPUTS
            and type(received) is dict
            and set(received) == {"submission", "assessment", "review"},
            "EXACT_REBOOT_PREDECESSOR_INPUTS",
        )
        _need(
            type(original_baseline["plan"]) is qualification.UsbQualificationPlan
            and type(absence) is UsbPresenceQualificationPhase
            and type(reconnect) is UsbReconnectQualificationPhase,
            "EXACT_REBOOT_PREDECESSOR_TYPES",
        )
        plan = original_baseline["plan"]
        qualification.verify_usb_qualification_plan(
            plan,
            expected_sha256=plan.sha256,
            received_submission=received["submission"],
            received_assessment=received["assessment"],
            received_review=received["review"],
        )
        checked = verify_usb_reconnect_qualification_phase(
            reconnect.payload,
            expected_sha256=reconnect.sha256,
            original_baseline=original_baseline,
            absence=absence,
            absence_sources=absence_sources,
            permit=reconnect_permit,
            sources=reconnect_sources,
        )
        d = checked.to_dict()
        _need(
            d["status"] == "RECONNECT_OBSERVATIONS_RETAINED",
            "COMPLETE_PHYSICAL_RECONNECT_REQUIRED",
        )
        records = _predecessor_records(
            absence, absence_reference, checked, reconnect_reference
        )
        used = _historical_ids(original_baseline, absence, checked)
        _need(
            not used.intersection(row["reference"]["evidence_id"] for row in records),
            "DISTINCT_REBOOT_PREDECESSOR_REFERENCES_REQUIRED",
        )
        return checked
    except UsbRebootPhaseError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbRebootPhaseError("REBOOT_PREDECESSOR_RECONSTRUCTION_MISMATCH") from exc


def build_usb_reboot_operator_event(
    *,
    plan: qualification.UsbQualificationPlan,
    reconnect: UsbReconnectQualificationPhase,
    phase_id: str,
    launch_session_id: str,
    operator_id: str,
    phase_started_at_utc_ns: int,
    reported_at_utc_ns: int,
) -> UsbRebootOperatorEvent:
    """Literal report only; the phase later reconstructs full independent history."""
    _need(
        type(plan) is qualification.UsbQualificationPlan
        and type(reconnect) is UsbReconnectQualificationPhase,
        "EXACT_REBOOT_REPORT_SUBJECTS",
    )
    plan = qualification.UsbQualificationPlan(plan.payload)
    previous = UsbReconnectQualificationPhase(reconnect.payload).to_dict()
    _need(
        previous["plan_sha256"] == plan.sha256
        and previous["status"] == "RECONNECT_OBSERVATIONS_RETAINED"
        and type(phase_started_at_utc_ns) is int
        and phase_started_at_utc_ns > previous["context"]["finished_at_utc_ns"]
        and phase_id != previous["context"]["operation_id"],
        "ORDERED_COMPLETE_RECONNECT_REQUIRED",
    )
    _need(
        launch_session_id != previous["context"]["launch_session_id"],
        "NEW_REBOOT_LAUNCH_REQUIRED",
    )
    return UsbRebootOperatorEvent(
        canonical(
            dict(
                schema=EVENT_SCHEMA,
                binding=plan.to_dict()["binding"],
                plan_sha256=plan.sha256,
                baseline_sha256=previous["baseline_sha256"],
                absence_sha256=previous["predecessor_sha256"],
                predecessor_sha256=reconnect.sha256,
                phase_id=phase_id,
                launch_session_id=launch_session_id,
                operator_id=operator_id,
                phase_started_at_utc_ns=phase_started_at_utc_ns,
                reported_at_utc_ns=reported_at_utc_ns,
                event="OPERATOR_REPORTED_HOST_RESTARTED",
                **FLAGS,
            )
        )
    )


def _metadata_ids(payload: bytes) -> tuple[str, str, str]:
    # Each full enrollment has already passed the unchanged native verifier.
    d = qualification._load(payload, ROLE_LIMITS["native_enrollment"])
    return (
        d["generic_review"]["operation_id"],
        d["view"]["inventory_operation_id"],
        d["view"]["identity"]["operation_id"],
    )


def build_usb_reboot_qualification_phase(
    *,
    original_baseline: dict[str, Any],
    received: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    absence_reference: Any,
    absence_sources: dict[str, bytes],
    reconnect: UsbReconnectQualificationPhase,
    reconnect_reference: Any,
    reconnect_sources: dict[str, bytes],
    reconnect_permit: ExactOperationPermit,
    permit: ExactOperationPermit,
    context: dict[str, Any],
    sources: dict[str, bytes],
    references: dict[str, Any],
) -> UsbRebootQualificationPhase:
    """Interpret exact new observations without promoting them into authority.

    Both descriptor permits are independent original inputs. Neither their
    self-hashes nor a successful cached phase authenticate their M1 origin.
    No cross-boot monotonic comparison, acquisition or filesystem read occurs.
    """
    try:
        previous = verify_usb_reboot_predecessor(
            original_baseline=original_baseline,
            received=received,
            absence=absence,
            absence_reference=absence_reference,
            absence_sources=absence_sources,
            reconnect=reconnect,
            reconnect_reference=reconnect_reference,
            reconnect_sources=reconnect_sources,
            reconnect_permit=reconnect_permit,
        )
        plan = qualification.UsbQualificationPlan(original_baseline["plan"].payload)
        baseline = original_baseline["baseline"].to_dict()
        absent, old = absence.to_dict(), previous.to_dict()
        qualification._context(context)
        _phase_id(context["operation_id"])
        prior_contexts = (baseline["context"], absent["context"], old["context"])
        prior_phase_ids = {item["operation_id"] for item in prior_contexts}
        _need(
            context["started_at_utc_ns"] > old["context"]["finished_at_utc_ns"]
            and context["operation_id"] not in prior_phase_ids,
            "ORDERED_DISTINCT_REBOOT_PHASE_REQUIRED",
        )
        _need(
            context["launch_session_id"]
            not in {item["launch_session_id"] for item in prior_contexts},
            "NEW_REBOOT_LAUNCH_REQUIRED",
        )
        _need(
            type(sources) is dict
            and set(sources) == set(ROLES)
            and type(references) is dict
            and set(references) == set(ROLES)
            and all(
                type(sources[role]) is bytes
                and 0 < len(sources[role]) <= ROLE_LIMITS[role]
                for role in ROLES
            ),
            "EXACT_REBOOT_ORIGINAL_ROLES",
        )
        records = [
            qualification._manifest(role, sources[role], references[role])
            for role in ROLES
        ]
        qualification._manifest_check(records, ROLES, ROLE_LIMITS)
        predecessors = _predecessor_records(
            absence, absence_reference, previous, reconnect_reference
        )
        used = _historical_ids(original_baseline, absence, previous)
        used.update(row["reference"]["evidence_id"] for row in predecessors)
        _need(
            not used.intersection(row["reference"]["evidence_id"] for row in records),
            "DISTINCT_REBOOT_ORIGINAL_ROLES_REQUIRED",
        )
        operation = verify_phase_operation_context(
            UsbIdentityOperation(sources["operation"]),
            plan,
            PHASE,
            context["operation_id"],
            previous.sha256,
        )
        event = UsbRebootOperatorEvent(sources["operator_event"]).to_dict()
        _need(
            event["binding"] == plan.to_dict()["binding"]
            and event["plan_sha256"] == plan.sha256
            and event["baseline_sha256"] == original_baseline["baseline"].sha256
            and event["absence_sha256"] == absence.sha256
            and event["predecessor_sha256"] == previous.sha256
            and event["phase_id"] == context["operation_id"]
            and event["launch_session_id"] == context["launch_session_id"]
            and event["operator_id"] == context["operator_id"]
            and event["phase_started_at_utc_ns"] == context["started_at_utc_ns"],
            "REBOOT_OPERATOR_EVENT_BINDING_MISMATCH",
        )
        _need(
            type(permit) is ExactOperationPermit, "EXACT_ORIGINAL_USB_PERMIT_REQUIRED"
        )
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
            "REBOOT_REVIEW_CONTEXT_MISMATCH",
        )
        absence_request = OwnedUsbPresenceRunEvidence(
            absence_sources["owned_presence_run"]
        ).preparation.request.to_dict()
        for key in ("attempt_id", "permit_sha256", "operation_sha256"):
            _need(
                request[key]
                not in (
                    baseline["execution"][key],
                    absence_request[key],
                    old["execution"][key],
                ),
                "NO_REPLAY_OR_REUSED_ADMISSION",
            )
        boot, boot_data, boot_values = qualification._boot(
            plan, PHASE, context, sources["host_boot"]
        )
        relation = compare_boot_observations(
            HostBootObservation(reconnect_sources["host_boot"]), boot
        )["status"]
        values, observed_checks, execution, provenance = (
            qualification._observed_usb_fields(
                plan, context, sources, boot_origin=boot_data["origin"]
            )
        )
        values.update(boot_values)
        new_ids = _metadata_ids(sources["native_enrollment"])
        previous_ids = prior_phase_ids | {context["operation_id"]}
        previous_ids.update(
            _metadata_ids(original_baseline["baseline_sources"]["native_enrollment"])
        )
        previous_ids.update(_metadata_ids(reconnect_sources["native_enrollment"]))
        _need(
            len(set(new_ids)) == 3 and not previous_ids.intersection(new_ids),
            "DISTINCT_REBOOT_METADATA_OPERATIONS_REQUIRED",
        )
        d, effect = run.to_dict(), run.bounded_effect_summary()
        response = boot_data["response"]
        boot_epoch = (
            None if response is None else _utc_ns(response["last_boot_up_time_utc"])
        )
        epoch_ordered = (
            boot_epoch is not None
            and old["context"]["finished_at_utc_ns"]
            < boot_epoch
            <= context["started_at_utc_ns"]
        )
        # UTC only across the restart. Owned codecs validate their own local
        # monotonic intervals; even a much lower post-reboot counter is valid.
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
                CHECKS[:6],
                (
                    boot_terminal(boot) == "BOOT_RETAINED",
                    relation == "SAME_HOST_DIFFERENT_BOOT",
                    epoch_ordered,
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
            hashes = (
                baseline["values"][field]["sha256"],
                old["values"][field]["sha256"],
                displayed[field]["sha256"],
            )
            comparisons.append(
                dict(
                    field=field,
                    baseline_sha256=hashes[0],
                    reconnect_sha256=hashes[1],
                    reboot_sha256=hashes[2],
                    status=_comparison_status(*hashes),
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
            == absent["target"]["physical_usb_instance_id"],
            all(row["status"] == "MATCHED" for row in comparisons),
        )
        checks.extend(
            dict(check_id=key, passed=bool(passed))
            for key, passed in zip(CHECKS[-4:], passes)
        )
        missing = [row["check_id"] for row in checks if not row["passed"]]
        return UsbRebootQualificationPhase(
            canonical(
                dict(
                    schema=PHASE_SCHEMA,
                    phase=PHASE,
                    ordinal=3,
                    plan_sha256=plan.sha256,
                    baseline_sha256=original_baseline["baseline"].sha256,
                    absence_sha256=absence.sha256,
                    predecessor_sha256=previous.sha256,
                    context=context,
                    predecessor_records=predecessors,
                    records=records,
                    values=displayed,
                    execution=execution,
                    provenance=provenance,
                    boot_relation=relation,
                    comparisons=comparisons,
                    checks=checks,
                    missing_requirements=missing,
                    status="HELD" if missing else "REBOOT_OBSERVATIONS_RETAINED",
                    meaning=MEANING,
                    **FLAGS,
                )
            )
        )
    except UsbRebootPhaseError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbRebootPhaseError("REBOOT_ORIGINAL_RECONSTRUCTION_MISMATCH") from exc


def verify_usb_reboot_qualification_phase(
    payload: bytes,
    *,
    expected_sha256: str,
    original_baseline: dict[str, Any],
    received: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    absence_reference: Any,
    absence_sources: dict[str, bytes],
    reconnect: UsbReconnectQualificationPhase,
    reconnect_reference: Any,
    reconnect_sources: dict[str, bytes],
    reconnect_permit: ExactOperationPermit,
    permit: ExactOperationPermit,
    sources: dict[str, bytes],
    references: dict[str, Any],
) -> UsbRebootQualificationPhase:
    """Rebuild against independently supplied refs, original bytes and permits."""
    _need(
        type(expected_sha256) is str
        and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
        "EXACT_EXPECTED_REBOOT_HASH_REQUIRED",
    )
    current = UsbRebootQualificationPhase(payload)
    rebuilt = build_usb_reboot_qualification_phase(
        original_baseline=original_baseline,
        received=received,
        absence=absence,
        absence_reference=absence_reference,
        absence_sources=absence_sources,
        reconnect=reconnect,
        reconnect_reference=reconnect_reference,
        reconnect_sources=reconnect_sources,
        reconnect_permit=reconnect_permit,
        permit=permit,
        context=current.to_dict()["context"],
        sources=sources,
        references=references,
    )
    _need(
        current.sha256 == expected_sha256 and current.payload == rebuilt.payload,
        "REBOOT_PHASE_RECONSTRUCTION_MISMATCH",
    )
    return current
