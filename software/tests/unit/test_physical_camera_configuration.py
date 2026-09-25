"""Modeled physical-shaped wire records only; no helper, file or device effects.

These exercise the production pure joins, not received-hardware observations.
The independent hashes below are test references, never physical admission.
"""

from dataclasses import asdict, replace
import ctypes
import hashlib
from pathlib import Path
import subprocess

import pytest

from rocell.application import physical_camera_configuration as module
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_capture_registration import (
    HELPER_RELATIVE_PATH,
    create_native_camera_capture_runtime_registration,
    prepare_owned_native_capture,
)
from rocell.providers.windows.native_camera_capture_protocol import (
    native_camera_capture_release,
)
from rocell.providers.windows.native_camera_protocol import (
    NativeCameraReady,
    READY_SCHEMA,
    RESULT_SCHEMA,
    canonical,
    native_camera_release,
)
from rocell.providers.windows.native_camera_registration import PreparedOwnedNativeProbe
from rocell.providers.windows.owned_native_camera_evidence import (
    retain_owned_native_camera_run,
)
from test_native_camera_parent_admission import preparation as probe_preparation
from test_windows_camera_worker import BINDING, receipt


@pytest.fixture(autouse=True)
def forbid_process_and_devices(monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail("pure physical configuration test attempted process/device I/O")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(ctypes, "CDLL", forbidden)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, forbidden)


def reported_control(name, value=0, flags=2):
    return dict(
        control_id=name,
        minimum=0,
        maximum=10,
        step=2,
        default=0,
        capability_flags=3,
        value=value,
        flags=flags,
        unit="device_native_units",
    )


def modeled_native_evidence(prepared, raw, *, cleanup=(), held=False):
    """All process and driver observations here are explicit in-memory models."""
    if held:
        return retain_owned_native_camera_run(
            probe=prepared,
            fixture=None,
            deadline_ns=20_000_000_000,
            elapsed_ns=1,
            primary_error="PHYSICAL_PROVIDER_QUALIFICATION_HELD",
            cleanup_errors=(),
            observed={},
            ready_wire=b"",
            release_wire=b"",
            result=None,
            native_validated=False,
            admission_only_validated=False,
            release_check_passed=False,
            handshake=None,
        )
    request = prepared.admission_request
    ready = NativeCameraReady(
        canonical(
            dict(
                schema=READY_SCHEMA,
                request_sha256=request.request_sha256,
                child_pid=123,
                challenge="1" * 64,
            )
        )
    )
    ready_wire = ready.payload + b"\n"
    release = (
        native_camera_release
        if type(prepared) is PreparedOwnedNativeProbe
        else native_camera_capture_release
    )(request, ready)
    result = dict(
        schema=RESULT_SCHEMA,
        request_sha256=request.request_sha256,
        child_pid=123,
        challenge_sha256=ready.challenge_sha256,
        permit_sha256=request.to_dict()["permit_sha256"],
        native_receipt=raw,
    )
    native_ok = raw["status"] == "OK"
    observed = dict(
        created=True,
        resumed=True,
        tree_exited=True,
        returncode=0 if native_ok else 1,
        pid=123,
        written=len(request.wire()) + len(release),
        peak_handles=8,
        peak_processes=1,
        stdout_eof=True,
        stderr_eof=True,
        pending=False,
        handles_remaining=0,
        unclosed_handles_remaining=0,
        pins_remaining=0,
        stdout=ready_wire + canonical(result) + b"\n",
        stderr=b"MODELED_PRIVATE_DIAGNOSTIC",
    )
    return retain_owned_native_camera_run(
        probe=prepared,
        fixture=None,
        deadline_ns=20_000_000_000,
        elapsed_ns=1_000_000,
        primary_error=None if native_ok else "NATIVE_DIAGNOSTIC_FAILED",
        cleanup_errors=cleanup,
        observed=observed,
        ready_wire=ready_wire,
        release_wire=release,
        result=result,
        native_validated=True,
        admission_only_validated=False,
        release_check_passed=True,
        handshake=None,
    )


