"""Full-resolution *metadata models*, not images, throughput or live hardware.

Production legacy/v2 codecs reconstruct the subjects. V2 uses a modeled process
owner with real protocol parsing; process creation and device calls are forbidden.
No pixel buffer or original store is created by these fixtures.
"""

from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from rocell.application import camera_operating_proposal as policy
from rocell.application import camera_operating_evidence_preflight as module
from rocell.application import physical_camera_configuration as configuration
from rocell.application.camera_activation_campaign_evidence import (
    camera_activation_evidence,
)
from rocell.application.physical_camera_mode_entry import (
    HASH_FIELDS,
    build_camera_mode_entry,
)
from rocell.providers.windows import native_camera_activation_supervisor as supervisor
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
    CameraEndpointBinding,
    NativeCameraMode,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_activation_registration import (
    create_activation_runtime,
    helper_relative_path,
    prepare_owned_activation,
)
from rocell.providers.windows.native_camera_activation_protocol import (
    activation_release,
)
from rocell.providers.windows.native_camera_registration import (
    HELPER_RELATIVE_PATH as PROBE_HELPER,
    create_native_camera_runtime_registration,
    prepare_owned_native_probe,
)
from rocell.providers.windows.native_camera_capture_registration import (
    HELPER_RELATIVE_PATH as CAPTURE_HELPER,
    create_native_camera_capture_runtime_registration,
    prepare_owned_native_capture,
)
from rocell.providers.windows.native_camera_protocol import (
    canonical,
    digest,
    FRAME_BYTES,
)
from rocell.vision.camera_profile import DEFAULT_B0477_CAMERA_PROFILE
from test_physical_camera_configuration import (
    forbid_process_and_devices,
    modeled_native_evidence,
    reported_control,
)
from test_native_camera_activation_evidence import modeled
from test_native_camera_activation_expectation import build, enrollment
from test_native_camera_activation_protocol import fixture as result_fixture, ready_for
from test_native_camera_activation_supervisor import ModelOwner, run, no_physical_owner
from test_windows_camera_worker import BINDING, receipt

SESSION = "physical-camera-" + "2" * 32
ENTRY_ID = "cameramode-" + "9" * 32
CONTEXT_KEYS = (
    "entry_payload",
    "expected_entry_id",
    "expected_entry_binding",
    "purchase_profile_payload",
    "expected_purchase_profile_sha256",
    "configuration_payload",
    "expected_settings_epoch",
)


def _prepare(directory, purpose, version, attempt, mode, controls, helper="c" * 64):
    expectation = build(enrollment()) if version == "v2" else None
    endpoint = (
        expectation.to_dict()["endpoint"] if expectation else BINDING.symbolic_link
    )
    binding = CameraEndpointBinding(endpoint, digest(endpoint.encode()), "b" * 64)
    if version == "v2":
        runtime = create_activation_runtime(
            directory,
            purpose=purpose,
            source_sha256="a" * 64,
            catalog_sha256="b" * 64,
            helper_sha256=helper,
            build_record_sha256="d" * 64,
        )
        relative = helper_relative_path(purpose)
    else:
        factory = (
            create_native_camera_runtime_registration
            if purpose == "probe"
            else create_native_camera_capture_runtime_registration
        )
        runtime = factory(
            directory,
            source_sha256="a" * 64,
            catalog_sha256="b" * 64,
            helper_sha256=helper,
            build_record_sha256="d" * 64,
        )
        relative = PROBE_HELPER if purpose == "probe" else CAPTURE_HELPER
    client = WindowsCameraWorkerClient(directory / relative, helper)
    kwargs = dict(source_sha256="a" * 64, campaign_id=attempt)
    work = directory / attempt
    plan = (
        client.prepare_probe(
            binding,
            budget=CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES),
            **kwargs,
        )
        if purpose == "probe"
        else client.prepare_capture(
            binding,
            mode,
            work / ("capture-" + attempt),
            budget=CameraCampaignBudget(5000, 1, 64 * 1024**2, 64 * 1024**2),
            controls=controls,
            **kwargs,
        )
    )
    common = dict(
        session_id=SESSION,
        operation_sha256=digest((attempt + "-operation").encode()),
        permit_sha256=digest((attempt + "-permit").encode()),
        working_directory=work,
    )
    if version == "v2":
        return prepare_owned_activation(runtime, plan, expectation, **common), binding
    prepare = (
        prepare_owned_native_probe
        if purpose == "probe"
        else prepare_owned_native_capture
    )
    return prepare(runtime, plan, **common), binding


