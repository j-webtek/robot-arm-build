from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json

import pytest

from rocell.application.semantic_step_schedule import (
    CONTACT_SEMANTIC_STEP_SCHEMA,
    MAX_REQUIRED_CALIBRATIONS,
    MAX_SEMANTIC_STEPS,
    OBSERVATION_SEMANTIC_STEP_SCHEMA,
    SEMANTIC_STEP_SCHEDULE_SCHEMA,
    ContactSemanticStep,
    PhoneStateObservationStep,
    SemanticStepDisposition,
    SemanticStepScheduleError,
    SemanticStepType,
    build_semantic_step_schedule,
)
from rocell.models.actions import (
    ActionPlan,
    Device,
    PressKey,
    TapPhoneTarget,
    VerifyPhoneState,
)
from rocell.typing.development_profiles import compile_development_text


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_keyboard_test_preserves_plan_and_uses_two_dense_ordinals() -> None:
    plan = compile_development_text("keyboard", "test")
    schedule = build_semantic_step_schedule(plan)

    assert schedule.schema == SEMANTIC_STEP_SCHEDULE_SCHEMA
    assert schedule.source_plan_schema == "rocell.action_plan.v1"
    assert schedule.source_plan_sha256 == plan.plan_hash
    assert schedule.device is Device.KEYBOARD
    assert schedule.profile_id == plan.profile_id
    assert schedule.requested_text_sha256 == plan.requested_text_sha256
    assert schedule.required_calibrations == plan.required_calibrations
    assert type(schedule.steps) is tuple
    assert schedule.contact_count == 4
    assert schedule.observation_count == 0

    contacts = schedule.steps
    assert all(type(step) is ContactSemanticStep for step in contacts)
    assert [step.semantic_step_ordinal for step in contacts] == [0, 1, 2, 3]
    assert [step.contact_occurrence_ordinal for step in contacts] == [0, 1, 2, 3]  # type: ignore[union-attr]
    assert [step.target_id for step in contacts] == ["T", "E", "S", "T"]  # type: ignore[union-attr]
    assert all(
        step.step_type is SemanticStepType.PRESS_KEY for step in contacts
    )
    assert all(step.disposition is SemanticStepDisposition.CONTACT for step in contacts)
    for action, step in zip(plan.actions, contacts):
        assert step.action_canonical_sha256 == _canonical_hash(action.to_dict())

    schedule.assert_matches_action_plan(plan)


def test_phone_test_period_has_six_semantic_steps_but_only_five_contacts() -> None:
    plan = compile_development_text("phone", "test.")
    schedule = build_semantic_step_schedule(plan)

    assert len(plan.actions) == 6
    assert len(schedule.steps) == 6
    assert schedule.contact_count == 5
    assert schedule.observation_count == 1

    observation = schedule.steps[0]
    assert type(observation) is PhoneStateObservationStep
    assert observation.schema == OBSERVATION_SEMANTIC_STEP_SCHEMA
    assert observation.semantic_step_ordinal == 0
    assert observation.step_type is SemanticStepType.VERIFY_PHONE_STATE
    assert observation.disposition is SemanticStepDisposition.OBSERVATION
    assert observation.state_id == "KEYBOARD_LOWER"
    assert observation.action_canonical_sha256 == _canonical_hash(
        plan.actions[0].to_dict()
    )

    contacts = schedule.steps[1:]
    assert all(type(step) is ContactSemanticStep for step in contacts)
    assert [step.semantic_step_ordinal for step in contacts] == [1, 2, 3, 4, 5]
    assert [step.contact_occurrence_ordinal for step in contacts] == [0, 1, 2, 3, 4]  # type: ignore[union-attr]
    assert [step.target_id for step in contacts] == [  # type: ignore[union-attr]
        "key_t",
        "key_e",
        "key_s",
        "key_t",
        "key_period",
    ]
    assert all(step.schema == CONTACT_SEMANTIC_STEP_SCHEMA for step in contacts)
    assert all(
        step.step_type is SemanticStepType.TAP_PHONE_TARGET for step in contacts
    )


def test_phone_verification_serialization_has_no_fake_contact_route_or_journal() -> None:
    schedule = build_semantic_step_schedule(
        compile_development_text("phone", "test.")
    )
    observation = schedule.steps[0]
    assert isinstance(observation, PhoneStateObservationStep)
    document = observation.to_dict()

    assert document == {
        "schema": OBSERVATION_SEMANTIC_STEP_SCHEMA,
        "disposition": "OBSERVATION",
        "step_type": "VERIFY_PHONE_STATE",
        "semantic_step_ordinal": 0,
        "action_canonical_sha256": _canonical_hash(
            {"type": "verify_phone_state", "state": "KEYBOARD_LOWER"}
        ),
        "state": {"state_id": "KEYBOARD_LOWER"},
    }
    forbidden = {
        "contact_occurrence_ordinal",
        "contact_id",
        "route_id",
        "route_target_id",
        "journal_id",
        "journal_action_id",
        "controller_command",
    }
    assert forbidden.isdisjoint(document)
    assert not hasattr(observation, "contact_occurrence_ordinal")
    assert not hasattr(observation, "target_id")


