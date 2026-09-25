"""Cached diagnostic files only; observations are synthetic, never hardware."""

import base64
from copy import deepcopy
from pathlib import Path
import json
from threading import Event
from time import monotonic_ns

import pytest

from rocell.application import camera_probe_attempt_export as m
from rocell.application.camera_probe_wire_export import CHUNK_CHARS, MARKER
from rocell.application.wizard_diagnostic_export import (
    verify_export,
    sanitize_diagnostic_record,
    MAX_ATTACHMENT_BYTES,
)
from rocell.providers.windows.native_camera_protocol import digest, canonical


def buffer(raw):
    return dict(
        base64=base64.b64encode(raw).decode("ascii"),
        retained_bytes=len(raw),
        retained_sha256=digest(raw),
        omitted_from_observed_buffer=0,
    )


def packet(raw=b"MODELED safe native text\n"):
    return dict(
        schema=m.DIAGNOSTICS_SCHEMA,
        source_sha256="a" * 64,
        launch_session_id="wizard-" + "1" * 32,
        queue=dict(
            operation_id="operation-" + "2" * 32, context_sha256="3" * 64, claimed=True
        ),
        admission=dict(
            status="FAILED_HELD",
            physical_authority=False,
            hardware_qualified=False,
            automatic_retry_allowed=False,
        ),
        dispatch=dict(original_evidence=dict(stdout=buffer(raw), actual_counts=None)),
        completion=None,
        physical_authority=False,
        hardware_qualified=False,
        meaning="MODELED failure diagnostics; unknown counts must remain unknown.",
    )


@pytest.mark.parametrize("size", [0, 1024, 256 * 1024])
def test_safe_native_pipe_bytes_round_trip_without_hidden_base64(size):
    value = packet(b"x" * size)
    snapshot, parts = m.prepare_probe_attempt_export(value)
    assert snapshot["original_bytes_preserved"] is True
    assert m.restore_probe_attempt_export(snapshot, parts) == value
    assert all(0 < len(raw) <= MAX_ATTACHMENT_BYTES for raw in parts.values())
    for raw in parts.values():
        part = json.loads(raw)
        assert (
            sanitize_diagnostic_record(part, maximum_bytes=MAX_ATTACHMENT_BYTES) == part
        )
        assert '"base64"' not in raw.decode("ascii")
    assert (
        m.restore_probe_attempt_export(snapshot, parts)["dispatch"][
            "original_evidence"
        ]["actual_counts"]
        is None
    )


@pytest.mark.parametrize(
    "raw",
    [
        b'{"password":"must-not-leak","value":1}\n',
        b"x" * (CHUNK_CHARS - 6) + b" password=must-not-leak\n",
        b"Authorization: Bearer must-not-leak\n",
        b'{"password":"must-not-leak',
    ],
    ids=["json-key", "part-boundary", "header", "truncated-json"],
)
def test_redact_native_bytes_before_encoding_and_part_boundaries(raw):
    value = packet(raw)
    snapshot, parts = m.prepare_probe_attempt_export(value)
    restored = m.restore_probe_attempt_export(snapshot, parts)
    assert snapshot["original_bytes_preserved"] is False
    decoded = base64.b64decode(
        restored["dispatch"]["original_evidence"]["stdout"]["base64"]
    )
    assert b"must-not-leak" not in decoded
    assert all(b"must-not-leak" not in part for part in parts.values())
    assert snapshot["original_diagnostics_sha256"] == digest(canonical(value))
    assert restored != value


def test_binary_and_control_transform_is_not_claimed_as_original():
    value = packet(b"bad\xff\x00 native output")
    snapshot, parts = m.prepare_probe_attempt_export(value)
    assert snapshot["original_bytes_preserved"] is False
    assert m.restore_probe_attempt_export(snapshot, parts) != value


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "bytes",
        "root",
        "source",
        "node-count",
        "authority",
        "wire-hash",
    ],
)
def test_modified_or_incomplete_reports_are_rejected(fault):
    value = packet()
    if fault == "wire-hash":
        value["dispatch"]["original_evidence"]["stdout"]["retained_sha256"] = "f" * 64
        with pytest.raises(ValueError):
            m.prepare_probe_attempt_export(value)
        return
    snapshot, parts = m.prepare_probe_attempt_export(value)
    if fault == "missing":
        parts.pop(next(iter(parts)))
    elif fault == "extra":
        parts["unexpected.json"] = b"{}"
    elif fault == "bytes":
        parts[next(iter(parts))] += b" "
    elif fault == "root":
        snapshot["root_sha256"] = "f" * 64
    elif fault == "source":
        snapshot["source_binding_sha256"] = "f" * 64
    elif fault == "node-count":
        snapshot["node_count"] += 1
    else:
        snapshot["physical_authority"] = True
    with pytest.raises((ValueError, KeyError)):
        m.restore_probe_attempt_export(snapshot, parts)


def test_file_export_verifies_and_keeps_cancelled_overcapacity_targets_absent(tmp_path):
    value = packet()
    root = tmp_path / "exports"
    cancelled = Event()
    cancelled.set()
    with pytest.raises(ValueError):
        m.export_probe_attempt(
            value,
            export_parent=root,
            cancellation=cancelled,
            deadline_ns=monotonic_ns() + m.TIMEOUT_NS,
        )
    assert not root.exists()
    huge = deepcopy(value)
    huge["completion"] = dict(rows=["x" * 60_000] * 80)
    with pytest.raises(ValueError):
        m.export_probe_attempt(
            huge,
            export_parent=root,
            cancellation=Event(),
            deadline_ns=monotonic_ns() + m.TIMEOUT_NS,
        )
    assert not root.exists()
    receipt = m.export_probe_attempt(
        value,
        export_parent=root,
        cancellation=Event(),
        deadline_ns=monotonic_ns() + m.TIMEOUT_NS,
    )
    assert verify_export(Path(receipt["path"]))["valid"]


def test_queue_only_and_reserved_wire_marker_are_not_admission():
    value = packet()
    value["admission"] = value["dispatch"] = None
    value["queue"]["claimed"] = False
    snapshot, parts = m.prepare_probe_attempt_export(value)
    assert m.restore_probe_attempt_export(snapshot, parts) == value
    value["completion"] = {MARKER: {}}
    with pytest.raises(ValueError):
        m.prepare_probe_attempt_export(value)
