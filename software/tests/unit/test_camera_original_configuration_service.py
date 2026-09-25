"""Original configuration service/M1/core/ingest with incapable native owners.

Only setup semantic authentication is MODELED. Probe originals, configuration
derivation/admission, current capacity, actual NTFS scopes and capture readback
run normally. These are not full-history or received-unit qualification tests.
"""

from pathlib import Path
from threading import Event
import time

import pytest

from rocell.application import camera_configuration_capacity as capacity
from rocell.application.camera_configuration_wizard_contract import CAPTURE_ACTION_ID
from rocell.application.cell_commissioning_coordinator import (
    CommissioningCoordinatorError,
)
from rocell.application.physical_camera_session import PhysicalCameraSession
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_configuration_originals import make_context, BUDGET, WINDOWS, LEASES
from test_camera_activation_dispatch_handoff import install_owner
from test_camera_activation_application_handoff import no_device_calls
from test_native_camera_activation_supervisor import no_physical_owner


def run_capture(c, *, request_key="MODELED-settings-original", **overrides):
    options = dict(
        request_key=request_key,
        expected_header_sha256=c.values["expected_header_sha256"],
        expected_preparation_sha256="1" * 64,
        expected_review_sha256="2" * 64,
        expected_plan_sha256=digest(canonical(c.capture_plan)),
        capture_budget=BUDGET,
        operator_id="MODELED settings operator",
        arm_actuator_supply_disconnected=True,
        bounded_configuration_capture_consent=True,
        cancellation=Event(),
        deadline_ns=time.monotonic_ns() + 240_000_000_000,
        progress=c.progress.append,
        validate_current_context=lambda: None,
        sealed_configuration_capture=c.capture_plan["schema"]
        == "rocell.physical_native_camera_configuration_campaign.v2",
    )
    options.update(overrides)
    return c.service.run_original_configuration_capture(
        c.session, c.enrollment, **options
    )


@WINDOWS
@pytest.mark.parametrize("sealed", [False, True])
def test_actual_configuration_admission_capture_publication_and_second_explicit_request(
    tmp_path, monkeypatch, sealed
):
    c = make_context(tmp_path, monkeypatch, sealed_configuration_capture=sealed)
    original_probe = c.service.retained_probe_diagnostics()
    owners = install_owner(tmp_path, monkeypatch, purpose="capture", pixels=True)
    # Keep the original coordinator reason visible if later readback encounters
    # missing evidence. This observer does not suppress/change any exception.
    coordinator_errors = []
    original_error_init = CommissioningCoordinatorError.__init__

    def observed_error_init(error, *args):
        coordinator_errors.append(str(args))
        original_error_init(error, *args)

    monkeypatch.setattr(CommissioningCoordinatorError, "__init__", observed_error_init)
    try:
        result = run_capture(c)
    except Exception as error:
        pytest.fail(
            f"Original coordinator failures: {coordinator_errors}; readback: {error}"
        )
    assert len(owners) == 1 and owners[0].cleaned
    reference_candidate = c.service.retained_capture_diagnostics()["pending"][
        "capture_reference_candidate"
    ]
    assert reference_candidate["retention"] == "LAUNCH_DIAGNOSTIC_ONLY_NOT_M1_ORIGINAL"
    assert reference_candidate["sha256"] == digest(
        canonical(reference_candidate["document"])
    )
    assert reference_candidate["document"]["request_key"] == "MODELED-settings-original"
    assert reference_candidate["document"]["frame"]["length_bytes"] == 16
    assert not reference_candidate["document"]["original_store_authenticated"]
    assert c.service.view()["publication"]["status"] == "PENDING"
    assert c.service.cache_published_preview("image-" + "3" * 32) is None
    c.service.validate_observation_publication(CAPTURE_ACTION_ID, result)
    c.service.publish_retained_observation("operation-" + "4" * 32)
    assert c.service.cache_published_preview("image-" + "5" * 32).startswith(b"\x89PNG")
    packet = c.service.retained_configuration_diagnostics()
    assert packet["admission"]["status"] == "RESULT_STAGED_NOT_PUBLISHED"
    assert packet["dispatch"]["transaction"]["attempt_state"] == "SEALED_KNOWN"
    if sealed:
        original = packet["dispatch"]["original_evidence"]
        assert (
            original["schema"]
            == "rocell.camera_activation_observation_with_checksum.v1"
        )
        assert original["capture_checksum"]["status"] == "CAPTURE_BYTES_HASHED"
        assert original["capture_checksum_sha256"] == digest(
            canonical(original["capture_checksum"])
        )
    assert packet["dispatch"]["original_admission"] == packet["admission"]["admission"]
    assert c.service.retained_probe_diagnostics() == original_probe
    with pytest.raises(ValueError, match="already attempted"):
        run_capture(c)
    assert len(owners) == 1
    # New explicit request, same settings: useful for a later separately guided
    # reopen check. This test does not assess/pass that physical stage.
    c.capture_plan = c.service.preview_activation_plan(
        "capture",
        c.enrollment,
        capture_budget=BUDGET,
        configuration_verification=True,
        sealed_configuration_capture=sealed,
    )
    try:
        second = run_capture(c, request_key="MODELED-explicit-second-capture")
    except Exception as error:
        pytest.fail(
            f"Second original coordinator failures: {coordinator_errors}; readback: {error}"
        )
    c.service.validate_observation_publication(CAPTURE_ACTION_ID, second)
    c.service.publish_retained_observation("operation-" + "6" * 32)
    assert len(owners) == 2
    assert c.service.retained_probe_diagnostics() == original_probe
    assert (
        c.service.retained_configuration_diagnostics()["dispatch"]["transaction"][
            "attempt_id"
        ]
        != packet["dispatch"]["transaction"]["attempt_id"]
    )
    assert not c.runtime.verify(c.service.session_id).active_lease_owners


