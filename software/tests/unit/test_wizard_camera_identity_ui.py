"""Cached stage-4 browser presentation: actual codecs, modeled metadata only."""

from copy import deepcopy

import pytest

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
    rendered,
    SUBMIT_VALUES,
    REVIEW_VALUES,
    EXPORT_VALUES,
)
from test_wizard_camera_identity_navigation import render
from test_windows_camera_driver_metadata import driver_fixture, unavailable


@pytest.mark.parametrize("missing", [False, True])
def test_actual_v2_metadata_assessment_and_export_remain_blocked(
    identity_composed, missing
):
    arrival, owner, state, source, runner = identity_composed
    native = arrival._native_camera
    packet = native.export_snapshot()["identity_packet"]
    receipt = packet["receipt"]
    receipt.update(
        schema="rocell.windows_camera_identity.v2",
        driver=driver_fixture()["driver"],
        api_calls=receipt["api_calls"] + 4,
        observed_property_bytes=receipt["observed_property_bytes"] + 512,
    )
    receipt["driver"]["devnode"] = receipt["device"]["devnode"]
    if missing:
        receipt["driver"]["provider"] = unavailable()
    choice = native.choices()[0]["value"]
    native.retain_identity(choice, packet, operation_id="modeled-driver-observation")
    native.review(choice, "modeled-driver-reviewer")
    perform(arrival, module.SUBMIT, SUBMIT_VALUES)
    view, page = rendered(arrival)
    expected = "UNAVAILABLE" if missing else "OBSERVED"
    assert f"Exact-devnode driver provider: {expected}" in page["text"]
    assert "USB_DESCRIPTOR_SERIAL_PROVENANCE_REQUIRED" in page["text"]
    assert "RECONNECT_AND_REBOOT_IDENTITY_EVIDENCE_REQUIRED" in page["text"]
    assert (
        view["camera_identity_onboarding"]["cycles"][0]["assessment"]["verdict"]
        == "BLOCKED"
    )
    assert "Physical authority: true" not in page["text"]
    perform(arrival, module.REVIEW, REVIEW_VALUES)
    perform(arrival, module.EXPORT, EXPORT_VALUES)
    rendered(arrival)
    assert not runner.calls


def test_current_pending_historical_and_malformed_subjects_are_inert(identity_composed):
    arrival, owner, state, source, runner = identity_composed
    perform(arrival, module.SUBMIT, SUBMIT_VALUES)
    perform(arrival, module.REVIEW, REVIEW_VALUES)
    perform(arrival, module.EXPORT, EXPORT_VALUES)
    view, _ = rendered(arrival)
    for publication in ("PENDING", "HISTORICAL_HELD"):
        changed = deepcopy(view)
        card = changed["camera_identity_onboarding"]
        card.update(status="HISTORICAL_HELD", next_action=None)
        card["publication"] = dict(status=publication, operation_id=None)
        if publication == "PENDING":
            card.update(cycles=[], identity_entry=None)
        page = render(changed)
        assert "CAMERA_IDENTITY_NOT_VERIFIED" not in page["text"]
        assert (
            "Identity publication pending"
            if publication == "PENDING"
            else "HISTORICAL ONLY"
        ) in page["text"]
        if publication == "PENDING":
            assert "Exact-devnode driver provider:" not in page["text"]

    def changes(card):
        return [
            lambda: card.update(physical_authority=True),
            lambda: card.update(source_sha256="f" * 64),
            lambda: card["original_context"].update(header_sha256="f" * 64),
            lambda: card["cycles"][0]["assessment"].update(verdict="PASS"),
            lambda: card["cycles"][0]["assessment"].update(missing_requirements=[]),
            lambda: card["cycles"][0]["assessment"]["checks"].update(
                exact_devnode_driver_observed=True
            ),
            lambda: card["cycles"][0].update(metadata=None),
            lambda: card["cycles"][0]["review"].update(sequence=2),
            lambda: card["export_receipt"].update(provenance="wrong old shorthand"),
            lambda: card["export_receipt"]["files"][-1].update(name="arbitrary.json"),
            lambda: card["export_receipt"].update(total_bytes=1),
            lambda: card["stage_states"].update(camera_identity="PASS"),
        ]

    for index in range(12):
        changed = deepcopy(view)
        changes(changed["camera_identity_onboarding"])[index]()
        page = render(changed)
        assert "CAMERA_IDENTITY_NOT_VERIFIED" in page["text"], index
        assert "Exact-devnode driver provider:" not in page["text"], index
    assert not runner.calls


def test_current_native_review_and_refreshed_original_offer_submit_link_only(
    identity_composed,
):
    arrival, owner, state, source, runner = identity_composed
    view = arrival.view()
    assert owner.view()["status"] == "WAITING_METADATA"
    # Suppress unrelated fresh application registry choices: this fixture
    # installs an already-owned original store, as a real reopen would do.
    for action in view["actions"]:
        if action["action_id"] in {
            "physical_camera_initialize",
            "physical_camera_discover",
            "physical_camera_reopen",
        }:
            action["enabled"] = False
    page = render(view, module.SUBMIT)
    assert [link["id"] for link in page["links"]] == [module.SUBMIT]
    assert page["navigations"] == ["camera-action-" + module.SUBMIT]
    assert owner.view()["cycles"] == [] and not runner.calls
    for action in view["actions"]:
        if action["action_id"] == module.SUBMIT:
            action["enabled"] = False
    assert module.SUBMIT not in [link["id"] for link in render(view)["links"]]


def test_initial_card_and_missing_legacy_projection_do_not_create_actions(make_service):
    arrival, runner, source = make_service(mode="physical")
    view = arrival.view()
    page = render(view)
    assert "CAMERA_IDENTITY_NOT_VERIFIED" not in page["text"]
    assert "No complete original identity collection" in page["text"]
    del view["camera_identity_onboarding"]
    page = render(view)
    assert "No original identity workflow is available" in page["text"]
    assert not runner.calls
