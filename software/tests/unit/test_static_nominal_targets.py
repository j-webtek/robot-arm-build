"""Exact static semantic/nominal geometry joins; no hardware or calibration."""

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from rocell.models.actions import PressKey, TapPhoneTarget
from rocell.targets.nominal import TargetMapError, load_nominal_target_catalog
from rocell.targets import static_nominal as module
from rocell.typing.static_development_profiles import (
    compile_static_development_text,
    static_development_keyboard_profile,
    static_development_phone_profile,
)


@pytest.fixture
def workspace(tmp_path):
    source = Path(__file__).resolve().parents[3]
    for relative in (
        module.GEOMETRY_SOURCE_PATH,
        module.STATIC_NOMINAL_TARGET_PATH,
        "active-project/RoCell_v0_3/config/workcell_layout.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, destination)
    return tmp_path


def test_complete_geometry_is_identical_and_all_semantic_actions_resolve(workspace):
    old = load_nominal_target_catalog(workspace)
    new = module.load_static_nominal_target_catalog(workspace)
    assert new.keyboard_targets == old.keyboard_targets
    assert new.phone_targets == old.phone_targets
    assert new.workcell_layout_path == old.workcell_layout_path
    assert (len(new.keyboard_targets), len(new.phone_targets)) == (46, 29)
    for device, factory in (
        ("keyboard", static_development_keyboard_profile),
        ("phone", static_development_phone_profile),
    ):
        profile = factory()
        text = "".join(
            profile.character_keys
            if device == "keyboard"
            else profile.character_targets
        )
        plan = compile_static_development_text(device, text)
        assert new.semantic_profile_id_for(device) == plan.profile_id
        assert old.semantic_profile_id_for(device) != plan.profile_id
        for action in plan.actions:
            if isinstance(action, PressKey):
                assert new.resolve(device, action.key_id) == old.resolve(
                    device, action.key_id
                )
            elif isinstance(action, TapPhoneTarget):
                assert new.resolve(device, action.target_id) == old.resolve(
                    device, action.target_id
                )
    assert new.simulation_only
    assert new.to_dict()["physical_release_effect"] == "NONE"


@pytest.mark.parametrize(
    "fault",
    [
        "semantic-id",
        "semantic-hash",
        "key-centre",
        "phone-origin",
        "graph",
        "authority",
        "missing-binding",
        "extra",
        "source",
        "bool",
    ],
)
def test_modified_static_contract_is_not_accepted(workspace, fault):
    path = workspace / module.STATIC_NOMINAL_TARGET_PATH
    data = json.loads(path.read_text("utf-8"))
    if fault == "semantic-id":
        data["keyboard"][
            "semantic_profile_id"
        ] = "development/keyboard-us-lowercase-semantic-v1"
    elif fault == "semantic-hash":
        data["phone"]["semantic_profile_sha256"] = "1" * 64
    elif fault == "key-centre":
        data["keyboard"]["rows"][0]["first_center_xy_mm"][0] += 1
    elif fault == "phone-origin":
        data["phone"]["device_origin_board_xy_mm"][0] += 1
    elif fault == "graph":
        data["static_binding"]["semantic_profiles"]["phone"]["graph_sha256"] = "1" * 64
    elif fault == "authority":
        data["static_binding"]["physical_authority"] = True
    elif fault == "missing-binding":
        del data["static_binding"]
    elif fault == "extra":
        data["not_in_contract"] = True
    elif fault == "source":
        data["static_binding"]["geometry_source"]["sha256"] = "1" * 64
    else:
        data["schema_version"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(TargetMapError, match="binding differs"):
        module.load_static_nominal_target_catalog(workspace)


def test_changed_legacy_geometry_seed_is_rejected(workspace):
    path = workspace / module.GEOMETRY_SOURCE_PATH
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(TargetMapError, match="geometry source changed"):
        module.load_static_nominal_target_catalog(workspace)


@pytest.mark.parametrize(
    "fault", ["duplicate", "non-finite", "oversized", "non-object"]
)
def test_malformed_catalog_is_rejected(workspace, fault):
    path = workspace / module.STATIC_NOMINAL_TARGET_PATH
    contents = {
        "duplicate": b'{"schema": 1, "schema": 2}',
        "non-finite": b'{"schema": NaN}',
        "oversized": b" " * (module.MAX_CATALOG_BYTES + 1),
        "non-object": b"[]",
    }
    path.write_bytes(contents[fault])
    with pytest.raises(TargetMapError):
        module.load_static_nominal_target_catalog(workspace)


@pytest.mark.parametrize(
    "fault", ["wrong-parser-result", "selected-file", "geometry-source"]
)
def test_changed_sources_or_parser_result_during_load_reject(
    workspace, monkeypatch, fault
):
    actual = module.load_nominal_target_catalog

    def read_then_change(*args, **kwargs):
        catalog = actual(*args, **kwargs)
        if fault == "wrong-parser-result":
            return replace(catalog, content_sha256="1" * 64)
        relative = (
            module.STATIC_NOMINAL_TARGET_PATH
            if fault == "selected-file"
            else module.GEOMETRY_SOURCE_PATH
        )
        path = workspace / relative
        path.write_bytes(path.read_bytes() + b" ")
        return catalog

    monkeypatch.setattr(module, "load_nominal_target_catalog", read_then_change)
    with pytest.raises(TargetMapError, match="changed"):
        module.load_static_nominal_target_catalog(workspace)


def test_changed_workcell_origin_is_rejected_by_numerical_parser(workspace):
    path = workspace / "active-project/RoCell_v0_3/config/workcell_layout.json"
    data = json.loads(path.read_text("utf-8"))
    data["devices"]["keyboard"]["nominal_origin_xy"][0] += 1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(TargetMapError):
        module.load_static_nominal_target_catalog(workspace)