def capabilities_fixture(tmp_path, *, probe_fault=None):
    prepared = probe_preparation(tmp_path)
    raw = receipt("probe")
    raw["controls"] = [reported_control("brightness"), reported_control("gain")]
    if probe_fault == "native-cleanup":
        raw.update(status="FAILED", reason_code="SOURCE_SHUTDOWN_FAILED")
        raw["cleanup"]["source_shutdown_hr"] = -1
    if probe_fault == "unsupported":
        raw["modes"].append({**raw["modes"][0], "subtype": "MJPG"})
    evidence = modeled_native_evidence(
        prepared,
        raw,
        cleanup=("CLOSE_FAILED:job",) if probe_fault == "process-cleanup" else (),
        held=probe_fault == "held",
    )
    capabilities = module.derive_physical_camera_capabilities(
        evidence,
        expected_preparation=prepared,
        expected_evidence_sha256=evidence.evidence_sha256,
        expected_source_sha256="a" * 64,
    )
    return prepared, evidence, capabilities


def staged(capabilities, controls=None):
    if controls is None:
        # The operator selects typed settings; canonical ordering is owned here
        # before any logical capture plan or application permit is constructed.
        controls = (
            CameraControlSetting("gain", 2),
            CameraControlSetting("brightness", 4),
        )
    return module.stage_physical_camera_configuration(
        capabilities,
        capabilities.view()["modes"][0]["choice_id"],
        controls,
        expected_capabilities_sha256=capabilities.capabilities_sha256,
        expected_source_sha256="a" * 64,
        expected_session_id="session-unit",
        expected_selected_identity_sha256=BINDING.binding_sha256,
    )


def capture_fixture(tmp_path, configuration, *, fault=None, context=None):
    # Different helper/build-record pins by design: probe and capture have
    # separate reviewed purposes. Neither runtime is executed by these tests.
    source, session, binding = "a" * 64, "session-unit", BINDING
    if context == "source":
        source = "0" * 64
    if context == "session":
        session = "another-session"
    if context == "identity":
        binding = replace(binding, binding_sha256="0" * 64)
    if context == "endpoint":
        endpoint = "MODELED_OTHER_ENDPOINT"
        binding = replace(
            binding,
            symbolic_link=endpoint,
            endpoint_sha256=hashlib.sha256(endpoint.encode()).hexdigest(),
        )
    runtime = create_native_camera_capture_runtime_registration(
        tmp_path,
        source_sha256=source,
        catalog_sha256="8" * 64,
        helper_sha256="9" * 64,
        build_record_sha256="7" * 64,
    )
    directory = tmp_path / "capture-work"
    plan = WindowsCameraWorkerClient(
        tmp_path / HELPER_RELATIVE_PATH, "9" * 64
    ).prepare_capture(
        binding,
        configuration.mode,
        directory / "capture-attempt-capture",
        source_sha256=source,
        campaign_id="attempt-capture",
        budget=CameraCampaignBudget(5000, 1, 32, 32),
        controls=configuration.controls,
    )
    prepared = prepare_owned_native_capture(
        runtime,
        plan,
        session_id=session,
        operation_sha256="5" * 64,
        permit_sha256="6" * 64,
        working_directory=directory,
    )
    raw = receipt("capture")
    raw["selected_endpoint"] = binding.symbolic_link
    raw["devices"][0]["symbolic_link"] = binding.symbolic_link
    raw["requested_mode"] = asdict(configuration.mode)
    raw["controls"] = [
        reported_control(item.control_id, item.value, 1 if item.mode == "auto" else 2)
        for item in configuration.controls
    ]
    raw["counts"]["control_set_attempts"] = len(configuration.controls)
    if fault == "auto-value":
        raw["controls"][0]["value"] = 9
    if fault == "capability-drift":
        raw["controls"][0]["minimum"] = -2
    if fault in {"manual-drift", "mode-drift", "native-cleanup"}:
        raw.update(status="FAILED", reason_code="MODELED_NATIVE_FAILURE")
        if fault == "manual-drift":
            raw["controls"][0]["value"] = 6
        elif fault == "mode-drift":
            raw["observed_mode"]["fps_numerator"] = 18
        else:
            raw["cleanup"]["source_shutdown_hr"] = -1
        if fault != "native-cleanup":
            raw["frames"] = []
            raw["counts"].update(samples_received=0, frames_written=0)
    evidence = modeled_native_evidence(
        prepared,
        raw,
        cleanup=("CLOSE_FAILED:job",) if fault == "process-cleanup" else (),
        held=fault == "held",
    )
    return prepared, evidence