def _evidence(directory, monkeypatch, prepared, raw, version, *, fault=None):
    if version == "legacy":
        evidence = modeled_native_evidence(
            prepared,
            raw,
            cleanup=("CLOSE_FAILED:job",) if fault == "cleanup" else (),
        )
        return module.CameraNativeEvidenceSubject(
            prepared, evidence, evidence.evidence_sha256
        )
    purpose = prepared.admission_request.purpose
    owner, args = modeled(directory, purpose)
    ready = ready_for(prepared.admission_request)
    release = activation_release(
        prepared.admission_request, ready, expected_child_pid=123
    )
    raw_result = result_fixture(purpose)[2]
    raw_result.update(
        request_sha256=prepared.admission_request.request_sha256,
        permit_sha256=prepared.admission_request.to_dict()["permit_sha256"],
        native_receipt=raw,
    )
    wire = canonical(raw_result) + b"\n"
    owner.stdout = ready.payload + b"\n" + wire
    args.update(
        prepared=prepared,
        ready_wire=ready.payload + b"\n",
        release_wire=release,
        accepted_result_sha256=digest(wire),
    )
    model_owner = ModelOwner(
        owner, args, "cleanup-error" if fault == "cleanup" else None
    )
    if raw["status"] != "OK":
        old_poll = model_owner.poll

        def poll(budget):
            done = old_poll(budget)
            if model_owner.returncode is not None:
                model_owner.returncode = 1
            return done

        model_owner.poll = poll
    monkeypatch.setattr(supervisor, "_new_owner", lambda: model_owner)
    outcome = run(prepared, lambda exact: None)
    artifacts = camera_activation_evidence(prepared, outcome)
    return module.CameraNativeEvidenceSubject(
        prepared, artifacts, artifacts[0].payload_sha256, artifacts[1].payload_sha256
    )


