"""Pure four-phase comparison and review; no store, device or stage authority.

Each computation reconstructs the heterogeneous original phases and their
received-camera binding using the existing codecs. Caller-supplied references
and permits must separately be authenticated by the original storage owner.
Eligibility here is only for that owner's exact-subject review, not proof of
fresh metadata publication, physical truth, capture or arm qualification.
"""

from dataclasses import dataclass
import re
from typing import Any, ClassVar

from rocell.application import physical_camera_usb_qualification as qualification
from rocell.application import physical_usb_presence_phase as presence
from rocell.application import physical_usb_reconnect_phase as reconnect
from rocell.application import physical_usb_reboot_phase as reboot
from rocell.application.physical_usb_trial_boot import _terminal as boot_terminal
from rocell.providers.windows.host_boot_observation import HostBootObservation
from rocell.providers.windows.usb_identity_protocol import canonical, digest


SCHEMAS = {
    role: f"rocell.usb_complete_qualification_{role}.v1"
    for role in ("series", "assessment", "review")
}
LIMITS = dict(series=16 * 1024, assessment=32 * 1024, review=8 * 1024)
PHASES = ("BASELINE", "RECONNECT_ABSENCE", "AFTER_RECONNECT", "AFTER_REBOOT")
PHASE_CHECKS = (
    qualification.OBSERVATION_CHECK_IDS,
    presence.CHECKS,
    reconnect.CHECKS,
    reboot.CHECKS,
)
PHASE_STATUS = (
    "OBSERVATIONS_RETAINED",
    "ABSENCE_OBSERVATIONS_RETAINED",
    "RECONNECT_OBSERVATIONS_RETAINED",
    "REBOOT_OBSERVATIONS_RETAINED",
)
PHASE_LIMITS = dict(
    zip(
        PHASES,
        (16 * 1024, presence.PHASE_LIMIT, reconnect.PHASE_LIMIT, reboot.PHASE_LIMIT),
    )
)
FLAGS = dict(
    **qualification.FLAGS,
    original_store_authenticated=False,
    metadata_acquisition_freshness_verified=False,
    authenticated_independent_people=False,
    mechanical_unplug_verified=False,
    continuous_absence_verified=False,
    host_restart_verified=False,
    cryptographic_attestation=False,
    arm_access_authorized=False,
)
MEANING = (
    "Four independently reconstructed original-byte phase records only. "
    "The original owner must separately authenticate storage, publication and "
    "current state. Review labels do not authenticate independent people. "
    "No stage PASS, capture, camera runtime, arm, motion or contact permission."
)
CHECK_IDS = (
    "PHYSICAL_PLAN",
    "BASELINE_PHYSICAL_OWNED_BOOT",
    *(phase + "_COMPLETE" for phase in PHASES),
    *(
        phase + "__" + check
        for phase, checks in zip(PHASES, PHASE_CHECKS)
        for check in checks
    ),
)
PREDECESSOR_KEYS = frozenset(
    (
        "original_baseline",
        "received",
        "absence",
        "absence_reference",
        "absence_sources",
        "reconnect",
        "reconnect_reference",
        "reconnect_sources",
        "reconnect_permit",
    )
)
ELIGIBLE = "ELIGIBLE_FOR_ORIGINAL_REVIEW"
REVIEW_ELIGIBLE = "ELIGIBLE_FOR_ORIGINAL_STAGE_ACCEPTANCE"


