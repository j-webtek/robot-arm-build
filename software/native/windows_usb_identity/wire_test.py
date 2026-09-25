"""Only the separately linked incapable native producer is executed here."""

from pathlib import Path
import json
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from rocell.providers.windows.usb_identity_protocol import (  # noqa: E402
    UsbIdentityObservation,
    UsbIdentityAdmissionRequest,
    canonical,
    parse_usb_identity_observation,
)

SCENARIOS = (
    "nominal",
    "unicode",
    "usb2",
    "pipes",
    "maximum-raw",
    "v2-unavailable",
    "no-serial",
    "duplicate-mapping",
    "changed-device",
    "malformed-device",
    "malformed-language",
    "malformed-serial",
    "language-conflict",
    "malformed-ex",
    "malformed-v2",
    "close-failure",
    "call-limit",
    "api-failure",
    "timeout",
    "cancelled",
    "byte-limit",
)


def main():
    executable = Path(sys.argv[1]).resolve()
    assert executable.name == "rocell_usb_identity_tests.exe"
    request = UsbIdentityAdmissionRequest(
        subprocess.run(
            [str(executable), "--request"], capture_output=True, check=True, timeout=10
        ).stdout.rstrip(b"\r\n")
    )
    for scenario in SCENARIOS:
        raw = subprocess.run(
            [str(executable), "--emit", scenario],
            capture_output=True,
            check=True,
            timeout=10,
        ).stdout
        assert len(raw) <= 65538
        value = UsbIdentityObservation(canonical(json.loads(raw)))
        bound = request
        if scenario == "unicode":
            bound = UsbIdentityAdmissionRequest(
                subprocess.run(
                    [str(executable), "--request", "unicode"],
                    capture_output=True,
                    check=True,
                    timeout=10,
                ).stdout.rstrip(b"\r\n")
            )
        parse_usb_identity_observation(raw, request=bound)
        if scenario in {"malformed-ex", "maximum-raw"}:
            scans = [
                row
                for row in value.to_dict()["calls"]
                if row["operation"] == "CONNECTION_EX" and row["status"] == "OK"
            ]
            assert scans and all(row["returned_raw_hex"] is not None for row in scans)
            assert all(
                len(bytes.fromhex(row["returned_raw_hex"])) == row["returned_bytes"]
                for row in scans
            )
        print(scenario, len(raw), value.to_dict()["outcome"], flush=True)
    print(f"{len(SCENARIOS)} actual incapable native -> Python receipts verified")


if __name__ == "__main__":
    main()
