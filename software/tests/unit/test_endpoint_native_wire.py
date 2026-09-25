"""Cross-request and canonical digest checks before native claiming/entry."""

import hashlib
import json

import pytest

from rocell.providers.windows.endpoint_native_wire import decode_request
from rocell.providers.windows.owned_worker_process import owned_request_wire
from rocell.application.arm_bench_qualification_contract import _canonical
from test_endpoint_native_registration import registration


def test_parent_wire_decodes_without_granting_authority(tmp_path):
    reg,outer = registration(tmp_path)
    raw,digest = owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
    result = decode_request(raw)
    assert result['request_sha256']==digest
    assert result['payload']['endpoint_request']['physical_authority'] is False


@pytest.mark.parametrize('field', ['attempt_id','session_id','source_sha256','operation_sha256',
                                  'selected_identity_sha256','registration_sha256',
                                  'expires_at_monotonic_ns','parent_deadline_monotonic_ns'])
def test_rehashed_cross_context_envelope_is_still_refused(tmp_path,field):
    reg,outer = registration(tmp_path)
    raw,_ = owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
    value = json.loads(raw)
    value[field] = 30_000_000_000 if field.endswith('_ns') else 'f'*64
    value['request_sha256'] = hashlib.sha256(_canonical({k:v for k,v in value.items() if k!='request_sha256'})).hexdigest()
    with pytest.raises(ValueError): decode_request(_canonical(value))


@pytest.mark.parametrize('raw',[b'{}',b'{"schema":1,"schema":2}',b'{}'*32769,b'{"T":104}'],
                         ids=['empty-envelope','duplicate-field','oversized','raw-command'])
def test_non_envelopes_and_oversized_input_refused(raw):
    with pytest.raises(ValueError): decode_request(raw)
