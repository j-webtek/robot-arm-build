"""Isolated commissioning entry; execute-one requires a reserved reviewed request."""
import hashlib
import json
from pathlib import Path
import sys


def main():
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv)!=4:
        return 2
    path=Path(sys.argv[1])
    if not path.is_absolute() or path.name!='first-motion-native.zip':
        return 3
    if sys.argv[3] not in {'check-imports','execute-one'}:
        return 5
    with path.open('rb') as stream:
        raw=stream.read(8*1024*1024+1)
    if len(raw)>8*1024*1024 or hashlib.sha256(raw).hexdigest()!=sys.argv[2]:
        return 4
    import ctypes
    import subprocess
    import socket
    import os
    def forbidden(*args,**kwargs):
        raise RuntimeError('COMMISSIONING_IMPORT_CHECK_HOST_ACCESS_FORBIDDEN')
    if sys.argv[3]=='check-imports':
        ctypes.WinDLL=forbidden
        subprocess.Popen=forbidden
        socket.socket=forbidden
        os.open=forbidden
    sys.path.insert(0,str(path))
    from rocell.application.first_motion_contract import FirstMotionRequest
    from rocell.application.first_motion_evidence_snapshot import FrozenFirstMotionReferences
    from rocell.providers.windows.first_motion_native_protocol import decode_request
    from rocell.providers.windows.first_motion_native_result import encode_result,decode_result
    from rocell.providers.windows.first_motion_child_execution import execute_first_motion_child
    from rocell.providers.windows.first_motion_native_registration import validate_registration
    from rocell.application.first_motion_reference_reader import FirstMotionReferenceReader
    from rocell.application.first_motion_result_retention import retain_first_motion_result
    from rocell.application.first_motion_result_review import review_completed_first_motion_trial
    from rocell.application.first_motion_worker_claim import claim_first_motion_worker
    from rocell.safety.first_motion_review_authority import AuthenticatedFirstMotionReviewReader
    from rocell.providers.windows.first_motion_current_context import FirstMotionCurrentContextReader
    from rocell.providers.windows.first_motion_trial_execution import execute_native_first_motion_trial
    from rocell.providers.windows.first_motion_serial_api import WindowsFirstMotionSerialApi
    if sys.argv[3]=='execute-one':
        from threading import Event
        try:
            request_raw=sys.stdin.buffer.read(65537)
            wire=decode_request(request_raw)
            child=execute_first_motion_child(Path(__file__).resolve().parents[5],request_raw,cancellation=Event())
            sys.stdout.buffer.write(encode_result(child,wire))
            sys.stdout.buffer.flush()
            return 0
        except Exception as error:
            sys.stdout.buffer.write(json.dumps(dict(schema='rocell.first_motion_child_error.v1',
                error_type=type(error).__name__,physical_authority=False,replay_allowed=False)).encode('ascii'))
            sys.stdout.buffer.flush()
            return 1
    report=dict(schema='rocell.first_motion_native_import_check.v1',
        status='IMPORTS_OK_NOT_HARDWARE_TESTED',native=WindowsFirstMotionSerialApi('COM4096').status(),
        physical_authority=False,connected=False,live_entry_enabled=False,
        registered_execution_mode='execute-one',signed_reserved_request_required=True)
    sys.stdout.buffer.write(json.dumps(report,sort_keys=True,separators=(',',':')).encode('ascii'))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
