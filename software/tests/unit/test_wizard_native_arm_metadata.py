"""Pure/injected arm metadata tests; never enumerate this host or open a port."""

from copy import deepcopy
from dataclasses import replace
import ctypes
import json
from pathlib import Path
import subprocess
from threading import Event

import pytest

from rocell.application import wizard_native_arm_metadata as metadata
from rocell.application import wizard_device_selection as selection
from rocell.application import physical_device_inventory as inventory
from rocell.application.wizard_inventory_fixture import rehearsal_device_inventory


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE = "a" * 64
SESSION = "wizard-native-arm-fixture"
_REAL_POPEN = subprocess.Popen


@pytest.fixture(autouse=True)
def no_host_access(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail(
            "No real native DLL, OS inventory, serial port or arbitrary process"
        )

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    from rocell.providers.windows import controller_metadata

    monkeypatch.setattr(
        controller_metadata, "inventory_serial_ports_with_pyserial", forbidden
    )


def generic_review(mode="rehearsal", scenario="nominal"):
    report = rehearsal_device_inventory(scenario)
    if mode == "physical":
        # Explicit physical-shaped records are still synthetic test inputs.
        old = metadata._batch(report["serial_inventory"])
        source = inventory.InventorySource.PYSERIAL_LIST_PORTS
        serial = replace(
            old,
            source=source,
            candidates=tuple(replace(v, source=source) for v in old.candidates),
        )
        report = inventory.compose_physical_device_inventory_report(
            platform_system="Windows",
            captured_at_unix_ns=1,
            camera_inventory=selection._batch(report["camera_inventory"]),
            serial_inventory=serial,
        ).to_dict()
    model = selection.WizardDeviceSelection(mode, SESSION, SOURCE)
    model.ingest(report, operation_id="operation-generic")
    return model.review(
        model.choices("SERIAL")[0]["value"], "SERIAL", "fixture-reviewer"
    )


def snapshot(scenario="nominal", mode="rehearsal"):
    value = metadata.rehearse_native_arm_metadata_snapshot(scenario)
    if mode == "physical":
        value["origin"] = "PHYSICAL_OBSERVATION"
        value["native_source"] = "WINDOWS_CM_METADATA"
        value["serial_inventory"]["source"] = "PYSERIAL_LIST_PORTS"
        for candidate in value["serial_inventory"]["candidates"]:
            candidate["source"] = "PYSERIAL_LIST_PORTS"
    return value


def correlate(value=None, review=None, mode="rehearsal", **kwargs):
    return metadata.correlate_native_arm_metadata(
        snapshot(mode=mode) if value is None else value,
        generic_review(mode) if review is None else review,
        mode=mode,
        session_id=kwargs.get("session_id", SESSION),
        source_sha256=kwargs.get("source_sha256", SOURCE),
        operation_id="operation-native",
    )


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
def test_exact_nominal_metadata_retained_and_summary_is_raw_free(mode):
    original, review = snapshot(mode=mode), generic_review(mode)
    value = correlate(original, review, mode)
    summary = metadata.summarize_native_arm_metadata(value)
    assert value["status"] == summary["status"] == "METADATA_CORRELATED"
    assert value["snapshot"] == original
    assert value["generic_review"] == review["review"]
    assert value["binding"]["generic_review_sha256"] == metadata._hash(review)
    assert (
        value["binding"]["generic_candidate_sha256"]
        == review["candidate"]["candidate_sha256"]
    )
    assert "inventory_report" not in value
    assert len(metadata._canonical(value)) < metadata.MAX_REPORT_BYTES
    assert len(metadata._canonical(summary)) < metadata.MAX_SUMMARY_BYTES
    assert all(v == "OBSERVED" for v in summary["native_fields"].values())
    assert summary["counts"] == {
        "serial_candidates": 1,
        "native_observations": 1,
        "generic_matches": 1,
        "native_matches": 1,
    }
    assert value["effects"] == {
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
    }
    for key in ("physical_authority", "connected", "qualified", "persistent_binding"):
        assert value[key] is summary[key] is False
    rendered = json.dumps(summary)
    assert "COM91" not in rendered and "SYNTHETIC-ARM-A" not in rendered
    assert "synthetic-not-installed.inf" not in rendered
    assert "arm_model_receipt_sha256" not in json.dumps(value)
    assert (
        original["native_observations"][0]["driver_service"]
        != original["serial_inventory"]["candidates"][0]["driver_service"]
    )


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("missing-fields", "NATIVE_REQUIRED_FIELD_MISSING"),
        ("duplicate-mapping", "NATIVE_MAPPING_AMBIGUOUS"),
        ("changed-device", "GENERIC_UNIT_NOT_PRESENT"),
        ("incomplete", "NATIVE_COLLECTION_INCOMPLETE"),
    ],
)
def test_closed_faults_hold_without_dropping_snapshot(scenario, expected):
    original = snapshot(scenario)
    value = correlate(original)
    assert value["status"] == "HELD" and expected in value["blockers"]
    assert value["snapshot"] == original
    assert metadata.summarize_native_arm_metadata(value)["status"] == "HELD"


