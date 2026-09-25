from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from rocell.application import physical_device_inventory as inventory
from rocell.application import rehearsal_arm_identity_stage as stage
from rocell.arm import connection


WORKSPACE = Path(__file__).resolve().parents[3]


def binding() -> stage.RehearsalArmIdentityBinding:
    return stage.RehearsalArmIdentityBinding(
        "a" * 64,
        "b" * 64,
        "cell-fixture",
        "session-fixture",
        "operator-fixture",
        "c" * 64,
        "d" * 64,
        "e" * 64,
        "f" * 64,
    )


def encoded(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def digest(value: object) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def verify(
    document: dict[str, Any], **kwargs: Any
) -> stage.RehearsalArmIdentityEvidence:
    return stage.verify_rehearsal_arm_identity_evidence(
        encoded(document), expected_binding=binding(), **kwargs
    )


def reseal(document: dict[str, Any]) -> dict[str, Any]:
    """Rehash reports without rederiving checks: consistency must still detect edits."""
    document["report_hashes"] = {
        key: digest(value) for key, value in document["reports"].items()
    }
    return document


@pytest.fixture(scope="module")
def retained() -> stage.RehearsalArmIdentityEvidence:
    return stage.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding())


def test_actual_profile_and_injected_inventory_round_trip(retained):
    document = retained.to_dict()
    assert retained.outcome == "REHEARSAL_CHECKS_PASSED"
    assert document["nominal_outcome"] == "NOMINAL_CHECKS_PASSED"
    assert document["negative_checks_outcome"] == "EXPECTED_FAULTS_REJECTED"
    assert 20_000 < len(retained.canonical_bytes()) < stage.MAX_EVIDENCE_BYTES
    assert len(retained.checks) == 12
    assert all(row["passed"] is True for row in retained.checks)
    assert {row["check_kind"] for row in retained.checks} == {
        "NOMINAL",
        "EXPECTED_FAULT",
        "INVARIANT",
    }
    assert all(
        set(row) == {"check_id", "check_kind", "passed", "observed", "meaning"}
        for row in retained.checks
    )
    assert (
        verify(
            document,
            expected_evidence_sha256=retained.evidence_sha256,
            expected_evaluator_source_sha256=document["evaluator"][
                "source_file_sha256"
            ],
        ).canonical_bytes()
        == retained.canonical_bytes()
    )
    assert document["selected_inputs_sha256"] == digest(document["selected_inputs"])


def test_full_substantive_reports_and_no_firmware_inference(retained):
    document = retained.to_dict()
    profile = document["reports"]["profile"]
    assert profile["loaded_profile"]["baudrate"] == 115200
    assert profile["loaded_profile"]["commissioned"] is False
    assert profile["loaded_profile"]["identity"]["firmware_revision"] is None
    assert (
        profile["profile_file_sha256"]
        == hashlib.sha256(profile["profile_utf8"].encode()).hexdigest()
    )
    nominal = document["reports"]["scenarios"]["nominal"]
    raw = nominal["specification"]["injected_payload"][0]
    report = nominal["inventory_report"]
    candidate = report["serial_inventory"]["candidates"][0]
    assert raw["location"] == "INCAPABLE-USB-ROOT.PORT-1"
    assert candidate["driver_service"] == raw["interface"]
    assert candidate["persistent_ids"] == ["usb-unit:1234:5678:INCAPABLE-ARM-001"]
    assert candidate["selection_performed"] is False
    assert candidate["qualified"] is False
    assert report["captured_at_unix_ns"] == 0
    assert report["authority"]["arm_qualified"] is False
    assert "ROARM_IDENTITY_REQUIRES_SEPARATE_EVIDENCE" in report["blockers"]
    for key in (
        "received_pro_arm_identity",
        "firmware_identity",
        "boot_reset_behavior",
        "driver_identity_and_version",
    ):
        assert document["provenance"][key] == "PHYSICAL_EVIDENCE_PENDING"
    assert document["authority"]["serial_bytes_written"] == 0
    assert document["authority"]["physical_release_effect"] == "NONE"
    assert all(
        value is False
        for key, value in document["authority"].items()
        if key not in {"composition", "physical_release_effect", "serial_bytes_written"}
    )