def physical_configuration_fixture(tmp_path):
    """Shared UI fixture; entirely modeled, physical-shaped evidence only."""
    probe, probe_evidence, capabilities = capabilities_fixture(tmp_path)
    candidate = staged(capabilities)
    capture, capture_evidence = capture_fixture(tmp_path, candidate)
    readback = module.compare_physical_camera_readback(
        candidate,
        capture_evidence,
        expected_preparation=capture,
        expected_capture_evidence_sha256=capture_evidence.evidence_sha256,
        expected_settings_epoch=candidate.settings_epoch,
    )
    return (
        probe,
        probe_evidence,
        capabilities,
        candidate,
        capture,
        capture_evidence,
        readback,
    )


def test_complete_join_is_distinct_reported_intent_and_readback(tmp_path):
    probe, pe, caps, cfg, capture, ce, readback = physical_configuration_fixture(
        tmp_path
    )
    assert (
        module.verify_physical_camera_capabilities(
            caps.payload,
            evidence=pe,
            expected_preparation=probe,
            expected_evidence_sha256=pe.evidence_sha256,
            expected_source_sha256="a" * 64,
            expected_capabilities_sha256=caps.capabilities_sha256,
        )
        == caps
    )
    assert (
        module.verify_physical_camera_configuration(
            cfg.payload,
            expected_capabilities=caps,
            expected_settings_epoch=cfg.settings_epoch,
        )
        == cfg
    )
    assert (
        module.verify_physical_camera_readback(
            readback.payload,
            configuration=cfg,
            capture_evidence=ce,
            expected_preparation=capture,
            expected_capture_evidence_sha256=ce.evidence_sha256,
            expected_settings_epoch=cfg.settings_epoch,
            expected_readback_sha256=readback.readback_sha256,
        )
        == readback
    )
    assert (
        probe.registration.executable.sha256 != capture.registration.executable.sha256
    )
    assert cfg.controls == (
        CameraControlSetting("brightness", 4),
        CameraControlSetting("gain", 2),
    )
    assert cfg.view()["applied"] is False
    assert readback.view()["status"] == "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
    assert readback.to_dict()["native_cleanup_confirmed"] is True
    assert readback.to_dict()["process_cleanup_confirmed"] is True
    assert readback.to_dict()["frame_content_verified"] is False
    for value in (caps, cfg, readback):
        assert (
            value.to_dict()["physical_authority"]
            is value.to_dict()["hardware_qualified"]
            is False
        )
        assert (
            b"REHEARSAL" not in value.payload
            and b"MODELED_PRIVATE_DIAGNOSTIC" not in value.payload
        )
        assert BINDING.symbolic_link not in str(value.view())


