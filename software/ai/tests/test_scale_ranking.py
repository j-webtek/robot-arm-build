import hashlib,json,sys
from pathlib import Path
import numpy as np
import pytest
AI=Path(__file__).resolve().parents[1];sys.path.insert(0,str(AI))
from vision.audit_scale_ranking import auc,ranks,metrics


def test_auc_orientation_ties_and_single_class():
    assert auc([1,2],[1,4])==1
    assert auc([2,1],[1,4])==0
    assert auc([1,1],[1,4])==.5
    assert auc([1,2],[1,2]) is None
    assert ranks([3,1,1,2]).tolist()==[3,.5,.5,2]


def test_retention_includes_ties_and_constant_rank_is_undefined():
    m=metrics([1,1,1,2],[1,2,4,5],[.25,1.])
    assert m['retention_curve'][0]['selected']==3
    assert m['retention_curve'][0]['tail_count']==1
    assert metrics([1,1],[1,4],[.5])['spearman'] is None
    with pytest.raises(ValueError):metrics([float('nan')],[1],[1.])


def test_audit_lineage_and_independent_retention_recount():
    p=AI/'eval/scale_ranking_v1_plan.json';plan=json.loads(p.read_text());source=AI/plan['source'];rows=json.loads(source.read_text())['rows']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==plan['source_sha256']
    assert hashlib.sha256((AI/'vision/audit_scale_ranking.py').read_bytes()).hexdigest()==plan['script_sha256']
    r=json.loads((AI/'eval/scale_ranking_v1_report.json').read_text());assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    scenes=[dict(seed=s,error_mm=max(v['error_mm'] for v in rows if v['seed']==s),scale_mm=max(v['scale_mm'] for v in rows if v['seed']==s),constant_scale_mm=max(v['constant_scale_mm'] for v in rows if v['seed']==s)) for s in sorted({v['seed'] for v in rows})]
    groups=[(rows,r['images']),(scenes,r['scenes'])]+[([v for v in rows if v['condition']==c],r['conditions'][c]) for c in plan['conditions']]+[([v for v in rows if v['style']==s],r['styles'][s]) for s in ['rectangle','ellipse']]
    for group,summary in groups:
        for name,key in [('image_scale','scale_mm'),('fold_constant','constant_scale_mm')]:
            scores=[v[key] for v in group];errors=[v['error_mm'] for v in group]
            assert summary[name]==metrics(scores,errors,plan['retention_fractions'])
            for point in summary[name]['retention_curve']:
                chosen=[v for v in group if v[key]<=point['diagnostic_scale_threshold']]
                assert point['selected']==len(chosen) and point['tail_count']==sum(v['error_mm']>3 for v in chosen)
    assert r['images']['image_scale']['tail_count']==141 and r['scenes']['image_scale']['tail_count']==49
    assert r['new_fits']==r['new_images']==r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
