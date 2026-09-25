"""Real-file preparation timing with synthetic evidence and NO native dispatch."""
import time
from threading import Event
import pytest

from rocell.application import wizard_first_motion_coordinator as coordinator
from rocell.application.first_motion_draft import FirstMotionDraft
from rocell.application.first_motion_review_intake import record_decision
from rocell.application.first_motion_reference_reader import ORIGINAL_REFERENCES
from rocell.safety.first_motion_review_authority import FirstMotionReviewAuthority, ENGINEERING_CHECKS, OPERATOR_CHECKS
from test_first_motion_worker_preparation import setup
from test_first_motion_measurement_binding import SESSION, OPERATION


@pytest.mark.parametrize('sample', range(3))
@pytest.mark.parametrize('parent_prelaunch', [False, True])
def test_real_file_pipeline_reaches_dispatch_boundary_within_budget(tmp_path, monkeypatch, record_property, sample, parent_prelaunch):
    workspace, original, _ = setup(tmp_path, monkeypatch)
    draft = FirstMotionDraft.from_request(original)
    prefix = original.to_dict()['attempt_id']
    references = {name:(tmp_path/(prefix+'-'+name+'.original.json')).read_bytes()
                  for name in ORIGINAL_REFERENCES}
    receipts = []
    for index, check in enumerate(sorted(ENGINEERING_CHECKS)):
        operation = 'operation-'+format(index, '032x')
        report = record_decision(dict(draft_json=draft.canonical_bytes.decode(),
            reviewer_id='synthetic-timing', check=check, decision='APPROVED',
            detail='Synthetic performance test; no actual physical review.'),
            root=tmp_path, operation_id=operation,
            source_sha256=original.to_dict()['references']['source_sha256'], now_ns=2_000_000_000)
        receipts.append((operation, report['review_sha256']))
    monkeypatch.setattr(coordinator, 'load_host_first_motion_review_authority',
                        lambda _:FirstMotionReviewAuthority(b'a'*32))
    boundary = []
    # Replace the entire supervisor at construction: this test cannot create a
    # native worker, claim a controller, load native I/O or issue serial commands.
    def forbidden_worker(*args, **kwargs):
        boundary.append(time.perf_counter_ns())
        raise RuntimeError('SYNTHETIC_TEST_STOP_BEFORE_NATIVE_DISPATCH')
    monkeypatch.setattr(coordinator, 'OwnedWindowsWorker', forbidden_worker)
    values = dict.fromkeys(OPERATOR_CHECKS, True)
    values.update(operator_id='synthetic-timing', selection_sha256=draft.selection_sha256)
    started = time.perf_counter_ns()
    clock = lambda:2_000_000_000+time.perf_counter_ns()-started
    if parent_prelaunch:
        from rocell.providers.windows import owned_worker_process as supervisor, first_motion_prelaunch
        # Cleanup uses the module clock directly; keep its origin aligned with
        # the advancing synthetic request clock, not the host boot-time origin.
        monkeypatch.setattr(supervisor.time, 'monotonic_ns', clock)
        monkeypatch.setattr(first_motion_prelaunch, 'load_host_first_motion_review_authority',
                            lambda _:FirstMotionReviewAuthority(b'a'*32))
        class IncapableBackend:
            pid = 0
            created = resumed = tree_exited = False
            returncode = None
            stdout = stderr = b''
            written = peak_handles = peak_processes = 0
            def pin(self, registration): pass
            def start(self, registration, wire, *, check):
                check()
                boundary.append(time.perf_counter_ns())
                raise RuntimeError('SYNTHETIC_STOP_NO_NATIVE_PROCESS')
            def cleanup(self, deadline):
                # The incapable backend has no process tree to leave alive.
                # Report that fact so tests do not set the real cleanup latch.
                self.tree_exited = True
                return ()
        monkeypatch.setattr(coordinator, 'OwnedWindowsWorker',
            lambda registration, authorizer: supervisor.OwnedWindowsWorker(registration,
                authorizer=authorizer, _backend_factory=IncapableBackend, _clock=clock))
    result = coordinator.run_confirmed_first_motion(workspace, draft, values,
        attempt_id='operation-'+'f'*32, reference_originals=references,
        review_selections=tuple(receipts), review_root=tmp_path, export_root=tmp_path,
        session_id=SESSION, measurement_operation_id=OPERATION, cancellation=Event(),
        check_current=lambda:None, clock_ns=clock, accepted_ns=2_000_000_000)
    elapsed = time.perf_counter_ns()-started
    record_property('pre_dispatch_elapsed_ms', elapsed/1_000_000)
    record_property('terminal_stage', result.stage)
    record_property('parent_prelaunch', parent_prelaunch)
    if result.owned is not None:
        record_property('supervisor_error', result.owned.primary_error)
        assert not result.owned.process_created and not result.owned.initial_thread_resumed
    assert not list(tmp_path.glob('*-first_motion-worker-claimed.json'))
    assert boundary, f'Pipeline did not reach blocked dispatch: {result.stage}, {elapsed/1e6:.1f} ms'
    assert result.stage == ('RETAINED' if parent_prelaunch else 'SUPERVISION_FAILED')
