from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import inspect

import pytest

from rocell.simulation.virtual_outcome import (
    VirtualTextOutcomeObserver,
    VirtualTextOutcomeSnapshot,
)
from rocell.simulation.virtual_workcell import (
    ContactDisposition,
    ContactResult,
    VirtualResourceLimitError,
    VirtualValidationError,
)


_MODEL_HASH = "1" * 64


def _accepted(
    action_index: int,
    output: str,
    *,
    activations: int = 1,
) -> ContactResult:
    return ContactResult(
        action_index=action_index,
        disposition=ContactDisposition.ACCEPTED,
        activation_count=activations,
        model_definition_hash=_MODEL_HASH,
        resolved_target_id=f"TRUTH_REGION_{action_index}",
        contact_depth_mm=1.0,
        normal_angle_deg=0.0,
        resolved_output=output,
    )


def _missed(action_index: int) -> ContactResult:
    return ContactResult(
        action_index=action_index,
        disposition=ContactDisposition.MISSED_CONTACT,
        activation_count=0,
        model_definition_hash=_MODEL_HASH,
        resolved_target_id=f"TRUTH_REGION_{action_index}",
        contact_depth_mm=1.0,
        normal_angle_deg=0.0,
    )


def test_observer_consumes_results_without_plan_or_expected_output_inputs() -> None:
    observer = VirtualTextOutcomeObserver(observer_id="keyboard-output-observer")
    observer.consume(_accepted(0, "a"))
    observer.consume(_accepted(2, "b", activations=2))
    snapshot = observer.consume(_missed(3))

    assert observer.observed_output == "abb"
    expected_hash = hashlib.sha256(b"abb").hexdigest()
    assert observer.output_matches(expected_hash, 3)
    assert not observer.output_matches(hashlib.sha256(b"abc").hexdigest(), 3)
    assert not observer.output_matches(expected_hash, 2)
    assert snapshot.result_count == 3
    assert snapshot.action_indices == (0, 2, 3)
    assert snapshot.accepted_activation_count == 3
    assert snapshot.last_action_index == 3
    assert len(snapshot.snapshot_hash) == 64
    assert snapshot.definition_hash == observer.definition_hash

    consume_parameters = set(inspect.signature(observer.consume).parameters)
    assert consume_parameters == {"result"}
    with pytest.raises(TypeError):
        observer.consume(  # type: ignore[call-arg]
            result=_accepted(4, "x"),
            expected_character="x",
            planned_target_id="KEY_X",
        )


def test_snapshot_is_immutable_and_serializes_hashes_and_lengths_only() -> None:
    observer = VirtualTextOutcomeObserver(observer_id="redacted-observer")
    snapshot = observer.consume(_accepted(0, "s"))
    document = snapshot.to_dict()

    assert isinstance(snapshot, VirtualTextOutcomeSnapshot)
    with pytest.raises(FrozenInstanceError):
        snapshot.output_length = 99  # type: ignore[misc]
    assert document["output_sha256"] == hashlib.sha256(b"s").hexdigest()
    assert document["output_length"] == 1
    assert document["raw_output_serialized"] is False
    assert document["input_contract"] == "CONTACT_RESULT_ONLY"
    assert document["authority"]["hardware_commands_generated"] == 0  # type: ignore[index]
    assert "observed_output" not in document
    assert "resolved_output" not in document
    assert "expected" not in document
    assert document["output_sha256"] != "s"


def test_observer_enforces_exact_once_and_strictly_increasing_actions_atomically() -> None:
    observer = VirtualTextOutcomeObserver(observer_id="ordered-observer")
    first = _accepted(4, "a")
    observer.consume(first)
    before_hash = observer.state_hash
    before_output = observer.observed_output

    with pytest.raises(VirtualValidationError, match="exactly once"):
        observer.consume(first)
    assert observer.state_hash == before_hash
    assert observer.observed_output == before_output

    with pytest.raises(VirtualValidationError, match="increase strictly"):
        observer.consume(_accepted(3, "b"))
    assert observer.state_hash == before_hash
    assert observer.observed_output == before_output


def test_observer_resource_bounds_fail_before_mutation() -> None:
    observer = VirtualTextOutcomeObserver(
        observer_id="bounded-observer",
        maximum_results=1,
        maximum_output_codepoints=2,
    )
    observer.consume(_accepted(0, "a", activations=2))
    before_hash = observer.state_hash
    with pytest.raises(VirtualResourceLimitError, match="results"):
        observer.consume(_accepted(1, "b"))
    assert observer.state_hash == before_hash
    assert observer.observed_output == "aa"

    output_bounded = VirtualTextOutcomeObserver(
        observer_id="output-bounded-observer",
        maximum_results=2,
        maximum_output_codepoints=1,
    )
    before_empty = output_bounded.state_hash
    with pytest.raises(VirtualResourceLimitError, match="output bound"):
        output_bounded.consume(_accepted(0, "a", activations=2))
    assert output_bounded.state_hash == before_empty
    assert output_bounded.observed_output == ""


def test_observer_rejects_non_results_and_invalid_expected_digests() -> None:
    observer = VirtualTextOutcomeObserver(observer_id="strict-observer")
    with pytest.raises(TypeError, match="ContactResult"):
        observer.consume("a")  # type: ignore[arg-type]
    with pytest.raises(VirtualValidationError, match="SHA-256"):
        observer.output_matches("not-a-digest", 0)

    valid = observer.snapshot
    with pytest.raises(VirtualValidationError, match="definition hash"):
        VirtualTextOutcomeSnapshot(
            observer_id=valid.observer_id,
            definition_hash="f" * 64,
            result_hashes=valid.result_hashes,
            action_indices=valid.action_indices,
            dispositions=valid.dispositions,
            accepted_activation_count=valid.accepted_activation_count,
            output_sha256=valid.output_sha256,
            output_length=valid.output_length,
            maximum_results=valid.maximum_results,
            maximum_output_codepoints=valid.maximum_output_codepoints,
        )
