"""Read-only real M1 output headroom plus labeled pure quota arithmetic."""

from pathlib import Path
from types import SimpleNamespace
import hashlib

import pytest

from rocell.application import camera_probe_capacity as m
from test_commissioning_camera_persistence import (
    runtime_and_adapter,
    WINDOWS,
    forbid_device_and_process_calls,
    LEASES,
    SESSION,
)
from test_physical_camera_activation_campaign import campaign


def test_fixed_record_bound_includes_all_parts_and_lifecycle_records():
    assert m.MAX_PART_RECORDS == 24
    assert m.CAMPAIGN_RECORD_COUNT == 29
    assert m.PART_RECORD_BOUND > (m.PART_BYTES * 4 + 2) // 3
    assert m.CAMPAIGN_RECORD_BYTES < m.MAX_RECORD_TOTAL_BYTES
    assert m._record_headroom({}, "probe")["remaining_record_count"] == 29


def test_existing_owned_records_are_not_reserved_twice():
    key, attempt = "probe", "attempt-" + "1" * 32
    name = "request-" + hashlib.sha256(key.encode("ascii")).hexdigest() + ".json"
    records = {
        name: {
            "data": {
                "attempt_id": attempt,
                "request_key": key,
                "permit": {"request": {"action_id": m.ACTION_IDS["probe"]}},
            }
        }
    }
    for number in range(5):
        records[str(number)] = {"data": {"attempt_id": attempt, "MODELED": "x" * 100}}
    observation = m._record_headroom(records, key)
    assert observation["remaining_record_count"] == m.CAMPAIGN_RECORD_COUNT - 6
    assert (
        observation["remaining_record_bytes"] + observation["family_record_bytes"]
        == m.CAMPAIGN_RECORD_BYTES
    )
    other = m._record_headroom(records, "another-request")
    assert other["remaining_record_count"] == m.CAMPAIGN_RECORD_COUNT
    assert other["remaining_record_bytes"] == m.CAMPAIGN_RECORD_BYTES


@pytest.mark.parametrize("kind", ["records", "bytes"])
def test_pure_quota_boundary_includes_unwritten_campaign(monkeypatch, kind):
    # Small modeled quotas exercise exact comparisons without a giant fixture.
    monkeypatch.setattr(m, "CAMPAIGN_RECORD_COUNT", 2)
    monkeypatch.setattr(m, "CAMPAIGN_RECORD_BYTES", 200)
    records = {"old": {"data": {"MODELED": True}}}
    used = len(m.canonical_json_bytes(records["old"]))
    monkeypatch.setattr(m, "MAX_RECORDS", 3)
    monkeypatch.setattr(m, "MAX_RECORD_TOTAL_BYTES", used + 200)
    assert m._record_headroom(records, "probe")["remaining_record_count"] == 2
    monkeypatch.setattr(
        m,
        "MAX_RECORDS" if kind == "records" else "MAX_RECORD_TOTAL_BYTES",
        2 if kind == "records" else used + 199,
    )
    with pytest.raises(m.CameraProbeCapacityError, match="RECORD_CAPACITY"):
        m._record_headroom(records, "probe")


@WINDOWS
def test_actual_camera_scope_measures_assigned_volume_without_creating_output(
    tmp_path, monkeypatch
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    plan = campaign(tmp_path, "probe").plan()
    output = runtime.deployment_root / "native-camera-output"
    plan["assigned_parent_directory"] = str(output)
    with adapter.transaction(LEASES) as tx:
        assert not output.exists()
        measured = m.observe_probe_capacity(tx, plan=plan, request_key="probe-capacity")
        assert measured["assigned_output_parent"] == str(output)
        assert measured["capacity_reserved"] is measured["physical_authority"] is False
        assert measured["frame_output_bytes"] == 0
        assert not output.exists()
        required = measured["required_free_bytes"]
        monkeypatch.setattr(
            m.shutil, "disk_usage", lambda _: SimpleNamespace(free=required)
        )
        assert (
            m.observe_probe_capacity(tx, plan=plan, request_key="probe-capacity")[
                "measured_free_bytes"
            ]
            == required
        )
        monkeypatch.setattr(
            m.shutil, "disk_usage", lambda _: SimpleNamespace(free=required - 1)
        )
        with pytest.raises(m.CameraProbeCapacityError, match="DISK_CAPACITY"):
            m.observe_probe_capacity(tx, plan=plan, request_key="probe-capacity")
        assert not output.exists()


@WINDOWS
def test_stage_only_wrong_path_or_existing_file_never_becomes_output_root(
    tmp_path, monkeypatch
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    plan = campaign(tmp_path, "probe").plan()
    output = runtime.deployment_root / "native-camera-output"
    plan["assigned_parent_directory"] = str(output)
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        with pytest.raises(m.CameraProbeCapacityError, match="CONTEXT"):
            m.observe_probe_capacity(tx, plan=plan, request_key="capacity")
    with adapter.transaction(LEASES) as tx:
        wrong = {**plan, "assigned_parent_directory": str(tmp_path / "other")}
        with pytest.raises(m.CameraProbeCapacityError, match="CONTEXT"):
            m.observe_probe_capacity(tx, plan=wrong, request_key="capacity")
        # Only a disposable test file; the collector must neither overwrite it
        # nor treat it as a suitable output parent.
        output.write_bytes(b"MODELED existing non-directory")
        with pytest.raises(ValueError):
            m.observe_probe_capacity(tx, plan=plan, request_key="capacity")
        assert output.read_bytes() == b"MODELED existing non-directory"


@WINDOWS
def test_independent_observer_still_audits_each_call_after_context_validation(
    tmp_path, monkeypatch
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    plan = campaign(tmp_path, "probe").plan()
    plan["assigned_parent_directory"] = str(
        runtime.deployment_root / "native-camera-output"
    )
    with adapter.transaction(LEASES) as tx:
        delegated_audit = tx._audit_records
        calls = []

        def observed_audit(*, include_family=False):
            calls.append(include_family)
            return delegated_audit(include_family=include_family)

        monkeypatch.setattr(tx, "_audit_records", observed_audit)
        for _ in range(2):
            m.observe_probe_capacity(tx, plan=plan, request_key="MODELED-independent")
        assert calls == [True, True]
        with pytest.raises(m.CameraProbeCapacityError, match="CAPACITY_CONTEXT"):
            m.observe_probe_capacity(
                tx,
                plan={**plan, "assigned_parent_directory": str(tmp_path / "wrong")},
                request_key="MODELED-independent",
            )
        assert calls == [True, True]  # Wrong context does not read the family.
