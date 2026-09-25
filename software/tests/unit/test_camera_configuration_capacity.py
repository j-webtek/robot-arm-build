"""Capture-size accounting and actual NTFS scope; no camera/native access."""

from types import SimpleNamespace

import pytest

from rocell.application import camera_configuration_capacity as m
from rocell.application import camera_probe_capacity as probe_capacity
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
)
from rocell.application.camera_activation_campaign_contract import (
    CONFIGURATION_CAPTURE_ACTION_ID,
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
)
from test_commissioning_camera_persistence import (
    runtime_and_adapter,
    WINDOWS,
    forbid_device_and_process_calls,
    LEASES,
    SESSION,
)
from test_physical_camera_activation_campaign import campaign


def test_output_budget_counts_raw_and_ingested_copy_plus_real_metadata_bounds(tmp_path):
    plan = campaign(tmp_path, "capture", configuration_verification=True).plan()
    budget = m.configuration_output_budget(plan)
    assert budget["raw_frame_bytes"] == budget["ingested_frame_bytes"] == 16
    assert budget["preview_bytes"] == 2 * 1024 * 1024
    assert budget["metadata_bytes"] == 2 * m.MAX_JSON_BYTES + 2 * m.MAX_CONTRACT_BYTES
    assert sum(budget.values()) > probe_capacity.PRIVATE_OUTPUT_HEADROOM_BYTES
    for purpose in ("probe", "capture"):
        with pytest.raises(ValueError, match="EXACT_PROFILE"):
            m.configuration_output_budget(campaign(tmp_path, purpose).plan())


