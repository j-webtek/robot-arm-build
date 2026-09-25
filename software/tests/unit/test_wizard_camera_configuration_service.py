"""Wizard ordering/state tests with inert coordinator, worker and transaction seams.

No M1 store, process, pixels, helper, OS inventory or hardware is exercised.
Capability fields use the actual pure parsed probe fixture; known attempt states
below are explicit ordering fixtures, never qualified durable observations.
"""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from rocell.application import commissioning_rehearsal_reopen as reopen
from rocell.application import commissioning_rehearsal_service as service_module
from rocell.application import owned_camera_probe_campaign as probe_module
from rocell.application import owned_camera_rehearsal_campaign as capture_module
from rocell.application.camera_configuration import stage_camera_configuration
from rocell.application.cell_commissioning_coordinator import AttemptResult
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.rehearsal_owned_camera_evidence import (
    retain_owned_camera_evidence,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_camera_configuration import (
    effective_camera_settings_epoch,
)
from rocell.providers.windows.camera_worker_client import (
    CameraControlSetting,
    WindowsCameraWorkerClient,
)
from test_owned_camera_configuration_campaign import configuration_pair
from test_owned_camera_rehearsal_campaign import arguments
from test_rehearsal_owned_camera_evidence import complete_inputs


PROBE = "rehearsal_camera_probe"
CONFIGURE = "rehearsal_camera_configuration"
OWNED = "rehearsal_owned_camera_campaign"
LEGACY = "rehearsal_camera_campaign"


def forbidden(*args, **kwargs):
    pytest.fail("Injected service test attempted filesystem/provider/worker work")


@pytest.fixture
def harness(tmp_path, monkeypatch):
    args = arguments(tmp_path)
    service = service_module.CommissioningRehearsalService(
        args["workspace"], args["root"], source_sha256=args["source_sha256"]
    )
    service.session_id = "rehearsal-service-fixture"
    stage = STAGE_ORDER[4]
    service._operator = "fixture-operator"
    service._selected = deepcopy(args["selected_camera"])
    service._camera_settings = {
        "settings": deepcopy(args["settings"]),
        "settings_epoch": args["settings_epoch"],
    }
    service._cached.update(
        session_id=service.session_id,
        status="ACTIVE_REHEARSAL",
        stage=stage.value,
        stage_state="WAITING_OPERATOR",
        challenge_sha256="4" * 64,
    )
    state = SimpleNamespace(
        service=service,
        args=args,
        cancellation=threading.Event(),
        events=[],
        stored=[],
        constructed=[],
        on_tx=lambda: None,
        on_execute=lambda: None,
        known=AttemptResult(
            "attempt-" + "1" * 32, AttemptState.SEALED_KNOWN, "2" * 64, (), None, False
        ),
    )

    def refresh(**kwargs):
        service._cached.update(
            status="HELD" if service._failed else "ACTIVE_REHEARSAL",
            selected_camera=deepcopy(service._selected),
            camera_settings=deepcopy(service._camera_settings),
            camera_configuration=service._configuration_projection(),
            camera_process=deepcopy(service._camera_process),
            capture_dataset=deepcopy(service._latest_capture),
        )

    @contextmanager
    def transaction():
        state.events.append("stage-tx-entry")
        state.on_tx()
        try:
            yield SimpleNamespace(
                _audit_records=lambda: (),
                snapshot=lambda: SimpleNamespace(
                    next_action=SimpleNamespace(stage=stage)
                ),
            )
        finally:
            state.events.append("stage-tx-exit")

    @contextmanager
    def admission_transaction(leases):
        state.events.append("admission-tx-entry")
        yield SimpleNamespace(
            verification=lambda: SimpleNamespace(challenge_sha256="4" * 64),
            read_admission=lambda request: SimpleNamespace(challenge_sha256="4" * 64),
        )

    def store(tx, stored_stage, value, label):
        state.events.append("store-json")
        state.stored.append(deepcopy(value))
        return SimpleNamespace(evidence_id="in-memory-reference")

    service._store = SimpleNamespace(
        snapshot=lambda session: SimpleNamespace(
            next_action=SimpleNamespace(stage=stage)
        ),
        transaction=admission_transaction,
    )
    monkeypatch.setattr(service, "_transaction", transaction)
    monkeypatch.setattr(service, "_store_json", store)
    monkeypatch.setattr(service, "_refresh", refresh)
    monkeypatch.setattr(
        service,
        "_configuration_context",
        lambda tx: (
            service._probe_receipt,
            service._camera_probe,
            service._configuration_receipt,
            service._electronic_configuration,
        ),
    )
    monkeypatch.setattr(
        service_module,
        "load_physical_onboarding_stage_catalog",
        lambda workspace: SimpleNamespace(source_sha256="8" * 64),
    )
    monkeypatch.setattr(reopen, "_verify_camera_probe_receipt", lambda *a, **k: None)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    # The legacy source digest remains an explicit injected observation; no
    # source/helper bytes or filesystem publication are needed for ordering.
    monkeypatch.setattr(Path, "read_bytes", lambda path: b"inert-source-fixture")
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    for method in (
        "probe",
        "capture",
        "enumerate_metadata",
        "resolve_identity_metadata",
    ):
        monkeypatch.setattr(WindowsCameraWorkerClient, method, forbidden)

    class Coordinator:
        def __init__(self, **kwargs):
            state.events.append("coordinator-created")
            self.registration = kwargs["registrations"][0]
            assert len(kwargs["workers"]) == 1
            self.retained = kwargs["retained_campaign_actions"]

        def prepare(self, request):
            state.events.append("coordinator-prepare")
            assert request.expected_challenge_sha256 == "4" * 64
            assert request.action_id == self.registration.action_id
            return request

        def execute(self, permit, *, cancellation):
            assert cancellation is state.cancellation
            state.events.append("coordinator-execute")
            state.on_execute()
            return state.known

    class CaptureWorker:
        def __init__(self, *args, **kwargs):
            assert service._camera_readback is None and service.latest_preview() is None
            state.constructed.append(("capture", kwargs))
            self.readback = {
                "status": "REQUESTED_SETTINGS_OBSERVED_REHEARSAL",
                "physical_authority": False,
                "fixture": "injected-new-readback",
            }
            # Pure retained bytes feed the strict diagnostic projector. All
            # transaction/worker outcomes here remain ordering-only fixtures.
            self.evidence = retain_owned_camera_evidence(**complete_inputs())
            self.capture = SimpleNamespace(
                to_dict=lambda: {"schema": "test.inert_dataset.v1"},
                latest_preview=SimpleNamespace(
                    png_bytes=b"injected-preview-not-pixels"
                ),
            )

        def plan(self):
            return {"process_backend": "OWNED_INCAPABLE_CAMERA_PROCESS"}

        def registration(self, selected_stage):
            assert selected_stage is stage
            return SimpleNamespace(
                action_id="rehearsal-owned-camera-campaign",
                worker_id="incapable-camera-fixture",
            )

    class ProbeWorker:
        def __init__(self, *args, **kwargs):
            assert service._probe_attempted and service.latest_preview() is None
            state.constructed.append(("probe", kwargs))
            self.evidence = state.probe_artifact

        def plan(self):
            return {"process_backend": "OWNED_INCAPABLE_CAMERA_PROBE"}

        def registration(self):
            return SimpleNamespace(
                action_id="rehearsal-owned-camera-probe",
                worker_id="incapable-camera-probe",
            )

    monkeypatch.setattr(service_module, "CellCommissioningCoordinator", Coordinator)
    monkeypatch.setattr(capture_module, "OwnedBinaryCameraWorker", CaptureWorker)
    monkeypatch.setattr(service_module, "SyntheticBinaryCameraWorker", CaptureWorker)
    monkeypatch.setattr(probe_module, "OwnedCameraProbeWorker", ProbeWorker)
    caps, config = configuration_pair(args, session=service.session_id)
    state.capabilities, state.empty_config = caps, config
    state.probe_artifact = SimpleNamespace(
        payload=b"explicit-inert-probe-receipt",
        evidence_sha256=caps.to_dict()["probe_evidence_sha256"],
        capabilities=lambda: caps,
        view=lambda: {
            "status": "COMPLETE_PROBE_REHEARSAL",
            "physical_authority": False,
            "qualified": False,
            "fixture": "cached-pure-capabilities",
        },
    )
    state.refresh = refresh
    refresh()
    return state


def install_probe(h, *, configured=False, controls=()):
    service = h.service
    service._probe_attempted = True
    service._camera_probe = h.probe_artifact
    service._probe_receipt = {"schema": "test.inert_probe_projection.v1"}
    if configured:
        config = stage_camera_configuration(
            h.capabilities,
            h.empty_config.to_dict()["mode_choice_id"],
            controls,
            expected_probe_evidence_sha256=h.capabilities.to_dict()[
                "probe_evidence_sha256"
            ],
            expected_source_sha256=service.source_sha256,
            expected_selected_identity_sha256=service_module._hash(service._selected),
        )
        service._electronic_configuration = config
        service._configuration_receipt = {
            "schema": "test.inert_configuration_projection.v1"
        }
    h.refresh()


def field_values(h):
    fields = h.service.camera_configuration_fields()
    values = {field["name"]: field["default"] for field in fields if "default" in field}
    values["mode_choice_id"] = fields[0]["options"][0]["value"]
    values.update(gain_mode="manual", gain_value=21)
    return values


def invoke(h, action, values=None, *, progress=None):
    values = (
        values
        if values is not None
        else (
            {"fault": "none"}
            if action == PROBE
            else {"fault": "none", "frame_count": 1}
        )
    )
    bound = h.service.bind(action, values)
    return h.service.perform(
        action,
        bound,
        cancellation=h.cancellation,
        progress=progress or (lambda _: None),
    )


def test_cached_views_fields_and_bind_do_not_touch_store_or_provider(
    harness, monkeypatch
):
    h = harness
    install_probe(h)
    monkeypatch.setattr(h.service, "_transaction", forbidden)
    monkeypatch.setattr(h.service, "_refresh", forbidden)
    h.service._store = SimpleNamespace(snapshot=forbidden, transaction=forbidden)
    first = h.service.view()
    fields = h.service.camera_configuration_fields()
    assert (
        len(fields) == 13
        and first["camera_configuration"]["status"] == "PROBE_COMPLETE"
    )
    first["camera_configuration"]["capabilities"]["modes"].clear()
    fields[0]["options"].clear()
    assert h.service.camera_configuration_fields()[0]["options"]
    bound = h.service.bind(CONFIGURE, field_values(h))
    assert bound["_view_sha256"] == service_module._hash(h.service.view())
    assert h.stored == h.constructed == []


@pytest.mark.parametrize(
    "fault",
    [
        "no-store",
        "identity-stage",
        "not-open",
        "no-identity",
        "no-operator",
        "attempted",
        "held",
    ],
)
def test_probe_requires_due_open_identified_once_only_state(harness, fault):
    h = harness
    if fault == "no-store":
        h.service._store = None
    elif fault == "identity-stage":
        h.service._cached["stage"] = STAGE_ORDER[3].value
    elif fault == "not-open":
        h.service._cached["stage_state"] = "PENDING"
    elif fault == "no-identity":
        h.service._selected = None
    elif fault == "no-operator":
        h.service._operator = None
    elif fault == "attempted":
        h.service._probe_attempted = True
    else:
        h.service._failed = True
    with pytest.raises(WizardError) as caught:
        h.service.bind(PROBE, {"fault": "none"})
    assert caught.value.code == "REHEARSAL_ACTION_BLOCKED"
    assert not h.constructed and not h.stored


def test_explicit_probe_uses_retained_coordinator_and_cannot_replay(harness):
    h = harness
    result = invoke(h, PROBE)
    assert result["status"] == "SUCCEEDED" and not result["physical_authority"]
    assert [name for name, _ in h.constructed] == ["probe"]
    assert h.events.count("coordinator-execute") == 1
    assert (
        len(h.stored) == 1
        and h.stored[0]["schema"] == "rocell.rehearsal_camera_probe_receipt.v1"
    )
    assert h.service._receipt is None  # Probe does not stand in for capture assessment.
    assert h.service.view()["camera_configuration"]["status"] == "PROBE_COMPLETE"
    with pytest.raises(WizardError):
        invoke(h, PROBE)
    assert h.events.count("coordinator-execute") == 1


@pytest.mark.parametrize("failure", ["uncertain-attempt", "stop-in-publication"])
def test_probe_failure_retains_diagnostic_but_cannot_publish_or_retry(harness, failure):
    h = harness
    if failure == "uncertain-attempt":
        h.known = replace(
            h.known, state=AttemptState.SEALED_UNCERTAIN, quarantine_latched=True
        )
        result = invoke(h, PROBE)
        assert result["status"] == "FAILED"
        assert h.service.view()["camera_configuration"]["status"] == "HELD"
    else:
        h.on_tx = h.cancellation.set
        with pytest.raises(WizardError) as caught:
            invoke(h, PROBE)
        assert caught.value.code == "REHEARSAL_CANCELLED_BEFORE_PUBLICATION"
        assert h.service.view()["camera_configuration"] is None
    assert h.service._probe_attempted and not h.stored
    assert h.service._probe_receipt is None
    assert (
        h.service._camera_process_diagnostic["retained_probe_sha256"]
        == h.probe_artifact.evidence_sha256
    )
    assert (
        h.service._camera_process_diagnostic["attempt_result"]["state"]
        == h.known.state.value
    )
    assert h.service.latest_preview() is None
    h.cancellation.clear()
    with pytest.raises(WizardError):
        invoke(h, PROBE)
    assert len(h.constructed) == 1 and h.events.count("coordinator-execute") == 1


@pytest.mark.parametrize("configured", [False, True])
def test_any_probe_attempt_blocks_legacy_and_unconfigured_fallback(harness, configured):
    h = harness
    assert h.service.blocked_reason(LEGACY) is None
    assert h.service.blocked_reason(OWNED) is None
    install_probe(h, configured=configured)
    assert h.service.blocked_reason(LEGACY) is not None
    assert (h.service.blocked_reason(OWNED) is None) is configured
    with pytest.raises(WizardError):
        h.service.bind(LEGACY, {"frame_count": 1, "fault": "none"})
    if not configured:
        with pytest.raises(WizardError):
            h.service.bind(OWNED, {"frame_count": 1, "fault": "none"})
    assert not h.constructed


def test_never_probed_legacy_campaign_keeps_separate_unconfigured_route(harness):
    h = harness
    result = invoke(h, LEGACY)
    assert result["status"] == "SUCCEEDED"
    assert (
        not h.service._probe_attempted and h.service._electronic_configuration is None
    )
    assert h.service._receipt["plan"]["mode"]["pixel_format"] == "YUY2"
    assert "camera_readback" not in h.service._receipt
    assert "configuration" not in h.constructed[0][1]


def test_staging_retains_exact_capability_bound_intent_without_process(harness):
    h = harness
    install_probe(h)
    result = invoke(h, CONFIGURE, field_values(h))
    assert result["status"] == "SUCCEEDED" and not h.constructed
    assert h.events.count("store-json") == 1 and "coordinator-created" not in h.events
    config = h.service._electronic_configuration
    retained = h.stored[0]
    assert retained["configuration"] == config.to_dict()
    assert (
        retained["session_id"] == config.to_dict()["session_id"] == h.service.session_id
    )
    assert retained["configuration"]["source_sha256"] == h.service.source_sha256
    assert retained["configuration"][
        "selected_identity_sha256"
    ] == service_module._hash(h.service._selected)
    assert retained["effective_settings_epoch"] == effective_camera_settings_epoch(
        h.service._camera_settings["settings_epoch"], config
    )
    assert not config.to_dict()["applied"] and h.service._camera_readback is None
    assert h.service.view()["camera_configuration"]["status"] == "CONFIGURATION_STAGED"
    with pytest.raises(WizardError):
        h.service.bind(CONFIGURE, field_values(h))


@pytest.mark.parametrize(
    "fault", ["source", "identity", "stale-view", "retained-probe"]
)
def test_stale_configuration_preparation_or_context_never_stores(
    harness, monkeypatch, fault
):
    h = harness
    install_probe(h)
    values = h.service.bind(CONFIGURE, field_values(h))
    if fault == "source":
        h.service.source_sha256 = "f" * 64
    elif fault == "identity":
        h.service._selected["unit_id"] = "OTHER-UNIT"
    elif fault == "stale-view":
        h.service._cached["challenge_sha256"] = "f" * 64
    else:
        monkeypatch.setattr(
            h.service,
            "_configuration_context",
            lambda tx: ({"changed": True}, h.service._camera_probe, None, None),
        )
    with pytest.raises(ValueError):
        h.service.perform(
            CONFIGURE, values, cancellation=h.cancellation, progress=lambda _: None
        )
    assert not h.stored and not h.constructed


@pytest.mark.parametrize("when", ["before", "progress", "transaction"])
def test_stop_prevents_configuration_publication_at_each_service_boundary(
    harness, when
):
    h = harness
    install_probe(h)
    if when == "before":
        h.cancellation.set()
    if when == "transaction":
        h.on_tx = h.cancellation.set
    with pytest.raises(WizardError):
        invoke(
            h,
            CONFIGURE,
            field_values(h),
            progress=(lambda _: h.cancellation.set()) if when == "progress" else None,
        )
    assert not h.stored and not h.constructed
    assert h.service._electronic_configuration is None


@pytest.mark.parametrize("stop", [False, True])
def test_configured_capture_clears_old_readback_and_obeys_final_transaction_stop(
    harness, stop
):
    h = harness
    install_probe(h, configured=True, controls=(CameraControlSetting("gain", 21),))
    h.service._camera_readback = {"fixture": "stale-readback"}
    h.service._latest_preview = b"stale-preview"
    h.refresh()
    stage_entries = []

    def entering():
        stage_entries.append(True)
        if stop and len(stage_entries) == 2:
            h.cancellation.set()

    h.on_tx = entering
    if stop:
        with pytest.raises(WizardError) as caught:
            invoke(h, OWNED)
        assert caught.value.code == "REHEARSAL_CANCELLED_BEFORE_PUBLICATION"
        assert not h.stored and h.service._receipt_reference is None
        assert h.service.latest_preview() is None and h.service._camera_readback is None
        assert h.service.view()["status"] == "HELD"
        assert h.service._receipt["attempt_result"]["state"] == "SEALED_KNOWN"
    else:
        result = invoke(h, OWNED)
        assert result["status"] == "SUCCEEDED"
        assert h.service._camera_readback["fixture"] == "injected-new-readback"
        assert h.stored[0]["camera_readback"] == h.service._camera_readback
        assert h.service.latest_preview() == b"injected-preview-not-pixels"
    assert len(stage_entries) == 2 and len(h.constructed) == 1
    assert h.constructed[0][1]["configuration"].controls == (
        CameraControlSetting("gain", 21),
    )


@pytest.mark.parametrize("configured", [False, True])
def test_readback_drift_without_requested_controls_is_denied_during_bind(
    harness, configured
):
    h = harness
    if configured:
        install_probe(h, configured=True)
    with pytest.raises(WizardError):
        h.service.bind(OWNED, {"frame_count": 1, "fault": "control-readback-drift"})
    assert not h.service._failed and not h.constructed and not h.stored


def test_readback_drift_is_a_choice_only_with_staged_control_request(harness):
    h = harness
    install_probe(h, configured=True, controls=(CameraControlSetting("gain", 21),))
    values = h.service.bind(
        OWNED, {"frame_count": 1, "fault": "control-readback-drift"}
    )
    assert values["fault"] == "control-readback-drift"
    assert not h.constructed and not h.stored
