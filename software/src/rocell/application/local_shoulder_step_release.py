"""Bind a local step to reviewed r31 installation, startup and fresh idle state.

This performs read-only checks. It does not prepare or authorize a movement.
Retained installation evidence describes a verified prior flash operation, not
an independent measurement of current firmware bytes.
"""
from pathlib import Path

from .hold_transport_export import capture_hold_transport
from .hold_transport_snapshot import HoldHTTPReader
from .shoulder_session_http import ShoulderSessionHTTP
from .supported_recovery_installation import review_recovery_startup


def bind_local_step(root, *, software_root, startup_export, boot, exchange):
    if (software_root is None or not startup_export or
            type(exchange) is not ShoulderSessionHTTP):
        raise ValueError('Local step release binding requires r31 startup evidence and live adapter')
    software = Path(software_root).resolve()
    if (Path(root).resolve() != software / 'runs/wizard-exports' or
            exchange.port != 80 or exchange.failed or exchange.attempts or
            not exchange.local_step_capability or not exchange.settling_capability):
        raise ValueError('Local step release binding requires unused capable transport and workspace exports')
    binding = review_recovery_startup(software, startup_export, revision=31)
    if binding['expected_boot'] != boot or binding['address'] != exchange.address:
        raise ValueError('Local step release binding differs from startup')
    # Retained startup alone is insufficient: reject a different or busy boot
    # before the runner reserves its command or sends any POST.
    capture = capture_hold_transport(root, HoldHTTPReader(binding['address']), expected_boot=boot)
    summary = capture['summary']
    status = summary.get('status', {})
    if (summary.get('category') != 'TRANSPORT_CAPTURED' or status.get('state') != 'IDLE' or
            status.get('reason') != 'NOT_CONFIGURED' or status.get('records') != 0 or
            status.get('storage_fault') is not False):
        raise ValueError('Fresh same-boot idle state required for local step')
    return dict(startup=binding, fresh_idle_capture=capture, revision=31)
