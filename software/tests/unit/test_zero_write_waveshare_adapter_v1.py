from __future__ import annotations

from dataclasses import replace

import pytest

from rocell.application.zero_write_waveshare_adapter_v1 import (
    WaveshareT102EncodingProfileV1,
    ZeroWriteEncodingPermitV1,
    ZeroWriteWaveshareAdapterError,
    ZeroWriteWaveshareAdapterV1,
    issue_zero_write_encoding_permit_v1,
    trajectory_limits_sha256,
)
from rocell.application.trajectory_execution_envelope_v2 import (
    bind_trajectory_execution_envelope_v2,
)

import test_trajectory_execution_envelope_v2 as env


def _envelope():
    batch, report = env._planner_inputs()
    report = env._synthetic_ready(report)
    inner = env._inner(
        batch.batch_sha256, report["derived_v1_surrogate_sha256"],
        report["measured_planner_gate_sha256"])
    return bind_trajectory_execution_envelope_v2(
        batch, batch.proposals[0], report, inner)


def _profile(envelope, **changes):
    values = dict(
        profile_id="waveshare-t102-offline-preview-v1",
        vendor_source_sha256="1" * 64,
        controller_joint_mapping_sha256="2" * 64,
        expected_trajectory_limits_sha256=trajectory_limits_sha256(envelope),
        controller_session_id=envelope.measured_envelope.controller_session_id,
        configuration_epoch_sha256=(
            envelope.measured_envelope.configuration_epoch_sha256),
        fixed_gripper_rad=0.25,
        speed=20,
        acceleration=1,
    )
    values.update(changes)
    return WaveshareT102EncodingProfileV1(**values)


def _permit(envelope, profile, *, issued=10, expires=2_000_000_000):
    return issue_zero_write_encoding_permit_v1(
        envelope, profile, issued_monotonic_ns=issued,
        expires_monotonic_ns=expires)


def test_exact_t102_preview_is_hash_bound_reviewable_and_zero_write():
    envelope = _envelope()
    profile = _profile(envelope)
    permit = _permit(envelope, profile)
    adapter = ZeroWriteWaveshareAdapterV1()

    receipt = adapter.preview(
        envelope, permit, profile, now_monotonic_ns=100)
    document = receipt.to_dict()

    assert permit.consumed is True
    assert document["command_count"] == 1
    assert document["commands"][0]["waypoint_sequence"] == 1
    assert document["commands"][0]["time_from_start_ns"] == 1_000_000_000
    assert document["commands"][0]["scheduled_dispatch_monotonic_ns"] == (
        1_000_000_100)
    assert document["commands"][0]["payload_utf8"] == (
        '{"T":102,"base":0.1,"shoulder":0.1,"elbow":0.1,'
        '"wrist":0.1,"roll":0.1,"hand":0.25,"spd":20,"acc":1}\n')
    assert document["transport_opened"] is False
    assert document["transport_write_count"] == 0
    assert document["submitted_bytes"] == []
    assert document["acknowledgements"] == []
    assert document["feedback_samples"] == []
    assert document["automatic_retry"] is False
    assert document["hardware_access"] is document["physical_authority"] is False
    assert len(document["receipt_sha256"]) == 64


def test_observed_start_is_not_encoded_as_a_motion_command():
    envelope = _envelope()
    profile = _profile(envelope)
    receipt = ZeroWriteWaveshareAdapterV1().preview(
        envelope, _permit(envelope, profile), profile,
        now_monotonic_ns=100)
    assert [item.waypoint_sequence for item in receipt.commands] == [1]


def test_permit_is_single_use_and_failed_replay_has_no_retry():
    envelope = _envelope()
    profile = _profile(envelope)
    permit = _permit(envelope, profile)
    adapter = ZeroWriteWaveshareAdapterV1()
    adapter.preview(envelope, permit, profile, now_monotonic_ns=100)
    with pytest.raises(ZeroWriteWaveshareAdapterError, match="already consumed"):
        adapter.preview(envelope, permit, profile, now_monotonic_ns=101)


def test_duplicate_correlation_is_rejected_with_a_fresh_permit():
    envelope = _envelope()
    profile = _profile(envelope)
    adapter = ZeroWriteWaveshareAdapterV1()
    adapter.preview(
        envelope, _permit(envelope, profile), profile, now_monotonic_ns=100)
    second = _permit(envelope, profile, issued=11)
    with pytest.raises(ZeroWriteWaveshareAdapterError, match="already previewed"):
        adapter.preview(envelope, second, profile, now_monotonic_ns=101)
    assert second.consumed is True


def test_expired_permit_is_consumed_and_rejected_before_encoding():
    envelope = _envelope()
    profile = _profile(envelope)
    permit = _permit(envelope, profile, expires=200)
    with pytest.raises(ZeroWriteWaveshareAdapterError, match="not current"):
        ZeroWriteWaveshareAdapterV1().preview(
            envelope, permit, profile, now_monotonic_ns=200)
    assert permit.consumed is True


def test_altered_envelope_does_not_match_exact_permit():
    envelope = _envelope()
    profile = _profile(envelope)
    permit = _permit(envelope, profile)
    altered_inner = replace(
        envelope.measured_envelope, deadline_monotonic_ns=2_900_000_000)
    altered = replace(envelope, measured_envelope=altered_inner)
    with pytest.raises(ZeroWriteWaveshareAdapterError, match="binding differs"):
        ZeroWriteWaveshareAdapterV1().preview(
            altered, permit, profile, now_monotonic_ns=100)


@pytest.mark.parametrize(("change", "message"), [
    ({"controller_session_id": "other-session"}, "controller session"),
    ({"configuration_epoch_sha256": "f" * 64}, "controller session"),
    ({"expected_trajectory_limits_sha256": "e" * 64}, "limits"),
])
def test_uncommissioned_profile_bindings_fail_closed(change, message):
    envelope = _envelope()
    profile = _profile(envelope, **change)
    permit = _permit(envelope, profile)
    with pytest.raises(ZeroWriteWaveshareAdapterError, match=message):
        ZeroWriteWaveshareAdapterV1().preview(
            envelope, permit, profile, now_monotonic_ns=100)


def test_schedule_that_would_outlive_envelope_is_rejected_without_write():
    envelope = _envelope()
    profile = _profile(envelope)
    permit = _permit(envelope, profile, issued=1_900_000_000,
                     expires=2_500_000_000)
    with pytest.raises(ZeroWriteWaveshareAdapterError, match="deadline"):
        ZeroWriteWaveshareAdapterV1().preview(
            envelope, permit, profile, now_monotonic_ns=2_000_000_001)


def test_preview_permit_cannot_be_constructed_by_a_caller():
    envelope = _envelope()
    profile = _profile(envelope)
    with pytest.raises(ZeroWriteWaveshareAdapterError, match="factory"):
        ZeroWriteEncodingPermitV1(
            _issuer=object(), envelope_v2_sha256=envelope.envelope_v2_sha256,
            encoding_profile_sha256=profile.profile_sha256,
            correlation_id=envelope.measured_envelope.correlation_id,
            controller_session_id=(
                envelope.measured_envelope.controller_session_id),
            issued_monotonic_ns=10, expires_monotonic_ns=100)


@pytest.mark.parametrize("change", [
    {"interpolation_mode": "FIRMWARE_INTERPOLATION"},
    {"gripper_behavior": "MODEL_CONTROLLED"},
    {"speed": 0},
    {"acceleration": 0},
])
def test_unsupported_semantics_are_rejected_at_profile_construction(change):
    with pytest.raises(ValueError):
        _profile(_envelope(), **change)