def test_calls_real_apis_only_with_closed_fixtures(monkeypatch):
    calls = {"load": 0, "inventory": 0, "compose": 0}
    actual_load = connection.load_arm_connection_profile
    actual_inventory = inventory.inventory_serial_ports_from_provider
    actual_compose = inventory.compose_physical_device_inventory_report

    def forbidden(*args, **kwargs):
        raise AssertionError("hardware or host enumeration attempted")

    def load(root):
        calls["load"] += 1
        return actual_load(root)

    def injected(provider):
        calls["inventory"] += 1
        assert type(provider) is stage._ClosedEnumerator
        assert len(provider.enumerate_serial_ports()) <= 2
        return actual_inventory(provider)

    def compose(**kwargs):
        calls["compose"] += 1
        return actual_compose(**kwargs)

    monkeypatch.setattr(connection, "load_arm_connection_profile", load)
    monkeypatch.setattr(inventory, "inventory_serial_ports_from_provider", injected)
    monkeypatch.setattr(inventory, "compose_physical_device_inventory_report", compose)
    for name in (
        "inventory_serial_ports_with_pyserial",
        "inventory_windows_pnp_cameras",
        "inventory_linux_video_cameras_from_sysfs",
    ):
        monkeypatch.setattr(inventory, name, forbidden)
    assert (
        stage.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding()).outcome
        == "REHEARSAL_CHECKS_PASSED"
    )
    assert calls == {"load": 1, "inventory": 10, "compose": 9}


def test_verifier_never_replays_or_reads_files(retained, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("retained verification performed external work")

    monkeypatch.setattr(stage, "evaluate_rehearsal_arm_identity_stage", forbidden)
    monkeypatch.setattr(connection, "load_arm_connection_profile", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_from_provider", forbidden)
    monkeypatch.setattr(
        inventory, "compose_physical_device_inventory_report", forbidden
    )
    monkeypatch.setattr(stage._ClosedEnumerator, "enumerate_serial_ports", forbidden)
    for name in ("open", "read_bytes", "read_text", "stat", "lstat", "resolve"):
        monkeypatch.setattr(Path, name, forbidden)
    assert (
        stage.verify_rehearsal_arm_identity_evidence(
            retained.canonical_bytes(),
            expected_binding=binding(),
            expected_evidence_sha256=retained.evidence_sha256,
            expected_evaluator_source_sha256=retained.to_dict()["evaluator"][
                "source_file_sha256"
            ],
        ).outcome
        == "REHEARSAL_CHECKS_PASSED"
    )


def test_regressed_nominal_does_not_hide_behind_passing_negative_checks(monkeypatch):
    actual = inventory.inventory_serial_ports_from_provider
    count = 0

    def changed(provider):
        nonlocal count
        count += 1
        batch = actual(provider)
        if count == 1:
            return replace(
                batch, candidates=(replace(batch.candidates[0], product="REGRESSED"),)
            )
        return batch

    monkeypatch.setattr(inventory, "inventory_serial_ports_from_provider", changed)
    result = stage.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding())
    assert result.outcome == "BLOCKED"
    assert result.to_dict()["nominal_outcome"] == "BLOCKED"
    assert result.to_dict()["negative_checks_outcome"] == "EXPECTED_FAULTS_REJECTED"
    assert (
        next(row for row in result.checks if row["check_id"] == "nominal_inventory")[
            "passed"
        ]
        is False
    )


def test_regressed_negative_alias_check_blocks_overall(monkeypatch):
    actual = inventory.inventory_serial_ports_from_provider

    def changed(provider):
        rows = provider.enumerate_serial_ports()
        if (
            rows
            and type(rows[0]) is inventory.RawSerialPortObservation
            and rows[0].port_name == "COM44"
        ):
            return actual(stage._ClosedEnumerator(stage._scenarios()["nominal"]))
        return actual(provider)

    monkeypatch.setattr(inventory, "inventory_serial_ports_from_provider", changed)
    result = stage.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding())
    assert result.outcome == "BLOCKED"
    assert result.to_dict()["nominal_outcome"] == "NOMINAL_CHECKS_PASSED"
    assert result.to_dict()["negative_checks_outcome"] == "BLOCKED"


