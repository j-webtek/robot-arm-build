import hashlib
import json
from pathlib import Path
import sys
import pytest
AI=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI))
from rocell_ai.confidence_metrics import score


def test_metrics_have_known_values():
    r=score([0.9,0.8,0.2,0.1],[True,False,True,False],threshold=0.8,bins=2)
    assert r['brier_score']==pytest.approx(0.325)
    assert r['accepted_count']==2
    assert r['false_accept_fraction_among_accepted']==0.5
    assert sum(b['count'] for b in r['reliability_bins'])==4


def test_no_acceptance_is_not_zero_error():
    r=score([0.1],[False])
    assert r['false_accept_fraction_among_accepted'] is None
    assert r['accepted_count']==0


def test_probability_one_goes_in_last_bin():
    r=score([0,1],[False,True])
    assert r['reliability_bins'][-1]['count']==1
    assert r['brier_score']==0


@pytest.mark.parametrize('probabilities,outcomes', [([],[]),([True],[True]),([float('nan')],[True]),([1.01],[True]),([0.5],[1]),([0.5],[])])
def test_bad_input_rejected(probabilities,outcomes):
    with pytest.raises(ValueError): score(probabilities,outcomes)


def test_frozen_plan_and_disjoint_seeds():
    plan=json.loads((AI/'train/localization_confidence_v0_plan.json').read_text())
    used=set()
    for split in plan['splits'].values():
        seeds=set(range(split['seed_start'],split['seed_start']+split['seed_count']))
        assert not seeds & used
        assert min(seeds)>=14000000
        used.update(seeds)
    for path,digest in plan['file_sha256'].items():
        assert hashlib.sha256((AI.parents[1]/path).read_bytes()).hexdigest()==digest
    assert plan['scope']=='SYNTHETIC_RESEARCH_ONLY'
