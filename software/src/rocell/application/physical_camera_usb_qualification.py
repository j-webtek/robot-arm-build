"""Pure original-byte USB/boot series; endpoint absence is never USB removal.

All producers are inert. Callers must authenticate the supplied references by
reading the original store; a content-shaped EvidenceReference is not an M1
receipt by itself. Constructors check closed wire syntax. The verify functions
also reconstruct all derived facts from the separately retained original bytes.
No assessment in this version can authorize capture or pass physical removal:
the available inventory observes camera endpoints, not all physical USB nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, ClassVar

from .physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
    _parse_evidence_reference,
)
from .physical_received_camera_submission import (
    ReceivedCameraSubmission,
    verify_received_camera_submission_assessment,
    verify_received_camera_submission_review,
)
from .physical_camera_selection import selection_from_enrollment_snapshot
from .wizard_native_camera_enrollment import verify_native_camera_enrollment_snapshot
from .wizard_native_camera_metadata import validate_native_packet
from .usb_identity_stage_policy import usb_identity_stage_policy
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    PHASES,
    compare_boot_observations,
)
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_identity_protocol import canonical, digest

FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    native_release_allowed=False,
    camera_capture_authorized=False,
    canonical_stage_pass=False,
    measurement_truth_verified=False,
    authenticated_operator_identity=False,
)
MEANING = (
    "Original USB/boot comparison only. Endpoint absence does not prove physical "
    "USB removal; that qualification remains BLOCKED. Capture, installation, "
    "arm commissioning and task acceptance require separate evidence."
)
ROLE_LIMITS = {
    "native_enrollment": 768 * 1024,
    "owned_usb_run": 128 * 1024,
    "host_boot": 32 * 1024,
    "endpoint_inventory": 256 * 1024,
}
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_BINDING = {
    "trial_id",
    "source_sha256",
    "cell_id",
    "session_id",
    "header_sha256",
    "origin_launch_id",
    "prerequisites_sha256",
    "identity_entry_sha256",
    "stage_policy_sha256",
    "stage_catalog_sha256",
    "stage_order_sha256",
}
_CONTEXT = {
    "launch_session_id",
    "operation_id",
    "operator_id",
    "started_at_utc_ns",
    "finished_at_utc_ns",
}
_BASE = {"schema", "meaning", *FLAGS}
_ROLE_FIELDS = {"role", "sha256", "payload_bytes", "reference"}
_VALUE_FIELDS = {
    "descriptor_serial",
    "vid",
    "pid",
    "endpoint",
    "endpoint_instance",
    "physical_usb_instance",
    "host_controller",
    "port_topology",
    "driver_provider",
    "driver_service",
    "driver_version",
    "driver_inf",
    "generic_driver_service",
    "generic_serial",
    "generic_vid",
    "generic_pid",
    "container_id",
    "machine_uuid",
    "boot_time_utc",
}
OBSERVATION_CHECK_IDS = (
    "HOST_BOOT_OBSERVED",
    "REVIEWED_NATIVE_SELECTION",
    "OWNED_USB_RUN_SUCCEEDED",
    "USB_OBSERVATION_COMPLETE",
    "PROCESS_CLEANUP_CONFIRMED",
    "NATIVE_CLEANUP_CONFIRMED",
    "DRIVER_FIELDS_OBSERVED",
    "DRIVER_SERVICE_MATCH",
    "V2_OPERATING_USB3_OBSERVED",
)
ABSENCE_CHECK_IDS = (
    "HOST_BOOT_OBSERVED",
    "ENDPOINT_INVENTORY_COMPLETE",
    "REVIEWED_ENDPOINT_ABSENT",
    "ENDPOINT_INVENTORY_FRESHNESS_REQUIRED",
)


class UsbQualificationError(ValueError):
    pass


def _need(ok, code="USB_QUALIFICATION_INVALID"):
    if not ok:
        raise UsbQualificationError(code)


def _exact(v, keys):
    _need(type(v) is dict and set(v) == set(keys), "EXACT_FIELDS_REQUIRED")


def _sha(v):
    _need(type(v) is str and bool(_HASH.fullmatch(v)), "EXACT_HASH_REQUIRED")


def _text(v, maximum=128):
    _need(
        type(v) is str
        and 0 < len(v.encode("utf-8")) <= maximum
        and v == v.strip()
        and all(ord(c) >= 32 and ord(c) != 127 for c in v),
        "BOUNDED_TEXT_REQUIRED",
    )


def _identifier(v):
    _need(type(v) is str and bool(_ID.fullmatch(v)), "EXACT_IDENTIFIER_REQUIRED")


def _integer(v, low=0, high=2**63 - 1):
    _need(type(v) is int and low <= v <= high, "EXACT_INTEGER_REQUIRED")


def _load(payload, limit):
    _need(type(payload) is bytes, "EXACT_BYTES_REQUIRED")
    try:
        result = decode_owned_json(payload, maximum=limit)
        _need(canonical(result) == payload, "CANONICAL_BYTES_REQUIRED")
        return result
    except (ValueError, TypeError, RecursionError) as exc:
        raise UsbQualificationError("INVALID_OR_OVERSIZED_JSON") from exc


def _reference(v, payload=None, stage=PhysicalOnboardingStage.CAMERA_IDENTITY):
    result = _parse_evidence_reference(
        v.to_dict() if type(v) is EvidenceReference else v
    )
    _need(result.stage is stage, "ORIGINAL_STAGE_MISMATCH")
    if payload is not None:
        _need(
            result.payload_sha256 == digest(payload)
            and result.payload_bytes == len(payload),
            "ORIGINAL_BYTES_REFERENCE_MISMATCH",
        )
    return result


def _manifest(role, payload, reference, stage=PhysicalOnboardingStage.CAMERA_IDENTITY):
    ref = _reference(reference, payload, stage)
    return dict(
        role=role,
        sha256=digest(payload),
        payload_bytes=len(payload),
        reference=ref.to_dict(),
    )


def _manifest_check(
    v, roles, limits=None, stage=PhysicalOnboardingStage.CAMERA_IDENTITY
):
    _need(
        type(v) is list and [r.get("role") for r in v if type(r) is dict] == list(roles)
    )
    ids = []
    for row in v:
        _exact(row, _ROLE_FIELDS)
        _sha(row["sha256"])
        _integer(row["payload_bytes"], 1, (limits or {}).get(row["role"], 1024 * 1024))
        ref = _reference(row["reference"], stage=stage)
        _need(
            ref.payload_sha256 == row["sha256"]
            and ref.payload_bytes == row["payload_bytes"]
        )
        ids.append(ref.evidence_id)
    _need(len(set(ids)) == len(ids), "DISTINCT_ORIGINAL_ROLES_REQUIRED")


def _binding(v):
    _exact(v, _BINDING)
    for key, value in v.items():
        _sha(value) if key.endswith("sha256") else _identifier(value)
    policy = usb_identity_stage_policy()
    p = policy.to_dict()
    _need(
        v["stage_policy_sha256"] == policy.sha256
        and v["stage_catalog_sha256"] == p["base_catalog_sha256"]
        and v["stage_order_sha256"] == p["canonical_stage_order_sha256"],
        "EXACT_POLICY_BINDING_REQUIRED",
    )


def _context(v):
    _exact(v, _CONTEXT)
    for k in ("launch_session_id", "operation_id"):
        _identifier(v[k])
    _text(v["operator_id"], 64)
    _integer(v["started_at_utc_ns"], 1)
    _integer(v["finished_at_utc_ns"], v["started_at_utc_ns"])


def _display(value):
    """Never abbreviate a value in a way that can masquerade as equality."""
    if value is None:
        return dict(status="NOT_OBSERVED", value=None, sha256=None)
    wire = canonical(value)
    return dict(
        status="VALUE_RETAINED" if len(wire) <= 128 else "VALUE_IN_ORIGINAL",
        value=value if len(wire) <= 128 else None,
        sha256=digest(wire),
    )


def _display_check(v):
    _exact(v, {"status", "value", "sha256"})
    _need(v["status"] in {"NOT_OBSERVED", "VALUE_RETAINED", "VALUE_IN_ORIGINAL"})
    if v["status"] == "NOT_OBSERVED":
        _need(v["value"] is None and v["sha256"] is None)
    else:
        _sha(v["sha256"])
        if v["status"] == "VALUE_IN_ORIGINAL":
            _need(v["value"] is None)
        else:
            _need(
                v["value"] is not None
                and len(canonical(v["value"])) <= 128
                and digest(canonical(v["value"])) == v["sha256"]
            )


def _operating_usb3(link):
    # EX.Speed is retained verbatim. Windows can report HighSpeed there while
    # the independent V2 operating flag reports SuperSpeed; capability is not
    # operation, and neither representation supplies an exact Mbps value.
    return (
        link["ex_v2_available"] is True
        and link["operating_superspeed_or_higher"] is True
    )


def _bounded_assessment_values(document):
    """Keep exact hashes and mark omitted values explicitly under a total cap.

    Original role files, not this presentation, retain every complete value.
    Common short values remain readable. This deterministic rule never changes
    a comparison or turns an omitted value into an unobserved field.
    """
    result = _load(canonical(document), 128 * 1024)
    for cap in (128, 64, 0):
        if (
            len(canonical(result)) <= 32 * 1024
            and len(canonical(_summary_document(result))) <= 24 * 1024 - 256
        ):
            return result
        for phase in result["phases"]:
            for value in phase["values"].values():
                if (
                    value["status"] == "VALUE_RETAINED"
                    and len(canonical(value["value"])) > cap
                ):
                    value.update(status="VALUE_IN_ORIGINAL", value=None)
    _need(
        len(canonical(result)) <= 32 * 1024
        and len(canonical(_summary_document(result))) <= 24 * 1024 - 256,
        "SUMMARY_LIMIT",
    )
    return result


def _summary_document(document):
    result = _load(canonical(document), 128 * 1024)
    result.pop("checks")  # all failed requirements are already retained exactly
    for phase in result["phases"]:
        phase["missing_requirements"] = [
            r["check_id"] for r in phase.pop("checks") if not r["passed"]
        ]
    return result


def _checks(v):
    _need(type(v) is list and len(v) <= 64)
    ids = []
    for row in v:
        _exact(row, {"check_id", "passed"})
        _identifier(row["check_id"])
        _need(type(row["passed"]) is bool)
        ids.append(row["check_id"])
    _need(len(ids) == len(set(ids)))


def _phase_details(v, absent):
    provenance = v["provenance"]
    _exact(provenance, {"usb", "metadata", "boot", "metadata_helper_sha256"})
    _sha(provenance["metadata_helper_sha256"])
    _need(provenance["usb"] in {None, "PHYSICAL_USB_QUERY", "INCAPABLE_USB_QUERY"})
    _need(provenance["metadata"] in {"WINDOWS_NATIVE_METADATA", "INCAPABLE_FIXTURE"})
    _need(
        provenance["boot"]
        in {"WINDOWS_LOCAL_CIM", "INJECTED_CIM_EXECUTOR", "INCAPABLE_OWNED_CHILD"}
    )
    _need(v["absence_scope"] == ("CAMERA_ENDPOINTS_ONLY" if absent else None))
    ex = v["execution"]
    _exact(
        ex,
        {
            "attempt_id",
            "permit_sha256",
            "operation_sha256",
            "usb3_operating",
            "ex_speed",
            "ex_v2_available",
            "process_clean",
            "native_clean",
        },
    )
    for k in ("usb3_operating", "ex_v2_available", "process_clean", "native_clean"):
        _need(ex[k] is None or type(ex[k]) is bool)
    if absent:
        _need(all(x is None for x in ex.values()) and provenance["usb"] is None)
    else:
        _need(provenance["usb"] is not None)
        _identifier(ex["attempt_id"])
        for k in ("permit_sha256", "operation_sha256"):
            _sha(ex[k])
        if ex["ex_speed"] is not None:
            _integer(ex["ex_speed"], 0, 3)
        _need(ex["usb3_operating"] is not True or ex["ex_v2_available"] is True)


def _phase_checks(rows, absent):
    _checks(rows)
    _need(
        [row["check_id"] for row in rows]
        == list(ABSENCE_CHECK_IDS if absent else OBSERVATION_CHECK_IDS),
        "EXACT_PHASE_CHECKS_REQUIRED",
    )


def _base(v, role, extra):
    _exact(v, _BASE | set(extra))
    _need(
        v["schema"] == f"rocell.usb_qualification_{role}.v1" and v["meaning"] == MEANING
    )
    _need(all(v[k] is False for k in FLAGS), "NO_AUTHORITY")


def _phase_views(rows):
    _need(type(rows) is list and len(rows) <= 4)
    for ordinal, row in enumerate(rows):
        _exact(
            row,
            {
                "phase",
                "phase_sha256",
                "status",
                "checks",
                "provenance",
                "execution",
                "values",
                "absence_scope",
            },
        )
        _need(row["phase"] == PHASES[ordinal])
        _sha(row["phase_sha256"])
        _phase_checks(row["checks"], ordinal == 1)
        _need(
            row["status"]
            == (
                "OBSERVATIONS_RETAINED"
                if all(c["passed"] for c in row["checks"])
                else "HELD"
            )
        )
        _phase_details(row, ordinal == 1)
        _exact(
            row["values"],
            _VALUE_FIELDS,
        )
        for item in row["values"].values():
            _display_check(item)


def _document(role, **fields):
    return dict(
        schema=f"rocell.usb_qualification_{role}.v1", **fields, **FLAGS, meaning=MEANING
    )


@dataclass(frozen=True, slots=True)
class _Subject:
    payload: bytes
    role: ClassVar[str]
    limit: ClassVar[int]

    def __post_init__(self):
        try:
            _validate(self.role, _load(self.payload, self.limit))
        except UsbQualificationError:
            raise
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            raise UsbQualificationError("INVALID_SUBJECT_FIELDS") from exc

    @property
    def sha256(self):
        return digest(self.payload)

    def to_dict(self):
        return _load(self.payload, self.limit)


@dataclass(frozen=True, slots=True)
class UsbQualificationPlan(_Subject):
    role: ClassVar[str] = "plan"
    limit: ClassVar[int] = 16 * 1024


@dataclass(frozen=True, slots=True)
class UsbQualificationPhase(_Subject):
    role: ClassVar[str] = "phase"
    limit: ClassVar[int] = 16 * 1024


@dataclass(frozen=True, slots=True)
class UsbQualificationSeries(_Subject):
    role: ClassVar[str] = "series"
    limit: ClassVar[int] = 8 * 1024


@dataclass(frozen=True, slots=True)
class UsbQualificationAssessment(_Subject):
    role: ClassVar[str] = "assessment"
    limit: ClassVar[int] = 32 * 1024

    def safe_summary(self):
        value = _summary_document(self.to_dict())
        value["schema"] = "rocell.usb_qualification_summary.v1"
        value["assessment_sha256"] = self.sha256
        _need(len(canonical(value)) <= 24 * 1024, "SUMMARY_LIMIT")
        return value


@dataclass(frozen=True, slots=True)
class UsbQualificationReview(_Subject):
    role: ClassVar[str] = "review"
    limit: ClassVar[int] = 8 * 1024


def _validate(role, v):
    if role == "plan":
        _base(
            v,
            role,
            {
                "binding",
                "mode",
                "operator_id",
                "launch_session_id",
                "created_at_utc_ns",
                "cable_label",
                "port_label",
                "received",
                "received_label",
                "phases",
            },
        )
        _binding(v["binding"])
        _need(v["mode"] in {"PHYSICAL", "MODELED"} and v["phases"] == list(PHASES))
        _text(v["operator_id"], 64)
        _identifier(v["launch_session_id"])
        _integer(v["created_at_utc_ns"], 1)
        for k in ("cable_label", "port_label"):
            _text(v[k], 128)
        _manifest_check(
            v["received"],
            ("submission", "assessment", "review"),
            stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
        )
        _exact(
            v["received_label"],
            {"manufacturer", "product_id", "serial", "inspection_sha256"},
        )
        for k in ("manufacturer", "product_id", "serial"):
            _text(v["received_label"][k], 256)
        _sha(v["received_label"]["inspection_sha256"])
    elif role == "phase":
        _base(
            v,
            role,
            {
                "plan_sha256",
                "phase",
                "ordinal",
                "predecessor_sha256",
                "context",
                "records",
                "values",
                "checks",
                "status",
                "provenance",
                "execution",
                "absence_scope",
            },
        )
        _sha(v["plan_sha256"])
        _need(v["phase"] in PHASES)
        _integer(v["ordinal"], 0, 3)
        _need(PHASES[v["ordinal"]] == v["phase"])
        if v["ordinal"] == 0:
            _need(v["predecessor_sha256"] is None)
        else:
            _sha(v["predecessor_sha256"])
        _context(v["context"])
        absent = v["phase"] == "RECONNECT_ABSENCE"
        roles = (
            ("endpoint_inventory", "host_boot")
            if absent
            else ("native_enrollment", "owned_usb_run", "host_boot")
        )
        _manifest_check(v["records"], roles, ROLE_LIMITS)
        _exact(v["values"], _VALUE_FIELDS)
        for value in v["values"].values():
            _display_check(value)
        _phase_checks(v["checks"], absent)
        _need(
            v["status"]
            == (
                "OBSERVATIONS_RETAINED"
                if all(x["passed"] for x in v["checks"])
                else "HELD"
            )
        )
        _phase_details(v, absent)
    elif role == "series":
        _base(v, role, {"plan_sha256", "phases"})
        _sha(v["plan_sha256"])
        _need(type(v["phases"]) is list and len(v["phases"]) <= 4)
        _manifest_check(v["phases"], PHASES[: len(v["phases"])])
    elif role == "assessment":
        _base(
            v,
            role,
            {
                "binding",
                "plan_sha256",
                "series_sha256",
                "mode",
                "verdict",
                "checks",
                "missing_requirements",
                "phases",
                "comparisons",
                "received_label",
                "cable_label",
                "port_label",
            },
        )
        _binding(v["binding"])
        for k in ("plan_sha256", "series_sha256"):
            _sha(v[k])
        _need(v["mode"] in {"PHYSICAL", "MODELED"} and v["verdict"] == "BLOCKED")
        _checks(v["checks"])
        expected_checks = [
            "PHYSICAL_PROVENANCE_REQUIRED",
            "ALL_FOUR_PHASES_REQUIRED",
            "PHYSICAL_USB_ABSENCE_REQUIRED",
        ]
        for i, name in enumerate(PHASES[: len(v["phases"])]):
            expected_checks.extend([name + "_COMPLETE", name + "_PHYSICAL_ORIGINS"])
            if i:
                expected_checks.append(name + "_BOOT_RELATION")
            if name != "RECONNECT_ABSENCE":
                expected_checks.extend(
                    [name + "_RECEIVED_SERIAL_MATCH", name + "_GENERIC_VID_PID_MATCH"]
                )
        expected_checks.extend(
            name + "_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY"
            for name in PHASES[: len(v["phases"])]
            if name in {"AFTER_RECONNECT", "AFTER_REBOOT"}
        )
        _need(
            [row["check_id"] for row in v["checks"]] == expected_checks,
            "EXACT_ASSESSMENT_CHECKS_REQUIRED",
        )
        _need(
            v["missing_requirements"]
            == [x["check_id"] for x in v["checks"] if not x["passed"]]
            and "PHYSICAL_USB_ABSENCE_REQUIRED" in v["missing_requirements"]
        )
        _phase_views(v["phases"])
        _need(
            type(v["comparisons"]) is list
            and len(v["comparisons"]) <= 2 * len(_VALUE_FIELDS)
        )
        for row in v["comparisons"]:
            _exact(
                row,
                {"field", "status", "before_phase", "after_phase"},
            )
            _need(
                row["before_phase"] == "BASELINE"
                and row["after_phase"] in {"AFTER_RECONNECT", "AFTER_REBOOT"}
            )
            _need(
                row["field"] in _VALUE_FIELDS
                and row["status"] in {"MATCHED", "CHANGED", "NOT_OBSERVED"}
            )
            phases_by_name = {x["phase"]: x for x in v["phases"]}
            _need(row["after_phase"] in phases_by_name and "BASELINE" in phases_by_name)
            first = phases_by_name["BASELINE"]["values"][row["field"]]["sha256"]
            last = phases_by_name[row["after_phase"]]["values"][row["field"]]["sha256"]
            _need(
                row["status"]
                == (
                    "NOT_OBSERVED"
                    if first is None or last is None
                    else "MATCHED" if first == last else "CHANGED"
                )
            )
        for k in ("cable_label", "port_label"):
            _text(v[k], 128)
        _need(
            [(x["after_phase"], x["field"]) for x in v["comparisons"]]
            == [
                (row["phase"], field)
                for row in v["phases"]
                if row["phase"] in {"AFTER_RECONNECT", "AFTER_REBOOT"}
                for field in sorted(_VALUE_FIELDS - {"boot_time_utc"})
            ],
            "EXACT_COMPARISON_ROSTER_REQUIRED",
        )
        _exact(
            v["received_label"],
            {"manufacturer", "product_id", "serial", "inspection_sha256"},
        )
        for key in ("manufacturer", "product_id", "serial"):
            _text(v["received_label"][key], 256)
        _sha(v["received_label"]["inspection_sha256"])
    elif role == "review":
        _base(
            v,
            role,
            {
                "plan_sha256",
                "series_sha256",
                "assessment_sha256",
                "decision",
                "reviewer_id",
                "review_launch_id",
                "reviewed_at_utc_ns",
                "verdict",
                "distinct_operator_labels",
                "authenticated_independent_people",
            },
        )
        for k in ("plan_sha256", "series_sha256", "assessment_sha256"):
            _sha(v[k])
        _need(
            v["decision"] in {"ACKNOWLEDGE_EXACT", "REJECT"}
            and v["verdict"] == "BLOCKED"
            and v["distinct_operator_labels"] is True
            and v["authenticated_independent_people"] is False
        )
        _text(v["reviewer_id"], 64)
        _identifier(v["review_launch_id"])
        _integer(v["reviewed_at_utc_ns"], 1)


def build_usb_qualification_plan(
    *,
    binding,
    mode,
    operator_id,
    launch_session_id,
    created_at_utc_ns,
    cable_label,
    port_label,
    received_submission,
    received_assessment,
    received_review,
    received_references,
):
    _need(type(received_submission) is ReceivedCameraSubmission)
    received_submission = ReceivedCameraSubmission(
        received_submission.payload, received_submission.prerequisites
    )
    assessment = verify_received_camera_submission_assessment(
        received_assessment,
        submission=received_submission,
        expected_assessment_sha256=received_assessment.sha256,
    )
    review = verify_received_camera_submission_review(
        received_review,
        submission=received_submission,
        assessment=assessment,
        expected_review_sha256=received_review.sha256,
    )
    old = received_submission.to_dict()
    _need(
        assessment.to_dict()["verdict"] == review.to_dict()["verdict"] == "PASS",
        "REVIEWED_RECEIPT_PASS_REQUIRED",
    )
    for k in (
        "source_sha256",
        "session_id",
        "cell_id",
        "header_sha256",
        "origin_launch_id",
        "prerequisites_sha256",
    ):
        _need(binding[k] == old["binding"][k], "ORIGINAL_RECEIPT_CONTEXT_MISMATCH")
    _need(
        created_at_utc_ns >= review.to_dict()["reviewed_at_ns"],
        "PLAN_PRECEDES_ORIGINAL_REVIEW",
    )
    subjects = (received_submission, assessment, review)
    _need(type(received_references) in (tuple, list) and len(received_references) == 3)
    received = [
        _manifest(role, subject.payload, ref, PhysicalOnboardingStage.CAMERA_RECEIPT)
        for role, subject, ref in zip(
            ("submission", "assessment", "review"), subjects, received_references
        )
    ]
    inspection = old["inspection"]
    _need(
        inspection is not None
        and inspection["identity_label_legible"] is True
        and inspection["inspection_uncertain"] is False
    )
    label = dict(
        manufacturer=inspection["observed_manufacturer"],
        product_id=inspection["observed_product_id"],
        serial=inspection["observed_camera_serial"],
        inspection_sha256=old["inspection_sha256"],
    )
    return UsbQualificationPlan(
        canonical(
            _document(
                "plan",
                binding=binding,
                mode=mode,
                operator_id=operator_id,
                launch_session_id=launch_session_id,
                created_at_utc_ns=created_at_utc_ns,
                cable_label=cable_label,
                port_label=port_label,
                received=received,
                received_label=label,
                phases=list(PHASES),
            )
        )
    )


def verify_usb_qualification_plan(
    value, *, expected_sha256, received_submission, received_assessment, received_review
):
    plan = UsbQualificationPlan(
        value.payload if type(value) is UsbQualificationPlan else value
    )
    d = plan.to_dict()
    expected = build_usb_qualification_plan(
        **{
            k: d[k]
            for k in (
                "binding",
                "mode",
                "operator_id",
                "launch_session_id",
                "created_at_utc_ns",
                "cable_label",
                "port_label",
            )
        },
        received_submission=received_submission,
        received_assessment=received_assessment,
        received_review=received_review,
        received_references=[r["reference"] for r in d["received"]],
    )
    _need(
        plan.sha256 == expected_sha256 and plan.payload == expected.payload,
        "PLAN_RECONSTRUCTION_MISMATCH",
    )
    return plan


def _phase_originals(records, sources):
    _need(
        type(sources) is dict and set(sources) == {r["role"] for r in records},
        "EXACT_ORIGINAL_ROLE_SET_REQUIRED",
    )
    for row in records:
        payload = sources[row["role"]]
        _need(type(payload) is bytes and 0 < len(payload) <= ROLE_LIMITS[row["role"]])
        _need(
            row == _manifest(row["role"], payload, row["reference"]),
            "ORIGINAL_ROLE_MISMATCH",
        )


def _boot(plan, phase, context, payload):
    boot = HostBootObservation(payload)
    b, p = boot.to_dict(), plan.to_dict()
    request = b["request"]
    for k, expected in dict(
        source_sha256=p["binding"]["source_sha256"],
        session_id=p["binding"]["session_id"],
        trial_id=p["binding"]["trial_id"],
        phase=phase,
        launch_session_id=context["launch_session_id"],
        operation_id=context["operation_id"],
    ).items():
        _need(request[k] == expected, "HOST_BOOT_PHASE_BINDING_MISMATCH")
    ex = b["execution"]
    _need(
        context["started_at_utc_ns"]
        <= ex["started_utc_ns"]
        <= ex["finished_utc_ns"]
        <= context["finished_at_utc_ns"],
        "HOST_BOOT_OUTSIDE_PHASE",
    )
    response = b["response"]
    return (
        boot,
        b,
        dict(
            machine_uuid=None if response is None else response["machine_uuid"],
            boot_time_utc=(
                None if response is None else response["last_boot_up_time_utc"]
            ),
        ),
    )


def _native(plan, context, payload):
    p = plan.to_dict()
    data = verify_native_camera_enrollment_snapshot(
        _load(payload, ROLE_LIMITS["native_enrollment"]),
        source_sha256=p["binding"]["source_sha256"],
        launch_session_id=context["launch_session_id"],
    )
    selection = selection_from_enrollment_snapshot(
        data,
        source_sha256=p["binding"]["source_sha256"],
        launch_session_id=context["launch_session_id"],
    )
    identity = data["identity_packet"]["receipt"]
    driver = identity.get("driver")
    candidate = data["generic_review"]["candidate_record"]
    usb = candidate["usb_identity"]

    def observed(item):
        return (
            item["value"]
            if item is not None and item["availability"] == "OBSERVED"
            else None
        )

    device = identity["device"]
    values = dict(
        generic_serial=usb["unit_serial"],
        generic_vid=usb["vid"],
        generic_pid=usb["pid"],
        generic_driver_service=candidate["driver_service"],
        container_id=None if device is None else observed(device["container_id"]),
        endpoint=identity["requested_endpoint"],
        endpoint_instance=None if device is None else observed(device["instance_id"]),
    )
    for target, key in (
        ("driver_provider", "provider"),
        ("driver_service", "service"),
        ("driver_version", "version"),
        ("driver_inf", "inf_path"),
    ):
        values[target] = None if driver is None else observed(driver[key])
    return data, selection, values


def _observed_usb_fields(plan, context, sources, *, boot_origin):
    """Derive descriptor facts without imposing a predecessor representation.

    Both the historical endpoint-only series and the physical-node successor
    use this exact parser. Callers separately verify boot bytes and the typed
    original predecessor; this helper never constructs a substitute phase,
    authenticates storage, obtains a permit or invokes a provider.
    """
    values = dict.fromkeys(sorted(_VALUE_FIELDS))
    checks = []
    execution = dict.fromkeys(
        (
            "attempt_id",
            "permit_sha256",
            "operation_sha256",
            "usb3_operating",
            "ex_speed",
            "ex_v2_available",
            "process_clean",
            "native_clean",
        )
    )
    data, selection, metadata_values = _native(
        plan, context, sources["native_enrollment"]
    )
    values.update(metadata_values)
    # Import only the closed pure evidence codec, never the executable owner.
    from rocell.providers.windows.owned_usb_identity_evidence import (
        OwnedUsbIdentityRunEvidence,
    )

    run = OwnedUsbIdentityRunEvidence(sources["owned_usb_run"])
    run_data = run.to_dict()
    prepared = run.preparation
    request = prepared.request.to_dict()
    identity = prepared.identity.to_dict()
    p = plan.to_dict()["binding"]
    _need(
        all(
            identity[k] == p[k]
            for k in (
                "source_sha256",
                "cell_id",
                "session_id",
                "header_sha256",
                "stage_policy_sha256",
            )
        ),
        "OWNED_RUN_ORIGINAL_CONTEXT_MISMATCH",
    )
    packet = data["identity_packet"]
    native = packet["receipt"]
    _need(
        request["native_identity_sha256"] == data["view"]["identity"]["identity_sha256"]
        and request["endpoint"] == native["requested_endpoint"],
        "USB_NATIVE_TARGET_MISMATCH",
    )
    device = native["device"]
    if device is not None and device["instance_id"]["availability"] == "OBSERVED":
        _need(
            request["expected_device_instance_id"] == device["instance_id"]["value"],
            "USB_NATIVE_INSTANCE_MISMATCH",
        )
    if selection is not None:
        _need(
            identity["selection_sha256"] == selection.sha256,
            "USB_SELECTION_MISMATCH",
        )
    _need(
        context["started_at_utc_ns"]
        <= run_data["started_utc_ns"]
        <= run_data["finished_utc_ns"]
        <= context["finished_at_utc_ns"],
        "USB_RUN_OUTSIDE_PHASE",
    )
    observation = run.observation
    obs = None if observation is None else observation.to_dict()
    summary = run.safe_summary()
    process_clean = run.process_cleanup_confirmed
    native_clean = run.usb_cleanup_confirmed
    checks += [
        dict(check_id="REVIEWED_NATIVE_SELECTION", passed=selection is not None),
        dict(
            check_id="OWNED_USB_RUN_SUCCEEDED",
            passed=run.status == "OBSERVED" and run.released,
        ),
        dict(
            check_id="USB_OBSERVATION_COMPLETE",
            passed=obs is not None and obs["outcome"] == "OBSERVED",
        ),
        dict(check_id="PROCESS_CLEANUP_CONFIRMED", passed=process_clean),
        dict(check_id="NATIVE_CLEANUP_CONFIRMED", passed=native_clean),
        dict(
            check_id="DRIVER_FIELDS_OBSERVED",
            passed=all(
                values[k] is not None
                for k in (
                    "driver_provider",
                    "driver_service",
                    "driver_version",
                    "driver_inf",
                )
            ),
        ),
        dict(
            check_id="DRIVER_SERVICE_MATCH",
            passed=values["driver_service"] is not None
            and values["driver_service"] == values["generic_driver_service"],
        ),
    ]
    execution.update(
        attempt_id=request["attempt_id"],
        permit_sha256=request["permit_sha256"],
        operation_sha256=request["operation_sha256"],
        process_clean=process_clean,
        native_clean=native_clean,
    )
    if obs is not None:
        mapping, desc, link = (
            obs["pre_mapping"],
            obs["device_descriptor"],
            obs["link"],
        )
        if mapping is not None:
            values.update(
                endpoint=mapping["returned_endpoint"],
                endpoint_instance=mapping["endpoint_instance_id"],
                physical_usb_instance=mapping["physical_usb_instance_id"],
                host_controller=mapping["host_controller_instance_id"],
                port_topology=[
                    {
                        k: hop[k]
                        for k in (
                            "hub_instance_id",
                            "hub_interface_path",
                            "connection_index",
                            "downstream_driver_key",
                        )
                    }
                    for hop in mapping["hops"]
                ],
            )
        if desc is not None:
            values.update(vid=desc["vid"], pid=desc["pid"])
        serials = obs["serial_descriptors"]
        if serials and all(s["value"] == serials[0]["value"] for s in serials):
            values["descriptor_serial"] = serials[0]["value"]
        if link is not None:
            execution.update(
                ex_speed=link["ex_speed"],
                ex_v2_available=link["ex_v2_available"],
                usb3_operating=_operating_usb3(link),
            )
    checks.append(
        dict(
            check_id="V2_OPERATING_USB3_OBSERVED",
            passed=execution["usb3_operating"] is True,
        )
    )
    provenance = dict(
        usb=summary["provenance"],
        metadata=packet["provenance"],
        boot=boot_origin,
        metadata_helper_sha256=packet["helper_sha256"],
    )
    return values, checks, execution, provenance


def build_usb_qualification_phase(
    plan, *, phase, predecessor, context, sources, references
):
    """Derive one phase from retained originals, without invoking their providers.

    ``sources`` maps each role to exact original bytes. ``references`` maps the
    same roles to authenticated original-store references supplied by the owner.
    The predecessor is the preceding manifest; series verification joins the
    complete original prefix again before assessment or review.
    """
    _need(type(plan) is UsbQualificationPlan and phase in PHASES)
    plan = UsbQualificationPlan(plan.payload)
    _context(context)
    _need(context["started_at_utc_ns"] >= plan.to_dict()["created_at_utc_ns"])
    ordinal = PHASES.index(phase)
    if ordinal:
        _need(type(predecessor) is UsbQualificationPhase)
        previous = predecessor.to_dict()
        _need(
            previous["ordinal"] == ordinal - 1
            and previous["plan_sha256"] == plan.sha256
            and previous["context"]["finished_at_utc_ns"]
            <= context["started_at_utc_ns"]
            and previous["context"]["operation_id"] != context["operation_id"],
            "EXACT_ORDERED_PHASE_REQUIRED",
        )
    else:
        _need(predecessor is None)
    roles = (
        ("endpoint_inventory", "host_boot")
        if phase == "RECONNECT_ABSENCE"
        else ("native_enrollment", "owned_usb_run", "host_boot")
    )
    _need(
        type(references) is dict
        and set(references) == set(roles)
        and type(sources) is dict
        and set(sources) == set(roles)
    )
    records = [_manifest(role, sources[role], references[role]) for role in roles]
    _phase_originals(records, sources)
    boot, b, boot_values = _boot(plan, phase, context, sources["host_boot"])
    values = dict.fromkeys(sorted(_VALUE_FIELDS))
    values.update(boot_values)
    checks = [
        dict(check_id="HOST_BOOT_OBSERVED", passed=b["status"] == "OBSERVED_HOST_BOOT")
    ]
    execution = dict.fromkeys(
        (
            "attempt_id",
            "permit_sha256",
            "operation_sha256",
            "usb3_operating",
            "ex_speed",
            "ex_v2_available",
            "process_clean",
            "native_clean",
        )
    )
    if phase == "RECONNECT_ABSENCE":
        packet = _load(sources["endpoint_inventory"], ROLE_LIMITS["endpoint_inventory"])
        packet, inventory = validate_native_packet(
            packet,
            kind="inventory",
            provenance=packet["provenance"],
            helper_sha256=predecessor.to_dict()["provenance"]["metadata_helper_sha256"],
        )
        endpoint = predecessor.to_dict()["values"]["endpoint"]
        hashes = {digest(canonical(c.symbolic_link)) for c in inventory.candidates}
        complete = inventory.status == "OK" and inventory.cleanup_confirmed
        absent = (
            complete
            and endpoint["sha256"] is not None
            and endpoint["sha256"] not in hashes
        )
        checks += [
            dict(check_id="ENDPOINT_INVENTORY_COMPLETE", passed=complete),
            dict(check_id="REVIEWED_ENDPOINT_ABSENT", passed=absent),
            # An existing packet has no acquisition nonce or time bracket.
            dict(check_id="ENDPOINT_INVENTORY_FRESHNESS_REQUIRED", passed=False),
        ]
        provenance = dict(
            usb=None,
            metadata=packet["provenance"],
            boot=b["origin"],
            metadata_helper_sha256=packet["helper_sha256"],
        )
    else:
        values, observed_checks, execution, provenance = _observed_usb_fields(
            plan, context, sources, boot_origin=b["origin"]
        )
        values.update(boot_values)
        checks += observed_checks
    return UsbQualificationPhase(
        canonical(
            _document(
                "phase",
                plan_sha256=plan.sha256,
                phase=phase,
                ordinal=ordinal,
                predecessor_sha256=None if predecessor is None else predecessor.sha256,
                context=context,
                records=records,
                values={k: _display(v) for k, v in values.items()},
                checks=checks,
                status=(
                    "OBSERVATIONS_RETAINED"
                    if all(x["passed"] for x in checks)
                    else "HELD"
                ),
                provenance=provenance,
                execution=execution,
                absence_scope=(
                    "CAMERA_ENDPOINTS_ONLY" if phase == "RECONNECT_ABSENCE" else None
                ),
            )
        )
    )


def verify_usb_qualification_phase(
    value, *, plan, predecessor, sources, expected_sha256
):
    phase = UsbQualificationPhase(
        value.payload if type(value) is UsbQualificationPhase else value
    )
    d = phase.to_dict()
    made = build_usb_qualification_phase(
        plan,
        phase=d["phase"],
        predecessor=predecessor,
        context=d["context"],
        sources=sources,
        references={r["role"]: r["reference"] for r in d["records"]},
    )
    _need(
        phase.sha256 == expected_sha256 and phase.payload == made.payload,
        "PHASE_RECONSTRUCTION_MISMATCH",
    )
    return phase


def build_usb_qualification_series(plan, *, phases, references):
    _need(
        type(plan) is UsbQualificationPlan
        and type(phases) in (tuple, list)
        and len(phases) <= 4
        and type(references) in (tuple, list)
        and len(references) == len(phases)
    )
    previous = None
    for ordinal, phase in enumerate(phases):
        _need(type(phase) is UsbQualificationPhase)
        d = phase.to_dict()
        _need(
            d["plan_sha256"] == plan.sha256
            and d["ordinal"] == ordinal
            and d["predecessor_sha256"]
            == (None if previous is None else previous.sha256),
            "SERIES_PREFIX_MISMATCH",
        )
        previous = phase
    return UsbQualificationSeries(
        canonical(
            _document(
                "series",
                plan_sha256=plan.sha256,
                phases=[
                    _manifest(PHASES[i], phase.payload, ref)
                    for i, (phase, ref) in enumerate(zip(phases, references))
                ],
            )
        )
    )


def assess_usb_qualification_series(plan, series, *, phases, phase_sources, received):
    """Reconstruct every supplied original before computing the bounded view."""
    _need(type(plan) is UsbQualificationPlan and type(series) is UsbQualificationSeries)
    _exact(received, {"submission", "assessment", "review"})
    plan = verify_usb_qualification_plan(
        plan,
        expected_sha256=plan.sha256,
        **{"received_" + role: subject for role, subject in received.items()},
    )
    d, p = series.to_dict(), plan.to_dict()
    expected = build_usb_qualification_series(
        plan, phases=phases, references=[r["reference"] for r in d["phases"]]
    )
    _need(
        series.payload == expected.payload
        and type(phase_sources) in (tuple, list)
        and len(phase_sources) == len(phases)
    )
    checked, previous = [], None
    for phase, sources in zip(phases, phase_sources):
        current = verify_usb_qualification_phase(
            phase,
            plan=plan,
            predecessor=previous,
            sources=sources,
            expected_sha256=phase.sha256,
        )
        checked.append(current.to_dict())
        previous = current
    checks = [
        dict(check_id="PHYSICAL_PROVENANCE_REQUIRED", passed=p["mode"] == "PHYSICAL"),
        dict(check_id="ALL_FOUR_PHASES_REQUIRED", passed=len(checked) == 4),
        dict(check_id="PHYSICAL_USB_ABSENCE_REQUIRED", passed=False),
    ]
    comparisons = []
    observation_rows = [x for x in checked if x["phase"] != "RECONNECT_ABSENCE"]
    used_attempts, used_permits, used_operations = set(), set(), set()
    for i, row in enumerate(checked):
        prefix = row["phase"]
        checks.append(
            dict(
                check_id=prefix + "_COMPLETE",
                passed=row["status"] == "OBSERVATIONS_RETAINED",
            )
        )
        origins = row["provenance"]
        physical = (
            origins["boot"] == "WINDOWS_LOCAL_CIM"
            and origins["metadata"] == "WINDOWS_NATIVE_METADATA"
            and origins["usb"] in (None, "PHYSICAL_USB_QUERY")
        )
        checks.append(dict(check_id=prefix + "_PHYSICAL_ORIGINS", passed=physical))
        if i:
            before = HostBootObservation(phase_sources[i - 1]["host_boot"])
            after = HostBootObservation(phase_sources[i]["host_boot"])
            comparison = compare_boot_observations(before, after)
            expected_status = (
                "SAME_HOST_DIFFERENT_BOOT"
                if prefix == "AFTER_REBOOT"
                else "SAME_HOST_SAME_BOOT"
            )
            checks.append(
                dict(
                    check_id=prefix + "_BOOT_RELATION",
                    passed=comparison["status"] == expected_status,
                )
            )
        if prefix == "RECONNECT_ABSENCE":
            continue
        values = row["values"]
        serial_hash = digest(canonical(p["received_label"]["serial"]))
        checks.append(
            dict(
                check_id=prefix + "_RECEIVED_SERIAL_MATCH",
                passed=values["descriptor_serial"]["sha256"]
                == serial_hash
                == values["generic_serial"]["sha256"],
            )
        )
        checks.append(
            dict(
                check_id=prefix + "_GENERIC_VID_PID_MATCH",
                passed=all(
                    values[k]["sha256"] is not None
                    and values[k]["sha256"] == values["generic_" + k]["sha256"]
                    for k in ("vid", "pid")
                ),
            )
        )
        ex = row["execution"]
        for name, used in (
            ("attempt_id", used_attempts),
            ("permit_sha256", used_permits),
            ("operation_sha256", used_operations),
        ):
            _need(ex[name] not in used, "NO_REPLAY_OR_REUSED_ADMISSION")
            used.add(ex[name])
    for row in observation_rows[1:]:
        baseline = observation_rows[0]
        for field in sorted(_VALUE_FIELDS - {"boot_time_utc"}):
            before, after = baseline["values"][field], row["values"][field]
            status = (
                "NOT_OBSERVED"
                if before["sha256"] is None or after["sha256"] is None
                else ("MATCHED" if before["sha256"] == after["sha256"] else "CHANGED")
            )
            comparisons.append(
                dict(
                    field=field,
                    status=status,
                    before_phase="BASELINE",
                    after_phase=row["phase"],
                )
            )
        checks.append(
            dict(
                check_id=row["phase"] + "_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY",
                passed=all(
                    baseline["values"][k]["sha256"] is not None
                    and baseline["values"][k]["sha256"] == row["values"][k]["sha256"]
                    for k in _VALUE_FIELDS - {"boot_time_utc"}
                ),
            )
        )
    phase_views = [
        dict(
            phase=x["phase"],
            phase_sha256=phases[i].sha256,
            status=x["status"],
            checks=x["checks"],
            provenance=x["provenance"],
            execution=x["execution"],
            values=x["values"],
            absence_scope=x["absence_scope"],
        )
        for i, x in enumerate(checked)
    ]
    return UsbQualificationAssessment(
        canonical(
            _bounded_assessment_values(
                _document(
                    "assessment",
                    binding=p["binding"],
                    plan_sha256=plan.sha256,
                    series_sha256=series.sha256,
                    mode=p["mode"],
                    verdict="BLOCKED",
                    checks=checks,
                    missing_requirements=[
                        x["check_id"] for x in checks if not x["passed"]
                    ],
                    phases=phase_views,
                    comparisons=comparisons,
                    received_label=p["received_label"],
                    cable_label=p["cable_label"],
                    port_label=p["port_label"],
                )
            )
        )
    )


def verify_usb_qualification_assessment(
    value, *, plan, series, phases, phase_sources, received, expected_sha256
):
    current = UsbQualificationAssessment(
        value.payload if type(value) is UsbQualificationAssessment else value
    )
    made = assess_usb_qualification_series(
        plan, series, phases=phases, phase_sources=phase_sources, received=received
    )
    _need(
        current.sha256 == expected_sha256 and current.payload == made.payload,
        "ASSESSMENT_RECONSTRUCTION_MISMATCH",
    )
    return current


def review_usb_qualification_series(
    plan,
    series,
    assessment,
    *,
    phases,
    phase_sources,
    received,
    reviewer_id,
    review_launch_id,
    reviewed_at_utc_ns,
    decision,
):
    checked = verify_usb_qualification_assessment(
        assessment,
        plan=plan,
        series=series,
        phases=phases,
        phase_sources=phase_sources,
        received=received,
        expected_sha256=assessment.sha256,
    )
    actors = {plan.to_dict()["operator_id"].casefold()} | {
        p.to_dict()["context"]["operator_id"].casefold() for p in phases
    }
    _text(reviewer_id, 64)
    _need(reviewer_id.casefold() not in actors, "DISTINCT_REVIEW_LABEL_REQUIRED")
    latest = (
        plan.to_dict()["created_at_utc_ns"]
        if not phases
        else phases[-1].to_dict()["context"]["finished_at_utc_ns"]
    )
    _need(reviewed_at_utc_ns >= latest, "REVIEW_PRECEDES_SUBJECT")
    return UsbQualificationReview(
        canonical(
            _document(
                "review",
                plan_sha256=plan.sha256,
                series_sha256=series.sha256,
                assessment_sha256=checked.sha256,
                decision=decision,
                reviewer_id=reviewer_id,
                review_launch_id=review_launch_id,
                reviewed_at_utc_ns=reviewed_at_utc_ns,
                verdict="BLOCKED",
                distinct_operator_labels=True,
                authenticated_independent_people=False,
            )
        )
    )


def verify_usb_qualification_review(
    value, *, plan, series, assessment, phases, phase_sources, received, expected_sha256
):
    current = UsbQualificationReview(
        value.payload if type(value) is UsbQualificationReview else value
    )
    d = current.to_dict()
    made = review_usb_qualification_series(
        plan,
        series,
        assessment,
        phases=phases,
        phase_sources=phase_sources,
        received=received,
        **{
            k: d[k]
            for k in (
                "reviewer_id",
                "review_launch_id",
                "reviewed_at_utc_ns",
                "decision",
            )
        },
    )
    _need(
        current.sha256 == expected_sha256 and current.payload == made.payload,
        "REVIEW_RECONSTRUCTION_MISMATCH",
    )
    return current
