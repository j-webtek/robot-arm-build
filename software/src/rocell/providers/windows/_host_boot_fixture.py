"""Sealed incapable child: no CIM, metadata enumeration, device or network API."""

import hashlib
import json
import os
import subprocess
import sys
import time


def main():
    scenario = sys.argv[1] if len(sys.argv) == 2 else "invalid"
    wire = sys.stdin.buffer.read(4097)
    if not 0 < len(wire) <= 4096:
        return 64
    if scenario == "stall":
        time.sleep(60)
    elif scenario in {"stdout-flood", "stderr-flood"}:
        stream = sys.stdout.buffer if scenario == "stdout-flood" else sys.stderr.buffer
        while True:
            stream.write(b"x" * 4096)
            stream.flush()
    elif scenario == "spawn-child":
        # The current owner permits one Job member. This fixed attempted child
        # must be denied/contained; it never accesses a provider or device.
        sys.stderr.write("FIXTURE_DESCENDANT_ATTEMPT\n")
        sys.stderr.flush()
        try:
            child = subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", "import time; time.sleep(60)"],
                creationflags=0x8,
            )
        except OSError:
            sys.stderr.write("FIXTURE_DESCENDANT_CREATION_DENIED\n")
            sys.stderr.flush()
            return 72
        child.wait()
        return 73
    elif scenario == "malformed":
        sys.stdout.write('{"x":1,"x":2}')
        return 0
    elif scenario == "exit-failure":
        return 71
    elif scenario not in {"nominal", "wrong-binding"}:
        return 65
    value = {
        "schema": "rocell.windows_local_cim_boot.v1",
        "request_sha256": (
            hashlib.sha256(wire).hexdigest() if scenario == "nominal" else "0" * 64
        ),
        "provider": "WINDOWS_LOCAL_CIM",
        "machine_uuid": "12345678-1234-5678-9abc-0123456789ab",
        "last_boot_up_time_utc": "2020-01-01T00:00:00.000000Z",
        "confirmation_boot_up_time_utc": "2020-01-01T00:00:00.000000Z",
        "os_version": "10.0.19045",
        "os_build": "19045",
    }
    sys.stdout.write(json.dumps(value, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