def test_all_operations_are_filesystem_inert_and_copy_isolated(tmp_path, monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail("pure configuration layer touched filesystem")

    with monkeypatch.context() as guard:
        for name in ("open", "stat", "lstat", "resolve", "mkdir", "iterdir"):
            guard.setattr(Path, name, forbidden)
        _, _, caps, cfg, _, _, readback = physical_configuration_fixture(tmp_path)
        for value in (caps, cfg, readback):
            original = value.payload
            detached = value.to_dict()
            detached["hardware_qualified"] = True
            assert (
                value.payload == original
                and value.to_dict()["hardware_qualified"] is False
            )


@pytest.mark.parametrize("fault", ["held", "native-cleanup", "process-cleanup"])
def test_probe_cannot_produce_capabilities_without_complete_clean_native_evidence(
    tmp_path, fault
):
    with pytest.raises(ValueError, match="COMPLETE_NATIVE_PROBE"):
        capabilities_fixture(tmp_path, probe_fault=fault)


def test_unsupported_reported_mode_is_retained_but_not_selectable(tmp_path):
    _, _, caps = capabilities_fixture(tmp_path, probe_fault="unsupported")
    row = caps.view()["modes"][1]
    assert not row["selectable"] and row["mode"]["subtype"] == "MJPG"
    with pytest.raises(ValueError, match="UNKNOWN_OR_UNSUPPORTED"):
        module.stage_physical_camera_configuration(
            caps,
            row["choice_id"],
            (),
            expected_capabilities_sha256=caps.capabilities_sha256,
            expected_source_sha256="a" * 64,
            expected_session_id="session-unit",
            expected_selected_identity_sha256=BINDING.binding_sha256,
        )


@pytest.mark.parametrize(
    "control,code",
    [
        (CameraControlSetting("brightness", 3), "CONTROL_OFF_STEP"),
        (CameraControlSetting("brightness", 12), "CONTROL_OUT_OF_RANGE"),
        (CameraControlSetting("exposure", 2), "CONTROL_NOT_REPORTED"),
    ],
)
def test_setting_selection_uses_only_reported_limits(tmp_path, control, code):
    _, _, caps = capabilities_fixture(tmp_path)
    with pytest.raises(ValueError, match=code):
        staged(caps, (control,))


@pytest.mark.parametrize("key", ["source", "session", "identity", "capabilities"])
def test_staging_rejects_stale_context(tmp_path, key):
    _, _, caps = capabilities_fixture(tmp_path)
    args = dict(
        expected_source_sha256="a" * 64,
        expected_session_id="session-unit",
        expected_selected_identity_sha256=BINDING.binding_sha256,
        expected_capabilities_sha256=caps.capabilities_sha256,
    )
    field = dict(
        source="expected_source_sha256",
        session="expected_session_id",
        identity="expected_selected_identity_sha256",
        capabilities="expected_capabilities_sha256",
    )[key]
    args[field] = "changed-session" if key == "session" else "0" * 64
    with pytest.raises(ValueError, match="STALE_NATIVE_CAPABILITIES"):
        module.stage_physical_camera_configuration(
            caps, caps.view()["modes"][0]["choice_id"], (), **args
        )


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("held", "NATIVE_RECEIPT_UNAVAILABLE"),
        ("manual-drift", "CONTROL_READBACK_MISMATCH"),
        ("mode-drift", "MODE_READBACK_MISMATCH"),
        ("native-cleanup", "NATIVE_CLEANUP_UNCONFIRMED"),
        ("process-cleanup", "PROCESS_CLEANUP_UNCONFIRMED"),
        ("capability-drift", "CONTROL_READBACK_MISMATCH"),
    ],
)
def test_capture_faults_remain_readback_mismatch_without_invented_success(
    tmp_path, fault, reason
):
    _, _, caps = capabilities_fixture(tmp_path)
    cfg = staged(caps)
    capture, evidence = capture_fixture(tmp_path, cfg, fault=fault)
    report = module.compare_physical_camera_readback(
        cfg,
        evidence,
        expected_preparation=capture,
        expected_capture_evidence_sha256=evidence.evidence_sha256,
        expected_settings_epoch=cfg.settings_epoch,
    ).to_dict()
    assert (
        report["status"] == "READBACK_MISMATCH_UNQUALIFIED"
        and reason in report["reasons"]
    )
    if fault == "held":
        assert report["observed_mode"] is None and all(
            row["observed"] is None for row in report["controls"]
        )
    if fault == "process-cleanup":
        assert report["native_cleanup_confirmed"] is True
    if fault == "native-cleanup":
        assert report["process_cleanup_confirmed"] is True


def test_auto_readback_is_flag_not_fixed_value_promise(tmp_path):
    _, _, caps = capabilities_fixture(tmp_path)
    cfg = staged(caps, (CameraControlSetting("brightness", 4, "auto"),))
    capture, evidence = capture_fixture(tmp_path, cfg, fault="auto-value")
    report = module.compare_physical_camera_readback(
        cfg,
        evidence,
        expected_preparation=capture,
        expected_capture_evidence_sha256=evidence.evidence_sha256,
        expected_settings_epoch=cfg.settings_epoch,
    )
    assert report.to_dict()["controls"][0]["observed"]["value"] == 9
    assert report.to_dict()["controls"][0]["matched"] is True


