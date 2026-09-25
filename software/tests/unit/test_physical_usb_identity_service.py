"""Actual service/codecs and complete original reader, explicitly modeled M1.

The fixed-file observations and ledger bodies are models; no process or device
API is reachable. Separate root tests exercise the actual original NTFS join.
"""

from copy import deepcopy
from dataclasses import replace
from threading import Event

import pytest

from rocell.application import physical_usb_identity_service as module
from rocell.application import physical_camera_usb_readback as readback
from rocell.application.cell_commissioning_coordinator import RegisteredActionRequest
from rocell.application.physical_usb_identity_campaign import (
    UsbIdentityOperation,
    PhysicalUsbIdentityCampaign,
)
from rocell.application.usb_identity_stage_policy import (
    usb_identity_stage_policy,
    UsbIdentityAdmissionIdentity,
)
from rocell.providers.windows import usb_identity_registration as registration
from rocell.providers.windows.usb_identity_protocol import canonical

from test_physical_camera_identity_service import (
    identity,
    received,
    static_service,
    modeled,
    setup_flow,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    run as identity_run,
    module as identity_module,
)
from test_physical_static_contract_readback import initial_epoch


@pytest.fixture(autouse=True)
def original_epochs(source_model, request):
    # Model the original creation prefix explicitly, before any service adopts
    # it. This does not invent a new vector at the later USB collection point.
    if getattr(request, "param", True):
        return initial_epoch(source_model)
    return None


def modeled_files(runtime, **kwargs):
    """Explicit file-API model, not an actual runtime inspection receipt."""
    d = runtime.to_dict()
    rows = [
        *registration.FIXED_SOURCE_PINS,
        (registration.BUILD_RECORD_PATH, registration.BUILD_RECORD_SHA256, 32768),
        (d["helper"]["path"], d["helper"]["sha256"], 1048576),
    ]
    return dict(
        schema="rocell.usb_identity_runtime_file_check.v1",
        runtime_registration_sha256=runtime.sha256,
        source_sha256=d["source_sha256"],
        status="FILES_MATCHED",
        files=[dict(path=p, sha256=h, bytes=n) for p, h, n in rows],
        physical_authority=False,
        hardware_qualified=False,
    )