@pytest.mark.parametrize(
    "field",
    [
        "persistent_instance_id",
        "port_name",
        "vid",
        "pid",
        "driver_provider",
        "driver_service",
        "driver_version",
        "driver_inf",
    ],
)
def test_missing_native_properties_not_filled_from_review(field):
    original = snapshot()
    original["native_observations"][0][field] = None
    value = correlate(original)
    assert value["status"] == "HELD"
    assert value["snapshot"]["native_observations"][0][field] is None
    assert value["native_fields"][field] in {"MISSING", "NOT_VERIFIED"}


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("port_name", "COM92"),
        ("vid", "1234"),
        ("pid", "5678"),
    ],
)
def test_no_usb_or_com_only_fallback(field, replacement):
    original = snapshot()
    original["native_observations"][0][field] = replacement
    value = correlate(original)
    assert value["status"] == "HELD"
    assert "NATIVE_MAPPING_NOT_PRESENT" in value["blockers"]


@pytest.mark.parametrize(
    "duplicate", ["port_name", "persistent_port_path", "persistent_instance_id"]
)
def test_nonmatching_alias_row_still_blocks_duplicate_native_identity(duplicate):
    value = snapshot()
    row = deepcopy(value["native_observations"][0])
    row.update(
        port_name="COM92",
        vid="1234",
        pid="5678",
        persistent_port_path=row["persistent_port_path"] + "-OTHER",
        persistent_instance_id="USB\\OTHER",
    )
    row[duplicate] = value["native_observations"][0][duplicate]
    value["native_observations"].append(row)
    result = correlate(value)
    assert result["status"] == "HELD"
    expected = {
        "port_name": "NATIVE_PORT_AMBIGUOUS",
        "persistent_port_path": "NATIVE_PERSISTENT_PATH_AMBIGUOUS",
        "persistent_instance_id": "NATIVE_INSTANCE_AMBIGUOUS",
    }[duplicate]
    assert expected in result["blockers"]


def test_generic_candidate_change_is_not_hidden_by_same_usb_serial():
    value = snapshot()
    value["serial_inventory"]["candidates"][0][
        "driver_service"
    ] = "CHANGED generic label"
    result = correlate(value)
    assert (
        result["status"] == "HELD" and "GENERIC_CANDIDATE_CHANGED" in result["blockers"]
    )


def test_generic_duplicate_and_blocked_original_review_are_distinct_holds():
    value = snapshot()
    value["serial_inventory"]["candidates"].append(
        deepcopy(value["serial_inventory"]["candidates"][0])
    )
    result = correlate(value)
    assert {"GENERIC_UNIT_AMBIGUOUS", "GENERIC_PORT_AMBIGUOUS"} <= set(
        result["blockers"]
    )
    result = correlate(review=generic_review(scenario="duplicate-identity"))
    assert "GENERIC_REVIEW_BLOCKED" in result["blockers"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda v: v.update(unrecognized=True),
        lambda v: v.update(physical_authority=0),
        lambda v: v.update(physical_authority=True),
        lambda v: v.update(started_monotonic_ns=True),
        lambda v: v.update(started_monotonic_ns=3),
        lambda v: v.update(finished_monotonic_ns=2**63),
        lambda v: v["native_observations"][0].update(extra="field"),
        lambda v: v["native_observations"][0].update(vid="FFFE"),
        lambda v: v["native_observations"][0].update(driver_service=" whitespace "),
        lambda v: v["serial_inventory"].update(collection_complete=1),
        lambda v: v["serial_inventory"]["boundary"].update(device_ports_opened=True),
        lambda v: v["serial_inventory"]["candidates"][0].update(qualified=True),
        lambda v: v["serial_inventory"]["candidates"][0]["usb_identity"].update(
            vid=65534
        ),
    ],
)
def test_snapshot_rejects_noncanonical_unknown_or_effect_fields(mutate):
    value = snapshot()
    mutate(value)
    with pytest.raises(metadata.NativeArmMetadataError):
        metadata.decode_controller_snapshot(value, "rehearsal")


