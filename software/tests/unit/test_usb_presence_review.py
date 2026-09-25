"""Actual pure review/binding codecs over explicitly modeled physical subjects.

Fixture prerequisites come from existing file fixtures. Review construction,
parsing and reconstruction perform no filesystem/native/device/process action.
No modeled baseline, label or reference constitutes original-store approval.
"""

from dataclasses import FrozenInstanceError
import builtins
import io
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from rocell.application.physical_usb_presence_binding import (
    UsbPresencePhaseBinding,
    build_usb_presence_phase_binding,
)
from rocell.application.usb_presence_stage_policy import usb_presence_stage_policy
from rocell.application.usb_identity_stage_policy import usb_identity_stage_policy
from rocell.providers.windows import usb_presence_review as m
from rocell.providers.windows import usb_presence_registration as registration
from rocell.providers.windows import host_boot_observation as host
from rocell.providers.windows.usb_identity_registration import (
    usb_identity_runtime_candidate,
)
from test_physical_usb_presence_binding import presence_fixture
from test_physical_received_camera import prerequisites, workspace


WORKSPACE = Path(__file__).resolve().parents[3]
OPERATION = "e" * 64
_CASE_CACHE = None


@pytest.fixture(autouse=True)
def no_process_or_observation(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Pure review must not acquire observations or create processes")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(os, "system", denied)
    monkeypatch.setattr(host, "_system_powershell", denied)
    monkeypatch.setattr(host, "_native_owner", denied)
    monkeypatch.setattr(registration, "inspect_usb_presence_runtime", denied)


def review_fixture(prerequisites, *, incapable=False, **changes):
    """No owner/campaign: physical baseline records and references are MODELED."""
    original = presence_fixture(prerequisites)
    phase = build_usb_presence_phase_binding(**original)
    builder = (
        registration.incapable_usb_presence_runtime_candidate
        if incapable
        else registration.usb_presence_runtime_candidate
    )
    runtime = builder(
        WORKSPACE, source_sha256=phase.to_dict()["binding"]["source_sha256"]
    )
    args = dict(
        phase_binding=phase,
        policy=usb_presence_stage_policy(),
        operation_sha256=OPERATION,
        operator_id="Bench Tech_A",
        reviewer_id="Review Tech_B",
        launch_session_id="wizard-presence-review",
        reviewed_at_ns=phase.to_dict()["not_before_utc_ns"] + 1,
    )
    args.update(changes)
    review = m.review_usb_presence_runtime(runtime, **args)
    return SimpleNamespace(
        original=original, phase=phase, runtime=runtime, args=args, review=review
    )


@pytest.fixture
def case(request):
    # Build the expensive original baseline codec chain once. Every malformed
    # case receives newly parsed immutable review/runtime/phase objects and a
    # detached argument dict; no original store or observation is reacquired.
    global _CASE_CACHE
    if _CASE_CACHE is None:
        _CASE_CACHE = review_fixture(request.getfixturevalue("prerequisites"))
    cached = _CASE_CACHE
    phase = UsbPresencePhaseBinding(cached.phase.payload)
    return SimpleNamespace(
        original=cached.original,
        phase=phase,
        runtime=type(cached.runtime)(cached.runtime.payload),
        args={**cached.args, "phase_binding": phase},
        review=m.UsbPresenceRuntimeReview(cached.review.payload),
    )


def verify(case, value=None, *, expected=None, **changes):
    args = dict(
        runtime=case.runtime,
        phase_binding=case.phase,
        policy=case.args["policy"],
        operation_sha256=OPERATION,
        expected_review_sha256=case.review.sha256 if expected is None else expected,
    )
    args.update(changes)
    return m.verify_usb_presence_runtime_review(
        case.review if value is None else value, **args
    )


@pytest.mark.parametrize("incapable", [False, True])
def test_actual_pure_producer_derives_exact_review_subjects_and_is_detached(
    prerequisites, incapable
):
    case = review_fixture(prerequisites, incapable=incapable)
    value = case.review.to_dict()
    phase, runtime = case.phase.to_dict(), case.runtime.to_dict()
    assert len(case.review.payload) <= m.MAX_REVIEW_BYTES == 8192
    assert value["schema"] == "rocell.usb_presence_runtime_review.v1"
    assert value["decision"] == "ACKNOWLEDGE_EXACT_USB_PRESENCE_POLICY_AND_RUNTIME"
    for key in ("source_sha256", "cell_id", "session_id", "header_sha256", "trial_id"):
        assert value[key] == phase["binding"][key]
    assert value["phase_binding_sha256"] == case.phase.sha256
    assert (
        value["target_instance_id_sha256"]
        == phase["target"]["physical_usb_instance_id_sha256"]
    )
    assert value["helper_sha256"] == runtime["helper"]["sha256"]
    assert value["runtime_registration_sha256"] == case.runtime.sha256
    assert value["usb_presence_policy_sha256"] == case.args["policy"].sha256
    assert value["operation_sha256"] == OPERATION
    assert value["distinct_operator_labels"] is True
    assert all(value[key] is False for key in m._FALSE_FLAGS)
    assert value["operator_id"] == "Bench Tech_A"
    assert value["reviewer_id"] == "Review Tech_B"
    assert "permit_sha256" not in value and "request_sha256" not in value
    for supplied in (case.review, case.review.payload):
        rebuilt = verify(case, supplied)
        assert rebuilt == case.review and rebuilt is not case.review
    value["operator_id"] = "changed"
    assert case.review.to_dict()["operator_id"] == "Bench Tech_A"
    with pytest.raises(FrozenInstanceError):
        case.review.payload = b"{}"


def test_review_build_restore_and_verify_do_not_read_files_or_inspect_runtime(
    case, monkeypatch
):
    original_phase_bytes = case.phase.payload
    original_runtime_bytes = case.runtime.payload

    def denied(*args, **kwargs):
        pytest.fail("Pure review path touched filesystem or source inspection")

    with monkeypatch.context() as patch:
        for owner, name in (
            (builtins, "open"),
            (io, "open"),
            (Path, "open"),
            (Path, "read_bytes"),
            (Path, "stat"),
            (registration, "source_fingerprint"),
            (registration, "inspect_usb_presence_runtime"),
        ):
            patch.setattr(owner, name, denied)
        made = m.review_usb_presence_runtime(case.runtime, **case.args)
        restored = m.UsbPresenceRuntimeReview(made.payload)
        assert verify(case, restored).payload == case.review.payload
        assert restored.to_dict()["hardware_qualified"] is False
    assert case.phase.payload == original_phase_bytes
    assert case.runtime.payload == original_runtime_bytes


@pytest.mark.parametrize("key", sorted(m._FIELDS))
def test_every_review_field_is_required(case, key):
    document = case.review.to_dict()
    del document[key]
    with pytest.raises(m.UsbPresenceReviewError):
        m.UsbPresenceRuntimeReview(m.canonical(document))


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema", "rocell.usb_identity_runtime_review.v1"),
        ("phase", "BASELINE"),
        ("decision", "PASS"),
        ("distinct_operator_labels", 1),
        ("distinct_operator_labels", False),
        *((key, val) for key in m._FALSE_FLAGS for val in (0, True)),
        ("cell_id", "arbitrary-cell"),
        ("session_id", "wizard-new-launch"),
        ("trial_id", "usbidentity-" + "1" * 32),
        ("launch_session_id", "x" * 129),
        ("launch_session_id", "launch\n"),
        ("reviewed_at_ns", True),
        ("reviewed_at_ns", 0),
        ("reviewed_at_ns", -1),
        ("reviewed_at_ns", 2**63),
        ("reviewed_at_ns", 1.0),
    ],
)
def test_closed_review_grammar_and_flags_cannot_be_rehashed_into_approval(
    case, key, value
):
    document = case.review.to_dict()
    document[key] = value
    with pytest.raises(m.UsbPresenceReviewError):
        m.UsbPresenceRuntimeReview(m.canonical(document))


