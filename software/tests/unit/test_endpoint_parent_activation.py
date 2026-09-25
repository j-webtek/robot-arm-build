"""Real parent admission with an incapable injected process backend."""

from threading import Event
import pytest
from rocell.application import endpoint_worker_preparation as preparation
from rocell.providers.windows import bench_review_key
from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker
from rocell.providers.windows import owned_worker_process as supervisor
from test_endpoint_worker_preparation import setup


def test_authenticated_reserved_request_reaches_only_injected_backend(tmp_path,monkeypatch):
    workspace,req,kwargs = setup(tmp_path,monkeypatch)
    monkeypatch.setattr(bench_review_key,'load_host_bench_review_authority',preparation.load_host_bench_review_authority)
    prepared = preparation.prepare_endpoint_worker(workspace,req,**kwargs)
    # Both the admission and cleanup clocks belong to this incapable fixture.
    # Mixing its synthetic deadline with real uptime creates a false cleanup hold.
    monkeypatch.setattr(supervisor.time,'monotonic_ns',lambda:1_000_000_000)
    calls = []
    class IncapableBackend:
        pid = 123
        created = resumed = tree_exited = False
        returncode = 1
        stdout = b'fake child failed without any device access'
        stderr = b''
        written = peak_handles = peak_processes = 0
        def pin(self,reg): calls.append('pin')
        def start(self,reg,wire,*,check):
            check()
            calls.append('start')
            self.created=self.resumed=True
        def poll(self,budget):
            self.tree_exited=True
            return True
        def cleanup(self,deadline):
            calls.append('cleanup')
            return ()
    def authorize(reg,outer,digest):
        assert reg==prepared.registration and outer==prepared.request
        calls.append('authorize')
    worker = OwnedWindowsWorker(prepared.registration,authorizer=authorize,
        _backend_factory=IncapableBackend,_clock=lambda:1_000_000_000)
    result = worker.run(prepared.request,cancellation=Event(),deadline_ns=prepared.request.expires_at_ns)
    assert calls==['pin','authorize','start','cleanup']
    assert result.status=='FAILED' and result.primary_error=='WORKER_EXIT_FAILED'
    assert result.cleanup_errors==()
    assert result.stdout==IncapableBackend.stdout
    with pytest.raises(ValueError):
        worker.run(prepared.request,cancellation=Event(),deadline_ns=prepared.request.expires_at_ns)
