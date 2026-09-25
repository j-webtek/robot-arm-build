"""Actual design bytes; explicitly modeled source admission, no devices/M1."""

from contextlib import contextmanager
from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path
from threading import Event
import time

import pytest

from rocell.application import physical_static_contract as module
from rocell.workcell import camera_architecture, static_camera_support

from test_physical_static_contract_readback import (
    WORKSPACE,
    actual_static_subjects,
    static_ready,
)
from test_physical_source_qualification_readback import source_model
from test_physical_camera_intake_session import intake_model
from test_physical_camera_session_readback import model, no_devices, workspace


@pytest.fixture
def actual(static_ready, monkeypatch):
    return static_ready, actual_static_subjects(static_ready, monkeypatch)


def verify(actual, **changes):
    (owner, prerequisites, state), records = actual
    receipt = records["receipt"]
    values = dict(
        prerequisites=prerequisites,
        source_qualification=state["qualified_sources"]["receipt"],
        expected_binding=receipt.to_dict()["binding"],
        expected_receipt_sha256=receipt.sha256,
    )
    values.update(changes)
    return module.verify_static_camera_contract_receipt(receipt, **values)


def collect_again(actual, **changes):
    _, records = actual
    options = dict(
        binding=records["receipt"].to_dict()["binding"],
        source_qualification=actual[0][2]["qualified_sources"]["receipt"],
        cancellation=Event(),
        progress=lambda _: None,
        deadline_ns=time.monotonic_ns() + module.MAX_COLLECTION_DURATION_NS,
    )
    options.update(changes)
    return module.collect_static_camera_contract(WORKSPACE, **options)


def blocked_receipt(receipt):
    """Real strict parsed design with a modeled original-source mismatch.

    Only original support bytes change (whitespace); its four source locks and
    validation remain real. Derive checks afresh, never write a passed boolean.
    A live source-fingerprint check would independently refuse this drift.
    """
    data = receipt.to_dict()
    row = next(
        row
        for row in data["source_files"]
        if row["relative_path"] == module.SUPPORT_PATH
    )
    row["utf8"] += "\n"
    raw = row["utf8"].encode("utf-8")
    row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    data.update(module._derived(data["source_files"], data["software_receipt"]))
    return module.StaticCameraContractReceipt(module._canonical(data))


def test_actual_files_contract_and_exact_subjects(actual):
    _, records = actual
    receipt, assessment, review = (
        records[key] for key in ("receipt", "assessment", "review")
    )
    assert verify(actual).payload == receipt.payload
    assert assessment.to_dict()["verdict"] == review.to_dict()["verdict"] == "PASS"
    data = receipt.to_dict()
    assert (
        tuple(row["relative_path"] for row in data["source_files"])
        == module.FIXED_PATHS
    )
    for row in data["source_files"]:
        assert (
            row["utf8"].encode("utf-8")
            == (WORKSPACE / row["relative_path"]).read_bytes()
        )
    assert all(check["passed"] for check in data["checks"])
    assert data["hazard_ids"] == ["HZ-007", "HZ-010"]
    assert all(data["blockers"].values())
    assert data["design"]["board_size_mm"] == [610.0, 457.0, 18.0]
    assert data["design"]["nominal_entrance_pupil_z_mm"] == 1000.0
    assert data["design"]["published_mode"]["width_px"] == 5472
    assert data["design"]["value_provenance"] == "DESIGN_NOT_MEASURED"
    for artifact in records.values():
        assert all(artifact.to_dict()[key] is False for key in module.FLAGS)
        assert (
            len(module._canonical(artifact.safe_summary())) <= module.MAX_SUMMARY_BYTES
        )
    assert len(receipt.payload) <= module.MAX_RECEIPT_BYTES
    assert (
        module.verify_static_camera_contract_assessment(
            assessment, receipt=receipt, expected_assessment_sha256=assessment.sha256
        )
        == assessment
    )
    assert (
        module.verify_static_camera_contract_review(
            review,
            receipt=receipt,
            assessment=assessment,
            expected_review_sha256=review.sha256,
        )
        == review
    )


