"""Actual service/codec projections; modeled M1 and identity metadata only.

Rendering is pure. These tests do not call native metadata, devices or helpers.
"""

from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import subprocess

import pytest

from rocell.ui.terminal import _CameraIdentityDisplay, _TerminalWizard
from rocell.application import physical_camera_identity_service as module
from test_arrival_camera_identity_composed import (
    identity_composed,
    identity_wait,
    received,
    static_service,
    modeled,
    setup_flow,
    source_model,
    intake_model,
    model,
    workspace,
    complete_modeled_storage_projection,
    make_service,
    perform,
    SUBMIT_VALUES,
    REVIEW_VALUES,
    EXPORT_VALUES,
)


def render(value, view=None):
    output = []

    def forbidden(*args, **kwargs):
        raise AssertionError("Rendering cannot call the service, input or sleep")

    wizard = _TerminalWizard(SimpleNamespace(), forbidden, output.append, forbidden)
    before = deepcopy(value)
    wizard.show_camera_identity(value, view or {})
    assert value == before
    return "\n".join(output)


def actual(arrival):
    view = arrival.view()
    value = view["camera_identity_onboarding"]
    assert _CameraIdentityDisplay._validate(value, view) is value
    text = render(value, view)
    assert "CAMERA_IDENTITY_NOT_VERIFIED" not in text
    return value, view, text


