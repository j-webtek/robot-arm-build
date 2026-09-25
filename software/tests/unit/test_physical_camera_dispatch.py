"""Real application/core/parsers; incapable modeled backend and protocol store.

These tests do not qualify native execution or M1 durability. The nominal
probe/settings/capture test does ingest real tiny YUY2 files; native/process
observations and predecessor acceptance are explicitly modeled. No test backend
can be selected in the production wizard.
"""

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import subprocess
import threading

import pytest

from rocell.application import physical_camera_dispatch as module
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_native_camera_campaign import (
    PhysicalNativeCameraCampaign,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_native_camera_bounded_effect import install_modeled_effect_runner
from test_physical_camera_acquisition_service import LAUNCH, SOURCE, reviewed_enrollment
from test_physical_camera_coordinator import CameraProtocolStore, admission


@pytest.fixture(autouse=True)
def no_devices(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("dispatch test attempted native execution or device access")

    monkeypatch.setattr(subprocess, "Popen", denied)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, denied)
    monkeypatch.setattr(module, "source_fingerprint", lambda path: SOURCE)
    monkeypatch.setattr(
        "rocell.application.physical_camera_capture_workflow.source_fingerprint",
        lambda path: SOURCE,
    )


class OriginalStoreModel(CameraProtocolStore):
    """Models committed byte readback independently of the worker's memory."""

    def __init__(self, campaign):
        plan, reg = campaign.plan(), campaign.registration()
        super().__init__(
            admission(
                cell_id=plan["cell_id"],
                session_id=plan["session_id"],
                stage=reg.stage,
                selected_identity_sha256=plan["selected_identity_sha256"],
            )
        )
        self.reads, self.permits = [], {}
        self.read_fault = None
        self.readback_exit_error = False

    def begin_intent(self, binding, permit):
        super().begin_intent(binding, permit)
        self.permits[permit.attempt_id] = permit

    def assert_consumed_permit(self, permit):
        assert self.held_leases[-1].level is LeaseLevel.CAMERA
        assert self.attempts[permit.attempt_id] is AttemptState.EFFECT_ARMED
        assert not self.acknowledged
        self.acknowledged = True

    def revalidate_consumed_permit(self, permit):
        assert self.acknowledged and self.held_leases[-1].level is LeaseLevel.CAMERA

    @contextmanager
    def transaction(self, leases):
        with super().transaction(leases) as transaction:
            yield transaction
        if self.reads and self.readback_exit_error:
            raise OSError("READBACK_LEASE_EXIT_FAILED")

    def read_campaign_permit(self, attempt):
        self.reads.append("permit")
        value = self.permits[attempt]
        return replace(value, nonce="f" * 64) if self.read_fault == "permit" else value

    def read_campaign_result(self, attempt):
        self.reads.append("result")
        value = self.results[attempt]
        return (
            replace(value, reason_codes=("CHANGED",))
            if self.read_fault == "result"
            else value
        )

    def read_campaign_evidence(self, attempt):
        self.reads.append("evidence")
        if self.read_fault == "missing":
            raise OSError("ORIGINAL_EVIDENCE_MISSING")
        if self.read_fault == "extra":
            return self.evidence * 2
        if self.read_fault == "bytes":
            return (replace(self.evidence[0], payload=b"{}"),)
        if self.read_fault == "schema":
            return (replace(self.evidence[0], schema="rocell.wrong-envelope.v1"),)
        if self.read_fault == "epoch":
            self.snapshot = replace(
                self.snapshot, configuration_epoch_hashes=("8" * 64,) * 8
            )
        return self.evidence


class RecordingSink:
    def __init__(self):
        self.received, self.invalidations = [], 0

    def accept_retained_probe(self, enrollment, evidence, **kwargs):
        self.received.append((evidence, kwargs))

    def stage_retained_capture(self, evidence, **kwargs):
        self.received.append((evidence, kwargs))

    def pending_observation_result(self, action_id):
        return {"action_id": action_id, "status": "SUCCEEDED"}

    def invalidate(self):
        self.invalidations += 1


def setup(
    tmp_path,
    monkeypatch,
    *,
    operation="probe",
    service=None,
    enrollment=None,
    fault=None
):
    service = service or PhysicalCameraAcquisitionService(
        tmp_path, launch_id=LAUNCH, source_sha256=SOURCE, mode="physical"
    )
    enrollment = enrollment or reviewed_enrollment()
    plan = service.preview_plan(operation, enrollment)
    campaign = PhysicalNativeCameraCampaign.from_plan(plan["native_campaign_plan"])
    store = OriginalStoreModel(campaign)
    calls = install_modeled_effect_runner(monkeypatch, fault=fault)
    owner = module._CameraDispatchTransaction(store, campaign)
    return service, enrollment, store, calls, owner


def perform(owner, sink, *, enrollment=None, cancellation=None, settings=None):
    return owner.perform(
        request_key="modeled-one-camera-attempt",
        sink=sink,
        enrollment=enrollment,
        cancellation=cancellation or threading.Event(),
        settings_epoch=settings,
    )


def test_inert_constructor_view_and_public_wrapper_rejects_protocol_store(
    tmp_path, monkeypatch
):
    service, enrollment, store, calls, owner = setup(tmp_path, monkeypatch)
    assert store.trace == [] and calls == []
    for _ in range(4):
        assert owner.view()["phase"] == "NOT_STARTED"
    with pytest.raises(ValueError, match="ORIGINAL_CAMERA_M1"):
        module.PhysicalCameraDispatchOwner(
            store, owner._campaign, revalidate_context=lambda: None
        )
    assert store.trace == [] and not service.directory.exists()


def test_real_probe_handoff_requires_original_readback_and_never_publishes(
    tmp_path, monkeypatch
):
    service, enrollment, store, calls, owner = setup(tmp_path, monkeypatch)
    result = perform(owner, service, enrollment=enrollment)
    assert result["status"] == "SUCCEEDED"
    assert store.reads == ["permit", "result", "evidence"]
    assert owner.view()["attempt_state"] == "SEALED_KNOWN"
    assert owner.view()["phase"] == "PENDING_COMPLETION_LOG"
    assert service.view()["publication"]["status"] == "PENDING"
    assert service.view()["connected"] is False
    assert service.cache_published_preview("image-" + "1" * 32) is None
    assert len(calls) == 1
    with pytest.raises(ValueError, match="ALREADY_USED"):
        perform(owner, service, enrollment=enrollment)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "fault",
    ["permit", "result", "missing", "extra", "bytes", "schema", "epoch", "lease-exit"],
)
def test_original_readback_failure_never_hands_off_or_replays(
    tmp_path, monkeypatch, fault
):
    _, _, store, calls, owner = setup(tmp_path, monkeypatch)
    store.read_fault = fault
    store.readback_exit_error = fault == "lease-exit"
    sink = RecordingSink()
    with pytest.raises((ValueError, OSError)):
        perform(owner, sink)
    assert not sink.received and sink.invalidations == 1
    assert owner.view()["phase"] == "FAILED_NO_REPLAY"
    if fault in {"epoch", "lease-exit"}:
        diagnostics = owner.retained_diagnostics()
        assert diagnostics["original_evidence"] is not None
        assert diagnostics["readback_scope"] == "EXIT_OR_FINAL_VALIDATION_UNCONFIRMED"
    assert len(calls) == 1
    with pytest.raises(ValueError, match="ALREADY_USED"):
        perform(owner, sink)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "fault", ["native-cleanup", "process-cleanup", "cancelled", "held"]
)
def test_uncertain_attempt_is_not_a_successful_observation(
    tmp_path, monkeypatch, fault
):
    _, _, store, calls, owner = setup(tmp_path, monkeypatch, fault=fault)
    sink = RecordingSink()
    with pytest.raises(ValueError, match="NOT_KNOWN"):
        perform(owner, sink)
    assert owner.view()["attempt_state"] == "SEALED_UNCERTAIN"
    assert store.reads == ["permit", "result", "evidence"]
    assert owner.retained_diagnostics()["original_evidence"] is not None
    assert not sink.received and len(calls) == 1


