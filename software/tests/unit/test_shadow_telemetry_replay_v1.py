from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest

from rocell.application.shadow_telemetry_replay_v1 import (
    ShadowTelemetryPolicyV1,
    ShadowTelemetryReplayError,
    ShadowTelemetrySampleV1,
    assess_shadow_telemetry_replay_v1,
)

import test_zero_write_waveshare_adapter_v1 as preview_fixture


ROOT = Path(__file__).resolve().parents[3]


def _preview():
    envelope = preview_fixture._envelope()
    profile = preview_fixture._profile(envelope)
    return preview_fixture.ZeroWriteWaveshareAdapterV1().preview(
        envelope, preview_fixture._permit(envelope, profile), profile,
        now_monotonic_ns=100,
    )


def _wire(value: float = 0.1, *, hand: float = 0.25) -> bytes:
    return json.dumps({
        "T": 1051,
        "b": value,
        "s": value,
        "e": value,
        "t": value,
        "r": value,
        "g": hand,
    }, separators=(",", ":")).encode("utf-8") + b"\n"


def _sample(preview, captured: int, *, wire: bytes | None = None,
            correlation: str | None = None, session: str | None = None,
            sequence: int = 1) -> ShadowTelemetrySampleV1:
    return ShadowTelemetrySampleV1(
        correlation_id=correlation or preview.correlation_id,
        controller_session_id=session or preview.controller_session_id,
        waypoint_sequence=sequence,
        captured_monotonic_ns=captured,
        response_bytes=wire or _wire(),
    )


