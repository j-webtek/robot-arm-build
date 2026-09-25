"""Actual correlation of synthetic streams, worker receipts and observations."""
import os
from dataclasses import replace
import pytest
from rocell.application.first_motion_qualification import assess_first_motion_evidence
from rocell.application.first_motion_observation import record_observation
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.providers.windows.first_motion_native_protocol import decode_request, validate_payload
from rocell.providers.windows.first_motion_result_publication import publish_first_motion_result
from test_first_motion_result_publication import fixture
from test_first_motion_observation import values


@pytest.mark.parametrize('fault', [None, 'no_movement', 'partial', 'missing_owner', 'cleanup', 'wrong_pid', 'different_bytes'])
def test_assessment_requires_both_evidence_chains(tmp_path, fault):
    request_raw, stdout = fixture(tmp_path)
    wire = decode_request(request_raw)
    req = validate_payload(wire['payload'])
    output = tmp_path/'out'; output.mkdir()
    observations = tmp_path/'observations'; observations.mkdir()
    _, report = publish_first_motion_result(output, request_raw=request_raw, stdout=stdout, stderr=b'',
        owned_process_id=os.getpid(), returncode=0, process_tree_closed=True, finished_ns=40_000_000_000)
    owned = OwnedWorkerResult(status='SUCCEEDED', primary_error=None, cleanup_errors=(),
        request_sha256=wire['request_sha256'], attempt_id=wire['attempt_id'], process_created=True,
        initial_thread_resumed=True, tree_exit_confirmed=True, returncode=0, elapsed_ns=1,
        stdin_bytes_written=len(request_raw), peak_observed_handles=1, peak_active_processes=1,
        stdout=stdout, stderr=b'', owned_process_id=os.getpid(), finished_monotonic_ns=40_000_000_000)
    inputs = values('NO_MOVEMENT' if fault == 'no_movement' else 'EXPECTED_MOVEMENT')
    if fault == 'partial': inputs['coverage'] = 'PARTIAL'
    if fault == 'missing_owner': owned = None
    if fault == 'cleanup': owned = replace(owned, cleanup_errors=('synthetic failure',))
    if fault == 'wrong_pid': owned = replace(owned, owned_process_id=os.getpid()+1)
    if fault == 'different_bytes': owned = replace(owned, stdout=b'other')
    receipt = record_observation(req, canonical(report), inputs, root=observations,
        operation_id='operation-'+'9'*32, recorded_ns=50_000_000_000)
    kwargs = dict(result_root=output, observation_root=observations, observation_receipt=receipt, owned_result=owned)
    if fault in ('wrong_pid','different_bytes'):
        with pytest.raises(ValueError): assess_first_motion_evidence(req, **kwargs)
    else:
        assessment = assess_first_motion_evidence(req, **kwargs)
        assert assessment['status'] == ('HELD' if fault else 'READY_FOR_EXPLICIT_QUALIFICATION_REVIEW')
        assert not assessment['campaign_advance_allowed']
        assert not assessment['physical_movement_verified']
