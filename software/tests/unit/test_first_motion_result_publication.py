"""Associate synthetic child output with real synthetic launch/claim originals."""
import base64
import hashlib
import json
import os
from pathlib import Path

import pytest

from rocell.application.first_motion_contract import FirstMotionRequest,canonical
from rocell.application.first_motion_worker_claim import reserve_first_motion_launch,claim_first_motion_worker
from rocell.providers.windows.first_motion_result_publication import publish_first_motion_result
from rocell.providers.windows.first_motion_native_result import encode_result
from test_first_motion_native_result import prepared
from test_first_motion_native_protocol import signed


def fixture(tmp_path):
    wire,child=prepared(tmp_path)
    request=FirstMotionRequest(canonical(wire['payload']['first_motion_request']))
    root=Path(wire['payload']['root'])
    reviews=b'synthetic-retained-review-bytes-not-authentication'
    (root/(wire['attempt_id']+'-first-motion-reviews.json')).write_bytes(reviews)
    runtime=canonical(wire['payload']['registration'])
    launch=reserve_first_motion_launch(root,request,runtime_original=runtime,
        review_bundle_sha256=hashlib.sha256(reviews).hexdigest(),now_ns=2_000_000_000)
    claim=claim_first_motion_worker(root,request,launch_sha256=launch,
        current_source_sha256=request.to_dict()['references']['source_sha256'],
        current_runtime_sha256=hashlib.sha256(runtime).hexdigest(),now_ns=2_000_000_000)
    wire['payload']['launch_sha256']=launch
    request_raw=signed(wire)
    child['claim_sha256']=claim.claim_sha256
    return request_raw,encode_result(child,wire)


@pytest.mark.parametrize('fault',[None,'pid','process','exit','malformed'])
def test_receipt_and_completion_without_qualifying_movement(tmp_path,fault):
    request_raw,stdout=fixture(tmp_path)
    if fault=='malformed': stdout=b'not-json\xff'
    output=tmp_path/'output'; output.mkdir()
    path,report=publish_first_motion_result(output,request_raw=request_raw,stdout=stdout,stderr=b'',
        owned_process_id=os.getpid()+(1 if fault=='pid' else 0),returncode=1 if fault=='exit' else 0,
        process_tree_closed=fault!='process',finished_ns=40_000_000_000)
    assert path.exists()
    expected='RESULT_REJECTED' if fault in {'pid','malformed'} else (
        'PROCESS_COMPLETION_UNCONFIRMED' if fault in {'process','exit'} else 'RESULT_RETAINED')
    assert report['status']==expected
    assert report['claim_receipt_verified']==(fault not in {'pid','malformed'})
    assert not report['physical_movement_verified'] and not report['campaign_advance_allowed']
    original=json.loads((output/report['originals']['stdout.bin']['file']).read_bytes())
    assert base64.b64decode(original['base64'],validate=True)==stdout
    with pytest.raises(Exception):
        publish_first_motion_result(output,request_raw=request_raw,stdout=stdout,stderr=b'',
            owned_process_id=os.getpid(),returncode=0,process_tree_closed=True,finished_ns=40_000_000_000)
