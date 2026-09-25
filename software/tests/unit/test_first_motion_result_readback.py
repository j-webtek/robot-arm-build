"""Readback of synthetic native publications, never physical qualification."""
import hashlib
import os
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.first_motion_result_readback import readback_first_motion_result
from rocell.providers.windows.first_motion_native_protocol import decode_request, validate_payload
from rocell.providers.windows.first_motion_result_publication import publish_first_motion_result
from test_first_motion_result_publication import fixture


@pytest.mark.parametrize('fault', [None, 'rejected', 'process', 'stream', 'summary', 'hash', 'request'])
def test_reconstruct_originals_without_physical_qualification(tmp_path, fault):
    request_raw, stdout = fixture(tmp_path)
    request = validate_payload(decode_request(request_raw)['payload'])
    output = tmp_path/'out'
    output.mkdir()
    path, report = publish_first_motion_result(output, request_raw=request_raw,
        stdout=b'bad child output' if fault == 'rejected' else stdout, stderr=b'',
        owned_process_id=os.getpid(), returncode=0, process_tree_closed=fault != 'process', finished_ns=40_000_000_000)
    if fault == 'stream':
        (output/report['originals']['stdout.bin']['file']).write_bytes(b'{}')
    if fault == 'summary':
        report['summary']['rebuilt_trial']['analysis']['post_count'] += 1
        path.write_bytes(canonical(report))
    if fault == 'request':
        from rocell.application.first_motion_contract import FirstMotionRequest
        body = request.to_dict()
        body['distal_radius_mm'] -= 1
        request = FirstMotionRequest(canonical(body))
    digest = 'f'*64 if fault == 'hash' else hashlib.sha256(path.read_bytes()).hexdigest()
    if fault in ('stream','summary','hash','request'):
        with pytest.raises(ValueError): readback_first_motion_result(output, request, expected_report_sha256=digest)
    else:
        review = readback_first_motion_result(output, request, expected_report_sha256=digest)
        assert review['telemetry_ready_for_review'] is (fault is None)
        assert not review['physical_movement_verified']
        assert not review['owned_process_reauthenticated']
        assert not review['campaign_advance_allowed']
        if fault == 'rejected': assert review['reconstructed_summary'] is None
