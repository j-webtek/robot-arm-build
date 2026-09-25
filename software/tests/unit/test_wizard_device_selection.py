"""Pure typed metadata fixtures; these tests never enumerate or open devices."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import pytest

from rocell.application.physical_connection_contracts import canonical_sha256
import rocell.application.physical_device_inventory as inventory
import rocell.application.wizard_device_selection as selection_module
from rocell.application.wizard_device_selection import (
    DeviceSelectionError,
    MAX_INVENTORY_BYTES,
    WizardDeviceSelection,
)


def candidate(
    device_class: str, *, source: str | None = None, unit: str = "FIXTURE-001"
) -> inventory.NormalizedDeviceCandidate:
    return inventory.NormalizedDeviceCandidate(
        device_class=inventory.InventoryDeviceClass(device_class),
        source=inventory.InventorySource(
            source
            or (
                "WINDOWS_PNP"
                if device_class == "CAMERA"
                else "INJECTED_SERIAL_ENUMERATOR"
            )
        ),
        display_name=f"Synthetic {device_class} {unit}",
        vid="fffe",
        pid="0001" if device_class == "CAMERA" else "0002",
        unit_serial=unit,
        os_instance_id=f"fixture:{device_class}:{unit}",
        persistent_ids=(f"fixture-unit:{device_class}:{unit}",),
        ephemeral_locator="fixture-camera" if device_class == "CAMERA" else "COM42",
        manufacturer="Synthetic fixture",
        product="Unverified model",
        driver_service=None,
        identity_blockers=(),
    )


def report(
    *, mode: str = "rehearsal", platform: str = "Windows", cameras=None, serials=None
) -> dict[str, Any]:
    camera_source = "WINDOWS_PNP" if platform == "Windows" else "LINUX_SYSFS"
    serial_source = (
        "INJECTED_SERIAL_ENUMERATOR" if mode == "rehearsal" else "PYSERIAL_LIST_PORTS"
    )
    if cameras is None:
        cameras = (candidate("CAMERA", source=camera_source),)
    if serials is None:
        serials = (candidate("SERIAL", source=serial_source),)

    def batch(kind, source, rows):
        return inventory.DeviceInventoryBatch(
            inventory.InventoryDeviceClass(kind),
            inventory.InventorySource(source),
            tuple(sorted(rows, key=lambda item: item.sort_key)),
            (),
            True,
        )

    return inventory.compose_physical_device_inventory_report(
        platform_system=platform,
        captured_at_unix_ns=1,
        camera_inventory=batch("CAMERA", camera_source, cameras),
        serial_inventory=batch("SERIAL", serial_source, serials),
    ).to_dict()


def selection(mode="rehearsal") -> WizardDeviceSelection:
    return WizardDeviceSelection(mode, "wizard-fixture-session", "a" * 64)


def choice(model, kind="CAMERA"):
    return model.choices(kind)[0]["value"]


def rehash(value):
    value["report_sha256"] = canonical_sha256(
        {k: v for k, v in value.items() if k != "report_sha256"}
    )


def assert_no_authority(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {
                "physical_authority",
                "connected",
                "qualified",
                "persistent_binding",
            }:
                assert child is False
            assert_no_authority(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_authority(child)


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
@pytest.mark.parametrize("platform", ["Windows", "Linux"])
def test_exact_typed_report_review_retains_original_without_connecting(mode, platform):
    model = selection(mode)
    original = report(mode=mode, platform=platform)
    model.ingest(original, operation_id="operation-1")
    before = model.view()
    assert before["status"] == "METADATA_CANDIDATES_AVAILABLE"
    assert all(device["review"] is None for device in before["devices"].values())
    assert "inventory_report" not in json.dumps(before)
    for kind in ("CAMERA", "SERIAL"):
        token = choice(model, kind)
        preview = model.preview(token, kind)
        assert (
            preview["candidate_record"]
            == original[kind.lower() + "_inventory"]["candidates"][0]
        )
        reviewed = model.review(token, kind, "fixture-reviewer")
        assert reviewed["inventory_report"] == original
        assert reviewed["review"]["status"] == "METADATA_ACKNOWLEDGED_FOR_INVESTIGATION"
        assert (
            reviewed["review"]["candidate_sha256"]
            == preview["candidate"]["candidate_sha256"]
        )
        assert reviewed["review"]["operation_id"] == "operation-1"
        assert len(reviewed["followup_requirements"]) == 4
        assert_no_authority(reviewed)
        assert model.review(token, kind, "fixture-reviewer") == reviewed
    assert model.view()["status"] == "METADATA_REVIEW_RECORDED"


def test_constructor_and_all_metadata_operations_do_not_touch_files_or_providers(
    monkeypatch,
):
    original = report()

    def forbidden(*args, **kwargs):
        pytest.fail("metadata selection attempted I/O or provider work")

    for name in (
        "inventory_windows_pnp_cameras",
        "inventory_linux_video_cameras_from_sysfs",
        "inventory_serial_ports_from_provider",
        "inventory_serial_ports_with_pyserial",
    ):
        monkeypatch.setattr(inventory, name, forbidden)
    monkeypatch.setattr(inventory.importlib, "import_module", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(inventory.subprocess, "run", forbidden)
    model = selection()
    assert model.view()["status"] == "NO_INVENTORY"
    assert model.choices("CAMERA") == []
    model.ingest(original, operation_id="operation-1")
    model.review(choice(model), "CAMERA", "reviewer")
    model.invalidate("SOURCE_CHANGED")
    assert model.view()["status"] == "INVALIDATED"


def test_input_and_output_mutation_cannot_change_retained_snapshot():
    model = selection()
    original = report()
    expected = deepcopy(original)
    model.ingest(original, operation_id="op-1")
    token = choice(model)
    original["camera_inventory"]["candidates"][0]["display_name"] = "mutated input"
    preview = model.preview(token, "CAMERA")
    preview["candidate_record"]["persistent_ids"].append("changed")
    reviewed = model.review(token, "CAMERA", "reviewer")
    reviewed["inventory_report"]["blockers"].clear()
    reviewed["review"]["followup_requirements"].clear()
    view = model.view()
    view["devices"]["CAMERA"]["candidates"][0]["identity_blockers"].append("CHANGED")
    view["devices"]["CAMERA"]["review"]["reviewer_id"] = "changed"
    again = model.review(token, "CAMERA", "reviewer")
    assert again["inventory_report"] == expected
    assert len(again["review"]["followup_requirements"]) == 4
    assert "CHANGED" not in again["candidate"]["identity_blockers"]


def test_replacement_and_invalidation_clear_every_old_choice_and_review():
    model = selection()
    original = report()
    model.ingest(original, operation_id="op-1")
    old = choice(model)
    model.review(old, "CAMERA", "reviewer")
    model.ingest(original, operation_id="op-2")
    assert choice(model) != old
    assert model.view()["devices"]["CAMERA"]["review"] is None
    with pytest.raises(DeviceSelectionError, match="current choice") as caught:
        model.review(old, "CAMERA", "reviewer")
    assert caught.value.code == "STALE_OR_UNKNOWN_CHOICE"
    current = choice(model)
    model.invalidate("SOURCE_CHANGED")
    view = model.view()
    assert view["operation_id"] is view["report_sha256"] is None
    assert view["provenance"]["platform_system"] is None
    assert view["provenance"]["captured_at_unix_ns"] is None
    assert model.choices("CAMERA") == []
    with pytest.raises(DeviceSelectionError):
        model.preview(current, "CAMERA")


@pytest.mark.parametrize(
    "mode,other", [("physical", "rehearsal"), ("rehearsal", "physical")]
)
def test_wrong_serial_source_never_issues_choices(mode, other):
    model = selection(mode)
    with pytest.raises(DeviceSelectionError) as caught:
        model.ingest(report(mode=other), operation_id="op")
    assert caught.value.code == "INVENTORY_SOURCE_MISMATCH"
    assert model.choices("SERIAL") == []


@pytest.mark.parametrize(
    "path,new_value",
    [
        (("schema",), "wrong"),
        (("purpose",), "DEVICE_CONNECTION"),
        (("platform_system",), "Darwin"),
        (("captured_at_unix_ns",), True),
        (("report_sha256",), "0" * 64),
        (("authority", "motion_authorized"), True),
        (("authority", "camera_opened"), 0),
        (("camera_inventory", "boundary", "selection_performed"), True),
        (("camera_inventory", "collection_complete"), 1),
        (("camera_inventory", "candidates", 0, "qualified"), True),
        (("camera_inventory", "candidates", 0, "selection_performed"), 0),
        (("camera_inventory", "candidates", 0, "display_name"), " white space "),
        (("camera_inventory", "candidates", 0, "usb_identity", "vid"), "FFFE"),
        (("camera_inventory", "candidates", 0, "persistent_ids"), ["0"]),
        (("camera_inventory", "candidates", 0, "source"), "LINUX_SYSFS"),
        (("camera_inventory", "candidates", 0, "device_class"), "SERIAL"),
        (("blockers",), []),
    ],
)
def test_strict_shapes_hash_types_sources_and_normalization_cannot_drift(
    path, new_value
):
    model = selection()
    model.ingest(report(), operation_id="op-old")
    original = report()
    target = original
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = new_value
    # Rehashing malformed metadata must not bypass schema/semantic equality.
    if path != ("report_sha256",):
        rehash(original)
    with pytest.raises(DeviceSelectionError):
        model.ingest(original, operation_id="op-new")
    assert model.view()["status"] == "INVALIDATED"
    assert model.choices("CAMERA") == []


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("authority",),
        ("camera_inventory",),
        ("camera_inventory", "boundary"),
        ("camera_inventory", "candidates", 0),
        ("camera_inventory", "candidates", 0, "usb_identity"),
    ],
)
def test_unknown_fields_rejected_at_each_inventory_layer(path):
    value = report()
    nested = value
    for key in path:
        nested = nested[key]
    nested["unexpected"] = "field"
    rehash(value)
    with pytest.raises(DeviceSelectionError):
        selection().ingest(value, operation_id="op")


@pytest.mark.parametrize("kind", ["camera_inventory", "serial_inventory"])
def test_partial_or_failed_collection_rejected_even_with_valid_report_hash(kind):
    value = report()
    value[kind]["collection_complete"] = False
    value[kind]["collection_blockers"] = ["FIXTURE_COLLECTION_FAILED"]
    rehash(value)
    with pytest.raises(DeviceSelectionError) as caught:
        selection().ingest(value, operation_id="op")
    assert caught.value.code == "INVENTORY_INCOMPLETE"


def test_duplicate_occurrences_remain_distinct_choices_with_explicit_ambiguity():
    duplicate = candidate("CAMERA")
    model = selection()
    model.ingest(report(cameras=(duplicate, duplicate)), operation_id="op")
    choices = model.choices("CAMERA")
    assert len(choices) == 2 and choices[0]["value"] != choices[1]["value"]
    summaries = model.view()["devices"]["CAMERA"]["candidates"]
    assert summaries[0]["candidate_sha256"] == summaries[1]["candidate_sha256"]
    for summary in summaries:
        assert "CAMERA_DUPLICATE_METADATA_OCCURRENCE" in summary["identity_blockers"]
        assert "CAMERA_USB_UNIT_IDENTITY_AMBIGUOUS" in summary["identity_blockers"]
        assert "CAMERA_PERSISTENT_ID_AMBIGUOUS" in summary["identity_blockers"]
        assert_no_authority(model.review(summary["choice_id"], "CAMERA", "reviewer"))


def test_missing_identity_is_derived_even_if_source_candidate_omits_blocker_codes():
    missing = replace(
        candidate("SERIAL"),
        vid=None,
        pid=None,
        unit_serial=None,
        os_instance_id=None,
        persistent_ids=(),
        identity_blockers=(),
    )
    model = selection()
    value = report(serials=(missing,))
    model.ingest(value, operation_id="op")
    reviewed = model.review(choice(model, "SERIAL"), "SERIAL", "reviewer")
    assert reviewed["candidate"]["identity_blockers"] == [
        "SERIAL_OS_INSTANCE_ID_MISSING",
        "SERIAL_PERSISTENT_SELECTOR_MISSING",
        "SERIAL_PID_MISSING",
        "SERIAL_UNIT_SERIAL_MISSING",
        "SERIAL_VID_MISSING",
    ]
    assert reviewed["inventory_report"] == value
    assert reviewed["candidate_record"]["identity_blockers"] == []
    assert_no_authority(reviewed)


def test_empty_complete_inventory_does_not_auto_select_anything():
    model = selection()
    model.ingest(report(cameras=(), serials=()), operation_id="op")
    assert model.choices("CAMERA") == model.choices("SERIAL") == []
    assert all(item["review"] is None for item in model.view()["devices"].values())
    with pytest.raises(DeviceSelectionError):
        model.review("COM42", "SERIAL", "reviewer")


def test_128_candidate_choice_list_and_labels_are_bounded():
    rows = tuple(
        replace(candidate("CAMERA", unit=f"U{index:03}"), display_name="X" * 128)
        for index in range(128)
    )
    value = report(cameras=rows, serials=())
    assert len(json.dumps(value, separators=(",", ":")).encode()) < MAX_INVENTORY_BYTES
    model = selection()
    model.ingest(value, operation_id="op")
    choices = model.choices("CAMERA")
    assert len(choices) == 128
    assert max(len(row["label"]) for row in choices) <= 192
    assert len({row["value"] for row in choices}) == 128


def test_label_is_explicitly_shortened_but_full_candidate_and_report_retained():
    row = replace(candidate("CAMERA"), display_name="X" * 2048)
    model = selection()
    model.ingest(report(cameras=(row,)), operation_id="op")
    assert "..." in model.choices("CAMERA")[0]["label"]
    assert (
        model.preview(choice(model), "CAMERA")["candidate"]["display_name"]
        == row.display_name
    )


@pytest.mark.parametrize(
    "bad",
    [
        [],
        None,
        {"cycle": None},
        {"oversize": "x" * (MAX_INVENTORY_BYTES + 1)},
        {"float": 1.0},
    ],
)
def test_non_json_shape_and_resource_limits_are_rejected(bad):
    if isinstance(bad, dict) and "cycle" in bad:
        bad["cycle"] = bad
    with pytest.raises(DeviceSelectionError):
        selection().ingest(bad, operation_id="op")


@pytest.mark.parametrize(
    "mode,session,source",
    [
        ("wrong", "session", "a" * 64),
        (True, "session", "a" * 64),
        ("physical", "", "a" * 64),
        ("physical", "../session", "a" * 64),
        ("physical", "session", "A" * 64),
    ],
)
def test_constructor_rejects_invalid_bindings(mode, session, source):
    with pytest.raises(DeviceSelectionError):
        WizardDeviceSelection(mode, session, source)


def test_class_confusion_unknown_choices_and_invalid_reviewer_rejected():
    model = selection()
    model.ingest(report(), operation_id="op")
    with pytest.raises(DeviceSelectionError) as caught:
        model.preview(choice(model), "SERIAL")
    assert caught.value.code == "CHOICE_CLASS_MISMATCH"
    for kind in ("camera", "ARM", True):
        with pytest.raises(DeviceSelectionError):
            model.choices(kind)
    for token in ("COM42", "0", [], None):
        with pytest.raises(DeviceSelectionError):
            model.preview(token, "CAMERA")
    for reviewer in ("", " reviewer", "x\n", "x" * 129):
        with pytest.raises(DeviceSelectionError):
            model.review(choice(model), "CAMERA", reviewer)
    assert model.view()["devices"]["CAMERA"]["review"] is None


def test_staged_copy_has_fresh_lock_and_does_not_publish_review_or_ingest():
    model = selection()
    model.ingest(report(), operation_id="op-original")
    before = model.view()
    staged = model.staged_copy()
    assert staged.view() == before
    assert staged._lock is not model._lock
    staged.review(choice(staged), "CAMERA", "staged-reviewer")
    assert model.view() == before
    assert staged.view()["status"] == "METADATA_REVIEW_RECORDED"
    staged.ingest(report(), operation_id="op-staged")
    assert model.view() == before
    assert staged.view()["operation_id"] == "op-staged"
    with pytest.raises(DeviceSelectionError):
        staged.preview(choice(model), "CAMERA")
    assert model.preview(choice(model), "CAMERA")["operation_id"] == "op-original"


def test_staged_copy_reviews_and_blockers_are_detached_both_directions():
    duplicate = candidate("CAMERA")
    model = selection()
    model.ingest(report(cameras=(duplicate, duplicate)), operation_id="op")
    model.review(choice(model), "CAMERA", "original-reviewer")
    staged = model.staged_copy()
    staged._reviews["CAMERA"]["followup_requirements"].clear()
    staged._choices[choice(staged)][1].clear()
    original = model.view()
    assert len(original["devices"]["CAMERA"]["review"]["followup_requirements"]) == 4
    assert original["devices"]["CAMERA"]["candidates"][0]["identity_blockers"]
    model.invalidate("SOURCE_CHANGED")
    assert staged.view()["report_sha256"] is not None


def test_staged_copy_of_initial_and_invalidated_state_is_exact():
    model = selection()
    assert model.staged_copy().view() == model.view()


def test_reviewed_candidate_is_inert_exact_and_returns_detached_data(monkeypatch):
    model = selection()
    assert model.reviewed_candidate("CAMERA") is None
    model.ingest(report(), operation_id="op")
    assert model.reviewed_candidate("CAMERA") is None
    expected = model.review(choice(model), "CAMERA", "reviewer")
    before = model.view()

    def forbidden(*args, **kwargs):
        pytest.fail("reading acknowledgement cannot call review or issue choices")

    monkeypatch.setattr(model, "review", forbidden)
    monkeypatch.setattr(selection_module, "uuid4", forbidden)
    actual = model.reviewed_candidate("CAMERA")
    assert actual == expected
    actual["inventory_report"]["blockers"].clear()
    actual["review"]["reviewer_id"] = "changed"
    assert model.reviewed_candidate("CAMERA") == expected
    assert model.view() == before
    model.invalidate("SOURCE_CHANGED")
    assert model.reviewed_candidate("CAMERA") is None
    model.invalidate("SOURCE_CHANGED")
    assert model.staged_copy().view() == model.view()


def test_retained_model_and_bytes_share_one_owned_snapshot(monkeypatch):
    source = report()
    original = deepcopy(source)
    encode = selection_module._bounded_document

    def change_after_copy(value):
        payload = encode(value)
        value["camera_inventory"]["candidates"][0]["display_name"] = "CHANGED"
        rehash(value)
        return payload

    monkeypatch.setattr(selection_module, "_bounded_document", change_after_copy)
    model = selection()
    model.ingest(source, operation_id="op")
    result = model.review(choice(model), "CAMERA", "reviewer")
    assert result["inventory_report"] == original
    assert result["candidate_record"] == original["camera_inventory"]["candidates"][0]


def test_random_collision_fails_closed_and_reset_does_not_resurrect_token(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        selection_module, "uuid4", lambda: SimpleNamespace(hex="0" * 32)
    )
    model = selection()
    model.ingest(report(serials=()), operation_id="op-1")
    old = choice(model)
    model.ingest(report(serials=()), operation_id="op-2")
    assert choice(model) != old
    with pytest.raises(DeviceSelectionError):
        model.preview(old, "CAMERA")
    with pytest.raises(DeviceSelectionError) as caught:
        model.ingest(report(), operation_id="op-3")
    assert caught.value.code == "CHOICE_COLLISION"
    assert model.choices("CAMERA") == []


@pytest.mark.parametrize("bad_text", ["\ud800", "x" * 513])
def test_invalid_text_reports_fixed_error_code(bad_text):
    with pytest.raises(DeviceSelectionError) as caught:
        selection().invalidate(bad_text)
    assert caught.value.code == "INVALID_INPUT"
