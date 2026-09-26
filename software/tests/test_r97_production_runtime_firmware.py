from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _stage_module(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import stage_r97_production_runtime

    return stage_r97_production_runtime


def test_r97_source_is_minimal_safe_idle_and_deterministic(monkeypatch):
    module = _stage_module(monkeypatch)
    first = module.sources(ROOT)
    second = module.sources(ROOT)
    assert first == second
    assert set(first) == {"RoArm-M3_example.ino", "production_runtime_v1.h"}
    combined = b"\n".join(first.values())
    assert combined.count(b"SyncWritePosEx") == 1
    assert b"startup_motion_commands\\\":0" in combined
    assert b"configuration_epoch_sha256\\\":null" in combined
    assert b"esp_partition_get_sha256" in combined
    assert b"Serial1.begin" in combined


@pytest.mark.parametrize(
    "token",
    [
        b"WiFi", b"WebServer", b"LittleFS", b"Preferences", b"esp_now",
        b"serialCtrl", b"webCtrlServer", b"mission", b"servo_.WritePosEx(",
    ],
)
def test_r97_source_excludes_broad_or_persistent_surfaces(monkeypatch, token):
    combined = b"\n".join(_stage_module(monkeypatch).sources(ROOT).values())
    assert token not in combined


def test_r97_surface_is_exact_and_fail_closed(monkeypatch):
    runtime = _stage_module(monkeypatch).sources(ROOT)["production_runtime_v1.h"]
    assert b"strcmp(line_, \"{\\\"T\\\":105}\")" in runtime
    assert b"strncmp(line_, \"{\\\"T\\\":102,\", 9)" in runtime
    assert b"UNSUPPORTED_OR_MALFORMED_COMMAND" in runtime
    assert b"NONCANONICAL_WHITESPACE" in runtime
    assert b"INVALID_T102" in runtime
    assert b"NONCANONICAL_CARRIAGE_RETURN" in runtime
    assert b"kMaximumPayloadBytes = kMaximumWireBytes - 1" in runtime
    assert b"terminal_locked_ = true" in runtime
    assert b"if (terminal_locked_) continue" in runtime


def test_r97_stage_never_overwrites_drift(tmp_path, monkeypatch):
    module = _stage_module(monkeypatch)
    source_root = tmp_path / "src/rocell/arm"
    source_root.mkdir(parents=True)
    for name in ("all_joint_command.py", "joint_mapping.py"):
        (source_root / name).write_bytes((ROOT / "src/rocell/arm" / name).read_bytes())
    result = module.stage(tmp_path)
    assert result["status"] == "STAGED_OFFLINE_NOT_COMPILED_NOT_INSTALLED"
    assert result["hardware_access"] is False
    staged = (tmp_path / ".firmware-tools" / module.TARGET /
              "RoArm-M3_example" / "production_runtime_v1.h")
    staged.write_bytes(staged.read_bytes() + b"drift")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        module.stage(tmp_path)
