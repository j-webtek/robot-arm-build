import pytest
from test_characterization_composition import binary
from test_characterization_socket_campaign import NativeHTTPRelay, KEY, BOOT, PREFIX
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_matched_runner import MatchedRunner


@pytest.mark.parametrize('hypothesis',['constant10','directional','frozen_reverse'])
def test_matched_runner(binary,tmp_path,hypothesis):
    relay=NativeHTTPRelay(binary,'matched',hypothesis=hypothesis)
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        result=MatchedRunner(client,tmp_path,key=KEY,boot=BOOT,sleep=lambda _:None).run(motion_admitted=True)
        report=result['report']
        if hypothesis=='frozen_reverse':
            assert report['status']=='INCONCLUSIVE' and report['fault_export']
            import json
            from pathlib import Path
            record=json.loads((Path(report['failed_leg_export']['export_path'])/'attachment-characterization-result.json').read_text())
            assert record['outcome']=='STOP'
            assert record['motion_summary']['observation_span_us']>=1800000
            assert all(j['final_net_counts']==0 for j in record['motion_summary']['joints'])
            assert len(report['legs'])==1
            assert relay.rpc('TICK 100')=='2'
        else:
            assert report['status']=='COMPLETE' and len(report['legs'])==12
            assert relay.calls.count(PREFIX+'receipt')==12
    finally:relay.close()


def test_lost_receipt_ack_never_retries(binary,tmp_path):
    relay=NativeHTTPRelay(binary,'matched',drop_receipt=True)
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
        def recovery(campaign):
            return CharacterizationRecoveryHTTP('127.0.0.1',relay.server.server_port,
                                                key=KEY,boot=BOOT,campaign=campaign)
        report=MatchedRunner(client,tmp_path,key=KEY,boot=BOOT,sleep=lambda _:None,
                             recovery_factory=recovery).run(motion_admitted=True)['report']
        assert report['status']=='INCONCLUSIVE'
        assert not report['controller_stop_confirmed']
        assert relay.calls.count(PREFIX+'receipt')==1
        assert relay.writes_after_lost_ack==2
        assert report['reconciliation']['state']=='RECEIPT_ACCEPTED_NEXT_LEG_POSSIBLE'
        assert not report['reconciliation']['resume_allowed']
        assert report['recovery_export']
    finally:relay.close()


@pytest.mark.parametrize('hypothesis',['transient_reverse','delayed_reverse'])
def test_transient_or_delayed_response(binary,tmp_path,hypothesis):
    import json
    from pathlib import Path
    relay=NativeHTTPRelay(binary,'matched',hypothesis=hypothesis)
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        report=MatchedRunner(client,tmp_path,key=KEY,boot=BOOT,sleep=lambda _:None).run(motion_admitted=True)['report']
        if hypothesis=='delayed_reverse':
            assert report['status']=='COMPLETE'
        else:
            assert report['status']=='INCONCLUSIVE'
            record=json.loads((Path(report['failed_leg_export']['export_path'])/'attachment-characterization-result.json').read_text())
            rows=record['motion_summary']['joints']
            assert [j['sampled_peak_absolute_counts'] for j in rows]==[4,4]
            assert [j['final_net_counts'] for j in rows]==[0,-2]
            assert relay.calls.count(PREFIX+'receipt')==1
            assert relay.rpc('TICK 100')=='2'
    finally:relay.close()