@pytest.fixture
def usb_service(identity, monkeypatch):
    original, state, inputs, _ = identity
    identity_run(original, inputs)
    identity_run(original, inputs, identity_module.REVIEW)
    owner = module.PhysicalUsbIdentityService(original.setup)
    monkeypatch.setattr(module, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    monkeypatch.setattr(
        module,
        "inspect_usb_identity_stage_policy",
        lambda _: usb_identity_stage_policy(),
    )
    monkeypatch.setattr(module, "inspect_usb_identity_runtime", modeled_files)
    monkeypatch.setattr(readback, "read_original_usb_campaigns", lambda *a: ())
    owner.observe_setup()
    return owner, state


def values(action):
    return {
        module.INSPECT: dict(operator_id="USB Inspector", confirm_file_inspection=True),
        module.REVIEW: dict(
            reviewer_id="USB Reviewer",
            confirm_policy_review=True,
            confirm_runtime_review=True,
            confirm_exact_target=True,
        ),
        module.COLLECT: dict(confirm_usb_query=True, confirm_no_capture_or_arm=True),
        module.EXPORT: dict(confirm_metadata_export=True),
    }[action]


def run(owner, action, *, supplied=None, publish=True, **kwargs):
    result = owner.perform(
        action,
        values(action) if supplied is None else supplied,
        expected_context_sha256=kwargs.pop("context", owner.context_sha256()),
        cancellation=kwargs.pop("cancellation", Event()),
        progress=kwargs.pop("progress", lambda _: None),
        **kwargs
    )
    owner.validate_publication(result)
    if publish:
        if action != module.EXPORT:
            owner.setup.publication_completed("modeled-usb-log")
        owner.publication_completed("modeled-usb-log")
    return result


def ready(owner):
    run(owner, module.INSPECT)
    run(owner, module.REVIEW)
    return owner.setup.original_source_workflow()


@pytest.mark.parametrize("original_epochs", [False], indirect=True)
def test_legacy_missing_vector_is_held_before_inspection(usb_service):
    owner, state = usb_service
    before = len(state["events"]), len(state["references"])
    for action in (module.INSPECT, module.REVIEW, module.COLLECT):
        assert "vector is absent" in owner.blocked_reason(action)
    assert owner.view()["next_action"] is None
    with pytest.raises(Exception):
        run(owner, module.INSPECT)
    assert before == (len(state["events"]), len(state["references"]))


def test_actual_original_inspect_review_and_pending_publication(usb_service):
    owner, state = usb_service
    original = deepcopy(
        owner.setup.original_source_workflow()["camera_identity_cycles"]
    )
    assert owner.view()["status"] == "AWAITING_INSPECTION"
    inspected = run(owner, module.INSPECT, publish=False)
    assert (
        inspected["device_open_count"] == 0
        and inspected["counter_coverage"] == "NO_DEVICE_IO"
    )
    assert owner.view()["publication"]["status"] == "PENDING"
    assert owner.view()["inspection"] is None and owner.view()["next_action"] is None
    changed = deepcopy(inspected)
    changed["steps"][0]["report"]["inspection"]["files_verified"] = 0
    with pytest.raises(ValueError):
        owner.validate_publication(changed)
    owner.setup.publication_completed("modeled-original-log")
    owner.publication_completed("modeled-usb-log")
    assert owner.view()["status"] == "AWAITING_REVIEW"
    assert owner.view()["inspection"]["operator_id"] == "USB Inspector"
    run(owner, module.REVIEW)
    assert owner.view()["status"] == "READY_TO_QUERY"
    assert owner.view()["next_action"] == module.COLLECT
    workflow = owner.setup.original_source_workflow()
    assert workflow["usb_baseline"]["state"] == "READY_TO_QUERY"
    assert workflow["camera_identity_cycles"] == original
    assert all(
        row["state"] == "PENDING" for row in owner.setup.session.view()["stages"][4:]
    )
    assert workflow["usb_baseline"]["query_event"]["state"] == "WAITING_OPERATOR"


@pytest.mark.parametrize(
    "fault", ["stale", "false-ack", "extra-field", "invalid-label", "stop", "source"]
)
def test_preflight_faults_never_start_originals(usb_service, fault):
    owner, state = usb_service
    before = len(state["events"]), len(state["references"])
    supplied, kwargs = values(module.INSPECT), {}
    if fault == "stale":
        kwargs["context"] = "f" * 64
    elif fault == "false-ack":
        supplied["confirm_file_inspection"] = 1
    elif fault == "extra-field":
        supplied["endpoint"] = "not accepted"
    elif fault == "invalid-label":
        supplied["operator_id"] = " "
    elif fault == "stop":
        kwargs["cancellation"] = Event()
        kwargs["cancellation"].set()
    else:
        state["source"] = "f" * 64
    with pytest.raises(ValueError):
        run(owner, module.INSPECT, supplied=supplied, **kwargs)
    assert before == (len(state["events"]), len(state["references"]))


def test_cached_view_and_fields_never_scan_or_query(usb_service, monkeypatch):
    owner, state = usb_service
    before = state["reads"], state["enters"]
    monkeypatch.setattr(
        module, "source_fingerprint", lambda _: pytest.fail("GET scanned")
    )
    owner.view()
    owner.context_sha256()
    for action in module.ACTIONS:
        owner.fields(action)
        owner.blocked_reason(action)
    owner.invalidate()
    assert owner.view()["status"] == "HISTORICAL_HELD"
    assert before == (state["reads"], state["enters"])


def test_distinct_review_failure_does_not_write(usb_service):
    owner, state = usb_service
    run(owner, module.INSPECT)
    before = len(state["events"]), len(state["references"])
    with pytest.raises(ValueError):
        run(
            owner,
            module.REVIEW,
            supplied={**values(module.REVIEW), "reviewer_id": "USB INSPECTOR"},
        )
    assert before == (len(state["events"]), len(state["references"]))


def test_partial_review_is_retained_and_never_replayed(usb_service, monkeypatch):
    owner, state = usb_service
    run(owner, module.INSPECT)
    retain = owner._retain

    def failed(tx, artifact, role, usb_id):
        if role == "runtime_review":
            raise RuntimeError("modeled original write failure")
        return retain(tx, artifact, role, usb_id)

    monkeypatch.setattr(owner, "_retain", failed)
    with pytest.raises(RuntimeError):
        run(owner, module.REVIEW)
    saved = owner.retained_diagnostics()
    assert (
        saved["attempt"]["records"]["policy_review"]["retention"]
        == "M1_FULL_BYTES_READ_BACK"
    )
    assert owner.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert owner.blocked_reason(module.REVIEW) is not None


def test_fresh_leased_facts_preserve_original_unobserved_epochs(usb_service):
    owner, state = usb_service
    workflow = ready(owner)
    baseline = workflow["usb_baseline"]
    campaign = PhysicalUsbIdentityCampaign(
        UsbIdentityOperation(
            canonical(baseline["inspection"]["document"]["operation"])
        ),
        identity=UsbIdentityAdmissionIdentity(
            canonical(baseline["identity"]["document"])
        ),
        review=registration.UsbIdentityRuntimeReview(
            canonical(baseline["runtime_review"]["document"])
        ),
    )
    provider = owner._facts_provider(
        workflow, owner.setup.current_prerequisite_artifact(), campaign, lambda: None
    )
    request = RegisteredActionRequest(
        workflow["binding"]["cell_id"],
        workflow["binding"]["session_id"],
        "physical-native-usb-identity",
        "modeled-query",
        "a" * 64,
    )
    snapshot = state["snapshot"]()
    facts = provider(request, snapshot)
    docs = facts.retained_documents()
    assert [item["entry"] for item in docs["configuration_epochs"]] == workflow[
        "configuration_epochs"
    ]["document"]["entries"]
    assert all(
        item["entry"]["status"] == "UNOBSERVED"
        and item["physical_configuration_qualified"] is False
        for item in docs["configuration_epochs"]
    )
    assert docs["hazard_assessment"]["observed_power"] == "UNKNOWN"
    assert docs["hazard_assessment"]["energy_envelope"] is None
    assert facts.open_blocker_ids == ()
    with pytest.raises(ValueError):
        provider(replace(request, session_id="physical-camera-" + "f" * 32), snapshot)
    with pytest.raises(ValueError):
        provider(request, replace(snapshot, evidence=snapshot.evidence[:-1]))
