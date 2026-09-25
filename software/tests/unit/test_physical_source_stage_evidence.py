"""Actual controlled files/software facts; no device, helper, serial or process."""

from contextlib import contextmanager
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import subprocess
from threading import Event
import time

import pytest

from rocell.application import physical_source_stage_evidence as module
from rocell.application import physical_camera_prerequisites as prerequisites_module


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE = "a" * 64
SESSION = "physical-camera-" + "1" * 32
ORIGIN = "wizard-source-origin"
COLLECTION = "wizard-source-collection"
HEADER = "b" * 64


def produce_actual_file_artifacts(monkeypatch):
    """Real original files/calculators, explicitly modeled broad source hash.

    No fake PASS report or physical observation is substituted. The monkeypatch
    is source-fingerprint only so parallel development doesn't forge freshness.
    """
    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    monkeypatch.setattr(prerequisites_module, "source_fingerprint", lambda _: SOURCE)
    prerequisites = prerequisites_module.collect_physical_camera_prerequisites(
        WORKSPACE,
        source_sha256=SOURCE,
        session_id=SESSION,
        launch_session_id=ORIGIN,
        cancellation=Event(),
        deadline_ns=time.monotonic_ns() + 30_000_000_000,
    )
    receipt = collect(prerequisites)
    assessment = module.assess_workspace_source_receipt(receipt)
    review = module.review_workspace_source_assessment(
        receipt,
        assessment,
        reviewer_id="independent-fixture-reviewer",
        review_launch_id="wizard-source-review",
    )
    return prerequisites, receipt, assessment, review


def collect(prerequisites, **kwargs):
    return module.collect_workspace_source_receipt(
        WORKSPACE,
        prerequisites=prerequisites,
        source_sha256=SOURCE,
        session_id=SESSION,
        origin_launch_id=ORIGIN,
        collection_launch_id=COLLECTION,
        header_sha256=HEADER,
        operator_id="fixture-operator",
        cancellation=kwargs.pop("cancellation", Event()),
        **kwargs,
    )


@pytest.fixture(scope="module")
def actual():
    with pytest.MonkeyPatch.context() as monkeypatch:
        # Prove even a cold platform.release cannot launch ver in this collector.
        def forbidden(*args, **kwargs):
            pytest.fail("No subprocess/native/device collector allowed")

        monkeypatch.setattr(subprocess, "Popen", forbidden)
        from rocell.application import physical_device_inventory
        from rocell.providers.windows import controller_metadata

        monkeypatch.setattr(
            physical_device_inventory, "inventory_serial_ports_with_pyserial", forbidden
        )
        monkeypatch.setattr(
            controller_metadata, "WindowsControllerMetadataAcquirer", forbidden
        )
        yield produce_actual_file_artifacts(monkeypatch)


def verify(receipt, prerequisites, **changes):
    kwargs = dict(
        prerequisites=prerequisites,
        expected_source_sha256=SOURCE,
        expected_session_id=SESSION,
        expected_origin_launch_id=ORIGIN,
        expected_header_sha256=HEADER,
        expected_receipt_sha256=receipt.sha256,
    )
    kwargs.update(changes)
    return module.verify_workspace_source_receipt(receipt.payload, **kwargs)


def encoded(value):
    return module._canonical(value)


