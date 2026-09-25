"""Native/host contract and mutation tests for offline hover evidence."""
from pathlib import Path
import hashlib
import hmac
import shutil
import subprocess

import pytest

from rocell.application.reviewed_hover_manifest import (
    encode_reviewed_hover_start, ghost_key_manifest, validate_manifest,
)
from rocell.application.reviewed_hover_record import (
    assess_reviewed_hover_leg, decode_reviewed_hover_record,
)
from rocell.application.reviewed_hover_offline_campaign import review_offline_campaign
from rocell.application.reviewed_hover_simulated_host import ReviewedHoverSimulatedHost
from rocell.application.characterization_request_auth import sign_request
from rocell.application.wizard_diagnostic_export import verify_export


ROOT = Path(__file__).resolve().parents[2]


def test_exact_native_start_body_uses_validated_canonical_manifest():
    manifest = ghost_key_manifest()
    body = encode_reviewed_hover_start(manifest)
    assert body.startswith(b"RCHM1:10:01020100040504030102010004050403:")
    assert body.endswith(validate_manifest(manifest)["manifest_sha256"].encode())
    assert len(body) == 106


@pytest.fixture(scope="module")
def records(tmp_path_factory):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path_factory.mktemp("hover-records") / "owner.exe"
    result = subprocess.run([compiler, "-std=c++17", "-O2",
        str(ROOT / "firmware/diagnostics/test_reviewed_hover_owner.cpp"),
        "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    output = subprocess.run([str(target), "success"], capture_output=True,
                            text=True, timeout=10)
    assert output.returncode == 0, output.stderr
    return [bytes.fromhex(line) for line in output.stdout.splitlines()]


def test_native_records_are_not_mistaken_for_real_manifest(records):
    # The harness binds a synthetic digest; the host must reject it.
    with pytest.raises(ValueError, match="binding"):
        assess_reviewed_hover_leg(records[0], manifest=ghost_key_manifest(),
                                  boot="ab" * 16, leg=1)


def test_decoder_and_mutations(records):
    decoded = decode_reviewed_hover_record(records[0])
    assert decoded["leg"] == 1 and decoded["pose_id"] == 1
    assert len(decoded["before"]) == 3 and len(decoded["after"]) == 3
    assert decoded["writes_attempted"] == 1
    for index, value in [(0, 0), (70, 2)]:
        changed = bytearray(records[0]); changed[index] = value
        with pytest.raises(ValueError):
            decode_reviewed_hover_record(bytes(changed))
    with pytest.raises(ValueError, match="framing"):
        decode_reviewed_hover_record(records[0][:-1])


def test_full_native_sequence_with_reviewed_manifest_digest(records):
    # Substitute only the harness's synthetic digest to model the wire value
    # produced by a future authenticated route. All motion evidence remains
    # untouched and must independently satisfy host rules.
    digest = bytes.fromhex(validate_manifest(ghost_key_manifest())["manifest_sha256"])
    previous = None
    for leg, raw in enumerate(records, 1):
        rebound = raw[:26] + digest + raw[58:]
        previous = assess_reviewed_hover_leg(rebound, manifest=ghost_key_manifest(),
                                             boot="ab" * 16, leg=leg, previous=previous)
        assert previous["leg"] == leg
        assert previous["status"] == "REVIEWED_HOVER_LEG_VERIFIED"


def test_host_rejects_wrong_boot_target_and_tampered_feedback(records):
    digest = bytes.fromhex(validate_manifest(ghost_key_manifest())["manifest_sha256"])
    raw = records[0][:26] + digest + records[0][58:]
    for offset in (10, 60, 65, 71, 87):
        bad = bytearray(raw); bad[offset] ^= 1
        with pytest.raises(ValueError):
            assess_reviewed_hover_leg(bytes(bad), manifest=ghost_key_manifest(),
                                      boot="ab" * 16, leg=1)


def _bound_records(records):
    digest = bytes.fromhex(validate_manifest(ghost_key_manifest())["manifest_sha256"])
    return [raw[:26] + digest + raw[58:] for raw in records]


def test_offline_campaign_exports_each_verified_leg_before_receipt_value(records, tmp_path):
    result = review_offline_campaign(_bound_records(records),
        manifest=ghost_key_manifest(), boot="ab" * 16, export_root=tmp_path)
    assert result["status"] == "REVIEWED_HOVER_OFFLINE_RECORDS_VERIFIED"
    assert len(result["exports"]) == len(result["simulated_receipts"]) == 16
    assert result["controller_receipts_sent"] is False
    assert result["motion_authorized"] is False
    assert all(verify_export(Path(path))["valid"] for path in result["exports"])
    assert all(receipt.startswith(f"{leg}:".encode())
               for leg, receipt in enumerate(result["simulated_receipts"], 1))


def test_offline_campaign_stops_on_corrupt_leg_and_exports_fault(records, tmp_path):
    altered = _bound_records(records)
    bad = bytearray(altered[7]); bad[59] = 2
    altered[7] = bytes(bad)
    with pytest.raises(ValueError, match="Offline campaign stopped; evidence:"):
        review_offline_campaign(altered, manifest=ghost_key_manifest(),
                                boot="ab" * 16, export_root=tmp_path)
    folders = list(tmp_path.glob("wizard-*"))
    assert len(folders) == 8
    assert all(verify_export(folder)["valid"] for folder in folders)


KEY = bytes(range(32))
BOOT = "ab" * 16


class SignedSimulator:
    simulation_only = True

    def __init__(self, records, fault=None):
        self.records = records
        self.fault = fault
        self.leg = 1
        self.sequence = 0
        self.receipts = []
        self.requests = []

    def __call__(self, request):
        method, path, body = request["method"], request["path"], request["body"]
        self.requests.append((method, path, body))
        assert request["headers"]["X-Rocell-Sequence"] == str(self.sequence)
        assert request["headers"]["X-Rocell-Signature"] == sign_request(
            key=KEY, boot=BOOT, sequence=self.sequence, method=method,
            path=path, body=body).hex()
        suffix = path.rsplit("/", 1)[-1]
        assert path.startswith("/rocell/reviewed-hover/")
        if suffix == "start":
            assert body == encode_reviewed_hover_start(ghost_key_manifest())
            response = b"CAPTURING_START"
        elif suffix == "status":
            response = f"AWAITING_EXPORT|{self.leg}".encode()
        elif suffix == "record":
            response = self.records[self.leg - 1].hex().encode()
        elif suffix == "receipt":
            assert body == (f"{self.leg}:" + hashlib.sha256(
                self.records[self.leg - 1]).hexdigest()).encode()
            self.receipts.append(self.leg)
            if self.fault == ("receipt_lost", self.leg):
                raise ConnectionError("simulated lost receipt reply")
            self.leg += 1
            response = b"COMPLETE" if self.leg == 17 else f"READY|{self.leg}".encode()
        elif suffix == "next":
            assert body == str(self.leg).encode()
            response = b"CAPTURING_START"
        else:
            raise AssertionError(path)
        digest = hashlib.sha256(response).digest()
        signed = (b"RCCRESPONSE01\0" + bytes.fromhex(BOOT) +
                  self.sequence.to_bytes(4, "big") + (200).to_bytes(2, "big") + digest)
        result = dict(status=200, body=response, sequence=str(self.sequence),
                      signature=hmac.digest(KEY, signed, "sha256").hex())
        if self.fault == ("bad_signature", self.leg) and suffix == "record":
            result["signature"] = "00" * 32
        self.sequence += 1
        return result


def test_signed_simulated_host_exports_before_every_receipt(records, tmp_path):
    simulator = SignedSimulator(_bound_records(records))
    host = ReviewedHoverSimulatedHost(simulator, manifest=ghost_key_manifest(),
                                     boot=BOOT, key=KEY, export_root=tmp_path)
    result = host.run_once()
    assert result["status"] == "REVIEWED_HOVER_SIMULATED_COMPLETE"
    assert result["simulated_receipts_sent"] == 16
    assert simulator.receipts == list(range(1, 17))
    assert all(verify_export(Path(path))["valid"] for path in result["exports"])
    assert not result["motion_authorized"]
    with pytest.raises(ValueError, match="consumed"):
        host.run_once()


def test_signed_simulated_host_stops_on_bad_record_before_receipt(records, tmp_path):
    altered = _bound_records(records)
    bad = bytearray(altered[7]); bad[59] = 2; altered[7] = bytes(bad)
    simulator = SignedSimulator(altered)
    host = ReviewedHoverSimulatedHost(simulator, manifest=ghost_key_manifest(),
                                     boot=BOOT, key=KEY, export_root=tmp_path)
    with pytest.raises(ValueError, match="Simulated campaign stopped; evidence:"):
        host.run_once()
    assert simulator.receipts == list(range(1, 8))
    assert len(list(tmp_path.glob("wizard-*"))) == 8


def test_lost_receipt_response_stops_without_retry(records, tmp_path):
    simulator = SignedSimulator(_bound_records(records), fault=("receipt_lost", 8))
    host = ReviewedHoverSimulatedHost(simulator, manifest=ghost_key_manifest(),
                                     boot=BOOT, key=KEY, export_root=tmp_path)
    with pytest.raises(ValueError, match="Simulated campaign stopped; evidence:"):
        host.run_once()
    assert simulator.receipts == list(range(1, 9))
    assert host.session.stopped
    assert host.session.uncertainty["continuation_may_have_been_authorized"]
    assert not host.session.uncertainty["retry_allowed"]
    last_receipt = next(index for index, (_, path, body) in
                        enumerate(simulator.requests)
                        if path.endswith("/receipt") and body.startswith(b"8:"))
    assert len(simulator.requests) == last_receipt + 1


def test_bad_signed_record_reply_stops_before_receipt(records, tmp_path):
    simulator = SignedSimulator(_bound_records(records), fault=("bad_signature", 8))
    host = ReviewedHoverSimulatedHost(simulator, manifest=ghost_key_manifest(),
                                     boot=BOOT, key=KEY, export_root=tmp_path)
    with pytest.raises(ValueError, match="Simulated campaign stopped; evidence:"):
        host.run_once()
    assert simulator.receipts == list(range(1, 8))
    assert host.session.stopped


def test_failed_export_prevents_first_receipt(records, tmp_path, monkeypatch):
    from rocell.application import reviewed_hover_simulated_host as module
    simulator = SignedSimulator(_bound_records(records))
    host = ReviewedHoverSimulatedHost(simulator, manifest=ghost_key_manifest(),
                                     boot=BOOT, key=KEY, export_root=tmp_path)
    actual_verify = module.verify_export
    calls = 0

    def fail_first_export(path):
        nonlocal calls
        calls += 1
        return {"valid": False} if calls == 1 else actual_verify(path)

    monkeypatch.setattr(module, "verify_export", fail_first_export)
    with pytest.raises(ValueError, match="Simulated campaign stopped; evidence:"):
        host.run_once()
    assert simulator.receipts == []
    assert calls == 2
