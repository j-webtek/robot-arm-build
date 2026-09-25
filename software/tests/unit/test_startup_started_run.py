from pathlib import Path

import pytest
from test_startup_prepared_start import inputs, fake_socket
from test_startup_command_contract import KEY
from rocell.application.startup_prepared_start import StartupStartSender, send_prepared_startup
from rocell.application.startup_started_run import collect_started_startup, replay_started_startup


@pytest.mark.parametrize('lost',[False,True])
def test_delivery_and_inconclusive_capture_stay_distinct(tmp_path,monkeypatch,lost):
    calls,_=fake_socket(monkeypatch,lost=lost)
    plan,policy,challenge,_=inputs()
    prepared=send_prepared_startup(tmp_path,StartupStartSender('127.0.0.1',8081,policy),
        plan,challenge,KEY,approved_policy=policy)
    reads=[]
    def reader(path,**kwargs):reads.append(path);raise TimeoutError()
    run=collect_started_startup(tmp_path,Path(prepared['export_path']).name,reader)
    replay=replay_started_startup(tmp_path,Path(run['export_path']).name)
    assert replay['matches'] and run['export_verified'] and run['replay_verified']
    assert replay['outcome']==dict(status='INCONCLUSIVE',assessment=None)
    assert replay['delivery']['result']==('DELIVERY_UNCERTAIN' if lost else 'CONTROLLER_REPORTED_ACCEPTANCE')
    assert not replay['delivery']['endpoint_verified'] and not replay['retry_allowed']
    assert calls.count('send')==1 and len(reads)==1


def test_changed_claim_blocks_collection_before_any_get(tmp_path,monkeypatch):
    fake_socket(monkeypatch)
    plan,policy,challenge,_=inputs()
    prepared=send_prepared_startup(tmp_path,StartupStartSender('127.0.0.1',8081,policy),
        plan,challenge,KEY,approved_policy=policy)
    (tmp_path/prepared['claim_file']).write_text('{}')
    def forbidden(*args,**kwargs):raise AssertionError('Must not collect after changed claim')
    with pytest.raises(ValueError,match='claim changed'):
        collect_started_startup(tmp_path,Path(prepared['export_path']).name,forbidden)
