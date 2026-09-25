import json
from pathlib import Path
import pytest
from test_characterization_composition import binary
from test_characterization_socket_campaign import NativeHTTPRelay, KEY, BOOT, PREFIX
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_repeatability_runner import RepeatabilityRunner
from test_shoulder_repeatability_plan import frozen


@pytest.mark.parametrize('hypothesis',['constant10','directional','frozen_reverse'])
def test_exact_six_leg_repeatability(binary,tmp_path,hypothesis):
    relay=NativeHTTPRelay(binary,'repeatability',hypothesis=hypothesis)
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        report=RepeatabilityRunner(client,tmp_path,key=KEY,boot=BOOT,
            frozen_models=frozen(),sleep=lambda _:None).run(motion_admitted=True)['report']
        complete=hypothesis!='frozen_reverse'
        assert report['status']==('COMPLETE' if complete else 'INCONCLUSIVE'),report
        assert len(report['legs'])==relay.calls.count(PREFIX+'receipt')==(6 if complete else 1)
        assert relay.rpc('TICK 100')==('6' if complete else '2')
        assert len(report['challenge']['manifest']['goals'])==6
        assert len(report['prediction_scores'])==len(report['legs'])
        assert Path(report['baseline_review']['prediction_export']).is_dir()
        records=[json.loads(p.read_text()) for p in tmp_path.rglob('attachment-characterization-result.json')]
        assert all(r['outcome']!='SETTLED_SMALL_RESPONSE' for r in records)
        if not complete:
            assert report['fault_export']['reason']=='NO_CLEAR_RESPONSE'
            assert report['failed_leg_export']['leg']==1
    finally:relay.close()


@pytest.mark.parametrize('stage',['predictions','score'])
def test_prediction_export_failure_prevents_progression(binary,tmp_path,monkeypatch,stage):
    original=RepeatabilityRunner._export
    def export(self,name,document):
        if name==f'repeatability-{stage}.json':raise ValueError('Injected prediction export failure')
        return original(self,name,document)
    monkeypatch.setattr(RepeatabilityRunner,'_export',export)
    relay=NativeHTTPRelay(binary,'repeatability')
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        report=RepeatabilityRunner(client,tmp_path,key=KEY,boot=BOOT,frozen_models=frozen(),
            sleep=lambda _:None).run(motion_admitted=True)['report']
        assert report['status']=='INCONCLUSIVE'
        assert relay.calls.count(PREFIX+'receipt')==0
        assert relay.calls.count(PREFIX+'start')==(0 if stage=='predictions' else 1)
        assert relay.rpc('TICK 100')==('0' if stage=='predictions' else '1')
    finally:relay.close()
