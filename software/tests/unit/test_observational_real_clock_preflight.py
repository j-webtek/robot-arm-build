"""Real-clock host preflight measurement with an incapable process backend.

No native process, real key lookup or device access. This measures preparation,
rechecks and optionally real-time capture with synthetic metadata/serial callbacks.
It does not measure serial opening, servo motion or native cleanup.
"""
import json
from threading import Event
import time
from dataclasses import replace
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.observational_worker_preparation import prepare_observational_worker
from rocell.providers.windows import bench_review_key, observational_prelaunch
from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker
from rocell.safety.observational_review_authority import ObservationalIntent, CHECKS
from test_observational_worker_preparation import fixture


@pytest.mark.parametrize('exercise_child', [False, True])
def test_actual_host_preflight_fits_signed_budget(tmp_path, monkeypatch, record_testsuite_property, exercise_child):
    workspace, staged, template, _, _, _ = fixture(tmp_path, monkeypatch)
    authority = bench_review_key.load_host_observational_review_authority(workspace)  # Synthetic fixture key.
    monkeypatch.setattr(observational_prelaunch, 'load_host_observational_review_authority', lambda _: authority)
    marks = {'accepted': time.monotonic_ns()}
    body = template.to_dict()
    body.update(issued_ns=marks['accepted'], deadline_ns=marks['accepted']+30_000_000_000)
    request = ObservationalIntent(canonical(body))
    signed = authority.seal(body, dict(operator_id='synthetic-timing', recorded_ns=marks['accepted'],
        checks=dict.fromkeys(CHECKS, True)), now_ns=time.monotonic_ns())
    prepared = prepare_observational_worker(workspace, staged, request, review_original=signed)
    marks['prepared'] = time.monotonic_ns()
    trial_results = []
    if exercise_child:
        from rocell.providers.windows import observational_child_execution as child
        from rocell.application.observational_owned_trial import run_owned_observational_trial
        from rocell.application.endpoint_owned_trial import EndpointCleanupResult
        from test_endpoint_current_context import fixture as context_fixture
        _, snapshots, _, _ = context_fixture()

        def synthetic_metadata():
            tick = time.monotonic_ns()
            return replace(snapshots[0], started_monotonic_ns=tick, finished_monotonic_ns=tick)

        monkeypatch.setattr(child, 'WindowsControllerMetadataAcquirer', lambda **kwargs: synthetic_metadata)
        monkeypatch.setattr(child, 'load_host_observational_review_authority', lambda _: authority)
        monkeypatch.setattr(child.WindowsObservationalSerialApi, '_load_kernel',
            lambda *args: pytest.fail('No native kernel access allowed in timing rehearsal'))

        def incapable_trial(actual, permit, api, **kwargs):
            marks['child_admitted'] = time.monotonic_ns()
            kwargs['worker_claim'].consume(actual,
                current_source_sha256=kwargs['current_source_sha256'],
                current_runtime_sha256=kwargs['current_runtime_sha256'], now_ns=time.monotonic_ns())
            connection = actual.to_dict()['attempt_id']
            port = snapshots[0].native_observations[0].port_name
            # The real facade factory already consumed the one-open claim.
            # Validate it here without invoking the operating-system open.
            permit.validate_native_open(actual, connection, port)
            simulated = dict(angle=.02, writes=0, closes=0)

            original_bind = permit.bind_owned_baseline
            def diagnostic_bind(*args, **kw):
                try:
                    return original_bind(*args, **kw)
                except Exception as exc:
                    simulated['binding_error'] = repr(exc)
                    raise
            monkeypatch.setattr(permit, 'bind_owned_baseline', diagnostic_bind)

            def read(size, timeout):
                # Real elapsed capture windows, synthetic frames and no OS I/O.
                time.sleep(min(25, timeout/2)/1000)
                return json.dumps(dict(T=1051, x=1, y=2, z=3, tit=0, b=0, s=0, e=0,
                    t=simulated['angle'], r=0, g=0), separators=(',', ':')).encode()+b'\n'

            def write(payload):
                try:
                    permit.claim_native_dispatch(actual, connection, port)
                except Exception as exc:
                    simulated['dispatch_error'] = repr(exc)
                    raise
                simulated['writes'] += 1
                simulated['angle'] = json.loads(payload)['rad']
                return len(payload)

            def close(timeout):
                simulated['closes'] += 1
                return EndpointCleanupResult(True, 0)

            trial = run_owned_observational_trial(actual, permit, connection_id=connection,
                port_name=port, read_once=read, write_once=write, close_once=close,
                cancellation=Event(), basis='SYNTHETIC_WIRE_REHEARSAL')
            marks['trial_completed'] = time.monotonic_ns()
            trial_results.append((trial, simulated))
            return trial

        monkeypatch.setattr(child, 'execute_native_observational_trial', incapable_trial)

    class IncapableProcess:
        created = resumed = tree_exited = False
        returncode = None
        pid = written = peak_handles = peak_processes = 0
        stdout = stderr = b''

        def pin(self, registration):
            marks['backend_reached'] = time.monotonic_ns()

        def start(self, registration, wire, *, check):
            check()
            marks['resume_check_completed'] = time.monotonic_ns()
            if exercise_child:
                try:
                    child.execute_observational_child(workspace, wire, cancellation=Event())
                except Exception as exc:
                    trial_results.append(('child_error', repr(exc)))
                    raise
            raise ValueError('INCAPABLE_TIMING_BOUNDARY')

        def cleanup(self, deadline):
            return ()

    result = OwnedWindowsWorker(prepared.registration, authorizer=lambda *args: None,
        _backend_factory=IncapableProcess).run(prepared.request, cancellation=Event(),
        deadline_ns=prepared.request.expires_at_ns)
    timing = {key+'_ms': round((value-marks['accepted'])/1e6, 3) for key,value in marks.items()}
    timing['hardware_accessed'] = False
    timing['supervisor_error'] = result.primary_error
    record_testsuite_property('host_preflight_timing', json.dumps(timing, sort_keys=True))
    print(json.dumps(timing, sort_keys=True))
    assert 'resume_check_completed' in marks, (result.to_dict(), timing)
    assert result.process_created is False and result.cleanup_errors == ()
    if exercise_child:
        assert len(trial_results) == 1, (result.to_dict(), timing)
        trial, simulated = trial_results[0]
        assert trial != 'child_error', simulated
        assert trial['status'] == 'AWAITING_OPERATOR_OBSERVATION', (trial['errors'], simulated, trial['baseline']['status'])
        assert trial['basis'] == 'SYNTHETIC_WIRE_REHEARSAL'
        assert simulated['writes'] == simulated['closes'] == 1
        assert trial['campaign_advance_allowed'] is False
