import hashlib
import json

import pytest

from rocell.application.local_pair_mapping_batch import plan_mapping_batch
from rocell.application.local_pair_mapping_runner import LocalPairMappingRunner


def reference_bytes(*, selected_goals=(2386,1728), selected_positions=(2391,1724)):
    # Canonical reference: three 156-byte poses, big endian.
    raw=bytearray()
    positions=[2047,*selected_positions,2904,1591,2041,2047]
    goals=[2047,*selected_goals,2907,1589,2040,2047]
    for n in range(3):
        raw.extend((100000+n*200000).to_bytes(8,'big'))
        raw.extend((110000+n*200000).to_bytes(8,'big'))
        for position,goal in zip(positions,goals):
            raw.extend(position.to_bytes(2,'big'));raw.extend(goal.to_bytes(2,'big'))
            raw.append(1);raw.extend(position.to_bytes(2,'little'));raw.extend(bytes(13))
    return bytes(raw)


def test_review_binds_exact_manifest_and_start(tmp_path):
    raw=reference_bytes();challenge={
        'reference':hashlib.sha256(raw).hexdigest(),'campaign':'11'*32,
        'manifest':{'goals':plan_mapping_batch()['manifest']['goals']}}
    runner=LocalPairMappingRunner(None,tmp_path,key=b'k'*32,boot='22'*16)
    review=runner.review(raw,challenge)
    assert review['measured_anchor'][1:3]==[2391,1724]
    assert review['mapping_plan_sha256']==plan_mapping_batch()['plan_sha256']


@pytest.mark.parametrize('fault',['manifest','goals','position'])
def test_review_rejects_changed_binding(tmp_path,fault):
    raw=bytearray(reference_bytes(
        selected_goals=(2385,1729) if fault=='goals' else (2386,1728),
        selected_positions=(2394,1724) if fault=='position' else (2391,1724)))
    challenge={'reference':hashlib.sha256(raw).hexdigest(),'campaign':'11'*32,
               'manifest':{'goals':plan_mapping_batch()['manifest']['goals']}}
    if fault=='manifest':challenge['manifest']['goals'][0][0]+=1
    if fault!='manifest':challenge['reference']=hashlib.sha256(raw).hexdigest()
    runner=LocalPairMappingRunner(None,tmp_path,key=b'k'*32,boot='22'*16)
    with pytest.raises(ValueError):runner.review(bytes(raw),challenge)