def test_actual_file_receipt_and_deterministic_blocked_assessment(actual):
    prerequisites, receipt, assessment, review = actual
    assert verify(receipt, prerequisites) == receipt
    assert module.assess_workspace_source_receipt(receipt).payload == assessment.payload
    assert (
        module.verify_workspace_source_assessment(
            assessment.payload,
            receipt=receipt,
            expected_assessment_sha256=assessment.sha256,
        )
        == assessment
    )
    assert (
        module.verify_workspace_source_review(
            review.payload,
            receipt=receipt,
            assessment=assessment,
            expected_review_sha256=review.sha256,
        )
        == review
    )
    data = receipt.to_dict()
    assert (
        data["workspace_requirements"]
        == prerequisites.to_dict()["requirements"]["stages"][0]
    )
    assert len(data["source_files"]) >= 40
    assert len(data["foundation"]["contracts"]) == 6
    assert all(row["passed"] for row in data["software_checks"][:3])
    assert assessment.to_dict()["verdict"] == review.to_dict()["verdict"] == "BLOCKED"
    assert set(module.MISSING_REQUIREMENTS) <= set(
        assessment.to_dict()["missing_requirements"]
    )
    for artifact in (receipt, assessment, review):
        assert artifact.sha256 == hashlib.sha256(artifact.payload).hexdigest()
        assert len(artifact.payload) <= module.MAX_EVIDENCE_BYTES
        assert len(encoded(artifact.safe_summary())) <= module.MAX_SUMMARY_BYTES
        assert artifact.to_dict()["effects"] == module._EFFECTS
        assert all(
            artifact.safe_summary()[key] is False
            for key in (
                "physical_authority",
                "canonical_stage_pass",
                "device_io_performed",
            )
        )
        assert artifact.safe_summary()["power_state"] == "UNKNOWN"


def test_pure_verifiers_and_projection_never_replay_collectors(actual, monkeypatch):
    prerequisites, receipt, assessment, review = actual

    def forbidden(*args, **kwargs):
        pytest.fail(
            "Retained evidence verifier replayed a source/host/device collector"
        )

    monkeypatch.setattr(module, "source_fingerprint", forbidden)
    monkeypatch.setattr(module, "import_build_snapshot", forbidden)
    monkeypatch.setattr(
        module.foundation_module, "load_physical_onboarding_foundation", forbidden
    )
    monkeypatch.setattr(module.host_module, "assess_physical_host_readiness", forbidden)
    monkeypatch.setattr(module, "read_bounded_regular_file", forbidden)
    assert verify(receipt, prerequisites).safe_summary() == receipt.safe_summary()
    assert (
        module.verify_workspace_source_assessment(
            assessment, receipt=receipt, expected_assessment_sha256=assessment.sha256
        ).safe_summary()
        == assessment.safe_summary()
    )
    assert (
        module.verify_workspace_source_review(
            review,
            receipt=receipt,
            assessment=assessment,
            expected_review_sha256=review.sha256,
        ).safe_summary()
        == review.safe_summary()
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_source_sha256", "c" * 64),
        ("expected_session_id", "physical-camera-other"),
        ("expected_origin_launch_id", "wizard-other"),
        ("expected_header_sha256", "c" * 64),
        ("expected_receipt_sha256", "c" * 64),
    ],
)
def test_original_independent_context_digest_is_required(actual, field, value):
    prerequisites, receipt, _, _ = actual
    with pytest.raises(ValueError):
        verify(receipt, prerequisites, **{field: value})


@pytest.mark.parametrize("kind", ["receipt", "assessment", "review"])
def test_canonical_immutable_bounded_types_and_copy_isolation(actual, kind):
    value = actual[{"receipt": 1, "assessment": 2, "review": 3}[kind]]
    with pytest.raises(FrozenInstanceError):
        value.payload = b"{}"
    changed = value.to_dict()
    changed["binding"]["operator_id"] = "MUTATED"
    summary = value.safe_summary()
    summary["binding"]["operator_id"] = "MUTATED"
    assert value.to_dict()["binding"]["operator_id"] == "fixture-operator"
    with pytest.raises(ValueError):
        type(value)(value.payload + b"\n")
    with pytest.raises(ValueError):
        type(value)(bytearray(value.payload))
    with pytest.raises(ValueError):
        type(value)(b"x" * (module.MAX_EVIDENCE_BYTES + 1))
    with pytest.raises(ValueError):
        type(value)(value.payload[:-1] + b',"physical_authority":false}')