@pytest.mark.parametrize("kind", ["capabilities", "configuration", "readback"])
def test_rehearsal_schema_or_qualification_cannot_be_relabelled(tmp_path, kind):
    fixture = physical_configuration_fixture(tmp_path)
    value = dict(
        capabilities=fixture[2], configuration=fixture[3], readback=fixture[6]
    )[kind]
    document = value.to_dict()
    document["schema"] = "rocell.camera_" + kind + ".v1"
    with pytest.raises(ValueError):
        type(value)(canonical(document))
    document = value.to_dict()
    document["hardware_qualified"] = True
    with pytest.raises(ValueError):
        type(value)(canonical(document))


def test_rehashed_capability_tampering_cannot_change_retained_report(tmp_path):
    probe, pe, caps = capabilities_fixture(tmp_path)
    changed = caps.to_dict()
    changed["controls"][0]["maximum"] = 12
    forged = module.PhysicalCameraCapabilities(canonical(changed))
    with pytest.raises(ValueError, match="RETAINED_PROBE_MISMATCH"):
        module.verify_physical_camera_capabilities(
            forged.payload,
            evidence=pe,
            expected_preparation=probe,
            expected_evidence_sha256=pe.evidence_sha256,
            expected_source_sha256="a" * 64,
            expected_capabilities_sha256=forged.capabilities_sha256,
        )


def test_exact_original_capture_settings_are_not_substitutable(tmp_path):
    _, _, caps = capabilities_fixture(tmp_path)
    original = staged(caps)
    different = staged(caps, (CameraControlSetting("brightness", 2),))
    capture, evidence = capture_fixture(tmp_path, different)
    with pytest.raises(ValueError, match="REQUESTED_SETTINGS_MISMATCH"):
        module.compare_physical_camera_readback(
            original,
            evidence,
            expected_preparation=capture,
            expected_capture_evidence_sha256=evidence.evidence_sha256,
            expected_settings_epoch=original.settings_epoch,
        )


@pytest.mark.parametrize("context", ["source", "session", "identity", "endpoint"])
def test_capture_must_share_exact_reviewed_unit_and_source_context(tmp_path, context):
    _, _, caps = capabilities_fixture(tmp_path)
    cfg = staged(caps)
    capture, evidence = capture_fixture(tmp_path, cfg, context=context)
    with pytest.raises(ValueError, match="CONFIGURATION_CONTEXT_MISMATCH"):
        module.compare_physical_camera_readback(
            cfg,
            evidence,
            expected_preparation=capture,
            expected_capture_evidence_sha256=evidence.evidence_sha256,
            expected_settings_epoch=cfg.settings_epoch,
        )


@pytest.mark.parametrize(
    "kind",
    ["probe-evidence", "probe-source", "settings", "capture-evidence", "readback"],
)
def test_independent_trusted_hashes_are_mandatory(tmp_path, kind):
    probe, pe, caps, cfg, capture, ce, readback = physical_configuration_fixture(
        tmp_path
    )
    with pytest.raises(ValueError):
        if kind in {"probe-evidence", "probe-source"}:
            module.derive_physical_camera_capabilities(
                pe,
                expected_preparation=probe,
                expected_evidence_sha256=(
                    "0" * 64 if kind == "probe-evidence" else pe.evidence_sha256
                ),
                expected_source_sha256="0" * 64 if kind == "probe-source" else "a" * 64,
            )
        elif kind == "readback":
            module.verify_physical_camera_readback(
                readback.payload,
                configuration=cfg,
                capture_evidence=ce,
                expected_preparation=capture,
                expected_capture_evidence_sha256=ce.evidence_sha256,
                expected_settings_epoch=cfg.settings_epoch,
                expected_readback_sha256="0" * 64,
            )
        else:
            module.compare_physical_camera_readback(
                cfg,
                ce,
                expected_preparation=capture,
                expected_capture_evidence_sha256=(
                    "0" * 64 if kind == "capture-evidence" else ce.evidence_sha256
                ),
                expected_settings_epoch=(
                    "0" * 64 if kind == "settings" else cfg.settings_epoch
                ),
            )


