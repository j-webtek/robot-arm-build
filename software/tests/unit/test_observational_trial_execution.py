import hashlib
from threading import Event

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.observational_worker_claim import reserve_observational_launch, claim_observational_worker
from rocell.providers.windows.observational_serial_api import WindowsObservationalSerialApi
from rocell.providers.windows.observational_trial_execution import execute_native_observational_trial
from test_observational_admission import prepared


def fixture(tmp_path, monkeypatch):
    import test_observational_current_context as context
    original = context.intent
    runtime = canonical({'synthetic': 'not-a-qualified-runtime'})
    def intent():
        body = original()
        body['references']['runtime_sha256'] = hashlib.sha256(runtime).hexdigest()
        return body
    monkeypatch.setattr(context, 'intent', intent)
    request, permit, _, _, clock, port = prepared(tmp_path)
    review = (tmp_path/(request.to_dict()['attempt_id']+'-observational-reviews.json')).read_bytes()
    launch = reserve_observational_launch(tmp_path, request, runtime_original=runtime,
        review_bundle_sha256=hashlib.sha256(review).hexdigest(), now_ns=clock[0])
    refs = request.to_dict()['references']
    claim = claim_observational_worker(tmp_path, request, launch_sha256=launch,
        current_source_sha256=refs['source_sha256'], current_runtime_sha256=refs['runtime_sha256'], now_ns=clock[0])
    def forbidden(*args, **kwargs):
        pytest.fail('Native I/O is forbidden in this composition test')
    monkeypatch.setattr(WindowsObservationalSerialApi, '_load_kernel', forbidden)
    api = WindowsObservationalSerialApi.from_observational_permit(request, permit,
        port_name=port, connection_id=request.to_dict()['attempt_id'])
    return request, permit, api, claim, refs, clock


def test_cancelled_child_consumes_claim_without_opening_device(tmp_path, monkeypatch):
    request, permit, api, claim, refs, clock = fixture(tmp_path, monkeypatch)
    cancellation = Event()
    cancellation.set()
    result = execute_native_observational_trial(request, permit, api, worker_claim=claim,
        current_source_sha256=refs['source_sha256'], current_runtime_sha256=refs['runtime_sha256'],
        cancellation=cancellation, clock_ns=lambda: clock[0])
    assert result['status'] == 'CANCELLED_BEFORE_OPEN'
    assert result['lifecycle']['owned_handle_count'] == 0
    assert result['lifecycle']['confirmed_write_bytes'] == 0
    assert result['trial'] is None
    with pytest.raises(ValueError):
        claim.consume(request, current_source_sha256=refs['source_sha256'],
            current_runtime_sha256=refs['runtime_sha256'], now_ns=clock[0])


def test_wrong_runtime_cannot_reach_connection_open(tmp_path, monkeypatch):
    request, permit, api, claim, refs, clock = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        execute_native_observational_trial(request, permit, api, worker_claim=claim,
            current_source_sha256=refs['source_sha256'], current_runtime_sha256='f'*64,
            cancellation=Event(), clock_ns=lambda: clock[0])