@pytest.mark.parametrize("when", ["before", "after-readback", "after-handoff"])
def test_stop_cannot_publish_or_replay(tmp_path, monkeypatch, when):
    _, _, store, calls, owner = setup(tmp_path, monkeypatch)
    cancel, sink = threading.Event(), RecordingSink()
    if when == "before":
        cancel.set()
    elif when == "after-readback":
        original = store.read_campaign_evidence

        def read(attempt):
            result = original(attempt)
            cancel.set()
            return result

        store.read_campaign_evidence = read
    else:
        original = sink.accept_retained_probe

        def accept(*args, **kwargs):
            original(*args, **kwargs)
            cancel.set()

        sink.accept_retained_probe = accept
    with pytest.raises(ValueError, match="CANCELLED"):
        perform(owner, sink, cancellation=cancel)
    assert len(calls) == int(when != "before")
    assert len(sink.received) == int(when == "after-handoff")
    assert sink.invalidations == 1


@pytest.mark.parametrize("after", [False, True])
def test_source_change_before_dispatch_or_after_original_readback(
    tmp_path, monkeypatch, after
):
    _, _, store, calls, owner = setup(tmp_path, monkeypatch)
    sink = RecordingSink()

    def changed(path):
        return "f" * 64 if not after or store.reads else SOURCE

    monkeypatch.setattr(module, "source_fingerprint", changed)
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        perform(owner, sink)
    assert len(calls) == int(after) and not sink.received