def case(tmp_path, monkeypatch, *, fps=8, version="v2", controls=None, fraction=1):
    """Return independently held test references and a factory for separate captures."""
    mode = NativeCameraMode(5472, 3648, fps * fraction, fraction)
    if controls is None:
        controls = (
            CameraControlSetting("exposure", 2),
            CameraControlSetting("white_balance", 4),
        )
    prepared, binding = _prepare(tmp_path, "probe", version, "probe-one", mode, ())
    raw = receipt("probe")
    raw["selected_endpoint"] = raw["devices"][0]["symbolic_link"] = (
        binding.symbolic_link
    )
    raw["modes"] = [asdict(mode)]
    raw["controls"] = [reported_control("exposure"), reported_control("white_balance")]
    probe = _evidence(tmp_path, monkeypatch, prepared, raw, version)
    caps = configuration.derive_physical_camera_capabilities(
        probe.evidence,
        expected_preparation=prepared,
        expected_evidence_sha256=probe.expected_evidence_sha256,
        expected_supervision_sha256=probe.expected_supervision_sha256,
        expected_source_sha256="a" * 64,
    )
    staged = configuration.stage_physical_camera_configuration(
        caps,
        caps.view()["modes"][0]["choice_id"],
        controls,
        expected_capabilities_sha256=caps.capabilities_sha256,
        expected_source_sha256="a" * 64,
        expected_session_id=SESSION,
        expected_selected_identity_sha256=binding.binding_sha256,
    )
    entry_binding = dict(
        **{key: "a" * 64 for key in HASH_FIELDS},
        cell_id="wizard-physical-camera-" + "1" * 16,
        session_id=SESSION,
        origin_launch_id="wizard-" + "3" * 32,
        entry_launch_id="wizard-" + "4" * 32,
    )
    entry = build_camera_mode_entry(
        entry_id=ENTRY_ID,
        binding=entry_binding,
        operator_id="MODELED entry operator",
        recorded_at_utc_ns=123,
    )
    profile = DEFAULT_B0477_CAMERA_PROFILE.read_bytes()
    context = dict(
        entry_payload=entry.payload,
        expected_entry_id=ENTRY_ID,
        expected_entry_binding=entry_binding,
        purchase_profile_payload=profile,
        expected_purchase_profile_sha256=digest(profile),
        configuration_payload=staged.payload,
        expected_settings_epoch=staged.settings_epoch,
    )
    proposal = policy.build_camera_operating_proposal(
        proposal_id="modepolicy-" + "1" * 32,
        operator_id="MODELED proposal operator",
        recorded_at_utc_ns=456,
        rationale="Explicit modeled mode for metadata tests.",
        variance_rationale=(
            "Evaluate 8 fps without changing the 9 fps purchase reference."
            if fps == 8
            else None
        ),
        **context,
    )

    def capture(attempt, *, fault=None, observed_fraction=1, helper="c" * 64):
        prepared, binding = _prepare(
            tmp_path, "capture", version, attempt, mode, staged.controls, helper
        )
        raw = receipt("capture")
        raw["selected_endpoint"] = raw["devices"][0]["symbolic_link"] = (
            binding.symbolic_link
        )
        observed = asdict(
            replace(
                mode,
                fps_numerator=fps * observed_fraction,
                fps_denominator=observed_fraction,
                stride_bytes=10944,
            )
        )
        raw.update(
            modes=[observed],
            requested_mode=asdict(mode),
            observed_mode=observed,
            controls=[
                reported_control(c.control_id, c.value, 2 if c.mode == "manual" else 1)
                for c in staged.controls
            ],
        )
        raw["frames"][0].update(length_bytes=5472 * 3648 * 2, stride_bytes=10944)
        raw["counts"]["control_set_attempts"] = len(staged.controls)
        if fault in (
            "value",
            "auto",
            "capability",
            "failed9",
            "native_cleanup",
            "missing_control",
        ):
            raw.update(status="FAILED", reason_code="MODELED_DIAGNOSTIC_FAILURE")
            raw["frames"] = []
            raw["counts"].update(samples_received=0, frames_written=0)
            if fault == "value":
                raw["controls"][0]["value"] = 6
            elif fault == "auto":
                raw["controls"][0]["flags"] = 1
            elif fault == "capability":
                raw["controls"][0]["minimum"] = -2
            elif fault == "failed9":
                raw["observed_mode"]["fps_numerator"] = 8
            elif fault == "native_cleanup":
                raw["cleanup"]["source_shutdown_hr"] = -1
            else:
                raw["controls"] = []
        if fault == "layout":
            raw["observed_mode"]["stride_bytes"] += 16
            raw["frames"][0].update(
                length_bytes=(10944 + 16) * 3648, stride_bytes=10944 + 16
            )
        subject = _evidence(tmp_path, monkeypatch, prepared, raw, version, fault=fault)
        readback = configuration.compare_physical_camera_readback(
            staged,
            subject.evidence,
            expected_preparation=prepared,
            expected_capture_evidence_sha256=subject.expected_evidence_sha256,
            expected_supervision_sha256=subject.expected_supervision_sha256,
            expected_settings_epoch=staged.settings_epoch,
        )
        return module.CameraReadbackSubject(
            subject, readback.payload, readback.readback_sha256
        )

    return (
        dict(
            **context,
            proposal_payload=proposal.payload,
            expected_proposal_sha256=proposal.sha256,
            capabilities_payload=caps.payload,
            expected_capabilities_sha256=caps.capabilities_sha256,
            probe=probe,
            captures=(),
        ),
        capture,
    )


def assess(inputs, captures=()):
    return module.assess_camera_operating_evidence(**{**inputs, "captures": captures})


@pytest.mark.parametrize("version", ["legacy", "v2"])
@pytest.mark.parametrize("fps,fraction", [(8, 1), (9, 1), (8, 1000), (9, 1000)])
def test_two_distinct_rederived_reports_are_consistent_not_approved(
    tmp_path, monkeypatch, version, fps, fraction
):
    inputs, capture = case(
        tmp_path, monkeypatch, version=version, fps=fps, fraction=fraction
    )
    captures = (capture("capture-one"), capture("capture-two", observed_fraction=2))
    report = assess(inputs, captures)
    data = report.to_dict()
    assert data["status"] == "CONSISTENT_METADATA_PENDING_ORIGINAL_REVIEW"
    assert not data["failed_checks"]
    assert all(data[key] is False for key in policy.FALSE_FIELDS)
    assert data["owner_obligations"] == list(module.OWNER_OBLIGATIONS)
    assert (
        module.verify_camera_operating_evidence_preflight(
            report.payload,
            expected_preflight_sha256=report.sha256,
            **{**inputs, "captures": captures},
        )
        == report
    )
    data["checks"][0]["satisfied"] = False
    assert report.to_dict()["checks"][0]["satisfied"] is True
    proposed = policy.CameraOperatingProposal(inputs["proposal_payload"]).to_dict()
    assert proposed["target_mode"]["fps_numerator"] == fps * fraction
    assert proposed["target_mode"]["fps_denominator"] == fraction
    # Separate historical entry/current selection domains; no implied continuity.
    assert (
        proposed["entry_binding"]["selected_identity_sha256"]
        != proposed["probe_binding"]["selected_identity_sha256"]
    )


