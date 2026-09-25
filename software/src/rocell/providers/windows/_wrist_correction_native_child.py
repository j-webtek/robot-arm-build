"""Isolated correction entry; physical process-owner dispatch remains gated."""
import hashlib
import json
from pathlib import Path
import sys


def main():
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv)!=4:
        return 2
    path=Path(sys.argv[1])
    if not path.is_absolute() or path.name!='wrist-correction-native.zip':
        return 3
    if sys.argv[3] not in ('check-imports','execute-one'):
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
        raise RuntimeError('CORRECTION_IMPORT_AUDIT_HOST_ACCESS_FORBIDDEN')
    if sys.argv[3]=='check-imports':
        ctypes.WinDLL=forbidden
        subprocess.Popen=forbidden
        socket.socket=forbidden
        os.open=forbidden
    sys.path.insert(0,str(path))
    from rocell.providers.windows.wrist_correction_trial_execution import _execute_claimed_correction_trial
    from rocell.providers.windows.wrist_correction_parent_review import review_correction_child_result
    from rocell.providers.windows.wrist_correction_native_result import encode_result,decode_result
    from rocell.providers.windows.wrist_correction_evidence_store import authenticate_evidence
    from rocell.providers.windows.wrist_correction_prelaunch import verify_reserved_correction_entry
    from rocell.providers.windows.wrist_correction_child_execution import execute_correction_child
    from rocell.providers.windows.wrist_correction_serial_api import WindowsWristCorrectionSerialApi
    from rocell.providers.windows.wrist_correction_invocation import verify_actual_invocation
    if sys.argv[3]=='execute-one':
        from threading import Event
        try:
            request_raw=sys.stdin.buffer.read(65537)
            verify_actual_invocation(request_raw,entry_path=Path(__file__).resolve(),executable=sys.executable,
                argv=('-I','-S',*sys.argv),working_directory=Path.cwd())
            child=execute_correction_child(Path(__file__).resolve().parents[5],request_raw,cancellation=Event())
            sys.stdout.buffer.write(encode_result(child,request_raw=request_raw))
            sys.stdout.buffer.flush()
            return 0
        except Exception as error:
            sys.stdout.buffer.write(json.dumps(dict(schema='rocell.wrist_correction_child_error.v1',
                error_type=type(error).__name__,physical_authority=False,replay_allowed=False)).encode('ascii'))
            sys.stdout.buffer.flush()
            return 1
    report=dict(schema='rocell.wrist_correction_import_check.v1',status='IMPORTS_OK_NOT_HARDWARE_TESTED',
        native=WindowsWristCorrectionSerialApi('COM4096').status(),connected=False,
        physical_authority=False,live_entry_enabled=False,registered_execution_mode='execute-one',
        signed_reserved_request_required=True)
    sys.stdout.buffer.write(json.dumps(report,sort_keys=True,separators=(',',':')).encode('ascii'))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
