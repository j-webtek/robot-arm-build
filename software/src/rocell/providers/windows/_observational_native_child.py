"""Isolated observational entry; execute-one requires a reserved signed intent."""
import hashlib
import json
from pathlib import Path
import sys


def main():
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv) != 4:
        return 2
    path = Path(sys.argv[1])
    if not path.is_absolute() or path.name != 'observational-native.zip':
        return 3
    if sys.argv[3] not in ('check-imports', 'execute-one'):
        return 5
    with path.open('rb') as stream:
        raw = stream.read(8*1024*1024+1)
    if len(raw) > 8*1024*1024 or hashlib.sha256(raw).hexdigest() != sys.argv[2]:
        return 4
    import ctypes
    import subprocess
    import socket
    import os
    def forbidden(*args, **kwargs):
        raise RuntimeError('OBSERVATIONAL_IMPORT_CHECK_HOST_ACCESS_FORBIDDEN')
    if sys.argv[3] == 'check-imports':
        ctypes.WinDLL = forbidden
        subprocess.Popen = forbidden
        socket.socket = forbidden
        os.open = forbidden
    sys.path.insert(0, str(path))
    from rocell.safety.observational_review_authority import ObservationalIntent
    from rocell.safety.observational_admission import admit_observational
    from rocell.application.observational_worker_claim import claim_observational_worker
    from rocell.application.observational_owned_trial import run_owned_observational_trial
    from rocell.application.observational_result_review import review_completed_observational_trial
    from rocell.providers.windows.observational_native_protocol import decode_request
    from rocell.providers.windows.observational_native_result import decode_result, encode_result
    from rocell.providers.windows.observational_current_context import AuthenticatedObservationalReader
    from rocell.providers.windows.observational_trial_execution import execute_native_observational_trial
    from rocell.providers.windows.observational_serial_api import WindowsObservationalSerialApi
    from rocell.providers.windows.bench_review_key import load_host_observational_review_authority
    from rocell.providers.windows.observational_child_execution import execute_observational_child
    if sys.argv[3] == 'execute-one':
        from threading import Event
        try:
            request_raw = sys.stdin.buffer.read(65537)
            wire = decode_request(request_raw)
            registration = wire['payload']['registration']
            # Match the actual interpreter/entry/archive invocation, not just
            # an internally consistent registration supplied over stdin.
            if (registration.get('argv') != ['-I','-S']+sys.argv
                    or registration.get('executable', {}).get('path') != sys.executable):
                raise ValueError('Actual observational invocation differs from registration')
            pins = registration.get('package_files')
            if (type(pins) is not list or len(pins) != 4
                    or pins[0].get('path') != str(Path(__file__).resolve())
                    or pins[1].get('path') != str(path) or pins[1].get('sha256') != sys.argv[2]):
                raise ValueError('Actual observational entry/archive pins differ')
            for pin in (registration['executable'], pins[0]):
                with Path(pin['path']).open('rb') as stream:
                    original = stream.read(32*1024*1024+1)
                if len(original) > 32*1024*1024 or hashlib.sha256(original).hexdigest() != pin['sha256']:
                    raise ValueError('Actual observational executable/entry changed')
            child = execute_observational_child(Path(__file__).resolve().parents[5], request_raw, cancellation=Event())
            sys.stdout.buffer.write(encode_result(child, wire=wire))
            sys.stdout.buffer.flush()
            return 0
        except Exception as error:
            sys.stdout.buffer.write(json.dumps(dict(schema='rocell.observational_child_error.v1',
                error_type=type(error).__name__, physical_authority=False, replay_allowed=False)).encode('ascii'))
            sys.stdout.buffer.flush()
            return 1
    report = dict(schema='rocell.observational_native_import_check.v1',
        status='IMPORTS_OK_NOT_HARDWARE_TESTED', native=WindowsObservationalSerialApi('COM4096').status(),
        physical_authority=False, connected=False, live_entry_enabled=False,
        registered_execution_mode='execute-one', signed_reserved_request_required=True)
    sys.stdout.buffer.write(json.dumps(report, sort_keys=True, separators=(',', ':')).encode('ascii'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