@pytest.mark.parametrize("count", [0, 1])
def test_missing_reports_remain_blocked(tmp_path, monkeypatch, count):
    inputs, capture = case(tmp_path, monkeypatch)
    report = assess(inputs, () if count == 0 else (capture("capture-one"),)).to_dict()
    assert report["status"] == "BLOCKED_METADATA"
    assert report["failed_checks"] == list(module.CHECK_IDS[1:])


@pytest.mark.parametrize(
    "controls",
    [
        (),
        (CameraControlSetting("exposure", 2),),
        (
            CameraControlSetting("exposure", 2, "auto"),
            CameraControlSetting("white_balance", 4),
        ),
    ],
)
def test_required_manual_controls_are_not_inferred(tmp_path, monkeypatch, controls):
    inputs, capture = case(tmp_path, monkeypatch, controls=controls)
    report = assess(inputs, (capture("capture-one"), capture("capture-two"))).to_dict()
    assert report["failed_checks"] == [module.CHECK_IDS[0]]


@pytest.mark.parametrize("version", ["legacy", "v2"])
@pytest.mark.parametrize(
    "fault",
    [
        "value",
        "auto",
        "capability",
        "failed9",
        "native_cleanup",
        "missing_control",
        "cleanup",
    ],
)
def test_failed_or_drifting_report_cannot_be_repaired_by_policy(
    tmp_path, monkeypatch, version, fault
):
    inputs, capture = case(
        tmp_path, monkeypatch, version=version, fps=9 if fault == "failed9" else 8
    )
    reports = (capture("capture-one"), capture("capture-two", fault=fault))
    data = assess(inputs, reports).to_dict()
    assert data["status"] == "BLOCKED_METADATA"
    assert module.CHECK_IDS[3] in data["failed_checks"]


@pytest.mark.parametrize(
    "fault,check", [("duplicate", 2), ("runtime", 5), ("layout", 4)]
)
def test_distinct_runtime_and_layout_constraints(tmp_path, monkeypatch, fault, check):
    inputs, capture = case(tmp_path, monkeypatch)
    first = capture("capture-one")
    second = (
        first
        if fault == "duplicate"
        else capture(
            "capture-two",
            helper="d" * 64 if fault == "runtime" else "c" * 64,
            fault="layout" if fault == "layout" else None,
        )
    )
    assert (
        module.CHECK_IDS[check]
        in assess(inputs, (first, second)).to_dict()["failed_checks"]
    )


@pytest.mark.parametrize(
    "key",
    [
        "expected_proposal_sha256",
        "expected_purchase_profile_sha256",
        "expected_capabilities_sha256",
        "expected_settings_epoch",
    ],
)
def test_changed_independent_hash_is_rejected(tmp_path, monkeypatch, key):
    inputs, _ = case(tmp_path, monkeypatch)
    inputs[key] = "f" * 64
    with pytest.raises(module.CameraOperatingPreflightError):
        assess(inputs)


@pytest.mark.parametrize(
    "key",
    [
        "source_sha256",
        "header_sha256",
        "configuration_epochs_sha256",
        "selected_identity_sha256",
        "complete_review_event_sha256",
        "entry_launch_id",
    ],
)
def test_changed_entry_context_is_rejected(tmp_path, monkeypatch, key):
    inputs, _ = case(tmp_path, monkeypatch)
    inputs["expected_entry_binding"][key] = (
        "wizard-" + "5" * 32 if key == "entry_launch_id" else "f" * 64
    )
    with pytest.raises(module.CameraOperatingPreflightError):
        assess(inputs)


def test_same_profile_meaning_with_changed_original_bytes_is_not_rebound(
    tmp_path, monkeypatch
):
    inputs, _ = case(tmp_path, monkeypatch)
    inputs["purchase_profile_payload"] += b"\n"
    inputs["expected_purchase_profile_sha256"] = digest(
        inputs["purchase_profile_payload"]
    )
    with pytest.raises(module.CameraOperatingPreflightError):
        assess(inputs)


