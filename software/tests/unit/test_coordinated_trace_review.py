import json
import pytest
from test_wifi_cartesian import setup
from rocell.application.coordinated_trace_review import review_coordinated_trace


def test_coordinated_review_preserves_model_only_scope(tmp_path):
    _,run,_,_,_,_=setup(tmp_path)
    result=run()
    report=json.loads(json.dumps(dict(schema='rocell.native_cartesian_trial.v1',status=result['status'],run=result)))
    review=review_coordinated_trace(report)
    assert review['position_error_mm']<1e-6 and len(review['joints'])==6
    assert not review['hardware_access'] and not review['compensation_fitted']
    report['run']['transaction']['rows'][-1][2][0]+=1
    with pytest.raises(ValueError): review_coordinated_trace(report)


def test_unordered_trace_rejected(tmp_path):
    _,run,_,_,_,_=setup(tmp_path)
    result=run(); report=json.loads(json.dumps(dict(schema='rocell.native_cartesian_trial.v1',status=result['status'],run=result)))
    report['run']['transaction']['rows'].reverse()
    with pytest.raises(ValueError): review_coordinated_trace(report)
