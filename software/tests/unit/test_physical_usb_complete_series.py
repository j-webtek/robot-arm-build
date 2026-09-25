"""Pure complete-series codecs over explicitly modeled received/USB/boot bytes.

No original M1 store or physical observer is exercised. These tests reconstruct
the real heterogeneous codecs; passing them is not application admission.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest


from rocell.application import physical_usb_complete_series as m

from test_physical_usb_reboot_phase import (  # noqa: E402
    subject,
    predecessor,
    prerequisites,
    workspace,
    no_process_or_device,
    reboot_fixture,
    build,
    _PREDECESSOR_KEYS,
    reference,
)


SERIES_ID = "usbseries-" + "8" * 32


def inputs(case):
    phase = build(case)
    return dict(
        predecessor={key: getattr(case, key) for key in _PREDECESSOR_KEYS},
        reboot_payload=phase.payload,
        reboot_reference=reference(phase.payload, "MODELED-complete-reboot-original"),
        reboot_permit=case.permit,
        reboot_sources=case.sources,
        reboot_references=case.references,
    )


def series_and_assessment(args):
    series = m.build_complete_usb_series(series_id=SERIES_ID, **args)
    return series, m.assess_complete_usb_series(series, **args)


def review(case, series, assessment, args, **changes):
    values = dict(
        reviewer_id="MODELED-independent-complete-reviewer",
        review_launch_id="wizard-MODELED-complete-review",
        reviewed_at_utc_ns=case.context["finished_at_utc_ns"] + 1,
        decision="ACKNOWLEDGE_EXACT",
    )
    values.update(changes)
    return m.review_complete_usb_series(series, assessment, **values, **args)


def test_exact_heterogeneous_chain_and_review_have_no_authority(subject, monkeypatch):
    args = inputs(subject)
    original = deepcopy(args)

    def denied(*args, **kwargs):
        pytest.fail("Pure complete-series codec opened a file")

    monkeypatch.setattr(Path, "open", denied)
    monkeypatch.setattr(Path, "read_bytes", denied)
    monkeypatch.setattr(Path, "read_text", denied)
    series, assessment = series_and_assessment(args)
    reviewed = review(subject, series, assessment, args)
    assert [r["role"] for r in series.to_dict()["phases"]] == list(m.PHASES)
    assert assessment.to_dict()["verdict"] == m.ELIGIBLE
    assert assessment.to_dict()["missing_requirements"] == []
    assert all(
        row["status"] == "MATCHED" for row in assessment.to_dict()["comparisons"]
    )
    assert reviewed.to_dict()["verdict"] == m.REVIEW_ELIGIBLE
    assert (
        m.verify_complete_usb_series(series, expected_sha256=series.sha256, **args)
        == series
    )
    assert (
        m.verify_complete_usb_assessment(
            assessment, series=series, expected_sha256=assessment.sha256, **args
        )
        == assessment
    )
    assert (
        m.verify_complete_usb_review(
            reviewed,
            series=series,
            assessment=assessment,
            expected_sha256=reviewed.sha256,
            **args
        )
        == reviewed
    )
    assert args == original
    for obj in (series, assessment, reviewed):
        assert len(obj.payload) <= m.LIMITS[obj.role]
        assert all(obj.to_dict()[key] is False for key in m.FLAGS)
        with pytest.raises(FrozenInstanceError):
            obj.payload = b"{}"
        detached = obj.to_dict()
        detached["physical_authority"] = True
        assert obj.to_dict()["physical_authority"] is False


@pytest.mark.parametrize(
    "changes,missing",
    [
        ({"operating_usb3": False}, "V2_OPERATING_USB3_OBSERVED"),
        ({"serial": "MODELED-DIFFERENT-UNIT"}, "RECEIVED_SERIAL_MATCH"),
        (
            {"driver_version": "9.9.9.9"},
            "BASELINE_AND_RECONNECT_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY",
        ),
        ({"epoch": "same_boot"}, "SAME_HOST_DIFFERENT_BOOT_AS_RECONNECT"),
        ({"epoch": "after_begin"}, "REBOOT_EPOCH_AFTER_RECONNECT_BEFORE_BEGIN"),
        ({"host_change": True}, "SAME_HOST_DIFFERENT_BOOT_AS_RECONNECT"),
        ({"boot_origin": "INJECTED_CIM_EXECUTOR"}, "HOST_BOOT_PHYSICAL_OWNED_CLEAN"),
        ({"boot_cleanup_uncertain": True}, "HOST_BOOT_PHYSICAL_OWNED_CLEAN"),
    ],
)
def test_negative_or_unknown_observation_stays_blocked_after_acknowledgment(
    predecessor, changes, missing
):
    case = reboot_fixture(predecessor, **changes)
    args = inputs(case)
    series, assessment = series_and_assessment(args)
    d = assessment.to_dict()
    assert d["verdict"] == "BLOCKED"
    assert "AFTER_REBOOT__" + missing in d["missing_requirements"]
    assert d["phases"][-1]["status"] == "HELD"
    assert review(case, series, assessment, args).to_dict()["verdict"] == "BLOCKED"


def test_reviewer_rejection_is_not_overridden_by_matching_observations(subject):
    args = inputs(subject)
    series, assessment = series_and_assessment(args)
    assert assessment.to_dict()["verdict"] == m.ELIGIBLE
    assert (
        review(subject, series, assessment, args, decision="REJECT").to_dict()[
            "verdict"
        ]
        == "BLOCKED"
    )


def test_reviewer_label_and_time_are_bound_to_original_actors_and_completion(subject):
    args = inputs(subject)
    series, assessment = series_and_assessment(args)
    labels = [subject.original_baseline["plan"].to_dict()["operator_id"]] + [
        phase.to_dict()["context"]["operator_id"]
        for phase in (
            subject.original_baseline["baseline"],
            subject.absence,
            subject.reconnect,
            m.reboot.UsbRebootQualificationPhase(args["reboot_payload"]),
        )
    ]
    for label in labels:
        with pytest.raises(m.CompleteUsbSeriesError, match="DISTINCT"):
            review(subject, series, assessment, args, reviewer_id=label.upper())
    for changes in (
        {"reviewed_at_utc_ns": True},
        {"reviewed_at_utc_ns": subject.context["finished_at_utc_ns"] - 1},
        {"review_launch_id": "not a launch"},
        {"decision": "OVERRIDE"},
    ):
        with pytest.raises(ValueError):
            review(subject, series, assessment, args, **changes)


@pytest.mark.parametrize(
    "fault",
    [
        "missing-predecessor",
        "wrong-permit",
        "changed-payload",
        "wrong-reference-stage",
        "alias-reference",
        "wrong-source",
    ],
)
def test_independent_inputs_cannot_be_swapped_or_invented(subject, fault):
    args = inputs(subject)
    if fault == "missing-predecessor":
        del args["predecessor"]["received"]
    elif fault == "wrong-permit":
        args["predecessor"]["reconnect_permit"] = subject.permit
    elif fault == "changed-payload":
        args["reboot_payload"] += b" "
    elif fault == "wrong-reference-stage":
        args["reboot_reference"] = replace(
            args["reboot_reference"],
            stage=m.qualification.PhysicalOnboardingStage.WORKSPACE_SOURCES,
        )
    elif fault == "alias-reference":
        old = subject.original_baseline["baseline_reference"]
        args["reboot_reference"] = replace(
            args["reboot_reference"],
            evidence_id=old.evidence_id,
            package_sha256=old.package_sha256,
        )
    else:
        args["reboot_sources"] = dict(
            subject.sources, host_boot=subject.reconnect_sources["host_boot"]
        )
    with pytest.raises(ValueError):
        m.build_complete_usb_series(series_id=SERIES_ID, **args)


def test_legacy_series_is_not_relabelled_to_complete_physical_absence(subject):
    args = inputs(subject)
    old = subject.original_baseline
    legacy = m.qualification.build_usb_qualification_series(
        old["plan"], phases=[old["baseline"]], references=[old["baseline_reference"]]
    )
    with pytest.raises(ValueError):
        m.assess_complete_usb_series(legacy.payload, **args)
    assert legacy.to_dict()["schema"] == "rocell.usb_qualification_series.v1"


def test_rehashed_success_claim_does_not_replace_original_reconstruction(predecessor):
    case = reboot_fixture(predecessor, driver_version="9.9.9.9")
    args = inputs(case)
    series, assessment = series_and_assessment(args)
    forged = assessment.to_dict()
    forged["verdict"], forged["missing_requirements"] = m.ELIGIBLE, []
    for row in forged["checks"]:
        row["passed"] = True
    for row in forged["phases"]:
        row["missing_checks"] = []
        row["status"] = m.PHASE_STATUS[m.PHASES.index(row["phase"])]
    for row in forged["comparisons"]:
        row["status"] = "MATCHED"
    raw = m.canonical(forged)
    m.CompleteUsbAssessment(raw)  # Syntax alone is not independently checked fact.
    with pytest.raises(m.CompleteUsbSeriesError, match="RECONSTRUCTION_MISMATCH"):
        m.verify_complete_usb_assessment(
            raw, series=series, expected_sha256=m.digest(raw), **args
        )


@pytest.mark.parametrize("role", ["series", "assessment", "review"])
def test_wire_types_flags_unknown_fields_and_byte_limits_are_closed(subject, role):
    args = inputs(subject)
    series, assessment = series_and_assessment(args)
    reviewed = review(subject, series, assessment, args)
    obj = {"series": series, "assessment": assessment, "review": reviewed}[role]
    for key, value in (
        ("unknown", None),
        ("schema", "legacy"),
        ("physical_authority", True),
        ("hardware_qualified", 0),
        ("series_id", True),
    ):
        bad = obj.to_dict()
        bad[key] = value
        with pytest.raises(ValueError):
            type(obj)(m.canonical(bad))
    with pytest.raises(ValueError):
        type(obj)(b" " * (m.LIMITS[role] + 1))
    with pytest.raises(ValueError):
        type(obj)(bytearray(obj.payload))


def test_series_cannot_change_phase_order_or_expected_hash(subject):
    args = inputs(subject)
    series, _ = series_and_assessment(args)
    wrong = series.to_dict()
    wrong["phases"][1:3] = list(reversed(wrong["phases"][1:3]))
    with pytest.raises(ValueError):
        m.CompleteUsbSeries(m.canonical(wrong))
    with pytest.raises(ValueError):
        m.verify_complete_usb_series(series, expected_sha256="f" * 64, **args)
    with pytest.raises(TypeError):
        m.build_complete_usb_series(series_id=SERIES_ID, passed=True, **args)


def test_maximal_closed_wire_summaries_fit_their_own_caps(subject):
    """Bound schema capacity, not authentication of these altered model bytes."""
    args = inputs(subject)
    series, assessment = series_and_assessment(args)
    reviewed = review(subject, series, assessment, args)
    for obj in (series, assessment, reviewed):
        d = obj.to_dict()
        for key in d["binding"]:
            if not key.endswith("sha256"):
                d["binding"][key] = "M" * 128
        if obj.role == "series":
            for row in d["phases"]:
                row["payload_bytes"] = m.PHASE_LIMITS[row["role"]]
                row["reference"]["payload_bytes"] = row["payload_bytes"]
        elif obj.role == "assessment":
            d["verdict"] = "BLOCKED"
            for row in d["checks"]:
                row["passed"] = False
            d["missing_requirements"] = list(m.CHECK_IDS)
            for index, row in enumerate(d["phases"]):
                row["status"] = "HELD"
                row["missing_checks"] = list(m.PHASE_CHECKS[index])
            for row in d["comparisons"]:
                row["status"] = "NOT_OBSERVED"
        else:
            d["review_launch_id"] = "M" * 128
            d["reviewer_id"] = "M" * 64
            d["reviewed_at_utc_ns"] = 2**63 - 1
        raw = m.canonical(d)
        assert len(raw) <= m.LIMITS[obj.role]
        assert type(obj)(raw).payload == raw


def test_original_role_chain_reconstructs_once_and_never_caches(subject, monkeypatch):
    """The bulk reader must not repeat the full predecessor for every role."""
    args = inputs(subject)
    series, assessment = series_and_assessment(args)
    reviewed = review(subject, series, assessment, args)
    payloads = dict(
        series=series.payload, assessment=assessment.payload, review=reviewed.payload
    )
    hashes = {role: m.digest(raw) for role, raw in payloads.items()}
    calls = []
    actual = m._reconstruct

    def reconstruct(**originals):
        calls.append("fresh-full-chain")
        return actual(**originals)

    monkeypatch.setattr(m, "_reconstruct", reconstruct)
    for expected_count in (1, 2):
        result = m.verify_complete_usb_subject_chain(
            payloads, expected_sha256s=hashes, expected_series_id=SERIES_ID, **args
        )
        assert result == (series, assessment, reviewed)
        assert len(calls) == expected_count
    # A changed independently supplied original is noticed on the next call.
    changed = dict(args, reboot_payload=args["reboot_payload"] + b" ")
    with pytest.raises(ValueError):
        m.verify_complete_usb_subject_chain(
            payloads, expected_sha256s=hashes, expected_series_id=SERIES_ID, **changed
        )
    assert len(calls) == 3


@pytest.mark.parametrize("count", [1, 2])
def test_original_role_chain_accepts_only_exact_partial_subjects(subject, count):
    args = inputs(subject)
    series, assessment = series_and_assessment(args)
    objects = (series, assessment)[:count]
    payloads = {obj.role: obj.payload for obj in objects}
    hashes = {obj.role: obj.sha256 for obj in objects}
    result = m.verify_complete_usb_subject_chain(
        payloads, expected_sha256s=hashes, expected_series_id=SERIES_ID, **args
    )
    assert result == objects


def test_original_role_chain_rejects_role_and_digest_substitution_without_reconstruction(
    monkeypatch,
):
    def denied(**originals):
        pytest.fail("invalid role prefix reached predecessor reconstruction")

    monkeypatch.setattr(m, "_reconstruct", denied)
    assert (
        m.verify_complete_usb_subject_chain(
            {}, expected_sha256s={}, expected_series_id=SERIES_ID
        )
        == ()
    )
    for payloads, hashes in (
        ({"review": b"{}"}, {"review": "a" * 64}),
        ({"series": b"{}"}, {}),
        ({"series": bytearray(b"{}")}, {"series": "a" * 64}),
        ({"unknown": b"{}"}, {"unknown": "a" * 64}),
        ({"series": b"{}"}, {"series": True}),
    ):
        with pytest.raises(ValueError):
            m.verify_complete_usb_subject_chain(
                payloads, expected_sha256s=hashes, expected_series_id=SERIES_ID
            )