def test_rehashed_settings_and_readback_must_rederive_from_exact_records(tmp_path):
    _, _, caps, cfg, capture, ce, readback = physical_configuration_fixture(tmp_path)
    changed = cfg.to_dict()
    changed["mode"]["fps_numerator"] = 18
    forged = module.StagedPhysicalCameraConfiguration(canonical(changed))
    with pytest.raises(ValueError, match="CAPABILITIES_MISMATCH"):
        module.verify_physical_camera_configuration(
            forged.payload,
            expected_capabilities=caps,
            expected_settings_epoch=forged.settings_epoch,
        )
    changed = readback.to_dict()
    changed["controls"][0]["observed"]["value"] = 6
    forged_readback = module.PhysicalCameraReadback(canonical(changed))
    with pytest.raises(ValueError, match="RETAINED_EVIDENCE_MISMATCH"):
        module.verify_physical_camera_readback(
            forged_readback.payload,
            configuration=cfg,
            capture_evidence=ce,
            expected_preparation=capture,
            expected_capture_evidence_sha256=ce.evidence_sha256,
            expected_settings_epoch=cfg.settings_epoch,
            expected_readback_sha256=forged_readback.readback_sha256,
        )


def test_empty_report_and_duplicate_modes_do_not_create_default_selection(tmp_path):
    probe = probe_preparation(tmp_path)
    raw = receipt("probe")
    raw["modes"] = []
    evidence = modeled_native_evidence(probe, raw)
    caps = module.derive_physical_camera_capabilities(
        evidence,
        expected_preparation=probe,
        expected_evidence_sha256=evidence.evidence_sha256,
        expected_source_sha256="a" * 64,
    )
    assert caps.view()["modes"] == [] and caps.view()["unavailable_controls"] == list(
        module.CONTROL_IDS
    )
    with pytest.raises(ValueError, match="UNKNOWN_OR_UNSUPPORTED"):
        module.stage_physical_camera_configuration(
            caps,
            "mode-" + "0" * 24,
            (),
            expected_capabilities_sha256=caps.capabilities_sha256,
            expected_source_sha256="a" * 64,
            expected_session_id="session-unit",
            expected_selected_identity_sha256=BINDING.binding_sha256,
        )
    raw = receipt("probe")
    raw["modes"] *= 2
    evidence = modeled_native_evidence(probe, raw)
    caps = module.derive_physical_camera_capabilities(
        evidence,
        expected_preparation=probe,
        expected_evidence_sha256=evidence.evidence_sha256,
        expected_source_sha256="a" * 64,
    )
    assert caps.view()["modes"][0]["choice_id"] != caps.view()["modes"][1]["choice_id"]


@pytest.mark.parametrize(
    "bad", [1, [], "mode-" + "0" * 100_000], ids=["integer", "array", "oversized"]
)
def test_mode_choice_is_a_bounded_opaque_id(tmp_path, bad):
    _, _, caps = capabilities_fixture(tmp_path)
    with pytest.raises(ValueError, match="EXACT_MODE_CHOICE"):
        module.stage_physical_camera_configuration(
            caps,
            bad,
            (),
            expected_capabilities_sha256=caps.capabilities_sha256,
            expected_source_sha256="a" * 64,
            expected_session_id="session-unit",
            expected_selected_identity_sha256=BINDING.binding_sha256,
        )


@pytest.mark.parametrize("field,value", [("reasons", [{}]), ("native_status", [])])
def test_malformed_readback_fields_return_contract_error(tmp_path, field, value):
    readback = physical_configuration_fixture(tmp_path)[-1]
    document = readback.to_dict()
    document[field] = value
    with pytest.raises(ValueError):
        module.PhysicalCameraReadback(canonical(document))
