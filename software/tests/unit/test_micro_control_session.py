from contextlib import contextmanager
import pytest
from test_micro_command_admission import setup,consume
from rocell.safety import micro_control_session as module
from rocell.application.first_motion_contract import canonical


def build(tmp_path,monkeypatch):
    admission=setup(tmp_path,monkeypatch)
    # Explicit synthetic same-session metadata; no saved hardware evidence used.
    record=admission.snapshot()
    record['predecessor']['dispatch_ns']=700_000_000
    admission._raw=canonical(record)
    (tmp_path/admission._name).write_bytes(admission._raw)
    ticks=[500_000_000];events=[]
    @contextmanager
    def lease():
        events.append('acquired')
        try:yield
        finally:events.append('released')
    session=module.MicroControlSession(lease_factory=lease,clock_ns=lambda:ticks[0])
    return admission,session,ticks,events


def bind(admission,session,ticks):
    ticks[0]=600_000_000;session.predecessor_intent()
    ticks[0]=1_300_000_000;session.bind(admission)


def test_continuous_scope_one_claim_and_release(tmp_path,monkeypatch):
    admission,session,ticks,events=build(tmp_path,monkeypatch)
    with session.scope():
        bind(admission,session,ticks)
        consume(admission);ticks[0]=1_400_000_000
        result=session.claim_staged_boundary(canonical(admission.snapshot()['command']))
        assert events==['acquired'] and result['cooperative_scope_checked']
        assert not result['native_enabled'] and not result['exclusive_external_control_proven']
        with pytest.raises(ValueError):session.claim_staged_boundary(b'')
    assert events==['acquired','released']
    with pytest.raises(ValueError):
        with session.scope():pass


@pytest.mark.parametrize('fault',['old_predecessor','expiry','clock','thread','unconsumed',
                                'payload','cancel','changed_consumption','disk_delay'])
def test_faults_never_yield_native_authority(tmp_path,monkeypatch,fault):
    admission,session,ticks,events=build(tmp_path,monkeypatch)
    with session.scope():
        if fault=='old_predecessor':
            ticks[0]=800_000_000;session.predecessor_intent();ticks[0]=1_300_000_000
            with pytest.raises(ValueError):session.bind(admission)
        else:
            bind(admission,session,ticks)
            if fault!='unconsumed':consume(admission)
            ticks[0]=1_400_000_000
            payload=canonical(admission.snapshot()['command'])
            if fault=='expiry':ticks[0]=2_200_000_001
            if fault=='clock':ticks[0]=1
            if fault=='thread':monkeypatch.setattr(module.threading,'get_ident',lambda:session._thread+1)
            if fault=='payload':payload=b'{}'
            if fault=='changed_consumption':(tmp_path/('a'*32+'-micro-consumed.json')).write_text('{}')
            if fault=='disk_delay':
                original=admission.consumed_receipt
                def slow():
                    receipt=original();ticks[0]=3_000_000_000;return receipt
                monkeypatch.setattr(admission,'consumed_receipt',slow)
            with pytest.raises(ValueError):session.claim_staged_boundary(payload,cancelled=fault=='cancel')
            with pytest.raises(ValueError):session.claim_staged_boundary(payload)
    assert events[-1]=='released'


def test_lease_failure_does_not_open_session():
    @contextmanager
    def unavailable():raise RuntimeError('busy');yield
    session=module.MicroControlSession(lease_factory=unavailable,clock_ns=lambda:1)
    with pytest.raises(RuntimeError):
        with session.scope():pass
    with pytest.raises(ValueError):session.predecessor_intent()


def test_scope_integrates_with_transaction_and_export(tmp_path,monkeypatch):
    from test_micro_transaction_simulation import inputs
    from rocell.application.micro_transaction_simulation import run_simulated_transaction
    admission,session,ticks,events=build(tmp_path,monkeypatch)
    reports=[]
    with session.scope():
        bind(admission,session,ticks);ticks[0]=1_400_000_000
        result=run_simulated_transaction(admission,control_session=session,
                                         export=reports.append,**inputs())
        assert result['status']=='EXPERIMENT_VERIFIED'
        assert result['cooperative_boundary']['cooperative_scope_checked']
        assert result['native_sends']==0 and len(reports)==1
        assert events==['acquired']
    assert events[-1]=='released'
