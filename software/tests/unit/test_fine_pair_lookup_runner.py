import hashlib
import pytest

from rocell.application.fine_pair_lookup_runner import FinePairLookupRunner
from rocell.application.fine_pair_lookup_validation import plan_fine_lookup_validation


def reference_bytes(*,goals=(2387,1727),positions=(2389,1726)):
    raw=bytearray();all_positions=[2047,*positions,2904,1591,2041,2047]
    all_goals=[2047,*goals,2907,1589,2040,2047]
    for n in range(3):
        raw.extend((100000+n*200000).to_bytes(8,'big'));raw.extend((110000+n*200000).to_bytes(8,'big'))
        for position,goal in zip(all_positions,all_goals):
            raw.extend(position.to_bytes(2,'big'));raw.extend(goal.to_bytes(2,'big'))
            raw.append(1);raw.extend(position.to_bytes(2,'little'));raw.extend(bytes(13))
    return bytes(raw)


def test_runner_binds_exact_r50_plan_and_terminal_state(tmp_path):
    raw=reference_bytes();challenge={'reference':hashlib.sha256(raw).hexdigest(),
        'campaign':'11'*32,'manifest':{'goals':plan_fine_lookup_validation()['manifest']['goals']}}
    runner=FinePairLookupRunner(None,tmp_path,key=b'k'*32,boot='22'*16)
    review=runner.review(raw,challenge)
    assert review['measured_anchor'][1:3]==[2389,1726]
    assert review['mapping_plan_sha256']==plan_fine_lookup_validation()['plan_sha256']


@pytest.mark.parametrize('fault',['manifest','goals','position'])
def test_runner_rejects_changed_r50_binding(tmp_path,fault):
    raw=reference_bytes(goals=(2388,1726) if fault=='goals' else (2387,1727),
                        positions=(2391,1726) if fault=='position' else (2389,1726))
    challenge={'reference':hashlib.sha256(raw).hexdigest(),'campaign':'11'*32,
               'manifest':{'goals':plan_fine_lookup_validation()['manifest']['goals']}}
    if fault=='manifest':challenge['manifest']['goals'][0][0]+=1
    runner=FinePairLookupRunner(None,tmp_path,key=b'k'*32,boot='22'*16)
    with pytest.raises(ValueError):runner.review(raw,challenge)
