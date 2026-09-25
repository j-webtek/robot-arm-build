"""Isolated import audit and authenticated, bounded attended campaign entry."""
import hashlib
import json
from pathlib import Path
import sys


def main():
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv) != 4:
        return 2
    path = Path(sys.argv[1])
    if not path.is_absolute() or path.name != 'positional-campaign-native.zip':
        return 3
    # Reject unknown modes before loading any application or native module.
    if sys.argv[3] not in ('check-imports', 'execute-campaign'):
        return 5
    with path.open('rb') as stream:
        raw = stream.read(8*1024*1024 + 1)
    if len(raw) > 8*1024*1024 or hashlib.sha256(raw).hexdigest() != sys.argv[2]:
        return 4
    import ctypes
    import subprocess
    import socket
    import os
    def forbidden(*args, **kwargs):
        raise RuntimeError('CAMPAIGN_IMPORT_AUDIT_HOST_ACCESS_FORBIDDEN')
    if sys.argv[3] == 'check-imports':
        ctypes.WinDLL = forbidden
        subprocess.Popen = forbidden
        socket.socket = forbidden
        os.open = forbidden
    sys.path.insert(0, str(path))
    from rocell.providers.windows.positional_campaign_child_execution import _execute_authenticated_campaign_child
    from rocell.providers.windows.positional_campaign_native_protocol import decode_request
    from rocell.providers.windows.positional_campaign_invocation import verify_actual_invocation
    from rocell.providers.windows.positional_campaign_bootstrap import prepare_authenticated_campaign_reader
    from rocell.providers.windows.positional_campaign_prelaunch import verify_reserved_campaign_entry
    from rocell.application.positional_campaign_native_review import review_native_campaign
    from rocell.application.positional_campaign_reference_reader import PositionalCampaignReferenceReader, FrozenPositionalCampaignReferences
    from rocell.application.positional_campaign_native_retention import publish_native_campaign_result
    if sys.argv[3] == 'execute-campaign':
        from threading import Event
        try:
            request_raw = sys.stdin.buffer.read(65537)
            verify_actual_invocation(request_raw, entry_path=Path(__file__).resolve(), executable=sys.executable,
                argv=('-I', '-S', *sys.argv), working_directory=Path.cwd())
            cancellation = Event()
            reader = verify_reserved_campaign_entry(Path(__file__).resolve().parents[5], request_raw,
                cancellation=cancellation)
            receipt = _execute_authenticated_campaign_child(request_raw, reader, cancellation=cancellation)
            sys.stdout.buffer.write(receipt)
            sys.stdout.buffer.flush()
            return 0
        except Exception as error:
            sys.stdout.buffer.write(json.dumps(dict(schema='rocell.positional_campaign_child_error.v1',
                error_type=type(error).__name__, error_message=str(error)[:512],
                physical_authority=False, replay_allowed=False)).encode('ascii'))
            sys.stdout.buffer.flush()
            return 1
    report = dict(schema='rocell.positional_campaign_import_check.v1',
        status='IMPORTS_OK_NOT_HARDWARE_TESTED', connected=False,
        physical_authority=False, live_entry_enabled=False, replay_allowed=False)
    sys.stdout.buffer.write(json.dumps(report, sort_keys=True, separators=(',', ':')).encode('ascii'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