@pytest.mark.parametrize(
    "target", ["probe", "capture", "readback", "supervision", "v2-domain"]
)
def test_native_subject_references_are_not_replaced_by_success_flags(
    tmp_path, monkeypatch, target
):
    inputs, capture = case(tmp_path, monkeypatch)
    first = capture("capture-one")
    if target == "probe":
        inputs["probe"] = replace(inputs["probe"], expected_evidence_sha256="f" * 64)
    elif target == "readback":
        first = replace(first, expected_readback_sha256="f" * 64)
    elif target == "supervision":
        first = replace(
            first, native=replace(first.native, expected_supervision_sha256="f" * 64)
        )
    elif target == "v2-domain":
        first = replace(
            first, native=replace(first.native, expected_supervision_sha256=None)
        )
    else:
        first = replace(
            first, native=replace(first.native, expected_evidence_sha256="f" * 64)
        )
    with pytest.raises(module.CameraOperatingPreflightError):
        assess(inputs, (first,))


def test_forged_self_consistent_readback_is_rederived(tmp_path, monkeypatch):
    inputs, capture = case(tmp_path, monkeypatch)
    good, bad = capture("capture-one"), capture("capture-two", fault="value")
    value = json.loads(good.readback_payload)
    # Retain the bad attempt's bindings but copy successful comparison fields.
    original = json.loads(bad.readback_payload)
    for key in (
        "capture_binding",
        "capture_preparation_sha256",
        "capture_evidence_sha256",
        "capture_request_sha256",
    ):
        value[key] = original[key]
    payload = canonical(value)
    forged = replace(
        bad, readback_payload=payload, expected_readback_sha256=digest(payload)
    )
    with pytest.raises(module.CameraOperatingPreflightError):
        assess(inputs, (good, forged))


def test_forged_preflight_checks_require_original_reconstruction(tmp_path, monkeypatch):
    inputs, _ = case(tmp_path, monkeypatch)
    data = assess(inputs).to_dict()
    for check in data["checks"]:
        check["satisfied"] = True
    data.update(failed_checks=[], status="CONSISTENT_METADATA_PENDING_ORIGINAL_REVIEW")
    payload = canonical(data)
    with pytest.raises(module.CameraOperatingPreflightError):
        module.verify_camera_operating_evidence_preflight(
            payload, expected_preflight_sha256=digest(payload), **inputs
        )


@pytest.mark.parametrize("fault", ["three", "list", "untyped"])
def test_capture_subjects_are_bounded_and_typed(tmp_path, monkeypatch, fault):
    inputs, capture = case(tmp_path, monkeypatch)
    first = capture("capture-one")
    bad = (first,) * 3 if fault == "three" else [first] if fault == "list" else ({},)
    with pytest.raises(module.CameraOperatingPreflightError):
        assess(inputs, bad)


@pytest.mark.parametrize(
    "fault",
    [
        "flag",
        "integer_flag",
        "extra",
        "duplicate",
        "noncanonical",
        "oversized",
        "obligations",
        "check_order",
    ],
)
def test_closed_preflight_payload(tmp_path, monkeypatch, fault):
    inputs, _ = case(tmp_path, monkeypatch)
    data = assess(inputs).to_dict()
    if fault == "flag":
        data["stage_passed"] = True
    elif fault == "integer_flag":
        data["stage_passed"] = 0
    elif fault == "extra":
        data["approved"] = True
    elif fault == "obligations":
        data["owner_obligations"] = []
    elif fault == "check_order":
        data["checks"].reverse()
    payload = canonical(data)
    if fault == "duplicate":
        payload = b'{"schema":"ignored",' + payload[1:]
    elif fault == "noncanonical":
        payload += b"\n"
    elif fault == "oversized":
        payload = b" " * (module.MAX_BYTES + 1)
    with pytest.raises(module.CameraOperatingPreflightError):
        module.CameraOperatingEvidencePreflight(payload)


