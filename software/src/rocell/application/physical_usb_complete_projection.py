"""Bounded display consistency only; never original authentication or admission.

Full subjects stay in the original store/export. The UI receives small summaries
and must agree with its already-validated four phase projections. No I/O occurs.
"""

import re

from .physical_camera_usb_complete_constants import USB_COMPLETE_STATES
from .physical_usb_complete_series import (
    PHASES,
    PHASE_STATUS,
    ELIGIBLE,
    REVIEW_ELIGIBLE,
)

ASSESSMENT_FIELDS = (
    "verdict",
    "phases",
    "comparisons",
    "checks",
    "missing_requirements",
)
REVIEW_FIELDS = (
    "verdict",
    "decision",
    "reviewer_id",
    "review_launch_id",
    "reviewed_at_utc_ns",
    "assessment_sha256",
    "series_sha256",
)
ASSESS = "physical_usb_complete_assess"
REVIEW = "physical_usb_complete_review"
EXPORT = "physical_usb_identity_export"


def _exact(value, keys):
    return type(value) is dict and set(value) == set(keys)


def _digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def complete_projection_valid(outer, stages=None):
    """Fail closed on malformed summaries and contradictory publication/state.

    Call after validating the enclosing schema and historical phase projections.
    The optional stages are the current Setup snapshot, not a source of authority.
    """
    try:
        return _valid(outer, stages)
    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        IndexError,
        RecursionError,
    ):
        return False


