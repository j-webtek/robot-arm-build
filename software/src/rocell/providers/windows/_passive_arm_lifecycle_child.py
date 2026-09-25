"""Fixed isolated child: actual lifecycle algorithm, memory-only Win32 API."""

import hashlib
import json
from pathlib import Path
import sys
from threading import Event


def main():
    path = Path(sys.argv[1])
    if not path.is_absolute() or path.name != "passive-lifecycle.zip":
        return 3
    with path.open("rb") as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != sys.argv[2]:
        return 4
    # The parent checks the archive against the exact closed source roster and
    # pins it for this process lifetime. -I -S excludes user/site import paths.
    sys.path.insert(0, str(path))
    from rocell.application.arm_bench_qualification_contract import (
        PassiveBenchRequest,
        _canonical,
    )
    from rocell.application.physical_connection_contracts import (
        EvidenceOrigin,
        RoArmUsbSerialIdentity,
        UsbDriverIdentity,
    )
    from rocell.providers.windows.arm_feedback_worker import ReviewedControllerBinding
    from rocell.providers.windows.nonpurging_serial_api import (
        IncapableWin32SerialApi,
        IncapableWin32Scenario,
    )
    from rocell.providers.windows.passive_serial_observation import observe_rehearsal
    from rocell.providers.windows.owned_worker_process import decode_owned_json

    outer = decode_owned_json(sys.stdin.buffer.read(64 * 1024 + 1), maximum=64 * 1024)
    core = {key: value for key, value in outer.items() if key != "request_sha256"}
    if hashlib.sha256(_canonical(core)).hexdigest() != outer["request_sha256"]:
        return 5
    payload = outer["payload"]
    scenario = sys.argv[3]
    failures = {
        "lifecycle-nominal": (),
        "lifecycle-open-failed": ("create_file",),
        "lifecycle-cleanup-unknown": ("close_port",),
    }
    if scenario not in failures or payload["scenario"] != scenario:
        return 6
    request = PassiveBenchRequest(_canonical(payload["request"]))
    identity = RoArmUsbSerialIdentity(
        "ffff",
        "0002",
        "SYNTHETIC-NOT-A-DEVICE",
        "USB\\VID_FFFF&PID_0002\\SYNTHETIC-NOT-A-DEVICE",
        "usb-unit:ffff:0002:SYNTHETIC-NOT-A-DEVICE",
        "COM404",
        UsbDriverIdentity("SYNTHETIC", "synthetic", "1.0", "synthetic.inf"),
    )
    binding = ReviewedControllerBinding(
        identity,
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "5" * 64,
        EvidenceOrigin.SYNTHETIC_REHEARSAL,
    )
    api = IncapableWin32SerialApi(
        IncapableWin32Scenario(
            startup_bytes=b"SYNTHETIC lifecycle startup\r\n",
            fail_operations=failures[scenario],
        )
    )
    observed = observe_rehearsal(request, binding, api, Event())
    result = dict(
        schema="rocell.owned_passive_arm_fixture_result.v1",
        request_sha256=outer["request_sha256"],
        attempt_id=outer["attempt_id"],
        physical_authority=False,
        scenario=scenario,
        passive_result=observed["result"],
        lifecycle=observed["lifecycle"],
    )
    sys.stdout.buffer.write(_canonical(result))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