@pytest.mark.parametrize("key", sorted(m._HASH_FIELDS))
@pytest.mark.parametrize("bad", [True, None, "0" * 64, "8" * 63, "E" * 64])
def test_all_subject_hashes_are_nonzero_closed_sha256(case, key, bad):
    document = case.review.to_dict()
    document[key] = bad
    with pytest.raises(m.UsbPresenceReviewError):
        m.UsbPresenceRuntimeReview(m.canonical(document))


@pytest.mark.parametrize("key", sorted(m._HASH_FIELDS - {"usb_presence_policy_sha256"}))
def test_rehashed_valid_digest_substitution_fails_exact_subject_reconstruction(
    case, key
):
    document = case.review.to_dict()
    document[key] = "8" * 64
    payload = m.canonical(document)
    # Structural parsing is deliberately separate from binding/original trust.
    m.UsbPresenceRuntimeReview(payload)
    with pytest.raises(m.UsbPresenceReviewError, match="RECONSTRUCTION"):
        verify(case, payload, expected=m.digest(payload))


@pytest.mark.parametrize(
    "key,bad",
    [
        ("cell_id", "wizard-physical-camera-" + "8" * 16),
        ("session_id", "physical-camera-" + "8" * 32),
        ("trial_id", "usbtrial-" + "8" * 32),
    ],
)
def test_valid_but_other_original_context_is_not_the_reviewed_phase(case, key, bad):
    document = case.review.to_dict()
    document[key] = bad
    payload = m.canonical(document)
    with pytest.raises(m.UsbPresenceReviewError, match="RECONSTRUCTION"):
        verify(case, payload, expected=m.digest(payload))


