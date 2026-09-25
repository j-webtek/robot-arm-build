import hashlib
import hmac
import pytest
from rocell.application.characterization_http_session import CharacterizationHTTPSession

KEY=bytes(range(32));BOOT='11'*16


def reply(sequence=0,status=200,body=b'{}'):
    data=b'RCCRESPONSE01\0'+bytes.fromhex(BOOT)+sequence.to_bytes(4,'big')+status.to_bytes(2,'big')+hashlib.sha256(body).digest()
    return dict(status=status,body=body,sequence=str(sequence),signature=hmac.digest(KEY,data,'sha256').hex())


def test_sequential_requests():
    client=CharacterizationHTTPSession(key=KEY,boot=BOOT)
    for i in range(3):
        request=client.request('GET','/rocell/characterization/status')
        assert request['headers']['X-Rocell-Sequence']==str(i)
        assert client.response(**reply(i))==b'{}'
    assert not client.stopped


def test_uncertain_receipt_report_is_sticky_and_does_not_expose_payload():
    client=CharacterizationHTTPSession(key=KEY,boot=BOOT)
    client.request('POST','/rocell/characterization/receipt',b'private-receipt')
    client.delivery_uncertain()
    report=client.uncertainty
    assert report['continuation_may_have_been_authorized']
    assert report['reconciliation_required']
    assert not report['controller_stop_confirmed']
    assert not report['retry_allowed']
    assert report['operation']['body_sha256']==hashlib.sha256(b'private-receipt').hexdigest()
    assert 'private-receipt' not in str(report)
    report['operation']['path']='changed'
    with pytest.raises(ValueError):
        client.request('GET','/rocell/characterization/status')
    client.delivery_uncertain()
    assert client.uncertainty['operation']['path']=='/rocell/characterization/receipt'


def test_uncertain_reviewed_hover_receipt_reports_possible_continuation():
    client=CharacterizationHTTPSession(key=KEY,boot=BOOT)
    client.request('POST','/rocell/reviewed-hover/receipt',b'1:'+b'0'*64)
    client.delivery_uncertain()
    assert client.uncertainty['continuation_may_have_been_authorized']
    assert client.uncertainty['reconciliation_required']
    assert not client.uncertainty['retry_allowed']


@pytest.mark.parametrize('case',['unsolicited','overlap','timeout','sequence','signature','body','status','replay','noncanonical'])
def test_uncertainty_or_mismatch_latches(case):
    client=CharacterizationHTTPSession(key=KEY,boot=BOOT)
    if case!='unsolicited':client.request('GET','/rocell/characterization/status')
    args=reply()
    with pytest.raises(ValueError):
        if case=='overlap':client.request('GET','/rocell/characterization/status')
        else:
            if case=='timeout':client.delivery_uncertain()
            if case=='sequence':args['sequence']='1'
            if case=='noncanonical':args['sequence']='00'
            if case=='signature':args['signature']='00'*32
            if case=='body':args['body']=b'{ }'
            if case=='status':args=reply(status=409)
            if case=='replay':client.response(**args)
            client.response(**args)
    assert client.stopped
    with pytest.raises(ValueError):client.request('GET','/rocell/characterization/status')
