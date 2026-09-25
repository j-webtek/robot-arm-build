"""Offline statistics and evidence gates; all verifier inputs are test doubles."""
from copy import deepcopy
import math
import pytest
from rocell.application import wrist_endpoint_models as model


def setup(monkeypatch):
    entries=[]
    results={}
    for i,(split,direction,error) in enumerate([
        ('train','INCREASING',-.4),('train','DECREASING',1.),
        ('validation','INCREASING',-.4),('validation','DECREASING',1.)]):
        digest=str(i)*64
        entries.append(dict(directory=str(i),report_name='report',report_sha256=digest,split=split))
        results[str(i)]=dict(report_sha256=digest,valid=True,reconstruction_consistent=True,
            configuration_references=dict.fromkeys(('native_controller_review_sha256',
                'tool_payload_sha256','workcell_sha256','protocol_review_sha256'),'same'),
            endpoint_diagnostics=[dict(leg_id='leg-01',target_rad=0.,final_rad=math.radians(error),
                signed_error_rad=math.radians(error),direction=direction,
                command=dict(T=101,joint=4,rad=0.,spd=20,acc=1),reported_endpoint_verified=abs(error)<=.5)])
    monkeypatch.setattr(model,'verify_native_retained_export',lambda directory,name:deepcopy(results[directory]))
    return entries,results


def test_compare_keeps_failures_and_does_not_claim_correction(monkeypatch):
    entries,_=setup(monkeypatch)
    r=model.compare_exports(entries)
    assert r['training_count']==r['validation_count']==2
    assert r['models']['direction_bias']['mae_deg']==pytest.approx(0)
    assert r['models']['constant_bias']['mae_deg']==pytest.approx(.7)
    assert sum(x['reported_pass'] for x in r['observations'])==2
    assert not r['motion_authorized'] and not r['compensation_enabled']


def test_validation_values_cannot_train_biases(monkeypatch):
    entries,results=setup(monkeypatch)
    before=model.compare_exports(entries)
    results['2']['endpoint_diagnostics'][0]['signed_error_rad']=math.radians(8.)
    after=model.compare_exports(entries)
    assert after['direction_bias_deg']==before['direction_bias_deg']
    assert after['constant_bias_deg']==before['constant_bias_deg']
    assert after['models']['direction_bias']['mae_deg']>0


@pytest.mark.parametrize('fault',['duplicate','digest','partial','context','speed','direction','nonfinite'])
def test_invalid_or_mixed_evidence_rejected(monkeypatch,fault):
    entries,results=setup(monkeypatch)
    if fault=='duplicate':entries[2]=dict(entries[0],split='validation')
    if fault=='digest':entries[2]['report_sha256']='f'*64
    if fault=='partial':results['2']['reconstruction_consistent']=False
    if fault=='context':results['2']['configuration_references']['workcell_sha256']='different'
    row=results['2']['endpoint_diagnostics'][0]
    if fault=='speed':row['command']['spd']=30
    if fault=='direction':row['direction']='UNKNOWN'
    if fault=='nonfinite':row['signed_error_rad']=float('nan')
    with pytest.raises(ValueError):model.compare_exports(entries)


def test_other_targets_and_unexecuted_legs_are_explicitly_excluded(monkeypatch):
    entries,results=setup(monkeypatch)
    row=results['2']['endpoint_diagnostics'][0]
    results['2']['endpoint_diagnostics'] += [dict(row,leg_id='leg-02',target_rad=.07),
        dict(row,leg_id='leg-03',final_rad=None)]
    r=model.compare_exports(entries)
    assert r['validation_count']==2
    assert {e['reason'] for e in r['excluded_endpoints']}=={'NONZERO_TARGET','NOT_EXECUTED'}


def test_training_requires_both_directions(monkeypatch):
    entries,_=setup(monkeypatch)
    with pytest.raises(ValueError):model.compare_exports(entries[1:])
