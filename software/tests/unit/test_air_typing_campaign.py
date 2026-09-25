from pathlib import Path
import hashlib
import shutil
import subprocess

import pytest

from rocell.application.air_typing_campaign import AirTypingHost, TARGETS, assess_leg
from rocell.application.wizard_diagnostic_export import verify_export


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path_factory.mktemp("air-typing-native") / "owner.exe"
    result = subprocess.run([compiler, "-std=c++17", "-O2",
        "-I" + str(ROOT / "firmware/diagnostics"),
        str(ROOT / "firmware/diagnostics/test_air_typing_owner.cpp"),
        "-o", str(target)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return target


@pytest.fixture(scope="module")
def records(native):
    result = subprocess.run([str(native), "success"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    return [bytes.fromhex(line) for line in result.stdout.splitlines()]


@pytest.mark.parametrize("mode", ["delivery", "wrong_endpoint", "evidence", "source", "prewrite", "stale", "timeout", "expired"])
@pytest.mark.parametrize("leg", range(1, 18))
def test_native_fault_stops(native, mode, leg):
    result = subprocess.run([str(native), mode, str(leg)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, (mode, leg, result.stderr, result.returncode)


def test_independent_leg_assessment(records):
    previous = None
    assert len(records) == len(TARGETS) == 17
    for leg, raw in enumerate(records, 1):
        previous = assess_leg(raw, boot="ab" * 16, leg=leg, previous=previous)
        assert previous["status"] == "LEG_ENDPOINT_VERIFIED"
        assert previous["target_goals"] == list(TARGETS[leg - 1])
        assert previous["physical_accuracy_verified"] is False
    with pytest.raises(ValueError):
        assess_leg(records[0], boot="cd" * 16, leg=1)
    with pytest.raises(ValueError):
        assess_leg(records[0], boot="ab" * 16, leg=2)


class Transport:
    def __init__(self, records, bad_receipt=0):
        self.records = records
        self.leg = 1
        self.receipts = []
        self.bad_receipt = bad_receipt

    def __call__(self, method, path, body=b""):
        suffix = path.rsplit("/", 1)[-1]
        if suffix == "start":
            assert method == "POST" and body == b"AIR17"
            return b"CAPTURING_START"
        if suffix == "status":
            return f"AWAITING_EXPORT|{self.leg}".encode()
        if suffix == "record":
            return self.records[self.leg - 1].hex().encode()
        if suffix == "receipt":
            assert body == f"{self.leg}:{hashlib.sha256(self.records[self.leg-1]).hexdigest()}".encode()
            self.receipts.append(self.leg)
            if self.bad_receipt == self.leg:
                raise TimeoutError("lost receipt")
            self.leg += 1
            return b"COMPLETE" if self.leg == 18 else f"READY|{self.leg}".encode()
        if suffix == "next":
            assert body == str(self.leg).encode()
            return b"CAPTURING_START"
        raise AssertionError(path)


def test_full_export_gated_campaign(records, tmp_path):
    transport = Transport(records)
    host = AirTypingHost(transport, boot="ab" * 16, export_root=tmp_path, source_kind="simulation")
    result = host.run_once()
    assert result["status"] == "CAMPAIGN_COMPLETE"
    assert transport.receipts == list(range(1, 18))
    assert all(verify_export(Path(p))["valid"] for p in result["exports"])
    from rocell.application.air_typing_scoring import score_exported_campaign
    export_ids = [Path(p).name for p in result["exports"]]
    score = score_exported_campaign(tmp_path, export_ids, boot="ab" * 16, source_kind="simulation")
    assert score["verified_legs"] == 17
    assert score["virtual_key_sequence"] == "ABA"
    assert score["physical_accuracy_verified"] is False
    with pytest.raises(ValueError, match="distinct"):
        score_exported_campaign(tmp_path, export_ids[:-1] + export_ids[:1], boot="ab" * 16)
    with pytest.raises(ValueError, match="One fixed"):
        host.run_once()


@pytest.mark.parametrize("leg", [1, 9, 17])
def test_uncertain_receipt_stops_no_retry(records, tmp_path, leg):
    transport = Transport(records, bad_receipt=leg)
    with pytest.raises(ValueError, match="Campaign stopped"):
        AirTypingHost(transport, boot="ab" * 16, export_root=tmp_path).run_once()
    assert transport.receipts == list(range(1, leg + 1))