def test_actual_original_workflow_exports_pending_history_and_strict_negatives(
    identity_composed,
    monkeypatch,
):
    arrival, owner, state, source, runner = identity_composed
    value, view, text = actual(arrival)
    assert value["status"] == "WAITING_METADATA"
    assert "No serial is inferred" in text
    perform(arrival, module.SUBMIT, SUBMIT_VALUES)
    value, view, text = actual(arrival)
    assert value["status"] == "REVIEW_PENDING"
    assert "Exact-devnode driver provider: NOT_RETAINED" in text
    assert "stage-5 entry" in text and "operating-speed" in text
    assert "physical_camera_identity_review" in text
    assert all(code in text for code in _CameraIdentityDisplay.MINIMUM_MISSING)

    # Mutation tests alter cached projections only; no successful evidence is authored.
    changes = (
        lambda p: p.update(source_sha256="f" * 64),
        lambda p: p.update(native_release_allowed=True),
        lambda p: p["original_context"].update(header_sha256="f" * 64),
        lambda p: p["publication"].update(status="PENDING"),
        lambda p: p["stage_states"].update(camera_identity="PASS"),
        lambda p: p["cycles"][0]["metadata"].update(raw_path="DO_NOT_RENDER"),
        lambda p: p["cycles"][0]["assessment"].update(verdict="PASS"),
        lambda p: p["cycles"][0]["assessment"]["checks"].update(
            exact_devnode_driver_observed=True
        ),
        lambda p: p["cycles"][0]["assessment"].update(missing_requirements=[]),
        lambda p: p["cycles"][0].update(helper=None),
        lambda p: p["cycles"][0].update(sequence=True),
    )
    for change in changes:
        broken = deepcopy(value)
        change(broken)
        assert _CameraIdentityDisplay.validate(broken, view) is None
        rejected = render(broken, view)
        assert "CAMERA_IDENTITY_NOT_VERIFIED" in rejected
        assert "DO_NOT_RENDER" not in rejected

    perform(arrival, module.REVIEW, REVIEW_VALUES)
    value, view, text = actual(arrival)
    assert "Exact-subject procedural review cannot upgrade BLOCKED" in text
    assert value["stage_states"]["camera_identity"] == "BLOCKED"
    perform(arrival, module.EXPORT, EXPORT_VALUES)
    value, view, text = actual(arrival)
    assert "Separate identity metadata export" in text
    assert value["export_receipt"]["provenance"]["mode"] == "PHYSICAL_DIAGNOSTIC"
    for change in (
        lambda e: e["files"][-1].update(name="attachment-arbitrary.json"),
        lambda e: e["provenance"].update(mode="physical"),
        lambda e: e["provenance"]["source_identity"].update(source_sha256="f" * 64),
        lambda e: e.update(total_bytes=e["total_bytes"] + 1),
    ):
        broken = deepcopy(value)
        change(broken["export_receipt"])
        assert _CameraIdentityDisplay.validate(broken, view) is None

    # The actual generic export pointer is coverage, never a live/original document.
    pointer = arrival._camera_identity_export_pointer()
    assert _CameraIdentityDisplay._validate(pointer, {}) is pointer
    assert "IDENTITY METADATA POINTER ONLY" in render(pointer)

    # No renderer path may load a file, query a device, create a process or read M1.
    before = state["reads"], state["enters"]
    with monkeypatch.context() as guard:

        def forbidden(*args, **kwargs):
            pytest.fail("cached rendering performed I/O")

        guard.setattr(Path, "read_bytes", forbidden)
        guard.setattr(Path, "read_text", forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        assert _CameraIdentityDisplay.validate(value, view) is value
        assert "CAMERA_IDENTITY_NOT_VERIFIED" not in render(value, view)
    assert before == (state["reads"], state["enters"])

    owner.invalidate()
    historical = owner.view()
    assert _CameraIdentityDisplay._validate(historical, {}) is historical
    assert "HISTORICAL ONLY" in render(historical)
    assert historical["next_action"] is None


def test_initial_and_pending_projection_withholds_subjects_and_show_is_joined(
    identity_composed,
    monkeypatch,
):
    arrival, owner, state, source, runner = identity_composed
    value, view, _ = actual(arrival)
    # The producer owns publication state; no documents are synthesized here.
    owner._publication = dict(status="PENDING", operation_id="operation-pending")
    pending = owner.view()
    assert _CameraIdentityDisplay._validate(pending, view) is pending
    assert "Identity publication pending" in render(pending, view)
    assert pending["cycles"] == [] and pending["identity_entry"] is None
    assert "Identity collection" not in render(pending, view)
    assert "No original identity workflow" in render(None)
    for malformed in ({}, [], "raw identity", dict(value, schema="unknown")):
        assert "CAMERA_IDENTITY_NOT_VERIFIED" in render(malformed, view)

    calls = []
    monkeypatch.setattr(
        _TerminalWizard, "show_camera_identity", lambda self, p, v: calls.append((p, v))
    )
    terminal = _TerminalWizard(
        SimpleNamespace(), lambda _: "", lambda _: None, lambda _: None
    )
    terminal.show(view)
    assert calls == [(view["camera_identity_onboarding"], view)]


@pytest.mark.parametrize("missing_provider", [False, True])
def test_actual_v2_driver_codec_into_service_terminal_stays_blocked(
    request,
    monkeypatch,
    missing_provider,
):
    from rocell.application.wizard_native_camera_metadata import (
        RehearsalNativeCameraMetadataProvider,
    )
    from test_windows_camera_driver_metadata import driver_fixture, unavailable

    original = RehearsalNativeCameraMetadataProvider.identity

    def modeled_v2(self, candidate):
        packet = original(self, candidate)
        receipt = packet["receipt"]
        receipt.update(
            schema="rocell.windows_camera_identity.v2",
            driver=driver_fixture()["driver"],
            api_calls=receipt["api_calls"] + 4,
            observed_property_bytes=receipt["observed_property_bytes"] + 512,
        )
        receipt["driver"]["devnode"] = receipt["device"]["devnode"]
        if missing_provider:
            receipt["driver"]["provider"] = unavailable()
        return packet

    # Explicitly modeled native packet flows through the actual strict parser,
    # enrollment and five stage codecs; no success summary is hand-authored.
    monkeypatch.setattr(RehearsalNativeCameraMetadataProvider, "identity", modeled_v2)
    arrival, owner, state, source, runner = request.getfixturevalue("identity_composed")
    perform(arrival, module.SUBMIT, SUBMIT_VALUES)
    value, view, text = actual(arrival)
    checks = value["cycles"][0]["assessment"]["checks"]
    assert checks["driver_protocol_schema"] == "rocell.windows_camera_identity.v2"
    assert checks["exact_devnode_driver_observed"] is (not missing_provider)
    assert (
        "Exact-devnode driver provider: "
        + ("UNAVAILABLE" if missing_provider else "OBSERVED")
        in text
    )
    assert value["cycles"][0]["assessment"]["verdict"] == "BLOCKED"


@pytest.mark.parametrize("action", [module.SUBMIT, module.REVIEW, module.EXPORT])
def test_actual_identity_forms_are_explicit_and_do_not_expand_global_cap(action):
    owner = object.__new__(module.PhysicalCameraIdentityService)
    fields = list(owner.fields(action))
    assert len(fields) <= 7
    output = []
    answers = []
    expected = {}
    for field in fields:
        if field["type"] == "checkbox":
            assert field["default"] is False
            answer, value = "yes", True
        elif field["type"] == "select":
            answer, value = "1", field["options"][0]["value"]
        else:
            answer = value = "Explicit_label_or_unknown_reason"
            assert field["default"] == ""
        answers.append(answer)
        expected[field["name"]] = value
    supplied = iter(answers)
    terminal = _TerminalWizard(
        SimpleNamespace(), lambda _: next(supplied), output.append, lambda _: None
    )
    assert terminal.gather(dict(action_id=action, fields=fields)) == expected
    malformed = [dict(fields[0], name=f"field_{index}") for index in range(25)]
    with pytest.raises(ValueError, match="bounded field"):
        terminal.gather(dict(action_id=action, fields=malformed))