@pytest.mark.parametrize("mode", ["physical", "rehearsal"])
def test_provenance_cannot_be_switched_by_requested_mode(mode):
    other = "physical" if mode == "rehearsal" else "rehearsal"
    with pytest.raises(metadata.NativeArmMetadataError):
        metadata.decode_controller_snapshot(snapshot(mode=other), mode)


def test_snapshot_bytes_unique_keys_and_detached_ownership():
    value = snapshot()
    raw = metadata._canonical(value)
    first = metadata.decode_controller_snapshot(raw, "rehearsal")
    assert first.payload() == raw
    value["native_observations"][0]["driver_service"] = "MUTATED"
    assert (
        json.loads(first.payload())["native_observations"][0]["driver_service"]
        != "MUTATED"
    )
    with pytest.raises(metadata.NativeArmMetadataError):
        metadata.decode_controller_snapshot(
            raw[:-1] + b',"physical_authority":false}', "rehearsal"
        )


@pytest.mark.parametrize("elapsed_ns", [10_000_000_000, 10_000_000_001])
def test_new_diagnostic_snapshot_cannot_overrun_original_collection_bound(elapsed_ns):
    value = snapshot()
    value["finished_monotonic_ns"] = value["started_monotonic_ns"] + elapsed_ns
    with pytest.raises(metadata.NativeArmMetadataError, match="DURATION_EXCEEDED"):
        metadata.decode_controller_snapshot(value, "rehearsal")


def test_missing_original_generic_identity_remains_held_even_if_summary_blocker_removed():
    review = generic_review(scenario="missing-identity")
    value = snapshot()
    value["serial_inventory"]["candidates"][0] = review["candidate_record"]
    report = correlate(value, review)
    assert report["status"] == "HELD"
    report["reviewed_candidate_blockers"] = []
    report["blockers"] = []
    report["status"] = "METADATA_CORRELATED"
    report["report_sha256"] = metadata._hash(
        {k: v for k, v in report.items() if k != "report_sha256"}
    )
    with pytest.raises(metadata.NativeArmMetadataError):
        metadata.summarize_native_arm_metadata(report)


@pytest.mark.parametrize(
    "value",
    [float("nan"), {"nested": "x" * 2049}, b"x" * (2 * 1024 * 1024 + 1)],
    ids=["nonfinite", "oversized-string", "oversized-payload"],
)
def test_oversized_and_non_json_payloads_refused(value):
    with pytest.raises(metadata.NativeArmMetadataError):
        metadata.decode_controller_snapshot(value, "rehearsal")


def test_cyclic_input_refused_before_encoding():
    value = snapshot()
    value["cycle"] = value
    with pytest.raises(metadata.NativeArmMetadataError):
        metadata.decode_controller_snapshot(value, "rehearsal")


@pytest.mark.parametrize(
    "kind", ["source", "session", "review", "candidate", "report", "physical"]
)
def test_exact_generic_review_binding_cannot_drift(kind):
    review = generic_review()
    kwargs = {}
    if kind == "source":
        kwargs["source_sha256"] = "b" * 64
    elif kind == "session":
        kwargs["session_id"] = "wizard-other"
    elif kind == "review":
        review["review"]["status"] = "CONNECTED"
    elif kind == "candidate":
        review["candidate_record"]["usb_identity"]["unit_serial"] = "OTHER"
    elif kind == "report":
        review["report_sha256"] = "b" * 64
    else:
        review["physical_authority"] = True
    with pytest.raises(metadata.NativeArmMetadataError):
        correlate(review=review, **kwargs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "METADATA_CORRELATED"),
        ("blockers", []),
        ("physical_authority", 0),
        ("connected", True),
        ("native_observation_sha256", "b" * 64),
        ("unexpected", False),
    ],
)
def test_summary_recomputes_held_report_even_after_selfhash_edit(field, value):
    report = correlate(snapshot("missing-fields"))
    report[field] = value
    report["report_sha256"] = metadata._hash(
        {k: v for k, v in report.items() if k != "report_sha256"}
    )
    with pytest.raises(metadata.NativeArmMetadataError):
        metadata.summarize_native_arm_metadata(report)


