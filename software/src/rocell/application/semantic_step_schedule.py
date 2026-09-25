"""Strict, zero-authority scheduling of semantic typing-plan steps.

``ActionPlan`` deliberately describes user-visible intent rather than robot
motion.  This module preserves that plan and gives its two different kinds of
work separate order domains:

* every source action receives a dense ``semantic_step_ordinal``;
* only ``PressKey`` and ``TapPhoneTarget`` receive a dense
  ``contact_occurrence_ordinal``;
* ``VerifyPhoneState`` remains an observation and never receives a synthetic
  contact, route, or journal identity.

The result is planning evidence only.  It contains no pose, trajectory,
controller command, live-motion permit, or physical-contact authority.  A
later integration coordinator may bind contact occurrences to separately
validated routes and journals, but must not reinterpret observation steps as
contacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import re
from typing import TypeAlias

from rocell.models.actions import (
    ActionPlan,
    Device,
    PressKey,
    TapPhoneTarget,
    VerifyPhoneState,
)


SEMANTIC_STEP_SCHEDULE_SCHEMA = "rocell.zero_authority.semantic_step_schedule.v1"
CONTACT_SEMANTIC_STEP_SCHEMA = "rocell.zero_authority.semantic_contact_step.v1"
OBSERVATION_SEMANTIC_STEP_SCHEMA = (
    "rocell.zero_authority.semantic_observation_step.v1"
)

# These limits are deliberately tighter than the unbounded semantic source
# model.  They keep downstream hashing/reconstruction bounded before any
# route, journal, camera, or controller adapter sees the plan.
MAX_SEMANTIC_STEPS = 512
MAX_REQUIRED_CALIBRATIONS = 64
MAX_SEMANTIC_TEXT_CHARACTERS = 256
MAX_ACTION_CANONICAL_BYTES = 4096
MAX_SCHEDULE_CANONICAL_BYTES = 1024 * 1024

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SemanticStepScheduleError(ValueError):
    """A semantic schedule or its ActionPlan binding is invalid."""


class SemanticStepType(str, Enum):
    """The three exact source-action variants understood by the scheduler."""

    PRESS_KEY = "PRESS_KEY"
    TAP_PHONE_TARGET = "TAP_PHONE_TARGET"
    VERIFY_PHONE_STATE = "VERIFY_PHONE_STATE"


class SemanticStepDisposition(str, Enum):
    """Whether a step requests contact or only observes external state."""

    CONTACT = "CONTACT"
    OBSERVATION = "OBSERVATION"


def _canonical_bytes(value: object, *, maximum: int) -> bytes:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SemanticStepScheduleError("value is not canonical JSON data") from exc
    if len(payload) > maximum:
        raise SemanticStepScheduleError("canonical JSON exceeds its byte limit")
    return payload


def _canonical_hash(value: object, *, maximum: int) -> str:
    return hashlib.sha256(_canonical_bytes(value, maximum=maximum)).hexdigest()


def _digest(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise SemanticStepScheduleError(
            f"{label} must be an exact lowercase SHA-256 digest"
        )
    return value


def _bounded_text(value: object, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise SemanticStepScheduleError(
            f"{label} must be an exact non-empty, surrounding-whitespace-free string"
        )
    if len(value) > MAX_SEMANTIC_TEXT_CHARACTERS:
        raise SemanticStepScheduleError(
            f"{label} exceeds {MAX_SEMANTIC_TEXT_CHARACTERS} characters"
        )
    if any(ord(character) < 32 for character in value):
        raise SemanticStepScheduleError(f"{label} contains a control character")
    return value


def _ordinal(value: object, label: str) -> int:
    if (
        isinstance(value, bool)
        or type(value) is not int
        or not 0 <= value < MAX_SEMANTIC_STEPS
    ):
        raise SemanticStepScheduleError(
            f"{label} must be an exact bounded nonnegative integer"
        )
    return value


def _action_hash(document: dict[str, object]) -> str:
    return _canonical_hash(document, maximum=MAX_ACTION_CANONICAL_BYTES)


def _authority_document() -> dict[str, object]:
    """Return permanent negative authority; there is no enabling flag."""

    return {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "physical_release_effect": "NONE",
    }


@dataclass(frozen=True, slots=True)
class ContactSemanticStep:
    """One semantic action that may later be bound to a physical contact.

    The occurrence ordinal is not itself a route or journal identifier.  It is
    the dense join key a future coordinator must use when producing those
    separately reviewed artifacts.
    """

    semantic_step_ordinal: int
    contact_occurrence_ordinal: int
    step_type: SemanticStepType
    action_canonical_sha256: str
    target_id: str
    required_state: str | None = None
    resulting_state: str | None = None
    schema: str = CONTACT_SEMANTIC_STEP_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(
            self,
            "_sealed_sha256",
            _canonical_hash(self._document_unvalidated(), maximum=MAX_ACTION_CANONICAL_BYTES),
        )

    @property
    def disposition(self) -> SemanticStepDisposition:
        return SemanticStepDisposition.CONTACT

    def action_document(self) -> dict[str, object]:
        if self.step_type is SemanticStepType.PRESS_KEY:
            return {"type": "press_key", "key": self.target_id}
        document: dict[str, object] = {
            "type": "tap_phone_target",
            "target": self.target_id,
            "required_state": self.required_state,
        }
        if self.resulting_state is not None:
            document["resulting_state"] = self.resulting_state
        return document

    def _validate_unsealed(self) -> None:
        if type(self.schema) is not str or self.schema != CONTACT_SEMANTIC_STEP_SCHEMA:
            raise SemanticStepScheduleError("unsupported contact-step schema")
        _ordinal(self.semantic_step_ordinal, "semantic_step_ordinal")
        _ordinal(self.contact_occurrence_ordinal, "contact_occurrence_ordinal")
        if type(self.step_type) is not SemanticStepType or self.step_type not in (
            SemanticStepType.PRESS_KEY,
            SemanticStepType.TAP_PHONE_TARGET,
        ):
            raise SemanticStepScheduleError(
                "contact step_type must be PRESS_KEY or TAP_PHONE_TARGET"
            )
        _bounded_text(self.target_id, "target_id")
        if self.step_type is SemanticStepType.PRESS_KEY:
            if self.required_state is not None or self.resulting_state is not None:
                raise SemanticStepScheduleError(
                    "PRESS_KEY cannot contain phone state fields"
                )
        else:
            _bounded_text(self.required_state, "required_state")
            if self.resulting_state is not None:
                _bounded_text(self.resulting_state, "resulting_state")
        expected_hash = _action_hash(self.action_document())
        if _digest(
            self.action_canonical_sha256, "action_canonical_sha256"
        ) != expected_hash:
            raise SemanticStepScheduleError(
                "action_canonical_sha256 does not bind the contact action fields"
            )

    def _document_unvalidated(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "disposition": self.disposition.value,
            "step_type": self.step_type.value,
            "semantic_step_ordinal": self.semantic_step_ordinal,
            "contact_occurrence_ordinal": self.contact_occurrence_ordinal,
            "action_canonical_sha256": self.action_canonical_sha256,
            "target": {
                "target_id": self.target_id,
                "required_state": self.required_state,
                "resulting_state": self.resulting_state,
            },
        }

    def validate(self) -> None:
        """Revalidate fields and reject post-construction mutation."""

        self._validate_unsealed()
        if (
            _canonical_hash(
                self._document_unvalidated(), maximum=MAX_ACTION_CANONICAL_BYTES
            )
            != self._sealed_sha256
        ):
            raise SemanticStepScheduleError("contact step changed after construction")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document_unvalidated()


@dataclass(frozen=True, slots=True)
class PhoneStateObservationStep:
    """One observation-only phone-state check from ``VerifyPhoneState``.

    Deliberately absent are contact occurrence, route, command, and journal
    fields.  An observation can block subsequent work, but cannot masquerade
    as a touch or consume a contact occurrence.
    """

    semantic_step_ordinal: int
    step_type: SemanticStepType
    action_canonical_sha256: str
    state_id: str
    schema: str = OBSERVATION_SEMANTIC_STEP_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(
            self,
            "_sealed_sha256",
            _canonical_hash(self._document_unvalidated(), maximum=MAX_ACTION_CANONICAL_BYTES),
        )

    @property
    def disposition(self) -> SemanticStepDisposition:
        return SemanticStepDisposition.OBSERVATION

    def action_document(self) -> dict[str, object]:
        return {"type": "verify_phone_state", "state": self.state_id}

    def _validate_unsealed(self) -> None:
        if (
            type(self.schema) is not str
            or self.schema != OBSERVATION_SEMANTIC_STEP_SCHEMA
        ):
            raise SemanticStepScheduleError("unsupported observation-step schema")
        _ordinal(self.semantic_step_ordinal, "semantic_step_ordinal")
        if (
            type(self.step_type) is not SemanticStepType
            or self.step_type is not SemanticStepType.VERIFY_PHONE_STATE
        ):
            raise SemanticStepScheduleError(
                "observation step_type must be VERIFY_PHONE_STATE"
            )
        _bounded_text(self.state_id, "state_id")
        expected_hash = _action_hash(self.action_document())
        if _digest(
            self.action_canonical_sha256, "action_canonical_sha256"
        ) != expected_hash:
            raise SemanticStepScheduleError(
                "action_canonical_sha256 does not bind the observed state"
            )

    def _document_unvalidated(self) -> dict[str, object]:
        # Do not add null contact/route/journal fields here.  Their absence is
        # the machine-checkable statement that this is not a contact action.
        return {
            "schema": self.schema,
            "disposition": self.disposition.value,
            "step_type": self.step_type.value,
            "semantic_step_ordinal": self.semantic_step_ordinal,
            "action_canonical_sha256": self.action_canonical_sha256,
            "state": {"state_id": self.state_id},
        }

    def validate(self) -> None:
        """Revalidate fields and reject post-construction mutation."""

        self._validate_unsealed()
        if (
            _canonical_hash(
                self._document_unvalidated(), maximum=MAX_ACTION_CANONICAL_BYTES
            )
            != self._sealed_sha256
        ):
            raise SemanticStepScheduleError(
                "observation step changed after construction"
            )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document_unvalidated()


ScheduledSemanticStep: TypeAlias = ContactSemanticStep | PhoneStateObservationStep


@dataclass(frozen=True, slots=True)
class SemanticStepSchedule:
    """An immutable, reconstructable binding to one exact ``ActionPlan``."""

    source_plan_sha256: str
    source_plan_schema: str
    device: Device
    profile_id: str
    requested_text_sha256: str
    required_calibrations: tuple[str, ...]
    steps: tuple[ScheduledSemanticStep, ...]
    schema: str = SEMANTIC_STEP_SCHEDULE_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(
            self,
            "_sealed_sha256",
            _canonical_hash(
                self._document_unvalidated(), maximum=MAX_SCHEDULE_CANONICAL_BYTES
            ),
        )

    @property
    def contact_count(self) -> int:
        return sum(type(step) is ContactSemanticStep for step in self.steps)

    @property
    def observation_count(self) -> int:
        return sum(type(step) is PhoneStateObservationStep for step in self.steps)

    def _source_action_plan_document(self) -> dict[str, object]:
        return {
            "schema": self.source_plan_schema,
            "device": self.device.value,
            "device_profile": self.profile_id,
            "requested_text_sha256": self.requested_text_sha256,
            "actions": [step.action_document() for step in self.steps],
            "required_calibrations": list(self.required_calibrations),
        }

    def _validate_unsealed(self) -> None:
        if type(self.schema) is not str or self.schema != SEMANTIC_STEP_SCHEDULE_SCHEMA:
            raise SemanticStepScheduleError("unsupported semantic-step schedule schema")
        if (
            type(self.source_plan_schema) is not str
            or self.source_plan_schema != "rocell.action_plan.v1"
        ):
            raise SemanticStepScheduleError("unsupported source ActionPlan schema")
        _digest(self.source_plan_sha256, "source_plan_sha256")
        if type(self.device) is not Device:
            raise SemanticStepScheduleError("device must be exactly Device")
        _bounded_text(self.profile_id, "profile_id")
        _digest(self.requested_text_sha256, "requested_text_sha256")
        if type(self.required_calibrations) is not tuple:
            raise SemanticStepScheduleError(
                "required_calibrations must be an immutable tuple"
            )
        if len(self.required_calibrations) > MAX_REQUIRED_CALIBRATIONS:
            raise SemanticStepScheduleError(
                "required_calibrations exceeds its count limit"
            )
        for index, calibration_id in enumerate(self.required_calibrations):
            _bounded_text(calibration_id, f"required_calibrations[{index}]")
        if len(set(self.required_calibrations)) != len(self.required_calibrations):
            raise SemanticStepScheduleError("required_calibrations contains duplicates")
        if type(self.steps) is not tuple or not 1 <= len(self.steps) <= MAX_SEMANTIC_STEPS:
            raise SemanticStepScheduleError(
                "steps must be a non-empty bounded immutable tuple"
            )
        for step in self.steps:
            if type(step) not in (ContactSemanticStep, PhoneStateObservationStep):
                raise SemanticStepScheduleError(
                    "steps contains an unsupported or substituted step type"
                )
            step.validate()
        semantic_ordinals = tuple(step.semantic_step_ordinal for step in self.steps)
        if semantic_ordinals != tuple(range(len(self.steps))):
            raise SemanticStepScheduleError(
                "semantic_step_ordinal values must be dense, unique, and ordered"
            )
        contacts = tuple(
            step
            for step in self.steps
            if type(step) is ContactSemanticStep
        )
        contact_ordinals = tuple(
            step.contact_occurrence_ordinal for step in contacts
        )
        if contact_ordinals != tuple(range(len(contacts))):
            raise SemanticStepScheduleError(
                "contact_occurrence_ordinal values must be dense, unique, and ordered"
            )
        if self.device is Device.KEYBOARD:
            if any(
                type(step) is not ContactSemanticStep
                or step.step_type is not SemanticStepType.PRESS_KEY
                for step in self.steps
            ):
                raise SemanticStepScheduleError(
                    "keyboard schedules may contain only PRESS_KEY contact steps"
                )
        else:
            if any(
                type(step) is ContactSemanticStep
                and step.step_type is not SemanticStepType.TAP_PHONE_TARGET
                for step in self.steps
            ):
                raise SemanticStepScheduleError(
                    "phone contact steps must be TAP_PHONE_TARGET"
                )

        source_document = self._source_action_plan_document()
        if (
            _canonical_hash(
                source_document, maximum=MAX_SCHEDULE_CANONICAL_BYTES
            )
            != self.source_plan_sha256
        ):
            raise SemanticStepScheduleError(
                "source_plan_sha256 does not bind the reconstructed ActionPlan"
            )
        # Reconstructing through the source type re-applies its cross-action
        # phone-state validation instead of duplicating those semantics here.
        try:
            reconstructed = ActionPlan(
                device=self.device,
                profile_id=self.profile_id,
                requested_text_sha256=self.requested_text_sha256,
                actions=tuple(_action_from_step(step) for step in self.steps),
                required_calibrations=self.required_calibrations,
                schema=self.source_plan_schema,
            )
        except (TypeError, ValueError) as exc:
            raise SemanticStepScheduleError(
                "scheduled steps do not reconstruct a valid ActionPlan"
            ) from exc
        if reconstructed.to_dict() != source_document:
            raise SemanticStepScheduleError(
                "scheduled fields do not preserve the source ActionPlan exactly"
            )

    def _document_unvalidated(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_action_plan": {
                "schema": self.source_plan_schema,
                "canonical_sha256": self.source_plan_sha256,
                "device": self.device.value,
                "device_profile": self.profile_id,
                "requested_text_sha256": self.requested_text_sha256,
                "required_calibrations": list(self.required_calibrations),
            },
            "counts": {
                "semantic_steps": len(self.steps),
                "contact_occurrences": self.contact_count,
                "observation_steps": self.observation_count,
            },
            "steps": [step._document_unvalidated() for step in self.steps],
            "authority": _authority_document(),
        }

    def validate(self) -> None:
        """Revalidate the entire source binding and construction-time seal."""

        self._validate_unsealed()
        if (
            _canonical_hash(
                self._document_unvalidated(), maximum=MAX_SCHEDULE_CANONICAL_BYTES
            )
            != self._sealed_sha256
        ):
            raise SemanticStepScheduleError("schedule changed after construction")

    @property
    def canonical_sha256(self) -> str:
        self.validate()
        return _canonical_hash(
            self._document_unvalidated(), maximum=MAX_SCHEDULE_CANONICAL_BYTES
        )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document_unvalidated()

    def assert_matches_action_plan(self, plan: ActionPlan) -> None:
        """Require an exact current match to the source plan, not only its hash."""

        self.validate()
        snapshot = _snapshot_action_plan(plan)
        if snapshot.to_dict() != self._source_action_plan_document():
            raise SemanticStepScheduleError(
                "ActionPlan differs from the plan preserved by this schedule"
            )
        if snapshot.plan_hash != self.source_plan_sha256:
            raise SemanticStepScheduleError("ActionPlan canonical hash changed")


def _action_from_step(
    step: ScheduledSemanticStep,
) -> PressKey | TapPhoneTarget | VerifyPhoneState:
    if isinstance(step, PhoneStateObservationStep):
        return VerifyPhoneState(step.state_id)
    assert isinstance(step, ContactSemanticStep)
    if step.step_type is SemanticStepType.PRESS_KEY:
        return PressKey(step.target_id)
    assert step.required_state is not None
    return TapPhoneTarget(
        target_id=step.target_id,
        required_state=step.required_state,
        resulting_state=step.resulting_state,
    )


def _snapshot_action_plan(plan: ActionPlan) -> ActionPlan:
    """Copy and revalidate one exact ActionPlan without retaining caller objects."""

    if type(plan) is not ActionPlan:
        raise TypeError("plan must be exactly ActionPlan")
    if type(plan.actions) is not tuple:
        raise SemanticStepScheduleError("ActionPlan.actions must be an immutable tuple")
    if not 1 <= len(plan.actions) <= MAX_SEMANTIC_STEPS:
        raise SemanticStepScheduleError(
            f"ActionPlan must contain 1..{MAX_SEMANTIC_STEPS} semantic actions"
        )
    if type(plan.required_calibrations) is not tuple:
        raise SemanticStepScheduleError(
            "ActionPlan.required_calibrations must be an immutable tuple"
        )
    if len(plan.required_calibrations) > MAX_REQUIRED_CALIBRATIONS:
        raise SemanticStepScheduleError(
            "ActionPlan required_calibrations exceeds its count limit"
        )
    if type(plan.device) is not Device:
        raise SemanticStepScheduleError("ActionPlan.device must be exactly Device")
    _bounded_text(plan.profile_id, "ActionPlan.profile_id")
    _digest(plan.requested_text_sha256, "ActionPlan.requested_text_sha256")
    if type(plan.schema) is not str or plan.schema != "rocell.action_plan.v1":
        raise SemanticStepScheduleError("unsupported ActionPlan schema")

    copied_actions: list[PressKey | TapPhoneTarget | VerifyPhoneState] = []
    try:
        for action in plan.actions:
            if type(action) is PressKey:
                copied_actions.append(PressKey(_bounded_text(action.key_id, "key_id")))
            elif type(action) is TapPhoneTarget:
                target_id = _bounded_text(action.target_id, "target_id")
                required_state = _bounded_text(action.required_state, "required_state")
                resulting_state = action.resulting_state
                if resulting_state is not None:
                    resulting_state = _bounded_text(resulting_state, "resulting_state")
                copied_actions.append(
                    TapPhoneTarget(target_id, required_state, resulting_state)
                )
            elif type(action) is VerifyPhoneState:
                copied_actions.append(
                    VerifyPhoneState(_bounded_text(action.state_id, "state_id"))
                )
            else:
                raise SemanticStepScheduleError(
                    "ActionPlan contains an unsupported or substituted action type"
                )
        copied = ActionPlan(
            device=plan.device,
            profile_id=plan.profile_id,
            requested_text_sha256=plan.requested_text_sha256,
            actions=tuple(copied_actions),
            required_calibrations=tuple(
                _bounded_text(value, f"required_calibrations[{index}]")
                for index, value in enumerate(plan.required_calibrations)
            ),
            schema=plan.schema,
        )
    except SemanticStepScheduleError:
        raise
    except (TypeError, ValueError) as exc:
        raise SemanticStepScheduleError("ActionPlan failed strict revalidation") from exc

    try:
        original_document = plan.to_dict()
        original_hash = plan.plan_hash
    except (AttributeError, TypeError, ValueError) as exc:
        raise SemanticStepScheduleError(
            "ActionPlan cannot produce canonical source evidence"
        ) from exc
    if original_document != copied.to_dict() or original_hash != copied.plan_hash:
        raise SemanticStepScheduleError(
            "ActionPlan representation changed during exact snapshotting"
        )
    _canonical_bytes(original_document, maximum=MAX_SCHEDULE_CANONICAL_BYTES)
    return copied


def build_semantic_step_schedule(plan: ActionPlan) -> SemanticStepSchedule:
    """Preserve one exact ActionPlan as separate semantic/contact orderings.

    This builder performs no coordinate lookup, route generation, journaling,
    camera access, controller access, or authorization.  Its output is
    permanently zero-authority integration evidence.
    """

    source = _snapshot_action_plan(plan)
    steps: list[ScheduledSemanticStep] = []
    contact_ordinal = 0
    for semantic_ordinal, action in enumerate(source.actions):
        action_document = action.to_dict()
        canonical_sha256 = _action_hash(action_document)
        if type(action) is PressKey:
            steps.append(
                ContactSemanticStep(
                    semantic_step_ordinal=semantic_ordinal,
                    contact_occurrence_ordinal=contact_ordinal,
                    step_type=SemanticStepType.PRESS_KEY,
                    action_canonical_sha256=canonical_sha256,
                    target_id=action.key_id,
                )
            )
            contact_ordinal += 1
        elif type(action) is TapPhoneTarget:
            steps.append(
                ContactSemanticStep(
                    semantic_step_ordinal=semantic_ordinal,
                    contact_occurrence_ordinal=contact_ordinal,
                    step_type=SemanticStepType.TAP_PHONE_TARGET,
                    action_canonical_sha256=canonical_sha256,
                    target_id=action.target_id,
                    required_state=action.required_state,
                    resulting_state=action.resulting_state,
                )
            )
            contact_ordinal += 1
        else:
            # Exact source validation means this is VerifyPhoneState.  Keeping
            # it in a separate type makes a fake contact impossible here.
            assert type(action) is VerifyPhoneState
            steps.append(
                PhoneStateObservationStep(
                    semantic_step_ordinal=semantic_ordinal,
                    step_type=SemanticStepType.VERIFY_PHONE_STATE,
                    action_canonical_sha256=canonical_sha256,
                    state_id=action.state_id,
                )
            )

    schedule = SemanticStepSchedule(
        source_plan_sha256=source.plan_hash,
        source_plan_schema=source.schema,
        device=source.device,
        profile_id=source.profile_id,
        requested_text_sha256=source.requested_text_sha256,
        required_calibrations=source.required_calibrations,
        steps=tuple(steps),
    )
    schedule.assert_matches_action_plan(source)
    return schedule


__all__ = [
    "CONTACT_SEMANTIC_STEP_SCHEMA",
    "MAX_REQUIRED_CALIBRATIONS",
    "MAX_SEMANTIC_STEPS",
    "OBSERVATION_SEMANTIC_STEP_SCHEMA",
    "SEMANTIC_STEP_SCHEDULE_SCHEMA",
    "ContactSemanticStep",
    "PhoneStateObservationStep",
    "ScheduledSemanticStep",
    "SemanticStepDisposition",
    "SemanticStepSchedule",
    "SemanticStepScheduleError",
    "SemanticStepType",
    "build_semantic_step_schedule",
]
