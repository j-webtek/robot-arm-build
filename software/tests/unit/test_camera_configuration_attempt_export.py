"""Separate cached settings-attempt exports; no process or device access."""

import base64
from copy import deepcopy
from pathlib import Path
from threading import Event
from time import monotonic_ns

import pytest

from rocell.application import camera_configuration_attempt_export as m
from rocell.application import camera_probe_attempt_export as probe
from rocell.application.wizard_diagnostic_export import verify_export
from test_camera_probe_attempt_export import packet
from test_commissioning_camera_persistence import forbid_device_and_process_calls


def configuration_packet(raw=b"MODELED settings capture\n"):
    value = packet(raw)
    value["schema"] = m.DIAGNOSTICS_SCHEMA
    value["admission"]["settings_epoch"] = "5" * 64
    return value


@pytest.mark.parametrize(
    "raw",
    [b"", b"safe\n", b"x" * (256 * 1024)],
    ids=["empty", "short", "maximum-buffer"],
)
def test_settings_report_has_distinct_schema_names_and_lossless_safe_bytes(raw):
    value = configuration_packet(raw)
    snapshot, parts = m.prepare_configuration_attempt_export(value)
    assert snapshot["schema"] == m.SCHEMA != probe.SCHEMA
    assert all(name.startswith("camera-configuration-attempt-part-") for name in parts)
    assert all(b'"base64"' not in payload for payload in parts.values())
    assert snapshot["original_bytes_preserved"] is True
    assert m.restore_configuration_attempt_export(snapshot, parts) == value
    assert snapshot["device_io_performed"] is snapshot["physical_authority"] is False


def test_probe_and_settings_families_cannot_be_substituted():
    value = configuration_packet()
    settings_snapshot, settings_parts = m.prepare_configuration_attempt_export(value)
    probe_snapshot, probe_parts = probe.prepare_probe_attempt_export(packet())
    with pytest.raises(ValueError):
        probe.prepare_probe_attempt_export(value)
    with pytest.raises(ValueError):
        m.prepare_configuration_attempt_export(packet())
    with pytest.raises(ValueError):
        probe.restore_probe_attempt_export(settings_snapshot, settings_parts)
    with pytest.raises(ValueError):
        m.restore_configuration_attempt_export(probe_snapshot, probe_parts)


@pytest.mark.parametrize("fault", ["part", "source", "authority", "unknown-schema"])
def test_incomplete_or_changed_configuration_report_cannot_restore(fault):
    snapshot, parts = m.prepare_configuration_attempt_export(configuration_packet())
    if fault == "part":
        parts.pop(next(iter(parts)))
    elif fault == "source":
        snapshot["source_binding_sha256"] = "f" * 64
    elif fault == "authority":
        snapshot["physical_authority"] = True
    else:
        snapshot["schema"] = "unknown"
    with pytest.raises(ValueError):
        m.restore_configuration_attempt_export(snapshot, parts)


def test_redaction_keeps_unknown_counts_unknown_and_does_not_claim_original_bytes():
    value = configuration_packet(b'{"password":"do-not-export"}\n')
    snapshot, parts = m.prepare_configuration_attempt_export(value)
    restored = m.restore_configuration_attempt_export(snapshot, parts)
    evidence = restored["dispatch"]["original_evidence"]
    assert evidence["actual_counts"] is None
    assert b"do-not-export" not in base64.b64decode(evidence["stdout"]["base64"])
    assert snapshot["original_bytes_preserved"] is False
    assert snapshot["credential_redaction_applied"] is True


def test_settings_export_uses_exact_folder_and_refuses_cancel_overcapacity_without_creation(
    tmp_path,
):
    root = tmp_path / "assigned-settings-exports"
    value = configuration_packet()
    stop = Event()
    stop.set()
    with pytest.raises(ValueError):
        m.export_configuration_attempt(
            value,
            export_parent=root,
            cancellation=stop,
            deadline_ns=monotonic_ns() + m.TIMEOUT_NS,
        )
    assert not root.exists()
    large = deepcopy(value)
    large["completion"] = {"MODELED": ["x" * 60000] * 80}
    with pytest.raises(ValueError):
        m.export_configuration_attempt(
            large,
            export_parent=root,
            cancellation=Event(),
            deadline_ns=monotonic_ns() + m.TIMEOUT_NS,
        )
    assert not root.exists()
    result = m.export_configuration_attempt(
        value,
        export_parent=root,
        cancellation=Event(),
        deadline_ns=monotonic_ns() + m.TIMEOUT_NS,
    )
    destination = Path(result["path"])
    assert destination.parent == root
    assert verify_export(destination)["valid"]