@pytest.mark.parametrize(
    "path,value",
    [
        (("physical_authority",), True),
        (("physical_authority",), 0),
        (("canonical_stage_pass",), True),
        (("power_state",), "DISCONNECTED"),
        (("effects", "device_open_count"), 1),
        (("effects", "serial_write_count"), False),
        (("foundation", "zero_physical_authority"), False),
        (("foundation", "source_sha256"), "d" * 64),
        (("host_readiness", "platform", "python_64_bit"), 1),
        (("host_readiness", "readiness", "base_software_ready"), False),
        (("collection", "after_source_sha256"), "d" * 64),
        (("collection", "before_files_sha256"), "d" * 64),
        (
            ("workspace_requirements", "actuator_power_requirement"),
            "ASSUMED_DISCONNECTED",
        ),
        (("workspace_requirements", "hazard_ids"), []),
        (("workspace_requirements", "unknown"), True),
        (("unknown",), 0),
    ],
)
def test_receipt_schema_fact_counter_and_derivation_tamper(actual, path, value):
    data = actual[1].to_dict()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    if path[0] == "host_readiness":
        host = data["host_readiness"]
        host["report_sha256"] = hashlib.sha256(
            encoded({k: v for k, v in host.items() if k != "report_sha256"})
        ).hexdigest()
    with pytest.raises(ValueError):
        module.WorkspaceSourceReceipt(encoded(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("verdict", "PASS"),
        ("missing_requirements", []),
        ("canonical_stage_pass", True),
        ("receipt_sha256", "d" * 64),
        ("physical_authority", 0),
    ],
)
def test_assessment_cannot_pass_or_change_its_subject(actual, field, value):
    _, receipt, assessment, _ = actual
    data = assessment.to_dict()
    data[field] = value
    raw = encoded(data)
    with pytest.raises(ValueError):
        module.verify_workspace_source_assessment(
            raw,
            receipt=receipt,
            expected_assessment_sha256=hashlib.sha256(raw).hexdigest(),
        )


@pytest.mark.parametrize(
    "reviewer",
    ["fixture-operator", "FIXTURE-OPERATOR", " fixture-operator", "\nother", "x" * 129],
)
def test_review_requires_distinct_bounded_literal_operator_label(actual, reviewer):
    _, receipt, assessment, _ = actual
    with pytest.raises(ValueError):
        module.review_workspace_source_assessment(
            receipt, assessment, reviewer_id=reviewer, review_launch_id="wizard-review"
        )


def test_unicode_casefold_is_authoritative_and_launch_is_separate(actual):
    _, receipt, _, _ = actual
    data = receipt.to_dict()
    data["binding"]["operator_id"] = "Straße_operator"
    receipt = module.WorkspaceSourceReceipt(encoded(data))
    assessment = module.assess_workspace_source_receipt(receipt)
    with pytest.raises(ValueError):
        module.review_workspace_source_assessment(
            receipt,
            assessment,
            reviewer_id="STRASSE_OPERATOR",
            review_launch_id="wizard-review",
        )
    review = module.review_workspace_source_assessment(
        receipt,
        assessment,
        reviewer_id="Réview_operator",
        review_launch_id="wizard-later-launch",
    )
    assert review.safe_summary()["reviewer_id"] == "Réview_operator"
    assert review.safe_summary()["authenticated_independent_people"] is False
    assert review.to_dict()["binding"]["origin_launch_id"] == ORIGIN
    assert review.to_dict()["review_launch_id"] != ORIGIN


@pytest.mark.parametrize(
    "field,value",
    [
        ("assessment_sha256", "d" * 64),
        ("receipt_sha256", "d" * 64),
        ("verdict", "PASS"),
        ("distinct_operator_labels", False),
        ("authenticated_independent_people", True),
    ],
)
def test_review_is_exact_subject_not_transferable_acceptance(actual, field, value):
    _, receipt, assessment, review = actual
    data = review.to_dict()
    data[field] = value
    raw = encoded(data)
    with pytest.raises(ValueError):
        module.verify_workspace_source_review(
            raw,
            receipt=receipt,
            assessment=assessment,
            expected_review_sha256=hashlib.sha256(raw).hexdigest(),
        )


def test_stop_before_any_source_read_and_source_drift_refused(actual, monkeypatch):
    prerequisite = actual[0]
    stopped = Event()
    stopped.set()
    monkeypatch.setattr(
        module, "source_fingerprint", lambda _: pytest.fail("Stop read source")
    )
    with pytest.raises(module.WorkspaceSourceEvidenceError, match="CANCELLED"):
        collect(prerequisite, cancellation=stopped)
    monkeypatch.setattr(module, "source_fingerprint", lambda _: "c" * 64)
    with pytest.raises(module.WorkspaceSourceEvidenceError, match="SOURCE_CHANGED"):
        collect(prerequisite)


