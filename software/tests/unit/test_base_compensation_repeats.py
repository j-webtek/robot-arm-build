"""Aggregate selection checks; per-pair raw reconstruction is tested separately."""
from copy import deepcopy
import pytest
from rocell.application.base_compensation_comparison import summarize_base_compensation_repeats


def fixtures(monkeypatch):
    rows=[]
    for i in range(2):
        pair=dict(local_pair_supports_candidate=True)
        for j,role in enumerate(('corrected','control')):
            pair[role]=dict(campaign_id=f'campaign-{i}-{j}',report_sha256=str(i*2+j+1)*64,
                context={'test':'same'},model_sha256='f'*64,desired_rad=.02,
                start_joints_rad=[0.]*6,final_joints_rad=[.02+j*.01,0,0,0,0,0],error_rad=j*.01)
        rows.append(pair)
    monkeypatch.setattr('rocell.application.base_compensation_comparison.compare_base_compensation_pair',
        lambda **kw:deepcopy(rows[kw['corrected']]))
    return rows,[dict(corrected=0,control=0),dict(corrected=1,control=1)]


def test_distinct_repeats_are_descriptive_not_global_validation(monkeypatch):
    _,pairs=fixtures(monkeypatch)
    r=summarize_base_compensation_repeats(pairs)
    assert r['pair_count']==2 and r['all_pairs_support_candidate']
    assert r['statistics']['corrected']['reported_endpoint_span_deg']==0
    assert not r['generalized_compensation_validated'] and not r['physical_accuracy_verified']


@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
def test_repeat_direction_forwarded_to_every_original_reader(monkeypatch,direction):
    rows,pairs=fixtures(monkeypatch)
    seen=[]
    def compare(**kwargs):
        seen.append(kwargs['direction'])
        return deepcopy(rows[kwargs['corrected']])
    monkeypatch.setattr('rocell.application.base_compensation_comparison.compare_base_compensation_pair',compare)
    assert summarize_base_compensation_repeats(pairs,direction=direction)['pair_count']==2
    assert seen==[direction,direction]


def test_unknown_repeat_direction_rejected(monkeypatch):
    _,pairs=fixtures(monkeypatch)
    with pytest.raises(ValueError):
        summarize_base_compensation_repeats(pairs,direction='BOTH')


@pytest.mark.parametrize('fault',['duplicate','hash','context','model','start','endpoint','count'])
def test_bad_repeat_selection_rejected(monkeypatch,fault):
    rows,pairs=fixtures(monkeypatch)
    row=rows[1]['corrected']
    if fault=='duplicate':row['campaign_id']=rows[0]['corrected']['campaign_id']
    if fault=='hash':row['report_sha256']=rows[0]['corrected']['report_sha256']
    if fault=='context':row['context']={}
    if fault=='model':row['model_sha256']='e'*64
    if fault=='start':row['start_joints_rad'][2]=.01
    if fault=='endpoint':row['desired_rad']=.03
    if fault=='count':pairs=pairs[:1]
    with pytest.raises(ValueError):summarize_base_compensation_repeats(pairs)