def test_report_and_summary_are_detached():
    review, snap = generic_review(), snapshot()
    report = correlate(snap, review)
    summary = metadata.summarize_native_arm_metadata(report)
    review["review"]["reviewer_id"] = "MUTATED"
    snap["native_observations"].clear()
    summary["counts"]["native_matches"] = 0
    assert report["generic_review"]["reviewer_id"] == "fixture-reviewer"
    assert len(report["snapshot"]["native_observations"]) == 1
    assert (
        metadata.summarize_native_arm_metadata(report)["counts"]["native_matches"] == 1
    )


def test_full_snapshot_allowed_but_correlation_refuses_export_overbudget():
    value = snapshot()
    base = value["native_observations"][0]
    # Native strings remain valid <=512 UTF8; ASCII JSON escaping makes this
    # strict existing snapshot large enough to exceed the separate export cap.
    rows = []
    for index in range(128):
        row = deepcopy(base)
        for field in (
            "driver_provider",
            "driver_service",
            "driver_version",
            "driver_inf",
        ):
            row[field] = "\u00e9" * 256
        row["persistent_instance_id"] = "USB\\" + "\u00e9" * 200 + str(index)
        rows.append(row)
    value["native_observations"] = rows
    decoded = metadata.decode_controller_snapshot(value, "rehearsal")
    assert len(decoded.payload()) < metadata.MAX_SNAPSHOT_BYTES
    with pytest.raises(metadata.NativeArmMetadataError, match="BYTE_LIMIT"):
        correlate(decoded)


@pytest.mark.parametrize("scenario", sorted(metadata.SCENARIOS))
def test_worker_rehearsal_branch_uses_actual_fixture_without_native_import(
    scenario, monkeypatch
):
    from rocell.application.wizard_worker import run
    from rocell.providers.windows import controller_metadata

    monkeypatch.setattr(
        controller_metadata,
        "WindowsControllerMetadataAcquirer",
        lambda **kw: pytest.fail("fixture attempted live collector"),
    )
    result = run(
        WORKSPACE,
        "rehearse_native_arm_metadata",
        {"scenario": scenario, "metadata_only": True},
        "test-cell",
    )
    assert result["status"] == "SUCCEEDED"  # Collection success, not correlation.
    assert result["metadata_inventory_performed"] is False
    assert result["steps"][0]["name"] == "native_arm_metadata_snapshot"
    metadata.decode_controller_snapshot(result["steps"][0]["report"], "rehearsal")


def test_physical_worker_branch_uses_exact_collector_contract_only_when_explicit(
    monkeypatch,
):
    from rocell.application import wizard_worker
    from rocell.providers.windows import controller_metadata

    calls = []
    shaped = metadata.decode_controller_snapshot(snapshot(mode="physical"), "physical")

    class ExplicitlyIncapableCollector:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def __call__(self):
            return shaped

    monkeypatch.setattr(
        controller_metadata,
        "WindowsControllerMetadataAcquirer",
        ExplicitlyIncapableCollector,
    )
    monkeypatch.setattr(wizard_worker.platform, "system", lambda: "Windows")
    monkeypatch.setattr(wizard_worker.time, "monotonic_ns", lambda: 123)
    values = {"power_disconnected": True, "metadata_only": True}
    result = wizard_worker.run(
        WORKSPACE, "inspect_native_arm_metadata", values, "test-cell"
    )
    assert len(calls) == 1 and calls[0]["deadline_ns"] == 10_000_000_123
    assert type(calls[0]["cancellation"]) is Event
    assert result["metadata_inventory_performed"] is True
    assert result["device_open_count"] == result["serial_write_count"] == 0
    assert result["physical_authority"] is False


def test_false_consent_never_constructs_collector(monkeypatch):
    from rocell.application import wizard_worker
    from rocell.providers.windows import controller_metadata

    monkeypatch.setattr(
        controller_metadata,
        "WindowsControllerMetadataAcquirer",
        lambda **kw: pytest.fail("denied action constructed collector"),
    )
    with pytest.raises(ValueError):
        wizard_worker.run(
            WORKSPACE,
            "inspect_native_arm_metadata",
            {"power_disconnected": False, "metadata_only": True},
            "test-cell",
        )