def test_full_actual_metadata_fits_existing_result_sanitizer(actual):
    from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record
    from rocell.application.arrival_wizard_service import MAX_RESULT_BYTES

    report = {key: value.to_dict() for key, value in actual[1].items()}
    value = {"steps": [{"name": "static_camera_contract", "report": report}]}
    clean = sanitize_diagnostic_record(value, maximum_bytes=MAX_RESULT_BYTES)
    assert clean == value


def test_pure_verification_and_summaries_never_read_or_resolve_files(
    actual, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Pure original verifier attempted filesystem/source execution")

    monkeypatch.setattr(module, "source_fingerprint", forbidden)
    monkeypatch.setattr(module, "read_bounded_regular_file", forbidden)
    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    assert verify(actual).safe_summary() == actual[1]["receipt"].safe_summary()
    receipt, assessment, review = (
        actual[1][key] for key in ("receipt", "assessment", "review")
    )
    assert module.assess_static_camera_contract(receipt) == assessment
    assert (
        module.verify_static_camera_contract_review(
            review.payload,
            receipt=receipt,
            assessment=assessment,
            expected_review_sha256=review.sha256,
        )
        == review
    )


def test_original_source_conflict_deterministically_blocked(actual):
    receipt = blocked_receipt(actual[1]["receipt"])
    assessment = module.assess_static_camera_contract(receipt)
    assert assessment.to_dict()["missing_requirements"] == [
        "support_design_file_matches_source_binding"
    ]
    review = module.review_static_camera_contract(
        receipt,
        assessment,
        reviewer_id="independent-reviewer",
        review_launch_id="wizard-" + "d" * 32,
        reviewed_at_ns=time.time_ns(),
    )
    assert assessment.to_dict()["verdict"] == review.to_dict()["verdict"] == "BLOCKED"
    assert (
        module.verify_static_camera_contract_review(
            review,
            receipt=receipt,
            assessment=assessment,
            expected_review_sha256=review.sha256,
        )
        == review
    )


@pytest.mark.parametrize(
    "key",
    [
        "source_sha256",
        "header_sha256",
        "prerequisites_sha256",
        "static_request_event_sha256",
        "contract_id",
        "store_directory",
        "collection_launch_id",
        "operator_id",
    ],
)
def test_independent_expected_binding_cannot_change(actual, key):
    binding = actual[1]["receipt"].to_dict()["binding"]
    binding[key] = "wrong"
    with pytest.raises(ValueError):
        verify(actual, expected_binding=binding)


@pytest.mark.parametrize("role", ["receipt", "assessment", "review"])
def test_types_are_canonical_bounded_immutable_and_detached(actual, role):
    artifact = actual[1][role]
    with pytest.raises(FrozenInstanceError):
        artifact.payload = b"{}"
    data = artifact.to_dict()
    data["binding"]["operator_id"] = "changed"
    assert artifact.to_dict()["binding"]["operator_id"] == "static-operator"
    for raw in (
        artifact.payload + b"\n",
        bytearray(artifact.payload),
        b"x" * (module.MAX_RECEIPT_BYTES + 1),
        artifact.payload[:-1] + b',"physical_authority":false}',
    ):
        with pytest.raises(ValueError):
            type(artifact)(raw)


@pytest.mark.parametrize(
    "mutation",
    [
        "check",
        "geometry",
        "raw-sha",
        "raw-bytes",
        "lock",
        "extra-path",
        "authority",
        "bool-time",
    ],
)
def test_rehashed_receipt_cannot_replace_calculations_or_originals(actual, mutation):
    data = actual[1]["receipt"].to_dict()
    if mutation == "check":
        data["checks"][0]["passed"] = False
    elif mutation == "geometry":
        data["design"]["nominal_entrance_pupil_z_mm"] = 900
    elif mutation == "raw-sha":
        data["source_files"][0]["sha256"] = "b" * 64
    elif mutation == "raw-bytes":
        data["source_files"][0]["bytes"] += 1
    elif mutation == "lock":
        row = next(
            row
            for row in data["source_files"]
            if row["relative_path"] == module.SUPPORT_PATH
        )
        row["utf8"] = row["utf8"].replace("e5414dc7", "f5414dc7")
        row["sha256"] = module._hash(row["utf8"].encode())
    elif mutation == "extra-path":
        data["source_files"][0]["relative_path"] = "../arbitrary.json"
    elif mutation == "authority":
        data["physical_authority"] = True
    else:
        data["collection"]["started_monotonic_ns"] = True
    with pytest.raises(ValueError):
        module.StaticCameraContractReceipt(module._canonical(data))


@pytest.mark.parametrize(
    "reviewer", ["static-operator", "STATIC-OPERATOR", "same\nactor", "é", "x" * 65]
)
def test_review_is_distinct_exact_subject_procedure(actual, reviewer):
    records = actual[1]
    with pytest.raises(ValueError):
        module.review_static_camera_contract(
            records["receipt"],
            records["assessment"],
            reviewer_id=reviewer,
            review_launch_id="wizard-" + "d" * 32,
            reviewed_at_ns=time.time_ns(),
        )


def test_review_refuses_different_assessment(actual):
    records = actual[1]
    other = module.assess_static_camera_contract(blocked_receipt(records["receipt"]))
    with pytest.raises(ValueError):
        module.review_static_camera_contract(
            records["receipt"],
            other,
            reviewer_id="different",
            review_launch_id="wizard-" + "d" * 32,
            reviewed_at_ns=time.time_ns(),
        )


def test_stop_before_read_and_original_deadline_are_not_renewed(actual, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Preflight refusal must not read a static source")

    monkeypatch.setattr(module, "read_bounded_regular_file", forbidden)
    cancellation = Event()
    cancellation.set()
    with pytest.raises(module.StaticCameraContractError, match="CANCELLED"):
        collect_again(actual, cancellation=cancellation)
    with pytest.raises(module.StaticCameraContractError):
        collect_again(actual, deadline_ns=time.monotonic_ns() - 1)


@pytest.mark.parametrize("point", ["source", "progress", "cleanup", "stop", "timeout"])
def test_complete_bytes_survive_late_refusal_never_current(actual, monkeypatch, point):
    original_pins = module._pins
    source = actual[1]["receipt"].to_dict()["binding"]["source_sha256"]
    calls = 0
    cancellation = Event()
    clock = time.monotonic_ns()
    expired = False

    def fingerprint(_):
        nonlocal calls, expired
        calls += 1
        if calls == 3:
            if point == "source":
                return "e" * 64
            if point == "stop":
                cancellation.set()
            if point == "timeout":
                expired = True
        return source

    def progress(message):
        if point == "progress" and message.startswith("Static design bytes"):
            raise RuntimeError("Modeled late callback failure")

    @contextmanager
    def pins(*args, **kwargs):
        with original_pins(*args, **kwargs):
            yield
        if point == "cleanup":
            raise RuntimeError("Modeled late guard-close failure")

    monkeypatch.setattr(module, "source_fingerprint", fingerprint)
    monkeypatch.setattr(module, "_pins", pins)
    if point == "timeout":
        monkeypatch.setattr(
            module.time,
            "monotonic_ns",
            lambda: clock + (31_000_000_000 if expired else 0),
        )
    with pytest.raises(module.StaticCameraContractError) as error:
        collect_again(actual, cancellation=cancellation, progress=progress)
    retained = error.value.receipt
    assert type(retained) is module.StaticCameraContractReceipt
    assert (
        retained.to_dict()["source_files"]
        == actual[1]["receipt"].to_dict()["source_files"]
    )


def test_legacy_loaders_equal_pure_retained_parsers_and_no_path_io(monkeypatch):
    architecture = camera_architecture.load_camera_architecture_plan(WORKSPACE)
    support = static_camera_support.load_static_camera_support_design(WORKSPACE)
    raw = {path: (WORKSPACE / path).read_bytes() for path in module.FIXED_PATHS}

    def forbidden(*args, **kwargs):
        pytest.fail("Pure parser attempted path access")

    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    assert (
        camera_architecture.parse_camera_architecture_plan_json(
            raw[module.ARCHITECTURE_PATH], source_path=architecture.source_path
        )
        == architecture
    )
    assert (
        static_camera_support.parse_static_camera_support_json(
            raw[module.SUPPORT_PATH],
            source_path=support.path,
            source_hashes={
                path: module._hash(raw[path]) for _, path in module.LOCKED_SOURCES
            },
        )
        == support
    )