@pytest.mark.parametrize(
    "fps,fault",
    [
        (8, "missing_variance"),
        (8, "blank_variance"),
        (9, "unexpected_variance"),
        (8, "operator"),
        (8, "bool_time"),
        (8, "rationale"),
        (8, "oversized_rationale"),
        (8, "id"),
        (8, "authority"),
    ],
)
def test_policy_proposal_is_explicit_bounded_and_never_approval(
    tmp_path, monkeypatch, fps, fault
):
    inputs, _ = case(tmp_path, monkeypatch, fps=fps)
    data = policy.CameraOperatingProposal(inputs["proposal_payload"]).to_dict()
    key, value = {
        "missing_variance": ("variance_rationale", None),
        "blank_variance": ("variance_rationale", " "),
        "unexpected_variance": ("variance_rationale", "Not a variance"),
        "operator": ("operator_id", "\noperator"),
        "bool_time": ("recorded_at_utc_ns", True),
        "rationale": ("rationale", "bad\x00text"),
        "oversized_rationale": ("rationale", "x" * 1025),
        "id": ("proposal_id", "../policy"),
        "authority": ("approved_operating_policy", True),
    }[fault]
    data[key] = value
    with pytest.raises(policy.CameraOperatingProposalError):
        policy.CameraOperatingProposal(canonical(data))


def test_preflight_has_no_file_or_device_effects(tmp_path, monkeypatch):
    inputs, capture = case(tmp_path, monkeypatch)
    captures = (capture("capture-one"), capture("capture-two"))

    def forbidden(*args, **kwargs):
        pytest.fail("Preflight attempted filesystem or owner access")

    with monkeypatch.context() as patch:
        for name in ("open", "read_bytes", "write_bytes", "stat", "resolve", "mkdir"):
            patch.setattr(Path, name, forbidden)
        patch.setattr(supervisor, "_new_owner", forbidden)
        assert (
            assess(inputs, captures).to_dict()["status"]
            == "CONSISTENT_METADATA_PENDING_ORIGINAL_REVIEW"
        )


@pytest.mark.parametrize(
    "fault",
    [
        "unsupported_fps",
        "different_dimensions",
        "different_format",
        "missing_mode_field",
        "reference_changed",
        "extra_binding",
        "bad_binding_hash",
        "source_join",
        "duplicate",
        "noncanonical",
        "oversized",
    ],
)
def test_proposal_exact_schema_and_policy_limits(tmp_path, monkeypatch, fault):
    inputs, _ = case(tmp_path, monkeypatch)
    data = policy.CameraOperatingProposal(inputs["proposal_payload"]).to_dict()
    if fault == "unsupported_fps":
        data["target_mode"]["fps_numerator"] = 10
    elif fault == "different_dimensions":
        data["target_mode"]["width"] = 1920
    elif fault == "different_format":
        data["target_mode"]["subtype"] = "MJPG"
    elif fault == "missing_mode_field":
        del data["target_mode"]["stride_bytes"]
    elif fault == "reference_changed":
        data["reference_mode"]["fps_numerator"] = 8
    elif fault == "extra_binding":
        data["probe_binding"]["approved"] = True
    elif fault == "bad_binding_hash":
        data["entry_binding"]["header_sha256"] = "0" * 64
    elif fault == "source_join":
        data["probe_binding"]["source_sha256"] = "f" * 64
    payload = canonical(data)
    if fault == "duplicate":
        payload = b'{"schema":"ignored",' + payload[1:]
    elif fault == "noncanonical":
        payload += b"\n"
    elif fault == "oversized":
        payload = b" " * (policy.MAX_BYTES + 1)
    with pytest.raises(policy.CameraOperatingProposalError):
        policy.CameraOperatingProposal(payload)


def test_reordered_capture_subjects_cannot_verify_a_saved_preflight(
    tmp_path, monkeypatch
):
    inputs, capture = case(tmp_path, monkeypatch)
    original = (capture("capture-one"), capture("capture-two"))
    report = assess(inputs, original)
    with pytest.raises(module.CameraOperatingPreflightError):
        module.verify_camera_operating_evidence_preflight(
            report.payload,
            expected_preflight_sha256=report.sha256,
            **{**inputs, "captures": tuple(reversed(original))},
        )


def test_changed_operator_rationale_cannot_verify_the_original_proposal(
    tmp_path, monkeypatch
):
    inputs, _ = case(tmp_path, monkeypatch)
    data = policy.CameraOperatingProposal(inputs["proposal_payload"]).to_dict()
    data["variance_rationale"] = "A different operator rationale."
    payload = canonical(data)
    with pytest.raises(policy.CameraOperatingProposalError):
        policy.verify_camera_operating_proposal(
            payload,
            expected_proposal_sha256=inputs["expected_proposal_sha256"],
            **{key: inputs[key] for key in CONTEXT_KEYS},
        )
