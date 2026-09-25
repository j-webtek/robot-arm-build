import pytest

from rocell.application.fine_pair_lookup_analysis import analyze_fine_pair_lookup
from rocell.application.fine_pair_lookup_validation import plan_fine_lookup_validation


def evidence():
    plan=plan_fine_lookup_validation()
    actuals=[[2385,1730],[2387,1728],[2391,1724],
             [2385,1730],[2387,1728],[2391,1724],
             [2385,1730],[2389,1725],[2391,1724],
             [2385,1730],[2389,1725],[2391,1724]]
    return {'schema':'rocell.fine_pair_lookup_result.v1',
            'plan_sha256':plan['plan_sha256'],
            'rows':[{'leg':i,'target':target,'actual':actuals[i]}
                    for i,target in enumerate(plan['manifest']['goals'])]}


def test_exact_r50_evidence_releases_only_two_local_lookups():
    analysis=analyze_fine_pair_lookup(evidence(),source_export='r50')
    assert analysis['fine_endpoint_lookup_validated'] is True
    assert analysis['release_scope']=='two_local_encoder_endpoint_lookups_only'
    assert analysis['movement_authorized'] is False
    assert analysis['general_compensation_validated'] is False
    assert [entry['candidate_errors_counts'] for entry in analysis['entries']]==[[1,1],[0,0]]
    assert all(entry['exact_repeat'] and entry['improves_over_retained_direct']
               for entry in analysis['entries'])


@pytest.mark.parametrize('fault',['hash','short','target','repeat','accuracy'])
def test_changed_or_failed_evidence_is_rejected_or_not_released(fault):
    result=evidence()
    if fault=='hash':result['plan_sha256']='0'*64
    elif fault=='short':result['rows'].pop()
    elif fault=='target':result['rows'][1]['target']=[0,0]
    elif fault=='repeat':result['rows'][4]['actual']=[2388,1728]
    else:result['rows'][1]['actual']=result['rows'][4]['actual']=[2389,1728]
    if fault in ('hash','short','target'):
        with pytest.raises(ValueError):analyze_fine_pair_lookup(result,source_export='r50')
    else:
        assert analyze_fine_pair_lookup(result,source_export='r50')[
            'fine_endpoint_lookup_validated'] is False