class CompleteUsbSeriesError(ValueError):
    """A closed reconstruction mismatch, without raw original identifiers."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise CompleteUsbSeriesError(code)


def _series_id(value: Any) -> None:
    _need(
        type(value) is str
        and re.fullmatch(r"usbseries-[0-9a-f]{32}", value) is not None,
        "EXACT_COMPLETE_SERIES_ID_REQUIRED",
    )


def _document(role: str, **fields: Any) -> dict[str, Any]:
    return dict(schema=SCHEMAS[role], meaning=MEANING, **FLAGS, **fields)


def _validate(role: str, payload: bytes) -> dict[str, Any]:
    try:
        d = qualification._load(payload, LIMITS[role])
        common = {"schema", "meaning", *FLAGS, "series_id", "binding", "plan_sha256"}
        extra = {
            "series": {"phases"},
            "assessment": {
                "series_sha256",
                "verdict",
                "checks",
                "missing_requirements",
                "phases",
                "comparisons",
            },
            "review": {
                "series_sha256",
                "assessment_sha256",
                "verdict",
                "decision",
                "reviewer_id",
                "review_launch_id",
                "reviewed_at_utc_ns",
                "distinct_operator_labels",
            },
        }[role]
        qualification._exact(d, common | extra)
        _need(
            d["schema"] == SCHEMAS[role]
            and d["meaning"] == MEANING
            and all(d[key] is False for key in FLAGS),
            "EXACT_COMPLETE_SERIES_MEANING",
        )
        _series_id(d["series_id"])
        qualification._binding(d["binding"])
        qualification._sha(d["plan_sha256"])
        if role == "series":
            qualification._manifest_check(d["phases"], PHASES, PHASE_LIMITS)
        else:
            qualification._sha(d["series_sha256"])
        if role == "assessment":
            qualification._checks(d["checks"])
            _need(
                tuple(row["check_id"] for row in d["checks"]) == CHECK_IDS,
                "EXACT_COMPLETE_SERIES_CHECKS",
            )
            missing = [row["check_id"] for row in d["checks"] if not row["passed"]]
            _need(
                d["missing_requirements"] == missing
                and d["verdict"] == ("BLOCKED" if missing else ELIGIBLE),
                "COMPLETE_SERIES_VERDICT_MISMATCH",
            )
            _need(
                type(d["phases"]) is list and len(d["phases"]) == 4,
                "EXACT_COMPLETE_PHASE_SUMMARIES",
            )
            passed = {row["check_id"]: row["passed"] for row in d["checks"]}
            for index, row in enumerate(d["phases"]):
                qualification._exact(
                    row, {"phase", "phase_sha256", "status", "missing_checks"}
                )
                qualification._sha(row["phase_sha256"])
                _need(
                    row["phase"] == PHASES[index]
                    and row["status"]
                    == ("HELD" if row["missing_checks"] else PHASE_STATUS[index])
                    and type(row["missing_checks"]) is list
                    and row["missing_checks"]
                    == [
                        key
                        for key in PHASE_CHECKS[index]
                        if not passed[PHASES[index] + "__" + key]
                    ]
                    and (row["status"] == PHASE_STATUS[index])
                    == passed[PHASES[index] + "_COMPLETE"],
                    "EXACT_COMPLETE_PHASE_SUMMARY",
                )
            _need(
                type(d["comparisons"]) is list
                and len(d["comparisons"]) == len(reboot.COMPARISON_FIELDS),
                "EXACT_COMPLETE_COMPARISONS",
            )
            for field, row in zip(reboot.COMPARISON_FIELDS, d["comparisons"]):
                qualification._exact(row, {"field", "status"})
                _need(
                    row["field"] == field
                    and row["status"] in ("MATCHED", "CHANGED", "NOT_OBSERVED"),
                    "EXACT_COMPLETE_COMPARISON",
                )
        if role == "review":
            qualification._sha(d["assessment_sha256"])
            qualification._text(d["reviewer_id"], 64)
            qualification._identifier(d["review_launch_id"])
            qualification._integer(d["reviewed_at_utc_ns"], 1)
            _need(
                d["decision"] in ("ACKNOWLEDGE_EXACT", "REJECT")
                and d["verdict"] in ("BLOCKED", REVIEW_ELIGIBLE)
                and (d["decision"] != "REJECT" or d["verdict"] == "BLOCKED")
                and d["distinct_operator_labels"] is True,
                "EXACT_COMPLETE_REVIEW",
            )
        return d
    except CompleteUsbSeriesError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise CompleteUsbSeriesError("COMPLETE_SERIES_INVALID_SUBJECT") from exc


class _Subject:
    payload: bytes
    role: ClassVar[str]

    def __post_init__(self) -> None:
        _validate(self.role, self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate(self.role, self.payload)


@dataclass(frozen=True, slots=True)
class CompleteUsbSeries(_Subject):
    payload: bytes
    role: ClassVar[str] = "series"


@dataclass(frozen=True, slots=True)
class CompleteUsbAssessment(_Subject):
    payload: bytes
    role: ClassVar[str] = "assessment"


@dataclass(frozen=True, slots=True)
class CompleteUsbReview(_Subject):
    payload: bytes
    role: ClassVar[str] = "review"


def _reconstruct(
    *,
    predecessor: dict[str, Any],
    reboot_payload: bytes,
    reboot_reference: Any,
    reboot_permit: Any,
    reboot_sources: dict[str, bytes],
    reboot_references: dict[str, Any],
) -> tuple[Any, tuple[Any, ...], tuple[Any, ...], bytes]:
    """One full pure reconstruction per public operation; no persistent cache."""
    try:
        _need(
            type(predecessor) is dict and set(predecessor) == PREDECESSOR_KEYS,
            "EXACT_COMPLETE_PREDECESSOR_INPUTS",
        )
        checked = reboot.verify_usb_reboot_qualification_phase(
            reboot_payload,
            expected_sha256=digest(reboot_payload),
            **predecessor,
            permit=reboot_permit,
            sources=reboot_sources,
            references=reboot_references,
        )
        original = predecessor["original_baseline"]
        phase_reference = qualification._reference(reboot_reference, checked.payload)
        used = reboot._historical_ids(
            original, predecessor["absence"], predecessor["reconnect"]
        )
        used.update(
            qualification._reference(predecessor[key]).evidence_id
            for key in ("absence_reference", "reconnect_reference")
        )
        used.update(
            row["reference"]["evidence_id"] for row in checked.to_dict()["records"]
        )
        _need(
            phase_reference.evidence_id not in used,
            "DISTINCT_COMPLETE_PHASE_REFERENCE_REQUIRED",
        )
        # The existing verifier reconstructed all of these subjects, including
        # received originals, independent permits and cross-phase ordering.
        phases = (
            original["baseline"],
            predecessor["absence"],
            predecessor["reconnect"],
            checked,
        )
        references = (
            original["baseline_reference"],
            predecessor["absence_reference"],
            predecessor["reconnect_reference"],
            phase_reference,
        )
        return (
            original["plan"],
            phases,
            references,
            original["baseline_sources"]["host_boot"],
        )
    except CompleteUsbSeriesError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise CompleteUsbSeriesError(
            "COMPLETE_SERIES_ORIGINAL_RECONSTRUCTION_MISMATCH"
        ) from exc


def _series(
    series_id: str, parts: tuple[Any, tuple[Any, ...], tuple[Any, ...], bytes]
) -> CompleteUsbSeries:
    plan, phases, references, _ = parts
    return CompleteUsbSeries(
        canonical(
            _document(
                "series",
                series_id=series_id,
                binding=plan.to_dict()["binding"],
                plan_sha256=plan.sha256,
                phases=[
                    qualification._manifest(name, phase.payload, ref)
                    for name, phase, ref in zip(PHASES, phases, references)
                ],
            )
        )
    )


def build_complete_usb_series(*, series_id: str, **originals: Any) -> CompleteUsbSeries:
    return _series(series_id, _reconstruct(**originals))


def build_complete_usb_assessment_pair(
    *, series_id: str, **originals: Any
) -> tuple[CompleteUsbSeries, CompleteUsbAssessment]:
    """Build the two publication subjects with one fresh reconstruction.

    No verification result or original authority is cached between operations.
    This is only a pure computation; the service still authenticates storage.
    """
    parts = _reconstruct(**originals)
    series = _series(series_id, parts)
    return series, _assessment(series, parts)


def verify_complete_usb_series(
    value: Any, *, expected_sha256: str, **originals: Any
) -> CompleteUsbSeries:
    current = CompleteUsbSeries(
        value.payload if type(value) is CompleteUsbSeries else value
    )
    qualification._sha(expected_sha256)
    made = _series(current.to_dict()["series_id"], _reconstruct(**originals))
    _need(
        current.sha256 == expected_sha256 and current.payload == made.payload,
        "COMPLETE_SERIES_RECONSTRUCTION_MISMATCH",
    )
    return current


def _assessment(
    series: Any, parts: tuple[Any, tuple[Any, ...], tuple[Any, ...], bytes]
) -> CompleteUsbAssessment:
    current = CompleteUsbSeries(
        series.payload if type(series) is CompleteUsbSeries else series
    )
    sd = current.to_dict()
    _need(
        current.payload == _series(sd["series_id"], parts).payload,
        "COMPLETE_SERIES_RECONSTRUCTION_MISMATCH",
    )
    plan, phases, _, baseline_boot = parts
    documents = [phase.to_dict() for phase in phases]
    checks = [
        dict(check_id="PHYSICAL_PLAN", passed=plan.to_dict()["mode"] == "PHYSICAL"),
        dict(
            check_id="BASELINE_PHYSICAL_OWNED_BOOT",
            passed=boot_terminal(HostBootObservation(baseline_boot)) == "BOOT_RETAINED",
        ),
        *(
            dict(check_id=name + "_COMPLETE", passed=d["status"] == status)
            for name, d, status in zip(PHASES, documents, PHASE_STATUS)
        ),
        *(
            dict(check_id=name + "__" + row["check_id"], passed=row["passed"])
            for name, d in zip(PHASES, documents)
            for row in d["checks"]
        ),
    ]
    missing = [row["check_id"] for row in checks if not row["passed"]]
    return CompleteUsbAssessment(
        canonical(
            _document(
                "assessment",
                series_id=sd["series_id"],
                binding=sd["binding"],
                plan_sha256=plan.sha256,
                series_sha256=current.sha256,
                verdict="BLOCKED" if missing else ELIGIBLE,
                checks=checks,
                missing_requirements=missing,
                phases=[
                    dict(
                        phase=name,
                        phase_sha256=phase.sha256,
                        status=d["status"],
                        missing_checks=[
                            r["check_id"] for r in d["checks"] if not r["passed"]
                        ],
                    )
                    for name, phase, d in zip(PHASES, phases, documents)
                ],
                comparisons=[
                    dict(field=row["field"], status=row["status"])
                    for row in documents[-1]["comparisons"]
                ],
            )
        )
    )


def assess_complete_usb_series(series: Any, **originals: Any) -> CompleteUsbAssessment:
    return _assessment(series, _reconstruct(**originals))


def verify_complete_usb_assessment(
    value: Any, *, series: Any, expected_sha256: str, **originals: Any
) -> CompleteUsbAssessment:
    current = CompleteUsbAssessment(
        value.payload if type(value) is CompleteUsbAssessment else value
    )
    qualification._sha(expected_sha256)
    made = assess_complete_usb_series(series, **originals)
    _need(
        current.sha256 == expected_sha256 and current.payload == made.payload,
        "COMPLETE_ASSESSMENT_RECONSTRUCTION_MISMATCH",
    )
    return current


def review_complete_usb_series(
    series: Any,
    assessment: Any,
    *,
    reviewer_id: str,
    review_launch_id: str,
    reviewed_at_utc_ns: int,
    decision: str,
    **originals: Any,
) -> CompleteUsbReview:
    return _review_complete_usb_series(
        series,
        assessment,
        reviewer_id=reviewer_id,
        review_launch_id=review_launch_id,
        reviewed_at_utc_ns=reviewed_at_utc_ns,
        decision=decision,
        parts=_reconstruct(**originals),
    )


def _review_complete_usb_series(
    series: Any,
    assessment: Any,
    *,
    reviewer_id: str,
    review_launch_id: str,
    reviewed_at_utc_ns: int,
    decision: str,
    parts: tuple[Any, tuple[Any, ...], tuple[Any, ...], bytes],
) -> CompleteUsbReview:
    """Internal reuse within one reconstruction, never a saved approval cache."""
    checked = _assessment(series, parts)
    supplied = CompleteUsbAssessment(
        assessment.payload if type(assessment) is CompleteUsbAssessment else assessment
    )
    _need(
        supplied.payload == checked.payload,
        "COMPLETE_ASSESSMENT_RECONSTRUCTION_MISMATCH",
    )
    plan, phases, _, _ = parts
    actors = {plan.to_dict()["operator_id"].casefold()} | {
        phase.to_dict()["context"]["operator_id"].casefold() for phase in phases
    }
    qualification._text(reviewer_id, 64)
    qualification._integer(reviewed_at_utc_ns, 1)
    _need(
        reviewer_id.casefold() not in actors, "DISTINCT_COMPLETE_REVIEW_LABEL_REQUIRED"
    )
    _need(
        reviewed_at_utc_ns >= phases[-1].to_dict()["context"]["finished_at_utc_ns"],
        "COMPLETE_REVIEW_PRECEDES_SUBJECT",
    )
    d = checked.to_dict()
    eligible = d["verdict"] == ELIGIBLE and decision == "ACKNOWLEDGE_EXACT"
    return CompleteUsbReview(
        canonical(
            _document(
                "review",
                series_id=d["series_id"],
                binding=d["binding"],
                plan_sha256=d["plan_sha256"],
                series_sha256=d["series_sha256"],
                assessment_sha256=checked.sha256,
                verdict=REVIEW_ELIGIBLE if eligible else "BLOCKED",
                decision=decision,
                reviewer_id=reviewer_id,
                review_launch_id=review_launch_id,
                reviewed_at_utc_ns=reviewed_at_utc_ns,
                distinct_operator_labels=True,
            )
        )
    )


def verify_complete_usb_review(
    value: Any, *, series: Any, assessment: Any, expected_sha256: str, **originals: Any
) -> CompleteUsbReview:
    current = CompleteUsbReview(
        value.payload if type(value) is CompleteUsbReview else value
    )
    qualification._sha(expected_sha256)
    d = current.to_dict()
    made = review_complete_usb_series(
        series,
        assessment,
        **{
            key: d[key]
            for key in (
                "reviewer_id",
                "review_launch_id",
                "reviewed_at_utc_ns",
                "decision",
            )
        },
        **originals,
    )
    _need(
        current.sha256 == expected_sha256 and current.payload == made.payload,
        "COMPLETE_REVIEW_RECONSTRUCTION_MISMATCH",
    )
    return current


def verify_complete_usb_subject_chain(
    payloads: dict[str, bytes],
    *,
    expected_sha256s: dict[str, str],
    expected_series_id: str,
    **originals: Any,
) -> tuple[CompleteUsbSeries | CompleteUsbAssessment | CompleteUsbReview, ...]:
    """Verify a retained role prefix with one full reconstruction per call.

    The original reader separately authenticates each supplied digest/reference,
    the complete M1 store and its campaign family. These are independently
    supplied role bytes, not a caller-authored verdict or persistent cache.
    An empty prefix has no series meaning and yields no acceptance evidence.
    """
    order = ("series", "assessment", "review")
    classes = dict(
        series=CompleteUsbSeries,
        assessment=CompleteUsbAssessment,
        review=CompleteUsbReview,
    )
    _series_id(expected_series_id)
    _need(
        type(payloads) is dict
        and type(expected_sha256s) is dict
        and set(payloads) == set(expected_sha256s)
        and len(payloads) <= len(order)
        and set(payloads) == set(order[: len(payloads)]),
        "EXACT_COMPLETE_ROLE_PREFIX_REQUIRED",
    )
    subjects: dict[str, Any] = {}
    for role in order[: len(payloads)]:
        _need(type(payloads[role]) is bytes, "EXACT_COMPLETE_ROLE_BYTES_REQUIRED")
        qualification._sha(expected_sha256s[role])
        subject = classes[role](payloads[role])
        _need(
            subject.sha256 == expected_sha256s[role]
            and subject.to_dict()["series_id"] == expected_series_id,
            "COMPLETE_ROLE_REFERENCE_MISMATCH",
        )
        subjects[role] = subject
    if not subjects:
        return ()
    # The final reboot verifier includes all heterogeneous predecessor checks.
    # Only this call owns these local parts; subsequent calls reconstruct again.
    parts = _reconstruct(**originals)
    series = _series(expected_series_id, parts)
    _need(
        subjects["series"].payload == series.payload,
        "COMPLETE_SERIES_RECONSTRUCTION_MISMATCH",
    )
    if "assessment" in subjects:
        assessment = _assessment(series, parts)
        _need(
            subjects["assessment"].payload == assessment.payload,
            "COMPLETE_ASSESSMENT_RECONSTRUCTION_MISMATCH",
        )
    if "review" in subjects:
        d = subjects["review"].to_dict()
        review = _review_complete_usb_series(
            series,
            subjects["assessment"],
            parts=parts,
            **{
                key: d[key]
                for key in (
                    "reviewer_id",
                    "review_launch_id",
                    "reviewed_at_utc_ns",
                    "decision",
                )
            },
        )
        _need(
            subjects["review"].payload == review.payload,
            "COMPLETE_REVIEW_RECONSTRUCTION_MISMATCH",
        )
    return tuple(subjects[role] for role in order if role in subjects)
