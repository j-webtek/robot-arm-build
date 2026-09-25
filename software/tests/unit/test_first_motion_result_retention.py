"""Diagnostic retention is never child-result validation or physical approval."""
import base64
import hashlib
import json

import pytest

from rocell.application import first_motion_result_retention as module
from test_first_motion_measurement_binding import setup


@pytest.mark.parametrize('stdout',[b'',b'not json\xff',b'{"physical_movement_verified":true}',b'x'*(256*1024)],
                         ids=['empty','malformed','false-claim','maximum-size'])
def test_exact_streams_retained_without_trusting_content(tmp_path,stdout):
    _,request = setup(tmp_path)
    path,report = module.retain_first_motion_result(tmp_path,request,stdout=stdout,stderr=b'error\x00')
    assert json.loads(path.read_bytes())==report
    assert report['status']=='ORIGINALS_RETAINED_NOT_VALIDATED'
    for key in ('child_result_validated','owned_process_receipt_verified','physical_movement_verified',
                'physical_stop_verified','campaign_advance_allowed','replay_allowed'):
        assert report[key] is False
    for name,expected in (('request',request.canonical_bytes),('stdout',stdout),('stderr',b'error\x00')):
        item=report['originals'][name]
        raw=(tmp_path/item['file']).read_bytes()
        doc=json.loads(raw)
        assert base64.b64decode(doc['base64'],validate=True)==expected
        assert item['sha256']==doc['sha256']==hashlib.sha256(expected).hexdigest()
        assert item['stored_sha256']==hashlib.sha256(raw).hexdigest()
    with pytest.raises(Exception):
        module.retain_first_motion_result(tmp_path,request,stdout=b'changed',stderr=b'')


@pytest.mark.parametrize('stdout,stderr',[(b'x'*(256*1024+1),b''),(b'',b'x'*8193),('text',b'')],
                         ids=['stdout-oversized','stderr-oversized','wrong-type'])
def test_invalid_streams_refused_before_publication(tmp_path,stdout,stderr):
    _,request=setup(tmp_path)
    with pytest.raises(ValueError): module.retain_first_motion_result(tmp_path,request,stdout=stdout,stderr=stderr)
    assert not list(tmp_path.glob('*-first-motion-result-*'))


def test_partial_publication_preserves_original_and_cannot_overwrite(tmp_path,monkeypatch):
    _,request=setup(tmp_path)
    publish=module.publish_bytes
    calls=[]
    def interrupted(*args,**kwargs):
        calls.append(1)
        if len(calls)==2: raise RuntimeError('synthetic interruption')
        return publish(*args,**kwargs)
    monkeypatch.setattr(module,'publish_bytes',interrupted)
    with pytest.raises(RuntimeError): module.retain_first_motion_result(tmp_path,request,stdout=b'raw',stderr=b'')
    assert len(list(tmp_path.glob('*-first-motion-result-request.json')))==1
    assert not list(tmp_path.glob('*-first-motion-result-report.json'))
    monkeypatch.setattr(module,'publish_bytes',publish)
    with pytest.raises(Exception): module.retain_first_motion_result(tmp_path,request,stdout=b'raw',stderr=b'')