def test_generic_rejection_does_not_count_as_all_expected_faults(monkeypatch):
    def rejected(provider):
        raise inventory.PhysicalDeviceInventoryError("INCAPABLE regression")

    monkeypatch.setattr(inventory, "inventory_serial_ports_from_provider", rejected)
    result = stage.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding())
    assert result.outcome == "BLOCKED"
    passed = {row["check_id"]: row["passed"] for row in result.checks}
    assert passed["reject_unexpected_output"] is True
    assert passed["nominal_inventory"] is False
    assert passed["reject_wrong_model"] is False


def test_regressed_composer_blockers_stop_nominal(monkeypatch):
    actual = inventory.compose_physical_device_inventory_report

    def changed(**kwargs):
        return replace(
            actual(**kwargs), blockers=("INVENTORY_ONLY_NOT_DEVICE_QUALIFICATION",)
        )

    monkeypatch.setattr(inventory, "compose_physical_device_inventory_report", changed)
    result = stage.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding())
    assert result.outcome == "BLOCKED"
    assert result.to_dict()["nominal_outcome"] == "BLOCKED"


def test_negative_report_must_still_match_its_raw_fixture(monkeypatch):
    actual = inventory.inventory_serial_ports_from_provider

    def changed(provider):
        batch = actual(provider)
        if batch.candidates and batch.candidates[0].unit_serial is None:
            return replace(
                batch, candidates=(replace(batch.candidates[0], product="UNEXPECTED"),)
            )
        return batch

    monkeypatch.setattr(inventory, "inventory_serial_ports_from_provider", changed)
    result = stage.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding())
    assert result.to_dict()["nominal_outcome"] == "NOMINAL_CHECKS_PASSED"
    assert result.to_dict()["negative_checks_outcome"] == "BLOCKED"
    check = next(
        row for row in result.checks if row["check_id"] == "reject_missing_unit_serial"
    )
    assert "PERSISTENT_IDENTITY_INCOMPLETE" in check["observed"]["reason_codes"]
    assert check["observed"]["inventory_consistent"] is False
    assert check["passed"] is False


@pytest.mark.parametrize("field", ["vid", "pid"])
@pytest.mark.parametrize("value", [None, 1234, True])
def test_fixture_oracle_rejects_nonstring_observed_usb_ids(monkeypatch, field, value):
    specification = stage._scenarios()["nominal"]
    raw = inventory.RawSerialPortObservation(**specification["injected_payload"][0])
    # Inject a typed-provider regression after its usual normalization. The
    # independent oracle must reject, not normalize or infer a replacement.
    object.__setattr__(raw, field, value)
    monkeypatch.setattr(stage, "RawSerialPortObservation", lambda **fields: raw)
    with pytest.raises(
        stage.RehearsalArmIdentityError, match="VID/PID must be strings"
    ):
        stage._fixture_candidates(specification)


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "Waveshare RoArm-M3 S"),
        ("baud", 9600),
        ("rts", True),
        ("dtr", True),
        ("blind_retry", True),
        ("auto_initialize", True),
        ("auto_connect", True),
        ("port", "COM9"),
        ("unknown_future_option", True),
        ("schema_version", True),
    ],
)
def test_changed_profile_is_blocked_by_actual_loader_or_nominal_policy(
    tmp_path, field, value
):
    raw = json.loads((WORKSPACE / stage._PROFILE).read_bytes())
    raw[field] = value
    path = tmp_path / stage._PROFILE
    path.parent.mkdir(parents=True)
    path.write_bytes(encoded(raw))
    result = stage.evaluate_rehearsal_arm_identity_stage(tmp_path, binding())
    assert result.outcome == "BLOCKED"
    assert result.to_dict()["nominal_outcome"] == "BLOCKED"
    assert result.to_dict()["negative_checks_outcome"] == "EXPECTED_FAULTS_REJECTED"
    assert (
        next(row for row in result.checks if row["check_id"] == "profile_policy")[
            "passed"
        ]
        is False
    )
    if field == "model":
        assert result.to_dict()["reports"]["profile"]["loader_outcome"] == "REJECTED"


