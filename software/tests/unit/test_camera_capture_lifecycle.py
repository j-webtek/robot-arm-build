"""M2 pure semantics with explicit modeled native/process observations only.

These fixtures do not establish original provenance, camera timing, USB facts or
pixels. Their in-memory timestamp edits define fault cases; production originals
are never modified. Existing v2 pair/run parsers remain unpatched.
"""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from rocell.application import camera_capture_lifecycle as module
from rocell.application.camera_activation_campaign_evidence import (
    CameraActivationArtifact,
    _COMMON,
)
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_operating_evidence_preflight import case, no_physical_owner


def rewrite_native(subject, change):
    """Produce a new modeled pair, keeping shared diagnostics internally joined."""
    data, detail = (json.loads(item.payload) for item in subject.native.evidence)
    change(data)
    detail.update({key: data[key] for key in _COMMON})
    detail["after_cleanup"] = data["owner_observation"]
    pair = (
        CameraActivationArtifact("run", canonical(data)),
        CameraActivationArtifact("supervision", canonical(detail)),
    )
    native = replace(
        subject.native,
        evidence=pair,
        expected_evidence_sha256=pair[0].payload_sha256,
        expected_supervision_sha256=pair[1].payload_sha256,
    )
    return replace(subject, native=native)


def shift(subject, offset):
    def change(data):
        for key in ("started_ns", "finished_ns", "parent_deadline_ns"):
            data[key] += offset
        for key in ("deadline_ns", "finished_ns"):
            data["cleanup"][key] += offset

    return rewrite_native(subject, change)


@pytest.fixture
def pair(tmp_path, monkeypatch):
    inputs, capture = case(tmp_path, monkeypatch)

    def subject(name, **kwargs):
        return module.CameraCaptureLifecycleSubject(
            native=capture(name, **kwargs).native,
            request_key="request-" + name,
            launch_session_id="wizard-" + "1" * 32,
            settings_epoch=inputs["expected_settings_epoch"],
            admission_sha256=digest(("MODELED admission " + name).encode()),
        )

    first = subject("first")
    second = shift(subject("second"), 1_000_000_000)
    return first, second, subject, inputs


def assess(pair):
    return module.assess_camera_capture_lifecycle(*pair[:2])


def test_consistent_pair_preserves_order_and_never_authenticates_itself(
    pair, monkeypatch
):
    saved = tuple(item.native.evidence for item in pair[:2])

    def forbidden(*args, **kwargs):
        pytest.fail("Pure lifecycle comparison attempted I/O")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "lstat", "resolve", "mkdir"):
            patch.setattr(Path, name, forbidden)
        for name in (
            "probe",
            "capture",
            "enumerate_metadata",
            "resolve_identity_metadata",
        ):
            patch.setattr(WindowsCameraWorkerClient, name, forbidden)
        report = assess(pair)
    assert report["status"] == "CONSISTENT_PENDING_ORIGINAL_AUTHENTICATION"
    assert report["failed_checks"] == []
    assert report["inter_run_gap_ns"] > 0
    assert [row["request_key"] for row in report["captures"]] == [
        "request-first",
        "request-second",
    ]
    assert report["owner_obligations"] == list(module.OWNER_OBLIGATIONS)
    for key in (
        "original_stage_authenticated",
        "clock_domain_authenticated",
        "stage_passed",
        "approved_operating_policy",
        "physical_authority",
        "hardware_qualified",
        "connected",
        "device_io_performed",
    ):
        assert report[key] is False
    assert len(canonical(report)) < 16 * 1024
    report["captures"][0]["request_key"] = "different"
    assert assess(pair)["captures"][0]["request_key"] == "request-first"
    assert saved == tuple(item.native.evidence for item in pair[:2])


@pytest.mark.parametrize("gap", [-1, 0, 1])
def test_exact_inter_run_boundary_has_no_arbitrary_wait(pair, gap):
    first, second = pair[:2]
    before = json.loads(first.native.evidence[0].payload)["finished_ns"]
    after = json.loads(second.native.evidence[0].payload)["started_ns"]
    second = shift(second, before + gap - after)
    report = module.assess_camera_capture_lifecycle(first, second)
    assert report["inter_run_gap_ns"] == gap
    assert ("STRICT_FINISH_BEFORE_NEXT_START_UNPROVEN" in report["failed_checks"]) == (
        gap <= 0
    )
    assert (report["status"] == "HELD") == (gap <= 0)


def test_reversed_selection_is_held_not_sorted(pair):
    report = module.assess_camera_capture_lifecycle(pair[1], pair[0])
    assert report["status"] == "HELD"
    assert report["inter_run_gap_ns"] < 0
    assert report["captures"][0]["request_key"] == "request-second"


