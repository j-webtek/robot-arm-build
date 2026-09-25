"""Read-only protected-key probe in the motion worker's Windows Job limits.

No serial, camera, motion intent, key creation or rotation. The child prints
only availability/error codes, never key material or the protected blob.
This is a diagnostic, not an admission or a replay of a motion request.
"""
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import time

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE/'software'/'src'))


def child():
    from rocell.providers.windows.bench_review_key import load_host_observational_review_authority
    try:
        load_host_observational_review_authority(WORKSPACE)
        result = dict(status='KEY_LOAD_OK', error_type=None, winerror=None)
    except Exception as error:
        result = dict(status='KEY_LOAD_FAILED', error_type=type(error).__name__,
                      winerror=getattr(error, 'winerror', ctypes.get_last_error()))
        known = ('Windows current-user DPAPI required', 'DPAPI operation failed',
                 'DPAPI output outside budget', 'Protected review key domain or length mismatch',
                 'Could not determine home directory.')
        result['diagnostic'] = str(error) if str(error) in known else 'UNCLASSIFIED_KEY_LOAD_ERROR'
    result.update(device_access=False, key_provisioned=False, motion_authorized=False)
    print(json.dumps(result), flush=True)
    return 0 if result['status'] == 'KEY_LOAD_OK' else 1


def main():
    from rocell.providers.windows._owned_worker_win32 import WindowsOwnedPassivePipeProcess
    from rocell.providers.windows.owned_worker_process import WorkerProcessRegistration, PinnedWorkerFile
    from rocell.providers.windows.observational_native_protocol import fixed_budget
    def pin(path):
        return PinnedWorkerFile(path, hashlib.sha256(path.read_bytes()).hexdigest())
    script = Path(__file__).resolve()
    registration = WorkerProcessRegistration('bench-key-read-only-probe',
        pin(Path(sys._base_executable).resolve()), ('-I', '-S', str(script), '--child'),
        (pin(script),), WORKSPACE, fixed_budget())
    backend = WindowsOwnedPassivePipeProcess()
    started = time.monotonic_ns()
    report = dict(schema='rocell.bench_key_process_probe.v1', device_access=False,
                  key_provisioned=False, motion_authorized=False)
    try:
        backend.pin(registration)
        backend.start(registration, b'{}\n', check=lambda: None)
        while not backend.poll(registration.budget):
            if time.monotonic_ns()-started > 15_000_000_000:
                raise TimeoutError('Key readiness probe exceeded 15 seconds')
            time.sleep(.01)
    except Exception as error:
        report['supervisor_error_type'] = type(error).__name__
    finally:
        report['cleanup_errors'] = backend.cleanup(time.monotonic_ns()+2_000_000_000)
    report.update(returncode=backend.returncode, tree_exit_confirmed=backend.tree_exited,
                  elapsed_ms=round((time.monotonic_ns()-started)/1e6),
                  stdout=backend.stdout.decode('utf-8', errors='replace'),
                  stderr=backend.stderr.decode('utf-8', errors='replace'))
    print(json.dumps(report, indent=2))
    return 0 if backend.returncode == 0 and not report['cleanup_errors'] else 1


if __name__ == '__main__':
    if sys.argv[1:] == ['--child']:
        raise SystemExit(child())
    if sys.argv[1:]:
        raise SystemExit('This fixed read-only probe accepts no options.')
    raise SystemExit(main())