def test_probe_settings_capture_real_pixels_through_same_transaction(
    tmp_path, monkeypatch
):
    service, enrollment, _, _, probe = setup(tmp_path, monkeypatch)
    perform(probe, service, enrollment=enrollment)
    service.publish_retained_observation("operation-" + "1" * 32)
    values = {
        field["name"]: field["default"]
        for field in service.configuration_fields()
        if "default" in field
    }
    fields = service.configuration_fields()
    values["mode_choice_id"] = fields[0]["options"][0]["value"]
    values["operator_id"] = "modeled-settings-operator"
    context = service.configuration_context_sha256()
    service.begin_configuration_action(context)
    staged = service.stage_configuration(
        values, expected_context_sha256=context, cancellation=threading.Event()
    )
    service.publish_configuration("operation-" + "2" * 32, staged)
    service, enrollment, store, calls, capture = setup(
        tmp_path,
        monkeypatch,
        operation="capture",
        service=service,
        enrollment=enrollment,
    )
    # The incapable producer creates only tiny files under the test's directory.
    # This deliberately models missing native output-directory ownership.
    original = store.retain_campaign_evidence

    def retain(permit, evidence):
        prepared = capture._campaign.preparation_for_permit(permit)
        output = Path(prepared.camera_plan.request.output_directory)
        output.mkdir(parents=True)
        (output / "frame-000000.yuy2").write_bytes(bytes([16, 128, 56, 128] * 4))
        original(permit, evidence)

    store.retain_campaign_evidence = retain
    epoch = service.view()["configuration"]["candidate"]["settings_epoch"]
    result = perform(capture, service, enrollment=enrollment, settings=epoch)
    assert result["status"] == "SUCCEEDED" and len(calls) == 1
    assert service.view()["publication"]["status"] == "PENDING"
    service.publish_retained_observation("operation-" + "3" * 32)
    png = service.cache_published_preview("image-" + "4" * 32)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert service.view()["status"] == "CONTENT_VERIFIED"
    assert service.view()["last_frame"]["live"] is False


def service_dispatch(tmp_path, monkeypatch):
    """Test-only store injection; still uses the real service and coordinator."""
    service = PhysicalCameraAcquisitionService(
        tmp_path, launch_id=LAUNCH, source_sha256=SOURCE, mode="physical"
    )
    enrollment = reviewed_enrollment()
    transactions = []

    def constructor(persistence, campaign, *, revalidate_context):
        owner = module._CameraDispatchTransaction(
            OriginalStoreModel(campaign),
            campaign,
            revalidate_context=revalidate_context,
        )
        transactions.append(owner)
        return owner

    monkeypatch.setattr(module, "PhysicalCameraDispatchOwner", constructor)
    calls = install_modeled_effect_runner(monkeypatch)

    def run():
        plan = service.preview_plan("probe", enrollment)
        return service.run_admitted_campaign(
            "probe",
            enrollment,
            persistence=None,
            request_key="test-service-dispatch",
            expected_plan_sha256=digest(canonical(plan)),
            cancellation=threading.Event(),
        )

    return service, enrollment, transactions, calls, run


def test_service_dispatch_stages_result_and_includes_retained_diagnostics(
    tmp_path, monkeypatch
):
    service, _, transactions, calls, run = service_dispatch(tmp_path, monkeypatch)
    result = run()
    assert result == service.pending_observation_result("physical_camera_probe")
    assert service.dispatch_view()["phase"] == "PENDING_COMPLETION_LOG"
    assert (
        service.retained_capture_diagnostics()["dispatch"]["original_evidence"]
        is not None
    )
    assert service.dispatch_view()["attempt_state"] == "SEALED_KNOWN"
    assert len(calls) == len(transactions) == 1


