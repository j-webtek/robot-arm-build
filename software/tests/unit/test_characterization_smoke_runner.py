import pytest
from test_characterization_composition import binary
from test_characterization_socket_campaign import NativeHTTPRelay, KEY, BOOT, PREFIX
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_smoke_runner import SmokeRunner


@pytest.mark.parametrize('drop', [False, True])
def test_single_leg_runner(binary, tmp_path, drop):
    relay=NativeHTTPRelay(binary, 'smoke', drop_receipt=drop)
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        runner=SmokeRunner(client,tmp_path,key=KEY,boot=BOOT,sleep=lambda _:None)
        with pytest.raises(ValueError): runner.run()
        assert not relay.calls
        result=runner.run(motion_admitted=True)['report']
        assert result['status']==('INCONCLUSIVE' if drop else 'COMPLETE')
        assert result['baseline_review']['target_minus_measured']==[-17,15]
        assert relay.calls.count(PREFIX+'start')==1
        assert relay.calls.count(PREFIX+'receipt')==1
        assert relay.rpc('TICK 100')=='1'
        count=len(relay.calls)
        with pytest.raises(ValueError): runner.run(motion_admitted=True)
        assert len(relay.calls)==count
    finally:
        relay.close()
