"""Independent, zero-I/O observation of virtual contact outcomes.

The device truth model resolves an achieved contact into a :class:`ContactResult`.
This module is deliberately downstream of that decision: it receives no action
plan, planned target, expected character, or semantic profile.  It observes the
resolved in-memory output exactly once and exposes only hashes and lengths in
serializable evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Any, Mapping

from .virtual_workcell import (
    ContactDisposition,
    ContactResult,
    VirtualResourceLimitError,
    VirtualValidationError,
)


MAX_VIRTUAL_OUTCOME_RESULTS = 100_000
MAX_VIRTUAL_OUTCOME_CODEPOINTS = 1_000_000

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _name(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VirtualValidationError(f"{label} must be non-empty text")
    parsed = value.strip()
    if len(parsed) > maximum:
        raise VirtualValidationError(f"{label} exceeds {maximum} characters")
    if any(ord(character) < 32 for character in parsed):
        raise VirtualValidationError(f"{label} contains a control character")
    return parsed


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VirtualValidationError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise VirtualValidationError(
            f"{label} must be within [{minimum}, {maximum}]"
        )
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise VirtualValidationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _stable_hash(value: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise VirtualValidationError(
            f"virtual outcome evidence is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _authority() -> dict[str, object]:
    return {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
        "live_motion_authorized": False,
        "contact_authorized": False,
    }


@dataclass(frozen=True, slots=True)
class VirtualTextOutcomeSnapshot:
    """Immutable, redacted observer state suitable for evidence serialization."""

    observer_id: str
    definition_hash: str
    result_hashes: tuple[str, ...]
    action_indices: tuple[int, ...]
    dispositions: tuple[ContactDisposition, ...]
    accepted_activation_count: int
    output_sha256: str
    output_length: int
    maximum_results: int
    maximum_output_codepoints: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "observer_id", _name(self.observer_id, "observer id"))
        object.__setattr__(
            self,
            "definition_hash",
            _digest(self.definition_hash, "observer definition hash"),
        )
        result_hashes = tuple(
            _digest(value, "observed contact result hash")
            for value in self.result_hashes
        )
        action_indices = tuple(
            _integer(
                value,
                "observed action index",
                maximum=1_000_000_000,
            )
            for value in self.action_indices
        )
        dispositions: list[ContactDisposition] = []
        for value in self.dispositions:
            if isinstance(value, ContactDisposition):
                dispositions.append(value)
                continue
            try:
                dispositions.append(ContactDisposition(value))
            except (TypeError, ValueError) as exc:
                raise VirtualValidationError(
                    "outcome snapshot contains an unsupported disposition"
                ) from exc
        if not len(result_hashes) == len(action_indices) == len(dispositions):
            raise VirtualValidationError(
                "outcome snapshot result, action, and disposition counts differ"
            )
        if len(result_hashes) != len(set(result_hashes)):
            raise VirtualValidationError(
                "outcome snapshot contact results must be consumed exactly once"
            )
        if any(
            current <= previous
            for previous, current in zip(action_indices, action_indices[1:])
        ):
            raise VirtualValidationError(
                "outcome snapshot action indices must increase strictly"
            )
        maximum_results = _integer(
            self.maximum_results,
            "maximum outcome results",
            minimum=1,
            maximum=MAX_VIRTUAL_OUTCOME_RESULTS,
        )
        maximum_output = _integer(
            self.maximum_output_codepoints,
            "maximum outcome codepoints",
            minimum=1,
            maximum=MAX_VIRTUAL_OUTCOME_CODEPOINTS,
        )
        if len(result_hashes) > maximum_results:
            raise VirtualValidationError("outcome snapshot exceeds its result bound")
        accepted_count = _integer(
            self.accepted_activation_count,
            "accepted outcome activation count",
            maximum=MAX_VIRTUAL_OUTCOME_CODEPOINTS,
        )
        output_length = _integer(
            self.output_length,
            "outcome output length",
            maximum=MAX_VIRTUAL_OUTCOME_CODEPOINTS,
        )
        if output_length > maximum_output:
            raise VirtualValidationError("outcome snapshot exceeds its output bound")
        if accepted_count != output_length:
            raise VirtualValidationError(
                "accepted activation count must equal observed output length"
            )
        expected_definition_hash = _stable_hash(
            {
                "schema": "rocell.virtual_text_outcome_observer_definition.v1",
                "observer_id": self.observer_id,
                "maximum_results": maximum_results,
                "maximum_output_codepoints": maximum_output,
                "input_contract": "CONTACT_RESULT_ONLY",
                "authority": _authority(),
            }
        )
        if not hmac.compare_digest(self.definition_hash, expected_definition_hash):
            raise VirtualValidationError(
                "outcome snapshot definition hash does not match its observer bounds"
            )
        object.__setattr__(self, "result_hashes", result_hashes)
        object.__setattr__(self, "action_indices", action_indices)
        object.__setattr__(self, "dispositions", tuple(dispositions))
        object.__setattr__(self, "maximum_results", maximum_results)
        object.__setattr__(self, "maximum_output_codepoints", maximum_output)
        object.__setattr__(self, "accepted_activation_count", accepted_count)
        object.__setattr__(self, "output_length", output_length)
        object.__setattr__(
            self,
            "output_sha256",
            _digest(self.output_sha256, "outcome output hash"),
        )

    @property
    def result_count(self) -> int:
        return len(self.result_hashes)

    @property
    def last_action_index(self) -> int | None:
        return self.action_indices[-1] if self.action_indices else None

    @property
    def snapshot_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_text_outcome_snapshot.v1",
            "observer_id": self.observer_id,
            "definition_hash": self.definition_hash,
            "result_count": self.result_count,
            "result_hashes": list(self.result_hashes),
            "action_indices": list(self.action_indices),
            "dispositions": [value.value for value in self.dispositions],
            "accepted_activation_count": self.accepted_activation_count,
            "output_sha256": self.output_sha256,
            "output_length": self.output_length,
            "maximum_results": self.maximum_results,
            "maximum_output_codepoints": self.maximum_output_codepoints,
            "raw_output_serialized": False,
            "input_contract": "CONTACT_RESULT_ONLY",
            "authority": _authority(),
        }


class VirtualTextOutcomeObserver:
    """Consume contact truth once and independently accumulate observed text."""

    __slots__ = (
        "_observer_id",
        "_maximum_results",
        "_maximum_output_codepoints",
        "_definition_hash",
        "_output",
        "_result_hashes",
        "_action_indices",
        "_dispositions",
        "_accepted_activation_count",
        "_seen_result_hashes",
    )

    def __init__(
        self,
        *,
        observer_id: str,
        maximum_results: int = 10_000,
        maximum_output_codepoints: int = 100_000,
    ) -> None:
        self._observer_id = _name(observer_id, "observer id")
        self._maximum_results = _integer(
            maximum_results,
            "maximum outcome results",
            minimum=1,
            maximum=MAX_VIRTUAL_OUTCOME_RESULTS,
        )
        self._maximum_output_codepoints = _integer(
            maximum_output_codepoints,
            "maximum outcome codepoints",
            minimum=1,
            maximum=MAX_VIRTUAL_OUTCOME_CODEPOINTS,
        )
        self._definition_hash = _stable_hash(
            {
                "schema": "rocell.virtual_text_outcome_observer_definition.v1",
                "observer_id": self._observer_id,
                "maximum_results": self._maximum_results,
                "maximum_output_codepoints": self._maximum_output_codepoints,
                "input_contract": "CONTACT_RESULT_ONLY",
                "authority": _authority(),
            }
        )
        self._output = ""
        self._result_hashes: list[str] = []
        self._action_indices: list[int] = []
        self._dispositions: list[ContactDisposition] = []
        self._accepted_activation_count = 0
        self._seen_result_hashes: set[str] = set()

    @property
    def observer_id(self) -> str:
        return self._observer_id

    @property
    def definition_hash(self) -> str:
        return self._definition_hash

    @property
    def observed_output(self) -> str:
        """Return plaintext to in-process verification; never serialize it."""

        return self._output

    @property
    def output_sha256(self) -> str:
        return hashlib.sha256(self._output.encode("utf-8")).hexdigest()

    @property
    def output_length(self) -> int:
        return len(self._output)

    @property
    def result_count(self) -> int:
        return len(self._result_hashes)

    @property
    def last_action_index(self) -> int | None:
        return self._action_indices[-1] if self._action_indices else None

    @property
    def snapshot(self) -> VirtualTextOutcomeSnapshot:
        return VirtualTextOutcomeSnapshot(
            observer_id=self.observer_id,
            definition_hash=self.definition_hash,
            result_hashes=tuple(self._result_hashes),
            action_indices=tuple(self._action_indices),
            dispositions=tuple(self._dispositions),
            accepted_activation_count=self._accepted_activation_count,
            output_sha256=self.output_sha256,
            output_length=self.output_length,
            maximum_results=self._maximum_results,
            maximum_output_codepoints=self._maximum_output_codepoints,
        )

    @property
    def state_hash(self) -> str:
        return self.snapshot.snapshot_hash

    def consume(self, result: ContactResult) -> VirtualTextOutcomeSnapshot:
        """Observe one immutable result atomically and return a redacted snapshot."""

        if not isinstance(result, ContactResult):
            raise TypeError("result must be a ContactResult")
        result_hash = result.result_hash
        if result_hash in self._seen_result_hashes:
            raise VirtualValidationError(
                "contact result must be consumed exactly once"
            )
        if (
            self.last_action_index is not None
            and result.action_index <= self.last_action_index
        ):
            raise VirtualValidationError(
                "observed contact action indices must increase strictly"
            )
        if self.result_count >= self._maximum_results:
            raise VirtualResourceLimitError(
                f"virtual outcome observer reached {self._maximum_results} results"
            )
        emitted_output = result.emitted_output
        if self.output_length > self._maximum_output_codepoints - len(emitted_output):
            raise VirtualResourceLimitError(
                "virtual outcome observer would exceed its output bound"
            )
        # All checks precede the state mutation so a rejected observation leaves
        # the prior evidence hash and in-memory plaintext unchanged.
        self._result_hashes.append(result_hash)
        self._action_indices.append(result.action_index)
        self._dispositions.append(result.disposition)
        self._seen_result_hashes.add(result_hash)
        self._output += emitted_output
        self._accepted_activation_count += result.activation_count
        return self.snapshot

    def output_matches(self, expected_sha256: str, expected_length: int) -> bool:
        """Compare redacted expected output in constant-time hash form plus length."""

        digest = _digest(expected_sha256, "expected outcome output hash")
        length = _integer(
            expected_length,
            "expected outcome output length",
            maximum=MAX_VIRTUAL_OUTCOME_CODEPOINTS,
        )
        return self.output_length == length and hmac.compare_digest(
            self.output_sha256,
            digest,
        )

    def to_dict(self) -> dict[str, object]:
        return self.snapshot.to_dict()


__all__ = [
    "MAX_VIRTUAL_OUTCOME_CODEPOINTS",
    "MAX_VIRTUAL_OUTCOME_RESULTS",
    "VirtualTextOutcomeObserver",
    "VirtualTextOutcomeSnapshot",
]
