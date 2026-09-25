"""Five-leg signed simulation proves export-gated continuation and fault stop."""
from pathlib import Path
import hashlib
import hmac
import shutil
import subprocess

import pytest

from rocell.application.characterization_request_auth import sign_request
from rocell.application.reviewed_hover_recovery_admission import (
    encode_recovery_admission, recovery_manifest, validate_recovery_manifest,
)
from rocell.application.reviewed_hover_recovery_simulated_host import (
    ReviewedHoverRecoverySimulatedHost,
)
from rocell.application.wizard_diagnostic_export import verify_export


ROOT = Path(__file__).resolve().parents[2]
KEY = bytes(range(32))
BOOT = "ab" * 16
RELEASE = "12" * 32


@pytest.fixture(scope="module")
def records(tmp_path_factory):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path_factory.mktemp("recovery-host") / "owner.exe"
    build = subprocess.run([compiler, "-std=c++17", "-O2",
        str(ROOT / "firmware/diagnostics/test_reviewed_hover_recovery_owner.cpp"),
        "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target), "records"], capture_output=True,
                         text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    digest = bytes.fromhex(validate_recovery_manifest(recovery_manifest()))
    raw = [bytes.fromhex(line) for line in run.stdout.splitlines()]
    assert len(raw) == 5
    return [item[:26] + digest + item[58:] for item in raw]


class Simulator:
    simulation_only = True

    def __init__(self, records, export_root, fault=None):
        self.records = records
        self.export_root = export_root
        self.fault = fault
        self.leg = 1
        self.sequence = 0
        self.receipts = []
        self.requests = []

    def __call__(self, request):
        method, path, body = request["method"], request["path"], request["body"]
        assert path.startswith("/rocell/recovery-hover/")
        assert request["headers"]["X-Rocell-Sequence"] == str(self.sequence)
        assert request["headers"]["X-Rocell-Signature"] == sign_request(
            key=KEY, boot=BOOT, sequence=self.sequence, method=method,
            path=path, body=body).hex()
        self.requests.append((method, path, body))
        suffix = path.rsplit("/", 1)[-1]
        if suffix == "start":
            assert body == encode_recovery_admission(recovery_manifest(),
                boot=BOOT, release_sha256=RELEASE,
                authorize_noncontact_motion=True)
            reply = b"CAPTURING_START"
        elif suffix == "status":
            reply = f"AWAITING_EXPORT|{self.leg}".encode()
        elif suffix == "record":
            reply = self.records[self.leg - 1].hex().encode()
        elif suffix == "receipt":
            expected = (f"{self.leg}:" + hashlib.sha256(
                self.records[self.leg - 1]).hexdigest()).encode()
            assert body == expected
            # All prior legs, including this one, must be durable before a
            # matching acknowledgement is sent to the simulated controller.
            assert len(list(self.export_root.glob("wizard-*"))) == self.leg
            self.receipts.append(self.leg)
            if self.fault == ("receipt_lost", self.leg):
                raise ConnectionError("simulated lost acknowledgement")
            self.leg += 1
            reply = b"COMPLETE" if self.leg == 6 else f"READY|{self.leg}".encode()
        elif suffix == "next":
            assert body == str(self.leg).encode()
            reply = b"CAPTURING_START"
        else:
            raise AssertionError(path)
        unsigned = (b"RCCRESPONSE01\0" + bytes.fromhex(BOOT) +
                    self.sequence.to_bytes(4, "big") + (200).to_bytes(2, "big") +
                    hashlib.sha256(reply).digest())
        result = dict(status=200, body=reply, sequence=str(self.sequence),
                      signature=hmac.digest(KEY, unsigned, "sha256").hex())
        self.sequence += 1
        return result


def test_five_leg_simulated_recovery_exports_before_every_receipt(records, tmp_path):
    simulator = Simulator(records, tmp_path)
    host = ReviewedHoverRecoverySimulatedHost(simulator, boot=BOOT, key=KEY,
        release_sha256=RELEASE, export_root=tmp_path)
    result = host.run_once()
    assert result["status"] == "REVIEWED_HOVER_RECOVERY_SIMULATED_COMPLETE"
    assert simulator.receipts == [1, 2, 3, 4, 5]
    assert len(result["exports"]) == 5
    assert all(verify_export(Path(path))["valid"] for path in result["exports"])
    assert not result["hardware_access"] and not result["motion_authorized"]
    with pytest.raises(ValueError, match="consumed"):
        host.run_once()


def test_bad_endpoint_stops_without_receipt_or_next(records, tmp_path):
    changed = records[:]
    bad = bytearray(changed[2]); bad[59] = 0; changed[2] = bytes(bad)
    simulator = Simulator(changed, tmp_path)
    host = ReviewedHoverRecoverySimulatedHost(simulator, boot=BOOT, key=KEY,
        release_sha256=RELEASE, export_root=tmp_path)
    with pytest.raises(ValueError, match="Simulated recovery stopped; evidence:"):
        host.run_once()
    assert simulator.receipts == [1, 2]
    assert len(list(tmp_path.glob("wizard-*"))) == 3


def test_lost_receipt_stops_without_retry(records, tmp_path):
    simulator = Simulator(records, tmp_path, fault=("receipt_lost", 2))
    host = ReviewedHoverRecoverySimulatedHost(simulator, boot=BOOT, key=KEY,
        release_sha256=RELEASE, export_root=tmp_path)
    with pytest.raises(ValueError, match="Simulated recovery stopped; evidence:"):
        host.run_once()
    assert simulator.receipts == [1, 2]
    assert host.session.stopped
    assert host.session.uncertainty["continuation_may_have_been_authorized"]
    assert not host.session.uncertainty["retry_allowed"]
    assert simulator.requests[-1][1].endswith("/receipt")
