"""Staged admission tests use synthetic evidence; no hardware or sender."""
import copy
import json
import pytest
from rocell.safety import micro_command_admission as module


def setup(tmp_path, monkeypatch, **changes):
    pose=[0,0,0,0,.0245,0]
    monkeypatch.setattr(module,'predecessor',lambda *a:dict(pose=pose,finished_ns=1_000_000_000))
    monkeypatch.setattr(module,'review_observation',lambda *a:None)
    baseline=dict(status='SUCCEEDED',address=module.ADDRESS,expected_mac=module.MAC,
                  identity_before_matched=True,identity_after_matched=True,cleanup_confirmed=True,
                  request_started_monotonic_s=1.1,response_finished_monotonic_s=1.2,
                  joints_rad=dict(zip(module.JOINTS,pose)))
    baseline.update(changes)
    return module.MicroCommandAdmission(root=tmp_path,attempt_id='a'*32,
        predecessor_path=tmp_path/'predecessor',predecessor_sha256='b'*64,
        baseline=baseline,now_ns=1_300_000_000)


def consume(admission, **changes):
    values=dict(now_ns=1_400_000_000,observed_mac=module.MAC)
    values.update(changes)
    return admission.consume(copy.deepcopy(module.COMMAND),**values)


def test_consumed_intent_is_not_native_authority(tmp_path,monkeypatch):
    admission=setup(tmp_path,monkeypatch)
    result=consume(admission)
    assert not result['native_enabled'] and not result['motion_authorized']
    assert len(list(tmp_path.glob('*-micro-consumed.json')))==1
    assert not hasattr(admission,'claim_native_send')
    with pytest.raises(ValueError):consume(admission)


@pytest.mark.parametrize('changes',[{'cancelled':True},{'observed_mac':'wrong'},
                                   {'now_ns':3_000_000_000},{'now_ns':1}])
def test_failed_consumption_burns_intent(tmp_path,monkeypatch,changes):
    admission=setup(tmp_path,monkeypatch)
    with pytest.raises(ValueError):consume(admission,**changes)
    with pytest.raises(ValueError,match='already consumed'):consume(admission)
    assert not list(tmp_path.glob('*-micro-consumed.json'))


def test_wrong_command_burns_intent(tmp_path,monkeypatch):
    admission=setup(tmp_path,monkeypatch)
    wrong=dict(module.COMMAND,rad=.90)  # Degrees accidentally passed as radians.
    with pytest.raises(ValueError):admission.consume(wrong,now_ns=1_400_000_000,observed_mac=module.MAC)
    with pytest.raises(ValueError):consume(admission)


def test_changed_record_rejected(tmp_path,monkeypatch):
    admission=setup(tmp_path,monkeypatch)
    path=next(tmp_path.glob('*-micro-staged.json'))
    path.write_text('{}')
    with pytest.raises(ValueError,match='changed'):consume(admission)


def test_predecessor_rechecked_before_consume(tmp_path,monkeypatch):
    admission=setup(tmp_path,monkeypatch)
    def reject(*args):raise ValueError('changed predecessor')
    monkeypatch.setattr(module,'predecessor',reject)
    with pytest.raises(ValueError,match='predecessor'):consume(admission)


@pytest.mark.parametrize('changes',[{'identity_before_matched':False},
    {'response_finished_monotonic_s':.1}, {'request_started_monotonic_s':.5},
    {'joints_rad':dict.fromkeys(module.JOINTS,0)}])
def test_invalid_baseline_rejected(tmp_path,monkeypatch,changes):
    with pytest.raises(ValueError):setup(tmp_path,monkeypatch,**changes)


def test_manifest_digest_checked_before_evidence(tmp_path):
    (tmp_path/'manifest.json').write_text('{}')
    with pytest.raises(ValueError,match='integrity'):module.predecessor(tmp_path,'0'*64)