def test_exact_preview_and_settled_replay_pass_without_authority():
    preview = _preview()
    dispatch = preview.commands[0].scheduled_dispatch_monotonic_ns
    report = assess_shadow_telemetry_replay_v1(
        preview,
        (_sample(preview, dispatch + 100), _sample(preview, dispatch + 200)),
        origin="SYNTHETIC",
    )

    assert report["status"] == "SIMULATION_REPLAY_PASS"
    assert report["all_waypoints_settled_in_replay"] is True
    assert report["waypoints"][0]["consecutive_settled_samples"] == 2
    assert report["waypoints"][0]["final_signed_joint_residual_rad"] == [
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    ]
    assert report["physical_arrival_proven"] is False
    assert report["independent_visual_outcome_proven"] is False
    assert report["transport_opened"] is False
    assert report["transport_write_count"] == 0
    assert report["execution_authorized"] is False
    assert report["hardware_access"] is report["physical_authority"] is False
    schema = json.loads((
        ROOT / "software/ai/schemas/shadow_telemetry_replay_v1.schema.json"
    ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(report)


def test_out_of_tolerance_replay_is_unverified_not_a_false_pass():
    preview = _preview()
    dispatch = preview.commands[0].scheduled_dispatch_monotonic_ns
    samples = (
        _sample(preview, dispatch + 100, wire=_wire(0.2)),
        _sample(preview, dispatch + 200, wire=_wire(0.2)),
    )
    report = assess_shadow_telemetry_replay_v1(
        preview, samples, origin="SYNTHETIC")
    assert report["status"] == "SIMULATION_REPLAY_UNVERIFIED"
    assert report["waypoints"][0]["settled"] is False
    assert report["waypoints"][0]["maximum_absolute_joint_residual_rad"] == (
        pytest.approx(0.1))


@pytest.mark.parametrize(("change", "message"), [
    ({"correlation": "crossed-correlation"}, "different correlation"),
    ({"session": "crossed-session"}, "different controller session"),
    ({"sequence": 99}, "unknown waypoint"),
    ({"wire": b'{"T":1051,"b":0.1}\n'}, "complete six-joint"),
    ({"wire": b'not-json\n'}, "valid T=1051"),
])
def test_crossed_or_malformed_replay_fails_closed(change, message):
    preview = _preview()
    dispatch = preview.commands[0].scheduled_dispatch_monotonic_ns
    with pytest.raises(ShadowTelemetryReplayError, match=message):
        assess_shadow_telemetry_replay_v1(
            preview, (_sample(preview, dispatch + 100, **change),),
            origin="SYNTHETIC",
        )


def test_pre_dispatch_stale_and_nonmonotonic_samples_fail_closed():
    preview = _preview()
    dispatch = preview.commands[0].scheduled_dispatch_monotonic_ns
    with pytest.raises(ShadowTelemetryReplayError, match="predates"):
        assess_shadow_telemetry_replay_v1(
            preview, (_sample(preview, dispatch - 1),), origin="SYNTHETIC")
    with pytest.raises(ShadowTelemetryReplayError, match="globally increasing"):
        assess_shadow_telemetry_replay_v1(
            preview,
            (_sample(preview, dispatch + 200), _sample(preview, dispatch + 100)),
            origin="SYNTHETIC",
        )
    policy = ShadowTelemetryPolicyV1(maximum_sample_lag_ns=50)
    with pytest.raises(ShadowTelemetryReplayError, match="freshness"):
        assess_shadow_telemetry_replay_v1(
            preview, (_sample(preview, dispatch + 51),),
            origin="SYNTHETIC", policy=policy,
        )


def test_feedback_after_next_command_cannot_be_attributed_to_prior_waypoint():
    preview = _preview()
    first = preview.commands[0]
    second = replace(
        first,
        waypoint_sequence=2,
        time_from_start_ns=first.time_from_start_ns + 1_000,
        scheduled_dispatch_monotonic_ns=(
            first.scheduled_dispatch_monotonic_ns + 1_000),
    )
    multi = replace(preview, commands=(first, second))
    with pytest.raises(ShadowTelemetryReplayError, match="ambiguous"):
        assess_shadow_telemetry_replay_v1(
            multi,
            (_sample(multi, second.scheduled_dispatch_monotonic_ns,
                     sequence=1),),
            origin="SYNTHETIC",
        )


def test_noncanonical_or_empty_preview_fails_closed():
    preview = _preview()
    with pytest.raises(ShadowTelemetryReplayError, match="no command"):
        assess_shadow_telemetry_replay_v1(
            replace(preview, commands=()), (), origin="SYNTHETIC")
    broken = replace(
        preview.commands[0],
        wire_bytes=b'{"T":102,"base":999}\n',
    )
    with pytest.raises(ShadowTelemetryReplayError, match="canonical T=102"):
        assess_shadow_telemetry_replay_v1(
            replace(preview, commands=(broken,)), (), origin="SYNTHETIC")


def test_retained_export_is_explicitly_bound_and_still_not_physical_proof():
    preview = _preview()
    dispatch = preview.commands[0].scheduled_dispatch_monotonic_ns
    with pytest.raises(ShadowTelemetryReplayError, match="source_export_sha256"):
        assess_shadow_telemetry_replay_v1(
            preview, (_sample(preview, dispatch + 100),),
            origin="RETAINED_EXPORT",
        )
    report = assess_shadow_telemetry_replay_v1(
        preview,
        (_sample(preview, dispatch + 100), _sample(preview, dispatch + 200)),
        origin="RETAINED_EXPORT", source_export_sha256="a" * 64,
    )
    assert report["source_export_sha256"] == "a" * 64
    assert report["physical_arrival_proven"] is False


def test_identical_inputs_produce_identical_report_hash():
    preview = _preview()
    dispatch = preview.commands[0].scheduled_dispatch_monotonic_ns
    samples = (
        _sample(preview, dispatch + 100), _sample(preview, dispatch + 200),
    )
    first = assess_shadow_telemetry_replay_v1(
        preview, samples, origin="SYNTHETIC")
    second = assess_shadow_telemetry_replay_v1(
        preview, samples, origin="SYNTHETIC")
    assert first == second
