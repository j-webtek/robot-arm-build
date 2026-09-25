"""Actual v2 dispatch/core/supervisor, explicit modeled process and store facts.

This is an application composition test, not hardware or original-store
qualification. The production M1 wrapper is tested separately. There is no
test-runner switch in the application or browser API.
"""

from dataclasses import replace
import json
from pathlib import Path
from threading import Event

import pytest

from rocell.application import physical_camera_dispatch as dispatch
from rocell.application import physical_camera_activation_campaign as campaign_module
from rocell.application.camera_activation_campaign_contract import (
    validate_camera_activation_binding,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.providers.windows import native_camera_activation_supervisor as supervisor
from rocell.providers.windows.native_camera_activation_protocol import (
    NativeCameraActivationRequest,
)
from rocell.providers.windows.native_camera_protocol import canonical
from test_camera_activation_application_handoff import PIXELS, no_device_calls
from test_native_camera_activation_evidence import modeled
from test_native_camera_activation_protocol import fixture as result_fixture, ready_for
from test_native_camera_activation_supervisor import ModelOwner, no_physical_owner
from test_physical_camera_activation_campaign import campaign
from test_physical_camera_coordinator import SOURCE
from test_physical_camera_dispatch import OriginalStoreModel, RecordingSink


class ActivationStoreModel(OriginalStoreModel):
    def retain_camera_activation_evidence(self, permit, evidence):
        assert self.acknowledged
        validate_camera_activation_binding(permit, evidence)
        self.evidence = evidence
        self.trace.append("CAMERA_V2_EVIDENCE_RETAINED")

    def read_camera_activation_evidence(self, attempt):
        return self.read_campaign_evidence(attempt)


def install_owner(directory, monkeypatch, *, purpose="probe", fault=None, pixels=False):
    """Bind modeled native output lazily to the real dispatch-created request.

    No permit, preparation or result is patched in the production code. Every
    admission/release/protocol/accounting check still runs normally. The owner
    cannot execute processes and only creates test pixels when requested.
    """
    owners = []

    def new_owner():
        raw_owner, args = modeled(directory, purpose)
        owner = ModelOwner(raw_owner, args, fault)
        start, send = owner.start, owner.send_final_input
        capture_directory = None
        admission_wait_s = None

        def bound_start(registration, request, *, check, keep_stdin_open):
            nonlocal capture_directory, admission_wait_s
            req = NativeCameraActivationRequest(canonical(json.loads(request)))
            fields = req.to_dict()
            admission_wait_s = fields["admission_timeout_ms"] / 1000 + 0.05
            ready = ready_for(req)
            _, _, raw = result_fixture(purpose)
            raw.update(
                request_sha256=req.request_sha256, permit_sha256=fields["permit_sha256"]
            )
            owner.ready = ready.payload + b"\n"
            if purpose == "capture":
                settings = json.loads(fields["capture_json"])
                capture_directory = Path(settings["output_directory"])
                assert settings["controls"] == ""
                raw["native_receipt"]["requested_mode"] = {
                    name: settings[name]
                    for name in (
                        "width",
                        "height",
                        "fps_numerator",
                        "fps_denominator",
                        "subtype",
                    )
                }
                # No advertised/requested stride is legitimate: the modeled
                # producer reports the actual buffer stride independently.
                stride = settings["requested_stride_bytes"]
                raw["native_receipt"]["requested_mode"]["stride_bytes"] = (
                    int(stride) if stride else None
                )
                raw["native_receipt"]["frames"][0]["media_timestamp_100ns"] = 0
            owner.result = canonical(raw) + b"\n"
            start(registration, request, check=check, keep_stdin_open=keep_stdin_open)

        def bound_send(wire, *, check):
            if fault == "admission-deadline":
                # Slow only this incapable transport. Let the real handshake
                # clock/deadline reject release; do not fabricate a receipt,
                # replace production clocks, or increase a time allowance.
                assert admission_wait_s is not None and 0 < admission_wait_s <= 6
                Event().wait(admission_wait_s)
            send(wire, check=check)
            if pixels and capture_directory is not None:
                # Test-only acquisition stand-in; never an application fallback.
                assert capture_directory.is_relative_to(directory)
                capture_directory.mkdir(parents=True)
                (capture_directory / "frame-000000.yuy2").write_bytes(PIXELS)

        owner.start, owner.send_final_input = bound_start, bound_send
        owners.append(owner)
        return owner

    monkeypatch.setattr(supervisor, "_new_owner", new_owner)
    monkeypatch.setattr(dispatch, "source_fingerprint", lambda path: SOURCE)
    monkeypatch.setattr(campaign_module, "source_fingerprint", lambda path: SOURCE)
    # Runtime approval is modeled here; actual installed software/pins have their
    # separate integration tests. This patch is not a production release option.
    monkeypatch.setattr(
        campaign_module, "verify_reviewed_activation_runtime", lambda *a, **kw: {}
    )
    return owners


def setup(tmp_path, monkeypatch, *, purpose="probe", fault=None, guard=None):
    worker = campaign(tmp_path, purpose)
    store = ActivationStoreModel(worker)
    owners = install_owner(tmp_path, monkeypatch, purpose=purpose, fault=fault)
    owner = dispatch._CameraDispatchTransaction(
        store, worker, revalidate_context=guard or (lambda: None)
    )
    return owner, store, owners


def perform(owner, sink, cancellation=None):
    return owner.perform(
        request_key="modeled-v2-dispatch-once",
        sink=sink,
        enrollment=None,
        cancellation=cancellation or Event(),
        settings_epoch="9" * 64 if owner.view()["operation"] == "capture" else None,
    )


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_original_pair_readback_precedes_single_data_handoff(
    tmp_path, monkeypatch, purpose
):
    owner, store, owners = setup(tmp_path, monkeypatch, purpose=purpose)
    sink = RecordingSink()
    result = perform(owner, sink)
    assert result["status"] == "SUCCEEDED"
    assert len(owners) == 1 and owners[0].cleaned
    assert store.reads == ["permit", "result", "evidence"]
    assert len(sink.received) == 1
    evidence, arguments = sink.received[0]
    assert evidence == store.evidence and len(evidence) == 2
    assert arguments["expected_evidence_sha256"] == evidence[0].payload_sha256
    assert arguments["expected_supervision_sha256"] == evidence[1].payload_sha256
    assert owner.retained_diagnostics()["readback_scope"] == "EXITED"
    assert owner.view()["phase"] == "PENDING_COMPLETION_LOG"
    assert owner.view()["attempt_state"] == "SEALED_KNOWN"
    assert owner.view()["physical_authority"] is False
    with pytest.raises(ValueError, match="ALREADY_USED"):
        perform(owner, sink)
    assert len(owners) == 1


@pytest.mark.parametrize(
    "fault", ["bad-result", "cleanup-error", "cleanup-missing-resource"]
)
def test_uncertain_pair_is_retained_but_cannot_feed_data_workflow(
    tmp_path, monkeypatch, fault
):
    owner, store, owners = setup(tmp_path, monkeypatch, fault=fault)
    sink = RecordingSink()
    with pytest.raises(
        dispatch.PhysicalCameraDispatchError, match="NOT_KNOWN"
    ) as raised:
        perform(owner, sink)
    assert owner.view()["attempt_state"] == "SEALED_UNCERTAIN"
    assert not sink.received and sink.invalidations == 1
    assert len(owners) == 1 and store.evidence
    assert (
        owner.retained_diagnostics()["original_evidence"]["schema"]
        == "rocell.camera_activation_observation_pair.v2"
    )
    result = next(iter(store.results.values()))
    summary = raised.value.diagnostic
    assert summary["attempt_state"] == "SEALED_UNCERTAIN"
    assert summary["native_accounting_available"] is (result.receipt is not None)
    assert summary["quarantine_latched"] is True
    assert summary["readback_scope"] == "EXITED"
    assert summary["physical_authority"] is summary["automatic_replay"] is False
    # None is a missing primary cause, not an inferred successful cleanup.
    assert (
        summary["reported_primary_error"]
        == owner.retained_diagnostics()["original_evidence"]["supervision"][
            "primary_error"
        ]
    )
    summary["attempt_state"] = "CHANGED_BY_CALLER"
    assert raised.value.diagnostic["attempt_state"] == "SEALED_UNCERTAIN"
    if fault == "bad-result":
        assert (
            result.receipt is None
        )  # unavailable accounting is not an invented zero receipt


@pytest.mark.parametrize(
    "fault", ["permit", "result", "missing", "extra", "bytes", "epoch", "lease-exit"]
)
def test_readback_or_lease_failure_never_hands_off(tmp_path, monkeypatch, fault):
    owner, store, owners = setup(tmp_path, monkeypatch)
    store.read_fault = fault
    store.readback_exit_error = fault == "lease-exit"
    sink = RecordingSink()
    with pytest.raises((ValueError, OSError)) as raised:
        perform(owner, sink)
    if type(raised.value) is dispatch.PhysicalCameraDispatchError:
        assert raised.value.diagnostic is None
    assert not sink.received and sink.invalidations == 1
    assert owner.view()["phase"] == "FAILED_NO_REPLAY"
    assert len(owners) == 1


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_deadline_error_surfaces_retained_cause_without_releasing_data(
    tmp_path, monkeypatch, purpose
):
    owner, store, owners = setup(
        tmp_path, monkeypatch, purpose=purpose, fault="admission-deadline"
    )
    sink = RecordingSink()
    with pytest.raises(dispatch.PhysicalCameraDispatchError) as raised:
        perform(owner, sink)
    assert raised.value.code == "CAMERA_ATTEMPT_NOT_KNOWN"
    assert "ADMISSION_DEADLINE_EXPIRED" in str(raised.value)
    assert "do not infer zero effects" in str(raised.value)
    summary = raised.value.diagnostic
    assert summary["reported_primary_error"] == "ADMISSION_DEADLINE_EXPIRED"
    assert summary["release_check_passed"] is False
    assert summary["native_accounting_available"] is False
    assert summary["operation"] == purpose
    assert summary["attempt_id"] == owner.view()["attempt_id"]
    assert store.reads == ["permit", "result", "evidence"]
    assert len(owners) == 1 and owners[0].cleaned
    assert owners[0].phase == "ready"  # Final release was not sent by this peer.
    assert not sink.received and sink.invalidations == 1
    assert owner.view()["phase"] == "FAILED_NO_REPLAY"
    assert owner.view()["attempt_state"] == "SEALED_UNCERTAIN"
    with pytest.raises(ValueError, match="ALREADY_USED"):
        perform(owner, sink)
    assert len(owners) == 1


@pytest.mark.parametrize("when", ["before", "after-readback", "after-handoff"])
def test_stop_withholds_current_data_and_never_replays(tmp_path, monkeypatch, when):
    owner, store, owners = setup(tmp_path, monkeypatch)
    sink, stop = RecordingSink(), Event()
    if when == "before":
        stop.set()
    elif when == "after-readback":
        original = store.read_camera_activation_evidence

        def read(attempt):
            value = original(attempt)
            stop.set()
            return value

        store.read_camera_activation_evidence = read
    else:
        original = sink.accept_retained_probe

        def accept(*args, **kwargs):
            original(*args, **kwargs)
            stop.set()

        sink.accept_retained_probe = accept
    with pytest.raises(ValueError, match="CANCELLED"):
        perform(owner, sink, stop)
    assert len(owners) == int(when != "before")
    assert len(sink.received) == int(when == "after-handoff")
    assert sink.invalidations == 1


def test_late_interruption_retains_original_uncertain_history_without_data_handoff(
    tmp_path, monkeypatch
):
    owners = []

    def current():
        if owners and owners[0].cleaned:
            raise KeyboardInterrupt("MODELED_LATE_INTERRUPT")

    owner, store, owners = setup(tmp_path, monkeypatch, guard=current)
    sink = RecordingSink()
    with pytest.raises(KeyboardInterrupt, match="MODELED_LATE_INTERRUPT"):
        perform(owner, sink)
    assert len(owners) == 1 and not sink.received
    assert store.reads == ["permit", "result", "evidence"]
    assert owner.view()["attempt_state"] == "SEALED_UNCERTAIN"
    assert owner.retained_diagnostics()["original_evidence"] is not None
    assert owner.retained_diagnostics()["readback_scope"] == "EXITED"


def test_v2_requires_original_guard_and_exact_production_store(tmp_path, monkeypatch):
    worker = campaign(tmp_path)
    store = ActivationStoreModel(worker)
    with pytest.raises(ValueError, match="ORIGINAL_ACTIVATION_CONTEXT"):
        dispatch._CameraDispatchTransaction(store, worker)
    with pytest.raises(ValueError, match="ORIGINAL_CAMERA_M1"):
        dispatch.PhysicalCameraDispatchOwner(
            store, worker, revalidate_context=lambda: None
        )
    assert not store.trace