def _valid(outer, stages):
    complete, publication = outer["complete"], outer["publication"]["status"]
    if publication == "PENDING":
        return (
            outer["status"] == "NOT_DECLARED"
            and outer["next_action"] is None
            and all(
                outer[k] is None
                for k in (
                    "plan",
                    "baseline",
                    "absence",
                    "reconnect",
                    "reboot",
                    "complete",
                )
            )
        )
    phase_rows = [
        outer[key]["phase_record"]
        for key in ("baseline", "absence", "reconnect", "reboot")
    ]
    if (
        outer["plan"] is None
        or any(type(row) is not dict for row in phase_rows)
        or outer["reboot"]["state"] != "RETAINED_BLOCKED"
    ):
        return False
    # The legacy baseline display intentionally has no status field. Derive
    # the codec's status from its already-validated checks without extending
    # or mutating that older projection schema.
    phase_rows[0] = dict(
        phase_rows[0],
        status=(
            PHASE_STATUS[0]
            if all(c["passed"] for c in phase_rows[0]["checks"])
            else "HELD"
        ),
    )
    state = "COMPLETE_REVIEW_READY" if complete is None else complete["state"]
    if publication == "CURRENT" and outer["status"] != state:
        return False
    if publication != "CURRENT" and outer["next_action"] not in (None, EXPORT):
        return False
    allowed = {None, EXPORT}
    if complete is None:
        allowed.add(ASSESS)
    else:
        if (
            not _exact(
                complete,
                (
                    "series_id",
                    "state",
                    "series_sha256",
                    "assessment_sha256",
                    "review_sha256",
                    "assessment",
                    "review",
                ),
            )
            or type(complete["series_id"]) is not str
            or re.fullmatch(r"usbseries-[0-9a-f]{32}", complete["series_id"]) is None
            or state not in USB_COMPLETE_STATES
        ):
            return False
        if any(
            complete[k] is not None and not _digest(complete[k])
            for k in ("series_sha256", "assessment_sha256", "review_sha256")
        ):
            return False
        a, r = complete["assessment"], complete["review"]
        if (a is None) != (complete["assessment_sha256"] is None) or (r is None) != (
            complete["review_sha256"] is None
        ):
            return False
        if (a is not None and complete["series_sha256"] is None) or (
            r is not None and a is None
        ):
            return False
        if state == "ASSESSMENT_REQUESTED" and complete["series_sha256"] is not None:
            return False
        if state == "REVIEW_PENDING":
            if a is None or r is not None:
                return False
            allowed.add(REVIEW)
        if state in ("REVIEWED_PASS", "REVIEWED_BLOCKED") and r is None:
            return False
        if a is not None:
            expected_checks = [
                dict(check_id="PHYSICAL_PLAN", passed=True),
                dict(
                    check_id="BASELINE_PHYSICAL_OWNED_BOOT",
                    passed=outer["baseline"]["host_boot"]["original_state"]
                    == "BOOT_RETAINED",
                ),
                *(
                    dict(check_id=name + "_COMPLETE", passed=row["status"] == status)
                    for name, row, status in zip(PHASES, phase_rows, PHASE_STATUS)
                ),
                *(
                    dict(
                        check_id=name + "__" + check["check_id"], passed=check["passed"]
                    )
                    for name, row in zip(PHASES, phase_rows)
                    for check in row["checks"]
                ),
            ]
            phases = [
                dict(
                    phase=name,
                    phase_sha256=row["phase_sha256"],
                    status=row["status"],
                    missing_checks=[
                        c["check_id"] for c in row["checks"] if not c["passed"]
                    ],
                )
                for name, row in zip(PHASES, phase_rows)
            ]
            missing = [c["check_id"] for c in expected_checks if not c["passed"]]
            comparisons = [
                {k: row[k] for k in ("field", "status")}
                for row in phase_rows[-1]["comparisons"]
            ]
            if (
                not _exact(a, ASSESSMENT_FIELDS)
                or type(a["checks"]) is not list
                or any(
                    not _exact(c, ("check_id", "passed"))
                    or type(c["passed"]) is not bool
                    for c in a["checks"]
                )
                or a
                != dict(
                    verdict="BLOCKED" if missing else ELIGIBLE,
                    phases=phases,
                    comparisons=comparisons,
                    checks=expected_checks,
                    missing_requirements=missing,
                )
            ):
                return False
        if r is not None:
            if (
                not _exact(r, REVIEW_FIELDS)
                or r["decision"] not in ("REJECT", "ACKNOWLEDGE_EXACT")
                or type(r["reviewer_id"]) is not str
                or re.fullmatch(r"[\x20-\x7e]{1,64}", r["reviewer_id"]) is None
                or r["reviewer_id"].strip() != r["reviewer_id"]
                or type(r["review_launch_id"]) is not str
                or re.fullmatch(r"wizard-[0-9a-f]{32}", r["review_launch_id"]) is None
                or type(r["reviewed_at_utc_ns"]) is not int
                or r["reviewed_at_utc_ns"] < 1
            ):
                return False
            eligible = r["decision"] == "ACKNOWLEDGE_EXACT" and a["verdict"] == ELIGIBLE
            if (
                r["series_sha256"] != complete["series_sha256"]
                or r["assessment_sha256"] != complete["assessment_sha256"]
                or r["verdict"] != (REVIEW_ELIGIBLE if eligible else "BLOCKED")
            ):
                return False
            if state.startswith("REVIEWED_") and state != (
                "REVIEWED_PASS" if eligible else "REVIEWED_BLOCKED"
            ):
                return False
    if outer["next_action"] not in allowed:
        return False
    if publication == "CURRENT" and stages is not None:
        expected = {
            "COMPLETE_REVIEW_READY": "BLOCKED",
            "ASSESSMENT_REQUESTED": "WAITING_OPERATOR",
            "REVIEW_PENDING": "REVIEW_PENDING",
            "REVIEWED_PASS": "PASS",
            "REVIEWED_BLOCKED": "BLOCKED",
            "INCOMPLETE": None,
        }[state]
        actual = stages[3]["state"]
        if (
            actual != expected
            if expected
            else actual not in ("WAITING_OPERATOR", "REVIEW_PENDING")
        ):
            return False
        # No later stage is unlocked by this identity-only suffix.
        if any(row["state"] != "PENDING" for row in stages[4:]):
            return False
    return True
