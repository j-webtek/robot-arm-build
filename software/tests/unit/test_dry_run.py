from __future__ import annotations

from rocell.models.profiles import KeyboardProfile, PhoneKeySpec, PhoneProfile
from rocell.motion.dry_run import DryRunEngine
from rocell.motion.primitives import MotionPhase
from rocell.typing.keyboard_compiler import KeyboardCompiler
from rocell.typing.phone_compiler import PhoneCompiler


def test_dry_run_is_deterministic_and_never_accesses_hardware(blocked_snapshot: object) -> None:
    plan = KeyboardCompiler().compile(
        "a",
        KeyboardProfile("keyboard/test", {"a": ("KEY_A",)}),
    )
    engine = DryRunEngine()
    first = engine.run(plan, blocked_snapshot)  # type: ignore[arg-type]
    second = engine.run(plan, blocked_snapshot)  # type: ignore[arg-type]
    assert first == second
    assert first.report_hash == second.report_hash
    assert first.to_dict()["hardware_accessed"] is False
    assert [step.phase for step in first.steps] == [
        MotionPhase.PARK,
        MotionPhase.TRANSIT,
        MotionPhase.HOVER,
        MotionPhase.VISION_CORRECT,
        MotionPhase.APPROACH,
        MotionPhase.CONTACT,
        MotionPhase.RETRACT,
        MotionPhase.VERIFY,
        MotionPhase.PARK,
        MotionPhase.COMPLETE,
    ]
    assert all(step.simulated for step in first.steps)


def test_phone_state_verification_does_not_create_contact_phase(blocked_snapshot: object) -> None:
    plan = PhoneCompiler().compile(
        "a",
        PhoneProfile(
            "phone/test",
            {"a": PhoneKeySpec("KEY_A", "KEYBOARD_LOWER")},
        ),
    )
    report = DryRunEngine().run(plan, blocked_snapshot)  # type: ignore[arg-type]
    first_action_steps = [step for step in report.steps if step.action_index == 0]
    assert [step.phase for step in first_action_steps] == [MotionPhase.VERIFY]
    tap_steps = [step for step in report.steps if step.action_index == 1]
    assert MotionPhase.CONTACT in [step.phase for step in tap_steps]


def test_empty_plan_stays_parked(blocked_snapshot: object) -> None:
    plan = KeyboardCompiler().compile(
        "",
        KeyboardProfile("keyboard/test", {"a": ("KEY_A",)}),
    )
    report = DryRunEngine().run(plan, blocked_snapshot)  # type: ignore[arg-type]
    assert [step.phase for step in report.steps] == [
        MotionPhase.PARK,
        MotionPhase.PARK,
        MotionPhase.COMPLETE,
    ]
