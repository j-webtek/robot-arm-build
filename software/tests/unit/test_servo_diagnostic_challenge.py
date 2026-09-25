import copy
import socket

import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_diagnostic_challenge import DiagnosticChallengeReader,CHALLENGE
from rocell.application.servo_diagnostic_http import DiagnosticHTTPReader
from test_servo_diagnostic_http import server,response
from test_servo_start_authorization import fixture


def test_explicit_discovery_retains_exact_response_and_never_refreshes():
    _,challenge=fixture();raw=canonical(challenge)
    with server([response(raw)]) as (port,requests):
        reader=DiagnosticChallengeReader('127.0.0.1',port)
        result=reader.discover(challenge['boot_id'])
        with pytest.raises(ValueError,match='consumed'):reader.discover(challenge['boot_id'])
    assert len(requests)==1 and requests[0].startswith(b'GET '+CHALLENGE.encode()+b' ')
    assert result['challenge']==challenge and result['response_body'].encode()==raw
    assert not result['provenance_verified'] and not result['progression_authority']


@pytest.mark.parametrize('fault',['boot','nonce','expiry','extra','duplicate'])
def test_invalid_challenge_is_terminal(fault):
    _,challenge=fixture();changed=copy.deepcopy(challenge)
    if fault=='boot':changed['boot_id']='f'*32
    if fault=='nonce':changed['nonce']='short'
    if fault=='expiry':changed['expires_us']=changed['issued_us']
    if fault=='extra':changed['key']='unexpected'
    raw=canonical(changed)
    if fault=='duplicate':raw=raw.replace(b'"issued_us":1000',b'"issued_us":1000,"issued_us":1000')
    with server([response(raw)]) as (port,requests):
        reader=DiagnosticChallengeReader('127.0.0.1',port)
        with pytest.raises(ValueError):reader.discover(challenge['boot_id'])
        with pytest.raises(ValueError,match='consumed'):reader.discover(challenge['boot_id'])
    assert len(requests)==1


def test_generic_reader_cannot_initialize_a_challenge(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Unexpected socket')
    monkeypatch.setattr(socket,'socket',forbidden)
    with pytest.raises(ValueError):
        DiagnosticHTTPReader('127.0.0.1')(CHALLENGE,maximum_bytes=512,timeout_seconds=3)
    reader=DiagnosticChallengeReader('127.0.0.1')
    with pytest.raises(ValueError):reader.discover('unknown')
