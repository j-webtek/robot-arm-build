"""Static semantic migration preserves behavior without claiming geometry."""

from dataclasses import replace
import hashlib
import json

import pytest

from rocell.calibration.static_phase1_requirements import STATIC_OVERHEAD_PHASE1_GRAPH
from rocell.typing.development_profiles import (
    compile_development_text,
    development_keyboard_profile,
    development_phone_profile,
)
from rocell.typing.static_development_profiles import (
    compile_static_development_text,
    static_development_keyboard_profile,
    static_development_phone_profile,
    static_semantic_profile_binding,
)
from rocell.typing.unicode_support import UnsupportedCharacterError
from rocell.typing import static_development_profiles as static_module


FACTORIES = (
    ("keyboard", development_keyboard_profile, static_development_keyboard_profile),
    ("phone", development_phone_profile, static_development_phone_profile),
)


@pytest.mark.parametrize("device,legacy_factory,static_factory", FACTORIES)
def test_all_supported_characters_preserve_actions_and_text_hash(
    device, legacy_factory, static_factory
):
    legacy, selected = legacy_factory(), static_factory()
    mapping = (
        legacy.character_keys if device == "keyboard" else legacy.character_targets
    )
    # Includes every supported semantic key, repeats, empty text and CRLF.
    for text in ("".join(mapping), "hi hi\r\n", ""):
        historical = compile_development_text(device, text)
        static = compile_static_development_text(device, text)
        assert static.actions == historical.actions
        assert static.requested_text_sha256 == historical.requested_text_sha256
        assert static.profile_id == selected.profile_id != historical.profile_id
        assert (
            static.required_calibrations
            == STATIC_OVERHEAD_PHASE1_GRAPH.device_closure(device)
        )
    assert selected.semantic_content_sha256 != legacy.semantic_content_sha256
    assert "eye_on_arm_extrinsic" in legacy.required_calibrations
    assert "eye_on_arm_extrinsic" not in selected.required_calibrations


@pytest.mark.parametrize("device,legacy_factory,static_factory", FACTORIES)
def test_static_closure_preserves_later_robot_and_controller_gates(
    device, legacy_factory, static_factory
):
    closure = static_factory().required_calibrations
    for required in (
        "phase1_static_intrinsics",
        "phase1_measured_tag_map",
        "phase1_static_extrinsic",
        "phase1_robot_reference",
        "phase1_arm_board",
        "phase1_controller_correlation",
        f"phase1_{device}_tcp",
        f"phase1_{device}_outcome_observer",
    ):
        assert required in closure
    assert not any(
        other in node
        for node in closure
        for other in (("phone",) if device == "keyboard" else ("keyboard",))
    )
    # Preserve the existing graph, including its distinction between passive
    # camera-to-board registration and the later robot-to-board calibration.
    for node in closure:
        for parent in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[node].prerequisites:
            assert closure.index(parent) < closure.index(node)


@pytest.mark.parametrize("device,legacy_factory,static_factory", FACTORIES)
def test_binding_is_deterministic_detached_and_graph_bound(
    device, legacy_factory, static_factory
):
    selected = static_factory()
    binding = static_semantic_profile_binding(selected)
    assert binding == static_semantic_profile_binding(static_factory())
    assert binding["graph_sha256"] == STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash
    assert binding["architecture"] == "RIGID_STATIC_OVERHEAD_EYE_TO_HAND"
    assert binding["camera_catalog_configuration"] == "ARDUCAM_B0477_IMX283_16MM"
    core = {k: v for k, v in binding.items() if k != "binding_sha256"}
    assert (
        binding["binding_sha256"]
        == hashlib.sha256(
            json.dumps(
                core, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        ).hexdigest()
    )
    assert (
        binding["geometry_bound"]
        is binding["installed_calibration_bound"]
        is binding["physical_authority"]
        is False
    )
    assert binding["hardware_commands_generated"] == 0
    binding["required_calibrations"].clear()
    assert static_semantic_profile_binding(selected)["required_calibrations"]


@pytest.mark.parametrize("device,legacy_factory,static_factory", FACTORIES)
@pytest.mark.parametrize(
    "fault", ["legacy", "renamed", "mixed-dependencies", "changed-semantics"]
)
def test_mixed_or_replaced_profile_is_rejected(
    device, legacy_factory, static_factory, fault
):
    selected, legacy = static_factory(), legacy_factory()
    if fault == "legacy":
        selected = legacy
    elif fault == "renamed":
        selected = replace(selected, profile_id="development/unreviewed-v1")
    elif fault == "mixed-dependencies":
        selected = replace(selected, required_calibrations=legacy.required_calibrations)
    elif device == "keyboard":
        selected = replace(
            selected, character_keys={**selected.character_keys, "h": ("I",)}
        )
    else:
        selected = replace(selected, initial_state="KEYBOARD_UPPER")
    with pytest.raises(ValueError, match="static semantic contract"):
        static_semantic_profile_binding(selected)


@pytest.mark.parametrize("device", ["keyboard", "phone"])
@pytest.mark.parametrize("text", ["A", "\U0001f916", "é"])
def test_migration_does_not_add_unsupported_characters(device, text):
    with pytest.raises(UnsupportedCharacterError):
        compile_static_development_text(device, text)


@pytest.mark.parametrize("device", ["", "Keyboard", "android", None])
def test_unknown_device_is_not_an_implicit_fallback(device):
    with pytest.raises(ValueError, match="Unsupported static"):
        compile_static_development_text(device, "hi")


@pytest.mark.parametrize("value", [None, {}, "keyboard"])
def test_binding_does_not_accept_caller_json(value):
    with pytest.raises(TypeError):
        static_semantic_profile_binding(value)


def test_legacy_semantic_hashes_remain_the_locked_historical_values():
    assert development_keyboard_profile().semantic_content_sha256 == (
        "8159068d09cb5547cd5b5c7067f27048e5f383ca74943a35f2751bf345513717"
    )
    assert development_phone_profile().semantic_content_sha256 == (
        "a8426d6aa6699667615d6effbf1174c2bdaff17945f533885cfaeefff013fd10"
    )


def test_graph_semantics_change_binding_even_if_dependency_ids_do_not(monkeypatch):
    profile = static_development_keyboard_profile()
    before = static_semantic_profile_binding(profile)
    graph = STATIC_OVERHEAD_PHASE1_GRAPH
    changed = dict(graph.requirements)
    identifier = "phase1_static_extrinsic"
    changed[identifier] = replace(
        changed[identifier], purpose="MODELED DIFFERENT CONTRACT"
    )
    monkeypatch.setattr(
        static_module,
        "STATIC_OVERHEAD_PHASE1_GRAPH",
        replace(graph, requirements=changed),
    )
    after = static_semantic_profile_binding(profile)
    assert before["required_calibrations"] == after["required_calibrations"]
    assert before["semantic_content_sha256"] == after["semantic_content_sha256"]
    assert before["graph_sha256"] != after["graph_sha256"]
    assert before["binding_sha256"] != after["binding_sha256"]


def test_semantic_compilation_and_binding_perform_no_io(monkeypatch):
    import builtins
    import io
    import socket
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("Semantic compilation must not perform IO")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(io, "open", forbidden)
        patch.setattr(subprocess, "Popen", forbidden)
        patch.setattr(socket, "socket", forbidden)
        for device, _, factory in FACTORIES:
            compile_static_development_text(device, "hi")
            static_semantic_profile_binding(factory())
