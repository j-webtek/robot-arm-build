"""Original-shaped synthetic result sections, with no device or process calls."""

from copy import deepcopy
import pytest

from rocell.providers.windows.native_camera_activation_observation import (
    validate_activation_observation,
    SCHEMA,
)
from test_native_camera_activation_expectation import build, enrollment


def fixture():
    model = enrollment()
    expected = build(model)
    metadata = deepcopy(model.export_snapshot()["identity_packet"]["receipt"])
    metadata["limits"].update(duration_ms=4500, max_parent_nodes=16)
    return expected, dict(
        schema=SCHEMA,
        expected_identity_sha256=expected.sha256,
        original_identity_sha256=expected.to_dict()["original_identity_sha256"],
        native_started_ms=1000,
        native_deadline_ms=6000,
        attempted=True,
        resolution_attempted=True,
        resolution_returned=True,
        activation_callback_entered=True,
        observation_started_ms=1500,
        observation_returned_ms=1510,
        comparison="MATCH",
        metadata=metadata,
    )


def validate(raw, expected, *, attempts=1, opened=1, status="OK"):
    return validate_activation_observation(
        raw,
        expected,
        source_activation_attempts=attempts,
        source_opened=opened,
        native_status=status,
    )


def test_original_identity_is_independently_compared_and_inputs_unchanged():
    expected, raw = fixture()
    saved = deepcopy(raw)
    result = validate(raw, expected)
    assert result.independently_matches is True and result.metadata is not None
    assert result.metadata.api_calls == raw["metadata"]["api_calls"]
    assert raw == saved


@pytest.mark.parametrize(
    "section,field",
    [
        ("device", "instance_id"),
        ("device", "container_id"),
        ("driver", "provider"),
        ("driver", "service"),
        ("driver", "version"),
        ("driver", "inf_path"),
    ],
)
def test_child_match_flag_cannot_substitute_for_observed_identity(section, field):
    expected, raw = fixture()
    raw["metadata"][section][field]["value"] = (
        "ffffffff-2222-3333-4444-555555555555" if field == "container_id" else "CHANGED"
    )
    with pytest.raises(ValueError):
        validate(raw, expected)
    raw.update(
        comparison=(
            ("CONTAINER_CHANGED" if field == "container_id" else "INSTANCE_CHANGED")
            if section == "device"
            else "DRIVER_CHANGED"
        ),
        activation_callback_entered=False,
    )
    result = validate(raw, expected, attempts=0, opened=0, status="FAILED")
    assert result.independently_matches is False


@pytest.mark.parametrize(
    "mutation",
    [
        dict(native_started_ms=True),
        dict(native_deadline_ms=6001),
        dict(observation_started_ms=5901),
        dict(observation_returned_ms=6000),
        dict(observation_returned_ms=1499),
        dict(attempted=1),
        dict(resolution_attempted=False),
        dict(resolution_returned=False),
        dict(comparison="DRIVER_CHANGED"),
        dict(comparison=None),
        dict(original_identity_sha256="f" * 64),
        dict(expected_identity_sha256="f" * 64),
        dict(physical_authority=True),
    ],
)
def test_closed_freshness_and_observation_contract(mutation):
    expected, raw = fixture()
    raw.update(mutation)
    with pytest.raises(ValueError):
        validate(raw, expected)


@pytest.mark.parametrize(
    "boundary",
    ["not-started", "before-query", "query-threw", "late-return", "callback-only"],
)
def test_incomplete_observations_stay_diagnostic_not_zero_activity_success(boundary):
    expected, raw = fixture()
    if boundary in {"not-started", "before-query", "query-threw"}:
        raw.update(
            attempted=boundary != "not-started",
            resolution_attempted=boundary == "query-threw",
            resolution_returned=False,
            metadata=None,
            observation_started_ms=1500 if boundary == "query-threw" else None,
            observation_returned_ms=None,
            comparison=None,
            activation_callback_entered=False,
        )
    elif boundary == "late-return":
        raw.update(
            observation_returned_ms=None,
            comparison=None,
            activation_callback_entered=False,
        )
    result = validate(raw, expected, attempts=0, opened=0, status="FAILED")
    assert result.resolution_attempted == raw["resolution_attempted"]
    if boundary == "query-threw":
        assert result.metadata is None and result.resolution_returned is False
    with pytest.raises(ValueError):
        validate(raw, expected, attempts=0, opened=0, status="OK")
