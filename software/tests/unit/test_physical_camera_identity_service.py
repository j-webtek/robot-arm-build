"""Real identity service/codecs/readback with modeled storage and unit facts.

The shared prefix deliberately models physical acceptance. These tests prove
software sequencing, not received hardware or native driver qualification.
"""

from contextlib import contextmanager
from copy import deepcopy
from threading import Event

import pytest

from rocell.application import physical_camera_identity_service as module
from rocell.application import physical_received_camera_service as received_module
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical

from test_physical_received_camera_service import (
    received,
    start,
    fill,
    observed_submission_values,
    review as receipt_review,
    run as received_run,
    republish_original,
)
from test_physical_static_camera_onboarding_service import static_service
from test_physical_source_qualification_service import modeled
from test_physical_camera_intake_setup import setup_flow
from test_physical_source_qualification_readback import source_model
from test_physical_camera_intake_session import intake_model
from test_physical_camera_session_readback import model, no_devices, workspace
from test_physical_camera_identity_readback import identity_inputs


@pytest.fixture
def identity(received, monkeypatch):
    old, state = received
    start(old)
    fill(old, observed=True)
    received_run(old, received_module.SUBMIT, observed_submission_values(old))
    receipt_review(old)
    received_run(old, received_module.IDENTITY)
    owner = module.PhysicalCameraIdentityService(old.setup)
    monkeypatch.setattr(module, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    owner.observe_setup()
    inputs = identity_inputs(
        source=owner.source_sha256, launch=owner.launch_id, return_owners=True
    )
    return owner, state, inputs, old


def values(action=module.SUBMIT):
    if action == module.REVIEW:
        return dict(
            file_only=True,
            reviewer_id="identity-reviewer",
            decision="ACKNOWLEDGE_EXACT",
        )
    if action == module.EXPORT:
        return dict(file_only=True, confirm_metadata_export=True)
    return dict(
        file_only=True,
        operator_id="identity-operator",
        observation_state="UNKNOWN",
        observed_value="Modeled test only: no physical identity observed.",
        method="Incapable fixture, not OS or received-hardware observation.",
        evidence_note="Physical USB and reconnect qualification remains pending.",
        observation_current=True,
    )


def run(owner, inputs, action=module.SUBMIT, *, supplied=None, publish=True, **kwargs):
    result = owner.perform(
        action,
        values(action) if supplied is None else supplied,
        **inputs,
        expected_context_sha256=kwargs.pop("context", owner.context_sha256(**inputs)),
        cancellation=kwargs.pop("cancellation", Event()),
        progress=kwargs.pop("progress", lambda _: None),
        **kwargs
    )
    owner.validate_publication(result)
    if publish:
        if action != module.EXPORT:
            owner.setup.publication_completed("modeled-identity-log")
        owner.publication_completed("modeled-identity-log")
    return result


def test_submit_exact_review_successor_and_stage3_history(identity):
    owner, state, inputs, old = identity
    original = owner.setup.original_source_workflow()["received_camera_cycles"]
    assert owner.view()["status"] == "WAITING_METADATA"
    assert owner.blocked_reason(module.SUBMIT, **inputs) is None
    result = run(owner, inputs, publish=False)
    assert owner.view()["publication"]["status"] == "PENDING"
    assert owner.view()["cycles"] == []
    changed = deepcopy(result)
    changed["steps"][0]["report"]["physical_authority"] = True
    with pytest.raises(WizardError):
        owner.validate_publication(changed)
    owner.setup.publication_completed("modeled-original-log")
    owner.publication_completed("modeled-identity-log")
    view = owner.view()
    assert view["status"] == "REVIEW_PENDING"
    assert view["cycles"][0]["assessment"]["verdict"] == "BLOCKED"
    assert (
        "USB_DESCRIPTOR_SERIAL_PROVENANCE_REQUIRED"
        in view["cycles"][0]["assessment"]["missing_requirements"]
    )
    run(owner, inputs, module.REVIEW)
    assert owner.view()["status"] == "REVIEWED_BLOCKED"
    run(owner, inputs)
    assert len(owner.view()["cycles"]) == 2
    assert owner.setup.original_source_workflow()["received_camera_cycles"] == original
    old.observe_setup()
    assert old.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert old.view()["collection"]["state"] == "REVIEWED_PASS"
    assert all(
        row["state"] == "PENDING" for row in owner.setup.session.view()["stages"][4:]
    )
    assert all(
        result[key] == 0
        for key in (
            "device_open_count",
            "serial_write_count",
            "power_event_count",
            "motion_command_count",
            "contact_command_count",
        )
    )


def test_inert_views_and_detached_metadata(identity, monkeypatch):
    owner, state, inputs, _ = identity
    before = (
        state["reads"],
        state["enters"],
        len(state["events"]),
        len(state["references"]),
    )
    monkeypatch.setattr(
        module, "source_fingerprint", lambda _: pytest.fail("GET performed source I/O")
    )
    owner.view()["publication"]["status"] = "changed"
    for action in module.ACTIONS:
        owner.fields(action)
        owner.blocked_reason(action, **inputs)
    owner.context_sha256(**inputs)
    assert before == (
        state["reads"],
        state["enters"],
        len(state["events"]),
        len(state["references"]),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "file-only",
        "observation-ack",
        "unknown-field",
        "actor",
        "state",
        "oversize",
        "stale",
        "stop",
        "source",
    ],
)
def test_preflight_rejects_without_original_write(identity, fault):
    owner, state, inputs, _ = identity
    before = len(state["events"]), len(state["references"])
    fields, kwargs = values(), {}
    if fault == "file-only":
        fields["file_only"] = 1
    elif fault == "observation-ack":
        fields["observation_current"] = False
    elif fault == "unknown-field":
        fields["endpoint"] = "not accepted"
    elif fault == "actor":
        fields["operator_id"] = ""
    elif fault == "state":
        fields["observation_state"] = "QUALIFIED"
    elif fault == "oversize":
        fields["observed_value"] = "x" * 1025
    elif fault == "stale":
        kwargs["context"] = "f" * 64
    elif fault == "stop":
        kwargs["cancellation"] = Event()
        kwargs["cancellation"].set()
    else:
        state["source"] = "f" * 64
    with pytest.raises((ValueError, WizardError)):
        run(owner, inputs, supplied=fields, **kwargs)
    assert before == (len(state["events"]), len(state["references"]))


