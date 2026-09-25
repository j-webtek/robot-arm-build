from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import shutil

import pytest

from rocell.safety.effects import (
    AUTHORITY_EFFECT_POLICY_SCHEMA,
    DEFAULT_AUTHORITY_EFFECT_POLICY,
    EXPECTED_EFFECT_CLASS_ORDER,
    AuthorityEffectPolicyError,
    EffectCertainty,
    EffectClass,
    load_authority_effect_policy,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def _copy_policy(destination: Path) -> Path:
    target = destination / DEFAULT_AUTHORITY_EFFECT_POLICY
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WORKSPACE / DEFAULT_AUTHORITY_EFFECT_POLICY, target)
    return target


def _document(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write(path: Path, document: object) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


def test_default_policy_is_immutable_stage_agnostic_and_zero_authority() -> None:
    policy = load_authority_effect_policy(WORKSPACE)

    assert policy.schema == AUTHORITY_EFFECT_POLICY_SCHEMA
    assert policy.scope == "STAGE_AGNOSTIC_DESIGN_ONLY"
    assert policy.runtime_activation is False
    assert policy.authority.is_zero_authority
    assert policy.authority.to_dict() == {
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "device_io_authorized": False,
        "robot_power_authorized": False,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "build_promotion_authorized": False,
        "physical_release_effect": "NONE",
    }
    assert policy.source_relative_path == DEFAULT_AUTHORITY_EFFECT_POLICY.as_posix()
    assert len(policy.source_sha256) == 64
    assert tuple(rule.effect_class for rule in policy.effect_classes) == (
        EXPECTED_EFFECT_CLASS_ORDER
    )
    assert "stage_contracts" not in policy.to_dict()
    with pytest.raises(FrozenInstanceError):
        policy.runtime_activation = True  # type: ignore[misc]


def test_effect_certainty_matches_fail_closed_receipt_semantics() -> None:
    certainty = load_authority_effect_policy(WORKSPACE).effect_certainty

    assert certainty.values == (
        EffectCertainty.CONFIRMED,
        EffectCertainty.UNCERTAIN,
    )
    assert certainty.uncertain_requires_manual_reconciliation is True
    assert certainty.automatic_retry_after_uncertain_effect is False


def test_exact_effect_class_risk_properties_are_locked() -> None:
    policy = load_authority_effect_policy(WORKSPACE)
    expected = {
        EffectClass.NO_DEVICE_IO: (False, False, False, False),
        EffectClass.READ_ONLY_OS_INVENTORY: (False, False, False, False),
        EffectClass.BOUNDED_CAMERA_CAMPAIGN: (True, True, True, False),
        EffectClass.MANUAL_ENERGY_CHANGE: (False, True, True, False),
        EffectClass.MANUAL_POSSIBLE_MOTION: (False, True, True, False),
        EffectClass.SERIAL_OPEN_OR_WRITE: (True, True, True, False),
        EffectClass.NONCONTACT_ARM_MOTION_EXTERNAL: (True, True, True, False),
    }

    assert set(expected) == set(EffectClass)
    for effect_class, properties in expected.items():
        rule = policy.rule_for(effect_class)
        assert (
            rule.device_open_allowed,
            rule.external_physical_effect_possible,
            rule.durable_attempt_required,
            rule.automatic_retry_allowed,
        ) == properties


@pytest.mark.parametrize(
    ("field", "unsafe"),
    [
        ("hardware_accessed", True),
        ("hardware_commands_generated", 1),
        ("device_io_authorized", True),
        ("robot_power_authorized", True),
        ("live_motion_authorized", True),
        ("physical_contact_authorized", True),
        ("build_promotion_authorized", True),
        ("physical_release_effect", "PROMOTE"),
    ],
)
def test_policy_rejects_every_authority_escalation(
    tmp_path: Path, field: str, unsafe: object
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    path = _copy_policy(workspace)
    document = _document(path)
    authority = document["authority"]
    assert isinstance(authority, dict)
    authority[field] = unsafe
    _write(path, document)

    with pytest.raises(AuthorityEffectPolicyError, match="zero authority"):
        load_authority_effect_policy(workspace)


def test_policy_rejects_runtime_activation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    path = _copy_policy(workspace)
    document = _document(path)
    document["runtime_activation"] = True
    _write(path, document)

    with pytest.raises(AuthorityEffectPolicyError, match="activation"):
        load_authority_effect_policy(workspace)


@pytest.mark.parametrize(
    ("effect_class", "field", "unsafe"),
    [
        (EffectClass.NO_DEVICE_IO, "device_open_allowed", True),
        (
            EffectClass.READ_ONLY_OS_INVENTORY,
            "external_physical_effect_possible",
            True,
        ),
        (EffectClass.BOUNDED_CAMERA_CAMPAIGN, "durable_attempt_required", False),
        (EffectClass.MANUAL_ENERGY_CHANGE, "external_physical_effect_possible", False),
        (EffectClass.MANUAL_POSSIBLE_MOTION, "durable_attempt_required", False),
        (EffectClass.SERIAL_OPEN_OR_WRITE, "automatic_retry_allowed", True),
        (
            EffectClass.NONCONTACT_ARM_MOTION_EXTERNAL,
            "device_open_allowed",
            False,
        ),
    ],
)
def test_policy_rejects_changed_risk_properties(
    tmp_path: Path,
    effect_class: EffectClass,
    field: str,
    unsafe: object,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    path = _copy_policy(workspace)
    document = _document(path)
    rules = document["effect_classes"]
    assert isinstance(rules, list)
    rule = next(item for item in rules if item["id"] == effect_class.value)
    rule[field] = unsafe
    _write(path, document)

    with pytest.raises(AuthorityEffectPolicyError):
        load_authority_effect_policy(workspace)


def test_policy_rejects_duplicate_missing_and_unknown_classes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    path = _copy_policy(workspace)
    document = _document(path)
    rules = document["effect_classes"]
    assert isinstance(rules, list)
    rules[-1] = dict(rules[0])
    _write(path, document)

    with pytest.raises(AuthorityEffectPolicyError, match="risk properties"):
        load_authority_effect_policy(workspace)

    document = _document(WORKSPACE / DEFAULT_AUTHORITY_EFFECT_POLICY)
    rules = document["effect_classes"]
    assert isinstance(rules, list)
    rules[0]["id"] = "SURPRISE"
    _write(path, document)
    with pytest.raises(AuthorityEffectPolicyError, match="unsupported"):
        load_authority_effect_policy(workspace)


@pytest.mark.parametrize("location", ["top", "authority", "class", "certainty"])
def test_policy_rejects_unknown_fields(tmp_path: Path, location: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    path = _copy_policy(workspace)
    document = _document(path)
    if location == "top":
        document["stage_contracts"] = []
    elif location == "authority":
        authority = document["authority"]
        assert isinstance(authority, dict)
        authority["surprise"] = False
    elif location == "class":
        rules = document["effect_classes"]
        assert isinstance(rules, list)
        rules[0]["surprise"] = False
    else:
        certainty = document["effect_certainty"]
        assert isinstance(certainty, dict)
        certainty["surprise"] = False
    _write(path, document)

    with pytest.raises(AuthorityEffectPolicyError, match="fields differ"):
        load_authority_effect_policy(workspace)


def test_policy_rejects_duplicate_fields_at_any_depth(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    path = workspace / DEFAULT_AUTHORITY_EFFECT_POLICY
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"schema":"rocell.authority_effect_policy.v1",'
        '"schema":"rocell.authority_effect_policy.v1"}',
        encoding="utf-8",
    )

    with pytest.raises(AuthorityEffectPolicyError, match="duplicate.*field"):
        load_authority_effect_policy(workspace)


@pytest.mark.parametrize("bad_number", ["1.0", "NaN", "Infinity", "-Infinity"])
def test_policy_rejects_floats_and_nonfinite_numbers(
    tmp_path: Path, bad_number: str
) -> None:
    workspace = tmp_path / "workspace"
    path = workspace / DEFAULT_AUTHORITY_EFFECT_POLICY
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"schema":"rocell.authority_effect_policy.v1",'
        f'"unexpected_number":{bad_number}}}',
        encoding="utf-8",
    )

    with pytest.raises(
        AuthorityEffectPolicyError, match="floats|nonfinite"
    ):
        load_authority_effect_policy(workspace)


def test_policy_source_cannot_escape_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "authority_effect_policy.json"
    shutil.copy2(WORKSPACE / DEFAULT_AUTHORITY_EFFECT_POLICY, outside)

    with pytest.raises(AuthorityEffectPolicyError, match="outside the workspace"):
        load_authority_effect_policy(workspace, outside)


def test_policy_source_cannot_be_a_symlink(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "authority_effect_policy.json"
    shutil.copy2(WORKSPACE / DEFAULT_AUTHORITY_EFFECT_POLICY, outside)
    link = workspace / "policy-link.json"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"this host cannot create a test symlink: {exc}")

    with pytest.raises(AuthorityEffectPolicyError, match="symlink"):
        load_authority_effect_policy(workspace, link)