def test_qualified_profile_cannot_be_promoted_by_rehearsal(tmp_path):
    raw = json.loads((WORKSPACE / stage._PROFILE).read_bytes())
    raw["port"] = "COM9"
    raw["identity"] = {
        "controller_usb_identity": "usb-fixture",
        "arm_serial_number": "unit-fixture",
        "firmware_revision": "fixture-revision",
        "state": "QUALIFIED",
    }
    path = tmp_path / stage._PROFILE
    path.parent.mkdir(parents=True)
    path.write_bytes(encoded(raw))
    result = stage.evaluate_rehearsal_arm_identity_stage(tmp_path, binding())
    assert result.outcome == "BLOCKED"
    assert result.to_dict()["authority"]["arm_identity_qualified"] is False


@pytest.mark.parametrize("field", list(asdict(binding())))
def test_all_binding_fields_exactly_bound(retained, field):
    updated = (
        "changed-identity"
        if field in {"cell_id", "session_id", "operator_id"}
        else "0" * 64
    )
    if field == "stage":
        document = retained.to_dict()
        document["binding"]["stage"] = "power_safety"
        with pytest.raises(stage.RehearsalArmIdentityError):
            verify(document)
        return
    with pytest.raises(stage.RehearsalArmIdentityError):
        stage.verify_rehearsal_arm_identity_evidence(
            retained.canonical_bytes(),
            expected_binding=replace(binding(), **{field: updated}),
        )


@pytest.mark.parametrize(
    "field",
    [
        "workspace_source_sha256",
        "catalog_sha256",
        "predecessor_receipt_sha256",
        "predecessor_assessment_sha256",
        "predecessor_review_sha256",
        "static_registration_evidence_sha256",
    ],
)
@pytest.mark.parametrize("invalid", [True, "A" * 64, "a" * 63])
def test_digest_binding_validation(field, invalid):
    with pytest.raises(stage.RehearsalArmIdentityError):
        replace(binding(), **{field: invalid})


@pytest.mark.parametrize(
    "location",
    [
        "schema",
        "authority",
        "provenance",
        "binding",
        "evaluator",
        "selected_inputs",
        "checks",
        "report",
        "candidate",
        "profile",
    ],
)
def test_strict_schema_rejects_unknowns_and_changes_even_if_report_rehashed(
    retained, location
):
    document = retained.to_dict()
    if location == "schema":
        document["schema"] = "rocell.rehearsal_arm_identity_stage.v2"
    elif location in {
        "authority",
        "provenance",
        "binding",
        "evaluator",
        "selected_inputs",
    }:
        document[location]["unknown"] = True
    elif location == "checks":
        document["checks"][0]["extra"] = "unknown"
    elif location == "report":
        document["reports"]["scenarios"]["nominal"]["unknown"] = True
    elif location == "candidate":
        report = document["reports"]["scenarios"]["nominal"]["inventory_report"]
        report["serial_inventory"]["candidates"][0]["unknown"] = True
        report["report_sha256"] = digest(
            {key: value for key, value in report.items() if key != "report_sha256"}
        )
    else:
        document["reports"]["profile"]["loaded_profile"]["unknown"] = True
    with pytest.raises(stage.RehearsalArmIdentityError):
        verify(reseal(document))


@pytest.mark.parametrize(
    "path,value",
    [
        (("authority", "physical_authority"), 0),
        (("authority", "serial_bytes_written"), False),
        (("authority", "stage_advance_authority"), True),
        (("checks", 0, "passed"), 1),
        (("checks", 0, "check_kind"), "EXPECTED_FAULT"),
        (("nominal_outcome",), "BLOCKED"),
        (("negative_checks_outcome",), "BLOCKED"),
        (("outcome",), "QUALIFIED"),
        (
            (
                "reports",
                "scenarios",
                "nominal",
                "inventory_report",
                "captured_at_unix_ns",
            ),
            False,
        ),
        (
            (
                "reports",
                "scenarios",
                "nominal",
                "inventory_report",
                "authority",
                "serial_port_opened",
            ),
            0,
        ),
    ],
)
def test_no_boolean_coercion_or_summary_substitution(retained, path, value):
    document = retained.to_dict()
    selected = document
    for component in path[:-1]:
        selected = selected[component]
    selected[path[-1]] = value
    with pytest.raises(stage.RehearsalArmIdentityError):
        verify(reseal(document))


