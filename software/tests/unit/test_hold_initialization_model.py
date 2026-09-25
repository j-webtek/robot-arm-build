"""Synthetic register snapshots only; these tests cannot access the arm."""
from dataclasses import replace

import pytest

from rocell.application.hold_initialization_model import (
    HoldInitializationModel, Joint, Snapshot,
)


POSITIONS = (2048, 2390, 1727, 2723, 2041, 2042, 2051)


def snapshot(at, *, torque=0, goal=0, position=2723, neighbor=False):
    joints = [Joint(p, 0, 0) for p in POSITIONS]
    joints[3] = Joint(position, goal, torque)
    if neighbor:
        joints[1] = replace(joints[1], torque=1)
    return Snapshot(at, at + 1000, tuple(joints))


def ready(*, enable=False):
    model = HoldInitializationModel(allow_enable=enable)
    model.baseline(snapshot(0), snapshot(110_000), now_us=111_000)
    return model


def test_already_enabled_hold_preserves_torque_without_enable_command():
    model=HoldInitializationModel(allow_enable=True)
    model.baseline(snapshot(0,torque=1,goal=2724),snapshot(110_000,torque=1,goal=2724),now_us=111_000)
    action=model.propose(snapshot(120_000,torque=1,goal=2724),now_us=121_000)
    assert action[1]==41
    model.acknowledge(success=True,finished_us=122_000)
    assert model.observe(snapshot(150_000,torque=1,goal=2723),now_us=151_000)=='SETTLING'
    assert model.observe(snapshot(260_000,torque=1,goal=2723),now_us=261_000)=='AWAIT_EXPORT'
    assert len(model.actions)==1


def test_enabled_goal_mismatch_rejected_before_any_command():
    model=HoldInitializationModel(allow_enable=True)
    with pytest.raises(ValueError):
        model.baseline(snapshot(0,torque=1,goal=2726),snapshot(110_000,torque=1,goal=2726),now_us=111_000)
    assert not model.actions


@pytest.mark.parametrize('residual', [-6, -5, 5, 6])
def test_recovery_residual_does_not_widen_arrival(residual):
    model = HoldInitializationModel(supported_recovery=True)
    scans = [snapshot(t, torque=1, goal=2723+residual) for t in (0, 110_000, 120_000)]
    if abs(residual) > 5:
        with pytest.raises(ValueError): model.baseline(*scans[:2], now_us=111_000)
        assert not model.actions
        return
    model.baseline(*scans[:2], now_us=111_000)
    model.propose(scans[2], now_us=121_000)
    model.acknowledge(success=True, finished_us=122_000)
    with pytest.raises(ValueError):
        model.observe(snapshot(230_000, torque=1, goal=2723, position=2726), now_us=231_000)
    assert len(model.actions) == 1


def test_recovery_never_enables_torque():
    with pytest.raises(ValueError):
        HoldInitializationModel(supported_recovery=True, allow_enable=True)
    model = HoldInitializationModel(supported_recovery=True)
    with pytest.raises(ValueError):
        model.baseline(snapshot(0), snapshot(110_000), now_us=111_000)
    assert not model.actions


def test_unexpected_torque_loss_is_not_automatically_reenabled():
    model=HoldInitializationModel(allow_enable=True)
    model.baseline(snapshot(0,torque=1,goal=2723),snapshot(110_000,torque=1,goal=2723),now_us=111_000)
    model.propose(snapshot(120_000,torque=1,goal=2723),now_us=121_000)
    model.acknowledge(success=True,finished_us=122_000)
    with pytest.raises(ValueError):model.observe(snapshot(150_000,goal=2723),now_us=151_000)
    assert len(model.actions)==1 and model.state=='FAULT'


def hold(*, enable=False):
    model = ready(enable=enable)
    action = model.propose(snapshot(120_000), now_us=121_000)
    assert action == (14, 41, b'\x01\xa3\x0a\x00\x00\x14\x00')
    model.acknowledge(success=True, finished_us=122_000)
    return model