@pytest.mark.parametrize("launch", [None, "another-launch"])
def test_unproven_clock_domain_is_not_subtracted(pair, launch):
    second = replace(pair[1], launch_session_id=launch)
    report = module.assess_camera_capture_lifecycle(pair[0], second)
    assert report["inter_run_gap_ns"] is None
    assert "COMMON_LAUNCH_CONTEXT_MISSING_OR_CHANGED" in report["failed_checks"]


@pytest.mark.parametrize("duplicate", ["request_key", "attempt"])
def test_duplicate_capture_cannot_be_a_reopen(pair, duplicate):
    first, second = pair[:2]
    second = (
        replace(second, request_key=first.request_key)
        if duplicate == "request_key"
        else replace(second, native=first.native)
    )
    assert (
        "DISTINCT_CAPTURE_ATTEMPTS_REQUIRED"
        in module.assess_camera_capture_lifecycle(first, second)["failed_checks"]
    )


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("native_cleanup", "SECOND_NATIVE_CLEANUP_UNCONFIRMED"),
        ("cleanup", "SECOND_PROCESS_CLEANUP_UNCONFIRMED"),
        ("failed9", "SECOND_RUN_NOT_SUCCESSFUL"),
    ],
)
def test_failed_capture_and_uncertain_cleanup_stay_explicit(pair, fault, reason):
    second = shift(pair[2]("failed", fault=fault), 1_000_000_000)
    report = module.assess_camera_capture_lifecycle(pair[0], second)
    assert report["status"] == "HELD" and reason in report["failed_checks"]


@pytest.mark.parametrize("field", ["started_ns", "finished_ns", "cleanup_finished_ns"])
def test_missing_timing_never_substitutes_another_boundary(pair, field):
    def change(data):
        if field == "cleanup_finished_ns":
            data["cleanup"]["finished_ns"] = None
        else:
            data[field] = None

    first = rewrite_native(pair[0], change)
    report = module.assess_camera_capture_lifecycle(first, pair[1])
    assert report["status"] == "HELD"
    assert report["captures"][0][field] is None


def test_reversed_internal_time_and_retained_resources_are_held(pair):
    def change(data):
        data["started_ns"] = data["finished_ns"] + 1
        data["owner_observation"]["fields"]["handles_remaining"]["value"] = 1

    first = rewrite_native(pair[0], change)
    report = module.assess_camera_capture_lifecycle(first, pair[1])
    assert "FIRST_RUN_NOT_SUCCESSFUL" in report["failed_checks"]
    assert "FIRST_PROCESS_CLEANUP_UNCONFIRMED" in report["failed_checks"]


def test_same_values_do_not_restore_changed_settings_epoch(pair):
    second = replace(pair[1], settings_epoch="b" * 64)
    report = module.assess_camera_capture_lifecycle(pair[0], second)
    assert report["failed_checks"] == ["SETTINGS_EPOCH_CHANGED"]


def test_changed_runtime_is_not_equivalent_to_a_new_capture(pair):
    second = shift(pair[2]("changed-runtime", helper="e" * 64), 1_000_000_000)
    report = module.assess_camera_capture_lifecycle(pair[0], second)
    assert "CHANGED_RUNTIME_REGISTRATION_SHA256" in report["failed_checks"]
    assert "CHANGED_HELPER_SHA256" in report["failed_checks"]


@pytest.mark.parametrize(
    "field", ["expected_evidence_sha256", "expected_supervision_sha256"]
)
def test_pair_reference_substitution_rejected_before_verdict(pair, field):
    native = replace(pair[0].native, **{field: "e" * 64})
    with pytest.raises(ValueError, match="LIFECYCLE_NATIVE_REFERENCE_MISMATCH"):
        module.assess_camera_capture_lifecycle(replace(pair[0], native=native), pair[1])


def test_probe_cannot_substitute_for_a_capture(pair):
    with pytest.raises(ValueError, match="LIFECYCLE_CAPTURE_REQUIRED"):
        module.assess_camera_capture_lifecycle(
            replace(pair[0], native=pair[3]["probe"]), pair[1]
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("launch_session_id", ""),
        ("launch_session_id", True),
        ("request_key", ""),
        ("request_key", "x" * 512),
        ("settings_epoch", "0" * 64),
        ("admission_sha256", "0" * 64),
        ("native", {"approved": True}),
    ],
)
def test_malformed_context_is_not_a_valid_unknown(pair, field, value):
    with pytest.raises(ValueError):
        module.assess_camera_capture_lifecycle(
            replace(pair[0], **{field: value}), pair[1]
        )