def test_closed_fixture_input_cannot_be_replaced(retained):
    document = retained.to_dict()
    document["reports"]["scenarios"]["nominal"]["specification"]["injected_payload"][0][
        "port_name"
    ] = "COM1"
    with pytest.raises(stage.RehearsalArmIdentityError):
        verify(reseal(document))


def test_trusted_hashes_reject_resealing(retained):
    document = retained.to_dict()
    document["evaluator"]["source_file_sha256"] = "0" * 64
    # Without a trusted hash this merely passes consistency, never admission.
    assert verify(document).outcome == "REHEARSAL_CHECKS_PASSED"
    with pytest.raises(stage.RehearsalArmIdentityError):
        verify(document, expected_evidence_sha256=retained.evidence_sha256)
    with pytest.raises(stage.RehearsalArmIdentityError):
        verify(
            document,
            expected_evaluator_source_sha256=retained.to_dict()["evaluator"][
                "source_file_sha256"
            ],
        )


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"[]",
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b"\xff",
        b" " * (stage.MAX_EVIDENCE_BYTES + 1),
        b'{"a":' + b"[" * 30 + b"0" + b"]" * 30 + b"}",
        encoded({"a": [0] * 65}),
        encoded({"a": 1 << 64}),
    ],
    ids=[
        "empty",
        "array",
        "duplicate",
        "nan",
        "infinity",
        "utf8",
        "oversized",
        "deep",
        "wide",
        "integer",
    ],
)
def test_bounded_strict_json(payload):
    with pytest.raises(stage.RehearsalArmIdentityError):
        stage.verify_rehearsal_arm_identity_evidence(
            payload, expected_binding=binding()
        )


def test_immutable_retained_value(retained):
    before = retained.canonical_bytes()
    document = retained.to_dict()
    document["checks"][0]["passed"] = False
    retained.checks[0]["passed"] = False
    assert retained.canonical_bytes() == before
    assert retained.checks[0]["passed"] is True


def test_profile_change_during_evaluation_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / stage._PROFILE
    path.parent.mkdir(parents=True)
    path.write_bytes((WORKSPACE / stage._PROFILE).read_bytes())
    actual = connection.load_arm_connection_profile

    def changed(root):
        profile = actual(root)
        path.write_bytes(path.read_bytes() + b" ")
        return profile

    monkeypatch.setattr(connection, "load_arm_connection_profile", changed)
    with pytest.raises(stage.RehearsalArmIdentityError, match="changed during"):
        stage.evaluate_rehearsal_arm_identity_stage(tmp_path, binding())


def test_source_change_during_evaluation_fails_closed(monkeypatch):
    actual = stage._read_fixed
    count = 0

    def changed(root, relative):
        nonlocal count
        raw = actual(root, relative)
        if relative.endswith("rehearsal_arm_identity_stage.py"):
            count += 1
            if count == 2:
                return raw + b"# synthetic source race"
        return raw

    monkeypatch.setattr(stage, "_read_fixed", changed)
    with pytest.raises(stage.RehearsalArmIdentityError, match="source changed"):
        stage.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding())


def test_oversized_or_malformed_fixed_input_rejected_before_loader(
    tmp_path, monkeypatch
):
    path = tmp_path / stage._PROFILE
    path.parent.mkdir(parents=True)
    path.write_bytes(b" " * (stage.MAX_EVIDENCE_BYTES + 1))
    monkeypatch.setattr(
        connection,
        "load_arm_connection_profile",
        lambda root: pytest.fail("loader should not run"),
    )
    with pytest.raises(stage.RehearsalArmIdentityError):
        stage.evaluate_rehearsal_arm_identity_stage(tmp_path, binding())
    path.write_bytes(b'{"schema_version":1,"schema_version":1}')
    with pytest.raises(stage.RehearsalArmIdentityError):
        stage.evaluate_rehearsal_arm_identity_stage(tmp_path, binding())