@pytest.mark.parametrize("published", [False, True])
def test_service_rejects_pending_or_retained_probe_before_another_attempt(
    tmp_path, monkeypatch, published
):
    service, _, transactions, calls, run = service_dispatch(tmp_path, monkeypatch)
    run()
    if published:
        service.publish_retained_observation("operation-" + "9" * 32)
    with pytest.raises(ValueError, match="Finish the existing observation"):
        run()
    assert len(calls) == len(transactions) == 1


@pytest.mark.parametrize("boundary", [1, 2])
def test_service_context_drift_is_rechecked_at_native_admission_boundaries(
    tmp_path, monkeypatch, boundary
):
    from test_native_camera_bounded_effect import modeled_effect_evidence
    import rocell.application.physical_native_camera_campaign as campaign_module

    service, _, transactions, _, run = service_dispatch(tmp_path, monkeypatch)
    checks = []

    class DriftRunner:
        def __init__(self, prepared, *, revalidate_consumed_permit):
            self.prepared, self.original = prepared, revalidate_consumed_permit

        def run(self, *, cancellation, deadline_ns):
            def revalidate(exact):
                checks.append("modeled-parent-revalidation")
                if len(checks) == boundary:
                    service.invalidate()
                self.original(exact)

            return modeled_effect_evidence(
                self.prepared,
                deadline_ns=deadline_ns,
                cancellation=cancellation,
                revalidate=revalidate,
            )

    monkeypatch.setattr(campaign_module, "OwnedNativeCameraRunner", DriftRunner)
    with pytest.raises(ValueError, match="WITHOUT_RETAINED_RECEIPT"):
        run()
    assert len(checks) == boundary
    assert transactions[0].view()["attempt_state"] == "SEALED_UNCERTAIN"
    assert service.view()["publication"]["status"] != "CURRENT"
    assert service.view()["configuration"]["capabilities"] is None


@pytest.mark.parametrize("last_hash", [2, 4])
def test_context_change_during_last_fingerprint_cannot_pass_native_release(
    tmp_path, monkeypatch, last_hash
):
    from test_native_camera_bounded_effect import modeled_effect_evidence
    import rocell.application.physical_native_camera_campaign as campaign_module

    service, _, transactions, _, run = service_dispatch(tmp_path, monkeypatch)
    active, source_reads = [False], []

    def source(path):
        if active[0]:
            source_reads.append(path)
            if len(source_reads) == last_hash:
                service.invalidate()
        return SOURCE

    class HashDriftRunner:
        def __init__(self, prepared, *, revalidate_consumed_permit):
            self.prepared, self.revalidate = prepared, revalidate_consumed_permit

        def run(self, *, cancellation, deadline_ns):
            active[0] = True
            return modeled_effect_evidence(
                self.prepared,
                deadline_ns=deadline_ns,
                cancellation=cancellation,
                revalidate=self.revalidate,
            )

    monkeypatch.setattr(campaign_module, "OwnedNativeCameraRunner", HashDriftRunner)
    monkeypatch.setattr(campaign_module, "source_fingerprint", source)
    with pytest.raises(ValueError, match="WITHOUT_RETAINED_RECEIPT"):
        run()
    assert len(source_reads) == last_hash
    assert transactions[0].view()["attempt_state"] == "SEALED_UNCERTAIN"
    assert service.view()["configuration"]["capabilities"] is None


def test_context_change_during_plan_is_rejected_before_owner_construction(
    tmp_path, monkeypatch
):
    service, enrollment, transactions, calls, _ = service_dispatch(
        tmp_path, monkeypatch
    )
    plan = service.preview_plan("probe", enrollment)
    original = service.preview_plan

    def changed(*args):
        result = original(*args)
        service.invalidate()
        return result

    monkeypatch.setattr(service, "preview_plan", changed)
    with pytest.raises(ValueError, match="context changed while preparing"):
        service.run_admitted_campaign(
            "probe",
            enrollment,
            persistence=None,
            request_key="stale-plan-test",
            expected_plan_sha256=digest(canonical(plan)),
            cancellation=threading.Event(),
        )
    assert not transactions and not calls
