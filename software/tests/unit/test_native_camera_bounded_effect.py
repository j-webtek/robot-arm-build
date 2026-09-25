"""Modeled native/OS observations through real codecs, handshake and core.

No native helper, process, device, file capture or physical qualification runs.
The scoped tests replace only the unqualified runner at the test boundary; the
production runner's independent pre-owner hold is covered unchanged elsewhere.
"""

from dataclasses import asdict
import base64
import ctypes
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace

import pytest

from rocell.application import physical_native_camera_campaign as campaign_module
from rocell.application.native_camera_bounded_effect import (
    NativeCameraEffectCounts,
    assess_native_camera_bounded_effect,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.cell_commissioning_coordinator import ObservedPowerState
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.native_camera_parent_admission import (
    NativeCameraParentHandshake,
)
from rocell.providers.windows.native_camera_protocol import canonical
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
)
from rocell.safety.effects import EffectCertainty

from test_physical_camera_configuration import modeled_native_evidence, reported_control
from test_physical_native_camera_campaign import campaign_fixture, components, SOURCE
from test_windows_camera_worker import receipt


@pytest.fixture(autouse=True)
def no_process_or_device(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("bounded effect test attempted a process or device")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(ctypes, "CDLL", forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, forbidden)


def modeled_effect_evidence(
    prepared,
    *,
    deadline_ns,
    fault=None,
    cancellation=None,
    revalidate=lambda exact: None,
):
    """Closed test-only packets with the actual pure parent state machine.

    All native/process observations are modeled, not observed from hardware.
    There is deliberately no runtime factory or enable switch in production.
    """
    request = prepared.camera_plan.request
    operation = request.operation
    raw = receipt(operation)
    raw["selected_endpoint"] = request.binding.symbolic_link
    raw["devices"][0]["symbolic_link"] = request.binding.symbolic_link
    if operation == "capture":
        mode = asdict(request.mode)
        raw["requested_mode"] = mode
        raw["observed_mode"] = {**mode, "stride_bytes": 8}
        raw["modes"] = [dict(raw["observed_mode"])]
        raw["controls"] = [
            reported_control(
                item.control_id, item.value, 1 if item.mode == "auto" else 2
            )
            for item in request.controls
        ]
        raw["counts"]["control_set_attempts"] = len(request.controls)
        template = raw["frames"][0]
        raw["frames"] = [
            {
                **template,
                "filename": f"frame-{index:06d}.yuy2",
                "host_sequence": index,
                "media_timestamp_100ns": index,
                "host_arrival_qpc": 1234567 + index,
            }
            for index in range(request.budget.max_frames)
        ]
        raw["counts"]["frames_written"] = request.budget.max_frames
        raw["counts"]["samples_received"] = request.budget.max_frames
    if fault in {"native-cleanup", "native-failure"}:
        raw.update(status="FAILED", reason_code="SOURCE_SHUTDOWN_FAILED")
        if fault == "native-cleanup":
            raw["cleanup"]["source_shutdown_hr"] = -1
    evidence = modeled_native_evidence(prepared, raw, held=fault == "held")
    data = evidence.to_dict()
    data["parent_deadline_ns"] = deadline_ns
    if fault == "held":
        return OwnedNativeCameraRunEvidence(canonical(data))

    # No fake "final state" literal: drive actual Python admission/result
    # validation, using a deterministic modeled clock and modeled process PID.
    parent = NativeCameraParentHandshake(
        prepared,
        cancellation=cancellation or threading.Event(),
        revalidate_consumed_permit=revalidate,
        _clock=lambda: 1,
    )
    parent.begin(deadline_ns=deadline_ns)
    ready = base64.b64decode(data["ready_wire"]["base64"])
    parent.accept_ready(ready, owned_child_pid=data["process"]["pid"])
    parent.check_release()
    parent.accept_result(
        base64.b64decode(data["stdout"]["base64"])[len(ready) :],
        returncode=data["process"]["returncode"],
    )
    data["handshake"] = parent.view()
    if fault in {"cancelled", "timed-out", "protocol-error"}:
        data["primary_error"] = {
            "cancelled": "CANCELLED",
            "timed-out": "TIMED_OUT",
            "protocol-error": "RESULT_PROTOCOL_FAILED",
        }[fault]
        data["status"] = {
            "cancelled": "CANCELLED",
            "timed-out": "TIMED_OUT",
            "protocol-error": "FAILED",
        }[fault]
    elif fault in {"process-cleanup", "retained-handles"}:
        data["cleanup_errors"] = [
            (
                "CLOSE_FAILED:job"
                if fault == "process-cleanup"
                else "PROCESS_RESOURCES_RETAINED"
            )
        ]
        data["status"] = "FAILED"
        if fault == "retained-handles":
            data["process"]["handles_remaining"] = 1
    elif fault == "missing-handshake":
        data["handshake"] = None
    elif fault == "unfinished-handshake":
        data["handshake"]["state"] = "RELEASE_CHECK_PASSED_DELIVERY_UNOBSERVED"
    elif fault == "partial-lifecycle":
        data["native_validated"] = False
        data["validated_result"] = None
        data["primary_error"] = "RESULT_PROTOCOL_FAILED"
        data["status"] = "FAILED"
        data["process"]["stdout_eof"] = False
        data["stdout"]["capture_complete"] = False
        data["stdout"]["omitted_bytes_exact"] = None
        data["handshake"]["state"] = "FAILED_NO_RETRY"
    elif fault == "wrong-deadline":
        data["parent_deadline_ns"] += 1
    elif fault == "duration":
        data["elapsed_ns"] = 25_000_000_000
    elif fault == "handle-budget":
        data["process"]["peak_handles"] = (
            prepared.registration.budget.observed_handles_per_process + 1
        )
    return OwnedNativeCameraRunEvidence(canonical(data))


def effect_fixture(tmp_path, *, capture=False, fault=None):
    campaign = campaign_fixture(tmp_path, capture=capture)
    core, store, permit = components(campaign)
    prepared = campaign.preparation_for_permit(permit)
    evidence = modeled_effect_evidence(
        prepared, deadline_ns=permit.expires_at_ns, fault=fault
    )
    return SimpleNamespace(
        campaign=campaign,
        core=core,
        store=store,
        permit=permit,
        prepared=prepared,
        evidence=evidence,
    )


def assess(model, **changes):
    return assess_native_camera_bounded_effect(
        model.evidence,
        **{
            "expected_preparation": model.prepared,
            "expected_evidence_sha256": model.evidence.evidence_sha256,
            "expected_deadline_ns": model.permit.expires_at_ns,
            "maximum_elapsed_ns": model.permit.registration.budget.timeout_ms
            * 1_000_000,
            **changes,
        },
    )


@pytest.mark.parametrize("capture", [False, True])
def test_complete_matching_probe_or_capture_has_known_effect_not_authority(
    tmp_path, monkeypatch, capture
):
    model = effect_fixture(tmp_path, capture=capture)
    original = model.evidence.payload

    def forbidden(*args, **kwargs):
        pytest.fail("pure effect assessment read a file")

    with monkeypatch.context() as guard:
        for name in ("open", "stat", "lstat", "iterdir", "mkdir", "resolve"):
            guard.setattr(Path, name, forbidden)
        effect = assess(model)
    assert effect.effect_certainty is EffectCertainty.CONFIRMED
    assert effect.reasons == ()
    assert effect.cleanup_confirmed
    assert effect.counts == NativeCameraEffectCounts(
        1, 1, int(capture), 2 if capture else 0, 2 if capture else 0, 1
    )
    assert model.evidence.payload == original
    document = model.evidence.to_dict()
    assert document["physical_authority"] is document["hardware_qualified"] is False
    assert document["provenance"] == "PHYSICAL_UNQUALIFIED"
    assert document["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    assert not model.prepared.runtime.to_dict()["dispatch_enabled"]
    if capture:
        assert not hasattr(model.evidence.native_receipt.frames[0], "sha256")
        assert not model.evidence.safe_summary()["frame_content_verified"]


@pytest.mark.parametrize("capture", [False, True])
@pytest.mark.parametrize(
    "fault,reason",
    [
        ("held", "COMPLETE_NATIVE_RESULT_REQUIRED"),
        ("native-cleanup", "NATIVE_CLEANUP_UNCONFIRMED"),
        ("native-failure", "NATIVE_DIAGNOSTIC_NOT_SUCCESSFUL"),
        ("process-cleanup", "PROCESS_CLEANUP_UNCONFIRMED"),
        ("retained-handles", "PROCESS_CLEANUP_UNCONFIRMED"),
        ("cancelled", "RUN_ERROR_RETAINED"),
        ("timed-out", "RUN_ERROR_RETAINED"),
        ("protocol-error", "RUN_ERROR_RETAINED"),
        ("missing-handshake", "PARENT_HANDSHAKE_INCOMPLETE"),
        ("unfinished-handshake", "PARENT_HANDSHAKE_INCOMPLETE"),
        ("partial-lifecycle", "COMPLETE_NATIVE_RESULT_REQUIRED"),
        ("wrong-deadline", "ORIGINAL_DEADLINE_MISMATCH"),
        ("duration", "CAMPAIGN_DURATION_EXCEEDED"),
        ("handle-budget", "PROCESS_HANDLE_BUDGET_EXCEEDED"),
    ],
)
def test_failed_or_incomplete_evidence_is_uncertain_without_counter_replacement(
    tmp_path, capture, fault, reason
):
    model = effect_fixture(tmp_path, capture=capture, fault=fault)
    effect = assess(model)
    assert effect.effect_certainty is EffectCertainty.UNCERTAIN
    assert reason in effect.reasons
    if fault == "partial-lifecycle":
        assert effect.counts is None
    elif fault == "held":
        assert effect.counts == NativeCameraEffectCounts(0, 0, 0, 0, 0, 0)
        assert not effect.cleanup_confirmed
    else:
        assert asdict(effect.counts) == dict(model.evidence.native_receipt.counts)


@pytest.mark.parametrize(
    "which", ["evidence", "preparation", "counter", "identity", "permit"]
)
def test_untrusted_or_malformed_subjects_cannot_be_assessed(tmp_path, which):
    model = effect_fixture(tmp_path)
    if which == "evidence":
        with pytest.raises(ValueError, match="TRUSTED_HASH"):
            assess(model, expected_evidence_sha256="f" * 64)
    elif which == "preparation":
        other = effect_fixture(tmp_path / "other")
        with pytest.raises(ValueError, match="TRUSTED_PREPARATION"):
            assess(model, expected_preparation=other.prepared)
    else:
        # Exact raw-result equality catches rehashed metadata edits before a
        # counter/identity/permit can be interpreted as a bounded observation.
        data = model.evidence.to_dict()
        raw = data["validated_result"]
        if which == "counter":
            del raw["native_receipt"]["counts"]["source_opened"]
        elif which == "identity":
            raw["native_receipt"]["selected_endpoint"] += "changed"
        else:
            raw["permit_sha256"] = "f" * 64
        with pytest.raises(ValueError):
            OwnedNativeCameraRunEvidence(canonical(data))


@pytest.mark.parametrize(
    "changes",
    [
        {"expected_deadline_ns": True},
        {"expected_deadline_ns": 0},
        {"maximum_elapsed_ns": True},
        {"maximum_elapsed_ns": 25_000_000_001},
    ],
)
def test_assessment_cannot_accept_new_or_unbounded_context(tmp_path, changes):
    with pytest.raises(ValueError, match="ASSESSMENT_CONTEXT"):
        assess(effect_fixture(tmp_path), **changes)


def install_modeled_effect_runner(monkeypatch, *, fault=None):
    """Test-only seam; production OwnedNativeCameraRunner is never enabled."""
    calls = []

    class ModeledRunner:
        def __init__(self, prepared, *, revalidate_consumed_permit):
            self.prepared, self.revalidate = prepared, revalidate_consumed_permit

        def run(self, *, cancellation, deadline_ns):
            calls.append(self.prepared.preparation_sha256)
            return modeled_effect_evidence(
                self.prepared,
                deadline_ns=deadline_ns,
                cancellation=cancellation,
                revalidate=self.revalidate,
                fault=fault,
            )

    monkeypatch.setattr(campaign_module, "OwnedNativeCameraRunner", ModeledRunner)
    monkeypatch.setattr(campaign_module, "source_fingerprint", lambda path: SOURCE)
    return calls


@pytest.mark.parametrize("capture", [False, True])
@pytest.mark.parametrize(
    "fault", [None, "native-cleanup", "process-cleanup", "cancelled"]
)
def test_scoped_campaign_and_core_use_assessed_effect_and_exact_counts(
    tmp_path, monkeypatch, capture, fault
):
    campaign = campaign_fixture(tmp_path, capture=capture)
    core, store, permit = components(campaign)
    calls = install_modeled_effect_runner(monkeypatch, fault=fault)
    result = core.execute(permit)
    known = fault is None
    assert result.state is (
        AttemptState.SEALED_KNOWN if known else AttemptState.SEALED_UNCERTAIN
    )
    assert result.quarantine_latched is not known
    assert result.receipt.effect_certainty is (
        EffectCertainty.CONFIRMED if known else EffectCertainty.UNCERTAIN
    )
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert (
        result.receipt.opens,
        result.receipt.reads,
        result.receipt.writes,
        result.receipt.frames,
        result.receipt.closes,
    ) == (1, 2 if capture else 0, int(capture), 2 if capture else 0, 1)
    assert result.receipt.evidence_sha256s == (campaign.evidence.evidence_sha256,)
    assert store.evidence[0].payload == campaign.evidence.payload
    assert store.trace.count("ACKNOWLEDGED_ONCE") == 1
    assert store.trace.count("CONSUMED_SCOPE_REVALIDATED") == 3
    assert core.execute(permit) == result and len(calls) == 1
    assert not (tmp_path / "assigned-output").exists()
