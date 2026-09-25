"""Explicit MODELED owners/receipts, with no kernel, camera, original-store or pixel I/O."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.native_camera_activation_observations import (
    ActivationOwnerObservation,
    FIELDS,
    capture_activation_owner,
)
from rocell.providers.windows.native_camera_activation_evidence import (
    OwnedNativeCameraActivationRunEvidence,
    MAX_EVIDENCE_BYTES,
    retain_activation_run,
    verify_activation_run,
)
from rocell.providers.windows.native_camera_activation_protocol import (
    activation_release,
)
from rocell.providers.windows.native_camera_protocol import (
    canonical,
    digest,
    parse_native_camera_ready,
)
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
)
from rocell.providers.windows.owned_worker_process import WorkerProcessBudget
from test_native_camera_activation_registration import preparation, ready
from test_native_camera_activation_protocol import fixture as result_fixture


def modeled(tmp_path, purpose="probe"):
    prepared = preparation(tmp_path, purpose)
    ready_wire = ready(prepared)
    observed_ready = parse_native_camera_ready(
        ready_wire,
        expected_request_sha256=prepared.admission_request.request_sha256,
        expected_child_pid=123,
    )
    release_wire = activation_release(
        prepared.admission_request, observed_ready, expected_child_pid=123
    )
    _, _, raw = result_fixture(purpose)
    raw.update(
        request_sha256=prepared.admission_request.request_sha256, permit_sha256="f" * 64
    )
    result = canonical(raw) + b"\n"
    owner = SimpleNamespace(
        created=True,
        resumed=True,
        tree_exited=True,
        returncode=0,
        pid=123,
        written=len(prepared.admission_request.wire()) + len(release_wire),
        peak_handles=8,
        peak_processes=1,
        stdout_eof=True,
        stderr_eof=True,
        pending=False,
        handles={},
        unclosed_handles={},
        pins=[],
        stdout=ready_wire + result,
        stderr=b"",
    )
    args = dict(
        prepared=prepared,
        owner_constructed=True,
        started_ns=1_000_000_000,
        finished_ns=3_000_000_000,
        parent_deadline_ns=25_000_000_000,
        primary_error=None,
        cleanup=dict(
            attempted=True,
            returned=True,
            deadline_ns=4_000_000_000,
            finished_ns=2_900_000_000,
            errors=[],
        ),
        ready_wire=ready_wire,
        release_wire=release_wire,
        release_check_passed=True,
        accepted_result_sha256=digest(result),
    )
    return owner, args


def retain(owner, args):
    return retain_activation_run(
        owner_observation=(
            capture_activation_owner(owner, args["prepared"].registration.budget)
            if owner is not None
            else None
        ),
        **args,
    )


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_retained_v2_result_reopens_inertly_from_exact_bytes(
    tmp_path, monkeypatch, purpose
):
    owner, args = modeled(tmp_path, purpose)
    original = retain(owner, args)
    saved = original.payload

    def forbidden(*a, **kw):
        pytest.fail("Retained verifier attempted I/O")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "lstat", "resolve", "mkdir"):
            patch.setattr(Path, name, forbidden)
        for name in (
            "probe",
            "capture",
            "resolve_identity_metadata",
            "enumerate_metadata",
        ):
            patch.setattr(WindowsCameraWorkerClient, name, forbidden)
        checked = verify_activation_run(
            original,
            expected_preparation=args["prepared"],
            expected_evidence_sha256=digest(saved),
        )
        assessment = checked.assessment()
        assert (
            assessment.status == "SUCCEEDED_NATIVE_DIAGNOSTIC"
            and not assessment.reasons
        )
        assert (
            assessment.native is not None
            and assessment.native.receipt.operation == purpose
        )
        assert assessment.process_cleanup_confirmed
        view = checked.safe_summary()
        assert view["native_receipt_valid"] and view["native_cleanup_confirmed"]
        assert (
            view["physical_authority"]
            is view["hardware_qualified"]
            is view["frame_content_verified"]
            is False
        )
        assert checked.payload == saved
        data = checked.to_dict()
        data["owner_constructed"] = False
        assert checked.payload == saved and checked.to_dict()["owner_constructed"]
    with pytest.raises(ValueError):
        OwnedNativeCameraRunEvidence(saved)


@pytest.mark.parametrize("field", FIELDS)
def test_missing_owner_attributes_are_unavailable_not_zero(tmp_path, field):
    owner, args = modeled(tmp_path)
    attribute = field[:-10] if field.endswith("_remaining") else field
    delattr(owner, attribute)
    observation = capture_activation_owner(owner, args["prepared"].registration.budget)
    assert field in observation.unavailable_fields and field not in observation.values()
    raw = observation.to_dict()["fields"][field]
    assert raw == dict(available=False, value=None, reason="ATTRIBUTE_UNAVAILABLE")
    record = retain(owner, args)
    assert record.assessment().status == "FAILED"
    assert field in record.safe_summary()["unavailable_fields"]


def test_unknown_returncode_is_distinct_from_observed_not_yet_exited(tmp_path):
    owner, args = modeled(tmp_path)
    owner.returncode = None
    known = capture_activation_owner(owner, args["prepared"].registration.budget)
    assert (
        known.values()["returncode"] is None
        and "returncode" not in known.unavailable_fields
    )
    del owner.returncode
    unknown = capture_activation_owner(owner, args["prepared"].registration.budget)
    assert (
        "returncode" not in unknown.values()
        and "returncode" in unknown.unavailable_fields
    )
    assert retain(owner, args).safe_summary()["native_counts"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("created", 1),
        ("pid", True),
        ("written", -1),
        ("stdout", "not bytes"),
        ("returncode", "0"),
    ],
)
def test_invalid_attribute_reads_stay_unavailable(tmp_path, field, value):
    owner, args = modeled(tmp_path)
    setattr(owner, field, value)
    observation = capture_activation_owner(owner, args["prepared"].registration.budget)
    assert observation.to_dict()["fields"][field]["reason"] == "INVALID_VALUE"
    assert retain(owner, args).assessment().status == "FAILED"


def test_attribute_exception_does_not_erase_other_observations(tmp_path):
    owner, args = modeled(tmp_path)

    class Faulty:
        def __getattr__(self, name):
            if name == "pending":
                raise OSError("Not copied into the report")
            return getattr(owner, name)

    observation = capture_activation_owner(
        Faulty(), args["prepared"].registration.budget
    )
    assert observation.unavailable_fields == ("pending",)
    assert observation.values()["pid"] == 123
    assert b"Not copied" not in observation.payload


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize(
    "fault",
    [
        "cleanup-error",
        "cleanup-threw",
        "cleanup-late",
        "cleanup-no-clock",
        "cleanup-before-run",
        "resource-remains",
        "missing-resource",
        "run-expired",
        "time-reversal",
        "cancelled",
        "too-many-processes",
        "created-without-observed-process",
        "too-many-handles",
    ],
)
def test_failed_run_retains_native_diagnostics_without_promoting_success(
    tmp_path, purpose, fault
):
    owner, args = modeled(tmp_path, purpose)
    if fault == "cleanup-error":
        args["cleanup"]["errors"] = ["CLOSE_FAILED:pinned-file"]
    elif fault == "cleanup-threw":
        args["cleanup"].update(returned=False, errors=None)
    elif fault == "cleanup-late":
        args["cleanup"]["finished_ns"] = 5_000_000_000
    elif fault == "cleanup-no-clock":
        args["cleanup"]["finished_ns"] = None
    elif fault == "cleanup-before-run":
        args["cleanup"]["finished_ns"] = args["started_ns"] - 1
    elif fault == "resource-remains":
        owner.handles = {1: "pinned-file"}
    elif fault == "missing-resource":
        del owner.pins
    elif fault == "run-expired":
        args["finished_ns"] = args["parent_deadline_ns"]
    elif fault == "time-reversal":
        args["finished_ns"] = 1
    elif fault == "cancelled":
        args["primary_error"] = "CANCELLED"
    elif fault == "too-many-processes":
        owner.peak_processes = 2
    elif fault == "created-without-observed-process":
        owner.peak_processes = 0
    elif fault == "too-many-handles":
        owner.peak_handles = 513
    record = retain(owner, args)
    result = record.assessment()
    assert result.status == ("CANCELLED" if fault == "cancelled" else "FAILED")
    assert (
        result.native is not None and result.native.receipt.counts["source_opened"] == 1
    )
    assert record.safe_summary()["native_counts"]["source_opened"] == 1
    assert record.safe_summary()["physical_authority"] is False


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_outer_interval_includes_pinning_not_just_native_reservation(tmp_path, purpose):
    owner, args = modeled(tmp_path, purpose)
    # Native work still has its own original deadline. A long outer interval
    # may include pinning before the reservation began; it is not a timeout
    # when all supplied completion observations precede the parent deadline.
    args["finished_ns"] = 23_000_000_000
    args["cleanup"].update(finished_ns=22_000_000_000, deadline_ns=23_000_000_000)
    assert (
        args["finished_ns"] - args["started_ns"] > args["prepared"].required_lifetime_ns
    )
    assert retain(owner, args).assessment().status == "SUCCEEDED_NATIVE_DIAGNOSTIC"


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize(
    "fault",
    [
        "missing-pid",
        "wrong-pid",
        "missing-ready",
        "not-released",
        "not-accepted",
        "accepted-digest",
        "short-write",
        "no-eof",
        "overflow",
        "bad-json",
        "bad-inner-count",
        "wrong-result-binding",
    ],
)
def test_incomplete_or_malformed_result_is_preserved_but_not_accepted(
    tmp_path, purpose, fault
):
    owner, args = modeled(tmp_path, purpose)
    if fault == "missing-pid":
        del owner.pid
    elif fault == "wrong-pid":
        owner.pid = 124
    elif fault == "missing-ready":
        args["ready_wire"] = b""
    elif fault == "not-released":
        args["release_check_passed"] = False
    elif fault == "not-accepted":
        args["accepted_result_sha256"] = None
    elif fault == "accepted-digest":
        args["accepted_result_sha256"] = "9" * 64
    elif fault == "short-write":
        owner.written -= 1
    elif fault == "no-eof":
        owner.stdout_eof = False
    elif fault == "overflow":
        args["primary_error"] = "STDOUT_LIMIT"
    else:
        import json

        result = owner.stdout[len(args["ready_wire"]) :]
        raw = json.loads(result)
        if fault == "bad-inner-count":
            raw["native_receipt"]["counts"]["source_opened"] = 2
        elif fault == "wrong-result-binding":
            raw["permit_sha256"] = "9" * 64
        result = b"not-json" if fault == "bad-json" else canonical(raw)
        owner.stdout = args["ready_wire"] + result
        args["accepted_result_sha256"] = digest(result)
    record = retain(owner, args)
    assert record.assessment().status == "FAILED"
    assert record.assessment().native is None
    assert record.safe_summary()["native_counts"] is None
    observed = ActivationOwnerObservation(
        canonical(record.to_dict()["owner_observation"])
    )
    assert observed.values()["stdout"] == owner.stdout


def test_pre_owner_hold_is_retained_without_synthetic_process_or_native_counts(
    tmp_path,
):
    owner, args = modeled(tmp_path)
    args.update(
        owner_constructed=False,
        primary_error="PHYSICAL_PROVIDER_QUALIFICATION_HELD",
        ready_wire=b"",
        release_wire=b"",
        release_check_passed=False,
        accepted_result_sha256=None,
        cleanup=dict(
            attempted=False,
            returned=False,
            deadline_ns=None,
            finished_ns=None,
            errors=None,
        ),
    )
    record = retain(None, args)
    assert record.to_dict()["owner_observation"] is None
    view = record.safe_summary()
    assert (
        view["status"] == "HELD"
        and view["process_created"] is None
        and view["native_counts"] is None
    )
    assert not view["process_cleanup_confirmed"]
    args["ready_wire"] = b"unrelated"
    with pytest.raises(ValueError, match="WITHOUT_OWNER"):
        retain(None, args)


def test_independent_original_hash_and_full_preparation_are_required(tmp_path):
    owner, args = modeled(tmp_path)
    record = retain(owner, args)
    with pytest.raises(ValueError, match="TRUSTED_HASH"):
        verify_activation_run(
            record,
            expected_preparation=args["prepared"],
            expected_evidence_sha256="9" * 64,
        )
    with pytest.raises(ValueError, match="TRUSTED_PREPARATION"):
        verify_activation_run(
            record,
            expected_preparation=preparation(tmp_path / "different"),
            expected_evidence_sha256=record.evidence_sha256,
        )


def test_large_available_output_fits_new_record_and_is_stored_only_once(tmp_path):
    owner, args = modeled(tmp_path)
    owner.stdout = bytes(range(256)) * 1024
    owner.stderr = b"diagnostic" * 800  # Below the separate 8 KiB bound.
    args.update(accepted_result_sha256=None, primary_error="STDOUT_LIMIT")
    record = retain(owner, args)
    assert 128 * 1024 < len(record.payload) < MAX_EVIDENCE_BYTES
    raw = record.to_dict()
    assert "validated_result" not in raw
    restored = ActivationOwnerObservation(canonical(raw["owner_observation"]))
    assert restored.values()["stdout"] == owner.stdout
    assert restored.values()["stderr"] == owner.stderr
    assert record.assessment().status == "FAILED"


def test_observed_buffer_truncation_is_explicit_not_complete_child_accounting(tmp_path):
    owner, args = modeled(tmp_path)
    owner.stdout = b"x" * (256 * 1024 + 7)
    snapshot = capture_activation_owner(owner, args["prepared"].registration.budget)
    assert (
        snapshot.to_dict()["fields"]["stdout"]["value"]["omitted_from_observed_buffer"]
        == 7
    )
    assert len(snapshot.values()["stdout"]) == 256 * 1024
    assert retain(owner, args).assessment().native is None
    owner.stderr = b"x" * (64 * 1024)
    full_budget = WorkerProcessBudget()
    assert len(capture_activation_owner(owner, full_budget).payload) < 448 * 1024


@pytest.mark.parametrize(
    "fault",
    [
        "extra",
        "authority",
        "bad-source",
        "bad-registration",
        "bool-clock",
        "cleanup-unknown-as-empty",
        "snapshot-budget",
    ],
)
def test_closed_record_rejects_fabricated_metadata(tmp_path, fault):
    owner, args = modeled(tmp_path)
    raw = retain(owner, args).to_dict()
    if fault == "extra":
        raw["status"] = "SUCCEEDED"
    elif fault == "authority":
        raw["physical_authority"] = True
    elif fault == "bad-source":
        raw["source_sha256"] = "9" * 64
    elif fault == "bad-registration":
        raw["registration_sha256"] = "9" * 64
    elif fault == "bool-clock":
        raw["finished_ns"] = True
    elif fault == "cleanup-unknown-as-empty":
        raw["cleanup"].update(returned=False, errors=[])
    elif fault == "snapshot-budget":
        raw["owner_observation"]["stdout_limit"] -= 1
    with pytest.raises(ValueError):
        OwnedNativeCameraActivationRunEvidence(canonical(raw))
