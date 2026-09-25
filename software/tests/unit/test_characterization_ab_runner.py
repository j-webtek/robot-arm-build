import json
from pathlib import Path
import pytest
from test_characterization_composition import binary
from test_characterization_socket_campaign import NativeHTTPRelay, KEY, BOOT, PREFIX
from test_shoulder_repeatability_plan import frozen
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_ab_runner import ABRunner


@pytest.mark.parametrize('variant,pattern',[('control','ab_control'),('compensated','ab_candidate')])
@pytest.mark.parametrize('hypothesis',[None,'directional'])
def test_pilot_terminal_evidence_and_conditioning_gate(binary,tmp_path,variant,pattern,hypothesis):
    relay=NativeHTTPRelay(binary,pattern,hypothesis=hypothesis)
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        result=ABRunner(client,tmp_path,key=KEY,boot=BOOT,frozen_models=frozen(),
            variant=variant,sleep=lambda _:None).run(motion_admitted=True)
        report=result['report']
        if hypothesis=='directional':
            assert report['status']=='INCONCLUSIVE'
            assert 'Conditioning return unmatched' in report['error_message']
            assert relay.calls.count(PREFIX+'receipt')==1
            assert relay.rpc('TICK 100')=='2'
            assert 'trial_audit_export' not in result
        else:
            assert report['status']==('INCONCLUSIVE' if variant=='control' else 'COMPLETE')
            assert relay.calls.count(PREFIX+'receipt')==(2 if variant=='control' else 3)
            assert relay.rpc('TICK 100')=='3'
            audit=json.loads((Path(result['trial_audit_export'])/'attachment-ab-terminal-review.json').read_text())
            assert audit['terminal_measurement_usable']
            assert audit['signed_error']==([3,-5] if variant=='control' else [-1,0])
            assert not audit['continuation_authorized']
    finally:relay.close()


def test_native_trial_gate_survives_host_gate_omission(binary,tmp_path,monkeypatch):
    # Deliberately omit only the host post-result gate in this fixture. The
    # native owner must reject the bad conditioning position before trial write.
    monkeypatch.setattr(ABRunner,'check_result',lambda *args:None)
    relay=NativeHTTPRelay(binary,'ab_candidate',hypothesis='directional')
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        result=ABRunner(client,tmp_path,key=KEY,boot=BOOT,frozen_models=frozen(),
            variant='compensated',sleep=lambda _:None).run(motion_admitted=True)
        assert result['report']['status']=='INCONCLUSIVE'
        assert result['report']['fault_export']['reason']=='BASELINE_ADMISSION'
        assert relay.calls.count(PREFIX+'receipt')==2
        assert relay.rpc('TICK 100')=='2'
    finally:relay.close()