@pytest.mark.parametrize(
    "key,bad",
    [
        ("operator_id", "Someone Else"),
        ("reviewer_id", "New Reviewer"),
        ("launch_session_id", "wizard-other"),
        ("reviewed_at_ns", 2**63 - 1),
    ],
)
def test_original_expected_hash_also_binds_explicit_actor_launch_and_time(
    case, key, bad
):
    document = case.review.to_dict()
    document[key] = bad
    with pytest.raises(m.UsbPresenceReviewError, match="ORIGINAL_REVIEW_HASH_MISMATCH"):
        verify(case, m.canonical(document))


@pytest.mark.parametrize("key", ["operator_id", "reviewer_id"])
@pytest.mark.parametrize(
    "bad", ["", " a", "a ", "a\n", "a\x7f", "é", "a" * 65, True, None]
)
def test_explicit_actor_labels_are_portable_bounded_and_never_normalized(
    case, key, bad
):
    args = {**case.args, key: bad}
    with pytest.raises(m.UsbPresenceReviewError):
        m.review_usb_presence_runtime(case.runtime, **args)


def test_casefold_distinct_labels_are_a_procedure_not_authenticated_people(case):
    with pytest.raises(
        m.UsbPresenceReviewError, match="DISTINCT_REVIEW_LABELS_REQUIRED"
    ):
        m.review_usb_presence_runtime(
            case.runtime, **{**case.args, "reviewer_id": "BENCH TECH_A"}
        )
    review = m.review_usb_presence_runtime(
        case.runtime, **{**case.args, "operator_id": "A" * 64, "reviewer_id": "B" * 64}
    )
    assert review.to_dict()["authenticated_independent_people"] is False


@pytest.mark.parametrize("bad", [True, 0, -1, 2**63, 1.0])
def test_builder_refuses_invalid_or_prebaseline_review_time(case, bad):
    with pytest.raises(m.UsbPresenceReviewError):
        m.review_usb_presence_runtime(
            case.runtime, **{**case.args, "reviewed_at_ns": bad}
        )


def test_review_time_cannot_precede_bound_baseline_and_boundary_is_exact(case):
    at = case.phase.to_dict()["not_before_utc_ns"]
    with pytest.raises(m.UsbPresenceReviewError, match="AFTER_ORIGINAL_BASELINE"):
        m.review_usb_presence_runtime(
            case.runtime, **{**case.args, "reviewed_at_ns": at - 1}
        )
    value = m.review_usb_presence_runtime(
        case.runtime, **{**case.args, "reviewed_at_ns": at}
    )
    assert value.to_dict()["reviewed_at_ns"] == at


