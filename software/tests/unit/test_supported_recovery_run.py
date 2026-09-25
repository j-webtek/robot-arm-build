"""Coordinator ordering/fault tests with injected hardware boundaries only."""
from pathlib import Path
import pytest
from rocell.application import supported_recovery_run as run
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError


@pytest.mark.parametrize('fault', ['none', 'baseline', 'prepare', 'send', 'uncertain', 'capture'])
@pytest.mark.parametrize('profile', ['supported', 'six_count', 'observed_pose'])
def test_recovery_trial_never_retries_or_progresses(tmp_path, monkeypatch, fault, profile):
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'runs').mkdir()
    source = Path(__file__).resolve().parents[2] / 'docs/hold-r7-supported-pose-draft.json'
    (tmp_path / 'docs'/source.name).write_bytes(source.read_bytes())
    calls = []
    boot = '11'*16
    def binding(*a, **kw):
        assert kw == ({'revision': 19} if profile == 'six_count' else {})
        return dict(expected_boot=boot, address='127.0.0.1')
    monkeypatch.setattr(run, 'review_recovery_startup', binding)
    extra = {}
    wire_profile = 'six_count' if profile=='observed_pose' else profile
    if profile == 'observed_pose':
        from test_observed_pose_candidate import inputs
        from rocell.application.observed_pose_candidate import draft_settings
        hold, _ = draft_settings(*inputs())
        def observed_binding(*a, **kw):
            assert kw == dict(startup_export='startup', stage_export='stage', installation_export='installed')
            return dict(expected_boot=boot, address='127.0.0.1',
                observed_pose_installation=dict(public_candidate_export='candidate'))
        monkeypatch.setattr(run, 'review_observed_startup', observed_binding)
        monkeypatch.setattr(run, 'recovery_policy_from_candidate', lambda *a:
            dict(schema='rocell.six_count_recovery_policy.v1',hold_policy=hold['hold_policy'],initial_residual_counts=6))
        extra = dict(stage_export_id='stage', installation_export_id='installed')
    def baseline(*a, **kw):
        calls.append('baseline')
        return dict(export_path='baseline', summary=dict(category='TRANSPORT_CAPTURED',
            status=dict(state='FAULT' if fault=='baseline' else 'IDLE', reason='NOT_CONFIGURED',
                        records=0, storage_fault=False)))
    monkeypatch.setattr(run, 'capture_hold_transport', baseline)
    monkeypatch.setattr(run, 'read_pair_capabilities', lambda **kw: calls.append('capabilities'))
    def prepare(*a, **kw):
        calls.append('prepare')
        assert (tmp_path / 'runs/wizard-exports'/f'supported-recovery-trial-{boot}.json').exists()
        return dict(export_path='challenge', report=dict(result=dict(
            category='CHALLENGE_UNCERTAIN' if fault=='prepare' else 'CHALLENGE_RECEIVED', challenge={})))
    monkeypatch.setattr(run, 'request_recovery_challenge', prepare)
    def send(*a, **kw):
        calls.append('send')
        assert kw['profile'] == wire_profile
        assert kw['approved_policy']['initial_residual_counts'] == (6 if wire_profile=='six_count' else 5)
        if profile=='observed_pose':
            assert run.OBSERVED_COMMAND.encode() in a[2].encoded
        if fault=='send': raise OSError('private detail')
        return dict(export_path='delivery', delivery=dict(result='DELIVERY_UNCERTAIN' if fault=='uncertain'
                                                          else 'CONTROLLER_REPORTED_ACCEPTANCE'))
    monkeypatch.setattr(run, 'send_prepared_recovery', send)
    def capture(*a, **kw):
        calls.append('capture')
        assert kw['profile'] == wire_profile
        if fault=='capture': raise OSError('lost capture')
        return dict(export_path='transport', summary=dict(category='TRANSPORT_CAPTURED', records=[]))
    monkeypatch.setattr(run, 'capture_recovery_transport', capture)
    monkeypatch.setattr(run, 'export_recovery', lambda *a, **kw: dict(path='assessment'))
    monkeypatch.setattr(run, 'replay_recovery', lambda *a: dict(category='CONTROLLER_REPORTED_RECOVERY_VERIFIED'))
    def pause(seconds): assert seconds==3;calls.append('pause')
    if fault=='baseline':
        with pytest.raises(ValueError): run.run_supported_recovery(tmp_path, startup_export_id='startup',
            key=b'k'*32, authorized_recovery=True, pause=pause, profile=profile, **extra)
        assert calls==['baseline']
        return
    result = run.run_supported_recovery(tmp_path, startup_export_id='startup', key=b'k'*32,
                                        authorized_recovery=True, pause=pause, profile=profile, **extra)
    assert result['category']==('CONTROLLER_REPORTED_RECOVERY_VERIFIED' if fault=='none' else 'INCONCLUSIVE')
    assert result['retry_allowed'] is result['progression_authority'] is False
    assert calls.count('prepare')==1 and calls.count('send')<=1
    assert 'private detail' not in str(result)
    previous = list(calls)
    with pytest.raises(ValueError): run.run_supported_recovery(tmp_path, startup_export_id='startup',
        key=b'k'*32, authorized_recovery=True, pause=pause, profile=profile, **extra)
    assert calls==previous


def test_missing_approval_stops_before_reading_or_connecting(tmp_path):
    with pytest.raises(ValueError, match='approval'):
        run.run_supported_recovery(tmp_path, startup_export_id='unused', key=b'k'*32)
    assert not list(tmp_path.iterdir())


def test_six_count_missing_installation_stops_before_network(tmp_path, monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail('Network access before installation receipt validation')
    monkeypatch.setattr(run, 'capture_hold_transport', forbidden)
    with pytest.raises(PhysicalOnboardingDurabilityError, match='regular file'):
        run.run_supported_recovery(tmp_path, startup_export_id='not-installed',
            key=b'k'*32, authorized_recovery=True, profile='six_count')
    assert not list(tmp_path.iterdir())


def test_observed_missing_receipts_stops_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(run, 'capture_hold_transport', lambda *a, **kw: pytest.fail('Unexpected hardware access'))
    with pytest.raises(ValueError, match='receipts required'):
        run.run_supported_recovery(tmp_path, startup_export_id='startup', key=b'k'*32,
            authorized_recovery=True, profile='observed_pose')
    assert not list(tmp_path.iterdir())
