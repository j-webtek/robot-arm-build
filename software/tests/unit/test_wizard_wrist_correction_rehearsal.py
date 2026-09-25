import json
from pathlib import Path
import pytest
from rocell.application.wizard_worker import run
from rocell.application.wrist_correction_rehearsal import SCENARIOS
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service,_run,WORKSPACE


@pytest.mark.parametrize('scenario',SCENARIOS)
def test_real_worker_correction_scenarios(scenario):
    result=run(WORKSPACE,'wrist_correction_rehearse',dict(scenario=scenario),'CELL-A')
    assert result['status']=='SUCCEEDED'
    assert result['steps'][0]['report']['expected_outcome_matched']
    assert result['device_open_count']==result['motion_command_count']==0


@pytest.mark.parametrize('values',[{'scenario':'LIVE'},{'raw_command':'{}'},{'scenario':'CONSTANT_BIAS','mode':'physical'}])
def test_no_arbitrary_command_or_native_mode(values):
    with pytest.raises(ValueError): run(WORKSPACE,'wrist_correction_rehearse',values,'CELL-A')


def test_public_wizard_retains_missed_scenario_and_export(make_service):
    service,runner,_=make_service(mode='physical')
    runner.run=lambda action,values,**kw:run(WORKSPACE,action,values,kw['cell_id'])
    operation=_run(service,'wrist_correction_rehearse',dict(scenario='BIAS_DISAPPEARS'))
    assert operation['status']=='SUCCEEDED', operation.get('error')  # Expected fault injection, not motion success.
    assert operation['result']['steps'][0]['report']['status']=='WRIST_EXCURSION'
    exported=_run(service,'export_logs')
    folder=Path(exported['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    retained=json.loads((folder/('attachment-result-'+operation['operation_id'].removeprefix('operation-')+'.json')).read_bytes())
    assert retained['steps'][0]['report']['status']=='WRIST_EXCURSION'
    import base64
    import hashlib
    from rocell.application.wrist_correction_result_review import review_wrist_correction_result
    from rocell.application.wrist_correction_pipeline_rehearsal import SYNTHETIC_KEY
    from rocell.safety.bench_review_authority import BenchReviewAuthority
    from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
    evidence={}
    for item in retained['steps'][0]['report']['originals']:
        raw=b''.join(base64.b64decode(c,validate=True) for c in item['base64_chunks'])
        assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
        evidence[item['name']]=raw
    context=json.loads(evidence['context.json'])
    originals=[(AbsoluteWristIntent(evidence['evidence-'+str(i)+'-request.json']),
                evidence['evidence-'+str(i)+'-trial.json']) for i in (1,2)]
    rebuilt=review_wrist_correction_result(evidence[context['attempt_id']+'-wrist-correction-trial.original.json'],
        authority=BenchReviewAuthority(SYNTHETIC_KEY).for_wrist_correction_review(),
        bundle=evidence['review.json'],context=context,originals=originals,expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    assert rebuilt['endpoint']['status']=='WRIST_EXCURSION'
    assert not rebuilt['campaign_advance_allowed']
