import hashlib
from pathlib import Path

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.observational_worker_preparation import stage_observational_runtime, prepare_observational_worker
from rocell.safety.observational_review_authority import ObservationalIntent
from rocell.safety.bench_review_authority import BenchReviewAuthority
from rocell.providers.windows.owned_worker_process import owned_registration_document
from test_endpoint_current_context import fixture as endpoint_fixture
from test_observational_review_authority import intent, review


def fixture(tmp_path, monkeypatch):
    from rocell.providers.windows import bench_review_key
    workspace = Path(__file__).resolve().parents[3]
    _, _, _, binding = endpoint_fixture()
    controller = canonical(binding.to_dict())
    protocol = b'{"synthetic":"not-real-protocol-approval"}'
    body = intent()
    staged = stage_observational_runtime(workspace, root=tmp_path, attempt_id=body['attempt_id'],
        controller_original=controller, protocol_original=protocol)
    body['deadline_ns'] = 31_000_000_000
    body['references'] = dict(source_sha256=staged.source_sha256,
        runtime_sha256=hashlib.sha256(canonical(owned_registration_document(staged.registration))).hexdigest(),
        native_controller_review_sha256=hashlib.sha256(controller).hexdigest(),
        protocol_review_sha256=hashlib.sha256(protocol).hexdigest())
    request = ObservationalIntent(canonical(body))
    authority = BenchReviewAuthority(b'Q'*32).for_observational_motion()
    monkeypatch.setattr(bench_review_key, 'load_host_observational_review_authority', lambda _: authority)
    signed = authority.seal(body, review(), now_ns=1_000_000_002)
    return workspace, staged, request, signed, controller, protocol


def test_stage_then_finalize_without_device_or_process(tmp_path, monkeypatch):
    workspace, staged, request, signed, controller, protocol = fixture(tmp_path, monkeypatch)
    with pytest.raises(FileExistsError):
        stage_observational_runtime(workspace, root=tmp_path, attempt_id=request.to_dict()['attempt_id'],
            controller_original=controller, protocol_original=protocol)
    prepared = prepare_observational_worker(workspace, staged, request,
        review_original=signed, clock_ns=lambda: 2_000_000_000)
    assert prepared.request.attempt_id == request.to_dict()['attempt_id']
    assert prepared.registration == staged.registration
    with pytest.raises(Exception):
        prepare_observational_worker(workspace, staged, request, review_original=signed, clock_ns=lambda: 2_000_000_000)


@pytest.mark.parametrize('fault', ['controller','runtime','review','deadline','key'])
def test_finalize_refuses_changed_or_missing_evidence(tmp_path, monkeypatch, fault):
    from rocell.providers.windows import bench_review_key
    workspace, staged, request, signed, _, _ = fixture(tmp_path, monkeypatch)
    now = 2_000_000_000
    if fault in ('controller','runtime'):
        (staged.registration.working_directory/(fault+'.original.json')).write_bytes(b'{}')
    if fault == 'review': signed = b'{}'
    if fault == 'deadline': now = 10_000_000_000
    if fault == 'key':
        def missing(_): raise ValueError('Synthetic missing key')
        monkeypatch.setattr(bench_review_key, 'load_host_observational_review_authority', missing)
    with pytest.raises(ValueError):
        prepare_observational_worker(workspace, staged, request, review_original=signed, clock_ns=lambda: now)
    assert not (tmp_path/(request.to_dict()['attempt_id']+'-observational-launch.json')).exists()