@WINDOWS
@pytest.mark.parametrize("sealed", [False, True])
def test_real_original_scope_checks_full_floor_without_creating_output(
    tmp_path, monkeypatch, sealed
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    plan = campaign(
        tmp_path,
        "capture",
        configuration_verification=True,
        sealed_configuration_capture=sealed,
    ).plan()
    output = runtime.deployment_root / "native-camera-output"
    plan["assigned_parent_directory"] = str(output)
    plan = PhysicalCameraActivationCampaign.from_plan(plan).plan()
    with adapter.transaction(LEASES) as tx:
        result = m.observe_configuration_capacity(tx, plan=plan, request_key="settings")
        assert result["schema"] == (m.SEALED_SCHEMA if sealed else m.SCHEMA)
        assert result["record_headroom"]["campaign_record_count_bound"] == (
            probe_capacity.CAMPAIGN_RECORD_COUNT + int(sealed)
        )
        assert result["required_free_bytes"] == (
            m.DISK_RESERVE_BYTES
            + sum(result["output_budget"].values())
            + result["record_headroom"]["remaining_record_bytes"]
        )
        assert result["capacity_reserved"] is result["hardware_qualified"] is False
        assert result["existing_output_credit_bytes"] == 0
        assert not output.exists()
        required = result["required_free_bytes"]
        monkeypatch.setattr(
            m.shutil, "disk_usage", lambda _: SimpleNamespace(free=required)
        )
        assert (
            m.observe_configuration_capacity(tx, plan=plan, request_key="settings")[
                "measured_free_bytes"
            ]
            == required
        )
        monkeypatch.setattr(
            m.shutil, "disk_usage", lambda _: SimpleNamespace(free=required - 1)
        )
        with pytest.raises(ValueError, match="DISK_CAPACITY"):
            m.observe_configuration_capacity(tx, plan=plan, request_key="settings")
        assert not output.exists()


@WINDOWS
def test_stage_only_changed_original_root_and_existing_file_are_refused(tmp_path):
    runtime, adapter = runtime_and_adapter(tmp_path)
    plan = campaign(tmp_path, "capture", configuration_verification=True).plan()
    output = runtime.deployment_root / "native-camera-output"
    plan["assigned_parent_directory"] = str(output)
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        with pytest.raises(ValueError, match="ORIGINAL_CONTEXT"):
            m.observe_configuration_capacity(tx, plan=plan, request_key="settings")
    with adapter.transaction(LEASES) as tx:
        with pytest.raises(ValueError, match="ORIGINAL_CONTEXT"):
            m.observe_configuration_capacity(
                tx,
                plan={**plan, "assigned_parent_directory": str(tmp_path / "wrong")},
                request_key="settings",
            )
        output.write_bytes(b"MODELED file, not output directory")
        with pytest.raises(ValueError):
            m.observe_configuration_capacity(tx, plan=plan, request_key="settings")
        assert output.read_bytes() == b"MODELED file, not output directory"


@WINDOWS
@pytest.mark.parametrize("purpose", ["probe", "configuration", "sealed"])
@pytest.mark.parametrize("quota", ["count", "bytes"])
def test_shared_usb_records_are_included_in_capture_and_probe_headroom(
    tmp_path, monkeypatch, purpose, quota
):
    # Actual scoped store; the additional USB record/quota is a labeled model
    # of capacity arithmetic, not fabricated original onboarding evidence.
    runtime, adapter = runtime_and_adapter(tmp_path)
    probe = purpose == "probe"
    plan = campaign(
        tmp_path,
        "probe" if probe else "capture",
        configuration_verification=not probe,
        sealed_configuration_capture=purpose == "sealed",
    ).plan()
    plan["assigned_parent_directory"] = str(
        runtime.deployment_root / "native-camera-output"
    )
    observe = (
        probe_capacity.observe_probe_capacity
        if probe
        else m.observe_configuration_capacity
    )
    with adapter.transaction(LEASES) as tx:
        read = tx._audit_records
        calls = []

        def family_records(*, include_family=False):
            records = read(include_family=include_family)
            calls.append(include_family)
            if include_family:
                records["MODELED-usb-sibling.json"] = {
                    "data": {"MODELED": "USB history"}
                }
            return records

        monkeypatch.setattr(tx, "_audit_records", family_records)
        if quota == "count":
            monkeypatch.setattr(
                probe_capacity, "MAX_RECORDS", probe_capacity.CAMPAIGN_RECORD_COUNT
            )
        else:
            monkeypatch.setattr(
                probe_capacity,
                "MAX_RECORD_TOTAL_BYTES",
                probe_capacity.CAMPAIGN_RECORD_BYTES,
            )
        with pytest.raises(ValueError, match="RECORD_CAPACITY"):
            observe(tx, plan=plan, request_key="MODELED-family-capacity")
        assert calls == [True]


def test_sealed_checksum_reserves_one_extra_record_before_any_effects(
    tmp_path, monkeypatch
):
    old = probe_capacity._record_headroom(
        {}, "settings", action_id=CONFIGURATION_CAPTURE_ACTION_ID
    )
    new = probe_capacity._record_headroom(
        {}, "settings", action_id=SEALED_CONFIGURATION_CAPTURE_ACTION_ID
    )
    assert new["remaining_record_count"] == old["remaining_record_count"] + 1
    assert (
        new["remaining_record_bytes"]
        == old["remaining_record_bytes"] + probe_capacity.CHECKSUM_RECORD_BOUND
    )
    assert (
        new["campaign_record_bytes_bound"]
        == probe_capacity.SEALED_CAMPAIGN_RECORD_BYTES
    )
    # A volume/family that only fits the old contract must not admit the new one.
    monkeypatch.setattr(probe_capacity, "MAX_RECORDS", old["remaining_record_count"])
    with pytest.raises(ValueError, match="RECORD_CAPACITY"):
        probe_capacity._record_headroom(
            {}, "settings", action_id=SEALED_CONFIGURATION_CAPTURE_ACTION_ID
        )
    assert (
        probe_capacity._record_headroom(
            {}, "settings", action_id=CONFIGURATION_CAPTURE_ACTION_ID
        )
        == old
    )


def test_new_profile_changes_only_original_record_headroom_not_pixel_budget(tmp_path):
    old = campaign(tmp_path, "capture", configuration_verification=True).plan()
    new = campaign(
        tmp_path,
        "capture",
        configuration_verification=True,
        sealed_configuration_capture=True,
    ).plan()
    assert m.configuration_output_budget(old) == m.configuration_output_budget(new)
    assert old["native_budget"] == new["native_budget"]
    assert old["campaign_timeout_ms"] == new["campaign_timeout_ms"] == 25000
