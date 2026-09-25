"""Real package/evidence preparation using synthetic approvals; never launch."""

from pathlib import Path
from threading import Event
import hashlib
import pytest
from rocell.application import endpoint_worker_preparation as module
from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.endpoint_reference_reader import source_fingerprint,import_build_snapshot
from rocell.application.physical_onboarding_durability import publish_bytes,PublicationMode
from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker
from rocell.safety.bench_review_authority import BenchReviewAuthority
from test_endpoint_reference_reader import prepare
from test_bench_review_authority import originals
from test_endpoint_current_context import fixture as context_fixture
from rocell.application.physical_connection_contracts import _canonical_bytes


def setup(tmp_path,monkeypatch):
    workspace = Path(__file__).resolve().parents[3]
    original = prepare(tmp_path,source_fingerprint(workspace),import_build_snapshot(workspace).snapshot_hash)
    data = original.to_dict()
    _,_,_,binding = context_fixture()
    native = _canonical_bytes(binding.to_dict())
    data['references']['native_controller_review_sha256']=hashlib.sha256(native).hexdigest()
    publish_bytes(tmp_path,data['attempt_id']+'-native_controller_review_sha256.original.json',
                  native,mode=PublicationMode.REPLACE)
    data['deadline_monotonic_ns']=31_000_000_000
    req = EndpointTrialRequest(_canonical(data))
    authority = BenchReviewAuthority(b'test-only-preparation-secret-12345')
    signed = authority.seal(req,originals(req),now_ns=1_000_000_000)
    publish_bytes(tmp_path,data['attempt_id']+'-bench-reviews.json',signed,mode=PublicationMode.IMMUTABLE)
    monkeypatch.setattr(module,'load_host_bench_review_authority',lambda _:authority)
    kwargs = dict(review_root=tmp_path,session_id='wizard-'+'c'*32,clock_ns=lambda:1_000_000_000)
    return workspace,req,kwargs


def test_prepared_package_is_exact_reserved_and_still_cannot_launch(tmp_path,monkeypatch):
    workspace,req,kwargs = setup(tmp_path,monkeypatch)
    prepared = module.prepare_endpoint_worker(workspace,req,**kwargs)
    assert len(prepared.registration.package_files)==3
    assert len(list(tmp_path.glob('*-endpoint-worker-launch.json')))==1
    def forbidden(*a,**k): pytest.fail('Preparation must not enable native launch')
    worker = OwnedWindowsWorker(prepared.registration,authorizer=forbidden,_backend_factory=forbidden,
                                _clock=lambda:1_000_000_000)
    result = worker.run(prepared.request,cancellation=Event(),deadline_ns=prepared.request.expires_at_ns)
    assert not result.process_created
    with pytest.raises(Exception): module.prepare_endpoint_worker(workspace,req,**kwargs)


def test_bad_review_refused_before_artifact_directory(tmp_path,monkeypatch):
    workspace,req,kwargs = setup(tmp_path,monkeypatch)
    publish_bytes(tmp_path,req.to_dict()['attempt_id']+'-bench-reviews.json',b'{}',mode=PublicationMode.REPLACE)
    with pytest.raises(ValueError): module.prepare_endpoint_worker(workspace,req,**kwargs)
    assert not list(tmp_path.glob('*-endpoint-native-child'))
    assert not list(tmp_path.glob('*-endpoint-worker-launch.json'))


def test_time_spent_preparing_does_not_extend_deadline(tmp_path,monkeypatch):
    workspace,req,kwargs = setup(tmp_path,monkeypatch)
    tick = [1_000_000_000]
    original = module.prepare_snapshot
    def delayed(*a,**k):
        path = original(*a,**k)
        tick[0]+=4_000_000_000
        return path
    monkeypatch.setattr(module,'prepare_snapshot',delayed)
    kwargs['clock_ns']=lambda:tick[0]
    with pytest.raises(ValueError): module.prepare_endpoint_worker(workspace,req,**kwargs)
    assert list(tmp_path.glob('*-endpoint-native-child'))
    assert not list(tmp_path.glob('*-endpoint-worker-launch.json'))
