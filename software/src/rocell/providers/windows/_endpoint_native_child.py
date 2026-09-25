"""Fixed isolated endpoint entry; execute-one requires the reserved signed request."""

import hashlib
import json
from pathlib import Path
import sys


def main():
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv)!=4:
        return 2
    path = Path(sys.argv[1])
    if not path.is_absolute() or path.name!='endpoint-native.zip':
        return 3
    if sys.argv[3] not in {'check-imports','execute-one'}:
        return 5  # No hidden live mode or fallback to a generic worker.
    with path.open('rb') as stream:
        raw = stream.read(8*1024*1024+1)
    if len(raw)>8*1024*1024 or hashlib.sha256(raw).hexdigest()!=sys.argv[2]:
        return 4
    import ctypes
    import subprocess
    import socket
    import os
    def forbidden(*args,**kwargs):
        raise RuntimeError('ENDPOINT_IMPORT_CHECK_HOST_ACCESS_FORBIDDEN')
    if sys.argv[3]=='check-imports':
        ctypes.WinDLL = forbidden
        subprocess.Popen = forbidden
        socket.socket = forbidden
        os.open = forbidden
    sys.path.insert(0,str(path))
    from rocell.application.endpoint_trial_contract import EndpointTrialRequest
    from rocell.application.endpoint_reference_reader import EndpointReferenceReader
    from rocell.application.endpoint_evidence_snapshot import decode_snapshot
    from rocell.application.endpoint_worker_claim import claim_endpoint_worker
    from rocell.safety.bench_review_authority import AuthenticatedBenchReviewReader
    from rocell.providers.windows.endpoint_serial_connection import EndpointSerialConnection
    from rocell.providers.windows.endpoint_trial_execution import execute_native_endpoint_trial
    from rocell.providers.windows.endpoint_serial_api import WindowsEndpointSerialApi
    from rocell.providers.windows.controller_metadata import WindowsControllerMetadataAcquirer
    from rocell.providers.windows.endpoint_native_wire import decode_request
    from rocell.providers.windows.endpoint_native_result import decode_result
    from rocell.providers.windows.bench_review_key import load_bench_review_authority
    from rocell.providers.windows.endpoint_current_context import EndpointCurrentContextReader
    from rocell.providers.windows.endpoint_child_execution import execute_endpoint_child
    if sys.argv[3]=='execute-one':
        from threading import Event
        from rocell.providers.windows.endpoint_native_result import encode_result
        try:
            request_raw = sys.stdin.buffer.read(65537)
            wire = decode_request(request_raw)
            result = execute_endpoint_child(Path(__file__).resolve().parents[5],request_raw,cancellation=Event())
            sys.stdout.buffer.write(encode_result(result,wire))
            sys.stdout.buffer.flush()
            return 0
        except Exception as error:
            sys.stdout.buffer.write(json.dumps({'schema':'rocell.endpoint_child_error.v1',
                'error_type':type(error).__name__,'physical_authority':False,'replay_allowed':False}).encode('ascii'))
            sys.stdout.buffer.flush()
            return 1
    report = {'schema':'rocell.endpoint_native_import_check.v1',
              'status':'IMPORTS_OK_NOT_HARDWARE_TESTED',
              'native':WindowsEndpointSerialApi('COM4096').status(),
              'physical_authority':False,'connected':False,'live_entry_enabled':False,
              'registered_execution_mode':'execute-one','signed_reserved_request_required':True}
    sys.stdout.buffer.write(json.dumps(report,sort_keys=True,separators=(',',':')).encode('ascii'))
    sys.stdout.buffer.flush()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