def test_schedule_document_is_bounded_canonical_zero_authority_evidence() -> None:
    schedule = build_semantic_step_schedule(
        compile_development_text("keyboard", "test")
    )
    document = schedule.to_dict()

    assert document["counts"] == {
        "semantic_steps": 4,
        "contact_occurrences": 4,
        "observation_steps": 0,
    }
    assert document["authority"] == {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "physical_release_effect": "NONE",
    }
    assert schedule.canonical_sha256 == _canonical_hash(document)


def test_builder_and_hash_are_deterministic_without_mutating_action_plan() -> None:
    plan = compile_development_text("phone", "test.")
    plan_before = plan.to_dict()

    first = build_semantic_step_schedule(plan)
    second = build_semantic_step_schedule(plan)

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.canonical_sha256 == second.canonical_sha256
    assert plan.to_dict() == plan_before


def test_schedule_and_step_tuples_are_immutable() -> None:
    schedule = build_semantic_step_schedule(
        compile_development_text("keyboard", "test")
    )
    assert type(schedule.required_calibrations) is tuple
    assert type(schedule.steps) is tuple

    with pytest.raises(FrozenInstanceError):
        schedule.steps = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        schedule.steps[0].semantic_step_ordinal = 9  # type: ignore[misc]


@pytest.mark.parametrize("changed_ordinal", [1, 2])
def test_semantic_ordinal_gap_or_duplicate_is_rejected(changed_ordinal: int) -> None:
    schedule = build_semantic_step_schedule(
        compile_development_text("keyboard", "test")
    )
    changed_first = replace(
        schedule.steps[0], semantic_step_ordinal=changed_ordinal
    )

    with pytest.raises(SemanticStepScheduleError, match="semantic_step_ordinal"):
        replace(schedule, steps=(changed_first, *schedule.steps[1:]))


@pytest.mark.parametrize("changed_ordinal", [0, 2])
def test_contact_ordinal_duplicate_or_gap_is_rejected(changed_ordinal: int) -> None:
    schedule = build_semantic_step_schedule(
        compile_development_text("keyboard", "test")
    )
    second = schedule.steps[1]
    assert isinstance(second, ContactSemanticStep)
    changed_second = replace(second, contact_occurrence_ordinal=changed_ordinal)

    with pytest.raises(SemanticStepScheduleError, match="contact_occurrence_ordinal"):
        replace(
            schedule,
            steps=(schedule.steps[0], changed_second, *schedule.steps[2:]),
        )


def test_action_field_or_action_hash_mutation_is_rejected() -> None:
    schedule = build_semantic_step_schedule(
        compile_development_text("phone", "test.")
    )
    contact = schedule.steps[1]
    assert isinstance(contact, ContactSemanticStep)

    with pytest.raises(SemanticStepScheduleError, match="does not bind"):
        replace(contact, target_id="key_x")
    with pytest.raises(SemanticStepScheduleError, match="does not bind"):
        replace(contact, action_canonical_sha256="0" * 64)

    observation = schedule.steps[0]
    assert isinstance(observation, PhoneStateObservationStep)
    object.__setattr__(observation, "state_id", "SYMBOLS_1")
    with pytest.raises(SemanticStepScheduleError, match="does not bind|changed"):
        schedule.validate()


def test_verify_phone_state_cannot_be_substituted_as_contact() -> None:
    verify_hash = _canonical_hash(
        {"type": "verify_phone_state", "state": "KEYBOARD_LOWER"}
    )
    with pytest.raises(SemanticStepScheduleError, match="contact step_type"):
        ContactSemanticStep(
            semantic_step_ordinal=0,
            contact_occurrence_ordinal=0,
            step_type=SemanticStepType.VERIFY_PHONE_STATE,
            action_canonical_sha256=verify_hash,
            target_id="KEYBOARD_LOWER",
        )


