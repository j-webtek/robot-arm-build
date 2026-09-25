"""Export recovery from synthetic owned-process bytes, without device activity."""
import base64
import hashlib
import json
from pathlib import Path
import pytest

from rocell.application.wizard_first_motion_coordinator import FirstMotionRunOutcome
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from test_arrival_wizard_service import make_service, _run


@pytest.mark.parametrize('size', [0, 1000, 256*1024])
def test_failed_publication_exports_original_streams(make_service, size):
    service, runner, _ = make_service(mode='physical')
    stdout = (bytes(range(256))*1024)[:size]
    stderr = b'Synthetic failure only.\x00\xff'
    owned = OwnedWorkerResult(status='FAILED', primary_error='SYNTHETIC_FAILURE',
        cleanup_errors=(), request_sha256='a'*64, attempt_id='operation-'+'b'*32,
        process_created=False, initial_thread_resumed=False, tree_exit_confirmed=False,
        returncode=None, elapsed_ns=100, stdin_bytes_written=0, peak_observed_handles=0,
        peak_active_processes=0, stdout=stdout, stderr=stderr)
    service._first_motion_outcome = FirstMotionRunOutcome('RETENTION_FAILED', owned, None, None, 'OSError')
    operation = _run(service, 'export_logs')
    assert operation['status'] == 'SUCCEEDED', operation
    folder = Path(operation['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    saved = json.loads((folder/'attachment-first-motion-native-logs.json').read_bytes())
    for name, raw in [('stdout', stdout), ('stderr', stderr)]:
        decoded = b''.join(base64.b64decode(chunk, validate=True) for chunk in saved[name+'_base64_chunks'])
        assert decoded == raw
        assert saved['process'][name+'_sha256'] == hashlib.sha256(decoded).hexdigest()
    assert saved['stage'] == 'RETENTION_FAILED'
    assert not saved['physical_movement_verified'] and not saved['replay_allowed']
    assert service._first_motion_outcome.owned is owned
    assert not runner.calls