def test_late_stop_preserves_complete_original_receipt(actual):
    cancellation = Event()

    def progress(message):
        if message.startswith("File facts collected"):
            cancellation.set()

    with pytest.raises(module.WorkspaceSourceEvidenceError) as caught:
        collect(actual[0], cancellation=cancellation, progress=progress)
    assert caught.value.code == "CANCELLED"
    historical = caught.value.receipt
    assert type(historical) is module.WorkspaceSourceReceipt
    assert verify(historical, actual[0]) == historical
    assert historical.safe_summary()["canonical_stage_pass"] is False


def test_late_progress_error_keeps_full_receipt_for_historical_export(actual):
    def progress(message):
        if message.startswith("File facts collected"):
            raise RuntimeError("not an authority proof")

    with pytest.raises(module.WorkspaceSourceEvidenceError) as caught:
        collect(actual[0], progress=progress)
    assert caught.value.code == "PROGRESS_FAILED"
    assert type(caught.value.receipt) is module.WorkspaceSourceReceipt


def test_late_deadline_keeps_receipt_without_extending_original_budget(
    actual, monkeypatch
):
    original_clock = module.time.monotonic_ns
    extra = [0]
    monkeypatch.setattr(
        module.time, "monotonic_ns", lambda: original_clock() + extra[0]
    )

    def progress(message):
        if message.startswith("File facts collected"):
            extra[0] = module.MAX_COLLECTION_DURATION_NS

    with pytest.raises(module.WorkspaceSourceEvidenceError) as caught:
        collect(actual[0], progress=progress)
    assert caught.value.code == "TIMED_OUT"
    assert type(caught.value.receipt) is module.WorkspaceSourceReceipt


def test_changed_final_fingerprint_produces_no_normal_receipt(actual, monkeypatch):
    values = iter((SOURCE, "c" * 64))
    monkeypatch.setattr(module, "source_fingerprint", lambda _: next(values))
    with pytest.raises(module.WorkspaceSourceEvidenceError) as caught:
        collect(actual[0])
    assert caught.value.code == "SOURCE_CHANGED"
    assert caught.value.receipt is None


@pytest.mark.skipif(module.os.name != "nt", reason="Windows file-sharing exclusion")
def test_copied_fixed_disk_file_is_write_and_rename_pinned(tmp_path):
    import shutil

    # This test only attempts changes to its copied file, never production data.
    relative = "software/config/runtime.json"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    shutil.copyfile(WORKSPACE / relative, target)
    original = target.read_bytes()
    with module._pins(tmp_path, (relative,), lambda: None):
        with pytest.raises(PermissionError):
            with target.open("ab"):
                pass
        with pytest.raises(PermissionError):
            target.rename(target.with_name("moved-runtime.json"))
    assert target.read_bytes() == original


def test_guard_exit_failure_never_returns_success_or_drops_facts(actual, monkeypatch):
    original = module._pins

    @contextmanager
    def uncertain(*args):
        with original(*args):
            yield
        raise module.WorkspaceSourceEvidenceError("SOURCE_PIN_CLOSE_FAILED")

    monkeypatch.setattr(module, "_pins", uncertain)
    with pytest.raises(module.WorkspaceSourceEvidenceError) as caught:
        collect(actual[0])
    assert caught.value.code == "SOURCE_PIN_CLOSE_FAILED"
    assert type(caught.value.receipt) is module.WorkspaceSourceReceipt


def test_external_dict_is_bounded_before_encoding(actual):
    _, receipt, assessment, _ = actual
    for data in (
        {"large": "x" * (module.MAX_EVIDENCE_BYTES + 1)},
        {"number": float("nan")},
    ):
        with pytest.raises(ValueError):
            module.verify_workspace_source_assessment(
                data, receipt=receipt, expected_assessment_sha256=assessment.sha256
            )
    cyclic = {}
    cyclic["cycle"] = cyclic
    with pytest.raises(ValueError):
        module.verify_workspace_source_assessment(
            cyclic, receipt=receipt, expected_assessment_sha256=assessment.sha256
        )