def test_same_reviewer_has_no_original_mutation(identity):
    owner, state, inputs, _ = identity
    run(owner, inputs)
    before = len(state["events"]), len(state["references"])
    with pytest.raises(ValueError):
        run(
            owner,
            inputs,
            module.REVIEW,
            supplied={**values(module.REVIEW), "reviewer_id": "IDENTITY-OPERATOR"},
        )
    assert before == (len(state["events"]), len(state["references"]))


def test_unlogged_commit_refresh_is_readback_not_replay(identity):
    owner, state, inputs, _ = identity
    run(owner, inputs, publish=False)
    owner.invalidate()
    before = len(state["events"]), len(state["references"])
    original = republish_original(owner, state)
    assert owner.view()["status"] == "REVIEW_PENDING"
    assert original["camera_identity_cycles"][0]["state"] == "REVIEW_PENDING"
    assert before == (len(state["events"]), len(state["references"]))
    reopened = module.PhysicalCameraIdentityService(owner.setup)
    reopened.observe_setup()
    assert reopened.view()["cycles"] == owner.view()["cycles"]
    assert reopened.blocked_reason(module.SUBMIT) is not None


def test_partial_retention_has_no_replay_and_survives_export(
    identity, monkeypatch, tmp_path
):
    owner, state, inputs, _ = identity
    original_retain = owner._retain

    def fail(tx, artifact, role, identifier):
        if role == "helper":
            raise RuntimeError("modeled publication failure")
        return original_retain(tx, artifact, role, identifier)

    monkeypatch.setattr(owner, "_retain", fail)
    with pytest.raises(RuntimeError):
        run(owner, inputs)
    assert (
        owner.retained_diagnostics()["attempt"]["records"]["metadata"]["reference"]
        is not None
    )
    republish_original(owner, state)
    assert owner.view()["status"] == "INCOMPLETE_HELD"
    assert owner.blocked_reason(module.SUBMIT, **inputs) is not None
    state["source"] = "f" * 64
    exported = run(owner, inputs, module.EXPORT, export_parent=tmp_path / "exports")
    assert exported["status"] == "SUCCEEDED"
    assert owner.export_metadata() is not None
    assert owner.view()["status"] != "REVIEWED_BLOCKED"


def test_new_live_metadata_invalidates_old_ticket(identity):
    owner, state, inputs, _ = identity
    context = owner.context_sha256(**inputs)
    inputs["native_camera"].invalidate("MODELED_METADATA_CHANGED")
    before = len(state["references"])
    with pytest.raises(WizardError):
        run(owner, inputs, context=context)
    assert len(state["references"]) == before