@pytest.mark.parametrize('auto_enable', [True, False])
def test_both_torque_behaviors_reach_partial_exported_result(auto_enable):
    model = hold(enable=not auto_enable)
    if not auto_enable:
        assert model.observe(snapshot(130_000, goal=2723), now_us=131_000) == 'READY_ENABLE'
        assert model.propose(snapshot(140_000, goal=2723), now_us=141_000) == (14, 40, b'\x01')
        model.acknowledge(success=True, finished_us=142_000)
    assert model.observe(snapshot(150_000, torque=1, goal=2723), now_us=151_000) == 'SETTLING'
    assert model.observe(snapshot(260_000, torque=1, goal=2723), now_us=261_000) == 'AWAIT_EXPORT'
    result = model.finish_export(verified=True)
    assert result['action_count'] == (1 if auto_enable else 2)
    assert result['whole_arm_ready'] is result['progression_authority'] is False
    assert model.original.joints[1].position + model.original.joints[2].position == 4117


def test_lost_ack_after_possible_execution_never_retries_or_releases():
    model = ready()
    model.propose(snapshot(120_000), now_us=121_000)
    with pytest.raises(ValueError, match='UNCERTAIN_ACK'):
        model.acknowledge(success=False, finished_us=122_000)
    with pytest.raises(ValueError):
        model.propose(snapshot(130_000, torque=1, goal=2723), now_us=131_000)
    assert len(model.actions) == 1
    assert model.state == 'FAULT'
    assert model.reason == 'UNCERTAIN_ACK'


@pytest.mark.parametrize('scan,now', [
    (snapshot(120_000, position=2726), 121_000),
    (snapshot(120_000, neighbor=True), 121_000),
    (snapshot(120_000), 500_000),
    (snapshot(110_000), 111_000),
    (snapshot(120_000, goal=100), 121_000),
])
def test_bad_prewrite_evidence_prevents_action(scan, now):
    model = ready()
    with pytest.raises(ValueError):
        model.propose(scan, now_us=now)
    assert model.actions == []
    assert model.state == 'FAULT'


@pytest.mark.parametrize('scan', [
    snapshot(130_000, torque=1, goal=0),
    snapshot(130_000, torque=1, goal=2723, position=2730),
    snapshot(130_000, torque=1, goal=2723, neighbor=True),
    snapshot(130_000, torque=0, goal=2723),
])
def test_bad_postwrite_evidence_stops_without_release(scan):
    model = hold()
    with pytest.raises(ValueError):
        model.observe(scan, now_us=131_000)
    assert len(model.actions) == 1
    assert model.state == 'FAULT'


def test_explicit_enable_without_arrival_faults():
    model = hold(enable=True)
    model.observe(snapshot(130_000, goal=2723), now_us=131_000)
    model.propose(snapshot(140_000, goal=2723), now_us=141_000)
    model.acknowledge(success=True, finished_us=142_000)
    with pytest.raises(ValueError):
        model.observe(snapshot(150_000, goal=2723), now_us=151_000)
    assert len(model.actions) == 2


def test_export_failure_retains_partial_state_without_extra_write():
    model = hold()
    model.observe(snapshot(150_000, torque=1, goal=2723), now_us=151_000)
    model.observe(snapshot(260_000, torque=1, goal=2723), now_us=261_000)
    with pytest.raises(ValueError, match='EXPORT_FAILED'):
        model.finish_export(verified=False)
    assert len(model.actions) == 1
    assert model.last.joints[3].torque == 1


def test_mode_change_and_moving_flag_rejected():
    for change in ({'mode': 1}, {'moving': 1}):
        model = ready()
        scan = snapshot(120_000)
        joints = list(scan.joints)
        joints[3] = replace(joints[3], **change)
        with pytest.raises(ValueError):
            model.propose(replace(scan, joints=tuple(joints)), now_us=121_000)
        assert not model.actions


def test_drift_from_seeded_goal_prevents_separate_enable():
    model = ready(enable=True)
    model.propose(snapshot(120_000, position=2725), now_us=121_000)
    model.acknowledge(success=True, finished_us=122_000)
    model.observe(snapshot(130_000, goal=2725, position=2725), now_us=131_000)
    with pytest.raises(ValueError, match='ENABLE_NOT_ELIGIBLE'):
        model.propose(snapshot(140_000, goal=2725, position=2721), now_us=141_000)
    assert len(model.actions) == 1