@WINDOWS
@pytest.mark.parametrize("sealed", [False, True])
@pytest.mark.parametrize(
    "fault",
    ["bad-result", "cleanup-missing-resource", "capacity", "guard", "late-stop"],
)
def test_failed_configuration_capture_keeps_probe_and_attempt_evidence_without_replay(
    tmp_path, monkeypatch, fault, sealed
):
    c = make_context(tmp_path, monkeypatch, sealed_configuration_capture=sealed)
    original_probe = c.service.retained_probe_diagnostics()
    owners = install_owner(
        tmp_path,
        monkeypatch,
        purpose="capture",
        pixels=True,
        fault=fault if fault in {"bad-result", "cleanup-missing-resource"} else None,
    )
    options = {}
    if fault == "capacity":
        monkeypatch.setattr(
            capacity.shutil, "disk_usage", lambda _: type("LowSpace", (), {"free": 0})()
        )
    elif fault == "guard":
        options["validate_current_context"] = lambda: True
    elif fault == "late-stop":
        stop = Event()
        original = c.service.stage_retained_capture

        def returned(*args, **kwargs):
            value = original(*args, **kwargs)
            stop.set()
            return value

        monkeypatch.setattr(c.service, "stage_retained_capture", returned)
        options["cancellation"] = stop
    with pytest.raises(ValueError):
        run_capture(c, **options)
    packet = c.service.retained_configuration_diagnostics()
    assert packet["admission"]["status"] == "FAILED_HELD"
    assert c.service.retained_probe_diagnostics() == original_probe
    assert c.service.cache_published_preview("image-" + "7" * 32) is None
    assert len(owners) == (0 if fault in {"capacity", "guard"} else 1)
    if fault in {"bad-result", "cleanup-missing-resource"}:
        assert packet["dispatch"]["original_evidence"] is not None
        assert packet["dispatch"]["transaction"]["attempt_state"] == "SEALED_UNCERTAIN"
    assert "MODELED-settings-original" in c.service._original_configuration_claims


@WINDOWS
def test_original_capture_rejects_cloned_owner_missing_store_and_unpublished_settings(
    tmp_path, monkeypatch
):
    c = make_context(tmp_path, monkeypatch)
    owners = install_owner(tmp_path, monkeypatch, purpose="capture", pixels=True)
    original_session = c.session
    c.session = PhysicalCameraSession(
        tmp_path,
        Path(original_session.descriptor()["directory"]),
        launch_id=c.service.origin_launch_id,
        source_sha256=c.service.source_sha256,
        cell_id=c.service.cell_id,
        session_id=c.service.session_id,
    )
    with pytest.raises(ValueError, match="same original"):
        run_capture(c)
    c.session = original_session
    with monkeypatch.context() as patch:
        patch.setattr(
            c.service, "_original_probe_enrollment", c.enrollment.staged_copy()
        )
        with pytest.raises(ValueError, match="same original"):
            run_capture(c)
    with monkeypatch.context() as patch:
        patch.setitem(c.service._view["publication"], "status", "PENDING")
        with pytest.raises(ValueError, match="published explicit settings"):
            run_capture(c)
    c.session._store = None
    with pytest.raises(ValueError, match="Refresh the existing"):
        run_capture(c)
    assert not owners