def test_step_and_action_type_substitution_is_rejected() -> None:
    class DerivedPressKey(PressKey):
        pass

    source = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id="keyboard/substitution-test",
        text="a",
        actions=(DerivedPressKey("A"),),
        required_calibrations=(),
    )
    with pytest.raises(SemanticStepScheduleError, match="substituted action type"):
        build_semantic_step_schedule(source)

    class DerivedActionPlan(ActionPlan):
        pass

    derived = DerivedActionPlan(
        device=Device.KEYBOARD,
        profile_id="keyboard/substitution-test",
        requested_text_sha256=hashlib.sha256(b"a").hexdigest(),
        actions=(PressKey("A"),),
        required_calibrations=(),
    )
    with pytest.raises(TypeError, match="exactly ActionPlan"):
        build_semantic_step_schedule(derived)


def test_schedule_rejects_substituted_step_type() -> None:
    class DerivedContactStep(ContactSemanticStep):
        pass

    schedule = build_semantic_step_schedule(
        compile_development_text("keyboard", "test")
    )
    first = schedule.steps[0]
    assert isinstance(first, ContactSemanticStep)
    substituted = DerivedContactStep(
        semantic_step_ordinal=first.semantic_step_ordinal,
        contact_occurrence_ordinal=first.contact_occurrence_ordinal,
        step_type=first.step_type,
        action_canonical_sha256=first.action_canonical_sha256,
        target_id=first.target_id,
    )
    with pytest.raises(SemanticStepScheduleError, match="substituted step type"):
        replace(schedule, steps=(substituted, *schedule.steps[1:]))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_plan_sha256", "0" * 64),
        ("profile_id", "different/profile"),
        ("requested_text_sha256", "1" * 64),
        ("required_calibrations", ("different/calibration",)),
    ],
)
def test_source_plan_binding_field_mutation_is_rejected(
    field: str, value: object
) -> None:
    schedule = build_semantic_step_schedule(
        compile_development_text("keyboard", "test")
    )
    with pytest.raises(SemanticStepScheduleError, match="source_plan_sha256"):
        replace(schedule, **{field: value})


def test_schedule_rejects_empty_and_oversized_action_plans() -> None:
    empty = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id="keyboard/empty",
        text="",
        actions=(),
        required_calibrations=(),
    )
    with pytest.raises(SemanticStepScheduleError, match="must contain"):
        build_semantic_step_schedule(empty)

    oversized = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id="keyboard/oversized",
        text="x" * (MAX_SEMANTIC_STEPS + 1),
        actions=tuple(PressKey("X") for _ in range(MAX_SEMANTIC_STEPS + 1)),
        required_calibrations=(),
    )
    with pytest.raises(SemanticStepScheduleError, match="must contain"):
        build_semantic_step_schedule(oversized)


def test_schedule_rejects_oversized_calibration_and_action_fields() -> None:
    too_many_calibrations = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id="keyboard/calibration-limit",
        text="x",
        actions=(PressKey("X"),),
        required_calibrations=tuple(
            f"calibration/{index}" for index in range(MAX_REQUIRED_CALIBRATIONS + 1)
        ),
    )
    with pytest.raises(SemanticStepScheduleError, match="count limit"):
        build_semantic_step_schedule(too_many_calibrations)

    oversized_target = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id="keyboard/target-limit",
        text="x",
        actions=(PressKey("X" * 257),),
        required_calibrations=(),
    )
    with pytest.raises(SemanticStepScheduleError, match="exceeds 256"):
        build_semantic_step_schedule(oversized_target)


def test_phone_state_fields_are_preserved_exactly_and_revalidated() -> None:
    plan = ActionPlan.from_text(
        device=Device.PHONE,
        profile_id="phone/state-transition",
        text="!",
        actions=(
            VerifyPhoneState("KEYBOARD_LOWER"),
            TapPhoneTarget(
                "open_symbols", "KEYBOARD_LOWER", resulting_state="SYMBOLS_1"
            ),
            VerifyPhoneState("SYMBOLS_1"),
        ),
        required_calibrations=("phone/target-map",),
    )
    schedule = build_semantic_step_schedule(plan)
    tap = schedule.steps[1]
    assert isinstance(tap, ContactSemanticStep)
    assert tap.required_state == "KEYBOARD_LOWER"
    assert tap.resulting_state == "SYMBOLS_1"
    assert tap.action_document() == plan.actions[1].to_dict()

    final_observation = schedule.steps[2]
    assert isinstance(final_observation, PhoneStateObservationStep)
    with pytest.raises(SemanticStepScheduleError, match="does not bind"):
        replace(final_observation, state_id="KEYBOARD_LOWER")


def test_assert_matches_action_plan_rejects_a_different_valid_plan() -> None:
    schedule = build_semantic_step_schedule(
        compile_development_text("keyboard", "test")
    )
    different = compile_development_text("keyboard", "tent")
    with pytest.raises(SemanticStepScheduleError, match="differs"):
        schedule.assert_matches_action_plan(different)