def test_descriptor_query_policy_and_runtime_are_not_presence_review(case):
    with pytest.raises(
        m.UsbPresenceReviewError, match="EXACT_PRESENCE_REVIEW_SUBJECTS"
    ):
        m.review_usb_presence_runtime(
            case.runtime, **{**case.args, "policy": usb_identity_stage_policy()}
        )
    query_runtime = usb_identity_runtime_candidate(
        WORKSPACE, source_sha256=case.review.to_dict()["source_sha256"]
    )
    with pytest.raises(
        m.UsbPresenceReviewError, match="EXACT_PRESENCE_REVIEW_SUBJECTS"
    ):
        m.review_usb_presence_runtime(query_runtime, **case.args)
    document = case.review.to_dict()
    document["usb_presence_policy_sha256"] = usb_identity_stage_policy().sha256
    with pytest.raises(m.UsbPresenceReviewError, match="FIXED_PRESENCE_POLICY"):
        m.UsbPresenceRuntimeReview(m.canonical(document))


def test_changed_runtime_source_or_incapable_runtime_needs_its_own_review(case):
    changed = registration.usb_presence_runtime_candidate(
        WORKSPACE, source_sha256="8" * 64
    )
    with pytest.raises(m.UsbPresenceReviewError, match="SOURCE_MISMATCH"):
        m.review_usb_presence_runtime(changed, **case.args)
    incapable = registration.incapable_usb_presence_runtime_candidate(
        WORKSPACE, source_sha256=case.review.to_dict()["source_sha256"]
    )
    with pytest.raises(m.UsbPresenceReviewError, match="RECONSTRUCTION"):
        verify(case, runtime=incapable)


def test_operation_is_pre_review_and_explicitly_crosschecked(case):
    with pytest.raises(m.UsbPresenceReviewError, match="RECONSTRUCTION"):
        verify(case, operation_sha256="8" * 64)
    with pytest.raises(m.UsbPresenceReviewError, match="ORIGINAL_REVIEW_HASH_MISMATCH"):
        verify(case, expected="8" * 64)
    assert case.args["operation_sha256"] == OPERATION
    assert case.phase.sha256 == case.review.to_dict()["phase_binding_sha256"]


@pytest.mark.parametrize(
    "variant",
    ["extra", "duplicate", "whitespace", "oversized", "not-bytes", "nonfinite"],
)
def test_raw_parser_rejects_extra_duplicate_noncanonical_or_oversized_json(
    case, variant
):
    raw = case.review.payload
    if variant == "extra":
        raw = m.canonical({**case.review.to_dict(), "approved": True})
    elif variant == "duplicate":
        raw = raw[:-1] + b',"schema":"rocell.usb_presence_runtime_review.v1"}'
    elif variant == "whitespace":
        raw = raw + b"\n"
    elif variant == "oversized":
        raw = b" " * m.MAX_REVIEW_BYTES + raw
    elif variant == "not-bytes":
        raw = bytearray(raw)
    else:
        data = case.review.to_dict()
        data["reviewed_at_ns"] = float("nan")
        raw = json.dumps(data).encode()
    with pytest.raises(m.UsbPresenceReviewError):
        m.UsbPresenceRuntimeReview(raw)


def test_verifier_rejects_untyped_or_forged_subjects(case):
    with pytest.raises(m.UsbPresenceReviewError, match="EXACT_REVIEW_BYTES_OR_TYPE"):
        verify(case, case.review.to_dict())
    with pytest.raises(m.UsbPresenceReviewError):
        verify(case, phase_binding=case.phase.to_dict())
    runtime = type(case.runtime)(case.runtime.payload)
    document = runtime.to_dict()
    document["helper"]["sha256"] = "8" * 64
    object.__setattr__(runtime, "payload", m.canonical(document))
    with pytest.raises(m.UsbPresenceReviewError):
        verify(case, runtime=runtime)
    review = m.UsbPresenceRuntimeReview(case.review.payload)
    object.__setattr__(review, "payload", b"{}")
    with pytest.raises(m.UsbPresenceReviewError):
        verify(case, review)


def test_review_cannot_accept_subclass_or_dictionary_phase(case):
    class NotExactPhase(UsbPresencePhaseBinding):
        pass

    for invalid in (case.phase.to_dict(), NotExactPhase(case.phase.payload)):
        with pytest.raises(
            m.UsbPresenceReviewError, match="EXACT_PRESENCE_REVIEW_SUBJECTS"
        ):
            m.review_usb_presence_runtime(
                case.runtime, **{**case.args, "phase_binding": invalid}
            )
