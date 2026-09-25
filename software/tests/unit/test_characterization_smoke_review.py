import hashlib
import pytest
from rocell.application.characterization_smoke_review import review_smoke_reference


def reference(positions=(2047,2414,1702,2904,1591,2041,2047)):
    goals=(2047,2405,1709,2907,1589,2040,2047)
    raw=bytearray()
    for t in (1,200001,400001):
        raw.extend(t.to_bytes(8,'big')+(t+100).to_bytes(8,'big'))
        for p,g in zip(positions,goals):
            raw.extend(p.to_bytes(2,'big')+g.to_bytes(2,'big')+b'\x01')
            raw.extend(p.to_bytes(2,'little')+bytes(13))
    return bytes(raw)


def test_live_baseline_residuals_are_not_command_deltas():
    raw=reference()
    r=review_smoke_reference(raw,reference_sha256=hashlib.sha256(raw).hexdigest(),
                            goals=[[2397,1717]])
    assert r['position_minus_goal']==[0,9,-7,-3,2,1,0]
    assert r['target_register_deltas']==[-8,8]
    assert r['target_minus_measured']==[-17,15]
    assert not r['movement_authorized'] and not r['physical_clearance_verified']


@pytest.mark.parametrize('goals', [[[2397,1717],[2405,1709]], [[2398,1716]], []])
def test_reject_other_plans(goals):
    raw=reference()
    with pytest.raises(ValueError):
        review_smoke_reference(raw,reference_sha256=hashlib.sha256(raw).hexdigest(),goals=goals)


def test_reject_excessive_travel():
    raw=reference((2047,2440,1702,2904,1591,2041,2047))
    with pytest.raises(ValueError,match='bounded'):
        review_smoke_reference(raw,reference_sha256=hashlib.sha256(raw).hexdigest(),
                               goals=[[2397,1717]])
