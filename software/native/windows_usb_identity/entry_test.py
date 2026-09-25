"""Bounded inherited-pipe tests of the separately linked incapable child only."""

from pathlib import Path
import json
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from rocell.providers.windows.usb_identity_protocol import (  # noqa: E402
    UsbIdentityAdmissionRequest,
    canonical,
    parse_owned_usb_identity_result,
    parse_usb_identity_ready,
    usb_identity_release,
)


def main():
    child, producer = map(lambda p: Path(p).resolve(), sys.argv[1:])
    assert child.name == "rocell_usb_identity_entry_tests.exe"
    assert producer.name == "rocell_usb_identity_tests.exe"
    request = UsbIdentityAdmissionRequest(
        subprocess.run(
            [str(producer), "--request"], capture_output=True, check=True, timeout=10
        ).stdout.rstrip(b"\r\n")
    )
    for scenario in (
        "nominal",
        "wrong-permit",
        "extra-input",
        "wrong-hash",
        "eof-only",
        "no-eof",
    ):
        expected = "0" * 64 if scenario == "wrong-hash" else request.request_sha256
        p = subprocess.Popen(
            [str(child), "--owned-usb-identity", "--request-sha256", expected],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            p.stdin.write(request.wire())
            p.stdin.flush()
            ready_wire = p.stdout.readline()
            if scenario == "wrong-hash":
                assert not ready_wire
            else:
                ready = parse_usb_identity_ready(
                    ready_wire,
                    expected_request_sha256=request.request_sha256,
                    expected_child_pid=p.pid,
                )
                release = usb_identity_release(request, ready)
                if scenario == "wrong-permit":
                    data = json.loads(release)
                    data["permit_sha256"] = "0" * 64
                    release = canonical(data) + b"\n"
                if scenario != "eof-only":
                    p.stdin.write(release)
                    if scenario == "extra-input":
                        p.stdin.write(b"extra\n")
                    p.stdin.flush()
                    if scenario == "no-eof":
                        p.wait(timeout=7)
            p.stdin.close()
            p.stdin = None
            stdout, stderr = p.communicate(timeout=8)
            if scenario == "nominal":
                assert p.returncode == 0 and not stderr
                _, observation = parse_owned_usb_identity_result(
                    stdout, request=request, ready=ready, returncode=p.returncode
                )
                assert observation.to_dict()["outcome"] == "OBSERVED"
            else:
                assert p.returncode == 2 and not stdout and not stderr
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate(timeout=5)
    # A raw endpoint CLI is never an alternate entry, even on the incapable target.
    r = subprocess.run(
        [str(child), "--endpoint", "arbitrary"], capture_output=True, timeout=5
    )
    assert r.returncode == 2 and not r.stdout
    print("7 incapable inherited-pipe admission cases passed")


if __name__ == "__main__":
    main()
