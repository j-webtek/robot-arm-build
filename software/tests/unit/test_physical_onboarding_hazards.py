from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.safety.onboarding_hazards import (
    DEFAULT_PHYSICAL_ONBOARDING_HAZARDS,
    MAX_PHYSICAL_ONBOARDING_HAZARD_BYTES,
    ConfigurationEpoch,
    HazardSeverity,
    HazardStatus,
    PhysicalOnboardingHazardError,
    load_physical_onboarding_hazard_register,
    load_physical_onboarding_hazards,
)


WORKSPACE = Path(__file__).resolve().parents[3]
REGISTER_PATH = WORKSPACE / DEFAULT_PHYSICAL_ONBOARDING_HAZARDS


def _document() -> dict[str, Any]:
    return json.loads(REGISTER_PATH.read_text(encoding="utf-8"))


def _temporary_register(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> Path:
    document = copy.deepcopy(_document())
    mutate(document)
    path = tmp_path / "physical_onboarding_hazards.json"
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path


def test_default_register_covers_the_reviewed_hazards_with_zero_authority() -> None:
    before = REGISTER_PATH.read_bytes()

    register = load_physical_onboarding_hazards(WORKSPACE)

    assert REGISTER_PATH.read_bytes() == before
    assert register.runtime_activation is False
    assert register.zero_physical_authority
    assert register.authority.to_dict() == {
        "planning_authority": True,
        "simulation_authority": True,
        "device_io_authorized": False,
        "robot_power_authorized": False,
        "motion_authorized": False,
        "contact_authorized": False,
        "build_promotion_authorized": False,
        "physical_release_effect": "NONE",
    }
    assert tuple(register.by_id) == tuple(f"HZ-{index:03d}" for index in range(1, 17))
    assert len(register.hazards) == 16
    assert len(register.blocking_hazards) == 15
    assert register.by_id["HZ-015"].status is HazardStatus.REVIEW_REQUIRED
    assert all(
        hazard.status in {HazardStatus.OPEN_BLOCKING, HazardStatus.REVIEW_REQUIRED}
        for hazard in register.hazards
    )
    assert all(hazard.status.value != "CLOSED" for hazard in register.hazards)
    assert all(
        hazard.controls
        and hazard.required_evidence
        and hazard.fail_safe
        and hazard.residual_status
        for hazard in register.hazards
    )


def test_reviewed_topics_stage_and_epoch_mappings_are_preserved() -> None:
    register = load_physical_onboarding_hazard_register(WORKSPACE)

    assert tuple(hazard.title for hazard in register.hazards) == (
        "Automatic startup movement",
        "Gravity drop or stored-energy movement",
        "Pinch crush or collision injury",
        "E-stop or cutoff path ineffective",
        "Polarity overcurrent heat or fire",
        "Serial open resets controller or causes movement",
        "Camera support or gantry falls or shifts",
        "USB or tool cable snag and pull",
        "Wrong or substituted device identity",
        "Stale calibration localization or UI map",
        "Automatic retry duplicates a physical effect",
        "Concurrent sessions or processes touch one device",
        "Calibration motion requires unavailable calibration",
        "Tool damages keyboard or phone",
        "Camera evidence exposes private screen content",
        "Operator observer or reviewer role confusion",
    )
    assert all(
        hazard.severity
        in {HazardSeverity.CRITICAL, HazardSeverity.HIGH, HazardSeverity.MEDIUM}
        for hazard in register.hazards
    )
    serial_reset = register.by_id["HZ-006"]
    assert serial_reset.evidence_stages == (
        PhysicalOnboardingStage.ARM_IDENTITY,
        PhysicalOnboardingStage.POWER_ON_OBSERVATION,
        PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION,
    )
    assert serial_reset.invalidation_epochs == (
        ConfigurationEpoch.SOFTWARE_BUILD,
        ConfigurationEpoch.ARM_CONTROLLER_TOOL,
        ConfigurationEpoch.POWER_SYSTEM,
    )
    assert register.by_id["HZ-013"].fail_safe == (
        "USE_CONTAINED_PRECALIBRATION_BOOTSTRAP_ONLY"
    )
    assert register.by_id["HZ-012"].controls[0] == (
        "Acquire leases only in canonical order CELL -> SESSION -> CAMERA -> "
        "ARM_CONTROLLER, with one mutable physical session per cell."
    )
    assert register.by_id["HZ-015"].evidence_stages[0] is (
        PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
    )
    assert (
        ConfigurationEpoch.CAMERA_SUPPORT_OPTICS
        in register.by_id["HZ-015"].invalidation_epochs
    )
    assert (
        PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION
        in register.by_id["HZ-016"].evidence_stages
    )
    for hazard_id in ("HZ-001", "HZ-004"):
        assert (
            PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE
            in register.by_id[hazard_id].evidence_stages
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda document: document.update({"unexpected": True}),
            "fields differ",
        ),
        (
            lambda document: document["hazards"][0].update({"unexpected": True}),
            "fields differ",
        ),
        (
            lambda document: document.update({"runtime_activation": True}),
            "runtime_activation",
        ),
        (
            lambda document: document["authority"].update({"motion_authorized": True}),
            "zero physical authority",
        ),
        (
            lambda document: document["authority"].update({"contact_authorized": 0}),
            "zero physical authority",
        ),
        (
            lambda document: document["hazards"][0].update({"status": "CLOSED"}),
            "CLOSED is forbidden",
        ),
        (
            lambda document: document["hazards"][0].update(
                {"severity": "CATASTROPHIC"}
            ),
            "valid severity",
        ),
        (
            lambda document: document["hazards"][0].update(
                {"evidence_stages": ["not_a_stage"]}
            ),
            "valid onboarding stage",
        ),
        (
            lambda document: document["hazards"][0].update(
                {"invalidation_epochs": ["not_an_epoch"]}
            ),
            "valid configuration epoch",
        ),
    ],
)
def test_rejects_unknown_or_unsafe_values(
    tmp_path: Path,
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    path = _temporary_register(tmp_path, mutation)

    with pytest.raises(PhysicalOnboardingHazardError, match=message):
        load_physical_onboarding_hazards(tmp_path, path)


@pytest.mark.parametrize(
    "field",
    [
        "evidence_stages",
        "invalidation_epochs",
        "controls",
        "required_evidence",
    ],
)
def test_rejects_empty_hazard_collections(tmp_path: Path, field: str) -> None:
    path = _temporary_register(
        tmp_path,
        lambda document: document["hazards"][0].update({field: []}),
    )

    with pytest.raises(PhysicalOnboardingHazardError, match="must not be empty"):
        load_physical_onboarding_hazards(tmp_path, path)


@pytest.mark.parametrize("field", ["fail_safe", "residual_status"])
def test_rejects_empty_required_hazard_text(
    tmp_path: Path,
    field: str,
) -> None:
    path = _temporary_register(
        tmp_path,
        lambda document: document["hazards"][0].update({field: ""}),
    )

    with pytest.raises(PhysicalOnboardingHazardError, match="non-empty"):
        load_physical_onboarding_hazards(tmp_path, path)


def test_rejects_duplicate_hazard_ids_and_references(tmp_path: Path) -> None:
    duplicate_id = _temporary_register(
        tmp_path,
        lambda document: document["hazards"][1].update({"id": "HZ-001"}),
    )
    with pytest.raises(PhysicalOnboardingHazardError, match="duplicate hazard ID"):
        load_physical_onboarding_hazards(tmp_path, duplicate_id)

    def duplicate_stage(document: dict[str, Any]) -> None:
        stage = document["hazards"][0]["evidence_stages"][0]
        document["hazards"][0]["evidence_stages"].append(stage)

    duplicate_reference = _temporary_register(tmp_path, duplicate_stage)
    with pytest.raises(PhysicalOnboardingHazardError, match="duplicate stages"):
        load_physical_onboarding_hazards(tmp_path, duplicate_reference)


def test_rejects_noncanonical_global_lease_order(tmp_path: Path) -> None:
    path = _temporary_register(
        tmp_path,
        lambda document: document["hazards"][11]["controls"].__setitem__(
            0,
            "Acquire leases in SESSION -> CELL -> CAMERA -> ARM_CONTROLLER order.",
        ),
    )

    with pytest.raises(PhysicalOnboardingHazardError, match="canonical CELL"):
        load_physical_onboarding_hazards(tmp_path, path)


@pytest.mark.parametrize(
    ("hazard_index", "field", "value"),
    [
        (14, "evidence_stages", ["camera_frame_freshness"]),
        (14, "invalidation_epochs", ["software_build", "phone_station"]),
        (15, "evidence_stages", ["power_safety", "power_on_observation"]),
    ],
)
def test_rejects_weakened_privacy_or_role_scope(
    tmp_path: Path, hazard_index: int, field: str, value: list[str]
) -> None:
    path = _temporary_register(
        tmp_path,
        lambda document: document["hazards"][hazard_index].update({field: value}),
    )
    with pytest.raises(PhysicalOnboardingHazardError, match="reviewed stage or epoch"):
        load_physical_onboarding_hazards(tmp_path, path)


def test_rejects_duplicate_fields_floats_and_nonfinite_values(tmp_path: Path) -> None:
    original = REGISTER_PATH.read_text(encoding="utf-8")
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        original.replace(
            '"runtime_activation": false,',
            '"runtime_activation": false,\n  "runtime_activation": false,',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(PhysicalOnboardingHazardError, match="duplicate JSON field"):
        load_physical_onboarding_hazards(tmp_path, duplicate)

    floating = tmp_path / "float.json"
    floating.write_text(
        original.replace('"revision": 2,', '"revision": 2.0,', 1),
        encoding="utf-8",
    )
    with pytest.raises(PhysicalOnboardingHazardError, match="must not contain floats"):
        load_physical_onboarding_hazards(tmp_path, floating)

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text(
        original.replace('"revision": 2,', '"revision": NaN,', 1),
        encoding="utf-8",
    )
    with pytest.raises(PhysicalOnboardingHazardError, match="nonfinite"):
        load_physical_onboarding_hazards(tmp_path, nonfinite)


def test_rejects_oversized_outside_traversal_and_symlink_paths(
    tmp_path: Path,
) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (MAX_PHYSICAL_ONBOARDING_HAZARD_BYTES + 1))
    with pytest.raises(PhysicalOnboardingHazardError, match="byte limit"):
        load_physical_onboarding_hazards(tmp_path, oversized)

    with pytest.raises(PhysicalOnboardingHazardError, match="beneath the workspace"):
        load_physical_onboarding_hazards(tmp_path, REGISTER_PATH)

    with pytest.raises(PhysicalOnboardingHazardError, match="traversal"):
        load_physical_onboarding_hazards(tmp_path, Path("../outside.json"))

    target = tmp_path / "target.json"
    target.write_bytes(REGISTER_PATH.read_bytes())
    link = tmp_path / "linked.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is not available on this host")
    with pytest.raises(PhysicalOnboardingHazardError, match="symlink"):
        load_physical_onboarding_hazards(tmp_path, link)


def test_authority_dataclass_cannot_be_escalated() -> None:
    register = load_physical_onboarding_hazards(WORKSPACE)

    with pytest.raises(PhysicalOnboardingHazardError, match="zero physical authority"):
        replace(register.authority, contact_authorized=True)
