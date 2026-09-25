import json
from pathlib import Path
import pytest
from test_characterization_composition import binary
from test_characterization_socket_campaign import NativeHTTPRelay, run_offline_campaign, KEY, BOOT, PREFIX
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_host_session import _pose
from rocell.application.shoulder_characterization import assess_leg


@pytest.mark.parametrize('hypothesis',['constant10','directional'])
def test_native_matched_residual_models(binary,tmp_path,hypothesis):
    relay=NativeHTTPRelay(binary,'matched',hypothesis=hypothesis)
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        saved=run_offline_campaign(client,tmp_path/'results',expected_position=2415)
        assert len(saved)==12 and relay.rpc('TICK 100')=='12'
        middle=[]
        for path in saved:
            r=json.loads((Path(path)/'attachment-characterization-result.json').read_text())
            a=assess_leg(_pose(r['baseline']),r['goals'][r['leg']],
                [_pose(p) for p in r['observations']],bounds=r['bounds'],
                delivery_confirmed=True,export_verified=True)
            if r['goals'][r['leg']]==[2397,1717]:middle.append(a)
        assert len(middle)==6
        assert sum(a['goal_delta'][0]>0 for a in middle)==3
        errors={tuple(a['endpoint_error']) for a in middle}
        assert errors==({(10,-7)} if hypothesis=='constant10' else {(10,-7),(6,-4)})
    finally:relay.close()


def test_native_reverse_no_response_stops_campaign(binary,tmp_path):
    relay=NativeHTTPRelay(binary,'matched',hypothesis='frozen_reverse')
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        with pytest.raises(AssertionError):
            run_offline_campaign(client,tmp_path/'results',expected_position=2415)
        assert relay.rpc('TICK 100')=='2'
        snapshot=json.loads(relay.rpc('SNAPSHOT'))
        assert snapshot['phase']=='FAULT'
        assert relay.calls.count(PREFIX+'receipt')==1
    finally:relay.close()
